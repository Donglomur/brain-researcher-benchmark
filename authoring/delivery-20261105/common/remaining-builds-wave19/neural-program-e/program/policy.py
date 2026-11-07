"""Explicit full-input, scientific-method and runtime prerequisites; no activation."""
import re
from pathlib import Path

def selection(s,source):
    fields={'schema','task_id','execution_selected','source','output','public_root','public_manifest','candidate_program','input_review','method_review','runtime_review','image','docker_binary','docker_socket','memory_bytes','other_future_bytes','plan','fit_seconds','infer_seconds','limits','private_grading_authorized'}
    c.need(type(s)is dict and set(s)==fields and s['schema']=='neural089-complete-selection-v1' and s['task_id']=='NEURAL-089' and s['execution_selected']is True and s['source']==source and s['private_grading_authorized']is False,'separately selected unscored authority')
    for key in ('output','public_root','docker_binary','docker_socket'):
        p=s[key];c.need(type(p)is str and len(p.encode())<=512 and Path(p).is_absolute() and str(c.path(p))==p,'absolute ordinary selected path')
    for key in ('public_manifest','candidate_program','input_review','method_review','runtime_review'):
        p=s[key];c.need(type(p)is dict and set(p)=={'path','bytes','sha256'},'exact operand');c.only_pin(p)
        c.need(type(p['path'])is str and Path(p['path']).is_absolute() and str(c.path(p['path']))==p['path'],'absolute operand')
    c.need(s['candidate_program']['bytes']<=131072 and s['public_manifest']['bytes']<=packet.JSON_CAP and all(s[k]['bytes']<=65536 for k in ('input_review','method_review','runtime_review')),'bounded operands')
    c.need(type(s['image'])is str and re.fullmatch('sha256:[a-f0-9]{64}',s['image']),'exact cached image')
    c.need(type(s['memory_bytes'])is int and s['memory_bytes']>=1073741824 and s['memory_bytes']%1048576==0,'explicit matched memory; no feasibility claim')
    c.need(type(s['other_future_bytes'])is int and s['other_future_bytes']>=0,'fresh OTHER')
    p=s['plan'];c.need(type(p)is dict and set(p)==packet.PLAN_FIELDS and all(type(v)is int and v>0 for v in p.values()),'complete scalar plan')
    c.need(p['cases']==p['training_count']+p['development_count']+p['query_count']<=2_000_000 and p['training_count']>=88 and p['development_count']>=1 and p['query_count']<=200000 and p['fit_files']==89 and p['query_files']==1,'original complete support')
    c.need(p['fit_feature_bytes']+p['query_feature_bytes']==p['total_feature_bytes']<=packet.NEURAL_CAP,'complete feature coverage')
    expected=packet.limits(p,{k:s[k+'_seconds'] for k in ('fit','infer')})
    c.need(type(s['limits'])is dict and all(type(v)is int for v in s['limits'].values()) and s['limits']==expected,'derived whole-panel resource bounds')
    c.need(c.path(s['public_manifest']['path'])==c.path(s['public_root'])/'PUBLIC.json','exact source metadata')
    a,b=c.path(s['output']),c.path(s['public_root']);c.need(a!=b and not a.is_relative_to(b) and not b.is_relative_to(a),'disjoint output/source')
    return s

def reviews(s,source,reference_pin,read):
    rows={k:c.parse(read(s[k]['path'],65536,c.only_pin(s[k]))) for k in ('input_review','method_review','runtime_review')}
    for r in rows.values():c.need(type(r)is dict and r.get('task_id')=='NEURAL-089' and r.get('approved')is True and r.get('source')==source,'independent exact review')
    inp=rows['input_review'];c.need(inp.get('schema')=='neural089-full90-input-review-v1' and inp.get('public_manifest')==s['public_manifest'] and inp.get('plan')==s['plan'],'full input review')
    for k in ('exact90_original_source_keys_and_asset_pins','all_original_eligible_events_and_no_skips','train_only_continuous_normalization','exact306_by125_clock_channel_alignment','exact_original_prepared_row_order','source_and_prepared_projection_lineage','label_free_runtime_membership_receipt','within_run_permutations_independently_recomputed','same_permutations_for_candidate_reference','prior_counts_all88_training_only','query_targets_and_source_metadata_absent_from_runtime_tree','full_preparation_costs_retained'):
        c.need(inp.get(k)is True,'input prerequisite '+k)
    c.need(inp.get('pins_alone_establish_source_lineage')is False,'hashes are not native provenance')
    programs=dict(candidate=c.only_pin(s['candidate_program']),independent_reference=reference_pin)
    method=rows['method_review'];c.need(method.get('schema')=='neural089-full90-method-review-v1' and method.get('programs')==programs,'exact method roles')
    for k in ('both_programs_fixed_before_any_numerical_exposure','development_only_selects_no_estimator_or_normalizer_fit','reference_uses_training_only_fixed_recipe','no_query_fitting_or_cross_query_state','same_inference_rule_for_MEG_and_ZERO','no_external_transcript_audio_or_label_lookup','source_exposure_history_declared','prior_has_counts_only','independent_reference_not_candidate_replaced','same_MEG_model_for_ZERO','single_window_adaptation_separately_reviewed'):
        c.need(method.get(k)is True,'method prerequisite '+k)
    c.need(method.get('hashes_prove_chronology')is False,'source hashes not chronology')
    r=rows['runtime_review'];profile={k:s[k] for k in ('image','memory_bytes','fit_seconds','infer_seconds','plan','limits')}
    c.need(r.get('schema')=='neural089-full90-runtime-review-v1' and r.get('programs')==programs and r.get('profile')==profile,'exact runtime/source profile')
    for k in ('cached_image_numpy226_sklearn161','native_and_cli_owned_resources_close','sealed_model_and_single_query_custody','all_phases_original_clock_observed','full_resource_host_capacity_and_memory_qualified'):
        c.need(r.get(k)is True,'runtime prerequisite '+k)
    c.need(r.get('scientific_qualified')is False and r.get('scoring_authorized')is False,'construction not scientific authority')
    return rows
