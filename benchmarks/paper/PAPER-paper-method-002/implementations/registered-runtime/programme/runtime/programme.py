"""Full paper producer DAG and concrete artifact contracts from original coordinates.

This does not turn an unknown native generator into a callback. Every unsupplied
source/coordinate/exporter is enumerated before an authentic invocation can exist.
"""
from .strict import require, unique, canonical_bytes, digest, integer
from .profiles import GROUPS
from .errors import SourceGap
from .arrays import DTYPES

# Roles are complete scientific products, not a single convenient headline score.
PRODUCTS={
"J01":("architecture_source_map",),
"J02":("Jaxley_voltage","NEURON_voltage","spike_times","spike_amplitudes","clock"),
"J03":("cold_compile_times","warm_times","peak_memory","gradient_times"),
"J04":("full_state","voltage","parameter_gradient","connectivity","timing_memory"),
"J05":("full_state","parameter_gradient","selected_12_loss","connectivity","timing_memory"),
"J06":("physical_parameters","untransformed_parameters","derivative","log_Jacobian","bounds"),
"J07":("loss_gradient","per_group_updates","learning_rate","zero_gradient_policy"),
"J08":("full_gradient","checkpoint_gradient","recompute_counts","peak_memory"),
"J09":("boundary_state_before","boundary_state_after","gradient_cuts","full_voltage"),
"J10":("full_voltage","four_summaries","parameters","loss_trajectory","simulation_count","time_to_055"),
"J11":("full_voltage","soft_DTW","spike_count","spike_times","spike_amplitudes","best_final_hof_lineage","resource_trajectory"),
"J12":("whole_branch_voltage","parameters_1390","regularizer","loss_trajectory","GA_comparison"),
"J13":("chains_200_transitions_500","log_density","acceptance","last_samples","distance_bin_quantiles","mixing_calibration"),
"J14":("all_input_voltage","decision_surface","class_predictions","GD_GA_trajectory"),
"J15":("anatomy_parameter_map","mechanism_state_map","observation_transform"),
"J16":("full_site_predictions","observation_mask","site_metrics","split_lineage"),
"J17":("all_branch_calcium","site_voltage","site_calcium","stimulus"),
"J18":("experimental_RF","model_RF","normalized_RF","contours","ASD_evidence_trajectory"),
"J19":("train_predictions","validation_predictions","test_predictions","correlations","SEM_tests","learning_curve"),
"J20":("network_mechanism_map","initial_state","connectivity","parameter_map"),
"J21":("full_state","voltage","Lyapunov_norms","QR_step_counts","maximal_Lyapunov"),
"J22":("test_logits","trial_labels","psychometric_responses","input_weights","recurrent_weights","output_weights","voltage_readout"),
"J23":("positive_trial_readout","negative_trial_readout","three_second_timecourses"),
"J24":("pattern_delay_logits","trial_labels","complete_voltage","raster","readout","curriculum_loss"),
"J25":("full_ion_gate_state","Hann40ms_smoothed","normalized_state","PCA_projection","PCA_basis"),
"J26":("architecture_map","full_logits","hidden_voltage","parameter_map"),
"J27":("full_test_logits","image_labels","fit_history","fit_parameter_identity"),
"J28":("initial_parameters","trained_parameters","reset_parameters","reset_logits","reset_membership"),
"J29":("clean_images","attacked_images","target_labels","true_labels","attacked_logits","norm_curve","optimizer_history"),
"J30":("all64_tuning","stimulus_identity","full_response"),
"J31":("input_weights","mechanism_parameters","parameter_correlations"),
"J32":("runtime_repeats","ratio","hardware_workload","availability_reason"),
"J33":("full_Jacobian","Jacobian_sign","all20_unit_state"),
"J34":("input","readout","raster","full_voltage_both_classes"),
"J35":("nine_table_rows","observed_operation_counts","observed_resources"),
"J36":("eight_notes_source_map","native_method_tests",),
}

DEPENDENCIES={"J08":["J01"],"J09":["J15"],"J13":["J12"],"J16":["J15"],
"J17":["J15"],"J18":["J16"],"J19":["J15"],"J21":["J20"],"J22":["J20"],
"J23":["J22"],"J24":["J20"],"J25":["J24"],"J27":["J26"],"J28":["J27"],
"J29":["J27"],"J30":["J27"],"J31":["J27"],"J33":["J20"],"J34":["J22"],
"J35":["J03","J10","J11","J12","J14","J19","J22","J24","J27"],
"J36":["J06","J07","J08","J09"]}

def graph(obligations, source_bindings):
    rows=obligations["required_groups"]
    require([r["id"] for r in rows]==list(GROUPS),"all 36 original obligations")
    nodes=[];gaps=[]
    for row in rows:
        group=row["id"];bindings=source_bindings.get(group,{})
        for role in ("constructor","reference","exporter","native_comparator"):
            b=bindings.get(role)
            if not b or b.get("implemented") is not True or not b.get("source_pin") or not b.get("entrypoint"):
                gaps.append({"group":group,"role":role,"missing":(b or {}).get("missing","exact complete source producer not supplied")})
        nodes.append({"group":group,"family":row["family"],"panels":row["panels"],
                      "operation":row["operation"],"unit":row["experimental_unit"],
                      "required_metric_labels":row["metrics"],"products":list(PRODUCTS[group]),
                      "dependencies":DEPENDENCIES.get(group,[]),"producers":bindings,
                      "source_locations":row["primary_locations"],"required":True})
    return {"schema":"jaxley_full_native_producer_graph_v1","nodes":nodes,
            "software_gaps":gaps,"whole_programme_native_implementation_complete":not gaps,
            "native_execution_performed":False}

def ordered_groups():
    out=[];remaining=set(GROUPS)
    while remaining:
        ready=[g for g in GROUPS if g in remaining and set(DEPENDENCIES.get(g,[]))<=set(out)]
        require(ready,"producer graph cycle")
        out+=ready;remaining-=set(ready)
    return out

def build_contracts(programme, exact_coordinates, metric_specs):
    """Coordinates and metric source definitions must be operator-native admissions.

    There is deliberately no inferred time dimension, unknown morphology ID,
    substituted seed, omitted product, or invented empty 'successful' output.
    """
    if programme["software_gaps"]:
        raise SourceGap("Unimplemented native producers: "+",".join(x["group"]+":"+x["role"] for x in programme["software_gaps"]))
    require(set(exact_coordinates)==set(GROUPS) and set(metric_specs)==set(GROUPS),"full native coordinate/metric roster")
    result={}
    for n in programme["nodes"]:
        group=n["group"];products=exact_coordinates[group]
        require(set(products)==set(PRODUCTS[group]),"every scientific product required: "+group)
        outputs=[]
        for role in PRODUCTS[group]:
            p=products[role]
            require(p.get("native_source_pin") and p.get("lineage"),"unresolved native output "+role)
            require(p.get("format") in ("json","jaxley-flat-numeric-v1"),"output format")
            axes=p.get("axes");require(type(axes) is list,"native coordinate axes")
            shape=[]
            for axis in axes:unique(axis,"native axis");require(axis,"nonempty native axis");shape.append(len(axis))
            if p["format"]=="jaxley-flat-numeric-v1":
                require(shape and p.get("dtype") in DTYPES,"numeric contract")
            else:require(p.get("dtype") is None,"JSON has no numeric dtype")
            outputs.append({"artifact_id":role,"format":p["format"],"dtype":p.get("dtype"),
                            "shape":shape,"axes":axes,"unit":p["unit"],"semantic_role":role,
                            "lineage":p["lineage"],"native_source_pin":p["native_source_pin"]})
        metrics=metric_specs[group]
        require(metrics.get("required_metric_labels")==n["required_metric_labels"],"native metric coverage")
        require(metrics.get("native_parity_evidence"),"independent/native comparison evidence")
        require(metrics.get("coverage")=="complete_native_family","no headline-only metric surrogate")
        for metric in metrics["metrics"]:
            require(metric.get("coordinate_contract",{}).get("schema")=="jaxley_metric_coordinates_v1","native metric coordinate contract missing")
            require(metric.get("kwargs") in (None,{}),"metric kwargs cannot bypass positional coordinate admission")
        result[group]={"group":group,"family":n["family"],"outputs":outputs,
                       "required_metric_labels":n["required_metric_labels"],
                       "metrics":metrics["metrics"],"native_parity_evidence":metrics["native_parity_evidence"],
                       "nonnumeric_obligation":metrics.get("nonnumeric_obligation",False),
                       "native_comparator":n["producers"]["native_comparator"]}
        labels=[label for m in metrics["metrics"] for label in m.get("covers_labels",[])]
        require(set(labels)==set(n["required_metric_labels"]),"unimplemented native scientific endpoint")
    return result
