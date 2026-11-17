"""Generated source controls only; no candidate, private asset or Docker access."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'benchmarks/neural/NEURAL-077/implementations/registered-runtime'
CURRENT_PIN = (2479, 'd72583caeec307b51254fd541ee5bf9e8ee0de407ef692d0dbcefcfde6ed4544')
HISTORICAL_WORKER = '2becee8830ee743d1d637e89fcbcfa0c9f8208c670ea73a070189671c0ba1ba2'
CURRENT_WORKER = 'cdeeb2019a17b0da8c809a796bab044dba54eae422436236fc2c27cb2565a88e'


def identity(body):
    return len(body), hashlib.sha256(body).hexdigest()


def load_source(name, filename):
    module = types.ModuleType(name)
    module.__file__ = str(PACKAGE / filename)
    exec(compile((PACKAGE / filename).read_bytes(), module.__file__, 'exec'), module.__dict__)
    return module


class CurrentSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Authenticate all current source bytes before importing package code.
        body = (PACKAGE / 'CURRENT_SOURCE.json').read_bytes()
        if identity(body) != CURRENT_PIN:
            raise AssertionError('Reviewed current source descriptor changed')
        cls.current = json.loads(body)
        if {p.name for p in PACKAGE.iterdir()} != set(cls.current['files']) | {'CURRENT_SOURCE.json'}:
            raise AssertionError('Current package member inventory changed')
        for filename, pin in cls.current['files'].items():
            if identity((PACKAGE / filename).read_bytes()) != (pin['bytes'], pin['sha256']):
                raise AssertionError('Current source changed: ' + filename)
        with mock.patch.dict(sys.modules, {'absence': load_source('_neural077_absence', 'absence.py')}), \
                mock.patch.object(sys, 'path', list(sys.path)):
            cls.score = load_source('_neural077_score', 'score.py')

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='neural077-source-controls-')
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.package = self.directory / 'package'
        shutil.copytree(PACKAGE, self.package)

    def write_descriptor(self, value):
        (self.package / 'CURRENT_SOURCE.json').write_text(json.dumps(value))

    def test_historical_freeze_preserves_stale_worker_pin(self):
        historical = json.loads((self.package / 'SOURCE_FREEZE.json').read_text())
        self.assertEqual(historical['files']['worker.py']['sha256'], HISTORICAL_WORKER)
        self.assertEqual(identity((self.package / 'worker.py').read_bytes())[1], CURRENT_WORKER)
        self.assertNotEqual(historical['files']['worker.py']['sha256'], CURRENT_WORKER)
        self.assertEqual(identity((self.package / 'SOURCE_FREEZE.json').read_bytes()),
                         (1128, '2e5229e534d9efaee31c408bc0079e1cf8c90b722e5e536bd385815bee9d0839'))

    def test_complete_current_source_authenticates(self):
        result = self.score.verify_source(self.package)
        self.assertEqual((result['bytes'], result['sha256']), CURRENT_PIN)
        self.assertEqual(result['path'], 'CURRENT_SOURCE.json')
        self.assertEqual(result['predecessor'], self.current['predecessor'])
        self.assertEqual(len(self.current['files']), 11)

    def test_each_source_mutation_is_rejected(self):
        for filename in self.current['files']:
            with self.subTest(filename=filename):
                path = self.package / filename
                original = path.read_bytes()
                path.write_bytes(original + b'\n')
                try:
                    with self.assertRaisesRegex(ValueError, 'Current package source changed: ' + filename):
                        self.score.verify_source(self.package)
                finally:
                    path.write_bytes(original)

    def test_missing_and_unexpected_package_members_are_rejected(self):
        path = self.package / 'worker.py'
        original = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing or unexpected package source member'):
            self.score.verify_source(self.package)
        path.write_bytes(original)
        for filename in ('unexpected.py', '__pycache__'):
            extra = self.package / filename
            extra.mkdir()
            with self.assertRaisesRegex(ValueError, 'Missing or unexpected package source member'):
                self.score.verify_source(self.package)
            extra.rmdir()

    def test_descriptor_cannot_omit_or_add_members(self):
        for action in ('omit', 'add', 'traversal'):
            with self.subTest(action=action):
                value = json.loads(json.dumps(self.current))
                if action == 'omit':
                    del value['files']['worker.py']
                else:
                    value['files']['../worker.py' if action == 'traversal' else 'other.py'] = value['files']['worker.py']
                self.write_descriptor(value)
                with self.assertRaisesRegex(ValueError, 'Exact current source file inventory required'):
                    self.score.verify_source(self.package)

    def test_descriptor_identity_schema_duplicates_and_bounds_are_checked(self):
        for field, value in (('candidate_id', 'NEURAL-078'), ('schema_version', True),
                             ('kind', 'historical_source'), ('extra', 'unrecognized')):
            with self.subTest(field=field):
                changed = dict(self.current, **{field: value})
                self.write_descriptor(changed)
                with self.assertRaises(ValueError):
                    self.score.verify_source(self.package)
        descriptor = self.package / 'CURRENT_SOURCE.json'
        descriptor.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaisesRegex(ValueError, 'Duplicate current source descriptor key'):
            self.score.verify_source(self.package)
        descriptor.write_bytes(b' ' * 32769)
        with self.assertRaisesRegex(ValueError, 'Bounded regular file required'):
            self.score.verify_source(self.package)

    def test_historical_predecessor_cannot_be_rewritten_and_repinned(self):
        path = self.package / 'SOURCE_FREEZE.json'
        path.write_bytes(path.read_bytes() + b'\n')
        size, digest = identity(path.read_bytes())
        value = json.loads(json.dumps(self.current))
        value['files'][path.name] = {'bytes': size, 'sha256': digest}
        self.write_descriptor(value)
        with self.assertRaisesRegex(ValueError, 'Historical source freeze pin changed'):
            self.score.verify_source(self.package)
        value['predecessor'].update(bytes=size, sha256=digest)
        self.write_descriptor(value)
        with self.assertRaisesRegex(ValueError, 'Historical source predecessor changed'):
            self.score.verify_source(self.package)

    def test_linked_or_nonregular_members_are_rejected(self):
        path = self.package / 'worker.py'
        outside = self.directory / 'worker-copy.py'
        path.rename(outside)
        path.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'Linked path rejected'):
            self.score.verify_source(self.package)
        path.unlink()
        os.link(outside, path)
        with self.assertRaisesRegex(ValueError, 'Bounded regular file required'):
            self.score.verify_source(self.package)
        path.unlink()
        path.mkdir()
        with self.assertRaisesRegex(ValueError, 'Bounded regular file required'):
            self.score.verify_source(self.package)

    def test_cli_selects_current_before_any_submission_or_external_asset_read(self):
        output = self.directory / 'unused-result.json'
        missing = self.directory / 'generated-absent-input.npz'
        command = [sys.executable, '-I', '-S', '-B', str(self.package / 'score.py'),
                   'score', '--submission', str(missing), '--output', str(output)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt['status'], 'preflight_rejected_no_score')
        self.assertIn('FileNotFoundError', receipt['error'])
        self.assertIn(missing.name, receipt['error'])
        self.assertFalse(output.exists())
        self.assertFalse(output.with_name(output.name + '.ownership.json').exists())
        (self.package / 'worker.py').write_bytes((self.package / 'worker.py').read_bytes() + b'\n')
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('Current package source changed: worker.py', json.loads(result.stdout)['error'])

    def test_failed_target_attempt_retains_counter_repair(self):
        # Run only worker control flow with generated stubs; the target read
        # fails before NumPy or metrics can touch data. No real model runs.
        numpy = types.ModuleType('numpy')
        validator = types.ModuleType('validator')
        validator.validate = mock.Mock(return_value={'development-001': [0.5]})
        validator.InvalidSubmission = ValueError
        metrics = types.ModuleType('metrics')
        metrics.score_candidate = lambda ordered, loader, reference: loader('development-001')
        with mock.patch.dict(sys.modules, {'numpy': numpy, 'validator': validator, 'metrics': metrics}), \
                mock.patch.object(sys, 'path', list(sys.path)):
            worker = load_source('_neural077_worker', 'worker.py')
        peak = mock.Mock()
        peak.read_text.return_value = '0'
        with mock.patch.object(sys, 'argv', ['worker.py', 'score']), \
                mock.patch.dict(os.environ, {'EXPECTED_SUBMISSION_SHA256': '0' * 64}), \
                mock.patch.object(worker, 'public_ids', return_value={'development-001': ['generated-id']}), \
                mock.patch.object(worker, 'frozen_submission', return_value='generated-placeholder'), \
                mock.patch.object(worker, 'references', return_value={}), \
                mock.patch.object(worker, 'pinned', side_effect=ValueError('generated target-read refusal')) as read, \
                mock.patch.object(worker, 'Path', return_value=peak):
            result, code = worker.main()
        read.assert_called_once()
        self.assertEqual(code, 2)
        self.assertEqual(result['target_loader_invocations'], 1)
        self.assertEqual(result['status'], 'scoring_error')
        self.assertIn('generated target-read refusal', result['error'])
        self.assertFalse(result['scientific_score_computed'])


if __name__ == '__main__':
    unittest.main()
