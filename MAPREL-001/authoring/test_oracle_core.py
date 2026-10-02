"""Manufactured arrays only; no IO, source assets, reference bank or network."""
import warnings

import numpy as np
import pytest
from neuromaps.nulls.spins import gen_spinsamples

import oracle_core as c


def sphere(n=12):
    rng = np.random.RandomState(123)
    xyz = rng.normal(size=(n, 3))
    xyz = 100*xyz/np.linalg.norm(xyz, axis=1)[:, None]
    return xyz, np.repeat([0, 1], n//2), np.arange(1, n+1)


@pytest.mark.parametrize('seed',[0, 1, 2**32-1])
def test_coupled_proper_rotation_and_private_rng(seed):
    left, right = c.rotation_pair(np.random.RandomState(seed))
    reflect = np.diag([-1, 1, 1])
    assert np.allclose(left.T@left, np.eye(3), rtol=0, atol=2e-15)
    assert np.linalg.det(left) == pytest.approx(1., abs=2e-15)
    assert np.array_equal(right, reflect@left@reflect)
    assert np.array_equal(left, c.rotation_pair(np.random.RandomState(seed))[0])


@pytest.mark.parametrize('method',c.METHODS)
@pytest.mark.parametrize('seed',[0, 19])
def test_exact_pinned_package_indices_and_costs(method,seed):
    xyz, hemi, ids = sphere()
    result = c.generate_spins(xyz, hemi, ids, method=method, seed=seed, count=100)
    expected, costs = gen_spinsamples(xyz, hemi, n_rotate=100, seed=seed,
                                      method=method, check_duplicates=True, return_cost=True)
    assert np.array_equal(result['spin_parcel_ids'], ids[expected])
    assert np.array_equal(result['assignment_cost'], costs)
    assert np.all(hemi[result['spin_parcel_ids']-1] == hemi[:, None])
    if method != 'original':
        for column in result['spin_parcel_ids'].T:
            assert np.array_equal(np.sort(column), ids)


@pytest.mark.parametrize('method',c.METHODS)
def test_seed_prefix_and_reordered_geometry(method):
    xyz, hemi, ids = sphere()
    small = c.generate_spins(xyz, hemi, ids, method=method, seed=3, count=100)
    order = np.arange(len(ids))[::-1]
    large = c.generate_spins(xyz[order], hemi[order], ids[order], method=method, seed=3, count=103)
    assert np.array_equal(small['spin_parcel_ids'], large['spin_parcel_ids'][:, :100])
    assert np.array_equal(large['parcel_ids'], ids)


@pytest.mark.parametrize('method',c.METHODS)
def test_exact_assignment_tie_matches_pinned_method(method):
    xyz = np.array([[100., 0, 0], [100., 0, 0], [0, 100., 0],
                    [100., 0, 0], [100., 0, 0], [0, 100., 0]])
    hemi = np.repeat([0, 1], 3); ids = np.arange(1, 7)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        out = c._columns(xyz, hemi, ids, method, 4, 5)
        expected = gen_spinsamples(xyz, hemi, n_rotate=5, method=method, seed=4)
    assert np.array_equal(out['spin_parcel_ids'], ids[expected])


def test_duplicate_fallback_retains_identity_and_warns_once():
    xyz = np.array([[100., 0, 0], [100., 0, 0]])
    hemi, ids = np.array([0, 1]), np.array([1, 2])
    with pytest.warns(UserWarning) as record:
        out = c._columns(xyz, hemi, ids, 'original', 0, 2)
    assert len(record) == 1
    assert np.array_equal(out['attempts'], [500, 500])
    assert np.all(out['retained_duplicate'])
    assert np.array_equal(out['spin_parcel_ids'], np.tile(ids[:, None], (1, 2)))


@pytest.mark.parametrize('method',c.METHODS)
def test_assignment_orientation_and_original_many_to_one(method):
    coor = np.array([[100., 0, 0], [100., 0, 0], [0, 100., 0]])
    columns, costs = c.assign(coor, np.eye(3), method)
    assert np.array_equal(costs, [0., 0., 0.])
    if method == 'original':
        assert len(np.unique(columns)) == 2
    else:
        assert np.array_equal(np.sort(columns), [0, 1, 2])


@pytest.mark.parametrize('method,seed,count',[
    ('unknown',0,100), ('original',True,100), ('vasa',0.,100),
    ('hungarian',-1,100), ('original',2**32,100), ('original',0,True),
    ('original',0,99), ('original',0,4097), ('original',0,100.)])
def test_public_configuration_bounds(method,seed,count):
    with pytest.raises(ValueError):c.configuration(method,seed,count)


@pytest.mark.parametrize('seed,count',[(0,100),(2**32-1,4096)])
def test_public_configuration_boundaries(seed,count):
    assert c.configuration('hungarian',seed,count) == ('hungarian',seed,count)


@pytest.mark.parametrize('mutate',[
    lambda x,h,p:(x*np.nan,h,p), lambda x,h,p:(x,h*0,p),
    lambda x,h,p:(x,h,np.ones_like(p)), lambda x,h,p:(x[:-1],h,p),
    lambda x,h,p:(x,h,np.zeros_like(p)), lambda x,h,p:(x, np.ones((2,6)),p),
    lambda x,h,p:(np.zeros_like(x),h,p)])
def test_geometry_failures(mutate):
    with pytest.raises(ValueError):c.geometry(*mutate(*sphere()))


@pytest.mark.parametrize('values',[[True,1], [1,False], np.array([True,False]), [1,np.inf], ['1','2']])
def test_strict_finite_nonboolean_values(values):
    with pytest.raises(ValueError):c.real_array(values)


def replay(a,b,spins):
    ids=np.arange(1,len(a)+1)
    support=c.source_fidelity(a,b,a,b,ids,spins)
    return c.derive(a,b,ids,spins,np.arange(spins.shape[1]),support)


def test_signed_observed_and_inclusive_identity_ties():
    a=np.arange(1.,5.);b=-a;spins=np.tile(np.arange(1,5)[:,None],(1,3))
    out=replay(a,b,spins)
    assert out['pearson_r']==pytest.approx(-1., abs=1e-15)
    assert out['n_exceedances']==3 and out['p_spin']==1
    assert out['significant_after_spatial_null'] is False


@pytest.mark.parametrize('a,b,state',[
    ([.1]*4,[1,2,3,4],'inactive_gradient'),
    ([1,2,3,4],[.1]*4,'inactive_thickness'),
    ([.1]*4,[.2]*4,'inactive_both')])
def test_constant_observed_preserves_all_null_slots(a,b,state):
    spins=np.tile(np.arange(1,5)[:,None],(1,4));out=replay(a,b,spins)
    assert out['observed_status']==state and out['pearson_r'] is None
    assert out['n_null_expected']==4 and len(out['null_distribution'])==4
    assert out['p_spin'] is None and out['n_exceedances'] is None
    assert out['significant_after_spatial_null'] is None


def test_one_undefined_original_null_does_not_shrink_denominator():
    spins=np.array([[1,1],[2,1],[3,1],[4,1]])
    out=replay([1,2,3,4],[4,2,1,3],spins)
    assert out['observed_status']=='ok'
    assert out['n_null_defined']==1 and out['n_null_expected']==2
    assert out['null_distribution'][1]['r'] is None
    assert out['p_spin'] is None and out['p_spin_denominator']==3


def test_constant_source_cannot_be_activated_by_accepted_rounding():
    ids=np.arange(1,5);a=np.full(4,.1);b=np.arange(4.)
    submitted=a+np.array([0,1,-1,2])*1e-8;spins=ids[:,None]
    support=c.source_fidelity(submitted,b,a,b,ids,spins)
    assert support['gradient'] is False and not support['null_gradient'].any()
    assert c.derive(submitted,b,ids,spins,[0],support)['pearson_r'] is None


@pytest.mark.parametrize('transform',[lambda a:-a,lambda a:a*2,lambda a:a+2])
def test_fixed_published_sign_offset_and_scale_bound(transform):
    a=np.array([1.,2,3,4]);b=a[::-1];ids=np.arange(1,5)
    with pytest.raises(ValueError,match='signed source fidelity'):
        c.source_fidelity(transform(a),b,a,b,ids,ids[:,None])


def test_original_remap_relative_fidelity_prevents_low_variance_amplification():
    a=np.array([0.,1e-10,1.,-1.]);b=np.array([2.,1,3,4]);ids=np.arange(1,5)
    accepted=a.copy();accepted[1]+=1e-8
    spins=np.array([[1],[2],[1],[2]])
    assert c.relative_fidelity(accepted,a)<1e-6
    with pytest.raises(ValueError,match='remapped source fidelity'):
        c.source_fidelity(accepted,b,a,b,ids,spins)


def test_original_remap_recenters_and_renormalizes():
    a=np.array([0.,1.,3.,9.]);b=np.array([4.,1.,2.,5.]);spins=np.array([[1],[1],[2],[3]])
    out=replay(a,b,spins)
    assert out['null_distribution'][0]['r']==pytest.approx(np.corrcoef(a[spins[:,0]-1],b)[0,1],abs=1e-15)


def test_coherent_parcel_rotation_permutations():
    a=np.array([1.,4,2,7]);b=np.array([2.,3,1,5]);ids=np.arange(1,5)
    spins=np.array([[1,2,4],[2,3,3],[3,4,2],[4,1,1]])
    support=c.source_fidelity(a,b,a,b,ids,spins);expected=c.derive(a,b,ids,spins,[0,1,2],support)
    row=np.array([2,0,3,1]);col=np.array([2,0,1]);permuted=spins[row][:,col]
    support=c.source_fidelity(a[row],b[row],a[row],b[row],ids[row],permuted)
    assert c.derive(a[row],b[row],ids[row],permuted,col,support)==expected


def test_strict_alpha_boundary_without_float_comparator(monkeypatch):
    # Observed1; nineteen null zeros: numerator1/denominator20 == .05, not significant.
    values=iter([1.]+[0.]*19)
    monkeypatch.setattr(c,'pearson',lambda a,b:next(values))
    ids=np.arange(1,5);spins=np.tile(ids[:,None],(1,19))
    support=dict(gradient=True,thickness=True,null_gradient=np.ones(19,dtype=bool))
    out=c.derive([1,2,3,4],[4,3,2,1],ids,spins,np.arange(19),support)
    assert out['p_spin']==.05 and out['significant_after_spatial_null'] is False


def test_very_small_finite_maps_no_arbitrary_variance_cutoff():
    a=np.array([0.,1.,3.,7.])*1e-280
    assert c.active(a) and c.pearson(a,-a)==pytest.approx(-1.,abs=1e-15)


@pytest.mark.parametrize('rotations',[[0,0],[0,2],[False,1],[0.,1.5]])
def test_rotation_membership_typed_and_complete(rotations):
    ids=np.arange(1,5);spins=np.tile(ids[:,None],(1,2))
    support=dict(gradient=True,thickness=True,null_gradient=np.ones(2,dtype=bool))
    with pytest.raises(ValueError):c.derive([1,2,3,4],[4,3,2,1],ids,spins,rotations,support)
