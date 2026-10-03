"""Manufactured cross-route checks; only fixtures import the two implementations."""
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path); result=importlib.util.module_from_spec(spec)
    sys.modules[name]=result;spec.loader.exec_module(result);return result


reader=module('artifact_reader',ROOT/'tests'/'artifact_reader.py')
math_ref=module('reference_math',ROOT/'tests'/'reference_math.py')
ref=module('source_reference',ROOT/'tests'/'source_reference.py')
oracle=module('oracle_kinetics',ROOT/'solution'/'kinetics.py')
fixture_module=module('manufactured_oracle_source',ROOT/'authoring'/'test_source_reader.py')
manufactured=fixture_module.manufactured


def test_independent_source_structure_and_composite(manufactured,monkeypatch):
    root,docs,_,_=manufactured
    for name in ('SOURCE_SHA','METHOD_SHA','SCHEMA_SHA'):
        monkeypatch.setattr(ref,name,getattr(fixture_module.r,name))
    expected=fixture_module.load(manufactured)
    actual=ref.reconstruct(root,docs/'source_manifest.json',docs/'method_contract.json',docs/'output_schema.json')
    assert actual['source_files']==expected['source_files'] and actual['source_observed']==expected['source_observed']
    for sid in ref.SUBJECTS:
        np.testing.assert_array_equal(actual['persons'][sid]['tissue_concentration'],[2,3,4])
        assert all(x['status']=='insufficient_fit_rows' for x in actual['persons'][sid]['models'].values())


def test_private_authority_unfrozen_rejects_before_sources(tmp_path,monkeypatch):
    monkeypatch.setattr(ref,'SCHEMA_SHA',None)
    with pytest.raises(ValueError,match='unfrozen'):
        ref.reconstruct(tmp_path,tmp_path/'missing',tmp_path/'missing',tmp_path/'missing')


@pytest.mark.parametrize('assumption',oracle.ASSUMPTIONS)
def test_independent_integrals_and_both_models(assumption):
    edges=np.array([0,300,900,1800,2400,3000,3600,4200],dtype=float)
    ct=np.array([1,3,2,1.8,1.7,1.5,1.3]); times=np.array([0,300,1200,2400,4200.])
    plasma=np.array([0,8,5,3,1.]); fraction=np.array([0,.95,.8,.65,.5])
    own=math_ref.primitives(edges[:-1],edges[1:],ct,times,plasma,fraction)
    mid,it=oracle.tissue_integral(edges[:-1],edges[1:],ct)
    knots=oracle.parent_knots(times,plasma,fraction,assumption)
    ip=oracle.input_integral(knots['times_min'],knots['values'],mid)
    arm=oracle.ASSUMPTIONS.index(assumption)
    np.testing.assert_allclose(own['tissue_integral'],it,rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(own['plasma_integral'][:,arm],ip,rtol=1e-12,atol=1e-12)
    for estimator in oracle.ESTIMATORS:
        a=math_ref.fit(ct,own,arm,estimator);b=oracle.fit_model(mid,ct,it,ip,estimator)
        assert a['status']==b['status']=='ok' and a['rank']==b['rank']==2
        np.testing.assert_allclose(a['coefficients'],b['coefficients'],rtol=1e-10,atol=1e-12)


def test_partial_support_keeps_slots_and_unavailable_fits():
    p=math_ref.primitives([0,1200,2400,3600],[1200,2400,3600,4800],[1,2,3,4],[0,2000],[0,1],[0,1])
    assert p['plasma_integral_defined'][:,0].tolist()==[True,True,False,False]
    assert math_ref.fit([1,2,3,4],p,0,'logan')['status']=='input_time_support_unavailable'


def test_ma1_fidelity_and_source_support_own_replay():
    source=np.array([1e-300,-1e-300]);actual=source*[1+1e-7,1]
    accepted=math_ref.accept_coefficients(actual,source,'ma1',True)
    assert math_ref.replay('ma1',accepted)['vt']>1
    with pytest.raises(ValueError):math_ref.accept_coefficients([1e-9,-1e-300],source,'ma1',True)
    assert math_ref.replay('ma1',[1,1e-9],False)['status']=='ma1_denominator_unresolved'


@pytest.mark.parametrize('values',[[2.]*7,[-3.,-2.,-1.,0.,1.,2.,3.],[1.]*6+[None],
    [float(np.nextafter(0.,1.))]+[0.]*6,[float(2**50)+.25*i for i in range(7)]])
def test_independent_group_replay(values):
    a=math_ref.group(values);b=oracle.complete_summary(values)
    assert a==b


def test_source_only_private_modules_do_not_import_oracle():
    import ast
    for name in ('source_reference.py','reference_math.py'):
        tree=ast.parse((ROOT/'tests'/name).read_text())
        imports=[n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
        imports += [a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
        assert not any('solution' in n or 'kinetics' in n or 'stager' in n for n in imports)
