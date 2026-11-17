"""Separate canonical-store/full54 sequential authority; no inherited v1 admission."""
from pathlib import Path
MODES=('candidate','cca','constant','frequency-permuted')
SCOPE=dict(people=54,outer_folds=54,queries_per_fold=400,training_per_fold=21200,one_frozen_program=True,prospective_block_mean_lopo=True,query_batch_fitting=False,two_phase_train_seal_infer=True)
MODEL_CAP=536870912

def limits(plan,fit_seconds,infer_seconds,reference_seconds):
    c.need(type(plan)is dict and set(plan)=={'contexts','query_count','phase_arrays','canonical_payload_bytes','canonical_total_bytes'} and all(type(v)is int for v in plan.values()),'exact canonical scalar plan')
    c.need(plan['contexts']==54 and plan['query_count']==21600 and plan['phase_arrays']==216 and plan['canonical_payload_bytes']==345600000 and 345600000<plan['canonical_total_bytes']<=360000000,'full original canonical store')
    for t in (fit_seconds,infer_seconds,reference_seconds):c.need(type(t)is int and 60<=t<=1800,'bounded selected phase seconds')
    return dict(reads=54*(8*345600000+4*MODEL_CAP+1000000000+4*16000000)+1000000000,writes=54*(345600000+MODEL_CAP)+270000000+32000000,retained=1610612736,observer_reads=360000000,observer_seconds=900,whole_seconds=54*(fit_seconds+infer_seconds+3*reference_seconds+5*130+240)+2400)

def selection(s,source):
    fields={'schema','execution_selected','task_id','repository','output','program','source','canonical_root','pool','preparation','input_review','method_review','runtime_review','docker_binary','docker_socket','fit_seconds','infer_seconds','reference_seconds','memory_bytes','other_future_bytes','plan','limits','private_grading_authorized'}
    c.need(type(s)is dict and set(s)==fields and s['schema']=='neural084-sequential-selection-v2' and s['execution_selected']is True and s['task_id']=='NEURAL-084' and s['source']==source and s['private_grading_authorized']is False,'exact newly selected sequential authority')
    for k in ('repository','output','canonical_root','docker_binary','docker_socket'):
        c.need(type(s[k])is str and len(s[k].encode())<=512 and Path(s[k]).is_absolute() and str(Path(s[k]))==s[k],'canonical bounded paths');c.path(s[k])
    for k in ('program','pool','preparation','input_review','method_review','runtime_review'):
        p=s[k];c.need(type(p)is dict and set(p)=={'path','bytes','sha256'} and type(p['path'])is str and Path(p['path']).is_absolute() and str(Path(p['path']))==p['path'],'exact absolute pin');c.path(p['path']);c.only_pin(p)
        c.need(p['bytes']<=(5000000 if k=='pool' else 131072 if k=='program' else 32768),'bounded authority')
    c.need(type(s['memory_bytes'])is int and 1073741824<=s['memory_bytes']<=4294967296 and s['memory_bytes']%1048576==0,'selected unqualified native memory')
    c.need(type(s['other_future_bytes'])is int and s['other_future_bytes']>=0,'fresh OTHER')
    c.need(type(s['limits'])is dict and all(type(v)is int for v in s['limits'].values()) and s['limits']==limits(s['plan'],s['fit_seconds'],s['infer_seconds'],s['reference_seconds']),'270-phase cumulative resource profile')
    root=c.path(s['canonical_root']);out=c.path(s['output']);c.need(c.path(s['pool']['path'])==root/'pool.json' and root!=out and not root.is_relative_to(out) and not out.is_relative_to(root),'disjoint canonical store and sole owned attempt')
    return s

def reviews(s,source,binding,read):
    def one(k):r=s[k];return c.parse(read(r['path'],32768,c.only_pin(r)))
    inp,method,runtime,panel=(one(k) for k in ('input_review','method_review','runtime_review','preparation'))
    for v in (inp,method,runtime):c.need(type(v)is dict and v.get('task_id')=='NEURAL-084' and v.get('approved')is True and v.get('source')==source,'root-bound source-specific authority')
    c.need(inp.get('schema')=='neural084-canonical-input-review-v2' and inp.get('pool')==s['pool'] and inp.get('preparation')==s['preparation'] and inp.get('plan')==s['plan'],'full canonical evidence binding')
    for k in ('all108_original_and216_phase_joins_verified','canonical_row_label_identity_join_verified','channel_rate_onsets_and_half_open_blocks_verified','all_float32_C_order_shapes_and_finite_values_verified','original_projection_and_generation_provenance_verified'):
        c.need(inp.get(k)is True,'independent original input preparation requirement')
    c.need(inp.get('pins_alone_prove_authenticity')is False and inp.get('matlab_parity_claimed')is False,'no inferred authenticity or native parity')
    c.need(type(panel)is dict and set(panel)=={'schema','task_id','scope','pool','projection','full_source_authenticity_admitted'} and panel['schema']=='neural084-canonical-preparation-v2' and panel['task_id']=='NEURAL-084' and panel['scope']==SCOPE and panel['pool']==s['pool'] and panel['full_source_authenticity_admitted']is True,'full canonical preparation gate')
    c.need(type(panel['projection'])is dict and set(panel['projection'])=={'path','bytes','sha256'},'original preparation evidence');c.path(panel['projection']['path']);c.only_pin(panel['projection'])
    c.need(method.get('schema')=='neural084-sequential-method-review-v2' and method.get('program')==c.only_pin(s['program']) and method.get('mode')=='frozen_program','explicit two-phase candidate')
    for k in ('policy_fixed_before_all_queries','training_only_grouped_inner_selection','no_query_batch_fitting_or_target_calibration','no_cross_fold_or_sibling083_state','fit_sealed_model_infer_ABI_reviewed','all_three_query_only_fixed_references_retained','source_exposure_history_attested'):
        c.need(method.get(k)is True,'original scientific access rules')
    c.need(method.get('hashes_prove_chronology')is False,'external provenance still necessary')
    c.need(runtime.get('schema')=='neural084-sequential-runtime-v2' and runtime.get('image')==binding['image'] and runtime.get('profile')=={k:s[k] for k in ('fit_seconds','infer_seconds','reference_seconds','memory_bytes','plan','limits')} and runtime.get('program')==c.only_pin(s['program']),'same270-phase runtime profile')
    for k in ('offline_isolation_and_native_closure_qualified','canonical_gather_row_order_and_bytes_qualified','fit_infer_split_and_sealed_model_custody_qualified','durable_view_and_model_retirement_qualified','host_memory_original_clock_and_full54_qualified','fixed_cached_dependencies_and_reference_arithmetic_qualified'):
        c.need(runtime.get(k)is True,'separate v2 runtime qualification')
    c.need(runtime.get('scientific_qualified')is False and runtime.get('numeric_scoring_authorized')is False,'unscored authority')
