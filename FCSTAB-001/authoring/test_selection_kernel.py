"""Manufactured-only fixtures. No source paths, data, network, or oracle imports."""
import copy
import importlib.util
import math
from pathlib import Path
import sys

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location("fcstab_selection_kernel",Path(__file__).resolve().parents[1]/"environment"/"selection_kernel.py")
k = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = k
SPEC.loader.exec_module(k)


@pytest.fixture
def basis():
    z = np.random.Generator(np.random.PCG64(918)).normal(0,.2,(4,3,15))
    pairs = np.array([(i,j) for i in range(1,7) for j in range(i+1,7)])
    return z,["101","102","103","104"],pairs


def anchors(step=2.0**-20, scale=1.):
    first = np.full(40,1.)*scale
    second = np.array([1.125-step,1.125+step]*20)*scale
    return second-first,abs(first),abs(second)


@pytest.mark.parametrize("bad",[[float("nan")],[float("inf")],[True],np.array([1j]),np.array([object()])])
def test_nonfinite_or_invalid_type(bad):
    with pytest.raises(k.ContractError):
        k.numeric(bad,1)


def test_empty_mean_sd():
    for fn in (k.mean,k.population_sd):
        with pytest.raises(k.ContractError):
            fn([])


@pytest.mark.parametrize("value",[0.,.1,-3.,2.0**-600])
def test_exact_constant_stable(value):
    x = np.full(196,value)
    assert k.mean(x)==value
    assert k.population_sd(x)==0
    assert k.stable_l2(k.centered(x))==0


def test_population_sd_definition_and_threshold_equality():
    x = np.array([-1e-8,1e-8])
    assert k.population_sd(x)==1e-8
    assert not (k.population_sd(x)>1e-8)
    assert k.population_sd([-2.,0.,2.])==pytest.approx(math.sqrt(8/3))


@pytest.mark.parametrize("scale",[1.,2.0**-600,2.0**500])
def test_pearson_scale_stable(scale):
    a = np.array([-3.,-1.,1.,3.])*scale
    assert k.pearson(a,a)==pytest.approx(1.,abs=1e-15)
    assert k.pearson(a,-a)==pytest.approx(-1.,abs=1e-15)


def test_pearson_undefined():
    assert k.pearson([1],[2]) is None
    assert k.pearson([1,1],[2,3]) is None


def test_fisher_caps_perfect_correlation():
    a = np.arange(8.)
    z = k.fisher_z(np.column_stack([a,2*a,-a]))
    np.testing.assert_allclose(z,[k.ZCAP,-k.ZCAP,-k.ZCAP],rtol=0,atol=1e-15)


@pytest.mark.parametrize("x",[np.ones((5,2)),np.ones((1,2)),np.ones((5,1))])
def test_fisher_insufficient_or_constant(x):
    with pytest.raises(k.ContractError):
        k.fisher_z(x)


def test_ties_use_original_pairs_and_all_other_subjects():
    pairs = np.array([(1,j) for j in range(2,22)])
    z = np.full((3,3,20),-.25)
    out = k.select_sets(z,["1","2","3"],pairs)
    for sid in out:
        assert out[sid]["forward_edge_indices"]==[0,1]
        assert out[sid]["reverse_edge_indices"]==[0,1]
        assert out[sid]["independent_edge_indices"]==[0,1]
        assert set(out[sid]["training_subject_ids"])==({"1","2","3"}-{sid})


def test_signed_not_absolute_ranking():
    pairs = np.array([[1,2],[1,3],[2,3]])
    z = np.broadcast_to(np.array([-.9,-.2,-.5]),(3,3,3)).copy()
    assert k.select_sets(z,["1","2","3"],pairs)["1"]["forward_edge_indices"]==[1]


def test_random_schedule_exact_and_k_floor():
    pairs = np.array([(1,j) for j in range(2,27)])
    z = np.zeros((3,3,25))
    ids = ["a","b","c"]
    expected = np.random.Generator(np.random.PCG64(0))
    out = k.select_sets(z,ids,pairs)
    for sid in ids:
        assert out[sid]["random_edge_indices"]==sorted(expected.choice(25,size=2,replace=False).tolist())


@pytest.mark.parametrize("defect",["duplicate_pair","reverse_pair","unsorted_pair","float_pair","duplicate_subject","bad_segment"])
def test_selection_axis_errors(basis,defect):
    z, ids, p = copy.deepcopy(basis)
    if defect=="duplicate_pair": p[1]=p[0]
    if defect=="reverse_pair": p[0]=p[0][::-1]
    if defect=="unsorted_pair": p=p[::-1]
    if defect=="float_pair": p=p.astype(float)
    if defect=="duplicate_subject": ids[1]=ids[0]
    if defect=="bad_segment": z=z[:,:2]
    with pytest.raises(k.ContractError):
        k.select_sets(z,ids,p)


def test_edge_translation_invariant_conditioned_fidelity():
    source = np.array([-.4,-.1,.2,.3])
    assert k.edge_fidelity(source+1e-8,source)
    with pytest.raises(k.ContractError,match="centered"):
        k.edge_fidelity(source+np.array([0.,0.,1e-6,0.]),source)


def test_constant_clamped_edges_jitter_cannot_create_reliability():
    source = np.full(8,k.ZCAP)
    accepted = source + np.array([-1e-8,1e-8]*4)
    out = k.reliability(accepted,accepted,source,source)
    assert out=={"edge_pearson":None,"edge_spearman":None,"status":"source_constant"}


def test_single_edge_correlation_null():
    out = k.reliability([.1],[.2],[.1],[.2])
    assert out["status"]=="source_insufficient_edges"
    assert out["edge_pearson"] is out["edge_spearman"] is None


def test_spearman_uses_accepted_exact_ties_not_source_coefficient():
    source = np.array([0.,1.,1.+1e-8,2.])
    accepted = np.array([0.,1.,1.,2.])
    second = np.array([0.,1.,2.,3.])
    out = k.reliability(accepted,second,source,second)
    expected = k.pearson(np.array([1.,2.5,2.5,4.]),np.arange(1.,5.))
    assert out["edge_spearman"]==pytest.approx(expected)
    assert out["edge_spearman"]<1


@pytest.mark.parametrize("scale",[1.,2.0**-40])
def test_representable_conditioning_active_and_uniform_shift_rejected(scale):
    d, f, s = anchors(scale=scale)
    status = k.source_delta_resolution(d,f,s)
    assert status["status"]=="active"
    out = k.group_summary(d,d,f,s)
    assert out["inference_status"]=="ok"
    with pytest.raises(k.ContractError,match="full-error"):
        k.group_summary(d+(2.0**-24)*scale,d,f,s)


@pytest.mark.parametrize("scale",[1.,2.0**-40])
def test_nonconstant_numerical_resolution_not_constant(scale):
    d,f,s = anchors(step=2.0**-52,scale=scale)
    out = k.group_summary(d,d,f,s)
    assert out["source_support"]["source_centered_l2"]>0
    assert out["inference_status"]=="numerical_resolution"
    assert out["t"] is out["p"] is out["ci95_lo"] is out["ci95_hi"] is None
    assert out["equivalence"]["equivalent_within_margin"] is None


@pytest.mark.parametrize("level",[0.,-.05,.05,.125])
def test_source_constant_jitter_remains_inference_null_own_descriptors(level):
    d = np.full(40,level)
    a = d + np.array([-1e-8,1e-8]*20)
    out = k.group_summary(a,d,np.ones(40),np.ones(40))
    assert out["inference_status"]=="source_zero_variance"
    assert out["delta_sd"]>0
    assert out["delta_mean"]==k.mean(a)
    assert out["n_negative"]==int(np.count_nonzero(a<0))
    assert out["t"] is out["p"] is None
    assert out["equivalence"]["tost_p"] is None


def test_tost_boundary_and_own_boolean():
    d = .05+np.array([-2.0**-10,2.0**-10]*20)
    out = k.group_summary(d,d,np.ones(40),np.ones(40))
    assert out["inference_status"]=="ok"
    assert out["equivalence"]["p_upper"]==pytest.approx(.5)
    assert out["equivalence"]["equivalent_within_margin"] is False
    zero = np.array([-2.0**-10,2.0**-10]*20)
    near = k.group_summary(zero,zero,np.ones(40),np.ones(40))
    assert near["equivalence"]["equivalent_within_margin"] is True
    assert near["equivalence"]["equivalent_within_margin"]==(near["equivalence"]["tost_p"]<.05)


def test_analyze_means_evidence_and_csv_authority_distinct(basis):
    z, ids, p = basis
    base = k.analyze(z,z,ids,p)
    rows = copy.deepcopy(base["rows"])
    for row in rows:
        row["forward_first_half"]+=2e-7
        row["forward_second_half"]+=2e-7
    out = k.analyze(z,z,ids,p,accepted_rows=rows[::-1])
    assert [r["subject_id"] for r in out["rows"]]==ids
    assert out["evidence"]==base["evidence"]
    assert out["summaries"]["forward_top_decile_connectivity"]["first_half_mean"]==k.mean([r["forward_first_half"] for r in rows])
    assert out["summaries"]["selection_schemes"]==base["summaries"]["selection_schemes"]


def test_accepted_reliability_receipts_drive_group_mean(basis):
    z, ids, p = basis
    base = k.analyze(z,z,ids,p)
    accepted = copy.deepcopy(base["accepted_reliability"])
    for row in accepted.values():
        row["edge_pearson"]*=1-1e-7
    out = k.analyze(z,z,ids,p,accepted_reliability=accepted)
    assert out["summaries"]["reliability"]["edge_pearson"]["mean"]==k.mean([accepted[s]["edge_pearson"] for s in ids])
    assert out["evidence"]==base["evidence"]


def test_all_cohort_retained_with_source_inactive_correlations():
    z = np.array([[[.1],[.2],[.15]],[[.2],[.4],[.3]],[[.3],[.2],[.25]]])
    out = k.analyze(z,z,["1","2","3"],np.array([[1,2]]))
    assert len(out["rows"])==3
    assert out["k"]==1
    rel = out["summaries"]["reliability"]["edge_pearson"]
    assert rel=={"mean":None,"n_defined":0,"n_undefined":3,"status":"undefined_member"}
    fake = copy.deepcopy(out["accepted_reliability"])
    fake["1"]["edge_pearson"]=.5
    with pytest.raises(k.ContractError,match="must be null"):
        k.analyze(z,z,["1","2","3"],np.array([[1,2]]),accepted_reliability=fake)


@pytest.mark.parametrize("defect",["duplicate","missing","extra","n_edges","boolean","nonfinite","delta"])
def test_rows_rejected(basis,defect):
    z,ids,p = basis
    rows = copy.deepcopy(k.analyze(z,z,ids,p)["rows"])
    if defect=="duplicate": rows[1]["subject_id"]=rows[0]["subject_id"]
    if defect=="missing": rows.pop()
    if defect=="extra": rows[0]["extra"]=1
    if defect=="n_edges": rows[0]["n_edges"]=14
    if defect=="boolean": rows[0]["forward_delta"]=True
    if defect=="nonfinite": rows[0]["forward_delta"]="nan"
    if defect=="delta": rows[0]["forward_delta"]+=.1
    with pytest.raises(k.ContractError):
        k.analyze(z,z,ids,p,accepted_rows=rows)


def test_import_has_no_runtime_io():
    text = Path(k.__file__).read_text()
    assert "Path(" not in text and "read_bytes" not in text and "np.load" not in text
    assert "__main__" not in text and "reference.npz" not in text
