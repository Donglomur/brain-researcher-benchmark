"""Source-specific native invocation recipes, not replacement scientific methods.

The pinned original functions do real work. Missing imports, native objects,
working directories and full exporters remain blockers before these recipes run.
"""
from .strict import require, integer, number
from .profiles import ALLEN

REVISION="5e7a86282adb9d4603b5546ac5d8dad59aec7cc0"
PREFIX="nex/fig3_l5pc/notebooks/03_allen_fits/"

def allen_reference(method, context):
    require(method in ("GD","GA"),"original Allen method")
    require(context["setup"] in ALLEN,"one of four exact specimens")
    required=("seed","setup","observation","t_max","n_particles")
    args={k:context[k] for k in required}
    integer(args["seed"],"optimization seed");integer(args["n_particles"],"particles",1)
    require(args["observation"]=="allen" and number(args["t_max"])>0,"native observed context")
    require(context.get("resolved_V06") and context.get("resolved_V07") and context.get("fixed_import_manifest"),"source conflicts/imports unresolved")
    if method=="GD":
        args.update({k:context[k] for k in ("steps","lr","momentum","cost_fn_power")})
        integer(args["steps"],"GD iterations",1)
        for k in ("lr","momentum","cost_fn_power"):number(args[k],k)
        path=PREFIX+"gradient_descent/run_gd.py"
    else:
        # The original CLI advertises mcmc flags that are never passed to main.
        # Preserve the actual function ABI, and do not bill those flags as work.
        args["smc_steps"]=integer(context["smc_steps"],"GA generations",1)
        path=PREFIX+"genetic_algo/run_ga.py"
    require(context.get("original_workdir") and context.get("complete_result_exporter_pin"),"native result exporter/workdir missing")
    return {"upstream_revision":REVISION,"source_path":path,"function":"main","kwargs":args,
            "working_directory":context["original_workdir"],"exporter_pin":context["complete_result_exporter_pin"],
            "actual_native_execution":False,"scope":"one explicit native operation; full catalogue required"}

def posterior_density_recipe(profile):
    scale=number(profile["laplace_scale"],"Laplace scale");require(scale>0,"positive likelihood scale")
    require(profile["regularizer_coordinate"] in ("physical","source_native_untransformed"),"R coordinate")
    require(profile.get("resolved_V09") and profile.get("source_pin"),"posterior derivation source")
    require(profile["chains"]==200 and profile["posterior_transitions"]==500 and profile["integration_steps"]==5,"full paper HMC support")
    return {"formula":"-MAE / scale - R + log_abs_det_J","scale":scale,
            "equivalent_energy_before_J":"MAE + scale * R",
            "relative_R_weight":scale,"regularizer_coordinate":profile["regularizer_coordinate"],
            "prior_stage":profile["prior_stage"],"source_pin":profile["source_pin"],
            "historical_coordinate_equivalence":profile["historical_coordinate_equivalence"]}
