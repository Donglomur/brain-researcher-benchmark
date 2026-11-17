# Source-only literal; root binds exactly the five None values after positive selection.
__PYTHON_EXECUTABLE__ -I -S -B - <<'PY'
from pathlib import Path
import hashlib,json,os,resource,stat,time
SELECTED_REQUEST_BYTES = None
SELECTED_REQUEST_SHA = None
SELECTED_DECISION_BYTES = None
SELECTED_DECISION_SHA = None
SELECTED_AT_UNIX_NS = None
assert type(SELECTED_REQUEST_BYTES) is int and type(SELECTED_DECISION_BYTES) is int and type(SELECTED_AT_UNIX_NS) is int, 'inert: root has not bound a selected request'
assert isinstance(SELECTED_REQUEST_SHA,str) and isinstance(SELECTED_DECISION_SHA,str)
S=Path(__SELECTION_DIR_LITERAL__)
D=Path(__RUNTIME_DIR_LITERAL__)
def read_pin(path,size,digest):
 p=Path(path);s=p.lstat();assert stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size==size
 b=p.read_bytes();assert len(b)==size and hashlib.sha256(b).hexdigest()==digest;return b
request_path=S/'REQUEST.json';request_body=read_pin(request_path,SELECTED_REQUEST_BYTES,SELECTED_REQUEST_SHA);req=json.loads(request_body)
read_pin(S/'ROOT_DECISION.json',SELECTED_DECISION_BYTES,SELECTED_DECISION_SHA)
template_body=read_pin(D/'REQUEST_TEMPLATE.json',__TEMPLATE_BYTES__,__TEMPLATE_SHA_LITERAL__);template=json.loads(template_body)
dynamic={'selected','selected_at_unix_ns','outside_host_bytes','outside_disk_bytes','other_selected_cpu_slots','root_decision'}
assert set(req)==set(template) and all(req[k]==template[k] for k in template if k not in dynamic)
assert req['selected'] is True and req['selected_at_unix_ns']==SELECTED_AT_UNIX_NS
assert 0<=time.time_ns()-req['selected_at_unix_ns']<=120000000000
assert req['root_decision']=={'path':str(S/'ROOT_DECISION.json'),'bytes':SELECTED_DECISION_BYTES,'sha256':SELECTED_DECISION_SHA}
assert req['sources'][0]=={'path':str(D/'owner.py'),'bytes':10908,'sha256':'530e40348139c0940538d61a4a4a9abafe1942dd5f0f0e65c3cc1ebec14fba5d'}
for row in req['sources']+[req['base_owner'],req['process_owner'],req['process_closer']]:read_pin(row['path'],row['bytes'],row['sha256'])
soft,hard=resource.getrlimit(resource.RLIMIT_CPU);assert hard==resource.RLIM_INFINITY or hard>=450
for name in ('owner_output','output'):
 p=Path(req[name]);assert not p.exists() and not p.is_symlink()
if os.getpid()!=os.getpgrp():os.setsid()
assert os.getpid()==os.getpgrp()
argv=[req['python'],'-I','-S','-B',str(D/'owner.py'),'--request',str(request_path)]
record={'schema':'fly-native-joins-dispatch-v1','pid':os.getpid(),'pgid':os.getpgrp(),'request_sha256':hashlib.sha256(request_body).hexdigest(),'owner_source':req['sources'][0],'argv':argv,'selected_at_unix_ns':req['selected_at_unix_ns'],'dispatch_unix_ns':time.time_ns(),'inherited_cpu_limits':[soft,hard],'same_pid_preexec':True}
body=(json.dumps(record,sort_keys=True,indent=2)+'\n').encode();fd=os.open(S/'DISPATCH.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'wb') as handle:handle.write(body);handle.flush();os.fsync(handle.fileno())
print(json.dumps({'dispatch_record':str(S/'DISPATCH.json'),'pid':os.getpid(),'pgid':os.getpgrp(),'once_only':True}),flush=True)
os.execv(req['python'],argv)
PY
