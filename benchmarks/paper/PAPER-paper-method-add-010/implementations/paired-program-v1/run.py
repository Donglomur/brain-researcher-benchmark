"""One frozen two-condition, twenty-phase MEG campaign with private final grading.

Production uses the exact owned Provider. Generated tests have an explicit
private seam and are reported as simulations, never runtime qualification.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import platform
import re
import sys
import time
import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contract
import grading
import transport
from storage import need, encoded, decoded, pin, descriptor, read, write, directory

JSON_CAP = 2 * 1024**2
DELIVERY_SOURCE = Path(__file__).resolve().parent.parent / "delivery-verifier-v1/verify.py"
DELIVERY_SOURCE_PIN = {"bytes": 21300, "sha256": "40469d6b03d9b38d41938b1a0e80caae1f3412b5ac296b02979edf8e02a71ba7"}


class CampaignIO:
    """Logical coordinator accounting, separate from Provider and kernel I/O."""
    def __init__(self, read_limit, write_limit, deadline, clock):
        self.read_limit, self.write_limit = read_limit, write_limit
        self.read_reserved = self.write_reserved = 0
        self.deadline, self.clock = deadline, clock

    def tick(self):
        need(self.clock() < self.deadline, "one original complete campaign deadline")

    def read(self, path, expected, cap):
        self.tick(); descriptor(expected)
        charge = expected["bytes"] + 1
        need(self.read_reserved + charge <= self.read_limit, "coordinator read ceiling")
        self.read_reserved += charge  # interrupted attempts retain their grant
        return read(path, cap, expected)

    def write(self, path, body, cap):
        self.tick()
        need(self.write_reserved + len(body) <= self.write_limit, "coordinator write ceiling")
        self.write_reserved += len(body)
        return write(path, body, cap)


def validate_runtime(value):
    keys = {"schema", "campaign_id", "outcome", "image", "docker_binary", "docker_socket",
            "image_inventory_sha256", "boundary_audit", "role_boundary_verified", "phase_resources",
            "total_seconds", "transport_read_bytes", "transport_write_bytes", "coordinator_read_bytes",
            "coordinator_write_bytes", "paper_pin", "paired_source_manifest", "delivery_read_bytes",
            "delivery_write_bytes", "delivery_seconds"}
    need(type(value) is dict and set(value) == keys and value["schema"] == "meg-runtime-campaign/v1",
         "exact externally selected runtime declaration")
    need(value["outcome"] in ("reproduction", "improvement"), "separate declared paper outcome")
    need(type(value["campaign_id"]) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,40}", value["campaign_id"]),
         "fresh bounded campaign identity")
    need(type(value["image"]) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", value["image"]), "immutable image")
    for key in ("docker_binary", "docker_socket"):
        need(type(value[key]) is str and Path(value[key]).is_absolute(), "absolute selected runtime path")
    need(type(value["image_inventory_sha256"]) is str
         and re.fullmatch(r"[0-9a-f]{64}", value["image_inventory_sha256"]), "reviewed image inventory identity")
    descriptor(value["boundary_audit"])
    descriptor(value["paper_pin"]); descriptor(value["paired_source_manifest"])
    need(value["role_boundary_verified"] is True, "external operator boundary review required")
    for key in ("total_seconds", "transport_read_bytes", "transport_write_bytes", "coordinator_read_bytes", "coordinator_write_bytes",
                "delivery_read_bytes", "delivery_write_bytes", "delivery_seconds"):
        need(type(value[key]) is int and value[key] > 0, "positive complete campaign resource: " + key)
    need(value["delivery_read_bytes"] <= 256 * 1024**2 and value["delivery_write_bytes"] <= 1024**2
         and value["delivery_seconds"] <= 300, "bounded independent delivery grant")
    resources = value["phase_resources"]
    # Existing ABI validation also checks resource key membership and type.
    transport.make_request(value["campaign_id"], "A", 0, value["image"],
        {"bytes": 1, "sha256": "0" * 64}, {"bytes": 1, "sha256": "0" * 64}, resources, 0, value["total_seconds"])
    span = sum(resources[k] for k in ("setup_seconds", "producer_seconds", "capture_seconds", "cleanup_seconds"))
    need(value["total_seconds"] > 20 * span + value["delivery_seconds"],
         "delivery plus full twenty phase allowances and coordinator time")
    need(value["transport_read_bytes"] > 20 * resources["source_read_bytes"]
         and value["transport_write_bytes"] >= 20 * resources["host_write_bytes"],
         "whole Provider allocation includes every phase and extra pinned receipt/result reads")
    return value


def admit_delivery(prepared_root, prepared_pin, runtime, output_root, io_budget, *, generated_author_hashes):
    """Mandatory fresh source-authenticated audit; no gate callback or skip flag."""
    source = io_budget.read(DELIVERY_SOURCE, DELIVERY_SOURCE_PIN, 65536)
    module = types.ModuleType("meg_mandatory_delivery_audit")
    module.__file__ = str(DELIVERY_SOURCE)
    exec(compile(source, str(DELIVERY_SOURCE), "exec"), module.__dict__)
    report_path = directory(output_root / "admission") / "DELIVERY.json"
    returned = module.verify(prepared_root, prepared_pin, runtime["paper_pin"], report_path,
        paired_source_manifest=runtime["paired_source_manifest"], read_limit=runtime["delivery_read_bytes"],
        write_limit=runtime["delivery_write_bytes"], seconds=runtime["delivery_seconds"],
        clock=io_budget.clock, original_deadline=io_budget.deadline,
        _generated_author_hashes=generated_author_hashes)
    io_budget.tick()
    report_pin = pin(encoded(returned))
    retained = decoded(io_budget.read(report_path, report_pin, 65536))
    expected_scope = "generated_delivery_control" if generated_author_hashes is not None else "protected_delivery_structure"
    need(retained == returned and retained["schema"] == "meg-protected-delivery-verification/v1"
         and retained["status"] == "provisional_structural_check" and retained["scope"] == expected_scope
         and retained["prepared"] == prepared_pin and retained["paper"] == runtime["paper_pin"]
         and retained["paired_source_manifest"] == runtime["paired_source_manifest"]
         and retained["original_deadline"] <= io_budget.deadline
         and retained["native_runtime_qualification"] is False and retained["scientific_qualification"] is False,
         "current-invocation returned and retained delivery evidence")
    io_budget.tick()
    return returned, {"source": DELIVERY_SOURCE_PIN, "report": report_pin, "scope": expected_scope,
        "fresh_successful_call_observed": True, "returned_before_original_deadline": True,
        "audit_private_panel_reads": retained["private_panel_reads"],
        "delivery_read_reserved_bytes": retained["read_reserved_bytes"],
        "delivery_write_reserved_bytes": report_pin["bytes"],
        "standalone_report_is_not_admission_authority": True}


def mounts_for(prepared, role, fold):
    need(role in ("A", "B") and type(fold) is int and 0 <= fold < 10, "declared arm/fold")
    mounts = {"/input/WINDOWS.npy": prepared["data"],
        "/input/CONTEXT.json": prepared["contexts"][str(fold)]["mount"],
        "/program": prepared["programmes"][role]["mount"],
        "/paper": prepared["paper"], "/contract": prepared["contract"]}
    if role == "B":
        mounts["/author"] = prepared["author"]
    transport.validate_mounts(role, mounts, prepared["programmes"][role]["source"])
    return mounts


def context_from(io_budget, prepared, fold):
    row = prepared["contexts"][str(fold)]
    mount = row["mount"]
    need(mount["kind"] == "file" and mount["purpose"] == "input"
         and set(mount["files"]) == {"CONTEXT.json"}, "exact context descriptor")
    context = contract.decode_json(io_budget.read(mount["path"], mount["files"]["CONTEXT.json"], JSON_CAP))
    # This structural check does not substitute for the externally pinned
    # PREPARED file; private source joins are checked again only after closure.
    contract._checked_context(context)
    need(context["fold"] == fold and context["context_sha256"] == row["context_sha256"]
         and context["panel_sha256"] == prepared["panel_sha256"], "prepared context identity")
    return context


def execute(prepared_root, prepared_pin, runtime, output_root, *, _generated=False,
            _transport_factory=None, _generated_author_hashes=None, clock=time.monotonic):
    started = clock()
    runtime = validate_runtime(runtime)
    need(type(_generated) is bool and _generated == (_transport_factory is not None)
         and _transport_factory is not transport.OwnedTransport,
         "production cannot inject a participant executor")
    need(_generated_author_hashes is None or (_generated and _transport_factory is not None),
         "fictional author hashes cannot enter production")
    if not _generated:
        need(platform.system() == "Linux", "selected Provider CLI ownership requires the qualified Linux operator")
    deadline = started + runtime["total_seconds"]
    io_budget = CampaignIO(runtime["coordinator_read_bytes"], runtime["coordinator_write_bytes"], deadline, clock)
    prepared_root, root = Path(prepared_root).absolute(), directory(output_root)
    phase_records, outputs = [], {"A": {}, "B": {}}
    target_reads = 0
    delivery_attempted, delivery_admission, transport_construction_attempted = False, None, False
    try:
        delivery_attempted = True
        delivery_report, delivery_admission = admit_delivery(prepared_root, prepared_pin, runtime, root, io_budget,
            generated_author_hashes=_generated_author_hashes)
        prepared = decoded(io_budget.read(prepared_root / "PREPARED.json", prepared_pin, JSON_CAP))
        need(prepared["schema"] == "meg-prepared-paired-campaign/v1"
             and prepared["task_id"] == "PAPER-paper-method-add-010"
             and prepared["rows"] == 376 and prepared["query_rows"] == 188
             and set(prepared["contexts"]) == {str(f) for f in range(10)}
             and set(prepared["programmes"]) == {"A", "B"}, "complete prepared paired cohort")
        need(delivery_report["panel_sha256"] == prepared["panel_sha256"]
             and delivery_report["programmes"] == {r: prepared["programmes"][r]["source"] for r in ("A", "B")},
             "admitted panel and programme identities")
        frozen_pin = pin(encoded(prepared["programmes"]))
        need(decoded(io_budget.read(prepared_root / "PROGRAMMES_FROZEN.json", frozen_pin, 32768))
             == prepared["programmes"], "both complete programme closures frozen before preparation")
        contexts = {fold: context_from(io_budget, prepared, fold) for fold in range(10)}
        need(delivery_report["contexts"] == [contexts[f]["context_sha256"] for f in range(10)],
             "admitted context identities")
        all_queries = [q for fold in range(10) for q in contexts[fold]["queries"]]
        need(len(all_queries) == len(set(all_queries)) == 188
             and all(contexts[f]["windows"] == contexts[0]["windows"] for f in range(10)),
             "exact complete held support and same original windows across folds")
        control = directory(root / "control")
        quarantine = directory(root / "quarantine")
        exposures_root = directory(root / "exposures")
        ownership_root = directory(root / "ownership")
        exposures, approved = {}, {}
        for role in ("A", "B"):
            for fold in range(10):
                mounts = mounts_for(prepared, role, fold)
                exposure = transport.make_exposure(role, runtime["image"], prepared["programmes"][role]["source"],
                    mounts, runtime["image_inventory_sha256"], runtime["boundary_audit"],
                    role_boundary_verified=runtime["role_boundary_verified"])
                path = exposures_root / f"{role}-{fold:02d}.json"
                exposure_pin = io_budget.write(path, encoded(exposure), JSON_CAP)
                exposures[(role, fold)] = exposure_pin
                approved[exposure_pin["sha256"]] = path
        factory = transport.OwnedTransport if _transport_factory is None else _transport_factory
        transport_construction_attempted = True
        owned = factory(campaign_id=runtime["campaign_id"], image=runtime["image"],
            frozen_programs={role: prepared["programmes"][role]["source"] for role in ("A", "B")},
            control_root=control, quarantine_root=quarantine,
            docker_binary=runtime["docker_binary"], docker_socket=runtime["docker_socket"],
            trusted_exposures=approved, source_read_limit=runtime["transport_read_bytes"],
            host_write_limit=runtime["transport_write_bytes"], origin=started, original_deadline=deadline)
        journal_counts = {}
        for fold in range(10):
            for role in ("A", "B"):
                io_budget.tick()
                phase = transport.phase_id(runtime["campaign_id"], role, fold)
                journal_counts[phase] = 0
                def journal(name, value, phase=phase):
                    journal_counts[phase] += 1
                    # Provider already retains its complete journal. Persist
                    # only the externally conveyed ownership identity needed
                    # by a separately admitted parent recovery operation.
                    if name == "OWNERSHIP":
                        io_budget.write(ownership_root / (phase + ".json"), encoded(value), 262144)
                result = owned.execute_fold(role, fold, mounts_for(prepared, role, fold),
                    exposures[(role, fold)], runtime["phase_resources"], deadline, journal)
                io_budget.tick()
                context = context_from(io_budget, prepared, fold)
                response = contract.decode_json(result["result_bytes"])
                contract.validate_prediction(response, context, runtime["outcome"])
                outputs[role][fold] = response
                phase_records.append({key: result[key] for key in ("phase_id", "request_pin", "receipt_pin", "result_pin")})
        closure = owned.complete_for_grading()
        need(len(phase_records) == 20 and all(set(outputs[r]) == set(range(10)) for r in ("A", "B")),
             "all twenty accepted current-invocation phases")
        # The mandatory trusted pre-delivery audit already inspected the private
        # ledger. This separate scoring read occurs only after all twenty public
        # outputs and actual transport closure; no target ledger is a mount.
        private_body = io_budget.read(prepared_root / "PRIVATE_PANEL.json", prepared["private_panel"], JSON_CAP)
        target_reads += 1
        panel = contract.decode_json(private_body)
        need(panel["panel_sha256"] == prepared["panel_sha256"], "exact protected panel")
        result = grading.grade_collections(panel, outputs, runtime["outcome"])
        score_pin = io_budget.write(root / "SCORE.json", encoded(result), JSON_CAP)
        io_budget.tick()
        receipt = {"schema": "meg-closed-paired-campaign/v1", "status": "provisional",
            "completion_requires_external_successful_exit_and_deadline_observation": True,
            "scope": "generated_coordinator_simulation" if _generated else "actual_owned_provider_campaign",
            "campaign_id": runtime["campaign_id"], "outcome": runtime["outcome"],
            "prepared": prepared_pin, "runtime": pin(encoded(runtime)),
            "delivery_admission": delivery_admission,
            "programmes": {r: prepared["programmes"][r]["source"] for r in ("A", "B")},
            "phases": phase_records, "closure": closure, "score": score_pin,
            "windows": 376, "predictions_per_condition": 188, "private_panel_reads": target_reads,
            "private_panel_reads_scope": "post-twenty-phase scoring only; delivery audit recorded separately",
            "journal_counts": journal_counts, "original_deadline": deadline,
            "elapsed_before_final_receipt_seconds": clock() - started,
            "coordinator_read_reserved_bytes": io_budget.read_reserved,
            "coordinator_write_reserved_bytes_before_final_receipt": io_budget.write_reserved,
            "counter_scope": "Explicit coordinator file operations only; Provider, adapter and source/bootstrap reads retain their separately stated scopes. Kernel/library I/O and aggregate CPU/RSS are not measured.",
            "physical_IO_and_aggregate_CPU_RSS_measured": False,
            "scientific_qualification": False, "automatic_retry": False}
        io_budget.write(root / "BATCH.json", encoded(receipt), JSON_CAP)
        io_budget.tick()
        return receipt
    except BaseException as error:
        failure = {"schema": "meg-failed-paired-campaign/v1", "status": "failed",
            "error_type": type(error).__name__, "accepted_phase_count": len(phase_records),
            "private_panel_reads": target_reads, "automatic_retry": False,
            "private_panel_reads_scope": "post-twenty-phase scoring only",
            "delivery_audit_private_panel_reads": (delivery_admission["audit_private_panel_reads"]
                if delivery_admission else None if delivery_attempted else 0),
            "delivery_admitted": delivery_admission is not None,
            "delivery_read_grant_retained_bytes": runtime["delivery_read_bytes"] if delivery_attempted else 0,
            "delivery_write_grant_retained_bytes": runtime["delivery_write_bytes"] if delivery_attempted else 0,
            "delivery_read_reserved_bytes": (delivery_admission["delivery_read_reserved_bytes"]
                if delivery_admission else None),
            "delivery_write_reserved_bytes": (delivery_admission["delivery_write_reserved_bytes"]
                if delivery_admission else None),
            "transport_construction_attempted": transport_construction_attempted,
            "owned_resource_absence_inferred": False, "partial_artifacts_retained": True,
            "scope": "generated_coordinator_simulation" if _generated else "actual_owned_provider_campaign",
            "coordinator_read_reserved_bytes": io_budget.read_reserved,
            "coordinator_write_reserved_bytes": io_budget.write_reserved}
        # On an exhausted deadline/budget the absence of this file is unknown,
        # never implicit success. Parent/native-supervisor evidence is required.
        try:
            io_budget.write(root / "FAILURE.json", encoded(failure), 32768)
        except BaseException:
            pass
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepared-root", "prepared-pin-json", "runtime", "runtime-sha256", "output-root"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    runtime_body = read(args.runtime, 65536)
    need(pin(runtime_body)["sha256"] == args.runtime_sha256, "externally selected runtime pin")
    result = execute(args.prepared_root, decoded(read(args.prepared_pin_json, 8192)),
                     decoded(runtime_body), args.output_root)
    print(encoded({"status": "returned_before_deadline", "persisted_batch_status": result["status"],
                   "external_supervisor_acceptance_still_required": True, "phases": len(result["phases"]),
                   "scope": result["scope"], "scientific_qualification": False}).decode())


if __name__ == "__main__":
    main()
