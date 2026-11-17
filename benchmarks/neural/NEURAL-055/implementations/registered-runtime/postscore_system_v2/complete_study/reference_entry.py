"""Real source-owned independent bank fit and current-view prediction CLI.

No use by BUILD ONLY controls; numerical providers remain unexecuted.
"""
import time
ORIGINAL_ENTRY=time.monotonic()
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from n055.common import parse,encoded,require,diagnostic_type
from n055.registry import PEOPLE,training_key
from n055.schedule import development
from n055.learning import Learner,TrainingRecorder,expected_jobs,arrays,checked,synthetic,pearson,probabilities,r1_correlation,r1_probabilities
from n055.assignment import assign

def write(path,value):
    body=encoded(value)
    with Path(path).open('xb') as f:f.write(body);f.flush();os.fsync(f.fileno())

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='phase',required=True)
    fit=sub.add_parser('fit');fit.add_argument('--train',required=True);fit.add_argument('--model-output',required=True)
    infer=sub.add_parser('infer');infer.add_argument('--query',required=True);infer.add_argument('--model',required=True);infer.add_argument('--output',required=True)
    a=p.parse_args();root=Path(a.train if a.phase=='fit' else a.query).parent
    cell=parse((root/'CELL.json').read_bytes());host=parse((root/'HOST.json').read_bytes())
    # Same monotonic clock domain is qualified by the native host profile.
    deadline=host['original_action_deadline'];require(ORIGINAL_ENTRY<deadline,'original inherited action deadline')
    def guard(stage):require(time.monotonic()<deadline,'reference original deadline: '+stage)
    ref=cell['evaluated_system'];require(ref in ('R0','R1','R2','R3'),'exact independent reference')
    operations=[];learner=None;first=None;recorder=TrainingRecorder(guard)
    if a.phase=='fit' and ref!='R0':
        recorder.declare(expected_jobs(ref,cell['outer_person'],training_key(cell)['mask'],cell['seed'],[q for q in PEOPLE if q!=cell['outer_person']]))
        operations=recorder.records
    try:
        guard('entry');np=arrays()
        def load(name,shape):
            guard('before array load');value=np.load(root/name,allow_pickle=False,mmap_mode='r')
            require(value.shape==shape and value.dtype.kind=='f','complete floating source geometry');checked(value);guard('after array load');return value
        if a.phase=='fit':
            require(ref!='R0','R0 FIT is declared no-fit, not a fabricated process')
            t=parse((root/'TRAINING.json').read_bytes());eligible=[q for q in PEOPLE if q!=cell['outer_person']]
            require([r['person_id'] for r in t['people']]==eligible and t['inner_participant_holdouts']==eligible,'full nine eligible training people')
            x=load('training_image_features.npy',(16540,4096))
            people={q:load('train/'+q+'.npy',(16540,17,100)).reshape(16540,1700) for q in eligible}
            d=development(t['original_THINGS_training_concept_ids'],t['training_image_ids'])
            require(sorted(i for p in d['selection_panels'] for i in p)==t['inner_development_row_indices'],'original330 concept support')
            calibration=[p['training_row_indices'] for p in t['reference_calibration_panels']['panels']]
            learner=Learner(x,people,cell['outer_person'],d['fit'],d['selection_panels'],calibration,guard,training_key(cell)['mask'],recorder)
            model,selection=learner.fit(ref,cell['seed'])
            guard('before complete bank write')
            payload=dict(model);payload['kind']=np.array(model['kind']);payload['temperature']=np.array(selection['temperature'],dtype=np.float64)
            with open(a.model_output,'xb') as f:np.savez(f,**payload);f.flush();os.fsync(f.fileno())
            require(Path(a.model_output).stat().st_size<=268435456,'original256MiB model cap')
            selection.update(cell=cell,training_key=training_key(cell),all_inner_search_dispositions_retained=True)
            method={'schema':'neural055-selected-method-v2','cell':cell,'fitted_people':eligible,'fit_rows':list(range(16540)),
                    'learned_transforms':['training-only feature mean/std','equal-person EEG target offset'],
                    'inner_search':selection['selection_records'],'selected_settings':{'config':selection['selected_config'],'epoch':selection['selected_epoch'],'temperature':selection['temperature']},
                    'inference_action_policy':{'kind':'fixed_independent_reference','query_fit':False},'source_lineage':[{'role':'complete_original_reference_source','controlled_by_native_host':True}],
                    'reference_detail':selection}
            write('/output/selected_method.json',method);guard('after complete selected bank publication')
            operations=learner.recorder.records
        else:
            case=parse((root/'CASE.json').read_bytes());require(len(case['query_ids'])==200 and len(case['candidate_ids'])==200,'whole200 case')
            if ref=='R0':
                probs=[[1/200]*200 for _ in range(200)];assignment=list(range(200))
                operations=[{'kind':'declared_no_fit_R0_current_view','actual_call':True,'EEG_values_read':False}]
            else:
                guard('before sealed bank read')
                with np.load(a.model,allow_pickle=False) as z:
                    model={k:z[k] for k in z.files};model['kind']=str(model['kind']);temperature=float(model.pop('temperature'))
                x=load('candidate_features.npy',(200,4096));query=load('query.npy',(200,17,100))
                predicted=synthetic(model,x,guard)
                scores=r1_correlation(query.reshape(200,1700),predicted) if ref=='R1' else pearson(query,predicted)
                probs=(r1_probabilities(scores,temperature) if ref=='R1' else probabilities(scores,temperature)).tolist();assignment=assign(scores)
                operations=[{'kind':'actual_current_view_reference_prediction','cell':cell,'query_fit':False,'temperature':temperature,'start':ORIGINAL_ENTRY,'end':time.monotonic()}]
            pred={'schema':'neural055-prediction-v1','case_id':case['case_id'],'query_ids':case['query_ids'],'candidate_ids':case['candidate_ids'],
                  'probabilities':probs,'assignment':[case['candidate_ids'][j] for j in assignment]}
            write(a.output,pred);guard('after full prediction publication')
    except BaseException as exc:
        first=exc
        recorder.fail_pending(exc)
        if learner is not None:
            learner.recorder.fail_pending(exc);operations=learner.recorder.records
            for r in learner.selection_records:
                if r['status']=='unattempted':r.update(status='unattempted_after_failure',first_error={'type':diagnostic_type(exc)})
        raise
    finally:
        try:
            write('/output/operations.json',{'schema':'neural055-reference-original-operations-v1','cell':cell,'phase':a.phase,'start':ORIGINAL_ENTRY,'end':time.monotonic(),
                                           'original_first_error':None if first is None else {'type':diagnostic_type(first)},'records':operations,
                                           'selection_dispositions':[] if learner is None else learner.selection_records,
                                           'physical_cost_is_enclosing_native_process':'inner timing is a breakdown, not double-counted additional process CPU'})
            guard('after original operation publication')
        except BaseException as secondary:
            try:
                raw=encoded({'reference_original_failure_type':None if first is None else diagnostic_type(first),
                             'secondary_operation_publication_failure':diagnostic_type(secondary)})+b'\n'
                offset=0
                while offset<len(raw):
                    n=os.write(2,raw[offset:]);require(n>0,'secondary receipt progress');offset+=n
            except BaseException:
                pass  # No false complete operations receipt; outer custody remains unavailable.
            if first is None:raise
            # Retain first scientific/process error; the native nonzero plus missing
            # required output preserves secondary publication failure as unavailable.
    return 0

if __name__=='__main__':raise SystemExit(main())
