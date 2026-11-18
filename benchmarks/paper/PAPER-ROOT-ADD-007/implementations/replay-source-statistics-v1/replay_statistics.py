"""Independent statistics for the retained author replay branch, not paper admission.

No author imports, fitting, native reads or random draws. Caller-supplied source
selection and decoded vectors require independent authentication before use.
"""
from __future__ import annotations

import math

MICE = ("478", "481", "483", "485")
PHASES = ("learning", "learned")
CLUSTERS = ("TC_cluster", "PC_cluster", "Non_SI_cluster")
SIDES = ("left", "right")
CONDITIONS = ("sampling_L", "sampling_R", "outward_L", "outward_R",
              "reward_L", "reward_R", "inward_L", "inward_R")
DRAW_COUNT = 500
TAIL_THRESHOLD = 0.025
WINDOW_BINS = 10
ARTIFACT_JUMP = 0.3
EVENT_KEYS = {"event_id", "frame_indices", "true_positions", "decoded_positions",
              "posterior_zero_columns", "time_permutations"}


class ContractError(ValueError):
    pass


def _need(condition, message):
    if not condition:
        raise ContractError(message)


def _finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    result = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        rank = (start + end - 1) / 2.0
        for i in order[start:end]:
            result[i] = rank
        start = end
    return result


def _correlation(x, y):
    mx, my = math.fsum(x) / len(x), math.fsum(y) / len(y)
    xx = [v - mx for v in x]
    yy = [v - my for v in y]
    den = math.sqrt(math.fsum(v*v for v in xx) * math.fsum(v*v for v in yy))
    if den == 0:
        return None
    return max(-1.0, min(1.0, math.fsum(a*b for a, b in zip(xx, yy)) / den))


def score_event(event, condition):
    """Reconstruct active-cell27 masking, temporal null and literal tail rules.

    A None decoded position must be declared as an all-zero posterior column.
    This is an operator assertion, not proof of counts or posterior provenance.
    time_permutations is the complete frozen list of500 permutations AFTER
    silent-column removal and outward truth-jump cropping. No RNG is invented.
    """
    _need(condition in CONDITIONS, "unknown condition")
    _need(type(event) is dict and set(event) == EVENT_KEYS, "event fields")
    _need(type(event["event_id"]) is str and bool(event["event_id"]), "event_id")
    fields = ("frame_indices", "true_positions", "decoded_positions", "posterior_zero_columns")
    _need(all(type(event[k]) is list and len(event[k]) == WINDOW_BINS for k in fields), "complete ten-bin window")
    frames = event["frame_indices"]
    _need(all(type(v) is int for v in frames), "integer frame indices")
    _need(frames == list(range(frames[0], frames[0] + WINDOW_BINS)), "contiguous source frame window")
    truth, decoded, zero = (event[k] for k in fields[1:])
    _need(all(_finite(v) for v in truth), "finite source positions")
    _need(all(type(v) is bool for v in zero), "posterior-zero booleans")
    _need(all((d is None) if z else _finite(d) for d, z in zip(decoded, zero)), "decoded/zero-column agreement")
    permutations = event["time_permutations"]
    _need(type(permutations) is list, "explicit temporal permutations")
    retained = [i for i, z in enumerate(zero) if not z]
    before_crop = list(retained)
    crop_at = None
    if condition.startswith("outward_"):
        for j in range(len(retained) - 1):
            if abs(truth[retained[j + 1]] - truth[retained[j]]) > ARTIFACT_JUMP:
                crop_at = j + 1
                retained = retained[:crop_at]
                break
    result = {
        "event_id": event["event_id"], "source_window_bins": WINDOW_BINS,
        "nonzero_posterior_bins_before_crop": len(before_crop),
        "retained_frame_indices": [frames[i] for i in retained],
        "outward_crop_after_compact_index": crop_at,
        "source_null": "permute_compacted_time_indices_without_redecoding",
        "time_axis": "zero_based_consecutive_after_filtering",
        "status": None, "rho": None, "null_rhos": [], "z": None,
        "p_forward": None, "p_backward": None, "significant": False,
        "rmse_normalized_position": None,
    }
    if len(retained) < 5:
        _need(not permutations, "skipped event must not claim null draws")
        result["status"] = "skipped_fewer_than_five_retained_bins"
        return result
    n = len(retained)
    _need(len(permutations) == DRAW_COUNT, "exactly500 frozen temporal draws required")
    expected = set(range(n))
    for order in permutations:
        _need(type(order) is list and len(order) == n and
              all(type(v) is int for v in order) and set(order) == expected,
              "every temporal draw must be a complete bijection")
    positions = [decoded[i] for i in retained]
    ranked = _ranks(positions)
    compact_time = list(range(n))
    observed = _correlation(ranked, compact_time)
    null = [_correlation(ranked, order) for order in permutations]
    # Literal source comparisons: a NaN comparison is false. JSON uses None
    # plus a status rather than emitting non-standard NaN/Infinity numbers.
    upper_less = sum(observed is not None and v is not None and observed > v for v in null)
    lower_greater = sum(observed is not None and v is not None and observed < v for v in null)
    p_forward = 1.0 - upper_less / DRAW_COUNT
    p_backward = 1.0 - lower_greater / DRAW_COUNT
    differences = [truth[i] - decoded[i] for i in retained]
    _need(all(_finite(v) for v in differences), "finite position differences")
    scale = max(abs(v) for v in differences)
    rmse = (scale * math.sqrt(math.fsum((v / scale)**2 for v in differences) / n)
            if scale else 0.0)
    result.update(rho=observed, null_rhos=null, p_forward=p_forward, p_backward=p_backward,
                  significant=p_forward < TAIL_THRESHOLD or p_backward < TAIL_THRESHOLD,
                  rmse_normalized_position=rmse)
    if observed is None or any(v is None for v in null):
        result["status"] = "tested_undefined_rank_statistic"
    else:
        mean = math.fsum(null) / DRAW_COUNT
        std = math.sqrt(math.fsum((v - mean)**2 for v in null) / DRAW_COUNT)
        if std == 0:
            result["status"] = "tested_zero_null_spread"
        else:
            result["z"] = (observed - mean) / std
            result["status"] = "tested_finite_statistics"
    return result


def score_stratum(context, selected_event_ids, events):
    """Preserve selected, tested and skipped denominators for ONE declared cell.

    This does not construct or authenticate biological support or aggregate a
    published panel. Extra/missing events relative to the supplied roster fail.
    """
    allowed = {"mouse": MICE, "phase": PHASES, "cluster": CLUSTERS,
               "decoder_side": SIDES, "condition": CONDITIONS}
    _need(type(context) is dict and set(context) == set(allowed), "stratum fields")
    _need(all(context[k] in values for k, values in allowed.items()), "stratum values")
    _need(type(selected_event_ids) is list and all(type(v) is str and v for v in selected_event_ids), "selected roster")
    _need(len(set(selected_event_ids)) == len(selected_event_ids), "duplicate selected event")
    _need(type(events) is list and len(events) == len(selected_event_ids), "complete selected event count")
    _need(all(type(v) is dict and type(v.get("event_id")) is str for v in events), "event records")
    _need([v["event_id"] for v in events] == selected_event_ids, "exact ordered selected roster")
    scored = [score_event(event, context["condition"]) for event in events]
    selected = len(scored)
    skipped = sum(v["status"].startswith("skipped_") for v in scored)
    significant = sum(v["significant"] for v in scored)
    undefined = sum(v["status"] == "tested_undefined_rank_statistic" for v in scored)
    return {
        "schema": "pfc-replay-source-statistics/v1", "context": dict(context),
        "selected_event_ids": list(selected_event_ids), "events": scored,
        "selected_count": selected, "tested_count": selected - skipped,
        "skipped_count": skipped, "undefined_tested_count": undefined,
        "significant_count": significant,
        "source_significant_fraction_all_selected": significant/selected if selected else None,
        "diagnostic_significant_fraction_tested": significant/(selected-skipped) if selected > skipped else None,
        "empty_selection": selected == 0,
        "scientific_qualification": "unresolved", "paper_reproduction": None,
        "paper_improvement": None, "source_support_authenticated": False,
        "prediction_support_includes_truth_dependent_outward_crop": context["condition"].startswith("outward_"),
    }
