"""Compile only pinned original public-contract support code; never fit or grade."""
import hashlib,os,stat,sys,types
from pathlib import Path
PINS={'interface.py':(7408,'fbfddcd29f6db5d200c58f46dbe331113757a7a976032f296bb33dd2fd56a56e'),
      'report_contract.py':(19245,'05e596a155a94716768a05df14d0467b4ab1f86f634fd44e3d2f8b33fa56d4f7'),
      'DESIGN.json':(773647,'3e4e7fec421ab57c61e19b66859f0434b314357de5c44dcf2957f6a5057108ec')}
INPUT_SHA='a755865f96debdad0ccb2ff2e2e395c0637e27a174178f4537ac59cedcf5e9db'
EXPORT_SHA='21124b4827954d756cbcd4575fe879bc4e9a23adda48eacdd9be197dd29f9e85'

def original(name):
    size,sha=PINS[name];p=Path('/support')/name;fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd)
        if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or a.st_size!=size:raise ValueError('support member type/extent')
        chunks=[];left=size+1
        while left:
            b=os.read(fd,min(65536,left))
            if not b:break
            chunks.append(b);left-=len(b)
        z=os.fstat(fd);n=p.lstat();fields=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
        if not all(getattr(a,k)==getattr(z,k)==getattr(n,k) for k in fields):raise ValueError('stable support capture')
    finally:os.close(fd)
    body=b''.join(chunks)
    if len(body)!=size or hashlib.sha256(body).hexdigest()!=sha:raise ValueError('original support pin')
    return body

def result(export_sha):
    return dict(task_id='NEURAL-052',status='support_consistent_artifact_only',participants=['01','02','03'],total_rows=3600,folds_per_person=15,fixed_models=4,shared_concept_draws=1000,private_reference_calls=0,numerical_values_verified=False,scientific_qualification_added=False,operator_entrypoint='neural052_full3_support_v1',export_manifest_sha256=export_sha,requires_observed_cli_exit_zero=True)

def main():
    if len(sys.argv)!=2 or sys.argv[1]!=EXPORT_SHA:raise ValueError('exact export SHA operand')
    if sys.version_info[:3]!=(3,12,8):raise ValueError('selected Python version')
    cg=Path('/sys/fs/cgroup')
    if os.getuid()!=65534 or (cg/'memory.max').read_text().strip()!='2147483648' or (cg/'memory.swap.max').read_text().strip()!='0' or (cg/'pids.max').read_text().strip()!='64':raise ValueError('trusted admission bounds')
    quota,period=map(int,(cg/'cpu.max').read_text().split())
    if quota!=period or period<=0:raise ValueError('trusted admission one CPU')
    bodies={name:original(name) for name in PINS}
    interface=types.ModuleType('interface');interface.__file__='/support/interface.py'
    exec(compile(bodies['interface.py'],interface.__file__,'exec'),interface.__dict__);sys.modules['interface']=interface
    contract=types.ModuleType('neural052_contract');contract.__file__='/support/report_contract.py'
    exec(compile(bodies['report_contract.py'],contract.__file__,'exec'),contract.__dict__)
    design=interface.decode_json(bodies['DESIGN.json'],cap=1000000)
    report=interface.decode_json(interface.capture_regular('/submission/result.json',cap=4000000),cap=4000000)
    methods=interface.capture_regular('/submission/METHODS.md',cap=1048576)
    if not methods or '\0' in methods.decode('utf-8'):raise ValueError('complete UTF8 METHODS')
    contract.validate_report(report,design)
    if report['input_manifest_sha256']!=INPUT_SHA:raise ValueError('exact complete public input identity')
    interface.write_json_fresh('/output/support.json',result(sys.argv[1]),cap=262144)
if __name__=='__main__':main()
