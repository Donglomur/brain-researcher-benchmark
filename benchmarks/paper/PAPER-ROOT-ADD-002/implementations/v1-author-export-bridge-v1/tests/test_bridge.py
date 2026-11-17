"""Generated author-export controls; no recordings, weights or native imports."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tested_author_bridge", PACKAGE / "bridge.py")
B = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(B)
RUN = "a" * 64


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def limits(**changes):
    values = dict(max_json_bytes=1000000, max_codepoints=100000, max_edit_cells=100000)
    values.update(changes)
    return B.E.Limits(**values)


class Tensor:
    def __init__(self, data):
        self.data = data

    def tolist(self):
        return copy.deepcopy(self.data)


def fixture():
    contract = B.E.source_contract()
    panel = {"schema": B.E.PANEL_SCHEMA, "task_id": B.E.TASK_ID, "metric_route": B.E.METRIC_ROUTE,
        "source": {k: contract[k] for k in ("code_commit", "data_revision")}, "modality": "MEG",
        "condition": {"id": "generated-source-export-control", "access_condition": "paper_data_official_code",
            "split_kind": "pinned-source-sentence-clusters", "disjoint_units": ["sentence_cluster"],
            "calibration_sentence_limit_per_person": 0, "representation": "per-keystroke-classes"},
        "provenance": {"panel_id": "generated-three-case-control", "eligibility_manifest_sha256": "1"*64,
            "preprocessing_manifest_sha256": "2"*64, "grouping_manifest_sha256": "3"*64,
            "training_or_checkpoint_manifest_sha256": "4"*64},
        "aliases": [], "recordings": [], "cases": []}
    ranks = [B.RankCapture(rank=i, world_size=2, run_manifest_sha256=RUN) for i in range(2)]
    for i, (participant, person, text, classes) in enumerate([
            ("S1", "S1", "ss", [0, 0]), ("S18", "S1", "oo", [1, 0]), ("S5", "S5", "ss", [1, 1])]):
        path = next(p for p, meta in contract["recording_identities"].items()
                    if meta["primary_case_eligible"] and meta["participant_id"] == participant)
        meta = contract["recording_identities"][path]
        source = next(row for row in contract["source_records"] if row["path"] == path)
        uid = f"2.0_{meta['study']}_subject-{participant}_session-{meta['session_id']}_task-{meta['task']}"
        strokes = [uid + "_button_1", uid + "_button_2"]
        panel["aliases"].append({"participant_id": participant, "person_id": person})
        panel["recordings"].append({"path": path, "bytes": source["bytes"], "sha256": "5"*64})
        panel["cases"].append({"case_id": "case-" + str(i), "participant_id": participant,
            "session_id": meta["session_id"], "sentence_uid": uid, "sentence_cluster_id": "cluster-" + text,
            "trial_id": 2, "split": "test", "source_path": path, "reference_text": text, "keystroke_ids": strokes})
        logits = [[3 if j == predicted else -2 for j in range(29)] for predicted in classes]
        batch = SimpleNamespace(segments=[SimpleNamespace(trigger=SimpleNamespace(
            extra={"sentence_UID": uid, "button_UID": stroke}, sentence=text)) for stroke in strokes])
        ranks[i % 2].add_batch((Tensor(logits), Tensor([28, 28])), batch)
    return panel, B.bundle_documents([rank.document() for rank in ranks])


def convert(panel, bundle, **kwargs):
    p, c = encode(panel), encode(bundle)
    return B.convert_bytes(p, digest(p), c, digest(c), RUN, kwargs.get("configured_limits", limits()))


class BridgeControls(unittest.TestCase):
    def test_real_evaluator_path_preserves_macro_cer_aliases_and_typed_distinction(self):
        panel, bundle = fixture()
        bundle["shards"].reverse()
        submission, receipt = convert(panel, bundle)
        p = encode(panel)
        result = B.E.evaluate_bytes(p, digest(p), encode(submission), limits())
        # Independent arithmetic: S1=(0 + 1/2)/2=1/4; S5=1; macro=5/8.
        self.assertEqual(result["summary"]["cer"], 5/8)
        self.assertEqual(result["summary"]["wer"], 3/4)
        self.assertEqual(receipt["sentence_count"], 3)
        self.assertEqual(receipt["keystroke_count"], 6)
        self.assertEqual([r["case_id"] for r in submission["predictions"]], ["case-0", "case-1", "case-2"])
        self.assertNotIn("true", encode(submission).decode())
        self.assertNotIn("typed", encode(submission).decode())
        self.assertEqual(receipt["qualification"], "software_conversion_only")

    def test_rank_zero_only_and_distributed_duplicates_refused(self):
        panel, bundle = fixture()
        missing = copy.deepcopy(bundle); missing["shards"].pop()
        with self.assertRaisesRegex(B.CaptureError, "missing distributed rank"):
            convert(panel, missing)
        duplicate = copy.deepcopy(bundle)
        duplicate["shards"].append(copy.deepcopy(duplicate["shards"][0]))
        with self.assertRaisesRegex(B.CaptureError, "duplicate rank"):
            convert(panel, duplicate)
        duplicate = copy.deepcopy(bundle)
        uid, entry = next(iter(duplicate["shards"][0]["callback"].items()))
        duplicate["shards"][1]["callback"][uid] = entry
        duplicate["shards"][1]["order"][uid] = duplicate["shards"][0]["order"][uid]
        with self.assertRaisesRegex(B.CaptureError, "multiple ranks"):
            convert(panel, duplicate)

    def test_padding_is_preserved_and_never_silently_deduplicated(self):
        panel, bundle = fixture()
        shard = bundle["shards"][0]; uid = next(iter(shard["callback"]))
        for key in ("pred", "typed", "logits"):
            shard["callback"][uid][key].append(copy.deepcopy(shard["callback"][uid][key][0]))
        shard["order"][uid].append(shard["order"][uid][0])
        with self.assertRaisesRegex(B.CaptureError, "repeated keystroke"):
            convert(panel, bundle)

    def test_count_equal_permutation_and_reference_substitution_refused(self):
        panel, bundle = fixture(); uid = next(iter(bundle["shards"][0]["callback"]))
        changed = copy.deepcopy(bundle); changed["shards"][0]["order"][uid].reverse()
        with self.assertRaisesRegex(B.CaptureError, "order differs"):
            convert(panel, changed)
        changed = copy.deepcopy(bundle); changed["shards"][0]["callback"][uid]["true"] = "private marker"
        with self.assertRaises(B.CaptureError) as error:
            convert(panel, changed)
        self.assertNotIn("private marker", str(error.exception))
        changed = copy.deepcopy(bundle)
        del changed["shards"][0]["callback"][uid]; del changed["shards"][0]["order"][uid]
        with self.assertRaisesRegex(B.CaptureError, "omits frozen"):
            convert(panel, changed)

    def test_finite_logits_source_first_tie_and_class_domains(self):
        self.assertEqual(B.first_argmax([2] * 29), 0)
        for value in (float("nan"), float("inf"), True, "2", None):
            with self.subTest(value=value), self.assertRaises(B.CaptureError):
                B.first_argmax([value] + [0] * 28)
        panel, bundle = fixture(); uid = next(iter(bundle["shards"][0]["callback"]))
        for value in (True, -1, 29, 1.0, "1"):
            changed = copy.deepcopy(bundle); changed["shards"][0]["callback"][uid]["typed"][0] = value
            with self.subTest(value=value), self.assertRaises(B.CaptureError):
                convert(panel, changed)
        bundle["shards"][0]["callback"][uid]["pred"][0] = 1
        with self.assertRaisesRegex(B.CaptureError, "first argmax"):
            convert(panel, bundle)

    def test_batch_truncation_and_conflicting_text_do_not_partially_mutate(self):
        capture = B.RankCapture(rank=0, world_size=1, run_manifest_sha256=RUN)
        segments = [SimpleNamespace(trigger=SimpleNamespace(extra={"sentence_UID": "uid", "button_UID": "button"}, sentence="x"))]
        with self.assertRaisesRegex(B.CaptureError, "length mismatch"):
            capture.add_batch((Tensor([[0] * 29]), Tensor([])), SimpleNamespace(segments=segments))
        self.assertEqual(capture.callback, {})
        other = copy.deepcopy(segments[0]); other.trigger.sentence = "y"
        with self.assertRaisesRegex(B.CaptureError, "inconsistent presented"):
            capture.add_batch((Tensor([[0] * 29] * 2), Tensor([0, 0])), SimpleNamespace(segments=segments+[other]))
        self.assertEqual(capture.callback, {})

    def test_source_schedule_padding_arithmetic_and_empty_ranks(self):
        # Round robin: rank 0 sizes 2+5=7; rank 1 size 3, padded by 4.
        audit = B.source_padding_audit([2, 3, 5], 2)
        self.assertEqual(audit["unique_keystrokes"], 10)
        self.assertEqual(audit["repeated_padding_keystrokes"], 4)
        self.assertEqual(audit["rank_zero_missing_sentences"], 1)
        sparse = B.source_padding_audit([2], 10**20)
        self.assertEqual(sparse["empty_rank_count"], 10**20-1)
        self.assertEqual(sparse["source_nonempty_rank_counts"][0]["yielded_keystrokes"], 2)

    def test_wrong_run_digest_duplicate_json_keys_and_byte_budget_refused(self):
        panel, bundle = fixture(); p, c = encode(panel), encode(bundle)
        with self.assertRaisesRegex(B.CaptureError, "mixed or unexpected"):
            B.convert_bytes(p, digest(p), c, digest(c), "b"*64, limits())
        with self.assertRaisesRegex(B.CaptureError, "capture digest"):
            B.convert_bytes(p, digest(p), c, "b"*64, RUN, limits())
        malformed = b'{"schema":"one","schema":"two","shards":[]}'
        with self.assertRaisesRegex(B.CaptureError, "duplicate JSON"):
            B.convert_bytes(p, digest(p), malformed, digest(malformed), RUN, limits())
        with self.assertRaises(B.E.ResourceLimit):
            convert(panel, bundle, configured_limits=limits(max_json_bytes=10))

    def test_cli_creates_usable_submission_and_never_overwrites(self):
        panel, bundle = fixture(); p, c = encode(panel), encode(bundle)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/"panel").write_bytes(p); (root/"capture").write_bytes(c)
            cmd = [sys.executable, "-I", "-S", "-B", str(PACKAGE/"bridge.py"), "--panel", str(root/"panel"),
                "--panel-sha256", digest(p), "--capture", str(root/"capture"), "--capture-sha256", digest(c),
                "--run-manifest-sha256", RUN, "--output", str(root/"predictions"),
                "--max-json-bytes", "1000000", "--max-codepoints", "100000"]
            result = subprocess.run(cmd, text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["rank_count"], 2)
            predicted = (root/"predictions").read_bytes()
            self.assertEqual(B.E.evaluate_bytes(p, digest(p), predicted, limits())["summary"]["cer"], 5/8)
            repeat = subprocess.run(cmd, text=True, capture_output=True, timeout=10)
            self.assertEqual(repeat.returncode, 3)
            self.assertNotIn(tmp, repeat.stdout + repeat.stderr)
            self.assertEqual((root/"predictions").read_bytes(), predicted)


if __name__ == "__main__":
    unittest.main()
