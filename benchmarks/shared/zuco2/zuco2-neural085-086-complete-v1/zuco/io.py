"""Bounded ordinary-file custody; no participant imports or executable deserialization."""
import hashlib,json,math,os,stat
from pathlib import Path
class Refusal(RuntimeError):
    def __init__(self,code,detail=None):self.code=code;self.detail=detail;super().__init__(f"{code}: {detail}")
def need(value,code,detail=None):
    if not value:raise Refusal(code,detail)
def failure(e):
    out={"type":type(e).__name__,"code":getattr(e,"code",None),"message":str(e)}
    if getattr(e,"cleanup_failures",None):out["cleanup_failures"]=list(e.cleanup_failures)
    return out
def exact(o,keys):need(type(o)is dict and set(o)==set(keys),"schema_keys",sorted(set(o) if type(o)is dict else []))
def finite(x):return type(x)in(int,float) and math.isfinite(x)
def duplicates(pairs):
    out={}
    for k,v in pairs:need(k not in out,"duplicate_JSON_key",k);out[k]=v
    return out
def decode(b):
    need(type(b)is bytes,"JSON_bytes")
    return json.loads(b.decode("utf-8"),object_pairs_hook=duplicates,parse_constant=lambda s:(_ for _ in ()).throw(Refusal("nonfinite_JSON",s)))
def encode(x):return (json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False)+"\n").encode()
def digest(b):return hashlib.sha256(b if type(b)is bytes else encode(b)).hexdigest()
def pin(b):return {"bytes":len(b),"sha256":digest(b)}
def descriptor(d):
    exact(d,["path","bytes","sha256"]);need(type(d["path"])is str and type(d["bytes"])is int and 0<=d["bytes"] and type(d["sha256"])is str and len(d["sha256"])==64 and set(d["sha256"])<=set("0123456789abcdef"),"descriptor")
def path_guard(path,existing=False,guard=lambda:None):
    guard()
    p=Path(path).absolute();need(".." not in Path(path).parts,"path_traversal")
    for a in list(reversed(p.parents))+[p]:
        guard()
        try:s=a.lstat()
        except FileNotFoundError:guard();continue
        guard()
        need(not stat.S_ISLNK(s.st_mode),"symlink_ancestor",str(a))
        if a!=p:need(stat.S_ISDIR(s.st_mode),"non_directory_ancestor",str(a))
    if existing:
        guard();present=p.exists();guard();need(present,"missing_path",str(p))
    guard()
    return p
def below(root,rel,guard=lambda:None):
    need(type(rel)is str and rel and not Path(rel).is_absolute() and all(x not in (".","..","") for x in Path(rel).parts),"relative_path",rel)
    p=path_guard(Path(root)/rel,guard=guard);need(p.is_relative_to(Path(root).absolute()),"path_escape");guard();return p
def close_original(fd,original_error):
    """Always close the already-open descriptor; never replace its first cause."""
    try:os.close(fd)
    except BaseException as secondary:
        if original_error is None:raise
        original_error.cleanup_failures=getattr(original_error,"cleanup_failures",[])+[failure(secondary)]
def read(path,cap,expected=None,guard=lambda:None):
    guard();p=path_guard(path,True,guard);guard();s=p.lstat();guard();need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size<=cap,"ordinary_bounded_input",str(p))
    guard();fd=os.open(p,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0));original_error=None
    try:
        guard();a=os.fstat(fd);guard();need((a.st_dev,a.st_ino)==(s.st_dev,s.st_ino),"input_race");parts=[];n=0
        while True:
            guard();z=os.read(fd,min(65536,cap+1-n));guard()
            if not z:break
            parts.append(z);n+=len(z);need(n<=cap,"input_cap")
        b=b"".join(parts);guard();t=os.fstat(fd);guard();u=p.lstat();guard()
        key=lambda v:(v.st_dev,v.st_ino,v.st_size,v.st_mtime_ns,v.st_ctime_ns,v.st_nlink)
        need(key(a)==key(t)==key(u) and len(b)==s.st_size,"unstable_input")
    except BaseException as e:original_error=e;raise
    finally:close_original(fd,original_error)
    if expected:need(pin(b)=={k:expected[k] for k in ("bytes","sha256")},"input_identity",str(p))
    guard();return b
def write(path,b,ledger=None,guard=lambda:None,pre_reserved=False):
    need(not pre_reserved or ledger is not None,"reserved_write_requires_original_ledger")
    def check():
        guard()
        if ledger:ledger.guard(closing=pre_reserved)
    check()
    if type(b)is not bytes:b=encode(b)
    if ledger and not pre_reserved:ledger.reserve_bytes(len(b),"metadata/output")
    p=path_guard(path,guard=check);check();present=p.exists();check();need(not present,"exclusive_output",str(p))
    check();p.parent.mkdir(parents=True,exist_ok=True);check()
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600);original_error=None
    try:
        check();off=0
        while off<len(b):
            check();n=os.write(fd,b[off:]);need(n>0,"zero_write");off+=n;check()
        check();os.fsync(fd);check()
    except BaseException as e:original_error=e;raise
    finally:close_original(fd,original_error)
    check()
    return {"path":str(p),**pin(b)}
def inventory(root,file_cap,byte_cap,guard=lambda:None):
    guard();root=path_guard(root,True,guard);guard();isdir=root.is_dir();guard();need(isdir,"inventory_root");rows=[];total=0;dirs=0;pending=[root]
    while pending:
        current=pending.pop();guard();scan=os.scandir(current)
        original_error=None
        try:
            guard()
            while True:
                guard()
                try:entry=next(scan)
                except StopIteration:guard();break
                guard();f=Path(current)/entry.name;s=f.lstat();guard()
                if stat.S_ISDIR(s.st_mode):
                    dirs+=1;need(dirs<=file_cap,"directory_cap");pending.append(f);continue
                need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,"unsafe_output",str(f));total+=s.st_size;need(total<=byte_cap and len(rows)<file_cap,"inventory_cap")
                b=read(f,byte_cap,guard=guard);rows.append({"path":str(f.relative_to(root)),**pin(b)})
        except BaseException as e:original_error=e;raise
        finally:
            try:scan.close()
            except BaseException as secondary:
                if original_error is None:raise
                original_error.cleanup_failures=getattr(original_error,"cleanup_failures",[])+[failure(secondary)]
        guard()
    guard();return sorted(rows,key=lambda r:r["path"])
def verify_inventory(root,rows,file_cap,byte_cap,guard=lambda:None):
    got=inventory(root,file_cap,byte_cap,guard);need(got==rows,"inventory_changed");return got

def extent(root,file_cap,byte_cap,guard=lambda:None):
    """Live structural/size monitor; stable body hashes are collected after exit."""
    guard();root=path_guard(root,True);count=total=dirs=0
    for current,children,names in os.walk(root,followlinks=False):
        guard();dirs+=len(children);need(dirs<=file_cap,"directory_cap")
        for n in children:need(stat.S_ISDIR((Path(current)/n).lstat().st_mode),"unsafe_directory")
        for n in names:
            s=(Path(current)/n).lstat();need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,"unsafe_output");count+=1;total+=s.st_size;need(count<=file_cap and total<=byte_cap,"inventory_cap")
    guard();return {"files":count,"bytes":total}

def authenticate(path,cap,expected,guard=lambda:None):
    """Streaming body authentication without retaining a multi-GB container."""
    guard();descriptor(expected);p=path_guard(path,True);a=p.lstat();need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size<=cap,'ordinary_bounded_input');fd=os.open(p,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0));h=hashlib.sha256();n=0
    key=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink)
    try:
        need(key(os.fstat(fd))==key(a),'input_race')
        while True:
            guard();b=os.read(fd,65536)
            if not b:break
            n+=len(b);need(n<=cap,'input_cap');h.update(b)
        need(key(a)==key(os.fstat(fd))==key(p.lstat()),'unstable_input')
    finally:os.close(fd)
    need(n==expected['bytes'] and h.hexdigest()==expected['sha256'],'input_identity');guard();return {'path':str(p),'bytes':n,'sha256':h.hexdigest()}
