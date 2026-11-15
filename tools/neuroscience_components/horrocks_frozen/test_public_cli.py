"""Invented controls for the public single-triple CLI only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).absolute().parent
spec = importlib.util.spec_from_file_location('invented_controls', HERE / 'test_transport.py')
controls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controls)


class PublicCLI(unittest.TestCase):
    def command(self, root):
        args = [sys.executable, '-I', '-S', '-B', str(HERE / 'convert_model.py')]
        for role, body in zip(('mask', 'beta', 'intercept'), controls.triples()):
            path = root / (role + '.npy')
            path.write_bytes(body)
            args.extend(['--' + role, str(path), '--' + role + '-sha256',
                         hashlib.sha256(body).hexdigest()])
        return args + ['--out', str(root / 'model.json')]

    def test_new_cli_pinned_triplet_and_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            run = subprocess.run(self.command(root), capture_output=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stderr.decode())
            body = (root / 'model.json').read_bytes()
            receipt = json.loads(run.stdout)
            self.assertEqual(receipt['sha256'], hashlib.sha256(body).hexdigest())
            self.assertEqual(receipt['bytes'], len(body))
            self.assertEqual(receipt['fit_calls'], 0)
            model = controls.p.strict_json(body)
            self.assertEqual(model['feature_count'], 3)
            self.assertEqual(model['selected_indices'], [0, 2])
            self.assertEqual(model['beta'], [[0., 1., 2., 3., 4., 5.],
                                            [6., 7., 8., 9., 10., 11.]])
            self.assertEqual(model['intercept'], [0.] * 6)
            self.assertNotIn(str(root).encode(), body)

    def test_new_cli_rejects_digest_mismatch_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); args = self.command(root)
            args[args.index('--mask-sha256') + 1] = '0' * 64
            run = subprocess.run(args, capture_output=True, timeout=10)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn(b'complete byte identity', run.stderr)
            self.assertFalse((root / 'model.json').exists())

    def test_new_cli_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); args = self.command(root)
            output = root / 'model.json'; output.write_bytes(b'existing')
            run = subprocess.run(args, capture_output=True, timeout=10)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn(b'new output', run.stderr)
            self.assertEqual(output.read_bytes(), b'existing')


if __name__ == '__main__':
    unittest.main(verbosity=2)
