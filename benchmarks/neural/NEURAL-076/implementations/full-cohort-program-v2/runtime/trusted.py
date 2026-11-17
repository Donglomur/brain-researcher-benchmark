"""Fixed NEURAL076 source-bound entry; no execution without explicit root operands."""
import time
ORIGIN=time.monotonic()
import sys,hashlib,types,os,stat
from pathlib import Path
HERE=Path(__file__).absolute().parent
BOOTSTRAP_PIN={'bytes': 2143, 'sha256': 'cd2388db9872bff4e9bd60ca2c1e21c75de4a834a5d573266e3ce57f1c1e7075'}

def main():
    if not(sys.flags.isolated and sys.dont_write_bytecode):raise ValueError('isolated no-bytecode entry')
    if '--source-sha256'not in sys.argv:raise ValueError('explicit source pin')
    p=HERE/'bootstrap.py'
    if any(x.is_symlink()for x in(p,*p.parents)):raise ValueError('unlinked bootstrap')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        s=os.fstat(fd)
        if not stat.S_ISREG(s.st_mode)or s.st_nlink!=1 or s.st_size!=BOOTSTRAP_PIN['bytes']:raise ValueError('bootstrap extent')
        b=os.read(fd,s.st_size+1)
    finally:os.close(fd)
    if len(b)!=BOOTSTRAP_PIN['bytes']or hashlib.sha256(b).hexdigest()!=BOOTSTRAP_PIN['sha256']:raise ValueError('bootstrap identity')
    m=types.ModuleType('_fixed_bootstrap');exec(compile(b,str(p),'exec'),m.__dict__)
    loader,bodies,manifest,source=m.load(HERE,sys.argv[sys.argv.index('--source-sha256')+1])
    return loader('trusted_worker').main(sys.argv[1:],loader,bodies,manifest,source)
if __name__=='__main__':raise SystemExit(main())
