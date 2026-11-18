"""Grader-only affine L2 calibration of already aligned CellMincer traces.

No clock mapping, detrending, ABF decoding, fitting of denoisers or scientific
qualification occurs here. Explicit fitting indices remain operator choices
until historical support is recovered. Outputs are EP-derived private material.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

TASK_ID = "PAPER-paper-method-030"
N_FRAMES = 5000
SAMPLE_RATE_HZ = 500
SOURCE_METHODS = frozenset({"raw", "cellmincer", "support", "pmd", "n2s"})
POPULATION = Path(__file__).resolve().parent.parent / "initial-evaluator-v1" / "population.json"
POPULATION_SHA256 = "626482a09a9fd6fd1c0713667aaeef97176f37e2ad21937a9df068c71041df9e"


class CalibrationError(ValueError):
    """An incomplete or non-identifiable input cannot yield a calibrated panel."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CalibrationError(message)


def valid_hash(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _vector(value: Any, name: str) -> list[float]:
    require(isinstance(value, (list, tuple)) and len(value) == N_FRAMES,
            f"{name}: exactly {N_FRAMES} aligned samples required")
    require(all(type(v) in (int, float) for v in value), f"{name}: real numeric samples required")
    try:
        values = [float(v) for v in value]
    except (ValueError, OverflowError) as exc:
        raise CalibrationError(f"{name}: finite representable samples required") from exc
    require(all(math.isfinite(v) for v in values), f"{name}: nonfinite sample")
    return values


def _support(value: Any) -> list[int]:
    require(isinstance(value, list) and 2 <= len(value) <= N_FRAMES,
            "explicit fitting indices with at least two samples required")
    require(all(type(v) is int and 0 <= v < N_FRAMES for v in value),
            "fitting indices must be integer native-frame indices")
    require(all(a < b for a, b in zip(value, value[1:])),
            "fitting indices must be strictly increasing without duplicates")
    return value


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode("utf-8")).hexdigest()


def _scaled_ratio_product(a: float, b: float, c: float) -> float:
    """Compute a*b/c without overflowing an avoidable intermediate ratio."""
    if a == 0:
        return 0.0
    ma, ea = math.frexp(a)
    mb, eb = math.frexp(b)
    mc, ec = math.frexp(c)
    result = math.ldexp(ma * mb / mc, ea + eb - ec)
    require(result != 0, "affine slope is below representable numeric range")
    return result


def affine_l2(ep_mv: Any, optical_au: Any, fit_sample_indices: Any) -> dict[str, Any]:
    """Unweighted min sum_i (EP_i - gain*optical_i - offset)^2 on supplied i.

    Scaling and centered sums keep the algebra finite for very small or large
    representable inputs. There is no positive-gain constraint, clipping, ridge,
    mask search or discarded observation. Constant optical fit support fails;
    it cannot identify a slope. EP outside the supplied support cannot affect
    the fitted coefficients. All 5000 optical samples are transformed.
    """
    ep = _vector(ep_mv, "ep_mv")
    optical = _vector(optical_au, "optical_au")
    indices = _support(fit_sample_indices)
    xs = max(abs(optical[i]) for i in indices)
    ys = max(abs(ep[i]) for i in indices)
    require(xs > 0, "constant optical fitting support: affine slope is not identifiable")
    ynorm = ys if ys else 1.0
    x = [optical[i] / xs for i in indices]
    y = [ep[i] / ynorm for i in indices]
    mx = math.fsum(x) / len(x)
    my = math.fsum(y) / len(y)
    dx = [v - mx for v in x]
    dy = [v - my for v in y]
    xx = math.fsum(v * v for v in dx)
    require(xx > 0, "constant optical fitting support: affine slope is not identifiable")
    beta = math.fsum(a * b for a, b in zip(dx, dy)) / xx
    try:
        gain = _scaled_ratio_product(beta, ynorm, xs)
        offset = (my - beta * mx) * ynorm
        # A zero slope is a constant fit, including outside the fitting range;
        # do not manufacture NaN from an otherwise unnecessary inf * 0.
        calibrated = ([offset] * N_FRAMES if beta == 0 else
                      [((v / xs - mx) * beta + my) * ynorm for v in optical])
    except (ArithmeticError, OverflowError) as exc:
        raise CalibrationError("affine result outside representable numeric range") from exc
    require(math.isfinite(gain) and math.isfinite(offset) and all(math.isfinite(v) for v in calibrated),
            "affine result outside representable numeric range")
    # The coefficients and every transformed sample must describe the same fit.
    residual_scale = max([abs(ep[i]) for i in indices] + [abs(calibrated[i]) for i in indices])
    if residual_scale:
        mean_square = math.fsum(((ep[i] / residual_scale) - (calibrated[i] / residual_scale)) ** 2
                                for i in indices) / len(indices)
        rmse = math.sqrt(mean_square) * residual_scale
    else:
        rmse = 0.0
    require(math.isfinite(rmse), "fit residual outside representable numeric range")
    return {"gain_mv_per_au": gain, "offset_mv": offset, "fit_sample_count": len(indices),
            "fit_indices_sha256": _canonical_hash(indices), "fit_rmse_mv": rmse,
            "calibrated_mv": calibrated}


def _catalogue() -> dict[str, str]:
    payload = POPULATION.read_bytes()
    require(hashlib.sha256(payload).hexdigest() == POPULATION_SHA256, "frozen population changed")
    source = json.loads(payload)
    rows = source["recordings"]
    require(len(rows) == 22 and len({r["recording_id"] for r in rows}) == 22,
            "frozen population must retain all 22 saved recordings")
    return {r["recording_id"]: r["cell_id"] for r in rows}


def calibrate_panel(panel: dict[str, Any]) -> dict[str, Any]:
    """Calibrate every supplied method on identical per-recording EP support.

    This is the saved inventory, not proof of the original 26/22 selection.
    No test/train assignment is introduced. No existing evaluator is invoked.
    Evidence hashes bind operator declarations; they do not authenticate the
    scientific origin of alignment, detrending, channels or fitting support.
    """
    required = {"schema_version", "task_id", "population_sha256", "reference_access",
                "optical_units", "ep_units", "sampling_rate_hz", "methods",
                "fit_policy", "support_status", "preparation_evidence_sha256", "recordings"}
    require(isinstance(panel, dict) and set(panel) == required, "exact calibration panel fields required")
    require(type(panel["schema_version"]) is int and panel["schema_version"] == 1 and
            panel["task_id"] == TASK_ID, "wrong task or schema")
    require(panel["population_sha256"] == POPULATION_SHA256, "population identity mismatch")
    require(panel["reference_access"] == "grader_only", "EP and calibrated outputs must remain grader-only")
    require(panel["optical_units"] == "fluorescence_arbitrary_units" and panel["ep_units"] == "mV",
            "explicit fluorescence AU and EP mV units required")
    require(type(panel["sampling_rate_hz"]) is int and panel["sampling_rate_hz"] == SAMPLE_RATE_HZ,
            "already aligned 500-Hz frame grid required")
    require(panel["fit_policy"] == "shared_explicit_indices_per_recording",
            "one common explicit fitting support per recording required")
    require(panel["support_status"] == "operator_frozen_historical_equivalence_unresolved",
            "historical fitting support is not authenticated by this component")
    require(valid_hash(panel["preparation_evidence_sha256"]), "preparation evidence identity required")
    methods = panel["methods"]
    require(isinstance(methods, list) and 5 <= len(methods) <= 32 and
            all(isinstance(m, str) and m and len(m) <= 80 for m in methods) and
            len(set(methods)) == len(methods) and SOURCE_METHODS <= set(methods),
            "complete raw/CellMincer/SUPPORT/PMD/N2S coverage and unique method names required")
    catalogue = _catalogue()
    rows = panel["recordings"]
    require(isinstance(rows, list) and len(rows) == len(catalogue) and
            all(isinstance(r, dict) for r in rows), "all 22 saved recordings required")
    require(all(isinstance(r.get("recording_id"), str) for r in rows) and
            {r["recording_id"] for r in rows} == set(catalogue), "recording coverage mismatch")
    prepared = []
    for row in sorted(rows, key=lambda r: r["recording_id"]):
        require(set(row) == {"recording_id", "cell_id", "alignment_evidence_sha256",
                             "fit_support_evidence_sha256", "fit_sample_indices", "ep_mv", "optical_au"},
                "exact recording fields required; method-specific fit policies are forbidden")
        require(row["cell_id"] == catalogue[row["recording_id"]], "cell identity mismatch")
        require(valid_hash(row["alignment_evidence_sha256"]) and valid_hash(row["fit_support_evidence_sha256"]),
                "alignment and fit-support evidence identities required")
        require(isinstance(row["optical_au"], dict) and set(row["optical_au"]) == set(methods),
                "every method must cover every saved recording")
        indices = _support(row["fit_sample_indices"])
        calibrated = {method: affine_l2(row["ep_mv"], row["optical_au"][method], indices) for method in methods}
        prepared.append({"recording_id": row["recording_id"], "cell_id": row["cell_id"],
                         "alignment_evidence_sha256": row["alignment_evidence_sha256"],
                         "fit_support_evidence_sha256": row["fit_support_evidence_sha256"],
                         "methods": calibrated})
    return {"schema_version": 1, "task_id": TASK_ID, "scope": "complete_saved_22_grader_affine_l2_component",
            "reference_access": "grader_only", "units": "mV", "sampling_rate_hz": SAMPLE_RATE_HZ,
            "frames_per_recording": N_FRAMES, "population_sha256": POPULATION_SHA256,
            "preparation_evidence_sha256": panel["preparation_evidence_sha256"],
            "alignment_policy": "grader_ep_fitted_affine_l2_not_external_no_test_ep_fit",
            "support_status": panel["support_status"], "electrical_reference_used_in_calibration": True,
            "scientific_qualification": "unknown", "reproduction_verified": False, "improvement_verified": False,
            "recordings": prepared,
            "remaining_gaps": ["ABF decoding, channel/units, detrending and clock mapping are upstream and unverified.",
                               "Historical fit support, raw-derived ROI masks and original26/22 membership remain unresolved.",
                               "Original prominence bins, spectral mask, aggregation and fresh denoisers are not supplied.",
                               "EP-derived output must not be released to the candidate; no process isolation is established."]}
