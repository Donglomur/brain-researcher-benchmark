"""Generated format/custody/mocked lifecycle controls; no native child launch."""
from contextlib import ExitStack
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import provider as p

WORK = 32*1024**2
BYTE = 65536


def fixture_module():
    spec = importlib.util.spec_from_file_location('provider_generated_bundle_fixture',
                    HERE.parent/'original-compact-bundles-v1/test_bundle.py')
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0,str(Path(spec.origin).parent))
    try: spec.loader.exec_module(module)
    finally: sys.path.pop(0)
    return module


F = fixture_module()


def inputs(held=-0.,fortran=False):
    source = F.fixture(); source['x'] = np.array(source['x'],order='F' if fortran else 'C')
    source,job,selection,allowed = F.operands(source,held)
    bundle = F.encode(source,selection,allowed)
    stream = io.BytesIO(); np.save(stream,source['x'],allow_pickle=False); feature = stream.getvalue()
    desc = F.b.make_descriptor(bundle,job.context,feature_sha256=p.sha(feature),feature_bytes=len(feature),
                              feature_fortran_order=fortran,byte_limit=BYTE,working_limit=WORK)
    return source,job,bundle,feature,desc


def config():
    caps = {key:16*1024**2 for key in p.CAPS}
    caps.update(working_bytes=WORK,bundle_bytes=BYTE,max_jobs=10,max_requests=20,
                per_request_seconds=3,cleanup_seconds=2,run_seconds=60,
                child_memory_bytes=128*1024**2,pids=8,tmpfs_bytes=1024**2,
                cpu_quota_us=100000,cpu_period_us=100000,child_cpu_seconds=5,
                request_stdout_bytes=65536,request_stderr_bytes=4096)
    tree = lambda kind: {'root':'/generated/'+kind,'manifest':'/generated/'+kind+'.json','manifest_sha256':'1'*64}
    return dict(schema='language-exec-provider/v1',mode=p.MODE,condition='paper_data',candidate_sha256='1'*64,
                provider_source_sha256=p.identity(),store_sha256='2'*64,schedule_sha256='3'*64,
                runtime=tree('runtime'),candidate=tree('candidate'),assistance=tree('assistance'),
                bwrap={'path':'/generated/bwrap','bytes':4,'sha256':'4'*64,'version':'0.11.0'},
                cgroup_parent='/generated-cgroup',python_path='/usr/bin/python3',caps=caps)


def admission(c):
    return {'schema':'language-native-execution-admission/v1','mode':p.MODE,
            'config_sha256':p.sha(p.encoded(c)),'protocol_sha256':'5'*64,'qualification_sha256':'6'*64,
            'qualification_scope':'linux-bwrap011-cgroupv2-execreset-native',
            'admitted_until_unix':int(time.time())+600,'root_admission_id':'generated-only-no-execution-authority'}


def generated_tree(parent,kind):
    root=parent/kind; root.mkdir()
    dirs = []
    members = {'candidate.py':b'NOT_EXECUTED'} if kind == 'candidate' else {}
    if kind == 'runtime':
        dirs = ['artifacts','candidate','dev','executor','input','proc','tmp','usr','usr/bin']
        members = {'executor/entry.py':b'','input/features.npy':b'','input/request.json':b'',
                   'input/responses.bin':b'','usr/bin/python3':b'NOT_EXECUTED'}
    for d in dirs: (root/d).mkdir(parents=True,exist_ok=True)
    files=[]
    for path,raw in sorted(members.items()):
        (root/path).write_bytes(raw); (root/path).chmod(0o444)
        files.append({'path':path,'bytes':len(raw),'sha256':p.sha(raw),'mode':0o444})
    for d in reversed(dirs): (root/d).chmod(0o555)
    root.chmod(0o555)
    raw=p.encoded({'schema':'language-frozen-public-tree/v1','kind':kind,
                   'condition':'generic' if kind=='runtime' else 'paper_data','directories':dirs,'files':files})
    manifest=parent/(kind+'.json');manifest.write_bytes(raw);manifest.chmod(0o444)
    return {'root':str(root),'manifest':str(manifest),'manifest_sha256':p.sha(raw)}


def setup_config(root):
    c=config()
    for kind in ('runtime','candidate','assistance'): c[kind]=generated_tree(root,kind)
    c['candidate_sha256']=c['candidate']['manifest_sha256']
    raw=b'\x7fELFgenerated-not-executable'; path=root/'fake-bwrap';path.write_bytes(raw);path.chmod(0o555)
    c['bwrap'].update(path=str(path),bytes=len(raw),sha256=p.sha(raw))
    return c


def fake_sealed(raw,meter):
    meter.charge('staging_bytes',len(raw))
    with tempfile.TemporaryFile() as stream:
        stream.write(raw);stream.flush();stream.seek(0)
        return os.dup(stream.fileno())


class FakeBackend:
    calls=[]
    @staticmethod
    def require_platform(): pass
    def invoke(self,c,fds,deadline,meter):
        self.calls.append((p.command(c,fds),dict(fds)))
        raw=os.pread(fds['bundle'],65536,0); desc=os.pread(fds['descriptor'],8192,0)
        feature=os.pread(fds['feature'],65536,0)
        tx,ty,qx,context=p.PUBLIC.operands(feature,raw,desc,byte_limit=BYTE,working_limit=WORK)
        out=io.BytesIO();np.save(out,np.zeros((len(qx),ty.shape[1]),dtype='<f4'),allow_pickle=False)
        prediction=out.getvalue();meter.charge('stdout_bytes',len(prediction))
        return prediction,{'natural_exit_zero':True,'owned_processes_absent':True,
                           'generated_mock_only':True,'gate_joined_before_exec':True,'pidfd_owned':True}


class ProviderControls(unittest.TestCase):
    def test_config_and_admission_preflight_before_serializing_unbounded_values(self):
        c=config();a=admission(c)
        c['runtime']['root']='x'*4097
        with mock.patch.object(p,'encoded',side_effect=AssertionError('unbounded serialization')):
            with self.assertRaises(ValueError):p.config_snapshot(c)
            a['root_admission_id']='x'*129
            with self.assertRaises(ValueError):p.admission_snapshot(c,a)

    def test_minimal_public_decoder_matches_accepted_callback_bits_and_context(self):
        for held,fortran in ((-0.,False),(-2.,True),(3.,False)):
            source,job,raw,feature,desc=inputs(held,fortran)
            actual=p.PUBLIC.operands(feature,raw,desc.public_json,byte_limit=BYTE,working_limit=WORK)
            expected=F.b.assemble_request(source['x'],raw,job.context,byte_limit=BYTE,working_limit=WORK)
            for a,b in zip(actual[:3],expected[:3]):
                self.assertEqual(a.dtype,b.dtype);self.assertEqual(a.shape,b.shape);self.assertEqual(a.tobytes(),b.tobytes())
            self.assertEqual(set(actual[3]),set(expected[3]))
            for key,value in expected[3].items():
                if isinstance(value,np.ndarray): self.assertEqual(actual[3][key].tobytes(),value.tobytes())
                else: self.assertEqual(actual[3][key],value)

    def test_public_decoder_rejects_mutable_trailing_object_and_wrong_feature_binding(self):
        _,_,bundle,feature,desc=inputs()
        for bad in (bundle+b'x',bytearray(bundle),bundle[:48]+b'x'+bundle[49:]):
            with self.assertRaises(ValueError): p.PUBLIC.operands(feature,bad,desc.public_json,byte_limit=BYTE,working_limit=WORK)
        with self.assertRaises(ValueError): p.PUBLIC.operands(feature[:-1]+b'x',bundle,desc.public_json,byte_limit=BYTE,working_limit=WORK)
        stream=io.BytesIO();np.save(stream,np.array([object()],dtype=object),allow_pickle=True)
        with self.assertRaises(ValueError): p.PUBLIC.feature(stream.getvalue(),6,False)

    def test_public_work_refusal_precedes_numpy_view(self):
        _,_,bundle,feature,desc=inputs()
        with mock.patch.object(p.PUBLIC.np,'frombuffer',side_effect=AssertionError('late admission')):
            with self.assertRaises(ValueError):p.PUBLIC.operands(feature,bundle,desc.public_json,byte_limit=BYTE,working_limit=1)

    def test_no_default_mode_expired_or_mismatched_admission_and_platform_fail_before_evidence(self):
        c=config()
        for mode in ('clean_forkserver_v1','',None):
            wrong=dict(c,mode=mode)
            with self.assertRaises(ValueError):p.config_snapshot(wrong)
        for a in (dict(admission(c),config_sha256='f'*64),dict(admission(c),admitted_until_unix=1)):
            with self.assertRaises(ValueError):p.admission_snapshot(c,a)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()/'absent'
            with mock.patch.object(p.LinuxBackend,'require_platform',side_effect=ValueError('unqualified')):
                with self.assertRaises(ValueError):p.NativeProvider(c,admission(c),evidence_root=root)
            self.assertFalse(root.exists())

    def test_command_contains_only_declared_mounts_and_required_namespaces(self):
        argv=p.command(config(),dict(zip(('bwrap','runtime','candidate','assistance','entry','feature','bundle','descriptor'),range(30,38))))
        self.assertEqual(argv.count('--ro-bind-fd'),5);self.assertEqual(argv.count('--ro-bind-data'),2)
        for flag in ('--unshare-user','--unshare-cgroup','--unshare-all','--disable-userns','--die-with-parent','--clearenv'):
            self.assertIn(flag,argv)
        self.assertNotIn('/generated',str(argv));self.assertNotIn('--share-net',argv)
        self.assertEqual(argv[-4:],['-B','/executor/entry.py',str(BYTE),str(WORK)])
        self.assertIn('/input/responses.bin',argv);self.assertNotIn('original-inputs',str(argv))

    def test_complete_generated_stage_dispatch_retire_and_single_journal(self):
        FakeBackend.calls=[]
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(p,'LinuxBackend',FakeBackend),mock.patch.object(p,'sealed',fake_sealed):
            root=Path(tmp).resolve();c=setup_config(root)
            _,_,bundle,feature,desc=inputs();path=root/'source.npy';path.write_bytes(feature);path.chmod(0o444)
            provider=p.NativeProvider(c,admission(c),evidence_root=root/'evidence')
            handle=provider.prepare_feature(path,{'sha256':p.sha(feature),'bytes':len(feature),'fortran_order':False},rows=6)
            original_staging=provider.meter.values['staging_bytes']
            raw,closure=provider.run_request(handle,bundle,desc)
            second,closure2=provider.run_request(handle,bundle,desc)
            self.assertEqual(len(FakeBackend.calls),2)
            self.assertEqual(FakeBackend.calls[0][1]['feature'],FakeBackend.calls[1][1]['feature'])
            self.assertEqual(provider.meter.values['staging_bytes']-original_staging,2*(len(bundle)+len(desc.public_json)))
            self.assertEqual(provider.meter.values['sandbox_copy_bytes'],2*(len(bundle)+len(desc.public_json)))
            self.assertTrue(closure['private_view_retired']);self.assertEqual(closure['transport_sha256'],p.sha(raw))
            self.assertEqual(raw,second);self.assertEqual(closure2['candidate_sha256'],c['candidate_sha256'])
            provider.release_feature(handle);receipt=provider.finish()
            provider.close();provider.close()
            self.assertFalse(receipt['scientific_qualification']);self.assertEqual(receipt['counters']['max_requests'],2)
            self.assertEqual(sorted(x.name for x in (root/'evidence').iterdir()),['LIFECYCLE.jsonl'])
            log=(root/'evidence'/'LIFECYCLE.jsonl').read_bytes()
            self.assertEqual(receipt['lifecycle']['sha256'],p.sha(log));self.assertEqual(len(log),receipt['lifecycle']['bytes'])

    def test_wrong_request_id_latches_before_launch_or_staging(self):
        with tempfile.TemporaryDirectory() as tmp,mock.patch.object(p,'LinuxBackend',FakeBackend),mock.patch.object(p,'sealed',fake_sealed):
            root=Path(tmp).resolve();c=setup_config(root);_,_,bundle,feature,desc=inputs()
            path=root/'source.npy';path.write_bytes(feature);path.chmod(0o444)
            provider=p.NativeProvider(c,admission(c),evidence_root=root/'evidence')
            handle=provider.prepare_feature(path,{'sha256':p.sha(feature),'bytes':len(feature),'fortran_order':False},rows=6)
            count=provider.meter.values['staging_bytes']
            with self.assertRaises(ValueError):provider.run_request(handle,bundle,{'public_json':desc.public_json,'public_id':'0'*64})
            self.assertTrue(provider.failed);self.assertEqual(count,provider.meter.values['staging_bytes'])
            with self.assertRaises(ValueError):provider.run_request(handle,bundle,desc)
            provider.close()

    def test_source_tree_rejects_unlisted_file_and_symlink_before_authenticating_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();desc=generated_tree(root,'assistance');tree=Path(desc['root']);tree.chmod(0o755)
            (tree/'leak').write_bytes(b'private');(tree/'leak').chmod(0o444);tree.chmod(0o555)
            meter=p.Meter(config()['caps'])
            with self.assertRaises(ValueError):p.authenticate_tree(desc,'assistance',meter,WORK)
            self.assertEqual(meter.observed['tree_read_bytes'],Path(desc['manifest']).stat().st_size)
            tree.chmod(0o755);(tree/'leak').unlink();(tree/'leak').symlink_to('/etc/passwd');tree.chmod(0o555)
            with self.assertRaises(ValueError):p.authenticate_tree(desc,'assistance',p.Meter(config()['caps']),WORK)
            # Remove our link directly; tempfile's permission repair must not follow it.
            tree.chmod(0o755);(tree/'leak').unlink()

    def test_read_budget_precedes_open_and_growth_is_bounded_by_exact_extent(self):
        meter=p.Meter(config()['caps']);meter.caps['feature_read_bytes']=4
        with mock.patch.object(p.os,'open',side_effect=AssertionError('unadmitted read')):
            with self.assertRaises(ValueError):p.read_owned('/absent',4,'1'*64,meter,'feature_read_bytes')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp).resolve()/'data';path.write_bytes(b'abcd');path.chmod(0o444)
            raw,_=p.read_owned(path,4,p.sha(b'abcd'),p.Meter(config()['caps']),'feature_read_bytes')
            self.assertEqual(raw,b'abcd')
            link=Path(tmp).resolve()/'link';link.symlink_to(path)
            with self.assertRaises(ValueError):p.read_owned(link,4,p.sha(b'abcd'),p.Meter(config()['caps']),'feature_read_bytes')


class MockNativeLifecycle(unittest.TestCase):
    def test_parent_death_guard_checks_owner_and_no_new_privs_without_native_calls(self):
        prctl=mock.Mock(return_value=0)
        with mock.patch.object(p.os,'getppid',return_value=77):p.arm_parent_death(prctl,77)
        self.assertEqual(prctl.call_args_list,[mock.call(1,int(p.signal.SIGKILL),0,0,0),mock.call(38,1,0,0,0)])
        prctl.reset_mock()
        with mock.patch.object(p.os,'getppid',return_value=1):
            with self.assertRaisesRegex(ValueError,'coordinator'):p.arm_parent_death(prctl,77)
        self.assertEqual(prctl.call_count,1)

    def scenario(self,nonzero=False):
        events=[];chunks={20:[b'raw-npy',b''],22:[b'err',b'']};waits=[(0,0),(1000,256 if nonzero else 0)]
        class Selector:
            def __init__(self):self.active={}
            def register(self,fd,event,data):self.active[fd]=types.SimpleNamespace(fd=fd,data=data)
            def unregister(self,fd):self.active.pop(fd)
            def get_map(self):return self.active
            def select(self,timeout):return [(x,1) for x in list(self.active.values())]
            def close(self):pass
        def read(fd,name,meter):
            events.append(('read',name))
            return {'cgroup.type':'domain','memory.max':str(128*1024**2),'memory.swap.max':'0','pids.max':'8',
                    'cpu.max':'100000 100000','cgroup.events':'populated 0','memory.events':'oom_kill 0',
                    'cgroup.procs':'1000','cpu.stat':'usage_usec 1'}[name]
        def write(fd,name,value,meter):events.append(('control',name,value))
        with ExitStack() as stack:
            patches={
              'open':mock.Mock(side_effect=[80,81]),'mkdir':mock.Mock(),'rmdir':mock.Mock(),
              'pipe2':mock.Mock(side_effect=[(20,21),(22,23),(24,25)]),'fork':mock.Mock(return_value=1000),
              'close':mock.Mock(side_effect=lambda fd:events.append(('close',fd))),
              'write':mock.Mock(side_effect=lambda fd,data:events.append(('gate',fd,data)) or len(data)),
              'set_blocking':mock.Mock(),'read':mock.Mock(side_effect=lambda fd,n:chunks[fd].pop(0)),
              'waitpid':mock.Mock(side_effect=lambda *a:waits.pop(0)),
              'fstat':mock.Mock(return_value=types.SimpleNamespace(st_ino=999,st_dev=10))}
            patches['pidfd_open']=mock.Mock(side_effect=lambda *a:(events.append(('pidfd',)),90)[1])
            for key,value in patches.items():stack.enter_context(mock.patch.object(p.os,key,value,create=True))
            stack.enter_context(mock.patch.object(p.signal,'pidfd_send_signal',create=True))
            stack.enter_context(mock.patch.object(p.LinuxBackend,'require_platform',return_value=None))
            stack.enter_context(mock.patch.object(p.selectors,'DefaultSelector',Selector))
            stack.enter_context(mock.patch.object(p,'_read_at',side_effect=read))
            stack.enter_context(mock.patch.object(p,'_write_at',side_effect=write))
            stack.enter_context(mock.patch.object(p,'_prctl',return_value=mock.Mock(return_value=0)))
            fds=dict(zip(('bwrap','runtime','candidate','assistance','entry','feature','bundle','descriptor'),range(30,38)))
            backend=p.LinuxBackend()
            if nonzero:
                with self.assertRaisesRegex(ValueError,'naturally'):backend.invoke(config(),fds,time.monotonic()+3,p.Meter(config()['caps']))
                result=None
            else:result=backend.invoke(config(),fds,time.monotonic()+3,p.Meter(config()['caps']))
        return result,events

    def test_parent_joins_exact_child_before_exec_gate_and_waits_closure_before_return(self):
        result,events=self.scenario()
        self.assertEqual(result[0],b'raw-npy');self.assertTrue(result[1]['owned_processes_absent'])
        attach=events.index(('control','cgroup.procs','1000'));gate=events.index(('gate',25,b'G'))
        self.assertLess(attach,gate);self.assertIn(('close',90),events)
        self.assertEqual(result[1]['cgroup_inode'],999)

    def test_nonzero_candidate_never_returns_raw_transport(self):
        result,events=self.scenario(True)
        self.assertIsNone(result);self.assertIn(('close',90),events)


if __name__=='__main__':unittest.main()
