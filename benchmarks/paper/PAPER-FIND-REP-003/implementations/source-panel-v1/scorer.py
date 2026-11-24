"""Original Figure 5 fold/joint panel, with a matched author prediction comparator.

No neural fitting, data loading, RNG emulation, native-source qualification or
scientific victory decision is performed. Operator reference contents are private.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median

TASK = "PAPER-FIND-REP-003"
REVISION = "815b610b3beddfed5a3abf611d3a465ab9e4ce5c"
SCHEMA = "fig5-source-panel/v1"
MICE = ("cfa17", "cfa19", "cfa20", "cfa22", "cfa24")
SESSIONS = {
    ("cfa17", "200825"): "M1", ("cfa17", "200827"): "S1",
    ("cfa19", "200820"): "M1", ("cfa19", "200826"): "S1",
    ("cfa20", "201114"): "M1", ("cfa20", "201118"): "S1",
    ("cfa22", "220605"): "M1", ("cfa22", "220611"): "S1",
    ("cfa24", "220727"): "M1", ("cfa24", "220724"): "S1",
}
JOINTS = ["SHDRf", "SHDRa", "SHDRr", "ELBOf", "WRSTf", "WRSTd", "WRSTr",
          "MCP1f", "MCP2f", "MCP3f", "MCP4f", "MCP1a", "MCP2a", "MCP3a",
          "MCP4a", "MCP1o", "MCP4o", "P1P2", "P2P3", "P3P4", "PIP1f",
          "PIP2f", "PIP3f", "PIP4f"]
TIME_MS = list(range(-100, 401, 10))


class PanelError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PanelError(message)


def exact_fields(value, fields, name):
    require(type(value) is dict and set(value) == set(fields), f"{name}: exact fields {fields} required")


def positive_integer(value, name):
    require(type(value) is int and value > 0, f"{name}: positive integer required")
    return value


def finite(value):
    require(type(value) in (int, float) and math.isfinite(value), "finite numeric values required")
    return float(value)


def matrix(value, rows, name):
    require(type(value) is list and len(value) == rows, f"{name}: {rows} time rows required")
    for row in value:
        require(type(row) is list and len(row) == 24, f"{name}: 24 ordered joints required")
        for item in row:
            finite(item)
    return value


def unique(records, key, name):
    require(type(records) is list, f"{name}: list required")
    out = {}
    for record in records:
        require(type(record) is dict, f"{name}: objects required")
        identity = key(record)
        require(identity not in out, f"{name}: duplicate identity {identity}")
        out[identity] = record
    return out


def trial_ids(values):
    require(type(values) is list and values, "nonempty trial-number list required")
    for value in values:
        positive_integer(value, "trial number")
    require(len(values) == len(set(values)), "duplicate trial number")
    return values


def source_ve(actual, predicted):
    """MATLAB 1-var(error,[],1)/var(target,[],1), over concatenated timepoints.

    Both sample variances have the same n-1 denominator, which cancels. Constant
    target channels are rejected instead of omitting a joint or inventing zero.
    """
    require(len(actual) == len(predicted) and len(actual) >= 2, "VE row mismatch")
    result = []
    for joint in range(24):
        y = [finite(row[joint]) for row in actual]
        residual = [a - finite(row[joint]) for a, row in zip(y, predicted)]
        ym = math.fsum(y) / len(y)
        rm = math.fsum(residual) / len(y)
        denom = math.fsum((a - ym) ** 2 for a in y)
        numerator = math.fsum((e - rm) ** 2 for e in residual)
        require(math.isfinite(denom) and denom > 0, "constant or overflow target: original VE undefined")
        score = 1 - numerator / denom
        require(math.isfinite(score), "nonfinite VE")
        result.append(score)
    return result


def source_summary(panel):
    """plotVEAll: median over models per joint, then median over joint groups."""
    require(len(panel) == 50 and all(len(row) == 24 for row in panel), "50 by 24 VE panel required")
    for row in panel:
        for value in row:
            finite(value)
    joint_medians = [median(row[j] for row in panel) for j in range(24)]
    return {"joint_median_ve": joint_medians,
            "proximal_median_ve": median(joint_medians[:7]),
            "distal_median_ve": median(joint_medians[7:])}


def validate_models(models, ordered_trials):
    """Admit recorded source folds; do not regenerate MATLAB's global RNG stream.

    cvRegress assigns permutation VALUES modulo ten to POSITIONS in trial order.
    Within each repeated ten-fold block test sets must partition all trials;
    model 10 holds out residue zero, whose size is floor(n/10), not the first
    larger group. train/test order is the source find() order.
    """
    keyed = unique(models, lambda x: positive_integer(x["model"], "model"), "models")
    require(set(keyed) == set(range(1, 51)), "exactly source models 1..50 required")
    population = set(ordered_trials)
    n = len(ordered_trials)
    require(n >= 10, "at least ten eligible source trials required")
    for repetition in range(5):
        seen = []
        for offset in range(1, 11):
            model = keyed[repetition * 10 + offset]
            train = trial_ids(model["train_trials"])
            test = trial_ids(model["test_trials"])
            train_set, test_set = set(train), set(test)
            require(train_set.isdisjoint(test_set) and train_set | test_set == population,
                    "each model must partition the complete eligible trial population")
            require(train == [t for t in ordered_trials if t in train_set] and
                    test == [t for t in ordered_trials if t in test_set],
                    "source find() trial ordering required")
            residue = offset % 10
            expected_size = sum(i % 10 == residue for i in range(1, n + 1))
            require(len(test) == expected_size, "source model-specific modulo holdout size mismatch")
            seen.extend(test)
        require(len(seen) == n and set(seen) == population,
                "every trial must be held out once in each source repetition")
    return keyed


def header(value, role):
    exact_fields(value, ["schema", "task_id", "source_revision", "role", "joint_names", "angle_units", "time_ms", "sessions"], role)
    require(value["schema"] == SCHEMA and value["task_id"] == TASK, "wrong schema or task")
    require(value["source_revision"] == REVISION and value["role"] == role, "wrong source revision or role")
    require(value["joint_names"] == JOINTS and value["time_ms"] == TIME_MS, "exact source joints and time grid required")
    require(value["angle_units"] == "degrees", "source joint-angle units must be degrees")
    keyed = unique(value["sessions"], lambda x: (x["mouse"], x["session"]), "sessions")
    require(set(keyed) == set(SESSIONS), "all ten original imaging sessions required")
    return keyed


def evaluate(reference, candidate):
    refs = header(reference, "operator_author_reference")
    candidates = header(candidate, "candidate_predictions")
    reports = []
    effects = {}
    for identity, area in SESSIONS.items():
        ref, pred = refs[identity], candidates[identity]
        exact_fields(ref, ["mouse", "session", "area", "trials", "models"], "reference session")
        exact_fields(pred, ["mouse", "session", "area", "models"], "candidate session")
        require(ref["area"] == area and pred["area"] == area, "original mouse/session/area assignment required")
        trials = unique(ref["trials"], lambda x: positive_integer(x["trial_number"], "trial number"), "trials")
        for trial in trials.values():
            exact_fields(trial, ["trial_number", "joint_angles"], "trial")
            matrix(trial["joint_angles"], 51, "target")
        models = validate_models(ref["models"], list(trials))
        candidate_models = unique(pred["models"], lambda x: positive_integer(x["model"], "model"), "candidate models")
        require(set(candidate_models) == set(models), "all 50 matched candidate models required")
        author_panel, candidate_panel, delta_panel, fold_reports = [], [], [], []
        for model in range(1, 51):
            item, submitted = models[model], candidate_models[model]
            exact_fields(item, ["model", "train_trials", "test_trials", "author_prediction", "author_ve"], "reference model")
            exact_fields(submitted, ["model", "test_trials", "joint_angles"], "candidate model")
            trial_ids(submitted["test_trials"])
            require(submitted["test_trials"] == item["test_trials"], "candidate heldout identity/order mismatch")
            actual = [row for t in item["test_trials"] for row in trials[t]["joint_angles"]]
            author = matrix(item["author_prediction"], len(actual), "author prediction")
            candidate_values = matrix(submitted["joint_angles"], len(actual), "candidate prediction")
            av, cv = source_ve(actual, author), source_ve(actual, candidate_values)
            require(type(item["author_ve"]) is list and len(item["author_ve"]) == 24, "24 saved author VEs required")
            for calculated, saved in zip(av, item["author_ve"]):
                require(math.isclose(calculated, finite(saved), rel_tol=1e-10, abs_tol=1e-10),
                        "author predictions fail saved source VE parity")
            delta = [c - a for c, a in zip(cv, av)]
            author_panel.append(av)
            candidate_panel.append(cv)
            delta_panel.append(delta)
            # Model membership belongs in protected reference, not public reports.
            fold_reports.append({"model": model, "n_test_trials": len(item["test_trials"])})
        a, c = source_summary(author_panel), source_summary(candidate_panel)
        group_delta = {group: c[group] - a[group] for group in ("proximal_median_ve", "distal_median_ve")}
        effects[(identity[0], area)] = group_delta
        reports.append({"mouse": identity[0], "session": identity[1], "area": area,
                        "n_eligible_trials": len(trials), "models": fold_reports,
                        "author_ve": author_panel, "candidate_ve": candidate_panel,
                        "candidate_minus_author_ve": delta_panel,
                        "author_summary": a, "candidate_summary": c,
                        "candidate_minus_author_summary": group_delta})
    paired = [{"mouse": mouse,
               **{area: effects[(mouse, area)] for area in ("M1", "S1")}} for mouse in MICE]
    return {"schema": SCHEMA, "task_id": TASK, "component": "source_figure5_panel",
            "source_revision": REVISION, "sessions": reports, "paired_mouse_effects": paired,
            "reduction": "median over 50 models per joint; median of joints 1:7 or 8:24 per mouse and area",
            "comparison": "candidate source summary minus matched author source summary; not median of paired deltas",
            "scientifically_qualified": False, "source_author_run_qualified": False,
            "published_numeric_baseline_recovered": False, "paper_win": None,
            "limits": ["Operator reference hash binds bytes, not source provenance or original-fold authenticity",
                       "Native preparation, author run, PCA/ROI/RADICaL parity and exporter remain unqualified",
                       "No published numeric gold, minimum meaningful effect or uncertainty decision is supplied",
                       "Five paired mice are independent units; 50 fits and 24 joints are not independent animals"]}


def read_json_bytes(body):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def bad_constant(value):
        raise PanelError(f"nonfinite JSON constant: {value}")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad_constant)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--reference-sha256", required=True, help="independently frozen operator reference hash")
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--candidate-sha256", required=True, help="independently frozen candidate prediction hash")
    parser.add_argument("--output", type=Path, required=True, help="private, previously nonexistent report")
    args = parser.parse_args(argv)
    reference_bytes, candidate_bytes = args.reference.read_bytes(), args.candidate.read_bytes()
    reference_sha = hashlib.sha256(reference_bytes).hexdigest()
    require(reference_sha == args.reference_sha256, "operator reference hash mismatch")
    candidate_sha = hashlib.sha256(candidate_bytes).hexdigest()
    require(candidate_sha == args.candidate_sha256, "frozen candidate hash mismatch")
    report = evaluate(read_json_bytes(reference_bytes), read_json_bytes(candidate_bytes))
    report["reference_sha256"] = reference_sha
    report["candidate_sha256"] = candidate_sha
    with args.output.open("x") as output:
        json.dump(report, output, indent=2, allow_nan=False)
        output.write("\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PanelError, KeyError, TypeError, OverflowError, OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"inadmissible: {error}")
