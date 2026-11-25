"""Portable complete-panel scoring; private target access follows score admission.

This is an operator component, not a candidate supervisor or a data preparation.
The original target-free numerical sources are preserved under legacy/.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path

import numpy as np


def _source(name):
    path = Path(__file__).resolve().parent / "legacy" / "public" / (name + ".py")
    spec = importlib.util.spec_from_file_location("neural051_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_io = _source("io_utils")
_protocol = _source("protocol")
SUBJECTS, ROIS = _protocol.SUBJECTS, _protocol.ROIS
CASES = tuple(f"sub-{p}_{r}" for p in SUBJECTS for r in ROIS)
SHAPE = (1540, 3700)


def roster_digest(roster):
    return hashlib.sha256(json.dumps(roster, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def validate_roster(roster):
    if not isinstance(roster, dict) or set(roster) != set(CASES):
        raise ValueError("complete six-case public roster required")
    for row in roster.values():
        if not isinstance(row, dict) or set(row) != {"query_ids", "candidate_ids"}:
            raise ValueError("public roster fields")
        for field, count, prefix in (("query_ids", 1540, "q"), ("candidate_ids", 3700, "i")):
            ids = row[field]
            if (not isinstance(ids, list) or len(ids) != count or
                    any(not isinstance(x, str) or len(x) != 25 or x[0] != prefix or
                        any(c not in "0123456789abcdef" for c in x[1:]) for x in ids) or
                    len(set(ids)) != count):
                raise ValueError("public roster support/opaque IDs")
    candidates = roster[CASES[0]]["candidate_ids"]
    if any(row["candidate_ids"] != candidates for row in roster.values()):
        raise ValueError("shared candidate order")
    for person in SUBJECTS:
        if roster[f"sub-{person}_V1"]["query_ids"] != roster[f"sub-{person}_IT"]["query_ids"]:
            raise ValueError("paired ROI query order")


def load_array(raw):
    if len(raw) > 50_000_000:
        raise ValueError("matrix byte cap")
    stream = io.BytesIO(raw)
    version = np.lib.format.read_magic(stream)
    if version == (1, 0):
        shape, fortran, dtype = np.lib.format.read_array_header_1_0(stream, max_header_size=4096)
    elif version == (2, 0):
        shape, fortran, dtype = np.lib.format.read_array_header_2_0(stream, max_header_size=4096)
    else:
        raise ValueError("NPY version")
    if shape != SHAPE or fortran or dtype.kind != "f" or dtype.itemsize not in (4, 8) or dtype.hasobject:
        raise ValueError("C-order float32/float64 exact shape")
    if len(raw) - stream.tell() != math.prod(SHAPE) * dtype.itemsize:
        raise ValueError("NPY exact payload")
    array = np.frombuffer(raw, dtype=dtype, offset=stream.tell()).reshape(SHAPE)
    if not np.isfinite(array).all():
        raise ValueError("finite scores required")
    return array


def admit(root, manifest, roster):
    validate_roster(roster)
    if (not isinstance(manifest, dict) or set(manifest) != {"schema", "files", "roster_sha256"}
            or manifest["schema"] != "neural051-scores-v1"
            or not isinstance(manifest["files"], dict) or set(manifest["files"]) != set(CASES)
            or manifest["roster_sha256"] != roster_digest(roster)):
        raise ValueError("complete submission and exact roster binding required")
    root = Path(root)
    if root.is_symlink() or any(p.is_symlink() for p in root.parents):
        raise ValueError("symlink submission ancestry")
    if not root.is_dir() or {p.name for p in root.iterdir()} != {"submission.json", *(c + ".npy" for c in CASES)}:
        raise ValueError("exact seven-file submission")
    arrays, pins = {}, {}
    for case in CASES:
        record = manifest["files"][case]
        if (not isinstance(record, dict) or set(record) != {"file", "sha256"}
                or record["file"] != case + ".npy"
                or not isinstance(record["sha256"], str) or len(record["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in record["sha256"])):
            raise ValueError("score file binding")
        raw, pins[case] = _io.capture(root / record["file"], 50_000_000, record["sha256"])
        arrays[case] = load_array(raw)
    return arrays, pins


def validate_design(roster, design):
    """Check full operator mapping, especially paired identities, before metrics."""
    if (not isinstance(design, dict) or design.get("schema") != "neural051-design-v1"
            or design.get("full_canonical_split") is not True):
        raise ValueError("operator design")
    candidates, concepts, cases = design["candidate_ids"], design["candidate_concepts"], design["cases"]
    if candidates != roster[CASES[0]]["candidate_ids"] or not isinstance(concepts, list) or len(concepts) != 3700:
        raise ValueError("operator candidate identity join")
    if any(not isinstance(c, str) or not c for c in concepts):
        raise ValueError("operator concept IDs")
    if Counter(Counter(concepts).values()) != Counter({5: 620, 6: 100}):
        raise ValueError("complete 720-concept candidate census")
    if not isinstance(cases, list) or len(cases) != 6 or {c["id"] for c in cases} != set(CASES):
        raise ValueError("complete six-case design")
    by_case = {}
    for case in cases:
        key = case["id"]
        if case["person"] not in SUBJECTS or case["roi"] not in ROIS or key != f"sub-{case['person']}_{case['roi']}":
            raise ValueError("person/ROI case identity")
        queries = case["queries"]
        if not isinstance(queries, list) or [q["id"] for q in queries] != roster[key]["query_ids"]:
            raise ValueError("public/private query identity join")
        correct = [q["candidate_index"] for q in queries]
        if any(type(i) is not int or not 0 <= i < 3700 for i in correct) or len(set(correct)) != 1540:
            raise ValueError("one distinct image per query group")
        trials, groups = set(), []
        for query in queries:
            ids = query["trial_ids"]
            if (not isinstance(ids, list) or len(ids) not in (1, 2) or
                    any(type(t) is not int or not 0 <= t < 9840 for t in ids)
                    or len(set(ids)) != len(ids) or trials.intersection(ids)):
                raise ValueError("unique native trial groups")
            trials.update(ids)
            groups.append(tuple(sorted(ids)))
        if Counter(map(len, groups)) != Counter({1: 1440, 2: 100}):
            raise ValueError("frozen query repeat census")
        by_case[key] = (correct, groups)
    for person in SUBJECTS:
        if by_case[f"sub-{person}_V1"] != by_case[f"sub-{person}_IT"]:
            raise ValueError("paired ROI image/trial mappings disagree")
    return by_case


def rank_metrics(scores, correct):
    """Expected Top1/Top5/MRR over uniform permutations within exact score ties."""
    scores = np.asarray(scores)
    if (scores.ndim != 1 or scores.dtype.kind != "f" or not np.isfinite(scores).all()
            or type(correct) is not int or not 0 <= correct < len(scores)):
        raise ValueError("finite floating score row and valid target index required")
    value = scores[correct]
    above = int(np.count_nonzero(scores > value))
    ties = int(np.count_nonzero(scores == value))
    return {"top1": 1.0 / ties if above == 0 else 0.0,
            "top5": min(ties, max(0, 5 - above)) / ties,
            "mrr": math.fsum(1.0 / rank for rank in range(above + 1, above + ties + 1)) / ties}


def _mean(rows):
    return {**{key: math.fsum(row[key] for row in rows) / len(rows) for key in ("top1", "top5", "mrr")},
            "images": len(rows)}


def grade_arrays(arrays, roster, design):
    """Trusted in-memory API; still validates every array before target metrics."""
    validate_roster(roster)
    if set(arrays) != set(CASES):
        raise ValueError("complete six arrays")
    for array in arrays.values():
        if (not isinstance(array, np.ndarray) or array.shape != SHAPE or array.dtype.kind != "f"
                or array.dtype.itemsize not in (4, 8) or not array.flags.c_contiguous or not np.isfinite(array).all()):
            raise ValueError("complete finite C-order float32/64 score arrays")
    mapping = validate_design(roster, design)
    concept_indices = {}
    for index, concept in enumerate(design["candidate_concepts"]):
        concept_indices.setdefault(concept, []).append(index)
    out = {}
    for case in CASES:
        all_rows, within, singles, repeats = [], [], [], []
        for scores, index, trials in zip(arrays[case], *mapping[case]):
            row = rank_metrics(scores, index)
            all_rows.append(row)
            (singles if len(trials) == 1 else repeats).append(row)
            indices = concept_indices[design["candidate_concepts"][index]]
            within.append(rank_metrics(scores[indices], indices.index(index)))
        out[case] = {"all_images": _mean(all_rows), "same_concept": _mean(within),
                     "single_presentation": _mean(singles), "two_repeat_mean": _mean(repeats)}
    macro = {roi: {key: math.fsum(out[f"sub-{p}_{roi}"]["all_images"][key] for p in SUBJECTS) / 3
                   for key in ("top1", "top5", "mrr")} for roi in ROIS}
    paired = {p: {key: out[f"sub-{p}_IT"]["all_images"][key] - out[f"sub-{p}_V1"]["all_images"][key]
                   for key in ("top1", "top5", "mrr")} for p in SUBJECTS}
    return {"status": "scored", "participant_macro": macro, "cases": out,
            "paired_IT_minus_V1": paired,
            "IT_minus_V1_top1": macro["IT"]["top1"] - macro["V1"]["top1"],
            "historical_primary_name": "participant_macro_IT_expected_top1",
            "historical_primary": macro["IT"]["top1"],
            "primary": {roi: macro[roi]["top1"] for roi in ROIS},
            "primary_name": "separate_ROI_participant_macro_expected_top1",
            "biological_units": 3, "population_inference": False,
            "runtime_or_data_qualification": False}


def evaluate(root, manifest, roster, private_loader):
    errors = (ValueError, TypeError, KeyError, OSError, OverflowError, RecursionError, IndexError)
    try:
        validate_roster(roster)
    except errors:
        return {"status": "operator_error", "primary": None, "private_reference_invoked": False}
    try:
        arrays, pins = admit(root, manifest, roster)
    except errors:
        return {"status": "invalid_submission", "primary": None, "private_reference_invoked": False}
    try:
        result = grade_arrays(arrays, roster, private_loader())
    except errors:
        return {"status": "operator_error", "primary": None, "private_reference_invoked": True}
    return {**result, "private_reference_invoked": True, "captured_submission_sha256": pins}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("submission", "roster", "roster-sha256", "design", "design-sha256", "output"):
        parser.add_argument("--" + field, required=True)
    args = parser.parse_args()
    _io.fresh(args.output)
    try:
        roster = _io.decode(_io.capture(args.roster, 3_000_000, args.roster_sha256)[0])
        validate_roster(roster)
    except (ValueError, TypeError, KeyError, OSError, RecursionError):
        result = {"status": "operator_error", "primary": None, "private_reference_invoked": False}
    else:
        try:
            manifest = _io.decode(_io.capture(Path(args.submission) / "submission.json", 10_000)[0])
        except (ValueError, TypeError, KeyError, OSError, RecursionError):
            result = {"status": "invalid_submission", "primary": None, "private_reference_invoked": False}
        else:
            result = evaluate(args.submission, manifest, roster,
                              lambda: _io.decode(_io.capture(args.design, 10_000_000, args.design_sha256)[0]))
    _io.write_json(args.output, result)
    return {"scored": 0, "invalid_submission": 1, "operator_error": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
