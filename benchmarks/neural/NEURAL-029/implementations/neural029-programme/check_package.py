"""Relocated generated checks; no real Docker, NumPy, targets or models.

The ten accepted boundary tests retain their byte-identical source. Their native
producer and numeric grader are inert leaves, not a scientific campaign.
"""
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

HERE = Path(__file__).resolve().parent


def load(name):
    path = HERE / (name + '.py')
    module = types.ModuleType('public_check_' + name)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


verifier = load('verify_source')
boundary = load('boundary_controls')


def admit_suite(result, count):
    verifier.need(result.testsRun == count and result.wasSuccessful()
                  and not result.failures and not result.errors and not result.skipped
                  and not result.expectedFailures and not result.unexpectedSuccesses,
                  'all expected methods must pass without any failure disposition')


def admit_populations(boundary_suite, packaging_suite):
    verifier.need(boundary_suite.countTestCases() == 10 and packaging_suite.countTestCases() == 8,
                  'exact ten boundary and eight packaging methods')


def manifest_pin(root):
    raw = (root / 'SOURCE_MANIFEST.json').read_bytes()
    return len(raw), hashlib.sha256(raw).hexdigest()


def copy_package(base):
    root = base / 'package'; root.mkdir()
    for path in HERE.iterdir():
        shutil.copyfile(path, root / path.name)
    return root


def command(root, size=None, digest=None):
    n, h = manifest_pin(root)
    return [sys.executable, '-I', '-S', '-B', str(root / 'verify_source.py'),
            '--manifest-bytes', str(n if size is None else size),
            '--manifest-sha256', h if digest is None else digest, '--check']


def run(argv, cwd):
    result = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=20)
    verifier.need(len(result.stdout) + len(result.stderr) <= 65536, 'bounded generated subprocess output')
    return result


def expected_result():
    return {'schema': 'neural029_public_generated_checks_v1', 'methods': 18,
            'boundary_methods': 10, 'packaging_methods': 8, 'failures': 0, 'errors': 0,
            'skipped': 0, 'expected_failures': 0, 'unexpected_successes': 0,
            'cache_regression_passed': True, 'real_Docker_calls': 0,
            'authentic_inputs_read': 0, 'model_calls': 0, 'scientific_qualification': False}


class PackageChecks(unittest.TestCase):
    def reject(self, change, expected, wrong_pin=False):
        with tempfile.TemporaryDirectory(prefix='neural029-package-refusal-') as temp:
            base = Path(temp).resolve(); root = copy_package(base)
            change(root)
            result = run(command(root, digest='f' * 64 if wrong_pin else None), base)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertEqual(result.stdout, b'')
            failure = json.loads(result.stderr)
            self.assertEqual(failure['status'], 'failed')
            self.assertIs(failure['scientific_qualification'], False)
            self.assertIn(expected, failure['reason'])

    def test_actual_inspection_cli_from_unrelated_directory(self):
        with tempfile.TemporaryDirectory(prefix='neural029-inspect-cwd-') as temp:
            size, digest = manifest_pin(HERE)
            result = run([sys.executable, '-I', '-S', '-B', str(HERE / 'run.py'), 'inspect',
                          '--source-bytes', str(size), '--source-sha256', digest], temp)
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(result.stdout)
            self.assertEqual(value['task_id'], 'NEURAL-029')
            self.assertEqual(value['submission_limit_bytes'], 100000000)
            for key in ('authentic_inputs_qualified', 'native_qualification', 'submission_ready'):
                self.assertIs(value[key], False)

    def test_wrong_manifest_pin_and_changed_runtime_refuse(self):
        self.reject(lambda root: None, 'authenticated source bytes', wrong_pin=True)
        def change(root):
            path = root / 'executor.py'; raw = path.read_bytes()
            path.write_bytes(raw[:-1] + (b'X' if raw[-1:] != b'X' else b'Y'))
        self.reject(change, 'authenticated source bytes')

    def test_missing_source_member_refuses(self):
        self.reject(lambda root: (root / 'core.py').unlink(), 'core.py')

    def test_linked_and_nonregular_members_refuse(self):
        def linked(root):
            path = root / 'core.py'; path.unlink(); path.symlink_to(root.parent / 'not-readable-source')
        self.reject(linked, 'ordinary exact source member')
        def fifo(root):
            path = root / 'core.py'; path.unlink(); os.mkfifo(path)
        self.reject(fifo, 'ordinary exact source member')

    def test_unlisted_file_refuses(self):
        self.reject(lambda root: (root / 'unselected.py').write_text('# not selected\n'), 'exact flat package population')
        self.reject(lambda root: (root / 'unselected.py').symlink_to(root.parent / 'unselected-target'),
                    'exact flat package population')

    def test_repinned_path_escape_and_boolean_extent_refuse(self):
        def rewrite(root, modify):
            path = root / 'SOURCE_MANIFEST.json'; value = json.loads(path.read_bytes())
            modify(value)
            path.write_text(json.dumps(value, sort_keys=True) + '\n')
        self.reject(lambda root: rewrite(root, lambda value: value['files'].update(
            {'../escape.py': {'bytes': 1, 'sha256': 'a' * 64}})), 'flat source member')
        self.reject(lambda root: rewrite(root, lambda value: value['files']['core.py'].update(
            {'bytes': True})), 'member extent')

    def test_result_protocol_rejects_dispositions_and_type_aliases(self):
        good = expected_result(); verifier.strict_result(good)
        for key in ('failures', 'errors', 'skipped', 'expected_failures', 'unexpected_successes'):
            for bad in (1, False):
                with self.subTest(key=key, bad=bad):
                    value = dict(good); value[key] = bad
                    with self.assertRaises(ValueError): verifier.strict_result(value)
        for change in ('missing', 'extra', 'count', 'boolean_count'):
            value = dict(good)
            if change == 'missing': del value['expected_failures']
            elif change == 'extra': value['unknown'] = 0
            elif change == 'count': value['methods'] = 17
            else: value['model_calls'] = False
            with self.assertRaises(ValueError): verifier.strict_result(value)
        class Tiny(unittest.TestCase):
            def runTest(self): pass
        for n, m in ((10, 8), (9, 9), (11, 7)):
            first = unittest.TestSuite(Tiny() for _ in range(n))
            second = unittest.TestSuite(Tiny() for _ in range(m))
            if (n, m) == (10, 8): admit_populations(first, second)
            else:
                with self.assertRaises(ValueError): admit_populations(first, second)

    def test_actual_unittest_expected_failures_skips_and_unexpected_successes_refuse(self):
        def passing(self): pass
        def unexpected_passing(self): pass
        def failing(self): self.fail('invented expected failure')
        def skipped(self): self.skipTest('invented skip')
        methods = [passing, unittest.expectedFailure(failing),
                   unittest.expectedFailure(unexpected_passing), skipped]
        for i, method in enumerate(methods):
            case = type('TinyDispositionControl', (unittest.TestCase,), {'test_one': method})
            result = unittest.TestResult(); case('test_one').run(result)
            if i == 0:
                admit_suite(result, 1)
            else:
                with self.assertRaises(ValueError): admit_suite(result, 1)


def main():
    verifier.need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
                  and not sys.flags.optimize, 'isolated unoptimized source controls')
    original_suite = unittest.defaultTestLoader.loadTestsFromTestCase(boundary.BoundaryControls)
    package_suite = unittest.defaultTestLoader.loadTestsFromTestCase(PackageChecks)
    admit_populations(original_suite, package_suite)
    suite = unittest.TestSuite([original_suite, package_suite])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    admit_suite(result, 18)
    with tempfile.TemporaryDirectory(prefix='neural029-cache-cwd-') as temp:
        cache = run([sys.executable, '-I', '-S', '-B', str(HERE / 'cache_regression.py')], temp)
    verifier.need(cache.returncode == 0, 'accepted cache regression failed')
    value = json.loads(cache.stdout)
    expected = {'cached_io_and_executor_ignored': True, 'local_stdlib_shadow_ignored': True,
                'actual_source_validator_reached': True, 'aggregate_arithmetic_checked': True,
                'real_Docker_calls': 0, 'authentic_inputs': 0}
    verifier.need(type(value) is dict and set(value) == set(expected), 'exact cache result')
    verifier.need(all(type(value[k]) is type(v) and value[k] == v for k, v in expected.items()),
                  'successful typed cache result')
    print(json.dumps(expected_result(), sort_keys=True))


if __name__ == '__main__':
    main()
