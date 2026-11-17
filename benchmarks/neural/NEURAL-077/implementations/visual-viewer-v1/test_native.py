"""Generated complete400 collection with the unchanged native NumPy validator."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('viewer', HERE / 'viewer.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class CompleteCollection(unittest.TestCase):
    def test_generated_complete400_preserves_all_ids_and_scalars(self):
        parser_path = HERE.parent / 'direct-response/portable/response_contract.py'
        validator_path = HERE.parent / 'registered-runtime/validator.py'
        parser = v.load_module('parser', parser_path, parser_path.read_bytes())
        validator = v.load_module('validator', validator_path, validator_path.read_bytes())
        # Intentionally invented identities and values, never authentic queries.
        rows = [{'trial_id': f'development-{case:03d}-generated-{i:03d}', 'channels': [[0.0] * 1024] * 2}
                for case in (1, 2) for i in range(200)]
        dataset = {'rows': rows, 'demos': [], 'parser': parser, 'validator': validator,
                   'packet': {'generated_only': '0' * 64}}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            sessions = root / 'sessions'; sessions.mkdir()
            for ordinal, row in enumerate(rows):
                session = v.Session(dataset, ordinal, 'zero_shot', sessions / f'{ordinal:03d}')
                response = v.encode({'trial_id': row['trial_id'], 'target_probability': ordinal / 399}).decode()
                session.handle(v.encode({'action': 'finalize', 'response': response}))
            with patch.object(v, 'source', return_value=dataset):
                receipt = v.collect('unused', sessions, 'zero_shot', root / 'collected')
            self.assertEqual(receipt['queries'], 400)
            with np.load(root / 'collected/submission.npz', allow_pickle=False) as submitted:
                self.assertEqual(submitted['trial_ids'].tolist(), [r['trial_id'] for r in rows])
                self.assertEqual(submitted['target_probability'].tolist(), [i / 399 for i in range(400)])


if __name__ == '__main__':
    unittest.main()
