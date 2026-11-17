"""Candidate-specific public validation, then private descriptive scoring.

Prepared source only. No real input bindings, launcher or authorization lives
here. The operator must hash-freeze submissions after the predictor stops and
must provide an isolated target loader only in the grading process.
"""
from dataclasses import dataclass
import hashlib
import io
import math
import os
from pathlib import Path
import re
import stat
import zipfile

import numpy as np

CLASS_ORDER = ("W", "N1", "N2", "N3", "R")
ROW_SUM_ATOL = 1e-6
MAX_FILE_BYTES = 16_000_000
MAX_ARRAY_BYTES = 16_000_000
MAX_HEADER_BYTES = 4096
MAX_PEOPLE = 16
MAX_TOTAL_EPOCHS = 100_000


def require(condition, message):
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True)
class Case:
    case_id: str
    epochs: int


@dataclass(frozen=True)
class Specification:
    cases: tuple
    comparator_names: tuple


def checked_specification(spec):
    require(isinstance(spec, Specification) and type(spec.cases) is tuple
            and 1 <= len(spec.cases) <= MAX_PEOPLE, "bounded frozen case specification")
    for case in spec.cases:
        require(isinstance(case, Case) and type(case.case_id) is str
                and re.fullmatch(r"[a-z][a-z0-9-]{0,63}", case.case_id) is not None
                and type(case.epochs) is int and 1 <= case.epochs <= MAX_TOTAL_EPOCHS,
                "canonical bounded participant specification")
    require(len({c.case_id for c in spec.cases}) == len(spec.cases)
            and sum(c.epochs for c in spec.cases) <= MAX_TOTAL_EPOCHS,
            "unique cases and total epoch ceiling")
    require(type(spec.comparator_names) is tuple
            and len(spec.comparator_names) <= 32
            and len(set(spec.comparator_names)) == len(spec.comparator_names)
            and all(type(name) is str and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", name)
                    for name in spec.comparator_names), "frozen unique comparator names")
    return spec


def expected_ids(case):
    return np.asarray([f"{case.case_id}/{index:05d}" for index in range(case.epochs)], dtype="U")


def _fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_nlink)


def _locked_bytes(path, lock):
    """Read one bounded ordinary file; lock must come from the trusted collector."""
    require(type(lock) is dict and set(lock) == {"bytes", "sha256"}
            and type(lock["bytes"]) is int and 0 < lock["bytes"] <= MAX_FILE_BYTES
            and type(lock["sha256"]) is str
            and re.fullmatch(r"[0-9a-f]{64}", lock["sha256"]) is not None,
            "trusted bounded file freeze required")
    path = Path(os.path.abspath(path))
    require(all(not p.is_symlink() for p in (path, *path.parents)), "linked input or parent")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and before.st_size == lock["bytes"], "ordinary single-link exact-size input")
        blocks, remaining = [], lock["bytes"]
        while remaining:
            block = os.read(fd, min(131072, remaining))
            require(bool(block), "truncated input")
            blocks.append(block)
            remaining -= len(block)
        require(os.read(fd, 1) == b"" and _fingerprint(os.fstat(fd)) == _fingerprint(before),
                "input changed while reading")
        data = b"".join(blocks)
    finally:
        os.close(fd)
    require(hashlib.sha256(data).hexdigest() == lock["sha256"], "frozen input digest differs")
    return data


def _array_layout(spec):
    layout = {"class_order": ((5,), "classes")}
    for case in spec.cases:
        layout[case.case_id + "__epoch_id"] = ((case.epochs,), "ids")
        layout[case.case_id + "__probabilities"] = ((case.epochs, 5), "probabilities")
    return layout


def _inspect_headers(data, layout):
    """Inspect every bounded NPY header before NumPy loads any payload array."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        expected = {name + ".npy" for name in layout}
        require(not archive.comment and len(entries) == len(expected)
                and {entry.filename for entry in entries} == expected,
                "exact unique NPZ inventory; no absent or extra cases/arrays")
        total = 0
        for entry in entries:
            require(not entry.is_dir() and not entry.flag_bits & 1
                    and entry.compress_type == zipfile.ZIP_STORED
                    and entry.compress_size == entry.file_size
                    and not stat.S_ISLNK(entry.external_attr >> 16)
                    and 0 < entry.file_size <= MAX_ARRAY_BYTES,
                    "ordinary unencrypted stored bounded NPY member")
            total += entry.file_size
            require(total <= MAX_ARRAY_BYTES, "cumulative array size ceiling")
            shape_expected, role = layout[entry.filename[:-4]]
            with archive.open(entry) as stream:
                version = np.lib.format.read_magic(stream)
                require(version in ((1, 0), (2, 0)), "supported bounded NPY version")
                read_header = (np.lib.format.read_array_header_1_0 if version == (1, 0)
                               else np.lib.format.read_array_header_2_0)
                shape, fortran, dtype = read_header(stream, max_header_size=MAX_HEADER_BYTES)
                require(type(shape) is tuple and all(type(n) is int and n >= 0 for n in shape)
                        and shape == shape_expected and type(fortran) is bool
                        and not dtype.hasobject and dtype.fields is None,
                        "exact array geometry; no object or structured dtype")
                if role == "probabilities":
                    require(dtype.kind == "f" and dtype.itemsize in (4, 8), "float32/float64 probabilities required")
                else:
                    max_chars = 8 if role == "classes" else 128
                    require(dtype.kind == "U" and 0 < dtype.itemsize <= 4 * max_chars,
                            "bounded Unicode identities/classes required")
                byte_count = math.prod(shape) * dtype.itemsize
                require(byte_count <= MAX_ARRAY_BYTES
                        and stream.tell() + byte_count == entry.file_size,
                        "exact complete NPY payload length")


def validate_submission(path, lock, spec):
    """Validate arbitrary probabilities; no seven-arm or ensemble constraints."""
    checked_specification(spec)
    data = _locked_bytes(path, lock)
    layout = _array_layout(spec)
    _inspect_headers(data, layout)
    # Only reached after every member's structure and prospective allocation pass.
    with np.load(io.BytesIO(data), allow_pickle=False, max_header_size=MAX_HEADER_BYTES) as archive:
        values = {name: archive[name] for name in layout}
    require(np.array_equal(values["class_order"], np.asarray(CLASS_ORDER)), "exact fixed class order")
    people = {}
    for case in spec.cases:
        ids = values[case.case_id + "__epoch_id"]
        probability = values[case.case_id + "__probabilities"]
        require(np.array_equal(ids, expected_ids(case)), "canonical full-clock epoch identity/order")
        require(np.isfinite(probability).all() and np.all((probability >= 0) & (probability <= 1)),
                "finite probabilities in [0,1]")
        # Float64 summation prevents float32 accumulation from defining another tolerance.
        require(np.all(np.abs(probability.sum(axis=1, dtype=np.float64) - 1.) <= ROW_SUM_ATOL),
                "absolute row-sum tolerance 1e-6; no correction")
        probability.setflags(write=False)
        ids.setflags(write=False)
        people[case.case_id] = {"epoch_id": ids, "probabilities": probability}
    return {"people": people, "file": dict(lock)}


def _checked_targets(targets, spec):
    require(type(targets) is dict and set(targets) == {case.case_id for case in spec.cases},
            "exact private participant set")
    checked = {}
    for case in spec.cases:
        row = targets[case.case_id]
        require(type(row) is dict and set(row) == {"epoch_id", "stage", "score_mask"}
                and all(isinstance(v, np.ndarray) for v in row.values()), "exact private target fields")
        ids, stage, mask = (row[name] for name in ("epoch_id", "stage", "score_mask"))
        require(ids.dtype.kind == "U" and np.array_equal(ids, expected_ids(case))
                and stage.shape == mask.shape == (case.epochs,)
                and stage.dtype.kind in "iu" and stage.dtype.itemsize <= 8
                and mask.dtype == np.dtype(bool), "private target identity/dtype/geometry")
        require(np.isin(stage, [-1, 0, 1, 2, 3, 4]).all()
                and np.array_equal(mask, stage >= 0), "private stage/mask contract")
        require(bool(mask.any()), "every participant requires a scored epoch; no missing-case averaging")
        checked[case.case_id] = (stage[mask].astype(np.int64), mask.copy())
    return checked


def _metrics(truth, predicted):
    # Target/probability checks already establish finite five-class vectors.
    confusion = np.bincount(5 * truth + predicted, minlength=25).reshape(5, 5)
    support, predicted_support = confusion.sum(1), confusion.sum(0)
    diagonal = np.diag(confusion)
    denominator = support + predicted_support
    f1 = np.divide(2 * diagonal, denominator, out=np.zeros(5), where=denominator > 0)
    recall = np.divide(diagonal, support, out=np.zeros(5), where=support > 0)
    return {"confusion": confusion.tolist(), "true_support": support.tolist(),
            "predicted_support": predicted_support.tolist(), "f1_by_stage": f1.tolist(),
            "recall_by_stage": [float(recall[i]) if support[i] else None for i in range(5)],
            "macro_f1_fixed_five": float(f1.mean()),
            "balanced_accuracy_supported_classes": float(recall[support > 0].mean()),
            "supported_class_count": int((support > 0).sum()), "scored_epochs": int(len(truth))}


def _score(validated, targets, spec):
    rows = []
    for case in spec.cases:
        truth, mask = targets[case.case_id]
        probability = validated["people"][case.case_id]["probabilities"]
        prediction = np.argmax(probability, axis=1)  # First index in W,N1,N2,N3,R on exact ties.
        rows.append({"person_id": case.case_id, "full_epochs": case.epochs,
                     **_metrics(truth, prediction[mask])})
    return {"per_person": rows,
            "person_mean_macro_f1": sum(r["macro_f1_fixed_five"] for r in rows) / len(rows),
            "person_mean_balanced_accuracy_supported_classes":
                sum(r["balanced_accuracy_supported_classes"] for r in rows) / len(rows)}


def _difference(candidate, comparator):
    rows = []
    for a, b in zip(candidate["per_person"], comparator["per_person"]):
        require(a["person_id"] == b["person_id"] and a["true_support"] == b["true_support"],
                "identical per-person comparison targets")
        rows.append({"person_id": a["person_id"],
                     "macro_f1_delta": a["macro_f1_fixed_five"] - b["macro_f1_fixed_five"],
                     "balanced_accuracy_delta": a["balanced_accuracy_supported_classes"] - b["balanced_accuracy_supported_classes"],
                     "f1_by_stage_delta": [x - y for x, y in zip(a["f1_by_stage"], b["f1_by_stage"])],
                     "recall_by_stage_delta": [None if x is None else x - y
                                               for x, y in zip(a["recall_by_stage"], b["recall_by_stage"])]})
    return {"direction": "candidate_minus_comparator", "per_person": rows,
            "person_mean_macro_f1_delta": candidate["person_mean_macro_f1"] - comparator["person_mean_macro_f1"],
            "person_mean_balanced_accuracy_delta": candidate["person_mean_balanced_accuracy_supported_classes"]
                - comparator["person_mean_balanced_accuracy_supported_classes"]}


def evaluate(submission_path, submission_lock, spec, target_loader, comparators):
    """Public packets pass completely before the one private target-loader call.

    comparators maps each operator-frozen comparator name to (path, trusted lock).
    target_loader is operator-owned and called with no arguments. It must enforce
    private file/lineage limits itself; candidate code is never a loader here.
    """
    checked_specification(spec)
    require(type(comparators) is dict and set(comparators) == set(spec.comparator_names),
            "all and only configured comparators required")
    candidate = validate_submission(submission_path, submission_lock, spec)
    references = {}
    for name in spec.comparator_names:
        item = comparators[name]
        require(type(item) is tuple and len(item) == 2, "comparator path/freeze pair")
        references[name] = validate_submission(item[0], item[1], spec)
    # All public submissions, identity, probability and comparator checks are done.
    targets = _checked_targets(target_loader(), spec)
    candidate_scores = _score(candidate, targets, spec)
    reference_scores = {name: _score(references[name], targets, spec) for name in spec.comparator_names}
    differences = {name: _difference(candidate_scores, reference_scores[name]) for name in spec.comparator_names}
    return {"status": "valid_descriptive_candidate_result", "class_order": list(CLASS_ORDER),
            "row_sum_atol": ROW_SUM_ATOL, "normalization_or_clipping": False,
            "argmax_tie_rule": "first_class_index", "n_people": len(spec.cases),
            "candidate": candidate_scores, "comparators": reference_scores,
            "signed_comparator_differences": differences,
            "input_freezes": {"candidate": candidate["file"],
                              "comparators": {name: references[name]["file"] for name in spec.comparator_names}},
            "binary_scientific_success_threshold": None, "population_inference": False,
            "confidence_interval": None, "p_value": None,
            "epoch_count_is_not_independent_sample_size": True,
            "exposure": "historical public development; no unseen-final or native-LLM-understanding claim"}
