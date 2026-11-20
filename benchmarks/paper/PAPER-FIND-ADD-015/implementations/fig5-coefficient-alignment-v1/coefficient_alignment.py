"""Source-only Figure 5 coefficient diagnostics; no fitting or paper acceptance.

The deposited notebook combines model.fixef with a population intercept.
For the inspected pymer4 v0.8.2 API, fixef means conditional coefficients,
not random deviations. Preserve both algebraic branches for adjudication.
This adapter requires an operator-supplied, explicitly keyed export. It does
not load the deposited pickle files, infer identities or choose a correction.
"""

from __future__ import annotations

import math


class AlignmentError(ValueError):
    """An export cannot support an unambiguous structural comparison."""


def _number(value, name):
    if type(value) not in (int, float):
        raise AlignmentError(name + " must be a finite JSON number, not a bool")
    original = value
    try:
        value = float(value)
    except (ValueError, OverflowError) as exc:
        raise AlignmentError(name + " is outside binary64") from exc
    if not math.isfinite(value):
        raise AlignmentError(name + " must be finite")
    if value != original:
        raise AlignmentError(name + " cannot be represented exactly as binary64")
    return value


def _identity(value):
    # Do not conflate a pandas integer cell with the text factor label "1".
    if type(value) is int:
        return (int, value)
    if type(value) is str and value:
        return (str, value)
    raise AlignmentError("cell IDs must be nonempty text or integer, not bool")


def _exact_fields(row, expected, label):
    if type(row) is not dict or set(row) != set(expected):
        raise AlignmentError(label + " has missing or unexpected fields")


def _coefficient_table(rows, expected_ids, label):
    if type(rows) is not list:
        raise AlignmentError(label + " must be a list of explicitly keyed rows")
    result = {}
    for row in rows:
        _exact_fields(row, ("cell_id", "intercept", "preceding"), label)
        cell = _identity(row["cell_id"])
        if cell in result:
            raise AlignmentError(label + " contains a duplicate cell")
        result[cell] = {
            "intercept": _number(row["intercept"], label + ".intercept"),
            "preceding": _number(row["preceding"], label + ".preceding"),
        }
    if set(result) != set(expected_ids):
        raise AlignmentError(label + " does not match the complete supplied roster")
    return result


def _finite_operation(value, name):
    if not math.isfinite(value):
        raise AlignmentError("nonfinite derived " + name)
    return value


def diagnose_group(export):
    """Join one declared full group and expose both intercept interpretations.

    Required fields: group, expected_cell_ids, fixed, conditional, random,
    trial_covariates and conditional_semantics. Coefficient rows carry exact
    cell_id/intercept/preceding fields; trial rows carry cell_id/basef. A
    repeated baseline value across DIFFERENT cells is valid. A varying baseline
    WITHIN a cell cannot define the notebook's single cell covariate and fails.

    `conditional_semantics` must explicitly be `fixed_plus_random`. This is
    a caller declaration, not runtime provenance verification. `random` is a
    separate exported ranef table; its consistency residuals are reported
    without inventing a numerical acceptance tolerance. No pass/fail score,
    historical runtime equivalence or scientific qualification is returned.
    """
    _exact_fields(export, (
        "group", "expected_cell_ids", "fixed", "conditional", "random",
        "trial_covariates", "conditional_semantics",
    ), "group export")
    if export["group"] not in ("activated", "suppressed"):
        raise AlignmentError("group must be activated or suppressed")
    if export["conditional_semantics"] != "fixed_plus_random":
        raise AlignmentError("conditional coefficient semantics must be explicit")
    roster = export["expected_cell_ids"]
    if type(roster) is not list or not roster:
        raise AlignmentError("expected_cell_ids must be a nonempty ordered list")
    keys = [_identity(cell) for cell in roster]
    if len(set(keys)) != len(keys):
        raise AlignmentError("duplicate cell in the supplied roster")
    _exact_fields(export["fixed"], ("intercept", "basef"), "fixed coefficients")
    population = _number(export["fixed"]["intercept"], "fixed.intercept")
    beta_basef = _number(export["fixed"]["basef"], "fixed.basef")
    conditional = _coefficient_table(export["conditional"], keys, "conditional")
    random = _coefficient_table(export["random"], keys, "random")
    trials = export["trial_covariates"]
    if type(trials) is not list:
        raise AlignmentError("trial_covariates must be an explicitly keyed list")
    baselines = {}
    counts = {}
    legacy_unique = []
    unique_seen = set()
    for row in trials:
        _exact_fields(row, ("cell_id", "basef"), "trial covariate")
        cell = _identity(row["cell_id"])
        baseline = _number(row["basef"], "trial.basef")
        if cell not in keys:
            raise AlignmentError("trial covariate contains an extra cell")
        if cell in baselines and baselines[cell] != baseline:
            raise AlignmentError("baseline fluorescence is not constant within a cell")
        baselines[cell] = baseline
        counts[cell] = counts.get(cell, 0) + 1
        if baseline not in unique_seen:
            unique_seen.add(baseline)
            legacy_unique.append(baseline)
    if set(baselines) != set(keys):
        raise AlignmentError("trial covariates omit a supplied roster cell")

    rows = []
    for original_id, cell in zip(roster, keys):
        cond = conditional[cell]
        ran = random[cell]
        covariate = _finite_operation(beta_basef * baselines[cell], "covariate effect")
        model_intercept = _finite_operation(cond["intercept"] + covariate,
                                             "conditional-model intercept")
        # Deliberately preserve the notebook's addition order. This is NOT
        # a claim of NumPy/R/lme4 floating-point equivalence.
        notebook_intercept = _finite_operation(
            (population + cond["intercept"]) + covariate, "literal notebook intercept")
        residual = _finite_operation(
            cond["intercept"] - (population + ran["intercept"]),
            "conditional/random identity residual")
        slope_residual = _finite_operation(
            cond["preceding"] - ran["preceding"], "slope identity residual")
        rows.append({
            "cell_id": original_id,
            "basef": baselines[cell],
            "trial_rows": counts[cell],
            "preceding_slope": cond["preceding"],
            "conditional_intercept": cond["intercept"],
            "random_intercept": ran["intercept"],
            "literal_notebook_intercept": notebook_intercept,
            "conditional_model_intercept": model_intercept,
            "literal_minus_conditional": _finite_operation(
                notebook_intercept - model_intercept, "branch difference"),
            "conditional_random_identity_residual": residual,
            "preceding_identity_residual": slope_residual,
        })
    by_cell = [baselines[cell] for cell in keys]
    return {
        "schema_version": "fig5-coefficient-alignment-diagnostic/v1",
        "group": export["group"],
        "cell_count_relative_to_supplied_roster": len(keys),
        "rows": rows,
        "population_intercept": population,
        "legacy_pd_unique_diagnostic": {
            "unique_baseline_count": len(legacy_unique),
            "cell_count": len(keys),
            "vector_length_matches": len(legacy_unique) == len(keys),
            "vector_matches_supplied_cell_order": legacy_unique == by_cell,
            "not_an_identity_join_even_if_values_match": True,
        },
        "coefficient_semantics": "caller_declared_fixed_plus_random",
        "historical_runtime_verified": False,
        "scientific_qualification": False,
        "reproduction_accepted": None,
        "improvement_accepted": None,
    }


def diagnose_panel(exports):
    """Require both named Figure 5 groups; never silently score a single group."""
    _exact_fields(exports, ("activated", "suppressed"), "panel export")
    for group in ("activated", "suppressed"):
        if type(exports[group]) is not dict or exports[group].get("group") != group:
            raise AlignmentError("panel key and declared group disagree")
    return {group: diagnose_group(exports[group]) for group in ("activated", "suppressed")}
