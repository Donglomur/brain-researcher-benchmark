#!/usr/bin/env python3
"""Check the complete original eight-condition interface; delegate all metrics.

This operator workflow is not participant isolation or scientific qualification.
Unknown authentic case/unit identities cannot be established by valid shapes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import numbers
from pathlib import Path
import stat
import tempfile
import types

SCORER_SHA256 = "05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476"
TARGET_SHA256 = "f2f434d30193251b58e6a693381fdd185c8fbc0e47d38f8810e65295bc42c865"
TARGET_BYTES = 105927616
NLB_COMMIT = "42f8410b88e12db136910fa2f888b025ea0aa2ae"
AUTHOR_COMMIT = "68dcbfaa78b2371851842333ae933eea1f961832"
RATE_KEYS = ("train_rates_heldin", "train_rates_heldout", "eval_rates_heldin",
             "eval_rates_heldout", "eval_rates_heldin_forward", "eval_rates_heldout_forward")
GROUPS = tuple(name + suffix for name in ("mc_maze", "mc_rtt", "area2_bump", "dmfc_rsg")
               for suffix in ("", "_20"))
OBSERVED_MS = {"mc_maze": 700, "mc_rtt": 600, "area2_bump": 600, "dmfc_rsg": 1500}


class ContractError(ValueError):
    """The declared original-panel structure or frozen content is incomplete."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def spec(group):
    dataset = group.removesuffix("_20")
    bin_ms = 20 if group.endswith("_20") else 5
    metrics = ["co-bps", "tp corr" if dataset == "dmfc_rsg" else "vel R2"]
    if dataset != "mc_rtt":
        metrics.append("psth R2")
    return dataset, bin_ms, OBSERVED_MS[dataset] // bin_ms, 200 // bin_ms, (*metrics, "fp-bps")


def _item(group, name):
    require(name in group, "missing field: " + name)
    if not isinstance(group, dict):
        import h5py
        require(isinstance(group, h5py.Group), "expected a mapping or HDF5 group")
        require(isinstance(group.get(name, getlink=True), h5py.HardLink), "indirect HDF5 link")
        item = group[name]
        if isinstance(item, h5py.Dataset):
            require(not item.is_virtual and not item.external, "indirect HDF5 storage")
        return item
    return group[name]


def _shape(group, name, ndim, *, kinds="fiu"):
    item = _item(group, name)
    shape = getattr(item, "shape", None)
    dtype = getattr(item, "dtype", None)
    require(shape is not None and len(shape) == ndim and all(int(n) > 0 for n in shape),
            "invalid dimensions: " + name)
    require(getattr(dtype, "kind", None) in kinds, "invalid array type: " + name)
    return tuple(int(n) for n in shape)


def validate_submission(data):
    """Target-blind shape coverage, without filtering or reading array values."""
    require(set(data.keys()) == set(GROUPS), "submission must contain exactly the eight selected groups")
    shapes = {}
    for group in GROUPS:
        values = _item(data, group)
        require(hasattr(values, "keys") and set(values.keys()) == set(RATE_KEYS),
                "each submission group must contain the six original rate fields")
        _, _, observed, forward, _ = spec(group)
        arrays = {name: _shape(values, name, 3) for name in RATE_KEYS}
        ntrain, _, heldin = arrays["train_rates_heldin"]
        neval, _, _ = arrays["eval_rates_heldin"]
        heldout = arrays["train_rates_heldout"][2]
        expected = {
            "train_rates_heldin": (ntrain, observed, heldin),
            "train_rates_heldout": (ntrain, observed, heldout),
            "eval_rates_heldin": (neval, observed, heldin),
            "eval_rates_heldout": (neval, observed, heldout),
            "eval_rates_heldin_forward": (neval, forward, heldin),
            "eval_rates_heldout_forward": (neval, forward, heldout),
        }
        require(arrays == expected, "inconsistent source time/unit/trial axes: " + group)
        shapes[group] = {name: list(shape) for name, shape in arrays.items()}
    return shapes


def validate_targets(targets, shapes):
    """Bind submitted axes to supplied targets; preserve all values and masks.

The authentic target hash is checked by score(), outside this structural helper.
Additional official target groups are permitted and remain untouched.
"""
    require(set(GROUPS).issubset(targets.keys()), "target is missing a selected condition")
    for group in GROUPS:
        values = _item(targets, group)
        require(hasattr(values, "keys"), "target condition must be a group")
        dataset, _, observed, _, _ = spec(group)
        expected = shapes[group]
        for key in ("eval_rates_heldout", "eval_rates_heldin_forward", "eval_rates_heldout_forward"):
            require(list(_shape(values, key.replace("rates", "spikes"), 3)) == expected[key],
                    "target/submission spike axes differ: " + group + "/" + key)
        ntrain = expected["train_rates_heldin"][0]
        neval = expected["eval_rates_heldin"][0]
        for split, count in (("train", ntrain), ("eval", neval)):
            wanted = (count, 5) if dataset == "dmfc_rsg" else (count, observed, 2)
            require(_shape(values, split + "_behavior", len(wanted)) == wanted,
                    "target/submission behavior axes differ: " + group + "/" + split)
        mask_names = {"train_decode_mask", "eval_decode_mask"}
        present = mask_names.intersection(values.keys())
        require(not present or present == mask_names, "incomplete decoder mask pair")
        if dataset == "area2_bump":
            require(present == mask_names, "original Area2 active/passive masks are required")
        if present:
            train_mask = _shape(values, "train_decode_mask", 2, kinds="b")
            eval_mask = _shape(values, "eval_decode_mask", 2, kinds="b")
            require(train_mask[0] == ntrain and eval_mask == (neval, train_mask[1]),
                    "decoder masks differ from original trial axes")
            if dataset == "area2_bump":
                require(train_mask[1] == 2, "Area2 requires both original decoder masks")
        if dataset != "mc_rtt":
            psth = _shape(values, "psth", 3)
            units = expected["eval_rates_heldin"][2] + expected["eval_rates_heldout"][2]
            require(psth[1:] == (observed, units), "PSTH time/unit axes differ")
            require(_shape(values, "eval_cond_idx", 1, kinds="Oiu")[0] == psth[0],
                    "PSTH condition index count differs")
        else:
            require("psth" not in values, "MC_RTT PSTH is inapplicable in the selected original panel")
        if "eval_jitter" in values:
            require(_shape(values, "eval_jitter", 1) == (neval,), "jitter trial axis differs")


def validate_results(results):
    require(isinstance(results, list) and len(results) == len(GROUPS), "expected eight result groups")
    seen = set()
    for row in results:
        require(isinstance(row, dict) and len(row) == 1, "result entry must have one group")
        key, metrics = next(iter(row.items()))
        require(isinstance(key, str) and key.endswith("_split"), "invalid result group")
        group = key.removesuffix("_split")
        require(group in GROUPS and group not in seen, "unknown or duplicated result group")
        require(isinstance(metrics, dict) and set(metrics) == set(spec(group)[4]),
                "missing or extra original companion metric: " + group)
        require(all(not isinstance(v, bool) and isinstance(v, numbers.Real) and math.isfinite(v)
                    for v in metrics.values()), "nonfinite or nonnumeric aggregate result")
        seen.add(group)
    require(sum(len(row[next(iter(row))]) for row in results) == 30, "expected thirty applicable metric cells")
    return results


def sha256(path, maximum):
    require(type(maximum) is int and maximum > 0, "a positive explicit file budget is required")
    path = Path(path)
    require(stat.S_ISREG(path.lstat().st_mode), "expected a regular file")
    require(path.stat().st_size <= maximum, "file exceeds the explicit byte budget")
    digest, count = hashlib.sha256(), 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(min(1024 * 1024, maximum + 1)), b""):
            count += len(block)
            require(count <= maximum, "file grew beyond the explicit byte budget")
            digest.update(block)
    return digest.hexdigest()


def _read_json(path):
    require(Path(path).stat().st_size <= 131072, "freeze record is too large")
    def pairs(rows):
        value = {}
        for key, item in rows:
            require(key not in value, "duplicate JSON key")
            value[key] = item
        return value
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ContractError("nonfinite JSON")))


def _write_new(path, value):
    with Path(path).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def freeze(submission, destination, *, max_submission_bytes):
    import h5py
    before = sha256(submission, max_submission_bytes)
    with h5py.File(submission, "r") as data:
        shapes = validate_submission(data)
    require(sha256(submission, max_submission_bytes) == before, "submission changed during freeze")
    record = {"schema": "langevin_complete_nlb_freeze_v1", "scope": "source_structure_only",
              "created_utc": datetime.now(timezone.utc).isoformat(), "submission_sha256": before,
              "shapes": shapes, "scorer_sha256": SCORER_SHA256,
              "rate_units": "expected_spike_counts_per_bin", "authentic_case_coverage_qualified": False}
    _write_new(destination, record)
    return record


def load_original_scorer(path):
    path = Path(path)
    require(path.stat().st_size <= 131072, "unexpected evaluator source size")
    source = path.read_bytes()
    require(hashlib.sha256(source).hexdigest() == SCORER_SHA256, "official evaluator source hash mismatch")
    module = types.ModuleType("_langevin_original_nlb_evaluation")
    module.__file__ = str(path)
    # Execute the exact authenticated bytes, without reopening a replaceable path.
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


def _snapshot(source, destination, maximum, expected_hash):
    count = 0
    with Path(source).open("rb") as src, Path(destination).open("xb") as dst:
        for block in iter(lambda: src.read(1024 * 1024), b""):
            count += len(block)
            require(count <= maximum, "snapshot exceeds explicit byte budget")
            dst.write(block)
    require(sha256(destination, maximum) == expected_hash, "submission changed before snapshot")
    return count


def score(submission, freeze_path, target, scorer_source, destination, *, max_submission_bytes):
    import h5py
    record = _read_json(freeze_path)
    require(isinstance(record, dict), "freeze record must be an object")
    require(record.get("schema") == "langevin_complete_nlb_freeze_v1"
            and record.get("scope") == "source_structure_only"
            and record.get("scorer_sha256") == SCORER_SHA256
            and record.get("authentic_case_coverage_qualified") is False
            and record.get("rate_units") == "expected_spike_counts_per_bin", "invalid source-structure freeze")
    require(sha256(submission, max_submission_bytes) == record.get("submission_sha256"),
            "submission changed after freeze")
    require(Path(submission).resolve() != Path(target).resolve(), "targets and submission must differ")
    with tempfile.TemporaryDirectory(prefix="langevin-panel-score-") as temporary:
        snapshot = Path(temporary) / "submission.h5"
        copied = _snapshot(submission, snapshot, max_submission_bytes, record["submission_sha256"])
        with h5py.File(snapshot, "r") as data:
            shapes = validate_submission(data)
            require(shapes == record.get("shapes"), "frozen submission shapes changed")
            # No target file is accessed before the frozen submission passes.
            require(sha256(target, TARGET_BYTES) == TARGET_SHA256, "original target file hash mismatch")
            scorer = load_original_scorer(scorer_source)
            with h5py.File(target, "r") as targets:
                validate_targets(targets, shapes)
                results = validate_results(scorer.evaluate(targets, data))
            require(sha256(target, TARGET_BYTES) == TARGET_SHA256, "target changed during scoring")
    report = {"schema": "langevin_complete_nlb_score_v1", "scope": "source_structure_and_target_axes_only",
              "results": [{key: {metric: float(value) for metric, value in metrics.items()}
                           for key, metrics in row.items()} for row in results],
              "submission_sha256": record["submission_sha256"], "target_sha256": TARGET_SHA256,
              "scorer_sha256": SCORER_SHA256, "nlb_source_commit": NLB_COMMIT,
              "snapshot_bytes": copied, "metric_cells": 30,
              "scientific_qualification": "unestablished", "authentic_case_coverage_qualified": False,
              "interpretation": "Original numerical evaluator output only. No reproduction agreement, improvement, aggregate ranking, or SOTA decision.",
              "dependency_versions": {name: importlib.metadata.version(name)
                                      for name in ("numpy", "scipy", "scikit-learn", "h5py")}}
    _write_new(destination, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("freeze", "score"):
        command = commands.add_parser(action)
        command.add_argument("--submission", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--max-submission-bytes", type=int, required=True)
        if action == "score":
            command.add_argument("--freeze", type=Path, required=True)
            command.add_argument("--target", type=Path, required=True)
            command.add_argument("--scorer-source", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.action == "freeze":
        result = freeze(args.submission, args.output, max_submission_bytes=args.max_submission_bytes)
    else:
        result = score(args.submission, args.freeze, args.target, args.scorer_source, args.output,
                       max_submission_bytes=args.max_submission_bytes)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
