"""Focused parent-envelope controls; only invented tiny files and model metadata."""
from pathlib import Path
from types import SimpleNamespace
import ast
import json
import tempfile
import unittest
from unittest.mock import patch

from io_support import Budget, canonical_bytes
from phase_manifest import budget_snapshot
from phase_launcher import _receipt_write
from storage import write_json_fresh, write_array_fresh
from adapters.common import write_fresh
from adapters.contexts import ProviderContext

FIXTURE_DEBIT = 32768


class Clock:
    value = 0.0
    def fsync(self, fd): self.value = self.end


class OriginalBudget(Budget):
    def snapshot(self): return budget_snapshot(self)


def new_budget():
    return OriginalBudget({'source_read':65536,'artifact_write':65536},0.0,10.0)


class DeadlineControls(unittest.TestCase):
    def test_actual_shared_writes_admit_on_time_refuse_after_close(self):
        import numpy as np
        clock=Clock(); payload=np.array([[1.0,2.0],[3.0,4.0]],dtype=np.float64)
        with tempfile.TemporaryDirectory(prefix='neural053-deadline-v4-') as folder:
            for name,writer in (
                ('json',lambda p,b:write_json_fresh(p,{'invented':1},b)),
                ('array',lambda p,b:write_array_fresh(p,payload,b)),
                ('adapter',lambda p,b:write_fresh(p,b'invented\n',b))):
                for late in (False,True):
                    clock.value=0.0;clock.end=11.0 if late else 9.0;b=new_budget()
                    target=Path(folder)/(name+str(late))
                    with patch('io_support.time.monotonic',side_effect=lambda:clock.value),patch('os.fsync',side_effect=clock.fsync):
                        if late:
                            with self.assertRaises(ValueError):writer(target,b)
                        else:
                            pin=writer(target,b);self.assertEqual(pin['bytes'],target.stat().st_size)
                    self.assertTrue(target.is_file())
                    self.assertEqual(b.used['artifact_write'],target.stat().st_size)
                    # Late artifact is retained as failed evidence; never retried,
                    # overwritten or returned as a successful pin.

    def test_actual_phase_receipt_late_fsync_not_success(self):
        clock=Clock()
        with tempfile.TemporaryDirectory(prefix='neural053-receipt-v4-') as folder:
            for late in (False,True):
                clock.value=0.0;clock.end=11.0 if late else 9.0;b=new_budget();p=Path(folder)/str(late)
                with patch('io_support.time.monotonic',side_effect=lambda:clock.value),patch('os.fsync',side_effect=clock.fsync):
                    if late:
                        with self.assertRaises(ValueError):_receipt_write(p,{'schema':'invented-receipt'},b)
                    else:
                        pin=_receipt_write(p,{'schema':'invented-receipt'},b)
                        self.assertEqual(pin['bytes'],p.stat().st_size)
                        self.assertEqual(json.loads(p.read_bytes())['budget_after'],budget_snapshot(b))
                self.assertEqual(b.used['artifact_write'],p.stat().st_size)

    def test_actual_model_seal_final_return_clock(self):
        clock=Clock()
        for late in (False,True):
            clock.value=0.0;b=new_budget();context=object.__new__(ProviderContext)
            context.phase='training_admitted';context.work=Path('/invented-never-opened/work')
            context.training=Path('/invented-never-opened/training');context.budget=b
            context.factory=SimpleNamespace(config={'sandbox':{'workspace_cap_bytes':2048},'provider':{}},
                verify_current=lambda:None,_bound_source_digest='a'*64)
            pin={'path':'/invented-never-opened/artifact','bytes':0,'sha256':'b'*64}
            context.descriptors={'training':pin,'training_metadata':pin};context.source_records=[]
            context.namespace_id='invented';context.case={'mode':'fixed_program','replication':0,'fold_ordinal':0,'arm':'neural'}
            context.program=None;context.tool_records=[];context.provider=SimpleNamespace(records=[])
            context.docker=SimpleNamespace(resources=[]);context.events=[]
            context._event=lambda *a,**k:setattr(clock,'value',11.0 if late else 9.0)
            with patch('io_support.time.monotonic',side_effect=lambda:clock.value),\
                 patch('adapters.contexts.file_pin',return_value=pin),\
                 patch('adapters.contexts.json_exact',return_value={'schema':'neural053_row_plan_v1'}),\
                 patch('adapters.contexts.authenticate',return_value=pin):
                if late:
                    with self.assertRaises(ValueError):context._finish({'invented':1})
                else:
                    result=context._finish({'invented':1});self.assertEqual(result['plan']['schema'],'neural053_row_plan_v1')

    def test_explicit_final_boundaries_present(self):
        root=Path(__file__).resolve().parent
        for filename,function in [('frontdoor.py','execute_stage'),('adapters/worker.py','__call__'),
                                  ('adapters/process.py','run_python'),('adapters/process.py','verify_shared_clock')]:
            p=root/filename;size=p.stat().st_size;body=p.read_text();self.assertEqual(len(body.encode()),size)
            tree=ast.parse(body);node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==function)
            self.assertIsInstance(node.body[-1],ast.Return)
            preceding=node.body[-2]
            self.assertIsInstance(preceding,ast.Expr)
            self.assertIsInstance(preceding.value,ast.Call)
            self.assertEqual(preceding.value.func.attr,'check_clock')


if __name__=='__main__':unittest.main()
