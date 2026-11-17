"""Concrete full PAC parent observation/protected grade, with no result callback."""
from pathlib import Path
import sys

def descriptor(x):
    u.need(type(x)is dict and set(x)=={'path','pin'},'exact operator descriptor');u.path(x['path']);u.only_pin(x['pin']);return x

def selection_pin(review):return u.pin(u.encode({k:v for k,v in review.items()if k not in ('qualification','grading_document')}))

def review_document(raw,cli,env):
    r=u.parse(raw)
    fields={'schema','task_id','selected','operation','panel','condition','central_source','parent_source','registry','authority',
        'campaign_request','work_sha256','original_origin','central_observation_deadline','central_readback_deadline',
        'other_reserve_bytes','limits','qualification','collection','collection_completion','grading_selection','roots'}
    u.need(type(r)is dict and set(r)==fields and r['schema']=='neural042_central_review_v1'and r['task_id']=='NEURAL-042'
        and r['selected']is True and r['operation']==cli['operation'],'explicit selected complete operation')
    u.need(r['central_source']==env['source']and r['parent_source']==env['parent_pin'],'distinct full central/parent sources')
    u.need(r['panel']=='full_pac'and r['condition']==cli['condition'],'one complete panel and alias')
    if r['operation']=='collect':
        u.need(r['panel']==cli['panel']==env['components']['routing'].ALIASES[cli['condition']]
            and all(r[k]is None for k in ('collection','collection_completion','grading_selection')),'collection has no grading operands')
    else:
        u.need(cli['panel']=='review'and cli['condition']is None,'separate protected scoring action')
        for k in ('collection','collection_completion','grading_selection'):descriptor(r[k])
    for k in ('authority','campaign_request','qualification'):descriptor(r[k])
    u.only_pin(r['registry']);u.only_pin({'bytes':0,'sha256':r['work_sha256']})
    for k in ('original_origin','central_observation_deadline','central_readback_deadline'):r[k]=u.finite(r[k])
    u.need(type(r['other_reserve_bytes'])is int and r['other_reserve_bytes']==cli['other_reserve_bytes']>=0,'same unrelated holds')
    roots=r['roots'];u.need(type(roots)is dict and set(roots)=={'operator','private','secrets'},'protected roots before authority capture')
    for value in roots.values():u.path(value)
    u.need(all(u.disjoint(x,y)for j,x in enumerate(roots.values())for y in list(roots.values())[j+1:]),'disjoint metadata/private namespaces')
    u.need(u.path(roots['operator'])in u.path(r['authority']['path']).parents,'operator authority namespace')
    limits=r['limits'];u.need(type(limits)is dict and set(limits)=={'read_bytes','write_bytes','host_memory_bytes','parent_retained_storage_bytes','free_floor_bytes'},'complete selected resource fields')
    for v in limits.values():u.integer(v,1)
    return r

def parent_config(r,a,env):
    files=env['parent_manifest']['files'];role='observe'if r['operation']=='collect'else'grade'
    config={'source_root':str(env['parent_root']),'manifest_path':str(env['parent_manifest_path']),'manifest':env['parent_pin'],
        'bootstrap_source':files['program/bootstrap.py'],'entry_source':files['program/entry.py'],
        'origin':a['clock']['origin'],'bootstrap_deadline':a['clock']['readback_end'],
        'launch_source_read_cap':files['program/bootstrap.py']['bytes']+files['program/entry.py']['bytes']+2,
        'source_read_cap':sum(p['bytes']+1 for p in files.values())+env['parent_pin']['bytes']+1,
        'authority':r['authority'],'role':role}
    if role=='grade':config['grading']=r['grading_selection']
    return config

def parent_command(config,a,env):
    return [a['host_python'],'-I','-B','-c',env['parent']['launch_code'].CODE,env['parent']['core'].encoded(config).decode()]

def qualify_review(r,a,env,host):
    q=r['qualification'];root=u.path(a['roots']['operator']);p=u.path(q['path']);u.need(root in p.parents,'central proof in operator namespace')
    d=u.parse(host.read(p,1048576,q['pin'],readonly=True))
    required={'complete_panel','inherited_clock','central_resources','actual_caller_observation','physical_root_custody','interpreter_environment','protected_scoring_boundary'}
    u.need(d.get('schema')=='neural042_actual_central_qualification_v1'and d.get('realm')=='actual_external_evidence'
        and d.get('qualified')is True and d.get('issuer')==a['issuer']and d.get('task_id')==a['task_id']
        and d.get('central_source')==env['source']and d.get('parent_source')==env['parent_pin']
        and d.get('selection')==selection_pin(r)and d.get('authority')==r['authority']['pin']
        and d.get('original_origin')==r['original_origin'],'independent exact central configuration/clock proof')
    u.need(type(d.get('findings'))is dict and set(d['findings'])==required and all(x is True for x in d['findings'].values()),'all actual central findings')
    evidence=d.get('evidence');u.need(type(evidence)is list and 1<=len(evidence)<=32,'bounded independent actual evidence')
    for item in evidence:
        descriptor(item);p=u.path(item['path']);u.need(root in p.parents,'operator-owned evidence');host.read(p,1048576,item['pin'],readonly=True,retain=False)
    return q['pin']

def configure(r,a,env,host):
    clock=a['clock'];origin=r['original_origin']
    u.need(origin==clock['origin']and origin<=host.entry_start<=host.tick()<min(host.entry_start+120,clock['readback_end']),'local startup inside original readback interval')
    u.need(clock['readback_end']<r['central_observation_deadline']<r['central_readback_deadline'],'separate central-only closeout cutoffs')
    host.origin=origin;host.deadline=r['central_readback_deadline']
    context=env['parent_context'];context['origin']=origin;context['deadline']=host.deadline
    host.protected=tuple(u.path(a['roots'][k])for k in ('private','secrets'))
    limits=r['limits'];res=a['resources'];source=sum(p['bytes']+1 for p in env['freeze_files'].values())
    # Repeated original admission is real work. Reserve the selected parent's
    # whole observer-read ceiling in addition to central generic/source work;
    # dynamic original capture still precharges every body/sentinel and can
    # refuse. No symbolic estimate is a proof of actual whole-study feasibility.
    generic=3*(4*(2097152+1)+2*(16777216+1)+source)
    campaigns=2*(env['gate'].CAPTURE_CAP+env['gate'].PREFERENCE_READ_CAP+env['gate'].VALIDATOR['bytes']+1)
    minimum=host.reads+generic+campaigns+2*source+80*1048576+res['observer_read_bytes']+res['host_read_bytes']
    u.need(limits['read_bytes']>=minimum and limits['write_bytes']>=1048576,'selected complete central resource envelope')
    u.need(limits['host_memory_bytes']>=16*1048576+res['producer_bytes']+res['journal_bytes']+res['closure_bytes']+8*res['candidate_report_bytes'],'selected full metadata working memory')
    host.read_cap=limits['read_bytes'];host.write_cap=limits['write_bytes']

def establish_limit(r,host):
    import resource
    host.tick();host.limit_establishment={'attempted':True,'syscall_returned':False,'clock_closed':False,'state_unknown':True}
    resource.setrlimit(resource.RLIMIT_AS,(r['limits']['host_memory_bytes'],r['limits']['host_memory_bytes']))
    host.limit_establishment.update(syscall_returned=True,state_unknown=False)
    host.tick();host.limit_establishment['clock_closed']=True

def recheck(env,host):
    for name,p in sorted(env['freeze_files'].items()):host.read(env['repo']/name,2097152,p,retain=False)
    return {'members':len(env['freeze_files']),'exact':True}

def collection_before_grade(r,a,env,host):
    collection=r['collection'];u.need(u.path(collection['path']).name=='RESULT.json','completed central collection result')
    doc=u.parse(host.read(collection['path'],131072,collection['pin'],readonly=True))
    u.need(doc.get('schema')=='neural042_central_result_v1'and doc.get('status')=='complete'and doc.get('operation')=='collect'
        and doc.get('panel')=='full_pac'and doc.get('parent_source')==env['parent_pin']and doc.get('central_source')==env['source']
        and doc.get('authority')==r['authority']['pin']and doc.get('original_origin')==a['clock']['origin']
        and doc.get('private_grading_performed')is False and doc.get('actual_parent_operation_observed')is True,'same complete prior collection')
    completion=r['collection_completion'];root=u.path(a['roots']['operator']);p=u.path(completion['path'])
    u.need(root in p.parents,'independently issued central completion namespace')
    external=u.parse(host.read(p,1048576,completion['pin'],readonly=True))
    u.need(external.get('schema')=='neural042_external_central_completion_v1'and external.get('realm')=='actual_original_tool_capture'
        and external.get('issuer')==a['issuer']and external.get('central_source')==env['source']and external.get('parent_source')==env['parent_pin']
        and external.get('authority')==r['authority']['pin']and external.get('collection')==collection
        and type(external.get('exit_code'))is int and external['exit_code']==0 and external.get('natural_exit')is True
        and external.get('streams_complete')is True and external.get('observed_after_central_return')is True
        and doc['observed_end']<=u.finite(external['completed_at'])<=host.tick(),'original external completion, never provisional self-attestation')
    rows=external.get('capture_artifacts');u.need(type(rows)is list and 1<=len(rows)<=32,'original external tool/stream/command evidence')
    for item in rows:
        descriptor(item);p=u.path(item['path']);u.need(root in p.parents,'protected original capture artifact');host.read(p,1048576,item['pin'],readonly=True,retain=False)
    grading,_=env['parent']['authority'].grading_selection(a,{'pin':env['parent_pin'],'authority_pin':r['authority']['pin']},r['grading_selection'],host)
    u.need(grading['observation']==doc['joined']['observation'],'late parent grade binds exact prior collection')
    r['grading_document']=grading;return collection['pin']

def retain_bundle(bundle,host):
    result={'attempted':[],'retained':{},'errors':[],'complete':False,'no_retry':True}
    for name,key in (('caller.stdout','stdout'),('caller.stderr','stderr'),('CALLER.json','record')):
        result['attempted'].append(name)
        try:result['retained'][name]=host.save(name,bundle[key],65536)
        except BaseException as error:result['errors'].append({'artifact':name,'error_type':type(error).__name__,'durability':'unknown'})
    result['complete']=not result['errors'];return result

def execute(cli,env,host):
    routing=env['components']['routing'];readback=env['components']['readback'];repo=env['repo'];role='observe'if cli['operation']=='collect'else'grade'
    registry=repo/routing.REGISTRY;raw=host.read(registry,131072);doc=u.parse(raw);routing.qualify(doc,cli,env,host)
    review_path=u.path(cli['review']);u.need(review_path.parent==env['here']/'operator-selections'and review_path.suffix=='.json','fixed operator review namespace')
    review_raw=host.read(review_path,32768,readonly=True);r=review_document(review_raw,cli,env)
    host.protected=tuple(u.path(r['roots'][k])for k in ('private','secrets'))
    u.need(all(u.disjoint(env['parent_root'],p)for p in host.protected),'protected roots separate from source/review realm')
    u.need(r['registry']==u.pin(raw),'exact already qualified registry')
    routing.qualify(doc,cli,env,host);first=routing.campaign(r,doc,cli,env,host)
    authority_raw=host.read(r['authority']['path'],2097152,r['authority']['pin'],readonly=True);a=u.parse(authority_raw)
    u.need(all(a['roots'][k]==v for k,v in r['roots'].items()),'authority joins preadmitted protected roots')
    env['parent']['authority'].selected(a,env['parent_pin'],r['original_origin'],role)
    u.need(a['roots']['source']==str(env['parent_root'])and a['host_python']==sys.executable,'exact parent source/interpreter')
    configure(r,a,env,host);proof=qualify_review(r,a,env,host)
    env['parent']['authority'].qualify(a,env['parent_pin'],r['original_origin'],role,host)
    operand=r['authority']if r['operation']=='collect'else r['collection'];u.need(cli['program']==operand['path'],'selected authority/collection operand')
    output=u.path(cli['output']);u.need(all(u.disjoint(output,p)for p in a['roots'].values()),'central output outside all parent roots')
    config=parent_config(r,a,env);command=routing.command(cli,doc,env)
    if r['operation']=='grade':collection_before_grade(r,a,env,host)
    routing.qualify(u.parse(host.read(registry,131072,r['registry'])),cli,env,host)
    second=routing.campaign(r,doc,cli,env,host);campaign=env['gate'].finish(first,second,command,repo)
    host.read(cli['review'],32768,u.pin(review_raw),readonly=True);host.read(r['authority']['path'],2097152,r['authority']['pin'],readonly=True)
    qualify_review(r,a,env,host);sources=recheck(env,host);nested=parent_command(config,a,env)
    bundle=None;retention=None;receipts={};phase='before_output_setup';attempted=False
    try:
        phase='limit_establishment';establish_limit(r,host)
        free=r['limits']['parent_retained_storage_bytes']+r['limits']['write_bytes']+r['limits']['free_floor_bytes']+r['other_reserve_bytes']
        host.prepare(output,free);phase='output_created'
        receipts['intent']=host.save('INTENT.json',{'schema':'neural042_central_intent_v1','task_id':a['task_id'],'operation':r['operation'],'panel':'full_pac',
            'source':env['source'],'parent_source':env['parent_pin'],'review':u.pin(review_raw),'authority':r['authority']['pin'],'qualification':proof,
            'original_origin':a['clock']['origin'],'parent_readback_deadline':a['clock']['readback_end'],'central_observation_deadline':r['central_observation_deadline'],
            'central_readback_deadline':r['central_readback_deadline'],'central_argv':command,'parent_argv':nested,'cwd':a['roots']['source'],
            'host_environment':a['host_environment'],'no_mutating_caller_signals':True,'forced_termination_supported':False,'limits':r['limits']})
        receipts['campaign']=host.save('CAMPAIGN.json',campaign);host.reserve(2*65536);phase='caller_entered';attempted=True
        bundle=env['parent']['caller_observer'].run(nested,a['clock']['readback_end'],r['central_observation_deadline'],a['host_environment'],a['roots']['source'])
        phase='caller_returned';retention=retain_bundle(bundle,host);receipts.update(retention['retained']);u.need(retention['complete'],'all original caller artifacts durable')
        joined=readback.result(bundle,nested,a,r,env,config,host);phase='readback_admitted';sources=recheck(env,host)
        result={'schema':'neural042_central_result_v1','status':'complete','task_id':a['task_id'],'operation':r['operation'],'panel':'full_pac',
            'central_source':env['source'],'parent_source':env['parent_pin'],'authority':r['authority']['pin'],'review':u.pin(review_raw),'original_origin':a['clock']['origin'],
            'source_closure':sources,'receipts':receipts,'capture_retention':retention,'joined':joined,'private_grading_performed':r['operation']=='grade',
            'actual_parent_operation_observed':True,'scientific_qualification_inferred':False,'qualified_neural_contribution':None,'observed_end':host.tick(),
            'own_future_exit_not_self_certified':True,'automatic_retry':False,'costs_before_publication':host.record()}
        p=host.save('RESULT.json',result);host.tick();return {'status':'complete','path':str(host.root/'RESULT.json'),'pin':p,'terminal_publication_logical_bytes':p['bytes']}
    except BaseException as error:
        if bundle is None:bundle=getattr(error,'bundle',None)
        if bundle is not None and retention is None:
            retention=retain_bundle(bundle,host);receipts.update(retention['retained'])
        failure={'schema':'neural042_central_failure_v1','phase':phase,'error_type':type(error).__name__,'caller_attempted':attempted,
            'caller':None if bundle is None else bundle['record'],'unknown_surviving_child_state':attempted,'forced_termination_supported':False,
            'private_grading_may_have_started':attempted and r['operation']=='grade','receipts':receipts,'capture_retention':retention,
            'costs':host.record(),'automatic_retry':False,'later_errors':[]}
        error.original_caller_bundle=bundle;error.failure_record=failure
        try:
            if host.prepared:host.save('FAILED.json',failure)
        except BaseException as later:failure['later_errors'].append({'error_type':type(later).__name__,'durability':'unknown'})
        failure['costs_after_failure_publication']=host.record();raise
