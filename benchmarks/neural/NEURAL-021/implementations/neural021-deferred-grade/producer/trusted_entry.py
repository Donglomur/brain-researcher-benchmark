"""Execute only unchanged public format validation; no private target or score."""
import hashlib,json,os,stat,sys,types
from pathlib import Path
INTERFACE={'bytes':3533,'sha256':'c748bdb0386713d505e1d5d79bec51645263b859471011df81f205168a6e61e2'}
CASES={'bytes':4075,'sha256':'f5fc38ca363db9367e259c466fc017af9e8e216726b302cc6f757857554c34c0'}

def need(ok,message):
    if not ok:raise ValueError(message)

def capture(p,cap,expected=None):
    p=Path(p);fd=os.open(p,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
    try:
        a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and 0<a.st_size<=cap,'ordinary support input')
        parts=[];left=a.st_size+1
        while left:
            raw=os.read(fd,min(65536,left))
            if not raw:break
            parts.append(raw);left-=len(raw)
        raw=b''.join(parts);z=os.fstat(fd);n=p.lstat()
        need(len(raw)==a.st_size and all(getattr(a,k)==getattr(z,k)==getattr(n,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')),'stable support input')
    finally:os.close(fd)
    need(expected is None or {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}==expected,'exact support source')
    return raw

def main():
    need(len(sys.argv)==2 and sys.argv[1]==CASES['sha256'],'exact public cases operand')
    cg=Path('/sys/fs/cgroup')
    need(os.getuid()==65534 and (cg/'memory.max').read_text().strip()=='1073741824' and (cg/'memory.swap.max').read_text().strip()=='0' and (cg/'pids.max').read_text().strip()=='64','observed support resources')
    quota,period=map(int,(cg/'cpu.max').read_text().split());need(quota==period and period>0,'support CPU')
    need(sys.version_info[:3]==(3,12,8),'selected support Python')
    source=capture('/support/interface.py',3533,INTERFACE)
    interface=types.ModuleType('neural021_public_format');exec(compile(source,'/support/interface.py','exec'),interface.__dict__)
    cases=interface.strict_json(capture('/support/cases.json',4075,CASES))
    rows=interface.validate_queries(cases)
    need(len(rows)==92 and sum(x['condition']=='active' for x in rows)==52 and sum(x['condition']=='passive' for x in rows)==40,'complete selected public roster')
    raw=capture('/submission/submission.json',4194304)
    result=interface.validate_submission(interface.strict_json(raw),cases,CASES['sha256'])
    need(len(result)==92,'complete format validation')
    report=dict(task_id='NEURAL-021',status='public_format_admitted_ungraded',query_trials=92,active_queries=52,perturbation_queries=40,time_bins=30,velocity_axes=2,cases_sha256=CASES['sha256'],private_target_calls=0,numerical_values_verified=False,scientific_qualification_added=False,operator_entrypoint='neural021_full92_public_support_v1',requires_observed_cli_exit_zero=True)
    body=(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n').encode()
    fd=os.open('/output/support.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        left=memoryview(body)
        while left:n=os.write(fd,left);need(n>0,'complete support write');left=left[n:]
        os.fsync(fd)
    finally:os.close(fd)
    fd=os.open('/output',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
if __name__=='__main__':main()
