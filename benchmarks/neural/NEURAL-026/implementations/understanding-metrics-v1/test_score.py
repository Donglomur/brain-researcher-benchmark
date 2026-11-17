"""Generated complete-support controls. No biological data or model fitting."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('neural026_new_score', HERE / 'score.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def panel(folder, *, candidate_offset=0., nuisance_offset=2., legacy=False,
          candidate_nuisance_offset=100., constant_target=False):
    api = s.backend()
    design = {'schema': 'neural026_design_v1', 'cases': []}
    manifest = {'schema': s.LEGACY_SCHEMA if legacy else s.NEW_SCHEMA, 'cases': []}
    truth, references = {}, {}
    folder.mkdir()
    for mouse in api.p.MICE:
        for area in api.p.AREAS:
            for fold in range(5):
                cid = f'{mouse}_{area}_fold{fold}'
                qids = [i for i in range(1, 21) if (i-1) % 5 == fold]
                row = dict(case_id=cid, mouse=mouse, area=area, fold=fold,
                           train_id=[i for i in range(1, 21) if i not in qids], query_id=qids,
                           matched_counts={'1': 10, '2': 10})
                design['cases'].append(row)
                ids = np.array(qids, dtype=np.int64)
                y = np.broadcast_to(ids[:, None, None] + np.arange(51)[None, :, None]/50.
                                    + np.arange(24)[None, None, :]/24., (4, 51, 24)).copy()
                if constant_target:
                    y[:] = 1.
                data = {'trial_id': ids, 'neural': y + candidate_offset}
                if legacy:
                    data.update(nuisance=y+candidate_nuisance_offset, shifted=y+17.)
                path = folder / (cid+'.npz')
                np.savez(path, **data)
                raw = path.read_bytes()
                manifest['cases'].append(dict(case_id=cid, file=path.name,
                    bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
                truth[cid] = {'trial_id': ids, 'y': y}
                references[cid] = {'trial_id': ids, 'nuisance': y+nuisance_offset,
                                   'neural': y+1., 'shifted': y+3.}
    (folder / 'submission.json').write_text(json.dumps(manifest))
    return design, truth, references


class MeasuredTargetTests(unittest.TestCase):
    def test_complete_measured_gain_and_actual_target_error(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp).resolve()/'candidate'
            design, truth, reference = panel(folder)
            result = s.evaluate(folder, design, lambda cid: (truth[cid], reference[cid]))
            self.assertEqual(result['complete_cases'], 50)
            self.assertEqual(result['independent_mice'], 5)
            self.assertTrue(result['primary_value'] > 0)
            rows = result['biological_effects']
            self.assertEqual(len(rows), 10)
            self.assertTrue(all(row['candidate_joint_mse'] == [0.]*24 for row in rows))
            self.assertTrue(all(np.allclose(row['fixed_nuisance_joint_mse'], 4.) for row in rows))
            self.assertFalse(result['candidate_nuisance_used'])

    def test_candidate_cannot_degrade_baseline_to_raise_primary(self):
        with tempfile.TemporaryDirectory() as temp:
            f1, f2 = Path(temp).resolve()/'one', Path(temp).resolve()/'two'
            d1,t1,r1 = panel(f1, candidate_offset=1., legacy=True, candidate_nuisance_offset=0.)
            d2,t2,r2 = panel(f2, candidate_offset=1., legacy=True, candidate_nuisance_offset=1e6)
            a=s.evaluate(f1,d1,lambda cid:(t1[cid],r1[cid]))
            b=s.evaluate(f2,d2,lambda cid:(t2[cid],r2[cid]))
            self.assertEqual(a['primary_value'],b['primary_value'])
            self.assertEqual(a['biological_effects'],b['biological_effects'])

    def test_negative_gain_is_valid_and_not_clipped(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp).resolve()/'candidate';d,t,r=panel(folder,candidate_offset=5.)
            result=s.evaluate(folder,d,lambda cid:(t[cid],r[cid]))
            self.assertLess(result['primary_value'],0.)
            self.assertIsNone(result['binary_pass'])

    def test_invalid_final_case_before_any_private_read(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp).resolve()/'candidate';d,t,r=panel(folder)
            last=d['cases'][-1]['case_id']
            (folder/(last+'.npz')).unlink()
            calls=[]
            with self.assertRaises(ValueError):
                s.evaluate(folder,d,lambda cid:calls.append(cid))
            self.assertEqual(calls,[])

    def test_disjoint_complete_fold_support_required_before_private_read(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp).resolve()/'candidate';d,t,r=panel(folder)
            d=copy.deepcopy(d);d['cases'][0]['query_id']=d['cases'][1]['query_id']
            calls=[]
            with self.assertRaises(ValueError):s.evaluate(folder,d,lambda cid:calls.append(cid))
            self.assertEqual(calls,[])

    def test_target_and_reference_alignment_and_flat_target_refuse(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp).resolve()/'candidate';d,t,r=panel(folder)
            def wrong(cid):
                bad=copy.deepcopy(r[cid]);bad['trial_id']=bad['trial_id'][::-1]
                return t[cid],bad
            with self.assertRaises(ValueError):s.evaluate(folder,d,wrong)
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp).resolve()/'candidate';d,t,r=panel(folder,constant_target=True)
            with self.assertRaises(ValueError):s.evaluate(folder,d,lambda cid:(t[cid],r[cid]))

    def test_finite_extreme_predictions_fail_without_nonfinite_grade(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp).resolve()/'candidate';d,t,r=panel(folder,candidate_offset=1e308)
            with self.assertRaises((FloatingPointError,ValueError)):
                s.evaluate(folder,d,lambda cid:(t[cid],r[cid]))

    def test_nonzero_residual_underflow_cannot_appear_perfect(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp).resolve()/'candidate';d,t,r=panel(folder)
            cid=d['cases'][0]['case_id'];y=t[cid]['y'];y[0,0,0]=0.
            prediction=y.copy();prediction[0,0,0]=1e-300
            path=folder/(cid+'.npz');np.savez(path,trial_id=t[cid]['trial_id'],neural=prediction)
            raw=path.read_bytes();mp=folder/'submission.json';manifest=json.loads(mp.read_text())
            manifest['cases'][0].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            mp.write_text(json.dumps(manifest))
            with self.assertRaises(FloatingPointError):
                s.evaluate(folder,d,lambda key:(t[key],r[key]))

    def test_cli_requires_independent_operator_hash_and_rejects_changed_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();folder=root/'candidate';d,t,r=panel(folder)
            private=root/'private';private.mkdir();binding={'schema':'neural026_private_binding_v1','cases':{}}
            for cid in t:
                binding['cases'][cid]={}
                for role,arrays in [('target',t[cid]),('reference',r[cid])]:
                    path=private/(cid+'_'+role+'.npz');np.savez(path,**arrays);raw=path.read_bytes()
                    binding['cases'][cid][role]={'file':path.name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
            design=root/'design.json';design.write_text(json.dumps(d))
            bp=root/'binding.json';bp.write_text(json.dumps(binding))
            def argv(out,bhash):
                return ['--submission',str(folder),'--design',str(design),'--design-sha256',hashlib.sha256(design.read_bytes()).hexdigest(),
                    '--binding',str(bp),'--binding-sha256',bhash,'--private-root',str(private),'--output',str(root/out)]
            pin=hashlib.sha256(bp.read_bytes()).hexdigest()
            self.assertEqual(s.main(argv('grade.json',pin)),0)
            with self.assertRaises(ValueError):s.main(argv('wrong-hash.json','0'*64))
            item=next(iter(binding['cases'].values()))['reference']
            with open(private/item['file'],'ab') as f:f.write(b'changed')
            with self.assertRaises(ValueError):s.main(argv('changed-ref.json',pin))


if __name__=='__main__':unittest.main()
