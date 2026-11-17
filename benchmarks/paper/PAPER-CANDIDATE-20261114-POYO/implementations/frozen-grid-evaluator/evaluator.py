"""POYO complete frozen-grid output consumer; no training or historical qualification."""
import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

TASK = "PAPER-CANDIDATE-20261114-POYO"
POLICY = "poyo-stitch-uniform-r2-tm1.9-prospective-v1"
FAMILIES = frozenset(("churchland-shenoy-2012", "perich-miller-2018",
                      "odoherty-sabes-rtt", "flint-slutzky-2012"))
METHODS = ("pretrained", "from_scratch", "ridge", "recurrent")
EPSILON = Fraction.from_float(1e-4)
MAX_BYTES = 64 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exact_keys(value, names, role):
    require(type(value) is dict and set(value) == set(names), role + ": keys")


def ident(value, role):
    require(type(value) is str and 0 < len(value) <= 256
            and all(32 < ord(c) < 127 for c in value), role + ": identifier")
    return value


def number(value, role):
    require(type(value) in (int, float), role + ": numeric type")
    try:
        x = float(value)
    except (OverflowError, ValueError):
        raise ValueError(role + ": numeric range") from None
    require(math.isfinite(x), role + ": finite")
    # JSON integers above 2**53 may be legitimate: retain their exact value in math.
    return Fraction(value)


def pair(value, role):
    require(type(value) is list and len(value) == 2, role + ": two dimensions")
    return tuple(number(x, role) for x in value)


def identity(value, role):
    exact_keys(value, ("bytes", "sha256"), role)
    require(type(value["bytes"]) is int and value["bytes"] > 0, role + ": extent")
    require(type(value["sha256"]) is str
            and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is not None,
            role + ": digest")


def list_ids(value, role, nonempty=True):
    require(type(value) is list and (value or not nonempty), role + ": list")
    result = [ident(x, role) for x in value]
    require(len(set(result)) == len(result), role + ": duplicate")
    return set(result)


def load_json(body):
    require(type(body) is bytes and len(body) <= MAX_BYTES, "JSON bytes/cap")
    def members(items):
        out = {}
        for key, value in items:
            require(key not in out, "duplicate JSON key")
            out[key] = value
        return out
    def constant(_):
        raise ValueError("nonfinite JSON token")
    return json.loads(body, object_pairs_hook=members, parse_constant=constant)


def authenticate(body, pin, role):
    identity(pin, role)
    require(len(body) == pin["bytes"] and hashlib.sha256(body).hexdigest() == pin["sha256"],
            role + ": content identity")


def admit_design(design):
    exact_keys(design, ("task_id", "schema", "policy", "corpus", "pretraining_sessions",
                        "budgets", "cases", "authority", "architecture"), "design")
    require(design["task_id"] == TASK and design["schema"] == "poyo_frozen_grid_v1",
            "design task/schema")
    require(design["policy"] == POLICY, "prospective metric policy")
    # This is a trusted external evidence identity, not proof that its conclusions hold.
    identity(design["authority"], "complete-grid scientific authority")
    ident(design["architecture"], "matched pretrained/from-scratch architecture")
    require(type(design["corpus"]) is list and len(design["corpus"]) == 158,
            "complete 158-session corpus required")
    corpus = {}
    for row in design["corpus"]:
        exact_keys(row, ("session_id", "animal_id", "source_family", "source",
                         "normalization"), "corpus row")
        sid = ident(row["session_id"], "session")
        ident(row["animal_id"], "animal")
        require(sid not in corpus and row["source_family"] in FAMILIES, "corpus identity")
        identity(row["source"], "original session provenance")
        norm = row["normalization"]
        exact_keys(norm, ("mean", "std", "provenance"), "normalization")
        pair(norm["mean"], "normalization mean")
        require(all(x > 0 for x in pair(norm["std"], "normalization std")),
                "positive normalization scale")
        identity(norm["provenance"], "training-only normalization provenance")
        corpus[sid] = row
    require({r["source_family"] for r in corpus.values()} == FAMILIES,
            "all four source families required")
    require(len({r["animal_id"] for r in corpus.values()}) == 7,
            "seven authenticated primates required")
    pretrain = list_ids(design["pretraining_sessions"], "pretraining sessions")
    require(pretrain <= corpus.keys(), "unknown pretraining session")
    require(type(design["budgets"]) is list and design["budgets"], "budgets required")
    budgets = {}
    for row in design["budgets"]:
        exact_keys(row, ("budget_id", "adaptation_trials", "held_sessions"), "budget")
        bid = ident(row["budget_id"], "budget id")
        require(bid not in budgets and type(row["adaptation_trials"]) is int
                and row["adaptation_trials"] > 0, "budget identity/trial count")
        held = list_ids(row["held_sessions"], "held sessions")
        require(held <= corpus.keys() and not held & pretrain,
                "held/pretraining overlap or unknown session")
        budgets[bid] = row
    require(type(design["cases"]) is list, "case grid")
    expected = {(b, s) for b, row in budgets.items() for s in row["held_sessions"]}
    cases = {}
    for row in design["cases"]:
        exact_keys(row, ("budget_id", "session_id", "adaptation_trials", "development_trials",
                         "rows", "support_provenance"), "case")
        key = (ident(row["budget_id"], "case budget"), ident(row["session_id"], "case session"))
        require(key in expected and key not in cases, "unexpected/duplicate case")
        adaptation = list_ids(row["adaptation_trials"], "adaptation trials")
        require(len(adaptation) == budgets[key[0]]["adaptation_trials"], "adaptation budget")
        development = list_ids(row["development_trials"], "development trials", nonempty=False)
        require(not adaptation & development, "adaptation/development overlap")
        identity(row["support_provenance"], "complete test-support provenance")
        require(type(row["rows"]) is list and row["rows"], "complete test rows")
        row_ids, timestamps = set(), set()
        for point in row["rows"]:
            exact_keys(point, ("row_id", "trial_id", "timestamp"), "test occurrence")
            rid = ident(point["row_id"], "row id")
            tid = ident(point["trial_id"], "test trial")
            require(rid not in row_ids and tid not in adaptation | development,
                    "duplicate occurrence or adaptation/development/test overlap")
            row_ids.add(rid)
            timestamps.add(number(point["timestamp"], "absolute session timestamp"))
        require(len(timestamps) >= 2, "R2 needs at least two stitched samples")
        cases[key] = row
    require(set(cases) == expected, "missing full held-session/budget support")
    return corpus, cases


def admit_predictions(submission, cases):
    exact_keys(submission, ("task_id", "schema", "policy", "results"), "submission")
    require(submission["task_id"] == TASK and submission["schema"] == "poyo_predictions_v1"
            and submission["policy"] == POLICY, "submission identity")
    require(type(submission["results"]) is list, "prediction results")
    expected = {(b, s, m) for b, s in cases for m in METHODS}
    admitted = {}
    for result in submission["results"]:
        exact_keys(result, ("budget_id", "session_id", "method", "rows"), "prediction result")
        key = (ident(result["budget_id"], "prediction budget"),
               ident(result["session_id"], "prediction session"),
               ident(result["method"], "method"))
        require(key in expected and key not in admitted, "unexpected/duplicate prediction result")
        support = cases[key[:2]]["rows"]
        require(type(result["rows"]) is list and len(result["rows"]) == len(support),
                "complete prediction occurrence count")
        values = []
        for point, fixed in zip(result["rows"], support):
            exact_keys(point, ("row_id", "values"), "prediction occurrence")
            require(point["row_id"] == fixed["row_id"], "prediction order/identity")
            values.append(pair(point["values"], "prediction values"))
        admitted[key] = values
    require(set(admitted) == expected, "missing complete methods/budgets/sessions")
    return admitted


def admit_targets(targets, cases):
    exact_keys(targets, ("schema", "cases"), "targets")
    require(targets["schema"] == "poyo_targets_v1" and type(targets["cases"]) is list,
            "target schema")
    admitted = {}
    for result in targets["cases"]:
        exact_keys(result, ("budget_id", "session_id", "rows"), "target case")
        key = (ident(result["budget_id"], "target budget"), ident(result["session_id"], "target session"))
        require(key in cases and key not in admitted, "unexpected/duplicate target case")
        support = cases[key]["rows"]
        require(type(result["rows"]) is list and len(result["rows"]) == len(support),
                "target support")
        values = []
        for point, fixed in zip(result["rows"], support):
            exact_keys(point, ("row_id", "values"), "target occurrence")
            require(point["row_id"] == fixed["row_id"], "target order/identity")
            values.append(pair(point["values"], "normalized target values"))
        admitted[key] = values
    require(set(admitted) == set(cases), "missing complete targets")
    return admitted


def stitch(support, values):
    pools = {}
    for row, value in zip(support, values):
        key = number(row["timestamp"], "timestamp")
        sums, count = pools.get(key, ((Fraction(0), Fraction(0)), 0))
        pools[key] = ((sums[0] + value[0], sums[1] + value[1]), count + 1)
    return [tuple(x / pools[key][1] for x in pools[key][0]) for key in sorted(pools)]


def r2(prediction, target):
    require(len(prediction) == len(target) and len(target) >= 2, "R2 sample support")
    scores, branches = [], []
    for dim in (0, 1):
        mean = sum((v[dim] for v in target), Fraction(0)) / len(target)
        rss = sum(((t[dim] - p[dim]) ** 2 for p, t in zip(prediction, target)), Fraction(0))
        tss = sum(((t[dim] - mean) ** 2 for t in target), Fraction(0))
        if rss <= EPSILON:
            score, branch = Fraction(1), "near_zero_residual"
        elif tss <= EPSILON:
            score, branch = Fraction(0), "near_constant_target"
        else:
            score, branch = 1 - rss / tss, "ordinary_r2"
        scores.append(score)
        branches.append(branch)
    return sum(scores, Fraction(0)) / 2, scores, branches


def as_float(value):
    try:
        result = float(value)
    except OverflowError:
        raise ValueError("unrepresentable metric; no clipped score") from None
    require(math.isfinite(result), "nonfinite metric")
    return result


def evaluate(design_body, design_pin, prediction_body, target_loader):
    """Trusted owner API. The callback is first called after complete public admission."""
    authenticate(design_body, design_pin, "selected design")
    design = load_json(design_body)
    corpus, cases = admit_design(design)
    predictions = admit_predictions(load_json(prediction_body), cases)
    targets = admit_targets(load_json(target_loader()), cases)
    results, by_group, exact_scores = [], {}, {}
    for (budget, session), case in cases.items():
        target = stitch(case["rows"], targets[(budget, session)])
        for method in METHODS:
            score, dims, branches = r2(stitch(case["rows"], predictions[(budget, session, method)]), target)
            exact_scores[(budget, session, method)] = score
            results.append(dict(budget_id=budget, session_id=session, method=method,
                                r2=as_float(score), dimension_r2=[as_float(x) for x in dims],
                                branches=branches, occurrences=len(case["rows"]),
                                stitched_samples=len(target)))
            groups = (("all", "all"), ("source", corpus[session]["source_family"]),
                      ("animal", corpus[session]["animal_id"]))
            for group, label in groups:
                by_group.setdefault((budget, method, group, label), []).append(score)
    summaries = [dict(budget_id=b, method=m, group=g, identity=i, sessions=len(v),
                      session_macro_r2=as_float(sum(v, Fraction(0)) / len(v)))
                 for (b, m, g, i), v in sorted(by_group.items())]
    contrasts = []
    for budget in design["budgets"]:
        bid = budget["budget_id"]
        for comparator in METHODS[1:]:
            diffs = [(s, exact_scores[(bid, s, "pretrained")] - exact_scores[(bid, s, comparator)])
                     for s in budget["held_sessions"]]
            contrasts.append(dict(budget_id=bid, comparator=comparator,
                                  session_differences=[dict(session_id=s, difference=as_float(d)) for s, d in diffs],
                                  mean_difference=as_float(sum((d for _, d in diffs), Fraction(0)) / len(diffs))))
    return dict(schema="poyo_frozen_grid_scores_v1", task_id=TASK, policy=POLICY,
                corpus_sessions=158, corpus_animals=7, cases=len(cases), results=results,
                summaries=summaries, contrasts=contrasts, scientific_qualification=False,
                historical_reproduction=False, input_provenance_verified=False,
                qualification_note="Scored supplied frozen metadata, not independently verified scientific membership or method execution.")


def read_bytes(path):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_size <= MAX_BYTES,
                "operand must be bounded ordinary regular file")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            body = handle.read(MAX_BYTES + 1)
    finally:
        os.close(fd)
    require(len(body) <= MAX_BYTES, "operand exceeds byte cap")
    return body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("design", "predictions", "targets", "output"):
        parser.add_argument("--" + name, required=True)
    for role in ("design", "targets"):
        parser.add_argument("--" + role + "-bytes", required=True, type=int)
        parser.add_argument("--" + role + "-sha256", required=True)
    args = parser.parse_args()
    def private():
        body = read_bytes(args.targets)
        authenticate(body, dict(bytes=args.targets_bytes, sha256=args.targets_sha256), "private targets")
        return body
    result = evaluate(read_bytes(args.design), dict(bytes=args.design_bytes, sha256=args.design_sha256),
                      read_bytes(args.predictions), private)
    body = json.dumps(result, indent=2, allow_nan=False) + "\n"
    with Path(args.output).open("x", encoding="utf8") as handle:
        handle.write(body)


if __name__ == "__main__":
    main()
