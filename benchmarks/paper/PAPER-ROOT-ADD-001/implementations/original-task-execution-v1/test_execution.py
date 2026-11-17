"""Generated private collection/recovery controls; no subprocess or model."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import execution as e
import run as cli
import prepare as prep

WORK = 32*1024**2
PINS = dict(store_sha256='1'*64,candidate_sha256='2'*64,schedule_sha256='3'*64,provider_source_sha256='4'*64)


def fixture(root):
    path = HERE.parent/'original-private-cache-v1/test_cache.py'
    spec = importlib.util.spec_from_file_location('_execution_cache_fixture',path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0,str(path.parent))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(path.parent))
    _,base,specs,arrays = mod.fixture(root)
    V = e.C.V
    jobs = [base,V.FeatureJob(V.JobContext('p1_1','unit','context',1,20,0),base.feature_id,
              base.qid_id,base.time_id,base.response_shards,base.output_columns)]
    y = np.empty((len(arrays[base.qid_id]),base.output_columns),dtype='<f8')
    for shard in base.response_shards:
        y[np.asarray(shard.row_positions)] = arrays[shard.object_id]
    feature = next(s for s in specs if s.object_id == base.feature_id)
    items = []
    for job in jobs:
        items.append({'context':{k:getattr(job.context,k) for k in e.J.SOURCE_CONTEXT_KEYS},
            'view_job':job,'qid':arrays[base.qid_id],'time_indices':arrays[base.time_id],
            'support_class_sha256':'5'*64,'target_sha256':e.sha(y.tobytes()),
            'feature':{'sha256':feature.sha256,'bytes':feature.bytes,'fortran_order':feature.fortran_order},
            'feature_spec':feature,'feature_path':root/feature.relative_path,'targets':y})
    return specs,items


class Session:
    def __init__(self,root,specs,items):
        self.root,self.specs,self.items,self.session,self.closed = root,specs,items,'p1_1',False
    def iter_jobs(self,*,include_targets=False):
        for item in self.items:
            yield {k:v for k,v in item.items() if include_targets or k != 'targets'}
    def close(self):
        self.closed = True


class Reader:
    def __init__(self,root,specs,items):
        self.session = Session(root,specs,items)
        self.store_sha256,self.closed = PINS['store_sha256'],False
    def iter_sessions(self):
        yield self.session
    def close(self):
        self.closed = True


class Provider:
    """Pure generated function consumes permitted bundle only; never launches code."""
    def __init__(self,wrong_closure=False):
        self.prepares=self.calls=self.releases=0
        self.closed=False
        self.active=None
        self.wrong_closure=wrong_closure
    def prepare_feature(self,path,spec,*,rows):
        assert self.active is None
        self.prepares += 1; self.active = (str(path),spec.sha256,rows)
        return self.active
    def run_request(self,handle,raw,descriptor):
        assert handle == self.active
        public = json.loads(descriptor.public_json)
        assert public['features']['sha256'] == handle[1]
        data = e.J.B.decode_bundle(raw,byte_limit=65536,working_limit=WORK)
        prediction = data.time_indices[data.query_positions,None].astype('<f8') + np.arange(data.output_columns)[None,:]
        out = io.BytesIO(); np.save(out,prediction,allow_pickle=False); body = out.getvalue()
        self.calls += 1
        closure = dict(schema='language-private-invocation-closure/v1',request_sha256=descriptor.public_id,
            candidate_sha256=PINS['candidate_sha256'],provider_source_sha256=PINS['provider_source_sha256'],
            natural_exit_zero=True,owned_processes_absent=not self.wrong_closure,private_view_retired=True,
            transport_sha256=e.sha(body))
        return body,closure
    def release_feature(self,handle):
        assert handle == self.active
        self.releases += 1; self.active=None
    def finish(self):
        assert self.active is None
        return {'generated_only':True,'calls':self.calls,'native_execution':False}
    def close(self):
        self.closed=True


def run():
    contexts = [dict(session_index=0,field_index=1,layer=layer,lag_index=20,lag_bins=0) for layer in (0,1)]
    return e.J.make_run(**PINS,condition='paper_data',working_limit=WORK,
                        generated_contexts=contexts,generated_requests=6)


def limits():
    return dict(working_bytes=WORK,cache_working_bytes=WORK,cache_read_bytes=1024**2,
        cache_payload_bytes=1024**2,cache_metadata_bytes=1024**2,cache_entries=10,bundle_bytes=65536,
        frozen_bundle_bytes=1024**2,dispatched_bundle_bytes=1024**2,packed_output_bytes=1024**2,
        authority_output_bytes=1024**2,authority_read_bytes=1024**2,packed_read_bytes=1024**2,
        receipt_output_bytes=1024**2,result_output_bytes=1024**2,wall_seconds=60)


def materialize(root):
    specs,items = fixture(root/'input')
    provider = Provider()
    receipt,pin = e.collect(Reader(root/'input',specs,items),provider,run(),root/'output',limits=limits())
    return specs,items,provider,receipt,pin


class ExecutionControls(unittest.TestCase):
    def test_complete_generated_cache_provider_durable_recovery_original_score(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root=Path(name); specs,items,provider,receipt,pin = materialize(root)
            self.assertEqual((provider.prepares,provider.calls,provider.releases),(2,6,2))
            self.assertTrue(provider.closed)
            self.assertEqual(receipt['frozen_bundle_bytes'],receipt['dispatched_bundle_bytes'])
            result,_ = e.recover(Reader(root/'input',specs,items),run(),root/'output',receipt,
                                 collection_sha256=pin['sha256'],limits=limits())
            self.assertEqual(result['authorities']['requests'],6)
            for item,score in zip(items,result['result']['generated_scores']):
                pred = item['time_indices'][:,None].astype('<f8')+np.arange(item['targets'].shape[1])[None,:]
                np.testing.assert_array_equal(score['correlations'],e.J.ORIGINAL.pooled_pearson(item['targets'],pred))
            self.assertIsNone(result['original_result_arrays'])
            self.assertFalse(result['scientific_qualification'])
            self.assertEqual(provider.calls,6)  # Recovery never calls provider again.
            self.assertEqual({p.name for p in (root/'output/authorities').iterdir()},{'META.bin','REQUESTS.bin'})

    def test_authority_corruption_refused_before_recovery_scores(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root=Path(name); specs,items,_,receipt,pin=materialize(root)
            path=root/'output/authorities/REQUESTS.bin'; path.chmod(0o600)
            body=bytearray(path.read_bytes()); body[-1]^=1; path.write_bytes(body); path.chmod(0o400)
            with self.assertRaisesRegex(ValueError,'authentication'):
                e.recover(Reader(root/'input',specs,items),run(),root/'output',receipt,
                          collection_sha256=pin['sha256'],limits=limits())
            self.assertFalse((root/'output/RECOVERY.json').exists())

    def test_changed_target_refused_even_with_valid_saved_authorities(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root=Path(name); specs,items,_,receipt,pin=materialize(root)
            altered=[dict(x) for x in items]
            altered[0]['targets']=items[0]['targets'].copy(); altered[0]['targets'][0,0]+=1
            with self.assertRaisesRegex(ValueError,'target bytes'):
                e.recover(Reader(root/'input',specs,altered),run(),root/'output',receipt,
                          collection_sha256=pin['sha256'],limits=limits())

    def test_provider_failure_retires_feature_and_keeps_partial_evidence(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root=Path(name); specs,items=fixture(root/'input'); provider=Provider(wrong_closure=True)
            with self.assertRaises(ValueError):
                e.collect(Reader(root/'input',specs,items),provider,run(),root/'output',limits=limits())
            self.assertTrue(provider.closed); self.assertEqual(provider.releases,1)
            self.assertTrue((root/'output/FAILURE.json').exists())
            self.assertFalse((root/'output/COLLECTION.json').exists())

    def test_whole_deadline_is_not_reset_for_each_query(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root=Path(name); specs,items=fixture(root/'input'); provider=Provider(); ticks=iter([0,0,0,0,0,0,61])
            with self.assertRaisesRegex(ValueError,'deadline'):
                e.collect(Reader(root/'input',specs,items),provider,run(),root/'output',limits=limits(),clock=lambda:next(ticks))
            self.assertTrue(provider.closed)
            self.assertFalse((root/'output/COLLECTION.json').exists())

    def test_cumulative_bundle_cap_fails_before_candidate_invocation(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root=Path(name); specs,items=fixture(root/'input'); provider=Provider(); cap=limits();cap['frozen_bundle_bytes']=1
            with self.assertRaisesRegex(ValueError,'Cumulative allocation'):
                e.collect(Reader(root/'input',specs,items),provider,run(),root/'output',limits=cap)
            self.assertEqual(provider.calls,0); self.assertTrue(provider.closed)

    def test_wrong_global_context_order_fails_before_provider(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root=Path(name); specs,items=fixture(root/'input'); provider=Provider()
            with self.assertRaisesRegex(ValueError,'Canonical original authority'):
                e.collect(Reader(root/'input',specs,list(reversed(items))),provider,run(),root/'output',limits=limits())
            self.assertEqual(provider.calls,0)

    def test_external_collection_digest_cannot_be_replaced_with_changed_receipt(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root=Path(name); specs,items,_,receipt,pin=materialize(root); changed=dict(receipt);changed['jobs']=1
            with self.assertRaisesRegex(ValueError,'collection receipt'):
                e.recover(Reader(root/'input',specs,items),run(),root/'output',changed,
                          collection_sha256=pin['sha256'],limits=limits())

    def test_undefined_correlations_are_saved_as_null_without_dropping_jobs(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root=Path(name); specs,items=fixture(root/'input')
            class Constant(Provider):
                def run_request(self,handle,raw,descriptor):
                    body,closure=super().run_request(handle,raw,descriptor)
                    shape=json.loads(descriptor.public_json)['prediction_shape']
                    out=io.BytesIO();np.save(out,np.ones(shape,dtype='<f8'),allow_pickle=False)
                    body=out.getvalue();closure['transport_sha256']=e.sha(body)
                    return body,closure
            receipt,pin=e.collect(Reader(root/'input',specs,items),Constant(),run(),root/'output',limits=limits())
            result,_=e.recover(Reader(root/'input',specs,items),run(),root/'output',receipt,
                              collection_sha256=pin['sha256'],limits=limits())
            self.assertEqual(len(result['result']['generated_scores']),2)
            self.assertTrue(all(v is None for row in result['result']['generated_scores'] for v in row['correlations']))

    def test_cleanup_attempts_all_owned_resources_after_first_failure(self):
        touched=[]
        class Bad:
            def close(self):touched.append('bad');raise OSError('generated close failure')
        class Good:
            def close(self):touched.append('good')
        with self.assertRaises(RuntimeError):e.close_owned(Bad(),Good())
        self.assertEqual(touched,['bad','good'])

    def test_authority_mutation_after_authentication_is_refused_before_frame_use(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root=Path(name); specs,items,_,receipt,_=materialize(root)
            reader=e.AuthorityReader(root/'output/authorities',run(),receipt['authorities'],
                receipt_sha256=e.sha(e.encoded(receipt['authorities'])),read_limit=1024**2,working_limit=WORK)
            try:
                path=root/'output/authorities/REQUESTS.bin';path.chmod(0o600);path.chmod(0o400)
                with self.assertRaisesRegex(ValueError,'identity unchanged'):
                    reader.next_job(qid=items[0]['qid'],time_indices=items[0]['time_indices'])
            finally:reader.close()

    def test_full_cli_refuses_scientific_scope_or_callback_substitution_before_loading(self):
        base={'schema':'language-full-original-execution-protocol/v1','scope':'original_full_reproduction',
              'source_pins':{'execution.py':e.sha((HERE/'execution.py').read_bytes()),'producer.py':'3'*64,'reader.py':'1'*64,'provider.py':'2'*64},
              'store_root':'/private/generated-source','store_sha256':'1'*64,'store_read_limit':1024**2,
              'store_working_limit':WORK,'schedule_sha256':'3'*64,
              'provider_config':{'store_sha256':'1'*64,'schedule_sha256':'3'*64,
                  'caps':{'max_jobs':58926,'max_requests':6776076,'working_bytes':WORK}},
              'provider_admission':{},'output_root':'/private/generated-output','provider_evidence_root':'/private/generated-provider',
              'limits':limits(),'operator_joint_admission_bytes':6*WORK,'permutation_budget':900000,
              'numpy_version':'generated','scipy_version':'generated'}
        self.assertEqual(cli.validate_protocol(base)['scope'],'original_full_reproduction')
        for fault in ('scope','callbacks','joint','source'):
            with self.subTest(fault=fault):
                value=json.loads(e.encoded(base))
                if fault=='scope':value['scope']='original_figure3b_population_improvement'
                if fault=='callbacks':value['provider_config']['caps']['max_requests']=5685
                if fault=='joint':value['operator_joint_admission_bytes']-=1
                if fault=='source':value['source_pins']['execution.py']='f'*64
                with patch.object(e,'load_pinned',side_effect=AssertionError('must refuse before source/native loading')) as load:
                    with self.assertRaises(ValueError):cli.run_protocol(value)
                    load.assert_not_called()

    def test_preparation_cli_refuses_unpinned_or_nonpreparation_admission_before_archive_access(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            path=Path(name)/'admission.json'
            raw=e.encoded({'schema':'language-original-store-preparation-admission/v1','model_execution':False,'native_execution':False})
            path.write_bytes(raw)
            self.assertEqual(prep.read_admission(path,e.sha(raw))[0],raw)
            with self.assertRaisesRegex(ValueError,'Exact stable'):prep.read_admission(path,'f'*64)
            bad=e.encoded({'schema':'language-original-store-preparation-admission/v1','model_execution':True,'native_execution':False})
            path.write_bytes(bad)
            with self.assertRaisesRegex(ValueError,'never a model'):prep.read_admission(path,e.sha(bad))

    def test_recovery_deadline_stops_before_more_scores_and_closes_store(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root=Path(name);specs,items,_,receipt,pin=materialize(root)
            reader=Reader(root/'input',specs,items);ticks=iter([0,0,0,61])
            with self.assertRaisesRegex(ValueError,'recovery deadline'):
                e.recover(reader,run(),root/'output',receipt,collection_sha256=pin['sha256'],
                          limits=limits(),clock=lambda:next(ticks))
            self.assertTrue(reader.closed)
            self.assertFalse((root/'output/RECOVERY.json').exists())

    def test_internal_authority_cleanup_attempts_both_streams_on_error(self):
        for cls in (e.AuthorityWriter,e.AuthorityReader):
            with self.subTest(kind=cls.__name__):
                events=[]
                class Broken:
                    closed=False
                    def close(self):events.append('broken');raise OSError('generated failure')
                class Good:
                    closed=False
                    def close(self):events.append('good');self.closed=True
                value=object.__new__(cls);value.root=Path('/unused-generated-authority')
                value.streams={'META.bin':Broken(),'REQUESTS.bin':Good()}
                with patch.object(e.os,'chmod'):
                    with self.assertRaises(RuntimeError):value.close()
                self.assertEqual(events,['broken','good'])

    def test_clean_reader_import_binds_producer_without_prior_global_alias(self):
        folder=HERE.parent/'original-store-producer-v1'
        pins={name:e.sha((folder/name).read_bytes()) for name in ('producer.py','reader.py')}
        prior=sys.modules.pop('producer',None)
        try:
            module=cli.load_reader(pins)
            self.assertTrue(hasattr(module,'StoreReader'))
            self.assertEqual(e.sha(Path(module.p.__file__).read_bytes()),pins['producer.py'])
            self.assertNotIn('producer',sys.modules)
        finally:
            if prior is not None:sys.modules['producer']=prior


if __name__ == '__main__':
    unittest.main()
