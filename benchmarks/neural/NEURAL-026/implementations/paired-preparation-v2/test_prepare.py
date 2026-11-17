"""Generated software controls; no authentic neural data or model fitting."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('neural026_paired_preparation', HERE / 'prepare.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def metadata_fixture(api):
    result = {}
    for asset in api.inventory:
        cid = p.session_id(asset)
        start = 1 if asset['area'] == 'M1' else 101
        target = [1] * 11 + [2] * 13 if asset['area'] == 'M1' else [1] * 13 + [2] * 11
        result[cid] = dict(schema='neural026_aligned_v1', session=cid,
            source_asset=copy.deepcopy(asset), source_sha256='a' * 64,
            aligned=dict(path=cid + '.npz', bytes=1, sha256='b' * 64),
            trial_id=list(range(start, start + 24)), target=target)
    return result


def generated_session(folder, metadata, cid, api, *, wrong_targets=False):
    row = metadata[cid]
    ids = np.asarray(row['trial_id'], dtype=np.int64)
    targets = np.asarray(row['target'], dtype=np.int64)
    if wrong_targets:
        targets = targets.copy()
        targets[0], targets[-1] = targets[-1], targets[0]
    values = dict(trial_id=ids, target=targets)
    for name, width in (('x', 128), ('z', 141), ('y', 24)):
        values[name] = np.broadcast_to(ids[:, None, None]
            + np.arange(51)[None, :, None] / 100.
            + np.arange(width)[None, None, :] / 1000., (len(ids), 51, width)).copy()
    path = folder / row['aligned']['path']
    np.savez(path, **values)
    row['aligned'] = api.common.pin(path)
    return values


def write_metadata(folder, metadata, api):
    rows = {}
    for cid, row in metadata.items():
        path = folder / (cid + '.json')
        path.write_text(json.dumps(row))
        rows[cid] = api.common.pin(path)
    binding = folder / 'metadata-binding.json'
    binding.write_text(json.dumps(dict(schema='neural026_session_metadata_binding_v1', sessions=rows)))
    return binding, hashlib.sha256(binding.read_bytes()).hexdigest()


class PairedPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = p.backend()

    def setUp(self):
        self.metadata = metadata_fixture(self.api)

    def test_chronological_first_min_with_unpaired_reach_ids(self):
        design = p.matched_design(self.metadata, self.api)
        self.assertEqual(len(design['cases']), 50)
        m1, s1 = design['cases'][0], design['cases'][5]
        self.assertEqual(m1['matched_counts'], {'1': 11, '2': 11})
        self.assertEqual(m1['query_id'], [1, 6, 11, 12, 17, 22])
        self.assertEqual(s1['query_id'], [101, 106, 111, 114, 119, 124])
        self.assertEqual(sorted(t for c in design['cases'][:5] for t in c['query_id']), list(range(1, 23)))
        self.assertEqual(sorted(t for c in design['cases'][5:10] for t in c['query_id']),
                         list(range(101, 112)) + list(range(114, 125)))

    def test_legacy_accepted_fold_permutation_is_rejected(self):
        design = p.matched_design(self.metadata, self.api)
        for name in ('train_id', 'query_id'):
            design['cases'][0][name], design['cases'][1][name] = (
                design['cases'][1][name], design['cases'][0][name])
        self.api.p.validate_design(design)  # Counterexample to predecessor admission.
        with self.assertRaisesRegex(ValueError, 'roster-derived'):
            p.validate_design(design, self.metadata, self.api)

    def test_legacy_accepted_false_target_counts_are_rejected(self):
        design = p.matched_design(self.metadata, self.api)
        for case in design['cases'][:10]:
            case['matched_counts'] = {'1': 12, '2': 10}
        self.api.p.validate_design(design)
        with self.assertRaisesRegex(ValueError, 'roster-derived'):
            p.validate_design(design, self.metadata, self.api)

    def test_legacy_accepted_late_trial_substitution_is_rejected(self):
        design = p.matched_design(self.metadata, self.api)
        for case in design['cases'][:5]:
            for key in ('train_id', 'query_id'):
                case[key] = sorted(24 if t == 22 else t for t in case[key])
        self.api.p.validate_design(design)
        with self.assertRaisesRegex(ValueError, 'roster-derived'):
            p.validate_design(design, self.metadata, self.api)

    def test_wrong_area_array_pin_cannot_follow_a_valid_design(self):
        design = p.matched_design(self.metadata, self.api)
        for case in design['cases'][:5]:
            case['session'] = design['cases'][5]['session']
            case['aligned'] = copy.deepcopy(design['cases'][5]['aligned'])
        self.api.p.validate_design(design)
        with self.assertRaisesRegex(ValueError, 'roster-derived'):
            p.validate_design(design, self.metadata, self.api)

    def test_exact_ten_source_sessions_and_minimum_target_support(self):
        for mutate in ('missing', 'source', 'bool_id', 'target_shortfall'):
            metadata = copy.deepcopy(self.metadata)
            cid = next(iter(metadata))
            if mutate == 'missing':
                metadata.pop(cid)
            elif mutate == 'source':
                metadata[cid]['source_asset']['area'] = 'S1'
            elif mutate == 'bool_id':
                metadata[cid]['trial_id'][0] = True
            else:
                metadata[cid]['target'] = [1] * 9 + [2] * 15
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                p.matched_design(metadata, self.api)

    def test_stage_preserves_public_abi_and_protected_target_order(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            sessions = root / 'sessions'
            sessions.mkdir()
            cid = next(iter(self.metadata))
            values = generated_session(sessions, self.metadata, cid, self.api)
            design = p.matched_design(self.metadata, self.api)
            public, private = root / 'public', root / 'private'
            p.stage_case(design, self.metadata, sessions, design['cases'][0]['case_id'],
                         public, private, self.api)
            with np.load(public / 'input.npz', allow_pickle=False) as packet:
                self.assertNotIn('query_y', packet.files)
                self.api.p.validate_packet(dict(packet))
                expected = np.array(design['cases'][0]['query_id'])
                np.testing.assert_array_equal(packet['query_id'], expected)
                np.testing.assert_array_equal(packet['query_x'], values['x'][expected - 1])
                np.testing.assert_array_equal(packet['query_target'], values['target'][expected - 1])
            with np.load(private / 'target.npz', allow_pickle=False) as target:
                np.testing.assert_array_equal(target['trial_id'], expected)
                np.testing.assert_array_equal(target['y'], values['y'][expected - 1])

    def test_rebound_arrays_with_wrong_targets_refused_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            cid = next(iter(self.metadata))
            generated_session(root, self.metadata, cid, self.api, wrong_targets=True)
            design = p.matched_design(self.metadata, self.api)
            public, private = root / 'public', root / 'private'
            with self.assertRaisesRegex(ValueError, 'metadata trial/target roster'):
                p.stage_case(design, self.metadata, root, design['cases'][0]['case_id'],
                             public, private, self.api)
            self.assertFalse(public.exists())
            self.assertFalse(private.exists())

    def test_metadata_only_cli_and_independent_pin_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            binding, sha = write_metadata(root, self.metadata, self.api)
            args = ['design', '--sessions', str(root), '--metadata-binding', str(binding),
                    '--metadata-binding-sha256', sha]
            self.assertEqual(p.main(args + ['--output', str(root / 'design.json')]), 0)
            # No aligned NPZ exists; the design step cannot inspect joint targets.
            self.assertEqual(len(json.loads((root / 'design.json').read_text())['cases']), 50)
            last = sorted(self.metadata)[-1]
            path = root / (last + '.json')
            path.write_text(path.read_text() + ' ')
            with self.assertRaisesRegex(ValueError, 'Pinned file bytes'):
                p.main(args + ['--output', str(root / 'tampered.json')])
            self.assertFalse((root / 'tampered.json').exists())
            with self.assertRaisesRegex(ValueError, 'checksum'):
                p.main(args[:-1] + ['0' * 64, '--output', str(root / 'bad-binding.json')])

    def test_stage_cli_design_pin_and_selected_session_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            cid = next(iter(self.metadata))
            generated_session(root, self.metadata, cid, self.api)
            binding, sha = write_metadata(root, self.metadata, self.api)
            design = p.matched_design(self.metadata, self.api)
            path = root / 'design.json'
            path.write_text(json.dumps(design))
            args = ['stage-case', '--sessions', str(root), '--metadata-binding', str(binding),
                    '--metadata-binding-sha256', sha, '--design', str(path), '--design-sha256',
                    hashlib.sha256(path.read_bytes()).hexdigest(), '--case-id', design['cases'][0]['case_id'],
                    '--public-output', str(root / 'public'), '--private-output', str(root / 'private')]
            with (root / self.metadata[cid]['aligned']['path']).open('ab') as stream:
                stream.write(b'changed')
            with self.assertRaisesRegex(ValueError, 'Pinned file bytes'):
                p.main(args)
            self.assertFalse((root / 'public').exists())
            path.write_text(path.read_text() + ' ')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                p.main(args)


if __name__ == '__main__':
    unittest.main(verbosity=2)
