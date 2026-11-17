"""Four closed public requests and acyclic external root/launch joins."""
from .common import need, pin, encode, parse, descriptor, same

PROGRAMMES = ("NEURAL-056","PAPER-FIND-050","PAPER-paper-method-replacement-016","NEURAL-098")
PROJECTION = ("schema","programme","source_binding","participant","campaign_inputs",
              "resources","output","publication")

def source_check(raw, schemas, catalog, adapter_manifest, meter):
    request = parse(raw, 131072)
    need(type(request) is dict and request.get("programme") in PROGRAMMES, "one canonical programme")
    programme = request["programme"]
    schemas.validate("public", programme, request, meter)
    expected = catalog["programmes"][programme]
    source = request["source_binding"]
    need(source["accepted_manifest"] == expected["source_manifest"] and
         source["accepted_candidate"] == expected["accepted_candidate"] and
         source["adapter_manifest"] == adapter_manifest, "full exact reviewed source identities")
    # No campaign/root/participant/resource/authentic descriptor is dereferenced.
    for name in ("accepted_manifest","accepted_candidate","adapter_manifest"):
        descriptor(source[name])
    return {"request":request,"raw_identity":pin(raw),
            "projection":pin(encode({key:request[key] for key in PROJECTION})),
            "source_check_only":True,"execution_authorized":False}

def bind_root(checked, request_pin, root_pin, root, launch_pin, launch,
              resource_pin, resources, schemas, meter, *, n098_prelaunch_context=None):
    request = checked["request"]
    schemas.validate("authority","root_selection_schema",root,meter)
    schemas.validate("authority","launch_binding_schema",launch,meter)
    schemas.validate("resources","root_resource_plan_schema",resources,meter)
    need({k:request_pin[k] for k in ("bytes","sha256")} == checked["raw_identity"], "actual raw request")
    need(request["root_execution_selection"] == root_pin and
         root["request_projection"] == checked["projection"], "acyclic exact request/root binding")
    need(root["programme"] == request["programme"] == launch["programme"] == resources["programme"],
         "same full canonical programme")
    need(root["source_binding"] == request["source_binding"] and
         launch["adapter_source"] == request["source_binding"]["adapter_manifest"],
         "actual adapter and original source")
    need(launch["request"] == request_pin and launch["root_selection"] == root_pin and
         launch["resource_plan"] == root["resource_plan"] == resource_pin == request["resources"]["selection"],
         "independent launch pins both raw originals and resource plan")
    need(launch["issuer"] == root["issuer"] and launch["campaign_id"] == resources["campaign_id"],
         "same independently selected issuer and campaign")
    need(resources["hard_envelope"]["origin_monotonic_ns"] <
         resources["hard_envelope"]["run_deadline_ns"] <=
         resources["hard_envelope"]["evidence_deadline_ns"], "one original full interval")
    bind_programme(request, root["programme_bindings"],n098_prelaunch_context=n098_prelaunch_context)
    return {"programme":request["programme"],"request":request,"root":root,"launch":launch,"resources":resources,
            "request_pin":request_pin,"root_pin":root_pin,"launch_pin":launch_pin,
            "resource_pin":resource_pin,"structural_joins_only":True}

def bind_programme(request, bindings, *, n098_prelaunch_context=None):
    p, c, u = request["programme"], request["campaign_inputs"], request["participant"]
    if p=="NEURAL-098":
        from .n098_startup import PrelaunchAdmission
        need(type(n098_prelaunch_context) is PrelaunchAdmission,"actual original private N098 prelaunch context")
        n098_prelaunch_context.check_original("request_join")
        need(bindings["startup_authority_bridge"]==n098_prelaunch_context.prelaunch_selection_pin,
             "exact earlier PrelaunchSelection descriptor, never later FinalBindingJoin")
    else:need(n098_prelaunch_context is None,"no N098 context on another original programme")
    if p == "NEURAL-056":
        need(bindings["kind"] == "neural056_root_bindings_v2" and
             bindings["profile"] == bindings["provider_profile"] == c["profile"] == u["profile"] and
             bindings["inputs"] == c["input_manifest"], "exact original N056 profile/provider/input")
    elif p == "PAPER-FIND-050":
        need(bindings["kind"] == "critical_init_root_bindings_v3", "CI repaired source authority")
        for key in ("census","paired_views","improvement_plan"):
            need(bindings[key] == c[key], "CI original input "+key)
        need(bindings["candidate_policy"] == u["candidate_policy"], "same paired candidate policy")
        need([x["stage"] for x in bindings["initial_stage_authorities"]] ==
             ["prepare","independent_reference","native_reference"], "all three supporting stages")
    elif p == "PAPER-paper-method-replacement-016":
        need(bindings["kind"] == "hundred_models_root_bindings_v2", "HM original root branch")
        for key in ("scope","inputs","improvement_plan"):
            need(bindings[key] == c[key], "HM full original "+key)
        need(bindings["submission_A"] == u["A"] and bindings["submission_B"] == u["B"],
             "both separately selected original submissions")
    elif p == "NEURAL-098":
        need(bindings["kind"] == "neural098_root_bindings_v2" and
             bindings["legacy_selection"] == c["legacy_selection"] and
             bindings["prompt"] == u["prompt"] and c["conditions"] == ["A_F","A_I","B_F","B_I"],
             "N098 full four-condition campaign and common prompt")
    else:
        need(False, "closed canonical programme")
