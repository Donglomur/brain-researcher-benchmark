"""Invented full-grid controls for the real candidate callback path."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import participant as p

fixture_path = HERE.parent / 'participant-packet' / 'test_packet.py'
spec = importlib.util.spec_from_file_location('localization_packet_fixtures', fixture_path)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)

PROGRAM = b'''def predict(case, observations):
    assert_unused = observations['observed_support']['dtype']
    w = observations['waveforms']['values']
    t = observations['template']['values']
    point = [sum(w) / len(w), sum(t) / len(t)]
    return {r['request_id']: point for r in case['requests']}
'''


class ParticipantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.neural, self.bodies = fixture.fixture()
        self.root = fixture.source(self.base, self.bodies)
        self.program = self.base / 'predict.py'
        self.program.write_bytes(PROGRAM)

    def produce(self, **changes):
        args = dict(expected_manifest_sha256=hashlib.sha256(fixture.p.canonical(self.neural)).hexdigest(),
                    expected_program_sha256=hashlib.sha256(PROGRAM).hexdigest(),
                    program_bytes=len(PROGRAM), total_input_byte_budget=100000,
                    maximum_artifact_bytes=10000)
        args.update(changes)
        return p.produce(self.neural, self.root, self.program, **args)

    def test_complete880_signal_sensitive_output_and_existing_scorer(self):
        submission, receipt = self.produce()
        self.assertEqual((receipt['cases'], receipt['requests']), (880, 2640))
        self.assertEqual({tuple(r['coordinate_um']) for r in submission['rows']}, {(8.5, 4.0)})
        self.assertEqual(receipt['submission_sha256'],
                         hashlib.sha256(fixture.p.canonical(submission)).hexdigest())
        self.assertFalse(receipt['sandbox_enforced'])
        self.assertFalse(receipt['scientific_qualification'])
        reference = {'schema': 'localization-owner-reference-v1', 'coordinate_unit': 'um',
                     'axis_names': ['z', 'x'], 'reference_kind': 'nearest_contact_proxy',
                     'reference_evidence_sha256': 'a' * 64, 'group_evidence_sha256': 'b' * 64,
                     'undegraded_condition_id': self.neural['conditions'][0],
                     'cells': [{'cell_id': c, 'recording_id': fixture.opaque('recording'),
                                'animal_id': fixture.opaque('animal'), 'coordinate_um': [0, 0]}
                               for c in self.neural['cells']]}
        neutral = fixture.p.load_neutral()
        score = neutral.score(self.neural, reference, submission, hashlib.sha256(PROGRAM).hexdigest())
        self.assertEqual(score['status'], 'COMPLETE_SUPPORT_SCORE')
        self.assertEqual((score['requested'], score['valid']), (2640, 2640))
        raw = fixture.npy([2, 3, 3], [0] * 18)
        fixture.replace_role(self.neural, self.bodies, 'waveforms', raw)
        (self.root / 'inputs' / (hashlib.sha256(raw).hexdigest() + '.npy')).write_bytes(raw)
        changed, _ = self.produce()
        self.assertEqual({tuple(r['coordinate_um']) for r in changed['rows']}, {(0.0, 4.0)})

    def test_target_free_arguments_and_callback_mutations_do_not_change_later_cases(self):
        seen = []
        def predict(case, observations):
            self.assertEqual(set(case), {'case_id', 'condition_id', 'sampling_frequency_hz',
                'voltage_unit', 'sample_offsets', 'channel_ids', 'inputs', 'requests',
                'axis_names', 'coordinate_unit'})
            self.assertEqual(case['axis_names'], self.neural['axis_names'])
            self.assertEqual(case['coordinate_unit'], 'um')
            self.assertEqual(set(observations), {'waveforms', 'template', 'probe_geometry', 'observed_support'})
            self.assertEqual(observations['waveforms']['values'], tuple(range(18)))
            self.assertEqual(observations['waveforms']['shape'], (2, 3, 3))
            result = {r['request_id']: [1, 2] for r in case['requests']}
            case['requests'].clear()
            case['axis_names'].reverse()
            observations['waveforms']['values'] = ('changed',)
            seen.append(True)
            return result
        before = fixture.p.canonical(self.neural)
        with mock.patch.object(p, '_load_predictor', return_value=predict):
            submission, _ = self.produce()
        self.assertEqual(len(seen), 880)
        self.assertEqual(len(submission['rows']), 2640)
        self.assertEqual(fixture.p.canonical(self.neural), before)

    def test_invalid_candidate_rows_abort_without_partial_output(self):
        for mode in ('missing', 'extra', 'nonfinite', 'boolean', 'exception'):
            def predict(case, observations):
                result = {r['request_id']: [1, 2] for r in case['requests']}
                first = next(iter(result))
                if mode == 'missing': result.pop(first)
                elif mode == 'extra': result['unknown'] = [1, 2]
                elif mode == 'nonfinite': result[first] = [float('inf'), 0]
                elif mode == 'boolean': result[first] = [True, 0]
                else: raise RuntimeError('invented participant failure')
                return result
            with self.subTest(mode=mode), mock.patch.object(p, '_load_predictor', return_value=predict):
                with self.assertRaises((p.ParticipantError, RuntimeError)):
                    self.produce()

    def test_complete_input_and_program_admission_precedes_candidate_execution(self):
        for mode in ('missing_case', 'missing_body', 'program_hash', 'allocation'):
            neural = copy.deepcopy(self.neural)
            saved = None
            kwargs = {}
            if mode == 'missing_case': self.neural['cases'].pop()
            elif mode == 'missing_body':
                saved = next((self.root / 'inputs').iterdir())
                body = saved.read_bytes(); saved.unlink()
            elif mode == 'program_hash': kwargs['expected_program_sha256'] = '0' * 64
            else: kwargs['total_input_byte_budget'] = 1
            with self.subTest(mode=mode), mock.patch.object(p, '_load_predictor') as load:
                with self.assertRaises(ValueError): self.produce(**kwargs)
                load.assert_not_called()
            self.neural = neural
            if saved is not None: saved.write_bytes(body)

    def test_program_mutation_rejected_and_dependencies_explicit(self):
        def predict(case, observations):
            self.program.write_bytes(b'x' * len(PROGRAM))
            return {r['request_id']: [0, 0] for r in case['requests']}
        with mock.patch.object(p, '_load_predictor', return_value=predict):
            with self.assertRaisesRegex(ValueError, 'hash mismatch'): self.produce()
        for code in (b'import numpy\ndef predict(c,o): return {}',
                     b'from os import system\ndef predict(c,o): return {}'):
            with self.assertRaisesRegex(p.ParticipantError, 'standard-library'):
                p._load_predictor(code)
        allowed = p._load_predictor(b'import math\ndef predict(c,o): return math.sqrt(9)')
        self.assertEqual(allowed({}, {}), 3)

    def test_geometry_trajectory_cannot_bypass_packet_checks(self):
        raw = fixture.npy([3, 2], [50, 90, 10, 30, 0, 0])
        descriptor = fixture.artifact('probe_geometry', [3, 2], raw)
        self.neural['artifacts'].append(descriptor)
        self.neural['cases'][0]['inputs']['probe_geometry'] = descriptor['sha256']
        (self.root / 'inputs' / (descriptor['sha256'] + '.npy')).write_bytes(raw)
        with mock.patch.object(p, '_load_predictor') as load:
            with self.assertRaisesRegex(p.ParticipantError, 'channel/coordinate'):
                self.produce()
            load.assert_not_called()


if __name__ == '__main__':
    unittest.main()
