"""One bounded direct HTTPS attempt and opaque file credential ownership."""
import http.client,ssl,os,stat,time,re
from .contracts import need,closed,integer,root_path,stable,Custody,Handles,Refusal
from .openai_protocol import ENDPOINT

CREDENTIAL_KEYS={'host_path','guest_path','device','inode','uid','mode','bytes','mtime_ns','ctime_ns'}
def credential_metadata(value):
 closed(value,CREDENTIAL_KEYS);root_path(value['host_path']);need(value['guest_path']=='/run/model-key','fixed secret mount')
 for k in CREDENTIAL_KEYS-{'host_path','guest_path'}:integer(value[k])
 integer(value['bytes'],1,16384);need(value['mode']==0o600,'owner-only credential file');return value

def credential_stat(st,selected):
 need(stat.S_ISREG(st.st_mode)and st.st_nlink==1,'ordinary single-link credential')
 actual=(st.st_dev,st.st_ino,st.st_uid,stat.S_IMODE(st.st_mode),st.st_size,st.st_mtime_ns,st.st_ctime_ns)
 expected=tuple(selected[k]for k in('device','inode','uid','mode','bytes','mtime_ns','ctime_ns'))
 need(actual==expected and st.st_uid==os.getuid(),'exact current private credential identity')

def read_credential(selected,budget,custody,*,opener=os.open,reader=os.read,fstater=os.fstat):
 """No discovery, environment fallback, content hash, or secret-valued errors."""
 credential_metadata(selected);budget.admit();h=Handles(custody);raw=bytearray();key=None
 try:
  fd=h.own(opener(selected['guest_path'],os.O_RDONLY|os.O_NOFOLLOW),'private_credential','fixed gateway credential')
  before=fstater(fd);credential_stat(before,selected);budget.reserve('read_bytes',selected['bytes'])
  while len(raw)<selected['bytes']:
   budget.admit();b=reader(fd,min(4096,selected['bytes']-len(raw)));need(type(b)is bytes and b,'short credential');raw.extend(b);budget.charge('read_bytes',len(b))
  need(stable(before)==stable(fstater(fd)),'credential changed while reading')
  # Decode only after identity and finite extent admission. Never retain the raw
  # decode error in serializable custody: it can contain credential bytes.
  need(all(c in b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-'for c in raw),'opaque credential format refusal')
  key=bytes(raw).decode('ascii')
 except BaseException as error:
  custody.original_credential_error=error;custody.fail(Refusal('opaque credential admission/read failure'),'credential')
 finally:
  for i in range(len(raw)):raw[i]=0
  h.finish()
 custody.raise_if_failed();budget.admit();return key

class TransportFailure(Refusal):
 def __init__(self,owner,raw,observation):
  self.owner=owner;self.raw=raw;self.observation=observation
  super().__init__('bounded provider transport failed; original prefix and opaque failure retained')

def post_once(request,key,transport,max_response_bytes,timeout_seconds,deadline,*,clock=time.monotonic,connection=http.client.HTTPSConnection,tls_context=ssl.create_default_context):
 need(transport==ENDPOINT,'only exact selected OpenAI HTTPS endpoint');integer(max_response_bytes,1,8*2**20)
 need(type(request)is bytes and type(key)is str and re.fullmatch(r'[A-Za-z0-9_-]+',key),'bounded encoded request and opaque credential')
 c=Custody('openai_https');conn=None;response=None;chunks=[];prefix=bytearray()
 observation={'schema':'NLB017_OpenAI_application_transport_v1','endpoint':dict(transport),'request_body_bytes':len(request),'request_attempted':False,'request_complete':False,'request_body_sent_bytes':None,'request_unknown_upper_bound':0,'response_status':None,'response_body_bytes':0,'response_read_attempts':[],'response_eof':False,'response_headers':None,'connection_close_attempted':False,'response_close_attempted':False,'original_deadline':deadline,'scope':'application JSON bodies; headers/TLS/DNS/socket/kernel/remote internals are not a unique physical total','retries':0}
 def tick():
  now=clock();need(now<deadline,'original provider deadline');return min(timeout_seconds,deadline-now)
 try:
  timeout=tick();need(timeout_seconds>0,'selected transport timeout')
  conn=connection(transport['host'],transport['port'],timeout=timeout,context=tls_context())
  tick();observation['request_attempted']=True;observation['request_unknown_upper_bound']=len(request)
  conn.request('POST',transport['path'],body=request,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Accept':'application/json'})
  observation['request_complete']=True;observation['request_body_sent_bytes']=len(request);observation['request_unknown_upper_bound']=0
  tick();response=conn.getresponse();observation['response_status']=response.status
  observation['response_headers']={k:response.getheader(k)for k in('content-type','content-length','x-request-id')}
  length=response.getheader('content-length')
  if length is not None:need(length.isdecimal()and int(length)<=max_response_bytes,'provider Content-Length cap')
  while True:
   timeout=tick()
   if getattr(conn,'sock',None)is not None:conn.sock.settimeout(timeout)
   capacity=min(65536,max_response_bytes-len(prefix)+1);need(capacity>0,'complete response cap')
   row={'requested_bytes':capacity,'returned_bytes':None,'unknown_upper_bound':capacity};observation['response_read_attempts'].append(row)
   b=response.read(capacity);need(type(b)is bytes,'provider body bytes');row['returned_bytes']=len(b);row['unknown_upper_bound']=0;prefix.extend(b);observation['response_body_bytes']=len(prefix)
   need(len(prefix)<=max_response_bytes,'provider response exceeds selected cap')
   if not b:observation['response_eof']=True;break
  tick();need(response.status==200,'provider HTTP non-success; no redirect/retry')
 except BaseException as error:
  c.original_transport_error=error;c.fail(Refusal('opaque provider transport/status failure'),'transport')
 finally:
  key=None
  for obj,flag,label in ((response,'response_close_attempted','response'),(conn,'connection_close_attempted','connection')):
   if obj is not None:
    observation[flag]=True
    try:obj.close()
    except BaseException as error:
     setattr(c,'original_'+label+'_close_error',error);c.fail(Refusal('opaque provider '+label+' close failure'),label+'_close')
  c.facts['transport']=observation;c.complete=c.first_error is None
 raw=bytes(prefix)
 if c.first_error is not None:raise TransportFailure(c,raw,observation)
 return raw,observation
