"""Generated offset controls on exact binary64 values and complete artifacts."""
from fractions import Fraction
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_find025_offset_fixture', HERE / 'test_numeric_scale.py')
f = importlib.util.module_from_spec(spec)
exec(compile((HERE / 'test_numeric_scale.py').read_bytes(), str(HERE / 'test_numeric_scale.py'), 'exec'), f.__dict__)
e, m, c = f.e, f.m, f.c


def exact_signed(y, p):
    y, p = list(map(Fraction, y)), list(map(Fraction, p))
    center = sum(y) / len(y)
    return float(1 - sum((a-b)**2 for a, b in zip(y, p)) / sum((a-center)**2 for a in y))


class OffsetControls(unittest.TestCase):
    def test_exact_large_offset_correlation(self):
        origin = 3 * 2**52
        observed = [origin, origin+2, origin+4]
        self.assertAlmostEqual(m.squared_pearson_correlation(observed, [-1, 0, 1]), 1., places=14)
        self.assertAlmostEqual(m.squared_pearson_correlation([-1, 0, 1], observed), 1., places=14)

    def test_signed_error_is_formed_before_rescaling(self):
        origin = 3 * 2**52
        y = [origin, origin+2, origin+4]
        p = [origin+2, origin+4, origin+6]
        self.assertEqual(exact_signed(y, p), -.5)
        self.assertAlmostEqual(m.signed_variance_explained(y, p), exact_signed(y, p), places=14)

    def test_supported_complete_artifact_pair_uses_offset_stable_metrics(self):
        data = f.panel(1.)
        plan, submissions, payloads, bundle = data
        origin = 3 * 2**52
        for row in bundle['cases']:
            row['target_values'] = [origin, origin+2, origin+4]
        for body_key, body in list(payloads.items()):
            decoded = json.loads(body)
            decoded['values'] = [origin+2, origin+4, origin+6]
            replacement = json.dumps(decoded, separators=(',', ':'), allow_nan=False).encode()
            new_hash = sha256(replacement).hexdigest()
            run, kind, logical, old_hash = body_key
            for submission in submissions:
                if submission['run_id'] == run:
                    for record in submission['records']:
                        for descriptor in record['artifacts']:
                            if (descriptor['kind'], descriptor['logical_id'], descriptor['sha256']) == (kind, logical, old_hash):
                                descriptor['sha256'] = new_hash
            del payloads[body_key]
            payloads[(run, kind, logical, new_hash)] = replacement
        result = e.evaluate_submissions(*data)
        self.assertEqual(len(result['case_audit']), 72)
        self.assertEqual(len(result['scores']), 16)
        for record in result['scores']:
            self.assertEqual(record['status'], 'valid')
            self.assertAlmostEqual(record['value'], -.5 if record['identity']['metric_id'] == c.SIGNED else 1., places=14)
        self.assertFalse(result['support_contract']['paper_qualification'])
        self.assertIsNone(result['comparison']['paper_pass'])

    def test_small_normal_and_constant_domains_are_preserved(self):
        for scale in (1e-200, 1., 1e99):
            y, p = [0., scale, 2*scale], [0., 2*scale, 4*scale]
            self.assertAlmostEqual(m.signed_variance_explained(y, p), -1.5, places=14)
            self.assertAlmostEqual(m.squared_pearson_correlation(y, p), 1., places=14)
        for metric in (m.signed_variance_explained, m.squared_pearson_correlation):
            with self.assertRaises(m.UndefinedMetric):
                metric([3., 3., 3.], [1., 2., 3.])


if __name__ == '__main__':
    unittest.main()
