"""Frozen local programs over complete, unchanged causal numeric EEG packets.

Operator-only source interface. This is not a filesystem/network sandbox, a
trained reference, an authentic-data run, or a direct-model provider adapter.
"""

import argparse
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time
import types
import uuid

HERE = Path(__file__).resolve().parent
ENTRYPOINT_SHA256 = "d61fadbe44290390b34a33819523183481ec2a75d87e73417f26b6d4850b065d"
MODE = "frozen_numeric_program"
PLAN_SCHEMA = "helsinki-numeric-program-plan-v1"
COLLECTION_SCHEMA = "helsinki-numeric-program-collection-v1"
COMPLETE_SCHEMA = "helsinki-numeric-program-complete-v1"


def _load_shared():
    path = HERE.parent / "raster-run-entrypoint-v1/run.py"
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != ENTRYPOINT_SHA256:
        raise ValueError("shared_entrypoint_changed")
    module = types.ModuleType("_helsinki_numeric_shared")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


shared = _load_shared()
transport, collector, protocol = shared.transport, shared.collector, shared.protocol
RunError, require, digest = shared.RunError, shared.require, shared.digest
PLAN_FIELDS = shared.PLAN_FIELDS
COMPLETE_FIELDS = shared.COMPLETE_FIELDS | {"resource_totals"}
PREREQUISITES = {
    **shared.EXTERNAL_PREREQUISITES,
    "representation": "complete_existing_numeric_causal_packet; not_raster_information_equivalence",
    "program_authorship": "freeze_program_and_train_only_artifacts_before_held_observations; account_authorship_separately",
}


def source_pins():
    return {**shared.source_pins(), "numeric-program-v1/run.py":
            hashlib.sha256(shared.read_bytes(Path(__file__).resolve(), 1048576)).hexdigest()}


def _artifacts(argv, artifacts, instructions_sha256, limit, *, check_files):
    require(type(argv) is list and argv and all(type(x) is str and x and "\x00" not in x for x in argv)
            and Path(argv[0]).is_absolute() and argv.count("{task_instructions}") == 1,
            "frozen_argv_with_one_instruction_placeholder_required")
    require(type(artifacts) is list and artifacts, "participant_artifacts_required")
    paths = set()
    for row in artifacts:
        require(type(row) is dict and set(row) == {"path", "sha256"} and type(row["path"]) is str
                and Path(row["path"]).is_absolute() and row["path"] not in paths, "invalid_artifact")
        shared._sha(row["sha256"]); paths.add(row["path"])
        if check_files:
            require(hashlib.sha256(shared.read_bytes(row["path"], limit)).hexdigest() == row["sha256"],
                    "participant_artifact_changed")
    require(argv[0] in paths and all(not Path(x).is_absolute() or x in paths for x in argv),
            "unbound_absolute_argv_artifact")
    require(hashlib.sha256(shared.read_bytes(HERE / "PARTICIPANT.md", 16384)).hexdigest() ==
            instructions_sha256, "instructions_changed")


def freeze_plan(reference, *, argv, artifacts, limits, max_document_bytes):
    require(type(max_document_bytes) is int and 1 <= max_document_bytes <= 1073741824,
            "invalid_document_limit")
    schedule = collector.freeze_reference(reference)
    prompt = hashlib.sha256(shared.read_bytes(HERE / "PARTICIPANT.md", 16384)).hexdigest()
    argv, artifacts = deepcopy(argv), deepcopy(artifacts)
    _artifacts(argv, artifacts, prompt, max_document_bytes, check_files=True)
    return {"schema": PLAN_SCHEMA, "task_id": "NEURAL-EXP-005", "mode": MODE,
            "reference_sha256": reference.reference_sha256, "schedule_sha256": protocol.digest(schedule),
            "case_count": schedule["case_count"], "instructions_sha256": prompt,
            "argv": argv, "artifacts": artifacts, "limits": transport._limits(limits),
            "max_document_bytes": max_document_bytes, "source_pins": source_pins(),
            "external_prerequisites": dict(PREREQUISITES)}


def admit_plan(reference, plan, expected_sha256, *, check_files):
    value = deepcopy(plan); shared._sha(expected_sha256)
    require(type(value) is dict and set(value) == PLAN_FIELDS and digest(value) == expected_sha256,
            "plan_commitment_or_fields_changed")
    require(value["schema"] == PLAN_SCHEMA and value["task_id"] == "NEURAL-EXP-005" and
            value["mode"] == MODE and value["source_pins"] == source_pins() and
            value["external_prerequisites"] == PREREQUISITES, "wrong_numeric_plan_identity")
    schedule = collector.freeze_reference(reference)
    require(value["reference_sha256"] == reference.reference_sha256 and
            value["schedule_sha256"] == protocol.digest(schedule) and
            type(value["case_count"]) is int and value["case_count"] == schedule["case_count"],
            "prepared_reference_or_schedule_changed")
    limit = value["max_document_bytes"]
    require(type(limit) is int and 1 <= limit <= 1073741824, "invalid_document_limit")
    transport._limits(value["limits"])
    _artifacts(value["argv"], value["artifacts"], value["instructions_sha256"], limit,
               check_files=check_files)
    return value, schedule


class _NumericWire(transport._Wire):
    def send_packet(self, packet):
        # The caller has already snapshotted and admitted this exact full packet
        # with the existing Session's exact fields, native clock and input hash.
        body = shared._bytes(packet) + b"\n"
        require(len(body) <= self.limits["max_response_bytes"], "response_byte_limit")
        require(self.wire_bytes + len(body) <= self.limits["max_wire_bytes"], "wire_byte_limit")
        offset = 0
        while offset < len(body):
            transport._wait(self.proc.stdin.fileno(), write=True, deadline=self.deadline)
            try:
                count = os.write(self.proc.stdin.fileno(), memoryview(body)[offset:])
            except BlockingIOError:
                continue
            except BrokenPipeError:
                raise transport.TransportError("participant_closed_input") from None
            offset += count
        self.wire_bytes += len(body)
        self._record(b"H", body)
        self.events.append({"direction": "host_to_participant", "schema": packet["schema"],
                            "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})


def run_case(owner, packet, *, argv, limits, scratch_root):
    """One complete numeric packet and one final probability, fresh local exec."""
    limits = transport._limits(limits)
    require(type(argv) in (list, tuple) and argv and
            all(type(x) is str and x and "\x00" not in x for x in argv) and
            Path(argv[0]).is_absolute(), "absolute_frozen_argv_required")
    root = Path(scratch_root).resolve(strict=True)
    require(root.is_dir(), "scratch_root_required")
    snapshot = deepcopy(packet)
    session = owner.open_case(snapshot)  # Exact packet fields/hash before any serialization.
    binding = session.act({"action": "describe"})["binding"]
    started = time.monotonic(); deadline = started + limits["wall_seconds"]
    proc = wire = None
    evidence = {"schema": "helsinki-numeric-program-case-v1", "mode": MODE,
                "binding": binding, "launch_id": uuid.uuid4().hex, "limits": limits,
                "argv_sha256": digest(tuple(argv)), "environment_sha256": digest(transport.ENVIRONMENT),
                "fresh_exec": False, "collector_committed": False, "scratch_removed": False}
    try:
        with tempfile.TemporaryDirectory(prefix="helsinki-numeric-", dir=root) as case_dir:
            os.chmod(case_dir, 0o700)
            evidence["empty_cwd_at_launch"] = not any(Path(case_dir).iterdir())
            proc = subprocess.Popen(tuple(argv), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, cwd=case_dir, env=dict(transport.ENVIRONMENT), shell=False,
                close_fds=True, pass_fds=(), start_new_session=True, bufsize=0)
            evidence.update(fresh_exec=True, pid=proc.pid, process_group_id=os.getpgid(proc.pid),
                            session_id=os.getsid(proc.pid))
            try:
                require(evidence["process_group_id"] == proc.pid and evidence["session_id"] == proc.pid,
                        "fresh_owned_session_not_observed")
                for stream in (proc.stdin, proc.stdout): os.set_blocking(stream.fileno(), False)
                wire = _NumericWire(proc, deadline - transport.CLEANUP_RESERVE_SECONDS, limits)
                wire.send_packet(snapshot)
                action = wire.action()
                require(action.get("action") == "answer", "one_numeric_answer_required")
                response = session.act(action)
                wire.send(response, binding)
                wire.finish()
                require(transport._group_state(proc.pid) == "absent", "residual_participant_process_group")
            finally:
                evidence["cleanup"] = transport._cleanup(proc, deadline)
        evidence["scratch_removed"] = not Path(case_dir).exists()
        require(evidence["cleanup"]["leader_reaped"] and evidence["cleanup"]["owned_group_absent"] and
                evidence["scratch_removed"], "cleanup_not_qualified")
        evidence["commit_receipt"] = owner.commit_current()
        evidence.update(status="committed", collector_committed=True)
    except Exception as exc:
        if "cleanup" not in evidence: evidence["cleanup"] = transport._cleanup(proc, deadline)
        if "case_dir" in locals(): evidence["scratch_removed"] = not Path(case_dir).exists()
        evidence.update(status="failed", failure=getattr(exc, "code", type(exc).__name__))
        raise RunError("numeric_case_failed", evidence) from exc
    finally:
        evidence["wall_seconds"] = time.monotonic() - started
        if wire is not None:
            evidence.update(actions=wire.actions, participant_stdout_bytes=wire.stdout_bytes,
                            host_wire_bytes=wire.wire_bytes, wire_sha256=wire.transcript.hexdigest(),
                            wire_events=wire.events)
    return evidence


def collect(reference, packet_stream, plan, expected_plan_sha256, *, scratch_root):
    plan, schedule = admit_plan(reference, plan, expected_plan_sha256, check_files=True)
    owner = collector.Collector(schedule, expected_schedule_sha256=plan["schedule_sha256"])
    argv = [str(HERE / "PARTICIPANT.md") if x == "{task_instructions}" else x for x in plan["argv"]]
    completed, chain = 0, hashlib.sha256()
    totals = {"wall_seconds": 0.0, "participant_stdout_bytes": 0, "host_wire_bytes": 0, "processes": 0}
    try:
        for packet in packet_stream:
            require(completed < plan["case_count"], "extra_packet")
            _artifacts(plan["argv"], plan["artifacts"], plan["instructions_sha256"],
                       plan["max_document_bytes"], check_files=True)
            receipt = run_case(owner, packet, argv=argv, limits=plan["limits"], scratch_root=scratch_root)
            require(receipt["status"] == "committed" and receipt["collector_committed"] is True,
                    "numeric_case_did_not_commit")
            body = shared._bytes(receipt); chain.update(len(body).to_bytes(8, "big") + body)
            for key in ("wall_seconds", "participant_stdout_bytes", "host_wire_bytes"):
                totals[key] += receipt[key]
            totals["processes"] += 1
            completed += 1
        require(completed == plan["case_count"], "missing_packet")
        _artifacts(plan["argv"], plan["artifacts"], plan["instructions_sha256"],
                   plan["max_document_bytes"], check_files=True)
        output = owner.finish()
        # The shared collector is only an ordered binding/answer accumulator.
        # This producer exports a distinct numeric identity, never a raster run.
        output.update(schema=COLLECTION_SCHEMA, mode=MODE)
        seal = {"schema": COMPLETE_SCHEMA, "status": "complete", "task_id": "NEURAL-EXP-005", "mode": MODE,
                "plan_sha256": expected_plan_sha256, "reference_sha256": reference.reference_sha256,
                "schedule_sha256": plan["schedule_sha256"], "case_count": completed,
                "collection_sha256": protocol.digest(output), "case_receipts_sha256": chain.hexdigest(),
                "source_pins": source_pins(), "resource_totals": totals}
        return output, seal
    except Exception as exc:
        failure = {"schema": "helsinki-numeric-program-failure-v1", "mode": MODE, "status": "failed",
                   "plan_sha256": expected_plan_sha256, "committed_cases_before_failure": completed,
                   "failure": getattr(exc, "code", type(exc).__name__), "complete_output_eligible": False,
                   "completed_resource_totals": totals}
        if isinstance(exc, RunError) and exc.receipt is not None:
            failure["last_case"] = exc.receipt
        raise RunError("numeric_collection_failed", failure) from exc


def score(reference, plan, expected_plan_sha256, output, seal, expected_completion_sha256):
    plan, schedule = admit_plan(reference, plan, expected_plan_sha256, check_files=False)
    seal, output = deepcopy(seal), deepcopy(output); shared._sha(expected_completion_sha256)
    require(type(seal) is dict and set(seal) == COMPLETE_FIELDS and
            digest(seal) == expected_completion_sha256, "completion_commitment_or_fields_changed")
    require(seal["schema"] == COMPLETE_SCHEMA and seal["status"] == "complete" and
            seal["task_id"] == "NEURAL-EXP-005" and seal["mode"] == MODE and
            seal["plan_sha256"] == expected_plan_sha256 and seal["reference_sha256"] == reference.reference_sha256 and
            seal["schedule_sha256"] == plan["schedule_sha256"] and type(seal["case_count"]) is int and
            seal["case_count"] == plan["case_count"] and seal["source_pins"] == source_pins(),
            "numeric_completion_identity_mismatch")
    shared._sha(seal["case_receipts_sha256"])
    totals = seal["resource_totals"]
    require(type(totals) is dict and set(totals) == {
                "wall_seconds", "participant_stdout_bytes", "host_wire_bytes", "processes"} and
            type(totals["processes"]) is int and totals["processes"] == plan["case_count"] and
            all(type(totals[key]) is int and totals[key] >= 0
                for key in ("participant_stdout_bytes", "host_wire_bytes")) and
            type(totals["wall_seconds"]) in (int, float) and
            math.isfinite(totals["wall_seconds"]) and totals["wall_seconds"] >= 0,
            "invalid_numeric_resource_totals")
    require(type(output) is dict and output.get("schema") == COLLECTION_SCHEMA and output.get("mode") == MODE and
            protocol.digest(output) == seal["collection_sha256"], "numeric_collection_identity_mismatch")
    # Reuse the pinned exact complete-row validator only after numeric envelope
    # admission. This local normalized copy is never exported as raster evidence.
    normalized = dict(output, schema=collector.COLLECTION_SCHEMA, mode=collector.MODE)
    rows = collector.admit_collection(schedule, normalized, expected_schedule_sha256=plan["schedule_sha256"],
                                     expected_collection_sha256=protocol.digest(normalized))
    evaluator = shared._load("complete-support-evaluator/evaluate.py", {"protocol": protocol})
    return evaluator.evaluate(reference, rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    for name in ("freeze", "collect", "score"):
        command = sub.add_parser(name)
        for flag in ("reference", "case-key", "output"):
            command.add_argument("--" + flag, type=Path, required=True)
        command.add_argument("--read-limit", type=int, required=True)
        if name == "freeze": command.add_argument("--participant-spec", type=Path, required=True)
        else:
            command.add_argument("--plan", type=Path, required=True)
            command.add_argument("--plan-sha256", required=True)
        if name == "collect":
            command.add_argument("--source-root", type=Path, required=True)
            command.add_argument("--scratch-root", type=Path, required=True)
        if name == "score":
            command.add_argument("--collection", type=Path, required=True)
            command.add_argument("--completion", type=Path, required=True)
            command.add_argument("--completion-sha256", required=True)
    args = parser.parse_args(argv)
    reference = shared._restore(args.reference, args.case_key, args.read_limit)
    if args.operation == "freeze":
        spec = shared.read_json(args.participant_spec, args.read_limit)
        require(type(spec) is dict and set(spec) == {"argv", "artifacts", "limits", "max_document_bytes"},
                "exact_participant_spec_required")
        plan = freeze_plan(reference, **spec)
        shared.write_prepared_new(args.output, plan, args.read_limit)
        print(json.dumps({"status": "numeric_plan_frozen", "plan_sha256": digest(plan)}))
        return 0
    plan = shared.read_json(args.plan, args.read_limit)
    if args.operation == "score":
        require(args.collection.name == "collection.json" and args.completion.name == "COMPLETED.json" and
                args.collection.parent.resolve() == args.completion.parent.resolve() and
                not (args.completion.parent / "FAILED.json").exists(), "ineligible_saved_run_bundle")
        report = score(reference, plan, args.plan_sha256, shared.read_json(args.collection, args.read_limit),
                       shared.read_json(args.completion, args.read_limit), args.completion_sha256)
        shared.write_prepared_new(args.output, report, args.read_limit)
        print(json.dumps({"status": "score_written", "report_sha256": digest(report)}))
        return 0
    plan, _ = admit_plan(reference, plan, args.plan_sha256, check_files=True)
    shared._forbid_private_artifacts(plan, args.reference, args.case_key, args.source_root)
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    try:
        adapter = shared._load("source-admission-v1/source_adapter.py", {"source_loader": shared.loader})
        with adapter.SourceCorpus(args.source_root) as source:
            output, seal = collect(reference, shared.packets(reference, source.read_samples), plan,
                                   args.plan_sha256, scratch_root=args.scratch_root)
        shared.write_prepared_new(args.output / "collection.json", output, plan["max_document_bytes"])
        shared.write_prepared_new(args.output / "COMPLETED.json", seal, plan["max_document_bytes"])
        print(json.dumps({"status": "numeric_collection_complete", "completion_sha256": digest(seal)}))
        return 0
    except Exception as exc:
        (args.output / "COMPLETED.json").unlink(missing_ok=True)
        failure = exc.receipt if isinstance(exc, RunError) and exc.receipt else {
            "schema": "helsinki-numeric-program-failure-v1", "status": "failed", "mode": MODE,
            "failure": type(exc).__name__, "complete_output_eligible": False}
        shared.write_prepared_new(args.output / "FAILED.json", failure, 65536)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
