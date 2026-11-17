"""Generated complete-roster controls, not authentic data or native execution."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import stat
import tempfile
import time
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
OP=HERE.parent/'prepared_operator'
spec=importlib.util.spec_from_file_location('cbramod_bootstrap',HERE/'run.py')
boot=importlib.util.module_from_spec(spec);spec.loader.exec_module(boot)
raw=(HERE/'SOURCE_MANIFEST.json').read_bytes()
manifest,bodies,manifest_raw=boot.source_check(len(raw),hashlib.sha256(raw).hexdigest())
executor=boot.load_runtime(bodies)
safe=sys.modules['safe_io'];engine=sys.modules['engine'];api=sys.modules['operator_api']
gp=sys.modules['grade_pair'];packet=sys.modules['packet'];boundary=sys.modules['runtime_contract']
holder=types.ModuleType('generated_holder');exec(compile(bodies['holder.py'],'<holder>','exec'),holder.__dict__)
import numpy as np


def pin(path):
    raw=path.read_bytes();return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def jwrite(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,sort_keys=True)+'\n');return pin(path)


def make_query(panel,c,purpose='improvement'):
    rows=[]
    for d in panel['primary_downstream_datasets']:
        n=20 if d['id']=='ISRUC' else 2
        rows.append({'id':d['id'],'class_labels':['c'+str(i) for i in range(d['classes'] or 0)],
                     'rows':[{'id':'r'+str(i),'group':'test'} for i in range(n)],
                     'training_groups':['train'],'validation_groups':['val'],
                     **{k:'1'*64 for k in ('split_sha256','preprocessing_sha256','input_sha256','label_selection_sha256')},
                     'sequence_assignment_sha256':'2'*64 if d['id']=='ISRUC' else None})
    q={'schema':'cbramod_query_v1','task_id':api.TASK,'purpose':purpose,
       'condition':'paper_original_splits' if purpose=='reproduction' else 'person_heldout_low_label_30pct',
       'datasets':rows,'source_qualification_sha256':'3'*64,
       'metric_abi':{'pr_definition':'trapezoidal_pr_auc','seed_sd_ddof':None,
                     'class_decision':'argmax_lowest_index_tie','undefined_policy':'explicit_null_no_support_drop',
                     'native_source_sha256':None}}
    c.validate_query(q,panel);return q


def make_submission(root,host,q,arm,invalid_last=False):
    root.mkdir();(root/'predictions').mkdir()
    panel,c=api.public(host);counts={d['id']:len(d['rows']) for d in q['datasets']};files=[]
    cases=c.cases(panel,q['purpose'])
    for i,case in enumerate(cases):
        shape=[counts[case['dataset']],case['columns']]
        x=np.arange(shape[0],dtype='<f4')[:,None] if shape[1]==1 else np.full(shape,1/shape[1],dtype='<f4')
        if invalid_last and i==len(cases)-1:x[:]=0
        name=f'predictions/{i:04d}.npy';np.save(root/name,x,allow_pickle=False)
        files.append({'case':case['id'],'path':name,'shape':shape,'dtype':'<f4',**pin(root/name)})
    value={'schema':'cbramod_prediction_artifacts_v1','task_id':api.TASK,'query_sha256':c.digest(q),
           'information_arm':api.ARMS[arm],'files':files}
    jwrite(root/'submission.json',value);return value


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='cbramod-generated-controls-');cls.base=Path(cls.tmp.name).resolve()
        cls.host=api.load(OP)
        # One authenticated source capture, reused only by generated controls to
        # avoid repeatedly reading the same103 source roles under this phase cap.
        selected=cls.host.verify_source();cls.host.verify_source=lambda:selected
        cls.panel,cls.contract=api.public(cls.host)
        cls.q=make_query(cls.panel,cls.contract)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def fresh(self):
        path=self.base/(self._testMethodName+'-'+str(time.monotonic_ns()));path.mkdir();return path

    def test_full_scope_no_population_shrink(self):
        s=api.scope(self.host)
        self.assertEqual((len(s['primary_datasets']),s['candidate_reproduction'],s['candidate_improvement'],
                          s['reference_improvement'],s['reference_reproduction']),(12,800,60,420,800))
        self.assertEqual(len(s['additional_required_paper_families']),14)
        self.assertIn('BCIC-IV-2a',s['additional_required_paper_families'][0])
        self.assertEqual(boundary.OUTPUT_BYTES,8_000_000_000)
        self.assertGreaterEqual(boundary.VOLUME_BYTES,boundary.OUTPUT_BYTES+4_000_000)

    def test_complete_800_case_holder_streams_and_final_file_pin_refuses(self):
        p=self.fresh();q=make_query(self.panel,self.contract,'reproduction')
        submission=make_submission(p/'source',self.host,q,'A');expect=api.expectation(self.host,q,'A')
        (p/'out').mkdir();receipt=holder.capture(p/'source',p/'out',expect,time.monotonic()+30)
        self.assertEqual(receipt['files'],800);self.assertEqual(len(list((p/'out/predictions').iterdir())),800)
        last=p/'source'/submission['files'][-1]['path'];b=bytearray(last.read_bytes());b[-1]^=1;last.write_bytes(b)
        (p/'bad').mkdir()
        with self.assertRaisesRegex(ValueError,'hash'):holder.capture(p/'source',p/'bad',expect,time.monotonic()+30)

    def test_holder_rejects_missing_final_extra_link_and_wrong_arm(self):
        p=self.fresh();submission=make_submission(p/'source',self.host,self.q,'A');expect=api.expectation(self.host,self.q,'A')
        for mode in ('missing','extra','hardlink','arm'):
            out=p/mode;out.mkdir();saved=copy.deepcopy(submission)
            if mode=='missing':submission['files'].pop()
            elif mode=='extra':(p/'source/extra.py').write_text('no')
            elif mode=='hardlink':os.link(p/'source'/submission['files'][0]['path'],p/'outside-link')
            else:submission['information_arm']=api.ARMS['B']
            jwrite(p/'source/submission.json',submission)
            with self.assertRaises(ValueError):holder.capture(p/'source',out,expect,time.monotonic()+30)
            if mode=='extra':(p/'source/extra.py').unlink()
            if mode=='hardlink':(p/'outside-link').unlink()
            submission=saved;jwrite(p/'source/submission.json',submission)

    def grade_request(self,p,invalid_last=False):
        captures={};private=p/'private';private.mkdir()
        for arm in ('A','B'):
            make_submission(p/arm,self.host,self.q,arm,invalid_last and arm=='B')
            captures[arm]={'root':str(p/arm),'submission':pin(p/arm/'submission.json')}
        qpin=jwrite(p/'QUERY.json',self.q)
        targets={}
        for d,qr in zip(self.panel['primary_downstream_datasets'],self.q['datasets']):
            y=np.arange(len(qr['rows']),dtype='<f8')
            if d['classes']:y%=d['classes']
            name=d['id']+'.npy';np.save(private/name,y,allow_pickle=False);targets[d['id']]={'path':name,**pin(private/name)}
        fields={'binary':['balanced_accuracy','average_precision','trapezoidal_pr_auc','auroc'],
                'multiclass':['balanced_accuracy','cohen_kappa','weighted_f1'],'regression':['pearson','r2','rmse']}
        dmap={d['id']:d for d in self.panel['primary_downstream_datasets']}
        refs={case['id']:{key:0.0 for key in fields[dmap[case['dataset']]['task']]}
              for case in self.contract.cases(self.panel,'improvement',True)}
        refpin=jwrite(private/'references.json',refs)
        binding={'schema':'cbramod_private_binding_v1','query_sha256':self.contract.digest(self.q),
                 'targets':targets,'reference_metrics':{'path':'references.json',**refpin},'reference_source_sha256':'4'*64}
        bpin=jwrite(private/'binding.json',binding)
        return {'operator_root':str(OP),'query':str(p/'QUERY.json'),'query_pin':qpin,'captures':captures,
                'binding':str(private/'binding.json'),'binding_pin':bpin,'grade_end':time.monotonic()+60,
                'evaluation_condition':'matched_support_re_evaluation'}

    def test_b_final_probability_prevents_any_private_binding_read(self):
        p=self.fresh();r=self.grade_request(p,True);calls=[];original=gp.read_pinned
        def observe(path,*args):
            if str(path)==r['binding']:calls.append(path)
            return original(path,*args)
        with patch.object(gp,'read_pinned',observe),self.assertRaisesRegex(ValueError,'probabilities'):
            gp.grade(r)
        self.assertEqual(calls,[])

    def test_real_unchanged_scorer_both_60_cases_420_comparators(self):
        p=self.fresh();r=self.grade_request(p);result=gp.grade(r)
        self.assertEqual(set(result['arms']),{'A','B'})
        self.assertNotIn('same_frozen_program',result)
        for arm in ('A','B'):
            grade=result['arms'][arm]['result']
            self.assertEqual(len(grade['methods']),12);self.assertEqual(len(grade['comparisons']),84)
            self.assertTrue(all(m['seed_slots']==5 for m in grade['methods']))
            self.assertFalse(grade['scientific_qualification'])

    def request(self,p):
        program=p/'program.py';program.write_text('# generated control; never executed\n')
        for name in ('operator','packet','config'):(p/name).mkdir()
        cli=p/'docker';cli.write_text('generated fake CLI; never executed')
        image='sha256:'+'5'*64
        admit={'schema':'cbramod_external_runtime_admission_v1','image':image,
               'common_dependency_image_without_task_material':True,'independent_program_custody':True,
               'operator_environment_qualified':True,'daemon_boundary_qualified':True,'review_identity_sha256':'6'*64}
        apin=jwrite(p/'admission.json',admit)
        return {'schema':'cbramod_paired_program_request_v1','program':str(program),'program_pin':pin(program),
                'operator_root':str(p/'operator'),'packet_root':str(p/'packet'),'packet_pin':{'bytes':1,'sha256':'7'*64},
                'binding':str(p/'private/NEVER_OPEN_PRIVATE'),'binding_pin':{'bytes':1,'sha256':'8'*64},
                'grader_python':sys.executable,'docker':str(cli),'docker_pin':pin(cli),
                'docker_host':'unix://'+str(p/'socket'),'docker_config':str(p/'config'),'image':image,
                'runtime_admission':str(p/'admission.json'),'runtime_admission_pin':apin,'output':str(p/'work'),
                'evaluation_condition':'matched_support_re_evaluation','candidate_wall_seconds':20,
                'capture_wall_seconds':30,'capture_cpu_seconds':30,'grade_wall_seconds':60,
                'cleanup_wall_seconds':30,'whole_wall_seconds':400,'candidate_cpu_seconds':20,
                'candidate_memory_bytes':9_000_000_000,'candidate_nano_cpus':1_000_000_000,
                'host_memory_budget_bytes':11_000_000_000,'retention_budget_bytes':26_000_000_000,'public_bytes_limit':1_000_000}

    def flow(self,p,mode=None):
        r=self.request(p);events=[];created=[];test=self
        class Host:
            def _condition(self,*a):pass
            def stage_view(self,arm,out):
                out.mkdir();(out/'PUBLIC.txt').write_text('common')
                if arm=='B':(out/'official').mkdir();(out/'official/code.py').write_text('B ONLY')
        class FakeDocker:
            def __init__(self,*a):self.owned=[];self.live=set();self.cleanup_rows=[];self.arm=0;self.end=0
            def volume(self,n):self.owned.append(('volume',n));self.live.add(('volume',n))
            def create(self,n,role,mounts):
                boundary.canonical(role,mounts);self.owned.append(('container',n));self.live.add(('container',n))
                self.mounts=mounts if role=='holder' else self.mounts
                if role=='candidate':
                    self.arm+=1;created.append(copy.deepcopy(mounts))
                    if mode=='second_create' and self.arm==2:raise ValueError('partial second creation')
                    for dest,row in mounts.items():
                        if dest!='/output':
                            test.assertNotIn('/operator',row['source']);test.assertNotIn('/trusted',row['source'])
                    if self.arm==1:test.assertFalse((Path(mounts['/view']['source'])/'official').exists())
            def call(self,argv,seconds=10):
                if argv[0]=='exec':
                    if mode=='second_capture' and self.arm==2:raise ValueError('second capture failed')
                    arm='A' if self.arm==1 else 'B';out=Path(self.mounts['/export']['source'])
                    value={'generated_flow_control':arm};bpin=jwrite(out/'submission.json',value)
                    return {'returncode':0,'stdout':json.dumps({'status':'captured','files':60,'artifact_bytes':9600,'submission':bpin}),'stderr':''}
                if argv[0]=='wait' and mode=='second_wait' and self.arm==2:raise ValueError('second program failed')
                return {'returncode':0,'stdout':'0' if argv[0]=='wait' else '', 'stderr':''}
            def inspect(self,kind,n):
                return {'State':{'Running':'holder' in n,'Pid':1 if 'holder' in n else 0,'OOMKilled':False,'ExitCode':0}}
            def remove(self,kind,n):self.live.discard((kind,n))
            def close(self):
                if mode=='second_close' and self.arm==2:return [{'error':'generated absence unproven'}]
                self.live.clear();return []
            def missing(self,kind,n):
                if mode=='final_absence' and self.arm==2:return False
                return (kind,n) not in self.live
        def staging(r,host,out,end):
            events.append('stage');test.assertTrue((p/'work/candidate.py').exists())
            out.mkdir();jwrite(out/'QUERY.json',test.q);return test.q,{'generated_staging_seam':True}
        def grade(*args):
            events.append('private_grade');test.assertEqual(len(created),2)
            test.assertEqual(created[0]['/program/candidate.py'],created[1]['/program/candidate.py'])
            test.assertEqual(created[0]['/input'],created[1]['/input']);return {'bytes':1,'sha256':'9'*64}
        original_is_symlink=Path.is_symlink
        def no_private_metadata(path):
            private_owner=Path(r['binding']).parent
            if path==private_owner or private_owner in path.parents:
                raise AssertionError('Private owner metadata accessed before paired preflight')
            return original_is_symlink(path)
        with patch.object(engine,'Docker',FakeDocker),patch.object(api,'freeze',lambda *a:Host()),\
             patch.object(packet,'stage',staging),patch.object(api,'expectation',lambda h,q,arm:{'cases':[{}]*60}),\
             patch.object(api,'scope',lambda h:{'primary_datasets':12,'generated_scope_seam':True}),\
             patch.object(executor,'run_grade',grade),patch.object(Path,'is_symlink',no_private_metadata):
            if mode:
                with self.assertRaises(ValueError):executor.execute(r,bodies,manifest_raw)
                self.assertNotIn('private_grade',events)
            else:self.assertEqual(executor.execute(r,bodies,manifest_raw)['status'],'paired_program_captured_and_graded')
        return events,created

    def test_paired_lifecycle_freezes_once_and_a_has_no_b_mount(self):
        events,created=self.flow(self.fresh());self.assertEqual(events,['stage','private_grade'])
        self.assertNotEqual(created[0]['/view']['source'],created[1]['/view']['source'])

    def test_second_condition_failure_never_opens_private(self):
        for mode in ('second_create','second_wait','second_capture','second_close','final_absence'):
            with self.subTest(mode=mode):self.flow(self.fresh(),mode)

    def test_request_refuses_shared_program_or_reduced_8gb_budget(self):
        r=self.request(self.fresh());r['program']=r['operator_root']+'/official.py'
        with self.assertRaises(ValueError):executor.validate(r)
        r=self.request(self.fresh());r['candidate_memory_bytes']=1_000_000
        with self.assertRaises(ValueError):executor.validate(r)

    def test_private_aliases_refused_before_any_filesystem_metadata(self):
        p=self.fresh();base=self.request(p)
        cases=[base[k] for k in ('program','docker','runtime_admission','grader_python')]
        cases += [base[k]+'/binding.json' for k in ('operator_root','packet_root','docker_config','output')]
        cases += [base['packet_root']+'/QUERY.json',base['docker_host'][7:],str(HERE/'binding.json')]
        for binding in cases:
            r=copy.deepcopy(base);r['binding']=binding
            with self.subTest(binding=binding),patch.object(Path,'is_symlink',side_effect=AssertionError('Early filesystem access')):
                with self.assertRaisesRegex(ValueError,'Dedicated private owner'):executor.validate(r)

    def test_double_root_roles_refused_before_metadata(self):
        p=self.fresh();base=self.request(p)
        for role in ('binding','program','operator_root','packet_root','docker','docker_config','output',
                     'runtime_admission','grader_python','docker_host'):
            r=copy.deepcopy(base)
            r[role]='unix:////'+r[role][8:] if role=='docker_host' else '/'+r[role]
            with self.subTest(role=role),patch.object(Path,'is_symlink',side_effect=AssertionError('Early filesystem metadata')):
                with self.assertRaisesRegex(ValueError,'single-root'):executor.validate(r)

    def test_standalone_grade_private_aliases_refused_before_reads(self):
        p=self.fresh();dummy={'bytes':1,'sha256':'1'*64}
        base={'operator_root':str(OP),'query':str(p/'query.json'),'query_pin':dummy,
              'binding':str(p/'private/binding.json'),'binding_pin':dummy,
              'captures':{a:{'root':str(p/a),'submission':dummy} for a in ('A','B')},
              'evaluation_condition':'matched_support_re_evaluation','grade_end':time.monotonic()+30}
        gp.admit_roles(base)
        for role in ('query','operator_root','A','B','binding-double','query-double','capture-double'):
            r=copy.deepcopy(base)
            if role=='query':r['query']=r['binding']
            elif role=='operator_root':r['operator_root']=str(p/'private/operator')
            elif role in ('A','B'):r['captures'][role]['root']=str(p/'private'/role)
            elif role=='binding-double':r['binding']='/'+r['binding']
            elif role=='query-double':r['query']='/'+r['query']
            else:r['captures']['A']['root']='/'+r['captures']['A']['root']
            with self.subTest(role=role),patch.object(api,'load',side_effect=AssertionError('Operator read before role admission')),\
                 patch.object(gp,'read_pinned',side_effect=AssertionError('Private read before role admission')):
                with self.assertRaises(ValueError):gp.grade(r)

    def test_strict_absence_is_not_transport_error(self):
        a=sys.modules['absence'].absence
        self.assertTrue(a(1,'[]','Error: No such object: x','container','x'))
        self.assertFalse(a(1,'','daemon unavailable: No such object: x','container','x'))

    def test_real_boundary_rejects_extra_mounts_network_and_budget_drift(self):
        r=self.request(self.fresh());name='generated-inspect'
        mounts={'/program/candidate.py':{'type':'bind','source':r['program'],'rw':False},
                '/input':{'type':'bind','source':r['packet_root'],'rw':False},
                '/view':{'type':'bind','source':r['operator_root']+'/view-A','rw':False},
                '/output':{'type':'volume','source':'owned-volume','rw':True}}
        lim=boundary.limits('candidate',r)
        h={'NetworkMode':'none','ReadonlyRootfs':True,'Privileged':False,'CapDrop':['ALL'],'CapAdd':[],
           'SecurityOpt':['no-new-privileges:true'],'AutoRemove':False,'RestartPolicy':{'Name':'no'},
           'PidMode':'','IpcMode':'private',
           'OomKillDisable':False,'Memory':lim['memory'],'MemorySwap':lim['memory'],'NanoCpus':lim['nano_cpus'],
           'PidsLimit':lim['pids'],'Tmpfs':boundary.TMPFS,
           'LogConfig':{'Type':'local','Config':{'max-size':'64k','max-file':'1','compress':'false'}},
           'Ulimits':[{'Name':k,'Soft':v[0],'Hard':v[1]} for k,v in
                      {'cpu':(lim['cpu'],lim['cpu']+2),'nofile':(1024,1024),'core':(0,0),'fsize':(8_000_000_000,8_000_000_000)}.items()],
           'Mounts':[{'Type':v['type'],'Source':v['source'],'Target':k,'ReadOnly':not v['rw'],
                      **({'VolumeOptions':{'NoCopy':True}} if v['type']=='volume' else {})} for k,v in mounts.items()]}
        info={'Name':'/'+name,'Image':r['image'],'HostConfig':h,'State':{'Status':'created','Running':False,'Pid':0},
              'Config':{'Image':r['image'],'Entrypoint':['python'],'Cmd':boundary.command('candidate'),'WorkingDir':'/output',
                        'User':'65534:65534','Env':[k+'=1' for k in (*boundary.THREADS,'PYTHONDONTWRITEBYTECODE')]},
              'NetworkSettings':{'Networks':{'none':{}}},
              'Mounts':[{'Type':v['type'],'Source':v['source'],'Name':v['source'],'Destination':k,'RW':v['rw']} for k,v in mounts.items()]}
        self.assertEqual(boundary.verify(info,name,'candidate',mounts,r)['role'],'candidate')
        argv=boundary.create_argv(name,'candidate',mounts,r)
        self.assertIn('fsize=8000000000:8000000000',argv)
        self.assertEqual(argv[argv.index('--ipc')+1],'private')
        for kind in ('effective_extra','requested_extra','network','memory','writable','image','command',
                     'shared_pid','shared_ipc','host_pid','host_ipc'):
            x=copy.deepcopy(info)
            if kind=='effective_extra':x['Mounts'].append({'Type':'bind','Source':'/official','Destination':'/leak','RW':False})
            elif kind=='requested_extra':x['HostConfig']['Mounts'].append({'Type':'bind','Source':'/official','Target':'/leak','ReadOnly':True})
            elif kind=='network':x['HostConfig']['NetworkMode']='host'
            elif kind=='memory':x['HostConfig']['Memory']-=1
            elif kind=='writable':x['Mounts'][1]['RW']=True
            elif kind=='image':x['Image']='sha256:'+'0'*64
            elif kind=='shared_pid':x['HostConfig']['PidMode']='container:other'
            elif kind=='shared_ipc':x['HostConfig']['IpcMode']='container:other'
            elif kind=='host_pid':x['HostConfig']['PidMode']='host'
            elif kind=='host_ipc':x['HostConfig']['IpcMode']='host'
            else:x['Config']['Cmd']=['untrusted']
            with self.subTest(kind=kind),self.assertRaises(ValueError):boundary.verify(x,name,'candidate',mounts,r)

    def test_full_packet_metadata_lineage_and_no_target_slot(self):
        # Exercise the real full packet validator; only bulky source-shaped signal
        # file streaming and the pinned publication body are fixture seams here.
        p=self.fresh();root=p/'packet';root.mkdir();datasets=[];q=copy.deepcopy(self.q)
        shape_map={'FACED':[32,10,200],'SEED-V':[62,1,200],'PhysioNet-MI':[64,4,200],'SHU-MI':[32,4,200],
                   'ISRUC':[20,6,6000],'CHB-MIT':[16,10,200],'BCIC2020-3':[64,3,200],'Mumtaz2016':[19,5,200],
                   'SEED-VIG':[17,8,200],'MentalArithmetic':[20,5,200],'TUEV':[16,5,200],'TUAB':[16,10,200]}
        for qr in q['datasets']:
            dataset={'id':qr['id']}
            for split in ('train','val','test'):
                if qr['id']=='ISRUC':
                    key='seq/ISRUC-group1-1/ISRUC-group1-1-0.npy'
                    keys=[[key,key.replace('seq/','labels/')]];groups={key:split}
                else:keys=['source0','source1'];groups={k:split for k in keys}
                line=self.host.row_lineage(qr['id'],split,keys,groups)
                if split=='test':qr['rows']=[{'id':x['id'],'group':x['group']} for x in line['rows']]
                base=qr['id']+'/'+split;shape=[len(keys),*shape_map[qr['id']]]
                signal={'path':'observations.npy','shape':shape,'dtype':'<f4','bytes':128+int(np.prod(shape))*4,
                        'sha256':'a'*64,'fortran_order':False}
                obs={'schema':'cbramod_target_free_observations_v2','dataset_id':qr['id'],'split':split,'lineage':line,
                     'signal_file':signal,'contains_target_labels':False,'source_parity_qualified':False}
                op=base+'/OBSERVATIONS.json';descriptor={'path':op,**jwrite(root/op,obs)}
                row={'observations':descriptor,'signals':{'path':base+'/observations.npy','bytes':signal['bytes'],'sha256':'a'*64}}
                if split!='test':row['labels']={'path':base+'/labels.npy','bytes':128+len(line['rows'])*8,'sha256':'b'*64}
                dataset[split]=row
            datasets.append(dataset)
        qpin=jwrite(root/'QUERY.json',q)
        value={'schema':'cbramod_participant_packet_v1','task_id':api.TASK,'query':{'path':'QUERY.json',**qpin},
               'paper':{'path':'paper.txt',**self.panel['paper_text_pin']},'datasets':datasets}
        ppin=jwrite(root/'PACKET.json',value);copied=[]
        def stream(source,dest,row,end,cap):
            copied.append(row['path'])
            if row['path'].endswith('OBSERVATIONS.json'):dest.write_bytes(source.read_bytes())
            else:dest.write_text('generated file-envelope seam')
        with patch.object(sys.modules['streaming'],'copy',stream),patch.object(sys.modules['streaming'],'npy_envelope',lambda *a:None):
            got,receipt=packet.stage({'packet_root':str(root),'packet_pin':ppin,'public_bytes_limit':100_000_000},
                                     self.host,p/'out',time.monotonic()+30)
        self.assertEqual(got,q);self.assertEqual(receipt['primary_datasets'],12)
        self.assertEqual(len([n for n in copied if n.endswith('/labels.npy')]),24)
        self.assertFalse(any('/test/labels.npy' in n for n in copied))
        value['datasets'][-1]['test']['labels']={'path':'PRIVATE'};ppin=jwrite(root/'PACKET.json',value)
        with patch.object(sys.modules['streaming'],'copy',stream),patch.object(sys.modules['streaming'],'npy_envelope',lambda *a:None),\
             self.assertRaisesRegex(ValueError,'query label slot'):
            packet.stage({'packet_root':str(root),'packet_pin':ppin,'public_bytes_limit':100_000_000},self.host,p/'bad',time.monotonic()+30)

    def test_packet_refuses_query_private_path_before_read(self):
        p=self.fresh();root=p/'packet';root.mkdir()
        value={'schema':'cbramod_participant_packet_v1','task_id':api.TASK,
               'query':{'path':'private.npy','bytes':1,'sha256':'1'*64},'paper':{},'datasets':[]}
        ppin=jwrite(root/'PACKET.json',value)
        with self.assertRaisesRegex(ValueError,'public query identity'):
            packet.stage({'packet_root':str(root),'packet_pin':ppin},self.host,p/'out',time.monotonic()+30)

    def test_umask077_owned_projections_and_capture_readable(self):
        p=self.fresh();work=p/'work';work.mkdir(mode=0o700)
        before_source=stat.S_IMODE(OP.stat().st_mode);mask=os.umask(0o077)
        try:
            for arm in ('A','B'):
                out=work/('view-'+arm);self.host.stage_view(arm,out)
                executor.seal_public_projection(out,work)
                self.assertEqual(stat.S_IMODE(out.stat().st_mode),0o555)
                self.assertEqual(stat.S_IMODE((out/'VIEW.json').stat().st_mode),0o444)
                for path in out.rglob('*'):
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o555 if path.is_dir() else 0o444)
            root=work/'input';(root/'FACED/train').mkdir(parents=True,mode=0o755)
            (root/'FACED/train/labels.npy').write_bytes(b'generated permission member')
            executor.seal_public_projection(root,work)
            self.assertEqual(stat.S_IMODE((root/'FACED/train').stat().st_mode),0o555)
            self.assertEqual(stat.S_IMODE((root/'FACED/train/labels.npy').stat().st_mode),0o444)
            submission=make_submission(p/'source',self.host,self.q,'A');(p/'capture').mkdir()
            holder.capture(p/'source',p/'capture',api.expectation(self.host,self.q,'A'),time.monotonic()+30)
            self.assertEqual(stat.S_IMODE((p/'capture/predictions').stat().st_mode),0o755)
            self.assertTrue(all(stat.S_IMODE(x.stat().st_mode)==0o444 for x in (p/'capture/predictions').iterdir()))
        finally:os.umask(mask)
        self.assertEqual(stat.S_IMODE(work.stat().st_mode),0o700)
        self.assertEqual(stat.S_IMODE(OP.stat().st_mode),before_source)
        with self.assertRaisesRegex(ValueError,'Only executor-owned'):
            executor.seal_public_projection(OP,work)


if __name__=='__main__':
    print(json.dumps({'controls':'generated_only','numpy':np.__version__,'authentic_data_reads':0,
                      'docker_calls':0,'model_calls':0,'8GB_capacity_test':False,'program_flow':'fake daemon and staging seams; numerical scorer controls are real'}))
    unittest.main(verbosity=2)
