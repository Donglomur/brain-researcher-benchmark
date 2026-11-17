"""Invented source/control checks only. No scientific input/optimizer/scorer run."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

BASE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location('_test_spatial_' + name, BASE / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


B = load('baseline'); C = B.C; G = load('grading')


def persons():
    return [{'participant': p, 'electrode_ids': ['invented_%s_%d' % (p, i) for i in range(n)]}
            for p, n in C.S.protocol.RELEASED_COUNTS.items()]


def panel(rows, sha='a'*64):
    return {'schema': 'visual_alpha_parameters_v1', 'roster_sha256': sha,
            'cases': [{'case_id': r['case_id'], **{role: [50.5,50.5,2.5,0.,0.] for role in C.ROLES}} for r in rows]}


def budget():
    return B.Budget({'origin': 0., 'deadline': 10., 'max_forward_calls': 100,
                     'max_residual_calls': 100}, clock=lambda: 1.)


class Controls(unittest.TestCase):
    def test_gain_signed_dc_and_constant(self):
        h = np.array([1., 2., 4.]); y = -3*h + 100
        gain, residual, sse = B.training_gain(y,h,sign_free=True)
        self.assertAlmostEqual(gain,-3.); self.assertLess(sse,1e-25)
        self.assertEqual(B.training_gain(y,h,sign_free=False)[0],0.)
        self.assertEqual(B.training_gain(y,np.ones(3),sign_free=True)[0],0.)

    def test_underflow_witnesses(self):
        h = np.array([1., 2., 3.])*1e-200
        gain, _, sse = B.training_gain(2*h,h,sign_free=True)
        self.assertAlmostEqual(gain,2.); self.assertEqual(sse,0.)
        gain, _, sse = B.training_gain(np.array([1.,2.,3.]),h,sign_free=True)
        self.assertAlmostEqual(gain/1e200,1.); self.assertLess(sse,1e-25)
        with self.assertRaisesRegex(ValueError,'sse_underflow'):
            B.training_gain(np.array([1.,3.,1.])*1e-200,np.array([1.,2.,3.]),sign_free=True)

    def test_source_grid_counts_order(self):
        grid = B.geometry_grid()
        self.assertEqual(len(grid),3969); self.assertEqual(len(set(grid)),2835)
        self.assertEqual(grid[0],(50.5,50.5,np.sqrt(.5)))
        self.assertEqual(grid[1],(50.5,50.5,.5))
        self.assertTrue(all(-49<=r<=150 and -49<=c<=150 for r,c,s in grid))
        self.assertEqual(len(B.RATIOS),18)

    def test_blocked_vs_scalar_signed_nonbinary(self):
        # 4x4x7 invented aperture, 17 geometries force a second partial block.
        aperture = (np.arange(112,dtype=float).reshape(4,4,7)-50.)/7.
        geometries = [(1.2+i*.1,2.7,.7+i*.03) for i in range(17)]
        idx = [0,2,5,6]; b = budget()
        actual = B.project_og_grid(aperture,idx,geometries,b)
        expected = np.array([C.S.forward.evaluate(aperture,[*g,1.,0.],model='OG')['prediction'][idx] for g in geometries])
        np.testing.assert_allclose(actual,expected,rtol=5e-14,atol=5e-14)
        self.assertEqual(b.forward_calls,17)
        # Independent literal pixel-sum witness fixes row/column orientation.
        r,c,s = geometries[0]
        manual = [sum(aperture[i,j,t]*np.exp(-.5*((i+1-r)/s)**2-.5*((j+1-c)/s)**2)/(2*np.pi*s*s)
                      for i in range(4) for j in range(4)) for t in idx]
        np.testing.assert_allclose(actual[0],manual,rtol=5e-14,atol=5e-14)

    def test_original_boundary_unsupported_retained(self):
        a = np.ones((4,4,3))
        for params in ([2.5,2.5,0.,1.,0.],[2.5,2.5,1.,1.,1.]):
            self.assertEqual(C.S.forward.evaluate(a,params)['status'],'unsupported')
        rows=C.full_roster(persons()); raw=panel(rows)
        raw['cases'][-1]['train_second'][2]=0.
        self.assertEqual(len(C.admit_panel(C.encode(raw),rows,'a'*64)['cases']),3464)

    def test_all27_assembly_and_complete_condition_identity(self):
        rows=C.full_roster(persons()); raw={}
        for p in C.S.protocol.PARTICIPANTS:
            for role in C.ROLES:
                raw[p,role]=C.encode({'schema':'visual_alpha_context_parameters_v1','roster_sha256':'a'*64,
                    'participant':p,'role':role,'cases':[{'case_id':r['case_id'],'parameters':[50.5,50.5,1.,0.,0.]} for r in C.context_rows(rows,p)]})
        out=C.assemble_contexts(raw,rows,'a'*64)
        self.assertEqual(len(out['cases']),3464)
        del raw['p11','train_second']
        with self.assertRaisesRegex(ValueError,'27'):
            C.assemble_contexts(raw,rows,'a'*64)
        altered=[dict(r) for r in rows]; altered[-1]['electrode_id']='wrong-but-unique'
        with self.assertRaisesRegex(ValueError,'bijection'):
            C.context_rows(altered,'p11')

    def test_half_response_shape_refused_before_aperture_read(self):
        rows=C.full_roster(persons())
        context={'participant':'p01','role':'train_first','response_indices':list(range(38)),
                 'signals':{s:{'responses':np.empty((11,75)), 'aperture':object(),
                    'aperture_identity':'b'*64,'band':C.S.protocol.band('p01',s)} for s in C.S.protocol.SIGNALS}}
        with self.assertRaisesRegex(ValueError,'no hidden test half'):
            B.validate_context(context,rows)

    def test_last_candidate_rejected_before_protected_callbacks(self):
        rows=C.full_roster(persons()); raw=C.encode(panel(rows)); calls=[]
        candidates={name:raw for name in C.PANELS}
        broken=panel(rows); broken['cases'][-1]['train_second'][2]=-1.
        candidates['corrected_B']=C.encode(broken)
        with self.assertRaises(ValueError):
            G.grade_panels(candidates,persons(),'a'*64,capture_operator_baseline=lambda:calls.append('baseline'),
                expected_baseline_pin=C.pin(raw),load_person=lambda p:calls.append('private'))
        self.assertEqual(calls,[])

    def test_baseline_pin_mismatch_before_private_and_candidate_extra_refused(self):
        rows=C.full_roster(persons()); raw=C.encode(panel(rows)); calls=[]
        candidates={name:raw for name in C.PANELS}
        with self.assertRaisesRegex(ValueError,'baseline identity'):
            G.grade_panels(candidates,persons(),'a'*64,capture_operator_baseline=lambda:raw+b' ',
                expected_baseline_pin=C.pin(raw),load_person=lambda p:calls.append(p))
        self.assertEqual(calls,[])
        candidate=panel(rows);candidate['baseline_gain']=100
        with self.assertRaises(ValueError):C.admit_panel(C.encode(candidate),rows,'a'*64)

    def test_deadline_and_call_caps_prevent_work(self):
        b=budget();b.limits['max_forward_calls']=1;b.take('forward')
        with self.assertRaisesRegex(RuntimeError,'call_cap'):b.take('forward')
        self.assertEqual(b.forward_calls,1)
        b.clock=lambda:10.
        with self.assertRaisesRegex(RuntimeError,'deadline'):b.take('residual')
        self.assertEqual(b.residual_calls,0)

    def test_four_starts_failure_retained_and_status0_finite(self):
        starts=[(50.5,50.5,s,0.) for s in (25.,2.5,1.,2.)]
        calls=[]
        def unit(a,geometry,ratio,idx,b):
            b.take('forward'); return np.array([1.,2.,3.])
        def solve(fun,x0,**kw):
            calls.append(kw);fun(np.array(x0));return SimpleNamespace(x=np.array(x0),status=0,nfev=1)
        report={}
        with patch.object(B,'choose_starts',return_value=starts),patch.object(B,'_unit',side_effect=unit):
            params=B.fit_case(np.array([2.,4.,6.]),None,[0,1,2],[],model='OG',sign_free=False,budget=budget(),solver=solve,audit=report)
        self.assertEqual(len(calls),4);self.assertEqual(params[3],2.)
        self.assertTrue(all(r['status']=='evaluation_limit' for r in report['starts']))
        self.assertTrue(all(k['max_nfev']==500 and k['method']=='trf' and k['jac']=='2-point' for k in calls))
        calls.clear();report={}
        # Separate counter because solve appends its call dictionary.
        n=[0]
        def failed2(fun,x0,**kw):
            n[0]+=1
            if n[0]==2:raise RuntimeError('invented solver failure')
            return solve(fun,x0,**kw)
        with patch.object(B,'choose_starts',return_value=starts),patch.object(B,'_unit',side_effect=unit):
            with self.assertRaisesRegex(RuntimeError,'invented'):
                B.fit_case(np.array([2.,4.,6.]),None,[0,1,2],[],model='OG',sign_free=False,budget=budget(),solver=failed2,audit=report)
        self.assertEqual([r['status'] for r in report['starts']],['evaluation_limit','failed','not_entered','not_entered'])

    def test_resource_formulas_no_invented_runtime_default(self):
        a=B.prospective_resources('p05','train_second',distinct_apertures=2)
        self.assertEqual(a['cases'],280);self.assertEqual(a['response_bytes'],4*35*37*8)
        self.assertEqual(a['grid_kernel_elements'],2*3969*10000)
        self.assertIsNone(a['wall_seconds']);self.assertIsNone(a['process_memory_bytes'])

    def test_native_unavailable_conversion_is_explicit(self):
        native={role:np.array([[50.5,50.5,2.5,1.,0.],[np.nan]*5]) for role in C.ROLES}
        G._native_parameters(native,2)
        native['train_first'][1,0]=0.
        with self.assertRaisesRegex(ValueError,'all-NaN'):
            G._native_parameters(native,2)
        native['train_first'][1,:]=np.inf
        with self.assertRaisesRegex(ValueError,'all-NaN'):
            G._native_parameters(native,2)

    def test_source_nonfinite_support_retained(self):
        value=np.array([[1.,np.nan,np.inf,-np.inf]])
        self.assertIs(C.source_responses(value,(1,4)),value)
        np.testing.assert_array_equal(np.isfinite(value),[[True,False,False,False]])
        report={}
        params=B.fit_case(np.array([np.inf,-np.inf,np.nan]),None,[0,1,2],[],
                         model='OG',sign_free=False,budget=budget(),solver=None,audit=report)
        self.assertEqual(params,[50.5,50.5,0.,0.,0.])
        self.assertEqual(report['status'],'unsupported_no_training_support')


if __name__=='__main__':
    unittest.main(verbosity=2)
