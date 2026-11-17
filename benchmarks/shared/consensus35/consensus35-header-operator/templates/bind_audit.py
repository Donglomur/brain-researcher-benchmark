"""Compose the exact offline audit request after natural producer return.
No producer dispatch or audit execution; authority remains false for root selection.
"""
import argparse,hashlib,json,os,stat
from pathlib import Path
HERE=Path(__file__).resolve().parent
E = Path('/UNCONFIGURED')
P = Path('/UNCONFIGURED/producer')
C = Path('/UNCONFIGURED/capture')
A = Path('/UNCONFIGURED/audit')
def pin(path,cap=65536):
 p=Path(path)
 if not p.is_absolute() or any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('ordinary absolute metadata')
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 with os.fdopen(fd,'rb') as f:
  s=os.fstat(f.fileno())
  if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or not 0<=s.st_size<=cap:raise ValueError('bounded metadata')
  b=f.read(s.st_size+1);z=os.fstat(f.fileno())
 keys=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')
 if len(b)!=s.st_size or any(getattr(s,k)!=getattr(z,k) or getattr(s,k)!=getattr(p.lstat(),k) for k in keys):raise ValueError('stable metadata')
 return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()},b
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--owner-request',required=True)
 p.add_argument('--bytes',type=int,required=True);p.add_argument('--sha256',required=True)
 p.add_argument('--output',required=True);a=p.parse_args()
 owner,body=pin(a.owner_request)
 if owner['bytes']!=a.bytes or owner['sha256']!=a.sha256 or json.loads(body)['execution_authority'] is not True:raise ValueError('selected owner pin')
 out=Path(a.output)
 if out.parent!=C or out.name!='AUDIT_REQUEST_INERT.json':raise ValueError('literal external inert audit proposal')
 req={'schema':'consensus35_offline_header_audit_v1','execution_authority':False,
      'root_authority':'INERT: root selection required; this composition does not execute an audit.',
      'owner_request':owner,'outer_birth':pin(Path(str(P)+'.OUTER_BIRTH.json'))[0],
      'launch':pin(C/'LAUNCH.json',16384)[0],'returned':pin(C/'RETURN.json',16384)[0],
      'auditor':pin(HERE/'audit.py',262144)[0],'output_path':str(A)}
 raw=(json.dumps(req,sort_keys=True,indent=2)+'\n').encode()
 fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 print(json.dumps({'path':str(out),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'execution_authority':False}))
if __name__=='__main__':main()

