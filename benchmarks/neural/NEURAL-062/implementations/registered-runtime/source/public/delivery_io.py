"""Bounded ordinary stream operations with optional caller-owned first-error custody.
Read/write counters reserve logical extents; they are not native I/O accounting.
"""
import hashlib,json,math,os,re,stat
from pathlib import Path
from contextlib import contextmanager
from contextvars import ContextVar
_OWNER=ContextVar('n062_io_owner',default=None)
def need(ok,message):
 if not ok:raise ValueError(message)
def exact(value,fields):need(type(value)is dict and set(value)==set(fields),'Exact object fields')
def canonical(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')
def pin(body):return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
def check_pin(value,cap,empty=False):
 exact(value,['bytes','sha256']);need(type(value['bytes'])is int and int(not empty)<=value['bytes']<=cap and type(value['sha256'])is str and re.fullmatch('[a-f0-9]{64}',value['sha256']),'Exact bounded pin')
def resolve(root,relative):
 need(type(relative)is str and relative and not Path(relative).is_absolute()and all(x not in('','.','..')for x in relative.split('/'))and '\\'not in relative,'Safe relative path')
 return Path(root)/relative
def regular(path):
 path=Path(path).absolute();need(all(not p.is_symlink()for p in(path,*path.parents)),'No linked paths');return path
@contextmanager
def using(owner):
 tok=_OWNER.set(owner)
 try:yield
 finally:_OWNER.reset(tok)
def reserve(key,n):
 owner=_OWNER.get()
 if owner is not None:owner.check();owner.charge(key,n)
def retain(error,stage):
 owner=_OWNER.get()
 if owner is not None:owner.retain(error,stage)
def signature(s):return tuple(getattr(s,k)for k in('st_dev','st_ino','st_size','st_nlink','st_mtime_ns','st_ctime_ns'))
@contextmanager
def verified_stream(path,expected):
 """First body error survives independent revalidation and close errors."""
 fd=None;stream=None;before=None;first=None
 try:
  check_pin(expected,expected['bytes'],empty=True);path=regular(path)
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
  stream=os.fdopen(fd,'rb');fd=None
  before=os.fstat(stream.fileno())
  need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size==expected['bytes'],'Exact ordinary source')
  reserve('read_bytes',expected['bytes']+1);digest=hashlib.sha256();count=0
  while count<expected['bytes']:
   b=stream.read(min(1048576,expected['bytes']-count));need(bool(b),'Truncated source');count+=len(b);digest.update(b)
  need(not stream.read(1)and {'bytes':count,'sha256':digest.hexdigest()}==expected,'Source content pin')
  stream.seek(0);reserve('read_bytes',expected['bytes']);yield stream
 except BaseException as e:first=e;retain(e,'stream_body')
 finally:
  for stage,fn in [('stream_identity',lambda:need(before is not None and signature(before)==signature(os.fstat(stream.fileno())),'Source changed during decoding'))if stream is not None and before is not None else('no_identity',lambda:None),('stream_close',lambda:stream.close())if stream is not None else('descriptor_close',lambda:os.close(fd))if fd is not None else('no_close',lambda:None)]:
   try:fn()
   except BaseException as e:
    if first is None:first=e
    retain(e,stage)
 if first is not None:raise first
def read(path,cap,expected=None,empty=False,retain=True):
 path=regular(path)
 # Exact observed size is validated again on the opened descriptor.
 s=path.lstat();need(stat.S_ISREG(s.st_mode)and s.st_nlink==1 and int(not empty)<=s.st_size<=cap,'Bounded ordinary file')
 if expected is not None:
  check_pin(expected,cap,empty);need(s.st_size==expected['bytes'],'Exact source size')
 fd=None;stream=None;first=None;observed=None;chunks=[]
 try:
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);stream=os.fdopen(fd,'rb');fd=None
  before=os.fstat(stream.fileno());need(signature(s)==signature(before),'Opened original source')
  reserve('read_bytes',before.st_size+1);digest=hashlib.sha256();count=0
  while count<before.st_size:
   block=stream.read(min(1048576,before.st_size-count));need(bool(block),'Truncated source');count+=len(block);digest.update(block)
   if retain:chunks.append(block)
  need(not stream.read(1)and signature(before)==signature(os.fstat(stream.fileno())),'Stable complete file')
  observed={'bytes':count,'sha256':digest.hexdigest()};need(expected is None or observed==expected,'Exact content binding')
 except BaseException as e:first=e;globals()['retain'](e,'read')
 finally:
  try:
   if stream is not None:stream.close()
   elif fd is not None:os.close(fd)
  except BaseException as e:
   if first is None:first=e
   globals()['retain'](e,'read_close')
 if first is not None:raise first
 return b''.join(chunks)if retain else observed
def decode(body):
 def pairs(rows):
  out={}
  for k,v in rows:need(k not in out,'Duplicate JSON field');out[k]=v
  return out
 def finite(x):
  v=float(x);need(math.isfinite(v),'Finite JSON scalar');return v
 def integer(x):need(len(x)<=18,'Bounded integer');return int(x)
 def invalid(x):raise ValueError('Nonstandard JSON')
 try:return json.loads(body.decode('utf8'),object_pairs_hook=pairs,parse_float=finite,parse_int=integer,parse_constant=invalid)
 except(UnicodeError,RecursionError,OverflowError)as e:raise ValueError('Malformed bounded JSON')from e
def json_file(path,cap=524288,expected=None):return decode(read(path,cap,expected))
def put_bytes(path,body,cap):
 need(type(body)is bytes and len(body)<=cap,'Output cap');path=regular(path);reserve('write_bytes',len(body));fd=None;first=None
 try:
  fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);i=0
  while i<len(body):
   n=os.write(fd,body[i:]);need(n>0,'Short output write');i+=n
  os.fsync(fd)
 except BaseException as e:first=e;retain(e,'write')
 finally:
  try:
   if fd is not None:os.close(fd)
  except BaseException as e:
   if first is None:first=e
   retain(e,'write_close')
 if first is not None:raise first
 path.chmod(0o444);return pin(body)
def put(path,value,cap=524288):return put_bytes(path,canonical(value),cap)
def fresh(path):
 path=regular(path);need(not path.exists()and path.parent.is_dir(),'Fresh owned output directory');path.mkdir(mode=0o700);return path
def asset(root,record,decode_json=False):
 expected={k:record[k]for k in('bytes','sha256')};path=resolve(root,record['path'])
 return json_file(path,record['bytes'],expected)if decode_json else read(path,record['bytes'],expected,retain=False)
def program_pin(value):check_pin(value,131072)
def copy_exact(source,target,expected):
 target=regular(target);fd=None;first=None
 try:
  with verified_stream(source,expected)as stream:
   reserve('write_bytes',expected['bytes']);fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
   remaining=expected['bytes']
   while remaining:
    b=stream.read(min(1048576,remaining));need(bool(b),'Truncated source copy');remaining-=len(b);i=0
    while i<len(b):
     n=os.write(fd,b[i:]);need(n>0,'Short copy write');i+=n
   need(not stream.read(1),'Extra source byte');os.fsync(fd)
 except BaseException as e:first=e;retain(e,'copy')
 finally:
  try:
   if fd is not None:os.close(fd)
  except BaseException as e:
   if first is None:first=e
   retain(e,'copy_close')
 if first is not None:raise first
 target.chmod(0o444);return read(target,expected['bytes'],expected,empty=True,retain=False)
