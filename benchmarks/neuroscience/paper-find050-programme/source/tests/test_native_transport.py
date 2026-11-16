"""Generated-only software controls; no author code, arrays, fork or cgroup run.

Inert leaves never establish scientific/native qualification. The complete
26-operation assembly is exercised with documentary generated capture rows.
"""
import base64
import copy
import importlib
from pathlib import Path
import socket
import struct
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

from critical.core import Costs, Refusal, decode, encode, pin
from critical.captured_author import CapturedAuthorClosure
from critical.lifecycle import Custody
from critical.native_worker import NativeWorker, NativeWorkerIssuer, NativeWorkerLease, RemoteWorkerFailure, run_reference_programme
from critical.native_producer import NativeProducer
from critical.programme import catalogue, contract
from critical.reference_assembly import source_row
from critical.worker_transport import CgroupTree, ParentChannel, RemoteCostPrefix, wire_receive, wire_send


def plan(root):
    return {'author_root': str(root), 'cgroup_parent': str(root), 'wall_seconds': 30,
            'retirement_seconds': 2, 'frame_bytes': 1048576,
            'transport_bytes': 2097152, 'log_bytes': 1024}


class Original:
    """Explicit inert engineering lease, NOT an admitted live deployment."""
    def __init__(self):
        self.phases = []
        self.closed = 0
    def require(self, phase, source):
        self.phases.append((phase, source))
    def close(self):
        self.closed += 1
    def native_plan(self, *args):
        raise AssertionError('candidate runtime forbidden in controls')
    def terminal(self, *args):
        raise AssertionError('candidate runtime forbidden in controls')


class Issuer:
    def __init__(self, original):
        self.original, self.calls = original, 0
    def issue(self, request):
        self.calls += 1
        return self.original


class Slot:
    def __init__(self):
        self.worker = None
    def register_issued(self, worker):
        if self.worker is not None:
            raise AssertionError('duplicate owner')
        self.worker = worker


class GeneratedTree:
    def __init__(self):
        self.attached = True
        self.populated_zero = self.removed = False
        self.calls = 0
    def retire(self, deadline, custody):
        self.calls += 1
        self.populated_zero = self.removed = True


class QueueChannel:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.logs = {'stdout': bytearray(), 'stderr': bytearray()}
    def receive(self):
        return next(self.rows)
    def drain_after_exit(self):
        return None


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
    def tearDown(self):
        self.tmp.cleanup()

    def worker(self):
        original = Original()
        lease = NativeWorkerLease(original, 'a' * 64, encode(plan(self.root)))
        host = types.SimpleNamespace(lease=lease, source_sha256='a' * 64)
        context = types.SimpleNamespace(authority=host, cost=Costs(100, 100))
        slot = Slot()
        selected = {'operation': 'generated', 'source_sha256': 'a' * 64}
        worker = NativeWorker(lease, host, context, selected, slot)
        producer = types.SimpleNamespace(worker=worker, slot=slot, capture=None)
        worker.require('issuance', host, producer, selected)
        return worker, producer, original

    def test_captured_transitive_source_beats_mutated_disk(self):
        sources = {'outer.py': b'import nb_generated_helper\nvalue=nb_generated_helper.value\n',
                   'nb_generated_helper.py': b'value=73\n'}
        (self.root / 'outer.py').write_text('raise AssertionError("disk executed")')
        closure = CapturedAuthorClosure(sources, self.root)
        try:
            closure.install()
            self.assertEqual(closure.load('outer.py').value, 73)
        finally:
            closure.close()
            for key in ('nb_generated_helper', '_critical_captured_outer_py'):
                sys.modules.pop(key, None)

    def test_author_alias_cache_is_refused(self):
        sys.modules['nb_generated_alias'] = types.ModuleType('nb_generated_alias')
        try:
            with self.assertRaises(Refusal):
                CapturedAuthorClosure({'nb_generated_alias.py': b''}, self.root).install()
        finally:
            sys.modules.pop('nb_generated_alias')

    def test_captured_directory_import_and_missing_alias(self):
        closure = CapturedAuthorClosure({'fig4/outer.py': b'import nb_generated_analysis\nvalue=nb_generated_analysis.value',
                                       'fig4/nb_generated_analysis.py': b'value=4',
                                       'fig2/nb_generated_analysis.py': b'value=2',
                                       'missing/nb_generated_missing.py': b''}, self.root)
        try:
            closure.install()
            self.assertEqual(closure.load('fig4/outer.py').value, 4)
            with self.assertRaises(Refusal):
                closure.find_spec('nb_generated_missing')
        finally:
            closure.close()
            for name in ('nb_generated_analysis', '_critical_captured_fig4_outer_py'):
                sys.modules.pop(name, None)

    def test_wire_roundtrip_and_oversized_header(self):
        left, right = socket.socketpair()
        try:
            wire_send(left, {'value': 7}, time.monotonic() + 2, 1024)
            self.assertEqual(wire_receive(right, time.monotonic() + 2, 1024), {'value': 7})
            left.sendall(struct.pack('!Q', 1025))
            with self.assertRaises(Refusal):
                wire_receive(right, time.monotonic() + 2, 1024)
        finally:
            left.close(); right.close()

    def test_parent_channel_reads_complete_frame(self):
        left, right = socket.socketpair()
        try:
            wire_send(left, {'kind': 'generated'}, time.monotonic() + 2, 1024)
            parent = ParentChannel(right, {}, time.monotonic() + 2, 1024, 2048, 128)
            self.assertEqual(parent.receive(), {'kind': 'generated'})
            self.assertGreater(parent.total, 8)
        finally:
            left.close(); right.close()

    def test_parent_channel_aggregate_limit(self):
        left, right = socket.socketpair()
        try:
            wire_send(left, {'padding': 'x' * 300}, time.monotonic() + 2, 1024)
            parent = ParentChannel(right, {}, time.monotonic() + 2, 1024, 32, 128)
            with self.assertRaises(Refusal):
                parent.receive()
        finally:
            left.close(); right.close()

    def test_remote_prefix_original_owner_and_outstanding_child_reservation(self):
        cost = Costs(100, 200, read=5, write=7)
        owner = RemoteCostPrefix(cost, {'selection': 1})
        self.assertIs(cost._io_operations[-1], owner)
        self.assertEqual((cost.reserved_read, cost.reserved_write), (95, 193))
        owner.admit({'selection': {'selection': 1}, 'read': 20, 'write': 30,
                     'reserved_read': 3, 'reserved_write': 4, 'operations': []})
        self.assertEqual((cost.read, cost.write, cost.reserved_read, cost.reserved_write), (25, 37, 3, 4))
        with self.assertRaises(Refusal):
            owner.admit(decode(owner.prefix_body))

    def test_missing_and_malformed_remote_prefix_never_refund(self):
        cost = Costs(10, 20)
        owner = RemoteCostPrefix(cost, {'selection': 1})
        owner.dispatched = True
        owner.release_undispatched()
        self.assertEqual((cost.reserved_read, cost.reserved_write), (10, 20))
        malformed = {'selection': {'selection': 1}, 'read': 11, 'write': 0,
                     'reserved_read': 0, 'reserved_write': 0, 'operations': []}
        with self.assertRaises(Refusal):
            owner.admit(malformed)
        self.assertIsNone(owner.prefix)
        self.assertEqual(cost.reserved_read, 10)

    def test_undispatched_remote_prefix_releases_only_its_own_reservation(self):
        cost = Costs(20, 30, reserved_read=3, reserved_write=4)
        owner = RemoteCostPrefix(cost, {})
        owner.release_undispatched()
        self.assertEqual((cost.reserved_read, cost.reserved_write), (3, 4))

    def test_issuer_delegates_original_once_and_closes_failed_admission(self):
        original = Original()
        issuer = Issuer(original)
        adapter = NativeWorkerIssuer(issuer, plan(self.root))
        lease = adapter.issue({'source_sha256': 'a' * 64})
        self.assertIs(lease.original, original)
        with self.assertRaises(Refusal):
            adapter.issue({'source_sha256': 'a' * 64})
        self.assertEqual(issuer.calls, 1)
        original = Original()
        def refuse(*args):
            raise Refusal('original qualification refused')
        original.require = refuse
        with self.assertRaises(Refusal):
            NativeWorkerIssuer(Issuer(original), plan(self.root)).issue({'source_sha256': 'a' * 64})
        self.assertEqual(original.closed, 1)

    def test_child_phase_rpc_never_calls_cloned_original(self):
        worker, producer, original = self.worker()
        lease = worker.lease
        worker.child_pid = lease.parent_pid + 10000
        lease.active_worker, lease.channel = worker, object()
        worker.deadline = time.monotonic() + 2
        sent = []
        def receive(*args):
            return {'kind': 'phase_reply', 'sequence': worker.sequence,
                    'selection': worker.selection_pin, 'allowed': True}
        before = list(original.phases)
        with patch('critical.native_worker.os.getpid', return_value=worker.child_pid), \
             patch('critical.native_worker.wire_send', side_effect=lambda *args: sent.append(args[1])), \
             patch('critical.native_worker.wire_receive', side_effect=receive):
            lease.require('actual_scientific_binding:generated', 'a' * 64)
        self.assertEqual(original.phases, before)
        self.assertEqual(sent[0]['kind'], 'phase')

    def test_parent_services_phase_on_original_owner(self):
        worker, producer, original = self.worker()
        worker.prefix = RemoteCostPrefix(worker.context.cost, worker.selection_pin)
        worker.deadline = time.monotonic() + 2
        terminal = {'kind': 'terminal', 'sequence': 2, 'selection': worker.selection_pin,
                    'status': 'failed', 'capture': None,
                    'cost_prefix': {'selection': worker.selection_pin, 'read': 2, 'write': 3,
                                    'reserved_read': 0, 'reserved_write': 0, 'operations': []},
                    'failure': {'first_error': {'type': 'GeneratedFailure'}}}
        worker.channel_owner = QueueChannel([
            {'kind': 'phase', 'sequence': 1, 'selection': worker.selection_pin,
             'phase': 'actual_scientific_binding:generated', 'source_sha256': 'a' * 64}, terminal])
        sent = []
        with patch('critical.native_worker.wire_send', side_effect=lambda *args: sent.append(args[1])):
            self.assertEqual(worker._serve(object()), terminal)
        self.assertIn(('actual_scientific_binding:generated', 'a' * 64), original.phases)
        self.assertEqual([r['kind'] for r in sent], ['phase_reply', 'terminal_ack'])
        self.assertEqual((worker.context.cost.read, worker.context.cost.write), (2, 3))

    def test_parent_rejects_wrong_channel_selection_and_replay(self):
        for selection, sequence in (({'forged': 1}, 1), (None, 2)):
            worker, producer, original = self.worker()
            worker.channel_owner = QueueChannel([{'kind': 'phase', 'selection': selection or worker.selection_pin,
                                                  'sequence': sequence}])
            with self.assertRaises(Refusal):
                worker._serve(object())

    def test_descriptor_close_failure_is_never_retried(self):
        worker, producer, original = self.worker()
        class FailingSocket:
            calls = 0
            def close(self):
                self.calls += 1
                raise OSError('generated uncertain close')
        channel = FailingSocket()
        worker.sockets.append(channel)
        with self.assertRaises(OSError):
            worker.close()
        with self.assertRaises(OSError):
            worker.close()
        self.assertEqual(channel.calls, 1)

    def test_unattached_child_kill_precedes_reap_and_no_postreap_signal(self):
        worker, producer, original = self.worker()
        worker.pid = 120000  # inert value; os.kill and wait are replaced
        events = []
        def wait(deadline):
            events.append('wait'); worker.status = 0
        with patch('critical.native_worker.os.kill', side_effect=lambda *args: events.append('kill')), \
             patch.object(worker, '_wait', side_effect=wait):
            worker.close()
            worker.close()
        self.assertEqual(events, ['kill', 'wait'])

    def test_cgroup_retirement_continues_after_kill_error_once(self):
        tree = CgroupTree(self.root)
        tree.fd, tree.parent_fd, tree.created = 77, 78, True
        events = []
        def failure(*args):
            events.append('kill')
            raise OSError('generated kill failure')
        custody = Custody('generated_tree_test')
        with patch.object(tree, 'write', side_effect=failure), \
             patch.object(tree, 'events', return_value={'populated': 0}), \
             patch('critical.worker_transport.os.close', side_effect=lambda fd: events.append(('close', fd))), \
             patch('critical.worker_transport.os.rmdir', side_effect=lambda *a, **k: events.append('remove')):
            tree.retire(time.monotonic() + 1, custody)
            tree.retire(time.monotonic() + 1, custody)
        self.assertEqual(events.count('kill'), 1)
        self.assertTrue(tree.populated_zero and tree.removed)
        self.assertIsInstance(custody.first, OSError)

    def test_full_26_operation_assembly_and_remote_capture_replay(self):
        original = Original()
        scientific_plans = {key: {'population': value['population'],
                                  'science_review_status': 'independently_qualified'}
                            for key, value in catalogue().items()}
        bindings = {key: {'operation': key, 'native_plan_sha256': pin(encode(value))['sha256'],
                          'source_method_label': 'literal_author_kernel'}
                    for key, value in scientific_plans.items()}
        design = {'profile': 'complete', 'design_sha256': 'b' * 64,
                  'programme_sha256': pin(encode(contract('PROGRAMME.json')))['sha256']}
        workers = []
        def acquire(worker):
            workers.append(worker)
            worker.prefix = RemoteCostPrefix(worker.context.cost, worker.selection_pin)
            worker.prefix.dispatched = True
            worker.tree = GeneratedTree()
            worker.pid = 200000 + len(workers)
            worker.deadline = time.monotonic() + 2
            body = encode(source_row(worker.operation, decode(worker.producer.bindings), {}))
            terminal = {'kind': 'terminal', 'sequence': 1, 'selection': worker.selection_pin,
                        'status': 'complete', 'capture': base64.b64encode(body).decode(),
                        'cost_prefix': {'selection': worker.selection_pin, 'read': 1, 'write': 2,
                                        'reserved_read': 0, 'reserved_write': 0, 'operations': []},
                        'failure': {'first_error': None, 'errors': []}}
            worker.channel_owner = QueueChannel([terminal])
            return object()
        def wait(worker, deadline):
            worker.status = 0
        cost = Costs(1000, 1000)
        with patch.object(NativeWorker, '_acquire', acquire), patch.object(NativeWorker, '_wait', wait), \
             patch('critical.native_worker.wire_send'), \
             patch('critical.native_worker.os.fork', side_effect=AssertionError('actual fork forbidden')), \
             patch('critical.native.original_call', side_effect=AssertionError('scientific kernel forbidden')):
            result = run_reference_programme(Issuer(original), {'source_sha256': 'a' * 64}, plan(self.root),
                                             design, cost, scientific_plans, bindings, self.root, self.root, 'generated-only')
        rows = decode(result)['records']
        self.assertEqual(len(rows), 26)
        self.assertEqual([r['operation'] for r in rows], list(catalogue()))
        self.assertTrue(all(r['status'] == 'complete' for r in rows))
        self.assertEqual((cost.read, cost.write), (26, 52))
        self.assertEqual(original.closed, 1)
        self.assertEqual(len(workers), 26)
        self.assertTrue(all(w.terminal_closed and w.tree.calls == 1 for w in workers))
        worker = workers[0]
        worker.admit_capture(worker.capture)
        with self.assertRaises(Refusal):
            worker.admit_capture(copy.copy(worker.capture))
        with self.assertRaises(Refusal):
            worker.dispatch(worker.producer)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TransportTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful() or result.skipped or result.expectedFailures or result.unexpectedSuccesses:
        raise SystemExit(1)
