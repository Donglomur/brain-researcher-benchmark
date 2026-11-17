"""Unconfigured by default; all authentic/native operations need externally admitted source bindings."""
import os,re,sys
from pathlib import Path
from .common import exact,need,read_json,check_pin,object_pin,read,absolute,relative
REQUIRED=("biological_admission","native_execution","runtime_environment","provider_bridge","candidate_F","candidate_I","reference_numerics","retention_feasibility")
def inspect(value):
    exact(value,["schema","task","authorities","limitations"])
    need(value["schema"]=="neural047-deployment-v1" and value["task"]=="NEURAL-047","Exact deployment")
    exact(value["authorities"],REQUIRED)
    return {"configured":all(value["authorities"][k] is not None for k in REQUIRED),
            "missing":[k for k in REQUIRED if value["authorities"][k] is None],
            "scientific_qualified":False,"limitations":value["limitations"]}
def load(path,expected,ledger):
    value=read_json(path,expected,ledger,"independently selected deployment")
    state=inspect(value);need(state["configured"],"Unconfigured qualification gates: "+",".join(state["missing"]))
    docs={}
    for role in REQUIRED:
        desc=value["authorities"][role];exact(desc,["path","bytes","sha256"])
        docs[role]=read_json(desc["path"],{k:desc[k] for k in ("bytes","sha256")},ledger,"qualified "+role)
    return value,docs
def code_snapshot(root,manifest,ledger):
    exact(manifest,["schema","files"]);need(manifest["schema"]=="neural047-source-freeze-v1","Ordinary source freeze")
    seen=set()
    for row in manifest["files"]:
        exact(row,["path","bytes","sha256"]);relative(row["path"])
        need(row["path"] not in seen,"Unique complete source member");seen.add(row["path"])
        read(absolute(root)/row["path"],{k:row[k] for k in ("bytes","sha256")},ledger,"operative source authentication",retain=False)
    need(seen and "program/runner.py" in seen,"Executable source graph")
def method(doc,mode):
    exact(doc,["schema","mode","source_manifest_pin","entrypoint","argv","family_review_pin","family_rule","limits","provider_model"])
    need(doc["schema"]=="neural047-method-admission-v1" and doc["mode"]==mode,"Exact global method")
    check_pin(doc["source_manifest_pin"],4194304);check_pin(doc["family_review_pin"],4194304)
    need(type(doc["family_rule"]) is str and doc["family_rule"],"Explicit independent semantic admission limitation")
    need(type(doc["argv"]) is list and all(type(x) is str and "\0" not in x for x in doc["argv"]),"Exact argv")
    relative(doc["entrypoint"]);need(doc["argv"] and doc["argv"][0].startswith("/"),"Native absolute entrypoint")
    from .budgets import validate_limits
    validate_limits(doc["limits"],mode)
    return doc
def qualified_outer(profile):
    """Join the original outer observer to actual kernel membership."""
    need(os.environ.get("NEURAL047_JOBS_CGROUP")==profile["cgroup_parent"],"Original outer observer and owned job cgroup")
    outer=absolute(os.environ["NEURAL047_OUTER_CGROUP"])
    need(outer.is_relative_to("/sys/fs/cgroup") and absolute(profile["cgroup_parent"])==outer/"jobs","Canonical owned hierarchy")
    member=[line.split("::",1)[1] for line in Path("/proc/self/cgroup").read_text().splitlines() if line.startswith("0::")]
    expected="/"+str((outer/"controller").relative_to("/sys/fs/cgroup"))
    need(member==[expected] and os.getpid() in [int(x) for x in (outer/"controller"/"cgroup.procs").read_text().split()],"Actual kernel controller membership")

