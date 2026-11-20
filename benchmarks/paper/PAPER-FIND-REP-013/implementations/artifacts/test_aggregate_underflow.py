"""Generated finite-wire edge cases; no authentic morphology or scientific result."""
import argparse
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--source-root', type=Path, default=HERE.parents[4])
args, remaining = parser.parse_known_args()
BASE = args.source_root / 'benchmarks/paper/PAPER-FIND-REP-013/implementations'
PROFILE = BASE / 'registered-runtime/program-v1'
ARTIFACTS = BASE / 'artifacts'

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

ADAPTER = load('aggregate_underflow_adapter', ARTIFACTS / 'artifact.py')
SCHEMA, NEW, _, _ = ADAPTER.contracts(PROFILE)
previous = sys.modules.get('schema')
sys.modules['schema'] = SCHEMA
try:
    F = load('aggregate_underflow_fixtures', ARTIFACTS / 'numeric_fixtures.py')
    OLD = load('before_aggregate_underflow', ARTIFACTS / 'regression_fixtures/pre_aggregate_underflow_numeric_score.py')
finally:
    if previous is None:
        sys.modules.pop('schema', None)
    else:
        sys.modules['schema'] = previous

class AggregateUnderflow(unittest.TestCase):
    def test_nonzero_nonnegative_aggregates_never_become_exact_zero(self):
        tiny = float.fromhex('0x0.0000000000001p-1022')
        for values in ([tiny, 0., 0.], [tiny, 0., 0., 0., 0.], [tiny] + [0.] * 9):
            with self.subTest(n=len(values)):
                self.assertEqual(OLD.stats(values)['mae'], 0.)
                with self.assertRaisesRegex(NEW.Unscorable, 'Nonzero error aggregate underflow'):
                    NEW.stats(values)
        self.assertEqual(OLD.stats([tiny] + [0.] * 9)['rmse'], 0.)

    def test_complete_wire_does_not_report_false_perfect_primary(self):
        rows, reference = copy.deepcopy(F.rows), copy.deepcopy(F.rows)
        # Select a generated cell with one branch so its cell error is representable;
        # the historical false zero arises at the outer ten-cell aggregation.
        cell = SCHEMA.CELLS[4]
        row = next(r for r in rows['branches.csv'] if r['cell_id'] == cell)
        ref = next(r for r in reference['branches.csv'] if r['cell_id'] == cell)
        row['length_um'], ref['length_um'] = '5e-324', '0'
        files, targets = F.files(rows), F.files(reference)
        old = OLD.grade(files, lambda: targets)
        self.assertEqual(old['status'], 'scored')
        self.assertEqual(old['comparison']['metrics']['primary_equal_cell_branch_length_rmse_um'], 0.)
        calls = []
        new = NEW.grade(files, lambda: calls.append(True) or targets)
        self.assertEqual(new['status'], 'unsupported_derived_numerics')
        self.assertEqual(new['reason'], 'Nonzero error aggregate underflow')
        self.assertIsNone(new['comparison'])
        self.assertEqual(calls, [True])
        self.assertIsNone(new['scientific_success'])
        self.assertFalse(new['full_paper_reproduction'])

    def test_exact_zero_representable_subnormal_and_ordinary_results_preserved(self):
        tiny = float.fromhex('0x0.0000000000001p-1022')
        for values in ([0.] * 10, [tiny] * 5, [tiny, -tiny], [1., 2., -3.], [1e308, 1e308, -1e308]):
            with self.subTest(values=values):
                self.assertEqual(NEW.stats(values), OLD.stats(values))
        self.assertEqual(NEW.grade(F.files(F.rows), lambda: F.reference),
                         OLD.grade(F.files(F.rows), lambda: F.reference))

    def test_preceding_scorer_receipt_is_refused_before_candidate(self):
        old_bytes = (ARTIFACTS / 'regression_fixtures/pre_aggregate_underflow_numeric_score.py').read_bytes()
        receipt = {'profile': ADAPTER.PROFILE, 'schema': 1,
                   'scorer': [len(old_bytes), hashlib.sha256(old_bytes).hexdigest()],
                   'wire_schema': list(ADAPTER.PINS['schema.py']),
                   'producer_stopped_attested': True, 'files': {}, 'total_bytes': 0}
        body = ADAPTER.encoded(receipt, ADAPTER.RECEIPT_CAP)
        with mock.patch.object(ADAPTER, 'read', return_value=body) as read:
            with mock.patch.object(ADAPTER, 'candidate') as candidate:
                with self.assertRaisesRegex(ADAPTER.Refusal, 'Receipt contract'):
                    ADAPTER.load_attempt(HERE / 'unused-invented-attempt', ADAPTER.pin(body), SCHEMA, NEW)
                self.assertEqual(read.call_count, 1)
                candidate.assert_not_called()

if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
