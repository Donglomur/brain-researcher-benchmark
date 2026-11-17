"""Generated controls; no authentic assets, targets, Docker or model execution."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent / 'registered-runtime'
spec = importlib.util.spec_from_file_location('sleep_portable', HERE / 'score.py')
portable = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portable)


class PortableSleepTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.shared = portable.helpers()
        self.submission = self.root / 'submission.npz'
        self.submission.write_bytes(b'generated captured submission')
        self.locations = {'schema_version': 1, 'candidate_id': 'NEURAL-007',
                          'comparators': {key: str(self.root / (key + '.npz')) for key in ('YASA', 'RF')},
                          'private_files': {name: str(self.root / name) for name in
                                            ('manifest.json', 'development-001_labels.npz', 'development-002_labels.npz')}}
        for path in self.locations['private_files'].values():
            Path(path).write_bytes(b'generated private-location file')
        self.descriptor = self.root / 'artifacts.json'
        self.descriptor.write_text(json.dumps(self.locations))
        self.args = argparse.Namespace(action='score', package_dir=str(PACKAGE), artifacts=str(self.descriptor),
                                       submission=str(self.submission), output_dir=str(self.root / 'out'),
                                       docker_cli='/unused/docker', docker_host='unix:///unused/socket', docker_config='/unused')

    def validated(self):
        return {'status': 'valid_prediction_contract', 'prediction_contract_valid': True,
                'epoch_count': 5450, 'people': 2, 'comparators': ['YASA', 'RF'],
                'private_loader_calls': 0, 'private_assets_read': False,
                'submission_sha256': self.shared.pin(self.submission.read_bytes())['sha256']}

    def scored(self):
        return {'status': 'scored', 'private_loader_calls': 1, 'result': {'n_people': 2,
                'candidate': {'per_person': [{'person_id': key, 'full_epochs': number}
                                            for key, number in portable.CASES.items()]},
                'comparators': {'YASA': {}, 'RF': {}}}}

    def run_mocked(self, responses):
        def stage(*args):
            args[5].mkdir()
            value, code = responses.pop(0)
            self.shared.save(args[5] / 'worker.json', value)
            return value, code
        with mock.patch.object(portable, 'helpers', return_value=self.shared), \
                mock.patch.object(self.shared, 'runtime_options', return_value=(['fake-docker'], {})), \
                mock.patch.object(portable, 'execute_stage', side_effect=stage) as execute:
            result, code = portable.run(self.args)
        return result, code, execute

    def test_exact_current_source_and_unchanged_numerical_helpers(self):
        core, plan, source = portable.capture_source(PACKAGE, self.root / 'source', self.shared)
        self.assertEqual(core.IMAGE, plan['image'])
        self.assertEqual(set(source), {'score.py', 'grader.py', 'operator_assets.json', 'execution_pins.json',
                                       'candidate_adapter.py', 'integration_helper.py', 'validate.py'})
        for name in ('score.py', 'grader.py', 'operator_assets.json'):
            self.assertEqual((PACKAGE / name).read_bytes(), (self.root / 'source' / name).read_bytes())
        self.assertEqual(source['integration_helper.py'], {k: plan['source_files']['integration_helper.py'][k]
                                                          for k in ('bytes', 'sha256')})

    def test_changed_runtime_is_rejected_before_import(self):
        altered = self.root / 'registered-runtime'
        shutil.copytree(PACKAGE, altered)
        with (altered / 'score.py').open('ab') as stream:
            stream.write(b'\nraise RuntimeError("must never execute")\n')
        with self.assertRaisesRegex(ValueError, 'Registered source changed'):
            portable.capture_source(altered, self.root / 'source', self.shared)
        self.assertFalse((self.root / 'source').exists())

    def test_changed_helper_is_rejected_before_import(self):
        fake = self.root / 'portable-grading'
        fake.mkdir()
        source = self.root / 'NEURAL-077/implementations/portable-grading'
        source.mkdir(parents=True)
        (source / 'score.py').write_text('raise RuntimeError("must never execute")')
        with mock.patch.object(portable, 'HERE', self.root / 'NEURAL-007/implementations/portable-grading'):
            with self.assertRaisesRegex(ValueError, 'pinned ordinary file'):
                portable.helpers()

    def test_artifact_schema_refuses_private_keys_in_validation_and_duplicates(self):
        with self.assertRaisesRegex(ValueError, 'schema'):
            portable.artifact_locations(self.descriptor, 'validate', self.shared)
        self.descriptor.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            portable.artifact_locations(self.descriptor, 'score', self.shared)

    def test_declared_public_private_aliases_fail_without_path_reads(self):
        self.locations['private_files']['manifest.json'] = self.locations['comparators']['YASA']
        self.descriptor.write_text(json.dumps(self.locations))
        with self.assertRaisesRegex(ValueError, 'aliases rejected'):
            portable.artifact_locations(self.descriptor, 'score', self.shared)

    def test_private_locations_are_not_touched_when_submission_is_invalid(self):
        # Even missing private files must not prevent public-only candidate refusal.
        for path in self.locations['private_files'].values():
            Path(path).unlink()
        touched = []
        original = self.shared.unlinked
        def checked(path):
            if str(path) in self.locations['private_files'].values():
                touched.append(str(path))
                raise AssertionError('premature target path access')
            return original(path)
        with mock.patch.object(self.shared, 'unlinked', side_effect=checked):
            result, code, execute = self.run_mocked([({'status': 'invalid_submission', 'private_loader_calls': 0}, 2)])
        self.assertEqual(code, 2)
        self.assertEqual(execute.call_count, 1)
        self.assertFalse(touched)
        mounts = execute.call_args.args[3]
        self.assertFalse(any(path.startswith('/private/') for path in mounts))
        self.assertNotIn('/source/integration_helper.py', mounts)

    def test_incomplete_public_receipts_refuse_private_dispatch(self):
        for field, bad in (('epoch_count', 5449), ('people', 1), ('private_loader_calls', 1),
                           ('private_assets_read', True), ('submission_sha256', '0' * 64), ('comparators', ['YASA'])):
            self.args.output_dir = str(self.root / field)
            result, code, execute = self.run_mocked([(dict(self.validated(), **{field: bad}), 0)])
            with self.subTest(field=field):
                self.assertEqual(code, 3)
                self.assertEqual(execute.call_count, 1)
                self.assertIn('Incomplete public validation receipt', result['error'])

    def test_full_scoring_uses_same_candidate_then_original_grader(self):
        result, code, execute = self.run_mocked([(self.validated(), 0), (self.scored(), 0)])
        self.assertEqual(code, 0)
        first, second = execute.call_args_list
        self.assertEqual(first.args[3]['/submission/predictions.npz'], second.args[3]['/submission/predictions.npz'])
        self.assertTrue(first.args[3]['/source/grader.py'].endswith('/validate.py'))
        self.assertTrue(second.args[3]['/source/grader.py'].endswith('/grader.py'))
        self.assertEqual(len([k for k in second.args[3] if k.startswith('/private/')]), 3)
        self.assertEqual(result['status'], 'scored')

    def test_private_failure_preserves_loader_attempt_count(self):
        failure = {'status': 'operator_error', 'private_loader_calls': 1, 'error': 'frozen input digest differs'}
        result, code, _ = self.run_mocked([(self.validated(), 0), (failure, 3)])
        self.assertEqual((result, code), (failure, 3))
        self.assertEqual(json.loads((Path(self.args.output_dir) / 'result.json').read_text()), failure)

    def test_comparator_failure_cannot_dispatch_private_stage(self):
        result, code, execute = self.run_mocked([({'status': 'operator_error', 'private_loader_calls': 0}, 3)])
        self.assertEqual(code, 3)
        self.assertEqual(execute.call_count, 1)

    def test_validate_needs_only_comparator_locations(self):
        self.args.action = 'validate'
        self.descriptor.write_text(json.dumps({k: v for k, v in self.locations.items() if k in portable.PUBLIC_KEYS}))
        result, code, execute = self.run_mocked([(self.validated(), 0)])
        self.assertEqual(code, 0)
        self.assertEqual(execute.call_count, 1)

    def test_existing_output_refused_without_input_access(self):
        output = Path(self.args.output_dir)
        output.mkdir()
        (output / 'prior').write_bytes(b'preserve')
        with mock.patch.object(portable, 'capture_source') as capture:
            with self.assertRaises(FileExistsError):
                portable.run(self.args)
        capture.assert_not_called()
        self.assertEqual((output / 'prior').read_bytes(), b'preserve')

    def test_receipts_and_snapshots_are_read_only_and_hashed(self):
        self.run_mocked([({'status': 'invalid_submission'}, 2)])
        output = Path(self.args.output_dir)
        receipt = json.loads((output / 'receipt.json').read_text())
        self.assertEqual(receipt['submission'], self.shared.pin((output / 'submission.npz').read_bytes()))
        self.assertEqual(receipt['result'], self.shared.pin((output / 'result.json').read_bytes()))
        for name in ('result.json', 'receipt.json', 'submission.npz', 'invocation.json'):
            self.assertEqual((output / name).stat().st_mode & 0o222, 0)

    def test_changed_captured_submission_cannot_be_successful(self):
        def stage(*args):
            args[5].mkdir()
            captured = Path(args[3]['/submission/predictions.npz'])
            captured.chmod(0o644)
            captured.write_bytes(b'changed')
            return self.validated(), 0
        self.args.action = 'validate'
        self.descriptor.write_text(json.dumps({k: v for k, v in self.locations.items() if k in portable.PUBLIC_KEYS}))
        with mock.patch.object(portable, 'helpers', return_value=self.shared), \
                mock.patch.object(self.shared, 'runtime_options', return_value=(['fake'], {})), \
                mock.patch.object(portable, 'execute_stage', side_effect=stage):
            result, code = portable.run(self.args)
        self.assertEqual(code, 3)
        self.assertIn('Captured candidate changed', result['error'])

    def test_sleep_create_retains_original_limits_and_disables_pull(self):
        core, _, _ = portable.capture_source(PACKAGE, self.root / 'source', self.shared)
        argv = portable.create_argv(core, 'owned', {'/source/grader.py': '/absolute/grader.py'})
        self.assertEqual(argv[argv.index('--pull') + 1], 'never')
        self.assertEqual(argv[argv.index('--memory') + 1], str(4 * 1024**3))
        self.assertEqual(argv[argv.index('--pids-limit') + 1], '32')
        self.assertEqual(argv[argv.index('--log-driver') + 1], 'none')
        self.assertEqual(argv[-4:], [core.IMAGE, '-I', '-B', '/source/grader.py'])

    def test_mount_encoding_rejects_output_or_source_delimiters(self):
        core, _, _ = portable.capture_source(PACKAGE, self.root / 'source', self.shared)
        for source in ('/path,readonly=false', '/path\nnext', '/path\x00end'):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'Unsafe mount encoding'):
                portable.create_argv(core, 'owned', {'/source/grader.py': source})

    def test_prestart_refusal_removes_only_owned_container(self):
        core, _, _ = portable.capture_source(PACKAGE, self.root / 'source', self.shared)
        calls = []
        def fake(argv, **kwargs):
            command = argv[1:]
            calls.append(command)
            if command[:2] == ['image', 'inspect']:
                return subprocess.CompletedProcess(argv, 0, json.dumps([{'Id': core.IMAGE, 'Config': {'Env': []}}]), '')
            if command[0] == 'inspect':
                count = len([c for c in calls if c[0] == 'inspect'])
                if count in (1, 3):
                    return subprocess.CompletedProcess(argv, 1, '[]', 'Error: No such object: ' + command[-1])
                return subprocess.CompletedProcess(argv, 0, '[{}]', '')
            return subprocess.CompletedProcess(argv, 0, 'created', '')
        with mock.patch.object(portable.subprocess, 'run', side_effect=fake):
            result, code = portable.execute_stage(core, ['fake'], {}, {}, 'validate', self.root / 'stage', self.shared)
        self.assertEqual(code, 3)
        self.assertFalse(any(c[0] == 'start' for c in calls))
        removed = next(c for c in calls if c[:2] == ['rm', '--force'])
        self.assertTrue(removed[-1].startswith('neural007-portable-'))
        receipt = json.loads((self.root / 'stage/execution.json').read_text())
        self.assertTrue(receipt['absence_verified'])

    def test_attached_timeout_retains_partial_output_and_cleanup(self):
        core, _, _ = portable.capture_source(PACKAGE, self.root / 'source', self.shared)
        calls = []
        def fake(argv, **kwargs):
            command = argv[1:]
            calls.append(command)
            if command[:2] == ['image', 'inspect']:
                return subprocess.CompletedProcess(argv, 0, json.dumps([{'Id': core.IMAGE, 'Config': {'Env': []}}]), '')
            if command[0] == 'inspect':
                count = len([c for c in calls if c[0] == 'inspect'])
                if count in (1, 3):
                    return subprocess.CompletedProcess(argv, 1, '[]', 'Error: No such object: ' + command[-1])
                return subprocess.CompletedProcess(argv, 0, '[{}]', '')
            if command[0] == 'start':
                raise subprocess.TimeoutExpired(argv, 1, output=b'partial output', stderr=b'partial failure')
            return subprocess.CompletedProcess(argv, 0, 'created', '')
        with mock.patch.object(portable.subprocess, 'run', side_effect=fake), mock.patch.object(core, 'verify'):
            result, code = portable.execute_stage(core, ['fake'], {}, {}, 'score', self.root / 'stage', self.shared)
        self.assertEqual(code, 3)
        receipt = json.loads((self.root / 'stage/execution.json').read_text())
        self.assertEqual(receipt['timed_out_command']['stdout'], 'partial output')
        self.assertEqual(receipt['timed_out_command']['stderr'], 'partial failure')
        self.assertTrue(receipt['absence_verified'])


if __name__ == '__main__':
    unittest.main()
