"""Source-free LIFESPAN arithmetic; no file readers, cache or reference imports.

``build_basis`` consumes CANONICAL, already once-rounded float32 parcel means
and computational ages, not tolerance-accepted participant evidence. Subjects,
frames and ROIs must already be in frozen computational order. Defaults enforce
59 people/148 parcels; smaller explicit dimensions are for manufactured fixtures.

Canonical FC uses the public NumPy corrcoef construction, and the single fit uses
the public sklearn KMeans recipe. These shared implementations are disclosed.
Separately centered normalized-dot FC is an independent DIAGNOSTIC only: it never
changes the canonical fit, support, or accepted estimator. Summaries use fsum and
age p-values use the symmetric beta tail rather than scipy.stats.pearsonr.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
from scipy.special import betainc
import sklearn
from sklearn.cluster import KMeans
from threadpoolctl import threadpool_limits


FISHER_CLIP = 0.999
KMEANS_PARAMETERS = dict(n_clusters=7, init="k-means++", n_init=10,
                         max_iter=300, tol=1e-4, verbose=0, random_state=0,
                         copy_x=True, algorithm="lloyd")


class PreconditionError(ValueError):
    """Invalid canonical input; the caller must preserve a failure receipt."""


class NumericalError(ArithmeticError):
    """A specified operation was not finite; never silently omit its input."""


def _real_array(value, ndim=None):
    a = np.asarray(value)
    if a.dtype.kind not in "iuf" or (ndim is not None and a.ndim != ndim):
        raise PreconditionError("expected a real numeric array of the stated rank")
    a = np.asarray(a, dtype=np.float64)
    if not np.isfinite(a).all():
        raise PreconditionError("canonical input contains nonfinite values")
    return a


def _float32_exact(value, ndim=None):
    a = _real_array(value, ndim)
    with np.errstate(over="ignore", invalid="ignore"):
        q = a.astype(np.float32)
    if not np.isfinite(q).all() or not np.array_equal(a, q.astype(np.float64)):
        raise PreconditionError("canonical input must equal promoted float32 values")
    return a


def vertex_mean(vertices):
    """Ordered X[:, v] -> C-order float64 mean -> single float32 conversion.

    The upstream reader supplies ascending original indices v separately for
    each hemisphere; this function does not select, concatenate or reorder them.
    """
    x = np.asarray(_real_array(vertices, 2), dtype=np.float64, order="C")
    if x.shape[1] == 0:
        raise PreconditionError("a parcel must contain vertices")
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        mean = np.mean(x, axis=1, dtype=np.float64)
        result = mean.astype(np.float32)
    if not np.isfinite(mean).all() or not np.isfinite(result).all():
        raise NumericalError("parcel mean or float32 storage is nonfinite")
    return result


def computational_age(source_age):
    """Separate source metadata helper, preserving the declared float32 cast."""
    a = _real_array(source_age, 1)
    if (a < 0).any():
        raise PreconditionError("age must be nonnegative")
    with np.errstate(over="ignore"):
        result = a.astype(np.float32).astype(np.float64)
    if not np.isfinite(result).all():
        raise NumericalError("computational age is nonfinite")
    return result


def _normalized(x):
    """Finite nonconstant vector -> centered unit vector, no near-zero cutoff."""
    center = math.fsum(float(v) for v in x) / len(x)
    c = x - center
    scale = float(np.max(np.abs(c)))
    if not math.isfinite(center) or not math.isfinite(scale) or scale == 0:
        raise NumericalError("nonconstant input has invalid centered norm")
    u = c / scale
    norm = math.sqrt(math.fsum(float(v) ** 2 for v in u))
    result = u / norm
    if not np.isfinite(result).all():
        raise NumericalError("normalized vector is nonfinite")
    return result


def parcel_support(q):
    """Canonical exact-constant support, independent of diagnostic reductions."""
    x = _float32_exact(q, 2)
    t, r = x.shape
    status = np.full(r, "insufficient_frames", dtype="U24")
    if t >= 2:
        status[:] = np.where(np.all(x == x[0], axis=0), "constant", "ok")
    return status


def normalized_dot_audit(q):
    """Independent diagnostic full Pearson matrix; invalid entries stay NaN."""
    x = _float32_exact(q, 2)
    t, r = x.shape
    status = parcel_support(x)
    result = np.full((r, r), np.nan)
    good = np.flatnonzero(status == "ok")
    normalized = np.column_stack([_normalized(x[:, j]) for j in good]) if len(good) else np.empty((t, 0))
    # No fitting, clipping-dependent support decision or private agreement gate.
    dot = np.clip(normalized.T @ normalized, -1.0, 1.0)
    result[np.ix_(good, good)] = dot
    return result, status


def canonical_connectome(q):
    """Public corrcoef basis plus diagnostic normalized-dot edge values."""
    x = _float32_exact(q, 2)
    t, r = x.shape
    if r < 2:
        raise PreconditionError("at least two parcels are required")
    ij = np.column_stack(np.triu_indices(r, 1))
    status = parcel_support(x)
    audit, _ = normalized_dot_audit(x)
    valid = (status[ij[:, 0]] == "ok") & (status[ij[:, 1]] == "ok")
    raw = np.full(len(ij), np.nan)
    if t >= 2:
        # Exact public constructor on the FULL source matrix, not a good-column
        # submatrix whose BLAS dimensions might change a discrete fit basis.
        with np.errstate(divide="ignore", invalid="ignore"):
            matrix = np.corrcoef(x.T)
        raw[valid] = matrix[ij[valid, 0], ij[valid, 1]]
        if not np.isfinite(raw[valid]).all():
            raise NumericalError("canonical nonconstant correlations are nonfinite")
    fisher = np.full(len(ij), np.nan)
    fisher[valid] = np.arctanh(np.clip(raw[valid], -FISHER_CLIP, FISHER_CLIP))
    audit_edges = audit[ij[:, 0], ij[:, 1]]
    delta = float(np.max(np.abs(raw[valid] - audit_edges[valid]))) if valid.any() else None
    return dict(parcel_status=status, edge_roi_index=ij, edge_valid=valid,
                raw_r=raw, fisher_z=fisher, audit_raw_r=audit_edges,
                audit_max_abs_r_difference=delta)


def group_connectome(fisher_z, edge_valid, edge_roi_index, n_rois):
    """Sequential equal-person sum in the caller's fixed cohort order."""
    z = np.asarray(fisher_z, dtype=np.float64)
    v = np.asarray(edge_valid)
    ij = np.asarray(edge_roi_index)
    expected = np.column_stack(np.triu_indices(n_rois, 1))
    if z.ndim != 2 or z.shape[0] == 0 or v.dtype.kind != "b" or v.shape != z.shape or not np.array_equal(ij, expected) or z.shape[1] != len(ij):
        raise PreconditionError("invalid canonical group axes or masks")
    if not np.isfinite(z[v]).all() or not np.isnan(z[~v]).all():
        raise PreconditionError("Fisher validity and NaN support disagree")
    full = np.all(v, axis=0)
    sums = np.zeros(len(ij), dtype=np.float64)
    for row in z:
        sums += row
    means = sums / z.shape[0]
    if not np.isfinite(means[full]).all():
        raise NumericalError("group feature is nonfinite")
    g = np.full((n_rois, n_rois), np.nan)
    mask = np.zeros_like(g, dtype=bool)
    np.fill_diagonal(g, 0.0)
    np.fill_diagonal(mask, True)
    g[ij[full, 0], ij[full, 1]] = means[full]
    g[ij[full, 1], ij[full, 0]] = means[full]
    mask[ij[full, 0], ij[full, 1]] = True
    mask[ij[full, 1], ij[full, 0]] = True
    return g, mask


def partition(group_features, group_valid):
    """One shared, version-pinned KMeans fit; no fits for incomplete support."""
    g = np.asarray(group_features, dtype=np.float64)
    valid = np.asarray(group_valid)
    if g.ndim != 2 or g.shape[0] != g.shape[1] or g.shape[0] < 7 or valid.shape != g.shape or valid.dtype.kind != "b":
        raise PreconditionError("invalid group geometry")
    if not np.array_equal(valid, valid.T) or not np.all(np.diag(valid)) or not np.all(np.diag(g) == 0):
        raise PreconditionError("group support must be symmetric with valid zero diagonal")
    if not np.isfinite(g[valid]).all() or not np.isnan(g[~valid]).all() or not np.array_equal(g, g.T, equal_nan=True):
        raise PreconditionError("invalid symmetric group features")
    if not valid.all():
        return dict(status="incomplete_group_connectome", labels=None,
                    n_clusters_occupied=None, fit_diagnostics=None, warnings=[])
    if sklearn.__version__ != "1.5.2":
        raise PreconditionError("canonical KMeans requires sklearn1.5.2")
    with warnings.catch_warnings(record=True) as captured, threadpool_limits(limits=1):
        warnings.simplefilter("always")
        model = KMeans(**KMEANS_PARAMETERS).fit(np.array(g, dtype=np.float64, order="C", copy=True), sample_weight=None)
    labels = np.asarray(model.labels_, dtype=np.int64)
    occupied = len(np.unique(labels))
    if not np.isfinite(model.cluster_centers_).all() or not math.isfinite(float(model.inertia_)):
        raise NumericalError("KMeans returned nonfinite diagnostics")
    return dict(status="ok" if occupied == 7 else "fewer_than_seven_occupied_clusters",
                labels=labels, n_clusters_occupied=occupied,
                fit_diagnostics=dict(centers=model.cluster_centers_.copy(),
                                     inertia=float(model.inertia_), n_iter=int(model.n_iter_)),
                warnings=[f"{w.category.__name__}: {w.message}" for w in captured])


def coassignment(labels):
    """Pair membership, independent of arbitrary nonempty cluster names."""
    x = np.asarray(labels)
    if x.ndim != 1 or len(x) == 0 or x.dtype.kind not in "iufUS":
        raise PreconditionError("invalid partition labels")
    if x.dtype.kind in "iuf" and not np.isfinite(x).all():
        raise PreconditionError("nonfinite partition label")
    if x.dtype.kind in "US" and any(not str(s) for s in x.astype(str)):
        raise PreconditionError("empty partition label")
    return x[:, None] == x[None, :]


def same_partition(left, right):
    return np.array_equal(coassignment(left), coassignment(right))


def summaries(fisher_z, edge_valid, edge_roi_index, partition_result, subject_ids, ages):
    """Complete-pair signed global and zero-clipped within/between arithmetic."""
    z = np.asarray(fisher_z, dtype=np.float64)
    v = np.asarray(edge_valid)
    ij = np.asarray(edge_roi_index)
    if z.ndim != 2 or v.shape != z.shape or v.dtype.kind != "b" or len(subject_ids) != len(z) or len(ages) != len(z):
        raise PreconditionError("invalid summary support")
    if not np.isfinite(z[v]).all() or not np.isnan(z[~v]).all():
        raise PreconditionError("summary Fisher support mismatch")
    fitted = partition_result["status"] == "ok"
    within = None
    if fitted:
        labels = np.asarray(partition_result["labels"])
        coassignment(labels)
        within = labels[ij[:, 0]] == labels[ij[:, 1]]
    result = []
    for i, person in enumerate(subject_ids):
        complete = bool(v[i].all())
        row = dict(subject_id=str(person), age=float(ages[i]),
                   n_edges_expected=z.shape[1], n_edges_defined=int(v[i].sum()),
                   global_fisher_sum=None, global_connectivity=None,
                   global_status="ok" if complete else "incomplete_edge_support",
                   n_within_edges=None, n_between_edges=None,
                   within_positive_sum=None, between_positive_sum=None,
                   within_network_connectivity=None, between_network_connectivity=None,
                   system_segregation=None, segregation_status="partition_undefined")
        if complete:
            total = math.fsum(float(t) for t in z[i])
            row.update(global_fisher_sum=total, global_connectivity=total / z.shape[1])
        if fitted:
            nw = int(within.sum())
            nb = len(within) - nw
            row.update(n_within_edges=nw, n_between_edges=nb)
            if nw == 0 or nb == 0:
                row["segregation_status"] = "empty_pair_family"
            elif not complete:
                row["segregation_status"] = "incomplete_edge_support"
            else:
                sw = math.fsum(max(float(t), 0.0) for t in z[i, within])
                sb = math.fsum(max(float(t), 0.0) for t in z[i, ~within])
                w, b = sw / nw, sb / nb
                ratio = None if w == 0.0 else (w - b) / w
                if ratio is not None and not math.isfinite(ratio):
                    raise NumericalError("nonfinite defined segregation")
                row.update(within_positive_sum=sw, between_positive_sum=sb,
                           within_network_connectivity=w, between_network_connectivity=b,
                           system_segregation=ratio,
                           segregation_status="zero_within_mean" if w == 0.0 else "ok")
        result.append(row)
    return result


def age_endpoint(age, values, subject_ids):
    """Complete-person signed Pearson, symmetric-beta p, published plug-in CI."""
    a = _float32_exact(age, 1)
    n = len(a)
    if n < 4 or len(values) != n or len(subject_ids) != n or (a < 0).any():
        raise PreconditionError("endpoint requires matching >=4 people and nonnegative age")
    missing = [str(s) for s, v in zip(subject_ids, values) if v is None]
    result = dict(status="incomplete_subject_support", n_expected=n,
                  n_defined=n - len(missing), undefined_subject_ids=missing,
                  pearson_r=None, p=None, ci95=None)
    # NaN is corruption, not an implicit None/missing-person signal.
    for v in values:
        if v is not None and (isinstance(v, (bool, np.bool_)) or not math.isfinite(float(v))):
            raise PreconditionError("invalid defined endpoint value")
    if missing:
        return result
    y = np.asarray(values, dtype=np.float64)
    if np.all(a == a[0]):
        result["status"] = "constant_age"
        return result
    if np.all(y == y[0]):
        result["status"] = "constant_summary"
        return result
    xnorm, ynorm = _normalized(a), _normalized(y)
    r = max(-1.0, min(1.0, math.fsum(float(x) * float(y) for x, y in zip(xnorm, ynorm))))
    shape = n / 2.0 - 1.0
    p = min(1.0, 2.0 * float(betainc(shape, shape, (1.0 - abs(r)) / 2.0)))
    z = math.atanh(max(-0.999999, min(0.999999, r)))
    half = 1.96 / math.sqrt(n - 3)
    ci = [math.tanh(z - half), math.tanh(z + half)]
    if not all(math.isfinite(v) for v in [r, p, *ci]):
        raise NumericalError("age endpoint is nonfinite")
    result.update(status="ok", pearson_r=r, p=p, ci95=ci)
    return result


def build_basis(q, age, subject_ids, roi_ids, *, expected_subjects=59, expected_rois=148):
    """Return keyed arrays, one fit, complete summary rows, results and audits.

    Upstream source authentication/order is a separate responsibility. This API
    never reads a file, accepts a participant model, or loads serialized evidence.
    ``q`` has shape[S,T,R]; ``age`` contains already promoted float32 ages.
    Smaller explicit expected dimensions are exclusively for source-free tests.
    """
    x = _float32_exact(q, 3)
    ages = _float32_exact(age, 1)
    s, t, r = x.shape
    ids = [str(v) for v in subject_ids]
    rois = np.asarray(roi_ids)
    if s != expected_subjects or r != expected_rois or s < 4 or r < 7 or len(ages) != s or (ages < 0).any():
        raise PreconditionError("canonical cohort/parcel/age dimensions differ")
    if len(ids) != s or len(set(ids)) != s or any(not v for v in ids):
        raise PreconditionError("subject keys must be unique nonempty strings")
    if rois.ndim != 1 or rois.dtype.kind not in "iu" or not np.array_equal(rois, np.arange(r)):
        raise PreconditionError("ROI keys must be the canonical ordered indices")
    people = [canonical_connectome(person) for person in x]
    raw = np.stack([p["raw_r"] for p in people])
    z = np.stack([p["fisher_z"] for p in people])
    valid = np.stack([p["edge_valid"] for p in people])
    ij = people[0]["edge_roi_index"]
    group, group_valid = group_connectome(z, valid, ij, r)
    fitted = partition(group, group_valid)
    rows = summaries(z, valid, ij, fitted, ids, ages)
    if t < 2:
        for row in rows:
            row["global_status"] = "insufficient_frames"
    result = dict(status="ok", n_subjects=s, age_range=[float(min(ages)), float(max(ages))],
                  overall_connectivity_vs_age=age_endpoint(ages, [v["global_connectivity"] for v in rows], ids),
                  system_segregation_vs_age=age_endpoint(ages, [v["system_segregation"] for v in rows], ids))
    return dict(subject_id=np.asarray(ids), roi_index=rois.copy(),
                age=ages.copy(), roi_timeseries=x.astype(np.float32),
                parcel_status=np.stack([p["parcel_status"] for p in people]),
                edge_roi_index=ij, edge_valid=valid, raw_r=raw, fisher_z=z,
                group_features=group, group_valid=group_valid, partition=fitted,
                summary_rows=rows, results=result,
                audit=dict(normalized_dot_raw_r=np.stack([p["audit_raw_r"] for p in people]),
                           max_abs_r_difference=[p["audit_max_abs_r_difference"] for p in people]))
