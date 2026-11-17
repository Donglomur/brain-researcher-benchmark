"""One protected gold capture; unchanged original195-field numerical comparison."""
import argparse,hashlib,json,os,stat,sys,types
from pathlib import Path

def captured(path,cap,expected=None):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd)
        if not(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and 0<a.st_size<=cap):raise ValueError('Bounded native input')
        with os.fdopen(fd,'rb',closefd=False) as f:raw=f.read(a.st_size+1)
        z=os.fstat(fd)
        if len(raw)!=a.st_size or any(getattr(a,k)!=getattr(z,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')):raise ValueError('Stable native capture')
    finally:os.close(fd)
    if expected is not None and {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}!=expected:raise ValueError('Exact native input pin')
    return raw

def loaded(name,raw):
    m=types.ModuleType(name);m.__file__='/source/'+name+'.py';sys.modules[name]=m;exec(compile(raw,m.__file__,'exec'),m.__dict__);return m

def evaluate(report_raw,metadata_raw,rows,source,gold_loader):
    public=loaded('_public078',source['public_report.py']).load(source['report_contract.py'])
    report=public.validate_report(public.strict_json_bytes(report_raw))
    # Private metadata and gold are deferred until complete public validation.
    loaded('bound_io',source['bound_io.py']);loaded('admission',source['admission.py']);binding=loaded('gold_binding',source['gold_binding.py'])
    pins={n:{'bytes':len(source[n]),'sha256':hashlib.sha256(source[n]).hexdigest()} for n in ('analysis_core.py','score.py')}
    gold_pin=binding.validate(metadata_raw,rows,list(public.PEOPLE),pins)
    core=loaded('analysis_core',source['analysis_core.py']);score=loaded('_unchanged078_score',source['score.py'])
    core.validate_report(report)
    calls=0
    def once():
        nonlocal calls
        calls+=1
        if calls!=1:raise ValueError('Exactly one protected gold capture')
        raw=gold_loader(gold_pin)
        if {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}!=gold_pin:raise ValueError('Protected gold hash')
        return core.validate_report(core.strict_json_bytes(raw))
    result=score.compare(report,once())
    if calls!=1 or result['required_fields']!=195:raise ValueError('Whole195 unchanged score with one gold capture')
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs-sha256',required=True);a=p.parse_args()
    raw=captured('/inputs/INPUTS.json',65536)
    if hashlib.sha256(raw).hexdigest()!=a.inputs_sha256:raise ValueError('Externally bound native inputs')
    plan=json.loads(raw);source={};expected={'public_report.py','report_contract.py','bound_io.py','admission.py','gold_binding.py','analysis_core.py','score.py'}
    if set(plan)!= {'sources','report','metadata','rows'} or set(plan['sources'])!=expected:raise ValueError('Exact native input graph')
    for name,pin in plan['sources'].items():source[name]=captured('/source/'+name,100000,pin)
    report=captured('/inputs/report.json',65536,plan['report'])
    # Validate complete public report before even capturing reference metadata.
    validator=loaded('_pre078',source['public_report.py']).load(source['report_contract.py']);validator.validate_report(validator.strict_json_bytes(report))
    rows=json.loads(captured('/inputs/ROWS.json',65536,plan['rows']))
    if set(plan['metadata'])!={'TARGET_BINDING.json','WORKER_COMPLETION.json','RECOVERY_ATTEMPT.json','RECOVERY_COMPLETION.json'}:raise ValueError('Complete admitted recovery metadata')
    metadata={name:captured('/private/'+name,32768,pin) for name,pin in plan['metadata'].items()}
    result=evaluate(report,metadata,rows,source,lambda pin:captured('/private/GOLD.json',65536,pin))
    raw=(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    if len(raw)>65536:raise ValueError('Bounded complete score output')
    sys.stdout.buffer.write(raw);sys.stdout.buffer.flush()
if __name__=='__main__':main()
