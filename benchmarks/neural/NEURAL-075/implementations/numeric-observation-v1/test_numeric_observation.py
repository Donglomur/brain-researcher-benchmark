"""Generated original-shaped source controls; no authentic inputs or scoring.

Five compressed immutable prototypes are shared, but every one of60 contexts
is actually decoded/admitted and charged independently. All fixed original
1200/1000/50/500/1750 dimensions remain. V=3 is an explicitly invented complete
native width, not a sample/reduction of authentic voxels or capacity evidence.
"""
from dataclasses import replace
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import resource
import signal
import socket
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('neural075_numeric_observation_controls', HERE / 'numeric_observation.py')
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
MEASURE = {'fixture_scope': 'generated original fixed shapes, invented complete native V=3',
           'persistent_fixture_bytes': 0, 'model_calls': 0, 'target_reads': 0, 'scoring_calls': 0}


def npz(values):
    stream = io.BytesIO()
    np.savez_compressed(stream, **values)
    return stream.getvalue()


def make_view(access, case, raw, materials, ids):
    person, arm, phase = case.split('/')
    c = {'protocol': m.PROTOCOL, 'case_id': case, 'person': person, 'arm': arm, 'phase': phase,
         'categories': list(m.CATEGORIES), 'trial_ids': ids[person, phase],
         'design_sha256': 'd' * 64, 'inputs': {'path': 'inputs.npz', **m.pin(raw)},
         'n_units': 1000, 'access_condition': access}
    context = m.encoded(c)
    material = tuple((name, body) for name, body in materials.items()
                     if name.startswith('public/') or access == 'B')
    identity = m.encoded({'schema': 'neural075_input_identity_v1', 'case_id': case, 'access': access,
                         'files': {'case.json': m.pin(context), 'inputs.npz': m.pin(raw),
                                   **{name: m.pin(body) for name, body in material}},
                         'context_pin': m.pin(context)})
    return m.PreparedView(identity, context, raw, material)


def changed(view, *, context=None, inputs=None, materials=None):
    raw_context = view.context if context is None else context
    raw_inputs = view.inputs if inputs is None else inputs
    material = view.materials if materials is None else materials
    c = json.loads(raw_context)
    c['inputs'] = {'path': 'inputs.npz', **m.pin(raw_inputs)}
    raw_context = m.encoded(c)
    identity = json.loads(view.identity)
    identity['context_pin'] = m.pin(raw_context)
    identity['files'] = {'case.json': m.pin(raw_context), 'inputs.npz': m.pin(raw_inputs),
                         **{name: m.pin(body) for name, body in material}}
    return m.PreparedView(m.encoded(identity), raw_context, raw_inputs, material)


def limits():
    # Explicit fictional control capacities, not provider tokens or production defaults.
    return m.Limits(max_captured_bytes=256 * 2**20, max_total_decoded_bytes=1024 * 2**20,
                    max_single_decoded_bytes=32 * 2**20, max_input_scalars=100000000,
                    max_numeric_pages=30000, max_exposure_bytes=3 * 2**30,
                    max_actor_bytes=2 * 2**30, max_collection_bytes=96 * 2**20,
                    max_actions=200000, page_values=4096, read_repetitions=1,
                    draft_repetitions=1, deadline=time.monotonic() + 110)


def forbidden(*args, **kwargs):
    raise AssertionError('No network, provider or subprocess in generated controls')


class NumericObservationControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patches = [patch.object(socket, 'socket', forbidden),
                       patch.object(socket, 'create_connection', forbidden),
                       patch.object(subprocess, 'Popen', forbidden)]
        for item in cls.patches:
            item.start()
        # Real dense arrays, finite values and fixed original dimensions.
        y = (np.arange(1200000, dtype=np.float64).reshape(1200, 1000) % 2048) / 2048
        y[0, 0] = -0.0
        y[0, 1] = 1e-300
        y[-1, -1] = np.nextafter(1.0, 2.0)
        bank = np.arange(50000, dtype=np.float64).reshape(50, 1000) / 50000
        groups = np.repeat(np.arange(150, dtype=np.int64), 8)
        runs = (np.arange(1200) % 24).astype(np.float64) + .5  # No integer recast permitted.
        x = np.arange(3600, dtype=np.float64).reshape(1200, 3) / 128
        perm = (np.arange(1200).reshape(150, 8)[np.roll(np.arange(150), 1)]).reshape(-1)
        cls.base = {'train_y': y, 'bank': bank, 'groups': groups, 'runs': runs}
        cls.queries = {phase: np.arange(m.ROWS[phase] * 3, dtype=np.float64).reshape(-1, 3) / 64
                       for phase in m.PHASES}
        cls.prototypes = {('no_neural', None): npz(cls.base)}
        for arm in ('neural', 'training_permuted'):
            for phase in m.PHASES:
                values = dict(cls.base, train_y=y if arm == 'neural' else y[perm],
                              train_x=x, query_x=cls.queries[phase])
                cls.prototypes[arm, phase] = npz(values)
        cls.materials = {name: (HERE / 'materials' / name).read_bytes() for name in m.MATERIAL_PINS}
        cls.ids = {(person, phase): ['q' + hashlib.sha256(f'{person}/{phase}/{i}'.encode()).hexdigest()[:24]
                                    for i in range(m.ROWS[phase])]
                   for person in m.PEOPLE for phase in m.PHASES}
        views = []
        for access, case in m.CASES:
            _, arm, phase = case.split('/')
            raw = cls.prototypes[arm, None if arm == 'no_neural' else phase]
            views.append(make_view(access, case, raw, cls.materials, cls.ids))
        cls.views = tuple(views)
        cls.pins = tuple(m.pin(v.identity) for v in cls.views)
        cls.limits = limits()
        cls.admitted = m.preflight(cls.views, cls.pins, cls.limits)
        cls.requirements = json.loads(cls.admitted.requirements)['requirements']
        MEASURE.update(unique_compressed_fixture_bytes=sum(map(len, cls.prototypes.values())),
                       complete60_compressed_input_occurrences=sum(len(v.inputs) for v in cls.views),
                       preflight_requirements=cls.requirements)

    @classmethod
    def tearDownClass(cls):
        for item in reversed(cls.patches):
            item.stop()

    def test_complete_original_shapes_preflight_and_lossless_all_first_view_pages(self):
        r = self.requirements
        self.assertEqual(r['input_scalars'], 75144000 + 18600 * (5 * 3))
        self.assertEqual((r['response_rows'], r['response_scalars']), (67500, 3375000))
        expected = dict(self.base, train_x=np.arange(3600, dtype=np.float64).reshape(1200, 3) / 128,
                        query_x=self.queries['imagery'])
        session = m.ObserverSession(self.admitted)
        description = json.loads(session.dispatch(m.encoded({'action': 'describe'})))
        self.assertEqual(description['context'], json.loads(self.views[0].context))
        self.assertFalse(description['visual_only'])
        seen = 0
        for row in description['arrays']:
            name = row['name']
            digest = hashlib.sha256()
            previous_end = 0
            for page in range(row['pages']):
                result = json.loads(session.dispatch(m.encoded({'action': 'numeric_page', 'array': name, 'page': page})))
                self.assertEqual(result['offset'], previous_end)
                self.assertEqual(result['shape'], list(expected[name].shape))
                self.assertEqual(result['dtype'], expected[name].dtype.str)
                values = np.asarray(result['values'], dtype=result['dtype'])
                digest.update(values.tobytes())
                previous_end += values.size
                seen += values.size
                if name == 'train_y' and page == 0:
                    self.assertTrue(np.signbit(values[0]))
                    self.assertEqual(values[1], 1e-300)
                if name == 'train_y' and page == row['pages'] - 1:
                    self.assertEqual(values[-1], np.nextafter(1.0, 2.0))
            self.assertEqual(previous_end, expected[name].size)
            self.assertEqual(digest.hexdigest(), hashlib.sha256(expected[name].tobytes()).hexdigest())
        self.assertEqual(seen, 1252400 + 1700 * 3)
        MEASURE['first_view_all_numeric_values_roundtripped'] = seen
        MEASURE['first_view_actual_exposure_bytes'] = session._exposure_bytes

    def test_full60_observer_outputs_and_exact_A_B_materials(self):
        session = m.ObserverSession(self.admitted)
        scores = [float(i) for i in range(50)]
        scores[0] = -0.0
        for index, (access, case) in enumerate(m.CASES):
            c = json.loads(self.views[index].context)
            if index in (0, 30):
                for name, expected in self.views[index].materials:
                    result = json.loads(session.dispatch(m.encoded({'action': 'material', 'path': name})))
                    self.assertEqual(result['text'].encode('utf8'), expected)
                self.assertEqual(sum(name.startswith('author_code/') for name, _ in self.views[index].materials),
                                 0 if access == 'A' else 4)
            for key in c['trial_ids']:
                session.dispatch(m.encoded({'action': 'draft_row', 'trial_id': key, 'scores': scores}))
            session.dispatch(m.encoded({'action': 'freeze_case'}))
        result = session.finish()
        self.assertEqual(tuple((a, c) for a, c, _ in result.predictions), m.CASES)
        for i, (access, case, body) in enumerate(result.predictions):
            value = json.loads(body)
            c = json.loads(self.views[i].context)
            self.assertEqual(value['trial_ids'], c['trial_ids'])
            self.assertEqual(value['categories'], c['categories'])
            self.assertEqual(value['context_sha256'], m.pin(self.views[i].context)['sha256'])
            self.assertEqual(value['scores'], [scores] * m.ROWS[c['phase']])
            self.assertTrue(np.signbit(value['scores'][-1][0]))
        report = json.loads(result.report)
        self.assertEqual(len(report['contexts']), 60)
        self.assertEqual(report['response_scalars'], 3375000)
        for key in ('observer_execution_attested', 'provider_context_qualified', 'closed_program_receipt',
                    'private_production_grader_compatible', 'targets_read', 'scoring_performed'):
            self.assertIs(report[key], False)
        with self.assertRaisesRegex(ValueError, 'Exactly all60'):
            session.finish()
        MEASURE.update(complete60_prediction_bytes=sum(len(b) for _, _, b in result.predictions),
                       complete60_observer_report_bytes=len(result.report),
                       complete60_actor_bytes=report['actor_bytes'],
                       complete60_exposure_bytes=report['exposure_bytes'])

    def test_late_capacity_failure_does_not_issue_dispatchable_panel(self):
        calls = []
        original = m._decode
        def counted(*args):
            value = original(*args)
            calls.append(True)
            return value
        # Last context makes the complete exposure reservation exceed capacity.
        bad = replace(self.limits, max_exposure_bytes=self.requirements['exposure_bytes'] - 1)
        with patch.object(m, '_decode', counted):
            with self.assertRaisesRegex(ValueError, 'Whole-condition capacity: exposure_bytes'):
                m.preflight(self.views, self.pins, bad)
        self.assertEqual(len(calls), 60)
        with self.assertRaisesRegex(ValueError, 'preflight required'):
            m.ObserverSession(None)

    def test_final60_context_wrong_support_refuses_before_exposure(self):
        c = json.loads(self.views[-1].context)
        c['trial_ids'] = c['trial_ids'][::-1]
        bad = changed(self.views[-1], context=m.encoded(c))
        views = self.views[:-1] + (bad,)
        pins = self.pins[:-1] + (m.pin(bad.identity),)
        with self.assertRaisesRegex(ValueError, 'Matched original query support'):
            m.preflight(views, pins, self.limits)

    def test_expanded_capacity_before_decoder_allocation(self):
        with patch.object(m, '_ARRAYS', side_effect=AssertionError('Decoder must not allocate')):
            with self.assertRaisesRegex(ValueError, 'decoded capacity before allocation'):
                m.preflight(self.views, self.pins, replace(self.limits, max_single_decoded_bytes=2**20))

    def test_no_neural_rejects_added_x_and_source_material_tamper(self):
        index = 2  # A/Subject1/no_neural/imagery
        bad = changed(self.views[index], inputs=self.prototypes['neural', 'imagery'])
        views = self.views[:index] + (bad,) + self.views[index + 1:]
        pins = self.pins[:index] + (m.pin(bad.identity),) + self.pins[index + 1:]
        with self.assertRaisesRegex(ValueError, 'Exact arm members'):
            m.preflight(views, pins, self.limits)
        material = list(self.views[0].materials)
        material[0] = (material[0][0], material[0][1] + b' altered')
        bad = changed(self.views[0], materials=tuple(material))
        with self.assertRaisesRegex(ValueError, 'Exact permitted source material'):
            m.preflight((bad,) + self.views[1:], (m.pin(bad.identity),) + self.pins[1:], self.limits)

    def test_missing_rows_bad_scores_and_unavailable_material_fail_closed(self):
        for request in ({'action': 'freeze_case'},
                        {'action': 'draft_row', 'trial_id': self.ids['Subject1', 'imagery'][0], 'scores': [0] * 49},
                        {'action': 'draft_row', 'trial_id': self.ids['Subject1', 'imagery'][0], 'scores': [False] * 50},
                        {'action': 'material', 'path': 'author_code/code_LICENSE'}):
            session = m.ObserverSession(self.admitted)
            with self.assertRaisesRegex(ValueError, 'no partial collection'):
                session.dispatch(m.encoded(request))
            with self.assertRaisesRegex(ValueError, 'closed'):
                session.dispatch(m.encoded({'action': 'describe'}))
            with self.assertRaisesRegex(ValueError, 'Exactly all60'):
                session.finish()

    def test_distinct_person_width_and_exact_permuted_observation(self):
        # One complete fictional native width differs; no authentic columns are
        # selected, dropped or sampled. Every original fixed axis stays full.
        x = np.arange(1200 * 7, dtype=np.float64).reshape(1200, 7) / 128
        permutation = np.arange(1200).reshape(150, 8)[np.roll(np.arange(150), 1)].reshape(-1)
        permuted_y = self.base['train_y'][permutation]
        prototypes = {}
        for arm in ('neural', 'training_permuted'):
            for phase in m.PHASES:
                query = np.arange(m.ROWS[phase] * 7, dtype=np.float64).reshape(-1, 7) / 64
                prototypes[arm, phase] = npz(dict(self.base, train_x=x, query_x=query,
                    train_y=self.base['train_y'] if arm == 'neural' else permuted_y))
        views = []
        for i, (access, case) in enumerate(m.CASES):
            person, arm, phase = case.split('/')
            views.append(changed(self.views[i], inputs=prototypes[arm, phase])
                         if person == 'Subject1' and arm != 'no_neural' else self.views[i])
        views = tuple(views)
        panel = m.preflight(views, tuple(m.pin(v.identity) for v in views), self.limits)
        requirements = json.loads(panel.requirements)['requirements']
        self.assertEqual(requirements['input_scalars'], 75144000 + 18600 * (7 + 4 * 3))
        session = m.ObserverSession(panel)
        for i in range(4):
            description = json.loads(session.dispatch(m.encoded({'action': 'describe'})))
            arrays = {row['name']: row for row in description['arrays']}
            if i < 2:
                self.assertEqual(arrays['train_x']['shape'], [1200, 7])
                self.assertEqual(arrays['query_x']['shape'][1], 7)
                if i == 0:
                    last = arrays['train_x']['pages'] - 1
                    page = json.loads(session.dispatch(m.encoded({'action': 'numeric_page',
                                                                   'array': 'train_x', 'page': last})))
                    self.assertEqual(page['values'][-1], x[-1, -1])
            else:
                self.assertEqual(set(arrays), set(m.COMMON))
                self.assertEqual(len(description['context']['trial_ids']), 500 if i == 2 else 1750)
            for trial in description['context']['trial_ids']:
                session.dispatch(m.encoded({'action': 'draft_row', 'trial_id': trial, 'scores': [0.0] * 50}))
            session.dispatch(m.encoded({'action': 'freeze_case'}))
        description = json.loads(session.dispatch(m.encoded({'action': 'describe'})))
        self.assertEqual(description['context']['arm'], 'training_permuted')
        for name, expected in [('train_y', permuted_y), ('groups', self.base['groups']),
                               ('runs', self.base['runs']), ('bank', self.base['bank'])]:
            first = json.loads(session.dispatch(m.encoded({'action': 'numeric_page', 'array': name, 'page': 0})))
            values = np.asarray(first['values'], dtype=first['dtype'])
            np.testing.assert_array_equal(values, expected.reshape(-1)[:len(values)])
            self.assertEqual(first['dtype'], expected.dtype.str)
        self.assertNotEqual(permuted_y[0, 0], self.base['train_y'][0, 0])
        self.assertEqual(self.base['groups'][0], 0)
        self.assertEqual(self.base['runs'][0], .5)
        MEASURE.update(heterogeneous_width_input_scalars=requirements['input_scalars'],
                       additional_unique_compressed_fixture_bytes=sum(map(len, prototypes.values())),
                       focused_actor_bytes=session._actor_bytes,
                       focused_exposure_bytes=session._exposure_bytes,
                       focused_prediction_bytes=sum(len(b) for _, _, b in session._frozen))

    def test_page_tail_and_repeat_policy(self):
        session = m.ObserverSession(self.admitted)
        row = next(r for r in self.admitted.layouts[0] if r[0] == 'train_y')
        action = m.encoded({'action': 'numeric_page', 'array': 'train_y', 'page': row[4] - 1})
        value = json.loads(session.dispatch(action))
        self.assertEqual(len(value['values']), 1200000 % self.limits.page_values)
        self.assertEqual(value['values'][-1], np.nextafter(1.0, 2.0))
        with self.assertRaisesRegex(ValueError, 'no partial collection'):
            session.dispatch(action)
        with self.assertRaisesRegex(ValueError, 'Exactly all60'):
            session.finish()


if __name__ == '__main__':
    start = time.monotonic()
    signal.alarm(115)
    result = unittest.main(verbosity=2, exit=False)
    signal.alarm(0)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss = usage.ru_maxrss if sys.platform == 'darwin' else usage.ru_maxrss * 1024
    MEASURE.update(elapsed_seconds=time.monotonic() - start, max_rss_bytes=rss,
                   tests_run=result.result.testsRun, successful=result.result.wasSuccessful())
    print('CONTROL_MEASUREMENTS=' + json.dumps(MEASURE, sort_keys=True))
    raise SystemExit(0 if result.result.wasSuccessful() and rss <= 2**30 else 1)
