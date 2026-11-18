"""Actual shared runtime and preferred-route gates, before operation operands.

The fixed NEURAL-010 registration is currently absent. This source does not create
it or substitute another task's passed receipt. Installation is a separate step.
"""
TASK='NEURAL-010'
CONDITION='full686_monitoring_analysis_two_modes_v2'
REGISTRY='benchmarks/neuroscience/neural-010/manifest.json'

def resolve(doc,condition):
    u.need(type(doc)is dict and doc.get('id')==TASK,'exact NEURAL-010 registry')
    if condition is not None:
        u.need(condition==CONDITION and doc.get('program_conditions',{}).get(condition)=='default',
               'named alias must preserve the complete default programme')
    return doc

def qualify(env,reader):
    """This fixed source/registry read precedes --program/--review/output access."""
    repo=env['repo'];doc,registry_pin=reader.json(repo/REGISTRY,131072)
    meta=doc.get('program_execution',{})
    u.need(type(meta)is dict and meta.get('verification',{}).get('status')=='passed',
           'full NEURAL-010 central runtime is not qualified')
    resolve(doc,None)
    frozen=meta.get('source_freeze');u.need(type(frozen)is dict,'complete registered source freeze')
    u.relative(frozen['path'])
    freeze,_=reader.json(repo/frozen['path'],2097152,u.only_pin(frozen))
    deployment=meta.get('deployment_source_closure')
    u.need(type(deployment)is dict and 1<=len(deployment)<=128,'separately qualified deployment source closure')
    for name,pin in deployment.items():u.relative(name);u.only_pin(pin)
    expected={**env['source_rows']}
    for name,pin in deployment.items():
        u.need(name not in expected,'deployment and captured task source namespaces must be distinct');expected[name]=pin
    u.need(freeze.get('schema')=='neural010_complete_central_qualification_v1'
           and freeze.get('task_id')==TASK and freeze.get('files')==expected,
           'qualification must bind all central/parent/shared/deployment sources exactly')
    entry=meta['entrypoint'];index=env['gate'].python_launch(entry['argv'])
    u.need(entry['argv'][index]==env['entry_relative'] and entry.get('working_directory')=='.'
           and entry.get('sha256')==env['source_rows'][env['entry_relative']]['sha256'],
           'exact actual central entry required')
    # Reserve the real shared helper's complete bounded reads, including its
    # four2MiB JSON reads, wrapper and first failing growth source capture.
    reader.reserve_read(4*(2097152+1)+2*(16777216+1)+sum(p['bytes']+1 for p in expected.values()))
    u.need(env['base'].verified_program_runtime(repo/REGISTRY,doc,repo) is True,
           'actual shared registered runtime evidence refused')
    captured={}
    for name,pin in deployment.items():
        captured[name]=reader.read(repo/name,16777216,u.only_pin(pin))
    policy_meta=meta.get('deployment_policy')
    u.need(type(policy_meta)is dict and policy_meta.get('path')in captured
           and u.only_pin(policy_meta)==deployment[policy_meta['path']], 'fixed qualified issuer policy in exact deployment closure')
    policy=u.parse(captured[policy_meta['path']])
    u.need(policy.get('issuer_source_closure')=={n:p for n,p in deployment.items()if n!=policy_meta['path']}, 'issuer binds every separately qualified source')
    custody=meta.get('protected_custody_receipt');u.descriptor(custody)
    u.need(custody['sha256']==meta['verification'].get('protected_custody_sha256'), 'issuer custody is bound by actual registered runtime verification')
    custody_doc,_=reader.json(custody['path'],2097152,u.only_pin(custody))
    u.need(custody_doc.get('schema')=='neural010_independent_central_custody_v1'
        and custody_doc.get('decision')=='accepted_registered_source_and_protected_namespaces'
        and custody_doc.get('source_freeze')==frozen and custody_doc.get('policy')==policy_meta,
        'independent protected custody observation bound to qualification and policy')
    reader.tick()
    return {'doc':doc,'registry_pin':registry_pin,'deployment':deployment,'qualified_source_rows':expected,
            'policy':policy,'policy_pin':{'path':str(repo/policy_meta['path']),**u.only_pin(policy_meta)}}

def campaign(env,reader,registered,review,actual_argv,actual_cwd):
    gate=env['gate'];repo=env['repo'];condition=review['condition']
    resolve(registered['doc'],condition)
    reader.reserve_read(gate.CAPTURE_CAP+gate.VALIDATOR['bytes']+1+gate.PREFERENCE_READ_CAP)
    request=review['campaign_request'];u.descriptor(request)
    first=gate.admit(repo,TASK,'run',condition,request['path'],request['sha256'],review['work_sha256'])
    u.need(first['request']==u.only_pin(request),'exact selected campaign request')
    route=gate.preferred_route(repo,TASK,'run',condition,review['work_sha256'],(repo/REGISTRY,registered['doc']))
    expected={'path':env['here'].relative_to(repo).as_posix(),
              'source':{'path':env['manifest_relative'],**env['source_pin']}}
    u.need(route.get('status')=='preferred_source_bound' and route.get('interface')==expected
           and route.get('registration')=={'path':REGISTRY,**registered['registry_pin']},
           'actual installed preferred full-study route required')
    first['preferred_program_route']=route;first['metadata_read_charge_bytes']+=route['metadata_read_charge_bytes']
    index=route['wrapper_index'];template=route['registered_argv']
    values={'{program}':review['actual_program_path'],'{output}':review['actual_output_path'],
            '{review}':review['actual_review_path'],'{other_reserve_bytes}':str(review['other_reserve_bytes'])}
    command=[env['python'],*template[1:index],route['wrapper_absolute'],*[values.get(x,x)for x in template[index+1:]]]
    u.need(command==actual_argv and actual_cwd==str(repo),'actual parsed central invocation binding')
    reader.tick();return first,command

def repeat_before_launch(env,reader,registered,review,first,actual_argv,actual_cwd):
    # Re-run real runtime and route/exposure checks before dispatch; a stale WORK
    # or registration cannot pass merely because the earlier metadata matched.
    again=qualify(env,reader)
    u.need(again==registered,'registered source/qualification changed before launch')
    second,command=campaign(env,reader,again,review,actual_argv,actual_cwd)
    return env['gate'].finish(first,second,command,actual_cwd)
