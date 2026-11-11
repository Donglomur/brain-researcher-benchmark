"""Operator-invoked authenticated bootstrap, not used during BUILD ONLY.

Arguments are the independently selected profile/signature/trust-key paths and
their exact byte/SHA pins, original monotonic origin/deadline and an independently
selected whole host-read ceiling. The authenticated profile must match it. Trust-key
selection is external evaluator authority; no such authority is issued here.
The bootstrap and Python/native image themselves require independent admission.
"""
import argparse,hashlib,importlib.abc,importlib.util,json,os,stat,sys,time
from pathlib import Path

def capture(path,size,sha,deadline,receipt=None):
    if type(size)is not int or not 0<=size<=1<<20:raise ValueError('bounded bootstrap member')
    p=Path(path)
    if not p.is_absolute():raise ValueError('absolute selected bootstrap input')
    for parent in p.parents:
        if not stat.S_ISDIR(os.lstat(parent).st_mode):raise ValueError('ordinary bootstrap parents')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    if receipt is not None:receipt['fd_acquired']=True;receipt['close_state']='open'
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size!=size or before.st_mode&0o222:raise ValueError('exact sealed bootstrap file')
        parts=[];left=size
        while left:
            if time.monotonic()>=deadline:raise TimeoutError('bootstrap original deadline')
            b=os.read(fd,min(left,65536))
            if receipt is not None:receipt['returned_bytes']+=len(b)
            if not b:raise ValueError('short bootstrap member')
            parts.append(b);left-=len(b)
        stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        extra=os.read(fd,1)
        if receipt is not None:receipt['returned_bytes']+=len(extra)
        if extra or stamp(before)!=stamp(os.fstat(fd)) or stamp(before)!=stamp(os.lstat(p)):raise ValueError('changed bootstrap file')
        raw=b''.join(parts)
        if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('bootstrap pin mismatch')
        if receipt is not None:receipt['body_verified']=True
        return raw
    finally:
        primary=sys.exception()
        if receipt is not None:receipt['close_state']='unknown'
        try:
            os.close(fd)
            if receipt is not None:receipt['close_state']='closed'
        except BaseException as later:
            if primary is not None:raise BaseExceptionGroup('bootstrap capture and close',[primary,later])from None
            raise

def run(args):
    failures=[];raw_first=None
    account={'logical_read_reserved':0,'host_read_cap':None,'reservations':[],
             'captures':[],'startup_physical_costs_unknown':True}
    # This same live prefix exists before the first possible capture or refusal.
    known=[account]
    owner={'failures':failures,'known_prefix':known,'raw_first':None,'unknown_effects':True}
    def reserve(stage,specs):
        # Validate the whole finite group before a single member is opened.
        for path,size,sha in specs:
            if type(size)is not int or not 0<=size<=1<<20:raise ValueError('bounded bootstrap member')
            if type(sha)is not str or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):raise ValueError('exact bootstrap SHA256')
        count=sum(size+1 for _,size,_ in specs)
        reservation={'stage':stage,'requested_bytes':count,'admitted':False}
        account['reservations'].append(reservation)
        if account['logical_read_reserved']+count>account['host_read_cap']:
            raise ValueError('bootstrap group exceeds whole host read cap before capture')
        account['logical_read_reserved']+=count;reservation['admitted']=True
        receipts=[]
        for path,size,sha in specs:
            receipt={'stage':stage,'path':path,'bytes':size,'sha256':sha,
                     'logical_reserved':size+1,'attempted':False,'returned_bytes':0,
                     'capture_returned':False,'body_verified':False,'fd_acquired':False,
                     'close_state':'not_acquired'}
            account['captures'].append(receipt);receipts.append(receipt)
        return receipts
    def captured(receipt):
        receipt['attempted']=True
        raw=capture(receipt['path'],receipt['bytes'],receipt['sha256'],args.deadline,receipt=receipt)
        receipt['capture_returned']=True
        return raw
    try:
        # The fixed caller's original Namespace retains custody even when the
        # eventual raw exception refuses attribute attachment. This precedes I/O.
        args.n041_bootstrap_owner=owner
        if type(args.host_read_bytes)is not int or args.host_read_bytes<0:raise ValueError('explicit whole host read ceiling')
        account['host_read_cap']=args.host_read_bytes
        if not args.origin<=time.monotonic()<args.deadline:raise ValueError('one original invocation clock')
        prefix=reserve('profile_signature_key',[(args.profile,args.profile_bytes,args.profile_sha),
            (args.signature,64,args.signature_sha),(args.trust_key,32,args.trust_key_sha)])
        raw=captured(prefix[0])
        def pairs(rows):
            d={}
            for k,v in rows:
                if k in d:raise ValueError('duplicate profile key')
                d[k]=v
            return d
        profile=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in()).throw(ValueError('nonfinite')))
        signature=captured(prefix[1]);key=captured(prefix[2])
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        canonical=json.dumps(profile,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
        Ed25519PublicKey.from_public_bytes(key).verify(signature,canonical)
        if type(profile['host_read_bytes'])is not int or profile['host_read_bytes']!=account['host_read_cap']:
            raise ValueError('authenticated profile must match original host read ceiling')
        files=profile['source']
        if type(files)is not dict or not 1<=len(files)<=128:raise ValueError('finite signed source closure')
        specs=[]
        for name,p in files.items():
            if type(name)is not str or not name.endswith('.py') or '/' in name or '\\' in name or name.startswith('.'):raise ValueError('source member spelling')
            if type(p)is not dict or set(p)!={'bytes','sha256'} or type(p['bytes'])is not int or not 0<=p['bytes']<=1<<20:raise ValueError('exact bounded source member')
            specs.append((str(Path(profile['source_root'])/name),p['bytes'],p['sha256']))
        if sum(s for _,s,_ in specs)>16<<20:raise ValueError('finite signed source extent')
        source_receipts=reserve('complete_source',specs)
        bodies={}
        for name,receipt in zip(files,source_receipts):
            bodies[name[:-3]]=(captured(receipt),name)
        class Captured(importlib.abc.MetaPathFinder,importlib.abc.Loader):
            def find_spec(self,fullname,path=None,target=None):return importlib.util.spec_from_loader(fullname,self) if fullname in bodies else None
            def create_module(self,spec):return None
            def exec_module(self,module):
                if time.monotonic()>=args.deadline:raise TimeoutError('source import original deadline')
                raw,name=bodies[module.__name__];module.__file__=str(Path(profile['source_root'])/name)
                exec(compile(raw,module.__file__,'exec',dont_inherit=True),module.__dict__)
        if any(k in sys.modules for k in bodies):raise ValueError('no stale task source module')
        sys.meta_path.insert(0,Captured())
        from entry import run as invoke
        return invoke(profile,signature,key,args.origin,args.deadline,account)
    except BaseException as error:
        raw_first=error;owner['raw_first']=error;failures.append(('bootstrap',error))
    try:raw_first.n041_bootstrap=owner
    except BaseException as later:failures.append(('bootstrap_owner_attachment',later))
    raise raw_first

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in('profile','profile-sha','signature','signature-sha','trust-key','trust-key-sha'):p.add_argument('--'+n,required=True)
    p.add_argument('--profile-bytes',type=int,required=True)
    p.add_argument('--host-read-bytes',type=int,required=True)
    p.add_argument('--origin',type=float,required=True);p.add_argument('--deadline',type=float,required=True)
    run(p.parse_args())
