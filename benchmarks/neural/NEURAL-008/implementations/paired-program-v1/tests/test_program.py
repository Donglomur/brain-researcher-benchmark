"""Generated software controls only; no original arrays, Docker or models."""
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import common
import prepare
import run
from vendor_transport.contract import validate_request, validate_exposure

WRITTEN = 0
ORIGINAL_PUBLISH = run.publish


def tracked_publish(path, body):
    global WRITTEN
    WRITTEN += len(body)
    if WRITTEN > 32 * 1024**2:
        raise AssertionError('Generated fixture cumulative allocation exceeded')
    return ORIGINAL_PUBLISH(path, body)


run.publish = tracked_publish


def save(path, body):
    global WRITTEN
    WRITTEN += len(body)
    if WRITTEN > 32 * 1024**2:
        raise AssertionError('Generated fixture cumulative allocation exceeded')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    path.chmod(0o444)
    return common.pin(body)


def npz(**values):
    stream = io.BytesIO()
    np.savez(stream, **values)
    return stream.getvalue()


def panel(case):
    n = common.CASES[case]
    return np.asarray([f'{case}/{i:05d}' for i in range(n)], dtype='<U21')


def predictions(class_index=0):
    values = {'class_order': np.asarray(common.CLASSES)}
    for case, n in common.CASES.items():
        if case.startswith('development-'):
            values[case + '__epoch_id'] = panel(case)
            probabilities = np.zeros((n, 5), dtype='<f8')
            probabilities[:, class_index] = 1
            values[case + '__probabilities'] = probabilities
    return npz(**values)


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='neural008-generated-')
        cls.root = Path(cls.temp.name).resolve()
        cls.bindings = {arm: [] for arm in common.ARMS}
        for arm, width in zip(common.ARMS, (15, 21)):
            files = []
            for case, n in common.CASES.items():
                names = [(case + '_features.npz', npz(epoch_id=panel(case), X=np.zeros((n, width), dtype='<f8')),
                          'training_features' if case.startswith('train-') else 'development_features')]
                if case.startswith('train-'):
                    mask = np.ones(n, dtype=bool)
                    if case == 'train-001':
                        mask[:79] = False
                    names.append((case + '_labels.npz', npz(epoch_id=panel(case), stage=np.zeros(n, dtype=np.int8), score_mask=mask),
                                  'training_labels'))
                for name, body, role in names:
                    path = cls.root / arm / name
                    identity = save(path, body)
                    cls.bindings[arm].append({'path': str(path.relative_to(cls.root)), **identity,
                                             'mount_destination': '/input/' + name, 'read_only': True})
                    files.append({'filename': name, **identity, 'case_id': case, 'role': role})
            manifest = {'arm': arm, 'classes': common.CLASSES, 'feature_count': width, 'files': files,
                        'training': [{'case_id': k, 'epochs': n} for k, n in common.CASES.items() if k.startswith('train-')],
                        'development': [{'case_id': k, 'epochs': n} for k, n in common.CASES.items() if k.startswith('development-')]}
            path = cls.root / arm / 'manifest.json'
            identity = save(path, common.encoded(manifest))
            cls.bindings[arm].append({'path': str(path.relative_to(cls.root)), **identity,
                                     'mount_destination': '/input/manifest.json', 'read_only': True})
        cls.good, cls.bad_class = predictions(0), predictions(1)
        cls.source = common.source()

    @classmethod
    def tearDownClass(cls):
        print(json.dumps({'generated_fixture_write_bytes': WRITTEN, 'original_payload_reads': 0,
                          'native_executions': 0, 'model_calls': 0}))
        cls.temp.cleanup()

    def test_complete_original_views(self):
        views = prepare.admit(self.root, self.bindings)
        self.assertEqual([len(views[a]) for a in common.ARMS], [15, 15])
        self.assertTrue(all('/input/development-002_features.npz' in views[a] for a in common.ARMS))

    def test_wrong_arm_or_extra_cache_is_rejected(self):
        for mutation in ('cache', 'missing', 'duplicate', 'other_arm'):
            altered = copy.deepcopy(self.bindings)
            if mutation == 'cache':
                altered[common.ARMS[0]][0]['mount_destination'] = '/input/yasa_predictions.npz'
            elif mutation == 'missing':
                altered[common.ARMS[0]].pop()
            elif mutation == 'duplicate':
                altered[common.ARMS[0]][0] = altered[common.ARMS[0]][1]
            else:
                altered[common.ARMS[0]] = altered[common.ARMS[1]]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                prepare.admit(self.root, altered)

    def test_shared_bit_identity_and_complete_order(self):
        case, n = 'development-002', 2670
        left = {'epoch_id': panel(case), 'X': np.zeros((n, 15), dtype='<f8')}
        right = {'epoch_id': panel(case), 'X': np.zeros((n, 21), dtype='<f8')}
        prepare.validate_pair(left, right, case)
        right['X'][0, 0] = -0.0
        with self.assertRaisesRegex(ValueError, 'Bit-identical'):
            prepare.validate_pair(left, right, case)
        right['X'][0, 0] = 0.0
        right['epoch_id'] = right['epoch_id'][::-1].copy()
        with self.assertRaisesRegex(ValueError, 'roster'):
            prepare.validate_pair(left, right, case)
        right['epoch_id'] = panel(case)[:-1]
        with self.assertRaisesRegex(ValueError, 'roster'):
            prepare.validate_pair(left, right, case)

    def exercise(self, mode):
        output = self.root / ('run-' + mode)
        stage = self.root / ('candidate-' + mode)
        stage.mkdir()
        save(stage / 'program.py', b'# Generated control; never executed\n')
        save(stage / 'method.json', common.encoded({'schema_version': 1, 'method_id': 'generated',
             'method_description': 'Scripted collector control', 'training_policy': 'No fit', 'limitations': 'Not AI results'}))
        save(stage / 'claims.json', common.encoded({'schema_version': 1, 'candidate_id': 'NEURAL-008', 'reported_contrast': None}))
        committed = run.commit(stage / 'program.py', stage / 'method.json', stage / 'claims.json', output)
        events, target_calls = [], []
        test = self
        class GeneratedBackend:
            def run(self, arm, view, program_pin):
                test.assertTrue((output / 'COMMIT.json').is_file())
                test.assertFalse((output / 'PAIRED_FREEZE.json').exists())
                events.append(arm)
                body = test.good if arm == common.ARMS[0] else test.bad_class
                if mode == 'malformed_second' and arm == common.ARMS[1]:
                    body = b'not a probability archive'
                if mode == 'mutated_source':
                    global WRITTEN
                    (output / 'program.py').chmod(0o600)
                    body_change = b'# changed after data access\n'
                    WRITTEN += len(body_change)
                    (output / 'program.py').write_bytes(body_change)
                return body, {'producer_removed_before_capture': mode != 'live_producer',
                              'all_native_resources_closed': True, 'source': test.source, 'program': program_pin,
                              'captured_output': common.pin(body)}
        def targets():
            target_calls.append(1)
            test.assertEqual(events, list(common.ARMS))
            test.assertTrue((output / 'PAIRED_FREEZE.json').is_file())
            return {case: {'epoch_id': panel(case), 'stage': np.zeros(n, dtype=np.int8),
                           'score_mask': np.ones(n, dtype=bool)}
                    for case, n in common.CASES.items() if case.startswith('development-')}
        if mode == 'complete':
            result = run.complete(output, committed, {a: {} for a in common.ARMS}, GeneratedBackend(), self.source, targets)
            self.assertEqual(len(target_calls), 1)
            self.assertLess(result['result']['paired_contrast']['person_mean_macro_f1_delta'], 0)
            self.assertIsNone(result['result']['scalar_optimization_reward'])
        else:
            with self.assertRaises(Exception):
                run.complete(output, committed, {a: {} for a in common.ARMS}, GeneratedBackend(), self.source, targets)
            self.assertEqual(target_calls, [])
            self.assertFalse((output / 'PAIRED_FREEZE.json').exists())
            if mode in ('live_producer', 'mutated_source'):
                self.assertEqual(events, [common.ARMS[0]])

    def test_both_freezes_before_target_and_negative_difference(self):
        self.exercise('complete')

    def test_bad_second_arm_prevents_target_access(self):
        self.exercise('malformed_second')

    def test_live_producer_prevents_next_arm(self):
        self.exercise('live_producer')

    def test_source_mutation_prevents_next_arm(self):
        self.exercise('mutated_source')

    def test_native_adapter_binds_exact_mounts_and_observes_capture(self):
        """Exercise the real request adapter against a generated transport double.

        This does not run or qualify the Docker transport itself.
        """
        stage = self.root / 'native-adapter-control'
        stage.mkdir()
        program_pin = save(stage / 'program.py', b'# Not executed\n')
        policy = {'schema': 'neural008_mechanical_boundary_v1',
                  'approved_rule': 'exact_original_paired_views_and_frozen_program_v1',
                  'source': self.source, 'image': 'sha256:' + 'a' * 64, 'image_inventory_sha256': 'b' * 64}
        policy_pin = save(stage / 'policy.json', common.encoded(policy))
        config = {'schema': 'neural008_native_configuration_v1', 'mechanical_policy_path': str(stage / 'policy.json'),
                  'mechanical_policy_pin': policy_pin, 'image': policy['image'], 'control_root': str(stage / 'control'),
                  'quarantine_root': str(stage / 'capture'), 'docker_binary': '/generated/no-docker',
                  'docker_socket': '/generated/no-socket'}
        test, observations, released = self, [], []
        class GeneratedProvider:
            def __init__(self, control, quarantine, binary, socket, engine_pin, exposures, *limits):
                self.exposures, self.quarantine = exposures, Path(quarantine)
            def execute_phase(self, request, mounts, deadline, journal):
                validate_request(request, mounts, deadline)
                approval = common.decode(common.read(self.exposures[request['exposure']['sha256']], 32768))
                validate_exposure(approval, request, mounts)
                test.assertEqual(len(mounts), 17)
                test.assertEqual(sum(d['purpose'] == 'input' for d in mounts.values()), 15)
                test.assertNotIn('/input/development-001_labels.npz', mounts)
                test.assertNotIn('/input/other_arm_predictions.npz', mounts)
                released.append(request['role'])
                capture = self.quarantine / request['phase_id']
                capture.mkdir(parents=True)
                prediction = save(capture / 'predictions.npz', test.good)
                result = save(capture / 'RESULT.json', common.encoded({'schema': 'neural008_program_exit_v1', 'candidate_exit_code': 0}))
                self.receipt = {'status': 'captured', 'producer_closed_before_capture': True,
                    'all_native_resources_closed': True, 'cli_reaped': True, 'error': None,
                    'natural_exit': {'ExitCode': 0, 'OOMKilled': False}, 'source': request['source'],
                    'role': request['role'], 'image': request['image'], 'exposure': request['exposure'],
                    'input_before': mounts, 'input_after': mounts, 'quarantine_root': str(capture),
                    'output_inventory': {'complete': True, 'files': {'predictions.npz': prediction, 'RESULT.json': result, 'OUTPUTS.json': {}}}}
                self.request = request
                return {'receipt_pin': common.pin(common.encoded(self.receipt)), 'receipt_path': '/generated/receipt.json'}
            def observe(self, phase_id, request_sha, receipt_pin, deadline):
                test.assertEqual(phase_id, self.request['phase_id'])
                test.assertEqual(request_sha, common.pin(common.encoded(self.request))['sha256'])
                observations.append(phase_id)
                return {'receipt': self.receipt}
        views = prepare.admit(self.root, self.bindings)
        with patch.object(run, 'Provider', GeneratedProvider):
            backend = run.Native(config, stage, (0, 150), self.source)
            for arm in common.ARMS:
                body, evidence = backend.run(arm, views[arm], program_pin)
                self.assertEqual(body, self.good)
                self.assertTrue(evidence['producer_removed_before_capture'])
        self.assertEqual(released, ['A', 'B'])
        self.assertEqual(len(set(observations)), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
