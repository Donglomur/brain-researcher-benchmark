"""Descriptive paired Figure 3C comparison; no scientific admission or fitting."""
from __future__ import annotations

import hashlib
import importlib.util
import math
from pathlib import Path

PINS = {
    "protocol.py": "7831de842c3df36fd4ea36ce135a27def12372929f3f00c3c627ccaf5399b6ac",
    "submissions.py": "3f8a56b4b218b2ada59d6c7ffb74f6958a0c8ae23495488a50dc74bfd8bb71e3",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


class Source:
    """Load the unchanged prediction interface from a trusted operator checkout."""

    def __init__(self, interface_directory=None):
        directory = (Path(interface_directory) if interface_directory else
                     Path(__file__).resolve().parent.parent / "prediction-interface-v1")
        for name, expected in PINS.items():
            path = directory / name
            with path.open("rb") as stream:
                raw = stream.read(65537)
            require(len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == expected,
                    "original interface identity mismatch: " + name)
            spec = importlib.util.spec_from_file_location("temporal026_pair_" + path.stem, path)
            module = importlib.util.module_from_spec(spec)
            exec(compile(raw, str(path), "exec"), module.__dict__)
            setattr(self, path.stem, module)


def _difference(reference, candidate):
    if (type(reference) in (float, int) and type(candidate) in (float, int)
            and math.isfinite(reference) and math.isfinite(candidate)):
        return candidate - reference
    return None


def _index(rows, key, expected, description):
    names = [key(row) for row in rows]
    require(names == expected, "complete ordered " + description + " support required")
    return {key(row): row for row in rows}


def _pair(reference, candidate, context):
    """Pair internally evaluated results. Not an intake API for claimed scores."""
    jobs = context["jobs"]
    expected_cv = [job["id"] for job in jobs if job["mode"] == "cv"]
    ref_cells = _index(reference["cv_cells"], lambda r: r["job_id"], expected_cv, "CV")
    cand_cells = _index(candidate["cv_cells"], lambda r: r["job_id"], expected_cv, "CV")
    cv = []
    for job_id in expected_cv:
        left, right = ref_cells[job_id], cand_cells[job_id]
        a, b = left.get("condition_r2"), right.get("condition_r2")
        raw_delta = ([_difference(x["value"], y["value"]) for x, y in zip(a, b)]
                     if a is not None and b is not None and len(a) == len(b) == 6 else [None] * 6)
        a, b = left.get("rounded_condition_r2"), right.get("rounded_condition_r2")
        rounded_delta = ([_difference(x, y) for x, y in zip(a, b)]
                         if a is not None and b is not None and len(a) == len(b) == 6 else [None] * 6)
        cv.append({"job_id": job_id, "reference_status": left["status"],
                   "candidate_status": right["status"], "condition_r2_delta": raw_delta,
                   "rounded_condition_r2_delta": rounded_delta,
                   "fold_r2_delta": _difference(left["fold_r2"], right["fold_r2"])})
    expected_electrodes = [(row["electrode_id"], scaling)
                           for row in context["items"].values()
                           for scaling in context["plan"]["scalings"]]
    key = lambda r: (r["id"], r["scaling"])
    left = _index(reference["electrode_cv"], key, expected_electrodes, "electrode")
    right = _index(candidate["electrode_cv"], key, expected_electrodes, "electrode")
    electrodes = []
    for identity in expected_electrodes:
        a, b = left[identity], right[identity]
        require(all(a[k] == b[k] for k in ("id", "subject", "varea", "scaling")),
                "electrode identity mismatch")
        electrodes.append({k: a[k] for k in ("id", "subject", "varea", "scaling")} |
                          {"r2_delta": _difference(a["r2"], b["r2"])})
    expected_regions = [(region, scaling) for region in ("V1-V3", "VOTC", "LOTC")
                        for scaling in context["plan"]["scalings"]]
    key = lambda r: (r["region"], r["scaling"])
    left = _index(reference["figure3_regional_cv"], key, expected_regions, "regional")
    right = _index(candidate["figure3_regional_cv"], key, expected_regions, "regional")
    regions = []
    for identity in expected_regions:
        a, b = left[identity], right[identity]
        require(a["electrodes"] == b["electrodes"] and a["participants"] == b["participants"],
                "regional identity mismatch")
        regions.append({"region": identity[0], "scaling": identity[1],
                        "reference_status": a["status"], "candidate_status": b["status"],
                        "descriptive_median_delta": _difference(a.get("median"), b.get("median"))})
    return {"cv_cells": cv, "electrodes": electrodes, "regions": regions}


def compare(reference_directory, reference_protocol, reference_manifest_sha256,
            candidate_directory, candidate_protocol, candidate_manifest_sha256,
            input_root, bootstrap_seed, source=None):
    """Evaluate two complete committed panels against one identical protected bank.

    The reference is an operator-selected prediction store, not an authenticated
    original author result merely because it occupies this argument. Both methods
    must have the same plan, original support, source implementation and declared
    assistance condition. Run separate pairs for the two assistance conditions.
    """
    source = source or Source()
    # Validate both frozen complete plans before either evaluator may open targets.
    ref_context = source.submissions._context(reference_protocol)
    source.submissions._context(candidate_protocol)
    a, b = reference_protocol.descriptor, candidate_protocol.descriptor
    common = ("schema", "plan_sha256", "manifest_sha256", "condition", "cv_column_branch",
              "source_producer_sha256", "source_replay_sha256", "source_cohort_sha256",
              "counts", "source_coordinate_order_sha256", "delivery_order_sha256", "delivery_policy")
    require(all(a[k] == b[k] for k in common),
            "paired methods require identical original plan, folds, inputs and assistance condition")
    require(type(bootstrap_seed) is int and 0 <= bootstrap_seed < 2**32,
            "prospective bootstrap seed required")
    reference = source.submissions.evaluate(reference_directory, reference_protocol,
                                           reference_manifest_sha256, input_root, bootstrap_seed)
    candidate = source.submissions.evaluate(candidate_directory, candidate_protocol,
                                           candidate_manifest_sha256, input_root, bootstrap_seed)
    return {
        "schema": "temporal026-complete-paired-comparison/v1",
        "plan_sha256": a["plan_sha256"], "condition": a["condition"],
        "source_branch": a["cv_column_branch"], "counts": a["counts"],
        "source_interface_sha256": dict(PINS),
        "reference": reference, "candidate": candidate,
        "paired_candidate_minus_reference": _pair(reference, candidate, ref_context),
        "primary_author_comparison_slot": "S",
        "same_method_identity": a["method_sha256"] == b["method_sha256"],
        "scientific_qualification": False, "reproduction_decision": "unresolved",
        "improvement_decision": "unresolved",
        "limits": [
            "Reference role does not authenticate original author execution or published-result calibration.",
            "Source none/S slots are comparison labels, not proof of candidate architecture.",
            "Both full 2054-coordinate stores, all failures, 158 electrode scores and six regional summaries are retained.",
            "Differences are descriptive; no aggregate scalar, win count, superiority threshold or paired uncertainty is supplied.",
            "Source electrode-bootstrap intervals remain within-method descriptive intervals, not intervals for paired differences.",
            "Same bootstrap seed preserves source reduction; undefined groups can consume different RNG streams across methods.",
            "Publication input/branch/fold/runtime parity, calibrated author reference, participant dependence, access delivery and scientific admission remain unresolved.",
        ],
    }
