"""Manufactured numerical fixtures only; no originals or historical reference."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from scipy import ndimage, signal
import nibabel as nib

SPEC = importlib.util.spec_from_file_location('oracle_math', Path(__file__).parents[1] / 'solution/segregation_contract.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
sys.path.insert(0, str(Path(__file__).parents[1] / 'solution'))
import compute as c


def manufactured_signals():
    rng = np.random.default_rng(1204)
    confounds = rng.normal(size=(60, 4))
    raw = 100 + np.arange(60)[:, None] * np.array([[0.2, -0.3, 0.1]])
    raw = raw + rng.normal(size=(60, 3)) + confounds @ rng.normal(size=(4, 3))
    return raw, confounds


def test_detrend_matches_alternative_scipy_lstsq():
    raw, _ = manufactured_signals()
    result = m.linear_detrend(raw)
    np.testing.assert_allclose(result, signal.detrend(raw, axis=0, type='linear'), atol=5e-14)
    np.testing.assert_allclose(result.mean(axis=0), 0, atol=5e-14)
    np.testing.assert_allclose(np.arange(len(raw)) @ result, 0, atol=1e-10)


def test_exact_decimal_constant_centers_and_detrends_to_zero():
    raw = np.full((168, 3), 0.1)
    assert np.array_equal(m.center_columns(raw), np.zeros_like(raw))
    assert np.array_equal(m.linear_detrend(raw), np.zeros_like(raw))


def test_cleaning_matches_independent_lstsq_span():
    raw, confounds = manufactured_signals()
    result = m.clean_parcels(raw, confounds)
    design = np.column_stack([np.ones(len(raw)), np.arange(len(raw)), confounds])
    residual = raw - design @ np.linalg.lstsq(design, raw, rcond=None)[0]
    residual -= residual.mean(axis=0)
    expected = residual / residual.std(axis=0, ddof=1)
    np.testing.assert_allclose(result['cleaned'], expected, atol=2e-13)
    np.testing.assert_allclose(result['cleaned'].mean(axis=0), 0, atol=1e-15)
    np.testing.assert_allclose(result['cleaned'].std(axis=0, ddof=1), 1, atol=1e-15)
    assert result['nuisance_rank'] == 4


def test_rank_deficient_and_constant_confounds_are_valid():
    raw, confounds = manufactured_signals()
    redundant = np.column_stack([confounds, confounds[:, 0], np.full(len(raw), 0.1)])
    a, b = m.clean_parcels(raw, confounds), m.clean_parcels(raw, redundant)
    assert a['nuisance_rank'] == b['nuisance_rank'] == 4
    np.testing.assert_allclose(a['cleaned'], b['cleaned'], atol=1e-13)


def test_all_constant_nuisance_is_rank_zero():
    raw, _ = manufactured_signals()
    result = m.clean_parcels(raw, np.full((len(raw), 15), 0.1))
    assert result['nuisance_rank'] == 0
    expected = m.linear_detrend(raw)
    expected -= expected.mean(axis=0)
    expected /= expected.std(axis=0, ddof=1)
    np.testing.assert_allclose(result['cleaned'], expected)


@pytest.mark.parametrize('amplitude,passes', [(0.0, False), (1e-13, False), (1e-10, True)])
def test_constant_and_near_constant_residual_precondition(amplitude, passes):
    x = np.sin(np.arange(60, dtype=float))[:, None] * amplitude
    if passes:
        result = m.clean_parcels(x, np.zeros((60, 1)))
        assert np.all(result['residual_sd'] > result['residual_sd_lower_bound'])
    else:
        with pytest.raises(m.PreconditionError, match='residual SD'):
            m.clean_parcels(x, np.zeros((60, 1)))


def test_nuisance_explained_signal_fails_no_subsetting():
    _, confounds = manufactured_signals()
    with pytest.raises(m.PreconditionError, match='residual SD'):
        m.clean_parcels(np.column_stack([confounds[:, 0], np.sin(np.arange(60))]), confounds)


@pytest.mark.parametrize('where', ['raw', 'confounds'])
@pytest.mark.parametrize('value', [float('nan'), float('inf')])
def test_nonfinite_cleaning_is_not_imputed(where, value):
    raw, nuisance = manufactured_signals()
    (raw if where == 'raw' else nuisance)[0, 0] = value
    with pytest.raises(m.PreconditionError, match='nonfinite'):
        m.clean_parcels(raw, nuisance)


def test_cleaning_frame_mismatch():
    raw, nuisance = manufactured_signals()
    with pytest.raises(m.PreconditionError, match='frame mismatch'):
        m.clean_parcels(raw, nuisance[:-1])


@pytest.mark.parametrize('translation', [-0.51, -0.5, -1e-12, 0, 0.499999999, 0.5, 1.5, 2.0, 2.000000001])
def test_nearest_ties_closed_domain_matches_scipy_order0(translation):
    atlas = np.arange(1, 28).reshape(3, 3, 3)
    target = np.eye(4); target[0, 3] = translation
    observed = m.nearest_labels(atlas, np.eye(4), (3, 3, 3), target)
    expected = ndimage.affine_transform(atlas, np.eye(3), offset=[translation, 0, 0],
                                        output_shape=(3, 3, 3), order=0, mode='constant', cval=0, prefilter=False)
    assert np.array_equal(observed, expected)


def test_nearest_affine_orientation_and_zero_background():
    atlas = np.arange(1, 28).reshape(3, 3, 3)
    source = np.diag([-1.0, 1, 1, 1]); source[0, 3] = 2
    assert np.array_equal(m.nearest_labels(atlas, source, (3, 3, 3), np.eye(4)), atlas[::-1])
    target = np.eye(4); target[0, 3] = 10
    assert not np.any(m.nearest_labels(atlas, source, (3, 3, 3), target))


@pytest.mark.parametrize('kind', ['singular', 'nonfinite', 'perspective'])
def test_bad_affine_fails(kind):
    affine = np.eye(4)
    if kind == 'singular': affine[0, 0] = 0
    elif kind == 'nonfinite': affine[0, 0] = np.nan
    else: affine[3, 0] = 1
    with pytest.raises(m.PreconditionError):
        m.nearest_labels(np.ones((2, 2, 2)), affine, (2, 2, 2), np.eye(4))


def test_all_voxels_including_zero_signal_are_in_parcel_mean():
    grid = np.asarray([0, 1, 1, 2], dtype=np.int16).reshape(2, 2, 1)
    values = np.asarray([[999, 999], [0, 0], [2, 4], [-1, 3]], dtype=float).reshape(2, 2, 1, 2)
    means, counts = m.parcel_means(values, grid, [1, 2])
    assert np.array_equal(counts, [2, 1])
    assert np.array_equal(means, [[1, -1], [2, 3]])


@pytest.mark.parametrize('change', ['absent', 'unknown_label', 'nonfinite_background', 'float_ids'])
def test_parcel_support_and_all_source_finiteness(change):
    grid = np.asarray([0, 1, 1, 2], dtype=np.int16).reshape(2, 2, 1)
    values = np.ones((2, 2, 1, 4))
    ids = [1, 2]
    if change == 'absent': grid[grid == 2] = 0
    elif change == 'unknown_label': grid[0, 0, 0] = 3
    elif change == 'nonfinite_background': values[0, 0, 0, 0] = np.nan
    else: ids = [1.0, 2.0]
    with pytest.raises(m.PreconditionError): m.parcel_means(values, grid, ids)


def test_pearson_fisher_and_full_edge_identity():
    x = np.arange(10, dtype=float)
    result = m.edge_connectivity(np.column_stack([x, -x, x * 5 + 12]), [3, 7, 9])
    assert np.array_equal(result['edge_roi_i'], [3, 3, 7])
    assert np.array_equal(result['edge_roi_j'], [7, 9, 9])
    np.testing.assert_allclose(result['pearson_r'], [-1, 1, -1])
    np.testing.assert_allclose(result['fisher_z'], np.arctanh(np.array([-1, 1, -1]) * 0.999999))
    assert result['positive_z'][0] == result['positive_z'][2] == 0


def segregation(z, networks):
    ids = np.arange(1, len(networks) + 1)
    i, j = np.triu_indices(len(ids), 1)
    return m.segregation_edges(z, ids, networks, ids[i], ids[j])


def test_negative_pairs_remain_in_denominator():
    # Upper triangle: AB(within), AC/AD/BC/BD(between), CD(within).
    result = segregation([2, -10, 4, -10, 0, -2], ['a', 'a', 'b', 'b'])
    assert result['n_within_pairs'] == 2 and result['n_between_pairs'] == 4
    assert result['within_sum'] == 2 and result['between_sum'] == 4
    assert result['mean_within'] == result['mean_between'] == 1
    assert result['segregation'] == 0


def test_unequal_networks_are_pair_weighted_not_equal_system_means():
    nets = np.array(['a', 'a', 'a', 'b', 'b'])
    i, j = np.triu_indices(5, 1)
    z = np.where(nets[i] == nets[j], np.where(nets[i] == 'a', 1.0, 5.0), 0.25)
    result = segregation(z, nets)
    assert result['n_within_pairs'] == 4 and result['mean_within'] == 2
    assert result['mean_within'] != 3  # Equal-system mean would be 3.


@pytest.mark.parametrize('z', [[0, 0, 0, 0, 0, 0], [-1, -2, -3, -4, -5, -6], [0, 2, 2, 2, 2, 0]])
def test_zero_within_is_null_no_epsilon(z):
    result = segregation(z, ['a', 'a', 'b', 'b'])
    assert result['status'] == 'zero_within_mean' and result['segregation'] is None
    assert result['mean_within'] == 0


def test_negative_segregation_not_clipped_or_outcome_gated():
    result = segregation([0.01, 5, 5, 5, 5, 0.01], ['a', 'a', 'b', 'b'])
    assert result['segregation'] == pytest.approx(-499)


def test_duplicate_or_missing_pair_fails():
    with pytest.raises(m.PreconditionError, match='pair'):
        m.segregation_edges([1, 1, 1], [1, 2, 3], ['a', 'a', 'b'], [1, 1, 1], [2, 3, 3])


def test_all_member_null_propagation_no_available_case():
    result = m.cohort_summary([1.0, None, 0.2, 0.4], ['child', 'child', 'adult', 'adult'])
    assert result['cohort']['n_defined'] == 3 and result['cohort']['mean'] is None
    assert result['groups']['child']['mean'] is None
    assert result['groups']['adult']['mean'] == pytest.approx(0.3)
    assert result['adult_minus_child']['status'] == 'undefined_member'
    assert result['adult_minus_child']['ci95'] is None


def test_constant_decimal_groups_have_zero_variance():
    result = m.cohort_summary([0.1] * 31 + [0.1] * 9, ['child'] * 31 + ['adult'] * 9)
    assert result['cohort']['sample_variance'] == 0
    assert result['adult_minus_child'] == {'status': 'ok', 'estimate': 0.0, 'se': 0.0, 'ci95': [0.0, 0.0]}


def test_person_level_normal_wald_contrast():
    result = m.cohort_summary([0.1, 0.3, 0.5, 0.9], ['child', 'child', 'adult', 'adult'])
    contrast = result['adult_minus_child']
    assert contrast['estimate'] == pytest.approx(0.5)
    assert contrast['se'] == pytest.approx(np.sqrt(0.02 / 2 + 0.08 / 2))
    np.testing.assert_allclose(contrast['ci95'], [0.5 - 1.96 * np.sqrt(0.05), 0.5 + 1.96 * np.sqrt(0.05)])


@pytest.fixture
def manufactured_inputs(tmp_path):
    method_path = Path(__file__).parents[1] / 'environment/method_contract.json'
    method = json.loads(method_path.read_text())
    people = ['sub-pixar001', 'sub-pixar002', 'sub-pixar123', 'sub-pixar124']
    method['source']['participant_ids'] = people
    source = tmp_path / 'source'; source.mkdir()
    rng = np.random.default_rng(32)
    images, paths, phenotype = {}, {}, {}
    for k, pid in enumerate(people):
        data = rng.normal(size=(101, 1, 1, 40)).astype(np.float32)
        images[pid] = nib.Nifti1Image(data, np.eye(4))
        paths[pid] = {'bold': pid + '.nii.gz', 'confounds': pid + '.tsv'}
        confounds = rng.normal(size=(40, 15))
        header = '\t'.join(method['preprocessing']['confound_columns'])
        lines = ['\t'.join(map(str, row)) for row in confounds]
        (source / paths[pid]['confounds']).write_text(header + '\n' + '\n'.join(lines) + '\n')
        phenotype[pid] = {'participant_id': pid, 'source_row_index': k,
                          'group': 'child' if k < 2 else 'adult', 'age': 4.0 if k < 2 else 25.0}
    networks = method['geometry']['network_names']
    lut = '\n'.join(f'{i} 7Networks_LH_{networks[(i-1) % 7]}_Fixture_{i} 1 2 3 0' for i in range(1, 101))
    (source / 'labels.txt').write_text(lut + '\n')
    atlas = nib.Nifti1Image(np.arange(101, dtype=np.float32).reshape(101, 1, 1), np.eye(4))
    return {'source': source, 'method': method, 'manifest': {'files': []}, 'paths': paths,
            'single': {'atlas_labels': 'labels.txt'}, 'phenotype': phenotype, 'images': images,
            'atlas': atlas, 'observed': {'n_selected_participants': 4}}


@pytest.mark.parametrize('pilot', [None, 'sub-pixar001'])
def test_manufactured_complete_run_writes_seven_files_and_private(tmp_path, monkeypatch, manufactured_inputs, pilot):
    monkeypatch.setattr(c, 'load_inputs', lambda *_: manufactured_inputs)
    output = tmp_path / 'output'; private = tmp_path / 'private'
    output.mkdir(); private.mkdir()
    result = c.run(manufactured_inputs['source'], tmp_path / 'method.json', output, private, pilot)
    assert set(p.name for p in output.iterdir()) == set(manufactured_inputs['method']['artifacts'])
    assert result['status'] == ('resource_pilot' if pilot else 'ok')
    assert result['n_participants'] == (1 if pilot else 4)
    with np.load(output / 'connectivity.npz', allow_pickle=False) as arrays:
        assert arrays['raw_mean'].shape == ((1 if pilot else 4), 40, 100)
        assert arrays['fisher_z'].shape == ((1 if pilot else 4), 4950)
        np.testing.assert_allclose(arrays['standardized_clean'].std(axis=1, ddof=1), 1)
    with np.load(private / 'analysis_arrays.npz', allow_pickle=False) as arrays:
        assert arrays['target_label_grid'].shape == (101, 1, 1)
    metadata = json.loads((output / 'run_metadata.json').read_text())
    assert metadata['warnings'] == [] and metadata['source_observed']['n_selected_participants'] == 4
    if pilot:
        assert result['adult_minus_child']['estimate'] is None
        assert result['resource_pilot_scope']['full_cohort_analysis'] is False


def test_native_nifti_calibration_and_header_retained(tmp_path):
    data = np.arange(8, dtype=np.int8).reshape(2, 2, 2)
    image = nib.Nifti1Image(data, np.eye(4)); image.header.set_slope_inter(2.5, -13)
    path = tmp_path / 'calibrated.nii.gz'; nib.save(image, path)
    loaded = nib.load(path)
    row = c.header_record(loaded, path.name)
    assert row['intensity_slope'] == 2.5 and row['intensity_intercept'] == -13
    assert row['storage_dtype'] == 'int8'
    np.testing.assert_array_equal(np.asarray(loaded.dataobj, dtype=np.float64), data * 2.5 - 13)


@pytest.mark.parametrize('text', ['{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}', '{"a":[Infinity]}'])
def test_strict_json_rejects_duplicate_and_nonfinite(tmp_path, text):
    path = tmp_path / 'bad.json'; path.write_text(text)
    with pytest.raises(c.PreconditionError): c.strict_json(path)


def test_header_wrong_identity_fails():
    method = json.loads((Path(__file__).parents[1] / 'environment/method_contract.json').read_text())
    with pytest.raises(c.PreconditionError, match='shape'):
        c.validate_header({'shape': [1]}, method['source']['observed_structure'], 'bold')


@pytest.mark.parametrize('kind', ['source_equal', 'inside_source', 'contains_source', 'private_equal', 'private_nested', 'method_overlap'])
def test_destination_overlap_fails_without_mutation(tmp_path, kind):
    source = tmp_path / 'source'; source.mkdir()
    (source / 'preserved').write_text('original')
    method = tmp_path / 'method.json'; method.write_text('{}')
    output, private = tmp_path / 'out', tmp_path / 'private'
    if kind == 'source_equal': output = source
    elif kind == 'inside_source': output = source / 'out'
    elif kind == 'contains_source': output = tmp_path
    elif kind == 'private_equal': private = output
    elif kind == 'private_nested': private = output / 'private'
    else: output = method
    with pytest.raises(c.PreconditionError): c.destinations(source, method, output, private)
    assert (source / 'preserved').read_text() == 'original'
    assert not (tmp_path / 'out').exists()


@pytest.mark.parametrize('dangling', [False, True])
@pytest.mark.parametrize('dotdot', [False, True])
def test_literal_symlink_ancestor_rejected_before_normalization(tmp_path, dangling, dotdot):
    target = tmp_path / 'target'
    if not dangling: target.mkdir()
    link = tmp_path / 'link'; link.symlink_to(target, target_is_directory=True)
    path = link / '..' / 'dest' if dotdot else link / 'dest'
    with pytest.raises(c.PreconditionError, match='symlink'): c.safe_path(path)
    assert not (tmp_path / 'dest').exists()


def test_literal_dotdot_normalizes_before_overlap_check(tmp_path):
    source = tmp_path / 'source'; source.mkdir()
    method = tmp_path / 'method.json'; method.write_text('{}')
    with pytest.raises(c.PreconditionError, match='overlap'):
        c.destinations(source, method, tmp_path / 'unused' / '..' / 'source' / 'out')


def test_existing_evidence_untouched(tmp_path):
    output = tmp_path / 'out'; output.mkdir()
    old = output / 'old.txt'; old.write_text('keep')
    assert c.main(['--data-dir', str(tmp_path / 'source'), '--method-contract', str(tmp_path / 'method'),
                   '--output-dir', str(output)]) == 1
    assert list(output.iterdir()) == [old] and old.read_text() == 'keep'


def test_empty_harbor_output_allowed(tmp_path):
    output = tmp_path / 'out'; output.mkdir()
    result = c.destinations(tmp_path / 'source', tmp_path / 'method', output)
    assert result[2] == output and not any(output.iterdir())


def test_missing_input_cli_actual_solve_emits_failure_receipt(tmp_path):
    solve = Path(__file__).parents[1] / 'solution/solve.sh'
    output = tmp_path / 'out'
    result = subprocess.run([str(solve), '--data-dir', str(tmp_path / 'absent'),
        '--method-contract', str(tmp_path / 'absent.json'), '--output-dir', str(output)], capture_output=True, text=True)
    assert result.returncode == 1
    failure = json.loads((output / 'failure_receipt.json').read_text())
    assert failure['status'] == 'failed_precondition' and failure['reason']
    assert not (output / 'run_metadata.json').exists()


def test_help_is_import_safe_and_needs_no_source(tmp_path):
    solve = Path(__file__).parents[1] / 'solution/solve.sh'
    env = dict(os.environ, OUTPUT_DIR=str(tmp_path / 'never_created'))
    result = subprocess.run([str(solve), '--help'], env=env, capture_output=True, text=True)
    assert result.returncode == 0 and '--pilot-subject' in result.stdout
    assert not (tmp_path / 'never_created').exists()


@pytest.mark.parametrize('where', ['private', 'late_metadata'])
def test_partial_failure_never_becomes_unguarded_success(tmp_path, monkeypatch, manufactured_inputs, where):
    monkeypatch.setattr(c, 'load_inputs', lambda *_: manufactured_inputs)
    output, private = tmp_path / 'out', tmp_path / 'private'
    if where == 'private':
        original = c.write_npz
        def writer(path, arrays):
            if path.parent == private: raise OSError('manufactured private failure')
            return original(path, arrays)
        monkeypatch.setattr(c, 'write_npz', writer)
    else:
        original = c.write_json
        def writer(path, value):
            if path.name == 'run_metadata.json': raise OSError('manufactured metadata failure')
            return original(path, value)
        monkeypatch.setattr(c, 'write_json', writer)
    code = c.main(['--data-dir', str(manufactured_inputs['source']), '--method-contract', str(tmp_path / 'method'),
                   '--output-dir', str(output), '--private-dir', str(private)])
    assert code == 1
    assert json.loads((output / 'failure_receipt.json').read_text())['reason'].startswith('manufactured')
    assert (output / 'connectivity.npz').is_file() and not (output / 'run_metadata.json').exists()
    if where == 'private': assert not (output / 'cohort_results.json').exists()


def test_source_pin_and_method_pin_are_checked_before_parser(tmp_path, monkeypatch):
    method = tmp_path / 'method.json'; method.write_text('{"method_id":"incorrect"}')
    monkeypatch.setattr(c, 'source_verifier', lambda: pytest.fail('stager should not run'))
    with pytest.raises(c.PreconditionError, match='method contract'):
        c.load_inputs(tmp_path / 'source', method)


def test_selected_confounds_no_imputation_or_extra_columns(tmp_path):
    path = tmp_path / 'confounds.tsv'; path.write_text('chosen\textra\n1\tn/a\n2\tNaN\n')
    np.testing.assert_array_equal(c.selected_confounds(path, ['chosen'], 2), [[1], [2]])
    with pytest.raises((ValueError, c.PreconditionError)):
        c.selected_confounds(path, ['extra'], 2)


@pytest.mark.parametrize('header', ['a\ta', 'a\tb'])
def test_tsv_duplicate_and_short_rows_rejected(tmp_path, header):
    path = tmp_path / 'table.tsv'; path.write_text(header + '\n1\n')
    with pytest.raises(c.PreconditionError): c.read_tsv(path)
