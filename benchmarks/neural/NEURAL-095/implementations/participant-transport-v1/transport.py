"""View-scoped DMFC participant transport and operator-owned closed-pair admission."""
from __future__ import annotations
import argparse
import base64
from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import selectors
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time
import uuid

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
VIEWER=HERE.parent/'count-viewer-v1'
PREFIX=struct.Struct('!II')
MAX_REQUEST=16384
HEADER_MAX=32768
PNG_MAX=4*1024**2
CLIENT_MAX=256*1024
JOURNAL_MAX=64*1024**2

def need(ok,message):
    if not ok:raise ValueError(message)

def encode(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def decode(body):
    def pairs(rows):
        result={}
        for key,value in rows:
            need(key not in result,'Duplicate JSON key');result[key]=value
        return result
    return json.loads(body,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'Nonfinite JSON'))

def digest(body):return hashlib.sha256(body).hexdigest()
def pin(body):return {'bytes':len(body),'sha256':digest(body)}

def unlinked(path):
    path=Path(path).absolute()
    need('..' not in path.parts and all(not p.is_symlink() for p in (path,*path.parents)),'Unlinked ordinary path required')
    return path

def identity(info):
    return tuple(getattr(info,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink'))

def ordinary(path,cap):
    path=unlinked(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    stream=os.fdopen(fd,'rb')
    try:
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<=before.st_size<=cap,'Bounded single-link ordinary file required')
        return stream,before
    except BaseException:stream.close();raise

def read(path,cap):
    stream,before=ordinary(path,cap)
    with stream:
        body=stream.read(cap+1)
        need(len(body)==before.st_size and identity(before)==identity(os.fstat(stream.fileno()))==identity(Path(path).stat()),
             'Input changed during capture')
    return body

def save(path,body):
    with unlinked(path).open('xb') as f:f.write(body);f.flush();os.fsync(f.fileno())
    Path(path).chmod(0o400)

def load_viewer():
    bindings=decode(read(HERE/'SOURCE_BINDINGS.json',65536))
    need(set(bindings)=={'schema','members'} and bindings['schema']=='neural095-participant-transport-dependencies/v1'
         and set(bindings['members'])=={'viewer.py','SOURCE.json'},'Exact original viewer closure required')
    bodies={}
    for name,expected in bindings['members'].items():
        body=read(VIEWER/name,256*1024)
        need(pin(body)==expected,'Changed original viewer/source manifest');bodies[name]=body
    spec=importlib.util.spec_from_loader('neural095_transport_viewer',loader=None)
    module=importlib.util.module_from_spec(spec);module.__file__=str(VIEWER/'viewer.py')
    sys.modules[spec.name]=module
    exec(compile(bodies['viewer.py'],module.__file__,'exec'),module.__dict__)
    return module

v=load_viewer()

def source_identity():return {name:pin(read(HERE/name,256*1024)) for name in ('transport.py','SOURCE_BINDINGS.json')}

@dataclass(frozen=True)
class Limits:
    max_actions:int
    max_images:int
    max_output_bytes:int
    wall_seconds:float
    def validate(self):
        need(type(self.max_actions) is int and 1265<=self.max_actions<=v.MAX_ACTIONS+1,
             'Action budget must permit all offered training/query observations and answers')
        need(type(self.max_images) is int and 1006<=self.max_images<self.max_actions,'Image budget must permit every offered case')
        need(type(self.max_output_bytes) is int and PNG_MAX+HEADER_MAX+4096<=self.max_output_bytes<=4*1024**3,
             'Explicit finite wire budget required')
        need(type(self.wall_seconds) in (int,float) and math.isfinite(self.wall_seconds) and 0<self.wall_seconds<=86400,
             'Finite positive per-view deadline required')

class WireFailure(Exception):
    def __init__(self,reason,captured=b''):self.reason=reason;self.captured=captured;super().__init__(reason)

class OwnerInterrupted(BaseException):pass

def wire(header,image=b''):
    body=encode(header)
    need(0<len(body)<=HEADER_MAX and len(image)<=PNG_MAX,'Frame capacity exceeded')
    return PREFIX.pack(len(body),len(image))+body+image

def unpack(body,inbound=False):
    need(len(body)>=8,'Missing frame prefix');hs,ps=PREFIX.unpack(body[:8])
    need(0<hs<=(MAX_REQUEST if inbound else HEADER_MAX) and (ps==0 if inbound else 0<=ps<=PNG_MAX)
         and len(body)==8+hs+ps,'Invalid complete frame lengths')
    return decode(body[8:8+hs]),body[8+hs:]

def wait_fd(fd,event,deadline):
    remaining=deadline-time.monotonic()
    if remaining<=0:raise WireFailure('deadline')
    with selectors.DefaultSelector() as selector:
        selector.register(fd,event)
        if not selector.select(remaining):raise WireFailure('deadline')

def read_frame(fd,deadline):
    result=bytearray()
    def take(size):
        while len(result)<size:
            try:
                wait_fd(fd,selectors.EVENT_READ,deadline);part=os.read(fd,size-len(result))
            except BlockingIOError:continue
            except WireFailure as exc:raise WireFailure(exc.reason,bytes(result)) from None
            if not part:raise WireFailure('request_eof',bytes(result))
            result.extend(part)
    take(8);hs,ps=PREFIX.unpack(result)
    if not 0<hs<=MAX_REQUEST or ps:raise WireFailure('request_length',bytes(result))
    take(8+hs);return bytes(result)

def write_frame(fd,body,deadline):
    sent=0
    try:
        while sent<len(body):
            wait_fd(fd,selectors.EVENT_WRITE,deadline)
            try:
                count=os.write(fd,body[sent:])
                if not count:raise WireFailure('response_not_delivered')
                sent+=count
            except BlockingIOError:continue
    except (OSError,WireFailure):raise WireFailure('response_not_delivered',body[:sent]) from None

def ready_header(packet,limits,episode):
    original=packet.header()
    keys=('condition','view','train_n','query_n','unit_ids','query_ids','question','instructions',
          'query_feedback','full_query_browsing','query_preprocessing_fit_allowed')
    return {'kind':'instructions','episode_id':episode,**{k:original[k] for k in keys},
      'actions':{'show_train':{'index':'0..747'},'show_query':{'index':'0..257'},
                 'answer':{'case_id':'next viewed original query','prediction_ms':'finite scalar'},'finish':{}},
      'limits':asdict(limits),'image_transport':'PNG bytes in the binary image frame, not a text description.',
      'context_scope':'State persists within this view. New process and context for the other view; no prior answers or feedback.'}

def projection(response):
    if set(response)=={'observation','image_png_base64'}:
        image=base64.b64decode(response['image_png_base64'],validate=True)
        need(image.startswith(b'\x89PNG\r\n\x1a\n') and len(image)<=PNG_MAX,'Bounded PNG image required')
        need(pin(image)==response['observation']['image'],'Viewer image commitment mismatch')
        return {'kind':'observation','observation':response['observation']},image
    need(set(response)=={'accepted','answered'},'Exact original answer acknowledgment required')
    return {'kind':'accepted',**response},b''

def terminal_header(packet):return {'kind':'complete','view':packet.view,'answers':258}

def sandbox_profile(client):
    need(sys.platform=='darwin' and Path('/usr/bin/sandbox-exec').is_file(),'macOS sandbox-exec required')
    quoted=json.dumps(str(unlinked(client)))
    return ('(version 1) (deny default) (deny sysctl* process-info* network* process-fork) '
      '(allow process-info* (target self)) (allow process-exec) (allow file-read-metadata) '
      '(allow sysctl-read (sysctl-name "kern.ostype") (sysctl-name "kern.osrelease") '
      '(sysctl-name "kern.version") (sysctl-name "kern.hostname") (sysctl-name "hw.machine")) '
      '(allow file-read-data (literal "/") (subpath "/System") (subpath "/usr") '
      '(subpath "/Library/Frameworks") (literal "/dev/null") (literal "/dev/urandom") '
      '(literal "/dev/random") (literal '+quoted+'))')

class Journal:
    def __init__(self,path):
        path.mkdir(mode=0o700);self.raw=(path/'wire.bin').open('xb');self.log=(path/'journal.jsonl').open('xb')
        self.sequence=0;self.offset=0;self.previous='0'*64
    def record(self,direction,body,complete=True):
        self.raw.write(body);self.raw.flush()
        row={'sequence':self.sequence,'direction':direction,'offset':self.offset,'bytes':len(body),
             'sha256':digest(body),'complete':complete,'previous':self.previous}
        line=encode(row);self.log.write(line);self.log.flush()
        self.sequence+=1;self.offset+=len(body);self.previous=digest(line)
    def close(self):self.raw.close();self.log.close()

def run_view(packet,output,client,python=sys.executable,sandbox='macos',limits=None):
    need(isinstance(limits,Limits),'Explicit frozen limits required');limits.validate()
    need(packet.view in v.VIEWS and len(packet.ids)==258 and packet.header()['train_n']==748,'Complete original view required')
    need(sandbox in ('macos','protocol_only'),'Unknown sandbox')
    body=read(client,CLIENT_MAX);need(bool(body),'Empty client')
    python=Path(python).resolve(strict=True);need(python.is_file() and os.access(python,os.X_OK),'Existing executable interpreter required')
    if sandbox=='macos':need(any(python.is_relative_to(Path(p)) for p in ('/System','/usr','/Library/Frameworks')),
                             'Interpreter outside sandbox runtime roots')
    output=unlinked(output);output.mkdir(mode=0o700)
    captured=output/'client.py';save(captured,body)
    episode=uuid.uuid4().hex;profile=sandbox_profile(captured) if sandbox=='macos' else None
    boundary={'schema':'neural095-participant-view/v1','view':packet.view,'mode':v.MODE,'episode_id':episode,
      'limits':asdict(limits),'sandbox':sandbox,'client':pin(body),'python':str(python),'source':source_identity(),
      'profile':pin(profile.encode()) if profile else None,'fresh_process_per_view':True,
      'stateful_within_view':True,'provider_context_qualified':False,'scientific_qualification':False}
    save(output/'BOUNDARY.json',encode(boundary))
    if profile:save(output/'sandbox.sb',profile.encode())
    journal=Journal(output/'transport');history=(output/'viewer-history.jsonl').open('xb')
    session=v.Session(packet);child=None;reason=None;forced=False;group=None;finished=False;completion=None
    images=outbound=actions=history_bytes=0;started=time.monotonic();deadline=started+limits.wall_seconds
    def persist(row):
        nonlocal history_bytes
        raw=v.encoded(row)
        need(len(raw)<=v.MAX_LINE and history_bytes+len(raw)<=v.MAX_HISTORY,'Original journal bounds exceeded')
        history.write(raw);history.flush();os.fsync(history.fileno());history_bytes+=len(raw)
    def send(header,png=b''):
        nonlocal images,outbound
        frame=wire(header,png);need(outbound+len(frame)<=limits.max_output_bytes,'Output budget exceeded')
        try:write_frame(child.stdin.fileno(),frame,deadline)
        except WireFailure as exc:journal.record('out',exc.captured,False);raise
        journal.record('out',frame);outbound+=len(frame);images+=bool(png)
    try:
        persist(packet.header())
        with tempfile.TemporaryDirectory(prefix='neural095-view-') as cwd:
            command=[str(python),'-I','-S','-B',str(captured)]
            if profile:command=['/usr/bin/sandbox-exec','-p',profile,*command]
            stops={signal.SIGTERM,signal.SIGHUP,signal.SIGINT}
            previous=signal.pthread_sigmask(signal.SIG_BLOCK,stops)
            try:
                child=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                       cwd=cwd,env={'LANG':'C','LC_ALL':'C'},close_fds=True,start_new_session=True,
                       preexec_fn=lambda:signal.pthread_sigmask(signal.SIG_SETMASK,previous))
                save(output/'ACTIVE_CHILD.json',encode({'schema':'neural095-owned-child/v1','episode_id':episode,
                     'view':packet.view,'pid':child.pid,'pgid':child.pid,'parent_pid':os.getpid(),
                     'command':command,'source':source_identity()}))
            finally:signal.pthread_sigmask(signal.SIG_SETMASK,previous)
            os.set_blocking(child.stdin.fileno(),False);os.set_blocking(child.stdout.fileno(),False)
            send(ready_header(packet,limits,episode))
            while not finished:
                need(actions<limits.max_actions,'Action budget exhausted')
                try:raw=read_frame(child.stdout.fileno(),deadline)
                except WireFailure as exc:journal.record('in',exc.captured,False);raise
                journal.record('in',raw);action,_=unpack(raw,True)
                if action=={'op':'finish'}:
                    completion=session.finish();finished=True;send(terminal_header(packet))
                else:
                    if type(action) is dict and action.get('op') in ('show_train','show_query'):
                        need(images<limits.max_images and outbound+PNG_MAX+HEADER_MAX+4096<=limits.max_output_bytes,
                             'Next image exceeds frozen budget')
                    event,response=session.step(action)
                    # Session mutates its answer in memory; persist/fsync must
                    # finish before ACK. Any durability failure ends the owner.
                    persist(event);send(*projection(response))
                actions+=1
            child.stdin.close()
            remaining=min(2.,deadline-time.monotonic());need(remaining>0,'Deadline before clean exit')
            try:child.wait(timeout=remaining)
            except subprocess.TimeoutExpired:raise WireFailure('client_did_not_exit') from None
            need(child.returncode==0,'Client failed after finish')
    except BaseException as exc:
        reason=exc.reason if isinstance(exc,WireFailure) else type(exc).__name__
    finally:
        if child is not None:
            forced=child.poll() is None
            try:
                os.killpg(child.pid,signal.SIGKILL);group='signalled';reason=reason or 'owned_group_remained'
            except ProcessLookupError:group='absent'
            except OSError:group='unverified';reason=reason or 'cleanup_unverified'
            try:child.wait(timeout=2)
            except subprocess.TimeoutExpired:reason='cleanup_unverified';group='unverified'
            for stream in (child.stdin,child.stdout):
                if stream and not stream.closed:stream.close()
        if child is not None:
            try:
                save(output/'CLOSED_CHILD.json',encode({'schema':'neural095-owned-child-end/v1','episode_id':episode,
                  'view':packet.view,'pid':child.pid,'exit_code':child.returncode,'forced_stop':forced,
                  'process_group_cleanup':group,'descendant_absence_verified':False}))
            except BaseException as exc:reason=reason or type(exc).__name__
        if reason is None and finished and completion is not None:
            try:persist(completion)
            except BaseException as exc:reason=type(exc).__name__
        history.close();journal.close()
    if reason is not None:save(output/'FAILED.json',encode({'status':'failed','reason':reason,'view':packet.view}))
    result={'schema':'neural095-participant-view-end/v1','status':'complete_unscored' if reason is None else 'failed',
      'view':packet.view,'episode_id':episode,'actions':actions,'images':images,'output_bytes':outbound,
      'wire_bytes':journal.offset,'wire_records':journal.sequence,'last_sha256':journal.previous,
      'history':pin(read(output/'viewer-history.jsonl',v.MAX_HISTORY)),
      'client_pid':child.pid if child else None,'client_exit_code':child.returncode if child else None,
      'forced_stop':forced,'process_group_cleanup':group,'descendant_absence_verified':False,
      'wall_seconds':time.monotonic()-started,'reason':reason,
      'provider_context_qualified':False,'scientific_qualification':False}
    save(output/'RESULT.json',encode(result));return result

def audit_view(path,packet):
    path=unlinked(path)
    need(not (path/'FAILED.json').exists(),'Failed participant view cannot be collected')
    boundary=decode(read(path/'BOUNDARY.json',65536));limits=Limits(**boundary['limits']);limits.validate()
    expected_boundary={'schema':'neural095-participant-view/v1','view':packet.view,'mode':v.MODE,
      'episode_id':boundary['episode_id'],'limits':asdict(limits),'sandbox':boundary['sandbox'],
      'client':pin(read(path/'client.py',CLIENT_MAX)),'python':boundary['python'],'source':source_identity(),
      'profile':boundary['profile'],'fresh_process_per_view':True,'stateful_within_view':True,
      'provider_context_qualified':False,'scientific_qualification':False}
    need(boundary==expected_boundary and boundary['fresh_process_per_view'] is True and boundary['stateful_within_view'] is True
         and boundary['provider_context_qualified'] is False and boundary['scientific_qualification'] is False
         and type(boundary['episode_id']) is str and len(boundary['episode_id'])==32
         and all(c in '0123456789abcdef' for c in boundary['episode_id']),'Exact source/view boundary required')
    need(boundary['sandbox'] in ('macos','protocol_only'),'Unknown sandbox record')
    profile=sandbox_profile(path/'client.py') if boundary['sandbox']=='macos' else None
    need(boundary['profile']==(pin(profile.encode()) if profile else None),'Profile identity mismatch')
    if profile:need(read(path/'sandbox.sb',65536)==profile.encode(),'Profile changed')
    else:need(not (path/'sandbox.sb').exists(),'Unexpected profile')
    need({p.name for p in path.iterdir()}=={'BOUNDARY.json','client.py','viewer-history.jsonl','transport','RESULT.json',
                                          'ACTIVE_CHILD.json','CLOSED_CHILD.json'}
         |({'sandbox.sb'} if profile else set()),'Unexpected or missing participant evidence')
    need({p.name for p in (path/'transport').iterdir()}=={'wire.bin','journal.jsonl'},'Unexpected wire evidence')
    history_body=read(path/'viewer-history.jsonl',v.MAX_HISTORY)
    lines=history_body.splitlines(keepends=True)
    need(lines and all(line.endswith(b'\n') and len(line)<=v.MAX_LINE for line in lines)
         and decode(lines[0])==packet.header(),'Original complete history header required')
    session=v.Session(packet);finished=False;history_index=1;pending=None
    streams=[]
    try:
        raw,raw_before=ordinary(path/'transport/wire.bin',limits.max_output_bytes+limits.max_actions*(MAX_REQUEST+8));streams.append(raw)
        log,log_before=ordinary(path/'transport/journal.jsonl',JOURNAL_MAX);streams.append(log)
        sequence=offset=images=outbound=actions=0;previous='0'*64
        while line:=log.readline(4097):
            need(len(line)<=4096 and line.endswith(b'\n'),'Bounded complete wire journal row required')
            row=decode(line);direction='out' if sequence%2==0 else 'in'
            need(set(row)=={'sequence','direction','offset','bytes','sha256','complete','previous'}
                 and type(row['sequence']) is int and row['sequence']==sequence and row['direction']==direction
                 and type(row['offset']) is int and row['offset']==offset and row['previous']==previous
                 and row['complete'] is True and type(row['bytes']) is int
                 and 8<row['bytes']<=8+HEADER_MAX+PNG_MAX,'Invalid or incomplete transport row')
            frame=raw.read(row['bytes']);need(pin(frame)=={'bytes':row['bytes'],'sha256':row['sha256']},'Wire capture changed')
            header,png=unpack(frame,direction=='in')
            if sequence==0:need(frame==wire(ready_header(packet,limits,boundary['episode_id'])),'Participant header changed')
            elif direction=='in':
                need(not finished and actions<limits.max_actions,'Action after finish or beyond budget');pending=header
            else:
                need(pending is not None and history_index<len(lines),'Missing original action/history')
                if pending=={'op':'finish'}:
                    event=session.finish();expected=wire(terminal_header(packet));finished=True
                else:
                    if type(pending) is dict and pending.get('op') in ('show_train','show_query'):
                        need(images<limits.max_images and outbound+PNG_MAX+HEADER_MAX+4096<=limits.max_output_bytes,
                             'Recorded image exceeded frozen budget')
                    event,response=session.step(pending);expected=wire(*projection(response))
                need(decode(lines[history_index])==event and frame==expected,'History/action/image/response mismatch')
                pending=None;history_index+=1;actions+=1
            if direction=='out':outbound+=len(frame);images+=bool(png)
            need(outbound<=limits.max_output_bytes,'Recorded output exceeded budget')
            offset+=len(frame);previous=digest(encode(row));sequence+=1
            need(sequence<=2*limits.max_actions+1,'Too many wire rows')
        need(raw.read(1)==b'' and finished and pending is None and history_index==len(lines),
             'Incomplete history or trailing wire data')
        for stream,before,file in ((raw,raw_before,path/'transport/wire.bin'),(log,log_before,path/'transport/journal.jsonl')):
            need(identity(before)==identity(os.fstat(stream.fileno()))==identity(file.stat()),'Evidence changed during replay')
    finally:
        for stream in streams:stream.close()
    result=decode(read(path/'RESULT.json',16384))
    active=decode(read(path/'ACTIVE_CHILD.json',65536));closed=decode(read(path/'CLOSED_CHILD.json',16384))
    command=[boundary['python'],'-I','-S','-B',str(path/'client.py')]
    if profile:command=['/usr/bin/sandbox-exec','-p',profile,*command]
    need(active=={'schema':'neural095-owned-child/v1','episode_id':boundary['episode_id'],'view':packet.view,
                  'pid':result['client_pid'],'pgid':result['client_pid'],'parent_pid':active.get('parent_pid'),
                  'command':command,'source':source_identity()}
         and type(active['parent_pid']) is int and active['parent_pid']>0,'Owned child identity changed')
    need(closed=={'schema':'neural095-owned-child-end/v1','episode_id':boundary['episode_id'],'view':packet.view,
                  'pid':result['client_pid'],'exit_code':0,'forced_stop':False,'process_group_cleanup':'absent',
                  'descendant_absence_verified':False}
         and closed['forced_stop'] is False and closed['descendant_absence_verified'] is False,
         'Child closure receipt differs')
    expected={'schema':'neural095-participant-view-end/v1','status':'complete_unscored','view':packet.view,
      'episode_id':boundary['episode_id'],'actions':actions,'images':images,'output_bytes':outbound,
      'wire_bytes':offset,'wire_records':sequence,'last_sha256':previous,'history':pin(history_body),
      'client_pid':result.get('client_pid'),'client_exit_code':0,'forced_stop':False,
      'process_group_cleanup':'absent','descendant_absence_verified':False,'wall_seconds':result.get('wall_seconds'),
      'reason':None,'provider_context_qualified':False,'scientific_qualification':False}
    need(result==expected and result['forced_stop'] is False and result['descendant_absence_verified'] is False
         and result['provider_context_qualified'] is False and result['scientific_qualification'] is False
         and type(result['client_pid']) is int and result['client_pid']>0
         and all(type(result[k]) is int for k in ('actions','images','output_bytes','wire_bytes','wire_records','client_exit_code'))
         and type(result['wall_seconds']) in (int,float) and math.isfinite(result['wall_seconds'])
         and 0<=result['wall_seconds']<=limits.wall_seconds+3,'Participant closure or receipt mismatch')
    return {'boundary':boundary,'result':result,'boundary_pin':pin(encode(boundary)),'result_pin':pin(encode(result))}

def audit_pair(packets,sessions):
    v.pair_packets(packets)
    need(type(sessions) is dict and set(sessions)==set(v.VIEWS),'Both view sessions required')
    paths={view:unlinked(sessions[view]) for view in v.VIEWS}
    need(len(set(paths.values()))==2,'Distinct view paths required')
    receipts={view:audit_view(paths[view],packets[view]) for view in v.VIEWS}
    boundaries=[receipts[view]['boundary'] for view in v.VIEWS]
    shared=('schema','mode','limits','sandbox','client','python','source','fresh_process_per_view','stateful_within_view')
    need(all({k:b[k] for k in shared}=={k:boundaries[0][k] for k in shared} for b in boundaries)
         and len({b['episode_id'] for b in boundaries})==2,'Mismatched client/limits or reused view context')
    return receipts,{view:paths[view]/'viewer-history.jsonl' for view in v.VIEWS}

def collect(packets,sessions,output):
    receipts,histories=audit_pair(packets,sessions)
    admitted=v.collect(packets,histories,output)
    result={'schema':'neural095-participant-collection/v1','status':'both_closed_views_collected','mode':v.MODE,
      'queries_per_view':258,'sessions':receipts,'original_collection':pin(v.encoded(admitted)),
      'source':source_identity(),'provider_context_qualified':False,'scientific_qualification':False}
    save(Path(output)/'TRANSPORT_COMPLETE.json',encode(result));return result

def evaluate(packets,sessions,collection,reference_loader,private_loader):
    receipts,histories=audit_pair(packets,sessions)
    _,admitted=v.validate_collection(packets,histories,collection)
    expected={'schema':'neural095-participant-collection/v1','status':'both_closed_views_collected','mode':v.MODE,
      'queries_per_view':258,'sessions':receipts,'original_collection':pin(v.encoded(admitted)),
      'source':source_identity(),'provider_context_qualified':False,'scientific_qualification':False}
    need(decode(read(Path(collection)/'TRANSPORT_COMPLETE.json',v.MAX_HISTORY))==expected,
         'Exact closed participant collection required before private/reference loaders')
    result=v.evaluate(packets,histories,collection,reference_loader,private_loader)
    return {'schema':'neural095-participant-grade/v1','transport_collection':pin(encode(expected)),
            'original_grade':result,'scientific_qualification':False,'provider_context_qualified':False}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('view','collect','grade'))
    p.add_argument('--inputs',type=Path,required=True);p.add_argument('--view',choices=v.VIEWS)
    for name in ('output','client','python','cue-session','neural-session','collection','evaluator-inputs'):
        p.add_argument('--'+name,type=Path)
    p.add_argument('--sandbox',choices=('macos','protocol_only'))
    for name in ('max-actions','max-images','max-output-bytes'):p.add_argument('--'+name,type=int)
    p.add_argument('--wall-seconds',type=float)
    a=p.parse_args(argv)
    prior={}
    def stop(signum,frame):raise OwnerInterrupted('Owned signal '+str(signum))
    for sig in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):prior[sig]=signal.signal(sig,stop)
    try:
        sources=v.Sources();inputs=decode(read(a.inputs,65536))
        if a.command=='view':
            need(a.view in v.VIEWS and set(inputs)=={a.view} and all(x is not None for x in
                 (a.output,a.client,a.python,a.sandbox,a.max_actions,a.max_images,a.max_output_bytes,a.wall_seconds)),
                 'One view and complete explicit participant configuration required')
            packet=v.Packet(a.view,inputs[a.view],sources)
            result=run_view(packet,a.output,a.client,a.python,a.sandbox,
                           Limits(a.max_actions,a.max_images,a.max_output_bytes,a.wall_seconds))
            return 0 if result['status']=='complete_unscored' else 2
        need(set(inputs)==set(v.VIEWS) and a.cue_session and a.neural_session,'Both original view locators and sessions required')
        packets={view:v.Packet(view,inputs[view],sources) for view in v.VIEWS}
        sessions={'cue_only':a.cue_session,'neural':a.neural_session}
        if a.command=='collect':need(a.output is not None,'Fresh output required');collect(packets,sessions,a.output)
        else:
            need(a.collection and a.evaluator_inputs and a.output,'Collection/evaluator/output paths required')
            # Reading the evaluator locator is metadata only; loader closures do
            # not touch any named reference/target operand before full admission.
            files=decode(read(a.evaluator_inputs,65536));references,private=v.loaders(sources,files,packets['cue_only'].ids)
            save(a.output,encode(evaluate(packets,sessions,a.collection,references,private)))
        return 0
    except (ValueError,OSError,KeyError,TypeError,EOFError):
        print('Participant operation refused; preserve existing evidence.',file=sys.stderr);return 2
    finally:
        for sig,handler in prior.items():signal.signal(sig,handler)

if __name__=='__main__':raise SystemExit(main())
