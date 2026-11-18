"""Generated metadata/operand controls only; no estimator, native or data run."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

HERE=Path(__file__).resolve().parent
TASK=Path(os.environ.get('LANGUAGE_TEST_TASK_HOME',str(HERE.parents[1])))


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
    return module


r=load('generated_executed_reference',HERE/'executed_reference.py')
p=load('generated_author_pairing',HERE/'paired.py')
entry_path=TASK/'implementations/original-exec-provider-v1/participant_entry.py'
endpoint_path=TASK/'implementations/original-figure3b-improvement-v1/improvement.py'
assert hashlib.sha256(entry_path.read_bytes()).hexdigest()=='530452d9b82b87fd395c9faf2496a7de2411c2ca3eb1b0053b21b8fd233de615'
assert hashlib.sha256(endpoint_path.read_bytes()).hexdigest()=='bbf81e3f3f8a82edfbeb8005de6b52d335e21d674e3798238a5f8a14555c3afa'
entry=load('generated_original_participant_entry',entry_path)
endpoint=load('generated_original_selected_endpoint',endpoint_path)


def h(value):return hashlib.sha256(str(value).encode()).hexdigest()


def record(path,identity):return {'path':path,'bytes':1,'sha256':h(identity),'mode':0o444}


def manifests():
    common=[record('paper.pdf','paper'),record('schema/data.json','data_schema')]
    code=[record('author/function_code.py','original_author')]
    recipe={'bytes':850,'sha256':h('literal_recipe')}
    result={};roles=[]
    for role in p.ROLES:
        condition='paper_data_author_code' if role=='executed_author_reference' else role
        cfg={'condition':condition,'caps':{'working_bytes':8*1024**2,'tree_read_bytes':10000},
             'provider_source_sha256':h('provider'),'bwrap':{'path':'/bin/bwrap','bytes':4,'sha256':h('ELF')},
             'python_path':'/usr/bin/python3','runtime':{'manifest_sha256':h('same-runtime')},
             'candidate':{'manifest_sha256':h(role)},'assistance':{'manifest_sha256':h(role+'assistance')}}
        roles.append({'role':role,'config':cfg})
        files=[] if role=='executed_author_reference' else common if role=='paper_data' else sorted(common+code,key=lambda v:v['path'])
        dirs=sorted({str(parent) for row in files for parent in Path(row['path']).parents if str(parent)!='.'})
        result[role]={
            'candidate':{'schema':'language-frozen-public-tree/v1','kind':'candidate','condition':condition,'directories':[],
                         'files':[dict(path='candidate.py',**recipe,mode=0o444)] if role=='executed_author_reference' else [record('candidate.py',role)]},
            'assistance':{'schema':'language-frozen-public-tree/v1','kind':'assistance','condition':condition,'directories':dirs,'files':files}}
    protocol={'roles':roles,'common_assets':common,'author_code_assets':code,'feedback':copy.deepcopy(p.FEEDBACK),'preflight_tree_read_limit':30000}
    return protocol,result,{'files':{'author_programme.py':recipe}}


def authority():
    return {'context':endpoint.contexts()[0],'coordinates':endpoint.coordinates()[0], 'rows':6,'outputs':1,
        'target_sha256':h('original-target'),'support_class_sha256':h('original-class'),
        'feature':{'bytes':1568,'sha256':h('feature'),'shape':[6,30]},'qid_sha256':h('qid'),'time_sha256':h('times'),
        'run_binding_sha256':h('programme-specific'),
        'requests':[{'held_f64le':struct.pack('<d',float(i)).hex(),'query_rows':2,
            'request_sha256':h('request'+str(i)),'bundle_sha256':h('bundle'+str(i)),'bundle_bytes':192} for i in (1,2,3)]}


def lifecycle_fixture():
    cfg={'candidate_sha256':h('candidate'),'provider_source_sha256':h('provider')}
    provider={'schema':'language-exec-provider-receipt/v1','mode':'exec_reset_bwrap_v1',
              'config_sha256':r.sha(r.encoded(cfg)),'admission':{'external':'generated'},'counters':{'max_requests':2}}
    rows=[{'event':'open','mode':'exec_reset_bwrap_v1','config_sha256':provider['config_sha256'],
           'admission':provider['admission'],'scientific_qualification':False}]
    requests=[];packed=[]
    for i,req in enumerate(authority()['requests'][:2]):
        requests.append((0,req,1568))
        close={'schema':'language-private-invocation-closure/v1','request_sha256':req['request_sha256'],
            'candidate_sha256':cfg['candidate_sha256'],'provider_source_sha256':cfg['provider_source_sha256'],
            'natural_exit_zero':True,'owned_processes_absent':True,'private_view_retired':True,'transport_sha256':h('transport'+str(i))}
        obs={'natural_exit_zero':True,'owned_processes_absent':True,'gate_joined_before_exec':True,'pidfd_owned':True,
             'cgroup_name':'language-'+format(i+1,'032x'),'cgroup_inode':100+i,'cgroup_device':12,'memory_events':{'oom_kill':0}}
        rows.extend([{'event':'start','request':i+1,'request_sha256':req['request_sha256'],'feature_bytes':1568,'bundle_bytes':192,'descriptor_bytes':1000},
                     {'event':'closed','request':i+1,'closure':close,'observation':obs}])
        packed.append((i,0,2,1,0,16,float(i+1),8,0,bytes.fromhex(req['request_sha256']),bytes.fromhex(close['transport_sha256']),bytes.fromhex(h('canonical')),bytes.fromhex(r.sha(r.encoded(close)))))
    before={'max_requests':2,'max_jobs':1,'journal_bytes':sum(len(r.encoded(row)) for row in rows)}
    rows.append({'event':'finish','counters_before_finish_record':before})
    provider['counters']={**before,'journal_bytes':sum(len(r.encoded(row)) for row in rows)}
    return rows,requests,packed,provider,cfg


def product(role,values):
    contexts=endpoint.contexts()
    jobs=[{'context':c,'lineage_sha256':h('same-job'+str(i)),'requests':136 if i<15 else 135} for i,c in enumerate(contexts)]
    value={'role':role,'information_condition':None if role=='executed_author_reference' else role,
           'store_sha256':h('store'),'schedule_sha256':h('schedule'),'source_support_sha256':h('support'),
           'jobs':jobs,'scores':[{'context':c,'pearson_r':v} for c,v in zip(contexts,values)],
           'collection':{'sha256':h('collection'+role)},'lifecycle':{'sha256':h('life'+role)},
           'invocation_groups':[role+'-generated-ownership']}
    # Explicit generated-only access to the private seal; no production recovery
    # or native qualification is claimed by these arithmetic tests.
    return r.Recovered(value,r._SEAL)


class PairingControls(unittest.TestCase):
    def test_permitted_operand_decoder_excludes_held_labels_and_returns_copies(self):
        x=np.arange(180,dtype=np.float64).reshape(6,30)
        stream=io.BytesIO();np.save(stream,x,allow_pickle=False);feature=stream.getvalue()
        q=np.array([1,1,2,2,3,3],dtype='<f8');times=np.arange(6,dtype='<i8')
        y=np.array([[10.],[11.],[30.],[31.]],dtype='<f8')
        bundle=entry.HEADER.pack(b'LCBNDL01',1,0,6,4,1,2.)+q.tobytes()+times.tobytes()+y.tobytes()
        context=dict(endpoint.contexts()[0],held_qid=2.)
        descriptor={'schema':'language-compact-selected-request/v1','context':context,
            'features':{'sha256':h('unused'),'bytes':len(feature),'format':'npy','dtype':'<f8','shape':[6,30],'fortran_order':False},
            'response_maps':{'schema':'language-permitted-response-maps-bundle/v1','sha256':r.sha(bundle),'bytes':len(bundle),'rows':6,'training_rows':4,'output_columns':1},
            'row_selection':'original-order:qids!=held(train);qids==held(query)','prediction_shape':[2,1]}
        descriptor['features']['sha256']=r.sha(feature)
        train_x,train_y,query_x,public=entry.operands(feature,bundle,entry.encoded(descriptor),byte_limit=4096,working_limit=1024**2)
        np.testing.assert_array_equal(train_x,x[[0,1,4,5]]);np.testing.assert_array_equal(query_x,x[[2,3]])
        np.testing.assert_array_equal(train_y,y);np.testing.assert_array_equal(public['train_qid'],[1,1,3,3])
        train_y[:]=-1;train_x[:]=-1
        self.assertEqual(r.sha(bundle),descriptor['response_maps']['sha256'])
        self.assertEqual(r.sha(feature),descriptor['features']['sha256'])

    def test_common_lineage_ignores_only_programme_and_changes_on_every_source_identity(self):
        original=authority();_,identity=r.common_lineage(original)
        other=copy.deepcopy(original);other['run_binding_sha256']=h('different programme')
        self.assertEqual(r.common_lineage(other)[1],identity)
        for field in ('context','coordinates','rows','outputs','target_sha256','support_class_sha256','feature','qid_sha256','time_sha256','requests'):
            changed=copy.deepcopy(original)
            if field=='requests':changed[field][0]['held_f64le']=struct.pack('<d',99.).hex()
            elif isinstance(changed[field],dict):changed[field]['changed']=True
            elif isinstance(changed[field],int):changed[field]+=1
            else:changed[field]=h('changed')
            with self.subTest(field=field):self.assertNotEqual(r.common_lineage(changed)[1],identity)

    def test_fresh_lifecycle_binds_packed_closures_and_transports(self):
        args=lifecycle_fixture()
        self.assertEqual(len(r.verify_lifecycle(*args,mode='exec_reset_bwrap_v1')),2)
        raw=b''.join(r.encoded(v) for v in args[0])
        self.assertEqual(r.lifecycle_records(raw,2),args[0])

    def test_fixed_reuse_and_bad_packed_join_are_rejected(self):
        for mutation in ('fixed_schema','closure_hash','transport_hash','wrong_job','duplicate_group','derived_close'):
            rows,requests,packed,provider,cfg=copy.deepcopy(lifecycle_fixture())
            if mutation=='fixed_schema':provider['schema']='language-fixed-time-provider/v1'
            elif mutation=='closure_hash':packed[0]=packed[0][:12]+(bytes.fromhex(h('wrong')),)
            elif mutation=='transport_hash':packed[0]=packed[0][:10]+(bytes.fromhex(h('wrong')),)+packed[0][11:]
            elif mutation=='wrong_job':packed[0]=(packed[0][0],9)+packed[0][2:]
            elif mutation=='duplicate_group':rows[4]['observation']['cgroup_name']=rows[2]['observation']['cgroup_name']
            else:rows[2]['closure']['closed_job_producer_sha256']=h('shared42worker')
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):r.verify_lifecycle(rows,requests,packed,provider,cfg,mode='exec_reset_bwrap_v1')

    def test_missing_failed_extra_or_unowned_closures_are_rejected(self):
        for mutation in ('missing','failed','suffix','gate','retired','oom'):
            rows,requests,packed,provider,cfg=copy.deepcopy(lifecycle_fixture())
            if mutation=='missing':rows.pop(2)
            elif mutation=='failed':rows[2]['event']='failed'
            elif mutation=='suffix':rows.append({'event':'finish'})
            elif mutation=='gate':rows[2]['observation']['gate_joined_before_exec']=False
            elif mutation=='retired':rows[2]['closure']['private_view_retired']=False
            else:rows[2]['observation']['memory_events']['oom_kill']=1
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):r.verify_lifecycle(rows,requests,packed,provider,cfg,mode='exec_reset_bwrap_v1')

    def test_exact_two_arm_exposure_and_private_reference(self):
        protocol,materials,source=manifests()
        self.assertTrue(p.validate_arm_manifests(protocol,materials,source))
        for mutation in ('code_in_A','extra_directory','changed_budget','baseline_extra','runtime'):
            pp,mm,ss=copy.deepcopy((protocol,materials,source))
            if mutation=='code_in_A':mm['paper_data']['assistance']['files']+=pp['author_code_assets']
            elif mutation=='extra_directory':mm['paper_data']['assistance']['directories'].append('target_hint')
            elif mutation=='changed_budget':pp['roles'][2]['config']['caps']['working_bytes']+=1
            elif mutation=='baseline_extra':mm['executed_author_reference']['candidate']['files'].append(record('other.py','extra'))
            else:pp['roles'][2]['config']['runtime']['manifest_sha256']=h('differentruntime')
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):p.validate_arm_manifests(pp,mm,ss)

    def test_all_role_material_preflight_precedes_any_collection_and_closes_descriptors(self):
        protocol,materials,_=manifests();calls=[];closed=[]
        class Meter:
            def __init__(self,caps):self.values={'tree_read_bytes':0}
        class Provider:
            @staticmethod
            def authenticate_tree(desc,kind,meter,working):
                calls.append((desc['manifest_sha256'],kind));meter.values['tree_read_bytes']+=1
                if kind=='candidate' and desc['manifest_sha256']==h('paper_data_author_code'):raise ValueError('Tampered third-role tree')
                doc={'condition':'generic','directories':['input','candidate','artifacts','executor','tmp','proc','dev'],
                     'files':[{'path':name,'bytes':0} for name in ('input/features.npy','input/responses.bin','input/request.json','executor/entry.py','usr/bin/python3')]} if kind=='runtime' else next(materials[role][kind] for role in p.ROLES if protocol['roles'][p.ROLES.index(role)]['config'][kind]==desc)
                return 100+len(calls),doc,None
            @staticmethod
            def read_owned(*args,**kwargs):return b'\x7fELF',None
        Provider.Meter=Meter
        with patch.object(p.os,'close',side_effect=closed.append),self.assertRaisesRegex(ValueError,'third-role'):
            p.preflight_trees(protocol,Provider,materials)
        self.assertEqual(len(calls),8)
        self.assertEqual(len(closed),7)
        # No provider construction, private StoreReader or collect function is
        # part of this preflight API; failures return before run_pair reaches them.

    def test_aggregate_and_role_substitution_are_refused(self):
        with self.assertRaises(ValueError):r.snapshot({'scores':[.1]*42})
        reference=product('executed_author_reference',[.1]*42)
        with self.assertRaises(ValueError):p.compare_products(reference,reference,r)
        candidate=product('paper_data',[.2]*42)
        changed=r.snapshot(candidate);changed['information_condition']='paper_data_author_code'
        with self.assertRaises(ValueError):p.compare_products(reference,r.Recovered(changed,r._SEAL),r)

    def test_same_census_with_changed_source_lineage_or_missing_job_is_refused(self):
        reference=product('executed_author_reference',[.1]*42)
        candidate=product('paper_data',[.2]*42)
        for mutation in ('target','feature','qid_time','held_rows','missing','order','reused_run'):
            value=r.snapshot(candidate)
            if mutation=='missing':value['jobs'].pop()
            elif mutation=='order':value['jobs'][0],value['jobs'][1]=value['jobs'][1],value['jobs'][0]
            elif mutation=='reused_run':value['collection']=r.snapshot(reference)['collection']
            else:value['jobs'][0]['lineage_sha256']=h(mutation)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):p.compare_products(reference,r.Recovered(value,r._SEAL),r)

    def test_nondyadic_reduction_exactly_matches_original_numeric_operations(self):
        author=[float(x) for x in np.linspace(-.987654321,.912345678,42)]
        candidate=[float(x) for x in np.nextafter(np.asarray(author),np.ones(42))]
        fresh=p.compare_products(product('executed_author_reference',author),product('paper_data',candidate),r)
        def original_packet(values,role):return {'schema':'language-original-figure3b-scores/v1','role':role,
            'selection_sha256':r.sha(endpoint.encoded(endpoint.selection())),'source_support_sha256':h('support'),
            'prediction_run_sha256':h(role),'scores':[{'context':c,'pearson_r':v} for c,v in zip(endpoint.contexts(),values)],'execution_qualified':False}
        old=endpoint.compare(original_packet(candidate,'candidate'),original_packet(author,'provided_author_reference'))
        self.assertEqual(fresh['equal_session_paired_mean_delta'],old['equal_session_paired_mean_delta'])
        self.assertEqual([x['paired_delta'] for x in fresh['sessions']],[x['paired_delta'] for x in old['sessions']])
        for actual,expected in zip(fresh['participants'],old['participants']):
            self.assertEqual(actual['contribution_to_equal_session_delta'],expected['contribution_to_equal_session_delta'])
            self.assertEqual(actual['leave_one_person_out_equal_remaining_session_delta'],expected['leave_one_person_out_equal_remaining_session_delta'])
        self.assertEqual(fresh['reference_role'],'executed_author_reference')

    def test_null_correlations_propagate_without_dropping_session(self):
        author=[.1]*42;candidate=[.2]*42;candidate[8]=None
        result=p.compare_products(product('executed_author_reference',author),product('paper_data',candidate),r)
        self.assertIsNone(result['equal_session_paired_mean_delta'])
        self.assertEqual(len(result['sessions']),14)
        self.assertIsNone(result['sessions'][2]['paired_delta'])
        self.assertFalse(result['scientific_qualification']);self.assertIsNone(result['binary_win'])

    def test_original_scope_or_reference_role_refusal_precedes_reader_access(self):
        class Engine:
            class J:
                ORIGINAL_SCOPE='original_figure3b_improvement'
                @staticmethod
                def _binding(run):return {'scope':'generated_engineering_control','jobs':42,'requests':5685}
        with self.assertRaisesRegex(ValueError,'original42/5685'):
            r.recover_executed(Engine,None,None,{}, {},'executed_author_reference',{},store_root='unused',output_root='unused',
                evidence_root='unused',store_limit=1,store_working=1,limits={},support_sha256=h('x'),extra_read_limit=1,working_limit=256*1024**2)

    def test_real_pinned_stack_import_then_missing_admission_refuses_before_execution(self):
        # Imports authenticated source only. No StoreReader, private array,
        # participant import or native backend can be reached with this shape.
        with self.assertRaisesRegex(ValueError,'Exact selected pairing protocol'):
            p.run_pair({'task_home':str(TASK)}, {}, r, {}, h('component'))

    def test_thin_entrypoint_role_order_with_generated_mocks_and_no_file_writes(self):
        protocol,materials,descriptor=manifests();events=[];output={}
        protocol.update(task_home='/generated-source',output_root='/generated-pair-output',store_root='/generated-store',
            store_sha256=h('store'),schedule_sha256=h('schedule'),source_support_sha256=h('support'),wall_seconds=60,
            extra_read_limit=1024**2,output_limit=1024**2,store_read_limit=1024**2,store_working_limit=1024**2,
            pairing_working_limit=256*1024**2,operator_joint_admission_bytes=1024**3,limits={'working_bytes':1024**2})
        for row in protocol['roles']:
            row['native_admission']={'generated':row['role']}
            row['config'].update(candidate_sha256=h(row['role']),provider_source_sha256=h('provider'))
            for kind in ('candidate','assistance'):row['config'][kind]['manifest']='/generated/'+row['role']+'/'+kind
        class Native:
            def __init__(self,config,admission,**kwargs):self.role=admission['generated'];events.append(('provider',self.role))
        class Backend:
            @staticmethod
            def require_platform():events.append(('platform','checked'))
        provider=types.SimpleNamespace(NativeProvider=Native,LinuxBackend=Backend)
        reader=types.SimpleNamespace(StoreReader=lambda *a,**k:object())
        engine=types.SimpleNamespace(J=types.SimpleNamespace(make_run=lambda **kw:kw),close_owned=lambda *args:None)
        def collect(reader,native,run,root,**kwargs):
            events.append(('collect',native.role))
            return {'provider':{'admission':{'generated':native.role}}},{'bytes':1,'sha256':h('collection'+native.role)}
        engine.collect=collect
        def recover(*args,**kwargs):
            role=args[5];events.append(('recover',role));return product(role,[.1 if role=='executed_author_reference' else .2]*42)
        def metadata(path,*args,**kwargs):
            _,_,role,kind=str(path).split('/');return r.encoded(materials[role][kind])
        class Sink(io.BytesIO):
            def __init__(self,name):super().__init__();self.name=name
            def close(self):output[self.name]=self.getvalue();super().close()
        def open_memory(path,*args,**kwargs):return Sink(path.name)
        with patch.object(r,'load_stack',return_value=(engine,reader,provider)),patch.object(p,'validate_protocol',side_effect=lambda pp,*a,**k:pp),\
             patch.object(r,'owned_bytes',side_effect=metadata),patch.object(p,'preflight_trees',side_effect=lambda *a:events.append(('preflight','all3')) or 0),\
             patch.object(r,'recover_executed',side_effect=recover),patch.object(Path,'stat',return_value=types.SimpleNamespace(st_size=1)),\
             patch.object(Path,'mkdir'),patch.object(Path,'open',open_memory):
            report=p.run_pair(protocol,{},r,descriptor,h('source'))
        self.assertEqual(events[0],('preflight','all3'))
        self.assertEqual([role for event,role in events if event=='collect'],list(p.ROLES))
        self.assertEqual([role for event,role in events if event=='recover'],list(p.ROLES))
        self.assertEqual(set(output),{role+'.json' for role in p.ROLES}|{'PAIR_RESULT.json'})
        self.assertEqual((report['jobs'],report['software_callbacks']),(126,17055))
        self.assertFalse(report['scientific_qualification'])


if __name__=='__main__':unittest.main()
