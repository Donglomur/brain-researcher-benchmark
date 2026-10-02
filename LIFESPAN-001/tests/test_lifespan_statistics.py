"""Manufactured arithmetic only: no original paths, readers or reference bank."""
import math

import numpy as np
import pytest
from scipy import stats
from sklearn.cluster import KMeans

import lifespan_statistics as m


def fixture_basis(s=5, t=17, r=8):
    q = np.random.default_rng(892).normal(size=(s, t, r)).astype(np.float32)
    return q, np.arange(s, dtype=np.float32) + 20, [f"person-{i}" for i in range(s)], np.arange(r)


def build_fixture(q=None):
    original, ages, people, rois = fixture_basis()
    return m.build_basis(original if q is None else q, ages, people, rois,
                         expected_subjects=5, expected_rois=8)


def test_dependency_versions():
    import scipy
    import sklearn
    assert (np.__version__, scipy.__version__, sklearn.__version__) == ("2.1.3", "1.14.1", "1.5.2")


def test_float64_accumulation_then_single_float32_storage():
    v = np.asarray([[2**24, 1, -2**24], [2, 3, 8]], dtype=np.float32)
    actual = m.vertex_mean(v)
    assert actual.dtype == np.float32
    assert np.array_equal(actual, np.mean(v, axis=1, dtype=np.float64).astype(np.float32))
    assert actual[0] == np.float32(1 / 3)
    assert actual[0] != v.mean(axis=1)[0]


@pytest.mark.parametrize("layout", ["c", "fortran", "advanced_selection"])
def test_canonical_mean_layout_is_explicit(layout):
    source = np.random.default_rng(21).normal(size=(9, 22)).astype(np.float32)
    indices = np.arange(0, 22, 2)
    selected = source[:, indices]
    if layout == "c": selected = np.ascontiguousarray(selected)
    if layout == "fortran": selected = np.asfortranarray(selected)
    expected = np.asarray(source[:, indices], dtype=np.float64, order="C").mean(axis=1, dtype=np.float64).astype(np.float32)
    np.testing.assert_array_equal(m.vertex_mean(selected), expected)


@pytest.mark.parametrize("v", [np.array([[np.nan]]), np.array([[np.inf]]), np.array([[True]]), np.array([[1j]]), np.empty((2, 0)), np.ones(2)])
def test_bad_vertices_refused(v):
    with pytest.raises(m.PreconditionError):
        m.vertex_mean(v)


def test_float32_overflow_is_numerical_failure():
    with pytest.raises(m.NumericalError):
        m.vertex_mean(np.array([[1e100, 1e100]]))


def test_zero_frames_remain_empty_not_imputed():
    assert m.vertex_mean(np.empty((0, 4))).shape == (0,)


def test_age_cast_preserved():
    source = np.array([20.1, 30.123456789])
    actual = m.computational_age(source)
    assert np.array_equal(actual, source.astype(np.float32).astype(np.float64))
    assert actual[0] != source[0]


@pytest.mark.parametrize("age", [[-1], [float("nan")], [True], [[22]]])
def test_bad_age(age):
    with pytest.raises(m.PreconditionError):
        m.computational_age(age)


@pytest.mark.parametrize("seed", range(5))
def test_canonical_corrcoef_exact_and_independent_dot_close(seed):
    q = np.random.default_rng(seed).normal(size=(23, 8)).astype(np.float32)
    d = m.canonical_connectome(q)
    ij = np.triu_indices(8, 1)
    expected = np.corrcoef(q.astype(np.float64).T)[ij]
    np.testing.assert_array_equal(d["raw_r"], expected)
    np.testing.assert_allclose(d["audit_raw_r"], expected, atol=3e-15, rtol=3e-15)
    np.testing.assert_array_equal(d["fisher_z"], np.arctanh(np.clip(expected, -.999, .999)))
    assert d["edge_valid"].all()


@pytest.mark.parametrize("level", [0.0, 0.1, -9.3])
def test_exact_constant_status_not_center_roundoff(level):
    q = np.random.default_rng(1).normal(size=(31, 8)).astype(np.float32)
    q[:, 0] = level
    d = m.canonical_connectome(q)
    assert d["parcel_status"][0] == "constant"
    bad = (d["edge_roi_index"] == 0).any(axis=1)
    assert np.array_equal(~d["edge_valid"], bad)
    assert np.isnan(d["raw_r"][bad]).all()
    assert np.isnan(d["audit_raw_r"][bad]).all()


@pytest.mark.parametrize("t", [0, 1])
def test_insufficient_frames(t):
    d = m.canonical_connectome(np.zeros((t, 8), dtype=np.float32))
    assert set(d["parcel_status"]) == {"insufficient_frames"}
    assert not d["edge_valid"].any()
    assert np.isnan(d["fisher_z"]).all()


def test_tiniest_float32_variation_is_not_thresholded():
    tiny = np.nextafter(np.float32(0), np.float32(1))
    q = np.array([[0, tiny], [tiny, 0], [0, tiny], [tiny, 0]], dtype=np.float32)
    d = m.canonical_connectome(q)
    assert list(d["parcel_status"]) == ["ok", "ok"]
    assert d["raw_r"][0] == -1


def test_noncanonical_evidence_is_not_computational_input():
    q = np.random.default_rng(3).normal(size=(10, 8)).astype(np.float32).astype(np.float64)
    q[0, 0] += 1e-12
    with pytest.raises(m.PreconditionError, match="promoted float32"):
        m.canonical_connectome(q)


def test_group_sequential_sum_complete_mask_and_zero_diagonal():
    ij = np.column_stack(np.triu_indices(8, 1))
    z = np.random.default_rng(4).normal(size=(5, len(ij)))
    valid = np.ones_like(z, dtype=bool)
    valid[1, 0] = False
    z[1, 0] = np.nan
    group, mask = m.group_connectome(z, valid, ij, 8)
    np.testing.assert_array_equal(np.diag(group), 0)
    assert np.diag(mask).all()
    assert np.isnan(group[0, 1]) and not mask[0, 1]
    expected = np.zeros(len(ij))
    for row in z:
        expected += row
    expected /= 5
    np.testing.assert_array_equal(group[ij[:, 0], ij[:, 1]], expected)


@pytest.mark.parametrize("corruption", ["nan_valid", "finite_invalid", "nonboolean_mask", "wrong_edges"])
def test_group_bad_support_refused(corruption):
    ij = np.column_stack(np.triu_indices(8, 1))
    z = np.zeros((5, len(ij)))
    valid = np.ones_like(z, dtype=bool)
    if corruption == "nan_valid": z[0, 0] = np.nan
    if corruption == "finite_invalid": valid[0, 0] = False
    if corruption == "nonboolean_mask": valid = valid.astype(int)
    if corruption == "wrong_edges": ij = ij[::-1]
    with pytest.raises(m.PreconditionError):
        m.group_connectome(z, valid, ij, 8)


def test_incomplete_group_never_calls_kmeans(monkeypatch):
    def forbidden(**kwargs): raise AssertionError("fit attempted")
    monkeypatch.setattr(m, "KMeans", forbidden)
    q, _, _, _ = fixture_basis()
    q[0, :, 0] = .1
    basis = build_fixture(q)
    assert basis["partition"]["status"] == "incomplete_group_connectome"
    assert basis["partition"]["labels"] is None
    assert len(basis["summary_rows"]) == 5
    assert basis["summary_rows"][0]["global_connectivity"] is None
    assert all(row["global_connectivity"] is not None for row in basis["summary_rows"][1:])
    assert all(row["system_segregation"] is None for row in basis["summary_rows"])
    assert basis["results"]["overall_connectivity_vs_age"]["n_defined"] == 4
    assert basis["results"]["system_segregation_vs_age"]["n_defined"] == 0


def test_shared_exact_recipe_and_no_input_mutation():
    matrix = np.random.default_rng(11).normal(size=(14, 14))
    matrix = (matrix + matrix.T) / 2
    np.fill_diagonal(matrix, 0)
    before = matrix.copy()
    result = m.partition(matrix, np.ones_like(matrix, dtype=bool))
    direct = KMeans(**m.KMEANS_PARAMETERS).fit(matrix.copy(), sample_weight=None)
    assert m.same_partition(result["labels"], direct.labels_)
    np.testing.assert_array_equal(matrix, before)
    assert result["status"] == "ok"


def test_less_than_seven_occupied_is_retained_with_warning():
    result = m.partition(np.zeros((8, 8)), np.ones((8, 8), bool))
    assert result["status"] == "fewer_than_seven_occupied_clusters"
    assert result["n_clusters_occupied"] == 1
    assert result["labels"].shape == (8,)
    assert result["warnings"]


def test_cap300_retained_and_all_parameters_explicit(monkeypatch):
    class Fake:
        def __init__(self, **kwargs): assert kwargs == m.KMEANS_PARAMETERS
        def fit(self, matrix, sample_weight):
            assert sample_weight is None and matrix.flags.c_contiguous and matrix.dtype == np.float64
            self.labels_ = np.array([0, 1, 2, 3, 4, 5, 6, 6])
            self.cluster_centers_ = np.zeros((7, 8))
            self.inertia_, self.n_iter_ = 1.5, 300
            return self
    monkeypatch.setattr(m, "KMeans", Fake)
    d = m.partition(np.zeros((8, 8)), np.ones((8, 8), bool))
    assert d["status"] == "ok" and d["fit_diagnostics"]["n_iter"] == 300


@pytest.mark.parametrize("problem", ["asymmetry", "bad_diagonal", "false_diagonal", "mask_asymmetry", "nan_valid"])
def test_partition_malformed_group(problem):
    g, v = np.zeros((8, 8)), np.ones((8, 8), bool)
    if problem == "asymmetry": g[0, 1] = 1
    if problem == "bad_diagonal": g[0, 0] = 1
    if problem == "false_diagonal": v[0, 0] = False
    if problem == "mask_asymmetry": v[0, 1] = False
    if problem == "nan_valid": g[0, 1] = g[1, 0] = np.nan
    with pytest.raises(m.PreconditionError): m.partition(g, v)


def test_label_permutations_not_membership_permutations():
    assert m.same_partition([0, 0, 1, 2], ["red", "red", "blue", "orange"])
    assert not m.same_partition([0, 0, 1, 2], ["red", "blue", "red", "orange"])
    assert not m.same_partition([0, 0], [0, 0, 1])


@pytest.mark.parametrize("labels", [[np.nan], [""], [True], [], [[1, 2]]])
def test_invalid_labels(labels):
    with pytest.raises(m.PreconditionError): m.coassignment(labels)


def summary_input(z):
    ij = np.column_stack(np.triu_indices(4, 1))
    z = np.asarray([z], dtype=float)
    return m.summaries(z, np.isfinite(z), ij, dict(status="ok", labels=np.array([0, 0, 1, 1])), ["s"], [20])[0]


def test_complete_pair_denominators_signed_global():
    # Edges01,02,03,12,13,23; only01 and23 are within.
    row = summary_input([-1, 2, -3, 4, 0, 5])
    assert row["n_within_edges"] == 2 and row["n_between_edges"] == 4
    assert row["within_network_connectivity"] == 2.5
    assert row["between_network_connectivity"] == 1.5
    assert row["global_connectivity"] == 7 / 6
    assert row["system_segregation"] == .4


def test_negative_segregation_not_flipped_or_rejected():
    row = summary_input([1, 4, 4, 4, 4, 1])
    assert row["system_segregation"] == -3
    assert row["segregation_status"] == "ok"


@pytest.mark.parametrize("between", [0, 2])
def test_zero_within_undefined_ratio_preserves_other_fields(between):
    row = summary_input([-1, between, between, between, between, 0])
    assert row["within_network_connectivity"] == 0
    assert row["between_network_connectivity"] == between
    assert row["system_segregation"] is None and row["segregation_status"] == "zero_within_mean"
    assert row["global_connectivity"] is not None


def test_small_positive_within_no_threshold():
    row = summary_input([1e-20, 1, 1, 1, 1, 1e-20])
    assert row["segregation_status"] == "ok"
    assert row["system_segregation"] < -1e19


def test_empty_pair_family_explicit():
    z = np.zeros((1, 6))
    row = m.summaries(z, np.ones_like(z, bool), np.column_stack(np.triu_indices(4, 1)),
                      dict(status="ok", labels=np.zeros(4, int)), ["s"], [20])[0]
    assert row["segregation_status"] == "empty_pair_family"
    assert row["n_between_edges"] == 0 and row["system_segregation"] is None


@pytest.mark.parametrize("seed", range(6))
def test_independent_beta_p_and_fisher_interval(seed):
    rng = np.random.default_rng(seed)
    a = rng.uniform(10, 80, 59).astype(np.float32)
    y = rng.normal(size=59)
    d = m.age_endpoint(a, y, [str(i) for i in range(59)])
    reference = stats.pearsonr(a.astype(np.float64), y)
    assert d["pearson_r"] == pytest.approx(reference.statistic, abs=5e-15)
    assert d["p"] == pytest.approx(reference.pvalue, abs=5e-14)
    expected = np.tanh(np.arctanh(np.clip(reference.statistic, -.999999, .999999)) + np.array([-1, 1]) * 1.96 / np.sqrt(56))
    np.testing.assert_allclose(d["ci95"], expected, atol=1e-14, rtol=0)


@pytest.mark.parametrize("sign", [-1, 1])
def test_perfect_correlation_ci_keeps_published_clamp(sign):
    age = np.arange(1, 60, dtype=np.float32)
    d = m.age_endpoint(age, sign * age.astype(float), [str(i) for i in range(59)])
    assert d["pearson_r"] == pytest.approx(sign, abs=1e-15)
    assert d["p"] < 1e-100
    assert d["ci95"][1] < 1 if sign == 1 else d["ci95"][0] > -1


def test_endpoint_precedence_complete_people_no_silent_subset():
    ids = list("abcde")
    d = m.age_endpoint([20] * 5, [None, 1, 1, 1, 1], ids)
    assert d["status"] == "incomplete_subject_support" and d["n_defined"] == 4
    assert d["undefined_subject_ids"] == ["a"] and d["pearson_r"] is None
    d = m.age_endpoint([20] * 5, [1] * 5, ids)
    assert d["status"] == "constant_age" and d["n_defined"] == 5
    d = m.age_endpoint([20, 21, 22, 23, 24], [0.1] * 5, ids)
    assert d["status"] == "constant_summary" and d["ci95"] is None


@pytest.mark.parametrize("bad", [np.nan, np.inf, True])
def test_nonfinite_endpoint_not_undefined(bad):
    with pytest.raises(m.PreconditionError):
        m.age_endpoint(np.arange(5, dtype=np.float32), [bad, 2, 3, 4, 5], list("abcde"))


def test_basis_complete_shapes_inputs_not_mutated():
    q, age, people, rois = fixture_basis()
    before = q.copy()
    d = m.build_basis(q, age, people, rois, expected_subjects=5, expected_rois=8)
    assert d["raw_r"].shape == (5, 28) and d["group_features"].shape == (8, 8)
    assert d["results"]["status"] == "ok" and len(d["summary_rows"]) == 5
    assert d["partition"]["status"] == "ok"
    np.testing.assert_array_equal(q, before)


@pytest.mark.parametrize("mutation", ["cohort", "roi_count", "duplicate_ids", "roi_order", "noncanonical_age", "nonfinite_q"])
def test_basis_guard(mutation):
    q, age, people, rois = fixture_basis()
    kwargs = dict(expected_subjects=5, expected_rois=8)
    if mutation == "cohort": kwargs["expected_subjects"] = 59
    if mutation == "roi_count": kwargs["expected_rois"] = 148
    if mutation == "duplicate_ids": people[1] = people[0]
    if mutation == "roi_order": rois = rois[::-1]
    if mutation == "noncanonical_age": age = age.astype(float) + 1e-10
    if mutation == "nonfinite_q": q[0, 0, 0] = np.nan
    with pytest.raises(m.PreconditionError): m.build_basis(q, age, people, rois, **kwargs)


def test_all_constant_complete_59_person_accounting(monkeypatch):
    def forbidden(**kwargs): raise AssertionError("fit attempted")
    monkeypatch.setattr(m, "KMeans", forbidden)
    d = m.build_basis(np.full((59, 4, 148), .1, dtype=np.float32),
                      np.arange(59, dtype=np.float32), [f"s{i}" for i in range(59)], np.arange(148))
    assert d["raw_r"].shape == (59, 10878)
    assert len(d["summary_rows"]) == 59 and not d["edge_valid"].any()
    for name in ("overall_connectivity_vs_age", "system_segregation_vs_age"):
        assert d["results"][name]["n_expected"] == 59
        assert d["results"][name]["n_defined"] == 0


def test_audit_is_not_fitting_basis(monkeypatch):
    original = m.normalized_dot_audit
    def altered(q):
        values, status = original(q)
        return values * .9, np.full_like(status, "constant")
    baseline = build_fixture()
    monkeypatch.setattr(m, "normalized_dot_audit", altered)
    altered_basis = build_fixture()
    np.testing.assert_array_equal(baseline["group_features"], altered_basis["group_features"])
    assert m.same_partition(baseline["partition"]["labels"], altered_basis["partition"]["labels"])
    assert baseline["results"] == altered_basis["results"]
    assert max(altered_basis["audit"]["max_abs_r_difference"]) > .01
