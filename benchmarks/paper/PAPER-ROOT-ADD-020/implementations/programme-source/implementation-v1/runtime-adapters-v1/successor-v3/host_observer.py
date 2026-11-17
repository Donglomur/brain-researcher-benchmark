"""Qualified primitive accounting of the live host and its owned phase children.

No host natural-zero exit is invented: the orchestrator remains alive while this
observer runs. Final external natural exit is a separate, original-clock gate.
The accounting executable is an externally qualified required capability; this
source executes its exact protocol and derives evidence, never accepts a final
receipt callback. Tests use a RAM command transport and RAM identity seam.
"""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
import hashlib
import os
import re
import secrets
import time

from .process_control import (CommandResult, ClosureEvidence, Qualification, ProcessError,
    ExecutablePin, SubprocessCommandTransport, canonical, digest, hex_digest, natural,
    parse_json, require, safe_text, hash_file)


COUNTERS = ("read_bytes", "write_bytes", "retained_bytes", "live_bytes", "cpu_ns", "memory_peak_bytes")
HOST_SCOPE = "owned_host_tree_excluding_exact_worker_container_cgroups"


def validate_identity(identity):
    require(type(identity) is dict and set(identity) == {"pid", "start_ticks", "boot_id"}, "Exact host process identity required")
    natural(identity["pid"], "host PID"); natural(identity["start_ticks"], "host start ticks")
    require(type(identity["boot_id"]) is str and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", identity["boot_id"]),
            "Kernel boot identity required")
    return identity


def read_host_identity():
    """Concrete Linux identity; never guesses a PID/start pair on another OS."""
    def bounded(path, cap):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            body = os.read(fd, cap + 1); require(len(body) <= cap, "Kernel identity extent exceeded")
            return body.decode("ascii")
        finally:
            os.close(fd)
    pid = os.getpid()
    raw = bounded("/proc/self/stat", 8192)
    split = raw.rfind(")")
    require(split > 0 and raw.split("(", 1)[0].strip() == str(pid), "Host PID identity changed")
    fields = raw[split + 1:].split()
    require(len(fields) >= 20 and fields[19].isdigit(), "Kernel start identity missing")
    return validate_identity({"pid": pid, "start_ticks": int(fields[19]),
                              "boot_id": bounded("/proc/sys/kernel/random/boot_id", 64).strip()})


@dataclass(frozen=True)
class HostQualification:
    process: Qualification
    implementation_digest: str
    programme_digest: str
    accounting_scope_digest: str
    certificate_digest: str
    trace_bytes: int
    phase_limit: int
    child_record_limit: int
    profile: dict

    def manifest(self):
        require(type(self.process) is Qualification, "Pinned process qualification required")
        self.process.manifest()
        for value in (self.implementation_digest, self.programme_digest, self.accounting_scope_digest, self.certificate_digest):
            hex_digest(value)
        for name in ("trace_bytes", "phase_limit", "child_record_limit"):
            natural(getattr(self, name), name)
        require(type(self.profile) is dict and set(self.profile) == set(COUNTERS), "Complete host profile required")
        for value in self.profile.values():
            natural(value, "host profile")
        return {"schema": "paper020_host_accounting_qualification_v1", **asdict(self), "scope": HOST_SCOPE,
                "required_capabilities": ["lossless_host_tree_coverage_from_original_origin", "stable_pid_start_boot_identity",
                    "full_logical_io_including_cached_tmpfs_and_provider_transports", "owned_child_exit_ledger",
                    "immutable_output_digest_observation", "exact_worker_cgroup_partition", "observer_transport_cost_capture",
                    "signed_immutable_accountant_executable_environment"]}


@dataclass(frozen=True)
class HostObservation:
    scope: str
    phase_id: str
    binding_digest: str
    origin_ns: int
    deadline_ns: int
    finished_ns: int
    accounted_through_ns: int | None
    host_identity: dict
    host_alive: bool
    phase_observation_complete: bool
    owned_children_closed: bool
    external_host_natural_exit_required: bool
    artifact_digest: str | None
    output_bundle_digests: dict
    resources: dict
    worker_resources: dict
    primitive_evidence_digest: str | None
    child_ledger_digest: str | None
    worker_closure_digests: dict
    failures: tuple[str, ...]

    def commitment(self):
        return digest(asdict(self))


def worker_commitment(evidence):
    # Custody binding is needed on failure too. It does not admit completion.
    require(type(evidence) is ClosureEvidence and re.fullmatch(r"[0-9a-f]{64}",evidence.container_id),
            "Typed owned worker identity required for accounting")
    return digest({"container_id": evidence.container_id, "nonce": evidence.nonce,
                   "binding_digest": evidence.binding_digest, "origin_ns": evidence.origin_ns,
                   "deadline_ns": evidence.deadline_ns, "finished_ns": evidence.finished_ns,
                   "payload_digest": evidence.payload_digest, "source_digest": evidence.source_digest,
                   "input_digest": evidence.input_digest, "model_digest": evidence.model_digest,
                   "evidence_digests": evidence.evidence_digests,"natural_complete":evidence.natural_complete,
                   "all_descendants_closed":evidence.all_descendants_closed,"exit_code":evidence.exit_code,
                   "failures":list(evidence.failures)})


class HostPhaseObserver:
    @classmethod
    def from_authority(cls, authority):
        """Build only from the independently signed installation's exact entry."""
        value = dict(authority.document["host_accounting"])
        process = dict(value["process"])
        for name in ("docker", "accountant", "guardian", "worker"):
            process[name] = ExecutablePin(**process[name])
        value["process"] = Qualification(**process)
        qualification = HostQualification(**value)
        transport = SubprocessCommandTransport(qualification.process, authority.process_qualification,
                                               clock=authority.clock)
        return cls(qualification, transport, authority.process_qualification, clock=authority.clock)

    def __init__(self, qualification, transport, verify, *, clock=time.monotonic_ns,
                 identity_reader=read_host_identity, file_hasher=hash_file,
                 nonce_factory=lambda: secrets.token_hex(24)):
        require(type(qualification) is HostQualification and callable(verify)
                and verify(qualification.manifest()) is True, "External signed host accounting qualification required")
        self.q, self.transport, self.clock = qualification, transport, clock
        self.identity_reader, self.file_hasher, self.nonce_factory = identity_reader, file_hasher, nonce_factory
        self.identity = validate_identity(identity_reader())
        self.origin = self.deadline = None; self.active = None
        self.records = {}; self.workers = {}; self.failures = []; self.commands = []
        self.last_counters = {k: 0 for k in COUNTERS}
        self.last_accounted = None; self.whole_closed = False
        self.measured_executable_read_bytes = 0
        self.last_observed_response=None

    def _clock(self):
        now = self.clock()
        require(type(now) is int and self.origin <= now < self.deadline, "Original strict host deadline exceeded")
        require(self.identity_reader() == self.identity, "Host PID/start/boot identity changed")
        return now

    def _phase(self, phase):
        phase_id = phase["id"] if type(phase) is dict else phase
        safe_text(phase_id, 512)
        return phase_id

    def _command(self, action, request):
        before = self._clock()
        pin = self.q.process.accountant
        sha, size = self.file_hasher(pin.path, pin.bytes)
        self.measured_executable_read_bytes += size
        require(sha == pin.sha256 and size == pin.bytes, "Host accounting executable changed")
        body = base64.b64encode(canonical(request)).decode()
        require(len(body) <= 120000, "Host accounting request argv bound")
        argv = (pin.path, action, "--request-base64", body)
        result = self.transport.run(argv, origin_ns=self.origin, deadline_ns=self.deadline,
                                    stdout_limit=self.q.trace_bytes, stderr_limit=min(self.q.trace_bytes, 65536))
        require(type(result) is CommandResult, "Typed independent command result required")
        self.commands.append({"action": action, "argv_digest": digest(list(argv)),
            "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(), "stdout_bytes": len(result.stdout),
            "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(), "stderr_bytes": len(result.stderr),
            "started_ns": result.started_ns, "finished_ns": result.finished_ns, "returncode": result.returncode,
            "timed_out": result.timed_out, "interrupted": result.interrupted, "forced": result.forced, "truncated": result.truncated})
        require(len(canonical(self.commands)) <= self.q.trace_bytes, "Whole host command trace bound")
        require(result.argv == argv and type(result.returncode) is int and result.returncode == 0
                and not any((result.timed_out, result.interrupted, result.forced, result.truncated))
                and before <= result.started_ns <= result.finished_ns < self.deadline
                and len(result.stdout) <= self.q.trace_bytes and len(result.stderr) <= min(self.q.trace_bytes, 65536),
                "Host accountant did not naturally complete within original bounds")
        now = self._clock()
        response = parse_json(result.stdout, self.q.trace_bytes)
        require(type(response) is dict and response.get("schema") == "paper020_host_primitive_snapshot_v1"
                and response.get("action") == action and response.get("request_digest") == digest(request), "Host primitive request join failed")
        for key in ("nonce", "host_identity", "origin_ns", "deadline_ns", "accounting_scope_digest"):
            require(response.get(key) == request[key], "Host primitive identity/clock/scope mismatch: " + key)
        require(response.get("scope") == HOST_SCOPE and response.get("host_alive") is True
                and response.get("coverage_complete") is True and response.get("trace_lost") is False,
                "Lossless live-host scope required")
        accounted = response.get("accounted_through_ns")
        require(type(accounted) is int and self.origin <= accounted <= now
                and type(response.get("coverage_started_ns")) is int
                and 0 <= response["coverage_started_ns"] <= self.origin
                and (self.last_accounted is None or accounted >= self.last_accounted), "Original host accounting clock coverage missing")
        snapshot = response.get("counters")
        require(type(snapshot) is dict and set(snapshot) == set(COUNTERS), "Complete primitive host counters required")
        for key, value in snapshot.items():
            natural(value, key, zero=True)
        # Preserve a typed, identity-bound observation BEFORE success/cap gates.
        self.last_observed_response=(response,hashlib.sha256(result.stdout).hexdigest())
        for key,value in snapshot.items():
            if value < self.last_counters[key]:self.failures.append("regressing_host_counter:"+key)
            if value > self.q.profile[key]:self.failures.append("exceeded_host_counter:"+key)
        require(response.get("child_ledger_complete") is True and response.get("unknown_children") == 0
                and type(response.get("unknown_children")) is int, "Complete child ledger required")
        ledger = response.get("children")
        require(type(ledger) is list and len(ledger) <= self.q.child_record_limit, "Bounded child ledger required")
        seen = set()
        for child in ledger:
            require(type(child) is dict and set(child) == {"identity", "owner_nonce", "started_ns", "finished_ns", "exit_code", "natural"},
                    "Exact child lifetime record required")
            validate_identity(child["identity"])
            key = digest(child["identity"])
            allowed_nonces = ([r["nonce"] for r in self.records.values()] + [request["nonce"]]
                              if action == "host-whole-close" else [request["nonce"]])
            require(key not in seen and child["identity"] != self.identity and child["owner_nonce"] in allowed_nonces, "Repeated/unowned child identity")
            seen.add(key)
            if not (type(child["started_ns"]) is int and type(child["finished_ns"]) is int
                    and self.origin <= child["started_ns"] <= child["finished_ns"] <= accounted
                    and type(child["exit_code"]) is int and child["exit_code"] == 0 and child["natural"] is True):
                self.failures.append("child_not_naturally_closed_zero:"+key)
        return response, hashlib.sha256(result.stdout).hexdigest(), result.finished_ns

    def _request(self, phase_id, binding, nonce):
        return {"schema": "paper020_host_account_request_v1", "phase_id": phase_id, "binding_digest": binding,
                "nonce": nonce, "host_identity": self.identity, "origin_ns": self.origin, "deadline_ns": self.deadline,
                "implementation_digest": self.q.implementation_digest, "programme_digest": self.q.programme_digest,
                "accounting_scope_digest": self.q.accounting_scope_digest}

    def start(self, phase, binding, origin, deadline):
        require(not self.failures and self.active is None, "Host observer failed or phase active")
        natural(origin, "original host origin"); natural(deadline, "original host deadline"); hex_digest(binding)
        require(deadline > origin, "Invalid original host duration")
        if self.origin is None:
            self.origin, self.deadline = origin, deadline
        require((origin, deadline) == (self.origin, self.deadline), "Host clock refresh forbidden")
        phase_id = self._phase(phase)
        require(phase_id not in self.records and len(self.records) < self.q.phase_limit, "Duplicate phase or full phase profile exceeded")
        nonce = self.nonce_factory()
        require(type(nonce) is str and re.fullmatch(r"[0-9a-f]{48}", nonce)
                and nonce not in {r["nonce"] for r in self.records.values()}, "Fresh host phase nonce required")
        self.active = {"phase_id": phase_id, "binding": binding, "nonce": nonce,
                       "kind": phase.get("kind") if type(phase) is dict else None}
        self.records[phase_id] = {"nonce": nonce, "open": None, "close": None}
        try:
            request = self._request(phase_id, binding, nonce)
            response, sha, finish = self._command("host-phase-open", request)
            require(response.get("output_seals") == {} and response.get("excluded_workers") == [], "Phase open must precede output seals")
            self.records[phase_id]["open"] = {"sha256": sha, "finished_ns": finish}
            self.active["open_counters"] = dict(response["counters"])
            self.last_accounted = response["accounted_through_ns"]
            # Do not subtract open snapshot: first-phase accounting includes
            # original-origin prelude and later phases include inter-phase costs.
            return {"phase_id": phase_id, "nonce": nonce, "host_identity": self.identity, "opened_ns": finish, "primitive_digest": sha}
        except BaseException as exc:
            self.failures.append("open:" + type(exc).__name__); raise

    def _workers(self, supplied, response):
        self.observed_worker_resources={};self.observed_worker_commitments={}
        expected = {}
        for evidence in supplied:
            commitment = worker_commitment(evidence)
            require((evidence.origin_ns, evidence.deadline_ns) == (self.origin, self.deadline)
                    and evidence.origin_ns <= evidence.finished_ns < self.deadline
                    and evidence.container_id not in expected, "Worker original-clock or duplicate binding failed")
            expected[evidence.container_id] = (evidence, commitment)
        observed = response.get("excluded_workers")
        require(type(observed) is list and len(observed) == len(expected), "Exact worker accounting partition required")
        resources = {}; commitments = {}
        for record in observed:
            require(type(record) is dict and set(record) == {"container_id", "worker_closure_digest", "counter_record_base64"},
                    "Exact sealed worker counter record required")
            cid = record["container_id"]
            require(cid in expected and cid not in resources, "Unexpected/repeated excluded worker")
            evidence, commitment = expected[cid]
            require(record["worker_closure_digest"] == commitment, "Worker closure commitment mismatch")
            raw = base64.b64decode(record["counter_record_base64"], validate=True)
            require(len(raw) <= self.q.trace_bytes,"Excluded worker raw accounting extent exceeded")
            seal_matches=hashlib.sha256(raw).hexdigest()==evidence.evidence_digests.get("counters")
            counters = parse_json(raw, self.q.trace_bytes)
            require(counters.get("container_id") == cid and counters.get("nonce") == evidence.nonce,
                    "Worker accounting partition identity differs")
            resources[cid] = {k: counters[k] for k in ("read_bytes", "write_bytes", "retained_bytes", "live_bytes", "memory_peak_bytes", "cpu_ns")}
            for value in resources[cid].values():
                natural(value, "worker primitive counter", zero=True)
            commitments[cid] = commitment
            self.observed_worker_resources[cid]=dict(resources[cid])
            self.observed_worker_commitments[cid]=commitment
            if not seal_matches:self.failures.append("worker_counter_seal_unjoined:"+cid)
            if not (counters.get("accounting_complete") is True and counters.get("all_tasks_exited") is True
                    and counters.get("trace_lost") is False and counters.get("forced_termination") is False):
                self.failures.append("worker_accounting_incomplete:"+cid)
            if not (evidence.natural_complete and evidence.all_descendants_closed and evidence.exit_code==0 and not evidence.failures):
                self.failures.append("worker_not_naturally_complete:"+cid)
        return resources, commitments

    def _seal(self, action, phase_id, binding, nonce, seals, workers):
        primitive = ledger_digest = None; accounted = None; artifact = seals.get("artifact")
        resources = {k: None for k in COUNTERS}; worker_resources = {}; commitments = {}
        self.last_observed_response=None;self.observed_worker_resources={};self.observed_worker_commitments={}
        try:
            for value in seals.values():
                hex_digest(value)
            request = self._request(phase_id, binding, nonce)
            worker_commits = {e.container_id: worker_commitment(e) for e in workers}
            for e in workers:
                if not (e.natural_complete and e.all_descendants_closed and type(e.exit_code) is int and e.exit_code==0 and not e.failures):
                    self.failures.append("primary_worker_failure:"+e.container_id)
            request.update({"expected_output_seals": seals, "expected_worker_closures": worker_commits})
            if action == "host-whole-close":
                # Full programmes may have thousands of workers. Do not put
                # their entire registry in a single OS argv: the qualified
                # accountant already owns each registered phase. Bind that
                # complete registry by count+digest and independently verify
                # every returned primitive record under the qualified trace cap.
                del request["expected_worker_closures"]
                request["expected_worker_closures_digest"] = digest(worker_commits)
                request["expected_worker_count"] = len(worker_commits)
                phases = {key: r["nonce"] for key, r in self.records.items()}
                request["owned_phases_digest"] = digest(phases)
                request["owned_phase_count"] = len(phases)
            self.last_observed_response=None
            response, primitive, _ = self._command(action, request)
            require(response.get("output_seals") == seals and response.get("unclosed_children") == [],
                    "Actual output seals or owned child closure incomplete")
            snapshot = response["counters"]
            if self.active is not None:
                require(all(snapshot[k] >= self.active["open_counters"][k] for k in COUNTERS), "Counter regressed after phase open")
            resources = {k: (snapshot[k] - self.last_counters[k] if snapshot[k]>=self.last_counters[k] else None)
                         if action != "host-whole-close" and k in ("read_bytes", "write_bytes", "retained_bytes", "cpu_ns")
                         else snapshot[k] for k in COUNTERS}
            if action != "host-whole-close":
                self.last_counters = {k:max(self.last_counters[k],snapshot[k]) for k in COUNTERS}
            accounted = response["accounted_through_ns"]; self.last_accounted = accounted
            ledger_digest = digest(response["children"])
            worker_resources, commitments = self._workers(workers, response)
            self._clock()
        except BaseException as exc:
            self.failures.append("seal:" + type(exc).__name__ + ":" + str(exc)[:192])
            worker_resources=dict(self.observed_worker_resources);commitments=dict(self.observed_worker_commitments)
            observed=getattr(self,"last_observed_response",None)
            if observed is not None:
                response,primitive=observed; snapshot=response["counters"]
                # Preserve known absolute measurements even when a later ledger,
                # output or partition admission fails. Do not refund lifetime I/O.
                resources["observed_cumulative_counters"]=dict(snapshot)
                for k in COUNTERS:
                    if resources[k] is None:
                        resources[k]=(snapshot[k]-self.last_counters[k] if snapshot[k]>=self.last_counters[k] else None) \
                            if action!="host-whole-close" and k in ("read_bytes","write_bytes","retained_bytes","cpu_ns") else snapshot[k]
                if action!="host-whole-close":self.last_counters={k:max(self.last_counters[k],snapshot[k]) for k in COUNTERS}
                accounted=response["accounted_through_ns"]
        observed=getattr(self,"last_observed_response",None)
        if observed is not None:
            # A typed regression is a sticky failure without an exception. Its
            # absolute observation is still known even when no valid delta can
            # be inferred; preserve it without reducing lifetime high-water marks.
            resources["observed_cumulative_counters"]=dict(observed[0]["counters"])
        finished = self.clock()
        if not (type(finished) is int and self.origin <= finished < self.deadline):
            self.failures.append("final_original_host_deadline")
        complete = not self.failures
        resources["observed_accountant_pin_read_bytes"] = self.measured_executable_read_bytes
        resources["retained_host_command_trace_bytes"] = len(canonical(self.commands))
        resources["unobserved_quantities"]=[k for k in COUNTERS if resources[k] is None]
        resources["unobserved_worker_ids"]=sorted({e.container_id for e in workers}-set(worker_resources))
        return HostObservation("live_host_phase_children", phase_id, binding, self.origin, self.deadline, finished,
            accounted, dict(self.identity), True, complete, complete, True, artifact, dict(seals), resources,
            worker_resources, primitive, ledger_digest, commitments, tuple(self.failures))

    def close(self, phase, binding, origin, deadline, expected_artifact_digest, *, worker_evidence=()):
        phase_id = self._phase(phase); hex_digest(binding); hex_digest(expected_artifact_digest)
        require(self.active is not None and self.active["phase_id"] == phase_id and self.active["binding"] == binding,
                "Host phase/binding has no exact open")
        require((origin, deadline) == (self.origin, self.deadline), "Host closure clock refresh forbidden")
        observation = self._seal("host-phase-seal", phase_id, binding, self.active["nonce"],
                                 {"artifact": expected_artifact_digest}, tuple(worker_evidence))
        self.records[phase_id]["close"] = observation; self.active = None
        for evidence in worker_evidence:
            require(evidence.container_id not in self.workers, "Worker reused across host phases")
            self.workers[evidence.container_id] = evidence
        return observation

    def close_all(self, expected_bundle_digests, origin, deadline, binding, *, worker_evidence=None):
        active_id = self.active["phase_id"] if self.active else None
        require(not self.whole_closed and self.records
                and (self.active is None or self.active["kind"] == "independent_full_process_and_resource_closure")
                and all(r["close"] is not None and r["close"].phase_observation_complete
                        for key, r in self.records.items() if key != active_id),
                "Complete host phase closure required")
        require((origin, deadline) == (self.origin, self.deadline), "Whole-host clock refresh forbidden")
        require(type(expected_bundle_digests) is dict and expected_bundle_digests, "Complete output bundle seals required")
        hex_digest(binding)
        for key, value in expected_bundle_digests.items():
            safe_text(key, 256); hex_digest(value)
        workers = tuple(self.workers.values()) if worker_evidence is None else tuple(worker_evidence)
        require({e.container_id for e in workers} == set(self.workers), "Whole-host worker coverage mismatch")
        seals = dict(expected_bundle_digests)
        seals["host_phase_observations_digest"] = digest({k: v["close"].commitment() if v["close"] is not None else v["open"]
                                                        for k, v in self.records.items()})
        nonce = self.nonce_factory()
        require(type(nonce) is str and re.fullmatch(r"[0-9a-f]{48}", nonce)
                and nonce not in {r["nonce"] for r in self.records.values()}, "Fresh whole-host nonce required")
        observation = self._seal("host-whole-close", "whole-host-close", binding, nonce, seals, workers)
        self.whole_closed = True
        return observation


HostObserver = HostPhaseObserver


@dataclass(frozen=True)
class HostTerminalEvidence:
    host_identity: dict
    observer_identity: dict
    origin_ns: int
    deadline_ns: int
    observed_ns: int
    host_finished_ns: int | None
    natural_complete: bool
    all_descendants_closed: bool
    exit_code: int | None
    full_result_digest: str
    resources: dict
    child_ledger_digest: str | None
    primitive_digest: str | None
    failures: tuple[str, ...]


class ExternalHostTerminalObserver:
    """Runs in a distinct qualified process AFTER the exact host terminates.

    It never launches/stops/signals the subject. The accountant must retain
    lossless terminal records by PID+start+boot identity after the PID is reaped.
    Reuse of the integer PID cannot substitute another process's result.
    """
    def __init__(self, qualification, transport, verify, *, complete_profile,
                 clock=time.monotonic_ns, identity_reader=read_host_identity,
                 file_hasher=hash_file, nonce_factory=lambda: secrets.token_hex(24)):
        require(type(qualification) is HostQualification, "Qualified host accounting source required")
        require(type(complete_profile) is dict and set(complete_profile) == set(COUNTERS), "Complete terminal resource profile required")
        for value in complete_profile.values():
            natural(value, "terminal resource bound")
        manifest = {"schema": "paper020_external_host_terminal_qualification_v1",
            "host_accounting_qualification_digest": digest(qualification.manifest()),
            "scope": "complete_subject_host_tree_including_owned_worker_containers",
            "profile": complete_profile, "required_capabilities": ["lossless_terminal_records_after_reap",
                "all_actual_task_exit_statuses", "immutable_complete_result_seal", "distinct_external_observer",
                "original_monotonic_clock_through_terminal_read"]}
        require(callable(verify) and verify(qualification.manifest()) is True and verify(manifest) is True,
                "Separate external terminal observation qualification required")
        self.q, self.transport, self.profile = qualification, transport, dict(complete_profile)
        self.clock, self.identity_reader, self.file_hasher, self.nonce_factory = clock, identity_reader, file_hasher, nonce_factory
        self.observer_identity = validate_identity(identity_reader()); self.used = False

    def observe_terminal(self, host_identity, origin, deadline, expected_result_digest, *, expected_bundle_digests=None):
        require(not self.used, "External terminal observation is single-use")
        self.used = True
        validate_identity(host_identity); natural(origin, "original origin"); natural(deadline, "original deadline")
        require(deadline > origin and host_identity != self.observer_identity, "A live host cannot observe its own natural exit")
        hex_digest(expected_result_digest)
        seals = {"full_result": expected_result_digest}
        if expected_bundle_digests is not None:
            require(type(expected_bundle_digests) is dict and "full_result" not in expected_bundle_digests, "Invalid complete output bundle seals")
            for key, value in expected_bundle_digests.items():
                safe_text(key, 256); hex_digest(value)
            seals.update(expected_bundle_digests)
        resources = {k: None for k in COUNTERS}; failures = []
        primitive = ledger_digest = host_finished = code = None
        def check_clock():
            now = self.clock()
            require(type(now) is int and origin <= now < deadline and self.identity_reader() == self.observer_identity,
                    "External observer identity/original strict clock changed")
            return now
        try:
            before = check_clock(); nonce = self.nonce_factory()
            require(type(nonce) is str and re.fullmatch(r"[0-9a-f]{48}", nonce), "Fresh terminal challenge required")
            request = {"schema": "paper020_host_terminal_request_v1", "nonce": nonce,
                "host_identity": host_identity, "observer_identity": self.observer_identity,
                "origin_ns": origin, "deadline_ns": deadline, "expected_output_seals": seals,
                "accounting_scope_digest": self.q.accounting_scope_digest}
            pin = self.q.process.accountant; sha, size = self.file_hasher(pin.path, pin.bytes)
            require(sha == pin.sha256 and size == pin.bytes, "Terminal accountant executable changed")
            encoded = base64.b64encode(canonical(request)).decode()
            require(len(encoded) <= 120000, "Terminal request argv bound")
            argv = (pin.path, "host-terminal", "--request-base64", encoded)
            result = self.transport.run(argv, origin_ns=origin, deadline_ns=deadline,
                stdout_limit=self.q.trace_bytes, stderr_limit=min(self.q.trace_bytes, 65536))
            require(type(result) is CommandResult and result.argv == argv and type(result.returncode) is int
                and result.returncode == 0 and not any((result.timed_out, result.interrupted, result.forced, result.truncated))
                and before <= result.started_ns <= result.finished_ns < deadline
                and len(result.stdout) <= self.q.trace_bytes and len(result.stderr) <= min(self.q.trace_bytes, 65536),
                "Terminal accountant command lacks natural original-clock closure")
            now = check_clock(); response = parse_json(result.stdout, self.q.trace_bytes)
            require(type(response) is dict and response.get("schema") == "paper020_host_terminal_primitive_v1"
                    and response.get("request_digest") == digest(request), "Terminal request seal differs")
            for key in ("nonce", "host_identity", "observer_identity", "origin_ns", "deadline_ns", "accounting_scope_digest"):
                require(response.get(key) == request[key], "Terminal exact identity/clock join differs")
            require(response.get("scope") == "complete_subject_host_tree_including_owned_worker_containers"
                    and response.get("host_alive") is False and response.get("coverage_complete") is True
                    and response.get("trace_lost") is False and response.get("forced") is False
                    and response.get("cancelled") is False and response.get("timed_out") is False
                    and response.get("output_seals") == seals, "Natural complete terminal scope/result absent")
            terminal = response.get("host_exit")
            require(type(terminal) is dict and set(terminal) == {"identity", "exit_code", "natural", "finished_ns"}
                    and terminal["identity"] == host_identity and type(terminal["exit_code"]) is int
                    and terminal["exit_code"] == 0 and terminal["natural"] is True, "Host did not naturally exit zero")
            host_finished = terminal["finished_ns"]; code = terminal["exit_code"]
            require(type(host_finished) is int and type(response.get("accounted_through_ns")) is int
                    and origin <= host_finished <= response["accounted_through_ns"] <= now
                    and type(response.get("coverage_started_ns")) is int
                    and 0 <= response["coverage_started_ns"] <= origin, "Terminal original-clock coverage absent")
            ledger = response.get("children")
            require(response.get("child_ledger_complete") is True and response.get("unknown_children") == 0
                    and type(response.get("unknown_children")) is int and response.get("unclosed_children") == []
                    and type(ledger) is list and len(ledger) <= self.q.child_record_limit, "Terminal child coverage incomplete")
            seen = set()
            for child in ledger:
                require(type(child) is dict and set(child) == {"identity", "exit_code", "natural", "finished_ns"}, "Exact terminal child record required")
                validate_identity(child["identity"]); identity_digest = digest(child["identity"])
                require(identity_digest not in seen and child["identity"] != host_identity
                        and type(child["exit_code"]) is int and child["exit_code"] == 0 and child["natural"] is True
                        and type(child["finished_ns"]) is int and origin <= child["finished_ns"] <= host_finished,
                        "Any nonzero/forced/late/unclosed descendant prevents terminal success")
                seen.add(identity_digest)
            counters = response.get("counters")
            require(type(counters) is dict and set(counters) == set(COUNTERS), "Complete terminal cumulative counters required")
            for key, value in counters.items():
                natural(value, key, zero=True); require(value <= self.profile[key], "Complete terminal resource cap exceeded")
            resources = dict(counters); ledger_digest = digest(ledger); primitive = hashlib.sha256(result.stdout).hexdigest()
            check_clock()
        except BaseException as exc:
            failures.append(type(exc).__name__ + ":" + str(exc)[:192])
        observed = self.clock()
        if not (type(observed) is int and origin <= observed < deadline):
            failures.append("final_original_terminal_deadline")
        complete = not failures and code == 0
        return HostTerminalEvidence(dict(host_identity), dict(self.observer_identity), origin, deadline, observed,
            host_finished, complete, complete, code, expected_result_digest, resources, ledger_digest, primitive, tuple(failures))
