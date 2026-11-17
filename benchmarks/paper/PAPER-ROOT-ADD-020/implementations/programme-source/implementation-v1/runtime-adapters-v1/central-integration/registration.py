"""Actual fixed registry and preferred gate before operator operand access."""
TASK='PAPER-ROOT-ADD-020'
REGISTRY='benchmarks/neuroscience/paper-root-add-020/manifest.json'
CONDITIONS={'full14_compiled_pair':'compiled','full14_investigate_pair':'investigate'}

def resolve(doc,condition):
    u.need(type(doc)is dict and doc.get('id')==TASK,'exact canonical PAPER-ROOT-ADD-020 registry required')
    if condition is not None:
        u.need(condition in CONDITIONS and doc.get('program_conditions',{}).get(condition)=='default',
               'named modes must preserve the same whole programme')
    return CONDITIONS.get(condition,'compiled')

def qualify(env,reader):
    repo=env['repo'];doc,rpin=reader.json(repo/REGISTRY,131072);resolve(doc,None)
    meta=doc.get('program_execution',{});entry=meta.get('entrypoint',{})
    # First reject stale legacy route. Historical passed receipts are not inherited.
    u.need(meta.get('preferred_source_interface')==env['interface']
           and entry.get('sha256')==env['source_rows'][env['entry_relative']]['sha256'],
           'current canonical registry does not select this full IT central source')
    index=env['gate'].python_launch(entry.get('argv'))
    u.need(entry['argv'][index]==env['entry_relative'] and entry.get('working_directory')=='.',
           'exact full-source central wrapper required')
    frozen=meta.get('source_freeze');u.need(type(frozen)is dict,'complete source freeze required')
    freeze,_=reader.json(repo/u.relative(frozen['path']),2_097_152,u.only_pin(frozen))
    deployment=meta.get('deployment_source_closure')
    u.need(type(deployment)is dict and 1<=len(deployment)<=128,'separately qualified deployment sources required')
    expected=dict(env['source_rows'])
    for name,p in deployment.items():
        u.relative(name);u.need(name not in expected,'deployment source namespace overlaps task source');expected[name]=u.only_pin(p)
    u.need(freeze.get('schema')=='paper020_complete_central_qualification_v1' and freeze.get('task_id')==TASK
           and freeze.get('files')==expected,'complete task/adapter/scientific/shared/deployment closure required')
    reader.reserve_read(4*(2_097_152+1)+2*(16_777_216+1)+sum(p['bytes']+1 for p in expected.values()))
    u.need(env['base'].verified_program_runtime(repo/REGISTRY,doc,repo)is True,'actual shared verification refused')
    # Live fixed WORK/preference join still precedes program/review/output operands.
    _,wpin=reader.json(repo/env['gate'].WORK,2_000_000)
    reader.reserve_read(env['gate'].PREFERENCE_READ_CAP)
    route=env['gate'].preferred_route(repo,TASK,'run',None,wpin['sha256'],(repo/REGISTRY,doc))
    u.need(route.get('status')=='preferred_source_bound' and route.get('interface')==env['interface']
           and route.get('registration')=={'path':REGISTRY,**rpin},'actual preferred full-source route required')
    reader.tick();return {'doc':doc,'registry_pin':rpin,'work_pin':wpin,'deployment':deployment,'source_rows':expected}

def campaign(env,reader,registered,review,argv,cwd,*,observing=False):
    u.need(type(review)is dict and set(review)=={'condition','campaign_request','work_sha256'},'exact campaign review metadata')
    mode=resolve(registered['doc'],review['condition']);gate=env['gate'];repo=env['repo']
    u.need(review['work_sha256']==registered['work_pin']['sha256'],'review WORK changed from fixed preflight')
    req=u.descriptor(review['campaign_request'])
    reader.reserve_read(gate.CAPTURE_CAP+gate.VALIDATOR['bytes']+1+gate.PREFERENCE_READ_CAP)
    first=gate.admit(repo,TASK,'run',review['condition'],req['path'],req['sha256'],review['work_sha256'])
    u.need(first['request']==u.only_pin(req),'exact campaign request extent')
    route=gate.preferred_route(repo,TASK,'run',review['condition'],review['work_sha256'],(repo/REGISTRY,registered['doc']))
    u.need(route.get('status')=='preferred_source_bound' and route.get('interface')==env['interface']
           and route.get('registration')=={'path':REGISTRY,**registered['registry_pin']},'actual selected route differs')
    first['preferred_program_route']=route;first['metadata_read_charge_bytes']+=route['metadata_read_charge_bytes']
    template=route['registered_argv'];index=route['wrapper_index'];values=env['operands']
    command=[env['python'],*template[1:index],route['wrapper_absolute'],*[values.get(x,x)for x in template[index+1:]]]
    u.need((observing or argv==command) and cwd==str(repo),'actual central invocation/registered argv differs')
    reader.tick();return first,command,mode

def repeat(env,reader,registered,review,first,argv,cwd):
    again=qualify(env,reader);u.need(again==registered,'fixed registry/preference changed before dispatch')
    second,command,_=campaign(env,reader,again,review,argv,cwd)
    return env['gate'].finish(first,second,command,cwd)
