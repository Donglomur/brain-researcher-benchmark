"""Pinned minimal container entrypoint. Never imported by source-only controls.

The host controller supplies an immutable request and exact mounts. Container
stdout is the sole result channel; neither candidate nor model sees engine keys,
source identities, sibling query packets, labels, reports or host writable paths.
"""
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import sys
import time


def clean(value):
 if hasattr(value,'tolist'): return clean(value.tolist())
 if hasattr(value,'item'): return clean(value.item())
 if isinstance(value,dict): return {str(k):clean(v) for k,v in value.items()}
 if isinstance(value,(list,tuple)): return [clean(x) for x in value]
 if value is None or isinstance(value,(str,bool,int)): return value
 if isinstance(value,float) and math.isfinite(value): return value
 raise ValueError('finite JSON-compatible result required')

def main():
 raw=Path('/input/request.json').read_bytes(); req=json.loads(raw)
 started=time.monotonic(); usage0=resource.getrusage(resource.RUSAGE_SELF)
 limits=req['supervision']
 worker_status={k:v.strip() for k,v in (line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)}
 supervisor_status={k:v.strip() for k,v in (line.split(':',1) for line in Path('/proc/1/status').read_text().splitlines() if ':' in line)}
 identities={'worker_uids':list(os.getresuid()),'worker_gids':list(os.getresgid()),'supervisor_uids':[int(x) for x in supervisor_status['Uid'].split()],'supervisor_gids':[int(x) for x in supervisor_status['Gid'].split()],'worker_cap_effective':worker_status['CapEff'],'worker_no_new_privileges':worker_status['NoNewPrivs'],'supervisor_cap_effective':supervisor_status['CapEff'],'supervisor_no_new_privileges':supervisor_status['NoNewPrivs'],'private_pid':os.getpid(),'supervisor_pid':os.getppid()}
 if identities['worker_uids']!=[limits['worker_uid']]*3 or identities['worker_gids']!=[limits['worker_gid']]*3 or identities['supervisor_uids']!=[limits['supervisor_uid']]*4 or identities['supervisor_gids']!=[limits['supervisor_gid']]*4 or any(int(identities[k],16)!=0 for k in ('worker_cap_effective','supervisor_cap_effective')) or any(identities[k]!='1' for k in ('worker_no_new_privileges','supervisor_no_new_privileges')) or identities['supervisor_pid']!=1:raise ValueError('actual privileged/identity/supervisor separation differs from sealed runtime')
 read_bytes=len(raw); write_bytes=0; plots=[]
 operation=req['operation']; inp=out=0; vram=0
 if operation=='numeric':
  import numpy as np
  import scipy as sp
  import scipy.linalg,scipy.signal,scipy.stats,scipy.special,scipy.optimize,scipy.interpolate,scipy.integrate
  import importlib.util
  spec=importlib.util.spec_from_file_location("safe_python","/code/safe_python.py")
  safe_python=importlib.util.module_from_spec(spec);spec.loader.exec_module(safe_python)
  tree=safe_python.validate_code(req['code'])
  def plot(x,y):
   nonlocal write_bytes
   import matplotlib
   matplotlib.use('Agg')
   from matplotlib import pyplot as plt
   name=Path('/scratch')/('plot-'+str(len(plots))+'.png')
   fig,ax=plt.subplots();ax.plot(x,y);fig.savefig(name);plt.close(fig)
   body=name.read_bytes();write_bytes+=len(body)
   if write_bytes>req['write_bytes']: raise ValueError('plot write budget exceeded')
   plots.append({'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'png_base64':base64.b64encode(body).decode()})
   return {'plot_index':len(plots)-1}
  builtin={k:getattr(__import__('builtins'),k) for k in ('abs','min','max','sum','len','range','enumerate','zip','sorted','float','int','bool','list','dict','tuple','round','all','any')}
  # Print is captured to a bounded logical transcript instead of stdout protocol.
  printed=[]
  def printing(*args):
   nonlocal write_bytes
   text=' '.join(str(a) for a in args);write_bytes+=len(text.encode())
   if write_bytes>req['write_bytes']: raise ValueError('print budget exceeded')
   printed.append(text)
  scope={'__builtins__':builtin,'np':np,'sp':sp,'math':math,'data':req['data'],'inputs':req.get('inputs',{}),'artifacts':req.get('artifacts',{}),'plot':plot,'print':printing}
  exec(compile(tree,'<scientific-script>','exec'),scope,scope)
  result={'value':clean(scope['result']),'plots':plots,'printed':printed}
 elif operation=='event_output':
  value=req['prediction'];event=req['event']
  if set(value)!={'id','values'} or value['id']!=event['id'] or len(value['values'])!=3 or any(type(x) not in (int,float) or not math.isfinite(float(x)) for x in value['values']):raise ValueError('complete exact finite event prediction required')
  if event.get('split')!='query' or 'target' in event:raise ValueError('one target-free query event required')
  result=value
 elif operation in ('reference','validation'):
  sys.path.insert(0,'/code')
  if operation=='reference':
   from references.tool import predict_one
   result=predict_one(req['model'],{'view':req['view'],'event':req['event']})
  else:
   from owner.scoring import absolute,admit_predictions
   predictions=admit_predictions(req['predictions'],[r['id'] for r in req['validation']])
   result=absolute(predictions,req['validation'],req['fit_scale'],15)['primary']
 elif operation=='model':
  import torch
  from transformers import AutoTokenizer,AutoModelForCausalLM
  torch.set_num_threads(req['cpu_threads']);torch.manual_seed(632026)
  if not torch.cuda.is_available() or torch.cuda.device_count()!=1: raise ValueError('one actual allocated GPU required')
  prop=torch.cuda.get_device_properties(0)
  if prop.total_memory!=req['gpu_total_bytes'] or prop.total_memory>48*2**30: raise ValueError('GPU memory differs from matched exact allocation')
  torch.cuda.set_per_process_memory_fraction(1.0,0)
  torch.cuda.reset_peak_memory_stats()
  tok=AutoTokenizer.from_pretrained('/checkpoint',local_files_only=True,trust_remote_code=False)
  model=AutoModelForCausalLM.from_pretrained('/checkpoint',local_files_only=True,trust_remote_code=False,use_safetensors=True,torch_dtype=torch.bfloat16).to('cuda').eval()
  encoded=tok(req['prompt'],return_tensors='pt');inp=int(encoded['input_ids'].numel())
  if inp>req['input_tokens_remaining']: raise ValueError('input token allowance exceeded before generation')
  with torch.inference_mode():
   ids=model.generate(**{k:v.to('cuda') for k,v in encoded.items()},do_sample=False,max_new_tokens=req['max_new_tokens'],use_cache=True,pad_token_id=tok.eos_token_id)
  generated=ids[0,encoded['input_ids'].shape[1]:];out=int(generated.numel())
  result={'text':tok.decode(generated,skip_special_tokens=True)}
  torch.cuda.synchronize();vram=int(torch.cuda.max_memory_reserved())
  read_bytes+=req['checkpoint_bytes']
 else: raise ValueError('unrecognized capsule operation')
 usage=resource.getrusage(resource.RUSAGE_SELF)
 proc_io={k:int(v.strip()) for k,v in (line.split(':',1) for line in Path('/proc/self/io').read_text().splitlines())}
 charged_reads=proc_io['rchar']+(req['checkpoint_bytes'] if operation=='model' else 0)
 charged_writes=max(proc_io['wchar'],write_bytes)
 if charged_reads>req['read_bytes'] or charged_writes>req['write_bytes']:raise ValueError('actual kernel logical I/O plus conservative model-map charge exceeds allocation')
 output={'schema':'neural063_capsule_result_v1','operation':operation,'result':result,
  'usage':{'input_tokens':inp,'output_tokens':out,'vram_peak_bytes':vram,'logical_read_bytes':charged_reads,'logical_write_bytes':charged_writes,'kernel_proc_io':proc_io,'checkpoint_map_byte_charge':req['checkpoint_bytes'] if operation=='model' else 0,'logical_io_basis':'observed Linux proc rchar/wchar plus conservative full checkpoint-map charge; mapping charge is not physical I/O','cpu_core_seconds':usage.ru_utime+usage.ru_stime,'wall_seconds':time.monotonic()-started,'ram_peak_bytes':usage.ru_maxrss*1024,'physical_os_io_bytes':None},
  'isolation':identities,
  'runtime':{'python':sys.version,'numpy':sys.modules['numpy'].__version__ if 'numpy' in sys.modules else None,'torch':sys.modules['torch'].__version__ if 'torch' in sys.modules else None,'transformers':sys.modules['transformers'].__version__ if 'transformers' in sys.modules else None}}
 body=json.dumps(clean(output),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 if len(body)+write_bytes>req['write_bytes']: raise ValueError('complete capsule result exceeds write allowance')
 sys.stdout.buffer.write(body+b'\n');sys.stdout.buffer.flush()

def supervise():
 # PID1 is a trusted finite-lifetime supervisor. The short namespace-root
 # bootstrap holds SETUID/SETGID only and irrevocably drops both identities.
 # Different real/effective/saved UIDs plus default-denied ptrace/signals stop
 # a candidate descendant from cancelling the deadline. PID1 exit causes the
 # kernel to kill the complete private PID namespace, independent of host liveness.
 request=json.loads(Path('/input/request.json').read_bytes());limit=request['supervision']
 if os.getpid()!=1 or os.geteuid()!=0:raise ValueError('private PID1 bootstrap required')
 deadline=min(time.monotonic()+limit['wall_seconds'],limit['deadline_monotonic'])
 if time.monotonic()>=deadline or time.time()>=limit['attempt_expires_at']:os._exit(124)
 ready_r,ready_w=os.pipe()
 pid=os.fork()
 if pid==0:
  os.close(ready_w)
  os.setgroups([]);os.setresgid(limit['worker_gid'],limit['worker_gid'],limit['worker_gid']);os.setresuid(limit['worker_uid'],limit['worker_uid'],limit['worker_uid'])
  resource.setrlimit(resource.RLIMIT_CPU,(limit['cpu_core_seconds'],limit['cpu_core_seconds']))
  resource.setrlimit(resource.RLIMIT_CORE,(0,0))
  if os.read(ready_r,1)!=b'R':os._exit(126)
  os.close(ready_r)
  try:main()
  except BaseException as exc:
   sys.stderr.write(type(exc).__name__+': '+str(exc)[:2048]+'\n');sys.stderr.flush();os._exit(1)
  os._exit(0)
 os.close(ready_r)
 os.setgroups([]);os.setresgid(limit['supervisor_gid'],limit['supervisor_gid'],limit['supervisor_gid']);os.setresuid(limit['supervisor_uid'],limit['supervisor_uid'],limit['supervisor_uid'])
 os.write(ready_w,b'R');os.close(ready_w)
 while True:
  child,status,usage=os.wait4(pid,os.WNOHANG)
  if child:os._exit(os.waitstatus_to_exitcode(status) if os.WIFEXITED(status) else 125)
  if time.monotonic()>=deadline or time.time()>=limit['attempt_expires_at']:os._exit(124)
  time.sleep(0.02)

if __name__=='__main__': supervise()
