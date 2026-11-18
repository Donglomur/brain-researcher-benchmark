"""Narrow orchestration tests with an in-memory backend/store/state adapter.

No Docker, candidate code, source-state parser or filesystem writes execute.
These controls verify failed state, close and final-receipt custody seams. The
real custody/parser and complete six-control fixture have separate coverage.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import time
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
DRIVER_PIN = 'f6d224078d7267c2cc062b8503210364d68cf069ad60b8adeb2dfd58a37e3141'
source = (HERE / 'qualification_driver_v2.py').read_bytes()
if hashlib.sha256(source).hexdigest() != DRIVER_PIN:
    raise AssertionError('driver pin differs')
driver = types.ModuleType('independent_fresh_driver')
driver.__file__ = str(HERE / 'qualification_driver_v2.py')
sys.modules[driver.__name__] = driver
exec(compile(source, driver.__file__, 'exec'), driver.__dict__)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def binding(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


class MemoryStore:
    refuse_state_receipt = False
    def __init__(self, root):
        self.entries = []; self.raws = []; self.cleanup = False
    def __call__(self, kind, raw):
        if kind == 'fresh_runtime_state' and self.refuse_state_receipt:
            raise OSError('fictional final state receipt custody failed')
        item = {'path': str(len(self.entries)).zfill(4) + '-' + kind + '.bin',
                'kind': kind, 'status': 'confirmed', 'binding': binding(raw)}
        self.entries.append(item); self.raws.append(raw)
        return dict(item['binding'])
    def lookup(self, bound, kind):
        for item, raw in zip(self.entries, self.raws):
            if item['binding'] == bound and item['kind'] == kind:
                return item, raw, raw[:4096]
        raise ValueError('missing mocked original')
    def summary(self):
        return {'files': copy.deepcopy(self.entries), 'fixture_memory_only': True}


class Context:
    def __init__(self, *, matched, missing_close):
        ctx = self
        self.output_root = Path('/fictional/fresh-driver')
        self.profile_bytes = b'fictional profile'; self.probe_source = b'fictional probe'
        self.protocol_sha256 = 'f' * 64; self.started = time.monotonic()
        self.command_prefix = []; self.command_runner = self.forbidden
        self.report = None; self.closed = 0; self.tools = []; self.bound_calls = 0
        self.protocol = {'context_ids': [v * 64 for v in 'abc'],
            'limits': {'operation_deadline_seconds': 480, 'cleanup_deadline_seconds': 570},
            'docker_executable': '/fictional/docker', 'docker_socket': '/fictional/daemon.sock',
            'python_executable': '/fictional/python', 'cli_shim': {'path': '/fictional/shim'},
            'modules': {key: {'sha256': 'd' * 64} for key in
                        ('policy', 'network_policy', 'owned', 'probe', 'cases')}}
        names = ('runtime', 'readonly_scratch', 'fresh_scratch', 'nonzero', 'flood', 'deadline')
        programs = {name: 'fictional source: ' + name for name in names}
        self.protocol['generated_programs'] = {k: binding(v.encode()) for k, v in programs.items()}

        class Backend:
            def __init__(self, **kw):
                self.recorder = kw['recorder']; self.calls = []; self.context = kw['context_id']
                self._write('fictional observation', kw['observation_bytes'])
            def _write(self, path, raw):
                return None  # No filesystem action: simulated staging accounting only.
            def run_tool(self, tool, program):
                name = next(k for k, v in programs.items() if v == program)
                ctx.tools.append(name); self._write('fictional program', program.encode())
                closure = {role: self.recorder('command_receipt', canonical(
                    {'fictional': role, 'ordinal': len(self.calls)})) for role in ('remove', 'absence')}
                self.calls.append(self.recorder('code_call', canonical(
                    {'fictional': name, 'ordinal': len(self.calls), 'closure': closure})))
                return {'status': 'ok', 'text': 'fictional'}
            def close(self):
                ctx.closed += 1
                calls = self.calls[:-1] if missing_close else self.calls
                return self.recorder('code_close', canonical({'complete': True, 'errors': [],
                    'owned_container_ids_unresolved': [], 'container_names_with_unresolved_create': [],
                    'calls': calls}))

        def derive(*args, **kwargs):
            return {'necessary_condition_matches': matched, 'runtime_control_confirmed': False,
                    'context_closure_pending': True, 'fixture_semantics_mocked': True}
        def close(provisional, raw, *, expected_call_bindings):
            value = json.loads(raw)
            if len(expected_call_bindings) != 4 or value['calls'] != expected_call_bindings:
                raise ValueError('four-call mocked close differs')
            ctx.bound_calls += 1
            return dict(provisional, runtime_control_confirmed=matched, context_closure_pending=False)

        class Writer:
            def __init__(self, root): self.bytes = 0
            def write(self, value):
                ctx.report = copy.deepcopy(value); raw = canonical(value); self.bytes = len(raw)
                return binding(raw)
            def summary(self): return {'fixture_memory_only': True, 'bytes': self.bytes}

        self.modules = {
            'backend': types.SimpleNamespace(DockerCodeBackend=Backend),
            'policy': types.SimpleNamespace(profile=lambda raw: {}, decode=json.loads, PROFILE_SHA256='a' * 64),
            'cases': types.SimpleNamespace(NAMES=names, CASE_ID='b' * 64, OBSERVATION_SHA256='c' * 64,
                OBSERVATION=b'fictional observation', CANARY=b'fictional canary',
                programs=lambda *a, **kw: dict(programs), validate_normal=lambda *a, **kw: {'fictional': True}),
            'store': types.SimpleNamespace(EvidenceStore=MemoryStore, ReportWriter=Writer,
                directory_signature=lambda path: None, binding=binding, canonical=canonical),
            'fresh_state': types.SimpleNamespace(Authority=lambda **kw: kw,
                derive_runtime_state=derive, bind_context_close=close),
            'raw': types.SimpleNamespace(run=self.forbidden), 'owned': object(),
            'probe': object(), 'network_policy': object(),
        }
    def forbidden(self, *args, **kwargs): raise AssertionError('external action forbidden')
    def checkpoint(self, **kwargs): pass


class DriverBoundaries(unittest.TestCase):
    def run_fixture(self, ctx):
        # Source loading already finished; these are the only driver OS mutation
        # seams reachable in this mock. Bodies and reports remain in RAM.
        with patch.object(driver.os, 'mkdir', lambda *a, **kw: None), \
             patch.object(driver.os, 'open', ctx.forbidden):
            return driver.run_qualification(ctx)

    def test_semantic_nonmatch_keeps_proven_cleanup_without_confirmation(self):
        ctx = Context(matched=False, missing_close=False)
        result = self.run_fixture(ctx)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(ctx.closed, 1); self.assertEqual(ctx.bound_calls, 1)
        self.assertEqual(ctx.tools, ['runtime', 'readonly_scratch', 'fresh_scratch', 'nonzero'])
        self.assertEqual(ctx.report['cleanup_failures'], [])
        self.assertEqual(len(ctx.report['context_closures']), 1)
        self.assertTrue(ctx.report['context_closures'][0]['complete'])
        self.assertEqual(ctx.report['cases'][0]['status'], 'necessary_condition_failed')
        self.assertFalse(ctx.report['cases'][0]['runtime_control_confirmed'])
        self.assertIn('fresh_state_receipt', ctx.report['cases'][0])
        self.assertNotIn('fresh_state', ctx.report['cases'][0])
        self.assertIn('fresh necessary network state condition', result['failure']['category'])

    def test_missing_final_call_cannot_promote_provisional_runtime(self):
        ctx = Context(matched=True, missing_close=True)
        result = self.run_fixture(ctx)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(ctx.closed, 1); self.assertEqual(ctx.bound_calls, 0)
        self.assertEqual(ctx.report['context_closures'], [])
        self.assertEqual(len(ctx.report['cleanup_failures']), 1)
        self.assertEqual(ctx.report['cases'][0]['status'], 'context_closure_pending')
        self.assertFalse(ctx.report['cases'][0]['fresh_state']['runtime_control_confirmed'])
        self.assertTrue(ctx.report['cases'][0]['fresh_state']['context_closure_pending'])

    def test_final_state_receipt_failure_cannot_promote_closed_runtime(self):
        ctx = Context(matched=True, missing_close=False)
        with patch.object(MemoryStore, 'refuse_state_receipt', True):
            result = self.run_fixture(ctx)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(ctx.closed, 1); self.assertEqual(ctx.bound_calls, 1)
        self.assertEqual(ctx.report['cleanup_failures'], [])
        self.assertEqual(len(ctx.report['context_closures']), 1)
        self.assertEqual(ctx.report['cases'][0]['status'], 'context_closed_receipt_pending')
        self.assertNotIn('fresh_state_receipt', ctx.report['cases'][0])
        self.assertNotEqual(ctx.report['cases'][0]['status'], 'confirmed')
        self.assertIn('state receipt custody failed', result['failure']['category'])


if __name__ == '__main__': unittest.main()
