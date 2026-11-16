"""Independent full-scope invented paired-loss controls; no clinical data."""
from pathlib import Path
from fractions import Fraction as F
import copy, hashlib, json, resource, signal, sys, time, types, unittest
S = Path(__file__).resolve().parent
PRIMARY = S / 'dosei_score.py'
source=(S/'dosei_paired.py').read_bytes()
assert len(source)==15568 and hashlib.sha256(source).hexdigest()=='5f885ffd5052765cedf2fd81bf98f2638c56da3080acc100acd1e13b14bef497'
q=types.ModuleType('independent_paired');exec(compile(source,str(S/'dosei_paired.py'),'exec'),q.__dict__)
m=q.primary_module(PRIMARY)
def encode(x):return json.dumps(x,separators=(',',':'),sort_keys=True).encode()
def sha(x):return hashlib.sha256(encode(x)).hexdigest()
def num(x):return None if x is None else F(int(x['numerator']),int(x['denominator']))
def primary_fixture():
    people=['Invented_A','Invented_B','Invented_C']
    policy={'schema':'dosei_complete_policy_v1','task':m.TASK,'categories':[1,2,3,4,5],
        'label_source':'original_EVENT_MOAAS_assessment','provenance':{k:'0'*64 for k in m.PROVENANCE},
        'people':people,'folds':[
            {'fold_id':'groupAB','training_people':[people[2]],'heldout_people':people[:2]},
            {'fold_id':'groupC','training_people':people[:2],'heldout_people':[people[2]]}],
        'recordings':[{'recording_id':'rec'+str(i),'person_id':people[i%3]} for i in range(171)],
        'assessments':[],'transitions':[]}
    pred={'schema':'dosei_predictions_v1','task':m.TASK,'assessments':[]}
    target={'schema':'dosei_targets_v1','task':m.TASK,'assessments':[]}
    for i in range(7328):
        person=0 if i<2 else 1 if i<5 else 2
        rid='rec'+str(person+3*(i%57))
        row={'assessment_id':'a'+str(i),'recording_id':rid,'source_event_id':'event'+str(i),
            'label_status':'ambiguous' if i==2 else 'valid','window_status':'complete',
            'timing_status':'verified','artifact_status':'included'}
        p=['0.25','0.25','0.25','0.25','0'];y=5
        if i==0:p=['1','0','0','0','0'];y=1
        if i==1:p=['0','0','0','0','1'];y=1
        if i==2:p=None;y=None
        if i==3:p=['0.2']*5;y=3
        if i==4:p=['1','0','0','0','0'];y=2
        policy['assessments'].append(row)
        pred['assessments'].append({'assessment_id':'a'+str(i),'outer_fold':'groupAB' if person<2 else 'groupC',
            'status':'not_evaluable' if i==2 else 'ok','probabilities':p})
        target['assessments'].append({'assessment_id':'a'+str(i),'category':y})
    for i in range(1129):
        policy['transitions'].append({'transition_id':'t'+str(i),'recording_id':'rec'+str(i%171),'source_event_id':'soc'+str(i)})
    # One original source event can legitimately annotate both separately typed kinds.
    policy['transitions'][0].update(recording_id=policy['assessments'][0]['recording_id'],source_event_id='event0')
    return policy,pred,target

def fixture():
    policy,original,targets=primary_fixture()
    maps={'schema':'dosei_frozen_pairing_manifest_v1','task':m.TASK,'policy_sha256':sha(policy),'arms':['armA'],
        'freeze_receipts':{k:'0'*64 for k in ('target_free_rules','original_packet_set','admissibility','before_outcomes')},
        'case_metadata':[{'assessment_id':row['assessment_id'],'session_id':'session_'+row['recording_id'],
          'nuisance_stratum':'stratum'+str(i%2),'original_packet_sha256':'1'*64} for i,row in enumerate(policy['assessments'])],
        'transforms':[]}
    pred={'schema':'dosei_paired_predictions_v1','task':m.TASK,'arms':[{'arm_id':'armA',
        'original_packet_set_sha256':'0'*64,'original':original,'transforms':[]}]}
    # case2 has an ambiguous original target; valid map still cannot make it scoreable.
    schedules=[{0:1,1:1,2:1,3:1,5:5,6:5},{4:5}]
    for j,support in enumerate(schedules):
        h=str(j+2)*64;tid='shuffle'+str(j)
        transform={'transform_id':tid,'kind':'temporal_shuffle','coordinate_map_sha256':h,
                   'nonidentity_receipt_sha256':'4'*64,'rows':[]}
        output={'transform_id':tid,'coordinate_map_sha256':h,'assessments':[]}
        for i,row in enumerate(policy['assessments']):
            mapped=i in support;paired=mapped and i!=2
            transform['rows'].append({'assessment_id':row['assessment_id'],'disposition':'supported' if mapped else 'unsupported',
                'reason':'supported' if mapped else 'unestablished_native_map','transformed_packet_sha256':h if mapped else None})
            output['assessments'].append({'assessment_id':row['assessment_id'],'outer_fold':original['assessments'][i]['outer_fold'],
                'status':'ok' if paired else 'not_paired','packet_sha256':h if mapped else None,
                'probabilities':[str(int(k==support[i])) for k in range(1,6)] if paired else None})
        maps['transforms'].append(transform);pred['arms'][0]['transforms'].append(output)
    return policy,maps,pred,targets

def admitted(p,maps,x):
    policy=m.admit_policy(p);parts=q.admit_maps(m,maps,policy,sha(p))
    return policy,parts,q.admit_predictions(m,x,policy,parts,maps)

class Independent(unittest.TestCase):
    def test_signed_pairing_equal_people_then_equal_transforms(self):
        p,maps,x,y=fixture();policy,parts,outputs=admitted(p,maps,x)
        out=q.grade(m,y,policy,parts,outputs)
        self.assertEqual(num(out['complete_original_scores']['armA']['primary_normalized_rps']),F(61,160))
        self.assertEqual(num(out['transforms'][0]['arms'][0]['supported_person_macro_difference']),F(-91,480))
        self.assertEqual(num(out['transforms'][1]['arms'][0]['supported_person_macro_difference']),F(1,2))
        self.assertEqual(num(out['equal_valid_transform_means'][0]['transformed_minus_original']),F(149,960))
        # Pooling the six matched observations would reverse the diagnostic's sign.
        self.assertLess((F(-1)+F(2,5)-2*F(15,32)+F(1,2))/6,0)
        self.assertEqual(out['available_transform_count'],2)
        self.assertEqual(out['transforms'][1]['people_without_support'],['Invented_A','Invented_C'])
        for t in out['transforms']:
            self.assertEqual(len(t['all_original_cases']),7328)
            self.assertEqual(sum(r['original_cases'] for r in t['coverage_by_person_recording_session_stratum']),7328)
            self.assertEqual(sum(r['paired_cases'] for r in t['coverage_by_person_recording_session_stratum']),
                             sum(len(v) for v in t['paired_case_ids_by_person'].values()))
        t=out['transforms'][0];self.assertFalse(t['all_original_cases'][2]['paired'])
        self.assertEqual(t['all_original_cases'][2]['mapping_disposition'],'supported')
        self.assertEqual(sum(sum(g['paired_target_categories'].values()) for g in t['coverage_by_person_recording_session_stratum']),5)
        self.assertFalse(out['actual_physical_transform_distinctness_verified'])
        self.assertFalse(out['native_mapping_admissibility_verified']);self.assertFalse(out['scientifically_qualified'])

    def test_all_unavailable_is_null_and_original_remains_complete(self):
        p,maps,x,y=fixture()
        for definition,output in zip(maps['transforms'],x['arms'][0]['transforms']):
            for r in definition['rows']:r.update(disposition='invalid',reason='unknown_masks',transformed_packet_sha256=None)
            for r in output['assessments']:r.update(status='not_paired',packet_sha256=None,probabilities=None)
        policy,parts,outputs=admitted(p,maps,x);out=q.grade(m,y,policy,parts,outputs)
        self.assertEqual(out['available_transform_count'],0);self.assertEqual(out['declared_distinct_mapping_count'],2)
        self.assertIsNone(out['equal_valid_transform_means'][0]['transformed_minus_original'])
        self.assertEqual(num(out['complete_original_scores']['armA']['primary_normalized_rps']),F(61,160))
        self.assertTrue(all(len(t['all_original_cases'])==7328 and len(t['people_without_support'])==3 for t in out['transforms']))

    def test_cli_original_or_transformed_failure_before_targets(self):
        p,maps,x,y=fixture()
        original=x['arms'][0]['original']['assessments'][-1]
        transformed=x['arms'][0]['transforms'][0]['assessments'][3]
        for row,pattern in ((original,'evaluable prediction'),(transformed,'failed supported')):
            saved=dict(row);row.update(status='not_paired',probabilities=None)
            raw={'policy':encode(p),'maps':encode(maps),'predictions':encode(x)};seen=[]
            def read(name,cap):
                seen.append(name)
                if name=='targets':raise AssertionError('protected targets opened')
                return raw[name]
            old_reader=m.read_regular;old_loader=q.primary_module
            m.read_regular=read;q.primary_module=lambda path:m
            argv=['--primary-source',str(PRIMARY),'--output','UNREACHED_INVENTED_PAIRED_OUTPUT']
            for k in q.CAPS:argv+=['--'+k,k,'--expected-'+k+'-sha256',hashlib.sha256(raw.get(k,b'unopened')).hexdigest()]
            try:
                with self.assertRaisesRegex(ValueError,pattern):q.main(argv)
            finally:m.read_regular=old_reader;q.primary_module=old_loader;row.clear();row.update(saved)
            self.assertEqual(seen,['policy','maps','predictions'])

    def test_second_arm_parity_and_supported_case_completeness(self):
        p,maps,x,y=fixture();maps['arms'].append('armB')
        # Shared immutable rows are legitimate invented object construction; only changed rows are copied.
        second=dict(x['arms'][0]);second['arm_id']='armB'
        second['transforms']=[dict(t) for t in second['transforms']]
        second['transforms'][0]['assessments']=list(second['transforms'][0]['assessments'])
        second['transforms'][0]['assessments'][0]=dict(second['transforms'][0]['assessments'][0])
        x['arms'].append(second);policy,parts,outputs=admitted(p,maps,x)
        self.assertEqual(set(outputs['armA'][1]['shuffle0']),set(outputs['armB'][1]['shuffle0']))
        bad=second['transforms'][0]['assessments'][0];bad['packet_sha256']='9'*64
        with self.assertRaisesRegex(ValueError,'identical transformed packet'):admitted(p,maps,x)
        bad['packet_sha256']='2'*64;second['transforms'][0]['assessments']=second['transforms'][0]['assessments'][:-1]
        with self.assertRaisesRegex(ValueError,'every original slot'):admitted(p,maps,x)

    def test_map_identity_schema_and_schedule_caps(self):
        p,maps,x,y=fixture();policy=m.admit_policy(p);policy_sha=sha(p)
        maps['case_metadata'][0]['category']=1
        with self.assertRaisesRegex(ValueError,'exact fields'):q.admit_maps(m,maps,policy,policy_sha)
        del maps['case_metadata'][0]['category']
        maps['transforms'][1]['coordinate_map_sha256']='2'*64
        with self.assertRaisesRegex(ValueError,'duplicate declared'):q.admit_maps(m,maps,policy,policy_sha)
        maps['transforms'][1]['coordinate_map_sha256']='3'*64
        maps['arms']=['arm'+str(i) for i in range(9)]
        with self.assertRaisesRegex(ValueError,'finite complete arm'):q.admit_maps(m,maps,policy,policy_sha)
        maps['arms']=['armA'];base=maps['transforms'][0]
        maps['transforms']=[dict(base,transform_id='t'+str(i)) for i in range(33)]
        with self.assertRaisesRegex(ValueError,'finite complete transform'):q.admit_maps(m,maps,policy,policy_sha)

if __name__ == '__main__':
    unittest.main()
