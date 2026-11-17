"""Numerical diagnostics for the unresolved Figure 5 metric join.

This module neither selects the original cohort nor qualifies a paper endpoint.
It makes two incompatible existing R2 conventions observable on identical rows.
No source/model/data execution, file loading, or truth discovery occurs here.
"""
from math import fsum, isfinite, sqrt


TARGETS = ("choice", "prior", "wheel-speed", "whisker-motion-energy")
REGIONS = ("PO", "LP", "DG", "CA1", "VISa")


class MetricError(ValueError):
    pass


def _number(value):
    if type(value) not in (int, float) or not isfinite(value):
        raise MetricError("values must be finite real numbers, excluding booleans")
    return float(value)


def _matrix(values):
    if type(values) not in (list, tuple) or not values:
        raise MetricError("nonempty ordered trial values required")
    nested = type(values[0]) in (list, tuple)
    rows = []
    for value in values:
        if (type(value) in (list, tuple)) != nested:
            raise MetricError("mixed scalar and vector trial shapes")
        row = list(value) if nested else [value]
        if not row:
            raise MetricError("empty output axis")
        rows.append([_number(x) for x in row])
    if any(len(row) != len(rows[0]) for row in rows):
        raise MetricError("ragged output axis")
    return rows, (len(rows), len(rows[0])), nested


def _result(value=None, reason=None):
    if value is not None and not isfinite(value):
        return {"value": None, "undefined_reason": "nonfinite_arithmetic"}
    return {"value": value, "undefined_reason": reason}


def _r2(truth, prediction):
    if len(truth) < 2:
        return _result(reason="fewer_than_two_scalar_observations")
    center = fsum(truth) / len(truth)
    denominator = fsum((v - center) ** 2 for v in truth)
    if denominator == 0:
        return _result(reason="constant_truth")
    numerator = fsum((a - b) ** 2 for a, b in zip(truth, prediction))
    return _result(1.0 - numerator / denominator)


def _auc(truth, prediction):
    # Mann-Whitney rank definition, with half credit for tied score pairs.
    # This uses the continuous score, never the thresholded prediction.
    positives = sum(truth)
    negatives = len(truth) - positives
    if not positives or not negatives:
        return _result(reason="single_class")
    ordered = sorted(zip(prediction, truth))
    rank_sum = 0.0
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][0] == ordered[start][0]:
            end += 1
        average_rank = (start + 1 + end) / 2.0
        rank_sum += average_rank * sum(label for _, label in ordered[start:end])
        start = end
    return _result((rank_sum - positives * (positives + 1) / 2) /
                   (positives * negatives))


def _pearson(truth, prediction):
    if len(truth) < 2:
        return _result(reason="fewer_than_two_trials")
    # Pearson is invariant to independent positive scaling. Scale BEFORE
    # centering/squaring so finite large values cannot overflow the covariance
    # or the means. In particular, do not clamp NaN into a fabricated +1.
    a_scale, b_scale = max(map(abs, truth)), max(map(abs, prediction))
    if a_scale == 0 or b_scale == 0:
        return _result(reason="constant_truth_or_prediction")
    a_scaled, b_scaled = [v / a_scale for v in truth], [v / b_scale for v in prediction]
    a_mean, b_mean = fsum(a_scaled) / len(truth), fsum(b_scaled) / len(prediction)
    a = [v - a_mean for v in a_scaled]
    b = [v - b_mean for v in b_scaled]
    aa, bb = fsum(v * v for v in a), fsum(v * v for v in b)
    if aa == 0 or bb == 0:
        return _result(reason="constant_truth_or_prediction")
    value = fsum(x * y for x, y in zip(a, b)) / sqrt(aa) / sqrt(bb)
    if not isfinite(value):
        return _result(reason="nonfinite_arithmetic")
    return _result(max(-1.0, min(1.0, value)))


def score_case(target, truth, prediction):
    """Score one already-paired session/region/method without choosing a panel recipe.

    Values must be ordinary lists/tuples. Static targets have one value per trial.
    Dynamic targets may be trial vectors, with a common ordered time/output axis.
    Shape equality is checked before flattening. Constant output bins stay explicit.
    """
    if target not in TARGETS:
        raise MetricError("unknown Figure 5 target")
    y, shape, nested = _matrix(truth)
    p, pshape, pnested = _matrix(prediction)
    if shape != pshape or nested != pnested:
        raise MetricError("truth and prediction need identical trial/output shapes")
    yy = [v for row in y for v in row]
    pp = [v for row in p for v in row]
    report = {"target": target, "trials": shape[0], "outputs_per_trial": shape[1],
              "scalar_observations": len(yy), "metrics": {}}
    if target in ("choice", "prior") and shape[1] != 1:
        raise MetricError("static Figure 5 targets require one scalar per trial")
    if target == "choice":
        if any(v not in (0.0, 1.0) for v in yy):
            raise MetricError("choice labels must be explicitly oriented as 0/1")
        if any(v < 0 or v > 1 for v in pp):
            raise MetricError("choice predictions must be positive-class probabilities")
        report["metrics"]["auc"] = _auc(yy, pp)
    elif target == "prior":
        report["metrics"]["pearson"] = _pearson(yy, pp)
    else:
        flattened = _r2(yy, pp)
        columns = [_r2([row[j] for row in y], [row[j] for row in p])
                   for j in range(shape[1])]
        undefined = [j for j, value in enumerate(columns) if value["value"] is None]
        uniform = (_result(reason="undefined_output_bins") if undefined else
                   _result(fsum(v["value"] for v in columns) / len(columns)))
        report["metrics"] = {"r2_flattened": flattened,
                             "r2_uniform_output_strict": uniform}
        report["per_output_r2"] = columns
        report["undefined_output_indices"] = undefined
        report["reduction_difference"] = (None if flattened["value"] is None or
                                           uniform["value"] is None else
                                           flattened["value"] - uniform["value"])
        report["original_panel_reduction"] = None
    return report


def summarize_group(expected_cases, scores, metric_name):
    """Retain one target/region/method vector and its complete expected denominator.

    expected_cases is an earlier operator-selected census, not a source admission.
    scores maps case ID to score_case output. Missing and undefined cases survive.
    Equal-session and equal-animal means are descriptive diagnostics; neither is
    selected as the original figure summary. Trials/bins are not replicates here.
    """
    if type(expected_cases) not in (list, tuple) or not expected_cases:
        raise MetricError("a nonempty earlier expected-case census is required")
    if type(scores) is not dict:
        raise MetricError("scores must be a case-indexed dictionary")
    identifiers, sessions, group = set(), set(), None
    rows = []
    for case in expected_cases:
        required = ("case_id", "session", "animal", "target", "region", "condition")
        if any(type(case.get(k)) is not str or not case[k] for k in required):
            raise MetricError("literal case/session/animal/target/region/condition identities required")
        if case["target"] not in TARGETS or case["region"] not in REGIONS:
            raise MetricError("unsupported Figure 5 target or region")
        key = (case["target"], case["region"], case["condition"])
        if group is not None and key != group:
            raise MetricError("do not combine distinct targets, regions or conditions")
        group = key
        if case["case_id"] in identifiers or case["session"] in sessions:
            raise MetricError("duplicate case or session within one panel group")
        identifiers.add(case["case_id"])
        sessions.add(case["session"])
        score = scores.get(case["case_id"])
        row = {k: case[k] for k in required}
        row.update(value=None, status="unavailable", reason="missing_score")
        if score is not None:
            if score.get("target") != case["target"]:
                raise MetricError("score target does not match expected case")
            metric = score.get("metrics", {}).get(metric_name)
            if metric is None:
                raise MetricError("requested metric absent from an observed score")
            value = metric.get("value")
            if value is None:
                reason = metric.get("undefined_reason")
                if type(reason) is not str or not reason:
                    raise MetricError("undefined metrics require a reason")
                row.update(status="undefined", reason=reason)
            else:
                row.update(value=_number(value), status="complete", reason=None)
        rows.append(row)
    if set(scores) - identifiers:
        raise MetricError("unexpected score case outside earlier census")
    permitted = {"choice": {"auc"}, "prior": {"pearson"},
                 "wheel-speed": {"r2_flattened", "r2_uniform_output_strict"},
                 "whisker-motion-energy": {"r2_flattened", "r2_uniform_output_strict"}}
    if metric_name not in permitted[group[0]]:
        raise MetricError("metric does not belong to this target")
    animal_groups = {}
    for row in rows:
        animal_groups.setdefault(row["animal"], []).append(row)

    def complete_mean(items):
        if any(r["status"] != "complete" for r in items):
            return None
        return fsum(r["value"] for r in items) / len(items)

    animals = [{"animal": animal, "sessions": [r["session"] for r in items],
                "value": complete_mean(items)}
               for animal, items in sorted(animal_groups.items())]
    complete = all(row["status"] == "complete" for row in rows)
    return {"target": group[0], "region": group[1], "condition": group[2],
            "metric": metric_name, "expected_sessions": len(rows),
            "complete_sessions": sum(row["status"] == "complete" for row in rows),
            "expected_animals": len(animals), "rows": rows, "animals": animals,
            "complete_support": complete,
            "equal_session_diagnostic": complete_mean(rows),
            "equal_animal_diagnostic": (fsum(a["value"] for a in animals) / len(animals)
                                         if complete else None),
            "original_panel_aggregation": None}
