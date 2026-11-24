"""Generated software controls; no authentic input or participant execution."""
import copy
import importlib.util
import math
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

PATH = Path(__file__).resolve().parents[1] / 'viewer.py'
spec = importlib.util.spec_from_file_location('neural058_viewer', PATH)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def fixture(role='J'):
    required, sessions = [], []
    for i in range(29):
        sid, animal, query = f'{i + 1:032x}', f'{100 + i % 13:032x}', f'{1000 + i:032x}'
        row = {'session': sid, 'animal': animal, 'session_ordinal': i, 'animal_ordinal': i % 13}
        required.append(dict(row))
        anatomy = {'regions': ['VISp', 'area<&>'], 'locations': [[0.0, 1.0, 2.0], [3.0, 0.0, 5.0]],
                   'location_missing': [[False, False, False], [False, True, False]]}
        window = {'query': query, 'context': [1.0, None, 0.5], 'support': [0.0, 1.0],
                  'times': [0.0, 0.12345678901234566, 0.9999999999999999], **copy.deepcopy(anatomy)}
        if role == 'J':
            window.update(spike_times=[0.0, 0.0, 0.25, 0.25, 0.75], spike_units=[0, 0, 1, 1, 0],
                          neural_domain=[[0.0, 0.4], [0.6, 1.0]])
        sessions.append({**row, **anatomy, 'windows': [window], 'fold': None, 'role': role,
                         'source_view': {'path': '/operator/source-path-SECRET', 'pin': {'sha256': 'SECRET'}}})
    # Animal ordinals are independent of an alphabetic sort of random aliases.
    return sessions, required


def viewer(role='J', **limits):
    sessions, required = fixture(role)
    return v.EvaluationViewer(sessions, required, role=role,
                              **dict({'page_rows': 2, 'max_cells': 20000,
                                      'max_actions': 2000, 'max_svg_bytes': 2000000}, **limits))


def text(svg):
    root = ET.fromstring(svg)
    return [node.text for node in root.findall('{http://www.w3.org/2000/svg}text')]


class ViewerControls(unittest.TestCase):
    def test_complete_delivery_requires_every_page_without_double_count(self):
        x = viewer()
        first = x.catalog()[0]
        action = {k: first[k] for k in ('session', 'query', 'table')} | {'page': 0}
        x.view(action); x.view(action)
        self.assertEqual(x.coverage()['returned_pages'], 1)
        self.assertFalse(x.coverage()['complete_delivery'])
        for item in x.catalog():
            for page in range(item['pages']):
                x.view({k: item[k] for k in ('session', 'query', 'table')} | {'page': page})
        self.assertTrue(x.coverage()['complete_delivery'])
        self.assertEqual((x.coverage()['sessions'], x.coverage()['animals'], x.coverage()['timestamps']), (29, 13, 87))

    def test_exact_events_duplicates_zero_and_final_page_are_preserved(self):
        x = viewer()
        rows = [r for r in x.catalog() if r['table'] == 'spikes'][0]
        rendered = []
        for page in range(rows['pages']):
            rendered.extend(text(x.view({k: rows[k] for k in ('session', 'query', 'table')} | {'page': page}))[2:])
        self.assertEqual(rendered, ['0 | 0.0 | 0', '1 | 0.0 | 0', '2 | 0.25 | 1', '3 | 0.25 | 1', '4 | 0.75 | 0'])

    def test_navigation_retains_same_public_animal_grouping_and_order(self):
        x = viewer()
        _, required = fixture()
        expected = {row['session']: row for row in required}
        for row in x.catalog():
            self.assertEqual({key: row[key] for key in expected[row['session']]}, expected[row['session']])
        self.assertEqual(len({row['animal'] for row in x.catalog()}), 13)

    def test_float_round_trip_and_missing_masks(self):
        x = viewer()
        pages = []
        for item in x.catalog()[:3]:
            for page in range(item['pages']):
                pages.extend(text(x.view({k: item[k] for k in ('session', 'query', 'table')} | {'page': page})))
        self.assertIn('1 | 0.12345678901234566', pages)
        self.assertIn('2 | 0.9999999999999999', pages)
        self.assertTrue(any('MISSING' in row for row in pages))
        self.assertTrue(any('3.0 | 0.0 | 5.0 | False | True | False' in row for row in pages))

    def test_context_and_neural_have_identical_common_pages(self):
        c, j = viewer('C'), viewer('J')
        for item in c.catalog():
            for page in range(item['pages']):
                action = {k: item[k] for k in ('session', 'query', 'table')} | {'page': page}
                self.assertEqual(c.view(action), j.view(action))
        self.assertFalse(any(row['table'] in ('spikes', 'domain') for row in c.catalog()))

    def test_empty_events_is_a_visible_complete_page(self):
        sessions, required = fixture()
        sessions[0]['windows'][0]['spike_times'] = []
        sessions[0]['windows'][0]['spike_units'] = []
        x = v.EvaluationViewer(sessions, required, role='J', page_rows=2, max_cells=20000, max_actions=1000, max_svg_bytes=2000000)
        action = {'session': required[0]['session'], 'query': sessions[0]['windows'][0]['query'], 'table': 'spikes', 'page': 0}
        self.assertIn('EMPTY: zero original events; complete support retained', text(x.view(action)))

    def test_no_source_paths_or_unescaped_markup_returned(self):
        x = viewer()
        for item in x.catalog():
            action = {k: item[k] for k in ('session', 'query', 'table')} | {'page': 0}
            svg = x.view(action)
            self.assertNotIn('SECRET', svg)
            self.assertNotIn('/operator', svg)
            self.assertNotIn('<script', svg)
            ET.fromstring(svg)
        self.assertNotIn('SECRET', repr(x.catalog()))

    def test_target_or_join_fields_are_refused(self):
        for name in ('labels', 'velocity', 'speed', 'source_trial', 'source_onset'):
            sessions, required = fixture()
            sessions[0]['windows'][0][name] = [999.0]
            with self.assertRaises(ValueError):
                v.EvaluationViewer(sessions, required, role='J', page_rows=2, max_cells=20000, max_actions=100, max_svg_bytes=100000)

    def test_no_surviving_session_population(self):
        sessions, required = fixture()
        with self.assertRaisesRegex(ValueError, '29'):
            v.EvaluationViewer(sessions[:-1], required[:-1], role='J', page_rows=2, max_cells=20000, max_actions=100, max_svg_bytes=100000)
        sessions[0]['animal'] = sessions[1]['animal']
        with self.assertRaisesRegex(ValueError, 'roster'):
            v.EvaluationViewer(sessions, required, role='J', page_rows=2, max_cells=20000, max_actions=100, max_svg_bytes=100000)

    def test_role_training_or_mutated_anatomy_refused(self):
        for mutation in ('training', 'anatomy', 'neural_C'):
            sessions, required = fixture()
            if mutation == 'training': sessions[0]['fold'] = 0
            if mutation == 'anatomy': sessions[0]['windows'][0]['locations'][0][0] = 8.0
            with self.assertRaises(ValueError):
                v.EvaluationViewer(sessions, required, role='C' if mutation == 'neural_C' else 'J',
                                   page_rows=2, max_cells=20000, max_actions=100, max_svg_bytes=100000)

    def test_budget_and_unknown_actions_fail_without_partial_coverage(self):
        x = viewer(max_actions=2, max_svg_bytes=1)
        first = x.catalog()[0]
        action = {k: first[k] for k in ('session', 'query', 'table')} | {'page': 0}
        with self.assertRaisesRegex(ValueError, 'byte budget'): x.view(action)
        with self.assertRaisesRegex(ValueError, 'typed page'): x.view({'exec': 'read targets'})
        with self.assertRaisesRegex(ValueError, 'action budget'): x.view(action)
        self.assertEqual(x.coverage()['returned_pages'], 0)
        self.assertEqual(x.coverage()['svg_bytes'], 0)
        with self.assertRaises(ValueError): viewer(max_cells=1)

    def test_complete_two_head_response_without_scoring_or_clipping(self):
        x = viewer()
        sessions, _ = fixture()
        response = {s['session']: {w['query']: [[-2.0, -3.0] for _ in w['times']] for w in s['windows']} for s in sessions}
        self.assertEqual(x.validate_response(response), response)
        for mode in ('session', 'window', 'timestamp', 'head', 'nan'):
            bad = copy.deepcopy(response); sid = next(iter(bad)); query = next(iter(bad[sid]))
            if mode == 'session': del bad[sid]
            if mode == 'window': del bad[sid][query]
            if mode == 'timestamp': bad[sid][query].pop()
            if mode == 'head': bad[sid][query][0].pop()
            if mode == 'nan': bad[sid][query][0][0] = math.nan
            with self.assertRaises(ValueError): x.validate_response(bad)

    def test_response_bytes_refuse_duplicates_constants_and_limits(self):
        self.assertEqual(v.parse_response(b'{"a": [[1.0, 2.0]]}', max_bytes=50), {'a': [[1.0, 2.0]]})
        for raw in (b'{"a":1,"a":2}', b'{"a":{"q":1,"q":2}}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.assertRaises(ValueError): v.parse_response(raw, max_bytes=100)
        with self.assertRaises(ValueError): v.parse_response(b'{}', max_bytes=1)

    def test_snapshot_does_not_change_when_host_inputs_mutate(self):
        sessions, required = fixture()
        x = v.EvaluationViewer(sessions, required, role='J', page_rows=2, max_cells=20000, max_actions=100, max_svg_bytes=100000)
        action = {'session': required[0]['session'], 'query': sessions[0]['windows'][0]['query'], 'table': 'timestamps', 'page': 0}
        before = x.view(action)
        sessions[0]['windows'][0]['times'][0] = 0.9
        self.assertEqual(x.view(action), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
