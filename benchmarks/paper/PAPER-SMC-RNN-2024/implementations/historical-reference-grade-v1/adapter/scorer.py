#!/usr/bin/env python3
"""Freeze predictions without targets, then score in a separate operator process.

The boundary is an operator workflow, not a hostile-code sandbox. Run candidate
code in a separate environment which cannot access the evaluator's target file.
Original test targets are public (January 2026); this is not an untouched test.
Only aggregate scores and provenance are emitted. No source data is bundled.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import tempfile

import h5py
import numpy as np


DATASET = "mc_maze_20"
SCORER_SHA256 = "05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476"
TARGET_SOURCE_COMMIT = "42f8410b88e12db136910fa2f888b025ea0aa2ae"
TARGET_SHA256 = "f2f434d30193251b58e6a693381fdd185c8fbc0e47d38f8810e65295bc42c865"
AUTHOR_COMMIT = "c808c76ad940491b0a14d2671e3884140aa61258"
METRICS = ("co-bps", "vel R2", "psth R2", "fp-bps")
PUBLISHED = {
    "causal": dict(zip(METRICS, (0.3225, 0.8479, 0.5927, 0.2184))),
    "noncausal": dict(zip(METRICS, (0.3407, 0.8902, 0.5963, 0.2417))),
}
RATE_KEYS = tuple(
    f"{split}_rates_{units}{suffix}"
    for split in ("train", "eval")
    for suffix in ("", "_forward")
    for units in ("heldin", "heldout")
)
OPTIONAL_KEYS = {"train_rates_heldin_forward", "train_rates_heldout_forward"}
REQUIRED_KEYS = set(RATE_KEYS) - OPTIONAL_KEYS
REFERENCE_PANEL = Path(__file__).with_name("reference_panel.json")
PANEL_IDENTITY_FIELDS = (
    "schema", "dataset", "phase", "source_commit", "dandiset", "dandi_version", "bin_ms",
    "n_train", "n_eval", "n_bins", "forward_bins", "n_heldin", "n_heldout", "condition_count",
    "trial_indices_sha256", "neuron_indices_sha256", "conditions_sha256", "split_counts",
    "tensor_trial_indices_sha256", "condition_membership_sha256",
    "expected_shapes", "nwb_sources", "input_content_sha256",
)


class ContractError(ValueError):
    """A file fails the complete original-panel evaluation contract."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def valid_digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def read_json(path):
    def pairs(rows):
        obj = {}
        for key, value in rows:
            require(key not in obj, "duplicate JSON key")
            obj[key] = value
        return obj

    return json.loads(Path(path).read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ContractError("nonfinite JSON")))


def write_new_json(path, value):
    # Never silently replace an existing freeze or result record.
    with Path(path).open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def validate_panel(manifest):
    require(REFERENCE_PANEL.is_file(), "authentic reference panel has not been qualified")
    reference = read_json(REFERENCE_PANEL)
    for field in PANEL_IDENTITY_FIELDS:
        require(field in reference and field in manifest and manifest[field] == reference[field],
                "panel does not match the complete source reference: " + field)
    require(manifest.get("schema") == "smc_nlb_panel_v1", "unsupported panel manifest")
    require(manifest.get("dataset") == DATASET and manifest.get("phase") == "test",
            "only the original MC_Maze20ms test panel is supported")
    for field, expected in (("n_bins", 35), ("forward_bins", 10), ("n_heldin", 137),
                            ("n_heldout", 45), ("condition_count", 108)):
        require(manifest.get(field) == expected, "incorrect original-panel " + field)
    for field in ("n_train", "n_eval", "n_bins"):
        require(type(manifest.get(field)) is int and manifest[field] > 0,
                "missing or invalid panel dimension " + field)
    for field in ("trial_indices_sha256", "neuron_indices_sha256", "conditions_sha256",
                  "tensor_trial_indices_sha256", "condition_membership_sha256"):
        require(valid_digest(manifest.get(field)), "missing panel provenance " + field)
    inputs = manifest.get("inputs_sha256")
    require(isinstance(inputs, dict) and bool(inputs) and all(valid_digest(x) for x in inputs.values()),
            "missing input content hashes")
    content = manifest.get("input_content_sha256")
    require(isinstance(content, dict) and bool(content) and all(valid_digest(x) for x in content.values()),
            "missing serialization-independent input content hashes")
    expected = {}
    for key in RATE_KEYS:
        expected[key] = [manifest["n_train"] if key.startswith("train_") else manifest["n_eval"],
                         manifest["forward_bins"] if key.endswith("_forward") else manifest["n_bins"],
                         manifest["n_heldin"] if "heldin" in key else manifest["n_heldout"]]
    require(manifest.get("expected_shapes") == expected, "expected_shapes does not match full panel")
    return expected


def plain_hdf5_link(group, name):
    require(isinstance(group.get(name, getlink=True), h5py.HardLink),
            "external or soft HDF5 links are forbidden")


def validate_submission(path, manifest, *, require_author_arrays=False):
    """Check full coverage without loading any target or emitting predictions."""
    expected = validate_panel(manifest)
    with h5py.File(path, "r") as handle:
        require(set(handle) == {DATASET}, "submission must contain exactly mc_maze_20")
        plain_hdf5_link(handle, DATASET)
        group = handle[DATASET]
        require(isinstance(group, h5py.Group), "dataset group is missing")
        require(set(group) == set(RATE_KEYS) or
                (not require_author_arrays and set(group) == REQUIRED_KEYS),
                "missing or extra rate arrays")
        for name, shape in expected.items():
            if name not in group:
                continue
            plain_hdf5_link(group, name)
            item = group[name]
            require(isinstance(item, h5py.Dataset), "rate entry must be a dataset")
            require(not item.is_virtual and not item.external, "indirect HDF5 data is forbidden")
            require(list(item.shape) == shape, "incomplete or misaligned array " + name)
            require(item.dtype.kind in "fiu", "rate arrays must be numeric")
            for first in range(0, shape[0], 32):
                block = item[first:first + 32]
                require(bool(np.isfinite(block).all()) and bool((block >= 0).all()),
                        "rate arrays must be finite and nonnegative")
    return expected


def freeze_predictions(submission, manifest_path, protocol_path, destination, *, arm,
                       method_id, role, seed, particles=None, repeats=None):
    """Target-blind candidate interface; no target path is accepted here."""
    require(arm in PUBLISHED, "arm must be causal or noncausal")
    require(role in ("author_calibration", "candidate"), "invalid prediction role")
    require(isinstance(method_id, str) and 0 < len(method_id) <= 200, "invalid method ID")
    require(type(seed) is int and seed >= 0, "seed must be a nonnegative integer")
    if role == "author_calibration":
        require(particles == 192 and repeats == 32, "author calibration requires 192 particles and 32 repeats")
    manifest = read_json(manifest_path)
    validate_submission(submission, manifest, require_author_arrays=role == "author_calibration")
    record = {
        "schema": "smc_nlb_prediction_freeze_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "submission_sha256": sha256(submission),
        "panel_manifest_sha256": sha256(manifest_path),
        "reference_panel_sha256": sha256(REFERENCE_PANEL),
        "protocol_sha256": sha256(protocol_path),
        "arm": arm, "method_id": method_id, "role": role, "seed": seed,
        "particles": particles, "repeats": repeats,
        "dataset": DATASET,
        "target_exposure": "public_original_test_targets_released_2026_01",
        "source_author_commit": AUTHOR_COMMIT if role == "author_calibration" else None,
    }
    write_new_json(destination, record)
    return record


def validate_freeze(submission, manifest_path, protocol_path, freeze_path):
    record = read_json(freeze_path)
    require(record.get("schema") == "smc_nlb_prediction_freeze_v1", "unsupported prediction freeze")
    require(record.get("dataset") == DATASET and record.get("arm") in PUBLISHED, "invalid frozen arm or dataset")
    require(record.get("role") in ("author_calibration", "candidate"), "invalid frozen role")
    if record["role"] == "author_calibration":
        require(record.get("particles") == 192 and record.get("repeats") == 32
                and record.get("source_author_commit") == AUTHOR_COMMIT,
                "incorrect frozen author inference recipe")
    for field, path in (("submission_sha256", submission), ("panel_manifest_sha256", manifest_path),
                        ("protocol_sha256", protocol_path), ("reference_panel_sha256", REFERENCE_PANEL)):
        require(record.get(field) == sha256(path), "frozen content changed: " + field)
    validate_submission(submission, read_json(manifest_path),
                        require_author_arrays=record["role"] == "author_calibration")
    return record


def load_original_scorer(source_path):
    source_path = Path(source_path)
    if source_path.is_dir():
        source_path = source_path / "nlb_tools" / "evaluation.py"
    require(sha256(source_path) == SCORER_SHA256,
            "scorer is not the byte-verified nlb_tools0.0.3 / target-release scorer")
    spec = importlib.util.spec_from_file_location("_smc_verified_nlb_evaluation", source_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def score_predictions(submission, manifest_path, protocol_path, freeze_path, target,
                      target_sha256, scorer_source, destination):
    """Operator-only action. Verify frozen bytes before the first target read."""
    require(target_sha256 == TARGET_SHA256,
            "target SHA256 must match the pinned January 2026 original-test release")
    record = validate_freeze(submission, manifest_path, protocol_path, freeze_path)
    require(Path(target).resolve() != Path(submission).resolve(), "target and submission must differ")
    require(Path(target).resolve().parent != Path(submission).resolve().parent,
            "operator targets must be stored separately from prediction submissions")
    scorer = load_original_scorer(scorer_source)
    with tempfile.TemporaryDirectory(prefix="smc-operator-score-") as temporary:
        snapshot = Path(temporary) / "submission.h5"
        shutil.copyfile(submission, snapshot)
        require(sha256(snapshot) == record["submission_sha256"], "submission changed during operator snapshot")
        # No access to the operator target occurs above this line.
        require(sha256(target) == target_sha256, "operator target does not match source SHA256")
        result = scorer.evaluate(str(target), str(snapshot))
    require(isinstance(result, list) and len(result) == 1
            and set(result[0]) == {DATASET + "_split"}, "scorer did not return the complete selected panel")
    metrics = result[0][DATASET + "_split"]
    require(set(metrics) == set(METRICS), "one or more original companion metrics are missing")
    metrics = {key: float(metrics[key]) for key in METRICS}
    require(all(math.isfinite(value) for value in metrics.values()), "nonfinite aggregate metric")
    anchor = PUBLISHED[record["arm"]]
    versions = {}
    for name in ("numpy", "scipy", "scikit-learn", "h5py"):
        versions[name] = importlib.metadata.version(name)
    report = {
        "schema": "smc_nlb_operator_score_v1", "dataset": DATASET,
        "arm": record["arm"], "role": record["role"], "method_id": record["method_id"],
        "metrics": metrics, "published_anchor": anchor,
        "difference_from_published": {key: metrics[key] - anchor[key] for key in METRICS},
        "prediction_freeze_sha256": sha256(freeze_path),
        "submission_sha256": record["submission_sha256"],
        "panel_manifest_sha256": record["panel_manifest_sha256"],
        "reference_panel_sha256": record["reference_panel_sha256"],
        "protocol_sha256": record["protocol_sha256"],
        "scorer_sha256": SCORER_SHA256, "target_sha256": target_sha256,
        "target_source_commit": TARGET_SOURCE_COMMIT,
        "target_exposure": "public_original_test_targets_released_2026_01",
        "dependency_versions": versions,
        "interpretation": "Aggregate source comparison only; reproduction is calibration. "
                          "No uncertainty, improvement, causal online, or current-SOTA claim is decided here.",
    }
    write_new_json(destination, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("freeze", "score"):
        command = sub.add_parser(action)
        for arg in ("submission", "manifest", "protocol", "output"):
            command.add_argument("--" + arg, type=Path, required=True)
        if action == "freeze":
            command.add_argument("--arm", choices=list(PUBLISHED), required=True)
            command.add_argument("--method-id", required=True)
            command.add_argument("--role", choices=("author_calibration", "candidate"), required=True)
            command.add_argument("--seed", type=int, required=True)
            command.add_argument("--particles", type=int)
            command.add_argument("--repeats", type=int)
        else:
            command.add_argument("--freeze", type=Path, required=True)
            command.add_argument("--target", type=Path, required=True)
            command.add_argument("--target-sha256", required=True)
            command.add_argument("--scorer-source", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.action == "freeze":
        result = freeze_predictions(args.submission, args.manifest, args.protocol, args.output,
                                    arm=args.arm, method_id=args.method_id, role=args.role, seed=args.seed,
                                    particles=args.particles, repeats=args.repeats)
    else:
        result = score_predictions(args.submission, args.manifest, args.protocol, args.freeze,
                                   args.target, args.target_sha256, args.scorer_source, args.output)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
