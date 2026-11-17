"""Actual complete original five-phase request, authority and observation chain."""
from pathlib import Path

def metadata(env,reader,root,name,value,cap):
    raw=env['c'].encoded(value);u.need(len(raw)<=cap,'whole original request metadata bound')
    return reader.write_new(root/name,raw,cap)

def authority_for(env,reader,channel,programme,run,phase,role,request,budget):
    budget.check_clock()
    response=channel.request('phase_admission',{'phase':phase,'execution_role':role,
        'source':env['parent_pin'],'source_files':env['parent_files'],'run':programme['run'],
        'request':request,'protected_root':programme['protected_root']})
    desc=response['authority'];u.descriptor(desc)
    u.need(u.absolute(desc['path']).is_relative_to(u.absolute(programme['protected_root'])),'authority descriptor in selected protected root')
    selected=p.read_pin(reader,desc,1048576)
    u.need(p.same(selected['request'],request)and p.same(selected['run'],programme['run'])
           and selected['root']==programme['protected_root'],'actual independently selected request/run/root')
    actual=env['parent_authority'].admit(selected,env['parent_pin'],phase,budget,env['parent_files'],
        observer=role=='observer',root_observer=role=='root_observer')
    u.need(p.same(actual,run),'one unchanged complete run allocation')
    budget.check_clock();return desc,selected

def payload(env,reader,channel,programme,phase,closed,budget):
    if phase=='fixed-authors':return {'analyst_config':programme['analyst_config']}
    if phase=='references':return {'reference_seal_settings':programme['reference_seal_settings'],
        'fixed_authors_closure':closed['fixed-authors']['bundle'],'capture_roots':programme['capture_roots']}
    if phase=='release':
        prior=closed['references'];art=prior['admitted']['artifacts'];bundle=prior['bundle']
        request={'schema':'neural010-assessment-release-request-v1','source':env['parent_pin'],
                 'master':art['master'],'master_admission':art['admission'],'reference_spec':bundle['spec'],
                 'reference_observation':bundle['receipt'],'reference_external':bundle['external']}
        budget.check_clock()
        response=channel.request('assessment_release',{'release_request':request,
            'reference_external_authority':bundle['external_authority'],'source':env['parent_pin'],
            'run':programme['run'],'reference_central_closure':prior['central_observation']})
        desc=response['authority'];u.descriptor(desc)
        u.need(u.absolute(desc['path']).is_relative_to(u.absolute(programme['protected_root'])),'protected release authority only')
        # Only the authority descriptor is carried. The original release source
        # owns all assessment descriptor/body handling after its full barrier.
        budget.check_clock();return {'release_request':request,'release_authority':desc,'capture_roots':programme['capture_roots']}
    if phase=='analysts':return {'analyst_config':programme['analyst_config'],
        'fixed_authors_closure':closed['fixed-authors']['bundle'],'release_closure':closed['release']['bundle']}
    u.need(phase=='grade','exact whole phase order')
    return {'analysts_closure':closed['analysts']['bundle'],'release_closure':closed['release']['bundle']}

def root_argv(env,programme,phase,request,authority,origin):
    source=env['parent_pin'];entry=str(env['parent_root']/'entry.py')
    return [programme['python']['path'],'-I','-B',entry,'--root-observe','--phase',phase,
        '--source-bytes',str(source['bytes']),'--source-sha256',source['sha256'],
        '--request',request['path'],'--request-bytes',str(request['bytes']),'--request-sha256',request['sha256'],
        '--authority',authority['path'],'--authority-bytes',str(authority['bytes']),'--authority-sha256',authority['sha256'],
        '--origin',repr(float(origin))]

def run_phase(env,reader,channel,programme,run,phase,closed,output,budget,state):
    c=env['c'];obs=env['parent_observer'];roots=programme['phase_roots'][phase]
    envelopes=programme['observation_envelopes'][phase];metadata_root=c.new_directory(output/phase,budget)
    request={'schema':'neural010-phase-request-v1','phase':phase,'source':env['parent_pin'],
        'run':programme['run'],'output_root':roots['worker'],
        'payload':payload(env,reader,channel,programme,phase,closed,budget)}
    rp=metadata(env,reader,metadata_root,'WORKER_REQUEST.json',request,run['request_caps'][phase])
    wp,worker=authority_for(env,reader,channel,programme,run,phase,'worker',rp,budget)
    entry=next(x for x in env['parent_files']if x['path']==str(env['parent_root']/'entry.py'))
    spec={'phase':phase,'source':env['parent_pin'],'source_files':env['parent_files'],'public_inputs':[],
        'request':rp,'child_authority':wp,'python':programme['python'],'entry':entry,'cwd':str(env['repo']),
        'env':{'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1'},**envelopes['worker'],
        'output_manifest_path':str(Path(roots['worker'])/'OUTPUT_MANIFEST.json'),
        'output_manifest_cap':envelopes['output_manifest_cap'],'child_output_root':roots['worker'],
        'expected_artifacts':p.roster(phase,roots['worker'],run['artifact_caps'][phase]),
        'provider_config':worker['provider_config'],'credential_names':worker['credential_names'],
        'original_origin':float(budget.origin),'original_deadline':float(budget.end)}
    obs.spec_document(spec,budget)
    specpin=metadata(env,reader,metadata_root,'SPEC.json',spec,run['request_caps'][phase])
    inner={'schema':'neural010-observer-request-v1','phase':phase,'source':env['parent_pin'],'spec':spec,'output_root':roots['observer']}
    ip=metadata(env,reader,metadata_root,'OBSERVER_REQUEST.json',inner,run['request_caps'][phase])
    op,observer=authority_for(env,reader,channel,programme,run,phase,'observer',ip,budget)
    request_root={'schema':'neural010-root-observation-request-v1','phase':phase,'source':env['parent_pin'],
        'observer_request':ip,'observer_authority':op,'output_root':roots['root'],**envelopes['observer']}
    rrp=metadata(env,reader,metadata_root,'ROOT_REQUEST.json',request_root,run['request_caps'][phase])
    ap,root_authority=authority_for(env,reader,channel,programme,run,phase,'root_observer',rrp,budget)
    for selected in (observer,root_authority):
        for key in ('provider_config','credential_names'):u.need(p.same(selected[key],worker[key]),'same independently admitted credential metadata across all3roles')
    provider_raw=None
    if phase in ('fixed-authors','analysts'):
        u.need(p.same(programme['analyst_config']['provider'],worker['provider_config']),'actual original analyst/provider join')
        desc=worker['provider_config'];provider_raw=c.capture(desc,budget,[Path(desc['path']).parent])
        env['parent_driver'].analyst_config(programme['analyst_config'],worker,budget,env['parent_files'])
    obs.environment_binding(spec,c.encoded(request),c.encoded(worker),provider_raw)
    for desc in [env['parent_pin'],*env['parent_files'],programme['python'],rp,wp,ip,op,rrp,ap]:
        c.authenticate_stream(desc,budget,[Path(desc['path']).parent])
    argv=root_argv(env,programme,phase,rrp,ap,budget.origin)
    intent={'schema':'neural010-central-root-intent-v1','phase':phase,'source':env['parent_pin'],
        'request':rrp,'authority':ap,'argv':argv,'cwd':str(env['repo']),'original_origin':float(budget.origin),
        'original_deadline':float(budget.end),'credential_names':worker['credential_names'],
        'provider_config':worker['provider_config'],'scope':p.SCOPE}
    intentpin=metadata(env,reader,metadata_root,'INTENT.json',intent,2097152)
    state['intent']=intentpin;state['argv']=argv;budget.check_clock()
    # First and only central credential-value read follows every actual source,
    # request, independent authority and provider-name join. Never serialize env.
    child_env=obs.child_environment(spec);budget.charge('host_processes',1)
    state['launch_attempted']=True
    result=env['process'].ProcessObserver().run(argv,cwd=str(env['repo']),env=child_env,
        budget=env['bridge'](budget),**envelopes['root'])
    state['returned_observation']=result['observation']
    # Retain original return immediately, including original raw streams, before
    # publication/parsing can fail. It is process-local failure evidence only.
    state['returned_streams_hex']={k:result[k].hex()for k in ('stdout','stderr')}
    observed=c.publish_json(metadata_root/'ROOT_PROCESS_OBSERVATION.json',result['observation'],budget)
    stdout=c.publish(metadata_root/'stdout.bin',result['stdout'],budget)
    stderr=c.publish(metadata_root/'stderr.bin',result['stderr'],budget)
    obs.natural(result['observation'],argv,budget)
    original=env['readback'].phase(env,programme,phase,spec,specpin,rp,ip,op,rrp,ap,intentpin,
        argv,result,stdout,stderr,observed,budget)
    ack={'phase':phase,'central_intent':intentpin,'central_observation':observed,
        'stdout':stdout,'stderr':stderr,'root_result':original['root_result'],'bundle':original['bundle'],
        'scope':p.SCOPE,'original_origin':float(budget.origin),'original_deadline':float(budget.end)}
    channel.request('phase_observation',ack);budget.check_clock()
    return {**original,'central_observation':observed,'stdout':stdout,'stderr':stderr,'intent':intentpin,'budget':budget.snapshot()}

def execute(env,reader,channel,programme,run,review,output):
    c=env['c'];closed={};states={ph:{'entered':False,'launch_attempted':False,'completed':False}for ph in p.PHASES}
    env['phase_states']=states;env['reserved_partitions']={}
    for phase in p.PHASES:
        limits=programme['central_limits']['phase_limits'][phase]
        env['reserved_partitions'][phase]=dict(limits) # retained before any attempt
        budget=c.Budget(review['original_origin'],limits)
        states[phase]['entered']=True
        try:
            closed[phase]=run_phase(env,reader,channel,programme,run,phase,closed,output,budget,states[phase])
            states[phase]['completed']=True
        except BaseException as error:
            states[phase]['failure_type']=type(error).__name__
            states[phase]['original_component_evidence']=getattr(error,'evidence',None)
            states[phase]['budget']=budget.snapshot()
            raise
    u.need(channel.sequence==22 and len(channel.records)==22,'all22 complete ordered protected exchanges')
    # Each original complete closure was admitted before its successor launch.
    # The last phase check still uses scientific D, never final receipt time.
    budget.check_clock();return closed
