"""New bounded engineering cases using tiny invented source, never originals/models."""
from pathlib import Path
import hashlib
import importlib
import io
import json
import os
import sys
import tempfile
import time
import types
from unittest.mock import patch
D=Path(__file__).resolve().parents[1];sys.path.insert(0,str(D))
from c4_distribution import io_core as c
from c4_distribution import dependencies as d
from c4_distribution import import_guard as g
checks=refusals=0;cases=[]
def check(ok,why):
 global checks
 checks+=1
 if not ok:raise AssertionError(why)
def leaves(exc):
 if isinstance(exc,BaseExceptionGroup):return [x for z in exc.exceptions for x in leaves(z)]
 return [exc]
def refuse(fn,typ=Exception):
 global refusals
 try:fn()
 except typ as exc:refusals+=1;return exc
 raise AssertionError('expected refusal')
def row(name,body):
 return {'path':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),
 'git_blob':hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest(),
 'url':'https://raw.githubusercontent.com/'+d.REPOSITORY+'/'+d.REVISION+'/'+name}
def invented_spec(files):
 rows=[row(n,b)for n,b in files.items()]
 return {'files':rows,'file_count':len(rows),'total_bytes':sum(len(b)for b in files.values())}
def remove_binding():
 for name in list(sys.modules):
  if name=='npyx'or name.startswith('npyx.'):sys.modules.pop(name)
 if g._ACTIVE in sys.meta_path:sys.meta_path.remove(g._ACTIVE)
 g._ACTIVE=None

# Exact real descriptor only, no original bodies or scientific imports.
actual=d.specification()
check(len(actual['files'])==41,'full fixed original count')
check(actual['total_bytes']==1346896,'complete original source extent')
check(not any(n in sys.modules for n in('numpy','torch','npyx','h5py')),'no scientific library imported')
cases.append('actual fixed41 descriptor full admission')

scratch=None
with tempfile.TemporaryDirectory(prefix='new-source-controls-',dir=scratch)as temporary:
 root=Path(temporary).resolve()
 files={'npyx/__init__.py':b'from .core import VALUE\n',
        'npyx/core.py':b'VALUE = 7\n',
        'npyx/c4/__init__.py':b'# invented empty package\n',
        'LICENSE.md':b'Invented test license fixture, not upstream source.\n',
        'pyproject.toml':b'# invented fixture only\n'}
 spec=invented_spec(files);source=root/'input';source.mkdir()
 for name,body in files.items():
  p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body)
 with patch.object(d,'specification',return_value=spec),patch.object(d,'MANIFEST_SHA256','f'*64):
  output=root/'prepared'
  result=d.prepare_dependencies(output,source_root=source)
  verified=d.verify_dependencies(output)
  check(dict(verified.files)==files,'complete invented source captured')
  check(result['source_files']==5,'complete original5 fixture')
  check(result['publication']['atomic_no_replace'],'atomic publication receipt')
  check(not output.stat().st_mode&0o222,'sealed root')
  check((output/'SOURCE_RECEIPT.json').is_file(),'whole manifest receipt')
  refuse(lambda:d.prepare_dependencies(output,source_root=source),FileExistsError)
  check((output/'npyx/core.py').read_bytes()==files['npyx/core.py'],'no overwrite')
  cases.append('actual local preparation publication and complete readback')

  # Entire inventory, not only receipt or rows present.
  output.chmod(0o755);extra=output/'extra.py';extra.write_bytes(b'pass\n');extra.chmod(0o444);output.chmod(0o555)
  refuse(lambda:d.verify_dependencies(output),c.SourceError)
  output.chmod(0o755);extra.unlink();output.chmod(0o555)
  check(dict(d.verify_dependencies(output).files)==files,'original fixture restored for independent following cases')
  cases.append('extra member rejected')

  foreign=types.ModuleType('npyx');sys.modules['npyx']=foreign
  with patch.object(g,'verify_dependencies',side_effect=AssertionError('preloaded check must precede any read')):
   refuse(lambda:g.activate_originals(output),c.SourceError)
  check(sys.modules['npyx']is foreign,'conflict not silently deleted')
  del sys.modules['npyx']
  with patch.object(g,'verify_dependencies',side_effect=d.verify_dependencies):
   bound=g.activate_originals(output)
   check('npyx'not in sys.modules,'activation imports no original')
   package=importlib.import_module('npyx')
   check(package.VALUE==7,'actual verified byte loader used invented source')
   check(package.__cached__ is None,'no bytecode output')
   check(g.require_bound_source()is bound,'actual caller guard joins binding')
   refuse(lambda:importlib.import_module('npyx.unlisted'),ModuleNotFoundError)
   fake=types.ModuleType('npyx.fake');sys.modules['npyx.fake']=fake
   refuse(g.require_bound_source,c.SourceError);del sys.modules['npyx.fake']
   finder=g._ACTIVE;sys.meta_path.remove(finder);sys.meta_path.insert(1,finder)
   refuse(g.require_bound_source,c.SourceError);sys.meta_path.remove(finder);sys.meta_path.insert(0,finder)
   package.__path__.append(str(root/'ambient'))
   refuse(g.require_bound_source,c.SourceError);package.__path__.pop()
   check(g.require_bound_source()is bound,'valid owner restored')
   # A changed disk member cannot be silently rebound; loader still captured exact old bytes.
   f=output/'npyx/core.py';f.chmod(0o644);f.write_bytes(b'VALUE = 8\n');f.chmod(0o444)
   refuse(lambda:g.activate_originals(output),c.SourceError)
   check(sys.modules['npyx.core'].VALUE==7,'captured code not reread from mutable disk')
  remove_binding()
  cases.append('actual importer fresh-process/preload/namespace/capture checks')

 # Low-level input failure before opening a FIFO; symlink and hardlink refusal.
 regular=root/'plain.txt';regular.write_bytes(b'ordinary fixture\n')
 symbolic=root/'link.txt';symbolic.symlink_to(regular)
 refuse(lambda:c.capture_path(symbolic,100),c.SourceError)
 hard=root/'hard.txt';os.link(regular,hard)
 refuse(lambda:c.capture_path(regular,100),c.SourceError);hard.unlink()
 fifo=root/'pipe';os.mkfifo(fifo)
 refuse(lambda:c.capture_path(fifo,100),c.SourceError)
 check(c.capture_path(regular,100)==b'ordinary fixture\n','regular capture')
 cases.append('actual ordinary-file type and hardlink boundaries')

 # Primary read failure plus descriptor-close failure retained on actual owner.
 primary=RuntimeError('invented read failure');secondary=RuntimeError('invented close failure')
 real_open=os.open;real_read=os.read;real_close=os.close;tracked=[]
 def opened(path,*args,**kwargs):
  fd=real_open(path,*args,**kwargs)
  if path=='plain.txt':tracked.append(fd)
  return fd
 def read(fd,n):
  if tracked and fd==tracked[-1]:raise primary
  return real_read(fd,n)
 def close(fd):
  if tracked and fd==tracked[-1]:raise secondary
  return real_close(fd)
 with patch.object(c.os,'open',side_effect=opened),patch.object(c.os,'read',side_effect=read),patch.object(c.os,'close',side_effect=close):
  exc=refuse(lambda:c.capture_path(regular,100),BaseExceptionGroup)
 check(leaves(exc)==[primary,secondary],'raw primary and close error order retained')
 check(secondary.c4_close_owner.fd==tracked[-1],'uncertain original fd owner retained')
 check(secondary.c4_close_owner.close_attempted,'no implicit retry')
 real_close(tracked[-1])
 cases.append('actual capture primary plus close error custody')

 # A publication failure retains its exact partial staging root.
 fail=RuntimeError('invented second member write failure');real_write=c._write_at;writes=[]
 def failing(fd,n,b):
  writes.append(n)
  if len(writes)==2:raise fail
  return real_write(fd,n,b)
 target=root/'partial'
 with patch.object(c,'_write_at',side_effect=failing):
  exc=refuse(lambda:c.publish_tree(target,[('a.txt',b'a'),('b.txt',b'b')]),RuntimeError)
 check(exc is fail,'original write error survives publication')
 check(not target.exists(),'failed tree never published')
 stages=list(root.glob('.c4-source-stage-*'));check(len(stages)==1,'owned partial retained')
 check((stages[0]/'a.txt').read_bytes()==b'a','partial evidence retained')
 check(any('published=False'in n for n in exc.__notes__),'publication state attached')
 cases.append('actual partial-write custody')

 # Destination appears after staging: real atomic syscall must refuse overwrite.
 real_rename=c._rename_no_replace;race=root/'race'
 def raced(parent,old,new):
  race.mkdir();(race/'existing.txt').write_bytes(b'keep')
  return real_rename(parent,old,new)
 with patch.object(c,'_rename_no_replace',side_effect=raced):
  refuse(lambda:c.publish_tree(race,[('new.txt',b'new')]),FileExistsError)
 check((race/'existing.txt').read_bytes()==b'keep'and not(race/'new.txt').exists(),'race target unchanged')
 cases.append('actual atomic no-replace collision')

 # A failure after rename is not reported as a successful publication.
 late=RuntimeError('invented post-publication parent fsync failure');parentfd=[];real_sync=os.fsync
 def renamed(parent,old,new):
  real_rename(parent,old,new);parentfd.append(parent)
 def sync(fd):
  if parentfd and fd==parentfd[-1]:raise late
  real_sync(fd)
 lateout=root/'late'
 with patch.object(c,'_rename_no_replace',side_effect=renamed),patch.object(c.os,'fsync',side_effect=sync):
  exc=refuse(lambda:c.publish_tree(lateout,[('x.txt',b'fixed')]),RuntimeError)
 check(exc is late and lateout.exists(),'published result retained with original late error')
 check(any('published=True'in n for n in exc.__notes__),'late custody state explicit')
 cases.append('actual post-publication failure custody')

 # Network acquisition boundaries use an invented HTTP leaf, never a connection.
 body=b'VALUE = 1\n';r=row('npyx/test.py',body)
 class Response:
  status=200
  def __init__(self,raw,close_error=None):
   self.stream=io.BytesIO(raw);self.headers={};self.closed=False;self.close_error=close_error
  def geturl(self):return r['url']
  def read(self,n):return self.stream.read(n)
  def close(self):
   self.closed=True
   if self.close_error:raise self.close_error
 class Opener:
  def __init__(self,response):self.response=response
  def open(self,*a,**k):return self.response
 good=Response(body);check(d._fetch(r,Opener(good),time.monotonic()+5)==body and good.closed,'bounded stream exact body')
 close_error=RuntimeError('invented response close failure');bad=Response(body+b'overflow',close_error)
 exc=refuse(lambda:d._fetch(r,Opener(bad),time.monotonic()+5),BaseExceptionGroup)
 check(isinstance(leaves(exc)[0],c.SourceError)and leaves(exc)[1]is close_error,'stream overrun plus close preserved')
 check(close_error.c4_close_owner.response is bad,'response owner retained')
 redirect_close=RuntimeError('invented redirect response close failure');redirect=Response(b'',redirect_close)
 exc=refuse(lambda:d._NoRedirect().http_error_302(None,redirect,302,'redirect',{}),BaseExceptionGroup)
 check(isinstance(leaves(exc)[0],c.SourceError)and leaves(exc)[1]is redirect_close,'redirect primary plus close preserved')
 cases.append('bounded stream/redirect errors with invented HTTP leaf')

 for p in sorted(root.rglob('*'),key=lambda x:len(x.parts)):
  if p.is_dir()and not p.is_symlink():p.chmod(0o755)
check(not any(n in sys.modules for n in('npyx','numpy','torch','h5py')),'no actual scientific packages left/imported')
result={'status':'pass','cases':cases,'case_count':len(cases),'assertions':checks,'expected_refusals':refusals,
 'scope':'Actual filesystem/source-preparation/importer control flow with tiny invented source and invented HTTP leaves. Fixed41 real descriptor read only; no original npyx body, article, dataset, model, numerical/native-scientific or network execution.',
 'original_scientific_execution':False,'old_campaigns_replayed':False}
print(json.dumps(result,indent=2))
