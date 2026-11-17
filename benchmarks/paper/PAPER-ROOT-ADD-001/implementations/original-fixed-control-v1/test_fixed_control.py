"""Generated composition and admission controls; native Popen always forbidden."""
import copy
import importlib.util
import io
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import fixed_control as d
import fixed_provider as provider
import test_fixed_provider as pf
WORK=64*1024**2
GROSS=0


def limits():
    return dict(working_bytes=WORK,cache_working_bytes=WORK,cache_read_bytes=8*1024**2,
        cache_payload_bytes=512*1024,cache_metadata_bytes=512*1024,cache_entries=32,bundle_bytes=65536,
        frozen_bundle_bytes=1024**2,dispatched_bundle_bytes=1024**2,packed_output_bytes=131072,
        authority_output_bytes=131072,authority_read_bytes=262144,packed_read_bytes=262144,
        receipt_output_bytes=131072,result_output_bytes=131072,wall_seconds=60)


def protocol():
    c=pf.config(42,5685);c.update(scope=provider.ORIGINAL,store_sha256=d.STORE_SHA)
    c['python']={'path':str(Path(sys.executable).resolve()),'bytes':1,'sha256':'3'*64,'version':sys.version.split()[0]}
    return dict(schema='language-selected-fixed-control-protocol/v1',activity=d.ACTIVITY,
        source_pins={k:d.e.sha(v.read_bytes()) for k,v in d.SOURCE_FILES.items()},
        store_root='/unused-private-fixed-store',store_sha256=d.STORE_SHA,source_support_sha256=d.SUPPORT_SHA,
        schedule_sha256='2'*64,store_read_limits={'collection':16*1024**2,'recovery':32*1024**2},
        store_working_bytes=128*1024**2,artifact_root='/unused-private-fixed-output',provider_config=c,
        collection_limits=limits(),recovery_limits=limits(),operator_joint_admission_bytes=1024**3,
        child_working_bytes=WORK,whole_seconds=180,numpy_version=np.__version__,summary_output_bytes=131072)


def fixture_module():
    path=HERE.parent/'original-figure3b-store-v1/test_store.py'
    spec=importlib.util.spec_from_file_location('_fixed_control_generated_fixture',path)
    module=importlib.util.module_from_spec(spec)
    saved={k:sys.modules.get(k) for k in ('producer','reader')}
    sys.path.insert(0,str(path.parent))
    try:
        for k in saved:sys.modules.pop(k,None)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
        for k,v in saved.items():
            if v is None:sys.modules.pop(k,None)
            else:sys.modules[k]=v
    return module


class Controls(unittest.TestCase):
    def setUp(self):
        self.forbid=patch.object(subprocess,'Popen',side_effect=AssertionError('No actual process in generated controls'))
        self.forbid.start()
    def tearDown(self):self.forbid.stop()

    def test_protocol_accepts_same_numeric_runtime_as_provider_and_rejects_mutated_scope(self):
        self.assertEqual(d.protocol_snapshot(protocol())['activity'],d.ACTIVITY)
        for field in ('source','store','support','counts','runtime','memory','time'):
            with self.subTest(field=field):
                p=protocol()
                if field=='source':p['source_pins']['fixed_provider.py']='0'*64
                elif field=='store':p['store_sha256']='0'*64
                elif field=='support':p['source_support_sha256']='0'*64
                elif field=='counts':p['provider_config']['caps']['max_requests']=5684
                elif field=='runtime':p['provider_config']['python']['version']=sys.version
                elif field=='memory':p['operator_joint_admission_bytes']=1
                else:p['whole_seconds']=119
                with self.assertRaises(ValueError):d.protocol_snapshot(p)

    def test_missing_admission_fails_before_reader_or_artifact_creation(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            p=protocol();p['artifact_root']=str(Path(tmp)/'new')
            with patch.object(d,'load_reader',side_effect=AssertionError('private source opened')):
                with self.assertRaisesRegex(ValueError,'root control admission'):d.execute(p,None)
            self.assertFalse(Path(p['artifact_root']).exists())

    def test_admission_protocol_mismatch_fails_before_provider_or_source(self):
        p=protocol()
        fake=types.SimpleNamespace(config_snapshot=lambda c:c,identity=provider.identity,
            admission_snapshot=lambda c,a:{'protocol_sha256':'0'*64})
        with patch.object(d.e,'load_pinned',return_value=fake),patch.object(d,'load_reader',side_effect=AssertionError('source opened')):
            with self.assertRaisesRegex(ValueError,'entire protocol'):d.execute(p,{})

    def test_owned_provider_closes_and_failure_is_saved_on_reader_error(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            p=protocol();p['artifact_root']=str(Path(tmp)/'new');closed=[]
            class Owned:
                def close(self):closed.append('provider')
            fake=types.SimpleNamespace(config_snapshot=lambda c:c,identity=provider.identity,
                admission_snapshot=lambda c,a:{'protocol_sha256':d.e.sha(d.e.encoded(p)),'root_admission_id':'generated'},
                FixedProvider=lambda *a,**k:Owned())
            readers=types.SimpleNamespace(StoreReader=lambda *a,**k:(_ for _ in ()).throw(ValueError('saved source failure')))
            with patch.object(d.e,'load_pinned',return_value=fake),patch.object(d,'load_reader',return_value=readers):
                with self.assertRaisesRegex(ValueError,'saved source failure'):d.execute(p,{})
            self.assertEqual(closed,['provider'])
            failure=d.e.J.P.parse((Path(p['artifact_root'])/'FAILURE.json').read_bytes())
            self.assertFalse(failure['complete']);self.assertEqual(failure['error'],'saved source failure')

    def test_signal_handler_raises_cleanup_exception_and_restores_handlers(self):
        before={s:signal.getsignal(s) for s in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT)}
        with self.assertRaises(KeyboardInterrupt):
            with d.interruptible():signal.getsignal(signal.SIGTERM)(signal.SIGTERM,None)
        self.assertEqual(before,{s:signal.getsignal(s) for s in before})

    def test_source_authentication_refuses_changed_bytes_and_symlink_before_exec(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            path=Path(tmp)/'code';path.write_bytes(b'pass\n')
            with self.assertRaises(ValueError):d.read_verified(path,'0'*64,128)
            alias=Path(tmp)/'alias';alias.symlink_to(path)
            with self.assertRaises(ValueError):d.read_verified(alias,d.e.sha(path.read_bytes()),128)
            with self.assertRaises(ValueError):d.read_verified(path,d.e.sha(path.read_bytes()),1)

    def test_original_equal_session_control_summary_preserves_all14_and_undefined_values(self):
        endpoint=d.e.J.ENDPOINT
        packet={'schema':'language-original-figure3b-scores/v1','role':'candidate',
            'selection_sha256':d.e.sha(endpoint.encoded(endpoint.selection())),
            'source_support_sha256':d.SUPPORT_SHA,'prediction_run_sha256':'4'*64,
            'scores':[{'context':context,'pearson_r':i/64} for i,context in enumerate(endpoint.contexts())],
            'execution_qualified':False}
        result=d.control_summary(packet)
        self.assertEqual(len(result['sessions']),14)
        np.testing.assert_equal(result['equal_session_mean'],np.arange(42,dtype=np.float64).reshape(14,3).mean(axis=1).mean()/64)
        self.assertEqual(result['defined_session_means'],14);self.assertIsNone(result['reference_comparison'])
        packet['scores'][5]['pearson_r']=None;result=d.control_summary(packet)
        self.assertIsNone(result['sessions'][1]['mean']);self.assertIsNone(result['equal_session_mean'])
        self.assertEqual(result['defined_session_means'],13);self.assertEqual(len(result['sessions']),14)

    def test_composed_generated_selected_store_fixed_provider_packed_and_original_scores(self):
        global GROSS
        fixture=fixture_module();_,data,_,plan=fixture.fixture()
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root=Path(tmp);store=root/'store'
            out=fixture.s.prepare_generated(store,plan,{'p1_1':data},working_limit=256*1024**2,
                output_limit=256*1024,metadata_limit=512*1024)
            readers=d.load_reader()
            def reader():return readers.StoreReader(store,expected_store_sha256=out['store']['sha256'],read_limit=16*1024**2,working_limit=256*1024**2)
            count=out['metadata']['counts']['software_callbacks']
            cfg=pf.config(3,count);cfg['store_sha256']=out['store']['sha256']
            fake=pf.FakeExecutor();fixed=provider.FixedProvider(cfg,None,evidence_root=root/'provider',executor=fake)
            run=d.e.J.make_run(store_sha256=out['store']['sha256'],candidate_sha256=provider.WORKER_SHA,
                schedule_sha256=cfg['schedule_sha256'],provider_source_sha256=provider.identity(),condition='paper_data',
                working_limit=WORK,generated_contexts=list(d.e.J.ENDPOINT.coordinates()[:3]),generated_requests=count)
            collected,pin=d.e.collect(reader(),fixed,run,root/'outputs',limits=limits())
            self.assertEqual(collected['provider']['worker_executions'],3)
            self.assertEqual(collected['provider']['derived_responses'],count)
            result,_=d.e.recover(reader(),run,root/'outputs',collected,collection_sha256=pin['sha256'],limits=limits())
            for item,score in zip(fixture.s.iter_selected_jobs(data),result['result']['generated_scores']):
                expected=((item['time_indices']%17)-8).astype('<f8')[:,None]/8
                np.testing.assert_equal(score['correlations'],d.e.J.ORIGINAL.pooled_pearson(item['y'],expected))
            self.assertFalse(result['scientific_qualification']);self.assertNotIn('candidate_scores',result['result'])
            self.assertEqual(len(fake.calls),3)
            GROSS+=sum(v.stat().st_size for v in root.rglob('*') if v.is_file())
            self.assertLess(GROSS,512*1024)

if __name__=='__main__':unittest.main()
