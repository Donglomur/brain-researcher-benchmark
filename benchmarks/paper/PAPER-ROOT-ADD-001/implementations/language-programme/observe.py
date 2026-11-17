"""Complete language building blocks program and source-bound normal-closure observer."""
import time
ORIGIN=time.monotonic()
import signal
INITIAL_HANDLERS={s:signal.getsignal(s) for s in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT)}
CLOCK_OWNED=False

def cleanup_clock(primary=None):
    failures=[]
    for action in [lambda:signal.setitimer(signal.ITIMER_REAL,0)]+[lambda s=s,h=h:signal.signal(s,h) for s,h in INITIAL_HANDLERS.items()]:
        try:action()
        except BaseException as e:failures.append(type(e).__name__)
    if failures:
        if primary is not None:primary.add_note('Independent alarm cleanup uncertainty: '+','.join(failures))
        else:raise RuntimeError('Independent alarm cleanup uncertainty: '+','.join(failures))

def enter_startup():
    global CLOCK_OWNED
    if signal.getitimer(signal.ITIMER_REAL)!=(0.,0.):raise RuntimeError('fresh inactive timer required')
    def expired(*_):raise TimeoutError('original whole-program clock')
    try:
        signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,max(0.001,ORIGIN+3000240-time.monotonic()))
    except BaseException as e:
        cleanup_clock(e);raise
    CLOCK_OWNED=True
if __name__=='__main__':enter_startup()
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import selectors
import stat
import subprocess
import sys

HERE = Path(__file__).absolute().parent
READ_CAP = 1024*1024**3
WRITE_CAP = 16*1024**2
STREAM_CAP = 65536


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def sync_directory(path):
    need(time.monotonic()<ORIGIN+3000240,'original directory durability clock')
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
    need(time.monotonic()<ORIGIN+3000240,'directory durability completed before original cutoff')


def owned_directories(path):
    path=Path(path).absolute()
    need('..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)),'ordinary owned directory chain')
    todo=[];cursor=path
    while not cursor.exists():
        need(len(todo)<17,'bounded owned directory depth');todo.append(cursor);cursor=cursor.parent
    need(cursor.is_dir(),'existing operator directory anchor')
    for directory in reversed(todo):
        need(time.monotonic()<ORIGIN+3000240,'original directory creation clock')
        directory.mkdir(mode=0o700);sync_directory(directory);sync_directory(directory.parent)


def freeze_source_file(path):
    os.chmod(path,0o444)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:os.fsync(fd)
    finally:os.close(fd)
    need(time.monotonic()<ORIGIN+3000240,'source mode durable inside original clock')


class IO:
    def __init__(self):
        self.read = self.write = 0
    def capture(self, path, expected, cap=1048576, *, owned_metadata_without_external_pin=False, retain=True, allow_empty=False):
        path = Path(path).absolute()
        need('..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)), 'ordinary observer path')
        need(type(expected) is dict and type(expected.get('bytes')) is int and (0 if allow_empty else 1) <= expected['bytes'] <= cap, 'bounded exact observer pin')
        self.read += expected['bytes']+1
        need(self.read <= READ_CAP and time.monotonic() < ORIGIN+3000240, 'observer read/clock cap')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected['bytes'], 'exact regular observer input')
            chunks, left, digest = [], before.st_size, hashlib.sha256()
            while left:
                b = os.read(fd, min(left, 65536))
                need(b, 'complete observer input')
                digest.update(b)
                if retain: chunks.append(b)
                left -= len(b)
            need(not os.read(fd,1), 'observer EOF')
            fields = lambda s: (s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            need(fields(before)==fields(os.fstat(fd))==fields(path.lstat()), 'stable observer input')
        finally:
            os.close(fd)
        body=b''.join(chunks)
        if not owned_metadata_without_external_pin:
            need({'bytes':before.st_size,'sha256':digest.hexdigest()}=={k:expected[k] for k in ('bytes','sha256')}, 'observer full pin')
        return body
    def save(self, path, body):
        self.write += len(body)
        need(self.write <= WRITE_CAP and time.monotonic() < ORIGIN+3000240, 'observer write/clock cap')
        path=Path(path);owned_directories(path.parent)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
        try:
            v=memoryview(body)
            while v:
                n=os.write(fd,v);need(n>0,'observer complete output');v=v[n:]
            os.fsync(fd)
        finally:
            os.close(fd)
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)
        need(time.monotonic() < ORIGIN+3000240, 'observer durable publication before original cutoff')
        return pin(body)


def encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def parse(raw):
    def pairs(rows):
        d={}
        for k,v in rows:
            need(k not in d,'duplicate observer JSON key');d[k]=v
        return d
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite observer JSON'))


def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod)
    return mod


def observe_child(command, output, io):
    """One owned host child; independent CLI groups/daemon resources need receipts."""
    p=None;selector=None;primary=None;reaped=False;absent=False;counts={'stdout':0,'stderr':0}
    io.save(output/'CHILD_INTENT.json',encoded({'schema':'language_building_blocks_outer_child_intent_v1',
        'original_origin':ORIGIN,'publication_end':ORIGIN+3000120,'outer_end':ORIGIN+3000240,
        'spawn_to_journal_gap_possible':True,'forced_transitive_custody_complete':False}))
    try:
        p=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                           start_new_session=True,bufsize=0)
        io.save(output/'CHILD_STARTED.json',encoded({'pid':p.pid,'pgid':p.pid,'original_origin':ORIGIN}))
        selector=selectors.DefaultSelector()
        for key,stream in (('stdout',p.stdout),('stderr',p.stderr)):
            os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,key)
        while selector.get_map():
            left=ORIGIN+3000120-time.monotonic()
            need(left>0,'original controller publication deadline')
            for key,_ in selector.select(min(.1,left)):
                try:b=os.read(key.fileobj.fileno(),min(65536,STREAM_CAP+1-counts[key.data]))
                except BlockingIOError:continue
                if not b:selector.unregister(key.fileobj);continue
                counts[key.data]+=len(b);need(counts[key.data]<=STREAM_CAP,'bounded discarded child streams')
        remaining=ORIGIN+3000120-time.monotonic()
        need(remaining>0,'original remaining natural-exit interval')
        rc=p.wait(timeout=remaining);reaped=True
        need(time.monotonic()<ORIGIN+3000120,'actual natural exit before original publication cutoff')
        need(type(rc)is int and rc==0,'natural controller exit zero')
        try:os.killpg(p.pid,0)
        except ProcessLookupError:absent=True
        need(absent,'owned controller group absent')
        need(counts=={'stdout':0,'stderr':0},'successful controller silent')
        return {'returncode':0,'natural_exit':True,'child_reaped':True,'owned_group_absence_observed':True,
                'terminal_bytes':counts,'original_origin':ORIGIN,'elapsed_seconds':time.monotonic()-ORIGIN,
                'forced_transitive_custody_complete':False}
    except BaseException as error:
        primary=error
        raise
    finally:
        failures=[]
        if p is not None and not absent:
            for sig in (signal.SIGTERM,signal.SIGKILL):
                try:os.killpg(p.pid,sig)
                except ProcessLookupError:break
                except BaseException as error:failures.append(type(error).__name__)
            try:
                remaining=ORIGIN+3000240-time.monotonic()
                need(remaining>0,'no invented cleanup time beyond original outer deadline')
                p.wait(timeout=min(5,remaining));reaped=True
            except BaseException as error:failures.append(type(error).__name__)
        if selector is not None:
            try:selector.close()
            except BaseException as error:failures.append(type(error).__name__)
        if p is not None:
            for stream in (p.stdout,p.stderr):
                if stream is not None:
                    try:stream.close()
                    except BaseException as error:failures.append(type(error).__name__)
        if failures:
            if primary is not None:primary.add_note('Independent outer cleanup uncertainty: '+','.join(failures))
            else:raise RuntimeError('Independent outer cleanup uncertainty: '+','.join(failures))


def verify_collection(io,root,selected,controller,engine):
    from verification import verify
    return verify(io,root,selected,controller,engine,ORIGIN)

def main(argv=None):
    p=argparse.ArgumentParser(allow_abbrev=False)
    p.add_argument('--selection',required=True);p.add_argument('--selection-sha256',required=True)
    p.add_argument('--output',required=True)
    a=p.parse_args(argv);io=IO();primary=None
    try:
        s=Path(a.selection).stat()
        raw=io.capture(a.selection,{'bytes':s.st_size,'sha256':a.selection_sha256})
        selected=parse(raw)
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(2147483648,2147483648)) # explicit prospective observer memory ceiling
        need(selected.get('operation_selected')is True and selected.get('schema')=='language_building_blocks_complete_program_operation_v1',
             'exact external root selection before any operand')
        manifest_raw=io.capture(HERE/'SOURCE_MANIFEST.json',selected['source_manifest'],262144)
        manifest=parse(manifest_raw)
        need(type(manifest.get('files'))is dict and 1<=len(manifest['files'])<=128 and
             sum(d['bytes'] for d in manifest['files'].values())<=4*1024**2,'bounded complete original source')
        bodies={}
        for name,d in manifest['files'].items():
            q=Path(name);need(not q.is_absolute() and '..'not in q.parts and q.as_posix()==name,'source relative identity')
            bodies[name]=io.capture(HERE/q,d,allow_empty=True)
        out=Path(a.output).absolute()
        need(not out.exists() and not any(x.is_symlink() for x in (out,*out.parents)),'fresh observer attempt')
        need(out.parent.is_dir(),'existing operator parent for fresh observer root')
        owned_directories(out)
        fs=os.statvfs(out)
        need(fs.f_bavail*fs.f_frsize>=2*1024**3+selected['other_future_bytes']+selected['retained_cap']+16*1024**2,'full future capacity before child')
        for name,body in bodies.items():
            io.save(out/'source'/name,body);freeze_source_file(out/'source'/name)
        io.save(out/'source/SOURCE_MANIFEST.json',manifest_raw);freeze_source_file(out/'source/SOURCE_MANIFEST.json')
        for directory in sorted((q for q in (out/'source').rglob('*') if q.is_dir()),key=lambda q:len(q.parts),reverse=True):
            os.chmod(directory,0o555);sync_directory(directory)
        os.chmod(out/'source',0o555);sync_directory(out/'source');sync_directory(out)
        io.save(out/'SELECTION.json',raw)
        sys.path.insert(0,str(out/'source'))
        controller=load('language_building_blocks_observed_controller',out/'source/controller.py')
        controller.selected(selected)
        engine=load('language_building_blocks_observed_engine',out/'source/engine/native.py')
        command=[sys.executable,'-I','-S','-B',str(out/'source/controller.py'),'--selection',str(out/'SELECTION.json'),
                 '--selection-sha256',pin(raw)['sha256'],'--output',str(out/'run'),'--origin',repr(ORIGIN)]
        child=observe_child(command,out,io)
        collected=verify_collection(io,out/'run',selected,controller,engine)
        need(time.monotonic()<ORIGIN+3000240,'original whole observation clock')
        io.save(out/'OBSERVED.json',encoded({'schema':'language_building_blocks_original_whole_command_observed_v1','source':selected['source_manifest'],
            'collection':collected,'child':child,'original_phase_records_checked':213,'original_trusted_host_records_checked':71,'observer_read_bytes':io.read,
            'observer_write_bytes_before_final':io.write,'runtime_qualified':False,'scientific_qualification':False,
            'full_paper_reproduction':False,'private_grade_called':False,'automatic_retry_authorized':False,
            'forced_stop_independent_host_and_daemon_state':'unknown'}))
        need(time.monotonic()<ORIGIN+3000240,'final success before original outer clock while alarm active')
        return 0
    except BaseException as error:
        primary=error
        raise
    finally:
        if CLOCK_OWNED:cleanup_clock(primary)


if __name__=='__main__':
    result = main()
    need(time.monotonic() < ORIGIN + 3000240, 'standalone completion after cleanup before original outer deadline')
    raise SystemExit(result)
