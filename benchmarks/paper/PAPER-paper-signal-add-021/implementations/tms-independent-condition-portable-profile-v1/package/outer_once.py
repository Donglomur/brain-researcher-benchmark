"""One exact prospective inner argv and its original terminal/capture boundary.

Adapted narrowly from P17's accepted outer V3. Source selection does not dispatch
a candidate run. The root-selected immutable manifest binds each fresh attempt. All captures and failure details remain in the private output root.
"""
import argparse,hashlib,json,os,selectors,signal,stat,subprocess,sys,time
from pathlib import Path

SOURCE=Path(__file__).absolute().parent
EXTERNAL=None
HOST_PYTHON=None
CONFIG_PATH=None
CONFIG_SHA=None
EXECUTION_LOCK_SHA256=None
CAP=1048576


def portable_bootstrap(source, lock_sha, config_path, config_sha):
    # Only this authenticated owner source is imported; never participant code.
    import importlib.util
    def take(p, cap):
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            a=os.fstat(fd)
            if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or not 0<a.st_size<=cap:
                raise ValueError('bounded portable source')
            parts=[];left=a.st_size
            while left:
                b=os.read(fd,min(left,65536))
                if not b:raise ValueError('short portable source')
                parts.append(b);left-=len(b)
            z=os.fstat(fd);n=Path(p).lstat()
            fields=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
            if any(getattr(a,k)!=getattr(z,k) or getattr(a,k)!=getattr(n,k) for k in fields):
                raise ValueError('unstable portable source')
            return b''.join(parts)
        finally:os.close(fd)
    raw=take(source/'PORTABLE_SOURCE_LOCK.json',65536)
    if hashlib.sha256(raw).hexdigest()!=lock_sha:raise ValueError('portable source lock identity')
    lock=json.loads(raw);entry=lock['members']['portable_config.py']
    body=take(source/'portable_config.py',1048576)
    if (len(body),hashlib.sha256(body).hexdigest())!=(entry['bytes'],entry['sha256']):
        raise ValueError('portable configuration source identity')
    if 'portable_config' in sys.modules:raise ValueError('fresh portable configuration namespace')
    spec=importlib.util.spec_from_file_location('portable_config',source/'portable_config.py')
    mod=importlib.util.module_from_spec(spec);sys.modules['portable_config']=mod
    exec(compile(body,str(source/'portable_config.py'),'exec'),mod.__dict__)
    bodies,total=mod.load_source(str(source),lock_sha)
    cfg=mod.load(config_path,config_sha,source_bodies=bodies)
    mod.state()['source_lock_sha256']=lock_sha
    return mod,cfg,bodies,total+len(raw)+len(body)+mod.state()['config_bytes']

def checked_attempt(value):
    if type(value) is not str or not (1 <= len(value) <= 64) or value[0] not in 'abcdefghijklmnopqrstuvwxyz0123456789' or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in value):
        raise ValueError('bounded_plain_attempt_id')
    return value

def admit_manifest(raw, expected_sha, attempt):
    checked_attempt(attempt)
    if type(expected_sha) is not str or len(expected_sha) != 64 or any(c not in '0123456789abcdef' for c in expected_sha):
        raise ValueError('manifest_sha256')
    if not (0 < len(raw) <= 65536) or hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError('root_manifest_identity')
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError('duplicate_manifest_key')
            out[key] = value
        return out
    obj = json.loads(raw, object_pairs_hook=pairs)
    if type(obj) is not dict or set(obj) != {'schema', 'attempt_id', 'selection'} or obj['schema'] != 'tms_local_method_reconstruction_run_v1' or obj['attempt_id'] != attempt or type(obj['selection']) is not dict or type(obj['selection'].get('comparator_calibration')) is not bool:
        raise ValueError('closed_root_run_manifest')
    return obj['selection']

def absent(pid):
    try:os.killpg(pid,0)
    except ProcessLookupError:return True
    except BaseException:return None
    return False

def main():
    global EXTERNAL,HOST_PYTHON,CONFIG_PATH,CONFIG_SHA,EXECUTION_LOCK_SHA256
    start=time.monotonic();proc=None;confirmed_absent=False;owner_authority=False
    owner_signals={signal.SIGALRM,signal.SIGTERM,signal.SIGINT}
    def reap_retire_owner():
        nonlocal owner_authority
        previous=signal.pthread_sigmask(signal.SIG_BLOCK,owner_signals)
        try:
            return None if proc is None else proc.poll()
        finally:
            if proc is not None and proc.returncode is not None:
                owner_authority=False
            signal.pthread_sigmask(signal.SIG_SETMASK,previous)
    def bounded_reap_owner(until):
        while True:
            code=reap_retire_owner()
            if code is not None:return code
            remaining=until-time.monotonic()
            if remaining<=0:return None
            time.sleep(min(.01,remaining))
    def request_fatal_cleanup():
        # An unreaped exact Popen reserves the PID. A reaped owner never retains
        # numeric signal authority, even if some group observation is unclear.
        previous=signal.pthread_sigmask(signal.SIG_BLOCK,owner_signals)
        try:
            if owner_authority and proc is not None and proc.returncode is None:
                os.kill(proc.pid,signal.SIGUSR1)
                return True
            return False
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK,previous)
    def fatal(*unused):
        for sig in owner_signals:signal.signal(sig,signal.SIG_IGN)
        # Never kill the owner ahead of its separate-client cleanup. It retains
        # its registry and original hard horizon. Unobserved cleanup is failure.
        try:request_fatal_cleanup()
        except BaseException:pass
        os._exit(124) # No successful closure beyond the original fatal horizon.
    def cancelled(*unused):
        signal.signal(signal.SIGTERM,signal.SIG_IGN)
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        raise InterruptedError('outer_soft_cancellation')
    signal.signal(signal.SIGALRM,fatal)
    signal.signal(signal.SIGTERM,cancelled)
    signal.signal(signal.SIGINT,cancelled)
    initial_end=start+390;remaining=initial_end-time.monotonic()
    assert remaining>0;signal.setitimer(signal.ITIMER_REAL,remaining)
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt-id',required=True)
    parser.add_argument('--run-manifest-sha256',required=True)
    parser.add_argument('--source-lock-sha256',required=True)
    parser.add_argument('--config',required=True)
    parser.add_argument('--config-sha256',required=True)
    args=parser.parse_args();attempt=checked_attempt(args.attempt_id)
    pc,cfg,_,bootstrap_reads=portable_bootstrap(SOURCE,args.source_lock_sha256,args.config,args.config_sha256)
    bootstrap_reads+=pc.admit_host(cfg);pc.preflight_assets(cfg)
    EXTERNAL=Path(cfg['workspace']);HOST_PYTHON=cfg['runtime']['host_python']['path']
    CONFIG_PATH=args.config;CONFIG_SHA=args.config_sha256;EXECUTION_LOCK_SHA256=args.source_lock_sha256
    sha=args.run_manifest_sha256;seconds=390;mode='benchmark'
    end=start+seconds;work=end-5;remaining=end-time.monotonic()
    assert remaining>0;signal.setitimer(signal.ITIMER_REAL,remaining)
    os.umask(0o077);reads=reserved=written=0
    path=EXTERNAL/'selections'/(attempt+'.json')
    assert not any(x.is_symlink() for x in (path,*path.parents))
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        first=os.fstat(fd)
        assert stat.S_ISREG(first.st_mode) and first.st_nlink==1 and stat.S_IMODE(first.st_mode)==0o400 and 0<first.st_size<=65536
        extent=first.st_size
        reads+=extent;assert reads<=CAP;data=bytearray()
        while len(data)<extent:
            assert time.monotonic()<end
            part=os.read(fd,extent-len(data));assert part;data.extend(part)
        last=os.fstat(fd);named=path.lstat()
        keys=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
        assert all(getattr(first,k)==getattr(last,k)==getattr(named,k) for k in keys)
    finally:os.close(fd)
    raw=bytes(data);assert (len(raw),hashlib.sha256(raw).hexdigest())==(extent,sha)
    selected=admit_manifest(raw,sha,attempt)
    argv=[HOST_PYTHON,'-I','-S','-B',str(SOURCE/'run_once.py'),
          '--mode',mode,'--source-lock-sha256',EXECUTION_LOCK_SHA256,
          '--root-selection-sha256',sha,'--attempt-id',attempt,
          '--config',CONFIG_PATH,'--config-sha256',CONFIG_SHA]
    inv={'argv':argv,'cwd':str(SOURCE),'mode':mode,'attempt_id':attempt,
         'run_manifest':{'path':str(path),'bytes':extent,'sha256':sha},
         'comparator_calibration':selected['comparator_calibration']}
    assert not any(x.is_symlink() for x in (EXTERNAL,*EXTERNAL.parents)) and EXTERNAL.is_dir()
    attempt_root=EXTERNAL/'attempts'/attempt
    assert not any(x.is_symlink() for x in (attempt_root.parent,*attempt_root.parent.parents)) and attempt_root.parent.is_dir()
    attempt_root.mkdir(mode=0o700) # Exclusive creation makes every selected run single-use.
    root=attempt_root/'outer-benchmark-01';root.mkdir(mode=0o700)
    rec={'schema':'tms_p21_original_outer_capture_v1','argv':argv,'cwd':inv['cwd'],'mode':mode,
         'run_manifest':{'path':str(path),'bytes':extent,'sha256':sha},'attempt_id':attempt,
         'inner_invocation':inv,'original_total_seconds':seconds,'bootstrap_managed_reads':bootstrap_reads,
         'portable_config_sha256':CONFIG_SHA,
         'child_capture_work_seconds':seconds-5,'dispatched':False,'EOF':[],'exit_code':None,
         'reaped':False,'group_absent':None,'signals':[],'errors':[],
         'observed_pipe_bytes_at_least':{'stdout':0,'stderr':0}}
    def save(name,value):
        nonlocal reserved,written
        body=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
        assert len(body)<=65536 and reserved+len(body)<=CAP and time.monotonic()<end
        reserved+=len(body)
        out=os.open(root/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
        errors=[]
        try:
            at=0
            while at<len(body):
                assert time.monotonic()<end
                n=os.write(out,body[at:]);assert n>0;at+=n;written+=n
        except BaseException as error:errors.append(error)
        finally:
            for action in (lambda:os.fsync(out),lambda:os.fchmod(out,0o400),lambda:os.close(out)):
                try:action()
                except BaseException as error:errors.append(error)
        if errors:raise RuntimeError('outer metadata persistence:'+','.join(type(x).__name__ for x in errors)) from errors[0]
    save('STARTED.private.json',rec)
    sel=None;files={};streams={};bodies={'stdout':bytearray(),'stderr':bytearray()}
    try:
        assert reserved+131072<=CAP;reserved+=131072
        for stream_name in bodies:files[stream_name]=os.open(root/(stream_name+'.bin'),os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        previous=signal.pthread_sigmask(signal.SIG_BLOCK,owner_signals)
        try:
            proc=subprocess.Popen(argv,cwd=inv['cwd'],stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            owner_authority=True
            rec['dispatched']=True;rec['pid']=proc.pid
            rec['registered_before_signal_unblock']=True
            streams={'stdout':proc.stdout,'stderr':proc.stderr}
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK,previous)
        save('DISPATCHED.private.json',rec)
        sel=selectors.DefaultSelector()
        for stream_name,stream in streams.items():
            os.set_blocking(stream.fileno(),False);sel.register(stream,selectors.EVENT_READ,stream_name)
        while sel.get_map() or reap_retire_owner() is None:
            assert time.monotonic()<work,'outer_work_deadline'
            for key,_ in sel.select(min(.05,max(0,work-time.monotonic()))):
                stream_name=key.data;request=min(65536,65536-len(bodies[stream_name])+1)
                assert reads+request<=CAP,'outer_combined_read_limit'
                block=os.read(key.fileobj.fileno(),request);reads+=len(block)
                if not block:rec['EOF'].append(stream_name);sel.unregister(key.fileobj);continue
                rec['observed_pipe_bytes_at_least'][stream_name]+=len(block)
                available=65536-len(bodies[stream_name]);retained=block[:available];at=0
                while at<len(retained):
                    assert time.monotonic()<end
                    n=os.write(files[stream_name],retained[at:]);assert n>0
                    bodies[stream_name].extend(retained[at:at+n]);at+=n;written+=n
                assert len(block)<=available,'outer_stream_extent'
        rec['exit_code']=reap_retire_owner();rec['reaped']=rec['exit_code'] is not None
    except BaseException as error:
        rec['errors'].append({'phase':'work','class':type(error).__name__,'message':str(error)[:2048]})
    finally:
        signal.signal(signal.SIGTERM,signal.SIG_IGN)
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        if proc is not None:
            if reap_retire_owner() is None:
                try:
                    if request_fatal_cleanup():
                        rec['signals'].append('SIGUSR1_owned_owner_fatal_cleanup_request')
                except ProcessLookupError:pass
                except BaseException as error:rec['errors'].append({'phase':'fatal_cleanup_request','class':type(error).__name__})
            try:
                code=bounded_reap_owner(end)
                rec['exit_code']=code;rec['reaped']=code is not None
            except BaseException as error:rec['errors'].append({'phase':'reap','class':type(error).__name__})
            rec['group_absent']=absent(proc.pid);confirmed_absent=rec['group_absent'] is True
            rec['owner_signal_authority_retired']=owner_authority is False
            rec['independent_owner_SIGKILL_used']=False
        if sel is not None:
            try:sel.close()
            except BaseException as error:rec['errors'].append({'phase':'selector_close','class':type(error).__name__})
        for stream_name,stream in streams.items():
            try:stream.close()
            except BaseException as error:rec['errors'].append({'phase':stream_name+'_close','class':type(error).__name__})
        for stream_name,out in files.items():
            for phase,action in [('fsync',lambda out=out:os.fsync(out)),('mode',lambda out=out:os.fchmod(out,0o400)),('close',lambda out=out:os.close(out))]:
                try:action()
                except BaseException as error:rec['errors'].append({'phase':stream_name+'_'+phase,'class':type(error).__name__})
            rec[stream_name]={'bytes':len(bodies[stream_name]),'sha256':hashlib.sha256(bodies[stream_name]).hexdigest()}
    rec['EOF'].sort();rec['elapsed_before_receipt']=time.monotonic()-start
    rec['complete']=(type(rec['exit_code']) is int and rec['exit_code']==0 and rec['reaped'] is True and
                     rec['group_absent'] is True and rec['EOF']==['stderr','stdout'] and
                     not rec['signals'] and not rec['errors'] and time.monotonic()<end)
    rec['read_bytes']=reads;rec['reserved_write_bytes_before_receipt']=reserved
    rec['successful_write_bytes_before_receipt']=written;rec['outer_read_write_cap_each']=CAP
    save('OUTER_RESULT.private.json',rec);os.chmod(root,0o500)
    assert time.monotonic()<end,'outer_final_original_deadline'
    print(json.dumps({'outer_complete':rec['complete'],'mode':mode,'exit_code':rec['exit_code'],
                      'elapsed':time.monotonic()-start,'reaped':rec['reaped'],
                      'group_absent':rec['group_absent'],'EOF':rec['EOF'],
                      'signals':rec['signals'],'errors':rec['errors']}),flush=True)
    assert time.monotonic()<end,'outer_final_transport_deadline'
    return 0 if rec['complete'] else 1

if __name__=='__main__':raise SystemExit(main())
