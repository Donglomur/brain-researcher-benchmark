"""Generated engineering controls; no authentic EEG or scientific outcomes."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

observation = load('observation')
session = load('session')


def npy(value=0.0):
    header = b"{'descr': '<f4', 'fortran_order': False, 'shape': (64, 512)}\n"
    return b'\x93NUMPY\x01\x00' + struct.pack('<H', len(header)) + header + struct.pack('<f', value)*32768


def roster(payload):
    digest = hashlib.sha256(payload).hexdigest()
    return [dict(row_alias=f'{group*12+number+1:032x}', group_alias=f'{group+1000:032x}',
                 label=label, npy_sha256=digest)
            for group in range(9) for number, label in enumerate(observation.CLASS_IDS)]


class SessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = npy()
        cls.query_alias = 'f'*32
        cls.query = observation.prepare_observation(cls.payload, context_alias=cls.query_alias, view='EEG')
        cls.training_image = observation.prepare_observation(cls.payload, context_alias='1'.zfill(32), view='EEG')

    def prepare(self, rows=None, expected=None, loader=None, view='EEG'):
        rows = roster(self.payload) if rows is None else rows
        expected = [row['row_alias'] for row in rows] if expected is None else expected
        return session.prepare_session(self.payload, context_alias=self.query_alias, view=view,
                                       training_rows=rows, expected_training_aliases=expected,
                                       load_training_window=loader or (lambda alias: self.payload))

    def test_complete_ordered_training_and_unlabeled_query_are_both_available(self):
        loaded = []
        with patch.object(observation, 'prepare_observation', return_value=self.query):
            projected = self.prepare(loader=lambda alias: loaded.append(alias) or self.payload)
        metadata = projected.metadata()
        self.assertEqual(len(metadata['training']), 108)
        self.assertEqual(metadata['training_group_count'], 9)
        self.assertEqual(loaded, [])
        # Streaming coverage is tested without redundantly rasterizing 108 copies.
        with patch.object(observation, 'prepare_observation', return_value=self.training_image):
            packets = list(projected.direct_packets())
        expected = [row['row_alias'] for row in roster(self.payload)]
        self.assertEqual(loaded, expected)
        self.assertEqual([packet['row_alias'] for packet in packets[:-1]], expected)
        self.assertEqual(len(packets), 109)
        self.assertEqual(set(packets[-1]), {'role', 'row_alias', 'observation'})
        self.assertEqual(packets[-1]['role'], 'query')
        self.assertNotIn('npy_sha256', str(metadata))

    def test_real_direct_and_viewer_demo_use_identical_four_image_bodies(self):
        projected = self.prepare()
        first = next(projected.direct_packets())
        alias = first['row_alias']
        for page in range(4):
            reply = projected.page({'action': 'view_page', 'row_alias': alias, 'page': page})
            self.assertEqual(reply['label'], 1)
            self.assertEqual(reply['image'], first['observation']['images'][page])
        query = projected.page({'action': 'view_page', 'row_alias': self.query_alias, 'page': 3})
        self.assertEqual(query['image'], projected._query.direct()['images'][3])
        self.assertEqual(set(query), {'role', 'row_alias', 'image'})

    def test_incomplete_reordered_duplicate_and_query_training_support_refuse_before_load(self):
        rows = roster(self.payload)
        expected = [row['row_alias'] for row in rows]
        bad_cases = [rows[:-1], list(reversed(rows))]
        duplicate = copy.deepcopy(rows); duplicate[1]['row_alias'] = duplicate[0]['row_alias']
        bad_cases.append(duplicate)
        query_in_train = copy.deepcopy(rows); query_in_train[0]['row_alias'] = self.query_alias
        bad_cases.append(query_in_train)
        for bad in bad_cases:
            with self.subTest(case=bad[:1]), patch.object(observation, 'prepare_observation') as render:
                with self.assertRaises(ValueError): self.prepare(rows=bad, expected=expected)
                render.assert_not_called()

    def test_every_group_and_class_required_and_no_extra_private_fields(self):
        for alteration in ('missing_class', 'extra_group', 'boolean_label', 'source_path', 'query_label'):
            rows = roster(self.payload)
            if alteration == 'missing_class': rows[0]['label'] = 2
            if alteration == 'extra_group': rows[0]['group_alias'] = 'e'*32
            if alteration == 'boolean_label': rows[0]['label'] = True
            if alteration == 'source_path': rows[0]['source_path'] = '/private/source.fif'
            if alteration == 'query_label': rows[0]['query_label'] = 1
            with self.subTest(alteration=alteration), self.assertRaises(ValueError): self.prepare(rows=rows)

    def test_rejected_viewer_requests_do_not_open_any_waveform(self):
        loaded = []
        projected = self.prepare(loader=lambda alias: loaded.append(alias) or self.payload)
        for action in ({'action': 'view_page', 'row_alias': 'e'*32, 'page': 0},
                       {'action': 'view_page', 'row_alias': '1'.zfill(32), 'page': True},
                       {'action': 'view_page', 'row_alias': '1'.zfill(32), 'page': 4},
                       {'action': 'raw', 'row_alias': '1'.zfill(32), 'page': 0},
                       {'action': 'view_page', 'row_alias': '1'.zfill(32), 'page': 0, 'scale': 2}):
            with self.subTest(action=action), self.assertRaises(ValueError): projected.page(action)
        self.assertEqual(loaded, [])

    def test_input_mutation_does_not_relabel_admitted_demonstration(self):
        rows = roster(self.payload)
        projected = self.prepare(rows=rows)
        rows[0]['label'] = 24
        public = projected.metadata(); public['training'][0]['label'] = 24
        self.assertEqual(projected.metadata()['training'][0]['label'], 1)

    def test_changed_missing_and_nonbytes_training_window_cannot_be_delivered(self):
        for payload in (self.payload[:-1], npy(1e-6), bytearray(self.payload)):
            projected = self.prepare(loader=lambda alias: payload)
            with self.subTest(kind=type(payload)), self.assertRaises(ValueError): next(projected.direct_packets())
        def missing(alias): raise FileNotFoundError('/private/source/held-P01.fif')
        projected = self.prepare(loader=missing)
        with self.assertRaisesRegex(ValueError, '^Authorized training observation is unavailable$') as error:
            next(projected.direct_packets())
        self.assertNotIn('/private/', str(error.exception))

    def test_zero_view_never_uses_nonzero_training_even_with_a_matching_pin(self):
        payload = npy(1e-6)
        rows = roster(payload)
        projected = self.prepare(rows=rows, loader=lambda alias: payload, view='ZERO')
        with self.assertRaises(ValueError): next(projected.direct_packets())


if __name__ == '__main__':
    unittest.main()
