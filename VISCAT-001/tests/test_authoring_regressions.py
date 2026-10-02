"""Manufactured source-free mathematical, serialization and identity regressions."""
import copy
import hashlib
import json
import os
import sys
import types
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import kruskal, rankdata

import category_statistics as s
import io_contract as io
import population_contract as q
import proof_of_work as p
import source_reference as source
from fixture_support import emit, manufactured_reference, mutate_json, mutate_npz, write_csv


@pytest.fixture
def ref(): return manufactured_reference()


@pytest.mark.parametrize("seed", range(12))
def test_independent_kw_matches_scipy_manufactured(seed):
    rng = np.random.default_rng(seed)
    groups = [rng.integers(0, 15, size=8+i) for i in range(5)]
    counts = np.concatenate(groups); categories = np.concatenate([np.full(len(v), i+1) for i, v in enumerate(groups)])
    got = s.category_test(counts, categories); expected = kruskal(*groups)
    assert got["H"] == pytest.approx(expected.statistic, abs=1e-12)
    assert got["p"] == pytest.approx(expected.pvalue, abs=1e-12)
    ranks = rankdata(counts)*2
    assert got["rank_sum_twice"] == [int(sum(ranks[categories == c])) for c in s.CATEGORIES]


def test_highest_mean_auc_can_be_below_chance():
    counts=np.array([0,0,100]+[10]*12); categories=np.repeat(np.arange(1,6),3)
    got=s.category_test(counts,categories)
    assert got["preferred"] == 1 and got["auc"] == 1/3


@pytest.mark.parametrize("value", [0, 1, 100])
def test_all_tied(value):
    got=s.category_test(np.full(25,value),np.repeat(np.arange(1,6),5))
    assert (got['status'],got['H'],got['p'],got['preferred'],got['preferred_tied'],got['auc'],got['selected']) == ('all_tied',0,1,1,True,.5,False)


def test_missing_support_and_no_rng_consumption():
    good=np.repeat(np.arange(1,6),5); missing=np.repeat(np.arange(1,5),5)
    got=s.category_test(np.arange(len(missing)),missing)
    assert got['status']=='insufficient_category_support' and got['p'] is got['preferred'] is got['auc'] is None
    a,starts,_=s.make_membership([missing,good]); b,_,_=s.make_membership([good])
    assert not a[:,:starts[1]].any() and np.array_equal(a[:,starts[1]:],b)


def test_strict_threshold():
    assert not s.is_selected('ok', .05)
    assert s.is_selected('ok', np.nextafter(.05,0))
    assert not s.is_selected('all_tied', 0)


def test_integer_auc_matches_pairwise():
    x=np.array([0,2,2,4,0,2,3,4]); c=np.array([1,1,1,1,2,3,4,5])
    a=s.auc_twice(x,c,1)
    twice=sum(2*int(u>v)+int(u==v) for u in x[c==1] for v in x[c!=1])
    assert a['u_preferred_twice']==twice


@pytest.mark.parametrize('n',[0,1,4,5,50])
def test_conditional_eligibility(n):
    rows=[{'selected':i<n,'test':{'auc':.3 if i<n else .9}} for i in range(50)]
    got=s.conditional_summary(rows)
    assert got['n_selected_splits']==n and got['heldout_eligible']==(n>=5)
    assert got['conditional_auc']==pytest.approx(.3) if n else got['conditional_auc'] is None


def test_population_equal_unit_and_empty():
    assert s.population([])==dict(n_units=0,mean_auc=None,status='empty_population')
    assert s.population([.2,.9])['mean_auc']==pytest.approx(.55)


def test_train_preference_not_heldout_preference():
    categories=np.repeat(np.arange(1,6),2); train=np.tile([True,False],5)
    counts=np.array([100,0,0,200,0,200,0,200,0,200])
    got=s.split_test(counts,categories,train)
    assert got['preferred']==1 and got['test']['auc']==0


def test_unsorted_duplicate_halfopen_copy():
    raw=np.array([11.7,10.2,10.2,11.,10.1]); old=raw.copy()
    assert source.count_intervals(raw,[10]).tolist()==[3]
    assert np.array_equal(raw,old)


@pytest.mark.parametrize('headline',q.POPULATIONS)
def test_both_headlines(ref,tmp_path,headline):
    out=emit(tmp_path/'out',ref,headline)
    assert p.validate_output_directory(out,ref)['n_split_events']==150


@pytest.mark.parametrize('categories',[np.array([],dtype=np.int64),np.repeat(np.arange(1,5),3),np.arange(1,6)])
def test_unsupported_complete_outputs(categories,tmp_path):
    ref=manufactured_reference(categories); out=emit(tmp_path/'out',ref)
    p.validate_output_directory(out,ref)


def test_coherent_all_axes_tables_reorder(ref,tmp_path):
    out=emit(tmp_path/'out',ref)
    for filename,schema in ref['method']['outputs'].items():
        if filename.endswith('.csv'):
            rows=io.csv_load(out/filename,schema['columns']);write_csv(out/filename,rows[::-1],schema['columns'][::-1])
    def change(a):
        unit=np.arange(len(a['unit_key']))[::-1];inverse=np.argsort(unit); response=np.arange(len(a['spike_count']))[::-1]
        repeat=np.arange(50)[::-1]
        a['unit_key']=a['unit_key'][unit];a['response_unit_index']=inverse[a['response_unit_index']]
        for key in ('response_unit_index','source_trial_row','trial_id','category_code','spike_count','rate_hz'):a[key]=a[key][response]
        a['repeat_id']=a['repeat_id'][repeat];a['train_membership']=a['train_membership'][np.ix_(repeat,response)]
    mutate_npz(out/'responses.npz',change);p.validate_output_directory(out,ref)


def test_independently_rounded_reports(ref,tmp_path):
    out=emit(tmp_path/'out',ref)
    for filename,name in [('neurons.csv','neurons'),('split_events.csv','split_events')]:
        schema=ref['method']['outputs'][filename]; rows=io.csv_load(out/filename,schema['columns'])
        for row in rows:
            for key in ('same_trial_auc','conditional_auc','train_auc','test_auc'):
                if row.get(key) and .1<float(row[key])<.9:row[key]=str(float(row[key])+9e-9)
        write_csv(out/filename,rows,schema['columns'])
    def change(r):
        for x in r['populations'].values():
            if x['mean_auc'] is not None:x['mean_auc']-=9e-9
        if r['preferred_category_auc'] is not None:r['preferred_category_auc']-=9e-9
    mutate_json(out/'results.json',change);p.validate_output_directory(out,ref)


@pytest.mark.parametrize('field',['spike_count','trial_id','category_code','source_trial_row','train_membership'])
def test_wrong_primitive(ref,tmp_path,field):
    out=emit(tmp_path/'out',ref)
    def change(a):
        if field=='train_membership':a[field][0,0]=not a[field][0,0]
        else:a[field][0]+=1
    mutate_npz(out/'responses.npz',change)
    with pytest.raises(AssertionError):p.validate_output_directory(out,ref)


@pytest.mark.parametrize('filename',['sessions.csv','trials.csv','units.csv','neurons.csv','split_events.csv'])
def test_missing_table_row(ref,tmp_path,filename):
    out=emit(tmp_path/'out',ref);schema=ref['method']['outputs'][filename]
    rows=io.csv_load(out/filename,schema['columns']);write_csv(out/filename,rows[:-1],schema['columns'])
    with pytest.raises(AssertionError):p.validate_output_directory(out,ref)


@pytest.mark.parametrize('mode',['empty','json','dangling','fifo'])
def test_authoritative_failure_report(ref,tmp_path,mode):
    out=emit(tmp_path/'out',ref);marker=out/'failure_report.json'
    if mode=='dangling':marker.symlink_to(out/'absent')
    elif mode=='fifo':os.mkfifo(marker)
    else:marker.write_text('' if mode=='empty' else '{}')
    with pytest.raises(AssertionError,match='failure_report'):p.validate_output_directory(out,ref)


@pytest.mark.parametrize('value',[True,False,'1.5','NaN','inf','1e100000000',2**63,-2**63-1])
def test_invalid_integer(value):
    with pytest.raises(AssertionError):io.integer(value)


@pytest.mark.parametrize('value',['9007199254740993','9.007199254740993e15',9007199254740993])
def test_large_integer_no_float_roundtrip(value):assert io.integer(value)==9007199254740993


@pytest.mark.parametrize('body',['{"x":1,"x":2}','{"x":[1e999]}','{"x":NaN}'])
def test_strict_json(body):
    with pytest.raises(AssertionError):io.parse_json(body)


def tiny_bundle(tmp_path,monkeypatch):
    root=tmp_path/'source';root.mkdir();rows=[]
    for i in range(87):
        name=f'sub{i}/asset.nwb';p=root/name;p.parent.mkdir();body=f'manufactured-{i}'.encode();p.write_bytes(body)
        rows.append(dict(path=name,role='session_nwb',size_bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
    body=json.dumps(dict(n_files=87,total_size_bytes=sum(r['size_bytes'] for r in rows),files=rows)).encode()
    (root/'source_manifest.json').write_bytes(body);monkeypatch.setattr(io,'SOURCE_SHA256',hashlib.sha256(body).hexdigest())
    return root


def test_grader_owned_source_auth_no_helper(tmp_path,monkeypatch):
    root=tiny_bundle(tmp_path,monkeypatch)
    monkeypatch.setitem(sys.modules,'stage_data',types.SimpleNamespace(verify_staged=lambda _: (_ for _ in ()).throw(RuntimeError('MUST NOT IMPORT'))))
    assert io.authenticate_source(root)[1]['n_files']==87


@pytest.mark.parametrize('mode',['manifest','corrupt','missing','extra','directory','link','dangling','fifo'])
def test_direct_source_auth_rejects(tmp_path,monkeypatch,mode):
    root=tiny_bundle(tmp_path,monkeypatch);p=root/'sub0/asset.nwb'
    if mode=='manifest':(root/'source_manifest.json').write_text('{}')
    elif mode=='corrupt':p.write_bytes(b'X'*p.stat().st_size)
    elif mode=='missing':p.unlink()
    elif mode=='extra':(root/'extra').write_text('x')
    elif mode=='directory':(root/'extra').mkdir()
    else:
        p.unlink()
        if mode=='fifo':os.mkfifo(p)
        else:p.symlink_to(root/('absent' if mode=='dangling' else 'sub1/asset.nwb'))
    with pytest.raises((AssertionError,FileNotFoundError)):io.authenticate_source(root)


def test_authenticated_json_same_bytes(tmp_path,monkeypatch):
    pth=tmp_path/'receipt.json';good=b'{"count":1}';pth.write_bytes(good);parse=io.parse_json
    def swap(body):pth.write_text('{"count":2}');return parse(body)
    monkeypatch.setattr(io,'parse_json',swap)
    assert io.authenticated_json(pth,hashlib.sha256(good).hexdigest())=={'count':1}


@pytest.mark.parametrize('field',['n_mtl_units','proportion_category_selective'])
def test_json_bool_is_not_number(ref,tmp_path,field):
    out=emit(tmp_path/'out',ref);mutate_json(out/'results.json',lambda r:r.__setitem__(field,True))
    with pytest.raises(AssertionError):p.validate_output_directory(out,ref)


def test_metadata_optional_extras(ref,tmp_path):
    out=emit(tmp_path/'out',ref)
    mutate_json(out/'run_metadata.json',lambda r:r.update(software_versions={'other':'equivalent'},warnings=['Manufactured message'],optional_notes={'anything':1}))
    (out/'findings.md').write_text('A free-form report with no mandatory statistical words.')
    p.validate_output_directory(out,ref)
