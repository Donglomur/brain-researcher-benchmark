"""One active-fold image-only viewer and complete original-format collection.

Trusted operator source. This is not a model provider or an OS sandbox.
Never give a participant the operator process, source/data filesystem or collector.
"""
import argparse
import base64
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys
import types
import zipfile
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
MODE='active_fold_calcium_behavior_viewer'
MAX_ACTIONS=4096
MAX_REQUEST=4096
FOLDS=tuple(range(7))
TRAIN,QUERIES,SAMPLES,CELLS=120,20,300,12
ARRAYS={'train_windows':((120,300,12),'<f8'), 'train_behavior':((120,300),'<f8'),
        'train_labels':((120,),'i1'), 'query_windows':((20,300,12),'<f8'),
        'query_behavior':((20,300),'<f8'), 'query_ids':((20,),'<U24')}


def need(ok,message):
    if not ok:
        raise ValueError(message)


def sha(body):return hashlib.sha256(body).hexdigest()


def encode(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def decode(body):
    def pairs(rows):
        result={}
        for k,v in rows:
            need(k not in result,'Duplicate JSON field')
            result[k]=v
        return result
    return json.loads(body,object_pairs_hook=pairs,
                      parse_constant=lambda _:need(False,'Nonfinite JSON'))


def plain(path):
    path=Path(path).absolute()
    need('..' not in path.parts and all(not p.is_symlink() for p in (path,*path.parents)),
         'Unlinked absolute path required')
    return path


def stamp(s):
    return s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink


def captured(path,cap,expected=None):
    path=plain(path)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=cap,
             'Bounded ordinary single-link file required')
        if expected is not None:
            need(before.st_size==expected['bytes'],'Exact source extent required')
        with os.fdopen(fd,'rb',closefd=False) as stream:
            body=stream.read(before.st_size+1)
        need(len(body)==before.st_size and stamp(before)==stamp(os.fstat(fd))==stamp(path.stat()),
             'File changed during capture')
        if expected is not None:need(sha(body)==expected['sha256'],'Pinned file checksum mismatch')
        return body
    finally:os.close(fd)


def write_new(path,body):
    with plain(path).open('xb') as stream:
        stream.write(body)
        stream.flush()


def module_from_body(name,body,path):
    module=types.ModuleType(name)
    module.__file__=str(path)
    exec(compile(body,str(path),'exec'),module.__dict__)
    return module


def dependencies():
    bindings=decode(captured(HERE/'SOURCE_BINDINGS.json',16384))
    bodies={}
    for role,entry in bindings['sources'].items():
        path=Path(entry['path'])
        need(not path.is_absolute() and '..' not in path.parts,'Relative repository source path required')
        bodies[role]=captured(ROOT/path,1000000,entry)
    need(set(bodies)=={'raster','inputs','cases','grader'},'Exact dependency source roles')
    raster=module_from_body('neural034_reviewed_raster',bodies['raster'],ROOT/bindings['sources']['raster']['path'])
    renderer=module_from_body('neural034_fold_render',captured(HERE/'render.py',100000),HERE/'render.py')
    manifest=decode(bodies['inputs'])
    rows={row['role']:row for row in manifest['files']}
    need(set(rows)=={f'fold-{i:02d}' for i in FOLDS}|{'public_panel','private_targets','private_references'},
         'Complete original external manifest')
    panel=decode(bodies['cases'])
    need(set(panel)=={'schema_version','cases'} and panel['schema_version']==1,'Original public panel')
    ids={fold:[] for fold in FOLDS}
    for row in panel['cases']:
        need(set(row)=={'fold','query_id'} and type(row['fold']) is int and row['fold'] in FOLDS
             and type(row['query_id']) is str and re.fullmatch('[0-9a-f]{24}',row['query_id']),
             'Exact public identity fields')
        ids[row['fold']].append(row['query_id'])
    need(len(panel['cases'])==140 and all(len(v)==len(set(v))==20 and v==sorted(v) for v in ids.values()),
         'Complete ordered seven-fold query roster')
    need(len(set(x for v in ids.values() for x in v))==140,'No shared query identity across folds')
    return raster,renderer,rows,ids


def source_identity():
    return {name:{'bytes':len(body),'sha256':sha(body)} for name in ('viewer.py','render.py','SOURCE_BINDINGS.json')
            for body in [captured(HERE/name,100000)]}


def runtime_identity():
    import numpy as np
    return {'python':sys.version.split()[0],'implementation':sys.implementation.name,
            'byte_order':sys.byteorder,'numpy':np.__version__,
            'zlib_compile':zlib.ZLIB_VERSION,'zlib_runtime':zlib.ZLIB_RUNTIME_VERSION}


class Packet:
    def __init__(self,path,fold,pin,query_ids):
        need(type(fold) is int and fold in FOLDS,'Exact active fold')
        self.fold=fold
        body=captured(path,4371604,pin)
        self.pin={'bytes':len(body),'sha256':sha(body)}
        self._decode(body,query_ids)

    def _decode(self,body,query_ids):
        import numpy as np
        arrays={}
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            members=archive.infolist()
            need(not archive.comment and len(members)==6 and
                 {r.filename for r in members}=={name+'.npy' for name in ARRAYS},'Exact six-array public fold')
            for name,(shape,dtype) in ARRAYS.items():
                item=archive.getinfo(name+'.npy')
                need(item.compress_type==zipfile.ZIP_STORED and item.file_size==item.compress_size
                     and not item.flag_bits&9 and not item.comment and not item.is_dir()
                     and stat.S_IFMT(item.external_attr>>16) in (0,stat.S_IFREG), 'Stored ordinary array member')
                with archive.open(item) as stream:
                    version=np.lib.format.read_magic(stream)
                    need(version in ((1,0),(2,0)),'Supported ordinary NPY header')
                    read=(np.lib.format.read_array_header_1_0 if version==(1,0) else np.lib.format.read_array_header_2_0)
                    got,fortran,actual=read(stream,max_header_size=4096)
                    need(got==shape and not fortran and actual==np.dtype(dtype)
                         and stream.tell()+math.prod(shape)*actual.itemsize==item.file_size,
                         'Original complete array dtype, shape and extent')
                with archive.open(item) as stream:
                    arrays[name]=np.lib.format.read_array(stream,allow_pickle=False,max_header_size=4096)
        need(arrays['query_ids'].tolist()==query_ids,'Active-fold ordered query identities differ')
        need(np.isin(arrays['train_labels'],(0,1)).all() and np.count_nonzero(arrays['train_labels'])==60,
             'Complete balanced active training labels')
        for role in ('train','query'):
            need(np.isfinite(arrays[role+'_windows']).all(),'Finite complete calcium observations')
            need(np.isin(arrays[role+'_behavior'],(0.,1.)).all(),'Complete binary behavior observations')
        self.arrays=arrays
        self.ids=list(query_ids)

    def observation(self,role,index):
        need(role in ('training','query') and type(index) is int and 0<=index<(TRAIN if role=='training' else QUERIES),
             'Observation outside current active fold')
        prefix='train' if role=='training' else 'query'
        result={'role':role,'index':index,'windows':self.arrays[prefix+'_windows'][index],
                'behavior':self.arrays[prefix+'_behavior'][index]}
        if role=='training':result['label']=int(self.arrays['train_labels'][index])
        return result


class Session:
    def __init__(self,packet,max_actions,raster,renderer):
        need(type(max_actions) is int and 41<=max_actions<=MAX_ACTIONS,'Bounded complete-fold action allocation')
        self.packet,self.max_actions,self.raster,self.renderer=packet,max_actions,raster,renderer
        self.actions=0
        self.role,self.index,self.gain='query',0,1.0
        self.seen=set()
        self.answers={}
        self.finished=False

    def handle(self,request):
        need(not self.finished and self.actions<self.max_actions,'Fold closed or action budget exhausted')
        self.actions+=1
        fields={'query':{'index'},'training':{'index'},'inspect':set(),'gain':{'units_per_division'},
                'respond':{'query_id','probability'},'finish':set()}
        need(type(request) is dict and type(request.get('action')) is str,'Typed viewer request')
        action=request['action']
        need(action in fields and set(request)==fields[action]|{'action'},'Unknown action or extra fields')
        if action in ('query','training'):
            index=request['index']
            need(type(index) is int and 0<=index<(TRAIN if action=='training' else QUERIES),'Index outside active fold')
            self.role,self.index=action,index
        elif action=='gain':
            gain=request['units_per_division']
            need(type(gain) in (int,float) and math.isfinite(gain) and 2**-20<=gain<=2**60,
                 'Finite declared-range display gain')
            self.gain=float(gain)
        elif action=='respond':
            need(self.role=='query' and self.index in self.seen,'Render the full current query before responding')
            query_id=self.packet.ids[self.index]
            need(request['query_id']==query_id and query_id not in self.answers,'Exact first final query response')
            probability=request['probability']
            need(type(probability) in (int,float) and math.isfinite(probability) and 0<=probability<=1,
                 'Finite probability in [0,1], not Boolean')
            self.answers[query_id]=float(probability)
            return {'kind':'response_accepted','query_id':query_id,'completed_queries':len(self.answers)}
        elif action=='finish':
            need(set(self.answers)==set(self.packet.ids),'Every active-fold query requires a response')
            self.finished=True
            return {'kind':'complete','queries':20}
        observation=self.packet.observation(self.role,self.index)
        image,clipped=self.renderer.render(observation,self.gain,self.raster)
        if self.role=='query':self.seen.add(self.index)
        response={'kind':'view','mode':MODE,'role':self.role,'index':self.index,
                  'gain_units_per_division':self.gain,'clipped_cells':clipped,
                  'samples':300,'cells':12,'sample_rate_hz':10,'window_seconds':30,
                  'first_sample_seconds':0.05,'last_sample_seconds':29.95,
                  'image':{'mime_type':'image/png','base64':base64.b64encode(image).decode('ascii')}}
        if self.role=='training':response['context_label']=observation['label']
        else:response['query_id']=self.packet.ids[self.index]
        return response


PROMPT=('Predict probability of context B (A=0, B=1) for all 20 active-fold queries. '
        'Use only this typed viewer. All 120 active-fold training windows and their labels are available. '
        'Each image shows all 300 samples of 12 selected author-processed calcium traces plus aligned binary behavior. '
        'Sample centers are 0.05..29.95 seconds at 10Hz within each 30-second window. '
        'No extra filtering, interpolation or normalization is applied. All cells share one display gain. '
        'Training/index, query/index, inspect, gain/units_per_division, respond/query_id/probability and finish '
        'are the only actions. Render a query before its first final response; responses cannot be replaced. '
        'No raw files, arbitrary code, query labels, other folds, saved answers, source identities or grader feedback '
        'are provided. Participant memory and writable state must start fresh for this fold and end when it closes. '
        'This is a historically exposed seven-mouse processed-data task. Behavior alone may predict context; '
        'behavior polarity, context/day order and whole-session preprocessing remain unresolved. '
        'This viewer is tool-mediated and does not establish neural contribution or causal memory.')


def fresh(path):
    path=plain(path)
    need(not os.path.lexists(path) and path.parent.is_dir() and not path.is_relative_to(ROOT),
         'Fresh external output directory required')
    path.mkdir(mode=0o700)
    return path


def serve(args):
    output=fresh(args.output)
    session=None
    chain=None
    captured_input=None
    successes=attempts=0
    try:
        raster,renderer,inputs,ids=dependencies()
        packet=Packet(args.packet,args.fold,inputs[f'fold-{args.fold:02d}'],ids[args.fold])
        session=Session(packet,args.max_actions,raster,renderer)
        manifest={'schema':'neural034-fold-viewer-session/v1','mode':MODE,'fold':args.fold,
                  'input':packet.pin,'query_ids':packet.ids,'max_actions':args.max_actions,
                  'source':source_identity(),'runtime':runtime_identity(),'prompt':PROMPT,
                  'participant_reset':'required_external_per_fold; not proven by this operator viewer'}
        write_new(output/'manifest.json',encode(manifest))
        chain=sha(encode(manifest))
        print(encode({'kind':'instructions','prompt':PROMPT,'training_windows':120,'query_windows':20,
                      'max_actions':args.max_actions}).decode(),end='',flush=True)
        with (output/'actions.jsonl').open('xb') as log:
            while not session.finished:
                captured_input=None
                captured_input=sys.stdin.buffer.readline(MAX_REQUEST+1)
                attempts+=1
                need(0<len(captured_input)<=MAX_REQUEST and captured_input.endswith(b'\n'),'Complete bounded request line')
                request=decode(captured_input)
                response=session.handle(request)
                row={'ordinal':session.actions,'previous':chain,'request':request,'response_sha256':sha(encode(response))}
                body=encode(row)
                log.write(body);log.flush()
                chain=sha(body)
                successes=session.actions
                print(encode(response).decode(),end='',flush=True)
        write_new(output/'completion.json',encode({'fold':args.fold,'mode':MODE,'queries':20,
                                                   'actions':session.actions,'last_sha256':chain}))
    except BaseException as error:
        failure={'schema':'neural034-fold-viewer-failure/v1','mode':MODE,'fold':args.fold,
                 'error_type':type(error).__name__,'error':str(error)[:1000],
                 'successful_actions':successes,'handled_action_attempts':session.actions if session else 0,
                 'input_events_observed':attempts,'last_success_chain':chain,
                 'last_input_capture':None if captured_input is None else {'bytes':len(captured_input),
                  'sha256':sha(captured_input),'base64':base64.b64encode(captured_input).decode('ascii'),
                  'possible_truncation':len(captured_input)==MAX_REQUEST+1 and not captured_input.endswith(b'\n'),
                  'eof':captured_input==b''}}
        try:write_new(output/'failure.json',encode(failure))
        except OSError:pass
        raise


def replay(directory,packet,raster,renderer):
    directory=plain(directory)
    need(not os.path.lexists(directory/'failure.json'),'Failed folds cannot be collected')
    manifest=decode(captured(directory/'manifest.json',65536))
    expected={'schema':'neural034-fold-viewer-session/v1','mode':MODE,'fold':packet.fold,
              'input':packet.pin,'query_ids':packet.ids,'max_actions':manifest.get('max_actions'),
              'source':source_identity(),'runtime':runtime_identity(),'prompt':PROMPT,
              'participant_reset':'required_external_per_fold; not proven by this operator viewer'}
    need(manifest==expected,'Exact fold/source/input/runtime/condition manifest required')
    session=Session(packet,manifest['max_actions'],raster,renderer)
    chain=sha(encode(manifest))
    body=captured(directory/'actions.jsonl',MAX_ACTIONS*(MAX_REQUEST+1024))
    need(body.endswith(b'\n'),'Complete action journal')
    for line in body.splitlines():
        need(0<len(line)<=MAX_REQUEST+1024,'Bounded journal entry')
        row=decode(line)
        need(set(row)=={'ordinal','previous','request','response_sha256'} and type(row['ordinal']) is int
             and row['ordinal']==session.actions+1 and row['previous']==chain,'Complete ordered action chain')
        response=session.handle(row['request'])
        need(row['response_sha256']==sha(encode(response)),'Observation or answer changed during replay')
        chain=sha(encode(row))
    need(session.finished,'Missing complete-fold finish')
    completion=decode(captured(directory/'completion.json',4096))
    need(completion=={'fold':packet.fold,'mode':MODE,'queries':20,'actions':session.actions,'last_sha256':chain},
         'Exact complete-fold receipt')
    return session.answers,{'actions':session.actions,'manifest_sha256':sha(encode(manifest)),
                            'actions_sha256':sha(body),'last_sha256':chain}


def collect(args):
    need(len(args.packets)==len(args.sessions)==7,'Seven complete fold packets and sessions required')
    output=fresh(args.output)
    raster,renderer,inputs,ids=dependencies()
    rows,receipts=[],{}
    for fold,packet_path,directory in zip(FOLDS,args.packets,args.sessions):
        packet=Packet(packet_path,fold,inputs[f'fold-{fold:02d}'],ids[fold])
        answers,receipts[str(fold)]=replay(directory,packet,raster,renderer)
        rows.extend({'fold':fold,'query_id':query_id,'probability':answers[query_id]} for query_id in ids[fold])
    need(len(rows)==140 and len({(r['fold'],r['query_id']) for r in rows})==140,'Full original140-case collection')
    body=encode({'schema_version':1,'probabilities':rows})
    need(len(body)<=100000,'Original complete probability-file extent')
    write_new(output/'probabilities.json',body)
    write_new(output/'collection.json',encode({'schema':'neural034-fold-viewer-collection/v1','mode':MODE,
              'folds':7,'queries':140,'submission':{'bytes':len(body),'sha256':sha(body)},
              'sessions':receipts,'source':source_identity(),'runtime':runtime_identity(),
              'scope':'Complete original-format public output after image/history replay; no targets or grader called.',
              'participant_reset_qualified':False,'provider_delivery_qualified':False,'scientific_qualification':False}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('serve')
    p.add_argument('--fold',type=int,choices=FOLDS,required=True)
    p.add_argument('--packet',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--max-actions',type=int,required=True)
    p=sub.add_parser('collect')
    p.add_argument('--packets',type=Path,nargs=7,required=True)
    p.add_argument('--sessions',type=Path,nargs=7,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='serve':serve(args)
    else:collect(args)


if __name__=='__main__':main()
