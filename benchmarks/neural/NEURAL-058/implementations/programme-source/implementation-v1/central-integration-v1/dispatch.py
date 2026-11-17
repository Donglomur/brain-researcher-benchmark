"""Qualified literal original observe/grade launches with separate central custody."""
from pathlib import Path
import sys


def descriptor(value):
    u.need(type(value) is dict and set(value) == {'path','pin'}, 'exact operator descriptor')
    u.path(value['path']); u.only_pin(value['pin']); return value


def selection_pin(review):
    return u.pin(u.encode({k:v for k,v in review.items() if k != 'qualification'}))


def review_document(raw, cli, env):
    r = u.parse(raw)
    fields = {'schema','task_id','selected','operation','condition','central_source','parent_source','registry',
              'request','production','collection','collection_root_closure','campaign_request','work_sha256','origin','parent_deadline',
              'observation_deadline','readback_deadline','limits','parent_limits','host_python','environment',
              'cwd','roots','qualification','other_reserve_bytes'}
    u.need(type(r) is dict and set(r) == fields and r['schema'] == 'neural058_central_review_v1'
           and r['task_id'] == 'NEURAL-058' and r['selected'] is True and r['operation'] == cli['operation'],
           'explicit complete central selection')
    u.need(r['central_source'] == env['source'] and r['parent_source'] == env['parent_pin']
           and r['condition'] == cli['condition'], 'exact sources and condition')
    u.need(r['condition'] in env['components']['routing'].ALIASES, 'default or one full-scope alias')
    if r['operation'] == 'collect':
        u.need(r['collection'] is None and r['collection_root_closure'] is None, 'collect cannot receive prior scores')
    else:
        u.need(r['condition'] is None, 'grade is distinct from information conditions')
        descriptor(r['collection']); descriptor(r['collection_root_closure'])
    for key in ('request','production','campaign_request','qualification'): descriptor(r[key])
    u.only_pin(r['registry']); u.only_pin({'bytes':0,'sha256':r['work_sha256']})
    for key in ('origin','parent_deadline','observation_deadline','readback_deadline'): r[key] = u.finite(r[key])
    u.need(r['origin'] < r['parent_deadline'] < r['observation_deadline'] < r['readback_deadline'],
           'original parent and separately selected outer closure intervals')
    u.need(r['host_python'] == sys.executable and r['cwd'] == str(env['parent_root']), 'qualified interpreter/source cwd')
    u.need(type(r['environment']) is dict and all(type(k) is str and type(v) is str and '\0' not in k+v
                                                for k,v in r['environment'].items()), 'literal selected environment')
    u.need(type(r['other_reserve_bytes']) is int and r['other_reserve_bytes'] == cli['other_reserve_bytes'] >= 0,
           'exact unrelated holds')
    roots = r['roots']; names = {'source','prepared','private','original','output','observation','operator','secrets'}
    u.need(type(roots) is dict and set(roots) == names and roots['source'] == str(env['parent_root']),
           'all protected namespaces before dynamic captures')
    values = list(roots.values())
    for value in values: u.path(value)
    u.need(all(u.disjoint(x,y) for j,x in enumerate(values) for y in values[j+1:]), 'eight disjoint original roots')
    for key in ('request','production','qualification'):
        u.need(u.path(roots['operator']) in u.path(r[key]['path']).parents, 'selected operator-only authority')
    limits = r['limits']
    u.need(type(limits) is dict and set(limits) == {'read_bytes','write_bytes','host_memory_bytes',
            'parent_retained_storage_bytes','free_floor_bytes'}, 'whole central resource fields')
    for value in limits.values(): u.integer(value,1)
    u.need(type(r['parent_limits']) is dict and set(r['parent_limits']) == {'read_bytes','write_bytes'},
           'exact original entry budgets')
    for value in r['parent_limits'].values(): u.integer(value,1)
    return r


def original_command(r, request, env):
    core = env['parent']['core']; files = env['parent_manifest']['files']
    return [r['host_python'],'-I',str(env['parent_root']/'program/entry.py'),
            '--mode','observe' if r['operation'] == 'collect' else 'grade',
            '--source-root',str(env['parent_root']),'--manifest',str(env['parent_manifest_path']),
            '--manifest-pin',core.encoded(env['parent_pin']).decode(),
            '--bootstrap-pin',core.encoded(files['program/bootstrap.py']).decode(),
            '--request',r['request']['path'],'--request-pin',core.encoded(r['request']['pin']).decode(),
            '--origin',str(request['origin']),'--deadline',str(request['deadline']),
            '--read-cap',str(r['parent_limits']['read_bytes']),'--write-cap',str(r['parent_limits']['write_bytes'])]


def expected_collect(request, production, env):
    core = env['parent']['core']; files = env['parent_manifest']['files']
    return [request['python'],'-I',str(env['parent_root']/'program/entry.py'),
            '--mode','collect','--source-root',str(env['parent_root']),
            '--manifest',production['source_manifest_path'],'--manifest-pin',core.encoded(env['parent_pin']).decode(),
            '--bootstrap-pin',core.encoded(files['program/bootstrap.py']).decode(),
            '--request',request['production']['path'],'--request-pin',core.encoded(request['production']['pin']).decode(),
            '--origin',str(production['origin']),'--deadline',str(production['deadline']),
            '--read-cap',str(production['limits']['read_bytes']),'--write-cap',str(production['limits']['write_bytes'])]


def proof(host, descriptor_value, roots, cap=262144):
    descriptor(descriptor_value)
    u.need(u.path(roots['operator']) in u.path(descriptor_value['path']).parents, 'qualified operator proof namespace')
    return u.parse(host.read(descriptor_value['path'], cap, descriptor_value['pin'], readonly=True))


def configure(r, request, production, env, host):
    origin = r['origin']
    u.need(request['origin'] == origin and request['deadline'] == r['parent_deadline']
           and origin <= host.entry_start <= host.tick() < min(host.entry_start+120,r['parent_deadline']),
           'local startup within original operation interval, never origin plus120')
    u.need(request['central_entry_limits'] == r['parent_limits'], 'original qualified request binds exact entry caps')
    source = sum(p['bytes']+1 for p in env['freeze_files'].values())
    qualification = 4*(2097152+1)+2*(16777216+1)+source
    gate = env['gate']; campaigns = gate.CAPTURE_CAP+gate.PREFERENCE_READ_CAP+gate.VALIDATOR['bytes']+1
    maxima = production['limits']['complete_metadata_bytes']+production['limits']['journal_bytes']
    maxima += request['observation_metadata_bytes'] if r['operation'] == 'collect' else request['metadata_bytes']
    # Three generic checks, two campaign gates, two full source recaptures,
    # all complete public metadata and bounded requests/proofs/evidence.
    minimum = host.reads+3*qualification+2*campaigns+2*source+4*maxima+64*1048576
    limits = r['limits']
    u.need(limits['read_bytes'] >= minimum and limits['write_bytes'] >= 4*1048576,
           'prospective complete central source/qualification/readback/publication allowance')
    u.need(limits['host_memory_bytes'] >= 32*1048576+4*maxima+source,
           'selected complete retained metadata resource lower bound, physical qualification still required')
    host.origin = origin; host.deadline = r['readback_deadline']
    host.read_cap = limits['read_bytes']; host.write_cap = limits['write_bytes']
    env['parent_context']['origin'] = origin; env['parent_context']['deadline'] = host.deadline


def qualify_review(r, env, host):
    d = proof(host,r['qualification'],r['roots'],1048576)
    required = {'full423_29_and24panels','original_clocks','complete_resources','actual_caller_custody',
                'physical_roots_and_source','interpreter_environment','protected_original_grading'}
    u.need(d.get('schema') == 'neural058_actual_central_qualification_v1'
           and d.get('realm') == 'actual_external_evidence' and d.get('independent_operator') is True
           and d.get('qualified') is True and d.get('task_id') == 'NEURAL-058'
           and d.get('central_source') == env['source'] and d.get('parent_source') == env['parent_pin']
           and d.get('selection') == selection_pin(r) and d.get('request') == r['request']
           and d.get('production') == r['production'] and d.get('origin') == r['origin'],
           'exact independent actual configuration and source evidence')
    u.need(type(d.get('findings')) is dict and set(d['findings']) == required
           and all(v is True for v in d['findings'].values()), 'all independent central findings')
    now = host.tick()
    u.need(r['origin'] <= u.finite(d['observed']) <= now < u.finite(d['valid_until']) <= r['readback_deadline'],
           'fresh central evidence in unchanged operation clock')
    evidence = d.get('evidence'); u.need(type(evidence) is list and 1 <= len(evidence) <= 32, 'bounded actual evidence list')
    for item in evidence:
        descriptor(item); u.need(u.path(r['roots']['operator']) in u.path(item['path']).parents, 'operator-owned actual evidence')
        host.read(item['path'],1048576,item['pin'],readonly=True,retain=False)
    return r['qualification']['pin']


def admit_requests(r, request, production, env, host):
    core = env['parent']['core']; ppin = core.pin(core.encoded(production))
    u.need(production.get('schema') == 'neural058_complete_selection_v1' and production.get('task') == 'NEURAL-058'
           and production.get('selected') is True and production.get('source') == env['parent_pin']
           and production['roots'] == r['roots'] and production['source_manifest_path'] == str(env['parent_manifest_path'])
           and production.get('conditional_history') is False and production.get('grading',{}).get('selected') is False,
           'exact original complete strict production selection')
    env['parent']['contracts'].matched_panel_limits(production['panel_limits'])
    u.need(request.get('task') == 'NEURAL-058' and request.get('selected') is True
           and request.get('source') == env['parent_pin'], 'exact selected original operation')
    q = proof(host,request['qualification'],r['roots'])
    binding = core.pin(core.encoded({k:v for k,v in request.items() if k != 'qualification'}))
    u.need(q.get('source') == env['parent_pin'] and q.get('selection') == binding
           and q.get('independent_operator') is True, 'parent independent proof covers full actual request')
    now = host.tick()
    u.need(request['origin'] <= u.finite(q['observed']) <= now < u.finite(q['valid_until']) <= request['deadline'],
           'original operation proof clocks')
    selected = {'review':r,'request_document':request,'production':r['production'],'production_binding':ppin}
    if r['operation'] == 'collect':
        u.need(request.get('schema') == 'neural058_outer_selection_v1' and q.get('schema') == 'neural058_outer_qualification_v1'
               and q.get('admitted') is True and request['production'] == r['production']
               and request['origin'] == production['origin'] and request['normal_end'] == production['deadline']
               and production['origin'] < request['normal_end'] < request['cleanup_end'] < request['deadline']
               and request['observation_root'] == production['roots']['observation']
               and request['python'] == r['host_python'] and request['environment'] == r['environment']
               and request['cwd'] == r['cwd'] and request['literal_collect_argv'] == expected_collect(request,production,env),
               'unchanged original observer and actual collect command')
        qualifications = env['parent']['authority'].Qualifications(production,env['parent_pin'],host)
        for kind in ('environment_and_physical_resources','source_and_input_custody','full_support_and_projection',
                     'units_sign_and_native_semantics','method_exposure_and_workflow','reference_numerical_parity',
                     'provider_protocol_account_and_costs','immutable_mount_and_namespace_isolation'):
            u.need(qualifications.require(kind) is True, 'actual original production qualification')
        return selected
    u.need(request.get('schema') == 'neural058_late_grading_selection_v1'
           and q.get('schema') == 'neural058_late_grading_qualification_v1'
           and request['private_root'] == r['roots']['private'], 'original late protected grading')
    for name in ('actual_program_semantics_and_exposure','original_units_sign_support','reference_parity_and_source_lineage',
                 'whole_operation_resources_and_custody','protected_target_membership'):
        u.need(q.get(name) is True, 'actual complete late qualification: '+name)
    collection = u.parse(host.read(r['collection']['path'],131072,r['collection']['pin'],readonly=True))
    u.need(collection.get('schema') == 'neural058_central_result_v1' and collection.get('status') == 'complete'
           and collection.get('operation') == 'collect' and collection.get('task_id') == 'NEURAL-058'
           and collection.get('central_source') == env['source'] and collection.get('parent_source') == env['parent_pin']
           and collection.get('production') == r['production'] and collection.get('private_grading_performed') is False
           and collection['joined']['observation'] == request['observation'], 'same closed central collection, no imported scores')
    central_closure = proof(host,r['collection_root_closure'],r['roots'])
    u.need(central_closure.get('schema') == 'neural058_root_observed_central_v1'
           and central_closure.get('task_id') == 'NEURAL-058' and central_closure.get('central_source') == env['source']
           and central_closure.get('collection') == r['collection'] and central_closure.get('natural_exit') is True
           and type(central_closure.get('exit_code')) is int and central_closure['exit_code'] == 0
           and central_closure.get('stdout_eof') is True and central_closure.get('stderr_eof') is True
           and collection['origin'] <= u.finite(central_closure['observed_end']) <= request['origin'],
           'actual root-observed central collection closure; provisional artifact is not completion')
    descriptor(request['observation']); descriptor(request['root_outer_closure'])
    u.need(request['observation']['path'] == str(Path(r['roots']['observation'])/'OBSERVATION.json'), 'original public observation path')
    closure = proof(host,request['root_outer_closure'],r['roots'])
    u.need(closure.get('schema') == 'neural058_root_observed_outer_v1' and closure.get('source') == env['parent_pin']
           and closure.get('natural_exit') is True and type(closure.get('exit_code')) is int and closure['exit_code'] == 0
           and closure.get('stdout_eof') is True and closure.get('stderr_eof') is True
           and closure.get('observation') == request['observation']['pin']
           and production['origin'] <= u.finite(closure['observed_end']) <= request['origin'],
           'actual root terminal facts; new grade does not reset old clocks')
    obs = u.parse(host.read(request['observation']['path'],request['metadata_bytes'],request['observation']['pin'],readonly=True))
    u.need(obs.get('schema') == 'neural058_external_observation_v1' and obs.get('source') == env['parent_pin']
           and obs.get('production') == r['production'] and obs.get('protected_targets_read') is False,
           'same authentic public-only observation')
    doc = env['components']['readback'].complete(host,production,ppin,env,obs)
    u.need(q.get('production') == ppin and q.get('observation') == request['observation']['pin']
           and q.get('method_graph') == core.pin(core.encoded({'methods':doc['methods'],'transcripts':doc['author_transcripts']})),
           'all168 actual source/method/transcript identities')
    u.need(set(request['target_joins']) == set(doc['roster']['evaluation']), 'all29 private descriptors; bodies remain unopened')
    u.need(all(u.disjoint(request['output_root'],p) for p in r['roots'].values()), 'separate selected grade output')
    selected['complete_document'] = doc
    return selected


def recheck(env, host):
    for name,p in sorted(env['freeze_files'].items()): host.read(env['repo']/name,2097152,p,retain=False)
    return {'members':len(env['freeze_files']),'exact':True}


def establish_limit(r,host):
    import resource
    host.tick()
    host.limit_establishment = {'attempted':True,'syscall_returned':False,'clock_closed':False,'state_unknown':True}
    resource.setrlimit(resource.RLIMIT_AS,(r['limits']['host_memory_bytes'],r['limits']['host_memory_bytes']))
    host.limit_establishment.update(syscall_returned=True,state_unknown=False)
    host.tick(); host.limit_establishment['clock_closed'] = True


def execute(cli, env, host):
    routing = env['components']['routing']; repo = env['repo']
    registry = repo/routing.REGISTRY; raw = host.read(registry,131072); doc = u.parse(raw)
    routing.qualify(doc,cli,env,host)
    review_path = u.path(cli['review'])
    u.need(review_path.parent == env['here']/'operator-selections' and review_path.suffix == '.json',
           'source-owned review namespace before any operator/candidate operand')
    review_raw = host.read(review_path,32768,readonly=True); r = review_document(review_raw,cli,env)
    host.protected = tuple(u.path(r['roots'][k]) for k in ('private','original','secrets'))
    u.need(r['registry'] == u.pin(raw), 'same qualified registry')
    routing.qualify(doc,cli,env,host); first = routing.campaign(r,doc,cli,env,host)
    request = u.parse(host.read(r['request']['path'],4<<20,r['request']['pin'],readonly=True))
    production = u.parse(host.read(r['production']['path'],4<<20,r['production']['pin'],readonly=True))
    configure(r,request,production,env,host); qualified = qualify_review(r,env,host)
    selected = admit_requests(r,request,production,env,host)
    operand = r['request'] if r['operation'] == 'collect' else r['collection']
    u.need(cli['program'] == operand['path'], 'exact selected authority or completed collection operand')
    output = u.path(cli['output']); forbidden = list(r['roots'].values())
    if r['operation'] == 'grade': forbidden += [request['output_root'],str(u.path(r['collection']['path']).parent)]
    u.need(all(u.disjoint(output,p) for p in forbidden), 'central output outside all original/protected namespaces')
    command = routing.command(cli,doc,env)
    again = host.read(registry,131072,r['registry']); routing.qualify(u.parse(again),cli,env,host)
    second = routing.campaign(r,doc,cli,env,host); campaign = env['gate'].finish(first,second,command,repo)
    host.read(review_path,32768,u.pin(review_raw),readonly=True)
    host.read(r['request']['path'],4<<20,r['request']['pin'],readonly=True)
    host.read(r['production']['path'],4<<20,r['production']['pin'],readonly=True)
    qualify_review(r,env,host); selected = admit_requests(r,request,production,env,host); sources = recheck(env,host)
    nested = original_command(r,request,env); bundle = None; receipts = {}; phase = 'before_output_setup'; attempted = False
    try:
        phase = 'limit_establishment_entered'; establish_limit(r,host); phase = 'limit_established'
        free = sum(r['limits'][k] for k in ('parent_retained_storage_bytes','write_bytes','free_floor_bytes'))+r['other_reserve_bytes']
        host.prepare(output,free); phase = 'output_created'
        receipts['intent'] = host.save('INTENT.json',{'schema':'neural058_central_intent_v1','task_id':'NEURAL-058',
            'operation':r['operation'],'source':env['source'],'parent_source':env['parent_pin'],'review':u.pin(review_raw),
            'request':r['request'],'production':r['production'],'qualification':qualified,'origin':r['origin'],
            'parent_deadline':r['parent_deadline'],'observation_deadline':r['observation_deadline'],
            'readback_deadline':r['readback_deadline'],'central_argv':command,'parent_argv':nested,
            'cwd':r['cwd'],'environment':r['environment'],'no_mutating_caller_signals':True,'limits':r['limits']})
        receipts['campaign'] = host.save('CAMPAIGN.json',campaign)
        # Reserve original streams plus a bounded sentinel/drain block per pipe.
        caller = env['parent']['caller_observer']; host.reserve(2*(caller.CAP+caller.CHUNK))
        phase = 'caller_entered'; attempted = True
        bundle = caller.run(nested,r['parent_deadline'],r['observation_deadline'],r['environment'],r['cwd'])
        phase = 'caller_returned'; host.tick()
        for name,key in (('caller.stdout','stdout'),('caller.stderr','stderr'),('CALLER.json','record')):
            receipts[name] = host.save(name,bundle[key],65536)
        joined = env['components']['readback'].result(bundle,nested,selected,production,env,host)
        phase = 'readback_admitted'; sources = recheck(env,host)
        result = {'schema':'neural058_central_result_v1','status':'complete','task_id':'NEURAL-058','operation':r['operation'],
            'central_source':env['source'],'parent_source':env['parent_pin'],'request':r['request'],'production':r['production'],
            'review':u.pin(review_raw),'origin':r['origin'],'source_closure':sources,'receipts':receipts,'joined':joined,
            'private_grading_performed':r['operation']=='grade','actual_parent_operation_observed':True,
            'scientific_qualification_inferred':False,'provisional_until_root_observes_central_natural_exit_and_EOF':True,
            'automatic_retry':False,'costs_before_publication':host.record()}
        p = host.save('RESULT.json',result); host.tick()
        return {'status':'complete','path':str(host.root/'RESULT.json'),'pin':p,'terminal_publication_logical_bytes':p['bytes']}
    except BaseException as error:
        if hasattr(error,'bundle'): bundle = error.bundle
        later_errors = []
        failure = {'schema':'neural058_central_failure_v1','phase':phase,'error_type':type(error).__name__,
            'caller_attempted':attempted,'caller':None if bundle is None else bundle['record'],
            'unknown_surviving_child_state':attempted,'forced_termination_supported':False,
            'private_grading_may_have_started':attempted and r['operation']=='grade','receipts':receipts,
            'costs':host.record(),'automatic_retry':False,'later_errors':[],
            'original_streams':None if bundle is None else {},'diagnostic_encoding_bytes':0,
            'retained_bytes_are_not_natural_closure':True}
        def later(where, problem):
            later_errors.append(problem)
            failure['later_errors'].append({'where':where,'error_type':type(problem).__name__})
        if bundle is not None:
            # Independently preserve both already captured original streams.
            # Distinct names never overwrite successful-path partial artifacts.
            # Pins/extents survive even if budget, clock or publication fails.
            for stream in ('stdout','stderr'):
                row={'available':False,'pin':None,'persistence':'not_attempted','persistent_pin':None}
                failure['original_streams'][stream]=row
                try:
                    body=bundle[stream]
                    u.need(type(body)is bytes and len(body)<=65536,'bounded original caller stream')
                    row.update(available=True,pin=u.pin(body))
                    if host.prepared:
                        row['persistence']='entered_outcome_unknown'
                        written=host.save('failure.'+stream,body,65536)
                        row.update(persistence='durably_returned',persistent_pin=written)
                        receipts['failure.'+stream]=written
                except BaseException as problem:
                    row['persistence']='failed_or_unknown';later('failure.'+stream,problem)
            try:
                caller_raw=u.encode(bundle['record'])
                failure['diagnostic_encoding_bytes']+=len(caller_raw)
                failure['original_caller_record_pin']=u.pin(caller_raw)
                if host.prepared:receipts['FAILURE_CALLER.json']=host.save('FAILURE_CALLER.json',caller_raw,65536)
            except BaseException as problem:later('FAILURE_CALLER.json',problem)
        try:
            if host.prepared: host.save('FAILED.json',failure)
        except BaseException as problem:later('FAILED.json',problem)
        failure['costs_after_failure_publication'] = host.record()
        if later_errors:
            combined=BaseExceptionGroup('central primary and ordered independent persistence failures',[error,*later_errors])
            combined.failure_record=failure;raise combined from None
        error.failure_record = failure; raise
