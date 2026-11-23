"""Recompute five-variant Allen likelihood components from declared native batches.

These are diagnostic components for original-endpoint reconciliation, not a
Table S1 score, a source-membership audit, or a scientific admission decision.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import re
import zipfile

import numpy as np

TASK_ID = "PAPER-paper-method-018"
SOURCE_COMMIT = "421b5eef321cac3d1c1279759e0f6b638068b021"
SESSION_IDS = ("757216464", "798911424", "715093703", "719161530", "721123822",
               "737581020", "739448407", "742951821", "743475441", "744228101")
VARIANTS = ("full_model", "bidirectional_rnn_encoder", "no_trial_wise_latent",
            "no_coupling", "no_post_spike_history")
INFERENCE_POLICY = "posterior_mean_where_present_target_conditioned_reconstruction"
TERMS = ("poisson_without_constant_sum", "log_factorial_sum", "poisson_with_constant_sum")


class ComponentError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ComponentError(message)


def keys(value, expected, name):
    require(isinstance(value, dict) and set(value) == set(expected),
            f"{name}: expected exactly {sorted(expected)}")


def ids(value, name):
    require(isinstance(value, list) and value and
            all(isinstance(x, str) and x for x in value), f"{name}: nonempty string ID list required")
    require(len(value) == len(set(value)), f"{name}: duplicate IDs")
    return value


def digest(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value),
            "lowercase SHA-256 required")


def read_manifest(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def nonfinite(value):
        raise ComponentError(f"nonfinite JSON constant: {value}")

    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ComponentError("invalid component manifest") from exc
    return value, hashlib.sha256(raw).hexdigest()


def read_array(root, record, key):
    keys(record, {"path", "sha256"}, "artifact")
    digest(record["sha256"])
    require(isinstance(record["path"], str) and record["path"], "artifact path required")
    relative = Path(record["path"])
    require(not relative.is_absolute() and ".." not in relative.parts, "unconfined artifact path")
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()) and path.is_file(), "missing or unconfined artifact")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == record["sha256"], "artifact digest mismatch")
    try:
        with np.load(io.BytesIO(raw), allow_pickle=False) as bundle:
            require(bundle.files == [key], f"NPZ must contain only {key}")
            array = bundle[key]
    except (ValueError, OSError, TypeError, EOFError, zipfile.BadZipFile) as exc:
        raise ComponentError(f"cannot decode numeric {key} artifact") from exc
    require(array.dtype.kind in "iuf" and np.isfinite(array).all(),
            f"{key}: finite real numeric array required")
    return array


def likelihood_components(counts, log_rate):
    """Sum Poisson terms on T,N,R support, with log expected counts per 2-ms bin.

    No KL, training penalty, observation normalization or run averaging is folded
    into these terms. Their relationship to the historical Table S1 total is open.
    """
    counts, log_rate = np.asarray(counts), np.asarray(log_rate)
    for name, array in (("counts", counts), ("log_rate", log_rate)):
        require(array.dtype.kind in "iuf" and np.isfinite(array).all(),
                f"{name}: finite real numeric array required")
    require(counts.ndim == 3 and all(counts.shape), "counts: nonempty T,N,R array required")
    require(log_rate.shape == counts.shape, "log_rate: shape mismatch")
    require((counts >= 0).all() and (counts == np.floor(counts)).all() and
            (counts <= 2**53).all(), "counts: exact nonnegative integer counts required")
    y, eta = counts.astype(np.float64), log_rate.astype(np.float64)
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            poisson = np.exp(eta) - y * eta
        without = math.fsum(float(x) for x in poisson.flat)
        constant = math.fsum(math.lgamma(float(x) + 1) for x in y.flat)
        with_constant = without + constant
        require(all(math.isfinite(x) for x in (without, constant, with_constant)),
                "likelihood aggregation is not finite")
    except (FloatingPointError, OverflowError, ValueError) as exc:
        raise ComponentError("invalid likelihood arithmetic; no clipping applied") from exc
    return dict(zip(TERMS, (without, constant, with_constant)))


def collect(manifest_path):
    path = Path(manifest_path).resolve()
    manifest, manifest_sha = read_manifest(path)
    keys(manifest, {"schema_version", "task_id", "source_commit", "run_id", "inference_policy",
                    "bin_width_seconds", "sessions"}, "manifest")
    require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1 and
            manifest["task_id"] == TASK_ID and manifest["source_commit"] == SOURCE_COMMIT,
            "wrong schema, task or source pin")
    require(isinstance(manifest["run_id"], str) and manifest["run_id"], "run_id required")
    require(manifest["inference_policy"] == INFERENCE_POLICY, "wrong inference policy")
    require(type(manifest["bin_width_seconds"]) in (int, float) and
            manifest["bin_width_seconds"] == 0.002, "paper bin width must be 0.002 seconds")
    sessions = manifest["sessions"]
    require(isinstance(sessions, list) and len(sessions) == len(SESSION_IDS), "all ten sessions required")
    require(all(isinstance(s, dict) and isinstance(s.get("session_id"), str) for s in sessions),
            "session records must have string IDs")
    by_id = {s["session_id"]: s for s in sessions}
    require(set(by_id) == set(SESSION_IDS), "missing, duplicate or unknown session")
    results = []
    for sid in SESSION_IDS:
        session = by_id[sid]
        keys(session, {"session_id", "neuron_ids", "time_bin_indices", "train_trial_ids",
                       "validation_trial_ids", "test_trial_ids", "model_runs", "batches"}, "session")
        neurons = ids(session["neuron_ids"], "neuron_ids")
        partitions = [ids(session[k], k) for k in ("train_trial_ids", "validation_trial_ids", "test_trial_ids")]
        all_trials = [trial for partition in partitions for trial in partition]
        require(len(all_trials) == len(set(all_trials)), "training/validation/test trial overlap")
        bins = session["time_bin_indices"]
        require(isinstance(bins, list) and bins and all(type(x) is int and x >= 0 for x in bins),
                "nonnegative integer time-bin indices required")
        require(bins == list(range(bins[0], bins[0] + len(bins))), "contiguous ordered time bins required")
        keys(session["model_runs"], VARIANTS, "model_runs")
        for variant, provenance in session["model_runs"].items():
            keys(provenance, {"checkpoint_sha256", "recipe_sha256", "model_stage"}, variant)
            digest(provenance["checkpoint_sha256"])
            digest(provenance["recipe_sha256"])
            require(isinstance(provenance["model_stage"], str) and provenance["model_stage"], "model stage required")
        batches = session["batches"]
        require(isinstance(batches, list) and batches, "native test batches required")
        ordered_trials, batch_results = [], []
        for batch in batches:
            keys(batch, {"trial_ids", "counts", "predictions"}, "batch")
            trials = ids(batch["trial_ids"], "batch trial IDs")
            ordered_trials.extend(trials)
            keys(batch["predictions"], VARIANTS, "predictions")
            counts = read_array(path.parent, batch["counts"], "counts")
            require(counts.shape == (len(bins), len(neurons), len(trials)), "counts do not match native axes")
            variants = {}
            for variant in VARIANTS:
                log_rate = read_array(path.parent, batch["predictions"][variant], "log_rate")
                variants[variant] = likelihood_components(counts, log_rate)
            batch_results.append({"trial_ids": trials, "observation_count": int(counts.size),
                                  "counts_sha256": batch["counts"]["sha256"],
                                  "predictions_sha256": {v: batch["predictions"][v]["sha256"] for v in VARIANTS},
                                  "variants": variants})
        require(ordered_trials == session["test_trial_ids"], "batches must exhaust ordered test trials exactly")
        totals = {}
        try:
            for variant in VARIANTS:
                totals[variant] = {term: math.fsum(b["variants"][variant][term] for b in batch_results)
                                   for term in TERMS}
                require(all(math.isfinite(x) for x in totals[variant].values()), "nonfinite session total")
        except OverflowError as exc:
            raise ComponentError("session likelihood total overflow") from exc
        results.append({"session_id": sid, "neuron_ids": neurons, "time_bin_indices": bins,
                        "model_runs": session["model_runs"], "batches": batch_results,
                        "observation_count": sum(b["observation_count"] for b in batch_results),
                        "declared_session_totals": totals})
    return {"schema_version": 1, "task_id": TASK_ID, "run_id": manifest["run_id"],
            "manifest_sha256": manifest_sha, "source_commit": SOURCE_COMMIT,
            "status": "original_endpoint_likelihood_components_only", "scientifically_qualified": False,
            "full_contract_complete": False, "paper_score": None, "paper_standard_error": None,
            "inference_policy": INFERENCE_POLICY, "bin_width_seconds": 0.002, "sessions": results,
            "limits": ["Declared support, model stages, recipes and checkpoints are not independently authenticated.",
                       "Historical Table S1 total/constant/KL/penalty convention and run aggregation remain unresolved.",
                       "No cross-session or cross-run score, standard error, acceptance threshold or paired improvement is inferred.",
                       "This does not verify coupling/dynamics outputs or complete-family reproduction."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = collect(args.manifest)
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write("\n")
    except (ComponentError, OSError) as exc:
        parser.exit(2, f"components rejected: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
