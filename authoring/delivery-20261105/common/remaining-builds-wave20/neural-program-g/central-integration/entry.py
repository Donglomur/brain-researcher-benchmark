#!/usr/bin/env python3
"""Literal central entry; trusted interpreter and externally qualified argv remain TCB."""
import hashlib,os,stat,sys,time
from pathlib import Path
EXPECTED = {'bytes': 10744, 'sha256': 'cd46ed908d4773ba18800db1f18d4ba8008e107a0cf366a482febbb085b1967d'}
p=Path(__file__).absolute().parent/'bootstrap.py'
assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
assert not any(x.is_symlink() for x in (p,*p.parents))
start=time.monotonic(); fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
try:
 a=os.fstat(fd); assert stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size==EXPECTED['bytes']
 parts=[]; total=0
 while total<=a.st_size:
  assert time.monotonic()<start+120
  block=os.read(fd,min(65536,a.st_size+1-total))
  if not block:break
  parts.append(block);total+=len(block)
 body=b''.join(parts); b=os.fstat(fd); c=p.lstat()
 assert all(getattr(a,k)==getattr(b,k)==getattr(c,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink'))
 assert len(body)==EXPECTED['bytes'] and hashlib.sha256(body).hexdigest()==EXPECTED['sha256']
finally:os.close(fd)
sys._sleep_central_bootstrap_pin=EXPECTED
exec(compile(body,'<captured-central-bootstrap>','exec'),{'__name__':'__main__','__file__':str(p)})
