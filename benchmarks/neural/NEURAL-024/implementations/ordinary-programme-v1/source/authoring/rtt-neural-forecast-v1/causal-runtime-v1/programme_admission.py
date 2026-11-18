"""Task-specific portable source/method/custody admission. No payload execution."""
import hashlib,json,os,re,stat,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
LIMITS={'candidate_seconds':600,'work_seconds':720,'whole_seconds':780,'cleanup_seconds':60,
        'external_term_seconds':785,'external_kill_grace_seconds':5,'host_ram_bytes':4294967296,
        'container_ram_bytes':3221225472,'numerical_threads':1,'managed_bytes':110000000,'receipt_reserve_bytes':6000000}

def need(ok,message):
 if not ok:raise ValueError(message)
def canonical(v):return(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('ascii')
def pin(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def strict(b):
 def pairs(rows):
  d={}
  for k,v in rows:need(k not in d,'duplicate JSON key');d[k]=v
  return d
 return json.loads(b,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite metadata'))
def valid_pin(v,cap=100000000):return type(v)is dict and set(v)=={'bytes','sha256'}and type(v['bytes'])is int and 0<v['bytes']<=cap and type(v['sha256'])is str and re.fullmatch('[a-f0-9]{64}',v['sha256'])
def meta(path,cap,expected=None):
 p=Path(path);need(p.is_absolute()and '..'not in p.parts and all(not x.is_symlink()for x in(p,*p.parents)),'absolute unlinked input')
 s=p.lstat();need(stat.S_ISREG(s.st_mode)and s.st_nlink==1 and 0<s.st_size<=cap,'bounded single-link input')
 stamp=lambda x:(x.st_dev,x.st_ino,x.st_mode,x.st_size,x.st_nlink,x.st_mtime_ns,x.st_ctime_ns)
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  before=os.fstat(fd)
  with os.fdopen(fd,'rb',closefd=False)as stream:b=stream.read(cap+1)
  need(len(b)==before.st_size and stamp(s)==stamp(before)==stamp(os.fstat(fd))==stamp(p.lstat()),'stable input bytes')
 finally:os.close(fd)
 if expected is not None:need(pin(b)==expected,'exact selected bytes')
 return b

def method(body):
 value=strict(body)
 need(type(value)is dict and set(value)=={'schema_version','method_id','method_description','training_policy','limitations'}
      and type(value['schema_version'])is int and value['schema_version']==1,'Exact method declaration')
 need(all(type(v)is str and 0<len(v)<=4096 for k,v in value.items()if k!='schema_version'),'Bounded method text')
 return value

def descriptor(value,cap):
 need(type(value)is dict and set(value)=={'path','bytes','sha256'}and valid_pin({k:value[k]for k in('bytes','sha256')},cap),'bounded selected descriptor')
 p=Path(value['path']);need(p.is_absolute()and '..'not in p.parts,'absolute selected path');return p

def spec(value):
 keys={'task_id','mode','programme','method','case_manifest','source_manifest_pin','run','docker_host','host_runtime','runtime_dependencies','limits'}
 need(type(value)is dict and set(value)==keys and value['task_id']=='NEURAL-024'and value['mode']in('ordinary','calibration_rate'),'closed task/mode selection')
 for name,cap in(('programme',65536),('method',16384),('case_manifest',32768)):descriptor(value[name],cap)
 need(valid_pin(value['source_manifest_pin'],131072),'source manifest identity')
 run=Path(value['run']);need(run.is_absolute()and run.parent==ROOT/'artifacts-build'and re.fullmatch('[a-z0-9][a-z0-9-]{0,79}',run.name),'fresh direct owned runtime location')
 need(value['limits']==LIMITS and all(type(v)is int for v in value['limits'].values()),'unchanged original resource contract')
 endpoint=value['docker_host'];need(type(endpoint)is str and endpoint.startswith('unix:///')and not any(ord(c)<=32 for c in endpoint),'explicit local Docker socket')
 runtime=value['host_runtime'];need(type(runtime)is dict and set(runtime)=={'executable','base_executable','real_executable','version','no_site','prefix_matches_base','has_pythonexecutable_override'}
  and runtime['no_site']==0 and type(runtime['no_site'])is int and runtime['prefix_matches_base']is True and runtime['has_pythonexecutable_override']is False
  and type(runtime['version'])is list and len(runtime['version'])==3 and runtime['version'][:2]==[3,11],'selected site-enabled Python3.11 host')
 need(type(value['runtime_dependencies'])is list and 1<=len(value['runtime_dependencies'])<=16,'finite host dependency identities')
 for row in value['runtime_dependencies']:descriptor(row,100000000)
 return value

def read_admission(path,sha,read=meta):
 body=read(path,65536);need(pin(body)['sha256']==sha,'selected admission hash');value=strict(body)
 need(type(value)is dict and set(value)=={'schema','execution_authorized','spec','independent_review'}and value['schema']=='neural024-programme-admission/v1'
  and value['execution_authorized']is True,'explicit externally selected operation admission')
 selected=spec(value['spec']);r=value['independent_review'];descriptor(r,131072)
 review=strict(read(r['path'],r['bytes'],{k:r[k]for k in('bytes','sha256')}))
 need(review.get('schema')=='neural024-programme-operation-review/v1'and review.get('decision')=='accepted_for_one_operator_released_attempt'
  and review.get('spec_sha256')==pin(canonical(selected))['sha256'],'review binds exact mode/source/custody/runtime selection')
 return selected

def selected():
 path=os.environ.get('NEURAL024_OPERATION_ADMISSION');sha=os.environ.get('NEURAL024_OPERATION_ADMISSION_SHA256')
 need(type(path)is str and type(sha)is str,'explicit inherited immutable operation admission')
 return read_admission(path,sha)

def source_closure(selected,read=meta):
 body=read(ROOT/'SOURCE_MANIFEST.json',131072,selected['source_manifest_pin']);value=strict(body)
 need(type(value)is dict and set(value)=={'schema','files'}and value['schema']=='neural024-ordinary-source/v1'and type(value['files'])is dict,'closed source manifest')
 expected=value['files'];actual={str(p.relative_to(ROOT))for p in(ROOT/'authoring').rglob('*')if p.is_file()}
 actual.add('run_programme.py');need(set(expected)==actual,'complete exact source roster including entrypoint')
 for relative,p in expected.items():
  need(not Path(relative).is_absolute()and '..'not in Path(relative).parts and valid_pin(p,1000000),'relative source identity')
  path=ROOT/relative;read(path,p['bytes'],p);need(stat.S_IMODE(path.stat().st_mode)==0o444,'immutable staged source')
 return value

def runtime_identity(selected):
 actual={'executable':sys.executable,'base_executable':getattr(sys,'_base_executable',None),'real_executable':os.path.realpath(sys.executable),
  'version':list(sys.version_info[:3]),'no_site':sys.flags.no_site,'prefix_matches_base':sys.prefix==sys.base_prefix,'has_pythonexecutable_override':'PYTHONEXECUTABLE'in os.environ}
 need(actual==selected['host_runtime'],'exact selected host startup identity')
 for row in selected['runtime_dependencies']:meta(row['path'],row['bytes'],{k:row[k]for k in('bytes','sha256')})

def selected_programme(selected,read=meta):
 result={}
 for name,key,cap in(('program.py','programme',65536),('method.json','method',16384)):
  row=selected[key];result[name]=read(row['path'],cap,{k:row[k]for k in('bytes','sha256')})
 result['program.py'].decode('utf-8');method(result['method.json'])
 if selected['mode']=='calibration_rate':
  assets=strict(read(HERE/'ASSETS.json',100000))['controls']['calibration_rate']
  need(pin(result['program.py'])=={k:assets['program'][k]for k in('bytes','sha256')}
   and pin(result['method.json'])=={k:assets['method'][k]for k in('bytes','sha256')},'exact disclosed fixed control source and method')
 return result
