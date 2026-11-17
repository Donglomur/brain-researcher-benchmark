"""Generated software controls; authentic admission evidence is kept outside Git."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent / 'registered-runtime'
spec = importlib.util.spec_from_file_location('portable_score', HERE / 'score.py')
portable = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portable)


class PortableTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='neural077-portable-controls-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.descriptor = self.root / 'artifacts.json'
        self.locations = {'schema_version': 1, 'candidate_id': 'NEURAL-077',
                          'public_features': {c: str(self.root / ('public-' + c)) for c in portable.CASES},
                          'private_targets': {c: str(self.root / ('PRIVATE-' + c)) for c in portable.CASES},
                          'reference_grade': str(self.root / 'PRIVATE-grade'),
                          'reference_commit': str(self.root / 'PRIVATE-commit')}
        self.descriptor.write_text(json.dumps(self.locations))
        self.submission = self.root / 'candidate.npz'
        self.submission.write_bytes(b'generated content for mocked transport only')
        self.args = argparse.Namespace(action='score', package_dir=str(PACKAGE),
                    artifacts=str(self.descriptor), docker_cli='/abs/docker',
                    docker_host='unix:///abs/socket', docker_config='/abs/config',
                    submission=str(self.submission), output_dir=str(self.root / 'fresh'))

    def validated(self):
        return {'status': 'valid_prediction_contract', 'prediction_contract_valid': True,
                'trial_count': 400, 'people': 2, 'target_loader_invocations': 0,
                'private_assets_read': False,
                'submission_sha256': hashlib.sha256(self.submission.read_bytes()).hexdigest()}

    def scored(self):
        return dict(self.validated(), status='scored', scientific_score_computed=True,
                    target_loader_invocations=2, candidate_minus_reference={name: {} for name in (
                        'prior', 'eeg', 'eog_site', 'gross_amplitude', 'behavioral_history', 'eeg_history')})

    def run_mocked(self, effects):
        with mock.patch.object(portable, 'runtime_options', return_value=(['generated-docker'], {})), \
                mock.patch.object(portable, 'stage_evidence', return_value={}), \
                mock.patch.object(portable, 'execute_stage', side_effect=effects) as execute:
            value, code = portable.run(self.args)
        return value, code, execute

    def test_complete_current_source_and_counter_repair_selected(self):
        core, assets, source = portable.capture_source(PACKAGE, self.root / 'snapshot')
        self.assertEqual((source['bytes'], source['sha256']), portable.CURRENT_PIN)
        self.assertEqual(assets['case_ids'], list(portable.CASES))
        worker = (self.root / 'snapshot' / 'worker.py').read_bytes()
        self.assertEqual(hashlib.sha256(worker).hexdigest(),
                         'cdeeb2019a17b0da8c809a796bab044dba54eae422436236fc2c27cb2565a88e')
        self.assertEqual(core.verify_source(self.root / 'snapshot'), source)

    def test_changed_source_rejected_before_import(self):
        package = self.root / 'changed'
        shutil.copytree(PACKAGE, package)
        (package / 'worker.py').write_text('raise RuntimeError("MUST NOT IMPORT")')
        with mock.patch.object(portable.importlib.util, 'spec_from_file_location') as importer:
            with self.assertRaisesRegex(ValueError, 'Current package source changed: worker.py'):
                portable.capture_source(package, self.root / 'snapshot')
        importer.assert_not_called()
        self.assertFalse((self.root / 'snapshot').exists())

    def test_repinning_descriptor_cannot_admit_changed_source(self):
        package = self.root / 'changed'
        shutil.copytree(PACKAGE, package)
        changed = (package / 'worker.py').read_bytes() + b'\n'
        (package / 'worker.py').write_bytes(changed)
        descriptor = json.loads((package / 'CURRENT_SOURCE.json').read_text())
        descriptor['files']['worker.py'] = portable.pin(changed)
        (package / 'CURRENT_SOURCE.json').write_text(json.dumps(descriptor))
        with self.assertRaisesRegex(ValueError, 'Unrecognized CURRENT_SOURCE'):
            portable.capture_source(package, self.root / 'snapshot')

    def test_descriptor_parsing_does_not_require_private_files(self):
        paths, _ = portable.artifact_locations(self.descriptor, 'score')
        self.assertEqual(len(paths), 6)
        self.assertFalse(any(Path(v).exists() for v in paths.values()))

    def test_bad_descriptors_reject_duplicates_extra_cases_and_relative_locations(self):
        for change in ('duplicate', 'extra', 'case', 'relative', 'comma'):
            value = json.loads(json.dumps(self.locations))
            if change == 'duplicate':
                self.descriptor.write_text('{"schema_version":1,"schema_version":1}')
            else:
                if change == 'extra': value['pins'] = {}
                if change == 'case': value['private_targets']['extra'] = '/abs/extra'
                if change == 'relative': value['reference_grade'] = 'relative'
                if change == 'comma': value['reference_grade'] = '/abs/path,readonly'
                self.descriptor.write_text(json.dumps(value))
            with self.subTest(change=change), self.assertRaises(ValueError):
                portable.artifact_locations(self.descriptor, 'score')

    def test_invalid_candidate_never_touches_or_dispatches_private_paths(self):
        original = portable.unlinked
        def guard(path):
            self.assertNotIn('PRIVATE', str(path))
            return original(path)
        with mock.patch.object(portable, 'unlinked', side_effect=guard):
            result, code, execute = self.run_mocked([({'status': 'invalid_submission'}, 2)])
        self.assertEqual(code, 2)
        self.assertEqual(result['status'], 'invalid_submission')
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(set(execute.call_args.args[3]),
                         {'/package', '/input/submission.npz', '/public/development-001.npz', '/public/development-002.npz'})
        receipt = json.loads((Path(self.args.output_dir) / 'receipt.json').read_text())
        self.assertFalse(receipt['private_stage_dispatched'])

    def test_incomplete_public_receipt_blocks_private_stage(self):
        for field, bad in (('trial_count', 399), ('people', 1), ('target_loader_invocations', 1),
                           ('private_assets_read', True), ('submission_sha256', '0' * 64)):
            self.args.output_dir = str(self.root / field)
            invalid = dict(self.validated(), **{field: bad})
            result, code, execute = self.run_mocked([(invalid, 0)])
            with self.subTest(field=field):
                self.assertEqual(code, 3)
                self.assertEqual(execute.call_count, 1)
                self.assertIn('Incomplete public validation receipt', result['error'])

    def test_full_scoring_only_after_valid_receipt_uses_same_captured_candidate(self):
        result, code, execute = self.run_mocked([(self.validated(), 0), (self.scored(), 0)])
        self.assertEqual(code, 0)
        self.assertEqual(result['status'], 'scored')
        first, second = execute.call_args_list
        self.assertEqual(first.args[4], 'validate')
        self.assertEqual(second.args[4], 'score')
        self.assertEqual(first.args[3]['/input/submission.npz'], second.args[3]['/input/submission.npz'])
        self.assertEqual(first.args[5], second.args[5])
        self.assertEqual(set(second.args[3]) - set(first.args[3]), {
            '/targets/development-001.npz', '/targets/development-002.npz',
            '/input/reference_grade.json', '/input/reference_commit.json'})

    def test_worker_private_failure_remains_operator_failure_and_retains_counter(self):
        failure = {'status': 'scoring_error', 'scientific_score_computed': False,
                   'target_loader_invocations': 1, 'error': 'generated target pin refusal'}
        result, code, _ = self.run_mocked([(self.validated(), 0), (failure, 3)])
        self.assertEqual(code, 3)
        self.assertEqual(result, failure)

    def test_validate_interface_requires_no_private_locations(self):
        self.args.action = 'validate'
        public = {key: value for key, value in self.locations.items() if key in portable.PUBLIC_KEYS}
        self.descriptor.write_text(json.dumps(public))
        result, code, execute = self.run_mocked([(self.validated(), 0)])
        self.assertEqual(code, 0)
        self.assertEqual(execute.call_count, 1)

    def test_existing_output_and_dangling_symlink_are_refused_without_reads(self):
        output = Path(self.args.output_dir)
        output.mkdir()
        sentinel = output / 'prior-receipt'
        sentinel.write_bytes(b'preserve')
        with mock.patch.object(portable, 'capture_source') as capture:
            with self.assertRaises(FileExistsError): portable.run(self.args)
        capture.assert_not_called()
        self.assertEqual(sentinel.read_bytes(), b'preserve')
        sentinel.unlink()
        output.rmdir()
        output.symlink_to(self.root / 'absent')
        with self.assertRaisesRegex(ValueError, 'Linked path rejected'): portable.run(self.args)

    def test_input_hardlink_and_symlink_are_rejected(self):
        for kind in ('hardlink', 'symlink'):
            linked = self.root / kind
            if kind == 'hardlink': os.link(self.submission, linked)
            else: linked.symlink_to(self.submission)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                portable.read_regular(linked, 1048576)
            linked.unlink()

    def test_receipts_and_candidate_snapshot_are_exclusive_read_only_and_hashed(self):
        self.run_mocked([({'status': 'invalid_submission'}, 2)])
        output = Path(self.args.output_dir)
        receipt = json.loads((output / 'receipt.json').read_text())
        self.assertEqual(receipt['result'], portable.pin((output / 'result.json').read_bytes()))
        self.assertEqual(receipt['submission'], portable.pin((output / 'submission.npz').read_bytes()))
        for name in ('result.json', 'receipt.json', 'submission.npz'):
            self.assertEqual((output / name).stat().st_mode & 0o222, 0)
        with self.assertRaises(FileExistsError): portable.save(output / 'result.json', {})

    def test_runtime_context_and_remote_socket_cannot_override_explicit_location(self):
        self.args.docker_cli = sys.executable
        self.args.docker_host = 'tcp://elsewhere:2375'
        with self.assertRaisesRegex(ValueError, 'local Unix'):
            portable.runtime_options(self.args)
        import socket
        endpoint = socket.socket(socket.AF_UNIX)
        self.addCleanup(endpoint.close)
        endpoint.bind(str(self.root / 'socket'))
        self.args.docker_host = 'unix://' + str(self.root / 'socket')
        self.args.docker_config = str(self.root)
        with mock.patch.dict(os.environ, {'DOCKER_CONTEXT': 'hostile-default', 'DOCKER_TLS_VERIFY': '1'}):
            argv, env = portable.runtime_options(self.args)
        self.assertEqual(argv[-2:], ['--host', self.args.docker_host])
        self.assertFalse(any(k.startswith('DOCKER_') for k in env))

    def test_container_inspection_refusal_cleans_up_without_starting(self):
        core, _, _ = portable.capture_source(PACKAGE, self.root / 'package')
        calls = []
        def fake(argv, **kwargs):
            command = argv[1:]
            calls.append(command)
            if command[0] == 'inspect':
                if len([c for c in calls if c[0] == 'inspect']) in (1, 3):
                    return subprocess.CompletedProcess(argv, 1, '[]\n', 'Error: No such object: ' + command[-1])
                return subprocess.CompletedProcess(argv, 0, '[{}]', '')
            return subprocess.CompletedProcess(argv, 0, 'generated\n', '')
        with mock.patch.object(portable.subprocess, 'run', side_effect=fake):
            result, code = portable.execute_stage(core, ['fake-docker'], {}, {}, 'validate', '0' * 64, self.root / 'stage')
        self.assertEqual(code, 3)
        self.assertEqual(result['status'], 'operator_execution_failed')
        self.assertFalse(any(c[0] == 'start' for c in calls))
        self.assertTrue(any(c[:2] == ['rm', '--force'] for c in calls))
        receipt = json.loads((self.root / 'stage' / 'execution.json').read_text())
        self.assertTrue(receipt['absence_verified'])

    def test_wait_timeout_recovers_worker_output_before_removal_without_accepting_score(self):
        core, _, _ = portable.capture_source(PACKAGE, self.root / 'package')
        calls = []
        def fake(argv, **kwargs):
            command = argv[1:]
            calls.append(command)
            if command[0] == 'inspect':
                if len([c for c in calls if c[0] == 'inspect']) in (1, 3):
                    return subprocess.CompletedProcess(argv, 1, '[]\n', 'Error: No such object: ' + command[-1])
                return subprocess.CompletedProcess(argv, 0,
                    json.dumps([{'Config': {'Env': ['EXPECTED_SUBMISSION_SHA256=' + '0' * 64]}}]), '')
            if command[0] == 'wait':
                raise subprocess.TimeoutExpired(argv, 1)
            if command[0] == 'logs':
                return subprocess.CompletedProcess(argv, 0, 'generated partial output', 'generated diagnostic')
            return subprocess.CompletedProcess(argv, 0, 'generated\n', '')
        with mock.patch.object(portable.subprocess, 'run', side_effect=fake), \
                mock.patch.object(core, 'inspect_contract'):
            result, code = portable.execute_stage(core, ['fake-docker'], {}, {}, 'score', '0' * 64, self.root / 'stage')
        self.assertEqual(code, 3)
        self.assertFalse(result['scientific_score_computed'])
        verbs = [c[0] for c in calls]
        self.assertLess(verbs.index('logs'), verbs.index('rm'))
        receipt = json.loads((self.root / 'stage' / 'execution.json').read_text())
        self.assertEqual(receipt['recovered_logs']['stdout'], 'generated partial output')
        self.assertEqual(receipt['recovered_logs']['stderr'], 'generated diagnostic')
        self.assertTrue(receipt['absence_verified'])
        self.assertIn('execution.json', portable.stage_evidence(self.root / 'stage'))


if __name__ == '__main__':
    unittest.main()
