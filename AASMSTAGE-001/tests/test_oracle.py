"""Synthetic-only mechanics; never mount or read the original source bundle."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
import pytest

SOLUTION = Path(__file__).parents[1]/'solution'
sys.path.insert(0,str(SOLUTION))
import compute as oracle
import source_reader as reader


@pytest.fixture
def method():
    return json.loads((Path(__file__).parents[1]/'environment'/'method_contract.json').read_text())


def row(i,onset,duration,label='Sleep stage W'):
    return dict(annotation_index=i,tal_index=i+1,onset_s=float(onset),duration_s=float(duration),description=label)


def test_tal_order_padding_and_multiple_descriptions():
    rows,keepers = reader.parse_tals(b'+0\x14\x14\0\0+30\x1530\x14Sleep stage W\x14Sleep stage 1\x14\0')
    assert keepers == [dict(tal_index=0,onset_s=0.)]
    assert [r['tal_index'] for r in rows] == [1,1]
    assert [r['annotation_index'] for r in rows] == [0,1]


@pytest.mark.parametrize('payload',[b'+0',b'+0\x14label',b'+0\x15-1\x14W\x14',
    b'NaN\x14W\x14',b'+1e999\x14W\x14',b'+0\x15Inf\x14W\x14'])
def test_malformed_tals_rejected(payload):
    with pytest.raises((ValueError,ArithmeticError)):
        reader.parse_tals(payload)


def test_crop_original_rows_and_movement(method):
    rows = [row(0,0,1800),row(1,1800,30,'Sleep stage 1'),row(2,1830,30,'Movement time'),
            row(3,1860,1800),row(4,3660,30,'Sleep stage ?')]
    annotations,epochs,obs = reader.annotation_ledgers(0,rows,366000,method)
    assert obs['requested_crop_start_s'] == 0 and obs['requested_crop_stop_s'] == 3660
    movement = next(r for r in epochs if r['onset_sample'] == 183000)
    assert movement['stage_id'] is None and not movement['retained']
    assert movement['drop_reason'] == 'unsupported_stage'
    assert annotations[-1]['n_complete_chunks'] == 0


@pytest.mark.parametrize('bad_start,bad_duration,dropped',[(60,0,0),(60,1,1),(59,1,1),(3660,1,0)])
def test_bad_positive_duration_halfopen(method,bad_start,bad_duration,dropped):
    rows = [row(0,0,1800),row(1,1800,30,'Sleep stage 1'),row(2,bad_start,bad_duration,'BAD artifact'),
            row(3,1830,1830),row(4,3660,30,'Sleep stage ?')]
    _,epochs,_ = reader.annotation_ledgers(0,rows,366000,method)
    assert sum(e['drop_reason']=='overlap_bad_annotation' for e in epochs) == dropped


def test_incomplete_chunk_kept_as_annotation_not_epoch(method):
    rows = [row(0,0,1800),row(1,1800,45,'Sleep stage 1'),row(2,1845,1800),row(3,3645,30,'Sleep stage ?')]
    a,e,_ = reader.annotation_ledgers(0,rows,364500,method)
    assert a[1]['n_complete_chunks'] == 1 and a[1]['discarded_tail_s'] == 15
    assert not any(x['onset_sample'] == 183000 for x in e)


@pytest.mark.parametrize('kind',['fraction','duplicate','overlap','infinite'])
def test_source_coordinate_failures(method,kind):
    rows = [row(0,0,1800),row(1,1800,60,'Sleep stage 1'),row(2,1860,1800),row(3,3660,30,'Sleep stage ?')]
    if kind=='fraction': rows[1]['onset_s'] += .001
    if kind=='duplicate': rows.insert(2,row(9,1800,30))
    if kind=='overlap': rows.insert(2,row(9,1815,30))
    if kind=='infinite': rows[1]['duration_s'] = float('inf')
    with pytest.raises(ValueError): reader.annotation_ledgers(0,rows,366000,method)


def test_welch_matches_explicit_fft_and_normalization():
    x = np.random.RandomState(3).normal(size=(3,2,3000))*1e-5
    f,d,p = oracle.spectral_features(x)
    seg = x[...,:2816].reshape(3,2,11,256)
    seg = seg-seg.mean(axis=-1,keepdims=True)
    window = .54-.46*np.cos(2*np.pi*np.arange(256)/256)
    expected = abs(np.fft.rfft(seg*window,axis=-1))**2/(100*np.sum(window**2))
    expected[...,1:-1] *= 2
    expected = expected.mean(axis=-2)
    np.testing.assert_allclose(p,expected,rtol=1e-12,atol=1e-30)
    np.testing.assert_allclose(d,p[...,2:77].sum(-1),rtol=1e-14)
    np.testing.assert_allclose((f.reshape(3,5,2)*np.array([10,10,8,10,37])[None,:,None]).sum(1),1,atol=1e-14)


def test_welch_discards184_tail_samples_and_scales_power():
    x = np.random.RandomState(5).normal(size=(1,2,3000))
    f,d,p = oracle.spectral_features(x)
    changed = x.copy(); changed[...,2816:] += 1e9
    np.testing.assert_array_equal(oracle.spectral_features(changed)[0],f)
    f2,d2,_ = oracle.spectral_features(x*2)
    np.testing.assert_allclose(f2,f,rtol=1e-14); np.testing.assert_allclose(d2,d*4,rtol=1e-14)


@pytest.mark.parametrize('kind',['zero','nan','wrongshape'])
def test_invalid_spectra_fail(kind):
    x = np.zeros((1,2,3000))
    if kind=='nan': x[0,0,0] = np.nan
    if kind=='wrongshape': x = x[:,:,:2999]
    with pytest.raises(ValueError): oracle.spectral_features(x)


def test_metric_weighting_and_exact_degenerate_kappa():
    c = np.zeros((5,5),int); c[0,0]=90; c[1,0]=10
    m = oracle.metrics(c)
    assert m['overall_accuracy']==.9 and m['balanced_accuracy']==.5
    assert m['per_class'][2]['recall'] is None and m['n_supported_classes']==2
    c[1,0]=0
    assert oracle.metrics(c)['kappa'] is None
    with pytest.raises(ValueError): oracle.metrics(np.zeros((5,5)))


def test_forest_recipe_and_manual_tree_traversal(method):
    assert method['classifier']['parameters']['n_estimators'] == 200
    assert method['classifier']['parameters']['random_state'] == 42
    rng = np.random.RandomState(9); x = rng.normal(size=(24,10))
    subjects = np.repeat(np.arange(6),4); labels = np.tile([1,3,1,3],6)
    keys = np.column_stack([subjects,np.ones(24,int),np.tile(np.arange(4)*3000,6)])
    params = dict(method['classifier']['parameters'],n_estimators=4)
    train,test,proba,pred,state = oracle.fit_fold(x,labels,subjects,keys,0,params)
    assert set(subjects[train]) == {1,2,3,4,5} and set(subjects[test]) == {0}
    result = np.zeros_like(proba); prefix='forest_0_'
    offsets = state[prefix+'node_offsets']; values=state[prefix+'value']; classes=state[prefix+'classes']
    for first,last in zip(offsets[:-1],offsets[1:]):
        for i,sample in enumerate(x[test].astype(np.float32)):
            node=0
            while state[prefix+'children_left'][first+node] != -1:
                j=first+node; branch='children_left' if sample[state[prefix+'feature'][j]] <= state[prefix+'threshold'][j] else 'children_right'
                node=state[prefix+branch][j]
            result[i,classes-1] += values[first+node]/values[first+node].sum()/4
    np.testing.assert_allclose(result,proba,rtol=0,atol=1e-15)
    np.testing.assert_array_equal(pred,np.argmax(result,axis=1)+1)
    assert (proba[:,[1,3,4]] == 0).all()


@pytest.mark.parametrize('case',['same','nested','source','existing','symlink'])
def test_evidence_paths_preserved(tmp_path,case):
    output,private,source,method = [tmp_path/k for k in ('output','private','source','method.json')]
    source.mkdir(); method.write_text('{}')
    if case=='same': private=output
    if case=='nested': private=output/'private'
    if case=='source': output=source/'output'
    if case=='existing': output.mkdir(); (output/'old').write_text('keep')
    if case=='symlink': output.symlink_to(source,target_is_directory=True)
    with pytest.raises(ValueError): oracle.prepare_destinations(output,private,source,method)
    if case=='existing': assert (output/'old').read_text()=='keep'
    assert method.read_text()=='{}'


def test_failure_evidence_nonempty_and_no_overwrite(tmp_path):
    oracle.failure(tmp_path,ValueError('missing data'))
    assert json.loads((tmp_path/'run_metadata.json').read_text())['reason']=='missing data'
    assert (tmp_path/'findings.md').read_text().strip()
    original=(tmp_path/'run_metadata.json').read_bytes()
    oracle.failure(tmp_path,ValueError('later failure'))
    assert (tmp_path/'run_metadata.json').read_bytes()==original


@pytest.mark.parametrize('pilot',[None,0])
def test_nine_outputs_from_synthetic_pipeline(tmp_path,monkeypatch,method,pilot):
    params=deepcopy(method); params['classifier']['parameters']['n_estimators']=2
    paths={(s,role):Path(f'fake{s}-{role}.edf') for s in range(6) for role in ['psg','hypnogram']}
    manifest={'files':[dict(path=p.name,sha256='0'*64) for p in paths.values()]}
    monkeypatch.setattr(oracle,'load_inputs',lambda *args:(params,manifest,paths))
    def inspect_subject(s,*args):
        annotations=[dict(subject=s,recording=1,annotation_index=i,tal_index=i+1,onset_s=i*30.,
            duration_s=30.,description=STAGE,stage_id=i+1,effective_onset_s=i*30.,effective_stop_s=(i+1)*30.,
            n_complete_chunks=1,discarded_tail_s=0.,status='used')
            for i,STAGE in enumerate(['Sleep stage W','Sleep stage 1','Sleep stage 2','Sleep stage 3','Sleep stage R'])]
        epochs=[dict(subject=s,recording=1,annotation_index=i,chunk_index=0,onset_s=i*30.,
            onset_sample=i*3000,end_sample_exclusive=(i+1)*3000,n_samples=3000,stage_id=i+1,
            retained=True,drop_reason='retained') for i in range(5)]
        return annotations,epochs,dict(subject=s,recording=1,n_samples=15000)
    monkeypatch.setattr(oracle,'inspect_subject',inspect_subject)
    monkeypatch.setattr(oracle,'read_retained_epochs',lambda path,e,obs:np.random.RandomState(obs['subject']).normal(size=(5,2,3000))*1e-5)
    out,private=oracle.prepare_destinations(tmp_path/'out',tmp_path/'private',tmp_path/'source',tmp_path/'method')
    result=oracle.run(tmp_path/'source',tmp_path/'method',out,private,pilot)
    assert set(p.name for p in out.iterdir()) == set(method['outputs'])
    assert result['status']==('ok' if pilot is None else 'resource_pilot')
    assert result['n_subjects']==(6 if pilot is None else 1)
    assert result['n_epochs_total']==(30 if pilot is None else 5)
    metadata=json.loads((out/'run_metadata.json').read_text())
    assert metadata['source_observed']['n_subjects']==6
    with np.load(private/'analysis_arrays.npz',allow_pickle=False) as arrays:
        assert arrays['features'].shape==(30,10)
        assert arrays['epoch_subject_0'].shape==(5,2,3000)
        assert arrays['psd_subject_0'].shape==(5,2,129)
        assert len(arrays['forest_0_node_offsets'])==3


def test_subprocess_missing_source_failure(tmp_path):
    import subprocess
    command=[sys.executable,str(SOLUTION/'compute.py'),'--data-dir',str(tmp_path/'missing-source'),
        '--method-contract',str(tmp_path/'missing-method'),'--output-dir',str(tmp_path/'out'),
        '--private-dir',str(tmp_path/'private')]
    result=subprocess.run(command,capture_output=True,text=True,timeout=30)
    assert result.returncode != 0
    assert json.loads((tmp_path/'out'/'staging_results.json').read_text())['status']=='failed_precondition'
    assert json.loads((tmp_path/'out'/'run_metadata.json').read_text())['reason']
    assert (tmp_path/'out'/'findings.md').read_text().strip()
    before=(tmp_path/'out'/'run_metadata.json').read_bytes()
    second=subprocess.run(command,capture_output=True,text=True,timeout=30)
    assert second.returncode != 0 and (tmp_path/'out'/'run_metadata.json').read_bytes()==before
