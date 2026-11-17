"""Tiny RAM seams only: no real staging, descriptors, processes or science."""
import ast
import hashlib
import json
from pathlib import Path
import tracemalloc
from types import SimpleNamespace

C=Path('authoring/delivery-20261105/common/remaining-builds-wave21/paper020-full-design/implementation-v1/runtime-adapters-v1/central-integration')
PINS={
 'dispatch.py':(6340,'366a34803bc7e16bcf51f96c72308948629c8c9885e30499f396ff387984a49b'),
 'transcript.py':(11274,'adaca1993ed6c7f077a26a3111da4c1263b6acfb0bd0ef3f92a9424a21b084c9'),
 'registration.py':(4845,'a200d058531e3a36c43776179a3f3a19fc30852969fa80beeedd3b161f7f13ea'),
}
source={}
for name,(n,h) in PINS.items():
 b=(C/name).read_bytes();assert len(b)==n and hashlib.sha256(b).hexdigest()==h;source[name]=b
raw=Path('benchmarks/neuroscience/paper-root-add-020/manifest.json').read_bytes()
assert len(raw)==26829 and hashlib.sha256(raw).hexdigest()=='5233d9d82a396cd8dfa331f6b6a26fb0fb41bbaa2b3be9bdf06bc0b4f0ecd89d'
registry=json.loads(raw)
def need(ok,message):
 if not ok:raise ValueError(message)
def definitions(name,selected,bindings):
 tree=ast.parse(source[name]);tree.body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in selected]
 ns=dict(bindings);exec(compile(tree,str(C/name),'exec'),ns);return ns
class PrimaryFailure(Exception):pass
class CloseFailure(Exception):pass
class JournalFailure(Exception):pass
events=[]
class Root:
 def exists(self):return False
 def mkdir(self,**kw):events.append('mkdir_mock')
 def __truediv__(self,other):return self
class Journal:
 def close(self):events.append('journal_close')
def call_once(*args):events.append('scientific_boundary_mock');raise PrimaryFailure('original failed operation')
def close_fd(fd):events.append('fd_close');raise CloseFailure('descriptor close failure')
u=SimpleNamespace(need=need,components=lambda p:p)
ns=definitions('dispatch.py',{'run'},{'u':u,'os':SimpleNamespace(close=close_fd),
 'stage':lambda *args:None,'load_adapter':lambda *args:None,'_call_once':call_once})
tracemalloc.start()
env={'credential':SimpleNamespace(receive=lambda *args:99),'transcript':SimpleNamespace(Journal=lambda *args:Journal())}
operands={'job':{'credential_broker':{},'metadata_limits':{'trace_bytes':100}},'runtime_document':{}}
try:ns['run'](env,None,operands,Root())
except CloseFailure as exc:
 assert isinstance(exc.__context__,PrimaryFailure)
 assert events==['mkdir_mock','scientific_boundary_mock','fd_close']
 first={'observed_primary_type':type(exc).__name__,'earlier_context_type':type(exc.__context__).__name__,
        'actions':events.copy(),'journal_close_attempted':False}
else:raise AssertionError('initial defect was not reproduced')
class Bound:
 runtime=None;monitor=None
 def observe(self,*args):raise PrimaryFailure('underlying observer failure')
class Append:
 def append(self,row):raise JournalFailure('journal failed')
ns=definitions('transcript.py',{'BoundTrace'},{'u':u})
trace=ns['BoundTrace'](Bound(),Append());trace.pending={'phase':{'id':'tiny'},'binding':'b'}
try:trace.observe({'id':'tiny'},{},1,2,'b')
except JournalFailure as exc:
 assert isinstance(exc.__context__,PrimaryFailure)
 second={'observed_primary_type':type(exc).__name__,'earlier_context_type':type(exc.__context__).__name__,
         'pending_cleared':trace.pending is None}
else:raise AssertionError('append precedence defect was not reproduced')
# Real fixed registry metadata is source evidence, not an invented numerical input.
ns=definitions('registration.py',{'resolve','qualify'},{'u':u,'TASK':'PAPER-ROOT-ADD-020',
 'REGISTRY':'benchmarks/neuroscience/paper-root-add-020/manifest.json','CONDITIONS':{'full14_compiled_pair':'compiled','full14_investigate_pair':'investigate'}})
reads=[]
reader=SimpleNamespace(json=lambda p,cap:(reads.append(str(p)) or registry,{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}))
env={'repo':Path('/inert/repo'),'interface':{'path':'inert-current-full'},'source_rows':{'entry.py':{'sha256':'0'*64}},'entry_relative':'entry.py'}
try:ns['qualify'](env,reader)
except ValueError as exc:
 assert str(exc)=='current canonical registry does not select this full IT central source'
 assert reads==['/inert/repo/benchmarks/neuroscience/paper-root-add-020/manifest.json']
 third={'refusal':str(exc),'reads':reads,'qualification_backend_or_candidate_reads':0}
else:raise AssertionError('actual legacy metadata accepted')
_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
result={'schema':'paper020_central_initial_peer_controls_v1','status':'TWO_CONFIRMED_FAILURE_PATH_DEFECTS_AND_POSITIVE_EARLY_REFUSAL',
 'dispatch_cleanup':first,'observation_journal':second,'legacy_gate':third,'source_pins':PINS,
 'scoped_tracemalloc_peak_bytes':peak,'source_and_import_cache_excluded':True,
 'fixture_precharge_bytes':131072,'retained_fixture_limit':1048576,'live_fixture_limit':8388608,
 'physical_fixtures':0,'authentic_inputs':0,'actual_process_or_descriptor_or_model_calls':0,
 'whole_graph_replay':False,'metadata_source_read_bytes':sum(len(b)for b in source.values())+len(raw)}
encoded=(json.dumps(result,sort_keys=True,indent=2)+'\n').encode()
assert len(encoded)<=65536 and peak<8388608
result['canonical_result_bytes_before_cost_field']=len(encoded)
encoded=(json.dumps(result,sort_keys=True,indent=2)+'\n').encode()
assert len(encoded)<65536
(C/'peer-review/INITIAL_CONTROL_RESULTS.json').write_bytes(encoded)
print(json.dumps({'status':result['status'],'result_bytes':len(encoded),'scoped_peak_bytes':peak,
                  'sha256':hashlib.sha256(encoded).hexdigest(),'source_read_bytes':result['metadata_source_read_bytes']}))
