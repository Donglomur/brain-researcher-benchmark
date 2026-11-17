"""Unexecuted source for finite, invented reporting-criterion controls.

Run only after a separate engineering selection. This program reads no files,
accepts no data paths and fits no models. All numerical inputs below are invented.
The target's required paper URL/locator are interface identifiers, not provenance:
its zero digest and SYNTHETIC path deliberately do not authenticate a real source.
No production reference-admission or scientific-qualification flag is fabricated.
"""
from copy import deepcopy
from decimal import Decimal
from fractions import Fraction
import json
from math import factorial
import traceback

# Production functions are bound only by the selected worker calling run(core).
# Merely loading this source neither imports the production module nor runs tests.
_ACTIVE = None


IDS = ("amy_self", "quest_self", "amy_quest")
METRICS = ("pearson_r", "p_two_sided", "k", "N")
CANDIDATE_RAW = b'''{"schema":"nider_published_numeric_submission_v1","rows":[
{"contrast":"amy_self","fields":{"pearson_r":0.20,"p_two_sided":0.123,"k":5,"N":100}},
{"contrast":"quest_self","fields":{"pearson_r":-0.30,"p_two_sided":0.456,"k":6,"N":101}},
{"contrast":"amy_quest","fields":{"pearson_r":0.00,"p_two_sided":0.789,"k":7,"N":102}}]}'''


class ControlFailure(AssertionError):
    pass


def expect(condition, code):
    if _ACTIVE is not None:
        _ACTIVE["attempted"] += 1
        _ACTIVE["completed"] += 1
    if not condition:
        if _ACTIVE is not None:
            _ACTIVE["failed"] += 1
        raise ControlFailure(code)


def candidate():
    return decode_numeric_json(CANDIDATE_RAW)


def target():
    # Invented reporting targets; none were read from a publication or dataset.
    values = (("0.20", "0.123", "5", "100"),
              ("-0.30", "0.456", "6", "101"),
              ("0.00", "0.789", "7", "102"))
    return {
        "schema": "nider_published_caption_targets_v1",
        "source_pin": {"path": "SYNTHETIC_NOT_A_SOURCE", "bytes": 0, "sha256": "0" * 64},
        "source_url": "https://www.nature.com/articles/s41586-026-11203-1",
        "locator": "Figure 1 caption; The correlations were; all tests two-sided and uncorrected",
        "rows": [{"contrast": contrast, "display_lexemes": dict(zip(METRICS, row))}
                 for contrast, row in zip(IDS, values)],
    }


def native():
    # All 36 numerical values are invented. Display strings are inert placeholders.
    rows = []
    for index, (contrast, z, p) in enumerate(zip(IDS, ("0.5", "-0.5", "0"),
                                               ("0.123", "0.456", "0.789"))):
        numbers = {
            "TE_random": z, "lower_random": "-0.8", "upper_random": "0.8",
            "pval_random": p, "k": str(5 + index), "N": str(100 + index),
            "tau": "0.1", "lower_tau": "0", "upper_tau": "0.2", "Q": "4",
            "df_Q": str(4 + index), "pval_Q": "0.4",
        }
        fields = ",".join(json.dumps(key) + ":" + value for key, value in numbers.items())
        rows.append('{"contrast":' + json.dumps(contrast) + ',"fields":{' + fields +
                    '},"formatted_table":' + json.dumps(["SYNTHETIC_DISPLAY_UNUSED"] * 11) + '}')
    raw = ('{"schema":"nider-reproduction-values-v1","rows":[' + ",".join(rows) + ']}').encode()
    return decode_numeric_json(raw)


def native_target():
    value = target()
    for row, r in zip(value["rows"], ("0.46", "-0.46", "0.00")):
        row["display_lexemes"]["pearson_r"] = r
    return value


def rejected(code, action):
    try:
        action()
    except InvalidInput as exc:
        expect(exc.args == (code,), "wrong_refusal_code")
    else:
        expect(False, "invalid_input_was_accepted")


def field_status(result, contrast, metric):
    matches = [row["status"] for row in result["per_field"]
               if row["contrast"] == contrast and row["metric"] == metric]
    expect(len(matches) == 1, "nonunique_field_result")
    return matches[0]


def candidate_field_case(contrast, metric, value, expected):
    packet = candidate()
    packet["rows"][IDS.index(contrast)]["fields"][metric] = Decimal(value)
    before = deepcopy(packet)
    result = compare_candidate(packet, target())
    expect(field_status(result, contrast, metric) == expected, "wrong_reporting_classification")
    expected_aggregate = ("COMPLETE_PUBLISHED_REPORTING_AGREEMENT"
                          if expected in ("REPORTING_AGREEMENT", "EXACT_COUNT_AGREEMENT")
                          else "PUBLISHED_REPORTING_NOT_ESTABLISHED")
    expect(result["status"] == expected_aggregate, "wrong_aggregate_status")
    expect(packet == before, "candidate_mutated")


def complete_candidate():
    packet = candidate()
    packet["rows"].reverse()
    result = compare_candidate(packet, target())
    expect(result["status"] == "COMPLETE_PUBLISHED_REPORTING_AGREEMENT", "positive_case_failed")
    expect(result["evaluated_fields"] == 12 and len(result["per_field"]) == 12, "field_count")
    expect([(x["contrast"], x["metric"]) for x in result["per_field"]] ==
           [(c, m) for c in IDS for m in METRICS], "canonical_output_support")
    for row in result["per_field"]:
        expected = "EXACT_COUNT_AGREEMENT" if row["metric"] in ("k", "N") else "REPORTING_AGREEMENT"
        expect(row["status"] == expected, "positive_field_status")
    for key in ("requires_R_formatted_strings", "numeric_estimator_accuracy_certified",
                "procedure_correctness_established", "all_36_native_fields_qualified",
                "scientifically_qualified_benchmark"):
        expect(result[key] is False, "overstated_candidate_claim")


def invalid_candidate(mutate, code):
    packet = candidate()
    mutate(packet)
    rejected(code, lambda: compare_candidate(packet, target()))


def invalid_target(mutate, code):
    packet = target()
    mutate(packet)
    rejected(code, lambda: compare_candidate(candidate(), packet))


def invalid_native(mutate, code):
    packet = native()
    mutate(packet)
    rejected(code, lambda: compare_serialized_native(packet, native_target()))


def native_projection():
    packet = native()
    before = deepcopy(packet)
    result = compare_serialized_native(packet, native_target())
    expect(result["status"] == "COMPLETE_PUBLISHED_REPORTING_AGREEMENT", "projected_positive_failed")
    expect(result["evaluated_fields"] == 12 and len(result["per_field"]) == 12, "native_field_count")
    expect({(x["contrast"], x["metric"]) for x in result["per_field"]} ==
           {(c, m) for c in IDS for m in METRICS}, "native_complete_support")
    for row in result["per_field"]:
        if row["metric"] == "pearson_r":
            expect(row["status"] == "REPORTING_AGREEMENT", "projected_r_status")
            expect(row["projection"] == "certified_rational_tanh_enclosure_of_serialized_Fisher_z", "projection_label")
            nonzero = row["contrast"] != "amy_quest"
            expect(row["raw_Fisher_z_as_r_diagnostic_status"] ==
                   ("REPORTING_DISAGREEMENT" if nonzero else "REPORTING_AGREEMENT"), "raw_scale_diagnostic")
            expect(row["reporting_status_differs_between_scale_projections"] is nonzero, "scale_resolution_claim")
        elif row["metric"] == "p_two_sided":
            expect(row["status"] == "REPORTING_AGREEMENT" and
                   row["projection"] == "unchanged_serialized_native_pval_random", "native_p_changed")
        else:
            expect(row["status"] == "EXACT_COUNT_AGREEMENT", "native_count_changed")
    expect(packet == before, "native_input_overwritten")
    expect(result["statistical_fits"] == 0, "unexpected_fit_claim")
    for key in ("original_binary64_reconstruction_claimed", "native_Fisher_z_values_overwritten",
                "all_36_native_fields_qualified", "independent_estimator_accuracy_certified",
                "procedure_correctness_established", "scientifically_qualified_benchmark"):
        expect(result[key] is False, "overstated_native_claim")


def native_display_inert():
    packet = native()
    expected = compare_serialized_native(packet, native_target())
    for row in packet["rows"]:
        row["formatted_table"] = ["DIFFERENT_SYNTHETIC_TEXT"] * 11
    expect(compare_serialized_native(packet, native_target()) == expected, "R_strings_affect_numeric_criterion")


def unused_native_fields_not_qualified():
    packet = native()
    expected = compare_serialized_native(packet, native_target())
    packet["rows"][0]["fields"]["tau"] = Decimal("999")
    actual = compare_serialized_native(packet, native_target())
    expect(actual == expected and actual["all_36_native_fields_qualified"] is False,
           "unused_field_falsely_qualified")


def native_p_boundary():
    packet = native()
    packet["rows"][0]["fields"]["pval_random"] = Decimal("0.1235")
    result = compare_serialized_native(packet, native_target())
    expect(field_status(result, "amy_self", "p_two_sided") == "INDETERMINATE_REPORTING_BOUNDARY",
           "native_p_tie_was_resolved")
    expect(result["status"] == "PUBLISHED_REPORTING_NOT_ESTABLISHED", "native_boundary_passed")


def projection_bounds():
    positive = tanh_rational_bounds(Fraction(1, 2))
    negative = tanh_rational_bounds(Fraction(-1, 2))
    expect(all(isinstance(x, Fraction) for x in (*positive, *negative)), "inexact_bounds_type")
    expect(Fraction(46, 100) < positive[0] <= positive[1] < Fraction(47, 100), "positive_enclosure")
    expect(negative == (-positive[1], -positive[0]), "odd_symmetry")
    expect(positive[1] - positive[0] < Fraction(1, 10 ** 30), "loose_enclosure")


def projection_endpoints():
    for z in (Fraction(-8), Fraction(8)):
        low, high = tanh_rational_bounds(z)
        expect(-1 < low <= high < 1, "endpoint_domain_or_order")
        expect(low > 0 if z > 0 else high < 0, "endpoint_sign")
        expect(high - low < Fraction(1, 10 ** 30), "endpoint_enclosure_width")


def projection_zero():
    expect(tanh_rational_bounds(Fraction(0)) == (Fraction(0), Fraction(0)), "zero_projection")


def projection_monotonicity():
    first = tanh_rational_bounds(Fraction(1, 10))
    second = tanh_rational_bounds(Fraction(1, 5))
    expect(0 < first[0] <= first[1] < second[0] <= second[1] < Fraction(1, 5),
           "monotonicity_or_tanh_below_argument")


def independent_refinement_certificate():
    # An independently formed, higher-order rational lower/upper certificate at
    # x=1 (z=1/2). Direct factorial summation differs from the production
    # degree128 recurrence. A zero-width lower-partial-sum implementation fails.
    higher_partial = sum((Fraction(1, factorial(j)) for j in range(257)), Fraction(0))
    higher_upper = higher_partial + Fraction(1, factorial(257)) / (1 - Fraction(1, 258))
    higher_low_r = (higher_partial - 1) / (higher_partial + 1)
    higher_high_r = (higher_upper - 1) / (higher_upper + 1)
    low, high = tanh_rational_bounds(Fraction(1, 2))
    expect(low < higher_low_r < higher_high_r < high, "refined_exp_certificate_not_enclosed")
    expect(high > low, "nonzero_remainder_lost")


def interval_boundary_enclosures():
    center, quantum = Fraction(1, 5), Fraction(1, 100)
    cases = (
        (Fraction(196, 1000), Fraction(204, 1000), "REPORTING_AGREEMENT"),
        (Fraction(204, 1000), Fraction(206, 1000), "INDETERMINATE_REPORTING_BOUNDARY"),
        (Fraction(204, 1000), Fraction(205, 1000), "INDETERMINATE_REPORTING_BOUNDARY"),
        (Fraction(194, 1000), Fraction(196, 1000), "INDETERMINATE_REPORTING_BOUNDARY"),
        (Fraction(195, 1000), Fraction(196, 1000), "INDETERMINATE_REPORTING_BOUNDARY"),
        (Fraction(195, 1000), Fraction(205, 1000), "INDETERMINATE_REPORTING_BOUNDARY"),
        (Fraction(206, 1000), Fraction(207, 1000), "REPORTING_DISAGREEMENT"),
        (Fraction(193, 1000), Fraction(194, 1000), "REPORTING_DISAGREEMENT"),
    )
    for low, high, expected in cases:
        expect(classify_interval(low, high, center, quantum) == expected,
               "wrong_enclosure_reporting_boundary_status")
    rejected("interval_shape", lambda: classify_interval(Fraction(1), Fraction(0), center, quantum))


def control_registry():
    controls = []

    def add(name, category, action):
        controls.append((name, category, action))

    add("complete_numeric_12_fields_shuffled_input", "candidate", complete_candidate)
    for name, metric, value, status in (
        ("r_lower_tie", "pearson_r", ".195", "INDETERMINATE_REPORTING_BOUNDARY"),
        ("r_upper_tie", "pearson_r", ".205", "INDETERMINATE_REPORTING_BOUNDARY"),
        ("r_lower_inside", "pearson_r", ".1950001", "REPORTING_AGREEMENT"),
        ("r_upper_inside", "pearson_r", ".2049999", "REPORTING_AGREEMENT"),
        ("r_lower_outside", "pearson_r", ".1949999", "REPORTING_DISAGREEMENT"),
        ("r_upper_outside", "pearson_r", ".2050001", "REPORTING_DISAGREEMENT"),
        ("p_lower_tie", "p_two_sided", ".1225", "INDETERMINATE_REPORTING_BOUNDARY"),
        ("p_upper_tie", "p_two_sided", ".1235", "INDETERMINATE_REPORTING_BOUNDARY"),
        ("p_lower_inside", "p_two_sided", ".1225001", "REPORTING_AGREEMENT"),
        ("p_upper_outside", "p_two_sided", ".1235001", "REPORTING_DISAGREEMENT"),
        ("exact_k_mismatch", "k", "6", "EXACT_COUNT_DISAGREEMENT"),
        ("exact_N_mismatch", "N", "101", "EXACT_COUNT_DISAGREEMENT"),
    ):
        add(name, "candidate", lambda m=metric, v=value, s=status: candidate_field_case("amy_self", m, v, s))
    add("negative_r_tie", "candidate", lambda: candidate_field_case(
        "quest_self", "pearson_r", "-.305", "INDETERMINATE_REPORTING_BOUNDARY"))
    add("negative_r_inside", "candidate", lambda: candidate_field_case(
        "quest_self", "pearson_r", "-.3049999", "REPORTING_AGREEMENT"))
    add("negative_r_outside", "candidate", lambda: candidate_field_case(
        "quest_self", "pearson_r", "-.3050001", "REPORTING_DISAGREEMENT"))

    for name, raw, code in (
        ("duplicate_root_key", b'{"rows":[],"rows":[]}', "duplicate_JSON_key"),
        ("duplicate_nested_key", b'{"x":{"k":5,"k":6}}', "duplicate_JSON_key"),
        ("NaN_literal", b'{"x":NaN}', "nonfinite_JSON_constant"),
        ("Infinity_literal", b'{"x":Infinity}', "nonfinite_JSON_constant"),
        ("negative_Infinity_literal", b'{"x":-Infinity}', "nonfinite_JSON_constant"),
        ("nonbytes_input", "{}", "candidate_extent"),
        ("oversized_input", b" " * 65537, "candidate_extent"),
    ):
        add(name, "protocol", lambda r=raw, c=code: rejected(c, lambda: decode_numeric_json(r)))

    for name, mutate, code in (
        ("missing_contrast", lambda p: p["rows"].pop(), "three_complete_contrasts_required"),
        ("duplicate_contrast", lambda p: p["rows"][1].update(contrast="amy_self"), "contrast_identity"),
        ("unknown_contrast", lambda p: p["rows"][1].update(contrast="unknown"), "contrast_identity"),
        ("missing_metric", lambda p: p["rows"][0]["fields"].pop("N"), "complete_four_fields_required"),
        ("extra_metric", lambda p: p["rows"][0]["fields"].update(tau=Decimal(1)), "complete_four_fields_required"),
        ("R_strings_rejected_from_candidate", lambda p: p["rows"][0].update(formatted_table=["x"] * 11), "row_keys"),
        ("extra_top_level_claim", lambda p: p.update(scientifically_qualified=True), "candidate_schema_keys"),
    ):
        add(name, "candidate", lambda m=mutate, c=code: invalid_candidate(m, c))
    for name, metric, value, code in (
        ("string_number", "pearson_r", "0.20", "finite_JSON_number_required"),
        ("boolean_number", "k", True, "finite_JSON_number_required"),
        ("null_number", "N", None, "finite_JSON_number_required"),
        ("unparsed_float", "pearson_r", 0.2, "finite_JSON_number_required"),
        ("unparsed_int", "k", 5, "finite_JSON_number_required"),
        ("Decimal_NaN", "pearson_r", Decimal("NaN"), "finite_JSON_number_required"),
        ("Decimal_Infinity", "pearson_r", Decimal("Infinity"), "finite_JSON_number_required"),
        ("r_above_domain", "pearson_r", Decimal("1.0001"), "Pearson_range"),
        ("r_below_domain", "pearson_r", Decimal("-1.0001"), "Pearson_range"),
        ("p_below_domain", "p_two_sided", Decimal("-.0001"), "p_range"),
        ("p_above_domain", "p_two_sided", Decimal("1.0001"), "p_range"),
        ("fractional_k", "k", Decimal("5.1"), "positive_exact_count"),
        ("fractional_N", "N", Decimal("100.1"), "positive_exact_count"),
        ("zero_k", "k", Decimal(0), "positive_exact_count"),
        ("negative_N", "N", Decimal(-1), "positive_exact_count"),
        ("N_less_than_k", "N", Decimal(4), "count_order"),
        ("excess_numeric_exponent", "pearson_r", Decimal("1e-401"), "numeric_extent"),
        ("excess_numeric_digits", "N", Decimal("1" * 401), "numeric_extent"),
    ):
        add(name, "candidate", lambda m=metric, v=value, c=code: invalid_candidate(
            lambda p: p["rows"][0]["fields"].__setitem__(m, v), c))

    for name, mutate, code in (
        ("target_missing_row", lambda p: p["rows"].pop(), "target_three_rows"),
        ("target_duplicate_contrast", lambda p: p["rows"][1].update(contrast="amy_self"), "target_contrast_identity"),
        ("target_missing_metric", lambda p: p["rows"][0]["display_lexemes"].pop("N"), "target_metric_support"),
        ("target_wrong_precision", lambda p: p["rows"][0]["display_lexemes"].update(pearson_r="0.200"), "published_display_precision"),
        ("target_scientific_notation", lambda p: p["rows"][0]["display_lexemes"].update(pearson_r="2e-1"), "target_fixed_decimal_lexeme"),
        ("target_count_order", lambda p: p["rows"][0]["display_lexemes"].update(N="4"), "target_count_order"),
    ):
        add(name, "target_contract", lambda m=mutate, c=code: invalid_target(m, c))

    add("native_Fisher_z_projection_separate_from_raw_diagnostic", "projection", native_projection)
    add("native_archived_display_is_not_a_score", "native", native_display_inert)
    add("unused_native_fields_not_numerically_qualified", "native", unused_native_fields_not_qualified)
    add("native_p_exact_reporting_tie", "native", native_p_boundary)
    for name, mutate, code in (
        ("native_missing_row", lambda p: p["rows"].pop(), "native_rows"),
        ("native_duplicate_contrast", lambda p: p["rows"][1].update(contrast="amy_self"), "native_contrast_identity"),
        ("native_missing_field", lambda p: p["rows"][0]["fields"].pop("tau"), "native_complete_fields"),
        ("native_null_field", lambda p: p["rows"][0]["fields"].update(tau=None), "finite_JSON_number_required"),
        ("native_short_display", lambda p: p["rows"][0]["formatted_table"].pop(), "native_archived_display_schema"),
        ("native_nonstr_display", lambda p: p["rows"][0]["formatted_table"].__setitem__(0, 1), "native_archived_display_schema"),
        ("native_fractional_df", lambda p: p["rows"][0]["fields"].update(df_Q=Decimal("4.5")), "native_exact_counts"),
        ("native_bad_p", lambda p: p["rows"][0]["fields"].update(pval_random=Decimal("1.1")), "native_p_range"),
        ("native_bad_count_order", lambda p: p["rows"][0]["fields"].update(N=Decimal(4)), "native_count_order"),
        ("native_unbounded_z", lambda p: p["rows"][0]["fields"].update(TE_random=Decimal("8.1")), "bounded_rational_Fisher_z_required"),
    ):
        add(name, "native", lambda m=mutate, c=code: invalid_native(m, c))
    add("independent_higher_order_rational_certificate", "projection", independent_refinement_certificate)
    add("interval_crossing_and_touching_reporting_boundaries", "projection", interval_boundary_enclosures)
    add("rational_tanh_zero", "projection", projection_zero)
    add("rational_tanh_sign_enclosure_symmetry", "projection", projection_bounds)
    add("rational_tanh_domain_endpoints", "projection", projection_endpoints)
    add("rational_tanh_monotonicity", "projection", projection_monotonicity)
    for name, value in (("projection_nonrational", Decimal("0.5")),
                        ("projection_above_bound", Fraction(81, 10)),
                        ("projection_below_bound", Fraction(-81, 10))):
        add(name, "projection", lambda v=value: rejected(
            "bounded_rational_Fisher_z_required", lambda: tanh_rational_bounds(v)))
    return controls


def run(core):
    """Selected worker API: run actual production functions and retain first failure.

    PASS is returned only after all dynamically registered controls complete.
    This function performs no input/output. The worker preserves this result and
    decides whether a separate authentic comparison may proceed.
    """
    global InvalidInput, compare_candidate, compare_serialized_native
    global decode_numeric_json, tanh_rational_bounds, classify_interval, _ACTIVE
    records = []
    registry = []
    harness_failure = None
    seen = set()
    _ACTIVE = {"attempted": 0, "completed": 0, "failed": 0}
    try:
        InvalidInput = core.InvalidInput
        compare_candidate = core.compare_candidate
        compare_serialized_native = core.compare_serialized_native
        decode_numeric_json = core.decode_numeric_json
        tanh_rational_bounds = core.tanh_rational_bounds
        classify_interval = core.classify_interval
        registry = control_registry()
        for name, category, action in registry:
            before = dict(_ACTIVE)
            record = {"name": name, "category": category}
            try:
                expect(name not in seen, "duplicate_control_name")
                seen.add(name)
                action()
            except Exception as exc:
                record.update(passed=False, error_type=type(exc).__name__,
                              error=str(exc), traceback=traceback.format_exc())
            else:
                record["passed"] = True
            record["assertions"] = {key: _ACTIVE[key] - before[key] for key in _ACTIVE}
            records.append(record)
            if not record["passed"]:
                break
    except Exception as exc:
        # Initialization is not a registered control and must not inflate counts.
        harness_failure = {"phase": "harness_binding_registration_or_dispatch",
                           "error_type": type(exc).__name__, "error": str(exc),
                           "traceback": traceback.format_exc()}
    finally:
        assertions = dict(_ACTIVE)
        _ACTIVE = None
    categories = sorted({row[1] for row in registry} | {x["category"] for x in records})
    groups = {}
    for category in categories:
        observed = [x for x in records if x["category"] == category]
        registered = sum(row[1] == category for row in registry)
        completed = sum(x["passed"] for x in observed)
        groups[category] = {
            "registered_controls": registered,
            "attempted_controls": len(observed),
            "completed_controls": completed,
            "failed_controls": len(observed) - completed,
            "group_completed": registered > 0 and completed == registered,
            "assertions": {key: sum(x["assertions"][key] for x in observed)
                           for key in ("attempted", "completed", "failed")},
        }
    passed = sum(x["passed"] for x in records)
    return {"schema": "nider_published_reporting_synthetic_controls_v1",
            "origin": "invented_values_only_no_authentic_targets_or_native_output",
            "status": "PASS" if harness_failure is None and records and
                      passed == len(records) == len(registry) else "FAIL",
            "executed_controls": len(records), "passed_controls": passed,
            "failed_controls": len(records) - passed,
            "registered_controls": len(registry),
            "remaining_controls_not_attempted": max(0, len(registry) - len(records)),
            "groups_attempted": sum(x["attempted_controls"] > 0 for x in groups.values()),
            "groups_completed": sum(x["group_completed"] for x in groups.values()),
            "groups": groups, "assertions": assertions,
            "harness_failure": harness_failure,
            "counter_semantics": {
                "completed_controls": "Registered action returned normally; failed actions are attempted but not completed.",
                "completed_assertions": "Predicate evaluated; failed predicates are also counted separately.",
                "harness_failure": "Separate from registered controls and never counted as an executed control.",
            },
            "executed_projection_controls": groups.get("projection", {}).get("attempted_controls", 0),
            "controls": records, "source_pin_authentication_tested": False,
            "R_or_estimator_or_model_execution": 0, "scientific_result": False,
            "qualified_reference": False, "readiness_delta": 0}
