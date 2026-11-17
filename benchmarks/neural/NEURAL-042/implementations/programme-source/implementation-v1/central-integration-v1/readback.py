"""Complete original admission and literal parent results, never a new scorer."""
from pathlib import Path

def natural(record,argv,a,review):
    u.need(type(record)is dict and record.get('argv')==argv and record.get('cwd')==a['roots']['source'],'actual parent command/cwd')
    for key in ('successful_observation','spawn_attempted','spawn_returned','natural_exit','process_reaped','process_group_absent','streams_closed','selector_closed','stdout_eof','stderr_eof','wait_attempted','mutating_signals_disabled','no_mutating_signals'):
        u.need(record.get(key)is True,'required natural caller '+key)
    for key in ('timed_out','cleanup_attempted','parent_timer_elapsed','output_overflow','cleanup_ownership_unknown','failed_unknown_child_state','spawn_ownership_unknown','requires_separate_child_inspection','term_attempted','term_sent','kill_attempted','kill_sent','forced_termination_supported','forced_termination_available'):
        u.need(record.get(key)is False,'no failed/uncertain caller '+key)
    u.need(type(record.get('exit_code'))is int and record['exit_code']==0 and type(record.get('mutating_signal_count'))is int and record['mutating_signal_count']==0,'natural ordinary zero/no mutators')
    for key in ('error_type','timer_disable_error','timer_restore_error'):u.need(record.get(key)is None,'no caller/timer error')
    u.need(record.get('cleanup_mode')=='observation_and_bounded_wait_only','selected conservative caller')
    u.need(record['normal_end']==a['clock']['readback_end']and record['cleanup_end']==review['central_observation_deadline']
        and a['clock']['origin']<=u.finite(record['observed_start'])<=u.finite(record['normal_closed_at'])<=u.finite(record['final_closed_at'])<a['clock']['readback_end'],'unchanged original parent clock')

def json_at(host,desc,cap,required):
    u.need(type(desc)is dict and set(desc)=={'path','pin'}and u.path(desc['path'])==u.path(required),'exact fixed artifact path')
    return u.parse(host.read(required,cap,u.only_pin(desc['pin']),readonly=True))

def captured_parent(env,authority):
    return {**env['captured_parent'],'manifest_path':str(env['parent_manifest_path']),'authority_descriptor':authority,'authority_pin':authority['pin']}

def observation(host,desc,a,env,review):
    root=Path(a['roots']['observation']);r=a['resources'];cap=captured_parent(env,review['authority'])
    obs=json_at(host,desc,r['closure_bytes'],root/'OBSERVATION.json')
    u.need(obs.get('schema')=='neural042_observation_v1'and obs.get('status')=='complete'and obs.get('source')==env['parent_pin']
        and obs.get('authority')==review['authority']['pin']and obs.get('original_origin')==a['clock']['origin'],'complete actual parent observation')
    u.need(a['clock']['origin']<=u.finite(obs['observed_end'])<a['clock']['readback_end'],'original parent metadata closure deadline')
    parent=env['parent'];parent['outer'].natural(obs['caller'],parent['outer'].command(a,cap),a)
    u.need(json_at(host,obs['caller_artifact'],65536,root/'CALLER.json')==obs['caller'],'original parent caller artifact')
    for name in ('stdout','stderr'):
        raw=host.read(root/(name+'.bin'),65536,obs['streams'][name],readonly=True)
        if name=='stderr':u.need(raw==b'','original worker stderr empty')
        else:
            returned=u.parse(raw);u.need(returned.get('status')=='collected'and returned.get('producer')==obs['producer'],'actual full controller return')
    inventory=obs['resource_inventory'];u.need(set(inventory)=={'public','private'},'both independent native inventories')
    for role,row in inventory.items():
        u.need(row['empty']is True and row['study']==a['native_'+role]['study']and a['clock']['origin']<=u.finite(row['observed'])<a['clock']['readback_end'],'exact observed native retirement realm')
        u.only_pin(row['raw'])
    # Reuse the unchanged source-owned fixed-path admission. It reads complete
    # public reports and private operation metadata, never reference bodies.
    admitted=parent['admission'].admit(a,cap,obs['producer'],host)
    counts={k:admitted['closure'][k]for k in ('phase_count','native_count','provider_count')}
    u.need(obs['closure_counts']==counts and counts['phase_count']==448 and obs['schedule']==admitted['producer']['disposition'],'same complete actual 448-phase closure')
    u.need(set(admitted['reports'])=={'-'.join(c)for c in parent['contracts'].CELLS}and len(admitted['targets'])==4,'all eight candidate/four reference reports')
    return {'observation':desc,'producer':obs['producer'],'journal':admitted['producer']['journal'],'closure_counts':counts,
        'full_support':{'sessions':44,'people':36,'person_rows_per_report':144,'group_rows_per_report':4,'candidate_reports':8,'reference_reports':4,'case_phases':288},
        'central_reexecuted_complete_original_metadata_admission':True,'private_reference_bodies_read_by_central':False,'private_grading_performed':False}

def result(bundle,argv,a,review,env,config,host):
    natural(bundle['record'],argv,a,review);u.need(bundle['stderr']==b'','parent successful stderr empty')
    returned=u.parse(bundle['stdout'])
    if review['operation']=='collect':
        u.need(type(returned)is dict and set(returned)=={'status','observation','source'}and returned['status']=='observed'and returned['source']==env['parent_pin'],'literal original observe return')
        return observation(host,returned['observation'],a,env,review)
    u.need(type(returned)is dict and set(returned)=={'status','score'}and returned['status']=='graded','literal original protected grade return')
    score=json_at(host,returned['score'],a['resources']['closure_bytes'],Path(a['roots']['observation'])/'SCORE.json')
    u.need(score.get('schema')=='neural042_grade_v1'and score.get('task_id')=='NEURAL-042'and score.get('authority')==review['authority']['pin']
        and score.get('source')==env['parent_pin']and score.get('late_grading')==review['grading_selection']
        and score.get('observation')==review['grading_document']['observation']and score.get('independent_references_agree')is True,'actual original protected report lineage')
    u.need(set(score['panels'])=={'-'.join(c)for c in env['parent']['contracts'].CELLS}and len(score['paired_comparisons'])==10
        and set(score['sanity_references'])=={'fixed_zero_metric_sanity','count_only_lower_reference','independent_competent_gold','additional_fits','not_canonical_full_report_support_predictors'},'complete selected score/diagnostics')
    u.need(score.get('qualified_neural_contribution')is None and score.get('causal_or_native_understanding_claim')is False
        and a['clock']['origin']<=u.finite(score['observed_end'])<a['clock']['readback_end'],'original score clock and claim limits')
    return {'protected_report':returned['score'],'observation':score['observation'],'full_support':{'sessions':44,'people':36,'candidate_reports':8,'reference_reports':4},
        'private_grading_performed':True,'metrics_computed_by':'unchanged authenticated parent grade.execute','scientific_qualification_inferred':False}
