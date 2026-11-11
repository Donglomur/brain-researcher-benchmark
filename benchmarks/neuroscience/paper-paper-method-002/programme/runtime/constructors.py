"""Actual normalized-context joins. Raw native converters remain named, gated producers."""
from .strict import require, number, integer, unique, digest, canonical_bytes
from .errors import SourceGap

def matrix(x, rows, cols, name):
    require(type(x) is list and len(x)==rows,name+" rows")
    for row in x:
        require(type(row) is list and len(row)==cols,name+" columns")
        for v in row:number(v,name)
    return x

def native_lineage(meta, expected, *, claim):
    require(meta.get("schema")=="jaxley_native_constructor_lineage_v1","constructor lineage")
    require(meta.get("claim")==claim,"constructor claim")
    require(meta.get("original_objects")==expected,"original object roster")
    require(meta.get("producer_source") and meta.get("original_attempt") and meta.get("transform_steps"),"unbound normalized input")
    require(meta.get("complete_original_roster") is True,"subset constructor")
    return meta

def retina_context(raw_roi_ids, site_ids, roi_site_edges, fields, rows, split, provenance):
    require(len(unique(raw_roi_ids,"rawROIs"))==232,"232 originalROIs")
    require(len(unique(site_ids,"sites"))==147,"147 modelsites")
    require(len(unique(fields,"scanfields"))==15,"15 scanfields")
    require(type(roi_site_edges) is list and len(roi_site_edges)==232,"fullROI mapping")
    mapping={}
    for roi,site in roi_site_edges:
        require(roi in raw_roi_ids and site in site_ids and roi not in mapping,"badROI mapping")
        mapping[roi]=site
    require(set(mapping)==set(raw_roi_ids) and set(mapping.values())==set(site_ids),"incompleteROI/site mapping")
    expected={(field,index) for field in fields for index in range(1024)}
    actual={(row["field"],row["stimulus_index"]) for row in rows}
    require(len(rows)==len(expected) and actual==expected,"full first1024images perfield")
    ids=[row["row_id"] for row in rows];unique(ids,"stimulus rows")
    for row in rows:
        require(type(row["observed_sites"]) is list,"observed support")
        unique(row["observed_sites"],"observed support")
        require(set(row["observed_sites"])<=set(site_ids),"unknownsite")
    require(set(split)=={"train","validation","test"},"split roles")
    sets=[set(unique(split[k],k)) for k in ("train","validation","test")]
    require(not (sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2]),"split leakage")
    require(set.union(*sets)==set(ids),"split must partition full admittedrows")
    require(provenance.get("rng_history_identity") and provenance.get("filter_lag_average_identity"),"historical RNG/preprocessing unresolved")
    return {"rows":rows,"sites":site_ids,"roi_site_mapping":roi_site_edges,"split":split,
            "historical_preprocessing_prospective":False,"biological_cells":1,
            "native_preparation_provenance":provenance}

def allen_context(cells, observations, profile):
    ids=["485574832","488683425","480353286","473601979"]
    require(cells==ids and set(observations)==set(ids),"allAllen fitting specimens")
    for cell in cells:
        o=observations[cell]
        require(o.get("specimen_id")==cell and o.get("sweep_id") and o.get("timebase"),"native sweep identity")
        require(o.get("morphology_identity") and o.get("stimulus_identity"),"morphology/stimulus")
        require(o.get("voltage_unit")=="mV" and o.get("time_unit")=="ms","nativeunits")
    require(profile.get("short_fit_ms")==200,"native fit interval")
    require(profile.get("long_selection_ms") in (1100,1150),"unrecognized longselection")
    require(profile.get("protocol_conflict_resolution"),"V06/V07 unresolved")
    return {"cells":cells,"observations":observations,"profile":profile,"long_trace_is_unseen_test":False}

def conductance_context(branch_ids, parameter_rows, edges, distances, observation, profile):
    unique(branch_ids,"branches"); require(branch_ids,"empty branches")
    require(len(parameter_rows)==1390,"all1390parameters")
    ids=[p["id"] for p in parameter_rows];unique(ids,"parameters")
    for p in parameter_rows:
        require(p["branch"] in branch_ids and p.get("mechanism") and p.get("unit"),"parameter lineage")
        lo=number(p["lower"]);hi=number(p["upper"]);require(lo<hi,"bounds")
    require(set(distances)==set(ids),"distance perparameter")
    require(type(edges) is list and edges,"native regularization graph")
    seen=set()
    for edge in edges:
        require(type(edge) is list and len(edge)==2 and edge[0] in ids and edge[1] in ids and edge[0]!=edge[1],"invalid neighbor edge")
        pair=tuple(sorted(edge));require(pair not in seen,"duplicate neighbor edge");seen.add(pair)
    for x in distances.values():require(number(x)>=0,"distance")
    require(profile.get("hmc_chains")==200,"allchains")
    require(profile.get("density_coordinate") in ("physical","source_native_untransformed"),"density profile")
    require(profile.get("resolved_V09"),"targetdensity unresolved")
    require(observation.get("every_branch") is True and observation.get("GP_generator_identity"),"fullsynthetic observation")
    return {"branch_ids":branch_ids,"parameters":parameter_rows,"edges":edges,"distances":distances,
            "observation":observation,"profile":profile}

def rnn_context(profile, state_coordinates, trials):
    required={"untrained_gain":(50,None),"EI":(20,None),"DMS":(50,10),"S2":(20,5)}
    name=profile.get("name");require(name in required,"RNNprofile")
    n,inh=required[name];require(profile.get("recurrent_units")==n,"neuron count")
    if inh is not None:require(profile.get("inhibitory_units")==inh,"inhibitory count")
    unique(state_coordinates,"statecoordinates");require(state_coordinates,"complete state")
    require(profile.get("includes_ion_and_gate_states") is True,"no voltage-only state surrogate")
    ids=[t["trial_id"] for t in trials];unique(ids,"trial IDs")
    require(trials or name in ("untrained_gain","S2"),"complete task trials")
    if name=="DMS":require(set(t["pattern"] for t in trials)=={"AA","AB","BA","BB"},"allDMS patterns")
    require(profile.get("source_bound_complete_trial_roster"),"unboundtrialmembership")
    return {"profile":profile,"state_coordinates":state_coordinates,"trials":trials}

def vision_context(image_ids, split, hidden_ids, fit_seeds, attacks, reset_groups, provenance):
    unique(image_ids,"images");require(image_ids,"fullimage roster")
    require(len(unique(hidden_ids,"hidden cells"))==64,"all64hidden cells")
    require(len(unique(fit_seeds["linear"],"linear seeds"))==50,"50linear fits")
    require(len(unique(fit_seeds["MLP"],"MLP seeds"))==50,"50MLP fits")
    require(fit_seeds.get("biophysical"),"nativebiophysical fitroster")
    require(set(split)=={"train","validation","test"},"image split roles")
    parts=[set(unique(split[k],"image "+k)) for k in ("train","validation","test")]
    require(set.union(*parts)==set(image_ids) and not(parts[0]&parts[1] or parts[0]&parts[2] or parts[1]&parts[2]),"image partition/leakage")
    require(len(attacks)==128 and len({x["image_id"] for x in attacks})==128,"128paired attacks")
    for a in attacks:
        require(type(a["target_label"]) is int and 0<=a["target_label"]<10 and type(a["true_label"]) is int and 0<=a["true_label"]<10,"attack digit labels")
        require(a["image_id"] in split["test"] and a["target_label"]!=a["true_label"],"attack membership/target")
    require(reset_groups and provenance.get("complete_native_reset_roster"),"reset groups")
    require(provenance.get("parameter_roster_identity") and provenance.get("native_image_source"),"native source")
    return {"image_ids":image_ids,"split":split,"hidden_ids":hidden_ids,"fit_seeds":fit_seeds,
            "attacks":attacks,"reset_groups":reset_groups,"provenance":provenance}

def require_raw_converter(binding, expected_id):
    """No generic normalized-array callback is accepted as original preparation."""
    if binding is None:
        raise SourceGap("Unimplemented/unadmitted native raw converter: "+expected_id)
    require(binding.get("producer_id")==expected_id and binding.get("kind")=="native_constructor","converter identity")
    require(binding.get("source") and binding.get("output_contract") and binding.get("qualification_evidence"),"converter source closure")
    return binding

def solver_context(cells, stimuli, sites, timebase, native):
    require(len(unique(cells,"solver cells"))==5,"CA1 and four solver cells")
    require(set(sites)==set(cells),"every morphology has sites")
    for values in sites.values():require(len(unique(values,"solver sites"))==3,"three sites")
    expected=[round(.2+.1*i,1) for i in range(10)]
    import math
    require(type(stimuli) is list and len(stimuli)==len(expected),"all ten native amplitudes")
    for supplied,target in zip(stimuli,expected):
        value=number(supplied,"finite stimulus amplitude")
        # Four ULPs cover ordinary binary64 .2+.1*i construction error;
        # this is representation tolerance, not a new experimental amplitude bin.
        require(abs(value-target)<=4*math.ulp(target),"off-grid native amplitude")
    require(timebase.get("unit")=="ms" and number(timebase.get("dt"))>0,"explicit solver clock")
    require(native.get("NEURON_mechanism_manifest") and native.get("Jaxley_mechanism_manifest") and native.get("morphology_manifest"),"both native simulators and morphology sources")
    return {"cells":cells,"stimuli_nA":stimuli,"sites":sites,"timebase":timebase,"native":native}

def nonlinear_context(rows, split, profile):
    require(rows and type(rows) is list,"complete native input support")
    ids=unique([r["id"] for r in rows],"nonlinear rows")
    for r in rows:
        require(type(r["input"]) is list and len(r["input"])==2,"two inputs")
        for x in r["input"]:number(x)
        require(number(r["target_mV"]) in (-70.,35.),"native voltage targets")
    require(profile.get("branches")==3 and profile.get("compartments")==12 and profile.get("parameters")==72,"native nonlinear architecture")
    require(profile.get("source_roster_pin") and profile.get("count_inferred_from_table") is False,"do not infer 32 examples from table")
    require(number(profile.get("readout_ms"))==3.,"readout at 3ms")
    parts=[set(unique(split[k],k)) for k in ("train","validation","test")]
    require(set.union(*parts)==set(ids) and not(parts[0]&parts[1] or parts[0]&parts[2] or parts[1]&parts[2]),"nonlinear partition")
    return {"rows":rows,"split":split,"profile":profile}

def methods_context(parameter_rows, checkpoints, truncation_ms, native):
    ids=unique([p["id"] for p in parameter_rows],"method parameters")
    require(ids,"parameter groups")
    for p in parameter_rows:
        require(number(p["lower"])<number(p["upper"]) and p.get("unit"),"explicit bounded units")
        require(p.get("group") and p.get("optimizer"),"per-group optimizer")
    require(checkpoints and all(type(c) is int and c>0 for c in checkpoints),"complete checkpoint scheme")
    require(truncation_ms==[50,100,150],"native truncation cuts")
    require(native.get("zero_gradient_policy") and native.get("state_ABI") and native.get("Polyak_loss_scale"),"native optimizer/state definitions")
    return {"parameters":parameter_rows,"checkpoints":checkpoints,"truncation_ms":truncation_ms,"native":native}

