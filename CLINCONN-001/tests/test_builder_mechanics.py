"""Bounded synthetic builder fixtures; never read original neural data."""
import hashlib
from pathlib import Path
import numpy as np
import pytest
import build_reference as b
import connectivity_contract as q
import proof_of_work as pw


def test_frozen_public_fingerprints():
    environment = Path(__file__).parents[1]/'environment'
    assert b.sha256(environment/'method_contract.json') == pw.METHOD_SHA256
    assert b.sha256(environment/'source_manifest.json') == pw.SOURCE_MANIFEST_SHA256


@pytest.mark.parametrize('tokens,n,first,mean', [(['n/a', '.1', '.2'], 2, False, .15),
    (['', '.1', '.3'], 2, False, .2), (['0', '.1', '.2'], 3, True, .1)])
def test_fd_defined_denominator(tokens, n, first, mean):
    total, count, flag, actual = b.parse_fd(tokens)
    assert count == n and flag is first and actual == pytest.approx(mean)
    assert total/count == actual


@pytest.mark.parametrize('tokens', [['n/a'], ['0', 'n/a'], ['n/a', ''], ['-1', '0'], ['0', 'NaN'], ['Infinity', '.1']])
def test_fd_later_missing_negative_nonfinite_fails(tokens):
    with pytest.raises(AssertionError): b.parse_fd(tokens)


def test_separate_detrending_against_closed_formula():
    x = np.random.default_rng(1).normal(size=(60, 5))+np.arange(60)[:,None]/10
    centered = x-x.mean(axis=0); time = np.arange(60)-29.5
    expected = centered-time[:,None]*(time@centered)[None,:]/(time@time)
    assert np.allclose(b.detrend_columns(x), expected, atol=1e-13, rtol=1e-13)


def test_detrending_exact_constant_column():
    x = np.full((61, 2), .1)
    assert np.array_equal(b.detrend_columns(x), np.zeros_like(x))


def test_cleaning_has_source_specific_norms_and_sample_scaling():
    rng = np.random.default_rng(2)
    y = rng.normal(size=(100, 4)); c = rng.normal(size=(100, 13))
    result = b.clean_parcels(y, c)
    assert result['nuisance_rank'] == 13
    assert np.all(result['parcel_status'] == 'ok')
    assert np.allclose(result['normalized'].mean(axis=0), 0, atol=1e-14)
    assert np.allclose(result['normalized'].std(axis=0, ddof=1), 1, atol=1e-13)
    assert np.allclose(result['parcel_zero_bound'], 10*100*q.EPS*result['parcel_original_centered_l2'])


def test_constant_nuisance_rank_zero_and_constant_signal_status():
    rng = np.random.default_rng(3); y = rng.normal(size=(70, 3)); y[:, 0] = .1
    result = b.clean_parcels(y, np.full((70, 13), .1))
    assert result['nuisance_rank'] == 0 and result['parcel_status'][0] == 'constant_input'
    assert np.all(result['normalized'][:,0] == 0)
    assert result['parcel_original_centered_l2'][0] == 0
    assert result['parcel_zero_bound'][0] == 10*70*q.EPS*q.TINY > 0


def test_nuisance_only_signal_numerical_zero():
    rng = np.random.default_rng(4); c = rng.normal(size=(100, 13))
    result = b.clean_parcels(c[:, :2].copy(), c)
    assert np.all(result['parcel_status'] == 'numerical_zero_residual')


@pytest.mark.parametrize('n', [0, 1, 33])
def test_filter_padding_precondition(n):
    with pytest.raises(AssertionError): b.clean_parcels(np.ones((n, 2)), np.ones((n, 13)))


def test_nonfinite_confound_no_imputation():
    y = np.ones((50, 2)); c = np.ones((50, 13)); c[3, 2] = np.nan
    with pytest.raises(AssertionError): b.clean_parcels(y, c)


@pytest.mark.parametrize('mode', ['existing', 'inside_source', 'ancestor_source', 'same_path', 'nested_paths', 'symlink_parent', 'dangling_leaf'])
def test_evidence_destinations_preserve_source(tmp_path, mode):
    source = tmp_path/'source'; source.mkdir(); (source/'keep').write_text('immutable')
    output = tmp_path/'bank.npz'; report = tmp_path/'report.json'
    if mode == 'existing': output.write_text('preserve')
    elif mode == 'inside_source': output = source/'new.npz'
    elif mode == 'ancestor_source': output = tmp_path
    elif mode == 'same_path': report = output
    elif mode == 'nested_paths': report = output/'nested'
    elif mode == 'symlink_parent':
        (tmp_path/'link').symlink_to(source, target_is_directory=True); output = tmp_path/'link'/'new.npz'
    else: output.symlink_to(tmp_path/'absent')
    with pytest.raises(AssertionError): b.destinations(source, output, report)
    assert list(source.iterdir()) == [source/'keep'] and (source/'keep').read_text() == 'immutable'


def test_forged_manifest_rejected_before_body(tmp_path):
    (tmp_path/'source_manifest.json').write_text('{}')
    with pytest.raises(AssertionError, match='manifest'):
        b.read_inputs(tmp_path, Path(__file__).parents[1]/'environment/method_contract.json')


def test_exclusive_bank_writer_does_not_overwrite(tmp_path):
    path = tmp_path/'reference.npz'; path.write_bytes(b'preserve')
    # Opening must fail before source payload serialization or any replacement.
    ref = {name: {} for name in ('cohort_rows', 'parcel_rows', 'edge_rows', 'connectivity_rows', 'metadata',
                                'provenance', 'method_contract_json', 'source_manifest_json')}
    with pytest.raises(FileExistsError): b.save_reference(path, ref)
    assert path.read_bytes() == b'preserve'
