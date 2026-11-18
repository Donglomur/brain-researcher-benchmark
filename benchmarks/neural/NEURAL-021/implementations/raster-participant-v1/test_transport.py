"""Generated raster-wire controls; genuine source sessions, no OS participants.

White/noise PNG renderer overrides are explicitly labelled transport fixtures.
They are never evidence of image content. Real-image controls are separate.
The full 729-view real-raster schedule is selectable after a parent timing check.
"""
import base64
import hashlib
import io
import json
from pathlib import Path
import random
import struct
import sys
import types
import unittest
from unittest import mock
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import raster_transport as rt
import fixed_response_client as client

HERE=Path(__file__).resolve().parent
IMPLEMENTATIONS=HERE.parent
BASE_TRANSPORT=HERE.parent/'participant-transport-v1/transport.py'


def packet_fixture(delivery):
    counts=tuple(tuple(100*b+u for u in range(65)) for b in range(35))
    history=delivery.expand_counts(counts)
    conditions=[0]*52+[1]*40
    cases={'schema':'neural021_public_cases_v1','task_id':'NEURAL-021','time_bins':30,
        'feature_shape':[30,6,65],'units':'m/s','conditions':{'0':'active','1':'passive'},
        'queries':[{'trial_id':'q%04d'%i,'condition':delivery.CONDITIONS[c]} for i,c in enumerate(conditions)]}
    train={'spike_counts':[history]*272,'condition':[0,1]*136,
           'velocity_m_s':[[[j/10,-j/20] for j in range(30)]]*272}
    query={'spike_counts':[history]*92,'condition':conditions}
    return delivery.Packet.from_arrays(train,query,delivery.encode(cases))


def schedule(mode,all_calibration=True):
    result=[]
    def add(op,**fields):
        result.append({'seq':len(result),'op':op,**fields})
    if all_calibration:
        for index in range(272):add('calibration',index=index)
    for i in range(92):
        key='q%04d'%i
        add('view',trial_id=key)
        if i == 0 and mode == 'typed_viewer':
            add('crop',trial_id=key,unit_start=0,unit_stop=5,bin_start=0,bin_stop=6)
        add('answer',trial_id=key,velocity_m_s=[[0.0,0.0] for _ in range(30)])
    add('finish')
    return result


def png_fixture(width,height,noise=False):
    # Generated codec fixture, not a rendered scientific observation.
    pixels=random.Random(72).randbytes(width*height) if noise else bytes([255])*(width*height)
    scan=b''.join(b'\0'+pixels[y*width:(y+1)*width] for y in range(height))
    def chunk(kind,body):
        return struct.pack('!I',len(body))+kind+body+struct.pack('!I',zlib.crc32(kind+body)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',width,height,8,0,0,0,0))
    png+=chunk(b'IDAT',zlib.compress(scan,6))+chunk(b'IEND',b'')
    return png,hashlib.sha256(pixels).hexdigest()


class GeneratedRenderer:
    """Explicit image-content stub used only for message/session coverage."""
    def __init__(self,noise=False):
        self.cache={};self.noise=noise
    def __call__(self,svg):
        width,height=rt.source_dimensions(svg)
        if (width,height) not in self.cache:
            self.cache[width,height]=png_fixture(width,height,self.noise)
        png,pixel_hash=self.cache[width,height]
        return {'png':png,'width':width,'height':height,'pixels_sha256':pixel_hash,
                'svg_sha256':hashlib.sha256(svg.encode()).hexdigest(),
                'profile':{'kind':'generated-noise-wire-fixture' if self.noise else 'generated-white-wire-fixture',
                           'scientific_image_content':False}}


class MemoryChannel:
    def __init__(self,requests):
        self.incoming=io.BytesIO(b''.join(struct.pack('!I',len(rt.encode(x)))+rt.encode(x) for x in requests))
        self.responses=[];self.total_sent=0;self.image_count=0
        self.last_image=None
    def read_exact(self,size):return self.incoming.read(size)
    def write(self,wire):
        size=struct.unpack('!I',wire[:4])[0]
        if size != len(wire)-4:raise AssertionError('bad response frame extent')
        body=wire[4:];value=json.loads(body)
        self.responses.append(rt.pin(body));self.total_sent+=len(wire)
        if value.get('type') == 'image':
            if set(value) != {'seq','type','media_type','png_base64','width','height'}:
                raise AssertionError('non-image metadata leak')
            client.decode_observation(value)
            self.image_count+=1;self.last_image=value
    def close_success(self):
        return {'leader_exit_code':0,'stdout_eof':True,'stderr_eof':True,
                'owned_process_group_absent':True,'group_id':987654321,
                'stderr':rt.pin(b''),'scope':'Generated closure only; no process was launched.'}


class Common:
    @classmethod
    def setUpClass(cls):
        cls.renderer_pin=rt.pin((HERE/'raster.py').read_bytes())
        cls.baseline=rt.make_runtime(renderer_pin=cls.renderer_pin,base_transport_path=BASE_TRANSPORT,
                                    renderer_override=GeneratedRenderer())
        cls.grade,cls.sources=cls.baseline.load_sources(IMPLEMENTATIONS)
        cls.packet=packet_fixture(cls.sources['delivery'])
    def runtime(self,render=None):
        return rt.make_runtime(renderer_pin=self.renderer_pin,base_transport_path=BASE_TRANSPORT,
                               renderer_override=render or GeneratedRenderer())
    def exchange(self,mode='direct_observation',render=None):
        return self.runtime(render).Exchange(self.sources,self.packet,mode)


class RasterTransportTests(Common,unittest.TestCase):
    def test_full_generated_two_mode_schedule_original_replay_and_png_wire(self):
        submissions=[]
        for mode in ('direct_observation','typed_viewer'):
            exchange=self.exchange(mode);channel=MemoryChannel(schedule(mode))
            transcript=exchange.run(channel)
            source_submission,source_receipt=exchange.pending
            replay=self.grade.replay(self.sources,self.packet,mode,source_submission,source_receipt)
            self.assertEqual(replay['queries'],92)
            self.assertEqual(replay['distinct_calibration_trials_viewed'],272)
            self.assertEqual(channel.image_count,364+(mode=='typed_viewer'))
            self.assertEqual(transcript['messages'],457+(mode=='typed_viewer'))
            self.assertEqual(channel.responses[0],transcript['hello'])
            self.assertEqual(channel.responses[1:],[row['response'] for row in transcript['frames']])
            self.assertEqual(channel.total_sent,transcript['response_wire_bytes'])
            self.assertTrue(transcript['generated_renderer_override_used'])
            self.assertEqual(len(transcript['raster_observations']),channel.image_count)
            visual=json.loads(source_receipt)
            for row in transcript['raster_observations']:
                event=visual['events'][row['source_event_sequence']]
                self.assertEqual(event['svg_sha256'],row['source_svg']['sha256'])
                self.assertIn(event['operation'],('training_view','query_view'))
            previous='0'*64
            for row in transcript['frames']:
                self.assertEqual(row['previous_sha256'],previous)
                self.assertEqual(row['sha256'],rt.pin(rt.encode({k:v for k,v in row.items() if k!='sha256'}))['sha256'])
                previous=row['sha256']
            self.assertLess(len(rt.encode(transcript)),rt.MAX_TRANSCRIPT)
            submissions.append(source_submission)
        self.assertEqual(*submissions)

    def test_png_only_response_and_hello_do_not_expose_source_or_arrays(self):
        ex=self.exchange();hello=json.loads(ex.hello())
        self.assertEqual(hello['schema'],rt.SCHEMA)
        self.assertEqual(hello['max_response_bytes'],22*1024**2)
        self.assertEqual(hello['max_png_bytes'],15406963)
        self.assertIn('actual image input',hello['image_channel_requirement'])
        self.assertFalse(hello['raster_display_qualified'])
        value=json.loads(ex.dispatch(rt.encode({'seq':0,'op':'calibration','index':271})))
        self.assertEqual(set(value),{'seq','type','media_type','png_base64','width','height'})
        self.assertEqual((value['width'],value['height']),(1710,2420))
        png=client.decode_observation(value)
        self.assertTrue(png.startswith(b'\x89PNG'))
        # Base64 text is arbitrary; only metadata can carry a semantic text leak.
        metadata=rt.encode({k:v for k,v in value.items() if k!='png_base64'}).decode()
        for token in ('svg','spike_counts','training_velocity','/Users/','source_svg'):
            self.assertNotIn(token,metadata)
        self.assertNotIn('renderer_profile',value)
        image_part=client.image_content_block(value)
        self.assertEqual(image_part,{'type':'image','mimeType':'image/png','data':value['png_base64']})
        self.assertEqual(base64.b64decode(image_part['data']),png)

    def test_crop_boundaries_modes_and_first_final_answers_preserved(self):
        crop={'seq':0,'op':'crop','trial_id':'q0000','unit_start':64,'unit_stop':65,'bin_start':34,'bin_stop':35}
        for mode in ('direct_observation','typed_viewer'):
            with self.assertRaises(ValueError):self.exchange(mode).dispatch(rt.encode(crop))
        ex=self.exchange('typed_viewer')
        ex.dispatch(rt.encode({'seq':0,'op':'view','trial_id':'q0000'}))
        response=json.loads(ex.dispatch(rt.encode({**crop,'seq':1})))
        self.assertEqual((response['width'],response['height']),(1300,302))
        ex.dispatch(rt.encode({'seq':2,'op':'answer','trial_id':'q0000','velocity_m_s':[[0,0]]*30}))
        with self.assertRaises(ValueError):
            ex.dispatch(rt.encode({'seq':3,'op':'answer','trial_id':'q0000','velocity_m_s':[[1,1]]*30}))
        self.assertTrue(ex.failed);self.assertIsNone(ex.pending)
        partial=self.exchange();partial.dispatch(rt.encode({'seq':0,'op':'view','trial_id':'q0000'}))
        partial.dispatch(rt.encode({'seq':1,'op':'answer','trial_id':'q0000','velocity_m_s':[[0,0]]*30}))
        with self.assertRaises(ValueError):partial.dispatch(rt.encode({'seq':2,'op':'finish'}))
        self.assertIsNone(partial.pending)

    def test_renderer_failure_permanently_seals_advanced_source_session(self):
        for error in (ValueError,KeyboardInterrupt,SystemExit):
            def fail(_,error=error):raise error('generated renderer interruption; no real signal')
            ex=self.exchange(render=fail)
            with self.subTest(error=error.__name__),self.assertRaises(error):
                ex.dispatch(rt.encode({'seq':0,'op':'view','trial_id':'q0000'}))
            self.assertTrue(ex.failed);self.assertTrue(ex.finished);self.assertIsNone(ex.pending)
            with self.assertRaises(ValueError):ex.dispatch(rt.encode({'seq':1,'op':'view','trial_id':'q0001'}))
            with self.assertRaises(ValueError):ex.run(MemoryChannel([]))

    def test_generated_override_cannot_fake_small_dimensions_or_source_binding(self):
        for kind in ('tiny','svg_hash','pixel_hash'):
            real=GeneratedRenderer()
            def wrong(svg,kind=kind):
                row=real(svg)
                if kind=='tiny':row['png'],row['pixels_sha256']=png_fixture(1,1)
                elif kind=='svg_hash':row['svg_sha256']='0'*64
                else:row['pixels_sha256']='0'*64
                return row
            ex=self.exchange(render=wrong)
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                ex.dispatch(rt.encode({'seq':0,'op':'view','trial_id':'q0000'}))
            self.assertTrue(ex.failed)

    def test_actual_png_frame_can_exceed_legacy_svg_cap_without_lineage_lie(self):
        ex=self.exchange(render=GeneratedRenderer(noise=True))
        raw=ex.dispatch(rt.encode({'seq':0,'op':'view','trial_id':'q0000'}))
        self.assertGreater(len(raw),512*1024)
        self.assertLess(len(raw),rt.MAX_RESPONSE)
        self.assertEqual(ex.rows[0]['response'],rt.pin(raw))
        self.assertEqual(len(client.decode_observation(json.loads(raw))),ex.raster_rows[0]['png']['bytes'])

    def test_response_budget_and_profile_limits_fail_closed(self):
        runtime=self.runtime();runtime.MAX_RESPONSE=100
        ex=runtime.Exchange(self.sources,self.packet,'direct_observation')
        with self.assertRaises(ValueError):ex.dispatch(rt.encode({'seq':0,'op':'view','trial_id':'q0000'}))
        self.assertTrue(ex.failed)
        renderer=GeneratedRenderer()
        def oversized(svg):
            value=renderer(svg);value['profile']={'unbounded':'x'*8192};return value
        ex=self.exchange(render=oversized)
        with self.assertRaises(ValueError):ex.dispatch(rt.encode({'seq':0,'op':'view','trial_id':'q0000'}))
        self.assertTrue(ex.failed)
        runtime=self.runtime();runtime.MAX_SENT=1
        ex=runtime.Exchange(self.sources,self.packet,'direct_observation')
        with self.assertRaises(ValueError):ex.run(MemoryChannel([{'seq':0,'op':'view','trial_id':'q0000'}]))
        self.assertIsNone(ex.pending)

    def test_renderer_profile_change_is_refused(self):
        count=[0];renderer=GeneratedRenderer()
        def changing(svg):
            value=renderer(svg);count[0]+=1;value['profile']['counter']=count[0];return value
        ex=self.exchange(render=changing)
        ex.dispatch(rt.encode({'seq':0,'op':'view','trial_id':'q0000'}))
        with self.assertRaises(ValueError):ex.dispatch(rt.encode({'seq':1,'op':'view','trial_id':'q0001'}))
        self.assertTrue(ex.failed)

    def test_client_rejects_svg_tables_metadata_and_noncanonical_png(self):
        ex=self.exchange();good=json.loads(ex.dispatch(rt.encode({'seq':0,'op':'view','trial_id':'q0000'})))
        for extra in ({'svg':'<svg/>'},{'spike_counts':[]},{'training_velocity':[]}):
            with self.assertRaises(ValueError):client.decode_observation({**good,**extra})
        for change in ({'type':'svg'},{'media_type':'image/svg+xml'},{'seq':False},{'width':False},
                       {'png_base64':good['png_base64']+'\n'},{'png_base64':base64.b64encode(b'<svg/>').decode()}):
            with self.assertRaises(ValueError):client.decode_observation({**good,**change})
        png=base64.b64decode(good['png_base64']);kind=b'tEXt';text=b'source\0<svg/>'
        chunk=struct.pack('!I',len(text))+kind+text+struct.pack('!I',zlib.crc32(kind+text)&0xffffffff)
        with self.assertRaises(ValueError):
            client.decode_observation({**good,'png_base64':base64.b64encode(png[:-12]+chunk+png[-12:]).decode()})

    def test_source_pin_mismatch_refused_before_renderer_execution(self):
        with self.assertRaises(ValueError):
            rt.make_runtime(renderer_pin={'bytes':self.renderer_pin['bytes'],'sha256':'0'*64},
                            base_transport_path=BASE_TRANSPORT)
        with mock.patch.object(rt,'BASE_PIN',{'bytes':1,'sha256':'0'*64}),self.assertRaises(ValueError):
            rt.make_runtime(renderer_pin=self.renderer_pin,base_transport_path=BASE_TRANSPORT)

        supplied=dict(self.renderer_pin)
        runtime=rt.make_runtime(renderer_pin=supplied,base_transport_path=BASE_TRANSPORT,
                                renderer_override=GeneratedRenderer())
        supplied['sha256']='f'*64;supplied['bytes']=1
        ex=runtime.Exchange(self.sources,self.packet,'direct_observation')
        ex.dispatch(rt.encode({'seq':0,'op':'view','trial_id':'q0000'}))
        self.assertEqual(ex.renderer_profile['renderer_source'],self.renderer_pin)
        self.assertEqual(runtime.raster_adapter['renderer'],self.renderer_pin)

    def test_wrapped_receipt_preserves_source_outputs_and_explicit_stub_label(self):
        runtime=self.runtime();channel=MemoryChannel(schedule('direct_observation',False))
        process=mock.Mock(pid=987654321,returncode=0)
        events=[]
        with mock.patch.object(runtime.subprocess,'Popen',return_value=process), \
             mock.patch.object(runtime,'PipeChannel',return_value=channel), \
             mock.patch.object(runtime,'cleanup',return_value={'leader_reaped':True,'owned_process_group_absent':True}):
            result=runtime.run_participant(self.grade,self.sources,self.packet,'direct_observation',
                ['/generated/participant'],str(HERE),60,observer=events.append)
        receipt=json.loads(result[3]);replay=json.loads(result[2])
        self.assertEqual(receipt['schema'],'neural021_raster_participant_transport_receipt_v1')
        self.assertTrue(receipt['generated_renderer_override_used'])
        self.assertEqual(receipt['submission'],rt.pin(result[0]))
        self.assertEqual(receipt['visual_receipt'],rt.pin(result[1]))
        self.assertEqual(replay['queries'],92)
        self.assertFalse(receipt['runtime_qualified']);self.assertFalse(receipt['raster_display_qualified'])
        self.assertFalse(receipt['admission']['artifacts_alone_admissible'])
        self.assertEqual([r['phase'] for r in events],['before_spawn','spawned','owned_participant_closed','replay_complete','cleanup_observed'])

    def test_real_renderer_single_complete_query_has_png_only_wire(self):
        runtime=rt.make_runtime(renderer_pin=self.renderer_pin,base_transport_path=BASE_TRANSPORT)
        ex=runtime.Exchange(self.sources,self.packet,'direct_observation')
        value=json.loads(ex.dispatch(rt.encode({'seq':0,'op':'view','trial_id':'q0091'})))
        png=client.decode_observation(value)
        self.assertGreater(len(png),100)
        self.assertEqual((value['width'],value['height']),(1710,1710))
        self.assertFalse(ex.renderer_profile['generated_renderer_override_used'])
        self.assertEqual(ex.raster_rows[0]['source_svg']['sha256'],ex.session._events[0]['svg_sha256'])


class FullRasterScheduleTests(Common,unittest.TestCase):
    def test_full_actual_raster_generated_two_mode_schedule(self):
        # Deliberately selectable: 729 actual renders, not a routine test rerun.
        submissions=[]
        for mode in ('direct_observation','typed_viewer'):
            runtime=rt.make_runtime(renderer_pin=self.renderer_pin,base_transport_path=BASE_TRANSPORT)
            ex=runtime.Exchange(self.sources,self.packet,mode);channel=MemoryChannel(schedule(mode))
            transcript=ex.run(channel)
            replay=self.grade.replay(self.sources,self.packet,mode,*ex.pending)
            self.assertEqual((replay['queries'],replay['distinct_calibration_trials_viewed']),(92,272))
            self.assertEqual(channel.image_count,364+(mode=='typed_viewer'))
            self.assertFalse(transcript['generated_renderer_override_used'])
            self.assertEqual(channel.responses[1:],[row['response'] for row in transcript['frames']])
            self.assertEqual(channel.total_sent,transcript['response_wire_bytes'])
            submissions.append(ex.pending[0])
        self.assertEqual(*submissions)


if __name__ == '__main__':
    args=[]
    for arg in sys.argv[1:]:
        if arg.startswith('--implementations-root='):IMPLEMENTATIONS=Path(arg.split('=',1)[1])
        elif arg.startswith('--base-transport='):BASE_TRANSPORT=Path(arg.split('=',1)[1])
        elif arg.startswith('--site-packages='):sys.path.insert(0,arg.split('=',1)[1])
        else:args.append(arg)
    sys.argv[1:]=args
    unittest.main(verbosity=2)
