"""Generated full-scope controls; no authentic payload, target, or model reads."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
import delivery as d
import interface


def fixture():
    # Distinct source-bin/unit values make a one-bin shift or axis swap observable.
    counts = tuple(tuple(100*b + u for u in range(65)) for b in range(35))
    history = d.expand_counts(counts)
    conditions = [0] * 52 + [1] * 40
    cases = {'schema': 'neural021_public_cases_v1', 'task_id': 'NEURAL-021', 'time_bins': 30,
             'feature_shape': [30, 6, 65], 'units': 'm/s', 'conditions': {'0': 'active', '1': 'passive'},
             'queries': [{'trial_id': f'q{i:04d}', 'condition': d.CONDITIONS[c]} for i, c in enumerate(conditions)]}
    train = {'spike_counts': [history] * 272, 'condition': [0, 1] * 136,
             'velocity_m_s': [[[j / 10, -j / 20] for j in range(30)]] * 272}
    query = {'spike_counts': [history] * 92, 'condition': conditions}
    return train, query, d.encode(cases), counts


class DeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train, cls.query, cls.cases, cls.counts = fixture()
        cls.packet = d.Packet.from_arrays(cls.train, cls.query, cls.cases)

    def test_lossless_history_and_independent_time_formula(self):
        collapsed = d.collapse_histories(d.expand_counts(self.counts))
        self.assertEqual(collapsed, self.counts)
        for j in range(30):
            for h in range(6):
                # Independent physical-time relation, not just inverse identity.
                history_start_ms = (-100 + j*20) - 120 + h*20
                k = (history_start_ms + 220)//20
                self.assertEqual(collapsed[k][64], 100*k + 64)
        self.assertEqual((-220 + 35*20, -100 + 30*20), (480, 500))

    def test_overlap_corruption_boolean_and_negative_counts_refused(self):
        history = [[list(row) for row in block] for block in d.expand_counts(self.counts)]
        history[1][0][0] += 1  # Same physical bin as [0][1][0].
        with self.assertRaisesRegex(ValueError, 'overlapping'):
            d.collapse_histories(history)
        for bad in (True, -1, 1.0, 2**63):
            history = [[list(row) for row in block] for block in d.expand_counts(self.counts)]
            history[0][0][0] = bad
            with self.assertRaisesRegex(ValueError, 'counts'):
                d.collapse_histories(history)

    def test_all_scope_and_identity_guards(self):
        for key in ('spike_counts', 'condition'):
            bad = dict(self.train); bad[key] = bad[key][:-1]
            with self.assertRaisesRegex(ValueError, '272/92'):
                d.Packet.from_arrays(bad, self.query, self.cases)
        wrong = json.loads(self.cases); wrong['queries'][0]['condition'] = 'passive'
        with self.assertRaisesRegex(ValueError, '52 active'):
            d.Packet.from_arrays(self.train, self.query, d.encode(wrong))
        wrong = dict(self.query); wrong['condition'] = list(reversed(self.query['condition']))
        with self.assertRaisesRegex(ValueError, 'roster condition'):
            d.Packet.from_arrays(self.train, wrong, self.cases)
        wrong = dict(self.query); wrong['velocity_m_s'] = []
        with self.assertRaisesRegex(ValueError, 'public-only'):
            d.Packet.from_arrays(self.train, wrong, self.cases)
        wrong = json.loads(self.cases); wrong['units'] = 'cm/s'
        with self.assertRaisesRegex(ValueError, 'metadata'):
            d.Packet.from_arrays(self.train, self.query, d.encode(wrong))

    def test_render_every_count_and_keep_query_target_free(self):
        rendered = d.render_svg(self.packet.queries[0])
        root = ET.fromstring(rendered)
        cells = {(int(e.attrib['data-bin']), int(e.attrib['data-unit'])): int(e.text)
                 for e in root.iter() if 'data-bin' in e.attrib}
        self.assertEqual(len(cells), 35*65)
        self.assertEqual(cells, {(b, u): 100*b + u for b in range(35) for u in range(65)})
        self.assertNotIn('TRAINING LABELS', rendered)
        self.assertIn('20 ms half-open', rendered)
        self.assertIn('m/s', rendered)
        self.assertIn('future acceleration', rendered)
        self.assertNotIn('http://', rendered.replace('http://www.w3.org/2000/svg', ''))
        training = d.render_svg(self.packet.training[0])
        self.assertIn('TRAINING LABELS ONLY', training)
        self.assertIn('29 | [+480,+500) | 2.9 | -1.45', training)

    def test_typed_crops_preserve_units_times_and_counts(self):
        session = d.Session(self.packet, 'typed_viewer')
        with self.assertRaisesRegex(ValueError, 'complete query'):
            session.view('q0000', unit_start=60)
        session.view('q0000')
        root = ET.fromstring(session.view('q0000', unit_start=60, unit_stop=65, bin_start=29, bin_stop=35))
        cells = {(int(e.attrib['data-bin']), int(e.attrib['data-unit'])): int(e.text)
                 for e in root.iter() if 'data-bin' in e.attrib}
        self.assertEqual(cells, {(b, u): 100*b+u for b in range(29, 35) for u in range(60, 65)})
        for bad in ({'unit_start': True}, {'bin_stop': 36}, {'normalization': 'zscore'}):
            with self.assertRaises(ValueError):
                session.view('q0000', **bad)
        direct = d.Session(self.packet, 'direct_observation')
        direct.view('q0000')
        with self.assertRaisesRegex(ValueError, 'fixed complete view'):
            direct.view('q0000', unit_start=0)

    def test_complete_two_arm_response_and_original_interface(self):
        outputs, receipts = [], []
        for mode in d.MODES:
            session = d.Session(self.packet, mode)
            # The whole calibration catalog is accessible; test both endpoints.
            self.assertIn('t0000', session.calibration(0))
            self.assertIn('t0271', session.calibration(271))
            for i in reversed(range(92)):
                key = f'q{i:04d}'
                session.view(key)
                session.answer(key, [[i + j/100, -i-j/200] for j in range(30)])
            raw, receipt = session.finish()
            submission = interface.strict_json(raw)
            values = interface.validate_submission(submission, json.loads(self.cases), d.sha(self.cases))
            self.assertEqual(len(values), 92)
            self.assertEqual(values[91][29], [91.29, -91.145])
            self.assertEqual([r['trial_id'] for r in submission['predictions']], [f'q{i:04d}' for i in range(92)])
            rec = json.loads(receipt)
            self.assertEqual(rec['mode'], mode)
            self.assertEqual(rec['submission_sha256'], d.sha(raw))
            self.assertFalse(rec['runtime_qualified'])
            previous = '0'*64
            for event in rec['events']:
                digest = event.pop('sha256')
                self.assertEqual(event['previous_sha256'], previous)
                self.assertEqual(d.sha(d.encode(event)), digest)
                previous = digest
            with self.assertRaisesRegex(ValueError, 'sealed'):
                session.finish()
            outputs.append(raw); receipts.append(rec)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(receipts[0]['observation_sha256'], receipts[1]['observation_sha256'])

    def test_incomplete_malformed_repeated_answers_and_budget(self):
        session = d.Session(self.packet, 'typed_viewer')
        with self.assertRaisesRegex(ValueError, 'view once'):
            session.answer('q0000', [[0, 0]]*30)
        session.view('q0000')
        for values in ([[0, 0]]*29, [[0, 0]]*29 + [[True, 0]], [[0, 0]]*29 + [[float('nan'), 0]],
                       [[0, 0]]*29 + [[0, 1e7]], [[0, 0]]*29 + [[0]]):
            with self.assertRaises(ValueError):
                session.answer('q0000', values)
        session.answer('q0000', [[0, 0]]*30)
        with self.assertRaisesRegex(ValueError, 'immutable answer'):
            session.answer('q0000', [[1, 1]]*30)
        with self.assertRaisesRegex(ValueError, 'all 92'):
            session.finish()
        session._view_count = d.MAX_VIEWS  # Generated boundary control, no views actually consumed.
        with self.assertRaisesRegex(ValueError, 'budget exhausted'):
            session.calibration(0)

    def test_public_file_authentication_before_numpy_use(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'cases.json'
            path.write_bytes(b'public fixture')
            self.assertEqual(d._capture(path, 14, d.sha(b'public fixture')), b'public fixture')
            with self.assertRaisesRegex(ValueError, 'pin'):
                d._capture(path, 14, '0'*64)
            with self.assertRaisesRegex(ValueError, 'exact ordinary'):
                d.load_public(directory, None)


if __name__ == '__main__':
    unittest.main(verbosity=2)
