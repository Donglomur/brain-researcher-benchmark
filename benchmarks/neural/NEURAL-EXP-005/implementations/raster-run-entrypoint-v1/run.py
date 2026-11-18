"""Operator-only Reference preparation, frozen-plan, collection and grading entrypoints.

Source construction only. Authentic preparation execution, participant deployment
and scientific/resource admission remain external; no approval issuer is created.
"""

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types

HERE = Path(__file__).resolve().parent
PINS = {
    "source-admission-v1/source_loader.py": "9cbd14214b6dfe0513935ca8ffd51ad08b12e8d3bf55cf8e9845c94f4733458e",
    "source-admission-v1/source_adapter.py": "34a850b2bdb97b0af71bd759a88a19e9552cce852958af58474746b3e56a6c58",
    "raster-process-transport-v1/transport.py": "fb441093c66d6185e0d977849c98c148ce9f2615395fac68f35c42ee3118dee6",
    "complete-support-evaluator/evaluate.py": "5483d60244db66a82249ba8dcc2e87e01a6d758595ae5c273811d494f352bcdc",
}
# These implementation dependencies belong only to owner preparation. They do
# not enter the existing packet/Reference/representation or collection-plan pins.
PREPARATION_PINS = {
    "source-admission-v1/coordinate.py": "17b2864f7be51e5a3f6d93d5902f48bb69d28879c839edfe0ee28ec8d10a44f5",
    "source-admission-v1/rolling_reference.py": "b17a9a2aecb69290bb678d12f67f4d2c4ace34e35cabb9442621c6bc4e89f982",
}
PLAN_SCHEMA = "helsinki-raster-run-plan-v1"
COMPLETE_SCHEMA = "helsinki-raster-run-complete-v1"
PLAN_FIELDS = {"schema", "task_id", "mode", "reference_sha256", "schedule_sha256",
    "case_count", "instructions_sha256", "argv", "artifacts", "limits", "max_document_bytes", "source_pins",
    "external_prerequisites"}
EXTERNAL_PREREQUISITES = {
    "prepared_reference_and_schedule": "external_protected_preparation_required",
    "authentic_EEG": "external_complete_source_custody_alignment_and_calibration_required",
    "participant_or_provider": "external_identity_immutable_deployment_fresh_context_and_containment_required",
    "validation_scope": "generated_controls_do_not_satisfy_authentic_or_scientific_admission",
}
COMPLETE_FIELDS = {"schema", "status", "task_id", "mode", "plan_sha256", "reference_sha256",
    "schedule_sha256", "case_count", "collection_sha256", "case_receipts_sha256", "source_pins"}


class RunError(ValueError):
    def __init__(self, code, receipt=None):
        super().__init__(code)
        self.code, self.receipt = code, receipt


def require(condition, code):
    if not condition:
        raise RunError(code)


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def digest(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _sha(value):
    require(type(value) is str and len(value) == 64 and
            all(c in "0123456789abcdef" for c in value), "invalid_sha256")


def read_bytes(path, limit):
    require(type(limit) is int and 0 < limit <= 1073741824, "invalid_document_limit")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit,
                "ordinary_bounded_file_required")
        body = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) and
                len(body) == before.st_size <= limit, "file_changed_or_exceeded_limit")
    return body


def read_json(path, limit):
    def pairs(rows):
        result = {}
        for k, v in rows:
            require(k not in result, "duplicate_json_key")
            result[k] = v
        return result
    def constant(_):
        raise RunError("nonfinite_json")
    return json.loads(read_bytes(path, limit), object_pairs_hook=pairs, parse_constant=constant)


def write_new(path, document, limit):
    body = _bytes(document) + b"\n"
    require(len(body) <= limit, "output_byte_limit")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())


def _loader():
    path = HERE.parent / "source-admission-v1/source_loader.py"
    body = read_bytes(path, 1048576)
    require(hashlib.sha256(body).hexdigest() == PINS["source-admission-v1/source_loader.py"],
            "source_loader_changed")
    module = types.ModuleType("_helsinki_run_source_loader")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


loader = _loader()


def _load(relative, imports=None):
    path = HERE.parent / relative
    body = loader.read_pinned(path, PINS[relative] if relative in PINS else PREPARATION_PINS[relative])
    return loader._module(path, body, "_helsinki_run", imports or {})


transport = _load("raster-process-transport-v1/transport.py")
collector = transport.collector
protocol = collector.protocol


def source_pins():
    return {**PINS, "raster-collection-v1/collector.py": transport.COLLECTOR_SHA256,
        "typed-raster-viewer-v1/viewer.py": collector.VIEWER_SHA256,
        "complete-support-evaluator/protocol.py": collector.viewer.PROTOCOL_SHA256,
        "raster-run-entrypoint-v1/run.py": hashlib.sha256(read_bytes(Path(__file__).resolve(), 1048576)).hexdigest()}


def _artifact_rows(argv, artifacts, instructions_sha256, byte_limit, *, check_files):
    require(type(argv) is list and argv and all(type(x) is str and x and "\x00" not in x for x in argv)
            and Path(argv[0]).is_absolute() and argv.count("{task_instructions}") == 1,
            "frozen_argv_with_one_instruction_placeholder_required")
    require(type(artifacts) is list and artifacts, "participant_artifacts_required")
    paths = set()
    for row in artifacts:
        require(type(row) is dict and set(row) == {"path", "sha256"} and type(row["path"]) is str
                and Path(row["path"]).is_absolute() and row["path"] not in paths, "invalid_artifact")
        _sha(row["sha256"]); paths.add(row["path"])
        if check_files:
            require(hashlib.sha256(read_bytes(row["path"], byte_limit)).hexdigest() == row["sha256"],
                    "participant_artifact_changed")
    require(argv[0] in paths, "executable_artifact_required")
    require(all(not Path(x).is_absolute() or x in paths for x in argv), "unbound_absolute_argv_artifact")
    prompt = read_bytes(HERE / "PARTICIPANT.md", 16384)
    require(hashlib.sha256(prompt).hexdigest() == instructions_sha256, "instructions_changed")


def freeze_plan(reference, *, argv, artifacts, limits, max_document_bytes):
    """Freeze already prepared reference and operator-selected execution inputs."""
    require(type(max_document_bytes) is int and 1 <= max_document_bytes <= 1073741824,
            "invalid_document_limit")
    schedule = collector.freeze_reference(reference)
    prompt_sha = hashlib.sha256(read_bytes(HERE / "PARTICIPANT.md", 16384)).hexdigest()
    argv, artifacts = deepcopy(argv), deepcopy(artifacts)
    _artifact_rows(argv, artifacts, prompt_sha, max_document_bytes, check_files=True)
    return {"schema": PLAN_SCHEMA, "task_id": "NEURAL-EXP-005", "mode": collector.MODE,
        "reference_sha256": reference.reference_sha256, "schedule_sha256": protocol.digest(schedule),
        "case_count": schedule["case_count"], "instructions_sha256": prompt_sha,
        "argv": argv, "artifacts": artifacts, "limits": transport._limits(limits),
        "max_document_bytes": max_document_bytes, "source_pins": source_pins(),
        "external_prerequisites": dict(EXTERNAL_PREREQUISITES)}


def admit_plan(reference, plan, expected_plan_sha256, *, check_files):
    value = deepcopy(plan); _sha(expected_plan_sha256)
    require(digest(value) == expected_plan_sha256 and type(value) is dict and set(value) == PLAN_FIELDS,
            "plan_commitment_or_fields_changed")
    require(value["schema"] == PLAN_SCHEMA and value["task_id"] == "NEURAL-EXP-005" and
            value["mode"] == collector.MODE and value["source_pins"] == source_pins() and
            value["external_prerequisites"] == EXTERNAL_PREREQUISITES, "wrong_plan_identity")
    require(value["reference_sha256"] == reference.reference_sha256, "prepared_reference_changed")
    schedule = collector.freeze_reference(reference)
    require(type(value["case_count"]) is int and value["case_count"] == schedule["case_count"] and
            value["schedule_sha256"] == protocol.digest(schedule), "prepared_schedule_changed")
    require(type(value["max_document_bytes"]) is int and 1 <= value["max_document_bytes"] <= 1073741824,
            "invalid_document_limit")
    transport._limits(value["limits"])
    _artifact_rows(value["argv"], value["artifacts"], value["instructions_sha256"],
                   value["max_document_bytes"], check_files=check_files)
    return value, schedule


def packets(reference, read_samples):
    """Original complete private order, lazy packet materialization only."""
    for rid in reference.record_ids():
        record = reference.record(rid)
        seconds = record["sample_count"] * record["sample_rate"]["den"] // record["sample_rate"]["num"]
        for second in range(29, seconds):
            yield protocol.packet(reference, rid, second, read_samples)


def collect(reference, packet_stream, plan, expected_plan_sha256, *, scratch_root):
    """No scorer is imported here. Any failure withholds complete output."""
    plan, schedule = admit_plan(reference, plan, expected_plan_sha256, check_files=True)
    owner = collector.Collector(schedule, expected_schedule_sha256=plan["schedule_sha256"])
    argv = [str(HERE / "PARTICIPANT.md") if x == "{task_instructions}" else x for x in plan["argv"]]
    chain, completed = hashlib.sha256(), 0
    try:
        for packet in packet_stream:
            require(completed < plan["case_count"], "extra_packet")
            _artifact_rows(plan["argv"], plan["artifacts"], plan["instructions_sha256"],
                           plan["max_document_bytes"], check_files=True)
            receipt = transport.run_case(owner, packet, argv=argv, limits=plan["limits"], scratch_root=scratch_root)
            require(receipt["status"] == "committed" and receipt["collector_committed"] is True,
                    "transport_did_not_commit")
            body = _bytes(receipt); chain.update(len(body).to_bytes(8, "big") + body)
            completed += 1
        require(completed == plan["case_count"], "missing_packet")
        _artifact_rows(plan["argv"], plan["artifacts"], plan["instructions_sha256"],
                       plan["max_document_bytes"], check_files=True)
        output = owner.finish()
        seal = {"schema": COMPLETE_SCHEMA, "status": "complete", "task_id": "NEURAL-EXP-005",
            "mode": collector.MODE, "plan_sha256": expected_plan_sha256,
            "reference_sha256": reference.reference_sha256, "schedule_sha256": plan["schedule_sha256"],
            "case_count": completed, "collection_sha256": protocol.digest(output),
            "case_receipts_sha256": chain.hexdigest(), "source_pins": source_pins()}
        return output, seal
    except Exception as exc:
        failure = {"schema": "helsinki-raster-run-failure-v1", "status": "failed",
            "plan_sha256": expected_plan_sha256, "committed_cases_before_failure": completed,
            "failure": exc.code if isinstance(exc, (RunError, transport.TransportError)) else type(exc).__name__,
            "complete_output_eligible": False}
        if isinstance(exc, transport.TransportError) and exc.evidence is not None:
            failure["last_transport_cleanup"] = exc.evidence.get("cleanup")
        raise RunError("collection_failed", failure) from exc


def score(reference, plan, expected_plan_sha256, output, seal, expected_completion_sha256):
    """Separate operator operation after externally protected complete commitment."""
    plan, schedule = admit_plan(reference, plan, expected_plan_sha256, check_files=False)
    seal = deepcopy(seal); _sha(expected_completion_sha256)
    require(digest(seal) == expected_completion_sha256 and type(seal) is dict and set(seal) == COMPLETE_FIELDS,
            "completion_commitment_or_fields_changed")
    require(seal["schema"] == COMPLETE_SCHEMA and seal["status"] == "complete" and
            seal["task_id"] == "NEURAL-EXP-005" and seal["mode"] == collector.MODE and
            seal["plan_sha256"] == expected_plan_sha256 and seal["reference_sha256"] == reference.reference_sha256 and
            seal["schedule_sha256"] == plan["schedule_sha256"] and type(seal["case_count"]) is int and
            seal["case_count"] == plan["case_count"] and seal["source_pins"] == source_pins(),
            "completion_identity_mismatch")
    _sha(seal["case_receipts_sha256"])
    rows = collector.admit_collection(schedule, output, expected_schedule_sha256=plan["schedule_sha256"],
                                     expected_collection_sha256=seal["collection_sha256"])
    evaluator = _load("complete-support-evaluator/evaluate.py", {"protocol": protocol})
    return evaluator.evaluate(reference, rows)


def write_prepared_new(path, document, limit):
    """Private-directory persistence; remove only our failed created inode.

    This identity check avoids deleting a preexisting or already replaced path.
    It is not a hostile-filesystem isolation or atomic-rename guarantee.
    """
    body = _bytes(document) + b"\n"
    require(len(body) <= limit, "output_byte_limit")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    owned = os.fstat(fd)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            current = os.lstat(path)
            if stat.S_ISREG(current.st_mode) and (current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino):
                os.unlink(path)
        except OSError:
            pass  # Preserve original failure; no successful preparation receipt.
        raise


def _preparation_modules():
    coordinate = _load("source-admission-v1/coordinate.py", {"source_loader": loader})
    adapter = _load("source-admission-v1/source_adapter.py",
                    {"source_loader": loader, "coordinate": coordinate})
    rolling = _load("source-admission-v1/rolling_reference.py")
    return adapter, rolling


def prepare(source_root, policy, case_key, expected_policy_sha256, *, statistics=None):
    """Owner-only full-source preparation; no new public/reference fields.

    This path performs the existing source census and coordinate/policy admission
    before hashing. SourceCorpus and the rolling helper remain immutable. Their
    compatibility checks do not independently confer scientific qualification.
    """
    _sha(expected_policy_sha256)
    require(digest(policy) == expected_policy_sha256, "preparation_policy_changed")
    adapter, rolling = _preparation_modules()
    adapter.load_sources().current._validate_key(case_key)
    with adapter.SourceCorpus(source_root) as corpus:
        census = corpus.private_census()
        description = adapter.current_description(census, policy)
        # Use the corpus's actual dynamically loaded protocol, not the separate
        # collector/viewer module that happens to have the same source bytes.
        return rolling.prepare_reference(corpus.sources.current, description,
            corpus.read_samples, case_key, source_adapter=adapter, statistics=statistics)


def _restore(reference_path, key_path, limit):
    return protocol.Reference(read_json(reference_path, limit), read_bytes(key_path, 4096))


def _forbid_private_artifacts(plan, reference_path, key_path, source_root):
    private = {Path(reference_path).resolve(), Path(key_path).resolve()}
    root = Path(source_root).resolve()
    for artifact in plan["artifacts"]:
        path = Path(artifact["path"]).resolve()
        require(path not in private and path != root and root not in path.parents, "private_input_in_participant_artifacts")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    for name in ("freeze", "collect", "score"):
        command = sub.add_parser(name)
        command.add_argument("--reference", required=True, type=Path)
        command.add_argument("--case-key", required=True, type=Path)
        command.add_argument("--read-limit", type=int, required=True)
        command.add_argument("--output", type=Path, required=True)
        if name == "freeze":
            command.add_argument("--participant-spec", type=Path, required=True)
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
    preparation = sub.add_parser("prepare")
    preparation.add_argument("--source-root", type=Path, required=True)
    preparation.add_argument("--policy", type=Path, required=True)
    preparation.add_argument("--policy-sha256", required=True)
    preparation.add_argument("--case-key", type=Path, required=True)
    preparation.add_argument("--read-limit", type=int, required=True)
    preparation.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.operation == "prepare":
        require(not os.path.lexists(args.output), "preparation_output_already_exists")
        policy = read_json(args.policy, args.read_limit)
        key = read_bytes(args.case_key, 4096)
        statistics = {}
        reference = prepare(args.source_root, policy, key, args.policy_sha256, statistics=statistics)
        write_prepared_new(args.output, reference.document, args.read_limit)
        print(json.dumps({"status": "reference_prepared", "reference_sha256": reference.reference_sha256,
            "policy_sha256": args.policy_sha256, "preparation_path": statistics["path"],
            "implementation_pins": {**PREPARATION_PINS,
                "source-admission-v1/source_adapter.py": PINS["source-admission-v1/source_adapter.py"],
                "source-admission-v1/source_loader.py": PINS["source-admission-v1/source_loader.py"],
                "complete-support-evaluator/protocol.py": loader.CURRENT_PROTOCOL_PIN,
                "raster-run-entrypoint-v1/run.py": hashlib.sha256(read_bytes(Path(__file__).resolve(), 1048576)).hexdigest()},
            "scientific_qualification": False}))
        return 0
    reference = _restore(args.reference, args.case_key, args.read_limit)
    if args.operation == "freeze":
        spec = read_json(args.participant_spec, args.read_limit)
        require(type(spec) is dict and set(spec) == {"argv", "artifacts", "limits", "max_document_bytes"},
                "exact_participant_spec_required")
        plan = freeze_plan(reference, **spec)
        write_new(args.output, plan, args.read_limit)
        print(json.dumps({"status": "plan_frozen", "plan_sha256": digest(plan)}))
        return 0
    plan = read_json(args.plan, args.read_limit)
    if args.operation == "score":
        require(args.collection.name == "collection.json" and args.completion.name == "COMPLETED.json" and
                args.collection.parent.resolve() == args.completion.parent.resolve() and
                not (args.completion.parent / "FAILED.json").exists(), "ineligible_saved_run_bundle")
        report = score(reference, plan, args.plan_sha256,
            read_json(args.collection, args.read_limit), read_json(args.completion, args.read_limit),
            args.completion_sha256)
        write_new(args.output, report, args.read_limit)
        print(json.dumps({"status": "score_written", "report_sha256": digest(report)}))
        return 0
    plan, _ = admit_plan(reference, plan, args.plan_sha256, check_files=True)
    _forbid_private_artifacts(plan, args.reference, args.case_key, args.source_root)
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    try:
        adapter = _load("source-admission-v1/source_adapter.py", {"source_loader": loader})
        with adapter.SourceCorpus(args.source_root) as source:
            output, seal = collect(reference, packets(reference, source.read_samples), plan,
                                   args.plan_sha256, scratch_root=args.scratch_root)
        write_new(args.output / "collection.json", output, plan["max_document_bytes"])
        # A collection file without a protected successful completion seal is ineligible.
        write_new(args.output / "COMPLETED.json", seal, plan["max_document_bytes"])
        return 0
    except Exception as exc:
        # This directory was exclusively created by this invocation. Never leave
        # an apparently successful seal after a caught persistence/lifecycle error.
        completion = args.output / "COMPLETED.json"
        if completion.exists():
            completion.unlink()
        failure = exc.receipt if isinstance(exc, RunError) and exc.receipt else {
            "schema": "helsinki-raster-run-failure-v1", "status": "failed",
            "plan_sha256": args.plan_sha256, "failure": type(exc).__name__, "complete_output_eligible": False}
        write_new(args.output / "FAILED.json", failure, 16384)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
