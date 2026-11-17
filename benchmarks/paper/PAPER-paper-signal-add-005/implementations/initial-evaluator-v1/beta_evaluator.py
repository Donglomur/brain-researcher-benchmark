"""Source-grounded downstream OPM-MEG beta amplitude evaluator.

Inputs are precomputed, nonnegative 13–30 Hz Hilbert amplitudes at the author's
index and pinky source peaks. This module does not perform MEG preprocessing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import stats

TASK_ID = "PAPER-paper-signal-add-005"
SOURCE_REVISION = "0eb3a56af3d0e3a44b0f65c364e999f69cd4563f"
CHILDREN = tuple(f"sub-{i:03d}" for i in range(1, 28))
ADULTS = tuple(f"sub-{i:03d}" for i in range(101, 127))
AUTHOR_EXCLUSIONS = ("sub-120", "sub-123")
CONDITIONS = ("index", "pinky")
WINDOWS = {"active": (0.3, 0.8), "rebound": (1.0, 1.5), "rest": (2.5, 3.0)}
ENDPOINTS = ("active_fraction", "rebound_fraction", "modulation_fraction")
COVARIATES = ("retained_trials", "head_size_cm", "motion_mm")
HOLDS = [
    "Authentic full-cohort input and native numerical reference execution not performed.",
    "Raw data import, artifact/ICA masks, peak selection, beamforming and amplitude extraction require native qualification.",
    "The paper equation and pinned beta-envelope code differ in normalization order; authentic reference reconciliation remains required.",
    "Missing index_pinky_4mm_evoked_func branch remains excluded; individualized bands cannot replace this primary band.",
    "Protected reference, candidate isolation, equal access budgets, scoring tolerances and scientific qualification remain unresolved.",
    "Public access does not establish stimulus/component rights or absence of prior exposure.",
]


class ContractError(ValueError):
    """Invalid or insufficient inputs; never silently drop participants/trials."""


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < minimum:
        raise ContractError(f"{name} must be an integer >= {minimum}")
    return int(value)


def _number(value, name, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)) or not np.isfinite(value):
        raise ContractError(f"{name} must be finite numeric")
    if minimum is not None and value < minimum:
        raise ContractError(f"{name} must be >= {minimum}")
    return float(value)


def window_indices(fs, n_samples, window):
    """Match MATLAB round(seconds*fs), inclusive 1-based index endpoints.

    MATLAB's first selected sample for 0.3 s is sample 360 at 1200 Hz,
    not Python sample 360. Plotting with linspace does not change this indexing.
    """
    fs = _number(fs, "sampling_frequency_hz", 61)
    lo, hi = window
    first = int(np.floor(lo * fs + 0.5)) - 1
    last = int(np.floor(hi * fs + 0.5))
    if first < 0 or last > n_samples or first >= last:
        raise ContractError("window is outside the supplied epoch")
    return slice(first, last)


def validate_envelopes(values, fs):
    a = np.asarray(values, dtype=float)
    fs = _number(fs, "sampling_frequency_hz", 61)
    expected = int(np.floor(3.5 * fs + 0.5))
    if a.ndim != 2 or a.shape[0] < 2 or a.shape[1] != expected:
        raise ContractError(f"amplitudes must be trials x {expected} samples with >=2 retained trials")
    if not np.isfinite(a).all() or (a < 0).any():
        raise ContractError("Hilbert amplitudes must be finite and nonnegative")
    return a


def summarize_envelopes(values, fs, *, normalization="code_per_trial"):
    """Primary: per-trial fractional amplitude, then average (Tstat get_envelope).

    paper_ratio_of_means is a separately reported sensitivity. It differs when
    trial baselines differ; no source/native equivalence is asserted.
    """
    a = validate_envelopes(values, fs)
    baseline = a[:, window_indices(fs, a.shape[1], WINDOWS["rest"])].mean(axis=1)
    if (baseline <= 0).any():
        raise ContractError("every trial's mean rest amplitude must be positive")
    if normalization == "code_per_trial":
        normalized = ((a - baseline[:, None]) / baseline[:, None]).mean(axis=0)
    elif normalization == "paper_ratio_of_means":
        mean_amplitude = a.mean(axis=0)
        normalized = (mean_amplitude - baseline.mean()) / baseline.mean()
    else:
        raise ContractError("unknown normalization profile")
    active = float(normalized[window_indices(fs, a.shape[1], WINDOWS["active"])].mean())
    rebound = float(normalized[window_indices(fs, a.shape[1], WINDOWS["rebound"])].mean())
    return {"active_fraction": active, "rebound_fraction": rebound,
            "modulation_fraction": rebound - active, "rest_amplitude": float(baseline.mean()),
            "retained_trials": int(a.shape[0]), "normalization": normalization}


def _seed(seed, *keys):
    payload = json.dumps([_integer(seed, "seed"), *keys], separators=(",", ":")).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "little")


def matched_trials(index, pinky, count, seed, participant_id):
    """Fixed count for both conditions/all participants; selection is amplitude blind."""
    count = _integer(count, "matched_trial_count", 2)
    out = {}
    for condition, values in zip(CONDITIONS, (index, pinky)):
        a = np.asarray(values)
        if count > len(a):
            raise ContractError("matched trial count exceeds retained count")
        rng = np.random.default_rng(_seed(seed, participant_id, condition, "matching"))
        rows = np.sort(rng.choice(len(a), count, replace=False))
        out[condition] = (a[rows], rows.tolist())
    return out


def event_shift_control(values, fs, *, repeats, seed, participant_id, condition):
    """Circularly shift each complete envelope trial, preserving cyclic autocorrelation.

    Prospective null diagnostic: independent, uniformly sampled nonzero shifts;
    epoch wraparound and near-event shifts are retained, not tuned away.
    """
    a = validate_envelopes(values, fs)
    repeats = _integer(repeats, "event_shift_repeats", 1)
    rng = np.random.default_rng(_seed(seed, participant_id, condition, "event-shift"))
    null = []
    for _ in range(repeats):
        shifts = rng.integers(1, a.shape[1], size=len(a))
        shifted = np.stack([np.roll(row, int(s)) for row, s in zip(a, shifts)])
        null.append(summarize_envelopes(shifted, fs)["modulation_fraction"])
    observed = summarize_envelopes(a, fs)["modulation_fraction"]
    p = (1 + sum(abs(x) >= abs(observed) for x in null)) / (repeats + 1)
    return {"null_modulation_fraction": null, "observed_modulation_fraction": observed,
            "absolute_surrogate_exceedance_fraction_plus_one": float(p), "calibrated_randomization_p_value": False,
            "policy": "nonzero_independent_circular_trial_shifts"}


def ols(y, columns, names):
    """OLS with HC3 participant-level uncertainty; fail closed on rank deficiency."""
    y = np.asarray(y, dtype=float)
    z = np.asarray(columns, dtype=float)
    if z.ndim == 1:
        z = z[:, None]
    if y.ndim != 1 or z.ndim != 2 or len(y) != len(z) or z.shape[1] != len(names):
        raise ContractError("OLS dimensions do not agree")
    x = np.column_stack([np.ones(len(y)), z])
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ContractError("OLS inputs must be finite")
    if len(y) <= x.shape[1] or np.linalg.matrix_rank(x) != x.shape[1]:
        raise ContractError("OLS requires a full-rank design and positive residual degrees of freedom")
    beta, _, _, _ = np.linalg.lstsq(x, y, rcond=None)
    residual = y - x @ beta
    bread = np.linalg.inv(x.T @ x)
    leverage = np.einsum("ij,jk,ik->i", x, bread, x)
    if np.any(1 - leverage < 1e-10):
        raise ContractError("HC3 is undefined at unit leverage")
    meat = x.T @ (x * (residual / (1 - leverage))[:, None] ** 2)
    se = np.sqrt(np.maximum(0, np.diag(bread @ meat @ bread)))
    critical = float(stats.t.ppf(0.975, len(y) - x.shape[1]))
    sst = float(np.sum((y - y.mean()) ** 2))
    sse = float(residual @ residual)
    return {"terms": ["intercept", *names], "coefficients": beta.tolist(),
            "hc3_standard_errors": se.tolist(),
            "hc3_t_95_intervals": np.column_stack([beta - critical * se, beta + critical * se]).tolist(),
            "r_squared": None if sst == 0 else 1 - sse / sst,
            "residual_df": len(y) - x.shape[1], "n_participants": len(y)}


def _model_or_hold(y, columns, names):
    try:
        return {"status": "computed", **ols(y, columns, names)}
    except ContractError as exc:
        return {"status": "held", "reason": str(exc)}


def age_models(rows, *, matched=False):
    """Separate developmental child, adult, and pooled descriptive relationships.

    Covariate-adjusted models and HC3 are prospective robustness analyses, not a
    claim of reproducing an author-selected covariate model or causal age effect.
    """
    output = {}
    for group in ("children", "adults", "pooled"):
        subset = [r for r in rows if group == "pooled" or r["group"] == group]
        group_result = {}
        for condition in CONDITIONS:
            age = [r["age_years"] for r in subset]
            cov_names = ["age_years", "head_size_cm", "motion_mm"] if matched else ["age_years", *COVARIATES]
            cov = [[r["age_years"], r["head_size_cm"], r["motion_mm"]] if matched else
                   [r["age_years"], r[condition]["retained_trials"], r["head_size_cm"], r["motion_mm"]] for r in subset]
            group_result[condition] = {}
            for endpoint in ENDPOINTS:
                y = [r[condition][endpoint] for r in subset]
                group_result[condition][endpoint] = {
                    "unadjusted": _model_or_hold(y, age, ["age_years"]),
                    "adjusted": _model_or_hold(y, cov, cov_names),
                    "pearson": {"r": None, "p_two_sided": None} if len(y) < 3 or np.ptp(y) == 0 or np.ptp(age) == 0 else
                        dict(zip(("r", "p_two_sided"), map(float, stats.pearsonr(age, y)))) ,
                }
        output[group] = group_result
    return output


def group_contrasts(rows):
    """Per-finger child/adult comparison, with no averaging across fingers."""
    out = {}
    for condition in CONDITIONS:
        out[condition] = {}
        for endpoint in ENDPOINTS:
            child = [r[condition][endpoint] for r in rows if r["group"] == "children"]
            adult = [r[condition][endpoint] for r in rows if r["group"] == "adults"]
            # Explicit asymptotic/tie-corrected policy, not claimed MATLAB parity.
            u, p = stats.mannwhitneyu(child, adult, alternative="two-sided", method="asymptotic", use_continuity=True)
            out[condition][endpoint] = {"adult_minus_child_mean": float(np.mean(adult) - np.mean(child)),
                "child_u": float(u), "two_sided_asymptotic_p": float(p),
                "n_children": len(child), "n_adults": len(adult)}
    return out


def bootstrap_age(rows, *, repeats, seed):
    """Resample participants within cohorts; both fingers/outcomes stay paired."""
    repeats = _integer(repeats, "bootstrap_repeats", 2)
    rng = np.random.default_rng(_seed(seed, "participant-bootstrap"))
    strata = [[r for r in rows if r["group"] == g] for g in ("children", "adults")]
    if any(not group for group in strata):
        raise ContractError("bootstrap requires both cohorts")
    values = {c: {e: [] for e in ENDPOINTS} for c in CONDITIONS}
    for _ in range(repeats):
        sample = [group[i] for group in strata for i in rng.integers(0, len(group), len(group))]
        x = np.asarray([r["age_years"] for r in sample])
        centered = x - x.mean()
        variance = float(centered @ centered)
        if variance == 0:
            continue
        for c in CONDITIONS:
            for e in ENDPOINTS:
                y = np.asarray([r[c][e] for r in sample])
                cy = y - y.mean()
                slope = float(centered @ cy / variance)
                vy = float(cy @ cy)
                r2 = None if vy == 0 else float((centered @ cy) ** 2 / (variance * vy))
                values[c][e].append((slope, r2))
    result = {}
    for c in CONDITIONS:
        result[c] = {}
        for e in ENDPOINTS:
            pairs = values[c][e]
            slopes = [p[0] for p in pairs]
            r2s = [p[1] for p in pairs if p[1] is not None]
            result[c][e] = {"age_slope_percentile_95": None if not slopes else np.quantile(slopes, [0.025, 0.975]).tolist(),
                "r_squared_percentile_95": None if not r2s else np.quantile(r2s, [0.025, 0.975]).tolist(),
                "valid_slope_replicates": len(slopes), "valid_r_squared_replicates": len(r2s)}
    return {"policy": "prospective_stratified_paired_participant_percentile", "requested_replicates": repeats, "endpoints": result}


def age_stratified_folds(rows, n_folds=5):
    """Prospective participant-only folds, age-sorted round robin within cohort.

    No amplitudes/outcomes enter allocation. Every trial/condition follows its
    participant. This utility freezes an extension split; no decoder is trained.
    """
    n_folds = _integer(n_folds, "n_folds", 2)
    ids = [r["participant_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ContractError("duplicate participant in fold input")
    result = {}
    for group in ("children", "adults"):
        subset = sorted((r for r in rows if r["group"] == group), key=lambda r: (r["age_years"], r["participant_id"]))
        if len(subset) < n_folds:
            raise ContractError("each cohort must have at least n_folds participants")
        for i, row in enumerate(subset):
            result[row["participant_id"]] = i % n_folds
    if len(result) != len(rows):
        raise ContractError("unknown cohort in fold input")
    return result


def _required_text(row, key):
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{key} must be a nonempty provenance string")
    return value


def evaluate(manifest, arrays):
    """Evaluate all included source participants while retaining full53 ledger.

    arrays maps participant ID to {'index': trials x samples, 'pinky': ...}.
    The exact53 roster and two source-script exclusions cannot be overridden.
    """
    if manifest.get("schema_version") != 1 or manifest.get("task_id") != TASK_ID:
        raise ContractError("wrong task/schema")
    if manifest.get("source_revision") != SOURCE_REVISION or manifest.get("band_hz") != [13, 30]:
        raise ContractError("source revision and primary 13–30 Hz band are fixed")
    if manifest.get("quantity") != "hilbert_amplitude":
        raise ContractError("input quantity must be hilbert_amplitude; power is not equivalent")
    for key in ("preprocessing_provenance", "artifact_policy_provenance", "source_peak_provenance", "envelope_extraction_provenance", "metadata_provenance"):
        _required_text(manifest, key)
    fs = _number(manifest.get("sampling_frequency_hz"), "sampling_frequency_hz", 61)
    # This artifact makes no resampling/rounding claim for other acquisition rates.
    if fs != 1200:
        raise ContractError("source profile requires 1200 Hz envelopes")
    seed = _integer(manifest.get("seed"), "seed")
    repeats = _integer(manifest.get("event_shift_repeats"), "event_shift_repeats", 1)
    match_count = _integer(manifest.get("matched_trial_count"), "matched_trial_count", 2)
    records = manifest.get("participants")
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        raise ContractError("participants must be a list of records")
    ids = [r.get("participant_id") for r in records]
    if len(ids) != 53 or len(set(ids)) != 53 or set(ids) != set(CHILDREN + ADULTS):
        raise ContractError("the complete original53 participant ledger is required exactly once")
    expected_arrays = set(CHILDREN + ADULTS) - set(AUTHOR_EXCLUSIONS)
    if set(arrays) != expected_arrays:
        raise ContractError("arrays must cover exactly51 author-included subjects; exclusions remain in ledger")
    bootstrap_repeats = _integer(manifest.get("bootstrap_repeats"), "bootstrap_repeats", 2)
    rows, matched_rows, paper_rows, ledger, controls = [], [], [], [], {}
    for record in sorted(records, key=lambda r: r["participant_id"]):
        pid = record["participant_id"]
        group = "children" if pid in CHILDREN else "adults"
        if record.get("group") != group:
            raise ContractError(f"cohort mismatch for {pid}")
        if pid in AUTHOR_EXCLUSIONS:
            if record.get("included") is not False:
                raise ContractError("source exclusions must remain explicitly marked included=false")
            ledger.append({"participant_id": pid, "group": group, "status": "excluded_by_fixed_author_script", "reason_status": "paper_reports_two_adults_excluded_for_HMM_data_quality; exact_ID_reason_link_requires_native_reconciliation"})
            continue
        if record.get("included") is not True:
            raise ContractError(f"cannot silently exclude author-included participant {pid}")
        age = _number(record.get("age_years"), "age_years", 0)
        head = _number(record.get("head_size_cm"), "head_size_cm", 1)
        motion = _number(record.get("motion_mm"), "motion_mm", 0)
        base = {"participant_id": pid, "group": group, "age_years": age, "head_size_cm": head, "motion_mm": motion}
        row, matched, paper = dict(base), dict(base), dict(base)
        a = arrays[pid]
        if set(a) != set(CONDITIONS):
            raise ContractError("both own-peak index and pinky arrays are required")
        checked = {c: validate_envelopes(a[c], fs) for c in CONDITIONS}
        selections = matched_trials(checked["index"], checked["pinky"], match_count, seed, pid)
        controls[pid] = {}
        for c in CONDITIONS:
            declared = _integer(record.get(f"retained_{c}_trials"), f"retained_{c}_trials", 2)
            if declared != len(checked[c]):
                raise ContractError(f"trial-count metadata disagrees for {pid}/{c}")
            row[c] = summarize_envelopes(checked[c], fs)
            paper[c] = summarize_envelopes(checked[c], fs, normalization="paper_ratio_of_means")
            selected, indices = selections[c]
            matched[c] = summarize_envelopes(selected, fs)
            matched[c]["selected_trial_indices_zero_based"] = indices
            controls[pid][c] = event_shift_control(selected, fs, repeats=repeats, seed=seed, participant_id=pid, condition=c)
        rows.append(row)
        matched_rows.append(matched)
        paper_rows.append(paper)
        ledger.append({"participant_id": pid, "group": group, "status": "included", "retained_index_trials": len(checked["index"]), "retained_pinky_trials": len(checked["pinky"])})
    return {"schema_version": 1, "task_id": TASK_ID, "scope": "downstream_source_peak_beta_amplitude_analysis",
        "scientific_qualification": "unknown", "native_reproduction": False, "source_revision": SOURCE_REVISION,
        "population": {"original": 53, "included": 51, "children": 27, "adults": 24, "ledger": ledger},
        "semantics": {"band_hz": [13, 30], "quantity": "hilbert_amplitude", "window_seconds": WINDOWS,
            "indexing": "MATLAB_round_seconds_times_fs_inclusive_1based", "normalization": "code_per_trial_rest_fractional_change_then_trial_mean",
            "fingers_pooled": False, "primary_age_population": "pooled_27children_24adults", "covariate_models": "prospective_HC3_OLS"},
        "all_retained": {"participants": rows, "age_models": age_models(rows), "group_contrasts": group_contrasts(rows),
            "pooled_age_bootstrap": bootstrap_age(rows, repeats=bootstrap_repeats, seed=seed)},
        "matched_trials": {"count_per_condition_per_participant": match_count, "participants": matched_rows,
            "age_models": age_models(matched_rows, matched=True), "group_contrasts": group_contrasts(matched_rows),
            "pooled_age_bootstrap": bootstrap_age(matched_rows, repeats=bootstrap_repeats, seed=seed)},
        "paper_equation_sensitivity": {"participants": paper_rows, "age_models": age_models(paper_rows)},
        "event_shift_control": controls, "prospective_participant_folds": age_stratified_folds(rows),
        "holds": HOLDS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    arrays, pins = {}, []
    for row in manifest.get("participants", []):
        pid = row["participant_id"]
        if pid in AUTHOR_EXCLUSIONS:
            continue
        path = args.manifest.parent / row["envelopes_npz"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if row.get("envelopes_sha256") != digest:
            raise ContractError(f"input file digest mismatch: {pid}")
        with np.load(path, allow_pickle=False) as content:
            if set(content.files) != set(CONDITIONS):
                raise ContractError("NPZ must contain exactly index and pinky arrays")
            arrays[pid] = {c: content[c] for c in CONDITIONS}
        pins.append({"participant_id": pid, "sha256": digest, "bytes": path.stat().st_size})
    result = evaluate(manifest, arrays)
    result["input_pins"] = pins
    result["manifest_sha256"] = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
