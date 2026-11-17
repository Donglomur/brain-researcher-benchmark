"""Exact official source verification and lazy real module dispatch."""
import hashlib,importlib,importlib.abc,importlib.util,json,os,stat,sys
from pathlib import Path
from .policy import COMMIT,DATASETS,need,encode
LOCK=Path(__file__).with_name('OFFICIAL_LOCK.json')

def pinned_file(path,expected,cap):
 path=Path(path);need(type(cap)is int and cap>0,'explicit read cap')
 need(not any(p.is_symlink()for p in (path,*path.parents)),'no source/input symlink')
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_size==expected['bytes'] and a.st_size<=cap,'ordinary exact bounded input')
  h=hashlib.sha256();n=0
  while True:
   b=os.read(fd,min(1<<20,cap-n+1))
   if not b:break
   n+=len(b);need(n<=cap,'bounded streamed pin');h.update(b)
  z=os.fstat(fd);need(all(getattr(a,k)==getattr(z,k)for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'stable pinned input')
  need(n==expected['bytes'] and h.hexdigest()==expected['sha256'],'input content pin')
 finally:os.close(fd)
 return {'bytes':n,'sha256':h.hexdigest()}

def read_lock(expected=None):
 """Authenticate and parse the same bounded captured lock bytes."""
 need(not any(q.is_symlink()for q in(LOCK,*LOCK.parents)),'ordinary lock ancestry')
 fd=os.open(LOCK,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  before=os.fstat(fd);need(stat.S_ISREG(before.st_mode)and 0<before.st_size<=1<<20,'bounded ordinary source lock')
  with os.fdopen(fd,'rb',closefd=False)as f:body=f.read((1<<20)+1)
  after=os.fstat(fd)
  need(all(getattr(before,k)==getattr(after,k)for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'stable same-read source lock')
  need(len(body)==before.st_size,'complete source lock')
 finally:os.close(fd)
 observed=hashlib.sha256(body).hexdigest()
 if expected is not None:need(observed==expected,'operative official-source lock binding')
 lock=json.loads(body);need(lock['schema']=='cbramod_official_lock_v1'and lock['commit']==COMMIT,'selected official lock/commit')
 return lock,observed

def official_lock_identity():return read_lock()[1]
def verify_official(root,expected):
 lock,_=read_lock(expected)
 root=Path(root).absolute();need(root.is_dir()and not root.is_symlink(),'official source root')
 for row in lock['files']:
  rel=Path(row['path']);need(rel.parts[0]=='official'and '..'not in rel.parts,'source lock path')
  pinned_file(root/Path(*rel.parts[1:]),row,1<<20)
 return lock

OFFICIAL_NAMESPACES=('models','datasets','utils','finetune_main','finetune_trainer','finetune_evaluator')

def _selected_namespace(name):return any(name==prefix or name.startswith(prefix+'.')for prefix in OFFICIAL_NAMESPACES)

def capture_official_python(root,expected):
 """Capture exactly the bytes that will be compiled; no bytecode-cache reuse."""
 root=Path(root).absolute();lock,_=read_lock(expected);captured={}
 for row in lock['files']:
  rel=Path(row['path']);parts=rel.parts[1:]
  if not parts or not parts[-1].endswith('.py'):continue
  package=parts[-1]=='__init__.py'
  name='.'.join(parts[:-1]if package else(*parts[:-1],parts[-1][:-3]))
  if not _selected_namespace(name):continue
  path=root/Path(*parts)
  need(not any(q.is_symlink()for q in(path,*path.parents)),'ordinary official source ancestry')
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
  try:
   before=os.fstat(fd);need(stat.S_ISREG(before.st_mode)and before.st_size==row['bytes']and before.st_size<=1<<20,'bounded exact source extent')
   with os.fdopen(fd,'rb',closefd=False)as f:body=f.read((1<<20)+1)
   after=os.fstat(fd)
   need(all(getattr(before,k)==getattr(after,k)for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'stable source capture')
   need(len(body)==row['bytes']and hashlib.sha256(body).hexdigest()==row['sha256'],'captured source pin')
   captured[name]={'body':body,'path':str(path),'package':package}
  finally:os.close(fd)
 return captured

class VerifiedSourceFinder(importlib.abc.MetaPathFinder,importlib.abc.Loader):
 """Compile captured selected source; ordinary .pyc and disk loaders are bypassed."""
 def __init__(self,captured):self.captured=captured
 def find_spec(self,fullname,path=None,target=None):
  if not _selected_namespace(fullname):return None
  need(fullname in self.captured,'unselected module in official namespace: '+fullname)
  row=self.captured[fullname]
  return importlib.util.spec_from_loader(fullname,self,origin=row['path'],is_package=row['package'])
 def create_module(self,spec):return None
 def exec_module(self,module):
  row=self.captured[module.__name__];module.__file__=row['path']
  if row['package']:module.__path__=[str(Path(row['path']).parent)]
  exec(compile(row['body'],row['path'],'exec',dont_inherit=True),module.__dict__)

def native_components(root,dataset,expected):
 """Fresh-worker native boundary; authentic source imports use captured bodies."""
 need(not any(_selected_namespace(n)for n in sys.modules),'fresh worker required: existing official namespace/submodule cache')
 captured=capture_official_python(root,expected)
 finder=VerifiedSourceFinder(captured);sys.meta_path.insert(0,finder)
 # Keep the finder for lazy official imports throughout this one worker. Native
 # dependency packages themselves still require separate environment qualification.
 import torch
 need(not any(_selected_namespace(n)for n in sys.modules),'native dependency populated an unverified official namespace')
 stem=DATASETS[dataset][0]
 return {'torch':torch,'loader':importlib.import_module('datasets.'+stem+'_dataset'),
  'head':importlib.import_module('models.model_for_'+stem),
  'trainer':importlib.import_module('finetune_trainer'),
  'entry':importlib.import_module('finetune_main')}
