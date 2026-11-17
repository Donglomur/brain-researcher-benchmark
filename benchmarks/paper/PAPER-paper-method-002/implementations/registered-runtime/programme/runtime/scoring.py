"""Family-specific operator grading. A printed paper percentage is not a success threshold."""
from .strict import require, canonical_bytes, digest
from .numerics import evaluate
from .arrays import load_flat, reshape2
from .coordinates import validate as validate_coordinates

FAMILIES=frozenset({"solver","methods","somatic_fitting","allen_fitting","conductance",
"posterior","nonlinear","retina","rnn","evidence_integration","DMS","vision","costs"})
OPERATIONS={
"solver":{"paired_errors","window_summaries"},
"methods":{"bounded_forward","bounded_log_jacobian","regularizer","paired_errors"},
"somatic_fitting":{"window_summaries","paired_errors"},
"allen_fitting":{"window_max","soft_dtw","paired_errors"},
"conductance":{"paired_errors","regularizer"},
"posterior":{"posterior_log_density","quantiles","distance_binned_quantiles","paired_errors"},
"nonlinear":{"paired_errors","classification"},
"retina":{"masked_metrics","pearson","paired_errors","receptive_field_normalize","paired_mean_difference"},
"rnn":{"lyapunov","jacobian_sign","paired_errors"},
"evidence_integration":{"classification","paired_errors","paired_mean_difference"},
"DMS":{"classification","paired_errors","paired_mean_difference"},
"vision":{"classification","pearson","parameter_reset","perturbation_norms","paired_mean_difference"},
"costs":{"paired_errors"}
}

def argument(spec,artifact_map,public_root,target_root,clock,budget,reference_root=None):
    if set(spec)=={"literal"}:
        # Only trusted pinned metric-spec literals, not submitted candidate metrics.
        return spec["literal"]
    require(set(spec)=={"artifact","shape_as"},"metric input descriptor")
    item=artifact_map[spec["artifact"]]
    root=target_root if item["role"]=="operator_target" else public_root
    if item["role"]=="reference_output":
        require(reference_root is not None,"independently collected native reference root")
        root=reference_root
    require(item["role"] in {"candidate_output","reference_output","operator_target"},"unknown metric operand")
    vals=load_flat(root,item["array"],clock=clock,byte_cap=budget["array_bytes"],memory_cap=budget["array_memory"])
    require(spec["shape_as"] in ("matrix","vector","boolean_vector"),"unknown operand layout")
    if spec["shape_as"]=="boolean_vector":
        require(item["array"]["dtype"]=="uint8" and all(x in (0,1) for x in vals),"boolean mask wire values")
        return [bool(x) for x in vals]
    return reshape2(vals,item["array"]["shape"]) if spec["shape_as"]=="matrix" else vals

def score_job(job,contract,artifact_map,public_root,target_root,banks,clock,budget,*,permit,condition,reference_root=None):
    from .barrier import AssessmentPermit
    require(type(permit) is AssessmentPermit,"complete assessment barrier required")
    permit.validate(job,condition)
    collection=next(c for c in permit.commits[condition]["collections"] if c["job_id"]==job["job_id"])
    committed={a["artifact_id"]:a for a in collection["artifacts"]}
    for item in artifact_map.values():
        if item["role"]=="candidate_output":
            a=item["array"];require(a["artifact_id"] in committed,"uncommitted candidate operand")
            require(a==committed[a["artifact_id"]],"candidate scoring operand changed after collection")
        elif item["role"]=="reference_output":
            refs=collection["all_original_stage_collections"][1]["artifacts"]
            require(item["array"] in refs,"reference scoring operand not from observed native producer")
    require(contract["group"]==job["group"],"group metric binding")
    require(digest(canonical_bytes(contract))==job["contract_sha256"],"metric contract changed")
    family=contract["family"];require(family in FAMILIES,"family")
    require(contract.get("native_parity_evidence"),"missing native metric validation")
    outputs=[]
    for metric in contract["metrics"]:
        require(metric["operation"] in OPERATIONS[family],"endpoint not valid forfamily")
        require(metric.get("independent_unit") and metric.get("scientific_definition"),"undefined estimand")
        coordinate_admission=validate_coordinates(metric,artifact_map)
        args=[argument(x,artifact_map,public_root,target_root,clock,budget,reference_root) for x in metric["arguments"]]
        clock.check()
        value=evaluate(banks,metric["operation"],args,metric.get("kwargs"))
        outputs.append({"metric_id":metric["metric_id"],"unit":metric["independent_unit"],
                        "definition":metric["scientific_definition"],"coordinate_admission":coordinate_admission,**value})
    require(outputs or contract.get("nonnumeric_obligation") is True,"empty numerical grade")
    return {"job_id":job["job_id"],"family":family,"metrics":outputs,
            "native_parity_evidence":contract["native_parity_evidence"],
            "scientific_pass":"not_inferred_from_math_agreement",
            "complete_required_metrics":True}

def bind_operands(specification,collection):
    """Join candidate/reference bytes after collection, not guessed future hashes."""
    maps={"candidate_output":{a["artifact_id"]:a for a in collection["artifacts"]},
          "reference_output":{a["artifact_id"]:a for a in collection["all_original_stage_collections"][1]["artifacts"]}}
    out={}
    for name,spec in specification.items():
        role=spec["role"]
        if role in maps:
            require(set(spec)=={"role","artifact_id"},"runtime operand specification")
            require(spec["artifact_id"] in maps[role],"uncollected metric operand")
            out[name]={"role":role,"array":maps[role][spec["artifact_id"]]}
        else:
            require(role=="operator_target" and set(spec)=={"role","array"},"trusted target operand")
            out[name]=spec
    return out

def report(manifest,grades,condition,original_costs):
    require([g["job_id"] for g in grades]==[j["job_id"] for j in manifest["jobs"]],"incomplete grade catalogue")
    require(condition in manifest["conditions"],"condition")
    families={}
    for g in grades:families.setdefault(g["family"],[]).append(g)
    return {"schema":"jaxley_full_paper_family_report_v1","condition":condition,
            "group_count":manifest["group_count"],"job_count":manifest["job_count"],
            "families":families,"aggregate_scientific_scalar":None,
            "actual_original_costs":original_costs,
            "library_assisted_experiment_reconstruction":True,
            "published_data_and_paper_exposure":True,
            "new_canonical_benchmark_ids":0}

