"""Tiny generated ZIP controls for source-only inspection. No downloaded payloads."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

SPEC = importlib.util.spec_from_file_location('inspect_rnn', Path(__file__).with_name('inspect_source.py'))
inspector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inspector)


class InspectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'generated.zip'
        self.members = {
            'sequenceFiltering/code/RNN_seqmodel.ipynb': json.dumps({'cells': [
                {'cell_type': 'markdown', 'source': ['# prose']},
                {'cell_type': 'code', 'source': ['raise RuntimeError("must not execute")'],
                 'outputs': [{'text': ['private-like generated output must not be emitted']}]}]}).encode(),
            'sequenceFiltering/src/modules_simpleRNN.py': b'def loss_mse(a, b, c):\n    raise RuntimeError("must not execute")\n',
        }
        self.pins = {name: {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                     for name, raw in self.members.items()}

    def write(self, *, omit=None, duplicate=None, changed=None):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(self.path, 'w') as out:
                for name, raw in self.members.items():
                    if name != omit:
                        out.writestr(name, changed if changed is not None and name.endswith('.py') else raw)
                    if name == duplicate:
                        out.writestr(name, raw)
                # Deliberately invalid data member; source inspector must never decode it.
                out.writestr('sequenceFiltering/data/figure4_data.npz', b'not scientific data')

    def test_only_source_is_read_without_execution_or_outputs(self):
        self.write()
        with patch.object(inspector, 'PINS', self.pins):
            result = inspector.inspect(self.path)
        self.assertFalse(result['source_execution'])
        self.assertEqual(len(result['code_cells']), 1)
        self.assertEqual(result['code_cells'][0]['index_zero_based'], 1)
        self.assertNotIn('private-like', json.dumps(result))
        self.assertIn('must not execute', result['loss_function']['source'])

    def test_missing_duplicate_size_and_digest_mismatch_rejected(self):
        module = 'sequenceFiltering/src/modules_simpleRNN.py'
        for options in ({'omit': module}, {'duplicate': module}, {'changed': b'short'},
                        {'changed': b'x' * len(self.members[module])}):
            with self.subTest(options=options):
                self.write(**options)
                with patch.object(inspector, 'PINS', self.pins), self.assertRaises(ValueError):
                    inspector.inspect(self.path)


if __name__ == '__main__':
    unittest.main()
