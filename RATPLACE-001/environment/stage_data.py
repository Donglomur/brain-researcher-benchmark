"""One immutable NWB object; source-only staging, no HDF5/scientific imports.

The internal deadline is supplemented by the build's mandatory hard timeout.
One request, no redirects/retries/proxies. Local reuse authenticates before copy.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import time
import urllib.error
import urllib.request

MANIFEST_SHA256='0bc1ef69627c18177f8a15c76bd8dbe003a6bdaf75ba33a9e0aaa5be652ab722'
URL='https://dandiarchive.s3.us-east-2.amazonaws.com/blobs/e42/58a/e4258ab4-a9cb-45ff-b92e-6aec93d44aca'
NAME='sub-M02_ses-20240312T100000_behavior+ecephys.nwb'
SIZE=61347328
SHA256='323e99a1ec1b028a35da8cd955f2671a1f9e1853b46622c19863424943c962db'
CAP=64*1024**2
WALL=300
SOCKET=30
RESERVE=1024**3

def need(ok,reason):
    if not ok:raise ValueError(reason)

def safe(value):
    raw=os.fspath(value)
    need(isinstance(raw,str) and raw.startswith('/') and '\0' not in raw
         and not any(x in ('.','..') for x in raw.split('/')),'unsafe_path')
    p=Path(raw)
    for x in (*reversed(p.parents),p):
        if os.path.lexists(x):
            mode=x.lstat().st_mode
            need(not stat.S_ISLNK(mode),'symlink_path')
            if x!=p:need(stat.S_ISDIR(mode),'nondirectory_ancestor')
    return p

def identity(s):return s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns
def digest(raw):return hashlib.sha256(raw).hexdigest()

def read(path,cap,expected=None,size=None):
    p=safe(path);before=p.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_size<=cap,'bounded_regular')
    with os.fdopen(os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as f:
        need(identity(os.fstat(f.fileno()))==identity(before),'changed_open')
        raw=f.read(before.st_size+1)
        need(identity(os.fstat(f.fileno()))==identity(before)==identity(p.lstat()),'changed_read')
    need(len(raw)==before.st_size and (size is None or len(raw)==size),'size')
    need(expected is None or digest(raw)==expected,'sha256')
    return raw

def load_manifest(path):
    need(isinstance(MANIFEST_SHA256,str) and len(MANIFEST_SHA256)==64,'unfrozen_manifest')
    raw=read(path,1024**2,MANIFEST_SHA256)
    def pairs(items):
        d={}
        for k,v in items:need(k not in d,'duplicate_json');d[k]=v
        return d
    def bad(_):raise ValueError('nonfinite_json')
    obj=json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
    need(obj['task_id']=='RATPLACE-001' and obj['schema_version']=='ratplace-source-v2','manifest_schema')
    need(len(obj['files'])==1,'manifest_inventory')
    row=obj['files'][0]
    need(row['path']==NAME and row['size_bytes']==SIZE and row['sha256']==SHA256,'manifest_identity')
    return raw,obj

def disjoint(*paths):
    paths=[safe(p) for p in paths]
    for i,a in enumerate(paths):
        for b in paths[i+1:]:
            need(a!=b and a not in b.parents and b not in a.parents,'overlapping_paths')
    return paths

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**kw):return None

def download(path,deadline,*,opener=None,clock=time.monotonic):
    if opener is None:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    remaining=deadline-clock();need(remaining>0,'deadline')
    request=urllib.request.Request(URL,headers={'Accept-Encoding':'identity','User-Agent':'RATPLACE-001-source/2'})
    try:
        response=opener.open(request,timeout=min(SOCKET,remaining))
    except urllib.error.HTTPError as error:
        status=error.code;error.close();raise ValueError('http_status_'+str(status)) from None
    received=0;hasher=hashlib.sha256()
    with response:
        need(response.status==200 and response.geturl()==URL,'response_endpoint_status')
        need(response.headers.get('Content-Encoding','identity').lower() in ('identity',''),'content_encoding')
        lengths=response.headers.get_all('Content-Length',[])
        need(len(lengths)==1 and lengths[0].isdigit() and int(lengths[0])==SIZE,'content_length')
        with path.open('xb') as output:
            while received<SIZE:
                need(clock()<deadline,'deadline')
                chunk=response.read1(min(1024**2,SIZE-received))
                need(bool(chunk),'truncated_body')
                received+=len(chunk);need(received<=SIZE,'payload_cap')
                output.write(chunk);hasher.update(chunk)
            need(clock()<deadline,'deadline')
            need(response.read1(1)==b'','oversized_body')
            output.flush();os.fsync(output.fileno())
    need(hasher.hexdigest()==SHA256,'sha256')
    return received

def verify(destination,manifest_raw):
    root=safe(destination)
    need(root.is_dir() and set(x.name for x in root.iterdir())=={NAME,'source_manifest.json'},'closed_source_inventory')
    need(read(root/'source_manifest.json',1024**2)==manifest_raw,'internal_manifest')
    read(root/NAME,CAP,SHA256,SIZE)

def write_json(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')

def stage(manifest,destination,work_dir,source_file=None):
    manifest=safe(manifest);destination=safe(destination);work=safe(work_dir)
    protect=[manifest]
    if source_file is not None:protect.append(safe(source_file))
    disjoint(destination,work,*protect)
    need(not os.path.lexists(destination) and not os.path.lexists(work),'fresh_paths_required')
    manifest_raw,_=load_manifest(manifest)
    local=read(source_file,CAP,SHA256,SIZE) if source_file is not None else None
    ancestor=work.parent
    while not ancestor.exists():ancestor=ancestor.parent
    need(shutil.disk_usage(ancestor).free>=RESERVE+2*SIZE,'disk_reserve')
    work.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();mode='local_copy' if local is not None else 'cold_download'
    write_json(work/'attempt.json',dict(status='started',mode=mode,requests_planned=int(local is None),
        source_url=URL,source_sha256=SHA256,source_bytes=SIZE,retries=0,redirects=0,wall_seconds=WALL))
    def alarm(*_):raise TimeoutError('source_deadline')
    old=signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,WALL)
    try:
        partial=work/'original.partial'
        if local is None:received=download(partial,start+WALL)
        else:
            with partial.open('xb') as f:f.write(local);f.flush();os.fsync(f.fileno())
            received=0
        raw=read(partial,CAP,SHA256,SIZE)
        if source_file is not None:need(read(source_file,CAP,SHA256,SIZE)==local,'local_source_changed')
        destination.mkdir(parents=True,exist_ok=False)
        with (destination/NAME).open('xb') as f:f.write(raw)
        with (destination/'source_manifest.json').open('xb') as f:f.write(manifest_raw)
        verify(destination,manifest_raw)
        need(read(manifest,1024**2,MANIFEST_SHA256)==manifest_raw,'manifest_changed')
        result=dict(status='ok',mode=mode,source_files=1,source_bytes=SIZE,source_sha256=SHA256,
            received_body_bytes=received,requests=int(local is None),redirects=0,retries=0,
            source_url=URL,elapsed_seconds=time.monotonic()-start,scientific_values_parsed=False)
        write_json(work/'result.json',result);return result
    except BaseException as error:
        write_json(work/'result.json',dict(status='failed',error_type=type(error).__name__,
            error_code=str(error) if isinstance(error,ValueError) else 'source_failure',
            elapsed_seconds=time.monotonic()-start,retries=0))
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--manifest',default='/app/source_manifest.json')
    p.add_argument('--destination',default='/app/data/ratplace')
    p.add_argument('--work-dir',default='/source_capture')
    p.add_argument('--source-file')
    p.add_argument('--verify-existing',action='store_true')
    a=p.parse_args()
    if a.verify_existing:
        raw,_=load_manifest(a.manifest);verify(a.destination,raw)
    else:
        print(json.dumps(stage(a.manifest,a.destination,a.work_dir,a.source_file),sort_keys=True))

if __name__=='__main__':main()

