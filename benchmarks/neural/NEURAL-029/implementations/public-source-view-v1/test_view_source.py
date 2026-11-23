"""Generated public-only renderer controls; no authentic neural data."""
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
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import view_source as view


def identifier(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


class SourceViewControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='neural029-source-view-generated-')
        self.root = Path(self.temp.name).resolve()
        (self.root / 'public').mkdir()
        self.ref = view.reference()
        self.train = np.array([[[100 * trial + 10 * cell + tick for tick in range(61)]
                               for cell in range(2)] for trial in range(5)], dtype=np.float64)
        self.row = {
            'pair_id': identifier('pair'), 'cell_ids': [identifier('cell0'), identifier('cell1')],
            'query_ids': [identifier('query0'), identifier('query1')],
            'source_delay_seconds': 1, 'target_delay_seconds': 2, 'reward_type': 'DAT',
            'calibration_trials': 4, 'validation_trials': 1,
        }
        self.document = {'schema': 'neural029-public-v1', 'time_seconds': self.ref.GRID,
                         'pairs': [self.row]}
        self.save_arrays()
        self.save_manifest()

    def tearDown(self):
        self.temp.cleanup()

    def save_arrays(self, **extra):
        path = self.root / 'public' / (self.row['pair_id'] + '.npz')
        np.savez(path, calibration=self.train[:4], validation=self.train[4:], **extra)
        raw = path.read_bytes()
        self.row['file'] = {'path': 'public/' + path.name, 'bytes': len(raw),
                            'sha256': hashlib.sha256(raw).hexdigest()}

    def save_manifest(self):
        (self.root / 'public/MANIFEST.json').write_text(json.dumps(self.document))

    def render(self, **kwargs):
        args = {'pair_id': self.row['pair_id'], 'split': 'validation',
                'trial_index1': 1, 'cell_index1': 2}
        args.update(kwargs)
        return view.render(self.root, np=np, ref=self.ref, **args)

    def parsed(self, svg):
        tree = ET.fromstring(svg)
        namespace = {'s': 'http://www.w3.org/2000/svg'}
        metadata = json.loads(tree.find('s:metadata', namespace).text)
        trace = tree.find('.//s:polyline', namespace)
        points = [tuple(float(x) for x in point.split(',')) for point in trace.attrib['points'].split()]
        return tree, metadata, points

    def test_complete_exact_grid_and_source_trial_cell_selection(self):
        tree, metadata, points = self.parsed(self.render())
        self.assertEqual(metadata['source_trial_index1'], 5)
        self.assertEqual(metadata['cell_id'], self.row['cell_ids'][1])
        self.assertEqual(metadata['source_split'], 'validation')
        self.assertEqual(metadata['display_min'], 410)
        self.assertEqual(metadata['display_max'], 470)
        self.assertEqual(metadata['time_seconds'], [i / 20 for i in range(61)])
        self.assertEqual(len(points), 61)
        for i, (x, y) in enumerate(points):
            self.assertAlmostEqual(x, 100 + 16 * i, places=6)
            self.assertAlmostEqual(y, 525 - 6 * i, places=6)
        self.assertIn('Source delay: 1 s', ''.join(tree.itertext()))
        self.assertIn('source-order trial 5', ''.join(tree.itertext()))
        self.assertIn('Target delay: 2 s; target responses are not displayed or read.', ''.join(tree.itertext()))

    def test_only_public_manifest_and_selected_pair_are_opened(self):
        (self.root / 'private').mkdir()
        (self.root / 'private/TARGETS.json').write_text('FORBIDDEN')
        seen = []
        original = self.ref.read_regular
        def observe(path, cap):
            relative = Path(path).relative_to(self.root).as_posix()
            self.assertTrue(relative.startswith('public/'))
            seen.append(relative)
            return original(path, cap)
        with patch.object(self.ref, 'read_regular', observe):
            _, metadata, _ = self.parsed(self.render(split='calibration', trial_index1=3, cell_index1=1))
        self.assertEqual(seen, ['public/MANIFEST.json', self.row['file']['path']])
        self.assertEqual(metadata['source_trial_index1'], 3)
        self.assertEqual(metadata['display_min'], 200)
        self.assertFalse(metadata['target_values_read'])
        self.assertFalse(metadata['provider_delivery_qualified'])

    def test_invalid_actions_refuse_before_source_array_read(self):
        invalid = [{'pair_id': 'unknown'}, {'split': 'target'}, {'trial_index1': 0},
                   {'trial_index1': True}, {'trial_index1': 2}, {'cell_index1': 0},
                   {'cell_index1': 3}, {'cell_index1': False}]
        for change in invalid:
            with self.subTest(change=change), patch.object(view, '_trace', side_effect=AssertionError('array read')):
                with self.assertRaises(ValueError):
                    self.render(**change)

    def test_incomplete_or_nonfinite_selected_pair_refuses(self):
        self.train[0, 0, 0] = np.nan  # Even an unviewed source trial in this pair is checked.
        self.save_arrays(); self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'finite complete'):
            self.render()
        self.train[0, 0, 0] = 0
        self.save_arrays(target=np.zeros((2, 2, 61))); self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'source-only NPZ'):
            self.render()

    def test_oversized_npy_header_refuses_before_allocation(self):
        path = self.root / self.row['file']['path']
        fake = io.BytesIO()
        np.lib.format.write_array_header_1_0(fake, {'descr': '<f8', 'fortran_order': False,
                                                   'shape': (10**12, 2, 61)})
        real = io.BytesIO(); np.save(real, self.train[4:])
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('calibration.npy', fake.getvalue())
            archive.writestr('validation.npy', real.getvalue())
        raw = path.read_bytes()
        self.row['file'].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        self.save_manifest()
        with patch.object(np, 'load', side_effect=AssertionError('array allocation')):
            with self.assertRaisesRegex(ValueError, 'extent before allocation'):
                self.render()

    def test_constant_and_extreme_finite_traces_have_finite_display(self):
        for values in (np.full(61, -2.0), np.linspace(-1, 1, 61) * 1e308):
            self.train[:] = values
            self.save_arrays(); self.save_manifest()
            _, metadata, points = self.parsed(self.render())
            self.assertTrue(np.isfinite(np.asarray(points)).all())
            self.assertEqual(metadata['display_min'], float(values.min()))
            self.assertEqual(metadata['display_max'], float(values.max()))
            if values.min() == values.max():
                self.assertTrue(all(y == 345 for _, y in points))

    def test_cli_creates_view_and_does_not_overwrite(self):
        output = self.root / 'view.svg'
        command = [sys.executable, '-I', '-B', str(HERE / 'view_source.py'), '--input', str(self.root),
                   '--pair-id', self.row['pair_id'], '--split', 'validation', '--trial-index1', '1',
                   '--cell-index1', '2', '--output', str(output)]
        first = subprocess.run(command, capture_output=True, text=True, timeout=15)
        self.assertEqual(first.returncode, 0, first.stderr)
        raw = output.read_bytes()
        self.parsed(raw)
        second = subprocess.run(command, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual(output.read_bytes(), raw)

    def test_small_amplitude_range_remains_visibly_distinct(self):
        self.train[:] = np.linspace(1.00001, 1.00002, 61)
        self.save_arrays(); self.save_manifest()
        tree, metadata, _ = self.parsed(self.render())
        self.assertIn('Displayed amplitude range: min 1.00001; max 1.00002', ''.join(tree.itertext()))
        self.assertNotEqual(metadata['display_min'], metadata['display_max'])

    def test_dependency_mutation_is_refused(self):
        altered = self.root / 'reference.py'
        altered.write_bytes(view.REFERENCE_PATH.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'reference source changed'):
            view.reference(altered)


if __name__ == '__main__':
    unittest.main(verbosity=2)
