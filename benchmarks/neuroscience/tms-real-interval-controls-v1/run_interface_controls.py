"""Run the finite invented closed-interface checks; never run a candidate."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import resource
import signal
import stat
import sys
import tempfile
import time
import traceback
import types

ROOT = Path(__file__).absolute().parent
NAMES = ('kernel.py','certificate.py','scorer.py','rounding.py',
         'closed_interface.py','interface_controls.py','run_interface_controls.py')
READ_LIMIT = 1048576
WRITE_LIMIT = 2097152
RSS_LIMIT = 268435456

def require(value, message):
    if not value:
        raise ValueError(message)

def pin(body):
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def encode(value):
    return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()

def main():
    start = time.monotonic(); deadline = start+30
    def expired(*_):
        raise TimeoutError('original thirty-second control deadline')
    signal.signal(signal.SIGALRM,expired)
    signal.setitimer(signal.ITIMER_REAL,30)
    parser = argparse.ArgumentParser()
    parser.add_argument('--out',required=True)
    parser.add_argument('--selection-sha256',required=True)
    args = parser.parse_args()
    require(sys.implementation.name=='cpython' and sys.version_info[:2]==(3,11) and
            sys.platform in ('darwin','linux') and sys.byteorder=='little' and
            (sys.float_info.radix,sys.float_info.mant_dig,sys.float_info.max_exp)==(2,53,1024),
            'CPython3.11 binary64 runtime')
    require(sys.flags.isolated==sys.flags.no_site==sys.flags.dont_write_bytecode==1,
            'isolated no-site no-bytecode invocation')
    reads=0
    def read(path):
        nonlocal reads
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            a=os.fstat(fd)
            require(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and 0<=a.st_size<=262144,
                    'bounded ordinary source')
            require(reads+a.st_size<=READ_LIMIT,'source read ceiling')
            pieces=[];left=a.st_size
            while left:
                part=os.read(fd,min(left,65536));require(bool(part),'complete source')
                pieces.append(part);reads+=len(part);left-=len(part)
            z=os.fstat(fd);named=Path(path).lstat()
            keys=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
            require(all(getattr(a,k)==getattr(z,k)==getattr(named,k) for k in keys),'stable source')
            return b''.join(pieces)
        finally:
            os.close(fd)
    lock_raw=read(ROOT/'INTERFACE_SOURCE_LOCK.json')
    require(hashlib.sha256(lock_raw).hexdigest()==args.selection_sha256,'selected interface source lock')
    def unique(items):
        result={}
        for key,value in items:
            require(key not in result,'duplicate source lock key');result[key]=value
        return result
    lock=json.loads(lock_raw,object_pairs_hook=unique)
    require(set(lock)=={'schema','members'} and lock['schema']=='tms_closed_interface_inert_source_v1'
            and set(lock['members'])==set(NAMES),'complete interface source closure')
    bodies={}
    for name in NAMES:
        raw=read(ROOT/name);require(pin(raw)==lock['members'][name],'source identity')
        bodies[name]=raw
    out=Path(args.out).absolute()
    require(not any(p.is_symlink() for p in (out,*out.parents)) and out.parent.is_dir(),
            'fresh ordinary artifact parent')
    out.mkdir(mode=0o700)
    retained=0;members=[]
    def save(name,body):
        nonlocal retained
        require(type(name) is str and name and '/' not in name and '\\' not in name and
                not name.startswith('.') and type(body) is bytes,'finite artifact name/body')
        require(retained+len(body)<=WRITE_LIMIT-16384,'artifact retention ceiling')
        fd=os.open(out/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            at=0
            while at<len(body):
                count=os.write(fd,body[at:]);require(count>0,'complete artifact write');at+=count
            os.fsync(fd);os.fchmod(fd,0o400)
        finally:
            os.close(fd)
        retained+=len(body);members.append({'name':name,**pin(body)})
    failure=None;report=None
    try:
        for name in NAMES[:-1]:
            key=name[:-3];require(key not in sys.modules,'fresh test module namespace')
            module=types.ModuleType(key);module.__file__=str(ROOT/name)
            sys.modules[key]=module
            exec(compile(bodies[name],module.__file__,'exec'),module.__dict__)
        with tempfile.TemporaryDirectory(prefix='invented-files-',dir=out) as temporary:
            report=sys.modules['interface_controls'].run(save,temporary)
        require(report['all_passed'] is True and report['fixture_only'] is True and
                report['control_count']==47,'complete forty-seven fixture checks')
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1024 if sys.platform=='linux' else 1)
        require(rss<=RSS_LIMIT and time.monotonic()<deadline,'observed memory and original deadline')
        save('CONTROLS.json',encode(report))
        save('RESULT.json',encode({'schema':'tms_closed_interface_inert_result_v1','status':'PASSED',
             'source_lock_sha256':args.selection_sha256,'control_count':report['control_count'],
             'source_read_bytes':reads,'retained_bytes_before_result':retained,
             'observed_peak_rss_bytes':rss,'elapsed_before_result':time.monotonic()-start,
             'python_version':platform.python_version(),'platform':sys.platform,
             'authentic_reads':0,'candidate_executions':0,'model_calls':0,
             'scientific_qualification':False,'hard_memory_quota':False}))
        require(time.monotonic()<deadline,'final success deadline')
    except BaseException as exc:
        failure={'status':'FAILED','error_type':type(exc).__name__,'error':str(exc)[:2048],
                 'traceback':traceback.format_exc()[-8192:],'automatic_retry':False}
        save('FAILURE.json',encode(failure))
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
    save('ARTIFACT_MANIFEST.json',encode({'schema':'tms_closed_interface_inert_artifacts_v1',
         'members':members,'body_bytes_before_manifest':retained,'fixture_only':True,
         'complete_success':failure is None,'manifest_self_excluded':True}))
    require(retained<=WRITE_LIMIT,'whole retained artifact ceiling')
    success=failure is None and time.monotonic()<deadline
    print(json.dumps({'status':'PASSED' if success else 'FAILED','fixture_only':True,
          'control_count':None if report is None else report['control_count'],
          'retained_bytes':retained,'source_read_bytes':reads,
          'elapsed_seconds':time.monotonic()-start,'automatic_retry':False},sort_keys=True))
    return 0 if success else 1

if __name__=='__main__':
    raise SystemExit(main())
