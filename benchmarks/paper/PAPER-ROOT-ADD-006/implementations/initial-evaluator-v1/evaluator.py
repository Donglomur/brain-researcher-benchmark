"""Source-grounded reactivation and prospective participant-held-out prediction.

This independent implementation is not a qualified reproduction. Native MCOS
conversion, author scaling and behavioural fits remain unresolved; see docs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

TASK = "PAPER-ROOT-ADD-006"
CONTRACT_SHA256 = "c4d1438fbdf13e3ecb5d5ce8ead240d10f0115b046bb63edc7c1144d96f9daf4"
SOURCE_REVISION = "1c9b3c92c77d4f5a4e4ccfa36d5a695814a2f612"
COHORT = tuple(f"sub-S{i:03d}" for i in range(1, 22))
EXCLUDED = ("sub-S006", "sub-S019")
HOLDS = [
    "Native MATLAB MCOS event-table conversion and event/epoch identities unqualified",
    "Author scaleFunc absent; paper 95th-percentile scaling applied train-only prospectively",
    "Behavioural fit source incomplete; supplied parameter estimates not reproduced",
    "Participant-independent target-fit declarations are unverified; joint hierarchical EM labels are inadmissible",
    "Exact MATLAB lassoglm parity and native robustfit/permutation results unverified",
    "Authentic full-cohort run, protected replay and independent scientific qualification absent",
    "Official code license and full-text/component redistribution rights unresolved",
    "Public source/results exposure; no blind frontier or causal code-benefit claim",
]


def finite(value: Any, name: str, ndim: int | None = None) -> np.ndarray:
    a = np.asarray(value)
    if a.dtype.kind not in "iuf" or (ndim is not None and a.ndim != ndim):
        raise ValueError(f"{name}: expected primitive numeric array of rank {ndim}")
    a = a.astype(float)
    if not np.isfinite(a).all():
        raise ValueError(f"{name}: nonfinite values")
    return a


def times(value: Any, name: str) -> np.ndarray:
    a = finite(value, name, 1)
    if not len(a) or np.any(np.diff(a) <= 0) or np.any(a % 10) or np.any((a < 0) | (a > 500)):
        raise ValueError(f"{name}: require increasing subset of source 0:10:500 ms")
    return a


def indices(axis: np.ndarray, requested: np.ndarray, name: str) -> list[int]:
    axis = finite(axis, name, 1)
    if np.any(np.diff(axis) <= 0):
        raise ValueError(f"{name}: duplicate or nonmonotonic axis")
    result = []
    for t in requested:
        found = np.flatnonzero(axis == t)
        if len(found) != 1:
            raise ValueError(f"{name}: exact time {t} ms absent; no interpolation")
        result.append(int(found[0]))
    return result


def standardize_fit(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Prospective population-SD scaling fitted only on training observations."""
    x = finite(x, "training design", 2)
    mean, scale = x.mean(0), x.std(0)
    scale[scale == 0] = 1.0
    return mean, scale


def fit_l1_binomial(x: np.ndarray, y: np.ndarray, penalty: float = 0.002) -> tuple[np.ndarray, float]:
    """Minimize mean binary log loss + lambda*L1, unpenalized intercept.

    Nonnegative split coefficients permit smooth bounded optimization. This
    implements the declared objective, not MATLAB solver equivalence.
    """
    x, y = finite(x, "x", 2), finite(y, "y", 1)
    if len(x) != len(y) or not np.all(np.isin(y, [0, 1])) or len(np.unique(y)) != 2:
        raise ValueError("binomial fit needs aligned positive and negative observations")
    if not np.isfinite(penalty) or penalty <= 0:
        raise ValueError("penalty must be positive")
    p = x.shape[1]
    init = np.zeros(2*p + 1)
    init[-1] = np.log(y.mean()/(1-y.mean()))

    def objective(v: np.ndarray) -> tuple[float, np.ndarray]:
        z = x @ (v[:p] - v[p:2*p]) + v[-1]
        residual = expit(z) - y
        g = x.T @ residual / len(y)
        loss = np.mean(np.logaddexp(0, z) - y*z) + penalty*v[:2*p].sum()
        return float(loss), np.r_[g + penalty, -g + penalty, residual.mean()]

    fit = minimize(objective, init, jac=True, method="L-BFGS-B",
                   bounds=[(0, None)]*(2*p)+[(None, None)],
                   options={"maxiter": 4000, "ftol": 1e-12, "gtol": 1e-7, "maxls": 50})
    if not fit.success or not np.isfinite(fit.x).all():
        raise ValueError(f"binomial optimizer failed: {fit.message}")
    grad = objective(fit.x)[1]
    projected = grad.copy()
    projected[:2*p] = np.where((fit.x[:2*p] <= 1e-10) & (grad[:2*p] > 0), 0, grad[:2*p])
    if np.max(np.abs(projected)) > 2e-5:
        raise ValueError("binomial optimizer failed projected-gradient certificate")
    return fit.x[:p] - fit.x[p:2*p], float(fit.x[-1])


def decode(localizer: np.ndarray, task: np.ndarray, localizer_ms: np.ndarray,
           task_ms: np.ndarray, image_class: np.ndarray, block: np.ndarray,
           train_ms: np.ndarray, test_ms: np.ndarray) -> np.ndarray:
    """Fit three one-v-rest localizer classifiers with equal -200 ms nulls."""
    localizer, task = finite(localizer, "localizer", 3), finite(task, "task", 3)
    image_class, block = finite(image_class, "image_class", 1), finite(block, "block", 1)
    train_ms, test_ms = times(train_ms, "train_ms"), times(test_ms, "test_ms")
    if len(image_class) != len(localizer) or len(block) != len(localizer):
        raise ValueError("localizer event/epoch mismatch")
    if localizer.shape[1] != task.shape[1] or localizer.shape[1] == 0:
        raise ValueError("sensor dimensions disagree or empty")
    if localizer.shape[2] != len(localizer_ms) or task.shape[2] != len(task_ms):
        raise ValueError("epoch time dimension mismatch")
    if np.any(image_class % 1) or not np.all(np.isin(image_class, np.arange(1, 8))):
        raise ValueError("image classes must be source O1/O2/OS/C1/C2/C3/C4 = 1..7")
    if np.any(block % 1) or np.any(block < 1):
        raise ValueError("block numbers must be positive integers")
    keep = block < 4
    if set(image_class[keep]) != set(range(1, 8)):
        raise ValueError("all seven localizer image classes required in blocks 1..3")
    ix_train = indices(localizer_ms, train_ms, "localizer_ms")
    ix_test = indices(task_ms, test_ms, "task_ms")
    null_index = indices(localizer_ms, np.array([-200.]), "localizer_ms")[0]
    null = localizer[keep, :, null_index]
    labels = np.r_[image_class[keep], np.full(keep.sum(), 8)]
    results = np.empty((len(task), len(train_ms), len(test_ms), 3))
    for k, train_idx in enumerate(ix_train):
        x = np.concatenate([localizer[keep, :, train_idx], null])
        scale = float(np.percentile(np.abs(x), 95))
        if scale == 0:
            raise ValueError("localizer 95th-percentile absolute scale is zero")
        x = x/scale
        task_x = task[:, :, ix_test].transpose(0, 2, 1)/scale
        for c in range(1, 4):
            beta, intercept = fit_l1_binomial(x, (labels == c).astype(float))
            results[:, k, :, c-1] = task_x @ beta + intercept
    return results


def first_level(logits: np.ndarray, choice_number: np.ndarray, o1_val: np.ndarray,
                o2_val: np.ndarray, rt_ms: np.ndarray, test_ms: np.ndarray) -> dict[str, np.ndarray]:
    """Exact source design and response-time censoring, with rank failure explicit."""
    logits = finite(logits, "logits", 4)
    test_ms = times(test_ms, "test_ms")
    values = [finite(v, n, 1) for v, n in zip(
        [choice_number, o1_val, o2_val, rt_ms], ["choice_number", "o1_val", "o2_val", "rt_ms"])]
    choice, o1, o2, rt = values
    if any(len(v) != len(logits) for v in values) or logits.shape[-1] != 3 or logits.shape[2] != len(test_ms):
        raise ValueError("first-level arrays misaligned")
    if not np.all(np.isin(choice, [1, 2, 3, 4])) or np.any(rt < 0):
        raise ValueError("choice_number must be 1..4 and RT milliseconds nonnegative")
    design = np.column_stack([np.ones(len(choice)), (5-choice)/5-.5, np.abs(o2)-np.abs(o1)])
    rp = expit(logits)
    response = rp[:, :, :, 1] - rp[:, :, :, 0]
    beta = np.empty((2, logits.shape[1], len(test_ms)))
    safe = np.empty((logits.shape[1], len(test_ms)))
    counts = np.zeros(len(test_ms), dtype=int)
    for j, t in enumerate(test_ms):
        keep = rt >= t
        counts[j] = keep.sum()
        if counts[j] < 4 or np.linalg.matrix_rank(design[keep]) != 3:
            raise ValueError(f"unidentified first-level design at {t} ms: count={counts[j]}")
        beta[:, :, j] = (np.linalg.pinv(design[keep]) @ response[keep, :, j])[1:]
        safe[:, j] = rp[keep, :, j, 2].mean(axis=0)
    return {"effects": beta, "safe": safe, "eligible_trials": counts}


def ridge_predict(x: np.ndarray, y: np.ndarray, query: np.ndarray, alpha: float) -> np.ndarray:
    x, y, query = finite(x, "ridge x", 2), finite(y, "ridge y", 1), finite(query, "ridge query", 2)
    if len(x) != len(y) or x.shape[1] != query.shape[1] or not np.isfinite(alpha) or alpha <= 0:
        raise ValueError("invalid ridge fit")
    mean, scale = standardize_fit(x)
    z, q = (x-mean)/scale, (query-mean)/scale
    target_mean = y.mean()
    beta = np.linalg.solve(z.T @ z + alpha*np.eye(z.shape[1]), z.T @ (y-target_mean))
    return q @ beta + target_mean


def _design(effects: np.ndarray, safe: np.ndarray, nuisance: np.ndarray,
            effect: int, cell: tuple[int, int], full: bool) -> np.ndarray:
    i, j = cell
    columns = [nuisance, effects[:, 1-effect, i, j, None], safe[:, i, j, None]]
    if full:
        columns.append(effects[:, effect, i, j, None])
    return np.concatenate(columns, axis=1)


def select_model(effects: np.ndarray, safe: np.ndarray, nuisance: np.ndarray,
                 y: np.ndarray, effect: int, alphas: np.ndarray, full: bool) -> tuple[tuple[int, int], float, float]:
    """Only training participants enter inner LOPO model and latency selection."""
    best = None
    for i in range(effects.shape[2]):
        for j in range(effects.shape[3]):
            x = _design(effects, safe, nuisance, effect, (i, j), full)
            for alpha in alphas:
                pred = np.empty(len(y))
                for k in range(len(y)):
                    keep = np.arange(len(y)) != k
                    pred[k] = ridge_predict(x[keep], y[keep], x[k:k+1], float(alpha))[0]
                score = float(np.mean((pred-y)**2))
                candidate = (score, i, j, float(alpha))
                if best is None or candidate < best:
                    best = candidate
    assert best is not None
    return (best[1], best[2]), best[3], best[0]


def nested_prediction(ids: list[str], effects: np.ndarray, safe: np.ndarray,
                      nuisance: np.ndarray, labels: np.ndarray, alphas: np.ndarray) -> dict[str, Any]:
    """Paired LOPO comparison, predeclared grid, all tuning nested within folds."""
    effects, safe = finite(effects, "effects", 4), finite(safe, "safe", 3)
    nuisance, labels = finite(nuisance, "nuisance", 2), finite(labels, "labels", 2)
    alphas = finite(alphas, "alphas", 1)
    n = len(ids)
    if n < 6 or len(set(ids)) != n or effects.shape[:2] != (n, 2) or safe.shape != (n, *effects.shape[2:]):
        raise ValueError("invalid participant identity/dimensions")
    if nuisance.shape[0] != n or labels.shape != (n, 2) or not len(alphas) or np.any(alphas <= 0) or len(set(alphas)) != len(alphas):
        raise ValueError("invalid nested participant labels/nuisance/grid")
    predictions = np.empty((n, 2, 2))
    folds = []
    for heldout in range(n):
        keep = np.arange(n) != heldout
        for effect in range(2):
            for mode, full in enumerate([False, True]):
                cell, alpha, inner_mse = select_model(effects[keep], safe[keep], nuisance[keep], labels[keep, effect], effect, alphas, full)
                x = _design(effects, safe, nuisance, effect, cell, full)
                predictions[heldout, effect, mode] = ridge_predict(x[keep], labels[keep, effect], x[heldout:heldout+1], alpha)[0]
                folds.append({"participant": ids[heldout], "target": ["beta_prob", "beta_rew"][effect],
                              "model": ["difficulty_correlated_neural_baseline", "plus_target_neural_effect"][mode],
                              "train_time_index": cell[0], "test_time_index": cell[1],
                              "alpha": alpha, "inner_mse": inner_mse,
                              "training_participants": [v for k, v in enumerate(ids) if k != heldout]})
    error = (predictions-labels[:, :, None])**2
    delta = error[:, :, 0]-error[:, :, 1]
    # Fixed-seed participant bootstrap is prospective descriptive uncertainty.
    rng = np.random.default_rng(6006)
    boot = delta[rng.integers(n, size=(2000, n))].mean(axis=1)
    return {"participant_ids": ids, "target_order": ["beta_prob", "beta_rew"],
            "predictions": predictions.tolist(), "truth": labels.tolist(),
            "baseline_mse": error[:, :, 0].mean(0).tolist(), "full_mse": error[:, :, 1].mean(0).tolist(),
            "paired_mse_improvement": delta.mean(0).tolist(),
            "paired_mse_improvement_participant_bootstrap_95pct": np.quantile(boot, [.025, .975], axis=0).T.tolist(),
            "bootstrap_caveat": "Descriptive participant resampling of fixed CV losses; overlapping training folds and parameter-estimation uncertainty not modelled",
            "folds": folds}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _local_file(base: Path, relative: str) -> Path:
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError("packet file must be relative")
    path = (base/relative).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file():
        raise ValueError("packet file escapes input directory or is absent")
    return path


def load_packet(manifest_path: Path) -> tuple[dict, list[tuple[dict, dict[str, np.ndarray]]]]:
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("task_id") != TASK or manifest.get("schema_version") != 1:
        raise ValueError("wrong task/schema")
    if manifest.get("contract_sha256") != CONTRACT_SHA256 or manifest.get("source_revision") != SOURCE_REVISION:
        raise ValueError("contract/source pin mismatch")
    if manifest.get("input_kind") not in ["generated_engineering_control", "unqualified_primitive_export"]:
        raise ValueError("input kind must retain unqualified native conversion status")
    if manifest.get("event_table_conversion_status") != "unqualified":
        raise ValueError("this version cannot certify MCOS event conversion")
    train_ms, test_ms = times(manifest["train_ms"], "train_ms"), times(manifest["test_ms"], "test_ms")
    alphas = finite(manifest["ridge_alphas"], "ridge_alphas", 1)
    if not len(alphas) or np.any(alphas <= 0):
        raise ValueError("positive predeclared ridge grid required")
    participants = manifest["participants"]
    if [p.get("participant_id") for p in participants] != list(COHORT):
        raise ValueError("complete source cohort sub-S001..sub-S021 in source order required")
    result = []
    required = {"localizer", "task", "localizer_ms", "task_ms", "image_class", "block",
                "choice_number", "o1_val", "o2_val", "safe_val", "rt_ms"}
    for p in participants:
        for key in ["localizer_trial_ids", "task_trial_ids", "sensor_names"]:
            v = p[key]
            if not isinstance(v, list) or not v or any(not isinstance(s, str) or not s for s in v) or len(set(v)) != len(v):
                raise ValueError(f"{key}: nonempty unique string identities required")
        if set(p["localizer_trial_ids"]) & set(p["task_trial_ids"]):
            raise ValueError("localizer and task trial identity overlap")
        provenance = p["provenance"]
        expected = {"localizer": f"derivatives/Epoched_Preprocessed_Data/Epoched_Localizer_Data/{p['participant_id']}_Epoched_Localizer_Data.mat",
                    "task": f"derivatives/Epoched_Preprocessed_Data/Epoched_Task_Choice_Data/{p['participant_id']}_Epoched_Task_Choice_Data.mat",
                    "events": f"derivatives/Event_Info_Tables/{p['participant_id']}_table.mat"}
        if provenance.get("release") != "ds005065/1.0.0" or provenance.get("native_paths") != expected:
            raise ValueError("released-to-packet source path mapping mismatch")
        if not isinstance(p.get("behavior_parameter_provenance"), str) or not p["behavior_parameter_provenance"]:
            raise ValueError("behavior parameter derivation provenance required")
        expected_scope = {"participants": [p["participant_id"]], "cross_participant_prior": False, "native_model_parity": "unverified"}
        if p.get("behavior_parameter_fit_scope") != expected_scope:
            raise ValueError("behavior targets require declared participant-independent fits without shared priors")
        labels = finite(p["behavior_parameters"], "behavior_parameters", 1)
        if labels.shape != (2,):
            raise ValueError("behavior parameter order is beta_prob,beta_rew")
        path = _local_file(manifest_path.parent, p["arrays"])
        if digest(path) != p["arrays_sha256"]:
            raise ValueError("numeric packet SHA256 mismatch")
        # NPZ never enables pickle; opaque MATLAB/pickled objects are not loaded.
        with np.load(path, allow_pickle=False) as data:
            if set(data.files) != required:
                raise ValueError("numeric NPZ fields do not match explicit schema")
            arrays = {key: finite(data[key], key) for key in required}
        if arrays["localizer"].shape[:2] != (len(p["localizer_trial_ids"]), len(p["sensor_names"])) or arrays["task"].shape[:2] != (len(p["task_trial_ids"]), len(p["sensor_names"])):
            raise ValueError("explicit event/sensor identity dimensions disagree")
        if arrays["safe_val"].shape != (len(p["task_trial_ids"]),):
            raise ValueError("safe reward must align to task rows")
        result.append((p, arrays))
    return manifest, result


def evaluate(manifest_path: Path) -> dict[str, Any]:
    manifest, participants = load_packet(manifest_path)
    effects, safe, nuisance, labels, ids, individual = [], [], [], [], [], []
    for p, a in participants:
        logits = decode(a["localizer"], a["task"], a["localizer_ms"], a["task_ms"],
                        a["image_class"], a["block"], manifest["train_ms"], manifest["test_ms"])
        first = first_level(logits, a["choice_number"], a["o1_val"], a["o2_val"], a["rt_ms"], manifest["test_ms"])
        individual.append({"participant_id": p["participant_id"], "excluded_second_level": p["participant_id"] in EXCLUDED,
                           "eligible_trials": first["eligible_trials"].tolist(),
                           "effects": first["effects"].tolist(), "safe": first["safe"].tolist()})
        if p["participant_id"] in EXCLUDED:
            continue
        # Source p(O2)=(5-choice)/5. Prospective expected-value distance controls
        # choice difficulty; it is not a claim of behavioural subjective value.
        p2 = (5-a["choice_number"])/5
        ev_gap = np.abs((1-p2)*a["o1_val"] + p2*a["o2_val"] - a["safe_val"])
        nuisance.append([float(ev_gap.mean()), float(ev_gap.std()), float(np.mean(np.abs(a["o2_val"])-np.abs(a["o1_val"])))])
        effects.append(first["effects"]); safe.append(first["safe"])
        labels.append(p["behavior_parameters"]); ids.append(p["participant_id"])
    result = nested_prediction(ids, np.array(effects), np.array(safe), np.array(nuisance), np.array(labels), np.array(manifest["ridge_alphas"]))
    for fold in result["folds"]:
        fold["train_time_ms"] = manifest["train_ms"][fold["train_time_index"]]
        fold["test_time_ms"] = manifest["test_ms"][fold["test_time_index"]]
    return {"task_id": TASK, "implementation": "initial-evaluator-v1", "scientific_readiness": "unknown",
            "input_kind": manifest["input_kind"], "input_manifest_sha256": digest(manifest_path),
            "contract_sha256": CONTRACT_SHA256, "source_revision": SOURCE_REVISION,
            "scientific_qualification": False, "whole_paper_reproduction": False,
            "second_level_excluded_source_participants": list(EXCLUDED), "preserved_gates": HOLDS,
            "train_ms": manifest["train_ms"], "test_ms": manifest["test_ms"],
            "participant_first_level": individual, "prospective_nested_prediction": result}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.manifest)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")


if __name__ == "__main__":
    main()
