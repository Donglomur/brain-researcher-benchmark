"""Generated program/Netlink/CLI bodies only; no live source or Docker calls."""
import ast
import copy
import hashlib
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'source-runtime-qualification-v1'


def load(path,name,pin=None):
    raw=path.read_bytes()
    if pin:assert hashlib.sha256(raw).hexdigest()==pin
    module=types.ModuleType(name);module.__file__=str(path);sys.modules[name]=module
    exec(compile(raw,str(path),'exec'),module.__dict__)
    return module


adapter=load(HERE/'fresh_runtime_state_v1.py','generated_fresh_runtime')
cases=load(HERE/'qualification_cases_v3.py','generated_fresh_cases',adapter.CASES_SHA256)
legacy_cases=load(OLD/'qualification_cases_v2.py','generated_legacy_cases')
legacy=load(OLD/'test_host_network_attestation_v1.py','generated_prior_fixture',
            '1ca490a9060eac9ddf18abb319981f42fe69973b4307f36b1cdd9d1abd2dc0fd')
frames=load(OLD/'test_network_state_probe_v1.py','generated_frames',
            'f2c02801b5b6f29ba8dc03740b018426e8388f284130ea8575c40ee19f7414a8')
probe=frames.probe
PROBE_SOURCE=(OLD/'network_state_probe_v1.py').read_bytes()
assert hashlib.sha256(PROBE_SOURCE).hexdigest()==adapter.PROBE_SHA256
policy,network,owned=legacy.policy,legacy.network,legacy.owned
PROFILE_BYTES,PROFILE=legacy.PROFILE_BYTES,legacy.PROFILE
MODULES={'docker_policy':policy,'network_policy':network,'owned':owned,'probe':probe,'cases':cases}


def fake_state(*,bad_route=False):
    made=[]
    class Socket(frames.FakeSocket):
        def __init__(self,seq):
            super().__init__(seq)
            if seq in (4,5):
                family=2 if seq==4 else 10
                address=b'\x7f\0\0\x01' if family==2 else b'\0'*15+b'\x01'
                attrs=frames.attr(15,struct.pack('=I',255))+frames.attr(1,address)+frames.attr(4,struct.pack('=I',1))
                if bad_route:attrs+=frames.attr(5,address)
                route=probe.ROUTE.pack(family,32 if family==2 else 128,0,0,0,2,254 if family==2 else 0,2,0)
                self.datagrams=[frames.frame(24,route+attrs,seq),frames.frame(3,struct.pack('=i',0),seq)]
    def factory():
        sock=Socket(len(made)+1);made.append(sock);return sock
    return probe.run_probe(socket_factory=factory,if_nameindex=lambda:[(1,'lo')],
        read_status=lambda:(frames.STATUS,True),uname=lambda:('Linux','fictional','6.12','generated','aarch64'),
        clock=lambda:1.0)


class Fixture:
    """Fresh originals with coherent binding updates for semantic mutations."""
    def __init__(self):
        self.base=legacy.Fixture();self.canary=self.base.root+'/staging/GENERATED_HOST_CANARY.txt'
        self.programs=cases.programs(self.canary,self.base.plan['docker_socket'],probe_source=PROBE_SOURCE)
        self.program=self.programs['runtime'].encode()
        self.runtime={'case':'runtime','observation_sha256':cases.OBSERVATION_SHA256,
            'uid':65534,'gid':65534,'python':'3.12.8','numpy':'2.2.6','executable':'/usr/local/bin/python3',
            'cwd':'/work','environment':dict(x.split('=',1) for x in policy.expected_environment(PROFILE)),
            'network_interfaces':['lo'],'network_interfaces_source':'socket.if_nameindex',
            'sysfs_directory_entries':['lo'],'default_ipv4_route':False,'test_net_connect_errno':101,
            'thread_count':1,'input_files':['observation.json','program.py']}
        self.state=fake_state();self.envelope_edit=None;self.call_edit=None;self.setup_edit=None
        self.receipt_edits={};self.command_edits={};self.rebuild()

    def rebuild(self):
        b=self.base;b.command_edits=self.command_edits;b.receipt_edits={};b.call_edit=None;b.rebuild()
        self.originals=dict(b.originals)
        self.originals.pop(legacy.producer.EVIDENCE_NAMES[27])
        def put(position,value):
            raw=value if type(value) is bytes else adapter.canonical(value)
            self.originals[adapter.ORIGINAL_NAMES[position]]=raw;return adapter.binding(raw)
        self.program_binding=put(4,self.program)
        envelope={'schema':'dosei_fresh_runtime_observation_v1','case':'runtime',
            'observation_sha256':cases.OBSERVATION_SHA256,'program_sha256':adapter.binding(self.program)['sha256'],
            'embedded_probe_sha256':adapter.PROBE_SHA256,'runtime':copy.deepcopy(self.runtime),'network_state':copy.deepcopy(self.state)}
        if self.envelope_edit:self.envelope_edit(envelope)
        put(12,adapter.canonical(envelope)+b'\n')
        bindings=[]
        for ordinal,(ip,op,rp) in enumerate(adapter.COMMAND_POSITIONS):
            intent=network.decode(self.originals[adapter.ORIGINAL_NAMES[ip]],adapter.ORIGINAL_CAP)
            if ordinal==3:intent['output_limit']=524288
            ib=put(ip,intent)
            receipt=network.decode(self.originals[adapter.ORIGINAL_NAMES[rp]],adapter.ORIGINAL_CAP)
            ob=adapter.binding(self.originals[adapter.ORIGINAL_NAMES[op]])
            receipt.update(intent=ib,observed_prefix=ob,retained_original=ob,charged_output_bytes=ob['bytes'])
            if ordinal in self.receipt_edits:self.receipt_edits[ordinal](receipt)
            bindings.append(put(rp,receipt))
        setup=network.decode(self.originals[adapter.ORIGINAL_NAMES[3]],adapter.ORIGINAL_CAP)
        setup['max_calls']=4;setup['image_receipt']=bindings[0]
        if self.setup_edit:self.setup_edit(setup)
        put(3,setup)
        call=network.decode(self.originals[adapter.ORIGINAL_NAMES[26]],adapter.ORIGINAL_CAP)
        call.update(program=self.program_binding,initial_inspection=bindings[2],command=bindings[3],final_inspection=bindings[4],
                    closure={'remove':bindings[6],'absence':bindings[7]})
        if self.call_edit:self.call_edit(call)
        put(26,call)
        self.authority=adapter.Authority(
            hashlib.sha256(b'fictional fresh protocol').hexdigest(),b.context_id,b.worker,b.root,
            b.plan['python_executable'],b.plan['cli_shim']['path'],b.plan['docker_executable'],
            b.plan['docker_socket'],self.canary,self.program_binding['sha256'],
            tuple((n,len(v),hashlib.sha256(v).hexdigest()) for n,v in sorted(self.originals.items())),adapter.MODULE_PINS)
        self.calls=[adapter.binding(self.originals[adapter.ORIGINAL_NAMES[26]])]+[
            adapter.binding(adapter.canonical({'fictional_later_call':i})) for i in range(2,5)]
        self.close={'schema':'dosei_docker_code_close_v1','context_id':b.context_id,'calls':copy.deepcopy(self.calls),
            'complete':True,'poisoned':False,'errors':[],'owned_container_ids_unresolved':[],
            'pre_container_setup_failures':[],'container_names_with_unresolved_create':[]}
        return self

    def derive(self):
        return adapter.derive_runtime_state(self.originals,profile_bytes=PROFILE_BYTES,probe_source=PROBE_SOURCE,
                                             authority=self.authority,modules=MODULES)

    def finish(self,receipt):
        return adapter.bind_context_close(receipt,adapter.canonical(self.close),expected_call_bindings=self.calls)


class Controls(unittest.TestCase):
    def setUp(self):
        def forbidden(*a,**k):raise AssertionError('live adapter or historical evaluate forbidden')
        for owner,name in ((probe.socket,'socket'),(probe.socket,'if_nameindex'),(probe.os,'open'),
                           (probe.os,'uname'),(owned,'OwnedProcess'),(network,'evaluate')):
            patcher=patch.object(owner,name,forbidden);patcher.start();self.addCleanup(patcher.stop)

    def test_five_programs_and_legacy_validator_preserved_exactly(self):
        old=legacy_cases.programs('/fictional/canary','/fictional/socket')
        new=cases.programs('/fictional/canary','/fictional/socket',probe_source=PROBE_SOURCE)
        self.assertEqual(tuple(new),legacy_cases.NAMES)
        for name in legacy_cases.NAMES[1:]:self.assertEqual(new[name].encode(),old[name].encode())
        def function_text(path,name):
            text=path.read_text();node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name)
            return ast.get_source_segment(text,node)
        self.assertEqual(function_text(OLD/'qualification_cases_v2.py','validate_normal'),
                         function_text(HERE/'qualification_cases_v3.py','validate_normal'))
        tree=ast.parse(new['runtime']);literal=next(n.value.value for n in tree.body if isinstance(n,ast.Assign) and
            any(isinstance(t,ast.Name) and t.id=='probe_source' for t in n.targets))
        self.assertEqual(literal,PROBE_SOURCE)
        self.assertNotEqual(hashlib.sha256(new['runtime'].encode()).hexdigest(),adapter.PROBE_SHA256)
        self.assertLess(sum(len(v.encode()) for v in new.values())+3*len(cases.OBSERVATION)+len(cases.CANARY),65536)

    def test_complete_fresh_chain_is_provisional_until_four_call_close(self):
        f=Fixture();before=copy.deepcopy(f.originals);p=f.derive()
        self.assertTrue(p['necessary_condition_matches']);self.assertFalse(p['runtime_control_confirmed'])
        self.assertTrue(p['context_closure_pending']);self.assertFalse(p['historical_proof_synthesized'])
        final=f.finish(p);self.assertTrue(final['runtime_control_confirmed']);self.assertFalse(final['network_qualified'])
        self.assertFalse(final['complete_six_control_qualification']);self.assertEqual(before,f.originals)
        self.assertEqual(p['status'],'provisional_runtime_evidence')
        f.calls[1]['bytes']=999;self.assertNotEqual(final['complete_context_calls'][1]['bytes'],999)

    def test_source_output_and_context_coherent_mismatch_refuse(self):
        edits=[lambda e:e.__setitem__('program_sha256','a'*64),
               lambda e:e.__setitem__('embedded_probe_sha256','b'*64),
               lambda e:e['runtime'].__setitem__('observation_sha256','c'*64)]
        for edit in edits:
            f=Fixture();f.envelope_edit=edit;f.rebuild()
            with self.assertRaises((ValueError,network.Refusal)):f.derive()
        f=Fixture();f.program+=b'# changed source\n';f.rebuild()
        with self.assertRaises(ValueError):f.derive()
        f=Fixture();f.call_edit=lambda c:c.__setitem__('context_id','d'*64);f.rebuild()
        with self.assertRaises(ValueError):f.derive()

    def test_non_network_runtime_requirements_still_refuse(self):
        for key,value in (('uid',0),('thread_count',2),('default_ipv4_route',True),('test_net_connect_errno',0),
                          ('numpy','wrong'),('input_files',['observation.json'])):
            f=Fixture();f.runtime[key]=value;f.rebuild()
            with self.assertRaises(ValueError):f.derive()
        f=Fixture();f.runtime['environment']['SECRET']='not allowed';f.rebuild()
        with self.assertRaises(ValueError):f.derive()

    def test_state_refusal_and_incomplete_collection_do_not_qualify(self):
        f=Fixture();f.state=fake_state(bad_route=True);f.rebuild();p=f.derive()
        self.assertFalse(p['necessary_condition_matches']);self.assertFalse(f.finish(p)['runtime_control_confirmed'])
        f=Fixture();f.state['collection_complete']=False;f.rebuild()
        with self.assertRaises(ValueError):f.derive()
        f=Fixture();f.state['dumps'][0]['records'][0]['parsed']['flags']=0;f.rebuild()
        with self.assertRaises(ValueError):f.derive()

    def test_cli_custody_and_context_close_omissions_refuse(self):
        for edit in (lambda r:r['closure'].__setitem__('leader_reaped',False),
                     lambda r:r.__setitem__('charged_output_bytes',True)):
            f=Fixture();f.receipt_edits[3]=edit;f.rebuild()
            with self.assertRaises(ValueError):f.derive()
        f=Fixture();p=f.derive()
        for key,value in (('complete',False),('poisoned',True),('context_id','f'*64),('calls',f.calls[:1])):
            closed=copy.deepcopy(f.close);closed[key]=value
            with self.assertRaises(ValueError):adapter.bind_context_close(p,adapter.canonical(closed),expected_call_bindings=f.calls)
        with self.assertRaises(ValueError):adapter.bind_context_close(p,adapter.canonical(f.close),expected_call_bindings=f.calls[:3])


if __name__=='__main__':unittest.main()
