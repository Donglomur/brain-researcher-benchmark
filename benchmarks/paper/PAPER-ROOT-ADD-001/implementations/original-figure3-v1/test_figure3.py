"""Generated controls only; no authentic neural values or model execution."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np

from figure3 import compare, summarize
from source_panel import SESSION_UNITS, SOURCE_FILES, load_panel, shapes


def fixture():
    return {session: {field: np.zeros(shape, dtype=np.float64)
                      for field, shape in shapes(session).items()}
            for session in SESSION_UNITS}


def write_panel(root, panel):
    for session, fields in panel.items():
        (root / session).mkdir()
        for field, array in fields.items():
            np.save(root / session / SOURCE_FILES[field], array, allow_pickle=False)


class Figure3Tests(unittest.TestCase):
    def test_fixed_source_selection_not_maximum(self):
        panel = fixture()
        expected = []
        for i, session in enumerate(SESSION_UNITS):
            a = panel[session]['population']
            a[:] = .8
            a[17:20, 5] = [.03+i/1000, .05+i/1000, .07+i/1000]
            expected.append(sum([.03+i/1000, .05+i/1000, .07+i/1000])/3)
        report = summarize(panel)
        np.testing.assert_allclose(report['figure3b']['population']['session_values'], expected)
        self.assertAlmostEqual(report['figure3b']['population']['mean'], sum(expected)/14)
        self.assertEqual(len(report['source_permutation_observations']['population']), 42)

    def test_session_weighting_and_companions(self):
        panel = fixture()
        panel['p4_1']['population'][17:20, 5] = 1
        for session in SESSION_UNITS:
            panel[session]['syn'][:, 0] = [-.3, .0, .3]
            panel[session]['time_shuffle'][17:20, 5] = -.2
            panel[session]['ngram3'][4] = .5
            panel[session]['ngram3'][12] = .4
        report = summarize(panel)
        self.assertAlmostEqual(report['figure3b']['population']['mean'], 1/14)
        self.assertNotAlmostEqual(report['figure3b']['population']['mean'], 1/8)
        self.assertAlmostEqual(report['figure3b']['syn']['mean'], 0)
        self.assertAlmostEqual(report['figure3b']['time_shuffle']['mean'], -.2)
        self.assertEqual(report['figure3c']['ngram3']['source_selected_layer_index'], 4)

    def test_undefined_primary_propagates_and_unit_denominator_visible(self):
        panel = fixture()
        panel['p1_1']['population'][18, 5] = np.nan
        panel['p1_2']['unit'][0, 0, 0] = np.nan
        report = summarize(panel)
        self.assertIsNone(report['figure3b']['population']['mean'])
        self.assertEqual(report['figure3b']['population']['defined_sessions'], 13)
        self.assertEqual(report['figure3e']['unit_defined_count_per_lag_layer'][0][0], 566)
        self.assertEqual(report['figure3e']['unit_defined_count_per_lag_layer'][1][0], 567)
        self.assertIsNone(report['figure3e']['unit_normalized'][0][0])
        json.dumps(report, allow_nan=False)

    def test_full_coverage_is_required(self):
        panel = fixture()
        del panel['p8_2']['sentence_swap']
        with self.assertRaisesRegex(ValueError, 'sixteen'):
            summarize(panel)
        panel = fixture()
        panel['p8_2']['unit'] = panel['p8_2']['unit'][:-1]
        with self.assertRaisesRegex(ValueError, 'shape'):
            summarize(panel)
        with self.assertRaisesRegex(ValueError, 'roster'):
            summarize(dict(reversed(list(fixture().items()))))

    def test_invalid_correlations_rejected(self):
        for value in (np.inf, -np.inf, 1.001):
            panel = fixture()
            panel['p2_1']['random_token'][2] = value
            with self.assertRaisesRegex(ValueError, 'invalid correlation'):
                summarize(panel)

    def test_reproduction_and_improvement_are_separate(self):
        reference, candidate = fixture(), fixture()
        for session in SESSION_UNITS:
            candidate[session]['population'][17:20, 5] = .02
        candidate['p8_2']['unit'][3, 2, 1] = .4
        report = compare(candidate, reference)
        self.assertAlmostEqual(report['improvement']['figure3b_equal_session_mean_delta'], .02)
        self.assertEqual(len(report['improvement']['participant_clusters']), 8)
        self.assertEqual(len(report['improvement']['participant_clusters']['p1']), 2)
        self.assertEqual(len(report['improvement']['participant_clusters']['p4']), 1)
        self.assertEqual(report['reproduction']['full_panel_discrepancies']['p8_2']['unit']['max_absolute_error_on_defined_pairs'], .4)
        self.assertIsNone(report['improvement']['scientific_win'])
        candidate['p1_1']['unit'][0, 0, 0] = np.nan
        report = compare(candidate, reference)
        self.assertFalse(report['reproduction']['full_panel_discrepancies']['p1_1']['unit']['same_defined_support'])

    def test_full_original_tree_roundtrip_and_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            panel = fixture()
            panel['p1_1']['population'] = np.asfortranarray(panel['p1_1']['population'])
            panel['p3_2']['syn'] = np.asarray([[.1], [.2], [.3]], dtype='>f8')
            write_panel(root, panel)
            loaded, receipts = load_panel(root)
            self.assertEqual(len(receipts), 224)
            np.testing.assert_equal(loaded['p3_2']['syn'], panel['p3_2']['syn'])
            result = root / 'report.json'
            subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('figure3.py')),
                            '--result-root', str(root), '--reference-root', str(root),
                            '--output', str(result)], check=True, capture_output=True)
            report = json.loads(result.read_text())
            self.assertEqual(report['improvement']['figure3b_equal_session_mean_delta'], 0)
            self.assertEqual(len(report['input_receipts']), 224)
            self.assertEqual(len(report['reference_input_receipts']), 224)

    def test_wrong_npy_header_and_trailing_payload_fail_before_allocation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_panel(root, fixture())
            path = root / 'p1_1' / SOURCE_FILES['population']
            original = path.read_bytes()
            stream = io.BytesIO()
            np.lib.format.write_array_header_1_0(stream, {
                'descr': '<f8', 'fortran_order': False, 'shape': (10**12,)})
            path.write_bytes(stream.getvalue())
            with self.assertRaisesRegex(ValueError, 'geometry'):
                load_panel(root)
            path.write_bytes(original + b'x')
            with self.assertRaisesRegex(ValueError, 'trailing'):
                load_panel(root)
            path.unlink()
            path.symlink_to(root / 'p1_2' / SOURCE_FILES['population'])
            with self.assertRaisesRegex(ValueError, 'ordinary'):
                load_panel(root)


if __name__ == '__main__':
    unittest.main(verbosity=2)
