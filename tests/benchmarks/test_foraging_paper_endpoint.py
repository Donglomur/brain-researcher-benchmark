"""Engineering-only endpoint controls. No source data, fits or scientific scores."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PROGRAM = ROOT / 'benchmarks/paper/PAPER-FIND-036/implementations/foraging-programme/program'


class ForagingEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        names = ('common', 'prepare', 'support', 'paper_endpoint')
        prior = {name: sys.modules.pop(name, None) for name in names}
        sys.path.insert(0, str(PROGRAM))
        try:
            cls.endpoint = importlib.import_module('paper_endpoint')
        finally:
            sys.path.remove(str(PROGRAM))
            for name, module in prior.items():
                sys.modules.pop(name, None)
                if module is not None:
                    sys.modules[name] = module

    def fixture(self):
        e = self.endpoint
        records, panels, native = [], {m: {} for m in e.METHODS}, {}
        for i in range(40):
            member = f'EventClassificationData_4C/#engineering-{i:02}_PL_eventClassificationData.mat'
            sid = hashlib.sha256(member.encode()).hexdigest()[:24]
            # Vary session sizes to distinguish equal-session from row weighting.
            n = 10 if i < 20 else 20
            folds = []
            for f in range(1, 6):
                test = [j for j in range(n) if j % 5 == f - 1]
                train = [j for j in range(n) if j not in test]
                folds.append({'fold': f, 'train_positions0': train, 'test_positions0': test,
                              'train_order0': train[::-1], 'query_order0': test[::-1]})
            r = {'session_id': sid, 'source_session_token': Path(member).name.removesuffix('_eventClassificationData.mat'),
                 'source_member': member, 'source_R': n * 2, 'rows': n, 'features': 40,
                 'unit_blocks': 1, 'native_supported': True, 'nested3_supported': True,
                 'prepared': dict.fromkeys(('X.npy', 'y.npy', 'source_rows.npy', 'fold_ids.npy')),
                 'folds': folds, 'source_HW_counts': {'avoidance': n // 2, 'escape': n // 2},
                 'window_seconds': [-1, 1], 'bin_seconds': 0.05, 'clip': [-5, 5],
                 'native_fold_seed': 622, 'upstream_whole_session_normalized': True,
                 'private_row_maps_candidate_visible': False}
            records.append(r)
            count = n // 2
            correct = count if i < 20 else count // 2
            for method in panels:
                k = correct if method in ('bnb', 'B') else count
                metric = {'confusion_counts': [[k, count-k], [count-k, k]],
                          'class_counts': [count, count], 'rows': n,
                          'balanced_accuracy': k/count, 'avoidance_recall': k/count, 'escape_recall': k/count}
                panels[method][sid] = metric
            native[sid] = [copy.deepcopy(panels['bnb'][sid])]
        source = {'bytes': 1, 'sha256': 'a' * 64}
        bundle = {'schema': 'foraging_full40_prepared_v1', 'task_id': e.TASK,
                  'records': records, 'complete_native_support': True, 'complete_nested3_support': True,
                  'archive': dict(e.ARCHIVE), 'source': source,
                  'archive_inventory': [{'name': r['source_member'], 'disposition': 'full_original_classification_MAT'} for r in records]}
        result = {'schema': 'foraging_full40_results_v1', 'task_id': e.TASK, 'source': source,
                  'sessions': 40, 'outer_folds': 200, 'producer_phases': 1320,
                  'released_features_transductive': True, 'causal_or_new_animal_claim': False,
                  'hidden_label_improvement': {m: {'sessions': panel, 'equal_session': {
                      'balanced_accuracy': sum(r['balanced_accuracy'] for r in panel.values()) / 40}}
                      for m, panel in panels.items()},
                  'native_real_and_separate_seeded_control': {'operator': {
                      'sessions': native, 'real': {'balanced_accuracy': 0.75}}},
                  # A bad fidelity score must not affect the scientific endpoint.
                  'native_reproduction': {'A': {'primary_equal_session_real_probability_MAE': 99}}}
        contexts = e.phases(records, 4096)
        collection = {'schema': 'foraging_collection_v1', 'task_id': e.TASK, 'source': source,
                      'all1320closed': True, 'private_grade_called': False, 'model_cap_bytes': 4096,
                      'contexts': contexts, 'phases': [{'context': c} for c in contexts]}
        return result, bundle, collection

    def test_complete_pooled_equal_session_endpoint_and_separate_comparators(self):
        inputs = self.fixture()
        before = copy.deepcopy(inputs)
        score = self.endpoint.score_endpoint(*inputs)
        self.assertEqual(inputs, before)
        self.assertEqual(score['operator_bnb_reconstruction'], .75)
        self.assertEqual(score['methods']['A']['difference_from_operator_bnb'], .25)
        self.assertAlmostEqual(score['methods']['A']['difference_from_published'], 1-.7271)
        self.assertTrue(score['operator_bnb_outside_rounding_interval'])
        self.assertIsNone(score['author_replay'])
        self.assertFalse(score['author_calibration_established'])
        self.assertFalse(score['improvement_ready'])
        self.assertIsNone(score['paper_win'])
        self.assertIsNone(score['uncertainty']['population_interval'])

    def test_missing_and_replaced_sessions_are_not_complete_panels(self):
        for mutation in ('missing', 'replacement', 'archive', 'phase'):
            result, bundle, collection = self.fixture()
            if mutation in ('missing', 'replacement'):
                panel = result['hidden_label_improvement']['A']['sessions']
                value = panel.pop(next(iter(panel)))
                if mutation == 'replacement':
                    panel['f' * 24] = value
            elif mutation == 'archive':
                bundle['archive_inventory'][0]['name'] = 'unknown.mat'
            else:
                collection['phases'].pop()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.endpoint.score_endpoint(result, bundle, collection)

    def test_metric_and_source_recipe_tampering_rejected(self):
        for mutation in ('BA', 'counts', 'row_weight', 'native', 'seed', 'window', 'order', 'fold', 'identity'):
            result, bundle, collection = self.fixture()
            r = bundle['records'][0]
            panel = result['hidden_label_improvement']['A']
            row = panel['sessions'][r['session_id']]
            if mutation == 'BA': row['balanced_accuracy'] = .99
            if mutation == 'counts': row['class_counts'] = [4, 6]
            if mutation == 'row_weight': result['hidden_label_improvement']['bnb']['equal_session']['balanced_accuracy'] = 2/3
            if mutation == 'native': result['native_real_and_separate_seeded_control']['operator']['sessions'][r['session_id']][0]['balanced_accuracy'] = .8
            if mutation == 'seed': r['native_fold_seed'] = 42
            if mutation == 'window': r['window_seconds'] = [-1, 0]
            if mutation == 'order': r['private_row_maps_candidate_visible'] = True
            if mutation == 'fold': r['folds'][0]['test_positions0'] = [0]
            if mutation == 'identity': r['source_session_token'] = '#substitute_PL'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.endpoint.score_endpoint(result, bundle, collection)

    def test_rat_join_is_complete_and_only_descriptive(self):
        inputs = self.fixture()
        mapping = {'schema': 'foraging_authenticated_five_animal_mapping_v1',
                   'independently_authenticated': True, 'source_rows_are_not_animals': True,
                   'sessions': {r['session_id']: f'rat{i % 5}' for i, r in enumerate(inputs[1]['records'])}}
        report = self.endpoint.score_endpoint(*inputs, mapping)
        self.assertTrue(report['methods']['A']['rat_descriptive_stability']['available'])
        self.assertIsNone(report['methods']['A']['rat_descriptive_stability']['population_confidence_interval'])
        mapping['sessions'].pop(next(iter(mapping['sessions'])))
        with self.assertRaises(ValueError): self.endpoint.score_endpoint(*inputs, mapping)

    def test_cli_binds_chain_and_never_reads_array_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result, bundle, collection = self.fixture()
            def write(name, obj):
                raw = (json.dumps(obj) + '\n').encode()
                p = root / name
                p.write_bytes(raw)
                return p, {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            bp, bd = write('prepared.json', bundle)
            collection['prepared'] = bd
            cp, cd = write('collection.json', collection)
            result['collection'] = cd
            rp, rd = write('result.json', result)
            args = ['--result', str(rp), '--result-sha256', rd['sha256'],
                    '--prepared', str(bp), '--prepared-sha256', bd['sha256'],
                    '--collection', str(cp), '--collection-sha256', cd['sha256'],
                    '--output', str(root / 'summary.json')]
            self.endpoint.main(args)
            self.assertEqual(json.loads((root / 'summary.json').read_text())['operator_bnb_reconstruction'], .75)
            # None of fixture's supposed arrays exist; summary uses counts only.
            with self.assertRaises(FileExistsError): self.endpoint.main(args)
            collection['prepared']['sha256'] = '0' * 64
            cp, cd = write('collection.json', collection)
            args[args.index('--collection-sha256')+1] = cd['sha256']
            with self.assertRaises(ValueError): self.endpoint.main(args)

    def test_json_duplicate_keys_and_changed_digest_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'receipt.json'
            raw = b'{"x":1,"x":2}'
            path.write_bytes(raw)
            with self.assertRaises(ValueError):
                self.endpoint.read_pinned_json(path, hashlib.sha256(raw).hexdigest())
            with self.assertRaises(ValueError): self.endpoint.read_pinned_json(path, '0' * 64)


if __name__ == '__main__':
    unittest.main()
