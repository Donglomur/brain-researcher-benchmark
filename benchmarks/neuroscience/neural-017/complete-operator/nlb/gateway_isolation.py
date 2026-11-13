"""Model-only network/secret capability; all other S13 profiles unchanged."""
import copy,os
from .contracts import need,closed,root_path
from .isolation import LinuxCgroupSandbox
from .openai_protocol import ENDPOINT
from .openai_transport import credential_metadata,credential_stat

BASE_KEYS={'qualification','bwrap','rootfs','cgroup_parent','cgroup_name','memory_bytes','pids','cpu_quota_us','cpu_period_us','mounts','runtime_environment','rootfs_qualification','storage_qualification','scratch_root','scratch_bytes','runtime_profile'}
ALLOWED_ROLES={'engine_source','gateway_config','operator_authority','gateway_qualification','output'}

def selected_transport(value):
 closed(value,{'transport','credential','qualification'});need(value['transport']==ENDPOINT,'fixed gateway endpoint');credential_metadata(value['credential']);return value

class ModelGatewaySandbox(LinuxCgroupSandbox):
 def validate(self,request):
  self.authority.check(request['stage'],self.role)
  need(self.role=='model_exchange'and self.selected.get('runtime_profile')=='model_gateway','exclusive model capability')
  closed(self.selected,BASE_KEYS|{'gateway_transport'});t=selected_transport(self.selected['gateway_transport']);self.transport=t
  need(t['qualification']in list(self.authority.input_pins),'explicit current model network/credential authority')
  q=self.store.json(t['qualification']);closed(q,{'schema','source','transport','credential','live_api_authorized','scope'})
  need(q['live_api_authorized'] is True,'explicit boolean live gateway authorization')
  need(q=={'schema':'NLB017_OpenAI_transport_qualification_v1','source':request['source'],'transport':t['transport'],'credential':t['credential'],'live_api_authorized':True,'scope':'model_exchange_only_no_participant_credentials'},'exact selected live transport qualification')
  need(self.selected['runtime_environment'].get('PYTHONPATH')=='/programme','one authenticated gateway package root')
  for m in self.selected['mounts']:
   need(m['role']in ALLOWED_ROLES,'model cannot mount neural/target/scorer/participant artifacts')
   if m['role']=='output':need(m['guest']=='/output'and m['access']=='rw','exact model output')
   else:need(m['access']=='ro','read-only gateway inputs')
  need(sum(m['role']=='engine_source'and m['guest']=='/programme'for m in self.selected['mounts'])==1 and sum(m['role']=='output'for m in self.selected['mounts'])==1,'complete source/output model mounts')
  credential_stat(os.lstat(root_path(t['credential']['host_path'])),t['credential'])
  full=self.selected
  try:
   self.selected={k:v for k,v in full.items()if k!='gateway_transport'}
   super().validate(request)
  finally:self.selected=full
 def command(self,request):
  need(self.role=='model_exchange'and self.selected['runtime_profile']=='model_gateway','model-only command')
  credential_stat(os.lstat(root_path(self.transport['credential']['host_path'])),self.transport['credential'])
  argv,env,attach=super().command(request);index=argv.index('--unshare-all')+1;argv[index:index]=['--share-net']
  index=argv.index('--chdir');argv[index:index]=['--ro-bind',self.transport['credential']['host_path'],'/run/model-key']
  # Actual gateway reopens and joins this exact inode before its first read,
  # catching a mount-source replacement after this metadata check.
  return argv,env,attach

def model_aware_sandbox(authority,job,role,selected,store):
 if role=='model_exchange':return ModelGatewaySandbox(authority,job,role,selected,store)
 need('gateway_transport'not in selected and selected.get('runtime_profile')!='model_gateway','model capability denied to every other role')
 return LinuxCgroupSandbox(authority,job,role,selected,store)

def model_aware_run(job,request,budget,isolation,**kwargs):
 from .process import run
 if type(isolation)is ModelGatewaySandbox:
  o=kwargs['observation'];isolation.custody=o.custody;isolation.store.custody=o.custody
 return run(job,request,budget,isolation,**kwargs)
