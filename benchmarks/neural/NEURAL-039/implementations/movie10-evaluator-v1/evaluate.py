#!/usr/bin/env python3
"""Whole-film Movie10 development scoring; never executes a candidate or fits a model."""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

SUBJECTS = ("sub-01", "sub-02", "sub-03", "sub-05")
FILMS = ("bourne", "figures", "life", "wolf")
CASES = tuple(f"{s}_hold-{f}" for s in SUBJECTS for f in FILMS)
SOURCE_COMMIT = "96750e7017b30cb02f011c11561a3df897695853"
CONDITION = "movie10_whole_film_development_strict_v2"
KEY = re.compile(r"ses-([0-9]+)_task-(bourne|figures|life|wolf)([0-9]+)(?:_run-([12]))?")


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def strict_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("Nonfinite JSON token")

    return json.loads(body.decode("utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)


def fields(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError("Exact object fields required: " + ", ".join(names))


def ordinary(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Symbolic links are not admitted")
    return path


def stamp(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns)


@contextmanager
def open_file(path, cap, expected=None):
    path = ordinary(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= cap:
            raise ValueError("Bounded singly linked ordinary file required")
        if expected is not None:
            hasher = hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(block)
            if before.st_size != expected["bytes"] or hasher.hexdigest() != expected["sha256"]:
                raise ValueError("Source byte identity differs")
            stream.seek(0)
        yield stream
        if stamp(before) != stamp(os.fstat(stream.fileno())) or stamp(before) != stamp(path.lstat()):
            raise ValueError("Input changed during use")


def read_bytes(path, cap):
    with open_file(path, cap) as stream:
        return stream.read(cap + 1)


def read_panel(path, expected_sha256):
    """Only operator metadata. This function never opens response files."""
    body = read_bytes(path, 1024 * 1024)
    if digest(body) != expected_sha256:
        raise ValueError("Frozen operator panel digest differs")
    return validate_panel(strict_json(body))


def validate_panel(panel):
    """Validate the complete scientific metadata contract without reading target values."""
    fields(panel, ("schema", "source_commit", "subjects"))
    if panel["schema"] != "neural039_movie10_panel_v1" or panel["source_commit"] != SOURCE_COMMIT:
        raise ValueError("Pinned Movie10 panel required")
    fields(panel["subjects"], SUBJECTS)
    for subject in SUBJECTS:
        source = panel["subjects"][subject]
        fields(source, ("file", "bytes", "sha256", "datasets"))
        if source["file"] != f"{subject}_movie10.h5":
            raise ValueError("Native participant source filename required")
        if type(source["bytes"]) is not int or source["bytes"] <= 0:
            raise ValueError("Positive source byte count required")
        if type(source["sha256"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]):
            raise ValueError("Source SHA256 required")
        datasets = source["datasets"]
        if type(datasets) is not dict or not datasets:
            raise ValueError("Complete native dataset inventory required")
        identities, films = set(), set()
        for key, shape in datasets.items():
            match = KEY.fullmatch(key)
            if not match:
                raise ValueError("Unknown native Movie10 dataset key")
            _, film, segment, run = match.groups()
            identity = (film, int(segment), int(run or 1))
            if int(segment) < 1 or identity in identities:
                raise ValueError("Duplicate or invalid segment/run identity")
            if film in ("life", "figures") and run is None:
                raise ValueError("Repeated movies need explicit native run identity")
            if film in ("bourne", "wolf") and run not in (None, "1"):
                raise ValueError("Unexpected second viewing")
            identities.add(identity)
            films.add(film)
            if (type(shape) is not list or len(shape) != 2 or
                    any(type(v) is not int for v in shape) or shape[0] <= 15 or shape[1] != 1000):
                raise ValueError("Native samples-by-1000 shape with complete fixed guards required")
        if films != set(FILMS):
            raise ValueError("All four complete films required for each person")
        for film, segment, run in identities:
            if film in ("life", "figures") and (film, segment, 3 - run) not in identities:
                raise ValueError("Both original viewings must remain in the same film")
    return panel


def queries(panel):
    """Public row/parcel identity. Source paths and neural values are never exported."""
    result = {}
    for subject in SUBJECTS:
        for film in FILMS:
            case_id = f"{subject}_hold-{film}"
            runs, offset = [], 0
            for key, shape in sorted(panel["subjects"][subject]["datasets"].items()):
                if KEY.fullmatch(key).group(2) != film:
                    continue
                start, stop = 8, shape[0] - 5
                runs.append({"key": key, "native_samples": shape[0], "start": start,
                             "stop": stop, "offset": offset})
                offset += stop - start
            result[case_id] = {
                "schema": "neural039_query_v2", "condition": CONDITION, "case_id": case_id,
                "subject": subject, "held_film": film, "source_commit": SOURCE_COMMIT,
                "shape": [offset, 1000], "dtype": "<f4", "tr_seconds": 1.49,
                "parcel_order": "native_subject_hdf5_columns_0_through_999", "runs": runs,
            }
    return result


def exact_directory(path, names):
    path = ordinary(path)
    if not path.is_dir() or set(p.name for p in path.iterdir()) != set(names):
        raise ValueError("Exact complete submission directory required")
    return path


def array(body, shape, np):
    """Non-pickle NPY parser; reject extra/truncated bytes and ambiguous axis metadata."""
    if body[:6] != b"\x93NUMPY" or body[6:8] not in (b"\x01\x00", b"\x02\x00"):
        raise ValueError("NPY version 1 or 2 required")
    width = 2 if body[6] == 1 else 4
    offset = 8 + width
    size = int.from_bytes(body[8:offset], "little")
    if not 0 < size <= 256 or len(body) != offset + size + 4 * math.prod(shape):
        raise ValueError("Exact NPY header and native array extent required")
    node = ast.parse(body[offset:offset + size].decode("ascii").strip(), mode="eval").body
    if not isinstance(node, ast.Dict) or len(node.keys) != 3:
        raise ValueError("Exact NPY header keys required")
    if any(not isinstance(k, ast.Constant) or type(k.value) is not str for k in node.keys):
        raise ValueError("String NPY header keys required")
    if len({k.value for k in node.keys}) != 3:
        raise ValueError("Duplicate NPY header key")
    header = ast.literal_eval(node)
    fields(header, ("descr", "fortran_order", "shape"))
    if (header["descr"] != "<f4" or header["fortran_order"] is not False or
            type(header["shape"]) is not tuple or any(type(x) is not int for x in header["shape"]) or
            header["shape"] != tuple(shape)):
        raise ValueError("Little-endian float32, C order, native time-by-parcel shape required")
    data = np.frombuffer(body, dtype="<f4", offset=offset + size).reshape(shape)
    if not np.isfinite(data).all():
        raise ValueError("All prediction samples must be finite")
    if np.any(np.all(data == data[0], axis=0)):
        raise ValueError("Undefined correlation: constant prediction parcel")
    return data


def admit(root, query, np):
    root = exact_directory(root, CASES)
    admitted, pins = {}, {}
    for case_id in CASES:
        folder = exact_directory(root / case_id, ("submission.json", "predictions.npy"))
        meta = strict_json(read_bytes(folder / "submission.json", 4096))
        if meta != {"schema": "neural039_prediction_v2", "case_id": case_id,
                    "query_sha256": digest(canonical(query[case_id]))}:
            raise ValueError("Prediction case/query identity differs")
        shape = query[case_id]["shape"]
        body = read_bytes(folder / "predictions.npy", 4 * math.prod(shape) + 512)
        admitted[case_id] = array(body, shape, np)
        pins[case_id] = {"bytes": len(body), "sha256": digest(body)}
    return admitted, pins


def correlations(prediction, target, np):
    if prediction.shape != target.shape or prediction.ndim != 2 or prediction.shape[1] != 1000:
        raise ValueError("Complete matched time-by-1000 arrays required")
    if not np.isfinite(target).all():
        raise ValueError("Nonfinite target; no response-dependent exclusions allowed")
    if np.any(np.all(target == target[0], axis=0)):
        raise ValueError("Undefined correlation: constant target parcel")
    if not np.isfinite(prediction).all() or np.any(np.all(prediction == prediction[0], axis=0)):
        raise ValueError("Undefined or nonfinite prediction")
    x, y = prediction.astype(np.float64), target.astype(np.float64)
    x -= x.mean(axis=0)
    y -= y.mean(axis=0)
    r = np.sum(x * y, axis=0) / (np.sqrt(np.sum(x * x, axis=0)) * np.sqrt(np.sum(y * y, axis=0)))
    if not np.isfinite(r).all() or np.any(np.abs(r) > 1 + 1e-12):
        raise ValueError("Pearson arithmetic outside rounding envelope")
    return {"samples": len(x), "parcels": 1000, "parcel_correlations": r.tolist(),
            "mean": float(r.mean())}


def aggregate(results):
    if set(results) != set(CASES):
        raise ValueError("All 16 person-film results required")
    person = {s: math.fsum(results[f"{s}_hold-{f}"]["mean"] for f in FILMS) / 4 for s in SUBJECTS}
    return {"primary_score": math.fsum(person.values()) / 4, "per_person": person,
            "biological_n": 4, "film_groups": 4,
            "aggregation": "equal parcels, then equal films, then equal people"}


def evaluate(panel, source_root, submission_root, np, h5py, validate_only=False):
    """Call only with operator-validated panel metadata; CLI pins it with read_panel."""
    target_opens = 0
    try:
        validate_panel(panel)
        query = queries(panel)
    except (KeyError, TypeError, ValueError) as error:
        return {"status": "operator_error", "primary_score": None, "detail": str(error), "target_file_opens": 0}
    try:
        prediction, pins = admit(submission_root, query, np)
    except (ValueError, OSError, SyntaxError, UnicodeError, TypeError) as error:
        return {"status": "candidate_invalid", "primary_score": None, "detail": str(error), "target_file_opens": 0}
    if validate_only:
        return {"status": "valid_predictions", "primary_score": None, "prediction_pins": pins, "target_file_opens": 0}
    results = {}
    try:
        for subject in SUBJECTS:
            source = panel["subjects"][subject]
            target_opens += 1
            with open_file(Path(source_root) / source["file"], source["bytes"], source) as stream:
                with h5py.File(stream, "r") as h:
                    if set(h.keys()) != set(source["datasets"]):
                        raise ValueError("Source inventory differs; cannot omit or add native runs")
                    for key, shape in source["datasets"].items():
                        if not isinstance(h.get(key, getlink=True), h5py.HardLink):
                            raise ValueError("External or soft HDF5 links rejected")
                        data = h[key]
                        if (not isinstance(data, h5py.Dataset) or list(data.shape) != shape or
                                data.dtype.str != "<f4" or data.is_virtual or data.external):
                            raise ValueError("Original local float32 dataset schema required")
                    for film in FILMS:
                        case_id = f"{subject}_hold-{film}"
                        target = np.concatenate([h[r["key"]][r["start"]:r["stop"]]
                                                 for r in query[case_id]["runs"]], axis=0)
                        results[case_id] = correlations(prediction[case_id], target, np)
        return {"status": "scored", "condition": CONDITION, **aggregate(results), "per_case": results,
                "prediction_pins": pins, "target_file_opens": target_opens,
                "runtime_or_training_provenance_verified": False,
                "uncertainty": "descriptive four-person values; no independent-TR or parcel inference"}
    except (ValueError, OSError, KeyError, TypeError) as error:
        return {"status": "operator_error", "primary_score": None, "detail": str(error),
                "target_file_opens": target_opens}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--panel-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("queries", help="Export public metadata without opening neural targets")
    score = sub.add_parser("score")
    score.add_argument("--submission-dir", type=Path, required=True)
    score.add_argument("--source-root", type=Path, required=True)
    score.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    panel = read_panel(args.panel, args.panel_sha256)
    if args.action == "queries":
        result = queries(panel)
    else:
        import numpy as np
        import h5py
        result = evaluate(panel, args.source_root, args.submission_dir, np, h5py, args.validate_only)
    output = ordinary(args.output)
    with output.open("xb") as handle:
        handle.write(canonical(result))
    return 0 if args.action == "queries" or result["status"] in ("scored", "valid_predictions") else 2


if __name__ == "__main__":
    raise SystemExit(main())
