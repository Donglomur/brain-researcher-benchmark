"""Fixed captured complete worker. No direct registry or scientific authority."""
import time
ENTRY_NS=time.monotonic_ns()
BOOT_READ=0
import hashlib,json,os,sys,types,signal
from pathlib import Path
IO_PIN={'bytes': 11967, 'sha256': '60751688732dcbc426e0b1290e17fe90c2af95ce027ce8a541df06c79efa04e7'}
LOADER_PIN={'bytes': 2007, 'sha256': 'a56fa8c33eddddc8d8a91b69a43b1f4632f8e7b407d32befe1ad82d426b03cd3'}
HERE=Path(__file__).absolute().parent
REL='authoring/delivery-20261105/common/remaining-builds-wave27/neural004-complete-design/implementation-v1/central-integration/successor-v3'
def boot(path,expected):
 global BOOT_READ
 import stat
 BOOT_READ+=expected['bytes']+1
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);primary=None
 try:
  a=os.fstat(fd)
  if not(stat.S_ISREG(a.st_mode)and a.st_nlink==1 and a.st_size==expected['bytes']):raise ValueError('Exact worker bootstrap file')
  with os.fdopen(fd,'rb',closefd=False)as stream:raw=stream.read(expected['bytes']+1)
  b=os.fstat(fd);named=path.lstat();keys=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
  if not(len(raw)==expected['bytes']and hashlib.sha256(raw).hexdigest()==expected['sha256']and all(getattr(a,k)==getattr(b,k)==getattr(named,k)for k in keys)):raise ValueError('Stable worker bootstrap source')
  return raw
 except BaseException as error:primary=error;raise
 finally:
  try:os.close(fd)
  except BaseException as extra:
   if primary is None:raise
   primary.add_note('Worker bootstrap close uncertainty: '+type(extra).__name__)
def module(name,path,raw):
 if name in sys.modules:raise ValueError('Fresh worker namespace')
 m=types.ModuleType(name);m.__file__=str(path);sys.modules[name]=m;exec(compile(raw,str(path),'exec'),m.__dict__);return m

def admitted_imports(modules,environment,captured,bootstrap):
 """Exact captured loader/file custody; no subtree-wide import exemption."""
 imports={};roots=tuple(x.root for x in captured)
 for name,m in tuple(modules.items()):
  filename=getattr(m,'__file__',None)
  if filename is None:continue
  path=Path(filename).absolute();owned=False
  for source in captured:
   if name in source.owned:
    declared=source.path(name)
    if declared is None or getattr(m,'__loader__',None) is not source or path!=source.root/declared:
     raise ValueError('Exact declared captured module and loader identity')
    owned=True;break
  if owned:continue
  if name in bootstrap:
   if m is not bootstrap[name] or path!=HERE/('central_io.py'if name=='central_io'else'source_loader.py'):
    raise ValueError('Exact pinned bootstrap module identity')
   continue
  if any(path.is_relative_to(root)for root in roots):
   raise ValueError('Undeclared filesystem module beneath captured root: '+name)
  key=str(path)
  if key not in environment['import_inventory']:raise ValueError('Imported module outside admitted inventory: '+name)
  imports[key]=environment['import_inventory'][key]
 return imports

def main():
 ci=module('central_io',HERE/'central_io.py',boot(HERE/'central_io.py',IO_PIN));load=module('_n004_loader',HERE/'source_loader.py',boot(HERE/'source_loader.py',LOADER_PIN))
 need=ci.need;need(len(sys.argv)==2 and len(sys.argv[1].encode())<=65536,'Exact bounded worker argument');b=ci.parse(sys.argv[1]);need(set(b)=={'schema','repository','central_root','source_manifest_pin','source_freeze_pin','parent_manifest_pin','profile','operation','config','output','origin','deadline','cutoff','original_clock'},'Exact captured worker binding')
 need(b['schema']=='neural004_central_worker_binding_v1'and b['central_root']==REL and HERE==Path(b['repository'])/REL,'Actual fixed worker source address')
 p=b['profile'];io=ci.IO(p['worker_read_bytes'],p['worker_write_bytes'],p['worker_retained_bytes'],b['origin'],b['cutoff']);io.reads=BOOT_READ+len(sys.argv[1].encode())+1;need(io.reads<=io.read_cap,'Original bootstrap and argument charges');out=ci.ordinary(b['output']);repo=ci.ordinary(b['repository']);primary=None;central=None;parent=None;old_paths=list(sys.path);old_handlers={s:signal.getsignal(s)for s in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT)}
 def timeout(*_):raise TimeoutError('Original worker cutoff')
 try:
  need(signal.getitimer(signal.ITIMER_REAL)==(0.,0.),'Fresh inactive worker timer')
  for sig in old_handlers:signal.signal(sig,timeout)
  signal.setitimer(signal.ITIMER_REAL,max(.000001,b['cutoff']-time.monotonic()))
  smraw=io.capture(HERE/'SOURCE_MANIFEST.json',b['source_manifest_pin'],262144);sm=ci.parse(smraw);own={n:io.capture(HERE/n,d,1048576)for n,d in sm['files'].items()}
  central=load.Captured('_n004_central_worker',HERE,own).install();check=central.module('receipt_check')
  bindings=ci.parse(own['BINDINGS.json']);need(bindings['central_root']==REL and set(own)==set(bindings['own_members']),'Full fixed central worker source')
  pm=bindings['parent_manifest'];pmraw=io.capture(repo/pm['path'],b['parent_manifest_pin'],262144);manifest=ci.parse(pmraw)
  need(manifest['files']==bindings['parent_members']and len(manifest['files'])==46,'Full fixed46 parent')
  pb={r['path']:io.capture(repo/bindings['parent_root']/r['path'],{k:r[k]for k in ('bytes','sha256')},1048576)for r in manifest['files']}
  opraw=io.capture(b['operation']['path'],{k:b['operation'][k]for k in ('bytes','sha256')},16*1048576);configraw=io.capture(b['config']['path'],{k:b['config'][k]for k in ('bytes','sha256')},16*1048576);op=ci.parse(opraw);config=ci.parse(configraw)
  need(config['clock']==b['original_clock']and config['source_root']==str(repo/bindings['parent_root'])and config['runtime_sources']==bindings['parent_members'],'Exact unchanged parent source/original clocks')
  need(op['config_pin']==ci.pin(configraw),'Exact immutable original operation/config pair')
  need(Path(sys.executable).resolve()==Path(p['worker_python']['path']).resolve(),'Actual admitted worker executable')
  check.hash_file(io,p['worker_python']['path'],{k:p['worker_python'][k]for k in ('bytes','sha256')},p['worker_python']['bytes'])
  envraw=io.capture(p['worker_environment']['path'],{k:p['worker_environment'][k]for k in ('bytes','sha256')},4*1048576);environment=ci.parse(envraw)
  need(environment['selected']is True and environment['python']==p['worker_python'],'Qualified concrete import environment')
  for path,d in environment['import_inventory'].items():check.hash_file(io,path,d,p['artifact_max_bytes'])
  for path in environment['import_roots']:
   need(str(ci.ordinary(path))==path,'Exact selected ordinary import root')
   if path not in sys.path:sys.path.append(path)
  parent=load.Captured('_n004_parent',repo/bindings['parent_root'],pb).install()
  io.directories(out/'parent-bodies')
  prediction_names=[m+'/'+v for m in ('P','I')for v in ('B','E','H','EH')]
  max_jobs=sum(26*config['policies'][name]['limits']['tools']for name in prediction_names)+sum(26*config['policies']['reconstruction/'+m]['limits']['tools']for m in ('P','I'))
  bound={'operation':op,'config':config,'output':out,'repository':repo,'operation_pin':ci.pin(opraw),'parent_manifest_pin':b['parent_manifest_pin'],'profile':p,
   'environment_pin':ci.pin(envraw),'max_jobs':max_jobs}
  result=central.module('driver').run(io,bound,parent)
  # Every imported filesystem module is either captured task code or in the
  # independently selected exact environment inventory. Native dependencies
  # and original preprocessing remain qualification obligations.
  imports=admitted_imports(sys.modules,environment,(central,parent),{'central_io':ci,'_n004_loader':load})
  for path,d in imports.items():check.hash_file(io,path,d,p['artifact_max_bytes'])
  for name,raw in own.items():need(io.capture(HERE/name,ci.pin(raw),1048576)==raw,'Unchanged full central source')
  for name,raw in pb.items():need(io.capture(repo/bindings['parent_root']/name,ci.pin(raw),1048576)==raw,'Unchanged full parent source')
  for path,raw in ((b['operation']['path'],opraw),(b['config']['path'],configraw),(p['worker_environment']['path'],envraw)):need(io.capture(path,ci.pin(raw),max(len(raw),1))==raw,'Unchanged original worker operands')
  result['worker_import_inventory']=imports;result['worker_costs_before_final_publication']=io.snapshot();raw=ci.encoded(result);need(len(raw)<=p['worker_return_bytes'],'Complete original worker return extent')
  io.save(out/'WORKER_RETURN.json',raw);io.tick()
 except BaseException as error:
  primary=error
  record=ci.failure_record(error,'complete_neural004_worker',io.snapshot(),{'original_binding':b,'no_retry':True})
  try:
   raw=ci.encoded(record);need(len(raw)<=p['worker_return_bytes'],'Complete worker failure receipt');io.save(out/'WORKER_FAILURE.json',raw)
  except BaseException as secondary:ci.cleanup_note(error,'worker failure publication',secondary)
  raise
 finally:
  actions=[('worker timer cancel',lambda:signal.setitimer(signal.ITIMER_REAL,0))]
  actions.extend(('worker signal restore',lambda s=s,h=h:signal.signal(s,h))for s,h in old_handlers.items())
  if parent is not None:actions.append(('captured parent close',parent.close))
  if central is not None:actions.append(('captured central close',central.close))
  actions.append(('import path restore',lambda:sys.path.__setitem__(slice(None),old_paths)))
  first=primary
  for name,action in actions:
   try:action()
   except BaseException as extra:
    if first is None:first=extra
    else:ci.cleanup_note(first,name,extra)
  if primary is None and first is not None:
   try:io.save(out/'WORKER_FAILURE.json',ci.encoded(ci.failure_record(first,'worker_cleanup',io.snapshot())))
   except BaseException as extra:ci.cleanup_note(first,'cleanup failure publication',extra)
   raise first
 io.tick();need(time.monotonic()<b['cutoff'],'Natural worker final return within original cutoff');return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except BaseException as error:
  if not isinstance(error,SystemExit) or error.code not in (None,0):error.add_note('Original worker bootstrap requested-source bytes='+str(BOOT_READ)+'; failed attempts are not erased')
  raise
