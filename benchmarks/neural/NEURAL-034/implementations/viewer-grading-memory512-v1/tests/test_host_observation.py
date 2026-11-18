"""Generated metadata only: no commands, host probes or subprocesses executed."""
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('host_observation', Path(__file__).resolve().parents[1] / 'host_observation.py')
H = importlib.util.module_from_spec(spec); spec.loader.exec_module(H)
VM = ('Mach Virtual Memory Statistics: (page size of 16384 bytes)\n'
      'Pages free: 100.\nPages inactive: 200.\nPages speculative: 3.\n'
      'File-backed pages: 400.\nPageouts: 9.\n')
PRESSURE = 'kern.memorystatus_vm_pressure_level: 1\n'


def success(argv, deadline, *, cap):
    return {'returncode': 0, 'stdout': VM if argv == ['/usr/bin/vm_stat'] else PRESSURE, 'stderr': ''}


class HostObservationControls(unittest.TestCase):
    def test_fixed_commands_bound_deadline_and_preserve_raw_metadata(self):
        calls = []
        def call(argv, deadline, *, cap):
            calls.append((argv, deadline, cap)); return success(argv, deadline, cap=cap)
        value = H.observe(call, 10.4, clock=lambda: 10., utc=lambda: 'GENERATED timestamp')
        self.assertEqual(calls, [(['/usr/bin/vm_stat'], 10.4, 16384),
            (['/usr/sbin/sysctl', 'kern.memorystatus_vm_pressure_level'], 10.4, 16384)])
        vm = value['observations']['vm_stat']
        self.assertEqual(vm['stdout'], VM); self.assertEqual(vm['status'], 'observed')
        estimates = vm['parsed']['estimates']
        self.assertEqual(estimates['free_plus_file_backed']['bytes'], 500 * 16384)
        self.assertEqual(estimates['free_plus_inactive']['bytes'], 300 * 16384)
        self.assertEqual(estimates['free_plus_inactive_plus_speculative']['bytes'], 303 * 16384)
        self.assertIsNone(value['admission_decision'])
        self.assertFalse(value['swap_growth_measured']); self.assertFalse(value['stability_established'])

    def test_one_second_cap_and_no_command_after_external_deadline(self):
        calls = []
        def call(argv, deadline, *, cap):
            calls.append(deadline); return success(argv, deadline, cap=cap)
        H.observe(call, 100., clock=lambda: 10., utc=lambda: 'GENERATED')
        self.assertEqual(calls, [11., 11.]); calls.clear()
        value = H.observe(call, 10., clock=lambda: 10., utc=lambda: 'GENERATED')
        self.assertEqual(calls, [])
        self.assertTrue(all(r['status'] == 'unknown' for r in value['observations'].values()))

    def test_failures_unknown_and_raw_failure_retained(self):
        fixtures = [({'returncode': 1, 'stdout': 'failure', 'stderr': 'denied'}, True),
            ({'returncode': 0, 'stdout': 'malformed', 'stderr': ''}, True),
            ({'returncode': 0, 'stdout': 'x' * 16385, 'stderr': ''}, False),
            ({'returncode': False, 'stdout': VM, 'stderr': ''}, False)]
        for result, retained in fixtures:
            value = H.observe(lambda *args, **kw: result, 10., clock=lambda: 1., utc=lambda: 'GENERATED')
            for row in value['observations'].values():
                self.assertEqual(row['status'], 'unknown'); self.assertIsNone(row['parsed'])
                self.assertEqual(row['stdout'], result['stdout'] if retained else None)
        def fail(*args, **kw): raise TimeoutError('GENERATED capture timeout')
        value = H.observe(fail, 10., clock=lambda: 1., utc=lambda: 'GENERATED')
        self.assertIn('TimeoutError', value['observations']['vm_stat']['reason'])

    def test_missing_component_is_unknown_not_zero_and_malformed_refused(self):
        missing = H.parse_vm_stat(VM.replace('File-backed pages: 400.\n', ''))
        self.assertIsNone(missing['estimates']['free_plus_file_backed']['bytes'])
        self.assertEqual(missing['estimates']['free_plus_inactive']['bytes'], 300 * 16384)
        for raw in (VM + 'Pages free: 1.\n', VM.replace('100.', '-1.'), VM.replace('16384', '3')):
            with self.assertRaises(ValueError): H.parse_vm_stat(raw)
        with self.assertRaises(ValueError): H.parse_pressure('1\n')
        with self.assertRaises(ValueError): H.observe(success, True)


if __name__ == '__main__':
    unittest.main()
