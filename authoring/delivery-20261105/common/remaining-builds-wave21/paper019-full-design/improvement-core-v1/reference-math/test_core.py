"""Tiny invented analytic controls; no authentic inputs, models or native tools."""
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest
sys.dont_write_bytecode = True
import core as m

ROOT = Path(__file__).resolve().parent
ENCODED = 0
ENCODING_CAP = 1024*1024
LIMITS = {"max_rows":16,"max_features":16,"max_pairs":120,
          "max_matrix_elements":256,"max_live_float_slots":4096}


def fixture(value):
    global ENCODED
    body = json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    ENCODED += len(body)
    assert ENCODED < ENCODING_CAP
    return value


def setting(family, lam=1.0, width=1.0):
    return next(s for s in m.settings() if s["family"]==family and s["lambda"]==lam and
                (family=="ridge" or s["width_multiplier"]==width))


def fit(X, times=(1.0,math.exp(2.0)), weights=(.25,.75), family="ridge", lam=1.0):
    fixture([X,list(times),list(weights)])
    return fixture(m.fit_head(X,list(times),list(weights),setting(family,lam),
                             ["invented-row-"+str(i) for i in range(len(X))],limits=LIMITS))


class Controls(unittest.TestCase):
    def test_01_exact_hierarchical_weights(self):
        rows=fixture([{"row_id":str(i),"animal":a,"session":s} for i,(a,s) in enumerate(
            [("a","a1"),("a","a2"),("a","a2"),("a","a2"),("b","b1"),("b","b1")])])
        w=fixture(m.group_weights(rows,["a","b"],{"a":["a1","a2"],"b":["b1"]}))
        self.assertEqual(w,[.25,1/12,1/12,1/12,.25,.25])
        self.assertEqual(math.fsum(w[:4]),.5);self.assertEqual(math.fsum(w[4:]),.5)
        with self.assertRaises(m.NumericFailure):m.group_weights(rows,["a","b"],{"a":["a1","a2","missing"],"b":["b1"]})

    def test_02_population_target_moments_and_no_renormalization(self):
        self.assertEqual(fixture(m.weighted_moments([0.,2.],[.25,.75])),{"mean":1.5,"variance":.75})
        self.assertEqual(m.weighted_moments([7.,7.],[.25,.75]),{"mean":7.,"variance":0.})
        with self.assertRaises(m.NumericFailure):m.weighted_moments([0.,2.],[.25,.5])

    def test_03_observed_only_constants_unobserved_and_indicators(self):
        values=fixture([[7.,None,1.,1],[7.,None,3.,0],[None,None,5.,1]])
        observed=fixture([[True,False,True,True],[True,False,True,True],[False,False,True,True]])
        state=fixture(m.fit_standardizer(values,observed,["continuous"]*3+["indicator"],[.2,.3,.5]))
        self.assertTrue(state['columns'][0]['constant_training'])
        self.assertEqual(state['columns'][0]['variance'],0.)
        self.assertTrue(state['columns'][1]['unobserved_training'])
        self.assertIsNone(state['columns'][1]['mean']);self.assertIsNone(state['columns'][1]['variance'])
        self.assertAlmostEqual(state['columns'][2]['mean'],3.6)
        self.assertAlmostEqual(state['columns'][2]['variance'],2.44)
        out=fixture(m.transform_standardizer(state,[[999.,12.,3.6,1]],[[True]*4]))
        self.assertEqual(out,[[0.,0.,0.,1.]])
        with self.assertRaises(m.NumericFailure):m.fit_standardizer([[3.]],[[False]],["continuous"],[1.])

    def test_04_exact_G_T_and_no_withdrawn_operand_access(self):
        base=[2.,-1.]; od=[1,0];oa=[1]; common=base*4; tail=[1.,0.,1.,1.,1.]
        expected={"B":common+tail,"D":common+[5.,0.]+tail,"ACh":common+[7.]+tail,"F":common+[5.,0.,7.]+tail}
        for v,wanted in expected.items():
            kwargs={}
            if v in ('D','F'):kwargs['n_D']=[5.,0.]
            if v in ('ACh','F'):kwargs['n_A']=[7.]
            self.assertEqual(fixture(m.build_variant(base,od,oa,1,1,variant=v,**kwargs)),wanted)
        class Poison:
            def __iter__(self):raise AssertionError('withdrawn numeric body touched')
            def __len__(self):raise AssertionError('withdrawn numeric body touched')
        with self.assertRaisesRegex(m.NumericFailure,'withdrawn_information'):
            m.build_variant(base,od,oa,1,1,variant='D',n_D=[5.,0.],n_A=Poison())
        self.assertEqual(m.build_variant([2.],[0],[1],0,1,variant='B'),[2.,0.,2.,0.,0.,1.,0.,1.])

    def test_05_nonuniform_epoch_exact_linear_integrals(self):
        times=fixture([-.4,-.023,.017,.19,.37,.6]);values=fixture([2*t+1 for t in times])
        for stratum,total,nbins in [('offer_CPIn',.84,12),('reward_SideOff',.84,12),('side_on',.84,12),('opt_out',.45,10)]:
            row=fixture(m.epoch_features(times,values,stratum))
            self.assertEqual(len(row['bins']),nbins);self.assertEqual(len(row['features']),nbins+1)
            self.assertAlmostEqual(row['integral'],total,places=14)
            for a,b,mean in zip(row['edges'],row['edges'][1:],row['bins']):self.assertAlmostEqual(mean,1+a+b,places=14)
        for ts,vs in [([0.,.6],[1.,2.]),([-.4,-.4,.6],[1.,2.,3.]),([-.4,.6],[1.,float('nan')])]:
            with self.assertRaises(m.NumericFailure):m.epoch_features(ts,vs,'offer_CPIn')

    def test_06_complete_positive_distance_multiset(self):
        self.assertEqual(m.positive_distance_median([[0.],[0.],[2.],[4.]],max_pairs=6),2.)
        self.assertEqual(m.positive_distance_median([[0.],[1.],[3.],[6.]],max_pairs=6),3.)
        with self.assertRaises(m.NumericFailure):m.positive_distance_median([[0.],[0.]],max_pairs=1)
        with self.assertRaises(m.NumericFailure):m.positive_distance_median([[0.],[1.],[2.]],max_pairs=2)

    def test_07_independent_ridge_formula_and_intercept_translation(self):
        model=fit([[0.],[2.]])
        expected_slope=.75/(.75+1.)
        expected_intercept=1.5-1.5*expected_slope
        pred=fixture(m.predict_head(model,[[0.],[2.],[3.]]))
        for x,y in zip((0.,2.,3.),pred):self.assertAlmostEqual(y,expected_intercept+expected_slope*x,places=13)
        self.assertAlmostEqual(model['target']['mean'],1.5);self.assertAlmostEqual(model['target']['variance'],.75)
        shifted=fit([[0.],[2.]],times=(math.exp(3.),math.exp(5.)))
        shifted_pred=fixture(m.predict_head(shifted,[[0.],[2.],[3.]]))
        for a,b in zip(pred,shifted_pred):self.assertAlmostEqual(b-a,3.,places=13)
        # No feature/intercept penalty: intercept-only head is the weighted mean.
        self.assertAlmostEqual(m.predict_head(fit([[],[]]),[[]])[0],1.5)

    def test_08_collinear_ridge_keeps_all_columns(self):
        model=fit([[0.,0.],[2.,2.]])
        self.assertEqual(len(model['coefficients']),2)
        self.assertAlmostEqual(model['coefficients'][0],model['coefficients'][1],places=13)
        slope=.75/(.75+.5)
        for x,y in zip((0.,2.),m.predict_head(model,[[0.,0.],[2.,2.]])):
            self.assertAlmostEqual(y,1.5-1.5*slope+slope*x,places=13)

    def test_09_RBF_two_row_independent_closed_form(self):
        model=fit([[-1.],[1.]],family='rbf')
        k=math.exp(-.5); z0=-math.sqrt(3.);z1=1/math.sqrt(3.)
        alpha=.25*.75*(z0-z1)/(2*.25*.75*(1-k)+1.)
        self.assertAlmostEqual(model['coefficients'][0],alpha,places=13)
        self.assertAlmostEqual(model['coefficients'][1],-alpha,places=13)
        self.assertEqual(model['positive_pair_median'],2.);self.assertEqual(model['sigma'],2.)
        pred=fixture(m.predict_head(model,[[-1.],[1.]]))
        self.assertAlmostEqual(.25*pred[0]+.75*pred[1],1.5,places=13)
        shifted=fit([[-1.],[1.]],times=(math.exp(3.),math.exp(5.)),family='rbf')
        for a,b in zip(pred,m.predict_head(shifted,[[-1.],[1.]])):self.assertAlmostEqual(b-a,3.,places=13)

    def test_10_complete_portfolio_and_exact_tie_order(self):
        grid=m.settings();self.assertEqual(len(grid),20)
        cells=fixture([{'setting_id':s['id'],'animal':a,'stratum':k,'loss':1.} for s in grid for a in ('a','b') for k in m.STRATA])
        selected=fixture(m.select_setting(cells,['a','b']))
        self.assertEqual(selected['setting'],setting('rbf',100.,2.));self.assertEqual(selected['complete_cells'],160)
        with self.assertRaises(m.NumericFailure):m.select_setting(cells[:-1],['a','b'])
        with self.assertRaises(m.NumericFailure):m.select_setting(cells+[cells[0]],['a','b'])
        chosen=setting('ridge',1e-6)
        modified=fixture([{**r,'loss':math.nextafter(1.,0.) if r['setting_id']==chosen['id'] else r['loss']} for r in cells])
        self.assertEqual(m.select_setting(modified,['a','b'])['setting'],chosen)

    def test_11_equal_session_validation_not_pooled_rows(self):
        rows=fixture([{'row_id':str(i),'animal':'held','session':'s1' if i==0 else 's2'} for i in range(4)])
        loss=m.validation_loss([0.]*4,[math.e]+[math.exp(2.)]*3,rows,'held',['s1','s2'],2.)
        self.assertAlmostEqual(loss,1.25)

    def test_12_preventive_failure_and_no_weak_survivor(self):
        class Poison:pass
        limits={**LIMITS,'max_rows':1}
        with self.assertRaisesRegex(m.NumericFailure,'preventive_extent_limit'):
            m.fit_head([[Poison()],[Poison()]],[1.,math.e],[.5,.5],setting('ridge'),['a','b'],limits=limits)
        with self.assertRaises(m.NumericFailure):fit([[0.],[1.]],times=(2.,2.))
        with self.assertRaises(m.NumericFailure):fit([[0.],[0.]],family='rbf')
        with self.assertRaises(m.NumericFailure):m._mul(1e-300,1e-300)
        model=fit([[-1.],[1.]],family='rbf');model['training_features'][0]=[]
        with self.assertRaises(m.NumericFailure):m.predict_head(model,[[0.]])


if __name__=='__main__':
    source=(ROOT/'core.py').read_bytes()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Controls)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    record={'schema':'ach_math_invented_analytic_controls_v1','attempt':1,
            'source':{'bytes':len(source),'sha256':hashlib.sha256(source).hexdigest()},
            'test_groups':result.testsRun,'failures':result.failures,'errors':result.errors,
            'passed':result.wasSuccessful(),'known_fixture_encoding_subtotal':ENCODED,
            'prospective_fixture_reservation':{'retained':131072,'cumulative':1048576,'live':2097152},
            'actual_authentic_data_keys_native_provider_models_science':0,
            'meaning':'Small analytic engineering fits only, not authentic scientific runs or runtime/resource qualification.'}
    record['failures']=[(str(t),msg) for t,msg in result.failures]
    record['errors']=[(str(t),msg) for t,msg in result.errors]
    body=(json.dumps(record,indent=2,sort_keys=True)+'\n').encode()
    assert ENCODED+len(body)<ENCODING_CAP
    (ROOT/'CONTROL_ATTEMPT_1.json').write_bytes(body)
    print(json.dumps({'passed':result.wasSuccessful(),'groups':result.testsRun,'encoded_fixture_bytes_including_receipt':ENCODED+len(body)}))
    sys.exit(0 if result.wasSuccessful() else 1)
