"""Full manifest compilation; known grids are generated rather than caller-selected."""
from itertools import product
from .strict import require, unique, canonical_bytes, digest, integer
from .profiles import GROUPS, CONDITIONS, SIZES
from .errors import SourceGap

def known_units(group, r):
    if group=="J19":
        return [f"{field}/{size}/{family}" for field,size,family in product(r["retinal_small_fields"],SIZES,("linear","MLP","hybrid"))]
    if group=="J27":
        return [f"{family}/{seed}" for family,seeds in (("linear",r["linear_fit_seeds"]),("MLP",r["mlp_fit_seeds"]),("biophysical",r["biophysical_fit_seeds"])) for seed in seeds]
    if group=="J29":
        # Each producer must return the complete norm curve for one example/model;
        # this does not assume independent retraining at every norm.
        return [f"{model}/{example}" for model,example in product(("biophysical","MLP"),r["attack_example_ids"])]
    if group=="J33":
        return ["steps/1","steps/2","steps/4"]
    if group=="J32":
        return [f"{pair}/{operation}/{batch}" for pair,operation,batch in product(("AMD_M3","A100_H100"),("simulation","gradient"),(1,10,100,1000,10000))]
    return None

def compile_manifest(profile, contracts, producer_map):
    require(set(contracts)==set(GROUPS), "complete group contracts")
    require(set(profile.get("native_group_units",{}))==set(GROUPS), "complete native group unit roster")
    require(set(producer_map)==set(GROUPS), "complete producer graph")
    jobs=[]
    for group in GROUPS:
        units=profile["native_group_units"][group]
        require(type(units) is list and units, "empty required group")
        unique(units,group)
        expected=known_units(group,profile["rosters"])
        if expected is not None:
            require(units==expected, "incomplete or reordered generated group "+group)
        require(profile["native_unit_evidence"].get(group), "native unit evidence "+group)
        contract=contracts[group]
        require(contract.get("group")==group and contract.get("outputs"), "concrete output contract")
        p=producer_map[group]
        missing=[role for role in ("constructor","reference","exporter") if not p.get(role)]
        if missing: raise SourceGap(group+" missing native "+",".join(missing))
        require(set(p.get("selected_profiles",[]))==set(profile["group_profiles"][group]),"scientific profile lineage")
        for unit in units:
            require(type(unit) is str and unit and "\x00" not in unit, "bad scientific unit")
            key=digest(canonical_bytes([group,unit]))[:24]
            job={"job_id":group+"-"+key,"group":group,"unit":unit,
                 "scientific_profiles":profile["group_profiles"][group],
                 "contract_sha256":digest(canonical_bytes(contract)),
                 "constructor":p["constructor"],"reference":p["reference"],"exporter":p["exporter"],
                 "required":True,"reuse_key":p.get("reuse_keys",{}).get(unit),
                 "cost_ceiling":profile["costs"][group][unit]}
            cost=job["cost_ceiling"]
            for name in ("wall_ns","cleanup_ns","memory_bytes","output_bytes","stdout_bytes","stderr_bytes","pids"):
                integer(cost.get(name),name,1)
            require(cost.get("all_search_prior_compile_and_failure_included") is True,"incomplete whole cost admission")
            jobs.append(job)
    ids=[x["job_id"] for x in jobs];require(len(ids)==len(set(ids)),"job collision")
    return {"schema":"jaxley_complete_manifest_v1","task_id":"PAPER-paper-method-002",
            "conditions":list(CONDITIONS),"jobs":jobs,"group_count":36,
            "job_count":len(jobs),"full_roster":True,
            "source_profile_sha256":digest(canonical_bytes(profile)),
            "metric_aggregation":"family_specific_no_scalar",
            "fit_count":"derive actual producer operations; job_count is not fit_count"}

def condition_job(manifest, condition, job_id):
    require(condition in CONDITIONS,"unknown information/procedure condition")
    hits=[j for j in manifest["jobs"] if j["job_id"]==job_id]
    require(len(hits)==1,"unknown or duplicate job")
    return {**hits[0],"condition":condition,"author_code_visible":condition.startswith("B"),
            "procedure":condition[-1]}

