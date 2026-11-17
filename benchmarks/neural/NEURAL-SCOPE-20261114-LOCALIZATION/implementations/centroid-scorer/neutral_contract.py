"""Source-only, normalized Localization projection and complete-support scoring.

This module does not read archives, deserialize scientific objects, infer source
roles, copy arrays or launch predictions. A reviewed owner normalizer must supply
the exact schema below. Validation of a declared hash/role is not authentication
of scientific bytes; the intake and isolation gates in OPERATION_PROPOSAL apply.
"""

import hashlib
import json
import math
import re
import statistics
from collections import defaultdict


TASK = "NEURAL-SCOPE-20261114-LOCALIZATION"
HEX = re.compile(r"[0-9a-f]{64}\Z")
OPAQUE = re.compile(r"[0-9a-f]{32}\Z")
ROLES = {"waveforms", "template", "probe_geometry", "observed_support"}
METHODS = {"center_of_mass", "monopolar_triangulation", "grid_convolution"}


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def exact(value, keys, name):
    require(type(value) is dict and set(value) == set(keys), name + ": keys")


def opaque(value):
    require(type(value) is str and OPAQUE.fullmatch(value), "opaque identifier")
    return value


def digest(value):
    require(type(value) is str and HEX.fullmatch(value), "sha256")
    return value


def finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, ValueError):
        return False


def number(value):
    require(finite_number(value), "finite representable number")
    return value


def distance_or_none(left, right):
    """No clipping: an unrepresentable distance is a typed null diagnostic."""
    try:
        value = math.hypot(*(a - b for a, b in zip(left, right)))
    except (OverflowError, ValueError):
        return None
    return value if finite_number(value) else None


def nonnegative_median(values):
    """Finite distance median without the overflowing (low + high) / 2."""
    ordered = sorted(values)
    require(ordered and all(finite_number(x) and x >= 0 for x in ordered),
            "finite nonnegative median support")
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    low, high = ordered[middle - 1], ordered[middle]
    return low + (high - low) / 2


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def unique_ids(values, count=None):
    require(type(values) is list, "identifier list")
    result = [opaque(x) for x in values]
    require(len(set(result)) == len(result), "duplicate identifier")
    if count is not None:
        require(len(result) == count, "incomplete fixed cohort dimension")
    return result


def validate_neural(owner):
    """Validate the whole normalized neural side without reading reference values.

    Owner provenance and targets are deliberately a separate argument to scoring,
    so target mutations cannot affect this function or the public manifest hash.
    Original cell/seed/condition labels and all archive paths stay outside it.
    """
    exact(owner, {"schema", "task_id", "axis_names", "coordinate_unit",
                  "cells", "conditions", "realizations", "artifacts", "cases"},
          "neural manifest")
    require(owner["schema"] == "localization-normalized-neural-v1", "schema")
    require(owner["task_id"] == TASK, "task")
    require(owner["coordinate_unit"] == "um", "coordinate unit")
    axes = owner["axis_names"]
    require(type(axes) is list and len(axes) == 2 and len(set(axes)) == 2
            and all(type(x) is str and re.fullmatch(r"[xyz]", x) for x in axes),
            "two verified ordered probe axes")
    cells = unique_ids(owner["cells"], 11)
    conditions = unique_ids(owner["conditions"], 16)
    realizations = unique_ids(owner["realizations"], 5)
    require(type(owner["artifacts"]) is list, "artifact list")
    artifacts = {}
    for art in owner["artifacts"]:
        exact(art, {"sha256", "bytes", "role", "dtype", "shape"}, "artifact")
        h = digest(art["sha256"])
        require(h not in artifacts, "duplicate artifact digest")
        require(type(art["bytes"]) is int and art["bytes"] > 0, "artifact bytes")
        require(art["role"] in ROLES, "unadmitted artifact role")
        # Owner normalizer emits only primitive numeric/bool .npy files, never
        # object/structured arrays or pickles. Dtype is a protocol value, not an
        # inference about the unaudited archive header.
        require(art["dtype"] in {"<f4", "<f8", "<i4", "<i8", "|b1"}, "dtype")
        require(type(art["shape"]) is list and 1 <= len(art["shape"]) <= 3
                and all(type(n) is int and n > 0 for n in art["shape"]), "shape")
        artifacts[h] = art
    require(type(owner["cases"]) is list and len(owner["cases"]) == 880,
            "all 11 x 16 x 5 cases required")
    cases, tuples, all_rows, used = {}, set(), set(), set()
    for case in owner["cases"]:
        exact(case, {"case_id", "cell_id", "condition_id", "realization_id",
                     "sampling_frequency_hz", "voltage_unit", "sample_offsets",
                     "channel_ids", "inputs", "requests"}, "case")
        cid = opaque(case["case_id"])
        require(cid not in cases, "duplicate case")
        triplet = (case["cell_id"], case["condition_id"], case["realization_id"])
        require(triplet[0] in cells and triplet[1] in conditions
                and triplet[2] in realizations and triplet not in tuples, "case grid")
        tuples.add(triplet)
        require(number(case["sampling_frequency_hz"]) > 0, "sampling frequency")
        require(case["voltage_unit"] == "uV", "waveforms must be normalized to uV")
        offsets = case["sample_offsets"]
        require(type(offsets) is list and len(offsets) > 0
                and all(type(x) is int for x in offsets)
                and offsets == list(range(offsets[0], offsets[0] + len(offsets))),
                "complete contiguous waveform sample offsets")
        channel_ids = unique_ids(case["channel_ids"])
        require(channel_ids, "empty channel support")
        exact(case["inputs"], ROLES, "case inputs")
        for role, h in case["inputs"].items():
            require(h in artifacts and artifacts[h]["role"] == role, "input binding")
            used.add(h)
        shape = lambda role: artifacts[case["inputs"][role]]["shape"]
        require(shape("probe_geometry") == [len(channel_ids), 2], "geometry shape")
        require(shape("template") == [len(offsets), len(channel_ids)], "template shape")
        require(shape("observed_support") == [len(channel_ids)], "observed support shape")
        require(artifacts[case["inputs"]["observed_support"]]["dtype"] == "|b1",
                "observed support is boolean, not a private degradation mask")
        require(type(case["requests"]) is list and case["requests"], "request list")
        spike_indices, templates = [], 0
        for row in case["requests"]:
            exact(row, {"request_id", "kind", "array_index"}, "request")
            rid = opaque(row["request_id"])
            require(rid not in all_rows, "duplicate request identity")
            all_rows.add(rid)
            require(type(row["array_index"]) is int, "array index")
            if row["kind"] == "spike":
                spike_indices.append(row["array_index"])
            else:
                require(row["kind"] == "template" and row["array_index"] == 0,
                        "template request")
                templates += 1
        require(templates == 1 and spike_indices
                and sorted(spike_indices) == list(range(len(spike_indices))),
                "one template and every admitted waveform row exactly once")
        require(shape("waveforms") == [len(spike_indices), len(offsets), len(channel_ids)],
                "waveform shape/support join")
        cases[cid] = case
    require(used == set(artifacts), "unreferenced artifact")
    return cases


def project(neural):
    """Return a logical target-free manifest. No files are copied by this API.

    SHA-named files must later be copied and authenticated by a separately reviewed
    owner in an empty isolated workspace. A logical allowlist alone is not isolation.
    """
    cases = validate_neural(neural)
    # Reconstruct every field; never copy arbitrary owner dictionaries wholesale.
    result = {"schema": "localization-participant-v1", "task_id": TASK,
              "axis_names": list(neural["axis_names"]), "coordinate_unit": "um",
              "artifacts": [], "cases": []}
    for a in sorted(neural["artifacts"], key=lambda a: a["sha256"]):
        result["artifacts"].append({k: a[k] for k in
                                   ("sha256", "bytes", "role", "dtype", "shape")})
        result["artifacts"][-1]["path"] = "inputs/" + a["sha256"] + ".npy"
    for cid in sorted(cases):
        c = cases[cid]
        result["cases"].append({
            "case_id": cid, "condition_id": c["condition_id"],
            "sampling_frequency_hz": c["sampling_frequency_hz"],
            "voltage_unit": "uV", "sample_offsets": list(c["sample_offsets"]),
            "channel_ids": list(c["channel_ids"]),
            "inputs": dict(c["inputs"]),
            "requests": [dict(r) for r in c["requests"]]})
    return result


def fixed_seed(neural, case_id, condition_id, method=None, kind=None):
    """Derive V3 seed only from the strict normalized neural projection.

    Arbitrary caller-supplied participant dictionaries are not accepted. project
    rejects every extra owner/target/cache field at all admitted schema levels
    before any hash is computed. The base manifest must precede newly made noise.
    """
    public_manifest = project(neural)
    digest_value = hashlib.sha256(canonical(public_manifest)).hexdigest()
    require(any(c["case_id"] == case_id and c["condition_id"] == condition_id
                for c in public_manifest["cases"]), "unknown seed case")
    fields = ["localization-fixed-attempt-v1", digest_value, case_id, condition_id]
    if method is None and kind is None:
        fields.append("input_noise")
    else:
        require(method in METHODS and kind in {"spike", "template"}, "seed method/kind")
        fields.extend([method, kind, "predictor"])
    # V3 seed serialization is compact ASCII JSON array, not a Python hash.
    return int(hashlib.sha256(canonical(fields)).hexdigest()[:8], 16)


def score(neural, reference, submission, frozen_program_sha256):
    """Owner-only strict <50 um scoring on full support, or no headline score.

    Any absent/extra/duplicate/invalid output is a protocol failure. Full requested
    denominators and valid-row error diagnostics remain, but no reduced-support
    primary score is emitted. This is the new group-balanced comparator, not the
    original paper's pooled-spike/seed result or a claim of native reproduction.
    """
    cases = validate_neural(neural)
    exact(reference, {"schema", "coordinate_unit", "axis_names", "reference_kind",
                      "reference_evidence_sha256", "group_evidence_sha256",
                      "undegraded_condition_id", "cells"},
          "private reference")
    require(reference["schema"] == "localization-owner-reference-v1", "reference schema")
    require(reference["coordinate_unit"] == "um"
            and reference["axis_names"] == neural["axis_names"], "reference axes/units")
    require(reference["reference_kind"] == "nearest_contact_proxy", "reference kind")
    digest(reference["reference_evidence_sha256"])
    digest(reference["group_evidence_sha256"])
    require(reference["undegraded_condition_id"] in neural["conditions"],
            "source-adjudicated undegraded condition")
    require(type(reference["cells"]) is list, "reference cells")
    ref = {}
    for cell in reference["cells"]:
        exact(cell, {"cell_id", "recording_id", "animal_id", "coordinate_um"}, "reference cell")
        cid = opaque(cell["cell_id"])
        require(cid not in ref, "duplicate reference cell")
        opaque(cell["recording_id"]); opaque(cell["animal_id"])
        require(type(cell["coordinate_um"]) is list and len(cell["coordinate_um"]) == 2,
                "reference coordinate")
        for value in cell["coordinate_um"]:
            number(value)
        ref[cid] = cell
    require(set(ref) == set(neural["cells"]), "incomplete reference/group support")
    recordings = {}
    for cell in ref.values():
        rid = cell["recording_id"]
        require(rid not in recordings or recordings[rid] == cell["animal_id"],
                "recording crosses animals")
        recordings[rid] = cell["animal_id"]
    exact(submission, {"schema", "program_sha256", "coordinate_unit", "axis_names", "rows"},
          "submission")
    require(submission["schema"] == "localization-predictions-v1", "submission schema")
    require(digest(submission["program_sha256"]) == digest(frozen_program_sha256),
            "program differs from owner-frozen program")
    require(submission["coordinate_unit"] == "um"
            and submission["axis_names"] == neural["axis_names"], "submission axes/units")
    require(type(submission["rows"]) is list, "prediction rows")
    expected = {r["request_id"]: (c, r) for c in cases.values() for r in c["requests"]}
    supplied, issues = {}, []
    for row in submission["rows"]:
        if type(row) is not dict or set(row) != {"request_id", "case_id", "status", "coordinate_um"}:
            issues.append("malformed_row"); continue
        rid = row["request_id"]
        if type(rid) is not str or rid not in expected:
            issues.append("extra_row"); continue
        if rid in supplied:
            issues.append("duplicate_row:" + rid)
            supplied[rid] = None
            continue
        supplied[rid] = row
    records, bins, per_case_bins, template_predictions = [], defaultdict(list), defaultdict(list), {}
    diagnostic_issues = []
    for rid, (case, request) in expected.items():
        row = supplied.get(rid)
        valid = (row is not None and row["case_id"] == case["case_id"]
                 and row["status"] == "ok"
                 and type(row["coordinate_um"]) is list and len(row["coordinate_um"]) == 2
                 and all(finite_number(x) for x in row["coordinate_um"]))
        distance = None
        if valid:
            target = ref[case["cell_id"]]["coordinate_um"]
            distance = distance_or_none(row["coordinate_um"], target)
            valid = distance is not None
        if not valid:
            distance = None
            issues.append("missing_or_invalid:" + rid)
        rec = {"request_id": rid, "case_id": case["case_id"], "kind": request["kind"],
               "valid": bool(valid), "error_um": distance,
               "correct_lt_50um": bool(valid and distance < 50)}
        records.append(rec)
        bins[(case["cell_id"], case["condition_id"], request["kind"])].append(rec)
        per_case_bins[(case["case_id"], request["kind"])].append(rec)
        if request["kind"] == "template":
            template_predictions[(case["cell_id"], case["condition_id"], case["realization_id"])] = (
                list(row["coordinate_um"]) if valid else None)
    per_case = []
    for (cid, kind), rows in sorted(per_case_bins.items()):
        c = cases[cid]
        per_case.append({"case_id": cid, "cell_id": c["cell_id"],
                         "condition_id": c["condition_id"], "realization_id": c["realization_id"],
                         "kind": kind, "requested": len(rows), "valid": sum(r["valid"] for r in rows),
                         "correct": sum(r["correct_lt_50um"] for r in rows)})
    stability = []
    for (cell, condition, realization), estimate in sorted(template_predictions.items()):
        base = template_predictions[(cell, reference["undegraded_condition_id"], realization)]
        available = estimate is not None and base is not None
        distance = distance_or_none(estimate, base) if available else None
        stability_status = ("finite" if distance is not None else
                            "unrepresentable_distance" if available else "invalid_prediction_support")
        if stability_status == "unrepresentable_distance":
            diagnostic_issues.append({"kind": "unrepresentable_template_stability",
                                      "cell_id": cell, "condition_id": condition,
                                      "realization_id": realization})
        stability.append({"cell_id": cell, "condition_id": condition, "realization_id": realization,
                          "status": stability_status,
                          "distance_from_own_undegraded_template_um": distance,
                          "interpretation": "estimator stability only; not measured biological drift"})
    per_cell, group_bins = [], defaultdict(list)
    for (cell, condition, kind), rows in sorted(bins.items()):
        valid = [r for r in rows if r["valid"]]
        complete = len(valid) == len(rows)
        accuracy = sum(r["correct_lt_50um"] for r in rows) / len(rows)
        median = nonnegative_median(r["error_um"] for r in valid) if complete else None
        entry = {"cell_id": cell, "condition_id": condition, "kind": kind,
                 "requested": len(rows), "valid": len(valid),
                 "accuracy_full_denominator": accuracy,
                 "median_error_um_complete_support_only": median}
        per_cell.append(entry)
        r = ref[cell]
        group_bins[(condition, kind, r["animal_id"], r["recording_id"])].append(entry)
    # Equal cells within recording, equal recordings within animal, equal animals.
    animal_bins = defaultdict(list)
    for (condition, kind, animal, recording), rows in sorted(group_bins.items()):
        animal_bins[(condition, kind, animal)].append({
            "accuracy": statistics.mean(r["accuracy_full_denominator"] for r in rows),
            "median_error": (statistics.mean(r["median_error_um_complete_support_only"] for r in rows)
                             if all(r["median_error_um_complete_support_only"] is not None for r in rows) else None)})
    per_animal, condition_bins = [], defaultdict(list)
    for (condition, kind, animal), rows in sorted(animal_bins.items()):
        entry = {"condition_id": condition, "kind": kind, "animal_id": animal,
                 "accuracy": statistics.mean(r["accuracy"] for r in rows),
                 "mean_cell_median_error_um": (statistics.mean(r["median_error"] for r in rows)
                     if all(r["median_error"] is not None for r in rows) else None)}
        per_animal.append(entry); condition_bins[(condition, kind)].append(entry)
    curves = []
    for (condition, kind), rows in sorted(condition_bins.items()):
        curves.append({"condition_id": condition, "kind": kind,
                       "animal_macro_accuracy": statistics.mean(r["accuracy"] for r in rows),
                       "animal_macro_mean_cell_median_error_um":
                           (statistics.mean(r["mean_cell_median_error_um"] for r in rows)
                            if all(r["mean_cell_median_error_um"] is not None for r in rows) else None)})
    return {"schema": "localization-private-score-v1", "reference_kind": "nearest_contact_proxy",
            "status": "PROTOCOL_FAILURE" if issues else "COMPLETE_SUPPORT_SCORE",
            "requested": len(expected), "valid": sum(r["valid"] for r in records),
            "issues": issues, "diagnostic_issues": diagnostic_issues,
            "row_diagnostics": records, "per_case": per_case,
            "template_stability": stability, "per_cell_condition": per_cell,
            "per_animal_condition": per_animal, "per_condition": curves,
            "primary_spike_macro_accuracy": None if issues else statistics.mean(
                r["animal_macro_accuracy"] for r in curves if r["kind"] == "spike"),
            "template_macro_accuracy": None if issues else statistics.mean(
                r["animal_macro_accuracy"] for r in curves if r["kind"] == "template"),
            "native_paper_parity": False, "scientific_qualification": False}
