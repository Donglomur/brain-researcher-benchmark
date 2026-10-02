"""Genuine source-bound controls; invoked only after separately gated source runs.

Reference construction is shared once per pytest session. No submitted-output
acceptance or mutation verdict is cached. Every temporary full output is removed.
"""
from contextlib import contextmanager
import copy
import csv
import json
import os
from pathlib import Path
import shutil
import tempfile

import numpy as np
import pytest

import fixture_support as f
import io_contract as io
import population_contract as q
import proof_of_work as p


def supplied(name):
    value=os.environ.get(name)
    if not value:pytest.skip(name+' is not configured for this source-free invocation')
    path=Path(value);assert path.is_dir(),name+' was supplied but does not exist'
    return path


@pytest.fixture(scope='module')
def original_output():return supplied('REPAIR_ORACLE_OUTPUT')


@contextmanager
def output_copy(original):
    with tempfile.TemporaryDirectory(prefix='viscat-control-') as name:
        path=Path(name)/'output';shutil.copytree(original,path);yield path


def rows(path):
    with path.open(newline='') as stream:
        reader=csv.DictReader(stream);return reader.fieldnames,list(reader)


def change_table(path, change):
    columns,data=rows(path);change(data);f.write_csv(path,data,columns)


def reject(path,ref):
    with pytest.raises((AssertionError,ValueError,EOFError,OSError,KeyError,TypeError)):
        p.validate_output_directory(path,ref)


@pytest.mark.parametrize('environment',['REPAIR_ORACLE_OUTPUT','REPAIR_INDEPENDENT_OUTPUT'])
def test_genuine_source_implementations(environment,source_reference):
    p.validate_output_directory(supplied(environment),source_reference)


def test_valid_other_headline(original_output,source_reference):
    with output_copy(original_output) as out:
        derived=q.analyze(source_reference)
        result=q.summarize(source_reference,derived['neurons'],q.POPULATIONS[0])
        (out/'results.json').write_text(json.dumps(result,allow_nan=False))
        f.mutate_json(out/'run_metadata.json',lambda x:x.update(headline_population=q.POPULATIONS[0]))
        p.validate_output_directory(out,source_reference)


def test_coherent_permutations(original_output,source_reference):
    with output_copy(original_output) as out:
        for name in ('sessions','trials','units','neurons','split_events'):
            columns,data=rows(out/(name+'.csv'));f.write_csv(out/(name+'.csv'),data[::-1],columns[::-1])
        def permute(a):
            n=len(a['unit_key']);a['unit_key']=a['unit_key'][::-1];a['response_unit_index']=n-1-a['response_unit_index']
            for name in p.INTEGER_ARRAYS:
                if name!='repeat_id':a[name]=a[name][::-1]
            a['rate_hz']=a['rate_hz'][::-1];a['repeat_id']=a['repeat_id'][::-1]
            a['train_membership']=a['train_membership'][::-1,::-1]
        f.mutate_npz(out/'responses.npz',permute)
        f.mutate_json(out/'run_metadata.json',lambda x:x['source_observed']['sessions'].reverse())
        p.validate_output_directory(out,source_reference)


def test_reasonable_float_rounding(original_output,source_reference):
    with output_copy(original_output) as out:
        for name in ('neurons','split_events'):
            columns,data=rows(out/(name+'.csv'))
            for row in data:
                for key,value in row.items():
                    if value and (key in ('kw_H','kw_p','train_H','train_p') or 'auc' in key or 'mean_rate' in key):
                        row[key]=format(float(value),'.12g')
            f.write_csv(out/(name+'.csv'),data,columns)
        f.mutate_npz(out/'responses.npz',lambda a:a.update(rate_hz=np.round(a['rate_hz'],9)))
        p.validate_output_directory(out,source_reference)


def test_harmless_descriptive_equivalents(original_output,source_reference):
    with output_copy(original_output) as out:
        f.mutate_json(out/'run_metadata.json',lambda x:x.update(software_versions={'independent':'different-version'},warnings=['A documented harmless warning'],notes={'extra':'description'}))
        f.mutate_json(out/'results.json',lambda x:x.update(optional_analysis={'description':'ungated optional context'}))
        (out/'findings.md').write_text('A differently phrased descriptive analysis. No prescribed keywords.\n')
        for filename in ('neurons.csv','split_events.csv'):
            columns,data=rows(out/filename)
            for row in data:row['descriptive_extra']='optional'
            f.write_csv(out/filename,data,columns+['descriptive_extra'])
        p.validate_output_directory(out,source_reference)


TABLE_CHANGES=[('sessions.csv','n_recognition_trials'),('sessions.csv','subject_id'),
 ('trials.csv','category_code'),('trials.csv','category_name'),('trials.csv','stim_on_time_s'),('trials.csv','trial_id'),
 ('units.csv','electrode_id'),('units.csv','original_channel'),('units.csv','included'),
 ('neurons.csv','kw_H'),('neurons.csv','kw_p'),('neurons.csv','preferred_category'),('neurons.csv','same_trial_auc'),
 ('neurons.csv','rank_sum_twice_cat_1'),('neurons.csv','sum_count_cat_1'),('neurons.csv','n_selected_splits'),
 ('split_events.csv','train_H'),('split_events.csv','train_p'),('split_events.csv','train_preferred_category'),
 ('split_events.csv','test_auc'),('split_events.csv','test_u_preferred_twice'),('split_events.csv','included_in_conditional_summary')]


@pytest.mark.parametrize('filename,field',TABLE_CHANGES)
def test_changed_required_field(original_output,source_reference,filename,field):
    with output_copy(original_output) as out:
        def change(data):
            row=next(r for r in data if r[field]!='')
            if field in ('subject_id','category_name'):row[field]+='wrong'
            elif field in ('included','included_in_conditional_summary'):row[field]='false' if io.flag(row[field]) else 'true'
            else:row[field]=str(float(row[field])+1)
        change_table(out/filename,change);reject(out,source_reference)


@pytest.mark.parametrize('mode',['counts','rates','labels','trial_id','row','unit_keys','membership','repeat','drop_response','duplicate_response',
                                'bool_counts','float_counts','nonfinite','negative','object','wrong_mask_dtype'])
def test_invalid_primitive(original_output,source_reference,mode):
    with output_copy(original_output) as out:
        def change(a):
            if mode=='counts':a['spike_count'][0]+=1
            elif mode=='rates':a['rate_hz'][0]+=1
            elif mode=='labels':a['category_code'][0]=6
            elif mode=='trial_id':a['trial_id'][0]+=1
            elif mode=='row':a['source_trial_row'][0]+=1
            elif mode=='unit_keys':a['unit_key'][0]=a['unit_key'][1]
            elif mode=='membership':a['train_membership'][0,0]=~a['train_membership'][0,0]
            elif mode=='repeat':a['repeat_id'][0]=a['repeat_id'][1]
            elif mode=='drop_response':
                for k in ('response_unit_index','source_trial_row','trial_id','category_code','spike_count','rate_hz'):a[k]=a[k][1:]
                a['train_membership']=a['train_membership'][:,1:]
            elif mode=='duplicate_response':
                for k in ('response_unit_index','source_trial_row','trial_id','category_code'):a[k][0]=a[k][1]
            elif mode=='bool_counts':a['spike_count']=a['spike_count'].astype(bool)
            elif mode=='float_counts':a['spike_count']=a['spike_count'].astype(float)
            elif mode=='nonfinite':a['rate_hz'][0]=np.inf
            elif mode=='negative':a['spike_count'][0]=-1
            elif mode=='object':a['unit_key']=a['unit_key'].astype(object)
            elif mode=='wrong_mask_dtype':a['train_membership']=a['train_membership'].astype(np.uint8)
        f.mutate_npz(out/'responses.npz',change);reject(out,source_reference)


@pytest.mark.parametrize('filename',['sessions.csv','trials.csv','units.csv','responses.npz','neurons.csv','split_events.csv','results.json','run_metadata.json','findings.md'])
def test_missing_artifact(original_output,source_reference,filename):
    with output_copy(original_output) as out:(out/filename).unlink();reject(out,source_reference)


@pytest.mark.parametrize('filename',['sessions.csv','trials.csv','units.csv','neurons.csv','split_events.csv'])
@pytest.mark.parametrize('mode',['missing','duplicate'])
def test_incomplete_or_duplicated_table(original_output,source_reference,filename,mode):
    with output_copy(original_output) as out:
        change_table(out/filename,lambda data:data.pop() if mode=='missing' else data.append(dict(data[0])))
        reject(out,source_reference)


@pytest.mark.parametrize('mode',['empty','json','dangling','fifo'])
def test_late_failure_receipt(original_output,source_reference,mode):
    with output_copy(original_output) as out:
        path=out/'failure_report.json'
        if mode=='dangling':path.symlink_to(out/'absent')
        elif mode=='fifo':os.mkfifo(path)
        else:path.write_text('' if mode=='empty' else '{"status":"failed_precondition"}')
        reject(out,source_reference)


@pytest.mark.parametrize('mode',['source_hash','method_hash','method_object','source_counts','category_mapping','status','bool_number','nonfinite_extra','missing_null','population'])
def test_changed_json_contract(original_output,source_reference,mode):
    with output_copy(original_output) as out:
        if mode in ('source_hash','method_hash','method_object','source_counts','category_mapping','status'):
            def change(x):
                if mode=='source_hash':x['source_manifest_sha256']='0'*64
                elif mode=='method_hash':x['method_contract_sha256']='0'*64
                elif mode=='method_object':x['method_contract']['task_id']='wrong'
                elif mode=='source_counts':x['source_observed']['n_mtl_units']+=1
                elif mode=='category_mapping':x['source_observed']['sessions'][0]['category_mapping'][0]['category_name']='wrong'
                else:x['status']='resource_pilot'
            f.mutate_json(out/'run_metadata.json',change)
        elif mode=='nonfinite_extra':
            path=out/'results.json';path.write_text(path.read_text().rstrip()[:-1]+',"extra":{"bad":1e999}}')
        else:
            def change(x):
                if mode=='bool_number':x['n_mtl_units']=True
                elif mode=='missing_null':x.pop('preferred_category_auc')
                else:x['populations']['invented_population']=dict(n=1,mean_auc=.9,status='ok')
            f.mutate_json(out/'results.json',change)
        reject(out,source_reference)


@pytest.mark.parametrize('mode',['add_one_all','category_cycle','zero_all','trial_rotation'])
def test_coherent_wrong_source_recomputed_reports(source_reference,original_output,mode):
    # A new internally coherent analysis cannot substitute a different source.
    reference={k:v for k,v in source_reference.items() if k!='_analysis'}
    wrong=dict(reference,arrays={k:v.copy() for k,v in reference['arrays'].items()})
    a=wrong['arrays']
    if mode=='add_one_all':a['spike_count']+=1
    elif mode=='category_cycle':a['category_code']=a['category_code']%5+1
    elif mode=='zero_all':a['spike_count'][:]=0
    else:a['spike_count']=np.roll(a['spike_count'],1)
    # Controls without an actual changed primitive are explicitly non-discriminating.
    effective=any(not np.array_equal(a[k],source_reference['arrays'][k]) for k in ('spike_count','category_code'))
    a['rate_hz']=a['spike_count']/1.5
    with tempfile.TemporaryDirectory(prefix='viscat-coherent-') as directory:
        out=f.emit(Path(directory)/'output',wrong)
        if effective:reject(out,source_reference)
        else:p.validate_output_directory(out,source_reference)


@pytest.mark.parametrize('control',['train_auc_as_heldout','fold_heldout_auc'])
def test_actual_component_control(control,source_reference):
    # Parent-reviewed source-derived control helper supplies its measured receipts.
    root=supplied('REPAIR_CONTROL_OUTPUT')
    report=io.json_load(root/'report.json')
    item=report['controls'][control]
    path=root/control;assert path.is_dir() and item['status']=='constructed'
    if item['nondiscriminating']:
        assert item['support_and_gaps']['n_exact_u2_changes']==0
        assert not item['numerical_rejection_demonstrated']
        p.validate_output_directory(path,source_reference)
    else:
        assert item['numerical_rejection_demonstrated']
        assert item['support_and_gaps']['n_exact_u2_changes']>0
        assert not item['actual_complete_verifier']['accepted']
        reject(path,source_reference)
