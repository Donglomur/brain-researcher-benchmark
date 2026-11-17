"""Bounded generated engineering controls; no empirical reproduction evidence."""
import copy
import csv
import hashlib
import importlib.util
import json
import math
import pathlib
import subprocess
import sys
import tempfile
import unittest
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('evaluator', ROOT/'evaluator.py')
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def row(pid='p1', region='Postcentral_gyrus', time=0, paf=8, age=8, timescale=25, fit0=0):
    return dict(ID=pid,age=age,region=region,time=time,fit0=fit0,PAF=paf,PAA=.3,INT=timescale,offset=-1,knee=1,exp=2)


def cohort():
    rows=[]
    for p,age in enumerate([4,8,16,32]):
        for j,region in enumerate(e.REGIONS):
            x=math.log2(age)
            paf=3+x+(.5*x if e.REGIONS[region]=='A' else 0)+.1*j
            for time in range(3):
                rows.append(row(f'p{p}',region,time,paf,age,15+2*paf+.7*j+.2*x))
    return rows


def predictions(reference):
    folds=[]
    roster=reference['expected_participants']
    for pid in roster:
        folds.append(dict(fold=pid,train_participants=[p for p in roster if p!=pid],test_participants=[pid],
            predictions=[dict(ID=r['ID'],region=r['region'],metric=m,prediction=r[m])
                         for r in reference['participant_region'] if r['ID']==pid for m in e.METRICS]))
    return dict(folds=folds)


class EvaluatorTests(unittest.TestCase):
    def test_independent_gaussian_reference(self):
        rows=[row(time=i,paf=v) for i,v in enumerate([4,6,float('nan'),10,12])]
        actual=e.qc_and_smooth(e.validate_rows(rows,['p1']))
        expected=[4.755081337596291,5.614367460826813,8,10.385632539173187,11.24491866240371]
        np.testing.assert_allclose([r['PAF'] for r in actual],expected,rtol=0,atol=1e-12)
        self.assertTrue(actual[2]['PAF_filled'])

    def test_qc_strict_boundaries_and_refill(self):
        rows=[row(time=i,fit0=f,paf=v) for i,(f,v) in enumerate([(0,4),(.2,6),(-.2,8),(float('nan'),10),(0,12)])]
        actual=e.qc_and_smooth(e.validate_rows(rows,['p1']))
        self.assertEqual([r['keep'] for r in actual],[True,False,False,False,True])
        self.assertAlmostEqual(actual[2]['PAF'],8)
        self.assertTrue(actual[2]['PAF_filled'])

    def test_order_invariance_and_group_isolation(self):
        rows=cohort()
        a=e.analyze(rows,['p0','p1','p2','p3'])
        b=e.analyze(list(reversed(rows)),['p0','p1','p2','p3'])
        self.assertEqual(e.json_safe(a),e.json_safe(b))
        a=e.qc_and_smooth(e.validate_rows([row(paf=4),row(pid='p2',paf=12)],['p1','p2']))
        self.assertEqual([r['PAF'] for r in a],[4,12])

    def test_independent_nonperfect_ols(self):
        model=e.ols([1,2,2,4],[[1,x] for x in [2,3,4,5]],['Intercept','log2_age'])
        self.assertAlmostEqual(model['terms']['Intercept']['coefficient'],-.9)
        self.assertAlmostEqual(model['terms']['log2_age']['coefficient'],.9)
        self.assertAlmostEqual(model['rss'],.7)
        self.assertAlmostEqual(model['r_squared'],.8526315789473683)
        self.assertAlmostEqual(model['terms']['log2_age']['standard_error'],.26457513110645914)
        self.assertAlmostEqual(model['terms']['log2_age']['p_two_sided'],.07661948312336131,places=12)

    def test_student_t_closed_form_df_one_and_two(self):
        for t in [0,.01,1,2,20,1000]:
            self.assertAlmostEqual(e.student_t_two_sided(t,1),1-2*math.atan(t)/math.pi,places=12)
            self.assertAlmostEqual(e.student_t_two_sided(t,2),1-t/math.sqrt(t*t+2),places=12)

    def test_bh_unsorted_and_ties(self):
        actual=e.bh_adjust({'c':.08,'a':.01,'b':.04,'d':.04})
        for key,value in {'a':.04,'b':.05333333333333334,'d':.05333333333333334,'c':.08}.items():
            self.assertAlmostEqual(actual[key],value)

    def test_paired_log_age_contrast(self):
        rows=[]
        for i,age in enumerate([4,8,16]):
            rows += [row(f'p{i}',paf=6+2*i,age=age),row(f'p{i}','Middle_frontal_gyrus',paf=7+3*i,age=age)]
        result=e.analyze(rows,['p0','p1','p2'])
        terms=result['prospective_paired_hierarchy']['PAF']['model']['terms']
        self.assertAlmostEqual(terms['log2_age']['coefficient'],1)
        self.assertAlmostEqual(terms['Intercept']['coefficient'],-1)
        self.assertFalse(result['scientifically_qualified'])

    def test_source_pooling_not_region_balancing(self):
        rows=[row(region='Postcentral_gyrus',paf=4),row(region='Precentral_gyrus',paf=10)]
        rows += [row(region='Precentral_gyrus',time=t,paf=10) for t in [1,2]]
        result=e.analyze(rows,['p1'])
        self.assertAlmostEqual(result['participant_context_pooled_time_rows'][0]['PAF'],8.5)
        self.assertEqual(result['prospective_paired_hierarchy']['PAF']['excluded_missing_context_or_endpoint'],['p1'])

    def test_all_missing_and_constant_age_are_unestimable(self):
        rows=[row(f'p{i}',paf=float('nan'),timescale=float('nan')) for i in range(4)]
        result=e.analyze(rows,[f'p{i}' for i in range(4)])
        self.assertEqual(result['source_age_models']['PAF']['omnibus']['status'],'not_estimable')
        self.assertEqual(e.ols([1,2,3],[[1,1]]*3,['a','b'])['status'],'not_estimable')

    def test_source_interaction_and_participant_covariance(self):
        rows=[]
        for i,age in enumerate([4,8,16,32]):
            for j,region in enumerate(e.REGIONS):
                s=float(e.REGIONS[region]=='S')
                paf=4+.2*i+.3*j+.05*i*j
                tau=10+3*s+2*paf+1.5*s*paf+.7*math.log2(age)
                rows.append(row(f'p{i}',region,paf=paf,age=age,timescale=tau))
        result=e.analyze(rows,[f'p{i}' for i in range(4)])
        model=result['source_region_level_INT_PAF_interaction']
        for term,truth in {'Intercept':10,'ctx_S':3,'PAF':2,'ctx_S:PAF':1.5,'log2_age':.7}.items():
            self.assertAlmostEqual(model['terms'][term]['coefficient'],truth,places=10)
        self.assertEqual(result['prospective_participant_clustered_INT_PAF_interaction']['inference_df'],3)
        for context, intercept, slope in [('A',10,2),('S',13,3.5)]:
            terms=result['source_context_INT_PAF_age_models'][context]['terms']
            self.assertAlmostEqual(terms['Intercept']['coefficient'],intercept,places=10)
            self.assertAlmostEqual(terms['PAF']['coefficient'],slope,places=10)
            self.assertAlmostEqual(terms['log2_age']['coefficient'],.7,places=10)
        joint=result['participant_region']
        corr=float(np.corrcoef([r['PAF'] for r in joint],[r['INT'] for r in joint])[0,1])
        self.assertAlmostEqual(result['source_pooled_region_PAF_INT_correlation']['r'],corr,places=12)

    def test_validation_adversaries(self):
        cases=[]
        cases.append(([row(),row()],['p1']))
        cases.append(([row(),row(time=1,age=9)],['p1']))
        cases.append(([row(region='unknown')],['p1']))
        cases.append(([row(paf=14.1)],['p1']))
        cases.append(([row(timescale=0)],['p1']))
        cases.append(([row(fit0=float('inf'))],['p1']))
        cases.append(([row()],['p1','missing']))
        for rows,roster in cases:
            with self.subTest(rows=rows),self.assertRaises(e.ContractError):e.validate_rows(rows,roster)

    def test_perfect_heldout_and_train_only_baseline(self):
        reference=e.analyze(cohort(),['p0','p1','p2','p3'])
        result=e.evaluate_heldout(reference,predictions(reference))
        self.assertAlmostEqual(result['scores']['PAF']['candidate']['participant_macro_mae'],0)
        self.assertGreater(result['scores']['PAF']['train_only_region_mean']['participant_macro_mae'],0)
        self.assertFalse(result['training_exposure_verified'])

    def test_heldout_macro_weights_participants(self):
        reference=e.analyze(cohort(),['p0','p1','p2','p3'])
        reference['participant_region']=[r for r in reference['participant_region'] if r['ID']!='p0' or r['region']=='Postcentral_gyrus']
        submission=predictions(reference)
        for fold in submission['folds']:
            for p in fold['predictions']:
                p['prediction']+=4 if p['ID']=='p0' else 0
        result=e.evaluate_heldout(reference,submission)
        self.assertAlmostEqual(result['scores']['PAF']['candidate']['participant_macro_mae'],1)
        self.assertAlmostEqual(result['scores']['PAF']['candidate']['root_participant_macro_mse'],2)

    def test_heldout_rejects_missing_leakage_duplicate_extra(self):
        reference=e.analyze(cohort(),['p0','p1','p2','p3'])
        for mutation in ['missing','leakage','duplicate','extra','repeated_test','nan']:
            sub=predictions(reference)
            fold=sub['folds'][0]
            if mutation=='missing':fold['predictions'].pop()
            if mutation=='leakage':fold['train_participants'].append('p0')
            if mutation=='duplicate':fold['predictions'].append(fold['predictions'][0])
            if mutation=='extra':fold['predictions'][0]['region']='unknown'
            if mutation=='repeated_test':sub['folds'][1]['test_participants']=['p0']
            if mutation=='nan':fold['predictions'][0]['prediction']=float('nan')
            with self.subTest(mutation=mutation),self.assertRaises(e.ContractError):e.evaluate_heldout(reference,sub)

    def test_protected_reference_identity_and_duplicates_rejected(self):
        original=e.analyze(cohort(),['p0','p1','p2','p3'])
        submission=predictions(original)
        for mutation in ['duplicate','wrong_task','wrong_component','duplicate_roster','numeric_roster','unknown_id','unknown_region','missing_population','infinite_target']:
            reference=copy.deepcopy(original)
            if mutation=='duplicate':
                duplicate=dict(reference['participant_region'][0]);duplicate['PAF']+=1
                reference['participant_region'].append(duplicate)
            if mutation=='wrong_task':reference['task_id']='OTHER'
            if mutation=='wrong_component':reference['component']='OTHER'
            if mutation=='duplicate_roster':reference['expected_participants'].append('p0')
            if mutation=='numeric_roster':reference['expected_participants']=[0,1,2,3]
            if mutation=='unknown_id':reference['participant_region'][0]['ID']='UNKNOWN'
            if mutation=='unknown_region':reference['participant_region'][0]['region']='UNKNOWN'
            if mutation=='missing_population':reference['participant_region']=[r for r in reference['participant_region'] if r['ID']!='p0']
            if mutation=='infinite_target':reference['participant_region'][0]['PAF']=float('inf')
            with self.subTest(mutation=mutation),self.assertRaises(e.ContractError):e.evaluate_heldout(reference,submission)

    def test_numeric_roster_and_overflow_scores_rejected(self):
        with self.assertRaises(e.ContractError):e.analyze([row(pid='1')],[1])
        reference=e.analyze(cohort(),['p0','p1','p2','p3'])
        for value in [1e308,1e200]:
            submission=predictions(reference)
            submission['folds'][0]['predictions'][0]['prediction']=value
            with self.subTest(value=value),self.assertRaises(e.ContractError):e.evaluate_heldout(reference,submission)
        self.assertEqual(e._mean([1e308,1e308]),1e308)
        with self.assertRaises(e.ContractError):e._mean([float('inf'),1])

    def test_incomplete_region_family_does_not_reduce_fdr(self):
        rows=[r for r in cohort() if r['region']!='Supramarginal_gyrus']
        result=e.analyze(rows,['p0','p1','p2','p3'])
        for metric in e.METRICS:
            models=result['source_age_models'][metric]
            self.assertEqual(models['region_FDR_family']['estimable_regions'],5)
            self.assertEqual(models['region_FDR_family']['status'],'not_computed_incomplete_six_region_family')
            self.assertFalse(any('age_p_FDR_BH_within_metric' in model for model in models['regions'].values()))

    def test_paths_and_packet_cli_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            self.assertEqual(e.portable_relative_path(root,'tables\\params.csv'),root.resolve()/'tables'/'params.csv')
            for bad in ['../escape','/absolute','C:\\params.csv']:
                with self.assertRaises(e.ContractError):e.portable_relative_path(root,bad)
            table=root/'explicit_generated.csv'
            with table.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=e.COLUMNS);writer.writeheader();writer.writerows(cohort())
            packet={'table_sha256':hashlib.sha256(table.read_bytes()).hexdigest(),'official_code_commit':e.SOURCE_COMMIT,
                    'expected_participants':['p0','p1','p2','p3'],'assessment_kind':'generated_engineering_control'}
            packetpath=root/'packet.json';packetpath.write_text(json.dumps(packet))
            output=root/'output.json'
            result=subprocess.run([sys.executable,str(ROOT/'evaluator.py'),'analyze','--parameters',str(table),'--packet',str(packetpath),'--output',str(output)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            document=json.loads(output.read_text())
            self.assertEqual(document['qc']['input_rows'],72)
            self.assertFalse(document['canonical_13_participant_count_matches'])
            packet['table_sha256']='0'*64
            with self.assertRaises(e.ContractError):e.read_table(table,packet)

if __name__=='__main__':unittest.main()
