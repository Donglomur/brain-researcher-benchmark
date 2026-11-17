"""Focused independent RAM engineering checks; no real source execution graph."""
import ast
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import tracemalloc
import types

C=Path('authoring/delivery-20261105/common/remaining-builds-wave21/paper020-full-design/implementation-v1/runtime-adapters-v1/central-integration')
S=C/'successor-v2'
source_reads=0;canonical_bytes=0;largest_encoding=0
proposal=json.loads((S/'SOURCE_PROPOSAL.json').read_bytes());source_reads+=8275
pins={Path(r['path']).relative_to(S).as_posix():r for r in proposal['files']}
def load(name):
 global source_reads
 p=S/(name+'.py');b=p.read_bytes();source_reads+=len(b);r=pins[name+'.py']
 assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256']
 m=types.ModuleType('_peer_it_central_'+name);m.__file__=str(p)
 if name!='common_io':m.u=u
 sys.modules[m.__name__]=m;exec(compile(b,str(p),'exec'),m.__dict__);return m
u=load('common_io');original_canonical=u.canonical
def canonical(value):
 global canonical_bytes,largest_encoding
 b=original_canonical(value)
 assert len(b)<=65536
 canonical_bytes+=len(b);largest_encoding=max(largest_encoding,len(b))
 assert canonical_bytes<=1048576
 return b
u.canonical=canonical
f=load('failure');e=load('evidence');t=load('transcript');d=load('dispatch')
t.failure=d.failure=f;t.evidence=e
results=[]
class Producer(Exception):pass
class Observer(Exception):pass
class Cleanup(Exception):pass
class Route(Exception):pass

# Only tiny object scaffolding is measured; source/import caches are excluded.
tracemalloc.start()
events=[]
class Root:
 def exists(self):return False
 def mkdir(self,**kw):events.append('mkdir')
 def __truediv__(self,other):return self
class J:
 closed=False;size=0;limit=65536
 def close(self):events.append('journal_close');raise Cleanup('journal')
reader=types.SimpleNamespace(tick=lambda:1,report=lambda:{'reserved':7})
old_stage,old_load,old_once,old_os=d.stage,d.load_adapter,d._call_once,d.os
d.stage=lambda *a:events.append('stage')
d.load_adapter=lambda *a:events.append('import')
def closed(fd):events.append('fd_close');raise Cleanup('fd')
d.os=types.SimpleNamespace(close=closed)
def gate(*a):events.append('final_gate');raise Route('changed')
env={'credential':types.SimpleNamespace(receive=lambda *a:(events.append('credential')or 99)),
 'transcript':types.SimpleNamespace(Journal=lambda *a:(events.append('journal_open')or J())),
 'registration':types.SimpleNamespace(repeat=gate),
 'prelaunch':{'registered':{},'review':{},'first':{},'argv':[],'cwd':'/inert'}}
operands={'job':{'credential_broker':{},'metadata_limits':{'trace_bytes':65536}},'runtime_document':{}}
d._call_once=lambda *a:(_ for _ in ()).throw(AssertionError('must not reach execution'))
try:d.run(env,reader,operands,Root())
except Route as exc:
 assert events==['mkdir','stage','import','credential','journal_open','final_gate','fd_close','journal_close']
 assert 'credential_descriptor_close' in exc.__notes__[-1] and 'phase_journal_close' in exc.__notes__[-1]
 results.append({'group':'last_gate_after_preparation_and_all_cleanup','actions':events.copy()})
else:raise AssertionError('changed route accepted')
events.clear();env['registration'].repeat=lambda *a:(events.append('final_gate')or {})
def once(*a):events.append('actual_parent_boundary');raise Producer('first')
d._call_once=once
try:d.run(env,reader,operands,Root())
except Producer as exc:
 assert events[-4:]==['final_gate','actual_parent_boundary','fd_close','journal_close']
 assert 'primary_type":"Producer' in exc.__notes__[-1]
 results.append({'group':'dispatch_original_primary_retained','actions':events.copy()})
else:raise AssertionError('producer failure lost')
d.stage,d.load_adapter,d._call_once,d.os=old_stage,old_load,old_once,old_os

events.clear()
old_os=t.os;t.os=types.SimpleNamespace(fsync=lambda fd:(_ for _ in ()).throw(Observer('fsync')),close=closed)
j=object.__new__(t.Journal);j.closed=False;j.close_attempted=False;j.fd=999;j.size=9;j.reader=reader
try:j.close()
except Observer as exc:
 assert events==['fd_close'] and j.close_attempted and not j.closed and 'journal_descriptor_close' in exc.__notes__[-1]
else:raise AssertionError('fsync failure lost')
try:j.close()
except ValueError:assert events==['fd_close']
else:raise AssertionError('uncertain fd retried')
t.os=old_os;results.append({'group':'journal_all_cleanup_no_unknown_fd_retry','actions':events.copy()})

class Bound:
 runtime=None
 monitor=types.SimpleNamespace(host=types.SimpleNamespace(transport=None,commands=[]))
 def __call__(self,*a):raise Producer('producer')
 def observe(self,*a):raise Observer('observer')
class Journal:
 size=0;limit=65536
 def append(self,row):raise Cleanup('append')
old_capture=e.capture;e.capture=lambda *a:{'known_failed_counter':11}
trace=t.BoundTrace(Bound(),Journal());phase={'id':'inert','kind':'metadata'}
try:trace(phase,{},1,100,'b')
except Producer:pass
try:trace.observe(phase,{},1,100,'b')
except Producer as exc:
 assert trace.pending is None
 note=json.loads(exc.__notes__[-1]);assert [x['stage']for x in note['failures']]==['actual_producer','actual_observer','phase_journal_append']
 results.append({'group':'trace_primary_and_ordered_secondary_failure','notes':note})
else:raise AssertionError('trace failure changed')
e.capture=old_capture

# Independent tiny raw no-worker phase: all values invented, not the full graph.
counts=lambda n:{k:n for k in e.COUNTERS}
identity={'pid':12,'start_ticks':3,'boot_id':'00000000-0000-0000-0000-000000000002'}
doc={'origin_ns':2,'deadline_ns':200,'scientific_source_digest':'a'*64,'programme_digest':'b'*64,
 'profile':{k:20 for k in ('read_bytes','write_bytes','retained_bytes','live_bytes')},
 'host_accounting':{'accounting_scope_digest':'c'*64,'trace_bytes':65536,'child_record_limit':2,
 'process':{'accountant':{'path':'/inert/accountant','bytes':6}},'profile':counts(30)}}
phase={'id':'inert_phase','kind':'metadata','dependencies':[]};binding='d'*64;nonce='e'*48;artifact={'safe':'é'}
commands=[]
for action,n in [('host-phase-open',3),('host-phase-seal',9)]:
 req={'schema':'paper020_host_account_request_v1','phase_id':phase['id'],'binding_digest':binding,'nonce':nonce,
 'host_identity':identity,'origin_ns':2,'deadline_ns':200,'implementation_digest':doc['scientific_source_digest'],
 'programme_digest':doc['programme_digest'],'accounting_scope_digest':doc['host_accounting']['accounting_scope_digest']}
 seals={}if action.endswith('open')else{'artifact':u.scientific_digest(artifact)}
 if seals:req.update(expected_output_seals=seals,expected_worker_closures={})
 resp={'schema':'paper020_host_primitive_snapshot_v1','action':action,'request_digest':u.sha(canonical(req)),
 **{k:req[k]for k in ('nonce','host_identity','origin_ns','deadline_ns','accounting_scope_digest')},
 'scope':'owned_host_tree_excluding_exact_worker_container_cgroups','host_alive':True,'coverage_complete':True,
 'trace_lost':False,'coverage_started_ns':0,'accounted_through_ns':10+n,'counters':counts(n),
 'child_ledger_complete':True,'unknown_children':0,'children':[],'output_seals':seals,'excluded_workers':[],'unclosed_children':[]}
 commands.append({'argv':['/inert/accountant',action,'--request-base64',base64.b64encode(canonical(req)).decode()],
 'returncode':0,'stdout_base64':base64.b64encode(canonical(resp)+b'\n').decode(),'stderr_base64':'',
 'started_ns':9+n,'finished_ns':11+n,'timed_out':False,'interrupted':False,'forced':False,'truncated':False})
compact=[e.compact_command(x)for x in commands]
host={'scope':'live_host_phase_children','phase_id':phase['id'],'binding_digest':binding,'origin_ns':2,'deadline_ns':200,
 'finished_ns':25,'accounted_through_ns':19,'host_identity':identity,'host_alive':True,'phase_observation_complete':True,
 'owned_children_closed':True,'external_host_natural_exit_required':True,'artifact_digest':u.scientific_digest(artifact),
 'output_bundle_digests':seals,'resources':{**counts(9),'observed_cumulative_counters':counts(9),
 'observed_accountant_pin_read_bytes':12,'retained_host_command_trace_bytes':len(canonical(compact)),
 'unobserved_quantities':[],'unobserved_worker_ids':[]},'worker_resources':{},
 'primitive_evidence_digest':compact[-1]['stdout_sha256'],'child_ledger_digest':u.sha(canonical([])),
 'worker_closure_digests':{},'failures':[]}
actual={'schema':'paper020_actual_phase_evidence_v2','host_identity':identity,'phase_nonce':nonce,
 'open':{'sha256':compact[0]['stdout_sha256'],'finished_ns':14},'host_close':host,'whole_close':None,
 'commands':commands,'compact_commands':compact,'workers':[],'pending':[],'known_failure_types':[],
 'runtime_failed':False,'known_last_host_counters':counts(9)}
row={'phase':phase,'binding':binding,'result':{'artifact':artifact},'actual_evidence':actual,
 'observation':{**{k:9 for k in ('read_bytes','write_bytes','retained_bytes','live_bytes')},
 'host_observation_digest':u.sha(canonical(host)),'finished_ns':25}}
assert len(canonical(row))<16384
e.Replay(doc,identity).phase(row)
mutants=[('compact_amount',lambda r:r['observation'].__setitem__('read_bytes',8)),
 ('host_commitment',lambda r:r['observation'].__setitem__('host_observation_digest','0'*64)),
 ('missing_raw_command',lambda r:r['actual_evidence']['commands'].pop()),
 ('failed_measurement',lambda r:r['actual_evidence']['known_failure_types'].append('lost')),
 ('different_host',lambda r:r['actual_evidence'].__setitem__('host_identity',{'pid':1})),
 ('regressed_counter',lambda r:r['actual_evidence']['known_last_host_counters'].__setitem__('write_bytes',1))]
refused=[]
for name,mutate in mutants:
 value=copy.deepcopy(row);mutate(value)
 try:e.Replay(doc,identity).phase(value)
 except ValueError:refused.append(name)
 else:raise AssertionError('raw mutant accepted: '+name)
results.append({'group':'independent_raw_phase_and_commitment_refusals','positive':True,'refused':refused})

# Raw worker counter partition must bind the original worker commitment and bytes.
cid='f'*64;worker={'container_id':cid,'nonce':'1'*48,'evidence_digests':{'counters':''}}
record={'container_id':cid,'nonce':'1'*48,'accounting_complete':True,'all_tasks_exited':True,
 'trace_lost':False,'forced_termination':False,**counts(7)}
blob=canonical(record);worker['evidence_digests']['counters']=u.sha(blob)
workers={cid:{'closure':worker,'commitment':'2'*64}}
response={'excluded_workers':[{'container_id':cid,'worker_closure_digest':'2'*64,'counter_record_base64':base64.b64encode(blob).decode()}]}
resources,commitments=e._partition(response,workers,65536)
assert resources[cid]==counts(7) and commitments[cid]=='2'*64
bad=copy.deepcopy(response);bad['excluded_workers'][0]['worker_closure_digest']='3'*64
try:e._partition(bad,workers,65536)
except ValueError:pass
else:raise AssertionError('worker identity substitution accepted')
results.append({'group':'raw_worker_counter_partition','positive':True,'changed_commitment_refused':True})
_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
assert peak<8388608
report={'schema':'paper020_central_successor_independent_controls_v1','status':'PASS_FOCUSED_SOURCE_ONLY','groups':results,
 'source_reads':source_reads,'canonical_serialization_bytes':canonical_bytes,'largest_canonical_encoding_bytes':largest_encoding,
 'precharged_canonical_ceiling':1048576,'scoped_tracemalloc_peak_bytes':peak,'retained_fixture_bytes_after_run':0,
 'physical_fixtures':0,'source_import_cache_excluded':True,'full_graph_scientific_or_real_process_or_credential_calls':0}
raw=(json.dumps(report,sort_keys=True,indent=2)+'\n').encode();assert len(raw)<65536
(C/'peer-review/SUCCESSOR_CONTROL_RESULTS.json').write_bytes(raw)
print(json.dumps({'status':report['status'],'groups':len(results),'canonical_bytes':canonical_bytes,
 'peak_bytes':peak,'read_bytes':source_reads,'report_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}))
