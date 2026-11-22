"""Separate exploratory32 image scorer. No participant executor; gold is gated.

The CLI requires externally committed protocol/prediction hashes and explicit
later gold authorization. Source preparation and generated controls never open
original gold. Existing full6400 evaluator remains unchanged.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import types

IDS = tuple(f"case-{i:02d}" for i in range(1, 33))
ARMS = ("direct", "programme")
STATUSES = ("ok", "abstain", "invalid", "error", "not_attempted")
CAP = 1024 * 1024
SOURCE_PINS = {
 "evaluator.py": {"bytes":25167,"sha256":"509318b7f3f6d0e0fa233e17718a3b53df3ee83d47b42243fad5db803756d81d"},
 "consumer.py": {"bytes":23062,"sha256":"09d5d6b85e7c5baa59c3e24b3a6d3edaff3d94d2efb9970506613d3fef420706"}}
MANIFEST = {"bytes":5428,"sha256":"241870678fed37fca67cc9c64e2e3a0830e0a97f9815332e27fa3018ed6c9f3f"}
COMPLETE = {"bytes":14385,"sha256":"f99a7d79170f879acb0d5c3ac6066c97e59743f36a923c72faf761ac7caccd33"}

def need(ok, why):
    if not ok: raise ValueError(why)

def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode()

def pin(body): return {"bytes":len(body),"sha256":hashlib.sha256(body).hexdigest()}

def decode(body):
    def unique(pairs):
        obj={}
        for k,v in pairs:
            need(k not in obj, "duplicate JSON key")
            obj[k]=v
        return obj
    return json.loads(body, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))

def check_pin(value, cap=CAP):
    need(type(value) is dict and set(value)=={"bytes","sha256"} and type(value["bytes"]) is int
         and 0<=value["bytes"]<=cap and type(value["sha256"]) is str
         and re.fullmatch("[0-9a-f]{64}",value["sha256"]), "bounded exact pin required")

def ordinary(path):
    path=Path(path).absolute()
    need(all(not x.is_symlink() for x in (path,*path.parents)), "symlink path refused")
    return path

def read(path, expected=None, cap=CAP):
    path=ordinary(path)
    if expected is not None: check_pin(expected,cap)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,"rb") as f:
        before=os.fstat(f.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size<=cap,"ordinary bounded input required")
        body=f.read(cap+1);after=os.fstat(f.fileno())
    key=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink)
    need(len(body)==before.st_size and key(before)==key(after)==key(path.lstat()),"changed input")
    need(expected is None or pin(body)==expected,"input pin mismatch")
    return body

def by_sha(path, sha, cap=CAP):
    need(type(sha) is str and re.fullmatch("[0-9a-f]{64}",sha),"external SHA256 required")
    b=read(path,cap=cap);need(pin(b)["sha256"]==sha,"external commitment mismatch");return b

def write_new(path, value):
    b=encode(value);need(len(b)<=CAP,"bounded result")
    p=ordinary(path);fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as f: f.write(b);f.flush();os.fsync(f.fileno())
    return pin(b)

def finite_probability(p):
    return type(p) in (int,float) and math.isfinite(p) and 0<=p<=1

def validate_arm(body, arm, protocol_sha):
    obj=decode(body)
    need(type(obj) is dict and set(obj)=={"schema","arm","protocol_sha256","records"},"exact arm schema")
    need(obj["schema"]=="erp-exploratory-predictions/v1" and obj["arm"]==arm and obj["protocol_sha256"]==protocol_sha,"arm binding")
    rows=obj["records"];need(type(rows) is list and len(rows)==32,"exact32 records required")
    seen={}
    for row in rows:
        need(type(row) is dict and set(row)=={"trial_id","status","target_probability","first_response"},"exact record fields")
        alias=row["trial_id"];need(type(alias) is str and alias in IDS and alias not in seen,"missing/extra/duplicate ID")
        status=row["status"];need(type(status) is str and status in STATUSES,"known status")
        raw=row["first_response"]
        if type(raw) is str: need(len(raw.encode("utf-8"))<=16384,"raw response exceeds cap; retain external pin")
        else: check_pin(raw,1024**3)
        p=row["target_probability"]
        if status=="ok":
            need(finite_probability(p),"finite probability required")
            need(type(raw) is str,"ok response must be retained and parseable")
            parsed=decode(raw)
            need(type(parsed) is dict and set(parsed)=={"trial_id","target_probability"}
                 and parsed["trial_id"]==alias and finite_probability(parsed["target_probability"])
                 and parsed["target_probability"]==p,"canonical prediction differs from first response")
        else: need(p is None,"failure probability must be null")
        seen[alias]=dict(row)
    need(set(seen)==set(IDS),"complete exact roster")
    return [seen[i] for i in IDS]

def admit(protocol_path, protocol_sha, commit_path, commit_sha):
    protocol_body=by_sha(protocol_path,protocol_sha);protocol=decode(protocol_body)
    need(protocol.get("schema")=="erp-exploratory-image-pilot-protocol/v1"
         and [c["trial_id"] for c in protocol["cases"]]==list(IDS),"selected pilot protocol")
    commit_body=by_sha(commit_path,commit_sha,65536);c=decode(commit_body)
    need(type(c) is dict and set(c)=={"schema","protocol","prediction_directory","arms","programme_source"},"exact frozen commit schema")
    need(c["schema"]=="erp-exploratory-prediction-commit/v1" and c["protocol"]==pin(protocol_body),"protocol commit differs")
    root=ordinary(c["prediction_directory"])
    need(root.is_dir() and sorted(x.name for x in root.iterdir())==["direct.json","programme.json"],"exact two prediction files required")
    need(type(c["arms"]) is dict and set(c["arms"])==set(ARMS),"both arm pins required")
    # Both bodies authenticated before parsing either; all admission precedes gold.
    bodies={a:read(root/(a+".json"),c["arms"][a]) for a in ARMS}
    arms={a:validate_arm(bodies[a],a,protocol_sha) for a in ARMS}
    source=c["programme_source"]
    need(type(source) is dict and set(source)=={"path","bytes","sha256"},"frozen programme source descriptor")
    read(source["path"],{k:source[k] for k in ("bytes","sha256")},65536)
    receipt={"schema":"erp-exploratory-prediction-admission/v1","status":"both32_arms_admitted_before_gold",
      "protocol":pin(protocol_body),"prediction_commit":pin(commit_body),"arms":c["arms"],
      "programme_source":{k:source[k] for k in ("bytes","sha256")},"gold_opened":False}
    return protocol,arms,receipt

def load_gold(binding_path,binding_sha,protocol):
    """Only caller after admit() may invoke this original-data adapter.

    Uses unchanged indexed public loader (no query accessor) and private parser.
    It opens full private cohort internally; only32 selected labels leave here.
    This is broader trusted-operator access, never participant access.
    """
    b=decode(by_sha(binding_path,binding_sha,65536))
    need(type(b) is dict and set(b)=={"schema","scoring_authorized","source_directory","public_root","public_manifest","private_material"},"exact gold binding")
    need(b["schema"]=="erp-exploratory-gold-binding/v1" and b["scoring_authorized"] is True,"later explicit scoring selection required")
    need(b["public_manifest"]==MANIFEST and b["private_material"]["complete"]==COMPLETE,"original material commitment")
    modules={}
    for name,expected in SOURCE_PINS.items():
        path=Path(b["source_directory"])/name;body=read(path,expected)
        module=types.ModuleType("pilot_"+name[:-3]);module.__file__=str(path)
        exec(compile(body,str(path),"exec"),module.__dict__);modules[name]=module
    select=protocol["selection"]["operator_map"]
    selected=decode(read(select["path"],{k:select[k] for k in ("bytes","sha256")},65536))
    rows=selected["rows"]
    need([r["alias"] for r in rows]==list(IDS) and len({r["trial_id"] for r in rows})==32
         and len({r["shard"] for r in rows})==32 and selected["selection_uses_labels"] is False,"exact unique selected aliases and shards")
    with modules["consumer.py"].PacketSession(b["public_root"],b["public_manifest"]) as session:
        need(all(r["trial_id"] in session.trial_ids and session._rows[r["trial_id"]]["path"]==r["shard"] for r in rows),"selection matches authenticated public roster")
        people=modules["evaluator.py"].load_private_people(b["private_material"],b["public_manifest"],set(session.trial_ids),{"read":16*1024**2})
    flat={identifier:(person,y) for person,trials in people.items() for identifier,y in trials}
    need(len({flat[r["trial_id"]][0] for r in rows})==32,"one selected query per private person")
    return {r["alias"]:flat[r["trial_id"]][1] for r in rows}

def summarize(arms, labels):
    import numpy as np
    need(np.__version__=="1.26.3" and sys.version_info[:3]==(3,11,6),"selected Python3.11.6/NumPy1.26.3 required")
    need(type(labels) is dict and set(labels)==set(IDS) and all(type(v) is int and v in (0,1) for v in labels.values()),"exact32 binary labels")
    y=np.array([labels[i] for i in IDS],dtype=np.int8)
    correct={};summary={}
    for arm in ARMS:
        rows=arms[arm]
        need([r["trial_id"] for r in rows]==list(IDS),"ordered admitted rows")
        correct[arm]=np.array([r["status"]=="ok" and int(r["target_probability"]>=.5)==labels[r["trial_id"]] for r in rows],dtype=np.float64)
        counts={s:sum(r["status"]==s for r in rows) for s in STATUSES}
        summary[arm]={"records":32,"coverage":counts["ok"]/32,"status_counts":counts,
          "failure_aliases":[r["trial_id"] for r in rows if r["status"]!="ok"],"balanced_accuracy":None}
    n0=int(np.sum(y==0));n1=32-n0
    out={"schema":"erp-exploratory32-image-score/v1","endpoint":"event_identity","class_support":{"standard":n0,"target":n1},"arms":summary,
      "primary_direct_minus_programme_BA":None,"uncertainty":None,"claims":"finite exploratory32-case image pilot; no physiological P3, full6400, native-isolation, source-unseen or SOTA claim"}
    if not n0 or not n1:
        out["status"]="one_class_balanced_accuracy_unavailable";return out
    idx=[np.flatnonzero(y==v) for v in (0,1)]
    for a in ARMS: summary[a]["balanced_accuracy"]=float(.5*(correct[a][idx[0]].mean()+correct[a][idx[1]].mean()))
    out["primary_direct_minus_programme_BA"]=summary["direct"]["balanced_accuracy"]-summary["programme"]["balanced_accuracy"]
    rng=np.random.Generator(np.random.PCG64(20261122))
    # One pair of class-stratified index arrays, reused for both arms.
    draws=[v[rng.integers(0,len(v),size=(10000,len(v)))] for v in idx]
    boot={a:.5*(correct[a][draws[0]].mean(axis=1)+correct[a][draws[1]].mean(axis=1)) for a in ARMS}
    interval=lambda v:[float(x) for x in np.quantile(v,[.025,.975],method="linear")]
    out["uncertainty"]={"replicates":10000,"seed":20261122,"generator":"PCG64","confidence":.95,"method":"paired observed-class-stratified percentile; NumPy linear quantiles",
      "primary_direct_minus_programme_BA":interval(boot["direct"]-boot["programme"]),
      "secondary_unadjusted_absolute_arm_BA":{a:interval(boot[a]) for a in ARMS},
      "scope":"conditional on observed class support; one selected case/person; no trial pseudoreplication"}
    out["runtime"]={"python":sys.version.split()[0],"numpy":np.__version__,"numpy_origin":np.__file__}
    out["status"]="exploratory_pair_scored";return out

def evaluate(protocol_path,protocol_sha,commit_path,commit_sha,*,gold_loader):
    protocol,arms,receipt=admit(protocol_path,protocol_sha,commit_path,commit_sha)
    labels=gold_loader(protocol)  # First permitted gold call, after complete admission.
    result=summarize(arms,labels);result["admission"]=receipt
    result["gold_opened_after_both_admitted"]=True
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ("protocol","protocol-sha256","commit","commit-sha256","output"): ap.add_argument("--"+name,required=True)
    ap.add_argument("--admit-only",action="store_true")
    ap.add_argument("--gold-binding");ap.add_argument("--gold-binding-sha256")
    args=ap.parse_args()
    if args.admit_only:
        need(not args.gold_binding and not args.gold_binding_sha256,"admission must have no gold operand")
        result=admit(args.protocol,args.protocol_sha256,args.commit,args.commit_sha256)[2]
    else:
        need(args.gold_binding and args.gold_binding_sha256,"separately authorized gold binding required")
        result=evaluate(args.protocol,args.protocol_sha256,args.commit,args.commit_sha256,
            gold_loader=lambda protocol:load_gold(args.gold_binding,args.gold_binding_sha256,protocol))
    print(json.dumps(write_new(args.output,result)))
if __name__=="__main__": main()
