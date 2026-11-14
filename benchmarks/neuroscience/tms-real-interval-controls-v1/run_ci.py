"""Bounded Linux owner for unchanged invented interval controls; no real data."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import resource
import signal
import stat
import subprocess
import sys
import time
import types

ROOT = Path(__file__).absolute().parent
NAMES = {'kernel.py', 'certificate.py', 'scorer.py', 'controls.py', 'FIXTURE.json', 'run_ci.py'}
THREADS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS')
LIMIT = 2 * 1024 * 1024
RSS_LIMIT = 256 * 1024 * 1024


def require(value, message):
    if not value:
        raise ValueError(message)


def ordinary(path, cap=1048576):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 <= before.st_size <= cap, 'bounded ordinary file')
        parts, left = [], before.st_size
        while left:
            block = os.read(fd, min(65536, left))
            require(bool(block), 'complete ordinary file')
            parts.append(block); left -= len(block)
        sig = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(sig(before) == sig(os.fstat(fd)), 'stable file')
        return b''.join(parts)
    finally:
        os.close(fd)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def encode(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))+'\n').encode()


def write(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())


def selected(expected):
    raw = ordinary(ROOT/'SOURCE_LOCK.json')
    require(pin(raw)['sha256'] == expected, 'selected execution lock')
    lock = json.loads(raw)
    require(set(lock) == {'schema','members'} and lock['schema'] == 'tms_interval_public_inert_lock_v1' and set(lock['members']) == NAMES, 'complete public source closure')
    bodies = {}
    for name, identity in lock['members'].items():
        body = ordinary(ROOT/name)
        require(pin(body) == identity, 'selected source identity')
        bodies[name] = body
    return bodies


def runtime():
    require(sys.platform == 'linux' and platform.machine() == 'x86_64' and sys.version_info[:3] == (3,11,18), 'selected Linux CPython3.11.18 runtime')
    require(sys.implementation.name == 'cpython' and sys.byteorder == 'little', 'CPython little-endian runtime')
    require(sys.flags.isolated == sys.flags.no_site == sys.flags.dont_write_bytecode == sys.flags.ignore_environment == 1, 'isolated no-site no-bytecode runtime')
    require((sys.float_info.radix, sys.float_info.mant_dig, sys.float_info.max_exp, sys.float_info.min_exp) == (2,53,1024,-1021), 'binary64 runtime')
    executable = Path(sys.executable).resolve()
    return {'schema':'tms_interval_public_existing_runtime_v1','version':sys.version,'executable':str(executable),
            'executable_pin':pin(ordinary(executable,4194304)),'platform':sys.platform,'machine':platform.machine(),
            'full_stdlib_os_loader_body_closure':False,'scientific_runtime_qualified':False}


def worker(args):
    start = time.monotonic()
    require(start < args.deadline <= start+55, 'inherited work deadline')
    def expired(*unused):
        raise TimeoutError('original worker deadline')
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, args.deadline-time.monotonic())
    bodies = selected(args.selection_sha256)
    out = Path(args.out)
    raw_runtime = ordinary(out/'RUNTIME.json',65536)
    require(pin(raw_runtime)['sha256'] == args.runtime_sha256 and json.loads(raw_runtime) == runtime(), 'owned runtime descriptor join')
    require(all(os.environ.get(name) == '1' for name in THREADS), 'library thread policy')
    work = out/'work'
    work.mkdir(mode=0o700)
    retained, files = 0, []
    def save(name, body):
        nonlocal retained
        require(type(name) is str and '/' not in name and not name.startswith('.') and type(body) is bytes, 'finite output name/body')
        require(retained+len(body) <= LIMIT-65536 and time.monotonic() < args.deadline, 'worker retention/deadline')
        write(work/name, body)
        retained += len(body)
        files.append({'name':name,**pin(body)})
    try:
        for name in ('kernel','certificate','scorer','controls'):
            module = types.ModuleType(name)
            module.__file__ = str(ROOT/(name+'.py'))
            sys.modules[name] = module
            exec(compile(bodies[name+'.py'],module.__file__,'exec'),module.__dict__)
        k,c = sys.modules['kernel'],sys.modules['certificate']
        budget = k.Budget(deadline=args.deadline,max_calls=64,max_values=4096)
        context = c.FixtureContext(pin(bodies['FIXTURE.json'])['sha256'],args.selection_sha256,args.runtime_sha256,'public-inert-qualification-01')
        report = sys.modules['controls'].run(budget,context,save)
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        require(rss <= RSS_LIMIT and time.monotonic() < args.deadline, 'worker observed RSS/deadline')
        result = {'schema':'tms_interval_public_inert_worker_v1','status':'PASSED','source_lock_sha256':args.selection_sha256,
                  'runtime_sha256':args.runtime_sha256,'absolute_deadline':args.deadline,
                  'elapsed_seconds_before_receipt':time.monotonic()-start,'observed_peak_rss_bytes':rss,
                  'control_count':report['control_count'],'scalar_calls':budget.calls,
                  'supplied_raw_entries':budget.supplied_values,'reached_group_entries':budget.values,
                  'combined_invented_entries':report['combined_supplied_raw_and_candidate_serialization_values'],
                  'files_before_receipt':list(files),'retained_bytes_before_receipt':retained,
                  'authentic_reads':0,'native_runs':0,'model_calls':0,'production_qualified':False}
        save('RESULT.json',encode(result))
        for item in work.iterdir(): item.chmod(0o400)
        work.chmod(0o500)
        print(json.dumps({'status':'PASSED','controls':report['control_count'],'source_lock_sha256':args.selection_sha256},sort_keys=True),flush=True)
        require(time.monotonic() < args.deadline, 'worker final transport deadline')
        return 0
    except BaseException as exc:
        work.chmod(0o700)
        write(work/'FAILURE.json',encode({'status':'FAILED','error_type':type(exc).__name__,'error':str(exc)[:1024],
              'source_lock_sha256':args.selection_sha256,'elapsed_seconds':time.monotonic()-start,'no_retry':True}))
        for item in work.iterdir(): item.chmod(0o400)
        work.chmod(0o500)
        raise


def owner(args, start, deadline, state):
    bodies = selected(args.selection_sha256)
    descriptor = runtime()
    out = Path(args.out).absolute()
    require(out.parent.is_dir() and not out.exists(), 'fresh private artifact directory')
    out.mkdir(mode=0o700)
    raw_runtime = encode(descriptor)
    write(out/'RUNTIME.json',raw_runtime)
    work_deadline = start+55
    cmd = [sys.executable,'-I','-S','-B',str(ROOT/'run_ci.py'),'--worker','--out',str(out),
           '--selection-sha256',args.selection_sha256,'--runtime-sha256',pin(raw_runtime)['sha256'],'--deadline',repr(work_deadline)]
    write(out/'STARTED.json',encode({'argv':cmd,'source_lock_sha256':args.selection_sha256,
          'monotonic_start':start,'original_deadline':deadline,'work_deadline':work_deadline,'attempt':1}))
    captures,errors,signals = [],[],[]
    timed_out = False
    def group_absent():
        child = state.get('child')
        if child is None: return True
        try: os.killpg(child.pid,0); return False
        except ProcessLookupError: return True
        except OSError as exc: errors.append('group_observation:'+type(exc).__name__); return None
    def send(sig):
        child = state.get('child')
        if child is None: return
        try: os.killpg(child.pid,sig); signals.append(signal.Signals(sig).name)
        except ProcessLookupError: pass
        except OSError as exc: errors.append('group_signal:'+type(exc).__name__)
    def remaining(): return max(0.001,deadline-time.monotonic())
    try:
        for name in ('WORKER_STDOUT.txt','WORKER_STDERR.txt'):
            fd = os.open(out/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
            captures.append(os.fdopen(fd,'wb'))
        child = subprocess.Popen(cmd,stdout=captures[0],stderr=captures[1],start_new_session=True,
                                 cwd=ROOT,env={**os.environ,**{name:'1' for name in THREADS}})
        state['child'] = child
        write(out/'SPAWNED.json',encode({'pid':child.pid,'owned_process_group':child.pid}))
        child.wait(timeout=max(0.001,work_deadline-time.monotonic()))
    except subprocess.TimeoutExpired:
        timed_out = True;errors.append('work_timeout')
    except BaseException as exc:
        errors.append('owned_operation:'+type(exc).__name__)
    finally:
        child = state.get('child')
        if child is not None:
            try:
                if child.poll() is None or group_absent() is False:
                    send(signal.SIGTERM)
                    try: child.wait(timeout=min(1,remaining()))
                    except subprocess.TimeoutExpired: pass
                if child.poll() is None or group_absent() is False: send(signal.SIGKILL)
                if child.poll() is None:
                    try: child.wait(timeout=remaining())
                    except subprocess.TimeoutExpired: errors.append('reap_timeout')
            except BaseException as exc:
                errors.append('cleanup:'+type(exc).__name__);send(signal.SIGKILL)
                try: child.wait(timeout=remaining())
                except BaseException as last: errors.append('final_reap:'+type(last).__name__)
        for stream in captures:
            try: stream.flush();os.fsync(stream.fileno());stream.close()
            except BaseException as exc: errors.append('capture_close:'+type(exc).__name__)
    closed = len(captures)==2 and all(x.closed for x in captures)
    absent = group_absent()
    reaped = child is not None and child.poll() is not None
    streams, observed = {},None
    try:
        if closed:
            for name in ('WORKER_STDOUT.txt','WORKER_STDERR.txt'): streams[name]=pin(ordinary(out/name,262144))
        if (out/'work/RESULT.json').exists(): observed=json.loads(ordinary(out/'work/RESULT.json',65536))
    except BaseException as exc: errors.append('result_admission:'+type(exc).__name__)
    owner_peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    child_peak=observed.get('observed_peak_rss_bytes',RSS_LIMIT+1) if observed else RSS_LIMIT+1
    retained=sum(x.lstat().st_size for x in out.rglob('*') if x.is_file())
    success=(child is not None and child.returncode==0 and reaped and absent is True and closed
             and not timed_out and not errors and observed is not None and observed.get('status')=='PASSED'
             and observed.get('source_lock_sha256')==args.selection_sha256
             and observed.get('runtime_sha256')==pin(raw_runtime)['sha256'] and observed.get('absolute_deadline')==work_deadline
             and observed.get('control_count')==359 and observed.get('scalar_calls')==21
             and observed.get('supplied_raw_entries')==540 and observed.get('reached_group_entries')==435
             and observed.get('combined_invented_entries')==1780
             and owner_peak+child_peak<=RSS_LIMIT and retained+32768<=LIMIT
             and not (out/'work/FAILURE.json').exists() and time.monotonic()<deadline)
    receipt={'schema':'tms_interval_public_inert_owner_v1','status':'PASSED' if success else 'FAILED',
             'source_lock_sha256':args.selection_sha256,'returncode':child.returncode if child else None,
             'worker_attempts':int(child is not None),'reaped':reaped,'owned_group_absent':absent,
             'regular_captures_closed':closed,'complete_capture_after_owner_closure':closed and reaped and absent is True,
             'timed_out':timed_out,'errors':errors,'signals':signals,'stream_pins':streams,
             'elapsed_seconds_before_receipt':time.monotonic()-start,'retained_bytes_before_receipt':retained,
             'observed_owner_peak_rss_bytes':owner_peak,'observed_child_peak_rss_bytes':child_peak,
             'sum_of_process_peaks_bytes':owner_peak+child_peak,'hard_memory_or_CPU_quota':False,
             'authentic_reads':0,'native_runs':0,'model_calls':0,'scientific_qualification':False,'no_retry':True}
    write(out/'OWNER_RESULT.json',encode(receipt))
    manifest={}
    for path in sorted(out.rglob('*')):
        if path.is_file(): manifest[str(path.relative_to(out))]=pin(ordinary(path,LIMIT))
    require(sum(x['bytes'] for x in manifest.values())+16384<=LIMIT,'complete artifact retention reserve')
    write(out/'ARTIFACT_MANIFEST.json',encode({'schema':'tms_interval_inert_artifact_manifest_v1','members':manifest,
          'files':len(manifest),'bytes':sum(x['bytes'] for x in manifest.values()),'includes_complete_fixture_outputs':True}))
    for path in out.rglob('*'):
        if path.is_file(): path.chmod(0o400)
    out.chmod(0o500)
    print(json.dumps(receipt,sort_keys=True),flush=True)
    require(time.monotonic()<deadline,'owner final original transport deadline')
    return 0 if success else 1


def main():
    start=time.monotonic();deadline=start+60;state={}
    def fatal(*unused):
        child=state.get('child')
        if child is not None:
            try:os.killpg(child.pid,signal.SIGKILL)
            except OSError:pass
        os._exit(124)
    # Owner timer starts before source, runtime or output-path IO. The worker
    # replaces it with the inherited55s deadline before its source IO.
    signal.signal(signal.SIGALRM,fatal);signal.setitimer(signal.ITIMER_REAL,60)
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--out',required=True)
    parser.add_argument('--selection-sha256',required=True)
    parser.add_argument('--runtime-sha256')
    parser.add_argument('--deadline',type=float)
    args=parser.parse_args()
    return worker(args) if args.worker else owner(args,start,deadline,state)


if __name__=='__main__':
    raise SystemExit(main())
