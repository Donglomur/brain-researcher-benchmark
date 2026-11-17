#!/usr/bin/env python3
"""Capture source V1 callback order and import a complete neural-only export.

No model, dataset, Lightning or Torch is imported. Capture runs in the operator's
author-inference process; import remains an offline artifact conversion.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys


EVALUATOR_SHA256 = "55916e0c191c94d480f18aff1dd587faffe71802c5802a75a1a09153f75f1f92"
CODE_COMMIT = "5f9889621d0df391c5aab37c996683d308e6e926"
CAPTURE_SCHEMA = "typing-v1-author-rank-capture-v1"
BUNDLE_SCHEMA = "typing-v1-author-capture-bundle-v1"


def _load_evaluator():
    path = Path(__file__).resolve().parent.parent / "v1-transcript-evaluation-v1" / "evaluator.py"
    if hashlib.sha256(path.read_bytes()).hexdigest() != EVALUATOR_SHA256:
        raise RuntimeError("frozen predecessor evaluator identity mismatch")
    spec = importlib.util.spec_from_file_location("typing_v1_frozen_evaluator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


E = _load_evaluator()


class CaptureError(E.PanelError):
    """Invalid or incomplete operator capture; never interpolate its contents."""


def require(condition, message):
    if not condition:
        raise CaptureError(message)


def fields(value, names, label):
    require(type(value) is dict and set(value) == set(names), "invalid " + label + " fields")


def class_id(value):
    require(type(value) is int and 0 <= value < 29, "invalid source class index")
    return value


def first_argmax(logits):
    """Match torch.max(vector, dim=0): first class wins finite-value ties."""
    require(type(logits) is list and len(logits) == 29, "expected 29 source logits per keystroke")
    require(all(type(x) is int or (type(x) is float and math.isfinite(x)) for x in logits),
            "source logits must be finite real numbers")
    return max(range(29), key=logits.__getitem__)


class RankCapture:
    """Sidecar collector called on the same outputs/batch as the source callback.

    The operator must save every rank's document after inference. This class does
    not gather processes or claim native Lightning integration has been tested.
    Unlike the author's zip(), mismatched batch lengths cannot silently truncate.
    Repeated observations are preserved so import can reject sampler padding.
    """

    def __init__(self, *, rank, world_size, run_manifest_sha256):
        require(type(world_size) is int and world_size > 0, "invalid world size")
        require(type(rank) is int and 0 <= rank < world_size, "invalid rank")
        E._sha(run_manifest_sha256, "run manifest digest")
        self.rank, self.world_size, self.run_manifest_sha256 = rank, world_size, run_manifest_sha256
        self.callback, self.order = {}, {}

    def add_batch(self, outputs, batch):
        require(type(outputs) in (tuple, list) and len(outputs) == 2, "invalid source batch outputs")
        predictions, targets = outputs
        # Tensor conversion is performed by the caller's existing tensor objects.
        # No device/model is instantiated by this component.
        logits_rows, typed = predictions.tolist(), targets.tolist()
        segments = batch.segments
        require(type(logits_rows) is list and type(typed) is list
                and len(logits_rows) == len(typed) == len(segments), "source batch length mismatch")
        staged = []
        for logits, target, segment in zip(logits_rows, typed, segments):
            uid = segment.trigger.extra.get("sentence_UID")
            stroke = segment.trigger.extra.get("button_UID")
            E._identifier(uid, "captured sentence UID")
            E._identifier(stroke, "captured button UID")
            sentence = getattr(segment.trigger, "sentence", None) or ""
            E._text(sentence, "captured presented sentence")
            staged.append((uid, stroke, sentence, first_argmax(logits), class_id(target), logits))
        # Validate all sentences before changing the capture (including two
        # disagreeing occurrences within this batch).
        references = {uid: row["true"] for uid, row in self.callback.items()}
        for uid, _, sentence, _, _, _ in staged:
            require(uid not in references or references[uid] == sentence,
                    "inconsistent presented sentence within capture")
            references[uid] = sentence
        for uid, stroke, sentence, prediction, target, logits in staged:
            row = self.callback.setdefault(uid, {"pred": [], "typed": [], "true": sentence, "logits": []})
            row["pred"].append(prediction)
            row["typed"].append(target)
            row["logits"].append(logits)
            self.order.setdefault(uid, []).append(stroke)

    def document(self):
        # Copy so later batches cannot retroactively mutate a returned document.
        return json.loads(json.dumps({"schema": CAPTURE_SCHEMA, "code_commit": CODE_COMMIT,
            "run_manifest_sha256": self.run_manifest_sha256, "rank": self.rank,
            "world_size": self.world_size, "callback": self.callback, "order": self.order}, allow_nan=False))


def bundle_documents(documents):
    """Pack captured documents; full coverage is checked only against the panel."""
    return {"schema": BUNDLE_SCHEMA, "shards": documents}


def convert_bytes(panel_raw, panel_sha256, capture_raw, capture_sha256, run_manifest_sha256, limits):
    """Return an evaluator-compatible submission and a reference-free receipt.

    Digests must come from the operator's independently frozen panel and run
    custody records. Self-attestation does not establish model competence.
    """
    for value, label in ((panel_sha256, "panel digest"), (capture_sha256, "capture digest"),
                         (run_manifest_sha256, "run manifest digest")):
        E._sha(value, label)
    require(type(panel_raw) is bytes and hashlib.sha256(panel_raw).hexdigest() == panel_sha256,
            "frozen panel digest mismatch")
    require(type(capture_raw) is bytes and hashlib.sha256(capture_raw).hexdigest() == capture_sha256,
            "frozen capture digest mismatch")
    contract = E.source_contract()
    panel = E.decode_json(panel_raw, label="panel", limits=limits, error=E.PanelError)
    _, test = E.validate_panel(panel, contract, limits)
    require(panel["condition"]["split_kind"] == "pinned-source-sentence-clusters"
            and panel["condition"]["representation"] == "per-keystroke-classes",
            "author bridge requires the original source output condition")
    bundle = E.decode_json(capture_raw, label="capture", limits=limits, error=CaptureError)
    fields(bundle, ("schema", "shards"), "capture bundle")
    require(bundle["schema"] == BUNDLE_SCHEMA and type(bundle["shards"]) is list
            and bool(bundle["shards"]), "invalid capture bundle")
    expected = {row["sentence_uid"]: row for row in test}
    seen, ranks, world_size, submissions = set(), set(), None, {}
    total_strokes = 0
    for shard in bundle["shards"]:
        fields(shard, ("schema", "code_commit", "run_manifest_sha256", "rank", "world_size", "callback", "order"),
               "rank capture")
        require(shard["schema"] == CAPTURE_SCHEMA and shard["code_commit"] == CODE_COMMIT,
                "wrong source callback revision")
        require(shard["run_manifest_sha256"] == run_manifest_sha256, "mixed or unexpected inference run")
        size, rank = shard["world_size"], shard["rank"]
        require(type(size) is int and size > 0 and type(rank) is int and 0 <= rank < size,
                "invalid rank identity")
        require(world_size is None or world_size == size, "inconsistent world size")
        world_size = size
        require(rank not in ranks, "duplicate rank capture")
        ranks.add(rank)
        callback, order = shard["callback"], shard["order"]
        require(type(callback) is dict and type(order) is dict and set(callback) == set(order),
                "callback and observed order sentence coverage differ")
        for uid, entry in callback.items():
            require(uid in expected, "capture contains a sentence outside the frozen test panel")
            require(uid not in seen, "sentence captured on multiple ranks")
            seen.add(uid)
            row = expected[uid]
            fields(entry, ("true", "pred", "typed", "logits"), "source callback sentence")
            require(type(entry["true"]) is str and entry["true"] == row["reference_text"],
                    "callback presented sentence differs from frozen reference")
            strokes = order[uid]
            require(type(strokes) is list and all(type(s) is str for s in strokes), "invalid observed button order")
            require(len(set(strokes)) == len(strokes), "repeated keystroke observation; source sampler padding is not scoreable")
            require(strokes == row["keystroke_ids"], "observed keystroke order differs from frozen assessment")
            require(all(type(entry[k]) is list and len(entry[k]) == len(strokes)
                        for k in ("pred", "typed", "logits")), "callback per-keystroke lengths disagree")
            for predicted, typed, logits in zip(entry["pred"], entry["typed"], entry["logits"]):
                class_id(typed)
                require(class_id(predicted) == first_argmax(logits), "callback prediction differs from neural first argmax")
            submissions[row["case_id"]] = {"case_id": row["case_id"], "keystroke_ids": strokes,
                                           "class_ids": entry["pred"]}
            total_strokes += len(strokes)
    # Compare counts plus bounds, not range(world_size): an invalid huge world
    # declaration must not allocate a correspondingly huge set.
    require(len(ranks) == world_size, "missing distributed rank capture")
    require(seen == set(expected), "capture omits frozen test sentences")
    submission = {"schema": E.SUBMISSION_SCHEMA, "task_id": E.TASK_ID, "metric_route": E.METRIC_ROUTE,
                  "representation": "per-keystroke-classes",
                  "predictions": [submissions[row["case_id"]] for row in test]}
    E.validate_submission(submission, contract, limits)
    receipt = {"schema": "typing-v1-author-bridge-receipt-v1", "panel_sha256": panel_sha256,
               "capture_sha256": capture_sha256, "run_manifest_sha256": run_manifest_sha256,
               "evaluator_sha256": EVALUATOR_SHA256, "source_contract_sha256": E.CONTRACT_SHA256,
               "rank_count": len(ranks), "sentence_count": len(test), "keystroke_count": total_strokes,
               "modality": panel["modality"], "qualification": "software_conversion_only"}
    return submission, receipt


def source_padding_audit(ordered_sentence_sizes, world_size):
    """Exact unshuffled source sampler counts, without constructing raw samples.

    Input order must be the actual dataset's first-seen sentence order. This is a
    schedule diagnostic, not recovery of source split membership or inference.
    """
    require(type(world_size) is int and world_size > 0, "invalid world size")
    require(type(ordered_sentence_sizes) is list and
            all(type(n) is int and n > 0 for n in ordered_sentence_sizes), "invalid sentence sizes")
    # Sparse ranks keep impossible declarations from forcing huge allocation.
    counts = {}
    for i, size in enumerate(ordered_sentence_sizes):
        rank = i % world_size
        counts[rank] = counts.get(rank, 0) + size
    longest = max(counts.values(), default=0)
    rows = [{"rank": rank, "unique_keystrokes": count, "repeated_padding_keystrokes": longest - count,
             "yielded_keystrokes": longest} for rank, count in sorted(counts.items())]
    return {"source_nonempty_rank_counts": rows, "empty_rank_count": world_size - len(counts),
            "source_reported_length_per_rank": longest,
            "unique_keystrokes": sum(ordered_sentence_sizes),
            "repeated_padding_keystrokes": sum(longest - n for n in counts.values()),
            "rank_zero_missing_sentences": len(ordered_sentence_sizes) - len(ordered_sentence_sizes[::world_size])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("panel", "panel-sha256", "capture", "capture-sha256", "run-manifest-sha256", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--max-json-bytes", type=int, required=True)
    parser.add_argument("--max-codepoints", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        limits = E.Limits(max_json_bytes=args.max_json_bytes, max_codepoints=args.max_codepoints, max_edit_cells=1)
        submission, receipt = convert_bytes(E.read_bounded(args.panel, limits.max_json_bytes), args.panel_sha256,
            E.read_bounded(args.capture, limits.max_json_bytes), args.capture_sha256, args.run_manifest_sha256, limits)
        body = (json.dumps(submission, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")
        require(len(body) <= limits.max_json_bytes, "converted submission exceeds JSON byte budget")
        with open(args.output, "xb") as stream:
            stream.write(body)
        print(json.dumps(receipt, allow_nan=False))
        return 0
    except (E.PanelError, E.CandidateError, E.ResourceLimit, OSError) as exc:
        reason = str(exc) if not isinstance(exc, OSError) else "operator file access failed"
        print(json.dumps({"status": "not_converted", "reason": reason}))
        return 3


if __name__ == "__main__":
    sys.exit(main())
