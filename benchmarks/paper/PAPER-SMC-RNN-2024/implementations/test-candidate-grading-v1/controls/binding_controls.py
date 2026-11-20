"""New TEST/VALID/checkpoint joins with explicit generated metadata authority.

Authentic production source closures are read normally. Only private historical
metadata bodies and genuine old native completion are external doubles. Their
fixed public descriptor pins and all nested new join predicates remain intact.
No payload is statted/read and no matching historical hash is fabricated on disk.
"""
from __future__ import annotations
import copy
from pathlib import Path
import types


def exercise_bindings(case,core,transform,isolate,root,gain_kernel,gain_runtime):
    root.mkdir();events=[];authority={};payload_reads=[]
    def describe(path):
        raw=path.read_bytes();return {'path':str(path),**core.pin(raw)}
    def put(name,value):
        p=root/name;raw=core.encoded(value);p.write_bytes(raw)
        return {'path':str(p),**core.pin(raw)}
    source=core.source_identity();profile=core.authenticate_source(source)
    base=Path(core.__file__).parent
    grader=describe(base/'grader'/'SOURCE.json');runtime=describe(base/'runtime'/'SOURCE.json')
    inputs={}
    for name in core.INPUT_KEYS:
        if name in core.PINS:inputs[name]={'path':str(root/('private-'+name)),**core.PINS[name]}
    inputs['gain_kernel']=gain_kernel;inputs['gain_runtime']=gain_runtime
    payload_paths={inputs[k]['path'] for k in ('test_reference_prediction','test_target','evaluator')}
    genuine_bad=put('not-an-original-panel.json',{'generated':True})
    with case.assertRaisesRegex(ValueError,'exact recorded test_panel'):
        core.fixed(genuine_bad,'test_panel')
    # The public fixed TEST profile is authentic; historical metadata content is
    # generated below and supplied only through the declared checked boundary.
    component={'files':{'validation_adapter.py':{'bytes':1,'sha256':'1'*64},
                        'helpers/generated.py':{'bytes':1,'sha256':'2'*64}}}
    author={'source_commit':profile['source_commit'],'arm':'noncausal','checkpoint_training_cohort':'unknown',
            'files':[{'path':name,**pin,'role':'checkpoint'} for name,pin in profile['checkpoint_files'].items()]
             +[{'path':name,**pin,'role':'configuration'} for name,pin in profile['adjacent_config'].items()]}
    packet=put('generated-valid-packet.json',{'files':{
        'mc_maze/val/train_input_20ms.h5':{'bytes':1,'sha256':'3'*64},
        'mc_maze/val/eval_input_20ms.h5':{'bytes':1,'sha256':'4'*64}}})
    packet_record=core.decode(core.checked(packet))
    material_files={'inputs/PACKET.json':{k:packet[k] for k in ('bytes','sha256')},
        **{'official_source/'+row['path']:{k:row[k] for k in ('bytes','sha256')} for row in author['files']},
        **{'inputs/'+name:{k:row[k] for k in ('bytes','sha256')} for name,row in packet_record['files'].items()}}
    materials={'schema':'smc_restricted_validation_materials_v1','route':'smc_restricted_validation_v1',
        'packet':{k:packet[k] for k in ('bytes','sha256')},'author_manifest':core.PINS['valid_author_manifest'],
        'files':material_files,'train_rate_scope':'canonical_metric_decoder_inputs_not_restricted_calibration',
        'checkpoint_training_cohort':'unknown','resource_adequacy':False}
    inputs['valid_materials']=put('generated-valid-materials.json',materials)
    bindings={'schema':'smc_restricted_validation_bindings_v1',
        'helpers':{'generated.py':component['files']['helpers/generated.py']},
        'packet':{k:packet[k] for k in ('bytes','sha256')},
        'materials':{k:inputs['valid_materials'][k] for k in ('bytes','sha256')}}
    inputs['valid_reference_bindings']=put('generated-valid-bindings.json',bindings)
    reference=put('generated-valid-reference-method.json',{'program':component['files']['validation_adapter.py'],
        'bindings':{k:inputs['valid_reference_bindings'][k] for k in ('bytes','sha256')}})
    valid_freeze={'path':str(root/'valid-freeze-not-opened.json'),'bytes':1,'sha256':'5'*64}
    inputs['valid_method']=put('generated-valid-gain-method.json',{'baseline_freeze':valid_freeze})
    ordered=[{'index':i,'gain':list(gain),'executed_gain':transform.executed_gain('<f4',list(gain)),
              'co_bps':1.0 if i==1 else 0.0} for i,gain in enumerate(transform.GAIN_GRID)]
    selection={'schema':'smc_gain_selection_report_v1','phase':'val','dataset':'mc_maze_20',
        'source':gain_kernel,'method':inputs['valid_method'],'lineage':{'reference_method':reference,'packet':packet},
        'ordered_scores':ordered,'selected_index':1,'selected_gain':[8,9],
        'selected_executed_gain':ordered[1]['executed_gain'],'selected_co_bps':1.0}
    inputs['valid_selection']=put('generated-valid-selection.json',selection)
    inputs['valid_selector_result']=put('generated-native-result-authority.json',{'external_native_authority_double':True})
    panel={'schema':'smc_nlb_panel_v1','phase':'test','dataset':'mc_maze_20',
           'source_commit':profile['source_commit'],'expected_shapes':profile['shapes'],
           **profile['geometry'],**profile['order']}
    protocol={'input_commitments':{'test_panel_sha256':core.PINS['test_panel']['sha256']},
              'exposure':{'target_sha256':core.PINS['test_target']['sha256']}}
    historical={'schema':'smc_nlb_prediction_freeze_v1','role':'author_calibration','arm':'noncausal',
        'seed':20261118,'particles':192,'repeats':32,'source_author_commit':profile['source_commit'],
        'submission_sha256':core.PINS['test_reference_prediction']['sha256'],
        'panel_manifest_sha256':core.PINS['test_panel']['sha256'],
        'protocol_sha256':core.PINS['test_protocol']['sha256'],
        'reference_panel_sha256':core.REFERENCE_PANEL_PIN['sha256'],'target_exposure':profile['target_exposure']}
    author_files=[{'path':name,**pin} for name,pin in {**profile['checkpoint_files'],**profile['adjacent_config']}.items()]
    while len(author_files)<38:
        author_files.append({'path':'generated/author-leaf-%02d.py'%len(author_files),'bytes':1,'sha256':'6'*64})
    manifest={'schema':'smc_source_manifest_v1','source_commit':profile['source_commit'],'files':author_files}
    post={'schema':'smc_completed_arm_source_check_v1','arm':'noncausal','author_source_commit':profile['source_commit'],
        'author_files_verified':38,'author_source_manifest_sha256':core.PINS['test_source_manifest']['sha256'],
        'input_panel_sha256':core.PINS['test_panel']['sha256'],
        'submission_sha256':core.PINS['test_reference_prediction']['sha256'],
        'submission_bytes':core.PINS['test_reference_prediction']['bytes'],
        'protocol_sha256':core.PINS['test_protocol']['sha256'],
        'native_report_sha256':'e010326e053e4be542540107f4ea70b8dc4051f3b17df749924e52f91a4da18c'}
    for name,value in [('valid_component_source',component),('valid_author_manifest',author),
        ('test_panel',panel),('test_protocol',protocol),('test_reference_freeze',historical),
        ('test_source_manifest',manifest),('test_source_postcheck',post)]:
        authority[inputs[name]['path']]=value
    def checked(row,cap=core.META_CAP):
        if row['path'] in authority:
            core.descriptor(row,cap);events.append('generated-historical-metadata-authority')
            return core.encoded(authority[row['path']])
        return core.checked(row,cap)
    def guarded_body(filename,cap=core.META_CAP):
        if str(filename) in payload_paths:
            payload_reads.append(str(filename));raise AssertionError('metadata admission must not access payloads')
        return core.body(filename,cap)
    def gate(result,selected,*,method_descriptor,baseline_freeze_descriptor):
        case.assertEqual(result,inputs['valid_selector_result']);case.assertEqual(selected,inputs['valid_selection'])
        case.assertEqual(method_descriptor,inputs['valid_method']);case.assertEqual(baseline_freeze_descriptor,valid_freeze)
        events.append('exact-completed-VALID-function-boundary')
        return copy.deepcopy(selection)
    def execute(name,filename,raw):
        if name=='smc_test_original_gain_host':
            case.assertEqual(core.pin(raw),{'bytes':53183,'sha256':'7ab6d64e5fb9d1db12c0ef6f5ac08a0821a5f38cb4e5309c278aa015d9ff8509'})
            events.append('authenticated-real-completed-gate-source')
            return types.SimpleNamespace(admit_completed_selection=gate)
        return core.execute_source(name,filename,raw)
    generated=isolate(core,{'checked':checked,'body':guarded_body,'execute_source':execute})
    request=put('METHOD_REQUEST.json',{'schema':'smc_test_gain_method_request_v1','source':source,
        'grader_source':grader,'runtime_source':runtime,'inputs':inputs})
    method=generated.freeze_method(request,root/'TEST_METHOD.json')
    admitted=generated.admit_test_method(method)
    transformed=generated.admit_test_transform(method)
    case.assertEqual(transformed['gain'],[8,9]);case.assertEqual(transformed['baseline_descriptor'],inputs['test_reference_prediction'])
    case.assertEqual(admitted['lineage']['test']['geometry']['n_train'],2295)
    case.assertEqual(admitted['lineage']['test']['geometry']['n_eval'],574)
    case.assertEqual(admitted['lineage']['test']['decoder_timebins'],35)
    case.assertEqual(admitted['lineage']['test']['order'],profile['order'])
    case.assertEqual(admitted['lineage']['checkpoint_training_run'],'unresolved')
    case.assertIs(admitted['lineage']['historical_failed_noncausal_supervision_repaired'],False)
    case.assertIn('exact-completed-VALID-function-boundary',events)
    case.assertEqual(payload_reads,[])
    metadata_refusals=[]
    def mutate_metadata(label,key,change):
        name=inputs[key]['path'];old=copy.deepcopy(authority[name]);change(authority[name])
        try:
            with case.assertRaises((ValueError,KeyError),msg=label):generated.admit_test_method(method)
        finally:authority[name]=old
        metadata_refusals.append(label)
    mutate_metadata('TEST_phase_cannot_be_VALID','test_panel',lambda x:x.update(phase='val'))
    mutate_metadata('TEST_decoder_cannot_use1721','test_panel',lambda x:x.update(n_train=1721))
    mutate_metadata('TEST_decoder_cannot_use45basebins','test_panel',lambda x:x.update(n_bins=45))
    mutate_metadata('TEST_tensor_trial_order','test_panel',lambda x:x.update(tensor_trial_indices_sha256='0'*64))
    mutate_metadata('checkpoint_drift','valid_author_manifest',lambda x:x['files'][0].update(sha256='0'*64))
    mutate_metadata('recorded_TEST_checkpoint_drift','test_source_manifest',lambda x:x['files'][0].update(sha256='0'*64))
    mutate_metadata('historical_prediction_drift','test_reference_freeze',lambda x:x.update(submission_sha256='0'*64))
    mutate_metadata('postcheck_wrong_author_count','test_source_postcheck',lambda x:x.update(author_files_verified=37))
    previous=selection['phase'];selection['phase']='test'
    with case.assertRaisesRegex(ValueError,'completed frozen VALID'):generated.admit_test_method(method)
    selection['phase']=previous
    method_record=core.decode(core.checked(method))
    method_refusals=[]
    for label,mutate in [('winner',lambda x:x['selected_row'].update(gain=[1,1])),
        ('lineage',lambda x:x['lineage'].update(phase='val')),
        ('author_recipe',lambda x:x['candidate_recipe'].update(role='author_calibration')),
        ('source',lambda x:x['source'].update(sha256='0'*64))]:
        value=copy.deepcopy(method_record);mutate(value);bad=put('bad-method-'+label+'.json',value)
        with case.assertRaises(ValueError,msg=label):generated.admit_test_method(bad)
        method_refusals.append(label)
    prediction={'path':str(root/'candidate-not-opened.h5'),'bytes':1,'sha256':'7'*64}
    candidate={'schema':'smc_nlb_prediction_freeze_v1','created_utc':'2026-11-20T00:00:00Z','dataset':'mc_maze_20',
        'arm':'noncausal','method_id':'smc-test-gain/'+method['sha256'],'role':'candidate','seed':0,
        'particles':None,'repeats':None,'source_author_commit':None,'submission_sha256':prediction['sha256'],
        'panel_manifest_sha256':core.PINS['test_panel']['sha256'],'protocol_sha256':core.PINS['test_protocol']['sha256'],
        'reference_panel_sha256':core.REFERENCE_PANEL_PIN['sha256'],'target_exposure':profile['target_exposure']}
    freeze=put('CANDIDATE_FREEZE.json',candidate)
    case.assertEqual(generated.admit_candidate_metadata(prediction,freeze,method,admitted)['prediction'],prediction)
    candidate_refusals=[]
    for label,mutate in [('claimed_author',lambda x:x.update(role='author_calibration')),
        ('claimed_commit',lambda x:x.update(source_author_commit=profile['source_commit'])),
        ('particles',lambda x:x.update(particles=192)),('boolean_seed',lambda x:x.update(seed=False)),
        ('wrong_method',lambda x:x.update(method_id='smc-test-gain/'+'0'*64)),
        ('wrong_prediction',lambda x:x.update(submission_sha256='0'*64))]:
        value=copy.deepcopy(candidate);mutate(value);bad=put('bad-candidate-'+label+'.json',value)
        with case.assertRaises(ValueError,msg=label):generated.admit_candidate_metadata(prediction,bad,method,admitted)
        candidate_refusals.append(label)
    case.assertEqual(payload_reads,[])
    case.assertTrue(all(not Path(p).exists() for p in payload_paths))
    extent=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    case.assertLessEqual(extent,262144)
    return {'genuine_original_fixed_pin_refusal':True,'actual_new_source_and_successor_authentication':True,
        'actual_retained_gain_gate_source_authentication':True,'completed_VALID_function_invoked_with_exact_identities':True,
        'historical_metadata_authority':'explicit generated checked-body boundary, not original metadata admission',
        'completed_native_VALID_authority':'explicit external completion boundary after genuine source authentication',
        'actual_new_nested_TEST_VALID_checkpoint_order_joins':True,'payload_reads':payload_reads,
        'metadata_refusals':metadata_refusals,'method_refusals':method_refusals,
        'candidate_role_refusals':candidate_refusals,'TEST_decoder_trials':2295,'TEST_decoder_bins':35,
        'actual_checkpoint_weights_or_original_TEST_delivery_qualified':False,'physical_ownership_qualified':False,
        'generated_file_write_bytes':extent,'read_work_bound_bytes':12582912}
