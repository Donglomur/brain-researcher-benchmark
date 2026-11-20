"""Changed paired TEST custody/scoring controls with explicitly separated seams.

Real original scorer bodies run under the actual local package versions and are
refused by the selected-production report gate. A distinct structural pipeline
uses generated selected-runtime reports; no package constant/global is patched.
"""
from __future__ import annotations
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import tempfile
import types


def exercise_pair(case,grade,core,metric_helper,isolate,root,evaluator_path):
    import h5py
    import numpy as np
    root.mkdir();inputs=root/'inputs';inputs.mkdir();events=[];deleted_bytes=0
    def desc(path):
        raw=path.read_bytes();return {'path':str(path),**grade.pin(raw)}
    def put(path,value):
        raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();path.write_bytes(raw)
        return {'path':str(path),**grade.pin(raw)}
    source=desc(Path(grade.__file__).parent/'SOURCE.json')
    case.assertEqual(importlib.metadata.version('h5py'),'3.11.0')
    with case.assertRaisesRegex(ValueError,'Selected scoring environment differs'):
        grade.versions()
    scorer=grade.load_scorer()
    original_panel=scorer.read_json(scorer.REFERENCE_PANEL)
    expected_shapes=scorer.validate_panel(original_panel)
    case.assertEqual(original_panel['n_train'],2295);case.assertEqual(original_panel['n_eval'],574)
    case.assertTrue(all(shape[1]==(10 if name.endswith('_forward') else 35) for name,shape in expected_shapes.items()))
    panel=inputs/'PANEL.json';panel.write_bytes(scorer.REFERENCE_PANEL.read_bytes())
    protocol=inputs/'PROTOCOL.json'
    target_dir=root/'protected-generated';target_dir.mkdir()
    target=target_dir/'target.txt';target.write_bytes(b'generated target authority only\n')
    protocol_descriptor=put(protocol,{'input_commitments':{'test_panel_sha256':desc(panel)['sha256']},
        'exposure':{'target_sha256':scorer.TARGET_SHA256},'generated_authority':True})
    method=put(inputs/'METHOD.json',{'schema':'smc_test_gain_method_v1',
        'candidate_recipe':grade.CANDIDATE_RECIPE,'selected_row':{'gain':[8,9]},
        'lineage':{'phase':'test','decoder_cohort':['train','val'],'decoder_timebins':35,
                   'checkpoint_training_run':'unresolved','generated_authority':True}})
    method_record=grade.checked(method)
    arrays={};prediction={}
    for role in ('reference','candidate'):
        filename=inputs/(role+'.h5')
        with h5py.File(filename,'w',track_order=True) as handle:
            group=handle.create_group(scorer.DATASET,track_order=True)
            for index,name in enumerate(scorer.RATE_KEYS):
                value=(np.arange(4,dtype=np.float32).reshape(2,2,1)+index+1)
                if role=='candidate':value=np.multiply(value,np.float32(8)/np.float32(9),dtype=np.float32)
                group.create_dataset(name,data=value,track_times=False)
        prediction[role]=desc(filename)
    raw_bytes={role:Path(row['path']).read_bytes() for role,row in prediction.items()}
    def fullshape_boundary(filename,manifest,*,require_author_arrays=False):
        case.assertEqual(scorer.validate_panel(manifest),expected_shapes)
        with h5py.File(filename,'r') as handle:
            case.assertEqual(set(handle[scorer.DATASET]),set(scorer.RATE_KEYS))
        events.append(('declared-original-geometry-boundary',Path(filename).name,require_author_arrays))
        return expected_shapes
    ordinary=isolate(scorer,{'validate_submission':fullshape_boundary})
    freezes={};freeze_records={}
    for role in ('reference','candidate'):
        path=inputs/(role+'-freeze.json')
        record=ordinary.freeze_predictions(prediction[role]['path'],panel,protocol,path,arm='noncausal',
            method_id='generated-reference' if role=='reference' else 'smc-test-gain/'+method['sha256'],
            role='author_calibration' if role=='reference' else 'candidate',seed=20261118 if role=='reference' else 0,
            particles=192 if role=='reference' else None,repeats=32 if role=='reference' else None)
        freezes[role]=desc(path);freeze_records[role]=record
    for role in ('reference','candidate'):
        case.assertEqual(ordinary.validate_freeze(prediction[role]['path'],panel,protocol,freezes[role]['path']),freeze_records[role])
    case.assertIs(freeze_records['candidate']['source_author_commit'],None)
    canonical=metric_helper.canonical_case();local_reports={};local_target_calls=[]
    scratch=root/'local-scorer-scratch';scratch.mkdir()
    class TrackedTemporary:
        def __init__(self,**kwargs):self.inner=tempfile.TemporaryDirectory(dir=scratch,**kwargs)
        def __enter__(self):self.folder=self.inner.__enter__();return self.folder
        def __exit__(self,*args):
            nonlocal deleted_bytes
            deleted_bytes+=sum(p.stat().st_size for p in Path(self.folder).rglob('*') if p.is_file())
            return self.inner.__exit__(*args)
    def generated_target_sha(filename):
        if Path(filename)==target:
            case.assertEqual(set(freeze_records),{'reference','candidate'})
            case.assertEqual(target.read_bytes(),b'generated target authority only\n')
            local_target_calls.append('explicit-generated-target-authority')
            return scorer.TARGET_SHA256
        return scorer.sha256(filename)
    def evaluator_boundary(filename):
        case.assertEqual(scorer.sha256(filename),scorer.SCORER_SHA256)
        def evaluate(target_path,snapshot):
            case.assertEqual(Path(target_path),target)
            raw=Path(snapshot).read_bytes()
            matches=[role for role,expected in raw_bytes.items() if raw==expected]
            case.assertEqual(len(matches),1)
            events.append(('original-score-numerical-boundary',matches[0]))
            return copy.deepcopy(canonical[matches[0]])
        return types.SimpleNamespace(evaluate=evaluate)
    local=isolate(scorer,{'validate_submission':fullshape_boundary,'sha256':generated_target_sha,
        'load_original_scorer':evaluator_boundary,'tempfile':types.SimpleNamespace(TemporaryDirectory=TrackedTemporary)})
    for role in ('reference','candidate'):
        local_reports[role]=local.score_predictions(prediction[role]['path'],panel,protocol,freezes[role]['path'],
            target,scorer.TARGET_SHA256,evaluator_path,root/('actual-local-'+role+'-score.json'))
        case.assertEqual(local_reports[role]['dependency_versions']['h5py'],'3.11.0')
    case.assertEqual(len(local_target_calls),2)
    panel_descriptor=desc(panel)
    request={'schema':'smc_test_gain_grade_request_v1','source':source,'test_method':method,
        'host_custody':put(inputs/'GENERATED_HOST_CUSTODY.json',{'generated_native_authority_boundary':True}),
        'predictions':prediction,'freezes':freezes,'panel':panel_descriptor,'protocol':protocol_descriptor,
        'target':{'path':str(target),'bytes':target.stat().st_size,'sha256':scorer.TARGET_SHA256},
        'evaluator':desc(evaluator_path),'output_root':str(root/'positive'/'report'/'test-pair'),
        'scratch_bytes':grade.SCRATCH_CAP}
    for role in ('reference','candidate'):
        with case.assertRaisesRegex(ValueError,'Unchanged canonical role, score and provenance joins'):
            grade.validate_score(local_reports[role],role,request,freeze_records[role])
    synthetic=put(inputs/'unmodified-original-authority-refusal.json',request)
    with case.assertRaisesRegex(ValueError,'Exact unchanged noncausal TEST reference'):
        grade.metadata(synthetic['path'],synthetic['sha256'])
    selected_reports={}
    for role in ('reference','candidate'):
        selected_reports[role]=copy.deepcopy(local_reports[role])
        selected_reports[role]['dependency_versions']=dict(grade.PACKAGES)
        case.assertEqual(grade.validate_score(selected_reports[role],role,request,freeze_records[role]),
                         canonical[role][0]['mc_maze_20_split'])
    score_refusals=[]
    for label,change in [('missing_metric',lambda x:x['metrics'].pop('fp-bps')),
        ('extra_metric',lambda x:x['metrics'].update(extra=0.0)),
        ('nonfinite',lambda x:x['metrics'].update({'vel R2':float('nan')})),
        ('boolean',lambda x:x['metrics'].update({'co-bps':True})),
        ('candidate_author_role',lambda x:x.update(role='author_calibration')),
        ('wrong_prediction',lambda x:x.update(submission_sha256='0'*64)),
        ('wrong_method',lambda x:x.update(method_id='other'))]:
        bad=copy.deepcopy(selected_reports['candidate']);change(bad)
        with case.assertRaises(ValueError,msg=label):grade.validate_score(bad,'candidate',request,freeze_records['candidate'])
        score_refusals.append(label)
    def run_case(label,change=None,fail_scale=False):
        selected=copy.deepcopy(request)
        report_parent=root/label/'report';report_parent.mkdir(parents=True)
        selected['output_root']=str(report_parent/'test-pair')
        if change:change(selected)
        request_descriptor=put(inputs/(label+'-request.json'),selected)
        seen=[];target_boundaries=[]
        def metadata_boundary(path,sha):
            raw=grade.body(path);case.assertEqual(grade.pin(raw)['sha256'],sha)
            case.assertEqual(grade.decode(raw),selected)
            return selected,freeze_records,method_record,{'explicit_host_authority_boundary':True}
        def frozen(filename,*args):
            result=ordinary.validate_freeze(filename,*args)
            role=Path(filename).stem;seen.append('validated:'+role);return result
        def scale_boundary(ref,candidate,gain,*,expected_shapes):
            case.assertEqual(gain,[8,9]);case.assertEqual(expected_shapes,original_panel['expected_shapes'])
            case.assertEqual(seen,['validated:reference','validated:candidate'])
            case.assertEqual(Path(ref).read_bytes(),raw_bytes['reference'])
            case.assertEqual(Path(candidate).read_bytes(),raw_bytes['candidate'])
            seen.append('scale-proof')
            if fail_scale:raise ValueError('generated scale mismatch before target')
            return {'schema':'smc_test_gain_scale_proof_v1','gain':[8,9],
                'reference':{k:prediction['reference'][k] for k in ('bytes','sha256')},
                'candidate':{k:prediction['candidate'][k] for k in ('bytes','sha256')},
                'all_eight_fields_exact':True,'target_accessed':False,
                'fullshape_scan_boundary':'explicit generated double; separate real tiny verifier controls'}
        def score_boundary(submission,manifest,protocol_path,freeze_path,target_path,target_sha,evaluator,output):
            role=Path(submission).stem
            case.assertEqual(seen,['validated:reference','validated:candidate','scale-proof'])
            barrier_path=Path(selected['output_root'])/'BOTH_SNAPSHOTS.json'
            case.assertTrue(barrier_path.is_file())
            barrier=grade.decode(grade.body(barrier_path))
            case.assertTrue(barrier['both_complete_original_freezes_validated'])
            case.assertTrue(barrier['candidate_transform_verified']);case.assertIs(barrier['target_payload_accessed'],False)
            case.assertEqual(grade.checked(barrier['scale_proof'])['gain'],[8,9])
            target_boundaries.append(role)
            value=copy.deepcopy(selected_reports[role])
            ordinary.write_new_json(output,value)
            return value
        selected_scorer=isolate(scorer,{'validate_submission':fullshape_boundary,
            'validate_freeze':frozen,'score_predictions':score_boundary})
        probe=isolate(grade,{'metadata':metadata_boundary,'versions':lambda:dict(grade.PACKAGES),
            'load_scorer':lambda:selected_scorer,'verify_scaled_pair':scale_boundary})
        if change or fail_scale:
            with case.assertRaises(ValueError):probe.run(request_descriptor['path'],request_descriptor['sha256'])
            case.assertEqual(target_boundaries,[])
            case.assertFalse((Path(selected['output_root'])/'REPORT.json').exists())
            return None
        result=probe.run(request_descriptor['path'],request_descriptor['sha256'])
        case.assertEqual(target_boundaries,['reference','candidate'])
        metric_helper.assert_vectors(case,result['arms']['reference']['metrics'],result['arms']['candidate']['metrics'],
                                     result['signed_candidate_minus_reference'])
        case.assertEqual((result['phase'],result['dataset']),('test','mc_maze_20'))
        for flag in ('historical_noncausal_supervisor_success','new_inference_executed','participant_episode_executed',
            'AI_trial_executed','reproduction_claim','improvement_claim','SOTA_claim'):case.assertIs(result[flag],False)
        case.assertEqual(result['target_exposure'],'public_original_test_targets_released_2026_01')
        return result
    result=run_case('positive')
    altered=inputs/'second-arm-drift.h5';altered.write_bytes(raw_bytes['candidate']+b'changed')
    run_case('second-arm-drift',lambda selected:selected['predictions']['candidate'].update(path=str(altered)))
    run_case('invalid-scale',fail_scale=True)
    case.assertEqual(grade.PACKAGES['h5py'],'3.10.0')
    case.assertEqual(importlib.metadata.version('h5py'),'3.11.0')
    files=[p for p in root.rglob('*') if p.is_file()]
    extent=sum(p.stat().st_size for p in files)
    case.assertLessEqual(extent+deleted_bytes,1048576)
    return {'actual_original_freeze_and_score_bodies':True,'actual_original_score_calls':2,
        'actual_local_score_dependency_versions':local_reports['reference']['dependency_versions'],
        'production_versions_refusal':True,'production_original_authority_refusal':True,
        'production_local_score_report_refusals':2,'production_constants_or_globals_changed':False,
        'positive_pipeline_boundary':'generated selected-runtime/numerical reports and original metadata/fullgeometry authority, not runtime admission',
        'real_pair_snapshot_byte_copy_and_freeze_hash_checks':True,
        'both_snapshot_and_scaleproof_barrier_before_target_boundary':True,
        'second_arm_drift_and_scale_failure_pre_target_refused':True,
        'all_four_vectors_and_signed_deltas':result['signed_candidate_minus_reference'],
        'decoder_cohort':{'train_trials':2295,'TEST_trials':574,'base_bins':35,'forward_bins':10},
        'score_report_refusals':score_refusals,'actual_original_target_or_model_used':False,
        'genuine_completed_VALID_or_physical_runtime_qualified':False,
        'generated_serialized_extent_bytes':extent,'deleted_generated_snapshot_bytes':deleted_bytes,
        'generated_write_charge_bytes':extent+deleted_bytes,'read_work_bound_bytes':8388608}
