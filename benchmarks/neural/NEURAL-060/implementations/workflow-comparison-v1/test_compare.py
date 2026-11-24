"""Generated full-cohort controls using the retained protected scorer itself."""
import argparse
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import tempfile
import types
import unittest


HERE = Path(__file__).absolute().parent
spec = importlib.util.spec_from_file_location('workflow_compare', HERE / 'compare.py')
compare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare)
PROGRAM = 'benchmarks/neural/NEURAL-060/implementations/full-central-programme/program'
BOOTSTRAP = {'bytes': 4479, 'sha256': '3715a7fbb504ebe99703421bed0595f2687f5242a192fe419c36cdff1ded53f1'}
MANIFEST = {'bytes': 2492, 'sha256': '2ca0f30669eb7ae0a5f0a5bbbe04b6f950fa18bfb709890e817ad574bd04d140'}


def generated_score(repository, scale=1.):
    root = repository / PROGRAM
    raw = (root / 'bootstrap.py').read_bytes()
    if {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} != BOOTSTRAP:
        raise ValueError('retained scorer bootstrap source changed')
    bootstrap = types.ModuleType('retained_bootstrap')
    exec(compile(raw, str(root / 'bootstrap.py'), 'exec'), bootstrap.__dict__)
    sources = bootstrap.Sources(root, MANIFEST)
    grader = sources.module('grader')
    roster_raw = (repository / 'benchmarks/neural/NEURAL-060/contracts/delivery/REQUIRED_SOURCES.json').read_bytes()
    hierarchy, gold_cases, index = compare.roster(roster_raw), [], {}
    for session, sid in enumerate(hierarchy):
        for case in range(1 + session % 3):
            cid = f'{session:016x}{case:016x}'
            index[cid] = sid
            gold_cases.append({'case_id': cid, 'session_id': sid, 'wheel_speed': [0.] * 50})
    candidates = {}
    for mode in compare.MODES:
        for r, rep in enumerate(compare.REPLICATES):
            for arm in compare.ARMS:
                rows = {}
                for case, session in index.items():
                    varying = 1. + list(hierarchy).index(session) % 3
                    value = 2. if mode == compare.MODES[0] else varying
                    if r == 1:
                        value = varying if mode == compare.MODES[0] else 2.
                    if r == 2:
                        value = 2.
                    rows[case] = [value * scale] * 50
                candidates[(mode, rep, arm)] = rows
    references = {(family, arm): {case: [scale] * 50 for case in index}
                  for family in compare.FAMILIES for arm in compare.ARMS}
    strongest = {(session, arm): 'linear' for session in hierarchy for arm in compare.ARMS}
    result = grader.evaluate(candidates, references, strongest, index,
                             {'schema': 'neural060_gold_v1', 'hierarchy': hierarchy, 'cases': gold_cases})
    # Match the actual serialized producer/consumer boundary.
    return json.loads(json.dumps(result, allow_nan=False)), sources.read_bytes + len(raw) + len(roster_raw), hierarchy


class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.score, cls.source_bytes, cls.hierarchy = generated_score(REPOSITORY)

    def test_actual_protected_scorer_full_panel_and_equal_mouse_arithmetic(self):
        result = compare.compare(self.score, self.hierarchy)
        animals = sorted({row['animal_id'] for row in self.hierarchy.values()})
        varying_by_animal = [sum((1 + session % 3) ** 2 for session, row in enumerate(self.hierarchy.values()) if row['animal_id'] == animal)
                             / sum(row['animal_id'] == animal for row in self.hierarchy.values()) for animal in animals]
        expected = 4 - sum(varying_by_animal) / 13
        pooled_session = 4 - sum((1 + session % 3) ** 2 for session in range(29)) / 29
        self.assertFalse(math.isclose(expected, pooled_session))
        pairs = result['replications']['replicate-01']['frozen_minus_adaptive']
        self.assertAlmostEqual(pairs['overall']['mse'], expected)
        self.assertEqual((len(pairs['animals']), len(pairs['sessions']), len(pairs['labs'])), (13, 29, 7))
        for animal, value in enumerate(varying_by_animal):
            self.assertAlmostEqual(pairs['animals'][animals[animal]]['mse'], 4 - value)
        opposite = result['replications']['replicate-02']['frozen_minus_adaptive']['overall']['mse']
        self.assertAlmostEqual(opposite, -expected)
        self.assertEqual(result['replications']['replicate-03']['frozen_minus_adaptive']['overall'], {'mse': 0., 'mae': 0.})
        self.assertIsNone(result['qualification']['qualified_neural_contribution'])
        self.assertFalse(result['qualification']['causal_or_native_understanding_claim'])

    def test_retained_grader_subnormal_mse_is_not_rejected(self):
        score, _, hierarchy = generated_score(REPOSITORY, scale=1e-162)
        result = compare.compare(score, hierarchy)
        self.assertEqual(set(result['replications']), set(compare.REPLICATES))
        self.assertTrue(any(0 < value['mse'] < 2.2250738585072014e-308
                            for value in score['metrics']['candidate/' + compare.MODES[0] + '/replicate-01/joint']['sessions'].values()))
        changed = copy.deepcopy(score)
        changed['metrics']['reference_selected/joint']['overall']['mse'] = 1e-320
        with self.assertRaisesRegex(ValueError, 'aggregation'):
            compare.compare(changed, hierarchy)

    def test_complete_population_and_primary_required(self):
        variants = []
        changed = copy.deepcopy(self.score); changed['metrics'].pop(next(iter(changed['metrics']))); variants.append(changed)
        changed = copy.deepcopy(self.score); changed['primary'].pop(next(iter(changed['primary']))); variants.append(changed)
        changed = copy.deepcopy(self.score); changed['sessions'] = 28; variants.append(changed)
        changed = copy.deepcopy(self.score); changed['mice'] = 39; variants.append(changed)
        changed = copy.deepcopy(self.score); changed['primary'][compare.MODES[0] + '/replicate-01'] += 1; variants.append(changed)
        for changed in variants:
            with self.subTest(change=changed.keys()), self.assertRaises(ValueError):
                compare.compare(changed, self.hierarchy)

    def test_same_biological_support_in_all_panels(self):
        changed = copy.deepcopy(self.score)
        panel = changed['metrics']['reference_selected/joint']
        panel['animals']['replacement-mouse'] = panel['animals'].pop(next(iter(panel['animals'])))
        with self.assertRaisesRegex(ValueError, 'same original biological'):
            compare.compare(changed, self.hierarchy)
        changed = copy.deepcopy(self.score)
        changed['descriptive_contrasts']['reference/linear']['animal_pairs'].pop(next(iter(changed['descriptive_contrasts']['reference/linear']['animal_pairs'])))
        with self.assertRaisesRegex(ValueError, '13 original animal'):
            compare.compare(changed, self.hierarchy)

    def test_aggregate_and_arm_contrast_mismatch_refused(self):
        changed = copy.deepcopy(self.score)
        changed['metrics']['reference_selected/joint']['overall']['mse'] += 1
        with self.assertRaisesRegex(ValueError, 'aggregation'):
            compare.compare(changed, self.hierarchy)
        changed = copy.deepcopy(self.score)
        changed['descriptive_contrasts']['reference/linear']['nuisance_minus_joint_mse'] = 1
        with self.assertRaisesRegex(ValueError, 'contrast'):
            compare.compare(changed, self.hierarchy)

    def test_no_promotion_or_undeclared_metric(self):
        changed = copy.deepcopy(self.score); changed['reference_competence_qualified'] = True
        with self.assertRaisesRegex(ValueError, 'nonqualification'):
            compare.compare(changed, self.hierarchy)
        changed = copy.deepcopy(self.score); changed['metrics']['reference_selected/joint']['overall']['accuracy'] = .7
        with self.assertRaisesRegex(ValueError, 'MSE/MAE'):
            compare.compare(changed, self.hierarchy)

    def test_invalid_and_extreme_numeric_values(self):
        for value in (True, float('nan'), float('inf'), 'NaN', 'Infinity', '1e999999999', -1):
            changed = copy.deepcopy(self.score)
            changed['metrics']['reference_selected/joint']['overall']['mse'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                compare.compare(changed, self.hierarchy)
        changed = copy.deepcopy(self.score)
        for mode, mse, mae in ((compare.MODES[0], '4E+616', '2E+308'), (compare.MODES[1], '1E+616', '1E+308')):
            key = mode + '/replicate-01'
            for arm in compare.ARMS:
                panel = changed['metrics']['candidate/' + key + '/' + arm]
                panel['overall'] = {'mse': mse, 'mae': mae}
                for level in ('sessions', 'animals', 'labs'):
                    panel[level] = {ident: {'mse': mse, 'mae': mae} for ident in panel[level]}
            changed['primary'][key] = mse
        result = compare.compare(changed, self.hierarchy)['replications']['replicate-01']['frozen_minus_adaptive']['overall']
        self.assertEqual(compare.number(result['mse']), compare.number('3E+616'))
        self.assertEqual(compare.render(compare.number('1E-647')), '1E-647')

    def test_pinned_file_command_and_failures(self):
        raw = json.dumps(self.score, allow_nan=False).encode()
        with tempfile.TemporaryDirectory(dir=SCRATCH) as directory:
            path = Path(directory) / 'SCORE.json'; path.write_bytes(raw)
            identity = hashlib.sha256(raw).hexdigest()
            with contextlib.redirect_stdout(io.StringIO()) as output:
                result = compare.main(['--roster', str(REPOSITORY / 'benchmarks/neural/NEURAL-060/contracts/delivery/REQUIRED_SOURCES.json'), '--score', str(path), '--score-bytes', str(len(raw)), '--score-sha256', identity])
            self.assertEqual(json.loads(output.getvalue()), result)
            self.assertEqual(result['source_score'], {'bytes': len(raw), 'sha256': identity})
            with self.assertRaisesRegex(ValueError, 'identity mismatch'):
                compare.capture(path, len(raw), '0' * 64)
            with self.assertRaisesRegex(ValueError, 'score file'):
                compare.capture(path, len(raw) - 1, identity)
            link = Path(directory) / 'alias.json'; link.symlink_to(path)
            with self.assertRaises(OSError):
                compare.capture(link, len(raw), identity)
            for malformed in (b'{"schema":"a","schema":"b"}', b'{"schema":NaN}'):
                path.write_bytes(malformed)
                with self.assertRaises(ValueError):
                    compare.main(['--roster', str(REPOSITORY / 'benchmarks/neural/NEURAL-060/contracts/delivery/REQUIRED_SOURCES.json'), '--score', str(path), '--score-bytes', str(len(malformed)),
                                  '--score-sha256', hashlib.sha256(malformed).hexdigest()])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True, type=Path)
    parser.add_argument('--scratch', required=True, type=Path)
    args = parser.parse_args()
    REPOSITORY, SCRATCH = args.repository, args.scratch
    if not SCRATCH.is_dir():
        parser.error('--scratch must be an existing owned scratch directory')
    unittest.main(argv=['test_compare.py'], verbosity=2)
