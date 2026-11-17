"""Generated full-panel source controls. Never opens provisioned scientific inputs."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import common,run,grade,worker,grade_export
from transport import provider
from transport.engine import LABEL
sys.path.insert(0,str(common.VENDOR));sys.path.insert(0,str(HERE/'original'))
import candidate,held_scorer,io_support,packet,controls
import numpy as np

WRITES=0
def write(path,body):
    global WRITES
    path.write_bytes(body);WRITES+=len(body);return common.pin(body)
ORIGINAL_PUBLISH=common.publish
def counted_publish(path,body,mode=0o400):
    global WRITES
    value=ORIGINAL_PUBLISH(path,body,mode);WRITES+=len(body);return value
ORIGINAL_OUTPUT=io_support.output
def counted_output(root,name,body,cap):
    global WRITES
    value=ORIGINAL_OUTPUT(root,name,body,cap);WRITES+=len(body);return value

def load(name,file):
    spec=importlib.util.spec_from_file_location(name,file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
original_project=load('original_project',HERE/'original/project.py')
original_grade=load('original_grade',HERE/'original/grade.py')

def synthetic():
    rows=[{'id':f'{i:024x}','mode':'passive' if i<40 else 'active','direction':45*(i%8)} for i in range(92)]
    ids=np.array([r['id'] for r in rows],dtype='<U24')
    active={'ids':np.array([f'{i+1000:024x}' for i in range(141)],dtype='<U24'),
            'counts':np.zeros((141,390),dtype='<i8'),'velocity':np.zeros((141,2),dtype='<f8'),
            'source_rows':np.arange(141,dtype='<i8'),'directions':np.arange(141,dtype='<i8')%8*45}
    query={'ids':ids,'counts':np.zeros((92,390),dtype='<i8'),'directions':np.array([r['direction'] for r in rows],dtype='<i8'),
           'modes':np.array([r['mode'] for r in rows],dtype='<U7')}
    target={'ids':ids,'velocity':np.zeros((92,2),dtype='<f8')}
    refs={'ids':ids,**{m:np.zeros((92,2),dtype='<f8') for m in candidate.METHODS}}
    truth=[{'id':r['id'],'velocity':[0.,0.]} for r in rows]
    expected=held_scorer.score(rows,truth,{m:truth for m in candidate.METHODS})
    values={'active':active,'query':query,'target':target,'references':refs}
    public={'schema':'neural022_public_cases_v1','cases':rows}
    predictions={'schema':candidate.SCHEMA,'predictions':truth}
    return values,public,predictions,expected


class Delivery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='neural022-generated-');cls.root=Path(cls.temp.name).resolve()
        cls.values,cls.public,cls.predictions,expected=synthetic()
        cls.contract=common.contract();cls.contract['expected_fixed_reference']=expected
        cls.source_pin=common.pin(common.capture(HERE/'SOURCE.json',65536))
        cls.contract_pin=common.pin(common.encoded(cls.contract));cls.packet=cls.root/'projected';cls.packet.mkdir()
        inputs={}
        receipt={'status':'complete_private_projection_and62fit_reference','all_predictions_committed_before_private_grade':True,
                 'qualified_ridge_fits':62,'predictions':644,'files':{}}
        for key,value in cls.values.items():
            raw=io_support.encoded_npz(value);item=cls.contract['saved_inputs'][key];item['pin']=common.pin(raw)
            receipt['files'][item['original_filename']]=item['pin'];inputs['/input/'+item['mount_name']]=raw
        raw=common.encoded(receipt);cls.contract['closed_worker_receipt']=common.pin(raw);inputs['/input/receipt.json']=raw
        cls.contract_pin=common.pin(common.encoded(cls.contract))
        task=(HERE/'original/TASK.md').read_bytes();inputs[str(HERE/'original/TASK.md')]=task
        def take(path,identity,cap):
            raw=inputs[str(path)];assert common.pin(raw)==identity and len(raw)<=cap;return raw
        args=['project','--contract',str(HERE/'original/CONTRACT.json'),'--contract-sha256',cls.contract_pin['sha256'],'--out',str(cls.packet)]
        with patch.object(sys,'argv',args),patch.object(io_support,'source_contract',return_value=(cls.contract,cls.contract_pin)),\
             patch.object(io_support,'capture',side_effect=take),patch.object(io_support,'output',side_effect=counted_output),contextlib.redirect_stdout(io.StringIO()):
            cls.project_exit=original_project.main()
        cls.files={p.name:common.pin(p.read_bytes()) for p in cls.packet.iterdir()}

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=self.root);self.out=Path(self.temp.name)
        self.patches=[patch.object(m,'publish',side_effect=counted_publish) for m in (common,run,grade)]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def test_original_complete_projection(self):
        self.assertEqual(self.project_exit,0)
        receipt=common.decode((self.packet/'receipt.json').read_bytes())
        self.assertEqual(receipt['generated_checks']['count'],34)
        self.assertEqual((receipt['public_training_rows'],receipt['public_query_rows']),(141,92))
        with np.load(self.packet/'training.npz',allow_pickle=False) as p:
            self.assertEqual(p['counts'].shape,(141,390));self.assertNotIn('source_rows',p.files)
        with np.load(self.packet/'queries.npz',allow_pickle=False) as p:
            self.assertEqual(p['counts'].shape,(92,390));self.assertNotIn('velocity',p.files)

    def test_original_full_grade_and_seven_comparisons(self):
        prediction=common.encoded(self.predictions)
        inputs={'schema':'neural022_finite_grade_inputs_v1','source_contract':self.contract_pin,
                'packet_receipt':self.files['receipt.json'],'candidate':common.pin(prediction),
                'candidate_resources_absent':True,'prediction_commit_before_private_grade':True}
        path=self.out/'INPUTS.json';identity=write(path,common.encoded(inputs))
        bodies={str(path):path.read_bytes(),'/packet/receipt.json':(self.packet/'receipt.json').read_bytes(),
                '/public/cases.json':(self.packet/'cases.json').read_bytes(),'/submission/predictions.json':prediction,
                '/private/reference.npz':(self.packet/'reference.private.npz').read_bytes()}
        def take(path,identity,cap):
            raw=bodies[str(path)];self.assertEqual(common.pin(raw),identity);self.assertLessEqual(len(raw),cap);return raw
        args=['grade','--contract','/source/CONTRACT.json','--contract-sha256',self.contract_pin['sha256'],
              '--inputs',str(path),'--inputs-sha256',identity['sha256'],'--out',str(self.out)]
        with patch.object(sys,'argv',args),patch.object(io_support,'source_contract',return_value=(self.contract,self.contract_pin)),\
             patch.object(io_support,'capture',side_effect=take),patch.object(io_support,'output',side_effect=counted_output),contextlib.redirect_stdout(io.StringIO()):
            original_grade.main()
        result=common.decode((self.out/'score.json').read_bytes())
        self.assertEqual(result['submission_rows'],92);self.assertEqual(result['primary_score'],0)
        self.assertEqual(set(result['metrics']['passive']['candidate_minus_fixed_reference']),set(candidate.METHODS))
        self.assertEqual(len(result['direction_strata']),16)

    def test_public_rejections_and_valid(self):
        self.assertIsNone(run.admit_public(common.encoded(self.predictions),common.encoded(self.public)))
        for mutate in ('missing','reverse','duplicate','bool','extra'):
            v=copy.deepcopy(self.predictions)
            if mutate=='missing':v['predictions'].pop()
            if mutate=='reverse':v['predictions'].reverse()
            if mutate=='duplicate':v['predictions'][-1]['id']=v['predictions'][0]['id']
            if mutate=='bool':v['predictions'][-1]['velocity'][0]=True
            if mutate=='extra':v['predictions'][-1]['hidden']=0
            result=run.admit_public(common.encoded(v),common.encoded(self.public))
            self.assertEqual(result['status'],'invalid_submission');self.assertEqual(result['private_target_loads'],0)

    def test_bad_operator_cases_fail(self):
        cases=copy.deepcopy(self.public);cases['cases'].pop()
        with self.assertRaises(ValueError):run.admit_public(common.encoded(self.predictions),common.encoded(cases))

    def test_invalid_last_never_touches_private(self):
        v=copy.deepcopy(self.predictions);v['predictions'].pop()
        self.complete(v,False)

    def test_valid_complete_dispatches_only_after_commit(self):self.complete(self.predictions,True)

    def complete(self,predictions,valid):
        packet={'files':self.files};root=self.packet
        programme=self.out/'program.py';program_pin=write(programme,b'# generated inert programme\n')
        producer=self.out/'capture';producer.mkdir();raw=common.encoded(predictions)
        pred_pin=write(producer/'predictions.json',raw)
        closure={'source':self.source_pin,'producer_removed_before_capture':True,'all_native_resources_closed':True}
        backend=types.SimpleNamespace(produce=lambda *unused:(producer,{'predictions.json':pred_pin},closure))
        calls=[];original_capture=run.capture;original_mount=grade.file_mount
        def guard_capture(path,*args):
            if Path(path).name=='reference.private.npz':raise AssertionError('Private touch before grader')
            return original_capture(path,*args)
        def grader(*args):
            calls.append(True);self.assertTrue((self.out/'PREDICTION_COMMIT.json').is_file())
            self.assertIsNone(run.admit_public(args[4].read_bytes(),(root/'cases.json').read_bytes()))
            return {'status':'scored_exposed_transfer_candidate','private_target_loads':1}
        with patch.object(run,'packet_metadata',return_value=(root,packet)),patch.object(run,'capture',side_effect=guard_capture),\
             patch.object(grade,'file_mount',side_effect=AssertionError('No private mount construction')):
            result=run.complete(backend,{},self.out,self.source_pin,program_pin,grader,time.monotonic()+180)
        self.assertEqual(calls,[True] if valid else [])
        self.assertEqual(result['status'],'scored_exposed_transfer_candidate' if valid else 'invalid_submission')

    def test_source_and_portable_locator_filter(self):
        self.assertEqual(common.authenticate(self.source_pin),self.source_pin)
        value=common.contract();self.assertNotIn('closed_worker_receipt_origin',value);self.assertNotIn('source_reference_provenance',value)
        for name in ('project.py','grade.py','controls.py','TASK.md'):
            self.assertEqual(common.pin((HERE/'original'/name).read_bytes()),value['local_sources'][name])

    def test_worker_actual_nonzero_propagation(self):
        output=self.out/'output';output.mkdir();request=self.out/'request';write(request,common.encoded({'phase_id':'generated'}))
        def path(value):return output if value=='/output' else request if value=='/request.json' else Path(value)
        with patch.object(worker,'Path',side_effect=path),patch.object(worker.sys,'argv',['worker','candidate']),\
             patch.object(worker.subprocess,'run',return_value=types.SimpleNamespace(returncode=7)):
            self.assertEqual(worker.main(),7)
        global WRITES
        WRITES+=sum(p.stat().st_size for p in output.iterdir())

    def test_grade_export_successful_exit_and_failure(self):
        path=self.out/'score.json';body=b'{"generated":true}\n';write(path,body)
        for code in (None,0,2):
            out=types.SimpleNamespace(buffer=io.BytesIO())
            with patch.object(grade_export.sys,'stdout',out),patch.object(grade_export.sys,'argv',['wrapper']),\
                 patch.object(grade_export,'Path',return_value=path),patch.object(grade_export.runpy,'run_path',side_effect=SystemExit(code)):
                if code==2:
                    with self.assertRaises(SystemExit):grade_export.main()
                    self.assertEqual(out.buffer.getvalue(),b'')
                else:grade_export.main();self.assertEqual(out.buffer.getvalue(),body)

    def test_trusted_project_partial_is_archived_not_usable(self):
        output=self.out/'output';output.mkdir();request=self.out/'request';write(request,common.encoded({'phase_id':'generated'}))
        def path(value):
            if value=='/output':return output
            if value=='/request.json':return request
            if value=='/source/CONTRACT.json':return HERE/'original/CONTRACT.json'
            return Path(value)
        def failed(*args,**kwargs):
            write(output/'receipt.json',b'{"status":"packet_incomplete_preserved"}\n')
            return types.SimpleNamespace(returncode=2)
        with patch.object(worker,'Path',side_effect=path),patch.object(worker.sys,'argv',['worker','project']),\
             patch.object(worker.subprocess,'run',side_effect=failed):
            self.assertEqual(worker.main(),0)
        global WRITES
        WRITES+=sum((output/n).stat().st_size for n in ('RESULT.json','OUTPUTS.json'))
        result=common.decode((output/'RESULT.json').read_bytes());self.assertEqual(result['exit_code'],2)
        backend=types.SimpleNamespace(project=lambda:(output,{'receipt.json':common.pin((output/'receipt.json').read_bytes())},{}))
        with self.assertRaises(ValueError):run.prepare(backend,self.out,self.source_pin)
        self.assertTrue((output/'receipt.json').is_file());self.assertFalse((self.out/'COMPLETE.json').exists())

    def test_fresh_stage_allocation_preserves_history(self):
        policy={'schema':'neural022_delivery_boundary_v1','source':self.source_pin,'image':common.IMAGE,
                'approved_rule':'exact_original_projection_then_public_candidate_then_private_grade',
                'operator_approved':True,'image_inventory_sha256':'a'*64}
        policy_path=self.out/'policy.json';policy_pin=write(policy_path,common.encoded(policy))
        allocation={'schema':'neural022_fresh_delivery_allocation_v1','source':self.source_pin,'stage':'run',
                    'operator_approved':True,'historical_failed_projection_seconds':150,'new_whole_seconds':210,
                    'current_prior_cumulative_seconds':150,'new_cumulative_ceiling_seconds':360,
                    'current_history_sha256':'b'*64,'operator_artifact_bytes':16777216}
        alloc_path=self.out/'allocation.json';alloc_pin=write(alloc_path,common.encoded(allocation))
        config={'schema':'neural022_delivery_configuration_v1','source':self.source_pin,'image':common.IMAGE,
                'docker_binary':'/generated/docker','docker_socket':'/generated/socket','control_root':'/generated/control',
                'quarantine_root':'/generated/quarantine','mechanical_policy_path':str(policy_path),'mechanical_policy_pin':policy_pin,
                'allocation_path':str(alloc_path),'allocation_pin':alloc_pin}
        path=self.out/'config.json';write(path,common.encoded(config));run.configuration(path,'run')
        with self.assertRaises(ValueError):run.configuration(path,'prepare')
        allocation['historical_failed_projection_seconds']=0
        config['allocation_pin']=write(alloc_path,common.encoded(allocation));write(path,common.encoded(config))
        with self.assertRaises(ValueError):run.configuration(path,'run')

    def test_profiles_requested_and_admitted(self):
        request={'resources':run.CANDIDATE_LIMITS,'image':common.IMAGE,'command':['/python','worker']}
        item={'kind':'container','name':'generated','owner':'generated','id':'a'*64}
        for holder in (True,False):
            command=['/python','holder'] if holder else request['command'];mounts={}
            args=provider.create_args(item,holder,mounts,request,command)
            self.assertEqual(args[args.index('--cpus')+1],'0.250000000' if holder else '1.500000000')
            h={'Memory':134217728 if holder else 3221225472,'MemorySwap':134217728 if holder else 3221225472,
               'NanoCpus':250000000 if holder else 1500000000,'PidsLimit':64,'ShmSize':16777216,
               'NetworkMode':'none','ReadonlyRootfs':True,'CgroupnsMode':'private','LogConfig':{'Type':'none'},'IpcMode':'private','PidMode':'',
               'Privileged':False,'CapDrop':['ALL'],'SecurityOpt':['no-new-privileges'],'RestartPolicy':{'Name':'no'},
               'AutoRemove':False,'Init':False,'Tmpfs':{'/ready':provider.READY_OPTIONS} if holder else {'/work':provider.scratch_options(67108864)},
               'Ulimits':[{'Name':k,'Soft':v,'Hard':v} for k,v in {'core':0,'nofile':128,'fsize':256 if holder else 65536}.items()]}
            info={'Name':'/generated','Id':'a'*64,'Image':common.IMAGE,'HostConfig':h,'Mounts':[],
                  'Config':{'Labels':{LABEL:'generated'},'Image':common.IMAGE,'User':'65534:65534','Entrypoint':[command[0]],
                            'Cmd':command[1:],'WorkingDir':'/' if holder else '/work','Env':[k+'='+v for k,v in provider.fixed_environment(holder).items()]}}
            provider.admit_container(info,item,holder,mounts,request,command,[])
            info['HostConfig']['NanoCpus']+=1
            with self.assertRaises(ValueError):provider.admit_container(info,item,holder,mounts,request,command,[])

    def test_standalone_grade_profile_and_submission_binding(self):
        item={'kind':'container','name':'generated','owner':'generated','id':'a'*64};p=common.pin(b'x');argv=grade.command(p,p)
        args=grade.create_args(item,{},argv,p);self.assertIn('cpu=20:22',args);self.assertIn('1.75',args)
        h={'Memory':3221225472,'MemorySwap':3221225472,'NanoCpus':1750000000,'PidsLimit':64,'NetworkMode':'none',
           'ReadonlyRootfs':True,'Privileged':False,'CapDrop':['ALL'],'SecurityOpt':['no-new-privileges:true'],
           'AutoRemove':False,'RestartPolicy':{'Name':'no'},'Tmpfs':{'/tmp':grade.TMP},'Mounts':[],
           'LogConfig':{'Type':'local','Config':{'max-size':'2m','max-file':'1','compress':'false'}},
           'Ulimits':[{'Name':k,'Soft':v[0],'Hard':v[1]} for k,v in {'cpu':(20,22),'nofile':(1024,1024),'core':(0,0),'fsize':(1048576,1048576)}.items()]}
        c={'Labels':{LABEL:'generated'},'Image':common.IMAGE,'Entrypoint':[argv[0]],'Cmd':argv[1:],'WorkingDir':'/tmp','User':'65534:65534',
           'Env':[k+'=2' for k in grade.THREADS]+['PYTHONDONTWRITEBYTECODE=1','EXPECTED_SUBMISSION_SHA256='+p['sha256']]}
        value={'Name':'/generated','Id':'a'*64,'Image':common.IMAGE,'HostConfig':h,'Config':c,'State':{'Status':'created','Running':False,'Pid':0},'Mounts':[]}
        grade.admit(value,item,{},argv,p)
        c['Env'][-1]='EXPECTED_SUBMISSION_SHA256='+'0'*64
        with self.assertRaises(ValueError):grade.admit(value,item,{},argv,p)

    def test_byte_and_link_boundaries(self):
        global WRITES
        path=self.out/'x';p=write(path,b'generated')
        with self.assertRaises(ValueError):common.capture(path,2)
        with self.assertRaises(ValueError):common.capture(path,100,dict(p,sha256='0'*64))
        linked=self.out/'linked';linked.symlink_to(path)
        with self.assertRaises(ValueError):common.capture(linked,100)
        from transport import bounds
        control=self.out/'mode-control';control.mkdir(mode=0o700)
        meter=bounds.Meter(1024,1024,time.monotonic()+10)
        old_umask=os.umask(0o077)
        try:
            for name in ('REQUEST.json','POLICY.json'):
                bounds.publish(control/name,b'{}\n',meter,mode=0o444)
            bounds.publish(control/'private.json',b'{}\n',meter)
            counted_publish(control/'private-record.json',b'{}\n')
        finally:
            WRITES+=meter.write_bytes
            os.umask(old_umask)
        self.assertEqual(tuple((control/name).stat().st_mode&0o777 for name in
                               ('REQUEST.json','POLICY.json','private.json','private-record.json')),
                         (0o444,0o444,0o600,0o400))
        self.assertEqual(control.stat().st_mode&0o777,0o700)

    def test_native_candidate_complete_transport_wiring(self):
        from transport.contract import validate_request,validate_exposure
        quarantine=self.out/'quarantine';quarantine.mkdir();program_pin=write(self.out/'program.py',b'# generated\n')
        config={'image':common.IMAGE,'docker_binary':'/generated/docker','docker_socket':'/generated/socket',
                'control_root':'/generated/control','quarantine_root':str(quarantine),
                'mechanical_policy_pin':common.pin(b'generated-policy')}
        policy={'image_inventory_sha256':'a'*64};seen=[]
        class FakeProvider:
            def __init__(self,*args):self.args=args
            def execute_phase(inner,request,mounts,deadline,journal):
                validate_request(request,mounts,deadline)
                exposure=common.decode(Path(next(iter(inner.args[5].values()))).read_bytes())
                validate_exposure(exposure,request,mounts)
                self.assertEqual(set(mounts),{'/input/'+n for n in common.PUBLIC}|{'/program/program.py','/library/worker.py'})
                self.assertEqual(request['resources'],run.CANDIDATE_LIMITS)
                self.assertEqual(request['command'][-1],'candidate');seen.append(request)
                folder=quarantine/request['phase_id'];folder.mkdir()
                files={'predictions.json':write(folder/'predictions.json',common.encoded(self.predictions)),
                       'RESULT.json':write(folder/'RESULT.json',common.encoded({'schema':'neural022_worker_exit_v1','mode':'candidate','exit_code':0})),
                       'OUTPUTS.json':common.pin(b'generated-envelope')}
                receipt={'status':'captured','producer_closed_before_capture':True,'all_native_resources_closed':True,
                    'cli_reaped':True,'error':None,'natural_exit':{'ExitCode':0,'OOMKilled':False},'source':self.source_pin,
                    'role':'A','image':common.IMAGE,'exposure':request['exposure'],'input_before':mounts,'input_after':mounts,
                    'quarantine_root':str(folder),'output_inventory':{'complete':True,'files':files}}
                inner.receipt=receipt;return {'receipt':receipt,'receipt_pin':common.pin(common.encoded(receipt))}
            def observe(inner,phase,sha,identity,deadline):
                self.assertEqual(phase,seen[0]['phase_id']);self.assertEqual(sha,common.pin(common.encoded(seen[0]))['sha256'])
                self.assertEqual(identity,common.pin(common.encoded(inner.receipt)));return {'receipt':inner.receipt}
        now=time.monotonic();backend=run.Native(config,policy,self.out,self.source_pin,now,now+210)
        with patch.object(run,'Provider',FakeProvider):
            root,files,closure=backend.produce(self.packet,{'files':self.files},program_pin)
        self.assertEqual(len(common.decode((root/'predictions.json').read_bytes())['predictions']),92)
        self.assertTrue(closure['all_native_resources_closed'])

    def test_standalone_grader_lifecycle_and_failure_cleanup(self):
        # Generated operator source/data files only. Exercise actual mount construction,
        # private hashing, phase sequencing, stopped/report order and cleanup dispatch.
        pred=self.out/'predictions.json';pred_pin=counted_publish(pred,common.encoded(self.predictions),0o444)
        packet={'files':self.files};config={'docker_binary':'/generated/docker','docker_socket':'/generated/socket'}
        snapshot=self.out/'snapshot';snapshot.mkdir(mode=0o700)
        for name in common.PACKET:
            write(snapshot/name,(self.packet/name).read_bytes());(snapshot/name).chmod(0o444)
        result={'schema':'neural022_finite_candidate_score_v1','candidate_id':'NEURAL-022','submission_commitment':pred_pin,
                'source_contract':common.pin((HERE/'original/CONTRACT.json').read_bytes()),'packet_receipt':self.files['receipt.json'],
                'candidate_code_executed_by_grader':False,'status':'scored_exposed_transfer_candidate','private_target_loads':1}
        calls=[];closures=[]
        class FakeDocker:
            def __init__(self,*args,**kwargs):self.records=[];self.reaped=True
        def call(engine,args,end,phase,cap=0,seconds=8):
            calls.append(phase)
            if phase=='create':return b'a'*64
            if phase=='wait':return b'0\n'
            if phase=='logs':return common.encoded(result)
            return b''
        def inspect(engine,kind,identity,end,phase):
            if phase=='admit':return {}
            self.assertEqual(calls[-1],'wait')
            return {'State':{'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False}}
        def retire(engine,item,end):closures.append(item.copy());return {'closed':True}
        with patch.object(grade,'Docker',FakeDocker),patch.object(grade,'call',side_effect=call),\
             patch.object(grade,'inspect',side_effect=inspect),patch.object(grade,'admit'),patch.object(grade,'owned'),\
             patch.object(grade,'resource_inventory',return_value=[]),patch.object(grade,'retire',side_effect=retire):
            got=grade.execute(config,self.out/'grader',snapshot,packet,pred,pred_pin,self.source_pin,time.monotonic()+90)
            self.assertEqual(got,result);self.assertEqual(calls,['create','start','wait','logs']);self.assertEqual(len(closures),1)
            calls.clear()
            with patch.object(grade,'admit',side_effect=ValueError('generated admission refusal')):
                with self.assertRaises(ValueError):
                    grade.execute(config,self.out/'refused',snapshot,packet,pred,pred_pin,self.source_pin,time.monotonic()+90)
            self.assertEqual(calls,['create']);self.assertEqual(len(closures),2)
            self.assertFalse((self.out/'refused/SCORE.json').exists())

    def test_prepare_publishes_complete_readable_snapshot(self):
        backend=types.SimpleNamespace(project=lambda:(self.packet,self.files,{'all_native_resources_closed':True}))
        original=run.capture
        def captured(path,*args):
            if Path(path)==HERE/'original/CONTRACT.json':return common.encoded(self.contract)
            return original(path,*args)
        with patch.object(run,'contract',return_value=self.contract),patch.object(run,'capture',side_effect=captured):
            result=run.prepare(backend,self.out,self.source_pin)
        self.assertEqual(set(result['files']),set(common.PACKET))
        self.assertEqual(result['public_query_rows'],92)
        for name in common.PACKET:self.assertEqual((self.out/'packet'/name).stat().st_mode&0o777,0o444)
        self.assertEqual((self.out/'packet').stat().st_mode&0o777,0o700)


class HolderGuard(unittest.TestCase):
    def test_actual_main_guard_cpu(self):
        from transport import holder
        policy={'schema':'osl_holder_policy_v1','phase_id':'generated','role':'operator',
                'file_cap':524288,'total_cap':2097152,'files':8,'directories':1}
        owner='osl-'+'a'*24+'/holder'
        argv=['holder.py','hold','--owner-token',owner,'--role','operator',
              '--policy','/generated/POLICY.json','--policy-sha256',common.pin(common.encoded(policy))['sha256']]
        cases=[('quarter','25000 100000',True,{}),('different_period','50000 200000',True,{}),
               ('small_period','1 4',True,{})]
        cases += [(name,cpu,False,{}) for name,cpu in (
            ('one_cpu','100000 100000'),('half_cpu','50000 100000'),('fifth_cpu','20000 100000'),
            ('near_quarter','25000 100001'),('zero_quota','0 100000'),('negative_quota','-25000 100000'),
            ('zero_period','25000 0'),('negative_period','25000 -100000'),('both_negative','-25000 -100000'),
            ('both_zero','0 0'),('unlimited','max 100000'),('missing_period','25000'),
            ('extra_token','25000 100000 1'),('malformed','quarter 100000'))]
        cases += [(name,'25000 100000',False,{key:value}) for name,key,value in (
            ('wrong_memory','memory.max','268435456'),('extra_swap','memory.swap.max','1'),
            ('wrong_pids','pids.max','65'),('wrong_uid','uid',0),('public_ready','ready_mode',0o755),
            ('writable_capture','capture_mode','rw'),('wrong_capacity','capture_bytes',2097153))]
        class ReadyReached(Exception):pass
        for name,cpu,accepted,overrides in cases:
            with self.subTest(name=name):
                values={'memory.max':'134217728','memory.swap.max':'0','pids.max':'64','cpu.max':cpu,
                        'uid':65534,'ready_mode':0o700,'capture_mode':'ro','capture_bytes':2097152}|overrides
                observations={'/sys/fs/cgroup/'+key:values[key] for key in
                              ('memory.max','memory.swap.max','pids.max','cpu.max')}
                observations['/proc/self/mountinfo']=(
                    '23 22 0:1 / /capture '+values['capture_mode']+',noexec,nosuid,nodev - tmpfs tmpfs ro\n'
                    '24 22 0:2 / /ready rw,noexec,nosuid,nodev - tmpfs tmpfs rw\n')
                def read_text(path,*args,**kwargs):return observations[str(path)]
                def lstat(path,*args,**kwargs):
                    self.assertEqual(str(path),'/ready')
                    return types.SimpleNamespace(st_mode=stat.S_IFDIR|values['ready_mode'],st_uid=65534,st_gid=65534,st_nlink=2)
                def statvfs(path):
                    return types.SimpleNamespace(f_blocks={'/capture':values['capture_bytes'],'/ready':4096}[str(path)],f_frsize=1)
                with patch.object(sys,'argv',argv),patch.object(holder,'POLICY',None),\
                     patch.object(holder,'load_policy',return_value=policy),patch.object(Path,'read_text',read_text),\
                     patch.object(Path,'lstat',lstat),patch.object(holder.os,'getuid',return_value=values['uid']),\
                     patch.object(holder.os,'statvfs',side_effect=statvfs),\
                     patch.object(holder,'publish_ready',side_effect=ReadyReached) as ready,\
                     patch.object(holder.time,'sleep',side_effect=AssertionError('Generated control never enters hold loop')):
                    with self.assertRaises(ReadyReached if accepted else ValueError):holder.main()
                    if accepted:ready.assert_called_once_with(Path('/capture'),owner)
                    else:ready.assert_not_called()
        print(json.dumps({'holder_guard_scenarios':len(cases),'actual_main_and_guard':True,
                          'cgroup_mount_observations':'generated in memory','fixture_body_bytes_written':0}))


if __name__=='__main__':
    print(json.dumps({'python':sys.version,'numpy':np.__version__,'fixture_scope':'invented complete 141/92 rows only'}))
    suite=(unittest.TestSuite(HolderGuard(name.split('.',1)[1]) if name.startswith('HolderGuard.') else Delivery(name)
                             for name in sys.argv[1:]) if len(sys.argv)>1
           else unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in (Delivery,HolderGuard)))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'generated_file_body_bytes_written':WRITES,'unknown_bytes':'filesystem metadata, Python/library I/O, failed partial writes not observed',
                      'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)}))
    raise SystemExit(not result.wasSuccessful())
