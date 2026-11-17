"""Invented records only. No data/model fit/empirical score/reference access."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
import numpy as np
import protocol as p
import reference_program as ref
from io_utils import capture,read_json,read_features
from prepare import validate_binding,bool_response,windows_from_epochs
from score import grade


def fixture():
    people=['S1','S2','S3'];rows=[]
    for person in people:
        for half in (0,1):
            for category in (0,1):
                for duration in p.DURATIONS:
                    for relevance in p.RELEVANCE:
                        for orientation in p.ORIENTATIONS:
                            rows.append({'participant':person,'trial_id':str(len(rows)),
                                'stim_trigger':1+half+20*category,'category':category,
                                'duration_ms':duration,'relevance':relevance,'orientation':orientation})
    x=np.zeros((len(rows),5,6),dtype='<f8')
    for i,r in enumerate(rows):
        for j,w in enumerate(p.WINDOWS):
            x[i,j]=i+j if w in p.AVAILABLE[r['duration_ms']] else np.nan
    return people,rows,x


def report(people,value=.5):
    cells=dict.fromkeys(p.CELL_KEYS,value)
    return {'schema':'neural098-analysis-v1','participants':{s:{'cells':dict(cells),'contrasts':p.contrasts(cells)} for s in people}}


class Generated(unittest.TestCase):
    def test_full_support_and_group_holdout(self):
        people,rows,_=fixture();p.validate_rows(rows,people)
        for person in people:
            for half in (0,1):
                tr,te=p.split(rows,person,half)
                self.assertFalse(set(tr)&set(te));self.assertEqual({rows[i]['participant'] for i in tr},set(people)-{person})
                self.assertEqual({rows[i]['duration_ms'] for i in tr},{1500})
                self.assertFalse({rows[i]['stim_trigger'] for i in tr}&{rows[i]['stim_trigger'] for i in te})
        with self.assertRaises(ValueError):p.validate_rows(rows[:-1],people)
        bad=copy.deepcopy(rows);bad[0]['category']=1
        with self.assertRaises(ValueError):p.validate_rows(bad,people)

    def test_weights_equal_stratum_mass(self):
        people,rows,_=fixture();rows.append(dict(rows[0],trial_id='duplicate-observation'))
        tr,_=p.split(rows,'S3',1);weights=p.training_weights(rows,tr)
        self.assertAlmostEqual(sum(weights),len(tr))
        groups={}
        for i,w in zip(tr,weights):
            key=tuple(rows[i][k] for k in ('participant','category','duration_ms','relevance','orientation'))
            groups[key]=groups.get(key,0)+w
        self.assertLess(max(groups.values())-min(groups.values()),1e-12)

    def test_orchestration_spy_no_model_fit(self):
        people,rows,x=fixture();seen=[]
        class Spy:
            classes_=np.array([0,1])
            def fit(self,a,y,sample_weight):
                seen.append((a.copy(),y.copy(),sample_weight.copy()))
                self.mean=a.mean(axis=0);return self
            def predict_proba(self,a):
                if not np.isfinite(a).all():raise AssertionError('unavailable query window leaked')
                return np.tile([.5,.5],(len(a),1))
        probs=ref.predict_all(x,rows,people,Spy)
        self.assertEqual(len(seen),len(people)*2*5)
        self.assertTrue(all(np.allclose(a.mean(axis=0),0,atol=1e-12) for a,_,_ in seen))
        result=ref.aggregate(probs,rows,people);p.validate_report(result,people)
        self.assertTrue(all(v==.5 for r in result['participants'].values() for v in r['cells'].values()))

    def test_structural_missingness(self):
        people,rows,x=fixture();ref.validate_features(x,rows)
        x[0,4,0]=0
        with self.assertRaises(ValueError):ref.validate_features(x,rows)
        x[0,4,0]=np.nan;x[0,0,0]=np.nan
        with self.assertRaises(ValueError):ref.validate_features(x,rows)

    def test_perfect_and_reversed_aggregate(self):
        people,rows,_=fixture();a=np.full((len(rows),9),np.nan)
        for i,r in enumerate(rows):
            for j,(_,w) in enumerate(p.MAPPINGS):
                if w in p.AVAILABLE[r['duration_ms']]:a[i,j]=r['category']
        good=ref.aggregate(a,rows,people);bad=ref.aggregate(1-a,rows,people)
        self.assertTrue(all(v==1 for r in good['participants'].values() for v in r['cells'].values()))
        self.assertTrue(all(v==0 for r in bad['participants'].values() for v in r['cells'].values()))

    def test_temporal_contrast_hand_values(self):
        cells=dict.fromkeys(p.CELL_KEYS,.5)
        cells['Irrelevant|1500|middle>middle']=.9;cells['Irrelevant|500|middle>middle']=.6
        cells['Irrelevant|1500|onset>onset']=.8
        c=p.contrasts(cells)
        self.assertAlmostEqual(c['Irrelevant|diagonal|middle_duration_interaction'],0)
        self.assertAlmostEqual(c['Irrelevant|diagonal|long_late_minus_onset'],-.3)
        self.assertEqual(len(p.CELL_KEYS),42);self.assertEqual(len(p.CONTRAST_KEYS),24)

    def test_complete_admission_before_reference(self):
        people,_,_=fixture();value=report(people);value['participants']['S1']['cells'].pop(p.CELL_KEYS[0])
        touched=[]
        with self.assertRaises(ValueError):grade(value,people,lambda:touched.append(True))
        self.assertEqual(touched,[])
        value=report(people);value['participants']['S1']['cells'][p.CELL_KEYS[0]]=10**400
        with self.assertRaises(ValueError):grade(value,people,lambda:touched.append(True))
        self.assertEqual(touched,[])

    def test_reconstruction_no_direction_reward(self):
        people,_,_=fixture();a=report(people);a['participants']['S1']['cells'][p.CELL_KEYS[0]]=.2
        a['participants']['S1']['contrasts']=p.contrasts(a['participants']['S1']['cells'])
        out=grade(a,people,lambda:copy.deepcopy(a));self.assertEqual(out['primary_cell_mae'],0)
        b=report(people);self.assertGreater(grade(b,people,lambda:a)['primary_cell_mae'],0)
        self.assertIsNone(out['p_values']);self.assertFalse(out['method_execution_authenticated'])

    def test_event_clock_response_and_censoring(self):
        row={'duration_ms':500,'stim_trigger':1}
        b={'selection_index':0,'run':1,'event_sample':1000,'epoch_event_sample':12345,'offset_sample':1500,'next_onset_sample':2000,'button_samples':[],'stim_trigger':1}
        self.assertTrue(validate_binding(row,b,1000,12345))
        self.assertFalse(validate_binding(row,dict(b,button_samples=[1100]),1000,12345))
        self.assertFalse(validate_binding(row,dict(b,next_onset_sample=1700),1000,12345))
        with self.assertRaises(ValueError):validate_binding(row,dict(b,offset_sample=1600),1000,12345)
        with self.assertRaises(ValueError):validate_binding(row,b,1000,12346)
        self.assertFalse(bool_response('False'));self.assertTrue(bool_response(True))
        for v in ('false',0,1,None):
            with self.assertRaises(ValueError):bool_response(v)

    def test_bounded_io_and_npy_same_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);f=root/'x.json';f.write_bytes(b'{"x":1,"x":2}')
            with self.assertRaises(ValueError):read_json(f)
            f.write_bytes(b'{}');raw,digest=capture(f,100);self.assertEqual(raw,b'{}')
            with self.assertRaises(ValueError):capture(f,100,'0'*64)
            fifo=root/'fifo';os.mkfifo(fifo)
            with self.assertRaises(ValueError):capture(fifo,100)
            people,rows,x=fixture();npy=root/'x.npy';np.save(npy,x,allow_pickle=False)
            sha=hashlib.sha256(npy.read_bytes()).hexdigest()
            self.assertEqual(read_features(npy,sha,len(rows)).shape,x.shape)
            np.save(npy,x.astype('<f4'),allow_pickle=False)
            with self.assertRaises(ValueError):read_features(npy,hashlib.sha256(npy.read_bytes()).hexdigest(),len(rows))

    def test_stale_output_precedes_reads(self):
        import score
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'out';out.symlink_to(Path(td)/'absent')
            argv=['score','--submission','absent','--reference','absent','--reference-sha256','0'*64,'--output',str(out)]
            with patch.object(sys,'argv',argv),patch.object(score,'read_json',side_effect=AssertionError('input opened')):
                with self.assertRaises(ValueError):score.main()

    def test_window_projection_invented_epochs(self):
        class Epochs:
            ch_names=list(p.CHANNELS);info={'bads':[],'sfreq':100.}
            times=np.arange(-50,201)/100
            def __init__(self,data):self.data=data
            def get_channel_types(self):return ['mag']*6
            def __getitem__(self,ids):return Epochs(self.data[ids])
            def get_data(self,picks):return self.data
        fake=Epochs(np.tile(Epochs.times,(3,6,1)))
        rows=[{'duration_ms':d} for d in p.DURATIONS]
        x=windows_from_epochs(fake,[0,1,2],rows)
        self.assertTrue(np.allclose(x[:,0],.2));self.assertTrue(np.allclose(x[:,1],.6))
        self.assertTrue(np.isnan(x[0,3:]).all());self.assertTrue(np.isnan(x[1,4]).all())
        self.assertTrue(np.isfinite(x[2]).all())

    def test_packet_schema(self):
        people,rows,_=fixture();q={'schema':'neural098-packet-v1','features_sha256':'a'*64,'rows':rows}
        p.validate_packet(q,people)
        for bad in [dict(q,features_sha256='a'*64+'\n'),dict(q,extra=True),dict(q,schema='wrong')]:
            with self.assertRaises(ValueError):p.validate_packet(bad,people)

    def test_cli_synthetic_reference_failure_and_success(self):
        import score
        people,_,_=fixture();value=report(people)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);candidate=root/'candidate.json';target=root/'target.json'
            candidate.write_text(json.dumps(value));target.write_text(json.dumps(value))
            original=score.read_json
            def read(path,*args,**kwargs):
                if Path(path).name=='COHORT.json':return {'participants':people},'metadata'
                return original(path,*args,**kwargs)
            for name,sha,expected in [('good',hashlib.sha256(target.read_bytes()).hexdigest(),'scored'),('bad','0'*64,'operator_error')]:
                output=root/name
                argv=['score','--submission',str(candidate),'--reference',str(target),'--reference-sha256',sha,'--output',str(output)]
                with patch.object(sys,'argv',argv),patch.object(score,'read_json',side_effect=read):
                    if expected=='scored':score.main()
                    else:
                        with self.assertRaises(SystemExit):score.main()
                result=json.loads(output.read_text());self.assertEqual(result['status'],expected);self.assertTrue(result['reference_invoked'])
                self.assertEqual(result['primary_cell_mae'],0 if expected=='scored' else None)

    def test_stager_views_exclude_benchmark_oracle(self):
        from stage_view import stage
        people,rows,x=fixture()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'operator';(root/'public/source').mkdir(parents=True);(root/'private').mkdir()
            (root/'public/COHORT.json').write_text(json.dumps({'participants':people}))
            (root/'public/TASK.md').write_bytes(b'invented protocol');(root/'public/source/author.txt').write_bytes(b'invented author source')
            (root/'private/reference_program.py').write_bytes(b'private invented oracle')
            entries=[]
            for path,target,arm in [('public/TASK.md','TASK.md','both'),('public/source/author.txt','source/author.txt','B')]:
                body=(root/path).read_bytes();entries.append({'source':path,'target':target,'arm':arm,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()})
            (root/'private/ACCESS_VIEWS.json').write_text(json.dumps({'files':entries}))
            packet_dir=Path(td)/'packet';packet_dir.mkdir();np.save(packet_dir/'features.npy',x,allow_pickle=False)
            packet=packet_dir/'packet.json';packet.write_text(json.dumps({'schema':'neural098-packet-v1','rows':rows,'features_sha256':hashlib.sha256((packet_dir/'features.npy').read_bytes()).hexdigest()}))
            digest=hashlib.sha256(packet.read_bytes()).hexdigest()
            for arm in ('A','B'):
                out=Path(td)/arm;stage(root,arm,packet,digest,out)
                self.assertEqual((out/'source/author.txt').exists(),arm=='B')
                self.assertFalse(any(p.name=='reference_program.py' for p in out.rglob('*')))
                self.assertEqual((out/'data/packet.json').read_bytes(),packet.read_bytes())
                self.assertFalse(json.loads((out/'VIEW.json').read_text())['isolation_attested'])
                with self.assertRaises(ValueError):stage(root,arm,packet,digest,out)


if __name__=='__main__':unittest.main()
