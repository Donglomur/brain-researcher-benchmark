"""Full Morse preparation -> paired controller -> five references -> private report.

Future explicitly authorized use only. Importing this module does not open data,
construct models, execute workers, or create authority. All numerical reductions
come from the captured incumbent modules. No score is returned to a worker.
"""
import hashlib
import math
import os
from pathlib import Path

from contract import PEOPLE, TASKS, CELLS, SOURCE_COMMIT, require
from morse_selection import (MODES, REFERENCE_NAMES, HOLDS, REPRESENTATION,
    CANONICAL_SHA256, canonical_bytes, digest, compile_paired_plan, freeze_capsule,
    write_new, file_pin)
from production_policy import (exact, captured, document, ordinary_directory,
                               separated, SelectedEvidence, SelectedNativeAdmission)
from storage_policy import PreprovisionedStorage


class ProductionFailure(RuntimeError):
    def __init__(self, first, secondary, stage):
        super().__init__("Morse production failed; no complete scientific claim")
        self.first, self.secondary, self.stage = first, tuple(secondary), stage


def _positive(value, name):
    require(type(value) is int and value > 0, "positive explicit " + name)


def _save(root, name, value, maximum, budget):
    _positive(maximum, "output member bound")
    # Reserve before serialization/publication. This conservative reservation
    # is never refunded, and is not a measurement of Python/native memory I/O.
    budget.write(maximum)
    body = canonical_bytes(value)
    require(len(body) <= maximum, "private metadata member exceeds selection")
    write_new(Path(root) / name, body)
    budget.check()
    return {"path": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def _load_artifact(root, pin, binding, maximum, budget):
    from morse_reports import read_artifact
    require(type(pin["bytes"]) is int and 0 < pin["bytes"] <= maximum, "artifact extent")
    budget.read(pin["bytes"] + 1)
    result = read_artifact(root, pin, binding, max_bytes=pin["bytes"])
    budget.check()
    return result


def _intake(intent, evidence_root, maximum, nonce, allocation, budget, window_bytes):
    """Actual unchanged provider, cohort and primary/premarker preparation."""
    from provider import Recording
    from packets import prepare
    value = document(evidence_root, intent["intake_manifest"], maximum, budget)
    exact(value, ("schema", "source_commit", "recordings"), "complete intake")
    require(value["schema"] == "morse-pinned-cohort-v1"
            and value["source_commit"] == SOURCE_COMMIT
            and type(value["recordings"]) is list and len(value["recordings"]) == 64,
            "complete source-version/64-recording intake")
    rows = value["recordings"]
    keys = [(r["participant"], r["task"]) for r in rows]
    require(keys == [(p, t) for p in PEOPLE for t in TASKS], "fixed complete intake order/identity")
    successful_prefix = failure_maximum = 0
    for row in rows:
        exact(row, ("source_commit", "participant", "task", "files"), "recording")
        exact(row["files"], ("header", "markers", "events", "signal"), "recording files")
        for role in ("header", "markers", "events", "signal"):
            pin = row["files"][role]
            exact(pin, ("path", "bytes", "sha256"), "recording pin")
            _positive(pin["bytes"], "recording bytes")
            require(pin["bytes"] <= (8 * 2**30 if role == "signal" else 2**20),
                    "incumbent provider body bound")
            # The unchanged provider may read through its role cap when a
            # body grows after the first stat. The first failure stops this
            # serial constructor chain; later files cannot also fail-read.
            role_cap = 8 * 2**30 if role == "signal" else 2**20
            failure_maximum = max(failure_maximum, successful_prefix + role_cap + 1)
            successful_prefix += pin["bytes"] + 1
            if role != "signal":
                successful_prefix += pin["bytes"] + 1
    # Provider supports <=4-byte native samples. Both fixed windows are read
    # once per trial, before any candidate execution; no reduced cohort.
    maximum_read = max(failure_maximum, successful_prefix + 2 * 9984 * window_bytes)
    require(allocation["intake_read_bytes"] >= maximum_read,
            "native intake reservation omits authentication or both windows")
    providers, first, secondary = {}, None, []
    try:
        for row in rows:
            budget.check()
            providers[row["participant"], row["task"]] = Recording(intent["data_root"], row)
        recordings = {k: p.rows for k, p in providers.items()}
        certificates = {k: p.certificate for k, p in providers.items()}
        records, ledger = prepare(recordings, providers, certificates, nonce)
        before, before_ledger = prepare(recordings, providers, certificates, nonce, premarker=True)
        require(ledger == before_ledger, "premarker/primary original trial identity differs")
        budget.check()
    except BaseException as exc:
        first = exc
    finally:
        for provider in providers.values():
            try:
                provider.close()
            except BaseException as exc:
                if first is None:
                    first = exc
                else:
                    secondary.append(exc)
    if first is not None:
        raise ProductionFailure(first, secondary, "authentic_intake") from first
    return records, before, ledger, maximum_read


def _window_pin(records):
    from morse_codec import encode_window
    result = {}
    for row in records:
        require(row["id"] not in result, "unique canonical window identity")
        result[row["id"]] = hashlib.sha256(encode_window(row["x"])).hexdigest()
    require(len(result) == 9984, "all9984 canonical windows")
    return digest(result)


def _capsule_descriptors(intent, workspace):
    exact(intent["capsule_sources"], MODES, "both fixed capsule sources")
    output = {}
    for mode in MODES:
        selected = intent["capsule_sources"][mode]
        exact(selected, ("root", "files", "entrypoint"), "capsule source selection")
        manifest = {"schema": "morse-source-capsule-v1", "entrypoint": selected["entrypoint"],
                    "files": sorted(selected["files"], key=lambda p: p["path"])}
        body = canonical_bytes(manifest)
        output[mode] = {"root": str(workspace / "capsules" / mode), "manifest": manifest,
            "manifest_pin": {"path": "CAPSULE.json", "bytes": len(body),
                             "sha256": hashlib.sha256(body).hexdigest()},
            "entrypoint": selected["entrypoint"],
            "files": {p["path"]: p["sha256"] for p in selected["files"]},
            "capsule_sha256": hashlib.sha256(body).hexdigest()}
    return output


def _order_nuisance(intent, root, maximum, ledger, evidence, budget):
    value = document(root, intent["order_nuisance"], maximum, budget)
    exact(value, ("schema", "intake_manifest_sha256", "field", "rows"), "order nuisance input")
    require(value["schema"] == "morse-source-identity-order-nuisance-v1"
            and value["intake_manifest_sha256"] == intent["intake_manifest"]["sha256"]
            and value["field"] == "within_block_order"
            and type(value["rows"]) is list and len(value["rows"]) == 9984,
            "independently selected complete order nuisance")
    inverse = {r["source_identity"]: r["id"] for r in ledger}
    rows = {}
    for row in value["rows"]:
        exact(row, ("source_identity", "within_block_order"), "nuisance row")
        v = row["within_block_order"]
        require(row["source_identity"] in inverse and inverse[row["source_identity"]] not in rows
                and type(v) in (int, float) and math.isfinite(v), "nuisance identity/value")
        rows[inverse[row["source_identity"]]] = [v]
    require(len(rows) == 9984, "all nuisance rows joined without ordinal pairing")
    # This existing-core flag is supplied ONLY after the exact external review
    # artifact and its data pin were selected, captured and matched. Selection
    # authenticity is an external operator responsibility, not inferred here.
    return {"arm": "order_only", "independent_join_verified": True,
            "fields": ["within_block_order"], "rows": rows,
            "certificate_sha256": evidence.pins["references"]["sha256"]}


def run_configuration(config, *, evidence_root, authorization_pin, source_sha256,
                      legacy_root, legacy_pins, budget):
    exact(config, ("schema", "metadata_member_bytes", "intent"), "production configuration")
    require(config["schema"] == "morse-production-configuration-v1", "configuration version")
    _positive(config["metadata_member_bytes"], "metadata member bytes")
    intent = config["intent"]
    exact(intent, ("data_root", "intake_manifest", "nonce_root", "nonce", "workspace_root",
          "storage_configuration", "order_nuisance", "capsule_sources", "paired_parameters",
          "native_profile", "allocation", "reference_seed", "bootstrap_seed", "bootstrap_repetitions"),
          "complete production intent")
    allocation = intent["allocation"]
    exact(allocation, ("intake_read_bytes", "prepared_array_bytes", "premarker_export_bytes",
          "private_member_bytes", "reference_member_bytes", "report_member_bytes",
          "total_artifact_bytes", "aggregate_volume_capacity_bytes"), "explicit full allocation")
    for key, value in allocation.items():
        _positive(value, key)
    require(type(intent["reference_seed"]) is int and intent["reference_seed"] >= 0,
            "explicit reference seed")
    require(type(intent["bootstrap_seed"]) is int and 0 <= intent["bootstrap_seed"] < 2**63
            and type(intent["bootstrap_repetitions"]) is int
            and 1000 <= intent["bootstrap_repetitions"] <= 100000, "existing scorer bootstrap operands")
    workspace = Path(intent["workspace_root"])
    require(type(intent["workspace_root"]) is str and not intent["workspace_root"].startswith("//")
            and str(workspace) == intent["workspace_root"]
            and ".." not in workspace.parts and workspace.is_absolute() and not workspace.exists() and not workspace.is_symlink(),
            "new private workspace")
    ordinary_directory(str(workspace.parent))
    roots = [intent["data_root"], intent["nonce_root"], evidence_root, str(workspace), legacy_root,
             intent["native_profile"]["docker_config_root"]]
    for value in roots:
        if value != str(workspace):
            ordinary_directory(value)
    separated(roots)
    # Only the two capsule source modes may deliberately share a public root;
    # no equality/nesting with private evidence, intake or output is permitted.
    capsule_roots = list(dict.fromkeys(intent["capsule_sources"][m]["root"] for m in MODES))
    for value in capsule_roots:
        ordinary_directory(value)
    separated(roots + capsule_roots)
    dependency_roots = [p["path"] for p in intent["native_profile"]["host_dependency_paths"]]
    for value in dependency_roots:
        ordinary_directory(value)
    separated(roots + capsule_roots + dependency_roots)
    evidence = SelectedEvidence(config, evidence_root, authorization_pin, source_sha256, budget)
    native = SelectedNativeAdmission(evidence, intent["native_profile"], budget)
    evidence.require_model_bound(intent["paired_parameters"]["model_spec"])
    native.prepare_dependencies()
    # No NumPy-bearing task import precedes the actual isolated-startup
    # dependency admission. The unchanged codec remains the representation
    # authority; no constant/kernel is substituted to work around -S.
    from morse_codec import WINDOW_BYTES
    from morse_views import build_fold, export_fold
    from morse_controller import execute_paired
    from morse_reports import target_binding, arm_binding, run_bound_reference, compose_report
    require(allocation["prepared_array_bytes"] >= 2 * 9984 * WINDOW_BYTES,
            "both complete float32 cohorts need explicit capacity")
    nonce = captured(intent["nonce_root"], intent["nonce"], config["metadata_member_bytes"], budget)
    require(len(nonce) >= 32, "independently selected private nonce minimum32bytes")
    records, before, ledger, native_intake_bound = _intake(intent, evidence_root,
        config["metadata_member_bytes"], nonce, allocation, budget, WINDOW_BYTES)
    primary_pin, premarker_pin = _window_pin(records), _window_pin(before)
    nuisance = _order_nuisance(intent, evidence_root, config["metadata_member_bytes"],
                              ledger, evidence, budget)
    capsules = _capsule_descriptors(intent, workspace)
    parameters = dict(intent["paired_parameters"])
    exact(parameters, ("environment", "stage_limits", "broker_limits", "model_spec", "freeze_limits",
          "prediction_max_bytes", "export_max_bytes", "context_max_bytes", "total_reserved_bytes",
          "max_concurrency", "authoring_exposure", "technical_retry_policy", "seed",
          "host_metadata_max_bytes", "workspace_max_files"), "fixed paired parameter operands")
    environment = dict(parameters["environment"])
    require("runtime_root" not in environment, "runtime root is fixed by source staging")
    environment["runtime_root"] = str(workspace / "worker-runtime")
    runtime_pins = [dict(legacy_pins[n], path=n) for n in ("morse_bootstrap.py", "morse_protocol.py")]
    storage_config = document(evidence_root, intent["storage_configuration"],
                              config["metadata_member_bytes"], budget)
    reference_bindings = {}
    for arm in REFERENCE_NAMES:
        provenance = {"arm": arm, "implementation": evidence.records["references"]["methods"][arm],
                      "source_sha256": source_sha256, "seed": intent["reference_seed"],
                      "order_nuisance": intent["order_nuisance"] if arm == "order_only" else None,
                      "premarker_window": "sample-302 through sample-2 inclusive" if arm == "premarker" else None}
        reference_bindings[arm] = {"input_windows_sha256": premarker_pin if arm == "premarker" else primary_pin,
                                   "provenance_sha256": digest(provenance)}
    parameters.update(schema="morse-paired-candidate-p0-v1", canonical_sha256=CANONICAL_SHA256,
        source_receipt_sha256=evidence.source_receipt_sha256, representation=REPRESENTATION,
        policy="P0-training-only-before-query", people=list(PEOPLE), cells=list(CELLS), modes=list(MODES),
        engineering_only=False, scientific_holds=[{"id": h, "qualified": False} for h in HOLDS],
        capsules=capsules, environment=environment, runtime_files=runtime_pins,
        storage_admission_id=storage_config["admission_id"],
        reference_selection={k: digest(v) for k, v in reference_bindings.items()})
    plan = compile_paired_plan(parameters)
    require(Path(storage_config["campaign"]["path"]) == workspace.parent,
            "new workspace must be direct child of admitted campaign mount")
    source_stage_bytes = 2 * (parameters["freeze_limits"]["max_total_bytes"]
        + parameters["freeze_limits"]["max_manifest_bytes"]) + sum(p["bytes"] for p in runtime_pins)
    required_artifacts = (parameters["total_reserved_bytes"] + allocation["premarker_export_bytes"]
        + 5 * allocation["reference_member_bytes"] + 9 * allocation["private_member_bytes"]
        + allocation["report_member_bytes"] + source_stage_bytes)
    require(allocation["total_artifact_bytes"] >= required_artifacts
            and storage_config["campaign"]["bytes"] >= required_artifacts,
            "complete candidate plus reference/report retained capacity")
    physical_capacity = storage_config["campaign"]["bytes"] + sum(
        row[k]["bytes"] for row in storage_config["stages"] for k in ("output", "workspace"))
    require(allocation["aggregate_volume_capacity_bytes"] >= physical_capacity,
            "all257 selected kernel capacities need independent aggregate provisioning")
    storage = None
    stage = "storage_admission"
    try:
        storage = PreprovisionedStorage(plan, storage_config, budget)
        native.bind_plan(plan, storage)
        workspace.mkdir(mode=0o700)
        stage = "source_freeze"
        for mode in MODES:
            selected = intent["capsule_sources"][mode]
            budget.read(len(selected["files"]) * (parameters["freeze_limits"]["max_member_bytes"] + 1))
            budget.write(sum(p["bytes"] for p in selected["files"]) + capsules[mode]["manifest_pin"]["bytes"])
            frozen = freeze_capsule(selected["root"], selected["files"], selected["entrypoint"],
                                    capsules[mode]["root"], parameters["freeze_limits"])
            require(frozen == capsules[mode], "actual frozen source differs from planned capsule")
        runtime = workspace / "worker-runtime"
        runtime.mkdir(mode=0o700)
        for pin in runtime_pins:
            body = captured(legacy_root, pin, parameters["freeze_limits"]["max_member_bytes"], budget)
            budget.write(len(body))
            write_new(runtime / pin["path"], body)
            os.chmod(runtime / pin["path"], 0o444)
        _save(workspace, "PRIVATE_INTAKE_LEDGER.json", ledger, allocation["private_member_bytes"], budget)
        _save(workspace, "PRODUCTION_SELECTION.json", {"plan": plan, "reference_bindings": reference_bindings,
            "authorization": authorization_pin, "evidence": evidence.pins,
            "native_intake_read_reservation": native_intake_bound,
            "allocation": allocation, "qualification_created": False}, allocation["private_member_bytes"], budget)
        pre_plan = build_fold(before, PEOPLE[0], nonce, "premarker-" + plan["sha256"][:16])
        pre_export = export_fold(pre_plan, workspace / "premarker",
                                  max_total_bytes=allocation["premarker_export_bytes"])
        require(digest(pre_export["canonical_window_pins"]) == premarker_pin,
                "premarker serialized numeric identity differs")
        stage = "paired_candidates"
        result = execute_paired(plan, records, nonce, workspace / "execution",
                    native_admission=native, storage_admission=storage, token_admission=evidence)
        require(result["primary_windows_sha256"] == primary_pin,
                "candidate serialization differs from frozen reference selection")
        private = Path(result["root"]) / "private"
        targets = _load_artifact(private, result["targets"], target_binding(plan),
                                  allocation["private_member_bytes"], budget)
        arms = {}
        for mode in MODES:
            binding = arm_binding(plan, targets.pin["sha256"], primary_pin, mode,
                input_windows_sha256=primary_pin, provenance_sha256=digest(plan["spec"]["capsules"][mode]))
            arms[mode] = _load_artifact(private, result["predictions"][mode], binding,
                                       allocation["reference_member_bytes"], budget)
        stage = "five_references"
        for arm in REFERENCE_NAMES:
            budget.check()
            reference = run_bound_reference(result["reference_export"], result["reference_inverse"], arm,
                seed=intent["reference_seed"], nuisance=nuisance if arm == "order_only" else None,
                premarker_receipt=pre_export if arm == "premarker" else None,
                premarker_inverse=pre_plan.inverse if arm == "premarker" else None)
            require(reference["primary_windows_sha256"] == primary_pin
                    and reference["input_windows_sha256"] == reference_bindings[arm]["input_windows_sha256"],
                    "actual reference values differ from frozen selection")
            pin = _save(workspace, arm + "-predictions.json", reference["predictions"],
                         allocation["reference_member_bytes"], budget)
            # Preserve the complete fitting metadata, not just an aggregate score.
            _save(workspace, arm + "-fit.json", {k: v for k, v in reference.items() if k != "predictions"},
                  allocation["private_member_bytes"], budget)
            binding = arm_binding(plan, targets.pin["sha256"], primary_pin, arm, **reference_bindings[arm])
            arms[arm] = _load_artifact(workspace, pin, binding, allocation["reference_member_bytes"], budget)
        stage = "private_report"
        execution_binding = {"schema": "morse-private-execution-v1", "plan_sha256": plan["sha256"],
            "source_receipt_sha256": parameters["source_receipt_sha256"], "canonical_sha256": CANONICAL_SHA256}
        execution = _load_artifact(private, result["execution"], execution_binding,
                                    allocation["private_member_bytes"], budget)
        report = compose_report(plan, targets, arms, primary_windows_sha256=primary_pin,
            reference_bindings=reference_bindings, execution_receipt=execution,
            bootstrap_seed=intent["bootstrap_seed"], repetitions=intent["bootstrap_repetitions"])
        require(report["report_composition_complete"] is True, "complete seven-arm diagnostic required")
        storage_receipt = storage.finalize()
        _save(workspace, "STORAGE_FINAL.json", storage_receipt, allocation["private_member_bytes"], budget)
        report_pin = _save(workspace, "REPORT.json", report, allocation["report_member_bytes"], budget)
        return {"schema": "morse-production-result-v1", "workspace_root": str(workspace),
                "report": report_pin, "plan_sha256": plan["sha256"], "benchmark_count": 1,
                "scientific_qualification": False, "native_qualification_created": False,
                "logical_contexts": 64, "stage_launches": 128, "metadata_budget": budget.snapshot()}
    except BaseException as first:
        secondary = []
        if storage is not None:
            try:
                storage.close_failed()
            except BaseException as exc:
                secondary.append(exc)
        if workspace.exists():
            try:
                _save(workspace, "PRODUCTION_FAILURE.json", {"stage": stage,
                    "first_type": type(first).__name__, "secondary_types": [type(e).__name__ for e in secondary],
                    "complete": False, "scientific_qualification": False,
                    "partial_artifacts_preserved": True, "metadata_budget": budget.snapshot()},
                    allocation["private_member_bytes"], budget)
            except BaseException as exc:
                secondary.append(exc)
        raise ProductionFailure(first, secondary, stage) from first
