"""Complete-support evaluator for NEURAL-036's current released-proxy contract.

Operator-only: never mount support, targets, or reports into a candidate process.
Pure Python; no authentic targets, model execution, or source loading at import.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import stat


TASK = "NEURAL-036"
ARMS = ("joint", "history", "reverse", "shift")
FOLDS = tuple(map(str, range(7)))
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
PRIMARY = "equal_mouse_history_mae_minus_joint_mae_on_released_proxy"
CONTRASTS = tuple(a + "_minus_joint" for a in ARMS[1:]) + ("persistence_minus_joint",)


class ContractError(ValueError):
    """Malformed submission or operator input; caller determines attribution."""


def need(condition, reason):
    if not condition:
        raise ContractError(reason)


def exact_fields(obj, fields, reason):
    need(type(obj) is dict and set(obj) == set(fields), reason)


def fraction(value):
    need(type(value) in (int, float), "numeric nonboolean fraction required")
    # Checking bounds first also handles arbitrarily large JSON integers safely.
    need(0 <= value <= 1, "finite fraction in [0,1] required")
    return float(value)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def invalid(_):
        raise ContractError("nonfinite JSON constant")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ContractError("invalid JSON") from exc


def read_json(path, cap, sha256=None):
    """Read a bounded regular file and authenticate before parsing its content."""
    if sha256 is not None:
        need(type(sha256) is str and HEX64.fullmatch(sha256), "invalid operator digest")
    path = Path(path).absolute()
    need(".." not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)),
         "no symlink input path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= cap, "bounded regular input required")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(cap + 1)
        after, linked = os.fstat(fd), path.lstat()
        attrs = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
        need(len(raw) == before.st_size <= cap and
             all(getattr(before, k) == getattr(after, k) == getattr(linked, k) for k in attrs),
             "input changed during read")
    finally:
        os.close(fd)
    if sha256 is not None:
        need(hashlib.sha256(raw).hexdigest() == sha256, "operator digest mismatch")
    return strict_json(raw)


def validate_support(support):
    """Original SUPPORT ABI: seven folds, two consecutive five-ID sessions each."""
    exact_fields(support, ("task_id", "folds"), "operator support fields")
    need(support["task_id"] == TASK, "operator support task")
    folds = support["folds"]
    need(type(folds) is dict and set(folds) == set(FOLDS), "exact seven held-mouse folds required")
    all_ids = []
    for fold in FOLDS:
        ids = folds[fold]
        need(type(ids) is list and len(ids) == 10, "ten query IDs per held mouse required")
        need(all(type(q) is str and HEX64.fullmatch(q) for q in ids), "opaque 64-hex query IDs required")
        all_ids.extend(ids)
    need(len(set(all_ids)) == 70, "query IDs must be unique across held mice")
    return {(fold, arm, q) for fold in FOLDS for arm in ARMS for q in folds[fold]}


def validate_submission(submission, expected):
    exact_fields(submission, ("task_id", "predictions"), "submission fields")
    need(submission["task_id"] == TASK, "submission task")
    rows = submission["predictions"]
    need(type(rows) is list and len(rows) == 280, "all 280 arm/query predictions required")
    result = {}
    for row in rows:
        exact_fields(row, ("fold", "arm", "id", "fraction"), "prediction fields")
        need(all(type(row[k]) is str for k in ("fold", "arm", "id")), "string prediction identities required")
        key = row["fold"], row["arm"], row["id"]
        need(key in expected and key not in result, "unexpected or duplicate prediction identity")
        result[key] = fraction(row["fraction"])
    need(set(result) == expected, "complete prediction support required")
    return result


def validate_targets(target_obj, support):
    exact_fields(target_obj, ("task_id", "targets"), "operator target fields")
    need(target_obj["task_id"] == TASK, "operator target task")
    targets = target_obj["targets"]
    expected = {q for ids in support["folds"].values() for q in ids}
    need(type(targets) is dict and set(targets) == expected, "exact operator target support required")
    clean = {}
    for query, row in targets.items():
        exact_fields(row, ("target", "persistence"), "operator target row fields")
        clean[query] = {k: fraction(row[k]) for k in ("target", "persistence")}
    return clean


def percentile(values, quantile):
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower, upper = math.floor(position), math.ceil(position)
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def _score_admitted(predictions, support, targets):
    per_mouse = []
    for fold in FOLDS:
        ids = support["folds"][fold]
        per_session = []
        # build.py appends exactly five ordered blocks for each source session.
        # These ordinals are private support positions, not source/context labels.
        for session in range(2):
            queries = ids[session * 5:(session + 1) * 5]
            errors = {arm: math.fsum(abs(targets[q]["target"] - predictions[fold, arm, q])
                                    for q in queries) / 5 for arm in ARMS}
            baseline = math.fsum(abs(targets[q]["target"] - targets[q]["persistence"])
                                 for q in queries) / 5
            prevalence = math.fsum(targets[q]["target"] for q in queries) / 5
            per_session.append({"session_ordinal": session, "queries": 5, "mae": errors,
                                "persistence_mae": baseline, "target_fraction_mean": prevalence})
        errors = {arm: math.fsum(s["mae"][arm] for s in per_session) / 2 for arm in ARMS}
        baseline = math.fsum(s["persistence_mae"] for s in per_session) / 2
        per_mouse.append({"fold": fold, "queries": 10, "sessions": per_session, "mae": errors,
                          "persistence_mae": baseline, "persistence_minus_joint": baseline - errors["joint"],
                          **{arm + "_minus_joint": errors[arm] - errors["joint"] for arm in ARMS[1:]}})
    rng = random.Random(36036)
    draws = {name: [] for name in CONTRASTS}
    for _ in range(10000):
        indices = [rng.randrange(7) for _ in range(7)]
        for name in CONTRASTS:
            draws[name].append(math.fsum(per_mouse[i][name] for i in indices) / 7)
    contrasts = {name: {"estimate": math.fsum(row[name] for row in per_mouse) / 7,
                        "pointwise_descriptive_bootstrap95": [percentile(draws[name], .025),
                                                              percentile(draws[name], .975)]}
                 for name in CONTRASTS}
    return {"schema_version": "neural036-proxy-score/v1", "status": "scored", "task_id": TASK,
            "primary": {"name": PRIMARY, "direction": "higher", **contrasts["history_minus_joint"]},
            "mice": 7, "sessions": 14, "queries": 70, "predictions": 280,
            "mouse_macro_mae": {arm: math.fsum(row["mae"][arm] for row in per_mouse) / 7 for arm in ARMS},
            "persistence_macro_mae": math.fsum(row["persistence_mae"] for row in per_mouse) / 7,
            "contrasts": contrasts, "per_mouse": per_mouse,
            "bootstrap": {"draws": 10000, "seed": 36036, "unit": "whole mouse", "shared_draws": True,
                          "prediction_refits": False, "interpretation": "pointwise descriptive"},
            "acceptance_threshold": None, "execution_isolation_verified_by_this_scorer": False,
            "physical_freezing_polarity_or_clock_verified_by_this_scorer": False}


def score(submission, support, target_obj):
    """In-memory software interface; file-based operators should use evaluate()."""
    expected = validate_support(support)
    predictions = validate_submission(submission, expected)
    targets = validate_targets(target_obj, support)
    return _score_admitted(predictions, support, targets)


def evaluate(submission_path, support_path, support_sha256, targets_path, targets_sha256):
    """Admit the entire candidate collection before even opening numeric targets."""
    try:
        submission = read_json(submission_path, 262144)
    except (ContractError, OSError):
        return {"status": "invalid_submission", "reason": "unreadable or malformed submission", "score": None}
    try:
        need(type(support_sha256) is str and HEX64.fullmatch(support_sha256), "invalid operator digest")
        support = read_json(support_path, 32768, support_sha256)
        expected = validate_support(support)
    except (ContractError, OSError) as exc:
        return {"status": "operator_error", "reason": str(exc) if isinstance(exc, ContractError) else "support read failure", "score": None}
    try:
        predictions = validate_submission(submission, expected)
    except ContractError as exc:
        return {"status": "invalid_submission", "reason": str(exc), "score": None}
    try:
        need(type(targets_sha256) is str and HEX64.fullmatch(targets_sha256), "invalid operator digest")
        target_obj = read_json(targets_path, 32768, targets_sha256)
        targets = validate_targets(target_obj, support)
        return _score_admitted(predictions, support, targets)
    except (ContractError, OSError) as exc:
        return {"status": "operator_error", "reason": str(exc) if isinstance(exc, ContractError) else "target read failure", "score": None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("submission", "support", "support-sha256", "targets", "targets-sha256", "output"):
        parser.add_argument("--" + flag, required=True)
    args = parser.parse_args(argv)
    output = Path(args.output).absolute()
    need(".." not in output.parts and all(not p.is_symlink() for p in (output, *output.parents)),
         "no symlink output path")
    # Reserve a fresh private report before reading inputs, so failure cannot
    # overwrite either input material or a previous report.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        report = evaluate(args.submission, args.support, args.support_sha256, args.targets, args.targets_sha256)
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(report["status"])
    return 0 if report["status"] == "scored" else 2


if __name__ == "__main__":
    raise SystemExit(main())
