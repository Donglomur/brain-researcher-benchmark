"""Invented fixtures only. No recording, media, model, fit or scientific score."""
import copy
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
if not (ROOT/'public').is_dir():ROOT=ROOT.parent
sys.path[:0]=[str(ROOT/'private'),str(ROOT/'public')]
import arrays
import score
import prepare_pool
from protocol import SUBJECTS,SESSIONS,ARMS
from join_metadata import join
from signals_core import eeg_bins,eye_bins,training_stats,standardize_fit
from stimulus_core import appearance,video_features,acoustic,spatial_cells
from stage import design
from scorer_core import evaluate,mse


def fixture_meta():
    times=[-.1+i/500 for i in range(1800)]
    meta={'stimulus_id':{},'run_number':{},'trial_number':{},'times':times}
    # 1102videos across8sessions, with exactlegal1..16run/1..66trial sourcekeys.
    for s,session in enumerate(SESSIONS):
        ids=list(range(1+s,1103,8));meta['stimulus_id'][session]=ids
        meta['run_number'][session]=[1+i//66 for i in range(len(ids))]
        meta['trial_number'][session]=[1+i%66 for i in range(len(ids))]
    eeg=copy.deepcopy(meta);eeg['ch_names']=['C'+str(i) for i in range(127)]
    return eeg,meta


def predictions():
    gold={p:np.zeros((3,2,4)) for p in SUBJECTS}
    pred={p:{arm:np.full((3,2,4),value) for arm,value in zip(ARMS,(4.,3.,2.,1.,2.))} for p in SUBJECTS}
    return pred,gold


class Tests(unittest.TestCase):
    def test_exact_key_join_uses_indices_not_equal_order(self):
        eeg,eye=fixture_meta()
        for s in SESSIONS:
            for k in ('stimulus_id','run_number','trial_number'):eye[k][s]=eye[k][s][::-1]
        r=join('sub-01',eeg,eye)
        self.assertEqual(r['support']['joined_trials'],1102);self.assertEqual(r['support']['missing_videos'],[])
        first=r['sessions']['ses-01']['joined'][0]
        self.assertNotEqual(first['eeg_row'],first['eye_row'])

    def test_join_refuses_stimulus_mismatch_missing_video_and_bad_clock(self):
        eeg,eye=fixture_meta();eye['stimulus_id']['ses-01'][0]=1102
        with self.assertRaises(ValueError):join('sub-01',eeg,eye)
        eeg,eye=fixture_meta()
        for k in ('stimulus_id','run_number','trial_number'):eye[k]['ses-01'].pop(0)
        with self.assertRaises(ValueError):join('sub-01',eeg,eye)
        eeg,eye=fixture_meta();eye['times'][100]+=.001
        with self.assertRaises(ValueError):join('sub-01',eeg,eye)

    def test_native_eeg_bin_and_fit_only_scale(self):
        x=np.broadcast_to(np.arange(1800,dtype=float),(2,127,1800)).copy()
        b=eeg_bins(x);self.assertEqual(b.shape,(2,127,150));self.assertEqual(b[0,0,0],54.5);self.assertEqual(b[0,0,-1],1544.5)
        a=np.stack((np.zeros((127,150)),np.full((127,150),2.)))
        anchor,mu,sd,n=training_stats([a]);self.assertEqual(n,2)
        self.assertTrue(np.all(((a-anchor)-mu)[0]/sd==-1));self.assertTrue(np.all(((a-anchor)-mu)[1]/sd==1))

    def test_exact_nonbinary_constant_target_is_undefined(self):
        x=np.full((7,127,150),.1)
        with self.assertRaises(ValueError):training_stats([x[:3],x[3:]])

    def test_eye_missingness_and_derivatives_preserved(self):
        x=np.broadcast_to(np.arange(1800,dtype=float)/500,(1,3,1800)).copy();x[:,:,50:60]=np.nan
        e=eye_bins(x);self.assertEqual(e.shape,(1,150,8));self.assertTrue(np.array_equal(e[0,0],np.zeros(8)))
        self.assertTrue(np.allclose(e[0,1,3:6],1.));self.assertTrue(np.all(e[0,1,6:]==1.))
        x[0,0,100]=np.nan
        with self.assertRaises(ValueError):eye_bins(x)

    def test_feature_constant_and_nearconstant_fit_handling(self):
        a=np.nextafter(.1,1.);x=np.asarray([[.1,.1],[.1,a],[100.,.2]])
        z,stats=standardize_fit(x,[0,1])
        self.assertTrue(np.all(z[:,0]==0));self.assertTrue(np.allclose(z[:2,1],[-1,1]))

    def test_duration_weighted_frame_bins_and_static_decomposition(self):
        cells=np.stack((np.zeros((8,8,3)),np.ones((8,8,3))))
        a=appearance(cells,[0.,.15],[.15,3.]);self.assertEqual(a[0,0],0.);self.assertAlmostEqual(a[1,0],.5)
        features=video_features(a);rev=video_features(a[::-1])
        self.assertTrue(np.allclose(features['static'],rev['static']));self.assertTrue(np.allclose(features['dynamic'].mean(0),0))
        with self.assertRaises(ValueError):appearance(cells,[0.,.16],[.15,3.])
        frame=np.full((16,24,3),255,dtype=np.uint8);self.assertTrue(np.array_equal(spatial_cells(frame),np.ones((8,8,3))))

    def test_acoustic_silence_and_no_guessed_origin(self):
        x=np.zeros((24000,2));a=acoustic(x,8000,0.)
        self.assertEqual(a.shape,(30,10));self.assertTrue(np.array_equal(a,np.zeros_like(a)))
        with self.assertRaises(ValueError):acoustic(x,8000,.01)

    def test_constant_decimals_do_not_create_dynamic_or_ocular_information(self):
        cells=np.full((7,8,8,3),.1);edges=np.linspace(0,3,8)
        a=appearance(cells,edges[:-1],edges[1:]);v=video_features(a)
        self.assertTrue(np.array_equal(a,np.full_like(a,.1)))
        self.assertTrue(np.array_equal(v['dynamic'],np.zeros_like(v['dynamic'])))
        self.assertTrue(np.array_equal(v['static'][192:],np.zeros(192)))
        x=np.full((1,3,1800),.1);x[:,:,50:55]=np.nan
        e=eye_bins(x);self.assertTrue(np.array_equal(e[0,:,0:3],np.full((150,3),.1)))
        self.assertTrue(np.array_equal(e[0,:,3:6],np.zeros((150,3))))

    def test_query_only_shift_leaves_fit_validation_identical(self):
        rng=np.random.default_rng(7);n=rng.normal(size=(5,4));e=rng.normal(size=(5,3));d=rng.normal(size=(5,30,192))
        full=design(n,e,d,'full',[0,1,2],[4]);shift=design(n,e,d,'full_shift500ms',[0,1,2],[4])
        self.assertTrue(np.array_equal(full[:4],shift[:4]));self.assertTrue(np.array_equal(full[4,:7],shift[4,:7]));self.assertFalse(np.array_equal(full[4,7:],shift[4,7:]))

    def test_signed_effects_participant_unit_and_fixed_calibration_sensitivity(self):
        p,y=predictions();out=evaluate(p,y,bootstrap_draws=10000)
        self.assertEqual(out['primary_full_mse'],1.);self.assertEqual(out['contrasts']['dynamic_gain_given_eye'],8.)
        self.assertEqual(out['descriptive_participant_bootstrap']['pointwise_95_percentile']['dynamic_gain_given_eye'],{'lower':8.,'upper':8.})
        self.assertIsNone(out['qualified_dynamic_information']);self.assertEqual(len(out['participants']),6)
        p['sub-03']['full'][:]=10.;out=evaluate(p,y,bootstrap_draws=10)
        self.assertGreater(out['primary_full_mse'],1.);self.assertEqual(out['fixed_leave_sub03_out_sensitivity']['arm_mse']['full'],1.)

    def test_weak_control_does_not_improve_primary_and_extremes_stay_finite_decimal(self):
        p,y=predictions();before=evaluate(p,y,bootstrap_draws=2)
        for person in SUBJECTS:p[person]['nuisance_eye'][:]=100.
        after=evaluate(p,y,bootstrap_draws=2);self.assertEqual(before['primary_full_mse'],after['primary_full_mse'])
        self.assertTrue(mse(np.array([1e308]),np.array([-1e308])).is_finite())

    def test_primitive_npy_rejects_object_false_shape_and_trailing_body(self):
        f=io.BytesIO();np.save(f,np.arange(6,dtype=np.float64).reshape(2,3),allow_pickle=False);b=f.getvalue()
        self.assertEqual(arrays.decode(b,(2,3)).shape,(2,3))
        for body,shape in ((b,(3,2)),(b+b'x',(2,3))):
            with self.assertRaises(ValueError):arrays.decode(body,shape)
        f=io.BytesIO();np.save(f,np.array([object()],dtype=object),allow_pickle=True)
        with self.assertRaises(ValueError):arrays.decode(f.getvalue(),(1,))

    def test_incomplete_candidate_never_opens_target_binding(self):
        q={'schema':'neural080_query_v1','subjects':list(SUBJECTS),'video_ids':list(range(1001,1103)),
           'shape_per_subject':[102,127,150],'arms':list(ARMS)}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);candidate=root/'candidate';candidate.mkdir();qb=json.dumps(q).encode();qp=root/'query.json';qp.write_bytes(qb)
            (candidate/'submission.json').write_text(json.dumps({'schema':'neural080_submission_v1','query_sha256':hashlib.sha256(qb).hexdigest(),'predictions':[]}))
            actual=score.capture
            def guarded(path,*args):
                if path.name=='FORBIDDEN':raise AssertionError('Private binding opened')
                return actual(path,*args)
            with patch.object(score,'capture',side_effect=guarded):
                with self.assertRaises(ValueError):score.score(candidate,qp,root/'FORBIDDEN')

    def test_full_recording_census_refuses_before_signal_or_feature_read(self):
        joined=json.dumps({'subjects':[]}).encode()
        records=[{'subject':p,'session':s,'modality':m,'relative_path':p+'/'+s+'/'+m+'.h5'}
                 for p in SUBJECTS for s in SESSIONS for m in ('eeg','eye')]
        required=json.dumps({'files':records}).encode()
        def captured(path,*args):
            if path.name=='JOINED_METADATA.json':return joined
            if path.name=='REQUIRED_RECORDINGS.json':return required
            raise AssertionError('Unexpected feature or signal access')
        with tempfile.TemporaryDirectory() as tmp,patch.object(prepare_pool,'capture',side_effect=captured),\
             patch.object(prepare_pool,'JOIN_SHA',hashlib.sha256(joined).hexdigest()),\
             patch.object(prepare_pool,'REQUIRED_SHA',hashlib.sha256(required).hexdigest()):
            with self.assertRaisesRegex(ValueError,'Complete96 source recordings'):prepare_pool.prepare(Path(tmp),Path('forbidden'),Path(tmp)/'out',10000)
            self.assertFalse((Path(tmp)/'out').exists())

    def test_stale_report_rejected_before_any_scoring_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'existing';out.write_text('old')
            argv=['score.py','--candidate','missing','--query','missing','--binding','missing','--out',str(out)]
            with patch.object(sys,'argv',argv),patch.object(score,'score',side_effect=AssertionError('Unexpected input access')):
                with self.assertRaises(ValueError):score.main()

    def test_writer_refuses_nonfinite_arrays_before_persisting(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer=prepare_pool.Writer(Path(tmp)/'pool',10000)
            for value in (math.nan,math.inf,-math.inf):
                with self.assertRaises(ValueError):writer.array('invalid.npy',np.asarray([value]))
                self.assertEqual(writer.used,0);self.assertFalse((writer.root/'invalid.npy').exists())
            receipt=writer.array('finite.npy',np.asarray([0.,.1,-1.]))
            self.assertEqual(receipt['bytes'],writer.used);self.assertEqual(len(writer.files),1)


if __name__=='__main__':unittest.main()
