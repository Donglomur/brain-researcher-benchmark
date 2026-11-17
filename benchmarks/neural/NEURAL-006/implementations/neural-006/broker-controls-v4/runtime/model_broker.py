"""Host-owned OpenAI broker; only reviewed provider source can access credentials/network."""
import base64
import hashlib
import hmac
import math
import os
from pathlib import Path
import secrets
import selectors
import subprocess
import tempfile
import time
from actors import Actors
from custody import parse
from model_state import CandidateSession, TrainingSession
from protocol import canonical, digest, exact_keys, need

ENDPOINT={"scheme":"https","host":"api.openai.com","port":443,"path":"/v1/responses"}
CONFIG_KEYS=("schema","endpoint","model","parameters","credential","token_bound","prompt",
 "python","qualification","limits","pricing","provider_hardware_policy")
LIMIT_KEYS=("calls_per_case","calls_total","request_bytes","response_bytes","result_bytes",
 "input_tokens","output_tokens","total_tokens_per_call","total_tokens","request_bytes_total",
 "response_bytes_total","timeout_seconds","spend_microdollars","compute_calls_per_case",
 "compute_seconds_per_call","compute_source_bytes","compute_stdout_bytes","compute_stderr_bytes")
BINDING_KEYS=("adapter_sha256","source_sha256","prompt_sha256","config_sha256","qualification_sha256")


FRAME_CAP=2097152
COMPUTE_REPORT_KEYS=("schema","action_sha256","language","source_sha256","status","returncode",
 "stdout_base64","stderr_base64","stdout_observed_bytes","stderr_observed_bytes",
 "stdout_retained_bytes","stderr_retained_bytes","stdout_sha256","stderr_sha256",
 "stdout_eof","stderr_eof","group_absent","elapsed_seconds","errors","observation_trust")

def compute_limits(config):
    v=config["limits"]
    return {"seconds":v["compute_seconds_per_call"],"source_bytes":v["compute_source_bytes"],
            "stdout_bytes":v["compute_stdout_bytes"],"stderr_bytes":v["compute_stderr_bytes"]}

def compute_action(action,limits):
    exact_keys(action,("compute",),"compute_action_fields");v=action["compute"]
    exact_keys(v,("language","source"),"compute_program_fields")
    need(v["language"] in ("python","r") and type(v["source"]) is str and
         0<len(v["source"].encode())<=limits["source_bytes"],"bounded_selected_compute_program")
    need(len(canonical(action))<=FRAME_CAP-16384,"encoded_compute_program_cap")
    return hashlib.sha256(v["source"].encode()).hexdigest()

def compute_report(report,action,limits):
    exact_keys(report,COMPUTE_REPORT_KEYS,"candidate_compute_report_fields")
    need(report["schema"]=="neural006-candidate-computation-v1" and
         report["observation_trust"]=="candidate_reported_untrusted","no_candidate_observation_authority")
    need(report["action_sha256"]==digest(action) and report["language"]==action["compute"]["language"] and
         report["source_sha256"]==compute_action(action,limits),"exact_issued_compute_source")
    for label in ("stdout","stderr"):
        text=report[label+"_base64"];cap=limits[label+"_bytes"]
        need(type(text) is str and len(text)<=4*((cap+2)//3),"encoded_compute_stream_cap")
        body=base64.b64decode(text,validate=True)
        need(len(body)<=cap and type(report[label+"_retained_bytes"]) is int and
             report[label+"_retained_bytes"]==len(body) and report[label+"_sha256"]==hashlib.sha256(body).hexdigest(),
             "candidate_stream_byte_identity")
        need(type(report[label+"_observed_bytes"]) is int and
             len(body)<=report[label+"_observed_bytes"]<2**63 and type(report[label+"_eof"]) is bool,
             "candidate_stream_report_types")
    need((report["group_absent"] is None or type(report["group_absent"]) is bool) and
         (report["returncode"] is None or type(report["returncode"]) is int),"candidate_process_report_types")
    need(type(report["elapsed_seconds"]) in (int,float) and math.isfinite(report["elapsed_seconds"]) and
         report["elapsed_seconds"]>=0,"candidate_elapsed_report")
    need(type(report["errors"]) is list and len(report["errors"])<=32,"bounded_candidate_errors")
    for error in report["errors"]:
        exact_keys(error,("phase","class","code"),"candidate_error_fields")
        need(all(type(x) is str and len(x.encode())<=1024 for x in error.values()),"bounded_candidate_error_text")
    status=report["status"];need(status in ("complete","analysis_failed","infrastructure_failed"),"candidate_compute_status")
    if status!="infrastructure_failed":
        need(report["group_absent"] is True and report["stdout_eof"] and report["stderr_eof"] and
             type(report["returncode"]) is int and not report["errors"],"candidate_complete_report_consistency")
        need((report["returncode"]==0)==(status=="complete"),"candidate_exit_report_consistency")
    # These checks authenticate a bounded candidate report, not its truth or resource authority.
    return report

def pin(s):
    return type(s) is str and len(s)==64 and all(x in "0123456789abcdef" for x in s)

def read_descriptor(c,row):
    exact_keys(row,("path","bytes","sha256"),"broker_descriptor")
    need(type(row["path"]) is str and Path(row["path"]).is_absolute(),"broker_absolute_descriptor")
    need(type(row["bytes"]) is int and 0<row["bytes"]<=16777216 and pin(row["sha256"]),"broker_descriptor_extent")
    return c.read(row["path"],row["bytes"],row["sha256"])

def config_identity(config):
    return digest({k:v for k,v in config.items() if k!="qualification"})

def authenticate_broker(c,config,sources,source_sha,programs):
    exact_keys(config,CONFIG_KEYS,"broker_config_fields")
    need(config["schema"]=="neural006-host-openai-broker-v1","broker_config_schema")
    need(config["endpoint"]==ENDPOINT,"selected_concrete_endpoint")
    need(type(config["model"]) is str and 0<len(config["model"])<=256,"selected_model")
    need(type(config["parameters"]) is dict and
         config["parameters"].get("max_output_tokens")==config["limits"]["output_tokens"],"explicit_generation_output_cap")
    need(type(config["prompt"]) is str and 0<len(config["prompt"].encode())<=32768,"frozen_developer_prompt")
    need(config["provider_hardware_policy"]=="external_unknown_not_container_cpu_or_rss","external_provider_policy")
    limits=config["limits"];exact_keys(limits,LIMIT_KEYS,"broker_limit_keys")
    need(all(type(v) is int and v>0 for v in limits.values()),"positive_broker_limits")
    need(limits["calls_per_case"]<=limits["calls_total"]<=1000000,"finite_call_limits")
    need(limits["compute_calls_per_case"]<=limits["calls_per_case"] and
         limits["compute_seconds_per_call"]<=c.limits["candidate_seconds_per_case"] and
         limits["compute_source_bytes"]<=131072 and limits["compute_stdout_bytes"]<=131072 and
         limits["compute_stderr_bytes"]<=65536,"bounded_compute_policy")
    need(limits["request_bytes"]<=8388608 and limits["response_bytes"]<=2097152 and
         limits["result_bytes"]<=16777216,"bounded_provider_bytes")
    need(limits["input_tokens"]+limits["output_tokens"]<=limits["total_tokens_per_call"]<=limits["total_tokens"],"per_call_token_reservation")
    need(limits["request_bytes"]<=limits["request_bytes_total"] and
         limits["response_bytes"]<=limits["response_bytes_total"],"total_byte_caps")
    need(limits["result_bytes"]>=6*(limits["response_bytes"]+1)+131072,"complete_provider_result_reservation")
    need(FRAME_CAP<=c.limits["per_file_bytes"],"compute_frame_within_original_file_cap")
    need(limits["result_bytes"]+4096<=c.limits["per_file_bytes"],"provider_result_within_original_file_cap")
    need(limits["calls_total"]*2048+c.limits["max_cases"]*1024+65536<=c.limits["per_file_bytes"],"complete_broker_closure_reservation")
    bound=config["token_bound"];exact_keys(bound,("per_utf8_byte","overhead_tokens"),"token_bound_fields")
    need(all(type(v) is int and v>0 for v in bound.values()),"positive_explicit_token_bound")
    rates=config["pricing"];exact_keys(rates,("currency","input_microdollars_per_million_tokens","output_microdollars_per_million_tokens"),"pricing_fields")
    need(rates["currency"]=="USD" and all(type(rates[k]) is int and rates[k]>0 for k in rates if k!="currency"),"explicit_positive_price_ceiling")
    credential=config["credential"]
    exact_keys(credential,("path","device","inode","uid","mode","bytes","mtime_ns","ctime_ns"),"credential_metadata")
    need(type(credential["path"]) is str and Path(credential["path"]).is_absolute(),"private_credential_path")
    need(all(type(credential[k]) is int and credential[k]>=0 for k in credential if k!="path"),"credential_stat_fields")
    need(credential["mode"]==0o600 and 0<credential["bytes"]<=16384,"private_credential_extent")
    # Hash the selected interpreter without loading a provider or reading a credential.
    read_descriptor(c,config["python"])
    need(programs["adaptive_investigation"]==sources["candidate_relay.py"],"exact_trusted_relay_source")
    qbody=read_descriptor(c,config["qualification"]);q=parse(qbody)
    exact_keys(q,("schema","provider_identity_sha256","source_manifest_sha256","provider_worker_sha256",
                 "model_id_is_immutable_snapshot","live_requests_authorized","credential_access_authorized",
                 "token_bound_evidence","source_review_sha256","provider_hardware_policy"),"broker_qualification_fields")
    need(q["schema"]=="neural006-broker-admission-v1" and
         q["provider_identity_sha256"]==config_identity(config) and q["source_manifest_sha256"]==source_sha and
         q["provider_worker_sha256"]==hashlib.sha256(sources["provider_worker.py"]).hexdigest(),"concrete_qualified_source_identity")
    need(q["model_id_is_immutable_snapshot"] is True and q["live_requests_authorized"] is True and
         q["credential_access_authorized"] is True and pin(q["source_review_sha256"]),"explicit_current_provider_admission")
    need(q["provider_hardware_policy"]==config["provider_hardware_policy"],"qualified_remote_accounting")
    evidence=parse(read_descriptor(c,q["token_bound_evidence"]))
    exact_keys(evidence,("schema","model","source_manifest_sha256","per_utf8_byte","overhead_tokens",
                        "request_schema","accepted_upper_bound","proof_record"),"token_proof_fields")
    need(evidence["schema"]=="neural006-input-token-bound-v1" and evidence["model"]==config["model"] and
         evidence["source_manifest_sha256"]==source_sha and
         evidence["per_utf8_byte"]==bound["per_utf8_byte"] and evidence["overhead_tokens"]==bound["overhead_tokens"] and
         evidence["request_schema"]=="OpenAI_Responses_full_request_utf8_v1" and
         evidence["accepted_upper_bound"] is True,"qualified_input_bound_required")
    read_descriptor(c,evidence["proof_record"])
    return {"identity":config_identity(config),"qualification_sha256":hashlib.sha256(qbody).hexdigest(),
            "source_sha256":source_sha,"worker_sha256":q["provider_worker_sha256"],
            "token_bound_evidence":q["token_bound_evidence"],"source_review_sha256":q["source_review_sha256"]}

def frame(key,session_id,sequence,kind,payload,previous):
    body={"schema":"neural006-model-duplex-v1","session_id":session_id,"sequence":sequence,
          "kind":kind,"payload":payload,"previous_sha256":previous}
    return {**body,"mac":hmac.new(key,canonical(body),hashlib.sha256).hexdigest()}

class BrokerSession:
    native=False
    def __init__(self,inner,owner,artifact=None):
        self.inner=inner;self.owner=owner;self.artifact=artifact
        self.finished=False;self.value=None;self.sequence=0;self.pending=None;self.history=[]
        self.provider_history=[];self.calls=0;self.deadline=None;self.compute_calls=0
        self.computation_deadline=None;self.compute_record=None;self.protocol_line_cap=FRAME_CAP
        self.key=secrets.token_bytes(32);self.session_id=secrets.token_hex(16)
        self.initial={"event":"neural006_broker_open_v1","session_id":self.session_id,"key_hex":self.key.hex(),
                      "initial_sha256":digest(inner.initial),"frame_bytes":FRAME_CAP}
        self.previous=digest(self.initial)
        self.record={"session_id":self.session_id,"initial_sha256":digest(inner.initial),
                     "candidate_seed":inner.initial["candidate_seed"],"event":inner.initial["event"],
                     "provider_calls":0,"tool_calls":0,"finished":False,
                     "frozen_model_sha256":None if artifact is None else artifact["sha256"]}
        owner.sessions.append(self.record)
    def bind_deadline(self,end):
        need(self.deadline is None and math.isfinite(end) and end<=self.owner.c.work_end,"original_session_deadline")
        self.deadline=end;self.record["deadline"]=end
    def next_deadline(self):
        return self.computation_deadline if self.computation_deadline is not None else self.deadline
    def exchange(self,message):
        need(not self.finished and self.deadline is not None and time.monotonic()<self.deadline,"live_broker_session")
        exact_keys(message,("schema","session_id","sequence","kind","payload","previous_sha256","mac"),"broker_frame_keys")
        need(type(message["sequence"]) is int and len(canonical(message))<=FRAME_CAP,"broker_frame_cap")
        expected=frame(self.key,self.session_id,self.sequence+1,message["kind"],message["payload"],self.previous)
        need(type(message["mac"]) is str and hmac.compare_digest(message["mac"],expected["mac"]) and
             {k:v for k,v in message.items() if k!="mac"}=={k:v for k,v in expected.items() if k!="mac"},"authenticated_sequence_and_chain")
        self.sequence+=1;self.previous=digest(message)
        if message["kind"]=="next_action":
            exact_keys(message["payload"],(),"next_action_no_candidate_context")
            need(self.pending is None and self.calls<self.owner.config["limits"]["calls_per_case"],"one_pending_bounded_model_call")
            self.calls+=1;self.record["provider_calls"]=self.calls
            action,provider_output=self.owner.generate(self.inner.initial,self.history,self.provider_history,
                                                       self.artifact,self.deadline,self.session_id,self.calls)
            need(type(action) is dict and (set(action)=={"tool","arguments"} or set(action)=={"submit"} or set(action)=={"trained"} or set(action)=={"compute"}),"provider_actual_protocol_action")
            need((self.inner.initial["event"]=="train_once" and "submit" not in action) or
                 (self.inner.initial["event"]!="train_once" and "trained" not in action),"provider_stage_action")
            self.pending=action;self.provider_history.extend(provider_output)
            if "compute" in action:
                limits=compute_limits(self.owner.config);source_sha=compute_action(action,limits)
                need(self.compute_calls<self.owner.config["limits"]["compute_calls_per_case"],"compute_call_cap")
                need(self.owner.c.written_bytes+2*FRAME_CAP<=self.owner.c.limits["retained_bytes"]-self.owner.c.publication_reserve,
                     "compute_report_retention_reservation")
                need(self.owner.c.files_reserved+2<=self.owner.c.limits["max_files"],"compute_report_file_reservation")
                self.compute_calls+=1;self.record["compute_calls"]=self.compute_calls
                now=time.monotonic();self.computation_deadline=min(self.deadline,now+limits["seconds"])
                self.compute_record={"number":len(self.owner.computations)+1,"session_id":self.session_id,
                    "model_request_id":self.session_id+"-"+str(self.calls),"model_call_number":self.owner.reserved["calls"],
                    "action_sha256":digest(action),"source_sha256":source_sha,"language":action["compute"]["language"],
                    "host_issued_monotonic":now,"host_deadline":self.computation_deadline,
                    "status":"issued_no_report","candidate_observation_authority":False}
                self.owner.computations.append(self.compute_record)
                self.compute_record["issued_record"]=self.owner.c.write("model-compute-issued-%08d.json"%self.compute_record["number"],
                    {**self.compute_record,"issued_action":action,"limits":limits})
                reply_kind="compute";reply={"action_sha256":digest(action),"action":action,"limits":limits,
                    "host_remaining_seconds":self.computation_deadline-now}
            else:
                reply_kind="model_action";reply={"action_sha256":digest(action)}
        elif message["kind"]=="compute_result":
            need(self.pending is not None and "compute" in self.pending and self.compute_record is not None,
                 "one_original_pending_compute")
            need(time.monotonic()<self.computation_deadline,"original_host_compute_deadline")
            report=compute_report(message["payload"],self.pending,compute_limits(self.owner.config))
            record=self.compute_record
            record["candidate_report_sha256"]=digest(report);record["host_received_monotonic"]=time.monotonic()
            record["status"]="reported"
            receipt=self.owner.c.write("model-compute-%08d.json"%record["number"],{**record,"candidate_report":report})
            self.owner.computation_receipts.append(receipt)
            reply_value={"candidate_computation":report,"observation_trust":"candidate_reported_untrusted"}
            self.history.append({"request":self.pending,"reply":reply_value})
            self.provider_history.append({"role":"user","content":canonical(reply_value).decode()})
            self.pending=None;self.compute_record=None;self.computation_deadline=None
            need(report["status"]!="infrastructure_failed","candidate_compute_infrastructure_failure")
            reply_kind="compute_feedback";reply={"reply_sha256":digest(reply_value),"finished":False}
        elif message["kind"]=="apply_action":
            exact_keys(message["payload"],("action_sha256",),"apply_only_issued_action")
            need(self.pending is not None and "compute" not in self.pending and message["payload"]["action_sha256"]==digest(self.pending),"exact_provider_action_commitment")
            action=self.pending;result=self.inner.exchange(action)
            self.history.append({"request":action,"reply":result})
            self.provider_history.append({"role":"user","content":canonical({"tool_or_terminal_reply":result}).decode()})
            self.pending=None;self.finished=self.inner.finished;self.value=self.inner.value
            if not self.finished:self.record["tool_calls"]+=1
            reply_kind="terminal" if self.finished else "tool_result"
            reply={"reply_sha256":digest(result),"finished":self.finished}
            self.record["finished"]=self.finished
        else:
            raise ValueError("unknown_broker_frame")
        self.sequence+=1
        result=frame(self.key,self.session_id,self.sequence,reply_kind,reply,self.previous)
        self.previous=digest(result);return result

class HostBroker:
    def __init__(self,c,config,admission,sources):
        self.c=c;self.config=config;self.admission=admission;self.sessions=[];self.calls=[];self.receipts=[];self.computations=[];self.computation_receipts=[]
        self.task_text=sources["TASK.md"].decode("utf-8")
        self.reserved={"calls":0,"tokens":0,"request_bytes":0,"response_bytes":0,"spend_microdollars":0}
        self.known_usage={"input_tokens":0,"output_tokens":0,"total_tokens":0}
        self.unknown_usage=False;self.closed=False;self.root=None;self.worker=None
        c.model_broker=self # Own partial construction before filesystem effects.
        self.root=Path(tempfile.mkdtemp(prefix="neural006-host-broker-"))
        self.worker=self.root/"provider_worker.py";c.stage(self.worker,sources["provider_worker.py"])
    def generate(self,initial,history,provider_history,artifact,deadline,session_id,turn):
        c=self.c;c.check();need(not self.closed and not self.unknown_usage,"broker_open_and_accounted")
        limit=self.config["limits"];need(time.monotonic()<deadline<=c.work_end,"same_absolute_attempt_deadline")
        token_reserve=limit["total_tokens_per_call"]
        rates=self.config["pricing"]
        cost=(limit["input_tokens"]*rates["input_microdollars_per_million_tokens"]+
              limit["output_tokens"]*rates["output_microdollars_per_million_tokens"]+999999)//1000000
        proposed={"calls":self.reserved["calls"]+1,"tokens":self.reserved["tokens"]+token_reserve,
                  "request_bytes":self.reserved["request_bytes"]+limit["request_bytes"],
                  "response_bytes":self.reserved["response_bytes"]+limit["response_bytes"],
                  "spend_microdollars":self.reserved["spend_microdollars"]+cost}
        caps={"calls":limit["calls_total"],"tokens":limit["total_tokens"],"request_bytes":limit["request_bytes_total"],
              "response_bytes":limit["response_bytes_total"],"spend_microdollars":limit["spend_microdollars"]}
        need(all(proposed[k]<=caps[k] for k in proposed),"nonrefundable_cumulative_provider_cap")
        # Keep complete per-call transport products and a small terminal receipt inside original custody.
        need(c.written_bytes+limit["request_bytes"]+limit["result_bytes"]+65536<=
             c.limits["retained_bytes"]-c.publication_reserve,"complete_provider_evidence_reservation")
        need(c.files_reserved+3<=c.limits["max_files"],"provider_evidence_file_reservation")
        initial_context={"task_markdown":self.task_text,"event":initial,"immutable_frozen_artifact":artifact,
            "direct_computation":{"action_schema":{"compute":{"language":{"enum":["python","r"]},"source":"exact program text"}},
                "limits":compute_limits(self.config),"input_case":"/input/case.json","reference_core":"/protocol/core.R",
                "task_file":"/protocol/TASK.md","frozen_artifact_file":"/input/model.bin" if artifact else None,
                "isolation":"existing offline candidate container; no host execution",
                "result_schema":"neural006-candidate-computation-v1","result_fields":list(COMPUTE_REPORT_KEYS),
                "stdout_stderr_encoding":"base64 exact retained bytes; code outputs are untrusted task data",
                "observations":"candidate-reported/untrusted; do not treat computation output as authenticated reference tool evidence"}}
        inputs=[{"role":"developer","content":self.config["prompt"]},
                {"role":"user","content":canonical(initial_context).decode()},*provider_history]
        bindings={"adapter_sha256":self.admission["worker_sha256"],"source_sha256":self.admission["source_sha256"],
                  "prompt_sha256":hashlib.sha256(self.config["prompt"].encode()).hexdigest(),
                  "config_sha256":self.admission["identity"],"qualification_sha256":self.admission["qualification_sha256"]}
        child_config={"endpoint":self.config["endpoint"],"model":self.config["model"],
                      "parameters":self.config["parameters"],"credential":self.config["credential"],
                      "token_bound":{"model":self.config["model"],"source_sha256":bindings["source_sha256"],
                          "qualification_sha256":bindings["qualification_sha256"],**self.config["token_bound"]},
                      "limits":{"request_bytes":limit["request_bytes"],"response_bytes":limit["response_bytes"],
                          "result_bytes":limit["result_bytes"],"input_tokens":limit["input_tokens"],
                          "output_tokens":limit["output_tokens"],"total_tokens":limit["total_tokens_per_call"],
                          "timeout_seconds":limit["timeout_seconds"]},"bindings":bindings}
        request_id=session_id+"-"+str(turn)
        envelope={"schema":"n006-provider-request-v1","request_id":request_id,"deadline":deadline,
                  "config":child_config,"input":inputs}
        body=canonical(envelope);need(len(body)<=limit["request_bytes"],"complete_worker_envelope_cap")
        self.reserved=proposed # Consume before publication/dispatch; never refund a failed request.
        number=self.reserved["calls"]
        record={"number":number,"request_id":request_id,"session_id":session_id,"turn":turn,
                "deadline":deadline,"reserved_tokens":token_reserve,"reserved_microdollars":cost,
                "provider_hardware":{"cpu_seconds":None,"peak_rss_bytes":None,"status":"unmeasured_external"},
                "usage":None,"status":"entered","response":None}
        self.calls.append(record)
        raw=b"";failure=None;result=None
        try:
            request_pin=c.write_bytes("model-request-%08d.json"%number,body);record["request"]=request_pin
            try:raw=self.process(body,deadline,record)
            except BaseException as error:
                failure=error;raw=record.pop("_raw_stdout",b"")
            result=parse(raw)
            need(type(result) is dict and result.get("schema")=="n006-provider-result-v1" and
                 result.get("request_id")==request_id and result.get("envelope_sha256")==hashlib.sha256(body).hexdigest() and
                 result.get("bindings")==bindings,"worker_result_identity")
            usage=result.get("usage")
            if usage is not None:
                need(type(usage) is dict and all(type(usage.get(k)) is int and usage[k]>=0 for k in self.known_usage),"actual_usage_fields")
                need(usage["input_tokens"]+usage["output_tokens"]==usage["total_tokens"],"actual_usage_arithmetic")
                record["usage"]={k:usage[k] for k in self.known_usage}
                for key in self.known_usage:self.known_usage[key]+=usage[key]
                need(usage["input_tokens"]<=limit["input_tokens"] and usage["output_tokens"]<=limit["output_tokens"] and
                     usage["total_tokens"]<=token_reserve,"qualified_token_bound_exceeded_actual_retained")
            else:
                self.unknown_usage=True
            record["provider_status"]=result.get("provider_status")
            record["status"]=result.get("status")
            need(not self.unknown_usage and result.get("usage_unknown") is False,"unknown_provider_usage_stops_campaign")
            if failure is not None:raise failure
            need(record.get("process",{}).get("returncode")==0,"provider_worker_nonzero_after_usage_settlement")
            need(result.get("status")=="complete" and result.get("model")==self.config["model"],"provider_complete_exact_model")
            output=result.get("output_text");need(type(output) is str,"provider_action_json_text")
            action=parse(output.encode());need(len(canonical(action))<=c.limits["per_file_bytes"],"provider_action_extent")
            carried=result.get("output_history");need(type(carried) is list,"complete_provider_history")
        except BaseException as error:
            if failure is None:failure=error
            record["status"]="failed";record["failure"]={"class":type(error).__name__,"message":str(error)[:512]}
            if record["usage"] is None:self.unknown_usage=True
        finally:
            # process() records the full bounded stdout even on nonzero/timeout.
            if not raw:raw=record.pop("_raw_stdout",b"")
            else:record.pop("_raw_stdout",None)
            try:record["response"]=c.write_bytes("model-response-%08d.json"%number,raw,diagnostic=True)
            except BaseException as error:
                c.event("provider_response_publication",error)
                if failure is None:failure=error
            record["usage_unknown"]=record["usage"] is None
            try:self.receipts.append(c.write("model-call-%08d.json"%number,record,diagnostic=True))
            except BaseException as error:
                c.event("provider_call_publication",error)
                if failure is None:failure=error
        if failure is not None:raise failure
        c.check();return action,carried
    def process(self,body,deadline,record):
        c=self.c;p=None;selector=None;buffers={};eof=[];input_pending=bytearray(body)
        old=len(c.events);cap=self.config["limits"]["result_bytes"]
        child={"phase":"entered","original_deadline":deadline,"provider_hardware_usage":"unknown",
               "stdout_observed_bytes":0,"stderr_observed_bytes":0};record["process"]=child
        try:
            p=subprocess.Popen([self.config["python"]["path"],"-I","-S","-B",str(self.worker)],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,
                env={"PATH":"/usr/bin:/bin","LANG":"C.UTF-8","PYTHONDONTWRITEBYTECODE":"1"})
            child["pid"]=p.pid;selector=selectors.DefaultSelector()
            for stream in (p.stdin,p.stdout,p.stderr):os.set_blocking(stream.fileno(),False)
            selector.register(p.stdin,selectors.EVENT_WRITE)
            for stream in (p.stdout,p.stderr):buffers[stream]=bytearray();selector.register(stream,selectors.EVENT_READ)
            while selector.get_map():
                need(time.monotonic()<deadline,"original_provider_process_deadline")
                for key,_ in selector.select(min(.05,max(0,deadline-time.monotonic()))):
                    stream=key.fileobj
                    if stream is p.stdin:
                        try:n=os.write(stream.fileno(),input_pending[:65536])
                        except BlockingIOError:continue
                        need(n>0,"provider_stdin_short_write")
                        del input_pending[:n]
                        if not input_pending:selector.unregister(stream);stream.close()
                        continue
                    try:block=os.read(stream.fileno(),4096)
                    except BlockingIOError:continue
                    if not block:selector.unregister(stream);eof.append(stream);continue
                    bound=cap if stream is p.stdout else 4096
                    child[("stdout" if stream is p.stdout else "stderr")+"_observed_bytes"]+=len(block)
                    available=bound-len(buffers[stream]);buffers[stream].extend(block[:available])
                    need(len(block)<=available,"provider_process_stream_cap")
            p.wait(timeout=max(.001,deadline-time.monotonic()))
            need(p.returncode in (0,1),"provider_worker_abnormal_exit")
            need(c.group_absent(p),"provider_worker_group_remains")
            child["phase"]="natural_complete"
        except BaseException as error:c.event("provider_process",error);child["phase"]="failed"
        finally:
            raw=bytes(buffers.get(None if p is None else p.stdout,b""))
            record["_raw_stdout"]=raw
            for stream,label in (() if p is None else ((p.stdout,"stdout"),(p.stderr,"stderr"))):
                data=bytes(buffers.get(stream,b""));child[label+"_bytes"]=len(data)
                child[label+"_sha256"]=hashlib.sha256(data).hexdigest();child[label+"_eof"]=stream in eof
                if label=="stderr":child["stderr_base64"]=base64.b64encode(data).decode()
            c.close_process(p,selector,[] if p is None else [p.stdin,p.stdout,p.stderr],len(c.events)>old,child)
        if len(c.events)>old:raise c.first_error
        return raw
    def close(self):
        if self.closed:return
        self.closed=True
        c=self.c
        # No provider processes are intentionally retained across calls or people.
        if self.worker is not None:c.attempt("broker_worker_source_remove",self.worker.unlink)
        if self.root is not None:c.attempt("broker_source_directory_remove",self.root.rmdir)
        evidence={"schema":"neural006-provider-accounting-v1","close_attempted":True,
            "resources_released":not(self.root is not None and self.root.exists()),"sessions":self.sessions,
            "entered_calls":len(self.calls),"retained_call_receipts":len(self.receipts),
            "call_receipt_complete":len(self.calls)==len(self.receipts),"remote_cancellation_confirmed":False,
            "call_receipts":self.receipts,"computation_records":self.computations,
            "computation_receipts":self.computation_receipts,
            "computation_receipt_complete":len(self.computations)==len(self.computation_receipts),
            "nonrefundable_reservations":self.reserved,"known_provider_usage":self.known_usage,
            "has_unknown_usage":self.unknown_usage,"source_admission":self.admission,
            "provider_hardware":{"cpu_seconds":None,"peak_rss_bytes":None,"status":"unmeasured_external"},
            "pricing_policy":"operator-selected ceiling; reservations are not an invoice",
            "container_cpu_rss_equivalence":False,"original_attempt_deadline":c.end,"work_deadline":c.work_end}
        c.write("MODEL_BROKER_CLOSURE.json",evidence,diagnostic=True)

class BrokerActors(Actors):
    def __init__(self,*args,broker_config,broker_admission):
        super().__init__(*args)
        self.broker=HostBroker(self.custody,broker_config,broker_admission,self.sources)
    def candidate(self,mode,case,reference,model=None,training_context=None,vault=None):
        if mode=="frozen_program":return super().candidate(mode,case,reference,model,training_context,vault)
        need(mode=="adaptive_investigation","broker_only_investigator")
        mounts=[(self.programs[mode],"/candidate/program.py"),(self.core,"/protocol/core.R"),(self.sources["TASK.md"],"/protocol/TASK.md")]
        artifact=None
        if model is not None:
            need(vault is not None and training_context is not None,"issued_frozen_state_required")
            row=vault.resolve(model,mode,self.recipe,self.seeds[mode],digest(training_context))
            model=vault.describe(model,mode);mounts.append((row[4],"/input/model.bin"))
            artifact={"bytes":row[5],"sha256":row[6],"format":row[7],"training_fingerprint":row[3],
                      "recipe_sha256":row[1],"candidate_seed":row[2],"artifact_base64":base64.b64encode(row[4]).decode()}
        inner=CandidateSession(case,reference,self.custody.limits["tool_calls_per_case"],self.seeds[mode],model,training_context)
        return self.container(case,["python3","-I","-B","/candidate/program.py"],mounts,BrokerSession(inner,self.broker,artifact))
    def train_candidate(self,mode,training,reference_model,vault):
        if mode=="frozen_program":return super().train_candidate(mode,training,reference_model,vault)
        need(mode=="adaptive_investigation","broker_only_investigator")
        inner=TrainingSession(training,reference_model,vault,self.recipe,self.custody.limits["tool_calls_per_case"],
                              self.seeds[mode],self.custody.limits["model_artifact_bytes"])
        return self.container(training,["python3","-I","-B","/candidate/program.py"],
            [(self.programs[mode],"/candidate/program.py"),(self.core,"/protocol/core.R"),(self.sources["TASK.md"],"/protocol/TASK.md")],
            BrokerSession(inner,self.broker))
