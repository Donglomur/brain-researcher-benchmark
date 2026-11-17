"""Prospective segment-aligned TCI correlations; no native-reproduction claim.

Original implementation. Source-derived endpoint, explicit prospective pairing
and interpolation rules. See README.md and source-provenance.json.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from itertools import combinations, product
import hashlib
import json
from pathlib import Path

import numpy as np

TASK_ID = "PAPER-FIND-024"
SCHEMA = "find024-segment-correlations-v1"
HOLDS = [
    "Native TCI dependency binding, alignment/pair weighting and numerical parity unverified",
    "Gamma integration-window refitting and absolute-time versus structure-yoking inference not implemented",
    "Authentic cohort/input hashes and story/participant split identities not verified",
    "Protected empirical reference, acceptance tolerance and isolated candidate replay not qualified",
    "Data/code redistribution rights unresolved; no author code or data redistributed",
]


class ContractError(ValueError):
    """Input is inconsistent with the frozen prospective analysis boundary."""


def _require(condition, message):
    if not condition:
        raise ContractError(message)


def _name(value, field):
    _require(isinstance(value, str) and bool(value.strip()), f"{field} must be a nonempty string")
    return value


def _finite_number(value, field):
    _require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{field} must be numeric")
    _require(np.isfinite(value), f"{field} must be finite")
    return float(value)


def _speech_rate(value):
    value = _finite_number(value, "speech_rate")
    for reference in (1 / np.sqrt(3), np.sqrt(3)):
        if np.isclose(value, reference, rtol=0, atol=1e-10):
            return float(reference)
    raise ContractError("main experiment rates must be 1/sqrt(3) or sqrt(3)")


def _unique_names(values, field):
    _require(isinstance(values, list) and bool(values), f"{field} must be nonempty")
    [_name(v, field) for v in values]
    _require(len(values) == len(set(values)), f"duplicate {field}")
    return values


def _real_array(value, field):
    array = np.asarray(value)
    _require(array.dtype.kind in "iuf", f"{field} must contain real numeric values")
    return np.asarray(array, dtype=float)


def _stable_mean(values):
    values = np.asarray(values, dtype=float)
    scale = float(np.max(np.abs(values)))
    return float(np.mean(values / scale) * scale) if scale else 0.0


def _pearson(x, y):
    """No pairwise omission: every prespecified segment contributes."""
    x = _real_array(x, "correlation x")
    y = _real_array(y, "correlation y")
    _require(x.shape == y.shape and x.ndim == 1 and x.size >= 3, "correlation needs at least three matched segments")
    _require(np.isfinite(x).all() and np.isfinite(y).all(), "nonfinite correlation samples")
    # Scale before centering as well as before dot products: even the mean of
    # several individually finite, large values can otherwise overflow.
    sx, sy = float(np.max(np.abs(x))), float(np.max(np.abs(y)))
    if sx == 0 or sy == 0:
        return None
    x, y = x / sx, y / sy
    x, y = x - x.mean(), y - y.mean()
    sx, sy = float(np.max(np.abs(x))), float(np.max(np.abs(y)))
    if sx == 0 or sy == 0:
        return None
    x, y = x / sx, y / sy
    return float(np.clip(np.dot(x, y) / np.sqrt(np.dot(x, x) * np.dot(y, y)), -1, 1))


def _aggregate_pairs(pair_values):
    """Undefined correlations are reported, never silently dropped."""
    if any(v is None for v in pair_values):
        return None
    return float(np.mean(pair_values))


def _validate_manifest(manifest):
    _require(manifest.get("schema") == SCHEMA, f"schema must be {SCHEMA}")
    _require(manifest.get("input_role") == "empirical_electrode_timecourses", "only empirical timecourses are admissible inputs")
    _require(manifest.get("boundary_policy") == "explicit_distinct_contexts", "boundary_policy must be explicit_distinct_contexts")
    _require(manifest.get("alignment_policy") == "linear_interpolation", "alignment_policy must be linear_interpolation")
    _name(manifest.get("cohort_id"), "cohort_id")
    _name(manifest.get("eligibility_provenance"), "eligibility_provenance")
    _require(manifest.get("selection_uses_assessment_effects") is False, "assessment-effect electrode selection forbidden")
    lags = np.asarray(manifest.get("lags_sec"), dtype=float)
    _require(lags.ndim == 1 and lags.size > 0 and np.isfinite(lags).all() and np.all(np.diff(lags) > 0), "lags_sec must be finite and strictly increasing")
    _require(lags[0] >= -2 and lags[-1] <= 4, "lags_sec outside author demo [-2,4] second domain")
    roster = _unique_names(manifest.get("expected_participants"), "expected_participants")
    stories = manifest.get("story_splits")
    _require(isinstance(stories, dict) and bool(stories), "story_splits required")
    mode = manifest.get("evaluation_mode")
    _require(mode in {"unsplit_recomputation", "prospective_story_holdout"}, "evaluation_mode must be explicit")
    allowed = {"analysis"} if mode == "unsplit_recomputation" else {"train", "assessment"}
    for story, split in stories.items():
        _name(story, "story_id")
        _require(split in allowed, "story split incompatible with evaluation_mode")
    _require(set(stories.values()) == allowed, "all declared split partitions are required")
    subjects = manifest.get("participants")
    _require(isinstance(subjects, list), "participants must be a list")
    _require(len(subjects) == len(roster) and {p.get("participant_id") for p in subjects} == set(roster), "participant roster must be complete and unique")
    return lags, stories


def evaluate(manifest, arrays):
    """Compute all declared participants, electrodes, conditions, stories and lags.

    arrays maps participant IDs to {'D': time×stimulus×electrode×repetition,
    't': seconds}. Context IDs identify repeatable surrounding arrangements;
    segment IDs identify the same acoustic segment across those arrangements.
    A complete context×repetition×segment design is required per cell.
    """
    lags, story_splits = _validate_manifest(manifest)
    _require(set(arrays) == set(manifest["expected_participants"]), "array participant roster mismatch")
    outputs = []
    audit = []
    observed_stories = set()
    for participant in manifest["participants"]:
        pid = participant["participant_id"]
        electrodes = _unique_names(participant.get("electrode_ids"), "electrode_ids")
        stimuli = _unique_names(participant.get("stimulus_ids"), "stimulus_ids")
        repeats = _unique_names(participant.get("repetition_ids"), "repetition_ids")
        durations = participant.get("stimulus_durations_sec")
        _require(isinstance(durations, dict) and set(durations) == set(stimuli), "stimulus_durations_sec must cover every stimulus")
        durations = {stimulus: _finite_number(value, "stimulus duration") for stimulus, value in durations.items()}
        _require(all(value > 0 for value in durations.values()), "stimulus durations must be positive")
        _require(len(repeats) >= 2, "at least two independent repetitions are required")
        excluded = participant.get("bad_stimuli", {})
        _require(isinstance(excluded, dict) and set(excluded) <= set(stimuli), "bad_stimuli must map declared stimulus IDs to reasons")
        for reason in excluded.values():
            _name(reason, "bad stimulus reason")
        data = _real_array(arrays[pid]["D"], "D")
        times = _real_array(arrays[pid]["t"], "t")
        _require(data.ndim == 4 and data.shape[1:] == (len(stimuli), len(electrodes), len(repeats)), "D axes must be time, stimulus, electrode, repetition")
        _require(times.ndim == 1 and len(times) == data.shape[0] and len(times) >= 2 and np.isfinite(times).all() and np.all(np.diff(times) > 0), "t must be finite, increasing and match D")
        active = [i for i, s in enumerate(stimuli) if s not in excluded]
        _require(bool(active) and np.isfinite(data[:, active]).all(), "all nonexcluded empirical timecourses must be finite")
        epochs = participant.get("epochs")
        _require(isinstance(epochs, list) and epochs, "explicit segment epochs required")
        declared_cells = participant.get("expected_cells")
        _require(isinstance(declared_cells, list) and bool(declared_cells), "expected_cells freezes complete condition/story coverage")
        expected = set()
        for c in declared_cells:
            story = _name(c.get("story_id"), "story_id")
            rate = _speech_rate(c.get("speech_rate"))
            duration = _finite_number(c.get("segment_duration_sec"), "segment_duration_sec")
            _require(story in story_splits and rate > 0 and duration > 0, "invalid expected cell")
            key = (story, rate, duration)
            _require(key not in expected, "duplicate expected cell")
            expected.add(key)
        _require({key[1] < 1 for key in expected} == {False, True}, "both main-experiment speech rates must be represented")
        # key -> context -> segment -> [lag,electrode,repetition]
        cells = defaultdict(lambda: defaultdict(dict))
        excluded_epochs = 0
        covered_stimuli = set()
        epoch_ids = set()
        physical_occurrences = set()
        stimulus_conditions = {}
        for epoch in epochs:
            eid = _name(epoch.get("epoch_id"), "epoch_id")
            _require(eid not in epoch_ids, "duplicate epoch_id")
            epoch_ids.add(eid)
            stimulus = _name(epoch.get("stimulus_id"), "stimulus_id")
            _require(stimulus in stimuli, "unknown stimulus_id")
            covered_stimuli.add(stimulus)
            story = _name(epoch.get("story_id"), "story_id")
            rate = _speech_rate(epoch.get("speech_rate"))
            duration = _finite_number(epoch.get("segment_duration_sec"), "segment_duration_sec")
            key = (story, rate, duration)
            _require(key in expected, "undeclared condition/story cell")
            context = _name(epoch.get("context_id"), "context_id")
            segment = _name(epoch.get("segment_id"), "segment_id")
            onset = _finite_number(epoch.get("onset_sec"), "onset_sec")
            binding = (story, rate)
            _require(stimulus_conditions.get(stimulus, binding) == binding, "one stimulus cannot cross story splits or speech rates")
            stimulus_conditions[stimulus] = binding
            _require(onset >= 0 and onset + duration <= durations[stimulus], "segment lies outside the actual stimulus, including padding")
            occurrence = (stimulus, onset, duration)
            _require(occurrence not in physical_occurrences, "one physical segment occurrence cannot be relabeled across contexts or segment IDs")
            physical_occurrences.add(occurrence)
            if stimulus in excluded:
                excluded_epochs += 1
                continue
            _require(segment not in cells[key][context], "duplicate segment within context and condition")
            sample_times = onset + lags
            _require(sample_times[0] >= times[0] and sample_times[-1] <= times[-1], "lag extraction exceeds recorded time range")
            _require(onset >= times[0] and onset + duration <= times[-1], "segment lies outside recorded range")
            si = stimuli.index(stimulus)
            aligned = np.empty((len(lags), len(electrodes), len(repeats)))
            for ei in range(len(electrodes)):
                for ri in range(len(repeats)):
                    aligned[:, ei, ri] = np.interp(sample_times, times, data[:, si, ei, ri])
            cells[key][context][segment] = aligned
        _require(covered_stimuli == set(stimuli), "every declared stimulus needs epoch coverage, including excluded stimuli")
        _require(set(cells) == expected, "an expected cell has no admissible epochs")
        for (story, rate, duration), contexts in sorted(cells.items()):
            observed_stories.add(story)
            _require(len(contexts) >= 2, "each cell needs at least two distinct contexts")
            context_ids = sorted(contexts)
            segments = sorted(contexts[context_ids[0]])
            _require(len(segments) >= 3, "each cell needs at least three segments")
            _require(all(set(contexts[c]) == set(segments) for c in context_ids), "complete matched segment coverage required; do not silently intersect")
            values = {c: np.stack([contexts[c][s] for s in segments]) for c in context_ids}
            for ei, electrode in enumerate(electrodes):
                for li, lag in enumerate(lags):
                    same, different = [], []
                    for c in context_ids:
                        for r1, r2 in combinations(range(len(repeats)), 2):
                            same.append(_pearson(values[c][:, li, ei, r1], values[c][:, li, ei, r2]))
                    for c1, c2 in combinations(context_ids, 2):
                        for r1, r2 in product(range(len(repeats)), repeat=2):
                            different.append(_pearson(values[c1][:, li, ei, r1], values[c2][:, li, ei, r2]))
                    ceiling, ccc = _aggregate_pairs(same), _aggregate_pairs(different)
                    status = "ok" if ceiling is not None and ccc is not None and ceiling > 0 else "undefined_or_nonpositive_ceiling"
                    normalized = ccc / ceiling if status == "ok" else None
                    if normalized is not None and not np.isfinite(normalized):
                        normalized = None
                        status = "nonfinite_normalization"
                    outputs.append({"participant_id": pid, "electrode_id": electrode,
                        "story_id": story, "split": story_splits[story], "speech_rate": rate,
                        "segment_duration_sec": duration, "lag_sec": float(lag),
                        "n_segments": len(segments), "n_contexts": len(context_ids),
                        "same_context_pair_count": len(same), "different_context_pair_count": len(different),
                        "same_context": ceiling, "diff_context": ccc,
                        "normalized_ccc": normalized,
                        "status": status})
        audit.append({"participant_id": pid, "n_electrodes": len(electrodes),
            "n_expected_cells": len(expected), "n_epochs": len(epochs),
            "excluded_epoch_count": excluded_epochs, "bad_stimuli": excluded})
    _require(observed_stories == set(story_splits), "story roster must be complete")
    return {"task_id": TASK_ID, "schema": SCHEMA + "-result", "cohort_id": manifest["cohort_id"],
        "scientific_qualification": "unknown", "native_parity_verified": False,
        "evaluation_mode": manifest["evaluation_mode"],
        "rows": outputs, "participant_audit": audit,
        "population_summary": summarize(outputs), "holds": HOLDS}


def summarize(rows):
    """Preserve stories; average electrodes within participant, then participants.

    Ratio of mean CCC to mean ceiling is reported separately from the mean of
    electrode-level ratios. No undefined electrode is dropped from a cell.
    """
    grouped = defaultdict(lambda: defaultdict(list))
    for row in rows:
        key = (row["story_id"], row["split"], row["speech_rate"], row["segment_duration_sec"], row["lag_sec"])
        grouped[key][row["participant_id"]].append(row)
    results = []
    for key, participants in sorted(grouped.items()):
        complete = all(r["status"] == "ok" for group in participants.values() for r in group)
        mean_ccc = mean_ceiling = normalized = mean_ratio = None
        if complete:
            mean_ccc = float(np.mean([np.mean([r["diff_context"] for r in group]) for group in participants.values()]))
            mean_ceiling = float(np.mean([np.mean([r["same_context"] for r in group]) for group in participants.values()]))
            normalized = mean_ccc / mean_ceiling
            mean_ratio = _stable_mean([_stable_mean([r["normalized_ccc"] for r in group]) for group in participants.values()])
        results.append(dict(zip(["story_id", "split", "speech_rate", "segment_duration_sec", "lag_sec"], key),
            n_participants=len(participants), n_electrodes=sum(map(len, participants.values())),
            participant_balanced_ccc=mean_ccc, participant_balanced_ceiling=mean_ceiling,
            ratio_of_participant_balanced_means=normalized,
            participant_balanced_mean_of_ratios=mean_ratio, status="ok" if complete else "incomplete_defined_correlations"))
    return results


def load_input(path):
    path = Path(path)
    manifest = json.loads(path.read_text())
    _validate_manifest(manifest)
    arrays = {}
    receipts = []
    for p in manifest["participants"]:
        source = p.get("source", {})
        _require(source.get("role") == "empirical_electrode_timecourses", "cached correlations or model fits cannot substitute for empirical timecourses")
        filename = _name(source.get("npz_path"), "npz_path")
        _require(Path(filename).name not in {"cross_context_correlation.mat", "model_fits.mat"}, "derived results are forbidden empirical input")
        local = Path(filename) if Path(filename).is_absolute() else path.parent / filename
        digest = hashlib.sha256(local.read_bytes()).hexdigest()
        _require(source.get("sha256") == digest, "timecourse file SHA256 mismatch")
        with np.load(local, allow_pickle=False) as packed:
            _require(set(packed.files) == {"D", "t"}, "NPZ must contain exactly D and t")
            arrays[p["participant_id"]] = {"D": packed["D"], "t": packed["t"]}
        receipts.append({"participant_id": p["participant_id"], "sha256": digest, "bytes": local.stat().st_size})
    return manifest, arrays, receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    manifest, arrays, receipts = load_input(args.manifest)
    result = evaluate(manifest, arrays)
    result["input_receipts"] = receipts
    result["manifest_sha256"] = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
