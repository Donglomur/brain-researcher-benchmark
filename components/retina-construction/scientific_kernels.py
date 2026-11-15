"""Protected-scoring mathematical primitives; no authentic scorer is qualified."""
import math
from retina_contract import Refusal, require


def finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def vector(values, label):
    require(type(values) is list and bool(values), label + ":nonempty_vector")
    require(all(finite_number(x) for x in values), label + ":finite")
    return [float(x) for x in values]


def score_response(target, prediction):
    """Every declared frame is required; missing/NaN predictions never disappear."""
    y, p = vector(target, "target"), vector(prediction, "prediction")
    require(len(y) == len(p), "prediction:complete_frames")
    require(all(x >= 0 for x in y), "target:negative_firing_rate")
    try:
        mean = math.fsum(y) / len(y)
        sse = math.fsum((a - b) ** 2 for a, b in zip(y, p))
        sst = math.fsum((a - mean) ** 2 for a in y)
    except OverflowError as exc:
        raise Refusal("metric:overflow") from exc
    require(math.isfinite(sse) and math.isfinite(sst), "metric:overflow")
    r2 = None if sst == 0 else 1 - sse / sst
    require(r2 is None or math.isfinite(r2), "metric:nonfinite_ratio")
    return {"frames": len(y), "sse": sse, "mse": sse / len(y),
            "r2_unclipped": r2, "r2_historical_clipped": None if r2 is None else max(0., r2),
            "constant_target_hold": sst == 0,
            "historical_nan_dropping_used": False,
            "negative_prediction_frames": sum(x < 0 for x in p)}


def pair_disagreement_ranking(dog, sg, protected_target, fixations, nonfixation_frames=None):
    """Par84: protected response RANGE, frames then cells, preserve every fixation.

    Returns a full ranking only. Exact historical top20% rounding and tie policies,
    as well as fixation/frame identity, require source closure before a Fig5 claim.
    """
    require(type(dog) is list and type(sg) is list and type(protected_target) is list
            and len(dog) == len(sg) == len(protected_target) == 2, "pair:two_cells")
    d = [vector(x, "dog") for x in dog]
    s = [vector(x, "sg") for x in sg]
    y = [vector(x, "protected_target") for x in protected_target]
    n = len(y[0])
    require(all(len(x) == n for x in d + s + y), "pair:complete_aligned_frames")
    require(all(x >= 0 for cell in y for x in cell), "target:negative_firing_rate")
    require(type(fixations) is list and bool(fixations), "fixations:nonempty")
    nonfixation_frames = [] if nonfixation_frames is None else nonfixation_frames
    require(type(nonfixation_frames) is list and all(type(i) is int and 0 <= i < n for i in nonfixation_frames)
            and len(nonfixation_frames) == len(set(nonfixation_frames)), "nonfixation:frames")
    ranges = [max(x) - min(x) for x in y]
    range_held = any(x == 0 or not math.isfinite(x) for x in ranges)
    frame_seen, ids_seen, scores = set(), set(), []
    for fixation in fixations:
        require(type(fixation) is dict and set(fixation) == {"id", "frames"}, "fixation:schema")
        fid, frames = fixation["id"], fixation["frames"]
        require(type(fid) is str and fid and fid not in ids_seen, "fixation:id")
        ids_seen.add(fid)
        require(type(frames) is list and bool(frames), "fixation:frames")
        require(all(type(i) is int and 0 <= i < n for i in frames), "fixation:frame_range")
        require(len(frames) == len(set(frames)) and not frame_seen.intersection(frames),
                "fixation:duplicate_frame")
        require(not set(nonfixation_frames).intersection(frames), "fixation:nonfixation_overlap")
        frame_seen.update(frames)
        if range_held:
            continue
        values = [math.fsum(abs(s[c][i] - d[c][i]) / ranges[c] for i in frames) / len(frames)
                  for c in range(2)]
        score = math.fsum(values) / 2
        require(math.isfinite(score), "disagreement:nonfinite")
        scores.append({"id": fid, "score": score})
    require(frame_seen.union(nonfixation_frames) == set(range(n)), "fixation:missing_frame")
    if range_held:
        return {"status": "HELD_ZERO_OR_NONFINITE_TEST_RANGE",
                "ranked_fixations": None, "selection_applied": False,
                "declared_fixations": len(fixations), "declared_nonfixation_frames": len(nonfixation_frames),
                "normalization": "protected_test_response_range"}
    # Stable supplied order is visible for tied scores, not claimed historical.
    ranked = sorted(scores, key=lambda x: -x["score"])
    return {"status": "COMPLETE_PROTECTED_RANKING_ONLY", "ranked_fixations": ranked,
            "ties": len({x["score"] for x in scores}) != len(scores),
            "selection_applied": False, "top20_rounding_policy": None,
            "declared_nonfixation_frames": len(nonfixation_frames),
            "fixation_mapping_authenticated": False,
            "normalization": "protected_test_response_range",
            "historical_selection_parity": False}


def improvement_population_gate(rows):
    """Check supplied records without treating declared IDs as authentic hierarchy.

    Animal-balanced scores are deliberately unavailable in this source packet.
    The original paper metrics remain primary; future robustness uses a separately
    authenticated complete population and original sampling hierarchy.
    """
    require(type(rows) is list and bool(rows), "population:empty")
    by_animal, seen = {}, set()
    for row in rows:
        require(type(row) is dict and set(row) == {
            "animal_id", "piece_id", "unit_id", "candidate_mse", "sg_mse", "dog_mse"
        }, "population:schema")
        require(all(type(row[k]) is str and bool(row[k]) for k in ("animal_id", "piece_id", "unit_id")),
                "population:missing_identity")
        key = (row["animal_id"], row["piece_id"], row["unit_id"])
        require(key not in seen, "population:duplicate_unit")
        seen.add(key)
        for k in ("candidate_mse", "sg_mse", "dog_mse"):
            require(finite_number(row[k]) and row[k] >= 0,
                    "population:failed_or_nonfinite_model")
        by_animal.setdefault(row["animal_id"], []).append(row)
    return {
        "status": "UNAVAILABLE_UNAUTHENTICATED_SAMPLING_HIERARCHY",
        "declared_group_ids": len(by_animal), "declared_units": len(rows),
        "authenticated_animals": None, "animal_balanced_scores": None,
        "complete_population_authenticated": False,
        "uncertainty_estimated": False, "improvement_claim": False,
        "original_metrics_replaced": False,
        "requires": "Authentic animal/retina/piece lineage and a frozen complete population, independently accepted before any grouped score.",
    }
