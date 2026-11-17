"""Trusted P0 lifecycle composition; never imports a candidate on the host.

The production route uses the concrete Docker transport and HTTPS broker. It
requires separately admitted native containment/storage/token/source policies.
EngineeringLeaves is an explicit invented-control route, never native evidence.
No scientific execution happens on import or plan compilation.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import os

from contract import PEOPLE, CELLS, require
from morse_selection import (MODES, canonical_bytes, digest, compile_paired_plan,
    read_member, write_new, file_pin, seal_fit_state, verify_fit_seal)
from morse_views import build_fold, export_fold, compare_canonical_windows
from morse_capture import capture_predictions, restore_predictions
from morse_broker import ModelBroker, HttpsJsonEngine, validate_model_spec
from morse_docker import run_stage, validate_spec


@dataclass(frozen=True)
class EngineeringLeaves:
    """All four substitutions must be declared; no implied production capability."""
    export: object
    stage: object
    broker: object
    label: str


def _success(receipt, stage):
    require(type(receipt) is dict and receipt.get("success") is True
            and receipt.get("terminal_observed") is True
            and receipt.get("cleanup_complete") is True
            and type(receipt.get("container_exit_code")) is int and receipt["container_exit_code"] == 0
            and type(receipt.get("attach_exit_code")) is int and receipt["attach_exit_code"] == 0
            and receipt.get("broker_thread_terminal") is True,
            "terminal successful stage and complete cleanup required")
    require(all(receipt.get(key) == stage[key] for key in ("context_id", "mode", "phase")),
            "trusted stage context/mode/phase binding required")


def _tree(root):
    root = Path(root)
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(), "ordinary source root")
    names = set()
    for current, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            require(not (Path(current) / name).is_symlink(), "source symlink forbidden")
        for name in files:
            names.add(str((Path(current) / name).relative_to(root)))
    return names


def verify_sources(spec):
    """Verify every mounted source byte before any worker can start."""
    runtime = Path(spec["environment"]["runtime_root"])
    require(_tree(runtime) == {"morse_bootstrap.py", "morse_protocol.py"}, "worker runtime must exclude host modules")
    for pin in spec["runtime_files"]:
        read_member(runtime, pin, spec["freeze_limits"]["max_member_bytes"])
    for capsule in spec["capsules"].values():
        require(_tree(capsule["root"]) == set(capsule["files"]) | {"CAPSULE.json"}, "complete capsule inventory")
        body = read_member(capsule["root"], capsule["manifest_pin"], spec["freeze_limits"]["max_manifest_bytes"])
        require(hashlib.sha256(body).hexdigest() == capsule["capsule_sha256"]
                and body == canonical_bytes(capsule["manifest"]), "frozen capsule manifest")
        require(capsule["manifest"]["entrypoint"] == capsule["entrypoint"]
                and {p["path"]: p["sha256"] for p in capsule["manifest"]["files"]} == capsule["files"],
                "capsule descriptor matches manifest")
        for pin in capsule["manifest"]["files"]:
            read_member(capsule["root"], pin, spec["freeze_limits"]["max_member_bytes"])


def capture_workspace(root, spec):
    """Retain all ordinary generated files after terminal cleanup; never execute."""
    names = sorted(_tree(root))
    require(len(names) <= spec["workspace_max_files"], "workspace file-count limit")
    pins, size = [], 0
    for name in names:
        path = Path(root) / name
        require(path.lstat().st_size <= spec["stage_limits"]["file_bytes"], "workspace member bound")
        pin = file_pin(path, name)
        read_member(root, pin, spec["stage_limits"]["file_bytes"])
        size += pin["bytes"]
        require(size <= spec["stage_limits"]["workspace_bytes"], "workspace aggregate bound")
        pins.append(pin)
    return {"root": str(root), "files": pins, "bytes": size,
            "note": "post-terminal file capture; not proof that every in-memory operation was logged"}


def _stage_spec(spec, context_id, mode, phase, capsule, exported, fit, stage_root):
    stage_root = Path(stage_root)
    stage_root.mkdir(mode=0o700)
    for leaf in ("context", "output", "work"):
        (stage_root / leaf).mkdir(mode=0o700)
    limits = spec["stage_limits"]
    storage = {"mechanism": "independently_admitted_bounded_host_volumes_v1",
               "admission_id": spec["storage_admission_id"],
               "output_root": str(stage_root / "output"), "workspace_root": str(stage_root / "work"),
               "output_bytes": limits["output_bytes"], "workspace_bytes": limits["workspace_bytes"]}
    env = spec["environment"]
    return {"context_id": context_id, "mode": mode, "phase": phase,
            "name": "morse-" + context_id + "-" + phase,
            "image_digest": env["image_digest"], "python_executable": env["python_executable"],
            "container_uid": env["container_uid"], "container_gid": env["container_gid"],
            "runtime_root": env["runtime_root"], "capsule_root": capsule["root"],
            "train_root": exported["training_root"],
            "query_root": exported["query_root"] if phase == "query" else None,
            "fit_root": fit["root"] if phase == "query" else None,
            "context_root": str(stage_root / "context"), "output_root": str(stage_root / "output"),
            "workspace_root": str(stage_root / "work"), "limits": limits, "storage_profile": storage}


def _context(spec, stage, capsule, exported, fit):
    payload = {"policy": spec["policy"], "representation": spec["representation"],
               "cells": list(CELLS), "classes": 26, "shape": [62, 301], "seed": spec["seed"],
               "training_manifest": "/training/manifest.json",
               "query_manifest": "/query/manifest.json" if stage["phase"] == "query" else None,
               "fit_seal": "/fit/FIT_SEAL.json" if stage["phase"] == "query" else None,
               "output_root": "/output", "workspace_root": "/work",
               "nominal_training_rows": 9672, "nominal_query_rows": 312,
               "model_revision": spec["model_spec"]["model_revision"],
               "stage_broker_limits": spec["broker_limits"],
               "query_policy": "diagnostic exploration and fixed inference; no fitting/tuning/normalization on query",
               "training_view_sha256": exported["training_manifest"]["sha256"]}
    context = {"phase": stage["phase"], "mode": stage["mode"], "context_id": stage["context_id"],
               "entrypoint": capsule["entrypoint"],
               "capsule_files": dict(capsule["files"], **{"CAPSULE.json": capsule["capsule_sha256"]}),
               "payload": payload}
    body = canonical_bytes(context)
    require(len(body) <= spec["context_max_bytes"], "context byte budget")
    write_new(Path(stage["context_root"]) / "context.json", body)
    return hashlib.sha256(body).hexdigest()


def execute_paired(compiled, records, private_secret, run_root, *, native_admission=None,
                   storage_admission=None, token_admission=None, engineering_leaves=None):
    """Execute the complete selected assay or preserve a failure and abort.

    A native admission is an independently selected trusted registry object with
    require_paired_execution(compiled, records, run_root). Its acceptance must
    cover authenticated intake, fixed image/runtime, containment/provider state,
    physical run storage and explicit scientific execution authorization. This
    source ships no implementation or affirmative admission. It is not a flag
    in candidate metadata. The actual worker/broker paths below remain concrete.
    """
    plan = compile_paired_plan(compiled["spec"])
    require(plan == compiled, "compiled plan mutated")
    spec = plan["spec"]
    require(isinstance(private_secret, bytes) and len(private_secret) >= 32, "private alias secret")
    require(type(records) is list and len(records) == 9984, "full source cohort")
    # Actual fold validation checks every class and participant before dispatch.
    first_fold = build_fold(records, PEOPLE[0], private_secret, "fold-00-" + plan["sha256"][:16])
    verify_sources(spec)
    validate_model_spec(spec["model_spec"])
    root = Path(run_root)
    require(root.is_absolute() and not root.exists(), "new private run root")
    if engineering_leaves is not None:
        require(type(engineering_leaves) is EngineeringLeaves and spec["engineering_only"] is True
                and engineering_leaves.label, "explicit engineering-only substitutions")
    else:
        require(spec["engineering_only"] is False and native_admission is not None
                and storage_admission is not None and token_admission is not None,
                "native source/storage/token/containment admission unavailable")
        native_admission.require_paired_execution(plan, records, str(root))
    root.mkdir(mode=0o700)
    private = root / "private"
    private.mkdir(mode=0o700)
    private_bytes = 0
    def write_private(path, body):
        nonlocal private_bytes
        require(private_bytes + len(body) <= spec["host_metadata_max_bytes"], "private metadata aggregate bound")
        write_new(path, body)
        private_bytes += len(body)
    write_private(private / "plan.json", canonical_bytes(plan))
    targets = sorted(({k: row[k] for k in ("id", "participant", "cell", "label")} for row in records),
                     key=lambda r: r["id"])
    write_private(private / "targets.json", canonical_bytes(targets))
    receipt = {"schema": "morse-paired-execution-v1", "plan_sha256": plan["sha256"],
               "source_receipt_sha256": spec["source_receipt_sha256"],
               "canonical_sha256": spec["canonical_sha256"],
               "complete": False, "logical_contexts": 64, "stage_launches": 128,
               "actual_stage_launches": 0, "engineering_only": spec["engineering_only"],
               "engineering_leaves": engineering_leaves.label if engineering_leaves else None,
               "contexts": [], "scientific_holds": spec["scientific_holds"],
               "scientific_qualification": False, "native_containment_qualified": False,
               "nominal_counts_only": True, "benchmark_count": 1,
               "budget_unit": "stage; each logical context reserves two equal stage allocations",
               "provider_state_independence_qualified": False,
               "hidden_transductive_fitting_excluded": False}
    predictions = {mode: [] for mode in MODES}
    canonical_receipt = None
    current = None
    try:
        for number, person in enumerate(PEOPLE):
            namespace = "fold-%02d-" % number + plan["sha256"][:16]
            fold_plan = first_fold if number == 0 else build_fold(records, person, private_secret, namespace)
            fold_root = root / ("fold-%02d" % number)
            fold_root.mkdir(mode=0o700)
            exporter = engineering_leaves.export if engineering_leaves else export_fold
            exported = exporter(fold_plan, fold_root / "views", max_total_bytes=spec["export_max_bytes"])
            require(exported["held_participant"] == person and exported["namespace"] == namespace,
                    "export identity binding")
            if canonical_receipt is None:
                canonical_receipt = exported
            else:
                compare_canonical_windows(canonical_receipt, exported)
            write_private(private / (namespace + "-inverse.json"), canonical_bytes(fold_plan.inverse))
            write_private(private / (namespace + "-export.json"), canonical_bytes(exported))
            for mode in MODES:
                # Same aliases/order/files in both modes. Contexts share no writable roots,
                # fitted state, engine instance, transcript or query feedback.
                capsule = spec["capsules"][mode]
                context_id = hashlib.sha256((plan["sha256"] + person + mode).encode()).hexdigest()[:32]
                context_root = fold_root / mode
                context_root.mkdir(mode=0o700)
                current = {"participant": person, "mode": mode, "context_id": context_id}
                fit = None
                for phase in ("train", "query"):
                    if phase == "query":
                        verify_fit_seal(fit, spec["freeze_limits"])
                    stage = _stage_spec(spec, context_id, mode, phase, capsule, exported,
                                        fit, context_root / phase)
                    current[phase + "_context_sha256"] = _context(spec, stage, capsule, exported, fit)
                    validate_spec(stage)
                    if engineering_leaves:
                        broker = engineering_leaves.broker(stage, spec)
                        runner = engineering_leaves.stage
                    else:
                        # A new stateless host engine/ledger per stage. Remote retention,
                        # model identity and cross-context provider state remain admitted
                        # registry obligations, not established by a fresh Python object.
                        engine = HttpsJsonEngine(spec["model_spec"], token_admission=token_admission)
                        broker = ModelBroker(engine, context_id, phase, spec["broker_limits"], spec["model_spec"])
                        runner = run_stage
                    receipt["actual_stage_launches"] += 1
                    result = runner(stage, broker, storage_admission=storage_admission)
                    current[phase] = result
                    if engineering_leaves is None:
                        write_private(private / (context_id + "-" + phase + "-transcript.json"),
                                      canonical_bytes(broker.private_transcript()))
                    write_private(private / (context_id + "-" + phase + "-receipt.json"), canonical_bytes(result))
                    _success(result, stage)
                    current[phase + "_workspace"] = capture_workspace(stage["workspace_root"], spec)
                    if phase == "train":
                        fit = seal_fit_state(stage["output_root"], context_root / "sealed-fit",
                                             spec["freeze_limits"], context_id=context_id,
                                             capsule_sha256=capsule["capsule_sha256"],
                                             training_view_sha256=exported["training_manifest"]["sha256"])
                        current["fit_seal_sha256"] = fit["sha256"]
                    else:
                        verify_fit_seal(fit, spec["freeze_limits"])
                        captured = capture_predictions(Path(stage["output_root"]) / "predictions.json",
                                                       [row["id"] for row in fold_plan.query],
                                                       max_bytes=spec["prediction_max_bytes"])
                        restored = restore_predictions(captured, fold_plan.inverse)
                        current["predictions_sha256"] = digest(restored)
                        current["raw_output_sha256"] = captured.payload_sha256
                        current["captured_alias_output_sha256"] = captured.canonical_sha256
                        write_private(private / (context_id + "-predictions.json"), canonical_bytes(restored))
                        predictions[mode].extend(restored)
                receipt["contexts"].append(current)
                current = None
        require(receipt["actual_stage_launches"] == 128 and len(receipt["contexts"]) == 64,
                "all logical contexts and stages required")
        for mode in MODES:
            require(len(predictions[mode]) == 9984 and len({r["id"] for r in predictions[mode]}) == 9984,
                    "full prediction coverage")
            write_private(private / (mode + "-predictions.json"), canonical_bytes(sorted(predictions[mode], key=lambda r: r["id"])))
        receipt["primary_windows_sha256"] = digest(canonical_receipt["canonical_window_pins"])
        receipt["complete"] = True
        write_private(private / "execution.json", canonical_bytes(receipt))
        return {"root": str(root), "execution": file_pin(private / "execution.json"),
                "targets": file_pin(private / "targets.json"),
                "predictions": {m: file_pin(private / (m + "-predictions.json")) for m in MODES},
                "primary_windows_sha256": receipt["primary_windows_sha256"],
                "reference_export": canonical_receipt,
                "reference_inverse": first_fold.inverse,
                "scientific_qualification": False, "engineering_only": spec["engineering_only"]}
    except BaseException as exc:
        receipt["failed_context"] = current
        receipt["error_type"] = type(exc).__name__
        # Preserve partial outputs and actual terminal uncertainty. No retry,
        # recursive deletion or full-cohort result after a failed stage.
        write_private(private / "failure.json", canonical_bytes(receipt))
        raise
