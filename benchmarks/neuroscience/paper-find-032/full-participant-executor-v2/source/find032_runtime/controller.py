"""Actual paired whole-study producer and target-free output capture controller."""
import hashlib
import os
from pathlib import Path
import time

from find032.core import Budget, Custody, Refusal, encode_json, write_exact
from find032.full_outputs import inspect_result, validate_metadata
from .resource_channel import Client
from .staging import ARMS, Stage, candidate_contract, strict, validate_config, need
from .lifecycle import ArmFailure, run_arm
from .attach_evidence import AttachEvidence
from .failure_evidence import describe_original_errors


ORIGINALS = []


class Receipt:
    """One precharged terminal metadata write, independent of poisoned work."""
    def __init__(self, budget, extent, deadline):
        self.budget, self.extent, self.deadline = budget, extent, deadline
        self.write_token = budget.reserve("write", extent)
        self.file_token = budget.reserve("files", 1)
        self.attempted = False

    def publish(self, root, value, custody):
        need(not self.attempted, "terminal receipt once")
        self.attempted = True
        raw = encode_json(value)
        need(len(raw) <= self.extent, "precharged terminal receipt bound")
        fd = None
        done = 0
        pending = False
        try:
            need(time.monotonic() < self.deadline, "original terminal receipt cutoff")
            fd = os.open("PARTICIPANT_EXECUTION.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         os.O_NOFOLLOW | os.O_CLOEXEC, 0o400, dir_fd=root)
            self.budget.observed(self.file_token, 1)
            while done < len(raw):
                need(time.monotonic() < self.deadline, "same terminal receipt cutoff")
                pending = True
                count = os.write(fd, memoryview(raw)[done:done + 65536])
                need(0 < count <= min(65536, len(raw) - done), "terminal receipt write progress")
                done += count
                pending = False
            pending = True
            os.fsync(fd)
            pending = False
            need(time.monotonic() < self.deadline, "terminal receipt complete before cutoff")
            self.budget.observed(self.write_token, done)
        except BaseException as error:
            custody.catch("terminal receipt", error)
            ORIGINALS.append((error, raw, done, pending))
        finally:
            if fd is not None:
                custody.close("terminal receipt descriptor", lambda: os.close(fd))


def retain_stdio(stage, arm, session, budget, custody):
    carrier = session.original_stdio
    need(type(carrier) is dict and "rawstdout" in carrier and "rawstderr" in carrier,
         "actual original attach streams required")
    ORIGINALS.append(carrier)
    result = {}
    for name, field in (("stdout", "rawstdout"), ("stderr", "rawstderr")):
        raw = bytes(carrier[field])
        result[name] = write_exact(stage.root, arm + "_" + name + ".bin", raw, budget, custody)
    return result


def capture_outputs(session, cfg, output_fd, budget, custody):
    """No reference root, neural decoder or scientific scorer is reachable here."""
    inventory = session.inventory()
    need(type(inventory) is list, "actual finite holder inventory")
    by_name = {}
    for row in inventory:
        need(type(row) is dict and set(row) == {"name", "bytes", "sha256"} and
             row["name"] not in by_name, "unique complete output inventory")
        by_name[row["name"]] = row
    need("RESULT_MANIFEST.json" in by_name, "whole-programme result manifest")
    result_pin = by_name["RESULT_MANIFEST.json"]
    need(result_pin["bytes"] <= cfg["docker"]["metadata_bytes"], "preselected result metadata extent")
    result_raw = session.read_member(result_pin)
    plan = inspect_result(result_raw, result_pin, member_bytes=cfg["docker"]["member_bytes"],
                          total_bytes=cfg["docker"]["volume_bytes"])
    metadata = {"RESULT_MANIFEST.json": result_raw}
    for request in plan["metadata_requests"]:
        need(request["name"] in by_name and by_name[request["name"]] == request and
             request["bytes"] <= cfg["docker"]["metadata_bytes"], "exact bounded metadata inventory join")
        metadata[request["name"]] = session.read_member(request)
    need("GROUP_INDEX.json" in metadata, "complete group index")
    coverage = {name: raw for name, raw in metadata.items() if name.startswith("coverage_")}
    admitted = validate_metadata(result_raw, result_pin, metadata["GROUP_INDEX.json"], coverage,
                                 member_bytes=cfg["docker"]["member_bytes"],
                                 total_bytes=cfg["docker"]["volume_bytes"], actual_names=tuple(by_name))
    need(admitted["fixed_seed"] == cfg["fixed_seed"], "original prospectively fixed scientific seed")
    captured = []
    for name, raw in metadata.items():
        expected = by_name[name]
        need(len(raw) == expected["bytes"] and hashlib.sha256(raw).hexdigest() == expected["sha256"],
             "actual complete metadata bytes")
        captured.append(write_exact(output_fd, name, raw, budget, custody))
    for request in admitted["capture_requests"]:
        expected = {k: request[k] for k in ("name", "bytes", "sha256")}
        need(expected["name"] in by_name and expected == by_name[expected["name"]],
             "exact full scientific payload inventory join")
        raw = session.read_member(expected)
        captured.append(write_exact(output_fd, expected["name"], raw, budget, custody))
    need({row["name"] for row in captured} == set(by_name) and len(captured) == len(by_name),
         "every exact full-scope output captured once")
    return {"files": captured, "result_manifest": result_pin, "fixed_seed": admitted["fixed_seed"],
            "scientific_payload_decoding": False, "complete_metadata_admission": admitted,
            "reference_opened": False, "scientific_qualification": False}


def private_metadata(stage, name, value, cap, budget, custody):
    raw = encode_json(value)
    need(len(raw) <= cap, "preselected full metadata publication extent")
    return write_exact(stage.root, name, raw, budget, custody)


def run(config_raw, ownership_fd, normal_end, cleanup_end, *, source_pins, holder_source):
    cfg = validate_config(strict(config_raw))
    need(type(holder_source) is bytes and len(holder_source) == source_pins["find032_runtime/holder.py"]["bytes"] and
         hashlib.sha256(holder_source).hexdigest() == source_pins["find032_runtime/holder.py"]["sha256"],
         "holder is the exact already captured authenticated source")
    need(time.monotonic() < normal_end < cleanup_end, "same original paired deadlines")
    custody = Custody()
    cleanup_custody = Custody(custody)
    evidence_custody = Custody(custody)
    work_end = normal_end - cfg["limits"]["receipt_seconds"]
    need(time.monotonic() < work_end < normal_end, "receipt reserve lies inside original normal interval")
    budget = Budget(**cfg["limits"]["normal"], deadline=work_end, custody=custody)
    cleanup_budget = Budget(**cfg["limits"]["cleanup"], deadline=cleanup_end, custody=cleanup_custody)
    evidence_budget = Budget(**cfg["limits"]["evidence"], deadline=normal_end, custody=evidence_custody)
    receipt = Receipt(budget, cfg["limits"]["receipt_bytes"], normal_end)
    evidence = {arm: AttachEvidence(arm, evidence_budget, cfg["limits"]["attach_evidence_bytes"],
                                   cfg["docker"]["stdio_bytes"], normal_end) for arm in ARMS}
    ORIGINALS.append(evidence)
    stage = channel = None
    arms = {}
    first = None
    try:
        channel = Client(ownership_fd, normal_end)
        stage = Stage(cfg, budget, custody, holder_source=holder_source)
        for arm in ARMS:
            evidence[arm].bind(stage.work)
        commitment = {"schema": "FIND032_ORIGINAL_PAIRED_COMMITMENT_V1",
                      "profile": cfg["profile"], "endpoint": cfg["endpoint"], "fixed_seed": cfg["fixed_seed"],
                      "programs": cfg["programs"], "input_manifest": cfg["input_manifest"],
                      "same_native_selection": cfg["docker"], "sources": source_pins,
                      "copy_buffer_lower_bound": stage.copy_buffer_lower_bound,
                      "scientific_qualification": False}
        write_exact(stage.root, "COMMITMENT.json", encode_json(commitment), budget, custody)
        contract = candidate_contract(cfg)
        channel.programme([[arm] for arm in ARMS])
        for index, arm in enumerate(ARMS):
            budget.checkpoint()
            channel.begin(index, [arm])
            stage_root, output_fd, view = stage.arm(arm, contract)
            session = None
            try:
                session = run_arm(cfg["docker"], arm, channel, budget, custody, stage_root,
                                  stage_root / "captured", work_end, cleanup_end,
                                  cleanup_budget=cleanup_budget, attach_receipt=evidence[arm])
                ORIGINALS.append(session)
                streams = retain_stdio(stage, arm, session, budget, custody)
                outputs = capture_outputs(session, cfg, output_fd, budget, custody)
                captured = private_metadata(stage, arm + "_CAPTURE.json", outputs,
                                             cfg["docker"]["metadata_bytes"], budget, custody)
                arms[arm] = {"view": view, "streams": streams,
                             "outputs": {"record": captured, "capture_root": str(stage_root / "captured"),
                                         "files": len(outputs["files"]), "result_manifest": outputs["result_manifest"]}}
            except ArmFailure as error:
                session = error.session
                ORIGINALS.append((error, session))
                if custody.first is None:
                    custody.catch("original arm failure", error)
                raise
            except BaseException as error:
                if custody.first is None:
                    custody.catch("original arm capture", error)
                raise
            finally:
                if session is not None:
                    try:
                        session.close()
                    except BaseException as error:
                        cleanup_custody.catch("independent original arm retirement", error)
                    if arm in arms:
                        try:
                            arms[arm]["native"] = private_metadata(stage, arm + "_NATIVE.json", session.report(),
                                cfg["docker"]["metadata_bytes"], budget, custody)
                        except BaseException as error:
                            if custody.first is None:
                                custody.catch("arm terminal metadata", error)
            custody.raise_first()
            channel.finish()
        need(tuple(arms) == ARMS, "both complete captured programmes before target access")
    except BaseException as error:
        first = error
        ORIGINALS.append(error)
        if custody.first is None:
            custody.catch("paired controller", error)
    finally:
        if channel is not None:
            custody.close("original ownership channel", channel.close)
        if stage is not None and hasattr(stage, "root"):
            try:
                value = {"schema": "FIND032_PARTICIPANT_EXECUTION_V1",
                         "status": "failed" if custody.first is not None or cleanup_custody.first is not None else
                                   "both_complete_captures_pending_original_parent_exit",
                         "profile": cfg["profile"], "endpoint": cfg["endpoint"], "fixed_seed": cfg["fixed_seed"],
                         "arms": arms, "normal_before_receipt": budget.report(), "cleanup": cleanup_budget.report(),
                         "attach_evidence": {arm: evidence[arm].report() for arm in ARMS},
                         "evidence_accounting": evidence_budget.report(),
                         "original_work_endpoint": work_end, "original_receipt_endpoint": normal_end,
                         "failure_evidence": describe_original_errors([event.raw for event in custody.events[:8]]),
                         "further_error_occurrences": max(0, len(custody.events) - 8),
                         "reference_opened": False, "scientific_qualification": False,
                         "native_qualification": False, "automatic_retry": False}
                receipt.publish(stage.root, value, custody)
            except BaseException as error:
                custody.catch("terminal receipt admission", error)
                ORIGINALS.append(error)
        if stage is not None:
            stage.close()
    custody.raise_first()
    need(first is None and time.monotonic() < normal_end, "original complete controller return")
    return 0
