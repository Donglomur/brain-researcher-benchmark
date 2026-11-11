"""Full participant/reference FIT -> immutable state -> current-case INFER producer.
The object is trusted fixed scheduling code. No candidate modules are imported.
Scientific preparation can be replaced only by explicitly engineering-only test
providers; production entry constructs ProductionServices itself.
"""
import copy,time,secrets,resource
from pathlib import Path
from .io import *
from .process import Process
from .oci import OCIBackend
from .products import capture,state,probabilities
from .programme import copy_source
from .splits import token

class ProductionServices:
    engineering=False
    def partition(self,panel,job,key):
        from .splits import partition
        return partition(panel,job,key)
    def public_view(self,partition,identity):
        from .features import public_rows
        return public_rows(partition,identity)
    def backend(self,profile,ledger,source,state_root):return OCIBackend(profile,ledger,source,state_root)

class Engine:
    def __init__(self,root,authority,ledger,programme,reference_programme,services=None):
        self.authority=authority;self.ledger=ledger;self.programme=programme;self.reference=reference_programme;self.services=services or ProductionServices();self.key=secrets.token_bytes(32);self.ordinal=0;self.attempts=[];self.current_request=None;self.current_chain_view_bytes=0
        ledger.guard();self.root=path_guard(root);need(not self.root.exists(),"fresh_campaign_root");self.report_cap=authority.review["whole_campaign_reservation"]["report_bytes"];need(type(self.report_cap)is int and self.report_cap>0,"positive_campaign_report_capacity");ledger.reserve_bytes(self.report_cap*2,"success/failure full campaign closure slots");ledger.guard();self.root.mkdir(parents=True);self.sealed=False;self.parent_cpu_start=time.process_time();self.initial_charged_CPU=ledger.cpu
    def allocate(self,name):
        self.ledger.guard();self.ordinal+=1;out=below(self.root,f"{self.ordinal:06d}-{name}");need(not out.exists(),"fresh_allocation");return out
    def view_file(self,root,name,body):
        raw=encode(body);cap=self.authority.review["whole_campaign_reservation"].get("view_bytes_per_chain");need(cap is None and self.services.engineering or type(cap)is int and self.current_chain_view_bytes+len(raw)<=cap,"chain_view_reservation");self.current_chain_view_bytes+=len(raw);self.ledger.reserve_bytes(len(raw),"training/query/view materialization");return write(below(root,name),raw)
    def launch(self,j,phase,programme,view_root,request,prior_state=None,entry=None):
        self.ledger.guard();need(programme["manifest"].get("mode",j["identity"]["mode"])==j["identity"]["mode"],"frozen_programme_mode_mismatch");self.current_request=copy.deepcopy(request);source=self.allocate("source");copy_source(programme,source,self.ledger);directory=self.allocate("job");job={"id":j["id"]+"-"+phase,"identity":j["identity"],"source_pin":{"bytes":programme["source_bytes"],"sha256":digest(programme["files"])},"directory":str(directory),"limits":copy.deepcopy(j["limits"]),"engineering":self.services.engineering,"view_root":str(view_root),"entry":entry or programme["manifest"]["entry"][1]}
        backend=self.services.backend(self.authority.review["OCI_profile"],self.ledger,source,None if prior_state is None else prior_state["root"]);process=Process(job,self.ledger,backend);receipt=process.run(request);self.attempts.append({"job":job,"request":request,"receipt":receipt});process.require_success();dest=self.allocate("captured");captured=capture(job,receipt,dest,self.ledger,self.services.engineering);return captured,receipt,job
    def freeze_query_census(self,plan,reference_jobs,panel):
        """All expected opaque queries are issuer-frozen before any worker sees data."""
        need(not self.attempts,'census_before_first_exposure')
        for j in plan['jobs']+reference_jobs:
            if j.get('source_disposition')=='required_unscorable_secondary_context':j['query_ids']=[];j['training_census_sha256']=None;continue
            self.ledger.guard();part=self.services.partition(panel,j,self.key);need(len(part['query_ids'])==len(set(part['query_ids'])) and len(part['train_ids'])==len(set(part['train_ids'])) and not set(part['query_ids'])&set(part['train_ids']),'complete_disjoint_issuer_census');j['query_ids']=list(part['query_ids']);j['training_census_sha256']=digest(part['train_ids'])
        plan['query_census_frozen_before_first_exposure']=True
        write(self.root/'FROZEN_QUERY_CENSUS.json',{'plan':plan,'reference_plan':reference_jobs},self.ledger)
    def chain(self,j,panel,programme):
        self.ledger.guard();self.current_chain_view_bytes=0;partition=self.services.partition(panel,j,self.key)
        if 'query_ids'in j:need(partition['query_ids']==j['query_ids'] and digest(partition['train_ids'])==j['training_census_sha256'],'frozen_query_training_census')
        view=self.services.public_view(partition,j["identity"]);viewroot=self.allocate("views");self.ledger.guard();viewroot.mkdir();training={"train":copy.deepcopy(view["train"]),"identity":j["identity"],"information_set":"offline_case_local"}
        # Only opaque per-job training groups are shared with arbitrary learners.
        for row,z in zip(training["train"],partition["train"]):
            r=z["sentence"];row["person_group"]=token(self.key,j["id"],"training_person",r["person"]);row["item_group"]=token(self.key,j["id"],"training_item",r["text"])
        if j["identity"]["role"] in ("reference","control"):training.update(raw_training=partition["train"],J=panel["J"])
        training_pin=self.view_file(viewroot,"training.json",training)
        fit_request={"phase":"FIT","identity":j["identity"],"training_path":"/view/training.json","training_pin":{**training_pin,"path":"/view/training.json"},"query_released":False,"output_contract":"fit_complete+state_files+analysis_trace","remaining_deadline_monotonic":self.ledger.spec["deadline_monotonic"],"information_set":"offline_case_local"}
        fit_product,fit_receipt,fit_job=self.launch(j,"FIT",programme,viewroot,fit_request);sealed=state(fit_product,j["limits"]["output_bytes"],lambda:self.ledger.guard(closing=True))
        # Query is materialized only after actual FIT completion and immutable state capture.
        query_root=self.allocate("query-view");self.ledger.guard();query_root.mkdir();query={"query":view["query"],"information_set":"offline_case_local","identity":j["identity"]};query_pin=self.view_file(query_root,"query.json",query)
        train_copy=read(training_pin["path"],training_pin["bytes"],training_pin,self.ledger.guard);cap=self.authority.review["whole_campaign_reservation"].get("view_bytes_per_chain");need(cap is None and self.services.engineering or type(cap)is int and self.current_chain_view_bytes+len(train_copy)<=cap,"chain_view_reservation");self.current_chain_view_bytes+=len(train_copy);self.ledger.reserve_bytes(len(train_copy),"INFER permitted training copy");write(query_root/"training.json",train_copy)
        request={"phase":"INFER","identity":j["identity"],"state_sha256":sealed["state_sha256"],"state_root":"/state","state_files":sealed["files"],"query_ids":partition["query_ids"],"query_path":"/view/query.json","query_pin":{**query_pin,"path":"/view/query.json"},"training_path":"/view/training.json","information_set":"offline_case_local","remaining_deadline_monotonic":self.ledger.spec["deadline_monotonic"]}
        if j["identity"]["role"] in ("reference","control"):
            d=next(x for x in sealed["files"] if x["path"]=="reference-state.pkl");request["trusted_reference_state_pin"]={**d,"path":"/state/reference-state.pkl"}
        product,infer_receipt,infer_job=self.launch(j,"INFER",programme,query_root,request,sealed);probabilities(product,request,j["limits"]["output_bytes"],lambda:self.ledger.guard(closing=True))
        record={"job_id":j["id"],"identity":j["identity"],"fit":fit_receipt,"fit_request":fit_request,"state":sealed,"infer":infer_receipt,"product":product,"request":request}
        target_rows=[]
        from .panel import text_id
        for rid,z in zip(partition["query_ids"],partition["query"]):
            r=z["sentence"];target_rows.append({"id":rid,"person":token(self.key,"person",r["person"]),"item":text_id(r["text"]),"word_index":z["word_index"],"label":int(r["condition"]=="TSR"),"repetition_ordinal":r.get("repetition_ordinal"),"block":r.get("block"),"duration_seconds":r.get("duration_seconds"),"window_duration_ms":z.get("window",{}).get("duration_ms")})
        record["control_observations"]=view.get("protected_control_observations",{});record["support_dispositions_sha256"]=digest(partition.get("dispositions",[]));record["support_dispositions"]=partition.get("dispositions",[]);return record,target_rows
    def run(self,plan,reference_jobs,panel):
        need(not self.sealed,"campaign_already_closed");self.freeze_query_census(plan,reference_jobs,panel);alljobs=[(j,self.programme) for j in plan["jobs"]]+[(j,self.reference) for j in reference_jobs];records=[];refs=[];targets={};notstarted=[];error=None;failed_job=None;unavailable=[];prediction_unavailable=[]
        for k,(j,programme) in enumerate(alljobs):
            if j.get('source_disposition')=='required_unscorable_secondary_context':
                need(j['identity']['task']=='NEURAL-086' and j['identity']['context']!='FFD','primary_source_unavailability_not_exempt');prediction_unavailable.append({'job_id':j['id'],'identity':j['identity'],'status':'required_unscorable_secondary_context','source_sha256':plan['source_sha256']});continue
            before_attempt=len(self.attempts)
            try:
                record,gold=self.chain(j,panel,programme);(records if j["identity"]["role"]=="participant" else refs).append(record);targets[j["id"]]=gold
            except BaseException as e:
                # Only explicit source-capability absence in an optional diagnostic can be unavailable.
                if len(self.attempts)==before_attempt and j["identity"]["role"]=="control" and getattr(e,"code",None) in ("duration_control_source_unavailable","ocular_control_source_unavailable","ocular_residual_source_unavailable","block_control_source_unavailable"):
                    unavailable.append({"job_id":j["id"],"identity":j["identity"],"status":"required_unscorable","source_gap":failure(e),"phase":"source_preparation","original_attempts_sha256":digest(self.attempts)});continue
                error=failure(e);failed_job={"job_id":j["id"],"identity":j["identity"],"phase_request":self.current_request};notstarted=[{"job_id":x["id"],"identity":x["identity"],"status":"not_started_after_original_failure"} for x,_ in alljobs[k+1:]];break
        self.sealed=True;report={"schema":"zuco2-produced-campaign-v1","candidate_records":records,"reference_records":refs,"diagnostic_unavailable":unavailable,"prediction_unavailable":prediction_unavailable,"original_failure":error,"failed_job":failed_job,"not_started":notstarted,"original_attempts":self.attempts,"closed_for_prediction":True,"plan":plan,"reference_plan":reference_jobs,"resources":self.ledger.snapshot(),"scientifically_qualified":False}
        self.ledger.guard(closing=True) if error is None else None
        from .constants import PERSONS
        gold={"source_sha256":plan["source_sha256"],"split_sha256":plan["split_sha256"],"people":[token(self.key,"person",s) for s in PERSONS],"J":panel["J"],"rows":targets,"job_target_keys":{k:k for k in targets}}
        # These private original targets never enter candidate mounts or safe reports.
        g=write(self.root/"PROTECTED_TARGETS.json",gold,self.ledger) if error is None else None
        if g:report["protected_target_pin"]=g
        from .lifecycle import new,prediction_stages
        report['lifecycle']=prediction_stages(new(),report)
        report['source_control_gaps']=panel.get('source_control_gaps',[]);report['source_control_observations']=panel.get('source_control_observations',{});report['job_control_observations']=[{'identity':r['identity'],'observations':r['control_observations']} for r in records+refs if r['control_observations']]
        if 'source_review' in panel:
            from .lifecycle import source_stages
            source_stages(report['lifecycle'],panel,panel['source_review'])
        # Original failures and incomplete observations must survive even when
        # eligibility/deadline/storage admission fails at final closure.
        try:
            self.ledger.charge_controller(max(0.,time.process_time()-self.parent_cpu_start))
            from .closure import reserve_tail,end_tail
            tail=reserve_tail(self.ledger,self.authority.review['budget']['controller_cpu_reserve']);report['resources']=self.ledger.snapshot();raw=encode(report);need(len(raw)<=self.report_cap,'full_campaign_report_capacity');write(self.root/'CAMPAIGN.json',raw);end_tail(self.ledger,tail)
        except BaseException as e:
            emergency={**report,'closure_failure':failure(e),'resources':self.ledger.snapshot(),'eligible_for_scoring':False};raw=encode(emergency);need(len(raw)<=self.report_cap,'failure_campaign_report_capacity');write(self.root/'ORIGINAL_CAMPAIGN_FAILURE.json',raw);raise
        return report
