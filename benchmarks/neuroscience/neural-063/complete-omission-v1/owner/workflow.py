"""Protected, single-invocation orchestration for the exact accepted graph.

There is no automatic execution on import or inspection. Every scientific stage
needs exact external authorization/allocation/runtime evidence. A durable claim
precedes its operational effects, and a completed receipt binds actual outputs.
"""
from __future__ import annotations

import hashlib
import importlib
import os
from pathlib import Path
import time
import traceback

from .contract import load_contract
from .evidence import verify, authorize, allocation, runtime_evidence, issue
from .io import Artifact, ArtifactStore, ByteMeter, ContractError, canonical, capture, decode, ordinary
from .model import StageContext, StageResult
from .deadline import admit as admit_deadline, check as check_deadline, finalize as finalize_deadline


COMPONENT = {**{x: "preparation.stages" for x in ("S00", "S01", "S02", "S03", "S04", "S05", "S06")},
             **{x: "references.stages" for x in ("R00", "R01", "R02", "C00", "R03", "C01", "RC00", "R04", "R05", "R06", "C02")},
             **{x: "runtime.stages" for x in ("D00", "D01", "Q00", "Q01", "Q02", "Q03", "N00")},
             **{x: "owner.stages" for x in ("E00", "E01", "E02")}}
TERMINAL = {"complete", "eligible_for_full_programme", "complete_with_narrative_failures",
            "terminated_before_query_reference_unqualified",
            "terminated_before_query_reference_selection_unavailable", "failed"}
EXTERNAL_INPUT_ROLES = {
    "S00": {"source_roster", "provider_manifest", "source_provenance",
            "experiment_metadata", "roi_metadata"},
    "D00": {"checkpoint", "tokenizer", "model_runtime", "candidate_development_recipe"},
    "N00": {"checkpoint", "tokenizer", "model_runtime", "report_recipe"},
    "E02": {"independent_scientific_review"},
}


def contract_digest(contract):
    return hashlib.sha256(canonical(contract["pins"])).hexdigest()


def verify_implementation(manifest_descriptor, *, meter=None):
    ref = Artifact.parse(manifest_descriptor)
    manifest = decode(capture(ref.path, 4_000_000, descriptor=ref, meter=meter))
    if manifest.get("schema") != "neural063_implementation_source_v1":
        raise ContractError("frozen implementation source manifest required")
    root = ordinary(Path(ref.path).parent, directory=True)
    if root != ordinary(Path(__file__).parent.parent, directory=True):
        raise ContractError("source manifest must freeze the actual executing implementation root")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ContractError("complete implementation closure missing")
    seen = set()
    for entry in files:
        if set(entry) != {"path", "bytes", "sha256"}:
            raise ContractError("exact source member descriptor required")
        rel = Path(entry["path"])
        if rel.is_absolute() or ".." in rel.parts or str(rel) in seen:
            raise ContractError("invalid/duplicate implementation member")
        seen.add(str(rel))
        d = Artifact(str(root / rel), entry["bytes"], entry["sha256"],
                     "implementation_source", "operator", "source_freeze", "application/octet-stream")
        capture(d.path, max(d.bytes, 1), descriptor=d, meter=meter)
    required = {"owner/workflow.py", "owner/io.py", "owner/model.py", "owner/scoring.py",
                "preparation/stages.py", "references/stages.py", "runtime/stages.py", "owner/stages.py"}
    active = {str(p.relative_to(root)) for component in ("owner", "preparation", "references", "runtime", "contract")
              for p in (root / component).glob("*.py")}
    active |= {str(p.relative_to(root)) for p in (root / "contract").glob("*.json")}
    active |= {component + "/INTERFACE.json" for component in ("owner", "preparation", "references", "runtime")}
    active.add("neural063.py")
    if not (required | active) <= seen:
        raise ContractError("complete actual executing modules, contracts and interfaces must be frozen")
    return ref, manifest


def verify_completion(ref, *, keys, issuer, attempt, stage, implementation_sha256,
                      c_digest, expected_prerequisites, output_root, now=None, meter=None):
    from .publication import read_authoritative
    obj = read_authoritative(ref, output_root, stage, meter=meter)
    decision = verify(obj, keys=keys, expected_issuer=issuer, kind="completion",
                     evidence_id="DONE_" + stage, attempt=attempt, stage=stage,
                     implementation_sha256=implementation_sha256,
                     contract_sha256=c_digest, prerequisites=expected_prerequisites,
                     now=now)
    if (set(decision) != {"schema","authority_rule","provisional","outcome","failure","publication_deadline_ns","deadline_disposition","original_attempt_expires_at"} or
            decision["schema"] != "neural063_terminal_publication_v1" or
            decision["authority_rule"] != "qualified_single_link_kernel_commit_v4"):
        raise ContractError("exact authoritative terminal publication required")
    candidate = Artifact.parse(decision["provisional"])
    if (candidate.path != str(Path(output_root)/"journal"/(stage+".candidate.json")) or
            candidate.role != "signed_stage_provisional" or candidate.producer != stage):
        raise ContractError("terminal decision must bind this invocation's exact provisional body")
    provisional = decode(capture(candidate.path,4_000_000,descriptor=candidate,meter=meter))
    content = dict(verify(provisional,keys=keys,expected_issuer=issuer,kind="completion_candidate",
        evidence_id="CANDIDATE_"+stage,attempt=attempt,stage=stage,implementation_sha256=implementation_sha256,
        contract_sha256=c_digest,prerequisites=expected_prerequisites,now=now))
    content.update({k:decision[k] for k in ("outcome","failure","deadline_disposition","original_attempt_expires_at")})
    content["authoritative_terminal_publication"] = ref.object()
    if content.get("outcome") not in TERMINAL or content.get("stage") != stage:
        raise ContractError("malformed actual completion receipt")
    if not isinstance(content.get("artifacts"), dict):
        raise ContractError("completion has no bound output inventory")
    for artifact in content["artifacts"].values():
        desc = Artifact.parse(artifact)
        if desc.producer != stage:
            raise ContractError("completion output has another producer")
        # The trusted producer's signed inventory binds bytes without opening
        # unconsumed targets/models. Actual content is authenticated by its
        # authorized consumer on the same read. In particular, ancestor replay
        # must not open S06 query targets before target-last admission.
    # Optional signed telemetry is a cost observation, not a second authority
    # predicate. Missing, expired or interrupted custody stays explicitly
    # unknown. It cannot change a previously authenticated committed fact.
    observed_path=Path(output_root)/"journal"/(stage+".publication-observation.json")
    try:
        cap=65536 if meter is None else min(65536,max(0,meter.read_limit-meter.read_bytes))
        observed_bytes=capture(observed_path,cap,meter=meter)
        observed=verify(decode(observed_bytes),keys=keys,expected_issuer=issuer,
            kind="publication_observation",evidence_id="OBSERVED_"+stage,attempt=attempt,
            stage=stage,implementation_sha256=implementation_sha256,contract_sha256=c_digest,
            prerequisites=expected_prerequisites,now=now)
        if (observed.get("schema")!="neural063_publication_observation_v4" or
                observed.get("authority_rule")!="qualified_single_link_kernel_commit_v4" or
                observed.get("provisional")!=candidate.object() or
                observed.get("authoritative_terminal")!=ref.object()):
            raise ContractError("publication telemetry scope differs from this exact committed fact")
        observed_ref=Artifact(str(observed_path),len(observed_bytes),hashlib.sha256(observed_bytes).hexdigest(),
            "signed_publication_observation","operator",stage)
        content["publication_observation"]={"status":"authenticated","artifact":observed_ref.object(),"observed":observed}
    except BaseException as exc:
        content["publication_observation"]={"status":"unavailable","reason":type(exc).__name__+": "+str(exc)[:2048],
            "unobserved_costs":None,"committed_authority_changed":False}
    return content


def entry_outcome(eid, requirement, content):
    outcome = content["outcome"]
    if requirement == "eligible_for_full_programme":
        if outcome != "eligible_for_full_programme":
            raise ContractError("reference competence did not admit the full programme")
    elif requirement.startswith("all_8_jobs_terminal_and_writers_closed"):
        if outcome not in ("complete", "complete_with_narrative_failures"):
            raise ContractError("all eight report jobs must reach terminal state")
        # N00's concrete runtime verifier and artifact inventory supply custody;
        # E00 rechecks these bodies before any target opens.
        if "narrative_receipts" not in content["artifacts"]:
            raise ContractError("narrative terminal/custody artifact absent")
    elif outcome != "complete":
        raise ContractError("required predecessor did not complete: " + eid)


def authorize_stage(spec, keys, *, contract=None, now=None):
    """Returns authenticated execution inputs; opens no native/target/model data."""
    preflight_meter = ByteMeter(64_000_000, 0)
    contract = contract or load_contract(meter=preflight_meter)
    required = {"schema", "attempt", "stage", "implementation", "issuers", "evidence",
                "completions", "inputs", "parameters", "output_root", "attempt_expires_at"}
    if set(spec) != required or spec["schema"] != "neural063_stage_request_v1":
        raise ContractError("exact stage request required")
    stage, attempt = spec["stage"], spec["attempt"]
    if stage not in contract["nodes"] or not isinstance(attempt, str) or not attempt:
        raise ContractError("fixed stage and attempt identity required")
    if set(spec["issuers"]) != {"authorization", "allocation", "implementation_runtime", "completion"}:
        raise ContractError("four explicitly provisioned external issuer roles required")
    if len(set(spec["issuers"].values())) != 4:
        raise ContractError("authorization/allocation/runtime/completion issuers must be distinct")
    impl, _ = verify_implementation(spec["implementation"], meter=preflight_meter)
    cdigest = contract_digest(contract)
    node = contract["nodes"][stage]
    expected_ancestors = contract["ancestors"][stage]
    if set(spec["completions"]) != expected_ancestors:
        raise ContractError("exact ancestor receipt roster required")
    receipts, refs = {}, {}
    for ancestor in contract["order"]:
        if ancestor not in expected_ancestors:
            continue
        refs[ancestor] = Artifact.parse(spec["completions"][ancestor])
        bindings = {"DONE_" + d: refs[d].sha256 for d in contract["nodes"][ancestor]["depends_on"]}
        receipts[ancestor] = verify_completion(
            refs[ancestor], keys=keys, issuer=spec["issuers"]["completion"], attempt=attempt,
            stage=ancestor, implementation_sha256=impl.sha256, c_digest=cdigest,
            expected_prerequisites=bindings, output_root=spec["output_root"], now=now, meter=preflight_meter)
    bindings = {"DONE_" + d: refs[d].sha256 for d in node["depends_on"]}
    for eid, condition in node["entry_outcome_requirements"].items():
        entry_outcome(eid, condition, receipts[eid.removeprefix("DONE_")])
    external_ids = [e for e in node["entry_evidence_ids"] if e.startswith("EXT_")]
    if set(spec["evidence"]) != set(external_ids):
        raise ContractError("exact stage external evidence roster required")
    contents = {}
    for eid in external_ids:
        kind = ("authorization" if eid.startswith("EXT_AUTH_") else
                "allocation" if eid.startswith("EXT_ALLOC_") else "implementation_runtime")
        ref = Artifact.parse(spec["evidence"][eid])
        envelope = decode(capture(ref.path, 4_000_000, descriptor=ref, meter=preflight_meter))
        # Runtime qualification is an attempt-bound external root; per-stage
        # authorization/allocation binds exactly the direct completed ancestors.
        eb = bindings if kind != "implementation_runtime" else {}
        estage = stage if kind != "implementation_runtime" else "ALL"
        contents[kind] = verify(envelope, keys=keys, expected_issuer=spec["issuers"][kind],
                                kind=kind, evidence_id=eid, attempt=attempt, stage=estage,
                                implementation_sha256=impl.sha256, contract_sha256=cdigest,
                                prerequisites=eb, now=now)
    inputs = {k: Artifact.parse(v) for k, v in spec["inputs"].items()}
    authorize(contents["authorization"], stage=stage, input_refs=inputs,
              parameters=spec["parameters"], output_root=spec["output_root"],
              attempt_expires_at=spec["attempt_expires_at"])
    for name, ref in inputs.items():
        if ref.producer in contract["nodes"]:
            if ref.producer not in receipts:
                raise ContractError("input comes from own/future/uncompleted stage: " + name)
            if ref.object() not in receipts[ref.producer]["artifacts"].values():
                raise ContractError("input differs from actual signed predecessor output: " + name)
        elif ref.role not in EXTERNAL_INPUT_ROLES.get(stage, set()):
            raise ContractError("external input role is not allowed for this stage: " + name)
    from .constructor import interface_union
    interfaces = interface_union(meter=preflight_meter, contract=contract)
    expected_bindings = interfaces["bindings"][stage]
    if set(inputs) != set(expected_bindings):
        raise ContractError("exact concrete stage input key set required")
    for key, binding in expected_bindings.items():
        ref = inputs[key]
        if ref.role != binding["role"]:
            raise ContractError("input role differs from frozen interface: " + key)
        if binding["producer"] != "external_explicit_input":
            expected = receipts[binding["producer"]]["artifacts"].get(binding["output_key"])
            if ref.object() != expected:
                raise ContractError("input is not the exact principal predecessor output: " + key)
        elif ref.producer in contract["nodes"]:
            raise ContractError("external explicit input cannot masquerade as stage output")
    limits = allocation(contents["allocation"], stage=stage)
    from .containment import profile as containment_profile
    containment_profile(limits)  # pure configuration check; no host operation
    if COMPONENT[stage] == "runtime.stages":
        profile = spec["parameters"].get("runtime_profile", {})
        for key in ("cleanup_read_bytes", "cleanup_write_bytes", "cleanup_wall_seconds"):
            if type(profile.get(key)) is not int or profile[key] <= 0:
                raise ContractError("prospective parent cleanup reserve missing: " + key)
    # Only external proof bodies are read here. No query target/body/model input.
    proof_store = ArtifactStore(ordinary(spec["output_root"], directory=True), preflight_meter)
    qualified = runtime_evidence(contents["implementation_runtime"], read_json=proof_store.read_json, implementation=impl, attempt=attempt,
                                 stage=stage, parameters=spec["parameters"], inputs=inputs, receipts=receipts, limits=limits)
    if preflight_meter.read_bytes >= limits["read_bytes"]:
        raise ContractError("complete preflight plus stage reads exceed allocation")
    expiry = spec["attempt_expires_at"]
    deadline = admit_deadline(expiry, limits["wall_seconds"], wall=now)
    if not isinstance(spec["parameters"], dict):
        raise ContractError("frozen stage parameter object required")
    return {"contract": contract, "implementation": impl, "contract_digest": cdigest,
            "node": node, "receipts": receipts, "bindings": bindings,
            "inputs": inputs, "limits": limits,
            "proof_read_bytes": preflight_meter.read_bytes, "deadline": deadline,
            "qualification": qualified["selection"]}


def run_stage(spec, keys, *, worker_runner):
    """Trusted parent. worker_runner must enforce actual subprocess resources."""
    admitted = authorize_stage(spec, keys)
    root = ordinary(spec["output_root"], directory=True)
    st = root.stat()
    if st.st_uid != os.geteuid() or st.st_mode & 0o077:
        raise ContractError("operator output root must be owned private mode0700")
    limits, stage = admitted["limits"], spec["stage"]
    # Journal subpartitions: context1/8 + logs1/8 + child result1/4 +
    # invocation/completion3/8 <=7/8; remaining1/8 is cleanup/failure margin.
    journal_meter = ByteMeter(1_000_000, limits["journal_bytes"] * 3 // 8)
    journal = ArtifactStore(root, journal_meter)
    journal.mkdir("journal")
    check_deadline(admitted["deadline"])
    claim = journal.json("journal/" + stage + ".claim.json",
                         {"attempt": spec["attempt"], "stage": stage,
                          "request_sha256": hashlib.sha256(canonical(spec)).hexdigest(),
                          "started_ns": time.time_ns(), "pid": os.getpid()},
                         role="stage_invocation_claim", visibility="operator", producer=stage)
    # O_EXCL claim is before all worker effects; an interrupted claim is never
    # automatically deleted, overwritten or converted to successful completion.
    start = time.monotonic()
    failure = None
    result = None
    worker_usage = {}
    cleanup = None
    recovered = None
    try:
        check_deadline(admitted["deadline"])
        result, worker_usage = worker_runner(spec, admitted)
        check_deadline(admitted["deadline"])
        if not isinstance(result, StageResult) or result.outcome not in TERMINAL:
            raise ContractError("component did not return a typed terminal result")
        for artifact in result.artifacts.values():
            if artifact.producer != stage:
                raise ContractError("worker output producer mismatch")
            path = ordinary(artifact.path)
            if root not in path.parents or path.stat().st_size != artifact.bytes:
                raise ContractError("worker output outside private custody or wrong size")
    except BaseException as exc:
        worker_usage = getattr(exc, "usage", worker_usage)
        failure = {"class": type(exc).__name__, "message": str(exc)[:2048],
                   "traceback": traceback.format_exc()[-8192:]}
        result = StageResult("failed", {}, reasons=[failure["class"] + ": " + failure["message"]])
    # Candidate/report backends can outlive a failed trusted worker. The
    # privileged parent always reconciles only this attempt's claimed jobs.
    if COMPONENT[stage] == "runtime.stages":
        try:
            from runtime.custody import cleanup_stage
            cleanup = cleanup_stage(spec, admitted)
        except BaseException as exc:
            prior = failure
            failure = {"class": "RuntimeCleanupFailure", "message": str(exc)[:2048],
                       "prior_failure": prior, "traceback": traceback.format_exc()[-8192:]}
            result = StageResult("failed", result.artifacts, result.measurements,
                                 result.reasons + ["parent runtime job cleanup failed"])
    try:
        from .recovery import retained_outputs
        recovered = retained_outputs(root, stage, spec["attempt"], cap=limits["journal_bytes"] // 8)
        returned = {canonical(a.object()) for a in result.artifacts.values()}
        durable = {canonical(a) for a in recovered["artifacts"].values()}
        if returned - durable or recovered["unbound_paths"]:
            raise ContractError("worker outputs lack complete durable custody; partial outputs retained")
    except BaseException as exc:
        prior = failure
        failure = {"class": "OutputCustodyFailure", "message": str(exc)[:2048],
                   "prior_failure": prior, "traceback": traceback.format_exc()[-8192:]}
        result = StageResult("failed", result.artifacts, result.measurements,
                             result.reasons + ["durable output recovery incomplete"])
    try:
        check_deadline(admitted["deadline"])
    except ContractError as exc:
        failure = {"class": "AttemptDeadlineFailure", "message": str(exc), "prior_failure": failure}
        result = StageResult("failed", result.artifacts, result.measurements, result.reasons + [str(exc)])
    body = {"stage": stage, "claim": claim.object(), **result.object(),
            "admitted_deadline": admitted["deadline"],
            "entry_evidence": spec["evidence"], "input_descriptors": spec["inputs"],
            "parameters_sha256": hashlib.sha256(canonical(spec["parameters"])).hexdigest(),
            "failure": failure, "wall_seconds": time.monotonic() - start,
            "worker_usage": worker_usage, "runtime_parent_cleanup": cleanup,
            "retained_outputs": recovered,
            "proof_read_bytes": admitted["proof_read_bytes"],
            "journal_usage_before_receipt": journal_meter.snapshot(),
            "scientific_qualification": "not_inferred_from_stage_completion"}
    if stage == "E02" and result.outcome == "complete":
        from .resource_report import trusted_closure
        body["complete_trusted_resource_closure"] = trusted_closure(admitted["receipts"], body)
    now = int(time.time())
    payload = {"schema": "neural063_evidence_v1", "issuer": spec["issuers"]["completion"],
               "kind": "completion", "evidence_id": "DONE_" + stage,
               "attempt": spec["attempt"], "stage": stage,
               "implementation_sha256": admitted["implementation"].sha256,
               "contract_sha256": admitted["contract_digest"],
               "prerequisites": admitted["bindings"], "issued_at": now,
               "expires_at": spec["attempt_expires_at"], "content": body}
    # The large durable body is provisional and cannot satisfy DONE, even if
    # its write/flush crosses a deadline or its descriptor is copied elsewhere.
    candidate_payload=dict(payload,kind="completion_candidate",evidence_id="CANDIDATE_"+stage,
                           expires_at=max(spec["attempt_expires_at"],now+86400))
    provisional_started=time.monotonic()
    provisional=journal.json("journal/"+stage+".candidate.json",
        issue(candidate_payload,keys[spec["issuers"]["completion"]]),
        role="signed_stage_provisional",visibility="operator",producer=stage)
    provisional_write_seconds=time.monotonic()-provisional_started
    def terminal_decision():
        final=finalize_deadline(payload,admitted["deadline"])
        resolved=final["content"]
        terminal_wall=admitted["deadline"]["admitted_wall"] + (admitted["deadline"]["terminal_deadline"]-admitted["deadline"]["admitted_monotonic"])
        final["content"]={"schema":"neural063_terminal_publication_v1",
            "authority_rule":"qualified_single_link_kernel_commit_v4", "provisional":provisional.object(),
            "outcome":resolved["outcome"],"failure":resolved["failure"],
            "publication_deadline_ns":int(min(terminal_wall,spec["attempt_expires_at"])*1_000_000_000),
            "deadline_disposition":resolved.get("deadline_disposition"),
            "original_attempt_expires_at":spec["attempt_expires_at"]}
        return final
    from .publication import publish, final_path
    receipt,final,observation=publish(journal,stage,admitted["deadline"],terminal_decision,keys[spec["issuers"]["completion"]])
    # This record is telemetry, never a second terminal outcome. Its failure
    # cannot reinterpret the already reconciled kernel commit. Unknown remains
    # unknown when its own custody or delivery cannot be established.
    observation["provisional"]=provisional.object()
    observation["provisional_body_write_wall_seconds"]=provisional_write_seconds
    observation["authoritative_terminal"]=receipt.object() if receipt else None
    observed_now=int(time.time())
    observed_payload=dict(payload,kind="publication_observation",evidence_id="OBSERVED_"+stage,
        issued_at=observed_now,expires_at=max(spec["attempt_expires_at"],observed_now+86400),content=observation)
    observed_ref=None;observation_error=None
    observation_write_started=time.monotonic()
    try:
        observed_ref=journal.json("journal/"+stage+".publication-observation.json",
            issue(observed_payload,keys[spec["issuers"]["completion"]]),
            role="signed_publication_observation",visibility="operator",producer=stage)
    except BaseException as exc:
        observation_error={"class":type(exc).__name__,"message":str(exc)[:2048],
                           "status":"telemetry_custody_unavailable","authority_changed":False}
    committed=receipt is not None and final is not None
    return {"receipt":receipt.object() if committed else None,
            "outcome":final["content"]["outcome"] if committed else "publication_unresolved",
            "failure":final["content"]["failure"] if committed else {"class":"PublicationUnresolved","observation":observation},
            "receipt_kind":final["kind"] if committed else None,
            "provisional":provisional.object(),"expected_terminal_path":str(final_path(root,stage)),
            "publication_observation":observed_ref.object() if observed_ref else None,
            "publication_observation_custody_error":observation_error,
            "publication_observed_facts":observation,
             "observation_write_wall_seconds_at_delivery":time.monotonic()-observation_write_started,
             "subsequent_output_delivery_cost":"unmeasured; requires independent outer capture, never zero-imputed",
            "attempt_lifetime_at_acknowledgement":observation["attempt_lifetime_at_acknowledgement"],
            "future_stage_admission":"Requires fresh current-time authorize_stage; a committed historical fact is not continuing execution permission."}


def dispatch_worker(context):
    """Called only inside the bounded trusted stage worker after parent admission."""
    context.require_scientific()
    module = importlib.import_module(COMPONENT[context.stage])
    result = module.run(context.stage, context)
    if not isinstance(result, StageResult):
        raise ContractError("concrete stage implementation returned invalid result")
    # Every returned artifact must be from this invocation's exact writes.
    written = {canonical(a.object()) for a in context.written.values()}
    if any(canonical(a.object()) not in written for a in result.artifacts.values()):
        raise ContractError("stage returned an artifact it did not create")
    return result
