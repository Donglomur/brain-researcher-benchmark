"""Exact task binding of the accepted PFC outer capture/reap mechanism."""
import time
START=time.monotonic()
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).absolute().parent))
from route_binding import HERE,exact,module,need,ordinary,load_request

def main():
    need(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode,'isolated no-site outer')
    need(len(sys.argv)==4,'request path/bytes/hash')
    pin,r,p,E=load_request(sys.argv[1],int(sys.argv[2]),sys.argv[3])
    from deployment import authenticate_source_graph, authenticate_host_python, safe_environment, limits
    authenticate_source_graph(r,HERE)
    authenticate_host_python(r['deployment'])
    ATTEMPTS=Path(r['deployment']['attempts_root']);HOST_PYTHON=r['deployment']['host_python']['path']
    for source in list(r['source_files'].values())+[p['inherited_owner'],p['inherited_outer']]:exact(source)
    ordinary(ATTEMPTS);ATTEMPTS.mkdir(mode=0o700,exist_ok=True)
    ordinary(E);need(not E.exists(),'fresh owner attempt')
    outer=module(p['inherited_outer'],'_accepted_pfc_outer')
    selected=limits(r)
    outer.START=START;outer.END=START+selected['outer_seconds'];outer.ROOT=ATTEMPTS/(r['attempt']+'-outer')
    ordinary(outer.ROOT);outer.ROOT.mkdir(mode=0o700,exist_ok=False)
    argv=[HOST_PYTHON,'-I','-S','-B',str(HERE/'owner_once.py'),*sys.argv[1:]]
    end=outer.END;work=end-10;term=end-4;reap=end-2
    process=None;confirmed_absent=False
    def fatal(*unused):
        if process is not None and not confirmed_absent:
            try:os.killpg(process.pid,signal.SIGKILL)
            except BaseException:pass
        os._exit(124)
    signal.signal(signal.SIGALRM,fatal);signal.setitimer(signal.ITIMER_REAL,max(.001,end-time.monotonic()))
    intent=outer.save('CALLER_INTENT.json',{'argv':argv,'request':pin,'cwd':str(HERE),
        'start':START,'end':end,'owner_seconds':selected['owner_seconds'],'one_attempt':True,'shell':False})
    poller=selectors.DefaultSelector();streams={'stdout':bytearray(),'stderr':bytearray()}
    eof=set();failure=None;signals=[];reaped=False;absent=False;received={'stdout':0,'stderr':0}
    try:
        need(time.monotonic()<START+10,'original staging horizon')
        process=subprocess.Popen(argv,cwd=HERE,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,start_new_session=True,close_fds=True,env=safe_environment())
        outer.save('CHILD_CREATED.json',{'pid':process.pid,'pgid':os.getpgid(process.pid),'seconds':time.monotonic()-START})
        for name,stream in (('stdout',process.stdout),('stderr',process.stderr)):
            os.set_blocking(stream.fileno(),False);poller.register(stream,selectors.EVENT_READ,name)
        while poller.get_map() or process.poll() is None:
            need(time.monotonic()<work,'original outer child cutoff')
            for key,_ in poller.select(.025):
                left=outer.STREAM_CAP-sum(len(v) for v in streams.values())
                part=os.read(key.fileobj.fileno(),min(65536,left+1))
                if not part:
                    eof.add(key.data);poller.unregister(key.fileobj);key.fileobj.close();continue
                received[key.data]+=len(part);streams[key.data].extend(part[:left])
                need(len(part)<=left,'complete bounded original outer streams')
        process.wait(timeout=0);reaped=True
    except BaseException as error:
        failure={'class':type(error).__name__,'message':str(error)[:4000]}
    finally:
        if process is not None:
            try:
                absent=outer.group_absent(process.pid)
                if not absent:
                    os.killpg(process.pid,signal.SIGTERM);signals.append('SIGTERM')
                    until=min(term,time.monotonic()+1)
                    while time.monotonic()<until and not outer.group_absent(process.pid):
                        process.poll();time.sleep(.02)
                    if not outer.group_absent(process.pid):
                        os.killpg(process.pid,signal.SIGKILL);signals.append('SIGKILL')
                remaining=reap-time.monotonic();need(remaining>0,'original reaping reserve')
                process.wait(timeout=remaining);reaped=True;absent=outer.group_absent(process.pid)
                confirmed_absent=absent
            except BaseException as error:
                if failure is None:failure={'class':type(error).__name__,'message':str(error)[:4000]}
            for stream in (process.stdout,process.stderr):
                if stream is not None and not stream.closed:stream.close()
        poller.close()
    captures={name:outer.save('child.'+name,bytes(raw)) for name,raw in streams.items()}
    code=None if process is None else process.returncode
    complete=failure is None and code==0 and reaped and absent and eof=={'stdout','stderr'} and not signals
    result={'schema':'PFC_PROTECTED_PARTICIPANT_OUTER_RESULT_V1','complete':complete,'intent':intent,'request':pin,
            'exit_code':code,'reaped':reaped,'process_group_absent':absent,'EOF':sorted(eof),'signals':signals,
            'failure':failure,'captures':captures,'received':received,'seconds':time.monotonic()-START,
            'docker_cleanup_proven_by_outer':False,'retry':False}
    saved=outer.save('CALLER_RESULT.json',result)
    need(time.monotonic()<end,'original outer final horizon')
    print(json.dumps({'complete':complete,'result':saved}),flush=True)
    need(time.monotonic()<end,'original outer transport horizon')
    return 0 if complete else 1

if __name__=='__main__':raise SystemExit(main())
