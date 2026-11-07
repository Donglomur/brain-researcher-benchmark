"""Independent source-custody and whole-process observer. Source construction only.

Requires explicit future root selection. It does not grade or assert scientific
qualification. A failed/killed worker can leave independently owned Docker state;
that uncertainty is preserved and forbids automatic retry or input retirement.
"""
import time
ORIGIN=globals().get('_CAPTURED_LAUNCH_ORIGIN',time.monotonic())
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import types

META=1048576
STREAM=65536
READ_CAP=16*1024**3
WRITE_CAP=16*1024**2


def need(ok,message):
    if not ok:raise ValueError(message)

def encode(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def parse(raw):
    def pairs(rows):
        out={}
        for k,v in rows:need(k not in out,'duplicate metadata field');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite JSON'))
def path(value):
    p=Path(value).absolute();need('..' not in p.parts and all(not x.is_symlink() for x in (p,*p.parents)),'ordinary exclusive path');return p

def relative(value):
    need(type(value)is str and value and '\\' not in value and len(value)<=240,'bounded source member')
    p=Path(value);need(not p.is_absolute() and p.as_posix()==value and all(x not in ('','.','..') for x in value.split('/')),'confined source path');return p

def sync(p):
    fd=os.open(path(p),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

class IO:
    def __init__(self,end):self.end=end;self.read=globals().get('_EARLY_SOURCE_READ_CHARGE',0);self.write=0
    def tick(self):need(time.monotonic()<self.end,'original whole observer deadline')
    def capture(self,p,d,cap=META,retain=True):
        self.tick();p=path(p)
        need(type(d)is dict and type(d.get('bytes'))is int and 0<=d['bytes']<=cap and type(d.get('sha256'))is str and len(d['sha256'])==64,'exact bounded content descriptor')
        self.read+=d['bytes']+1;need(self.read<=READ_CAP,'whole observer read cap')
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            st=os.fstat(fd);need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size==d['bytes'],'ordinary exact source/body')
            fields=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            left=st.st_size;h=hashlib.sha256();pieces=[]
            while left:
                self.tick();b=os.read(fd,min(left,1048576));need(b,'no truncated input');left-=len(b);h.update(b)
                if retain:pieces.append(b)
            need(not os.read(fd,1) and fields(st)==fields(os.fstat(fd))==fields(p.lstat()) and h.hexdigest()==d['sha256'],'stable exact full input and EOF')
            return b''.join(pieces) if retain else d
        finally:os.close(fd)
    def owned(self,p,cap=META):
        # Allowed only in the fresh exclusively owned attempt, after natural worker exit.
        p=path(p);st=p.lstat();need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size<=cap,'bounded own output')
        self.read+=st.st_size+1;need(self.read<=READ_CAP,'owned discovery read cap')
        with p.open('rb') as f:raw=f.read(cap+1)
        need(len(raw)==st.st_size,'exact own receipt extent')
        return self.capture(p,pin(raw),cap)
    def save(self,p,raw):
        self.tick();self.write+=len(raw);need(self.write<=WRITE_CAP,'observer cumulative write cap')
        p=path(p);missing=[];q=p.parent
        while not q.exists():missing.append(q);q=q.parent
        for q in reversed(missing):q.mkdir(mode=0o700);sync(q);sync(q.parent)
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
        try:
            view=memoryview(raw)
            while view:self.tick();n=os.write(fd,view);need(n>0,'full observer write');view=view[n:]
            os.fsync(fd)
        finally:os.close(fd)
        sync(p.parent);self.tick();return pin(raw)


def frozen_sources(root,destination,expected,io):
    raw=io.capture(root/'SOURCE_MANIFEST.json',expected,262144);manifest=parse(raw)
    need(manifest['schema']=='visual_alpha_complete_program_source_v1' and manifest['task_id']=='PAPER-ROOT-ADD-014' and manifest['source_only']is True,'exact source-only program manifest')
    files=manifest['files'];need(type(files)is dict and 1<=len(files)<=128 and sum(d['bytes'] for d in files.values())<=4*META,'bounded complete source closure')
    need({'worker.py','controller.py','engine/native.py','engine/holder.py','candidate_entry.py','baseline_entry.py','BINDINGS.json','protocol.py'}<=set(files),'actual complete program implementation')
    bodies={n:io.capture(root/relative(n),d,META) for n,d in files.items()}
    need(not destination.exists(),'fresh exclusive source snapshot')
    for n,b in bodies.items():io.save(destination/relative(n),b)
    io.save(destination/'SOURCE_MANIFEST.json',raw)
    # Read every snapshot body back before import or mounting.
    for n,d in files.items():io.capture(destination/relative(n),d,META,retain=False)
    dirs=sorted({(destination/relative(n)).parent for n in files}|{destination},key=lambda x:len(x.parts),reverse=True)
    for directory in dirs:os.chmod(directory,0o555);sync(directory)
    return manifest,bodies


def observe_child(command,end,io):
    """Observe this worker group only; daemon/CLI closure additionally needs85receipts."""
    p=None;selector=None;buf={'out':bytearray(),'err':bytearray()};natural=False;group_absent=False;error=None;code=None
    try:
        p=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,bufsize=0,env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')})
        selector=selectors.DefaultSelector()
        for key,stream in [('out',p.stdout),('err',p.stderr)]:os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,key)
        while selector.get_map():
            need(time.monotonic()<end,'original worker success deadline')
            for event,_ in selector.select(min(.1,max(0,end-time.monotonic()))):
                try:b=os.read(event.fileobj.fileno(),min(65536,STREAM+1-sum(map(len,buf.values()))))
                except BlockingIOError:continue
                if not b:selector.unregister(event.fileobj);continue
                need(sum(map(len,buf.values()))+len(b)<=STREAM,'combined exact stdout/stderr cap');buf[event.data].extend(b)
        code=p.wait(timeout=max(0,end-time.monotonic()));natural=code==0
        try:os.killpg(p.pid,0)
        except ProcessLookupError:group_absent=True
        need(natural and group_absent and time.monotonic()<end,'natural zero and owned worker-group absence inside original clock')
    except BaseException as e:error=type(e).__name__
    finally:
        cleanup_end=min(io.end,time.monotonic()+10)
        if p is not None and not group_absent:
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:group_absent=True
            except BaseException as e:error=error or type(e).__name__
        if p is not None:
            try:p.wait(timeout=max(0,cleanup_end-time.monotonic()))
            except BaseException as e:error=error or type(e).__name__
            while not group_absent and time.monotonic()<cleanup_end:
                try:os.killpg(p.pid,0)
                except ProcessLookupError:group_absent=True;break
                except BaseException as e:error=error or type(e).__name__;break
                time.sleep(.01)
        if selector is not None:selector.close()
        if p is not None:
            for stream in (p.stdout,p.stderr):
                if stream is not None:stream.close()
    return {'schema':'visual_alpha_external_worker_v1','command':command,'worker_pid':None if p is None else p.pid,'natural_zero':natural,'returncode':code,'group_absence_observed':group_absent,'stdout':pin(bytes(buf['out'])),'stderr':pin(bytes(buf['err'])),'error_type':error,'original_success_end':end,'observed_monotonic':time.monotonic(),'native_resource_closure_not_inferred_from_worker_group':True}


def admit_collection(root,raw,engine,protocol,io,source,end,selection):
    c=parse(raw);phases=protocol.phases()
    need(c['schema']=='visual_alpha_complete_paired_collection_v1' and c['source_manifest']==source and c['coverage']==protocol.COVERAGE,'exact complete collection')
    need([r['context'] for r in c['phases']]==phases and set(c['artifacts'])=={x['phase_id'] for x in phases},'all85 original contexts')
    for record,ctx in zip(c['phases'],phases):
        pr=root/'phases'/ctx['phase_id']
        request=parse(io.capture(pr/'REQUEST.json',record['request']))
        engine.validate_request(ctx['mode'],request)
        need(all(request[k]==ctx[k] for k in ('phase_id','mode','participant','fit_role')) and request['source']==source and request['image']==selection['image'] and request['producer_seconds']==selection['producer_seconds'][ctx['mode']],'exact selected phase request and matched envelope')
        receipt=parse(io.capture(pr/'ACCEPTED_PHASE.json',record['receipt']))
        need(receipt['phase_id']==ctx['phase_id'] and receipt['phase']==ctx['mode'] and receipt['participant']==ctx['participant'] and receipt['fit_role']==ctx['fit_role'],'exact context receipt join')
        need(receipt['status']=='captured' and receipt['source']==source and receipt['source_before']==receipt['source_after'] and receipt['source_before']['manifest']==source,'same authenticated execution closure')
        engine.validate_natural_exit(receipt['natural_exit']);engine.validate_cli_records(receipt['command_metadata'])
        need(receipt['producer_closed_before_capture']is True and receipt['all_native_resources_closed']is True and receipt['cli_reaped']is True and len(receipt['closures'])==3 and all(r['closed']is True for r in receipt['closures']),'normal transitive owned-resource closure')
        need(receipt['original_deadline']==end and receipt['started']+receipt['elapsed_seconds']<receipt['phase_end']<=end,'unrenewed phase clock')
        expected=engine.expected_outputs(ctx['mode'],ctx['participant']);pins=receipt['artifacts']['files']
        need(set(pins)==set(expected) and receipt['artifacts']['capture_complete']is True and pins==c['artifacts'][ctx['phase_id']]['raw'],'exact captured complete output set')
        for name,d in pins.items():io.capture(pr/'closed/artifacts'/name,d,expected[name],retain=False)
        io.capture(pr/'ADMITTED.json',c['artifacts'][ctx['phase_id']]['admitted'],16*META,retain=False)
        io.capture(pr/'JOURNAL.jsonl',record['journal'],META,retain=False)
        need(record['input_retired_only_after_exact_closure']is True and not (pr/'input').exists(),'owned view absent after exact natural closure')
    need(type(c['panels'])is dict and set(c['panels'])=={'reproduction_A','reproduction_B','corrected_A','corrected_B','portable_operator'},'exact five complete spatial panels')
    for name,d in c['panels'].items():
        p=root/'phases'/('spatial_'+name[-1])/'ADMITTED.json' if name.startswith('reproduction_') else root/'panels'/(name+'.json')
        io.capture(p,d,16*META,retain=False)
    join=parse(io.capture(root/'SEALED_GRADE_JOIN.json',c['sealed_grade_join']))
    need(join['panels']==c['panels'] and join['source_manifest']==source and join['portable_operator_phases']==[x['phase_id'] for x in phases if x['mode']=='reference'] and join['automatic_scoring']is False,'sealed independent baseline all27 exact output join')
    commit=parse(io.capture(root/'GLOBAL_COMMITMENT.json',c['commitment']))
    need(commit['schema']=='visual_alpha_six_programs_global_commitment_v1' and commit['authorship']==selection['authorship'] and commit['all6_frozen_before_any_numeric_input']is True,'exact global six-program commitment')
    for arm in ('A','B'):
        need(set(commit['programs'][arm])==set(protocol.PURPOSES),'exact three purposes per arm')
        for purpose in protocol.PURPOSES:
            d=commit['programs'][arm][purpose]
            need(d=={k:selection['programs'][arm][purpose][k] for k in ('bytes','sha256')},'same selected program')
            io.capture(root/'programs'/arm/(purpose+'.py'),d,8*META,retain=False)
    need(c['private_scoring_called']is False and c['runtime_qualified']is False and c['scientific_qualified']is False,'collection alone grants no qualification')
    return c


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--selection',required=True);parser.add_argument('--selection-sha256',required=True);parser.add_argument('--output',required=True)
    a=parser.parse_args();root=Path(__file__).absolute().parent;io=IO(ORIGIN+120)
    previous=globals().get('_CAPTURED_LAUNCH_HANDLERS')
    early=globals().get('_CAPTURED_LAUNCH_ALARM')
    timer=signal.getitimer(signal.ITIMER_REAL)
    need(type(previous)is dict and set(previous)=={signal.SIGALRM,signal.SIGINT,signal.SIGTERM} and callable(early) and signal.getsignal(signal.SIGALRM)is early and timer[1]==0. and 0<timer[0]<=ORIGIN+120-time.monotonic()+.01,'captured-byte launcher and original early alarm required')
    def expired(*_):raise TimeoutError('original whole observer clock')
    primary=None
    try:
        signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,ORIGIN+120-time.monotonic())
        selection=path(a.selection);sraw=io.capture(selection,{'bytes':selection.stat().st_size,'sha256':a.selection_sha256});v=parse(sraw)
        # Source gate before any candidate program or scientific input body is opened.
        need(v.get('scientific_execution_authorized')is True and v.get('exclusive_custody')is True,'explicit future root operation required')
        output=path(a.output);need(not output.exists() and output.parent.is_dir(),'fresh run root')
        fs=os.statvfs(output.parent)
        need(fs.f_bavail*fs.f_frsize>=2*1024**3+v.get('other_future_bytes',0)+6*1024**3+WRITE_CAP,'prospective whole selected output floor plus OTHER and observer reserve')
        output.mkdir(mode=0o700);sync(output);sync(output.parent)
        manifest,bodies=frozen_sources(root,output/'source',v['source_manifest'],io)
        sys.path.insert(0,str(output/'source'))
        import controller
        controller.selected(v)
        seconds=sum(v['producer_seconds'][c['mode']]+360 for c in controller.protocol.phases())
        work_end=ORIGIN+120+seconds+600;observer_end=work_end+600
        io.tick();io.end=observer_end;signal.setitimer(signal.ITIMER_REAL,observer_end-time.monotonic())
        sp=io.save(output/'SELECTION.json',sraw)
        command=[sys.executable,'-I','-S','-B',str(output/'source/worker.py'),'--selection',str(output/'SELECTION.json'),'--output',str(output/'collection'),'--origin',str(ORIGIN)]
        external=observe_child(command,work_end,io);ep=io.save(output/'EXTERNAL_EXIT.json',encode(external))
        need(external['natural_zero']is True and external['group_absence_observed']is True and external['error_type']is None,'natural external worker closure required; preserve failure custody')
        eroot=output/'source';spec=importlib.util.spec_from_file_location('_visual_alpha_observed_engine',eroot/'engine/native.py')
        engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
        raw=io.owned(output/'collection/COLLECTION.json');collection=admit_collection(output/'collection',raw,engine,controller.protocol,io,v['source_manifest'],work_end,v)
        for n,d in manifest['files'].items():io.capture(eroot/relative(n),d,META,retain=False)
        receipt={'schema':'visual_alpha_whole_collection_observed_v1','status':'normal_complete85_collection_integrity_only','source_manifest':v['source_manifest'],'selection':sp,'external':ep,'collection':pin(raw),'all85_natural_owned_resource_receipts_admitted':True,'portable_baseline_outputs_sealed_before_scoring':True,'original_origin':ORIGIN,'work_end':work_end,'observer_end':observer_end,'observed_monotonic_before_publication':time.monotonic(),'managed_read_bytes':io.read,'managed_write_bytes_before_receipt':io.write,'runtime_qualified':False,'scientific_qualified':False,'private_scoring_called':False,'automatic_retry_authorized':False}
        io.save(output/'OBSERVED.json',encode(receipt));return 0
    except BaseException as error:primary=error;raise
    finally:
        failures=[]
        for action in [lambda:signal.setitimer(signal.ITIMER_REAL,0)]+[lambda s=s,h=h:signal.signal(s,h) for s,h in previous.items()]:
            try:action()
            except BaseException as e:failures.append(type(e).__name__)
        if failures:
            if primary is None:raise RuntimeError('observer alarm cleanup uncertainty:'+','.join(failures))
            primary.add_note('observer alarm cleanup uncertainty:'+','.join(failures))
if __name__=='__main__':raise SystemExit(main())
