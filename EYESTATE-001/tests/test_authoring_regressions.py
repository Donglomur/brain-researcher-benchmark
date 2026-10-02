"""Source-free parser, equivalence and adversarial fixtures; no original ROI reads."""
import copy
import json
import os
from pathlib import Path
import shutil
import stat
import tomllib
import numpy as np
import pytest
import fixture_support as f
import io_contract as io
import metric_contract as m
import proof_of_work as p
import source_reference as source


@pytest.fixture(scope='module')
def reference():
    return f.manufactured_reference()


@pytest.fixture(scope='module')
def baseline(tmp_path_factory, reference):
    return f.emit_manufactured(tmp_path_factory.mktemp('toy') / 'output', reference)


@pytest.fixture
def case(tmp_path, baseline):
    return Path(shutil.copytree(baseline, tmp_path / 'output'))


def reject(case, ref):
    with pytest.raises((AssertionError, ValueError, TypeError, KeyError, EOFError, OSError)):
        p.validate_output_directory(case, ref)


def test_complete_manufactured(case, reference):
    p.validate_output_directory(case, reference)


@pytest.mark.parametrize('kind', ['receipt', 'empty', 'dangling_symlink'])
def test_late_failure_marker_rejects_otherwise_complete_output(case, reference, kind):
    path = case / 'failure_report.json'
    if kind == 'dangling_symlink': path.symlink_to(case / 'absent')
    else: path.write_text('{"status":"failed_precondition"}' if kind == 'receipt' else '')
    with pytest.raises(AssertionError, match='reserved failure_report'):
        p.validate_output_directory(case, reference)


def test_equivalent_nonidentical_solver(tmp_path, reference):
    # The public gap permits this independently specified near-optimum vector;
    # no private coefficient equality is allowed to reject it.
    case = f.emit_manufactured(tmp_path / 'alternative', reference, intercept_delta=1e-7)
    p.validate_output_directory(case, reference)


def test_nearzero_own_sign_and_recomputed_metrics(tmp_path, reference):
    case = f.emit_manufactured(tmp_path / 'nearzero', reference, nearzero_reported_score=5e-9)
    result = p.validate_output_directory(case, reference)
    assert np.all(result['predictions']['random10'] == 1)


def test_rounded_evidence_is_not_a_new_model_input(case, reference):
    # Allowed serialization noise in an exactly constant source feature must
    # not get standardized into an invented classification signal.
    def feature_change(a):
        a['correlation'][:] = np.linspace(-5e-9, 5e-9, len(a['phenotype_row']))[:, None]
    f.rewrite_npz(case / 'features.npz', feature_change)
    p.validate_output_directory(case, reference)


def test_changed_model_does_not_reuse_cached_acceptance(case, reference):
    p.validate_output_directory(case, reference)
    f.rewrite_npz(case / 'fold_models.npz', lambda a: a['intercept'].__setitem__(0, 7.))
    reject(case, reference)


def test_order_float_integer_notation_and_extras(case, reference):
    for name in ('cohort.csv', 'oof_predictions.csv', 'per_fold.csv'):
        columns, rows = f.read_csv(case / name)
        for row in rows:
            row['harmless_note'] = 'extra'
            for key in ('phenotype_row', 'subject_id', 'fold_id'):
                if key in row: row[key] = format(int(row[key]), '.17e')
        f.write_csv(case / name, ['harmless_note'] + columns[::-1], rows[::-1])
    rng = np.random.default_rng(7)
    def features(a):
        r = rng.permutation(len(a['phenotype_row'])); c = rng.permutation(len(a['feature_index']))
        for k in ('phenotype_row', 'subject_id', 'shrinkage'): a[k] = a[k][r]
        for k in ('feature_index', 'roi_i', 'roi_j'): a[k] = a[k][c]
        a['correlation'] = a['correlation'][np.ix_(r, c)].astype('float32')
        for k in ('phenotype_row', 'subject_id', 'feature_index', 'roi_i', 'roi_j'): a[k] = a[k].astype(float)
    f.rewrite_npz(case / 'features.npz', features)
    def models(a):
        r = rng.permutation(len(a['fold_id'])); c = rng.permutation(len(a['feature_index']))
        for k in ('scheme', 'fold_id', 'intercept'): a[k] = a[k][r]
        for k in ('scaler_mean', 'scaler_variance', 'scaler_scale', 'coefficient'): a[k] = a[k][np.ix_(r, c)]
        a['feature_index'] = a['feature_index'][c].astype(float)
        a['fold_id'] = a['fold_id'].astype(float)
    f.rewrite_npz(case / 'fold_models.npz', models)
    def metadata(a):
        a['optional_analysis'] = {'no_keyword_gate': True}
        a['software_versions'] = {'different_solver': 2}
        a['fit_warnings'].reverse()
        for key in ('site_support', 'frame_count_histogram', 'roi_count_histogram', 'constant_roi_count_histogram'):
            a['source_observed'][key].reverse()
    f.rewrite_json(case / 'run_metadata.json', metadata)
    p.validate_output_directory(case, reference)


@pytest.mark.parametrize('filename', ['cohort.csv', 'features.npz', 'fold_models.npz', 'oof_predictions.csv',
                                    'per_fold.csv', 'eye_decoding_results.json', 'run_metadata.json', 'findings.md'])
def test_missing_artifact(case, reference, filename):
    (case / filename).unlink(); reject(case, reference)


@pytest.mark.parametrize('field,value', [('phenotype_row', 'True'), ('subject_id', '900001'), ('site', 'invented'),
                                       ('eye_code', '2'), ('label', '0'), ('n_timepoints', '81'),
                                       ('n_constant_rois', '1'), ('n_low_sd_rois', '1'), ('included', 'false'),
                                       ('selected_index', '1'), ('source_sha256', 'b' * 64)])
def test_cohort_bound(case, reference, field, value):
    f.rewrite_csv(case / 'cohort.csv', lambda rows: rows[0].update({field: value}))
    reject(case, reference)


@pytest.mark.parametrize('mode', ['duplicate_row', 'duplicate_feature', 'wrong_endpoint', 'wrong_subject',
                                 'boolean_axis', 'fraction_axis', 'overflow_axis', 'nonfinite', 'wrong_fc',
                                 'wrong_shrinkage', 'object_array', 'partial'])
def test_feature_mutations(case, reference, mode):
    def update(a):
        if mode == 'duplicate_row': a['phenotype_row'][1] = a['phenotype_row'][0]
        elif mode == 'duplicate_feature': a['feature_index'][1] = a['feature_index'][0]
        elif mode == 'wrong_endpoint': a['roi_i'][0] += 1
        elif mode == 'wrong_subject': a['subject_id'][0] += 1000
        elif mode == 'boolean_axis': a['phenotype_row'] = a['phenotype_row'].astype(bool)
        elif mode == 'fraction_axis': a['phenotype_row'] = a['phenotype_row'].astype(float) + .5
        elif mode == 'overflow_axis': a['phenotype_row'] = a['phenotype_row'].astype(float) + 1e30
        elif mode == 'nonfinite': a['correlation'][0, 0] = np.nan
        elif mode == 'wrong_fc': a['correlation'][0, 0] = .04
        elif mode == 'wrong_shrinkage': a['shrinkage'][0] = .5
        elif mode == 'object_array': a['extra'] = np.array([{}], dtype=object)
        elif mode == 'partial': a['correlation'] = a['correlation'][:-1]
    f.rewrite_npz(case / 'features.npz', update); reject(case, reference)


@pytest.mark.parametrize('mode', ['mean', 'scale', 'variance', 'coefficient', 'intercept', 'duplicate_model', 'nonfinite'])
def test_model_source_and_objective(case, reference, mode):
    def update(a):
        if mode in ('mean', 'scale', 'variance'): a['scaler_' + mode][0, 0] += .1
        elif mode == 'coefficient': a['coefficient'][0, 0] = 1
        elif mode == 'intercept': a['intercept'][0] += 1
        elif mode == 'duplicate_model': a['fold_id'][1] = a['fold_id'][0]
        else: a['coefficient'][0, 0] = np.inf
    f.rewrite_npz(case / 'fold_models.npz', update); reject(case, reference)


@pytest.mark.parametrize('field,value', [('decision_score', '1'), ('prediction', '0'), ('label', '0'),
                                       ('fold_id', '99'), ('training_majority_prediction', '0'),
                                       ('held_out_site', 'B'), ('subject_id', '0')])
def test_oof_identity_and_own_arithmetic(case, reference, field, value):
    f.rewrite_csv(case / 'oof_predictions.csv', lambda rows: rows[0].update({field: value}))
    # The initial LOSO fold is held-out A, trains 7 open/8 closed and predicts0;
    # use an actual changed value for sign and majority rather than a no-op.
    if field in ('prediction', 'training_majority_prediction'):
        f.rewrite_csv(case / 'oof_predictions.csv', lambda rows: rows[0].update({field: '1'}))
    reject(case, reference)


@pytest.mark.parametrize('filename', ['cohort.csv', 'oof_predictions.csv', 'per_fold.csv'])
def test_duplicate_csv_key(case, reference, filename):
    f.rewrite_csv(case / filename, lambda rows: rows.append(rows[0].copy())); reject(case, reference)


@pytest.mark.parametrize('field', ['cv_balanced_accuracy', 'legacy_equal_site_mean_recall', 'site_only_unseen_site_baseline',
                                 'random_kfold_balanced_accuracy', 'n_subjects'])
def test_fabricated_summary(case, reference, field):
    f.rewrite_json(case / 'eye_decoding_results.json', lambda a: a.update({field: a[field] + .1})); reject(case, reference)


@pytest.mark.parametrize('mode', ['status', 'source_hash', 'source_extra', 'method_hash', 'missing_observed',
                                 'missing_warning', 'unknown_warning', 'nonfinite_extra', 'boolean_count'])
def test_metadata(case, reference, mode):
    def update(a):
        if mode == 'status': a['status'] = 'failed_precondition'
        elif mode == 'source_hash': a['source_manifest_sha256'] = 'f' * 64
        elif mode == 'source_extra': a['source_sha256']['fictitious'] = 'f' * 64
        elif mode == 'method_hash': a['method_contract_sha256'] = 'f' * 64
        elif mode == 'missing_observed': del a['source_observed']['constant_roi_count_histogram']
        elif mode == 'missing_warning': a['fit_warnings'].pop()
        elif mode == 'unknown_warning': a['fit_warnings'][0]['scheme'] = 'unknown'
        elif mode == 'boolean_count': a['source_observed']['n_features'] = True
    if mode == 'nonfinite_extra':
        text = (case / 'run_metadata.json').read_text()
        (case / 'run_metadata.json').write_text(text[:-1] + ', "extra":{"nested":1e999}}')
    else: f.rewrite_json(case / 'run_metadata.json', update)
    reject(case, reference)


@pytest.mark.parametrize('bad', ['1e100000000', '-1e100000000', '9223372036854775808', '-9223372036854775809',
                               'NaN', 'Infinity', '1.25', True])
def test_integer_failclosed(bad):
    with pytest.raises(AssertionError): io.integer(bad)


@pytest.mark.parametrize('value', ['9.007199254740993e15', '9223372036854775807', '-9223372036854775808', '2.0e0'])
def test_exact_integer_notation(value):
    from decimal import Decimal
    assert io.integer(value) == int(Decimal(value))


@pytest.mark.parametrize('text', ['{"a":1,"a":2}', '{"extra":[{"a":1e999}]}', '{"a":NaN}'])
def test_json_strict(text):
    with pytest.raises(AssertionError): io.json_text(text)


@pytest.mark.parametrize('mode', ['directory', 'fifo', 'dangling_symlink'])
def test_source_cache_all_nodes(tmp_path, mode):
    (tmp_path / 'file').write_text('a'); before = source.source_stat_snapshot(tmp_path)
    if mode == 'directory': (tmp_path / 'unexpected').mkdir()
    elif mode == 'fifo': os.mkfifo(tmp_path / 'fifo')
    elif mode == 'dangling_symlink': (tmp_path / 'dangling').symlink_to(tmp_path / 'absent')
    if mode in ('fifo', 'dangling_symlink'):
        with pytest.raises(AssertionError): source.source_stat_snapshot(tmp_path)
    else: assert source.source_stat_snapshot(tmp_path) != before


def test_source_cache_reauthenticates_bytes_even_restored_timestamps(tmp_path, monkeypatch):
    root = tmp_path / 'source'; root.mkdir(); original = root / 'original.txt'; original.write_text('abc')
    method = tmp_path / 'method.json'; method.write_text('{}')
    manifest = root / 'source_manifest.json'
    manifest.write_text(json.dumps({'files': [dict(path='original.txt', size_bytes=3, sha256=io.sha256(original))]}))
    monkeypatch.setattr(source, 'METHOD_SHA256', io.sha256(method))
    monkeypatch.setattr(source, 'SOURCE_SHA256', io.sha256(manifest))
    ref = {'snapshot': source.source_stat_snapshot(root)}
    monkeypatch.setattr(source, '_construct', lambda *args: ref)
    assert source.load_reference(root, method) is ref
    st = original.stat(); original.write_text('xyz'); os.utime(original, ns=(st.st_atime_ns, st.st_mtime_ns))
    with pytest.raises(AssertionError, match='source member bytes'): source.load_reference(root, method)


@pytest.mark.parametrize('mode', ['within_source', 'dotdot_source', 'source_ancestor', 'same_output_report',
                                 'output_ancestor', 'existing', 'symlink', 'dangling', 'fifo'])
def test_source_receipt_destinations(tmp_path, mode):
    root = tmp_path / 'source'; root.mkdir(); (root / 'method.json').write_text('{}')
    output, report = tmp_path / 'new.npz', tmp_path / 'report.json'
    if mode == 'within_source': output = root / 'new.npz'
    elif mode == 'dotdot_source': output = tmp_path / 'absent' / '..' / 'source' / 'new.npz'
    elif mode == 'source_ancestor': output = tmp_path
    elif mode == 'same_output_report': report = output
    elif mode == 'output_ancestor': report = output / 'report.json'
    elif mode == 'existing': output.write_text('preserve')
    elif mode == 'symlink': output.symlink_to(root / 'method.json')
    elif mode == 'dangling': output.symlink_to(tmp_path / 'absent')
    else: os.mkfifo(output)
    with pytest.raises(AssertionError): source.destinations(root, root / 'method.json', output, report)
    assert (root / 'method.json').read_text() == '{}'


def test_source_receipt_exclusive_external_only(tmp_path, reference):
    root = tmp_path / 'source'; root.mkdir(); method = root / 'method.json'; method.write_text('{}')
    output, report = source.destinations(root, method, tmp_path / 'new.npz', tmp_path / 'report.json')
    receipt = source.write_source_receipt(reference, output, report, 'resource_pilot', 0.)
    assert receipt['status'] == 'resource_pilot' and receipt['n_features'] == [20, 19900]
    with np.load(output, allow_pickle=False) as archive:
        np.testing.assert_array_equal(archive['correlation'], reference['features'])
        assert archive['scaler_mean'].shape[1] == 19900
    original = output.read_bytes()
    with pytest.raises(FileExistsError): source.write_source_receipt(reference, output, report, 'resource_pilot', 0.)
    assert output.read_bytes() == original


def test_packaging_offline_and_harvest():
    task = Path(__file__).parents[1]
    config = tomllib.loads((task / 'task.toml').read_text())
    assert {'/app/output', '/app/data/eyestate/source_manifest.json', '/app/method_contract.json'} <= set(config['artifacts'])
    assert len(f.public_method()['artifacts']) == 8
    shell = (task / 'tests/test.sh').read_text()
    assert 'python3 -m pytest' in shell and 'echo 0 > /logs/verifier/reward.txt' in shell
    assert all(token not in shell for token in ('uvx', 'apt-get', 'pip install', '$HOME', 'source '))
    assert (task / 'tests/test.sh').stat().st_mode & stat.S_IXUSR
    docker = (task / 'environment/Dockerfile').read_text()
    assert 'reference.npz' not in docker and 'COPY tests' not in docker and 'COPY solution' not in docker
