"""Protected family/knowledge-source admission; unknown lineage stays unclean."""
from pathlib import Path
from .io import need,read_json,source_bundle,identity,canonical
from .contract import require_deployment

def admit_family(record,binding,agent_policy):
    need(record["contract"]==binding and record["campaign_agent_policy"]==agent_policy,"Exact exposure/campaign join")
    need(record["family"]=="cogitate-experiment1-MEG"and record["status"]=="independently_audited_clean","Known source-family exposure provenance")
    required=("model_training","parent_checkpoints","prompt_contexts","tool_caches","workspaces","prior_runs","trained_descendants","source_versions","participant_image_overlap")
    need(all(k in record["lineage"]and record["lineage"][k]["coverage"]=="complete_audited"for k in required),"Unknown lineage cannot be called clean")
    for event in record["prior_exposures"]:
        need(event["content_provenance"]and event["source_family"],"Original exposure identity")
        if event["source_family"]=="cogitate-experiment1-MEG":
            need(event["exposure_kind"]=="audited_source_only"and event["no_labels_fitted_states_or_results"]is True,
                 "N098/related-paper labeled packets/results/models contaminate clean N097")
    return identity(canonical(record))

def knowledge_views(root,manifest,binding):
    require_deployment()
    need(manifest["contract"]==binding and manifest["independent_projection_audit"],"Actual audited candidate source view")
    a=manifest["A"];b=manifest["B"]
    need(b["base_files"]==a["base_files"],"Identical A/B base paper/spec material")
    need(a["training_query_tools_and_budget"]==b["training_query_tools_and_budget"],"Equal numerical tools/observations/budget")
    need(a["extra_code"]==[]and b["extra_code"],"Only B adds audited ordinary author source")
    need(manifest["excluded"]==["original_person_rosters","stimulus_identity_dictionaries","fitted_models","reference_predictions","held_out_targets"],"No unsafe whole author repository mount")
    return {"A":source_bundle(root,a["base_files"]),"B":source_bundle(root,b["base_files"]+b["extra_code"]),
            "audit_identity":identity(canonical(manifest))}
