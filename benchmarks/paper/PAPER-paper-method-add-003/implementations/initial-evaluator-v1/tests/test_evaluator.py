import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np
from scipy.io import savemat

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dredge_evaluator', ROOT / 'evaluator.py')
e = importlib.util.module_from_spec(spec); spec.loader.exec_module(e)
SETTINGS = dict(max_shift_bins=2, min_correlation=0.7, max_time_separation=3,
                huber_delta_um=2.0, iterations=5)


def signal():
    rng = np.random.default_rng(51023)
    z = np.arange(30.)
    base = rng.normal(size=40)
    d = np.array([0., 2., 0., -2., 0., 2., 0., -2.])
    v = np.array([np.interp(z - shift + 5, np.arange(40), base) for shift in d])
    return v, z, np.arange(len(d)) / 250, d


def evaluate(v=None, d=None):
    raw, z, t, truth = signal()
    return e.evaluate_segment(raw if v is None else v, z, t,
        fit_channels=list(range(0, 30, 2)), evaluation_channels=list(range(1, 30, 2)),
        displacements={'default_dredge': truth if d is None else d, 'alternate': np.zeros(8)},
        rigid_settings=SETTINGS, fixed_offset_um=0.)


class RegistrationTests(unittest.TestCase):
    def test_physical_translation_sign_and_gauge(self):
        v, z, _, truth = signal()
        result = e.rigid_reference(v[:, ::2], z[::2], **SETTINGS)
        np.testing.assert_allclose(result['displacement_um'], truth, atol=1e-7)

    def test_inverse_sampling_relation(self):
        z = np.arange(7.)
        raw = np.array([3*z, 3*(z-1), 3*(z+1)])
        corrected = e.align(raw, z, [0., 1., -1.])
        np.testing.assert_allclose(corrected[:, 1:-1], np.broadcast_to(3*z[1:-1], (3, 5)))
        self.assertTrue(np.isnan(corrected[1, -1]))
        self.assertTrue(np.isnan(corrected[2, 0]))

    def test_zero_displacement_identity(self):
        v, z, _, _ = signal()
        np.testing.assert_array_equal(e.align(v, z, np.zeros(len(v))), v)

    def test_nonrigid_fold_rejected(self):
        v, z, _, _ = signal()
        d = np.zeros_like(v); d[:, 4] = 10
        with self.assertRaisesRegex(ValueError, 'folds'):
            e.align(v, z, d)

    def test_nonrigid_inverse_affine_coordinate_map(self):
        z = np.arange(12.)
        d = np.broadcast_to(.2*z, (3, 12))
        raw = 3*(z[None, :]-d)
        corrected = e.align(raw, z, d)
        np.testing.assert_allclose(corrected[:, :9], np.broadcast_to(3*z[:9], (3,9)))
        self.assertTrue(np.isnan(corrected[:, 9:]).all())

    def test_constant_profiles_do_not_report_motion(self):
        with self.assertRaisesRegex(ValueError, 'identifiable'):
            e.rigid_reference(np.zeros((4, 8)), np.arange(8), **SETTINGS)

    def test_zero_weight_graph_not_identifiable(self):
        profiles=np.array([[1.,-1.,0.,0.],[0.,0.,1.,-1.]])
        with self.assertRaisesRegex(ValueError, 'identifiable'):
            e.rigid_reference(profiles,np.arange(4),max_shift_bins=0,min_correlation=0,
                max_time_separation=1,huber_delta_um=1)

    def test_undefined_pairs_cannot_support_paired_gain(self):
        profiles=np.array([[1.,2.,3.],[2.,4.,6.],[0.,0.,0.],[1.,2.,3.]])
        panel=e.metric_panel(profiles,profiles)
        self.assertAlmostEqual(panel['adjacent_profile_correlation'],1.)
        self.assertEqual(panel['defined_adjacent_pairs'],1)
        self.assertEqual(panel['total_adjacent_pairs'],3)
        self.assertIsNone(panel['complete_adjacent_profile_correlation'])

    def test_shared_support_and_true_shift_alignment(self):
        result = evaluate()
        panels = result['methods']
        self.assertAlmostEqual(panels['default_dredge']['adjacent_profile_correlation'], 1)
        self.assertGreater(panels['default_dredge']['paired_consistency_gain'], .1)
        self.assertEqual(len({p['retained_depth_channels'] for p in panels.values()}), 1)
        self.assertLess(result['coverage_fraction'], 1)
        self.assertEqual(result['scientific_readiness'], 'unknown')

    def test_holdout_and_support_fail_closed(self):
        v,z,t,d = signal()
        with self.assertRaisesRegex(ValueError, 'disjoint'):
            e.evaluate_segment(v,z,t,fit_channels=[0,1,2],evaluation_channels=[1,2,3],
                displacements={'default_dredge':d,'alternate':d},rigid_settings=SETTINGS,fixed_offset_um=0)
        with self.assertRaisesRegex(ValueError, 'common support'):
            evaluate(d=np.full(8, 500.))

    def test_smoothing_adversary_visible(self):
        v,_,_,_ = signal()
        smooth = np.broadcast_to(v.mean(axis=0), v.shape).copy()
        panel = e.metric_panel(smooth, v)
        self.assertAlmostEqual(panel['adjacent_profile_correlation'], 1.)
        self.assertEqual(panel['temporal_difference_energy_ratio'], 0.)
        zero = e.metric_panel(np.zeros_like(v), v)
        self.assertIsNone(zero['adjacent_profile_correlation'])
        self.assertEqual(zero['signal_energy_ratio'], 0.)

    def test_full_cohort_required_and_patient_macro(self):
        result=evaluate()
        with self.assertRaisesRegex(ValueError, 'Full human cohort'):
            e.summarize_cohort([dict(patient='Pt01',segment_id='a',result=result)])
        rows=[dict(patient=p,segment_id='a',result=result) for p in e.PATIENTS]
        summary=e.summarize_cohort(rows)
        self.assertEqual(summary['patient_count'],3)
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            e.summarize_cohort(rows+[rows[0]])


class RawAndCliTests(unittest.TestCase):
    def make_protocol(self, root):
        v,z,t,d=signal()
        protocol={'task_id':e.TASK_ID,'source_commit':e.SOURCE_COMMIT,
                  'metric_status':'prospective_unqualified','rigid_settings':SETTINGS,
                  'fixed_offset_um':0.,'segments':[]}
        for patient in e.PATIENTS:
            binary=root/f'{patient}.imec0.lf.bin'
            raw=np.column_stack([np.rint(v*1000),np.zeros(8)]).astype('<i2');raw.tofile(binary)
            meta=root/f'{patient}.imec0.lf.meta'
            meta.write_text('nSavedChans=31\nimSampRate=250\nsnsApLfSy=0,30,1\n')
            cm=root/f'{patient}_map.mat'
            savemat(cm,dict(chanMap=np.arange(1,31),xcoords=np.zeros(30),ycoords=z,connected=np.ones(30)))
            record=dict(patient=patient,segment_id='eval',role='evaluation',start_sample=0,stop_sample=8,
                binary=binary.name,meta=meta.name,channel_map=cm.name,recording_sha256=e.file_sha256(binary),
                meta_sha256=e.file_sha256(meta),map_sha256=e.file_sha256(cm),column_x=0.,
                fit_channels=list(range(0,30,2)),evaluation_channels=list(range(1,30,2)),estimates={})
            # Ensure fixture patient raw identities differ; a real digest identifies
            # one recording, so duplicate bytes would rightfully overlap below.
            raw[:,-1]=int(patient[-1]);raw.tofile(binary)
            record['recording_sha256']=e.file_sha256(binary)
            for method in e.REQUIRED_METHODS:
                path=root/f'{patient}_{method}.npz'
                np.savez(path,times_s=t,depths_um=z,displacement_um=d if method=='default_dredge' else np.zeros(8))
                record['estimates'][method]=dict(path=path.name,sha256=e.file_sha256(path),
                    recording_sha256=record['recording_sha256'],start_sample=0,stop_sample=8,
                    source_commit=e.SOURCE_COMMIT,settings={'engineering_fixture':True},fit_channels=record['fit_channels'])
            protocol['segments'].append(record)
        return protocol

    def test_cli_generated_full_cohort(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);protocol=self.make_protocol(root)
            path=root/'protocol.json';path.write_text(json.dumps(protocol));out=root/'out.json'
            run=subprocess.run([sys.executable,str(ROOT/'evaluator.py'),str(path),str(out)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            output=json.loads(out.read_text())
            self.assertEqual(output['cohort']['patient_count'],3)
            self.assertFalse(output['cohort']['full_contract_complete'])
            self.assertEqual(output['protocol_sha256'],e.file_sha256(path))

    def test_raw_loader_hash_and_aligned_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);s=self.make_protocol(root)['segments'][0]
            kw=dict(patient=s['patient'],start_sample=0,stop_sample=8,expected_sha256=s['recording_sha256'],
                expected_meta_sha256=s['meta_sha256'],expected_map_sha256=s['map_sha256'],column_x=0.)
            args=[root/s[k] for k in ['binary','meta','channel_map']]
            packet=e.load_raw_lfp(*args,**kw)
            self.assertEqual(packet['values'].shape,(8,30))
            kw['expected_sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'hash mismatch'):e.load_raw_lfp(*args,**kw)
            with self.assertRaisesRegex(ValueError,'raw human LFP'):
                e.load_raw_lfp(root/'Pt01_DREDgealigned_0.dat',args[1],args[2],**kw)

    def test_protocol_overlap_rejected_before_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);protocol=self.make_protocol(root)
            duplicate=dict(protocol['segments'][0]);duplicate['segment_id']='dev';duplicate['role']='development'
            protocol['segments'].append(duplicate)
            path=root/'p.json';path.write_text(json.dumps(protocol))
            run=subprocess.run([sys.executable,str(ROOT/'evaluator.py'),str(path),str(root/'out')],capture_output=True,text=True)
            self.assertNotEqual(run.returncode,0)
            self.assertIn('overlap',run.stderr)

if __name__=='__main__':unittest.main()
