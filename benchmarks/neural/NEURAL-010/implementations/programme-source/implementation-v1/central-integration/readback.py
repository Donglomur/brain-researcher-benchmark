"""Original root and original complete artifact admission, with no new scorer."""
from pathlib import Path

def phase(env,programme,phase,spec,specpin,worker_request,observer_request,observer_authority,
          root_request,root_authority,intent,argv,result,stdout,stderr,observation,budget):
    c=env['c'];load=env['load'];root=Path(programme['phase_roots'][phase]['root'])
    env['parent_observer'].natural(result['observation'],argv,budget)
    for key,desc in [('stdout',stdout),('stderr',stderr)]:
        actual=result['observation']['streams'][key]
        u.need(type(actual['bytes'])is int and actual['bytes']==len(result[key])
               and actual['sha256']==c.pin(result[key])['sha256'],'complete actual original root stream')
        c.authenticate_stream(desc,budget,[Path(desc['path']).parent],empty=True)
    returned=c.parse(result['stdout']);c.exact(returned,('result','body'))
    rp=returned['result'];u.need(rp['path']==str(root/'ROOT_RESULT.json'),'literal actual root result')
    body=c.capture_json(rp,budget,[root]);u.need(c.typed_equal(body,returned['body']),'original raw stdout agrees with full captured result')
    c.exact(body,('schema','phase','intent','source','request','observer_receipt','external','external_authority',
                  'admission','original_origin','original_deadline','root_caller_own_future_exit_established','budget'))
    u.need(body['schema']=='neural010-root-observed-phase-v1'and body['phase']==phase
        and p.same(body['source'],env['parent_pin'])and p.same(body['request'],root_request)
        and body['root_caller_own_future_exit_established']is False,'original root source/request/provisional identity')
    u.need(p.same(body['original_origin'],float(budget.origin))and p.same(body['original_deadline'],float(budget.end)),'unchanged root original clock')
    for key,name in [('intent','ROOT_INTENT.json'),('external','EXTERNAL_OBSERVATION.json'),('external_authority','EXTERNAL_AUTHORITY.json')]:
        u.need(body[key]['path']==str(root/name),'literal protected root artifact '+key)
    u.need(body['observer_receipt']['path']==str(Path(programme['phase_roots'][phase]['observer'])/'OBSERVATION.json'),'literal original observer receipt')
    original_intent=c.capture_json(body['intent'],budget,[root])
    expected_argv=[programme['python']['path'],'-I','-B',spec['entry']['path'],'--observe','--phase',phase,
        '--source-bytes',str(env['parent_pin']['bytes']),'--source-sha256',env['parent_pin']['sha256'],
        '--request',observer_request['path'],'--request-bytes',str(observer_request['bytes']),'--request-sha256',observer_request['sha256'],
        '--authority',observer_authority['path'],'--authority-bytes',str(observer_authority['bytes']),'--authority-sha256',observer_authority['sha256'],
        '--origin',repr(float(budget.origin))]
    u.need(original_intent=={'schema':'neural010-original-root-phase-intent-v1','phase':phase,
        'source':env['parent_pin'],'request':root_request,'argv':expected_argv,'original_origin':float(budget.origin),
        'original_deadline':float(budget.end),'credential_names':spec['credential_names'],'provider_config':spec['provider_config']},'original root intent and exact immediate command')
    bundle={'spec':specpin,'receipt':body['observer_receipt'],'external':body['external'],'external_authority':body['external_authority']}
    admitted=env['parent_driver'].closure(bundle,phase,env['parent_pin'],budget,programme['protected_root'])
    u.need(p.same(admitted['proof'],body['admission'])and p.same(admitted['spec'],spec),'same actual original complete closure and spec')
    u.need(list(admitted['artifacts'])==[x['kind']for x in spec['expected_artifacts']],'full source-owned ordered artifact roles')
    for d in [env['parent_pin'],*env['parent_files'],programme['python'],worker_request,observer_request,observer_authority,root_request,root_authority]:
        c.authenticate_stream(d,budget,[Path(d['path']).parent])
    budget.check_clock();return {'root_result':rp,'bundle':bundle,'admitted':admitted,
        'observed_original_root_exit':True,'scientific_deadline_admission_complete':True}
