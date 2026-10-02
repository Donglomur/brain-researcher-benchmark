"""Manufactured-only source/MNE/epoch tests; no original inputs or endpoints."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys

import numpy as np
import pytest
from scipy.io import savemat

HERE=Path(__file__).resolve().parents[1]/'solution'
for name in ('mat_metadata','oracle_source'):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
m=sys.modules['oracle_source']
CHANNELS=['FP1','F3','F7','FC3','C3','C5','P3','P7','P9','PO7','PO3','O1','Oz','Pz','CPz',
          'FP2','Fz','F4','F8','FC4','FCz','Cz','C4','C6','P4','P8','P10','PO8','PO4','O2',
          'HEOG_left','HEOG_right','VEOG_lower']


def method():
    return dict(subjects=list(m.SUBJECTS),source=dict(n_channels=33,n_trials=1,sfreq_hz=256,xmin=0,
        channel_labels=CHANNELS,reference_token='common',units='EEGLAB microvolt convention'),
        reference={'channels':CHANNELS[:30]},filter=dict(low_hz=.1,high_hz=30,low_transition_hz=.1,high_transition_hz=7.5),
        epoch=dict(sample_offsets_inclusive=[-51,102],baseline_offsets_inclusive=[-51,0],ptp_threshold_uv=150,
            rejection_reason_precedence=['out_of_bounds','duplicate_target_sample','crosses_boundary','peak_to_peak','accepted']),
        measurement={'electrode':'PO8'})


def eeg_struct(subject=2,n=512,events=None,**overrides):
    if events is None:events=[dict(type=1,latency=121.,duration=0.,urevent=1),dict(type=41,latency=301.,duration=0.,urevent=2)]
    eeg=dict(data=f'{subject}_N170_shifted_ds.fdt',nbchan=33,pnts=n,trials=1,srate=256.,xmin=0.,xmax=(n-1)/256,
        ref='common',history='manufactured fixture',chanlocs=np.array([{'labels':v} for v in CHANNELS],dtype=object),
        event=np.array(events,dtype=object),urevent=np.array(events,dtype=object),icaweights=np.zeros((0,0)))
    eeg.update(overrides);return eeg


def set_bytes(eeg):
    out=io.BytesIO();savemat(out,{'EEG':eeg},do_compression=True);return out.getvalue()


def member(root,subject,role,raw):
    name=f'{subject}_N170_shifted_ds.{role}';(root/name).write_bytes(raw)
    return dict(subject=subject,role=role,path=name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),md5=hashlib.md5(raw).hexdigest())


def pair(tmp_path,**overrides):
    root=tmp_path/'data';root.mkdir();n=512
    data=np.arange(33*n,dtype=np.float32).reshape(33,n,order='F')/100
    data[30:]=np.nan
    rows=[member(root,2,'set',set_bytes(eeg_struct(**overrides))),member(root,2,'fdt',data.astype('<f4').tobytes(order='F'))]
    return dict(root=root,method=method(),by_key={(str(r['subject']),r['role']):r for r in rows}),data


def full_bundle(tmp_path,monkeypatch):
    root=tmp_path/'data';root.mkdir();rows=[]
    for s in m.SUBJECTS:
        rows.extend([member(root,int(s),'set',set_bytes(eeg_struct(int(s)))),
                     member(root,int(s),'fdt',np.zeros((33,512),dtype='<f4').tobytes())])
    manifest=dict(subjects=[int(s) for s in m.SUBJECTS],files=rows)
    docs={'source_manifest.json':manifest,'method.json':method(),'schema.json':{'task_id':'N170PROFILE-001'}}
    for name,doc in docs.items():(tmp_path/name).write_text(json.dumps(doc))
    (root/'source_manifest.json').write_bytes((tmp_path/'source_manifest.json').read_bytes())
    for name,const in [('source_manifest.json','SOURCE_SHA256'),('method.json','METHOD_SHA256'),('schema.json','SCHEMA_SHA256')]:
        monkeypatch.setattr(m,const,hashlib.sha256((tmp_path/name).read_bytes()).hexdigest())
    monkeypatch.setattr(m,'SOURCE_BYTES',sum(r['size_bytes'] for r in rows))
    return root,tmp_path/'source_manifest.json',tmp_path/'method.json',tmp_path/'schema.json'


@pytest.mark.parametrize('value,code',[(1,1),(80.,80),(' +41 ',41),('-99',-99),('1.0',None),('face1',None),(True,None),(np.nan,None),(None,None)])
def test_code_tokens(value,code):assert m.normalized_code(value)==code


def test_documentary_preserves_nonfinite_without_json_nan():
    actual=m.documentary({'a':np.nan,'b':np.inf,'c':-np.inf,'d':np.array([1,2]),'e':np.array([])})
    assert actual=={'a':{'__nonfinite__':'NaN'},'b':{'__nonfinite__':'Infinity'},'c':{'__nonfinite__':'-Infinity'},'d':[1,2],'e':None}
    json.dumps(actual,allow_nan=False)


def test_clock_duplicate_and_precedence():
    events=[{'type':1,'latency':121.5},{'type':2,'latency':121.5},{'type':41,'latency':122.5},
            {'type':3,'latency':1.},{'type':4,'latency':1.},{'type':'other','latency':{'__nonfinite__':'NaN'}}]
    annotations,trials,segments,_,_=m.event_plan('2',events,512,method())
    assert [r['event_sample'] for r in trials]==[120,120,122,0,0]
    assert [r['rejection_reason'] for r in trials]==['duplicate_target_sample','duplicate_target_sample','accepted','out_of_bounds','out_of_bounds']
    assert len(annotations)==6 and segments==[(0,512)]


def test_boundaries_split_not_duration_exclusion():
    events=[{'type':' Boundary ','latency':201.2,'duration':1000}, {'type':-99,'latency':201.2},
            {'type':1,'latency':160},{'type':41,'latency':300},{'type':'BAD_noise','latency':400}]
    annotations,trials,segments,bounds,cuts=m.event_plan('2',events,512,method())
    assert cuts==[0,201,512] and segments==[(0,201),(201,512)] and bounds==[0,1]
    assert trials[0]['rejection_reason']=='crosses_boundary' and trials[1]['rejection_reason']=='accepted'
    assert annotations[-1]['event_role']=='other'


@pytest.mark.parametrize('event',[{'type':1,'latency':np.nan},{'type':41,'latency':'121'},
    {'type':'boundary','latency':None},{'type':-99,'latency':-1},{'type':-99,'latency':1000}])
def test_invalid_target_or_boundary_latency(event):
    with pytest.raises(ValueError):m.event_plan('2',[m.documentary(event)],512,method())


def test_metadata_external_pointer_before_other_decoding(tmp_path,monkeypatch):
    inputs,_=pair(tmp_path,data='wrong.fdt')
    original=m.MatScan.decode;calls=[]
    def guarded(self,node):calls.append(node['matlab_class']);return original(self,node)
    monkeypatch.setattr(m.MatScan,'decode',guarded)
    with pytest.raises(ValueError,match='literal_fdt_pointer'):m.read_metadata(inputs,'2')
    assert calls==[4]


def test_metadata_inline_eeg_never_decoded(tmp_path,monkeypatch):
    inputs,_=pair(tmp_path,data=np.zeros((33,512)))
    monkeypatch.setattr(m.MatScan,'decode',lambda *a:pytest.fail('no selected decoder before pointer guard'))
    with pytest.raises(ValueError,match='external_data_pointer_required'):m.read_metadata(inputs,'2')


@pytest.mark.parametrize('overrides,reason',[({'srate':128},'source_header_srate'),({'ref':'average'},'source_reference'),
    ({'unit':'uV'},'source_units_fields'),({'icaweights':np.ones((1,1))},'source_ica_not_empty'),
    ({'pnts':511},'fdt_byte_equation')])
def test_metadata_preconditions(tmp_path,overrides,reason):
    inputs,_=pair(tmp_path,**overrides)
    with pytest.raises(ValueError,match=reason):m.read_metadata(inputs,'2')


def test_metadata_exact_shapes_and_original_fields(tmp_path):
    inputs,_=pair(tmp_path);meta=m.read_metadata(inputs,'2');obs=meta['observed']
    assert meta['n_samples']==512 and len(meta['annotations'])==2
    assert obs['literal_data_pointer']=='2_N170_shifted_ds.fdt' and obs['header_fields']['history']=='manufactured fixture'
    assert obs['channel_labels']==CHANNELS and obs['boundary_cut_samples']==[0,512]
    assert obs['ica_field_shapes']['icaweights']==[0,0]


def test_all_74_authentication_precedes_any_set_parse(tmp_path,monkeypatch):
    args=full_bundle(tmp_path,monkeypatch);(args[0]/'40_N170_shifted_ds.fdt').write_bytes(b'wrong')
    monkeypatch.setattr(m,'read_metadata',lambda *a:pytest.fail('all-source authentication must precede parsing'))
    with pytest.raises(ValueError,match='source_size'):m.reconstruct(*args,pilot=True)


@pytest.mark.parametrize('mutation',['extra','symlink','internal_manifest','method_pin','same_size_hash'])
def test_source_bundle_failure(tmp_path,monkeypatch,mutation):
    args=full_bundle(tmp_path,monkeypatch)
    if mutation=='extra':(args[0]/'extra').write_bytes(b'')
    elif mutation=='symlink':(args[0]/'extra').symlink_to(args[0]/'2_N170_shifted_ds.set')
    elif mutation=='internal_manifest':(args[0]/'source_manifest.json').write_text('{}')
    elif mutation=='method_pin':args[2].write_text('{}')
    else:
        p=args[0]/'2_N170_shifted_ds.fdt';raw=p.read_bytes();p.write_bytes(b'1'+raw[1:])
    with pytest.raises(ValueError):m.load_inputs(*args)


def test_mne_actual_manufactured_pair_layout_scaling_and_excluded_eog(tmp_path):
    inputs,expected=pair(tmp_path);meta=m.read_metadata(inputs,'2');warnings=[]
    observed=m.read_mne_uv(inputs,meta,warnings)
    np.testing.assert_allclose(observed,expected[:30].astype(np.float64),rtol=2e-15,atol=1e-12)
    assert observed.dtype==np.float64 and np.isfinite(observed).all()
    assert all(set(w)=={'subject_id','stage','category','message'} for w in warnings)


def test_private_copies_not_source_paths_and_mutation_fails(tmp_path,monkeypatch):
    import mne
    inputs,_=pair(tmp_path);meta=m.read_metadata(inputs,'2');paths=[]
    class FakeRaw:
        ch_names=CHANNELS;n_times=512;info={'sfreq':256};first_samp=0
        def get_data(self,picks):
            assert picks==CHANNELS[:30]
            p=paths[0].with_suffix('.fdt');raw=p.read_bytes();p.write_bytes(b'1'+raw[1:])
            return np.zeros((30,512),dtype=np.float64)
        def close(self):pass
    def reader(path,**kwargs):
        paths.append(Path(path));assert Path(path).parent!=inputs['root'];return FakeRaw()
    monkeypatch.setattr(mne.io,'read_raw_eeglab',reader)
    with pytest.raises(ValueError,match='source_sha256'):m.read_mne_uv(inputs,meta,[])
    assert not paths[0].parent.exists()


def test_filter_parameters_reference_order_segments_and_input_immutable(monkeypatch):
    import mne
    raw=np.arange(30*8,dtype=float).reshape(30,8);before=raw.copy();calls=[]
    def identity(piece,**kwargs):calls.append((piece.copy(),kwargs));return piece
    monkeypatch.setattr(mne.filter,'filter_data',identity)
    result=m.filter_reference(raw,[(0,3),(3,8)],method(),'2',[])
    np.testing.assert_array_equal(raw,before);np.testing.assert_array_equal(result,raw-np.mean(raw,axis=0,keepdims=True))
    assert [x.shape[1] for x,_ in calls]==[3,5]
    for _,kw in calls:
        assert kw['sfreq']==256 and kw['l_freq']==.1 and kw['h_freq']==30
        assert kw['filter_length']=='auto' and kw['l_trans_bandwidth']==.1 and kw['h_trans_bandwidth']==7.5
        assert kw['phase']=='zero' and kw['fir_design']=='firwin' and kw['fir_window']=='hamming' and kw['pad']=='reflect_limited'
        assert kw['n_jobs']==1 and kw['method']=='fir' and kw['copy'] is True


def test_filter_actual_mne_manufactured_segment_and_warning_capture():
    raw=np.zeros((30,20));raw[0,5]=1
    warnings=[];out=m.filter_reference(raw,[(0,20)],method(),'2',warnings)
    assert out.shape==raw.shape and np.isfinite(out).all()
    assert any('filter_length' in w['message'] for w in warnings)


def trial_meta(events,n=512):
    ann,targets,segments,_,_=m.event_plan('2',events,n,method())
    return dict(subject='2',n_samples=n,targets=targets,segments=segments,annotations=ann)


@pytest.mark.parametrize('peak,accepted',[(150.,True),(150.000001,False)])
def test_ptp_boundary_and_artifact_receipts(peak,accepted):
    meta=trial_meta([{'type':1,'latency':121}]);data=np.zeros((30,512));data[0,150]=peak
    result=m.summarize_epochs(data,meta,method())
    assert result['trials'][0]['accepted'] is accepted
    assert result['epoch_keys']==[('2',0)] and result['epoch_peak_to_peak_uv'][0,0]==peak
    assert result['condition_defined'].tolist()==[accepted,False]
    assert np.array_equal(result['evoked_po8_uv'][1],np.zeros(154))


def test_epoch_baseline_full_channel_rejection_and_condition_mean_order():
    events=[{'type':1,'latency':301},{'type':1,'latency':121},{'type':41,'latency':700}]
    meta=trial_meta(events,n=900);data=np.zeros((30,900));po8=CHANNELS.index('PO8')
    data[po8]=np.sin(np.arange(900)/30)*5+10
    result=m.summarize_epochs(data,meta,method());offsets=np.arange(-51,103)
    epochs=np.array([data[po8,300+offsets],data[po8,120+offsets]])
    expected=(epochs-epochs[:,:52].mean(axis=1,keepdims=True)).mean(axis=0)
    np.testing.assert_allclose(result['evoked_po8_uv'][0],expected,rtol=0,atol=1e-14)
    assert result['epoch_keys']==[('2',0),('2',1),('2',2)]
    assert result['analysis_observed']['n_face_accepted']==2
    assert set(result['analysis_observed']['rejection_counts'])==set(method()['epoch']['rejection_reason_precedence'])


def test_no_eligible_trials_preserves_false_masks_and_empty_receipts():
    meta=trial_meta([{'type':1,'latency':1}]);result=m.summarize_epochs(np.zeros((30,512)),meta,method())
    assert result['epoch_peak_to_peak_uv'].shape==(0,30) and result['epoch_po8_baseline_uv'].shape==(0,)
    assert not result['condition_defined'].any() and not result['evoked_po8_uv'].any()
    assert result['analysis_observed']['n_face_rejected']==1


def test_pilot_authenticates_all_and_only_decodes_subject2(tmp_path,monkeypatch):
    args=full_bundle(tmp_path,monkeypatch);decoded=[]
    def load(inputs,meta,warnings):decoded.append(meta['subject']);return np.zeros((30,512))
    monkeypatch.setattr(m,'read_mne_uv',load)
    monkeypatch.setattr(m,'filter_reference',lambda data,*a:data)
    result=m.reconstruct(*args,pilot=True)
    assert result['status']=='resource_pilot' and result['subjects']==['2'] and decoded==['2']
    assert len(result['source_files'])==74 and len(result['annotations'])==74 and len(result['trials'])==2
    assert len(result['source_observed']['persons'])==37 and len(result['analysis_observed']['persons'])==1
    assert result['condition_defined'].shape==(1,2) and result['evoked_po8_uv'].shape==(1,2,154)
    assert set(result['pins'])=={'source_manifest_sha256','method_contract_sha256','output_schema_sha256'}
    assert not any(k in result for k in ('amp_po8_uv','onset_ms','n170','amplitude_summary','onset_summary'))


def test_mne_input_source_digest_rechecked_before_private_copy(tmp_path):
    inputs,_=pair(tmp_path);meta=m.read_metadata(inputs,'2');p=inputs['root']/'2_N170_shifted_ds.fdt'
    raw=p.read_bytes();p.write_bytes(b'1'+raw[1:])
    with pytest.raises(ValueError,match='source_sha256'):m.read_mne_uv(inputs,meta,[])


def test_temporary_source_overlap_refused_without_writes(tmp_path,monkeypatch):
    inputs,_=pair(tmp_path);meta=m.read_metadata(inputs,'2');before=set(inputs['root'].iterdir())
    monkeypatch.setattr(m.tempfile,'gettempdir',lambda:str(inputs['root']))
    with pytest.raises(ValueError,match='temporary_source_or_code_overlap'):m.read_mne_uv(inputs,meta,[])
    assert set(inputs['root'].iterdir())==before


def test_safe_path_and_json_guards(tmp_path):
    p=tmp_path/'link';p.symlink_to(tmp_path/'missing')
    for value in (str(p),str(p)+'/../x','relative'):
        with pytest.raises(ValueError):m.safe_path(value)
    for raw in (b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":1e999}'):
        with pytest.raises(ValueError):m.strict_json(raw)
