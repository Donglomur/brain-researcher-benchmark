"""Generated engineering controls only; no empirical reproduction claims."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from scipy.special import logit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluator as e


def generated_arrays(seed=1):
    rng = np.random.default_rng(seed)
    nloc, ntask, sensors = 42, 24, 4
    labels = np.tile(np.arange(1, 8), 6)
    localizer = rng.normal(0, .2, (nloc, sensors, 2))
    for c in range(1, 4):
        localizer[labels == c, c-1, 1] += 2
    task = rng.normal(0, .4, (ntask, sensors, 1))
    return dict(localizer=localizer, task=task, localizer_ms=np.array([-200., 0.]),
                task_ms=np.array([0.]), image_class=labels, block=np.ones(nloc),
                choice_number=np.tile([1., 2., 3., 4.], 6),
                o1_val=np.tile([1., 5., 3., 7., 4., 2.], 4),
                o2_val=np.tile([8., 2., 4., 3., 9., 7.], 4), safe_val=np.full(ntask, 4.), rt_ms=np.full(ntask, 700.))


def write_packet(base):
    participants = []
    for i, identity in enumerate(e.COHORT):
        a = generated_arrays(i)
        path = base/f'{identity}.npz'
        np.savez(path, **a)
        participants.append(dict(participant_id=identity, arrays=path.name, arrays_sha256=e.digest(path),
            localizer_trial_ids=[f'L{k}' for k in range(len(a['localizer']))],
            task_trial_ids=[f'T{k}' for k in range(len(a['task']))], sensor_names=[f'M{k}' for k in range(4)],
            behavior_parameters=[i/20., float(np.sin(i))], behavior_parameter_fit_scope=dict(participants=[identity],cross_participant_prior=False,native_model_parity='unverified'), behavior_parameter_provenance='generated engineering labels, not source estimates',
            provenance=dict(release='ds005065/1.0.0', native_paths={
                'localizer':f'derivatives/Epoched_Preprocessed_Data/Epoched_Localizer_Data/{identity}_Epoched_Localizer_Data.mat',
                'task':f'derivatives/Epoched_Preprocessed_Data/Epoched_Task_Choice_Data/{identity}_Epoched_Task_Choice_Data.mat',
                'events':f'derivatives/Event_Info_Tables/{identity}_table.mat'})))
    m=dict(schema_version=1, task_id=e.TASK, contract_sha256=e.CONTRACT_SHA256, source_revision=e.SOURCE_REVISION,
           input_kind='generated_engineering_control', event_table_conversion_status='unqualified',
           train_ms=[0], test_ms=[0], ridge_alphas=[.1, 1.], participants=participants)
    path=base/'manifest.json';path.write_text(json.dumps(m));return path,m


class SourceEquations(unittest.TestCase):
    def test_first_level_known_joint_coefficients(self):
        choice=np.tile([1,2,3,4], 4)
        o1=np.zeros(16);o2=np.tile([1,4,2,3],4)+np.repeat([0,1,3,5],4)
        diff=.12*((5-choice)/5-.5)+.007*o2
        rp=np.stack([np.full(16,.3), .3+diff, np.full(16,.2)],axis=-1)[:,None,None,:]
        result=e.first_level(logit(rp),choice,o1,o2,np.full(16,300),[0])
        np.testing.assert_allclose(result['effects'][:,0,0],[.12,.007],atol=1e-12)
        self.assertAlmostEqual(result['safe'][0,0],.2)

    def test_rt_censor_inclusive_and_rank_failure(self):
        choice=np.tile([1,2,3,4], 4);o1=np.zeros(16);o2=np.arange(16)%7
        logits=np.zeros((16,1,2,3));rt=np.full(16,10.);rt[0]=9.
        r=e.first_level(logits,choice,o1,o2,rt,[0,10])
        np.testing.assert_array_equal(r['eligible_trials'],[16,15])
        with self.assertRaisesRegex(ValueError,'unidentified'):
            e.first_level(logits,choice,o1,o2,np.zeros(16),[0,10])

    def test_probability_orientation(self):
        choice=np.array([1,2,3,4]);p2=(5-choice)/5
        np.testing.assert_allclose(p2,[.8,.6,.4,.2])


class DecoderControls(unittest.TestCase):
    def test_intercept_only_closed_form(self):
        x=np.zeros((10,2));y=np.r_[np.ones(2),np.zeros(8)]
        b,a=e.fit_l1_binomial(x,y)
        np.testing.assert_allclose(b,0,atol=1e-12)
        self.assertAlmostEqual(a,np.log(.2/.8),places=6)

    def test_prediction_is_independent_of_other_task_rows(self):
        a=generated_arrays()
        args=[a['localizer'],a['task'],a['localizer_ms'],a['task_ms'],a['image_class'],a['block'],[0],[0]]
        initial=e.decode(*args)
        changed=a['task'].copy();changed[1:]*=1000;args[1]=changed
        after=e.decode(*args)
        np.testing.assert_allclose(after[0],initial[0],atol=1e-12)

    def test_missing_class_or_exact_time_rejected(self):
        a=generated_arrays();a['image_class'][a['image_class']==7]=6
        with self.assertRaisesRegex(ValueError,'seven'):
            e.decode(a['localizer'],a['task'],a['localizer_ms'],a['task_ms'],a['image_class'],a['block'],[0],[0])
        with self.assertRaisesRegex(ValueError,'absent'):
            e.indices(np.array([-200.,0.]),np.array([10.]),'axis')


class NestedControls(unittest.TestCase):
    def test_heldout_label_cannot_change_own_prediction_or_selection(self):
        rng=np.random.default_rng(32);n=8
        effects=rng.normal(size=(n,2,2,1));safe=rng.normal(size=(n,2,1));nuisance=rng.normal(size=(n,2))
        y=np.column_stack([effects[:,0,0,0]+.1*rng.normal(size=n),effects[:,1,1,0]])
        args=[[f'P{k}' for k in range(n)],effects,safe,nuisance,y,np.array([.1,1.])]
        initial=e.nested_prediction(*args)
        changed=y.copy();changed[0]+=1000;args[4]=changed
        after=e.nested_prediction(*args)
        np.testing.assert_allclose(initial['predictions'][0],after['predictions'][0],atol=0)
        self.assertEqual(initial['folds'][:4],after['folds'][:4])
        for fold in initial['folds']:
            self.assertNotIn(fold['participant'],fold['training_participants'])
            self.assertEqual(len(fold['training_participants']),n-1)

    def test_ridge_manual_one_feature_reference(self):
        x=np.array([[1.],[2.],[3.]]);y=np.array([2.,4.,6.]);q=np.array([[4.]])
        z=(x[:,0]-2)/np.sqrt(2/3);beta=np.dot(z,y-4)/(np.dot(z,z)+1)
        expected=4+(4-2)/np.sqrt(2/3)*beta
        self.assertAlmostEqual(e.ridge_predict(x,y,q,1)[0],expected)


class PacketControls(unittest.TestCase):
    def test_full_generated_path_and_preserved_holds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,m=write_packet(Path(tmp));result=e.evaluate(path)
            self.assertEqual(len(result['participant_first_level']),21)
            self.assertEqual(len(result['prospective_nested_prediction']['participant_ids']),19)
            self.assertEqual(result['second_level_excluded_source_participants'],['sub-S006','sub-S019'])
            self.assertFalse(result['scientific_qualification']);self.assertFalse(result['whole_paper_reproduction'])
            json.dumps(result,allow_nan=False)

    def test_missing_participant_hash_and_path_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,m=write_packet(Path(tmp));original=json.loads(json.dumps(m))
            m['participants'].pop();path.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'complete source cohort'):e.load_packet(path)
            m=original;m['participants'][0]['arrays_sha256']='0'*64;path.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'SHA256'):e.load_packet(path)
            m['participants'][0]['arrays']='../outside.npz';path.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'escapes'):e.load_packet(path)

    def test_joint_population_behavior_fits_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,m=write_packet(Path(tmp))
            m['participants'][0]['behavior_parameter_fit_scope']['cross_participant_prior']=True
            path.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'participant-independent'):e.load_packet(path)

    def test_object_npz_and_false_qualification_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,m=write_packet(Path(tmp));p=Path(tmp)/m['participants'][0]['arrays']
            a=generated_arrays();a['localizer']=np.array([object()],dtype=object);np.savez(p,**a)
            m['participants'][0]['arrays_sha256']=e.digest(p);path.write_text(json.dumps(m))
            with self.assertRaises(ValueError):e.load_packet(path)
            m['event_table_conversion_status']='qualified';path.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'cannot certify'):e.load_packet(path)


if __name__=='__main__':unittest.main()
