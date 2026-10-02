"""Manufactured source/authentication/operator fixtures only."""
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import zipfile
import numpy as np
import pytest
from scipy.io import savemat
import io_contract as guard
import mat_metadata
import n2pc_math as core
import source_reference as source


def mat_bytes(*,scalar=True,compressed=False,change=None):
    method,_=source.authority()
    fields=dict(data='fake.fdt',nbchan=33,pnts=2000,trials=1,srate=1024,xmin=0,ref='common',
                chanlocs=np.array([{'labels':s} for s in method['source']['channel_labels']],dtype=object),
                event=np.array([{'type':111,'latency':501,'urevent':1},{'type':121,'latency':1201,'urevent':2}],dtype=object),
                history='literal history\n',times=np.arange(2000),icaweights=np.ones((3,3)))
    if change:change(fields)
    b=io.BytesIO();savemat(b,{'EEG':fields} if scalar else fields,do_compression=compressed);return b.getvalue()


@pytest.mark.parametrize('scalar',[False,True])
@pytest.mark.parametrize('compressed',[False,True])
def test_metadata_classic_layout(scalar,compressed):
    method,_=source.authority()
    m=source.metadata(mat_bytes(scalar=scalar,compressed=compressed),1,{'path':'fake.set'},{'path':'fake.fdt','size_bytes':264000},method)
    assert m['observed']['history_sha256']==hashlib.sha256(b'literal history\n').hexdigest()
    assert len(m['trials'])==2 and m['observed']['source_units_json'] is None


@pytest.mark.parametrize('key,value',[('data',np.ones((2,2))),('data','../fake.fdt'),('srate',256),('nbchan',32),
 ('trials',2),('xmin',1),('ref','average'),('unit','V')])
def test_metadata_preconditions(key,value):
    method,_=source.authority()
    with pytest.raises(ValueError):
        source.metadata(mat_bytes(change=lambda d:d.update({key:value})),1,{'path':'fake.set'},{'path':'fake.fdt','size_bytes':264000},method)


def test_no_times_ica_decode(monkeypatch):
    called=[];original=mat_metadata.MatScan.decode
    def decode(self,node):
        called.append(node['name']);return original(self,node)
    monkeypatch.setattr(mat_metadata.MatScan,'decode',decode)
    method,_=source.authority()
    source.metadata(mat_bytes(scalar=False),1,{'path':'fake.set'},{'path':'fake.fdt','size_bytes':264000},method)
    assert not {'times','icaweights','EEG'}&set(called)


@pytest.mark.parametrize('source_type',['111','BAD',True,1.5,np.inf])
def test_numeric_event_type_only(source_type):
    with pytest.raises(ValueError):core.annotate(1,[{'type':source_type,'latency':100}],2000)


@pytest.mark.parametrize('latency',[0,1,1.4,2500.5])
def test_boundary_half_sample_bounds(latency):
    with pytest.raises(ValueError):core.annotate(1,[{'type':-99,'latency':latency}],2000)


@pytest.mark.parametrize('cut',[0,2000])
def test_edge_cut_not_empty_segment(cut):
    a,t,s=core.annotate(1,[{'type':-99,'latency':cut+.5},{'type':111,'latency':501}],2000)
    assert s==[[0,2000]] and t[0]['retained']


@pytest.mark.parametrize('sample,cross',[(538,False),(539,True),(1204,True),(1205,False)])
def test_boundary_inclusive_support(sample,cross):
    # Cut1000: last sample at999 is safe; first sample1000 is safe.
    a,t,s=core.annotate(1,[{'type':-99,'latency':1000.5},{'type':111,'latency':sample+1}],2000)
    assert t[0]['crosses_boundary']==cross


def test_durations_and_diagnostic_boundary_rounding():
    events=[{'type':201,'latency':1},{'type':201,'latency':2,'duration':None},
            {'type':201,'latency':3,'duration':0},{'type':-99,'latency':10.5,'duration':{'source_nonfinite':'nan'}}]
    a,t,s=core.annotate(1,events,2000)
    assert [r['duration_status'] for r in a]==['absent','empty','finite','nonfinite']
    assert a[-1]['sample']==10 and a[-1]['boundary_cut_sample']==10


def test_duplicate_target_only():
    with pytest.raises(ValueError):
        core.annotate(1,[{'type':111,'latency':501},{'type':121,'latency':501}],2000)
    assert len(core.annotate(1,[{'type':111,'latency':501},{'type':201,'latency':501}],2000)[1])==1


def test_clock_endpoint_baseline_measurement():
    assert core.OFFSETS.tolist()==list(range(-205,462))
    assert core.OFFSETS[1:206].tolist()==list(range(-204,1))
    assert core.OFFSETS[410:513].tolist()==list(range(205,308))
    x=np.zeros((2,2,667));x[:,:,0]=1e6;x[0,1,410:513]=-4;x[1,0,410:513]=-1
    trials=[dict(subject=1,source_event_index=i,retained=True,target_field=f,drop_reason='retained') for i,f in enumerate(('left','right'))]
    own=core.derive(trials,x,subjects=(1,))
    assert own['per_subject'][0]['n2pc_uv']==-2.5 and own['per_subject'][0]['fixed_po8_minus_po7_pooled_uv']==-1.5
    assert own['trials'][0]['po7_baseline_uv']==0


def test_unequal_field_weights():
    x=np.zeros((10,2,667));x[:2,1,410:513]=-4;x[2:,0,410:513]=-1
    t=[dict(subject=1,source_event_index=i,retained=True,target_field='left' if i<2 else 'right',drop_reason='retained') for i in range(10)]
    own=core.derive(t,x,subjects=(1,))
    assert own['result']['n2pc_amplitude_uv']==-2.5
    assert own['result']['n2pc_amplitude_uv']!=(2*-4+8*-1)/10


def test_direct_FDT_layout_units_and_excluded_EOG(monkeypatch):
    n=1200;stored=np.arange(n*33,dtype=np.float32).reshape(n,33);stored[:,30:]=np.nan
    _,trials,segments=core.annotate(1,[{'type':111,'latency':501}],n)
    monkeypatch.setattr(core,'kernel',lambda:np.array([1.]))
    m=dict(n_samples=n,trials=trials,segments=segments)
    x=source.direct_fdt_epochs(stored.astype('<f4').tobytes(),m)
    eeg=stored[:,:30].astype(float);expect=(eeg[:,[9,27]]-eeg.mean(axis=1)[:,None])[295:962].T
    np.testing.assert_array_equal(x[0],expect)
    stored[400,0]=np.nan
    with pytest.raises(ValueError,match='nonfinite_source_EEG'):source.direct_fdt_epochs(stored.astype('<f4').tobytes(),m)


@pytest.mark.parametrize('length',[1,2,127,1024,33793])
def test_analytic_filter_against_MNE(length):
    from mne.filter import create_filter,filter_data
    import warnings
    x=np.sin(np.arange(length)*.037)+.13*np.cos(np.arange(length)*.13)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        h=create_filter(None,1024,.1,30,verbose='ERROR')
        y=filter_data(x,1024,.1,30,pad='reflect_limited',verbose='ERROR')
    np.testing.assert_allclose(core.kernel(),h,atol=2e-17,rtol=0)
    np.testing.assert_allclose(core.filter_one(x,core.kernel()),y,atol=1e-6,rtol=1e-6)


@pytest.mark.parametrize('levels',[(.1,.3),(.3,.1)])
def test_own_primitive_zero_sign_roundoff_receipt(levels):
    # Diagnostic only: public strict sign is not automatically stable under
    # mathematically equivalent reduction order. No original outcomes involved.
    x=np.zeros((2,2,667));x[0,0]=levels[0];x[0,1]=levels[1]
    t=[dict(subject=1,source_event_index=i,retained=True,target_field=f,drop_reason='retained') for i,f in enumerate(('left','right'))]
    ours=core.derive(t,x,subjects=(1,))['per_subject'][0]['n2pc_uv']
    baseline=x[:,:,1:206].mean(axis=2)
    win=(x-baseline[:,:,None])[:,:,410:513].mean(axis=2)
    native=((win[0,1]+win[1,0])-(win[0,0]+win[1,1]))/2
    print(json.dumps({'sourcefree_constant_epoch_sign':{'fsum_window_minus_baseline':ours,'numpy_corrected_window':float(native),
                     'fsum_negative':ours<0,'numpy_negative':bool(native<0)}}))
    assert abs(ours-native)<1e-8


def fake_inventory(tmp_path,monkeypatch):
    method,manifest=source.authority()
    manifest=json.loads(json.dumps(manifest))
    root=tmp_path/'data';root.mkdir()
    for r in manifest['files']:
        raw=(str(r['subject'])+r['role']).encode();r['size_bytes']=len(raw);r['sha256']=hashlib.sha256(raw).hexdigest()
        (root/r['path']).write_bytes(raw)
    raw=json.dumps(manifest).encode();(root/'source_manifest.json').write_bytes(raw);(root/'SOURCE_NOTICE.md').write_bytes(b'notice')
    monkeypatch.setattr(source,'SOURCE_SHA',hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(source,'NOTICE_SHA',hashlib.sha256(b'notice').hexdigest())
    monkeypatch.setattr(source,'authority',lambda:(method,manifest))
    return root,manifest


def test_authenticate_fake_closed24(tmp_path,monkeypatch):
    root,m=fake_inventory(tmp_path,monkeypatch)
    assert len(source.authenticate(root)[2]['files'])==24


def test_mutable_stager_not_imported(tmp_path,monkeypatch):
    import builtins
    root,m=fake_inventory(tmp_path,monkeypatch);original=builtins.__import__
    def guarded(name,*args,**kwargs):
        if 'stage_data' in name or name.startswith('solution'):raise RuntimeError('forbidden agent helper import')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',guarded)
    assert len(source.authenticate(root)[2]['files'])==24


@pytest.mark.parametrize('name',['method_authority.json','source_authority.json','mat_metadata.py'])
def test_private_authority_hashes_not_mutable(tmp_path,monkeypatch,name):
    for f in ('method_authority.json','source_authority.json','mat_metadata.py'):
        (tmp_path/f).write_bytes((source.HERE/f).read_bytes())
    (tmp_path/name).write_bytes((tmp_path/name).read_bytes()+b' ')
    monkeypatch.setattr(source,'HERE',tmp_path)
    with pytest.raises(ValueError,match='sha256'):source.authority()


@pytest.mark.parametrize('kind',['changed','extra','directory','symlink','fifo','manifest','notice','missing'])
def test_authentication_rejects(tmp_path,monkeypatch,kind):
    root,m=fake_inventory(tmp_path,monkeypatch);p=root/m['files'][0]['path']
    if kind=='changed':p.write_bytes(b'wrong')
    if kind=='extra':(root/'stage_data.py').write_text('raise RuntimeError("must never import")')
    if kind=='directory':(root/'extra').mkdir()
    if kind=='symlink':p.unlink();p.symlink_to(tmp_path/'outside')
    if kind=='fifo':p.unlink();os.mkfifo(p)
    if kind=='manifest':(root/'source_manifest.json').write_bytes(b'{}')
    if kind=='notice':(root/'SOURCE_NOTICE.md').write_bytes(b'changed')
    if kind=='missing':p.unlink()
    with pytest.raises(ValueError):source.authenticate(root)


def test_lexical_symlink_traversal(tmp_path):
    target=tmp_path/'real';target.mkdir();(tmp_path/'alias').symlink_to(target)
    with pytest.raises(ValueError):guard.safe_path(str(tmp_path)+'/alias/../anything')
    with pytest.raises(ValueError):guard.safe_path(tmp_path/'alias'/'file')


def test_nonregular_read_refuses_without_blocking(tmp_path):
    p=tmp_path/'fifo';os.mkfifo(p)
    with pytest.raises(ValueError):guard.read_bytes(p)


def test_same_buffer_hash_precedes_parse(tmp_path):
    p=tmp_path/'fake';p.write_bytes(b'abc')
    with pytest.raises(ValueError,match='sha256'):guard.read_bytes(p,sha256='0'*64)


def test_stale_pyc_and_pythonpath_ignored(tmp_path):
    # Exercise the same isolated bootstrap semantics without production source IO.
    poison=tmp_path/'poison';poison.mkdir();(poison/'sitecustomize.py').write_text('raise RuntimeError("poison site")')
    (poison/'pytest.py').write_text('raise RuntimeError("poison pytest")')
    trusted=tmp_path/'trusted';trusted.mkdir();(trusted/'tiny.py').write_text('value=7\n')
    (trusted/'tiny.pyc').write_bytes(b'not valid bytecode')
    env=dict(os.environ,PYTHONPATH=str(poison))
    code='import sys,tempfile;sys.pycache_prefix=tempfile.mkdtemp();sys.path.insert(0,sys.argv[1]);import tiny,pytest;assert tiny.value==7;print("isolated")'
    r=subprocess.run([sys.executable,'-I','-B','-c',code,str(trusted)],cwd=poison,env=env,capture_output=True,text=True,timeout=30)
    assert r.returncode==0 and r.stdout.strip()=='isolated',r.stderr


def test_actual_wrapper_bootstrap_with_manufactured_test(tmp_path):
    trusted=tmp_path/'trusted';trusted.mkdir();logs=tmp_path/'logs';poison=tmp_path/'poison';poison.mkdir()
    (trusted/'test_outputs.py').write_text('def test_generated_only():\n    assert 1 + 1 == 2\n')
    (poison/'pytest.py').write_text('raise RuntimeError("poisoned pytest")\n')
    (poison/'sitecustomize.py').write_text('raise RuntimeError("poisoned sitecustomize")\n')
    wrapper=Path(__file__).with_name('test.sh').read_text().replace('/tests',str(trusted)).replace('/logs/verifier',str(logs))
    script=tmp_path/'wrapper.sh';script.write_text(wrapper)
    env=dict(os.environ,PYTHONPATH=str(poison),PYTEST_PLUGINS='nonexistent_poison_plugin',PYTEST_ADDOPTS='-k never_execute')
    r=subprocess.run(['bash',str(script)],cwd=poison,env=env,capture_output=True,text=True,timeout=30)
    assert r.returncode==0,(r.stdout,r.stderr)
    assert (logs/'reward.txt').read_text()=='1\n'
    assert json.loads((logs/'ctrf.json').read_text())['results']['summary']['passed']==1


def test_npz_duplicate_member(tmp_path):
    p=tmp_path/'duplicate.npz';b=io.BytesIO();np.save(b,np.zeros(1))
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        with zipfile.ZipFile(p,'w') as z:
            z.writestr('x.npy',b.getvalue());z.writestr('x.npy',b.getvalue())
    with pytest.raises(ValueError,match='duplicate'):guard.npz_read(p)


def test_npz_shape_claim_checked_before_allocation(tmp_path):
    p=tmp_path/'claimed.npz';b=io.BytesIO()
    np.lib.format.write_array_header_1_0(b,dict(descr='<f8',fortran_order=False,shape=(2**40,)))
    with zipfile.ZipFile(p,'w') as z:z.writestr('huge.npy',b.getvalue())
    with pytest.raises(ValueError,match='claimed_size'):guard.npz_read(p)


@pytest.mark.parametrize('kind',['symlink','fifo','directory'])
def test_output_inventory_refuses_nonregular(tmp_path,kind):
    p=tmp_path/'out';p.mkdir();f=p/'response_epochs.npz'
    if kind=='symlink':f.symlink_to(tmp_path/'absent')
    if kind=='fifo':os.mkfifo(f)
    if kind=='directory':f.mkdir()
    with pytest.raises(ValueError,match='nonregular'):guard.output_files(p)
