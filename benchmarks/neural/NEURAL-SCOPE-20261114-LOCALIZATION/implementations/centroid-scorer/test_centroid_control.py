"""Invented complete880 controls; no original corpus or spatial targets opened."""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import centroid_control as c

ROOT = Path(__file__).resolve().parent
PROGRAM = hashlib.sha256(Path(c.__file__).read_bytes()).hexdigest()


def opaque(text):
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()


def npy(coords, dtype='<f8', fortran=False, version=1):
    shape = (len(coords), 2)
    header = repr({'descr': dtype, 'fortran_order': fortran, 'shape': shape}).encode('ascii')
    start = 10 if version == 1 else 12
    header += b' ' * ((-start - len(header) - 1) % 64) + b'\n'
    values = ([row[j] for j in range(2) for row in coords] if fortran
              else [v for row in coords for v in row])
    raw = b'\x93NUMPY' + bytes((version, 0))
    raw += struct.pack('<H' if version == 1 else '<I', len(header)) + header
    raw += b''.join(struct.pack('<' + c.DTYPES[dtype][0], v) for v in values)
    return raw


def descriptor(raw, shape=None, dtype='<f8'):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
            'role': 'probe_geometry', 'dtype': dtype, 'shape': shape or [3, 2]}


def fixture(coords=None, axes=None):
    coords = coords or [[-100, 0], [0, 0], [100, 0]]
    raw = npy(coords)
    art = descriptor(raw, [len(coords), 2])
    arts = [art]
    inputs = {'probe_geometry': art['sha256']}
    for role, shape, dtype in [('waveforms', [2, 3, len(coords)], '<f4'),
                               ('template', [3, len(coords)], '<f4'),
                               ('observed_support', [len(coords)], '|b1')]:
        # These unavailable bodies must never be requested by the producer.
        h = hashlib.sha256(('unavailable-' + role).encode()).hexdigest()
        arts.append({'sha256': h, 'bytes': 100, 'role': role, 'dtype': dtype, 'shape': shape})
        inputs[role] = h
    cells = [opaque('cell' + str(i)) for i in range(11)]
    conds = [opaque('condition' + str(i)) for i in range(16)]
    seeds = [opaque('realization' + str(i)) for i in range(5)]
    neural = {'schema': 'localization-normalized-neural-v1', 'task_id': 'NEURAL-SCOPE-20261114-LOCALIZATION',
              'axis_names': axes or ['x', 'y'], 'coordinate_unit': 'um', 'cells': cells,
              'conditions': conds, 'realizations': seeds, 'artifacts': arts, 'cases': []}
    for cell in cells:
        for condition in conds:
            for seed in seeds:
                cid = opaque(cell + condition + seed)
                neural['cases'].append({'case_id': cid, 'cell_id': cell, 'condition_id': condition,
                    'realization_id': seed, 'sampling_frequency_hz': 30000, 'voltage_unit': 'uV',
                    'sample_offsets': [-1, 0, 1], 'channel_ids': [opaque('channel' + str(i)) for i in range(len(coords))],
                    'inputs': dict(inputs), 'requests': [
                        {'request_id': opaque(cid + 'spike' + str(i)), 'kind': 'spike', 'array_index': i}
                        for i in range(2)] + [{'request_id': opaque(cid + 'template'), 'kind': 'template', 'array_index': 0}]})
    reference = {'schema': 'localization-owner-reference-v1', 'coordinate_unit': 'um',
                 'axis_names': neural['axis_names'], 'reference_kind': 'nearest_contact_proxy',
                 'reference_evidence_sha256': '1' * 64, 'group_evidence_sha256': '2' * 64,
                 'undegraded_condition_id': conds[0], 'cells': []}
    for i, cell in enumerate(cells):
        reference['cells'].append({'cell_id': cell, 'recording_id': opaque('recording' + str(i)),
            'animal_id': opaque('animal' + str(bool(i))), 'coordinate_um': [100 if i else 0, 0]})
    return neural, {art['sha256']: raw}, reference


def run_control(neural, bodies, budget=100000, **kwargs):
    calls = []
    def load(desc):
        calls.append(desc['role'])
        if desc['role'] != 'probe_geometry':
            raise AssertionError('forbidden body requested')
        return bodies[desc['sha256']]
    h = hashlib.sha256(json.dumps(neural, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    out, receipt = c.produce(neural, load, repo_root=ROOT, expected_manifest_sha256=h,
                             expected_program_sha256=PROGRAM, geometry_byte_budget=budget, **kwargs)
    return out, receipt, calls


class CentroidTests(unittest.TestCase):
    def test_full880_geometry_only_and_unchanged_scorer(self):
        neural, bodies, reference = fixture()
        out, receipt, calls = run_control(neural, bodies)
        self.assertEqual(calls, ['probe_geometry'])
        self.assertEqual((receipt['cases'], receipt['requested_rows']), (880, 2640))
        self.assertEqual({r['request_id'] for r in out['rows']},
                         {r['request_id'] for case in neural['cases'] for r in case['requests']})
        self.assertFalse(receipt['competent_reference'])
        neutral = c.load_neutral(ROOT)
        score = neutral.score(neural, reference, out, PROGRAM)
        self.assertEqual(score['status'], 'COMPLETE_SUPPORT_SCORE')
        self.assertEqual(score['primary_spike_macro_accuracy'], .5)
        self.assertTrue(all(r['distance_from_own_undegraded_template_um'] == 0 for r in score['template_stability']))
        self.assertEqual({r['error_um'] for r in score['row_diagnostics']}, {0, 100})

    def test_all_contacts_and_axis_order(self):
        neural, bodies, _ = fixture([[0, 0], [3, 6], [9, 12]], ['z', 'x'])
        out, receipt, _ = run_control(neural, bodies)
        self.assertEqual(out['axis_names'], ['z', 'x'])
        self.assertTrue(all(r['coordinate_um'] == [4, 6] for r in out['rows']))
        self.assertTrue(all(r['contact_count'] == 3 for r in receipt['per_case']))

    def test_npy_c_and_fortran_primitive_orders(self):
        coords = [[1, 9], [3, 7], [8, 2]]
        for dtype in c.DTYPES:
            for order in (False, True):
                for version in (1, 2):
                    raw = npy(coords, dtype, order, version)
                    self.assertEqual(c.decode_geometry(raw, descriptor(raw, dtype=dtype)), coords)

    def test_geometry_hash_shape_nonfinite_payload_rejected(self):
        raw = npy([[1, 2], [3, 4], [5, 6]])
        bad = [(raw + b'x', descriptor(raw)),
               (raw, descriptor(raw, shape=[2, 2])),
               (raw, descriptor(raw, dtype='<f4'))]
        for candidate in (raw[:-1], raw + b'x', npy([[1, 2], [3, float('nan')], [5, 6]])):
            bad.append((candidate, descriptor(candidate)))
        for data, desc in bad:
            with self.subTest(size=len(data)), self.assertRaises(c.ControlError):
                c.decode_geometry(data, desc)

    def test_header_object_duplicate_or_nonboolean_refused(self):
        headers = ["{'descr':'|O','shape':(3,2),'fortran_order':False}",
                   "{'descr':'<f8','shape':(3,2),'shape':(3,2),'fortran_order':False}",
                   "{'descr':'<f8','shape':(3,2),'fortran_order':0}"]
        for text in headers:
            h = text.encode() + b'\n'
            raw = b'\x93NUMPY\x01\x00' + struct.pack('<H', len(h)) + h + bytes(48)
            with self.assertRaises(c.ControlError):
                c.decode_geometry(raw, descriptor(raw))

    def test_no_subset_and_no_private_fields_before_body(self):
        original, bodies, _ = fixture()
        for mutate in ('missing_case', 'missing_request', 'extra_target'):
            neural = copy.deepcopy(original)
            if mutate == 'missing_case': neural['cases'].pop()
            elif mutate == 'missing_request': neural['cases'][0]['requests'].pop(0)
            else: neural['spatial_target'] = [0, 0]
            with self.subTest(mutate=mutate), self.assertRaises(c.ControlError):
                run_control(neural, bodies)

    def test_budget_and_identity_refuse_before_loader(self):
        neural, bodies, _ = fixture()
        neutral = c.load_neutral(ROOT)
        expected = hashlib.sha256(neutral.canonical(neural)).hexdigest()
        for manifest, program, budget in [(None, PROGRAM, 10000), (expected, None, 10000),
                                           ('0' * 64, PROGRAM, 10000), (expected, PROGRAM, 1)]:
            with self.assertRaises(c.ControlError):
                c.produce(neural, lambda _: self.fail('body read after refusal'), repo_root=ROOT,
                          expected_manifest_sha256=manifest, expected_program_sha256=program,
                          geometry_byte_budget=budget)

    def test_inconsistent_cell_geometry_refused(self):
        neural, bodies, _ = fixture()
        raw = npy([[0, 0], [1, 0], [2, 0]])
        desc = descriptor(raw)
        neural['artifacts'].append(desc); bodies[desc['sha256']] = raw
        neural['cases'][0]['inputs']['probe_geometry'] = desc['sha256']
        with self.assertRaisesRegex(c.ControlError, 'inconsistent contacts'):
            run_control(neural, bodies)

    def test_consistent_channel_permutation_allowed(self):
        neural, bodies, _ = fixture()
        raw = npy([[100, 0], [0, 0], [-100, 0]])
        desc = descriptor(raw); neural['artifacts'].append(desc); bodies[desc['sha256']] = raw
        neural['cases'][0]['inputs']['probe_geometry'] = desc['sha256']
        neural['cases'][0]['channel_ids'].reverse()
        out, receipt, calls = run_control(neural, bodies)
        self.assertEqual(len(out['rows']), 2640)
        self.assertEqual(len(calls), 2)

    def test_representable_mean_no_overflow(self):
        self.assertEqual(c.centroid([[1e308, -1e308], [1e308, 1e308]]), [1e308, 0])
        self.assertEqual(c.centroid([[1e308, 0], [-1e308, 0], [3, 0]]), [1, 0])
        for value in (True, float('inf'), 10 ** 1000):
            with self.assertRaises(c.ControlError): c.centroid([[value, 0]])

    def test_cli_complete_geometry_only_paths(self):
        neural, bodies, _ = fixture()
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); (base / 'inputs').mkdir()
            for h, body in bodies.items(): (base / 'inputs' / (h + '.npy')).write_bytes(body)
            raw = json.dumps(neural).encode(); (base / 'manifest.json').write_bytes(raw)
            args = ['--repo-root', str(ROOT), '--manifest', str(base / 'manifest.json'),
                    '--manifest-sha256', hashlib.sha256(raw).hexdigest(), '--program-sha256', PROGRAM,
                    '--participant-root', str(base), '--geometry-byte-budget', '10000',
                    '--output', str(base / 'prediction.json'), '--receipt', str(base / 'receipt.json')]
            c.main(args)
            self.assertEqual(len(json.loads((base / 'prediction.json').read_text())['rows']), 2640)
            self.assertEqual(json.loads((base / 'receipt.json').read_text())['manifest_file_sha256'], hashlib.sha256(raw).hexdigest())
            with self.assertRaises(FileExistsError): c.main(args)

    def test_regular_boundary_and_required_pin(self):
        with patch.object(c.os, 'open', side_effect=AssertionError('opened')):
            with self.assertRaises(c.ControlError): c.read_regular('unused', 1, None)
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); regular = base / 'regular'; regular.write_bytes(b'x')
            (base / 'link').symlink_to(regular); os.mkfifo(base / 'fifo')
            for path in (base / 'link', base / 'fifo', base):
                with self.assertRaises(c.ControlError):
                    c.read_regular(path, 1, hashlib.sha256(b'x').hexdigest())

    def test_strict_json_duplicate_and_nonfinite(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'\xff'):
            with self.assertRaises(c.ControlError): c.strict_json(raw)


if __name__ == '__main__':
    unittest.main()
