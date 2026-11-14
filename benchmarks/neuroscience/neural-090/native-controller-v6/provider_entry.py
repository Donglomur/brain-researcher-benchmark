"""One actual HTTPS Responses attempt, inside a separately owned trusted process.

No retry/redirect/hosted tool/server defaults. Parent reservations precede spawn.
Provider completion and usage are required; local kill is not remote cancellation.
"""
import base64,hashlib,http.client,json,os,ssl,stat,sys,time
from pathlib import Path

def main():
    cfg=json.loads(Path(sys.argv[1]).read_bytes());deadline=cfg['deadline'];cap=cfg['response_bytes'];raw=bytearray();conn=response=None;first=None;secondary=[]
    state={'attempted':False,'status':None,'eof':False,'response_closed':False,'connection_closed':False,'retries':0,'request_pin':None}
    key=None
    try:
        p=Path(cfg['credential']['path']);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        credential_first=None;credential_secondary=[]
        try:
            a=os.fstat(fd)
            if not stat.S_ISREG(a.st_mode)or a.st_nlink!=1 or a.st_uid!=os.getuid()or stat.S_IMODE(a.st_mode)!=0o600 or not 1<=a.st_size<=16384:raise ValueError('private credential identity')
            key=os.read(fd,a.st_size+1)
            if len(key)!=a.st_size or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=tuple(cfg['credential'][k]for k in('device','inode','bytes','mtime_ns','ctime_ns')):raise ValueError('selected credential identity')
        except BaseException as error:credential_first=error
        finally:
            try:os.close(fd)
            except BaseException as error:
                if credential_first is None:credential_first=error
                else:credential_secondary.append(error)
        secondary.extend({'where':'credential-close','type':type(error).__name__}for error in credential_secondary)
        if credential_first is not None:raise credential_first
        request=json.dumps({'model':cfg['model'],'input':cfg['input'],'store':False,'stream':False,'truncation':'disabled','max_output_tokens':cfg['output_tokens'],'tools':[]},separators=(',',':'),allow_nan=False).encode()
        if len(request)>cfg['request_bytes']:raise ValueError('provider request cap')
        state['request_pin']={'bytes':len(request),'sha256':hashlib.sha256(request).hexdigest()}
        remaining=lambda:max(.001,deadline-time.monotonic())
        if time.monotonic()>=deadline:raise TimeoutError('original provider cutoff')
        conn=http.client.HTTPSConnection('api.openai.com',443,timeout=remaining(),context=ssl.create_default_context());state['attempted']=True
        conn.request('POST','/v1/responses',body=request,headers={'Authorization':'Bearer '+key.decode('ascii'),'Content-Type':'application/json','Accept':'application/json'})
        response=conn.getresponse();state['status']=response.status
        while True:
            if time.monotonic()>=deadline:raise TimeoutError('original provider cutoff')
            if conn.sock is not None:conn.sock.settimeout(remaining())
            part=response.read(min(16384,cap+1-len(raw)));raw.extend(part)
            if len(raw)>cap:raise ValueError('provider cap-plus-probe')
            if not part:state['eof']=True;break
        if response.status!=200:raise ValueError('provider non-200; no retry')
    except BaseException as e:first=e
    finally:
        key=None
        for name,obj in (('response_closed',response),('connection_closed',conn)):
            if obj is not None:
                try:obj.close();state[name]=True
                except BaseException as e:secondary.append({'where':name,'type':type(e).__name__});first=first or e
    out={'transport':state,'raw_base64':base64.b64encode(raw).decode('ascii'),'first_error':None if first is None else type(first).__name__,'secondary':secondary}
    sys.stdout.write(json.dumps(out,separators=(',',':'))+'\n');sys.stdout.flush()
    if first is not None:raise SystemExit(1)
if __name__=='__main__':main()
