"""Bounded original command custody for OCI control-plane commands."""
import os,selectors,signal,subprocess,time
from .io import need,failure,Refusal

def bounded(argv,deadline,cap,cleanup_seconds):
    need(type(cap)is int and cap>0 and time.monotonic()<deadline,"command_before_effects")
    p=None;selector=selectors.DefaultSelector();data={"stdout":bytearray(),"stderr":bytearray()};counts={k:0 for k in data};eof=set();error=None;forced=False;observed=None;final=None;start=time.monotonic()
    try:
        p=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        for name in data:
            f=getattr(p,name);os.set_blocking(f.fileno(),False);selector.register(f,selectors.EVENT_READ,name)
        while len(eof)<2 or p.poll()is None:
            need(time.monotonic()<deadline,"command_deadline")
            for key,_ in selector.select(min(.02,max(0,deadline-time.monotonic()))):
                raw=os.read(key.fileobj.fileno(),65536);name=key.data
                if not raw:eof.add(name);selector.unregister(key.fileobj);continue
                counts[name]+=len(raw);room=max(0,cap-len(data[name]));data[name].extend(raw[:room]);need(len(raw)<=room,"command_stream_cap")
        observed=p.poll();final=p.wait(timeout=max(.001,deadline-time.monotonic()));need(final==0,"command_exit",final)
    except BaseException as e:error=e
    finally:
        emergency=time.monotonic()+cleanup_seconds
        if p is not None:
            if p.poll()is None or error is not None:
                forced=True
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            try:final=p.wait(timeout=max(.001,emergency-time.monotonic()))
            except BaseException as e:error=error or e
            while len(eof)<2 and time.monotonic()<emergency:
                for key,_ in selector.select(min(.01,max(0,emergency-time.monotonic()))):
                    raw=os.read(key.fileobj.fileno(),65536);name=key.data
                    if not raw:eof.add(name);selector.unregister(key.fileobj);continue
                    counts[name]+=len(raw);data[name].extend(raw[:max(0,cap-len(data[name]))])
            for name in data:getattr(p,name).close()
        selector.close()
    record={"argv":list(argv),"original_observed_exit":observed,"original_final_wait":final,"forced_cleanup":forced,"stdout":bytes(data["stdout"]).decode("utf-8",errors="replace"),"stderr":bytes(data["stderr"]).decode("utf-8",errors="replace"),"stdout_hex":bytes(data["stdout"]).hex(),"stderr_hex":bytes(data["stderr"]).hex(),"actual_bytes":counts,"streams_complete":len(eof)==2 and all(counts[k]==len(data[k]) for k in counts),"started":start,"ended":time.monotonic(),"failure":failure(error) if error else None}
    if not record["streams_complete"] and record["failure"]is None:record["failure"]=failure(Refusal("command_incomplete_streams"))
    return record,bytes(data["stdout"])
