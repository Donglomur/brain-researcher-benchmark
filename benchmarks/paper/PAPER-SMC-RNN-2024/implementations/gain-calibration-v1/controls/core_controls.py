"""Generated metadata controls for frozen gain lineage and target-free wiring.

Original neural validation, full-shape HDF5 inspection, and saved native owner
proofs are explicit external doubles here. Real metadata guards, source closure,
byte snapshotting, barrier publication and score-row admission remain unchanged.
The separate tiny transform/numerical controls execute the actual scientific
helpers. No positive case authenticates original data or physical ownership.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import types


def isolated(module, replacements):
    namespace = dict(vars(module))
    for name, value in vars(module).items():
        if isinstance(value, types.FunctionType) and value.__globals__ is vars(module):
            function = types.FunctionType(value.__code__, namespace, value.__name__,
                                          value.__defaults__, value.__closure__)
            function.__kwdefaults__ = value.__kwdefaults__
            namespace[name] = function
    namespace.update(replacements)
    result = types.SimpleNamespace(**namespace)
    for name, value in namespace.items():
        if isinstance(value, types.FunctionType) and name not in replacements and hasattr(module, name):
            original = getattr(module, name)
            if isinstance(original, types.FunctionType):
                assert value.__code__ is original.__code__
    return result


def exercise_core(case, core, selector, transform, root, evaluator_path):
    import h5py
    import numpy as np
    root.mkdir()
    events = []
    source = core.source_identity()
    runtime_path = Path(core.__file__).parent / 'selector-runtime' / 'SOURCE.json'
    def desc(path):
        raw = path.read_bytes()
        return {'path': str(path), **core.pin(raw)}
    runtime = desc(runtime_path)
    def put(name, value):
        path = root / name
        raw = core.encoded(value)
        with path.open('xb') as stream:
            stream.write(raw)
        return {'path': str(path), **core.pin(raw)}
    baseline_dir = root / 'baseline'
    baseline_dir.mkdir()
    baseline = baseline_dir / 'prediction.h5'
    with h5py.File(baseline, 'w') as handle:
        handle.create_group('mc_maze_20').create_dataset('eval_rates_heldout', data=np.ones((1,1,1)))
    os.chmod(baseline, 0o400)
    baseline_descriptor = desc(baseline)
    panel = put('panel.json', {'generated_metadata_authority': True, 'kind': 'panel'})
    packet = put('packet.json', {'generated_metadata_authority': True, 'kind': 'packet'})
    reference_method = put('reference-method.json', {'generated_metadata_authority': True, 'kind': 'reference'})
    validation_source = {'path': str(root / 'original-validation-source-not-opened.py'), **core.VALIDATION_PIN}
    freeze_record = {
        'schema':'smc_restricted_validation_prediction_freeze_v1',
        'route':'smc_restricted_validation_v1','phase':'val','role':'reference',
        'source':dict(core.VALIDATION_PIN),
        'snapshot':{'filename':'prediction.h5', **{k:baseline_descriptor[k] for k in ('bytes','sha256')}},
        'panel':panel,'packet':packet,'method':reference_method,'shapes':copy.deepcopy(core.SHAPES),
        'target_accessed_by_freeze':False,'inference_execution_qualified':False,
        'pipeline_execution_qualified':False,'physical_owner_qualified':False,
    }
    freeze_path = baseline_dir / 'FREEZE.json'
    freeze_path.write_bytes(core.encoded(freeze_record))
    freeze = desc(freeze_path)
    def expect(actual, expected, event):
        case.assertEqual(actual, expected)
        events.append(event)
    def target_spy(*args, **kwargs):
        events.append('TARGET_BODY')
        raise AssertionError('No target access belongs to generated lineage controls')
    validation = types.SimpleNamespace(
        FREEZE_KEYS=set(freeze_record), ROUTE='smc_restricted_validation_v1',
        AUTHOR_COMMIT='c808c76ad940491b0a14d2671e3884140aa61258',
        validate_panel=lambda value: expect(value,panel,'panel_metadata_double'),
        validate_packet_metadata=lambda value: expect(value,packet,'packet_metadata_double'),
        validate_method=lambda value,pkt,role: (expect(value,reference_method,'method_metadata_double'),
                                               case.assertEqual(pkt,packet),case.assertEqual(role,'reference')),
        validate_freeze=lambda value: (expect(value,freeze,'original_freeze_double') or
                                      {'record':freeze_record,'snapshot':baseline_descriptor}),
        validate_prediction=lambda value,role: (case.assertEqual(role,'reference'),
            case.assertEqual(core.content_pin(value), {k:baseline_descriptor[k] for k in ('bytes','sha256')}),
            events.append('original_prediction_shape_double')),
        decode=core.decode, checked=core.checked, absolute=core.absolute,
        content_pin=core.content_pin, publish=core.publish, authenticate_target=target_spy,
    )
    def load_validation(value):
        expect(value,validation_source,'original_validation_module_double')
        return validation
    generated = isolated(core, {'load_validation':load_validation})
    method = generated.prepare_method(source,freeze,validation_source,runtime,root/'METHOD_FROZEN.json')
    admitted = generated.admit_method(method,source,freeze)
    case.assertEqual(admitted['record']['grid'],core.GRID)
    case.assertEqual(admitted['record']['lineage']['checkpoint_provenance']['fit_cohort'],'unknown')
    case.assertEqual(admitted['record']['baseline_prediction'],{k:baseline_descriptor[k] for k in ('bytes','sha256')})
    method_record = core.decode(core.checked(method))
    mutations = {
        'grid': lambda x: x['grid'].reverse(),
        'arithmetic': lambda x: x.update(arithmetic_policy='float64-only replacement'),
        'metric': lambda x: x.update(selection_metric='TEST co-bps'),
        'tie': lambda x: x.update(tie_rule='last maximum'),
        'prediction': lambda x: x['baseline_prediction'].update(sha256='0'*64),
        'lineage': lambda x: x['lineage'].update(phase='test'),
        'source': lambda x: x['source'].update(sha256='0'*64),
    }
    for name, mutate in mutations.items():
        changed=copy.deepcopy(method_record);mutate(changed)
        bad=put('bad-method-'+name+'.json',changed)
        with case.assertRaises(ValueError):generated.admit_method(bad,source,freeze)
    for name,value in [('phase','test'),('role','candidate'),('target_accessed_by_freeze',True)]:
        changed=copy.deepcopy(freeze_record);changed[name]=value
        bad=put('bad-freeze-'+name+'.json',changed)
        with case.assertRaises(ValueError):generated.baseline_metadata(bad,validation)
    case.assertNotIn('TARGET_BODY',events)

    target={'path':str(root/'target-never-created.h5'),'bytes':1,'sha256':core.TARGET_SHA256}
    evaluator={'path':str(evaluator_path),**core.EVALUATOR_PIN}
    request={'schema':'smc_gain_selection_request_v1','source':source,'method':method,
             'baseline_freeze':freeze,'target':target,'evaluator':evaluator,'output_root':str(root/'selection')}
    request_descriptor=put('request.json',request)
    def inspect_double(handle,shapes,gain):
        case.assertEqual(shapes,core.SHAPES);case.assertEqual(gain,[1,1])
        case.assertEqual(list(handle),['mc_maze_20'])
        events.append('complete_original_geometry_external_double')
    def load_kernel(name, selected):
        case.assertEqual(selected,source)
        if name=='gain_transform':return types.SimpleNamespace(_inspect=inspect_double)
        return generated.load_kernel_module(name,selected)
    preparing=isolated(core,{'load_validation':load_validation,'load_kernel_module':load_kernel})
    prepared=preparing.prepare_selection(request_descriptor['path'],request_descriptor['sha256'])
    barrier=core.decode(core.checked(prepared['barrier']))
    case.assertTrue(barrier['method_and_baseline_frozen']);case.assertIs(barrier['target_accessed'],False)
    case.assertEqual(core.content_pin(prepared['baseline_snapshot']['path']),
                     {k:baseline_descriptor[k] for k in ('bytes','sha256')})
    case.assertEqual(barrier['baseline_snapshot'],prepared['baseline_snapshot'])
    case.assertIn('complete_original_geometry_external_double',events)
    case.assertNotIn('TARGET_BODY',events)
    case.assertFalse(Path(target['path']).exists())
    # Real production geometry must reject this tiny baseline before target access.
    selector_probe=isolated(selector,{'load_core':lambda value:types.SimpleNamespace(
        prepare_selection=lambda path,sha:prepared),'load_original_evaluator':target_spy})
    with case.assertRaisesRegex(ValueError,'exact VALID heldout prediction geometry'):
        selector_probe.select(request_descriptor['path'],request_descriptor['sha256'])
    case.assertNotIn('TARGET_BODY',events)
    case.assertEqual(selector.PRODUCTION_SHAPE,(574,35,45))
    for label,key,value in [('claimed_target','target_accessed',True),
                            ('unfrozen','method_and_baseline_frozen',False),
                            ('wrong_request','request_sha256','0'*64)]:
        changed=copy.deepcopy(barrier);changed[key]=value
        folder=root/('barrier-'+label);folder.mkdir()
        path=folder/'METHOD_AND_BASELINE_FROZEN.json'
        path.write_bytes(core.encoded(changed))
        altered=dict(prepared,barrier=desc(path))
        probe=isolated(selector,{'load_core':lambda selected,ready=altered:types.SimpleNamespace(
            prepare_selection=lambda path,sha:ready),'load_original_evaluator':target_spy})
        with case.assertRaisesRegex(ValueError,'authenticated source-bound method'):
            probe.select(request_descriptor['path'],request_descriptor['sha256'])
    case.assertNotIn('TARGET_BODY',events)

    rows=[{'index':i,'gain':gain,'executed_gain':transform.executed_gain('<f4',gain),
           'co_bps':2.0 if i in (1,3) else 1.0} for i,gain in enumerate(core.GRID)]
    report={'schema':'smc_gain_selection_report_v1','route':core.ROUTE,'phase':'val','dataset':'mc_maze_20',
        'status':'selected_from_all_nine_canonical_co_bps_scores','request_sha256':request_descriptor['sha256'],
        'source':source,'method':method,'baseline_freeze':freeze,'baseline_snapshot':prepared['baseline_snapshot'],
        'barrier':prepared['barrier'],'lineage':admitted['lineage'],'target':target,'evaluator':evaluator,
        'ordered_scores':rows,'selected_index':1,'selected_gain':rows[1]['gain'],
        'selected_executed_gain':rows[1]['executed_gain'],'selected_co_bps':rows[1]['co_bps'],
        'metric':'co-bps','tie_rule':'first_exact_maximum','canonical_endpoint':'original_evaluator.bits_per_spike',
        'selection_is_development_calibration':True,'heldout_improvement':False,
        'inference_execution_qualified':False,'physical_owner_qualified':False,'scientific_improvement':False,'SOTA':False}
    case.assertEqual(generated.validate_selection_record(report,method,admitted),report)
    report_mutations={
        'phase':lambda x:x.update(phase='test'),
        'reference':lambda x:x['baseline_freeze'].update(sha256='0'*64),
        'method':lambda x:x['method'].update(sha256='0'*64),
        'baseline':lambda x:x['baseline_snapshot'].update(bytes=2),
        'order':lambda x:x['ordered_scores'].reverse(),
        'nonfinite':lambda x:x['ordered_scores'][0].update(co_bps=float('nan')),
        'rounded_gain':lambda x:x['ordered_scores'][1]['executed_gain'].update(value_hex='0x1p+0'),
        'mixed_dtype':lambda x:x['ordered_scores'][1].update(executed_gain=transform.executed_gain('<f8',core.GRID[1])),
        'later_tie':lambda x:x.update(selected_index=3,selected_gain=rows[3]['gain'],selected_executed_gain=rows[3]['executed_gain']),
        'bool_index':lambda x:x.update(selected_index=True),
        'claim':lambda x:x.update(scientific_improvement=True),
        'target':lambda x:x['target'].update(sha256='0'*64),
    }
    for name,mutate in report_mutations.items():
        changed=copy.deepcopy(report);mutate(changed)
        with case.assertRaises(ValueError,msg=name):generated.validate_selection_record(changed,method,admitted)
    selected=put('SELECTION.json',report)
    owner_result=put('OWNER_RESULT_EXTERNAL_DOUBLE.json',{'generated_saved_owner_double':True})
    def saved_owner(result,selection,**kwargs):
        expect(result,owner_result,'saved_owner_external_double')
        case.assertEqual(selection,selected);case.assertEqual(kwargs['method_descriptor'],method)
        case.assertEqual(kwargs['baseline_freeze_descriptor'],freeze)
        return report
    def execute(name,filename,raw):
        if name=='smc_gain_selected_host':
            return types.SimpleNamespace(admit_completed_selection=saved_owner)
        return core.execute_source(name,filename,raw)
    submitting=isolated(core,{'load_validation':load_validation,'execute_source':execute})
    actual=submitting.admit_selected_gain(selected,method,owner_result)
    case.assertEqual(actual['gain'],[8,9]);case.assertEqual(actual['baseline_descriptor'],baseline_descriptor)
    dispatch=[]
    output={'path':str(root/'not-numerically-transformed.h5'),'bytes':1,'sha256':'a'*64}
    def transform_boundary(src,dst,pin,gain,*,expected_shapes):
        dispatch.append('target_free_fixed_geometry_transform_double')
        case.assertEqual(src,baseline_descriptor['path']);case.assertEqual(gain,[8,9])
        case.assertEqual(pin,{k:baseline_descriptor[k] for k in ('bytes','sha256')})
        case.assertEqual(expected_shapes,core.SHAPES)
        return {'output':output,'target_accessed':False}
    production=isolated(transform,{'_authenticated_core':lambda:(submitting,source),'transform_h5':transform_boundary})
    result=production.production_transform(selected,method,owner_result,output['path'])
    case.assertIs(result['target_accessed'],False);case.assertEqual(len(dispatch),1)
    def refuse_owner(*args,**kwargs):raise ValueError('generated saved closure is incomplete')
    refusing=isolated(core,{'load_validation':load_validation,'execute_source':lambda name,path,raw:
        types.SimpleNamespace(admit_completed_selection=refuse_owner) if name=='smc_gain_selected_host'
        else core.execute_source(name,path,raw)})
    failed=isolated(transform,{'_authenticated_core':lambda:(refusing,source),'transform_h5':transform_boundary})
    with case.assertRaisesRegex(ValueError,'closure is incomplete'):
        failed.production_transform(selected,method,owner_result,output['path'])
    case.assertEqual(len(dispatch),1);case.assertNotIn('TARGET_BODY',events)
    case.assertFalse(Path(target['path']).exists())
    files=[p for p in root.rglob('*') if p.is_file()]
    total=sum(p.stat().st_size for p in files)
    case.assertLessEqual(total,131072)
    return {'generated_authority':True,'authentic_original_baseline_admission':False,
        'physical_owner_qualification':False,'kernel_runtime_source_authentication':True,
        'original_shape_validator': 'explicit external double; production geometry unchanged',
        'actual_selector_tiny_geometry_refusal_before_target':True,
        'actual_selector_barrier_tamper_refusals':3,
        'actual_copy_snapshot_and_barrier':True,'target_body_calls':0,
        'saved_owner_positive':'explicit external double',
        'production_transform':'real admission and fixed-shape wiring; final numerical boundary double',
        'generated_file_extent_bytes':total,'generated_write_charge_bytes':total+2*baseline.stat().st_size,
        'generated_file_count':len(files),'read_work_bound_bytes':3145728,
        'method_mutation_refusals':len(mutations),'freeze_mutation_refusals':3,
        'selection_mutation_refusals':len(report_mutations)}
