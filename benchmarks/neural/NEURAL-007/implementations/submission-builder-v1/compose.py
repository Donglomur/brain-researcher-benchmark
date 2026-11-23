"""Build the existing finite sleep submission from a complete probability CSV.

Public input validation only. No EEG, targets, reference predictions, fitting,
scoring or participant-provenance claim. Requires Python 3.11 and NumPy.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys


HERE = Path(__file__).resolve().parent
CASES = (("development-001", 2780), ("development-002", 2670))
CLASSES = ("W", "N1", "N2", "N3", "R")
HEADER = ("epoch_id", *CLASSES)
MAX_BYTES = 4_000_000
ADAPTER_PIN = (14326, "fc8363b28a86cd1f5083b4cc5d24fb1a5a4abd1d490d9163a305f85f1fbe4d23")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def ordinary(path):
    path = Path(os.path.abspath(path))
    require(not any(p.is_symlink() for p in (path, *path.parents)), "Linked path rejected")
    return path


def read_source(path, cap):
    path = ordinary(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and 0 < before.st_size <= cap, "Bounded ordinary single-link input required")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(cap + 1)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        require(len(raw) == before.st_size and stamp(before) == stamp(os.fstat(fd))
                == stamp(path.stat()), "Input changed during capture")
        return raw
    finally:
        os.close(fd)


def load_adapter(path=None):
    path = ordinary(path or HERE.parent / "finite-attempt-audit/vendor/candidate_adapter.py")
    raw = read_source(path, ADAPTER_PIN[0])
    require((len(raw), hashlib.sha256(raw).hexdigest()) == ADAPTER_PIN,
            "Original public validator source changed")
    name = "_sleep007_csv_adapter_" + ADAPTER_PIN[1]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            exec(compile(raw, str(path), "exec"), module.__dict__)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    return sys.modules[name]


def arrays_from_csv(raw, adapter):
    """Require complete ordered IDs; never sort, fill, clip or normalize rows."""
    require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, "Bounded CSV bytes required")
    text = raw.decode("utf-8")
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    require(tuple(next(reader, ())) == HEADER, "Exact header required: epoch_id,W,N1,N2,N3,R")
    arrays = {"class_order": adapter.np.asarray(CLASSES)}
    for case, epochs in CASES:
        rows = []
        for index in range(epochs):
            row = next(reader, None)
            expected = f"{case}/{index:05d}"
            require(row is not None and len(row) == 6, "Six CSV fields required at " + expected)
            require(row[0] == expected, "Canonical whole-clock identity/order required at " + expected)
            try:
                probabilities = [float(value) for value in row[1:]]
            except (ValueError, OverflowError) as exc:
                raise ValueError("Numeric probabilities required at " + expected) from exc
            rows.append(probabilities)
        probabilities = adapter.np.asarray(rows, dtype=adapter.np.float64)
        require(adapter.np.isfinite(probabilities).all()
                and adapter.np.all((probabilities >= 0) & (probabilities <= 1)),
                "Finite probabilities in [0,1] required for " + case)
        require(adapter.np.all(adapter.np.abs(probabilities.sum(axis=1, dtype=adapter.np.float64)
                                             - 1.) <= adapter.ROW_SUM_ATOL),
                "Absolute row-sum tolerance 1e-6; no correction for " + case)
        arrays[case + "__epoch_id"] = adapter.expected_ids(adapter.Case(case, epochs))
        arrays[case + "__probabilities"] = probabilities
    require(next(reader, None) is None, "Extra CSV rows rejected")
    return arrays


def build(input_path, output_path, adapter_source=None):
    """Create one new NPZ and authenticate it through the unchanged validator."""
    output = ordinary(output_path)
    require(output.suffix == ".npz", "Explicit .npz output filename required")
    if output.exists():
        raise FileExistsError("Output already exists")
    require(output.parent.is_dir(), "Existing output parent required")
    # Check destination before reading participant predictions or validator code.
    raw = read_source(input_path, MAX_BYTES)
    adapter = load_adapter(adapter_source)
    arrays = arrays_from_csv(raw, adapter)
    stream = io.BytesIO()
    adapter.np.savez(stream, **arrays)
    body = stream.getvalue()
    require(0 < len(body) <= MAX_BYTES, "Encoded submission exceeds original 4,000,000-byte cap")
    identity = pin(body)
    # Exclusive creation protects existing predictions even if another writer wins
    # after the initial check. A filesystem/validation failure retains the new file.
    with output.open("xb") as destination:
        destination.write(body)
    output.chmod(0o444)
    spec = adapter.Specification(tuple(adapter.Case(*case) for case in CASES), ("YASA", "RF"))
    adapter.validate_submission(output, identity, spec)
    return {"schema": "neural007_csv_submission_v1", "status": "valid_prediction_contract",
            "source_csv": pin(raw), "submission": identity,
            "people": len(CASES), "epochs": sum(epochs for _, epochs in CASES),
            "class_order": list(CLASSES), "probability_dtype": "float64",
            "rows_reordered": False, "probabilities_corrected": False,
            "targets_read": False, "scientific_score_computed": False,
            "programme_provenance_verified": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="Complete ordered probability CSV")
    parser.add_argument("--output", required=True, help="New .npz path with an existing parent")
    parser.add_argument("--adapter-source", help="Optional relocated exact original public validator")
    args = parser.parse_args(argv)
    try:
        result = build(args.csv, args.output, args.adapter_source)
    except (ValueError, OSError, csv.Error, ImportError) as exc:
        print(json.dumps({"status": "submission_not_built_or_not_validated",
                          "error_type": type(exc).__name__, "error": str(exc),
                          "scientific_score_computed": False}), file=sys.stderr)
        return 2
    print(json.dumps(result, allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
