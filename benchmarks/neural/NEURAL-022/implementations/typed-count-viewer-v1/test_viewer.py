"""Generated full-support controls; no authentic signals, private targets or model."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--repository', type=Path, default=HERE.parents[4])
ARGS, REMAINING = parser.parse_known_args()
TASK = ARGS.repository / 'benchmarks/neural/NEURAL-022'
spec = importlib.util.spec_from_file_location('neural022_typed_viewer_tested', HERE / 'viewer.py')
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)
INSTRUCTIONS = (TASK / 'implementations/numerical-observation-v1/INSTRUCTIONS.md').read_bytes()
assert hashlib.sha256(INSTRUCTIONS).hexdigest() == viewer.INSTRUCTION_SHA256
CANDIDATE_BODY = (TASK / 'implementations/artifact-grading/private/vendor/candidate.py').read_bytes()
assert hashlib.sha256(CANDIDATE_BODY).hexdigest() == '55ad617d0b9f9ee208ba6df9684133ab489e8de2749591e277dc09e98bbd8e54'
candidate = types.ModuleType('neural022_original_public_validator')
exec(compile(CANDIDATE_BODY, '<pinned original public validator>', 'exec'), candidate.__dict__)


def panel_value():
    training = []
    for i in range(141):
        training.append({'id': f'{i+1000:024x}', 'direction': 45*(i % 8),
                         'counts': [[10000*i + 100*b + u for u in range(65)] for b in range(6)],
                         'velocity': [i/100., -i/200.]})
    queries = []
    for i in range(92):
        queries.append({'id': f'{i:024x}', 'direction': 45*(i % 8),
                        'mode': 'passive' if i < 40 else 'active',
                        'counts': [[10000*i + 100*b + u for u in range(65)] for b in range(6)]})
    return {'schema': 'neural022_numerical_observation_v1', 'task_id': 'NEURAL-022',
            'condition': 'direct_numerical_full_panel_v1', 'instructions': INSTRUCTIONS.decode(),
            'original_public_scientific_contract': 'Generated scientific excerpt, not authentic metadata.',
            'representation': copy.deepcopy(viewer.REPRESENTATION), 'training': training, 'queries': queries}


def export_value(raw):
    descriptor = {'bytes': 1, 'sha256': 'a'*64}
    return {'schema': 'neural022_numerical_export_v1', 'source': viewer.PREDECESSOR,
            'condition': 'direct_numerical_full_panel_v1', 'packet': descriptor,
            'packet_producer': viewer.PRODUCER,
            'public_inputs': {k: descriptor for k in viewer.PUBLIC_CAPS}, 'observation': viewer.pin(raw),
            'training_rows': 141, 'query_rows': 92, 'count_values': 90870, 'training_velocity_values': 282,
            'provider_delivery_qualified': False, 'authenticity_requires_external_packet_custody': True}


def request(session, value):
    return viewer.strict(session.apply(viewer.encoded(value)))


def cells(svg):
    root = ET.fromstring(svg)
    return {(int(n.attrib['data-bin']), int(n.attrib['data-unit'])): int(n.text)
            for n in root.iter() if 'data-bin' in n.attrib}


class ViewerControls(unittest.TestCase):
    def setUp(self):
        self.panel = panel_value()
        self.raw = viewer.encoded(self.panel)
        self.manifest = viewer.encoded(export_value(self.raw))
        self.identity = viewer.pin(self.manifest)
        self.session = viewer.Session(self.raw, self.manifest, self.identity['sha256'])

    def test_all_233_full_views_preserve_every_count_and_calibration(self):
        for split, key in (('training', 'training'), ('query', 'queries')):
            for i, row in enumerate(self.panel[key]):
                result = request(self.session, {'action': 'view', 'split': split, 'index': i,
                                                'units': [0, 65], 'bins': [0, 6]})
                self.assertTrue(result['ok'])
                svg = result['result']['svg']
                self.assertEqual(cells(svg), {(b, u): row['counts'][b][u] for b in range(6) for u in range(65)})
                self.assertEqual('Calibration velocity' in svg, split == 'training')
                if split == 'training':
                    self.assertIn(repr(row['velocity']), svg)
                self.assertIn(row['id'], svg)
        self.assertEqual(len(self.session.receipt()['views']), 233)
        self.assertLess(self.session.receipt()['output_bytes'], 12*1024*1024)

    def test_crops_are_exact_half_open_unit_and_bin_coordinates(self):
        result = request(self.session, {'action': 'view', 'split': 'query', 'index': 91,
                                        'units': [63, 65], 'bins': [5, 6]})
        self.assertEqual(cells(result['result']['svg']), {(5, u): self.panel['queries'][91]['counts'][5][u]
                                                        for u in [63, 64]})
        self.assertGreaterEqual(int(ET.fromstring(result['result']['svg']).attrib['width']), 1000)

    def test_max_int64_counts_and_float_labels_are_not_rounded_or_clipped(self):
        row = copy.deepcopy(self.panel['training'][0])
        row['counts'] = [[2**63-1]*65 for _ in range(6)]
        row['velocity'] = [1.7976931348623157e308, -1.7976931348623157e308]
        svg = viewer.grid(row, 'training', 0, [0, 65], [0, 6])
        self.assertEqual(set(cells(svg).values()), {2**63-1})
        self.assertIn(repr(row['velocity']), svg)
        self.assertLess(len(svg.encode()), viewer.SVG_CAP)
        for value in self.panel['training']:
            value['counts'] = copy.deepcopy(row['counts'])
            value['velocity'] = list(row['velocity'])
        for value in self.panel['queries']:
            value['counts'] = copy.deepcopy(row['counts'])
        raw = viewer.encoded(self.panel)
        self.assertLess(len(raw), viewer.PANEL_CAP)
        manifest = viewer.encoded(export_value(raw))
        session = viewer.Session(raw, manifest, viewer.pin(manifest)['sha256'],
                                 action_limit=327, output_limit=12*1024*1024)
        self.assertTrue(request(session, {'action': 'about'})['ok'])
        for split, count in (('training', 141), ('query', 92)):
            for i in range(count):
                self.assertTrue(request(session, {'action': 'view', 'split': split, 'index': i,
                                                  'units': [0, 65], 'bins': [0, 6]})['ok'])
        for i in range(92):
            self.assertTrue(request(session, {'action': 'answer', 'index': i, 'velocity': [0., 0.]})['ok'])
        self.assertTrue(request(session, {'action': 'finish'})['ok'])
        self.assertEqual(session.receipt()['attempted_actions'], 327)
        self.assertTrue(session.receipt()['complete'])

    def test_complete92_first_final_predictions_match_original_public_validator(self):
        first = request(self.session, {'action': 'answer', 'index': 0, 'velocity': [1., -2.]})
        self.assertTrue(first['ok'])
        self.assertFalse(request(self.session, {'action': 'answer', 'index': 0, 'velocity': [0., 0.]})['ok'])
        for i in reversed(range(1, 92)):
            self.assertTrue(request(self.session, {'action': 'answer', 'index': i, 'velocity': [float(i), -i]})['ok'])
        finished = request(self.session, {'action': 'finish'})
        prediction = finished['result']
        public = {'schema': 'neural022_public_cases_v1',
                  'cases': [{key: row[key] for key in ('id', 'mode', 'direction')} for row in self.panel['queries']]}
        validated = candidate.validate(viewer.encoded(prediction), public)
        self.assertEqual(validated[0], [1., -2.])
        self.assertEqual([r['id'] for r in prediction['predictions']], [r['id'] for r in public['cases']])
        self.assertTrue(self.session.receipt()['complete'])
        with self.assertRaises(ValueError):
            self.session.apply(viewer.encoded({'action': 'about'}))

    def test_incomplete_last_answer_cannot_finish_and_no_target_feedback(self):
        for i in range(91):
            self.assertTrue(request(self.session, {'action': 'answer', 'index': i, 'velocity': [0, 0]})['ok'])
        self.assertFalse(request(self.session, {'action': 'finish'})['ok'])
        self.assertFalse(self.session.receipt()['complete'])
        self.assertNotIn('score', self.session.receipt())
        self.assertFalse(self.session.receipt()['private_targets_loaded'])

    def test_malformed_actions_never_change_answers_or_views(self):
        invalid = [
            {'action': 'read', 'path': 'reference.private.npz'},
            {'action': 'view', 'split': 'query', 'index': True, 'units': [0, 65], 'bins': [0, 6]},
            {'action': 'view', 'split': 'query', 'index': 92, 'units': [0, 65], 'bins': [0, 6]},
            {'action': 'view', 'split': 'query', 'index': 0, 'units': [0, 66], 'bins': [0, 6]},
            {'action': 'view', 'split': 'query', 'index': 0, 'units': [0, 65], 'bins': [6, 6]},
            {'action': 'view', 'split': 'query', 'index': 0, 'units': [0, 65], 'bins': [0, 6], 'targets': True},
            {'action': 'answer', 'index': 0, 'velocity': [True, 0]},
            {'action': 'answer', 'index': 0, 'velocity': [2**2000, 0]},
            {'action': 'answer', 'index': 0, 'velocity': [0]},
        ]
        for value in invalid:
            self.assertFalse(request(self.session, value)['ok'])
        for raw in (b'{"action":"about","action":"finish"}\n', b'{"action":"answer","index":0,"velocity":[NaN,0]}\n',
                    b'{}{}\n', b'\xff\n'):
            self.assertFalse(viewer.strict(self.session.apply(raw))['ok'])
        with self.assertRaises(ValueError):
            self.session.apply(b'x'*4097)
        self.assertEqual(self.session.receipt()['answers'], 0)
        self.assertEqual(self.session.receipt()['views'], [])
        self.assertEqual(self.session.receipt()['attempted_actions'], len(invalid)+4)

    def test_full_panel_rejects_missing_support_target_injection_and_axis_changes(self):
        mutations = []
        p = copy.deepcopy(self.panel); p['queries'].pop(); mutations.append(p)
        p = copy.deepcopy(self.panel); p['queries'][0]['velocity'] = [0., 0.]; mutations.append(p)
        p = copy.deepcopy(self.panel); p['training'][0]['counts'][0].pop(); mutations.append(p)
        p = copy.deepcopy(self.panel); p['training'][0]['counts'][0][0] = -1; mutations.append(p)
        p = copy.deepcopy(self.panel); p['training'][0]['counts'][0][0] = True; mutations.append(p)
        p = copy.deepcopy(self.panel); p['queries'][0]['id'] = p['training'][0]['id']; mutations.append(p)
        p = copy.deepcopy(self.panel); p['queries'][0]['mode'] = 'active'; mutations.append(p)
        p = copy.deepcopy(self.panel); p['representation']['unit_positions'][1] = True; mutations.append(p)
        p = copy.deepcopy(self.panel); p['instructions'] += 'changed'; mutations.append(p)
        p = copy.deepcopy(self.panel); p['training'][0]['velocity'] = [10**308, 0]; mutations.append(p)
        for p in mutations:
            raw = viewer.encoded(p)
            manifest = viewer.encoded(export_value(raw))
            with self.assertRaises(ValueError):
                viewer.Session(raw, manifest, viewer.pin(manifest)['sha256'])

    def test_constructor_refuses_observation_from_a_different_or_unselected_export(self):
        changed = copy.deepcopy(self.panel)
        changed['training'][0]['counts'][0][0] += 1
        raw = viewer.encoded(changed)
        manifest = viewer.encoded(export_value(raw))
        # Both observations are scientifically-shaped valid generated panels.
        # The stale pairing must fail before panel validation or any action.
        with patch.object(viewer, 'validate_panel', side_effect=AssertionError('Unbound panel reached validation')):
            with self.assertRaisesRegex(ValueError, 'Observation belongs'):
                viewer.Session(raw, self.manifest, self.identity['sha256'])
            with self.assertRaisesRegex(ValueError, 'export commitment'):
                viewer.Session(raw, manifest, self.identity['sha256'])
        with self.assertRaises(TypeError):
            viewer.Session(self.raw, self.identity)  # Old descriptor-only API is unavailable.
        valid = viewer.Session(raw, manifest, viewer.pin(manifest)['sha256'])
        self.assertEqual(valid.receipt()['observation'], viewer.pin(raw))
        self.assertEqual(valid.receipt()['export'], viewer.pin(manifest))
        self.assertTrue(request(valid, {'action': 'about'})['ok'])

    def test_event_commitments_bind_exact_requests_responses_order_and_export(self):
        raws = [viewer.encoded({'action': 'about'}), viewer.encoded({'action': 'answer', 'index': 0, 'velocity': [3., 4.]})]
        responses = [self.session.apply(r) for r in raws]
        receipt = self.session.receipt(); previous = '0'*64
        for i, event in enumerate(receipt['events']):
            expected = {'sequence': i+1, 'request': viewer.pin(raws[i]), 'response': viewer.pin(responses[i]), 'previous': previous}
            previous = hashlib.sha256(viewer.encoded(expected)).hexdigest()
            self.assertEqual(event, expected | {'sha256': previous})
        self.assertEqual(receipt['event_chain'], previous)
        self.assertEqual(receipt['export'], self.identity)
        self.assertEqual(receipt['observation'], viewer.pin(self.raw))

    def test_mechanical_limits_do_not_silently_partial_accept(self):
        session = viewer.Session(self.raw, self.manifest, self.identity['sha256'], action_limit=327)
        for _ in range(327):
            self.assertFalse(request(session, {'action': 'unknown'})['ok'])
        with self.assertRaises(ValueError):
            request(session, {'action': 'answer', 'index': 0, 'velocity': [0, 0]})
        self.assertEqual(session.receipt()['answers'], 0)
        # Force the remaining-byte boundary without allocating repeated output.
        self.session._bytes = self.session._output_limit
        with self.assertRaises(ValueError):
            request(self.session, {'action': 'answer', 'index': 0, 'velocity': [0, 0]})
        self.assertEqual(self.session.receipt()['answers'], 0)

    def test_loader_touches_only_committed_export_and_observation(self):
        manifest = viewer.encoded(export_value(self.raw))
        calls = []
        def capture(path, cap, expected):
            calls.append(Path(path).name)
            value = manifest if Path(path).name == 'EXPORT.json' else self.raw
            self.assertEqual(hashlib.sha256(value).hexdigest(), expected)
            return value
        with patch.object(viewer, 'capture', side_effect=capture):
            loaded, captured_manifest = viewer.load_export('/generated/unused', hashlib.sha256(manifest).hexdigest())
        self.assertEqual(calls, ['EXPORT.json', 'OBSERVATION.json'])
        self.assertEqual(loaded, self.raw); self.assertEqual(captured_manifest, manifest)

    def test_changed_predecessor_or_export_extent_refused_before_use(self):
        for change in ('producer', 'extent', 'ready'):
            obj = export_value(self.raw)
            if change == 'producer': obj['packet_producer'] = {'bytes': 1, 'sha256': '0'*64}
            if change == 'extent': obj['observation']['bytes'] -= 1
            if change == 'ready': obj['provider_delivery_qualified'] = True
            manifest = viewer.encoded(obj)
            def capture(path, cap, expected):
                return manifest if Path(path).name == 'EXPORT.json' else self.raw
            with patch.object(viewer, 'capture', side_effect=capture):
                with self.assertRaises(ValueError):
                    viewer.load_export('/generated/unused', hashlib.sha256(manifest).hexdigest())

    def test_about_uses_viewer_instructions_and_never_claims_native_or_image_proof(self):
        result = request(self.session, {'action': 'about'})['result']
        self.assertEqual(result['condition'], viewer.CONDITION)
        self.assertIn('optional', viewer.INSTRUCTIONS)
        self.assertNotEqual(result['instructions'], self.panel['instructions'])
        self.assertFalse(result['external_isolation_verified'])
        self.assertFalse(result['image_rendering_verified'])
        self.assertIs(type(result['queries']), int)
        self.assertEqual(result['queries'], 92)
        self.assertNotIn('training', result)


if __name__ == '__main__':
    unittest.main(argv=[__file__, *REMAINING])
