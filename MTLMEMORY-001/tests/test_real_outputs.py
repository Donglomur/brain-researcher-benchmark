"""Genuine source-output positives and mutations; no synthetic scientific bank.
Every mutation uses a disposable copy deleted after its test; originals are read-only.
"""
from contextlib import contextmanager
import copy
import csv
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
from zipfile import BadZipFile
import numpy as np
import pytest
import population_contract as q
from proof_of_work import load_reference
from fixture_support import emit,write_csv


def required_env(name):
    value=os.environ.get(name)
    if value is None: pytest.skip('Genuine original-source artifact not supplied: '+name)
    p=Path(value);assert p.is_dir(), 'Supplied genuine path is missing: '+name
    return p


@pytest.fixture(scope='module')
def original(): return required_env('REPAIR_ORACLE_OUTPUT')


@pytest.fixture(scope='module')
def reference(original):
    return load_reference(os.environ.get('REPAIR_REFERENCE_PATH',str(Path(__file__).with_name('reference.npz'))))


@contextmanager
def copied(original):
    with tempfile.TemporaryDirectory(prefix='mtl-receipt-') as temp:
        p=Path(temp)/'output';shutil.copytree(original,p);yield p


@pytest.fixture
def output(original):
    with copied(original) as p: yield p


def read_csv(p):
    with p.open(newline='') as stream:
        r=csv.DictReader(stream);return list(r.fieldnames),list(r)


def save_csv(p,fields,rows):
    with p.open('w',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(rows)


def arrays(p):
    with np.load(p/'trial_counts.npz',allow_pickle=False) as z:return {k:np.array(z[k]) for k in z.files}


def save_arrays(p,a): np.savez_compressed(p/'trial_counts.npz',**a)


def change_json(p,name,fn):
    data=q.json_load(p/name);fn(data);(p/name).write_text(json.dumps(data,allow_nan=False))


def reject(p,ref,match=None):
    with pytest.raises((AssertionError,ValueError,KeyError,TypeError,EOFError,BadZipFile),match=match):
        q.validate_output_directory(p,ref)


def test_genuine_original(original,reference): q.validate_output_directory(original,reference)


def test_genuine_independent(reference): q.validate_output_directory(required_env('REPAIR_INDEPENDENT_OUTPUT'),reference)


def test_other_declared_headline(output,reference):
    result=q.json_load(output/'results.json');head=q.POPULATIONS[0] if result['headline_population']==q.POPULATIONS[1] else q.POPULATIONS[1]
    result.update(headline_population=head,headline_status=result['populations'][head]['status'],memory_selective_new_old_auc=result['populations'][head]['mean_auc'])
    (output/'results.json').write_text(json.dumps(result));change_json(output,'run_metadata.json',lambda d:d.update(headline_population=head))
    q.validate_output_directory(output,reference)


def test_all_axis_and_table_reordering(output,reference):
    rng=np.random.default_rng(51)
    for name in q.TABLE_KEYS:
        fields,rows=read_csv(output/name);rng.shuffle(rows);fields=fields[::-1]+['ungraded_note']
        for row in rows:row['ungraded_note']='independent serialization'
        save_csv(output/name,fields,rows)
    a=arrays(output);u=rng.permutation(len(a['unit_key']));r=rng.permutation(len(a['spike_count']));b=rng.permutation(60)
    inverse=np.empty(len(u),dtype=np.int64);inverse[u]=np.arange(len(u));a['unit_key']=a['unit_key'][u]
    a['response_unit_index']=inverse[a['response_unit_index']]
    for key in q.ARRAY_FIELDS[1:7]:a[key]=a[key][r]
    a['repeat_id']=a['repeat_id'][b];a['train_membership']=a['train_membership'][np.ix_(b,r)]
    save_arrays(output,a)
    change_json(output,'run_metadata.json',lambda d:d['source_observed']['sessions'].reverse())
    q.validate_output_directory(output,reference)


def test_rounding_and_integral_notation(output,reference):
    for name in q.TABLE_KEYS:
        spec=reference['metadata']['method_contract']['outputs'][name];fields,rows=read_csv(output/name)
        for row in rows:
            for key,value in row.items():
                if not value:continue
                kind=spec['types'][key]
                if 'integer' in kind:row[key]=str(q.integer(value))+'.000e0'
                elif 'probability' in kind:row[key]=format(float(value),'.12g')
                elif 'boolean' in kind:row[key]='true' if q.flag(value) else 'FALSE'
        save_csv(output/name,fields,rows)
    q.validate_output_directory(output,reference)


def test_actual_versions_free_prose_extra_fields(output,reference):
    def alter(d):
        d['software_versions']={'alternate_math':'1.0','runtime':'actual reported version'}
        d['descriptive_note']={'not_a_statistic':'any wording'}
        d['source_observed']['sessions'][0]['comment']='additional harmless source note'
    change_json(output,'run_metadata.json',alter)
    change_json(output,'results.json',lambda d:d.update(optional_analysis={'ungraded':[2,1,0]}))
    (output/'findings.md').write_text('These numbers are the requested descriptive calculation.\n')
    (output/'analysis_arrays.npz').write_bytes(b'ignored optional authoring evidence')
    q.validate_output_directory(output,reference)


def test_public_template_identity(reference):
    path=Path(__file__).resolve().parents[1]/'environment/method_contract.json'
    q.match(json.loads(path.read_text()),reference['metadata']['method_contract'],closed=True,kind='exact')


@pytest.mark.parametrize('name',list(q.TABLE_KEYS)+['trial_counts.npz','results.json','run_metadata.json','findings.md'])
@pytest.mark.parametrize('mode',['missing','empty'])
def test_required_artifacts(output,reference,name,mode):
    if mode=='missing':(output/name).unlink()
    else:(output/name).write_bytes(b'')
    reject(output,reference)


@pytest.mark.parametrize('name',list(q.TABLE_KEYS))
@pytest.mark.parametrize('mode',['drop','duplicate','missing_column','duplicate_header'])
def test_complete_csv_identity(output,reference,name,mode):
    fields,rows=read_csv(output/name)
    if mode=='drop':rows.pop()
    elif mode=='duplicate':rows.append(rows[0].copy())
    elif mode=='missing_column':
        removed=fields.pop();[r.pop(removed) for r in rows]
    else:fields.append(fields[0])
    save_csv(output/name,fields,rows);reject(output,reference)


@pytest.mark.parametrize('field',['spike_count','source_label','trial_id','source_trial_row','response_unit_index','repeat_id'])
def test_wrong_npz_integer_fields(output,reference,field):
    a=arrays(output);a[field][0]+=1;save_arrays(output,a);reject(output,reference)


@pytest.mark.parametrize('mode',['mask_bit','mask_integer','count_boolean','count_fractional','uint_overflow','rate_nan','wrong_duration','unit_alias','unit_duplicate','object','drop_response'])
def test_npz_semantics(output,reference,mode):
    a=arrays(output)
    if mode=='mask_bit':a['train_membership'][0,0]=not a['train_membership'][0,0]
    elif mode=='mask_integer':a['train_membership']=a['train_membership'].astype(np.int8)
    elif mode=='count_boolean':a['spike_count']=a['spike_count'].astype(bool)
    elif mode=='count_fractional':a['spike_count']=a['spike_count'].astype(float);a['spike_count'][0]+=.5
    elif mode=='uint_overflow':a['spike_count']=a['spike_count'].astype(np.uint64);a['spike_count'][0]=np.iinfo(np.uint64).max
    elif mode=='rate_nan':a['rate_hz'][0]=np.nan
    elif mode=='wrong_duration':a['rate_hz']=a['spike_count']/1.
    elif mode=='unit_alias':a['unit_key']=np.array([str(x)+'-alias' for x in a['unit_key']])
    elif mode=='unit_duplicate':a['unit_key'][1]=a['unit_key'][0]
    elif mode=='object':a['unit_key']=a['unit_key'].astype(object)
    else:
        for k in q.ARRAY_FIELDS[1:7]:a[k]=a[k][:-1]
        a['train_membership']=a['train_membership'][:,:-1]
    save_arrays(output,a);reject(output,reference)


@pytest.mark.parametrize('name,field',[
    ('trials.csv','source_label_token'),('trials.csv','external_image_file'),('trials.csv','image_in_learning'),
    ('trials.csv','stim_on_time_s'),('trials.csv','stim_off_time_s'),('trials.csv','stop_time_s'),
    ('units.csv','electrode_id'),('units.csv','electrode_row'),('units.csv','original_channel'),('units.csv','region'),
    ('sessions.csv','n_recognition_trials'),('sessions.csv','subject_id'),('sessions.csv','literal_session_id')])
def test_source_ledger_bindings(output,reference,name,field):
    fields,rows=read_csv(output/name);row=next(r for r in rows if r[field] or field=='literal_session_id')
    kind=reference['metadata']['method_contract']['outputs'][name]['types'][field]
    if 'boolean' in kind:row[field]='0' if q.flag(row[field]) else '1'
    elif 'integer' in kind:row[field]=str(q.integer(row[field])+1)
    elif kind=='finite_float':row[field]=str(float(row[field])+.01)
    else:row[field]='invented_'+row[field]
    save_csv(output/name,fields,rows);reject(output,reference)


@pytest.mark.parametrize('name,field',[
    ('split_events.csv','train_p'),('split_events.csv','train_auc_old'),('split_events.csv','test_auc_old'),
    ('split_events.csv','test_directed_auc'),('split_events.csv','train_u_old_twice'),('split_events.csv','train_preferred_sign'),
    ('split_events.csv','train_selected'),('split_events.csv','included_in_conditional_summary'),
    ('neurons.csv','full_p'),('neurons.csv','auc_old'),('neurons.csv','same_trial_auc'),('neurons.csv','conditional_auc'),
    ('neurons.csv','memory_selective'),('neurons.csv','n_selected_splits'),('neurons.csv','heldout_eligible')])
def test_every_statistical_receipt_bound(output,reference,name,field):
    fields,rows=read_csv(output/name);row=next(r for r in rows if r[field]!='')
    kind=reference['metadata']['method_contract']['outputs'][name]['types'][field]
    if 'boolean' in kind:row[field]='0' if q.flag(row[field]) else '1'
    elif 'integer' in kind:row[field]=str(q.integer(row[field])+1)
    else:row[field]=str(.2 if float(row[field])>.5 else .8)
    save_csv(output/name,fields,rows);reject(output,reference)


@pytest.mark.parametrize('mode',['source_hash','method_hash','method_bool','source_extra','missing_versions','pilot','missing_metadata_key',
    'old_history_missing','unordered_forced_zero','duplicates_forced_zero','unknown_continuity','phase_id','wrong_headline',
    'learning_timing_forced_zero','recognition_timing_invented'])
def test_metadata_binding(output,reference,mode):
    d=q.json_load(output/'run_metadata.json');rows=d['source_observed']['sessions']
    if mode=='source_hash':d['source_sha256'][next(iter(d['source_sha256']))]='0'*64
    elif mode=='method_hash':d['method_contract_sha256']='0'*64
    elif mode=='method_bool':d['method_contract']['rank_statistics']['scipy_equivalent']['use_continuity']=1
    elif mode=='source_extra':d['source_sha256']['invented.nwb']='0'*64
    elif mode=='missing_versions':d.pop('software_versions')
    elif mode=='pilot':d['status']='resource_pilot'
    elif mode=='missing_metadata_key':d.pop('source_manifest_sha256')
    elif mode=='old_history_missing':next(r for r in rows if r['label_membership_counts']['code1_absent_from_learning']>0)['label_membership_counts']['code1_absent_from_learning']=0
    elif mode=='unordered_forced_zero':next(r for r in rows if r['n_unordered_units']>0).update(n_unordered_units=0,all_unit_spikes_nondecreasing=True,raw_adjacent_inversions=0)
    elif mode=='duplicates_forced_zero':next(r for r in rows if r['duplicate_timestamp_occurrences']>0)['duplicate_timestamp_occurrences']=0
    elif mode=='unknown_continuity':rows[0]['observation_coverage']='continuous'
    elif mode=='phase_id':rows[0]['phase_experiment_ids']['recog']+=1
    elif mode=='learning_timing_forced_zero':next(r for r in rows if r['n_learning_temporal_order_violations']>0)['n_learning_temporal_order_violations']=0
    elif mode=='recognition_timing_invented':rows[0]['n_recognition_temporal_order_violations']=1
    else:d['headline_population']='invented'
    (output/'run_metadata.json').write_text(json.dumps(d));reject(output,reference)


@pytest.mark.parametrize('mode',['headline','proportion','n_units','bool_count','population_missing','population_extra','overlap','missing_null','null_chance'])
def test_wrong_population_summary(output,reference,mode):
    d=q.json_load(output/'results.json')
    if mode=='headline':d['memory_selective_new_old_auc']=.123456
    elif mode=='proportion':d['proportion_memory_selective']=.123456
    elif mode=='n_units':d['n_mtl_units']+=1
    elif mode=='bool_count':d['n_sessions']=True
    elif mode=='population_missing':d['populations'].pop(q.POPULATIONS[0])
    elif mode=='population_extra':d['populations']['invented']=copy.deepcopy(d['populations'][q.POPULATIONS[0]])
    elif mode=='overlap':d['population_overlap']['both']+=1
    elif mode=='missing_null':d.pop('headline_status')
    else:d['populations'][q.POPULATIONS[0]].update(n_units=0,mean_auc=.5,status='empty_population')
    (output/'results.json').write_text(json.dumps(d));reject(output,reference)


@pytest.mark.parametrize('mode',['rank_preserving_count_shift','labels_complemented','per_unit_rng_reset','swap_unit_counts'])
def test_coherent_wrong_primitives(output,reference,mode):
    fake={k:(np.array(v) if isinstance(v,np.ndarray) else copy.deepcopy(v)) for k,v in reference.items() if not k.startswith('_')}
    if mode=='rank_preserving_count_shift':fake['spike_count']+=1
    elif mode=='labels_complemented':
        fake['source_label']=1-fake['source_label']
        for r in fake['trials']:
            if r['included']:r['source_label']=1-r['source_label'];r['source_label_token']=str(r['source_label'])
        fake['train_membership']=q.generate_masks(fake)
    elif mode=='per_unit_rng_reset':
        for i in range(len(fake['unit_key'])):
            idx=np.flatnonzero(fake['response_unit_index']==i); local=dict(unit_key=fake['unit_key'][i:i+1],response_unit_index=np.zeros(len(idx),dtype=int),source_label=fake['source_label'][idx])
            fake['train_membership'][:,idx]=q.generate_masks(local)
    else:
        a=np.flatnonzero(fake['response_unit_index']==0);b=np.flatnonzero(fake['response_unit_index']==1)
        assert len(a)==len(b)
        fake['spike_count'][a],fake['spike_count'][b]=fake['spike_count'][b].copy(),fake['spike_count'][a].copy()
    fake['rate_hz']=fake['spike_count']/1.5;emit(output,fake)
    reject(output,reference)


def test_heldout_folding_with_coherent_means(output,reference):
    spec=reference['metadata']['method_contract']['outputs'];events=q.csv_load(output/'split_events.csv',spec['split_events.csv'])
    changed=0
    for r in events:
        if r['test_directed_auc'] is not None and r['test_directed_auc']<.5:
            r['test_directed_auc']=1-r['test_directed_auc'];changed+=1
    assert changed>0
    neurons=q.csv_load(output/'neurons.csv',spec['neurons.csv']);sums={}
    for r in events:
        if r['train_selected']:sums.setdefault(r['unit_key'],[]).append(r['test_directed_auc'])
    for r in neurons:
        values=sums.get(r['unit_key'],[]);r['conditional_auc']=math.fsum(values)/len(values) if values else None
    write_csv(output/'split_events.csv',events,spec['split_events.csv']['columns']);write_csv(output/'neurons.csv',neurons,spec['neurons.csv']['columns'])
    result=q.summarize(reference,neurons,q.json_load(output/'results.json')['headline_population']);(output/'results.json').write_text(json.dumps(result))
    reject(output,reference,match='test_directed_auc')


def test_genuine_unsorted_search_control(reference):
    """Actual source-only wrong algorithm, not a fabricated or metadata-only arm."""
    control=required_env('REPAIR_WRONG_UNSORTED_OUTPUT')
    results=q.json_load(control/'results.json')
    assert results['status']=='complete'
    q.validate_metadata(q.json_load(control/'run_metadata.json'),reference,results['headline_population'])
    reject(control,reference,match='spike_count differs from original source')
