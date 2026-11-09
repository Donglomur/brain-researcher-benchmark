"""Concrete observe/grade composition; no callbacks replacing scientific producers."""
from pathlib import Path
import sys
import time

PROFILE = 'curated_retrospective_full_v1'
ROOT_NAMES = {'source','packet','targets','reference','output','operator','observation','secrets','store'}
LIMIT_NAMES = {'read_bytes','write_bytes','host_memory_bytes','parent_retained_storage_bytes','free_floor_bytes',
               'qualification_read_bytes','validation_read_bytes','validation_cpu_ns','validation_numeric'}
NUMERIC_NAMES = {'allocation_bytes','elements','serialized_bytes','files','work'}


def descriptor(x):
    u.need(type(x) is dict and set(x) == {'path','pin'},'exact operator descriptor')
    u.path(x['path']); u.only_pin(x['pin']); return x


def selection_pin(r):
    return u.pin(u.encode({k:v for k,v in r.items() if k not in ('qualification','grading_document')}))


def review_document(raw, cli, env):
    r = u.parse(raw)
    fields = {'schema','task_id','selected','operation','panel','condition','selected_modules','cache',
              'central_source','parent_source','registry','authority','campaign_request','work_sha256',
              'original_origin','central_observation_deadline','central_validation_deadline','other_reserve_bytes',
              'limits','qualification','collection','collection_completion','grading_selection','roots'}
    u.need(type(r) is dict and set(r) == fields and r['schema'] == 'neural049_central_review_v1'
           and r['task_id'] == 'NEURAL-049' and r['selected'] is True and r['operation'] == cli['operation'],
           'explicit exact selected central review')
    u.need(r['central_source'] == env['source'] and r['parent_source'] == env['parent_pin'], 'exact distinct central/parent sources')
    u.need(r['panel'] == PROFILE and r['condition'] == cli['condition'], 'same complete panel and alias')
    mods = r['selected_modules']
    u.need(type(mods) is list and mods and mods[0] == 'core' and len(mods) == len(set(mods))
           and mods == [m for m in ('core','T1','D') if m in mods] and type(r['cache']) is bool, 'complete selected modules/cache')
    if r['operation'] == 'collect':
        u.need(cli['panel'] == PROFILE and all(r[k] is None for k in ('collection','collection_completion','grading_selection')),
               'collection has no future grading operands')
    else:
        u.need(cli['panel'] == 'review' and cli['condition'] is None,'separate protected score context')
        for k in ('collection','collection_completion','grading_selection'): descriptor(r[k])
    for k in ('authority','campaign_request','qualification'): descriptor(r[k])
    u.only_pin(r['registry']); u.only_pin({'bytes':0,'sha256':r['work_sha256']})
    for k in ('original_origin','central_observation_deadline','central_validation_deadline'): r[k] = u.finite(r[k])
    u.need(type(r['other_reserve_bytes']) is int and r['other_reserve_bytes'] == cli['other_reserve_bytes'] >= 0,'same unrelated holds')
    roots = r['roots']; u.need(type(roots) is dict and set(roots) == ROOT_NAMES,'complete parent/protected namespaces')
    for p in roots.values(): u.path(p)
    u.need(u.path(roots['targets']) == u.path(roots['packet'])/'private','fixed private packet subtree')
    items = [p for k,p in roots.items() if k != 'targets']
    u.need(all(u.disjoint(x,y) for i,x in enumerate(items) for y in items[i+1:]),'disjoint selected namespaces')
    u.need(u.path(roots['operator']) in u.path(r['authority']['path']).parents,'operator authority location')
    limits = r['limits']; u.need(type(limits) is dict and set(limits) == LIMIT_NAMES,'complete selected resource fields')
    for k,v in limits.items():
        if k != 'validation_numeric': u.integer(v,1)
    u.need(type(limits['validation_numeric']) is dict and set(limits['validation_numeric']) == NUMERIC_NAMES,'full public-array validation resources')
    for v in limits['validation_numeric'].values(): u.integer(v,1)
    return r


def parent_config(r, a, env):
    files = env['parent_manifest']['files']
    cfg = {'source_root':str(env['parent_root']),'manifest_path':str(env['parent_manifest_path']),'manifest':env['parent_pin'],
           'bootstrap_source':files['program/bootstrap.py'],'entry_source':files['program/entry.py'],
           'origin':float(a['clock']['origin']),'bootstrap_deadline':a['clock']['readback_end'],
           'launch_source_read_cap':files['program/bootstrap.py']['bytes']+files['program/entry.py']['bytes']+2,
           'source_read_cap':sum(p['bytes']+1 for p in files.values())+env['parent_pin']['bytes']+1,
           'authority':r['authority'],'role':'observe' if r['operation'] == 'collect' else 'grade'}
    if cfg['role'] == 'grade': cfg['grading'] = r['grading_selection']
    return cfg


def parent_command(cfg, a, env):
    return [a['host_python'],'-I','-B','-c',env['parent']['launch_code'].CODE,env['parent']['core'].encoded(cfg).decode()]


def qualify_review(r, a, env, host):
    root = u.path(a['roots']['operator']); p = u.path(r['qualification']['path'])
    u.need(root in p.parents,'independent central qualification namespace')
    q = u.parse(host.read(p,1048576,r['qualification']['pin'],readonly=True))
    fields = {'complete_panel','inherited_clock','central_resources','public_array_validation_resources',
              'actual_caller_observation','physical_root_custody','interpreter_environment','protected_scoring_boundary'}
    u.need(q.get('schema') == 'neural049_actual_central_qualification_v1' and q.get('realm') == 'actual_external_evidence'
           and q.get('qualified') is True and q.get('issuer') == a['operator_identity'] and q.get('task_id') == a['task_id']
           and q.get('central_source') == env['source'] and q.get('parent_source') == env['parent_pin']
           and q.get('selection') == selection_pin(r) and q.get('authority') == r['authority']['pin']
           and q.get('original_origin') == r['original_origin'],'exact independently qualified central selection')
    u.need(type(q.get('findings')) is dict and set(q['findings']) == fields and all(x is True for x in q['findings'].values()),
           'all actual central findings, not source-construction qualification')
    rows = q.get('evidence'); u.need(type(rows) is list and 1 <= len(rows) <= 32,'bounded actual proof evidence')
    for d in rows:
        descriptor(d); u.need(root in u.path(d['path']).parents,'operator proof artifact')
        host.read(d['path'],1048576,d['pin'],readonly=True,retain=False)
    return r['qualification']['pin']


def configure(r, a, env, host):
    origin = r['original_origin']; clock = a['clock']; end = clock['readback_end']
    now = host.tick(min(host.entry_start+120,end))
    u.need(origin == clock['origin'] and origin <= host.entry_start <= now < end,'local startup inside original readback interval')
    u.need(end < r['central_observation_deadline'] < r['central_validation_deadline'],'separate later capture/audit intervals')
    host.origin = origin; host.deadline = r['central_validation_deadline']
    limits = r['limits']; res = a['resources']; total = sum(p['bytes']+1 for p in env['freeze_files'].values())
    generic = 3*(4*(2097152+1)+2*(16777216+1)+total)
    campaigns = 2*(env['gate'].CAPTURE_CAP+env['gate'].PREFERENCE_READ_CAP+env['gate'].VALIDATOR['bytes']+1)
    u.need(campaigns == env['bindings']['shared_four_pass_read_bound'] == 16809096,'actual adopted complete shared capacity graph')
    minimum = host.reads+generic+campaigns+2*total+80*1048576+limits['qualification_read_bytes']+limits['validation_read_bytes']
    u.need(limits['read_bytes'] >= minimum and limits['write_bytes'] >= 1048576,'complete central logical envelope')
    u.need(limits['qualification_read_bytes'] >= res['host_read_bytes'] and limits['validation_read_bytes'] >= res['host_read_bytes'],
           'qualification and repeated full original admission ceilings')
    numeric = {k:a['profiles']['audit']['numeric_'+k] for k in NUMERIC_NAMES}
    u.need(limits['validation_numeric'] == numeric,'same complete actual public validation profile')
    u.need(limits['validation_cpu_ns'] >= a['profiles']['audit']['cpu_ns'],'independently qualified full CPU audit ceiling')
    u.need(limits['host_memory_bytes'] >= res['host_live_bytes']+16*1048576,'full parent public-array working memory plus central definitions')
    host.read_cap = limits['read_bytes']; host.write_cap = limits['write_bytes']


def establish_limit(r, host):
    import resource
    host.tick(); host.limit_establishment = {'attempted':True,'syscall_returned':False,'clock_closed':False,'state_unknown':True}
    resource.setrlimit(resource.RLIMIT_AS,(r['limits']['host_memory_bytes'],r['limits']['host_memory_bytes']))
    host.limit_establishment.update(syscall_returned=True,state_unknown=False)
    host.tick(); host.limit_establishment['clock_closed'] = True


def recheck(env, host):
    for name,p in sorted(env['freeze_files'].items()): host.read(env['repo']/name,2097152,p,retain=False)
    return {'members':len(env['freeze_files']),'exact':True}


def raw_budget(b):
    return None if b is None else {'origin':b.origin,'deadline':b.deadline,'read_cap':b.read_cap,'write_cap':b.write_cap,
                                  'read_reserved':b.read_bytes,'write_reserved':b.write_bytes}


def collection_before_grade(r, a, env, host, qualification_budget):
    d = r['collection']; u.need(u.path(d['path']).name == 'RESULT.json','existing completed central result')
    doc = u.parse(host.read(d['path'],131072,d['pin'],readonly=True))
    u.need(doc.get('schema') == 'neural049_central_result_v1' and doc.get('status') == 'complete' and doc.get('operation') == 'collect'
           and doc.get('panel') == PROFILE and doc.get('parent_source') == env['parent_pin'] and doc.get('central_source') == env['source']
           and doc.get('authority') == r['authority']['pin'] and doc.get('original_origin') == a['clock']['origin']
           and doc.get('selected_modules') == r['selected_modules'] and doc.get('cache') is r['cache']
           and doc.get('private_grading_performed') is False and doc.get('actual_parent_operation_observed') is True
           and doc.get('own_future_exit_not_self_certified') is True,'same actual complete collection')
    root = u.path(a['roots']['operator']); d = r['collection_completion']
    u.need(root in u.path(d['path']).parents,'outside-observer completion namespace')
    end = u.parse(host.read(d['path'],1048576,d['pin'],readonly=True))
    u.need(end.get('schema') == 'neural049_external_central_completion_v1' and end.get('realm') == 'actual_original_tool_capture'
           and end.get('issuer') == a['operator_identity'] and end.get('central_source') == env['source']
           and end.get('parent_source') == env['parent_pin'] and end.get('authority') == r['authority']['pin']
           and end.get('collection') == r['collection'] and end.get('review') == doc['review']
           and end.get('provisional') is False and type(end.get('exit_code')) is int and end['exit_code'] == 0
           and end.get('natural_exit') is True and end.get('streams_complete') is True
           and end.get('observed_after_central_return') is True
           and doc['observed_end'] <= u.finite(end['completed_at']) <= host.tick(),
           'independent original central completion, not self-certified future exit')
    intent_path = u.path(r['collection']['path']).parent/'INTENT.json'
    intent = u.parse(host.read(intent_path,131072,doc['receipts']['intent'],readonly=True))
    u.need(end.get('argv') == intent['central_argv'] and end.get('cwd') == str(env['repo'])
           and intent['review'] == doc['review'] and intent['authority'] == r['authority']['pin'], 'original central invocation/source/selection join')
    evidence = end.get('capture_artifacts'); u.need(type(evidence) is list and 1 <= len(evidence) <= 32,'retained original external capture evidence')
    for item in evidence:
        descriptor(item); u.need(root in u.path(item['path']).parents,'operator external capture custody')
        host.read(item['path'],1048576,item['pin'],readonly=True,retain=False)
    u.need(root in u.path(r['grading_selection']['path']).parents,'protected late parent declaration before capture')
    q = env['parent']['authority'].grading_selection(a,r['grading_selection'],qualification_budget)
    u.need(q['observation'] == doc['joined']['observation'],'late parent grading binds exact completed collection')
    # The independent issuer must additionally bind the already existing
    # outside central completion to its separate parent outer-completion proof.
    proof = q['external_completion']; p = root/env['parent']['core'].relative(proof['path'])
    outer = u.parse(host.read(p,a['resources']['qualification_bytes'],proof['pin'],readonly=True))
    u.need(outer.get('central_collection') == r['collection'] and outer.get('central_external_completion') == r['collection_completion']
           and outer.get('nested_caller') == doc['receipts']['CALLER.json'], 'separate nested/central original completion chronology')
    r['grading_document'] = q
    env['prior_collection'] = doc
    return doc


def retain_bundle(bundle, host):
    result = {'attempted':[],'retained':{},'errors':[],'complete':False,'no_retry':True}
    for name,key in (('caller.stdout','stdout'),('caller.stderr','stderr'),('CALLER.json','record')):
        result['attempted'].append(name)
        try: result['retained'][name] = host.save(name,bundle[key],65536)
        except BaseException as error: result['errors'].append({'artifact':name,'error_type':type(error).__name__,'durability':'unknown'})
    result['complete'] = not result['errors']
    return result


def execute(cli, env, host):
    bundle = retention = qualification_budget = validation_budget = None
    receipts = {}; attempted = False; phase = 'fixed_registry'; r = a = None
    validation_cpu = {'attempted':False,'before_ns':None,'after_ns':None,'elapsed_ns':None,'complete':False}
    try:
        routing = env['components']['routing']; readback = env['components']['readback']; registry = env['repo']/routing.REGISTRY
        raw = host.read(registry,131072); doc = u.parse(raw); routing.qualify(doc,cli,env,host)
        phase = 'review'
        p = u.path(cli['review']); u.need(p.parent == env['here']/'operator-selections' and p.suffix == '.json','fixed operator review namespace')
        review_raw = host.read(p,32768,readonly=True); r = review_document(review_raw,cli,env)
        roots = r['roots']; host.protected = tuple(u.path(x) for x in (roots['packet'],roots['secrets'],str(u.path(roots['store'])/'private')))
        u.need(all(u.disjoint(env['here'],x) and u.disjoint(env['parent_root'],x) for x in host.protected),'source/operator review outside private roots')
        u.need(r['registry'] == u.pin(raw),'exact qualified registry')
        routing.qualify(doc,cli,env,host); first = routing.campaign(r,doc,cli,env,host)
        authority_raw = host.read(r['authority']['path'],2097152,r['authority']['pin'],readonly=True); a = u.parse(authority_raw)
        u.need(a.get('roots') == roots and a.get('active') is True,'authority joins protected namespaces before imports')
        u.need(a['roots']['source'] == str(env['parent_root']) and a['host_python'] == sys.executable,'exact source/interpreter')
        u.need(a['modules'] == r['selected_modules'] and a['cache'] is r['cache'],'same complete selected parent modules')
        phase = 'parent_definitions'
        env['bind_parent'](env,r,a,host)
        parent = env['parent']; parent['configuration'].validate(a,env['parent_pin'])
        configure(r,a,env,host); proof = qualify_review(r,a,env,host)
        host.reserve(r['limits']['qualification_read_bytes'])
        qualification_budget = parent['core'].Budget(r['original_origin'],a['clock']['readback_end'],r['limits']['qualification_read_bytes'],0)
        phase = 'parent_qualification'; parent['authority'].qualify(a,env['parent_pin'],qualification_budget)
        operand = r['authority'] if r['operation'] == 'collect' else r['collection']
        u.need(cli['program'] == operand['path'],'exact selected operand')
        output = u.path(cli['output']); u.need(all(u.disjoint(output,x) for x in a['roots'].values()),'fresh central output outside every parent root')
        command = routing.command(cli,doc,env)
        if r['operation'] == 'grade': collection_before_grade(r,a,env,host,qualification_budget)
        routing.qualify(u.parse(host.read(registry,131072,r['registry'])),cli,env,host)
        second = routing.campaign(r,doc,cli,env,host); campaign = env['gate'].finish(first,second,command,env['repo'])
        host.read(cli['review'],32768,u.pin(review_raw),readonly=True); host.read(r['authority']['path'],2097152,r['authority']['pin'],readonly=True)
        qualify_review(r,a,env,host); source_join = recheck(env,host)
        config = parent_config(r,a,env); nested = parent_command(config,a,env)
        phase = 'limit_establishment'; qualification_budget.tick(); establish_limit(r,host)
        free = sum(r['limits'][k] for k in ('parent_retained_storage_bytes','write_bytes','free_floor_bytes'))+r['other_reserve_bytes']
        host.prepare(output,free); phase = 'output_created'
        receipts['intent'] = host.save('INTENT.json',{'schema':'neural049_central_intent_v1','task_id':a['task_id'],'operation':r['operation'],'panel':PROFILE,
            'source':env['source'],'parent_source':env['parent_pin'],'review':u.pin(review_raw),'authority':r['authority']['pin'],'qualification':proof,
            'original_origin':r['original_origin'],'original_parent_clock':a['clock'],'selected_modules':a['modules'],'cache':a['cache'],
            'central_observation_deadline':r['central_observation_deadline'],'central_validation_deadline':r['central_validation_deadline'],
            'central_argv':command,'parent_argv':nested,'central_cwd':str(env['repo']),'parent_cwd':a['roots']['source'],
            'host_environment':a['host_environment'],'no_mutating_caller_signals':True,'forced_termination_supported':False,'limits':r['limits']})
        receipts['campaign'] = host.save('CAMPAIGN.json',campaign)
        host.reserve(131072); qualification_budget.tick(); phase = 'caller_entered'; attempted = True
        bundle = parent['caller_observer'].run(nested,a['clock']['readback_end'],r['central_observation_deadline'],a['host_environment'],a['roots']['source'])
        phase = 'caller_returned'; retention = retain_bundle(bundle,host); receipts.update(retention['retained'])
        u.need(retention['complete'],'independent original streams/caller durability')
        host.reserve(r['limits']['validation_read_bytes'])
        validation_budget = parent['core'].Budget(r['original_origin'],r['central_validation_deadline'],r['limits']['validation_read_bytes'],0)
        phase = 'public_readback'; before_cpu = time.process_time_ns()
        validation_cpu.update(attempted=True,before_ns=before_cpu)
        joined = readback.result(bundle,nested,a,r,env,config,host,validation_budget)
        after_cpu = time.process_time_ns(); cpu = after_cpu-before_cpu
        validation_cpu.update(after_ns=after_cpu,elapsed_ns=cpu,complete=True)
        u.need(type(cpu) is int and 0 <= cpu <= r['limits']['validation_cpu_ns'],'complete public validation observed CPU within qualified bound')
        phase = 'readback_admitted'; source_join = recheck(env,host)
        result = {'schema':'neural049_central_result_v1','status':'complete','task_id':a['task_id'],'operation':r['operation'],'panel':PROFILE,
            'selected_modules':a['modules'],'cache':a['cache'],'completion_scope':'whole_three_module_suite' if a['modules'] == ['core','T1','D'] else 'complete_selected_modules',
            'central_source':env['source'],'parent_source':env['parent_pin'],'authority':r['authority']['pin'],'review':u.pin(review_raw),'original_origin':r['original_origin'],
            'source_closure':source_join,'receipts':receipts,'capture_retention':retention,'joined':joined,'private_grading_performed':r['operation'] == 'grade',
            'actual_parent_operation_observed':True,'scientific_qualification_inferred':False,'qualified_neural_contribution':None,
            'observed_end':host.tick(),'own_future_exit_not_self_certified':True,'automatic_retry':False,'costs_before_publication':host.record(),
            'parent_qualification_costs':raw_budget(qualification_budget),'public_validation_costs':raw_budget(validation_budget),
            'validation_process_cpu_ns':cpu,'validation_cpu_observation':validation_cpu}
        p = host.save('RESULT.json',result); host.tick()
        return {'status':'complete','path':str(host.root/'RESULT.json'),'pin':p,'terminal_publication_logical_bytes':p['bytes']}
    except BaseException as error:
        if bundle is None: bundle = getattr(error,'bundle',None)
        if bundle is not None and retention is None:
            retention = retain_bundle(bundle,host); receipts.update(retention['retained'])
        failure = {'schema':'neural049_central_failure_v1','phase':phase,'error_type':type(error).__name__,'caller_attempted':attempted,
            'caller':None if bundle is None else bundle['record'],'unknown_surviving_child_state':attempted,'forced_termination_supported':False,
            'private_grading_may_have_started':attempted and r is not None and r['operation'] == 'grade','receipts':receipts,'capture_retention':retention,
            'costs':host.record(),'parent_qualification_costs':raw_budget(qualification_budget),'public_validation_costs':raw_budget(validation_budget),
            'parent_source_accounting':env.get('parent_context'),'validation_cpu_observation':validation_cpu,
            'automatic_retry':False,'later_errors':[]}
        if validation_cpu['attempted'] and validation_cpu['after_ns'] is None:
            try:
                validation_cpu['after_ns'] = time.process_time_ns()
                validation_cpu['elapsed_ns'] = validation_cpu['after_ns']-validation_cpu['before_ns']
            except BaseException as later: failure['later_errors'].append({'error_type':type(later).__name__,'cpu_observation':'unknown'})
        error.original_caller_bundle = bundle; error.failure_record = failure
        try:
            if host.prepared: host.save('FAILED.json',failure)
        except BaseException as later: failure['later_errors'].append({'error_type':type(later).__name__,'durability':'unknown'})
        failure['costs_after_failure_publication'] = host.record()
        raise
