"""Trusted fixed time-only producer; no arbitrary candidate or containment claim.

Each job has one fresh frozen standard-library worker, followed by exact row
slices. The worker sees only public full time indices, never X, qids or Y. This
reuse proof applies only to the pinned function, not general participant code.
Actual subprocess execution requires explicit external root admission. Generated
controls inject an executor only under a separate, unqualified scope.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import struct
import subprocess
import sys
import threading
import time
import types

import numpy as np

HERE=Path(__file__).resolve().parent
WORKER_SHA='7085f45a2e2f79c4c9e77f7b870dece03f625bdd6c4bae88ba800f53ef154f0d'
JOIN_SHA='52b6b7691768dff8043e533f95dec303531f871b373bb97420ca5d80c80fffd3'
ORIGINAL='original_figure3b_improvement'
GENERATED='generated_engineering_control'
CAPS={'working_bytes','bundle_bytes','feature_read_bytes','runtime_read_bytes','stdin_bytes','stdout_bytes',
      'stderr_bytes','response_bytes','journal_bytes','max_jobs','max_requests','job_seconds','cleanup_seconds',
      'run_seconds','stderr_per_job_bytes'}
CONFIG={'schema','scope','candidate_sha256','provider_source_sha256','store_sha256','schedule_sha256',
        'condition','python','caps'}
def need(ok,message):
    if not ok:raise ValueError(message)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def integer(v,lo=1,hi=2**63-1):return type(v) is int and lo<=v<=hi
def digest(v):return type(v) is str and len(v)==64 and all(c in '0123456789abcdef' for c in v)
def encoded(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def parse(raw):
    def pairs(rows):
        value={}
        for k,v in rows:need(k not in value,'Duplicate primitive key');value[k]=v
        return value
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'Nonfinite JSON'))
def stamp(s):return tuple(getattr(s,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))
def ordinary(path):
    path=Path(path).absolute()
    need(not any(p.is_symlink() for p in (path,*path.parents)),'No private path symlink')
    return path
def read_regular(path,expected,*,cap,readonly=False):
    path=ordinary(path)
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
    with os.fdopen(fd,'rb',buffering=0) as stream:
        before=os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=cap
             and (not readonly or before.st_mode&0o222==0),'Ordinary bounded immutable file')
        if 'bytes' in expected:need(before.st_size==expected['bytes'],'Exact file extent before read')
        raw=stream.read(before.st_size+1)
        need(len(raw)==before.st_size and sha(raw)==expected['sha256']
             and stamp(before)==stamp(os.fstat(stream.fileno()))==stamp(path.lstat()),'Exact stable file bytes')
    return raw
def _source(path,digest_value):
    raw=read_regular(path,{'sha256':digest_value},cap=131072)
    name='_language_fixed_'+digest_value[:12]
    module=types.ModuleType(name);module.__file__,module.__package__=str(path),''
    sys.modules[name]=module
    try:exec(compile(raw,str(path),'exec',dont_inherit=True),module.__dict__)
    except BaseException:sys.modules.pop(name,None);raise
    return module
J=_source(HERE.parent/'original-figure3b-scoring-join-v1/join.py',JOIN_SHA)
B=J.B

def identity():
    path=Path(__file__)
    with path.open('rb') as stream:raw=stream.read(131073)
    need(len(raw)<=131072,'Bounded provider identity')
    return sha(encoded({'fixed_provider.py':sha(raw),'time_worker.py':WORKER_SHA,'selected_join':JOIN_SHA}))

def config_snapshot(value):
    need(type(value) is dict and set(value)==CONFIG,'Exact fixed programme config')
    for key in CONFIG-{'python','caps'}:
        need(type(value[key]) is str and 0<len(value[key])<=128,'Bounded config strings')
    py=value['python']
    need(type(py) is dict and set(py)=={'path','bytes','sha256','version'}
         and type(py['path']) is str and 0<len(py['path'])<=4096 and Path(py['path']).is_absolute()
         and integer(py['bytes'],1,64*1024**2) and digest(py['sha256'])
         and type(py['version']) is str and 0<len(py['version'])<=128,'Exact bounded trusted interpreter identity')
    need(type(value['caps']) is dict and set(value['caps'])==CAPS and all(integer(v) for v in value['caps'].values()),
         'Finite complete fixed programme resource caps')
    need(value['schema']=='language-fixed-time-provider/v1' and value['scope'] in (ORIGINAL,GENERATED)
         and value['condition']=='paper_data' and value['candidate_sha256']==WORKER_SHA,'Only fixed time programme and explicit scope')
    need(all(digest(value[k]) for k in ('candidate_sha256','provider_source_sha256','store_sha256','schedule_sha256')),'Frozen global identities')
    c=value['caps']
    need(c['working_bytes']<=1024**3 and 64<=c['bundle_bytes']<=B.MAX_BUNDLE_BYTES
         and c['max_jobs']<=42 and c['max_requests']<=5685 and c['max_requests']>=2*c['max_jobs']
         and c['job_seconds']+c['cleanup_seconds']<=c['run_seconds'] and c['cleanup_seconds']<=30
         and c['stderr_per_job_bytes']<=65536,'Bounded per-job/whole fixed-control resources')
    if value['scope']==ORIGINAL:need(c['max_jobs']==42 and c['max_requests']==5685,'Complete original selected control schedule')
    raw=encoded(value);need(len(raw)<=8192,'Bounded frozen config')
    return parse(raw)

def admission_snapshot(config,admission):
    keys={'schema','config_sha256','protocol_sha256','root_admission_id','admitted_until_unix'}
    need(type(admission) is dict and set(admission)==keys,'External exact root control admission required')
    need(admission['schema']=='language-fixed-control-admission/v1'
         and admission['config_sha256']==sha(encoded(config)) and digest(admission['protocol_sha256'])
         and type(admission['root_admission_id']) is str and 0<len(admission['root_admission_id'])<=128
         and integer(admission['admitted_until_unix']) and time.time()<admission['admitted_until_unix'],
         'Live exact fixed-programme admission, not generic candidate execution')
    return parse(encoded(admission))

class Meter:
    """Nonrefundable pre-admitted allowances; pipe actual bytes also reported."""
    def __init__(self,caps):self.caps=dict(caps);self.values={k:0 for k in caps}
    def charge(self,key,count):
        need(integer(count,0) and self.values[key]+count<=self.caps[key],'Cumulative '+key+' exhausted before operation')
        self.values[key]+=count

class WorkerFailure(RuntimeError):
    def __init__(self,message,receipt):super().__init__(message);self.receipt=receipt

class PosixExecutor:
    """Trusted fixed child only; never called by generated tests.

    One wait owner, default SIGCHLD and no competing threads are prerequisites.
    Cleanup signals the new process group only while this owner still retains
    the unreaped child, then reaps and checks absence without signalling a reused
    PID/group. No namespace, hostile-code or parent-death containment is claimed.
    """
    def __init__(self,python_path,source,caps):
        self.python_path,self.source,self.caps=python_path,source,dict(caps)
    def __call__(self,frame,stdout_limit,deadline):
        need(os.name=='posix' and threading.active_count()==1 and signal.getsignal(signal.SIGCHLD)==signal.SIG_DFL,
             'One trusted POSIX wait owner with default SIGCHLD')
        need(type(frame) is bytes and len(frame)<=16+8*144111 and integer(stdout_limit,1,128+8*144111),
             'Exact admitted fixed worker transport')
        proc=None;selector=None;streams=[];out=bytearray();err=bytearray();at=0;reaped=False
        receipt={'schema':'language-fixed-job-process/v1','generated':False,'pid':None,'natural_exit_zero':False,
            'owned_group_absent':False,'pipes_closed':False,'stdin_bytes':0,'stdout_bytes':0,'stderr_bytes':0,
            'source_sha256':sha(self.source),'exec_reset':True,'containment_qualified':False}
        failure=None
        try:
            need(time.monotonic()<deadline,'Job deadline before process creation')
            proc=subprocess.Popen([self.python_path,'-I','-S','-B','-c',self.source.decode('utf-8')],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0,close_fds=True,
                start_new_session=True,restore_signals=True,cwd='/',env={'LANG':'C','LC_ALL':'C'})
            receipt['pid']=proc.pid
            streams=[proc.stdin,proc.stdout,proc.stderr];selector=selectors.DefaultSelector()
            for stream,event,label in ((proc.stdin,selectors.EVENT_WRITE,'stdin'),(proc.stdout,selectors.EVENT_READ,'stdout'),(proc.stderr,selectors.EVENT_READ,'stderr')):
                os.set_blocking(stream.fileno(),False);selector.register(stream,event,label)
            while selector.get_map():
                need(time.monotonic()<deadline,'Whole finite job transport deadline')
                for key,_ in selector.select(min(.05,max(0,deadline-time.monotonic()))):
                    stream=key.fileobj;kind=key.data
                    if kind=='stdin':
                        chunk=memoryview(frame)[at:at+65536]
                        wrote=os.write(stream.fileno(),chunk);need(wrote>0,'Worker input write progress')
                        at+=wrote;receipt['stdin_bytes']+=wrote
                        if at==len(frame):selector.unregister(stream);stream.close()
                    else:
                        buffer,limit=(out,stdout_limit) if kind=='stdout' else (err,self.caps['stderr_per_job_bytes'])
                        # One overflow/EOF probe is included in the up-front
                        # reservation; no read can exceed that owned allowance.
                        extent=min(65536,limit-len(buffer)+1);need(extent>0,'Pipe cap before read')
                        chunk=os.read(stream.fileno(),extent)
                        receipt[kind+'_bytes']+=len(chunk)
                        if chunk:
                            buffer.extend(chunk);need(len(buffer)<=limit,'Worker '+kind+' overflow')
                        else:selector.unregister(stream);stream.close()
            need(at==len(frame),'Complete time-only stdin')
            # wait() is the sole reap. Natural success cannot trigger cleanup
            # signalling after reap; unexpected surviving groups are refused.
            code=proc.wait(timeout=max(.001,deadline-time.monotonic()));reaped=True
            receipt['natural_exit_zero']=code==0
            try:os.killpg(proc.pid,0)
            except ProcessLookupError:receipt['owned_group_absent']=True
            need(code==0 and receipt['owned_group_absent'],'Natural zero and absent owned group required')
        except BaseException as exc:failure=exc
        finally:
            cleanup_errors=[]
            # Popen.wait can reap internally before propagating an interrupt.
            # Inspect only its already-recorded state, never poll/reap here.
            if proc is not None and proc.returncode is not None:reaped=True
            if proc is not None and not reaped:
                # The unreaped child retains its process identity; this owner
                # never poll()s or targets an already reaped numeric PID.
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                except BaseException as exc:cleanup_errors.append(exc)
                try:proc.wait(timeout=self.caps['cleanup_seconds']);reaped=True
                except BaseException as exc:cleanup_errors.append(exc)
                if proc.returncode is not None:reaped=True
                if reaped:
                    try:os.killpg(proc.pid,0)
                    except ProcessLookupError:receipt['owned_group_absent']=True
                    except BaseException as exc:cleanup_errors.append(exc)
            if selector is not None:
                try:selector.close()
                except BaseException as exc:cleanup_errors.append(exc)
            for stream in streams:
                try:stream.close()
                except BaseException as exc:cleanup_errors.append(exc)
            receipt['pipes_closed']=all(s.closed for s in streams)
            if cleanup_errors:failure=RuntimeError('Owned fixed-worker cleanup failed: '+type(cleanup_errors[0]).__name__)
        if failure is not None:raise WorkerFailure(type(failure).__name__+': '+str(failure)[:256],receipt) from failure
        return {'stdout':bytes(out),'stderr':bytes(err),'receipt':receipt}

def npy_bytes(payload,rows):
    need(type(payload) is bytes and len(payload)==8*rows,'Exact immutable prediction payload')
    header=("{'descr': '<f8', 'fortran_order': False, 'shape': (%d, 1), }"%rows).encode('ascii')
    header+=b' '*(117-len(header))+b'\n'
    return b'\x93NUMPY\x01\x00'+struct.pack('<H',118)+header+payload

def prediction_payload(raw,rows):
    need(type(raw) is bytes and len(raw)==128+8*rows,'Exact complete full-job prediction transport')
    header=npy_bytes(b'\0'*(8*rows),rows)[:128]
    need(raw[:128]==header,'Canonical worker NPY header, no pickle/extra shape/order')
    payload=raw[128:];need(np.isfinite(np.frombuffer(payload,dtype='<f8')).all(),'Finite fixed programme prediction')
    return payload

class FixedProvider:
    def __init__(self,config,admission,*,evidence_root,executor=None):
        self.config=config_snapshot(config);self.caps=self.config['caps'];self.scope=self.config['scope']
        need(self.config['provider_source_sha256']==identity(),'Exact executing provider identity')
        self.generated=self.scope==GENERATED
        if self.generated:need(admission is None and callable(executor),'Generated scope requires explicit simulated executor')
        else:
            need(executor is None,'Actual fixed control rejects injected executors')
            self.admission=admission_snapshot(self.config,admission)
            need(os.name=='posix' and threading.active_count()==1 and signal.getsignal(signal.SIGCHLD)==signal.SIG_DFL,
                 'Trusted POSIX one-owner execution prerequisite')
        self.candidate_sha256=self.config['candidate_sha256'];self.provider_source_sha256=self.config['provider_source_sha256']
        self.condition=self.config['condition'];self.meter=Meter(self.caps)
        self.failed=self.closed=self.finished=False;self.active=None;self.jobs=self.requests=self.workers=self.worker_attempts=0
        self.started=time.monotonic();self.deadline=self.started+self.caps['run_seconds']
        self.io_actual={k:0 for k in ('stdin_bytes','stdout_bytes','stderr_bytes')}
        self.journal=None;self.journal_hash=hashlib.sha256();self.journal_records=0
        worker_size=(HERE/'time_worker.py').lstat().st_size
        need(integer(worker_size,1,16384),'Bounded fixed worker source before read')
        need(8*worker_size+65536<=self.caps['working_bytes'],'Worker source workspace before read')
        self.meter.charge('runtime_read_bytes',worker_size+1)
        self.worker_source=read_regular(HERE/'time_worker.py',{'bytes':worker_size,'sha256':WORKER_SHA},cap=16384)
        if not self.generated:
            py=self.config['python']
            need(py['version']==sys.version.split()[0] and Path(py['path'])==Path(sys.executable).resolve(),
                 'Existing exact trusted interpreter, no arbitrary executable')
            need(2*py['bytes']+16*1024**2<=self.caps['working_bytes'],'Interpreter authentication workspace before read')
            self.meter.charge('runtime_read_bytes',py['bytes']+1)
            read_regular(py['path'],py,cap=64*1024**2)
            executor=PosixExecutor(py['path'],self.worker_source,self.caps)
        self.executor=executor
        self.root=ordinary(evidence_root);self.root.mkdir(mode=0o700)
        try:
            self.journal=(self.root/'JOBS.jsonl').open('xb',buffering=0);os.chmod(self.root/'JOBS.jsonl',0o600)
            self._journal({'kind':'configuration','schema':'language-fixed-time-job-journal/v1','config_sha256':sha(encoded(self.config)),
                'candidate_sha256':WORKER_SHA,'provider_source_sha256':self.provider_source_sha256,
                'scope':self.scope,'reuse':'One trusted time-only producer/job; ordered slices per held request, not one process/request.',
                'generated':self.generated,'containment_qualified':False,'scientific_qualification':False})
        except BaseException:self.failed=True;self.close();raise

    def _check(self):
        need(not self.failed and not self.closed and not self.finished,'Live unfailed fixed provider')
        need(self.started<=time.monotonic()<self.deadline-self.caps['cleanup_seconds'],'Whole-run deadline including cleanup reserve')
        if not self.generated:need(time.time()<self.admission['admitted_until_unix'],'Root control admission still live')
    def _journal(self,value):
        raw=encoded(value);need(len(raw)<=8192,'Bounded private job journal record')
        self.meter.charge('journal_bytes',len(raw));need(self.journal.write(raw)==len(raw),'Complete journal write')
        self.journal_hash.update(raw);self.journal_records+=1
    def prepare_feature(self,path,spec,*,rows):
        try:
            self._check();need(self.active is None and self.jobs<self.caps['max_jobs'],'One feature job in canonical sequence')
            need(type(spec) is dict and len(spec)<=16 and {'sha256','bytes','fortran_order'}<=set(spec)
                 and digest(spec['sha256']) and integer(spec['bytes']) and spec['fortran_order'] is False
                 and integer(rows,2,144111) and spec['bytes']==128+240*rows,'Exact original canonical feature descriptor')
            need(4*spec['bytes']+128*rows+16*1024**2<=self.caps['working_bytes'],'Feature authentication workspace before I/O')
            self.meter.charge('feature_read_bytes',spec['bytes']+1)
            raw=read_regular(path,spec,cap=spec['bytes'],readonly=True)
            stream=io.BytesIO(raw)
            need(np.lib.format.read_magic(stream)==(1,0),'Original feature NPY1.0')
            shape,order,dtype=np.lib.format.read_array_header_1_0(stream,max_header_size=4096)
            need(shape==(rows,30) and order is False and dtype==np.dtype('<f8') and stream.tell()==128,'Exact authenticated source feature geometry')
            handle=object();self.active={'handle':handle,'rows':rows,'feature':{'bytes':len(raw),'sha256':sha(raw),'fortran_order':False},
                'next':0,'binding':None,'query_trace':hashlib.sha256()}
            return handle
        except BaseException:self.failed=True;raise

    def _worker(self,times_raw,rows,context):
        frame=struct.pack('<8sQ',b'LNGTIME1',rows)+times_raw;maximum=128+8*rows
        # Reserve full per-job pipe maxima before launching; actual transport
        # counters remain separate and include failure observations.
        for key,amount in [('stdin_bytes',len(frame)),('stdout_bytes',maximum+1),('stderr_bytes',self.caps['stderr_per_job_bytes']+1)]:self.meter.charge(key,amount)
        self.meter.charge('max_jobs',1)
        need(self.meter.values['journal_bytes']+16384<=self.caps['journal_bytes'],'Start/completion journal reservation before execution')
        self._journal({'kind':'worker_start','job':self.jobs,'context':context,'time_frame_sha256':sha(frame),
            'time_frame_bytes':len(frame),'worker_source_sha256':WORKER_SHA,'worker_visible_operands':['time_indices'],
            'generated':self.generated,'event_scope':'Launch attempt; actual child identity is recorded only by its executor receipt.'})
        deadline=min(self.deadline-self.caps['cleanup_seconds'],time.monotonic()+self.caps['job_seconds'])
        self.worker_attempts+=1
        try:
            result=self.executor(frame,maximum,deadline)
        except WorkerFailure as exc:
            receipt=exc.receipt
            if integer(receipt.get('pid')):self.workers+=1
            for key in self.io_actual:self.io_actual[key]+=receipt.get(key,0)
            self._journal({'kind':'worker_failure','job':self.jobs,'receipt':receipt,'error':str(exc)[:256]})
            raise
        need(type(result) is dict and set(result)=={'stdout','stderr','receipt'} and type(result['stdout']) is bytes
             and type(result['stderr']) is bytes and len(result['stdout'])<=maximum and len(result['stderr'])<=self.caps['stderr_per_job_bytes'],
             'Bounded complete worker transport result')
        receipt=result['receipt']
        need(type(receipt) is dict and receipt.get('schema')=='language-fixed-job-process/v1'
             and receipt.get('generated') is self.generated and receipt.get('source_sha256')==WORKER_SHA
             and all(receipt.get(k) is True for k in ('natural_exit_zero','owned_group_absent','pipes_closed')),
             'Closed owned job producer before any prediction derivation')
        for key,n in [('stdin_bytes',len(frame)),('stdout_bytes',len(result['stdout'])),('stderr_bytes',len(result['stderr']))]:
            need(receipt.get(key)==n,'Exact worker observed pipe accounting');self.io_actual[key]+=n
        need(self.generated or integer(receipt.get('pid')),'Actual closed worker PID required')
        self.workers+=1
        payload=prediction_payload(result['stdout'],rows)
        self._journal({'kind':'worker_closed','job':self.jobs,'context':context,'receipt':receipt,
            'full_row_prediction_sha256':sha(result['stdout']),'full_row_prediction_bytes':len(result['stdout']),
            'execution_scope':'One fixed time-only producer for this complete job, not one worker for each held qid.'})
        return payload,sha(encoded(receipt))

    def run_request(self,handle,bundle,descriptor):
        try:
            self._check();a=self.active;need(a is not None and handle is a['handle'],'Owned active feature handle')
            need(type(bundle) is bytes and 64<=len(bundle)<=self.caps['bundle_bytes'],'Bounded immutable response bundle')
            need(8*len(bundle)+192*a['rows']+3*8192+16*1024**2<=self.caps['working_bytes'],'Joint decode/maps/full-output workspace before allocation')
            if type(descriptor) is dict:
                need(set(descriptor)=={'public_json','public_id'},'Exact primitive descriptor carrier')
                raw,request_id=descriptor['public_json'],descriptor['public_id']
            else:raw,request_id=descriptor.public_json,descriptor.public_id
            need(type(raw) is bytes and 0<len(raw)<=8192 and digest(request_id) and sha(raw)==request_id,'Exact immutable public identity')
            public=parse(raw);need(type(public) is dict and type(public.get('context')) is dict,'Original public context')
            context=dict(public['context']);context.pop('held_qid',None)
            typed=J._source_context(context)
            need(context==J.ENDPOINT.contexts()[self.jobs],'Canonical fixed42 source job order')
            expected=B.make_descriptor(bundle,typed,feature_sha256=a['feature']['sha256'],feature_bytes=a['feature']['bytes'],
                feature_fortran_order=False,byte_limit=self.caps['bundle_bytes'],working_limit=self.caps['working_bytes'])
            need(expected.public_json==raw and expected.public_id==request_id,'Actual authenticated feature/bundle/context join')
            view=B.decode_bundle(bundle,byte_limit=self.caps['bundle_bytes'],working_limit=self.caps['working_bytes'])
            need(view.rows==a['rows'] and view.output_columns==1,'Exact selected one-column source rows')
            qid_raw=view.qid.tobytes();times_raw=view.time_indices.tobytes()
            binding=(encoded(context),qid_raw,times_raw)
            if a['binding'] is None:
                labels=np.unique(view.qid);a['held_bits']=labels.astype('<f8',copy=False).tobytes()
                a['held_count']=len(labels);a['binding']=binding
                need(self.requests+len(labels)<=self.caps['max_requests'],'Complete held roster fits remaining count before worker')
                need(struct.pack('<d',view.held_qid)==a['held_bits'][:8],'First canonical held qid before worker')
                a['payload'],a['worker_receipt_sha256']=self._worker(times_raw,view.rows,context)
            need(a['binding']==binding,'Identical full public time/qid maps and context throughout fixed job')
            need(a['next']<a['held_count'] and struct.pack('<d',view.held_qid)==a['held_bits'][8*a['next']:8*(a['next']+1)],
                 'Canonical complete held order; no duplicate, skipped or changed request')
            self.meter.charge('max_requests',1)
            self.meter.charge('response_bytes',128+8*len(view.query_positions))
            payload=np.frombuffer(a['payload'],dtype='<f8')[view.query_positions].tobytes()
            prediction=npy_bytes(payload,len(view.query_positions))
            closure={'schema':'language-private-invocation-closure/v1','request_sha256':request_id,
                'candidate_sha256':WORKER_SHA,'provider_source_sha256':self.provider_source_sha256,
                'natural_exit_zero':True,'owned_processes_absent':True,'private_view_retired':True,'transport_sha256':sha(prediction)}
            a['query_trace'].update(encoded({'ordinal':a['next'],'request_sha256':request_id,'prediction_sha256':sha(prediction),
                'closure_sha256':sha(encoded(closure)),'closed_job_producer_sha256':a['worker_receipt_sha256']}))
            a['next']+=1;self.requests+=1
            return prediction,closure
        except BaseException:self.failed=True;raise

    def release_feature(self,handle):
        if self.active is None:return
        a=self.active
        if self.failed:
            # Accepted collector calls this from finally. Preserve the original
            # request/worker error rather than replacing it with incompleteness.
            self.active=None
            try:self._journal({'kind':'failed_job_retired','job':self.jobs,'derived_responses':a['next'],
                'complete':False,'primary_failure_preserved':True})
            except BaseException:pass
            return
        try:
            need(handle is a['handle'],'Owned feature release')
            need(not self.failed and a['binding'] is not None and a['next']==a['held_count'],'Complete job before successful release')
            self._journal({'kind':'derived_requests_complete','job':self.jobs,'context':parse(a['binding'][0]),
                'derived_responses':a['next'],'ordered_request_prediction_closure_sha256':a['query_trace'].hexdigest(),
                'closed_job_producer_sha256':a['worker_receipt_sha256'],'per_request_processes':False})
            self.jobs+=1
        except BaseException:self.failed=True;raise
        finally:self.active=None

    def finish(self):
        self._check();need(self.active is None and self.jobs==self.caps['max_jobs'] and self.requests==self.caps['max_requests']
            and self.workers==self.jobs,'Complete fixed job and derived-response roster')
        receipt={'schema':'language-fixed-time-provider-result/v1','scope':self.scope,'worker_source_sha256':WORKER_SHA,
            'provider_source_sha256':self.provider_source_sha256,'jobs':self.jobs,'worker_executions':self.workers,
            'worker_launch_attempts':self.worker_attempts,
            'derived_responses':self.requests,'generated':self.generated,'pipe_actual_bytes':dict(self.io_actual),
            'nonrefundable_admitted_bytes_and_counts':dict(self.meter.values),'journal_records':self.journal_records,
            'journal_sha256':self.journal_hash.hexdigest(),'prediction_reuse':'Only fixed time-only function; identical time vector and row map per job.',
            'native_containment_qualified':False,'scientific_qualification':False}
        self.finished=True;self.close();return receipt

    def close(self):
        if self.closed:return
        self.closed=True;self.active=None
        if self.journal is not None:
            try:self.journal.flush();os.fchmod(self.journal.fileno(),0o400)
            finally:self.journal.close()
