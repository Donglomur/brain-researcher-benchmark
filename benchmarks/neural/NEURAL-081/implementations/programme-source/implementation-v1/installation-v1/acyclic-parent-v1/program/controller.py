"""Concrete complete G0/G1/G2/G3/G4/G5 source-owned study composition."""
import os
from pathlib import Path
import common as c
import protocol as p
import authority,schedule,preparation_driver,reference_driver,public_projection,episodes
import grading,closure
from channel import Channel,selected_descriptor
from custody import Access
from runtime import Runtime,admit_closure
from projection_broker import Broker
from host_observation import Bridge

def metadata(desc,budget):return c.capture_json(desc,budget,[Path(desc['path']).parent])
def unique(rows):return reference_driver.unique_descriptors(rows)

def phase_limits(run,phase,budget):return c.LocalBudget(budget,run['phase_limits'][phase])

def request(out,phase,payload,source,run_desc,budget):
    return c.publish_json(out/(phase+'-REQUEST.json'),{'schema':'neural081_phase_request_v1','task_id':c.TASK,'phase':phase,'source':source,'run':run_desc,'output_root':str(out/phase),'payload':payload},budget)

def selected_metadata(desc,conditions,role,key,budget):
    selected_descriptor(conditions,role,key,desc);return metadata(desc,budget)

def provider_configuration(desc,selected,conditions,budget):
    same=c.typed_equal
    c.need(same(selected['provider_config'],desc),'actual selected provider descriptor before credential access')
    config=selected_metadata(desc,conditions,'provider','configuration',budget)
    c.need(selected['credential_names']==[config['api_key_env']],'one metadata-bound credential name')
    c.need(conditions['provider'].get('exact_plain_chat_framing')is True and conditions['provider'].get('resolved_ip')==config['resolved_ip']and c.typed_equal(conditions['provider'].get('tokenizer_qualification'),config['tokenizer_contract']['qualification']),'actual selected token framing and literal network endpoint mechanisms')
    # No key read here: only concrete provider transport accesses this one selected
    # environment value immediately before a request; no values enter receipts.
    return config

def run(configuration,source,source_files,budget):
    owned={'broker':None}
    try:return _run(configuration,source,source_files,budget,owned)
    except BaseException as error:
        if owned['broker']is not None:
            try:owned['broker'].failure_close(error)
            except BaseException:pass  # Original operation failure remains primary.
        raise

def _run(configuration,source,source_files,budget,owned):
    c.exact(configuration,('schema','source','run','channel','output_root','protected_roots','native_config','preparation','preparation_manifest','reference_manifest','issuer_manifest','issuer_worker_limits','issuer_sandbox','host_python','host_environment','provider_config','replication_seeds','public_protocol','tool_source','candidate_runner','numeric_source','grade_manifest','grade_worker_io','host_metadata_capacity_bytes'))
    c.need(configuration['schema']=='neural081_complete_controller_v1'and c.typed_equal(configuration['source'],source),'exact full source controller configuration')
    for name in('native_config','preparation_manifest','reference_manifest','issuer_manifest','provider_config','tool_source','candidate_runner','numeric_source','grade_manifest'):c.descriptor(configuration[name])
    run_desc=configuration['run'];allocation=authority.run_allocation(metadata(run_desc,budget),budget)
    n=allocation['N'];c.need(c.integer(configuration['host_metadata_capacity_bytes'],1)>=12*n*16384+7380*8192+64*2**20,'full metadata construction preventive capacity; physical enforcement remains qualified')
    root=c.new_directory(configuration['output_root'],budget);journal_root=c.new_directory(root/'journal',budget);journal=c.Journal(journal_root,budget)
    channel=Channel(configuration['channel'],budget,source,source_files,run_desc,configuration['protected_roots'])
    journal.append('controller-start',{'source':source,'run':run_desc,'original_origin':budget.origin,'original_endpoint':budget.end})
    g0=phase_limits(allocation,'G0',budget);r0=request(root,'G0',{'preparation':configuration['preparation'],'source_manifest':configuration['preparation_manifest'],'native_config':configuration['native_config']},source,run_desc,g0)
    a0,_,q0=channel.acquire(r0,'G0','controller')
    native_config=selected_metadata(configuration['native_config'],q0,'native','configuration',g0)
    selected_descriptor(q0,'input','preparation_selection',configuration['preparation'])
    preparation_selection=metadata(configuration['preparation'],g0)
    prep_manifest=selected_metadata(configuration['preparation_manifest'],q0,'native','preparation_manifest',g0)
    c.need(q0['physical_custody'].get('ordinary_controller_descriptor_only')is True,'qualified controller/physical trusted preparation boundary')
    g0root=c.new_directory(root/'G0',g0);g0native=Runtime(native_config,g0,source_files,c.new_directory(g0root/'native',g0))
    prepared=preparation_driver.run(preparation_selection,g0native,source,prep_manifest,g0,g0root/'preparation')
    index=prepared['index'];authority.run_allocation(allocation,budget,index);protected=prepared['protected']
    journal.append('G0-closed',{'result':prepared['descriptor'],'index':prepared['index_descriptor'],'counts':p.counts(index)})

    g1=phase_limits(allocation,'G1',budget);r1=request(root,'G1',{'index':prepared['index_descriptor'],'preparation':prepared['descriptor'],'source_manifest':configuration['reference_manifest'],'numeric_source':configuration['numeric_source'],'native_config':configuration['native_config']},source,run_desc,g1)
    a1,_,q1=channel.acquire(r1,'G1','controller');selected_descriptor(q1,'native','configuration',configuration['native_config'])
    ref_manifest=selected_metadata(configuration['reference_manifest'],q1,'native','reference_manifest',g1)
    selected_descriptor(q1,'access','operative_numeric_source',configuration['numeric_source'])
    g1root=c.new_directory(root/'G1',g1);g1native=Runtime(native_config,g1,source_files,c.new_directory(g1root/'native',g1))
    references=reference_driver.run(index,prepared['preparation']['roles'],g1native,configuration['numeric_source'],ref_manifest,g1,g1root/'references',protected)
    journal.append('G1-closed',{'result':references['descriptor'],'fixed_fits':3680,'fixed_inferences':3680,'selectors':20})

    g2=phase_limits(allocation,'G2',budget);r2=request(root,'G2',{'public_protocol':configuration['public_protocol'],'provider':configuration['provider_config'],'source_only_tools':[configuration['tool_source'],configuration['numeric_source'],configuration['candidate_runner']],'native_config':configuration['native_config']},source,run_desc,g2)
    a2,_,q2=channel.acquire(r2,'G2','controller');selected_descriptor(q2,'native','configuration',configuration['native_config'])
    provider=provider_configuration(configuration['provider_config'],a2,q2,g2)
    c.exact(configuration['replication_seeds'],c.REPS)
    for seed in configuration['replication_seeds'].values():c.need(seed is None or type(seed)is int and 0<=seed<2**31,'declared seed or unknown provider determinism')
    source_mounts=[{'source':configuration[name],'target':target,'opaque_host':False}for name,target in(('tool_source','/tools/reference_tools.py'),('numeric_source','/tools/numeric.py'),('candidate_runner','/tools/candidate_runner.py'))]
    g2root=c.new_directory(root/'G2',g2);author_native=Runtime(native_config,g2,source_files,c.new_directory(g2root/'native',g2));authors=[];programmes={}
    for replication in c.REPS:
        config=dict(provider,seed=configuration['replication_seeds'][replication])
        author=episodes.author(replication,config,author_native,g2,g2root,source_mounts,configuration['public_protocol'])
        programmes[replication]=author['programme'];authors.append({'replication':replication,'receipt':author['receipt']})
    journal.append('G2-sealed',{'authors':authors,'query_provider_for_F':False})

    g3=phase_limits(allocation,'G3',budget);r3=request(root,'G3',{'index':prepared['index_descriptor'],'references':references['descriptor'],'authors':authors,'issuer_manifest':configuration['issuer_manifest'],'native_config':configuration['native_config'],'provider':configuration['provider_config']},source,run_desc,g3)
    a3,_,q3=channel.acquire(r3,'G3','controller');selected_descriptor(q3,'native','configuration',configuration['native_config'])
    provider=provider_configuration(configuration['provider_config'],a3,q3,g3)
    issuer_manifest=selected_metadata(configuration['issuer_manifest'],q3,'physical_custody','issuer_manifest',g3)
    c.need(q3['physical_custody'].get('one_persistent_current_fd_issuer')is True and q3['physical_custody'].get('candidate_namespace_qualified')is True,'actual qualified current-only issuer and native namespaces')
    c.need(c.typed_equal(q3['physical_custody'].get('issuer_sandbox'),configuration['issuer_sandbox']),'exact admitted concrete restriction mechanism')
    g3root=c.new_directory(root/'G3',g3);case_root=c.new_directory(g3root/'cases',g3);query_native=Runtime(native_config,g3,source_files,c.new_directory(g3root/'native',g3))
    model_registry=public_projection.issue_models(index,references,prepared['preparation']['model_row_tokens'],configuration['tool_source'],g3,g3root/'models')
    model_folds={(r['view'],r['outer']):r for r in model_registry['folds']}
    context_maps={(r['mode'],r['replication'],r['view'],r['canonical_id']):r for r in prepared['preparation']['contexts']}
    c.need(len(context_maps)==12*n,'all12N preissued current-only contexts')
    final_roles={(r['view'],r['outer']):r for r in prepared['preparation']['roles']if r['inner']=='FINAL'}
    roster=[]
    for ordinal,identity in enumerate(schedule.cases(index)):
        mapping=context_maps[(identity['mode'],identity['replication'],identity['view'],identity['canonical_id'])];role=final_roles[(identity['view'],identity['outer'])]['role']
        roster.append({'kind':'project','ordinal':ordinal,'context':mapping['map'],'role':role,'source':source,'generation':index['preparation_generation']})
    issuer_budget=c.LocalBudget(budget,allocation['issuer_limits'])
    worker_limits=dict(configuration['issuer_worker_limits']);c.exact(worker_limits,('seconds',*budget.limits))
    c.need(worker_limits['seconds']==budget.end-budget.origin,'issuer original whole endpoint')
    issuer_config={'schema':'neural081_projection_issuer_v1','source':source,'origin':budget.origin,'limits':worker_limits,'sandbox':configuration['issuer_sandbox'],'request_roster':roster,'maximum_requests':12*n}
    manifest_desc=c.publish_json(g3root/'ISSUER-SOURCE.json',issuer_manifest,g3)
    issuer_request=c.publish_json(g3root/'ISSUER-REQUEST.json',{'schema':'neural081_issuer_entry_request_v1','source':source,'config':issuer_config,'source_manifest':manifest_desc},g3)
    entry=issuer_manifest['entry'];boot=issuer_manifest['bootstrap'];python=c.absolute(configuration['host_python'])
    c.need(c.typed_equal(q3['physical_custody'].get('host_python'),str(python))and c.typed_equal(q3['physical_custody'].get('host_environment'),configuration['host_environment']),'exact independently admitted issuer launch environment')
    argv=[str(python),'-I','-B',entry['path'],'--request',issuer_request['path'],'--request-bytes',str(issuer_request['bytes']),'--request-sha256',issuer_request['sha256'],'--bootstrap',boot['path'],'--bootstrap-bytes',str(boot['bytes']),'--bootstrap-sha256',boot['sha256'],'--read-cap',str(worker_limits['read_bytes']),'--write-cap',str(worker_limits['write_bytes']),'--origin',str(budget.origin),'--deadline',str(budget.end),'--entry-bytes',str(entry['bytes']),'--issuer-fd','{ISSUER_FD}']
    issued_inputs=unique([*[r['map']for r in prepared['preparation']['contexts']],*[d for r in final_roles.values()for d in r['allowed']],*[r['window_descriptor']for r in index['rows']]])
    opaque=[d['path']for d in issued_inputs if d['path'].endswith('.npy')or d['path'].endswith('-labels.json')]
    issuer_access=Access('issuer',issued_inputs,protected,issuer_budget,opaque)
    launch={'argv':argv,'cwd':'/','env':configuration['host_environment'],'normal_seconds':max(0,budget.end-budget.clock()),'cleanup_seconds':120,'stream_cap':262144,'fd_argument':'{ISSUER_FD}'}
    broker=Broker(launch,issuer_config,issuer_request,source,issuer_access,Bridge(issuer_budget),g3root/'issuer')
    owned['broker']=broker
    cases=[];candidate_rows={};candidate_closures={}
    for ordinal,identity in enumerate(schedule.cases(index)):
        key=(identity['mode'],identity['replication'],identity['view'],identity['canonical_id']);mapping=context_maps[key];fold=model_folds[(identity['view'],identity['outer'])]
        train_n=sum(1 for r in index['rows']if r['person']!=identity['outer']);model_bytes=sum(m['source']['bytes']for m in fold['mounts'])
        read_cap=8*(train_n*64*512*4+model_bytes+16*2**20)
        local_limits=dict(g3.limits,seconds=2400,read_bytes=read_cap,write_bytes=16*2**30,native_cpu_seconds=480,native_processes=1 if identity['mode']=='F'else 8,provider_requests=0 if identity['mode']=='F'else 9,provider_tokens=0 if identity['mode']=='F'else 9*(32768+4096),stream_bytes=2*262145*(1 if identity['mode']=='F'else 8),tool_processes=0 if identity['mode']=='F'else 8,host_processes=0)
        case_budget=c.LocalBudget(g3,local_limits);case_directory=c.new_directory(case_root/('%08d'%ordinal),case_budget)
        projection_request={**roster[ordinal],'limits':{'metadata_bytes':16*2**20,'output_bytes':max(train_n*64*512*4+65536,train_n*128+65536),'array_bytes':64*512*4+65536},'original_endpoint':budget.end,'case_endpoint':case_budget.end}
        descriptors,reply=broker.project(projection_request)
        remaining={'native_seconds':480,'native_actions':1 if identity['mode']=='F'else 8,'provider_requests':0 if identity['mode']=='F'else 9,'scratch_write_bytes':16*2**30,'managed_read_bytes':read_cap,'source_bytes':65536,'normal_seconds_remaining':max(0,case_budget.end-case_budget.clock())}
        projection=public_projection.issue_context(index,mapping['map'],{'descriptors':descriptors,'reply':reply},fold,remaining,case_budget,case_directory/'projection')
        if identity['mode']=='I':
            config=dict(provider,seed=configuration['replication_seeds'][identity['replication']]);e=episodes.investigate(projection['context'],config,query_native,case_budget,case_directory,projection['mounts'],configuration['candidate_runner'])
        else:e=episodes.fixed(projection['context'],programmes[identity['replication']],query_native,case_budget,case_directory,projection['mounts'],configuration['candidate_runner'])
        broker.cleanup(e);case_budget.check_clock()
        cases.append({'identity':identity,'context_alias':mapping['context_alias'],'binding':projection['binding']['descriptor'],'episode':e['receipt'],'projection':broker.events[-2],'cleanup':broker.events[-1]})
        pk=(identity['mode'],identity['replication'],identity['view'],identity['outer']);candidate_rows.setdefault(pk,[]).append({'id':identity['canonical_id'],'probabilities':e['probabilities']});candidate_closures.setdefault(pk,[]).append(e['receipt'])
    issuer=broker.finish();journal.append('G3-all-cases-closed',{'count':len(cases),'issuer':issuer})
    panels_root=c.new_directory(root/'panels',budget);panels=[]
    reference_panels={(x['role'],x['handle'],x['view'],x['person']):x for x in references['panels']}
    for ordinal,identity in enumerate(schedule.panels()):
        ids=[r['canonical_id']for r in index['rows']if r['person']==identity['person']]
        if identity['role']=='candidate':
            pk=(identity['mode'],identity['replication'],identity['view'],identity['person']);rows=candidate_rows[pk]
            c.need([r['id']for r in rows]==ids,'complete original candidate person panel')
            submission=c.publish_json(panels_root/('%03d-predictions.json'%ordinal),{'schema':'neural081_predictions_v1','predictions':rows},budget);producers=candidate_closures[pk]
        else:
            original=reference_panels[(identity['role'],identity['handle'],identity['view'],identity['person'])];submission=original['predictions'];producers=[original['closure']]
        panels.append(c.publish_json(panels_root/('%03d-panel.json'%ordinal),{'schema':'neural081_closed_panel_v1','identity':identity,'submission':submission,'producer_closures':producers,'source':source,'generation':index['preparation_generation'],'role_support':ids},budget))
    study=c.publish_json(root/'STUDY.json',{'schema':'neural081_complete_study_v1','source':source,'source_files':source_files,'generation':index['preparation_generation'],'index':prepared['index_descriptor'],'preparation':prepared['descriptor'],'references':references['descriptor'],'authors':authors,'cases':cases,'issuer':issuer,'panels':panels,'channel_records':channel.records,'normal_endpoint':budget.end,'G4_metadata_only':True},budget)
    never=[*preparation_selection['raw_files'],preparation_selection['key']]
    audit=closure.AuditAccess([root,configuration['channel']['request_root'],configuration['channel']['response_root'],*[r['authority']['channel_root']for r in channel.records],*[Path(d['path']).parent for d in source_files]],protected,never,budget)
    graph=closure.admit(study,index,audit,source);grading.admit_panels(index,graph['panels'],audit,source)
    barrier=c.publish_json(root/'G4-ADMITTED.json',{'schema':'neural081_complete_pretarget_barrier_v1','source':source,'study':study,'index':prepared['index_descriptor'],'all240panels':panels,'metadata_reads':list(audit.allowed.values()),'protected_body_reads':0,'completed_monotonic':budget.clock()},budget)
    from grade_driver import run as run_grade
    g5=phase_limits(allocation,'G5',budget);r5=request(root,'G5',{'study':study,'index':prepared['index_descriptor'],'barrier':barrier,'grade_manifest':configuration['grade_manifest'],'worker_io':configuration['grade_worker_io'],'native_config':configuration['native_config']},source,run_desc,g5)
    a5,_,q5=channel.acquire(r5,'G5','controller');selected_descriptor(q5,'native','configuration',configuration['native_config'])
    grade_manifest=selected_metadata(configuration['grade_manifest'],q5,'native','grade_manifest',g5)
    g5root=c.new_directory(root/'G5',g5);grade_native=Runtime(native_config,g5,source_files,c.new_directory(g5root/'native',g5))
    graded=run_grade(index,prepared['index_descriptor'],study,barrier,list(audit.allowed.values()),protected,source,grade_manifest,configuration['grade_worker_io'],grade_native,g5,g5root/'grade')
    result={'schema':'neural081_provisional_complete_controller_v1','source':source,'study':study,'index':prepared['index_descriptor'],'G4_barrier':barrier,'grade':graded,'channel_records':channel.records,'budget':budget.snapshot(),'status':'provisional_until_independent_whole_controller_natural_exit','scientific_claim':'Full ten-person instructed-excerpt decoding; broader matched single-query candidate adaptation than inductive references, not reasoning-only attribution or causal understanding.'}
    budget.check_clock();return c.publish_json(root/'RESULT.json',result,budget)
