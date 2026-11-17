"""Generated engineering controls, not empirical benchmark results."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

PATH = Path(__file__).resolve().parents[1] / "evaluator.py"
spec = importlib.util.spec_from_file_location("evaluator", PATH)
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def behavior(n=100):
    rng = np.random.default_rng(271)
    # Each trial has one sample of each sign per pair; equal consistency support.
    samples = rng.uniform(.5, 5, (n, 12)) * np.tile([1, -1], 6)
    estimate = .3*samples[:, 0] + .5*samples[:, 7] + rng.normal(size=n)
    return dict(trial_ids=np.array([f"trial-{i:03d}" for i in range(n)]), sess=np.full(n, 3),
                samples=samples, binary_choices=np.ones(n), interm_cues=np.ones(n),
                estimations=estimate, gen_means=np.zeros(n),
                consistent_samples=np.where(samples > 0, samples, np.nan),
                inconsistent_samples=np.where(samples < 0, samples, np.nan))


def packet(directory, n=100):
    b = behavior(n)
    rng = np.random.default_rng(45)
    components = rng.normal(size=(n, 2, 801))
    np.savez(directory / "behavior.npz", **b)
    np.savez(directory / "neural.npz", trial_ids=b["trial_ids"], components=components)
    def ref(name):
        return {"path":name, "sha256":hashlib.sha256((directory/name).read_bytes()).hexdigest()}
    p = {"schema_version":1, "task_id":ev.TASK, "packet_kind":"generated_engineering_controls",
         "component_provenance":"generated_reference_shape_160Hz", "expected_participants":["generated-subject"],
         "expected_parcels":["generated-parcel"], "contexts":["choice"], "region_groups":{"generated-region":["generated-parcel"]},
         "participants":[{"id":"generated-subject", "behavior":ref("behavior.npz"),
                           "neural":[{"context":"choice", "parcel":"generated-parcel", "array":ref("neural.npz")}]}]}
    path=directory/"packet.json"
    path.write_text(json.dumps(p))
    return path,p


class NumericalControls(unittest.TestCase):
    def test_perfect_independent_linear_reference_and_units(self):
        x = np.arange(100, dtype=float)
        folds = np.arange(100) % 10
        r = np.stack([x, -2*x],axis=1)[:, :, None] * 1e-12
        scores, pred = ev.cross_validated_linear(r, 3*x+2, 7*x-5, folds)
        np.testing.assert_allclose(scores, 1, atol=1e-12)
        np.testing.assert_allclose(pred[:, 0, :, 0], np.repeat((3*x+2)[:, None],2,axis=1), atol=1e-10)
        np.testing.assert_allclose(pred[:, 1, :, 0], np.repeat((7*x-5)[:, None],2,axis=1), atol=1e-10)

    def test_fit_ignores_heldout_targets(self):
        rng=np.random.default_rng(14)
        x=rng.normal(size=(60,2,3));s=rng.normal(size=60);e=rng.normal(size=60);fold=np.arange(60)%3
        _,p1=ev.cross_validated_linear(x,s,e,fold)
        s[fold==0]+=100;e[fold==0]-=80
        _,p2=ev.cross_validated_linear(x,s,e,fold)
        np.testing.assert_allclose(p1[fold==0],p2[fold==0])

    def test_mean_fold_correlation_is_not_pooled_correlation(self):
        x=np.arange(60,dtype=float)
        folds=np.repeat(np.arange(3),20)
        s=x+np.repeat([0,100,-40],20)
        scores,pred=ev.cross_validated_linear(x[:,None,None],s,s,folds)
        direct=[]
        for f in range(3):
            tr=folds!=f;te=~tr
            beta=np.linalg.lstsq(np.c_[np.ones(tr.sum()),x[tr]],s[tr],rcond=None)[0]
            yp=np.c_[np.ones(te.sum()),x[te]]@beta
            direct.append(np.corrcoef(s[te],yp)[0,1])
        np.testing.assert_allclose(scores[:,0,0,0],direct,atol=1e-12)
        self.assertGreater(abs(np.mean(direct)-np.corrcoef(s,pred[:,0,0,0])[0,1]),.1)

    def test_encoding_and_readout_are_distinct(self):
        stimulus=np.tile([-1.,-1.,1.,1.],15)
        estimate=np.tile([-1.,1.,-1.,1.],15)
        scores,_=ev.cross_validated_linear(stimulus[:,None,None],stimulus,estimate,np.repeat(np.arange(3),20))
        np.testing.assert_allclose(scores[:,0],1,atol=1e-12)
        np.testing.assert_allclose(scores[:,2],0,atol=1e-12)

    def test_zero_evidence_neither_consistency_class(self):
        b=behavior()
        b['samples'][0,0]=0;b['consistent_samples'][0,0]=0
        _,mask,_=ev.source_rows(ev.validate_behavior(b),'choice')
        self.assertFalse(mask[0,0,0]);self.assertFalse(mask[0,0,1]);self.assertTrue(mask[0,0,2])

    def test_constant_component_undefined_not_zero(self):
        x=np.ones((30,1,2));v=np.arange(30,dtype=float)
        scores,_=ev.cross_validated_linear(x,v,v,np.arange(30)%3)
        self.assertTrue(np.isnan(scores).all())

    def test_constant_prediction_roundoff_cannot_fabricate_correlation(self):
        rng=np.random.default_rng(20261117)
        r=np.ones((97,3,5));s=rng.normal(size=97);e=rng.normal(size=97)
        scores,pred=ev.cross_validated_linear(r,s,e,np.arange(97)%7)
        self.assertTrue(np.isnan(scores).all())
        for fold in range(7):self.assertTrue((np.ptp(pred[np.arange(97)%7==fold],axis=0)==0).all())

    def test_constant_training_features_ignore_centering_residue(self):
        fold=np.arange(30)%3;r=np.full((30,1,1),1.1)
        r[fold==0,0,0]=np.linspace(0,2,10)
        y=np.random.default_rng(8).normal(size=30)
        scores,pred=ev.cross_validated_linear(r,y,y,fold)
        self.assertTrue(np.isnan(scores[0]).all())
        self.assertTrue((np.ptp(pred[fold==0],axis=0)==0).all())

    def test_constant_training_targets_cannot_create_roundoff_slope(self):
        rng=np.random.default_rng(8);fold=np.arange(30)%3
        r=rng.normal(size=(30,1,1));y=np.full(30,1.1);y[fold==0]=rng.normal(size=10)
        scores,pred=ev.cross_validated_linear(r,y,y,fold)
        self.assertTrue(np.isnan(scores[0]).all())
        self.assertTrue((np.ptp(pred[fold==0],axis=0)==0).all())

    def test_behavioral_slope_constant_roundoff(self):
        y=np.random.default_rng(8).normal(size=97)
        self.assertTrue(np.isnan(ev._slope(np.full(97,1.1),y)))
        self.assertEqual(ev._slope(y,np.full(97,1.1)),0)

    def test_grouped_trial_folds_keep_all_samples_together(self):
        groups=np.tile(np.array([f"t{i}" for i in range(40)]),2)
        folds=ev.fold_assignments(groups,np.random.default_rng(5),"grouped_trials")
        self.assertEqual(set(folds),set(range(10)))
        for group in np.unique(groups):self.assertEqual(len(set(folds[groups==group])),1)
        source=ev.fold_assignments(groups,np.random.default_rng(5),"source_rows")
        self.assertTrue(any(len(set(source[groups==group]))>1 for group in np.unique(groups)))

    def test_epoch_indices_and_actual_source_baseline(self):
        x=np.broadcast_to(np.arange(801),(2,1,801)).copy().astype(float)
        actual=ev.epoch_components(x)
        self.assertEqual(actual.shape,(2,12,1,129))
        # First onset index88, baseline inclusive0:88 gives44, epoch begins72.
        self.assertEqual(actual[0,0,0,0],28)
        self.assertEqual(actual[0,0,0,16],44)
        self.assertEqual(actual[0,-1,0,-1],700)

    def test_source_eligibility_and_integer_mean_selection(self):
        b=behavior(100);b['binary_choices'][0]=99;b['estimations'][1]=np.nan
        b['gen_means'][2]=.5;b['gen_means'][3]=5
        b=ev.validate_behavior(b)
        _,_,alltrials=ev.source_rows(b,'choice',0)
        _,_,nearzero=ev.source_rows(b,'choice',4)
        self.assertEqual(alltrials.sum(),98);self.assertEqual(nearzero.sum(),96)

    def test_duplicate_or_misaligned_identity_rejected(self):
        b=behavior();b['trial_ids'][1]=b['trial_ids'][0]
        with self.assertRaisesRegex(ValueError,'duplicate'):ev.validate_behavior(b)
        b=behavior()
        with self.assertRaisesRegex(ValueError,'identity/order'):
            ev.evaluate_participant(b,np.ones((100,1,801)),b['trial_ids'][::-1],'choice','s','p')

    def test_invalid_source_mask_and_nonfinite_neural_rejected(self):
        b=behavior();b['inconsistent_samples'][0,6]=b['samples'][0,6]
        with self.assertRaisesRegex(ValueError,'overlap'):ev.validate_behavior(b)
        x=np.zeros((4,1,801));x[0,0,0]=np.nan
        with self.assertRaisesRegex(ValueError,'finite'):ev.epoch_components(x)

    def test_underpowered_pairs_retained(self):
        b=behavior(40)
        out=ev.evaluate_participant(b,np.ones((40,1,801)),b['trial_ids'],'choice','s','p')
        self.assertEqual(len(out['pairs']),6)
        self.assertTrue(all(x['status']=='insufficient_support' for x in out['pairs']))
        self.assertTrue(all(x['status']=='incomplete' for x in out['interval_summaries']))

    def test_complete_packet_controls_and_determinism(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,p=packet(Path(tmp))
            a=ev.evaluate_packet(path,seed=11,fold_mode='grouped_trials')
            b=ev.evaluate_packet(path,seed=11,fold_mode='grouped_trials')
            self.assertEqual(a,b)
            self.assertEqual(a['scientific_qualification'],'unknown')
            self.assertFalse(a['full_contract_complete'])
            result=a['participant_results'][0]
            self.assertTrue(all(q['status']=='computed' for q in result['pairs']))
            for q in result['pairs']:
                for c in q['classes'].values():self.assertEqual(c['trials_split_across_folds_by_repetition'],[0]*5)
            self.assertIsNone(a['prospective_participant_associations'][0]['behavior_vs_linear_readout_pearson'])
            json.dumps(ev.json_safe(a),allow_nan=False)

    def test_abs_after_signed_time_and_component_averaging(self):
        # Opposite signed readout relations cancel before unsigned summary.
        value=np.array([[[[.9,.9],[-.9,-.9]]]]) # repetition,fold,PC,time
        self.assertEqual(abs(value.mean()),0)
        self.assertAlmostEqual(np.abs(value).mean(),.9)
        # Assert source summary implementation using a controlled CV oracle.
        original=ev.cross_validated_linear
        def oracle(r,s,e,folds):
            arr=np.ones((10,3,2,129));arr[:,:,1,:]=-1
            return arr,None
        ev.cross_validated_linear=oracle
        try:
            b=behavior()
            out=ev.evaluate_participant(b,np.zeros((100,2,801)),b['trial_ids'],'choice','s','p')
            self.assertEqual(out['pairs'][0]['classes']['consistent']['readout_absolute_window_mean'],0)
        finally:ev.cross_validated_linear=original

    def test_regional_abs_follows_signed_parcel_mean(self):
        def result(parcel,value):
            classes={k:{"signed_window_mean":[.3,.4,value],"behavioral_absolute_slope":.2} for k in ev.CLASS_NAMES}
            classes["inconsistent"]["signed_window_mean"]=[.3,.4,.2]
            return {"participant":"s","context":"choice","parcel":parcel,"pairs":[{"status":"computed","classes":classes} for _ in range(6)]}
        out=ev.aggregate_region([result("p1",.8),result("p2",-.8)],"s","choice","region",["p1","p2"])
        self.assertAlmostEqual(out["pairs"][0]["neural_consistency_contrast"][2],-.2)

    def test_roster_and_hash_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,p=packet(Path(tmp),40)
            p['expected_participants'].append('missing')
            path.write_text(json.dumps(p))
            with self.assertRaisesRegex(ValueError,'roster'):ev.evaluate_packet(path)
            p['expected_participants'].pop()
            p['participants'][0]['behavior']['sha256']='0'*64
            path.write_text(json.dumps(p))
            with self.assertRaisesRegex(ValueError,'hash mismatch'):ev.evaluate_packet(path)

    def test_json_undefined_is_null_and_invalid_seed(self):
        self.assertEqual(ev.json_safe({'x':[float('nan'),float('inf')]}),{'x':[None,None]})
        b=behavior()
        with self.assertRaisesRegex(ValueError,'seed'):
            ev.evaluate_participant(b,np.zeros((100,1,801)),b['trial_ids'],'choice','s','p',seed=-1)


if __name__=='__main__':unittest.main()
