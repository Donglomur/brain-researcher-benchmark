"""Changed TEST-wrapper wiring; numerical copy is an explicit external boundary.

The genuine selected shared transform source is authenticated first. The new
scaled-pair controls separately exercise actual array proof on tiny fixtures.
This method never claims authentic TEST baseline or native owner admission.
"""
from __future__ import annotations
import copy
import inspect
import json
from pathlib import Path
import types


def isolated(module,replacements):
    namespace=dict(vars(module))
    for name,value in vars(module).items():
        if isinstance(value,types.FunctionType) and value.__globals__ is vars(module):
            function=types.FunctionType(value.__code__,namespace,value.__name__,value.__defaults__,value.__closure__)
            function.__kwdefaults__=value.__kwdefaults__;namespace[name]=function
    namespace.update(replacements)
    for name,value in namespace.items():
        if name not in replacements and isinstance(value,types.FunctionType) and hasattr(module,name):
            assert value.__code__ is getattr(module,name).__code__
    return types.SimpleNamespace(**namespace)


def exercise_transform_wiring(case,wrapper,gain_source,root):
    root.mkdir()
    actual_core,source=wrapper.authenticated_core()
    shared=wrapper.load_gain_transform(gain_source)
    case.assertEqual(shared.source_identity(),wrapper.GAIN_TRANSFORM_PIN)
    case.assertEqual(tuple(shared.RATE_KEYS),wrapper.RATE_KEYS)
    case.assertEqual(set(inspect.signature(wrapper.transform_test).parameters),{'test_method_descriptor','output_path'})
    method_path=root/'GENERATED_METHOD.json'
    raw=b'{"generated_metadata_authority":true}\n';method_path.write_bytes(raw)
    method={'path':str(method_path),**wrapper.pin(raw)}
    baseline={'path':str(root/'baseline-not-opened.h5'),'bytes':1,'sha256':'a'*64}
    output={'path':str(root/'candidate-not-created.h5'),'bytes':1,'sha256':'b'*64}
    admitted={'gain':[8,9],'baseline_descriptor':baseline,'gain_source':gain_source,
        'source':source,'method':method,'lineage':{'phase':'test','generated_authority':True}}
    events=[]
    def admit(selected):
        case.assertEqual(selected,method);events.append('admit-before-copy');return admitted
    def copy_boundary(src,dst,pin,gain,*,expected_shapes):
        case.assertEqual(events,['admit-before-copy','load-shared-kernel'])
        case.assertEqual(src,baseline['path']);case.assertEqual(dst,output['path'])
        case.assertEqual(pin,{k:baseline[k] for k in ('bytes','sha256')});case.assertEqual(gain,[8,9])
        expected={name:[2295 if name.startswith('train_') else 574,
                       10 if name.endswith('_forward') else 35,137 if 'heldin' in name else 45]
                  for name in wrapper.RATE_KEYS}
        case.assertEqual(expected_shapes,expected);events.append('target-free-copy-boundary')
        return {'output':output,'target_accessed':False,'inference_execution_qualified':False}
    shared_probe=isolated(shared,{'transform_h5':copy_boundary})
    def load(selected):
        case.assertEqual(selected,gain_source);events.append('load-shared-kernel');return shared_probe
    probe=isolated(wrapper,{'authenticated_core':lambda:(types.SimpleNamespace(admit_test_transform=admit),source),
                           'load_gain_transform':load})
    result=probe.transform_test(method,output['path'])
    case.assertEqual(events,['admit-before-copy','load-shared-kernel','target-free-copy-boundary'])
    case.assertEqual((result['schema'],result['phase'],result['role']),('smc_test_gain_transform_v1','test','candidate'))
    for flag in ('historical_author_identity_claim','target_accessed','physical_filesystem_exclusion_qualified',
                 'inference_execution_qualified','scientific_improvement'):case.assertIs(result[flag],False)
    case.assertFalse(Path(baseline['path']).exists());case.assertFalse(Path(output['path']).exists())
    negatives={
        'wrong_test_source':lambda x:x['source'].update(sha256='0'*64),
        'wrong_method':lambda x:x['method'].update(sha256='0'*64),
        'extra_author_claim':lambda x:x.update(author_calibration=True),
        'undeclared_gain':lambda x:x.update(gain=[3,4]),
    }
    for name,mutate in negatives.items():
        altered=copy.deepcopy(admitted);mutate(altered);calls=[]
        def guard_copy(*args,**kwargs):calls.append('copy');raise AssertionError('refusal must precede prediction copy')
        candidate_shared=isolated(shared,{'transform_h5':guard_copy})
        bad=isolated(wrapper,{'authenticated_core':lambda value=altered:(
            types.SimpleNamespace(admit_test_transform=lambda supplied:value),source),
            'load_gain_transform':lambda selected:candidate_shared})
        with case.assertRaises(ValueError,msg=name):bad.transform_test(method,output['path'])
        case.assertEqual(calls,[])
    def denied(selected):raise ValueError('genuine completed VALID selection required')
    called=[]
    bad=isolated(wrapper,{'authenticated_core':lambda:(types.SimpleNamespace(admit_test_transform=denied),source),
        'load_gain_transform':lambda selected:called.append('loaded')})
    with case.assertRaisesRegex(ValueError,'completed VALID selection required'):
        bad.transform_test(method,output['path'])
    case.assertEqual(called,[])
    return {'actual_wrapper_function_executed':True,'actual_wrapper_source_authentication':True,
        'actual_shared_transform_source_authentication':True,'production_TEST_geometry_unchanged':True,
        'candidate_role_and_no_author_claim':True,'admission_precedes_copy':True,
        'negative_cases':list(negatives)+['missing_genuine_VALID_completion'],
        'baseline_or_target_body_access':False,'test_baseline_and_VALID_owner_authority':'explicit generated external double',
        'numerical_copy':'explicit external boundary; separate new scaled-pair proof controls cover tiny arrays',
        'original_payload_qualification':False,'generated_write_bytes':len(raw),'read_work_bound_bytes':262144}
