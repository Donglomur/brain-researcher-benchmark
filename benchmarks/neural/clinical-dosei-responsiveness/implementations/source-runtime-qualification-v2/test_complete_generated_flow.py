"""One full generated source flow; memory evidence, no Docker or live Netlink.

This checks complete orchestration and real report serialization/limits. It is
not a new physical-write, process-custody, sandbox, or native-runtime proof.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

R2=Path(__file__).resolve().parent
OLD=R2.parent/'source-runtime-qualification-v1'
AD=R2.parent/'source-runtime-adapters-v1'
PINS={
 'driver':(R2/'qualification_driver_v2.py','f6d224078d7267c2cc062b8503210364d68cf069ad60b8adeb2dfd58a37e3141'),
 'fixture':(R2/'test_fresh_runtime_state_v1.py','47c476b97825d84527e0338a42cc45987b3b4d9847a4f7685b2e6bbf3b81d8ef'),
 'backend':(AD/'docker_code_backend.py','1a8d96d57e325db0aacd31f2abf8b92ba20de8821bf065aee6b6ef8a9ba3bd9a'),
 'raw':(AD/'raw_command.py','9c2285abdbca85075bf885a2cf40721d9be1ea843671e69ebf05ddc3a46a87a0'),
 'store':(OLD/'evidence_store.py','bc909f0607d3ef70ac720fd5a46b1f5b44283fb5d749dfd6df9d0a132b28eaca')}


def load(key):
    path,pin=PINS[key];data=path.read_bytes();assert hashlib.sha256(data).hexdigest()==pin
    module=types.ModuleType('full_generated_'+key);module.__file__=str(path);sys.modules[module.__name__]=module
    exec(compile(data,str(path),'exec'),module.__dict__);return module


driver,fixture,backend,raw,storage=(load(k) for k in ('driver','fixture','backend','raw','store'))
policy,cases,owned,network,probe=(fixture.policy,fixture.cases,fixture.owned,fixture.network,fixture.probe)
PROFILE_BYTES,PROFILE=fixture.PROFILE_BYTES,fixture.PROFILE
# Use only this pure fictional-output constructor, not the old test module main.
old_test=(OLD/'test_qualification.py').read_bytes()
assert hashlib.sha256(old_test).hexdigest()=='551243198846bb31220c86ad35e41894a28f027a0d92aceea9b31b8b3d97a0b0'
node=next(n for n in ast.parse(old_test).body if isinstance(n,ast.FunctionDef) and n.name=='normal_value')
space={'cases':cases,'policy':policy,'PROFILE':PROFILE}
exec(compile(ast.Module(body=[node],type_ignores=[]),'fixed_generated_normal_value','exec'),space)
normal_value=space['normal_value']


class MemoryEvidence:
    """Successful store shape/cache parity; intentionally no durability claim."""
    instances=[]
    def __init__(self,root):
        self.root=Path(root);self.cleanup=False;self.poisoned=False
        self.charged=self.confirmed=self.known_written=self.denied=0
        self.entries=[];self._by_hash={};self.instances.append(self)
    def __call__(self,kind,data):
        assert type(data) is bytes and type(kind) is str and re.fullmatch('[a-z][a-z0-9_]{0,47}',kind)
        assert not self.poisoned
        cleanup=self.cleanup or kind in ('code_call','code_close','qualification_failure')
        limit=storage.EVIDENCE_CAP if cleanup else storage.EVIDENCE_CAP-storage.CLEANUP_RESERVE
        if self.charged+len(data)>limit or len(self.entries)>=storage.MAX_FILES:
            self.denied+=len(data);raise storage.CustodyFailure('memory evidence capacity')
        self.charged+=len(data);self.confirmed+=len(data);self.known_written+=len(data)
        entry={'path':f'{len(self.entries):04d}-{kind}.bin','kind':kind,'binding':storage.binding(data),
            'charged_bytes':len(data),'known_written_bytes':len(data),'status':'confirmed','cleanup_allowance':cleanup}
        self.entries.append(entry)
        self._by_hash.setdefault(entry['binding']['sha256'],[]).append((entry,data if len(data)<=65536 else None,data[:4096]))
        return dict(entry['binding'])
    lookup=storage.EvidenceStore.lookup
    summary=storage.EvidenceStore.summary


class MemoryReport:
    instances=[]
    def __init__(self,root):
        self.attempted=False;self.charged=self.confirmed=self.known_written=0;self.receipt=None;self.raw=None
        self.instances.append(self)
    def write(self,value):
        assert not self.attempted;self.attempted=True
        self.raw=storage.canonical(value)
        if len(self.raw)>storage.REPORT_CAP:raise storage.CustodyFailure('final report capacity')
        self.charged=self.confirmed=self.known_written=len(self.raw);self.receipt=storage.binding(self.raw)
        return dict(self.receipt)
    summary=storage.ReportWriter.summary


class FakeRunner:
    def __init__(self,ctx):self.ctx=ctx;self.objects={};self.attach_count=0;self.created=0;self.calls=[]
    def __call__(self,command,**kw):
        self.calls.append((list(command),dict(kw)));args=command[5:];output=b'';code=0;failure=None
        if args[:2]==['image','inspect']:output=policy.canonical([PROFILE['selected_image']])
        elif args[0]=='create':
            name=args[args.index('--name')+1];labels=[args[i+1] for i,v in enumerate(args) if v=='--label']
            paths=[args[i+1].split(',')[1][4:] for i,v in enumerate(args) if v=='--mount']
            spec=policy.specification(PROFILE,labels[0].split('=',1)[1],int(labels[1].split('=',1)[1]),*paths)
            identity=hashlib.sha256(name.encode()).hexdigest()
            assert Path(paths[0]).read_bytes()==cases.OBSERVATION
            program=Path(paths[1]).read_bytes();case=cases.NAMES[self.created];self.created+=1
            assert program==self.ctx.generated[case].encode()
            ast.parse(program)  # Syntax only; no candidate execution.
            self.objects[identity]=[spec,0];output=(identity+'\n').encode()
        elif args[:2]==['container','inspect']:
            wanted=args[2];identity=wanted if wanted in self.objects else next(k for k,v in self.objects.items() if v[0]['name']==wanted)
            spec,exitcode=self.objects[identity];item=fixture.legacy.inspect_container(spec,identity)
            item['State']['ExitCode']=exitcode;output=policy.canonical([item])
        elif args[:3]==['container','start','--attach']:
            identity=args[3];name=cases.NAMES[self.attach_count];self.attach_count+=1
            if name in ('flood','deadline'):
                failure='command_output_capacity' if name=='flood' else 'command_wall_timeout';code=-9
                output=cases.marker(name)
                if name=='flood':output=(output+b'F'*(kw['output_limit']+1))[:kw['output_limit']+1]
            elif name=='runtime':output=policy.canonical(self.ctx.runtime_envelope)+b'\n'
            else:
                code=23 if name=='nonzero' else 0;output=policy.canonical(normal_value(name,self.ctx))+b'\n'
            self.objects[identity][1]=code
        elif args[:3]==['container','rm','--force']:
            del self.objects[args[3]];output=(args[3]+'\n').encode()
        elif args[:2]==['container','ls']:output=b''
        else:raise AssertionError(args)
        recorder=kw['recorder'];full=list(self.ctx.command_prefix)+command
        intent=raw.retain(recorder,'command_intent',policy.canonical({'schema':'dosei_raw_command_intent_v1',
            'command':full,'cwd':kw['cwd'],'timeout_seconds':kw['timeout_seconds'],'output_limit':kw['output_limit'],
            'stderr':'merged_raw_stdout','stdin':'closed_without_input'}))
        prefix=raw.retain(recorder,'command_output_prefix',output)
        spawn,closed=fixture.legacy.closed_process(full,len(self.calls),os.getpid())
        closed['leader_returncode']=code;closed['events'][-1]['returncode']=code
        receipt={'schema':'dosei_raw_command_receipt_v1','intent':intent,'spawn':spawn,'closure':closed,
            'observed_prefix':prefix,'retained_original':prefix,'eof_observed':failure is None,
            'unread_output_bytes':None if failure else 0,'charged_output_bytes':kw['output_limit']+1 if failure else len(output),
            'failure_category':failure,'errors':[],'returncode':code,'elapsed_seconds':0.01,'success':failure is None}
        receipt['retained_receipt']=raw.retain(recorder,'command_receipt',policy.canonical(receipt))
        if failure:raise raw.CommandFailure(failure,receipt)
        return {'output':output,'receipt':receipt,'returncode':code}


class Context:
    def __init__(self,root):
        self.output_root=Path(root);self.profile_bytes=PROFILE_BYTES;self.probe_source=fixture.PROBE_SOURCE
        self.started=time.monotonic();self.cancelled=False;self.protocol_sha256='f'*64
        self.command_prefix=['/generated/python','-I','-S','-B','/generated/shim.py','--']
        self.modules={'backend':backend,'policy':policy,'raw':raw,'owned':owned,'cases':cases,
            'store':types.SimpleNamespace(EvidenceStore=MemoryEvidence,ReportWriter=MemoryReport,
                directory_signature=storage.directory_signature,binding=storage.binding,canonical=storage.canonical),
            'fresh_state':fixture.adapter,'network_policy':network,'probe':probe}
        self.generated=cases.programs(str(self.output_root/'staging/GENERATED_HOST_CANARY.txt'),
                                     '/generated/daemon.sock',probe_source=self.probe_source)
        module_pins={'policy':dict(fixture.adapter.MODULE_PINS)['docker_policy'],
            'network_policy':dict(fixture.adapter.MODULE_PINS)['network_policy'],
            'owned':dict(fixture.adapter.MODULE_PINS)['owned'],
            'probe':fixture.adapter.PROBE_SHA256,'cases':fixture.adapter.CASES_SHA256}
        self.protocol={'context_ids':[c*64 for c in 'abc'],'docker_executable':'/generated/docker',
            'docker_socket':'/generated/daemon.sock','python_executable':'/generated/python',
            'cli_shim':{'path':'/generated/shim.py'},'limits':{'operation_deadline_seconds':480,'cleanup_deadline_seconds':570},
            'generated_programs':{k:storage.binding(v.encode()) for k,v in self.generated.items()},
            'modules':{k:{'sha256':v} for k,v in module_pins.items()}}
        example=fixture.Fixture()
        small_link=fixture.frames.link
        def large_link(sequence,**kw):
            kw['unknown']=b'G'*32000
            return small_link(sequence,**kw)
        with patch.object(fixture.frames,'link',large_link):large_state=fixture.fake_state()
        self.runtime_envelope={'schema':'dosei_fresh_runtime_observation_v1','case':'runtime',
            'observation_sha256':cases.OBSERVATION_SHA256,'program_sha256':self.protocol['generated_programs']['runtime']['sha256'],
            'embedded_probe_sha256':fixture.adapter.PROBE_SHA256,'runtime':example.runtime,'network_state':large_state}
        self.command_runner=FakeRunner(self)
    def checkpoint(self,*,cleanup=False):
        if self.cancelled and not cleanup:raise TimeoutError('generated cancellation')


class CompleteFlow(unittest.TestCase):
    def test_all_six_controls_exact_three_closures_and_real_report_cap(self):
        def forbidden(*a,**k):raise AssertionError('real process/network/native execution forbidden')
        with tempfile.TemporaryDirectory(prefix='dosei-fresh-generated-',dir=Path.cwd()) as temp, \
             patch.object(raw,'run',forbidden),patch.object(owned,'OwnedProcess',forbidden), \
             patch.object(probe.socket,'socket',forbidden),patch.object(probe.socket,'if_nameindex',forbidden), \
             patch.object(probe.os,'uname',forbidden),patch.object(network,'evaluate',forbidden):
            ctx=Context(temp);result=driver.run_qualification(ctx);writer=MemoryReport.instances[-1]
            report=json.loads(writer.raw)
            state_binding=report['cases'][0].get('fresh_state_receipt')
            metrics={'generated_only':True,'report_bytes':len(writer.raw or b''),'report_cap':65536,
                'final_fresh_receipt_bytes':None if state_binding is None else state_binding['bytes'],
                'status':result['status'],'failure':result['failure'],'staging_bytes':result['staging_writes']['confirmed_cumulative_write_bytes'],
                'generated_original_runtime_bytes':len(policy.canonical(ctx.runtime_envelope))+1,
                'attach_calls':ctx.command_runner.attach_count,'daemon_commands':len(ctx.command_runner.calls),
                'durable_flood_bytes':0,'durable_report_bytes':0,'actual_docker_or_candidate_execution':False}
            print(json.dumps(metrics,sort_keys=True),flush=True)
            self.assertEqual(result['status'],'succeeded',metrics)
            self.assertEqual([v['case'] for v in report['cases']],list(cases.NAMES))
            self.assertTrue(all(v['status']=='confirmed' for v in report['cases']))
            self.assertEqual(len(report['context_closures']),3)
            self.assertEqual(report['commands']['command_attempts'],43)
            self.assertEqual(ctx.command_runner.attach_count,6);self.assertEqual(ctx.command_runner.created,6)
            self.assertFalse(ctx.command_runner.objects);self.assertEqual(report['commands']['unknown_or_unverified_commands'],[])
            memory_store=MemoryEvidence.instances[-1]
            runtime_original=memory_store.lookup(state_binding,'fresh_runtime_state')[1]
            self.assertIsNotNone(runtime_original)
            self.assertEqual(storage.binding(runtime_original),state_binding)
            self.assertEqual(len([e for e in memory_store.entries if e['kind']=='fresh_runtime_state']),1)
            self.assertNotIn('fresh_state',report['cases'][0])
            runtime=json.loads(runtime_original)
            self.assertTrue(runtime['runtime_control_confirmed']);self.assertFalse(runtime['context_closure_pending'])
            self.assertEqual(len(runtime['complete_context_calls']),4)
            attaches=[r for r in report['commands']['commands'] if r['operation']==['container','start','--attach']]
            self.assertEqual(attaches[0]['requested_output_limit'],2097152)
            self.assertEqual(attaches[0]['effective_output_limit'],524288)
            self.assertEqual(attaches[4]['effective_output_limit'],2097152)
            self.assertEqual(attaches[4]['failure_category'],'command_output_capacity')
            self.assertEqual(attaches[5]['failure_category'],'command_wall_timeout')
            self.assertLessEqual(result['report']['bytes'],65536)
            self.assertLessEqual(report['staging']['confirmed_cumulative_write_bytes'],40960)
            self.assertEqual(report['staging']['unknown_write_grant_bytes'],0)
            self.assertEqual(result['evidence_writes']['unknown_write_grant_bytes'],0)
            self.assertEqual(result['report_writes']['confirmed_cumulative_write_bytes'],len(writer.raw))
            self.assertEqual(sorted(p.name for p in Path(temp,'staging').iterdir()),['GENERATED_HOST_CANARY.txt'])


if __name__=='__main__':unittest.main(verbosity=2)
