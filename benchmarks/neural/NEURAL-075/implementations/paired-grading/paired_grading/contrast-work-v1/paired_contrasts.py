"""Pure paired summaries of two complete NEURAL-075 scorer results.

This module neither admits prediction matrices nor authenticates provenance or
opens targets. Its caller must complete both original 30-case admissions first.
The unchanged finite scorer ordinarily emits finite metrics. Nullable summary
values are conservatively supported here only: None never admits an invalid or
missing case and never receives numerical credit or an observed-only substitute.
"""

import copy
import math

PROTOCOL = "neural075-v1"
PEOPLE = tuple("Subject" + str(i) for i in range(1, 6))
ARMS = ("neural", "no_neural", "training_permuted")
PHASES = ("imagery", "perception")
LEVELS = ("trial", "private_category_mean_scores")
METRICS = ("top1_tie_fraction", "mean_midrank", "pairwise_half_ties",
           "author_strict_greater_rank_fraction_diagnostic")
CONTROLS = ("no_neural", "training_permuted")
PRIMARY_DEFINITION = "Equal-person mean50-way imagery trial Top1; exact ties split credit"
TOLERANCE = 1e-12
CORE_FIELDS = {
    "protocol", "n_biological_people", "n_cases", "primary", "primary_definition",
    "per_case", "participant_macro", "binary_success", "execution_attested", "scientific_limits",
}
CLI_FIELDS = {"design_sha256", "context_index_sha256", "supplied_access_condition", "submitted_program_as_declared"}


def _need(ok, message):
    if not ok:
        raise ValueError(message)


def _exact(value, fields, name):
    _need(type(value) is dict and set(value) == set(fields), name + ": exact fields required")


def _scalar(value, low, high, name):
    if value is None:
        return None
    _need(type(value) in (int, float), name + ": finite number or None required")
    try:
        valid = math.isfinite(value) and low <= value <= high
    except OverflowError:
        valid = False
    _need(valid, name + ": finite metric within original bounds required")
    return value


def _mean(values):
    return None if any(value is None for value in values) else math.fsum(values) / len(values)


def _difference(left, right):
    return None if left is None or right is None else left - right


def _match(value, expected, name):
    _need((value is None) == (expected is None), name + ": exact undefinedness required")
    if value is not None:
        _need(abs(value - expected) <= TOLERANCE, name + ": inconsistent original summary")


def _metrics(value, name):
    _exact(value, METRICS, name)
    for metric in METRICS:
        low, high = (1, 50) if metric == "mean_midrank" else (0, 1)
        _scalar(value[metric], low, high, name + "/" + metric)


def _levels(value, name):
    _exact(value, LEVELS, name)
    for level in LEVELS:
        _metrics(value[level], name + "/" + level)


def _validate(result, access):
    _need(type(result) is dict and set(result) in (CORE_FIELDS, CORE_FIELDS | CLI_FIELDS),
          "Complete unchanged scorer core, optionally with all CLI provenance fields")
    _need(result["protocol"] == PROTOCOL and type(result["n_biological_people"]) is int and
          result["n_biological_people"] == 5 and type(result["n_cases"]) is int and result["n_cases"] == 30,
          "Original protocol, five people and all 30 cases")
    _need(result["primary_definition"] == PRIMARY_DEFINITION, "Original trial-level primary definition")
    _need(result["binary_success"] is None and result["execution_attested"] is False,
          "Original unthresholded and externally unattested result status")
    _need(type(result["scientific_limits"]) is list and result["scientific_limits"] and
          all(type(item) is str and item for item in result["scientific_limits"]), "Retained scientific limitations")
    if CLI_FIELDS <= set(result):
        _need(result["supplied_access_condition"] == access, "Correct supplied access-result identity")
        # These declared values are retained, not authenticated or interpreted as
        # proof of the actual design, code, execution or held-target custody.
        _need(type(result["design_sha256"]) is str and type(result["context_index_sha256"]) is str and
              type(result["submitted_program_as_declared"]) is dict, "Original declared CLI provenance shape")
    cases = result["per_case"]
    expected_cases = {person + "/" + arm + "/" + phase for person in PEOPLE for arm in ARMS for phase in PHASES}
    _exact(cases, expected_cases, "All original person/arm/phase cases")
    for case, values in cases.items():
        _levels(values, case)
    macro = result["participant_macro"]
    _exact(macro, PHASES, "Both original phases")
    for phase in PHASES:
        _exact(macro[phase], (*ARMS, "paired_neural_minus_controls"), phase + " macro")
        for arm in ARMS:
            values = macro[phase][arm]
            _levels(values, phase + "/" + arm)
            for level in LEVELS:
                for metric in METRICS:
                    expected = _mean([cases[f"{person}/{arm}/{phase}"][level][metric] for person in PEOPLE])
                    _match(values[level][metric], expected, phase + "/" + arm + "/" + level + "/" + metric)
        controls = macro[phase]["paired_neural_minus_controls"]
        _exact(controls, CONTROLS, phase + " original control contrasts")
        for control in CONTROLS:
            _exact(controls[control], PEOPLE, phase + "/" + control + " original paired support")
            for person in PEOPLE:
                expected = _difference(cases[f"{person}/neural/{phase}"]["trial"]["top1_tie_fraction"],
                                       cases[f"{person}/{control}/{phase}"]["trial"]["top1_tie_fraction"])
                value = _scalar(controls[control][person], -1, 1, "Original signed control difference")
                _match(value, expected, "Original signed control difference")
    primary = _scalar(result["primary"], 0, 1, "Original primary")
    _match(primary, macro["imagery"]["neural"]["trial"]["top1_tie_fraction"], "Original primary")
    return result


def _paired(a, b, definition):
    rows = [{"person": person, "A": a[person], "B": b[person],
             "B_minus_A": _difference(b[person], a[person])} for person in PEOPLE]
    values = [row["B_minus_A"] for row in rows]
    defined = [row["person"] for row in rows if row["B_minus_A"] is not None]
    missing = [row["person"] for row in rows if row["B_minus_A"] is None]
    return {"definition": definition, "per_person": rows,
            "equal_person_mean": _mean(values),
            "range": None if missing else {"minimum": min(values), "maximum": max(values)},
            "n_people": 5, "n_defined": len(defined), "defined_people": defined,
            "undefined_people": missing, "observed_only_substitution": False}


def compare_results(result_a, result_b):
    """Return complete, detached A/B originals and descriptive Top-1 contrasts.

    Both result cores must contain all five original people, all three arms and
    both phases. Every original trial/category metric, macro and within-access
    contrast is checked for numeric consistency. This cannot authenticate how
    those values were produced. Explicit nullable summaries propagate through
    all-person means and ranges; they never bypass prediction admission.

    New contrasts use trial top1_tie_fraction only. Category metrics remain
    separate in original_results: they average frozen prediction-score vectors
    by private category, not fMRI features before decoding. The historical
    strict-greater diagnostic is retained separately and never treated as Top-1.
    """
    a, b = _validate(result_a, "A"), _validate(result_b, "B")
    access, interactions = {}, {}
    for phase in PHASES:
        access[phase], interactions[phase] = {}, {}
        for arm in ARMS:
            av = {person: a["per_case"][f"{person}/{arm}/{phase}"]["trial"]["top1_tie_fraction"] for person in PEOPLE}
            bv = {person: b["per_case"][f"{person}/{arm}/{phase}"]["trial"]["top1_tie_fraction"] for person in PEOPLE}
            access[phase][arm] = _paired(av, bv, "B minus A trial Top1 with fractional ties")
        for control in CONTROLS:
            av = a["participant_macro"][phase]["paired_neural_minus_controls"][control]
            bv = b["participant_macro"][phase]["paired_neural_minus_controls"][control]
            interactions[phase][control] = _paired(
                av, bv, "(B neural minus B control) minus (A neural minus A control), trial fractional-tie Top1")
    return {
        "schema": "neural075_paired_contrasts_v1", "protocol": PROTOCOL,
        "n_biological_people": 5, "n_cases_per_access": 30,
        "original_results": {"A": copy.deepcopy(a), "B": copy.deepcopy(b)},
        "primary": {"phase": "imagery", "arm": "neural", "level": "trial",
                    "metric": "top1_tie_fraction", "contrast": copy.deepcopy(access["imagery"]["neural"])},
        "access_contrasts": access, "differences_of_access_contrasts": interactions,
        "perception_role": "Separate diagnostic phase; never pooled with imagery or weighted by trial count",
        "category_metric_meaning": "Original private_category_mean_scores averages frozen prediction-score vectors by category; it does not average fMRI features before decoding",
        "historical_diagnostic_meaning": "Original strict-greater rank fraction is a separate diagnostic; all-50-way ties can score 1 there but trial Top1 is 0.02",
        "undefined_policy": "All five people and 30 cases remain required; any undefined paired value withholds the full mean and range",
        "nullable_summary_support_is_prediction_admission": False,
        "numerical_provenance_authenticated": False, "execution_attestation_performed": False,
        "scientific_success": None, "confidence_interval": None, "p_value": None,
        "causal_neural_information_established": False, "internal_understanding_established": False,
    }
