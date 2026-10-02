import numpy as np
import pytest

import spin_math as m


@pytest.mark.parametrize("method", m.METHODS)
@pytest.mark.parametrize("seed", [0, 2**32-1])
def test_declared_bounds(method, seed):
    assert m.declaration(method, seed, 100) == (method, seed, 100)
    assert m.declaration(method, seed, 4096)[2] == 4096


@pytest.mark.parametrize("method,seed,count", [("shuffle", 0, 100), (True, 0, 100), ("original", True, 100),
    ("original", -1, 100), ("original", 2**32, 100), ("original", 0, 99), ("original", 0, 4097),
    ("original", 0, True), ("original", "0", 100), ("original", 0, 100.5), ("original", 0, float("nan"))])
def test_bad_declaration(method, seed, count):
    with pytest.raises(ValueError): m.declaration(method, seed, count)


@pytest.mark.parametrize("value", [[1, True], [1, "2"], [1, float("inf")], np.array([1+0j, 2]), np.array([True, False])])
def test_bad_real_array(value):
    with pytest.raises(ValueError): m.array(value)


@pytest.mark.parametrize("value", [[1, True], [1, 2.5], [1, 2**63], [1, float("nan")]])
def test_bad_integer_array(value):
    with pytest.raises(ValueError): m.integers(value)


@pytest.mark.parametrize("scale", [1., 1e300, 1e-300])
def test_stable_signed_pearson(scale):
    x = np.array([-1., 0., 1., 0.])*scale
    assert m.pearson(x, -x) == pytest.approx(-1., abs=1e-14)
    assert m.pearson(x, np.array([0., 1., 0., -1.])*scale) == pytest.approx(0., abs=1e-14)


@pytest.mark.parametrize("value", [0., .1, 1e300, 1e-300])
def test_exact_constant(value):
    x = np.full(20, value)
    assert not m.active(x)
    assert np.array_equal(m.center_scaled(x), np.zeros(20))
    with pytest.raises(ValueError): m.pearson(x, np.arange(20.))


def test_small_nonconstant_has_no_unit_floor():
    assert m.active(np.array([0., 1e-300, 2e-300]))


def test_original_many_to_one_recentered():
    maps = np.array([[1., 2.], [4., 0.], [8., 1.], [11., 5.]])
    ids = np.array([11, 13, 17, 19])
    mapped = np.array([[11], [11], [13], [19]])
    result = m.replay(maps, maps, ids, mapped)
    assert result["null_distribution"][0]["r"] == pytest.approx(np.corrcoef(maps[[0, 0, 1, 3], 0], maps[:, 1])[0, 1])
    assert result["n_null_defined"] == 1


def test_constant_remap_retained_and_invalidates_inference():
    maps = np.column_stack([np.arange(4.), np.array([1., 3., 0., 2.])])
    mapping = np.array([[1, 1], [2, 1], [3, 1], [4, 1]])
    result = m.replay(maps, maps, np.arange(1, 5), mapping)
    assert result["observed_status"] == "ok"
    assert result["n_null_defined"] == 1
    assert result["null_distribution"][1] == dict(rotation_id=1, status="inactive_gradient", r=None)
    assert result["p_spin"] is result["n_exceedances"] is result["significant_after_spatial_null"] is None
    assert result["p_spin_numerator"] is None
    assert result["n_null_expected"] == 2 and result["p_spin_denominator"] == 3
    assert len(result["null_distribution"]) == 2


@pytest.mark.parametrize("columns,status", [([0], "inactive_gradient"), ([1], "inactive_thickness"), ([0, 1], "inactive_both")])
def test_canonical_constant_jitter_cannot_manufacture_support(columns, status):
    source = np.column_stack([np.arange(4.), np.array([1., 3., 0., 2.])])
    source[:, columns] = 1.
    own = source.copy()
    own[:, columns] += np.arange(4.)[:, None]*1e-8
    result = m.replay(own, source, np.arange(1, 5), np.arange(1, 5)[:, None])
    assert result["observed_status"] == status
    assert result["pearson_r"] is result["p_spin"] is None


def test_remap_relative_fidelity_detects_low_variance_amplification():
    source = np.array([[1., 3.], [1.+1e-8, 2.], [20., 0.], [-20., 1.]])
    own = source.copy(); own[1, 0] += 1e-8
    m.centered_fidelity(own[:, 0], source[:, 0])  # full-map receipt is close
    with pytest.raises(ValueError, match="centered source fidelity"):
        m.map_fidelity(own, source, np.arange(1, 5), np.array([[1], [1], [2], [2]]))


def test_source_sign_and_scale_not_free():
    source = np.column_stack([np.arange(4.), np.array([1., 3., 0., 2.])])
    for changed in (-source, source*2):
        with pytest.raises(ValueError, match="signed pointwise"):
            m.map_fidelity(changed, source, np.arange(1, 5), np.arange(1, 5)[:, None])


def test_own_unrounded_tie_changes_count_not_source_target():
    r = .50000004
    rows = [dict(rotation_id=0, status="ok", r=.50000001), dict(rotation_id=1, status="ok", r=-r)]
    result = m.summarize("ok", r, rows)
    assert result["n_exceedances"] == 1
    rounded = m.summarize("ok", round(r, 6), [dict(row, r=round(row["r"], 6)) for row in rows])
    assert rounded["n_exceedances"] == 2


@pytest.mark.parametrize("n,expected", [(18, False), (19, False), (20, True)])
def test_strict_integer_alpha_boundary(n, expected):
    rows = [dict(rotation_id=k, status="ok", r=0.) for k in range(n)]
    result = m.summarize("ok", 1., rows)
    assert result["n_exceedances"] == 0
    assert result["n_null_expected"] == n
    assert result["p_spin_numerator"] == 1 and result["p_spin_denominator"] == n+1
    assert result["significant_after_spatial_null"] is expected


def test_repeated_null_slots_are_not_deduplicated():
    source = np.column_stack([np.arange(4.), np.array([1., 3., 0., 2.])])
    result = m.replay(source, source, np.arange(1, 5), np.tile(np.arange(1, 5)[:, None], (1, 17)))
    assert len(result["null_distribution"]) == result["n_exceedances"] == 17
    assert result["p_spin"] == 1.


@pytest.mark.parametrize("method", m.METHODS)
def test_native_package_generator_is_seeded_local_and_prefix_stable(method):
    # Only synthetic geometry, under the separately reviewed PR193 deps gate.
    rng = np.random.RandomState(314)
    xyz = rng.normal(size=(20, 3)); xyz *= 100/np.linalg.norm(xyz, axis=1)[:, None]
    ids = np.arange(101, 121); hemi = np.repeat([0, 1], 10)
    first, _ = m.construct(xyz, hemi, ids, method, 5, 100)
    repeat, _ = m.construct(xyz, hemi, ids, method, 5, 101)
    assert np.array_equal(first, repeat[:, :100])
    assert np.all(first[:10] < 111) and np.all(first[10:] >= 111)
    if method != "original": assert all(len(set(column)) == 20 for column in first.T)
