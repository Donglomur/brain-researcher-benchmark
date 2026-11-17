"""Small source/profile gates only; no native, inputs, arrays or model fixtures."""
import ast,hashlib,json,types
from pathlib import Path
HERE=Path(__file__).absolute().parent

def need(v,m):
 if not v:raise ValueError(m)
def refused(f):
 try:f()
 except (ValueError,TypeError):return
 raise AssertionError('expected refusal')
def chosen(name,names):
 tree=ast.parse((HERE/'program'/name).read_bytes());ns={}
 selected=[]
 for n in tree.body:
  if isinstance(n,ast.Assign) and any((isinstance(t,ast.Name) and t.id in names) or (isinstance(t,ast.Subscript) and isinstance(t.value,ast.Name) and t.value.id in names) for t in n.targets):selected.append(n)
 exec(compile(ast.Module(body=selected,type_ignores=[]),name,'exec'),ns);return ns

def main():
 ns={'c':types.SimpleNamespace(need=need),'__name__':'source_control'}
 exec(compile((HERE/'program/policy.py').read_bytes(),'policy.py','exec'),ns)
 plan=dict(contexts=54,query_count=21600,phase_arrays=216,canonical_payload_bytes=345600000,canonical_total_bytes=350000000)
 limits=ns['limits'](plan,900,120,120);d=json.loads((HERE/'RESOURCE_DERIVATION.json').read_bytes())
 assert limits['reads']==d['worker_read_cap_bytes']==323719316992
 assert limits['writes']==d['worker_write_cap_bytes']==47955429248
 assert limits['retained']==d['retained_phase_cap_bytes']==1610612736
 assert limits['whole_seconds']==54*(900+120+3*120+5*130+240)+2400
 for k in ('contexts','query_count','phase_arrays','canonical_payload_bytes'):refused(lambda k=k:ns['limits']({**plan,k:plan[k]-1},900,120,120))
 refused(lambda:ns['limits'](plan,True,120,120))
 native=chosen('native.py',{'PROFILE'})['PROFILE'];holder=chosen('holder.py',{'KINDS'})['KINDS']
 assert set(native)==set(holder)=={'fit','infer','cca','constant','frequency-permuted'}
 for k,p in native.items():
  assert holder[k]==(p['cap'],p['volume'],p['memory'],p['name'])
  assert p['volume']>p['cap'] and p['reply']>4*((p['cap']+2)//3)+256 and p['responses']>p['reply']
 assert native['fit']['cap']==ns['MODEL_CAP']==536870912>339200128+5000000
 assert native['fit']['memory']==4294967296
 # Disabled templates refuse at the first authority guard, before any path or input access.
 selection=json.loads((HERE/'SELECTION.template.json').read_bytes());refused(lambda:ns['selection'](selection,selection['source']))
 for name,key in [('REVIEW','approved'),('RUNTIME','qualified'),('INPUT_REVIEW','approved'),('METHOD_REVIEW','approved'),('CONTROLLER_RUNTIME','approved')]:assert json.loads((HERE/(name+'.template.json')).read_bytes())[key]is False
 proposed=json.loads((HERE/'proposed/benchmarks/neuroscience/neural-084/manifest.json').read_bytes())
 assert proposed['id']=='NEURAL-084' and proposed['registration_notes']['preferred_install_authorized']is False and proposed['program_execution']['execution_selected']is False
 root=HERE.parents[5];f=json.loads((HERE/'QUALIFICATION_SOURCE_FREEZE.json').read_bytes())
 for name,p in f['files'].items():
  b=(root/name).read_bytes();assert {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}==p
 abi=(HERE/'program/controller.py').read_text();admit=(HERE/'program/admission.py').read_text()
 assert 'canonical_store_or_private_gold_candidate_mounted' in abi and 'canonical_store_or_private_gold_candidate_mounted' in admit
 assert 'canonical_or_labels_candidate_mounted' not in abi+admit
 # Exact unchanged scientific/reference and trusted metadata-validation reuse.
 assert (HERE/'program/reference_program.py').read_bytes()==(HERE.parent/'program/reference_program.py').read_bytes()
 assert (HERE/'program/contracts.py').read_bytes()==(HERE.parent/'program/packet.py').read_bytes()
 print('PASS 4 groups: cumulative/fullscope bounds; native/holder profiles; disabled authority; frozen source and unchanged scientific contracts. No canonical fixture serialization or physical fixture writes.')
if __name__=='__main__':main()
