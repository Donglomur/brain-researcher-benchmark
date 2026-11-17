"""Full prepared contexts, without subset constructors or target-based selection."""
from .common import exact,need,canonical,object_pin,publish,fresh_dir,relative
from .legacy.prepare import build
from .legacy.scorer_core import public_contract,admit
from .development import validate
def construct(normalized,secret):
    audit,panel,folds,targets=build(normalized,secret)
    need(panel is not None,"Complete source support insufficient: "+audit.get("reason","unspecified source refusal"))
    expected={(f["fold_id"],a) for f in panel["folds"] for a in ("N","B","NB")}
    need({(f["fold_id"],f["arm"]) for f in folds}==expected and len(folds)==len(expected),"Exact full programme packet coverage")
    for f in folds:validate(f)
    return {"audit":audit,"panel":panel,"folds":folds,"targets":targets}
def compile_jobs(prepared):
    panel=prepared["panel"];public_contract(panel)
    foldmap={(f["fold_id"],f["arm"]):f for f in prepared["folds"]}
    expected={(f["fold_id"],a) for f in panel["folds"] for a in ("N","B","NB")}
    need(set(foldmap)==expected and len(foldmap)==len(prepared["folds"]),"Full packet join")
    jobs=[]
    for mode in ("F","I","R0","R1","R2"):
        for fold in panel["folds"]:
            for arm in ("N","B","NB"):
                packet=foldmap[(fold["fold_id"],arm)];validate(packet)
                jobs.append({"job_id":mode+"_"+fold["fold_id"]+"_"+arm,"mode":mode,"fold_id":fold["fold_id"],"arm":arm,
                             "input_pin":object_pin(packet),"query_count":len(packet["query"]),"training_count":len(packet["training"])})
    return {"schema":"neural047-full-program-v1","packet_id":panel["packet_id"],"animals":len(panel["folds"]),
            "jobs":jobs,"job_count":len(jobs),"reference_inner_fit_count":27*len(panel["folds"])*(len(panel["folds"])-1),
            "reference_final_fit_count":9*len(panel["folds"]),"candidate_contexts":6*len(panel["folds"]),
            "independence_unit":"animal","scientific_ready":False}
def write_prepared(prepared,out,ledger,cap):
    """Operator-only fresh private directory. All materialization costs admitted in advance."""
    need(type(cap) is int and 0<cap<=300000000,"Existing full-preparation ceiling, no scope-reducing crop")
    rows=[("panel.json",prepared["panel"]),("targets.json",prepared["targets"]),("audit.json",prepared["audit"]),("programme.json",compile_jobs(prepared))]
    rows += [(f["fold_id"]+"_"+f["arm"]+".json",f) for f in prepared["folds"]]
    descriptors=[{"path":name,**object_pin(obj)} for name,obj in rows]
    manifest={"schema":"neural047-prepared-programme-v1","files":descriptors,"packet_id":prepared["panel"]["packet_id"]}
    need(sum(x["bytes"] for x in descriptors)+len(canonical(manifest))<=cap,"Complete materialization exceeds cap; nothing emitted")
    root=fresh_dir(out)
    for name,value in rows:publish(root/relative(name),value,ledger,"full preparation "+name)
    publish(root/"MANIFEST.json",manifest,ledger,"preparation closure")
    return manifest
def collect(panel,results):
    need(type(results) is list and len(results)==15*len(panel["folds"]),"Every F/I/reference producer, no subset")
    collections={}
    for mode in ("F","I","R0","R1","R2"):
        selected=[r for r in results if r["mode"]==mode]
        need(len(selected)==3*len(panel["folds"]),"Every arm/animal in each mode")
        outcomes=[]
        for row in selected:
            exact(row,["mode","job_id","prediction"])
            p=row["prediction"];exact(p,["schema","packet_id","outcome"])
            need(p["schema"]=="neural047-fold-predictions-v1" and p["packet_id"]==panel["packet_id"],"Bound single outcome")
            need(row["job_id"]==mode+"_"+p["outcome"]["fold_id"]+"_"+p["outcome"]["arm"],"Producer/outcome identity")
            outcomes.append(p["outcome"])
        c={"schema":"neural047-predictions-v1","packet_id":panel["packet_id"],"outcomes":outcomes}
        admit(panel,c);collections[mode]=c
    return collections

