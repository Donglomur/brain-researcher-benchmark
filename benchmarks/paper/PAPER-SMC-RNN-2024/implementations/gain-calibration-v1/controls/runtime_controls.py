"""Generated saved-record controls, with explicit container-profile doubles.

No subprocess, socket, signal, Docker, timer or original payload is used.
Actual source resource/command construction and completed-result predicates run.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import types


def exercise_host(case, host, isolate):
    token='1'*32;cid='a'*64
    source={'path':'/gain-generated/kernel/SOURCE.json','bytes':604,'sha256':'b'*64}
    child_request={
        'schema':'smc_gain_selection_request_v1','source':source,
        'method':{'path':'/gain-generated/input/METHOD.json','bytes':1,'sha256':'c'*64},
        'baseline_freeze':{'path':'/gain-generated/input/FREEZE.json','bytes':1,'sha256':'d'*64},
        'target':{'path':'/gain-generated/input/target.h5','bytes':1,'sha256':host.TARGET_SHA256},
        'evaluator':{'path':'/gain-generated/source/evaluation.py',**host.EVALUATOR_PIN},
        'output_root':'/gain-generated/work/report/selection'}
    case.assertEqual(host.validate_child_request(child_request,source,Path('/gain-generated/work/report')),child_request)
    for key,value in [('schema','smc_historical_reference_grade_request_v1'),
                      ('output_root','/gain-generated/work/report/test')]:
        altered=copy.deepcopy(child_request);altered[key]=value
        with case.assertRaises(ValueError):host.validate_child_request(altered,source,Path('/gain-generated/work/report'))
    altered=copy.deepcopy(child_request);altered['target']['sha256']='0'*64
    with case.assertRaises(ValueError):host.validate_child_request(altered,source,Path('/gain-generated/work/report'))
    actor={'role':'grade','token':token,'operation_id':'smc-gain-selector-'+token,
        'image_id':host.IMAGE_ID,'architecture':'arm64','image_labels':{'generated':'true'},
        'container_base_labels':{'generated':'true'},'image_environment':['BLIS_NUM_THREADS=1'],
        'entrypoint':{'path':'/gain-generated/source/child.py','bytes':1,'sha256':'e'*64},
        'arguments':['--request','/gain-generated/input/request.json','--sha256','f'*64],
        'workdir':'/gain-generated/work/report','scratch_dir':'/tmp','uid':0,'gid':0,
        'readonly_mounts':[{'source':p,'destination':p} for p in (
            '/gain-generated/source/child.py','/gain-generated/input/request.json',
            '/gain-generated/input/target.h5')],
        'writable_mounts':[{'source':'/gain-generated/work/report','destination':'/gain-generated/work/report'}]}
    policy=types.SimpleNamespace(validate_label_maps=lambda image,base:case.assertEqual(image,base))
    builder=isolate(host,{'label_policy':lambda:policy})
    built=builder.build_create(actor,['/gain-generated/input/target.h5'])
    argv=built['argv']
    for flag,expected in [('--memory','2147483648'),('--memory-swap','2147483648'),
                          ('--cpus','1'),('--pids-limit','128'),('--network','none')]:
        case.assertEqual(argv[argv.index(flag)+1],expected)
    case.assertIn('cpu=600:605',argv);case.assertIn('--read-only',argv)
    case.assertIn('type=bind,src=/gain-generated/input/target.h5,dst=/gain-generated/input/target.h5,readonly',argv)
    case.assertEqual(built['memory'],2*1024**3);case.assertEqual(built['cpu_seconds'],600)
    case.assertEqual((host.WORK_SECONDS,host.CLEANUP_SECONDS,host.CPU_SOFT,host.CPU_HARD),(720,60,600,605))
    bad=copy.deepcopy(actor);bad['writable_mounts']=[{'source':'/gain-generated/input','destination':'/gain-generated/input'}]
    with case.assertRaises(ValueError):builder.build_create(bad,['/gain-generated/input/target.h5'])
    bad=copy.deepcopy(actor);bad['readonly_mounts'].append({'source':'/','destination':'/'})
    with case.assertRaises(ValueError):builder.build_create(bad,['/gain-generated/input/target.h5'])
    prefix=['/gain-generated/bin/docker','--host','unix:///gain-generated/docker.sock']
    request={'source':{'path':'/gain-generated/runtime/SOURCE.json','bytes':1,'sha256':'1'*64},
        'child_request':{'path':'/gain-generated/input/request.json','bytes':1,'sha256':'f'*64},
        'provenance':{'generated_external_metadata':True},
        'docker':{'path':prefix[0],'bytes':1,'sha256':'2'*64},'socket':prefix[2]}
    def call(label,args,stdout='',stderr='',code=0):
        return {'pid':123,'returncode':code,'label':label,'argv':prefix+args,
            'stdout':stdout,'stderr':stderr,'errors':[],
            'cleanup':{'cleanup_complete':True,'reaped':True,'group_absence_observed':True,
                       'error':None,'pid':123,'returncode':code},
            'capture':{'all_eof_observed':True,'storage_truncated':False,'read_ceiling_exhausted':False,
                       'closed_without_eof':False,'stream_close_errors':[]}}
    state=lambda status:{'Id':cid,'State':{'Status':status,'Running':False,'ExitCode':0,'OOMKilled':False,'Error':''}}
    calls=[call('create_gain_selector',argv,cid),
        call('container_inspect',['container','inspect','--format','{{json .}}',cid],json.dumps(state('created'))),
        call('start_gain_selector',['container','start',cid],cid),
        call('wait_gain_selector',['container','wait',cid],'0'),
        call('container_inspect',['container','inspect','--format','{{json .}}',cid],json.dumps(state('exited'))),
        call('remove_owned_grade',['container','rm',cid],cid),
        call('container_inspect',['container','inspect','--format','{{json .}}',cid],
             stderr='Error: No such container: '+cid,code=1)]
    closed={'intended':True,'container_absent':True,'container_id':cid}
    result={'schema':'smc_gain_selector_host_result_v1','source':request['source'],
        'child_request':request['child_request'],'image_id':host.IMAGE_ID,'provenance':request['provenance'],
        'error':None,'all_nine_gains_share_one_child_and_budget':True,'closed':closed,
        'bounds':{'memory_bytes':host.GRADE_MEMORY,'cpu_soft_seconds':host.CPU_SOFT,
                  'cpu_hard_seconds':host.CPU_HARD,'work_seconds':host.WORK_SECONDS,
                  'cleanup_seconds':host.CLEANUP_SECONDS,'threads':1},**host.completion(None,closed,calls)}
    def profile(value,selected_actor,selected_built):
        case.assertEqual(selected_actor,actor);case.assertEqual(selected_built,built)
        case.assertEqual(value['Id'],cid)
        return cid
    gate=isolate(host,{'verify_container':profile})
    report={'generated_report_validator_external_boundary':True}
    case.assertEqual(gate.validate_completed_result(result,request,child_request,report,calls,actor,built),report)
    mutations=[]
    def refusal(label,change_result=None,change_calls=None):
        r=copy.deepcopy(result);c=copy.deepcopy(calls)
        if change_result:change_result(r)
        if change_calls:change_calls(c)
        with case.assertRaises((ValueError,KeyError,TypeError),msg=label):
            gate.validate_completed_result(r,request,child_request,report,c,actor,built)
        mutations.append(label)
    refusal('container_absence_unknown',lambda r:r['closed'].update(container_absent=False))
    refusal('process_eof_unknown',change_calls=lambda c:c[0]['capture'].update(all_eof_observed=False))
    refusal('process_not_reaped',change_calls=lambda c:c[0]['cleanup'].update(reaped=False))
    refusal('errors_missing',change_calls=lambda c:c[0].pop('errors'))
    refusal('failed_child',change_calls=lambda c:c[3].update(stdout='1'))
    refusal('duplicate_create',change_calls=lambda c:c.insert(1,copy.deepcopy(c[0])))
    refusal('missing_created_profile',change_calls=lambda c:c.pop(1))
    refusal('missing_exited_profile',change_calls=lambda c:c.pop(4))
    refusal('missing_post_remove_absence',change_calls=lambda c:c.pop())
    refusal('boolean_cpu',lambda r:r['bounds'].update(cpu_soft_seconds=True))
    refusal('reset_per_gain_budget',lambda r:r['bounds'].update(work_seconds=720*9))
    refusal('only_success_booleans',change_calls=lambda c:c.clear())
    refusal('incorrect_saved_status',lambda r:r.update(status='closure_unknown'))
    failed=host.completion({'type':'TimeoutError'},closed,calls)
    case.assertFalse(failed['success']);case.assertEqual(failed['status'],'failed')
    unknown=host.completion(None,{'container_absent':False},calls)
    case.assertFalse(unknown['success']);case.assertEqual(unknown['status'],'closure_unknown')
    missing=copy.deepcopy(calls);missing[0]['capture']['all_eof_observed']=False
    case.assertEqual(host.completion(None,closed,missing)['status'],'closure_unknown')
    return {'whole_selection_bounds':result['bounds'],'real_command_builder_exercised':True,
        'real_completed_result_validator_exercised':True,'generated_saved_calls':7,
        'saved_record_refusals':mutations,'container_profile_boundary':'explicit generated double',
        'image_label_policy_boundary':'explicit generated double; retained policy not replayed',
        'real_OS_provider_or_saved_native_proofs':False,'physical_runtime_qualification':False,
        'generated_file_write_bytes':0,'generated_read_work_bound_bytes':262144}
