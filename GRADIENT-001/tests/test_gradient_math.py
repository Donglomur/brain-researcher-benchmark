"""Manufactured spectral/GPA certificates only; no source, bank or oracle imports."""
import math

import numpy as np
import pytest
from scipy import linalg

import gradient_math as g


def toy_basis(eigenvalues=None, n_components=3):
    # Unit-sum positive affinity with a known stationary Hadamard column.
    values = np.array([1., .22, .15, .10, .06, .04, .02, .01] if eigenvalues is None else eigenvalues)
    q = linalg.hadamard(8).astype(float) / math.sqrt(8)
    affinity = (q * values) @ q.T
    return g.operator_basis(affinity, np.arange(1, 9), n_components)


def candidate(basis):
    u, coordinates = g.orient(basis["proposal_vectors"], basis)
    return u, basis["spectral_eigenvalues"].copy(), coordinates


def certificate(data, initial):
    """Separate fixture constructor uses SciPy's Procrustes implementation."""
    reference = initial.copy()
    history, distances, rotations = [reference.copy()], [], []
    previous = None
    for _ in range(g.GPA_MAX_ITER):
        step = np.stack([linalg.orthogonal_procrustes(person, reference)[0] for person in data])
        aligned = np.stack([person @ rotation for person, rotation in zip(data, step)])
        current = np.mean(aligned, axis=0)
        distance = float(np.sum((reference - current)**2))
        rotations.append(step)
        history.append(current)
        distances.append(distance)
        if previous is not None and abs(distance - previous) < g.GPA_STOP_TOL:
            break
        reference, previous = current, distance
    return dict(rotations=np.asarray(rotations), reference_history=np.asarray(history),
                distances=np.asarray(distances), n_iterations=len(rotations), saved_aligned=aligned)


@pytest.mark.parametrize("value", [True, [True], ["1"], [1 + 0j], [float("nan")], [float("inf")], np.array([1], dtype=object)])
def test_strict_real_inputs(value):
    with pytest.raises(ValueError):
        g.real(value, "manufactured")


@pytest.mark.parametrize("value", [True, "2", 1.5, -1, 11, 10**1000, float("nan"), float("inf")])
def test_iteration_integer_parsing(value):
    with pytest.raises(ValueError):
        g.count(value, "iterations", 1, 10)


def test_activity_preserves_exact_constant_and_projection_roundoff_as_inactive():
    raw = np.column_stack([np.full(8, .1), np.arange(8.)])
    clean = np.stack([np.column_stack([np.full(8, .1), np.arange(8.) * 1e-16])]*2)
    result = g.activity(raw, clean, np.ones(2, bool))
    assert result["raw_sample_sd"][0] == 0
    assert result["clean_centered_l2"][0, 0] == 0
    assert not result["person_parcel_active"].any()


def test_activity_uses_one_raw_scale_for_both_arms_strictly_above_threshold():
    # Mean-zero two-frame columns have raw sample SD exactly one.
    raw = np.array([[-1., 0.], [1., 0.]]) / math.sqrt(2)
    clean = np.zeros((2, 2, 2))
    clean[0, :, 0] = [-1e-13, 1e-13]
    clean[1, :, 0] = [-1e-11, 1e-11]
    result = g.activity(raw, clean, np.ones(2, bool))
    assert result["activity_threshold"].shape == (2,)
    assert result["person_parcel_active"][:, 0].tolist() == [False, True]
    exact = np.array([[0., 0.], [0., 0.]])
    # Strict >, not >=: manufactured zero cannot become active.
    assert not g.activity(exact, np.stack([exact, exact]), np.ones(2, bool))["person_parcel_active"].any()


def test_activity_retains_absent_parcel_and_explicit_nan_diagnostics():
    raw = np.column_stack([np.arange(8.), np.full(8, np.nan)])
    result = g.activity(raw, np.stack([raw, raw]), np.array([True, False]))
    assert result["person_parcel_active"].shape == (2, 2)
    assert result["person_parcel_active"][:, 0].all()
    assert not result["person_parcel_active"][:, 1].any()
    assert np.isnan(result["raw_sample_sd"][1])


def test_activity_exact_nonzero_threshold_is_inactive_and_next_float_is_active():
    raw = np.zeros((4, 1))
    amplitude = 1e-12
    next_amplitude = np.nextafter(amplitude, np.inf)
    clean = np.asarray([[[-amplitude], [amplitude], [-amplitude], [amplitude]],
                        [[-next_amplitude], [next_amplitude], [-next_amplitude], [next_amplitude]]])
    result = g.activity(raw, clean, np.array([True]))
    assert result["clean_centered_l2"][0, 0] == result["activity_threshold"][0]
    assert result["person_parcel_active"][:, 0].tolist() == [False, True]


@pytest.mark.parametrize("mode", ["present_nan", "absent_finite", "bool_mask_values", "boolean_raw"])
def test_activity_invalid_source_or_types(mode):
    raw = np.arange(8.)[:, None]
    clean = np.stack([raw, raw])
    mask = np.array([True])
    if mode == "present_nan":
        clean[0, 0, 0] = np.nan
    elif mode == "absent_finite":
        mask[:] = False
    elif mode == "bool_mask_values":
        mask = mask.astype(int)
    else:
        raw = raw.astype(bool)
    with pytest.raises(ValueError):
        g.activity(raw, clean, mask)


def test_explicit_40_signed_entries_with_tie_ids_and_diagonal_eligibility():
    fc = np.ones((60, 60))
    sparse, mask = g.sparsify_fc(fc, np.arange(1, 61))
    assert np.all(mask.sum(axis=1) == 40)
    assert np.all(mask[:, :40]) and not np.any(mask[:, 40:])
    assert not mask[50, 50]  # Eligibility is not force-insertion in a tie.
    assert np.array_equal(sparse, mask.astype(float))


def test_signed_not_absolute_selection_and_permutation():
    fc = np.eye(6)
    fc[0] = [1., -.99, .2, .3, -.1, .1]
    ids = np.array([60, 50, 40, 30, 20, 10])
    sparse, mask = g.sparsify_fc(fc, ids, retained=3)
    assert np.flatnonzero(mask[0]).tolist() == [0, 2, 3]
    perm = np.array([5, 3, 1, 4, 2, 0])
    swapped, selected = g.sparsify_fc(fc[np.ix_(perm, perm)], ids[perm], 3)
    assert np.array_equal(swapped, sparse[np.ix_(perm, perm)])
    assert np.array_equal(selected, mask[np.ix_(perm, perm)])


def test_normalized_angle_exact_diagonal_and_zero_profile_failure():
    value = g.normalized_angle(np.array([[1., 0], [0, 1.], [-1., 0]]))
    assert np.array_equal(np.diag(value), np.ones(3))
    assert value[0, 1] == .5 and value[0, 2] == 0
    with pytest.raises(ValueError, match="zero-norm"):
        g.normalized_angle(np.zeros((4, 4)))


def test_correct_symmetric_conjugate_recovers_nonsymmetric_markov_eigenproblem():
    w = np.array([[1., .2, .1, .05], [.2, 1., .4, .3], [.1, .4, 1., .6], [.05, .3, .6, 1.]])
    basis = g.operator_basis(w, np.arange(1, 5), n_components=2)
    q = w.sum(axis=1)
    wa = w / (np.sqrt(q)[:, None] * np.sqrt(q)[None, :])
    markov = wa / wa.sum(axis=1)[:, None]
    assert not np.allclose(markov, markov.T, atol=1e-12, rtol=0)
    u, values, gradient = candidate(basis)
    psi = u / basis["u0"][:, None]
    assert np.max(np.abs(markov @ psi - psi * basis["eigenvalues"])) < 1e-12
    assert g.validate_spectrum(u, values, gradient, basis) is not None


def test_valid_spectrum_no_hidden_basis_target_and_no_inputs_mutated():
    basis = toy_basis()
    u, values, gradient = candidate(basis)
    before = (u.copy(), values.copy(), gradient.copy())
    assert np.allclose(g.validate_spectrum(u, values, gradient, basis), gradient)
    for value, old in zip((u, values, gradient), before):
        assert np.array_equal(value, old)


@pytest.mark.parametrize("mode", ["wrong_lambda", "wrong_order", "mixed_distinct", "scaled_vector", "stationary", "wrong_sign", "scaled_gradient"])
def test_invalid_spectral_components(mode):
    basis = toy_basis()
    u, values, gradient = candidate(basis)
    if mode == "wrong_lambda":
        values[0] += .01
    elif mode == "wrong_order":
        u = u[:, [1, 0, 2]]
    elif mode == "mixed_distinct":
        theta = .4
        rotation = np.array([[math.cos(theta), -math.sin(theta), 0], [math.sin(theta), math.cos(theta), 0], [0, 0, 1.]])
        u = u @ rotation
    elif mode == "scaled_vector":
        u[:, 0] *= 2
    elif mode == "stationary":
        u[:, 0] = basis["u0"]
    elif mode == "wrong_sign":
        u[:, 0] *= -1
        gradient[:, 0] *= -1
    else:
        gradient *= 2
    with pytest.raises(ValueError):
        g.validate_spectrum(u, values, gradient, basis)


def test_exact_internal_repeated_block_rotations_are_legitimate():
    basis = toy_basis([1., .22, .12, .12, .06, .04, .02, .01])
    u, values, _ = candidate(basis)
    theta = .63
    rotation = np.array([[1., 0, 0], [0, math.cos(theta), -math.sin(theta)], [0, math.sin(theta), math.cos(theta)]])
    changed, gradient = g.orient(u @ rotation, basis)
    assert basis["principal_identifiable"] and basis["retained_boundary_identifiable"]
    assert g.validate_spectrum(changed, values, gradient, basis) is not None


def test_leading_and_retained_boundary_degeneracy_are_distinct():
    principal = toy_basis([1., .2, .2, .10, .06, .04, .02, .01])
    assert not principal["principal_identifiable"] and principal["gpa_eligible"]
    assert g.validate_spectrum(*candidate(principal), principal) is not None
    boundary = toy_basis([1., .22, .15, .10, .10, .04, .02, .01])
    assert boundary["principal_identifiable"] and not boundary["gpa_eligible"]
    assert g.validate_spectrum(*candidate(boundary), boundary) is not None


def test_multiscale_singularity_is_undefined_not_fabricated_zero():
    basis = g.operator_basis(np.eye(8), np.arange(1, 9), 3)
    assert not basis["multiscale_defined"]
    u = linalg.hadamard(8).astype(float)[:, 1:4] / math.sqrt(8)
    assert g.validate_spectrum(u, basis["spectral_eigenvalues"], None, basis) is None
    with pytest.raises(ValueError, match="require null"):
        g.validate_spectrum(u, basis["spectral_eigenvalues"], np.zeros((8, 3)), basis)


def test_eigenvalue_receipt_does_not_rescale_accepted_coordinates():
    basis = toy_basis()
    u, values, gradient = candidate(basis)
    values += g.EIGEN_ATOL / 2
    assert np.array_equal(g.validate_spectrum(u, values, gradient, basis), gradient)


def test_zero_diffusion_coordinate_does_not_impose_eigenvector_sign():
    q = linalg.hadamard(8).astype(float) / math.sqrt(8)
    basis = dict(operator=np.full((8, 8), 1 / 8), u0=q[:, 0], eigenvalues=np.zeros(3),
                 spectral_eigenvalues=np.zeros(4), parcel_ids=np.arange(1, 9), multiscale_defined=True)
    for sign in (-1., 1.):
        u = sign * q[:, 1:4]
        assert np.array_equal(g.validate_spectrum(u, np.zeros(4), np.zeros((8, 3)), basis), np.zeros((8, 3)))


def test_gpa_history_from_independent_procrustes_fixture():
    rng = np.random.default_rng(80)
    data = rng.normal(size=(4, 12, 3))
    initial = rng.normal(size=(12, 3))
    receipts = certificate(data, initial)
    result = g.validate_gpa_history(data, initial, **receipts)
    assert result["n_iterations"] == receipts["n_iterations"]
    assert np.allclose(result["aligned"], receipts["saved_aligned"])


def test_identical_people_are_not_an_outcome_failure():
    one = np.arange(18, dtype=float).reshape(6, 3)
    data = np.repeat(one[None], 3, axis=0)
    receipts = certificate(data, one)
    assert g.validate_gpa_history(data, one, **receipts)["n_iterations"] == 2


def test_nonunique_nullspace_rotations_accepted_without_single_svd_gauge():
    one = np.zeros((6, 3))
    one[:, 0] = np.arange(6.)
    data = np.repeat(one[None], 2, axis=0)
    rotations = np.repeat(np.eye(3)[None, None], 4, axis=0).reshape(2, 2, 3, 3)
    theta = .7
    rotations[0, 0, 1:, 1:] = [[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]]
    rotations[1, 1, 1:, 1:] = [[0, 1], [1, 0]]
    result = g.validate_gpa_history(data, one, rotations, np.repeat(one[None], 3, axis=0), np.zeros(2), 2, data)
    assert np.array_equal(result["aligned"], data)


@pytest.mark.parametrize("mode", ["nonorthogonal", "nonoptimal", "initial", "history", "distance", "aligned", "premature", "continued", "nonfinite"])
def test_gpa_certificate_rejections(mode):
    one = np.eye(6, 3)
    data = np.repeat(one[None], 2, axis=0)
    receipts = certificate(data, one)
    if mode == "nonorthogonal":
        receipts["rotations"][0, 0, 0, 0] = 2
    elif mode == "nonoptimal":
        receipts["rotations"][0, 0] *= -1
    elif mode == "initial":
        receipts["reference_history"][0, 0, 0] += .1
    elif mode == "history":
        receipts["reference_history"][1, 0, 0] += .1
    elif mode == "distance":
        receipts["distances"][0] += .1
    elif mode == "aligned":
        receipts["saved_aligned"][0, 0, 0] += .1
    elif mode == "premature":
        receipts["n_iterations"] = 1
        receipts["rotations"] = receipts["rotations"][:1]
        receipts["reference_history"] = receipts["reference_history"][:2]
        receipts["distances"] = receipts["distances"][:1]
    elif mode == "continued":
        receipts["n_iterations"] = 3
        receipts["rotations"] = np.concatenate([receipts["rotations"], receipts["rotations"][:1]])
        receipts["reference_history"] = np.concatenate([receipts["reference_history"], receipts["reference_history"][:1]])
        receipts["distances"] = np.zeros(3)
    else:
        receipts["rotations"][0, 0, 0, 0] = np.nan
    with pytest.raises(ValueError):
        g.validate_gpa_history(data, one, **receipts)


def test_rounded_history_is_receipt_not_stopping_or_minimizer_input():
    one = np.eye(6, 3)
    data = np.repeat(one[None], 2, axis=0)
    receipts = certificate(data, one)
    receipts["reference_history"] += 5e-7
    receipts["distances"] += 5e-7
    result = g.validate_gpa_history(data, one, **receipts)
    assert np.array_equal(result["distances"], np.zeros(2))
    assert np.array_equal(result["reference_history"], np.repeat(one[None], 3, axis=0))
