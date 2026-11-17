"""Prospective inert controls only. Never dispatches Docker, a provider, or scientific data."""
import argparse,base64,hashlib,importlib.abc,importlib.util,json,os
from pathlib import Path
import sys,tempfile,time,types,unittest
from unittest import mock

def encoded(v):return (json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def load_sources(path,size,pin):
    raw=Path(path).read_bytes()
    assert len(raw)==size and sha(raw)==pin
    m=json.loads(raw);assert m["schema"]=="neural006-operative-source-v1" and len(m["files"])==15
    bodies={}
    for row in m["files"]:
        p=Path(row["path"]);b=p.read_bytes()
        assert p.is_absolute() and not p.is_symlink() and len(b)==row["bytes"] and sha(b)==row["sha256"]
        bodies[p.name]=b
    modules={Path(n).stem:n for n in bodies if n.endswith(".py") and n!="launch.py"}
    assert not set(modules)&set(sys.modules)
    class Loader(importlib.abc.Loader):
        def __init__(self,n):self.n=n
        def create_module(self,spec):return None
        def exec_module(self,mod):
            mod.__file__="<authenticated-inert-control:"+self.n+">"
            exec(compile(bodies[modules[self.n]],mod.__file__,"exec",dont_inherit=True),mod.__dict__)
    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self,name,path=None,target=None):
            return importlib.util.spec_from_loader(name,Loader(name)) if name in modules else None
    finder=Finder();sys.meta_path.insert(0,finder)
    try:
        return __import__("model_broker"),__import__("provider_worker"),__import__("custody"),bodies,__import__("candidate_relay")
    finally:sys.meta_path.remove(finder)

class MemoryCustody:
    def __init__(self):
        self.start=time.monotonic();self.end=self.start+60;self.work_end=self.end-5
        self.limits={"candidate_seconds_per_case":4,"per_file_bytes":16777216,"retained_bytes":100000000,"max_files":1000,"max_cases":100}
        self.publication_reserve=65536;self.written_bytes=0;self.files_reserved=0
        self.events=[];self.first_error=None;self.outputs={}
    def check(self,cleanup=False):
        if self.first_error is not None and not cleanup:raise self.first_error
        if time.monotonic()>self.end:raise ValueError("test_deadline")
    def event(self,phase,error):
        if self.first_error is None:self.first_error=error
        self.events.append({"phase":phase,"class":type(error).__name__})
    def write_bytes(self,name,body,diagnostic=False):
        assert name not in self.outputs
        self.outputs[name]=body;self.written_bytes+=len(body);self.files_reserved+=1
        return {"path":"/inert/"+name,"bytes":len(body),"sha256":sha(body)}
    def write(self,name,value,diagnostic=False):return self.write_bytes(name,encoded(value),diagnostic)
    def attempt(self,name,operation):
        try:return operation()
        except BaseException as e:self.event(name,e);return None

class InertInner:
    def __init__(self,event="case"):
        self.initial={"event":event,"candidate_seed":7};self.finished=False;self.value=None;self.received=[]
    def exchange(self,a):
        self.received.append(a)
        if "submit" in a or "trained" in a:
            self.finished=True;self.value={"inert":True};return {"event":"inert_terminal","feedback":None}
        return {"sequence":len(self.received),"response":{"inert_value":3},"response_sha256":"3"*64}

class InertOwner:
    def __init__(self,actions):
        self.c=MemoryCustody();self.config={"limits":{"calls_per_case":8,"compute_calls_per_case":8,
            "compute_seconds_per_call":2,"compute_source_bytes":131072,"compute_stdout_bytes":131072,"compute_stderr_bytes":65536}}
        self.reserved={"calls":0};self.computations=[];self.computation_receipts=[]
        self.sessions=[];self.actions=list(actions);self.requests=[]
    def generate(self,initial,history,carried,artifact,deadline,session,turn):
        self.reserved["calls"]+=1
        self.requests.append({"initial":initial,"history":list(history),"carried":list(carried),"artifact":artifact})
        return self.actions.pop(0),[{"type":"message","id":"inert-"+str(turn),"role":"assistant","status":"completed",
                                     "content":[{"type":"output_text","text":"INERT"}]}]

def fixture_broker():
    c=MemoryCustody();o=MB.HostBroker.__new__(MB.HostBroker)
    o.task_text="INERT exact source-owned TASK"
    o.c=c;o.closed=False;o.unknown_usage=False;o.sessions=[];o.calls=[];o.receipts=[];o.computations=[];o.computation_receipts=[]
    o.reserved={"calls":0,"tokens":0,"request_bytes":0,"response_bytes":0,"spend_microdollars":0}
    o.known_usage={"input_tokens":0,"output_tokens":0,"total_tokens":0}
    o.admission={"worker_sha256":"a"*64,"source_sha256":"b"*64,"identity":"c"*64,"qualification_sha256":"d"*64}
    o.config={"endpoint":MB.ENDPOINT,"model":"INERT-model-no-provider","parameters":{"max_output_tokens":10},
      "credential":{"path":"/NEVER-READ-INERT-CREDENTIAL","device":0,"inode":0,"uid":0,"mode":384,
                    "bytes":1,"mtime_ns":0,"ctime_ns":0},
      "token_bound":{"per_utf8_byte":1,"overhead_tokens":1},"prompt":"INERT control; no API execution",
      "pricing":{"currency":"USD","input_microdollars_per_million_tokens":1000000,
                 "output_microdollars_per_million_tokens":1000000},
      "limits":{"calls_per_case":8,"calls_total":4,"request_bytes":200000,"response_bytes":200000,
                "result_bytes":1500000,"input_tokens":1000,"output_tokens":10,"total_tokens_per_call":1010,
                "total_tokens":4040,"request_bytes_total":800000,"response_bytes_total":800000,
                "timeout_seconds":2,"spend_microdollars":1000000,"compute_calls_per_case":2,
                "compute_seconds_per_call":2,"compute_source_bytes":131072,"compute_stdout_bytes":131072,"compute_stderr_bytes":65536}}
    return o

def inert_result(body,record=None,**changes):
    if record is not None:record["process"]={"returncode":0,"inert":True}
    e=json.loads(body)
    v={"schema":"n006-provider-result-v1","request_id":e["request_id"],"envelope_sha256":sha(body),
       "bindings":e["config"]["bindings"],"model":e["config"]["model"],"status":"complete",
       "usage":{"input_tokens":5,"output_tokens":3,"total_tokens":8},"usage_unknown":False,
       "provider_status":"completed","output_text":'{"tool":"training_summary","arguments":{}}',
       "output_history":[{"type":"message","id":"inert","role":"assistant","status":"completed",
                         "content":[{"type":"output_text","text":"INERT"}]}]}
    v.update(changes);return encoded(v)

def call_broker(o):
    return o.generate({"event":"case","candidate_seed":7},[],[],None,o.c.work_end,"INERT-session",1)

class BrokerControls(unittest.TestCase):
    def session(self,actions=None):
        own=InertOwner(actions or [{"tool":"training_summary","arguments":{}},{"submit":{"inert":True}}])
        sess=MB.BrokerSession(InertInner(),own);sess.bind_deadline(own.c.work_end)
        return sess,own
    def send(self,s,kind,payload):
        return s.exchange(MB.frame(s.key,s.session_id,s.sequence+1,kind,payload,s.previous))
    def test_01_real_action_applies_only_after_matching_ack(self):
        s,o=self.session();a=self.send(s,"next_action",{});self.assertEqual(s.inner.received,[])
        self.send(s,"apply_action",a["payload"]);self.assertEqual(s.inner.received,[{"tool":"training_summary","arguments":{}}])
        b=self.send(s,"next_action",{});terminal=self.send(s,"apply_action",b["payload"])
        self.assertTrue(s.finished);self.assertEqual(terminal["kind"],"terminal")
    def test_02_wrong_mac_never_dispatches(self):
        s,o=self.session();a=MB.frame(s.key,s.session_id,1,"next_action",{},s.previous);a["mac"]="0"*64
        with self.assertRaises(ValueError):s.exchange(a)
        self.assertFalse(o.requests)
    def test_03_replay_never_calls_model_twice(self):
        s,o=self.session();a=MB.frame(s.key,s.session_id,1,"next_action",{},s.previous);s.exchange(a)
        with self.assertRaises(ValueError):s.exchange(a)
        self.assertEqual(len(o.requests),1)
    def test_04_wrong_sequence_refused(self):
        s,o=self.session()
        with self.assertRaises(ValueError):s.exchange(MB.frame(s.key,s.session_id,3,"next_action",{},s.previous))
        self.assertFalse(o.requests)
    def test_05_boolean_sequence_refused(self):
        s,o=self.session();a=MB.frame(s.key,s.session_id,True,"next_action",{},s.previous)
        with self.assertRaises(ValueError):s.exchange(a)
        self.assertFalse(o.requests)
    def test_06_candidate_context_injection_refused(self):
        s,o=self.session()
        with self.assertRaises(ValueError):self.send(s,"next_action",{"model":"substitute","messages":["leak"]})
        self.assertFalse(o.requests)
    def test_07_apply_without_model_refused(self):
        s,o=self.session()
        with self.assertRaises(ValueError):self.send(s,"apply_action",{"action_sha256":"0"*64})
        self.assertFalse(s.inner.received)
    def test_08_changed_action_digest_refused(self):
        s,o=self.session();self.send(s,"next_action",{})
        with self.assertRaises(ValueError):self.send(s,"apply_action",{"action_sha256":"0"*64})
        self.assertFalse(s.inner.received)
    def test_09_post_terminal_refused(self):
        s,o=self.session([{"submit":{"inert":True}}]);a=self.send(s,"next_action",{});self.send(s,"apply_action",a["payload"])
        with self.assertRaises(ValueError):self.send(s,"next_action",{})
        self.assertEqual(len(o.requests),1)
    def test_10_fresh_person_history(self):
        s,o=self.session();a=self.send(s,"next_action",{});self.send(s,"apply_action",a["payload"])
        other=MB.BrokerSession(InertInner(),o);other.bind_deadline(o.c.work_end);self.send(other,"next_action",{})
        self.assertEqual(o.requests[-1]["history"],[]);self.assertEqual(o.requests[-1]["carried"],[])
        self.assertNotEqual(other.key,s.key);self.assertNotEqual(other.session_id,s.session_id)
    def test_11_exact_frozen_artifact_enters_fresh_predict(self):
        o=InertOwner([{"submit":{"inert":True}}]);artifact={"sha256":"e"*64,"artifact_base64":"SU5FUlQ="}
        s=MB.BrokerSession(InertInner("predict"),o,artifact);s.bind_deadline(o.c.work_end);self.send(s,"next_action",{})
        self.assertEqual(o.requests[0]["artifact"],artifact)
    def test_12_frozen_program_never_uses_broker(self):
        o=MB.BrokerActors.__new__(MB.BrokerActors)
        with mock.patch.object(MB.Actors,"candidate",return_value="inert-fixed-program") as fixed:
            self.assertEqual(o.candidate("frozen_program",{},{}),"inert-fixed-program");fixed.assert_called_once()
    def test_13_failed_known_usage_is_retained_and_charged(self):
        o=fixture_broker();o.process=lambda b,d,r:inert_result(b,r,status="failed",provider_status="failed")
        with self.assertRaises(ValueError):call_broker(o)
        self.assertEqual(o.known_usage["total_tokens"],8);self.assertEqual(o.reserved["tokens"],1010)
        self.assertFalse(o.unknown_usage);self.assertEqual(len(o.receipts),1)
    def test_14_unknown_usage_stops_next_request(self):
        o=fixture_broker();count=[]
        def effect(b,d,r):count.append(1);return inert_result(b,r,status="failed",usage=None,usage_unknown=True)
        o.process=effect
        with self.assertRaises(ValueError):call_broker(o)
        with self.assertRaises(ValueError):call_broker(o)
        self.assertEqual(len(count),1);self.assertTrue(o.unknown_usage);self.assertEqual(o.reserved["calls"],1)
    def test_15_excess_usage_not_clipped(self):
        o=fixture_broker();o.process=lambda b,d,r:inert_result(b,r,usage={"input_tokens":2000,"output_tokens":3,"total_tokens":2003})
        with self.assertRaises(ValueError):call_broker(o)
        self.assertEqual(o.known_usage["total_tokens"],2003);self.assertEqual(o.reserved["tokens"],1010)
    def test_16_valid_usage_survives_process_failure(self):
        o=fixture_broker()
        def effect(b,d,r):r["_raw_stdout"]=inert_result(b,r);raise RuntimeError("INERT cleanup failure")
        o.process=effect
        with self.assertRaises(RuntimeError):call_broker(o)
        self.assertEqual(o.known_usage["total_tokens"],8);self.assertFalse(o.unknown_usage)
        self.assertTrue(o.c.outputs["model-response-00000001.json"])
    def test_17_caps_precede_next_dispatch(self):
        o=fixture_broker();o.config["limits"]["calls_total"]=1;count=[]
        def effect(b,d,r):count.append(1);return inert_result(b,r)
        o.process=effect;call_broker(o)
        with self.assertRaises(ValueError):call_broker(o)
        self.assertEqual(len(count),1);self.assertEqual(o.reserved["calls"],1)
    def test_18_failed_call_cost_not_refunded(self):
        o=fixture_broker();o.process=lambda b,d,r:inert_result(b,r,status="failed")
        with self.assertRaises(ValueError):call_broker(o)
        self.assertEqual(o.reserved["spend_microdollars"],1010)
        self.assertEqual(o.calls[0]["provider_hardware"]["cpu_seconds"],None)
    def test_19_provider_identity_mismatch_cannot_yield_action(self):
        o=fixture_broker();o.process=lambda b,d,r:inert_result(b,r,model="different-INERT")
        with self.assertRaises(ValueError):call_broker(o)
        self.assertEqual(o.known_usage["total_tokens"],8)
    def test_20_credential_not_in_candidate_opening(self):
        s,o=self.session()
        text=encoded(s.initial)
        self.assertNotIn(b"credential",text);self.assertNotIn(b"endpoint",text);self.assertNotIn(b"model",text)
    def test_21_wrong_reply_chain_refused(self):
        s,o=self.session()
        with self.assertRaises(ValueError):s.exchange(MB.frame(s.key,s.session_id,1,"next_action",{},"0"*64))
        self.assertFalse(o.requests)
    def test_22_extra_json_action_fields_fail_before_apply(self):
        s,o=self.session([{"tool":"training_summary","arguments":{},"endpoint":"bad"}])
        with self.assertRaises(ValueError):self.send(s,"next_action",{})
        self.assertFalse(s.inner.received)
    def test_23_training_does_not_accept_submit(self):
        o=InertOwner([{"submit":{}}]);s=MB.BrokerSession(InertInner("train_once"),o);s.bind_deadline(o.c.work_end)
        with self.assertRaises(ValueError):self.send(s,"next_action",{})
        self.assertFalse(s.inner.received)
    def test_24_predict_does_not_accept_retrain_artifact(self):
        o=InertOwner([{"trained":{}}]);s=MB.BrokerSession(InertInner("predict"),o);s.bind_deadline(o.c.work_end)
        with self.assertRaises(ValueError):self.send(s,"next_action",{})
        self.assertFalse(s.inner.received)

def worker_envelope():
    o=fixture_broker();prompt=o.config["prompt"];bind={"adapter_sha256":"a"*64,"source_sha256":"b"*64,
        "prompt_sha256":sha(prompt.encode()),"config_sha256":"c"*64,"qualification_sha256":"d"*64}
    config={"endpoint":PW.ENDPOINT,"model":"INERT-model-no-provider","parameters":{"max_output_tokens":10},
        "credential":o.config["credential"],"token_bound":{"model":"INERT-model-no-provider","source_sha256":"b"*64,
        "qualification_sha256":"d"*64,"per_utf8_byte":1,"overhead_tokens":1},
        "limits":{"request_bytes":200000,"response_bytes":200000,"result_bytes":1500000,
        "input_tokens":1000000,"output_tokens":10,"total_tokens":1000010,"timeout_seconds":1},"bindings":bind}
    return {"schema":"n006-provider-request-v1","request_id":"INERT-control","deadline":time.monotonic()+10,
        "config":config,"input":[{"role":"developer","content":prompt},{"role":"user","content":"INERT task"}]}

def provider_response(status="completed",model="INERT-model-no-provider"):
    return encoded({"object":"response","id":"resp-INERT","model":model,"status":status,
       "error":None,"incomplete_details":None,"usage":{"input_tokens":5,"output_tokens":3,"total_tokens":8,
       "input_tokens_details":{"cached_tokens":0},"output_tokens_details":{"reasoning_tokens":0}},
       "output":[{"type":"reasoning","id":"reason-INERT","encrypted_content":"INERT-encrypted"},
                 {"type":"message","id":"message-INERT","role":"assistant","status":"completed",
                  "content":[{"type":"output_text","text":'{"tool":"training_summary","arguments":{}}'}]}]})

class ProviderControls(unittest.TestCase):
    def run_inert(self,e,raw):
        def transport(body,key,config,deadline,observation,errors):
            observation.update(response_eof=True,response_status=200,request_attempted=True,
                               request_complete=True,connection_close_attempted=True,connection_closed=True,
                               response_close_attempted=True,response_closed=True)
            return raw
        with mock.patch.object(PW,"read_credential",return_value="INERT-not-a-key") as key, \
             mock.patch.object(PW,"post_once",side_effect=transport) as call:
            result,cap=PW.run(e,encoded(e))
            return result,key.call_count,call.call_count
    def test_25_complete_output_retains_encrypted_reasoning(self):
        r,k,n=self.run_inert(worker_envelope(),provider_response())
        self.assertEqual(r["status"],"complete");self.assertEqual(k,1);self.assertEqual(n,1)
        self.assertEqual(r["output_history"][0]["encrypted_content"],"INERT-encrypted")
        self.assertEqual(r["provider_hardware"]["cpu_seconds"],None)
    def test_26_failed_provider_usage_retained(self):
        r,k,n=self.run_inert(worker_envelope(),provider_response(status="failed"))
        self.assertEqual(r["status"],"failed");self.assertEqual(r["usage"]["total_tokens"],8)
    def test_27_model_mismatch_usage_retained(self):
        r,k,n=self.run_inert(worker_envelope(),provider_response(model="wrong-INERT"))
        self.assertEqual(r["status"],"failed");self.assertEqual(r["usage"]["total_tokens"],8)
    def test_28_token_bound_refuses_before_credential(self):
        e=worker_envelope();e["config"]["limits"]["input_tokens"]=1
        r,k,n=self.run_inert(e,provider_response())
        self.assertEqual(r["status"],"failed");self.assertEqual((k,n),(0,0))
    def test_29_prompt_identity_refuses_before_credential(self):
        e=worker_envelope();e["input"][0]["content"]="changed-INERT"
        r,k,n=self.run_inert(e,provider_response())
        self.assertEqual(r["status"],"failed");self.assertEqual((k,n),(0,0))
    def test_30_endpoint_refuses_before_credential(self):
        e=worker_envelope();e["config"]["endpoint"]={**PW.ENDPOINT,"host":"wrong.invalid"}
        r,k,n=self.run_inert(e,provider_response())
        self.assertEqual(r["status"],"failed");self.assertEqual((k,n),(0,0))
    def test_31_duplicate_provider_history_refused(self):
        e=worker_envelope();item=json.loads(provider_response())["output"][0];e["input"]+=[item,item]
        r,k,n=self.run_inert(e,provider_response())
        self.assertEqual(r["status"],"failed");self.assertEqual((k,n),(0,0))
    def test_32_original_expired_deadline_refuses_before_credential(self):
        e=worker_envelope();e["deadline"]=time.monotonic()-1
        r,k,n=self.run_inert(e,provider_response())
        self.assertEqual(r["status"],"failed");self.assertEqual((k,n),(0,0))


def admission_fixture():
    o=fixture_broker();c=o.c;c.read_log=[];c.read_members={}
    def add(path,body):
        c.read_members[path]=body
        return {"path":path,"bytes":len(body),"sha256":sha(body)}
    def read(path,size,pin):
        c.read_log.append(str(path));body=c.read_members[str(path)]
        if len(body)!=size or sha(body)!=pin:raise ValueError("INERT authenticated read mismatch")
        return body
    c.read=read
    sources={"provider_worker.py":b"INERT provider source; never executed","candidate_relay.py":b"INERT relay source"}
    cfg=o.config
    cfg["schema"]="neural006-host-openai-broker-v1";cfg["python"]=add("/inert/python",b"INERT executable descriptor")
    cfg["provider_hardware_policy"]="external_unknown_not_container_cpu_or_rss";cfg["limits"]["calls_per_case"]=2
    proof=add("/inert/token-proof",b"INERT proof fixture: no actual qualification")
    evidence={"schema":"neural006-input-token-bound-v1","model":cfg["model"],"source_manifest_sha256":"b"*64,
        **cfg["token_bound"],"request_schema":"OpenAI_Responses_full_request_utf8_v1",
        "accepted_upper_bound":True,"proof_record":proof}
    e=add("/inert/token-evidence.json",encoded(evidence))
    q={"schema":"neural006-broker-admission-v1","provider_identity_sha256":MB.config_identity(cfg),
       "source_manifest_sha256":"b"*64,"provider_worker_sha256":sha(sources["provider_worker.py"]),
       "model_id_is_immutable_snapshot":True,"live_requests_authorized":True,"credential_access_authorized":True,
       "token_bound_evidence":e,"source_review_sha256":"1"*64,"provider_hardware_policy":cfg["provider_hardware_policy"]}
    cfg["qualification"]=add("/inert/admission.json",encoded(q))
    return c,cfg,sources,{"adaptive_investigation":sources["candidate_relay.py"],"frozen_program":b"INERT fixed"}

class AdmissionAndScienceControls(unittest.TestCase):
    def test_33_admission_reads_actual_selected_proof(self):
        c,cfg,s,p=admission_fixture();a=MB.authenticate_broker(c,cfg,s,"b"*64,p)
        self.assertEqual(a["identity"],MB.config_identity(cfg));self.assertIn("/inert/token-proof",c.read_log)
    def test_34_changed_relay_refused_before_provider(self):
        c,cfg,s,p=admission_fixture();p["adaptive_investigation"]=b"changed"
        with self.assertRaises(ValueError):MB.authenticate_broker(c,cfg,s,"b"*64,p)
        self.assertNotIn(cfg["credential"]["path"],c.read_log)
    def test_35_changed_configuration_breaks_qualification(self):
        c,cfg,s,p=admission_fixture();cfg["prompt"]+="changed"
        with self.assertRaises(ValueError):MB.authenticate_broker(c,cfg,s,"b"*64,p)
        self.assertNotIn(cfg["credential"]["path"],c.read_log)
    def test_36_changed_proof_bytes_refused(self):
        c,cfg,s,p=admission_fixture();c.read_members["/inert/token-proof"]=b"changed"
        with self.assertRaises(ValueError):MB.authenticate_broker(c,cfg,s,"b"*64,p)
    def test_37_unselected_endpoint_refused_without_reads(self):
        c,cfg,s,p=admission_fixture();cfg["endpoint"]={**MB.ENDPOINT,"host":"wrong.invalid"}
        with self.assertRaises(ValueError):MB.authenticate_broker(c,cfg,s,"b"*64,p)
        self.assertEqual(c.read_log,[])
    def test_38_actual_candidate_session_tool_and_claim(self):
        protocol=sys.modules["protocol"]
        row={k:1.0 for k in protocol.FEATURES}
        train={**row,**{k:2.0 for k in protocol.TARGETS},"participant":"203","original_participant":"203","source_row":181}
        case={"schema":"neural006-case-v1","participant":"202","training":[train],
              "query":[{**row,"source_row":1}],"clusters":[{"fit_id":"203","original_participant":"203"}]}
        inner=MB.CandidateSession(case,{},1,7);o=InertOwner([{"tool":"training_summary","arguments":{}}])
        s=MB.BrokerSession(inner,o);s.bind_deadline(o.c.work_end)
        send=lambda k,p:s.exchange(MB.frame(s.key,s.session_id,s.sequence+1,k,p,s.previous))
        action=send("next_action",{});send("apply_action",action["payload"])
        reply=inner.session.history[0]
        report={"estimand":"INERT synthetic fixture","limitations":"No science/model inference",
                "alternative_explanations":"Fixture only","claims":[{"evidence_sequence":1,
                "response_sha256":reply["response_sha256"],"path":["training_rows"],"value":1}]}
        o.actions.append({"submit":{"status":"complete","predictions":[[1,0.1,0.2]],"investigation":report}})
        action=send("next_action",{});send("apply_action",action["payload"])
        self.assertTrue(inner.finished);self.assertEqual(inner.value["predictions"]["predictions"],[[1,0.1,0.2]])
    def vault_fixture(self):
        state=sys.modules["model_state"];c=MemoryCustody();c.limits["tool_calls_per_case"]=2;c.limits["model_artifact_bytes"]=1000
        training={"schema":"INERT-training","training":[],"query":[]};recipe="4"*64;seeds={"frozen_program":7,"adaptive_investigation":9}
        vault=state.ModelVault(c,recipe,MB.digest(training),seeds)
        body=b"INERT frozen33 artifact"
        token=vault.publish("adaptive_investigation",{"training_fingerprint":MB.digest(training),"candidate_seed":9,
            "body":body,"bytes":len(body),"sha256":sha(body),"format":"INERT-frozen"})
        a=MB.BrokerActors.__new__(MB.BrokerActors);a.custody=c;a.recipe=recipe;a.seeds=seeds
        a.programs={"adaptive_investigation":b"INERT-relay"};a.core=b"INERT";a.sources={"TASK.md":b"INERT"}
        a.broker=InertOwner([]);a.container=lambda case,argv,mounts,session:session
        return a,vault,token,training,body
    def test_39_actual_vault_bytes_and_lineage_reused(self):
        a,v,t,training,body=self.vault_fixture()
        case={"participant":"201","query":[],"training":[],"clusters":[]}
        s=a.candidate("adaptive_investigation",case,{},t,training,v)
        self.assertEqual(base64.b64decode(s.artifact["artifact_base64"]),body)
        self.assertEqual(s.artifact["training_fingerprint"],MB.digest(training))
        self.assertEqual(s.inner.initial["event"],"predict")
    def test_40_changed_training_identity_refused_before_actor(self):
        a,v,t,training,body=self.vault_fixture()
        with self.assertRaises(ValueError):a.candidate("adaptive_investigation",{}, {},t,{**training,"changed":True},v)
    def test_41_actual_training_session_freezes_exact_artifact(self):
        state=sys.modules["model_state"];training={"training":[],"query":[]}
        inner=state.TrainingSession(training,None,None,"4"*64,1,9,100)
        body=b"INERT once-trained"
        o=InertOwner([{"trained":{"training_fingerprint":MB.digest(training),"candidate_seed":9,
            "format":"INERT","artifact_base64":base64.b64encode(body).decode()}}])
        s=MB.BrokerSession(inner,o);s.bind_deadline(o.c.work_end)
        action=s.exchange(MB.frame(s.key,s.session_id,1,"next_action",{},s.previous))
        s.exchange(MB.frame(s.key,s.session_id,3,"apply_action",action["payload"],s.previous))
        self.assertTrue(s.finished);self.assertEqual(s.value["body"],body)
        self.assertFalse(inner.initial["reserved_queries_available"])
    def test_42_missing_worker_exit_status_is_not_success(self):
        o=fixture_broker()
        def effect(b,d,r):
            raw=inert_result(b,r);r.pop("process");return raw
        o.process=effect
        with self.assertRaises(ValueError):call_broker(o)
        self.assertEqual(o.known_usage["total_tokens"],8)


    def test_46_complete_provider_history_and_fresh_case(self):
        o=fixture_broker();captured=[]
        def effect(body,deadline,record):
            captured.append(json.loads(body));return inert_result(body,record)
        o.process=effect
        carried=[{"type":"reasoning","id":"reason-INERT","encrypted_content":"COMPLETE-INERT-REASONING"},
            {"type":"message","id":"assistant-INERT","role":"assistant","status":"completed",
             "content":[{"type":"output_text","text":"INERT prior exact action"}]},
            {"role":"user","content":'{"tool_or_terminal_reply":{"sequence":1,"response":{"inert":true}}}'}]
        initial={"event":"case","candidate_seed":7}
        o.generate(initial,[],carried,None,o.c.work_end,"first-INERT",2)
        o.generate(initial,[],[],None,o.c.work_end,"fresh-INERT",1)
        self.assertEqual(json.loads(captured[0]["input"][1]["content"])["task_markdown"],o.task_text)
        self.assertEqual(captured[0]["input"][2:],carried)
        self.assertEqual(captured[0]["input"][2]["encrypted_content"],"COMPLETE-INERT-REASONING")
        self.assertEqual(len(captured[1]["input"]),2)

INERT_CHILD_COMPLETE_EXIT1 = r"""
import json,hashlib,sys
b=sys.stdin.buffer.read();e=json.loads(b)
v={"schema":"n006-provider-result-v1","request_id":e["request_id"],
"envelope_sha256":hashlib.sha256(b).hexdigest(),"bindings":e["config"]["bindings"],
"model":e["config"]["model"],"status":"complete","usage":{"input_tokens":5,"output_tokens":3,"total_tokens":8},
"usage_unknown":False,"provider_status":"completed","output_text":'{"tool":"training_summary","arguments":{}}',
"output_history":[]}
sys.stderr.write("INERT partial stderr without newline");sys.stderr.flush()
sys.stdout.write(json.dumps(v)+"\n");sys.stdout.flush();sys.exit(1)
"""
class OwnedWorkerControls(unittest.TestCase):
    def run_child(self,script,timeout=3):
        # Explicit inert child Python source only. No provider/client/task execution.
        o=fixture_broker();c=o.c
        c.group_absent=types.MethodType(CUSTODY.Custody.group_absent,c)
        c.close_process=types.MethodType(CUSTODY.Custody.close_process,c)
        c.end=time.monotonic()+5;c.work_end=time.monotonic()+timeout
        with tempfile.TemporaryDirectory(prefix="n006-inert-provider-control-") as path:
            child=Path(path)/"inert.py";child.write_text(script)
            o.worker=child;o.config["python"]={"path":sys.executable}
            with self.assertRaises(BaseException):call_broker(o)
        return o
    def test_43_complete_output_exit1_refuses_after_settling_usage(self):
        o=self.run_child(INERT_CHILD_COMPLETE_EXIT1)
        self.assertEqual(o.known_usage["total_tokens"],8);self.assertEqual(o.calls[0]["process"]["returncode"],1)
        self.assertEqual(base64.b64decode(o.calls[0]["process"]["stderr_base64"]),b"INERT partial stderr without newline")
        self.assertTrue(o.calls[0]["process"]["group_absent"]);self.assertEqual(o.reserved["tokens"],1010)
    def test_44_stderr_only_failure_retained(self):
        o=self.run_child('import sys\nsys.stdin.buffer.read()\nsys.stderr.write("INERT terminal failure")\nsys.exit(1)\n')
        self.assertTrue(o.unknown_usage);self.assertEqual(o.reserved["tokens"],1010)
        self.assertEqual(base64.b64decode(o.calls[0]["process"]["stderr_base64"]),b"INERT terminal failure")
        self.assertTrue(o.calls[0]["process"]["group_absent"])
    def test_45_original_deadline_kills_and_reaps_inert_worker(self):
        o=self.run_child('import sys,time\nsys.stdin.buffer.read()\nsys.stderr.write("INERT before deadline");sys.stderr.flush()\ntime.sleep(30)\n',timeout=0.1)
        self.assertTrue(o.unknown_usage);self.assertTrue(o.calls[0]["process"]["group_absent"])
        self.assertIsNotNone(o.calls[0]["process"]["returncode"]);self.assertEqual(o.reserved["tokens"],1010)
        self.assertIn("stderr_base64",o.calls[0]["process"])


    def test_47_stderr_cap_crossing_preserves_exact_bounded_prefix(self):
        o=self.run_child('import sys,os\nsys.stdin.buffer.read()\nos.write(2,b"X"*8192)\nsys.exit(1)\n')
        process=o.calls[0]["process"]
        self.assertEqual(base64.b64decode(process["stderr_base64"]),b"X"*4096)
        self.assertGreater(process["stderr_observed_bytes"],process["stderr_bytes"])
        self.assertEqual(process["stderr_bytes"],4096);self.assertTrue(process["group_absent"])
        self.assertEqual(o.calls[0]["status"],"failed");self.assertTrue(o.unknown_usage)


class ComputeControls(unittest.TestCase):
    def limits(self,seconds=2,stdout=131072):
        return {"seconds":seconds,"source_bytes":131072,"stdout_bytes":stdout,"stderr_bytes":65536}
    def report(self,action,stdout=b"",status="complete"):
        return {"schema":"neural006-candidate-computation-v1","action_sha256":MB.digest(action),
            "language":action["compute"]["language"],"source_sha256":sha(action["compute"]["source"].encode()),
            "status":status,"returncode":0 if status=="complete" else 1,
            "stdout_base64":base64.b64encode(stdout).decode(),"stderr_base64":"",
            "stdout_observed_bytes":len(stdout),"stderr_observed_bytes":0,
            "stdout_retained_bytes":len(stdout),"stderr_retained_bytes":0,"stdout_sha256":sha(stdout),
            "stderr_sha256":sha(b""),"stdout_eof":True,"stderr_eof":True,"group_absent":True,
            "elapsed_seconds":0.01,"errors":[],"observation_trust":"candidate_reported_untrusted"}
    def send(self,s,k,p):
        return s.exchange(MB.frame(s.key,s.session_id,s.sequence+1,k,p,s.previous))
    def session(self,action):
        o=InertOwner([action]);s=MB.BrokerSession(InertInner(),o);s.bind_deadline(o.c.work_end)
        return s,o
    def actual_composition(self,source):
        # Actual original scientific session + host Actor pipe owner + actual
        # relay. The model and Docker effect leaves are explicitly inert.
        pr=sys.modules["protocol"];row={k:1.0 for k in pr.FEATURES}
        train={**row,**{k:2.0 for k in pr.TARGETS},"participant":"203","original_participant":"203","source_row":181}
        case={"schema":"neural006-case-v1","participant":"202","training":[train],
            "query":[{**row,"source_row":1}],"clusters":[{"fit_id":"203","original_participant":"203"}]}
        report={"estimand":"INERT fixture","limitations":"No scientific/model result",
            "alternative_explanations":"Literal controls only","claims":[]}
        actions=[{"compute":{"language":"python","source":source}},
            {"submit":{"status":"complete","predictions":[[1,0.1,0.2]],"investigation":report}}]
        owner=InertOwner(actions);c=owner.c
        c.group_absent=types.MethodType(CUSTODY.Custody.group_absent,c)
        c.close_process=types.MethodType(CUSTODY.Custody.close_process,c)
        session=MB.BrokerSession(MB.CandidateSession(case,{},2,7),owner)
        actor=MB.Actors.__new__(MB.Actors);actor.custody=c;actor.records=[];actor.docker="/INERT-never-executed"
        with tempfile.TemporaryDirectory(prefix="n006-inert-relay-composition-") as directory:
            wrapper=Path(directory)/"literal_relay_control.py"
            wrapper.write_text("body="+repr(BODIES["candidate_relay.py"])+"\n"+
                "ns={'__name__':'inert_authenticated_relay'}\nexec(compile(body,'<inert-authenticated-relay>','exec'),ns)\n"+
                "ns['CANDIDATE_CWD']="+repr(directory)+"\nraise SystemExit(ns['main']())\n")
            original=MB.subprocess.Popen
            def inert_docker_leaf(argv,**kwargs):
                self.assertEqual(argv,[actor.docker,"start","-a","-i","INERT-container"])
                kwargs["env"]={"PATH":"/usr/bin:/bin","LANG":"C.UTF-8"}
                return original([sys.executable,"-I","-S","-B",str(wrapper)],**kwargs)
            with mock.patch.object(MB.subprocess,"Popen",side_effect=inert_docker_leaf):
                value=actor.attach("INERT-container",4,session)
        self.assertTrue(actor.records[-1]["group_absent"]);self.assertTrue(session.finished)
        self.assertEqual(owner.computations[0]["candidate_observation_authority"],False)
        return value,owner,actor
    def test_48_actual_actor_relay_computation_and_scientific_submission(self):
        value,o,a=self.actual_composition('print("INERT computation")')
        self.assertEqual(value["predictions"]["predictions"],[[1,0.1,0.2]])
        self.assertEqual(len(o.computation_receipts),1)
        record=json.loads(o.c.outputs["model-compute-00000001.json"])
        self.assertEqual(base64.b64decode(record["candidate_report"]["stdout_base64"]),b"INERT computation\n")
    def test_49_changed_code_digest_never_executes(self):
        action={"compute":{"language":"python","source":"print('INERT')"}}
        with mock.patch.object(REL.subprocess,"Popen",side_effect=AssertionError("must not execute")) as spawn:
            with self.assertRaises(ValueError):
                REL.compute({"action_sha256":"0"*64,"action":action,"limits":self.limits(),"host_remaining_seconds":2})
        spawn.assert_not_called()
    def test_50_analysis_failure_is_bounded_untrusted_feedback(self):
        action={"compute":{"language":"python","source":"import sys\nprint('INERT diagnostic')\nsys.exit(1)\n"}}
        with tempfile.TemporaryDirectory(prefix="n006-inert-compute-failure-") as d, mock.patch.object(REL,"CANDIDATE_CWD",d):
            result=REL.run_compute(action,self.limits(),2)
        self.assertEqual(result["status"],"analysis_failed");self.assertTrue(result["group_absent"])
        s,o=self.session(action);self.send(s,"next_action",{})
        reply=self.send(s,"compute_result",result)
        self.assertEqual(reply["kind"],"compute_feedback");self.assertFalse(s.finished)
        self.assertEqual(len(s.inner.received),0)
    def test_51_local_timeout_stays_failure_and_group_is_closed(self):
        action={"compute":{"language":"python","source":"import time\ntime.sleep(30)\n"}}
        with tempfile.TemporaryDirectory(prefix="n006-inert-compute-timeout-") as d, mock.patch.object(REL,"CANDIDATE_CWD",d):
            result=REL.run_compute(action,self.limits(seconds=.3),.3)
        self.assertEqual(result["status"],"infrastructure_failed");self.assertTrue(result["group_absent"])
        s,o=self.session(action);self.send(s,"next_action",{})
        with self.assertRaises(ValueError):self.send(s,"compute_result",result)
        self.assertEqual(len(o.computation_receipts),1)
    def test_52_compute_stdout_cap_retains_exact_prefix(self):
        action={"compute":{"language":"python","source":"import os\nos.write(1,b'X'*512)\n"}}
        with tempfile.TemporaryDirectory(prefix="n006-inert-compute-overflow-") as d, mock.patch.object(REL,"CANDIDATE_CWD",d):
            r=REL.run_compute(action,self.limits(stdout=16),2)
        self.assertEqual(r["status"],"infrastructure_failed")
        self.assertEqual(base64.b64decode(r["stdout_base64"]),b"X"*16)
        self.assertGreater(r["stdout_observed_bytes"],r["stdout_retained_bytes"]);self.assertTrue(r["group_absent"])
    def test_53_r_argv_is_fixed_without_running_r(self):
        action={"compute":{"language":"r","source":'cat("INERT")'}}
        with mock.patch.object(REL.subprocess,"Popen",side_effect=RuntimeError("INERT do not run R")) as spawn:
            r=REL.run_compute(action,self.limits(),2)
        self.assertEqual(spawn.call_args.args[0][:2],["/usr/bin/Rscript","--vanilla"])
        self.assertEqual(r["status"],"infrastructure_failed")
        self.assertFalse(spawn.call_args.kwargs.get("shell",False))
        self.assertEqual(spawn.call_args.kwargs["env"],REL.CHILD_ENV)
    def test_54_compute_source_cap_refuses_before_relay(self):
        action={"compute":{"language":"python","source":"X"*131073}}
        s,o=self.session(action)
        with self.assertRaises(ValueError):self.send(s,"next_action",{})
        self.assertEqual(o.computations,[])
    def test_55_candidate_cannot_assert_trusted_compute_observations(self):
        action={"compute":{"language":"python","source":"print('INERT')"}}
        s,o=self.session(action);self.send(s,"next_action",{});r=self.report(action);r["observation_trust"]="trusted"
        with self.assertRaises(ValueError):self.send(s,"compute_result",r)
        self.assertEqual(o.computation_receipts,[])
    def test_56_compute_result_does_not_become_reference_evidence(self):
        action={"compute":{"language":"python","source":"print('INERT')"}}
        s,o=self.session(action);self.send(s,"next_action",{});self.send(s,"compute_result",self.report(action))
        self.assertEqual(s.inner.received,[]);self.assertEqual(len(s.history),1)
        self.assertEqual(s.history[0]["reply"]["observation_trust"],"candidate_reported_untrusted")
    def test_57_large_frame_crosses_old_limit_in_actual_actor_loop(self):
        value,o,a=self.actual_composition("import os\nos.write(1,b'X'*100000)\n")
        record=json.loads(o.c.outputs["model-compute-00000001.json"])
        self.assertEqual(record["candidate_report"]["stdout_retained_bytes"],100000)
        self.assertGreater(a.records[-1]["stdout_bytes"],131072)
        self.assertEqual(value["predictions"]["predictions"],[[1,0.1,0.2]])

def main():
    global MB,PW,CUSTODY,BODIES,REL
    assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
    p=argparse.ArgumentParser();p.add_argument("--manifest",required=True);p.add_argument("--manifest-bytes",type=int,required=True)
    p.add_argument("--manifest-sha256",required=True);a=p.parse_args()
    MB,PW,CUSTODY,BODIES,REL=load_sources(a.manifest,a.manifest_bytes,a.manifest_sha256)
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(BrokerControls),
                             unittest.defaultTestLoader.loadTestsFromTestCase(ProviderControls),
                             unittest.defaultTestLoader.loadTestsFromTestCase(AdmissionAndScienceControls),
                             unittest.defaultTestLoader.loadTestsFromTestCase(OwnedWorkerControls),
                             unittest.defaultTestLoader.loadTestsFromTestCase(ComputeControls)])
    assert suite.countTestCases()==57
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"schema":"n006-inert-engineering-controls-v1","tests_run":result.testsRun,
        "failures":len(result.failures),"errors":len(result.errors),"all_passed":result.wasSuccessful(),
        "model_calls":0,"provider_network_calls":0,"scientific_runs":0,"actual_model_qualification":False}))
    return 0 if result.wasSuccessful() else 1
if __name__=="__main__":raise SystemExit(main())
