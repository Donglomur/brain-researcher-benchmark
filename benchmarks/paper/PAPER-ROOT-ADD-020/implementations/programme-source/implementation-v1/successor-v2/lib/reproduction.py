"""PAPER-ROOT-ADD-020 supplied-array reproduction mathematics.

No loading, random sampling, process dispatch, admission, tolerance selection or
scientific qualification occurs here.  All calculations are PORTABLE calculations,
including the ``native_literal`` comparison arrangement.  In particular, NumPy's
solver is not MATLAB regress, and the supplied sampling receipt is provenance,
not proof that native RNG/environment qualification occurred.

Production layout is features[row, 20], PSTH[row, cell, time].  Original array
layout, units, semantic feature coordinates, identities, configuration membership,
source integrity and trusted qualification receipts must be admitted by the
owner before calling this module.  Generic mathematical kernels deliberately
accept smaller dimensions for invented engineering controls; reproduce_case
enforces the complete original stimulus and feature contracts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import re

import numpy as np

Method = Literal["STA", "OLS_INTERCEPT", "PAPER_WHITENED"]
Family = Literal["published_paired964", "native_literal"]
Mode = Literal["static", "time_course"]
METHODS = ("STA", "OLS_INTERCEPT", "PAPER_WHITENED")
FAMILIES = ("published_paired964", "native_literal")
PORTABLE_STATUS = "portable_calculation_not_literal_matlab_qualified"


class ContractError(ValueError):
    """Input/output membership or a required source contract was violated."""


def _array(value, ndim: int, name: str) -> np.ndarray:
    raw = np.asarray(value)
    if raw.ndim != ndim or raw.dtype.kind not in "fiu":
        raise ContractError(f"{name}: expected real numeric {ndim}-dimensional array")
    return np.asarray(raw, dtype=np.float64)


def _freeze(value, dtype=None) -> np.ndarray:
    result = np.array(value, dtype=dtype, copy=True)
    result.flags.writeable = False
    return result


def _ids(values, length: int, name: str) -> tuple[str, ...]:
    result = tuple(values)
    if (len(result) != length or any(not isinstance(x, str) or not x for x in result)
            or len(set(result)) != length):
        raise ContractError(f"{name}: every original position needs a unique nonempty ID")
    return result


def _digest(value: str | None, name: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ContractError(f"{name}: required supplied qualification receipt SHA-256")


def _indices(values, name: str) -> tuple[int, ...]:
    result = tuple(values)
    if any(isinstance(x, (bool, np.bool_)) or not isinstance(x, (int, np.integer))
           for x in result):
        raise ContractError(f"{name}: indices must be explicit integers, zero based")
    result = tuple(int(x) for x in result)
    if len(set(result)) != len(result):
        raise ContractError(f"{name}: duplicate rows are forbidden")
    return result


@dataclass(frozen=True)
class WindowPlan:
    mode: Mode
    times: np.ndarray
    indices: tuple[tuple[int, ...], ...]
    center_indices: tuple[int | None, ...]
    centers: tuple[float | None, ...]
    width_bins: int | None


def validate_times(times) -> np.ndarray:
    """Require an exact finite increasing uniform grid; never repair its units."""
    t = _array(times, 1, "times")
    if t.size < 2 or not np.all(np.isfinite(t)):
        raise ContractError("times: at least two finite original clock values required")
    delta = np.diff(t)
    if delta[0] <= 0 or not np.all(delta == delta[0]):
        raise ContractError("times: exact increasing uniform grid required; no interpolation")
    return _freeze(t)


def build_windows(times, mode: Mode = "time_course") -> WindowPlan:
    t = validate_times(times)
    if mode == "static":
        ind = tuple(int(x) for x in np.flatnonzero((t > 50) & (t < 300)))
        if not ind:
            raise ContractError("static: no bins strictly between 50 and 300")
        return WindowPlan(mode, t, (ind,), (None,), (None,), None)
    if mode != "time_course":
        raise ContractError("mode must be static or time_course")
    # Positive MATLAB round ties away from zero, unlike Python/NumPy bankers round.
    width = int(np.floor(50.0 / (t[1] - t[0]) + 0.5))
    if width < 1 or width % 2 != 1:
        raise ContractError("native time window requires positive odd integral width")
    centers = tuple(int(x) for x in np.flatnonzero((t > 0) & (t < 500)))
    if not centers:
        raise ContractError("time_course: no centers strictly between 0 and 500")
    half = (width - 1) // 2
    if centers[0] - half < 0 or centers[-1] + half >= len(t):
        raise ContractError("native boundary windows lack full support; cropping forbidden")
    windows = tuple(tuple(range(x-half, x+half+1)) for x in centers)
    return WindowPlan(mode, t, windows, centers, tuple(float(t[x]) for x in centers), width)


@dataclass(frozen=True)
class FeatureTransform:
    values: np.ndarray
    means: np.ndarray
    rms_divisors: np.ndarray
    sd_population: np.ndarray
    sd_sample: np.ndarray
    column_states: tuple[str, ...]


def normalize_features(raw_features) -> FeatureTransform:
    """Literal full-matrix RMS division; no row selection, centering or repair."""
    f = _array(raw_features, 2, "features")
    if not f.shape[0] or not f.shape[1]:
        raise ContractError("features: nonempty full matrix required")
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        means = f.mean(axis=0)
        rms = np.sqrt(np.mean(f ** 2, axis=0))
        values = f / rms
        sd0 = np.std(f, axis=0, ddof=0)
        sd1 = np.std(f, axis=0, ddof=1) if len(f) > 1 else np.full(f.shape[1], np.nan)
    states = tuple("zero_rms" if x == 0 else "nonfinite_rms" if not np.isfinite(x)
                   else "finite" for x in rms)
    return FeatureTransform(*(_freeze(x) for x in (values, means, rms, sd0, sd1)), states)


@dataclass(frozen=True)
class AxisResult:
    method: Method
    coefficients: np.ndarray                 # [feature, cell]
    intercepts: np.ndarray                   # OLS only; NaN otherwise
    states: tuple[str, ...]
    coefficient_defined: np.ndarray          # mathematical portable result only
    retained_response_rows: np.ndarray       # [input row, cell], excludes ONLY NaN r
    response_counts: np.ndarray
    design_ranks: np.ndarray                 # -1 if rank was not evaluated
    calculation_status: str = PORTABLE_STATUS


def axes(features, response, method: Method = "STA") -> AxisResult:
    """Generic kernel. Preserve response-only NaN deletion and unsupported states.

    OLS uses an intercept and returns feature coefficients separately. A deficient
    design is explicitly unsupported here, not silently assigned a pseudoinverse
    or ridge solution. The paper sensitivity uses an actual inverse of F'F and
    centered responses, WITHOUT feature centering; its singular case is undefined.
    Neither alternative claims native solver/warning/rank-decision parity.
    """
    if method not in METHODS:
        raise ContractError("unknown axis method")
    f = _array(features, 2, "features")
    r = _array(response, 2, "response")
    if f.shape[0] != r.shape[0] or not f.shape[1] or not r.shape[1]:
        raise ContractError("features and response require identical row axis and nonempty columns")
    d, c = f.shape[1], r.shape[1]
    coeff = np.full((d, c), np.nan)
    intercepts = np.full(c, np.nan)
    ranks = np.full(c, -1, dtype=np.int64)
    keep = ~np.isnan(r)
    counts = keep.sum(axis=0)
    defined = np.zeros(c, dtype=bool)
    states: list[str] = []
    for cell in range(c):
        x, y = f[keep[:, cell]], r[keep[:, cell], cell]
        if not np.all(np.isfinite(y)):
            states.append("nonfinite_response")
            continue
        if not np.all(np.isfinite(x)):
            states.append("nonfinite_features")
            continue
        if len(y) == 0:
            if method == "STA":
                coeff[:, cell] = 0.0  # empty native matrix product
                defined[cell] = True
            states.append("no_response_rows")
            continue
        try:
            with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
                if method == "STA":
                    b = x.T @ (y - y.mean())
                elif method == "OLS_INTERCEPT":
                    design = np.column_stack((x, np.ones(len(x))))
                    ranks[cell] = np.linalg.matrix_rank(design)
                    if ranks[cell] != d + 1:
                        states.append("unsupported_rank")
                        continue
                    solved, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
                    if rank != d + 1:
                        states.append("unsupported_rank")
                        continue
                    b, intercepts[cell] = solved[:-1], solved[-1]
                else:
                    gram = x.T @ x
                    if not np.all(np.isfinite(gram)):
                        states.append("nonfinite_gram")
                        continue
                    ranks[cell] = np.linalg.matrix_rank(gram)
                    if ranks[cell] != d:
                        states.append("undefined_inverse")
                        continue
                    b = np.linalg.inv(gram) @ (x.T @ (y-y.mean()))
        except np.linalg.LinAlgError:
            states.append("solver_failure")
            continue
        coeff[:, cell] = b
        defined[cell] = np.all(np.isfinite(b))
        states.append("nonfinite_coefficients" if not defined[cell]
                      else "zero_axis" if np.all(b == 0) else "finite")
    return AxisResult(method, _freeze(coeff), _freeze(intercepts), tuple(states),
                      _freeze(defined), _freeze(keep), _freeze(counts), _freeze(ranks))


@dataclass(frozen=True)
class CosineResult:
    values: np.ndarray
    defined: np.ndarray
    states: np.ndarray


def cosine(left, right) -> CosineResult:
    """Generic [feature, cell] signed cosine, no centering/epsilon/clipping."""
    a, b = _array(left, 2, "left axis"), _array(right, 2, "right axis")
    if a.shape != b.shape or not a.shape[0] or not a.shape[1]:
        raise ContractError("cosine operands must have identical nonempty axes")
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        aa, bb = np.sum(a*a, axis=0), np.sum(b*b, axis=0)
        values = np.sum(a*b, axis=0) / np.sqrt(aa*bb)
    finite_operands = np.all(np.isfinite(a), axis=0) & np.all(np.isfinite(b), axis=0)
    states = np.full(values.shape, "finite", dtype="U32")
    states[~np.isfinite(values)] = "nonfinite_arithmetic"
    states[(aa == 0) | (bb == 0)] = "zero_axis"
    states[~finite_operands] = "nonfinite_operand"
    return CosineResult(_freeze(values), _freeze(np.isfinite(values)), _freeze(states))


@dataclass(frozen=True)
class IndexManifest:
    unfamiliar: tuple[int, ...]
    familiar: tuple[int, ...]
    matched: tuple[int, ...]
    ancillary: tuple[int, ...]
    subsets: tuple[tuple[int, ...], ...]
    role_qualification_sha256: str
    sampling_qualification_sha256: str | None = None
    sampling_procedure: str | None = None


def validate_index_manifest(manifest: IndexManifest, stimulus_set: int, nrows: int) -> IndexManifest:
    if not isinstance(manifest, IndexManifest):
        raise ContractError("an explicit IndexManifest is required")
    if isinstance(stimulus_set, bool) or stimulus_set not in (2, 3):
        raise ContractError("only original stimulus sets 2 and 3 are supported")
    _digest(manifest.role_qualification_sha256, "role qualification")
    nref, nbase = (1000, 1036) if stimulus_set == 2 else (1008, 1080)
    if isinstance(nrows, bool) or not isinstance(nrows, (int, np.integer)) or nrows < nbase:
        raise ContractError("complete original row support is required")
    roles = tuple(_indices(getattr(manifest, name), name)
                  for name in ("unfamiliar", "familiar", "matched", "ancillary"))
    expected = (tuple(range(nref)), tuple(range(nref, nref+36)),
                () if stimulus_set == 2 else tuple(range(1044, 1080)),
                tuple(range(nbase, nrows)))
    if roles != expected:
        raise ContractError("original index roles/order or explicit ancillary row coverage differ")
    subsets = tuple(_indices(x, "subset") for x in manifest.subsets)
    if stimulus_set == 2:
        _digest(manifest.sampling_qualification_sha256, "sampling qualification")
        if manifest.sampling_procedure != "MATLAB:rng(default);randperm(1000,36);100_repetitions":
            raise ContractError("supplied native sampling procedure must be explicitly identified")
        if len(subsets) != 100 or any(len(x) != 36 or min(x) < 0 or max(x) >= 1000 for x in subsets):
            raise ContractError("set2 requires all 100 supplied 36-of-1000 ordered subsets")
    elif subsets or manifest.sampling_qualification_sha256 is not None or manifest.sampling_procedure is not None:
        raise ContractError("set3 has one matched 36-face control, no random subset schedule")
    return IndexManifest(*roles, subsets, manifest.role_qualification_sha256,
                         manifest.sampling_qualification_sha256, manifest.sampling_procedure)


@dataclass(frozen=True)
class PairResult:
    condition: str
    repetition: int
    reference_rows: tuple[int, ...]
    comparison_rows: tuple[int, ...]
    reference: AxisResult
    comparison: AxisResult
    cosine: CosineResult


@dataclass(frozen=True)
class ComparisonPartition:
    condition: str
    repetition: int
    reference_rows: tuple[int, ...]
    comparison_rows: tuple[int, ...]


def comparison_partitions(manifest: IndexManifest, stimulus_set: int, nrows: int,
                          family: Family) -> tuple[ComparisonPartition, ...]:
    """Complete production partition plan; the same plan is reused at every time."""
    manifest = validate_index_manifest(manifest, stimulus_set, nrows)
    if family not in FAMILIES:
        raise ContractError("unknown comparison family")
    if stimulus_set == 3:
        return (ComparisonPartition("familiar", 0, manifest.unfamiliar, manifest.familiar),
                ComparisonPartition("control", 0, manifest.unfamiliar, manifest.matched))
    result = []
    if family == "native_literal":
        result.append(ComparisonPartition("familiar", 0, manifest.unfamiliar, manifest.familiar))
    for rep, sub in enumerate(manifest.subsets):
        selected = set(sub)
        complement = tuple(x for x in manifest.unfamiliar if x not in selected)
        if family == "published_paired964":
            result.append(ComparisonPartition("familiar", rep, complement, manifest.familiar))
        result.append(ComparisonPartition("control", rep, complement, sub))
    return tuple(result)


def compare_partition_axes(features, response, *, reference_rows, comparison_rows,
                           method: Method = "STA", condition: str = "diagnostic",
                           repetition: int = 0) -> PairResult:
    """Generic pair kernel; original production partitions are validated separately."""
    f, r = _array(features, 2, "features"), _array(response, 2, "response")
    ref = _indices(reference_rows, "reference rows")
    cmp = _indices(comparison_rows, "comparison rows")
    if (f.shape[0] != r.shape[0] or not ref or not cmp or set(ref) & set(cmp)
            or min(ref+cmp) < 0 or max(ref+cmp) >= len(f)):
        raise ContractError("pair requires disjoint nonempty in-range rows on identical axes")
    a = axes(f[list(ref)], r[list(ref)], method)
    b = axes(f[list(cmp)], r[list(cmp)], method)
    return PairResult(condition, repetition, ref, cmp, a, b, cosine(a.coefficients, b.coefficients))


@dataclass(frozen=True)
class NativeSummary:
    per_cell: np.ndarray                     # [window, cell], subset nanmean FIRST
    subset_non_nan_counts: np.ndarray        # [window, cell]
    means: np.ndarray                        # [window]
    sem: np.ndarray                          # [window], sample SD / sqrt(actual n)
    cell_non_nan_counts: np.ndarray          # [window]
    source_default_dimension_compatible: bool


def _nanmean(value: np.ndarray, axis: int) -> tuple[np.ndarray, np.ndarray]:
    count = np.sum(~np.isnan(value), axis=axis)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        mean = np.nansum(value, axis=axis) / count
    return mean, count


def native_summary(values) -> NativeSummary:
    """Source nanmean/subset order and MATLAB singleton-std convention.

    Infinity is not treated as NaN. The plotting helper's later removal of NaN
    x/mean/SEM coordinates is NOT applied to these complete numerical outputs.
    """
    v = _array(values, 3, "cosines[window,repetition,cell]")
    if 0 in v.shape:
        raise ContractError("summary requires full nonempty axes")
    per_cell, subset_n = _nanmean(v, axis=1)
    means, cell_n = _nanmean(per_cell, axis=1)
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        residual = per_cell-means[:, None]
        # Omit ORIGINAL NaN rows only, not nonfinite arithmetic from infinity.
        sq = np.where(np.isnan(per_cell), 0.0, residual*residual).sum(axis=1)
        sem = np.sqrt(sq / np.maximum(cell_n-1, 1)) / np.sqrt(cell_n)
        sem[cell_n == 0] = np.nan
    # Original MATLAB nanmean/std choose the first nonsingleton dimension. If
    # a hypothetical one-cell time series were admitted, those plot summaries
    # collapse time instead. Keep full outputs and disclose incompatibility;
    # the literal wrapper captures that actual behavior. No such header is known.
    compatible = not (v.shape[2] == 1 and v.shape[0] > 1)
    return NativeSummary(*(_freeze(x) for x in (per_cell, subset_n, means, sem, cell_n)), compatible)


@dataclass(frozen=True)
class ConditionResult:
    condition: str
    cosines: CosineResult                    # [window, repetition, cell]
    pairs: tuple[tuple[PairResult, ...], ...] # [window][repetition], all operands
    summary: NativeSummary


@dataclass(frozen=True)
class ReproductionResult:
    configuration: str
    stimulus_set: int
    family: Family
    method: Method
    cell_ids: tuple[str, ...]
    row_ids: tuple[str, ...]
    feature_ids: tuple[str, ...]
    feature_groups: tuple[str, ...]
    windows: WindowPlan
    feature_transform: FeatureTransform
    index_manifest: IndexManifest
    averaged_responses: tuple[np.ndarray, ...]  # every original row/cell per window
    response_bin_nan_counts: tuple[np.ndarray, ...]
    conditions: tuple[ConditionResult, ...]
    calculation_status: str = PORTABLE_STATUS
    literal_native_qualified: bool = False


def reproduce_case(raw_features, psth, times, *, configuration: str, stimulus_set: int,
                   cell_ids, feature_ids, feature_groups, row_ids,
                   index_manifest: IndexManifest, mode: Mode,
                   method: Method = "STA", family: Family = "published_paired964") -> ReproductionResult:
    """Compute every original cell/window/condition/repetition from supplied data.

    The owner must independently admit source/identity/role/window manifests and
    runtime resources. Nothing in this return value authorizes execution or
    qualifies native outputs. Complete PSTH and feature rows are retained; extra
    original rows require explicit ancillary roles and participate in RMS scaling.
    """
    if family not in FAMILIES or method not in METHODS:
        raise ContractError("unknown reproduction family or method")
    if not isinstance(configuration, str) or not configuration:
        raise ContractError("configuration must be bound by the owner to the original roster")
    f, p = _array(raw_features, 2, "raw_features"), _array(psth, 3, "psth[row,cell,time]")
    if f.shape[1] != 20 or f.shape[0] != p.shape[0] or not p.shape[1]:
        raise ContractError("production requires every original row, 20 admitted features and all cells")
    cells = _ids(cell_ids, p.shape[1], "cell IDs")
    rows = _ids(row_ids, p.shape[0], "row IDs")
    features = _ids(feature_ids, 20, "feature IDs")
    groups = tuple(feature_groups)
    if groups != ("shape",)*10 + ("appearance",)*10:
        raise ContractError("features require admitted 10 shape then 10 appearance coordinates")
    manifest = validate_index_manifest(index_manifest, stimulus_set, len(f))
    partitions = comparison_partitions(manifest, stimulus_set, len(f), family)
    windows = build_windows(times, mode)
    if len(windows.times) != p.shape[2]:
        raise ContractError("PSTH time axis differs; implicit transpose/cropping forbidden")
    transformed = normalize_features(f)
    f = transformed.values
    familiar_windows: list[tuple[PairResult, ...]] = []
    control_windows: list[tuple[PairResult, ...]] = []
    averaged_responses, bin_nan_counts = [], []
    for bins in windows.indices:
        # Ordinary arithmetic mean: an included NaN is retained until per-cell
        # response-row deletion in analysis_STA; do not nanmean PSTH bins.
        with np.errstate(invalid="ignore", over="ignore"):
            response = np.mean(p[:, :, list(bins)], axis=2)
        averaged_responses.append(_freeze(response))
        bin_nan_counts.append(_freeze(np.isnan(p[:, :, list(bins)]).sum(axis=2)))
        familiar, controls = [], []
        for part in partitions:
            pair = compare_partition_axes(f, response, reference_rows=part.reference_rows,
                comparison_rows=part.comparison_rows, method=method, condition=part.condition,
                repetition=part.repetition)
            (familiar if part.condition == "familiar" else controls).append(pair)
        familiar_windows.append(tuple(familiar))
        control_windows.append(tuple(controls))
    conditions = []
    for label, nested in (("familiar", familiar_windows), ("control", control_windows)):
        values = _freeze([[pair.cosine.values for pair in w] for w in nested])
        defined = _freeze([[pair.cosine.defined for pair in w] for w in nested])
        states = _freeze([[pair.cosine.states for pair in w] for w in nested])
        conditions.append(ConditionResult(label, CosineResult(values, defined, states),
                                           tuple(nested), native_summary(values)))
    return ReproductionResult(configuration, stimulus_set, family, method, cells, rows, features,
                              groups, windows, transformed, manifest, tuple(averaged_responses),
                              tuple(bin_nan_counts), tuple(conditions))


@dataclass(frozen=True)
class Discrepancy:
    expected_positions: int
    expected_defined: int
    expected_undefined: int
    mask_equal: bool
    candidate_finite_on_support: bool
    scorable: bool
    mse: float | None
    maximum_absolute_error: float | None
    state: str


def compare_cosines(candidate: CosineResult, expected: CosineResult) -> Discrepancy:
    """Compare fixed independently qualified support; NEVER infer it from candidate.

    This diagnostic does not weight a whole study, choose a tolerance or establish
    qualification. Shape/type errors refuse; mask differences are explicit failed
    discrepancies. An all-undefined required configuration remains unscorable.
    """
    cv, ev = np.asarray(candidate.values), np.asarray(expected.values)
    cm, em = np.asarray(candidate.defined), np.asarray(expected.defined)
    if cv.shape != ev.shape or cm.shape != ev.shape or em.shape != ev.shape:
        raise ContractError("candidate and qualified reference must retain identical full shapes")
    if cm.dtype.kind != "b" or em.dtype.kind != "b" or cv.dtype.kind not in "fiu" or ev.dtype.kind not in "fiu":
        raise ContractError("cosine values must be real and masks boolean")
    if not np.array_equal(em, np.isfinite(ev)):
        raise ContractError("reference mask contradicts its source-defined cosine values")
    n = int(em.sum())
    equal = bool(np.array_equal(cm, em))
    candidate_consistent = bool(np.array_equal(cm, np.isfinite(cv)))
    finite = bool(np.all(np.isfinite(cv[em])))
    scorable = equal and candidate_consistent and finite and n > 0
    state = ("mask_mismatch" if not equal else "candidate_mask_value_mismatch" if not candidate_consistent
             else "candidate_nonfinite" if not finite else "no_defined_support" if n == 0 else "scorable")
    mse = maximum = None
    if scorable:
        with np.errstate(over="ignore", invalid="ignore"):
            delta = cv[em]-ev[em]
            mse, maximum = float(np.mean(delta*delta)), float(np.max(np.abs(delta)))
        if not np.isfinite(mse) or not np.isfinite(maximum):
            scorable, state, mse, maximum = False, "nonfinite_discrepancy", None, None
    return Discrepancy(ev.size, n, ev.size-n, equal, finite, scorable, mse, maximum, state)


def coefficient_discrepancy(candidate: AxisResult, expected: AxisResult) -> Discrepancy:
    """Separate raw coefficient fidelity from scale-invariant signed cosine."""
    if candidate.method != expected.method:
        raise ContractError("coefficient methods differ")
    a, b = candidate.coefficients, expected.coefficients
    if a.shape != b.shape:
        raise ContractError("coefficient dimensions differ")
    # Reuse the support-safe arithmetic without reinterpreting coefficients as
    # cosines: masks here are individual finite coefficients, not cell masks.
    return compare_cosines(CosineResult(a, np.isfinite(a), np.asarray(candidate.states)),
                           CosineResult(b, np.isfinite(b), np.asarray(expected.states)))
