"""Compare complete behavior-component outputs; never declares whole-paper success."""
import json
import math

COMPONENTS = {
    "deterministic_figure_reproduction": ("figure_mean_abs", "valid_trials", "missing_trials"),
    "deterministic_helper_formula_reproduction": ("source_helper_mean_signed",),
    "paired_statistics": ("figure_paired", "source_helper_signed_paired"),
    "corrected_scientific_inference": ("corrected_participant_sign_flip", "corrected_participant_bootstrap",
                                       "corrected_sign_flip_holm_six_contrasts", "leave_one_person_out"),
}


def _equal(a, b, path, errors):
    if type(a) is float:
        if type(b) not in (int, float) or not math.isfinite(b) or not math.isclose(a, b, rel_tol=1e-7, abs_tol=1e-9):
            errors.append(path)
    elif type(a) is dict:
        if type(b) is not dict or set(a) != set(b):
            errors.append(path + ":keys")
            return
        for key in a:
            _equal(a[key], b[key], path + "/" + key, errors)
    elif type(a) is list:
        if type(b) is not list or len(a) != len(b):
            errors.append(path + ":length")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            _equal(x, y, path + "/" + str(i), errors)
    elif type(a) is not type(b) or a != b:
        errors.append(path)


def score(reference, candidate):
    """Separate scientific and literal-deterministic scores; no unknown historical p-value target."""
    results = {name: [] for name in COMPONENTS}
    if (type(candidate) is not dict or candidate.get("schema") != reference["schema"]
            or type(candidate.get("roster")) is not list
            or any(type(x) is not int for x in candidate["roster"])
            or candidate["roster"] != reference["roster"]):
        return {"accepted": False, "failure": "schema/cohort", "whole_task_qualified": False}
    if type(candidate.get("metrics")) is not dict or set(candidate["metrics"]) != set(reference["metrics"]):
        return {"accepted": False, "failure": "metric census", "whole_task_qualified": False}
    for metric, expected in reference["metrics"].items():
        proposed = candidate["metrics"][metric]
        if type(proposed) is not dict or not {"participant_cells", "contrasts"}.issubset(proposed):
            return {"accepted": False, "failure": "metric schema", "whole_task_qualified": False}
        cells = proposed["participant_cells"]
        expected_cells = expected["participant_cells"]
        if type(cells) is not list or len(cells) != len(expected_cells):
            return {"accepted": False, "failure": "participant-condition census", "whole_task_qualified": False}
        for i, (e, c) in enumerate(zip(expected_cells, cells)):
            if (type(c) is not dict or type(c.get("person")) is not int
                    or c.get("person") != e["person"] or c.get("condition") != e["condition"]):
                return {"accepted": False, "failure": "participant-condition identity", "whole_task_qualified": False}
            for component in ("deterministic_figure_reproduction", "deterministic_helper_formula_reproduction"):
                for key in COMPONENTS[component]:
                    _equal(e[key], c.get(key), metric + "/cells/" + str(i) + "/" + key, results[component])
        contrasts = proposed["contrasts"]
        if type(contrasts) is not dict or set(contrasts) != set(expected["contrasts"]):
            return {"accepted": False, "failure": "contrast census", "whole_task_qualified": False}
        for name, e in expected["contrasts"].items():
            c = contrasts[name]
            if type(c) is not dict or c.get("a") != e["a"] or c.get("b") != e["b"]:
                return {"accepted": False, "failure": "contrast direction", "whole_task_qualified": False}
            for component in ("paired_statistics", "corrected_scientific_inference"):
                for key in COMPONENTS[component]:
                    _equal(e[key], c.get(key), metric + "/contrasts/" + name + "/" + key, results[component])
    return {"accepted": not any(results.values()),
            "components": {name: {"passed": not errors, "mismatches": errors} for name, errors in results.items()},
            "literal_randomized_statistic_scored": False,
            "whole_task_qualified": False}


def load_json(path):
    def pairs(items):
        output = {}
        for key, value in items:
            if key in output:
                raise ValueError("duplicate JSON key")
            output[key] = value
        return output
    with open(path, encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=pairs,
                         parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))



# Participant boundary adapter. The accepted component arithmetic above is unchanged.
import hashlib

CAP = 2 * 1024 * 1024
ROSTER = (1, 3, 5, 6, 7, 10, 12, 14, 15, 17, 22, 23, 25, 26, 27)
CONDITIONS = ("No TMS", "mid inPF", "mid outPF", "early inPF", "early outPF", "midrep inPF", "midrep outPF")
METRICS = ("ierr", "isacc_rt", "isacc_peakvel")
CONTRASTS = {
    "exp1_in_minus_no": ("mid inPF", "No TMS"),
    "exp1_in_minus_out": ("mid inPF", "mid outPF"),
    "exp1_out_minus_no": ("mid outPF", "No TMS"),
    "exp2_middle_in_minus_out": ("midrep inPF", "midrep outPF"),
    "exp2_early_in_minus_out": ("early inPF", "early outPF"),
    "exp2_early_in_minus_middle_in": ("early inPF", "midrep inPF"),
}
CELL_KEYS = {"person", "condition", "valid_trials", "missing_trials", "figure_mean_abs", "source_helper_mean_signed"}
SUMMARY_KEYS = {"n", "mean", "sample_sd", "standard_error", "df", "t", "cohens_dz", "degenerate"}
CONTRAST_KEYS = {"a", "b", "figure_paired", "source_helper_signed_paired", "corrected_participant_sign_flip", "corrected_participant_bootstrap", "leave_one_person_out", "corrected_sign_flip_holm_six_contrasts"}
SCHEMA = "tms-full-behavior-component-v1"

class InvalidSubmission(ValueError):
    pass

class InvalidReference(ValueError):
    pass


def need(condition, reason):
    if not condition:
        raise InvalidSubmission(reason)


def decode(raw, error_class=InvalidSubmission):
    try:
        need(type(raw) is bytes and 0 < len(raw) <= CAP, "bounded submission bytes")
        def pairs(items):
            result = {}
            for key, value in items:
                need(key not in result, "duplicate JSON key")
                result[key] = value
            return result
        def bad(_):
            raise InvalidSubmission("nonfinite JSON constant")
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=bad)
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError) as exc:
        raise error_class(str(exc)) from exc


def keys(value, expected, reason):
    need(type(value) is dict and set(value) == set(expected), reason)


def number(value, reason, minimum=None, maximum=None):
    try:
        good = type(value) in (int, float) and math.isfinite(value)
    except (OverflowError, ValueError):
        good = False
    need(good, reason)
    if minimum is not None:
        need(value >= minimum, reason)
    if maximum is not None:
        need(value <= maximum, reason)


def integer(value, reason, minimum=0):
    need(type(value) is int and value >= minimum, reason)


def summary(value, n):
    keys(value, SUMMARY_KEYS, "complete paired summary")
    need(type(value["n"]) is int and value["n"] == n and type(value["df"]) is int and value["df"] == n - 1, "paired participant denominator")
    number(value["mean"], "finite paired mean")
    number(value["sample_sd"], "nonnegative paired SD", 0)
    number(value["standard_error"], "nonnegative paired SE", 0)
    if value["sample_sd"] == 0:
        expected = "all_zero" if value["mean"] == 0 else "constant_nonzero"
        need(value["standard_error"] == 0 and value["t"] is None and value["cohens_dz"] is None and value["degenerate"] == expected, "explicit degenerate paired summary")
    else:
        need(value["standard_error"] > 0 and value["degenerate"] is None, "ordinary paired summary status")
        number(value["t"], "finite paired t")
        number(value["cohens_dz"], "finite paired effect")


def validate(value):
    """Require every scientific field before comparison; no missing-key-as-null pass."""
    keys(value, ("schema", "roster", "metrics"), "exact submission fields")
    need(value["schema"] == SCHEMA, "submission schema")
    need(type(value["roster"]) is list and all(type(x) is int for x in value["roster"]) and value["roster"] == list(ROSTER), "complete ordered fifteen-person roster")
    keys(value["metrics"], METRICS, "complete three outcomes")
    for metric in METRICS:
        result = value["metrics"][metric]
        keys(result, ("participant_cells", "contrasts"), "exact metric fields")
        cells = result["participant_cells"]
        need(type(cells) is list and len(cells) == 105, "complete 105 cells per outcome")
        for i, (person, condition) in enumerate((p, c) for p in ROSTER for c in CONDITIONS):
            cell = cells[i]
            keys(cell, CELL_KEYS, "exact participant cell fields")
            need(type(cell["person"]) is int and cell["person"] == person and cell["condition"] == condition, "unique ordered participant-condition cells")
            integer(cell["valid_trials"], "positive valid-trial count", 1)
            integer(cell["missing_trials"], "nonnegative missing-trial count")
            number(cell["figure_mean_abs"], "finite absolute figure mean", 0)
            number(cell["source_helper_mean_signed"], "finite signed helper mean")
        keys(result["contrasts"], CONTRASTS, "complete six contrasts per outcome")
        for name, (a, b) in CONTRASTS.items():
            contrast = result["contrasts"][name]
            keys(contrast, CONTRAST_KEYS, "complete contrast fields")
            need(contrast["a"] == a and contrast["b"] == b, "declared contrast direction")
            summary(contrast["figure_paired"], 15)
            summary(contrast["source_helper_signed_paired"], 15)
            sf = contrast["corrected_participant_sign_flip"]
            keys(sf, ("p_two_sided", "extreme", "enumerated", "tie_tolerance", "unit", "assumption"), "complete sign-pattern fields")
            integer(sf["extreme"], "sign-pattern extreme count")
            need(type(sf["enumerated"]) is int and sf["enumerated"] == 32768 and sf["extreme"] <= 32768, "full sign-pattern enumeration")
            number(sf["p_two_sided"], "finite sign-pattern probability", 0, 1)
            number(sf["tie_tolerance"], "finite nonnegative tie tolerance", 0)
            need(sf["unit"] == "participant" and sf["assumption"] == "joint sign exchangeability of paired differences", "sign-pattern scope")
            bs = contrast["corrected_participant_bootstrap"]
            keys(bs, ("lower", "upper", "confidence", "draws", "seed", "method"), "complete bootstrap fields")
            number(bs["lower"], "finite bootstrap lower")
            number(bs["upper"], "finite bootstrap upper")
            number(bs["confidence"], "finite bootstrap confidence")
            need(bs["lower"] <= bs["upper"] and bs["confidence"] == .95 and type(bs["draws"]) is int and bs["draws"] == 2000 and type(bs["seed"]) is int and bs["seed"] == 20261114 and bs["method"] == "participant-paired percentile bootstrap; type7 quantiles", "fixed bootstrap convention")
            number(contrast["corrected_sign_flip_holm_six_contrasts"], "finite Holm probability", 0, 1)
            loo = contrast["leave_one_person_out"]
            need(type(loo) is list and len(loo) == 15, "all fifteen leave-one-out summaries")
            for person, item in zip(ROSTER, loo):
                keys(item, ("excluded_person", "summary"), "exact leave-one-out fields")
                need(type(item["excluded_person"]) is int and item["excluded_person"] == person, "unique ordered omission")
                summary(item["summary"], 14)
    return value


def submission_from_reference(reference):
    try:
        keys(reference, ("schema", "roster", "metrics", "helper_reproduction_scope", "complete_task_qualified", "intake"), "complete accepted reference envelope")
        need(reference["complete_task_qualified"] is False and type(reference["helper_reproduction_scope"]) is str and type(reference["intake"]) is dict, "reference scope metadata")
        submission = {k: reference[k] for k in ("schema", "roster", "metrics")}
        validate(submission)
        return submission
    except (InvalidSubmission, ValueError, TypeError, OverflowError) as exc:
        raise InvalidReference(str(exc)) from exc


def score_submission(candidate_raw, reference_raw, expected_reference_sha256):
    if type(reference_raw) is not bytes or not 0 < len(reference_raw) <= CAP or type(expected_reference_sha256) is not str or hashlib.sha256(reference_raw).hexdigest() != expected_reference_sha256:
        raise InvalidReference("protected reference identity")
    reference = decode(reference_raw, InvalidReference)
    submission_from_reference(reference)
    try:
        candidate = validate(decode(candidate_raw))
    except InvalidSubmission as exc:
        return {"status": "invalid_submission", "score": 0.0, "reason": str(exc), "whole_task_qualified": False}
    result = score(reference, candidate)
    return {"status": "scored", "score": 1.0 if result["accepted"] else 0.0,
            "component_assessment": result, "coverage": {"participants": 15, "cells": 315, "contrasts": 18, "omissions": 270},
            "score_meaning": "complete prescribed behavior-component agreement; no improvement reward",
            "whole_task_qualified": False}
