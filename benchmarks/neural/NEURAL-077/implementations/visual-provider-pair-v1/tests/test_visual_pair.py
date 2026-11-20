"""Generated construction controls; no original signals, providers or scientific fits."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
import types
import unittest
from unittest import mock
import zlib

HERE = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get('N077_IMPLEMENTATIONS_ROOT', str(HERE.parent)))
FIXTURE_BYTES = 0


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m


support=module('n077_visual_test_support',HERE/'support.py')
with mock.patch.dict(sys.modules,{'support':support}):
    arm=module('n077_visual_test_arm',HERE/'provider_arm.py')
codec=module('n077_visual_test_codec',HERE/'transfer_png.py')
protected=module('n077_visual_test_protected',HERE/'protected_compare.py')


def encode(value):return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()


def put(path,raw):
    global FIXTURE_BYTES
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);FIXTURE_BYTES+=len(raw)
    return support.pin(raw)


def png(scan=None,ihdr=None):
    scan=scan if scan is not None else (b'\0'+bytes([17,42,83])*1400)*820
    return codec.SIGNATURE+codec.chunk(b'IHDR',ihdr or codec.IHDR)+codec.chunk(b'IDAT',zlib.compress(scan,1))+codec.chunk(b'IEND',b'')


class CodecAndSource(unittest.TestCase):
    def test_lossless_exact_canvas_and_cross_codec_equivalence(self):
        raw=png();delivered,receipt=codec.encode_transport_image(raw)
        self.assertTrue(codec.verify_equivalence(raw,delivered,receipt))
        self.assertEqual(codec.scanlines(raw),codec.scanlines(delivered))
        self.assertEqual(receipt['dimensions'],[1400,820]);self.assertFalse(receipt['pixel_change'])
        foreign=dict(receipt,zlib_runtime_version='different-recorded-runtime')
        self.assertTrue(codec.verify_equivalence(raw,delivered,foreign))

    def test_malformed_image_extent_crc_trailing_and_pixel_change_rejected(self):
        original=png();delivered,receipt=codec.encode_transport_image(original)
        badcrc=bytearray(original);badcrc[-1]^=1
        for malformed in (bytes(badcrc),original+b'extra',original[:40],
                          png(ihdr=struct.pack('>IIBBBBB',1401,820,8,2,0,0,0)),
                          png(b'\0'*(codec.SCAN_BYTES+1)),png(b'\0'*(codec.SCAN_BYTES-1))):
            with self.subTest(extent=len(malformed)),self.assertRaises(ValueError):codec.scanlines(malformed)
        changed=png((b'\0'+bytes([18,42,83])*1400)*820)
        forged=dict(receipt,transfer=codec.pin(changed))
        with self.assertRaises(ValueError):codec.verify_equivalence(original,changed,forged)

    def test_additive_source_closure_loads_exact_originals(self):
        deps=support.load(ROOT)
        self.assertEqual(deps['operator'],support.identity(deps['s']))
        self.assertEqual(deps['original']['pair'].CONDITIONS,('legacy_waveform_no_tools','matched_waveform_programme'))
        self.assertEqual(support.CONDITIONS,('four_demo','matched_waveform_programme'))
        self.assertIn('transfer_png.py',deps['operator'])
        self.assertNotIn('provider_sender.py',deps['operator'])

    def test_grade_rejects_unbounded_wrong_hash_and_duplicate_request_before_source(self):
        with tempfile.TemporaryDirectory() as folder,mock.patch.object(support,'load') as load:
            path=Path(folder).resolve()/'request.json'
            for raw,sha in [(b'x'*65537,'0'*64),(b'{}','0'*64),
                            (b'{"implementations_root":"a","implementations_root":"b"}',None)]:
                put(path,raw)
                with self.assertRaises(ValueError):arm.grade(path,sha or support.pin(raw)['sha256'])
            load.assert_not_called()


class ArmAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.deps=support.load(ROOT)
        cls.original_write=staticmethod(cls.deps['s'].write)
        def counted(path,raw):
            global FIXTURE_BYTES
            result=cls.original_write(path,raw);FIXTURE_BYTES+=len(raw);return result
        cls.deps['s'].write=counted

    @classmethod
    def tearDownClass(cls):cls.deps['s'].write=cls.original_write

    def fixture(self,root):
        d=self.deps;s=d['s']
        limits=arm.budgets(d['transport'],10,2000,8388608,8388608,1048576,400*8388608,400*1048576)
        rows=[{'turns':1,'request_bytes':100,'response_bytes':80,'provider_response_ids':['resp_'+str(i)],
               'episode_id':f'{i:032x}','started_monotonic':100+2*i,'finished_monotonic':101+2*i,
               'usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2},'probability':0.5,
               'transport_end':support.pin(b't'),'client_end':support.pin(b'c')} for i in range(400)]
        data={'validator':types.SimpleNamespace(validate=lambda path,ids:None),'packet':{'invented':'fixture-only'},'rows':[{'trial_id':f'development-{1+i//200:03d}-{i:024x}'} for i in range(400)]}
        manifest={'schema':'neural077_visual_provider_campaign_v1','route':arm.ROUTE,'condition':'four_demo',
                  'queries':400,'demonstrations':4,'source':d['bindings'],'operator':d['operator'],
                  'packet':data['packet'],'model':'generated-only','max_output_tokens':10,'limits':limits,
                  'started_monotonic':100,'deadline':2100,'retry_policy':'none','local_participant_sandbox':None,
                  'participant_code_executed_locally':False,'remote_context_qualified':False,
                  'provider_capacity_qualified':False,'scientific_qualification':False}
        manifest_pin=put(root/'MANIFEST.json',encode(manifest))
        for kind in ('sessions','providers'):
            for i in range(400):(root/kind/f'{i:03d}').mkdir(parents=True)
        submission=put(root/'collection/submission.npz',b'invented_npz_capture')
        collection={'schema':'neural077_transport_collection_v1','queries':400,
                    'status':'complete_unscored_transport_collection','condition':'four_demo',
                    'submission_sha256':submission['sha256'],'scoring_performed':False,
                    'provider_qualification':'not_established'}
        cp=put(root/'collection/TRANSPORT_COMPLETE.json',encode(collection))
        record={'schema':arm.ARM,'status':'closed_unscored_visual_provider_arm','route':arm.ROUTE,'condition':'four_demo',
                'queries':400,'demonstrations':4,'source':d['bindings'],'operator':d['operator'],'manifest':manifest_pin,
                'episodes':[{k:r[k] for k in ('transport_end','client_end')} for r in rows],
                'totals':arm._sum(rows,limits),'collection':cp,'submission':submission,
                'local_participant_sandbox':None,'remote_context_qualified':False,'provider_capacity_qualified':False,
                'scientific_qualification':False,'private_target_reads':0,'scoring_performed':False}
        receipt=put(root/'ARM.json',encode(record))
        class Array:
            def __init__(self,x):self.x=x
            def tolist(self):return self.x
        class Archive:
            files=['trial_ids','target_probability']
            def __enter__(self):return self
            def __exit__(self,*unused):return False
            def __getitem__(self,key):return Array([r['trial_id'] for r in data['rows']]) if key=='trial_ids' else [0.5]*400
        fake=types.SimpleNamespace(load=lambda *a,**k:Archive(),asarray=lambda x,**k:x,array_equal=lambda a,b:a==b,float64=float)
        return data,rows,record,receipt,fake

    def test_full400_join_uses_every_first_final_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();data,rows,record,receipt,fake=self.fixture(root)
            with mock.patch.object(arm,'dataset_for',return_value=data),mock.patch.object(arm,'audit_episode',side_effect=rows) as audit,mock.patch.dict(sys.modules,{'numpy':fake}):
                result=arm.admit_arm(root,receipt,'invented-packet',self.deps)
            self.assertEqual(audit.call_count,400);self.assertEqual(result[1],record['submission'])
            self.assertEqual(self.deps['original']['pair'].CONDITIONS,('legacy_waveform_no_tools','matched_waveform_programme'))

    def test_mixed_mode_or_missing_query_refused_before_public_or_private_loading(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();data,rows,record,receipt,fake=self.fixture(root)
            wrong=copy.deepcopy(record);wrong['condition']='zero_shot';rp=put(root/'ARM.json',encode(wrong))
            with mock.patch.object(arm,'audit_episode') as audit,mock.patch.object(arm,'dataset_for',return_value=data):
                with self.assertRaises(ValueError):arm.admit_arm(root,rp,'invented',self.deps)
                put(root/'ARM.json',encode(record));(root/'sessions/399').rmdir()
                with self.assertRaises(ValueError):arm.admit_arm(root,receipt,'invented',self.deps)
                audit.assert_not_called()

    def test_changed_episode_chain_and_changed_first_final_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();data,rows,record,receipt,fake=self.fixture(root)
            bad=copy.deepcopy(rows);bad[17]['client_end']=support.pin(b'changed')
            with mock.patch.object(arm,'dataset_for',return_value=data),mock.patch.object(arm,'audit_episode',side_effect=bad):
                with self.assertRaises(ValueError):arm.admit_arm(root,receipt,'invented',self.deps)
            bad=copy.deepcopy(rows);bad[17]['probability']=0.9
            with mock.patch.object(arm,'dataset_for',return_value=data),mock.patch.object(arm,'audit_episode',side_effect=bad),mock.patch.dict(sys.modules,{'numpy':fake}):
                with self.assertRaises(ValueError):arm.admit_arm(root,receipt,'invented',self.deps)

    def test_malformed_public_archive_refused_before_array_materialization(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();data,rows,record,receipt,fake=self.fixture(root)
            data['validator']=types.SimpleNamespace(validate=mock.Mock(side_effect=ValueError('generated malformed ZIP')))
            fake.load=mock.Mock(side_effect=AssertionError('array allocation before validator'))
            with mock.patch.object(arm,'dataset_for',return_value=data),mock.patch.object(arm,'audit_episode',side_effect=rows),mock.patch.dict(sys.modules,{'numpy':fake}):
                with self.assertRaises(ValueError):arm.admit_arm(root,receipt,'invented',self.deps)
            fake.load.assert_not_called()

    def test_provider_ids_episode_identity_order_and_cumulative_limits(self):
        rows=[{'turns':1,'request_bytes':1,'response_bytes':1,'provider_response_ids':['resp_'+str(i)],
               'episode_id':str(i),'started_monotonic':2*i,'finished_monotonic':2*i+1,
               'usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2}} for i in range(400)]
        limits={'maximum_provider_requests':400,'max_campaign_request_bytes':400,'max_campaign_response_bytes':400}
        self.assertEqual(arm._sum(rows,limits)['turns'],400)
        for changed in ('provider_response_ids','episode_id','started_monotonic'):
            bad=copy.deepcopy(rows);bad[1][changed]=bad[0][changed]
            with self.subTest(changed=changed),self.assertRaises(ValueError):arm._sum(bad,limits)
        with self.assertRaises(ValueError):arm._sum(rows,dict(limits,max_campaign_request_bytes=399))
        with self.assertRaises(ValueError):arm._sum(rows[:-1],limits)


class SavedEpisodeAdmission(unittest.TestCase):
    """Actual new episode auditor, with old raster/transport replay injected.

    Real client+unchanged Sender produce all private HTTP custody via finite fake
    HTTP. Original renderer execution is deliberately not repeated. The original
    transport-audit result is the only injected qualification seam.
    """
    @classmethod
    def setUpClass(cls):
        cls.deps=support.load(ROOT)
        cls.helper=module('n077_generated_client_helpers',HERE/'tests/test_visual_client.py')
        cls.client=cls.helper.client
        cls.sender=cls.client.source(ROOT/'waveform-provider-v1/client.py',cls.client.ORIGINAL_SENDER)

    def fixture(self,root,*,campaign_remaining_seconds=999):
        global FIXTURE_BYTES
        d=self.deps;t=d['transport'];h=self.helper
        session=root/'session';provider=root/'provider';custody=provider/'custody'
        custody.mkdir(parents=True,mode=0o700)
        trial='development-001-'+'0'*24
        limits=arm.budgets(t,30,1000,8388608,8388608,1048576,400*8388608,400*1048576)
        start=time.monotonic()
        deadline=start+campaign_remaining_seconds
        manifest={'started_monotonic':deadline-limits['campaign_seconds'],'deadline':deadline,
                  'model':'generated-model','max_output_tokens':100,
                  'limits':limits,'operator':d['operator']}
        cfg=arm.configuration(d,trial,'generated-model',100,
                              min(start+limits['query_seconds'],manifest['deadline'])-2,limits)
        raw=d['s'].encode(cfg);put(provider/'CONFIG.json',raw)
        img1,img2=h.png(0),h.png(255)
        context=types.SimpleNamespace(query={'trial_id':trial},prompt=t.v.scientific_prompt(trial,'four_demo'))
        first=t.ready_header(context,t.Limits(**limits['transport']),'a'*32)
        first['initial']=h.rendered(img1,remaining=127)
        select=h.bridge.encode({'action':'select','record':'demo1'})
        answer=h.bridge.encode({'trial_id':trial,'target_probability':0.5})
        final=h.bridge.encode({'action':'finalize','response':answer.decode()})
        terminal={'status':'valid_unscored','response_sha256':support.pin(answer)['sha256'],'terminal':True}
        frames=[t.wire(first,img1),t.wire(h.rendered(img2,'demo1'),img2),t.wire(terminal)]
        http=h.HTTP([h.provider(select),h.provider(final,'resp_generated_2')]);output=io.BytesIO()
        fd=os.open(custody,os.O_RDONLY|os.O_DIRECTORY)
        try:
            ok=self.client.serve(cfg,support.pin(raw),'SYNTHETIC_CREDENTIAL_7',fd,self.sender,h.bridge,codec,h.Alarm(),
                                 io.BytesIO(b''.join(frames)),output,http_factory=http)
        finally:os.close(fd)
        FIXTURE_BYTES+=sum(q.stat().st_size for q in custody.rglob('*') if q.is_file())
        self.assertTrue(ok)
        actions=[t.PREFIX.pack(len(x),0)+x for x in (select,final)]
        for i,frame in enumerate((frames[0],actions[0],frames[1],actions[1],frames[2])):
            name=f'{i:04d}-'+('out' if i%2==0 else 'in')+'.bin'
            put(session/'transport'/name,frame)
        transport_manifest=t.boundary_manifest(t.Limits(**limits['transport']),'protocol_only',HERE/'visual_client.py','a'*32,None)
        put(session/'transport/MANIFEST.json',h.bridge.encode(transport_manifest))
        end={'messages':5}
        end_pin=put(session/'transport/END.json',h.bridge.encode(end))
        put(session/'response.txt',answer)
        put(provider/'OPERATOR_END.json',encode({'started_monotonic':start,'finished_monotonic':time.monotonic(),
                                              'config':support.pin(raw),'transport_end':end_pin}))
        data={'rows':[{'trial_id':trial}],'parser':d['original']['parser']}
        return session,provider,data,manifest,end

    def test_actual_multi_turn_custody_reconstruction(self):
        with tempfile.TemporaryDirectory() as folder:
            session,provider,data,manifest,end=self.fixture(Path(folder).resolve())
            with mock.patch.object(self.deps['transport'],'audit_transport',return_value=end):
                result=arm.audit_episode(session,provider,data,0,self.deps,manifest)
            self.assertEqual(result['turns'],2);self.assertEqual(result['probability'],0.5)
            self.assertEqual(result['provider_response_ids'],['resp_generated_1','resp_generated_2'])

    def test_query_clock_rounding_boundary_and_closure_refusals(self):
        start = float.fromhex('0x1.0000000000005p+1')
        for remaining in (999, 20):
            with self.subTest(campaign_remaining_seconds=remaining), tempfile.TemporaryDirectory() as folder:
                with mock.patch.object(time, 'monotonic', return_value=start):
                    session, provider, data, manifest, end = self.fixture(
                        Path(folder).resolve(), campaign_remaining_seconds=remaining)
                config_path = provider / 'CONFIG.json'
                closure_path = provider / 'OPERATOR_END.json'
                original_config = config_path.read_bytes()
                original_closure = closure_path.read_bytes()
                config = json.loads(original_config)
                closure = json.loads(original_closure)
                self.assertEqual(config['deadline'],
                                 min(start + manifest['limits']['query_seconds'], manifest['deadline']) - 2)
                if remaining == 999:
                    # Different rounding at 30 and 32 makes the former shortcut invalid.
                    self.assertEqual(config['deadline'], 30.0)
                    self.assertNotEqual(start + 28, config['deadline'])
                else:
                    self.assertEqual(config['deadline'], manifest['deadline'] - 2)
                    self.assertLess(config['deadline'], start + 28)
                with mock.patch.object(self.deps['transport'], 'audit_transport', return_value=end):
                    result = arm.audit_episode(session, provider, data, 0, self.deps, manifest)
                self.assertEqual(result['turns'], 2)
                self.assertEqual(result['probability'], 0.5)
                if remaining != 999:
                    continue
                wrong_config = encode(dict(config, deadline=start + 28))
                wrong_config_closure = encode(dict(closure, config=support.pin(wrong_config)))
                wrong_transport = dict(closure['transport_end'], sha256='0' * 64)
                changes = (
                    ('rounded_shortcut', wrong_config, wrong_config_closure),
                    ('late_closure', original_config, encode(dict(closure, finished_monotonic=start + 31))),
                    ('changed_transport_end', original_config, encode(dict(closure, transport_end=wrong_transport))),
                )
                for reason, config_body, closure_body in changes:
                    with self.subTest(reason=reason):
                        try:
                            put(config_path, config_body)
                            put(closure_path, closure_body)
                            with mock.patch.object(self.deps['transport'], 'audit_transport', return_value=end):
                                with self.assertRaisesRegex(ValueError, 'Query clock/closure mismatch'):
                                    arm.audit_episode(session, provider, data, 0, self.deps, manifest)
                        finally:
                            put(config_path, original_config)
                            put(closure_path, original_closure)

    def test_tampered_history_image_final_and_http_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            session,provider,data,manifest,end=self.fixture(Path(folder).resolve())
            paths=[provider/'custody/001/REQUEST.bin',provider/'custody/000/BRIDGE.json',session/'response.txt',
                   provider/'custody/001/HTTP.json']
            originals=[p.read_bytes() for p in paths]
            changed=[h for h in originals]
            request=self.helper.bridge.decode(originals[0]);request['input']=request['input'][-1:]
            changed[0]=self.helper.bridge.encode(request)
            binding=self.helper.bridge.decode(originals[1]);binding['image_mapping']['scanlines']['sha256']='0'*64
            changed[1]=self.helper.bridge.encode(binding)
            changed[2]=b'{"trial_id":"wrong","target_probability":0.5}'
            http=self.helper.bridge.decode(originals[3]);http['requests_attempted']=2
            changed[3]=self.helper.bridge.encode(http)
            for path,body,original in zip(paths,changed,originals):
                with self.subTest(path=path.name):
                    put(path,body)
                    with mock.patch.object(self.deps['transport'],'audit_transport',return_value=end),self.assertRaises(ValueError):
                        arm.audit_episode(session,provider,data,0,self.deps,manifest)
                    put(path,original)


class ProtectedAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_write=staticmethod(ArmAdmission.deps['s'].write)
        def counted(path,raw):
            global FIXTURE_BYTES
            result=cls.original_write(path,raw);FIXTURE_BYTES+=len(raw);return result
        ArmAdmission.deps['s'].write=counted

    @classmethod
    def tearDownClass(cls):ArmAdmission.deps['s'].write=cls.original_write

    def test_each_public_validation_precedes_private_locations(self):
        # Actual protected loader entry; numpy is not reached while validation rejects.
        for failure_index in (0,1):
            with self.subTest(failure_index=failure_index),tempfile.TemporaryDirectory() as folder:
                root=Path(folder).resolve();a=root/'a';b=root/'b';ap=put(a,b'public-a');bp=put(b,b'public-b');seen=[]
                def read(path,cap=1048576,expected=None):
                    if str(path)=='private-locations':self.fail('Private locations opened before both public validations')
                    raw=Path(path).read_bytes();return raw
                def write(path,raw):return put(path,raw)
                def validate(path,ids):
                    seen.append(str(path))
                    if len(seen)-1==failure_index:raise ValueError('generated invalid public submission')
                fakepair=types.SimpleNamespace(need=support.need,read=read,write=write,decode=lambda raw:json.loads(raw),module=None,
                                              HERE=root,CASES=('development-001','development-002'),bundle=None)
                comparator=types.SimpleNamespace(canonical=lambda path:(types.SimpleNamespace(validate=validate),None))
                acc={'temporary_submission_bytes_created':0,'both_public_validated_before_private':False}
                with mock.patch.dict(sys.modules,{'numpy':types.ModuleType('numpy')}),self.assertRaises(ValueError):
                    protected.protected_compare(fakepair,comparator,{},((a,ap,{}),(b,bp,{})),{},'private-locations',acc,support.CONDITIONS)
                self.assertEqual(len(seen),failure_index+1);self.assertFalse(acc['both_public_validated_before_private'])

    def test_bad_programme_arm_stops_before_protected_compare(self):
        deps=copy.copy(ArmAdmission.deps);deps['original']=dict(deps['original'])
        fakepair=types.SimpleNamespace(_admit_arm=mock.Mock(side_effect=ValueError('changed programme')),
                                      operator_identity=lambda:{},public_roster=mock.Mock())
        deps['original']['pair']=fakepair
        protector=mock.Mock();deps['protected']=types.SimpleNamespace(protected_compare=protector)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();request={'schema':'neural077_visual_provider_pair_request_v1','implementations_root':'invented',
                 'operator':deps['operator'],'source':deps['bindings'],'output':str(root/'grade'),
                 'a':{'root':'a','receipt':{}},'b':{},'packet':'packet','delivery_root':'delivery','private_locations':'never-read'}
            path=root/'request.json';raw=encode(request);put(path,raw)
            with mock.patch.object(support,'load',return_value=deps),mock.patch.object(arm,'admit_arm',return_value=('a',{},{})):
                with self.assertRaises(ValueError):arm.grade(path,support.pin(raw)['sha256'])
            protector.assert_not_called();self.assertTrue((root/'grade/FAILED.json').exists())

    def test_visual_condition_supplied_before_scoring_without_numerical_global_mutation(self):
        deps=copy.copy(ArmAdmission.deps);deps['original']=dict(deps['original'])
        original_conditions=deps['original']['pair'].CONDITIONS
        fakepair=types.SimpleNamespace(_admit_arm=lambda *a:('b',{},{}),operator_identity=lambda:{},public_roster=lambda *a:{})
        deps['original']['pair']=fakepair;seen=[]
        def compare(*args):seen.append(args[-1]);return {'status':'paired_scored'}
        deps['protected']=types.SimpleNamespace(protected_compare=compare)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();request={'schema':'neural077_visual_provider_pair_request_v1','implementations_root':'invented',
                 'operator':deps['operator'],'source':deps['bindings'],'output':str(root/'grade'),
                 'a':{'root':'a','receipt':{}},'b':{},'packet':'packet','delivery_root':'delivery','private_locations':'never-read'}
            path=root/'request.json';raw=encode(request);put(path,raw)
            with mock.patch.object(support,'load',return_value=deps),mock.patch.object(arm,'admit_arm',return_value=('a',{},{})):
                result=arm.grade(path,support.pin(raw)['sha256'])
            self.assertTrue(result['paired_scores_computed']);self.assertEqual(seen,[('four_demo','matched_waveform_programme')])
            self.assertEqual(original_conditions,('legacy_waveform_no_tools','matched_waveform_programme'))


def tearDownModule():
    print('N077_VISUAL_PAIR_GENERATED_FIXTURE_BYTES='+str(FIXTURE_BYTES))


if __name__=='__main__':unittest.main()
