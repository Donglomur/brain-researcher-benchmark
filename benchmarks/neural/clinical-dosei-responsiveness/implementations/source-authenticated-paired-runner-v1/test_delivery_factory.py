"""Focused generated factory boundaries; no Docker, signal files or models.

The real immutable PairedCaseDelivery and pure packet validator are used.
Projection, rendering, backend construction and durable custody are explicit
fakes. Constructor population is complete7345/171; delivered test scope is one
case per scenario. The parent owns the one full integrated fictional run.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import types
import unittest

HERE=Path(__file__).resolve().parent
SOURCE_SHA256='e8cc730de704138f095e319fc4a812bdbcec5f68a2037630665309f776359fce'

def load(name,path,pin):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin:raise AssertionError('source pin mismatch')
    module=types.ModuleType(name);module.__file__=str(path);sys.modules[name]=module
    exec(compile(raw,str(path),'exec'),module.__dict__);return module

m=load('generated_delivery_factory',HERE/'delivery_factory.py',SOURCE_SHA256)
delivery=load('generated_factory_host',HERE.parent/'source-paired-delivery-v1/host_projection.py',
    '35d71ffef64415fc89f7828a4377ef6516eccb0fd32e8fcad1b929f494891dd2')
real_viewer=load('generated_factory_viewer',HERE.parent/'source-signal-viewer-v1/trace_viewer.py',
    'c65b111c76fea971963dab4ecab0850171fb10802ba1e9dc45f7b91bd1d9db79')
owned=load('generated_factory_owned',HERE.parent/'source-runtime-adapters-v1/owned_process_v2.py',
    m.OWNED_PROCESS_SHA256)

def packet(case_id):
    return {'schema':'dosei_paired_observation_v1','condition':'native_marker_relative_30s_v1',
        'case_id':case_id,'channels':['Intellivue/EEG_1','Intellivue/EEG_2'],'units':'microvolt',
        'interval_ms':[-30000,0],'relative_time_ms':[-8,-4],
        'values_uv':[[1.0,None],[-2.0,187.5]],'observation_mask':[[True,False],[True,True]],
        'source_endpoint_mask':[[False,False],[False,True]],
        'coverage':{'source_prefix_missing_ms':29992,'full_interval_recorded':False,'row_count':2}}

class Fixture:
    def __init__(self):
        self.manifest=[];self.indices={};self.receipts={};self.contexts=[]
        self.originals=[];self.projections=[];self.viewers=[];self.code_backends=[]
        self.project_mutation=None;self.bad_observation=False;self.constructor_error=None
        self.code_close_error=None;self.sink_error_kind=None
        for n in range(m.CASES):
            case_id=format(n+1,'064x');rid=str(n%m.RECORDINGS+1);row=n//m.RECORDINGS
            self.manifest.append({'case_id':case_id,'observation_sha256':m.binding(m.canonical(packet(case_id)))['sha256']})
            self.indices[case_id]={'schema':'dosei_private_window_index_v1','visibility':'evaluator_private',
                'case_id':case_id,'evaluator':{'case_id':case_id,'recording_id':rid,'source_row':row,
                    'source_event_id':f'recording:{rid}/row:{row}','moaas_grouped_ordinal':None,
                    'biological_person_id':None,'private_only_canary':'DO_NOT_EXPORT'}}
            self.receipts[rid]={'schema':'dosei_full_eeg_member_success_v1','status':'succeeded',
                'recording_id':rid,'complete_source_EOF_CRC_SHA':True,
                'all_three_streams_closed_and_size_stat_checked':True,'private_path':'/generated/private/source'}
            self.contexts.append(hashlib.sha256(('context/'+case_id).encode()).hexdigest())
        fixture=self
        class Viewer:
            def __init__(self,p,profile):
                self.packet=copy.deepcopy(p);self.profile=copy.deepcopy(profile);self.gain=187.5
                fixture.viewers.append(self)
            def action(self,command):
                if command['action']=='gain':self.gain=command['limit_uv']
                return m.canonical({'rendered_gain':self.gain}),{'observation_sha256':self.profile['observation_sha256']}
        self.viewer_module=types.SimpleNamespace(TraceViewer=Viewer,validate_packet=real_viewer.validate_packet)
        class Code:
            def __init__(self,options):
                self.options=options;self.closed=False;self.closes=0;self.tools=[]
            def code_observation(self):
                if self.closed:raise RuntimeError('closed generated backend')
                return b'wrong' if fixture.bad_observation else self.options['observation_bytes']
            def viewer_action(self,command):return self.options['viewer'](command)
            def run_tool(self,name,program):
                if self.closed:raise RuntimeError('closed generated backend')
                self.tools.append((name,program));return {'status':'ok','text':'fictional result'}
            def close(self):
                self.closes+=1;self.closed=True
                if fixture.code_close_error is not None:raise fixture.code_close_error
                raw=m.canonical({'schema':'fictional_code_close','complete':True,
                    'context_id':self.options['context_id']})
                return fixture.sink('code_close',raw)
        self.Code=Code
    def sink(self,kind,raw):
        if kind==self.sink_error_kind:raise OSError('generated custody failure')
        assert type(raw) is bytes
        self.originals.append((kind,raw));return m.binding(raw)
    def project(self,index,receipt,**options):
        self.projections.append((index['case_id'],receipt['recording_id']))
        p=packet(index['case_id']);raw=m.canonical(p)
        evidence={'schema':'dosei_host_slice_projection_receipt_v1','visibility':'evaluator_private',
            'case_id':p['case_id'],'observation_sha256':m.binding(raw)['sha256'],'observation_bytes':len(raw),
            'source_rows_read':2,'array_identity_binding_sha256':'a'*64,
            'read_counters_before':{'logical_array_read_bytes':0},
            'read_counters_after':{'logical_array_read_bytes':52},
            'private_projection_canary':'DO_NOT_EXPORT'}
        if self.project_mutation:self.project_mutation(p,evidence)
        return p,evidence
    def code_factory(self,**options):
        if self.constructor_error is not None:raise self.constructor_error
        result=self.Code(options);self.code_backends.append(result);return result
    def kwargs(self):
        return {'public_manifest':self.manifest,'private_indices':self.indices,'member_receipts':self.receipts,
            'project_case':self.project,'projection_options':{},'delivery_module':delivery,
            'viewer_module':self.viewer_module,'code_backend_factory':self.code_factory,
            'code_options':{'profile_bytes':b'{}','staging_parent':'/generated/staging',
                'docker_executable':'/generated/docker','docker_socket':'/generated/socket',
                'policy_api':types.SimpleNamespace(),'command_api':types.SimpleNamespace(),
                'call_wall_seconds':30,'max_calls':2},'context_ids':self.contexts,
            'owned_process_v2':owned,'owned_process_sha256':m.OWNED_PROCESS_SHA256,'evidence_sink':self.sink}
    def factory(self):return m.OrderedDeliveryFactory(**self.kwargs())

class FactoryControls(unittest.TestCase):
    def test_complete_preflight_order_and_owned_version(self):
        f=Fixture()
        for change in ('duplicate_join','missing_case','public_order','wrong_owned','override_process'):
            kw=f.kwargs()
            if change=='duplicate_join':
                kw['private_indices']=dict(f.indices)
                last=f.manifest[-1]['case_id'];first=f.manifest[0]['case_id']
                kw['private_indices'][last]=copy.deepcopy(f.indices[last])
                e=kw['private_indices'][last]['evaluator'];e.update(recording_id='1',source_row=0,source_event_id='recording:1/row:0')
            elif change=='missing_case':
                kw['private_indices']=dict(f.indices);kw['private_indices'].pop(f.manifest[-1]['case_id'])
            elif change=='public_order':kw['public_manifest']=list(reversed(f.manifest))
            elif change=='wrong_owned':kw['owned_process_sha256']='0'*64
            else:kw['code_options']=dict(kw['code_options'],process_api=owned)
            with self.subTest(change=change),self.assertRaises(m.DeliveryFactoryRefusal):
                m.OrderedDeliveryFactory(**kw)
        self.assertEqual(f.projections,[]);self.assertEqual(f.originals,[]);self.assertEqual(f.code_backends,[])
        factory=f.factory()
        with self.assertRaises(m.DeliveryFactoryRefusal):factory(f.manifest[0],'code_enabled')
        self.assertTrue(factory.summary()['poisoned'])
        with self.assertRaises(m.DeliveryFactoryRefusal):factory(f.manifest[0],'viewer_only')
        factory.close()

    def test_once_projection_two_fresh_states_and_closed_capabilities(self):
        f=Fixture();factory=f.factory();public=f.manifest[0]
        first=factory(dict(public),'viewer_only')
        self.assertEqual(set(first),{'backend','common_disclosure','source_evidence'})
        first['backend'].viewer_action({'action':'gain','limit_uv':50})
        ref=first['backend'].close();self.assertEqual(first['backend'].close(),ref)
        with self.assertRaises(m.DeliveryFactoryRefusal):first['backend'].viewer_action({'action':'view'})
        with self.assertRaises(m.DeliveryFactoryRefusal):first['backend'].code_observation()
        second=factory(dict(public),'code_enabled')
        self.assertEqual(first['common_disclosure'],second['common_disclosure'])
        self.assertEqual(first['source_evidence'],second['source_evidence'])
        self.assertEqual(f.projections,[(public['case_id'],'1')])
        self.assertEqual([x.gain for x in f.viewers],[50,187.5])
        raw=second['backend'].code_observation()
        self.assertEqual(m.binding(raw)['sha256'],public['observation_sha256'])
        for token in (b'DO_NOT_EXPORT',b'recording_id',b'private_path',b'moaas_grouped_ordinal'):
            self.assertNotIn(token,raw);self.assertNotIn(token,first['common_disclosure'])
        code=f.code_backends[0]
        self.assertIs(code.options['process_api'],owned)
        self.assertEqual(code.options['context_id'],f.contexts[0])
        second['backend'].run_tool('python','print(1)')
        second['backend'].close()
        self.assertEqual(code.closes,1)
        for method,args in ((second['backend'].viewer_action,({'action':'view'},)),
            (second['backend'].code_observation,()),(second['backend'].run_tool,('python','print(2)'))):
            with self.assertRaises(m.DeliveryFactoryRefusal):method(*args)
        summary=factory.summary()
        self.assertEqual((summary['completed_cases'],summary['projected_cases'],summary['viewer_instances'],
            summary['facade_closures']),(1,1,2,2))
        self.assertTrue(summary['cache_empty']);self.assertFalse(summary['active_backend'])
        close=factory.close();self.assertEqual(factory.close(),close)
        self.assertTrue(factory.summary()['closed']);self.assertFalse(factory.summary()['all_cases_completed'])

    def test_returned_object_setup_cleanup_and_original_interruption(self):
        for fault in ('wrong_observation','setup_custody','constructor_interrupt','cleanup_interrupt'):
            f=Fixture();factory=f.factory();public=f.manifest[0]
            factory(public,'viewer_only')['backend'].close()
            if fault in ('wrong_observation','cleanup_interrupt'):f.bad_observation=True
            if fault=='setup_custody':f.sink_error_kind='paired_delivery_setup'
            if fault=='constructor_interrupt':f.constructor_error=KeyboardInterrupt('generated constructor')
            if fault=='cleanup_interrupt':f.code_close_error=KeyboardInterrupt('generated cleanup')
            wanted=KeyboardInterrupt if fault.endswith('interrupt') else (m.DeliveryFactoryRefusal,OSError)
            with self.subTest(fault=fault),self.assertRaises(wanted):
                factory(public,'code_enabled')
            self.assertTrue(factory.summary()['poisoned']);self.assertTrue(factory.summary()['cache_empty'])
            if f.code_backends:self.assertEqual(f.code_backends[0].closes,1)
            failures=[json.loads(raw) for kind,raw in f.originals if kind=='paired_delivery_setup_failure']
            self.assertTrue(failures)
            if fault in ('constructor_interrupt','cleanup_interrupt'):self.assertFalse(failures[-1]['cleanup_complete'])
            with self.assertRaises(m.DeliveryFactoryRefusal):factory(public,'code_enabled')
            if fault in ('constructor_interrupt','cleanup_interrupt'):
                self.assertTrue(factory.summary()['setup_cleanup_unconfirmed'])
                with self.assertRaises(m.DeliveryFactoryRefusal):factory.close()
                with self.assertRaises(m.DeliveryFactoryRefusal):factory.close()
            else:factory.close()

if __name__=='__main__':unittest.main()
