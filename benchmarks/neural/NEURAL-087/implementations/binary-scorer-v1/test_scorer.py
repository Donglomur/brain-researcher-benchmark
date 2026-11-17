"""Generated software controls only; no authentic data or model execution."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contract import COUNTS, VIEWS, binary_count, node_role
from io_utils import decode
from score import load_bound_roster
from scorer import average_precision, grade, log_loss


def submission(rows, probabilities):
    return {'schema_version': 1, 'predictions': [
        {'edge_id': r['edge_id'], 'probability': p}
        for r, p in zip(rows, probabilities, strict=True)]}


class ArithmeticTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {'edge_id': 'e0', 'pre_id': 1, 'post_id': 2, 'projection': 'V1->V1'},
            {'edge_id': 'e1', 'pre_id': 1, 'post_id': 3, 'projection': 'V1->V1'},
            {'edge_id': 'e2', 'pre_id': 4, 'post_id': 5, 'projection': 'HVA->HVA'},
        ]
        self.target = {'schema_version': 1, 'targets': [
            {'edge_id': r['edge_id'], 'connected': y}
            for r, y in zip(self.rows, [1, 0, 1], strict=True)]}
        self.views = {VIEWS[0]: submission(self.rows, [.5, .5, .5]),
                      VIEWS[1]: submission(self.rows, [.8, .25, .9])}
        self.calls = 0

    def private(self):
        self.calls += 1
        return self.target

    def test_neuron_macro_loss_and_brier_hand_calculation(self):
        result = grade(self.rows, self.views, self.private)
        expected = ((-math.log(.8) - math.log(.75)) / 2 - math.log(.9)) / 2
        self.assertAlmostEqual(result['primary']['value'], expected, places=14)
        pair_mean = (-math.log(.8) - math.log(.75) - math.log(.9)) / 3
        self.assertNotAlmostEqual(result['primary']['value'], pair_mean, places=8)
        self.assertAlmostEqual(result['views'][VIEWS[1]]['equal_pre_brier'],
                               ((.2**2 + .25**2) / 2 + .1**2) / 2)
        self.assertEqual(self.calls, 1)
        json.dumps(result, allow_nan=False)

    def test_anatomy_weakening_cannot_change_primary(self):
        expected = grade(self.rows, self.views, self.private)['primary']
        self.views[VIEWS[0]] = submission(self.rows, [0, 1, 0])
        self.assertEqual(grade(self.rows, self.views, self.private)['primary'], expected)

    def test_negative_information_contrast_is_preserved(self):
        self.views[VIEWS[0]] = submission(self.rows, [1, 0, 1])
        result = grade(self.rows, self.views, self.private)
        self.assertLess(result['anatomy_minus_joint_diagnostic']['value'], 0)

    def test_complete_ties_ap_and_degenerate_targets(self):
        self.assertAlmostEqual(average_precision([1, 0, 1], [.9, .9, .1])['value'], 7 / 12)
        self.assertEqual(average_precision([1, 0, 1], [.9, .9, .1]),
                         average_precision([0, 1, 1], [.9, .9, .1]))
        self.assertEqual(average_precision([1, 0, 0], [.4] * 3)['value'], 1 / 3)
        self.assertEqual(average_precision([1, 1], [.8, .2])['value'], 1)
        self.assertEqual(average_precision([0, 0], [.8, .2])['status'],
                         'undefined_no_positive_targets')

    def test_endpoint_probabilities_not_clipped(self):
        self.assertEqual(log_loss(0, 0), 0)
        self.assertEqual(log_loss(1, 1), 0)
        self.assertTrue(math.isinf(log_loss(1, 0)))
        self.assertTrue(math.isinf(log_loss(0, 1)))
        self.views = {v: submission(self.rows, [0, 1, 0]) for v in VIEWS}
        result = grade(self.rows, self.views, self.private)
        self.assertEqual(result['primary']['status'], 'positive_infinity')
        self.assertEqual(result['anatomy_minus_joint_diagnostic']['status'],
                         'undefined_infinity_difference')
        json.dumps(result, allow_nan=False)

    def test_each_invalid_paired_submission_precedes_private_access(self):
        mutations = [
            lambda x: x.pop(VIEWS[0]),
            lambda x: x[VIEWS[0]]['predictions'].pop(),
            lambda x: x[VIEWS[1]]['predictions'].pop(),
            lambda x: x[VIEWS[1]]['predictions'].__setitem__(1, x[VIEWS[1]]['predictions'][0]),
            lambda x: x[VIEWS[1]]['predictions'][0].update(edge_id='e999'),
            lambda x: x[VIEWS[1]]['predictions'][0].update(probability=True),
            lambda x: x[VIEWS[1]]['predictions'][0].update(probability=math.nan),
            lambda x: x[VIEWS[1]]['predictions'][0].update(probability=math.inf),
            lambda x: x[VIEWS[1]]['predictions'][0].update(probability=-.01),
            lambda x: x[VIEWS[1]]['predictions'][0].update(probability=1.01),
            lambda x: x[VIEWS[1]]['predictions'][0].update(connected=1),
            lambda x: x[VIEWS[1]].update(schema_version=True),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                bad = copy.deepcopy(self.views)
                mutate(bad)
                with self.assertRaises(ValueError):
                    grade(self.rows, bad, self.private)
                self.assertEqual(self.calls, 0)

    def test_prediction_order_independent_private_order_exact(self):
        expected = grade(self.rows, self.views, self.private)
        self.views[VIEWS[1]]['predictions'].reverse()
        self.assertEqual(grade(self.rows, self.views, self.private), expected)
        self.target['targets'].reverse()
        with self.assertRaises(ValueError):
            grade(self.rows, self.views, self.private)

    def test_duplicate_pairs_rejected_and_counts_not_booleans(self):
        self.rows[1]['post_id'] = self.rows[0]['post_id']
        with self.assertRaises(ValueError):
            grade(self.rows, self.views, self.private)
        self.assertEqual(self.calls, 0)
        self.assertEqual([binary_count(n) for n in (0, 1, 5)], [0, 1, 1])
        with self.assertRaises(ValueError):
            binary_count(True)

    def test_strict_json(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.assertRaises(ValueError):
                decode(raw)


class OperatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Explicitly generated identities, not the authentic historical roster.
        query_nodes = [n for n in range(1, 5000) if node_role(n) == 2]
        pres, posts = query_nodes[:21], query_nodes[21:340]
        cls.rows = [{'edge_id': f'e{i}', 'pre_id': pre, 'post_id': post, 'projection': 'V1->V1'}
                    for i, (pre, post) in enumerate((a, b) for a in pres for b in posts)]
        cls.rows = cls.rows[:COUNTS['query']]

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.roster_pin = self.write('roster.json', self.rows)
        targets = {'schema_version': 1, 'targets': [
            {'edge_id': r['edge_id'], 'connected': i % 2}
            for i, r in enumerate(self.rows)]}
        target_pin = self.write('targets.json', targets)
        self.binding = {'schema': 'neural087_prepared_binding_v1', 'task_id': 'NEURAL-087',
                        'counts': COUNTS, 'query_roster': self.roster_pin, 'query_targets': target_pin}
        self.binding_sha = self.write('binding.json', self.binding)['sha256']
        for name in ('anatomy', 'joint'):
            self.write(name + '.json', submission(self.rows, [.5] * len(self.rows)))

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        raw = (json.dumps(value, separators=(',', ':')) + '\n').encode()
        (self.root / name).write_bytes(raw)
        return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

    def invoke(self, target='targets.json', overrides=None, forbid_body_reads=False):
        entrypoint = str(Path(__file__).with_name('score.py'))
        argv = [sys.executable, '-B', entrypoint, '--binding-sha256', self.binding_sha]
        names = dict(binding='binding.json', roster='roster.json', targets=target,
                     anatomy='anatomy.json', joint='joint.json', output='scores.json')
        names.update(overrides or {})
        for flag, name in names.items():
            argv.extend(['--' + flag, str(self.root / name)])
        if forbid_body_reads:
            # Execute the real CLI while independently trapping ANY fixture-body
            # open, not only calls through the scorer's private callback.
            bootstrap = '''
import pathlib, runpy, sys
entrypoint, fixture_root, *arguments = sys.argv[1:]
fixture_root = pathlib.Path(fixture_root)
def audit(event, arguments):
    if event == 'open' and isinstance(arguments[0], (str, bytes)):
        path = pathlib.Path(arguments[0])
        if path.is_relative_to(fixture_root):
            raise RuntimeError('BODY_READ_BEFORE_ROLE_PREFLIGHT: ' + str(path))
sys.addaudithook(audit)
sys.path.insert(0, str(pathlib.Path(entrypoint).parent))
sys.argv = [entrypoint, *arguments]
runpy.run_path(entrypoint, run_name='__main__')
'''
            argv = [sys.executable, '-I', '-B', '-c', bootstrap,
                    entrypoint, str(self.root), *argv[3:]]
        return subprocess.run(argv, capture_output=True, text=True, timeout=15)

    def test_complete_generated_operator_cli(self):
        self.assertEqual(len(self.rows), 6691)
        run = self.invoke()
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads((self.root / 'scores.json').read_text())
        self.assertAlmostEqual(result['primary']['value'], math.log(2), places=14)
        self.assertEqual(result['support']['presynaptic_neurons'], 21)
        self.assertEqual(result['private_loader_calls'], 1)
        self.assertEqual(result['operator_binding_sha256'], self.binding_sha)
        self.assertFalse(result['research_qualified'])

    def test_invalid_joint_does_not_open_absent_target(self):
        self.write('joint.json', submission(self.rows[:-1], [.5] * (len(self.rows) - 1)))
        run = self.invoke('target-does-not-exist.json')
        self.assertEqual(run.returncode, 2, run.stderr)
        result = json.loads((self.root / 'scores.json').read_text())
        self.assertEqual(result['status'], 'invalid_submission')
        self.assertEqual(result['private_loader_calls'], 0)

    def test_wrong_binding_and_altered_roster_fail(self):
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            load_bound_roster(self.root / 'binding.json', '0' * 64, self.root / 'roster.json')
        with (self.root / 'roster.json').open('ab') as handle:
            handle.write(b' ')
        with self.assertRaisesRegex(ValueError, 'committed input'):
            load_bound_roster(self.root / 'binding.json', self.binding_sha, self.root / 'roster.json')

    def test_rehashed_truncated_roster_is_not_complete_panel(self):
        self.binding['query_roster'] = self.write('roster.json', self.rows[:-1])
        self.binding_sha = self.write('binding.json', self.binding)['sha256']
        with self.assertRaisesRegex(ValueError, '6691-pair'):
            load_bound_roster(self.root / 'binding.json', self.binding_sha, self.root / 'roster.json')

    def test_wrong_endpoint_role_even_when_rehashed(self):
        rows = copy.deepcopy(self.rows)
        rows[0]['post_id'] = next(n for n in range(1, 100) if node_role(n) != 2)
        self.binding['query_roster'] = self.write('roster.json', rows)
        self.binding_sha = self.write('binding.json', self.binding)['sha256']
        with self.assertRaisesRegex(ValueError, 'query partition'):
            load_bound_roster(self.root / 'binding.json', self.binding_sha, self.root / 'roster.json')

    def test_target_tamper_produces_no_output(self):
        with (self.root / 'targets.json').open('ab') as handle:
            handle.write(b' ')
        run = self.invoke()
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse((self.root / 'scores.json').exists())

    def test_nonuniform_weight_extension_cannot_be_ignored(self):
        self.binding['sampling_weights'] = [2] * len(self.rows)
        self.binding_sha = self.write('binding.json', self.binding)['sha256']
        with self.assertRaisesRegex(ValueError, 'alternative weighting'):
            load_bound_roster(self.root / 'binding.json', self.binding_sha, self.root / 'roster.json')

    def test_cli_target_aliases_refused_before_any_body_read(self):
        for role in ('binding', 'roster', 'anatomy', 'joint'):
            for kind in ('samepath', 'relative', 'symlink', 'hardlink'):
                with self.subTest(role=role, kind=kind):
                    alias = self.root / f'{role}-{kind}.json'
                    name = 'targets.json'
                    if kind == 'relative':
                        name = f'../{self.root.name}/targets.json'
                    elif kind == 'symlink':
                        alias.symlink_to(self.root / 'targets.json')
                        name = alias.name
                    elif kind == 'hardlink':
                        os.link(self.root / 'targets.json', alias)
                        name = alias.name
                    before = (self.root / 'targets.json').read_bytes()
                    try:
                        run = self.invoke(overrides={role: name}, forbid_body_reads=True)
                        self.assertNotEqual(run.returncode, 0)
                        self.assertIn(f'Input role alias: targets and {role}', run.stderr)
                        self.assertNotIn('BODY_READ_BEFORE_ROLE_PREFLIGHT', run.stderr)
                        self.assertFalse((self.root / 'scores.json').exists())
                        self.assertEqual((self.root / 'targets.json').read_bytes(), before)
                    finally:
                        if kind in ('symlink', 'hardlink'):
                            alias.unlink()

    def test_cli_body_read_probe_detects_unaliased_binding_open(self):
        run = self.invoke(forbid_body_reads=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('BODY_READ_BEFORE_ROLE_PREFLIGHT', run.stderr)
        self.assertIn('binding.json', run.stderr)
        self.assertFalse((self.root / 'scores.json').exists())

    def test_cli_output_aliases_refused_before_any_body_read(self):
        for role in ('binding', 'roster', 'anatomy', 'joint', 'targets'):
            source = self.root / f'{role}.json'
            for kind in ('samepath', 'symlink', 'hardlink'):
                with self.subTest(role=role, kind=kind):
                    alias = self.root / f'output-{role}-{kind}.json'
                    name = source.name
                    if kind == 'symlink':
                        alias.symlink_to(source)
                        name = alias.name
                    elif kind == 'hardlink':
                        os.link(source, alias)
                        name = alias.name
                    before = source.read_bytes()
                    try:
                        run = self.invoke(overrides={'output': name}, forbid_body_reads=True)
                        self.assertNotEqual(run.returncode, 0)
                        self.assertIn(f'Output role alias: output and {role}', run.stderr)
                        self.assertNotIn('BODY_READ_BEFORE_ROLE_PREFLIGHT', run.stderr)
                        self.assertEqual(source.read_bytes(), before)
                    finally:
                        if kind in ('symlink', 'hardlink'):
                            alias.unlink()


if __name__ == '__main__':
    unittest.main()
