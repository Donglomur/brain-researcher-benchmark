"""Finite Figure 5e prediction evaluator. No fitting, loading neural arrays or code execution."""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import statistics

TASK = "PAPER-SCOPE-20261114-REM-DYNAMICS"
ARTICLE_SHA = "83792709d1157ba7527a4b67e95c93c98d94932e3396d8a0c44c6f9587cfdc18"
CODE_COMMIT = "ded027368c37f19c837baf02b81802007886ba46"
MAX_BYTES = 2 * 1024 * 1024
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")


class Invalid(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise Invalid(message)


def fields(value, names, where):
    require(type(value) is dict and set(value) == set(names), where + ": exact fields required")


def number(x, lo, hi, where):
    # Reject arbitrary-size JSON integers before converting them to C double.
    require(type(x) in (int, float) and lo <= x <= hi, where)
    require(math.isfinite(x), where)
    return x


def identifier(x):
    require(type(x) is str and ID.fullmatch(x), "invalid identifier")
    return x


def digest(x):
    require(type(x) is str and SHA.fullmatch(x), "invalid SHA-256")
    return x


def unique_pairs(pairs):
    result = {}
    for k, v in pairs:
        require(k not in result, "duplicate JSON key")
        result[k] = v
    return result


def constant(_):
    raise Invalid("nonfinite JSON constant")


def load(path):
    """Ordinary single-link finite files only; neither imports nor pickle decoding."""
    path = Path(path).absolute()
    for parent in (path, *path.parents):
        require(not parent.is_symlink(), "symlink path component")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "ordinary single-link file required")
        require(0 < before.st_size <= MAX_BYTES, "file byte limit")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(MAX_BYTES + 1)
        after = os.fstat(fd)
        require(len(body) == before.st_size and (before.st_size, before.st_mtime_ns, before.st_ctime_ns) == (after.st_size, after.st_mtime_ns, after.st_ctime_ns), "file changed or oversized")
    finally:
        os.close(fd)
    try:
        parsed = json.loads(body, object_pairs_hook=unique_pairs, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise Invalid("invalid bounded JSON") from error
    return parsed, hashlib.sha256(body).hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def validate_owner(owner):
    fields(owner, ["schema", "task_id", "mode", "provenance", "mice", "trials", "historical"], "owner")
    require(owner["schema"] == "rem-dmm-owner-v1" and owner["task_id"] == TASK, "owner identity")
    require(owner["mode"] in ("historical_fig5e", "prospective_onset"), "mode")
    prov = owner["provenance"]
    fields(prov, ["article_sha256", "official_code_commit", "data_manifest_sha256", "annotation_join_sha256", "cohort_join_sha256"], "provenance")
    require(prov["article_sha256"] == ARTICLE_SHA and prov["official_code_commit"] == CODE_COMMIT, "source identity")
    for key in ("data_manifest_sha256", "annotation_join_sha256", "cohort_join_sha256"):
        digest(prov[key])
    mice = owner["mice"]
    require(type(mice) is list and len(mice) == 5, "five mice required")
    require(len(set(identifier(x) for x in mice)) == 5, "unique mice required")
    require(type(owner["trials"]) is list and len(owner["trials"]) == 45, "complete 45-trial cohort required")
    trials = {}
    for row in owner["trials"]:
        fields(row, ["trial_id", "mouse_id", "nrem_at_onset", "rem_within_60s"], "trial")
        tid = identifier(row["trial_id"])
        require(tid not in trials and row["mouse_id"] in mice, "trial duplicate or unknown mouse")
        require(row["nrem_at_onset"] is True, "Figure 5e requires NREM at laser onset")
        require(type(row["rem_within_60s"]) is int and row["rem_within_60s"] in (0, 1), "binary owner target required")
        trials[tid] = row
    require({r["mouse_id"] for r in trials.values()} == set(mice), "all five mice must contribute")
    require(sum(r["rem_within_60s"] for r in trials.values()) == 20, "20 successful and 25 unsuccessful trials required")
    hist = owner["historical"]
    if owner["mode"] == "prospective_onset":
        require(hist is None, "prospective mode must not inherit historical splits")
        return trials, {}
    fields(hist, ["split_realization_sha256", "train_count", "bonferroni_factor", "splits"], "historical")
    digest(hist["split_realization_sha256"])
    require(type(hist["train_count"]) is int and hist["train_count"] in (31, 32), "70/30 rounding must be explicitly bound")
    factor = hist["bonferroni_factor"]
    require(factor is None or type(factor) is int and 1 <= factor <= 10000, "explicit correction factor or null required")
    require(type(hist["splits"]) is list and len(hist["splits"]) == 220, "22 by 10 split cells required")
    splits = {}
    for split in hist["splits"]:
        fields(split, ["pc", "repeat", "train_ids", "test_ids"], "split")
        pc, rep = split["pc"], split["repeat"]
        require(type(pc) is int and 1 <= pc <= 22 and type(rep) is int and 0 <= rep < 10, "split indices")
        require((pc, rep) not in splits, "duplicate split cell")
        for key, n in (("train_ids", hist["train_count"]), ("test_ids", 45 - hist["train_count"])):
            ids = split[key]
            require(type(ids) is list and len(ids) == n, "split size")
            require(all(type(x) is str and x in trials for x in ids) and len(set(ids)) == n, "split IDs")
        tr, te = set(split["train_ids"]), set(split["test_ids"])
        require(not tr & te and tr | te == set(trials), "train/test must partition complete cohort")
        require({trials[t]["rem_within_60s"] for t in tr} == {0, 1}, "LDA training requires both classes")
        splits[pc, rep] = split
    return trials, splits


def public_plan(owner):
    """No assessment outcomes; this binds IDs and selected support, not source parity."""
    validate_owner(owner)
    return {"task_id": TASK, "mode": owner["mode"], "mice": owner["mice"],
            "trials": [{"trial_id": t["trial_id"], "mouse_id": t["mouse_id"]} for t in owner["trials"]],
            "historical": owner["historical"]}


def beta_fraction(a, b, x):
    """Continued fraction for regularized incomplete beta; finite iteration bound."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1 / d
    h = d
    for m in range(1, 201):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d, c = 1 + aa * d, 1 + aa / c
        if abs(d) < tiny: d = tiny
        if abs(c) < tiny: c = tiny
        d = 1 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d, c = 1 + aa * d, 1 + aa / c
        if abs(d) < tiny: d = tiny
        if abs(c) < tiny: c = tiny
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 3e-14:
            return h
    raise Invalid("beta convergence failure")


def t_upper_tail(t, df):
    number(t, -1e12, 1e12, "bounded t")
    x, a, b = df / (df + t * t), df / 2, 0.5
    if x == 1:
        return 0.5
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        ib = bt * beta_fraction(a, b, x) / a
    else:
        ib = 1 - bt * beta_fraction(b, a, 1 - x) / b
    p = min(1.0, max(0.0, 0.5 * ib))
    return p if t >= 0 else 1 - p


def summarize_accuracies(values, factor):
    mean = statistics.mean(values)
    sem = statistics.stdev(values) / math.sqrt(len(values))
    if sem == 0:
        t, p = None, None
        status = "undefined_zero_sample_variance"
    else:
        t = (mean - 0.5) / sem
        p = t_upper_tail(t, len(values) - 1)
        status = "finite"
    return {"mean_accuracy": mean, "sem": sem, "t_against_0_5": t, "t_status": status,
            "df": len(values) - 1, "p_one_sided_raw": p,
            "bonferroni_factor": factor, "p_bonferroni": None if p is None or factor is None else min(1.0, p * factor)}


def prediction_rows(candidate, owner, plan_hash):
    fields(candidate, ["schema", "task_id", "mode", "case_plan_sha256", "predictions"], "predictions")
    require(candidate["schema"] == "rem-dmm-predictions-v1" and candidate["task_id"] == TASK and candidate["mode"] == owner["mode"], "candidate identity/mode")
    require(candidate["case_plan_sha256"] == plan_hash, "case-plan mismatch")
    rows = candidate["predictions"]
    require(type(rows) is list, "prediction rows required")
    return rows


def historical_predictions(rows, splits):
    require(len(rows) == sum(len(s["test_ids"]) for s in splits.values()), "complete held prediction grid required")
    predictions = {}
    for r in rows:
        fields(r, ["pc", "repeat", "trial_id", "predicted_label"], "prediction")
        require(type(r["pc"]) is int and type(r["repeat"]) is int, "integer indices required")
        key = (r["pc"], r["repeat"])
        require(key in splits and type(r["trial_id"]) is str and r["trial_id"] in splits[key]["test_ids"], "unexpected prediction support")
        k = (*key, r["trial_id"])
        require(k not in predictions, "duplicate prediction")
        require(type(r["predicted_label"]) is int and r["predicted_label"] in (0, 1), "binary predicted label required")
        predictions[k] = r["predicted_label"]
    return predictions


def historical_counts(ids, trials, predictions, pc, rep, baseline=None):
    result = {"n_test": len(ids), "tp": 0, "fp": 0, "tn": 0, "fn": 0}
    if baseline is not None:
        result.update(baseline_correct=0, candidate_only_correct=0, baseline_only_correct=0)
    for tid in ids:
        y, yh = trials[tid]["rem_within_60s"], predictions[pc, rep, tid]
        result[{(1, 1): "tp", (0, 1): "fp", (0, 0): "tn", (1, 0): "fn"}[y, yh]] += 1
        if baseline is not None:
            base_correct = baseline[pc, rep, tid] == y
            result["baseline_correct"] += int(base_correct)
            result["candidate_only_correct"] += int(yh == y and not base_correct)
            result["baseline_only_correct"] += int(yh != y and base_correct)
    correct = result["tp"] + result["tn"]
    result["accuracy"] = correct / len(ids) if ids else None
    if baseline is not None:
        result["baseline_accuracy"] = result["baseline_correct"] / len(ids) if ids else None
        result["paired_accuracy_delta"] = (correct - result["baseline_correct"]) / len(ids) if ids else None
    return result


def score(owner, candidate, baseline=None):
    trials, splits = validate_owner(owner)
    require(baseline is None or owner["mode"] == "historical_fig5e", "paired baseline requires historical_fig5e mode")
    plan_hash = canonical_hash(public_plan(owner))
    rows = prediction_rows(candidate, owner, plan_hash)
    report = {"schema": "rem-dmm-score-v1", "task_id": TASK, "mode": owner["mode"],
              "case_plan_sha256": plan_hash, "cohort_trials": 45, "biological_mice": 5,
              "author_pipeline_parity_established": False, "scientific_qualification": False,
              "information_isolation_established_by_scorer": False,
              "comparison_present": baseline is not None,
              "scope": "Figure 5e dmM stimulation only; excludes Figure 2h and other interventions"}
    if owner["mode"] == "historical_fig5e":
        predictions = historical_predictions(rows, splits)
        baseline_index = historical_predictions(prediction_rows(baseline, owner, plan_hash), splits) if baseline is not None else None
        cells, pcs = [], []
        for pc in range(1, 23):
            accuracies, baseline_accuracies, deltas = [], [], []
            for rep in range(10):
                ids = splits[pc, rep]["test_ids"]
                cell = {"pc": pc, "repeat": rep, **historical_counts(ids, trials, predictions, pc, rep, baseline_index)}
                cell["mice"] = [{"mouse_id": mouse, **historical_counts(
                    [tid for tid in ids if trials[tid]["mouse_id"] == mouse], trials, predictions, pc, rep, baseline_index)}
                    for mouse in owner["mice"]]
                accuracies.append(cell["accuracy"])
                if baseline_index is not None:
                    baseline_accuracies.append(cell["baseline_accuracy"])
                    deltas.append(cell["paired_accuracy_delta"])
                cells.append(cell)
            summary = {"pc": pc, "accuracies": accuracies, **summarize_accuracies(accuracies, owner["historical"]["bonferroni_factor"])}
            if baseline_index is not None:
                summary.update(baseline_accuracies=baseline_accuracies,
                               baseline_summary=summarize_accuracies(baseline_accuracies, owner["historical"]["bonferroni_factor"]),
                               paired_accuracy_deltas=deltas, mean_paired_accuracy_delta=statistics.mean(deltas))
            pcs.append(summary)
        usage = Counter(tid for split in splits.values() for tid in split["test_ids"])
        support = [{"trial_id": tid, "mouse_id": trial["mouse_id"], "held_split_uses": usage[tid]} for tid, trial in trials.items()]
        report.update(cells=cells, principal_components=pcs, fit_cells=220, trial_support=support,
                      interpretation="Historical pooled-trial resampling statistic; resamples are not independent animals. Paired accuracy differences are descriptive on the identical declared plan, not a superiority test or animal-level uncertainty. Every mouse and all 45 trials remain visible, including zero held support. Exact author splits, PCA/LDA implementation, rounding and correction family are not certified by an owner manifest.")
    else:
        require(len(rows) == 45, "complete prospective 45-trial support required")
        predictions = {}
        for r in rows:
            fields(r, ["trial_id", "probability_rem_within_60s"], "prospective prediction")
            tid = r["trial_id"]
            require(type(tid) is str and tid in trials and tid not in predictions, "unexpected/duplicate prospective trial")
            predictions[tid] = number(r["probability_rem_within_60s"], 0, 1, "finite probability in [0,1] required")
        mouse_rows = []
        for mouse in owner["mice"]:
            ids = [t for t in trials if trials[t]["mouse_id"] == mouse]
            losses = {t: (predictions[t] - trials[t]["rem_within_60s"]) ** 2 for t in ids}
            classes = {}
            for label in (0, 1):
                values = [losses[t] for t in ids if trials[t]["rem_within_60s"] == label]
                classes[str(label)] = {"n": len(values), "brier": statistics.mean(values) if values else None}
            mouse_rows.append({"mouse_id": mouse, "n": len(ids), "brier": statistics.mean(losses.values()), "class_conditional": classes})
        report.update(mice=mouse_rows, equal_mouse_brier=statistics.mean(r["brier"] for r in mouse_rows),
                      pooled_trial_brier=statistics.mean((predictions[t] - trials[t]["rem_within_60s"]) ** 2 for t in trials),
                      interpretation="Assistant-proposed onset-prospective endpoint, not the paper's Figure 5e statistic. Requires independently admitted past-only inputs, calibration and held-mouse protocol; this evaluator cannot prove those properties.")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("owner")
    parser.add_argument("candidate")
    parser.add_argument("--baseline", help="Frozen historical Figure 5e comparator on the identical case plan")
    args = parser.parse_args()
    try:
        owner, oh = load(args.owner)
        candidate, ch = load(args.candidate)
        baseline, bh = load(args.baseline) if args.baseline else (None, None)
        result = score(owner, candidate, baseline)
        result.update(owner_sha256=oh, candidate_sha256=ch)
        if baseline is not None:
            result["baseline_sha256"] = bh
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    except (Invalid, OSError, RecursionError) as error:
        print(json.dumps({"schema": "rem-dmm-refusal-v1", "error": str(error)}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
