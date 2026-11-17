import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('decision_evaluator', PACKAGE / 'evaluator.py')
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def fixture():
    """Generated engineering controls, not empirical data or reproduction targets."""
    trials=[]
    for p in ['0_epo','1_epo']:
        for cond in ['accuracy','speed']:
            for c in [5,10,55,95]:
                for rep in range(2):
                    bump = (10 if p == '1_epo' else 0) + (20 if cond == 'accuracy' else 0) + c
                    trials.append({'participant':p,'epoch':f'{cond}-{c}-{rep}','condition':cond,'contrast_percent':c,
                        'side':'left','response':'left' if rep == 0 else 'right','rt_ms':750+bump,
                        'model_end_ms':760+bump,'event_times_ms':[50,150,250,650+bump,700+bump]})
    return {'schema':'decision-times-export-v1','purpose':'engineering_control','time_unit':'ms','contrast_unit':'percent',
        'time_origin':'stimulus_onset','point_time_method':'explicit_point_estimates','sample_rate_hz':512,
        'expected_participants':['0_epo','1_epo'],'trial_inventory':[{'participant':r['participant'],'epoch':r['epoch'],'disposition':'retained'} for r in trials], 'trials':trials}


def laws(payload,mode='descriptive',model='linear'):
    values={'linear':[.5,.1],'pieron':[.02,1],'fechner':[2,1,.1]}[model]
    rows=[]
    for p in payload['expected_participants']:
        for cond in ['accuracy','speed']:
            contrasts=sorted({r['contrast_percent'] for r in payload['trials'] if r['participant']==p and r['condition']==cond})
            for held in contrasts if mode == 'leave_one_contrast_out' else [None]:
                row={'participant':p,'condition':cond,'values':values}
                if held is not None:row.update(held_out_contrast_percent=held,fit_contrasts_percent=[c for c in contrasts if c!=held])
                rows.append(row)
    return {'target':'rt','selection':'all_responded','mode':mode,'model':model,'parameters':rows}


def likelihood(payload):
    models=[]
    for name,delta in [('baseline',0),('candidate',2)]:
        folds=[]
        for p in payload['expected_participants']:
            train=[q for q in payload['expected_participants'] if q!=p]
            folds.append({'test_participants':[p],'fit_participants':train,'preprocess_fit_participants':train,
                'scores':[{'participant':p,'epoch':r['epoch'],'log_likelihood':-10+delta} for r in payload['trials'] if r['participant']==p]})
        models.append({'name':name,'event_count':5,'event_width_ms':25,'folds':folds})
    return {'unit':'natural_log_per_trial','same_observation_space':True,'baseline_model':'baseline','models':models}


def erp(payload):
    channels=sum(e.ROIS.values(),[])
    rows=[]
    for r in payload['trials']:
        value=(2 if r['contrast_percent']<50 else 1)*1e-6
        rows.append({'participant':r['participant'],'epoch':r['epoch'],'volts':[[value]*3 for _ in channels]})
    return {'alignment':'stimulus','amplitude_unit':'V','times_ms':[0,500,1000],'channels':channels,'trials':rows}


class IndependentAnalyticControls(unittest.TestCase):
    def test_six_stages_offset_and_combined(self):
        p=fixture();r=p['trials'][0];r.update(event_times_ms=[50,150,250,650,700],rt_ms=750,model_end_ms=760)
        row=e.read_trials(p)[0]
        self.assertEqual([row['values'][x] for x in e.STAGES],[50,100,100,400,50,60])
        self.assertEqual(row['values']['encoding'],200)
        self.assertEqual(row['values']['decision'],450)
        self.assertEqual(row['values']['rt'],750)
        self.assertEqual(row['model_end_minus_rt_ms'],10)

    def test_primary_law_numeric_cases(self):
        self.assertAlmostEqual(e.law_prediction('linear',10,[.5,.1])[0],150)
        self.assertEqual(e.law_prediction('pieron',10,[.02,1])[0],200)
        latency,acc=e.law_prediction('fechner',5,[2,1,.1])
        self.assertAlmostEqual(latency,544.0191349399206)
        self.assertAlmostEqual(acc,81/82)
        self.assertEqual(e.law_prediction('fechner',5,[0,1,.1]),(1100,.5))

    def test_mode_not_expectation_and_first_tie(self):
        rows=[]
        for i in range(5):
            row=[0.]*12;row[i+1]=.5;row[i+6]=.5;rows.append(row)
        out=e.posterior_point_times(rows,1000)
        self.assertEqual(out['event_times_ms'],[1,2,3,4,5])
        self.assertEqual(out['model_end_ms'],11)

    def test_zero_mode_group_ambiguity_rejected(self):
        with self.assertRaisesRegex(ValueError,"group context"):
            e.posterior_point_times([[1.,0.]]*5,100)

    def test_irregular_erp_window_uses_time_weighting(self):
        p=fixture();s=erp(p);s["times_ms"]=[0,100,1000]
        for row,r in zip(s["trials"],p["trials"]):
            row["volts"]=[[0,0,2e-6] if r["contrast_percent"]<50 else [0,0,0] for _ in s["channels"]]
        out=e.erp_scores(e.read_trials(p),s)
        self.assertTrue(all(abs(v-.9)<1e-12 for row in out["summaries"] for v in row["participant_window_mean_difference_uV"].values()))

    def test_wrong_posterior_normalization_rejected(self):
        with self.assertRaises(ValueError):e.posterior_point_times([[.3,.3]]*5,100)

    def test_participant_slopes_and_error_denominators(self):
        out=e.evaluate(fixture())
        slopes=out['latency']['all_responded']['participant_slopes']
        self.assertTrue(all(r['ms_per_percent']['rt']==1 for r in slopes))
        self.assertEqual(out['latency']['all_responded']['n_trials'],32)
        self.assertEqual(out['latency']['correct_only']['n_trials'],16)
        self.assertTrue(all(r['accuracy_all_responded']==.5 for r in out['latency']['correct_only']['cells']))
        pairs=out['latency']['all_responded']['accuracy_minus_speed_ms']
        self.assertTrue(all(r['mean']==20 for r in pairs if r['target']=='rt'))

    def test_replication_does_not_change_participant_estimand(self):
        p=fixture();before=e.evaluate(p)['latency']['all_responded']['participant_equal_contrast_slopes']
        for r in list(p['trials']):
            if r['participant']=='0_epo':
                new=copy.deepcopy(r);new['epoch']+='-copy';p['trials'].append(new)
                p['trial_inventory'].append({'participant':new['participant'],'epoch':new['epoch'],'disposition':'retained'})
        after=e.evaluate(p)['latency']['all_responded']['participant_equal_contrast_slopes']
        self.assertEqual(before,after)

    def test_law_mse_units(self):
        p=fixture();s=laws(p);rows=e.read_trials(p);out=e.law_scores(rows,s)
        part=[r for r in rows if r['participant']=='0_epo' and r['condition']=='accuracy']
        expected=sum(((r['values']['rt']-e.law_prediction('linear',r['contrast_percent'],[.5,.1])[0])/1000)**2 for r in part)/len(part)
        self.assertAlmostEqual(out['participant_trial_mse_seconds_squared'][0]['mse_s2'],expected)

    def test_loco_is_not_participant_holdout_and_catches_leakage(self):
        p=fixture();s=laws(p,'leave_one_contrast_out');out=e.law_scores(e.read_trials(p),s)
        self.assertEqual(out['mode'],'leave_one_contrast_out')
        s['parameters'][0]['fit_contrasts_percent'].append(s['parameters'][0]['held_out_contrast_percent'])
        with self.assertRaisesRegex(ValueError,'leakage'):e.law_scores(e.read_trials(p),s)

    def test_source_asymmetric_loco_score_exposed(self):
        p=fixture()
        for r in list(p['trials']):
            if r['participant']=='0_epo':
                new=copy.deepcopy(r);new['epoch']+='-copy';p['trials'].append(new)
                p['trial_inventory'].append({'participant':new['participant'],'epoch':new['epoch'],'disposition':'retained'})
        result=e.law_scores(e.read_trials(p),laws(p,'leave_one_contrast_out'))
        for r in result['curve_scores']:
            self.assertNotEqual(r['participant_equal_curve_rmse_ms'],r['source_asymmetric_curve_rmse_ms'])

    def test_correct_latency_accuracy_keeps_errors(self):
        p=fixture();s=laws(p,model='fechner');s['selection']='correct_only'
        self.assertTrue(all(r['observed_accuracy']==.5 for r in e.law_scores(e.read_trials(p),s)['cells']))

    def test_erp_source_rois_bins_and_volts_conversion(self):
        p=fixture();out=e.erp_scores(e.read_trials(p),erp(p))
        self.assertEqual(len(out['summaries']),6)
        self.assertTrue(all(all(abs(v-1)<1e-12 for v in r['low_minus_high_uV']) for r in out['summaries']))
        self.assertEqual(out['summaries'][0]['participants'],['0_epo','1_epo'])

    def test_erp_out_of_bin_source_trials_are_accounted_not_dropped(self):
        p=fixture();p["trials"][0]["contrast_percent"]=3;p["trials"][-1]["contrast_percent"]=100
        p["erp"]=erp(p);out=e.evaluate(p)
        self.assertEqual(out["n_trials"],32)
        self.assertEqual(out["erp"]["n_input_trials"],32)
        self.assertEqual(out["erp"]["n_ERP_scored_trials"],30)
        self.assertEqual([r["contrast_percent"] for r in out["erp"]["out_of_source_bin_trials"]],[3,100])

    def test_ll_groups_and_pairing(self):
        p=fixture();out=e.heldout_likelihood(e.read_trials(p),likelihood(p))
        self.assertEqual(out['comparisons'][0]['participant_equal_delta']['mean'],2)
        self.assertEqual(out['comparisons'][0]['total_delta'],64)

    def test_leaking_preprocessing_rejected(self):
        p=fixture();s=likelihood(p);s['models'][1]['folds'][0]['preprocess_fit_participants']+=['0_epo']
        with self.assertRaisesRegex(ValueError,'leakage'):e.heldout_likelihood(e.read_trials(p),s)

    def test_missing_ll_trial_rejected(self):
        p=fixture();s=likelihood(p);s['models'][1]['folds'][0]['scores'].pop()
        with self.assertRaisesRegex(ValueError,'omits'):e.heldout_likelihood(e.read_trials(p),s)

    def test_missing_law_parameters_rejected(self):
        p=fixture();s=laws(p);s['parameters'].pop()
        with self.assertRaisesRegex(ValueError,'exactly cover'):e.law_scores(e.read_trials(p),s)

    def test_missing_erp_trial_rejected(self):
        p=fixture();s=erp(p);s['trials'].pop()
        with self.assertRaisesRegex(ValueError,'exactly all'):e.erp_scores(e.read_trials(p),s)

    def test_missing_duplicate_or_misordered_trial_rejected(self):
        p=fixture();p['trials'].pop()
        with self.assertRaisesRegex(ValueError,'missing retained'):e.read_trials(p)
        p=fixture();p['trials'].append(p['trials'][0])
        with self.assertRaisesRegex(ValueError,'duplicate'):e.read_trials(p)
        p=fixture();p['trials'][0]['event_times_ms'][1]=1
        with self.assertRaisesRegex(ValueError,'event order'):e.read_trials(p)

    def test_native_roster_cannot_shrink(self):
        p=fixture();p['purpose']='empirical_export'
        with self.assertRaisesRegex(ValueError,'all 26'):e.read_trials(p)

    def test_nonfinite_boolean_units_and_boundary_rejected(self):
        for value in [float('nan'),True]:
            p=fixture();p['trials'][0]['rt_ms']=value
            with self.assertRaises(ValueError):e.read_trials(p)
        p=fixture();p['time_unit']='seconds'
        with self.assertRaises(ValueError):e.read_trials(p)
        with self.assertRaises(ValueError):e.law_prediction('fechner',2.5,[1,1,0])
        with self.assertRaises(ValueError):e.law_prediction('pieron',5,[1,1,1])

    def test_constant_r2_null_and_alternative_sampling_explicit(self):
        self.assertIsNone(e.r_squared([1,1],[1,1]))
        p=fixture();p['sample_rate_hz']=100
        self.assertEqual(e.evaluate(p)['sampling_profile'],'explicit_alternative_not_native_recipe')

    def test_cli_all_modules_and_holds(self):
        p=fixture();p['law_evaluations']=[laws(p),laws(p,'leave_one_contrast_out','fechner')]
        p['erp']=erp(p);p['heldout_likelihood']=likelihood(p)
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'input.json';output=Path(directory)/'output.json';source.write_text(json.dumps(p))
            subprocess.run([sys.executable,str(PACKAGE/'evaluator.py'),str(source),'--output',str(output)],check=True)
            result=json.loads(output.read_text())
            self.assertEqual(result['qualification'],'unknown');self.assertIsNone(result['binary_reward'])
            self.assertEqual(result['scientific_runs'],0);self.assertEqual(len(result['input_sha256']),64)
            self.assertGreater(len(result['holds']),5)

if __name__=='__main__':unittest.main()
