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
    # Historical v1 references retain their original cell/contrast-only score.
    summary_component = "deterministic_figure_summary_reproduction"
    if reference["schema"] == "tms-full-behavior-component-v2":
        results[summary_component] = []
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
        if summary_component in results:
            _equal(expected["figure_condition_summaries"], proposed.get("figure_condition_summaries"),
                   metric + "/figure_condition_summaries", results[summary_component])
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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("candidate")
    arguments = parser.parse_args()
    print(json.dumps(score(load_json(arguments.reference), load_json(arguments.candidate)), allow_nan=False))
