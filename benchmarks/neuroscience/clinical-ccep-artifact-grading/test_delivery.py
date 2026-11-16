"""Primary-only public relocation checks using invented complete patient fixtures."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import score
import test_score


class DeliveryChecks(unittest.TestCase):
    def test_complete_exact_local_members(self):
        manifest = json.loads((HERE / 'COMPONENT_SOURCE.json').read_bytes())
        self.assertEqual({x['path'] for x in manifest['files']} | {'COMPONENT_SOURCE.json'},
                         {p.name for p in HERE.iterdir()})
        for row in manifest['files']:
            raw = (HERE / row['path']).read_bytes()
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (row['bytes'], row['sha256']))
        self.assertEqual(Path(score.__file__).resolve(), HERE / 'score.py')
        self.assertIs(test_score.score, score)

    def test_primary_cli_from_unrelated_directory(self):
        p, s, t = test_score.fixture()
        policy_hash = hashlib.sha256(test_score.encoded(p)).hexdigest()
        s['policy_sha256'] = policy_hash
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            for name, doc in [('policy', p), ('submission', s), ('targets', t)]:
                (base / (name + '.json')).write_bytes(test_score.encoded(doc))
            result = subprocess.run([sys.executable, '-I', '-S', '-B', str(HERE / 'score.py'),
                '--policy', str(base / 'policy.json'), '--expected-policy-sha256', policy_hash,
                '--submission', str(base / 'submission.json'), '--targets', str(base / 'targets.json')],
                cwd=base, capture_output=True, timeout=10, umask=0o077)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            report = json.loads(result.stdout)
            self.assertEqual((report['patients'], report['blocks']), (5, 15))
            self.assertEqual(report['condition'], 'original_full_scope')
            self.assertEqual([x['blocks'] for x in report['patient_folds']], [1, 2, 3, 4, 5])
            self.assertAlmostEqual(report['primary_patient_macro_log_loss'],
                                   math.fsum(-math.log(.1 * (i + 1)) for i in range(5)) / 5)
            self.assertFalse(report['scientifically_qualified'])

    def test_transformed_condition_refuses_before_targets(self):
        p, s, _ = test_score.fixture()
        policy_hash = hashlib.sha256(test_score.encoded(p)).hexdigest()
        s['policy_sha256'] = policy_hash
        s['condition'] = 'paired_null'
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / 'policy.json').write_bytes(test_score.encoded(p))
            (base / 'submission.json').write_bytes(test_score.encoded(s))
            original = score.read_document; opened = []
            def observe(path, expected=None):
                opened.append(Path(path).name)
                if Path(path).name == 'targets.json':
                    raise AssertionError('primary-only projection read targets for transformed arm')
                return original(path, expected)
            with patch.object(score, 'read_document', observe), self.assertRaises(score.Invalid):
                score.score_files(base / 'policy.json', policy_hash,
                                  base / 'submission.json', base / 'targets.json')
            self.assertEqual(opened, ['policy.json', 'submission.json'])


if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('assertions must remain enabled')
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DeliveryChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.testsRun == 3 and result.wasSuccessful() and not
                     (result.skipped or result.expectedFailures or result.unexpectedSuccesses) else 1)
