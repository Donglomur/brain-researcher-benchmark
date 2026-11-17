"""Bounded invented controls for complete NEURAL035 metadata/clock adapter."""
import copy
import hashlib
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import mock

HERE = Path(__file__).resolve().parent
source = (HERE / 'adapter.py').read_bytes()
a = ModuleType('invented_neural035_adapter'); a.__file__ = str(HERE / 'adapter.py')
exec(compile(source, a.__file__, 'exec'), a.__dict__)
SERIALIZED = 0
original_encode = a.encode
def encoded(value):
    global SERIALIZED
    raw = original_encode(value); SERIALIZED += len(raw)
    assert SERIALIZED <= 350000
    return raw
a.encode = encoded
PIN = {'bytes': 12, 'sha256': 'a' * 64}
def row(name, identity=PIN): return {'path': '/invented/' + name, **identity}
class RAM:
    def __init__(self, docs): self.docs = docs; self.reads = []
    def read(self, path, cap, expected=None, *args):
        key = str(path); assert key in self.docs, key
        self.reads.append(key); raw = self.docs[key]; assert len(raw) <= cap
        if expected is not None: assert a.pin(raw) == expected
        return raw
    def tick(self): pass
class Poison:
    def __str__(self): raise AssertionError('poison operand converted')
    def __fspath__(self): raise AssertionError('poison operand touched')
def refuse(fn, message=None):
    try: fn()
    except ValueError as error:
        if message is not None: assert str(error) == message, (str(error), message)
    else: raise AssertionError('required refusal absent')

# 1: partial timer installation attempts every independent cleanup action.
old = {1: object(), 2: object(), 3: object()}; calls = []; timer = [0., 0.]
def changing(sig, value):
    calls.append(('signal', sig)); old[sig] = value
    if sig == 2: raise OSError('invented restoration failure')
def set_timer(kind, value):
    calls.append(('timer', value))
    if value > 0: raise OSError('invented initial timer failure')
    timer[:] = [0., 0.]
signal = SimpleNamespace(ITIMER_REAL=0, SIGALRM=1, SIGTERM=2, SIGINT=3,
    getitimer=lambda _: tuple(timer), getsignal=lambda n: old[n], signal=changing, setitimer=set_timer)
with mock.patch.object(a, 'signal', signal), mock.patch.object(a, 'time', SimpleNamespace(monotonic=lambda: 110.)), mock.patch.object(a, 'ORIGIN', 100.):
    try: a.enter_startup()
    except OSError: pass
    else: raise AssertionError('failed setup passed')
    assert ('timer', 0) in calls and ('signal', 3) in calls

# 2: nonperiodic original remainder only; no fresh120-second renewal.
signal.getsignal = lambda _: a.expired
for value in ((120., 0.), (100., 1.), (0., 0.)):
    signal.getitimer = lambda _, value=value: value
    with mock.patch.object(a, 'signal', signal), mock.patch.object(a, 'time', SimpleNamespace(monotonic=lambda: 110.)), mock.patch.object(a, 'ORIGIN', 100.):
        refuse(a.startup_owned)
signal.getitimer = lambda _: (109., 0.)
with mock.patch.object(a, 'signal', signal), mock.patch.object(a, 'time', SimpleNamespace(monotonic=lambda: 110.)), mock.patch.object(a, 'ORIGIN', 100.): a.startup_owned()

# 3: missing independent qualification refuses before selection/program/output.
binding = {'controller_source': PIN, 'resources': {}}
qualified = {'schema':'neural035_full14_registration_runtime_v1','task_id':a.TASK,'qualified':False}
qraw = encoded(qualified)
review = {'schema':'neural035_full14_registration_review_v1','task_id':a.TASK,'approved':True,
    'adapter_source':PIN,'controller_source':PIN,'selection':'must never parse','program':'must never parse',
    'adapter_runtime':row('qualification', a.pin(qraw)), 'typed_result':'neural035_full14_unscored_result_v1','private_grading_authorized':False}
ram = RAM({'/invented/review':encoded(review), '/invented/qualification':qraw})
args = SimpleNamespace(review='/invented/review',program=Poison(),output=Poison(),other_reserve_bytes=Poison())
with mock.patch.object(a, 'literal', side_effect=lambda x: Path(x)):
    refuse(lambda:a.bind(args,ram,PIN,binding), 'independent complete NEURAL035 adapter runtime prerequisite')
assert ram.reads == ['/invented/review','/invented/qualification']

# 4: current observer uses the checked native interface without source rewriting.
observer = (HERE.parent / 'program/observe.py').read_bytes()
a.original_observer(observer, '/invented/observe.py')
refuse(lambda:a.original_observer(observer.replace(b"guard(ORIGIN)",b"guard(ORIGIN+1)"),'/invented/observe.py'))
refuse(lambda:a.original_observer(observer.replace(b"raise SystemExit(result)",b"raise SystemExit(0)"),'/invented/observe.py'))

# 5: complete metadata joins two28-query outputs and fixed/candidate commitments.
origin = a.ORIGIN; whole = origin + 1000; outer = whole + 60
output = Path('/invented/attempt'); baseline = b'invented operator source'
selection = {'program':row('candidate'), 'method_review':row('method')}
programs = {'candidate':PIN, 'operator':a.pin(baseline)}
outputs = {'candidate':{'bytes':101,'sha256':'b'*64}, 'operator':{'bytes':102,'sha256':'c'*64}}
commitment = {'schema':'neural035_program_commitment_v1','source':PIN,'programs':programs,'before_any_public_view':True,'method_review':PIN}
complete = {'schema':'neural035_full14_complete_v1','status':'complete_unqualified','source':PIN,
    'programs':programs,'commitment':a.pin(encoded(commitment)), 'outputs':2,'query_blocks_per_output':28,
    'sessions':14,'biological_mice':7,'cells':1012,'all_views_retired':True,'external_natural_zero_required':True,
    'private_grading_performed':False,'target_bodies_opened':False,'runtime_qualified':False,'scientific_qualified':False,
    'contexts':[{'case':i,'role':role,'native_closed':True,'prediction':outputs[role],'native_receipt':PIN}
                for i,role in enumerate(('candidate','operator'))], 'public_manifest':PIN,'retirement':PIN}
child = {'exit_code':0,'natural_exit':True,'process_reaped':True,'process_group_absent':True,'streams_closed':True,
    'timed_out':False,'kill_sent':False,'error_type':None,'timer_disable_error':None,'timer_restore_error':None}
observed = {'schema':'neural035_full14_external_v1','status':'complete_unqualified','source':PIN,'selection':PIN,
    'attempt':str(output),'error_type':None,'origin_monotonic':origin,'whole_deadline':whole,'outer_deadline':outer,
    'full14_source_scope':True,'scientific_qualified':False,'runtime_qualified':False,'grading_performed':False,
    'nested_native_recovery_may_be_required':False,'automatic_retry':False,'child':child,'outputs':outputs,
    'complete':a.pin(encoded(complete))}
def packet(obs,comp,commit):
    c = encoded(commit); comp = copy.deepcopy(comp); comp['commitment'] = a.pin(c); b = encoded(comp)
    obs = copy.deepcopy(obs); obs['complete'] = a.pin(b); r = encoded(obs); assert len(r) <= 8192
    return RAM({str(output)+'.observer':r+b' '*(8192-len(r)),str(output/'COMPLETE.json'):b,
                str(output/'commitment/COMMITMENT.json'):c})
def call(ram):
    with mock.patch.object(a,'literal',side_effect=lambda x:Path(x)):
        return a.outcome(ram,(Path('/invented/selection'),PIN,32768),binding,
                         {'baseline_program.py':baseline},output,whole,outer,selection)
ram = packet(observed,complete,commitment); answer=call(ram)
assert answer['outputs']==outputs and len(ram.reads)==3 and answer['adapter_replays_prediction_or_target_bodies']is False

# 6: selected incompleteness/lineage/qualification failures do not become success.
mutations = [
    ('observed',lambda x:x['outputs'].pop('operator')),
    ('observed',lambda x:x['child'].update(kill_sent=True)),
    ('observed',lambda x:x.update(whole_deadline=whole+1)),
    ('complete',lambda x:x.update(query_blocks_per_output=27)),
    ('complete',lambda x:x['programs'].update(operator=PIN)),
    ('complete',lambda x:x['contexts'][0].update(case=False)),
    ('complete',lambda x:x.update(target_bodies_opened=True)),
    ('commitment',lambda x:x.update(before_any_public_view=False))]
for where,mutate in mutations:
    parts={'observed':copy.deepcopy(observed),'complete':copy.deepcopy(complete),'commitment':copy.deepcopy(commitment)}
    mutate(parts[where]); refuse(lambda:call(packet(parts['observed'],parts['complete'],parts['commitment'])))
print(json.dumps({'status':'PASS_SOURCE_RAM_ONLY','groups':6,'adapter':a.pin(source),
    'observer':a.pin(observer),'invented_encoded_bytes':SERIALIZED,'physical_fixture_bytes':0,
    'actual_signals_native_environment_candidate_scorer_calls':0}))
