#!/usr/bin/env python3
"""Replay the pinned author's Poisson score; never fit or regenerate folds."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

SOURCE_COMMIT = "130f5e64f86bd63980f70bb839c02cd264782aef"
SOURCE_CLASS_SHA256 = "eb712ad14d1b9465ddbaa84c460657eac9cfa7f3f7772212c3fdcbd543287ded"


class ReplayError(ValueError):
    """Invalid source export or mismatched comparison support."""


def require(condition, message):
    if not condition:
        raise ReplayError(message)


def number(value, label, positive=False, integer=False):
    require(type(value) in (int, float) and math.isfinite(value), label + " must be finite numeric")
    require(not positive or value > 0, label + " must be positive")
    require(not integer or value == int(value), label + " must be integral")
    return value


def vector(value, label, positive=False, integer=False):
    require(isinstance(value, list) and bool(value), label + " must be a nonempty vector")
    return [number(x, label, positive, integer) for x in value]


def unique_indices(value, label):
    result = vector(value, label, positive=True, integer=True)
    require(len(result) == len(set(result)), label + " contains duplicates")
    # JSON has one number category: admitted integral floats such as 1.0
    # must become Python indices before indexing the unchanged source arrays.
    return [int(index) for index in result]


def identity(cell):
    require(isinstance(cell, dict), "cell must be an object")
    key = (cell.get("monkey"), cell.get("cell_id"))
    require(all(isinstance(x, str) and x.strip() for x in key), "missing animal/cell identity")
    return key


def poisson_log_likelihood(target, means):
    """Author's sum(-mu + y*log(mu) - gammaln(y+1)), in nats.

    Positive finite means are the finite exp(XW) domain. Zero is rejected,
    including y=0, because the literal source expression gives NaN there.
    """
    counts = vector(target, "target", integer=True)
    expected = vector(means, "prediction", positive=True)
    require(all(y >= 0 for y in counts), "target must be nonnegative")
    require(len(counts) == len(expected), "target/prediction length mismatch")
    terms = [-mu + y * math.log(mu) - math.lgamma(y + 1) for y, mu in zip(counts, expected)]
    require(all(math.isfinite(x) for x in terms), "nonfinite likelihood term")
    try:
        result = math.fsum(terms)
    except OverflowError as exc:
        raise ReplayError("nonfinite likelihood sum") from exc
    require(math.isfinite(result), "nonfinite likelihood sum")
    return result


def close(actual, expected):
    return math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-8)


def support_sha256(cell):
    fields = ("monkey", "cell_id", "bin_ms", "selected_source_trial_indices",
              "source_trial_numbers", "trial_index_by_bin")
    data = {key: cell[key] for key in fields}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def replay_cell(cell):
    key = identity(cell)
    number(cell["bin_ms"], "bin_ms", positive=True)
    selected = unique_indices(cell["selected_source_trial_indices"], "selected source trial indices")
    require(selected == sorted(selected), "source selected trial indices must preserve order")
    trial_numbers = vector(cell["source_trial_numbers"], "source trial numbers", integer=True)
    require(len(trial_numbers) == len(set(trial_numbers)), "duplicate source trial numbers")
    require(len(selected) == len(trial_numbers), "trial mapping length mismatch")
    trial_x = vector(cell["trial_index_by_bin"], "trial_index_by_bin", positive=True, integer=True)
    require(trial_x == sorted(trial_x), "source trial bins must be contiguous and ordered")
    require(set(trial_x) == set(range(1, len(selected) + 1)), "missing/extra selected trial bins")
    target = vector(cell["target_counts"], "target_counts", integer=True)
    require(len(target) == len(trial_x), "source target/bin mapping length mismatch")
    base_ll = poisson_log_likelihood(target, cell["unspecialized_prediction_means"])
    recorded_base_nll = number(cell["unspecialized_cv2_neg_log_likelihood"], "source base cv2NegLnL")
    require(close(-base_ll, recorded_base_nll), "unspecialized cv2NegLnL does not replay")
    require(type(cell["unspecialized_cv_train_sel_present"]) is bool, "fold presence must be boolean")
    require(type(cell["bias_column_present"]) is bool, "bias column presence must be boolean")

    leaves = cell["hierarchical_leaves"]
    require(isinstance(leaves, list) and leaves, "missing final hierarchy")
    joint = [None] * len(target)
    leaf_reports = []
    for ordinal, leaf in enumerate(leaves, 1):
        trials = unique_indices(leaf["trial_indices"], "leaf trial indices")
        bins = unique_indices(leaf["bin_indices"], "leaf bin indices")
        require(set(trials) <= set(trial_x), "leaf contains unknown trial")
        trial_set = set(trials)
        expected_bins = [i + 1 for i, trial in enumerate(trial_x) if trial in trial_set]
        require(bins == expected_bins, "leaf bins must equal complete source trials in source order")
        leaf_target = leaf["target_counts"]
        leaf_ll = poisson_log_likelihood(leaf_target, leaf["prediction_means"])
        require(leaf_target == [target[i - 1] for i in bins], "leaf target differs from original support")
        for index, mu in zip(bins, leaf["prediction_means"]):
            require(joint[index - 1] is None, "overlapping hierarchical leaf support")
            joint[index - 1] = mu
        raw_nll = number(leaf["reported_cv2_neg_log_likelihood"], "leaf reported cv2NegLnL")
        inherited = leaf["fit_info_equals_progenitor"]
        fold_present = leaf["cv_train_sel_present"]
        require(type(inherited) is bool and type(fold_present) is bool, "leaf provenance flags must be boolean")
        matches = close(-leaf_ll, raw_nll)
        require(matches or inherited, "leaf cv2NegLnL mismatch without identical progenitor fitInfo")
        leaf_reports.append({"leaf_ordinal": ordinal, "n_bins": len(bins), "n_trials": len(trials),
                             "log_likelihood_nats": leaf_ll, "reported_cv2_neg_log_likelihood": raw_nll,
                             "reported_cv2_matches_leaf_support": matches,
                             "fit_info_equals_progenitor": inherited,
                             "cv_train_sel_present": fold_present})
    require(all(mu is not None for mu in joint), "incomplete final hierarchy support")
    final_ll = poisson_log_likelihood(target, joint)
    native_ll = number(cell["native_joint_log_likelihood"], "native joint score")
    require(close(final_ll, native_ll), "hierarchical native joint likelihood does not replay")
    require(close(final_ll, math.fsum(x["log_likelihood_nats"] for x in leaf_reports)),
            "leaf likelihoods do not sum to joint score")
    return {"monkey": key[0], "cell_id": key[1], "n_trials": len(selected), "n_bins": len(target),
            "bin_ms": cell["bin_ms"], "source_support_sha256": support_sha256(cell),
            "bias_column_present": cell["bias_column_present"],
            "unspecialized_cv_train_sel_present": cell["unspecialized_cv_train_sel_present"],
            "unspecialized_log_likelihood_nats": base_ll,
            "hierarchical_log_likelihood_nats": final_ll,
            "hierarchical_minus_unspecialized_nats": final_ll - base_ll,
            "hierarchical_leaves": leaf_reports}


def replay(document, candidate=None):
    require(document.get("schema") == "dentate-author-score-export-v1", "wrong source schema")
    require(document.get("source_commit") == SOURCE_COMMIT, "wrong source commit")
    require(document.get("source_class_sha256") == SOURCE_CLASS_SHA256, "wrong source class hash")
    cells = document.get("cells")
    require(isinstance(cells, list) and cells, "missing source cells")
    seen = set()
    reports, source_by_key, exclusions = [], {}, []
    for cell in cells:
        key = identity(cell)
        require(key not in seen, "duplicate source cell identity")
        seen.add(key)
        if cell.get("status") == "unfitted":
            require(cell.get("reason") == "source_unspecialized_model_is_experiment_struct",
                    "unrecognized source exclusion")
            exclusions.append({"monkey": key[0], "cell_id": key[1], "reason": cell["reason"]})
            continue
        require(cell.get("status") == "fitted", "unknown source cell status")
        require(cell.get("source_n_cv_folds") == 5 and type(cell.get("source_n_cv_folds")) is int,
                "source configuration must retain five folds")
        reports.append(replay_cell(cell))
        source_by_key[key] = cell
    require(bool(reports), "no fitted cells to replay")

    if candidate is not None:
        require(candidate.get("schema") == "dentate-candidate-means-v1", "wrong candidate schema")
        candidates = candidate.get("cells")
        require(isinstance(candidates, list), "candidate cells must be a list")
        lookup = {}
        for cell in candidates:
            key = identity(cell)
            require(key not in lookup, "duplicate candidate cell")
            lookup[key] = cell
        require(set(lookup) == set(source_by_key), "candidate cohort differs from fitted source cohort")
        for report in reports:
            key = identity(report)
            source, proposed = source_by_key[key], lookup[key]
            require(proposed.get("source_support_sha256") == report["source_support_sha256"],
                    "candidate source support hash mismatch")
            bins = unique_indices(proposed["bin_indices"], "candidate bin indices")
            require(set(bins) == set(range(1, report["n_bins"] + 1)), "candidate bin support mismatch")
            means = vector(proposed["prediction_means"], "candidate means", positive=True)
            require(len(bins) == len(means), "candidate bin/prediction length mismatch")
            by_bin = dict(zip(bins, means))
            candidate_ll = poisson_log_likelihood(source["target_counts"], [by_bin[i] for i in range(1, len(bins) + 1)])
            report["candidate_log_likelihood_nats"] = candidate_ll
            report["candidate_minus_source_hierarchical_nats"] = candidate_ll - report["hierarchical_log_likelihood_nats"]

    return {"schema": "dentate-source-score-replay-report-v1", "source_commit": SOURCE_COMMIT,
            "score_definition": "sum_bins(-mu + y*log(mu) - lgamma(y+1))",
            "prediction_units": "expected_spike_count_per_source_bin", "normalization": "none",
            "cells": reports, "source_unfitted_cells": exclusions,
            "scope": "replay_of_supplied_source_fit_exports_only",
            "cross_cell_score": None, "fold_identity_verified": False,
            "complete_original_cohort_verified": False, "paper_improvement_established": False,
            "qualification": "software_replay_only"}


def _load_json_snapshot(path):
    raw = Path(path).read_bytes()
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON object key: " + key)
            result[key] = value
        return result
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs), hashlib.sha256(raw).hexdigest()


def load_json(path):
    return _load_json_snapshot(path)[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--author-export", required=True)
    parser.add_argument("--candidate")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    inputs = [Path(x).resolve() for x in (args.author_export, args.candidate) if x]
    require(output not in inputs, "output cannot overwrite an input")
    document, author_hash = _load_json_snapshot(inputs[0])
    candidate, candidate_hash = _load_json_snapshot(inputs[1]) if args.candidate else (None, None)
    result = replay(document, candidate)
    result["author_export_sha256"] = author_hash
    if args.candidate:
        result["candidate_file_sha256"] = candidate_hash
    with output.open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
