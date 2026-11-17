"""Independent generated transport controls; no fork, cgroups, native kernels or data."""
import base64
from fractions import Fraction
import importlib.util
import math
from pathlib import Path
import socket
import struct
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

import test_native_transport as author
from critical.core import Costs, Refusal, encode, decode
from critical.native_worker import NativeWorker, NativeWorkerLease, RemoteWorkerFailure
from critical.worker_transport import ParentChannel, RemoteCostPrefix, wire_receive
from critical.programme import contract, catalogue
from critical import tensors

class PeerControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
    def tearDown(self):
        self.tmp.cleanup()
    def worker(self):
        original = author.Original()
        lease = NativeWorkerLease(original, "a"*64, encode(author.plan(self.root)))
        host = types.SimpleNamespace(lease=lease, source_sha256="a"*64)
        context = types.SimpleNamespace(authority=host, cost=Costs(100,100))
        slot = author.Slot()
        selected = {"operation":"generated", "source_sha256":"a"*64}
        worker = NativeWorker(lease,host,context,selected,slot)
        producer = types.SimpleNamespace(worker=worker,slot=slot,capture=None)
        worker.require("issuance",host,producer,selected)
        return worker,producer,original

    def test_truncated_frame_has_no_successful_decode(self):
        left,right=socket.socketpair()
        try:
            left.sendall(struct.pack("!Q",100)+b"{}")
            left.close()
            with self.assertRaisesRegex(Refusal,"closed before complete frame"):
                wire_receive(right,time.monotonic()+1,1024)
        finally:
            left.close()
            right.close()

    def test_diagnostic_overflow_is_rejected_before_receipt(self):
        import os
        left,right=socket.socketpair()
        reader,writer=os.pipe()
        try:
            os.write(writer,b"123456789")
            channel=ParentChannel(right,{reader:"stderr"},time.monotonic()+1,1024,2048,8)
            with self.assertRaisesRegex(Refusal,"diagnostic output limit"):
                channel.receive()
        finally:
            left.close();right.close();os.close(reader);os.close(writer)

    def test_attachment_failure_owns_every_resource_and_never_sends_go(self):
        worker,producer,_=self.worker()
        worker.lease.captured={"inert.py":b""}
        original=OSError("inert attachment failure")
        closed=[];signals=[];waits=[]
        class Socket:
            def close(self):closed.append(("socket",id(self)))
        parent,child=Socket(),Socket()
        class Tree:
            attached=False
            populated_zero=False
            removed=False
            calls=0
            def __init__(self,*args):pass
            def create(self):pass
            def attach(self,pid):raise original
            def retire(self,deadline,custody):
                self.calls+=1;self.populated_zero=True;self.removed=True
        def wait(deadline):
            waits.append(worker.pid);worker.status=0
        with patch("critical.native_worker.sys.platform","linux"), \
             patch("critical.native_worker.threading.enumerate",return_value=[object()]), \
             patch("critical.native_worker.CgroupTree",Tree), \
             patch("critical.native_worker.socket.socketpair",return_value=(parent,child)), \
             patch("critical.native_worker.os.pipe",side_effect=[(101,102),(103,104)]), \
             patch("critical.native_worker.os.fork",return_value=654321), \
             patch("critical.native_worker.os.close",side_effect=lambda fd:closed.append(("fd",fd))), \
             patch("critical.native_worker.os.kill",side_effect=lambda *args:signals.append(args)), \
             patch.object(worker,"_wait",side_effect=wait), \
             patch("critical.native_worker.wire_send",side_effect=AssertionError("GO forbidden")):
            with self.assertRaises(OSError) as caught:
                worker.dispatch(producer)
            self.assertIs(caught.exception,original)
            with self.assertRaises(OSError):
                worker.close()
        self.assertEqual(worker.tree.calls,1)
        self.assertEqual(len(signals),1)
        self.assertEqual(waits,[654321])
        self.assertEqual(sorted(x[1] for x in closed if x[0]=="fd"),[101,102,103,104])
        self.assertEqual(len([x for x in closed if x[0]=="socket"]),2)
        self.assertEqual((worker.context.cost.reserved_read,worker.context.cost.reserved_write),(100,100))
        self.assertIsNone(producer.capture)
        self.assertFalse(worker.terminal_closed)

    def test_wrong_source_phase_is_never_delegated(self):
        worker,_,original=self.worker()
        worker.channel_owner=author.QueueChannel([{"kind":"phase","sequence":1,
            "selection":worker.selection_pin,"phase":"native_operation:generated","source_sha256":"b"*64}])
        before=list(original.phases)
        with self.assertRaises(Refusal):
            worker._serve(object())
        self.assertEqual(original.phases,before)

    def test_completed_child_with_retirement_error_never_admits_capture(self):
        worker,producer,_=self.worker()
        failure=OSError("inert tree retirement failed")
        class Tree(author.GeneratedTree):
            def retire(self,deadline,custody):
                self.calls+=1
                custody.capture(failure,"inert_tree_failure")
        def acquire():
            worker.pid=654322
            worker.deadline=time.monotonic()+1
            worker.tree=Tree()
            worker.prefix=RemoteCostPrefix(worker.context.cost,worker.selection_pin)
            worker.prefix.dispatched=True
            worker.channel_owner=author.QueueChannel([{"kind":"terminal","sequence":1,
                "selection":worker.selection_pin,"status":"complete","capture":base64.b64encode(b"{}").decode(),
                "cost_prefix":{"selection":worker.selection_pin,"read":1,"write":2,
                               "reserved_read":0,"reserved_write":0,"operations":[]},
                "failure":{"first_error":None,"errors":[]}}])
            return object()
        def wait(deadline):worker.status=0
        with patch.object(worker,"_acquire",side_effect=acquire),patch.object(worker,"_wait",side_effect=wait), \
             patch("critical.native_worker.wire_send"):
            with self.assertRaises(OSError) as caught:
                worker.dispatch(producer)
        self.assertIs(caught.exception,failure)
        self.assertIsNone(producer.capture)
        self.assertFalse(worker.terminal_closed)
        self.assertEqual(worker.tree.calls,1)
        self.assertIsNotNone(worker.remote_terminal)
        self.assertEqual((worker.context.cost.read,worker.context.cost.write),(1,2))

    def test_malformed_remote_prefix_preserves_complete_unknown_reservation(self):
        worker,_,_=self.worker()
        worker.prefix=RemoteCostPrefix(worker.context.cost,worker.selection_pin)
        worker.prefix.dispatched=True
        worker.deadline=time.monotonic()+1
        worker.channel_owner=author.QueueChannel([{"kind":"terminal","sequence":1,
            "selection":worker.selection_pin,"status":"failed","capture":None,
            "cost_prefix":{"selection":worker.selection_pin,"read":1,"write":0,
                           "reserved_read":101,"reserved_write":0,"operations":[]},
            "failure":{"first_error":{"type":"GeneratedFailure"}}}])
        with patch("critical.native_worker.wire_send",side_effect=AssertionError("ACK forbidden")):
            with self.assertRaises(Refusal):
                worker._serve(object())
        self.assertIsNotNone(worker.remote_terminal)
        self.assertIsNone(worker.prefix.prefix)
        self.assertEqual((worker.context.cost.reserved_read,worker.context.cost.reserved_write),(100,100))
        self.assertEqual((worker.context.cost.read,worker.context.cost.write),(0,0))

    def test_observation_failure_keeps_first_error_and_closes_all_issued_workers(self):
        from critical.native_worker import run_reference_programme
        from critical.lifecycle import _RAISED_OWNERS
        from critical.core import pin
        original=author.Original()
        plans={k:{"population":v["population"],"science_review_status":"independently_qualified"}
               for k,v in catalogue().items()}
        bindings={k:{"operation":k,"native_plan_sha256":pin(encode(v))["sha256"],
                     "source_method_label":"literal_author_kernel"} for k,v in plans.items()}
        design={"profile":"complete","design_sha256":"b"*64,
                "programme_sha256":pin(encode(contract("PROGRAMME.json")))["sha256"]}
        first=Refusal("generated worker body failure")
        secondary=RuntimeError("generated transport observation failure")
        workers=[]
        issue=NativeWorkerLease.issue_reference_worker
        def retain(lease,*args):
            worker=issue(lease,*args);workers.append(worker);return worker
        with patch.object(NativeWorkerLease,"issue_reference_worker",retain), \
             patch.object(NativeWorker,"_acquire",side_effect=first), \
             patch.object(NativeWorker,"observation",side_effect=secondary), \
             patch("critical.native_worker.os.fork",side_effect=AssertionError("fork forbidden")):
            with self.assertRaises(Refusal) as caught:
                run_reference_programme(author.Issuer(original),{"source_sha256":"a"*64},author.plan(self.root),
                                        design,Costs(1000,1000),plans,bindings,self.root,self.root,"generated-only")
        self.assertIs(caught.exception,first)
        self.assertEqual(len(workers),26)
        self.assertTrue(all(worker.closed for worker in workers))
        self.assertEqual(original.closed,1)
        custody=_RAISED_OWNERS[id(first)][1]
        self.assertTrue(any(event.error is secondary for event in custody.events))

    def test_scientific_roster_and_open_gates_preserved(self):
        programme=contract("PROGRAMME.json")
        self.assertEqual(len(catalogue()),26)
        self.assertEqual(programme["profiles"]["complete"],programme["profiles"]["reproduction"])
        self.assertFalse(programme["full_paper_reproduced"])
        self.assertEqual(contract("COHORT.json")["session_count"],29)
        spectra=contract("SPECTRAL_CONTRACT.json")["dense_outputs"]
        self.assertEqual(len(spectra),40)
        self.assertTrue(all(x["shape"]==[10000,2] for x in spectra.values()))
        gates=contract("GATES.json")
        self.assertEqual(len(gates["gates"]),32)
        self.assertTrue(all(x["state"]=="open" for x in gates["gates"]))
        self.assertFalse(gates["source_construction_closes_scientific_gates"])

    def tensor_pair(self, candidate, reference):
        # Only the scalar loader is replaced; execute the actual scorer with
        # one-shot iterators, without any reference, native or data campaign.
        left, right = iter(candidate), iter(reference)
        with patch.object(tensors, "values", side_effect=[left, right]) as loader:
            result = tensors.pair_error(None, None, None, None, None, None)
        self.assertEqual(loader.call_count, 2)
        return result

    def assert_tensor_oracle(self, candidate, reference):
        residuals = [abs(x-y) for x,y in zip(candidate, reference)]
        expected = float(sum(map(Fraction, residuals), Fraction()) / len(residuals))
        result = self.tensor_pair(candidate, reference)
        self.assertEqual(result, {"mae": expected, "max_error": max(residuals),
                                  "count": len(residuals)})
        self.assertTrue(math.isfinite(result["mae"]))

    def test_tensor_large_repeated_finite_mean(self):
        for value in (1e308, sys.float_info.max):
            for count in (2, 3, 17):
                with self.subTest(value=value, count=count):
                    self.assertEqual(self.tensor_pair([value]*count, [0.]*count),
                                     {"mae": value, "max_error": value, "count": count})

    def test_tensor_signed_ordinary_values_preserve_mae(self):
        self.assert_tensor_oracle([-7., 0., 5., -2., 0.125],
                                  [-3., 1., -5., -3., -0.125])
        self.assert_tensor_oracle([1., 2., 3.], [0., 0., 0.])

    def test_tensor_integer_residuals_preserve_precision(self):
        self.assert_tensor_oracle([2**60+1, 2**60+3], [2**60, 2**60])
        self.assert_tensor_oracle([-10**308, 10**308], [0, 0])

    def test_tensor_subnormal_mean_rounds_after_accumulation(self):
        tiny = math.ulp(0.)
        for values in ([tiny]*17, [tiny, tiny, 0.], [tiny, tiny*2, tiny*3]):
            with self.subTest(values=values):
                self.assert_tensor_oracle(values, [0.]*len(values))

    def test_tensor_positive_underflow_refuses_but_exact_zero_is_valid(self):
        tiny = math.ulp(0.)
        for values in ([tiny, 0.], [tiny, 0., 0.]):
            with self.subTest(values=values), self.assertRaisesRegex(Refusal, "representable tensor mean"):
                self.tensor_pair(values, [0.]*len(values))
        self.assertEqual(self.tensor_pair([-0., 1., -1.], [0., 1., -1.]),
                         {"mae": 0., "max_error": 0., "count": 3})

    def test_tensor_dynamic_range_and_order_agree_with_exact_oracle(self):
        values = [sys.float_info.max, math.ulp(0.), 1., sys.float_info.max, 1e-100]
        for ordered in (values, list(reversed(values)), sorted(values)):
            self.assert_tensor_oracle(ordered, [0.]*len(ordered))
        # Deterministic generated controls span the full binary64 exponent
        # range. Fraction is an independent exact arithmetic mean oracle.
        import random
        rng = random.Random(50050)
        for _ in range(80):
            values = [math.ldexp(rng.uniform(-1., 1.), rng.randrange(-1073, 1024))
                      for _ in range(rng.randrange(2, 33))]
            self.assert_tensor_oracle(values, [0.]*len(values))

    def test_tensor_nonfinite_or_unrepresentable_residual_refuses(self):
        for candidate, reference in ((sys.float_info.max, -sys.float_info.max),
                                     (2**1023, -2**1023), (math.inf, 0.), (math.nan, 0.)):
            with self.subTest(candidate=candidate), self.assertRaisesRegex(Refusal, "finite residual"):
                self.tensor_pair([candidate], [reference])

    def test_tensor_complete_support_is_required(self):
        for left, right in (([1., 2.], [1.]), ([1.], [1., 2.])):
            with self.assertRaisesRegex(Refusal, "same complete tensor support"):
                self.tensor_pair(left, right)
        with self.assertRaisesRegex(Refusal, "nonempty complete tensor support"):
            self.tensor_pair([], [])

    def test_tensor_actual_generated_shards_keep_counts_and_io_cost(self):
        from critical.core import pin
        total_bytes = 0
        def descriptor(name, chunks):
            nonlocal total_bytes
            rows = []
            start = 0
            for index, values in enumerate(chunks):
                body = encode(values)
                path = "tensors/"+name+"/"+str(index)+".json"
                target = self.root/path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(body)
                rows.append({"path": path, **pin(body), "start": start, "count": len(values)})
                start += len(values)
                total_bytes += len(body)
            return {"schema": "critical_init_scalar_shards_v1", "shape": [start], "chunks": rows}
        candidate = descriptor("candidate", [[1e308], [1e308, 1e308]])
        reference = descriptor("reference", [[0., 0.], [0.]])
        costs = Costs(total_bytes, 0)
        result = tensors.pair_error(candidate, reference, {"shape": [3]}, self.root, self.root, costs)
        self.assertEqual(result, {"mae": 1e308, "max_error": 1e308, "count": 3})
        self.assertEqual((costs.read, costs.write, costs.reserved_read), (total_bytes, 0, 0))
        self.assertEqual(len(costs.operations), 4)

if __name__=="__main__":
    suites=[unittest.defaultTestLoader.loadTestsFromTestCase(author.TransportTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(PeerControls)]
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(suites))
    if result.testsRun!=34 or not result.wasSuccessful() or result.skipped or result.expectedFailures or result.unexpectedSuccesses:
        raise SystemExit(1)
