#!/usr/bin/env python3
"""Generated observation controls; no neural arrays, weights or tensor imports."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
import math
from pathlib import Path
import random
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
observer = ModuleType('_observer_under_test'); observer.__file__ = str(HERE/'observe.py')
exec(compile((HERE/'observe.py').read_bytes(), observer.__file__, 'exec'), observer.__dict__)


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def fake_native():
    """The maintained native.fit_reference/recipe.drive_fit, with an inert backend."""
    native = observer.load_module('_generated_native', HERE/'native.py',
                                  (HERE/'native.py').read_bytes())
    calls = []
    class Backend:
        def __init__(self, *, seed, profile, **kwargs):
            random.seed(seed)
            self.spec = native.recipe.reference_spec(seed, profile=profile)
            self.audit = []; self.runtime = {}; self.initial_rng = '0'*64
            self.attention_profile = 'generated'; self.initial_head_identity = '1'*64
            self.selected = None; calls.append(('construct', random.random()))
        def begin_stage(self, stage): self.stage = stage; calls.append(('begin', stage['name']))
        def train_epoch(self, epoch):
            self.train_batch('PRIVATE_INPUT_SENTINEL', labels='PRIVATE_LABEL_SENTINEL', epoch=epoch)
            self.audit.append({'epoch': epoch, 'stage': self.stage['name']})
        def train_batch(self, samples, labels, *, epoch):
            calls.append(('batch', self.stage['name'], epoch, random.random()))
        def validation_metrics(self):
            calls.append(('validation', self.stage['name']))
            return {'accuracy': .5, 'balanced_accuracy': .5}
        def snapshot_selected(self): self.selected = True; calls.append(('snapshot',))
        def restore_selected(self): calls.append(('restore',))
        def step_scheduler(self, accuracy): calls.append(('scheduler', accuracy))
        def save_checkpoint(self, path):
            calls.append(('save',)); body = b'GENERATED CHECKPOINT, NOT TENSORS'
            Path(path).write_bytes(body)
            return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
        def rng_identity(self): return '0'*64
    native.NativeReference = Backend
    return native, calls


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def make(self, name='trace.jsonl', **kwargs):
        tick = iter(i*.125 for i in range(1000))
        params = {'clock': lambda: next(tick), 'high_water': lambda: 100,
                  'current': lambda: 80}
        params.update(kwargs)
        return observer.Observer(self.root/name, command='fit', **params)

    def test_real_source_controller_and_cli_receipt_parity(self):
        info = {'materials_identity': '2'*64, 'data_identity': '3'*64,
                'records': [{'split':'train','shape':[6300,64,800]},
                            {'split':'val','shape':[1734,64,800]}]}
        (self.root/'info.json').write_text(json.dumps(info))
        def args(output):
            return ['fit','--info',str(self.root/'info.json'),'--packet',str(self.root),
                    '--author-source',str(self.root),'--profile','cpu-fp32-math',
                    '--overlay',str(self.root),'--encoder',str(self.root/'absent-weight'),
                    '--seed','42','--output',str(output)]
        plain, calls_plain = fake_native()
        operator = observer.load_module('_generated_operator', HERE/'run.py', (HERE/'run.py').read_bytes())
        operator._native_module = lambda: plain
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(operator.main(args(self.root/'plain')), 0)
        rng_plain = random.getstate()
        profiled, calls_profiled = fake_native()
        original_load = observer.load_module
        def load(name, path, body):
            return profiled if name == '_reve_observed_native' else original_load(name, path, body)
        with patch.object(observer, 'load_module', side_effect=load), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(observer.main(['--trace',str(self.root/'cost.jsonl'),'--',*args(self.root/'observed')]), 0)
        self.assertEqual(calls_plain, calls_profiled)
        self.assertEqual(rng_plain, random.getstate())
        self.assertEqual((self.root/'plain/fit.json').read_bytes(), (self.root/'observed/fit.json').read_bytes())
        self.assertEqual((self.root/'plain/classifier.pt').read_bytes(), (self.root/'observed/classifier.pt').read_bytes())
        report = records(self.root/'cost.jsonl')
        self.assertTrue(report[-1]['observation_complete'])
        self.assertEqual(sum(r.get('phase') == 'train_epoch' and r['record'] == 'begin' for r in report), 12)
        self.assertNotIn('PRIVATE_', (self.root/'cost.jsonl').read_text())
        self.assertNotIn('numpy', sys.modules); self.assertNotIn('torch', sys.modules)

    def test_exception_identity_and_methods_restored(self):
        native, _ = fake_native(); original = dict(vars(native.NativeReference))
        trace = self.make(); error = ValueError('PRIVATE_LABEL_SENTINEL')
        with self.assertRaises(ValueError) as caught:
            with observer.instrument(native, trace), trace.phase('operation'):
                raise error
        self.assertIs(caught.exception, error)
        for name in observer.METHODS: self.assertIs(getattr(native.NativeReference,name), original[name])
        self.assertFalse(trace.close(2))
        self.assertNotIn('PRIVATE', (self.root/'trace.jsonl').read_text())

    def test_nested_phase_parentage_and_no_phase_peak_claim(self):
        trace=self.make()
        with trace.phase('operation'):
            with trace.phase('train_batch'): pass
        self.assertTrue(trace.close(0))
        rows=records(self.root/'trace.jsonl')
        self.assertEqual([(r['record'],r['depth']) for r in rows if 'depth' in r], [('begin',0),('begin',1),('end',1),('end',0)])
        self.assertIn('not independent phase peak',rows[0]['high_water_scope'])
        self.assertNotIn('phase_peak_rss_bytes',json.dumps(rows))

    def test_sampler_failure_is_null_and_incomplete_not_zero(self):
        trace=self.make(current=lambda: (_ for _ in ()).throw(OSError('PRIVATE')))
        with trace.phase('operation'): pass
        self.assertFalse(trace.close(0)); rows=records(self.root/'trace.jsonl')
        self.assertIsNone(rows[1]['boundary_current_rss_bytes'])
        self.assertEqual(rows[-1]['failures'],['rss_current'])
        self.assertNotIn('PRIVATE',json.dumps(rows))

    def test_nonmonotonic_clock_is_not_valid_cost(self):
        ticks=iter([2.0,1.0]);trace=self.make(clock=lambda:next(ticks))
        with trace.phase('operation'): pass
        self.assertFalse(trace.close(0)); rows=records(self.root/'trace.jsonl')
        self.assertIsNone(rows[-2]['duration_seconds'])
        self.assertIn('clock',rows[-1]['failures'])

    def test_event_budget_does_not_change_backend_work(self):
        trace=self.make(max_events=2); reached=[]
        with trace.phase('operation'):
            with trace.phase('train_batch'): reached.append(True)
        self.assertEqual(reached,[True]); self.assertFalse(trace.close(0))
        self.assertIn('event_limit',records(self.root/'trace.jsonl')[-1]['failures'])

    def test_byte_budget_retains_incomplete_summary(self):
        trace=self.make(max_bytes=8192)
        for _ in range(40):
            with trace.phase('train_batch'): pass
        self.assertFalse(trace.close(0));path=self.root/'trace.jsonl'
        self.assertLessEqual(path.stat().st_size,8192)
        self.assertEqual(records(path)[-1]['record'],'summary')
        self.assertIn('byte_limit',records(path)[-1]['failures'])

    def test_unknown_phase_and_failure_fields_refused(self):
        trace=self.make()
        with self.assertRaises(ValueError):
            with trace.phase('labels'): pass
        with self.assertRaises(ValueError):trace.fail('PRIVATE_LOGIT')
        self.assertTrue(trace.close(0))
        self.assertNotIn('PRIVATE_LOGIT', (self.root/'trace.jsonl').read_text())

    def test_existing_or_linked_trace_is_never_overwritten(self):
        target=self.root/'existing';target.write_text('preserve')
        with self.assertRaises(FileExistsError):self.make(name='existing')
        (self.root/'linked').symlink_to(target)
        with self.assertRaises(OSError):self.make(name='linked')
        self.assertEqual(target.read_text(),'preserve')

    def test_source_identity_refuses_changed_dependency(self):
        for name in observer.PINS:(self.root/name).write_bytes((HERE/name).read_bytes())
        observer.pinned_sources(self.root)
        with (self.root/'native.py').open('ab') as stream:stream.write(b'\n# modified\n')
        with self.assertRaises(ValueError):observer.pinned_sources(self.root)

    def test_current_platform_rss_boundary_sample(self):
        self.assertGreater(observer.current_rss(),0)
        self.assertGreater(observer.high_water_rss(),0)

    def test_entry_preserves_maintained_no_bytecode_policy(self):
        native, _ = fake_native(); original_load = observer.load_module; seen = []
        def load(name, path, body):
            if name == '_reve_observed_native':
                seen.append(sys.dont_write_bytecode)
                return native
            return original_load(name, path, body)
        previous = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = False
            with patch.object(observer, 'load_module', side_effect=load), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                status = observer.main(['--trace',str(self.root/'no-bytecode.jsonl'),'--',
                    'fit','--info',str(self.root/'absent-info'),'--packet',str(self.root),
                    '--author-source',str(self.root),'--profile','cpu-fp32-math',
                    '--overlay',str(self.root),'--encoder',str(self.root/'absent-weight'),
                    '--seed','42','--output',str(self.root/'never-output')])
            self.assertEqual(status,2)
            self.assertEqual(seen,[True])
            self.assertTrue(sys.dont_write_bytecode)
        finally:
            sys.dont_write_bytecode = previous

    def test_predict_is_not_silently_partial_instrumentation(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            observer.main(['--trace',str(self.root/'never'), '--','predict'])
        self.assertEqual(caught.exception.code,2)
        self.assertFalse((self.root/'never').exists())


if __name__=='__main__':
    unittest.main()
