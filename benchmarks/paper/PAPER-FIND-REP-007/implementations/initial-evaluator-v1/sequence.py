"""Pinned-code sequence-similarity variant; paper/code policy conflict stays open."""
import numpy as np
from evaluator import AREAS, numeric, source_dprime, stimulus_name


def sequence_similarity(bundle):
    """Get_sort_spk/get_seq_corr leaf1 variant, not generic noise correlation.

    Even zero-based frame trials select neurons. Odd zero-based reference
    trials split alternately to determine reference and repeat-test peaks.
    Other stimuli use all trials as in the pinned source, with no claim of
    prospective held-out evaluation. Source uses full-session zscoring.
    """
    for key in ("frame_trial", "frame_gray", "interp_spks"):
        if key not in bundle:
            raise ValueError(f"sequence endpoint requires {key}")
    index = numeric(bundle["frame_trial"], "frame_trial", 1, integer=True)
    gray = numeric(bundle["frame_gray"], "frame_gray", 1)
    nframes, ntrials = bundle["spks"].shape[1], len(bundle["trial_wall"])
    if len(index) != nframes or len(gray) != nframes or not np.isin(gray, [0, 1]).all():
        raise ValueError("sequence frame alignment/gray mask mismatch")
    if np.any(index < 0) or np.any(index >= ntrials):
        raise ValueError("frame trial outside source range")
    train = (index % 2 == 0) & (bundle["frame_move"] > 0)
    corridor, gray_mask = train & bundle["frame_corridor"].astype(bool), train & gray.astype(bool)
    first, second = stimulus_name(bundle, 2), stimulus_name(bundle, 0)
    masks = [corridor & (bundle["frame_wall"] == name) for name in (first, second)]
    if not gray_mask.any():
        raise ValueError("no training gray frames")
    dp = source_dprime(*(bundle["spks"][:, mask] for mask in masks))
    baseline = bundle["spks"][:, gray_mask].mean(axis=1)
    responsive = (bundle["spks"][:, masks[0]].mean(axis=1) > baseline) | (bundle["spks"][:, masks[1]].mean(axis=1) > baseline)
    flat = bundle["interp_spks"].reshape(len(dp), -1)
    with np.errstate(divide="ignore", invalid="ignore"):
        norm = ((flat - flat.mean(axis=1, keepdims=True)) / flat.std(axis=1, keepdims=True)).reshape(bundle["interp_spks"].shape)
    odd_reference = np.flatnonzero((bundle["trial_wall"] == first) & (np.arange(ntrials) % 2 == 1))
    reference, repeat = odd_reference[::2], odd_reference[1::2]
    if not len(reference) or not len(repeat):
        raise ValueError("sequence needs two odd-index leaf1 reference trials")
    areas = {}
    for area, ids in AREAS.items():
        eligible = responsive & np.isin(bundle["area_ids"], ids)
        candidates = dp[eligible]
        if not len(candidates) or not np.isfinite(candidates).all():
            areas[area] = {"status": "undefined_selection", "eligible_cell_count": len(candidates), "selected_cell_count": 0, "targets": {}}
            continue
        threshold = float(np.percentile(candidates, 95))
        selected = eligible & (dp >= threshold)  # Inclusive ties, as source.
        traces = norm[selected]
        ref_trace = traces[:, reference, :40].mean(axis=1)
        ref_peak = np.argsort(ref_trace, axis=1)[:, -1]
        valid_ref = np.isfinite(ref_trace).all()
        targets = {}
        for code in range(7):
            if code not in bundle["stimulus_ids"]:
                continue
            name = stimulus_name(bundle, code)
            trials = repeat if code == 2 else np.flatnonzero(bundle["trial_wall"] == name)
            if not len(trials):
                targets[str(code)] = {"trial_count": 0, "correlation": None, "status": "no_target_trials"}
                continue
            target_trace = traces[:, trials, :40].mean(axis=1)
            peak = np.argsort(target_trace, axis=1)[:, -1]
            defined = bool(valid_ref and np.isfinite(target_trace).all() and len(peak) >= 2 and np.std(ref_peak) > 0 and np.std(peak) > 0)
            targets[str(code)] = {"stimulus_name": str(name), "trial_count": len(trials),
                                  "correlation": float(np.corrcoef(ref_peak, peak)[0, 1]) if defined else None,
                                  "status": "defined" if defined else "insufficient_or_nonfinite_peak_variation",
                                  "target_peak_positions": peak.tolist() if np.isfinite(target_trace).all() else None}
        areas[area] = {"status": "source_variant_evaluated", "eligible_cell_count": len(candidates),
                       "selected_cell_count": int(selected.sum()), "dprime_percentile95": threshold,
                       "reference_peak_positions": ref_peak.tolist() if valid_ref else None, "targets": targets}
    return {"variant": "pinned_code_top5pct_leaf1_sequence", "reference_trial_indices": reference.tolist(),
            "repeat_test_trial_indices": repeat.tolist(), "train_frame_trial_parity_zero_based": 0,
            "normalization": "source full-session per-cell zscore; not prospective train-only normalization",
            "paper_code_policy_conflict_unresolved": True, "areas": areas}
