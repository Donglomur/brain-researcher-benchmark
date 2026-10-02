"""Manufactured arithmetic/emission only; never opens original source values."""
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import warnings

import numpy as np
import pytest
from scipy.stats import pearsonr

SOLUTION = Path(__file__).resolve().parents[1] / 'solution'
sys.path.insert(0, str(SOLUTION))
import core as oracle
import partition_contract as partition
import compute


def qfixture():
    return np.random.default_rng(81).normal(size=(7, 17, 10)).astype(np.float32)


def test_exact_declared_vertex_expression():
    x = np.array([[1e8, 1, -1e8, 7], [3, 4, 5, 8]], dtype=np.float32)
    ids = [np.array([0, 1, 2]), np.array([3])]
    q, before = oracle.parcel_means(x, ids)
    expect = np.column_stack([np.asarray(x[:, v], dtype=np.float64, order='C').mean(axis=1, dtype=np.float64) for v in ids])
    assert np.array_equal(before, expect) and np.array_equal(q, expect.astype(np.float32))
    assert q[0, 0] == np.float32(1 / 3)


@pytest.mark.parametrize('indices', [[1, 0], [0, 0], [-1], [4], [], [0.5], [True]])
def test_parcel_membership_rejects_invalid(indices):
    with pytest.raises(ValueError):
        oracle.parcel_means(np.ones((4, 4), np.float32), [np.asarray(indices)])


@pytest.mark.parametrize('bad', [np.nan, np.inf, -np.inf])
def test_nonfinite_original_fails(bad):
    x = np.ones((3, 3), np.float32); x[0, 0] = bad
    with pytest.raises(ValueError):
        oracle.parcel_means(x, [np.array([0, 1])])


def test_canonical_corrcoef_upper_and_clip():
    q = qfixture()[0]
    q[:, 1] = q[:, 0]
    q[:, 2] = -q[:, 0]
    a = oracle.individual_connectome(q)
    i, j = a['edge_roi_index'].T
    expected = np.corrcoef(q.astype(float).T)[i, j]
    assert np.array_equal(a['raw_r'], expected)
    assert np.array_equal(a['fisher_z'], np.arctanh(np.clip(expected, -.999, .999)))
    assert a['raw_r'][0] == 1 and a['fisher_z'][0] == oracle.ZMAX


@pytest.mark.parametrize('constant', [0, .1, -2, np.finfo(np.float32).tiny])
def test_exact_constant_status_not_mean_roundoff(constant):
    q = qfixture()[0]; q[:, 4] = np.float32(constant)
    a = oracle.individual_connectome(q)
    hits = np.any(a['edge_roi_index'] == 4, axis=1)
    assert a['parcel_status'][4] == 'constant'
    assert not a['edge_valid'][hits].any() and np.isnan(a['raw_r'][hits]).all()
    assert a['edge_valid'][~hits].all()


@pytest.mark.parametrize('frames', [0, 1])
def test_insufficient_frames_explicit(frames):
    a = oracle.individual_connectome(np.empty((frames, 8), np.float32) if frames == 0 else np.ones((1, 8), np.float32))
    assert (a['parcel_status'] == 'insufficient_frames').all() and not a['edge_valid'].any()


def test_arbitrarily_small_nonconstant_is_kept():
    q = np.array([[0, 0], [1e-43, 2e-43], [2e-43, 4e-43]], dtype=np.float32)
    assert oracle.individual_connectome(q)['edge_valid'].all()


def test_noncanonical_double_values_refused():
    with pytest.raises(ValueError, match='exact float32'):
        oracle.individual_connectome(np.array([[.1, .2], [.3, .4]], dtype=float))


def test_group_adds_in_order_then_mirrors():
    z = np.array([[1.0], [2.0 ** -54], [-1.0]])
    edges = np.array([[0, 1]])
    group, mask = oracle.group_connectome(z, np.ones_like(z, bool), edges, 2, 3)
    assert group[0, 1] == ((0 + z[0, 0]) + z[1, 0] + z[2, 0]) / 3
    assert np.array_equal(group, group.T) and np.diag(group).tolist() == [0, 0] and mask.all()


def test_group_missing_person_or_edge_is_not_subset_average():
    edges = np.array([[0, 1], [0, 2], [1, 2]])
    z = np.array([[1., 2., 3.], [2., np.nan, 4.]])
    for expected in (2, 3):
        group, mask = oracle.group_connectome(z, np.isfinite(z), edges, 3, expected)
        assert not mask[0, 2] and np.isnan(group[0, 2])
        if expected == 3:
            assert mask.sum() == 3


def test_partition_full_recipe_one_fit_and_cap_retained(monkeypatch):
    calls = []
    class Fake:
        def __init__(self, **kw):
            assert kw == partition.PARAMETERS
        def fit(self, x, sample_weight):
            calls.append(x.copy())
            assert x.dtype == np.float64 and x.flags.c_contiguous and sample_weight is None
            self.labels_ = np.arange(8) % 7
            self.cluster_centers_ = np.zeros((7, 8))
            self.inertia_, self.n_iter_ = 3., 300
            warnings.warn('retained manufactured cap warning')
            return self
    monkeypatch.setattr(partition, 'KMeans', Fake)
    out = partition.fit_partition(np.zeros((8, 8)), np.ones((8, 8), bool))
    assert len(calls) == 1 and out['n_iter'] == 300 and out['status'] == 'ok'
    assert 'manufactured cap warning' in out['warnings'][0]


def test_incomplete_partition_does_not_fit(monkeypatch):
    monkeypatch.setattr(partition, 'KMeans', lambda **k: pytest.fail('incomplete input fit'))
    valid = np.eye(8, dtype=bool)
    out = partition.fit_partition(np.where(valid, 0, np.nan), valid)
    assert out['status'] == 'incomplete_group_connectome' and out['labels'] is None


def test_fewer_than_seven_actual_returned_clusters():
    out = partition.fit_partition(np.zeros((8, 8)), np.ones((8, 8), bool))
    assert out['status'] == 'fewer_than_seven_occupied_clusters' and out['n_clusters_occupied'] == 1
    assert out['labels'] is not None and out['warnings']


def summary_fixture(values, labels=None):
    labels = np.array([0, 0, 0, 1, 1, 2, 3, 4, 5, 6]) if labels is None else np.asarray(labels)
    edges = np.column_stack(np.triu_indices(len(labels), 1))
    z = np.broadcast_to(values, (len(edges),)).copy()[None, :]
    rows = oracle.summarize_people(z, np.isfinite(z), edges, np.full((1, len(labels)), 'ok'),
                                  {'status': 'ok', 'labels': labels}, ['S'], [25])
    return rows[0], edges, labels


def test_signed_global_full_pair_zero_clipped_means():
    values = np.zeros(45); values[0] = 2; values[1] = -1; values[-1] = 3
    row, edges, labels = summary_fixture(values)
    assert row['global_fisher_sum'] == 4 and row['global_connectivity'] == 4 / 45
    assert row['n_within_edges'] == 4 and row['within_positive_sum'] == 2
    assert row['within_network_connectivity'] == .5
    assert row['between_network_connectivity'] == 3 / 41
    assert row['system_segregation'] == (.5 - 3 / 41) / .5


def test_zero_within_retains_means_and_nulls_ratio():
    row, _, _ = summary_fixture(-np.ones(45))
    assert row['segregation_status'] == 'zero_within_mean'
    assert row['within_network_connectivity'] == row['between_network_connectivity'] == 0
    assert row['system_segregation'] is None and row['global_connectivity'] == -1


def test_tiny_positive_within_not_thresholded():
    row, _, _ = summary_fixture(np.full(45, 1e-300))
    assert row['segregation_status'] == 'ok' and row['system_segregation'] == 0


def test_empty_family_status():
    row, _, _ = summary_fixture(1., labels=np.arange(7))
    assert row['n_within_edges'] == 0 and row['segregation_status'] == 'empty_pair_family'


@pytest.mark.parametrize('mode,status', [('missing', 'incomplete_subject_support'), ('age', 'constant_age'), ('summary', 'constant_summary')])
def test_endpoint_undefined_precedence(mode, status):
    age, values, ids = list(range(8)), list(range(8)), list('abcdefgh')
    if mode == 'missing':
        values[0] = None; age = [1] * 8
    elif mode == 'age':
        age = [1] * 8; values = [2] * 8
    else:
        values = [2] * 8
    out, _ = oracle.endpoint(age, values, ids, ids)
    assert out['status'] == status and out['pearson_r'] is out['p'] is out['ci95'] is None
    assert out['n_defined'] == (7 if mode == 'missing' else 8)


@pytest.mark.parametrize('sign', [-1, 1])
def test_signed_perfect_endpoint_does_not_force_ci_containment(sign):
    x = np.arange(59, dtype=float)
    ids = [str(i) for i in range(59)]
    out, _ = oracle.endpoint(x, sign * x, ids, ids)
    expected = pearsonr(x, sign * x)
    assert out['pearson_r'] == expected.statistic and out['p'] == expected.pvalue
    assert out['ci95'] == pytest.approx(np.tanh(np.arctanh(sign * .999999) + np.array([-1, 1]) * 1.96 / np.sqrt(56)))


def test_full_analyze_and_public_npz_axes():
    q = qfixture(); ids = [f'S{i}' for i in range(7)]
    a = oracle.analyze(q, np.arange(7, dtype=np.float32), ids)
    assert a['results']['status'] == 'ok' and a['parcel_status'].shape == (7, 10)
    assert a['raw_r'].shape == (7, 45) and a['partition']['n_clusters_occupied'] == 7
    assert len(a['summary']) == 7 and a['results']['overall_connectivity_vs_age']['n_expected'] == 7


def test_pilot_never_fits_or_computes_age_inference(monkeypatch):
    monkeypatch.setattr(partition, 'KMeans', lambda **k: pytest.fail('pilot fit'))
    monkeypatch.setattr(oracle, 'pearsonr', lambda *a: pytest.fail('pilot age inference'))
    q = qfixture()[:1]
    out = oracle.analyze(q, [20], ['S0'], expected_subject_ids=['S0', 'S1'], pilot=True)
    assert out['results']['status'] == 'resource_pilot'
    assert out['partition']['status'] == 'incomplete_group_connectome'
    assert out['results']['overall_connectivity_vs_age']['undefined_subject_ids'] == ['S1']


def manufactured_inputs():
    q = qfixture(); ids = [f'S{i}' for i in range(7)]
    p = dict(subject_ids=ids, membership={'lh': [np.array([i]) for i in range(5)],
                                         'rh': [np.array([i]) for i in range(5)]},
             parcels=[dict(roi_index=i, hemisphere='lh' if i < 5 else 'rh', annotation_id=i % 5,
                           label_name=f'R{i}', vertex_count=1) for i in range(10)],
             phenotype={s: dict(phenotype_row_index=i, age_source=float(i), age_computational=float(i), sex='X') for i, s in enumerate(ids)},
             sources={(s, h): dict(path=f'{s}_{h}.gii', sha256='1' * 64) for s in ids for h in ('lh', 'rh')},
             manifest={'files': []}, annotation_diagnostics=[])
    return p, q


def test_nine_files_and_private_safe_serialization(tmp_path):
    inputs, q = manufactured_inputs(); ids = inputs['subject_ids']
    analysis = oracle.analyze(q, range(7), ids)
    art = compute.make_artifacts(inputs, ids, q, [], analysis, False)
    compute.emit(tmp_path, art)
    assert len(list(tmp_path.iterdir())) == 9
    with np.load(tmp_path / 'connectome_primitives.npz', allow_pickle=False) as z:
        assert len(z.files) == 14 and z['roi_timeseries'].shape == (119, 10)
        assert z['subject_frame_offsets'].tolist() == list(range(0, 120, 17))
    assert json.loads((tmp_path / 'run_metadata.json').read_text())['status'] == 'ok'


@pytest.mark.parametrize('mode', ['runtime', 'read_subject', 'private_write', 'late_emit', 'private_mkdir'])
def test_failure_marker_and_no_stale_success(tmp_path, monkeypatch, mode):
    inputs, q = manufactured_inputs()
    monkeypatch.setattr(compute, 'check_runtime', lambda: None)
    monkeypatch.setattr(compute.source, 'load_inputs', lambda *a: inputs)
    monkeypatch.setattr(compute.source, 'read_subject', lambda inp, s: (q[inp['subject_ids'].index(s)], q[0].astype(float), {'subject_id': s}))
    def fail(*a, **k):
        raise ValueError('manufactured failure')
    if mode == 'runtime':
        monkeypatch.setattr(compute, 'check_runtime', fail)
    elif mode == 'read_subject':
        monkeypatch.setattr(compute.source, 'read_subject', fail)
    elif mode == 'private_write':
        monkeypatch.setattr(compute, 'write_npz', fail)
    elif mode == 'late_emit':
        original = compute.emit
        def late(out, artifacts):
            original(out, artifacts)
            fail()
        monkeypatch.setattr(compute, 'emit', late)
    else:
        mkdir = Path.mkdir
        def make(path, *a, **k):
            if path.name == 'private':
                fail()
            return mkdir(path, *a, **k)
        monkeypatch.setattr(Path, 'mkdir', make)
    out, private = tmp_path / 'out', tmp_path / 'private'
    with pytest.raises(ValueError, match='manufactured failure'):
        compute.run(tmp_path / 'source', tmp_path / 'method', tmp_path / 'cohort', out, private)
    marker = json.loads((out / 'failure_report.json').read_text())
    assert marker['status'] == 'failed_precondition'
    if mode == 'late_emit':
        assert (out / 'results.json').exists()
        assert json.loads((out / 'results.json').read_text())['status'] == 'ok'


@pytest.mark.parametrize('mode', ['existing', 'source_child', 'source_ancestor', 'overlap', 'dangling', 'parentlink', 'traversal'])
def test_destination_preconditions(tmp_path, mode):
    source = tmp_path / 'source'; source.mkdir()
    output, private = tmp_path / 'out', tmp_path / 'private'
    if mode == 'existing':
        output.mkdir()
    elif mode == 'source_child':
        output = source / 'output'
    elif mode == 'source_ancestor':
        output = tmp_path
    elif mode == 'overlap':
        private = output / 'private'
    elif mode == 'dangling':
        output.symlink_to(tmp_path / 'missing')
    elif mode == 'parentlink':
        output.symlink_to(source, target_is_directory=True); output = output / 'out'
    else:
        output = tmp_path / 'a' / '..' / 'source' / 'out'
    with pytest.raises(ValueError):
        compute.destinations(output, private, [source])


def test_under_solution_guard_does_not_protect_entire_root(tmp_path, monkeypatch):
    code = tmp_path / 'runtime' / 'solution'; code.mkdir(parents=True)
    monkeypatch.setattr(compute, '__file__', str(code / 'compute.py'))
    out, private = compute.destinations(tmp_path / 'out', tmp_path / 'private', [tmp_path / 'data'])
    assert out.name == 'out' and private.name == 'private'


@pytest.mark.parametrize('args', [[], ['--pilot-first-subject'], ['--private-dir', '/evidence/private', '--pilot-first-subject'],
                                 ['--data-dir', '/data/path with spaces', '--output-dir', '/evidence/new-output']])
def test_actual_shell_wrapper_forwards_arguments_without_numerical_execution(args):
    # Docker's source-free /tmp is noexec. Intercept the exec shell builtin in
    # the child rather than launching a PATH stub (or any numerical Python).
    command = 'function exec() { printf "%s\\n" "$@"; }; export -f exec; /bin/bash "$@"'
    env = dict(os.environ, OUTPUT_DIR='/evidence/default-output')
    result = subprocess.run(['/bin/bash', '-c', command, 'wrapper-test', str(SOLUTION / 'solve.sh'), *args], env=env, check=True,
                            capture_output=True, text=True)
    assert result.stdout.splitlines() == ['python3', str(SOLUTION / 'compute.py'), '--output-dir', '/evidence/default-output', *args]


def test_actual_manufactured_runtime_versions():
    compute.check_runtime()
