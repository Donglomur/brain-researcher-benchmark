"""Exact source-only closure and narrow AST delta checks. No imports of subjects."""
import ast
import hashlib
import json
from pathlib import Path
import stat

C=Path('authoring/delivery-20261105/common/remaining-builds-wave21/paper020-full-design/implementation-v1/runtime-adapters-v1/central-integration')
S=C/'successor-v2';P=C/'peer-review';cache={};reads=0
def pin(path):
 global reads
 path=Path(path);name=path.as_posix()
 if name not in cache:
  st=path.lstat();assert stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size<=200000
  b=path.read_bytes();reads+=len(b);assert len(b)==st.st_size;cache[name]=b
 b=cache[name];return {'path':name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def verify(row):
 actual=pin(row['path']);assert all(actual[k]==row[k]for k in ('bytes','sha256'));return actual
def document(path):pin(path);return json.loads(cache[str(path)])
old=verify({'path':str(C/'SOURCE_PROPOSAL.json'),'bytes':11045,'sha256':'651a2a03f7d00eaf28b9aae71926149e242f64a027e66792a6bdc87a9036b66a'})
new=verify({'path':str(S/'SOURCE_PROPOSAL.json'),'bytes':8275,'sha256':'f5a85d49b22bc5a06ecb17daeb34970eef15a7640cde52405ab577ad9c9c02ca'})
oldrows=document(C/'SOURCE_PROPOSAL.json')['files'];newrows=document(S/'SOURCE_PROPOSAL.json')['files']
assert len(oldrows)==36 and len(newrows)==26
for row in oldrows+newrows:verify(row)
initial=verify({'path':str(P/'INITIAL_SOURCE_PROPOSAL.json'),'bytes':2870,'sha256':'9b28a6345e94cba99f8788106dbf8cedcf2393f34400163aa7e786e93dd0c8b7'})
for row in document(P/'INITIAL_SOURCE_PROPOSAL.json')['files']:verify(row)
manifest=document(S/'SOURCE_MANIFEST.json')
for name,row in manifest['files'].items():verify({'path':str(S/name),**row})
binding=document(S/'source-capture/BINDING.json');assert binding['total_members']==34
for row in binding['files']:verify({'path':row['source_path'],'bytes':row['bytes'],'sha256':row['sha256']})
assert sum(r['bytes']for r in binding['files'])==462268
shared=document(S/'SHARED_SOURCE_BINDINGS.json')
for row in shared['external']+shared['campaign_contract_files']:verify(row)
context=document(S/'ROOT_CONTEXT.json');verify(context['root_receipt'])
unchanged=[];deltas=[];newmembers=[];function_deltas={}
for name in manifest['files']:
 oldpath=C/name;newpath=S/name
 if not oldpath.exists():newmembers.append(name);continue
 pin(oldpath);a=cache[str(oldpath)];b=cache[str(newpath)]
 if a==b:unchanged.append(name);continue
 deltas.append(name)
 if name.endswith('.py'):
  def functions(body):return {n.name:ast.dump(n,include_attributes=False)for n in ast.parse(body).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
  left,right=functions(a),functions(b)
  function_deltas[name]={'changed':sorted(k for k in left.keys()&right.keys()if left[k]!=right[k]),'added':sorted(right.keys()-left.keys()),'removed':sorted(left.keys()-right.keys())}
assert set(deltas)=={'DEPLOYMENT_CONTRACT.md','bootstrap.py','credential.py','dispatch.py','entry.py','external.py','observer_entry.py','transcript.py'}
assert set(newmembers)=={'CORRECTIONS.json','evidence.py','failure.py'}
assert set(unchanged)=={'ROOT_CONTEXT.json','SHARED_SOURCE_BINDINGS.json','artifacts.py','authority.py','common_io.py','registration.py','source-capture/BINDING.json','source-capture/capture.py'}
assert function_deltas['dispatch.py']=={'changed':['run'],'added':[],'removed':[]}
assert function_deltas['external.py']=={'changed':['observe'],'added':[],'removed':[]}
assert function_deltas['transcript.py']=={'changed':['BoundTrace','Journal','read_records'],'added':[],'removed':[]}
assert cache[str(C/'source-capture/BINDING.json')]==cache[str(S/'source-capture/BINDING.json')]
boot=ast.parse(cache[str(S/'bootstrap.py')]);names=next(ast.literal_eval(n.value)for n in boot.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='NAMES'for t in n.targets))
assert names==set(manifest['files']) and len(names)==19
source=cache[str(S/'bootstrap.py')].decode()
assert 'rows[helper.BINDING_PATH]=u.pin('in source and 'repo=here.parents[8]'in source
parsed={'json':0,'python':0}
for name,body in cache.items():
 if name.endswith('.json'):json.loads(body);parsed['json']+=1
 elif name.endswith('.py'):ast.parse(body);parsed['python']+=1
assert not Path('authoring/delivery-20261105/paper020_peer_placeholder.tmp').exists()
report={'schema':'paper020_central_peer_final_source_joins_v1','status':'PASS_SOURCE_PINS_AND_NARROW_DELTAS',
 'original_proposal':old,'successor_proposal':new,'initial_peer_proposal':initial,'original_payloads':36,
 'successor_payloads':26,'central_manifest_members':19,'captured_parent_members':34,'captured_parent_bytes':462268,
 'unchanged_central_members':sorted(unchanged),'changed_central_members':sorted(deltas),'added_central_members':sorted(newmembers),
 'function_deltas':function_deltas,'source_only_parses':parsed,'logical_unique_body_reads':reads,
 'pins':[pin(n)for n in sorted(cache)],'source_execution':False,'authentic_or_private_graph_or_key_reads':False,
 'placeholder_removed':True,'all_initial_peer_files_unchanged':True,'all_original_author_files_unchanged':True}
raw=(json.dumps(report,indent=2,sort_keys=True)+'\n').encode();(P/'FINAL_SOURCE_PINS.json').write_bytes(raw)
print(json.dumps({'status':report['status'],'members':len(cache),'reads':reads,'report_bytes':len(raw),'report_sha256':hashlib.sha256(raw).hexdigest(),'function_deltas':function_deltas}))
