"""Paper-grounded DPAD Figure 6h-i prediction evaluator; no model execution.

Independently written from the paper's mathematical definitions. See the
companion task documentation for unresolved source and qualification gates.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
from statistics import mean, pstdev

TASK_ID = "PAPER-CANDIDATE-20261114-DPAD"
DIMENSIONS = (1, 2, 4, 8, 16, 32, 64, 128)
# Candidate mapping by source dates, NOT certification of wideband identity.
SESSIONS = ("indy_20160622_01", "indy_20160624_03", "indy_20160627_01",
            "indy_20160630_01", "indy_20160915_01", "indy_20160916_01",
            "indy_20160921_01")
METHODS = ("linear", "only_Aprime", "only_K", "only_Cy", "only_Cz",
           "flexible_decoding", "flexible_prediction")
GATES = (
    "Candidate seven-session mapping not independently verified against wideband inventory",
    "Exact random 32-electrode subset and resulting 77-99 single units not frozen",
    "Historical full preprocessing, temporal purge, runtime and source-version equivalence unresolved",
    "Historical undefined-channel sanitization and Wilcoxon numerical behavior unresolved",
    "Native training, all 90 fitted architectures and inference provenance not executed or verified",
    "Protected targets, original full populations, A/B parity and contamination not verified",
    "Source code USC research/nonprofit terms; commercial permission remains separate",
    "Authentic reproduction, prospective improvement and scientific qualification unknown",
)


class ContractError(ValueError):
    """Malformed, incomplete or scientifically inadmissible evaluation input."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def number(value, context):
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value), context + " must be a finite number")
    return float(value)


def cc_number(value, context):
    result = number(value, context)
    require(-1 <= result <= 1, context + " outside [-1,1]")
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def architecture_grid():
    """The paper's 61 feed-forward plus 29 LSTM cases, with stable local IDs."""
    result = {"linear": {"Aprime": "linear", "nonlinear": [], "layers": 0, "units": 0}}
    loci = ("Aprime", "K", "Cy", "Cz")
    for size in range(1, 5):
        for subset in itertools.combinations(loci, size):
            for layers, units in itertools.product((1, 2), (64, 128)):
                key = "+".join(subset) + f":{layers}x{units}"
                result[key] = {"Aprime": "feedforward" if "Aprime" in subset else "linear",
                               "nonlinear": list(subset), "layers": layers, "units": units}
    result["LSTM:linear-readouts"] = {"Aprime": "LSTM", "nonlinear": [], "layers": 0, "units": 0}
    for size in range(1, 4):
        for subset in itertools.combinations(loci[1:], size):
            for layers, units in itertools.product((1, 2), (64, 128)):
                key = "LSTM+" + "+".join(subset) + f":{layers}x{units}"
                result[key] = {"Aprime": "LSTM", "nonlinear": list(subset), "layers": layers, "units": units}
    return result


ARCHITECTURES = architecture_grid()
FIXED = {"linear": "linear", **{"only_" + p: p + ":1x64" for p in ("Aprime", "K", "Cy", "Cz")}}


def matrix(value, context, allow_missing=False):
    require(isinstance(value, list) and len(value) >= 2, context + " needs at least two rows")
    require(isinstance(value[0], list) and value[0], context + " needs channels")
    width = len(value[0])
    result = []
    for row in value:
        require(isinstance(row, list) and len(row) == width, context + " is ragged")
        result.append([None if v is None and allow_missing else number(v, context) for v in row])
    return result


def channel_cc(truth, prediction):
    """Strict full-coverage per-channel Pearson. Undefined channels remain null.

    Unlike source evaluateDecoding, this boundary rejects missing/nonfinite
    predictions instead of silently removing their rows. This is an explicitly
    prospective admission rule to prevent selective omission of hard samples.
    """
    truth, prediction = matrix(truth, "truth"), matrix(prediction, "prediction")
    require(len(truth) == len(prediction) and len(truth[0]) == len(prediction[0]), "prediction shape mismatch")
    values = []
    for x, y in zip(zip(*truth), zip(*prediction)):
        # Center then scale to avoid needless overflow in a sum of squares.
        scale_x, scale_y = max(map(abs, x)), max(map(abs, y))
        x = [v / scale_x for v in x] if scale_x else x
        y = [v / scale_y for v in y] if scale_y else y
        mx, my = mean(x), mean(y)
        dx, dy = [v - mx for v in x], [v - my for v in y]
        sx, sy = max(map(abs, dx)), max(map(abs, dy))
        if sx == 0 or sy == 0:
            values.append(None)
            continue
        dx, dy = [v / sx for v in dx], [v / sy for v in dy]
        denom = math.sqrt(math.fsum(v*v for v in dx) * math.fsum(v*v for v in dy))
        value = math.fsum(a*b for a, b in zip(dx, dy)) / denom
        values.append(max(-1.0, min(1.0, value)))
    return {"per_channel": values,
            "mean_cc": mean(values) if all(v is not None for v in values) else None,
            "undefined_channels": [i for i, v in enumerate(values) if v is None],
            "sample_count": len(truth)}


def choose_dimension(curve):
    """Larger of the smallest training neural/behavior peak dimensions."""
    require(set(curve) == set(DIMENSIONS), "incomplete dimension curve")
    peaks = []
    for metric in ("training_neural_cc", "training_behavior_cc"):
        scores = {d: cc_number(curve[d][metric], metric) for d in DIMENSIONS}
        peak = max(scores.values())
        peaks.append(min(d for d in DIMENSIONS if scores[d] == peak))
    return max(peaks)


def choose_architecture(candidates, focus):
    """Two-fold, within-one-SEM architecture selection from the full 90 grid.

    Population-SD SEM follows the pinned current source helper; lexicographic
    exact ties are a declared choice. Historical runtime equivalence is open.
    """
    require(set(candidates) == set(ARCHITECTURES), "incomplete 90-architecture grid")
    require(focus in ("decoding", "prediction"), "invalid architecture focus")
    metrics = {}
    for key, row in candidates.items():
        metrics[key] = {}
        for field in ("inner_neural_cc", "inner_behavior_cc"):
            require(isinstance(row[field], list) and len(row[field]) == 2, "two inner folds required")
            vals = [cc_number(x, field) for x in row[field]]
            metrics[key][field] = (mean(vals), pstdev(vals) / math.sqrt(2))
    main = "inner_behavior_cc" if focus == "decoding" else "inner_neural_cc"
    other = "inner_neural_cc" if focus == "decoding" else "inner_behavior_cc"
    # Pinned isWithin1SEMOfTheBest uses the maximum lower SEM bound over
    # candidates, not the lower bound of only the highest raw-mean candidate.
    threshold = max(metrics[k][main][0] - metrics[k][main][1] for k in candidates)
    eligible = [k for k in candidates if metrics[k][main][0] >= threshold]
    selected = min(eligible, key=lambda k: (-metrics[k][other][0], k))
    return selected


def protocol(value):
    require(value["task_id"] == TASK_ID, "wrong task ID")
    require(value["profile"] in ("historical_symmetric", "prospective_causal"), "unknown preprocessing profile")
    require(value["reference_kind"] in ("generated_engineering_control", "owner_supplied_unverified"), "reference kind cannot assert qualification")
    require(value["sessions"] == list(SESSIONS), "candidate seven-session roster mismatch")
    require(value["dimensions"] == list(DIMENSIONS), "state grid mismatch")
    require(value["folds"] == [1, 2, 3, 4, 5], "all five outer folds required")
    for field in ("filter_past_support_samples", "filter_future_support_samples", "purge_samples"):
        require(type(value[field]) is int and value[field] >= 0, "invalid filter/purge support")
    if value["profile"] == "prospective_causal":
        require(value["filter_future_support_samples"] == 0, "causal profile cannot use future smoothing")
    require(type(value["neural_lag_samples"]) is int and value["neural_lag_samples"] >= 1,
            "one-step-ahead inference needs past neural observations")
    require(value["held_behavior_used"] is False, "held behavior cannot be an inference input")
    sizes = value["session_sample_counts"]
    require(set(sizes) == set(SESSIONS), "missing session sizes")
    for s, n in sizes.items():
        require(type(n) is int and n >= 10 and n % 5 == 0, "equal continuous fold profile requires sample count divisible by five")
    require(set(value["animal_ids"]) == set(SESSIONS) and all(value["animal_ids"][s] == "indy" for s in SESSIONS), "candidate roster belongs to animal indy")
    return value


def held_ids(p, session, fold):
    width = p["session_sample_counts"][session] // 5
    return list(range((fold - 1)*width, fold*width))


def check_provenance(p, entry):
    s, fold = entry["session_id"], entry["fold"]
    require(s in SESSIONS and type(fold) is int and fold in range(1, 6), "unknown session/fold")
    n = p["session_sample_counts"][s]
    held = held_ids(p, s, fold)
    for field in ("fit_sample_ids", "selection_sample_ids"):
        ids = entry[field]
        require(isinstance(ids, list) and ids and all(type(x) is int and 0 <= x < n for x in ids)
                and len(ids) == len(set(ids)), field + " has invalid or duplicate sample IDs")
        require(not set(ids).intersection(held), "held samples used in " + field)
        if p["profile"] == "prospective_causal":
            # A training sample's full preprocessing support cannot touch test,
            # and the declared additional purge is applied on both sides.
            lo = held[0] - p["filter_future_support_samples"] - p["purge_samples"]
            hi = held[-1] + p["filter_past_support_samples"] + p["purge_samples"]
            require(all(x < lo or x > hi for x in ids), "training/filter support overlaps protected block")
    return (s, fold)


def select(training):
    """Freeze a plan using train-only metadata, before loading held targets."""
    p = protocol(training["protocol"])
    rows = {}
    for entry in training["cases"]:
        key = check_provenance(p, entry)
        require(key not in rows, "duplicate training session/fold")
        dimensions = entry["dimensions"]
        require(set(dimensions) == set(map(str, DIMENSIONS)), "missing training dimensions")
        for candidates in dimensions.values():
            require(set(candidates) == set(ARCHITECTURES), "missing architecture candidates")
            for candidate in candidates.values():
                for f in ("training_neural_cc", "training_behavior_cc"):
                    cc_number(candidate[f], f)
        method_rows = {}
        for method in METHODS:
            curve, architecture_by_dimension = {}, {}
            for d in DIMENSIONS:
                candidates = dimensions[str(d)]
                if method in FIXED:
                    selected = FIXED[method]
                else:
                    selected = choose_architecture(candidates, method.removeprefix("flexible_"))
                curve[d] = candidates[selected]
                architecture_by_dimension[str(d)] = selected
            dim = choose_dimension(curve)
            method_rows[method] = {"selected_dimension": dim, "n1": min(16, dim),
                                   "architectures": architecture_by_dimension,
                                   "selection_curve": {str(d): {k: curve[d][k] for k in ("training_neural_cc", "training_behavior_cc")} for d in DIMENSIONS}}
        rows[key] = {"session_id": key[0], "fold": key[1], "methods": method_rows}
    require(set(rows) == set(itertools.product(SESSIONS, range(1, 6))), "incomplete 35 session-folds")
    return {"schema": "dpad-selection-v1", "protocol": p, "training_sha256": digest(training),
            "cases": [rows[k] for k in sorted(rows)], "scientific_qualification": "unknown", "gates": list(GATES)}


def signed_rank_greater(a, b):
    """Exact conditional sign-permutation Wilcoxon tail, with average ties.

    Zeros are removed (Wilcox convention). Integer doubled ranks permit an
    exact DP tail for ties; no SciPy/runtime-dependent auto approximation.
    """
    require(len(a) == len(b) and len(a) > 0, "unpaired signed-rank vectors")
    differences = [number(x, "paired score") - number(y, "paired score") for x, y in zip(a, b)]
    differences = sorted((d for d in differences if d != 0), key=abs)
    if not differences:
        return 1.0
    ranks, i = [], 0
    while i < len(differences):
        j = i + 1
        while j < len(differences) and abs(differences[j]) == abs(differences[i]):
            j += 1
        rank2 = i + 1 + j
        ranks.extend((rank2, differences[k] > 0) for k in range(i, j))
        i = j
    observed = sum(r for r, positive in ranks if positive)
    counts = {0: 1}
    for rank, _ in ranks:
        next_counts = dict(counts)
        for total, count in counts.items():
            next_counts[total + rank] = next_counts.get(total + rank, 0) + count
        counts = next_counts
    return sum(count for total, count in counts.items() if total >= observed) / 2**len(ranks)


def summary(values):
    require(values and all(v is not None for v in values), "undefined score cannot be omitted")
    return {"mean": mean(values), "sem": pstdev(values)/math.sqrt(len(values)) if len(values) > 1 else None, "n": len(values)}


def frontier(vectors):
    """Source-defined two-metric rule; statistical runtime is labelled."""
    methods = sorted(vectors)
    pairwise, on = [], []
    for a in methods:
        admitted = True
        for b in methods:
            if a == b:
                continue
            better, worse, metrics = False, False, {}
            for metric in ("neural_cc", "behavior_cc"):
                av, bv = vectors[a][metric], vectors[b][metric]
                ma, mb = mean(av), mean(bv)
                # Source code uses comparator mean as denominator. At zero,
                # nonzero differences satisfy the relative-effect threshold.
                effect = abs(ma-mb) >= .01 * abs(mb) and ma != mb
                pg, pl = signed_rank_greater(av, bv), signed_rank_greater(bv, av)
                # Signed ranks determine direction; the relative mean change
                # is an absolute effect-size gate, not a second direction test.
                win, loss = effect and pg <= .05, effect and pl <= .05
                better, worse = better or win, worse or loss
                metrics[metric] = {"p_greater": pg, "p_less": pl, "mean_delta": ma-mb,
                                   "relative_effect_pass": effect, "better": win, "worse": loss}
            admitted = admitted and not (worse and not better)
            pairwise.append({"method": a, "comparator": b, "metrics": metrics})
        if admitted:
            on.append(a)
    return {"methods": on, "pairwise": pairwise,
            "inference_unit": "35 session-fold pairs; dependent folds reproduce paper reporting unit",
            "numerical_profile": "exact conditional sign permutation; average ties; zero differences removed; population-SD SEM",
            "historical_numerical_equivalence": "unverified"}


def evaluate(targets, predictions, plan):
    p = protocol(targets["protocol"])
    require(predictions["protocol"] == p and plan["protocol"] == p, "protocol drift between artifacts")
    require(plan["schema"] == "dpad-selection-v1", "wrong selection plan")
    require(predictions["selection_plan_sha256"] == digest(plan), "predictions not bound to frozen selection plan")
    expected_folds = set(itertools.product(SESSIONS, range(1, 6)))
    target_rows, plan_rows = {}, {}
    for row in targets["cases"]:
        key = (row["session_id"], row["fold"])
        require(type(row["fold"]) is int, "fold must be integer")
        require(key in expected_folds and key not in target_rows, "duplicate or unknown protected target fold")
        require(all(type(x) is int for x in row["sample_ids"]), "sample IDs must be integers")
        require(row["sample_ids"] == held_ids(p, *key), "target samples do not cover full temporal block")
        for field in ("neural", "behavior"):
            require(len(matrix(row[field], field)) == len(row["sample_ids"]), "target row alignment mismatch")
        target_rows[key] = row
    for row in plan["cases"]:
        key = (row["session_id"], row["fold"])
        require(type(row["fold"]) is int, "fold must be integer")
        require(key in expected_folds and key not in plan_rows, "duplicate or unknown plan fold")
        require(set(row["methods"]) == set(METHODS), "missing plan methods")
        for method, method_row in row["methods"].items():
            require(method_row["selected_dimension"] == choose_dimension({int(k): v for k, v in method_row["selection_curve"].items()}), "plan dimension changed after selection")
            require(type(method_row["selected_dimension"]) is int and type(method_row["n1"]) is int
                    and method_row["n1"] == min(16, method_row["selected_dimension"]), "plan n1 differs from paper profile")
            require(set(method_row["architectures"]) == set(map(str, DIMENSIONS)), "plan architectures incomplete")
            require(all(v in ARCHITECTURES for v in method_row["architectures"].values()), "unknown architecture")
            if method in FIXED:
                require(all(v == FIXED[method] for v in method_row["architectures"].values()), "fixed-method architecture changed")
        plan_rows[key] = row
    require(set(target_rows) == expected_folds and set(plan_rows) == expected_folds, "missing protected or plan folds")
    all_scores = {}
    for row in predictions["cases"]:
        key = (row["session_id"], row["fold"])
        method, dimension = row["method"], row["dimension"]
        require(type(row["fold"]) is int and all(type(x) is int for x in row["sample_ids"]), "fold/sample IDs must be integers")
        require(key in expected_folds and method in METHODS and type(dimension) is int and dimension in DIMENSIONS, "unknown prediction key")
        full_key = (*key, method, dimension)
        require(full_key not in all_scores, "duplicate prediction key")
        target, chosen = target_rows[key], plan_rows[key]["methods"][method]
        require(row["sample_ids"] == target["sample_ids"], "prediction sample alignment/coverage mismatch")
        require(row["architecture"] == chosen["architectures"][str(dimension)], "prediction architecture differs from frozen plan")
        metrics = {field: channel_cc(target[field], row[field]) for field in ("neural", "behavior")}
        require(all(v["mean_cc"] is not None for v in metrics.values()), "undefined CC: explicit source channel policy required; no omission allowed")
        all_scores[full_key] = {"session_id": key[0], "fold": key[1], "method": method,
                                "dimension": dimension, "architecture": row["architecture"], **metrics}
    expected = set(itertools.product(SESSIONS, range(1, 6), METHODS, DIMENSIONS))
    require(set(all_scores) == expected, "incomplete held prediction grid; all 1960 cases required")
    selected = [all_scores[(s, f, m, plan_rows[(s, f)]["methods"][m]["selected_dimension"])]
                for s, f, m in itertools.product(SESSIONS, range(1, 6), METHODS)]
    vectors = {m: {metric + "_cc": [row[metric]["mean_cc"] for row in selected if row["method"] == m]
                   for metric in ("neural", "behavior")} for m in METHODS}
    session_summary = [{"session_id": s, "animal_id": p["animal_ids"][s], "method": m,
                        **{metric + "_cc": summary([r[metric]["mean_cc"] for r in selected if r["session_id"] == s and r["method"] == m])
                           for metric in ("neural", "behavior")}}
                       for s, m in itertools.product(SESSIONS, METHODS)]
    return {"schema": "dpad-results-v1", "task_id": TASK_ID, "profile": p["profile"],
            "reference_kind": p["reference_kind"], "selection_plan_sha256": digest(plan),
            "targets_sha256": digest(targets), "predictions_sha256": digest(predictions),
            "all_grid_scores": [all_scores[k] for k in sorted(all_scores)], "selected_scores": selected,
            "session_summary": session_summary,
            "animal_summary": [{"animal_id": "indy", "method": m,
                                 **{metric: summary([r[metric]["mean"] for r in session_summary if r["method"] == m]) for metric in ("neural_cc", "behavior_cc")}}
                               for m in METHODS],
            "paper_unit_summary": {m: {metric: summary(values) for metric, values in vals.items()} for m, vals in vectors.items()},
            "frontier": frontier(vectors), "scientific_qualification": "unknown", "gates": list(GATES),
            "prospective_improvement": "not assessed; whole-session split, matched capacity and noninferiority margin require separate preregistration"}


def read_json(path):
    def reject_constant(value):
        raise ContractError("nonstandard JSON number: " + value)
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON object key: " + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), parse_constant=reject_constant, object_pairs_hook=reject_duplicates)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    selection = sub.add_parser("select", help="freeze choices using training metadata only")
    selection.add_argument("--training", required=True)
    evaluation = sub.add_parser("evaluate", help="score every held prediction and report Figure 6 comparisons")
    for field in ("targets", "predictions", "plan"):
        evaluation.add_argument("--" + field, required=True)
    for command in (selection, evaluation):
        command.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = select(read_json(args.training)) if args.command == "select" else evaluate(read_json(args.targets), read_json(args.predictions), read_json(args.plan))
        Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    except (ContractError, KeyError, TypeError, OSError, json.JSONDecodeError) as error:
        parser.exit(2, "DPAD input rejected: " + str(error) + "\n")


if __name__ == "__main__":
    main()
