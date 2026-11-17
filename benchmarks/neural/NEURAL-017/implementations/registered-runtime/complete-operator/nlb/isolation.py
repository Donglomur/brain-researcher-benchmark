"""Future qualified Linux bubblewrap/cgroup-v2 execution, never a local fallback."""
import os,stat,time
from pathlib import Path
from .contracts import closed,need,root_path,relative,digest,Refusal,Store,Custody,Handles

class LinuxCgroupSandbox:
 def __init__(self,authority,job,role,selected,source_store):
  self.authority=authority;self.job=job;self.role=role;self.selected=selected;self.store=source_store;self.cg=None;self.baseline=None;self.custody=Custody('cgroup:'+job)
 def validate(self,request):
  self.authority.check(request['stage'],self.role);need(os.uname().sysname=='Linux','qualified Linux required')
  s=self.selected;closed(s,{'qualification','bwrap','rootfs','cgroup_parent','cgroup_name','memory_bytes','pids','cpu_quota_us','cpu_period_us','mounts','runtime_environment','rootfs_qualification','storage_qualification','scratch_root','scratch_bytes','runtime_profile'})
  for k in('qualification','rootfs_qualification','storage_qualification'):
   need(s[k]in list(self.authority.input_pins),'selected containment qualification');self.store.read(s[k],8*2**20)
  executable=self.store.path(s['bwrap']['path']);self.store.read(s['bwrap'],16*2**20);need(os.access(executable,os.X_OK),'pinned bwrap executable')
  root=root_path(s['rootfs']);need(root.is_dir(),'rootfs directory');parent=root_path(s['cgroup_parent'])
  from .runtime_policy import rootfs_qualification
  rootfs_qualification(s['runtime_profile'],self.store.json(s['rootfs_qualification']),s['rootfs'])
  if s['runtime_profile']!='model_gateway':need(any(m['role']=='engine_source'for m in s['mounts']),'reviewed engine source must be a separate authenticated mount')
  need(str(parent).startswith('/sys/fs/cgroup/')and parent.is_dir(),'delegated cgroup v2 root');relative(s['cgroup_name']);need('/'not in s['cgroup_name'],'single fresh cgroup')
  need(not(parent/s['cgroup_name']).exists(),'never reuse cgroup');need(s['memory_bytes']<=16*2**30 and s['pids']<=64 and s['cpu_quota_us']/s['cpu_period_us']<=4,'matched resource ceilings')
  quota=self.store.json(s['storage_qualification']);need(quota['schema']=='NLB017_current_kernel_storage_qualification_v1'and quota['scratch_root']==s['scratch_root']and quota['hard_total_bytes']<=2*2**30 and quota['kernel_enforced']is True and quota['original_probe_terminal']in list(self.authority.input_pins),'current finite kernel scratch quota')
  self.store.read(quota['original_probe_terminal'],8*2**20);need(s['scratch_bytes']<=quota['hard_total_bytes'],'scratch inside qualified quota');root_path(s['scratch_root']);self.request=request
  targets=set()
  for mount in s['mounts']:
   keys={'host','guest','access','role','manifest'};need(set(mount)in(keys,keys|{'member'}),'closed mount schema');host=root_path(mount['host']);need(host.exists(),'selected mount exists')
   need(mount['guest'].startswith('/inputs/')or mount['guest']in('/programme','/state_ro','/output'),'closed guest mount role')
   need(mount['guest']not in targets,'duplicate mount');targets.add(mount['guest'])
   need(mount['access']in('ro','rw')and(mount['access']=='ro'or mount['guest']=='/output'),'only output writable')
   need(mount['role']not in('assessment_target','private_ledger')or self.role in('protected_score','protected_uncertainty','raw_prepare'),'protected mount capability')
   need(mount['role']!='raw_asset'or self.role=='raw_prepare','raw asset operator only')
   need(mount['manifest']in request['input_manifests'],'mount explicitly bound by job')
   if mount['access']=='ro':self._mount(mount)
  self.cg=parent/s['cgroup_name'];self.cg.mkdir(mode=0o700)
  for name,value in(('memory.max',s['memory_bytes']),('pids.max',s['pids']),('cpu.max',str(s['cpu_quota_us'])+' '+str(s['cpu_period_us']))):self._write(name,str(value))
  self.baseline=self._cpu();need(self._read('cgroup.procs').strip()=='','fresh empty cgroup')
 def _mount(self,mount):
  doc=self.store.json(mount['manifest'],16*2**20)
  if 'member'in mount:
   closed(doc,{'schema','programme','job','files'});need(doc['schema']=='NLB017_input_mount_set_v1'and doc['job']==self.job,'actual current invocation input set');rows=[r for r in doc['files']if r['source']['path']==mount['member']];need(len(rows)==1 and rows[0]['role']==mount['role'],'exact input leaf role');pin=rows[0]['source'];need(mount['host']==str(self.store.path(pin['path']))and mount['guest']=='/inputs/'+pin['path']and mount['access']=='ro','exact host-to-guest input identity')
   if 'runtime_profile'in self.selected:
    from .runtime_policy import source_mount
    source_mount(self.selected['runtime_profile'],mount['role'],[pin['path']])
   self.store.read(pin,1024*2**20);return
  closed(doc,{'schema','role','files'});need(doc['schema']=='NLB017_mount_tree_v1'and doc['role']==mount['role'],'closed physical mount role')
  expected={x['path']:x for x in doc['files']};need(len(expected)==len(doc['files'])and len(expected)<=10000,'finite complete mount inventory');root=root_path(mount['host']);seen=set();dirs={'.'}
  if mount['role']=='engine_source':
   source=self.store.json(self.request['source'],16*2**20);need(source['schema']=='NLB017_runtime_source_manifest_v1','reviewed runtime source manifest');accepted={x['path']:x for x in source['files']};need(all(name in accepted and pin==accepted[name]for name,pin in expected.items()),'every mounted engine body belongs to exact selected reviewed source')
  if 'runtime_profile'in self.selected:
   from .runtime_policy import source_mount
   source_mount(self.selected['runtime_profile'],mount['role'],expected)
  for name in expected:
   relative(name);parts=name.split('/')
   for i in range(1,len(parts)):dirs.add('/'.join(parts[:i]))
  stack=[root]
  while stack:
   d=stack.pop()
   owner=Custody('mount_directory:'+str(d));scan=None;owner.facts['close_state']='not_opened'
   try:
    scan=os.scandir(d);owner.facts['close_state']='owned'
    for e in scan:
     rel=str(Path(e.path).relative_to(root));need(not e.is_symlink(),'physical projection symlink')
     if e.is_dir(follow_symlinks=False):need(rel in dirs,'unlisted input directory');stack.append(Path(e.path))
     else:need(e.is_file(follow_symlinks=False)and rel in expected,'unlisted empirical/source mount member');seen.add(rel)
   except BaseException as error:owner.fail(error,'mount_directory_body')
   finally:
    if scan is not None:
     owner.facts['close_state']='attempted_unknown'
     try:scan.close();owner.facts['close_state']='closed'
     except BaseException as error:owner.fail(error,'mount_directory_close')
    owner.complete=owner.first_error is None;self.custody.fail(None,'original_mount_directory',owner)
   owner.raise_if_failed()
  need(seen==set(expected),'complete input mount census');reader=Store(root,self.store.budget,self.custody)
  for pin in expected.values():reader.read(pin,1024*2**20)
 def _write(self,name,value):
  c=Custody('cgroup_write:'+name);h=Handles(c);event={'member':name,'operation':'write','open_attempted':False,'opened':False,'requested_bytes':None,'returned_bytes':None,'effect':'not_attempted'};c.events.append(event)
  try:
   p=self.cg/name;need(not p.is_symlink(),'cgroup member');raw=value.encode();event['requested_bytes']=len(raw);event['open_attempted']=True
   fd=h.own(os.open(p,os.O_WRONLY|os.O_NOFOLLOW),'cgroup_file',name);event['opened']=True;event['effect']='attempted_unknown'
   n=os.write(fd,raw);event['returned_bytes']=n;event['effect']='returned';need(n==len(raw),'cgroup complete write')
  except BaseException as error:c.fail(error,'cgroup_write')
  finally:
   h.finish();c.complete=c.first_error is None;self.custody.fail(None,'original_cgroup_write',c)
  c.raise_if_failed()
 def _read(self,name):
  c=Custody('cgroup_read:'+name);h=Handles(c);event={'member':name,'operation':'read','open_attempted':False,'opened':False,'requested_bytes':65537,'returned_bytes':None,'effect':'not_attempted'};c.events.append(event);value=None
  try:
   event['open_attempted']=True;fd=h.own(os.open(self.cg/name,os.O_RDONLY|os.O_NOFOLLOW),'cgroup_file',name);event['opened']=True;event['effect']='attempted_unknown'
   b=os.read(fd,65537);event['returned_bytes']=len(b);event['effect']='returned';need(len(b)<=65536,'cgroup metadata cap');value=b.decode('ascii')
  except BaseException as error:c.fail(error,'cgroup_read')
  finally:
   h.finish();c.complete=c.first_error is None;self.custody.fail(None,'original_cgroup_read',c)
  c.raise_if_failed();return value
 def _cpu(self):return int(dict(x.split()for x in self._read('cpu.stat').splitlines())['usage_usec'])/1e6
 def command(self,request):
  s=self.selected;argv=[str(self.store.path(s['bwrap']['path'])),'--die-with-parent','--new-session','--unshare-all','--ro-bind',s['rootfs'],'/','--proc','/proc','--dev','/dev','--bind',s['scratch_root'],'/tmp','--tmpfs','/run','--clearenv']
  for key,value in sorted(s['runtime_environment'].items()):need(key in('PATH','PYTHONPATH','LANG','LC_ALL','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'),'closed environment');argv+=['--setenv',key,str(value)]
  for m in s['mounts']:argv+=['--ro-bind'if m['access']=='ro'else'--bind',m['host'],m['guest']]
  need(type(request['argv'])is list and request['argv']and all(type(x)is str and '\0'not in x for x in request['argv']),'literal argv')
  argv+=['--chdir','/output','--',*request['argv']]
  def attach_before_exec():
   self._write('cgroup.procs',str(os.getpid()))
  return argv,{'PATH':'/usr/bin:/bin'},attach_before_exec
 def check_runtime(self):
  self.authority.check(self.request['stage'],self.role);need(self.cg is not None,'cgroup launched');need(self._cpu()-self.baseline<=self.request['cpu_remaining'],'original cumulative CPU allowance')
 def running_cpu(self):
  need(self.cg is not None and self.baseline is not None,'original cgroup CPU scope')
  used=self._cpu()-self.baseline;need(used>=0,'monotone original cgroup CPU');return used
 def _freeze(self,value,deadline):
  need(self.cg is not None,'original cgroup freeze scope');self._write('cgroup.freeze',str(value))
  # Observe the kernel acknowledgement; a successful write alone is not a pause.
  while time.monotonic()<deadline:
   events=dict(x.split()for x in self._read('cgroup.events').splitlines())
   if events.get('frozen')==str(value):return
   time.sleep(min(.01,max(0,deadline-time.monotonic())))
  raise Refusal('original cgroup freeze acknowledgement deadline')
 def pause(self,deadline):
  self.authority.check(self.request['stage'],self.role);self._freeze(1,deadline)
 def resume(self,deadline):
  # Thaw cleanup remains attempted even after authority/deadline expiry.
  self._freeze(0,deadline)
 def kill(self):
  if self.cg is not None:self._write('cgroup.kill','1')
 def quiesce(self,deadline):
  if self.cg is None:return True
  if int(self._read('pids.current')):self.kill()
  while time.monotonic()<deadline:
   if int(self._read('pids.current'))==0 and self._read('cgroup.procs').strip()=='':return True
   time.sleep(min(.02,max(0,deadline-time.monotonic())))
  return False
 def measure(self):
  if self.cg is None:return {'cpu_seconds':0.0,'memory_peak_bytes':0,'scope':'no_cgroup_no_dispatch'}
  for mount in self.selected['mounts']:
   if mount['access']=='ro':self._mount(mount)
  return {'cpu_seconds':self._cpu()-self.baseline,'memory_peak_bytes':int(self._read('memory.peak')),'scope':'entire_original_cgroup'}
