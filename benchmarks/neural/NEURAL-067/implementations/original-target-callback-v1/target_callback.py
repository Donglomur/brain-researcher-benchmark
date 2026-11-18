"""Grader-only original NEURAL-067 targets for the unchanged session scorer.

No participant execution, fitting, metric implementation or target publication.
All private reads occur in the callback, after complete prediction admission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import types

SCORER_PIN = (11283, "91dbec46a088e807ebdbf243c478ea6f9e8a3ea0cb5f7747837673d499279b51")
BRIDGE_PIN = (6579, "f46895d79cf3646313749e7226a334d4a468dc67a8a60d62a02562da7dd09e33")
READER_PIN = (3576, "e72688ecd53c9dfd891b105b1e49b3d22871cc8b3ecb17339bd8a7f88672b890")
PRODUCER_PIN = (5759, "73aaa0453f7c31d4baddf2b32f5f276316716c28c4745ec0455e9213deba5edb")
# Whole-file pins only. Operator paths and individual target digest tables are private.
EVIDENCE_PINS = {
    "preparation": (36791, "805e767deea97c1d0255982911965f1fedcc78270acc81180ff58929ef67ac45"),
    "asset_manifest": (15297, "ccfc3b0c4f10509f617e7856af82964be6e60334d0194fd3309acd944db9663d"),
    "design": (6081, "73cdfd5d8760ad456251877d458a257af8f0100d5c73f95f965a0f9dda5b2028"),
    "private_bindings": (3821, "1cad6da2c49afed5f8e9658475af790f763f54d39a651c29062e7e9d6733fc38"),
    "attempt_receipt": (9683, "c05e05d0b2cb937565c312192311e6dd555792a0baac1ba0dc1d86cb40c9699a"),
    "operator_result": (22103, "57638f19935e1bb5e0963fe1126a8a15a34fa30e36684932564905748ea7f976"),
}
SOURCE_COMMIT = "770c9b9597b8f58bf67b5a9ec6401ef705a2cb0f"
UNITS = "source arbitrary position increments per20ms sample; no SI conversion"
MAX_TARGET_CAPTURE = 8_000_000
MAX_TARGET_EXPANDED = 40_000_000
MAX_PUBLIC_SUBMISSION = 64_000_000


def need(condition, message):
    if not condition:
        raise ValueError(message)


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def json_value(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, "duplicate JSON field")
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, "nonfinite JSON literal"))


def capture_source(path, cap):
    path = Path(path)
    need(all(not x.is_symlink() for x in (path, *path.parents)), 'No linked file or ancestor')
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0))
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= cap, 'Bounded ordinary file only')
        parts, n = [], 0
        while True:
            block = os.read(fd, min(1024**2, cap + 1 - n))
            if not block: break
            parts.append(block); n += len(block)
            need(n <= cap, 'Bounded capture')
        after = os.fstat(fd)
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
             == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
             and n == before.st_size, 'Stable complete file capture')
        return b''.join(parts)
    finally:
        os.close(fd)


def module(path, expected, name):
    """Compile the captured pinned source, never a later pathname read."""
    path = Path(path)
    raw = capture_source(path, expected[0])
    need((len(raw), hashlib.sha256(raw).hexdigest()) == expected, "exact source: " + name)
    result = types.ModuleType(name)
    result.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), result.__dict__)
    return result


def load_scorer(path=None):
    return module(path or Path(__file__).resolve().parent.parent / "session-evaluator-v1/scorer.py",
                  SCORER_PIN, "neural067_original_target_session_scorer")


def load_reader():
    return module(Path(__file__).resolve().with_name("guarded_npz.py"), READER_PIN,
                  "neural067_original_target_guarded_npz")


def descriptor(value):
    need(type(value) is dict and set(value) == {"bytes", "sha256"}, "exact descriptor fields")
    need(type(value["bytes"]) is int and 0 < value["bytes"] <= MAX_TARGET_CAPTURE,
         "bounded positive target extent")
    need(type(value["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", value["sha256"]),
         "lowercase target SHA256")
    return dict(value)


class _Targets:
    """Private lazy loader; only the public composition functions grant admission."""
    def __init__(self, prepared_root, evidence_paths, scorer, source_inputs=None):
        need(type(evidence_paths) is dict and
             set(evidence_paths) == set(EVIDENCE_PINS) - {"preparation"}, "exact evidence path roles")
        self.root = Path(prepared_root)
        self.paths = {k: Path(v) for k, v in evidence_paths.items()}
        self.paths["preparation"] = self.root / "PREPARATION.json"
        self.scorer = scorer
        self.source_inputs = source_inputs
        self.rows = None
        self.reader = None
        self.position = 0
        self.loaded = []

    def initialize(self):
        self.reader = load_reader()
        evidence = {}
        for role, expected in EVIDENCE_PINS.items():
            raw = self.reader.capture(self.paths[role], expected[0])
            need((len(raw), hashlib.sha256(raw).hexdigest()) == expected,
                 "exact original metadata: " + role)
            evidence[role] = json_value(raw)
        p, a, d, b, receipt, actual = (evidence[k] for k in
            ("preparation", "asset_manifest", "design", "private_bindings", "attempt_receipt", "operator_result"))
        need(p["schema"] == "falcon_h1_shared_preparation_v1" and
             p["full_raw_files"] == 40 and p["distinct_calibration_runs"] == 27 and
             p["minival_duplicates"] == 13, "complete original preparation")
        need(d["schema"] == "neural067_design_v1" and d["task_id"] == "NEURAL-067" and
             d["person_count"] == 1 and d["query_label_access"] is False and
             d["source_code_commit"] == SOURCE_COMMIT, "original task/source identity")
        need(d["columns"] == list(self.scorer.COLUMNS) and d["arms"] == list(self.scorer.ARMS),
             "unchanged seven columns and four information arms")
        need(b["design_sha256"] == EVIDENCE_PINS["design"][1], "private/public design join")
        need(receipt["status"] == "prepared_source_only" and
             receipt["operator_pin"]["bytes"] == PRODUCER_PIN[0] and
             receipt["operator_pin"]["sha256"] == PRODUCER_PIN[1] and
             receipt["manifest_snapshot_sha256"] == EVIDENCE_PINS["asset_manifest"][1] and
             receipt["preparation"]["sha256"] == EVIDENCE_PINS["preparation"][1] and
             receipt["process"]["completion"]["returncode"] == 0 and
             receipt["process"]["absence_verified"] is True, "observed original producer receipt")
        need(actual["status"] == "original40_full27_prepared_and_externally_closed" and
             actual["native"]["exit_code"] == 0 and
             actual["closure"]["both_natural_child_returncodes"] == 0 and
             actual["closure"]["native_lease_free_at_observation"] is True,
             "saved external operation closure")
        assets = {r["asset_id"]: r for r in a["files"]}
        need(len(a["files"]) == len(assets) == 40 and len(p["rows"]) == 40, "unique full40 sources")
        seen, rows, minival = set(), {}, 0
        for row in p["rows"]:
            ident = row["asset_id"]
            need(ident in assets and ident not in seen, "unique original source row")
            seen.add(ident)
            need(all(row[k] == v for k, v in assets[ident].items()), "exact original source descriptor")
            if row["role"] == "duplicate_minival_not_projected":
                need("minival" in row["path"] and "prepared" not in row, "inventory-only minival")
                minival += 1
                continue
            run = row["run"]
            need(run not in rows and re.fullmatch(r"[0-9]{8}T[0-9]{6}", run), "unique canonical run")
            need(row["units"] == UNITS and row["columns"] == list(self.scorer.COLUMNS) and
                 row["channel_ids"] == "0..175 source row slots, not tracked neuron identity",
                 "unchanged units/coordinates/channel slots")
            need(type(row["n_rows"]) is int and type(row["n_masked_rows"]) is int and
                 2 <= row["n_masked_rows"] <= row["n_rows"] and
                 row["day"] == run[:8], "complete run/mask count")
            need(set(row["prepared"]) == {"input.npz", "target.npz"}, "exact prepared members")
            descriptor(row["prepared"]["input.npz"])
            descriptor(row["prepared"]["target.npz"])
            rows[run] = row
        need(len(rows) == 27 and minival == 13 and set(rows) == set(b["targets"]), "full27 target join")
        need(len(d["train"]) == 13 and len(d["query"]) == 14, "original train/query counts")
        need([(r["run"], r["n_rows"]) for r in d["query"]] ==
             [(r, n) for r, _, n in self.scorer.QUERY], "exact current query order/geometry")
        for role in ("train", "query"):
            need([r["run"] for r in p["rows"] if r["role"] == role] ==
                 [r["run"] for r in d[role]], "exact original split/order")
            for declared in d[role]:
                row = rows[declared["run"]]
                need(row["role"] == role and row["n_rows"] == declared["n_rows"] and
                     row["day"] == declared["day"] and
                     row["prepared"]["input.npz"] == declared["input"] and
                     row["prepared"]["target.npz"] == b["targets"][row["run"]], "prepared/design/target join")
                if role == "train":
                    need(row["prepared"]["target.npz"] == declared["target"], "training target join")
        if self.source_inputs is not None:
            need(self.source_inputs == {r["run"]: r["input"] for r in d["query"]},
                 "journal observations bound to original prepared inputs")
        inventory = {r["path"]: {"bytes": r["bytes"], "sha256": r["sha256"]}
                     for r in actual["actual_files"] if r["path"].endswith(".npz")}
        expected = {"preparation/prepared/" + run + "/" + name: desc
                    for run, row in rows.items() for name, desc in row["prepared"].items()}
        need(len(inventory) == 54 and inventory == expected, "opaque operator inventory join")
        need(sum(v["bytes"] for v in expected.values()) == p["prepared_bytes"], "prepared extent join")
        # Fresh immutable JSON copies detach all mutable caller/metadata dictionaries.
        self.rows = json_value(json.dumps(rows, allow_nan=False).encode())

    def __call__(self, run):
        need(self.position < len(self.scorer.QUERY), "target callback once per original run")
        expected_run, session, count = self.scorer.QUERY[self.position]
        need(run == expected_run, "exact scorer target callback order")
        if self.rows is None:
            self.initialize()
        row = self.rows[run]
        raw = self.reader.capture(self.root / run / "target.npz", MAX_TARGET_CAPTURE)
        need(pin(raw) == row["prepared"]["target.npz"], "same captured authentic target bytes")
        arrays = self.reader.arrays(raw, ("velocity", "eval_mask"), MAX_TARGET_EXPANDED)
        np = self.reader.np
        velocity, mask = arrays["velocity"], arrays["eval_mask"]
        need(velocity.shape == (count, 7) and velocity.dtype.kind == "f" and
             velocity.dtype.itemsize == 8 and np.isfinite(velocity).all(), "original finite float64 seven-output target")
        need(mask.shape == (count,) and mask.dtype.kind == "u" and mask.dtype.itemsize == 1 and
             np.all((mask == 0) | (mask == 1)), "original uint8 zero/one mask")
        need(int(mask.sum()) == row["n_masked_rows"], "declared complete source mask count")
        result = {"run": run, "session": session, "row_ids": list(range(count)),
                  "velocity": velocity.tolist(), "eval_mask": mask.astype(bool).tolist()}
        self.position += 1
        self.loaded.append({"run": run, "rows": count, "masked_rows": int(mask.sum())})
        return result


def grade_submission(submission, prepared_root, evidence_paths, *, scorer_path=None):
    scorer = load_scorer(scorer_path)
    targets = _Targets(prepared_root, evidence_paths, scorer)
    # The unchanged scorer captures all 56 blocks before its first target call.
    return scorer.grade(submission, targets)


def grade_journals(descriptors, load_journal, source_inputs, prepared_root, evidence_paths,
                   *, scorer_path=None, bridge_path=None):
    bridge = module(bridge_path or Path(__file__).resolve().parent.parent / "journal-session-bridge-v1/bridge.py",
                    BRIDGE_PIN, "neural067_original_target_prediction_bridge")
    frozen_inputs = json_value(json.dumps(source_inputs, allow_nan=False).encode())
    submission = bridge.convert(descriptors, load_journal, frozen_inputs, scorer_path=scorer_path)
    scorer = load_scorer(scorer_path)
    targets = _Targets(prepared_root, evidence_paths, scorer, frozen_inputs)
    return scorer.grade(submission, targets)


def qualify_targets(prepared_root, evidence_paths, *, scorer_path=None):
    """Operator-only I/O/interface qualification: synthetic admission, no metric."""
    scorer = load_scorer(scorer_path)
    submission = {"schema": "neural067_session_predictions_v1", "contract_sha256": scorer.CONTRACT_SHA256,
                  "columns": list(scorer.COLUMNS), "entries": [
                      {"arm": arm, "run": run, "session": session, "row_ids": list(range(n)),
                       "prediction": [[0.0] * 7 for _ in range(n)]}
                      for arm in scorer.ARMS for run, session, n in scorer.QUERY]}
    scorer.admit(submission)
    del submission
    targets = _Targets(prepared_root, evidence_paths, scorer)
    for run, session, count in scorer.QUERY:
        value = targets(run)
        scorer.identity(value, run, session, count)
        need(all(type(x) is bool for x in value["eval_mask"]), "literal boolean target interface")
        del value
    return {"schema": "neural067_original_target_qualification_v1", "status": "qualified_callback_io_only",
            "runs": targets.loaded, "full_rows": sum(r["rows"] for r in targets.loaded),
            "masked_rows": sum(r["masked_rows"] for r in targets.loaded), "scientific_score_computed": False,
            "predictions_were_synthetic_admission_only": True, "readiness_promoted": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--submission", type=Path)
    mode.add_argument("--qualify-targets", action="store_true")
    parser.add_argument("--prepared-root", type=Path, required=True)
    for name in EVIDENCE_PINS:
        if name != "preparation":
            parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    parser.add_argument("--scorer-path", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Output freshness is checked before any target access; only aggregate reports are written.
    need(not args.output.exists() and not args.output.is_symlink() and
         all(not p.is_symlink() for p in args.output.parents), "fresh unlinked operator output")
    paths = {k: getattr(args, k) for k in EVIDENCE_PINS if k != "preparation"}
    if args.qualify_targets:
        result = qualify_targets(args.prepared_root, paths, scorer_path=args.scorer_path)
    else:
        raw = load_reader().capture(args.submission, MAX_PUBLIC_SUBMISSION)
        result = grade_submission(json_value(raw), args.prepared_root, paths, scorer_path=args.scorer_path)
    body = (json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    need(len(body) <= 262144, "bounded aggregate operator report")
    with args.output.open("xb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # No target values or unbounded traceback in an operator failure log.
        message = str(exc).encode("utf-8", errors="replace")[:1024].decode("utf-8", errors="ignore")
        print(json.dumps({"status": "failed", "type": type(exc).__name__, "message": message}), file=sys.stderr)
        raise SystemExit(1)
