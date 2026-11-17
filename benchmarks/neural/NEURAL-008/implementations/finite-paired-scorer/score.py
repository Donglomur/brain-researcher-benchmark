#!/usr/bin/env python3
"""Portable finite paired scorer. Never imports or executes a candidate program."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import zipfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np
from neural008_vendor import candidate_adapter as adapter
from neural008_vendor import paired_core

TARGET_IDENTITY_SHA256 = "21298a32e0d30f9f9175395bf8bad4fa26049e55f47a510585d3e50736350e88"
CASES = (adapter.Case("development-001", 2780), adapter.Case("development-002", 2670))
SPEC = adapter.Specification(CASES, ())
FILES = ("EEG_clock.npz", "EEG_EOG_clock.npz", "claims.json")


def ordinary_path(path):
    path = Path(os.path.abspath(path))
    adapter.require(all(not p.is_symlink() for p in (path, *path.parents)), "Unlinked path and parents required")
    return path


def bounded_bytes(path, cap):
    """Freeze a stopped producer's ordinary file without following links/FIFOs."""
    path = ordinary_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        adapter.require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                        and 0 < before.st_size <= cap, "Bounded ordinary single-link file required")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(cap + 1)
        adapter.require(len(body) == before.st_size
                        and adapter._fingerprint(before) == adapter._fingerprint(os.fstat(fd)),
                        "File changed during freeze")
        return body
    finally:
        os.close(fd)


def strict_json(body):
    return json.loads(body.decode("utf-8", errors="strict"), object_pairs_hook=paired_core.unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def freeze_submission(folder):
    folder = ordinary_path(folder)
    adapter.require(folder.is_dir() and {p.name for p in folder.iterdir()} == set(FILES),
                    "Exactly two probability files and claims.json required")
    locks = {}
    for name in FILES:
        body = bounded_bytes(folder / name, 16384 if name == "claims.json" else 4_000_000)
        locks[name] = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    return locks


def target_headers(body, case):
    """Inspect stored target arrays before allocation; never accept pickle."""
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        entries = archive.infolist()
        adapter.require(not archive.comment and len(entries) == 3
                        and {e.filename for e in entries} == {"epoch_id.npy", "stage.npy", "score_mask.npy"},
                        "Exact target array inventory required")
        for entry in entries:
            adapter.require(not entry.is_dir() and not entry.flag_bits & 1
                            and entry.compress_type == zipfile.ZIP_STORED
                            and entry.file_size == entry.compress_size
                            and not stat.S_ISLNK(entry.external_attr >> 16), "Ordinary stored target member required")
            with archive.open(entry) as stream:
                version = np.lib.format.read_magic(stream)
                adapter.require(version in ((1, 0), (2, 0)), "Supported target NPY version required")
                reader = (np.lib.format.read_array_header_1_0 if version == (1, 0)
                          else np.lib.format.read_array_header_2_0)
                shape, fortran, dtype = reader(stream, max_header_size=4096)
                adapter.require(shape == (case.epochs,) and type(fortran) is bool
                                and not dtype.hasobject and dtype.fields is None, "Exact target geometry/type required")
                if entry.filename == "epoch_id.npy":
                    valid = dtype.kind == "U" and 0 < dtype.itemsize <= 512
                elif entry.filename == "stage.npy":
                    valid = dtype.kind in "iu" and dtype.itemsize <= 8
                else:
                    valid = dtype == np.dtype(bool)
                adapter.require(valid and stream.tell() + case.epochs * dtype.itemsize == entry.file_size,
                                "Exact target dtype and complete payload required")


def _load_targets(root, plan):
    """Operator-only lazy read; the CLI supplies only the fixed historical plan."""
    root = ordinary_path(root)
    adapter.require(root.is_dir() and {p.name for p in root.iterdir()} == set(plan["private_files"]),
                    "Exact historical target inventory required")
    body = adapter._locked_bytes(root / "manifest.json", plan["private_files"]["manifest.json"])
    adapter.require(strict_json(body) == plan["private_manifest_expected"], "Historical target lineage differs")
    result = {}
    for case in CASES:
        name = case.case_id + "_labels.npz"
        body = adapter._locked_bytes(root / name, plan["private_files"][name])
        target_headers(body, case)
        with np.load(io.BytesIO(body), allow_pickle=False, max_header_size=4096) as arrays:
            result[case.case_id] = {key: arrays[key] for key in ("epoch_id", "stage", "score_mask")}
    return result


def historical_targets(root):
    # Called only after both complete public panels and claims pass validation.
    body = bounded_bytes(HERE / "target_identity.json", 16384)
    adapter.require(hashlib.sha256(body).hexdigest() == TARGET_IDENTITY_SHA256,
                    "Historical target identity source changed")
    plan = strict_json(body)
    adapter.require(plan["id"] == "NEURAL-008" and plan["class_order"] == list(adapter.CLASS_ORDER)
                    and plan["cases"] == [{"case_id": c.case_id, "epochs": c.epochs} for c in CASES],
                    "Fixed two-person historical scope required")
    return _load_targets(root, plan)


def assess(folder, target_loader=None):
    """With no loader validate only; otherwise score after complete validation.

    This Python boundary expects a trusted operator loader. It is not a submitted
    candidate callback. The command-line route never accepts alternative pins.
    """
    folder = ordinary_path(folder)
    locks = freeze_submission(folder)
    claims = paired_core.read_claims(folder / "claims.json", locks["claims.json"], SPEC)
    arms = {arm: (folder / (arm + ".npz"), locks[arm + ".npz"]) for arm in paired_core.ARMS}
    calls = 0
    if target_loader is None:
        for arm in paired_core.ARMS:
            adapter.validate_submission(*arms[arm], SPEC)
        return {"id": "NEURAL-008", "status": "public_panels_validated", "score": None,
                "private_loader_calls": 0, "submission_freeze": locks,
                "people": 2, "epochs_per_arm": 5450,
                "scientific_improvement_verified": False,
                "paired_training_and_information_access_provenance": "unverified_from_finished_files"}

    def once():
        nonlocal calls
        calls += 1
        adapter.require(calls == 1, "Exactly one private loader call required")
        return target_loader()

    result = paired_core.evaluate(arms, claims, SPEC, once)
    return {"id": "NEURAL-008", "status": "scored", "score": None,
            "private_loader_calls": calls, "submission_freeze": locks,
            "producer_stop_and_execution_isolation": "external_operator_responsibility",
            "result": result}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--targets", type=Path, help="Operator-only directory of the three fixed historical target files")
    parser.add_argument("--output", type=Path, required=True, help="Fresh JSON file in an existing directory")
    args = parser.parse_args(argv)
    output = ordinary_path(args.output)
    adapter.require(output.parent.is_dir() and not output.exists(), "Fresh output in an existing ordinary directory required")
    # Reserve output before any target access. On failure keep a non-answer-bearing
    # failure report; never silently replace an existing operator record.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    code = 0
    try:
        report = assess(args.submission, None if args.validate_only else lambda: historical_targets(args.targets))
    except Exception as exc:
        code = 2
        report = {"id": "NEURAL-008", "status": "assessment_failed", "score": None,
                  "error_type": type(exc).__name__, "scientific_improvement_verified": False}
    try:
        body = (json.dumps(report, allow_nan=False, indent=2) + "\n").encode()
        adapter.require(len(body) <= 32768, "Bounded JSON report required")
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(fd)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
