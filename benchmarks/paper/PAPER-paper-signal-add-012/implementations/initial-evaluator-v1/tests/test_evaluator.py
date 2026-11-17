# SPDX-License-Identifier: GPL-3.0-only
"""Bounded generated controls; no empirical reproduction evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import unittest
import tempfile
import contextlib

class Approx:
    def __init__(self, expected): self.expected = expected
    def __eq__(self, actual): return bool(np.allclose(actual, self.expected, atol=1e-10, rtol=1e-10))

@contextlib.contextmanager
def expect_value_error():
    try:
        yield
    except ValueError:
        return
    raise AssertionError('ValueError was not raised')

SOURCE = Path(__file__).resolve().parents[1] / 'evaluator.py'
spec = importlib.util.spec_from_file_location('isd_evaluator', SOURCE)
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def test_independent_analytic_cases():
    # Derived independently from source worker: strict > excludes threshold .50.
    complete = np.full((3, 3), .5); np.fill_diagonal(complete, 1)
    r = e.isd_from_fc(complete, complete)
    assert r['integration'] == Approx(.49)
    assert r['segregation'] == Approx(.735)  # Retained self-loops.
    assert r['isd'] == Approx(-.245)
    assert r['multilevel_efficiency'][48] == 1
    assert r['multilevel_efficiency'][49] == 0
    assert r['multilevel_clustering'][-1] == 0
    identity = e.isd_from_fc(np.eye(3), np.eye(3))
    assert (identity['integration'], identity['segregation'], identity['isd']) == (0, 0, 0)
    chain = np.array([[1, .5, 0], [.5, 1, .5], [0, .5, 1]])
    r = e.isd_from_fc(chain, chain)
    assert r['integration'] == Approx(49 / 120)
    assert r['segregation'] == Approx(1519 / 1800)
    assert r['isd'] == Approx(-98 / 225)
    disconnected = np.eye(4); disconnected[:3, :3] = complete
    r = e.isd_from_fc(disconnected, disconnected)
    assert r['integration'] == Approx(.245)
    assert r['segregation'] == Approx(.55125)


def test_preprocessing_roles_not_swappable():
    full = np.ones((3, 3)); identity = np.eye(3)
    a, b = e.isd_from_fc(full, identity), e.isd_from_fc(identity, full)
    assert a['isd'] == Approx(.99)
    assert b['isd'] == Approx(-1.485)


def bfs_reference(a):
    # Independent integer BFS, no scipy path code.
    total = 0
    for start in range(len(a)):
        distances = {start: 0}; todo = [start]
        while todo:
            u = todo.pop(0)
            for v in range(len(a)):
                if a[u, v] and v not in distances:
                    distances[v] = distances[u] + 1; todo.append(v)
        total += sum(1 / d for d in distances.values() if d)
    return total / (len(a) * (len(a) - 1))


def test_independent_graph_reference():
    rng = np.random.default_rng(991)
    for n in (2, 3, 7):
        for _ in range(4):
            a = rng.random((n, n)) > .6; a |= a.T
            assert e.binary_global_efficiency(a) == Approx(bfs_reference(a))


def test_phase_null_preserves_full_spectrum_and_pair_relation(n):
    a = np.random.default_rng(77).normal(size=(n, 4)); b = 2 * a + 3
    sa, sb = e.phase_randomized_pair(a, b, 44)
    assert not np.allclose(sa, a)
    np.testing.assert_allclose(np.abs(np.fft.rfft(sa, axis=0)), np.abs(np.fft.rfft(a, axis=0)), atol=1e-12)
    np.testing.assert_allclose(sb, 2 * sa + 3, atol=1e-12)
    np.testing.assert_array_equal(sa, e.phase_randomized_pair(a, b, 44)[0])


def test_pair_interval_uses_participant_differences():
    r = e.paired_effect([10, 20, 30], [11, 22, 33])
    assert r['mean_difference_after_minus_before'] == 2
    assert r['standard_error'] == Approx(1 / np.sqrt(3))
    assert r['ci95'] == Approx([-.484137711719546, 4.484137711719546])
    assert e.paired_effect([1, 2], [4, 5])['ci95'] == [3, 3]


def test_undefined_timeseries_rejected(bad):
    with expect_value_error(): e.correlation_matrix(bad)


def fixture_manifest(tmp_path):
    rng = np.random.default_rng(41)
    manifest = dict(schema_version=1, task_id=e.TASK_ID, cohort='Dataset-3', engineering_control=True,
        participant_ids=['p1', 'p2'], roster_source='generated control; not real participants',
        contrast={'before': 'baseline', 'after': 'deep'}, tr_seconds=2.0, n_timepoints=12,
        n_rois=3, length_policy='require_equal_no_truncation', motion_policy='report_all_no_exclusion',
        normalization_provenance='generated engineering arrays', surrogate_count=2, surrogate_seed=8, recordings=[])
    for p in manifest['participant_ids']:
        for c in ('baseline', 'deep'):
            a = rng.normal(size=(12, 3)); b = a - a.mean(axis=1, keepdims=True)
            path = tmp_path / f'{p}_{c}.npz'
            np.savez(path, no_gsr=a, gsr=b, no_gsr_sample_ids=np.arange(12), gsr_sample_ids=np.arange(12),
                     no_gsr_roi_ids=['a', 'b', 'c'], gsr_roi_ids=['a', 'b', 'c'])
            manifest['recordings'].append(dict(participant_id=p, condition=c, path=path.name,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(), tr_seconds=2.0,
                mean_framewise_displacement_mm=.1))
    return manifest


def test_cli_whole_path_and_permutation_invariance(tmp_path):
    m = fixture_manifest(tmp_path)
    path, out = tmp_path / 'manifest.json', tmp_path / 'report.json'
    path.write_text(json.dumps(m))
    subprocess.run([sys.executable, str(SOURCE), str(path), '--output', str(out)], check=True)
    r = json.loads(out.read_text())
    assert r['status'] == 'engineering_control_only' and r['scientifically_qualified'] is False
    assert r['contrasts']['isd']['n_participants'] == 2
    assert len(r['scientific_holds']) >= 8
    m['recordings'].reverse()
    assert e.evaluate_manifest(m, tmp_path)['contrasts'] == r['contrasts']


def test_admission_rejects_scientific_shortcuts(tmp_path, mutation):
    m = fixture_manifest(tmp_path)
    if mutation == 'drop': m['recordings'].pop()
    if mutation == 'duplicate': m['recordings'].append(copy.deepcopy(m['recordings'][0]))
    if mutation == 'sha': m['recordings'][0]['sha256'] = '0' * 64
    if mutation == 'tr': m['recordings'][0]['tr_seconds'] = 3
    if mutation == 'roster': m['participant_ids'].append('missing')
    if mutation == 'scientific': m['engineering_control'] = False
    if mutation == 'dataset4': m['cohort'] = 'Dataset-4-main'
    if mutation == 'length': m['length_policy'] = 'truncate_shortest'
    if mutation == 'nulls': m['surrogate_count'] = 0
    with expect_value_error(): e.evaluate_manifest(m, tmp_path)


def test_pair_binding_fail_closed(tmp_path, kind):
    m = fixture_manifest(tmp_path); rec = m['recordings'][0]; path = tmp_path / rec['path']
    with np.load(path) as z: arrays = {key: z[key] for key in z.files}
    if kind == 'sample': arrays['gsr_sample_ids'] = arrays['gsr_sample_ids'][::-1]
    if kind == 'roi': arrays['gsr_roi_ids'] = arrays['gsr_roi_ids'][::-1]
    if kind == 'constant': arrays['gsr'][:, 0] = 0
    if kind == 'shape': arrays['gsr'] = arrays['gsr'][:-1]
    if kind == 'cross_record_roi':
        arrays['gsr_roi_ids'] = np.array(['d', 'e', 'f']); arrays['no_gsr_roi_ids'] = arrays['gsr_roi_ids']
    np.savez(path, **arrays); rec['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    with expect_value_error(): e.evaluate_manifest(m, tmp_path)


class EngineeringControls(unittest.TestCase):
    def test_analytic_cases(self): test_independent_analytic_cases()
    def test_preprocessing_roles(self): test_preprocessing_roles_not_swappable()
    def test_graph_reference(self): test_independent_graph_reference()
    def test_phase_surrogates(self):
        for n in (15, 16):
            with self.subTest(n=n): test_phase_null_preserves_full_spectrum_and_pair_relation(n)
    def test_pair_interval(self): test_pair_interval_uses_participant_differences()
    def test_correlation_overflow_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'overflow'):
            e.correlation_matrix(np.arange(12).reshape(4, 3) * 1e200)
        with self.assertRaisesRegex(ValueError, 'overflow'):
            e.correlation_matrix(np.full((4, 3), 1e308))
    def test_undefined_arrays(self):
        for bad in (np.ones((5, 3)), np.array([[1, 2], [3, np.nan]])):
            test_undefined_timeseries_rejected(bad)
    def test_cli_and_permutation(self):
        with tempfile.TemporaryDirectory() as tmp: test_cli_whole_path_and_permutation_invariance(Path(tmp))
    def test_admission_failures(self):
        for mutation in ('drop','duplicate','sha','tr','roster','scientific','dataset4','length','nulls'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                test_admission_rejects_scientific_shortcuts(Path(tmp), mutation)
    def test_identity_failures(self):
        for kind in ('sample','roi','constant','shape','cross_record_roi'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                test_pair_binding_fail_closed(Path(tmp), kind)

if __name__ == '__main__':
    unittest.main()
