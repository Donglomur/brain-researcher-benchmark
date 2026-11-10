"""Request custody before external effects; source/state/support joins are explicit."""
import time
from .errors import Custody, need
from .identity import identity, exact, descriptor, canonical, parse, finite
from .policy import evidence, validate_evidence

class Journal:
    def __init__(self,store,generation,source,context,profile,direct=False):
        self.store=store;self.generation=generation;self.source=source
        self.context=context;self.profile=profile;self.direct=direct
        self.owned={};self.records={};self.sequence=0;self.custody=Custody()
        self.parents={};self.review_records={}

    def begin(self,stage,method,inputs,outputs,parent=None):
        self.sequence+=1
        ancestry=self.parents.get(self.context,{"request_id":None,"receipt":None}) if parent is None else parent
        request={"protocol":"N071","version":1,"generation":self.generation,
                 "context_id":self.context,"stage_id":stage,"method_id":method,
                 "caller_source":self.source,"operative_source_manifest":self.source,
                 "parent_request":ancestry["request_id"],"original_receipt":ancestry["receipt"],
                 "input_descriptors":inputs,
                 "output_reservations":outputs,"resource_profile":self.profile,
                 "monotonic_start":time.monotonic(),"utc_start":time.time(),**evidence(self.direct)}
        rid=identity([self.sequence,request])
        # Ownership is established before publishing the request or invoking its producer.
        self.owned[rid]={"request":request,"request_artifact":None,"receipt":None,"finished":False}
        rec=self.store.put("request-"+rid+".json",request)
        self.owned[rid]["request_artifact"]=rec
        return rid

    def finish(self,rid,outputs,original_completion):
        need(rid in self.owned and not self.owned[rid]["finished"],"request-owned-once")
        item=self.owned[rid]
        need(item["request_artifact"] is not None,"request-published")
        receipt={"request_id":rid,"request":item["request_artifact"],"outputs":outputs,
                 "original_completion":original_completion,"monotonic_end":time.monotonic(),
                 "utc_end":time.time(),"cost_snapshot":self.store.budget.report(),**evidence(self.direct)}
        item["receipt_value"]=receipt
        rec=self.store.put("receipt-"+rid+".json",receipt)
        item["receipt"]=rec;self.records[rid]=receipt
        # Construct the closed projection while the permitted producer owns the
        # original values. Postscore consumers never reopen enclosing raw bodies.
        projection=self.review_projection(item["request"],receipt,rec)
        projected=self.store.put("review-metadata-"+rid+".json",projection)
        self.review_records[identity(rec)]=projected
        item["finished"]=True
        self.parents[item["request"]["context_id"]]={"request_id":rid,"receipt":rec}
        return rec

    def review_projection(self,request,receipt,record):
        keys=("protocol","version","generation","context_id","stage_id","method_id",
              "caller_source","operative_source_manifest","parent_request","original_receipt",
              "resource_profile","monotonic_start","utc_start","method_prior_identity",
              "clock_conventions_identity","historical_layer8_direct_consumer","evaluation_label")
        q={k:request[k] for k in keys}
        inputs=request["input_descriptors"]
        q["input_identity"]=identity(inputs)
        # Only immediate closed descriptor values are metadata. Never recursively
        # interpret an arbitrary message/result or dereference an embedded body.
        def descriptors(values):
            out=[]
            for value in values:
                if type(value)is dict and set(value)=={"path","bytes","sha256","mode"}:
                    out.append(descriptor(value))
            return out
        q["input_artifacts"]=descriptors(inputs if type(inputs)is list else
                                         inputs.values() if type(inputs)is dict else [])
        q["private_input_bodies_delivered"]=False
        outputs=receipt["outputs"];completion=receipt["original_completion"]
        output_artifacts={k:descriptor(v) for k,v in outputs.items()
            if type(v)is dict and set(v)=={"path","bytes","sha256","mode"}}
        native=("exit_code","raw_wait_status","wait_cpu_seconds","wall_seconds")
        facts={k:completion[k] for k in native if k in completion}
        for value in facts.values():need(finite(value),"review-native-cost-scalar")
        if "cleanup"in completion:
            c=completion["cleanup"];exact(c,("first_phase","secondary_phases"))
            need(c["first_phase"]is None or type(c["first_phase"])is str,"review-cleanup-first")
            need(type(c["secondary_phases"])is list and all(type(x)is str for x in c["secondary_phases"]),"review-cleanup-secondary")
            facts["cleanup"]=c
        for key in ("kind","returned","identity","targets_scoped_to_full_barrier"):
            if key in completion:
                need(type(completion[key])in(str,bool),"review-completion-scalar")
                facts[key]=completion[key]
        if "launcher"in completion:facts["launcher"]=descriptor(completion["launcher"])
        provider=None
        if request["method_id"]=="provider":
            usage=completion["usage"];exact(usage,("input_tokens","output_tokens"))
            need(all(type(v)is int and v>=0 for v in usage.values()),"review-provider-usage")
            need(type(completion["provider_model"])is str and completion["provider_model"] and
                 type(completion["provider_request_id"])is str and completion["provider_request_id"],
                 "review-provider-identities")
            need(finite(completion["cost"])and completion["cost"]>=0,"review-provider-cost")
            need(type(completion["price_identity"])is str and completion["price_identity"],"review-provider-price-identity")
            provider={k:completion[k] for k in ("provider_model","provider_request_id","usage","cost","price_identity")}
        result={"schema":"n071-owned-review-metadata-v1","original_receipt":record,
                "original_request":receipt["request"],"request_id":receipt["request_id"],
                "request":q,"monotonic_end":receipt["monotonic_end"],"utc_end":receipt["utc_end"],
                "cost_snapshot":receipt["cost_snapshot"],"original_completion":facts,
                "output_artifacts":output_artifacts,"output_identity":identity(outputs),
                "provider":provider,"analysis_result_identity":None}
        if request["method_id"]=="candidate-author-tool":
            need("projected_result"in outputs,"owned-analysis-result")
            result["analysis_result_identity"]=identity(outputs["projected_result"])
        body=canonical(result)
        if len(body)>1<<20:
            # Optional evidence capacity does not invalidate an otherwise closed
            # numeric producer. No truncation or raw-body fallback is authorized.
            return {"schema":"n071-owned-review-metadata-unavailable-v1",
                    "original_receipt":record,"original_request":receipt["request"],
                    "reason":"closed-review-metadata-cap","required_bytes":len(body),
                    "cap_bytes":1<<20}
        return parse(body)

    def review_metadata(self,receipts):
        keys=[identity(r) for r in receipts]
        need(len(keys)==len(set(keys))and all(k in self.review_records for k in keys),
             "complete-owned-review-metadata")
        return {k:self.review_records[k] for k in keys}

    def invoke(self,stage,method,inputs,outputs,fn,*args,parent=None):
        rid=self.begin(stage,method,inputs,outputs,parent)
        try:
            result=fn(*args)
        except BaseException as exc:
            self.custody.retain(exc,method)
            self.owned[rid]["failed"]=True
            raise
        receipt=self.finish(rid,outputs,{"kind":"in_process_return","returned":True})
        return result,receipt

    def require_complete(self):
        need(self.owned and all(x["finished"] for x in self.owned.values()),"all-original-requests-closed")
        need(self.custody.first is None,"first-error-present")
        return [x["receipt"] for x in self.owned.values()]

def validate_receipt(receipt,generation,context,source,direct):
    request=receipt["request_value"]
    need((request["generation"],request["context_id"],request["operative_source_manifest"])==
         (generation,context,source),"receipt-context-source")
    validate_evidence(request,direct)
    need(receipt["closed"] is True and receipt["request_id"] and
         receipt["cost"]["closed"] is True and not receipt["cost"]["unknown"],"receipt-cost-closure")
