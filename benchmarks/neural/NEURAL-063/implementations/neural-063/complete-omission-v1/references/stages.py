"""Concrete authorized numerical/reference/control stage handlers.

No stage or fitter is run by importing this module. All authentic execution is
behind the owner engine plus ctx.require_scientific at this sole entrypoint.
"""
from __future__ import annotations
import math
from owner.io import Artifact, ContractError
from owner.model import StageResult
from owner import scoring
from . import features, primary, independent, controls, jobs
from .schema import (LAMBDA_GRID, SEEDS, MICE, admit_rows, timing_view,
                     expected_grid_ids, finite_number, object_hash)

CAP = 1_500_000_000
ROLES = {"fit_rows": "fit_rows", "validation_rows": "validation_rows", "fit_scale": "fit_scale",
         "feature_bank": "reference_feature_bank", "model_bank": "reference_model_bank",
         "selection": "reference_selection", "direct_controls": "reference_direct_controls",
         "independent_models": "reference_independent_models", "qualification": "reference_qualification",
         "perturbation_bank": "reference_perturbation_bank", "query_T": "query_T", "query_N": "query_N",
         "query_index": "query_index", "reference_predictions": "reference_predictions",
         "independent_predictions": "reference_independent_predictions"}
REQUIRED = {
    "R00": {"fit_rows", "fit_scale"},
    "R01": {"fit_rows", "fit_scale", "feature_bank"},
    "R02": {"validation_rows", "fit_scale", "model_bank"},
    "C00": {"fit_rows", "validation_rows", "fit_scale"},
    "R03": {"fit_rows", "validation_rows", "fit_scale", "model_bank", "selection", "direct_controls"},
    "C01": {"fit_rows", "validation_rows", "fit_scale", "selection"},
    "RC00": {"model_bank", "selection", "independent_models", "qualification", "perturbation_bank"},
    "R04": {"selection", "query_T", "query_N", "query_index"},
    "R05": {"independent_models", "query_T", "query_N", "query_index"},
    "R06": {"reference_predictions", "independent_predictions", "query_index", "fit_scale"},
    "C02": {"direct_controls", "perturbation_bank", "query_T", "query_N", "query_index"},
}


def _read(ctx, name):
    return ctx.read_input(name, roles={ROLES[name]}, cap=CAP)


def _read_ref(ctx, ref, role):
    return ctx.store.read_json(ref, roles={role}, cap=CAP)


def _rows(ctx, split):
    return admit_rows(_read(ctx, split + "_rows"), split, view="N")


def _scale(ctx, fit_ref=None):
    obj = _read(ctx, "fit_scale")
    if (obj.get("schema") != "neural063_fit_scale_v2" or obj.get("fit_mice") != 73
            or not isinstance(obj.get("fit_rows_sha256"), str)):
        raise ContractError("frozen FIT-only scale binding required")
    sd = finite_number(obj.get("training_target_sd"))
    if sd <= 0 or (fit_ref is not None and obj["fit_rows_sha256"] != fit_ref.sha256):
        raise ContractError("FIT scale identity/positivity mismatch")
    return sd


def _emit(ctx, outputs, key, body, role):
    ref = ctx.write_json(key + ".json", body, role=role)
    outputs[key] = ref
    return ref


def _result(outputs, outcome="complete", **measurements):
    return StageResult(outcome, outputs, measurements=measurements)


def _fail(ctx, outputs, operation, exc, **facts):
    _emit(ctx, outputs, "failure", {"schema": "neural063_reference_failure_v1", "stage": ctx.stage,
          "operation": operation, "error_type": type(exc).__name__, "message": str(exc)[:2048],
          "facts": facts, "no_replacement_or_pruning": True}, "reference_failure")
    return StageResult("failed", outputs, measurements=facts, reasons=[operation + ": " + str(exc)[:2048]])


def _allocation(ctx, job_id, rows, dimension, independent_job=False):
    plans = ctx.parameters.get("fit_allocations")
    if not isinstance(plans, dict) or job_id not in plans:
        raise ContractError("full per-job numerical allocation absent: " + job_id)
    return jobs.validate_allocation(plans[job_id], rows=rows, dimension=dimension, independent=independent_job)


def _job(ctx, outputs, job_id, kind, arguments, rows, dimension):
    receipt = None
    try:
        plan = _allocation(ctx, job_id, rows, dimension, kind == "independent")
        # jobs.run performs independent per-fit CPU/AS/affinity/wall enforcement.
        receipt = jobs.run(kind, arguments, {k: plan[k] for k in ("rows", "dimension", "wall_seconds", "cpu_seconds", "ram_bytes", "cpu_ids", "result_bytes", "workspace_bytes", "input_object_bytes")},
                           rows=rows, dimension=dimension, require_scientific=ctx.require_scientific)
        model = receipt.pop("model")
        training_binding = object_hash(arguments[0])
        if model is not None:
            model["fit_value_sha256"] = training_binding
        receipt["fit_value_sha256"] = training_binding
        receipt["input_artifact_sha256s"] = {name: ref.sha256 for name, ref in ctx.inputs.items()}
        receipt.update(schema="neural063_fit_job_v1", job_id=job_id, algorithm=kind)
        model_ref = None
        if model is not None:
            role = "reference_independent_model" if kind == "independent" else "reference_primary_model"
            model_ref = _emit(ctx, outputs, "model_" + job_id, model, role)
            receipt["model"] = model_ref.object()
        job_ref = _emit(ctx, outputs, "job_" + job_id, receipt, "reference_fit_job")
        if receipt.get("closure", {}).get("owned_stage_escalation_required"):
            ctx.abort_for_containment(job_ref)
        record = {"status": receipt["status"], "job_id": job_id,
                  "model": model_ref.object() if model_ref else None, "job_receipt": job_ref.object()}
        return model, record
    except BaseException as exc:
        ctx.abort_for_containment(None, initiating_failure={"where":"numerical_call_or_failure_custody", "type":type(exc).__name__, "message":str(exc)[:2048], "job_id":job_id, "known_receipt":receipt})
        raise ContractError("owned containment escalation unexpectedly returned")


def _check_job(ctx, record, expected_id, kind):
    if not isinstance(record, dict) or record.get("status") != "complete" or record.get("job_id") != expected_id:
        raise ContractError("required numerical job is not complete")
    receipt = _read_ref(ctx, record["job_receipt"], "reference_fit_job")
    if (receipt.get("schema") != "neural063_fit_job_v1" or receipt.get("job_id") != expected_id
            or receipt.get("algorithm") != kind or receipt.get("status") != "complete"
            or receipt.get("process_exit_code") != 0 or receipt.get("model") != record["model"]):
        raise ContractError("fit job receipt/model identity mismatch")
    role = "reference_independent_model" if kind == "independent" else "reference_primary_model"
    model = _read_ref(ctx, record["model"], role)
    if receipt.get("fit_value_sha256") != model.get("fit_value_sha256"):
        raise ContractError("fit numerical inputs not bound to model receipt")
    if expected_id.startswith(("T-", "N-")):
        view, basis, lam = expected_id.split("-")
        if (model.get("view"), model.get("basis"), model.get("lambda")) != (view, basis, float(lam)):
            raise ContractError("model does not implement its exact grid member")
    if expected_id.startswith("independent-") and model.get("view") != expected_id.rsplit("-", 1)[1]:
        raise ContractError("independent model view mismatch")
    if expected_id.startswith("perturb_") and model.get("view") != "N":
        raise ContractError("history perturbation must retain complete N model")
    if model.get("fit_mice") != 73 or model.get("outputs") != 3:
        raise ContractError("model omitted full FIT support or outputs")
    if kind == "primary":
        residual = finite_number(model.get("relative_normal_equation_residual"))
        if not 0 <= residual <= 1e-10:
            raise ContractError("primary residual criterion not met")
    return model


def _prediction_scores(predictions, rows, sd, mice):
    admitted = scoring.admit_predictions(predictions, [r["id"] for r in rows])
    return scoring.absolute(admitted, rows, sd, mice)


def _select(grid, view):
    candidates = [x for x in grid.values() if x["view"] == view]
    if len(candidates) != 14: raise ContractError("complete fourteen-model view required")
    finite = [x for x in candidates if x["score"]["primary"]["status"] == "finite"]
    if not finite: return None
    return min(finite, key=lambda x: (x["score"]["primary"]["value"], 0 if x["basis"] == "L" else 1, -x["lambda"]))


def _comparison(a, b):
    paired = scoring.paired(a["per_mouse"], b["per_mouse"], 15)
    interval = scoring.bootstrap(paired, seed=63015)
    return {**paired, "bootstrap": interval}


def _superiority(comparison):
    point, interval = comparison["contrast"], comparison["bootstrap"]["interval"]
    if point["status"] != "finite" or interval["status"] != "finite":
        return "not_demonstrated_numeric_unavailable"
    return "met" if point["value"] <= -0.001 and interval["upper"] < 0 else "not_met"


def _equivalence(primary_table, independent_table):
    if [x["id"] for x in primary_table] != [x["id"] for x in independent_table]:
        raise ContractError("independent prediction IDs/order differ")
    if not primary_table: raise ContractError("empty equivalence table")
    maximum = 0.0; discrepancy = 0.0
    for a, b in zip(primary_table, independent_table):
        if len(a["values"]) != 3 or len(b["values"]) != 3:
            raise ContractError("equivalence requires all three bins")
        for x, y in zip(a["values"], b["values"]):
            x, y = finite_number(x), finite_number(y)
            maximum = max(maximum, abs(x)); discrepancy = max(discrepancy, abs(x - y))
    tolerance = 1e-8 * max(1.0, maximum)
    return {"schema": "neural063_prediction_equivalence_v1", "rows": len(primary_table), "bins": 3,
            "max_abs_primary_normalized": maximum,
            "max_abs_discrepancy": discrepancy if math.isfinite(discrepancy) else None,
            "discrepancy_status": "finite" if math.isfinite(discrepancy) else "positive_infinity",
            "tolerance": tolerance,
            "status": "equivalent" if math.isfinite(discrepancy) and discrepancy <= tolerance else "not_equivalent"}


def _query(ctx):
    index = _read(ctx, "query_index")
    if (index.get("schema") != "neural063_query_index_v2" or index.get("target_shape") != [3]
            or index.get("heldout_mouse_count") != 19):
        raise ContractError("fixed complete query index required")
    ids = index.get("ids")
    if not isinstance(ids, list) or not ids or ids != sorted(set(ids)):
        raise ContractError("ordered unique complete query identity index required")
    t = admit_rows(_read(ctx, "query_T"), "query", view="T", require_target=False)
    n = admit_rows(_read(ctx, "query_N"), "query", view="N", require_target=False)
    if [r["id"] for r in t] != ids or [r["id"] for r in n] != ids or t != timing_view(n):
        raise ContractError("T/N rows differ in schedule, identity or allowed context")
    return {"T": t, "N": n}, ctx.inputs["query_index"].sha256


def R00(ctx):
    outputs = {}; rows = _rows(ctx, "fit"); sd = _scale(ctx, ctx.inputs["fit_rows"])
    if scoring.training_scale(rows) != sd:
        raise ContractError("provided target scale differs from complete FIT-only hierarchy")
    bank = {"schema": "neural063_feature_bank_v2", "fit_rows_sha256": ctx.inputs["fit_rows"].sha256,
            "fit_scale_sha256": ctx.inputs["fit_scale"].sha256, "states": {}, "dimensions": {}}
    for view in ("T", "N"):
        selected_rows = timing_view(rows) if view == "T" else rows
        for basis in ("L", "Q"):
            key = view + "-" + basis
            descriptor = features.layout(selected_rows, view, basis)
            dimension = descriptor["nonintercept_dimension"]
            # All full-data allocations must be provided before constructing the
            # corresponding feature statistics, not supplied after a fit succeeds.
            for lam in LAMBDA_GRID:
                _allocation(ctx, f"{view}-{basis}-{lam:g}", len(rows), dimension)
            _allocation(ctx, "independent-" + key, len(rows), dimension, True)
            state = features.fit_statistics(selected_rows, descriptor)
            state_ref = _emit(ctx, outputs, "features_" + key, state, "reference_feature_state")
            bank["states"][key] = state_ref.object()
            bank["dimensions"][key] = {"rows": len(rows), "columns_without_intercept": dimension}
    _emit(ctx, outputs, "feature_bank", bank, "reference_feature_bank")
    return _result(outputs, feature_families=4, fit_mice=73, grid_members=28)


def R01(ctx):
    outputs = {}; rows = _rows(ctx, "fit"); sd = _scale(ctx, ctx.inputs["fit_rows"]); bank = _read(ctx, "feature_bank")
    if bank.get("schema") != "neural063_feature_bank_v2" or bank.get("fit_rows_sha256") != ctx.inputs["fit_rows"].sha256 or bank.get("fit_scale_sha256") != ctx.inputs["fit_scale"].sha256:
        raise ContractError("feature bank belongs to another FIT packet")
    result = {"schema": "neural063_model_bank_v2", "fit_rows_sha256": ctx.inputs["fit_rows"].sha256,
              "fit_scale_sha256": ctx.inputs["fit_scale"].sha256, "models": {}, "required_ids": expected_grid_ids()}
    try:
        for view in ("T", "N"):
            view_rows = timing_view(rows) if view == "T" else rows
            for basis in ("L", "Q"):
                state = _read_ref(ctx, bank["states"][view + "-" + basis], "reference_feature_state")
                for lam in LAMBDA_GRID:
                    key = f"{view}-{basis}-{lam:g}"
                    _, record = _job(ctx, outputs, key, "primary", (view_rows, state, sd, lam), len(rows), state["layout"]["nonintercept_dimension"])
                    result["models"][key] = record
                    if record["status"] != "complete": raise ContractError("required primary job failed: " + key)
    except Exception as exc:
        result["complete"] = False
        _emit(ctx, outputs, "model_bank", result, "reference_model_bank")
        return _fail(ctx, outputs, "complete_28_fit_grid", exc, required_jobs=28, attempted_jobs=len(result["models"]))
    result["complete"] = True
    _emit(ctx, outputs, "model_bank", result, "reference_model_bank")
    return _result(outputs, required_jobs=28, completed_jobs=28)


def R02(ctx):
    outputs = {}; rows = _rows(ctx, "validation"); sd = _scale(ctx); bank = _read(ctx, "model_bank")
    if bank.get("schema") != "neural063_model_bank_v2" or set(bank.get("models", {})) != set(expected_grid_ids()) or bank.get("complete") is not True or bank.get("fit_scale_sha256") != ctx.inputs["fit_scale"].sha256:
        raise ContractError("all 28 exact fitted members and scale required")
    candidates = {}
    try:
        for key in expected_grid_ids():
            model = _check_job(ctx, bank["models"][key], key, "primary")
            if model["target_sd"] != sd: raise ContractError("model target scale differs from frozen FIT scale")
            view_rows = timing_view(rows) if model["view"] == "T" else rows
            predictions = primary.predict(view_rows, model)
            scores = _prediction_scores(predictions, rows, sd, 15)
            pred = _emit(ctx, outputs, "validation_" + key, {"schema": "neural063_reference_validation_predictions_v2", "model_id": key, "predictions": predictions}, "reference_validation_predictions")
            candidates[key] = {"model_id": key, "view": model["view"], "basis": model["basis"], "lambda": model["lambda"],
                               "model_record": bank["models"][key], "predictions": pred.object(), "score": scores}
    except Exception as exc:
        _emit(ctx, outputs, "partial_validation_grid", {"schema": "neural063_reference_partial_grid_v1", "candidates": candidates, "required_ids": expected_grid_ids()}, "reference_partial_grid")
        return _fail(ctx, outputs, "complete_28_validation_predictions", exc, required_jobs=28, completed_predictions=len(candidates))
    selected = {v: _select(candidates, v) for v in ("T", "N")}
    selection = {"schema": "neural063_reference_selection_v2", "validation_rows_sha256": ctx.inputs["validation_rows"].sha256,
                 "fit_scale_sha256": ctx.inputs["fit_scale"].sha256, "candidates": candidates,
                 "selected": selected, "refit_on_validation": False,
                 "status": "selected" if all(selected.values()) else "no_finite_winner"}
    _emit(ctx, outputs, "selection", selection, "reference_selection")
    outcome = "complete" if all(selected.values()) else "terminated_before_query_reference_selection_unavailable"
    return _result(outputs, outcome, grid_outcomes_retained=28, validation_mice=15)


def C00(ctx):
    outputs = {}; fit = _rows(ctx, "fit"); val = _rows(ctx, "validation"); sd = _scale(ctx, ctx.inputs["fit_rows"])
    mean = controls.fit_mean(fit); predictions = controls.direct(val, mean)
    body = {"schema": "neural063_direct_controls_v2", "fit_rows_sha256": ctx.inputs["fit_rows"].sha256,
            "validation_rows_sha256": ctx.inputs["validation_rows"].sha256,
            "fit_scale_sha256": ctx.inputs["fit_scale"].sha256,
            "mean_model": mean, "validation_predictions": predictions,
            "validation_scores": {k: _prediction_scores(v, val, sd, 15) for k, v in predictions.items()},
            "aliases": {"last_bin_persistence": "zero"}, "independent_control_count": 3}
    _emit(ctx, outputs, "direct_controls", body, "reference_direct_controls")
    return _result(outputs, distinct_controls=3, persistence_is_zero_alias=True)


def R03(ctx):
    outputs = {}; fit = _rows(ctx, "fit"); val = _rows(ctx, "validation"); sd = _scale(ctx, ctx.inputs["fit_rows"])
    selection = _read(ctx, "selection"); direct = _read(ctx, "direct_controls"); bank = _read(ctx, "model_bank")
    if selection.get("status") != "selected" or selection.get("validation_rows_sha256") != ctx.inputs["validation_rows"].sha256 or selection.get("fit_scale_sha256") != ctx.inputs["fit_scale"].sha256:
        raise ContractError("complete fixed finite selection required")
    if (direct.get("validation_rows_sha256") != ctx.inputs["validation_rows"].sha256 or direct.get("fit_rows_sha256") != ctx.inputs["fit_rows"].sha256
            or direct.get("fit_scale_sha256") != ctx.inputs["fit_scale"].sha256 or bank.get("fit_rows_sha256") != ctx.inputs["fit_rows"].sha256
            or bank.get("fit_scale_sha256") != ctx.inputs["fit_scale"].sha256):
        raise ContractError("control packet mismatch")
    reconstructed = {}; equivalence = {}
    try:
        for view in ("T", "N"):
            chosen = selection["selected"][view]; key = chosen["model_id"]
            if chosen["model_record"] != bank["models"][key]: raise ContractError("selected model differs from complete bank")
            model = _check_job(ctx, chosen["model_record"], key, "primary")
            fit_view = timing_view(fit) if view == "T" else fit
            val_view = timing_view(val) if view == "T" else val
            independent_id = "independent-" + view
            args = (fit_view, view, chosen["basis"], sd, chosen["lambda"])
            rebuilt, record = _job(ctx, outputs, independent_id, "independent", args, len(fit), model["feature_state"]["layout"]["nonintercept_dimension"])
            reconstructed[view] = record
            if record["status"] != "complete": raise ContractError("independent reconstruction failed")
            a, b = model["feature_state"], rebuilt["feature_state"]
            if any(a[k] != b[k] for k in ("layout_sha256", "fit_ids_sha256", "weights_sha256")):
                raise ContractError("independent feature/category/weight identities differ")
            pairs = {}
            for label, rows in (("fit", fit_view), ("validation", val_view)):
                primary_values = primary.predict(rows, model, normalized=True)
                independent_values = independent.predict(rows, rebuilt, normalized=True)
                compare = _equivalence(primary_values, independent_values)
                _emit(ctx, outputs, view + "_" + label + "_independent_comparison", {"schema": "neural063_independent_comparison_v1", "primary_normalized": primary_values, "independent_normalized": independent_values, "comparison": compare}, "reference_independent_comparison")
                pairs[label] = compare
                if compare["status"] != "equivalent": raise ContractError("independent selected prediction mismatch")
            equivalence[view] = pairs
    except Exception as exc:
        _emit(ctx, outputs, "independent_models", {"schema": "neural063_independent_models_v2", "models": reconstructed, "complete": False}, "reference_independent_models")
        return _fail(ctx, outputs, "selected_independent_reconstruction", exc, independent_jobs_attempted=len(reconstructed))
    diagnostics = {}
    tscore = selection["selected"]["T"]["score"]; nscore = selection["selected"]["N"]["score"]
    t_status = []
    for name in ("zero", "fit_mean"):
        comp = _comparison(tscore, direct["validation_scores"][name]); diagnostics["T_minus_" + name] = comp; t_status.append(_superiority(comp))
    temp = "not_demonstrated_numeric_unavailable" if "not_demonstrated_numeric_unavailable" in t_status else ("met" if all(x == "met" for x in t_status) else "not_met")
    ncomparison = _comparison(nscore, tscore); diagnostics["N_minus_T"] = ncomparison
    point = ncomparison["contrast"]
    nemp = "not_demonstrated_numeric_unavailable" if point["status"] != "finite" else ("met" if point["value"] <= 0.001 else "not_met")
    for name in ("zero", "fit_mean", "trend"):
        comp = _comparison(nscore, direct["validation_scores"][name]); comp["superiority_status"] = _superiority(comp); diagnostics["N_minus_" + name] = comp
    _emit(ctx, outputs, "independent_models", {"schema": "neural063_independent_models_v2", "models": reconstructed, "complete": True,
          "selection_sha256": ctx.inputs["selection"].sha256, "fit_rows_sha256": ctx.inputs["fit_rows"].sha256,
          "fit_scale_sha256": ctx.inputs["fit_scale"].sha256}, "reference_independent_models")
    q = {"schema": "neural063_reference_qualification_v2", "views": {"T": {"empirical_status": temp}, "N": {"empirical_status": nemp}},
         "development_equivalence": equivalence, "validation_diagnostics": diagnostics,
         "selection_sha256": ctx.inputs["selection"].sha256, "model_bank_sha256": ctx.inputs["model_bank"].sha256,
         "complete_primary_jobs": 28, "complete_independent_jobs": 2,
         "query_equivalence": None, "reference_gain": None}
    _emit(ctx, outputs, "qualification", q, "reference_qualification")
    return _result(outputs, independent_jobs=2, empirical_T=temp, empirical_N=nemp)


def C01(ctx):
    outputs = {}; fit = _rows(ctx, "fit"); val = _rows(ctx, "validation"); sd = _scale(ctx, ctx.inputs["fit_rows"]); selection = _read(ctx, "selection")
    if selection.get("status") != "selected" or selection.get("fit_scale_sha256") != ctx.inputs["fit_scale"].sha256:
        raise ContractError("original finite selection and scale required")
    selected = selection["selected"]["N"]; result = {"schema": "neural063_perturbation_bank_v2", "models": {}, "seeds": list(SEEDS),
            "selection_sha256": ctx.inputs["selection"].sha256, "fit_rows_sha256": ctx.inputs["fit_rows"].sha256,
            "validation_rows_sha256": ctx.inputs["validation_rows"].sha256, "fit_scale_sha256": ctx.inputs["fit_scale"].sha256}
    try:
        for seed in SEEDS:
            rows, permutation = controls.permute(fit, seed)
            key = "perturb_" + str(seed)
            permutation_ref = _emit(ctx, outputs, key + "_permutation", permutation, "reference_history_permutation")
            descriptor = features.layout(rows, "N", selected["basis"])
            _allocation(ctx, key, len(rows), descriptor["nonintercept_dimension"])
            state = features.fit_statistics(rows, descriptor)
            model, record = _job(ctx, outputs, key, "primary", (rows, state, sd, selected["lambda"]), len(rows), descriptor["nonintercept_dimension"])
            record["permutation"] = permutation_ref.object(); record["support"] = permutation["support"]
            result["models"][key] = record
            if record["status"] != "complete": raise ContractError("required perturbation fit failed")
            predictions = primary.predict(val, model)
            record["validation_predictions"] = _emit(ctx, outputs, key + "_validation", {"schema": "neural063_perturbation_validation_v1", "predictions": predictions}, "reference_perturbation_validation").object()
            record["validation_score"] = _prediction_scores(predictions, val, sd, 15)
    except Exception as exc:
        result["complete"] = False; _emit(ctx, outputs, "perturbation_bank", result, "reference_perturbation_bank")
        return _fail(ctx, outputs, "all_five_history_perturbations", exc, required_jobs=5, attempted_jobs=len(result["models"]))
    result["complete"] = True; _emit(ctx, outputs, "perturbation_bank", result, "reference_perturbation_bank")
    return _result(outputs, completed_jobs=5, unsupported=sum(x["support"] == "unsupported" for x in result["models"].values()))


def RC00(ctx):
    outputs = {}; bank = _read(ctx, "model_bank"); selected = _read(ctx, "selection"); ind = _read(ctx, "independent_models"); q = _read(ctx, "qualification"); perturb = _read(ctx, "perturbation_bank")
    if (set(bank.get("models", {})) != set(expected_grid_ids()) or not bank.get("complete")
            or selected.get("status") != "selected" or set(ind.get("models", {})) != {"T", "N"} or not ind.get("complete")
            or set(perturb.get("models", {})) != {"perturb_" + str(s) for s in SEEDS} or not perturb.get("complete")):
        raise ContractError("all 28+2+5 concrete development jobs required")
    if q.get("selection_sha256") != ctx.inputs["selection"].sha256 or q.get("model_bank_sha256") != ctx.inputs["model_bank"].sha256 or ind.get("selection_sha256") != ctx.inputs["selection"].sha256 or perturb.get("selection_sha256") != ctx.inputs["selection"].sha256:
        raise ContractError("qualification/development source selection mismatch")
    for key in expected_grid_ids(): _check_job(ctx, bank["models"][key], key, "primary")
    for view in ("T", "N"): _check_job(ctx, ind["models"][view], "independent-" + view, "independent")
    for seed in SEEDS: _check_job(ctx, perturb["models"]["perturb_" + str(seed)], "perturb_" + str(seed), "primary")
    diagnostics = q["validation_diagnostics"]
    t_checks = [_superiority(diagnostics["T_minus_" + name]) for name in ("zero", "fit_mean")]
    t_status = "not_demonstrated_numeric_unavailable" if "not_demonstrated_numeric_unavailable" in t_checks else ("met" if all(x == "met" for x in t_checks) else "not_met")
    n_point = diagnostics["N_minus_T"]["contrast"]
    n_status = "not_demonstrated_numeric_unavailable" if n_point["status"] != "finite" else ("met" if n_point["value"] <= 0.001 else "not_met")
    statuses = {"T": t_status, "N": n_status}
    if statuses != {v: q["views"][v]["empirical_status"] for v in ("T", "N")}:
        raise ContractError("declared empirical status differs from retained numerical evidence")
    eligible = all(x == "met" for x in statuses.values())
    outcome = "eligible_for_full_programme" if eligible else "terminated_before_query_reference_unqualified"
    _emit(ctx, outputs, "reference_decision", {"schema": "neural063_reference_decision_v2", "outcome": outcome,
          "qualification_sha256": ctx.inputs["qualification"].sha256, "empirical_statuses": statuses,
          "technical_fit_jobs": 35, "query_model_work_permitted": eligible,
          "unsupported_perturbations": [k for k, r in perturb["models"].items() if r["support"] == "unsupported"],
          "reference_gain": None}, "reference_decision")
    return _result(outputs, outcome, primary_jobs=28, independent_jobs=2, perturbation_jobs=5)


def R04(ctx):
    outputs = {}; rows, index_hash = _query(ctx); selection = _read(ctx, "selection")
    if selection.get("status") != "selected": raise ContractError("complete reference selection required")
    views = {}; identities = {}
    for view in ("T", "N"):
        chosen = selection["selected"][view]
        model = _check_job(ctx, chosen["model_record"], chosen["model_id"], "primary")
        if model["view"] != view: raise ContractError("reference tool information view mismatch")
        views[view] = primary.predict(rows[view], model); identities[view] = chosen["model_record"]["model"]
    _emit(ctx, outputs, "reference_predictions", {"schema": "neural063_reference_predictions_v2", "query_index_sha256": index_hash,
          "fit_scale_sha256": selection["fit_scale_sha256"], "views": views, "models": identities}, "reference_predictions")
    return _result(outputs, complete_views=2, query_mice=19)


def R05(ctx):
    outputs = {}; rows, index_hash = _query(ctx); bank = _read(ctx, "independent_models")
    if not bank.get("complete") or set(bank.get("models", {})) != {"T", "N"}: raise ContractError("both independent models required")
    views = {}; identities = {}
    for view in ("T", "N"):
        model = _check_job(ctx, bank["models"][view], "independent-" + view, "independent")
        if model["view"] != view: raise ContractError("independent information view mismatch")
        views[view] = independent.predict(rows[view], model); identities[view] = bank["models"][view]["model"]
    _emit(ctx, outputs, "independent_predictions", {"schema": "neural063_independent_predictions_v2", "query_index_sha256": index_hash,
          "fit_scale_sha256": bank["fit_scale_sha256"], "views": views, "models": identities}, "reference_independent_predictions")
    return _result(outputs, complete_views=2, query_mice=19)


def R06(ctx):
    outputs = {}; a = _read(ctx, "reference_predictions"); b = _read(ctx, "independent_predictions"); index = _read(ctx, "query_index"); sd = _scale(ctx)
    qhash = ctx.inputs["query_index"].sha256
    if (index.get("schema") != "neural063_query_index_v2" or index.get("target_shape") != [3] or index.get("heldout_mouse_count") != 19
            or a.get("schema") != "neural063_reference_predictions_v2" or b.get("schema") != "neural063_independent_predictions_v2"
            or a.get("fit_scale_sha256") != ctx.inputs["fit_scale"].sha256 or b.get("fit_scale_sha256") != ctx.inputs["fit_scale"].sha256
            or a.get("query_index_sha256") != qhash or b.get("query_index_sha256") != qhash or set(a.get("views", {})) != {"T", "N"} or set(b.get("views", {})) != {"T", "N"}):
        raise ContractError("query equivalence source/index binding mismatch")
    measurements = {}
    for view in ("T", "N"):
        scoring.admit_predictions(a["views"][view], index["ids"]); scoring.admit_predictions(b["views"][view], index["ids"])
        aa = [{"id": r["id"], "values": [v / sd for v in r["values"]]} for r in a["views"][view]]
        bb = [{"id": r["id"], "values": [v / sd for v in r["values"]]} for r in b["views"][view]]
        measurements[view] = _equivalence(aa, bb)
    passed = all(v["status"] == "equivalent" for v in measurements.values())
    _emit(ctx, outputs, "query_equivalence", {"schema": "neural063_query_equivalence_v2", "status": "equivalent" if passed else "not_equivalent",
          "primary_prediction_sha256": ctx.inputs["reference_predictions"].sha256,
          "independent_prediction_sha256": ctx.inputs["independent_predictions"].sha256,
          "query_index_sha256": qhash, "fit_scale_sha256": ctx.inputs["fit_scale"].sha256,
          "measurements": measurements, "query_targets_accessed": False}, "reference_query_equivalence")
    return _result(outputs, "complete" if passed else "failed", complete_views=2)


def C02(ctx):
    outputs = {}; rows, index_hash = _query(ctx); direct = _read(ctx, "direct_controls"); perturb = _read(ctx, "perturbation_bank")
    if not perturb.get("complete") or set(perturb.get("models", {})) != {"perturb_" + str(s) for s in SEEDS}:
        raise ContractError("all five original perturbations required")
    if direct.get("fit_scale_sha256") != perturb.get("fit_scale_sha256"):
        raise ContractError("direct and perturbed controls use different FIT normalization")
    predictions = controls.direct(rows["N"], direct["mean_model"])
    support = {}
    for seed in SEEDS:
        key = "perturb_" + str(seed); rec = perturb["models"][key]
        model = _check_job(ctx, rec, key, "primary")
        predictions[key] = primary.predict(rows["N"], model); support[key] = rec["support"]
    _emit(ctx, outputs, "control_predictions", {"schema": "neural063_control_predictions_v2", "query_index_sha256": index_hash,
          "fit_scale_sha256": direct["fit_scale_sha256"], "controls": predictions, "support": support, "aliases": {"last_bin_persistence": "zero"}, "distinct_controls": 8}, "control_predictions")
    return _result(outputs, complete_control_tables=8)


HANDLERS = {name: globals()[name] for name in REQUIRED}


def run(stage, ctx):
    ctx.require_scientific()
    if stage not in HANDLERS or ctx.stage != stage or set(ctx.inputs) != REQUIRED[stage]:
        raise ContractError("exact reference stage/input roster required")
    expected_parameters = {"fit_allocations"} if stage in ("R00", "R01", "R03", "C01") else set()
    if set(ctx.parameters) != expected_parameters:
        raise ContractError("unexpected reference stage parameters")
    return HANDLERS[stage](ctx)
