"""NEURAL-068 source-bound layout and paired session scorer; no fitting/imports of data."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

VERSION = "neural068-paired-session-v1"
ARMS = ("neural_clock", "clock_only")
BUDGETS = (0, 5, 10)
# Official H1_NEW_TO_OLD at 770c9b9597b8f58bf67b5a9ec6401ef705a2cb0f.
RUNS = (
    ("19250126T113454", "S6_set_1"), ("19250126T114029", "S6_set_2"),
    ("19250127T120333", "S7_set_1"), ("19250127T120826", "S7_set_2"),
    ("19250129T112555", "S8_set_1"), ("19250129T113059", "S8_set_2"),
    ("19250202T113958", "S9_set_1"), ("19250202T114452", "S9_set_2"),
    ("19250203T113515", "S10_set_1"), ("19250203T114018", "S10_set_2"),
    ("19250206T112219", "S11_set_1"), ("19250206T112712", "S11_set_2"),
    ("19250209T111826", "S12_set_1"), ("19250209T112327", "S12_set_2"),
)
SESSIONS = tuple(f"S{i}" for i in range(6, 13))


class ContractError(ValueError):
    """A malformed input or numerically undefined computation cannot be scored."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def exact(value, keys, label):
    require(type(value) is dict and set(value) == set(keys), f"{label}: exact keys required")


def number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def finite_sum(values):
    try:
        result = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        raise ContractError("Nonfinite numeric aggregate") from exc
    require(math.isfinite(result), "Nonfinite numeric aggregate")
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def sha256(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def context_id(run, arm, budget):
    return f"{run}__{arm}__{budget}"


def make_layout(source_metadata):
    """Prepare identity/mask layout from complete source metadata, never target values.

    Requires exact 20-ms zero-origin clock and three source TrialNum segments,
    preserving the recovered first-prefix/third-segment protocol. Native loading,
    source SHA verification and calibration label staging are the operator's job.
    """
    require(type(source_metadata) is list and len(source_metadata) == 14, "Complete fourteen-run metadata")
    rows = []
    for source, (run, dataset) in zip(source_metadata, RUNS):
        exact(source, ("run", "source_sha256", "time_s", "trial", "eval_mask"), "Source metadata")
        require(source["run"] == run and sha256(source["source_sha256"]), "Source order/identity")
        time, trial, mask = (source[k] for k in ("time_s", "trial", "eval_mask"))
        require(all(type(v) is list for v in (time, trial, mask)), "Native metadata lists")
        require(len(time) == len(trial) == len(mask) and len(time) >= 502, "Aligned metadata length")
        require(all(number(t) and abs(t - i * .02) <= 1e-10 for i, t in enumerate(time)),
                "Verified zero-origin 20-ms clock required")
        require(all(number(t) and t == math.floor(t) for t in trial), "Integer TrialNum")
        require(all(b >= a for a, b in zip(trial, trial[1:])), "Monotonic TrialNum")
        require(all(type(m) is bool for m in mask), "Strict Boolean source mask")
        starts = [0] + [i for i in range(1, len(trial)) if trial[i] != trial[i - 1]]
        require(len(starts) == 3 and starts[1] >= 500, "Three segments and full 10-second first prefix")
        start, stop = starts[2], len(time)
        # Target construction has 12 past and 13 future bins of support.
        guard = (time[start] - 12 * .02) - (time[499] + 13 * .02)
        require(guard >= 1., "One-second separation of full target receptive fields")
        require(sum(mask[start:stop]) >= 2, "At least two scored rows per run")
        require(all(sum(mask[:b * 50]) >= 2 for b in (5, 10)), "Nonempty fixed calibration prefixes")
        rows.append({"run": run, "dataset": dataset, "session": dataset.split("_")[0],
                     "source_sha256": source["source_sha256"],
                     "query_start_bin": start, "query_stop_bin": stop,
                     "row_ids": [f"{run}:{i}" for i in range(start, stop)],
                     "eval_mask": mask[start:stop],
                     "calibration_labeled_rows": {str(b): sum(mask[:b * 50]) for b in BUDGETS}})
    body = {"schema": VERSION, "runs": rows}
    return {**body, "packet_id": digest(body)}


def validate_layout(layout):
    exact(layout, ("schema", "runs", "packet_id"), "Layout")
    require(layout["schema"] == VERSION and type(layout["runs"]) is list and len(layout["runs"]) == 14,
            "Complete layout")
    require(layout["packet_id"] == digest({k: layout[k] for k in ("schema", "runs")}), "Layout digest")
    for row, (run, dataset) in zip(layout["runs"], RUNS):
        exact(row, ("run", "dataset", "session", "source_sha256", "query_start_bin", "query_stop_bin",
                    "row_ids", "eval_mask", "calibration_labeled_rows"), "Run layout")
        require((row["run"], row["dataset"], row["session"]) == (run, dataset, dataset.split("_")[0]),
                "Exact official run/set/session join")
        require(sha256(row["source_sha256"]), "Source SHA256")
        start, stop = row["query_start_bin"], row["query_stop_bin"]
        require(type(start) is int and type(stop) is int and 574 <= start < stop, "Guarded query suffix")
        require(row["row_ids"] == [f"{run}:{i}" for i in range(start, stop)], "Exact ordered native row IDs")
        mask = row["eval_mask"]
        require(type(mask) is list and len(mask) == stop - start and all(type(m) is bool for m in mask)
                and sum(mask) >= 2, "Complete Boolean query mask")
        counts = row["calibration_labeled_rows"]
        exact(counts, ("0", "5", "10"), "Prefix counts")
        require(all(type(counts[str(b)]) is int for b in BUDGETS) and counts["0"] == 0
                and 2 <= counts["5"] <= 250 and counts["5"] <= counts["10"] <= 500, "Prefix support")


def matrix(values, length, label):
    require(type(values) is list and len(values) == length, f"{label}: full query rows required")
    require(all(type(row) is list and len(row) == 7 and all(number(x) for x in row) for row in values),
            f"{label}: seven finite nonboolean outputs required")


def validate_submission(layout, submission):
    """Validate all 84 contexts before any evaluator target callback can run."""
    validate_layout(layout)
    exact(submission, ("schema", "packet_id", "contexts"), "Submission")
    require(submission["schema"] == VERSION and submission["packet_id"] == layout["packet_id"], "Packet binding")
    contexts = submission["contexts"]
    expected = {context_id(run, arm, b) for run, _ in RUNS for arm in ARMS for b in BUDGETS}
    require(type(contexts) is dict and set(contexts) == expected, "Exact complete 84 contexts")
    for row in layout["runs"]:
        for arm in ARMS:
            for budget in BUDGETS:
                value = contexts[context_id(row["run"], arm, budget)]
                exact(value, ("row_ids", "predictions"), "Context")
                require(value["row_ids"] == row["row_ids"], "Exact ordered same-suffix row IDs")
                matrix(value["predictions"], len(row["row_ids"]), "Predictions")
    return contexts


def variance_weighted_r2(target, prediction):
    """Official variance weighting for nonconstant outputs; explicit constant diagnostics.

    Zero-variance channels have zero weight. All-constant targets are undefined,
    overriding sklearn's finite fallback as required by this task's contract.
    """
    require(len(target) >= 2, "At least two scored rows")
    matrix(target, len(target), "Targets")
    matrix(prediction, len(target), "Predictions")
    sse, sst, constants, per_channel = [], [], [], []
    for j in range(7):
        column = [float(row[j]) for row in target]
        constant = all(x == column[0] for x in column)
        mean = column[0] if constant else finite_sum(x / len(column) for x in column)
        try:
            error = finite_sum((x - float(p[j])) ** 2 for x, p in zip(column, prediction))
            variance = 0. if constant else finite_sum((x - mean) ** 2 for x in column)
        except OverflowError as exc:
            raise ContractError("Squared-error overflow") from exc
        require(constant or variance > 0, "Nonconstant target variance underflow")
        value = None if constant else 1. - error / variance
        require(value is None or math.isfinite(value), "R2 overflow")
        sse.append(error)
        sst.append(variance)
        constants.append(constant)
        per_channel.append(value)
    total = finite_sum(sst)
    score = None if total == 0 else 1. - finite_sum(e for e, c in zip(sse, constants) if not c) / total
    require(score is None or math.isfinite(score), "R2 overflow")
    return {"r2": score, "scored_rows": len(target), "sse": sse, "sst": sst,
            "constant_channels": constants, "per_channel_r2": per_channel}


def score(layout, submission, target_loader):
    """Recompute budget-wise gains relative to each arm's frozen 0-second decoder.

    target_loader(run) returns full-query {row_ids, targets}; not a participant API.
    Operator provenance must establish that 0-second predictions come from the
    unchanged decoder and that all recipes were frozen before query access.
    """
    contexts = validate_submission(layout, submission)
    grouped = {session: {"targets": [], "predictions": {a: {str(b): [] for b in BUDGETS} for a in ARMS},
                         "runs": []} for session in SESSIONS}
    for row in layout["runs"]:
        gold = target_loader(row["run"])
        exact(gold, ("row_ids", "targets"), "Evaluator targets")
        require(gold["row_ids"] == row["row_ids"], "Exact evaluator target row order")
        matrix(gold["targets"], len(row["row_ids"]), "Targets")
        selected = [i for i, take in enumerate(row["eval_mask"]) if take]
        group = grouped[row["session"]]
        group["runs"].append({"run": row["run"], "full_rows": len(row["row_ids"]), "scored_rows": len(selected),
                              "calibration_labeled_rows": row["calibration_labeled_rows"]})
        group["targets"].extend(gold["targets"][i] for i in selected)
        for arm in ARMS:
            for budget in BUDGETS:
                values = contexts[context_id(row["run"], arm, budget)]["predictions"]
                group["predictions"][arm][str(budget)].extend(values[i] for i in selected)
    sessions = []
    for session, group in grouped.items():
        metrics = {a: {str(b): variance_weighted_r2(group["targets"], group["predictions"][a][str(b)])
                       for b in BUDGETS} for a in ARMS}
        sessions.append({"session": session, "runs": group["runs"], "metrics": metrics})
    undefined = [r["session"] for r in sessions if r["metrics"][ARMS[0]]["0"]["r2"] is None]
    result = {"schema": VERSION, "packet_id": layout["packet_id"], "by_session": sessions,
              "biological_participants": 1, "sessions": 7, "contexts": 84,
              "full_rows": sum(len(r["row_ids"]) for r in layout["runs"]),
              "scored_rows": sum(sum(r["eval_mask"]) for r in layout["runs"]),
              "constant_target_sessions": undefined,
              "primary_name": "equal_session_paired_variance_weighted_r2_gain_by_budget"}
    if undefined:
        return {**result, "status": "undefined_constant_target_session", "primary": None,
                "absolute_curves": None, "paired_gains": None, "neural_minus_clock": None,
                "neural_minus_clock_recalibration_gain": None}
    def mean(values):
        return finite_sum(x / len(sessions) for x in values)
    curves = {a: {str(b): mean([r["metrics"][a][str(b)]["r2"] for r in sessions]) for b in BUDGETS} for a in ARMS}
    gains = {a: {str(b): mean([r["metrics"][a][str(b)]["r2"] - r["metrics"][a]["0"]["r2"]
                               for r in sessions]) for b in BUDGETS} for a in ARMS}
    contrast = {str(b): finite_sum((curves[ARMS[0]][str(b)], -curves[ARMS[1]][str(b)])) for b in BUDGETS}
    adjusted = {str(b): finite_sum((gains[ARMS[0]][str(b)], -gains[ARMS[1]][str(b)])) for b in BUDGETS}
    return {**result, "status": "scored", "primary": gains["neural_clock"], "absolute_curves": curves,
            "paired_gains": gains, "neural_minus_clock": contrast,
            "neural_minus_clock_recalibration_gain": adjusted}


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    with Path(path).open() as handle:
        return json.load(handle, object_pairs_hook=unique)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", required=True)
    parser.add_argument("--submission", required=True)
    parser.add_argument("--targets", required=True, help="Operator-only JSON keyed by all fourteen run IDs")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    layout, submission = read_json(args.layout), read_json(args.submission)
    validate_submission(layout, submission)  # Reject submissions before opening targets.
    targets = read_json(args.targets)
    exact(targets, (r for r, _ in RUNS), "Target roster")
    result = score(layout, submission, targets.__getitem__)
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
