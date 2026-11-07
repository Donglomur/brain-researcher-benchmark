"""Explicit future root authority; no source construction grants execution."""
import re
from pathlib import Path

def selection(s,source):
    fields={'schema','task_id','execution_selected','source','output','public_root','public_manifest','candidate_program','input_review','method_review','runtime_review','image','docker_binary','docker_socket','memory_bytes','other_future_bytes','plan','fit_seconds','adapt_seconds','infer_seconds','prior_seconds','limits','private_grading_authorized'}
    c.need(type(s)is dict and set(s)==fields and s['schema']=='neural014-complete-selection-v1' and s['task_id']=='NEURAL-014' and s['execution_selected']is True and s['source']==source and s['private_grading_authorized']is False,'exact separately selected unscored authority')
    for key in ('output','public_root','docker_binary','docker_socket'):
        p=s[key];c.need(type(p)is str and len(p.encode())<=512 and Path(p).is_absolute() and str(c.path(p))==p,'absolute ordinary selected path')
    for key in ('public_manifest','candidate_program','input_review','method_review','runtime_review'):
        p=s[key];c.need(type(p)is dict and set(p)=={'path','bytes','sha256'},'exact selected operand');c.only_pin(p)
        c.need(type(p['path'])is str and Path(p['path']).is_absolute() and str(c.path(p['path']))==p['path'],'absolute ordinary operand')
    c.need(s['candidate_program']['bytes']<=131072 and s['public_manifest']['bytes']<=packet.JSON_CAP and all(s[k]['bytes']<=65536 for k in ('input_review','method_review','runtime_review')),'bounded explicit operands')
    c.need(re.fullmatch('sha256:[a-f0-9]{64}',s['image']) is not None,'exact operator-selected cached image')
    c.need(type(s['memory_bytes'])is int and s['memory_bytes']>=1073741824 and s['memory_bytes']%1048576==0,'matched selected memory; feasibility separately qualified')
    c.need(type(s['other_future_bytes'])is int and s['other_future_bytes']>=0,'fresh explicit other reservations')
    p=s['plan'];c.need(type(p)is dict and set(p)==packet.PLAN_FIELDS and all(type(v)is int and v>0 for v in p.values()),'exact actual full scalar plan')
    c.need(9<=p['query_count']<p['cases']<=50000 and p['fit_feature_bytes']+p['calibration_feature_bytes']+p['query_feature_bytes']==p['total_feature_bytes']<=packet.NEURAL_CAP and p['max_feature_bytes']<=packet.ARRAY_CAP,'full original interface bounds')
    expected=packet.limits(p,{k:s[k+'_seconds'] for k in ('fit','adapt','infer','prior')})
    c.need(type(s['limits'])is dict and all(type(v)is int for v in s['limits'].values()) and s['limits']==expected,'derived whole2panel resource allowances')
    c.need(c.path(s['public_manifest']['path'])==c.path(s['public_root'])/'PUBLIC.json','exact clean source metadata')
    a,b=c.path(s['output']),c.path(s['public_root']);c.need(a!=b and not a.is_relative_to(b) and not b.is_relative_to(a),'disjoint output and prepared source')
    return s

def reviews(s,source,reference_pin,read):
    rows={k:c.parse(read(s[k]['path'],65536,c.only_pin(s[k]))) for k in ('input_review','method_review','runtime_review')}
    for r in rows.values():c.need(type(r)is dict and r.get('task_id')=='NEURAL-014' and r.get('approved')is True and r.get('source')==source,'separate pinned external review')
    inp=rows['input_review'];c.need(inp.get('schema')=='neural014-full45-input-review-v1' and inp.get('public_manifest')==s['public_manifest'] and inp.get('plan')==s['plan'],'exact whole input review')
    for key in ('all45_sessions_and86_labeled_members','exact_archive_and_native_projection','global_sentence_priority_and_no_refill','all_required_partitions_supported','finite_full512_column_features','source_preprocessing_lineage','sanitized_tree_excludes_query_labels_and_identity_keys','all_query_permutations_independently_recomputed_numpy226','permutation_case_seed_length_and_raw_feature_identity_joined','projection_and_permutation_preparation_costs_retained'):
        c.need(inp.get(key)is True,'original input prerequisite '+key)
    c.need(inp.get('pins_alone_establish_source_lineage')is False,'numeric custody is not native provenance')
    method=rows['method_review'];programs=dict(candidate=c.only_pin(s['candidate_program']),independent_reference=reference_pin)
    c.need(method.get('schema')=='neural014-full45-method-review-v1' and method.get('programs')==programs,'separate exact candidate/reference method reviews')
    for key in ('train_only_fitting_normalization','development_only_selection_no_refit','calibration_only_adaptation','same_full_adapted_model_for_three_ablations','no_query_fitting_or_cross_query_state','no_arm_dependent_inference_algorithm','no_external_lm_or_all_session_weights','source_exposure_history_declared','independent_reference_cannot_be_candidate_replaced'):
        c.need(method.get(key)is True,'scientific method prerequisite '+key)
    c.need(method.get('hashes_prove_chronology')is False,'source hashes not historical training proof')
    run=rows['runtime_review'];profile={k:s[k] for k in ('image','memory_bytes','fit_seconds','adapt_seconds','infer_seconds','prior_seconds','plan','limits')}
    c.need(run.get('schema')=='neural014-full45-runtime-review-v1' and run.get('programs')==programs and run.get('profile')==profile,'exact matched runtime/source profile')
    for key in ('cached_image_numpy226_torch260_cpu','native_and_cli_owned_resources_close','shared_sealed_model_custody','all_phases_original_clock_observed','full_resource_and_host_capacity_qualified'):
        c.need(run.get(key)is True,'future runtime prerequisite '+key)
    c.need(run.get('scientific_qualified')is False and run.get('scoring_authorized')is False,'source producer does not authorize scientific grading')
    return rows
