"""One-child bound ordering with generated metadata and OS/numerical doubles."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import types


def exercise_child(case, child, isolate, root, kernel_source):
    root.mkdir();events=[];limits=[]
    report_root=root/'report'/'selection';report_root.mkdir(parents=True)
    def put(path,value):
        raw=(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
        path.write_bytes(raw)
        return {'path':str(path),**child.pin(raw)}
    request={'schema':'smc_gain_selection_request_v1','source':kernel_source,
        'method':{'path':str(root/'METHOD-not-opened.json'),'bytes':1,'sha256':'a'*64},
        'baseline_freeze':{'path':str(root/'FREEZE-not-opened.json'),'bytes':1,'sha256':'b'*64},
        'target':{'path':str(root/'target-never-opened.h5'),'bytes':1,'sha256':child.TARGET_SHA256},
        'evaluator':{'path':str(root/'evaluator-never-opened.py'),**child.EVALUATOR_PIN},
        'output_root':str(report_root)}
    request_desc=put(root/'REQUEST.json',request)
    def setlimit(which,value):limits.append((which,value));events.append('limit:'+which)
    resource=types.SimpleNamespace(RLIMIT_CPU='CPU',RLIMIT_CORE='CORE',setrlimit=setlimit)
    os_copy=types.SimpleNamespace(**dict(vars(os)));os_copy.environ={}
    def load_selector(source):
        case.assertEqual(limits,[('CPU',(600,605)),('CORE',(0,0))])
        case.assertTrue(all(os_copy.environ[k]=='1' for k in child.THREAD_ENV))
        case.assertEqual(source,kernel_source);events.append('selector-module-boundary')
        def select(path,sha):
            case.assertEqual(path,request_desc['path']);case.assertEqual(sha,request_desc['sha256'])
            events.append('one-nine-gain-selection-boundary')
            return put(report_root/'SELECTION.json',{
                'schema':'smc_gain_selection_report_v1','request_sha256':sha,
                **{key:request[key] for key in ('source','method','baseline_freeze','target','evaluator')}})
        return types.SimpleNamespace(select=select)
    probe=isolate(child,{'resource':resource,'os':os_copy,'load_selector':load_selector})
    completed=probe.run(request_desc['path'],request_desc['sha256'])
    case.assertEqual(events,['limit:CPU','limit:CORE','selector-module-boundary','one-nine-gain-selection-boundary'])
    case.assertTrue(completed['all_nine_gains_share_one_child_and_budget'])
    case.assertIs(completed['physical_owner_qualified'],False)
    case.assertFalse(Path(request['target']['path']).exists())
    case.assertFalse(Path(request['evaluator']['path']).exists())
    case.assertEqual(child.os.environ,os.environ)
    # Real fixed kernel source admission remains separate from the invocation double.
    selected=child.load_selector(kernel_source)
    case.assertEqual(selected.PRODUCTION_SHAPE,(574,35,45))
    case.assertEqual(selected.GAIN_GRID,((1,1),(8,9),(9,8),(4,5),(5,4),(2,3),(3,2),(1,2),(2,1)))
    with case.assertRaisesRegex(ValueError,'requires the selected bounded owner child'):
        selected.main(['--request',request_desc['path'],'--sha256',request_desc['sha256']])
    for name,change in [('historical_schema',lambda x:x.update(schema='smc_historical_reference_grade_request_v1')),
        ('target',lambda x:x['target'].update(sha256='0'*64)),
        ('other_output',lambda x:x.update(output_root=str(root/'test')))]:
        altered=copy.deepcopy(request);change(altered)
        with case.assertRaises(ValueError,msg=name):child.validate_request(altered)
    files=[p for p in root.rglob('*') if p.is_file()]
    extent=sum(p.stat().st_size for p in files)
    case.assertLessEqual(extent,8192)
    return {'actual_child_run_exercised':True,'limit_calls':[[name,list(value)] for name,value in limits],
        'selector_invocations':1,'all_six_thread_settings':'1','source_loader_actual':True,
        'unbounded_selector_cli_refused':True,'OS_limits_boundary':'explicit resource/environ double',
        'scientific_selection_boundary':'explicit generated selector module double',
        'target_or_evaluator_body_access':False,'physical_runtime_qualification':False,
        'generated_write_charge_bytes':extent,'read_work_bound_bytes':262144}
