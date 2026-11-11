"""Complete prediction custody before protected EEG binding.

These APIs validate actual captured bytes, not execution authority. The trusted
operator must generate the fixed reference and isolate candidate execution. A
CapturedPanel is merely a locator: comparison re-admits its entire body roster
before touching private target metadata. All accepted bytes are copied into a
fresh private archive; no caller object can skip the complete admission pass.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import math
from pathlib import PurePosixPath

from .splits import outer_cases, validate_family_plan

ARMS = ("training_mean", "eye_only", "nuisance", "nuisance_eye",
        "nuisance_dynamic", "full", "full_reverse")
RIDGE_ARMS = ("eye_only", "nuisance", "nuisance_eye", "nuisance_dynamic", "full")
MODES = ("frozen_program", "case_adaptive_equal_inputs_tools_compute")
TOOL_REGIMES = ("generic_numerical", "agent_plus_supplied_decoder")
CANDIDATE_CELLS = tuple((mode, regime) for mode in MODES for regime in TOOL_REGIMES)
CANDIDATE_KEYS = tuple(mode + "::" + regime for mode, regime in CANDIDATE_CELLS)
UNITS = "original_eeg"
TARGET_SHAPE = (127, 150)
HEADER_LIMIT = 4096
DOCUMENT_LIMIT = 4 * 1024 * 1024


@dataclass(frozen=True)
class CapturedPanel:
    """Locator only; never a credential or a bypass for body admission."""
    root: str
    manifest: dict


@dataclass(frozen=True)
class AdmittedPanel:
    """Produced by complete byte admission within compare's current attempt."""
    root: str
    manifest: dict
    document: dict
    rows: dict
    reference: dict
    candidates: dict
    fit_supports: dict


def need(condition, message):
    if not condition:
        raise ValueError(message)


def descriptor(value, maximum):
    from input_owner import descriptor as original_descriptor
    original_descriptor(value, max_bytes=maximum)
    path = value["path"]
    parsed = PurePosixPath(path)
    need(parsed.as_posix() == path and not parsed.is_absolute() and
         "\\" not in path and all(part not in ("", ".", "..") for part in path.split("/")) and
         not any(ord(char) < 32 or ord(char) == 127 for char in path),
         "Canonical local descriptor path required")
    return dict(value)


def _shape(value):
    need(type(value) in (tuple, list) and bool(value) and
         all(type(size) is int and 0 < size < 2**31 for size in value),
         "Positive explicit primitive-array shape required")
    return tuple(value)


def array_limit(shape):
    return math.prod(_shape(shape)) * 8 + HEADER_LIMIT + 12


def array_header(body, shape):
    """Validate bounded primitive NPY grammar/extent before a numeric import.

    Header parsing is a small literal-only AST. Duplicate/unknown keys, object or
    structured dtypes, Fortran layout, wrong shapes and trailing payload refuse.
    No np.load, pickle, memory map, or header-directed allocation is used.
    """
    shape = _shape(shape)
    need(type(body) is bytes and 10 <= len(body) <= array_limit(shape),
         "Explicit array extent exceeded")
    need(body[:6] == b"\x93NUMPY", "Primitive NPY magic required")
    version = tuple(body[6:8])
    if version == (1, 0):
        width, start = 2, 10
    elif version == (2, 0):
        width, start = 4, 12
    else:
        raise ValueError("Only primitive NPY versions one and two admitted")
    need(len(body) >= start, "Truncated NPY prefix")
    header_size = int.from_bytes(body[8:8 + width], "little")
    need(0 < header_size <= HEADER_LIMIT and start + header_size <= len(body),
         "Bounded complete NPY header required")
    text = body[start:start + header_size].decode("latin1")
    need(text.endswith("\n"), "Complete NPY header terminator required")
    tree = ast.parse(text.strip(), mode="eval")
    need(isinstance(tree.body, ast.Dict) and len(tree.body.keys) == 3 and
         all(isinstance(key, ast.Constant) and type(key.value) is str
             for key in tree.body.keys), "Closed NPY header dictionary required")
    keys = [key.value for key in tree.body.keys]
    need(set(keys) == {"descr", "fortran_order", "shape"} and len(set(keys)) == 3,
         "Unique exact NPY header keys required")
    header = ast.literal_eval(tree)
    need(type(header["shape"]) is tuple and _shape(header["shape"]) == shape and
         header["fortran_order"] is False,
         "Exact fixed support and C-order array required")
    dtype = header["descr"]
    need(type(dtype) is str and dtype in ("<f4", "<f8", ">f4", ">f8"),
         "Only real primitive float32/float64 predictions admitted")
    count, offset = math.prod(shape), start + header_size
    itemsize = int(dtype[-1])
    need(len(body) == offset + count * itemsize,
         "Exact primitive payload extent; no truncation or trailing body")
    return dtype, offset, count


def decode_array(body, shape, owner):
    dtype, offset, count = array_header(body, shape)
    import numpy as np
    owner.reserve("retained_bytes", count)  # finite-check boolean temporary
    result = np.frombuffer(body, dtype=dtype, count=count, offset=offset).reshape(shape)
    need(np.isfinite(result).all(), "Every full-support prediction value must be finite")
    result.flags.writeable = False
    return result


def capture_array(root, row, shape, owner):
    from input_owner import capture
    maximum = array_limit(shape)
    descriptor(row, maximum)
    body = capture(root, row, owner, max_bytes=maximum)
    decode_array(body, shape, owner)
    return body


def capture_document(root, row, owner):
    from input_owner import capture
    from io_contract import decode
    descriptor(row, DOCUMENT_LIMIT)
    body = capture(root, row, owner, max_bytes=DOCUMENT_LIMIT)
    return body, decode(body)


def _coordinates(case, value):
    expected = [[person, video] for person, video in case.query_coordinates()]
    need(type(value) is list and len(value) == len(expected) and
         all(type(row) is list and len(row) == 2 and type(row[0]) is str and
             type(row[1]) is int for row in value) and value == expected,
         "Every query coordinate in exact deterministic case order required")


def validate_reference(plan, document):
    cases = outer_cases(plan)
    need(type(document) is dict and set(document) == {
        "schema", "assignment_sha256", "units", "arms", "cases", "actual_ridge_fit_count",
        "target_manifest_identity", "historical_scope"},
        "Closed full fixed-reference panel required")
    need(document["schema"] == "neural080_reference_panel_v1" and
         document["assignment_sha256"] == plan.assignment_sha256 and
         document["units"] == UNITS and document["arms"] == list(ARMS) and
         type(document["actual_ridge_fit_count"]) is int and document["actual_ridge_fit_count"] == 39150,
         "Selected complete reference recipe, unit contract and split required")
    need(type(document["cases"]) is list and len(document["cases"]) == 30,
         "All thirty fixed-reference cases required")
    descriptor(document["target_manifest_identity"], DOCUMENT_LIMIT)
    need(type(document["historical_scope"]) is str and bool(document["historical_scope"]),
         "Explicit exposed-development reference scope required")
    case_keys = {"schema", "case_id", "assignment_sha256", "units", "query_coordinates",
                 "predictions", "target_scale", "selection", "actual_ridge_fit_count",
                 "fit_support", "preprocessing", "final_models", "resource_before",
                 "resource_after", "observed_duration", "resource_scope", "feature_backend", "full_arm_cost"}
    for case, row in zip(cases, document["cases"]):
        need(type(row) is dict and set(row) == case_keys and
             row["schema"] == "neural080_reference_case_v1" and
             row["case_id"] == case.case_id and row["assignment_sha256"] == plan.assignment_sha256 and
             row["units"] == UNITS and type(row["actual_ridge_fit_count"]) is int and
             row["actual_ridge_fit_count"] == 1305 and
             row["feature_backend"] in ("full_svd_materialized", "streamed_dual_certified") and
             row["feature_backend"] == document["cases"][0]["feature_backend"],
             "Complete ordered fixed-reference case required")
        _coordinates(case, row["query_coordinates"])
        for label in ("resource_before", "resource_after"):
            counters = row[label]
            need(type(counters) is dict and set(counters) == {
                "read_bytes", "write_bytes", "retained_bytes", "attempts"} and
                all(type(value) is int and value >= 0 for value in counters.values()),
                "Actual complete logical resource counters required")
        need(all(row["resource_after"][key] >= row["resource_before"][key]
                 for key in row["resource_before"]), "Resource counters cannot decrease")
        duration = row["observed_duration"]
        need(type(duration) is dict and set(duration) == {"monotonic_ns", "process_cpu_ns"} and
             all(type(value) is int and value >= 0 for value in duration.values()) and
             type(row["resource_scope"]) is str and bool(row["resource_scope"]),
             "Actual bounded-clock observations and their limited scope required")
        need(type(row["predictions"]) is dict and set(row["predictions"]) == set(ARMS),
             "All seven full-reference arms required")
        shape = (len(case.query_video_ids), *TARGET_SHAPE)
        for arm in ARMS:
            descriptor(row["predictions"][arm], array_limit(shape))
        scale = row["target_scale"]
        need(type(scale) is dict and set(scale) == {
            "mean", "sigma", "units", "scorer_residual_sigma_divisions"} and
            scale["units"] == UNITS and type(scale["scorer_residual_sigma_divisions"]) is int and
            scale["scorer_residual_sigma_divisions"] == 1,
            "Original-unit outer TRAIN scale and exactly one residual division required")
        for label in ("mean", "sigma"):
            descriptor(scale[label], array_limit(TARGET_SHAPE))
        need(type(row["selection"]) is dict and set(row["selection"]) == set(RIDGE_ARMS) and
             type(row["final_models"]) is dict and set(row["final_models"]) == set(RIDGE_ARMS),
             "Every selected fixed-reference ridge arm required")
        for arm in RIDGE_ARMS:
            selection = row["selection"][arm]
            need(type(selection) is dict and set(selection) == {"alpha", "risk", "ledger"} and
                 type(selection["alpha"]) in (int, float) and selection["alpha"] in
                 tuple(10.0**exponent for exponent in range(-6, 7)) and
                 type(selection["risk"]) in (int, float) and math.isfinite(selection["risk"]) and
                 selection["risk"] >= 0,
                 "Selected exact alpha, complete finite nested risk and fit ledger required")
            descriptor(selection["ledger"], 2**63 - 1)
            descriptor(row["final_models"][arm], DOCUMENT_LIMIT)
        descriptor(row["full_arm_cost"], DOCUMENT_LIMIT)
        descriptor(row["fit_support"], DOCUMENT_LIMIT)
        descriptor(row["preprocessing"], DOCUMENT_LIMIT)
    return document


def validate_candidate(plan, mode, regime, document):
    need(mode in MODES and regime in TOOL_REGIMES and type(document) is dict and set(document) == {
        "schema", "assignment_sha256", "access_mode", "tool_regime", "units", "cases"} and
        document["schema"] == "neural080_candidate_panel_v1" and
        document["assignment_sha256"] == plan.assignment_sha256 and
        document["access_mode"] == mode and document["tool_regime"] == regime and
        document["units"] == UNITS,
        "Closed complete candidate panel with original EEG units required")
    need(type(document["cases"]) is list and len(document["cases"]) == 30,
         "Every one of thirty candidate FULL cases required")
    for case, row in zip(outer_cases(plan), document["cases"]):
        need(type(row) is dict and set(row) == {"case_id", "query_coordinates", "prediction"} and
             row["case_id"] == case.case_id, "Exact ordered candidate case required")
        _coordinates(case, row["query_coordinates"])
        descriptor(row["prediction"], array_limit((len(case.query_video_ids), *TARGET_SHAPE)))
    return document


def validate_fit_support(plan, case, document):
    """Bind actual reference TRAIN values to their exact row coordinates."""
    keys = {"assignment_sha256", "coordinates", "query_coordinates", "target_values_identity",
            "feature_values_identity", "weighting", "weights", "original_preprocessing"}
    coordinates = tuple(case.training_coordinates())
    need(type(document) is dict and set(document) == keys and
         document["assignment_sha256"] == plan.assignment_sha256 and
         document["weighting"] == "equal_person_then_genuine_family_then_video",
         "Exact complete reference fit-support body required")
    supplied = document["coordinates"]
    need(type(supplied) is list and all(type(row) is list and len(row) == 2 and
         type(row[0]) is str and type(row[1]) is int for row in supplied) and
         supplied == [list(row) for row in coordinates], "Every actual ordered outer TRAIN row required")
    _coordinates(case, document["query_coordinates"])
    identity = document["target_values_identity"]
    need(type(identity) is dict and set(identity) == {"dtype", "shape", "order", "value_bytes", "value_sha256"} and
         identity["dtype"] in ("<f8", ">f8") and identity["order"] == "C" and
         _shape(identity["shape"]) == (len(coordinates), *TARGET_SHAPE) and
         type(identity["value_bytes"]) is int and identity["value_bytes"] == len(coordinates) * 127 * 150 * 8 and
         type(identity["value_sha256"]) is str and len(identity["value_sha256"]) == 64 and
         all(char in "0123456789abcdef" for char in identity["value_sha256"]),
         "Actual complete contiguous float64 TRAIN value identity required")
    need(type(document["feature_values_identity"]) is dict and bool(document["feature_values_identity"]) and
         type(document["original_preprocessing"]) is str and bool(document["original_preprocessing"]),
         "Captured complete feature identity and original preprocessing disclosure required")
    descriptor(document["weights"], array_limit((len(coordinates),)))
    return document


def expected_roles(plan):
    """Canonical complete archive roles; names are never supplied by candidates."""
    roles = []
    for case in outer_cases(plan):
        shape = (len(case.query_video_ids), *TARGET_SHAPE)
        for arm in ARMS:
            roles.append((case.case_id, "reference:" + arm, shape))
        for key in CANDIDATE_KEYS:
            roles.append((case.case_id, "candidate:" + key, shape))
        for label in ("mean", "sigma"):
            roles.append((case.case_id, "scale:" + label, TARGET_SHAPE))
    return tuple(roles)


def _archive_name(index):
    return "operand-%04d.npy" % index


def _source_name(index):
    return "source-panel-%02d.json" % index


def capture_panel(plan, reference_root, reference_manifest, candidates, output, owner, *,
                  target_manifest_identity):
    """Capture complete fixed-reference/candidate panels, with NO target operand.

    candidates maps each canonical mode+"::"+tool_regime key to {root, manifest}.
    Its four isolated full-case panels must already have completed under the actual operator.
    Full fit/model custody stays in the fixed-reference output directory; this
    archive preserves the exact panel manifests, predictions and target scales.
    """
    from input_owner import Writer
    record = owner.begin("capture_complete_generalization_prediction_panel")
    answer = None
    try:
        validate_family_plan(plan)
        need(type(candidates) is dict and set(candidates) == set(CANDIDATE_KEYS),
             "All four canonical access-mode/tool-regime panels required")
        target_identity = descriptor(target_manifest_identity, DOCUMENT_LIMIT)
        writer = Writer(output, owner)
        source_rows = []
        reference_body, reference = capture_document(reference_root, reference_manifest, owner)
        validate_reference(plan, reference)
        need(reference["target_manifest_identity"] == target_identity,
             "Fixed reference must bind the exact same private target pool identity")
        source_rows.append({"role": "reference", "original": dict(reference_manifest),
                            "captured": writer.put(_source_name(0), reference_body)})
        candidate_docs = {}
        for index, ((mode, regime), key) in enumerate(zip(CANDIDATE_CELLS, CANDIDATE_KEYS), 1):
            operand = candidates[key]
            need(type(operand) is dict and set(operand) == {"root", "manifest"},
                 "Exact candidate archive locator required")
            body, document = capture_document(operand["root"], operand["manifest"], owner)
            candidate_docs[key] = validate_candidate(plan, mode, regime, document)
            source_rows.append({"role": "candidate:" + key, "original": dict(operand["manifest"]),
                                "captured": writer.put(_source_name(index), body)})
        fit_supports = []
        for index, case in enumerate(outer_cases(plan)):
            original = reference["cases"][index]["fit_support"]
            body, support = capture_document(reference_root, original, owner)
            validate_fit_support(plan, case, support)
            fit_supports.append({"case_id": case.case_id, "original": dict(original),
                "captured": writer.put("fit-support-%02d.json" % index, body)})
        rows = []
        role_index = 0
        for index, case in enumerate(outer_cases(plan)):
            operands = [("reference:" + arm, reference_root,
                         reference["cases"][index]["predictions"][arm]) for arm in ARMS]
            operands += [("candidate:" + key, candidates[key]["root"],
                          candidate_docs[key]["cases"][index]["prediction"]) for key in CANDIDATE_KEYS]
            operands += [("scale:" + label, reference_root,
                          reference["cases"][index]["target_scale"][label]) for label in ("mean", "sigma")]
            for role, root, original in operands:
                shape = TARGET_SHAPE if role.startswith("scale:") else (
                    len(case.query_video_ids), *TARGET_SHAPE)
                body = capture_array(root, original, shape, owner)
                if role == "scale:sigma":
                    sigma = decode_array(body, shape, owner)
                    need((sigma > 0).all(), "Every full-support TRAIN sigma must be positive")
                rows.append({"case_id": case.case_id, "role": role, "shape": list(shape),
                             "original": dict(original),
                             "captured": writer.put(_archive_name(role_index), body)})
                role_index += 1
        document = {"schema": "neural080_captured_prediction_panel_v1",
                    "assignment_sha256": plan.assignment_sha256, "units": UNITS,
                    "target_manifest_identity": target_identity,
                    "arms": list(ARMS), "access_modes": list(MODES),
                    "tool_regimes": list(TOOL_REGIMES),
                    "source_manifests": source_rows, "fit_supports": fit_supports, "arrays": rows,
                    "complete_array_count": len(expected_roles(plan)),
                    "target_access_during_capture": "none",
                    "scope": "Byte custody only; source authenticity, candidate isolation, reference competence and freshness remain external gates"}
        manifest = writer.document("CAPTURED_PANEL.json", document)
        answer = CapturedPanel(str(writer.root), manifest)
    except BaseException as exc:
        owner.failure(record, exc)
    owner.complete(record)
    return answer


def admit_panel(plan, panel, owner):
    """Re-admit ALL archive bodies before compare opens any target binding.

    A manually constructed CapturedPanel follows this exact same full path. The
    source manifests, every role, fixed shape, descriptor and original-unit
    contract are joined again. This does not attest external experiment conduct.
    """
    record = owner.begin("readmit_complete_prediction_archive_before_targets")
    answer = None
    try:
        validate_family_plan(plan)
        need(type(panel) is CapturedPanel, "Explicit captured-panel locator required")
        _, document = capture_document(panel.root, panel.manifest, owner)
        keys = {"schema", "assignment_sha256", "units", "arms", "access_modes", "tool_regimes",
                "source_manifests", "fit_supports", "arrays", "complete_array_count",
                "target_access_during_capture", "scope", "target_manifest_identity"}
        need(type(document) is dict and set(document) == keys and
             document["schema"] == "neural080_captured_prediction_panel_v1" and
             document["assignment_sha256"] == plan.assignment_sha256 and
             document["units"] == UNITS and document["arms"] == list(ARMS) and
             document["access_modes"] == list(MODES) and
             document["tool_regimes"] == list(TOOL_REGIMES) and
             document["target_access_during_capture"] == "none" and
             type(document["complete_array_count"]) is int and
             document["complete_array_count"] == len(expected_roles(plan)),
             "Complete exact prediction archive required before private targets")
        descriptor(document["target_manifest_identity"], DOCUMENT_LIMIT)
        source_roles = ("reference", *("candidate:" + key for key in CANDIDATE_KEYS))
        sources = document["source_manifests"]
        need(type(sources) is list and len(sources) == len(source_roles),
             "All original source-panel manifests required")
        docs = {}
        for index, (role, row) in enumerate(zip(source_roles, sources)):
            need(type(row) is dict and set(row) == {"role", "original", "captured"} and
                 row["role"] == role and row["captured"]["path"] == _source_name(index),
                 "Exact canonical source-panel archive role required")
            descriptor(row["original"], DOCUMENT_LIMIT)
            body, source = capture_document(panel.root, row["captured"], owner)
            need(row["original"]["bytes"] == len(body) and
                 row["original"]["sha256"] == hashlib.sha256(body).hexdigest(),
                 "Archived panel must retain exact original source bytes")
            docs[role] = (validate_reference(plan, source) if role == "reference" else
                          validate_candidate(plan, *role.split(":", 1)[1].split("::"), source))
        need(docs["reference"]["target_manifest_identity"] == document["target_manifest_identity"],
             "Archived fixed reference and protected target identity must agree")
        support_rows = document["fit_supports"]
        need(type(support_rows) is list and len(support_rows) == 30,
             "All thirty actual TRAIN value-identity bodies required before targets")
        fit_supports = {}
        for index, (case, row) in enumerate(zip(outer_cases(plan), support_rows)):
            need(type(row) is dict and set(row) == {"case_id", "original", "captured"} and
                 row["case_id"] == case.case_id and row["captured"]["path"] == "fit-support-%02d.json" % index and
                 row["original"] == docs["reference"]["cases"][index]["fit_support"],
                 "Exact original fit-support archive join required")
            body, support = capture_document(panel.root, row["captured"], owner)
            need(len(body) == row["original"]["bytes"] and
                 hashlib.sha256(body).hexdigest() == row["original"]["sha256"],
                 "Retained exact original reference fit-support body required")
            fit_supports[case.case_id] = validate_fit_support(plan, case, support)
        expected = expected_roles(plan)
        need(type(document["arrays"]) is list and len(document["arrays"]) == len(expected),
             "No missing, additional, repeated or partial prediction roles")
        rows = {}
        cases = {case.case_id: index for index, case in enumerate(outer_cases(plan))}
        for index, ((case_id, role, shape), row) in enumerate(zip(expected, document["arrays"])):
            need(type(row) is dict and set(row) == {"case_id", "role", "shape", "original", "captured"} and
                 row["case_id"] == case_id and row["role"] == role and
                 _shape(row["shape"]) == shape and row["captured"]["path"] == _archive_name(index),
                 "Exact ordered archive array role required")
            case_index = cases[case_id]
            if role.startswith("reference:"):
                original = docs["reference"]["cases"][case_index]["predictions"][role.split(":", 1)[1]]
            elif role.startswith("candidate:"):
                original = docs[role]["cases"][case_index]["prediction"]
            else:
                original = docs["reference"]["cases"][case_index]["target_scale"][role.split(":", 1)[1]]
            need(row["original"] == original, "Archive operand must join its captured source manifest")
            body = capture_array(panel.root, row["captured"], shape, owner)
            need(original["bytes"] == len(body) and original["sha256"] == hashlib.sha256(body).hexdigest(),
                 "Exact original prediction/scale body required")
            if role == "scale:sigma":
                need((decode_array(body, shape, owner) > 0).all(),
                     "Exact nonconstant positive full-support scale required")
            rows[(case_id, role)] = row
        answer = AdmittedPanel(panel.root, dict(panel.manifest), document, rows,
                               docs["reference"], {key: docs["candidate:" + key] for key in CANDIDATE_KEYS},
                               fit_supports)
    except BaseException as exc:
        owner.failure(record, exc)
    owner.complete(record)
    return answer


def read_operand(admitted, case_id, role, owner):
    """Recapture the same admitted bytes; any later archive mutation refuses."""
    need(type(admitted) is AdmittedPanel, "Within-comparison admitted panel required")
    row = admitted.rows[(case_id, role)]
    shape = tuple(row["shape"])
    body = capture_array(admitted.root, row["captured"], shape, owner)
    return decode_array(body, shape, owner)
