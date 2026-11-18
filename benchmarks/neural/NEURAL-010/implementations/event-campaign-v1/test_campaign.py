"""Full686 generated exchange-peer controls. No authentic signals/native imports.

The externally supervised participant/custody/renderer services are explicit
in-memory doubles. The actual source campaign loop, phase15 admission, phase12
projection/freeze/scoring and observation arithmetic execute unchanged.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import common as u
import campaign as c
import provider

PREDECESSOR=Path(os.environ.get('NEURAL010_COMPATIBILITY_ROOT',str(HERE.parent/'preparation-compatibility-v1')))
sys.path.insert(0,str(PREDECESSOR))
import test_bridge as predecessor


def sha(raw):return hashlib.sha256(raw).hexdigest()


class MemoryIO(u.IO):
    def __init__(self,files,stats,budget):
        self.files=dict(files);self.stats=dict(stats);self.dirs=set();self.budget=budget
        self.accesses=[];self.used=0;self.assessment_reads=0;self.creates=[]
    def checked(self,path):return u.c.absolute(str(path))
    def directory(self,path):
        p=self.checked(path);self.budget.tick()
        u.need(str(p)not in self.dirs and str(p)not in self.files,'fresh generated directory')
        self.dirs.add(str(p));return p
    def create(self,path,body):
        p=self.checked(path);u.need(type(body)is bytes and 0<len(body)<=u.CAP,'bounded generated artifact')
        self.budget.charge('write_bytes',len(body))
        u.need(str(p)not in self.files,'create-only generated artifact')
        self.files[str(p)]=body;self.stats[str(p)]=u.pin(body);self.creates.append(str(p))
        return {'path':str(p),**u.pin(body)}
    def _capture(self,desc,role,cap):
        u.c.descriptor(desc,True);u.need(desc['bytes']<=cap,'bounded capture')
        self.charge(desc['bytes']+1)
        if desc['path']in self.files:raw=self.files[desc['path']]
        else:
            p=Path(desc['path']);u.need(p.is_relative_to(HERE),'only frozen source outside generated memory')
            raw=p.read_bytes()
        u.need(u.c.same(u.pin(raw),u.c.bare(desc)),'actual generated operand/source pin')
        self.accesses.append({'path':desc['path'],'role':role})
        return raw
    def capture(self,desc,role,cap=u.CAP):
        u.need(Path(desc['path']).name.casefold() not in ('assessment.json','train.json','validation.json'),'protected body requires explicit release')
        return self._capture(desc,role,cap)
    def capture_training(self,desc,cap=u.CAP):
        u.need(Path(desc['path']).name=='TRAIN.json','scoped training')
        return self._capture(desc,'authorized_current_fold_training',cap)
    def capture_assessment(self,desc,cap=u.CAP):
        self.assessment_reads+=1
        return self._capture(desc,'post_freeze_protected_assessment',cap)
    journal_body=predecessor.MemoryIO.journal_body
    names=predecessor.MemoryIO.names
    stat_only=predecessor.MemoryIO.stat_only


class GeneratedSignals:
    def __init__(self,io,public_root,bindings,rows):
        self.io,self.rows=io,rows;self.calls=[]
        io.signal_instance=self
    def window(self,row,req):
        self.calls.append((row['patient_id'],row['recording_id'],copy.deepcopy(req)))
        value=1.0 if int(row['recording_id'][-1],16)%2==0 else -1.0
        return [[value for _ in req['channels']]for _ in range(req['stop_sample']-req['start_sample'])]


class Fixture:
    def __init__(self,mode='frozen_program',training='other22'):
        self.base=predecessor.Fixture();self.files=dict(self.base.files);self.stats=dict(self.base.stats)
        self.source=u.pin((HERE/'SOURCE_MANIFEST.json').read_bytes())
        self.rows=u.parse(self.base.payloads['public/metadata.json'])['records']
        self.people=sorted({r['patient_id']for r in self.rows});self.events=[];self.fail_person=None;self.bad_freeze=False
        self.corrupt_reference=False;self.transport_calls=[]
        targets={r['recording_id']:r['events']for r in u.parse(self.base.payloads['private/assessment.json'])['records']}
        for person in self.people:
            doc={'schema':'neural010-detector-view-v1','task_id':'NEURAL-010','outer_person':person,
                 'inner_person':None,'role':'training','records':[dict(r,events=targets[r['recording_id']])for r in self.rows if r['patient_id']!=person]}
            raw=u.encoded(doc);name=f'/generated/original/private/views/{person}/final/TRAIN.json'
            wanted=next(v['artifacts']['TRAIN.json']for v in self.base.views if v['name']==person+'/final')
            assert u.pin(raw)==wanted
            self.files[name]=raw
        self.limits={'read_bytes':512*1048576,'write_bytes':128*1048576,'signal_samples':100000,'actions':10000,'seconds':120}
        policy={'training':training if mode=='frozen_program'else'none','max_actions_per_fold':1000,
            'max_samples_per_request':64,'max_channels_per_request':2,'frame_bytes':1048576,
            'delivery':'calibrated_windows'if mode=='frozen_program'else'rendered_pixels',
            'display_half_range_microvolts':None if mode=='frozen_program'else 100.0}
        contract={k:sha(('generated:'+k).encode())for k in c.CONTRACT_FIELDS}
        contract['resource_policy_sha256']=u.pin(u.encoded(self.limits))['sha256']
        contract['training_policy_sha256']=u.pin(u.encoded({'training':policy['training']}))['sha256']
        contract['tool_policy_sha256']=u.pin(u.encoded({'mode':mode,'policy':policy}))['sha256']
        contexts={person:{'context_id':sha(('context:'+person).encode()),'participant_exchange':f'/generated-exchange/{person}/participant',
            'custody_exchange':f'/generated-exchange/{person}/custody','renderer_exchange':f'/generated-exchange/{person}/renderer'if mode=='typed_viewer'else None}for person in self.people}
        # All comparator files are explicitly generated doubles selected BEFORE
        # the participant loop; their provenance cannot qualify real references.
        projected_scientific=[]
        prov=u.parse(self.base.payloads['private/SOURCE_PROVENANCE.json'])['records']
        bysource={r['recording_id']:r['source_path']for r in prov}
        for row in self.rows:
            projected_scientific.append({k:row[k]for k in ('recording_id','patient_id','duration_seconds','montage_id')}|{'source_record':bysource[row['recording_id']]})
        scientific_raw=json.dumps({'schema':'neural010-scientific-panel-v2','records':projected_scientific},sort_keys=True,separators=(',',':')).encode()
        self.panel_hash=sha(scientific_raw)
        refs={};runs={}
        for arm in ('matched_no_eeg','signal_reference','montage_only'):
            raw=json.dumps({'schema':'neural010-scientific-events-v2','panel_sha256':self.panel_hash,'arm':arm,
                'records':[{'recording_id':r['recording_id'],'events':[]}for r in self.rows]},sort_keys=True,separators=(',',':')).encode()
            refs[arm]=self.put('/generated-evaluation/'+arm+'.json',raw)
            closure=self.put('/generated-evaluation/'+arm+'.closure.json',u.encoded({'generated_process_evidence':True}))
            run={'schema':'neural010-reference-run-binding-v1','arm':arm,'stream':u.c.bare(refs[arm]),'held_people':self.people,
                'source_identity':u.pin(b'GENERATED REFERENCE SOURCE'),'training_protocol':u.pin(b'GENERATED TRAINING'),
                'tuning_protocol':u.pin(b'GENERATED TUNING'),'resource_protocol':u.pin(b'GENERATED BUDGET'),'closure_evidence':closure}
            runs[arm]=self.put('/generated-evaluation/'+arm+'.run.json',u.encoded(run))
        proof={'schema':'neural010-independent-reference-binding-v1','evidence_class':'generated_control',
            'reference_pins':{k:u.c.bare(v)for k,v in refs.items()},'candidate_contract':contract,
            'interpretation':'fixed_reference_comparison','reference_runs':runs,'matching_evidence':None}
        proof_desc=self.put('/generated-evaluation/provenance.json',u.encoded(proof))
        evaluation={'schema':'neural010-event-evaluation-selection-v1','references':refs,'reference_provenance':proof_desc,
            'interpretation':'fixed_reference_comparison','candidate_contract':contract,
            'original_panel':u.pin(self.base.payloads['public/panel.json']),
            'original_assessment':u.pin(self.base.payloads['private/assessment.json'])}
        eval_desc=self.put('/generated-evaluation/selection.json',u.encoded(evaluation))
        self.request={'schema':'neural010-event-campaign-request-v1','source':self.source,
            'preparation':self.base.original_selection,'mode':mode,'candidate_contract':contract,'policy':policy,
            'contexts':contexts,'limits':self.limits,'evaluation':eval_desc}
        self.request_raw=u.encoded(self.request)
        ids=sorted(v['context_id']for v in contexts.values())
        caps=['fresh_context_per_person','only_current_fold_allowlist','no_controller_filesystem','no_cross_fold_memory',
            'independent_launch_and_close','read_only_signals',policy['delivery']]
        if mode=='typed_viewer':caps+=['no_code_execution','no_raw_array_or_svg_export','no_task_specific_detector_tools','visual_observation_only']
        deployment={'schema':'neural010-event-deployment-binding-v1','campaign_request':u.pin(self.request_raw),
            'source':self.source,'evidence_class':'generated_control','context_ids':ids,'mode':mode,'capabilities':caps}
        deployment_desc=self.put('/generated-control/deployment.json',u.encoded(deployment))
        self.authority_raw=u.encoded({'schema':'neural010-event-campaign-authority-v1','request':u.pin(self.request_raw),
            'source':self.source,'evidence_class':'generated_control','deployment_receipt':deployment_desc,'context_ids':ids})

    def put(self,path,raw):
        self.files[path]=raw;self.stats[path]=u.pin(raw)
        return {'path':path,**u.pin(raw)}

    def io(self):return MemoryIO(self.files,self.stats,u.Budget(self.limits))

    def exchange_factory(self,io,root,context,role,cap):
        owner=self
        class Peer:
            def __init__(self):
                self.seq=0;self.rows=[];self.answers=[];self.mode=None;self.held=None;self.query=None;self.training_pending=False
                io.directory(root)
            def action(self,row):
                return {'kind':'observe','signal_handle':row['signal_handle'],'start_sample':0,'stop_sample':1,'channels':[0,1]}
            def ready(self):
                return {'kind':'ready','method_sha256':owner.request['candidate_contract']['method_sha256'],
                    'fold_state_sha256':sha(('generated-state:'+context).encode())}
            def request(self,value):
                io.budget.charge('actions',1);self.seq+=1
                envelope={'schema':'neural010-service-request-v1','context_id':context,'role':role,'sequence':self.seq,'body':value}
                body=u.encoded(envelope);u.need(len(body)<=cap,'generated outgoing frame cap')
                desc=io.create(Path(root)/f'request-{self.seq}.json',body)
                owner.transport_calls.append((role,context,value['operation']))
                if role=='custody':
                    operation=value['operation']
                    if operation=='freeze_state':
                        reply={'schema':'neural010-external-state-freeze-v1','context_id':context,'request_sha256':desc['sha256'],
                            'candidate_contract':value['candidate_contract'],'fold_state_sha256':value['fold_state_sha256'],
                            'training_complete':True,'held_query_not_delivered':not owner.bad_freeze,'state_immutable_for_query':True}
                    else:
                        reply={'schema':'neural010-external-context-receipt-v1','operation':operation,'context_id':context,
                            'request_sha256':desc['sha256'],'status':'isolated_context_started'if operation=='launch'else'natural_exit_and_context_retired',
                            'fold_state_sha256':value.get('fold_state_sha256'),'submission':value.get('submission')}
                elif role=='renderer':
                    u.need(value['operation']=='render_svg_to_pixels','only selected renderer operation')
                    u.need('<script'not in value['svg']and 'href='not in value['svg'],'self-contained generated rendering')
                    reply={'schema':'neural010-rendered-observation-v1','media_type':'image/png',
                        'image_handle':'image:'+sha(('generated-image:'+context+':'+str(self.seq)).encode()),
                        'render_sha256':value['render_sha256']}
                elif value['operation']=='initialize':
                    self.mode=value['mode']
                    if value['training']is not None:
                        self.training_pending=True;reply=self.action(value['training']['records'][0])
                    else:reply=self.ready()
                elif value['operation']=='held_person_query':
                    self.query=value['query'];self.held=self.query['held_person'];self.rows=list(self.query['records'])
                    if self.held==owner.fail_person:raise ValueError('generated worker failed; no empty predictions')
                    reply=self.action(self.rows[0])
                elif value['operation']=='observation':
                    observation=value['value']
                    if self.training_pending:
                        self.training_pending=False;reply=self.ready()
                    else:
                        current=self.rows.pop(0)
                        if self.mode=='frozen_program':events=[[0,1]]if observation['microvolts'][0][0]>0 else[]
                        else:
                            u.need('microvolts'not in observation and 'svg'not in observation,'no raw values/source in viewer response')
                            events=[]
                        self.answers.append({'recording_id':current['recording_id'],'events':events})
                        if self.rows:reply=self.action(self.rows[0])
                        else:
                            query_raw=json.dumps(self.query,sort_keys=True,separators=(',',':')).encode()
                            reply={'kind':'submit','submission':{'schema':'neural010-detection-submission-v1',
                                'query_sha256':sha(query_raw),'records':self.answers}}
                else:raise AssertionError('unexpected generated peer operation')
                raw=u.encoded({'schema':'neural010-service-response-v1','context_id':context,'role':role,'sequence':self.seq,
                    'request_sha256':desc['sha256'],'body':reply})
                io.budget.charge('read_bytes',len(raw)+1)
                return reply,raw,desc
        return Peer()

    def run(self,io,root='/generated-output/campaign'):
        return c.run(self.request_raw,self.authority_raw,u.pin(self.authority_raw),source_pin=self.source,
            source_root=HERE,output_root=root,io=io,signal_factory=GeneratedSignals,exchange_factory=self.exchange_factory)

    def score_arguments(self,io,receipt):
        req={'schema':'neural010-event-score-request-v1','source':self.source,'campaign':receipt,
            'campaign_request':{'path':'/generated-output/campaign/SELECTED_REQUEST.json',**u.pin(self.request_raw)},'limits':self.limits}
        raw=u.encoded(req)
        authority={'schema':'neural010-event-score-authority-v1','request':u.pin(raw),'campaign':receipt,'source':self.source,
            'evidence_class':'generated_control','assessment':{'path':'/generated/original/private/assessment.json',
                **u.pin(self.base.payloads['private/assessment.json'])}}
        return raw,u.encoded(authority)


class Campaign(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=Fixture();cls.io=cls.fixture.io();cls.receipt=cls.fixture.run(cls.io)

    def test_full686_operational_programme_peer_and_unchanged_score(self):
        f=self.fixture;io=self.io
        complete=u.parse(io.files[self.receipt['path']]);self.assertEqual(len(complete['folds']),23)
        self.assertEqual(len(io.signal_instance.calls),686+23)
        self.assertEqual(io.assessment_reads,0)
        for person in f.people:
            q=u.parse(io.files[f'/generated-output/campaign/{person}/QUERY.json'])
            s=u.parse(io.files[f'/generated-output/campaign/{person}/SUBMISSION.json'])
            self.assertEqual({r['recording_id']for r in q['records']},{r['recording_id']for r in s['records']})
            self.assertTrue(all(r['patient_id']==person for r in q['records']))
            self.assertTrue(any(r['events']==[]for r in s['records']))
        raw,authority=f.score_arguments(io,self.receipt)
        result=c.score(raw,authority,u.pin(authority),source_pin=f.source,source_root=HERE,
            output_root='/generated-output/score',io=io)
        answer=u.parse(io.files[result['path']]);self.assertEqual(io.assessment_reads,1)
        self.assertEqual(answer['campaign_route']['evidence_class'],'generated_control')
        self.assertFalse(answer['detection_interface']['qualified_provider_or_process_isolation'])
        self.assertFalse(answer['detection_interface']['independent_reference_matching_or_competence_established'])

    def test_missing_final_person_keeps_partial_and_never_freezes(self):
        f=Fixture();f.fail_person=f.people[-1];io=f.io()
        with self.assertRaisesRegex(ValueError,'worker failed'):f.run(io)
        self.assertFalse('/generated-output/campaign/CAMPAIGN.json'in io.files)
        self.assertFalse('/generated-output/campaign/FREEZE.json'in io.files)
        self.assertTrue('/generated-output/campaign/WHOLE_RUN_RESERVATION.json'in io.files)
        self.assertEqual(io.assessment_reads,0)

    def test_no_query_before_independent_state_freeze(self):
        f=Fixture();f.bad_freeze=True;io=f.io()
        with self.assertRaisesRegex(ValueError,'pre-query freeze'):f.run(io)
        self.assertFalse(any(p.endswith('/QUERY.json')for p in io.creates))
        self.assertEqual(io.assessment_reads,0)

    def test_viewer_loop_delivers_images_only_and_all686_explicit_empty_outputs(self):
        f=Fixture('typed_viewer');io=f.io();receipt=f.run(io)
        self.assertEqual(len(io.signal_instance.calls),686)
        self.assertFalse(any(r['role']=='authorized_current_fold_training'for r in io.accesses))
        self.assertEqual(sum(role=='renderer'for role,_,_ in f.transport_calls),686)
        complete=u.parse(io.files[receipt['path']]);self.assertEqual(complete['people'],23)
        candidate=u.parse(io.files['/generated-output/campaign/CANDIDATE.json'])
        self.assertEqual(len(candidate['records']),686)
        self.assertTrue(all(r['events']==[]for r in candidate['records']))
        self.assertEqual(io.assessment_reads,0)

    def test_fixed_gain_and_single_sample_marker(self):
        row={'channel_labels':['FP1-F7','FP1-F7']};req={'channels':[0,1],'start_sample':0,'stop_sample':1}
        a,pa=provider.svg_frame(row,req,[[1.,-1.]],100.)
        b,pb=provider.svg_frame(row,req,[[1000.,-1000.]],100.)
        self.assertEqual(pa,pb);self.assertEqual(a.count(b'<circle'),2)
        self.assertEqual(pa['vertical_half_range_microvolts'],100.)
        self.assertIn(b'cy="10.000000000"',b)
        self.assertNotIn(b'microvolts',a)

    def test_viewer_metadata_is_fixed_and_extreme_ratio_finite(self):
        policy={'max_samples_per_request':64,'max_channels_per_request':2,'frame_bytes':1048576,'display_half_range_microvolts':1e308}
        row={'duration_seconds':2,'signal_handle':'signal:'+'0'*24,'channel_labels':['FP1-F7']}
        req={'kind':'observe','signal_handle':row['signal_handle'],'start_sample':0,'stop_sample':1,'channels':[0]}
        class Signals:
            value=1.0
            def window(self,*args):return [[self.value]]
        class Display:
            def __init__(self):self.frames=[]
            def render(self,raw,render):
                self.frames.append(raw)
                return {'schema':'neural010-rendered-observation-v1','media_type':'image/png',
                    'image_handle':'image:'+sha(str(len(self.frames)).encode()),'render_sha256':sha(raw)}
        signal=Signals();display=Display();budget=u.Budget(self.fixture.limits)
        observations=provider.Observations(signal,policy,budget,display)
        a=observations.observe(req,{row['signal_handle']:row},'typed_viewer')
        signal.value=1e308
        b=observations.observe(req,{row['signal_handle']:row},'typed_viewer')
        self.assertEqual({k:v for k,v in a.items()if k!='image_handle'},{k:v for k,v in b.items()if k!='image_handle'})
        self.assertNotIn('render_sha256',a);self.assertNotIn('microvolts',a)
        self.assertNotEqual(display.frames[0],display.frames[1])
        self.assertNotIn(b'inf',display.frames[1]);self.assertNotIn(b'nan',display.frames[1])
        self.assertIn(b'<circle',display.frames[1])

    def test_source_bootstrap_imports_no_h5_or_numpy(self):
        spec=importlib.util.spec_from_file_location('generated_event_entry',HERE/'entry.py')
        entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
        manifest=u.pin((HERE/'SOURCE_MANIFEST.json').read_bytes())
        _,bodies,_,load,_,_=entry.bootstrap(manifest['bytes'],manifest['sha256'])
        actual=load('campaign');self.assertTrue(callable(actual.run)and callable(actual.score))
        self.assertEqual(bodies['vendor/detection-interface-v1/interface.py'],(HERE/'vendor/detection-interface-v1/interface.py').read_bytes())
        self.assertNotIn('h5py',sys.modules);self.assertNotIn('numpy',sys.modules)


if __name__=='__main__':unittest.main(verbosity=2)
