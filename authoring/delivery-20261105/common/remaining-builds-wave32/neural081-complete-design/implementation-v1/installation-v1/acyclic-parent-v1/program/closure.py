"""Independent complete pretarget artifact/source/producer admission.

All reads here are metadata/original operation streams. Array, training-label,
identity-key and complete assessment operands are never opened by this module.
"""
from pathlib import Path
import common as c
import protocol as p
import schedule
from custody import Access
from runtime import admit_closure

class AuditAccess(Access):
    """Source-owned G4 metadata discovery; G5 replays its exact observed read set."""
    def __init__(self,roots,protected,never_read,budget):
        super().__init__('G4',[],protected,budget)
        self.roots=[c.absolute(str(x))for x in roots];self.never={d['path']for d in never_read}
    def admit(self,desc):
        c.descriptor(desc,True);self._protected(desc['path']);path=c.absolute(desc['path'])
        c.need(any(path==r or path.is_relative_to(r)for r in self.roots),'selected operator metadata roots')
        c.need(desc['path']not in self.never and path.suffix not in('.npy','.fif')and not path.name.endswith('-labels.json')and path.name!='PERSON_PROTECTED.json','no numeric/training/global/key body in pretarget reader')
        if desc['path']in self.allowed:c.need(c.typed_equal(self.allowed[desc['path']],desc),'immutable metadata identity')
        else:self.allowed[desc['path']]=desc
        return desc

def same(a,b,reason):c.need(c.typed_equal(a,b),reason)

def captured_return(desc,access,returned=None):
    body=access.json(desc)
    if returned is not None:same(body,{k:v for k,v in returned.items()if k!='receipt'},'actual original receipt equals returned operation body')
    return body

def native(desc,access,source_files,*,expected_job=None,expected_kind=None):
    body=captured_return(desc,access);admit_closure(body)
    same(body['source_files'],source_files,'every actual worker uses full admitted source closure')
    if expected_job is not None:c.need(body['job_id']==expected_job,'exact original worker job')
    if expected_kind is not None:c.need(body['kind']==expected_kind,'exact original worker role')
    intent=access.json(body['intent'])
    for key in('job_id','kind','work_root','normal_deadline','original_deadline','source_files','mounts','script','argv','worker_io','cpu_reservation','memory_reservation','execution_config'):
        same(intent[key],body[key],'immutable actual launch intent '+key)
    for key in('stdout','stderr'):
        raw=access.read(body['raw_streams'][key]);same(c.pin(raw),{k:body['raw_streams'][key][k]for k in('bytes','sha256')},'actual original raw stream')
    for sequence,event in enumerate(body['engine_operations']):
        c.need(type(event['sequence'])is int and event['sequence']==sequence,'all original engine operation identities')
        request_raw=access.read(event['request_artifact']);same(c.pin(request_raw),event['request'],'original engine request body')
        response_raw=access.read(event['response_artifact'])
        if event['method']=='POST'and event['endpoint'].startswith('/containers/create?'):
            same(c.parse(request_raw),body['create_payload'],'actual source-owned isolated create payload')
        if event['method']=='POST'and event['endpoint']=='/containers/'+body['container_id']+'/wait?condition=not-running':
            same(c.parse(response_raw),body['wait'],'actual original daemon wait, no reconstruction')
    manifest=access.json(body['artifact_manifest'])
    c.exact(manifest,('schema','artifacts','operation_result'));c.need(manifest['schema']=='neural081_runtime_artifacts_v1'and manifest['operation_result']=='RESULT.json','full produced manifest')
    mapped=[{'path':str(Path(body['work_root'])/r['relative_path']),'bytes':r['bytes'],'sha256':r['sha256']}for r in manifest['artifacts']]
    same(mapped,body['artifacts'],'complete original manifest-to-artifact mapping')
    c.need(len({d['path']for d in mapped})==len(mapped),'unique produced operands')
    if body['kind']in('preparation','reference','grader'):
        cp=[d for d in mapped if d['path']==str(Path(body['work_root'])/'COMPLETE.json')]
        c.need(len(cp)==1,'one genuine worker completion')
        complete=access.json(cp[0]);c.exact(complete,('schema','job','request','numeric_source','original_origin','original_deadline','observed_before_publication','managed_requested_io','reservation','eof_probe_demand_included','physical_library_IO_or_RSS_measured'))
        c.need(complete['schema']=='neural081_worker_complete_v1'and (complete['job'].get('id')if type(complete['job'])is dict else complete['job'])==body['job_id'],'complete same worker')
        same(complete['reservation'],body['worker_io'],'same prospective retained worker IO reservation')
        c.need(complete['original_deadline']==body['supplied_original_deadline']and complete['observed_before_publication']<=body['normal_deadline']and complete['eof_probe_demand_included']is True,'exact completion endpoint and probes')
        for key in('read_bytes','write_bytes'):c.integer(complete['managed_requested_io'][key],0,complete['reservation'][key])
        req=access.json(complete['request']);same(complete['job'],req['job'],'same original complete request job');same(req['worker_io'],body['worker_io'],'worker request IO');same(req['clock'],{'origin':complete['original_origin'],'deadline':complete['original_deadline']},'original serialized worker clock')
        c.need(complete['request']in[d['source']for d in body['mounts']],'actual mounted immutable worker request')
        same(complete['numeric_source'],req['source'],'worker completion exact source')
    return body

def provider(record,access,deadline):
    c.need(record['status']=='completed'and record['response_stream_closed']is True and record['ended_monotonic']<=record['normal_deadline']<=record['original_deadline']==deadline,'full original provider close inside original episode')
    c.need(record['watchdog']['triggered']is False and record['watchdog']['thread_joined']is True and record['watchdog']['owned_socket_only']is True and record['watchdog']['remote_request_cancelled']is False and record['tls_hostname']=='api.openai.com','actual joined request watchdog; no remote-retirement fiction')
    request=access.json(record['request_artifact']);raw=access.read(record['response_artifact']);response=c.parse(raw)
    from transport.provider import parse_completion
    message,finish,usage=parse_completion(response,record['exact_input_tokens'])
    c.need(finish=='stop'and request['model']==record['model']==response['model']and request['n']==1 and request['store']is False and request['stream']is False,'exact complete provider action source')
    same(usage,record['usage'],'actual provider usage and original response');c.integer(usage['prompt_tokens'],0,32768);c.integer(usage['completion_tokens'],0,4096)
    c.need(usage['prompt_tokens']==record['exact_input_tokens']and request['max_completion_tokens']==record['output_token_limit'],'actual source-selected tokenizer/response limits')
    return message

def episode(desc,access,source_files,mode,alias=None,replication=None):
    body=captured_return(desc,access)
    c.need(body['status']=='completed'and body['source_admitted_natural_closure']is True and body.get('receipt_publication_uncertain')is not True,'actual successful source episode, never failure promotion')
    if mode=='author':
        c.need(body['schema']=='neural081_author_episode_v1'and body['replication']==replication and body['authentic_inputs_exposed']is False,'data-free original author')
    else:c.need(body['schema']=='neural081_candidate_episode_v1'and body['mode']==mode and body['context_alias']==alias,'same one current query episode')
    actions=body['native_actions'];c.need(type(actions)is list and len(actions)<=(1 if mode=='F'else 8),'complete action cap')
    if mode=='F':c.need(len(actions)==1 and body['provider_attempts']==[]and body['provider_at_query']is False,'exact fixed source prediction without provider')
    for returned in actions:
        actual=native(returned['receipt'],access,source_files,expected_kind={'F':'fixed','I':'investigate','author':'author'}[mode])
        same(actual,{k:v for k,v in returned.items()if k!='receipt'},'all native originals equal episode embedded records')
    requests=body['provider_attempts']
    if mode!='F':c.need(type(requests)is list and 1<=len(requests)<=9,'all original provider attempts')
    for ordinal,row in enumerate(requests,1):
        c.need(type(row['ordinal'])is int and row['ordinal']==ordinal,'unskipped original provider ordinal');provider(row,access,body['original_deadline'])
    used=body['budget']['logical_used'];c.need(used['provider_requests']==len(requests),'all provider reservations and original attempts')
    c.need(sum(x['cpu_reservation']for x in actions)<=480 and used['native_cpu_seconds']>=sum(x['cpu_reservation']for x in actions),'full native cumulative episode bound')
    if mode=='author':
        programme=body['programme'];sealed=captured_return(programme['receipt'],access,programme)
        c.need(sealed['schema']=='neural081_frozen_programme_v1'and sealed['replication']==replication and sealed['provider_at_query']is False and sealed['before_authentic_exposure_required']is True,'fixed original pre-exposure programme')
        c.need(1<=len(sealed['files'])<=16 and sum(r['source']['bytes']for r in sealed['files'])<=524288,'full bounded source bundle')
        for item in sealed['files']:access.read(item['source'])
    else:
        prediction=access.json(body['prediction_artifact']);c.exact(prediction,('context_alias','probabilities'))
        c.need(prediction['context_alias']==alias,'exact current alias');same(prediction['probabilities'],body['probabilities'],'actual prediction publication')
        from candidate_runner import probability_row
        probability_row(body['probabilities'])
    return body

def reference_graph(record,index,access,source_files):
    c.need(record['schema']=='neural081_reference_run_v1'and record['generation']==index['preparation_generation']and record['R2_qualification_study_executed']is False,'operative full R1 study, no invented R2 run')
    expected=list(schedule.reference_jobs(index));schedule.exact_roster(record['jobs'],expected)
    fits={};oof={};selections={};strongest={};models=[]
    for item,wanted in zip(record['jobs'],expected):
        c.need(item['operation']==wanted['operation'],'exact full operation order')
        observed=native(item['closure'],access,source_files,expected_job=item['id'],expected_kind='reference')
        c.need(item['result']in observed['artifacts']and c.typed_equal(item['artifact_manifest'],observed['artifact_manifest']),'result/manifest produced by same actual worker')
        req=access.json(item['request']);out=access.json(item['result'])
        c.need(c.typed_equal(req['job'],wanted)and req['operation']==wanted['operation']and req['generation']==index['preparation_generation']and out['operation']==wanted['operation']and out['generation']==index['preparation_generation'],'actual immutable request/result operation joins')
        same(req['source'],record['numeric_source'],'operative independent R1 source');same(out['numeric_source'],record['numeric_source'],'actual result source')
        c.need(req['clock']['deadline']==item['original_deadline']==observed['supplied_original_deadline'],'original worker deadline before allocation')
        same(req['worker_io'],item['worker_io'],'retained prospective worker IO')
        payload=req['payload'];body=out['body'];view,outer=wanted['view'],wanted['outer'];inner=wanted.get('inner','FINAL')
        op=wanted['operation'];key=(view,outer)
        if op in('fit','historical'):
            same(body['training_role'],payload['role'],'same complete issued training role')
            c.need(body['view']==view and body['outer']==outer and body['inner']==inner,'full fold/model identity')
            if inner=='FINAL':same(payload['selection'],selections[key],'all180 OOF selection before finalfit')
            else:c.need(payload['selection']is None,'no final/query selection in inner fit')
            config=body['configuration']['id'];fits[(view,outer,inner,config if inner!='FINAL'else body['family'])]=body['model']
            if inner=='FINAL':models.append(body['model'])
        elif op in('inner_infer','infer'):
            family_key=wanted['configuration']['id']if inner!='FINAL'else wanted['family']
            same(payload['model'],fits[(view,outer,inner,family_key)],'exact previously fitted state, no query refit');same(body['model'],payload['model'],'inference actual same model')
            person=inner if op=='inner_infer'else outer;ids=[r['canonical_id']for r in index['rows']if r['person']==person]
            same(body['ids'],ids,'all held-person support, no selective rows');same(payload['query']['ids'],ids,'same full held query input')
            if op=='inner_infer':oof.setdefault(key,[]).append(item['result'])
        else:
            same(payload['oof'],oof[key],'complete180 ordered independent OOF producers');same(body['oof'],oof[key],'actual full selector dependencies')
            c.need(len(oof[key])==180 and body['selection']['strongest_family']in p.FAMILIES,'complete competent family selection')
            selections[key]=item['result'];strongest[key]=body['selection']['strongest_family']
    c.need(len(models)==80 and len(selections)==20 and len(record['models'])==80 and len(record['panels'])==120,'entire fixed reference scope')
    same([r['model']for r in record['models']],models,'all80 exact final models')
    for row in record['selections']:
        key=(row['view'],row['outer']);same(row['result'],selections[key],'all20 exact selected comparator records');same(access.json(row['result'])['body'],row['body'],'same actual computed selection body')
    return strongest

def qualifications(records,source,source_files,access,phases=('G0','G1','G2','G3')):
    from authority import ROLES
    c.need(type(records)is list and len(records)==len(phases),'complete actual phase qualification exchanges')
    common_run=None
    for sequence,(phase,row)in enumerate(zip(phases,records)):
        c.need(type(row['sequence'])is int and row['sequence']==sequence and row['phase']==phase and row['actor']=='controller','all original phase authority requests')
        intent=access.json(row['intent']);response=access.json(row['response']);selected=row['authority']
        c.need(intent['schema']=='neural081_operator_metadata_request_v1'and intent['sequence']==sequence and intent['phase']==phase and intent['actor']=='controller'and intent['statistical_semantic_verdict_requested']is False,'mechanical protected metadata exchange only')
        same(intent['request'],row['request'],'actual request pin');same(response['intent'],row['intent'],'actual one-shot response intent');same(response['authority'],selected,'actual original authority response')
        c.need(response['schema']=='neural081_operator_metadata_response_v1'and type(response['sequence'])is int and response['sequence']==sequence,'same actual response sequence')
        same(selected['source'],source,'same qualified full source');same(selected['source_files'],source_files,'same qualified full source members');same(selected['request'],row['request'],'same qualified phase request')
        c.need(selected['selected_actual']is True and selected['phase']==phase and selected['actor']=='controller','separately selected actual phase authority')
        request=access.json(row['request']);c.need(request['schema']=='neural081_phase_request_v1'and request['task_id']==c.TASK and request['phase']==phase,'actual source-owned phase request')
        same(request['source'],source,'actual phase source');same(request['run'],selected['run'],'same selected original run')
        if common_run is None:common_run=selected['run']
        else:same(selected['run'],common_run,'no whole-clock/limit substitution between stages')
        registry=access.json(selected['registry']);c.need(registry['schema']=='neural081_qualification_registry_v1'and registry['selected_actual']is True,'actual protected qualification registry')
        same(registry['source'],source,'same registry source');same(registry['run'],common_run,'same registry original run');c.exact(registry['templates'],ROLES);c.exact(selected['receipts'],ROLES)
        for role in ROLES:
            template=access.json(registry['templates'][role]);receipt=access.json(selected['receipts'][role])
            c.need(template['schema']=='neural081_qualification_template_v1'and template['role']==role and template['status']=='qualified'and template['request_binding']=='later-independent-exact-request-v1','actual stable acyclic role template')
            c.need(receipt['schema']=='neural081_qualification_receipt_v1'and receipt['role']==role and receipt['status']=='qualified'and receipt['phase']==phase and receipt['actor']=='controller','actual exact current role receipt')
            for key,wanted in(('source',source),('run',common_run),('request',row['request']),('registry',selected['registry']),('template',registry['templates'][role]),('conditions',template['conditions'])):same(receipt[key],wanted,'actual authority '+key+' closure')
            c.need(receipt['issuer']==template['issuer']and receipt['issuer']in registry['issuers'][role]and phase in template['phases']and 'controller'in template['actors'],'independent selected issuer and role')
    return access.json(common_run)

def issuer_closure(study,index,access,source,files,allocation):
    issuer=access.json(study['issuer']);total=12*len(index['rows'])
    c.exact(issuer,('schema','intent','ready','events','final','observation','stdout','stderr','source','completed','normal_endpoint'))
    c.need(issuer['schema']=='neural081_complete_projection_issuer_v1'and type(issuer['completed'])is int and issuer['completed']==total,'one complete persistent issuer lifetime')
    same(issuer['source'],source,'same captured issuer source');c.need(issuer['normal_endpoint']==study['normal_endpoint'],'same original issuer endpoint')
    intent=access.json(issuer['intent']);same(intent['source'],source,'same original launch source')
    c.need(intent['schema']=='neural081_issuer_launch_v1'and intent['origin']==allocation['origin']and intent['end']==study['normal_endpoint']and intent['refunded']is False,'original issuer clock and retained reservation')
    request=access.json(intent['config']);c.exact(request,('schema','source','config','source_manifest'))
    c.need(request['schema']=='neural081_issuer_entry_request_v1','actual issuer entry request');same(request['source'],source,'same source request')
    config=request['config'];c.exact(config,('schema','source','origin','limits','sandbox','request_roster','maximum_requests'))
    c.need(config['schema']=='neural081_projection_issuer_v1'and type(config['maximum_requests'])is int and config['maximum_requests']==total and config['origin']==allocation['origin'],'complete exact persistent issuer configuration')
    same(config['source'],source,'same issuer configuration source');same(config['limits'],intent['worker_reservation'],'exact reserved worker IO')
    c.need(config['origin']+config['limits']['seconds']==study['normal_endpoint']and len(config['request_roster'])==total,'same original worker clock and all identities')
    manifest=access.json(request['source_manifest']);c.need(manifest['schema']=='neural081_issuer_source_manifest_v1','actual captured issuer bootstrap')
    for desc in [manifest['entry'],manifest['bootstrap'],*[r['source']for r in manifest['modules']]]:
        c.need(desc in files,'issuer source belongs to exact complete operative closure');access.read(desc)
    readiness=access.json(issuer['ready']);c.exact(readiness,('kind','source','restriction','original_endpoint'))
    c.need(readiness['kind']=='ready'and readiness['original_endpoint']==study['normal_endpoint'],'actual original issuer readiness');same(readiness['source'],source,'actual readiness source')
    restriction=readiness['restriction'];same(restriction['configuration'],config['sandbox'],'same concrete selected sandbox')
    for name in('new_user_namespace','new_network_namespace','no_new_privs','forbidden_root_open_refused'):c.need(restriction[name]is True,'actual issuer restriction '+name)
    c.need(type(restriction['landlock_abi'])is int and restriction['landlock_abi']>=3 and type(restriction['path_rules'])is int and restriction['path_rules']==0 and restriction['deployment_qualification_established_by_this_observation']is False,'actual restriction never substitutes for external qualification')
    from host_observation import admit as host_admit
    host_admit(issuer['observation'],intent['argv'],intent['origin'],issuer['normal_endpoint'],issuer['stdout'],issuer['stderr'])
    for key in('stdout','stderr'):access.read(issuer[key])
    c.need(type(issuer['observation']['passed_descriptor_count'])is int and issuer['observation']['passed_descriptor_count']==1,'one inherited current-only issuer channel')
    c.need(type(issuer['events'])is list and len(issuer['events'])==2*total,'every projection and cleanup event')
    previous=None
    for ordinal,row in enumerate(study['cases']):
        same(row['projection'],issuer['events'][2*ordinal],'same original projection event');same(row['cleanup'],issuer['events'][2*ordinal+1],'same original cleanup event')
        reply=access.json(row['projection']);clean=access.json(row['cleanup'])
        c.need(type(reply['ordinal'])is int and reply['ordinal']==ordinal and type(clean['ordinal'])is int and clean['ordinal']==ordinal,'complete monotone issuer identities')
        same(reply['previous_reply'],previous,'original projection chain');previous=c.pin(c.encoded(reply));same(clean['reply'],previous,'cleanup binds this exact original projection')
        expected=config['request_roster'][ordinal];c.exact(expected,('kind','ordinal','context','role','source','generation'))
        same(expected,{'kind':'project','ordinal':ordinal,'context':reply['context'],'role':reply['role'],'source':source,'generation':index['preparation_generation']},'all original source-owned current requests')
    final=issuer['final'];c.exact(final,('kind','completed','last_reply','budget'))
    c.need(final['kind']=='finished'and type(final['completed'])is int and final['completed']==total,'actual final issuer response');same(final['last_reply'],previous,'entire original issuer chain closed')
    b=final['budget'];c.need(b['original_origin']==config['origin']and b['original_deadline']==study['normal_endpoint']and b['physical_IO_or_RSS_measured']is False,'original worker accounting is logical')
    same(b['limits'],{k:v for k,v in config['limits'].items()if k!='seconds'},'same admitted worker limits');c.exact(b['logical_used'],b['limits'])
    for key,used in b['logical_used'].items():c.integer(used,0,b['limits'][key])
    return issuer

def admit(study_desc,index,access,source):
    p.validate_index(index);study=access.json(study_desc)
    c.exact(study,('schema','source','source_files','generation','index','preparation','references','authors','cases','issuer','panels','channel_records','normal_endpoint','G4_metadata_only'))
    c.need(study['schema']=='neural081_complete_study_v1'and study['generation']==index['preparation_generation']and study['G4_metadata_only']is True,'complete source-owned study')
    same(study['source'],source,'operative study source');same(access.json(study['index']),index,'same complete label-free index')
    files=study['source_files'];c.need(type(files)is list and len({d['path']for d in files})==len(files),'unique exact complete source closure')
    for desc in files:access.read(desc)
    allocation=qualifications(study['channel_records'],source,files,access)
    c.need(allocation['normal_endpoint']==study['normal_endpoint']and allocation['N']==len(index['rows']),'same complete actual original clock/census')
    prep=access.json(study['preparation']);c.need(prep['schema']=='neural081_complete_G0_driver_v1'and len(prep['jobs'])==10 and prep['ordinary_controller_numeric_or_label_body_reads']==0,'actual ten trusted preparation workers')
    for ordinal,(person,row)in enumerate(zip(c.PEOPLE,prep['jobs'])):
        c.need(row['person']==person and type(row['ordinal'])is int and row['ordinal']==ordinal,'all original ten preparer identities')
        produced=native(row['closure'],access,files,expected_job='G0/'+person,expected_kind='preparation')
        c.need(row['result']in produced['artifacts'],'actual trusted G0 result');r=access.json(row['result']);c.need(r['generation']==index['preparation_generation']and r['person']==person,'same trusted full generation')
        if ordinal==9:same(r['complete_preparation']['index'],study['index'],'full support assembled only by last trusted worker')
    reference=access.json(study['references']);strongest=reference_graph(reference,index,access,files)
    reference_panels={};reference_jobs={r['id']:r for r in reference['jobs']}
    for row in reference['panels']:
        key=(row['role'],row['handle'],row['view'],row['person'])
        c.need(key not in reference_panels,'one actual reference/analytic panel')
        job=row['view']+'/'+row['person']+('/select'if row['role']=='analytic'else'/final/'+row['handle']+'/infer')
        c.need(job in reference_jobs,'source-owned panel producer identity');same(row['closure'],reference_jobs[job]['closure'],'exact full reference panel producer')
        producer=access.json(row['closure']);c.need(row['panel']in producer['artifacts']and row['predictions']in producer['artifacts'],'both original panel and prediction artifact produced')
        original=access.json(row['panel']);c.need(original['schema']=='neural081_reference_panel_v1'and original['role']==row['role']and original['handle']==row['handle']and original['view']==row['view']and original['person']==row['person']and original['generation']==index['preparation_generation'],'same actual reference/analytic panel identity')
        same(original['predictions'],row['predictions'],'original source-owned full numerical predictions');reference_panels[key]=row
    c.need(type(study['authors'])is list and len(study['authors'])==3,'all three original fixed-source authors')
    for rep,row in zip(c.REPS,study['authors']):
        c.need(row['replication']==rep,'canonical author replications');episode(row['receipt'],access,files,'author',replication=rep)
    c.need(type(study['cases'])is list and len(study['cases'])==12*len(index['rows']),'every full F/I query')
    candidate_rows={};candidate_closures={}
    for identity,row in zip(schedule.cases(index),study['cases']):
        c.exact(row,('identity','context_alias','binding','episode','projection','cleanup'))
        same(row['identity'],identity,'complete ordered case identity');c.ident(row['context_alias'])
        e=episode(row['episode'],access,files,identity['mode'],row['context_alias'])
        binding=access.json(row['binding']);c.need(binding['context_alias']==row['context_alias']and binding['generation']==index['preparation_generation'],'same actual private/public context projection')
        c.need(binding['schema']=='neural081_projection_binding_v4'and binding['access_policy']==p.POLICY and binding['query_count']==1 and type(binding['query_count'])is int and binding['controller_array_or_label_body_reads']==0,'exact source-issued single-query capability')
        same(binding['support_index_pin'],c.pin(c.encoded(index)),'same full label-free support');same(binding['protected_support'],index['protected_support_descriptor'],'same unopened protected support');same(binding['protected_assessment'],index['protected_assessment_descriptor'],'same unopened protected assessment')
        projected=access.json(row['projection']);same(binding['issuer_reply'],projected,'actual original current-only issuer reply')
        same(projected['context'],binding['issued_context'],'same independently issued context source')
        context=access.json(binding['issued_context']);c.need(context['mode']==identity['mode']and context['replication']==identity['replication']and context['view']==identity['view']and context['outer_person']==identity['outer']and context['canonical_id']==identity['canonical_id']and context['context_alias']==row['context_alias'],'exact private inverse for this one original query')
        public=access.json(binding['public_context']);from candidate_runner import validate_context
        validate_context(public);c.need(public['context_alias']==row['context_alias']and public['mode']==identity['mode']and public['replication']==identity['replication']and public['view']==identity['view'],'actual sanitized matched current context')
        fold=access.json(binding['frozen_model_fold']);same(fold['reference_run'],study['references'],'all modes share same already-closed reference run')
        c.need(fold['view']==identity['view']and fold['outer']==identity['outer']and fold['generation']==index['preparation_generation'],'same complete frozen fold, no cross-fold source')
        same(fold['training_role'],context['training_role'],'same original nine-person training role')
        for action in e['native_actions']:
            mounted={m['target']:m for m in action['mounts']}
            for expected in binding['mounts']:same(mounted.get(expected['target']),expected,'same exact current projected input/model/tool mounts in every action')
        cleanup=access.json(row['cleanup']);same(cleanup['candidate_closure'],dict(e,receipt=row['episode']),'actual closed episode before projection cleanup')
        c.need(all(value is True for value in cleanup['cleanup'].values()),'complete current-context removal before nextquery')
        key=(identity['mode'],identity['replication'],identity['view'],identity['outer'])
        candidate_rows.setdefault(key,[]).append({'id':identity['canonical_id'],'probabilities':e['probabilities']});candidate_closures.setdefault(key,[]).append(row['episode'])
    issuer_closure(study,index,access,source,files,allocation)
    c.need(type(study['panels'])is list and len(study['panels'])==240,'all240 complete assessment panel descriptors')
    for desc,identity in zip(study['panels'],schedule.panels()):
        panel=access.json(desc);same(panel['identity'],identity,'exact all240 canonical source panels')
        if identity['role']=='candidate':
            key=(identity['mode'],identity['replication'],identity['view'],identity['person'])
            same(panel['producer_closures'],candidate_closures[key],'all current-query original producers, no substituted panel')
            same(access.json(panel['submission']),{'schema':'neural081_predictions_v1','predictions':candidate_rows[key]},'every emitted candidate probability equals actual closed query result')
        else:
            original=reference_panels[(identity['role'],identity['handle'],identity['view'],identity['person'])]
            same(panel['producer_closures'],[original['closure']],'exact reference producer');same(panel['submission'],original['predictions'],'unchanged genuine reference numerical output')
    access.budget.check_clock();return {'panels':study['panels'],'strongest':strongest,'source':source,'generation':index['preparation_generation']}
