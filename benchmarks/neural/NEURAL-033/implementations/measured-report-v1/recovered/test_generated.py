"""Generated numerical/interface checks. No released observations are opened."""
import copy
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analysis_core as core
import package_io as io
import score

def fixture(mice=3):
    rows=[]
    slopes={'apical_control':1.,'apical_kir':2.,'basal_control':3.,'basal_kir':1.}
    for group in core.GROUPS:
        c,t=group.split('_')
        for m in range(mice):
            for a in range(3):
                for b in range(3):
                    baseline=2.**b
                    y=slopes[group]*(a+.5)/3+.2*(b+.5)/3+.05*m
                    rows.append({'row_id':f'{group}_{m}_{a}_{b}','mouse_id':f'{t}_{m}',
                                 'compartment':c,'treatment':t,'member_index0':m,'source_row0':a*3+b,
                                 'baseline_flag':{'kind':'list','value':[]},'followup_flag':{'kind':'str','value':'Stable'},
                                 'baseline_volume':baseline,'followup_volume':baseline*2.**y,'event_rate':a})
    return rows

def packet(rows,analysis):
    identity={'row_ids':[r['row_id'] for r in rows],'mouse_ids':sorted({r['mouse_id'] for r in rows})}
    return {'schema_version':1,'task_id':'NEURAL-033','contract_sha256':'c'*64,'input_sha256':'d'*64,'analysis':analysis},identity

class Generated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=fixture();cls.expected=core.analyze(cls.rows);cls.candidate,cls.identity=packet(cls.rows,cls.expected)

    def evaluate(self,candidate):
        return score.evaluate(candidate,self.identity,'c'*64,'d'*64,lambda:copy.deepcopy(self.expected))

    def test_known_slopes_and_contrasts(self):
        for p in self.expected['panels'].values():
            for key,wanted in zip(core.CONTRASTS,(1.,-2.,3.)):
                self.assertAlmostEqual(p['contrasts'][key]['estimate'],wanted,places=12)
                self.assertEqual(p['contrasts'][key]['uncertainty_status'],'defined')

    def test_exact_artifact_and_wrong_sign(self):
        self.assertEqual(self.evaluate(self.candidate)['primary_normalized_contrast_mae'],0)
        wrong=copy.deepcopy(self.candidate)
        wrong['analysis']['panels']['all']['contrasts'][core.CONTRASTS[0]]['estimate']*=-1
        self.assertGreater(self.evaluate(wrong)['primary_normalized_contrast_mae'],0)

    def test_complete_partition_before_reference(self):
        wrong=copy.deepcopy(self.candidate);wrong['analysis']['eligible_row_ids'].pop()
        called=[]
        result,code=score.grade_bytes(io.encode(wrong),self.identity,'c'*64,'d'*64,lambda:called.append(True))
        self.assertEqual(code,2);self.assertEqual(result['status'],'invalid_submission');self.assertEqual(called,[])

    def test_unsupported_disclosure_cannot_get_primary_zero(self):
        wrong=copy.deepcopy(self.candidate)
        wrong['analysis']['panels']['all']['delete_one_mouse'].pop('control_0')
        result=self.evaluate(wrong)
        self.assertIsNone(result['primary_normalized_contrast_mae']);self.assertGreater(result['structural_mismatch_count'],0)

    def test_missing_point_not_silently_omitted(self):
        wrong=copy.deepcopy(self.candidate)
        wrong['analysis']['panels']['all']['contrasts'][core.CONTRASTS[0]]={'estimate':None,'jackknife_se':None,'deletion_min':None,'deletion_max':None,'uncertainty_status':'point_unavailable'}
        result=self.evaluate(wrong);self.assertIsNone(result['primary_normalized_contrast_mae']);self.assertTrue(result['availability_mismatches'])

    def test_huge_finite_error_does_not_overflow(self):
        wrong=copy.deepcopy(self.candidate)
        for panel in wrong['analysis']['panels'].values():
            for item in panel['contrasts'].values():item['estimate']=1.7e308
        self.assertTrue(math.isfinite(self.evaluate(wrong)['primary_normalized_contrast_mae']))

    def test_adjacent_float_error_retained(self):
        a=math.nextafter(2.,-math.inf)
        self.assertEqual(score.relative_error(a,2.),abs(a-2.)/3.)
        self.assertGreater(score.relative_error(a,2.),0)

    def test_impossible_fit_rejected_before_reference(self):
        mutations=[{'row_ids':[],'mice':[],'n_rows':0,'n_mice':0},
                   {'effective_mice':None},{'effective_mice':-1},{'effective_mice':4}]
        for changes in mutations:
            wrong=copy.deepcopy(self.candidate);wrong['analysis']['panels']['all']['groups']['apical_control'].update(changes)
            called=[];result,code=score.grade_bytes(io.encode(wrong),self.identity,'c'*64,'d'*64,lambda:called.append(True))
            self.assertEqual(code,2);self.assertEqual(called,[])

    def test_json_format_rejections_before_reference(self):
        body=io.encode(self.candidate)
        cases=[b'{"a":1,"a":2}',body.decode().encode('utf-16'),b'{"a":NaN}',b'['*1500+b']'*1500]
        wrong=copy.deepcopy(self.candidate);wrong['schema_version']=True;cases.append(io.encode(wrong))
        wrong=copy.deepcopy(self.candidate);wrong['input_sha256']='e'*64;cases.append(io.encode(wrong))
        for item in cases:
            called=[];result,code=score.grade_bytes(item,self.identity,'c'*64,'d'*64,lambda:called.append(True))
            self.assertEqual(code,2);self.assertFalse(result['reference_invoked']);self.assertEqual(called,[])

    def test_operator_failure_is_not_candidate_failure(self):
        def broken():raise OSError('operator fixture failure')
        result,code=score.grade_bytes(io.encode(self.candidate),self.identity,'c'*64,'d'*64,broken)
        self.assertEqual(code,3);self.assertEqual(result['status'],'operator_error');self.assertTrue(result['reference_invoked'])

    def test_both_shaft_flags_and_missing_values(self):
        for field,reason in [('baseline_flag','baseline_shaft'),('followup_flag','followup_shaft')]:
            row=copy.deepcopy(self.rows[0]);row[field]={'kind':'list','value':['Shaft Spine']};self.assertEqual(core.exclusion(row),reason)
        for field in ('baseline_volume','followup_volume','event_rate'):
            row=copy.deepcopy(self.rows[0]);row[field]=None;self.assertEqual(core.exclusion(row),'nonfinite_'+field)
        row=copy.deepcopy(self.rows[0]);row['followup_volume']=0;self.assertEqual(core.exclusion(row),'invalid_followup_volume')

    def test_within_mouse_replication_preserves_equal_mouse_estimand(self):
        rows=copy.deepcopy(self.rows)
        for row in self.rows:
            if row['mouse_id']=='kir_0':rows.append({**copy.deepcopy(row),'row_id':row['row_id']+'_copy'})
        actual=core.analyze(rows)
        for name,panel in actual['panels'].items():
            for key in core.CONTRASTS:self.assertAlmostEqual(panel['contrasts'][key]['estimate'],self.expected['panels'][name]['contrasts'][key]['estimate'],places=12)

    def test_nonordinary_candidate_and_changed_asset_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'a';p.write_bytes(b'{}');link=Path(tmp)/'link';link.symlink_to(p)
            with self.assertRaises(ValueError):io.read_bytes(link,100)
            pipe=Path(tmp)/'pipe';os.mkfifo(pipe)
            with self.assertRaises(ValueError):io.read_bytes(pipe,100)
            hard=Path(tmp)/'hard';os.link(p,hard)
            with self.assertRaises(ValueError):io.read_bytes(p,100)
            hard.unlink();base=Path(tmp)/'pkg';(base/'private').mkdir(parents=True);(base/'public').mkdir()
            target=base/'public/x.json';target.write_bytes(b'{}');record={'target':'public/x.json',**io.pin(b'[]')}
            (base/'private/asset_manifest.json').write_bytes(io.encode({'files':[record]}));prior=io.ROOT
            try:
                io.ROOT=base
                with self.assertRaises(ValueError):io.asset('public/x.json')
            finally:io.ROOT=prior

if __name__=='__main__':unittest.main(verbosity=2)
