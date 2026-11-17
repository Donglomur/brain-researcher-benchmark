"""Prospective, blocked dentate-neuron encoding analysis (NumPy only).

The source-field converter follows the pinned ErasmusAttn converter where stated;
the nested ridge model and directional contrast are new construction choices.
No empirical reference, paper reproduction, or scientific qualification is implied.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any
import numpy as np

TASK_ID = "PAPER-FIND-ADD-005"
SOURCE_COMMIT = "130f5e64f86bd63980f70bb839c02cd264782aef"
EVENTS = ("fix_on", "c_start", "delay_start", "choice_target", "saccade_onset", "reward_start")
TIMINGS = ("fix_on", "cue_start", "cue_stop", "c_start", "c_stop", "delay_start", "choice_target", "saccade_onset", "reward_start")
GATES = [
    "Authentic cells4.2.mat payload/schema import and complete population reconciliation are unverified.",
    "Direct attention estimand, exact paper contrast, figure reference and numerical tolerance remain unresolved.",
    "This prospective ridge/circular-contrast model does not reproduce the author group-lasso hierarchy or MATLAB runtime.",
    "Native MATLAB/toolbox/SPAMS qualification and authentic-data resource envelope are unmeasured.",
    "Only within-cell trial-block evaluation is implemented; recording/session identities and cross-session assessment remain unresolved.",
    "Two macaques cannot establish population-wide generalization; directional association is not causal attention control.",
    "Public source/results are exposed; protected assessment, independent model attempts and source-exposure comparison are not established.",
    "Dryad component terms and imported-data rights must be checked independently of the author code license.",
]

class ContractError(ValueError):
    """Fail-closed malformed or analytically ineligible input."""

@dataclass(frozen=True)
class Config:
    bin_ms: int = 25
    event_duration_ms: int = 1500
    event_bases: int = 5
    outer_folds: int = 5
    inner_folds: int = 3
    guard_trials: int = 1
    lambdas: tuple[float, ...] = (0.01, 0.1, 1.0)
    max_iterations: int = 80
    tolerance: float = 1e-8

    def validate(self) -> None:
        for name in ("bin_ms", "event_duration_ms", "event_bases", "outer_folds", "inner_folds", "guard_trials", "max_iterations"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ContractError(f"{name} must be an integer")
        if self.bin_ms <= 0 or self.event_duration_ms <= 0 or self.event_bases < 2:
            raise ContractError("positive time scales and at least two basis functions required")
        if self.outer_folds < 2 or self.inner_folds < 2 or self.guard_trials < 1:
            raise ContractError("nested folds >=2 and history guard >=1 required")
        if self.max_iterations < 1 or not math.isfinite(self.tolerance) or self.tolerance <= 0:
            raise ContractError("invalid optimizer configuration")
        if not self.lambdas or any(isinstance(x, bool) or not math.isfinite(x) or x <= 0 for x in self.lambdas):
            raise ContractError("ridge grid must contain finite positive penalties")
        if len(set(self.lambdas)) != len(self.lambdas):
            raise ContractError("duplicate penalties")

def number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ContractError(f"{label}: finite numeric value required")
    return float(value)

def integer(value: Any, label: str) -> int:
    val = number(value, label)
    if val != int(val):
        raise ContractError(f"{label}: integer required")
    return int(val)

def vector(value: Any, label: str) -> np.ndarray:
    if not isinstance(value, list):
        raise ContractError(f"{label}: JSON array required")
    return np.asarray([number(x, label) for x in value], dtype=float)

def eye_vector(value: Any, label: str) -> np.ndarray:
    if not isinstance(value, list):
        raise ContractError(f"{label}: JSON array required")
    return np.asarray([np.nan if x is None else number(x, label) for x in value], dtype=float)


def normalize_cell(cell: dict[str, Any], cfg: Config) -> tuple[list[dict], list[dict]]:
    """Map a declared JSON export of source trials; never infer a MAT schema.

    Source rules: missing n_minus_1 omits cell; bad durations, repeated events,
    empty SS and negative c_stop on conditions 1/2 omit trials. Source rounding
    excludes spikes whose rounded millisecond is outside duration. Additional
    prospective complete-eye/finite-time requirements are separately labelled.
    """
    if not isinstance(cell, dict):
        raise ContractError("cell must be an object")
    for name in ("monkey", "cell_id"):
        if not isinstance(cell.get(name), str) or not cell[name]:
            raise ContractError(f"nonempty {name} required")
    trials = cell.get("trials")
    if not isinstance(trials, list) or not trials:
        raise ContractError("nonempty trials array required")
    if any(not isinstance(t, dict) for t in trials):
        raise ContractError("trial must be an object")
    if any("n_minus_1" not in t for t in trials):
        return [], [{"scope": "cell", "reason": "source_missing_n_minus_1", "trials": len(trials)}]
    retained, audit, seen = [], [], set()
    for raw in trials:
        nr = integer(raw.get("trial_nr"), "trial_nr")
        if nr in seen:
            raise ContractError("duplicate trial_nr within cell")
        seen.add(nr)
        condition = integer(raw.get("condition_code"), "condition_code")
        if condition not in range(5):
            raise ContractError("unknown source condition_code")
        duration = integer(raw.get("fixon2fixon"), "fixon2fixon")
        c_stop = number(raw.get("c_stop"), "c_stop")
        presentations = vector(raw.get("event_presentations"), "event_presentations")
        if not presentations.size or np.any(presentations < 0) or np.any(presentations != np.floor(presentations)):
            raise ContractError("event_presentations must contain nonnegative integer counts")
        spikes = vector(raw.get("SS"), "SS")
        reason = None
        if duration < 1:
            reason = "source_duration_below_1ms"
        elif condition in (1, 2) and c_stop < 0:
            reason = "source_invalid_c_stop"
        elif np.any(presentations > 1):
            reason = "source_repeated_event"
        elif not spikes.size:
            reason = "source_empty_SS"
        if reason:
            audit.append({"trial_nr": nr, "reason": reason}); continue
        # Source registered timings; saccade onset is first landmark, delay is c_stop+100.
        times = {k: number(raw.get(k), k) for k in TIMINGS if k not in ("saccade_onset", "delay_start")}
        landmarks = vector(raw.get("saccade_landmarks"), "saccade_landmarks")
        times["saccade_onset"] = float(landmarks[0]) if landmarks.size else None
        times["delay_start"] = c_stop + 100.0
        if condition == 4:
            shift = number(raw.get("trial_start"), "trial_start")
            if shift != int(shift):
                raise ContractError("random-reward trial_start must be integer ms")
            times = {k: (v - shift if v is not None and v >= 0 else None) for k, v in times.items()}
            times["fix_on"] = 0.0
            duration -= int(shift)
            spikes = spikes - shift / 1000.0
        spikes_ms = spikes * 1000.0
        spikes_ms = spikes_ms[(spikes_ms >= 0) & (np.floor(spikes_ms + 0.5) < duration)]
        past = raw["n_minus_1"]
        if not isinstance(past, dict):
            raise ContractError("n_minus_1 must be an object")
        past_condition = integer(past.get("condition_code"), "n_minus_1.condition_code")
        if past_condition not in range(5):
            raise ContractError("unknown past condition_code")
        gap = number(raw.get("gap_direction"), "gap_direction")
        past_gap = number(past.get("gap_direction"), "n_minus_1.gap_direction")
        reward_duration = number(raw.get("reward_duration"), "reward_duration")
        if reward_duration < 0:
            raise ContractError("negative reward_duration")
        if reward_duration == 0:
            times["reward_start"] = None
        # Source selection from fitSingleCellGLM, with extra strict timing gates.
        reason = None
        if condition not in (1, 2) or past_condition not in (1, 2):
            reason = "source_current_or_previous_condition_not_1_or_2"
        elif times["cue_start"] is None or times["cue_start"] > 1000:
            reason = "source_cue_after_1000ms"
        elif times["saccade_onset"] is None:
            reason = "source_missing_saccade"
        elif not spikes_ms.size:
            reason = "source_empty_SS_after_clipping"
        else:
            event_times = [times[k] for k in EVENTS]
            if any(a is not None and b is not None and b - a <= cfg.bin_ms for a, b in zip(event_times, event_times[1:])):
                reason = "source_event_spacing_not_above_bin"
            elif any(times[k] is None or not 0 <= times[k] < duration for k in EVENTS[:-1]):
                reason = "prospective_invalid_required_event_time"
            elif times["reward_start"] is not None and not 0 <= times["reward_start"] < duration:
                reason = "prospective_invalid_reward_time"
            elif not 0 <= times["cue_start"] < duration:
                reason = "prospective_invalid_cue_time"
        if reason:
            audit.append({"trial_nr": nr, "reason": reason}); continue
        eye_x, eye_y = eye_vector(raw.get("eyeX"), "eyeX"), eye_vector(raw.get("eyeY"), "eyeY")
        # MATLAB range 4000:(4000+duration-1) becomes Python [3999:3999+duration].
        if len(eye_x) != len(eye_y) or len(eye_x) < 3999 + duration:
            audit.append({"trial_nr": nr, "reason": "prospective_incomplete_eye_support"}); continue
        eye = np.column_stack((eye_x[3999:3999+duration], eye_y[3999:3999+duration]))
        if not np.all(np.isfinite(eye)):
            audit.append({"trial_nr": nr, "reason": "prospective_nonfinite_eye_support"}); continue
        retained.append({"trial_nr": nr, "duration_ms": duration, "spikes_ms": spikes_ms,
                         "times": times, "eye": eye, "condition_code": condition,
                         "past_condition": past_condition, "gap_direction": gap % 360,
                         "saccade_direction": (gap + (180 if condition == 1 else 0)) % 360,
                         "past_gap": past_gap % 360,
                         "past_saccade": (past_gap + (180 if past_condition == 1 else 0)) % 360})
    retained.sort(key=lambda t: t["trial_nr"])
    # Preserve original chronological positions for guards, including excluded trials.
    positions = {nr: i for i, nr in enumerate(sorted(seen))}
    for trial in retained:
        trial["position"] = positions[trial["trial_nr"]]
    return retained, audit

def source_bin_index(times_ms: np.ndarray, bin_ms: int) -> np.ndarray:
    """Zero-based equivalent of source (t==0)+ceil(t/binSize)."""
    return np.maximum(0, np.ceil(times_ms / bin_ms).astype(int) - 1)


def temporal_basis(cfg: Config) -> np.ndarray:
    """Pinned progressive cosine x1.5 off0 formula, normalized per author fit.

    Formula attribution: Sue Ann Koay / ErasmusAttn_2020, pinned source commit
    130f5e64..., CC BY 4.0; independently expressed with NumPy broadcasting.
    """
    n = int(math.ceil(cfg.event_duration_ms / cfg.bin_ms))
    k = np.arange(cfg.event_bases)
    sigma = n * 3 * 2**cfg.event_bases / (4 * 3**cfg.event_bases - 3 * 2**cfg.event_bases)
    widths = 1.5**k * sigma
    centers = 1 + (1.5**(k + 1) - 1) * sigma
    phase = (np.arange(1, n + 1)[:, None] - centers) / widths
    basis = np.where(np.abs(phase) < 0.5, (np.cos(2 * np.pi * phase) + 1) / 2, 0)
    maximum = basis.max(axis=0)
    if np.any(maximum <= 0):
        raise ContractError("too few temporal bins for nonzero source basis")
    return basis / maximum


def event_design(event_ms: float | None, bins: int, cfg: Config) -> np.ndarray:
    result = np.zeros((bins, cfg.event_bases))
    if event_ms is None:
        return result
    start = int(source_bin_index(np.array([event_ms]), cfg.bin_ms)[0])
    template = temporal_basis(cfg)
    extent = min(len(template), bins - start)
    if extent > 0:
        result[start:start + extent] = template[:extent]
    return result

def make_design(trials: list[dict], cfg: Config) -> dict[str, Any]:
    cfg.validate()
    xs, ys, exposures, rows, labels = [], [], [], [], []
    base_names = [f"{event}.basis{k}" for event in EVENTS for k in range(cfg.event_bases)] + ["eye_x", "eye_y"]
    # Conditional direction-associated signal: controlling history and ensuing saccade.
    nuisance = (("past_gap", "fix_on"), ("past_saccade", "fix_on"), ("saccade_direction", "saccade_onset"))
    focal = (("gap_direction", "c_start"), ("gap_direction", "delay_start"))
    for variables in (nuisance, focal):
        for variable, event in variables:
            base_names += [f"{variable}.{harmonic}.{event}.basis{k}" for harmonic in ("sin", "cos") for k in range(cfg.event_bases)]
    reduced_columns = len(base_names) - len(focal) * 2 * cfg.event_bases
    for index, trial in enumerate(trials):
        duration = trial["duration_ms"]
        starts = np.arange(0, duration, cfg.bin_ms)
        widths = np.minimum(cfg.bin_ms, duration - starts)
        basis = {event: event_design(trial["times"][event], len(starts), cfg) for event in EVENTS}
        eye = np.array([trial["eye"][start:start+width].mean(axis=0) for start, width in zip(starts, widths)])
        columns = [basis[event] for event in EVENTS] + [eye]
        for variable, event in nuisance + focal:
            angle = np.deg2rad(trial[variable])
            columns += [basis[event] * np.sin(angle), basis[event] * np.cos(angle)]
        xs.append(np.column_stack(columns))
        indices = source_bin_index(trial["spikes_ms"], cfg.bin_ms)
        ys.append(np.bincount(indices, minlength=len(starts)).astype(float))
        exposures.append(widths / 1000.0)
        rows.extend([index] * len(starts))
        labels.append(trial["trial_nr"])
    if not xs:
        raise ContractError("no trials admitted")
    return {"X": np.vstack(xs), "y": np.concatenate(ys), "exposure": np.concatenate(exposures),
            "trial_rows": np.array(rows), "trial_ids": labels, "positions": np.array([t["position"] for t in trials]),
            "feature_names": base_names, "reduced_columns": reduced_columns}

def blocked_folds(indices: np.ndarray, positions: np.ndarray, folds: int, guard: int) -> list[tuple[np.ndarray, np.ndarray]]:
    if len(indices) < folds:
        raise ContractError("fewer trials than requested blocks")
    result = []
    indices = np.asarray(sorted(indices, key=lambda i: positions[i]), dtype=int)
    for test in np.array_split(indices, folds):
        keep = np.array([i for i in indices if np.min(np.abs(positions[test] - positions[i])) > guard], dtype=int)
        if len(keep) < 2:
            raise ContractError("fewer than two training trials after whole-trial history guard")
        result.append((keep, test))
    return result

def validate_score_arrays(y: np.ndarray, mu: np.ndarray) -> None:
    if y.shape != mu.shape or y.ndim != 1 or not len(y):
        raise ContractError("matching nonempty one-dimensional scoring arrays required")
    if not np.all(np.isfinite(y)) or np.any(y < 0) or np.any(y != np.floor(y)):
        raise ContractError("invalid observed Poisson counts")
    if not np.all(np.isfinite(mu)) or np.any(mu <= 0):
        raise ContractError("invalid predicted Poisson mean")

def log_likelihood(y: np.ndarray, mu: np.ndarray) -> float:
    validate_score_arrays(y, mu)
    factorial = np.array([math.lgamma(float(v) + 1) for v in y])
    return float(np.sum(y * np.log(mu) - mu - factorial))

def poisson_deviance(y: np.ndarray, mu: np.ndarray) -> float:
    validate_score_arrays(y, mu)
    terms = mu - y
    positive = y > 0
    terms = terms.copy()
    terms[positive] += y[positive] * np.log(y[positive] / mu[positive])
    return float(2 * np.sum(terms))

@dataclass
class PoissonModel:
    mean: np.ndarray
    scale: np.ndarray
    coefficients: np.ndarray
    iterations: int
    penalty: float

    def predict(self, x: np.ndarray, exposure: np.ndarray) -> np.ndarray:
        z = np.column_stack((np.ones(len(x)), (x - self.mean) / self.scale))
        eta = z @ self.coefficients + np.log(exposure)
        if not np.all(np.isfinite(eta)) or np.any(np.abs(eta) > 700):
            raise ContractError("nonfinite/overflowing held-out prediction; no clipping permitted")
        return np.exp(eta)

def fit_poisson(x: np.ndarray, y: np.ndarray, exposure: np.ndarray, penalty: float, cfg: Config) -> PoissonModel:
    """Ridge Poisson Newton fit with train-only scaling and unpenalized intercept.

    Objective = mean(mu-y*eta) + penalty*||beta_without_intercept||²/2.
    The exposure offset is log(seconds), so exp(intercept) has rate units Hz.
    """
    if not math.isfinite(penalty) or penalty <= 0:
        raise ContractError("positive finite ridge penalty required")
    if x.ndim != 2 or len(x) != len(y) or y.shape != exposure.shape or not len(y):
        raise ContractError("incompatible fit arrays")
    if not all(np.all(np.isfinite(v)) for v in (x, y, exposure)) or np.any(y < 0) or np.any(y != np.floor(y)) or np.any(exposure <= 0):
        raise ContractError("finite nonnegative integer counts and positive exposure required")
    if y.sum() <= 0:
        raise ContractError("all-zero training counts have no finite unpenalized-intercept optimum")
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale < 1e-12] = 1.0
    z = np.column_stack((np.ones(len(x)), (x - mean) / scale))
    coef = np.zeros(z.shape[1]); coef[0] = np.log(y.sum() / exposure.sum())
    offset = np.log(exposure)
    ridge = np.ones(len(coef)) * penalty; ridge[0] = 0
    def objective(b):
        eta = z @ b + offset
        if not np.all(np.isfinite(eta)) or np.any(eta > 700):
            return float("inf")
        return float(np.mean(np.exp(eta) - y * eta) + 0.5 * np.dot(ridge * b, b))
    for iteration in range(1, cfg.max_iterations + 1):
        eta = z @ coef + offset
        mu = np.exp(eta)
        grad = z.T @ (mu - y) / len(y) + ridge * coef
        if np.max(np.abs(grad)) <= cfg.tolerance:
            return PoissonModel(mean, scale, coef, iteration, penalty)
        hessian = (z.T * mu) @ z / len(y) + np.diag(ridge)
        try:
            step = np.linalg.solve(hessian, grad)
        except np.linalg.LinAlgError as error:
            raise ContractError("singular Poisson Hessian") from error
        value, size = objective(coef), 1.0
        slope = float(grad @ step)
        if not math.isfinite(slope) or slope <= 0:
            raise ContractError("non-descent Newton direction")
        for _ in range(40):
            candidate = coef - size * step
            if objective(candidate) <= value - 1e-4 * size * slope:
                coef = candidate
                break
            size *= 0.5
        else:
            raise ContractError("Poisson line search failed")
    raise ContractError("Poisson optimizer did not converge; no score returned")

def evaluate_cell(trials: list[dict], cfg: Config) -> dict[str, Any]:
    design = make_design(trials, cfg)
    x, y, exposure, rows = (design[k] for k in ("X", "y", "exposure", "trial_rows"))
    positions, ids = design["positions"], design["trial_ids"]
    all_trials = np.arange(len(trials))
    folds = blocked_folds(all_trials, positions, cfg.outer_folds, cfg.guard_trials)
    predictions = {name: np.full(len(y), np.nan) for name in ("reduced", "full", "null")}
    records = []
    for fold_index, (training, testing) in enumerate(folds):
        inner = blocked_folds(training, positions, cfg.inner_folds, cfg.guard_trials)
        train_rows, test_rows = np.isin(rows, training), np.isin(rows, testing)
        if y[train_rows].sum() <= 0:
            raise ContractError("outer training fold has no spikes")
        null_mu = exposure[test_rows] * y[train_rows].sum() / exposure[train_rows].sum()
        predictions["null"][test_rows] = null_mu
        record = {"fold": fold_index, "train_trials": [ids[i] for i in training], "test_trials": [ids[i] for i in testing], "models": {}}
        for name, ncols in (("reduced", design["reduced_columns"]), ("full", x.shape[1])):
            scores = []
            for penalty in sorted(cfg.lambdas):
                total_ll, count = 0.0, 0
                for inner_train, inner_test in inner:
                    mask_train, mask_test = np.isin(rows, inner_train), np.isin(rows, inner_test)
                    model = fit_poisson(x[mask_train, :ncols], y[mask_train], exposure[mask_train], penalty, cfg)
                    mu = model.predict(x[mask_test, :ncols], exposure[mask_test])
                    total_ll += log_likelihood(y[mask_test], mu); count += int(mask_test.sum())
                scores.append({"penalty": penalty, "validation_log_likelihood_per_bin": total_ll / count})
            # Fixed tie rule prefers stronger regularization, never outer targets.
            chosen = max(scores, key=lambda r: (r["validation_log_likelihood_per_bin"], r["penalty"]))["penalty"]
            model = fit_poisson(x[train_rows, :ncols], y[train_rows], exposure[train_rows], chosen, cfg)
            mu = model.predict(x[test_rows, :ncols], exposure[test_rows])
            predictions[name][test_rows] = mu
            record["models"][name] = {"penalty": chosen, "inner_scores": scores, "iterations": model.iterations,
                                      "held_out_log_likelihood": log_likelihood(y[test_rows], mu),
                                      "training_mean": model.mean.tolist(), "training_scale": model.scale.tolist(),
                                      "standardized_coefficients_including_intercept": model.coefficients.tolist()}
        records.append(record)
    if any(not np.all(np.isfinite(mu)) for mu in predictions.values()):
        raise ContractError("outer predictions did not cover all admitted bins")
    ll = {name: log_likelihood(y, mu) for name, mu in predictions.items()}
    dev = {name: poisson_deviance(y, mu) for name, mu in predictions.items()}
    delta = ll["full"] - ll["reduced"]
    spike_count = int(y.sum())
    trial_predictions = []
    for index, nr in enumerate(ids):
        mask = rows == index
        trial_predictions.append({"trial_nr": nr, "observed_counts": y[mask].astype(int).tolist(),
                                  "exposure_seconds": exposure[mask].tolist(),
                                  "predicted_counts": {name: mu[mask].tolist() for name, mu in predictions.items()}})
    return {"trials": len(trials), "bins": len(y), "spikes": spike_count,
            "endpoint": "prospective_conditional_gap_direction_delta_log_likelihood_nats_per_spike",
            "delta_log_likelihood_nats": delta,
            "delta_log_likelihood_nats_per_spike": delta / spike_count if spike_count else None,
            "log_likelihood": ll, "poisson_deviance": dev,
            "deviance_explained_against_train_only_null": {name: 1 - dev[name] / dev["null"] if dev["null"] > 0 else None for name in ("reduced", "full")},
            "feature_names": design["feature_names"], "reduced_columns": design["reduced_columns"],
            "folds": records, "out_of_fold_predictions": trial_predictions}

def evaluate(document: dict[str, Any], cfg: Config = Config()) -> dict[str, Any]:
    cfg.validate()
    if not isinstance(document, dict) or document.get("schema") != "erasmus-source-trials-json-v1":
        raise ContractError("explicit erasmus-source-trials-json-v1 export schema required")
    if document.get("source_commit") != SOURCE_COMMIT:
        raise ContractError("source commit mismatch")
    if not isinstance(document.get("cells"), list) or not document["cells"]:
        raise ContractError("nonempty cells array required")
    cells, seen = [], set()
    for cell in document["cells"]:
        trials, audit = normalize_cell(cell, cfg)
        key = (cell["monkey"], cell["cell_id"])
        if key in seen:
            raise ContractError("duplicate animal/cell identity")
        seen.add(key)
        item = {"monkey": key[0], "cell_id": key[1], "source_trials": len(cell["trials"]), "exclusions": audit}
        if not trials:
            item.update(status="no_trials_admitted", result=None)
        else:
            # Lack of power for nested splits is visible, never silently dropped from a macro score.
            item.update(status="evaluated", result=evaluate_cell(trials, cfg))
        cells.append(item)
    values = [c["result"]["delta_log_likelihood_nats_per_spike"] for c in cells if c["result"] is not None]
    animal_summaries = []
    for monkey in sorted({c["monkey"] for c in cells}):
        members = [c for c in cells if c["monkey"] == monkey]
        valid = [c["result"]["delta_log_likelihood_nats_per_spike"] for c in members if c["result"] is not None]
        animal_summaries.append({"monkey": monkey, "input_cells": len(members), "evaluated_cells": len(valid),
                                 "descriptive_cell_macro_mean_nats_per_spike": float(np.mean(valid)) if valid else None})
    return {"task_id": TASK_ID, "schema": "dentate-prospective-evaluation-v1", "scientific_qualification": "unknown",
            "benchmark_complete": False, "paper_reproduction_established": False,
            "source_commit": SOURCE_COMMIT, "config": asdict(cfg), "cells": cells,
            "population_accounting": {"input_cells": len(cells), "evaluated_cells": len(values),
                                      "animals": sorted({c["monkey"] for c in cells})},
            "descriptive_cell_macro_mean_nats_per_spike": float(np.mean(values)) if values else None,
            "descriptive_animal_summaries": animal_summaries,
            "selection_scope": "Source-preserved retrospective inclusion requires nonempty source spikes and retained in-trial spikes; this conditions the estimand on spike-containing trials.",
            "macro_scope": "Admitted input cells only; no complete-population, animal-independent, or significance claim.",
            "preserved_gates": GATES}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    try:
        cfg = Config(**json.loads(args.config.read_text())) if args.config else Config()
        result = evaluate(json.loads(raw), cfg)
        result["input_sha256"] = hashlib.sha256(raw).hexdigest()
        payload = json.dumps(result, indent=2, allow_nan=False) + "\n"
    except (ContractError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, f"invalid evaluation: {error}\n")
    args.output.write_text(payload)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
