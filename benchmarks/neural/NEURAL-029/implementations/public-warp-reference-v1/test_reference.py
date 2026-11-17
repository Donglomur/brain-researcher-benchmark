"""Generated controls only; no authentic neural recording or model is used."""
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reference_program as reference
sys.path.insert(0, str(HERE.parent / 'neural029-programme'))
import core
from source_identity_join import bind_public_identity


def identifier(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


class ReferenceControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='neural029-generated-reference-')
        self.root = Path(self.temp.name).resolve()
        (self.root / 'public').mkdir()
        self.output = self.root / 'submission.json'
        self.doc = {'schema': 'neural029-public-v1', 'time_seconds': reference.GRID, 'pairs': []}
        self.trains = []
        for pair, (trials, cells, queries) in enumerate([(5, 2, 3), (7, 1, 1), (6, 3, 2)]):
            # Trial offsets make ignoring validation or averaging split means fail.
            # Distinct slopes/intercepts expose transposed cells and incorrect warp.
            train = np.array([[[pair + 7 * cell + 3 * trial + (cell + 1) * t * t
                               for t in reference.GRID] for cell in range(cells)]
                              for trial in range(trials)], dtype=np.float64)
            self.trains.append(train)
            split = 4 * trials // 5
            row = {'pair_id': identifier(('pair', pair)),
                   'cell_ids': [identifier(('cell', pair, c)) for c in range(cells)],
                   'query_ids': [identifier(('query', pair, q)) for q in range(queries)],
                   'source_delay_seconds': 1, 'target_delay_seconds': 2,
                   'reward_type': 'DAT' if pair < 2 else 'MFB',
                   'calibration_trials': split, 'validation_trials': trials - split}
            self.doc['pairs'].append(row)
            self.save_arrays(pair, calibration=train[:split], validation=train[split:])
        self.save_manifest()

    def tearDown(self):
        self.temp.cleanup()

    def save_manifest(self):
        (self.root / 'public/MANIFEST.json').write_text(json.dumps(self.doc))

    def save_arrays(self, number, **arrays):
        row = self.doc['pairs'][number]
        path = self.root / 'public' / (row['pair_id'] + '.npz')
        np.savez(path, **arrays)
        raw = path.read_bytes()
        row['file'] = {'path': 'public/' + path.name, 'bytes': len(raw),
                       'sha256': hashlib.sha256(raw).hexdigest()}

    def expected(self, pair):
        mean = self.trains[pair].mean(axis=0)
        # Independent exact half-grid interpolation: below 2s the target tick
        # maps to half a source tick; from 2s onward it maps to tick - 20.
        columns = []
        for tick in range(61):
            if tick < 40:
                lower = tick // 2
                value = mean[:, lower] if tick % 2 == 0 else (mean[:, lower] + mean[:, lower + 1]) / 2
            else:
                value = mean[:, tick - 20]
            columns.append(value)
        return np.stack(columns, axis=1)

    def invoke(self):
        reference.run(self.root, self.output, np)
        return json.loads(self.output.read_text())

    def test_complete_three_pair_grid_and_trial_weighting(self):
        answer = self.invoke()
        values = core.validate(answer, self.doc, np)
        self.assertEqual(len(values), 3)
        for i, row in enumerate(self.doc['pairs']):
            expected = np.repeat(self.expected(i)[None], len(row['query_ids']), axis=0)
            np.testing.assert_allclose(values[row['pair_id']], expected, rtol=0, atol=1e-12)
            self.assertFalse(np.array_equal(expected[0], self.trains[i][:row['calibration_trials']].mean(axis=0)))
        self.assertEqual(self.output.stat().st_nlink, 1)

    def test_actual_scorer_keeps_mouse_macro_and_fixed_warp_comparison(self):
        answer = self.invoke()
        pairs, census, targets = [], [], []
        for i, row in enumerate(self.doc['pairs']):
            si, ti = 2 * i + 1, 2 * i + 2
            for session, delay in [(si, 1), (ti, 2)]:
                census.append({'session_index1': session, 'is_grc': True, 'delay_s': delay,
                               'has_chronic_green': True, 'disposition': 'not_two_second_target'
                               if delay == 1 else 'required_registered_target'})
            cells = len(row['cell_ids'])
            raw = {'pair_index1': i + 1, 'source_session_index1': si, 'target_session_index1': ti,
                   'mouse_id': 'A' if i < 2 else 'B', 'reward_type': row['reward_type'],
                   'source_cells_index1': list(range(1, cells + 1)),
                   'target_cells_index1': list(range(1, cells + 1)),
                   'source_shape': list(self.trains[i].shape),
                   'target_shape': [len(row['query_ids']), cells, 61],
                   'source_time_seconds': reference.GRID, 'target_time_seconds': reference.GRID,
                   'registration_rows_source_target': [[c, c] for c in range(1, cells + 1)]}
            for side in ('source', 'target'):
                raw[side + '_file'] = {'path': f'pair{i + 1:04d}_{side}.f64',
                                       'bytes': 8 * int(np.prod(raw[side + '_shape'])), 'sha256': '0' * 64}
            pairs.append(raw)
            delta, scale = [(1, 4), (3, 9), (5, 25)][i]
            warped = self.expected(i)
            targets.append({'pair_id': row['pair_id'], 'mouse_id': raw['mouse_id'],
                            'target': np.repeat(warped[None] + delta, len(row['query_ids']), axis=0),
                            'baseline': self.trains[i].mean(axis=0), 'fixed_warp_baseline': warped,
                            'training_scale_squared': scale})
        index = {'schema': 'neural029-raw-projection-v2', 'source_record': '21645651',
                 'complete_selected_cohort': True, 'source_part_count': 2, 'source_session_count': 6,
                 'selected_target_session_indices1': [2, 4, 6], 'cohort_dispositions': census,
                 'pairs': pairs, 'scientific_fits': 0, 'scientific_scores': 0}
        payload = {'pairs': targets, 'identity': bind_public_identity(index, self.doc, '0' * 64)}
        grade = core.grade(answer, self.doc, lambda: payload, np)
        self.assertAlmostEqual(grade['primary_nrmse'], 0.875)
        self.assertAlmostEqual(grade['candidate_minus_fixed_warp'], 0.0)
        self.assertEqual(len(grade['pairs']), 3)
        self.assertEqual(len(grade['mice']), 2)

    def test_private_directory_never_needed_or_read(self):
        # A poison private location exists solely to detect accidental access.
        (self.root / 'private').mkdir()
        (self.root / 'private/TARGETS.json').write_text('DO NOT READ')
        seen = []
        original = reference.read_regular
        def observe(path, cap):
            seen.append(Path(path).relative_to(self.root).as_posix())
            return original(path, cap)
        with patch.object(reference, 'read_regular', observe):
            self.invoke()
        self.assertEqual(set(seen), {'public/MANIFEST.json'} | {p['file']['path'] for p in self.doc['pairs']})

    def test_invalid_late_pair_leaves_no_partial_output(self):
        train = self.trains[-1].copy()
        train[0, 0, 0] = np.nan
        split = self.doc['pairs'][-1]['calibration_trials']
        self.save_arrays(2, calibration=train[:split], validation=train[split:])
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'finite full source'):
            self.invoke()
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob('.neural029-*')))

    def test_bad_source_identity_axes_and_split_refuse(self):
        for mutate in [lambda d: d['pairs'][0]['file'].update(path='private/TARGETS.json'),
                       lambda d: d['pairs'][0]['file'].update(sha256='0' * 64),
                       lambda d: d['pairs'][0]['cell_ids'].append(d['pairs'][0]['cell_ids'][0]),
                       lambda d: d['pairs'].append(copy.deepcopy(d['pairs'][0])),
                       lambda d: d['pairs'][0].update(calibration_trials=True),
                       lambda d: d['pairs'][0].update(validation_trials=7)]:
            original = copy.deepcopy(self.doc)
            mutate(self.doc)
            self.save_manifest()
            with self.assertRaises(ValueError):
                self.invoke()
            self.assertFalse(self.output.exists())
            self.doc = original

    def test_extra_npz_member_refuses(self):
        split = self.doc['pairs'][0]['calibration_trials']
        self.save_arrays(0, calibration=self.trains[0][:split], validation=self.trains[0][split:],
                         target=np.zeros((1, 2, 61)))
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'source-only NPZ'):
            self.invoke()
        self.assertFalse(self.output.exists())

    def test_npy_shape_header_refuses_before_array_allocation(self):
        row = self.doc['pairs'][0]
        path = self.root / row['file']['path']
        fake = io.BytesIO()
        np.lib.format.write_array_header_1_0(fake, {'descr': '<f8', 'fortran_order': False,
                                                   'shape': (10**12, 2, 61)})
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('calibration.npy', fake.getvalue())
            real = io.BytesIO()
            np.save(real, self.trains[0][-1:])
            archive.writestr('validation.npy', real.getvalue())
        raw = path.read_bytes()
        row['file'].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        self.save_manifest()
        with patch.object(np, 'load', side_effect=AssertionError('array allocation reached')):
            with self.assertRaisesRegex(ValueError, 'extent before allocation'):
                self.invoke()
        self.assertFalse(self.output.exists())

    def test_cap_failure_and_existing_output_are_preserved(self):
        with patch.object(reference, 'SUBMISSION_CAP', 200):
            with self.assertRaisesRegex(ValueError, 'no truncation'):
                self.invoke()
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob('.neural029-*')))
        self.output.write_text('previous')
        with self.assertRaisesRegex(ValueError, 'fresh ordinary output'):
            self.invoke()
        self.assertEqual(self.output.read_text(), 'previous')

    def test_standalone_participant_abi(self):
        # Only this one source file is mounted by the existing participant ABI.
        isolated = self.root / 'program'
        isolated.mkdir()
        program = isolated / 'candidate.py'
        program.write_bytes((HERE / 'reference_program.py').read_bytes())
        result = subprocess.run([sys.executable, '-I', '-B', str(program), '--input', str(self.root),
                                 '--output', str(self.output)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        core.validate(json.loads(self.output.read_text()), self.doc, np)


if __name__ == '__main__':
    unittest.main(verbosity=2)
