"""Strict, standard-library admission and scoring for release-native Figure 1H."""
from __future__ import annotations

import bisect
import hashlib
import json
import math
from pathlib import Path

TASK = "PAPER-FIND-REP-003"
COMPONENT = "opto-figure1h-release-native-v1"
DATA_SHA = "9d2be90908a05684dff9871697f5c37bb4f93522af67bf2625219f12cb4fd19c"
REVISION = "815b610b3beddfed5a3abf611d3a465ab9e4ce5c"
EDGES = [i * (9.0 / 29) for i in range(30)]
SESSIONS = {
    ("cfaVG1", "20210304_153342"): 264,
    ("cfaVG1", "20210305_153354"): 400,
    ("cfaVG1", "20210311_153800"): 431,
    ("cfaVG1", "20210312_150224"): 415,
    ("cfaVG4", "20210601_152047"): 476,
    ("cfaVG4", "20210602_145241"): 377,
    ("cfaVG4", "20210603_144703"): 521,
    ("cfaVG4", "20210604_134012"): 420,
}


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def exact_keys(value, expected, name):
    require(type(value) is dict and set(value) == set(expected), f"{name}: unexpected/missing fields")


def integer(value, name):
    require(type(value) is int and value >= 0, f"{name}: nonnegative integer required")
    return value


def finite(value, name):
    require(type(value) in (int, float) and math.isfinite(value), f"{name}: finite number required")
    return float(value)


def binary(value, name):
    require(type(value) in (bool, int) and value in (0, 1), f"{name}: binary required")
    return bool(value)


def identity(row):
    require(type(row) is dict, "trial must be an object")
    require(type(row.get("mouse")) is str and type(row.get("session")) is str, "trial identity strings required")
    trial = integer(row.get("trial_number"), "trial_number")
    require(trial > 0, "trial_number must be positive")
    return row["mouse"], row["session"], trial


def index_trials(rows):
    require(type(rows) is list and rows, "nonempty complete trial list required")
    result = {}
    for row in rows:
        key = identity(row)
        require(key not in result, f"duplicate trial identity {key}")
        result[key] = row
    return result


def read_json(path):
    require(Path(path).is_file() and not Path(path).is_symlink(), "ordinary JSON file required")
    require(Path(path).stat().st_size <= 32 * 1024 * 1024, "JSON exceeds 32 MiB")
    raw = Path(path).read_bytes()
    require(len(raw) <= 32 * 1024 * 1024, "JSON exceeds 32 MiB")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"duplicate JSON member {key}")
            result[key] = value
        return result
    def bad(value):
        raise ContractError(f"nonfinite JSON constant {value}")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def reconstruct(rows):
    """Operator reference port of pinned plotOptoHists; no paper numbers embedded."""
    keyed = index_trials(rows)
    trials, values = [], {"control": [], "opto": []}
    for key, row in sorted(keyed.items()):
        success = binary(row["success"], "success")
        problem = binary(row["optoProblem"], "optoProblem")
        wrong = binary(row["wrongGrabFirst"], "wrongGrabFirst")
        group = "opto" if binary(row["optoTrial"], "optoTrial") else "control"
        grab = None if row["grabTimeC"] is None else finite(row["grabTimeC"], "grabTimeC")
        lift = None if row["liftTimeC"] is None else finite(row["liftTimeC"], "liftTimeC")
        selected = success and not problem and not wrong and grab is not None and lift is not None and grab > lift
        contact = grab / 1000 if selected else None
        trials.append(dict(mouse=key[0], session=key[1], trial_number=key[2],
                           condition=group, selected=selected, contact_seconds=contact))
        if selected:
            values[group].append(contact)
    histograms = {}
    for group, observations in values.items():
        require(observations, f"no selected {group} trials")
        counts = [0] * 29
        for value in observations:
            if EDGES[0] <= value <= EDGES[-1]:
                position = min(bisect.bisect_right(EDGES, value) - 1, 28)
                counts[position] += 1
        histograms[group] = dict(selected_trials=len(observations), counts=counts,
                                 probability=[count / len(observations) for count in counts],
                                 outside_display_window=len(observations) - sum(counts))
    return dict(task_id=TASK, component=COMPONENT, input_sha256=DATA_SHA,
                trials=trials, bin_edges_seconds=EDGES, histograms=histograms)


def validate_submission(value, roster):
    exact_keys(value, ("task_id", "component", "input_sha256", "trials", "bin_edges_seconds", "histograms"), "submission")
    require(value["task_id"] == TASK and value["component"] == COMPONENT, "task/component mismatch")
    require(value["input_sha256"] == DATA_SHA, "input binding mismatch")
    keyed = index_trials(value["trials"])
    require(set(keyed) == set(roster), "complete trial identity coverage required")
    for key, row in keyed.items():
        exact_keys(row, ("mouse", "session", "trial_number", "condition", "selected", "contact_seconds"), "trial")
        require(row["condition"] in ("control", "opto"), "trial condition invalid")
        selected = binary(row["selected"], "selected")
        if selected:
            finite(row["contact_seconds"], "contact_seconds")
        else:
            require(row["contact_seconds"] is None, "excluded contact_seconds must be null")
    edges = value["bin_edges_seconds"]
    require(type(edges) is list and len(edges) == 30, "30 bin edges required")
    for observed, expected in zip(edges, EDGES):
        require(abs(finite(observed, "edge") - expected) <= 1e-12, "source bin edges mismatch")
    exact_keys(value["histograms"], ("control", "opto"), "histograms")
    for group, hist in value["histograms"].items():
        exact_keys(hist, ("selected_trials", "counts", "probability", "outside_display_window"), group)
        n = integer(hist["selected_trials"], "selected_trials")
        out = integer(hist["outside_display_window"], "outside_display_window")
        require(n > 0 and out <= n, "invalid histogram population")
        require(type(hist["counts"]) is list and len(hist["counts"]) == 29, "29 counts required")
        require(type(hist["probability"]) is list and len(hist["probability"]) == 29, "29 probabilities required")
        counts = [integer(x, "count") for x in hist["counts"]]
        require(sum(counts) + out == n, "histogram accounting does not close")
        require(sum(binary(r["selected"], "selected") and r["condition"] == group for r in keyed.values()) == n,
                "selected trial/histogram population mismatch")
        for count, probability in zip(counts, hist["probability"]):
            p = finite(probability, "probability")
            require(0 <= p <= 1 and abs(p - count / n) <= 1e-12,
                    "probability must divide counts by all selected trials")
    return keyed


def compare(reference, submission):
    expected = index_trials(reference["trials"])
    validate_submission(reference, expected)
    actual = validate_submission(submission, expected)
    condition_errors = sum(actual[k]["condition"] != r["condition"] for k, r in expected.items())
    selection_errors = sum(bool(actual[k]["selected"]) != bool(r["selected"]) for k, r in expected.items())
    differences = [actual[k]["contact_seconds"] - r["contact_seconds"] for k, r in expected.items()
                   if r["selected"] and actual[k]["selected"]]
    count_errors = []
    probability_errors = []
    for group in ("control", "opto"):
        a, b = submission["histograms"][group], reference["histograms"][group]
        count_errors.extend(abs(x - y) for x, y in zip(a["counts"], b["counts"]))
        probability_errors.extend(x - y for x, y in zip(a["probability"], b["probability"]))
    return dict(task_id=TASK, component=COMPONENT, admissible=True, complete_trials=len(expected),
                condition_mismatches=condition_errors, selection_mismatches=selection_errors,
                contact_compared_trials=len(differences),
                contact_rmse_seconds=math.sqrt(sum(x*x for x in differences)/len(differences)) if differences else None,
                histogram_count_l1=sum(count_errors),
                histogram_probability_rmse=math.sqrt(sum(x*x for x in probability_errors)/58),
                scientifically_qualified=False, full_contract_complete=False,
                article_quantitative_reproduction="unresolved_cue_origin_and_article_percentage_reconciliation",
                time_origin_validated=False,
                interpretation="Continuous release-native reconstruction diagnostics; no scientific pass threshold or causal inference")


def verify_independent(reference, independent):
    """Compare separately implemented reviewer output before reference release."""
    require(independent["schema"] == "independent-opto-native-reference-v1", "independent reference schema")
    require(independent["task_id"] == TASK and independent["input_sha256"] == DATA_SHA, "independent input/task mismatch")
    require(independent["official_code_revision"] == REVISION, "independent source mismatch")
    keyed = index_trials(reference["trials"])
    validate_submission(reference, keyed)
    reviewed = index_trials(independent["trial_outputs"])
    require(set(keyed) == set(reviewed), "independent per-trial coverage mismatch")
    for key, row in keyed.items():
        other = reviewed[key]
        require(other["condition"] == row["condition"] and
                binary(other["selected"], "independent selected") == row["selected"],
                "independent per-trial condition/selection mismatch")
        if row["selected"]:
            require(abs(finite(other["contact_seconds"], "independent contact") - row["contact_seconds"]) <= 1e-12,
                    "independent contact mismatch")
        else:
            require(other["contact_seconds"] is None, "independent excluded contact must be null")
    require(len(independent["unique_keys"]) == len(keyed) == independent["record_count"], "independent roster length")
    require({tuple(k) for k in independent["unique_keys"]} == set(keyed), "independent roster mismatch")
    for value, group in (("0", "control"), ("1", "opto")):
        expected = {k for k, r in keyed.items() if r["selected"] and r["condition"] == group}
        keys = independent["selected_trial_keys"][value]
        require(len(keys) == len(expected) and {tuple(k) for k in keys} == expected, "independent selection mismatch")
        a, b = reference["histograms"][group], independent["histograms"][group]
        for field in ("selected_trials", "counts", "outside_display_window"):
            require(a[field] == b[field], f"independent {group}/{field} mismatch")
        require(len(b["probability"]) == 29, "independent probability length")
        require(all(abs(x-finite(y, "independent probability")) <= 1e-12 for x,y in zip(a["probability"], b["probability"])),
                "independent probability mismatch")
    excluded = {k for k,r in keyed.items() if not r["selected"]}
    require(len(independent["excluded_trial_keys"]) == len(excluded) and
            {tuple(k) for k in independent["excluded_trial_keys"]} == excluded, "independent exclusion mismatch")
    require(len(independent["source_histogram_edges_seconds"]) == 30 and
            all(abs(x-finite(y, "independent edge")) <= 1e-12 for x,y in zip(EDGES, independent["source_histogram_edges_seconds"])),
            "independent bin mismatch")
