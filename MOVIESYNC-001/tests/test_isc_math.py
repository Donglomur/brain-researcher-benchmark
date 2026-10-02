"""Pure manufactured vectors. No source/bank/oracle inputs or expected outcome bands."""
import math
import numpy as np
import pytest

import isc_math as m


def vectors(n=4, t=12, k=3):
    rng = np.random.default_rng(2)
    return rng.normal(size=(n,t,k))


@pytest.mark.parametrize("bad", [np.array([True]), np.array([1+0j]), np.array(["1"]),
                                np.array([np.nan]), np.array([np.inf]), np.array([object()])])
def test_typed_finite_inputs(bad):
    with pytest.raises(ValueError): m.real_array(bad, "test")


@pytest.mark.parametrize("constant", [0., .1, -1e10, 1e-100])
def test_exact_constant_center_and_support(constant):
    x = np.full((4,12,3), constant)
    assert np.array_equal(m.centered(x[0,:,0]), np.zeros(12))
    support = m.support(x)
    assert not support["person_active"].any()
    assert not support["template_active"].any()
    out = m.replay(x, support)
    assert out["headline"] == {"pairwise":None, "loo":None}
    assert len(out["pairs"]) == 18


def test_identical_series_valid_even_identical_person_summaries():
    x = np.tile(np.arange(12.)[None,:,None], (4,1,3))
    result = m.replay(x, m.support(x))
    assert result["headline"] == {"pairwise":1., "loo":1.}
    assert all(v == 1. for v in result["pairs"].values())


def test_negative_isc_and_loo_below_pairwise_are_valid():
    # Three equal-length centered vectors at 120 degrees; all pair r=-1/2,
    # each leave-one-out mean is antiparallel to the held-out person.
    q = np.array([[1.,-1.,0.], [1.,1.,-2.]])
    q[0] /= np.linalg.norm(q[0]); q[1] /= np.linalg.norm(q[1])
    x = np.array([math.cos(a)*q[0]+math.sin(a)*q[1]
                  for a in (0.,2*math.pi/3,4*math.pi/3)])[:,:,None]
    result = m.replay(x, m.support(x))
    assert result["headline"]["pairwise"] == pytest.approx(-.5)
    assert result["headline"]["loo"] == pytest.approx(-1.)


def test_loo_excludes_self_and_is_not_pairwise_relabel():
    x = vectors()
    result = m.replay(x, m.support(x))
    for i in range(4):
        for r in range(3):
            expected = np.corrcoef(x[i,:,r], np.delete(x[:,:,r],i,axis=0).mean(axis=0))[0,1]
            assert result["per_person_region"][i][r]["loo"] == pytest.approx(expected, abs=2e-15)


def test_full_pair_family_and_complete_denominators():
    x = vectors()
    result = m.replay(x, m.support(x))
    assert len(result["pairs"]) == 4*3//2*3
    for r in range(3):
        assert result["per_region"][r]["n_pairs_expected"] == 6
        assert result["per_region"][r]["pairwise"] == pytest.approx(
            sum(result["per_person_region"][i][r]["pairwise"] for i in range(4))/4)


def test_one_inactive_person_propagates_no_available_case_means():
    x = vectors(); x[0,:,0] = 0
    out = m.replay(x, m.support(x))
    assert out["per_person_region"][1][0]["n_pairs_defined"] == 2
    assert out["per_person_region"][1][0]["n_pairs_expected"] == 3
    assert out["per_person_region"][1][0]["pairwise"] is None
    assert out["per_region"][0]["pairwise"] is None
    assert out["headline"]["pairwise"] is None


def test_constant_contributor_does_not_invalidate_variable_loo_template():
    x = vectors(); x[0] = 0
    basis = m.support(x)
    out = m.replay(x, basis)
    assert out["headline"]["pairwise"] is None
    for i in range(1, 4):
        for r in range(3):
            assert out["per_person_region"][i][r]["pairwise"] is None
            assert out["per_person_region"][i][r]["loo"] is not None
            expected = np.corrcoef(x[i,:,r], np.delete(x[:,:,r],i,axis=0).mean(0))[0,1]
            assert out["per_person_region"][i][r]["loo"] == pytest.approx(expected)


def test_cancelling_template_retained_undefined_despite_jitter():
    x = np.array([[1.,0.,-1.,0.], [0.,1.,0.,-1.], [0.,-1.,0.,1.]])[:,:,None]
    canon = m.support(x)
    assert canon["person_active"].all() and not canon["template_active"][0,0]
    submitted = x.copy(); submitted[1,0,0] += 1e-9
    support = m.source_fidelity(submitted, x)
    result = m.replay(submitted, support)
    assert result["per_person_region"][0][0]["loo"] is None
    assert result["per_person_region"][0][0]["pairwise"] is not None
    assert result["headline"]["loo"] is None


def test_active_template_fidelity_blocks_near_cancellation_fabrication():
    x = np.array([[1.,0.,-1.,0.], [0.,1.,0.,-1.], [1e-9,-1.,-1e-9,1.]])[:,:,None]
    assert m.support(x)["template_active"][0,0]
    submitted = x.copy(); submitted[1,0,0] += 1e-8
    # Every person's pointwise and centered budgets can pass while template
    # direction changes drastically; explicit template fidelity must reject.
    with pytest.raises(ValueError, match="template centered fidelity"):
        m.source_fidelity(submitted, x)


def test_active_person_relative_fidelity_has_no_absolute_floor():
    x = vectors()*1e-10
    submitted = x.copy(); submitted[0,0,0] += 1e-10
    with pytest.raises(ValueError, match="person centered fidelity"):
        m.source_fidelity(submitted, x)


def test_rounding_and_coherent_axes_are_equivalent_when_within_budgets():
    x = vectors()
    sub = x.astype(np.float32).astype(np.float64)
    basis = m.source_fidelity(sub, x)
    out = m.replay(sub, basis)
    perm = np.array([2,0,3,1])
    changed = m.replay(sub[perm], {key:val[perm] for key,val in basis.items() if key.endswith("active")})
    assert changed["headline"] == pytest.approx(out["headline"], abs=2e-15)


def test_active_support_not_reclassified_after_serialization():
    q = np.array([-1.,1.,-1.,1.])*1.00000001e-12
    x = np.tile(q[None,:,None], (3,1,1))
    sub = x*(1-1e-7)
    source = m.source_fidelity(sub, x)
    assert source["person_active"].all()
    assert not m.support(sub)["person_active"].any()
    assert m.replay(sub, source)["headline"]["pairwise"] == pytest.approx(1.)


def test_pointwise_gate_independent_of_centered_shift_invariance():
    x = vectors()
    with pytest.raises(ValueError, match="pointwise"):
        m.source_fidelity(x+1., x)


def test_stable_l2_tiny_and_large():
    assert m.stable_l2(np.array([3e-200,4e-200])) == pytest.approx(5e-200, abs=0, rel=1e-14)
    assert m.stable_l2(np.array([3e200,4e200])) == pytest.approx(5e200)


def test_complete_mean_never_drops_null_or_flips_sign():
    assert m.complete_mean([1.,None]) is None
    assert m.complete_mean([]) is None
    assert m.complete_mean([-.5,.1]) == pytest.approx(-.2)


@pytest.mark.parametrize("shape", [(1,12,3),(4,1,3),(4,12,0)])
def test_bad_series_support(shape):
    with pytest.raises(ValueError): m.support(np.zeros(shape))
