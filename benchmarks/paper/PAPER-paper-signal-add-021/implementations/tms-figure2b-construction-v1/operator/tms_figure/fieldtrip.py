"""Explicit future MATLAB/FieldTrip reference caller; never runs on import."""
from __future__ import annotations
import hashlib,json,os,signal,subprocess,threading,time
from pathlib import Path
from .contract import *

DRIVER_PIN={'bytes': 6117, 'sha256': 'eaebab052392d1243f39985a3530a43ec8f0e94e1f02d031f7514d42c44059b1'}

OFFICIAL={'ft_math.m':'ababdd6e4d5ca461220480f4371b63c60ccd207891e1d68a78737107745a97d3','ft_topoplotTFR.m':'9f6975644c45c9d679790078d7cd1159760d1a65a2cdbafcf4b239363d9bbd06','private/topoplot_common.m':'9c2632839f0d783673afbce4b71cfcf787ad491a8d3fc57473d755d9850eb69a','utilities/nearest.m':'8c3aa77600209e3e444399994d2ba3236f766bcd9469ab8519b0b93b98b123f7','external/stats/nanmean.m':'e7c3c458f9f903b7c5948b1ca36f7db8a67db24de6a67b5077eaa9f0f3b0cceb','external/stats/nansum.m':'765e03cfbccbcf67f52ad36edc15b07cad914cad0a350e3d6ce03c854843ae45'}

def run_reference(*, matlab, executable_pin, fieldtrip_root, fieldtrip_commit, driver, driver_pin,
                  derivative, identity, work, authority_path, authority_pin,
                  environment_pin, layout_path, neighbors_path, budget, seconds, cleanup_seconds, max_log_bytes):
    """Trusted operator operation, requiring separate authentic runtime authorization.

    This source is not a native containment provider. MATLAB licensing/dependencies,
    complete path identity, source custody, physical quotas and child-process closure
    must be qualified externally before the operator can issue the grant.
    """
    metadata(identity);require(type(budget) is Budget,'exact budget')
    require(type(seconds) in (int,float) and math.isfinite(seconds) and seconds>0 and type(cleanup_seconds) in (int,float) and math.isfinite(cleanup_seconds) and cleanup_seconds>0 and strict_int(max_log_bytes,1),'explicit runtime operands')
    pin(environment_pin);pin(executable_pin);pin(driver_pin)
    require(driver_pin==DRIVER_PIN and Path(driver).name=='figure2b_reference.m','exact reviewed driver identity')
    require(fieldtrip_commit==FT_COMMIT,'selected official revision')
    operation={'identity_sha256':digest(identity),'environment':environment_pin,'executable':executable_pin,'driver':driver_pin,'fieldtrip_commit':FT_COMMIT,'seconds':seconds,'cleanup_seconds':cleanup_seconds,'max_log_bytes':max_log_bytes}
    grant=json_body(read_pinned(authority_path,authority_pin,budget))
    keys(grant,['schema','operation_sha256','authorized_by_operator','native_environment_qualified'])
    require(grant['schema']=='tms_figure2b_FieldTrip_reference_grant_v1' and grant['operation_sha256']==digest(operation) and grant['authorized_by_operator'] is True and grant['native_environment_qualified'] is True,'separate qualified FieldTrip grant')
    for path,p in [(layout_path,{'bytes':3702,'sha256':'5d574f7e1c9f40245694aa3cab50ec15790d0fe637697e4bbb9448320d0b8110'}),(neighbors_path,{'bytes':1848,'sha256':'6478cdff47a16c1ec037a8e435b8ed2222d9ea18dcd3a4be68e61cf258bac7bb'}),(matlab,executable_pin),(driver,driver_pin),(derivative,identity['source'])]:fd=open_pinned(path,p,budget);os.close(fd)
    for path,sha in OFFICIAL.items():
        target=Path(fieldtrip_root)/path;fd=open_pinned(target,{'bytes':target.stat().st_size,'sha256':sha},budget);os.close(fd)
    work=Path(work).absolute();require(not work.exists(),'fresh FieldTrip work');work.mkdir(mode=0o700)
    config={'layout':str(Path(layout_path).absolute()),'identity':identity,'derivative':str(Path(derivative).absolute()),'fieldtrip_root':str(Path(fieldtrip_root).absolute()),'output':str(work/'output')}
    body=json.dumps(config,sort_keys=True,allow_nan=False).encode();budget.charge(write=len(body))
    with (work/'CONFIG.json').open('xb') as stream:stream.write(body)
    def quote(s):return "'"+str(s).replace("'","''")+"'"
    expr='addpath('+quote(Path(driver).absolute().parent)+'); assert(strcmp(which(\'figure2b_reference\'),'+quote(Path(driver).absolute())+')); figure2b_reference('+quote(work/'CONFIG.json')+');'
    argv=[str(Path(matlab).absolute()),'-batch',expr]
    # Reserve bounded capture and failure-report serialization before launching.
    # The whole reservation remains charged on every dispatched attempt.
    budget.charge(read=max_log_bytes+2*4096,write=8*max_log_bytes+65536)
    chunks={'stdout':bytearray(),'stderr':bytearray()};errors=[];lock=threading.Lock();overflow=threading.Event()
    process=None;workers=[];started=[];failure=None;natural=False;cleanup_errors=[]
    start=time.monotonic()
    def drain(name,stream):
        try:
            while True:
                block=stream.read(4096)
                if not block:return
                with lock:
                    if sum(len(v) for v in chunks.values())+len(block)>max_log_bytes:overflow.set();return
                    chunks[name].extend(block)
        except BaseException as e:errors.append(type(e).__name__+': '+str(e));overflow.set()
        finally:stream.close()
    try:
        process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=work,start_new_session=True,env={'PATH':'/usr/bin:/bin','HOME':str(work),'TMPDIR':str(work)})
        workers=[threading.Thread(target=drain,args=(k,getattr(process,k)),daemon=True) for k in chunks]
        for thread in workers:
            thread.start();started.append(thread)
        while process.poll() is None:
            require(not overflow.is_set() and time.monotonic()-start<seconds,'bounded MATLAB capture/deadline')
            budget.charge();time.sleep(0.01)
        natural=True
        require(process.returncode==0,'FieldTrip reference nonzero exit')
    except BaseException as exc:
        failure=type(exc).__name__+': '+str(exc)
    finally:
        cleanup_end=time.monotonic()+cleanup_seconds
        if process is not None:
            # Every cleanup action is attempted independently, even after a
            # thread-start, process-kill, wait, or capture exception.
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            except BaseException as exc:cleanup_errors.append('kill: '+type(exc).__name__+': '+str(exc))
            try:process.wait(timeout=max(0.001,cleanup_end-time.monotonic()))
            except BaseException as exc:cleanup_errors.append('wait: '+type(exc).__name__+': '+str(exc))
        for thread in workers:
            try:
                if thread in started or thread.is_alive():thread.join(timeout=max(0.001,cleanup_end-time.monotonic()))
                if thread.is_alive():cleanup_errors.append('capture thread remains alive')
            except BaseException as exc:cleanup_errors.append('join: '+type(exc).__name__+': '+str(exc))
        if process is not None:
            for name in chunks:
                try:
                    # Never synchronously close a pipe being read by an
                    # unjoined worker: that can block on its I/O lock.
                    if not any(t.is_alive() for t in workers):getattr(process,name).close()
                except BaseException as exc:cleanup_errors.append('pipe close: '+type(exc).__name__+': '+str(exc))
    worker_status=[]
    for index,thread in enumerate(workers):
        try:alive=thread.is_alive()
        except BaseException:alive=None
        worker_status.append({'index':index,'start_returned':thread in started,'alive':alive,'thread_ident':getattr(thread,'ident',None)})
    with lock:
        logs={k:bytes(v).decode('utf-8',errors='replace') for k,v in chunks.items()}
    receipt={'schema':'tms_figure2b_FieldTrip_invocation_v1','operation':operation,'argv':argv,'launched_pid':None if process is None else process.pid,'owned_process_group_id':None if process is None else process.pid,'capture_workers':worker_status,'natural_exit':natural,'returncode':None if process is None else process.returncode,'elapsed_seconds_including_cleanup':time.monotonic()-start,'failure':failure,'capture_errors':errors,'cleanup_errors':cleanup_errors,'capture_overflow':overflow.is_set(),**logs,'descendant_namespace_qualification':'external hold; group kill is not native validation'}
    encoded=json.dumps(receipt,sort_keys=True).encode()
    require(len(encoded)<=8*max_log_bytes+65536,'reserved receipt extent')
    with (work/'INVOCATION.json').open('xb') as stream:stream.write(encoded)
    require(failure is None and natural and process.returncode==0 and not errors and not cleanup_errors and not overflow.is_set(),'FieldTrip reference incomplete; retained invocation receipt')
    return receipt
