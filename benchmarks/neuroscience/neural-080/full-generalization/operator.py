"""Inactive central inspection and fresh-process routing to the genuine N080 CLI.

No scientific module is imported here. exec_phase is a future process-replacement
API, not a native-authority issuer. The original CLI constructs its own actual
input_owner.Owner and captures its own exact config in a fresh interpreter.
Generic run/score stay null; all scientific and native gates remain open.
"""
import argparse,hashlib,json,os,stat,sys
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parent
ONE=1048576
PHASES=('prepare','stage','execute','compare')
class InactiveSource(RuntimeError):pass
def require(ok,message):
 if not ok:raise ValueError(message)
def pin(body):return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
def parse(body):
 def unique(items):
  out={}
  for key,value in items:require(key not in out,'duplicate source metadata key');out[key]=value
  return out
 return json.loads(body,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in()).throw(ValueError('nonfinite metadata')))
def relative(name):
 require(type(name)is str and name and '\\'not in name,'literal source relative path')
 p=PurePosixPath(name);require(not p.is_absolute()and all(x not in('','.','..')for x in name.split('/')),'source relative domain')
 return Path(*p.parts)
def capture_source(path,budget,expected=None):
 require(not any(p.is_symlink()for p in(path,*path.parents)),'source aliases refused')
 fd=None;first=None
 try:
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
  s=os.fstat(fd);require(stat.S_ISREG(s.st_mode)and s.st_nlink==1 and s.st_size<=ONE,'ordinary bounded source')
  require(budget['read']+s.st_size<=budget['limit'],'explicit central source-read allowance')
  body=bytearray()
  while len(body)<=s.st_size:
   value=os.read(fd,min(65536,s.st_size+1-len(body)))
   budget['read']+=len(value)
   require(budget['read']<=budget['limit'],'actual source-read allowance')
   if not value:break
   body.extend(value)
  fields=lambda t:(t.st_dev,t.st_ino,t.st_mode,t.st_nlink,t.st_size,t.st_mtime_ns,t.st_ctime_ns)
  require(fields(s)==fields(os.fstat(fd))==fields(path.lstat())and len(body)==s.st_size,'source identity stable')
  body=bytes(body);body.decode('utf-8');require(b'\0'not in body,'ordinary UTF8 source')
  if expected is not None:require(pin(body)=={k:expected[k]for k in('bytes','sha256')},'exact selected source identity')
  return body
 except BaseException as error:first=error;raise
 finally:
  if fd is not None:
   try:os.close(fd)
   except BaseException as error:
    if first is None:raise
    first.source_cleanup_failures=getattr(first,'source_cleanup_failures',())+(error,)
def _inspect(budget):
 resolution=parse(capture_source(ROOT/'INSTALLED_SOURCE_RESOLUTION.json',budget))
 require(resolution['schema']=='n080-full-central-source-resolution-v1'and resolution['source_roles']==58,'complete N080 source map')
 rows=resolution['files'];require(len(rows)==58 and len({r['installed_relative']for r in rows})==58,'unique complete58 source roles')
 total=0
 for row in rows:
  require(row['installed_relative']==row['original_relative'],'unchanged original source-relative structure')
  total+=len(capture_source(ROOT/relative(row['installed_relative']),budget,row))
 require(total==603562,'complete exact58-role source extent')
 source=parse(capture_source(ROOT/'SOURCE_MANIFEST.json',budget,resolution['source_manifest']))
 require(source['source_file_count']==58 and source['source_bytes']==603562,'accepted full source manifest')
 require({(r['path'],r['bytes'],r['sha256'])for r in source['source_files']}=={(r['original_relative'],r['bytes'],r['sha256'])for r in rows},'exact source-to-installed inverse')
 capture_source(ROOT/'SOURCE_API.json',budget,resolution['source_api'])
 gates=parse(capture_source(ROOT/'QUALIFICATION_GATES.json',budget,resolution['qualification_gates']))
 require(len(gates['gates'])==9 and not any(x['satisfied']for x in gates['gates']),'all original empirical obligations remain open')
 manifest=parse(capture_source(ROOT/'SOURCE_INTEGRATION.json',budget))
 require(manifest['id']=='NEURAL-080'and all(manifest[x]is None for x in('run','score','program_execution')),'inactive generic central routes')
 require(all(manifest['admission'][x]is False for x in('source_complete','runnable','research_qualified','submission_ready','full_contract_complete')),'no readiness promotion')
 require(manifest['scope']==resolution['scope'],'whole six-person programme retained')
 require(resolution['scope']['people']==6 and resolution['scope']['videos']==1102 and resolution['scope']['outer_cases']==30,'complete original support')
 require(manifest['source_construction']['operator_api']=='operator.exec_phase'and manifest['source_construction']['actual_source_operator']=='neural080.py:main','real original CLI route')
 return {'schema':'n080-central-source-inspection-v1','id':'NEURAL-080','source_roles':58,'source_bytes':603562,'scope':resolution['scope'],'open_gates':9,'run':None,'score':None,'runnable':False,'research_qualified':False,'actual_source_operator':'neural080.py:main','actual_logical_owner':'source/private/input_owner.py:Owner','native_authority_issuer':None,'phase_isolation':'one fresh interpreter exec for one original phase','bootstrap_logical_read_bytes':budget['read'],'scientific_execution':False}
def inspect_definition(*,source_read_bytes=2*ONE):
 require(type(source_read_bytes)is int and source_read_bytes>0,'explicit positive ordinary source allowance')
 return _inspect({'limit':source_read_bytes,'read':0})
def _absolute(value):
 require(type(value)is str and Path(value).is_absolute()and '\0'not in value,'explicit absolute operator path')
 return value
def exec_phase(*,phase,interpreter,interpreter_pin,environment,config,config_pin,output,logical_limits,bootstrap_read_bytes,roots=None):
 """Replace this process with one explicitly selected original scientific phase.

 Provisioned interpreter/environment and an immutable exact programme tree are
 future trusted-host inputs. Their selection does not qualify host hooks,
 numerical packages, native isolation, aggregate resources, rights or data.
 No config/signal/target body is opened by this dispatcher. Bootstrap source and
 interpreter reads are separate from the original phase Owner's counters.
 """
 require(phase in PHASES,'only four original outer phases; worker-reference is internal')
 require(sys.platform=='linux'and os.execve in os.supports_fd,'future Linux descriptor-exec provision required')
 require(type(bootstrap_read_bytes)is int and bootstrap_read_bytes>0,'explicit bootstrap source/interpreter allowance')
 require(type(interpreter_pin)is dict and set(interpreter_pin)=={'bytes','sha256'},'exact interpreter byte identity')
 require(type(interpreter_pin['bytes'])is int and 0<interpreter_pin['bytes']<=64*ONE,'explicit bounded interpreter extent')
 require(type(interpreter_pin['sha256'])is str and len(interpreter_pin['sha256'])==64 and all(x in '0123456789abcdef'for x in interpreter_pin['sha256']),'interpreter SHA256')
 require(type(config_pin)is dict and set(config_pin)=={'bytes','sha256'}and type(config_pin['bytes'])is int and 0<config_pin['bytes']<=16*ONE,'exact original config descriptor')
 require(type(config_pin['sha256'])is str and len(config_pin['sha256'])==64 and all(x in '0123456789abcdef'for x in config_pin['sha256']),'config SHA256')
 require(type(environment)is dict and all(type(k)is str and type(v)is str and k and '='not in k and '\0'not in k+v for k,v in environment.items()),'explicit complete environment, never inherited implicitly')
 require(type(logical_limits)is dict and set(logical_limits)=={'read_bytes','write_bytes','retained_bytes','attempts'}and all(type(v)is int and v>0 for v in logical_limits.values()),'original Owner explicit positive logical limits')
 require((phase=='prepare')==(roots is not None),'roots belong only to original prepare')
 if roots is not None:
  require(type(roots)is dict and set(roots)=={'metadata','recordings','media','logs','checkpoint'},'all five original preparation roots')
  for value in roots.values():_absolute(value)
 interpreter=Path(_absolute(interpreter));_absolute(config);_absolute(output)
 require(not any(p.is_symlink()for p in(interpreter,*interpreter.parents)),'explicit interpreter without aliases')
 budget={'limit':bootstrap_read_bytes,'read':0};definition=_inspect(budget)
 require(budget['read']+interpreter_pin['bytes']<=budget['limit'],'source plus interpreter fits explicit allowance')
 argv=[str(interpreter),'-I','-B',str(ROOT/'neural080.py'),phase,'--config',config,'--bytes',str(config_pin['bytes']),'--sha256',config_pin['sha256'],'--output',output,'--logical-limits',json.dumps(logical_limits,sort_keys=True,separators=(',',':'),allow_nan=False)]
 if roots is not None:argv+=['--roots',json.dumps(roots,sort_keys=True,separators=(',',':'),allow_nan=False)]
 fd=None;first=None
 try:
  fd=os.open(interpreter,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
  s=os.fstat(fd);require(stat.S_ISREG(s.st_mode)and s.st_nlink==1 and s.st_size==interpreter_pin['bytes']and bool(s.st_mode&0o111),'selected regular executable image')
  digest=hashlib.sha256();size=0
  while size<=s.st_size:
   body=os.read(fd,min(65536,s.st_size+1-size));size+=len(body);budget['read']+=len(body)
   require(budget['read']<=budget['limit'],'actual interpreter read allowance')
   if not body:break
   digest.update(body)
  fields=lambda t:(t.st_dev,t.st_ino,t.st_mode,t.st_nlink,t.st_size,t.st_mtime_ns,t.st_ctime_ns)
  require(fields(s)==fields(os.fstat(fd))==fields(interpreter.lstat())and size==s.st_size and digest.hexdigest()==interpreter_pin['sha256'],'exact stable selected interpreter')
  notice={'schema':'n080-central-bootstrap-observation-v1','phase':phase,'logical_read_bytes':budget['read'],'logical_read_limit':budget['limit'],'scope':'Source/interpreter bootstrap only; separate from original phase Owner and not whole-job/native qualification. Caller must account this overhead.','scientific_qualification':False}
  raw=(json.dumps(notice,sort_keys=True)+'\n').encode();require(len(raw)<=4096,'bounded bootstrap observation')
  at=0
  while at<len(raw):
   n=os.write(2,raw[at:]);require(n>0,'bootstrap observation write returned no progress');at+=n
  os.execve(fd,argv,dict(environment))
  raise RuntimeError('descriptor exec unexpectedly returned')
 except BaseException as error:first=error;raise
 finally:
  if fd is not None:
   try:os.close(fd)
   except BaseException as error:
    if first is None:raise
    first.dispatch_cleanup_failures=getattr(first,'dispatch_cleanup_failures',())+(error,)
def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--inspect',action='store_true',required=True);a=parser.parse_args(argv)
 value=inspect_definition();print(json.dumps(value,sort_keys=True));return value
if __name__=='__main__':main()
