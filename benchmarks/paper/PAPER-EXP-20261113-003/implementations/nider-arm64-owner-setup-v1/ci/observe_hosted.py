"""Bounded capture for this one authenticated hosted dependency owner only.

Uses the existing concurrent-pipe/owned-process-group pattern. A stream limit
requests owner cleanup rather than immediately killing the native owner.
"""
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time
import traceback

STREAM_CAP=983040
INTENT_CAP=16384
RECEIPT_CAP=49152
TOTAL_CAP=1048576
ACTIVE_SECONDS=6300
CLEANUP_SECONDS=330
REAP_SECONDS=5


def need(ok,code):
    if not ok:raise ValueError(code)


def encoded(value):return (json.dumps(value,indent=2,allow_nan=False)+'\n').encode()


class Capture:
    """Bound combined retained bytes before writing, independent of image size."""
    def __init__(self,streams):
        self.streams=streams;self.retained={'stdout':0,'stderr':0}
        self.observed={'stdout':0,'stderr':0};self.truncated=False
    def consume(self,name,chunk):
        room=max(0,STREAM_CAP-sum(self.retained.values()))
        kept=chunk[:room]
        self.streams[name].write(kept);self.streams[name].flush()
        self.retained[name]+=len(kept);self.observed[name]+=len(chunk)
        self.truncated=self.truncated or len(kept)!=len(chunk)
    def report(self):
        return {'retained_bytes':dict(self.retained),'observed_pipe_bytes_at_least':dict(self.observed),
                'combined_retained':sum(self.retained.values()),'truncated':self.truncated,
                'combined_stream_cap':STREAM_CAP}


def stop_reason(cancelled,elapsed,truncated):
    return 'external_cancel' if cancelled else 'stream_extent' if truncated else 'active_deadline' if elapsed>=ACTIVE_SECONDS else None


def plain(value):
    p=Path(value)
    need(p.is_absolute() and '..' not in p.parts and len(str(p))<=2048 and
         not any(x.is_symlink() for x in (p,*p.parents)),'plain_observer_path')
    return p


def main():
    os.umask(0o077);need(len(sys.argv)==5,'source_lock_owner_capture_arguments')
    source=plain(sys.argv[1]);owner=plain(sys.argv[3]);capture_root=plain(sys.argv[4])
    lockpath=source/'ci/CI_SOURCE_LOCK.json';raw=lockpath.read_bytes()
    need(len(raw)<=1048576 and hashlib.sha256(raw).hexdigest()==sys.argv[2],'observer_source_lock')
    lock=json.loads(raw);need(lock['schema']=='nider_hosted_setup_source_lock_v1' and len(lock['files'])==33,'observer_source_closure')
    rows={x['relative_path']:x for x in lock['files']};need(len(rows)==33,'observer_unique_source_members')
    for name in ['ci/hosted_setup.py','ci/observe_hosted.py']:
        p=plain(source/name);b=p.read_bytes();entry=rows[name]
        need(len(b)==entry['bytes'] and hashlib.sha256(b).hexdigest()==entry['sha256'],'observer_driver_identity')
    need(not owner.exists() and not capture_root.exists() and owner!=capture_root and
         owner not in capture_root.parents and capture_root not in owner.parents,'fresh_separate_capture_root')
    capture_root.mkdir(mode=0o700)
    entry=rows['ci/hosted_setup.py']
    bootstrap='import hashlib,pathlib,sys; p=pathlib.Path(sys.argv[1]); b=p.read_bytes(); assert len(b)==int(sys.argv[2]) and hashlib.sha256(b).hexdigest()==sys.argv[3]; sys.argv=[str(p)]+sys.argv[4:]; exec(compile(b,str(p),"exec"),{"__name__":"__main__","__file__":str(p)})'
    argv=[sys.executable,'-I','-S','-B','-c',bootstrap,str(source/'ci/hosted_setup.py'),str(entry['bytes']),
          entry['sha256'],str(source),sys.argv[2],str(owner)]
    result={'schema':'nider_hosted_capture_lifecycle_v1','argv':argv,'source_lock_sha256':sys.argv[2],
            'active_seconds':ACTIVE_SECONDS,'cleanup_seconds':CLEANUP_SECONDS,'reap_seconds':REAP_SECONDS,
            'attempts':0,'exit_code':None,'reaped':False,'pipe_EOF':[],'signals':[],
            'reason':None,'original_failure':None,'retry':False}
    intent=encoded(result);need(len(intent)<=INTENT_CAP,'intent_reserve')
    (capture_root/'INTENT.json').write_bytes(intent)
    started=time.monotonic();proc=None;term_at=None;killed_at=None;cancel=[];select=selectors.DefaultSelector()
    streams={};files={};capture=None
    def requested(signum,_frame):cancel.append(signum)
    signal.signal(signal.SIGTERM,requested);signal.signal(signal.SIGINT,requested)
    def send(sig,label):
        event={'signal':label,'elapsed_seconds':time.monotonic()-started,'delivered':False}
        try:os.killpg(proc.pid,sig);event['delivered']=True
        except ProcessLookupError:event['already_absent']=True
        result['signals'].append(event)
    try:
        for name in ('stdout','stderr'):files[name]=(capture_root/(name+'.log')).open('xb')
        capture=Capture(files)
        proc=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        result['attempts']=1;result['pid']=proc.pid;result['owned_process_group']=proc.pid
        streams={'stdout':proc.stdout,'stderr':proc.stderr}
        for name,stream in streams.items():os.set_blocking(stream.fileno(),False);select.register(stream,selectors.EVENT_READ,name)
        while select.get_map() or proc.poll() is None:
            now=time.monotonic()
            result['reason']=result['reason'] or stop_reason(bool(cancel),now-started,capture.truncated)
            if result['reason'] and term_at is None:
                term_at=now;send(signal.SIGTERM,'SIGTERM_owned_owner_cleanup_requested')
            if term_at is not None and now-term_at>=CLEANUP_SECONDS and killed_at is None:
                killed_at=now;send(signal.SIGKILL,'SIGKILL_after_full_cleanup_opportunity')
            if killed_at is not None and now-killed_at>=REAP_SECONDS:break
            for key,_ in select.select(.05):
                chunk=os.read(key.fileobj.fileno(),65536)
                if not chunk:
                    result['pipe_EOF'].append(key.data);select.unregister(key.fileobj)
                else:capture.consume(key.data,chunk)
        result['exit_code']=proc.wait(timeout=REAP_SECONDS);result['reaped']=True
    except BaseException as exc:
        result['reason']=result['reason'] or 'observer_exception'
        result['original_failure']={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
    finally:
        # An observer failure must still give a running native owner its cleanup
        # interval. Do not claim that the Docker daemon itself was terminated.
        if proc is not None and proc.poll() is None:
            if term_at is None:
                term_at=time.monotonic();send(signal.SIGTERM,'SIGTERM_finally_owner_cleanup_requested')
            while proc.poll() is None and time.monotonic()-term_at<CLEANUP_SECONDS:
                try:
                    for key,_ in select.select(.05):
                        chunk=os.read(key.fileobj.fileno(),65536)
                        if not chunk:result['pipe_EOF'].append(key.data);select.unregister(key.fileobj)
                        elif capture is not None:capture.consume(key.data,chunk)
                except BaseException:
                    time.sleep(.05)
            if proc.poll() is None:send(signal.SIGKILL,'SIGKILL_finally_after_cleanup')
            try:result['exit_code']=proc.wait(timeout=REAP_SECONDS);result['reaped']=True
            except subprocess.TimeoutExpired:result['reaped']=False
        select.close()
        for stream in streams.values():stream.close()
        for stream in files.values():stream.close()
        result['capture']=capture.report() if capture is not None else None
        result['cancellation_signals']=cancel
        result['pipe_EOF']=sorted(set(result['pipe_EOF']))
        result['elapsed_seconds']=time.monotonic()-started
        result['capture_closed']=True
        result['running_at_cutoff']=proc is not None and proc.poll() is None
        if capture is not None and capture.truncated:result['reason']=result['reason'] or 'stream_extent'
        receipt=encoded(result);need(len(receipt)<=RECEIPT_CAP,'receipt_reserve')
        need(sum(x.stat().st_size for x in capture_root.iterdir())+len(receipt)<=TOTAL_CAP,'combined_capture_limit')
        (capture_root/'LIFECYCLE.json').write_bytes(receipt)
        print(json.dumps({'capture_root':str(capture_root),'exit_code':result['exit_code'],'reason':result['reason'],
                          'reaped':result['reaped'],'truncated':capture.truncated if capture is not None else None}))
    return 0 if result['exit_code']==0 and result['reaped'] and not result['running_at_cutoff'] and result['reason'] is None and result['pipe_EOF']==['stderr','stdout'] else 1


if __name__=='__main__':raise SystemExit(main())
