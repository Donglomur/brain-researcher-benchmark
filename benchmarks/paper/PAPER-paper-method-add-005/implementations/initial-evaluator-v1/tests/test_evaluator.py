"""Generated engineering controls; independent source derivation noted in docs."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ajile_evaluator',ROOT/'evaluator.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)

class Mathematics(unittest.TestCase):
    def test_independent_train_moments_fences_and_boundary(self):
        x=np.array([[[0,2]],[[0,4]],[[0,6]],[[0,8]]],float)
        stats,valid=e.fit_preprocessing(x)
        np.testing.assert_allclose(stats['mean'],[2.5]);np.testing.assert_allclose(stats['scale']**2,[8.75])
        np.testing.assert_allclose(stats['lower'],[-11.5]);np.testing.assert_allclose(stats['upper'],[21.5])
        np.testing.assert_array_equal(e.quality_mask(np.array([[[0,21.5]],[[0,21.5001]],[[1,1]]]),stats),[[1],[0],[0]])
        x[-1]=0;stats,valid=e.fit_preprocessing(x)
        np.testing.assert_allclose(stats['mean'],[2]);np.testing.assert_allclose(stats['scale']**2,[16/3])
        self.assertEqual(valid[:,0].tolist(),[True,True,True,False])

    def test_pinned_rounding_rng_and_schedule(self):
        self.assertEqual(np.flatnonzero(e.observed_channels(5,.5,0)).tolist(),[3,4])
        self.assertEqual([e.observed_channels(64,d,0).sum() for d in e.DROPOUTS],[32,19,6])
        self.assertEqual(set(np.flatnonzero(e.observed_channels(64,.9,0))),{16,38,31,19,2,50})
        with self.assertRaises(ValueError):e.observed_channels(2,.9,0)

    def test_target_isolation_and_train_only_ridge_closed_form(self):
        train=np.array([[[-1,1,-1,1],[-2,2,-2,2]]],float)
        obs=np.array([1,0],bool);valid=np.ones((1,2),bool)
        test=np.array([[[3,3,3,3],[99,-99,99,-99]]],float)
        cond=e.condition(test,obs,valid)
        test[:,1,:]=1e6
        other_valid=valid.copy();other_valid[:,1]=False
        np.testing.assert_array_equal(cond,e.condition(test,obs,other_valid))
        pred=e.conditional_ridge(train,valid,cond,obs,alpha=.5)
        np.testing.assert_allclose(pred[:,1,:],4)
        np.testing.assert_array_equal(pred[:,0,:],3)

    def test_independent_phase_amplitude_units_and_observed_immunity(self):
        ref=np.array([[[0,1,0,-1],[1,-1,1,-1]]],float);obs=np.array([1,0],bool)
        pred=ref.copy();pred[:,1,:]*=-1
        result=e.score_case(ref,pred,obs,np.ones((1,2),bool),np.array([1,2]),4)
        self.assertEqual(result['mse_standardized_all'],4)
        self.assertEqual(result['mse_source_units_squared_eligible'],16)
        self.assertEqual(result['psd_db_mae_eligible'],0)
        self.assertAlmostEqual(result['pearson_eligible'],-1)
        pred[:,0,:]=500
        self.assertEqual(result,e.score_case(ref,pred,obs,np.ones((1,2),bool),np.array([1,2]),4))
        pred[:,1,:]=2*ref[:,1,:]
        amp=e.score_case(ref,pred,obs,np.ones((1,2),bool),np.array([1,2]),4)
        self.assertAlmostEqual(amp['psd_db_mae_eligible'],10*np.log10(4)/2)
        pred[:,1,:]=0
        mean=e.score_case(ref,pred,obs,np.ones((1,2),bool),np.array([1,2]),4)
        self.assertEqual(mean['mse_standardized_all'],1);self.assertEqual(mean['mse_source_units_squared_eligible'],4)
        self.assertEqual(mean['pearson_eligible'],0);self.assertEqual(mean['constant_prediction_event_channels'],1)

    def test_periodogram_parseval_even_odd(self):
        for length in [4,5,1001]:
            x=np.arange(length,dtype=float)**2
            psd=e.periodogram(x,250)
            self.assertAlmostEqual(float(psd.sum()*250/length),float(np.var(x)),delta=max(1e-8,np.var(x)*1e-12))

    def test_quality_counts_no_silent_exclusion(self):
        ref=np.tile(np.array([1,-1,1,-1]),(2,2,1));pred=np.zeros_like(ref)
        result=e.score_case(ref,pred,np.array([1,0]),np.array([[1,1],[1,0]],bool),np.ones(2),4)
        self.assertEqual(result['target_event_channels'],2);self.assertEqual(result['eligible_target_event_channels'],1)
        self.assertEqual(result['excluded_target_event_channels'],1)
        with self.assertRaises(ValueError):e.score_case(ref,pred,np.array([1,0]),np.zeros((2,2),bool),np.ones(2),4)
        pred=pred.astype(float);pred[0,1,0]=np.nan
        with self.assertRaises(ValueError):e.score_case(ref,pred,np.array([1,0]),np.ones((2,2),bool),np.ones(2),4)

    def test_input_shape_duplicate_and_day_validation(self):
        x=np.ones((2,2,4));t=np.arange(4)
        with self.assertRaises(ValueError):e.source_arrays(x,[1,2],t,['same','same'])
        with self.assertRaises(ValueError):e.source_arrays(x,[1,1],t,['a','b'])
        with self.assertRaises(ValueError):e.source_arrays(x,[1,2],[0,1,3,4],['a','b'])


class FullPanel(unittest.TestCase):
    def test_prepare_baselines_score_complete_panel_and_rejections(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);t=np.linspace(-2,2,1001);records=[]
            for i,pid in enumerate(e.PARTICIPANTS):
                # Deliberately different event counts and unsorted days; no test truth fitting.
                n=4+i%2
                signal=np.array([[np.sin((c+1)*np.pi*t)+.1*j+.01*c for c in range(10)] for j in range(n)])
                days=np.array([7,1,2]+[3]*(n-3))
                path=root/(pid+'.npz')
                np.savez_compressed(path,signal=signal,days=days,times=t,row_ids=np.array([f'{pid}-{j}' for j in range(n)]),source_filename=np.array(pid+'_ecog_data.nc'),source_sha256=np.array('0'*64))
                records.append({'id':pid,'path':path.name,'sha256':e.digest_file(path)})
            manifest=root/'input.json';e.write_json(manifest,{'schema':e.SCHEMA,'kind':'generated_control','participants':records})
            e.prepare(manifest,root/'public',root/'private')
            public=root/'public/manifest.json';private=root/'private/manifest.json';m=json.loads(public.read_text())
            self.assertEqual(len(m['cases']),180);self.assertEqual(len(m['participants']),12)
            self.assertEqual(m['participants'][0]['test_day'],7);self.assertEqual(m['participants'][0]['test_events'],1)
            packet=e.load_npz(root/'public'/m['cases'][0]['input_file'])
            self.assertEqual(set(packet),{'condition','row_ids'})
            obs=m['cases'][0]['observed_channels'];hidden=m['cases'][0]['target_channels']
            self.assertTrue(np.all(packet['condition'][:,hidden,:]==0));self.assertTrue(np.all(packet['condition'][:,10+np.array(hidden),:]==0))
            # The operator collection leaks all channels if incorrectly distributed.
            union=set().union(*(set(c['observed_channels']) for c in m['cases'] if c['participant']=='EC01'))
            self.assertEqual(union,set(range(10)))
            case=m['cases'][0]
            e.export_case(public,case['id'],root/'single-case')
            exported=json.loads((root/'single-case/case.json').read_text())
            self.assertEqual(exported['distribution'],'single_case_candidate_packet')
            self.assertNotIn('cases',exported)
            self.assertEqual({p.name for p in (root/'single-case').iterdir()},{'case.json','EC01-train.npz',case['input_file']})
            np.testing.assert_array_equal(e.load_npz(root/'single-case'/case['input_file'])['condition'],packet['condition'])
            with self.assertRaises(ValueError):e.export_case(public,case['id'],root/'public/nested-export')
            for method in ('mean','ridge'):
                e.run_baseline(public,root/method,method)
                score=e.evaluate(public,private,root/method/'predictions.json')
                self.assertEqual(score['case_count'],180);self.assertEqual(score['scientific_qualification'],'unknown')
                for metric in e.METRICS:
                    self.assertAlmostEqual(score['overall'][metric],np.mean([p[metric] for p in score['participants']]))
            e.collect_predictions(public,root/'mean/predictions.json',root/'collected')
            collected_score=e.evaluate(public,private,root/'collected/predictions.json')
            self.assertEqual(collected_score['case_count'],180)
            submitted=json.loads((root/'mean/predictions.json').read_text())
            submitted['predictions'].pop();e.write_json(root/'mean/incomplete.json',submitted)
            with self.assertRaises(ValueError):e.evaluate(public,private,root/'mean/incomplete.json')
            # Wrong row identity fails even when updated file SHA is honestly declared.
            submitted=json.loads((root/'mean/predictions.json').read_text());r=submitted['predictions'][0];pp=root/'mean'/r['path'];data=e.load_npz(pp)
            data['row_ids']=np.array(['wrong']);np.savez_compressed(pp,**data);r['sha256']=e.digest_file(pp)
            e.write_json(root/'mean/wrong-rows.json',submitted)
            with self.assertRaises(ValueError):e.evaluate(public,private,root/'mean/wrong-rows.json')
            # Incomplete participants fail before any output creation.
            e.write_json(root/'short.json',{'schema':e.SCHEMA,'kind':'generated_control','participants':records[:-1]})
            with self.assertRaises(ValueError):e.prepare(root/'short.json',root/'short-public',root/'short-private')
            self.assertFalse((root/'short-public').exists())
            # Honest authentic claim rejects deliberately small control channel counts.
            e.write_json(root/'authentic.json',{'schema':e.SCHEMA,'kind':'authentic_input','participants':records})
            with self.assertRaises(ValueError):e.prepare(root/'authentic.json',root/'native-public',root/'native-private')

if __name__=='__main__':unittest.main()
