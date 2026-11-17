"""Invented source controls; no real numeric inputs, timers or child processes."""
import importlib.util,sys,json,unittest,ast,hashlib
from pathlib import Path
from unittest.mock import patch,Mock,MagicMock
HERE=Path(__file__).absolute().parent
sys.path.insert(0,str(HERE))
import controller as c
import observe as o

def enc(x):return (json.dumps(x,sort_keys=True,separators=(',',':'))+'\n').encode()
class Budget:
    read=0;written=0;retained_charge=0
    def deadline(self):pass
    def reading(self,n):self.read+=n
    def writing(self,n):self.written+=n
    def metadata(self,n):self.written+=n
    def producer_writes(self,n):self.written+=n
class Tests(unittest.TestCase):
    def test_fullcontexts_and_latefailure(self):
        events=[]
        class Op:
            def commit_all_four_before_data(self):events.append('freeze')
            def phase(self,ctx):events.append(ctx['phase_id']);return ctx
            def complete(self,rows):events.append('complete');return rows
        rows=c.run_sequence(Op());self.assertEqual(len(rows),5);self.assertEqual(events[0],'freeze');self.assertEqual(events[-1],'complete');self.assertEqual(rows[-1]['role'],'reference')
        class Fail(Op):
            def phase(self,ctx):
                if ctx['role']=='reference':raise ValueError('late')
                return super().phase(ctx)
        events.clear()
        with self.assertRaises(ValueError):c.run_sequence(Fail())
        self.assertNotIn('complete',events)
    def test_binding_fullscope_no_private(self):
        b=c.bindings(json.loads((HERE/'BINDINGS.json').read_bytes()))
        for arm,n in [('A',20),('B',43)]:
            rows=c.route_rows(b,{'role':'reproduction','arm':arm},Path('/invented/repo'))
            self.assertEqual(len(rows),n);self.assertFalse(any('truth' in r['target'] or 'baseline' in r['target'] or r['target'].endswith('.pkl') for r in rows))
        wrong=json.loads(json.dumps(b));wrong['coverage']['units']-=1
        with self.assertRaises(ValueError):c.bindings(wrong)
        self.assertEqual(len(b['reference_assets']),5)
    def test_validate_full_identity_without_scalar_experiment(self):
        # Mock parser's full-size support in memory; no actual scorer or numeric estimates.
        meta={'condition':'improvement'};values={k:[None]*100000 for k in (*c.validation.BASE,*c.validation.EXTRA)}
        with patch.object(c.validation,'validate',return_value=(values,meta)) as v:
            result=c.validate_artifact(b'x',b'{}','improvement');self.assertEqual(result['required_rows'],600000);self.assertEqual(set(result['failed_fit_counts'].values()),{100000});v.assert_called_once()
            with self.assertRaises(ValueError):c.validate_artifact(b'x',b'{}','reproduction')
    def test_exact_validation_source_extraction(self):
        parent=Path('authoring/delivery-20261105/isttc/private/grader.py');a=ast.parse(parent.read_bytes());b=ast.parse((HERE/'validation.py').read_bytes())
        for name in ('strict_json','validate'):
            aa=next(n for n in a.body if isinstance(n,ast.FunctionDef) and n.name==name);bb=next(n for n in b.body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertEqual(ast.dump(aa,include_attributes=False),ast.dump(bb,include_attributes=False))
        self.assertFalse(any(isinstance(n,ast.FunctionDef) and n.name in ('grade','errors','fixed_truth') for n in b.body))
    def test_failure_cleanup_independent(self):
        for mod in (c,o):
            calls=[]
            def timer(*args):calls.append('cancel');raise OSError('cancel')
            with patch.object(mod.signal,'setitimer',side_effect=timer),patch.object(mod.signal,'signal',side_effect=lambda s,h:calls.append(s)):
                with self.assertRaises(RuntimeError):mod.cleanup_clock()
            self.assertEqual(len(calls),4)
    def test_startup_arm_failure_and_inherited(self):
        for mod in (c,o):
            calls=[]
            def timer(*a):calls.append(('timer',a));raise OSError('arm')
            with patch.object(mod.signal,'getitimer',return_value=(0.,0.)),patch.object(mod.signal,'setitimer',side_effect=timer),patch.object(mod.signal,'signal',side_effect=lambda *a:calls.append(('signal',a))):
                with self.assertRaises(OSError) as e:mod.enter_startup()
                self.assertTrue(e.exception.__notes__);self.assertEqual(len(calls),6)
            with patch.object(mod.signal,'getitimer',return_value=(1.,0.)),patch.object(mod.signal,'setitimer') as timer,patch.object(mod.signal,'signal') as sig:
                with self.assertRaises(RuntimeError):mod.enter_startup()
                timer.assert_not_called();sig.assert_not_called()
    def test_budget_full_derivation(self):
        r=json.loads((HERE/'RESOURCE_PLAN.json').read_bytes());b=json.loads((HERE/'BINDINGS.json').read_bytes())
        staged=sum(sum(x['bytes'] for x in c.route_rows(b,ctx,Path('/repo'))) for ctx in c.contexts());self.assertGreater(staged,10*1024**3)
        self.assertLess(4*staged+5*174003616+5*100020000+4*8*1024**2,64*1024**3)
        self.assertEqual(r['full_phase_sum'],874200);self.assertEqual(r['whole_retained_reservation'],3*1024**3+16*1024**2)
    def test_all_failed_and_large_tau_are_valid_not_filtered(self):
        # Original literal validation only on three invented units: no scoring.
        meta=enc({'schema':'isttc_submission_v1','condition':'reproduction','source_commit':c.validation.REV,'notes':'invented'})
        text='unit_id,method,status,tau_ms\n'+''.join(f'{i},{m},'+('ok,1e300\n' if i==0 else 'failed,\n') for m in c.validation.BASE for i in range(3))
        data,_=c.validation.validate(text.encode(),meta,n=3);self.assertEqual(data['acf'],[1e300,None,None])
        with self.assertRaises(c.validation.Invalid):c.validation.validate(text.rsplit('\n',2)[0].encode(),meta,n=3)
    def test_engine_source_and_full_outputs(self):
        e=c.load('isttc_test_engine',HERE/'engine/native.py')
        self.assertEqual({tuple(x) for x in e.OUTPUTS.values()},{('estimates.csv','methods.json')})
        for role in ('reproduction','improvement','reference'):
            self.assertEqual(sum(e.TIMES[role].values()),174840);self.assertEqual(e.PROFILES[role]['memory'],8*1024**3);self.assertEqual(e.phase_budget(role,2)['max_calls'],158)
    def test_retirement_credit_only_after_durable_complete_cleanup(self):
        import staging
        for fault in ('none','unlink','sync','closure'):
            v=staging.View.__new__(staging.View);v.live=True;v.root=MagicMock();v.budget=Mock();v.retirement_credit=12345;v.verify=Mock()
            if fault=='unlink':v.root.__truediv__.return_value.unlink.side_effect=OSError('injected')
            check=Mock(side_effect=ValueError('closure') if fault=='closure' else None)
            with patch.object(staging,'tree',return_value=({'x':object()},[])),patch.object(staging.os,'chmod'),patch.object(staging,'sync',side_effect=OSError('sync') if fault=='sync' else None):
                if fault=='none':v.retire_after_closed_execution({},check);v.budget.release_retired.assert_called_once_with(12345);self.assertFalse(v.live)
                else:
                    with self.assertRaises((OSError,ValueError)):v.retire_after_closed_execution({},check)
                    v.budget.release_retired.assert_not_called();self.assertTrue(v.live)
        q=c.Budget(Path('/invented'),10**30,read_cap=100,write_cap=100,retained_cap=100,other_future=0);q.retained_charge=50;q.read=25;q.written=40
        q.release_retired(30);self.assertEqual((q.retained_charge,q.read,q.written),(20,25,40))
        with self.assertRaises(ValueError):q.release_retired(21)

    def test_public_source_excerpts_exclude_outputs(self):
        b=json.loads((HERE/'BINDINGS.json').read_bytes());p=next(r['source'] for r in b['candidate_assets']['B'] if r['target']=='SOURCE_NOTEBOOK_CELLS.json');j=json.loads(Path(p).read_bytes())
        self.assertEqual(j['schema'],'source_code_excerpts_v1')
        for notebook in j['notebooks']:
            self.assertNotIn('outputs',notebook)
            for cell in notebook['code_cells']:self.assertEqual(set(cell),{'cell_index_zero_based','source'});self.assertIsInstance(cell['source'],str)
if __name__=='__main__':unittest.main(verbosity=2)
