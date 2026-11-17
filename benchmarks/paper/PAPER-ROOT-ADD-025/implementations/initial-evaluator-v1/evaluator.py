"""Processed-component linear encoding/readout endpoint for Park et al. (2025).

Independent implementation of the published supplementary linear analysis.
This is not intersection information, a native MATLAB reproduction, or a grader.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

TASK = "PAPER-ROOT-ADD-025"
SOURCE_COMMIT = "8b79caa5b95fadce826ea39bf6c69828991a4b28"
ONSETS = np.array([.05, .20, .35, .50, .65, .80, 2.70, 2.85, 3., 3.15, 3.30, 3.45])
RELATIVE_TIMES = np.arange(-16, 113) / 160
CONTEXTS = {"attn": (1, 2), "choice": (3, 4)}
CLASS_NAMES = ("consistent", "inconsistent", "all")
METRIC_NAMES = ("stimulus_encoding", "estimation_encoding", "linear_stimulus_readout")
GATES = [
    "Full original participant/parcel roster and exclusions have not been validated on payloads.",
    "The 200-to-160Hz native resampling and MAT-to-packet export require numerical validation.",
    "Author PCA used all trials; released components cannot establish train-only PCA or a sealed assessment.",
    "Native MATLAB/MINT equivalence, exact figure references and tolerances are unqualified.",
    "Paper shared-information definition versus source I_min setting remains unresolved; no II is computed.",
    "Pinned code MIT license is newly evidenced; data CC BY 4.0 attribution and packet redistribution still require review.",
    "Whole-participant improvement, public exposure controls, authentic runtime and scientific qualification remain open.",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _finite_array(value: Any, name: str, ndim: int) -> np.ndarray:
    a = np.asarray(value, dtype=float)
    require(a.ndim == ndim and np.all(np.isfinite(a)), f"{name}: expected finite {ndim}D array")
    return a


def _ids(value: Any, name: str) -> np.ndarray:
    a = np.asarray(value)
    require(a.ndim == 1 and a.dtype.kind in "US", f"{name}: string vector required")
    require(len(a) > 0 and all(str(x).strip() for x in a), f"{name}: empty IDs")
    require(len(set(a.tolist())) == len(a), f"{name}: duplicate IDs")
    return a.astype(str)


def validate_behavior(behavior: dict[str, Any]) -> dict[str, np.ndarray]:
    keys = {"trial_ids", "sess", "samples", "binary_choices", "interm_cues", "estimations", "gen_means", "consistent_samples", "inconsistent_samples"}
    require(set(behavior) == keys, "behavior: exact named source fields required")
    b = {k: np.asarray(v) for k, v in behavior.items()}
    b["trial_ids"] = _ids(b["trial_ids"], "behavior.trial_ids")
    n = len(b["trial_ids"])
    for k in keys - {"trial_ids"}:
        b[k] = np.asarray(b[k], dtype=float)
        shape = (n, 12) if k.endswith("samples") or k == "samples" else (n,)
        require(b[k].shape == shape, f"behavior.{k}: expected {shape}")
        require(not np.any(np.isinf(b[k])), f"behavior.{k}: infinite values")
    require(np.all(np.isin(b["sess"], [1, 2, 3, 4])), "sessions must be 1..4")
    require(np.all(np.isin(b["binary_choices"], [-1, 1, 99])), "choices must be -1,+1,99 (missed)")
    require(np.all(np.isin(b["interm_cues"], [-1, 1])), "cues must be -1,+1")
    require(np.all(np.isfinite(b["samples"])), "samples must be finite; trial exclusions use named source fields")
    for k in ("consistent_samples", "inconsistent_samples"):
        mask = np.isfinite(b[k])
        require(np.all(b[k][mask] == b["samples"][mask]), f"{k}: nonmissing values must equal source samples")
    require(not np.any(np.isfinite(b["consistent_samples"][:, 6:]) & np.isfinite(b["inconsistent_samples"][:, 6:])), "second-interval consistency masks overlap")
    return b


def epoch_components(components: np.ndarray) -> np.ndarray:
    """160Hz [trial, PC, 801] -> [trial, sample, PC, 129].

    Pinned source uses inclusive baseline -0.5..+0.05 despite its 0s comment.
    No resampling or new PCA is performed here.
    """
    x = _finite_array(components, "components", 3)
    require(x.shape[0] > 0 and 1 <= x.shape[1] <= 15 and x.shape[2] == 801, "components require trials,1..15 PCs,801 samples (-.5..4.5s at160Hz)")
    baseline_end = int(round((ONSETS[0] + .5) * 160))
    x = x - np.mean(x[:, :, :baseline_end + 1], axis=2, keepdims=True)
    epochs = [x[:, :, int(round((o + .5) * 160)) - 16:int(round((o + .5) * 160)) + 113] for o in ONSETS]
    return np.stack(epochs, axis=1)


def source_rows(behavior: dict[str, np.ndarray], context: str, generative_limit: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    require(context in CONTEXTS, "unknown context")
    context_rows = np.flatnonzero(np.isin(behavior["sess"], CONTEXTS[context]))
    require(len(context_rows) > 0, f"no {context} observations")
    b = {k: v[context_rows] for k, v in behavior.items()}
    valid = (b["binary_choices"] != 99) & np.isfinite(b["estimations"]) & np.isfinite(b["gen_means"])
    require(generative_limit in (0, 4), "generative limit must be0 (source S11) or4 (near-zero sensitivity)")
    # MATLAB ismember(gen_means,-4:4), not merely a floating-point interval.
    if generative_limit:
        valid &= np.isin(b["gen_means"], np.arange(-4, 5))
    interm = b["interm_cues"] if context == "attn" else b["binary_choices"]
    consistency = np.zeros((len(context_rows), 12, 3), dtype=bool)
    consistency[:, :6, 0] = b["samples"][:, :6] * interm[:, None] > 0
    consistency[:, :6, 1] = b["samples"][:, :6] * interm[:, None] < 0
    consistency[:, 6:, 0] = np.isfinite(b["consistent_samples"][:, 6:])
    consistency[:, 6:, 1] = np.isfinite(b["inconsistent_samples"][:, 6:])
    consistency[:, :, 2] = True
    consistency &= valid[:, None, None]
    return context_rows, consistency, valid


def fold_assignments(groups: np.ndarray, rng: np.random.Generator, mode: str, nfolds: int = 10) -> np.ndarray:
    """Author row folds or explicitly prospective trial-grouped sensitivity."""
    require(mode in ("source_rows", "grouped_trials"), "invalid fold mode")
    keys = np.arange(len(groups)) if mode == "source_rows" else np.unique(groups)
    require(len(keys) >= nfolds, "insufficient independent groups for folds")
    keys = rng.permutation(keys)
    fold = np.empty(len(groups), dtype=int)
    for i, subset in enumerate(np.array_split(keys, nfolds)):
        mask = np.isin(np.arange(len(groups)) if mode == "source_rows" else groups, subset)
        fold[mask] = i
    return fold


def _pearson(y: np.ndarray, predictions: np.ndarray) -> np.ndarray:
    yc = y - np.mean(y)
    pc = predictions - np.mean(predictions, axis=0)
    den = np.sqrt(np.sum(yc * yc) * np.sum(pc * pc, axis=0))
    result = np.full(predictions.shape[1:], np.nan)
    # Centering an exact constant can leave rounding residue; range checks
    # prevent that residue from becoming a fabricated finite correlation.
    nonconstant = (np.ptp(y) > 0) & (np.ptp(predictions, axis=0) > 0)
    np.divide(np.sum(yc[:, None, None] * pc, axis=0), den, out=result, where=(den > 0) & nonconstant)
    return np.clip(result, -1, 1)


def cross_validated_linear(r: np.ndarray, s: np.ndarray, e: np.ndarray, folds: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return [fold, metric, PC,time] Pearson and predictions [row,2,PC,time].

    Each OLS fit uses training rows only. Predictor units are consistent at fit
    and predict; avoids source script's 1e12 fit-only scaling discrepancy.
    """
    r = _finite_array(r, "neural rows", 3)
    s, e = _finite_array(s, "stimulus", 1), _finite_array(e, "estimate", 1)
    require(len(s) == len(e) == len(r) == len(folds), "row length mismatch")
    labels = np.unique(folds)
    require(len(labels) >= 2, "at least two folds required")
    scores = np.full((len(labels), 3, r.shape[1], r.shape[2]), np.nan)
    predictions = np.full((len(r), 2, r.shape[1], r.shape[2]), np.nan)
    for j, fold in enumerate(labels):
        tr, te = folds != fold, folds == fold
        require(np.count_nonzero(tr) >= 3 and np.count_nonzero(te) >= 3, "folds require at least three training and test rows")
        train_mean = np.mean(r[tr], axis=0)
        centered = r[tr] - train_mean
        # Exact constant training features can have nonzero subtraction residue.
        constant_training = np.ptp(r[tr], axis=0) == 0
        scale = np.where(constant_training, 0., np.max(np.abs(centered), axis=0))
        z = np.divide(centered, scale, out=np.zeros_like(centered), where=scale > 0)
        ztest = np.divide(r[te] - train_mean, scale, out=np.zeros_like(r[te]), where=scale > 0)
        variance = np.sum(z * z, axis=0)
        for target_index, y in enumerate((s, e)):
            ym = np.mean(y[tr])
            target_centered = np.zeros_like(y[tr]) if np.ptp(y[tr]) == 0 else y[tr] - ym
            coefficient = np.divide(np.sum(z * target_centered[:, None, None], axis=0), variance, out=np.zeros_like(variance), where=variance > 0)
            predictions[te, target_index] = ym + ztest * coefficient
        scores[j, 0] = _pearson(s[te], predictions[te, 0])
        scores[j, 1] = _pearson(e[te], predictions[te, 1])
        scores[j, 2] = _pearson(e[te], predictions[te, 0])
    return scores, predictions


def _slope(x: np.ndarray, y: np.ndarray) -> float:
    if np.ptp(x) == 0:
        return float("nan")
    if np.ptp(y) == 0:
        return 0.
    xc = x - np.mean(x)
    scale = np.max(np.abs(xc))
    if scale == 0:
        return float("nan")
    xc = xc / scale
    return float(np.dot(xc, y - np.mean(y)) / np.dot(xc, xc) / scale)


def _stable_seed(seed: int, *identity: Any) -> int:
    return int.from_bytes(hashlib.sha256(json.dumps([seed, *identity], separators=(",", ":")).encode()).digest()[:8], "little")


def evaluate_participant(behavior: dict[str, Any], components: np.ndarray, neural_trial_ids: np.ndarray,
                         context: str, participant: str, parcel: str, *, seed: int = 0,
                         fold_mode: str = "source_rows", generative_limit: int = 0) -> dict[str, Any]:
    """Complete linear endpoint; ineligible pairs remain explicit, never dropped."""
    require(isinstance(seed, int) and not isinstance(seed, bool) and seed >= 0, "seed must be nonnegative integer")
    b = validate_behavior(behavior)
    rows, masks, _ = source_rows(b, context, generative_limit)
    ids = _ids(neural_trial_ids, "neural trial IDs")
    require(np.array_equal(ids, b["trial_ids"][rows]), "neural trial identity/order differs from context behavior")
    require(len(components) == len(rows), "component trial count mismatch")
    neural = epoch_components(components)
    output: dict[str, Any] = {"participant": participant, "parcel": parcel, "context": context,
        "fold_mode": fold_mode, "generative_limit": generative_limit, "source_context_trials": len(rows), "pairs": []}
    for pair in range(6):
        # MATLAB column-major pooling: all trials of sample A, then sample B.
        stim = b["samples"][rows, 2*pair:2*pair+2].reshape(-1, order="F")
        estimates = np.tile(b["estimations"][rows], 2)
        trial_groups = np.tile(ids, 2)
        r = np.concatenate([neural[:, 2*pair], neural[:, 2*pair+1]], axis=0)
        selected = [np.flatnonzero(masks[:, 2*pair:2*pair+2, c].reshape(-1, order="F")) for c in range(3)]
        target_n = min(len(x) for x in selected)
        record: dict[str, Any] = {"sample_positions_one_based": [2*pair+1, 2*pair+2],
            "available_rows": dict(zip(CLASS_NAMES, map(len, selected))), "matched_rows": target_n,
            "status": "eligible" if target_n >= 81 else "insufficient_support", "classes": {}}
        if target_n < 81:
            record["reason"] = "Published consistency information inclusion threshold81 retained for this linear construction; no silent lower-count fallback."
            output["pairs"].append(record)
            continue
        for c, cname in enumerate(CLASS_NAMES):
            rng = np.random.default_rng(_stable_seed(seed, participant, context, pair, cname))
            scores, slopes, split_counts, audit = [], [], [], []
            for repetition in range(5):
                take = np.sort(rng.choice(selected[c], target_n, replace=False))
                folds = fold_assignments(trial_groups[take], rng, fold_mode)
                fs, _ = cross_validated_linear(r[take], stim[take], estimates[take], folds)
                audit.append({"source_pooled_row_indices": take.tolist(), "fold_ids": folds.tolist(), "trial_ids": trial_groups[take].tolist()})
                scores.append(fs)
                slopes.append(_slope(stim[take], estimates[take]))
                split_counts.append(sum(len(set(folds[trial_groups[take] == g])) > 1 for g in np.unique(trial_groups[take])))
            score = np.stack(scores)
            timecourses = np.mean(score, axis=(0, 1, 3))  # metric,time; no nanmean exclusions
            window = (RELATIVE_TIMES >= .1) & (RELATIVE_TIMES <= .5)
            signed = np.mean(timecourses[:, window], axis=1)
            record["classes"][cname] = {
                "metric_names": METRIC_NAMES, "signed_window_mean": signed.tolist(),
                "readout_absolute_window_mean": float(abs(signed[2])), "signed_timecourses": timecourses.tolist(),
                "fold_correlations_mean_over_components": np.mean(score, axis=3).tolist(), "subsample_audit": audit,
                "undefined_correlation_count": int(np.count_nonzero(~np.isfinite(score))),
                "behavioral_signed_slope": float(np.mean(slopes)), "behavioral_absolute_slope": float(abs(np.mean(slopes))),
                "trials_split_across_folds_by_repetition": split_counts,
            }
        con, inc = (record["classes"][x] for x in CLASS_NAMES[:2])
        record["neural_consistency_contrast"] = [con["signed_window_mean"][0]-inc["signed_window_mean"][0], con["signed_window_mean"][1]-inc["signed_window_mean"][1], con["readout_absolute_window_mean"]-inc["readout_absolute_window_mean"]]
        record["behavioral_consistency_contrast"] = con["behavioral_absolute_slope"] - inc["behavioral_absolute_slope"]
        record["status"] = "unestimable_correlation" if any(x["undefined_correlation_count"] for x in record["classes"].values()) else "computed"
        output["pairs"].append(record)
    # Prospective, explicitly identified summary: arithmetic mean of pair effects
    # within each interval. Full pair-level source endpoint remains in output.
    output["interval_summaries"] = []
    for interval in range(2):
        subset = output["pairs"][interval*3:interval*3+3]
        complete = all(x["status"] == "computed" for x in subset)
        output["interval_summaries"].append({"interval": interval+1, "status": "complete" if complete else "incomplete",
            "aggregation": "prospective_equal_mean_of_three_pair_contrasts",
            "neural_contrast": np.mean([x["neural_consistency_contrast"] for x in subset], axis=0).tolist() if complete else None,
            "behavioral_contrast": float(np.mean([x["behavioral_consistency_contrast"] for x in subset])) if complete else None})
    return output


def aggregate_region(results: list[dict[str, Any]], participant: str, context: str, region: str, parcels: list[str]) -> dict[str, Any]:
    """Average signed parcel endpoints before taking absolute readout magnitude."""
    rows = [r for r in results if r["participant"] == participant and r["context"] == context and r["parcel"] in parcels]
    require(len(rows) == len(parcels) and {r["parcel"] for r in rows} == set(parcels), "region parcel roster incomplete")
    pairs = []
    for p in range(6):
        src = [r["pairs"][p] for r in rows]
        complete = all(r["status"] == "computed" for r in src)
        pair = {"sample_positions_one_based": [2*p+1,2*p+2], "status": "computed" if complete else "incomplete", "classes": {}}
        if complete:
            for cname in CLASS_NAMES:
                v = np.mean([r["classes"][cname]["signed_window_mean"] for r in src],axis=0)
                pair["classes"][cname] = {"signed_window_mean":v.tolist(), "readout_absolute_window_mean":float(abs(v[2])),
                    "behavioral_absolute_slope":src[0]["classes"][cname]["behavioral_absolute_slope"]}
            c,i = (pair["classes"][x] for x in CLASS_NAMES[:2])
            pair["neural_consistency_contrast"] = [c["signed_window_mean"][0]-i["signed_window_mean"][0], c["signed_window_mean"][1]-i["signed_window_mean"][1], c["readout_absolute_window_mean"]-i["readout_absolute_window_mean"]]
            pair["behavioral_consistency_contrast"] = c["behavioral_absolute_slope"]-i["behavioral_absolute_slope"]
        pairs.append(pair)
    intervals=[]
    for interval in range(2):
        part=pairs[interval*3:interval*3+3]
        complete=all(p["status"]=="computed" for p in part)
        intervals.append({"interval":interval+1,"status":"complete" if complete else "incomplete",
            "aggregation":"prospective_equal_mean_of_three_pair_contrasts",
            "neural_contrast":np.mean([p["neural_consistency_contrast"] for p in part],axis=0).tolist() if complete else None,
            "behavioral_contrast":float(np.mean([p["behavioral_consistency_contrast"] for p in part])) if complete else None})
    return {"participant":participant,"context":context,"region":region,"parcels":parcels,"pairs":pairs,"interval_summaries":intervals}


def _pinned_npz(base: Path, ref: dict[str, str]) -> dict[str, np.ndarray]:
    require(set(ref) == {"path", "sha256"}, "array reference requires path and sha256 only")
    path = (base / ref["path"]).resolve()
    require(path.is_relative_to(base.resolve()) and path.is_file(), "packet path must resolve inside packet directory")
    require(hashlib.sha256(path.read_bytes()).hexdigest() == ref["sha256"], f"hash mismatch: {ref['path']}")
    with np.load(path, allow_pickle=False) as archive:
        return {k: archive[k] for k in archive.files}


def _correlation(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def evaluate_packet(path: Path, *, seed: int = 0, fold_mode: str = "source_rows", generative_limit: int = 0) -> dict[str, Any]:
    packet = json.loads(path.read_text())
    require(packet.get("schema_version") == 1 and packet.get("task_id") == TASK, "wrong packet schema/task")
    require(packet.get("packet_kind") in ("generated_engineering_controls", "authorized_processed_input"), "declare packet kind")
    expected = packet["expected_participants"]
    parcels, contexts = packet["expected_parcels"], packet["contexts"]
    for values in (expected, parcels, contexts):
        require(isinstance(values, list) and len(values) > 0 and len(set(values)) == len(values) and all(isinstance(x, str) and x for x in values), "nonempty unique named rosters required")
    require(set(contexts) <= set(CONTEXTS), "invalid context roster")
    expected_provenance = "generated_reference_shape_160Hz" if packet["packet_kind"] == "generated_engineering_controls" else "author_released_all_trial_PCA_160Hz_export_unqualified"
    require(packet.get("component_provenance") == expected_provenance, "component provenance/resampling qualification must be explicit")
    subjects = packet["participants"]
    require(len(subjects) == len(expected) and set(x["id"] for x in subjects) == set(expected), "participant roster incomplete/duplicated")
    results = []
    for subject in subjects:
        b = _pinned_npz(path.parent, subject["behavior"])
        pairs = [(x["context"], x["parcel"]) for x in subject["neural"]]
        require(len(pairs) == len(contexts)*len(parcels) and set(pairs) == {(c, p) for c in contexts for p in parcels}, "context/parcel roster incomplete/duplicated")
        for neural in subject["neural"]:
            a = _pinned_npz(path.parent, neural["array"])
            require(set(a) == {"trial_ids", "components"}, "neural archive requires trial_ids and components")
            results.append(evaluate_participant(b, a["components"], a["trial_ids"], neural["context"], subject["id"], neural["parcel"], seed=seed, fold_mode=fold_mode, generative_limit=generative_limit))
    regions = packet["region_groups"]
    require(isinstance(regions, dict) and bool(regions), "named region groups required")
    for name, members in regions.items():
        require(isinstance(name,str) and bool(name) and isinstance(members,list) and len(members)>0 and len(set(members))==len(members) and set(members)<=set(parcels), "invalid region parcel membership")
    require(set(p for members in regions.values() for p in members)==set(parcels), "all declared parcels must be represented in region groups")
    regional = [aggregate_region(results,p,c,g,members) for p in expected for c in contexts for g,members in regions.items()]
    associations = []
    for context in contexts:
        for region in regions:
            for interval in (1, 2):
                rows = [(x["participant"], x["interval_summaries"][interval-1]) for x in regional if x["context"] == context and x["region"] == region]
                usable = [(p, x) for p, x in rows if x["status"] == "complete"]
                associations.append({"context": context, "region": region, "interval": interval,
                    "expected_participants": expected, "included_participants": [p for p, _ in usable],
                    "excluded_participants": [p for p, x in rows if x["status"] != "complete"],
                    "status": "complete_roster" if len(usable) == len(expected) else "incomplete_roster",
                    "behavior_vs_linear_readout_pearson": _correlation([x["behavioral_contrast"] for _, x in usable], [x["neural_contrast"][2] for _, x in usable]) if len(usable) == len(expected) else None})
    return {"schema_version": 1, "task_id": TASK, "source_commit": SOURCE_COMMIT,
        "endpoint": "supplementary_linear_encoding_readout", "packet_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "packet_kind": packet["packet_kind"], "scientific_qualification": "unknown", "full_contract_complete": False,
        "native_reproduction_qualified": False, "binary_reward_registered": False, "seed": seed,
        "fold_mode": fold_mode, "generative_limit": generative_limit, "relative_times_seconds": RELATIVE_TIMES.tolist(),
        "preserved_gates": GATES, "participant_results": results, "regional_results": regional, "prospective_participant_associations": associations}


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--fold-mode", choices=["source_rows", "grouped_trials"], default="source_rows")
    parser.add_argument("--generative-limit", type=int, choices=[0, 4], default=0)
    args = parser.parse_args()
    result = evaluate_packet(args.packet, seed=args.seed, fold_mode=args.fold_mode, generative_limit=args.generative_limit)
    args.output.write_text(json.dumps(json_safe(result), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
