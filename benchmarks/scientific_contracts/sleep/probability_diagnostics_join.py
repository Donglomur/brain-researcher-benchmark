"""Optional consistency join of trusted sleep score/report probability summaries.

No probability arrays, targets, file I/O, fitting or source authentication.
Raw losses are attributed to the already admitted scorer, not recomputed here.
"""
import copy
import math
import re

CLASSES = ["W", "N1", "N2", "N3", "R"]
EPSILON = 1e-15
MAX_LOG_LOSS = -math.log(EPSILON)
SIMPLEX_TOLERANCE = 1e-6
FROZEN = "frozen_program"
ADAPTIVE = "case_adaptive_equal_inputs_tools_compute"


def need(ok, text):
    if not ok:
        raise ValueError(text)


def number(value):
    need(type(value) in (int, float), "Finite number, not bool")
    try:
        result = float(value)
    except (ValueError, OverflowError) as error:
        raise ValueError("Finite representable number") from error
    need(math.isfinite(result), "Finite number")
    return result


def count(value):
    need(type(value) is int and 0 <= value <= 2**63 - 1, "Nonnegative signed-64-bit count, not bool")
    return value


def close(value, expected, text):
    need(math.isclose(number(value), expected, rel_tol=1e-12, abs_tol=1e-12), text)


def identity(value):
    return type(value) is str and re.fullmatch(r"0|[1-9][0-9]{0,11}", value) is not None


def prediction_descriptor(value):
    return (type(value) is dict and set(value) == {"bytes", "sha256"} and
            type(value["bytes"]) is int and 0 < value["bytes"] <= 2**63 - 1 and
            type(value["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is not None)


def expected_panels(profile):
    need(profile in ("generic_current_person", "training_only_reuse"), "Known frozen profile")
    keys = set()
    for mode in (FROZEN, ADAPTIVE):
        selected = profile if mode == FROZEN else "current_person"
        for view in ("C", "EC", "OC", "EOC"):
            keys.add(f"{mode}|{selected}|{view}|original")
        for view in ("EC", "EOC"):
            keys.add(f"{mode}|{selected}|{view}|shifted")
    keys.add("R0|independent_reference|C|original")
    for family in ("R1", "R2"):
        for view in ("C", "EC", "OC", "EOC"):
            keys.add(f"{family}|independent_reference|{view}|original")
        for view in ("EC", "EOC"):
            keys.add(f"{family}|independent_reference|{view}|shifted")
    for view in ("C", "EC"):
        keys.add(f"R2|independent_reference|{view}|association")
    return keys


def base_support(grade, report):
    """Join already admitted base objects; original grade math remains upstream."""
    need(type(grade) is dict and grade.get("schema") == "neural007_full153_grade_v1" and
         type(report) is dict and report.get("schema") == "sleep_scientific_comparison_v1" and
         report.get("status") == "complete_descriptive_comparison" and
         report.get("source_grade_schema") == grade["schema"], "Admitted base grade/report schemas")
    need(all(grade.get(k) is False for k in ("raw_native_LLM_understanding_tested", "scientific_content_admitted", "research_qualified", "submission_ready")) and
         all(report.get(k) is False for k in ("internal_LLM_understanding_established", "causal_effect_established", "full_contract_complete", "research_qualified", "submission_ready")), "No qualification promotion")
    need(report.get("calibration") == {"status": "not_inferable_from_confusion_counts", "diagnostics": None}, "Original unavailable calibration state; no double join")
    for k, value in (("people", 78), ("nights", 153), ("independent_tasks", 1)):
        need(type(grade.get(k)) is int and grade[k] == value, "Original full grade scope")
    scope = report.get("scope")
    need(type(scope) is dict and all(type(scope.get(k)) is int and scope[k] == value for k, value in
         (("people", 78), ("nights", 153), ("folds", 6), ("scored_panels", 27),
          ("candidate_inferences_required_upstream", 936), ("reference_inferences_required_upstream", 1170), ("new_assignments", 0))), "Complete base report scope")
    descriptor = grade.get("predictions")
    need(prediction_descriptor(descriptor) and prediction_descriptor(report.get("prediction_panel")) and
         report.get("prediction_panel") == descriptor, "Same complete prediction descriptor")
    panels = grade.get("panels")
    need(type(panels) is dict and set(panels) == expected_panels(report.get("frozen_profile")) and
         report.get("all_27_absolute_panels") == panels, "Exact same original 27 panels")
    support = report.get("support")
    need(type(support) is dict and set(support) == {"schema", "people"} and support["schema"] == "sleep_full153_support_v1", "Independent original support")
    rows = support["people"]
    need(type(rows) is list and len(rows) == 78, "All 78 people")
    people = {}
    for row in rows:
        need(type(row) is dict and set(row) == {"person", "fold", "nights"} and identity(row["person"]) and row["person"] not in people,
             "Exact unique supplied person support")
        need(type(row["fold"]) is int and 1 <= row["fold"] <= 6 and type(row["nights"]) is int and row["nights"] in (1, 2), "Original fold/night counts")
        people[row["person"]] = row
    need(sum(row["nights"] for row in rows) == 153 and all(sum(row["fold"] == f for row in rows) == 13 for f in range(1, 7)), "All nights and six folds")
    truths = {}
    for panel in panels.values():
        need(type(panel) is dict and type(panel.get("people")) is dict and set(panel["people"]) == set(people) and
             type(panel.get("independent_people")) is int and panel["independent_people"] == 78, "Same complete person panel")
        for person, metric in panel["people"].items():
            need(type(metric) is dict, "Original person metrics")
            matrix = metric.get("confusion")
            need(type(matrix) is list and len(matrix) == 5 and all(type(row) is list and len(row) == 5 for row in matrix), "Five-class confusion")
            truth = [sum(count(value) for value in row) for row in matrix]
            eligible = count(sum(truth))
            need(eligible > 0 and type(metric.get("eligible_epochs")) is int and metric["eligible_epochs"] == eligible and
                 type(metric.get("support")) is list and len(metric["support"]) == 5 and
                 all(type(value) is int for value in metric["support"]) and metric["support"] == truth, "Original nonempty eligible/truth support")
            need(person not in truths or truths[person] == truth, "Common scored truth support")
            truths[person] = truth
    return people, truths


def person_summary(value, truth, night_count):
    keys = {"schema", "classes", "clock_epochs", "eligible_epochs", "masked_epochs", "nights", "truth_counts",
            "mean_multiclass_brier", "mean_clipped_log_loss_nats", "log_loss_floor", "log_loss_clipped_epochs",
            "mean_predicted_probability", "observed_class_frequency", "calibration_in_large_predicted_minus_observed", "defined"}
    need(type(value) is dict and set(value) == keys and value["schema"] == "sleep_probability_diagnostics_person_v1" and
         value["classes"] == CLASSES and value["defined"] is True, "Complete defined person diagnostics")
    clock, eligible, masked = [count(value[k]) for k in ("clock_epochs", "eligible_epochs", "masked_epochs")]
    need(clock > 0 and eligible == sum(truth) > 0 and clock == eligible + masked and
         type(value["truth_counts"]) is list and len(value["truth_counts"]) == 5 and
         all(type(x) is int for x in value["truth_counts"]) and value["truth_counts"] == truth, "Same integrated eligible support and full clock")
    nights = value["nights"]
    need(type(nights) is dict and len(nights) == night_count and all(identity(n) for n in nights), "Original person night count")
    totals = {"clock": 0, "eligible": 0, "masked": 0}
    for row in nights.values():
        need(type(row) is dict and set(row) == set(totals), "Exact night accounting")
        for key in totals:
            totals[key] += count(row[key])
        need(row["clock"] > 0 and row["clock"] == row["eligible"] + row["masked"], "Complete night accounting")
    need(totals == {"clock": clock, "eligible": eligible, "masked": masked}, "Night sums equal person accounting")
    need(type(value["log_loss_floor"]) in (int, float) and value["log_loss_floor"] == EPSILON, "Selected log-loss floor")
    clipped = count(value["log_loss_clipped_epochs"])
    need(clipped <= eligible, "Clipping count bounded by eligible epochs")
    brier, loss = number(value["mean_multiclass_brier"]), number(value["mean_clipped_log_loss_nats"])
    # sum(p) <= 1+tolerance and p in[0,1] imply Brier <=2+tolerance.
    # This conservative bound preserves admitted slightly non-unit row sums.
    need(0 <= brier <= 2 + SIMPLEX_TOLERANCE and 0 <= loss <= MAX_LOG_LOSS + 1e-12 and
         loss + 1e-12 >= MAX_LOG_LOSS * clipped / eligible, "Probability-loss range and clipped-loss consistency")
    vectors = []
    for key in ("mean_predicted_probability", "observed_class_frequency", "calibration_in_large_predicted_minus_observed"):
        row = value[key]
        need(type(row) is list and len(row) == 5, "Five marginal diagnostics")
        vectors.append([number(x) for x in row])
    predicted, observed, bias = vectors
    need(all(0 <= x <= 1 for x in predicted) and abs(math.fsum(predicted) - 1) <= SIMPLEX_TOLERANCE + 1e-12, "Unrenormalized mean probability simplex")
    for k in range(5):
        close(observed[k], truth[k] / eligible, "Recomputed observed class frequency")
        close(bias[k], predicted[k] - truth[k] / eligible, "Recomputed marginal prediction bias")
    return brier, loss, [predicted[k] - truth[k] / eligible for k in range(5)], nights


def join_probability_diagnostics(grade, report, diagnostics=None):
    """Return a detached base report, optionally with consistent trusted summaries.

    Already admitted grade/report and operator-produced diagnostics are required.
    Matching metadata does not authenticate raw losses, records or source custody.
    """
    people, truth = base_support(grade, report)
    result = copy.deepcopy(report)
    if diagnostics is None:
        return result
    need(type(diagnostics) is dict and set(diagnostics) == {"schema", "predictions", "people", "nights", "classes", "panels"} and
         diagnostics["schema"] == "neural007_full153_probability_diagnostics_v1" and diagnostics["classes"] == CLASSES and
         prediction_descriptor(diagnostics["predictions"]) and diagnostics["predictions"] == grade["predictions"] and type(diagnostics["people"]) is int and diagnostics["people"] == 78 and
         type(diagnostics["nights"]) is int and diagnostics["nights"] == 153, "Exact companion schema/scope/prediction binding")
    panels = diagnostics["panels"]
    need(type(panels) is dict and set(panels) == set(grade["panels"]), "Same complete 27 diagnostic panels")
    night_accounting = {}
    for panel in panels.values():
        keys = {"schema", "people", "required_people", "undefined_people", "person_macro_brier", "person_macro_clipped_log_loss_nats",
                "person_macro_calibration_in_large_predicted_minus_observed", "aggregation", "log_loss_floor", "interval", "p_value", "interpretation"}
        need(type(panel) is dict and set(panel) == keys and panel["schema"] == "sleep_probability_diagnostics_panel_v1" and
             type(panel["required_people"]) is int and panel["required_people"] == 78 and panel["undefined_people"] == [] and
             panel["aggregation"] == "eligible epochs pooled within person; equal people" and panel["log_loss_floor"] == EPSILON and
             panel["interval"] is None and panel["p_value"] is None and
             panel["interpretation"] == "Prediction quality and marginal calibration diagnostics; no full calibration or inference guarantee",
             "Complete noninferential integrated panel")
        need(type(panel["people"]) is dict and set(panel["people"]) == set(people), "All required diagnostic people")
        values = []
        for person in sorted(people):
            item = person_summary(panel["people"][person], truth[person], people[person]["nights"])
            need(person not in night_accounting or night_accounting[person] == item[3], "Identical clock/mask/night accounting in all panels")
            night_accounting[person] = item[3]
            values.append(item)
        close(panel["person_macro_brier"], math.fsum(v[0] for v in values) / 78, "Equal-person Brier macro")
        close(panel["person_macro_clipped_log_loss_nats"], math.fsum(v[1] for v in values) / 78, "Equal-person log-loss macro")
        marginal = panel["person_macro_calibration_in_large_predicted_minus_observed"]
        need(type(marginal) is list and len(marginal) == 5, "Five macro marginal biases")
        for k in range(5):
            close(marginal[k], math.fsum(v[2][k] for v in values) / 78, "Equal-person marginal bias macro")
    result["calibration"] = {
        "status": "consistent_trusted_scorer_probability_diagnostics",
        "diagnostics": copy.deepcopy(diagnostics),
        "summary_consistency_checked": True,
        "raw_probability_metrics_authenticated_by_this_join": False,
        "attribution": "Already admitted protected scorer; supplied summaries alone do not prove raw loss or source identity.",
        "full_conditional_calibration_established": False,
        "confidence_interval": None, "p_value": None,
    }
    return result
