"""Full54 prospective SSVEP program authority; no template grants execution."""
from pathlib import Path
MODES=('candidate','cca','constant','frequency-permuted')
SCOPE=dict(people=54,outer_folds=54,queries_per_fold=400,training_per_fold=21200,one_frozen_program=True,prospective_block_mean_lopo=True,query_batch_fitting=False)

def limits(plan,candidate_seconds,reference_seconds):
    c.need(type(candidate_seconds)is int and 60<=candidate_seconds<=1800 and type(reference_seconds)is int and 60<=reference_seconds<=900,'explicit bounded per-phase clocks')
    c.need(type(plan)is dict and set(plan)=={'contexts','query_count','training_per_context','files','public_bytes','max_fold_bytes'} and all(type(v)is int for v in plan.values()),'exact scalar full54 plan')
    c.need(plan['contexts']==54 and plan['query_count']==21600 and plan['training_per_context']==21200 and plan['files']==216,'original full54 scope')
    c.need(18662400000<plan['public_bytes']<=54*352000000 and 345600000<plan['max_fold_bytes']<=352000000,'full candidate input including all training arrays')
    return dict(reads=16*plan['public_bytes']+216*16000000+512000000,writes=plan['public_bytes']+216*1000000+32000000,retained=1073741824,observer_reads=320000000,observer_seconds=600,whole_seconds=54*(candidate_seconds+3*reference_seconds+4*130+180)+1800)

def selection(s,source):
    fields={'schema','execution_selected','task_id','repository','output','program','source','public_root','public_manifest','preparation','input_review','method_review','runtime_review','docker_binary','docker_socket','candidate_seconds','reference_seconds','memory_bytes','other_future_bytes','plan','limits','private_grading_authorized'}
    c.need(type(s)is dict and set(s)==fields and s['schema']=='neural084-full54-selection-v1' and s['execution_selected']is True and s['task_id']=='NEURAL-084' and s['source']==source and s['private_grading_authorized']is False,'exact full54 selected authority')
    for k in ('repository','output','public_root','docker_binary','docker_socket'):
        c.need(type(s[k])is str and len(s[k].encode())<=512 and Path(s[k]).is_absolute() and str(Path(s[k]))==s[k],'canonical literal path');c.path(s[k])
    for k in ('program','public_manifest','preparation','input_review','method_review','runtime_review'):
        p=s[k];c.need(type(p)is dict and set(p)=={'path','bytes','sha256'} and type(p['path'])is str and Path(p['path']).is_absolute() and str(Path(p['path']))==p['path'],'exact absolute input descriptor');c.path(p['path']);c.only_pin(p)
        c.need(p['bytes']<=(131072 if k in ('program','public_manifest') else 32768),'bounded authority')
    c.need(type(s['memory_bytes'])is int and 1073741824<=s['memory_bytes']<=4294967296 and s['memory_bytes']%1048576==0,'candidate memory explicit; adequacy unmeasured')
    c.need(type(s['other_future_bytes'])is int and s['other_future_bytes']>=0,'fresh OTHER')
    c.need(type(s['limits'])is dict and all(type(v)is int for v in s['limits'].values()) and s['limits']==limits(s['plan'],s['candidate_seconds'],s['reference_seconds']),'full cumulative resource derivation')
    c.need(c.path(s['public_manifest']['path'])==c.path(s['public_root'])/'INPUT_INDEX.json','one selected index')
    out=c.path(s['output']);inp=c.path(s['public_root']);c.need(out!=inp and not out.is_relative_to(inp) and not inp.is_relative_to(out),'disjoint output and public source')
    return s

def reviews(s,source,binding,read):
    def one(k):r=s[k];return c.parse(read(r['path'],32768,c.only_pin(r)))
    inp,method,runtime,panel=(one(k) for k in ('input_review','method_review','runtime_review','preparation'))
    for v in (inp,method,runtime):c.need(type(v)is dict and v.get('task_id')=='NEURAL-084' and v.get('approved')is True and v.get('source')==source,'external source-bound root prerequisite')
    c.need(inp.get('schema')=='neural084-complete-input-review-v1' and inp.get('public_manifest')==s['public_manifest'] and inp.get('preparation')==s['preparation'] and inp.get('plan')==s['plan'],'full input evidence binding')
    for k in ('all108_originals_and216_phase_joins_verified','all54_training_and_query_partitions_verified','channel_order_rate_onsets_and_half_open_blocks_verified','all_float32_shapes_and_finite_values_verified','opaque_ID_order_and_private_gold_join_verified','original_source_and_projection_provenance_verified'):
        c.need(inp.get(k)is True,'complete authentic preparation must be independently admitted')
    c.need(inp.get('pins_alone_prove_original_authenticity')is False and inp.get('matlab_pipeline_parity_claimed')is False,'prospective representation, not inferred native parity')
    c.need(type(panel)is dict and set(panel)=={'schema','task_id','scope','input_index','projection','full_source_authenticity_admitted'} and panel['schema']=='neural084-preparation-admission-v1' and panel['task_id']=='NEURAL-084' and panel['scope']==SCOPE and panel['input_index']==s['public_manifest'] and panel['full_source_authenticity_admitted']is True,'full root preparation admission')
    c.need(type(panel['projection'])is dict and set(panel['projection'])=={'path','bytes','sha256'},'retained preparation receipt descriptor');c.path(panel['projection']['path']);c.only_pin(panel['projection'])
    c.need(method.get('schema')=='neural084-fixed-program-method-review-v1' and method.get('program')==c.only_pin(s['program']) and method.get('mode')=='frozen_program','one source-committed method')
    for k in ('policy_fixed_before_all_outer_queries','training_only_transforms_grouped_inner_selection','no_target_person_calibration_or_query_batch_fitting','no_cross_fold_or_sibling083_state','all21600_predictions_and_four_raw_scores','per_epoch_frozen_calculation_only','all_three_fixed_reference_modes_retained','source_exposure_history_attested'):
        c.need(method.get(k)is True,'original task access and comparison obligations')
    c.need(method.get('hashes_prove_chronology')is False,'chronology requires external evidence')
    c.need(runtime.get('schema')=='neural084-full54-runtime-review-v1' and runtime.get('image')==binding['image'] and runtime.get('profile')=={k:s[k] for k in ('candidate_seconds','reference_seconds','memory_bytes','plan','limits')} and runtime.get('program')==c.only_pin(s['program']),'same runtime profile')
    for k in ('offline_isolation_and_all_native_closure_qualified','full54_packet_custody_and_retirement_qualified','host_memory_and_original_clock_qualified','fixed_cached_image_and_dependencies_qualified','fixed_reference_source_and_native_arithmetic_qualified'):
        c.need(runtime.get(k)is True,'separate real runtime qualification required')
    c.need(runtime.get('scientific_qualified')is False and runtime.get('numeric_scoring_authorized')is False,'no grade authorization')
    return panel
