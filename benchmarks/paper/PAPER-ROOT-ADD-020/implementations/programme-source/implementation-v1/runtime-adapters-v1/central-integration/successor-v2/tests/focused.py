"""Invented metadata only: actual new replay and failure paths, no science."""
import base64
import copy
import dataclasses
import json
from pathlib import Path
import sys
import tracemalloc
import types
import unittest

HERE=Path(__file__).absolute().parents[1];FIXTURE=0;READ=0;EVIDENCE={}
def mod(name):
    global READ
    p=HERE/(name+'.py');raw=p.read_bytes();READ+=len(raw);m=types.ModuleType('_it_central_v2_'+name);m.__file__=str(p)
    if name!='common_io':m.u=u
    sys.modules[m.__name__]=m;exec(compile(raw,str(p),'exec'),m.__dict__);return m
u=mod('common_io');f=mod('failure');e=mod('evidence');t=mod('transcript');d=mod('dispatch');c=mod('credential')
t.failure=d.failure=c.failure=f;t.evidence=e
def charge(x):
    global FIXTURE
    FIXTURE+=len(u.canonical(x));assert FIXTURE<=512*1024
    return x
class PrimaryFailure(Exception):pass
class SecondaryFailure(Exception):pass

def phase_fixture():
    counters=lambda n:{k:n for k in e.COUNTERS}
    origin,deadline=1,1000;identity={'pid':7,'start_ticks':1,'boot_id':'00000000-0000-0000-0000-000000000001'}
    doc={'origin_ns':origin,'deadline_ns':deadline,'scientific_source_digest':'1'*64,'programme_digest':'2'*64,
         'profile':{k:100 for k in ('read_bytes','write_bytes','retained_bytes','live_bytes')},
         'host_accounting':{'accounting_scope_digest':'3'*64,'trace_bytes':100000,'child_record_limit':20,
           'process':{'accountant':{'path':'/invented/accountant','bytes':4}},'profile':counters(100)}}
    p={'id':'invented-metadata','kind':'invented_metadata','dependencies':[]};binding='4'*64;nonce='a'*48;artifact={'label':'étendue'}
    commands=[]
    for n,action in enumerate(('host-phase-open','host-phase-seal')):
        request={'schema':'paper020_host_account_request_v1','phase_id':p['id'],'binding_digest':binding,'nonce':nonce,
                 'host_identity':identity,'origin_ns':origin,'deadline_ns':deadline,'implementation_digest':doc['scientific_source_digest'],
                 'programme_digest':doc['programme_digest'],'accounting_scope_digest':doc['host_accounting']['accounting_scope_digest']}
        seals={}if n==0 else{'artifact':u.scientific_digest(artifact)}
        if n:request.update(expected_output_seals=seals,expected_worker_closures={})
        response={'schema':'paper020_host_primitive_snapshot_v1','action':action,'request_digest':u.sha(u.canonical(request)),
          **{k:request[k]for k in ('nonce','host_identity','origin_ns','deadline_ns','accounting_scope_digest')},
          'scope':'owned_host_tree_excluding_exact_worker_container_cgroups','host_alive':True,'coverage_complete':True,
          'trace_lost':False,'coverage_started_ns':0,'accounted_through_ns':11+10*n,'counters':counters(4+n),
          'child_ledger_complete':True,'unknown_children':0,'children':[],'output_seals':seals,'excluded_workers':[],'unclosed_children':[]}
        raw=u.canonical(response)+b'\n'
        commands.append({'argv':['/invented/accountant',action,'--request-base64',base64.b64encode(u.canonical(request)).decode()],
           'returncode':0,'stdout_base64':base64.b64encode(raw).decode(),'stderr_base64':'','started_ns':10+10*n,
           'finished_ns':12+10*n,'timed_out':False,'interrupted':False,'forced':False,'truncated':False})
    compact=[e.compact_command(x)for x in commands]
    resources={**counters(5),'observed_cumulative_counters':counters(5),'observed_accountant_pin_read_bytes':8,
               'retained_host_command_trace_bytes':len(u.canonical(compact)),'unobserved_quantities':[],'unobserved_worker_ids':[]}
    h={'scope':'live_host_phase_children','phase_id':p['id'],'binding_digest':binding,'origin_ns':1,'deadline_ns':1000,
       'finished_ns':25,'accounted_through_ns':21,'host_identity':identity,'host_alive':True,'phase_observation_complete':True,
       'owned_children_closed':True,'external_host_natural_exit_required':True,'artifact_digest':u.scientific_digest(artifact),
       'output_bundle_digests':{'artifact':u.scientific_digest(artifact)},'resources':resources,'worker_resources':{},
       'primitive_evidence_digest':compact[-1]['stdout_sha256'],'child_ledger_digest':u.sha(u.canonical([])),
       'worker_closure_digests':{},'failures':[]}
    actual={'schema':'paper020_actual_phase_evidence_v2','host_identity':identity,'phase_nonce':nonce,
       'open':{'sha256':compact[0]['stdout_sha256'],'finished_ns':12},'host_close':h,'whole_close':None,
       'commands':commands,'compact_commands':compact,'workers':[],'pending':[],'known_failure_types':[],'runtime_failed':False,
       'known_last_host_counters':counters(5)}
    row={'phase':p,'binding':binding,'result':{'artifact':artifact},'actual_evidence':actual,
         'observation':{k:5 for k in ('read_bytes','write_bytes','retained_bytes','live_bytes')}}
    row['observation'].update(host_observation_digest=u.sha(u.canonical(h)),finished_ns=25)
    return charge((row,doc,identity))

class Controls(unittest.TestCase):
    def test_actual_command_capture(self):
        @dataclasses.dataclass
        class Result:
            argv:tuple;returncode:int;stdout:bytes;stderr:bytes;started_ns:int;finished_ns:int
            timed_out:bool=False;interrupted:bool=False;forced:bool=False;truncated:bool=False
        result=Result(('/invented/accountant','host-phase-open','--request-base64','e30='),0,b'{"invented_counter":3}',b'',2,3)
        calls=[]
        def run(*args,**kwargs):calls.append(args);return result
        observed=e.Commands(types.SimpleNamespace(run=run),10000);self.assertIs(observed.run(result.argv,origin_ns=1),result)
        self.assertEqual(len(calls),1);self.assertEqual(base64.b64decode(observed.rows[0]['stdout_base64']),result.stdout)
        charge(observed.rows);observed.begin();self.assertEqual(observed.rows,[])
        observed.limit=1
        with self.assertRaises(ValueError):observed.run(result.argv)
        self.assertEqual(len(observed.rows),1);charge(observed.rows)

    def test_actual_fit_receipt_and_context(self):
        row,doc,identity=phase_fixture();p=row['phase'];p.update(id='fit/A/calibrated/0/observed/case',kind='fit',actor='A',dependencies=['view/A/calibrated/0/observed'])
        cid='c'*64;image='d'*64;source='e'*64;model='b'*64;input_digest='f'*64
        doc['images']={'candidate':{'source_digest':image}}
        rawcounter={'container_id':cid,'nonce':'b'*48,'accounting_complete':True,'all_tasks_exited':True,'trace_lost':False,
                    'forced_termination':False,**{k:7 for k in e.COUNTERS}}
        counters=u.canonical(rawcounter);payload=b'invented output'
        worker={'phase_id':p['id'],'binding_digest':row['binding'],'implementation_digest':doc['scientific_source_digest'],
          'origin_ns':1,'deadline_ns':1000,'finished_ns':20,'container_id':cid,'nonce':'b'*48,'natural_complete':True,
          'all_descendants_closed':True,'exit_code':0,'input_digest':input_digest,'model_digest':None,'source_digest':image,
          'payload_digest':u.sha(payload),'resources':{k:7 for k in e.COUNTERS},'view_isolation_verified':True,
          'source_seal_unchanged':True,'evidence_digests':{'counters':u.sha(counters)},'failures':[]}
        commitment=e.worker_commitment(worker)
        receipt={'natural_complete':True,'all_descendants_closed':True,'exit_code':0,'model_digest':model,'input_digest':input_digest,
          'binding_digest':row['binding'],'container_id':cid,'output_digest':u.sha(payload),'source_digest':source,'finished_ns':20,
          'evidence_digests':worker['evidence_digests']}
        artifact={'model_digest':model,'input_digest':input_digest,'fit_receipt_digest':u.scientific_digest(receipt),'implementation_digest':doc['scientific_source_digest']}
        row['result']['artifact']=artifact;actual=row['actual_evidence'];actual['workers']=[{'context':'ctx','phase_id':p['id'],'operation':'fit','closure':worker,'payload_pin':u.pin(payload)}]
        actual['pending']=[{'context':'ctx','operation':'fit','input_digest':input_digest,'source_digest':source,'actual_model_digest':model,'worker_closure_digest':commitment}]
        for n,command in enumerate(actual['commands']):
            req=u.parse(base64.b64decode(command['argv'][3]));req['phase_id']=p['id']
            resp=u.parse(base64.b64decode(command['stdout_base64']))
            if n:
                req['expected_output_seals']={'artifact':u.scientific_digest(artifact)};req['expected_worker_closures']={cid:commitment}
                resp['output_seals']=req['expected_output_seals'];resp['excluded_workers']=[{'container_id':cid,'worker_closure_digest':commitment,'counter_record_base64':base64.b64encode(counters).decode()}]
            resp['request_digest']=u.sha(u.canonical(req));command['argv'][3]=base64.b64encode(u.canonical(req)).decode();command['stdout_base64']=base64.b64encode(u.canonical(resp)+b'\n').decode()
        actual['compact_commands']=[e.compact_command(z)for z in actual['commands']]
        actual['open']['sha256']=actual['compact_commands'][0]['stdout_sha256']
        h=actual['host_close'];h.update(phase_id=p['id'],artifact_digest=u.scientific_digest(artifact),output_bundle_digests={'artifact':u.scientific_digest(artifact)},
           worker_resources={cid:{k:7 for k in e.COUNTERS}},worker_closure_digests={cid:commitment},primitive_evidence_digest=actual['compact_commands'][-1]['stdout_sha256'])
        h['resources']['retained_host_command_trace_bytes']=len(u.canonical(actual['compact_commands']))
        row['observation'].update({k:12 for k in ('read_bytes','write_bytes','retained_bytes','live_bytes')});row['observation']['host_observation_digest']=u.sha(u.canonical(h))
        charge((row,doc))
        def check(value):
            r=e.Replay(doc,identity);r.context_outputs[p['dependencies'][0]]='ctx';r._current_open=value['actual_evidence']['open'];r.phase(value)
        check(row)
        for key,value in [('source_digest','a'*64),('actual_model_digest','a'*64),('context','other')]:
            bad=copy.deepcopy(row);bad['actual_evidence']['pending'][0][key]=value;charge(bad)
            with self.subTest(key=key),self.assertRaises(ValueError):check(bad)
        EVIDENCE['actual_fit_receipt']={'worker_source_input_output_model_context_join':True,'mutations_refused':3,'scientific_fits':0}

    def test_raw_phase_replay(self):
        row,doc,identity=phase_fixture();replay=e.Replay(doc,identity);replay._current_open=row['actual_evidence']['open'];replay.phase(row)
        self.assertEqual(replay.consumed['read_bytes'],5);self.assertEqual(replay.phase_count,1)
        mutations=[('compact cost',lambda x:x['observation'].update(read_bytes=6)),
          ('raw absolute',lambda x:x['actual_evidence']['host_close']['resources']['observed_cumulative_counters'].update(read_bytes=4)),
          ('raw delta',lambda x:x['actual_evidence']['host_close']['resources'].update(read_bytes=4)),
          ('known failure',lambda x:x['actual_evidence'].update(known_failure_types=['failed worker'])),
          ('incomplete commands',lambda x:x['actual_evidence']['commands'].pop()),
          ('unknown clock',lambda x:x['actual_evidence']['commands'][0].update(started_ns=None))]
        for label,change in mutations:
            bad=copy.deepcopy(row);change(bad);charge(bad);r=e.Replay(doc,identity);r._current_open=bad['actual_evidence']['open']
            with self.subTest(label=label),self.assertRaises((ValueError,KeyError)):r.phase(bad)
        EVIDENCE['actual_primitive_replay']={'invented_phases':1,'negative_controls':len(mutations),'actual_accountant_commands':0}

    def test_whole_partition_no_double_count(self):
        row,doc,identity=phase_fixture();r=e.Replay(doc,identity);r.consumed['read_bytes']=4
        r.phase_observations={'earlier':row['actual_evidence']['host_close']};r._current_open={'sha256':'5'*64,'finished_ns':40}
        phase={'id':'outer-close','kind':'independent_full_process_and_resource_closure'};binding='6'*64
        rawcounter={'container_id':'7'*64,'nonce':'b'*48,'accounting_complete':True,'all_tasks_exited':True,'trace_lost':False,
                    'forced_termination':False,**{k:(7 if k=='read_bytes'else 1)for k in e.COUNTERS}}
        raw=u.canonical(rawcounter);closure={'container_id':'7'*64,'nonce':'b'*48,'evidence_digests':{'counters':u.sha(raw)}}
        worker={'closure':closure,'commitment':'8'*64};workers={'7'*64:worker}
        artifact={k:'9'*64 for k in ('native_bundle_digest','prediction_bundle_digest','expected_bundle_digest','native_schema_digest')}
        seals={**artifact,'host_phase_observations_digest':u.sha(u.canonical({'earlier':u.sha(u.canonical(r.phase_observations['earlier'])),'outer-close':r._current_open}))}
        response={'counters':{k:5 for k in e.COUNTERS},'output_seals':seals,'children':[],'unclosed_children':[],
          'accounted_through_ns':50,'excluded_workers':[{'container_id':'7'*64,'worker_closure_digest':'8'*64,'counter_record_base64':base64.b64encode(raw).decode()}]}
        resources={**response['counters'],'observed_cumulative_counters':response['counters'],'unobserved_quantities':[],'unobserved_worker_ids':[],
                   'observed_accountant_pin_read_bytes':0,'retained_host_command_trace_bytes':len(u.canonical([]))}
        h={'scope':'live_host_phase_children','host_identity':identity,'phase_id':'whole-host-close','binding_digest':binding,
           'origin_ns':1,'deadline_ns':1000,'host_alive':True,'phase_observation_complete':True,'owned_children_closed':True,
           'external_host_natural_exit_required':True,'failures':[],'primitive_evidence_digest':'a'*64,'child_ledger_digest':u.sha(u.canonical([])),
           'accounted_through_ns':50,'finished_ns':55,'output_bundle_digests':seals,'resources':resources,
           'worker_resources':{'7'*64:{k:rawcounter[k]for k in e.COUNTERS}},'worker_closure_digests':{'7'*64:'8'*64}}
        doc['profile']['read_bytes']=12;charge((h,response,workers,artifact,doc))
        r._close(h,response,{'stdout_sha256':'a'*64,'finished_ns':52},workers,'host-whole-close',phase,binding,artifact)
        self.assertIs(r.whole,h);self.assertEqual(r.consumed['read_bytes'],4)
        EVIDENCE['whole_cost_oracle']={'prior_host':4,'current_cumulative_host':5,'distinct_worker':7,'whole':12,'profile':12,'prior_total_added':False}

    def test_trace_preserves_observer_failure(self):
        calls=[];phase={'id':'invented','kind':'invented_metadata'}
        host=types.SimpleNamespace(records={'invented':{'nonce':'a'*48,'open':None,'close':None}},identity={'pid':7},commands=[],last_counters={},failures=['invented failed observation'])
        runtime=types.SimpleNamespace(jobs=[],pending={},failure=True)
        def observe(*args):calls.append('observe');raise PrimaryFailure('primary')
        def append(value):charge(value);calls.append('append');raise SecondaryFailure('journal')
        bound=types.SimpleNamespace(runtime=runtime,monitor=types.SimpleNamespace(host=host,whole_observation=None),observe=observe)
        trace=t.BoundTrace.__new__(t.BoundTrace);trace.bound=bound;trace.pending={'phase':phase,'binding':'1'*64,'producer_error':None}
        trace.producer_failure=None;trace.commands=types.SimpleNamespace(rows=[]);trace.compact_start=0
        trace.journal=types.SimpleNamespace(append=append,size=42)
        with self.assertRaises(PrimaryFailure)as ctx:trace.observe(phase,{},1,100,'1'*64)
        self.assertEqual(calls,['observe','append']);self.assertIn('SecondaryFailure',' '.join(ctx.exception.__notes__))

    def test_journal_independent_close(self):
        journal=t.Journal.__new__(t.Journal);journal.closed=False;journal.close_attempted=False;journal.fd=33;journal.size=12
        calls=[]
        def sync(fd):calls.append('sync');raise PrimaryFailure('sync')
        def close(fd):calls.append('close');raise SecondaryFailure('close')
        def tick():calls.append('clock');raise ValueError('late')
        journal.reader=types.SimpleNamespace(tick=tick);old=t.os;t.os=types.SimpleNamespace(fsync=sync,close=close)
        try:
            with self.assertRaises(PrimaryFailure)as ctx:journal.close()
            self.assertEqual(calls,['sync','close','clock']);self.assertIn('SecondaryFailure',' '.join(ctx.exception.__notes__))
            with self.assertRaises(ValueError):journal.close()
            self.assertEqual(calls,['sync','close','clock'])
        finally:t.os=old

    def test_credential_cleanup_all_owned(self):
        calls=[];state=f.Failures();state.capture(PrimaryFailure('acquire'),'acquire')
        def socket_close():calls.append('socket');raise SecondaryFailure('socket')
        def fdclose(fd):calls.append(fd);raise SecondaryFailure('descriptor')
        old=c.os;c.os=types.SimpleNamespace(close=fdclose)
        try:c._close_resources(types.SimpleNamespace(close=socket_close),[33,34,33],state)
        finally:c.os=old
        with self.assertRaises(PrimaryFailure)as ctx:state.raise_if_failed({'known_descriptors':2})
        self.assertEqual(calls,['socket',33,34]);self.assertEqual(len(state.records),4)

    def test_last_route_and_cleanup(self):
        class Path:
            def exists(self):return False
            def mkdir(self,**kwargs):events.append('mkdir')
            def __truediv__(self,name):return self
        class Journal:
            def __init__(self,*args):self.closed=False;events.append('journal')
            def close(self):events.append('journal-close');self.closed=True;raise SecondaryFailure('journal close')
        for reject in (False,True):
            events=[];path=Path();old=(d.u,d.stage,d.load_adapter,d._call_once,d.os)
            fake_u=types.SimpleNamespace(components=lambda x:path,need=u.need)
            def stage(*args):events.append('stage');return path
            def load(*args):events.append('import');return object()
            def credential(*args):events.append('credential');return 33
            def route(*args):
                events.append('last-route')
                if reject:raise PrimaryFailure('route changed')
                return {'invented_route':True}
            def call(*args):events.append('actual-call-seam');raise PrimaryFailure('scientific seam')
            def close(fd):events.append('fd-close');raise SecondaryFailure('close')
            d.u=fake_u;d.stage=stage;d.load_adapter=load;d._call_once=call;d.os=types.SimpleNamespace(close=close)
            env={'transcript':types.SimpleNamespace(Journal=Journal),'credential':types.SimpleNamespace(receive=credential),
                 'registration':types.SimpleNamespace(repeat=route),'prelaunch':{k:None for k in ('registered','review','first','argv','cwd')}}
            reader=types.SimpleNamespace(tick=lambda:events.append('clock'),report=lambda:{'invented_cost':1})
            operands={'job':{'credential_broker':{},'metadata_limits':{'trace_bytes':100}},'runtime_document':{}}
            try:
                with self.assertRaises(PrimaryFailure)as ctx:d.run(env,reader,operands,path)
            finally:d.u,d.stage,d.load_adapter,d._call_once,d.os=old
            self.assertLess(events.index('credential'),events.index('last-route'))
            self.assertEqual(events[-2:],['fd-close','journal-close'])
            self.assertEqual('actual-call-seam'in events,not reject)
            self.assertIn('SecondaryFailure',' '.join(ctx.exception.__notes__));charge(events)
        EVIDENCE['failure_and_route']={'last_route_after_preparation':True,'changed_route_prevents_entry':True,'primary_retained':True,'all_cleanup_attempted':True,'real_processes_or_descriptors':0}

if __name__=='__main__':
    tracemalloc.start();suite=unittest.TestSuite(Controls(n)for n in sys.argv[1:])if len(sys.argv)>1 else unittest.defaultTestLoader.loadTestsFromTestCase(Controls)
    result=unittest.TextTestRunner(verbosity=1).run(suite);_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    print(json.dumps({'schema':'paper020_central_v2_focused_controls','tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
      'canonical_fixture_bytes':FIXTURE,'scoped_peak_bytes':peak,'source_read_bytes':READ,'evidence':EVIDENCE,'authentic_graphs':0,'science':0,'actual_processes':0},sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful()else 1)
