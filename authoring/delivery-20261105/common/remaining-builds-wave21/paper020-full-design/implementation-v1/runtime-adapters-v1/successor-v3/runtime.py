"""Concrete composition of admitted source, immutable transport and workers.

There is no finished-fit, prediction, grading or scientific executor callback.
The scientific dispatcher remains the reviewed V2 dispatcher. External images,
credentials, source admissions and physical accounting must be independently
qualified before this module can construct a production runtime.
"""
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
from .basis import basis, EXPECTED, authenticate_adapters
from .wire import (WireLimits, ImmutableStore, canonical, parse, sha, need,
                   encode, bundle_bytes, decode_bundle, _read, _write)
from .mat_source import OriginalMatSource, Limits as SourceLimits
from .process_control import (Qualification, ExecutablePin, Mount, Limits,
    LaunchSpec, SubprocessCommandTransport, DockerProcessAdapter, IndependentDockerObserver)
from .authority import Authority
from .provider import ResponsesClient, author_source

def _qualification(value):
    v=dict(value)
    for k in ("docker","accountant","guardian","worker"): v[k]=ExecutablePin(**v[k])
    return Qualification(**v)

def _candidate_model(source,parameters):
    fingerprint=basis("dispatcher").artifact_fingerprint
    core={"source":source,"source_digest":sha(source.encode()),"parameters":parameters}
    return {**core,"model_digest":fingerprint(core)}

def _check_candidate_model(model):
    need(type(model) is dict and set(model)=={"source","source_digest","parameters","model_digest"},"Exact source/parameter model required")
    need(model["source_digest"]==sha(model["source"].encode()), "Source model identity differs")
    core={k:v for k,v in model.items() if k!="model_digest"}
    need(basis("dispatcher").artifact_fingerprint(core)==model["model_digest"],"Sealed model parameter identity differs")
    return model

class Runtime:
    def __init__(self,authority,source,store,images,*,contract,admission,credential_fd=None):
        self.authority=authority;self.source=source;self.store=store;self.images=images
        self.credential_fd=credential_fd;self.document=authority.document
        self.contract=contract;self.admission=admission
        self.wire_limits=WireLimits(**self.document["wire_limits"])
        self.phase=None;self.binding=None;self.contexts={};self.policies={};self.pending={}
        self.jobs=[];self.failure=False;self.provider_receipts=[];self.monitor=None
        self._views=self._validate_views(self.document["views"])
    def _validate_views(self,views):
        need(set(views)=={a+"/"+t for a in ("A","B","reference") for t in ("native","prediction")},"All six exact source views required")
        for track in ("native","prediction"):
            left=views["A/"+track];right=views["B/"+track]
            need(all(x["scientific_role"] in ("paper","common_clarification","interface") for x in left),"A view includes author/evaluator/private material")
            common=[x for x in right if x["scientific_role"]!="author_code"]
            need(left==common,"A/B common source views differ")
            author=[x for x in right if x["scientific_role"]=="author_code"]
            need(len(author)==13 and {x["sha256"] for x in author}==set(self.document["original_code_sha256"]),
                 "B view requires exactly all 13 admitted original code/readme files")
        return views
    def begin(self,phase,binding):
        self.authority.begin(phase,binding);self.phase=phase;self.binding=binding
    def _phase(self,binding):
        self.authority._clock();need(self.phase is not None and binding==self.binding,"Runtime called outside its current bound phase")
        return self.phase
    def new_isolated_context(self,descriptor,binding):
        self._phase(binding);context=uuid.uuid4().hex
        self.contexts[context]=json.loads(canonical(descriptor));self.authority.contexts[context]=self.contexts[context]
        return context
    def _view(self,actor,track): return self._views[actor+"/"+track]
    def _source_view_text(self,actor,track):
        parts=[]
        for f in self._view(actor,track):
            raw=_read(Path(f["host_path"]),f["bytes"])
            need(len(raw)==f["bytes"] and sha(raw)==f["sha256"],"Source view changed before exposure")
            # Source-view admission permits UTF-8 text only; PDF extraction is separately pinned.
            parts.append(f["scientific_role"]+"\n"+raw.decode("utf-8","strict"))
        text="\n\n".join(parts)
        need(len(text.encode())<=self.document["provider"]["request_bytes"],"Complete source view exceeds provider budget")
        return text
    def commit_policy(self,actor,track,binding):
        self._phase(binding);key=(actor,track)
        need(key not in self.policies,"Repeated policy commitment")
        if actor=="reference":
            policy={"kind":"reviewed_reference_portfolio","source":EXPECTED,"track":track}
        else:
            policy=self.document["candidate_policies"][actor][track]
            need(policy["mode"] in ("compiled","investigate") and policy["provider_model"]==self.document["provider"]["model"],"Explicit common provider policy required")
            need(policy==self.document["candidate_policies"]["A"][track],"A/B policy/resource mode differs")
        self.policies[key]=policy
        return {"policy_digest":sha(canonical(policy)),"source_view_digest":sha(canonical(self._view(actor,track)))}
    def pre_admitted_native_schemas(self,admission_digest,implementation_digest):
        need(admission_digest==self.document["admission_digest"] and implementation_digest==EXPECTED,"Native schema identity differs")
        value=self.document["native_schemas"]
        schemas={tuple(x["key"]):x["schema"] for x in value}
        need(set(schemas)==basis("native_scoring").native_keys() and len(schemas)==len(value),"All 336 unique pre-admitted schemas required")
        need(basis("native_scoring").native_schemas_digest(schemas)==self.document["native_schemas_digest"],"Native schema digest differs")
        return schemas
    def reproduction_packet(self,phase,context,admission_digest):
        need(admission_digest==self.document["admission_digest"],"Native admission differs")
        cap=self.authority.source_token("native",context=context,configuration=phase["configuration"])
        return self.source.native_packet(phase,context=context,capability=cap)
    def read_training_rows(self,context,kind,case,rowids,binding):
        self._phase(binding)
        cap=self.authority.source_token("training",context=context,configuration=case,row_ids=tuple(rowids))
        return self.source.training_rows(context,kind,case,rowids,capability=cap)
    def release_query_features(self,context,seal_digest,binding):
        self._phase(binding);self.authority.release(context,seal_digest)
    def read_query_features(self,context,case,rowids,seal_digest,binding):
        self._phase(binding)
        descriptor=self.contexts[context]
        assignment=basis("splits").make_outer_assignment(self.admission["rows"])
        view=basis("splits").fold_view(self.admission["rows"],assignment,descriptor["outer_fold"],descriptor["regime"])
        expected=[r["row_id"] for r in view["queries"] if r["configuration"]==case]
        need(list(rowids)==expected,"Query must include complete admitted held support")
        cap=self.authority.source_token("query_features",context=context,configuration=case,row_ids=tuple(rowids),seal=seal_digest)
        return self.source.query_features(context,case,rowids,seal_digest,capability=cap)
    def store_immutable(self,kind,value,context,binding):
        self._phase(binding);need(context in self.contexts,"Unknown immutable context")
        return self.store.put(kind,value,context,binding)
    def load_immutable(self,handle,context): return self.store.get(handle,context)
    def _bundle_file(self,directory,name,value):
        manifest,blobs=encode(value,self.wire_limits)
        raw=bundle_bytes(manifest,blobs);path=directory/name;_write(path,raw)
        return path,raw
    def _run(self,operation,packet,context,binding,*,source=None,model=None,model_digest=None):
        phase=self._phase(binding);descriptor=self.contexts[context]
        actor=descriptor["actor"];track=descriptor["track"]
        role="native" if operation=="literal_native" else "reference" if actor=="reference" else "candidate"
        launcher,observer=self.images[role];q=launcher.q
        directory=self.store.root/("job-"+uuid.uuid4().hex);directory.mkdir(mode=0o700)
        path,raw=self._bundle_file(directory,"packet.wire",packet)
        mounts=[Mount("input",str(path),"/paper020-view/packet.wire",sha(raw),len(raw))]
        job={"schema":"paper020_isolated_job_v1","operation":operation,"packet_file":"/paper020-view/packet.wire",
             "wire_limits":dataclasses.asdict(self.wire_limits),"phase":phase,"origin_ns":self.document["origin_ns"],
             "deadline_ns":self.document["deadline_ns"],"implementation_digest":EXPECTED}
        if source is not None:
            job.update(source=source,source_digest=sha(source.encode()))
        if model is not None:
            path,rawmodel=self._bundle_file(directory,"model.wire",model)
            mounts.append(Mount("model",str(path),"/paper020-view/model.wire",sha(rawmodel),len(rawmodel)))
            job["model_file"]="/paper020-view/model.wire"
        view=self._view(actor,track)
        if operation=="literal_native":
            view=self.document["native_release_view"]
            need(len(view)==43,"Literal native worker requires all 43 original files")
            job["native_envelope"]=self.document["native_envelope"]
        for item in view:
            mounts.append(Mount("source",item["host_path"],item["container_path"],item["sha256"],item["bytes"]))
        # Pin a source manifest even where a trusted reference needs no article text.
        source_manifest=canonical({"view":view,"image":q.image,"implementation_digest":EXPECTED})
        _write(directory/"source.json",source_manifest)
        mounts.append(Mount("source",str(directory/"source.json"),"/paper020-view/source.json",sha(source_manifest),len(source_manifest)))
        jobraw=canonical(job);_write(directory/"job.json",jobraw)
        mounts.append(Mount("request",str(directory/"job.json"),"/paper020-view/job.json",sha(jobraw),len(jobraw)))
        # Canonical fit-packet identity is distinct from byte-level mounted input identity.
        semantic=(basis("dispatcher").artifact_fingerprint(packet) if phase["kind"]=="fit" else sha(raw))
        spec=LaunchSpec(phase["id"],context,binding,EXPECTED,semantic,model_digest,
            self.document["origin_ns"],self.document["deadline_ns"],
            (q.python_path,"-I","-B",q.worker.path,"--job","/paper020-view/job.json","--output-root","/scratch/output"),
            tuple(mounts),Limits(**self.document["process_limits"][role]))
        # Preserve the exact original reservation before dispatch, including on
        # launch/closure failure. This operator-only file is never mounted in a
        # candidate view and never refunds or replaces observed counters.
        _write(directory/"reservation.json",canonical(dataclasses.asdict(spec)))
        os.chmod(directory,0o500)
        handle=None
        try:
            handle=launcher.launch(spec)
            closure=observer.close(handle)
            self.jobs.append((context,phase["id"],operation,closure))
            if not closure.natural_complete:
                # Failure evidence never enters a candidate/native scoring slot.
                # It remains private and retains the actual nonzero process state.
                try: failed=decode_bundle(closure.payload,self.wire_limits) if closure.payload else {"status":"no_observed_payload"}
                except (ValueError,TypeError,KeyError):
                    failed={"status":"invalid_failed_payload","raw_payload":closure.payload}
                self.store.put("native_capture_evidence",{"failure":failed,"closure":dataclasses.asdict(closure),
                    "reservation":dataclasses.asdict(spec)},context,binding)
            need(closure.natural_complete and closure.all_descendants_closed and closure.exit_code==0,
                 "Worker did not naturally close under original deadline")
            result=decode_bundle(closure.payload,self.wire_limits)
            self.authority._clock()
            self.pending[(context,phase["id"])]={"closure":closure,"result":result,"input_digest":semantic,
                "operation":operation,"mounts":tuple(mounts),"source_digest":sha(source.encode()) if source else EXPECTED}
            return result
        except BaseException:
            self.failure=True
            # No forced cleanup can create success; process layer owns any future cleanup.
            raise
    def run_reference(self,name,fixed_source_callable,packet,context,binding,implementation_digest):
        need(implementation_digest==EXPECTED and basis("dispatcher").KERNELS.get(name) is fixed_source_callable,
             "Reference callable/source substituted")
        if name=="frozen_reference_predict":
            return self._run(name,packet,context,binding,model=packet["sealed"],model_digest=packet["observed_fit_digest"])
        return self._run(name,packet,context,binding)
    def literal_native_capture(self,phase,context,binding,implementation_digest):
        need(implementation_digest==EXPECTED,"Literal native implementation differs")
        packet=self.reproduction_packet(phase,context,self.document["admission_digest"])
        captured=self._run("literal_native",packet,context,binding)
        need(type(captured) is dict and set(captured)=={"record","raw_capture","instrumentation"}
             and type(captured["raw_capture"]) is bytes and captured["raw_capture"],"Complete original native workspace evidence required")
        receipt=self.store.put("native_capture_evidence",captured,context,binding)
        self.pending[(context,phase["id"])]["native_evidence_store"]=receipt
        return captured["record"]
    def _author(self,context,packet,binding,operation):
        descriptor=self.contexts[context];actor=descriptor["actor"];track=descriptor["track"]
        policy=self.policies[(actor,track)]
        client=ResponsesClient(self.authority,actor,track,self.credential_fd)
        # Each context is independent. No native/history/other-fold transcript is reused.
        prompt=(self._source_view_text(actor,track)+"\n\n"+self.document["candidate_interface"]+
                "\nCurrent operation: "+operation+"\nAdmitted context:\n"+canonical(descriptor).decode()+
                "\nOnly training data or the permitted native packet are available to probe(packet). "
                "Return source via submit_source. Prediction query responses are never available.")
        def probe(source):
            need(policy["mode"]=="investigate","Compiled policy cannot investigate numerical cases")
            return self._run("probe",packet,context,binding,source=source)
        try: return author_source(client,prompt,probe)
        finally: self.provider_receipts.extend(client.receipts)
    def candidate_reproduction(self,phase,packet,context,binding):
        source=self._author(context,packet,binding,"reproduce")
        return self._run("reproduce",packet,context,binding,source=source)
    def candidate_fit(self,phase,packet,context,binding):
        source=self._author(context,packet,binding,"fit")
        parameters=self._run("fit",packet,context,binding,source=source)
        model=_candidate_model(source,parameters)
        stored=self.store_immutable("candidate_fit",model,context,binding)
        self.pending[(context,phase["id"])]["actual_model_digest"]=model["model_digest"]
        return {**stored,"model_digest":model["model_digest"]}
    def candidate_predict(self,phase,stored,query,model_digest,context,binding):
        model=_check_candidate_model(self.store.get(stored["handle"],context))
        need(model["model_digest"]==model_digest,"Inference model differs from closed fit")
        result=self._run("predict",query,context,binding,source=model["source"],model=model["parameters"],model_digest=model_digest)
        need(_check_candidate_model(self.store.get(stored["handle"],context))["model_digest"]==model_digest,"Model mutated during inference")
        return result
    def load_protected_targets(self,admission_digest,binding):
        self._phase(binding);need(admission_digest==self.document["admission_digest"],"Target admission differs")
        cap=self.authority.source_token("protected_targets")
        prediction=self.source.protected_targets(capability=cap)
        protected=self.document["protected_reproduction"]
        need(protected["path"] in self.document["protected_host_paths"],"Protected reproduction path lacks custody")
        raw=_read(Path(protected["path"]),protected["bytes"])
        need(len(raw)==protected["bytes"] and sha(raw)==protected["sha256"],"Independent protected reproduction changed")
        reproduction=decode_bundle(raw,self.wire_limits)
        self.authority._clock()
        return {"prediction":prediction,"reproduction":reproduction}

class Monitor:
    """Semantic joins plus independent actual worker/host observation."""
    def __init__(self,runtime,host):
        self.runtime=runtime;self.authority=runtime.authority;self.host=host;self.fit_receipts={};self.closed_phases={}
        self.whole_observation=None;self.phase_totals={k:0 for k in ("read_bytes","write_bytes","retained_bytes","live_bytes")}
    def _observed(self,observation,*,include_workers=True):
        need(observation.scope=="live_host_phase_children" and observation.host_alive is True
             and observation.external_host_natural_exit_required is True and observation.phase_observation_complete is True
             and observation.owned_children_closed is True and not observation.failures,
             "Complete independently observed live-host phase/children evidence required")
        resources={}
        for key in self.phase_totals:
            value=observation.resources[key]
            need(type(value) is int and value>=0,"Unobserved host resource counter")
            workers=[r[key] for r in observation.worker_resources.values()] if include_workers else []
            need(all(type(v) is int and v>=0 for v in workers),"Unobserved worker resource counter")
            # _run closes every worker before another can start; source dispatch
            # is sequential. Host peak plus the largest worker peak is a safe
            # upper bound. Summing all historical worker peaks would invent
            # concurrency and can reject the complete programme incorrectly.
            resources[key]=value+(max(workers,default=0) if key=="live_bytes" else sum(workers))
        return resources
    def close_fit(self,context,case,stored,model_digest,input_digest,binding):
        phase=self.runtime._phase(binding);p=self.runtime.pending[(context,phase["id"])]
        value=self.runtime.store.get(stored["handle"],context)
        if self.runtime.contexts[context]["actor"]=="reference": actual=value["model_digest"]
        else: actual=_check_candidate_model(value)["model_digest"]
        e=p["closure"]
        need(actual==model_digest and p["input_digest"]==input_digest and e.input_digest==input_digest
             and e.binding_digest==binding and e.natural_complete and e.all_descendants_closed and e.exit_code==0,
             "Actual fit output/input/source/process join failed")
        receipt={"natural_complete":True,"all_descendants_closed":True,"exit_code":0,"model_digest":actual,
                 "input_digest":input_digest,"binding_digest":binding,"container_id":e.container_id,
                 "output_digest":e.payload_digest,"source_digest":p["source_digest"],"finished_ns":e.finished_ns,
                 "evidence_digests":e.evidence_digests}
        digest=basis("strict").digest(receipt)
        self.fit_receipts[phase["id"]]=(digest,actual)
        self.authority.fit_closed(context,case,actual,digest)
        return receipt
    def observe_phase(self,phase,result,origin,deadline,binding,implementation_digest):
        need(implementation_digest==EXPECTED,"Observer implementation differs")
        artifact=result.get("artifact",{})
        receipts=[j[3] for j in self.runtime.jobs if j[1]==phase["id"]]
        host=self.host.close(phase,binding,origin,deadline,basis("strict").digest(artifact),worker_evidence=tuple(receipts))
        resources=self._observed(host)
        if phase["kind"]=="independent_full_process_and_resource_closure":
            need(self.whole_observation is not None,"Whole-host observation missing")
            # Whole-close is a nonconsuming diagnostic snapshot. This phase's
            # actual close delta already includes its observation overhead.
        okay=not self.runtime.failure and all(e.natural_complete and e.all_descendants_closed and e.exit_code==0
            and e.binding_digest==binding and e.origin_ns==origin and e.deadline_ns==deadline for e in receipts)
        computational=phase["kind"] in ("fit","predict","reproduction")
        if computational: need(receipts,"Scientific phase lacks actual isolated execution")
        # These are phase-level completion fields required by V2, explicitly not
        # a claim that the still-live host has naturally exited. Terminal observer
        # evidence is required before a final installed execution is accepted.
        out={**resources,"phase_id":phase["id"],"binding_digest":binding,"origin_ns":origin,
             "implementation_digest":EXPECTED,"natural_complete":okay,
             "all_descendants_closed":okay,"exit_code":0 if okay else None,
             "finished_ns":host.finished_ns,"observation_scope":host.scope,
             "host_alive":True,"external_host_natural_exit_required":True,
             "host_observation_digest":host.commitment()}
        if computational:
            out.update(view_isolation_verified=all(e.view_isolation_verified for e in receipts),
                       source_seal_unchanged=all(e.source_seal_unchanged for e in receipts),
                       protected_grading_targets_absent=self._targets_absent(phase))
        if phase["kind"]=="fit":
            receipt,model=self.fit_receipts[phase["id"]]
            out.update(fit_receipt_digest=receipt,model_digest_after_fit=model)
        if phase["kind"]=="predict":
            out["model_digest_after_inference"]=artifact["model_digest"]
            need(all(e.model_digest==artifact["model_digest"] for e in receipts),
                 "Independent inference model mount differs")
        need(origin<=out["finished_ns"]<deadline,"Final host closure exceeded original deadline")
        self.closed_phases[phase["id"]]=out
        for key,value in resources.items():
            self.phase_totals[key]=max(self.phase_totals[key],value) if key=="live_bytes" else self.phase_totals[key]+value
        return out
    def _targets_absent(self,phase):
        # All original source data is prohibited from prediction mounts. Native
        # contexts legitimately receive original responses but never grade keys.
        candidates=[p for (context,pid),p in self.runtime.pending.items() if pid==phase["id"]]
        protected=set(self.authority.document["protected_host_paths"])
        return bool(candidates) and all(m.host_path not in protected for p in candidates for m in p["mounts"])
    def close_all(self,artifacts,origin,deadline,binding):
        need(not self.runtime.failure,"Any failed process prevents full closure")
        required=basis("programme").build_plan(self.runtime.contract)["phases"]
        expected={p["id"] for p in required if p["kind"] in ("fit","predict","reproduction")}
        actual={pid for pid,r in self.closed_phases.items() if r["natural_complete"] is True}
        need(expected<=actual,"Every original scientific phase must be independently closed")
        observation=self.host.close_all(artifacts,origin,deadline,binding)
        cumulative=self._observed(observation,include_workers=True)
        need(all(observation.output_bundle_digests.get(k)==v for k,v in artifacts.items()),"Actual complete output seals differ")
        profile=self.authority.document["profile"]
        for key,total in cumulative.items():
            # The whole checkpoint is a cumulative host snapshot plus every
            # distinct raw worker partition exactly once. Earlier per-phase
            # totals already contain host costs and must not be added again.
            need(total<=profile[key],"Whole-study physical resource profile exceeded")
        self.whole_observation=observation
        closure={**artifacts,"all_outputs_validated":True,"resources_passed":True,"natural_complete":True,
                 "all_descendants_closed":True,"observation_scope":observation.scope,"host_alive":True,
                 "external_host_natural_exit_required":True,"host_observation_digest":observation.commitment()}
        self.authority.closed=closure;return closure

class BoundDispatcher:
    def __init__(self,dispatcher,runtime,monitor):
        self.dispatcher=dispatcher;self.runtime=runtime;self.monitor=monitor
    def __call__(self,phase,parents,origin,deadline,binding):
        self.runtime.begin(phase,binding);self.monitor.host.start(phase,binding,origin,deadline)
        return self.dispatcher(phase,parents,origin,deadline,binding)
    def observe(self,*args): return self.dispatcher.observe(*args)

def construct(envelope,public_key,contract,admission,mapping,*,credential_fd=None):
    """Only production constructor. No authentic files/processes before authority."""
    authority=Authority(envelope,public_key)
    authenticate_adapters(authority.document)
    plan=basis("programme").build_plan(contract)
    need(plan["programme_digest"]==authority.document["programme_digest"] and len(plan["phases"])==23786,
         "Exact full programme required before original source access")
    need(basis("strict").digest(admission)==authority.document["admission_digest"]
         and sha(canonical(mapping))==authority.document["mapping_digest"],"Signed source admission differs")
    store=ImmutableStore(authority.document["store_root"],WireLimits(**authority.document["wire_limits"]),authority,authority.token("store"))
    source=OriginalMatSource.open(authority.document["source_root"],contract,admission,mapping,authority=authority,
        capability=authority.source_token("source_open",root=authority.document["source_root"]),limits=SourceLimits(**authority.document["source_limits"]))
    images={}
    for role in ("candidate","reference","native"):
        q=_qualification(authority.document["images"][role])
        launchtransport=SubprocessCommandTransport(q,authority.process_qualification)
        observetransport=SubprocessCommandTransport(q,authority.process_qualification)
        launcher=DockerProcessAdapter(q,launchtransport,authority.process_qualification)
        observer=IndependentDockerObserver(q,observetransport,authority.process_qualification,launcher)
        images[role]=(launcher,observer)
    from .host_observer import HostObserver
    host=HostObserver.from_authority(authority)
    runtime=Runtime(authority,source,store,images,contract=contract,admission=admission,credential_fd=credential_fd)
    monitor=Monitor(runtime,host);runtime.monitor=monitor
    dispatcher=basis("dispatcher")._ScientificDispatcher(contract,admission,runtime,monitor,
        admission_digest=authority.document["admission_digest"],implementation_digest=EXPECTED)
    return BoundDispatcher(dispatcher,runtime,monitor)
