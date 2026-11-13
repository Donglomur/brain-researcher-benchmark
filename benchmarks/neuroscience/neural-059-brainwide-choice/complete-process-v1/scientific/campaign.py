"""Actual source-component composition; no generic benchmark activation or provider authority."""
import time
import resource
from copy import deepcopy
from pathlib import Path
from .contracts import need, pin, canonical, CONDITIONS, STATUS, check_prepared, identity
from .io import OwnedDirectory, Journal
from .controller import PanelController
from .validation import ValidationPanel
from .lifecycle import FIELDS, zero

def measured_call(call, *, input_value, source_evidence):
    """Measure this trusted process; tokens/tools require the fixed boundary's own record."""
    start=time.monotonic(); cpu=resource.getrusage(resource.RUSAGE_SELF)
    transferred=len(canonical(input_value))
    try:
        value=call()
    except BaseException as error:
        end=resource.getrusage(resource.RUSAGE_SELF)
        error.n059_work={"wall_seconds":time.monotonic()-start,
            "cpu_seconds":(end.ru_utime+end.ru_stime)-(cpu.ru_utime+cpu.ru_stime),
            "read_bytes":transferred,"write_bytes":0,"tool_calls":0,"fit_calls":0,
            "provider_tokens":0}
        error.n059_work_scope={"source":deepcopy(source_evidence),
            "returned_output_extent_unknown":True,"external_costs_unknown":True}
        raise
    end=resource.getrusage(resource.RUSAGE_SELF)
    return value,{"wall_seconds":time.monotonic()-start,
        "cpu_seconds":(end.ru_utime+end.ru_stime)-(cpu.ru_utime+cpu.ru_stime),
        "read_bytes":transferred,"write_bytes":len(canonical(value)),
        "tool_calls":0,"fit_calls":0,"provider_tokens":0}

class CalibrationViews:
    """Fresh separate session x F/I x condition roots; never all sessions in an actor root."""
    def __init__(self, path, sessions, members, project_case, frozen_F_sources, max_bytes):
        check_prepared(sessions,members)
        need(set(frozen_F_sources)==set(CONDITIONS) and all(type(x) is bytes and x
             for x in frozen_F_sources.values()),"actual global F source bodies before values")
        self.parent=OwnedDirectory(path,max_bytes)
        self.records=[];self.actor_commits={};self.max_bytes=max_bytes
        self.source_pins={c:pin(b) for c,b in frozen_F_sources.items()}
        self.total=0;self.poisoned=False;self.children={}
        try:
            for session in sessions:
                sid=session["session_id"]
                sid_name=pin(sid)["sha256"][:24]
                for arm in ("F","I"):
                    for condition in CONDITIONS:
                        childpath=self.parent.path/(arm+"-"+condition+"-"+sid_name)
                        with OwnedDirectory(childpath,max_bytes) as child:
                            self.children[(sid,arm,condition)]={"path":str(childpath),
                                "identity":child.root_stamp}
                            if arm=="F":
                                self._write(child,"frozen_source.txt",frozen_F_sources[condition])
                            splits={split:[project_case(deepcopy(c),condition,include_label=True)
                                for c in session["cases"] if c["split"]==split]
                                for split in ("train","val")}
                            body=canonical({"status":STATUS,"arm":arm,"condition":condition,
                                "session_id":sid,"calibration":splits,"future_query_files":False,
                                "F_source_precedes_values":self.source_pins[condition]})
                            published=self._write(child,"calibration.json",body)
                            self.records.append({"session_id":sid,"arm":arm,"condition":condition,
                                "directory":str(childpath),"calibration":published})
            manifest=canonical({"status":STATUS,"views":self.records,
                "actor_mount_isolation_qualified":False})
            self.total+=len(manifest);need(self.total<=max_bytes,"complete view manifest allowance")
            self.parent.write("VIEW_MANIFEST.json",manifest)
        except BaseException:
            self.poisoned=True;self.close();raise

    def _write(self,child,name,body):
        self.total+=len(body)
        need(self.total<=self.max_bytes,"complete attempted calibration write budget")
        return child.write(name,body)

    def commit_actor(self, session_id, arm, condition, source_body, config_body, learned_state_body):
        key=(session_id,arm,condition)
        need(not self.poisoned and key in self.children and key not in self.actor_commits,
             "one source/config/state freeze per session/arm/condition")
        need(all(type(b) is bytes and b for b in (source_body,config_body,learned_state_body)),
             "actual actor source/config/state bytes")
        child_info=self.children[key]
        try:
            self.parent.check()
            with OwnedDirectory.attach(child_info["path"],self.max_bytes,child_info["identity"]) as child:
                if arm=="F":
                    need(pin(source_body)==self.source_pins[condition],"unchanged F source before calibration")
                    source=pin(child.read_exact("frozen_source.txt",self.source_pins[condition]))
                else:source=self._write(child,"selected_source.txt",source_body)
                captured={"source":source,"configuration":self._write(child,"selected_config.txt",config_body),
                          "state":self._write(child,"selected_state.txt",learned_state_body)}
                need(captured=={"source":pin(source_body),"configuration":pin(config_body),
                                "state":pin(learned_state_body)},"actual durable actor bodies before held route")
                self.actor_commits[key]=captured
            return deepcopy(captured)
        except BaseException:
            self.poisoned=True;raise

    def close(self):
        self.parent.close()

def calibration(session,condition,project_case):
    return tuple([project_case(deepcopy(c),condition,include_label=True)
                  for c in session["cases"] if c["split"]==split]
                 for split in ("train","val"))

def fit_validation_panel(session,conditions,runtime,reference,project_case,journal,*,records):
    """Train every candidate; commit chronological full validation panels; then select/refit."""
    need(type(records) is list and not records,"fresh caller-owned session fit records")
    panel=ValidationPanel(session,conditions,journal,project_case);stages={};models={}
    sid=session["session_id"]
    try:
        for condition in conditions:
            train=[project_case(deepcopy(c),condition,include_label=True) for c in session["cases"] if c["split"]=="train"]
            for family in ("L","H"):
                entry={"session_id":sid,"condition":condition,"family":family,"grid":{},
                       "validation_observations":[],"selection":{},"refit":{},"work":{}}
                records.append(entry)
                start=time.monotonic();cpu=resource.getrusage(resource.RUSAGE_SELF)
                try:
                    stage=reference.stage_grid(family,train,runtime,session_id=sid,condition=condition,record=entry["grid"])
                    panel.register(stage);stages[(family,condition)]=(stage,train,entry)
                finally:
                    end=resource.getrusage(resource.RUSAGE_SELF)
                    entry["work"]["train_candidates"]={"wall_seconds":time.monotonic()-start,
                        "cpu_seconds":end.ru_utime+end.ru_stime-cpu.ru_utime-cpu.ru_stime,
                        "known_input_bytes":len(canonical(train)),"known_record_bytes":len(canonical(entry["grid"]))}
        while panel.next_case() is not None:
            for family,condition in sorted(stages):
                stage,train,entry=stages[(family,condition)];observation={}
                entry["validation_observations"].append(observation)
                view=panel.current_view(stage);start=time.monotonic();cpu=resource.getrusage(resource.RUSAGE_SELF)
                try:
                    reference.predict_validation_case(stage,view,runtime,panel_gate=panel,record=observation)
                finally:
                    end=resource.getrusage(resource.RUSAGE_SELF)
                    observation["own_process_work"]={"wall_seconds":time.monotonic()-start,
                        "cpu_seconds":end.ru_utime+end.ru_stime-cpu.ru_utime-cpu.ru_stime,
                        "known_view_bytes":len(canonical(view)),"known_record_bytes_before_timing":len(canonical(observation))}
            panel.commit_case()
        panel.seal()
        for family,condition in sorted(stages):
            stage,train,entry=stages[(family,condition)];released=panel.released(stage)
            start=time.monotonic();cpu=resource.getrusage(resource.RUSAGE_SELF)
            try:
                selected=reference.select_grid(stage,released["labels"],released["transcript"],runtime,
                    panel_gate=panel,record=entry["selection"])
                model=reference.refit_selected(selected,train,released["labelled_views"],runtime,
                    session_id=sid,condition=condition,record=entry["refit"])
                models[(condition,family)]=model
            finally:
                end=resource.getrusage(resource.RUSAGE_SELF)
                entry["work"]["selection_refit"]={"wall_seconds":time.monotonic()-start,
                    "cpu_seconds":end.ru_utime+end.ru_stime-cpu.ru_utime-cpu.ru_stime,
                    "known_input_bytes":len(canonical(released)),"known_record_bytes":len(canonical(entry["refit"]))}
                entry["work"]["scope"]="own-process clocks/known serialized operands; native threads/peak/provider costs unqualified"
        return models
    except BaseException as error:
        panel.failed={"type":type(error).__name__,"error":str(error),"position":panel.position}
        raise

def fit_references(sessions,members,runtime_factory,reference,project_case,*,validation_journal,records=None):
    check_prepared(sessions,members)
    models={};runtimes={};records=[] if records is None else records
    need(type(records) is list and not records,"fresh retained reference records")
    for session in sessions:
        sid=session["session_id"]
        runtime=runtime_factory(reference.shape_from_prepared(session));runtimes[sid]=runtime
        train_labels=[c["y"] for c in session["cases"] if c["split"]=="train"]
        # The prior's final train+val estimate is computed only after the validation seal below.
        def prior(labels):
            return {**reference.prior(labels),"status":"available"} if labels else {
                "status":"unavailable","error":"empty fitting support","qualification":STATUS,"fit_attempted":False}
        prior_record={"session_id":sid,"family":"prior","train":prior(train_labels),"refit":None}
        records.append(prior_record);session_records=[]
        holder={"session_id":sid,"complete_panel_records":session_records,"runtime_inference_records":runtime.inference_records}
        records.append(holder)
        fitted=fit_validation_panel(session,CONDITIONS,runtime,reference,project_case,validation_journal,records=session_records)
        val_labels=[c["y"] for c in session["cases"] if c["split"]=="val"]
        prior_record["refit"]=prior(train_labels+val_labels)
        for condition in CONDITIONS:
            models[(sid,condition,"prior")]=deepcopy(prior_record["refit"])
            for family in ("L","H"):models[(sid,condition,family)]=fitted[(condition,family)]
    return models,runtimes,records

def method_registry(sessions,reference,models,actor_commitments):
    """Reference states and external actor captures precede all held observations."""
    methods=[]
    for family in ("L","H","prior"):
        commitments=[]
        for s in sessions:
            for condition in CONDITIONS:
                if family=="prior":
                    c={"status":models[(s["session_id"],condition,family)].get("status"),"config_identity":pin({"family":"Laplace_prior"}),
                       "parameter_identity":pin(models[(s["session_id"],condition,family)])}
                else:
                    c=reference.model_commitment(models[(s["session_id"],condition,family)])
                need(c["status"]=="available","complete final reference states required")
                commitments.append({"session_id":s["session_id"],"condition":condition,
                    "config_identity":c["config_identity"],"parameter_identity":c["parameter_identity"]})
        methods.append({"method_id":family,"kind":"prior" if family=="prior" else "reference","arm":"R",
            "method_source_identity":reference.source_identity(),"commitments":commitments})
    for actor in actor_commitments:
        need(actor["kind"]=="actor" and actor["arm"] in ("F","I"),"actual actor commitment")
        methods.append(deepcopy(actor))
    need({m["arm"] for m in methods if m["kind"]=="actor"}=={"F","I"},"both actor arms")
    return methods

def predict_and_grade(sessions,members,methods,models,runtimes,reference,project_case,
                      actor_respond,external_complete,output_root,max_output_bytes,score_panel,
                      ledger=None):
    """Actual shared barrier. Test calls must name inert provider/closure leaves."""
    records=[]
    with OwnedDirectory(output_root,max_output_bytes) as directory:
        journal=Journal(directory,"predictions.jsonl",max_output_bytes)
        controller=PanelController(sessions,members,methods,project_case,journal.append)
        try:
            while True:
                request=controller.next_case()
                if request is None:break
                responses=[];sid=request["session_id"]
                for method in methods:
                    for condition in CONDITIONS:
                        view=deepcopy(request["views"][condition])
                        if method["kind"] in ("reference","prior"):
                            if method["method_id"]=="prior":
                                probability=models[(sid,condition,"prior")]["probability_left"]
                            else:
                                probability=reference.predict(models[(sid,condition,method["method_id"])],
                                                              [view],runtimes[sid])[0]
                        else:
                            call=lambda:actor_respond(method["method_id"],method["arm"],sid,condition,view)
                            try:
                                probability,work=measured_call(call,input_value=view,
                                    source_evidence=method["method_source_identity"])
                            except BaseException as error:
                                if ledger is not None and hasattr(error,"n059_work"):
                                    ledger.charge(sid,condition,method["arm"],"failed_work",
                                        error.n059_work,evidence=error.n059_work_scope,failed=True)
                                raise
                            if ledger is not None:
                                ledger.charge(sid,condition,method["arm"],"inference",work,
                                    evidence={"scope":"trusted process own wall/CPU and serialized view/return",
                                              "provider_tokens_tools_native_subprocesses":"unmeasured",
                                              "qualification":False})
                        responses.append({"method_id":method["method_id"],"arm":method["arm"],
                            "condition":condition,"case_id":request["case_id"],"p":probability})
                controller.commit(responses)
            journal_identity=journal.seal()
            outside=external_complete()
            completion=controller.finish(outside)
            directory.write("COMPLETION.json",canonical({**completion,"journal":journal_identity}))
            directory.write("REFERENCE_INFERENCE.json",canonical({sid:rt.inference_records
                            for sid,rt in runtimes.items()}))
            prepared,captured,expected=controller.captured_scoring_operands()
            grade=score_panel(prepared,captured,expected_methods=expected)
            directory.write("GRADE.json",canonical(grade))
            return {"status":STATUS,"completion":completion,"journal":journal_identity,
                    "grade":grade,"lifecycle":ledger.report() if ledger else None,
                    "all_gates_unqualified":True}
        except BaseException as error:
            failure={"status":"failed","error_type":type(error).__name__,"error":str(error),
                "controller":controller.failure,"committed_cases":len(controller.committed),
                "journal_attempted_bytes":journal.total,"journal_extent_unknown":journal.poisoned,
                "scientific_qualification":False,
                "reference_inference_records":{sid:rt.inference_records for sid,rt in runtimes.items()}}
            try:
                directory.write("FAILURE.json",canonical(failure))
            except BaseException as secondary:
                error.add_note("Failure retention also failed: "+repr(secondary))
            raise
        finally:
            journal.close()
