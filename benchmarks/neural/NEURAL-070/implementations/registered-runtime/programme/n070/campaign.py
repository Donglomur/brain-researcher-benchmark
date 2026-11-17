"""Complete actual participant/reference/scorer orchestration, no host science."""
from pathlib import Path
from .core import Attempt,need,digest
from .protocol import CONDITIONS,ARMS,PARTICIPANTS
from .native.io import load,dump,tree
from .assembly import capture_existing,merge,stage_score
class Campaign:
    def __init__(self,deployment,programme,engine,root):
        self.deployment=deployment;self.programme=programme;self.engine=engine;self.root=Path(root)
        self.owner=Attempt("campaign");self.owner.children.append(engine);self.submissions={};self.final={};self.reports={};self.frozen_sources=None
    def freeze_sources(self):
        """Observe all original fixed source trees before the first view dispatch."""
        b=self.deployment.body;need(self.frozen_sources is None,"Only one original frozen-source admission")
        need(set(b["frozen_programmes"])==set(ARMS),"All three fixed programmes, no arm filtering")
        captured={}
        for arm in ARMS:
            row=b["frozen_programmes"][arm];actual=tree(row["root"],**b["tree_limits"])
            need(actual==row["selection"] and actual["identity"]==row["source_identity"],"Original frozen identity is actual complete source tree")
            captured[arm]=actual
        self.frozen_sources=captured;self.owner.originals["frozen_sources"]=captured
    def source(self,condition,arm,person,fold,step):
        b=self.deployment.body
        # Fixed programmes were sealed before any evaluation view. Adaptive
        # source is a finite operator-captured submission sequence, never a receipt.
        key="/".join((condition,arm,person,str(fold),str(step)))
        row=b["submissions"][key]
        if condition=="frozen_program":
            need(self.frozen_sources is not None,"Actual original fixed trees captured before exposure")
            frozen=self.frozen_sources[arm]
            need(row["source_identity"]==frozen["identity"] and row["selection"]==frozen,"F submission binds original actual tree, not a shared label")
        need(row["exposure_state"]=="sealed_before_this_step" and row["budget_group"]==key.rsplit("/",1)[0],"Exact original submission and charge group")
        actual=tree(row["root"],**b["tree_limits"]);need(actual==row["selection"],"Actual submitted source bytes")
        need(actual["identity"]==row["source_identity"],"Declared submission identity matches actual tree")
        if condition=="frozen_program":need(actual==self.frozen_sources[arm],"Original complete fixed tree at every dispatch")
        self.submissions[key]=actual;return row["root"]
    def evaluate(self):
        b=self.deployment.body;limits=b["tree_limits"];jobs=self.programme["body"]["jobs"]
        self.freeze_sources() # before ANY prepared view is dispatched, including references
        prepared=load(Path(b["prepared_root"])/"prepared_manifest.json",pin=b["prepared_manifest"])
        from .splits import validate,verify_groups
        groups=verify_groups(b["equivalence_binding"])
        validate(b["split"],groups)
        need(groups==b["video_groups"] and prepared["split_identity"]==digest(b["split"]),"Exact source groups and split")
        views=prepared["views"];targets=prepared["targets"]
        # Source completeness is checked before exposure. Every requested arm,
        # case, control, step, reference and report remains in the fixed plan.
        need(len(views)==len(targets)==50,"Complete 10-person by 5-fold prepared joins")
        references={};reference_jobs={}
        for job in jobs:
            if job["operation"]!="reference":continue
            key=job["participant"]+"/fold-"+str(job["fold"])
            need(key not in reference_jobs,"Fixed reference generated once per original view")
            references[key]=self.engine.execute(job,b["evaluator_source"],Path(b["prepared_root"])/views[key]["path"],
                {"operation":"reference","member_bytes":job["resource_reservation"]["caps"]["member_bytes"]},
                expected={"source":b["evaluator_selection"],"inputs":b["prepared_view_selections"][key]})
            reference_jobs[key]=job["id"]
        need(set(reference_jobs)==set(views),"All50 original protected reference attempts retained")
        for job in jobs:
            if job["operation"]!="participant":continue
            condition,arm,p,f,step=(job[k]for k in("condition","arm","participant","fold","step"))
            key=p+"/fold-"+str(f);source=self.source(condition,arm,p,f,step)
            products=references[key]["root"]if arm in("supplied_reference","agent_with_reference")else None
            # Supplied reference artifacts contain predictions/fit metadata only;
            # evaluator query targets are in a disjoint preparation subtree.
            captured=self.engine.execute(job,source,Path(b["prepared_root"])/views[key]["path"],
                {"operation":"predict","condition":condition,"arm":arm,"step":step,
                 "member_bytes":job["resource_reservation"]["caps"]["member_bytes"]},products=products,
                 expected={"source":self.submissions[job["id"]],"inputs":b["prepared_view_selections"][key],
                           **({"products":references[key]["selection"]}if products is not None else {})})
            self.final[condition,arm,key]=job["id"]
        actor_ids=[j["id"]for j in jobs if j["operation"]in("participant","reference")]
        self.engine.barrier(actor_ids) # all arms/steps cease before ANY target read
        private={key:capture_existing(Path(b["prepared_root"])/row["path"],limits)for key,row in targets.items()}
        need({key:row["selection"]for key,row in private.items()}==b["prepared_target_selections"],"Actual protected target trees agree with independent preparation closure")
        for job in jobs:
            if job["operation"]!="score":continue
            condition=job["condition"];arm=job["scored_arm"]
            selected={key:self.final[condition,arm,key]for key in views}
            inputs=stage_score(self.engine,condition,arm,selected,reference_jobs,private,b["video_groups"],prepared["split_identity"],
                               self.root/"score-inputs"/job["public_id"],limits)
            result=self.engine.execute(job,b["evaluator_source"],inputs["root"],
                {"operation":"score","member_bytes":job["resource_reservation"]["caps"]["member_bytes"],
                 "draws":b["bootstrap"]["draws"],"seed":b["bootstrap"]["seed"],
                 "reference_binding_identity":inputs["reference_binding_identity"]},
                 expected={"source":b["evaluator_selection"],"inputs":inputs["selection"]})
            self.reports[condition,arm]=result
        return {"reports":{c+"/"+a:v for(c,a),v in self.reports.items()},"complete_conditions":2,"arms":3,
                "case_views_per_arm":50,"all_actor_steps_retained":True}
    def prepare(self):
        b=self.deployment.body;outputs={};limits=b["tree_limits"]
        for job in self.programme["body"]["jobs"]:
            op=job["operation"]
            if op in("convert","features"):
                inputs=b["preparation_inputs"][op];input_selection=b["preparation_selections"][op]
            else:
                # Convert and feature outputs use disjoint responses/features paths.
                metadata=capture_existing(b["preparation_inputs"]["metadata"],limits)
                need(metadata["selection"]==b["preparation_selections"]["metadata"],"Exact preparation metadata before composition")
                stage=merge([("",outputs["convert"]),("",outputs["features"]),("",metadata)],
                            self.root/"preparation-inputs",limits);inputs=stage["root"];input_selection=stage["selection"]
            outputs[op]=self.engine.execute(job,b["evaluator_source"],inputs,b["preparation_requests"][op],
                expected={"source":b["evaluator_selection"],"inputs":input_selection})
        return outputs
    def run(self):
        result=None
        try:
            phase=self.programme["body"]["phase"]
            if phase=="evaluate":result=self.evaluate()
            elif phase=="prepare":result=self.prepare()
            else:
                b=self.deployment.body;j=self.programme["body"]["jobs"][0]
                result=self.engine.execute(j,b["evaluator_source"],b["literal_a_inputs"],b["literal_a_request"],
                    expected={"source":b["evaluator_selection"],"inputs":b["literal_a_selection"]})
        except BaseException as error:self.owner.fail("body",error)
        self.owner.originals["result"]=result
        body=self.owner.call("projection",lambda:{"status":"failed"if self.owner.errors else"complete","result":result,
            "custody":self.owner.summary(),"scientific_claim":"conditional released measurement and checkpoint"})
        if body is not None:self.owner.publish("campaign",body,lambda:dump(self.root/"CAMPAIGN.json",body))
        self.owner.raise_first();return body

