"""Invented data only. Actual stage/config/scorer; Docker transport is never run."""
import ast
from contextlib import ExitStack
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'));sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from fixture_support import invented_manifest, invented_receipt
import common as c
import docker_owner as owner
import fold_context
import fold_runner as f
import packet
import provision
import run_once
import outer_once
import runner_config as rc
import score
import split

# Source controls must have no process/network escape hatch, even if accidentally
# switched from the fake below to the actual CLI or runtime.
def audit(event,args):
    if event in {'subprocess.Popen','os.system','os.posix_spawn','socket.connect','socket.bind'}:
        raise RuntimeError('source-control transport forbidden: '+event)
sys.addaudithook(audit)
FIXTURE_PROFILE={'animals':104,'records':104,'samples':312,'stacks':104}
FAILURES=(ValueError,AssertionError,TypeError,KeyError,FileNotFoundError)

def digest(x):return hashlib.sha256(x.encode()).hexdigest()

def unseal_delete(root):
    for base,dirs,files in os.walk(root):
        os.chmod(base,0o700)
        for name in files:os.chmod(Path(base)/name,0o600)
    shutil.rmtree(root)

class Controls(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='abr-invented-',dir=str(Path.home()))).resolve()
        self.budget=c.Budget(time.monotonic()+8000,32*1024**2,32*1024**2)
        self.packet=self.root/'invented-packet';self.packet.mkdir()
        (self.packet/'animals').mkdir();(self.packet/'evaluator').mkdir()
        self.manifest=invented_manifest()
        rows=self.manifest['animals']
        self.animals={}
        animalpins=[]
        for number,row in enumerate(rows,1):
            aid=row['animal_id']
            a={'schema':'abr-background-animal/v1','animal_id':aid,
               'representation':'within_release_sample_index_float64',
               'records':[{'record_id':'record_'+digest('invented-record-'+aid),'stimulus':'click',
                 'level':25.0,'repeat_index':0,'sample_indices':[0,1,2],
                 'samples':[0.25,float(number)/100,-0.5]}]}
            packet.validate_animal(a);self.animals[aid]=a
            p=c.write(self.packet/'animals'/(aid+'.json'),c.encode(a),self.budget)
            animalpins.append({'name':aid+'.json','bytes':p['bytes'],'sha256':p['sha256']})
        mp=c.write(self.packet/'evaluator/PRIVATE_MANIFEST.json',c.encode(self.manifest),self.budget)
        # This label explicitly distinguishes the invented reduced arrays. The
        # loader has a fixed cohort profile. Only stage counts are patched for
        # reduced arrays; opaque structure and scoring remain active throughout.
        comp={'schema':'abr-background-opaque-packet-completion/v1','profile':packet.PROFILE,
              'sample_count':312,'private_manifest_sha256':split.digest(self.manifest),
              'animal_files':animalpins,'control_only':'invented-small-arrays'}
        cp=c.write(self.packet/'evaluator/PACKET_COMPLETION.json',c.encode(comp),self.budget)
        prep=invented_receipt({k:mp[k]for k in ('bytes','sha256')},{k:cp[k]for k in ('bytes','sha256')})
        pp=c.write(self.packet/'evaluator/PREPARATION_RECEIPT.json',c.encode(prep),self.budget)
        progs={}
        for route in f.ROUTES:
            progs[route]=c.write(self.root/(route+'.py'),b'# invented frozen fixture; never executed\n',self.budget)
        self.selection={'root_execution_selected':True,'packet_root':str(self.packet),
                        'manifest':mp,'completion':cp,'preparation':pp,'programs':progs}
        self.documents={n:(ROOT/n).read_bytes() for n in f.DOCS}
        self.calls=[];self.score_calls=[];self.sabotage=None
        self.reportroot=self.root/'campaign'
        self.original_score=score.score

    def tearDown(self):unseal_delete(self.root)

    def fake_owner(self,**kw):
        root=kw['root'];root.mkdir()
        header=c.decode((kw['input_dir']/'FOLD.json').read_bytes())
        fold=header['partition']['outer_fold'];route=header['route']
        self.assertEqual(set(header['training_labels']),set(header['partition']['train_animal_ids']))
        test=set(header['partition']['test_animal_ids']);self.assertFalse(test & set(header['training_labels']))
        self.assertFalse((self.reportroot/'ALL_104_PAIRED_COMMITTED.private.json').exists())
        self.assertFalse((self.reportroot/'EVALUATION.private.json').exists())
        self.assertEqual(self.score_calls,[])
        self.assertEqual(set(p.name for p in kw['task_dir'].iterdir()),set(f.DOCS))
        self.assertEqual(set(p.name for p in kw['input_dir'].iterdir()),{'FOLD.json','animals'})
        files=list((kw['input_dir']/'animals').glob('*.json'));self.assertEqual(len(files),104)
        for path in files:
            a=c.decode(path.read_bytes())
            if route=='layout_only':
                self.assertEqual(set(a),{'schema','animal_id','records'})
                self.assertNotIn('samples',a['records'][0])
            else:self.assertEqual(a,self.animals[a['animal_id']])
        for inner in header['partition']['inner_folds']:
            self.assertFalse(test & set(inner['train_animal_ids']))
            self.assertFalse(test & set(inner['validation_animal_ids']))
        self.calls.append((route,fold,str(root),str(kw['input_dir']),kw['program'].read_bytes()))
        # Constant probabilities, independent of all held labels. This is a gate
        # fixture, not a competent scientific reference or a measured model.
        rows=[{'animal_id':aid,'outer_fold':fold,'p_6n':0.5} for aid in sorted(test)]
        life={'episode_closed':True,'candidate_closed':True,'remaining_owned_cid':None,
              'publication_errors':[],'journal':{'closed':True,'persistence_errors':[]},
              'failure':None}
        if self.sabotage:self.sabotage(kw,header,rows,life)
        sub=c.write(root/'SUBMISSION.private.json',c.encode(rows),self.budget)
        life['submission']=sub
        lp=c.write(root/'LIFECYCLE.private.json',c.encode(life),self.budget)
        return owner.ClosedRun(sub,lp,owner._CLOSED_TOKEN)

    def observe_score(self,manifest,candidate,layout):
        self.assertEqual(len(candidate),104);self.assertEqual(len(layout),104)
        self.assertEqual(len(self.calls),10)
        barrier=c.decode((self.reportroot/'ALL_104_PAIRED_COMMITTED.private.json').read_bytes())
        self.assertFalse(barrier['feedback_issued']);self.assertEqual(len(barrier['folds']),10)
        self.assertEqual(barrier['candidate_predictions'],104)
        self.assertEqual(barrier['layout_predictions'],104)
        self.score_calls.append((104,104))
        return self.original_score(manifest,candidate,layout)

    def execute(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(f,'PROFILE',FIXTURE_PROFILE))
            stack.enter_context(patch.object(owner,'configure_cli',return_value={'control':'no-transport'}))
            stack.enter_context(patch.object(owner,'require_configured_cli',return_value=None))
            stack.enter_context(patch.object(owner,'run_candidate',side_effect=self.fake_owner))
            stack.enter_context(patch.object(score,'score',side_effect=self.observe_score))
            return f.execute(self.selection,self.documents,root=self.reportroot,budget=self.budget,
                             active_deadline=time.monotonic()+7200)

    def assert_no_score(self):
        self.assertEqual(self.score_calls,[])
        self.assertFalse((self.reportroot/'EVALUATION.private.json').exists())
        self.assertFalse((self.reportroot/'ALL_104_PAIRED_COMMITTED.private.json').exists())

    def test_complete_actual_projection_commit_and_score(self):
        result=self.execute()
        self.assertEqual(result['paired_complete_predictions'],208)
        self.assertEqual(self.score_calls,[(104,104)])
        self.assertEqual([x[:2] for x in self.calls],[(r,i) for r in f.ROUTES for i in range(5)])
        self.assertEqual(len({x[2] for x in self.calls}),10)
        self.assertEqual(len({x[3] for x in self.calls}),10)
        self.assertEqual(len({x[4] for x in self.calls}),1)
        report=c.decode(Path(result['report']['path']).read_bytes())
        self.assertEqual(report['score']['metrics']['balanced_accuracy'],0.5)
        self.assertFalse(result['scientific_qualification'])

    def test_missing_last_prediction_blocks_all_feedback(self):
        def bad(kw,h,rows,life):
            if h['route']=='layout_only' and h['partition']['outer_fold']==4:rows.pop()
        self.sabotage=bad
        with self.assertRaisesRegex(ValueError,'complete test-fold'):self.execute()
        self.assertEqual(len(self.calls),10);self.assert_no_score()

    def test_known_positive_negative_and_layout_scoring_controls(self):
        # Privileged evaluator fixtures, never a candidate/reference program.
        good=[{'animal_id':a['animal_id'],'outer_fold':a['outer_fold'],'p_6n':a['label']}
              for a in self.manifest['animals']]
        bad=[dict(r,p_6n=1-r['p_6n']) for r in good]
        prior=[dict(r,p_6n=0.5) for r in good]
        positive=score.score(self.manifest,good,prior)
        negative=score.score(self.manifest,bad,prior)
        self.assertEqual(positive['metrics']['balanced_accuracy'],1)
        self.assertEqual(negative['metrics']['balanced_accuracy'],0)
        self.assertEqual(positive['layout_comparison']['delta_balanced_accuracy'],0.5)
        self.assertEqual(negative['layout_comparison']['delta_balanced_accuracy'],-0.5)

    def test_ninth_context_failure_blocks_all_feedback(self):
        def bad(kw,h,rows,life):
            if h['route']=='layout_only' and h['partition']['outer_fold']==3:raise RuntimeError('invented missing context')
        self.sabotage=bad
        with self.assertRaisesRegex(RuntimeError,'invented missing'):self.execute()
        self.assertEqual(len(self.calls),9);self.assert_no_score()

    def test_unknown_cleanup_blocks_before_commit(self):
        self.sabotage=lambda kw,h,rows,life:life.update(remaining_owned_cid='f'*64)
        with self.assertRaisesRegex(ValueError,'closed complete evidence'):self.execute()
        self.assert_no_score()

    def test_input_mutation_detected_even_if_transport_claims_closed(self):
        def bad(kw,h,rows,life):
            p=kw['input_dir']/'FOLD.json';os.chmod(p,0o600)
            p.write_bytes(p.read_bytes()+b' ');os.chmod(p,0o400)
        self.sabotage=bad
        with self.assertRaisesRegex(ValueError,'immutability'):self.execute()
        self.assert_no_score()

    def test_method_mutation_does_not_cross_folds(self):
        def bad(kw,h,rows,life):
            p=kw['program'];os.chmod(p,0o600);p.write_bytes(b'# changed\n');os.chmod(p,0o400)
        self.sabotage=bad
        with self.assertRaisesRegex(ValueError,'immutability'):self.execute()
        self.assertEqual(len(self.calls),1);self.assert_no_score()

    def test_injected_private_label_refused_before_stage(self):
        aid=next(iter(self.animals));self.animals[aid]['label']=1
        with self.assertRaisesRegex(ValueError,'public animal exact shape'):
            with patch.object(f,'PROFILE',FIXTURE_PROFILE):
                f.stage_fold(self.root/'leak',self.manifest,0,'candidate',self.animals.__getitem__,self.budget)

    def test_record_source_identity_leak_refused(self):
        aid=next(iter(self.animals));self.animals[aid]['records'][0]['released_mouse_id']='1'
        with self.assertRaisesRegex(ValueError,'private/source'):
            with patch.object(f,'PROFILE',FIXTURE_PROFILE):
                f.stage_fold(self.root/'leak',self.manifest,0,'layout_only',self.animals.__getitem__,self.budget)

    def test_real_profile_not_weakened_by_fixture(self):
        with self.assertRaisesRegex(ValueError,'complete original cohort'):
            f.stage_fold(self.root/'small',self.manifest,0,'candidate',self.animals.__getitem__,self.budget)

    def test_invalid_predictions_against_unchanged_fold_validator(self):
        ids=self.manifest['folds'][0]['test_animal_ids']
        good=[{'animal_id':a,'outer_fold':0,'p_6n':0.5} for a in ids]
        for change in ('missing','duplicate','wrongfold','bool','nan','inf','extra','trainingID'):
            rows=copy.deepcopy(good)
            if change=='missing':rows.pop()
            if change=='duplicate':rows[1]=rows[0].copy()
            if change=='wrongfold':rows[0]['outer_fold']=1
            if change=='bool':rows[0]['p_6n']=True
            if change=='nan':rows[0]['p_6n']=float('nan')
            if change=='inf':rows[0]['p_6n']=float('inf')
            if change=='extra':rows[0]['label']=0
            if change=='trainingID':rows[0]['animal_id']=self.manifest['folds'][0]['train_animal_ids'][0]
            with self.subTest(change=change),self.assertRaises(ValueError):
                fold_context.fold_prediction_bytes(self.manifest,0,rows)

    def test_forged_capability_and_nonclosed_owner_fail(self):
        with self.assertRaises(ValueError):f.freeze_closed(object(),self.root,self.budget)
        with self.assertRaises(ValueError):
            f.freeze_closed(owner.ClosedRun({}, {}, object()),self.root,self.budget)

    def test_reused_context_and_early_scoring_fail(self):
        camp=fold_context.Campaign(self.manifest,'a'*64,'b'*64)
        cid='c'*64;camp.start('candidate',0,cid)
        rows=[{'animal_id':a,'outer_fold':0,'p_6n':0.5} for a in self.manifest['folds'][0]['test_animal_ids']]
        self.assertEqual(set(camp.commit_stopped(cid,rows,'d'*64)),{'status','prediction_sha256'})
        with self.assertRaises(ValueError):camp.start('candidate',1,cid)
        with self.assertRaises(ValueError):camp.evaluate()

    def render_request(self):
        return {'schema':'abr_fold_render_request_v1','package_root':str(self.root/'generated'),
            'operation_root':str(self.root/'operation'),'attempt_id':'invented-control',
            'image':'sha256:'+'a'*64,'daemon_socket':str(self.root/'invented.sock'),
            'daemon_guard':{'dev':1,'inode':2,'mode':stat.S_IFSOCK|0o600,'uid':501,'gid':20,'nlink':1},
            'host_python':'/invented/cpython3116',
            'operands':{n:self.selection[n] for n in ('packet_root','manifest','completion','preparation','programs')}}

    def configured(self):
        request=self.render_request();result=provision.render(request)
        package=Path(request['package_root'])
        lock=c.decode((package/'EXECUTION_LOCK.json').read_bytes())
        bodies={n:(package/n).read_bytes() for n in lock['members']}
        source={'schema':'abr_fold_source_review_v1','whole_source_accepted':True,'members':lock['members']}
        runtime={'schema':'abr_fold_runtime_review_v1','image':request['image'],'versions':rc.RUNTIME,
             'whole_runtime_accepted':True,'no_protected_payload_in_image':True,
             'independent_review':c.pin(b'invented runtime review; no native qualification')}
        capacity={'schema':'abr_fold_capacity_v1','observed_unix':time.time(),
             'image':request['image'],'daemon_socket':request['daemon_socket'],'daemon_guard':request['daemon_guard'],
             'pressure_samples':['NORMAL','NORMAL'],'swap_used_growth_bytes':0,'swapouts_growth':0,'pageouts_growth':0,
             'potential_memory_bytes':16*1024**3,'selected_host_memory_bytes':1024**3,
             'disk_available_bytes':20*1024**3,'cpu_demand_plus_reserve':2,
             'vm_cpus':2,'vm_memory_bytes':4*1024**3,'complete_observations':c.pin(b'invented capacity')}
        metadata={'source_review':source,'runtime_review':runtime,'fresh_capacity':capacity}
        selection=copy.deepcopy(self.selection);selection['budget']=rc.LIMITS
        selection['runtime_evidence']={n:c.write(self.root/(n+'.json'),c.encode(v),self.budget) for n,v in metadata.items()}
        wrapper={'schema':rc.SCHEMA,'attempt_id':'invented-control','selection':selection}
        return request,result,bodies,wrapper,metadata

    def admission(self,request,bodies,wrapper):
        with patch.object(owner,'IMAGE',request['image']),patch.object(owner,'DAEMON_SOCKET',Path(request['daemon_socket'])),patch.object(owner,'DAEMON_GUARD',request['daemon_guard']):
            return rc.prepare(wrapper,{},bodies,self.budget)

    def test_provision_exact_closure_and_unselected_runtime_template(self):
        request,result,bodies,wrapper,metadata=self.configured()
        self.assertEqual(set(bodies),run_once.LOCK_MEMBERS)
        self.assertEqual(provision.LIMITS,rc.LIMITS)
        self.assertEqual(provision.VERSIONS,rc.RUNTIME)
        self.assertFalse(result['dispatch_performed'])
        self.assertFalse(Path(result['required_selection_path']).exists())
        template=c.decode((Path(request['package_root'])/'UNSELECTED_RUN.json').read_bytes())
        self.assertFalse(template['selection']['root_execution_selected'])
        with self.assertRaises(ValueError):rc.admit_manifest(c.encode(template),c.pin(c.encode(template))['sha256'],'invented-control')
        with self.assertRaises(ValueError):outer_once.admit_manifest(c.encode(template),c.pin(c.encode(template))['sha256'],'invented-control')
        raw=c.encode(wrapper);rc.admit_manifest(raw,c.pin(raw)['sha256'],'invented-control')
        self.assertEqual(outer_once.admit_manifest(raw,c.pin(raw)['sha256'],'invented-control'),wrapper)
        admitted=self.admission(request,bodies,wrapper)
        self.assertEqual(admitted['selection'],wrapper['selection'])
        argv=result['prospective_outer_argv']
        tree=ast.parse(bodies['runtime/outer_once.py'])
        flags={n.args[0].value for n in ast.walk(tree) if isinstance(n,ast.Call) and
               isinstance(n.func,ast.Attribute) and n.func.attr=='add_argument'}
        self.assertEqual({x for x in argv if x.startswith('--')},flags)
        with self.assertRaisesRegex(ValueError,'exclusive'):provision.render(request)

    def test_config_stale_capacity_and_changed_source_refused(self):
        request,result,bodies,wrapper,metadata=self.configured()
        bad=copy.deepcopy(bodies);bad['TASK.md']+=b'changed'
        with self.assertRaisesRegex(ValueError,'whole generated-source'):self.admission(request,bad,wrapper)
        metadata['fresh_capacity']['observed_unix']-=61
        p=c.write(self.root/'stale.json',c.encode(metadata['fresh_capacity']),self.budget)
        wrapper['selection']['runtime_evidence']['fresh_capacity']=p
        with self.assertRaisesRegex(ValueError,'fresh same'):self.admission(request,bodies,wrapper)

    def test_unselected_runtime_cannot_enter_prepare(self):
        request,result,bodies,wrapper,metadata=self.configured()
        self.assertEqual(owner.IMAGE,'UNSELECTED_ABR_RUNTIME')
        with self.assertRaisesRegex(ValueError,'source-bound'):rc.prepare(wrapper,{},bodies,self.budget)

    def test_provision_rejects_path_alias_and_mutable_image(self):
        for field,value in [('image','python:latest'),('package_root',str(self.packet/'child')),
                            ('operation_root',str(self.root/'bad,src=/evaluator'))]:
            request=self.render_request();request[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):provision.render(request)
        link=self.root/'alias';link.symlink_to(self.packet,target_is_directory=True)
        request=self.render_request();request['package_root']=str(link/'child')
        with self.assertRaises(ValueError):provision.render(request)

    def test_whole_stage_wiring_uses_real_admission_and_execution(self):
        request,result,bodies,wrapper,metadata=self.configured()
        self.reportroot=self.root/'whole'/'benchmark';self.reportroot.parent.mkdir()
        modules={'common':c,'docker_owner':owner,'runner_config':rc,'fold_runner':f}
        with ExitStack() as stack:
            for name,value in [('IMAGE',request['image']),('DAEMON_SOCKET',Path(request['daemon_socket'])),('DAEMON_GUARD',request['daemon_guard'])]:
                stack.enter_context(patch.object(owner,name,value))
            stack.enter_context(patch.object(f,'PROFILE',FIXTURE_PROFILE))
            stack.enter_context(patch.object(owner,'configure_cli',return_value={'control':'no-transport'}))
            stack.enter_context(patch.object(owner,'require_configured_cli',return_value=None))
            stack.enter_context(patch.object(owner,'run_candidate',side_effect=self.fake_owner))
            stack.enter_context(patch.object(score,'score',side_effect=self.observe_score))
            out=run_once.execute_stages(wrapper,modules,bodies,root=self.reportroot.parent,
                    budget=self.budget,active_deadline=time.monotonic()+7200)
        self.assertEqual(out['paired_complete_predictions'],208)
        self.assertTrue((self.reportroot.parent/'ADMISSION.private.json').exists())

    def inspection(self):
        cid='f'*64;name='abr-fold-invented'
        mounts={(str(self.root/'input'),'/input',False),(str(self.root/'task'),'/task',False),
                (str(self.root/'program.py'),'/candidate/solution.py',False)}
        obj=[{'Id':cid,'Image':owner.IMAGE,'Name':'/'+name,'RestartCount':0,
          'Config':{'Labels':{owner.LABEL:name},'Entrypoint':['python3'],
                    'Cmd':['-I','-B','/candidate/solution.py'],'User':'501:20','WorkingDir':'/work',
                    'Env':list(owner.THREAD_ENV)},
          'HostConfig':{'Memory':owner.MEMORY,'MemorySwap':owner.MEMORY,'NanoCpus':1000000000,
            'PidsLimit':64,'NetworkMode':'none','ReadonlyRootfs':True,'CapDrop':['ALL'],
            'SecurityOpt':['no-new-privileges'],'LogConfig':{'Type':'none'},'Privileged':False,
            'IpcMode':'private','Tmpfs':{'/work':'rw,nosuid,nodev,size=134217728,mode=1777',
                                      '/tmp':'rw,nosuid,nodev,size=134217728,mode=1777'},
            'Ulimits':[{'Name':'nofile','Soft':1024,'Hard':1024},{'Name':'fsize','Soft':1048576,'Hard':1048576}]},
          'Mounts':[{'Type':'bind','Source':s,'Destination':d,'RW':rw} for s,d,rw in mounts],
          'State':{'Running':False,'Paused':False,'Restarting':False,'OOMKilled':False,'Error':'','Status':'exited','ExitCode':0}}]
        return obj,cid,name,mounts

    def test_actual_owner_mount_and_security_seams(self):
        obj,cid,name,mounts=self.inspection()
        owner.validate_inspection(obj,cid,name,mounts,final=True)
        argv=owner.create_argv(name,self.root/'input',self.root/'task',self.root/'program.py')
        self.assertIn('--network=none',argv);self.assertIn('--pull=never',argv)
        self.assertEqual(argv.count('--mount'),3)
        self.assertFalse(any('/evaluator' in x or '/var/run/docker' in x for x in argv))
        for mode in ('extra_bind','rw_input','network','state','labels','image','tmpfs'):
            bad=copy.deepcopy(obj)
            if mode=='extra_bind':bad[0]['Mounts'].append({'Type':'bind','Source':'/private','Destination':'/evaluator','RW':False})
            if mode=='rw_input':bad[0]['Mounts'][0]['RW']=True
            if mode=='network':bad[0]['HostConfig']['NetworkMode']='host'
            if mode=='state':bad[0]['State']['Running']=True
            if mode=='labels':bad[0]['Config']['Labels']={}
            if mode=='image':bad[0]['Image']='sha256:'+'e'*64
            if mode=='tmpfs':bad[0]['HostConfig']['Tmpfs']['/work']='rw'
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                owner.validate_inspection(bad,cid,name,mounts,final=True)

if __name__=='__main__':
    unittest.main(verbosity=2)
