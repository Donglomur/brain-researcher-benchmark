"""Real source worker dispatch through the bounded shared process lifecycle."""
import hashlib,json,os,sys
from pathlib import Path
from .policy import validate_plan,need,digest
from .owners import admit_owners
from .source import verify_official
from .process import run_process

def command(plan_path,plan_sha,official_root,inputs_root,output_root,python_executable):
 return [str(python_executable),'-B','-m','benchmark.native.worker','--plan',str(plan_path),
  '--plan-sha256',plan_sha,'--official-root',str(official_root),'--inputs-root',str(inputs_root),'--output-root',str(output_root)]

def dispatch(plan_path,expected_sha,official_root,inputs_root,output_root,log_path,maximum_log_bytes,python_executable=sys.executable):
 plan_path=Path(plan_path);need(plan_path.stat().st_size<=16*1024*1024,'bounded complete plan');raw=plan_path.read_bytes()
 need(hashlib.sha256(raw).hexdigest()==expected_sha,'exact whole plan');plan=json.loads(raw);validate_plan(plan)
 owners=admit_owners({'official':official_root,'inputs':inputs_root},{'output':output_root,'log':log_path})
 official,inputs,output,log_path=[owners[k]for k in ('official','inputs','output','log')]
 verify_official(official,plan['official_source_sha256'])
 need(type(maximum_log_bytes)is int and 1<=maximum_log_bytes<=64*1024*1024,'explicit bounded log allocation')
 cwd=Path(__file__).resolve().parents[2];argv=command(plan_path.absolute(),expected_sha,official,inputs,output,python_executable)
 actual=run_process(argv,cwd,plan['caps']['maximum_runtime_seconds'],maximum_log_bytes,log_path,
  env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
 result=output/'RESULT.json';need(result.is_file()and result.stat().st_size<=plan['caps']['maximum_receipt_bytes'],'bounded native result')
 receipt=json.loads(result.read_bytes());need(receipt['binding']['plan_sha256']==digest(plan),'native result plan join')
 return {'exit_code':actual['returncode'],'log_bytes':actual['log_bytes'],'elapsed_seconds':actual['elapsed_seconds'],
  'cleanup':actual['cleanup'],'receipt':receipt,'scientifically_qualified':False}
