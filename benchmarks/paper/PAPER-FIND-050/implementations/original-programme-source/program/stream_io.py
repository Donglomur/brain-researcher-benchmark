"""Chronological duplex protocol: no future input until current output is durable."""
import hashlib,os,secrets,selectors,signal,struct,subprocess,time
from common import need,pin,sync
MAGIC=b'CIFRAME1'
HEADER=struct.Struct('<8sQQ16s')

def frame_header(index,neurons,token):return HEADER.pack(MAGIC,index,neurons,token)

def validate_header(raw,index,neurons,token):
    need(len(raw)==HEADER.size and HEADER.unpack(raw)==(MAGIC,index,neurons,token),'exact currentframe echo; no stale/future response')

def exchange(command,query_vectors,indices,neurons,outputs,deadline,budget,env):
    """query_vectors yields bytes for current vector only; producer outputs never graded.

    outputs is a list of owned writable fds, one per expected method. Operator
    reference writes3 vectors per echo, candidates1. All are fixedwidthfloat64.
    """
    need(len(outputs)in(1,3),'candidate or complete3reference streams');p=sel=None;stream_bytes=0;stderr=0;request_bytes=0;chain=bytes(32);count=0;natural=False;group_absent=False;error=None;closed=False;start=time.monotonic();records=[]
    try:
        p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,bufsize=0,env=env)
        sel=selectors.DefaultSelector()
        for key,f in [('out',p.stdout),('err',p.stderr)]:os.set_blocking(f.fileno(),False);sel.register(f,selectors.EVENT_READ,key)
        os.set_blocking(p.stdin.fileno(),False)
        def transfer(request,nreply):
            nonlocal stderr,stream_bytes
            sent=0;reply=bytearray();sel.register(p.stdin,selectors.EVENT_WRITE,'in')
            while sent<len(request) or len(reply)<nreply:
                need(time.monotonic()<deadline,'original stream deadline')
                for key,_ in sel.select(min(.1,max(0,deadline-time.monotonic()))):
                    if key.data=='in':
                        try:n=os.write(p.stdin.fileno(),request[sent:sent+65536])
                        except BlockingIOError:continue
                        need(n>0,'request pipe');sent+=n
                        if sent==len(request):sel.unregister(p.stdin)
                    elif key.data=='err':
                        b=os.read(p.stderr.fileno(),min(65536,65537-stderr));budget.reading(len(b));stderr+=len(b);need(stderr<=65536,'boundedstderr')
                        if not b:sel.unregister(p.stderr)
                    else:
                        b=os.read(p.stdout.fileno(),min(65536,nreply+1-len(reply)));budget.reading(len(b));need(b,'response EOF before fullvector');reply.extend(b);stream_bytes+=len(b);need(len(reply)<=nreply,'no extra future output')
            return bytes(reply)
        for index,vector in zip(indices,query_vectors):
            need(type(vector)is bytes and len(vector)==8*neurons,'onefullcurrentvector');token=secrets.token_bytes(16);header=frame_header(index,neurons,token);request=header+vector;request_bytes+=len(request);raw=transfer(request,HEADER.size+len(outputs)*8*neurons);validate_header(raw[:HEADER.size],index,neurons,token)
            import math
            for j,fd in enumerate(outputs):
                body=raw[HEADER.size+j*8*neurons:HEADER.size+(j+1)*8*neurons];need(all(math.isfinite(v[0]) for v in struct.iter_unpack('<d',body)),'finite full prediction');budget.writing(len(body));v=memoryview(body)
                while v:n=os.write(fd,v);need(n>0,'completepredictioncapture');v=v[n:]
                os.fsync(fd)
            captured=time.monotonic();need(captured<deadline,'currentpredictiondurable insideoriginalclock');chain=hashlib.sha256(chain+header+hashlib.sha256(vector).digest()+hashlib.sha256(raw).digest()).digest();count+=1
        # End input only after every eligible frame, then require natural exit and EOF.
        p.stdin.close();out_tail=0
        while sel.get_map():
            need(time.monotonic()<deadline,'streamEOFdeadline')
            for key,_ in sel.select(min(.1,max(0,deadline-time.monotonic()))):
                b=os.read(key.fileobj.fileno(),65536);budget.reading(len(b))
                if not b:sel.unregister(key.fileobj);continue
                if key.data=='out':stream_bytes+=len(b);out_tail+=len(b);need(out_tail==0,'nooutputaftercompletepanel')
                else:stderr+=len(b);need(stderr<=65536,'stderr ceiling')
        code=p.wait(timeout=max(0,deadline-time.monotonic()));need(code==0,'naturalzero streamingclient');natural=True
        try:os.killpg(p.pid,0)
        except ProcessLookupError:group_absent=True
        need(group_absent,'streamclientgroupabsent');closed=True
    except BaseException as exc:error=type(exc).__name__
    finally:
        if p is not None and not group_absent:
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            try:p.wait(timeout=max(0,min(1,deadline-time.monotonic())))
            except BaseException:pass
        if sel is not None:sel.close()
        if p is not None:
            for f in (p.stdin,p.stdout,p.stderr):
                if f is not None and not f.closed:f.close()
    return {'natural_exit':natural,'client_group_absent':group_absent,'client_reaped':closed,'query_count':count,'request_response_chain_sha256':chain.hex(),'response_bytes':stream_bytes,'outbound_request_bytes':request_bytes,'stderr_bytes':stderr,'original_deadline':deadline,'started':start,'closed':time.monotonic(),'current_predictions_durable_before_next_input':True,'error':error,'success':error is None and natural and group_absent and closed,'private_targets_opened':False}
