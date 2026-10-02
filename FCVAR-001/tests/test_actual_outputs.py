"""AUTHORING ONLY: gated genuine-output equivalence and component controls.

Never add this module to production scoring: tolerance/cap closure under a
second serialization or perturbation is not required of arbitrary submissions.
Requires the shared session-scoped original_reference fixture and explicit
REPAIR_ORACLE_OUTPUT. No source reconstruction or original execution occurs
at import. Originals remain untouched; copies are detached and removed after
each case. Ineffective/unavailable controls are reported, not called negatives.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
import os
import shutil

import numpy as np
import pytest

import artifact_reader as a
import proof_of_work as p

AUTHORING_ONLY = True
STAT_FILES = ("variability.csv", "surrogate_statistics.csv", "dynamics.json")


def hashes(root, names=a.REQUIRED):
    return {name: hashlib.sha256(a.read_bytes(root / name, 64*2**20)).hexdigest() for name in names}


def read_arrays(root):
    return a.parse_npz(a.read_bytes(root / "roi_evidence.npz", a.CAPS["npz"]))


def write_json(path, value):
    path.write_text(json.dumps(value, allow_nan=False, indent=2)+"\n", encoding="utf-8")


def read_json(path):
    # The original full artifact set has already passed strict bounded parsing.
    return json.loads(a.read_bytes(path, a.CAPS["json"]))


def write_csv(path, rows):
    assert rows
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def write_statistics(root, analyses, dynamics):
    write_csv(root / "variability.csv", [row for result in analyses for row in result["windows"]])
    write_csv(root / "surrogate_statistics.csv", [row for result in analyses for row in result["surrogates"]])
    write_json(root / "dynamics.json", dynamics)


@pytest.fixture(scope="session")
def actual_original(original_reference):
    configured = os.environ.get("REPAIR_ORACLE_OUTPUT")
    assert configured, "REPAIR_ORACLE_OUTPUT must be explicit for authoring-only genuine controls"
    root = a.guarded_path(configured, directory=True)
    before = hashes(root)
    assert p.validate_output_directory(root, original_reference)["status"] == "accepted"
    yield root
    assert hashes(root) == before, "original output bytes changed during authoring QA"


@pytest.fixture(scope="session")
def actual_replay(actual_original, original_reference):
    kernel = p.load_kernel()
    arrays = read_arrays(actual_original)
    accepted = p.canonical_primitives(arrays, original_reference)
    seed = a.integer(read_json(actual_original / "dynamics.json")["seed"], json_number=True)
    analyses = [kernel.analyze_subject(accepted[sid], original_reference["persons"][sid]["clean"],
                                      original_reference["persons"][sid]["active"], sid, seed)
                for sid in original_reference["participant_ids"]]
    return dict(kernel=kernel, accepted=accepted, seed=seed, analyses=analyses,
                dynamics=kernel.summarize_subjects(analyses, original_reference["participant_ids"]))


@pytest.fixture
def candidate(tmp_path, actual_original):
    output = tmp_path / "detached-output"
    output.mkdir()
    for name in a.REQUIRED:
        # Copy bytes, never hardlink or preserve an unwritable original mode.
        shutil.copyfile(actual_original / name, output / name)
    yield output
    assert output.parent == tmp_path and not output.is_symlink()
    shutil.rmtree(output)  # exactly this newly created per-case directory only


def replay_accepted(arrays, reference, kernel, seed):
    accepted = p.canonical_primitives(arrays, reference)
    results = [kernel.analyze_subject(accepted[sid], reference["persons"][sid]["clean"],
                                     reference["persons"][sid]["active"], sid, seed)
               for sid in reference["participant_ids"]]
    return results, kernel.summarize_subjects(results, reference["participant_ids"])


def rounded_scalars(value):
    if isinstance(value, dict): return {k: rounded_scalars(v) for k, v in value.items()}
    if isinstance(value, list): return [rounded_scalars(v) for v in value]
    if isinstance(value, (float, np.floating)): return round(float(value), 6)
    return value


@pytest.mark.parametrize("mode", ["baseline", "coherent_keys", "phase_float32", "six_decimal_scalars", "source_close_own_replay"])
def test_actual_equivalent_positive(candidate, original_reference, actual_replay, mode, record_property):
    record_property("case_role", "genuine_positive")
    if mode == "coherent_keys":
        z = read_arrays(candidate)
        for key in ("participant_ids", "roi_ids", "roi_labels", "frame_subject", "frame_index", "phase_subject", "phase_window", "frequency_index", "surrogate_ids"):
            z[key] = z[key][::-1]
        for key in ("geometry_present", "n_voxels", "support_sha256", "roi_active", "raw_sample_sd", "prestandardization_centered_l2", "activity_threshold", "full_clean_centered_l2", "raw_roi_mean", "clean_roi_series", "phase_angles"):
            z[key] = z[key][::-1, ::-1]
        np.savez(candidate / "roi_evidence.npz", **z)
        for name in ("cohort.csv", "variability.csv", "surrogate_statistics.csv"):
            rows = a.parse_csv(a.read_bytes(candidate/name, a.CAPS["csv"]))
            rows = [{k: row[k] for k in reversed(list(row))} for row in rows[::-1]]
            write_csv(candidate/name, rows)
        metadata = read_json(candidate/"run_metadata.json")
        metadata["source_files"].reverse(); metadata["source_observed"]["roi_labels"].reverse()
        write_json(candidate/"run_metadata.json", metadata)
        dynamics = read_json(candidate/"dynamics.json")
        dynamics["windows"].reverse(); dynamics["window_lengths_tr"].reverse()
        write_json(candidate/"dynamics.json", dynamics)
    elif mode == "phase_float32":
        z = read_arrays(candidate)
        z["phase_angles"] = z["phase_angles"].astype(np.float32)
        np.savez(candidate / "roi_evidence.npz", **z)
    elif mode == "six_decimal_scalars":
        write_statistics(candidate, rounded_scalars(actual_replay["analyses"]), rounded_scalars(actual_replay["dynamics"]))
    elif mode == "source_close_own_replay":
        z = read_arrays(candidate)
        before = z["clean_roi_series"].copy()
        z["clean_roi_series"] = before.astype(float) * (1.+1e-9)
        changed = bool(np.any(z["clean_roi_series"] != before))
        results, dynamics = replay_accepted(z, original_reference, actual_replay["kernel"], actual_replay["seed"])
        np.savez(candidate / "roi_evidence.npz", **z)
        write_statistics(candidate, results, dynamics)
        # All-inactive canonical sources can make the perturbation a no-op;
        # never assert that their p/status must change or count this as a test
        # of a genuinely changed active source primitive.
        record_property("primitive_change_effective", changed)
        record_property("positive_variant_status", "changed_own_series" if changed else "zero_series_roundtrip_only")
    assert p.validate_output_directory(candidate, original_reference)["status"] == "accepted"
    record_property("control_status", "positive_accepted")


@pytest.mark.parametrize("mode", ["raw_changed", "clean_changed", "literal_subject", "frame_missing", "roi_missing", "support_flip", "support_digest", "phase_changed", "source_pin", "metadata_seed", "rank_changed", "null_row_dropped", "failure_marker"])
def test_actual_effective_binding_negative(candidate, original_reference, mode, record_property):
    record_property("case_role", "binding_negative")
    before = hashes(candidate)
    if mode in ("raw_changed", "clean_changed", "literal_subject", "frame_missing", "roi_missing", "support_flip", "support_digest", "phase_changed"):
        z = read_arrays(candidate)
        if mode in ("raw_changed", "clean_changed"):
            key = "raw_roi_mean" if mode == "raw_changed" else "clean_roi_series"
            atol, rtol = p.RAW_TOL if mode == "raw_changed" else p.CLEAN_TOL
            previous = float(z[key][0, 0])
            z[key] = z[key].astype(float)
            z[key][0, 0] = previous + 100*(atol+rtol*abs(previous)) + .001
            assert z[key][0, 0] != previous
        elif mode == "literal_subject":
            sid = str(z["participant_ids"][0]); altered = str(int(sid))
            assert altered != sid, "prospectively fixed first ID has leading zeroes"
            z["participant_ids"][0] = altered
        elif mode == "frame_missing":
            for key in ("frame_subject", "frame_index", "raw_roi_mean", "clean_roi_series"): z[key] = z[key][:-1]
        elif mode == "roi_missing":
            z["roi_ids"] = z["roi_ids"][:-1]
        elif mode == "support_flip": z["roi_active"][0, 0] = not z["roi_active"][0, 0]
        elif mode == "support_digest":
            old = str(z["support_sha256"][0, 0]); z["support_sha256"][0, 0] = ("0" if old[0] != "0" else "1")+old[1:]
        elif mode == "phase_changed":
            previous = float(z["phase_angles"][1, 0]); z["phase_angles"][1, 0] = previous+.01
            assert z["phase_angles"][1, 0] != previous
        np.savez(candidate / "roi_evidence.npz", **z)
    elif mode in ("source_pin", "metadata_seed", "rank_changed"):
        meta = read_json(candidate/"run_metadata.json")
        if mode == "source_pin":
            old = meta["source_manifest_sha256"]
            meta["source_manifest_sha256"] = ("0" if old[0] != "0" else "1")+old[1:]
        elif mode == "metadata_seed": meta["seed"] = (meta["seed"]+1) % (2**32)
        else:
            sid = next(iter(meta["analysis_observed"]["persons"]))
            meta["analysis_observed"]["persons"][sid]["cleaning_rank"] += 1
        write_json(candidate/"run_metadata.json", meta)
    elif mode == "null_row_dropped":
        rows = a.parse_csv(a.read_bytes(candidate/"surrogate_statistics.csv", a.CAPS["csv"]))
        rows.pop(); write_csv(candidate/"surrogate_statistics.csv", rows)
    else: (candidate/"failure_report.json").symlink_to(candidate/"absent")
    assert mode == "failure_marker" or hashes(candidate) != before, "no-op mutation is not a negative"
    with pytest.raises(ValueError): p.validate_output_directory(candidate, original_reference)
    record_property("control_status", "effective_rejection")


def _scalar_snapshot(analyses, dynamics):
    return {"variability": [row for item in analyses for row in item["windows"]],
            "surrogates": [row for item in analyses for row in item["surrogates"]], "dynamics": dynamics}


def observable_gaps(expected, actual):
    """Compare every scientific scalar, status, exact count and draw indicator."""
    exact, numerical, max_gap = 0, 0, 0.
    def visit(left, right):
        nonlocal exact, numerical, max_gap
        if isinstance(left, dict):
            assert isinstance(right, dict) and set(left) == set(right)
            for key in left: visit(left[key], right[key])
        elif isinstance(left, list):
            assert isinstance(right, list) and len(left) == len(right)
            for x, y in zip(left, right): visit(x, y)
        elif isinstance(left, (float, np.floating)) and isinstance(right, (float, np.floating)):
            gap = abs(float(left)-float(right)); max_gap = max(max_gap, gap)
            numerical += int(gap > p.DERIVED_TOL[0] + p.DERIVED_TOL[1]*abs(float(left)))
        else:
            exact += int(type(left) is not type(right) or left != right)
    visit(expected, actual)
    return {"n_exact_fields_changed": exact, "n_float_values_over_public_tolerance": numerical,
            "max_absolute_numeric_difference": max_gap, "effective": bool(exact or numerical)}


def _raw_r_statistic(series, window, kernel):
    """Explicit wrong-component control: omit Fisher transform, keep ddof1."""
    centered, _, norms = kernel._window_vectors(series, window)
    assert len(centered) >= 2 and np.all(norms > 0)
    units = np.ascontiguousarray(centered / norms[:, None, :])
    corr = np.matmul(units.transpose(0, 2, 1), units)
    assert np.isfinite(corr).all() and np.max(np.abs(corr)) <= 1+1e-12
    upper = np.triu_indices(series.shape[1], 1)
    values = np.ascontiguousarray(np.clip(corr[:, upper[0], upper[1]], -1., 1.))
    deviations = values-np.mean(values, axis=0, dtype=np.float64)
    sd = np.sqrt(np.sum(deviations*deviations, axis=0, dtype=np.float64)/(len(values)-1))
    sd[np.all(values == values[:1], axis=0)] = 0.
    return float(np.mean(sd, dtype=np.float64))


def component_candidate(analyses, dynamics, reference, accepted, kernel, mode):
    """No source modification; produce a declared wrong-method scalar control."""
    altered = copy.deepcopy(analyses)
    supported_cells = 0
    rng = np.random.default_rng(194001)  # counterfeit-null diagnostic only
    for item in altered:
        sid = item["subject"]
        active = reference["persons"][sid]["active"]
        clean = np.ascontiguousarray(accepted[sid][:, active])
        for row in item["windows"]:
            w = row["window_tr"]
            slots = [slot for slot in item["surrogates"] if slot["window_tr"] == w]
            observed = dict(status=row["observed_status"], mean_edge_sd=row["mean_edge_sd"])
            if mode == "ratio_of_group_means": continue
            constructed = False
            if mode == "gaussian_null":
                if row["inference_status"] != "ok": continue
                null_mean = row["mean_edge_sd_null"]
                counterfeit = np.abs(rng.normal(null_mean, .1*max(1., null_mean), size=50))
                for slot, value in zip(slots, counterfeit): slot["mean_edge_sd"] = float(value)
                constructed = True
            elif mode == "ddof0":
                if row["n_windows"] < 2: continue
                # Exact relation for every edge when only sample-SD ddof changes.
                factor = math.sqrt((row["n_windows"]-1)/row["n_windows"])
                if observed["mean_edge_sd"] is not None: observed["mean_edge_sd"] *= factor; constructed = True
                for slot in slots:
                    if slot["mean_edge_sd"] is not None: slot["mean_edge_sd"] *= factor; constructed = True
            elif mode == "raw_r_instead_of_fisher":
                if observed["mean_edge_sd"] is not None:
                    observed["mean_edge_sd"] = _raw_r_statistic(clean, w, kernel); constructed = True
                for slot in slots:
                    if slot["mean_edge_sd"] is not None:
                        phase = item["phases"][w][slot["surrogate_id"]]
                        slot["mean_edge_sd"] = _raw_r_statistic(kernel.phase_surrogate(clean, phase), w, kernel)
                        constructed = True
            elif mode not in ("median_null_mean", "inverse_ratio", "no_plus_one", "strict_ties"):
                raise AssertionError("unknown numerical control")
            summary, comparisons = kernel.summarize_slots(observed, slots)
            if mode == "median_null_mean" and summary["n_null_defined"] == 50:
                ordered = sorted(slot["mean_edge_sd"] for slot in slots)
                median = math.fsum(ordered[24:26])/2
                summary["mean_edge_sd_null"] = median
                if observed["mean_edge_sd"] is not None:
                    summary["ratio_status"] = "zero_null_mean" if median == 0 else "ok"
                    summary["observed_over_null_ratio"] = None if median == 0 else observed["mean_edge_sd"]/median
                constructed = True
            elif mode == "inverse_ratio" and summary["ratio_status"] == "ok" and observed["mean_edge_sd"] > 0:
                summary["observed_over_null_ratio"] = summary["mean_edge_sd_null"]/observed["mean_edge_sd"]
                constructed = True
            elif mode == "no_plus_one":
                summary["p_denominator"] = 50
                if summary["n_exceedances"] is not None:
                    summary["p_numerator"] = summary["n_exceedances"]
                    summary["p_value"] = summary["p_numerator"]/50
                    summary["significant"] = 20*summary["p_numerator"] < 50
                constructed = True  # exact always-retained denominator changes
            elif mode == "strict_ties":
                comparisons = [None if observed["mean_edge_sd"] is None or slot["mean_edge_sd"] is None
                               else bool(slot["mean_edge_sd"] > observed["mean_edge_sd"]) for slot in slots]
                if summary["inference_status"] == "ok":
                    count = sum(comparisons)
                    summary.update(n_exceedances=count, p_numerator=1+count, p_value=(1+count)/51,
                                   significant=20*(1+count)<51)
                constructed = any(value is not None for value in comparisons)
            if constructed: supported_cells += 1
            row.update(summary)
            for slot, indicator in zip(slots, comparisons): slot["exceeds_observed"] = indicator
    result = kernel.summarize_subjects(altered, reference["participant_ids"])
    if mode == "ratio_of_group_means":
        for row in result["windows"]:
            target = row["mean_subject_observed_over_null_ratio"]
            obs = row["mean_observed_edge_sd"]["value"]
            null = row["mean_null_edge_sd"]["value"]
            if target["status"] == "ok" and obs is not None and null is not None and null > 0:
                target["value"] = obs/null; supported_cells += 1
    gaps = observable_gaps(_scalar_snapshot(analyses, dynamics), _scalar_snapshot(altered, result))
    return altered, result, {"construction": "constructed" if supported_cells else "unavailable_support",
                             "n_constructed_cells": supported_cells, **gaps}


def validate_scientific_receipts(root, expected_analyses, expected_dynamics):
    rows = a.parse_csv(a.read_bytes(root/"variability.csv", a.CAPS["csv"]))
    p.table(rows, [row for item in expected_analyses for row in item["windows"]],
            ("subject", "window_tr"), ("window_tr",), context="actual scientific variability")
    draws = a.parse_csv(a.read_bytes(root/"surrogate_statistics.csv", a.CAPS["csv"]))
    p.table(draws, [row for item in expected_analyses for row in item["surrogates"]],
            ("subject", "window_tr", "surrogate_id"), ("window_tr", "surrogate_id"), context="actual scientific nulls")
    p.validate_dynamics(a.parse_json(a.read_bytes(root/"dynamics.json", a.CAPS["json"])), expected_dynamics)


@pytest.mark.parametrize("mode", ["gaussian_null", "median_null_mean", "inverse_ratio", "no_plus_one", "strict_ties", "ddof0", "raw_r_instead_of_fisher", "ratio_of_group_means"])
def test_actual_numerical_components(candidate, original_reference, actual_replay, mode, record_property):
    record_property("case_role", "numerical_component_control")
    preserved_names = tuple(name for name in a.REQUIRED if name not in STAT_FILES)
    before = hashes(candidate, preserved_names)
    analyses, dynamics, report = component_candidate(actual_replay["analyses"], actual_replay["dynamics"],
        original_reference, actual_replay["accepted"], actual_replay["kernel"], mode)
    write_statistics(candidate, analyses, dynamics)
    assert hashes(candidate, preserved_names) == before, "control changed source primitives or provenance"
    for key, value in report.items(): record_property(key, value)
    if report["effective"]:
        with pytest.raises(ValueError): validate_scientific_receipts(candidate, actual_replay["analyses"], actual_replay["dynamics"])
        with pytest.raises(ValueError): p.validate_output_directory(candidate, original_reference)
        record_property("control_status", "effective_rejection")
        record_property("numerical_rejection_demonstrated", True)
    else:
        validate_scientific_receipts(candidate, actual_replay["analyses"], actual_replay["dynamics"])
        assert p.validate_output_directory(candidate, original_reference)["status"] == "accepted"
        record_property("control_status", "control_not_constructed" if report["construction"] != "constructed" else "control_not_discriminating")
        record_property("numerical_rejection_demonstrated", False)
