import ast
import copy
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from vendor_transport import provider as p, contract as c, bounds as b, engine as e
PIN = {'bytes': 1, 'sha256': '1' * 64}

class NoDocker:

    def __init__(self, *args, **kwargs):
        self.records = []
        self.reaped = True
        self.phase_caps = kwargs['phase_caps']

    def __call__(self, *args, **kwargs):
        raise AssertionError('No Docker/native invocation in generated controls')

class AggregateTransportTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.now = time.monotonic()
        self.plan = {'schema': 'smc_cgroup_plan_v1', 'phase_id': 'paper_data', 'name': 'smc-' + 'a' * 32 + '-a', 'parent': str(self.root / 'cg'), 'path': str(self.root / 'cg' / ('smc-' + 'a' * 32 + '-a')), 'cgroup_parent': '/cg/smc-' + 'a' * 32 + '-a', 'deployment_pin': PIN.copy(), 'invocation_pin': PIN.copy()}
        r = dict(setup_seconds=60, producer_seconds=10800, capture_seconds=300, cleanup_seconds=60, memory_bytes=8589934592, cpu_nanos=6000000000, cpu_seconds=7200, pids=32, scratch_bytes=4096, max_files=4, max_directories=1, max_file_bytes=4096, max_output_bytes=8192, manifest_bytes=2048, max_cli_calls=256, max_cli_bytes=1048576, inventory_bytes=4096, source_read_bytes=2097152, host_write_bytes=2097152)
        self.request = dict(schema='smc_aggregate_phase_request_v1', phase_id='paper_data', action='held_attempt', role='A', image='sha256:' + '2' * 64, command=['/usr/local/bin/python', '/runner/worker.py'], workdir='/work', source=PIN.copy(), exposure=PIN.copy(), clock={'origin': self.now, 'phase_deadline': self.now + 22500}, resources=r, output={'kind': 'generic', 'manifest': 'OUTPUTS.json'}, aggregate=self.plan)
        self.mounts = {'/runner/worker.py': {'path': str(self.root / 'worker.py'), 'kind': 'file', 'purpose': 'program', 'files': {'.': PIN.copy()}}}
        self.no_spawn = patch.object(e.subprocess, 'Popen', side_effect=AssertionError('No process'))
        self.no_spawn.start()
        self.fixture_charge = 0
        def charge(raw):
            self.fixture_charge += len(raw)
            if self.fixture_charge > 16384:
                raise AssertionError('Generated fixture payload cap before write')
        original_publish = b.publish
        def counted_publish(file, raw, *args, **kwargs):
            charge(raw)
            return original_publish(file, raw, *args, **kwargs)
        original_write = Path.write_bytes
        def counted_write(file, raw):
            if not file.is_relative_to(self.root):
                raise AssertionError('Generated writes stay in test directory')
            charge(raw)
            return original_write(file, raw)
        self.write_patches = [patch.object(p, 'publish', new=counted_publish),
                              patch.object(b, 'publish', new=counted_publish),
                              patch.object(Path, 'write_bytes', new=counted_write)]
        for hook in self.write_patches:
            hook.start()


    def tearDown(self):
        for hook in reversed(self.write_patches):
            hook.stop()
        print(json.dumps({'method': self._testMethodName, 'generated_fixture_payload_charge_bytes': self.fixture_charge}))
        self.no_spawn.stop()
        self.tmp.cleanup()

    def provider(self):
        for name in ('control', 'quarantine'):
            (self.root / name).mkdir(mode=448)
        manifest = (HERE / 'vendor_transport/SOURCE_MANIFEST.json').read_bytes()
        return p.Provider(self.root / 'control', self.root / 'quarantine', '/unused/docker', self.root / 'unused.sock', e.pin(manifest), {PIN['sha256']: str(self.root / 'EXPOSURE.json')}, 4194304, 4194304)

    def test_exact_request_and_compact_encoding(self):
        self.assertIs(c.validate_request(self.request, self.mounts, self.now + 22560), self.request)
        self.assertEqual(e.encoded(self.request), (json.dumps(self.request, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode())

    def test_refuses_old_or_unbound_request_and_budget(self):
        changes = [('schema', 'osl_owned_phase_request_v1'), ('action', 'report')]
        for key, value in changes:
            q = copy.deepcopy(self.request)
            q[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                c.validate_request(q, self.mounts, self.now + 22560)
        for key, value in [('pids', None), ('pids', True), ('cpu_seconds', 75000), ('cpu_nanos', 1000000000), ('memory_bytes', 4294967296)]:
            q = copy.deepcopy(self.request)
            q['resources'][key] = value
            with self.subTest(resource=key, value=value), self.assertRaises(ValueError):
                c.validate_request(q, self.mounts, self.now + 22560)
        for key, value in [('phase_id', 'other'), ('path', str(self.root / 'other')), ('parent', '/'), ('cgroup_parent', '/wrong'), ('cgroup_parent', 'relative'), ('cgroup_parent', '/cg/../name'), ('invocation_pin', {'qualified': True})]:
            q = copy.deepcopy(self.request)
            q['aggregate'][key] = value
            with self.subTest(aggregate=key), self.assertRaises(ValueError):
                c.validate_request(q, self.mounts, self.now + 22560)

    def test_producer_parent_and_holder_resources_are_distinct(self):
        item = {'name': 'owned', 'owner': 'owned/producer'}
        producer = p.create_args(item, False, {}, self.request, ['/holder'])
        holder = p.create_args(item, True, {}, self.request, ['/holder'])
        self.assertEqual(producer[producer.index('--cgroup-parent') + 1], self.plan['cgroup_parent'])
        self.assertNotIn('--cgroup-parent', holder)
        for argv, memory, cpus, pids in [(producer, '8589934592', '6.000000000', '32'), (holder, '134217728', '1.000000000', '64')]:
            for key, value in [('--memory', memory), ('--memory-swap', memory), ('--cpus', cpus), ('--pids-limit', pids)]:
                self.assertEqual(argv[argv.index(key) + 1], value)
        self.assertEqual(p.fixed_environment(False)['OMP_THREAD_LIMIT'], '6')
        self.assertEqual(p.fixed_environment(True)['OMP_NUM_THREADS'], '1')

    def test_attachment_refuses_finished_pid_zero_or_wrong_parent(self):
        item = {'name': 'owned', 'owner': 'owned/producer', 'kind': 'container', 'id': '3' * 64}
        state = {'Name': '/owned', 'Id': item['id'], 'Config': {'Labels': {e.LABEL: item['owner']}}, 'HostConfig': {'CgroupParent': self.plan['cgroup_parent']}, 'State': {'Running': True, 'Dead': False, 'Status': 'running', 'Pid': 123}}
        self.assertEqual(p.aggregate_attachment(state, item, self.request)['pid'], 123)
        for changes in ({'Pid': 0}, {'Pid': True}, {'Running': False, 'Status': 'exited'}, {'Dead': True}):
            bad = copy.deepcopy(state)
            bad['State'].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                p.aggregate_attachment(bad, item, self.request)
        state['HostConfig']['CgroupParent'] = '/wrong'
        with self.assertRaises(ValueError):
            p.aggregate_attachment(state, item, self.request)

    def test_failed_intent_defers_all_cleanup_to_parent(self):
        service = self.provider()
        events = []

        def journal(name, value):
            events.append(name)
            if name == 'CGROUP-INTENT':
                raise ValueError('Generated parent refusal before creation')
        with patch.object(p, 'Docker', NoDocker), patch.object(p, 'retire') as retire:
            result = service.execute_phase(self.request, self.mounts, self.now + 22560, journal)
        receipt = result['receipt']
        self.assertEqual(events, ['OWNERSHIP', 'CGROUP-INTENT', 'PHASE-CLOSURE'])
        retire.assert_not_called()
        self.assertEqual(receipt['schema'], 'smc_aggregate_phase_receipt_v1')
        self.assertEqual(receipt['status'], 'failed')
        self.assertFalse(receipt['aggregate_final_acknowledged'])
        self.assertTrue(receipt['failure_cleanup_deferred_to_parent'])
        self.assertEqual(receipt['retired_resources'], [])
        self.assertEqual(receipt['resource_custody_scope'], 'docker_volume_holder_producer_only')
        self.assertEqual(receipt['aggregate_custody_owner'], 'parent')

    def test_public_modes_under_077_and_private_modes_preserved(self):
        old = os.umask(63)
        try:
            meter = b.Meter(65536, 65536, self.now + 10)
            b.publish(self.root / 'public.json', b'{}\n', meter, mode=292)
            b.publish(self.root / 'private.json', b'{}\n', meter)
            (self.root / 'private').mkdir(mode=448)
        finally:
            os.umask(old)
        self.assertEqual(stat.S_IMODE((self.root / 'public.json').stat().st_mode), 292)
        self.assertEqual(stat.S_IMODE((self.root / 'private.json').stat().st_mode), 384)
        self.assertEqual(stat.S_IMODE((self.root / 'private').stat().st_mode), 448)

    def test_source_hook_order_and_final_ack_success_gate(self):
        source = (HERE / 'vendor_transport/provider.py').read_text()
        ast.parse(source)
        snippets = ["record('OWNERSHIP'", "record('CGROUP-INTENT'", 'container(producer,False', "'producer_start',4096)", "record('CGROUP-ATTACHED'", "'producer_release',4096)", "raw=d(['container','wait'", 'items.remove(producer);closed_before=True', "record('CGROUP-FINAL'", 'aggregate_final_acknowledged=True', 'capture_end=min(work_end']
        positions = [source.index(value) for value in snippets]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('good=error is None and aggregate_final_acknowledged', source)
        self.assertNotIn("record('CGROUP-FINAL'", source[source.index('def recover('):])

    def test_recovery_keeps_aggregate_separate_and_refuses_legacy_ownership(self):
        service = self.provider()
        control = self.root / 'control' / 'paper_data'
        control.mkdir(mode=448)
        request_pin = e.pin(e.encoded(self.request))
        prefix = 'osl-' + '4' * 24
        ownership = dict(schema='smc_aggregate_phase_ownership_v1', phase_id='paper_data', request_pin=request_pin, engine_source_pin=service.engine_pin, original_deadline=self.now + 22560, phase_deadline=self.now + 11220, attempt_prefix=prefix, aggregate=self.plan, resources={key: {'kind': 'volume' if key == 'volume' else 'container', 'name': prefix + '-' + key, 'owner': prefix + '/' + key, 'attempted': False, 'acknowledged': False} for key in ('volume', 'holder', 'producer')})
        raw = e.encoded(ownership)
        (control / 'OWNERSHIP.json').write_bytes(raw)
        limits = dict(max_records=32, max_record_bytes=65536, max_metadata_bytes=131072, max_cli_calls=64, max_cli_bytes=65536, source_read_bytes=1048576, host_write_bytes=1048576)
        with patch.object(p, 'Docker', NoDocker), patch.object(p, 'retire', side_effect=lambda d, row, end: {'kind': row['kind'], 'name': row['name'], 'closed': True}), patch.object(p, 'resource_inventory', return_value=[]), patch.object(p, 'validate_cli_records'):
            result = service.recover('paper_data', request_pin, e.pin(raw), self.now + 22560, lambda *args: None, limits, PIN.copy())
        self.assertEqual(result['receipt']['schema'], 'smc_aggregate_independent_phase_recovery_v1')
        self.assertEqual(result['receipt']['resource_custody_scope'], 'docker_volume_holder_producer_only')
        self.assertTrue(result['receipt']['parent_aggregate_evidence_required'])
        self.assertEqual(e.pin(Path(result['receipt_path']).read_bytes()), result['receipt_pin'])
        ownership['schema'] = 'osl_phase_ownership_v1'
        raw = e.encoded(ownership)
        (control / 'OWNERSHIP.json').write_bytes(raw)
        with patch.object(p, 'Docker', NoDocker), patch.object(p, 'retire') as retire, self.assertRaises(ValueError):
            service.recover('paper_data', request_pin, e.pin(raw), self.now + 22560, lambda *args: None, limits, PIN.copy())
        retire.assert_not_called()
if __name__ == '__main__':
    unittest.main(verbosity=2)
