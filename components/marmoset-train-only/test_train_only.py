"""Invented complete170-cell response-branch controls; no native imports."""
import copy
import hashlib
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import train_only as m


def ident(value):
    return hashlib.sha256(value.encode()).hexdigest()[:32]


def make_npy(shape, values, order=False, dtype='<i4'):
    header = repr({'descr': dtype, 'fortran_order': order, 'shape': tuple(shape)}).encode()
    header += b' ' * ((-10 - len(header) - 1) % 64) + b'\n'
    cells, trials, frames = shape
    indexes = ([c * trials * frames + t * frames + f for f in range(frames)
                for t in range(trials) for c in range(cells)] if order else range(len(values)))
    return b'\x93NUMPY\x01\x00' + struct.pack('<H', len(header)) + header + b''.join(
        struct.pack('<' + m.DTYPES[dtype][0], values[i]) for i in indexes)


def fixture(condition='wn_to_wn'):
    classes = [kind for kind, count in m.CLASSES.items() for _ in range(count)]
    cells = [{'cell_id': ident('selected' + str(i)), 'published_class': classes[i]} for i in range(170)]
    preparations = [{'dataset': dataset, 'cells': cells[i * 85:(i + 1) * 85]}
                    for i, dataset in enumerate(sorted(m.DATASETS))]
    policy = {'schema': 'marmoset-train-only-policy-v1', 'task_id': m.TASK,
              'source_release': '10.12751/g-node.t43ph1', 'condition': condition,
              'cohort_evidence_sha256': '1' * 64, 'complete_stream_census_sha256': '2' * 64,
              'preparations': preparations, 'streams': []}
    bodies, expected = {}, {}
    for prep_number, prep in enumerate(preparations):
        # Raw source contains one extra, unselected row and a nontrivial row order.
        source_cells = [ident('unselected' + str(prep_number))] + [c['cell_id'] for c in reversed(prep['cells'])]
        for domain, seed in [('WN', None), ('NM', 1), ('NM', 2)]:
            shape = [86, 2, 3]
            values = [10000 * prep_number + (1000 if domain == 'NM' else 0) + (seed or 0) * 100 + i
                      for i in range(86 * 2 * 3)]
            raw = make_npy(shape, values, order=bool(prep_number))
            stream = {'dataset': prep['dataset'], 'stimulus': domain, 'seed': seed,
                      'source_cell_ids': source_cells, 'train_trial_ids': [ident('trial0'), ident('trial1')],
                      'train_frames_per_trial': 3, 'test_frames_per_trial': 7,
                      'timing_evidence_sha256': '3' * 64, 'independent_extent_evidence_sha256': '4' * 64,
                      'artifact': {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                                   'dtype': '<i4', 'shape': shape}}
            policy['streams'].append(stream)
            path = str(m.official_training_path(stream)); bodies[path] = raw
            expected[(prep['dataset'], domain, seed)] = [v for cell in prep['cells']
                for v in values[source_cells.index(cell['cell_id']) * 6:(source_cells.index(cell['cell_id']) + 1) * 6]]
    return policy, bodies, expected


def install(folder, policy, bodies, only_permitted=True):
    for stream in policy['streams']:
        if only_permitted and stream['stimulus'] not in m.CONDITIONS[policy['condition']]:
            continue
        path = Path(folder) / m.official_training_path(stream); path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bodies[str(m.official_training_path(stream))])


def run(policy, root, **kwargs):
    return m.prepare_training(policy, policy_sha256=hashlib.sha256(m.canonical(policy)).hexdigest(),
                              source_root=root, read_byte_budget=1000000,
                              output_byte_budget=1000000, **kwargs)


class TrainOnlyTests(unittest.TestCase):
    def test_complete170_exact_projection_both_storage_orders(self):
        policy, bodies, expected = fixture()
        with tempfile.TemporaryDirectory() as folder:
            install(folder, policy, bodies)
            result = run(policy, folder)
        self.assertEqual((result['selected_cells'], result['preparations'], len(result['packets'])), (170, 2, 2))
        self.assertFalse(result['scientific_qualification'])
        for packet in result['packets']:
            self.assertEqual(packet['shape'], [85, 2, 3])
            values = [x[0] for x in struct.iter_unpack('<i', packet['counts'])]
            self.assertEqual(values, expected[(packet['dataset'], packet['stimulus'], packet['seed'])])
            self.assertEqual(len(packet['cell_ids']), 85)
            self.assertEqual(packet['test_frames_per_trial'], 7)

    def test_all_six_conditions_and_forbidden_opens(self):
        original_open = os.open
        for condition, roles in m.CONDITIONS.items():
            policy, bodies, _ = fixture(condition)
            opened = []
            with tempfile.TemporaryDirectory() as folder:
                install(folder, policy, bodies, only_permitted=True)
                def monitor(path, *args, **kwargs):
                    relative = Path(path).relative_to(folder); opened.append(str(relative))
                    self.assertEqual(relative.name, 'train_responses_binned.npy')
                    self.assertNotIn('test', str(relative)); self.assertNotIn('stas', str(relative))
                    return original_open(path, *args, **kwargs)
                with patch.object(m.os, 'open', side_effect=monitor):
                    result = run(policy, folder)
            self.assertEqual(len(opened), sum(s['stimulus'] in roles for s in policy['streams']))
            self.assertEqual({p['stimulus'] for p in result['packets']}, set(roles))
            self.assertTrue(all(p['response_access'] == roles[p['stimulus']] for p in result['packets']))
            self.assertEqual(result['protected_response_reads'], 0)
            self.assertEqual(result['original_sta_reads'], 0)

    def test_required_policy_identity_before_open(self):
        policy, _, _ = fixture()
        for expected in (None, '0' * 64):
            with patch.object(m.os, 'open', side_effect=AssertionError('opened before authentication')):
                with self.assertRaises(m.InputError):
                    m.prepare_training(policy, policy_sha256=expected, source_root='unused',
                                       read_byte_budget=10000, output_byte_budget=10000)

    def test_missing_support_and_extra_fields_before_open(self):
        original, _, _ = fixture()
        for change in ('cell', 'preparation', 'wn_stream', 'nm_streams', 'trial', 'shape_bool', 'test_path', 'unknown_domain'):
            policy = copy.deepcopy(original)
            if change == 'cell': policy['preparations'][0]['cells'].pop()
            elif change == 'preparation': policy['preparations'].pop()
            elif change == 'wn_stream': policy['streams'].pop(0)
            elif change == 'nm_streams': del policy['streams'][1:3]
            elif change == 'trial': policy['streams'][0]['train_trial_ids'].pop()
            elif change == 'shape_bool': policy['streams'][0]['artifact']['shape'][0] = True
            elif change == 'test_path': policy['streams'][0]['artifact']['path'] = 'test_responses_binned.npy'
            elif change == 'unknown_domain': policy['streams'][0]['stimulus'] = 'all'
            with self.subTest(change=change), patch.object(m.os, 'open', side_effect=AssertionError('opened')):
                with self.assertRaises(m.InputError): run(policy, 'unused')

    def test_complete_allocation_refuses_before_open(self):
        policy, _, _ = fixture()
        h = hashlib.sha256(m.canonical(policy)).hexdigest()
        for read, output in [(1, 1000000), (1000000, 1)]:
            with patch.object(m.os, 'open', side_effect=AssertionError('opened')):
                with self.assertRaises(m.InputError):
                    m.prepare_training(policy, policy_sha256=h, source_root='unused',
                                       read_byte_budget=read, output_byte_budget=output)

    def test_body_tampering_and_shape_mismatch(self):
        policy, bodies, _ = fixture()
        stream = policy['streams'][0]
        raw = bodies[str(m.official_training_path(stream))]
        for body in (raw[:-1], raw + b'x', raw[:-1] + bytes([raw[-1] ^ 1])):
            with self.assertRaises(m.InputError):
                m.project_counts(body, stream['artifact'], stream['source_cell_ids'],
                                 [c['cell_id'] for c in policy['preparations'][0]['cells']])
        artifact = dict(stream['artifact'], shape=[86, 3, 2])
        with self.assertRaises(m.InputError):
            m.project_counts(raw, artifact, stream['source_cell_ids'], [stream['source_cell_ids'][0]])

    def test_count_domain_and_object_refusal(self):
        for value in (-1, .25, float('nan'), float('inf')):
            raw = make_npy([1, 1, 1], [value], dtype='<f8')
            art = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'dtype': '<f8', 'shape': [1, 1, 1]}
            with self.assertRaises(m.InputError): m.project_counts(raw, art, ['a'], ['a'])
        raw = make_npy([1, 1, 1], [1])
        art = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'dtype': '|O', 'shape': [1, 1, 1]}
        with self.assertRaises(m.InputError): m.project_counts(raw, art, ['a'], ['a'])

    def test_primitive_dtypes_preserve_full_counts(self):
        for dtype in m.DTYPES:
            raw = make_npy([2, 1, 2], [1, 2, 3, 4], order=True, dtype=dtype)
            art = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'dtype': dtype, 'shape': [2, 1, 2]}
            result = m.project_counts(raw, art, ['a', 'b'], ['b', 'a'])
            self.assertEqual([v[0] for v in struct.iter_unpack('<' + m.DTYPES[dtype][0], result)], [3, 4, 1, 2])

    def test_regular_file_boundary_no_symlink_fifo_or_hardlink(self):
        policy, bodies, _ = fixture(); stream = policy['streams'][0]
        for variant in ('link', 'fifo', 'hardlink'):
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / m.official_training_path(stream); path.parent.mkdir(parents=True)
                other = Path(folder) / 'other'; other.write_bytes(bodies[str(m.official_training_path(stream))])
                if variant == 'link': path.symlink_to(other)
                elif variant == 'fifo': os.mkfifo(path)
                else: os.link(other, path)
                with self.assertRaises(m.InputError): m.read_training(folder, stream)

    def test_no_result_from_later_stream_failure(self):
        policy, bodies, _ = fixture()
        with tempfile.TemporaryDirectory() as folder:
            install(folder, policy, bodies)
            last = next(s for s in reversed(policy['streams']) if s['stimulus'] == 'WN')
            path = Path(folder) / m.official_training_path(last)
            path.write_bytes(b'broken')
            with self.assertRaises(m.InputError): run(policy, folder)


if __name__ == '__main__':
    unittest.main()
