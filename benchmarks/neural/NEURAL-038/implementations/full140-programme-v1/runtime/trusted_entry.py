"""Exact scorer_core.admit only: public panel and closed report, no arrays or gold."""
import hashlib,json,os,stat,sys,types
from pathlib import Path
PINS={'delivery_io.py':{'bytes':4396,'sha256':'9ba54409ff3aae8e17d2c0e96f1c5f335fa46cd33aeaf83d3be427a8ebf585d7'},'analysis_core.py':{'bytes':3088,'sha256':'e75be729ca9a5f3df444b7b3441400c36af52013862b75f4eb946ed0651ed511'},'scorer_core.py':{'bytes':5933,'sha256':'9cbfd7d824935274406c6e6e3a209c96934a57833939ebc3e79838fb2ccb436b'}}
PANEL={'bytes':8367,'sha256':'495832e67560bae3b2178245ba96ea82e612bcbfcfc2a6c19402b0522ec2c65f'}

def capture(p,cap,expected=None):
    p=Path(p);fd=os.open(p,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
    try:
        a=os.fstat(fd)
        if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or not 0<a.st_size<=cap:raise ValueError('bounded ordinary admission member')
        parts=[];count=0
        while count<=cap:
            b=os.read(fd,min(65536,cap+1-count))
            if not b:break
            count+=len(b);parts.append(b)
        raw=b''.join(parts);z=os.fstat(fd);n=p.lstat()
        if len(raw)!=a.st_size or any(getattr(a,k)!=getattr(z,k) or getattr(z,k)!=getattr(n,k) for k in ('st_dev','st_ino','st_size','st_mode','st_nlink','st_mtime_ns','st_ctime_ns')):raise ValueError('stable whole admission member')
    finally:os.close(fd)
    if expected is not None and {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}!=expected:raise ValueError('exact admission source/panel pin')
    return raw

def main():
    if len(sys.argv)!=2:raise ValueError('exact export SHA operand')
    import numpy
    if sys.version_info[:2]!=(3,12) or numpy.__version__!='2.2.6':raise ValueError('selected dependency versions')
    cg=Path('/sys/fs/cgroup')
    if os.getuid()!=65534 or (cg/'memory.max').read_text().strip()!='536870912' or (cg/'memory.swap.max').read_text().strip()!='0' or (cg/'pids.max').read_text().strip()!='64':raise ValueError('trusted admission bounds')
    quota,period=map(int,(cg/'cpu.max').read_text().split())
    if quota!=period or period<=0:raise ValueError('trusted admission one CPU')
    # Capture all exact modules before compiling them. Module top levels are imports/constants only.
    bodies={n:capture('/trusted/'+n,16384,p) for n,p in PINS.items()}
    modules={}
    for name,raw in bodies.items():
        key=name[:-3];module=types.ModuleType(key);module.__file__='/trusted/'+name
        sys.modules[key]=module;exec(compile(raw,module.__file__,'exec'),module.__dict__);modules[key]=module
    io=modules['delivery_io'];core=modules['scorer_core']
    public=io.decode(capture('/public/panel.json',2000000,PANEL))
    submission=io.decode(capture('/submission/report.json',16000000))
    # No score(), reference, decompose(), means, array loading or private callback.
    core.admit(public,submission)
    result=dict(task_id='NEURAL-038',status='public_structure_consistent_artifact_only',memberships=140,blocks=4,declared_numeric_operands=866,private_reference_calls=0,numeric_comparison_performed=False,scientific_qualification_added=False,operator_entrypoint='neural038_exact_scorer_core_admit_v1',export_manifest_sha256=sys.argv[1],requires_observed_cli_exit_zero=True)
    with open('/output/report.json','xb') as f:
        f.write((json.dumps(result,sort_keys=True,separators=(',',':'))+'\n').encode());f.flush();os.fsync(f.fileno())
if __name__=='__main__':main()
