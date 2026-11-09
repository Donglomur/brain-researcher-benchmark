"""Bounded local Docker Engine transport and exact container inspection.

No Docker CLI or arbitrary backend command is accepted. All calls require an
explicit runtime profile supplied only after parent scientific authorization.
"""
from __future__ import annotations
import http.client
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import time
import urllib.parse
from owner.io import ContractError, guard_namespace, canonical, decode
from .contracts import profile

class EngineResponseError(ContractError):
 def __init__(self,message,method,path,status,body):
  super().__init__(message)
  self.response={'method':method,'path':path,'status':status,'observed_body_bytes':len(body),'observed_body_sha256':hashlib.sha256(body).hexdigest(),'observed_body_base64':base64.b64encode(body).decode()}

class UnixHTTP(http.client.HTTPConnection):
 def __init__(self,path,timeout): super().__init__('localhost',timeout=timeout);self.path=path
 def connect(self):
  self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.sock.settimeout(self.timeout);self.sock.connect(self.path)

class Engine:
 def __init__(self,p,meter,*,deadline=None):
  self.p=profile(p);self.meter=meter;self.deadline=deadline
  path=guard_namespace(p['engine_socket'])
  for x in (*reversed(path.parents),path):
   if stat.S_ISLNK(x.lstat().st_mode): raise ContractError('engine socket symlink denied')
  st=path.stat()
  if not stat.S_ISSOCK(st.st_mode) or st.st_uid!=os.geteuid() or st.st_mode&0o007: raise ContractError('private operator-owned local engine socket required')
  self.path=str(path)
 def timeout(self):
  left=self.p['engine_timeout_seconds'] if self.deadline is None else min(self.p['engine_timeout_seconds'],self.deadline-time.monotonic())
  if left<=0: raise ContractError('backend deadline exceeded')
  return left
 def request(self,method,path,body=None,*,allowed=(200,),cap=None):
  if not path.startswith('/') or '\r' in path or '\n' in path: raise ContractError('exact engine path required')
  raw=None if body is None else canonical(body)
  if raw:self.meter.write(len(raw))
  conn=UnixHTTP(self.path,self.timeout())
  try:
   conn.request(method,'/'+self.p['engine_api']+path,body=raw,headers={'Content-Type':'application/json'})
   response=conn.getresponse();bound=cap or self.p['engine_response_bytes'];parts=[];n=0
   while True:
    timeout=self.timeout()
    if conn.sock is not None:conn.sock.settimeout(timeout)
    chunk=response.read1(min(65536,bound-n+1))
    if not chunk:break
    n+=len(chunk);self.meter.read(len(chunk))
    if n>bound: raise EngineResponseError('backend response byte cap exceeded',method,path,response.status,b''.join(parts)+chunk)
    parts.append(chunk)
   data=b''.join(parts)
   if response.status not in allowed: raise EngineResponseError('engine response '+str(response.status)+' for '+method+' '+path,method,path,response.status,data)
   try:return None if not data else decode(data)
   except Exception as exc:raise EngineResponseError('invalid backend JSON: '+type(exc).__name__,method,path,response.status,data) from exc
  finally:conn.close()
 def inspect(self,ident,*,absent=False):
  self.ident(ident)
  return self.request('GET','/containers/'+ident+'/json',allowed=(200,404) if absent else (200,))
 @staticmethod
 def ident(value):
  if not isinstance(value,str) or not value or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-' for c in value): raise ContractError('unsafe exact registered container identity')
 def list_attempt(self,attempt_label):
  query=urllib.parse.urlencode({'all':'1','filters':json.dumps({'label':['neural063.attempt='+attempt_label]},separators=(',',':'))})
  return self.request('GET','/containers/json?'+query)
 def qualify(self):
  info=self.request('GET','/info')
  if info.get('ID')!=self.p['engine_id'] or info.get('OSType')!='linux' or not any('rootless' in x for x in info.get('SecurityOptions',[])): raise ContractError('same pinned qualified rootless Linux engine required')
  image=self.request('GET','/images/'+self.p['image_id']+'/json')
  if image.get('Id')!=self.p['image_id'] or self.p['image_repo_digest'] not in image.get('RepoDigests',[]): raise ContractError('local exact image is absent or changed; no pull is permitted')
  if image.get('Config',{}).get('Volumes'):raise ContractError('image may not declare implicit writable volumes')
  supplied={'PATH','LANG','HOME','TMPDIR','PYTHONDONTWRITEBYTECODE','PYTHONHASHSEED','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','TRANSFORMERS_OFFLINE','HF_HUB_OFFLINE','HF_DATASETS_OFFLINE','MPLCONFIGDIR'}
  if any(x.split('=',1)[0] not in supplied for x in image.get('Config',{}).get('Env',[])):raise ContractError('image environment must be fully overridden by the fixed sanitized configuration')
  return {'engine_id':info['ID'],'image_id':image['Id'],'rootless_security':info['SecurityOptions'],'os':info['OSType']}
 def attach(self,ident):
  self.ident(ident);sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);sock.settimeout(self.timeout());sock.connect(self.path)
  path='/'+self.p['engine_api']+'/containers/'+ident+'/attach?stream=1&stdout=1&stderr=1'
  req=('POST '+path+' HTTP/1.1\r\nHost: localhost\r\nConnection: Upgrade\r\nUpgrade: tcp\r\nContent-Length: 0\r\n\r\n').encode();sock.sendall(req);self.meter.write(len(req));data=b''
  while b'\r\n\r\n' not in data:
   chunk=sock.recv(4096)
   if not chunk: raise ContractError('engine attach ended before upgrade')
   self.meter.read(len(chunk));data+=chunk
   if len(data)>16384: raise ContractError('engine attach header too large')
  headers,buffer=data.split(b'\r\n\r\n',1)
  if headers.split(b'\r\n',1)[0].split()[1]!=b'101': raise ContractError('engine attach did not provide raw stream upgrade')
  sock.settimeout(0.05)
  return sock,buffer

def inspect_config(actual,expected):
 if not isinstance(actual,dict) or 'Id' not in actual: raise ContractError('actual container inspection missing')
 c,h=actual.get('Config',{}),actual.get('HostConfig',{})
 for key in ('Image','User','Env','Entrypoint','Cmd','WorkingDir','Labels','Tty','OpenStdin','Healthcheck'):
  if c.get(key)!=expected[key]: raise ContractError('actual container config differs: '+key)
 for key in ('NetworkMode','ReadonlyRootfs','Privileged','CapDrop','CapAdd','SecurityOpt','PidsLimit','Memory','MemorySwap','NanoCpus','CpusetCpus','IpcMode','PidMode','UTSMode','CgroupnsMode','Tmpfs','DeviceRequests','LogConfig','RestartPolicy','AutoRemove'):
  if h.get(key)!=expected['HostConfig'][key]: raise ContractError('actual container isolation/resource setting differs: '+key)
 if any(x.get('Type') not in {'bind','tmpfs'} or (x.get('Type')=='tmpfs' and x.get('Destination')!='/scratch') for x in actual.get('Mounts',[])):raise ContractError('unexpected implicit image volume or mount')
 actual_mounts={(x['Source'],x['Destination'],bool(x['RW'])) for x in actual.get('Mounts',[]) if x.get('Type')=='bind'}
 wanted={(x['Source'],x['Target'],False) for x in expected['HostConfig']['Mounts']}
 if actual_mounts!=wanted: raise ContractError('actual source/sibling/target mount inventory differs')
 if actual.get('NetworkSettings',{}).get('Ports'): raise ContractError('unexpected exposed container port')
 return {'id':actual['Id'],'config_sha256':__import__('hashlib').sha256(canonical(expected)).hexdigest(),'mounts':sorted([list(x) for x in actual_mounts]),'network_mode':h['NetworkMode'],'uid':c['User'],'read_only_root':h['ReadonlyRootfs']}
