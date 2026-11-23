"""Engineering-only endpoint controls. No source data, fits or scientific scores."""
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PROGRAM = ROOT / 'benchmarks/paper/PAPER-FIND-036/implementations/foraging-programme/program'
DEPENDENCIES = Path(os.environ.get('FORAGING_EXISTING_SOURCE_ROOT', str(PROGRAM)))


class ForagingEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        names = ('common', 'prepare', 'support', 'author_replay', 'paper_endpoint')
        prior = {name: sys.modules.pop(name, None) for name in names}
        sys.path[:0] = [str(PROGRAM), str(DEPENDENCIES)]
        try:
            cls.endpoint = importlib.import_module('paper_endpoint')
        finally:
            del sys.path[:2]
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

    @staticmethod
    def pin(value):
        raw = (json.dumps(value) + '\n').encode()
        return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

    def author_fixture(self, bundle):
        """Invented report metadata only; no original arrays or fits exist."""
        sessions, vectors = {}, {}
        for source in bundle['records']:
            sid = source['session_id']
            a, b = (source['source_HW_counts'][name] for name in ('avoidance', 'escape'))
            sessions[sid] = {'source_member': source['source_member'], 'fits': 5,
                             'confusion_counts': [[a, 0], [b, 0]],
                             'class_counts': [a, b], 'rows': a+b,
                             'avoidance_recall': 1., 'escape_recall': 0.,
                             'balanced_accuracy': .5}
            vectors[sid] = {'file': sid+'.f64', 'rows': a+b, 'dtype': '<f8',
                            'bytes': 8*(a+b), 'sha256': '0'*64}
        author_pin = {'bytes': self.endpoint.AUTHOR_BYTES,
                      'sha256': self.endpoint.AUTHOR_SHA256}
        numeric = sum(row['bytes'] for row in vectors.values())
        component = {'schema': 'foraging_source_api_real_branch_v1',
                     'task_id': self.endpoint.TASK, 'source_classifier': author_pin,
                     'runtime_versions': dict(self.endpoint.VERSIONS),
                     'completed_real_fits': 200, 'sessions': sessions,
                     'output_numeric_bytes': numeric, 'equal_session_balanced_accuracy': .5,
                     'unchanged_whole_script_execution': False,
                     'historical_environment_equivalence': False,
                     'source_shuffle_companions_executed': False,
                     'permutation_importance_executed': False,
                     'source_or_custody_qualification_established': False,
                     'paper_reproduced': None, 'paper_win': None, 'improvement_ready': False}
        result = {'schema': 'foraging_source_api_cli_result_v1',
                  'task_id': self.endpoint.TASK, 'status': 'complete_author_api_component_only',
                  'complete_sessions': 40, 'completed_real_fits': 200, 'probabilities': vectors,
                  'author_component': {'file': 'AUTHOR_COMPONENT.json', **self.pin(component)},
                  'prepared': self.pin(bundle), 'author_source': author_pin,
                  'numeric_output_bytes': numeric,
                  'paper_reproduced': None, 'paper_win': None, 'overall_benchmark_ready': False}
        return component, result

    def compare(self, inputs, component, replay_result):
        return self.endpoint.compare_author_replay(
            *inputs, component, replay_result, self.pin(inputs[1]), self.pin(component))

    def test_source_api_comparison_preserves_three_comparators_and_limits(self):
        inputs = self.fixture()
        component, replay_result = self.author_fixture(inputs[1])
        before = copy.deepcopy((inputs, component, replay_result))
        report = self.compare(inputs, component, replay_result)
        self.assertEqual((inputs, component, replay_result), before)
        self.assertEqual(report['operator_bnb_reconstruction'], .75)
        self.assertEqual(report['author_replay'], .5)
        self.assertEqual(report['published'], .7271)
        self.assertEqual(report['methods']['A']['difference_from_author_api_replay'], .5)
        self.assertEqual(report['methods']['A']['difference_from_operator_bnb'], .25)
        self.assertEqual(report['methods']['B']['difference_from_author_api_replay'], .25)
        self.assertFalse(report['author_replay_scope']['probability_vectors_reopened'])
        self.assertFalse(report['author_calibration_established'])
        self.assertFalse(report['improvement_ready'])
        self.assertIsNone(report['paper_win'])
        self.assertIsNone(report['uncertainty']['population_interval'])

    def test_source_api_chain_roster_recipe_and_qualification_tampering_refused(self):
        mutations = ('prepared', 'component_pin', 'source', 'missing_session', 'member',
                     'fits', 'complete_fits', 'runtime', 'BA', 'mean', 'counts',
                     'missing_vector', 'vector_rows', 'vector_bytes', 'numeric_total',
                     'whole_script', 'custody', 'reproduced', 'ready')
        for mutation in mutations:
            inputs = self.fixture()
            component, replay_result = self.author_fixture(inputs[1])
            sid = inputs[1]['records'][0]['session_id']
            row, vector = component['sessions'][sid], replay_result['probabilities'][sid]
            if mutation == 'prepared': replay_result['prepared']['sha256'] = 'f'*64
            if mutation == 'source': replay_result['author_source']['sha256'] = 'f'*64
            if mutation == 'missing_session': component['sessions'].pop(sid)
            if mutation == 'member': row['source_member'] = 'another_session.mat'
            if mutation == 'fits': row['fits'] = 4
            if mutation == 'complete_fits': component['completed_real_fits'] = 199
            if mutation == 'runtime': component['runtime_versions']['scikit_learn'] = 'unknown'
            if mutation == 'BA': row['balanced_accuracy'] = .6
            if mutation == 'mean': component['equal_session_balanced_accuracy'] = .7
            if mutation == 'counts': row['confusion_counts'][0][0] -= 1
            if mutation == 'missing_vector': replay_result['probabilities'].pop(sid)
            if mutation == 'vector_rows': vector['rows'] += 1
            if mutation == 'vector_bytes': vector['bytes'] += 8
            if mutation == 'numeric_total': replay_result['numeric_output_bytes'] -= 8
            if mutation == 'whole_script': component['unchanged_whole_script_execution'] = True
            if mutation == 'custody': component['source_or_custody_qualification_established'] = True
            if mutation == 'reproduced': component['paper_reproduced'] = True
            if mutation == 'ready': replay_result['overall_benchmark_ready'] = True
            # Exercise content validation beyond the report hash itself.
            replay_result['author_component'].update(self.pin(component))
            if mutation == 'component_pin': replay_result['author_component']['sha256'] = 'f'*64
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.compare(inputs, component, replay_result)

    def test_source_api_cli_binds_reports_without_opening_vector_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result, bundle, collection = self.fixture()
            component, replay_result = self.author_fixture(bundle)
            def write(name, obj):
                path = root/name
                path.write_bytes((json.dumps(obj)+'\n').encode())
                return path, self.pin(obj)
            bp, bd = write('prepared.json', bundle)
            collection['prepared'] = bd
            cp, cd = write('collection.json', collection)
            result['collection'] = cd
            rp, rd = write('result.json', result)
            ap, ad = write('AUTHOR_COMPONENT.json', component)
            xp, xd = write('COMPONENT_RESULT.json', replay_result)
            args = ['--result', str(rp), '--result-sha256', rd['sha256'],
                    '--prepared', str(bp), '--prepared-sha256', bd['sha256'],
                    '--collection', str(cp), '--collection-sha256', cd['sha256'],
                    '--author-component', str(ap), '--author-component-sha256', ad['sha256'],
                    '--author-result', str(xp), '--author-result-sha256', xd['sha256'],
                    '--output', str(root/'comparison.json')]
            self.endpoint.main(args)
            report = json.loads((root/'comparison.json').read_bytes())
            self.assertEqual(report['author_replay'], .5)
            self.assertEqual(report['inputs']['author_component'], ad)
            self.assertEqual(report['inputs']['author_result'], xd)
            self.assertEqual(list(root.glob('*.f64')), [])
            with self.assertRaisesRegex(ValueError, 'both expected digests together'):
                incomplete = args.copy()
                position = incomplete.index('--author-result-sha256')
                del incomplete[position:position+2]
                self.endpoint.main(incomplete)


if __name__ == '__main__':
    unittest.main()
