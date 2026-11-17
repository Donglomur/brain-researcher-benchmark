"""Generated full-support controls; no original numerical artifacts or models."""
import copy
import io
import importlib.machinery
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import broker
import collect

WRITTEN = 0
original_publish = broker.publish


def published(path, body):
    global WRITTEN
    result = original_publish(path, body)
    WRITTEN += len(body)
    if WRITTEN > 32 * 1024**2:
        raise AssertionError('Generated fixture write allowance')
    return result


broker.publish = collect.publish = published


class CountJournal:
    def __init__(self, stream):
        self.stream = stream
    def write(self, body):
        global WRITTEN
        count = self.stream.write(body)
        WRITTEN += count
        return count
    def __getattr__(self, name):
        return getattr(self.stream, name)


def method():
    return broker.encode({'schema_version': 1, 'method_id': 'generated', 'description': 'Scripted probability control',
                          'training_policy': 'No training performed', 'limitations': 'No AI capability result'})


def prefix(features, episode, current):
    result = []
    for r in range(1, current + 1):
        row = dict(zip(features.BEHAVIOR, (10 * r, None if r % 2 else 2, 3, 4, 5, 6)))
        row.update(dict(zip(features.ERP, (101, 202, 303, 404, 505, 606, 707))))
        row.update(round=r, trial_global=(episode - 1) * 5 + r, episode=episode, partner=episode + 500, choice=r % 2)
        result.append(row)
    return result


def fixtures(features):
    training_people = [str(i) for i in range(1, 27)]
    development_people = [str(i) for i in range(101, 108)]
    train = {'feature_names': {k: list(v) for k, v in features.ARMS.items()}, 'participant_ids': training_people,
             'cv_fold_by_id': {p: i % 3 for i, p in enumerate(training_people)}, 'rows': []}
    for i, person in enumerate(training_people):
        for j in range(126 if i < 4 else 125):
            episode, current = j // 4 + 1, j % 4 + 1
            train['rows'].append({'participant': person, 'case_id': f'{person}:{episode}:{current}',
                                 'features': features.vector(prefix(features, episode, current), 'all_erp'), 'target': (current + 1) % 2})
    development = {'participant_ids': development_people, 'coverage': {}, 'cases': []}
    for i, person in enumerate(development_people):
        n = 117 if i < 4 else 116
        development['coverage'][person] = {'structural': 144, 'eligible': n, 'missing_current_ERP': 144 - n}
        for j in range(n):
            episode, current = j // 4 + 1, j % 4 + 1
            development['cases'].append({'request': {'participant': person, 'case_id': f'{person}:{episode}:{current}',
                                        'prefix': prefix(features, episode, current)}, 'target': (current + 1) % 2,
                                        'source_current': i * 180 + (episode - 1) * 5 + current,
                                        'source_target': i * 180 + (episode - 1) * 5 + current + 1})
    panel = {'cases': [{k: r['request'][k] for k in ('participant', 'case_id')} for r in development['cases']]}
    return train, development, panel


def response(frame, probability=0.5):
    return broker.encode({**{k: frame[k] for k in ('session_id', 'nonce', 'participant', 'view', 'case_id')}, 'probability': probability})


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        identity, cls.features, cls.contribution, pins, _ = broker.configuration()
        cls.train, cls.development, cls.panel = fixtures(cls.features)
        cls.identity = {'source': identity, 'inputs': {'fixture': True}, 'public_panel': broker.pin(broker.encode(cls.panel))}
        cls.study = broker.Study(cls.train, cls.development, cls.panel, cls.features, cls.contribution.schedule_counts, cls.identity)
        cls.temp = tempfile.TemporaryDirectory(prefix='neural005-generated-')
        cls.root = Path(cls.temp.name).resolve()
        cls.sessions = cls.root / 'all-sessions'
        cls.sessions.mkdir()
        for view in broker.VIEWS:
            for person in cls.study.people:
                session = cls.new_session(cls.study, person, view, cls.sessions / (view + '-' + person))
                while session.index < len(cls.study.queries[person]):
                    session.commit(response(session.offer()))
                session.finish()

    @staticmethod
    def new_session(study, person, view, directory):
        session = broker.Session(study, person, view, method(), directory)
        session.journal = CountJournal(session.journal)
        return session

    @classmethod
    def tearDownClass(cls):
        print(json.dumps({'python': sys.version, 'generated_fixture_write_bytes': WRITTEN, 'original_numerical_body_reads': 0,
                          'model_or_provider_calls': 0, 'native_executions': 0}))
        cls.temp.cleanup()

    def test_complete_training_and_nonprefix_erp_projection(self):
        for view, width in zip(broker.VIEWS, (50, 53, 57)):
            training = self.study.training(view)
            self.assertEqual(len(training['rows']), 3254)
            self.assertEqual(len(training['participant_ids']), 26)
            self.assertTrue(all(len(r['features']) == width for r in training['rows']))
        self.assertEqual(self.study.training('prestimulus')['rows'][0]['features'][-3:], [303, 505, 707])
        self.assertNotEqual(self.study.training('prestimulus')['rows'][0]['features'],
                            self.study.training('all_erp')['rows'][0]['features'][:53])
        values = self.features.vector(prefix(self.features, 1, 3), 'history')
        self.assertEqual(values[13:17], [20.0, 10, 30, 10])

    def test_all_seven_current_erp_values_required_before_history_mask(self):
        development = copy.deepcopy(self.development)
        development['cases'][0]['request']['prefix'][-1]['P3b_offer'] = None
        with self.assertRaisesRegex(ValueError, 'seven-ERP'):
            broker.Study(self.train, development, self.panel, self.features, self.contribution.schedule_counts, self.identity)

    def test_missing_case_or_training_person_cannot_reduce_support(self):
        development = copy.deepcopy(self.development)
        development['cases'].pop()
        with self.assertRaises(ValueError):
            broker.Study(self.train, development, self.panel, self.features, self.contribution.schedule_counts, self.identity)
        train = copy.deepcopy(self.train)
        train['rows'][0]['participant'] = self.study.people[0]
        with self.assertRaises(ValueError):
            broker.Study(train, self.development, self.panel, self.features, self.contribution.schedule_counts, self.identity)

    def test_one_current_observation_and_delayed_choice_feedback(self):
        session = self.new_session(self.study, '101', 'all_erp', self.root / 'sequential')
        try:
            training = session.training_message()
            self.assertEqual(len(training['training']['rows']), 3254)
            first = session.offer()
            self.assertEqual(set(first), {'schema', 'session_id', 'nonce', 'participant', 'view', 'case_id', 'index', 'feature_names', 'features'})
            self.assertEqual(first['case_id'], '101:1:1')
            with self.assertRaisesRegex(ValueError, 'Commit'):
                session.offer()
            with self.assertRaises(ValueError):
                session.training_message()
            first['features'][0] = 999  # Caller mutation cannot alter internal observation.
            session.commit(response(first))
            second = session.offer()
            self.assertEqual(second['case_id'], '101:1:2')
            self.assertEqual(second['features'][second['feature_names'].index('current_reject')], self.development['cases'][0]['target'])
            self.assertNotEqual(first['nonce'], second['nonce'])
        finally:
            session.abort()

    def test_durable_commit_failure_prevents_advance_and_completion(self):
        session = self.new_session(self.study, '101', 'history', self.root / 'fsync-failure')
        try:
            frame = session.offer()
            with patch.object(broker.os, 'fsync', side_effect=OSError('generated flush failure')):
                with self.assertRaises(OSError):
                    session.commit(response(frame))
            self.assertEqual(session.index, 0)
            with self.assertRaises(ValueError):
                session.offer()
            with self.assertRaises(ValueError):
                session.finish()
            self.assertFalse((session.directory / 'COMPLETE.json').exists())
        finally:
            session.abort()

    def test_future_answer_noninterference_and_later_lawful_feedback(self):
        development = copy.deepcopy(self.development)
        development['cases'][0]['target'] = 1
        for row in development['cases']:
            request = row['request']
            if request['participant'] == '101' and request['prefix'][-1]['episode'] == 1 and len(request['prefix']) >= 2:
                request['prefix'][1]['choice'] = 1
        changed = broker.Study(self.train, development, self.panel, self.features, self.contribution.schedule_counts, self.identity)
        for view in broker.VIEWS:
            a = self.new_session(self.study, '101', view, self.root / ('future-original-' + view))
            b = self.new_session(changed, '101', view, self.root / ('future-changed-' + view))
            try:
                first_a, first_b = a.offer(), b.offer()
                for field in ('participant', 'view', 'case_id', 'index', 'feature_names', 'features'):
                    self.assertEqual(first_a[field], first_b[field])
                with self.assertRaises(ValueError):
                    b.offer()
                a.commit(response(first_a))
                b.commit(response(first_b))
                second_a, second_b = a.offer(), b.offer()
                index = second_a['feature_names'].index('current_reject')
                self.assertEqual(second_a['features'][index], 0)
                self.assertEqual(second_b['features'][index], 1)
            finally:
                a.abort()
                b.abort()

    def test_bad_current_answers_fail_without_retry(self):
        for i, variant in enumerate(('bool', 'nan', 'nonce', 'view', 'extra', 'duplicate')):
            session = self.new_session(self.study, '101', 'history', self.root / ('bad-' + variant))
            try:
                frame = session.offer()
                value = broker.decode(response(frame))
                if variant == 'bool': value['probability'] = True
                elif variant == 'nan': value['probability'] = float('nan')
                elif variant == 'nonce': value['nonce'] = 'f' * 32
                elif variant == 'view': value['view'] = 'all_erp'
                elif variant == 'extra': value['target'] = 1
                body = json.dumps(value).encode()
                if variant == 'duplicate': body = body[:-1] + b',"probability":0.2}'
                with self.assertRaises(ValueError):
                    session.commit(body)
                with self.assertRaises(ValueError):
                    session.offer()
            finally:
                session.abort()

    def test_complete_21_sessions_and_all_three_original_scorer_panels(self):
        output = self.root / 'collected'
        report = collect.collect(self.study, self.sessions, output)
        self.assertEqual((report['protocols'], report['predictions'], report['queries_per_view']), (21, 2448, 816))
        self.assertFalse(report['no_tools_enforced'])
        self.assertFalse(report['external_participant_reset_verified'])
        rows_by_view = {}
        for view in broker.VIEWS:
            submission = broker.decode(broker.read(output / (view + '.probabilities.json'), 100000))
            self.assertEqual(set(submission), {'schema_version', 'probabilities'})
            self.assertEqual(len(submission['probabilities']), 816)
            self.assertTrue(all(set(r) == {'participant', 'case_id', 'probability'} for r in submission['probabilities']))
            rows_by_view[view] = {r['case_id']: r['probability'] for r in submission['probabilities']}
        metrics = broker.dependency('generated_original_probability_metrics', 'registered-runtime/probability_metrics.py')
        rows = [{'participant': r['request']['participant'], 'case_id': r['request']['case_id'], 'target': r['target'],
                 'probabilities': {view: rows_by_view[view if view != 'candidate' else 'all_erp'][r['request']['case_id']]
                                   for view in metrics.ARMS}}
                for r in self.development['cases']]
        scored = metrics.calculate(rows)
        for view in broker.VIEWS:
            self.assertAlmostEqual(scored['equal_participant_arms'][view]['log_loss'], math.log(2), places=13)

    def test_verified_source_bytes_execute_without_cached_loader(self):
        with patch.object(importlib.machinery.SourceFileLoader, 'get_code', side_effect=AssertionError('Cached loader forbidden')):
            features = broker.dependency('verified_features_control', 'pinned-source-preparation-v1/features.py')
        self.assertEqual(len(features.ARMS['all_erp']), 57)
        path = self.root / 'generated-dependency.py'
        raw = b'VALUE = 1\n'
        published(path, raw)
        self.assertEqual(broker.execute_source('generated_source', path, broker.pin(raw)).VALUE, 1)
        with self.assertRaises(ValueError):
            broker.execute_source('changed_source', path, broker.pin(b'VALUE = 2\n'))

    def test_incomplete_campaign_refused_before_any_collection_output(self):
        original = self.sessions / 'history-101'
        moved = self.root / 'temporarily-removed-session'
        original.rename(moved)
        try:
            output = self.root / 'must-not-publish'
            with self.assertRaises(ValueError):
                collect.collect(self.study, self.sessions, output)
            self.assertFalse(output.exists())
        finally:
            moved.rename(original)

    def test_changed_observation_refused_even_with_resealed_hash_chain(self):
        global WRITTEN
        path = self.root / 'tampered-session'
        original = self.sessions / 'prestimulus-101'
        path.mkdir()
        for file in original.iterdir():
            body = file.read_bytes()
            published(path / file.name, body)
        complete = broker.decode((path / 'COMPLETE.json').read_bytes())
        records = [broker.decode(line) for line in (path / 'commits.jsonl').read_bytes().splitlines()]
        records[0]['observation']['sha256'] = '0' * 64
        previous, lines = complete['start'], []
        for record in records:
            record['previous'] = previous
            line = broker.encode(record)
            lines.append(line)
            previous = broker.pin(line)
        journal = b''.join(lines)
        complete.update(journal=broker.pin(journal), last_commit=previous)
        for name, body in (('commits.jsonl', journal), ('COMPLETE.json', broker.encode(complete))):
            (path / name).chmod(0o600)
            (path / name).write_bytes(body)
            WRITTEN += len(body)
        with self.assertRaisesRegex(ValueError, 'permitted numeric observation'):
            collect.session_rows(self.study, path, '101', 'prestimulus')

    def test_actual_main_streams_one_complete_person(self):
        global WRITTEN
        # Exercise the CLI loop without replacing fixed authentic input pins in production.
        output = self.root / 'main-session'
        method_path = self.root / 'method.json'
        published(method_path, method())
        emitted = []
        class Client:
            def write(self, body):
                emitted.append(broker.decode(body))
                return len(body)
            def flush(self): pass
            def readline(self, cap):
                self.last = emitted[-1]
                return response(self.last)
        client = Client()
        with patch.object(broker, 'load_study', return_value=self.study), \
             patch.object(broker.sys, 'stdin', types.SimpleNamespace(buffer=client)), \
             patch.object(broker.sys, 'stdout', types.SimpleNamespace(buffer=client)):
            broker.main(['--train', '/generated/no-input', '--development-private', '/generated/no-target',
                         '--method', str(method_path), '--output', str(output), '--participant', '107', '--view', 'prestimulus'])
        WRITTEN += (output / 'commits.jsonl').stat().st_size
        self.assertEqual(emitted[0]['schema'], 'neural005_training_observation_v1')
        self.assertEqual(sum(r.get('schema') == 'neural005_numeric_observation_v1' for r in emitted), 116)
        self.assertEqual(emitted[-1]['status'], 'complete')
        rows, _, _, _ = collect.session_rows(self.study, output, '107', 'prestimulus')
        self.assertEqual(len(rows), 116)


if __name__ == '__main__':
    unittest.main(verbosity=2)
