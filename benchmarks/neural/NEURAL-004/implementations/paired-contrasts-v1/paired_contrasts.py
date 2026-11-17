"""Post-release paired comparisons of the protected NEURAL-004 prediction grade.

This consumes the existing grader's result; it does not score forecasts, open the
target barrier, authenticate a supplied JSON document, or qualify an experiment.
Call only in the operator/scorer process after grade_prediction_panels returns.
All comparisons are fixed here, before any authentic results have been examined.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics


PEOPLE = tuple(str(i) for i in range(26))
POLICIES = tuple(f"{mode}/{view}" for mode in ("P", "I") for view in ("B", "E", "H", "EH"))
UNIT = "fractional contrast squared"


class InvalidGrade(ValueError):
    """The supplied result does not satisfy the existing complete-panel contract."""


def _need(condition, message):
    if not condition:
        raise InvalidGrade(message)


def _number(value):
    _need(type(value) in (int, float) and math.isfinite(value), "finite numeric loss")
    _need(0 <= value <= 1, "fractional-contrast squared error in [0,1]")
    return float(value)


def _same_number(actual, expected):
    _need(math.isclose(_number(actual), expected, rel_tol=1e-12, abs_tol=1e-15),
          "loss does not match its trial/person components")


def _panel(panel):
    _need(type(panel) is dict and panel.get("status") in ("complete", "incomplete"), "prediction panel status")
    rows = panel.get("person_results")
    failures = panel.get("failures")
    _need(type(rows) is list and type(failures) is list, "person results and failures")
    by_person = {}
    for row in rows:
        _need(type(row) is dict and set(row) == {"person", "trial_errors", "n", "mse"}, "source person-loss fields")
        person = row["person"]
        _need(person in PEOPLE and person not in by_person, "unique original person")
        trials = row["trial_errors"]
        _need(type(row["n"]) is int and row["n"] > 0 and type(trials) is list and len(trials) == row["n"],
              "complete nonempty trial support")
        ids = set()
        errors = []
        for trial in trials:
            _need(type(trial) is dict and set(trial) == {"id", "squared_error"}, "source trial-error fields")
            _need(type(trial["id"]) is str and trial["id"] and trial["id"] not in ids, "unique context-local trial id")
            ids.add(trial["id"])
            errors.append(_number(trial["squared_error"]))
        mse = math.fsum(errors) / len(errors)
        _same_number(row["mse"], mse)
        by_person[person] = {"mse": mse, "n": row["n"]}
    failed = {}
    for failure in failures:
        _need(type(failure) is dict and set(failure) == {"person", "status"}, "source failure fields")
        person = failure["person"]
        _need(person in PEOPLE and person not in by_person and person not in failed, "unique failed person")
        _need(failure["status"] in ("failed", "blocked"), "preserved failed/blocked context")
        failed[person] = failure["status"]
    _need(set(by_person) | set(failed) == set(PEOPLE), "all26 original people, including failures")
    _need([r["person"] for r in rows] == [p for p in PEOPLE if p in by_person], "source-ordered person results")
    _need([r["person"] for r in failures] == [p for p in PEOPLE if p in failed], "source-ordered failures")
    if failed:
        _need(panel["status"] == "incomplete" and panel.get("macro_mse") is None, "failed person prevents panel macro")
    else:
        _need(panel["status"] == "complete", "all26 complete person losses")
        _same_number(panel.get("macro_mse"), math.fsum(by_person[p]["mse"] for p in PEOPLE) / 26)
        _need(panel.get("unit") == UNIT, "fractional contrast units")
    return by_person, failed


def _comparison(identifier, kind, baseline, alternative, panels):
    left, left_failed = panels[baseline]
    right, right_failed = panels[alternative]
    pairs = []
    failures = []
    for person in PEOPLE:
        if person in left_failed or person in right_failed:
            failures.append({"person": person, "baseline_status": left_failed.get(person, "complete"),
                             "alternative_status": right_failed.get(person, "complete")})
            continue
        _need(left[person]["n"] == right[person]["n"], "same retained trial count for paired information views")
        pairs.append({"person": person, "n_trials": left[person]["n"],
                      "baseline_mse": left[person]["mse"], "alternative_mse": right[person]["mse"],
                      "baseline_minus_alternative_mse": left[person]["mse"] - right[person]["mse"]})
    result = {"id": identifier, "kind": kind, "baseline": baseline, "alternative": alternative,
              "status": "incomplete" if failures else "complete", "people": pairs, "failures": failures,
              "unit": UNIT, "positive_means": "lower MSE for alternative", "person_macro_difference": None,
              "median_person_difference": None, "minimum_person_difference": None, "maximum_person_difference": None,
              "descriptive_delete_one_person_macro": None, "population_confidence_interval": None}
    if failures:
        return result
    values = [row["baseline_minus_alternative_mse"] for row in pairs]
    result.update(person_macro_difference=math.fsum(values) / 26,
                  median_person_difference=statistics.median(values), minimum_person_difference=min(values),
                  maximum_person_difference=max(values),
                  descriptive_delete_one_person_macro=[
                      {"omitted_person": person, "difference": math.fsum(values[:i] + values[i + 1:]) / 25}
                      for i, person in enumerate(PEOPLE)])
    return result


def paired_contrasts(grade):
    """Return 15 prespecified paired contrasts, preserving failures and signs.

    The input must come directly from the protected grade_prediction_panels.
    Its target-map checks establish identical canonical trial support. Trial IDs
    differ across actor contexts by design, so this extension never joins them.
    The digest binds the result used, but is not an authentication credential.
    Returned records belong to the post-seal report, never a prediction context.
    """
    _need(type(grade) is dict and grade.get("schema") == "neural004_prediction_grade_v1", "protected prediction-grade schema")
    release = grade.get("release_pin")
    _need(type(release) is dict and set(release) == {"bytes", "sha256"}, "original target-release receipt pin")
    _need(type(release["bytes"]) is int and release["bytes"] >= 0 and type(release["sha256"]) is str
          and len(release["sha256"]) == 64 and all(c in "0123456789abcdef" for c in release["sha256"]),
          "original target-release receipt pin format")
    actors, references = grade.get("actors"), grade.get("references")
    _need(type(actors) is dict and set(actors) == set(POLICIES), "all eight actor panels")
    _need(type(references) is dict and set(references) == {"B", "N"}, "both reference panels")
    panels = {key: _panel(panel) for key, panel in actors.items()}
    panels.update({f"reference/{key}": _panel(panel) for key, panel in references.items()})
    # Every successful context represents the same retained trials for a person.
    # Do this even for incomplete panels, without computing a complete-case macro.
    for person in PEOPLE:
        counts = {rows[person]["n"] for rows, _ in panels.values() if person in rows}
        _need(len(counts) <= 1, "same source support across actor and reference panels")
    complete = all(not failed for _, failed in panels.values())
    _need(type(grade.get("whole_prediction_complete")) is bool and grade["whole_prediction_complete"] == complete,
          "whole-panel completeness matches actual person dispositions")
    comparisons = []
    for mode in ("P", "I"):
        for baseline, alternative in (("B", "E"), ("B", "H"), ("B", "EH"), ("E", "EH"), ("H", "EH")):
            comparisons.append(_comparison(f"{mode}/{alternative}_vs_{baseline}", "matched_information_view",
                                           f"{mode}/{baseline}", f"{mode}/{alternative}", panels))
    for view in ("B", "E", "H", "EH"):
        comparisons.append(_comparison(f"I_vs_P/{view}", "matched_mode", f"P/{view}", f"I/{view}", panels))
    comparisons.append(_comparison("reference/N_vs_B", "matched_reference", "reference/B", "reference/N", panels))
    try:
        raw = json.dumps(grade, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise InvalidGrade("grade must be finite JSON") from exc
    return {"schema": "neural004_paired_contrasts_v1", "input_grade_sha256": hashlib.sha256(raw).hexdigest(),
            "source_release_pin": dict(release),
            "comparisons": comparisons, "all_comparisons_complete": all(c["status"] == "complete" for c in comparisons),
            "aggregation": "equal mean over all26 held people; no trial pooling or failure deletion",
            "uncertainty": "fixed-vector delete-one-person sensitivity; overlapping LOPO fits are not independent replicates",
            "interpretation": "matched prediction contrasts conditional on the admitted data, methods and resource profiles",
            "direct_or_viewer_understanding_established": False, "whole_study_qualified": False}
