"""Manufactured grid/SVD/filter fixtures; no original images are loaded."""
import numpy as np
import pytest
from scipy import linalg, signal

import source_numerics as n


def test_identity_resampling_and_negative_map_values():
    atlas = np.arange(24.).reshape(2,3,2,2)-12
    got = n.resample_maps(atlas,np.eye(4),(2,3,2),np.eye(4))
    np.testing.assert_array_equal(got,atlas)
    assert got.min() < 0


def test_linear_interpolation_outside_constant_zero():
    atlas = np.arange(4.)[:,None,None,None]
    affine = np.eye(4); affine[0,3] = .5
    out = n.resample_maps(atlas,np.eye(4),(4,1,1),affine)
    np.testing.assert_allclose(out[:,0,0,0],[.5,1.5,2.5,0])


def test_closed_boundary_and_half_spacing():
    atlas=np.arange(1.,4.)[:,None,None,None]
    target=np.eye(4); target[0,0]=.5
    got=n.resample_maps(atlas,np.eye(4),(6,1,1),target)
    np.testing.assert_array_equal(got[:,0,0,0],[1.,1.5,2.,2.5,3.,0.])


def test_negative_translation_boundary():
    atlas=np.arange(1.,4.)[:,None,None,None]
    target=np.eye(4); target[0,3]=-.5
    got=n.resample_maps(atlas,np.eye(4),(4,1,1),target)
    np.testing.assert_array_equal(got[:,0,0,0],[0.,1.5,2.5,0.])


def test_identity_shortcut_and_diagonal_dispatch(monkeypatch):
    calls=[]; original=n.ndimage.affine_transform
    def capture(data,matrix,**kwargs):
        calls.append(np.asarray(matrix).copy())
        return original(data,matrix,**kwargs)
    monkeypatch.setattr(n.ndimage,"affine_transform",capture)
    affine=np.array([[.7,0,0,.1],[0,1.3,0,-.2],[0,0,2.1,.4],[0,0,0,1.]])
    atlas=np.arange(8.).reshape(2,2,2,1)
    np.testing.assert_array_equal(n.resample_maps(atlas,affine,(2,2,2),affine),atlas)
    np.testing.assert_array_equal(calls[0],np.ones(3))


def test_joint_maps_not_weighted_means_or_selected_only_fit():
    maps = np.array([[1.,1.],[1.,0.],[0.,1.],[2.,1.]]).reshape(4,1,1,2)
    beta = np.array([[2.,-3.],[1.,4.],[0.,5.]])
    bold = (maps.reshape(4,2) @ beta.T).reshape(4,1,1,3)
    got = n.extract_coefficients(bold,n.map_basis(maps))
    np.testing.assert_allclose(got,beta,atol=2e-14)
    one = n.extract_coefficients(bold,n.map_basis(maps[...,:1]))
    assert not np.allclose(one[:,0],beta[:,0])


def test_rank_deficient_all_columns_minimum_norm_retained():
    maps = np.ones((4,1,1,3)); maps[...,2]=0
    b = n.map_basis(maps)
    assert b["rank"] == 1 and b["n_maps"] == 3
    result = n.extract_coefficients(np.ones((4,1,1,2))*6,b)
    np.testing.assert_allclose(result,[[3,3,0],[3,3,0]],atol=1e-14)


def test_zero_rank_diagnostic_not_map_dropping():
    b = n.map_basis(np.zeros((2,2,2,3)))
    assert b["rank"] == 0
    np.testing.assert_array_equal(n.extract_coefficients(np.ones((2,2,2,4)),b),np.zeros((4,3)))


def test_manufactured_svd_cutoff_separated_from_exact_tie():
    eps=np.finfo(np.float64).eps
    maps=np.diag([1.,4*eps,eps/4]).reshape(3,1,1,3)
    basis=n.map_basis(maps)
    assert basis["rank"]==2 and basis["cutoff"]==eps
    np.testing.assert_array_equal(basis["singular_values"],[1.,4*eps,eps/4])
    bold=np.eye(3).reshape(3,1,1,3)
    actual=n.extract_coefficients(bold,basis)
    expected=linalg.lstsq(maps.reshape(3,3),np.eye(3),cond=eps,lapack_driver="gelsd")[0].T
    assert np.isfinite(actual).all()
    np.testing.assert_allclose(actual,expected,atol=0,rtol=2e-15)
    np.testing.assert_array_equal(actual[:,2],np.zeros(3))


def test_svd_matches_disclosed_lstsq_on_manufactured_basis():
    rng=np.random.default_rng(6)
    maps=rng.normal(size=(3,4,2,5)); bold=rng.normal(size=(3,4,2,12))
    got=n.extract_coefficients(bold,n.map_basis(maps))
    expected=linalg.lstsq(maps.reshape(-1,5),bold.reshape(-1,12),cond=np.finfo(float).eps,lapack_driver="gelsd")[0].T
    np.testing.assert_allclose(got,expected,atol=2e-14,rtol=2e-14)


def test_filter_and_nuisance_recipe_no_extra_sd_epsilon():
    rng=np.random.default_rng(7)
    y=rng.normal(size=(168,4)); conf=rng.normal(size=(168,3))
    cleaned,receipt=n.clean_coefficients(y,conf)
    assert receipt["confound_rank"] == 3
    np.testing.assert_allclose(cleaned.mean(0),0,atol=1e-15)
    np.testing.assert_allclose(cleaned.std(0,ddof=1),1,atol=1e-15)
    np.testing.assert_array_equal(receipt["sos"],signal.butter(5,[.01,.1],btype="bandpass",fs=.5,output="sos"))


def test_zero_signals_and_duplicate_confounds():
    t=np.arange(168.)
    c=np.column_stack([t,t,np.zeros(168)])
    clean,receipt=n.clean_coefficients(np.zeros((168,3)),c)
    assert receipt["confound_rank"] == 1
    np.testing.assert_array_equal(clean,np.zeros((168,3)))


@pytest.mark.parametrize("which", ["bold","atlas","confounds","coefficients"])
def test_nonfinite_not_silently_imputed(which):
    with pytest.raises(ValueError,match="nonfinite"):
        if which == "atlas": n.resample_maps(np.full((2,2,2,2),np.nan),np.eye(4),(2,2,2),np.eye(4))
        elif which == "bold": n.extract_coefficients(np.full((2,2,2,3),np.inf),n.map_basis(np.ones((2,2,2,2))))
        else:
            y=np.ones((168,2)); c=np.ones((168,2))
            (c if which == "confounds" else y)[0,0]=np.nan
            n.clean_coefficients(y,c)


def test_no_input_mutation():
    rng=np.random.default_rng(8)
    y=rng.normal(size=(168,2)); c=rng.normal(size=(168,3))
    before_y=y.copy(); before_c=c.copy()
    n.clean_coefficients(y,c)
    np.testing.assert_array_equal(y,before_y); np.testing.assert_array_equal(c,before_c)
