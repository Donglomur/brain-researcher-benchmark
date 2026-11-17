"""Pinned author-code geometry primitives and complete downstream OPM panels.

This does not segment MRIs, register heads, certify supplied sensor distances,
or score a proposed helmet design. See README.md for unresolved source parity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import stats
from scipy.spatial import cKDTree

TASK_ID = "PAPER-paper-signal-add-005"
REVISION = "0eb3a56af3d0e3a44b0f65c364e999f69cd4563f"
SOURCE_SHA256 = "8d6638e36e11dcd6102c577f80e88374bb1c74a0f0aec24965b38ace750628b0"
CHILDREN = tuple(f"sub-{i:03d}" for i in range(1, 28))
ADULTS = tuple(f"sub-{i:03d}" for i in range(101, 127) if i not in (120, 123))
INCLUDED = CHILDREN + ADULTS
EXCLUDED = ("sub-120", "sub-123")


class GeometryError(ValueError):
    pass


def _array(value, name, ndim):
    raw = np.asarray(value)
    if raw.dtype.kind not in "iuf" or raw.ndim != ndim or not np.isfinite(raw).all():
        raise GeometryError(f"{name} must be finite real numeric with {ndim} dimensions")
    return raw.astype(float)


def _positive(value, name):
    a = _array(value, name, 0)
    if float(a) <= 0:
        raise GeometryError(f"{name} must be positive")
    return float(a)


def source_sensor_centers(channels, sens2template):
    """Author lines 603–631: X channel, positions /100, then affine transform.

    channels is the parsed native TSV rows with name/Px/Py/Pz. The source's
    scalar/vector transform serialization uses MATLAB column-major reshape.
    Returned positions are in metres if the original transform is in metres.
    Its coordinate frame and calibration must be authenticated upstream.
    """
    transform = _array(sens2template, "sens2template", np.asarray(sens2template).ndim)
    if transform.shape not in ((16,), (4, 4)):
        raise GeometryError("sens2template must be 16 MATLAB-order entries or a 4x4 matrix")
    transform = transform.reshape((4, 4), order="F")
    if not np.allclose(transform[3], [0, 0, 0, 1], atol=1e-12, rtol=0):
        raise GeometryError("sens2template must be affine homogeneous")
    names = []
    positions = []
    for row in channels:
        name = row["name"]
        if not isinstance(name, str) or not name:
            raise GeometryError("channel names must be nonempty strings")
        if name.endswith("X"):
            names.append(name)
            positions.append([float(row[k]) for k in ("Px", "Py", "Pz")])
    if not names or len(names) != len(set(names)):
        raise GeometryError("X-channel names must identify nonempty unique physical sensors")
    points = _array(positions, "channel positions", 2) / 100.0
    return names, points @ transform[:3, :3].T + transform[:3, 3]


def nearest_vertex_distances(sensor_centers_m, scalp_vertices_m):
    """Exact nearest-vertex boundary of KDTreeSearcher/knnsearch, in metres.

    This intentionally does not interpolate triangles. Tied vertex identities
    may differ between libraries; the distance is the endpoint.
    """
    sensors = _array(sensor_centers_m, "sensor_centers_m", 2)
    scalp = _array(scalp_vertices_m, "scalp_vertices_m", 2)
    if sensors.shape[1:] != (3,) or scalp.shape[1:] != (3,) or not len(sensors) or not len(scalp):
        raise GeometryError("nonempty points x 3 coordinates required")
    distances, _ = cKDTree(scalp).query(sensors, k=1, workers=1)
    if not np.isfinite(distances).all():
        raise GeometryError("distance calculation overflowed")
    return distances


def line_fit(x, y):
    """Source intercept/slope and Pearson association, one row per participant."""
    x, y = _array(x, "predictor", 1), _array(y, "distance", 1)
    if x.shape != y.shape or len(x) < 3 or np.ptp(x) == 0:
        raise GeometryError("line fit requires paired rows and a varying predictor")
    xc = x - x.mean()
    slope = float(xc @ (y - y.mean()) / (xc @ xc))
    intercept = float(y.mean() - slope * x.mean())
    if np.ptp(y) == 0:
        r, p = None, None
    else:
        r, p = map(float, stats.pearsonr(x, y))
    return {"intercept_mm": intercept, "slope_mm_per_predictor_unit": slope,
            "pearson_r": r, "pearson_p_two_sided": p, "n_participants": len(x)}


def paired_slope_control(head, actual_mm, virtual_mm, swap_mask):
    """Source lines 510–547; paired within-person swaps, strict upper exceedance.

    Supplying masks explicitly separates the calculation from the unrecorded
    MATLAB RNG. This function does not claim recovered historical random draws.
    The source reports mean(null > observed), with no plus-one correction.
    """
    head = _array(head, "head circumference", 1)
    actual = _array(actual_mm, "actual distance", 1)
    virtual = _array(virtual_mm, "virtual distance", 1)
    masks = np.asarray(swap_mask)
    if actual.shape != head.shape or virtual.shape != head.shape or len(head) < 3 or np.ptp(head) == 0:
        raise GeometryError("paired slope inputs require equal lengths and varying heads")
    if masks.dtype.kind != "b" or masks.ndim != 2 or masks.shape[1] != len(head) or not len(masks):
        raise GeometryError("swap_mask must be nonempty boolean permutations x participants")
    centered = head - head.mean()
    weights = centered / (centered @ centered)
    differences = actual - virtual
    observed = float(differences @ weights)
    null = ((1 - 2 * masks.astype(float)) * differences) @ weights
    # MATLAB prctile uses midpoint plotting positions; NumPy's hazen matches.
    return {"actual_minus_virtual_slope": observed,
            "upper_tail_fraction_strict": float(np.mean(null > observed)),
            "null_97_5_percentile_hazen": float(np.percentile(null, 97.5, method="hazen")),
            "permutations": len(masks), "null_slope_differences": null.tolist(),
            "policy": "source_strict_upper_tail_no_plus_one",
            "historical_random_draw_parity": False}


def _distances(row, arm):
    block = row[arm]
    names = block["sensor_ids"]
    if not isinstance(names, list) or not names or any(not isinstance(n, str) or not n for n in names):
        raise GeometryError(f"{arm} requires nonempty sensor IDs")
    if len(names) != len(set(names)):
        raise GeometryError(f"{arm} has repeated physical sensors")
    distances = _array(block["nearest_scalp_vertex_distances_m"], f"{arm} distances", 1)
    if len(distances) != len(names) or np.any(distances < 0):
        raise GeometryError(f"{arm} requires one nonnegative distance per physical sensor")
    return names, distances


def evaluate(manifest):
    """Reconstruct all four code panels from complete per-sensor distance inputs."""
    if manifest.get("task_id") != TASK_ID or manifest.get("source_revision") != REVISION:
        raise GeometryError("task/revision mismatch")
    if manifest.get("schema_version") != 1 or manifest.get("source_code_sha256") != SOURCE_SHA256:
        raise GeometryError("schema/source content mismatch")
    for key in ("geometry_provenance", "head_circumference_provenance", "age_provenance"):
        if not isinstance(manifest.get(key), str) or not manifest[key].strip():
            raise GeometryError(f"{key} required")
    if manifest.get("excluded_participants") != list(EXCLUDED):
        raise GeometryError("retain both source-code exclusions explicitly")
    rows = manifest["participants"]
    ids = [row["participant_id"] for row in rows]
    if len(ids) != len(INCLUDED) or set(ids) != set(INCLUDED):
        raise GeometryError("exact complete 51-participant source-code cohort required")
    keyed = dict(zip(ids, rows))
    rows = [keyed[name] for name in INCLUDED]
    age = [_positive(r["age_years"], "age_years") for r in rows]
    head = [_positive(r["head_circumference_source_value"], "head circumference") for r in rows]
    # The source picks the largest included adult, only if larger than all kids.
    adult_head = head[len(CHILDREN):]
    if max(adult_head) <= max(head[:len(CHILDREN)]):
        raise GeometryError("source adult-reference branch undefined for these head values")
    reference = ADULTS[int(np.argmax(adult_head))]
    if manifest.get("reference_participant_id") != reference:
        raise GeometryError("reference must match source largest-adult selection")
    reference_sensors, _ = _distances(keyed[reference], "actual")
    summaries = []
    for row in rows:
        actual_ids, actual = _distances(row, "actual")
        virtual_ids, virtual = _distances(row, "virtual")
        if virtual_ids != reference_sensors:
            raise GeometryError("all virtual heads require the same ordered reference-helmet sensors")
        summaries.append({"participant_id": row["participant_id"],
                          "actual_sensor_count": len(actual_ids), "virtual_sensor_count": len(virtual_ids),
                          "actual_mean_mm": float(actual.mean() * 1000),
                          "virtual_mean_mm": float(virtual.mean() * 1000)})
    actual_mm = [r["actual_mean_mm"] for r in summaries]
    virtual_mm = [r["virtual_mean_mm"] for r in summaries]
    seed = manifest["permutation_seed"]
    if type(seed) is not int or seed < 0:
        raise GeometryError("permutation_seed must be a nonnegative integer")
    # Frozen prospective replay policy: source Nperm=10000, NumPy PCG64 RNG.
    swaps = np.random.Generator(np.random.PCG64(seed)).integers(0, 2, size=(10000, len(INCLUDED))).astype(bool)
    return {"task_id": TASK_ID, "scope": "four_source_code_opm_panels_and_paired_slope_diagnostic",
            "source_revision": REVISION, "source_code_sha256": SOURCE_SHA256,
            "participant_order": list(INCLUDED), "excluded_participants": list(EXCLUDED),
            "reference_participant_id": reference, "participants": summaries,
            "panels": {"actual_vs_age": line_fit(age, actual_mm),
                       "virtual_vs_age": line_fit(age, virtual_mm),
                       "actual_vs_head_source_value": line_fit(head, actual_mm),
                       "virtual_vs_head_source_value": line_fit(head, virtual_mm)},
            "head_predictor_unit": "unresolved_native_regionprops_perimeter_unit",
            "paired_slope_control": paired_slope_control(head, actual_mm, virtual_mm, swaps),
            "permutation_rng": {"algorithm": "NumPy PCG64", "seed": seed, "role": "prospective_replay"},
            "qualification": "unqualified_downstream_calculation",
            "paper_reproduction_score": None, "paper_improvement_score": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = args.input.read_bytes()
    manifest = json.loads(data)
    report = evaluate(manifest)
    report["input_sha256"] = hashlib.sha256(data).hexdigest()
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
