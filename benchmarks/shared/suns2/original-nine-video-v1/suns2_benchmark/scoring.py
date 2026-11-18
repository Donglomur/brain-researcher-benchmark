"""Original nine-video scores plus a separately declared geometry audit.

This trusted API consumes operator-owned arrays, never participant Python code.
Original neuron order/multiplicity are preserved; only audit predictions are
deduplicated. Exact count-derived fractions decide the descriptive outcome.
"""
from collections import deque
from fractions import Fraction
import time

import numpy as np

from .constants import VIDEO_IDS, MASK_HEIGHT, MASK_WIDTH, MAX_INSTANCES, TASK_SLUG
from .literal_assignment import matlab_hungarian_control_flow, Refused as MatcherRefusal

SCORE_TIMEOUT_SECONDS = 55.0
AUDIT_NAME = "unique-prediction-geometry-max-cardinality-iou-half/v1"

class ScoringError(ValueError):
    """Malformed complete-panel input or bounded arithmetic refusal."""

def _need(ok, message):
    if not ok:
        raise ScoringError(message)

def _tick(deadline):
    _need(time.monotonic() < deadline, "panel scoring deadline exceeded")

def _normalize_panel(panel, role, deadline):
    _need(type(panel) is dict and set(panel) == set(VIDEO_IDS), f"{role}: exact nine video IDs required")
    result = {}
    for video in VIDEO_IDS:
        _tick(deadline)
        value = panel[video]
        _need(type(value) is np.ndarray, f"{role}/{video}: plain NumPy array required")
        _need(value.ndim == 3 and value.shape[:2] == (MASK_HEIGHT, MASK_WIDTH), f"{role}/{video}: expected50x50xN")
        _need(value.shape[2] <= MAX_INSTANCES, f"{role}/{video}: instance resource limit")
        _need(role != "ground_truth" or value.shape[2] > 0, f"{role}/{video}: original task requires nonempty GT")
        _need(value.dtype.kind in "buif" and value.dtype.itemsize <= 8, f"{role}/{video}: unsupported numeric dtype")
        _need(np.isfinite(value).all() and np.all((value == 0) | (value == 1)), f"{role}/{video}: finite binary masks required")
        _need(np.all(np.count_nonzero(value, axis=(0, 1)) > 0), f"{role}/{video}: zero-area individual ROI")
        # Snapshot without sorting/deduplicating; source arrays remain unchanged.
        result[video] = value.astype(np.bool_, copy=True)
    return result

def _geometry(mask):
    """Exact unordered binary geometries, with first-occurrence audit indices."""
    columns = mask.reshape((MASK_HEIGHT * MASK_WIDTH, mask.shape[2]), order="F")
    packed = np.packbits(columns.T, axis=1, bitorder="little")
    first = {}
    for index, row in enumerate(packed):
        first.setdefault(row.tobytes(), index)
    keys = frozenset(first)
    # Sorting only selects a canonical audit order; raw source order is untouched.
    indices = [first[key] for key in sorted(first)]
    return keys, indices

def _maximum_cardinality(edges, deadline):
    """Hopcroft-Karp on the exact integer-threshold audit graph."""
    _need(edges.ndim == 2 and edges.dtype == np.bool_, "audit requires a Boolean bipartite graph")
    left_count, right_count = edges.shape
    _need(max(edges.shape, default=0) <= MAX_INSTANCES, "audit graph resource limit")
    adjacency = [np.flatnonzero(row).tolist() for row in edges]
    left = [-1] * left_count
    right = [-1] * right_count
    matches = 0
    while True:
        _tick(deadline)
        distance = [-1] * left_count
        queue = deque()
        for u in range(left_count):
            if left[u] < 0:
                distance[u] = 0
                queue.append(u)
        shortest = None
        while queue:
            _tick(deadline)
            u = queue.popleft()
            if shortest is not None and distance[u] >= shortest:
                continue
            for v in adjacency[u]:
                matched = right[v]
                if matched < 0:
                    shortest = distance[u] + 1
                elif distance[matched] < 0:
                    distance[matched] = distance[u] + 1
                    queue.append(matched)
        if shortest is None:
            return matches

        def augment(u):
            _tick(deadline)
            for v in adjacency[u]:
                matched = right[v]
                if matched < 0:
                    if distance[u] + 1 != shortest:
                        continue
                elif distance[matched] != distance[u] + 1 or not augment(matched):
                    continue
                left[u], right[v] = v, u
                return True
            distance[u] = -1
            return False

        augmented = 0
        for u in range(left_count):
            if left[u] < 0 and augment(u):
                matches += 1
                augmented += 1
        _need(augmented > 0, "audit augmentation made no progress")

def _fraction_json(value):
    if value is None:
        return None
    return {"numerator": str(value.numerator), "denominator": str(value.denominator),
            "encoding": "base10 integer strings"}

def _source_metrics(matches, gt_count, pred_count):
    _need(0 <= matches <= min(gt_count, pred_count) and gt_count > 0, "invalid original match counts")
    if pred_count == 0:
        return {"matches": 0, "ground_truth_instances": gt_count, "prediction_instances": 0,
                "recall": 0.0, "precision": 0.0, "f1": 0.0,
                "status": "literal_helper_empty_prediction_zero", "f1_exact": _fraction_json(Fraction(0)),
                "full_native_producer_empty_path_parity": "untested"}, Fraction(0)
    recall = matches / gt_count
    precision = matches / pred_count
    if matches == 0:
        return {"matches": 0, "ground_truth_instances": gt_count, "prediction_instances": pred_count,
                "recall": recall, "precision": precision, "f1": None,
                "status": "literal_helper_nonempty_zero_match_NaN", "f1_exact": None}, None
    exact = Fraction(2 * matches, gt_count + pred_count)
    return {"matches": matches, "ground_truth_instances": gt_count, "prediction_instances": pred_count,
            "recall": recall, "precision": precision, "f1": 2 * recall * precision / (recall + precision),
            "status": "finite", "f1_exact": _fraction_json(exact)}, exact

def _score_prediction(gt, pred, deadline):
    _tick(deadline)
    gt_count, pred_count = gt.shape[2], pred.shape[2]
    geometries, audit_indices = _geometry(pred)
    if pred_count == 0:
        original, original_exact = _source_metrics(0, gt_count, 0)
        audit_matches = 0
    else:
        g = gt.reshape((MASK_HEIGHT * MASK_WIDTH, gt_count), order="F").astype(np.uint32)
        p = pred.reshape((MASK_HEIGHT * MASK_WIDTH, pred_count), order="F").astype(np.uint32)
        intersections = g.T @ p
        unions = g.sum(axis=0)[:, None] + p.sum(axis=0)[None, :] - intersections
        _need(np.all(unions > 0), "undefined Jaccard union")
        distances = 1 - intersections / unions
        costs = np.where(distances > 0.5, np.inf, distances)
        try:
            matching, details = matlab_hungarian_control_flow(costs, deadline)
        except MatcherRefusal as exc:
            raise ScoringError(f"literal source matcher refused: {exc}") from exc
        original, original_exact = _source_metrics(int(matching.sum()), gt_count, pred_count)
        original["assignment_control_flow"] = details
        # Integer arithmetic, with unchanged GT instances and unique predictions.
        audit_edges = 2 * intersections[:, audit_indices] >= unions[:, audit_indices]
        audit_matches = _maximum_cardinality(audit_edges, deadline)
    audit_count = len(audit_indices)
    audit_exact = Fraction(2 * audit_matches, gt_count + audit_count)
    audit = {"name": AUDIT_NAME, "matches": audit_matches, "ground_truth_instances": gt_count,
             "unique_prediction_instances": audit_count, "raw_prediction_instances": pred_count,
             "duplicate_prediction_instances_removed_for_audit_only": pred_count - audit_count,
             "f1": float(audit_exact), "f1_exact": _fraction_json(audit_exact),
             "totalization": "G>0,P_unique=0 or zero matches ->0; separately declared extension"}
    return original, original_exact, audit, audit_exact, geometries

def _mean(fractions):
    if any(value is None for value in fractions):
        return None
    return sum(fractions, Fraction(0)) / len(VIDEO_IDS)

def _float_mean(values):
    if any(value is None for value in values):
        return None
    return float(np.mean(values))

def _comparison(original_author, original_candidate, audit_author, audit_candidate, changed):
    author_original = _mean(original_author)
    candidate_original = _mean(original_candidate)
    author_audit = _mean(audit_author)
    candidate_audit = _mean(audit_candidate)
    original_delta = None if author_original is None or candidate_original is None else candidate_original - author_original
    audit_delta = candidate_audit - author_audit
    original_positive = None if original_delta is None else original_delta > 0
    audit_positive = audit_delta > 0
    outcome = original_positive is True and bool(changed) and audit_positive
    return {"same_panel_geometry_improvement": outcome,
            "classification": ("descriptive_same_nine_video_geometry_improvement" if outcome else
                               "undefined_original_panel" if original_delta is None else
                               "no_qualified_same_panel_geometry_improvement"),
            "criteria": {"all_original_scores_defined": original_delta is not None,
                         "positive_original_mean_delta_exact": original_positive,
                         "changed_unordered_prediction_geometry": bool(changed),
                         "positive_declared_audit_mean_delta_exact": audit_positive},
            "original_mean_delta_exact": _fraction_json(original_delta),
            "audit_mean_delta_exact": _fraction_json(audit_delta),
            "geometry_changed_video_ids": list(changed)}

def score_panel(gt_by_id, author_by_id, candidate_by_id):
    """Score complete nine-video dictionaries; return JSON-safe descriptive data.

All arrays must be plain NumPy finite-binary50×50×N arrays with N<=512.
Axes retain original MAT order: [column, row, neuron]. A movie location
[time, row, column] therefore maps to mask[column, row, neuron].
The trusted caller owns GT/reference isolation and native process resources.
This API does not execute a procedure, authenticate its run or confer readiness.
"""
    deadline = time.monotonic() + SCORE_TIMEOUT_SECONDS
    gt = _normalize_panel(gt_by_id, "ground_truth", deadline)
    author = _normalize_panel(author_by_id, "author", deadline)
    candidate = _normalize_panel(candidate_by_id, "candidate", deadline)
    rows, changed = [], []
    original_author, original_candidate, audit_author, audit_candidate = [], [], [], []
    for video in VIDEO_IDS:
        a_orig, a_exact, a_audit, aa_exact, a_geometry = _score_prediction(gt[video], author[video], deadline)
        c_orig, c_exact, c_audit, ca_exact, c_geometry = _score_prediction(gt[video], candidate[video], deadline)
        geometry_changed = a_geometry != c_geometry
        if geometry_changed:
            changed.append(video)
        original_author.append(a_exact)
        original_candidate.append(c_exact)
        audit_author.append(aa_exact)
        audit_candidate.append(ca_exact)
        rows.append({"video_id": video, "original": {"author": a_orig, "candidate": c_orig,
                     "candidate_minus_author_f1_float": None if a_exact is None or c_exact is None else c_orig["f1"] - a_orig["f1"],
                     "candidate_minus_author_f1_exact": None if a_exact is None or c_exact is None else _fraction_json(c_exact - a_exact)},
                     "declared_order_invariant_audit": {"author": a_audit, "candidate": c_audit,
                     "candidate_minus_author_f1_float": c_audit["f1"] - a_audit["f1"],
                     "candidate_minus_author_f1_exact": _fraction_json(ca_exact - aa_exact)},
                     "geometry": {"unordered_exact_geometry_changed": geometry_changed,
                                  "author_unique_geometries": len(a_geometry), "candidate_unique_geometries": len(c_geometry),
                                  "raw_instance_order_equal": np.array_equal(author[video], candidate[video])}})
    a_source = [r["original"]["author"]["f1"] for r in rows]
    c_source = [r["original"]["candidate"]["f1"] for r in rows]
    a_mean, c_mean = _float_mean(a_source), _float_mean(c_source)
    result = {"schema": "suns2-nine-video-panel-score/v1", "task": TASK_SLUG,
              "status": "scored_complete_panel" if a_mean is not None and c_mean is not None else "scored_with_undefined_original",
              "video_ids": list(VIDEO_IDS), "cases": rows,
              "original_summary": {"metric": "equal-video mean of literal source-helper spatial F1",
                  "author_mean_float": a_mean, "candidate_mean_float": c_mean,
                  "candidate_minus_author_mean_float": None if a_mean is None or c_mean is None else c_mean - a_mean,
                  "author_population_SD_float": None if a_mean is None else float(np.std(a_source, ddof=0)),
                  "candidate_population_SD_float": None if c_mean is None else float(np.std(c_source, ddof=0)),
                  "author_mean_exact": _fraction_json(_mean(original_author)),
                  "candidate_mean_exact": _fraction_json(_mean(original_candidate)),
                  "undefined_author_videos": [v for v, f in zip(VIDEO_IDS, original_author) if f is None],
                  "undefined_candidate_videos": [v for v, f in zip(VIDEO_IDS, original_candidate) if f is None],
                  "no_nan_dropping_or_audit_substitution": True},
              "declared_audit_summary": {"name": AUDIT_NAME,
                  "author_mean_float": _float_mean([r["declared_order_invariant_audit"]["author"]["f1"] for r in rows]),
                  "candidate_mean_float": _float_mean([r["declared_order_invariant_audit"]["candidate"]["f1"] for r in rows]),
                  "author_mean_exact": _fraction_json(_mean(audit_author)), "candidate_mean_exact": _fraction_json(_mean(audit_candidate)),
                  "same_GT_instances_preserved": True, "exact_duplicate_predictions_removed_symmetrically": True,
                  "original_metric_equivalence_claimed": False},
              "descriptive_outcome": _comparison(original_author, original_candidate, audit_author, audit_candidate, changed),
              "qualification": {"native_MATLAB_parity": "unestablished", "prediction_generation_reproduced": False,
                  "candidate_execution_authenticated_by_this_API": False, "population_inference": "unqualified",
                  "clinical_meaning": "unqualified", "global_SOTA": "unqualified", "benchmark_ready": False,
                  "reference_audit_authentic_data_re_evaluation": "requires separate admission; not established by construction"},
              "limits": {"max_instances_per_video": MAX_INSTANCES, "resource_limit_is_not_original_biological_limit": True,
                  "zero_area_individual_ROIs": "rejected at interface", "same_fixed_exposed_panel_only": True}}
    return result
