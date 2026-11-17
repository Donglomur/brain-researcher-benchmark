"""Invented mathematical/interface fixtures only; no neural observations."""
import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import likelihood as m
import cli


def curve(coeff=None,knots=None,quad=None):
    return {'policy':m.POLICY,'rate_units':'Hz','knots_seconds':knots or [0.,1.],
            'coefficients':coeff or [[2.,0.,0.,0.]],'quadrature_seconds':quad or [0.,1.]}


def complete_fixture():
    roster=[];episodes=[]
    units=[2**53+1,2**53+2,2**53+3]
    for subject in (0,1):
        for session in range(15):
            pid=f'p{subject}-{session}'
            roster.append({'population_id':pid,'subject_id':subject,'session_id':session,'uids':list(units)})
            for trial,condition in enumerate(sorted(m.CONDITIONS)):
                episodes.append({'population_id':pid,'subject_id':subject,'session_id':session,'trial_id':trial,
                                 'stimulus_condition':condition,'duration_seconds':1.,'chosen_side':'SECRET',
                                 'nested_secret':{'held_spikes':[.1,.9]},'spikes':[
                                     {'unit_id':u,'dense_neuron_index':i,'spike_seconds_from_window_start':[] if i==0 else [.25,.75],
                                      'unknown_nested':{'answer':123}} for i,u in enumerate(units)]})
    projection={'schema':'neuralflow-row-projection-v1','source_clock':'absolute_seconds',
                'endpoint_policy':'closed','episodes':episodes}
    index=m.build_lono_index(projection,roster)
    predictions=[];bindings={}
    for key,episode in index['episodes'].items():
        for unit in episode['spikes']:
            k=key+(unit['unit_id'],)
            predictions.append(dict(zip(('population_id','subject_id','session_id','trial_id','unit_id'),k),
                                    fit_status='fallback_after_fit_failure' if unit['dense_neuron_index']==0 else 'fit',curve=curve()))
            bindings[k]={'knots_seconds':[0.,1.],'quadrature_seconds':[0.,1.]}
    return roster,projection,index,predictions,bindings


class LikelihoodTests(unittest.TestCase):
    def test_constant_process(self):
        s=m.curve_log_density([.25,.75],1,curve(),'closed')
        self.assertAlmostEqual(s['log_density_nats'],2*math.log(2)-2)
        self.assertEqual(s['integrated_intensity'],2.)

    def test_silent_trial_retained(self):
        self.assertEqual(m.curve_log_density([],1,curve(),'closed')['log_density_nats'],-2.)

    def test_exact_curvature_integral_prevents_trapezoid_game(self):
        s=m.curve_log_density([.5],1,curve([[0.,4.,-4.,0.]]),'closed')
        self.assertAlmostEqual(s['log_density_nats'],-2/3)
        self.assertAlmostEqual(s['integrated_intensity'],2/3)
        self.assertEqual(s['trapezoid_integral_diagnostic'],0.)

    def test_positive_endpoints_negative_interior_rejected(self):
        with self.assertRaises(m.ContractError):m.curve_log_density([],1,curve([[.01,-1.,1.,0.]]),'closed')

    def test_tiny_interval_negative_interior_regression(self):
        width = 1e-200
        coefficients = [2e-93, -1e108, 1e308, 0.]
        self.assertGreater(m._poly(coefficients, 0.), 0.)
        self.assertGreater(m._poly(coefficients, width), 0.)
        self.assertLess(m._poly(coefficients, width / 2), 0.)
        with self.assertRaisesRegex(m.ContractError, 'negative cubic intensity between knots'):
            m.curve_log_density([], width,
                curve([coefficients], [0., width], [0., width]), 'closed')

    def test_generated_extreme_width_quadratics(self):
        # A*(3/16-u+u**2) has positive endpoints and minimum -A/16.
        # Raising its constant to 5*A/16 gives minimum A/16 and integral 7*A*w/48.
        for width_exponent, coefficient_exponent in (
                (0, 0), (-100, 100), (-500, 1000), (-540, 1000),
                (-600, 1000), (-660, 1000), (600, -1000)):
            width = math.ldexp(1., width_exponent)
            amplitude = math.ldexp(1., coefficient_exponent + 2 * width_exponent)
            coefficients = [3 * amplitude / 16,
                -math.ldexp(1., coefficient_exponent + width_exponent),
                math.ldexp(1., coefficient_exponent), 0.]
            with self.subTest(width_exponent=width_exponent):
                with self.assertRaisesRegex(m.ContractError, 'negative cubic intensity between knots'):
                    m.curve_log_density([], width,
                        curve([coefficients], [0., width], [0., width]), 'closed')
                coefficients[0] = 5 * amplitude / 16
                score = m.curve_log_density([], width,
                    curve([coefficients], [0., width], [0., width]), 'closed')
                self.assertTrue(math.isclose(score['integrated_intensity'],
                    7 * amplitude * width / 48, rel_tol=1e-14))
                self.assertFalse(score['zero_event_density'])

    def test_generated_extreme_width_cubics(self):
        # A*(3/16-3*u/4+u**3) has its interior minimum -A/16 at u=1/2.
        # Raising its constant to 5*A/16 gives minimum A/16 and integral 3*A*w/16.
        for width_exponent, coefficient_exponent in (
                (0, 0), (-100, 100), (-350, 1000), (-360, 1000),
                (-400, 1000), (-500, 1000), (400, -1000)):
            width = math.ldexp(1., width_exponent)
            amplitude = math.ldexp(1., coefficient_exponent + 3 * width_exponent)
            coefficients = [3 * amplitude / 16,
                -.75 * math.ldexp(1., coefficient_exponent + 2 * width_exponent),
                0., math.ldexp(1., coefficient_exponent)]
            with self.subTest(width_exponent=width_exponent):
                with self.assertRaisesRegex(m.ContractError, 'negative cubic intensity between knots'):
                    m.curve_log_density([], width,
                        curve([coefficients], [0., width], [0., width]), 'closed')
                coefficients[0] = 5 * amplitude / 16
                score = m.curve_log_density([], width,
                    curve([coefficients], [0., width], [0., width]), 'closed')
                self.assertEqual(score['integrated_intensity'], 3 * amplitude * width / 16)
                self.assertFalse(score['zero_event_density'])

    def test_finite_cubic_derivative_overflow_regression(self):
        with self.assertRaises(m.ContractError):
            m.curve_log_density([],1,curve([[5e307,-1.5e308,0.,1e308]]),'closed')

    def test_large_grid_linear_work_path(self):
        # A permitted wire-size construction, not a timing/performance claim.
        knots=[i/9999 for i in range(10000)]
        s=m.curve_log_density([],1,curve([[2.,0.,0.,0.] for _ in range(9999)],knots,knots),'closed')
        self.assertAlmostEqual(s['integrated_intensity'],2.)
        self.assertAlmostEqual(s['trapezoid_integral_diagnostic'],2.)

    def test_zero_rate_observed_spike_has_negative_infinite_density(self):
        s=m.curve_log_density([0.],1,curve([[0.,1.,0.,0.]]),'closed')
        self.assertIsNone(s['log_density_nats']);self.assertTrue(s['zero_event_density'])
        self.assertEqual(s['integrated_intensity'],.5)

    def test_all_zero_silent_process_is_valid(self):
        s=m.curve_log_density([],1,curve([[0.,0.,0.,0.]]),'closed')
        self.assertEqual(s['log_density_nats'],0.);self.assertFalse(s['zero_event_density'])

    def test_explicit_endpoint(self):
        m.curve_log_density([0.,1.],1,curve(),'closed')
        with self.assertRaises(m.ContractError):m.curve_log_density([1.],1,curve(),'left_closed_right_open')

    def test_bad_grid_policy_or_rate_rejected(self):
        for updates in ({'policy':'historical_default'},{'rate_units':'kHz'},
                        {'knots_seconds':[.01,1.]},{'quadrature_seconds':[0.,0.,1.]},
                        {'coefficients':[[2.,float('nan'),0.,0.]]}):
            c=curve();c.update(updates)
            with self.subTest(updates=updates),self.assertRaises(m.ContractError):m.curve_log_density([],1,c,'closed')

    def test_nonuniform_piecewise_integral(self):
        c=curve([[1.,2.,0.,0.],[2.,0.,0.,0.]],[0.,.5,1.],[0.,.25,.5,1.])
        self.assertEqual(m.curve_log_density([],1,c,'closed')['integrated_intensity'],1.75)

    def test_small_intensity_logs_do_not_underflow(self):
        s=m.curve_log_density([.5],1,curve([[1e-300,0.,0.,0.]]),'closed')
        self.assertAlmostEqual(s['log_density_nats'],math.log(1e-300))

    def test_per_neuron_rt_normalization(self):
        result=m.normalized_population_comparison({'joint_log_density':-10,'reaction_time_log_density':-2},
              [{'unit_id':7,'joint_log_density':-4,'reaction_time_log_density':-1},
               {'unit_id':8,'joint_log_density':-5,'reaction_time_log_density':-3}],[7,8])
        self.assertEqual(result['population_log_density_nats'],-8)
        self.assertEqual(result['independent_log_density_nats'],-5)
        self.assertEqual(result['population_minus_independent_nats'],-3)

    def test_constituent_complete_support(self):
        p={'joint_log_density':0,'reaction_time_log_density':0}
        for rows in ([],[{'unit_id':1,**p},{'unit_id':1,**p}],[{'unit_id':2,**p}]):
            with self.assertRaises(m.ContractError):m.normalized_population_comparison(p,rows,[1])

    def test_positive_log_density_is_allowed(self):
        self.assertEqual(m.normalized_log_density(4,1),3)


class CohortTests(unittest.TestCase):
    def setUp(self):self.roster,self.projection,self.index,self.predictions,self.bindings=complete_fixture()

    def test_one_query_whitelist_and_deep_copy(self):
        key=next(iter(self.bindings));view=m.public_view(self.index,key)
        self.assertEqual(view['held_unit_id'],2**53+1)
        self.assertEqual([x['unit_id'] for x in view['spikes']],[2**53+2,2**53+3])
        self.assertNotIn('SECRET',json.dumps(view));self.assertNotIn('unknown_nested',json.dumps(view))
        view['spikes'][0]['spike_seconds_from_window_start'].append(.9)
        self.assertEqual(len(self.index['episodes'][key[:4]]['spikes'][1]['spike_seconds_from_window_start']),2)

    def test_all_population_condition_neuron_cases_scored(self):
        s=m.score_lono(self.index,self.predictions,self.bindings)
        self.assertEqual(s['n_cases'],360);self.assertEqual(len(s['population_conditions']),120)
        self.assertEqual(sum(x['fallback_cases'] for x in s['population_conditions']),120)
        self.assertTrue(all(x['n_neurons']==3 and x['n_trials']==1 for x in s['population_conditions']))
        self.assertFalse(s['candidate_provenance_verified'])

    def test_missing_silent_case_rejected(self):
        with self.assertRaises(m.ContractError):m.score_lono(self.index,self.predictions[1:],self.bindings)

    def test_duplicate_or_foreign_case_rejected(self):
        for rows in (self.predictions+[self.predictions[0]],copy.deepcopy(self.predictions)):
            if len(rows)==360:rows[0]['session_id']=999
            with self.assertRaises(m.ContractError):m.score_lono(self.index,rows,self.bindings)

    def test_candidate_cannot_change_quadrature_or_knots(self):
        for name in ('quadrature_seconds','knots_seconds'):
            rows=copy.deepcopy(self.predictions);rows[0]['curve'][name]=[0.,.5,1.]
            with self.assertRaises(m.ContractError):m.score_lono(self.index,rows,self.bindings)

    def test_missing_condition_or_population_rejected(self):
        for remove in (1,4):
            p=copy.deepcopy(self.projection);p['episodes']=p['episodes'][remove:]
            with self.assertRaises(m.ContractError):m.build_lono_index(p,self.roster)

    def test_missing_neuron_is_not_silence(self):
        p=copy.deepcopy(self.projection);p['episodes'][0]['spikes'].pop()
        with self.assertRaises(m.ContractError):m.build_lono_index(p,self.roster)

    def test_unresolved_clock_and_boolean_identity_rejected(self):
        p=copy.deepcopy(self.projection);p['source_clock']=None
        with self.assertRaises(m.ContractError):m.build_lono_index(p,self.roster)
        k=next(iter(self.bindings))
        with self.assertRaises(m.ContractError):m.public_view(self.index,k[:4]+(True,))

    def test_zero_density_not_dropped_from_group(self):
        self.predictions[1]['curve']=curve([[0.,0.,0.,0.]])
        s=m.score_lono(self.index,self.predictions,self.bindings)
        g=next(x for x in s['population_conditions'] if x['zero_event_density_cases'])
        self.assertEqual(g['n_neuron_trials'],3);self.assertEqual(g['sum_status'],'negative_infinity')
        self.assertIsNone(g['sum_log_density_nats'])

    def test_paired_reference_and_undefined_zero_density(self):
        refs=copy.deepcopy(self.predictions)
        result=m.compare_lono(self.index,self.predictions,refs,self.bindings)
        self.assertTrue(all(x['candidate_minus_reference_nats']==0 for x in result['cases']))
        self.predictions[1]['curve']=curve([[0.,0.,0.,0.]])
        refs[1]['curve']=curve([[0.,0.,0.,0.]])
        result=m.compare_lono(self.index,self.predictions,refs,self.bindings)
        self.assertEqual(result['cases'][1]['difference_status'],'undefined_both_negative_infinity')


class CliTests(unittest.TestCase):
    def test_strict_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.json'
            for body in ('{"a":1,"a":2}','{"a":NaN}','{"a":1e999}','{"a":1e-999}'):
                p.write_text(body)
                with self.assertRaises(m.ContractError):cli.read_json(p)

    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.json';p.write_text('{}');link=Path(tmp)/'link';link.symlink_to(p)
            with self.assertRaises(OSError):cli.read_json(link)

    def test_actual_cli_and_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.json';out=Path(tmp)/'out.json'
            p.write_text(json.dumps({'population':{'joint_log_density':-2,'reaction_time_log_density':-1},
                         'single_neurons':[{'unit_id':3,'joint_log_density':-3,'reaction_time_log_density':-1}],
                         'expected_units':[3]}))
            argv=[sys.executable,'-S','-B',str(Path(__file__).with_name('cli.py')),'normalize','--input',str(p),'--out',str(out)]
            a=subprocess.run(argv,capture_output=True,text=True,timeout=5)
            self.assertEqual(a.returncode,0,a.stderr);before=out.read_bytes()
            self.assertEqual(json.loads(before)['population_minus_independent_nats'],1)
            b=subprocess.run(argv,capture_output=True,text=True,timeout=5)
            self.assertNotEqual(b.returncode,0);self.assertEqual(out.read_bytes(),before)


if __name__=='__main__':unittest.main(verbosity=2)
