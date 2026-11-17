"""Original Fig. 3b arithmetic on externally frozen, owner-held source folds.

No pickle loading, native preparation, fitting, resplitting, or win decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

TASK = "PAPER-EXP-20261113-004"
COMMIT = "adf0f9ed3defa22275d92fa0ed996f47008e05b3"
ANIMALS = ("GCAMP3", "GCAMP4", "GCAMP7", "GCAMP11", "GCAMP12", "GCAMP13",
           "GCAMP14", "GCAMP15", "GCAMP17", "GCAMP18", "GCAMP19")
DAYS = (3, 5, 7, 8, 10, 12, 14)
CELL_TYPES = ("rr", "track", "nonreward_remap")
MODELS = ("train0_test0", "train0_test1", "train1_test1", "train1_test0", "random")
SCHEMA = "reward-relative-fig3-panel-v2"


class InputError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InputError(message)


def exact(obj, fields, name):
    require(isinstance(obj, dict) and set(obj) == set(fields), name + ": unexpected fields")


def finite(value, name):
    require(type(value) in (int, float), name + ": must be a finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise InputError(name + ": must be a finite number") from None
    require(math.isfinite(result), name + ": must be a finite number")
    return result


def vector(value, size, name):
    require(isinstance(value, list) and len(value) == size, name + ": wrong dimension")
    return [finite(x, name) for x in value]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def hash_value(value, name):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), name + ": invalid SHA256")


def _validate(panel):
    exact(panel, ("schema", "source_commit", "preparation_sha256", "fold_receipt_sha256", "rows"), "panel")
    require(panel["schema"] == SCHEMA and panel["source_commit"] == COMMIT, "wrong source/schema")
    for name in ("preparation_sha256", "fold_receipt_sha256"):
        hash_value(panel[name], name)
    require(isinstance(panel["rows"], list) and len(panel["rows"]) == 1155,
            "require all 77 sessions x 3 cell classes x 5 source models")
    rows, supports = {}, {}
    for row in panel["rows"]:
        exact(row, ("animal", "day", "cell_type", "model", "folds", "shuffle_scores"), "row")
        require(isinstance(row["animal"], str) and row["animal"] in ANIMALS, "unknown animal")
        require(type(row["day"]) is int and row["day"] in DAYS, "unknown switch day")
        require(isinstance(row["cell_type"], str) and row["cell_type"] in CELL_TYPES, "unknown cell class")
        require(isinstance(row["model"], str) and row["model"] in MODELS, "unknown model condition")
        key = (row["animal"], row["day"], row["cell_type"], row["model"])
        require(key not in rows, "duplicate session/cell/model condition")
        require(isinstance(row["folds"], list) and len(row["folds"]) == 10, "ten original folds required")
        seen, lengths, fold_scores, support = set(), [], [], []
        for fold in row["folds"]:
            exact(fold, ("sample_ids", "actual", "predicted"), "fold")
            ids = fold["sample_ids"]
            require(isinstance(ids, list) and ids and all(isinstance(x, str) and x for x in ids),
                    "nonempty sample IDs required")
            require(len(set(ids)) == len(ids) and not (seen & set(ids)), "repeated test sample across folds")
            seen.update(ids)
            actual = vector(fold["actual"], len(ids), "actual angles")
            predicted = vector(fold["predicted"], len(ids), "predicted angles")
            require(all(-math.pi <= x <= math.pi for x in actual + predicted), "angles must be radians in [-pi,pi]")
            lengths.append(len(ids))
            fold_scores.append(statistics.fmean(math.cos(a - p) for a, p in zip(actual, predicted)))
            support.append({"sample_ids": ids, "actual": actual})
        quotient, remainder = divmod(sum(lengths), 10)
        require(lengths == [quotient + (i < remainder) for i in range(10)],
                "fold sizes differ from source np.array_split ordering")
        # All populations use the same ds indices; both training conditions with
        # the same test set use the same ten contiguous test folds.
        test_set = "all" if row["model"] == "random" else row["model"][-1]
        support_key = (row["animal"], row["day"], test_set)
        fingerprint = digest(support)
        require(support_key not in supports or supports[support_key] == fingerprint,
                "test samples/targets differ across cell populations or shared test condition")
        supports[support_key] = fingerprint
        shuffles = row["shuffle_scores"]
        require(isinstance(shuffles, list) and len(shuffles) == 100, "100 original shuffles required")
        means = []
        for shuffle in shuffles:
            values = vector(shuffle, 10, "shuffle fold scores")
            require(all(-1 <= x <= 1 for x in values), "shuffle scores must be cosine means, not effect sizes")
            means.append(statistics.fmean(values))
        rows[key] = {"fold_scores": fold_scores, "mean_cosine": statistics.fmean(fold_scores),
                     "shuffle_mean_cosine": statistics.fmean(means),
                     "shuffle_repeat_means": means, "sample_count": sum(lengths),
                     "test_support_sha256": fingerprint}
    expected = {(a, d, c, m) for a in ANIMALS for d in DAYS for c in CELL_TYPES for m in MODELS}
    require(set(rows) == expected, "incomplete original source panel")
    # Before/after test sets must be disjoint. Whole-session random support may overlap.
    before_after = {}
    for row in panel["rows"]:
        if row["cell_type"] == "rr" and row["model"] in MODELS[:2]:
            before_after[(row["animal"], row["day"], row["model"])] = {
                x for fold in row["folds"] for x in fold["sample_ids"]}
    for a in ANIMALS:
        for d in DAYS:
            require(not (before_after[a, d, MODELS[0]] & before_after[a, d, MODELS[1]]),
                    "before/after test samples overlap")
    return rows


def score_panel(panel):
    """Return session vectors; folds are equal-weighted, never pooled by samples."""
    rows = _validate(panel)
    output = []
    for (animal, day, cell_type, model), scores in sorted(rows.items()):
        output.append(dict(animal=animal, day=day, cell_type=cell_type, model=model,
                           figure3b=model in MODELS[:2], **scores))
    return {"schema": "reward-relative-fig3-scores-v2", "task_id": TASK,
            "panel_sha256": digest(panel), "rows": output,
            "figure3b_session_conditions": 462, "companion_session_conditions": 693,
            "qualification": "arithmetic_only; source protocol and author baseline not admitted"}


def compare(candidate, author):
    """Descriptive paired gains only, with exact source support and receipt equality."""
    left, right = _validate(candidate), _validate(author)
    for field in ("preparation_sha256", "fold_receipt_sha256"):
        require(candidate[field] == author[field], "candidate/author " + field + " differs")
    results, mice = [], []
    for key in sorted(left):
        require(left[key]["test_support_sha256"] == right[key]["test_support_sha256"],
                "candidate/author sample identity, order, fold or target mismatch")
        a, d, c, m = key
        results.append({"animal": a, "day": d, "cell_type": c, "model": m,
                        "candidate_mean_cosine": left[key]["mean_cosine"],
                        "author_mean_cosine": right[key]["mean_cosine"],
                        "paired_gain": left[key]["mean_cosine"] - right[key]["mean_cosine"],
                        "candidate_shuffle_mean": left[key]["shuffle_mean_cosine"],
                        "author_shuffle_mean": right[key]["shuffle_mean_cosine"]})
    for a in ANIMALS:
        for c in CELL_TYPES:
            for m in MODELS:
                gains = [r["paired_gain"] for r in results
                         if (r["animal"], r["cell_type"], r["model"]) == (a, c, m)]
                mice.append({"animal": a, "cell_type": c, "model": m,
                             "mean_paired_gain": statistics.fmean(gains), "sessions": 7})
    return {"schema": "reward-relative-fig3-comparison-v2", "task_id": TASK,
            "candidate_sha256": digest(candidate), "author_sha256": digest(author),
            "session_conditions": results, "mouse_conditions": mice,
            "qualification": "descriptive comparison only; no meaningful-effect or uncertainty rule admitted",
            "paper_win": None}


def export_native(native, support, preparation_sha256, fold_receipt_sha256):
    """Adapt JSON-safe author arrays using an owner-supplied exact fold ID map.

    `scores_shuffle[day][animal][cell]` is [100,10,5], not [5,100,10].
    `support[day][animal][model]` contains ten lists of source sample IDs.
    Native objects must be converted by an already admitted owner loader; this
    function never opens or executes pickles. No sample IDs are synthesized.
    """
    exact(native, ("pred", "actual", "scores", "scores_shuffle"), "native export")
    exact(support, map(str, DAYS), "native support days")
    for name in native:
        exact(native[name], map(str, DAYS), "native " + name + " days")
        for day in DAYS:
            exact(native[name][str(day)], ANIMALS, "native animals")
            for animal in ANIMALS:
                exact(native[name][str(day)][animal], CELL_TYPES, "native cell classes")
    for day in DAYS:
        exact(support[str(day)], ANIMALS, "support animals")
        for animal in ANIMALS:
            exact(support[str(day)][animal], MODELS, "support models")
    rows = []
    for day in DAYS:
        for animal in ANIMALS:
            for cell_type in CELL_TYPES:
                try:
                    pre = native["pred"][str(day)][animal][cell_type]
                    act = native["actual"][str(day)][animal][cell_type]
                    recorded = native["scores"][str(day)][animal][cell_type]
                    shuffled = native["scores_shuffle"][str(day)][animal][cell_type]
                    sample_map = support[str(day)][animal]
                except (KeyError, TypeError):
                    raise InputError("missing native session/cell arrays or exact sample support") from None
                exact(pre, MODELS, "native predicted models")
                exact(act, MODELS, "native actual models")
                require(isinstance(recorded, list) and len(recorded) == 5, "native scores shape must be [5,10]")
                require(isinstance(shuffled, list) and len(shuffled) == 100, "native shuffle shape must be [100,10,5]")
                for repeat in shuffled:
                    require(isinstance(repeat, list) and len(repeat) == 10, "native shuffle shape must be [100,10,5]")
                    for fold in repeat:
                        vector(fold, 5, "native shuffle model axis")
                for model_index, model in enumerate(MODELS):
                    try:
                        require(isinstance(pre[model], list) and len(pre[model]) == 10 and
                                isinstance(act[model], list) and len(act[model]) == 10 and
                                isinstance(sample_map[model], list) and len(sample_map[model]) == 10,
                                "native prediction/target/support requires ten folds")
                        folds = [{"sample_ids": sample_map[model][i], "actual": act[model][i],
                                  "predicted": pre[model][i]} for i in range(10)]
                    except (KeyError, TypeError):
                        raise InputError("missing native model arrays or fold IDs") from None
                    rows.append({"animal": animal, "day": day, "cell_type": cell_type,
                                 "model": model, "folds": folds,
                                 "shuffle_scores": [[shuffled[j][i][model_index] for i in range(10)]
                                                    for j in range(100)]})
    panel = {"schema": SCHEMA, "source_commit": COMMIT, "preparation_sha256": preparation_sha256,
             "fold_receipt_sha256": fold_receipt_sha256, "rows": rows}
    scores = _validate(panel)
    for row in rows:
        recorded = native["scores"][str(row["day"])][row["animal"]][row["cell_type"]][MODELS.index(row["model"])]
        recorded = vector(recorded, 10, "native real fold scores")
        calculated = scores[row["animal"], row["day"], row["cell_type"], row["model"]]["fold_scores"]
        require(all(math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10) for a, b in zip(recorded, calculated)),
                "native stored scores disagree with recomputed cosine fold scores")
    return panel


def _pairs(items):
    out = {}
    for key, value in items:
        require(key not in out, "duplicate JSON key")
        out[key] = value
    return out


def read_json(path):
    def reject(value):
        raise InputError("nonfinite JSON constant: " + value)
    return json.loads(Path(path).read_text(), object_pairs_hook=_pairs, parse_constant=reject)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    score = sub.add_parser("score")
    score.add_argument("--panel", required=True)
    paired = sub.add_parser("compare")
    paired.add_argument("--candidate", required=True)
    paired.add_argument("--author", required=True)
    export = sub.add_parser("export-native")
    export.add_argument("--native", required=True)
    export.add_argument("--support", required=True)
    export.add_argument("--preparation-sha256", required=True)
    export.add_argument("--fold-receipt-sha256", required=True)
    for command in (score, paired, export):
        command.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if args.command == "score":
            result = score_panel(read_json(args.panel))
        elif args.command == "compare":
            result = compare(read_json(args.candidate), read_json(args.author))
        else:
            result = export_native(read_json(args.native), read_json(args.support),
                                   args.preparation_sha256, args.fold_receipt_sha256)
        # Exclusive output creation avoids overwriting frozen owner evidence.
        with Path(args.output).open("x") as handle:
            json.dump(result, handle, indent=2, allow_nan=False)
            handle.write("\n")
    except (InputError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    main()
