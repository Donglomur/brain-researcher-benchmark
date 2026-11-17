"""Generated scorer-boundary checks; no scientific imports or original inputs.

The full scorer and JSON I/O run unchanged. Only the numerical modules' import
surface is isolated: their actual constants, need(), and packet_valid() source
are loaded without importing NumPy/SciPy or running scientific calculations.
"""
import ast
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


PACKAGE = Path(__file__).resolve().parent
PRIVATE = PACKAGE / 'package' / 'private'
PUBLIC = PACKAGE / 'package' / 'public'


def selected_definitions(path, names, namespace):
    tree = ast.parse(path.read_bytes(), filename=str(path))
    selected = []
    found = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            selected.append(node)
            found.add(node.name)
        elif isinstance(node, ast.Assign):
            identifiers = {target.id for target in node.targets
                           if isinstance(target, ast.Name)}
            if identifiers & names:
                # This test loader must never execute arbitrary initializers.
                ast.literal_eval(node.value)
                selected.append(node)
                found.update(identifiers & names)
    if found != names:
        raise AssertionError('Expected exact boundary definitions')
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'),
         namespace)


def load_scorer():
    pac = types.ModuleType('pac')
    selected_definitions(PUBLIC / 'pac.py',
                         {'DESIGNS', 'CONTRASTS', 'METRICS', 'need'}, pac.__dict__)
    reference = types.ModuleType('reference')
    reference.need = pac.need
    selected_definitions(PRIVATE / 'reference.py', {'packet_valid'},
                         reference.__dict__)
    io = types.ModuleType('io_utils')
    io.__file__ = str(PRIVATE / 'io_utils.py')
    exec(compile((PRIVATE / 'io_utils.py').read_bytes(), io.__file__, 'exec'),
         io.__dict__)
    scorer = types.ModuleType('neural042_boundary_test_scorer')
    scorer.__file__ = str(PRIVATE / 'score.py')
    original_path = sys.path[:]
    try:
        with patch.dict(sys.modules, {'pac': pac, 'reference': reference,
                                      'io_utils': io}):
            exec(compile((PRIVATE / 'score.py').read_bytes(), scorer.__file__,
                         'exec'), scorer.__dict__)
    finally:
        sys.path[:] = original_path
    return scorer


class CandidateJsonBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.score = load_scorer()
        self.packet = {'schema': 'neural042_packet_v1', 'source_sessions': 44,
                       'patients': [f'{i:024x}' for i in range(36)],
                       'channels': []}
        self.packet_pin = self.store('packet.json', self.packet)
        self.operator = self.root / 'operator.json'
        self.submission = self.root / 'candidate.json'
        self.output = self.root / 'result.json'
        self.pin_reads = []
        actual_pinned_json = self.score.pinned_json

        def observed_pinned_json(base, descriptor, *args):
            self.pin_reads.append(descriptor['path'])
            return actual_pinned_json(base, descriptor, *args)

        self.score.pinned_json = observed_pinned_json

    def store(self, name, value=None, *, body=None):
        if body is None:
            body = json.dumps(value, allow_nan=False).encode()
        (self.root / name).write_bytes(body)
        return {'path': name, 'bytes': len(body),
                'sha256': hashlib.sha256(body).hexdigest()}

    def report(self):
        return {
            'schema': 'neural042_report_v1',
            'claim_scope': 'descriptive_patient_associations_not_causal_or_crossoscillator_proof',
            'patients': [
                {'patient': patient, 'design': design, 'contrast': contrast,
                 'n_sessions': 0, 'n_channels': 0, 'metrics': None}
                for patient in self.packet['patients']
                for design in self.score.DESIGNS for contrast in self.score.CONTRASTS],
            'groups': [
                {'design': design, 'contrast': contrast, 'n_patients': 0,
                 'mean': None, 'ci95': None, 'sign_flip_p': None}
                for design in self.score.DESIGNS for contrast in self.score.CONTRASTS]}

    def prepare(self, candidate=None, *, body=None, gold=None, packet=None):
        self.store('candidate.json', candidate, body=body)
        self.store('operator.json', {'packet': self.packet_pin if packet is None else packet,
                                    'gold': gold})

    def run_main(self):
        with patch.object(sys, 'argv', ['score.py', '--submission', str(self.submission),
                                       '--operator', str(self.operator),
                                       '--out', str(self.output)]):
            return self.score.main()

    def test_deep_candidate_is_invalid_before_gold_access(self):
        gold = self.store('gold.json', self.report())
        self.prepare(body=b'[' * 2000 + b'0' + b']' * 2000, gold=gold)
        self.assertEqual(self.run_main(), 2)
        result = json.loads(self.output.read_text())
        self.assertEqual(result['status'], 'invalid_submission')
        self.assertEqual(result['detail'], 'RecursionError')
        self.assertIsNone(result['score'])
        self.assertEqual(result['target_loader_calls'], 0)
        self.assertEqual(self.pin_reads, ['packet.json'])

    def test_ordinary_malformed_candidate_still_avoids_gold(self):
        gold = self.store('gold.json', self.report())
        for value in ({'bad': 1}, {'schema': 'neural042_report_v1'}):
            with self.subTest(value=value):
                self.pin_reads.clear()
                self.prepare(value, gold=gold)
                self.assertEqual(self.run_main(), 2)
                result = json.loads(self.output.read_text())
                self.assertEqual(result['status'], 'invalid_submission')
                self.assertEqual(result['target_loader_calls'], 0)
                self.assertEqual(self.pin_reads, ['packet.json'])

    def test_valid_report_without_gold_retains_reference_hold(self):
        self.prepare(self.report())
        self.assertEqual(self.run_main(), 2)
        result = json.loads(self.output.read_text())
        self.assertEqual(result['status'], 'reference_unavailable')
        self.assertEqual(result['target_loader_calls'], 0)

    def test_deep_operator_descriptor_is_not_candidate_failure(self):
        self.prepare(self.report())
        self.operator.write_bytes(b'[' * 2000 + b'0' + b']' * 2000)
        with self.assertRaises(RecursionError):
            self.run_main()
        self.assertFalse(self.output.exists())
        self.assertEqual(self.pin_reads, [])

    def test_deep_gold_is_not_candidate_failure(self):
        gold = self.store('gold.json', body=b'[' * 2000 + b'0' + b']' * 2000)
        self.prepare(self.report(), gold=gold)
        with self.assertRaises(RecursionError):
            self.run_main()
        self.assertFalse(self.output.exists())
        self.assertEqual(self.pin_reads, ['packet.json', 'gold.json'])

    def test_corrupt_gold_pin_remains_operator_error(self):
        gold = self.store('gold.json', self.report())
        gold['sha256'] = '0' * 64
        self.prepare(self.report(), gold=gold)
        self.assertEqual(self.run_main(), 2)
        result = json.loads(self.output.read_text())
        self.assertEqual(result['status'], 'operator_error')
        self.assertEqual(result['target_loader_calls'], 1)

    def test_generated_empty_support_does_not_become_scored(self):
        gold = self.store('gold.json', self.report())
        self.prepare(self.report(), gold=gold)
        self.assertEqual(self.run_main(), 2)
        result = json.loads(self.output.read_text())
        self.assertEqual(result['status'], 'incomplete_primary_support')
        self.assertIsNone(result['score'])
        self.assertEqual(result['target_loader_calls'], 1)


if __name__ == '__main__':
    unittest.main()
