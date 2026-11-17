"""Complete128-stage actual caller wiring with explicitly inert scientific leaves.

Two metadata-only campaigns: complete success and last query failure. Neither
performs an EEG transform, model invocation, Docker action or native admission.
Full32/6/26/2 records are invented identities, not nominal-shaped signal arrays.
"""
import hashlib
import json
import os
from pathlib import Path
import types

from control_support import require, patched, refuses

PARTIAL = {}


class Sink:
    """Virtual private artifact sink: exact bytes are hashed then discarded.

This substitutes physical private persistence, not its schema/order consumer.
Only small closure receipts are retained, explicitly capped before copying.
"""
    def __init__(self, selection):
        self.selection = selection
        self.pins, self.receipts = {}, {}
        self.bytes = 0

    def write(self, path, body):
        path = Path(path)
        if "worker-runtime" in path.parts or "capsules" in path.parts:
            return self.selection.write_new(path, body)
        require(str(path) not in self.pins, "virtual sink refuses overwrite")
        require(len(body) <= 4 * 2**20, "finite virtual metadata member")
        self.bytes += len(body)
        require(self.bytes <= 12 * 2**20, "declared virtual campaign body bound")
        self.pins[str(path)] = {"path": path.name, "bytes": len(body),
                                "sha256": hashlib.sha256(body).hexdigest()}
        if path.name in ("execution.json", "failure.json", "PRODUCTION_FAILURE.json", "REPORT.json"):
            require(len(body) <= 512 * 1024, "small retained closure receipt")
            self.receipts[path.name] = json.loads(body)

    def pin(self, path, name=None):
        result = dict(self.pins[str(path)])
        if name is not None:
            result["path"] = name
        return result


def run(sources, meter, root, log, *, late_failure):
    # Before fixture creation: four passes over the12MiB virtual sink,
    # all64 additional digest(restored) encodings/hashes, context hash reads,
    # finite plan/seal/broker work and8MiB fixture/sort representations.
    # This is70MiB of prospective managed work, not native signal allocation.
    meter.charge(read=32 * 2**20, write=38 * 2**20,
                 label="full128 recipe: sink48MiB+digest11502080+context524288+other2MiB+fixture8MiB")
    root = Path(root)
    PARTIAL.update(case="late_failure" if late_failure else "positive", stages=0, references=0,
                   protected_artifact_calls=0, complete=False)
    contract = sources.load("contract")
    selection = sources.load("morse_selection")
    policy = sources.load("production_policy")
    operation = sources.load("production_operation")
    sink = Sink(selection)
    events, stages, fits, refs = [], [], {}, []
    first = RuntimeError("invented last case-adaptive query failure")
    close_failure = OSError("invented storage independent closure failure")
    publication_failure = OSError("invented failure receipt publication refusal")
    sentinel = object()
    records = []
    for person in contract.PEOPLE:
        for cell in contract.CELLS:
            for label in range(26):
                for repeat in range(2):
                    identity = f"{person}/{cell}/{label}/{repeat}"
                    records.append({"id": hashlib.sha256(identity.encode()).hexdigest(),
                                    "participant": person, "cell": cell, "label": label})
    require(len(records) == 9984, "full invented roster")
    # No original/private identity or EEG body appears in this suite.
    ledger = [{"id": row["id"], "source_identity": row["id"]} for row in records]
    primary_map = {"INERT_NUMERIC_LEAF": "0" * 64}
    primary_pin = selection.digest(primary_map)
    prepared = False
    exports = {}

    def build_fold(rows, held, secret, namespace):
        require(prepared and rows is records and len(rows) == 9984, "fold after admitted inert intake")
        query = tuple({"id": r["id"]} for r in rows if r["participant"] == held)
        require(len(query) == 312, "all312 held-person metadata identities")
        # This deliberately substitutes numerical fold/alias construction. It
        # does NOT establish alias privacy, window equality or training labels.
        return types.SimpleNamespace(query=query, inverse={"INERT_INVERSE": held},
            held_participant=held, namespace=namespace)

    def export_fold(fold, destination, *, max_total_bytes):
        destination = Path(destination)
        destination.mkdir(); (destination / "training").mkdir(); (destination / "query").mkdir()
        receipt = {"held_participant": fold.held_participant, "namespace": fold.namespace,
                   "training_root": str(destination / "training"), "query_root": str(destination / "query"),
                   "training_manifest": {"path": "manifest.json", "bytes": 1, "sha256": "0" * 64},
                   "canonical_window_pins": primary_map}
        exports[receipt["query_root"]] = fold.query
        return receipt

    def compare(a, b):
        require(a["canonical_window_pins"] == b["canonical_window_pins"], "same inert window leaf")

    def capture_predictions(path, aliases, *, max_bytes):
        require(len(aliases) == len(set(aliases)) == 312, "full expected query identities")
        return types.SimpleNamespace(ids=tuple(aliases), payload_sha256="1" * 64, canonical_sha256="2" * 64)

    def restore(capture, inverse):
        require(set(inverse) == {"INERT_INVERSE"}, "declared inert inverse boundary")
        return [{"id": identity, "probabilities": [1] + [0] * 25} for identity in capture.ids]

    def run_reference(receipt, inverse, arm, **kwargs):
        require(len(stages) == 128 and stages[-1][2] == "query", "all candidate closure before any reference")
        refs.append(arm)
        PARTIAL["references"] = len(refs)
        return {"predictions": [{"inert_reference": arm}], "primary_windows_sha256": primary_pin,
                "input_windows_sha256": primary_pin, "fits": [{"participant": p, "inert": True} for p in contract.PEOPLE]}

    def compose(plan, targets, arms, **kwargs):
        require(tuple(refs) == selection.REFERENCE_NAMES, "complete exact five-reference order")
        require(set(arms) == set(selection.MODES) | set(selection.REFERENCE_NAMES), "both modes plus all five references")
        require(kwargs["execution_receipt"].value["complete"] is True, "closed actual controller receipt")
        events.append("report")
        return {"report_composition_complete": True, "scientific_qualification": False,
                "INERT_REPORT_LEAF": True, "arms": sorted(arms)}

    def install_numerical_leaves():
        nonlocal prepared
        require("numpy" not in __import__("sys").modules, "no NumPy available or imported")
        for name in ("morse_codec", "morse_views", "morse_controller", "morse_reports"):
            require(name not in __import__("sys").modules, "numerical caller import precedes admission: " + name)
        events.append("dependency_admission")
        sources.shim("morse_codec", WINDOW_BYTES=62 * 301 * 4)
        sources.shim("morse_views", build_fold=build_fold, export_fold=export_fold,
                     compare_canonical_windows=compare)
        sources.shim("morse_capture", capture_predictions=capture_predictions, restore_predictions=restore)
        sources.shim("morse_reports", target_binding=lambda plan: {"role": "target"},
                     arm_binding=lambda *a, **k: {"role": "arm"}, run_bound_reference=run_reference,
                     compose_report=compose)
        prepared = True
        controller = sources.load("morse_controller")
        # All numerical/provider/native leaves are explicit here; the actual
        # controller, stage-spec/context/schema, seal and success checks remain.
        controller.export_fold = export_fold
        controller.write_new = sink.write
        controller.file_pin = sink.pin
        controller.HttpsJsonEngine = Engine
        controller.run_stage = stage_runner
        return controller

    class Evidence:
        def __init__(self, config, *args):
            self.intent = config["intent"]
            self.source_receipt_sha256 = "3" * 64
            self.pins = {k: {"path": k + ".json", "bytes": 1, "sha256": "3" * 64}
                         for k in ("intake", "deployment", "token", "references")}
            self.records = {"references": {"methods": {a: ("erp_shrinkage" if a == "validated_competent_EEG_reference" else a)
                                                       for a in selection.REFERENCE_NAMES}}}
            events.append("external_evidence_leaf")

        def require_model_bound(self, spec):
            require(spec["endpoint"] == "https://invented.invalid/no-call", "inert fixed endpoint only")

    class Native:
        def __init__(self, evidence, profile, budget):
            self.storage = None

        def prepare_dependencies(self):
            install_numerical_leaves()

        def bind_plan(self, plan, storage):
            require(self.storage is None and storage.plan_sha256 == plan["sha256"], "one plan/storage bind")
            self.storage = storage

        def require_paired_execution(self, plan, rows, run_root):
            require(self.storage is not None and rows is records and len(rows) == 9984, "full actual controller native seam")
            events.append("native_admission_leaf")

        def command_transport(self):
            events.append("transport")
            return sentinel

    class Engine:
        kind = "engineering_injected_engine"
        def __init__(self, model_spec, *, token_admission):
            token_admission.require_model_bound(model_spec)

        def generate(self, *args, **kwargs):
            raise AssertionError("no model request selected")

    class Storage:
        def __init__(self, plan, config, budget):
            self.plan_sha256, self.config = plan["sha256"], config
            self.used, self.consumed = [], []
            self.lookup = {}
            for row in config["stages"]:
                context_id = hashlib.sha256((self.plan_sha256 + row["participant"] + row["mode"]).encode()).hexdigest()[:32]
                self.lookup[context_id, row["mode"], row["phase"]] = row
            require(len(self.lookup) == 128, "all fixed stage roots selected")
            storage_instances.append(self)

        def stage_roots(self, context_id, mode, phase):
            key = context_id, mode, phase
            require(key in self.lookup and key not in self.used, "single-use exact stage")
            self.used.append(key)
            row = self.lookup[key]
            return {"output_root": row["output"]["path"], "workspace_root": row["workspace"]["path"]}

        def require_storage(self, profile):
            key = self.used[-1]
            require(key not in self.consumed, "single admission")
            self.consumed.append(key)

        def finalize(self):
            require(len(self.used) == len(self.consumed) == 128, "full storage lifecycle seam")
            events.append("storage_finalize")
            return {"complete": True, "INERT_STORAGE": True, "stages": 128}

        def close_failed(self):
            events.append("storage_close_failed")
            if late_failure:
                raise close_failure

    def stage_runner(stage, broker, *, storage_admission, transport):
        require(transport is sentinel, "actual partial binds selected native transport")
        require((broker.context_id, broker.phase) == (stage["context_id"], stage["phase"]), "broker identity parity")
        require(broker.calls == 0, "actual broker constructed without any model dispatch")
        storage_admission.require_storage(stage["storage_profile"])
        stages.append((stage["context_id"], stage["mode"], stage["phase"]))
        PARTIAL["stages"] = len(stages)
        if late_failure and len(stages) == 128:
            raise first
        if stage["phase"] == "train":
            body = b"INVENTED FIT STATE; NEVER EXECUTED\n"
            out = Path(stage["output_root"])
            selection.write_new(out / "state.txt", body)
            pin = {"path": "state.txt", "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
            selection.write_new(out / "fit_manifest.json", selection.canonical_bytes({"context_id": stage["context_id"], "files": [pin]}))
            fits[stage["context_id"]] = True
        else:
            require(fits.get(stage["context_id"]) is True and Path(stage["fit_root"]).is_dir(), "sealed fit before query")
        return {"success": True, "terminal_observed": True, "cleanup_complete": True,
                "container_exit_code": 0, "attach_exit_code": 0, "broker_thread_terminal": True,
                **{k: stage[k] for k in ("context_id", "mode", "phase")}, "INERT_WORKER": True}

    folders = {}
    for name in ("data", "nonce", "evidence", "campaign", "docker-config", "dependency", "capsule", "stage-roots"):
        folders[name] = root / name
        folders[name].mkdir(mode=0o700)
    capsule_body = b"# INERT SOURCE; THIS CANDIDATE IS NEVER EXECUTED\n"
    selection.write_new(folders["capsule"] / "candidate.py", capsule_body)
    capsule_pin = {"path": "candidate.py", "bytes": len(capsule_body), "sha256": hashlib.sha256(capsule_body).hexdigest()}
    limits = {"wall_seconds": 1, "cleanup_seconds": 9, "cpus": 1, "cpu_seconds": 11,
              "memory_bytes": 2**20, "pids": 8, "file_bytes": 65536, "nofile": 64,
              "workspace_bytes": 65536, "output_bytes": 65536, "tmp_bytes": 65536,
              "stderr_bytes": 4096, "stdout_bytes": 4096, "frame_bytes": 4096,
              "command_timeout_seconds": 1, "gpu_devices": []}
    stages_config = []
    for number, triple in enumerate((p, m, phase) for p in contract.PEOPLE for m in selection.MODES for phase in ("train", "query")):
        row = dict(zip(("participant", "mode", "phase"), triple))
        for key in ("output", "workspace"):
            p = folders["stage-roots"] / (str(number) + "-" + key);p.mkdir(mode=0o700)
            row[key] = {"path": str(p), "bytes": 65536}
        stages_config.append(row)
    storage_config = {"admission_id": "INERT_STORAGE", "campaign": {"path": str(folders["campaign"]), "bytes": 2**38}, "stages": stages_config}
    model = {"endpoint": "https://invented.invalid/no-call", "model_revision": "INERT", "credential_env": "MUST_NOT_READ",
             "protocol": "messages-text-usage-v1", "request_max_bytes": 4096, "response_max_bytes": 4096,
             "stderr_max_bytes": 4096, "timeout_seconds": 1,
             "token_bound": {"utf8_multiplier": 1, "fixed_overhead": 0, "per_message_overhead": 0, "certificate_sha256": "4" * 64}}
    params = {"environment": {"image_digest": "sha256:" + "5" * 64, "python_executable": "/usr/bin/python3", "container_uid": 1234, "container_gid": 1234},
              "stage_limits": limits, "broker_limits": {"max_calls": 1, "input_tokens": 32, "output_tokens": 32,
                  "max_input_bytes": 4096, "max_messages": 2, "frame_bytes": 4096, "call_seconds": 1}, "model_spec": model,
              "freeze_limits": {"max_files": 2, "max_member_bytes": 65536, "max_total_bytes": 65536, "max_manifest_bytes": 65536},
              "prediction_max_bytes": 2**20, "export_max_bytes": 745285632, "context_max_bytes": 16384,
              "total_reserved_bytes": 2**36, "max_concurrency": 1, "authoring_exposure": {"declared": True},
              "technical_retry_policy": "abort-preserve-no-automatic-retry", "seed": 0,
              "host_metadata_max_bytes": 16 * 2**20, "workspace_max_files": 2}
    pin = {"path": "inert.json", "bytes": 1, "sha256": "6" * 64}
    intent = {"data_root": str(folders["data"]), "intake_manifest": pin, "nonce_root": str(folders["nonce"]), "nonce": dict(pin, path="nonce"),
              "workspace_root": str(folders["campaign"] / "run"), "storage_configuration": dict(pin, path="storage"),
              "order_nuisance": dict(pin, path="order"), "capsule_sources": {m: {"root": str(folders["capsule"]), "files": [capsule_pin], "entrypoint": "candidate.py"} for m in selection.MODES},
              "paired_parameters": params, "native_profile": {
                  "docker_binary": {"path": "/INERT-NOT-EXECUTED/docker", "bytes": 1, "sha256": "8" * 64},
                  "host_python": {"path": "/INERT-NOT-EXECUTED/python", "bytes": 1, "sha256": "8" * 64},
                  "docker_socket": {"path": "/INERT-NOT-OPENED/docker.sock", "device": 1, "inode": 1, "uid": 1234, "mode": 0o600},
                  "deployment_id": "INERT_NO_NATIVE_EVIDENCE", "host_owner_source_sha256": "8" * 64,
                  "docker_config_root": str(folders["docker-config"]), "numpy_version": "INERT_NO_IMPORT",
                  "host_dependency_paths": [{"path": str(folders["dependency"]), "device": folders["dependency"].stat().st_dev,
                      "inode": folders["dependency"].stat().st_ino, "uid": folders["dependency"].stat().st_uid, "mode": 0o700}]},
              "allocation": {"intake_read_bytes": 2**35, "prepared_array_bytes": 2 * 9984 * 62 * 301 * 4,
                  "premarker_export_bytes": 745285632, "private_member_bytes": 2 * 2**20, "reference_member_bytes": 2**20,
                  "report_member_bytes": 2**20, "total_artifact_bytes": 2**37, "aggregate_volume_capacity_bytes": 2**39},
              "reference_seed": 0, "bootstrap_seed": 0, "bootstrap_repetitions": 1000}
    config = {"schema": "morse-production-configuration-v1", "metadata_member_bytes": 2**20, "intent": intent}
    storage_instances = []
    nuisance = {"schema": "morse-source-identity-order-nuisance-v1", "intake_manifest_sha256": pin["sha256"],
                "field": "within_block_order", "rows": [{"source_identity": r["id"], "within_block_order": i} for i, r in enumerate(records)]}

    def document(root, p, maximum, budget):
        if p["path"] == "storage": return storage_config
        if p["path"] == "order": return nuisance
        raise AssertionError("unexpected metadata leaf")

    def captured(root, p, maximum, budget):
        if p["path"] == "nonce": return b"x" * 32
        return policy.captured(root, p, maximum, budget)

    def load_artifact(root, p, binding, maximum, budget):
        events.append("artifact:" + p["path"])
        PARTIAL["protected_artifact_calls"] += 1
        require(len(stages) == 128 and not late_failure, "protected artifacts only after both complete modes")
        return types.SimpleNamespace(pin=dict(p), value=sink.receipts.get(p["path"], {}))

    def save(root, name, value, maximum, budget):
        if late_failure and name == "PRODUCTION_FAILURE.json":
            events.append("failure_publication")
            raise publication_failure
        return original_save(root, name, value, maximum, budget)

    class Budget:
        """Explicit inert native allocation ledger; outer Meter charged above.

        Production metadata max reservations remain recorded; they are neither
        actual RAM allocation nor a declaration that native data were read.
        """
        def __init__(self): self.read_reserved = self.write_reserved = 0
        def check(self): meter.check()
        def read(self, n): require(type(n) is int and n >= 0, "metadata read reservation"); self.read_reserved += n
        def write(self, n): require(type(n) is int and n >= 0, "metadata write reservation"); self.write_reserved += n
        def snapshot(self): return {"INERT_NATIVE_ALLOCATION": True, "read": self.read_reserved, "write": self.write_reserved}

    original_save = operation._save
    legacy_pins = {p["path"]: p for p in sources.manifest["legacy_files"]}
    with patched(operation, SelectedEvidence=Evidence, SelectedNativeAdmission=Native, PreprovisionedStorage=Storage,
                 document=document, captured=captured, _intake=lambda *a: (records, records, ledger, 2**35),
                 _window_pin=lambda rows: primary_pin, write_new=sink.write, _load_artifact=load_artifact, _save=save):
        call = lambda: operation.run_configuration(config, evidence_root=str(folders["evidence"]),
            authorization_pin=pin, source_sha256="7" * 64, legacy_root=str(sources.legacy),
            legacy_pins=legacy_pins, budget=Budget())
        if late_failure:
            exc = refuses(call)
            require(type(exc) is operation.ProductionFailure and exc.first is first
                    and exc.secondary == (close_failure, publication_failure), "original worker and both independent failures retained")
            require(not refs and not any(e.startswith("artifact:") for e in events), "last failure closes protected target/reference barrier")
            receipt = sink.receipts["failure.json"]
            require(receipt["complete"] is False and receipt["actual_stage_launches"] == 128
                    and len(receipt["contexts"]) == 63, "honest last-query failed receipt")
            log.passed("full128_last_query_failure", completed_contexts=63, target_or_reference_reads=0,
                       original_error_retained=True, independent_errors_retained=2)
        else:
            result = call()
            receipt = sink.receipts["execution.json"]
            require(result["scientific_qualification"] is False and result["stage_launches"] == 128
                    and result["logical_contexts"] == 64 and receipt["complete"] is True
                    and len(receipt["contexts"]) == 64, "full paired result scope")
            require(len(refs) == 5 and events.index("report") < events.index("storage_finalize"), "five references/report before final storage receipt")
            require(all(x["qualified"] is False for x in receipt["scientific_holds"]), "all13 holds unchanged")
            log.passed("full128_success_then_five_references", contexts=64, stages=128, references=5,
                       scientific_qualification=False)
    require(len(stages) == 128 and len(fits) == 64, "complete fixed stage plan reached exactly once")
    require(events.count("transport") == 128, "actual selected transport bound on all128 calls")
    require(all(stages[i][0:2] == stages[i + 1][0:2] and stages[i][2] == "train"
                and stages[i + 1][2] == "query" for i in range(0, 128, 2)), "train/seal/query context parity")
    PARTIAL.update(complete=True, virtual_metadata_bytes=sink.bytes)
    return {"case": "late_failure" if late_failure else "positive", "stages": len(stages),
            "virtual_metadata_bytes": sink.bytes, "virtual_members": len(sink.pins),
            "physical_fixture_signal_arrays": 0, "model_calls": 0, "container_launches": 0,
            "source_guards_exercised": ["actual operation/control order", "full scope plan compiler", "_stage_spec/_context",
                "validate_spec", "native transport partial", "_success", "fit seal/readback", "complete predictions count", "failure propagation"],
            "substitutions": ["external evidence/native admission", "kernel storage (separate actual storage suite)",
                "intake/preparation/window hashing", "numeric fold/export/inverse", "prediction capture/restore",
                "model engine and worker (actual zero-call ModelBroker retained)", "private artifact sink/capture", "reference arithmetic/report grading"],
            "interpretation": "Actual full caller metadata wiring, not signal, privacy, numerical, native or scientific qualification"}
