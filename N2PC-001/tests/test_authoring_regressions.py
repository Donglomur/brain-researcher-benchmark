"""Manufactured source-bound acceptance/rejection; no original data mounted."""
import csv
import json
import numpy as np
import pytest
import fixture_support as fs
import io_contract as io
import proof_of_work as proof


@pytest.fixture
def reference():return fs.manufactured()


def rewrite_csv(path,change):
    with path.open() as f:rows=list(csv.DictReader(f));names=list(rows[0])
    change(rows)
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=names);w.writeheader();w.writerows(rows)


def rewrite_json(path,change):
    value=json.loads(path.read_text());change(value);path.write_text(json.dumps(value))


def rewrite_npz(path,change):
    with np.load(path,allow_pickle=False) as f:a={k:f[k] for k in f.files}
    change(a)
    with path.open('wb') as f:np.savez_compressed(f,**a)


def test_genuine(reference,tmp_path):
    fs.write_output(tmp_path/'out',reference)
    assert proof.validate(tmp_path/'out',reference)['status']=='ok'


def test_coherent_all_axes_order(reference,tmp_path):
    p=tmp_path/'out';fs.write_output(p,reference)
    def change(a):
        for k in ('subject','source_event_index'):a[k]=a[k][::-1]
        a['channel_labels']=a['channel_labels'][::-1];a['sample_offsets']=a['sample_offsets'][::-1]
        a['epochs_uv']=a['epochs_uv'][::-1,::-1,::-1]
    rewrite_npz(p/'response_epochs.npz',change)
    for name in ('annotations.csv','trials.csv','per_subject.csv','waveforms.csv'):rewrite_csv(p/name,lambda r:r.reverse())
    def meta(m):
        for k in ('subjects','source_files','source_observed','processing_observed'):m[k].reverse()
        for r in m['processing_observed']:r['eeg_reference_channels'].reverse()
    rewrite_json(p/'run_metadata.json',meta);rewrite_json(p/'n2pc.json',lambda r:r['subjects'].reverse())
    assert proof.validate(p,reference)['status']=='ok'


def test_source_tolerance_own_sign(tmp_path):
    r=fs.manufactured(zero=True);x=r['epochs_uv'].copy()
    for j,row in enumerate(t for t in r['trials'] if t['retained']):
        x[j,1 if row['target_field']=='left' else 0,410:513]=-5e-7
    p=tmp_path/'out';fs.write_output(p,r,x)
    assert json.loads((p/'n2pc.json').read_text())['n_subjects_negative']==12
    assert proof.validate(p,r)['status']=='ok'


def test_empty_field_complete_cohort(tmp_path):
    r=fs.manufactured(empty_subject=8);p=tmp_path/'out';fs.write_output(p,r)
    own=json.loads((p/'n2pc.json').read_text());assert own['n_subjects']==12 and own['n2pc_amplitude_uv'] is None
    assert proof.validate(p,r)['status']=='ok'


def test_bom_extra_prose_and_float32(reference,tmp_path):
    p=tmp_path/'out';fs.write_output(p,reference,reference['epochs_uv'].astype(np.float32))
    for name in ('annotations.csv','trials.csv','per_subject.csv','waveforms.csv'):
        f=p/name;f.write_bytes(b'\xef\xbb\xbf'+f.read_bytes())
    rewrite_npz(p/'response_epochs.npz',lambda a:a.update(description=np.array(['alternate'])))
    rewrite_json(p/'n2pc.json',lambda v:v.update(extra=1.2));(p/'findings.md').write_text('Any nonempty explanation is accepted.')
    assert proof.validate(p,reference)['status']=='ok'


@pytest.mark.parametrize('name,column,value',[
 ('annotations.csv','latency_samples','999'),('annotations.csv','event_type_json','"111"'),
 ('annotations.csv','duration_status','finite'),('annotations.csv','urevent_json','2'),
 ('annotations.csv','is_bad','true'),('trials.csv','retained','false'),('trials.csv','target_field','right'),
 ('trials.csv','po7_baseline_uv','999'),('trials.csv','trial_contra_minus_ipsi_uv','999'),
 ('per_subject.csv','n2pc_uv','999'),('per_subject.csv','n_left_trials','1.5'),
 ('waveforms.csv','n2pc_uv','999'),('waveforms.csv','time_s','0')])
def test_table_corruption(reference,tmp_path,name,column,value):
    p=tmp_path/'out';fs.write_output(p,reference);rewrite_csv(p/name,lambda r:r[0].update({column:value}))
    with pytest.raises(ValueError):proof.validate(p,reference)


@pytest.mark.parametrize('name',['annotations.csv','trials.csv','per_subject.csv','waveforms.csv'])
@pytest.mark.parametrize('action',['duplicate','missing'])
def test_membership(reference,tmp_path,name,action):
    p=tmp_path/'out';fs.write_output(p,reference)
    rewrite_csv(p/name,lambda r:r.append(dict(r[0])) if action=='duplicate' else r.pop())
    with pytest.raises(ValueError):proof.validate(p,reference)


@pytest.mark.parametrize('key,value',[('status','resource_pilot'),('n_subjects','12'),('n_subjects',True),
 ('n2pc_amplitude_uv',999),('n_subjects_negative',999),('n_target_events_total',0),('field_weights',{'left':.4,'right':.6})])
def test_result_corruption(reference,tmp_path,key,value):
    p=tmp_path/'out';fs.write_output(p,reference);rewrite_json(p/'n2pc.json',lambda v:v.update({key:value}))
    with pytest.raises(ValueError):proof.validate(p,reference)


@pytest.mark.parametrize('section,key,value',[
 ('source_files','sha256','0'*64),('source_observed','source_bad_channels',[]),
 ('source_observed','source_units_json','uV'),('source_observed','n_samples','4096'),
 ('source_observed','event_type_counts',{}),('processing_observed','baseline_offsets',[-205,0]),
 ('processing_observed','filter_segments',[[0,4096]]),('processing_observed','drop_reason_counts',{})])
def test_metadata_corruption(reference,tmp_path,section,key,value):
    p=tmp_path/'out';fs.write_output(p,reference)
    rewrite_json(p/'run_metadata.json',lambda v:v[section][0].update({key:value}))
    with pytest.raises(ValueError):proof.validate(p,reference)


@pytest.mark.parametrize('mode',['values','keys','offset','channel','object','nonfinite','bool_axis','float_axis'])
def test_npz_corruption(reference,tmp_path,mode):
    p=tmp_path/'out';fs.write_output(p,reference)
    def mutate(a):
        if mode=='values':a['epochs_uv']+=1
        if mode=='keys':a['source_event_index'][0]=999
        if mode=='offset':a['sample_offsets'][0]=0
        if mode=='channel':a['channel_labels'][0]='FCz'
        if mode=='object':a['extra']=np.array([{}],dtype=object)
        if mode=='nonfinite':a['epochs_uv'][0,0,0]=np.nan
        if mode=='bool_axis':a['subject']=a['subject'].astype(bool)
        if mode=='float_axis':a['subject']=a['subject'].astype(float)
    rewrite_npz(p/'response_epochs.npz',mutate)
    with pytest.raises(ValueError):proof.validate(p,reference)


@pytest.mark.parametrize('kind',['empty','dangling'])
def test_failure_marker(reference,tmp_path,kind):
    p=tmp_path/'out';fs.write_output(p,reference);f=p/'failure_report.json'
    if kind=='empty':f.touch()
    else:f.symlink_to(tmp_path/'absent')
    with pytest.raises(ValueError,match='failed_run'):proof.validate(p,reference)


def test_no_derived_secondary_reference_gate(tmp_path):
    r=fs.manufactured(zero=True);x=r['epochs_uv'].copy();x[:,0,:]=5e-7
    p=tmp_path/'out';fs.write_output(p,r,x)
    assert proof.validate(p,r)['status']=='ok'
    rewrite_csv(p/'trials.csv',lambda rows:rows[0].update(po7_baseline_uv='0'))
    with pytest.raises(ValueError):proof.validate(p,r)


@pytest.mark.parametrize('reported',[-5e-12,0.0,5e-12])
def test_accepted_nearzero_person_sign_count(tmp_path,reported):
    r=fs.manufactured(zero=True);p=tmp_path/'out';fs.write_output(p,r)
    rewrite_csv(p/'per_subject.csv',lambda rows:[v.update(n2pc_uv=str(reported)) for v in rows])
    count=12 if reported<0 else 0
    rewrite_json(p/'n2pc.json',lambda v:v.update(n_subjects_negative=count))
    assert proof.validate(p,r)['status']=='ok'
    rewrite_json(p/'n2pc.json',lambda v:v.update(n_subjects_negative=1))
    with pytest.raises(ValueError):proof.validate(p,r)


@pytest.mark.parametrize('raw',[b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":1e999}'])
def test_strict_json(raw):
    with pytest.raises(ValueError):io.json_bytes(raw)


def test_csv_decimal_integer_and_bool():
    assert io.integer('1e1')==10 and io.boolean('TRUE')
    for bad in ('1.1','nan',True,'inf'):
        with pytest.raises(ValueError):io.integer(bad)


def test_fresh_writer_preserves(reference,tmp_path):
    p=tmp_path/'out';fs.write_output(p,reference);before=(p/'n2pc.json').read_bytes()
    with pytest.raises(ValueError):fs.write_output(p,reference)
    assert (p/'n2pc.json').read_bytes()==before
