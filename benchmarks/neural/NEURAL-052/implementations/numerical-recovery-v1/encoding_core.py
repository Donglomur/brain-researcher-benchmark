"""Pure numerical reference for the prospective NEURAL-052 property task.

This module performs no I/O. It is a new, frozen benchmark analysis, not a
reproduction of the source notebook's in-sample OLS. ``analyze`` accepts only
already joined, complete inputs. The caller owns image-descriptor provenance,
native voxel identity, source integrity and the derivation of within-run
position from the *complete* stimulus sequence.

The primary is an equal-voxel mean of pooled held-out incremental-variance
ratios. Any zero-SST voxel makes that full-ROI primary undefined; the explicitly
named defined-voxel diagnostic does not replace it. Two separate secondary
estimands pool errors before division: unweighted, and weighted to equalize
coarse training-reliability bins between ROIs. Their paired difference compares
like estimands. Neither is a corrected macro primary or noise-ceiling match.

Bootstrap draws resample concepts, preserving all twelve repetitions and
sharing a schedule across people/ROIs. They reuse fixed held-out predictions:
no refitting, voxel-independent inference, population inference or favorable
discarding/redrawing of undefined replicates is performed.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any

import numpy as np


POLICY = "neural052_property_increment_draft_v1"
CONCEPT_SEED = 52052
BOOTSTRAP_SEED = 52053
RIDGE = 1.0
SUBJECTS = ("01", "02", "03")
ROIS = ("V1", "IT")
METRICS = ("animacy_given_size", "size_given_animacy", "joint")
MODELS = ("base", "animacy", "size", "both")
METHODS = ("macro_primary", "unweighted_pooled", "reliability_weighted_pooled",
           "reliability_adjustment")
SESSION_BLOCKS = ((1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12))
BIN_LABELS = ("[-1,0)", "[0,0.25)", "[0.25,0.5)", "[0.5,0.75)", "[0.75,1]")
VOXEL_BLOCK = 256


class CoreError(ValueError):
    """Invalid inputs or unsupported numerical arithmetic, never a low score."""


def _int(value: Any, name: str, minimum: int = 0) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise CoreError(f"{name} must be an integer")
    value = int(value)
    if value < minimum:
        raise CoreError(f"{name} below minimum")
    return value


def _finite_array(value: Any, name: str, ndim: int) -> np.ndarray:
    a = np.asarray(value)
    if a.ndim != ndim or a.dtype.kind not in "iuf":
        raise CoreError(f"{name} must be a real numeric {ndim}-D array")
    try:
        a = np.asarray(a, dtype=np.float64)
    except (ValueError, OverflowError) as exc:
        raise CoreError(f"{name} cannot be represented as float64") from exc
    if not np.isfinite(a).all():
        raise CoreError(f"{name} must be finite; no implicit row/voxel exclusion")
    return a


def concept_folds(concepts: list[str]) -> dict[str, int]:
    """Five deterministic concept folds, independent of responses/labels."""
    if len(concepts) < 5 or len(set(concepts)) != len(concepts):
        raise CoreError("need at least five distinct concepts")
    if any(not isinstance(c, str) or not c or "\0" in c for c in concepts):
        raise CoreError("concept IDs must be nonempty NUL-free strings")
    ordered = sorted(concepts, key=lambda c: (
        hashlib.sha256((str(CONCEPT_SEED) + "\0" + c).encode("utf-8")).digest(), c))
    return {c: i % 5 for i, c in enumerate(ordered)}


def split_indices(rows: list[dict], folds: dict[str, int]) -> list[dict]:
    """Intersection holdouts: train excludes both query concepts and sessions."""
    result = []
    concept = np.array([folds[r["concept"]] for r in rows], dtype=np.int64)
    session = np.array([r["session"] for r in rows], dtype=np.int64)
    for fold in range(5):
        for block in SESSION_BLOCKS:
            in_block = np.isin(session, block)
            train = np.flatnonzero((concept != fold) & ~in_block)
            query = np.flatnonzero((concept == fold) & in_block)
            if not len(train) or not len(query):
                raise CoreError("empty training or query split")
            result.append({"concept_fold": fold, "heldout_sessions": list(block),
                           "train": train, "query": query})
    return result


def _column_mean(a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Exact constants center to zero, including non-binary decimals.

    This is equality detection, not a tolerance or near-constant exclusion.
    Ordinary summation can move mean([0.1, ...]) away from its identical input
    value and falsely create response SST or Pearson variation.
    """
    if not len(a):
        raise CoreError("cannot center an empty training array")
    constant = (a == a[0]).all(axis=0)
    mean = a[0].copy()
    mean[~constant] = a[:, ~constant].mean(axis=0)
    return mean, constant


def scale_predictors(train: np.ndarray, query: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Population SD and mean are fitted only on training rows, once per fold."""
    train = _finite_array(train, "training predictors", 2)
    query = _finite_array(query, "query predictors", 2)
    if not len(train) or train.shape[1] != query.shape[1]:
        raise CoreError("predictor shape mismatch")
    mean, _ = _column_mean(train)
    scale = np.sqrt(np.mean((train - mean) ** 2, axis=0))
    scale = np.where(scale == 0, 1.0, scale)
    return (train - mean) / scale, (query - mean) / scale, mean, scale


def ridge_predict(train_x: np.ndarray, query_x: np.ndarray, train_y: np.ndarray) -> np.ndarray:
    """Fixed lambda=1 ridge with an unpenalized intercept; useful for controls."""
    train_x = _finite_array(train_x, "ridge train X", 2)
    query_x = _finite_array(query_x, "ridge query X", 2)
    train_y = _finite_array(train_y, "ridge train Y", 2)
    if len(train_y) != len(train_x) or train_x.shape[1] != query_x.shape[1]:
        raise CoreError("ridge shape mismatch")
    # Centering here makes the intercept convention explicit even for callers
    # supplying matrices not produced by scale_predictors.
    xm, _ = _column_mean(train_x)
    ym, _ = _column_mean(train_y)
    xc = train_x - xm
    beta = np.linalg.solve(xc.T @ xc + RIDGE * np.eye(xc.shape[1]), xc.T @ (train_y - ym))
    return ym + (query_x - xm) @ beta


def raw_reliability(y: np.ndarray, rows: list[dict], train: np.ndarray,
                    training_concepts: list[str]) -> np.ndarray:
    """Raw Pearson across training concepts, first four vs last four sessions."""
    lookup = {(rows[i]["concept"], rows[i]["session"]): int(i) for i in train}
    sessions = sorted({rows[i]["session"] for i in train})
    if len(sessions) != 8:
        raise CoreError("reliability needs exactly eight training sessions")
    early = np.array([[lookup[(c, s)] for s in sessions[:4]] for c in training_concepts])
    late = np.array([[lookup[(c, s)] for s in sessions[4:]] for c in training_concepts])
    a, b = y[early].mean(axis=1), y[late].mean(axis=1)
    am, constant_a = _column_mean(a)
    bm, constant_b = _column_mean(b)
    a, b = a - am, b - bm
    aa, bb = np.sum(a * a, axis=0), np.sum(b * b, axis=0)
    ok = ~constant_a & ~constant_b & (aa > 0) & (bb > 0)
    result = np.full(y.shape[1], np.nan)
    result[ok] = np.sum(a[:, ok] * b[:, ok], axis=0) / np.sqrt(aa[ok] * bb[ok])
    # Only correct floating point roundoff at the mathematical Pearson bounds.
    if np.any(np.abs(result[ok]) > 1 + 1e-12):
        raise CoreError("Pearson arithmetic outside its mathematical range")
    result[ok] = np.clip(result[ok], -1.0, 1.0)
    return result


def shared_bin_weights(reliability: np.ndarray, masks: dict[str, np.ndarray]) -> tuple[dict[str, np.ndarray], dict]:
    """Equal common-bin mass, equal voxel mass within each common finite bin.

    Undefined and non-common bins receive no *secondary* weight and are counted.
    They remain in the primary and unweighted pooled comparator. A fold with no
    common finite bin makes the complete reliability control unsupported.
    """
    reliability = np.asarray(reliability, dtype=np.float64)
    finite = np.isfinite(reliability)
    if np.any(np.abs(reliability[finite]) > 1):
        raise CoreError("reliability outside [-1,1]")
    bins = np.full(len(reliability), -1, dtype=np.int64)
    bins[finite] = np.searchsorted([0.0, .25, .5, .75], reliability[finite], side="right")
    counts = {r: [int(np.sum(masks[r] & (bins == k))) for k in range(5)] for r in ROIS}
    common = [k for k in range(5) if all(counts[r][k] > 0 for r in ROIS)]
    weights = {r: np.zeros(len(reliability), dtype=np.float64) for r in ROIS}
    for r in ROIS:
        for k in common:
            weights[r][masks[r] & (bins == k)] = 1.0 / (len(common) * counts[r][k])
    support = {
        "supported": bool(common), "common_bins": [BIN_LABELS[k] for k in common],
        "bin_counts": {r: dict(zip(BIN_LABELS, counts[r])) for r in ROIS},
        "undefined_reliability_voxels": {r: int(np.sum(masks[r] & ~finite)) for r in ROIS},
        "weighted_voxels": {r: int(np.sum(weights[r] > 0)) for r in ROIS},
        "zero_weight_voxels": {r: int(np.sum(masks[r] & (weights[r] == 0))) for r in ROIS},
    }
    return weights, support


def bootstrap_multiplicities(concepts: list[str], draws: int) -> np.ndarray:
    """Shared PCG64 concept-level schedule; no outcome-dependent resampling."""
    draws = _int(draws, "draws", 1)
    rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    indices = rng.integers(0, len(concepts), size=(draws, len(concepts)))
    counts = np.zeros((draws, len(concepts)), dtype=np.uint32)
    for i, row in enumerate(indices):
        counts[i] = np.bincount(row, minlength=len(concepts))
    return counts


def _interval(point: float | None, values: np.ndarray) -> dict:
    good = np.isfinite(values)
    result = {"requested_draws": len(values), "defined_draws": int(good.sum()),
              "undefined_draws": int((~good).sum()), "level": .95,
              "quantile_method": "linear", "lower": None, "upper": None}
    if point is None:
        result["status"] = "undefined_point_estimate"
    elif not good.all():
        result["status"] = "undefined_resample_support"
    else:
        result.update(status="defined", lower=float(np.quantile(values, .025, method="linear")),
                      upper=float(np.quantile(values, .975, method="linear")))
    return result


def _summary(point: float | None, values: np.ndarray, reason: str = "undefined_support") -> dict:
    if point is not None and not math.isfinite(point):
        raise CoreError("nonfinite derived scalar")
    return {"status": "defined" if point is not None else reason, "value": point,
            "conditional_concept_bootstrap": _interval(point, values)}


def _ratio(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    answer = np.full(np.shape(numerator), np.nan, dtype=np.float64)
    np.divide(numerator, denominator, out=answer, where=denominator > 0)
    return answer


def aggregate_contributions(numerator: np.ndarray, sst: np.ndarray,
                            masks: dict[str, np.ndarray], counts: np.ndarray) -> tuple[dict, dict]:
    """Aggregate per-concept errors, retaining every voxel and undefined draw.

    numerator has metric × concept × voxel axes; sst is concept × voxel.
    This is also exposed for independently hand-computed generated controls.
    """
    totals = sst.sum(axis=0)
    nums = numerator.sum(axis=1)
    result, draws_out = {}, {}
    for roi in ROIS:
        mask = masks[roi]
        v = int(mask.sum())
        if not v:
            raise CoreError("empty ROI")
        positive = totals[mask] > 0
        metrics, draws_for_roi = {}, {}
        for mi, name in enumerate(METRICS):
            individual = _ratio(nums[mi, mask], totals[mask])
            value = float(individual.mean()) if positive.all() else None
            sums = np.zeros(len(counts), dtype=np.float64)
            defined_counts = np.zeros(len(counts), dtype=np.int64)
            selected = np.flatnonzero(mask)
            for start in range(0, len(selected), VOXEL_BLOCK):
                ix = selected[start:start + VOXEL_BLOCK]
                den = counts @ sst[:, ix]
                num = counts @ numerator[mi][:, ix]
                rat = _ratio(num, den)
                ok = np.isfinite(rat)
                sums += np.where(ok, rat, 0.0).sum(axis=1)
                defined_counts += ok.sum(axis=1)
            boot = np.where(defined_counts == v, sums / v, np.nan)
            metrics[name] = _summary(value, boot, "undefined_voxel_sst")
            metrics[name]["defined_voxel_mean_diagnostic"] = (
                float(individual[positive].mean()) if positive.any() else None)
            draws_for_roi[name] = boot
        result[roi] = {"support": {"all_voxels": v, "positive_sst_voxels": int(positive.sum()),
                                    "zero_sst_voxels": int((~positive).sum())}, "metrics": metrics}
        draws_out[roi] = draws_for_roi
    return result, draws_out


def _pooled(numerators: dict, denominators: dict, counts: np.ndarray,
            supported: bool = True) -> tuple[dict, dict]:
    result, draw_result = {}, {}
    for roi in ROIS:
        den = denominators[roi]
        total_den = float(den.sum())
        result[roi], draw_result[roi] = {}, {}
        for mi, metric in enumerate(METRICS):
            num = numerators[roi][mi]
            value = float(num.sum() / total_den) if supported and total_den > 0 else None
            boot = _ratio(counts @ num, counts @ den) if supported else np.full(len(counts), np.nan)
            reason = "undefined_zero_total_sst" if supported else "undefined_common_reliability_bins"
            result[roi][metric] = _summary(value, boot, reason)
            draw_result[roi][metric] = boot
    return result, draw_result


def _difference(a: dict, adraws: dict, b: dict, bdraws: dict) -> tuple[dict, dict]:
    result, bootresult = {}, {}
    for metric in METRICS:
        av, bv = a[metric]["value"], b[metric]["value"]
        value = float(av - bv) if av is not None and bv is not None else None
        boot = adraws[metric] - bdraws[metric]
        result[metric] = _summary(value, boot)
        bootresult[metric] = boot
    return result, bootresult


def _features(features: dict, strict: bool) -> tuple[list[str], dict, list[str]]:
    if not isinstance(features, dict) or (strict and len(features) != 100):
        raise CoreError("strict panel requires exactly 100 concept feature records")
    concepts = list(features)
    concept_folds(concepts)  # validates identities before ordering or fitting
    concepts.sort()
    fixed, images, dimension = {}, set(), None
    for c in concepts:
        f = features[c]
        if not isinstance(f, dict) or set(f) != {"image", "image_features", "animacy", "size"}:
            raise CoreError("feature record fields differ from contract")
        image = f["image"]
        if not isinstance(image, str) or not image or image in images:
            raise CoreError("one distinct nonempty image ID per concept required")
        images.add(image)
        image_features = _finite_array(f["image_features"], "image features", 1)
        if not len(image_features) or (dimension is not None and len(image_features) != dimension):
            raise CoreError("image feature dimensions differ")
        dimension = len(image_features)
        if any(isinstance(f[k], (bool, np.bool_)) for k in ("animacy", "size")):
            raise CoreError("semantic ratings must be numeric, not boolean")
        semantic = _finite_array([f["animacy"], f["size"]], "semantic labels", 1)
        if not 1 <= semantic[0] <= 7 or not 0 <= semantic[1] <= 519:
            raise CoreError("semantic labels outside source rating ranges")
        fixed[c] = np.concatenate([image_features, semantic])
    names = ["session", "run", "within_run_position"] + [f"image_{i}" for i in range(dimension)]
    return concepts, fixed, names + ["animacy", "size"]


def _subject(subject: dict, concepts: list[str], features: dict, fixed: dict,
             strict: bool) -> tuple[str, np.ndarray, list[dict], dict, np.ndarray]:
    if not isinstance(subject, dict) or set(subject) != {"subject_id", "responses", "voxel_ids", "roi_masks", "rows"}:
        raise CoreError("subject fields differ from contract")
    sid = subject["subject_id"]
    if not isinstance(sid, str) or not sid:
        raise CoreError("invalid subject ID")
    y = _finite_array(subject["responses"], "responses", 2)
    rows = subject["rows"]
    if not isinstance(rows, list) or len(rows) != len(concepts) * 12 or len(y) != len(rows):
        raise CoreError("complete concept-by-12-session panel required")
    ids = subject["voxel_ids"]
    if not isinstance(ids, list) or len(ids) != y.shape[1]:
        raise CoreError("voxel identity length mismatch")
    if any(isinstance(v, bool) or not isinstance(v, (str, int)) for v in ids):
        raise CoreError("voxel IDs must be strings or integers")
    if len({(type(v).__name__, v) for v in ids}) != len(ids):
        raise CoreError("duplicate within-person voxel identities")
    if not isinstance(subject["roi_masks"], dict) or set(subject["roi_masks"]) != set(ROIS):
        raise CoreError("need precisely V1 and IT masks")
    masks = {}
    for r in ROIS:
        a = np.asarray(subject["roi_masks"][r])
        if a.dtype.kind != "b" or a.shape != (y.shape[1],) or not a.any():
            raise CoreError("ROI mask must be nonempty boolean vector")
        masks[r] = a
    if not (masks["V1"] | masks["IT"]).all():
        raise CoreError("supplied response columns must be exactly the ROI union")
    keys, tids = set(), set()
    cset = set(concepts)
    for r in rows:
        if not isinstance(r, dict) or set(r) != {"concept", "image", "session", "run", "trial_id", "within_run_position"}:
            raise CoreError("row fields differ from contract")
        if not isinstance(r["concept"], str) or r["concept"] not in cset:
            raise CoreError("row concept absent from complete feature panel")
        if r["image"] != features[r["concept"]]["image"]:
            raise CoreError("concept/image identity mismatch")
        session = _int(r["session"], "session", 1)
        if session > 12:
            raise CoreError("session outside 1..12")
        _int(r["run"], "run")
        _int(r["within_run_position"], "within_run_position")
        tid = _int(r["trial_id"], "trial_id")
        if strict and tid >= 9840:
            raise CoreError("trial ID outside complete native 9840-row sequence")
        key = (r["concept"], session)
        if key in keys or tid in tids:
            raise CoreError("duplicate concept/session or trial identity")
        keys.add(key)
        tids.add(tid)
    # Canonical reduction order makes ordinary row permutations immaterial.
    order = sorted(range(len(rows)), key=lambda i: (rows[i]["concept"], rows[i]["session"]))
    rows = [rows[i] for i in order]
    y = y[order]
    x = np.array([[r["session"], r["run"], r["within_run_position"], *fixed[r["concept"]]]
                  for r in rows], dtype=np.float64)
    if not np.isfinite(x).all():
        raise CoreError("predictors cannot be represented as finite float64")
    return sid, y, rows, masks, x


def _one(subject: dict, concepts: list[str], features: dict, fixed: dict,
         feature_names: list[str], counts: np.ndarray, folds: dict, strict: bool) -> tuple[dict, dict]:
    sid, y, rows, masks, x = _subject(subject, concepts, features, fixed, strict)
    ci = {c: i for i, c in enumerate(concepts)}
    row_ci = np.array([ci[r["concept"]] for r in rows], dtype=np.int64)
    c, v = len(concepts), y.shape[1]
    num = np.zeros((3, c, v), dtype=np.float64)
    sst = np.zeros((c, v), dtype=np.float64)
    weighted_num = {r: np.zeros((3, c), dtype=np.float64) for r in ROIS}
    weighted_den = {r: np.zeros(c, dtype=np.float64) for r in ROIS}
    fold_support = []
    supported = True
    base = list(range(x.shape[1] - 2))
    columns = {"base": base, "animacy": base + [x.shape[1] - 2],
               "size": base + [x.shape[1] - 1], "both": list(range(x.shape[1]))}
    for split in split_indices(rows, folds):
        train, query = split["train"], split["query"]
        train_concepts = sorted({rows[i]["concept"] for i in train})
        query_concepts = sorted({rows[i]["concept"] for i in query})
        tx, qx, _, _ = scale_predictors(x[train], x[query])
        constant = (x[train] == x[train][0]).all(axis=0)
        reliability = raw_reliability(y, rows, train, train_concepts)
        weights, rel_support = shared_bin_weights(reliability, masks)
        supported = supported and rel_support["supported"]
        gains, query_design = {}, {}
        # Fixed training design across voxel blocks; response means remain local
        # to this participant/fold, and no voxel identities cross participants.
        for model in MODELS:
            design = tx[:, columns[model]]
            center, _ = _column_mean(design)
            design = design - center
            gains[model] = np.linalg.solve(design.T @ design + RIDGE * np.eye(design.shape[1]), design.T)
            query_design[model] = qx[:, columns[model]] - center
        query_codes = row_ci[query]
        unique_codes = sorted(set(query_codes.tolist()))
        for start in range(0, v, VOXEL_BLOCK):
            stop = min(start + VOXEL_BLOCK, v)
            ty, qy = y[train, start:stop], y[query, start:stop]
            mean, _ = _column_mean(ty)
            centered = ty - mean
            errors = {}
            for model in MODELS:
                pred = mean + query_design[model] @ (gains[model] @ centered)
                errors[model] = (qy - pred) ** 2
            fold_sst = (qy - mean) ** 2
            differences = np.stack((errors["size"] - errors["both"],
                                    errors["animacy"] - errors["both"],
                                    errors["base"] - errors["both"]))
            for code in unique_codes:
                ix = query_codes == code
                dn = differences[:, ix, :].sum(axis=1)
                dd = fold_sst[ix].sum(axis=0)
                num[:, code, start:stop] += dn
                sst[code, start:stop] += dd
                for r in ROIS:
                    weighted_num[r][:, code] += dn @ weights[r][start:stop]
                    weighted_den[r][code] += dd @ weights[r][start:stop]
        fold_support.append({"concept_fold": split["concept_fold"],
                             "heldout_sessions": split["heldout_sessions"],
                             "training_rows": len(train), "query_rows": len(query),
                             "training_concepts": len(train_concepts), "query_concepts": len(query_concepts),
                             "constant_training_predictors": [feature_names[i] for i in np.flatnonzero(constant)],
                             "reliability": rel_support})
    if not np.isfinite(num).all() or not np.isfinite(sst).all():
        raise CoreError("unsupported nonfinite held-out error arithmetic")
    primary, pdraw = aggregate_contributions(num, sst, masks, counts)
    un_num = {r: num[:, :, masks[r]].sum(axis=2) for r in ROIS}
    un_den = {r: sst[:, masks[r]].sum(axis=1) for r in ROIS}
    unweighted, udraw = _pooled(un_num, un_den, counts)
    weighted, wdraw = _pooled(weighted_num, weighted_den, counts, supported)
    adjustment, adraw = {}, {}
    for r in ROIS:
        adjustment[r], adraw[r] = _difference(weighted[r], wdraw[r], unweighted[r], udraw[r])
    roi_metrics = {"macro_primary": {r: primary[r]["metrics"] for r in ROIS},
                   "unweighted_pooled": unweighted, "reliability_weighted_pooled": weighted,
                   "reliability_adjustment": adjustment}
    all_draws = {"macro_primary": pdraw, "unweighted_pooled": udraw,
                 "reliability_weighted_pooled": wdraw, "reliability_adjustment": adraw}
    contrasts, contrast_draws = {}, {}
    for method in METHODS:
        contrasts[method], contrast_draws[method] = _difference(
            roi_metrics[method]["IT"], all_draws[method]["IT"],
            roi_metrics[method]["V1"], all_draws[method]["V1"])
    report = {"subject_id": sid, "rows": len(rows),
              "voxel_support": {r: primary[r]["support"] for r in ROIS},
              "roi_overlap_voxels": int(np.sum(masks["V1"] & masks["IT"])),
              "roi_metrics": roi_metrics, "it_minus_v1": contrasts,
              "reliability_control_support": {"all_folds_supported": supported,
                  "folds_total": len(fold_support),
                  "folds_with_common_bins": sum(int(f["reliability"]["supported"]) for f in fold_support)},
              "fold_support": fold_support}
    return report, {"roi_metrics": all_draws, "it_minus_v1": contrast_draws}


def _mean_summary(summaries: list[dict], draws: list[np.ndarray]) -> dict:
    available = [s["value"] is not None for s in summaries]
    value = float(np.mean([s["value"] for s in summaries])) if all(available) else None
    boots = np.mean(np.stack(draws), axis=0)
    result = _summary(value, boots, "undefined_participant_support")
    result["participants_total"] = len(summaries)
    result["participants_defined"] = sum(available)
    return result


def analyze(subjects: list[dict], concept_features: dict, draws: int = 1000,
            strict: bool = True) -> dict:
    """Compute the declared analysis from caller-owned complete joined arrays.

    ``strict=False`` is exclusively for generated source controls: it permits a
    smaller number of concepts/participants and fewer bootstrap draws. It does
    not permit incomplete concept×12-session panels or altered model rules.
    The production entry point must retain ``strict=True`` and 1,000 draws.
    """
    if type(strict) is not bool or not isinstance(subjects, list) or not subjects:
        raise CoreError("invalid analysis arguments")
    draws = _int(draws, "draws", 1)
    if strict and draws != 1000:
        raise CoreError("strict protocol requires exactly 1000 bootstrap draws")
    ids = [s.get("subject_id") for s in subjects if isinstance(s, dict)]
    if len(ids) != len(subjects) or any(not isinstance(s, str) or not s for s in ids) or len(set(ids)) != len(ids):
        raise CoreError("participant identities must be distinct")
    if strict and set(ids) != set(SUBJECTS):
        raise CoreError("strict protocol requires all three participants 01/02/03")
    concepts, fixed, feature_names = _features(concept_features, strict)
    folds = concept_folds(concepts)
    counts = bootstrap_multiplicities(concepts, draws)
    reports, private_draws = [], []
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            for subject in sorted(subjects, key=lambda s: s["subject_id"]):
                report, boot = _one(subject, concepts, concept_features, fixed, feature_names, counts, folds, strict)
                reports.append(report)
                private_draws.append(boot)
            group_roi, group_contrasts = {}, {}
            for method in METHODS:
                group_roi[method] = {}
                for roi in ROIS:
                    group_roi[method][roi] = {m: _mean_summary(
                        [r["roi_metrics"][method][roi][m] for r in reports],
                        [d["roi_metrics"][method][roi][m] for d in private_draws]) for m in METRICS}
                group_contrasts[method] = {m: _mean_summary(
                    [r["it_minus_v1"][method][m] for r in reports],
                    [d["it_minus_v1"][method][m] for d in private_draws]) for m in METRICS}
    except (FloatingPointError, np.linalg.LinAlgError, OverflowError) as exc:
        raise CoreError("unsupported numerical arithmetic; no scientific score assigned") from exc
    return {
        "policy": POLICY, "strict_benchmark_panel": strict,
        "cohort": {"subject_ids": sorted(ids), "concept_count": len(concepts), "sessions": list(range(1, 13))},
        "split": {"concept_seed": CONCEPT_SEED, "concept_folds": folds,
                  "session_blocks": [list(b) for b in SESSION_BLOCKS], "query_coverage": "each row exactly once"},
        "model": {"ridge_lambda": RIDGE, "intercept": "unpenalized", "predictor_scale": "training population SD",
                  "constant_scale": 1.0, "feature_order": feature_names, "response_transformation": "training mean only"},
        "participants": reports,
        "group_descriptive": {"roi_metrics": group_roi, "it_minus_v1": group_contrasts,
                              "weighting": "equal participant; no subject/ROI exclusion"},
        "bootstrap": {"unit": "concept, all 12 repetitions together", "draws": draws, "seed": BOOTSTRAP_SEED,
                      "generator": "numpy.PCG64", "concept_order": concepts,
                      "multiplicities_sha256": hashlib.sha256(counts.astype("<u4", copy=False).tobytes(order="C")).hexdigest(),
                      "refit": False, "undefined_policy": "retain; interval null if any requested draw undefined",
                      "scope": "conditional fixed-prediction concept uncertainty for these participants"},
        "estimands": {
            "macro_primary": "equal-voxel mean of pooled per-voxel incremental-SSE/SST ratios",
            "unweighted_pooled": "sum incremental SSE / sum SST over every ROI voxel",
            "reliability_weighted_pooled": "sum training-common-bin-weighted incremental SSE / weighted SST",
            "reliability_adjustment": "reliability-weighted pooled minus unweighted pooled; like-estimand comparison"},
        "limits": ["new prospective analysis, not source-notebook or full-paper reproduction",
                   "no cross-participant voxel matching or voxel-independent population inference",
                   "training reliability is raw Pearson, not a noise ceiling; coarse shared-bin weighting is descriptive",
                   "macro primary is not replaced by its defined-voxel diagnostic or by pooled-error controls",
                   "semantic increments are predictive associations conditional on these descriptors, not causal semantic effects"]}
