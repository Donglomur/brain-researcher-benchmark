"""Strict records, path custody and bounded ordinary-file operations."""
import hashlib,json,math,os,stat,time
from pathlib import Path,PurePosixPath
from .lifecycle import current,guard

class Refusal(ValueError):pass
def require(ok,message):
 if not ok:raise Refusal(message)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def identity(value):return hashlib.sha256(canonical(value)).hexdigest()
def pairs(items):
 out={}
 for k,v in items:require(k not in out,'duplicate JSON key');out[k]=v
 return out
def invalid_constant(x):raise Refusal('nonfinite JSON constant: '+x)
def decode(body):
 try:return json.loads(body,object_pairs_hook=pairs,parse_constant=invalid_constant)
 except(UnicodeError,json.JSONDecodeError)as e:raise Refusal('invalid JSON')from e
def relative(value):
 require(isinstance(value,str)and value and '\\'not in value and '\0'not in value,'invalid relative path')
 p=PurePosixPath(value);require(not p.is_absolute()and p.as_posix()==value and all(x not in('.','..')for x in p.parts),'noncanonical path');return p
def plain_path(path):
 p=Path(path).absolute()
 for q in (p,*p.parents):require(not q.is_symlink(),'symlink path forbidden')
 return p
def bounded_read(path,limit=32*1024*1024,pin=None):
 guard("bounded read admission");p=plain_path(path);before=p.lstat();require(stat.S_ISREG(before.st_mode)and before.st_nlink==1,'ordinary single-link file required');require(0<=before.st_size<=limit,'read quota')
 fd=os.open(p,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
 try:
  info=os.fstat(fd);require((info.st_dev,info.st_ino)==(before.st_dev,before.st_ino),'file replaced before open')
  with os.fdopen(fd,'rb',closefd=False)as stream:body=stream.read(limit+1)
  after=os.fstat(fd);require(len(body)<=limit and (info.st_size,info.st_mtime_ns,info.st_ctime_ns)==(after.st_size,after.st_mtime_ns,after.st_ctime_ns),'file changed during read')
 finally:os.close(fd)
 end=p.lstat();require((end.st_dev,end.st_ino,end.st_size,end.st_mtime_ns)==(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns),'file replaced during read')
 got={'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
 if pin is not None:require(all(got[k]==pin[k]for k in got),'content pin mismatch')
 guard("bounded read completion");return body,got
def load(path,limit=32*1024*1024,pin=None):return decode(bounded_read(path,limit,pin)[0])
def make_dir(path,exist_ok=False):
 guard('directory creation');p=plain_path(path);c=current()
 if p.exists():require(exist_ok and p.is_dir(),'fresh directory required');return
 if c is not None:c.campaign.ledger.directories(p)
 else:p.mkdir(parents=True,exist_ok=exist_ok)
 guard('directory creation completion')
def write_bytes_new(path,body,closing=False):
 p=plain_path(path);c=current()
 if c is not None:return c.campaign.ledger.ordinary(p,body,closing=closing)
 p.parent.mkdir(parents=True,exist_ok=True);fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb')as out:out.write(body);out.flush();os.fsync(out.fileno())
 return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
def write_new(path,value,closing=False):return write_bytes_new(path,canonical(value)+b'\n',closing)
def append_record(path,value):
 c=current();require(c is not None,'trusted journal requires campaign accounting');return c.campaign.ledger.ordinary(path,canonical(value)+b'\n',append=True)
def copy_new(src,dst,pin,limit):
 body,got=bounded_read(src,limit,pin);write_bytes_new(dst,body);return got
def exact_keys(obj,required,optional=()):
 require(isinstance(obj,dict),'object required');require(set(required)<=set(obj)<=set(required)|set(optional),'unknown or missing keys')
def integer(x,minimum=0):require(type(x)is int and x>=minimum,'integer domain');return x
def finite(x):require(type(x)in(int,float)and math.isfinite(x),'finite number required');return x
def token(x):require(isinstance(x,str)and 0<len(x)<=160 and all(c.isalnum()or c in'._-'for c in x),'invalid opaque token');return x
def keyed(rows,key='id'):
 require(isinstance(rows,list),'row list required');out={}
 for row in rows:
  require(isinstance(row,dict)and key in row,'missing row key');k=token(row[key]);require(k not in out,'duplicate row identity');out[k]=row
 return out
def census(root,max_files,max_bytes):
 guard("census admission");root=plain_path(root);rows=[];total=0;entries=0
 for base,dirs,files in os.walk(root,followlinks=False):
  for name in dirs+files:
   guard("census member");p=Path(base)/name;st=p.lstat();entries+=1;require(entries<=max_files,'writable entry ceiling')
   require(not stat.S_ISLNK(st.st_mode),'writable symlink forbidden')
   if stat.S_ISDIR(st.st_mode):continue
   require(stat.S_ISREG(st.st_mode)and st.st_nlink==1,'writable special/hardlink forbidden');total+=st.st_size;require(total<=max_bytes,'writable byte ceiling')
   rows.append({'path':p.relative_to(root).as_posix(),'bytes':st.st_size})
 return {'files':sorted(rows,key=lambda x:x['path']),'entries':entries,'bytes':total}
def seal_tree(root,max_files,max_bytes):
 inventory=census(root,max_files,max_bytes);pins=[]
 for row in inventory['files']:
  _,pin=bounded_read(Path(root)/row['path'],max_bytes);pins.append({'path':row['path'],**pin})
 guard('seal completion');return {'files':pins,'bytes':inventory['bytes'],'entries':inventory['entries'],'id':identity(pins)}
def verify_tree(root,sealed,max_files,max_bytes):
 now=seal_tree(root,max_files,max_bytes);require(now==sealed,'sealed tree changed');return now
def now():return time.monotonic()
