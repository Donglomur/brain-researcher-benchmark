"""Actual data-free F authors, current-query I loops, and provider-free F runs.

Only source-owned transports execute work. No completed-model/prediction callback
is accepted. These functions require separately admitted execution authority in
the parent; importing this module performs no provider/native operation.
"""
import ast
import copy
import math
import os
from pathlib import Path
import time
import uuid

import common as c
from candidate_runner import probability_row, validate_context
from runtime import Bridge, Runtime, admit_closure, relative
from transport.common import AdapterError
from transport.provider import ChatCompletionTransport

TRACE_CAP = 16 * 2**20
AUTHOR_PROMPT = """You are authoring the frozen NEURAL-081 programme before any authentic training/query/model exposure. Reply only with one JSON object. A Python action is {\"action\":\"python\",\"code\":\"...\",\"requested_seconds\":integer}; at most eight actions, each at most60seconds and within480 cumulative seconds. Code is at most65536UTF8bytes. The final object is {\"action\":\"seal_program\",\"entrypoint\":\"program.py\",\"files\":[{\"relative_path\":\"program.py\",\"source\":\"...\"}]}. Provide1..16ordinary.pyfiles, total at most524288UTF8bytes. program.py must provide predict(context), returning a plain list of12finite probabilities in the declared class order with sum within1e-6 of1. At query time your sealed programme receives the complete permitted nine-person training set, immutable model tools and exactly one unlabeled query; it may jointly adapt private scratch state from their union. It has one480second native invocation, no provider/network/children, and no other query/target/shared writable state. Do not request a statistical reviewer. Python action context contains public protocol only. All requests/actions/failures consume their original budget; no automatic retries or history truncation."""
I_PROMPT = """Investigate this one current NEURAL-081 query. Reply only with one JSON object: {\"action\":\"python\",\"code\":\"...\",\"requested_seconds\":integer} or final {\"action\":\"predict\",\"probabilities\":[12numbers]}. At most8Python actions/9requests; each positive requested interval must fit the remaining480 cumulative native seconds. Code at most65536UTF8bytes. Python receives variable context and the generic input/model/tool paths. All permitted nine-person training evidence and exactly one unlabeled current query may jointly drive scratch fitting, pseudo-labels or private model adaptation. Original models/source remain readonly. No target/feedback, other query/context, provider from Python, network, child process or shared writable state exists. Keep probabilities finite in[0,1], class order fixed, sum within1e-6 of1; no scorer renormalization. A closed analytical error can consume a later action; uncertain closure, malformed output or unprojectable streams abort. No statistical-semantic review service is required. Full conversation and every failure remain retained without automatic retry/truncation."""


def parse_action(text, mode, native_remaining, actions_used):
    c.need(type(text) is str, "plain complete provider text")
    action = c.parse(text); c.need(type(action) is dict and type(action.get("action")) is str, "exact JSON action")
    if action["action"] == "python":
        c.exact(action, ("action", "code", "requested_seconds"))
        c.need(actions_used < 8 and type(action["code"]) is str and action["code"], "bounded nonempty Python action")
        raw = action["code"].encode("utf-8", errors="strict"); c.need(len(raw) <= 65536, "source byte cap before launch")
        c.integer(action["requested_seconds"], 1, min(60 if mode == "author" else 480, native_remaining))
        return action
    if mode == "author":
        c.exact(action, ("action", "entrypoint", "files")); c.need(action["action"] == "seal_program" and action["entrypoint"] == "program.py", "exact fixed source seal")
        c.need(type(action["files"]) is list and 1 <= len(action["files"]) <= 16, "complete bounded source bundle")
        names = []; size = 0
        for row in action["files"]:
            c.exact(row, ("relative_path", "source")); name = relative(row["relative_path"])
            c.need(name.endswith(".py") and type(row["source"]) is str, "ordinary Python source only")
            names.append(name); raw = row["source"].encode("utf-8", errors="strict"); size += len(raw)
            c.need(size <= 524288, "full bundle source byte cap")
            ast.parse(row["source"], filename="/programme/" + name)
        c.need(len(names) == len(set(names)) and "program.py" in names, "unique complete programme closure")
        return action
    c.exact(action, ("action", "probabilities")); c.need(action["action"] == "predict", "final current-query prediction")
    action["probabilities"] = probability_row(action["probabilities"])
    return action


def _limits(parent, mode, context=None):
    author_mode = mode == "author"; fixed_mode = mode == "fixed"
    read = 256 * 2**20 if author_mode else context["remaining"]["managed_read_bytes"]
    writes = 256 * 2**20 if author_mode else 16 * 2**30
    limits = dict(seconds=2400, read_bytes=read, write_bytes=writes + TRACE_CAP,
                  native_cpu_seconds=480, native_processes=1 if fixed_mode else 8, host_processes=0,
                  provider_requests=0 if fixed_mode else 9, provider_tokens=0 if fixed_mode else 9 * (32768+4096),
                  stream_bytes=(1 if fixed_mode else 8) * 2 * (262144+1), tool_processes=0 if fixed_mode else 8)
    c.need(set(limits) == {"seconds", *parent.limits}, "complete unchanged study counter schema")
    return limits


def remaining(local, mode):
    return {"native_seconds": max(0, local.limits["native_cpu_seconds"]-local.used["native_cpu_seconds"]),
            "native_actions": max(0, local.limits["native_processes"]-local.used["native_processes"]),
            "provider_requests": max(0, local.limits["provider_requests"]-local.used["provider_requests"]),
            "scratch_write_bytes": max(0, local.limits["write_bytes"]-local.used["write_bytes"]-TRACE_CAP),
            "managed_read_bytes": max(0, local.limits["read_bytes"]-local.used["read_bytes"]),
            "source_bytes": 524288 if mode == "author" else 65536,
            "normal_seconds_remaining": max(0.,local.end-local.clock())}


class TraceReservation:
    """Source, raw action results and engine transcript preflight within16MiB."""
    def __init__(self): self.extra = 0
    def reserve(self, amount, provider=None):
        c.integer(amount)
        provider_reserved = 0 if provider is None else provider.reserved_trace
        c.need(self.extra + amount + provider_reserved <= TRACE_CAP, "complete episode trace reservation")
        self.extra += amount
        if provider is not None:
            provider.config["transcript_cap_bytes"] = min(provider.config["transcript_cap_bytes"], TRACE_CAP-self.extra)
    def native(self, runtime, seconds, code_bytes, manifest_bytes, provider=None):
        # Conservative upper count of same-process engine control requests, including
        # two observations per polling interval, create/attach/closeout and receipts.
        calls = 24 + 2 * math.ceil(seconds/runtime.config["poll_seconds"])
        reserve = calls * (2 * runtime.config["engine_response_cap_bytes"] + 2048) + 2 * 262144 + 524288 + code_bytes + manifest_bytes
        self.reserve(reserve, provider)
        return reserve


def _no_private_text(text, runtime, mounts):
    forbidden = [str(runtime.root), *[d["path"] for d in runtime.source_files], *[m["source"]["path"] for m in mounts]]
    c.need(not any(value and value in text for value in forbidden), "private runtime path cannot be projected")
    c.need(not any(value in text for value in ("/Users/", "/home/", "file://", "Bearer ")), "runtime-private text cannot be projected")


def project_stream(raw, limit, runtime, mounts):
    c.need(type(raw) is bytes and len(raw) <= 262144, "complete bounded original stream")
    # Invalid UTF8 is retained as a closed encoding error but never replaced,
    # decoded with replacement characters, or sent as an invented prefix.
    text = raw.decode("utf-8", errors="strict")
    _no_private_text(text, runtime, mounts)
    return {"text": text[:limit], "projection_truncated": len(text) > limit,
            "original_bytes": len(raw), "original_sha256": c.pin(raw)["sha256"]}


def _result(record, budget):
    admit_closure(record)
    rows = record["candidate_artifact_snapshots"]
    candidates = [d for d in rows if Path(d["path"]).name == "RESULT.json" and Path(d["path"]).parent.name == "artifacts"]
    c.need(len(candidates) == 1, "host-authenticated exact operation result")
    value = c.capture_json(candidates[0], budget, [Path(candidates[0]["path"]).parent])
    c.exact(value, ("schema", "operation", "status", "error_category", "probabilities"))
    c.need(value["schema"] == "neural081_candidate_operation_result_v1" and value["status"] in
           ("completed", "closed_analytical_error", "closed_encoding_error"), "closed source operation result schema")
    c.need((value["status"] == "completed" and value["error_category"] is None) or
           (value["status"] == "closed_analytical_error" and value["error_category"] == "analytical_error") or
           (value["status"] == "closed_encoding_error" and value["error_category"] == "encoding_error"), "generic closed error category")
    return value


def _tool_projection(record, result, action_index, local, mode, runtime, mounts):
    raw = {name: c.capture(desc, local, [Path(desc["path"]).parent], empty=True) for name, desc in record["raw_streams"].items()}
    try:
        stdout = project_stream(raw["stdout"], 8192, runtime, mounts)
        stderr = project_stream(raw["stderr"], 2048, runtime, mounts)
    except UnicodeError as error:
        # The original native closure remains true. The episode/projection fails,
        # with no further provider request and no fabricated decoded transcript.
        raise AdapterError("closed_encoding_error: raw UTF8 projection withheld", {"native_receipt":record["receipt"], "raw_streams":record["raw_streams"], "provider_delivery":False}) from error
    files = [{"relative_path":str(Path(desc["path"]).relative_to(Path(record["work_root"]))),
              "bytes":desc["bytes"],"sha256":desc["sha256"]} for desc in record["artifacts"] if Path(desc["path"]) != Path(record["work_root"])/"RESULT.json"]
    return {"action_index":action_index,"status":result["status"],"stdout":stdout,"stderr":stderr,
            "files":files,"remaining":remaining(local,mode)}


def _runner_descriptor(source_mounts, runner=None):
    if runner is not None:
        c.descriptor(runner); return runner
    rows = [m["source"] for m in source_mounts if m["target"] == "/tools/candidate_runner.py"]
    c.need(len(rows) == 1, "exact source-owned runner closure")
    return rows[0]


def _native_request(context, operation, mounts, action_source, programme, config):
    return {"schema":"neural081_candidate_runner_v1", "operation":operation, "context":context,
            "input_manifest":[dict(m["source"],path=m["target"]) for m in mounts],
            "action_source":None if action_source is None else dict(action_source,path="/action/action.py"),
            "programme":programme, "workspace_cap_bytes":min(config["workspace_cap_bytes"],256*2**20 if operation=="author_python" else 16*2**30),
            "workspace_entry_cap":config["workspace_entry_cap"]}


def _native_action(index, action, context, mode, mounts, runner, native, local, directory, workspace, owner, trace, provider):
    action_deadline = min(local.end, local.clock()+action["requested_seconds"])
    action_dir = c.new_directory(directory/("action-%03d" % index),local)
    source = c.publish(action_dir/"action.py",action["code"].encode("utf-8"),local)
    action_mounts = [dict(m) for m in mounts]
    if not any(m["target"] == "/tools/candidate_runner.py" for m in action_mounts):
        action_mounts.append({"source":runner,"target":"/tools/candidate_runner.py","opaque_host":False})
    action_mounts.append({"source":source,"target":"/action/action.py","opaque_host":False})
    projected = copy.deepcopy(context)
    if mode != "author": projected["remaining"] = remaining(local,mode)
    request = _native_request(projected,"author_python" if mode=="author" else "python",action_mounts,source,None,native.config)
    raw_request = c.encoded(request)
    trace.native(native,action["requested_seconds"],source["bytes"],len(raw_request),provider)
    request_pin = c.publish(action_dir/"request.json",raw_request,local)
    action_mounts.append({"source":request_pin,"target":"/action/request.json","opaque_host":False})
    record = native.run(owner+"/action-%03d"%index,"/tools/candidate_runner.py",action_mounts,["/action/request.json"],
                        seconds=action["requested_seconds"],memory_bytes=(4 if mode=="author" else 8)*2**30,
                        kind="author" if mode=="author" else "investigate",workspace=workspace,original_deadline=action_deadline)
    result = _result(record,local)
    c.need(result["operation"] == ("author_python" if mode=="author" else "python") and result["probabilities"] is None,"same analytical action result")
    public = _tool_projection(record,result,index,local,mode,native,action_mounts)
    c.publish_json(action_dir/"TOOL_RESULT.json",public,local)
    return record, public


def _setup(mode, runtime, budget, root, context=None):
    local = c.LocalBudget(budget,_limits(budget,mode,context))
    directory = c.new_directory(c.absolute(str(root))/uuid.uuid4().hex,local)
    native_root = c.new_directory(directory/"native",local)
    native = Runtime(runtime.config,local,runtime.source_files,native_root)
    owner = ("author" if mode=="author" else context["context_alias"])+"-"+uuid.uuid4().hex
    workspace = native.allocate(owner)
    return local,directory,native,owner,workspace


def _provider_admission(transport, local):
    c.need(len(transport.records) == local.used["provider_requests"] and 1 <= len(transport.records) <= 9, "complete original request attempts")
    for record in transport.records:
        c.need(record["status"] == "completed" and record["response_stream_closed"] is True and
               record["ended_monotonic"] <= record["normal_deadline"] <= record["original_deadline"] == local.end,
               "original provider closure without retries or reset")
        c.need(record["usage"]["prompt_tokens"] == record["exact_input_tokens"] <= 32768 and
               record["usage"]["completion_tokens"] <= 4096, "exact selected token framing/usage")
    return True


def _seal(action, replication, directory, local):
    sealed = c.new_directory(directory/"sealed",local); files=[]
    for row in sorted(action["files"], key=lambda value:value["relative_path"]):
        path = sealed/row["relative_path"]
        for parent in reversed(path.parents):
            if parent != sealed and parent.is_relative_to(sealed) and not parent.exists(): c.new_directory(parent,local)
        descriptor = c.publish(path,row["source"].encode("utf-8"),local); path.chmod(0o444)
        c.capture(descriptor,local,[sealed]); files.append({"relative_path":row["relative_path"],"source":descriptor})
    seal = {"schema":"neural081_frozen_programme_v1","replication":replication,"entrypoint":"program.py","files":files,
            "before_authentic_exposure_required":True,"provider_at_query":False}
    seal["receipt"] = c.publish_json(directory/"SEALED.json",seal,local)
    return seal


def author(replication, provider_config, runtime, budget, root, source_mounts, public_protocol):
    c.need(replication in c.REPS and type(public_protocol) is dict,"selected data-free author")
    c.need(all(m["target"].startswith("/tools/") and m["opaque_host"] is False for m in source_mounts),"author public source only, no authentic operands")
    runner = _runner_descriptor(source_mounts)
    local,directory,native,owner,workspace = _setup("author",runtime,budget,root)
    context = {"schema":"neural081_author_context_v1","replication":replication,"public_protocol":public_protocol}
    initial = c.encoded(context,False).decode(); _no_private_text(initial,native,source_mounts)
    messages=[{"role":"system","content":AUTHOR_PROMPT},{"role":"user","content":initial}]
    trace=TraceReservation();trace.reserve(len(c.encoded(messages))+65536)
    provider=None;record={"schema":"neural081_author_episode_v1","replication":replication,"original_deadline":local.end,
                          "authentic_inputs_exposed":False,"native_actions":[],"status":"entered"}
    c.publish_json(directory/"INTENT.json",record,local)
    try:
        config=copy.deepcopy(provider_config);config["transcript_cap_bytes"]=min(config["transcript_cap_bytes"],TRACE_CAP-trace.extra)
        provider=ChatCompletionTransport(config,Bridge(local),directory/"provider")
        for ordinal in range(1,10):
            local.check_clock();message,finish=provider.complete(messages,allow_tools=False)
            c.need(finish=="stop","complete text JSON action");messages.append(message)
            action=parse_action(message["content"],"author",remaining(local,"author")["native_seconds"],len(record["native_actions"]))
            if action["action"]=="seal_program":
                trace.reserve(sum(len(row["source"].encode("utf-8"))for row in action["files"]),provider)
                record["programme"]=_seal(action,replication,directory,local);break
            native_record,public=_native_action(len(record["native_actions"])+1,action,context,"author",source_mounts,runner,native,local,directory,workspace,owner,trace,provider)
            record["native_actions"].append(native_record);messages.append({"role":"user","content":c.encoded(public,False).decode()})
        c.need("programme"in record,"final seal before request exhaustion");_provider_admission(provider,local)
        record.update(status="completed",source_admitted_natural_closure=True)
        return record
    except BaseException as error:
        record.update(status="failed",failure_type=type(error).__name__,failure_evidence=getattr(error,"evidence",None));raise
    finally:
        record["provider_attempts"]=[]if provider is None else provider.records;record["trace_reservation"]={"extra":trace.extra,"provider":0 if provider is None else provider.reserved_trace,"cap":TRACE_CAP}
        record["budget"]=local.snapshot();record["ended_monotonic"]=time.monotonic()
        try:record["receipt"]=c.publish_json(directory/"EPISODE.json",record,local)
        except BaseException:
            record["receipt_publication_uncertain"]=True
            if record["status"]=="completed":raise


def investigate(context,provider_config,runtime,budget,root,mounts,runner):
    validate_context(context);c.need(context["mode"]=="I","current-query I context")
    runner=_runner_descriptor(mounts,runner)
    local,directory,native,owner,workspace=_setup("investigate",runtime,budget,root,context)
    public=copy.deepcopy(context);public["remaining"]=remaining(local,"investigate")
    initial=c.encoded(public,False).decode();_no_private_text(initial,native,mounts)
    messages=[{"role":"system","content":I_PROMPT},{"role":"user","content":initial}]
    trace=TraceReservation();trace.reserve(len(c.encoded(messages))+65536)
    provider=None;record={"schema":"neural081_candidate_episode_v1","mode":"I","context_alias":context["context_alias"],
                         "original_deadline":local.end,"native_actions":[],"status":"entered","target_feedback":False}
    c.publish_json(directory/"INTENT.json",record,local)
    try:
        config=copy.deepcopy(provider_config);config["transcript_cap_bytes"]=min(config["transcript_cap_bytes"],TRACE_CAP-trace.extra)
        provider=ChatCompletionTransport(config,Bridge(local),directory/"provider")
        for ordinal in range(1,10):
            local.check_clock();message,finish=provider.complete(messages,allow_tools=False)
            c.need(finish=="stop","complete text JSON action");messages.append(message)
            action=parse_action(message["content"],"investigate",remaining(local,"investigate")["native_seconds"],len(record["native_actions"]))
            if action["action"]=="predict":record["probabilities"]=action["probabilities"];break
            native_record,tool=_native_action(len(record["native_actions"])+1,action,context,"investigate",mounts,runner,native,local,directory,workspace,owner,trace,provider)
            record["native_actions"].append(native_record);messages.append({"role":"user","content":c.encoded(tool,False).decode()})
        c.need("probabilities"in record,"final probability row before request exhaustion");_provider_admission(provider,local)
        record["prediction_artifact"]=c.publish_json(directory/"PREDICTION.json",{"context_alias":context["context_alias"],"probabilities":record["probabilities"]},local)
        record.update(status="completed",source_admitted_natural_closure=True);return record
    except BaseException as error:
        record.update(status="failed",failure_type=type(error).__name__,failure_evidence=getattr(error,"evidence",None));raise
    finally:
        record["provider_attempts"]=[]if provider is None else provider.records;record["trace_reservation"]={"extra":trace.extra,"provider":0 if provider is None else provider.reserved_trace,"cap":TRACE_CAP}
        record["budget"]=local.snapshot();record["ended_monotonic"]=time.monotonic()
        try:record["receipt"]=c.publish_json(directory/"EPISODE.json",record,local)
        except BaseException:
            record["receipt_publication_uncertain"]=True
            if record["status"]=="completed":raise


def fixed(context,programme,runtime,budget,root,mounts,runner):
    """Exactly one sealed predict(context) invocation; no provider constructor/call."""
    validate_context(context);c.need(context["mode"]=="F","fixed current-query context")
    c.need(programme["schema"]=="neural081_frozen_programme_v1"and programme["replication"]==context["replication"]and programme["entrypoint"]=="program.py","same pre-exposure seal")
    runner=_runner_descriptor(mounts,runner)
    local,directory,native,owner,workspace=_setup("fixed",runtime,budget,root,context)
    original_deadline=min(local.end,local.clock()+480)
    all_mounts=[dict(m)for m in mounts]
    if not any(m["target"]=="/tools/candidate_runner.py"for m in all_mounts):all_mounts.append({"source":runner,"target":"/tools/candidate_runner.py","opaque_host":False})
    generic=[]
    for row in programme["files"]:
        relative(row["relative_path"]);c.descriptor(row["source"])
        target="/programme/"+row["relative_path"];all_mounts.append({"source":row["source"],"target":target,"opaque_host":False});generic.append(dict(row["source"],path=target))
    public=copy.deepcopy(context);public["remaining"]=remaining(local,"fixed")
    request=_native_request(public,"fixed",all_mounts,None,{"entrypoint":"/programme/program.py","files":generic},native.config)
    trace=TraceReservation();trace.native(native,480,sum(d["bytes"]for d in generic),len(c.encoded(request)))
    req=c.publish_json(directory/"request.json",request,local);all_mounts.append({"source":req,"target":"/action/request.json","opaque_host":False})
    native_record=native.run(owner,"/tools/candidate_runner.py",all_mounts,["/action/request.json"],seconds=480,memory_bytes=8*2**30,kind="fixed",workspace=workspace,original_deadline=original_deadline)
    result=_result(native_record,local);c.need(result["operation"]=="fixed"and result["status"]=="completed","one successful fixed prediction")
    row=probability_row(result["probabilities"])
    record={"schema":"neural081_candidate_episode_v1","mode":"F","context_alias":context["context_alias"],
            "original_deadline":local.end,"native_actions":[native_record],"provider_attempts":[],"provider_at_query":False,
            "status":"completed","source_admitted_natural_closure":True,"probabilities":row,"budget":local.snapshot(),
            "prediction_artifact":c.publish_json(directory/"PREDICTION.json",{"context_alias":context["context_alias"],"probabilities":row},local),
            "trace_reservation":{"extra":trace.extra,"provider":0,"cap":TRACE_CAP}}
    record["receipt"]=c.publish_json(directory/"EPISODE.json",record,local);return record
