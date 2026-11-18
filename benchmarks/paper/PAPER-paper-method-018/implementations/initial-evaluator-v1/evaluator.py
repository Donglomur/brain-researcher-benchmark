"""Prospective matched-ablation scoring for the pinned GLM-Transformer task.

This independent implementation consumes arrays; it neither trains nor imports the
unlicensed author repository. Array order is time, neuron, trial after history padding.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import io
import json
import math
from pathlib import Path
import re
import zipfile
from typing import Any

import numpy as np

TASK_ID = "PAPER-paper-method-018"
SOURCE_COMMIT = "421b5eef321cac3d1c1279759e0f6b638068b021"
CONTRACT_SHA256 = "7032a947b6b9a0a860301d587d81e83ef5b44adc1764654e0074b4cd8e55718f"
SESSION_IDS = ("757216464", "798911424", "715093703", "719161530", "721123822",
               "737581020", "739448407", "742951821", "743475441", "744228101")
ARMS = ("history_only", "interaction_enabled")
INFERENCE_POLICY = "posterior_mean_target_conditioned_reconstruction"
HOLDS = [
    "No authentic Allen payload, preprocessing, checkpoint or native execution has been validated.",
    "Declared full neuron/trial inventory still needs independent raw-data eligibility audit.",
    "Paper 70/10/20 train/test/validation wording conflicts with code 70/10/20 train/validation/test.",
    "Fig5 uses fix_latents arguments absent from pinned model/trainer interfaces.",
    "Pinned batch_first encoder input layout may mix trials; original ordered batch composition and layout reconciliation remain required.",
    "Fig5 includes a test-batch-estimated baseline and disables individual self-history; this recipe does neither.",
    "Table S1 total NLL, Fig5 trial-weighted variational loss, and this prospective endpoint are distinct.",
    "Anatomical membership/condition pickles and their figure subpanels remain unavailable and excluded.",
    "Numerical reproduction targets/tolerances, protected reference, independent improvement panel and resource envelope remain unfrozen.",
    "Author code reuse rights, Allen terms, immutable NWB content hashes and exposure controls remain unresolved.",
    "Predictive reconstruction gain does not establish directed causal biological influence.",
]


class EvaluationError(ValueError):
    """An artifact cannot be evaluated under this recipe."""


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise EvaluationError(message)


def _keys(value: Any, expected: set[str], name: str) -> None:
    _need(isinstance(value, dict) and set(value) == expected,
          f"{name}: expected exactly keys {sorted(expected)}")


def _digest(value: Any, name: str) -> str:
    _need(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
          f"{name}: expected lowercase SHA-256")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_snapshot(path: Path) -> tuple[dict, str]:
    """Parse and commit the same captured bytes, never a later pathname read."""
    def pairs(items):
        result = {}
        for key, value in items:
            _need(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def reject_constant(value):
        raise EvaluationError(f"nonfinite JSON constant: {value}")
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"cannot read manifest {path}: {exc}") from exc
    _need(isinstance(value, dict), "manifest root must be an object")
    return value, hashlib.sha256(raw).hexdigest()


def _json(path: Path) -> dict:
    """Retain the existing parser interface for callers that need no receipt."""
    return _json_snapshot(path)[0]


def _ids(value: Any, name: str, nonempty: bool = True) -> list[str]:
    _need(isinstance(value, list) and (bool(value) or not nonempty),
          f"{name}: expected {'nonempty ' if nonempty else ''}ID list")
    _need(all(isinstance(x, str) and bool(x) for x in value), f"{name}: IDs must be strings")
    _need(len(set(value)) == len(value), f"{name}: duplicate IDs")
    return value


def _number(value: Any, name: str, positive: bool = False) -> float:
    _need(type(value) in (int, float), f"{name}: expected finite number")
    try:
        converted = float(value)
    except (ValueError, OverflowError) as exc:
        raise EvaluationError(f"{name}: number exceeds finite float64 range") from exc
    _need(math.isfinite(converted), f"{name}: expected finite number")
    _need(converted > 0 if positive else converted >= 0, f"{name}: invalid range")
    return converted


def _artifact(base: Path, record: Any, name: str) -> tuple[Path, bytes]:
    _keys(record, {"path", "sha256"}, name)
    _digest(record["sha256"], name)
    _need(isinstance(record["path"], str), f"{name}: path must be string")
    raw = Path(record["path"])
    _need(not raw.is_absolute() and ".." not in raw.parts, f"{name}: expected relative confined path")
    path = (base / raw).resolve()
    _need(path.is_relative_to(base.resolve()) and path.is_file(), f"{name}: missing or unconfined file")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise EvaluationError(f"{name}: cannot capture numeric artifact: {exc}") from exc
    _need(hashlib.sha256(raw).hexdigest() == record["sha256"], f"{name}: content digest mismatch")
    return path, raw


def _arrays(snapshot: tuple[Path, bytes], expected: set[str]) -> dict[str, np.ndarray]:
    """Decode only the NPZ bytes authenticated by _artifact.

    The compressed input snapshot remains in memory during decoding; a pathname
    replacement after capture cannot alter the evaluated observations/predictions.
    This is content binding, not filesystem or process isolation.
    """
    path, raw = snapshot
    try:
        with np.load(io.BytesIO(raw), allow_pickle=False) as bundle:
            _need(set(bundle.files) == expected and len(bundle.files) == len(expected),
                  f"{path.name}: wrong or duplicate array keys")
            result = {key: bundle[key] for key in expected}
    except (ValueError, OSError, TypeError, EOFError, zipfile.BadZipFile) as exc:
        raise EvaluationError(f"cannot read numeric NPZ {path.name}: {exc}") from exc
    for key, array in result.items():
        _need(array.dtype.kind in "iuf" and array.dtype.kind != "b",
              f"{path.name}/{key}: real numeric dtype required")
        _need(np.isfinite(array).all(), f"{path.name}/{key}: nonfinite values")
    return result


def loss_components(counts: np.ndarray, log_rate: np.ndarray,
                    posterior_mu: np.ndarray, posterior_logvar: np.ndarray,
                    beta: float = 1.0) -> dict:
    """Exact pinned-source loss components, plus the full Poisson NLL diagnostic.

    Counts and log_rate are (time, neuron, trial). Posterior arrays are
    (trial, latent_dimension); latent moments need not agree across ablations.
    Natural logs refer to expected counts per bin, not spikes/second.
    """
    counts, log_rate, mu, lv = (np.asarray(x) for x in
                              (counts, log_rate, posterior_mu, posterior_logvar))
    for name, array in (("counts", counts), ("log_rate", log_rate),
                        ("posterior_mu", mu), ("posterior_logvar", lv)):
        _need(array.dtype.kind in "iuf" and np.isfinite(array).all(),
              f"{name}: finite real numeric array required")
    _need(counts.ndim == 3 and all(counts.shape), "counts: expected nonempty T,N,R array")
    _need(log_rate.shape == counts.shape, "log_rate: shape mismatch")
    _need((counts >= 0).all() and (counts == np.floor(counts)).all(),
          "counts: nonnegative integer spike counts required")
    _need((counts <= 2**53).all(), "counts: values exceed exact float64 count range")
    _need(mu.ndim == 2 and mu.shape[0] == counts.shape[2] and mu.shape[1] > 0
          and lv.shape == mu.shape, "posterior: expected matching R,D arrays")
    beta = _number(beta, "beta")
    y, eta = counts.astype(np.float64), log_rate.astype(np.float64)
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            poisson = np.exp(eta) - y * eta
            kl_raw = -0.5 * (1.0 + lv.astype(np.float64) - mu.astype(np.float64)**2
                             - np.exp(lv.astype(np.float64)))
            kl_scaled = float(np.mean(kl_raw) * mu.shape[1] / (y.shape[0] * y.shape[1]))
            poisson_mean = float(np.mean(poisson))
            total = poisson_mean + beta * kl_scaled
            constant = float(np.mean(np.fromiter((math.lgamma(float(n) + 1)
                             for n in y.flat), dtype=np.float64, count=y.size)))
            per_neuron = np.mean(poisson, axis=(0, 2)).tolist()
            spikes = float(np.sum(y))
    except (FloatingPointError, OverflowError, ValueError) as exc:
        raise EvaluationError("loss overflow or invalid arithmetic; no clipping applied") from exc
    _need(all(math.isfinite(v) for v in (kl_scaled, poisson_mean, total, constant, spikes, poisson_mean + constant)),
          "loss aggregation is not finite")
    return {"poisson_nll_without_constant_mean": poisson_mean,
            "poisson_nll_with_constant_mean": poisson_mean + constant,
            "scaled_latent_kl": kl_scaled, "source_variational_loss_mean": total,
            "per_neuron_poisson_nll_without_constant": per_neuron,
            "spike_count": spikes, "observation_count": int(y.size),
            "trial_count": int(y.shape[2])}


def exact_session_sign_flip(gains: list[float]) -> float:
    """Two-sided exact paired-session randomization diagnostic, not qualification."""
    values = np.asarray(gains, dtype=np.float64)
    _need(values.shape == (10,) and np.isfinite(values).all(), "sign flip requires all ten sessions")
    scale = float(np.max(np.abs(values)))
    if scale == 0:
        return 1.0
    values = values / scale
    observed = abs(float(np.sum(values)))
    extreme = sum(abs(float(np.dot(values, signs))) >= observed - 32 * np.finfo(float).eps * float(np.sum(np.abs(values)))
                  for signs in itertools.product((-1, 1), repeat=10))
    return extreme / 1024.0


def _weighted_mean(values: list[float], weights: list[int] | None = None) -> float:
    """Finite convex reduction without overflowing the unnormalized sum."""
    _need(bool(values) and all(math.isfinite(v) for v in values), "nonfinite aggregation input")
    weights = [1] * len(values) if weights is None else weights
    _need(len(weights) == len(values) and all(w > 0 for w in weights), "invalid aggregate weights")
    scale = max(abs(v) for v in values)
    if scale == 0:
        return 0.0
    total_weight = sum(weights)
    ratio = math.fsum((v / scale) * (w / total_weight) for v, w in zip(values, weights))
    return min(1.0, max(-1.0, ratio)) * scale


def _sessions(records: Any, name: str) -> dict[str, dict]:
    _need(isinstance(records, list) and len(records) == 10, f"{name}: all ten sessions required")
    _need(all(isinstance(r, dict) and r.get("session_id") in SESSION_IDS for r in records),
          f"{name}: unknown session")
    result = {r["session_id"]: r for r in records}
    _need(set(result) == set(SESSION_IDS), f"{name}: missing or duplicate session")
    return result


def _validate_reference(reference: dict, root: Path) -> dict[str, dict]:
    _keys(reference, {"schema_version", "task_id", "contract_sha256", "source_commit",
                      "inventory_status", "recipe", "sessions"}, "reference")
    _need(type(reference["schema_version"]) is int and reference["schema_version"] == 1 and reference["task_id"] == TASK_ID,
          "wrong reference schema/task")
    _need(reference["contract_sha256"] == CONTRACT_SHA256 and reference["source_commit"] == SOURCE_COMMIT,
          "wrong canonical contract/source pin")
    _need(reference["inventory_status"] == "operator_frozen_not_independently_native_validated",
          "inventory status must retain native validation hold")
    recipe = reference["recipe"]
    _keys(recipe, {"inference_policy", "include_stimulus", "include_self_history", "use_self_coupling",
                   "beta", "latent_dimension", "bin_width_seconds", "history_padding_bins",
                   "model_capacity_sha256", "training_recipe_sha256", "preprocessing_sha256",
                   "split_policy", "split_frozen_after_final_batch_size"}, "recipe")
    _need(recipe["inference_policy"] == INFERENCE_POLICY, "unsupported inference policy")
    _need(recipe["include_stimulus"] is True and recipe["include_self_history"] is True
          and recipe["use_self_coupling"] is False, "recipe must retain stimulus and neuron history, excluding within-area population coupling")
    _need(recipe["split_policy"] == "operator_frozen_condition_stratified_code_route",
          "unsupported split policy")
    _need(recipe["split_frozen_after_final_batch_size"] is True, "split must be frozen after final batch-size construction")
    _number(recipe["beta"], "beta")
    _number(recipe["bin_width_seconds"], "bin_width_seconds", positive=True)
    for key in ("latent_dimension", "history_padding_bins"):
        _need(type(recipe[key]) is int and recipe[key] > 0, f"{key}: positive integer required")
    for key in ("model_capacity_sha256", "training_recipe_sha256", "preprocessing_sha256"):
        _digest(recipe[key], key)
    sessions = _sessions(reference["sessions"], "reference sessions")
    for sid, record in sessions.items():
        _keys(record, {"session_id", "neuron_ids", "eligible_trial_ids", "train_trial_ids",
                       "validation_trial_ids", "test_trial_ids", "test_batches", "trial_conditions",
                       "time_bin_indices", "counts", "eligibility_receipt_sha256"}, f"reference {sid}")
        _ids(record["neuron_ids"], "neuron_ids")
        eligible = _ids(record["eligible_trial_ids"], "eligible_trial_ids")
        splits = [_ids(record[key], key) for key in ("train_trial_ids", "validation_trial_ids", "test_trial_ids")]
        flattened = [x for part in splits for x in part]
        _need(len(flattened) == len(set(flattened)) and set(flattened) == set(eligible),
              f"{sid}: trial splits must be disjoint and exhaust eligible trials")
        batches = record["test_batches"]
        _need(isinstance(batches, list) and bool(batches), f"{sid}: ordered test batches required")
        batched_trials = [trial for batch in batches for trial in _ids(batch, "test batch")]
        _need(batched_trials == record["test_trial_ids"], f"{sid}: test batches must exhaust ordered test trials exactly")
        conditions = record["trial_conditions"]
        _need(isinstance(conditions, dict) and set(conditions) == set(eligible),
              f"{sid}: condition map must cover every eligible trial")
        groups = {}
        for trial, condition in conditions.items():
            _keys(condition, {"stimulus_name", "stimulus_condition_id"}, "trial condition")
            _need(isinstance(condition["stimulus_name"], str) and condition["stimulus_name"],
                  "stimulus_name must be nonempty string")
            cid = condition["stimulus_condition_id"]
            _need(cid is None or (isinstance(cid, str) and bool(cid)), "invalid stimulus condition ID")
            if condition["stimulus_name"] == "drifting_gratings":
                _need(cid is not None, "drifting gratings require stimulus condition ID")
            group = (condition["stimulus_name"], cid if condition["stimulus_name"] == "drifting_gratings" else None)
            groups.setdefault(group, set()).add(trial)
        for group, trials in groups.items():
            n = len(trials)
            nt, nv = (9, 2) if n == 15 else (int(0.7 * n), int(0.1 * n))
            _need([len(trials.intersection(part)) for part in splits] == [nt, nv, n - nt - nv],
                  f"{sid}: split sizes disagree with pinned loader group {group}")
        bins = record["time_bin_indices"]
        _need(isinstance(bins, list) and bins and all(type(b) is int for b in bins),
              f"{sid}: integer time-bin indices required")
        _need(bins == list(range(recipe["history_padding_bins"], recipe["history_padding_bins"] + len(bins))),
              f"{sid}: scoring requires every contiguous bin after padding")
        _digest(record["eligibility_receipt_sha256"], "eligibility_receipt_sha256")
        _artifact(root, record["counts"], "counts")
    return sessions


def evaluate(reference_path: str | Path, submission_path: str | Path) -> dict:
    reference_path, submission_path = Path(reference_path).resolve(), Path(submission_path).resolve()
    reference, reference_sha256 = _json_snapshot(reference_path)
    submission, submission_sha256 = _json_snapshot(submission_path)
    expected = _validate_reference(reference, reference_path.parent)
    _keys(submission, {"schema_version", "task_id", "reference_sha256", "arms"}, "submission")
    _need(type(submission["schema_version"]) is int and submission["schema_version"] == 1 and submission["task_id"] == TASK_ID, "wrong submission schema/task")
    _need(submission["reference_sha256"] == reference_sha256, "reference digest mismatch")
    _keys(submission["arms"], set(ARMS), "arms")
    arm_sessions = {}
    for arm in ARMS:
        record = submission["arms"][arm]
        _keys(record, {"recipe", "include_coupling", "checkpoint_sha256", "fit_training_partition_sha256",
                       "sessions"}, arm)
        _need(record["recipe"] == reference["recipe"], f"{arm}: unmatched model, preprocessing, training or inference recipe")
        _need(record["include_coupling"] is (arm == "interaction_enabled"), f"{arm}: incorrect coupling flag")
        _digest(record["checkpoint_sha256"], "checkpoint_sha256")
        _need(record["fit_training_partition_sha256"] == partition_digest(reference), f"{arm}: wrong fitting trial partition")
        arm_sessions[arm] = _sessions(record["sessions"], arm)
    _need(submission["arms"][ARMS[0]]["checkpoint_sha256"] != submission["arms"][ARMS[1]]["checkpoint_sha256"],
          "separately fitted ablations require distinct checkpoint artifacts")
    results = []
    for sid in SESSION_IDS:
        ref = expected[sid]
        counts = _arrays(_artifact(reference_path.parent, ref["counts"], "counts"), {"counts"})["counts"]
        _need(counts.shape == (len(ref["time_bin_indices"]), len(ref["neuron_ids"]), len(ref["test_trial_ids"])),
              f"{sid}: counts do not match complete frozen axes")
        metrics = {}
        for arm in ARMS:
            record = arm_sessions[arm][sid]
            _keys(record, {"session_id", "neuron_ids", "test_trial_ids", "test_batches", "time_bin_indices", "predictions"}, f"{arm}/{sid}")
            for key in ("neuron_ids", "test_trial_ids", "test_batches", "time_bin_indices"):
                _need(record[key] == ref[key], f"{arm}/{sid}: {key} order or coverage mismatch")
            arrays = _arrays(_artifact(submission_path.parent, record["predictions"], "predictions"),
                             {"log_rate", "posterior_mu", "posterior_logvar"})
            _need(arrays["posterior_mu"].ndim == 2
                  and arrays["posterior_mu"].shape[1] == reference["recipe"]["latent_dimension"],
                  f"{arm}/{sid}: latent capacity mismatch")
            metrics[arm] = loss_components(counts, beta=reference["recipe"]["beta"], **arrays)
        h, i = (metrics[arm] for arm in ARMS)
        gain = h["poisson_nll_without_constant_mean"] - i["poisson_nll_without_constant_mean"]
        _need(math.isfinite(gain), f"{sid}: paired gain overflow")
        per_neuron = [a - b for a, b in zip(h["per_neuron_poisson_nll_without_constant"],
                                          i["per_neuron_poisson_nll_without_constant"])]
        bits_per_spike = (gain * (h["observation_count"] / (h["spike_count"] * math.log(2)))
                          if h["spike_count"] else None)
        _need(all(math.isfinite(v) for v in per_neuron)
              and (bits_per_spike is None or math.isfinite(bits_per_spike)), f"{sid}: diagnostic gain overflow")
        results.append({"session_id": sid, "neuron_ids": ref["neuron_ids"], "arms": metrics,
                        "interaction_gain_nats_per_observation": gain,
                        "per_neuron_interaction_gain": per_neuron,
                        "interaction_gain_bits_per_spike": bits_per_spike})
    gains = [r["interaction_gain_nats_per_observation"] for r in results]
    aggregate = {}
    for arm in ARMS:
        records = [r["arms"][arm] for r in results]
        aggregate[arm] = {
            "equal_session_poisson_nll_without_constant": _weighted_mean([r["poisson_nll_without_constant_mean"] for r in records]),
            "pooled_observation_poisson_nll_without_constant": _weighted_mean([r["poisson_nll_without_constant_mean"] for r in records], [r["observation_count"] for r in records]),
            "source_trial_weighted_variational_loss": _weighted_mean([r["source_variational_loss_mean"] for r in records], [r["trial_count"] for r in records]),
        }
    return {"schema_version": 1, "task_id": TASK_ID,
            "status": "prospective_evaluator_engineering_output",
            "scientifically_qualified": False, "full_contract_complete": False,
            "inference_policy": INFERENCE_POLICY,
            "reference_sha256": reference_sha256,
            "submission_sha256": submission_sha256,
            "primary_endpoint": "equal_session_interaction_gain_nats_per_observation",
            "primary_value": _weighted_mean(gains),
            "secondary_exact_session_sign_flip_two_sided_p": exact_session_sign_flip(gains),
            "secondary_test_assumption": "Ten independent, exchangeable session-level paired gain signs under the null; exploratory with no pass threshold.",
            "aggregate": aggregate, "sessions": results, "preserved_holds": HOLDS}


def partition_digest(reference: dict) -> str:
    """Canonical digest of all training/validation/test identities in fixed cohort order."""
    records = {s["session_id"]: s for s in reference["sessions"]}
    partition = [{"session_id": sid, **{key: records[sid][key] for key in
                 ("train_trial_ids", "validation_trial_ids", "test_trial_ids")}} for sid in SESSION_IDS]
    return hashlib.sha256(json.dumps(partition, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = evaluate(args.reference, args.submission)
        _need(args.output.resolve() not in (args.reference.resolve(), args.submission.resolve()),
              "output must not overwrite an input manifest")
        with args.output.open("x") as handle:
            handle.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    except (EvaluationError, OSError) as exc:
        parser.exit(2, f"evaluation rejected: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
