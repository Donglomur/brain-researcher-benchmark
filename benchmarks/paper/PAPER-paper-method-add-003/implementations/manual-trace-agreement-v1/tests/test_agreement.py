import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('agreement', ROOT / 'agreement.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def packets():
    reference = {
        'schema': a.REFERENCE_SCHEMA, 'task_id': a.TASK_ID,
        'alignment_recipe_sha256': 'a' * 64, 'author_execution_sha256': 'b' * 64,
        'records': [{
            'patient': patient, 'recording_sha256': str(i + 1) * 64,
            'times_s': [0.0, 0.5, 1.0, 1.5],
            'manual_displacement_um': [-3, -1, 1, 3],
            'author_displacement_um': [-1, 1, 1, -1],
        } for i, patient in enumerate(a.PATIENTS)],
    }
    candidate = {
        'schema': a.CANDIDATE_SCHEMA, 'task_id': a.TASK_ID,
        'support_sha256': a.support_sha256(reference),
        'records': [{
            'patient': row['patient'], 'recording_sha256': row['recording_sha256'],
            'times_s': row['times_s'].copy(), 'displacement_um': [-30, -10, 10, 30],
        } for row in reference['records']],
    }
    return reference, candidate


class AgreementTests(unittest.TestCase):
    def test_analytic_r_and_no_cohort_scalar(self):
        source, candidate = packets()
        result = a.score_packets(source, candidate)
        self.assertEqual(result['patient_order'], list(a.PATIENTS))
        self.assertEqual(len(result['patients']), 3)
        for row in result['patients']:
            self.assertAlmostEqual(row['author_r'], 0.0)
            self.assertAlmostEqual(row['candidate_r'], 1.0)
            self.assertAlmostEqual(row['delta_r'], 1.0)
        self.assertNotIn('cohort_mean', result)
        self.assertNotIn('paper_win', result)

    def test_affine_invariance_does_not_imply_physical_accuracy(self):
        self.assertAlmostEqual(a.pearson_r([1, 2, 5, 9], [103, 106, 115, 127]), 1)
        self.assertAlmostEqual(a.pearson_r([1, 2, 5, 9], [-3, -6, -15, -27]), -1)
        self.assertAlmostEqual(a.pearson_r([-1e308, 0, 1e308], [-1e308, 0, 1e308]), 1)

    def test_large_offset_preserves_representable_variation(self):
        # Independent review's exact-rational counterexamples. Scaling these
        # coordinates before subtracting an offset changed the Pearson value.
        x = [1e16 + i * 2 for i in range(4)]
        self.assertAlmostEqual(a.pearson_r(x, [0, 1, 2, 3]), 1, places=14)
        self.assertAlmostEqual(a.pearson_r(x, [2, -1, 0, 4]), 7 / math.sqrt(295), places=14)

    def test_constant_candidate_is_retained_as_undefined(self):
        source, candidate = packets()
        candidate['records'][1]['displacement_um'] = [2, 2, 2, 2]
        result = a.score_packets(source, candidate)
        self.assertEqual(len(result['patients']), 3)
        self.assertIsNone(result['patients'][1]['candidate_r'])
        self.assertIsNone(result['patients'][1]['delta_r'])
        self.assertIsNone(a.pearson_r([0, 0, 0], [1, 2, 3]))

    def test_no_sample_deletion_or_nonfinite_scores(self):
        source, candidate = packets()
        for replacement in ([1, 2, 3], [1, 2, float('nan'), 4], [1, 2, True, 4]):
            changed = copy.deepcopy(candidate)
            changed['records'][0]['displacement_um'] = replacement
            with self.assertRaises(ValueError):
                a.score_packets(source, changed)

    def test_no_automatic_alignment_or_recording_substitution(self):
        source, candidate = packets()
        changed = copy.deepcopy(candidate)
        changed['records'][0]['times_s'] = [0.5, 1, 1.5, 2]
        with self.assertRaisesRegex(ValueError, 'time support'):
            a.score_packets(source, changed)
        changed = copy.deepcopy(candidate)
        changed['records'][0]['recording_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'recording identity'):
            a.score_packets(source, changed)

    def test_full_cohort_and_unique_members_required(self):
        source, candidate = packets()
        candidate['records'].pop()
        with self.assertRaisesRegex(ValueError, 'Full original'):
            a.score_packets(source, candidate)
        source, candidate = packets()
        candidate['records'][2] = candidate['records'][1]
        with self.assertRaisesRegex(ValueError, 'duplicate patient'):
            a.score_packets(source, candidate)

    def test_canonical_order_and_target_free_support(self):
        source, candidate = packets()
        source['records'].reverse()
        candidate['records'].reverse()
        self.assertEqual(a.score_packets(source, candidate)['patient_order'], list(a.PATIENTS))
        support = a.public_support(source)
        self.assertNotIn('manual_displacement_um', json.dumps(support))
        self.assertNotIn('author_displacement_um', json.dumps(support))
        original_hash = a.support_sha256(source)
        source['records'][0]['manual_displacement_um'][0] = 200
        self.assertEqual(a.support_sha256(source), original_hash)
        source['alignment_recipe_sha256'] = 'c' * 64
        self.assertNotEqual(a.support_sha256(source), original_hash)
        with self.assertRaisesRegex(ValueError, 'frozen support'):
            a.score_packets(source, candidate)

    def test_cli_frozen_reference_and_json_output(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source, candidate = packets()
            ref, cand, out = [folder / name for name in ('reference.json', 'candidate.json', 'result.json')]
            ref.write_text(json.dumps(source))
            cand.write_text(json.dumps(candidate))
            digest = hashlib.sha256(ref.read_bytes()).hexdigest()
            command = [sys.executable, '-I', '-B', str(ROOT / 'agreement.py'),
                       str(ref), str(cand), str(out), '--reference-sha256', digest]
            run = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(out.read_text())
            self.assertEqual(result['reference_packet_sha256'], digest)
            ref.write_text(json.dumps(source) + '\n')
            run = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn('reference packet hash mismatch', run.stderr)

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'duplicate.json'
            path.write_text('{"patient": "Pt01", "patient": "Pt02"}')
            with self.assertRaisesRegex(ValueError, 'Duplicate JSON key'):
                a._load(path)


if __name__ == '__main__':
    unittest.main()
