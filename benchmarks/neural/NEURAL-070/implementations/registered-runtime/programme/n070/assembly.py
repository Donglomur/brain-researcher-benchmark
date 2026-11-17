"""Bounded ordinary capture composition; no scientific array decoding on host."""
from pathlib import Path
from .core import need,digest
from .protocol import PARTICIPANTS
from .native.io import read,write_new,tree,relative,dump,load
def merge(captures,target,limits):
    target=Path(target);need(not target.exists(),"Fresh composed input namespace")
    allrows=[];seen=set()
    for prefix,capture in captures:
        for row in capture["selection"]["files"]:
            name=relative(prefix+"/"+row["path"]if prefix else row["path"])
            need(name not in seen,"No source/output collision");seen.add(name)
            allrows.append((name,Path(capture["root"])/row["path"],row))
    need(len(allrows)<=limits["files"]and sum(r["bytes"]for _,_,r in allrows)<=limits["total"],"Full composition before body copies")
    for name,path,row in allrows:write_new(target/name,read(path,limits["member"],row),limits["member"])
    return {"root":str(target),"selection":tree(target,**limits)}
def capture_existing(root,limits):return {"root":str(root),"selection":tree(root,**limits)}
def stage_score(engine,condition,arm,actors,reference_jobs,targets,groups,split_identity,root,limits):
    expected={p+"/fold-"+str(f)for p in PARTICIPANTS for f in range(5)}
    need(set(actors)==set(reference_jobs)==set(targets)==expected,"Complete50 actor/reference/target joins")
    barrier=engine.barrier(list(actors.values())+list(reference_jobs.values()));sources=[];views={};bindings={}
    for key,actor_id in actors.items():
        capture=engine.captures[actor_id];target=targets[key]
        person,fold=key.split("/fold-")
        reference,binding=engine.reference_capture(reference_jobs[key],person,int(fold))
        bindings[key]=binding
        sources.extend([("predictions/"+key,capture),("references/"+key,reference),("targets/"+key,target)])
        views[key]={"target_manifest":"targets/"+key+"/targets.json",
                    "target_root":"targets/"+key,"prediction_manifest":"predictions/"+key+"/predictions.json",
                    "prediction_root":"predictions/"+key,"reference_manifest":"references/"+key+"/predictions.json",
                    "reference_root":"references/"+key}
    result=merge(sources,root,limits)
    dump(Path(root)/"score_inputs.json",{"barrier":"all_actor_lifetimes_closed_and_predictions_immutable",
        "original_barrier_identity":barrier,"views":views,"groups":groups,
        "split_identity":split_identity,"condition":condition,"arm":arm,
        "reference_bindings":bindings,"reference_binding_identity":digest(bindings)})
    result["selection"]=tree(root,**limits);result["reference_binding_identity"]=digest(bindings);return result

