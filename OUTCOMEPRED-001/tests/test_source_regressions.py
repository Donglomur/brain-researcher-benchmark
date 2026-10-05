"""Actual source-output acceptance/forgery matrix; never fabricates a reference."""
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import numpy as np
import pytest
import prediction_contract as q
import proof_of_work as pw
from test_authoring_regressions import write_csv,write_submission

@pytest.fixture(scope='module')
def reference():
    if not os.environ.get('REPAIR_ORACLE_OUTPUT'): pytest.skip('Genuine parent-run outputs not provided')
    return pw.load_reference(Path(os.environ.get('REPAIR_REFERENCE_PATH',Path(__file__).with_name('reference.npz'))))

@pytest.fixture
def output(reference,tmp_path):
    with tempfile.TemporaryDirectory(dir=tmp_path) as directory:
        target=Path(directory)/'output'; shutil.copytree(Path(os.environ['REPAIR_ORACLE_OUTPUT']),target)
        yield target

def csv_mutate(path,fields,change):
    rows=q.csv_load(path,fields); change(rows); write_csv(path,fields,rows)

def json_mutate(path,change):
    value=q.json_load(path); change(value); path.write_text(json.dumps(value,allow_nan=False))

def npz_mutate(path,change):
    with np.load(path,allow_pickle=False) as z: values={k:np.array(z[k]) for k in z.files}
    change(values)
    with path.open('wb') as f: np.savez_compressed(f,**values)

def reject(output,reference):
    with pytest.raises((AssertionError,ValueError,KeyError,FileNotFoundError,TypeError,EOFError)):
        q.validate_output_directory(output,reference)

def test_actual_original_oracle(reference):
    q.validate_output_directory(Path(os.environ['REPAIR_ORACLE_OUTPUT']),reference)

def test_actual_independent_original_source(reference):
    name=os.environ.get('REPAIR_INDEPENDENT_OUTPUT')
    if not name: pytest.skip('Original-source independent positive not provided')
    q.validate_output_directory(Path(name),reference)

def test_axis_and_csv_order_free(output,reference):
    for name,fields in [('source_trials.csv',q.SOURCE_FIELDS),('trial_predictions.csv',q.PRED_FIELDS),('folds.csv',q.FOLD_FIELDS),('decoding_vs_window.csv',q.CURVE_FIELDS)]:
        rows=q.csv_load(output/name,fields)[::-1]
        for row in rows: row['description']='harmless extra'
        write_csv(output/name,list(reversed(fields))+['description'],rows)
    def change(v):
        a=np.arange(21)[::-1]; t=np.arange(len(v['trial_id']))[::-1]; u=np.arange(len(v['unit_id']))[::-1]
        for k in ('analysis','window_start_s','window_end_s'): v[k]=v[k][a]
        for k in ('source_trial_row','trial_id'): v[k]=v[k][t]
        for k in ('source_unit_row','unit_id'): v[k]=v[k][u]
        v['spike_count']=v['spike_count'][np.ix_(a,t,u)]
    npz_mutate(output/'spike_counts.npz',change)
    json_mutate(output/'results.json',lambda r:r['analyses'].reverse())
    json_mutate(output/'run_metadata.json',lambda r:(r['support_by_analysis'].reverse(),r['fits'].reverse()))
    q.validate_output_directory(output,reference)

def test_numeric_notation_and_rounding(output,reference):
    integer_fields=set('source_trial_row trial_id fold label prediction rewarded eligible selected n_train_trials n_test_trials n_train_class0 n_train_class1 n_test_class0 n_test_class1 n_correct'.split())
    for name,fields in [('source_trials.csv',q.SOURCE_FIELDS),('trial_predictions.csv',q.PRED_FIELDS),('folds.csv',q.FOLD_FIELDS),('decoding_vs_window.csv',q.CURVE_FIELDS)]:
        rows=q.csv_load(output/name,fields)
        for row in rows:
            for key,value in row.items():
                if value=='' or key in ('analysis','choice','selection_reason'): continue
                if key in integer_fields:
                    before=q.integer(value); row[key]=f'{before:.17e}'; assert q.integer(row[key])==before
                elif key=='decision_score': row[key]=format(float(value),'.8f')
                else: row[key]=format(float(value),'.17e')
        if name=='trial_predictions.csv':
            for row in rows: row['prediction']=int(float(row['decision_score'])>0)
        write_csv(output/name,fields,rows)
    # Allowed near-zero rounding can flip the sign; derived statistics must follow it.
    pred=q.validate_predictions(q.csv_load(output/'trial_predictions.csv',q.PRED_FIELDS),reference)
    folds,curve,result=q.summarize(reference,pred)
    write_csv(output/'folds.csv',q.FOLD_FIELDS,folds)
    write_csv(output/'decoding_vs_window.csv',q.CURVE_FIELDS,curve)
    (output/'results.json').write_text(json.dumps(result,allow_nan=False))
    q.validate_output_directory(output,reference)

def test_optional_status_versions_and_free_prose(output,reference):
    def change(r):
        r.pop('status',None); r['software']={'equivalent_independent_implementation':'reported-version'}; r['additional_description']={'label':'not graded'}
    json_mutate(output/'run_metadata.json',change)
    json_mutate(output/'results.json',lambda r:r.update(optional_sensitivity={'accuracy':.91,'description':'Extra ungraded analysis'}))
    (output/'findings.md').write_text('The requested measurements and limitations are reported in the accompanying tables.\n')
    q.validate_output_directory(output,reference)

def test_public_contract_identity(reference):
    import hashlib
    path=Path(__file__).parents[1]/'environment/method_contract.json'
    assert hashlib.sha256(path.read_bytes()).hexdigest()==pw.METHOD_SHA256
    q.match(q.json_load(path),reference['metadata']['method'],closed=True)

FILES=['source_trials.csv','spike_counts.npz','trial_predictions.csv','folds.csv','decoding_vs_window.csv','results.json','run_metadata.json','findings.md']
@pytest.mark.parametrize('name',FILES)
@pytest.mark.parametrize('mode',['missing','empty'])
def test_missing_empty(output,reference,name,mode):
    path=output/name
    if mode=='missing': path.unlink()
    else: path.write_bytes(b'')
    reject(output,reference)

@pytest.mark.parametrize('name,fields',[('source_trials.csv',q.SOURCE_FIELDS),('trial_predictions.csv',q.PRED_FIELDS),('folds.csv',q.FOLD_FIELDS),('decoding_vs_window.csv',q.CURVE_FIELDS)])
@pytest.mark.parametrize('mode',['drop','duplicate'])
def test_partial_duplicate_tables(output,reference,name,fields,mode):
    csv_mutate(output/name,fields,lambda r:r.pop() if mode=='drop' else r.append(dict(r[0])))
    reject(output,reference)

@pytest.mark.parametrize('field',['trial_id','source_trial_row','rewarded','eligible','selected','selection_reason','fold','choice','feedback_time_s','stimulus_time_s'])
def test_wrong_source_ledger(output,reference,field):
    def change(rows):
        r=next(r for r in rows if r['selected']=='1')
        if field=='selection_reason': r[field]='eligible_not_sampled'
        elif field=='choice': r[field]='none'
        elif field in ('rewarded','eligible','selected'): r[field]=1-int(r[field])
        elif field.endswith('_s'): r[field]=float(r[field])+.01
        else: r[field]=int(r[field])+1
    csv_mutate(output/'source_trials.csv',q.SOURCE_FIELDS,change); reject(output,reference)

@pytest.mark.parametrize('mode',['changed_count','bool_count','float_count','negative_count','overflow_count','unit_id','trial_id','analysis','window','partial_unit','partial_trial','object'])
def test_false_count_receipt(output,reference,mode):
    def change(v):
        if mode=='changed_count': v['spike_count'][0,0,0]+=1
        elif mode=='bool_count': v['spike_count']=v['spike_count'].astype(bool)
        elif mode=='float_count': v['spike_count']=v['spike_count'].astype(float)
        elif mode=='negative_count': v['spike_count']=v['spike_count'].astype(np.int64); v['spike_count'][0,0,0]=-1
        elif mode=='overflow_count': v['spike_count']=v['spike_count'].astype(np.uint64); v['spike_count'][0,0,0]=2**64-1
        elif mode=='unit_id': v['unit_id'][0]+=100000
        elif mode=='trial_id': v['trial_id'][0]+=100000
        elif mode=='analysis': v['analysis'][0]='invented'
        elif mode=='window': v['window_start_s'][0]+=.01
        elif mode=='partial_unit': v['spike_count']=v['spike_count'][:,:,:-1]
        elif mode=='partial_trial': v['spike_count']=v['spike_count'][:,:-1,:]
        else: v['unit_id']=v['unit_id'].astype(object)
    npz_mutate(output/'spike_counts.npz',change); reject(output,reference)

@pytest.mark.parametrize('field',['analysis','source_trial_row','trial_id','fold','label','prediction','decision_score','window_start_s','window_end_s'])
def test_wrong_oof_identity_or_score(output,reference,field):
    def change(rows):
        r=rows[0]
        if field=='analysis': r[field]='unknown'
        elif field in ('label','prediction'): r[field]=1-int(r[field])
        elif field=='decision_score': r[field]=float(r[field])+1
        elif field.endswith('_s'): r[field]=float(r[field])+.01
        else: r[field]=int(r[field])+1
    csv_mutate(output/'trial_predictions.csv',q.PRED_FIELDS,change); reject(output,reference)

@pytest.mark.parametrize('mode',['score_scale','perfect','zero','inverse','swap_windows'])
def test_coherent_score_and_aggregate_forgeries(output,reference,mode):
    scores=reference['scores'].copy()
    if mode=='score_scale': scores*=2
    elif mode=='perfect': scores[:]=np.tile(2*reference['labels']-1,(21,1))
    elif mode=='zero': scores[:]=0
    elif mode=='inverse': scores*=-1
    else: scores[[0,1]]=scores[[1,0]]
    assert not np.allclose(scores,reference['scores'],atol=1e-5,rtol=1e-6)
    write_submission(output,reference,scores); reject(output,reference)

@pytest.mark.parametrize('mode',['translate_source_ids','complement_labels'])
def test_coherent_historical_identity_holes(output,reference,mode):
    forged=copy.deepcopy(reference)
    if mode=='translate_source_ids':
        forged['source_trial_row']+=100000; forged['trial_id']+=100000
        for row in forged['source_rows']:
            row['source_trial_row']+=100000; row['trial_id']+=100000
    else:
        forged['labels']=1-forged['labels']; forged['scores']=-forged['scores']
        for row in forged['source_rows']: row['rewarded']=1-row['rewarded']
    # Every public trial/count identity or label/score/aggregate changes together.
    write_submission(output,forged)
    reject(output,reference)

@pytest.mark.parametrize('field',q.FOLD_FIELDS[2:])
def test_wrong_fold_arithmetic(output,reference,field):
    csv_mutate(output/'folds.csv',q.FOLD_FIELDS,lambda rows:rows[0].update({field:float(rows[0][field])+.1 if field=='accuracy' else int(rows[0][field])+1}))
    reject(output,reference)

@pytest.mark.parametrize('mode',['affine_curve','pooled_as_mean','headline','n_units','class_counts','bool_number','missing_analysis'])
def test_wrong_reported_arithmetic(output,reference,mode):
    if mode=='affine_curve':
        csv_mutate(output/'decoding_vs_window.csv',q.CURVE_FIELDS,lambda rows:[r.update(accuracy=.1+.7*float(r['accuracy'])) for r in rows])
    else:
        def change(r):
            if mode=='pooled_as_mean':
                pooled=r['headline']['pooled_oof_accuracy']
                assert abs(pooled-r['headline']['mean_accuracy'])>1e-6
                r['headline']['mean_accuracy']=pooled
                next(v for v in r['analyses'] if v['analysis']=='headline_pre')['mean_accuracy']=pooled
                r['post_minus_pre']=r['post_feedback']['mean_accuracy']-pooled
            elif mode=='headline': r['headline']['mean_accuracy']+=.1; r['post_minus_pre']-=.1
            elif mode=='n_units': r['n_units']-=1
            elif mode=='class_counts': r['selected_class_counts']['0']+=1
            elif mode=='bool_number': r['chance']=True
            else: r['analyses'].pop()
        json_mutate(output/'results.json',change)
    reject(output,reference)

@pytest.mark.parametrize('mode',['source_hash','method_hash','extra_source','extra_method','boolean_method','quality_count','window_support','incomplete_fit','fit_gradient','fit_finite','fit_warning_type','failed_status','pilot_status','missing_software'])
def test_false_metadata(output,reference,mode):
    def change(r):
        if mode=='source_hash': r['source_manifest_sha256']='0'*64
        elif mode=='method_hash': r['method_contract_sha256']='0'*64
        elif mode=='extra_source': r['source']['additional_source']='invented'
        elif mode=='extra_method': r['method']['alternative_preprocessing']=True
        elif mode=='boolean_method': r['method']['model']['C']=True
        elif mode=='quality_count': k=next(iter(r['source_summary']['kilosort_label_counts'])); r['source_summary']['kilosort_label_counts'][k]+=1
        elif mode=='window_support': r['support_by_analysis'][0][q.SUPPORT_FIELDS[0]]+=1
        elif mode=='incomplete_fit': r['fits'].pop()
        elif mode=='fit_gradient': r['fits'][0]['mean_gradient_inf']=1e-4
        elif mode=='fit_finite': r['fits'][0]['finite_parameters']=False
        elif mode=='fit_warning_type': r['fits'][0]['warnings']='hidden'
        elif mode=='failed_status': r['status']='failed_precondition'
        elif mode=='pilot_status': r['status']='resource_pilot'
        else: r.pop('software')
    json_mutate(output/'run_metadata.json',change); reject(output,reference)

def test_genuine_global_scaler_control(reference):
    name=os.environ.get('REPAIR_GLOBAL_CONTROL_OUTPUT')
    if not name: pytest.skip('Genuine wrong-scaler control not provided')
    output=Path(name)
    q.validate_source(q.csv_load(output/'source_trials.csv',q.SOURCE_FIELDS),reference)
    q.validate_counts(output/'spike_counts.npz',reference)
    q.validate_metadata(q.json_load(output/'run_metadata.json'),reference)
    with pytest.raises(AssertionError,match='decision score'): q.validate_output_directory(output,reference)
