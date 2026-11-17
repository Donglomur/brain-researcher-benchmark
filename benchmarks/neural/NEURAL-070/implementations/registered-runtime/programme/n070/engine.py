"""Actual OCI call, immutable capture and complete original cost ownership."""
from pathlib import Path
import os
from .core import Attempt,need,digest
from .native import oci
from .native.io import tree,snapshot,dump
from .native.process import validate_command
from .native.resources import eligible
from .native.observation import Observation
from .native.contracts import bind
class Engine:
    def __init__(self,deployment,programme,root,controller):
        self.deployment=deployment;self.programme=programme;self.root=Path(root)
        self.controller=controller;self.attempts={};self.captures={}
    def execute(self,job,source,inputs,request,*,state=None,products=None,expected=None):
        owner=Attempt(job["id"]);self.attempts[job["id"]]=owner
        observation=Observation("n070_owned_capsule");owner.children.append(observation)
        cap=job["resource_reservation"]["caps"];profile=dict(self.deployment.body["oci"])
        profile["qualification"]=self.deployment.identity;profile["selected_qualification"]=self.deployment.identity
        work=self.root/"operations"/job["public_id"];result=None
        try:
            need(self.controller.active,"Actual enclosing controller lifetime")
            need(job["id"]not in self.captures,"No repeated completed operation")
            selected={}
            for name,path in(("source",source),("inputs",inputs),("state",state),("products",products)):
                if path is not None:selected[name]=tree(path,**self.deployment.body["tree_limits"])
            owner.originals["before"]=selected
            need(expected is not None and selected==expected,"Every actual mounted tree is independently selected or owned capture")
            request=dict(request);request["input_bytes"]=sum(t["bytes"]for t in selected.values())
            request["entrypoint"]=[self.deployment.body["capsule_python"],"-I","-B","/source/entry.py"]
            owner.originals["request"]=request
            with bind(self.deployment),self.controller.actor(job["id"]):
                result=oci.run(profile,job,request,source,inputs,state,work,cap,products=products,observation=observation)
            owner.originals["returned"]=result
        except BaseException as error:owner.fail("execute",error)
        # These independent tails retain original owners even after early failure.
        owner.call("account",self._account,job,observation)
        for name,path in(("source",source),("inputs",inputs),("state",state),("products",products)):
            if path is not None and name in owner.originals.get("before",{}):
                owner.call("immutable:"+name,self._unchanged,path,owner.originals["before"][name])
        if not owner.errors:
            owner.call("eligible",eligible,observation.record,cap)
            owner.call("actual_command",validate_command,work/"command",
                [profile["runc"]["path"],"--root",str(work/"runtime-state"),"run","--bundle",str(work/"bundle"),job["public_id"]],
                request,{"PATH":os.defpath},work)
        if not owner.errors:
            owner.call("capture",self._capture,job,work/"writable"/"output",owner)
        summary=owner.call("summary",owner.summary)
        if summary is not None:owner.publish("attempt",summary,lambda:dump(self.root/"attempts"/(job["public_id"]+".json"),summary))
        owner.raise_first()
        return self.captures[job["id"]]
    def _account(self,job,observation):
        costs=observation.record.get("resources");complete=observation.record.get("resource_completeness",{})
        self.attempts[job["id"]].originals["costs"]={"values":costs,"complete":complete}
        need(costs is not None and all(complete.values())and complete,"Unknown cost retained; never a zero certificate")
        need(not self.programme["budget"].commit(job["id"],costs),"Original cost exceeds reserved cap")
    def _unchanged(self,path,selected):
        need(tree(path,**self.deployment.body["tree_limits"])==selected,"Selected immutable source/input changed")
    def _capture(self,job,source,owner):
        limits=self.deployment.body["tree_limits"];selection=tree(source,**limits)
        target=self.root/"captures"/job["public_id"]
        actual=snapshot(source,target,selection,limits)
        for row in actual["files"]:(target/row["path"]).chmod(0o400)
        actual=tree(target,**limits)
        owner.originals["capture"]={"root":str(target),"selection":actual}
        self.captures[job["id"]]=owner.originals["capture"]
    def barrier(self,ids):
        need(set(ids)<=set(self.attempts) and set(ids)<=set(self.captures),"Every required actor has actual retained capture")
        for key in ids:
            owner=self.attempts[key]
            need(not owner.errors and owner.children[0].record["all_descendants_absent"],"No live/failed actor before target access")
            need(all(v["state"]=="durable"for v in owner.publications.values()),"Attempt publication complete before scoring")
        return digest({k:self.captures[k]["selection"]["identity"]for k in sorted(ids)})
    def reference_capture(self,job_id,participant,fold):
        """Return only this Engine's original successful fixed-reference capture.
        Supplied output dictionaries or claimed receipt labels are not inputs.
        """
        jobs=[j for j in self.programme["body"]["jobs"]if j["id"]==job_id]
        need(len(jobs)==1,"One original reserved reference job")
        job=jobs[0];key=participant+"/fold-"+str(fold)
        need(job["operation"]=="reference" and job["participant"]==participant and job["fold"]==fold,"Exact original reference operation and view")
        barrier=self.barrier([job_id]);owner=self.attempts[job_id];capture=self.captures[job_id]
        need(capture is owner.originals["capture"],"Original capture object retained by original attempt")
        before=owner.originals["before"];b=self.deployment.body
        need(before=={"source":b["evaluator_selection"],"inputs":b["prepared_view_selections"][key]},"Reference ran fixed evaluator source on exact original public view")
        need(owner.originals["request"]["operation"]=="reference","Actual issued reference request")
        need(tree(capture["root"],**b["tree_limits"])==capture["selection"],"Protected reference capture remains immutable")
        binding={"job_id":job_id,"participant":participant,"fold":fold,
                 "source_identity":before["source"]["identity"],"input_identity":before["inputs"]["identity"],
                 "capture_identity":capture["selection"]["identity"],"original_barrier_identity":barrier,
                 "programme_identity":self.programme["identity"],"deployment_identity":self.deployment.identity}
        return capture,binding

