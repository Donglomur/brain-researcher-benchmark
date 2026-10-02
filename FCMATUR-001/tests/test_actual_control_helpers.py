"""Source-free authoring-helper qualification; not part of scoring tests."""
import copy

import pytest

import actual_control_helpers as h
import output_contract as c
from test_output_contract import documents, emit, reference_fixture


def check(tmp_path, reference, candidate, details):
    if candidate is None:
        assert details['status'] in ('unavailable', 'not_constructed')
        assert details['reason']
        return
    root = emit(tmp_path / 'output', candidate)
    if details['status'] == 'effective':
        assert details['effect']['n_changed'] > 0
        with pytest.raises((ValueError, TypeError)): c.validate(root, reference)
    else:
        assert details['status'] in ('constructed', 'nondiscriminating')
        assert c.validate(root, reference)['status'] == 'accepted'


@pytest.mark.parametrize('mode', h.POSITIVES)
def test_manufactured_equivalent_positives(tmp_path, mode):
    ref = reference_fixture()
    docs = documents(ref)
    candidate, details = h.positive_candidate(mode, docs, ref)
    assert details['status'] == 'constructed'
    check(tmp_path, ref, candidate, details)


@pytest.mark.parametrize('mode', h.NUMERICAL)
def test_numerical_controls_classified_before_complete_validation(tmp_path, mode):
    ref = reference_fixture()
    docs = documents(ref)
    saved = copy.deepcopy(docs)
    candidate, details = h.numerical_candidate(mode, docs, ref)
    assert docs == saved
    if candidate is not None:
        assert candidate['run_metadata.json'] == docs['run_metadata.json']
        if mode != 'stale_affine_receipts': assert candidate['connectivity.csv'] == docs['connectivity.csv']
    check(tmp_path, ref, candidate, details)


@pytest.mark.parametrize('mode', h.BINDING)
def test_manufactured_binding_controls(tmp_path, mode):
    ref = reference_fixture()
    docs = documents(ref)
    saved = copy.deepcopy(docs)
    candidate, details = h.binding_candidate(mode, docs, ref)
    assert docs == saved
    assert details['status'] == 'effective'
    check(tmp_path, ref, candidate, details)


@pytest.mark.parametrize('mode', h.NUMERICAL)
def test_undefined_sources_are_unavailable_not_claimed_negatives(tmp_path, mode):
    ref = reference_fixture(mode='undefined')
    candidate, details = h.numerical_candidate(mode, documents(ref), ref)
    assert details['status'] in ('unavailable', 'nondiscriminating')
    assert details['effect']['n_changed'] == 0
    check(tmp_path, ref, candidate, details)


@pytest.mark.parametrize('mode', ['signflip_values', 'constant_values', 'permuted_values'])
def test_exact_primitive_noops_remain_nondiscriminating(tmp_path, mode):
    ref = reference_fixture(mode='constant')
    for row in ref['canonical_rows']:
        row['connectivity'] = 0.
        ref['persons'][row['subject']]['connectivity'] = 0.
    candidate, details = h.binding_candidate(mode, documents(ref), ref)
    assert details['status'] == 'nondiscriminating' and details['effect']['n_changed'] == 0
    check(tmp_path, ref, candidate, details)


def test_equal_site_weight_control_is_nondiscriminating_when_site_sizes_equal(tmp_path):
    ref = reference_fixture()
    candidate, details = h.numerical_candidate('weighted_between', documents(ref), ref)
    assert details['status'] == 'nondiscriminating'
    check(tmp_path, ref, candidate, details)


def test_unequal_site_weight_control_has_measured_numeric_effect(tmp_path):
    ref = reference_fixture()
    first = ref['canonical_rows'][0]
    first['age'] = None
    pheno = ref['phenotype_ledger'][0]
    pheno['normalized']['age'] = None
    pheno['tokens']['AGE_AT_SCAN'] = ''
    pheno['covariate_status']['age'] = 'missing'
    candidate, details = h.numerical_candidate('weighted_between', documents(ref), ref)
    assert details['status'] == 'effective' and details['effect']['max_absolute_gap'] > 0
    check(tmp_path, ref, candidate, details)


def test_affine_positive_not_constructed_at_public_fidelity_boundary():
    ref = reference_fixture()
    accepted = {r['subject']: r['connectivity'] + 1e-6 for r in ref['canonical_rows']}
    docs = documents(ref, accepted)
    candidate, details = h.positive_candidate('own_affine_replay', docs, ref)
    assert candidate is None and details['status'] == 'not_constructed'
    assert details['reason'].startswith('public_fidelity:')


@pytest.mark.parametrize('actual,expected,count', [(0., 0., 0), (5e-7, 0., 0), (2e-6, 0., 1),
                                                 (None, 0., 1), (0., None, 1), (True, 1, 1)])
def test_effect_measurement_uses_typed_public_tolerances(actual, expected, count):
    result = h.numeric_effects({'r': actual}, {'r': expected})
    assert result['n_changed'] == count


def test_counts_are_exact_not_floating_tolerance():
    assert h.numeric_effects({'n': 2}, {'n': 1})['n_changed'] == 1
    assert h.numeric_effects({'r': -5e-7}, {'r': 0.})['n_changed'] == 0
    assert h.numeric_effects({'p': -5e-7}, {'p': 0.})['n_changed'] == 1


def test_exact_inference_status_and_ci_support_are_disclosed_separately():
    status = h.numeric_effects({'estimate_status': 'perfect_correlation'}, {'estimate_status': 'ok'})
    assert status['n_changed'] == status['n_inference_status_changes'] == 1
    assert status['n_numeric_changes'] == 0
    support = h.numeric_effects({'ci95': None}, {'ci95': [-.1, .1]})
    assert support['n_numeric_changes'] == 1 and support['examples'][0]['kind'] == 'numeric_support'


@pytest.mark.parametrize('function', [h.positive_candidate, h.numerical_candidate, h.binding_candidate])
def test_unknown_control_modes_fail_closed(function):
    with pytest.raises(ValueError, match='unknown'):
        function('unknown', {}, {})


def test_helper_has_no_source_reader_import_or_network():
    from pathlib import Path
    text = Path(h.__file__).read_text()
    assert 'import source_reference' not in text and 'reconstruct(' not in text
    assert 'urllib' not in text and 'requests.' not in text
