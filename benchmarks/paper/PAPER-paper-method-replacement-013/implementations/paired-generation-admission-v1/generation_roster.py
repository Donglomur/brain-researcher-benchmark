"""Operator-only complete-roster admission for source-token diagnostics.

This composes the unchanged Neuroformer source metric path; it does not select
Figure 6's metric, authenticate an author run, or activate a benchmark runtime.
No numerical dependency or private target is imported at module import time.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import math
import numbers
from pathlib import Path
import struct
from types import ModuleType

BEHAVIOR_PIN = (12875, "0dd548d558825fb08095cdaee400da5729c2bead808c4c59e7100f838cc526e6")
BEHAVIOR_PATH = Path(__file__).resolve().parents[1] / "native-behavior-truth-v1" / "behavior_truth.py"
SCHEMA = "neuroformer_generation_roster_v1"
BRANCHES = ("compute_scores", "compute_scores_scikit")
METRICS = ("precision", "recall", "F1")
ARMS = ("paper_data", "paper_data_author_code")
ROLES = ("source_reference", "candidate")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


@contextlib.contextmanager
def source_context():
    """Reuse the source-pinned predecessor's private-namespace loader."""
    with BEHAVIOR_PATH.open("rb") as handle:
        body = handle.read(BEHAVIOR_PIN[0] + 1)
    require((len(body), digest(body)) == BEHAVIOR_PIN, "behavior source dependency changed")
    module = ModuleType("_neuroformer_roster_dependency")
    module.__file__ = str(BEHAVIOR_PATH)
    exec(compile(body, str(BEHAVIOR_PATH), "exec"), module.__dict__)
    with module.sources() as loaded:
        yield loaded


def _identity(value, label):
    require(type(value) is str and bool(value.strip()), label + " identity")


def _pin(value, native):
    require(type(value) is dict and set(value) == {"path", "bytes", "sha256"}, "source/study descriptor")
    native.relative(value["path"])
    native.integer(value["bytes"], "descriptor extent")
    h = value["sha256"]
    require(type(h) is str and len(h) == 64 and set(h) <= set("0123456789abcdef"), "descriptor digest")


def _float32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def _admit_study(study, loaded):
    native = loaded.modules["native_dataset"]
    composition = loaded.modules["run_composition"]
    require(type(study) is dict and set(study) == {"schema", "study_identity", "runs", "pairs", "limits"},
            "closed generation-roster study")
    require(study["schema"] == SCHEMA, "generation-roster schema")
    _pin(study["study_identity"], native)
    limits = study["limits"]
    names = {"max_runs", "max_support_rows", "max_windows", "max_prediction_events", "max_truth_events"}
    require(type(limits) is dict and set(limits) == names, "all aggregate bounds required")
    for name, value in limits.items():
        native.integer(value, name)
    runs = study["runs"]
    require(type(runs) is list and 0 < len(runs) <= limits["max_runs"], "complete bounded run roster")
    cases = {case["id"]: case for case in json.loads(loaded.bodies["source/public/PANEL.json"])["cases"]}
    admitted = {}
    support_rows = window_count = 0
    for run in runs:
        require(type(run) is dict and set(run) == {"run_id", "case_id", "condition", "arm", "role", "seed", "source_run", "support"},
                "exact run fields")
        _identity(run["run_id"], "run")
        require(run["run_id"] not in admitted, "duplicate run")
        case = cases.get(run["case_id"])
        require(case is not None and case["kind"] == "counts" and case["family"] == "neural_ablation",
                "original neural-cell inventory only; no 5 ms substitution")
        # Historical neural generation uses a finetune prefix, unlike behavior's
        # selection=evaluation test support. Do not impose that behavior rule on
        # an unbound original neural experiment or silently repair its protocol.
        require(run["condition"] == composition.PROTECTED,
                "protected source-amended condition only; historical neural support remains unbound")
        require(run["arm"] in ARMS and run["role"] in ROLES, "explicit information arm and method role")
        require(type(run["seed"]) is int and 0 <= run["seed"] < 2**32, "explicit seed")
        _pin(run["source_run"], native)
        support = run["support"]
        require(type(support) is dict and set(support) == {"train", "selection", "evaluation"} and
                all(type(rows) is list for rows in support.values()), "all full support roles")
        support_rows += sum(len(rows) for rows in support.values())
        require(support_rows <= limits["max_support_rows"], "aggregate support capacity")
        composition.admit_support(support, run["condition"])
        recordings = {row["recording"] for rows in support.values() for row in rows}
        require(len(recordings) == 1, "original Trial0 ABI requires one recording per run")
        windows = tuple((_float32(row["end_tick"] * .01), 0) for row in support["evaluation"])
        require(len(set(windows)) == len(windows), "float32 interval collision")
        window_count += len(windows)
        require(window_count <= limits["max_windows"], "aggregate window capacity")
        admitted[run["run_id"]] = {"run": run, "windows": windows,
            "population": {"lateral": 2022, "medial": 1905}[case["cohort"]],
            "support_sha256": digest(canonical(support))}
    pairs = study["pairs"]
    require(type(pairs) is list and len(pairs) * 2 == len(runs), "every selected run needs one declared pair")
    pair_ids, used = set(), set()
    for pair in pairs:
        require(type(pair) is dict and set(pair) == {"pair_id", "source_reference", "candidate"}, "pair fields")
        _identity(pair["pair_id"], "pair")
        require(pair["pair_id"] not in pair_ids, "duplicate pair identity")
        pair_ids.add(pair["pair_id"])
        ids = (pair["source_reference"], pair["candidate"])
        require(all(type(i) is str and i in admitted and i not in used for i in ids) and ids[0] != ids[1],
                "complete unique reference/candidate pairing")
        reference, candidate = (admitted[i]["run"] for i in ids)
        require(reference["role"] == "source_reference" and candidate["role"] == "candidate", "pair roles")
        for key in ("case_id", "condition", "arm", "seed", "support"):
            require(reference[key] == candidate[key], "paired " + key + " mismatch")
        used.update(ids)
    require(used == set(admitted), "orphan selected run")
    return admitted


def _original_analysis(loaded):
    index = json.loads(loaded.bodies["source/operator/CODE_INDEX.json"])
    rows = [row for row in index["files"] if row["path"] == "neuroformer/analysis.py"]
    require(len(rows) == 1, "unique original analysis source")
    row = rows[0]
    body = loaded.bodies["source/public/official_code/" + row["path"]]
    if "public_distribution" in row:
        prefix = row["public_distribution"]["notice_prefix"].encode()
        require(body.startswith(prefix), "analysis notice prefix")
        body = body[len(prefix):]
    require((len(body), digest(body)) == (row["bytes"], row["sha256"]), "original analysis identity")
    return {row["path"]: body}


def _freeze_truth(windows, expected, population, remaining):
    require(type(windows) is tuple and len(windows) == len(expected), "full independently issued window count")
    frozen, count = [], 0
    for window, identity in zip(windows, expected):
        require(type(window) is dict and set(window) == {"interval", "trial", "ids"}, "truth window fields")
        require(type(window["interval"]) in (int, float) and math.isfinite(window["interval"]) and
                type(window["trial"]) is int and (window["interval"], window["trial"]) == identity,
                "exact ordered independently issued windows")
        ids = window["ids"]
        require(type(ids) is tuple, "immutable truth ID sequence")
        count += len(ids)
        require(count <= remaining, "aggregate truth event capacity")
        require(all(type(i) is int and 0 <= i < population for i in ids), "truth ID outside source population")
        frozen.append({"interval": identity[0], "trial": identity[1], "ids": tuple(ids)})
    return tuple(frozen), count


def _reported_branches(report):
    branches = report["branches"]
    require(type(branches) is dict and set(branches) == set(BRANCHES), "both original metric branches required")
    result = {}
    for name in BRANCHES:
        values = branches[name]
        require(type(values) is dict and set(values) in (set(), set(METRICS)), "original branch keys")
        result[name] = {}
        for key, value in values.items():
            require(isinstance(value, numbers.Real) and not isinstance(value, bool), "numerical source metric")
            result[name][key] = float(value) if math.isfinite(float(value)) else None
    return result


def assess(packets, study, truth_loader, runtime_factory):
    """Freeze ALL runs, bind complete truth, then compute unchanged diagnostics.

    All arguments except detached prediction packets are trusted evaluator
    inputs. Callbacks and descriptor equality do not establish physical isolation,
    actual source provenance, independent truth, competent baselines or paper parity.
    """
    study = copy.deepcopy(study)
    with source_context() as loaded:
        admitted = _admit_study(study, loaded)
        metrics = loaded.modules["run_metrics"]
        limits = study["limits"]
        require(type(packets) is list and len(packets) == len(admitted), "complete selected prediction roster")
        frozen, total = {}, 0
        for packet, run in zip(packets, study["runs"]):
            require(type(packet) is dict and set(packet) == {"run_id", "prediction"} and packet["run_id"] == run["run_id"],
                    "exact ordered prediction run identities")
            prediction = packet["prediction"]
            require(type(prediction) is dict, "detached prediction mapping")
            events = metrics.freeze_generation(prediction, max_events=limits["max_prediction_events"])
            total += len(events)
            require(total <= limits["max_prediction_events"], "aggregate prediction event capacity")
            bound = admitted[run["run_id"]]
            windows = set(bound["windows"])
            require(all(i < bound["population"] and (interval, trial) in windows for i, dt, trial, interval in events),
                    "prediction outside source population or declared window support")
            frozen[run["run_id"]] = events
        # No target-loader or numerical-runtime callback can occur above here.
        truth, total_truth = {}, 0
        for run in study["runs"]:
            bound = admitted[run["run_id"]]
            windows, count = _freeze_truth(truth_loader(copy.deepcopy(run)), bound["windows"], bound["population"],
                limits["max_truth_events"] - total_truth)
            truth[run["run_id"]] = windows
            total_truth += count
        for pair in study["pairs"]:
            require(truth[pair["source_reference"]] == truth[pair["candidate"]], "paired private truth mismatch")
        runtime = runtime_factory()
        bodies = _original_analysis(loaded)
        reports = {}
        for run in study["runs"]:
            run_id = run["run_id"]
            events = frozen[run_id]
            prediction = {key: tuple(event[i] for event in events) for i, key in enumerate(("ID", "dt", "Trial", "Interval"))}
            report = metrics.grade_generation(prediction, lambda rid=run_id: truth[rid], bodies, runtime,
                max_events=max(limits["max_truth_events"], limits["max_prediction_events"]),
                max_windows=limits["max_windows"])
            report["branches"] = _reported_branches(report)
            reports[run_id] = {"run_id": run_id, "case_id": run["case_id"], "condition": run["condition"],
                "arm": run["arm"], "role": run["role"], "seed": run["seed"],
                "support_sha256": admitted[run_id]["support_sha256"], "source_run": run["source_run"],
                "diagnostics": report}
        comparisons = []
        for pair in study["pairs"]:
            left = reports[pair["source_reference"]]["diagnostics"]["branches"]
            right = reports[pair["candidate"]]["diagnostics"]["branches"]
            deltas = {}
            for branch in BRANCHES:
                deltas[branch] = {}
                for metric in METRICS:
                    a, b = left[branch].get(metric), right[branch].get(metric)
                    deltas[branch][metric] = b - a if a is not None and b is not None else None
            comparisons.append({**pair, "candidate_minus_reference": deltas,
                "paired_truth_equal": True, "paper_win": None, "scientifically_qualified": False})
        return {"schema": "neuroformer_generation_roster_report_v1", "study_sha256": digest(canonical(study)),
            "study_identity": study["study_identity"], "runs": [reports[run["run_id"]] for run in study["runs"]],
            "comparisons": comparisons, "all_predictions_admitted_before_targets_and_runtime": True,
            "full_declared_window_support_checked": True, "true_event_values_returned": False,
            "selected_paper_figure6_metric": None, "physical_isolation_qualified": False,
            "source_study_authenticated": False, "source_complete": False, "scientifically_qualified": False,
            "paper_result_reproduced": False, "paper_win": None}
