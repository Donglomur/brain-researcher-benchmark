"""Exact, expiring operator-issued evidence; never a candidate qualification flag.

The trusted deployment provisions distinct HMAC issuer keys outside every worker
mount. This source does not provision keys, read any key automatically, or claim
that the required external authorities/evidence currently exist.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from .io import canonical, ContractError, Artifact


FIELDS = {"schema", "issuer", "kind", "evidence_id", "attempt", "stage",
          "implementation_sha256", "contract_sha256", "prerequisites",
          "issued_at", "expires_at", "content"}
KINDS = {"authorization", "allocation", "implementation_runtime", "completion", "terminal_failure", "completion_candidate", "publication_observation"}


def issue(payload, key):
    """Trusted operator action only; may use invented bytes in reserved controls."""
    if not isinstance(key, bytes) or len(key) < 32:
        raise ContractError("minimum 256-bit separately provisioned issuer key required")
    if not isinstance(payload, dict) or set(payload) != FIELDS or payload["kind"] not in KINDS:
        raise ContractError("exact evidence payload schema required")
    issued, expires = payload["issued_at"], payload["expires_at"]
    if type(issued) is not int or type(expires) is not int or issued >= expires:
        raise ContractError("cannot sign an impossible evidence validity interval")
    return {"payload": payload,
            "hmac_sha256": hmac.new(key, canonical(payload), hashlib.sha256).hexdigest()}


def verify(envelope, *, keys, expected_issuer, kind, evidence_id, attempt, stage,
           implementation_sha256, contract_sha256, prerequisites, now=None):
    if not isinstance(envelope, dict) or set(envelope) != {"payload", "hmac_sha256"}:
        raise ContractError("signed evidence envelope required")
    payload = envelope["payload"]
    if not isinstance(payload, dict) or set(payload) != FIELDS:
        raise ContractError("exact evidence fields required")
    if expected_issuer not in keys:
        raise ContractError("unprovisioned trusted issuer")
    sig = envelope["hmac_sha256"]
    expected = hmac.new(keys[expected_issuer], canonical(payload), hashlib.sha256).hexdigest()
    if not isinstance(sig, str) or not hmac.compare_digest(sig, expected):
        raise ContractError("invalid evidence signature")
    if payload["schema"] != "neural063_evidence_v1":
        raise ContractError("wrong evidence schema")
    expected_fields = {"issuer": expected_issuer, "kind": kind,
                       "evidence_id": evidence_id, "attempt": attempt, "stage": stage,
                       "implementation_sha256": implementation_sha256,
                       "contract_sha256": contract_sha256,
                       "prerequisites": prerequisites}
    if any(payload[k] != v for k, v in expected_fields.items()):
        raise ContractError("evidence scope/source/prerequisite binding mismatch")
    issued, expires = payload["issued_at"], payload["expires_at"]
    if type(issued) is not int or type(expires) is not int or issued >= expires:
        raise ContractError("finite integer evidence validity interval required")
    clock = int(time.time()) if now is None else now
    if not issued <= clock < expires:
        raise ContractError("evidence not currently valid")
    if not isinstance(payload["content"], dict):
        raise ContractError("typed evidence content required")
    return payload["content"]


def authorize(content, *, stage, input_refs, parameters, output_root, attempt_expires_at):
    if set(content) != {"operation", "stage", "inputs", "consent_record",
                       "parameters_sha256", "output_root", "attempt_expires_at"}:
        raise ContractError("exact stage-authorization content required")
    if content["operation"] != "authorized_scientific_stage" or content["stage"] != stage:
        raise ContractError("authentic/scientific stage not explicitly authorized")
    if content["inputs"] != {k: v.object() for k, v in input_refs.items()}:
        raise ContractError("authorization does not bind every exact input")
    if (content["parameters_sha256"] != hashlib.sha256(canonical(parameters)).hexdigest()
            or content["output_root"] != output_root
            or content["attempt_expires_at"] != attempt_expires_at):
        raise ContractError("authorization does not bind exact parameters/output/expiry")
    consent = content["consent_record"]
    if not isinstance(consent, dict) or set(consent) != {"issuer_record_id", "scope"}:
        raise ContractError("external explicit authorization record missing")
    if not all(isinstance(consent[k], str) and consent[k] for k in consent):
        raise ContractError("empty external authorization record")


def allocation(content, *, stage):
    required = {"stage", "read_bytes", "write_bytes", "journal_bytes",
                "wall_seconds", "cpu_core_seconds", "ram_bytes",
                "device_manifest", "permitted_surfaces", "complete_scope"}
    if set(content) != required or content["stage"] != stage:
        raise ContractError("complete exact stage allocation required")
    for key in ("read_bytes", "write_bytes", "journal_bytes", "wall_seconds",
                "cpu_core_seconds", "ram_bytes"):
        if type(content[key]) is not int or content[key] <= 0:
            raise ContractError("finite positive allocation required: " + key)
    if content["journal_bytes"] < 65536 or content["journal_bytes"] >= content["write_bytes"]:
        raise ContractError("separate failure/journal reserve required")
    if content["complete_scope"] != "NEURAL063_original_full_scope_v2":
        raise ContractError("allocation may not prune original task scope")
    if not isinstance(content["device_manifest"], dict) or not isinstance(content["permitted_surfaces"], list):
        raise ContractError("concrete devices and surface allowlist required")
    return content


def runtime_evidence(content, *, read_json, implementation, attempt, stage, parameters, inputs, receipts, limits):
    """Authenticate actual independent probe invocations, exits and measurements.

    The issuer is independently provisioned. Empty JSON observations and a
    caller's passed flag are insufficient. These are future evidence schemas;
    this source construction neither creates nor asserts those observations.
    """
    required = {"implementation_manifest", "environment", "checkpoint",
                "source_review", "isolation_report", "report_generator", "tokenizer", "model_runtime"}
    if set(content) != required or content["implementation_manifest"] != implementation.object():
        raise ContractError("runtime evidence must bind this exact executing implementation")
    for name in required:
        Artifact.parse(content[name])
    from .qualification import qualified_selection
    selection = qualified_selection(content, read_json=read_json, implementation=implementation, attempt=attempt,
                                    stage=stage, parameters=parameters, inputs=inputs, receipts=receipts, limits=limits)
    review = read_json(content["source_review"], roles={"independent_source_review"}, cap=4_000_000)
    if (review.get("schema") != "neural063_independent_source_review_v1" or
            review.get("implementation_sha256") != implementation.sha256 or
            review.get("blocking_findings") != [] or review.get("stages_reviewed") != 28 or
            not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip()):
        raise ContractError("complete independent current-source review absent")
    report = read_json(content["isolation_report"], roles={"independent_isolation_report"}, cap=4_000_000)
    mandatory = {"source_target_sibling_denial", "network_denial", "descriptor_environment_cleanup",
                 "read_only_mounts", "unprivileged_identity", "model_broker_scope",
                 "cpu_ram_gpu_token_tool_limits", "writer_quiescence", "report_prediction_separation"}
    if (report.get("schema") != "neural063_independent_isolation_v1" or
            report.get("attempt") != attempt or report.get("implementation_sha256") != implementation.sha256 or
            set(report.get("checks", {})) != mandatory or
            report.get("environment_sha256") != content["environment"]["sha256"]):
        raise ContractError("all independent actual isolation probes must bind this attempt/source/environment")
    def positive(value): return type(value) is int and value > 0
    def zero(value): return type(value) is int and value == 0
    for name, check in report["checks"].items():
        if not isinstance(check, dict) or set(check) != {"invocation", "exit", "observation"}:
            raise ContractError("actual invocation/exit/observation descriptors required: " + name)
        values = {}
        refs = {field: Artifact.parse(check[field]) for field in check}
        for field, desc in refs.items():
            values[field] = read_json(desc.object(), roles={"independent_runtime_observation"}, cap=4_000_000)
            if (values[field].get("check") != name or values[field].get("attempt") != attempt or
                    values[field].get("environment_sha256") != content["environment"]["sha256"]):
                raise ContractError("independent probe context mismatch")
        invocation, ended, observation = (values[k] for k in ("invocation", "exit", "observation"))
        if (invocation.get("schema") != "neural063_runtime_probe_invocation_v1" or
                not isinstance(invocation.get("command"), list) or not invocation["command"] or
                any(not isinstance(x, str) or not x for x in invocation["command"]) or
                not positive(invocation.get("started_ns"))):
            raise ContractError("actual probe command/start record absent")
        if (ended.get("schema") != "neural063_runtime_probe_exit_v1" or
                ended.get("invocation_sha256") != refs["invocation"].sha256 or
                type(ended.get("exit_code")) is not int or ended["exit_code"] != 0 or
                not positive(ended.get("ended_ns")) or ended["ended_ns"] < invocation["started_ns"]):
            raise ContractError("actual successful independent probe exit absent")
        if (observation.get("schema") != "neural063_runtime_probe_observation_v1" or
                observation.get("invocation_sha256") != refs["invocation"].sha256 or
                observation.get("exit_sha256") != refs["exit"].sha256 or
                not isinstance(observation.get("measured"), dict)):
            raise ContractError("measured probe does not bind actual invocation and exit")
        m = observation["measured"]
        if name == "source_target_sibling_denial":
            surfaces = {"raw_source", "query_targets", "query_binding", "sibling_events", "peer_artifacts"}
            counts = m.get("denied_open_attempts", {})
            ok = set(counts) == surfaces and all(positive(v) for v in counts.values()) and zero(m.get("forbidden_bytes_read"))
        elif name == "network_denial":
            ok = (positive(m.get("ipv4_attempts")) and positive(m.get("ipv6_attempts")) and
                  zero(m.get("successful_connections")))
        elif name == "descriptor_environment_cleanup":
            ok = (m.get("unexpected_fds") == [] and m.get("unexpected_environment_keys") == [] and
                  zero(m.get("inherited_secret_capabilities")) and positive(m.get("inspected_processes")))
        elif name == "read_only_mounts":
            ok = positive(m.get("protected_write_attempts")) and zero(m.get("successful_protected_writes")) and positive(m.get("inspected_mounts"))
        elif name == "unprivileged_identity":
            ok = (positive(m.get("worker_euid")) and positive(m.get("supervisor_euid")) and
                  m["worker_euid"] != m["supervisor_euid"] and m.get("worker_effective_capabilities") == [])
        elif name == "model_broker_scope":
            ok = positive(m.get("unauthorized_model_attempts")) and zero(m.get("successful_unbrokered_calls")) and positive(m.get("accounted_model_calls"))
        elif name == "cpu_ram_gpu_token_tool_limits":
            categories = {"cpu", "ram", "gpu", "tokens", "tools", "reads", "writes", "trusted_descendants"}
            cases = m.get("limit_cases", {})
            ok = set(cases) == categories
            for record in cases.values():
                ok = (ok and isinstance(record, dict) and positive(record.get("attempted_over_limit")) and
                      zero(record.get("accepted_over_limit")) and positive(record.get("observed_enforcement_events")))
        elif name == "writer_quiescence":
            ok = (positive(m.get("terminated_jobs")) and zero(m.get("populated_cgroup_members")) and
                  m.get("active_container_ids") == [] and zero(m.get("open_output_writers")))
            pub=m.get("terminal_publication_cases",{})
            ok=(ok and set(pub)=={"provisional","late_commit","interrupted_commit","replaced_terminal"}
                and m.get("publication_clock_basis")=="qualified_linux_single_link_ctime_ns_realtime"
                and all(isinstance(v,dict) and positive(v.get("attempts")) and zero(v.get("inadmissible_accepted")) for v in pub.values()))
            acknowledgements=m.get("terminal_acknowledgement_cases",{})
            ok=(ok and set(acknowledgements)=={"timely_commit_late_ack","lost_acknowledgement_telemetry","publisher_loss_after_commit"}
                and all(isinstance(v,dict) and positive(v.get("attempts")) and positive(v.get("committed_fact_recovered"))
                        and zero(v.get("contradictory_authority_outcomes")) for v in acknowledgements.values()))
        else:
            ok = (m.get("report_identities_tested") == 8 and positive(m.get("predictor_write_attempts")) and
                  zero(m.get("successful_predictor_writes")) and zero(m.get("report_target_bytes_read")) and
                  zero(m.get("report_sibling_bytes_read")))
        if not ok:
            raise ContractError("required actual denial/limit measurement not established: " + name)
    return {"selection": selection, "isolation_report": content["isolation_report"], "checks": report["checks"]}
