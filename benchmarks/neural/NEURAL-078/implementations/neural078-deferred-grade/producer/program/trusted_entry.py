"""Public report-schema admission only. No package, arrays, private code or gold mount."""
import hashlib,json,os,stat,sys,types
from pathlib import Path

def main():
    if len(sys.argv)!=2:raise ValueError('exact export SHA operand')
    import numpy,scipy
    if sys.version_info[:2]!=(3,12) or numpy.__version__!='2.2.6' or scipy.__version__!='1.15.3':raise ValueError('selected dependency versions')
    cg=Path('/sys/fs/cgroup')
    if os.getuid()!=65534 or (cg/'memory.max').read_text().strip()!='268435456' or (cg/'memory.swap.max').read_text().strip()!='0' or (cg/'pids.max').read_text().strip()!='64':raise ValueError('trusted admission bounds')
    quota,period=map(int,(cg/'cpu.max').read_text().split())
    if quota!=period or period<=0:raise ValueError('trusted admission one CPU')
    p=Path('/submission/report.json');fd=os.open(p,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
    try:
        a=os.fstat(fd)
        if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or not 0<a.st_size<=65536:raise ValueError('bounded report')
        raw=os.read(fd,65537);z=os.fstat(fd);n=p.lstat()
        if len(raw)!=a.st_size or any(getattr(a,k)!=getattr(z,k) or getattr(z,k)!=getattr(n,k) for k in ('st_dev','st_ino','st_size','st_mode','st_nlink','st_mtime_ns','st_ctime_ns')):raise ValueError('stable report')
    finally:os.close(fd)
    source=Path('/trusted/report_contract.py').read_bytes()
    contract=types.ModuleType('public_report_contract')
    exec(compile(source,'/trusted/report_contract.py','exec'),contract.__dict__)
    contract.validate_report(contract.strict_json_bytes(raw))
    result=dict(task_id='NEURAL-078',status='schema_support_consistent_artifact_only',participants=8,required_fields=195,private_reference_calls=0,numeric_comparison_performed=False,scientific_qualification_added=False,operator_entrypoint='neural078_public_report_admission_v1',export_manifest_sha256=sys.argv[1],requires_observed_cli_exit_zero=True)
    with open('/output/report.json','xb') as f:
        f.write((json.dumps(result,sort_keys=True,separators=(',',':'))+'\n').encode());f.flush();os.fsync(f.fileno())
if __name__=='__main__':main()
