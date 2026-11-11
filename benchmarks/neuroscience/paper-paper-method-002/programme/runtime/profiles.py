"""Scientific conflicts never receive convenient defaults."""
from .errors import SourceGap
from .strict import require, unique

CONDITIONS = ("A_R","B_R","A_I","B_I")
GROUPS = tuple("J%02d"%i for i in range(1,37))
CONFLICTS = tuple("V%02d"%i for i in range(1,17))
GATES = tuple("G%02d"%i for i in range(1,22))
ALLEN = ("485574832","488683425","480353286","473601979")
SIZES = (32,64,128,256,512)

def admit_profile(p, expected_design_sha):
    require(p.get("schema")=="jaxley_scientific_profile_v1", "scientific profile schema")
    require(p.get("design_sha256")==expected_design_sha, "unadopted scientific scope")
    require(p.get("task_id")=="PAPER-paper-method-002", "canonical task")
    require(p.get("common_simulator")=="library_assisted_Jaxley", "A/B interpretation changed")
    require(tuple(p.get("conditions",()))==CONDITIONS, "all four conditions required")
    require(tuple(p.get("required_groups",()))==GROUPS, "whole paper roster required")
    require(set(p.get("conflicts",{}))==set(CONFLICTS), "full conflict roster required")
    missing=[]
    for key,row in p["conflicts"].items():
        if row.get("status") not in ("reconciled","separate_profiles"):
            missing.append(key)
        else:
            require(row.get("primary_sources") and row.get("resolution_source") and row.get("reason"), "unsupported conflict resolution")
            if row["status"]=="separate_profiles":
                require(row.get("historical_equivalence") is False, "unresolved profiles cannot claim equivalence")
    require(set(p.get("gates",{}))==set(GATES), "full gate roster required")
    missing += [k for k,v in p["gates"].items() if v.get("status")!="accepted" or not v.get("evidence")]
    if missing: raise SourceGap("Required evidence not admitted: "+",".join(sorted(missing)))
    r=p["rosters"]
    require(tuple(r.get("allen_fitting_cells",()))==ALLEN, "all four exact Allen fitting cells required")
    for key,n in (("retinal_scanfields",15),("retinal_raw_rois",232),("retinal_sites",147),("retinal_small_fields",7),("linear_fit_seeds",50),("mlp_fit_seeds",50),("attack_example_ids",128)):
        vals=unique(r.get(key),key); require(len(vals)==n,key+" incomplete")
    require(set(r["retinal_small_fields"])<=set(r["retinal_scanfields"]), "small-field lineage")
    require(tuple(r.get("retinal_train_sizes",()))==SIZES, "all five retinal sizes")
    require(r.get("hmc_chains")==200 and r.get("hidden_neurons")==64, "full inference/vision dimension")
    require(r.get("DMS_patterns")==["AA","AB","BA","BB"], "four DMS patterns required")
    for key in ("solver_cells","solver_main_batch_sizes","gain_grid","psychometric_grid","biophysical_fit_seeds","reset_groups","attack_norm_grid"):
        require(type(r.get(key)) is list and r[key], "missing native roster "+key)
        unique(r[key], key)
    require(len(r["solver_cells"])==5, "CA1 plus four solver morphologies")
    require(p.get("published_test_exposure_disclosed") is True, "public exposure declaration")
    require(p.get("historical_retina_preprocessing_prospective") is False, "historical preprocessing is not prospective")
    return p

