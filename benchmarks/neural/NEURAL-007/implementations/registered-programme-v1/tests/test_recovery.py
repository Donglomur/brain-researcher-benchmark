"""Generated metadata/source controls; no task arrays, Docker or model calls."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import signal
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[1]
ANCHOR = 'authoring/sleep-eog/program-runner-v1'
WRITTEN = 0


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def write(path, body):
    global WRITTEN
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    WRITTEN += len(body)
    return pin(body)


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class Recovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='sleep007-source-')
        cls.root = Path(cls.temp.name).resolve()
        cls.original = json.loads((SOURCE / 'ORIGINAL_SOURCE.json').read_bytes())
        cls.freeze = json.loads((SOURCE / ANCHOR / 'FREEZE.json').read_bytes())
        cls.external = set()
        for row in cls.original['declared_members']:
            rel = row['path']
            if row['disposition'] == 'external_operator_prerequisite':
                cls.external.add(rel)
                body = encoded({'generated': True, 'logical_path': rel})
            else:
                body = (SOURCE / rel).read_bytes()
            cls.freeze['files'][rel] = write(cls.root / rel, body)
        cls.freeze_body = encoded(cls.freeze)
        write(cls.root / ANCHOR / 'FREEZE.json', cls.freeze_body)
        cls.outer = module(cls.root / ANCHOR / 'run_outer.py', '_sleep007_generated_outer')
        cls.plan = json.loads((cls.root / ANCHOR / 'PLAN.json').read_bytes())
        cls.serial = 0

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        type(self).serial += 1
        self.case = self.root / 'artifacts-build' / ('generated-' + str(self.serial))
        self.case.mkdir(mode=0o700)
        self.env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env)

    def review(self, mode='qualify', total=3500.0):
        prior = {'candidate_id': 'NEURAL-007', 'mode': 'qualify',
                 'all_owned_absent': True, 'all_activated_groups_absent': True,
                 'prior_known_wall_seconds': total - 240, 'charged_seconds': 240,
                 'known_wall_seconds_after': total,
                 'conservative_YASA_associated_allocation_seconds_after': 900.0}
        p = self.case / 'prior' / 'outer_receipt.json'
        prior_pin = {'path': str(p.relative_to(self.root)), **write(p, encoded(prior))}
        whole = 180 if mode == 'qualify' else 100
        return {'decision': 'authorize_one_sleep_program_' + mode,
                'freeze_sha256': pin(self.freeze_body)['sha256'], 'whole_seconds': whole,
                'artifact_reserve_bytes': 12_000_000, 'other_reserve_bytes': 0,
                'output_path': str((self.case / 'attempt').relative_to(self.root)),
                'prior_receipt': prior_pin, 'prior_known_wall_seconds': total,
                'prospective_known_wall_seconds_after': total + whole,
                'candidate_cumulative_ceiling_seconds': total + whole,
                'docker_host': 'unix:///generated/operator/docker.sock',
                'conservative_YASA_associated_allocation_seconds_before': 900.0,
                'conservative_YASA_associated_allocation_seconds_after': 900.0 + whole}

    def qualify(self, review, freeze_sha=None):
        value = {'status': 'passed', 'mode': 'qualify',
                 'source_freeze_sha256': freeze_sha or review['freeze_sha256'],
                 'all_owned_absent': True, 'all_activated_groups_absent': True}
        p = self.case / 'qualification' / 'outer_receipt.json'
        review['qualified_outer_receipt'] = {'path': str(p.relative_to(self.root)), **write(p, encoded(value))}

    def dispatch(self, review, mode='qualify'):
        global WRITTEN
        path = self.case / ('review-' + str(time.monotonic_ns()) + '.json')
        write(path, encoded(review))
        out = self.root / review['output_path']
        argv = ['run_outer.py', '--mode', mode, '--review', str(path), '--output', str(out), '--other-reserve-bytes', '0']
        if mode == 'submission':
            argv += ['--program', str(self.case / 'not-opened-program.py')]
        calls, alarms = [], []
        initial = time.monotonic() - 12.0
        old_durable = self.outer.durable

        def durable(*args):
            global WRITTEN
            old_durable(*args)
            WRITTEN += args[0].stat().st_size

        def admitted(args, freeze, captured_review, plan):
            calls.append({'endpoint': os.environ['NEURAL007_DOCKER_HOST'], 'mode': args.mode,
                          'deadline': self.outer.DEADLINE, 'origin': self.outer.STARTED})
            self.outer.latest_prior(captured_review, plan, args.mode, captured_review['freeze_sha256'])
            durable(out / 'outer_receipt.json', {'generated_admission_sentinel': True})
            return 0

        with patch.object(sys, 'argv', argv), patch.object(self.outer, 'STARTED', initial), \
             patch.object(self.outer, 'execute', side_effect=admitted), patch.object(self.outer, 'durable', side_effect=durable), \
             patch.object(signal, 'getitimer', return_value=(0., 0.)), patch.object(signal, 'getsignal', return_value=signal.SIG_DFL), \
             patch.object(signal, 'signal'), patch.object(signal, 'setitimer', side_effect=lambda *x: alarms.append(x)), \
             patch('subprocess.Popen', side_effect=AssertionError('No process launch')), \
             patch('subprocess.run', side_effect=AssertionError('No command launch')):
            result = self.outer.dispatch()
        return result, calls, alarms

    def test_complete_source_and_unchanged_scientific_closure(self):
        original_rows = self.original['declared_members']
        self.assertEqual(len(original_rows), 51)
        self.assertEqual(len(self.external), 6)
        current = json.loads((SOURCE / ANCHOR / 'FREEZE.json').read_bytes())
        changed = set()
        for row in original_rows:
            rel = row['path']
            if rel in self.external:
                self.assertFalse((SOURCE / rel).exists())
                self.assertEqual(current['files'][rel], row['original'])
            else:
                self.assertEqual(pin((SOURCE / rel).read_bytes()), current['files'][rel])
                if current['files'][rel] != row['original']:
                    changed.add(rel)
        self.assertEqual(changed, {
            'authoring/dmfc-timing/program-runner-v2/engine.py',
            'authoring/shared-program-runner-v2/QUALIFIED_IMPORTS.json',
            ANCHOR + '/run_outer.py',
            'benchmarks/neuroscience/neural-007-whole-night-sleep-scoring/score.py',
        })
        source = json.loads((SOURCE / 'SOURCE.json').read_bytes())
        for rel, expected in source['files'].items():
            self.assertEqual(pin((SOURCE / rel).read_bytes()), expected, rel)

    def test_actual_relative_imports_complete_case_metadata_and_no_dispatch(self):
        old_modules, old_path = dict(sys.modules), list(sys.path)
        try:
            self.outer.bind_endpoint({'docker_host': 'unix:///generated/operator/docker.sock'})
            sys.path.insert(0, str(self.root / ANCHOR))
            with patch('subprocess.Popen', side_effect=AssertionError('No process launch')), \
                 patch('subprocess.run', side_effect=AssertionError('No command launch')):
                common = __import__('sleep_common')
                driver = __import__('driver')
                units = common.units()
                self.assertEqual([x['unit_id'] for x in units], ['development-001', 'development-002'])
                self.assertTrue(all(len(x['public_inputs']) == 24 for x in units))
                profile = common.profile()
                self.assertEqual(sum(x['epochs'] for x in profile['training'] if x['role'] == 'training_labels'), 16290)
                self.assertEqual([x['epochs'] for x in profile['units']], [2780, 2670])
                self.assertEqual(common.ENV['DOCKER_HOST'], 'unix:///generated/operator/docker.sock')
                self.assertEqual(common.DOCKER, '/usr/local/bin/docker')
                self.assertEqual(driver.grade.__module__, 'driver')
                pinfile = json.loads((self.root / 'authoring/shared-program-runner-v2/QUALIFIED_IMPORTS.json').read_bytes())
                for value in pinfile['files'].values():
                    self.assertEqual(pin((self.root / value['path']).read_bytes()), {k: value[k] for k in ('bytes', 'sha256')})
        finally:
            sys.path[:] = old_path
            for name in list(sys.modules):
                if name not in old_modules:
                    del sys.modules[name]
            sys.modules.update(old_modules)

    def test_review_bound_endpoint_and_original_clocks(self):
        review = self.review()
        os.environ['NEURAL007_DOCKER_HOST'] = 'unix:///unreviewed/stale.sock'
        result, calls, alarms = self.dispatch(review)
        self.assertEqual(result, 0)
        self.assertEqual(calls[0]['endpoint'], review['docker_host'])
        self.assertEqual(calls[0]['deadline'] - calls[0]['origin'], 180)
        self.assertTrue(97 < alarms[0][1] <= 98)
        for endpoint in (None, '', 'tcp://host:2375', 'unix://relative', 'unix:///a/../b', 'unix:///a\nb', 'unix:///a,b'):
            with self.subTest(endpoint=endpoint), self.assertRaises((KeyError, ValueError)):
                self.outer.bind_endpoint({'docker_host': endpoint})
        with self.assertRaises(KeyError):
            self.outer.bind_endpoint({})

    def test_missing_external_or_drift_refuses_before_runtime_import(self):
        rel = sorted(self.external)[0]
        path = self.root / rel
        before = path.read_bytes()
        try:
            path.unlink()
            with self.assertRaises(FileNotFoundError):
                self.dispatch(self.review())
            self.assertTrue((self.case / 'attempt/preflight_or_outer_failure.json').is_file())
            write(path, before + b'changed')
            review = self.review()
            review['output_path'] += '-drift'
            with self.assertRaisesRegex(ValueError, 'Exact source freeze'):
                self.dispatch(review)
        finally:
            write(path, before)

    def test_latest_closed_cost_required_for_both_modes(self):
        for total in (1010.0258648320159, 1190.025864832016, 2270.025864832015):
            for mode in ('qualify', 'submission'):
                with self.subTest(total=total, mode=mode), self.assertRaises(ValueError):
                    review = self.review(mode, total)
                    self.outer.latest_prior(review, self.plan, mode, review['freeze_sha256'])
        review = self.review(total=4500.0)
        self.assertEqual(self.outer.latest_prior(review, self.plan, 'qualify', review['freeze_sha256']), 900.0)
        for field, value in [('all_owned_absent', False), ('all_activated_groups_absent', False),
                             ('known_wall_seconds_after', 4400.0), ('charged_seconds', 239.0),
                             ('candidate_id', 'NEURAL-000')]:
            changed = copy.deepcopy(review)
            path = self.root / changed['prior_receipt']['path']
            before = path.read_bytes()
            data = json.loads(before); data[field] = value
            changed['prior_receipt'].update(write(path, encoded(data)))
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.outer.latest_prior(changed, self.plan, 'qualify', changed['freeze_sha256'])
            write(path, before)
        missing = copy.deepcopy(review)
        missing['prior_receipt']['path'] = 'artifacts-build/missing/outer_receipt.json'
        with self.assertRaises(FileNotFoundError):
            self.outer.latest_prior(missing, self.plan, 'qualify', missing['freeze_sha256'])

    def test_submission_requires_same_current_qualification(self):
        review = self.review('submission')
        with self.assertRaises(KeyError):
            self.outer.latest_prior(review, self.plan, 'submission', review['freeze_sha256'])
        self.qualify(review, '0' * 64)
        with self.assertRaisesRegex(ValueError, 'Same source closure'):
            self.outer.latest_prior(review, self.plan, 'submission', review['freeze_sha256'])
        self.qualify(review)
        result, calls, alarms = self.dispatch(review, 'submission')
        self.assertEqual(result, 0)
        self.assertEqual(calls[0]['deadline'] - calls[0]['origin'], 100)
        self.assertTrue(57 < alarms[0][1] <= 58)

    def test_stale_or_insufficient_allocation_refuses_before_execute(self):
        for ceiling in (1200.0, 3500.0, 3679.0):
            review = self.review()
            review['output_path'] += '-' + str(int(ceiling))
            review['candidate_cumulative_ceiling_seconds'] = ceiling
            with self.subTest(ceiling=ceiling), self.assertRaisesRegex(ValueError, 'Explicit prospective cumulative allocation'):
                self.dispatch(review)

    def test_nonfinite_boolean_or_negative_accounting_refuses(self):
        for value in (float('inf'), float('nan'), -1, True, '3500', 10 ** 1000):
            with self.subTest(value=str(value)[:24]), self.assertRaisesRegex(ValueError, 'Finite nonnegative'):
                self.outer.amount(value)
        review = self.review()
        path = self.root / review['prior_receipt']['path']
        original = json.loads(path.read_bytes())
        for key in ('known_wall_seconds_after', 'prior_known_wall_seconds', 'charged_seconds',
                    'conservative_YASA_associated_allocation_seconds_after'):
            value = copy.deepcopy(original)
            value[key] = float('inf')
            changed = copy.deepcopy(review)
            changed['prior_receipt'].update(write(path, json.dumps(value).encode()))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'Finite nonnegative'):
                self.outer.latest_prior(changed, self.plan, 'qualify', review['freeze_sha256'])
        write(path, encoded(original))


if __name__ == '__main__':
    print(json.dumps({'python': platform.python_version(), 'dependencies': 'standard library only',
                      'scope': 'generated source/metadata, no scientific arrays, processes, Docker or model calls'}))
    try:
        unittest.main(verbosity=2)
    finally:
        print(json.dumps({'generated_file_body_writes_bytes': WRITTEN, 'native_calls': 0, 'arrays_read': 0}))
