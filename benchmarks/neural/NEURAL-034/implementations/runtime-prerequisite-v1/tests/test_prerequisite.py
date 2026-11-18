"""Generated source/lifecycle guards; never invoke Docker or original data."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import configure
import run as driver
import support as s
import probe
import controller


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='neural034-runtime-generated-')
        cls.base = Path(cls.temp.name).resolve()
        cls.root = cls.base / 'workspace'
        prior = os.umask(0o077)
        try:
            cls.configured = configure.configure(HERE.parents[4], cls.root)
            cls.fixture = driver.fixtures(cls.root, cls.configured)
        finally:
            os.umask(prior)
        with mock.patch.dict(os.environ, {'NEURAL034_DOCKER': '/no-docker-in-generated-tests',
                                         'NEURAL034_DOCKER_HOST': 'unix:///no-engine-in-generated-tests'}):
            cls.api, cls.recover = s.runtime(cls.root, cls.configured['source_freeze'])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_complete_typed_serialization_and_public_modes_under077(self):
        self.assertEqual(len(self.fixture['units']), 2)
        for index, unit in enumerate(self.fixture['units']):
            asset = unit['public_inputs'][0]; path = self.root / asset['path']
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o444)
            self.assertLess(path.stat().st_size, 32768)
            self.assertEqual(s.pin(s.read(path)), {k: asset[k] for k in ('bytes', 'sha256')})
            ids, selected = probe.packet(path)
            self.assertEqual(ids, unit['expected_ids']); self.assertEqual(selected, index + 1)
        self.assertTrue(all(Path(p).is_file() for p in self.fixture['unmounted_canaries']))
        program = self.root / self.fixture['program']['path']
        self.assertEqual(stat.S_IMODE(program.stat().st_mode), 0o444)
        self.assertEqual(s.pin(s.read(program)), {k: self.fixture['program'][k] for k in ('bytes', 'sha256')})
        self.assertNotIn('HOST_CANARIES = ()', program.read_text())

    def test_exact_current_source_and_no_authentic_profile_or_grader_call(self):
        self.assertEqual(configure.load(self.root), self.configured)
        self.assertFalse((self.root / 'benchmarks/neuroscience/neural-034/public/cases.json').exists())
        self.assertFalse((self.root / 'artifacts-build/glial-context-002').exists())
        self.assertEqual(self.api.profile.runtime(self.fixture['units'][0]),
            {'public_destinations': ('/input/public.npz',), 'output_name': 'probabilities.json', 'max_output_bytes': 100000})
        # Loading succeeded with an impossible Docker path. It cannot be evidence
        # that a container, authentic profile or private grader was executed.
        self.assertEqual(self.api.unit.ProfileEngine.__mro__[1].__name__, 'Engine')

    def record(self):
        names = ['root_write', 'active_input_write', *['unmounted_' + str(i) for i in range(5)], 'network_no_route']
        value = {'schema': 'neural034-generated-runtime-probe/v1',
            'versions': {'python': '3.12.8', 'numpy': '2.2.6', 'scipy': '1.15.3'},
            'selected_generated_unit': 1, 'queries': 20,
            'fresh_tmp_marker_before_write': True, 'fresh_output_before_write': True,
            'generated_data_only': True, 'fits': 0, 'scientific_scores': 0,
            'denials': [{'probe': name, 'errno': 30 if i < 2 else 101 if i == 7 else 2}
                        for i, name in enumerate(names)]}
        body = json.dumps(value) + '\n'
        return {'status': 'unit_committed', 'all_owned_absent': True,
                'candidate_logs': {'returncode': 0, 'stdout': body, 'stderr': '',
                                   'capture_truncated': False, 'captured_stdout_bytes': len(body.encode())}}

    def test_no_favorable_partial_wrong_unit_version_or_denial_category(self):
        record = self.record(); s.validate_probe(record, 1)
        for key, replacement in [('queries', 19), ('selected_generated_unit', 2),
                                 ('fresh_output_before_write', False), ('fits', 1)]:
            broken = copy.deepcopy(record); value = json.loads(broken['candidate_logs']['stdout'])
            value[key] = replacement; body = json.dumps(value)
            broken['candidate_logs'].update(stdout=body, captured_stdout_bytes=len(body.encode()))
            with self.subTest(key=key), self.assertRaises(ValueError): s.validate_probe(broken, 1)
        for error_number in (0, 111, 110, 51):
            broken = copy.deepcopy(record); value = json.loads(broken['candidate_logs']['stdout'])
            value['denials'][-1]['errno'] = error_number; body = json.dumps(value)
            broken['candidate_logs'].update(stdout=body, captured_stdout_bytes=len(body.encode()))
            with self.subTest(errno=error_number), self.assertRaises(ValueError): s.validate_probe(broken, 1)
        record['all_owned_absent'] = False
        with self.assertRaises(ValueError): s.validate_probe(record, 1)

    def test_public_output_validator_preserves20_ids_no_scientific_grade(self):
        ids = self.fixture['units'][0]['expected_ids']
        body = s.encode({'schema_version': 1, 'probabilities': [{'query_id': q, 'probability': .5} for q in ids]})
        self.assertEqual(len(self.api.assembler.validate(body, ids)), 20)
        with self.assertRaises(ValueError): self.api.assembler.validate(body, self.fixture['units'][1]['expected_ids'])
        bad = s.encode({'schema_version': 1, 'probabilities': [{'query_id': q, 'probability': .5} for q in ids[:19]]})
        with self.assertRaises(ValueError): self.api.assembler.validate(bad, ids)

    def ledger(self, plan_path, plan_body, ledger_path):
        expected = {'path': str(plan_path), 'sha256': s.pin(plan_body)['sha256']}
        command = [sys.executable, '-I', '-B', str(HERE / 'run.py'), '--plan', str(plan_path), '--ledger', str(ledger_path)]
        return {'minimum_free_disk_bytes': driver.LIMITS['minimum_free_disk_bytes'],
            'approved_native_protocols': [{'id': driver.APPROVAL_ID, 'owner': driver.OWNER,
                'approved_by': '/root', 'protocol': expected}],
            'native_runs': [{'id': driver.RUN_ID, 'owner': driver.OWNER, 'status': 'running',
                'protocol': expected, 'approval_id': driver.APPROVAL_ID, 'coordinator_pid': os.getppid(),
                'command': command, 'requested_threads': 1,
                'declared_max_working_ram_bytes': driver.LIMITS['declared_max_working_ram_bytes'],
                'child_pid': os.getpid()}],
            'reservations': [{'id': driver.ARTIFACT_ID, 'owner': driver.OWNER, 'status': 'active',
                'kind': 'artifact', 'destination': str(self.base / 'never-created'),
                'reserved_bytes': driver.LIMITS['artifact_bytes']}]}

    def test_exact_root_lease_reservation_and_approval_guards_only_metadata(self):
        plan = {'operator': {'invocation_path': sys.executable}, 'output_root': str(self.base / 'never-created')}
        raw = s.encode(plan); path = self.base / 'plan.json'; ledger_path = self.base / 'ledger.json'
        ledger = self.ledger(path, raw, ledger_path)
        with mock.patch.object(s, 'read', return_value=s.encode(ledger)):
            driver.lease(plan, path, raw, ledger_path)
        for group, field, value in [('approved_native_protocols', 'approved_by', 'not-root'),
                                     ('native_runs', 'child_pid', -1), ('native_runs', 'status', 'closed'),
                                     ('reservations', 'reserved_bytes', 1), ('reservations', 'status', 'closed')]:
            changed = copy.deepcopy(ledger); changed[group][0][field] = value
            with self.subTest(field=field), mock.patch.object(s, 'read', return_value=s.encode(changed)), self.assertRaises(ValueError):
                driver.lease(plan, path, raw, ledger_path)
        self.assertFalse((self.base / 'never-created').exists())

    def test_actual_original_owned_group_barrier_completion_and_reaping(self):
        folder = self.root / 'artifacts-build/generated-owner-check'; folder.mkdir(parents=True)
        source = self.root / 'authoring/neural034-runtime-prerequisite/empty_controller.py'
        source.parent.mkdir(mode=0o700, parents=True)
        s.publish(source, b'import sys\nsys.exit(0)\n', 0o444)
        descriptor = {'path': source.relative_to(self.root).as_posix(), **s.pin(s.read(source))}
        proc = self.api.owner.launch([sys.executable, str(source)], folder, 8, descriptor)
        try:
            end = time.monotonic() + 4
            while not (folder / 'process_completion.json').exists():
                self.assertLess(time.monotonic(), end); self.assertIsNone(proc.poll()); time.sleep(.01)
            record = self.api.owner.read(folder / 'process_completion.json')
            self.assertEqual(record['returncode'], 0)
            self.assertTrue(record['group_leader_waits_for_owner_stop'])
        finally:
            closed = self.api.owner.stop(folder, time.monotonic() + 3, proc)
        self.assertTrue(closed['absence_verified']); self.assertIsNotNone(proc.returncode)

    def test_failure_before_lease_cannot_create_output_or_invoke_docker(self):
        plan = self.base / 'invalid-plan.json'; plan.write_text('{}')
        result = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'run.py'), '--plan', str(plan),
            '--ledger', str(self.base / 'missing-ledger.json')], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        value = json.loads(result.stdout)
        self.assertEqual(value['status'], 'failed_preserved'); self.assertFalse(value['runtime_qualified'])
        self.assertFalse(value['prior_costs_reset']); self.assertIsNone(value['cumulative_family_seconds'])

    def test_success_cannot_survive_terminal_publication_or_capacity_failure(self):
        for kind in ('write', 'cap'):
            with self.subTest(kind=kind):
                output = self.base / ('finalization-' + kind); output.mkdir()
                result = {'status': 'two_generated_units_closed_pending_independent_review', 'runtime_qualified': False}
                original = s.publish
                def publication(path, body, mode=0o400):
                    if Path(path).name == 'RESULT.json':
                        raise OSError('generated terminal publication failure')
                    return original(path, body, mode)
                if kind == 'write':
                    with mock.patch.object(s, 'publish', side_effect=publication):
                        self.assertFalse(driver.publish_terminal(output, result))
                    self.assertTrue((output / 'FAILURE.json').exists())
                else:
                    with mock.patch.dict(driver.LIMITS, {'artifact_bytes': 1}):
                        self.assertFalse(driver.publish_terminal(output, result))
                self.assertEqual(result['status'], 'failed_finalization_preserved')
                self.assertFalse((output / 'RESULT.json').exists())

    def test_controller_full_sequence_and_failed_first_unit_prevents_second(self):
        for fail in (False, True):
            with self.subTest(fail=fail):
                root = self.base / ('controller-failure' if fail else 'controller-positive'); root.mkdir()
                local = root / 'authoring/neural034-runtime-prerequisite'; local.mkdir(parents=True)
                out = root / 'artifacts-build/runtime-prerequisite'; out.mkdir(parents=True)
                fixture = copy.deepcopy(self.fixture)
                program = root / fixture['program']['path']; program.parent.mkdir()
                s.publish(program, s.read(self.root / self.fixture['program']['path']), 0o444)
                fixture_path = root / 'fixture.json'; s.save(fixture_path, fixture)
                calls = []
                def run_unit(program, program_sha, unit, destination, budget, work, whole, previous, task, validate):
                    calls.append(unit['unit_id'])
                    self.assertEqual(task, 'NEURAL-034'); self.assertEqual(program_sha, fixture['program']['sha256'])
                    if fail:
                        return {'status': 'failed_cleanup', 'all_owned_absent': False}
                    destination.mkdir(); body = s.encode({'schema_version': 1, 'probabilities': [
                        {'query_id': q, 'probability': .5} for q in unit['expected_ids']]})
                    validate(body, unit)
                    commit = s.encode({'generated_mock_only': True, 'unit': unit['unit_id'], 'previous': previous})
                    s.publish(destination / 'commit.json', commit)
                    result = self.record(); value = json.loads(result['candidate_logs']['stdout'])
                    value['selected_generated_unit'] = len(calls)
                    text = json.dumps(value)
                    result['candidate_logs'].update(stdout=text, captured_stdout_bytes=len(text.encode()))
                    result.update(commit_sha256=s.pin(commit)['sha256'],
                                  producer={'container_id': f'{len(calls):064x}'})
                    return result
                argv = [str(local / 'controller.py'), '--fixture', str(fixture_path), '--fixture-sha256',
                        s.pin(s.read(fixture_path))['sha256'], '--work-end', str(time.monotonic() + 5),
                        '--whole-end', str(time.monotonic() + 10)]
                api = SimpleNamespace(HostBudget=self.api.HostBudget, assembler=self.api.assembler,
                    owner=SimpleNamespace(expected=lambda _: ({'child_argv': [sys.executable, *argv]}, None)),
                    unit=SimpleNamespace(run_unit=run_unit))
                with (mock.patch.object(controller, '__file__', str(local / 'controller.py')),
                      mock.patch.object(s, 'runtime', return_value=(api, None)),
                      mock.patch.object(sys, 'argv', argv)):
                    code = controller.main()
                self.assertEqual(code, 2 if fail else 0)
                self.assertEqual(calls, ['fixture-00'] if fail else ['fixture-00', 'fixture-01'])
                self.assertEqual((out / 'controller_result.json').exists(), not fail)
                self.assertEqual((out / 'controller_failure.json').exists(), fail)


class GuardControls(unittest.TestCase):
    def test_wrong_fixture_pin_stops_before_runtime_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp).resolve() / 'fixture.json'; fixture.write_text('{}')
            argv = ['controller.py', '--fixture', str(fixture), '--fixture-sha256', '0' * 64,
                    '--work-end', str(time.monotonic() + 1), '--whole-end', str(time.monotonic() + 2)]
            with (mock.patch.object(sys, 'argv', argv), mock.patch.object(s, 'runtime') as runtime,
                  self.assertRaises(ValueError)):
                controller.main()
            runtime.assert_not_called()

    def test_unverified_process_absence_prevents_resource_recovery(self):
        api = SimpleNamespace(owner=SimpleNamespace(stop=lambda *args: {'absence_verified': False}))
        recovery = mock.Mock()
        with self.assertRaises(ValueError):
            driver.close_owned(api, recovery, Path('/operator/attempt'), None, {}, Path('/operator/root'), None)
        recovery.assert_not_called()
        api.owner.stop = lambda *args: {'absence_verified': True}
        fixture = {'program': {'path': 'program.py'}, 'units': [{'unit_id': 'fixture-00'}, {'unit_id': 'fixture-01'}]}
        recovery.return_value = [{'absence_verified': False}]
        result = driver.close_owned(api, recovery, Path('/operator/attempt'), SimpleNamespace(returncode=0),
                                    fixture, Path('/operator/root'), None)
        self.assertFalse(result['all_owned_absent'])
        self.assertEqual([str(call.args[1]) for call in recovery.call_args_list],
                         ['/operator/attempt/fixture-01', '/operator/attempt/fixture-00'])


if __name__ == '__main__':
    unittest.main()
