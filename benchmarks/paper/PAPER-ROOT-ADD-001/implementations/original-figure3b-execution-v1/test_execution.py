"""Generated selected-store→cache→provider-interface→original-score controls."""
import ast
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import execution as e
import run as cli
import reference as ref
import prepare as prep
WORK=64*1024**2
GROSS=0
CAP=1024**2


def load_fixture():
    path=HERE.parent/'original-figure3b-store-v1/test_store.py'
    spec=importlib.util.spec_from_file_location('_selected_execution_store_fixture',path)
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


def limits():
    return dict(working_bytes=WORK,cache_working_bytes=WORK,cache_read_bytes=8*1024**2,
        cache_payload_bytes=512*1024,cache_metadata_bytes=512*1024,cache_entries=32,bundle_bytes=65536,
        frozen_bundle_bytes=1024**2,dispatched_bundle_bytes=1024**2,packed_output_bytes=131072,
        authority_output_bytes=131072,authority_read_bytes=262144,packed_read_bytes=262144,
        receipt_output_bytes=131072,result_output_bytes=131072,wall_seconds=60)


class Provider:
    """Generated pure function; consumes only permitted public bundle, no child."""
    def __init__(self):self.calls=0;self.features=0;self.active=None;self.closed=False
    def prepare_feature(self,path,spec,*,rows):
        assert self.active is None
        assert type(spec) is dict
        self.features+=1;self.active=(str(path),spec['sha256'],rows);return self.active
    def run_request(self,handle,raw,descriptor):
        assert handle==self.active
        view=e.J.B.decode_bundle(raw,byte_limit=65536,working_limit=WORK)
        assert view.output_columns==1
        y=(view.time_indices[view.query_positions,None].astype('<f8')**2+3)
        stream=io.BytesIO();np.save(stream,y,allow_pickle=False);body=stream.getvalue();self.calls+=1
        return body,dict(schema='language-private-invocation-closure/v1',request_sha256=descriptor.public_id,
            candidate_sha256='2'*64,provider_source_sha256='4'*64,natural_exit_zero=True,
            owned_processes_absent=True,private_view_retired=True,transport_sha256=e.sha(body))
    def release_feature(self,handle):assert handle==self.active;self.active=None
    def finish(self):return {'generated_only':True,'calls':self.calls,'native_execution':False}
    def close(self):self.closed=True


def source_pins():
    paths={'execution.py':HERE/'execution.py','reference.py':HERE/'reference.py',
        'producer.py':HERE.parent/'original-figure3b-store-v1/producer.py',
        'reader.py':HERE.parent/'original-figure3b-store-v1/reader.py',
        'provider.py':HERE.parent/'original-exec-provider-v1/provider.py'}
    return {k:e.sha(p.read_bytes()) for k,p in paths.items()}


def protocol():
    return dict(schema='language-selected-figure3b-execution-protocol/v1',scope='original_figure3b_improvement',
        source_pins=source_pins(),store_root='/unused-input',store_sha256='1'*64,
        store_read_limit=32*1024**2,store_working_limit=256*1024**2,schedule_sha256='3'*64,
        provider_config={'store_sha256':'1'*64,'schedule_sha256':'3'*64,
            'caps':{'max_jobs':42,'max_requests':5685,'working_bytes':WORK}},provider_admission={},
        output_root='/unused-output',provider_evidence_root='/unused-provider',limits=limits(),
        operator_joint_admission_bytes=1024**3,numpy_version=np.__version__,reference_path='/unused-reference',
        reference_sha256=ref.REFERENCE_SHA,source_support_sha256=ref.CENSUS_SHA)


class Controls(unittest.TestCase):
    def test_composed_actual_generated_store_to_packed_rows_and_unchanged_original_scorer(self):
        global GROSS
        fixture=load_fixture();_,data,_,plan=fixture.fixture()
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root=Path(tmp);store_root=root/'store'
            out=fixture.s.prepare_generated(store_root,plan,{'p1_1':data},working_limit=256*1024**2,
                output_limit=256*1024,metadata_limit=512*1024)
            GROSS+=out['written_bytes'];self.assertLessEqual(GROSS,CAP)
            r=cli.load_reader(source_pins())
            def reader():return r.StoreReader(store_root,expected_store_sha256=out['store']['sha256'],
                read_limit=16*1024**2,working_limit=256*1024**2)
            run=e.J.make_run(store_sha256=out['store']['sha256'],candidate_sha256='2'*64,
                schedule_sha256='3'*64,provider_source_sha256='4'*64,condition='paper_data',working_limit=WORK,
                generated_contexts=list(e.J.ENDPOINT.coordinates()[:3]),
                generated_requests=out['metadata']['counts']['software_callbacks'])
            provider=Provider();collected,pin=e.collect(reader(),provider,run,root/'output',limits=limits())
            self.assertEqual(provider.features,3);self.assertEqual(provider.calls,out['metadata']['counts']['software_callbacks'])
            self.assertTrue(provider.closed)
            self.assertEqual(collected['frozen_bundle_bytes'],collected['dispatched_bundle_bytes'])
            # The very same generated store cannot be relabelled authentic.
            with self.assertRaisesRegex(ValueError,'Generated control'):
                e.recover(reader(),run,root/'output',collected,collection_sha256=pin['sha256'],limits=limits(),
                          source_support_sha256=ref.CENSUS_SHA)
            result,_=e.recover(reader(),run,root/'output',collected,collection_sha256=pin['sha256'],limits=limits())
            expected=list(fixture.s.iter_selected_jobs(data))
            for item,score in zip(expected,result['result']['generated_scores']):
                y=item['time_indices'][:,None].astype('<f8')**2+3
                np.testing.assert_equal(score['correlations'],e.J.ORIGINAL.pooled_pearson(item['y'],y))
            self.assertNotIn('candidate_scores',result['result']);self.assertIsNone(result['original_result_arrays'])
            self.assertFalse(result['scientific_qualification'])
            self.assertEqual(provider.calls,collected['software_callbacks'])
            GROSS+=sum(p.stat().st_size for p in (root/'output').rglob('*') if p.is_file())
            self.assertLessEqual(GROSS,CAP)

    def test_selected_cli_refuses_full_scope_count_support_or_runtime_changes(self):
        self.assertEqual(cli.validate_protocol(protocol())['scope'],'original_figure3b_improvement')
        for edit in ('scope','requests','support','runtime','joint'):
            p=protocol()
            if edit=='scope':p['scope']='original_full_reproduction'
            elif edit=='requests':p['provider_config']['caps']['max_requests']=6776076
            elif edit=='support':p['source_support_sha256']='0'*64
            elif edit=='runtime':p['numpy_version']='unknown'
            else:p['operator_joint_admission_bytes']=1
            with self.assertRaises(ValueError):cli.validate_protocol(p)

    def test_reference_adapter_preserves42_saved_values_order_and_has_no_execution_claim(self):
        values=[-.2+i/100. for i in range(42)]
        obj={'schema':'language_original_figure3_reduction_v1','sessions':list(ref.endpoint.SESSIONS),
            'participants':8,'released_fr_matrix_unit_columns':567,
            'source_permutation_observations':{'population':values}}
        packet=ref._packet_from_saved_reference(obj)
        self.assertEqual([v['pearson_r'] for v in packet['scores']],values)
        self.assertEqual([v['context'] for v in packet['scores']],list(e.J.ENDPOINT.contexts()))
        self.assertFalse(packet['execution_qualified'])
        self.assertEqual(packet['prediction_run_sha256'],ref.REFERENCE_SHA)
        obj['source_permutation_observations']['population']=values[:-1]
        with self.assertRaises(ValueError):ref._packet_from_saved_reference(obj)
        with patch.object(ref,'parse',side_effect=AssertionError('unverified reference parsed')):
            with self.assertRaises(ValueError):ref.packet_from_bytes(b'{}')

    def test_original_row_authority_and_collection_machinery_unchanged(self):
        old=ast.parse((HERE.parent/'original-task-execution-v1/execution.py').read_text())
        new=ast.parse((HERE/'execution.py').read_text())
        for name in ('AuthorityWriter','AuthorityReader','collect','limits_snapshot','close_owned'):
            a=next(n for n in old.body if getattr(n,'name',None)==name)
            b=next(n for n in new.body if getattr(n,'name',None)==name)
            self.assertEqual(ast.dump(a,include_attributes=False),ast.dump(b,include_attributes=False))

    def test_selected_preparation_cli_refuses_full_or_model_admission(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            path=Path(tmp)/'admission.json'
            for scope in ('language-original-store-preparation-admission/v1','language-figure3b-store-preparation-admission/v1'):
                value={'schema':scope,'model_execution':scope.endswith('figure3b-store-preparation-admission/v1'),'native_execution':False}
                raw=e.encoded(value);path.write_bytes(raw)
                with self.assertRaises(ValueError):prep.read_admission(path,e.sha(raw))

    def test_unqualified_provider_refuses_before_selected_source_store(self):
        p=protocol()
        class FakeProviderModule:
            @staticmethod
            def config_snapshot(value):return dict(value,provider_source_sha256='4'*64)
            @staticmethod
            def identity():return '4'*64
            @staticmethod
            def NativeProvider(*args,**kwargs):raise ValueError('Unqualified explicit provider')
        class FakeReader:
            @staticmethod
            def StoreReader(*args,**kwargs):raise AssertionError('Source store opened before provider admission')
        with patch.object(cli,'load_reader',return_value=FakeReader),patch.object(e,'load_pinned',return_value=FakeProviderModule),patch.object(ref,'load',return_value={}):
            with self.assertRaisesRegex(ValueError,'Unqualified'):cli.run_protocol(p)

    def test_recovery_closes_its_reader_even_when_admission_fails(self):
        class R:
            closed=False
            def close(self):self.closed=True
        reader=R()
        with self.assertRaises(ValueError):
            e.recover(reader,None,'/unused',{},collection_sha256='0'*64,limits={})
        self.assertTrue(reader.closed)

    def test_complete42_controlled_recovery_branch_emits14_deltas8_people_without_win(self):
        # Synthetic authorities exercise the production accumulator branch only.
        # Mocked authenticated readers do not prove source or OS qualification.
        path=HERE.parent/'original-figure3b-scoring-join-v1/test_join.py'
        spec=importlib.util.spec_from_file_location('_selected_execution_join_fixture',path)
        fixture=importlib.util.module_from_spec(spec)
        prior=sys.modules.get('join');sys.modules['join']=e.J
        try:spec.loader.exec_module(fixture)
        finally:
            if prior is None:sys.modules.pop('join',None)
            else:sys.modules['join']=prior
        run=fixture.run(True);plans=[];items=[]
        for i,context in enumerate(e.J.ENDPOINT.contexts()):
            job,y,_=fixture.frozen(run,context,136 if i<15 else 135)
            a=e.J.P.parse(job.authority_json);plans.append(job)
            items.append({'context':context,'qid':np.frombuffer(job.qid_bytes,dtype='<f8'),
                'time_indices':np.frombuffer(job.time_bytes,dtype='<i8'),'target_sha256':a['target_sha256'],
                'support_class_sha256':a['support_class_sha256'],'feature':a['feature'],'targets':y})
        class Session:
            def __init__(self,values):self.values=values
            def iter_jobs(self,**kwargs):yield from self.values
            def close(self):pass
        class Reader:
            store_sha256='1'*64;scope=e.J.ORIGINAL_SCOPE
            metadata={'preserved_metadata':{'CENSUS.json':{'sha256':ref.CENSUS_SHA}}}
            def iter_sessions(self):
                for i in range(14):yield Session(items[3*i:3*i+3])
            def close(self):pass
        class Authorities:
            def __init__(self,*a,**kw):self.index=0
            def next_job(self,**kw):
                value=plans[self.index];self.index+=1;return value
            def finish(self):return {'jobs':self.index,'generated_reader':True}
            def close(self):pass
        class Packed:
            def __init__(self,*a,**kw):self.index=0
            def score_job(self,job,target):
                context=e.J.P.parse(job.authority_json)['context'];self.index+=1
                return {'context':context,'correlations':np.array([.3],dtype='<f8')}
            def finish(self):return {'jobs':self.index,'generated_reader':True}
            def close(self):pass
        reference=ref._packet_from_saved_reference({'schema':'language_original_figure3_reduction_v1',
            'sessions':list(ref.endpoint.SESSIONS),'participants':8,'released_fr_matrix_unit_columns':567,
            'source_permutation_observations':{'population':[.1]*42}})
        collected={'schema':'language-original-task-collection/v1','scope':e.J.ORIGINAL_SCOPE,
            'jobs':42,'software_callbacks':5685,'run_binding_sha256':e.sha(run.binding_json),'authorities':{},'join':{}}
        with tempfile.TemporaryDirectory(dir=HERE) as tmp,patch.object(e,'AuthorityReader',Authorities),patch.object(e.J,'CompactReader',Packed):
            result,_=e.recover(Reader(),run,tmp,collected,collection_sha256=e.sha(e.encoded(collected)),
                limits=limits(),source_support_sha256=ref.CENSUS_SHA,reference=reference,
                reference_sha256=e.sha(e.encoded(reference)))
            value=result['result']['paired_difference']
            self.assertEqual(len(value['sessions']),14);self.assertEqual(len(value['participants']),8)
            self.assertAlmostEqual(value['equal_session_paired_mean_delta'],.2)
            self.assertIsNone(value['binary_win']);self.assertFalse(value['scientific_qualification'])

    def test_verified_loader_executes_authenticated_bytes_without_reopening_source(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root=Path(tmp);(root/'dependency').mkdir();path=root/'dependency/code.py'
            raw=b'value=7\n';path.write_bytes(raw);original=e.read_source
            def changed_after_authentication(p,digest,cap=262144):
                value=original(p,digest,cap);path.write_bytes(b'raise AssertionError("reopened source")\n');return value
            with patch.object(e,'HERE',root/'operator'),patch.object(e,'read_source',side_effect=changed_after_authentication):
                module=e.load_pinned('_selected_verified_bytes_control','dependency','code.py',e.sha(raw))
            self.assertEqual(module.value,7);sys.modules.pop(module.__name__,None)

    def test_source_reader_rejects_oversize_or_symlink_before_payload_read(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root=Path(tmp);path=root/'source.py';path.write_bytes(b'value=7\n')
            with self.assertRaisesRegex(ValueError,'before allocation'):e.read_source(path,e.sha(path.read_bytes()),cap=4)
            link=root/'alias.py';link.symlink_to(path)
            with self.assertRaisesRegex(ValueError,'symlink'):e.read_source(link,e.sha(path.read_bytes()))
            with self.assertRaisesRegex(ValueError,'symlink'):prep.read_source(link,e.sha(path.read_bytes()))


if __name__=='__main__':
    try:unittest.main(verbosity=2)
    finally:print({'generated_physical_bytes':GROSS,'gross_cap':CAP,'native_runs':0,'authentic_array_reads':0,'models_fitted':0})
