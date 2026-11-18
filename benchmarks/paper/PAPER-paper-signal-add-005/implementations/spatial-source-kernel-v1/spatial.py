"""OPM source-map arithmetic from qualified covariance and lead-field operands.

This is a component reconstruction, not a preprocessing pipeline or paper score.
The fixed source uses two tangential orientations, condition-specific covariance,
5% largest-singular-value loading, and the first minimum pseudo-T voxel.
"""
from __future__ import annotations

import numpy as np

TASK_ID = "PAPER-paper-signal-add-005"
SOURCE_REVISION = "0eb3a56af3d0e3a44b0f65c364e999f69cd4563f"
MU = 0.05
CONDITIONS = ("index", "pinky")


class SourceKernelError(ValueError):
    """The supplied component cannot be evaluated without an unresolved choice."""


def _real(value, name, ndim):
    a = np.asarray(value)
    if a.ndim != ndim or a.dtype.kind not in "iuf" or any(n == 0 for n in a.shape):
        raise SourceKernelError(f"{name}: nonempty real numeric {ndim}-D array required")
    a = np.asarray(a, dtype=np.float64)
    if not np.isfinite(a).all():
        raise SourceKernelError(f"{name}: all values must be finite")
    return a


def _covariance(value, name, channels=None):
    a = _real(value, name, 2)
    if a.shape[0] != a.shape[1] or (channels is not None and a.shape != (channels, channels)):
        raise SourceKernelError(f"{name}: covariance dimensions do not match channels")
    scale = float(np.max(np.abs(a)))
    tolerance = 64 * np.finfo(float).eps * len(a) * scale
    if not np.allclose(a, a.T, rtol=0, atol=tolerance):
        raise SourceKernelError(f"{name}: covariance is not symmetric")
    if float(np.linalg.eigvalsh(a).min()) < -tolerance:
        raise SourceKernelError(f"{name}: covariance is not positive semidefinite")
    return a


def covariance_from_trials(trials):
    """Sample covariance across all supplied samples/trials, not per-trial means.

    Input axes are channel, sample, trial. MATLAB column-major flattening is
    retained explicitly; the denominator is total sample count minus one.
    Caller owns bandpass, event identity, cleaning and complete retained support.
    """
    a = _real(trials, "trials", 3)
    flat = a.reshape(a.shape[0], -1, order="F")
    if flat.shape[1] < 2:
        raise SourceKernelError("sample covariance needs at least two observations")
    centered = flat - flat.mean(axis=1, keepdims=True)
    answer = centered @ centered.T / (flat.shape[1] - 1)
    if not np.isfinite(answer).all():
        raise SourceKernelError("covariance arithmetic overflow")
    return answer


def tangential_lead_fields(cartesian_fields, source_positions_m, mesh_vertices_m):
    """Convert supplied Cartesian fields to the source's two tangential axes.

    The origin is the arithmetic mean of supplied mesh vertices, not an assumed
    sphere center. Inputs must already share the authenticated metre frame.
    No MRI segmentation, field generation or outside-brain selection occurs.
    """
    fields = _real(cartesian_fields, "cartesian_fields", 3)
    positions = _real(source_positions_m, "source_positions_m", 2)
    vertices = _real(mesh_vertices_m, "mesh_vertices_m", 2)
    if fields.shape[1] != 3 or positions.shape != (fields.shape[2], 3) or vertices.shape[1] != 3:
        raise SourceKernelError("Cartesian/source/mesh dimensions do not match")
    offsets = positions - vertices.mean(axis=0)
    radius = np.linalg.norm(offsets, axis=1)
    if not np.isfinite(radius).all() or (radius <= 0).any():
        raise SourceKernelError("source at mesh origin has undefined tangential frame")
    phi = np.arctan2(offsets[:, 1], offsets[:, 0])
    elevation = np.arctan2(offsets[:, 2], np.hypot(offsets[:, 0], offsets[:, 1]))
    theta = np.pi / 2 - elevation
    e_theta = np.column_stack((np.cos(theta)*np.cos(phi), np.cos(theta)*np.sin(phi), -np.sin(theta)))
    e_phi = np.column_stack((-np.sin(phi), np.cos(phi), np.zeros(len(phi))))
    result = np.stack((np.einsum("csv,vs->cv", fields, e_theta),
                       np.einsum("csv,vs->cv", fields, e_phi)), axis=1)
    if not np.isfinite(result).all():
        raise SourceKernelError("tangential field arithmetic overflow")
    return result


def _regularized(covariance):
    c = _covariance(covariance, "covariance")
    scale = float(np.linalg.svd(c, compute_uv=False)[0])
    if not np.isfinite(scale) or scale <= 0:
        raise SourceKernelError("zero covariance cannot define the source inverse")
    result = c + MU * scale * np.eye(len(c))
    if not np.isfinite(result).all():
        raise SourceKernelError("regularization arithmetic overflow")
    return result


def _weight(regularized, lead_field):
    l = _real(lead_field, "lead_field", 2)
    if l.shape != (len(regularized), 2):
        raise SourceKernelError("the source requires channel-by-two tangential lead fields")
    inverse_l = np.linalg.solve(regularized, l)
    inverse_power = l.T @ inverse_l
    if not np.isfinite(inverse_power).all():
        raise SourceKernelError("inverse-power arithmetic overflow")
    orientations, singular, _ = np.linalg.svd(inverse_power)
    tolerance = 64 * np.finfo(float).eps * max(l.shape) * float(singular[0])
    if singular[-1] <= tolerance:
        raise SourceKernelError("rank-deficient tangential source has no qualified inverse")
    if singular[0] - singular[-1] <= tolerance:
        raise SourceKernelError("minimum-power orientation is degenerate; native choice unresolved")
    lopt = l @ orientations[:, -1]
    inverse_opt = np.linalg.solve(regularized, lopt)
    denominator = float(lopt @ inverse_opt)
    if not np.isfinite(denominator) or denominator <= 0:
        raise SourceKernelError("source-weight denominator is not positive finite")
    weight = inverse_opt / denominator
    if not np.isfinite(weight).all():
        raise SourceKernelError("source-weight arithmetic overflow")
    return weight


def source_weight(covariance, tangential_field):
    """Unit-gain weight; overall SVD sign is not a cross-platform invariant."""
    return _weight(_regularized(covariance), tangential_field)


def pseudo_t_map(covariance, active_covariance, control_covariance, tangential_fields):
    """Compute every supplied voxel; reject any unresolved voxel rather than drop it."""
    regularized = _regularized(covariance)
    channels = len(regularized)
    active = _covariance(active_covariance, "active_covariance", channels)
    control = _covariance(control_covariance, "control_covariance", channels)
    fields = _real(tangential_fields, "tangential_fields", 3)
    if fields.shape[:2] != (channels, 2):
        raise SourceKernelError("field shape must be channels by two by all supplied voxels")
    values = np.empty(fields.shape[2])
    for voxel in range(fields.shape[2]):
        weight = _weight(regularized, fields[:, :, voxel])
        pa = float(weight @ active @ weight)
        pc = float(weight @ control @ weight)
        denominator = 0.5 * (pa + pc)
        if not np.isfinite([pa, pc, denominator]).all() or denominator <= 0:
            raise SourceKernelError(f"voxel {voxel}: undefined pseudo-T denominator")
        values[voxel] = (pa - pc) / denominator
    if not np.isfinite(values).all():
        raise SourceKernelError("nonfinite pseudo-T map")
    return values


def select_peak(pseudo_t, voxel_ids, source_positions_m):
    """First minimum in retained source order, including exact ties; never abs-max."""
    values = _real(pseudo_t, "pseudo_t", 1)
    positions = _real(source_positions_m, "source_positions_m", 2)
    if not isinstance(voxel_ids, (list, tuple)) or len(voxel_ids) != len(values):
        raise SourceKernelError("one supplied identity per voxel is required")
    if any(not isinstance(v, str) or not v for v in voxel_ids) or len(set(voxel_ids)) != len(voxel_ids):
        raise SourceKernelError("voxel identities must be unique nonempty strings")
    if positions.shape != (len(values), 3):
        raise SourceKernelError("one metre-frame coordinate per voxel is required")
    index = int(np.argmin(values))
    return {"voxel_index_zero_based": index, "voxel_id": voxel_ids[index],
            "position_m": positions[index].tolist(), "pseudo_t": float(values[index]),
            "exact_minimum_tie_count": int(np.sum(values == values[index]))}


def virtual_electrode(trials, covariance, tangential_field):
    """Return sample-by-trial VE, using THIS trial condition's covariance.

    The caller supplies the selected peak's lead field. For the opposite-finger
    companion, recompute weights with the opposite condition's covariance while
    retaining the selected source location. No bandpass/Hilbert/normalization is
    performed here. The fixed source divides by the weight Euclidean norm.
    """
    a = _real(trials, "trials", 3)
    c = _covariance(covariance, "covariance", a.shape[0])
    weight = source_weight(c, tangential_field)
    norm = float(np.linalg.norm(weight))
    if not np.isfinite(norm) or norm <= 0:
        raise SourceKernelError("invalid weight norm")
    result = np.einsum("c,ctr->tr", weight/norm, a)
    if not np.isfinite(result).all():
        raise SourceKernelError("virtual electrode arithmetic overflow")
    return result


def condition_maps(operands, tangential_fields, voxel_ids, source_positions_m):
    """Separate index/pinky maps and source locations, without inventing a score."""
    if not isinstance(operands, dict) or set(operands) != set(CONDITIONS):
        raise SourceKernelError("both separate finger operands are required exactly once")
    result = {}
    for condition in CONDITIONS:
        row = operands[condition]
        if not isinstance(row, dict) or set(row) != {"covariance", "active_covariance", "control_covariance"}:
            raise SourceKernelError("each finger needs all three exact covariance operands")
        values = pseudo_t_map(**row, tangential_fields=tangential_fields)
        result[condition] = {"pseudo_t": values.tolist(),
                             "peak": select_peak(values, voxel_ids, source_positions_m)}
    return {"task_id": TASK_ID, "source_revision": SOURCE_REVISION,
            "scope": "supplied_operand_spatial_source_kernel",
            "native_numerical_parity": "unqualified", "scientific_outcome": "unknown",
            "reproduction_score": None, "improvement_score": None,
            "voxel_ids": list(voxel_ids), "conditions": result}
