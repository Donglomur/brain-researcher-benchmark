"""Complete portable stage engine with immutable, externally bound continuation."""
from pathlib import Path
from dataclasses import asdict,replace
import os,time,resource
from banc_runtime.codec import need,encode,parse,pin,relative
from banc_runtime.construct import manifest
from banc_runtime.producers import complete_pipeline
from .protected import capture_bundle,compare_sealed
from banc_runtime.metrics import fixed_quantity_comparison
from .source import STAGES,SCOPE,PROFILE
from .io import metadata,exact_fields,read,read_json,write_json,fresh_directory,digest
from .storage import copy,role_index
from .seals import serialize,restore
from .reference import run_reference
from .actor import run_actor
from .authority import verify_envelope

def prepare(ctx,root,meter):
    index=role_index(ctx['method']);staged=fresh_directory(root,'inputs')
    for name,row in index.items():
        copy(staged,name,read(ctx['roots']['input_root'],row['descriptor'],meter,ctx['deployment']['limits']['read_bytes']),meter)
    paper=ctx['method']['paper'];raw=read(ctx['roots']['input_root'],paper,meter,ctx['deployment']['limits']['read_bytes'])
    pd=copy(root,'paper.pdf',raw,meter)
    value={'schema':'banc_complete_preparation_v1','input_index':index,'paper':pd,
      'program':manifest(ctx['program']),
      'pipeline':complete_pipeline(ctx['program'],ctx['source']['contracts'],ctx['source']['members']),
      'scientific_qualification':False,'data_bodies_admitted':True,'all20_roles_retained':True}
    value['identity']=pin(encode(value))['sha256'];return value

def collect(ctx,actor,root,meter):
    from .clustering import bind
    from .io import write
    cap=ctx['deployment']['limits']['file_bytes']
    seal=capture_bundle(actor['bundle_root'],actor['bundle'],ctx['source']['contracts'],
      program_identity=ctx['program'].selection_identity,meter=meter,cap=cap)
    first=actor['phases']['cluster'];phase=actor['prelabel']
    need(pin(encode(first['files']))['sha256']==first['identity']==phase['phase_inventory_identity'] and
      pin(encode(actor['phases']['downstream']['files']))['sha256']==actor['phases']['downstream']['identity']==phase['downstream_phase_inventory_identity'], 'actual both-phase inventories')
    raw=read(first['root'],phase['descriptor'],meter,cap)
    fixed={role:ctx['method']['data'][role] for role in ('fixed_an_dn_annotations','fixed_cns_annotations','fixed_effector_annotations')}
    proof=bind(seal,raw,phase,ctx['source']['contracts'],ctx['program'].selection_identity,fixed,cap)
    retained=write(root,'prelabel-artifact.json',raw,meter)
    declared=parse(seal.manifest_bytes)['attempts'];actual=actor['attempts']
    d=write_json(root,'candidate-seal.json',serialize(seal),meter)
    return {'seal':d,'root':str(root),'identity':seal.identity,'actual_actor_attempts':actual,
      'candidate_declared_attempts_untrusted':declared,'prelabel_artifact':retained,'prelabel_phase':phase,
      'clustering_binding':proof,'references_read':False}

def grade(ctx,collected,reference,root,meter):
    # No assessment/reference evidence or target body is opened until the full
    # retained manifest, all96 payloads and all family/legacy products pass.
    raw=read_json(collected['root'],collected['seal'],meter,ctx['deployment']['limits']['read_bytes'])
    cap=ctx['deployment']['limits']['file_bytes']
    candidate=restore(raw,ctx['source']['contracts'],ctx['program'].selection_identity,cap)
    need(candidate.identity==collected['identity'],'retained collection identity')
    from .clustering import bind
    prelabel_raw=read(collected['root'],collected['prelabel_artifact'],meter,cap)
    fixed={role:ctx['method']['data'][role] for role in ('fixed_an_dn_annotations','fixed_cns_annotations','fixed_effector_annotations')}
    binding=bind(candidate,prelabel_raw,collected['prelabel_phase'],ctx['source']['contracts'],ctx['program'].selection_identity,fixed,cap)
    need(binding==collected['clustering_binding'],'retained source-owned clustering/phase binding')
    assessment=read_json(ctx['roots']['input_root'],ctx['method']['assessment_plan'],meter)
    exact_fields(assessment,('schema','reference_review_path','baseline_costs','untouched_evaluation'),'assessment plan')
    need(assessment['schema']=='banc_complete_assessment_v1','closed assessment schema')
    path=ctx['roots']['input_root']/relative(assessment['reference_review_path'])
    evidence=verify_envelope(parse(metadata(path,meter,1048576)),ctx['keys'],ctx['deployment']['issuers']['reference'],'reference_assessment')
    exact_fields(evidence,('program_identity','source_sha256','candidate_seal','reference_bundle','reference_seal','projection',
      'fidelity_review_sha256','identical_estimand','fidelity_qualified','untouched_evaluation','clustering_binding_sha256'),'independent protected assessment')
    need(evidence['program_identity']==ctx['program'].selection_identity and evidence['source_sha256']==ctx['source']['manifest_identity']['sha256'] and
      evidence['candidate_seal']==candidate.identity and evidence['reference_bundle']==reference['bundle'] and
      evidence['reference_seal']==reference['seal_identity'] and evidence['projection']==reference['projection'],'exact candidate/reference/source/projection assessment')
    digest(evidence['fidelity_review_sha256'])
    need(evidence['clustering_binding_sha256']==pin(encode(binding))['sha256'],'independent assessment binds exact source map, prelabel artifact and both phases')
    comparison=compare_sealed(candidate,reference['bundle_root'],reference['bundle'],ctx['source']['contracts'],
      program_identity=ctx['program'].selection_identity,meter=meter,cap=cap)
    need(comparison['reference_seal']==reference['seal_identity'],'actual protected reference identity')
    ratios=None
    if ctx['program'].objective=='fixed_quantity_improvement':
        need(assessment['untouched_evaluation'] is not None and evidence['untouched_evaluation']==assessment['untouched_evaluation'],
          'original selected-test transmitter scores cannot support genuine improvement; separate untouched evaluation required')
        digest(assessment['untouched_evaluation'])
        need(all(row['state']=='compared_unqualified' for row in comparison['panels']),
          'missing required scientific quantity cannot support a full-programme improvement')
        baseline=read_json(ctx['roots']['input_root'],assessment['baseline_costs'],meter)
        attempts=collected['actual_actor_attempts']
        costs={'wall_seconds':sum(r['wall_seconds'] for r in attempts),'peak_rss_bytes':max(r['peak_rss_bytes'] for r in attempts),
          'output_bytes':sum(r['output_bytes'] for r in attempts),'failed_attempt_seconds':sum(r['wall_seconds'] for r in attempts if r['exit_code']!=0)}
        ratios=fixed_quantity_comparison(costs,baseline,identical_estimand=evidence['identical_estimand'],fidelity_qualified=evidence['fidelity_qualified'])
    return {'comparison':comparison,'clustering_binding':binding,'provisional_resource_ratios':ratios,'assessment_evidence_sha256':pin(encode(evidence))['sha256'],
      'scientific_qualification':False,'success':None,'source_controls_are_scientific_results':False}

def report(ctx,states,root,meter):
    comparison=states['grade']['comparison']
    return {'schema':'banc_complete_report_v1','task_id':'PAPER-FIND-NEW-003','profile':PROFILE,'scope':SCOPE,
      'condition':ctx['method']['condition'],'operator_branch':ctx['program'].operator_branch,
      'annotation_profile':ctx['program'].annotation_profile,'graph_variant':ctx['program'].graph_variant,
      'biological_units':1,'unit':'one adult female fly; neurons/edges are dependent within this animal',
      'uncertainty':'Conditional graph/algorithmic uncertainty; no animal-population confidence from nodes, edges or panels.',
      'transmitter_evaluation':'Original neuron80/20 split with test-selected checkpoint; ED3b is selected-test evaluation.',
      'graph_null':'Required-unscorable: original randomized-graph producer unlocated; other nulls do not replace it.',
      'source_identity':ctx['source']['manifest_identity'],'method_identity':ctx['authority'].method_identity,
      'complete_input_identity':states['prepare']['identity'],'candidate_seal':states['collect']['identity'],
      'panels':comparison['panels'],'gates':ctx['source']['contracts']['GATES']['gates'],
      'native_attempts':states['reference']['attempts'],'actor_attempts':states['actor']['attempts'],
      'grade':states['grade'],'whole_attempt_costs':meter.report(),'scientific_qualification':False,
      'runtime_execution_is_not_scientific_parity':True,'ready_benchmark_count_increment':0}

def continue_budget(meter,record,journal_bytes):
    costs=record['costs'];prior=costs['limits']
    need(all(prior[k]==getattr(meter.limits,k) for k in prior if k!='deadline_ns'),'same whole-attempt budget, no continuation reset')
    for k in ('read_reserved','read_completed','output_reserved','output_completed','rows','pair_work','jobs'):
        setattr(meter,k,getattr(meter,k)+costs[k])
    meter.output_reserved+=journal_bytes;meter.output_completed+=journal_bytes
    need(costs['cpu_seconds_limit']==meter.cpu_seconds_limit and costs['address_space_ceiling']==meter.address_space_ceiling and
      costs['file_bytes_ceiling']==meter.file_bytes_ceiling,'same continued CPU/memory/file policy')
    meter.cpu_seconds_reserved+=costs['cpu_seconds_reserved']
    need(meter.cpu_seconds_reserved<=meter.cpu_seconds_limit,'continued whole-attempt CPU reservation')
    for field,limit in (('read_reserved','read_bytes'),('output_reserved','output_bytes'),('rows','row_count'),('pair_work','pair_work'),('jobs','jobs')):
        need(getattr(meter,field)<=getattr(meter.limits,limit),'continued whole-attempt '+field)
    # Adopt the original absolute origin/deadlines; time between commands does
    # not become a fresh interval. Startup reads were already charged.
    meter.attempt_clock.adopt(record['attempt_clock'])
    meter.limits=replace(meter.limits,deadline_ns=meter.attempt_clock.record['deadline_monotonic_ns'])


def execute(ctx,action,meter):
    from .clock import guard
    from .custody import acquire,bindings,restore as restore_directories,unlink,identity
    from .io import write_diagnostic
    from .failures import FailureEnvelope,combine
    requested=ctx['output'];out=None;states={};records=[];previous=None;lock_identity=None
    primary=None;stage='admission';failure_reserve=False;result=None
    try:
        guard(meter,'engine_entry');meter.reserve_output(65536);failure_reserve=True
        if action in ('prepare','run'):
            need(ctx['previous_journal_sha256'] is None,'first operation has no predecessor')
            out=fresh_directory(ctx['roots']['output_root'],requested.name,meter)
        else:
            out=acquire(requested,ctx['attempt_directory_identity'])
            terminal=ctx['previous_terminal_confirmation']
            need(terminal is not None and terminal['previous_journal_sha256']==ctx['previous_journal_sha256'] and terminal['attempt_clock']==ctx['clock'].record, 'independently confirmed outer predecessor required')
            for oldstage in STAGES:
                if oldstage==action:break
                raw=metadata(out/(oldstage+'.journal.json'),meter,2097152);r=parse(raw)
                need(r['stage']==oldstage and r['previous_sha256']==previous and r['method_identity']==ctx['authority'].method_identity and
                  r['source_identity']==ctx['source']['manifest_identity']['sha256'] and r['status']=='provisional_stage_result', 'exact predecessor chain')
                if not records:
                    meter.attempt_clock.adopt(r['attempt_clock'])
                    meter.limits=replace(meter.limits,deadline_ns=meter.attempt_clock.record['deadline_monotonic_ns'])
                need(r['attempt_clock']==meter.attempt_clock.record and r['attempt_directory_identity']==out.identity,'original attempt clock/directory')
                restore_directories(r['directory_capabilities'],out)
                need(not (out/(oldstage+'.failure.json')).exists(),'failed stage cannot authorize continuation')
                previous=pin(raw)['sha256'];records.append(r);states[oldstage]=r['result']
            need(previous==ctx['previous_journal_sha256'] and records,'independently selected predecessor')
            continue_budget(meter,records[-1],len(raw));guard(meter,'after_continuation_admission')
        write_json(out,'operation.lock',{'operation':action,'pid':os.getpid(),'evidence':asdict(ctx['authority'])},meter)
        lock_identity=identity(os.stat('operation.lock',dir_fd=out.fd,follow_symlinks=False))
        selected=STAGES if action=='run' else (action,)
        for stage in selected:
            guard(meter,'before_stage_'+stage);out.verify()
            need(not (out/(stage+'.journal.json')).exists() and not (out/(stage+'.failure.json')).exists(),'stage already spent; no implicit retry')
            stage_root=fresh_directory(out,stage,meter)
            if stage=='prepare':value=prepare(ctx,stage_root,meter)
            elif stage=='reference':value=run_reference(ctx,states['prepare'],stage_root,meter)
            elif stage=='actor':value=run_actor(ctx,stage_root,meter)
            elif stage=='collect':value=collect(ctx,states['actor'],stage_root,meter)
            elif stage=='grade':value=grade(ctx,states['collect'],states['reference'],stage_root,meter)
            elif stage=='report':value=report(ctx,states,stage_root,meter)
            else:raise ValueError('unknown stage')
            guard(meter,'after_stage_'+stage);stage_root.verify();out.verify();states[stage]=value
            record={'schema':'banc_complete_stage_journal_v2','stage':stage,'status':'provisional_stage_result','previous_sha256':previous,
              'method_identity':ctx['authority'].method_identity,'source_identity':ctx['source']['manifest_identity']['sha256'],
              'authority':asdict(ctx['authority']),'result':value,'costs':meter.report(),'attempt_clock':ctx['clock'].record,
              'attempt_directory_identity':out.identity,'directory_capabilities':bindings(out),
              'active_elapsed_seconds':ctx['clock'].elapsed(),'outer_terminal_publication_unverified':True,'scientific_qualification':False}
            guard(meter,'before_journal_'+stage)
            d=write_json(out,stage+'.journal.json',record,meter)
            guard(meter,'after_journal_'+stage);previous=d['sha256']
        guard(meter,'before_engine_terminal_result')
        result={'observed_stages':list(states),'last_journal_sha256':previous,'result':states[selected[-1]],'costs':meter.report(),
          'attempt_clock':ctx['clock'].record,'terminal_closure':'awaits_outer_process_receipt','stage_results_are_provisional':True}
    except BaseException as exc:
        primary=FailureEnvelope(exc,'stage_'+stage)
        if out is not None and failure_reserve:
            failure={'schema':'banc_complete_stage_failure_v2','stage':stage,'observations':primary.document(),
              'previous_sha256':previous,'method_identity':ctx['authority'].method_identity,'costs':meter.report(),
              'attempt_clock':ctx['clock'].record,'diagnostic_publication_may_follow_deadline':True,'stage_retry_requires_new_attempt':True,'scientific_qualification':False}
            try:write_diagnostic(out,stage+'.failure.json',failure,meter)
            except BaseException as secondary:primary.add(secondary,'failure_record_publication')
    finally:
        if out is not None and lock_identity is not None:
            try:guard(meter,'before_lock_retirement')
            except BaseException as exc:primary=combine(primary,exc,'retirement_deadline')
            # Required cleanup is attempted independently even after timeout.
            try:unlink(out,'operation.lock',lock_identity)
            except BaseException as exc:primary=combine(primary,exc,'lock_retirement')
            try:guard(meter,'after_lock_retirement')
            except BaseException as exc:primary=combine(primary,exc,'post_retirement_deadline')
    if primary is not None:raise primary
    guard(meter,'engine_terminal_closure');out.verify()
    result['terminal_observation']=ctx['clock'].check('engine_return')
    return result
