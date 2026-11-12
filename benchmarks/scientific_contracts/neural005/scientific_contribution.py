"""NEURAL-005 descriptive scientific assessment after existing v2 admission.

Pure stdlib API; no files, targets, fitting, imports of candidate code, or execution.
The trusted caller must already have admitted the existing complete projection,
21-process closure and score artifact. Numeric consistency here is not provenance.
"""
import copy
import math

VIEWS = ("history", "prestimulus", "all_erp")
PRIOR = "training_participant_macro_prior"
ARMS = (*VIEWS, PRIOR)
PAIRS = (("history", "all_erp"), ("history", "prestimulus"),
         ("prestimulus", "all_erp"), *((v, PRIOR) for v in VIEWS))
MEASURES = ("log_loss", "brier", "mean_probability", "observed_frequency",
            "calibration_mean_error")
EPSILON = 1e-15


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value, label):
    require(type(value) in (int, float), label + ": finite number, not bool")
    try:
        parsed = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(label + ": finite number") from error
    require(math.isfinite(parsed), label + ": finite number")
    return parsed


def near(left, right, label):
    left = number(left, label)
    right = number(right, label)
    require(math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12), label)


def schedule_counts(schedule):
    """Validate the full target-free public roster; no reduced-support override."""
    require(type(schedule) is dict and set(schedule) == {"participants", "cases"},
            "Exact target-free schedule")
    people = schedule["participants"]
    require(type(people) is list and len(people) == 7 and
            all(type(person) is str and person.isascii() and person.isdigit() and
                0 < len(person) <= 12 and str(int(person)) == person and int(person) > 0
                for person in people) and len(set(people)) == 7,
            "Seven unique independently admitted participant identities")
    require(type(schedule["cases"]) is list and len(schedule["cases"]) == 816,
            "All 816 query identities required")
    seen = set()
    counts = dict.fromkeys(people, 0)
    for row in schedule["cases"]:
        require(type(row) is dict and set(row) == {"participant", "case_id"}, "Exact public case row")
        person, case = row["participant"], row["case_id"]
        require(type(person) is str and person in counts and type(case) is str and len(case) <= 64,
                "Known participant and bounded case ID")
        pieces = case.split(":")
        require(len(pieces) == 3 and pieces[0] == person and
                all(part.isascii() and part.isdigit() for part in pieces[1:]),
                "Canonical participant:episode:round identity")
        episode, current_round = map(int, pieces[1:])
        require(1 <= episode <= 36 and 1 <= current_round <= 4 and
                case == f"{person}:{episode}:{current_round}", "Exact original episode and round support")
        key = (person, episode, current_round)
        require(key not in seen, "Duplicate current-trial identity")
        seen.add(key)
        counts[person] += 1
    require(all(counts.values()), "Every person must contribute")
    return counts


def check_projection(receipt):
    """Check known scalar fields of the previously admitted projection receipt."""
    require(type(receipt) is dict and receipt.get("status") == "three_view_projection_complete" and
            receipt.get("error") is None, "Complete existing projection receipt")
    expected = {"training_rows": 3254, "training_people": 26, "development_people": 7,
                "queries_per_view": 816, "total_view_queries": 2448,
                "fits": 0, "reserved_person_inputs": 0}
    for key, value in expected.items():
        require(type(receipt.get(key)) is int and receipt[key] == value, "Full projection scope: " + key)
    require(receipt.get("views") == list(VIEWS) and
            receipt.get("widths") == {"history": 50, "prestimulus": 53, "all_erp": 57} and
            all(type(value) is int for value in receipt["widths"].values()) and
            receipt.get("canonical_support_checked_before_mask") is True,
            "Same full support before view masking")
    # File hashes, split identities and actual receipt provenance are the existing
    # operator's responsibility; this function never promotes an assertion to proof.


def validate_report(report, counts):
    expected_people = tuple(counts)
    require(type(report) is dict and report.get("status") == "matched_scored" and
            report.get("public_validation_passed") is True, "Previously admitted complete v2 score required")
    for key, value in {"participant_n": 7, "record_n_per_view": 816,
                       "prediction_n": 2448, "complete_process_n": 21}.items():
        require(type(report.get(key)) is int and report[key] == value, "Full scored scope: " + key)
    require(report.get("primary_metric") == "equal_participant_all_erp_log_loss" and
            report.get("direction") == "lower" and report.get("primary_unit") == "participant",
            "Existing absolute-loss ranking is unchanged")
    require(report.get("log_loss_clip_epsilon") == EPSILON, "Original clipping policy")
    require(report.get("unchanged_metric_audit_crosscheck") is True and
            report.get("independent_scalar_crosscheck") is True, "Existing arithmetic crosschecks")
    require(report.get("full_contract_qualified") is False and
            report.get("bootstrap_or_significance_test") is False and
            report.get("independent_ERP_trial_identity_verified") is False,
            "No inherited qualification or inferential promotion")
    prior = number(report.get("training_participant_macro_prior"), "Training-only prior")
    require(0 <= prior <= 1, "Training prior probability")
    people = report.get("per_participant")
    require(type(people) is list and len(people) == 7 and
            all(type(row) is dict for row in people), "All seven person reports")
    ids = [row.get("participant") for row in people]
    require(all(type(person) is str for person in ids) and
            len(set(ids)) == 7 and set(ids) == set(expected_people), "Exact unique person report set")
    by_person = {row["participant"]: row for row in people}
    max_loss = max(-math.log(EPSILON), -math.log1p(-(1 - EPSILON)))
    for person in expected_people:
        row = by_person[person]
        require(set(row) == {"participant", "n", "positive_n", "arms"}, "Closed per-person score row")
        require(type(row.get("n")) is int and row["n"] == counts[person], "Per-person exact scheduled support")
        require(type(row.get("positive_n")) is int and 0 <= row["positive_n"] <= row["n"],
                "Exact binary-class count")
        arms = row.get("arms")
        require(type(arms) is dict and set(arms) == set(ARMS), "All absolute arms including prior")
        for arm in ARMS:
            metric = arms[arm]
            require(type(metric) is dict and set(metric) == {*MEASURES, "auc"}, "Closed per-person metric object")
            values = {key: number(metric.get(key), person + "/" + arm + "/" + key) for key in MEASURES}
            require(0 <= values["log_loss"] <= max_loss + 1e-12 and
                    0 <= values["brier"] <= 1 and 0 <= values["mean_probability"] <= 1 and
                    0 <= values["observed_frequency"] <= 1, "Metric domains")
            near(values["observed_frequency"], row["positive_n"] / row["n"], "Shared target frequency")
            near(values["calibration_mean_error"],
                 values["mean_probability"] - values["observed_frequency"], "Calibration arithmetic")
            auc = metric.get("auc")
            if row["positive_n"] in (0, row["n"]):
                require(auc is None, "One-class AUC remains undefined without dropping person")
            else:
                require(auc is not None and 0 <= number(auc, "AUC") <= 1, "Defined mixed-class AUC")
    means = report.get("equal_participant_arms")
    require(type(means) is dict and set(means) == set(ARMS), "All absolute participant means")
    for arm in ARMS:
        require(type(means[arm]) is dict and set(means[arm]) == {*MEASURES, "auc_mean_defined_only",
                "auc_defined_participant_n", "auc_undefined_participant_n"}, "Closed macro metric object")
        for metric in MEASURES:
            near(means[arm].get(metric), math.fsum(by_person[p]["arms"][arm][metric] for p in expected_people) / 7,
                 "Equal-person arithmetic: " + arm + "/" + metric)
        auc = [by_person[p]["arms"][arm]["auc"] for p in expected_people
               if by_person[p]["arms"][arm]["auc"] is not None]
        for key, value in (("auc_defined_participant_n", len(auc)),
                           ("auc_undefined_participant_n", 7 - len(auc))):
            require(type(means[arm].get(key)) is int and means[arm][key] == value, "AUC support")
        if auc:
            near(means[arm].get("auc_mean_defined_only"), math.fsum(auc) / len(auc), "Defined-only AUC mean")
        else:
            require(means[arm].get("auc_mean_defined_only") is None, "No defined AUC mean")
    near(report.get("score"), means["all_erp"]["log_loss"], "Unchanged all-ERP primary")
    comparisons = report.get("signed_comparisons")
    expected = {left + "_minus_" + right for left, right in PAIRS}
    require(type(comparisons) is dict and set(comparisons) == expected, "All six signed contrasts")
    for left, right in PAIRS:
        item = comparisons[left + "_minus_" + right]
        require(type(item) is dict and set(item) == {"left_arm", "right_arm", "direction",
                "per_participant", "equal_participant_mean"} and
                item.get("direction") == "left-minus-right loss; positive means lower right-arm loss" and
                item.get("left_arm") == left and item.get("right_arm") == right,
                "Contrast arm identities")
        rows = item.get("per_participant")
        require(type(rows) is list and len(rows) == 7 and all(type(row) is dict for row in rows),
                "Complete contrast person support")
        ids = [row.get("participant") for row in rows]
        require(all(type(person) is str for person in ids) and
                len(set(ids)) == 7 and set(ids) == set(expected_people), "Exact contrast people")
        macro = item.get("equal_participant_mean")
        require(type(macro) is dict and set(macro) == {"log_loss", "brier"}, "Closed contrast mean object")
        for metric in ("log_loss", "brier"):
            for row in rows:
                require(set(row) == {"participant", "log_loss", "brier"}, "Closed per-person contrast row")
                person = row["participant"]
                near(row.get(metric), by_person[person]["arms"][left][metric] -
                     by_person[person]["arms"][right][metric], "Signed person arithmetic")
            near(macro.get(metric), math.fsum(row[metric] for row in rows) / 7, "Signed participant mean")
    return by_person


def matched_history_control(schedule):
    """No ERP data access or permutation; establish structural singleton groups.

    For an admitted source projection, H contains episode and current round.
    Within one person, equality of H implies equality of those fields, hence
    equality of the unique case ID. Therefore each exact-H group has size one.
    """
    schedule_counts(schedule)
    return {
        "status": "infeasible_exact_within_participant_full_history",
        "infeasibility_is_structural_under_admitted_projection": True,
        "conditioning_history_width": 50,
        "identity_fields_in_history": ["episode", "round"],
        "unique_case_identity": ["participant", "episode", "round"],
        "development_strata": 816, "development_singleton_strata": 816,
        "movable_development_cases": 0,
        "training_same_injectivity_rule": "Unique participant:episode:round with episode and round in H.",
        "ERP_randomizations_performed": 0, "randomization_repetitions_selected": None,
        "seed": None, "p_value": None,
        "null_fitting_or_refitting_policy_selected": False,
        "no_movement_is_not_a_null_control": True,
        "joint_vector_if_a_future_design_is_admitted": {
            "all_erp_beyond_history": "All seven ERP components jointly conditional on H.",
            "offer_components_beyond_prestimulus": "Four offer components jointly conditional on H and three fixed baselines."
        },
        "alternative_sampling_law_or_cross_person_exchangeability_validated": False,
        "raw_online_or_causal_inference": False
    }


def assess(report, projection_receipt, schedule):
    """Augment a complete admitted v2 result; never grade predictions or read targets.

    This is a descriptive estimand/report adapter, not an alternative runner or
    gain-based leaderboard. The caller retains the original full score artifact.
    """
    counts = schedule_counts(schedule)
    check_projection(projection_receipt)
    by_person = validate_report(report, counts)
    expected_people = tuple(counts)
    values = {p: by_person[p]["arms"]["history"]["log_loss"] -
              by_person[p]["arms"]["all_erp"]["log_loss"] for p in expected_people}
    delta = math.fsum(values.values()) / 7
    leave_one_out = [{"omitted_for_sensitivity_only": p,
                      "mean_log_loss_gain": math.fsum(values[q] for q in expected_people if q != p) / 6}
                     for p in expected_people]
    return {
        "schema": "neural005-scientific-contribution-report-v1",
        "status": "complete_descriptive_predictive_contribution",
        "benchmark_count": 1, "new_benchmarks": 0,
        "scope": {"training_people": 26, "training_examples": 3254,
                  "development_people": 7, "queries_per_view": 816,
                  "views": list(VIEWS), "predictions": 2448, "complete_protocols": 21,
                  "common_current_seven_ERP_support_preserved": True},
        "ranking": {"metric": report["primary_metric"], "direction": "lower",
                    "score": report["score"], "gain_does_not_control_ranking": True},
        "predictive_contribution": {
            "estimand": "Equal-person held-development loss(history) minus loss(all_ERP) for the frozen matched procedure.",
            "units": "nats per prediction, averaged within person then equally across seven people",
            "mean_log_loss_gain": delta,
            "direction": "Positive means lower observed all-ERP prediction loss.",
            "per_person": [{"participant": p, "queries": counts[p], "log_loss_gain": values[p]} for p in expected_people],
            "observed_sign": "positive" if delta > 0 else "negative" if delta < 0 else "zero",
            "positive_people": sum(value > 0 for value in values.values()),
            "zero_people": sum(value == 0 for value in values.values()),
            "negative_people": sum(value < 0 for value in values.values()),
            "leave_one_person_out_sensitivity": leave_one_out,
            "sensitivity_does_not_select_a_scoring_subset": True,
            "population_confidence_interval": None, "p_value": None,
            "causal_effect": False, "intrinsic_neural_information_established": False,
            "reference_and_matched_method_adequacy_remain_source_review_obligations": True
        },
        "absolute_arms": copy.deepcopy(report["equal_participant_arms"]),
        "per_person_absolute_arms": copy.deepcopy(report["per_participant"]),
        "all_six_signed_contrasts": copy.deepcopy(report["signed_comparisons"]),
        "matched_history_ERP_control": matched_history_control(schedule),
        "conditional_independence_test_performed": False,
        "scientific_neural_contribution_claim_admitted": False,
        "full_contract_complete": False, "research_qualified": False, "submission_ready": False,
        "limits": [
            "Seven previously exposed development people; held from training is not a new unexposed cohort.",
            "Procedure-specific prediction difference, not a causal neural effect or universal conditional-information measure.",
            "The published same-round choice endpoint differs from this benchmark's explicit next-round extension.",
            "Current ERP eligibility, positional linkage and offline preprocessing holds remain.",
            "Matched training-only methods, prefix availability, target custody and 21-process closure require existing trusted admission.",
            "No matched-history null, randomization p-value, scientific success threshold or favorable-subset selection is supplied."
        ]
    }
