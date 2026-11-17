"""Relocated CLI/source checks; generated full support, no authentic observations."""
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scorer
import test_scorer


class DeliveryChecks(unittest.TestCase):
    def test_complete_exact_local_members(self):
        manifest = json.loads((HERE / 'COMPONENT_SOURCE.json').read_bytes())
        declared = {row['path'] for row in manifest['files']}
        self.assertEqual(declared | {'COMPONENT_SOURCE.json'}, {p.name for p in HERE.iterdir()})
        for row in manifest['files']:
            raw = (HERE / row['path']).read_bytes()
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (row['bytes'], row['sha256']))
        self.assertEqual(Path(scorer.__file__).resolve(), HERE / 'scorer.py')
        self.assertIs(test_scorer.s, scorer)

    def test_full_support_cli_from_unrelated_directory(self):
        p, t, r = test_scorer.fixture()
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            hashes = {}
            for name, document in [('prediction', p), ('targets', t), ('reference', r)]:
                raw = (json.dumps(document, separators=(',', ':'), allow_nan=False) + '\n').encode()
                (base / (name + '.json')).write_bytes(raw)
                hashes[name] = hashlib.sha256(raw).hexdigest()
            out = base / 'private.json'
            command = [sys.executable, '-I', '-S', '-B', str(HERE / 'scorer.py'),
                       '--prediction', str(base / 'prediction.json'),
                       '--targets', str(base / 'targets.json'), '--targets-sha256', hashes['targets'],
                       '--comparator', str(base / 'reference.json'), '--comparator-sha256', hashes['reference'],
                       '--output', str(out)]
            result = subprocess.run(command, cwd=base, capture_output=True, timeout=20, umask=0o077)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(result.stdout, b'')
            report = json.loads(out.read_bytes())
            self.assertEqual(report['cohort']['future_state_slots'], 59796)
            self.assertEqual(report['cohort']['eligible_future_state_slots'], 59796)
            self.assertEqual(len(report['cell_support']), 1661)
            self.assertEqual(len(report['mice']), 31)
            self.assertEqual(report['document_sha256'], {'prediction': hashes['prediction'],
                             'targets': hashes['targets'], 'comparator': hashes['reference']})
            self.assertEqual(report['paired_loss_reduction'], 1)
            self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)

    def test_relocated_public_admission_has_no_private_dependency(self):
        p, _, _ = test_scorer.fixture()
        p['cells'].pop()
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); submitted = base / 'incomplete.json'
            submitted.write_text(json.dumps(p))
            original = scorer.read_document
            opened = []
            def observe(path, expected=None):
                opened.append(Path(path))
                if Path(path) != submitted:
                    raise AssertionError('relocated module attempted protected read')
                return original(path, expected)
            with patch.object(scorer, 'read_document', observe), self.assertRaises(scorer.ContractError):
                scorer.main(['--prediction', str(submitted), '--targets', 'absent-targets',
                             '--targets-sha256', 'a' * 64, '--comparator', 'absent-reference',
                             '--comparator-sha256', 'b' * 64, '--output', str(base / 'must-not-exist')])
            self.assertEqual(opened, [submitted])
            self.assertFalse((base / 'must-not-exist').exists())


if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('assertions must remain enabled')
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DeliveryChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.testsRun == 3 and result.wasSuccessful() and not
                     (result.skipped or result.expectedFailures or result.unexpectedSuccesses) else 1)
