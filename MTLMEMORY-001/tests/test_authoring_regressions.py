"""Source-free mechanics, not scientific evidence or substitute reference banks."""
import copy
from pathlib import Path
import numpy as np
import pytest
from scipy.stats import mannwhitneyu
import population_contract as q
import proof_of_work as proof
from fixture_support import toy_ref,emit,write_csv


@pytest.mark.parametrize('value',[True,False,'true','false','nan','inf','1.5','9007199254740993.1'])
def test_invalid_integer(value):
    with pytest.raises(AssertionError): q.integer(value)


@pytest.mark.parametrize('value',['9007199254740993','9.007199254740993e15','1.0','1e0','-12'])
def test_exact_integer_notation(value):
    assert str(q.integer(value)) in ('9007199254740993','1','-12')


@pytest.mark.parametrize('value',['1e0','0.0','2','-1','yes',1.,None])
def test_strict_boolean_tokens(value):
    with pytest.raises(AssertionError): q.flag(value)


@pytest.mark.parametrize('value',['0','1','TRUE','False',True,False,0,1])
def test_boolean_tokens(value): assert type(q.flag(value)) is bool


@pytest.mark.parametrize('token',['NaN','Infinity','1e999'])
def test_nonfinite_json(tmp_path,token):
    p=tmp_path/'x.json'; p.write_text('{"value":'+token+'}')
    with pytest.raises(AssertionError): q.json_load(p)


def test_duplicate_json_keys(tmp_path):
    p=tmp_path/'x.json';p.write_text('{"x":1,"x":1}')
    with pytest.raises(AssertionError): q.json_load(p)


@pytest.mark.parametrize('count,label',[
    ([1,1,1,1],[0,0,1,1]),([0,1,2,3,4,5],[0,0,0,1,1,1]),
    ([5,4,4,0,1,2],[0,0,0,1,1,1]),([1,4,3,3,0,1,4],[1,0,1,0,1,0,1])])
def test_direct_u_matches_independent_scipy_fixture(count,label):
    c=np.asarray(count);y=np.asarray(label);result=q.rank_measure(c,y)
    native=mannwhitneyu(c[y==1],c[y==0],alternative='two-sided',method='asymptotic',use_continuity=True)
    assert result['u_old_twice'] == int(2*native.statistic)
    assert result['p'] == pytest.approx(native.pvalue,abs=1e-15)


@pytest.mark.parametrize('n0,n1',[(0,0),(3,0),(0,4)])
def test_missing_class_is_undefined(n0,n1):
    a=q.rank_measure(np.zeros(n0+n1,dtype=int),np.array([0]*n0+[1]*n1,dtype=int))
    assert a['status']=='insufficient_class_support' and a['auc_old'] is None and not a['selected']


def test_unsupported_does_not_consume_rng():
    a=toy_ref(labels=[0,0,0,1,1,1],counts=[np.arange(6)])
    assert not q.generate_masks(a).any()
    rows=q.analyze(a)['split_events']; assert len(rows)==60
    assert all(r['n_test_new'] is None and not r['train_selected'] for r in rows)


def test_rng_global_not_reset_per_unit():
    r=toy_ref(); n=len(r['spike_count'])//2
    assert not np.array_equal(r['train_membership'][:,:n],r['train_membership'][:,n:])
    rng=np.random.Generator(np.random.PCG64(0)); mask=np.zeros_like(r['train_membership'])
    for b in range(60):
        for unit in range(2):
            rows=np.flatnonzero(r['response_unit_index']==unit)
            for label in (0,1):
                local=np.flatnonzero(r['source_label'][rows]==label)
                mask[b,rows[rng.choice(local,len(local)//2,replace=False,shuffle=True)]]=True
    assert np.array_equal(mask,r['train_membership'])


def test_full_and_conditional_denominators_are_distinct():
    r=toy_ref(); rows=copy.deepcopy(q.analyze(r)['neurons'])
    rows[0].update(memory_selective=True,same_trial_auc=.8,heldout_eligible=False,n_selected_splits=4,conditional_auc=.2)
    rows[1].update(memory_selective=False,heldout_eligible=True,n_selected_splits=5,conditional_auc=.4)
    summary=q.summarize(r,rows,q.POPULATIONS[1])
    assert summary['populations'][q.POPULATIONS[0]]['mean_auc']==.8
    assert summary['memory_selective_new_old_auc']==.4
    assert summary['population_overlap']==dict(full_only=1,conditional_only=1,both=0,neither=0)


@pytest.mark.parametrize('n_selected',[0,1,4,5,60])
def test_conditional_minimum_support_and_below_chance(n_selected):
    # Deliberately controlled numerical masks, NOT a source/RNG fixture bank.
    r=toy_ref(counts=[np.array([0]*4+[10]*4+[0]*4+[10]*4)])
    ordinary=np.zeros(16,dtype=bool);ordinary[[0,1,4,5,8,9,12,13]]=True
    selected=np.zeros(16,dtype=bool);selected[[0,1,2,3,12,13,14,15]]=True
    r['train_membership'][:]=ordinary;r['train_membership'][:n_selected]=selected
    row=q.analyze(r)['neurons'][0]
    assert not row['memory_selective']
    assert row['n_selected_splits']==n_selected
    assert row['conditional_auc']==(0. if n_selected else None)
    assert row['heldout_eligible']==(n_selected>=5)


def test_skipped_unsupported_unit_consumes_no_rng_draw():
    labels=np.array([0]*3+[1]*3+[0]*4+[1]*4)
    mixed=dict(unit_key=np.array(['unsupported','supported']),response_unit_index=np.array([0]*6+[1]*8),source_label=labels)
    alone=dict(unit_key=np.array(['supported']),response_unit_index=np.zeros(8,dtype=int),source_label=labels[6:])
    assert np.array_equal(q.generate_masks(mixed)[:,6:],q.generate_masks(alone))


def test_zero_units_stays_defined_accounting():
    r=toy_ref(counts=[]);derived=q.analyze(r);result=q.summarize(r,derived['neurons'],q.POPULATIONS[1])
    assert result['n_mtl_units']==0 and result['proportion_memory_selective'] is None
    assert result['headline_status']=='empty_population' and result['memory_selective_new_old_auc'] is None


@pytest.mark.parametrize('headline',q.POPULATIONS)
def test_complete_synthetic_parser_fixture(tmp_path,headline):
    r=toy_ref(); q.validate_output_directory(emit(tmp_path,r,headline),r)


def test_empty_population_not_chance_gate(tmp_path):
    r=toy_ref(counts=[np.zeros(16,dtype=int)]); emit(tmp_path,r);q.validate_output_directory(tmp_path,r)
    result=q.json_load(tmp_path/'results.json'); assert result['memory_selective_new_old_auc'] is None


def test_independent_rounding_opposite_endpoints(tmp_path):
    r=toy_ref(); emit(tmp_path,r)
    for name in ('neurons.csv','split_events.csv'):
        spec=r['metadata']['method_contract']['outputs'][name];rows=q.csv_load(tmp_path/name,spec)
        for row in rows:
            for key in ('auc_old','train_auc_old','test_auc_old'):
                if row.get(key) is not None and 0<row[key]<1: row[key]+=9e-9
            for key in ('same_trial_auc','test_directed_auc','conditional_auc'):
                if row.get(key) is not None and 0<row[key]<1: row[key]-=9e-9
        write_csv(tmp_path/name,rows,spec['columns'])
    q.validate_output_directory(tmp_path,r)


def test_outside_individual_bound_rejected(tmp_path):
    r=toy_ref();emit(tmp_path,r);spec=r['metadata']['method_contract']['outputs']['neurons.csv']
    rows=q.csv_load(tmp_path/'neurons.csv',spec);rows[1]['auc_old']+=1.1e-8
    write_csv(tmp_path/'neurons.csv',rows,spec['columns'])
    with pytest.raises(AssertionError,match='source/declared'): q.validate_output_directory(tmp_path,r)


def test_cache_identity_changes_every_primitive():
    r=toy_ref();a=q.analyze(r);assert q.analyze(r) is a
    r['spike_count'][0]+=1; assert q.analyze(r) is not a
    before=q.primitive_fingerprint(r);r['train_membership'][0,0]=not r['train_membership'][0,0]
    assert before!=q.primitive_fingerprint(r)


def test_obsolete_bank_always_rejected(tmp_path):
    p=tmp_path/'old.npz';np.savez(p,ref_stats=np.asarray('{}'))
    with pytest.raises(AssertionError,match='Obsolete'):proof.load_reference(p)


def test_public_hash_matches_frozen_file():
    raw=(Path(__file__).parents[1]/'environment/method_contract.json').read_text()
    assert proof.digest(raw)==q.METHOD_SHA256


def test_offline_python3_entrypoint():
    p=Path(__file__).with_name('test.sh');s=p.read_text()
    assert 'python3 -m pytest' in s and not any(x in s for x in ('curl','pip install','apt-get','uvx'))
    assert p.stat().st_mode & 0o111


@pytest.mark.parametrize('actual,expected',[(True,1),(1,True),('1',1),({'x':True},{'x':1})])
def test_json_types_no_boolean_alias(actual,expected):
    with pytest.raises(AssertionError):q.match(actual,expected)
