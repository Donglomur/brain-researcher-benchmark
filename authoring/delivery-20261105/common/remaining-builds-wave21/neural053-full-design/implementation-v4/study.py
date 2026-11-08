"""Complete training-only reference and agent programme; all-query admission gate.

Trusted operator ports supply independently qualified context isolation, provider
execution, custody and process observation. No such live ports or approvals ship
with this source. Invented controls never authorize the production entry points.
"""
import hashlib
from dataclasses import dataclass, field
from cohort import (CANONICAL, ARMS, MODES, require, canonical_profile,
                    validate_training_metadata, inner_splits, study_plan)
from io_support import admit_full_run, object_digest, canonical_bytes
from grading import required_case_keys, array_digest

FAMILY_PUBLIC = {"ridge": "ridge", "shrinkage_lda": "lda", "fourier_ridge": "fourier_ridge",
                 "historical_centroid": "centroid"}


def state_digest(value):
    """Streaming typed state identity, not a claim of source/fit-support correctness."""
    import numpy as np
    digest = hashlib.sha256()

    def visit(x):
        if isinstance(x, np.ndarray):
            require(not x.dtype.hasobject, "No object array model state")
            digest.update(canonical_bytes({"array_shape": list(x.shape), "dtype": x.dtype.str}))
            flat = np.ascontiguousarray(x).reshape(-1)
            for start in range(0, len(flat), 65536):
                digest.update(flat[start:start + 65536].tobytes())
        elif isinstance(x, dict):
            digest.update(b"dict")
            for key in sorted(x):
                digest.update(canonical_bytes(key))
                visit(x[key])
        elif isinstance(x, (list, tuple)):
            digest.update(canonical_bytes({"sequence_length": len(x)}))
            for item in x:
                visit(item)
        elif isinstance(x, np.generic):
            visit(x.item())
        else:
            digest.update(canonical_bytes(x))
    visit(value)
    return digest.hexdigest()


def training_support_digest(packet, indices):
    return object_digest([{ "training_id": packet["training_ids"][i],
                           "label": packet["training_labels"][i],
                           "group": packet["groups"][i] } for i in indices])


def fit_reference_case(X, packet, fold_ordinal, arm, budget, profile=CANONICAL, engineering_engine=None):
    """All240 inner fits, three final family fits and centroid; no query input."""
    import numpy as np
    from reference import models
    require(engineering_engine is None or profile.engineering, "No substituted production reference engine")
    engine = models if engineering_engine is None else engineering_engine
    validate_training_metadata(packet, profile)
    X = np.asarray(X)
    require(X.ndim == 2 and len(X) == profile.train_rows and np.isfinite(X).all(), "Complete finite training matrix")
    require(arm in ARMS and 0 <= fold_ordinal < 4, "Canonical reference case")
    if not profile.engineering:
        require(X.shape[1] == ARMS[arm], "Canonical arm feature width")
    labels = np.asarray(packet["training_labels"], dtype=np.int64)
    prior_counts = np.bincount(labels, minlength=profile.classes + 1)[1:]
    uniform_prior = np.full(profile.classes, 1 / profile.classes, dtype=np.float32)
    frequency_prior = (prior_counts / len(labels)).astype(np.float32)
    require(np.array_equal(uniform_prior, frequency_prior), "Balanced training-frequency and uniform priors coincide")
    support = [(tid, group["person_group"], label) for tid, group, label in
               zip(packet["training_ids"], packet["groups"], packet["training_labels"])]
    splits, records, fits = inner_splits(packet, profile), [], []
    grid = engine.setting_grid()
    require([s["rank"] for s in grid] == list(range(16)), "Exact ordered16 reference settings")
    for setting in grid:
        accumulators = [engine.TrainingMetricAccumulator(support, profile.classes, t) for t in (0.1, 1, 10)]
        for split_no, split in enumerate(splits):
            fit_idx, valid_idx = list(split["fit_indices"]), list(split["validation_indices"])
            budget.charge("reference_fits")
            fitted = engine.fit_reference(setting["family"], setting["parameters"], X[fit_idx], labels[fit_idx],
                                          profile.classes, fold_ordinal, arm)
            fit_identity = state_digest(fitted)
            for start in range(0, len(valid_idx), 128):
                budget.check_clock()
                indices = valid_idx[start:start + 128]
                scores = engine.score_reference(fitted, X[indices])
                ids = [packet["training_ids"][i] for i in indices]
                for accumulator in accumulators:
                    accumulator.update(scores, ids)
            require(state_digest(fitted) == fit_identity, "No state mutation during validation")
            fits.append({"phase": "inner", "rank": setting["rank"], "split": split_no,
                         "state_digest": fit_identity, "fit_support": training_support_digest(packet, fit_idx),
                         "validation_support": training_support_digest(packet, valid_idx),
                         "transient_state_retired": True, "validation_predictions_retired": True})
            del fitted
        for accumulator in accumulators:
            records.append({"rank": setting["rank"], **accumulator.finalize()})
    selected = {family: engine.select_setting([r for r in records if grid[r["rank"]]["family"] == family], family)
                for family in ("ridge", "shrinkage_lda", "fourier_ridge")}
    primary = engine.select_setting(records)
    plans = {}
    for family, choice in selected.items():
        setting = grid[choice["rank"]]
        budget.charge("reference_fits")
        fitted = engine.fit_reference(family, setting["parameters"], X, labels,
                                      profile.classes, fold_ordinal, arm)
        plans[FAMILY_PUBLIC[family]] = engine.export_plan(fitted, choice["temperature"])
        fits.append({"phase": "final", "family": FAMILY_PUBLIC[family], "rank": choice["rank"],
                     "temperature": choice["temperature"], "state_digest": state_digest(fitted),
                     "fit_support": training_support_digest(packet, range(len(X)))})
    budget.charge("reference_fits")
    centroid = engine.fit_reference("historical_centroid", {}, X, labels, profile.classes, fold_ordinal, arm)
    plans["centroid"] = engine.export_plan(centroid, 1)
    fits.append({"phase": "final", "family": "centroid", "temperature": 1,
                 "state_digest": state_digest(centroid), "fit_support": training_support_digest(packet, range(len(X)))})
    require(len(fits) == 244 and len(records) == 48 and set(plans) == {"ridge", "lda", "fourier_ridge", "centroid"},
            "Complete reference operation/panel scope")
    return {"schema": "neural053_reference_case_v1", "fold_ordinal": fold_ordinal, "arm": arm,
            "plans": plans, "selection_records": records, "selected": selected,
            "primary_family": FAMILY_PUBLIC[grid[primary["rank"]]["family"]],
            "unfitted_prior_controls": {"training_counts": prior_counts.tolist(),
                "uniform_float32": uniform_prior.tolist(), "training_frequency_float32": frequency_prior.tolist(),
                "coincide": True, "additional_fits": 0},
            "fit_records": fits, "fits": 244, "empirical_competence_established": False,
            "engineering_profile": profile.engineering}


def fit_full_references(training_loader, reference_sink, permit, bindings, approved_receipts, budget):
    admit_full_run(permit, bindings, approved_receipts, "train_references")
    manifests = []
    for case in study_plan()["reference_cases"]:
        budget.check_clock()
        X, packet = training_loader(case["fold_ordinal"], case["arm"])
        output = fit_reference_case(X, packet, case["fold_ordinal"], case["arm"], budget)
        # Sink is operator-owned source-bound storage, never an author tool.
        stored = reference_sink(case, output)
        require(isinstance(stored, dict) and stored.get("case") == case and
                stored.get("fits") == 244 and isinstance(stored.get("artifact_manifest_sha256"), str),
                "Exact stored reference case lineage")
        manifests.append(stored)
        del output, X, packet
    require(len(manifests) == 16, "Every reference fold/arm retained")
    return {"schema": "neural053_full_reference_program_v1", "cases": manifests,
            "completed_fits": 3904, "scientific_qualification_conferred": False}


@dataclass
class CasePhases:
    mode: str
    context_key: tuple
    phase: str = "new"
    events: list = field(default_factory=list)

    def transition(self, phase, digest):
        require(self.mode in MODES, "Named author mode")
        allowed = {"new": "program_sealed" if self.mode == "fixed_program" else "training_admitted",
                   "program_sealed": "training_admitted", "training_admitted": "model_sealed",
                   "model_sealed": "method_admitted", "method_admitted": "query_completed"}
        require(allowed.get(self.phase) == phase, "No query adaptation or out-of-order source exposure")
        require(isinstance(digest, str) and len(digest) == 64, "Exact phase artifact identity")
        self.phase = phase
        self.events.append({"phase": phase, "artifact_sha256": digest})


def author_all_candidates(context_factory, training_loader, sealed_sink, static_task_spec,
                          permit, bindings, approved_receipts, budget):
    """96 fresh contexts; fixed seal precedes even calling its training loader.

    The qualified context port implements seal_program(spec), train_fixed(seal,
    packet,X), or investigate(spec,packet,X), and close(). It may not access query
    files, other contexts/folds, arbitrary external models or a shared namespace.
    These isolation facts require external qualification; a Python port is not
    itself a sandbox. Neither this function nor a port receives query data.
    """
    from method.plan import load_plan
    admit_full_run(permit, bindings, approved_receipts, "author_candidates")
    sealed, namespace_ids = [], set()
    for case in study_plan()["contexts"]:
        budget.charge("author_contexts")
        key = (case["mode"], case["replication"], case["fold_ordinal"], case["arm"])
        phase = CasePhases(case["mode"], key)
        port = context_factory(case)
        require(port.namespace_id not in namespace_ids and port.namespace_id,
                "Every author has a fresh independently qualified namespace")
        namespace_ids.add(port.namespace_id)
        try:
            program = None
            if case["mode"] == "fixed_program":
                program = port.seal_program(static_task_spec)
                phase.transition("program_sealed", object_digest(program))
            X, packet = training_loader(case)
            validate_training_metadata(packet)
            require(X.shape == (55620, ARMS[case["arm"]]), "Exact candidate training support")
            phase.transition("training_admitted", training_support_digest(packet, range(55620)))
            if case["mode"] == "fixed_program":
                authored = port.train_fixed(program, packet, X)
            else:
                authored = port.investigate(static_task_spec, packet, X)
            require(set(authored) == {"plan", "training_lineage", "final_source_seal", "resource_receipt"},
                    "Complete sealed program/fit provenance and resource receipt")
            plan = load_plan(authored["plan"])
            require(plan.input_dim == ARMS[case["arm"]] and plan.class_count == 1854,
                    "Actual sealed plan input/output scope")
            phase.transition("model_sealed", plan.digest)
            stored = sealed_sink(case, authored, tuple(phase.events))
            require(stored.get("context_key") == list(key) and stored.get("plan_sha256") == plan.digest,
                    "Exact sealed candidate storage binding")
            sealed.append(stored)
        finally:
            # The external observer must still qualify natural completion/cleanup;
            # this call is not a universal process-retirement guarantee.
            port.close()
        budget.check_clock()
    require(len(sealed) == len(namespace_ids) == 96, "All independent author contexts")
    return sealed


def predict_all_admitted(cases, current_binding_loader, plan_loader, registry, reference_selection,
                          qualified_worker_launcher, permit,
                          bindings, approved_receipts, budget):
    """All160 method gates pass before the first query loader invocation.

    Each case contains a reviewed receipt; current bindings and plans come from
    trusted independently authenticated operator custody. The observer must
    independently admit natural process completion and exact source/state/output.
    No method review, approval or process observation is self-minted here.
    """
    from method.admission import validate_admission
    from selection import ReferenceSelection
    admit_full_run(permit, bindings, approved_receipts, "predict_all")
    require(set(cases) == set(required_case_keys()), "Complete96+64 prediction methods")
    require(type(reference_selection) is ReferenceSelection and
            bindings.get("reference_selection_sha256") == reference_selection.digest,
            "Independently approved pre-query training-selected comparator")
    case_manifest = [{"context_key": list(key), "expected_context": cases[key]["expected_context"],
                      "request": cases[key]["worker_request"],
                      "receipt_digest": object_digest(cases[key]["receipt"])} for key in required_case_keys()]
    require(bindings.get("prediction_case_manifest") == object_digest(case_manifest),
            "Operator-bound full160-case context/request manifest")
    admitted = {}
    for key in required_case_keys():
        current = current_binding_loader(key)
        plan = plan_loader(key)
        require(current["context"] == cases[key]["expected_context"], "Exact case-to-method mapping")
        gate = validate_admission(cases[key]["receipt"], current, registry, plan)
        request = cases[key]["worker_request"]
        require(request["profile"] == "canonical" and request["context_key"] == list(key),
                "No engineering worker or cross-context production substitution")
        admitted[key] = {"bindings_digest": object_digest(current), "plan_digest": plan.digest, "gate": gate}
        del plan
    whole_gate = {"schema": "neural053_whole_method_gate_v1",
                  "reference_selection_sha256": reference_selection.digest, "methods": [
        {"context_key": list(key), "receipt_sha256": admitted[key]["gate"]["receipt_sha256"],
         "bindings_sha256": admitted[key]["gate"]["bindings_sha256"],
         "plan_sha256": admitted[key]["plan_digest"]} for key in required_case_keys()]}
    require(object_digest(whole_gate) in registry.document()["approved_qualifications"],
            "Complete160-method seal independently approved by protected operator registry")
    for key in required_case_keys():
        request = cases[key]["worker_request"]
        require(request["whole_method_gate"]["sha256"] == object_digest(whole_gate) and
                request["whole_method_gate"]["bytes"] == len(canonical_bytes(whole_gate)),
                "Every worker binds the exact complete pre-query gate")
        require(request["reference_selection"]["sha256"] == reference_selection.digest,
                "Every worker binds independently derived reference-selection artifact")
    outputs = {}
    for key in required_case_keys():
        budget.charge("prediction_cases")
        saved = admitted[key]
        current, plan = current_binding_loader(key), plan_loader(key)
        require(object_digest(current) == saved["bindings_digest"] and plan.digest == saved["plan_digest"],
                "No method/support change after whole-study gate")
        validate_admission(cases[key]["receipt"], current, registry, plan)
        del plan
        # The qualified launcher invokes prediction_worker.py in the exact
        # admitted fresh namespace, waits for natural process exit, authenticates
        # its output and returns an independently observed completion receipt.
        # A current in-process function cannot certify its own future process exit.
        observed = qualified_worker_launcher(key, cases[key]["worker_request"], saved["gate"])
        execution, worker = observed["execution_receipt"], observed["worker_manifest"]
        require(type(execution.get("natural_exit_code")) is int and execution["natural_exit_code"] == 0 and
                execution.get("source_state_unchanged") is True and
                execution.get("context_key") == list(key) and worker.get("context_key") == list(key) and
                worker.get("profile") == "canonical" and worker.get("bindings_digest") == saved["bindings_digest"] and
                worker.get("reference_selection_digest") == reference_selection.digest and
                execution.get("reference_selection_digest") == reference_selection.digest and
                execution.get("probabilities_digest") == worker.get("probabilities_digest"),
                "Independent actual prediction completion required")
        outputs[key] = {"probability_artifact": worker["probability_artifact"],
                        "method_gate": saved["gate"], "execution_receipt": execution}
    return outputs
