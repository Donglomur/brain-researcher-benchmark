"""Concrete manifest-only six-phase production composition; never self-authorized."""
from pathlib import Path
from cohort import ARMS, MODES, require, study_plan
from io_support import object_digest
from storage import write_json_fresh, write_array_fresh, read_array_exact
from phase_manifest import PHASES, admit_invocation, metadata, source_closure, budget_snapshot


def _table(document, schema, keys):
    require(document.get("schema") == schema and type(document.get("cases")) is list, "Exact persisted case table")
    rows = document["cases"]
    require(len(rows) == len(keys) and [tuple(x["key"]) for x in rows] == list(keys), "Complete deterministic case order")
    return {tuple(x["key"]): x["value"] for x in rows}


def _table_document(schema, table):
    return {"schema": schema, "cases": [{"key": list(k), "value": v} for k, v in table.items()]}


def case_store(pin, budget):
    keys = [(r, f, a) for r in ("reference", "rep0", "rep1", "rep2") for f in range(4) for a in ARMS]
    return _table(metadata(pin, budget, 64 * 1024 * 1024), "neural053_case_store_v2", keys)


def _adapter_config(pin, permit, budget, invocation):
    from adapters.common import current_source_manifest
    config = metadata(pin, budget)
    require(config["source"]["root"] == invocation["source_root"] and
            config["source"]["files"] == invocation["runtime_sources"],
            "Concrete sandbox captures the same complete approved runtime source")
    require(object_digest(config) == permit["bindings"].get("adapter_config_sha256") and
            object_digest(current_source_manifest(config, budget)) == permit["bindings"].get("adapter_source_manifest_sha256"),
            "Actual concrete adapter config/source equals independently approved port")
    return config


def _fresh_aliaser():
    """Fresh operator secret generated only during an authorized view phase.

    It is never read from disk, hashed as an artifact or disclosed to authors.
    One key across all64 stores preserves paired aliases; persisted exact case
    stores, rather than re-creation of a secret, govern subsequent reproduction.
    """
    import secrets
    from cohort import make_aliaser
    return make_aliaser(secrets.token_bytes(32))


def _prediction_inputs(pin, store, candidate_pin, selection, registry, budget):
    from grading import required_case_keys
    from packets import prediction_case_files
    from method.plan import load_plan
    rows = _table(metadata(pin, budget, 64 * 1024 * 1024), "neural053_prediction_cases_v2", required_case_keys())
    candidate = metadata(candidate_pin, budget, 64 * 1024 * 1024)
    require(candidate.get("schema") == "neural053_candidate_program_v2" and len(candidate.get("cases", [])) == 96,
            "Actual complete upstream candidate programme")
    candidate_plans = {}
    for entry in candidate["cases"]:
        manifest = metadata(entry["manifest"], budget)
        require({k:v for k,v in entry.items() if k != "manifest"} == manifest, "Candidate output joins actual sealed manifest")
        key = tuple(entry["context_key"])
        require(key not in candidate_plans, "No duplicate candidate context")
        candidate_plans[key] = entry["plan"]
    refs = {(x["fold_ordinal"], x["arm"]): x["final_plans"] for x in selection.document["cases"]}
    cases, workers, loaded_bindings, loaded_plans = {}, {}, {}, {}
    for key in required_case_keys():
        value = rows[key]
        require(set(value) == {"worker"}, "Exact operator worker mapping")
        worker = value["worker"]
        request = metadata(worker["request"], budget)
        actual = worker["inputs"]
        expected_plan = refs[key[2], key[3]][key[1]] if key[0] == "independent_reference" else candidate_plans[key]
        require(actual["plan"] == expected_plan, "Prediction plan is actual sealed upstream family/context output")
        files = prediction_case_files(store, key)
        require(actual["query"] == files["query"] and actual["query_descriptor"] == files["query_descriptor"],
                "Actual worker query operands match prepared held-person case")
        bindings = metadata(actual["bindings"], budget)
        receipt = metadata(actual["receipt"], budget)
        for name, role in (("training_features", "training"), ("query_artifact", "query"), ("query_descriptor", "query_descriptor")):
            require(all(bindings["artifacts"][name][k] == files[role][k] for k in ("bytes", "sha256")),
                    "Method operand joins actual prepared support: " + name)
        require(all(actual["registry"][k] == registry[k] for k in ("bytes", "sha256")), "Exact protected worker registry")
        cases[key] = {"expected_context": bindings["context"], "receipt": receipt, "worker_request": request}
        workers[key] = worker
        loaded_bindings[key] = (actual["bindings"], bindings)
        loaded_plans[key] = actual["plan"]
    require(set(candidate_plans) == {k for k in required_case_keys() if k[0] != "independent_reference"}, "All96 actual candidate outputs")
    def binding_loader(key):
        pin, original = loaded_bindings[key]
        value = metadata(pin, budget)
        require(value == original, "Method binding unchanged")
        return value
    def plan_loader(key):
        return load_plan(metadata(loaded_plans[key], budget, 1024 * 1024 * 1024))
    return cases, workers, binding_loader, plan_loader


def execute_stage(phase, invocation_pin, permit, expected_bindings, approved_receipts, budget):
    """No callable ports, mutable arrays, private keys or caller family choices."""
    invocation = admit_invocation(phase, invocation_pin, permit, expected_bindings, approved_receipts, budget)
    artifacts, parameters = invocation["artifacts"], invocation["parameters"]
    expected_parameters = {"output_root"} | ({"source_root"} if phase == "prepare_original" else set()) | (
        {"study_nonce", "alias_policy"} if phase == "prepare_views" else set())
    require(set(parameters) == expected_parameters, "Closed phase-specific parameter vocabulary")
    root = Path(parameters["output_root"])
    require(root.is_absolute() and root.parent.is_dir() and not root.parent.is_symlink() and not root.exists(), "Fresh exact phase output root")
    root.mkdir()
    outputs = {}
    if phase == "prepare_original":
        from preparation import prepare_full_original
        rows, features, evidence = prepare_full_original(parameters["source_root"], metadata(artifacts["source_spec"], budget),
            metadata(artifacts["metadata_manifest"], budget), metadata(artifacts["sensors"], budget),
            permit, expected_bindings, approved_receipts, budget)
        prepared = {"schema": "neural053_prepared_original_v2", "rows": write_json_fresh(root / "rows.json", rows, budget),
                    "features": {arm: write_array_fresh(root / (arm + ".npy"), array, budget) for arm, array in features.items()},
                    "evidence": write_json_fresh(root / "evidence.json", evidence, budget)}
        outputs["prepared"] = write_json_fresh(root / "prepared.json", prepared, budget)
    elif phase == "prepare_views":
        from packets import prepare_case_store
        require(parameters["alias_policy"] == "fresh_operator_hmac_sha256_256bit_v2", "Reviewed concrete alias authority policy")
        prepared = metadata(artifacts["prepared"], budget)
        require(prepared.get("schema") == "neural053_prepared_original_v2" and set(prepared["features"]) == {"neural", "ocular"}, "Actual original preparation")
        require(expected_bindings.get("original_preparation") == artifacts["prepared"]["sha256"], "Accepted preparation identity")
        rows = metadata(prepared["rows"], budget, 128 * 1024 * 1024)
        features = {a: read_array_exact(p["path"], p, (88992, ARMS[a]), budget) for a,p in prepared["features"].items()}
        store = prepare_case_store(rows, features, _fresh_aliaser(), parameters["study_nonce"], root / "cases", permit,
                                   expected_bindings, approved_receipts, budget)
        outputs["case_store"] = write_json_fresh(root / "case_store.json", _table_document("neural053_case_store_v2", store), budget)
    elif phase == "train_references":
        from study import fit_full_references
        from packets import reference_training_loader
        from outputs import reference_sink
        from selection import store_reference_selection
        store = case_store(artifacts["case_store"], budget)
        program = fit_full_references(reference_training_loader(store, budget), reference_sink(root, budget), permit,
                                      expected_bindings, approved_receipts, budget)
        outputs["reference_program"] = write_json_fresh(root / "reference_program.json", program, budget)
        outputs["reference_selection"], _ = store_reference_selection(root / "reference_selection.json", outputs["reference_program"], budget)
    elif phase == "author_candidates":
        from study import author_all_candidates
        from packets import candidate_training_loader
        from outputs import candidate_sink
        from adapters import ProviderContextFactory
        store = case_store(artifacts["case_store"], budget)
        config = _adapter_config(artifacts["adapter_config"], permit, budget, invocation)
        # The adapter receives only training pins, never the private case map.
        training = {(m,r,f,a): {"case_id": store[f"rep{r}",f,a]["case_id"], "arm": a,
                    **{n:store[f"rep{r}",f,a][n] for n in ("training", "training_metadata")}}
                    for m in MODES for r in range(3) for f in range(4) for a in ARMS}
        factory = ProviderContextFactory(config, budget, {"receipt": permit, "approved": approved_receipts}, case_files=training)
        sealed = author_all_candidates(factory, candidate_training_loader(store, budget), candidate_sink(root, budget),
            metadata(artifacts["static_task_spec"], budget), permit, expected_bindings, approved_receipts, budget)
        outputs["candidate_program"] = write_json_fresh(root / "candidate_program.json", {"schema": "neural053_candidate_program_v2", "cases": sealed}, budget)
    elif phase == "predict_all":
        from study import predict_all_admitted
        from adapters import DockerWorkerLauncher
        from method.admission import TrustedRegistry
        from selection import admit_reference_selection
        store = case_store(artifacts["case_store"], budget)
        require(expected_bindings.get("reference_program_output_sha256") == artifacts["reference_program"]["sha256"], "Approved actual training programme")
        selection = admit_reference_selection(artifacts["reference_selection"], artifacts["reference_program"], expected_bindings["reference_selection_sha256"], budget)
        pin = artifacts["method_registry"]; budget.charge("source_read", pin["bytes"])
        registry = TrustedRegistry.from_file(pin["path"], expected_bytes=pin["bytes"], expected_sha256=pin["sha256"])
        cases, workers, bindings_loader, plans_loader = _prediction_inputs(artifacts["prediction_cases"], store, artifacts["candidate_program"], selection, pin, budget)
        launcher = DockerWorkerLauncher(_adapter_config(artifacts["adapter_config"], permit, budget, invocation), budget,
                                        {"receipt": permit, "approved": approved_receipts}, case_files=workers)
        completed = predict_all_admitted(cases, bindings_loader, plans_loader, registry, selection, launcher, permit,
                                          expected_bindings, approved_receipts, budget)
        outputs["completed_predictions"] = write_json_fresh(root / "completed_predictions.json", _table_document("neural053_completed_predictions_v2", completed), budget)
    else:
        from grading import grade_full_run, required_case_keys
        from packets import protected_target_loader
        from outputs import prediction_record_loader, query_descriptors
        from selection import admit_reference_selection
        from method.admission import TrustedRegistry
        store = case_store(artifacts["case_store"], budget)
        selection = admit_reference_selection(artifacts["reference_selection"], artifacts["reference_program"], expected_bindings["reference_selection_sha256"], budget)
        descriptors = query_descriptors(store, budget)
        completed = _table(metadata(artifacts["completed_predictions"], budget, 64 * 1024 * 1024), "neural053_completed_predictions_v2", required_case_keys())
        registry_pin = artifacts["method_registry"]; budget.charge("source_read", registry_pin["bytes"])
        registry = TrustedRegistry.from_file(registry_pin["path"], expected_bytes=registry_pin["bytes"], expected_sha256=registry_pin["sha256"])
        executions = metadata(artifacts["execution_registry"], budget)
        require(executions.get("schema") == "neural053_execution_registry_v2" and type(executions.get("approved_receipts")) is list,
                "Independently admitted observer registry; completed outputs do not approve themselves")
        metrics = grade_full_run(prediction_record_loader(completed, descriptors, selection, budget), descriptors,
            frozenset(registry.document()["approved_receipts"]), artifacts["reference_selection"], artifacts["reference_program"],
            frozenset(executions["approved_receipts"]), protected_target_loader(store, budget), permit,
            expected_bindings, approved_receipts, budget)
        outputs["metrics"] = write_json_fresh(root / "metrics.json", metrics, budget)
    source_closure(invocation["source_root"], invocation["runtime_sources"], budget)
    result = {"schema": "neural053_phase_outputs_v2", "phase": phase, "invocation_sha256": invocation_pin["sha256"],
              "runtime_source_sha256": object_digest(invocation["runtime_sources"]), "artifacts": outputs,
              "natural_process_completion": "external_observer_required", "scientific_qualification_conferred": False}
    output_pin = write_json_fresh(root / "phase_outputs.json", result, budget)
    budget.check_clock()
    return output_pin


if __name__ == "__main__":
    import json
    plan = study_plan()
    print(json.dumps({k: plan[k] for k in ("schema", "author_contexts", "prospective_reference_fits", "candidate_matrices", "reference_matrices", "canonical_task_count", "scientific_execution")}))
