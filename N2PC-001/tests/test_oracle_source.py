"""Manufactured source authentication and oracle IO tests; no original data."""
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.io import savemat

from test_oracle_core import SOLUTION,contract,manufactured
import compute
import core
import source_reader as s
import set_metadata as matmeta

def write_json(path,obj):
    raw=(json.dumps(obj,allow_nan=False)+'\n').encode();path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()

def bundle(tmp_path,monkeypatch,contract):
    root=tmp_path/'source';root.mkdir();rows=[]
    n=2000;raw=np.repeat(np.arange(1,34,dtype='<f4')[:,None],n,axis=1)
    raw[30:]=np.nan
    for subject in s.SUBJECTS:
        base=f'sub-{subject:03d}_task-N2pc_eeg'
        fields=dict(data=base+'.fdt',nbchan=33,pnts=n,trials=1,srate=1024,xmin=0,xmax=(n-1)/1024,
                    ref='common',history='literal history',
                    chanlocs=[dict(labels=label) for label in contract['source']['channel_labels']],
                    event=[dict(type=111,latency=801,urevent=1),dict(type=121,latency=1501,urevent=2)])
        buf=io.BytesIO();savemat(buf,dict(EEG=fields))
        for role,payload in (('set',buf.getvalue()),('fdt',raw.tobytes(order='F'))):
            name=base+'.'+role;(root/name).write_bytes(payload)
            rows.append(dict(subject=subject,role=role,path=name,size_bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest(),
                             md5=hashlib.md5(payload).hexdigest(),object_id=f'{len(rows):024x}',version=1))
    manifest=dict(subjects=list(s.SUBJECTS),files=rows)
    monkeypatch.setattr(s,'SOURCE_SHA256',write_json(root/'source_manifest.json',manifest))
    (root/'SOURCE_NOTICE.md').write_text('manufactured notice')
    monkeypatch.setattr(s,'NOTICE_SHA256',hashlib.sha256((root/'SOURCE_NOTICE.md').read_bytes()).hexdigest())
    method=tmp_path/'method.json';monkeypatch.setattr(s,'METHOD_SHA256',write_json(method,contract))
    return root,method,manifest

def test_authenticate_then_real_mne_manufactured_read(tmp_path,monkeypatch,contract):
    root,method,_=bundle(tmp_path,monkeypatch,contract)
    inputs=s.load_inputs(root,method);metadata=s.read_metadata(inputs,1);warnings=[]
    eeg=s.load_mne_eeg(inputs,metadata,warnings)
    np.testing.assert_allclose(eeg[:,0],np.arange(1,31)*1e-6,atol=0,rtol=1e-15)
    assert eeg.shape==(30,2000) and np.isfinite(eeg).all()
    assert metadata['observed']['source_units_json'] is None
    assert metadata['observed']['source_bad_channels'] is None
    assert metadata['observed']['history_sha256']==hashlib.sha256(b'literal history').hexdigest()

@pytest.mark.parametrize('mode',['corrupt','missing','extra','empty_dir','symlink','dangling','fifo','manifest_changed','method_changed','notice_changed'])
def test_auth_failclosed(mode,tmp_path,monkeypatch,contract):
    root,method,_=bundle(tmp_path,monkeypatch,contract);path=root/'sub-013_task-N2pc_eeg.fdt'
    if mode=='corrupt':
        raw=path.read_bytes();path.write_bytes(b'x'+raw[1:])
    elif mode=='missing':path.unlink()
    elif mode=='extra':(root/'extra').write_text('x')
    elif mode=='empty_dir':(root/'extra').mkdir()
    elif mode=='symlink':(root/'link').symlink_to(path)
    elif mode=='dangling':(root/'link').symlink_to('absent')
    elif mode=='fifo':os.mkfifo(root/'pipe')
    else:
        changed=method if mode=='method_changed' else root/('source_manifest.json' if mode=='manifest_changed' else 'SOURCE_NOTICE.md')
        changed.write_bytes(changed.read_bytes()+b' ')
    with pytest.raises((ValueError,FileNotFoundError)):
        s.load_inputs(root,method)

@pytest.mark.parametrize('mode',['set_replace','fdt_replace','set_modify','fdt_modify','fdt_symlink'])
def test_pair_identity_retained_after_auth(mode,tmp_path,monkeypatch,contract):
    root,method,_=bundle(tmp_path,monkeypatch,contract);inputs=s.load_inputs(root,method)
    role=mode.split('_')[0];path=root/f'sub-001_task-N2pc_eeg.{role}';raw=path.read_bytes()
    if mode.endswith('replace'):path.unlink();path.write_bytes(raw)
    elif mode.endswith('symlink'):path.unlink();path.symlink_to(root/'sub-003_task-N2pc_eeg.fdt')
    else:path.write_bytes(raw)
    with pytest.raises(ValueError):
        s.read_metadata(inputs,1)

def test_mne_reopen_guard_after_value_access(tmp_path,monkeypatch,contract):
    import mne
    root,method,_=bundle(tmp_path,monkeypatch,contract);inputs=s.load_inputs(root,method);metadata=s.read_metadata(inputs,1)
    class Raw:
        ch_names=contract['source']['channel_labels'];n_times=2000;info={'sfreq':1024};first_samp=0
        closed=False
        def get_data(self,picks):
            p=root/'sub-001_task-N2pc_eeg.fdt';raw=p.read_bytes();p.unlink();p.write_bytes(raw)
            return np.ones((30,2000),dtype=np.float64)
        def close(self):self.closed=True
    raw=Raw();monkeypatch.setattr(mne.io,'read_raw_eeglab',lambda *a,**k:raw)
    with pytest.raises(ValueError,match='changed_after_authentication'):
        s.load_mne_eeg(inputs,metadata,[])
    assert raw.closed

@pytest.mark.parametrize('mode',['inline','wrong_pointer'])
def test_pointer_checked_before_signal_reader(mode,tmp_path,monkeypatch,contract):
    root,method,manifest=bundle(tmp_path,monkeypatch,contract);path=root/'sub-001_task-N2pc_eeg.set'
    payload=dict(data=np.zeros((33,2000)) if mode=='inline' else 'other.fdt')
    buf=io.BytesIO();savemat(buf,dict(EEG=payload));raw=buf.getvalue();path.write_bytes(raw)
    row=next(r for r in manifest['files'] if r['path']==path.name)
    row.update(size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),md5=hashlib.md5(raw).hexdigest())
    monkeypatch.setattr(s,'SOURCE_SHA256',write_json(root/'source_manifest.json',manifest))
    inputs=s.load_inputs(root,method)
    if mode=='inline':
        monkeypatch.setattr(matmeta,'loadmat',lambda *a,**k:pytest.fail('inline metadata value decoded'))
    with pytest.raises(ValueError,match='external_character|literal_fdt'):
        s.read_metadata(inputs,1)

@pytest.mark.parametrize('mode',['existing','inside_source','source_ancestor','private_nested','private_same','symlink','dangling','dotdot','method_fifo'])
def test_destination_and_input_safety(mode,tmp_path):
    source=tmp_path/'source';source.mkdir();method=tmp_path/'method.json';method.write_text('{}')
    output=tmp_path/'output';private=tmp_path/'private'
    if mode=='existing':output.mkdir()
    elif mode=='inside_source':output=source/'output'
    elif mode=='source_ancestor':output=tmp_path
    elif mode=='private_nested':private=output/'private'
    elif mode=='private_same':private=output
    elif mode=='symlink':
        (tmp_path/'link').symlink_to(tmp_path,target_is_directory=True);output=tmp_path/'link'/'output'
    elif mode=='dangling':output.symlink_to('absent')
    elif mode=='dotdot':output=str(source)+'/../output'
    else:method.unlink();os.mkfifo(method)
    if mode=='method_fifo':
        with pytest.raises(ValueError):s.authenticated_json(method,'0'*64)
    else:
        with pytest.raises(ValueError):compute.validate_destinations(output,private,source,method)

def mock_analysis(contract):
    trials,arrays=manufactured();rows,people,waves,result=core.derive(trials,arrays,[1],pilot=True)
    return dict(annotations=[],trials=rows,arrays=arrays,people=people,waveforms=waves,result=result,
                metadata={'status':'resource_pilot','source_observed':[],'processing_observed':[]})

@pytest.mark.parametrize('stage',['source','analysis','public','late_private'])
def test_failures_preserved_authoritative_marker(stage,tmp_path,monkeypatch,contract):
    source=tmp_path/'source';source.mkdir();method=tmp_path/'method.json';method.write_text('{}')
    output=tmp_path/'output';private=tmp_path/'private'
    def fail(*a,**k):raise RuntimeError('manufactured failure')
    monkeypatch.setattr(s,'load_inputs',fail if stage=='source' else lambda *a:dict(contract=contract))
    monkeypatch.setattr(compute,'analyze',fail if stage=='analysis' else lambda *a:mock_analysis(contract))
    if stage=='public':monkeypatch.setattr(compute,'emit',fail)
    if stage=='late_private':
        original=compute.write_json
        def write(path,value):
            if path.name=='analysis_receipt.json':fail()
            return original(path,value)
        monkeypatch.setattr(compute,'write_json',write)
    with pytest.raises(RuntimeError):compute.run(source,method,output,private)
    receipt=json.loads((output/'failure_report.json').read_text())
    assert receipt['status']=='failed_precondition'
    if stage=='late_private':
        assert json.loads((output/'n2pc.json').read_text())['status']=='resource_pilot'
        assert len(list(output.iterdir()))==9 # success-looking public files are superseded by failure marker

@pytest.mark.parametrize('raw',[b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":[1e999]}'])
def test_strict_json(raw):
    with pytest.raises(ValueError):s.strict_json(raw)

def test_module_imports_no_data_or_output_io(tmp_path):
    script='import sys;sys.path.insert(0,sys.argv[1]);import compute,core,source_reader,set_metadata'
    result=subprocess.run([sys.executable,'-c',script,str(SOLUTION)],cwd=tmp_path,capture_output=True,text=True,timeout=30)
    assert result.returncode==0 and result.stdout=='' and not list(tmp_path.iterdir())

def test_pilot_only_reads_selected_subject_after_full_auth(tmp_path,monkeypatch,contract):
    inputs=dict(contract=contract,manifest={'files':[]})
    seen=[]
    def read(inputs,subject):
        seen.append(subject)
        return dict(subject=subject,n_samples=5000,events=[dict(type=111,latency=1001),dict(type=121,latency=2001)],
                    observed={'subject':subject})
    monkeypatch.setattr(s,'read_metadata',read)
    monkeypatch.setattr(s,'load_mne_eeg',lambda *a:np.zeros((30,5000)))
    monkeypatch.setattr(core,'filter_reference',lambda *a:np.zeros((2,5000)))
    result=compute.analyze(inputs,[],pilot_subject=8)
    assert seen==[8] and result['metadata']['subjects']==[8] and result['result']['status']=='resource_pilot'
