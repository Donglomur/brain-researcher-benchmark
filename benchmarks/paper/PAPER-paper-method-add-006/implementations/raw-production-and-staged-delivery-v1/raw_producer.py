"""Explicit source recording entrypoints; importing this module runs no fits.

Execution requires a separately admitted authentic compute/storage run. These
functions preserve the original grids and scientific methods, adding raw operands
needed by the existing evaluator. A partial range remains a partial checkpoint.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import numpy as np

from dependency_loader import G, R, P, GB, GLB, need
import recorded_glm as RG
import recorded_geometry as RR

SCHEMA = "population_raw_production_binding_v1"
HERE = Path(__file__).resolve().parent


def execution_binding(panel, svc_policy=R.SVC_POLICY):
    """Separate recorder identity makes legacy summary-only resume fail closed."""
    base = P.execution_binding(panel, svc_policy)
    code = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in ("dependency_loader.py", "raw_producer.py", "recorded_glm.py", "recorded_geometry.py")}
    return {"schema": SCHEMA, "original": base, "recording_code": code,
            "raw_operands": ["alpha_oof_predictions", "svc_test_predictions"],
            "qualification": False}


def _limits(max_result_bytes, max_total_bytes, max_capture_bytes):
    need(all(type(v) is int and v > 0 for v in
             (max_result_bytes, max_total_bytes, max_capture_bytes)), "explicit positive byte ceilings required")
    need(max_capture_bytes <= max_result_bytes <= max_total_bytes,
         "capture/result/total ceilings must be nested")


def validate_glm_recorded(result):
    counts = np.asarray(result["counts"])
    held = np.asarray(result.get("alpha_oof_predictions"))
    need(counts.ndim == 2 and held.shape == counts.shape + (10,) and held.dtype == np.dtype(np.float64),
         "complete all-alpha held predictions required; legacy checkpoints cannot resume")
    need(np.array_equal(result["fold_ids"], G.source_fold_ids(len(counts))),
         "original contiguous held-fold identities required")
    return result


def validate_geometry_recorded(result):
    readout = result["readout"]
    prediction = np.asarray(readout.get("svc_test_predictions"))
    teachers = R.indices(readout["valid_teacher_indices"], 500, "recorded teacher", count=None)
    need(len(teachers) > 100 and np.all(np.diff(teachers) > 0),
         "complete sorted unique original teacher identities required")
    need(prediction.shape == (200, len(teachers)) and prediction.dtype == np.dtype(np.float64)
         and np.isfinite(prediction).all(),
         "complete finite raw SVC predictions required; summary-only checkpoints cannot resume")
    train = R.indices(readout["training_positions"], 500, "recorded training", count=300)
    test = R.indices(readout["test_positions"], 500, "recorded test", count=200)
    need(np.array_equal(test, np.setdiff1d(np.arange(500), train)),
         "recorded test positions must be exact original training complement")
    rows = R.identities(result["row_ids"], 500, "recorded native rows")
    R.identities(result["unit_ids"], 19, "recorded native units")
    GB._same(result["training_row_ids"], rows[train], "recorded training rows")
    GB._same(result["test_row_ids"], rows[test], "recorded test rows")
    return result


def run_glm(panel, output, *, max_result_bytes, max_total_bytes, max_capture_bytes,
            start=0, stop=13824):
    """Source-derived P.run_glm, with raw capture and a conservative write ceiling.

    A whole result allowance is reserved before each new fit. The returned write
    charge includes successful output bytes; a failed save must be charged by its
    full reserved allowance by the external run controller. Existing files stay.
    """
    _limits(max_result_bytes, max_total_bytes, max_capture_bytes)
    P.require_runtime()
    need(type(start) is int and type(stop) is int and 0 <= start < stop <= 13824,
         "valid chunk of complete13824-job plan required")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    binding = execution_binding(panel)
    pool_cache, written, charged, resumed = {}, [], 0, 0
    for index, job in enumerate(G.job_plan()):
        if not start <= index < stop:
            continue
        target = output / job["id"]
        if target.exists():
            saved = validate_glm_recorded(P.load_result(target, binding, max_bytes=max_result_bytes))
            need(saved.get("job") == job, "checkpoint job identity differs")
            resumed += 1
            continue
        need(charged + max_result_bytes <= max_total_bytes,
             "reserve complete result allowance before any new fit")
        animal, session, region = job["animal"], job["session_index"], job["region"]
        panel.paired(animal, session)
        if animal not in pool_cache:
            pool_cache[animal] = G.pooled_latents(panel.load_session, animal)
        packet = panel.load_session(animal, session, region)
        result = RG.fit_session_recorded(packet, pool_cache[animal], job["basis_index"],
                                         max_capture_bytes=max_capture_bytes)
        result.update(job=job, case_id=packet["case_id"], packet_pin=packet["packet_pin"],
                      source_asset_id=packet["source_asset_id"], source_epoch=packet["source_epoch"],
                      prediction_roles={"predictions": "original full-row selected-alpha refit",
                                        "oof_predictions": "additional selected-alpha refits; selection exposed all folds",
                                        "alpha_oof_predictions": "recorded original grid held predictions at each alpha"})
        result["source_session_mean_selected_cv_d2"] = float(np.mean(
            result["test_scores"][np.arange(len(result["selected_alpha_indices"])), result["selected_alpha_indices"]]))
        validate_glm_recorded(result)
        pin = P.save_result(target, result, binding, max_bytes=max_result_bytes)
        charged += pin["bytes"]
        written.append(pin)
    return {"schema": "population_raw_glm_chunk_v1", "range": [start, stop], "written": written,
            "resumed": resumed, "charged_successful_output_bytes": charged,
            "full_job_count": 13824, "qualification": False}


def run_geometry(panel, output, *, max_result_bytes, max_total_bytes, max_prediction_bytes,
                 svc_policy=R.SVC_POLICY, stop=64000):
    """Preserve the global source stream; resume starts at its original first job.

    ``stop`` bounds a prefix checkpoint, never an alternative benchmark panel.
    No independent starting offset can skip the earlier RNG continuation.
    """
    _limits(max_result_bytes, max_total_bytes, max_prediction_bytes)
    P.require_runtime()
    need(svc_policy == R.SVC_POLICY, "resumable panel requires current reproducible source policy")
    need(type(stop) is int and 0 < stop <= 64000, "original geometry prefix required")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    binding = execution_binding(panel, svc_policy)
    generators = {region: np.random.RandomState(seed) for region, seed in R.REGION_SEEDS.items()}
    charged, written, resumed = 0, 0, 0
    for index, job in enumerate(R.geometry_plan()):
        if index >= stop:
            break
        target = output / P.geometry_id(job)
        rng = generators[job["region"]]
        before = R.state(rng)
        if target.exists():
            saved = validate_geometry_recorded(P.load_result(target, binding, max_bytes=max_result_bytes))
            need(saved["job"] == job and saved["rng_before"] == before,
                 "geometry checkpoint does not continue identical source stream")
            P.restore_rng(rng, saved["rng_after"])
            resumed += 1
            continue
        need(charged + max_result_bytes <= max_total_bytes,
             "reserve complete result allowance before any new classifier call")
        packet = panel.load_session(job["animal"], job["session"] - 1, job["region"])
        prepared = R.prepare_geometry(packet, job["region"])
        result = RR.geometry_repetition_recorded(prepared["x"], prepared["z"], prepared["row_ids"],
                                                prepared["unit_ids"], rng=rng, repetition=job["repetition"],
                                                svc_policy=svc_policy, max_prediction_bytes=max_prediction_bytes)
        result.update(job=job, case_id=job["case_id"], behavior=prepared["behavior"],
                      packet_pin=packet["packet_pin"], selected_times=prepared["t"][result["row_positions"]],
                      selected_trial_ids=prepared["trial"][result["row_positions"]])
        validate_geometry_recorded(result)
        pin = P.save_result(target, result, binding, max_bytes=max_result_bytes)
        charged += pin["bytes"]
        written += 1
    return {"schema": "population_raw_geometry_chunk_v1", "range": [0, stop],
            "written": written, "resumed": resumed, "charged_successful_output_bytes": charged,
            "full_job_count": 64000, "qualification": False}


def glm_candidate(recorded, *, method_sha256):
    """Project an authenticated recorded source result into the exact raw schema.

    This is an author-reference replay operand, not a participant execution or
    an independently improved model. The operator must authenticate the record.
    """
    validate_glm_recorded(recorded)
    GLB._job(recorded)
    GB.digest(method_sha256)
    return {"schema": "population_glm_candidate_v1", "job_id": recorded["job"]["id"],
            "method_sha256": method_sha256,
            **{key: np.asarray(recorded[key]).copy() for key in
               ("row_ids", "unit_ids", "fold_ids", "alpha_oof_predictions", "selected_alpha_indices")},
            "full_predictions": np.asarray(recorded["predictions"]).copy()}


def geometry_reference(prepared, recorded, *, checkpoint_sha256, reference_chain):
    """Use the newly retained raw SVC matrix in the unchanged reference bridge."""
    validate_geometry_recorded(recorded)
    prediction = recorded["readout"]["svc_test_predictions"]
    return GB.make_reference(prepared, recorded, prediction, checkpoint_sha256=checkpoint_sha256,
                             source_prediction_sha256=R.array_identity(prediction)["sha256"],
                             reference_chain=reference_chain)
