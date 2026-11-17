"""Generated controls only: never open authentic NPZs, labels or references."""
import argparse
import contextlib
import copy
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import tempfile
import time
import types
import unittest
from unittest.mock import patch
import zipfile
import zlib

HERE=Path(__file__).resolve().parent


def load(name,path):
    module=types.ModuleType(name)
    module.__file__=str(path)
    exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
    return module


V=load('generated_viewer',HERE/'viewer.py')
OriginalPacket=V.Packet


def decode_png(body):
    """Independent PNG chunk/CRC and unfiltered RGB decoder."""
    assert body[:8]==b'\x89PNG\r\n\x1a\n'
    offset=8
    chunks=[]
    while offset<len(body):
        size=struct.unpack('>I',body[offset:offset+4])[0]
        kind=body[offset+4:offset+8]
        payload=body[offset+8:offset+8+size]
        crc=struct.unpack('>I',body[offset+8+size:offset+12+size])[0]
        assert zlib.crc32(kind+payload)==crc
        chunks.append((kind,payload))
        offset+=12+size
    assert offset==len(body) and [k for k,_ in chunks]==[b'IHDR',b'IDAT',b'IEND']
    assert struct.unpack('>IIBBBBB',chunks[0][1])==(1400,820,8,2,0,0,0)
    raw=zlib.decompress(chunks[1][1])
    stride=1400*3+1
    assert len(raw)==stride*820 and all(raw[y*stride]==0 for y in range(820))
    return b''.join(raw[y*stride+1:(y+1)*stride] for y in range(820))


class ViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        cls.np=np
        cls.temporary=tempfile.TemporaryDirectory(prefix='neural034-generated-')
        cls.directory=Path(cls.temporary.name).resolve()
        cls.written=0
        cls.raster,cls.renderer,cls.inputs,cls.ids=V.dependencies()
        cls.arrays={'train_windows':np.zeros((120,300,12),dtype='<f8'),
                    'train_behavior':np.zeros((120,300),dtype='<f8'),
                    'train_labels':np.array([0,1]*60,dtype='i1'),
                    'query_windows':np.zeros((20,300,12),dtype='<f8'),
                    'query_behavior':np.zeros((20,300),dtype='<f8'),
                    'query_ids':np.array(cls.ids[0],dtype='<U24')}
        memory=io.BytesIO()
        np.savez(memory,**cls.arrays)
        cls.body=memory.getvalue()
        cls.packet_path=cls.directory/'generated-public.npz'
        cls.write(cls.packet_path,cls.body)
        cls.pin={'bytes':len(cls.body),'sha256':V.sha(cls.body)}
        cls.packet=V.Packet(cls.packet_path,0,cls.pin,cls.ids[0])

    @classmethod
    def write(cls,path,body):
        path.write_bytes(body)
        cls.written+=len(body)

    @classmethod
    def tearDownClass(cls):
        print(json.dumps({'generated_fixture_bytes_written':cls.written,
                          'authentic_payload_reads':0,'provider_calls':0}))
        cls.temporary.cleanup()

    def test_01_exact_generated_packet_and_source_bindings(self):
        self.assertEqual(len(self.body),4371604)
        self.assertEqual(len(self.ids),7)
        self.assertEqual(sum(map(len,self.ids.values())),140)
        for role,count in (('training',120),('query',20)):
            for i in range(count):
                observation=self.packet.observation(role,i)
                self.assertEqual(observation['windows'].shape,(300,12))
                self.assertEqual(observation['behavior'].shape,(300,))
                self.assertEqual('label' in observation,role=='training')
        with self.assertRaises(ValueError):
            V.Packet(self.packet_path,0,{**self.pin,'sha256':'0'*64},self.ids[0])
        with self.assertRaises(ValueError):
            V.Packet(self.packet_path,1,self.pin,self.ids[1])

    def test_02_packet_mutation_controls(self):
        for key,change in (
            ('query_windows',lambda a:a.__setitem__((19,299,11),float('nan'))),
            ('query_behavior',lambda a:a.__setitem__((19,299),2)),
            ('train_labels',lambda a:a.__setitem__(119,3)),
            ('query_ids',lambda a:a.__setitem__(19,a[0]))):
            values=dict(self.arrays)
            values[key]=values[key].copy()
            change(values[key])
            buffer=io.BytesIO()
            self.np.savez(buffer,**values)
            packet=object.__new__(V.Packet)
            with self.subTest(key=key),self.assertRaises(ValueError):
                packet._decode(buffer.getvalue(),self.ids[0])
        for values in ({**self.arrays,'query_windows':self.arrays['query_windows'][:19]},
                       {**self.arrays,'train_windows':self.arrays['train_windows'].astype('<f4')}):
            buffer=io.BytesIO();self.np.savez(buffer,**values)
            with self.assertRaises(ValueError):
                object.__new__(V.Packet)._decode(buffer.getvalue(),self.ids[0])
        duplicate=io.BytesIO(self.body)
        with zipfile.ZipFile(duplicate,'a') as archive:
            archive.writestr('unexpected.npy',b'extra')
        with self.assertRaises(ValueError):
            object.__new__(V.Packet)._decode(duplicate.getvalue(),self.ids[0])

    def test_03_png_lossless_pixels_and_all_trace_lanes(self):
        pixels=bytes((i%251 for i in range(1400*820*3)))
        self.assertEqual(decode_png(self.renderer.png(pixels)),pixels)
        record=self.packet.observation('query',0)
        start=time.monotonic()
        base,clipped=self.renderer.render(record,1.0,self.raster)
        self.assertEqual(clipped,[])
        baseline=decode_png(base)
        for cell in range(12):
            changed={**record,'windows':record['windows'].copy()}
            changed['windows'][100:200,cell]=1
            image,flags=self.renderer.render(changed,1.0,self.raster)
            self.assertEqual(flags,[])
            actual=decode_png(image)
            middle=153+cell*43
            lo,hi=(middle-16)*1400*3,(middle+17)*1400*3
            self.assertNotEqual(actual[lo:hi],baseline[lo:hi])
            self.assertEqual(actual[:lo],baseline[:lo])
            self.assertEqual(actual[hi:],baseline[hi:])
        changed={**record,'behavior':record['behavior'].copy()}
        changed['behavior'][100:200]=1
        image,_=self.renderer.render(changed,1.0,self.raster)
        actual=decode_png(image)
        self.assertEqual(actual[:680*1400*3],baseline[:680*1400*3])
        self.assertNotEqual(actual[680*1400*3:730*1400*3],baseline[680*1400*3:730*1400*3])
        self.assertEqual(actual[730*1400*3:],baseline[730*1400*3:])
        self.assertEqual(self.renderer.x_for(0),182)
        self.assertEqual(self.renderer.x_for(299),1298)
        print(json.dumps({'generated_render_profile':{'images':14,'wall_seconds':time.monotonic()-start,
              'constant_trace_png_bytes':len(base),'raw_rgb_bytes':len(baseline)},
              'scope':'Generated constant/step traces only; not a real-data compression estimate.'}))

    def test_04_clipping_and_gain_are_explicit(self):
        record=self.packet.observation('query',0)
        changed={**record,'windows':record['windows'].copy()}
        changed['windows'][0,0]=-1e308
        changed['windows'][1,0]=1e308
        changed['windows'][:,11]=3
        image,flags=self.renderer.render(changed,1.0,self.raster)
        self.assertEqual(flags,[1,12]);decode_png(image)
        _,flags=self.renderer.render(changed,2.0,self.raster)
        self.assertEqual(flags,[1])
        with self.assertRaises(ValueError):self.renderer.render(changed,True,self.raster)
        class Lines:
            def __init__(self):self.lines=[]
            def line(self,*args):self.lines.append(args)
        lines=Lines()
        self.renderer.segment(lines,0,-4,100,4,1,50)
        self.assertEqual(lines.lines,[(25,66,75,34,self.renderer.BLUE)])

    class FastRenderer:
        @staticmethod
        def render(record,gain,_raster):
            # Generated transport controls; authentic image correctness tested separately.
            return V.encode({'role':record['role'],'index':record['index'],'gain':gain,
                             'label':record.get('label'),'first':float(record['windows'][0][0])}),[]

    def new_session(self,max_actions=512):
        return V.Session(self.packet,max_actions,None,self.FastRenderer)

    def test_05_complete_training_access_and_query_projection(self):
        session=self.new_session()
        for index in range(120):
            response=session.handle({'action':'training','index':index})
            self.assertEqual(response['context_label'],index%2)
            self.assertNotIn('query_id',response)
        response=session.handle({'action':'query','index':19})
        self.assertEqual(response['query_id'],self.ids[0][19])
        self.assertEqual(set(response),{'kind','mode','role','index','gain_units_per_division',
             'clipped_cells','samples','cells','sample_rate_hz','window_seconds',
             'first_sample_seconds','last_sample_seconds','image','query_id'})
        self.assertEqual(set(response['image']),{'mime_type','base64'})

    def test_06_action_contract_rejects_missing_extra_foreign_and_late_answers(self):
        invalid=[{'action':'training','index':120},{'action':'query','index':True},
                 {'action':'query','index':0,'fold':1},{'action':'fold','index':1},
                 {'action':'gain','units_per_division':float('inf')},{'action':'finish'},
                 {'action':'respond','query_id':self.ids[0][0],'probability':.5}]
        for request in invalid:
            with self.subTest(request=request),self.assertRaises(ValueError):self.new_session().handle(request)
        for probability in (True,-.1,1.1,float('nan')):
            session=self.new_session();session.handle({'action':'inspect'})
            with self.assertRaises(ValueError):
                session.handle({'action':'respond','query_id':self.ids[0][0],'probability':probability})
        session=self.new_session();session.handle({'action':'inspect'})
        with self.assertRaises(ValueError):
            session.handle({'action':'respond','query_id':self.ids[1][0],'probability':.5})
        session=self.new_session();session.handle({'action':'inspect'})
        request={'action':'respond','query_id':self.ids[0][0],'probability':.5}
        session.handle(request)
        with self.assertRaises(ValueError):session.handle(request)
        session=self.new_session(41)
        for _ in range(41):session.handle({'action':'inspect'})
        with self.assertRaises(ValueError):session.handle({'action':'inspect'})

    def memory_packet(self,path,fold,pin,ids):
        self.assertEqual(str(path),f'generated-fold-{fold}')
        packet=object.__new__(OriginalPacket)
        packet.fold,packet.pin,packet.ids=fold,{'bytes':pin['bytes'],'sha256':pin['sha256']},list(ids)
        packet.arrays=self.arrays
        return packet

    def serve_generated(self,fold,directory,requests):
        args=argparse.Namespace(fold=fold,packet=f'generated-fold-{fold}',output=directory,max_actions=512)
        stdin=types.SimpleNamespace(buffer=io.BytesIO(b''.join(V.encode(r) for r in requests)))
        with patch.object(V,'Packet',self.memory_packet),patch.object(V,'dependencies',
                return_value=(None,self.FastRenderer,self.inputs,self.ids)),patch.object(V.sys,'stdin',stdin),\
                contextlib.redirect_stdout(io.StringIO()):
            try:V.serve(args)
            finally:
                if directory.exists():type(self).written+=sum(p.stat().st_size for p in directory.iterdir() if p.is_file())

    def requests(self,fold):
        rows=[]
        for index,query_id in enumerate(self.ids[fold]):
            rows.extend([{'action':'query','index':index},
                         {'action':'respond','query_id':query_id,'probability':.5}])
        return rows+[{'action':'finish'}]

    def test_07_complete_140_collection_and_unchanged_original_grader(self):
        sessions=[]
        for fold in range(7):
            directory=self.directory/f'complete-{fold}'
            self.serve_generated(fold,directory,self.requests(fold));sessions.append(directory)
        output=self.directory/'collected'
        args=argparse.Namespace(packets=[f'generated-fold-{f}' for f in range(7)],sessions=sessions,output=output)
        with patch.object(V,'Packet',self.memory_packet),patch.object(V,'dependencies',
                return_value=(None,self.FastRenderer,self.inputs,self.ids)):
            V.collect(args)
        type(self).written+=sum(p.stat().st_size for p in output.iterdir())
        submission=(output/'probabilities.json').read_bytes()
        rows=V.decode(submission)['probabilities']
        self.assertEqual([(r['fold'],r['query_id']) for r in rows],[(f,i) for f in range(7) for i in self.ids[f]])
        receipt=V.decode((output/'collection.json').read_bytes())
        self.assertFalse(receipt['scientific_qualification'])
        self.assertFalse(receipt['participant_reset_qualified'])
        self.grade_generated(submission)
        self.grade_generated(V.encode({'schema_version':1,'probabilities':rows[:-1]}),valid=False)
        args.sessions=list(reversed(sessions));args.output=self.directory/'swapped-folds'
        with patch.object(V,'Packet',self.memory_packet),patch.object(V,'dependencies',
                return_value=(None,self.FastRenderer,self.inputs,self.ids)),self.assertRaises(ValueError):
            V.collect(args)
        self.assertFalse((args.output/'probabilities.json').exists())

    def grade_generated(self,submission,valid=True):
        bindings=V.decode((HERE/'SOURCE_BINDINGS.json').read_bytes())
        grader=load('unchanged_generated_grader',V.ROOT/bindings['sources']['grader']['path'])
        root=self.directory/('grader-valid' if valid else 'grader-invalid');root.mkdir()
        panel=V.encode({'schema_version':1,'cases':[{'fold':f,'query_id':i} for f in range(7) for i in self.ids[f]]})
        targets=V.encode({'folds':[{'fold':f,'query_ids':self.ids[f],'query_labels':[0,1]*10} for f in range(7)]})
        references=V.encode({'summary':{f'generated_reference_{i}':{'balanced_accuracy':.5,'log_loss':math.log(2)} for i in range(6)}})
        blobs={'/public/cases.json':panel,'/submission/probabilities.json':submission,
               '/private/targets.json':targets,'/private/reference_grade.json':references}
        pins={p:{'bytes':len(b),'sha256':V.sha(b)} for p,b in blobs.items()}
        assets=V.encode({'public_panel':pins['/public/cases.json'],'private_targets':pins['/private/targets.json'],
                         'private_references':pins['/private/reference_grade.json']})
        blobs.update({'/source/operator_assets.json':assets,
                      '/source/invocation.json':V.encode({'submission':pins['/submission/probabilities.json']})})
        for path,body in blobs.items():
            dest=root/path.lstrip('/');dest.parent.mkdir(parents=True,exist_ok=True);self.write(dest,body)
        touched=[]
        original_read=grader.read_pinned
        def generated_read(path,pin):
            touched.append(path)
            return original_read(root/path.lstrip('/'),pin)
        grader.Path=lambda path:root/path.lstrip('/')
        grader.read_pinned=generated_read
        stdout=io.StringIO()
        with contextlib.redirect_stdout(stdout):status=grader.main()
        result=json.loads(stdout.getvalue())
        self.assertEqual(status,0 if valid else 2)
        if valid:
            self.assertEqual(len(result['per_mouse']),7)
            self.assertEqual(result['score']['balanced_accuracy'],.5)
            self.assertAlmostEqual(result['score']['log_loss'],math.log(2))
            self.assertEqual(len(result['signed_candidate_minus_reference']),6)
            for values in result['signed_candidate_minus_reference'].values():
                for value in values.values():self.assertAlmostEqual(value,0)
        else:
            self.assertFalse(result['private_targets_decoded'])
            self.assertFalse(any(p.startswith('/private/') for p in touched))

    def test_08_replay_rejects_journal_manifest_completion_failure_mutations(self):
        directory=self.directory/'mutations'
        self.serve_generated(0,directory,self.requests(0))
        packet=self.memory_packet('generated-fold-0',0,self.inputs['fold-00'],self.ids[0])
        original={name:(directory/name).read_bytes() for name in ('manifest.json','actions.jsonl','completion.json')}
        manifest=V.decode(original['manifest.json'])
        mutations=[]
        for field,value in (('mode','direct'),('fold',1),('runtime',{}),('source',{}),('query_ids',list(reversed(self.ids[0]))),('input',{})):
            mutations.append(('manifest.json',V.encode({**manifest,field:value})))
        lines=original['actions.jsonl'].splitlines(keepends=True)
        mutations.extend([('actions.jsonl',b''.join(lines[:-1])),('actions.jsonl',lines[1]+lines[0]+b''.join(lines[2:])),
                          ('completion.json',V.encode({'queries':19}))])
        late=V.decode(lines[-2]);late['request']['probability']=.9
        mutations.append(('actions.jsonl',b''.join(lines[:-2])+V.encode(late)+lines[-1]))
        for filename,body in mutations:
            self.write(directory/filename,body)
            with self.subTest(filename=filename),self.assertRaises(ValueError):V.replay(directory,packet,None,self.FastRenderer)
            self.write(directory/filename,original[filename])
        self.write(directory/'failure.json',b'{}\n')
        with self.assertRaises(ValueError):V.replay(directory,packet,None,self.FastRenderer)

    def test_09_failed_serve_preserves_eof_and_failed_request(self):
        for name,requests in (('eof',[]),('bad-action',[{'action':'fold','index':1}])):
            directory=self.directory/name
            with self.assertRaises(ValueError):self.serve_generated(0,directory,requests)
            failure=V.decode((directory/'failure.json').read_bytes())
            expected=b'' if not requests else V.encode(requests[0])
            self.assertEqual(failure['last_input_capture']['sha256'],V.sha(expected))
            self.assertEqual(failure['last_input_capture']['eof'],not requests)
            self.assertEqual(failure['successful_actions'],0)
            self.assertFalse((directory/'completion.json').exists())


if __name__=='__main__':unittest.main(verbosity=2)
