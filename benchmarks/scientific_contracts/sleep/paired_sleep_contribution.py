"""Descriptive sleep/EOG contrasts after trusted full-panel grading.

Pure standard-library arithmetic. Supplied metadata is not proof of authentic
roster, lifecycle closure, fitting policy, matched effort or source custody.
"""
import copy
import math
import re

FROZEN = "frozen_program"
ADAPTIVE = "case_adaptive_equal_inputs_tools_compute"
MODES = (FROZEN, ADAPTIVE)
VIEWS = ("C", "EC", "OC", "EOC")
PROFILES = ("generic_current_person", "training_only_reuse")
SIGNALS = (("EC", "C", "EEG_over_clock"),
           ("EOC", "OC", "EEG_given_EOG"),
           ("EOC", "EC", "EOG_given_EEG"))
CLASSES = ("W", "N1", "N2", "N3", "R")


def need(ok, message):
    if not ok:
        raise ValueError(message)


def finite(value, label):
    need(type(value) in (int, float), label + ": number, not bool")
    try:
        out = float(value)
    except (ValueError, OverflowError) as error:
        raise ValueError(label + ": finite number") from error
    need(math.isfinite(out), label + ": finite number")
    return out


def close(actual, expected, label):
    if expected is None:
        need(actual is None, label + ": undefined remains null")
    else:
        need(actual is not None and math.isclose(finite(actual, label), expected,
             rel_tol=1e-12, abs_tol=1e-12), label + ": arithmetic mismatch")


def count(value):
    need(type(value) is int and 0 <= value <= 2**63 - 1,
         "Nonnegative signed-64-bit representable count, not bool")
    return value


def support_rows(support):
    need(type(support) is dict and set(support) == {"schema", "people"} and
         support["schema"] == "sleep_full153_support_v1", "Exact independently admitted support schema")
    rows = support["people"]
    need(type(rows) is list and len(rows) == 78, "All 78 people required")
    seen = set()
    for row in rows:
        need(type(row) is dict and set(row) == {"person", "fold", "nights"}, "Exact target-free person row")
        person = row["person"]
        need(type(person) is str and re.fullmatch(r"0|[1-9][0-9]{0,11}", person) is not None and
             person not in seen, "Unique canonical nonnegative numeric-string person identity")
        seen.add(person)
        need(type(row["fold"]) is int and 1 <= row["fold"] <= 6 and
             type(row["nights"]) is int and row["nights"] in (1, 2), "Fixed fold/night support")
    need(all(sum(row["fold"] == fold for row in rows) == 13 for fold in range(1, 7)) and
         sum(row["nights"] for row in rows) == 153, "Six groups of 13; all 153 nights")
    return sorted(rows, key=lambda row: int(row["person"]))


def panel_keys(profile):
    need(profile in PROFILES, "Explicit selected frozen fitting profile")
    keys = []
    for mode in MODES:
        selected = profile if mode == FROZEN else "current_person"
        keys.extend(f"{mode}|{selected}|{view}|original" for view in VIEWS)
        keys.extend(f"{mode}|{selected}|{view}|shifted" for view in ("EC", "EOC"))
    keys.append("R0|independent_reference|C|original")
    for family in ("R1", "R2"):
        keys.extend(f"{family}|independent_reference|{view}|original" for view in VIEWS)
        keys.extend(f"{family}|independent_reference|{view}|shifted" for view in ("EC", "EOC"))
    keys.extend(f"R2|independent_reference|{view}|association" for view in ("C", "EC"))
    return tuple(keys)


def metrics(matrix):
    need(type(matrix) is list and len(matrix) == 5 and
         all(type(row) is list and len(row) == 5 for row in matrix), "Exact five-by-five confusion")
    for row in matrix:
        for value in row:
            count(value)
    support = [sum(row) for row in matrix]
    total = count(sum(support))
    need(total > 0, "No required person without eligible target support")
    f1, recall = [], []
    for stage in range(5):
        tp = matrix[stage][stage]
        denominator = support[stage] + sum(row[stage] for row in matrix)
        f1.append(2 * tp / denominator if denominator else 0.0)
        recall.append(tp / support[stage] if support[stage] else None)
    return {"confusion": copy.deepcopy(matrix), "support": support, "eligible_epochs": total,
            "class_f1": f1, "class_recall": recall,
            "fixed_five_macro_f1": math.fsum(f1) / 5,
            "supported_balanced_accuracy": math.fsum(x for x in recall if x is not None) /
            sum(x is not None for x in recall)}


def validate_grade(grade, rows, profile):
    """Recheck existing arithmetic and complete identities; not custody evidence."""
    keys = {"schema", "panels", "contrasts", "people", "nights", "predictions",
            "raw_native_LLM_understanding_tested", "scientific_content_admitted",
            "research_qualified", "submission_ready", "independent_tasks"}
    need(type(grade) is dict and set(grade) == keys and
         grade["schema"] == "neural007_full153_grade_v1", "Existing complete score schema")
    for key, expected in (("people", 78), ("nights", 153), ("independent_tasks", 1)):
        need(type(grade[key]) is int and grade[key] == expected, "Unchanged graded scope: " + key)
    need(all(grade[key] is False for key in ("raw_native_LLM_understanding_tested",
         "scientific_content_admitted", "research_qualified", "submission_ready")), "No qualification promotion")
    descriptor = grade["predictions"]
    need(type(descriptor) is dict and set(descriptor) == {"bytes", "sha256"} and
         count(descriptor["bytes"]) > 0 and type(descriptor["sha256"]) is str and
         re.fullmatch(r"[0-9a-f]{64}", descriptor["sha256"]) is not None, "Exact complete-prediction descriptor")
    panels = grade["panels"]
    need(type(panels) is dict and set(panels) == set(panel_keys(profile)), "All 27 expected candidate/reference panels")
    people = [row["person"] for row in rows]
    truth = {}
    computed = {}
    for key in panel_keys(profile):
        panel = panels[key]
        need(type(panel) is dict and set(panel) == {"primary", "people", "independent_people", "metric"} and
             type(panel["independent_people"]) is int and panel["independent_people"] == 78 and
             panel["metric"] == "equal_person_fixed_five_class_macro_f1", "Original person-macro panel")
        need(type(panel["people"]) is dict and set(panel["people"]) == set(people), "Exact common person set")
        values = {}
        for person in people:
            observed = panel["people"][person]
            need(type(observed) is dict and set(observed) == {"confusion", "support", "eligible_epochs",
                 "class_f1", "class_recall", "fixed_five_macro_f1", "supported_balanced_accuracy"}, "Closed original person metric schema")
            expected = metrics(observed["confusion"])
            need(type(observed["support"]) is list and len(observed["support"]) == 5 and
                 all(type(x) is int for x in observed["support"]) and observed["support"] == expected["support"] and
                 type(observed["eligible_epochs"]) is int and observed["eligible_epochs"] == expected["eligible_epochs"], "Exact class/eligible counts")
            for name in ("class_f1", "class_recall"):
                need(type(observed[name]) is list and len(observed[name]) == 5, "All five class metrics")
                for a, b in zip(observed[name], expected[name]):
                    close(a, b, name)
            for name in ("fixed_five_macro_f1", "supported_balanced_accuracy"):
                close(observed[name], expected[name], name)
            if person in truth:
                need(expected["support"] == truth[person], "Identical scored truth support in every panel")
            else:
                truth[person] = expected["support"]
            values[person] = expected
        close(panel["primary"], math.fsum(values[p]["fixed_five_macro_f1"] for p in people) / 78, "Equal-person primary")
        computed[key] = values
    contrasts = grade["contrasts"]
    need(type(contrasts) is dict and set(contrasts) == {m + "|" + n for m in MODES for _, _, n in SIGNALS}, "All six existing signal contrasts")
    for mode in MODES:
        selected = profile if mode == FROZEN else "current_person"
        for left, right, name in SIGNALS:
            item = contrasts[mode + "|" + name]
            need(type(item) is dict and set(item) == {"mean_delta", "paired_person_deltas"} and
                 type(item["paired_person_deltas"]) is dict and set(item["paired_person_deltas"]) == set(people), "Exact existing paired contrast")
            values = []
            for person in people:
                value = (computed[f"{mode}|{selected}|{left}|original"][person]["fixed_five_macro_f1"] -
                         computed[f"{mode}|{selected}|{right}|original"][person]["fixed_five_macro_f1"])
                close(item["paired_person_deltas"][person], value, "Existing paired person difference")
                values.append(value)
            close(item["mean_delta"], math.fsum(values) / 78, "Existing paired mean")
    return computed


def summarize(values, rows):
    people = [row["person"] for row in rows]
    need(set(values) == set(people), "Complete paired vector")
    def group(ids):
        data = [values[person] for person in ids]
        known = [value for value in data if value is not None]
        return {"required_people": len(ids), "defined_people": len(known),
                "mean": math.fsum(known) / len(ids) if len(known) == len(ids) else None}
    result = {**group(people), "per_person": dict(values),
              "positive_people": sum(value is not None and value > 0 for value in values.values()),
              "zero_people": sum(value == 0 for value in values.values()),
              "negative_people": sum(value is not None and value < 0 for value in values.values()),
              "folds": {}, "leave_one_fold_out_sensitivity": {}}
    for fold in range(1, 7):
        result["folds"][str(fold)] = group([row["person"] for row in rows if row["fold"] == fold])
        result["leave_one_fold_out_sensitivity"][str(fold)] = group([row["person"] for row in rows if row["fold"] != fold])
    return result


def difference(left, right):
    need(set(left) == set(right), "Paired same-person support")
    return {p: left[p] - right[p] if left[p] is not None and right[p] is not None else None for p in left}


def assess(grade, expected_support, profile):
    """Assess an already admitted JSON-decoded grade; never read targets/files."""
    rows = support_rows(expected_support)
    computed = validate_grade(grade, rows, profile)
    def key(mode, view, control="original"):
        selected = profile if mode == FROZEN else "current_person" if mode == ADAPTIVE else "independent_reference"
        return f"{mode}|{selected}|{view}|{control}"
    def vector(mode, view, metric="macro_f1", control="original"):
        panel = computed[key(mode, view, control)]
        return {r["person"]: (panel[r["person"]]["fixed_five_macro_f1"] if metric == "macro_f1"
                else panel[r["person"]]["class_recall"][4]) for r in rows}
    comparisons = {}
    def add(name, left, right, interpretation):
        values = difference(left, right)
        comparisons[name] = {"interpretation": interpretation, **summarize(values, rows)}
        return values
    for view in VIEWS:
        add("mode:" + view, vector(ADAPTIVE, view), vector(FROZEN, view),
            "Adaptive minus frozen procedure performance; same people, original inputs.")
    signals = {}
    for mode in MODES:
        for a, b, name in SIGNALS:
            signals[mode, name] = add(mode + ":" + name, vector(mode, a), vector(mode, b),
                "Procedure-specific provided-signal predictive difference; not a causal effect.")
    for _, _, name in SIGNALS:
        add("mode_interaction:" + name, signals[ADAPTIVE, name], signals[FROZEN, name],
            "Difference of paired predictive gains; not causal difference-in-differences.")
    for mode in (*MODES, "R1", "R2"):
        for view in ("EC", "EOC"):
            add(mode + ":alignment:" + view, vector(mode, view), vector(mode, view, control="shifted"),
                "Original minus same-state shifted-EEG performance; alignment sensitivity, not a null test.")
    for view in ("C", "EC"):
        add("R2:association:" + view, vector("R2", view), vector("R2", view, control="association"),
            "Original minus separately refitted label-association diagnostic; not an EEG-only intervention.")
    for mode in MODES:
        add(mode + ":EOC_minus_R0_C", vector(mode, "EOC"), vector("R0", "C"),
            "Combined-view performance relative to the declared independent clock/prior reference.")
        for family in ("R1", "R2"):
            for view in VIEWS:
                add(mode + ":" + view + "_minus_" + family, vector(mode, view), vector(family, view),
                    "Same-view candidate minus predeclared reference; no held-out reference selection.")
    for family in ("R1", "R2"):
        for a, b, name in SIGNALS:
            add(family + ":" + name, vector(family, a), vector(family, b),
                "Independent reference signal increment; empirical competence remains unqualified.")
    rem = {}
    for mode in MODES:
        rem[mode] = add(mode + ":EOG_given_EEG:rem_recall", vector(mode, "EOC", "rem"), vector(mode, "EC", "rem"),
            "Paired REM recall increment; all-person mean null if any required person lacks REM.")
    add("mode_interaction:EOG_given_EEG:rem_recall", rem[ADAPTIVE], rem[FROZEN],
        "Difference of paired REM increments; strict all-person definedness.")
    for view in ("EC", "EOC"):
        add("mode:" + view + ":rem_recall", vector(ADAPTIVE, view, "rem"), vector(FROZEN, view, "rem"),
            "Adaptive minus frozen REM recall; no supported-only substitution.")
    targets = {}
    for mode in (*MODES, "mode_interaction"):
        for metric, suffix in (("macro_f1", ""), ("rem_recall", ":rem_recall")):
            item = comparisons[mode + ":EOG_given_EEG" + suffix]
            targets[mode + ":eog_gain:" + metric] = {"aggregate": item["mean"], "per_person": dict(item["per_person"])}
    generic = profile == "generic_current_person"
    return {
        "schema": "sleep_scientific_comparison_v1", "status": "complete_descriptive_comparison",
        "source_grade_schema": grade["schema"], "prediction_panel": dict(grade["predictions"]),
        "scope": {"people": 78, "nights": 153, "folds": 6, "views": list(VIEWS), "modes": list(MODES),
                  "candidate_inferences_required_upstream": 936, "reference_inferences_required_upstream": 1170,
                  "scored_panels": 27, "new_assignments": 0},
        "support": copy.deepcopy(expected_support), "class_order": list(CLASSES),
        "frozen_profile": profile,
        "comparison_policy": {"kind": "matched_current_person_opportunities" if generic else "different_query_selection_and_fit_reuse_treatments",
                              "equal_actual_compute_established": False, "identical_fitting_semantics_established": False,
                              "declared_fixed_final_fits": 312 if generic else 24, "declared_adaptive_final_fits": 312,
                              "counts_are_declared_requirements_not_measured_costs": True},
        "absolute_eoc_rankings": {m: grade["panels"][key(m, "EOC")]["primary"] for m in MODES},
        "ranking_direction": "higher", "gain_does_not_replace_absolute_ranking": True,
        "primary_mode_comparison": "mode:EOC", "comparisons": comparisons,
        "all_27_absolute_panels": copy.deepcopy(grade["panels"]),
        "original_six_signal_contrasts": copy.deepcopy(grade["contrasts"]),
        "neural008_numeric_claim_targets": targets,
        "rem_support": {r["person"]: {"true_rem_epochs": computed[key(FROZEN, "EOC")][r["person"]]["support"][4],
                                      "defined": computed[key(FROZEN, "EOC")][r["person"]]["support"][4] > 0} for r in rows},
        "uncertainty": {"kind": "descriptive_person_fold_and_leave_fold_sensitivity", "primary_uses_all_78_people": True,
                        "bootstrap_performed": False, "confidence_interval": None, "p_value": None,
                        "population_coverage_established": False, "shared_fold_training_and_one_campaign_variability_unresolved": True},
        "calibration": {"status": "not_inferable_from_confusion_counts", "diagnostics": None},
        "neural008_extension": {"status": "proposed_full_raw_cohort_readout_not_registry_adoption",
                                "historical_finite_feature_task_preserved": True, "shared_cohort_and_costs_with_neural007": True},
        "internal_LLM_understanding_established": False, "causal_effect_established": False,
        "scientific_reasoning_credit": None, "full_contract_complete": False,
        "research_qualified": False, "submission_ready": False
    }
