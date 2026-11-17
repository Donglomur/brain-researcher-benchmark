"""Independent invented DoSEI controls; no authentic policy or clinical data."""
from pathlib import Path
from fractions import Fraction as F
import copy, hashlib, json, resource, signal, sys, time, types, unittest

S = Path(__file__).resolve().parent
source = (S/'dosei_score.py').read_bytes()
assert len(source)==15749 and hashlib.sha256(source).hexdigest()=='09560538d472f0b99c65532bf371c8e9af56635e1ec437f68dd2f83b5f7bde77'
m=types.ModuleType('independent_dosei');exec(compile(source,str(S/'dosei_score.py'),'exec'),m.__dict__)

def encode(x): return json.dumps(x,separators=(',',':'),sort_keys=True).encode()
def as_fraction(x): return None if x is None else F(int(x['numerator']),int(x['denominator']))
def energy_rps(p,y):
    # Different algebraic definition: discrete energy distance, normalized by K-1.
    q=list(map(F,p))
    return (sum(q[i]*abs(i+1-y) for i in range(5))
            -sum(q[i]*q[j]*abs(i-j) for i in range(5) for j in range(5))/2)/4

def fixture():
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

def score(p,x,y):
    raw=[encode(v) for v in (p,x,y)]
    return m.score_artifacts(*raw,**{'expected_'+k+'_sha256':hashlib.sha256(b).hexdigest() for k,b in zip(m.INPUT_CAPS,raw)})

class Independent(unittest.TestCase):
    def test_three_person_unequal_support_energy_identity(self):
        p,x,y=fixture();before=hashlib.sha256(encode([p,x,y])).hexdigest();out=score(p,x,y)
        self.assertEqual(as_fraction(out['primary_normalized_rps']),F(61,160))
        self.assertNotEqual(F(61,160),(F(1)+F(7,20)+7323*F(15,32))/7327)
        self.assertEqual([as_fraction(r['normalized_rps']) for r in out['people']],[F(1,2),F(7,40),F(15,32)])
        for i in [0,1,3,4,5,7327]:
            self.assertEqual(as_fraction(out['assessments'][i]['normalized_rps']),
                             energy_rps(x['assessments'][i]['probabilities'],y['assessments'][i]['category']))
        self.assertIsNone(out['assessments'][2]['normalized_rps'])
        self.assertEqual([r['assessments'] for r in out['people']],[2,3,7323])
        self.assertEqual([r['evaluable'] for r in out['people']],[2,2,7323])
        self.assertEqual((len(out['recordings']),len(out['assessments']),sum(r['transitions'] for r in out['recordings'])),(171,7328,1129))
        self.assertEqual(sum(sum(r['statuses'].values()) for r in out['recordings']),7328)
        self.assertTrue(any(r['assessments']==0 for r in out['recordings']))
        self.assertFalse(out['transitions_are_targets']);self.assertFalse(out['scientifically_qualified'])
        self.assertEqual(hashlib.sha256(encode([p,x,y])).hexdigest(),before)

    def test_zero_person_preserves_denominator_and_valid_ineligible_labels(self):
        p,x,y=fixture()
        for i in (0,1):
            p['assessments'][i]['window_status']='incomplete'
            x['assessments'][i].update(status='not_evaluable',probabilities=None)
        out=score(p,x,y)
        self.assertIsNone(out['primary_normalized_rps']);self.assertEqual(out['people_without_evaluable_assessments'],['Invented_A'])
        self.assertEqual(out['counts']['evaluable_assessments'],7325);self.assertEqual(len(out['people']),3)
        self.assertEqual(len(out['assessments']),7328);self.assertEqual(out['people'][0]['assessments'],2)

    def test_admission_rejects_model_missingness_before_target_open(self):
        p,x,y=fixture();x['assessments'][-1].update(status='not_evaluable',probabilities=None)
        raw={'policy':encode(p),'predictions':encode(x)};seen=[]
        def read(name,cap):
            seen.append(name)
            if name=='targets':raise AssertionError('protected target read occurred')
            return raw[name]
        original=m.read_regular;m.read_regular=read
        args=[]
        for name in m.INPUT_CAPS:
            b=raw.get(name,b'not opened')
            args+=['--'+name,name,'--expected-'+name+'-sha256',hashlib.sha256(b).hexdigest()]
        args+=['--output','UNREACHED_INVENTED_OUTPUT']
        try:
            with self.assertRaisesRegex(ValueError,'evaluable prediction'):m.main(args)
        finally:m.read_regular=original
        self.assertEqual(seen,['policy','predictions'])

    def test_original_identity_namespaces_and_complete_fold_membership(self):
        p,x,y=fixture();m.admit_policy(p)
        p['assessments'][3]['source_event_id']='event0' # Different recording: legal source-local identity.
        m.admit_policy(p)
        p['assessments'][3]['recording_id']=p['assessments'][0]['recording_id']
        with self.assertRaisesRegex(ValueError,'repeated original assessment'):m.admit_policy(p)
        p,_,_=fixture()
        p['transitions'][1].update(recording_id=p['transitions'][0]['recording_id'],source_event_id=p['transitions'][0]['source_event_id'])
        with self.assertRaisesRegex(ValueError,'duplicate original transition'):m.admit_policy(p)
        p,_,_=fixture();p['folds'][1]['heldout_people'].append('Invented_A')
        with self.assertRaises(ValueError):m.admit_policy(p)
        p,_,_=fixture();p['assessments'].pop()
        with self.assertRaisesRegex(ValueError,'7328'):m.admit_policy(p)

    def test_exact_probability_energy_oracle_and_fixed_caps(self):
        vectors=[['0.1','0.2','0.3','0.1','0.3'],['0.999999999999999999','0.000000000000000001','0','0','0']]
        for vector in vectors:
            for category in range(1,6):
                self.assertEqual(m.normalized_rps(m.probability_vector(vector),category),energy_rps(vector,category))
        for kind,cap in m.INPUT_CAPS.items():
            raw=b' '*(cap+1)
            with self.assertRaisesRegex(ValueError,'input cap'):m.decode(raw,hashlib.sha256(raw).hexdigest(),kind)
        for vector in [['0.2']*4+['0.200000000000000001'],['1e0','0','0','0','0'],['nan','0','0','0','0']]:
            with self.assertRaises(ValueError):m.probability_vector(vector)

if __name__ == '__main__':
    unittest.main()
