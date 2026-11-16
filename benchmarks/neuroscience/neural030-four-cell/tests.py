"""Generated full128-schedule controls; no real Docker or scientific campaign."""
import hashlib,json,os,subprocess,sys,tempfile,unittest,shutil
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import executor,native,holder,runtime_contract as contract,views,run,grading,budget

def save(path,value):
    raw=(json.dumps(value,allow_nan=False)+'\n').encode();path.write_bytes(raw)
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

class FakeDocker(native.Docker):
    """Known generated programme runs locally only in this test provider."""
    fault = None
    latest = None
    instances = []
    dispatches = 0
    inputs = []
    budgets = []

    def __init__(self, *args):
        super().__init__(*args); self.resources = {}; self.observed = []
        type(self).latest = self; type(self).instances.append(self)

    def call(self, argv, seconds=10):
        self.observed.append(argv)
        def answer(code=0, stdout='', stderr=''):
            return {'returncode': code, 'stdout': stdout, 'stderr': stderr}
        if argv[:2] == ['volume', 'inspect'] or argv[:3] == ['inspect', '--type', 'container']:
            name = argv[-1]
            if name not in self.resources:
                kind = 'volume' if argv[0] == 'volume' else 'object'
                return answer(1, '', f'Error: No such {kind}: {name}')
            return answer(stdout=json.dumps([self.resources[name]['info']]))
        if argv[:2] == ['volume', 'create']:
            name = argv[-1]; path = self.output.parent/('fake-' + name); path.mkdir()
            self.resources[name] = {'path': path, 'info': {'Name': name, 'Driver': 'local',
                'Options': {'type': 'tmpfs', 'device': 'tmpfs', 'o': contract.VOLUME_OPTIONS}}}
            return answer(stdout=name)
        if argv[0] == 'create':
            name = argv[argv.index('--name')+1]
            role = 'holder' if '/trusted/holder.py' in argv else 'candidate'
            mounts = {}
            for i, arg in enumerate(argv):
                if arg != '--mount':
                    continue
                bits = argv[i+1].split(','); fields = dict(x.split('=', 1) for x in bits if '=' in x)
                mounts[fields['dst']] = {'type': fields['type'], 'source': fields['src'], 'rw': 'readonly' not in bits}
            lim = contract.limits(role, self.r)
            h = {'NetworkMode': 'none', 'ReadonlyRootfs': True, 'Privileged': False,
                 'CapDrop': ['ALL'], 'CapAdd': None, 'SecurityOpt': ['no-new-privileges:true'],
                 'Devices': None, 'DeviceRequests': None, 'PortBindings': None, 'PidMode': '',
                 'IpcMode': 'private', 'AutoRemove': False, 'RestartPolicy': {'Name': 'no'},
                 'OomKillDisable': None, 'Memory': lim['memory'], 'MemorySwap': lim['memory'],
                 'NanoCpus': lim['nano_cpus'], 'PidsLimit': lim['pids'],
                 'Tmpfs': contract.TMPFS if role == 'candidate' else {},
                 'LogConfig': {'Type': 'local', 'Config': {'max-size': '64k', 'max-file': '1', 'compress': 'false'}},
                 'Ulimits': [{'Name': k, 'Soft': v[0], 'Hard': v[1]} for k, v in
                     {'cpu': (lim['cpu'], lim['cpu']+2), 'nofile': (1024,1024),
                      'core': (0,0), 'fsize': (100000000,100000000)}.items()],
                 'Mounts': [{'Type': v['type'], 'Source': v['source'], 'Target': k,
                            'ReadOnly': not v['rw'], 'VolumeOptions': {'NoCopy': True}} for k,v in mounts.items()]}
            effective = [{'Type': v['type'], 'Name': v['source'], 'Source': v['source'],
                          'Destination': k, 'RW': v['rw']} for k,v in mounts.items()]
            if role == 'candidate':
                effective += [{'Type':'tmpfs','Destination':'/tmp','RW':True}]
            info = {'Name': '/' + name, 'Id': name, 'Image': self.r['image'], 'HostConfig': h,
                    'Config': {'Image': self.r['image'], 'Entrypoint': ['python'], 'Cmd': contract.command(role),
                               'WorkingDir': '/' if role == 'holder' else '/output', 'User': '65534:65534',
                               'Env': [k+'=1' for k in contract.THREADS] + ['PYTHONDONTWRITEBYTECODE=1']},
                    'State': {'Status': 'created', 'Running': False, 'Pid': 0, 'OOMKilled': False, 'ExitCode': 0},
                    'NetworkSettings': {'Networks': {'none': {}}}, 'Mounts': effective}
            if self.fault == 'extra_mount' and role == 'candidate':
                info['Mounts'].append({'Type':'bind','Source':'/private','Destination':'/private','RW':False})
            self.resources[name] = {'info': info, 'role': role, 'mounts': mounts}
            return answer(stdout=name)
        if argv[0] == 'start':
            row = self.resources[argv[1]]; row['info']['State'].update(Status='running', Running=True, Pid=100)
            if row['role'] == 'candidate':
                mounts = row['mounts']; volume = self.resources[mounts['/output']['source']]['path']
                type(self).dispatches += 1
                type(self).inputs.append(Path(mounts['/input/public']['source'],'case.json').read_bytes())
                type(self).budgets.append(contract.limits('candidate',self.r))
                assert list(volume.iterdir()) == [], 'Fresh writable case state'
                if self.fault == 'last_failure' and type(self).dispatches == 128:
                    row['info']['State'].update(Status='exited', Running=False, Pid=0, ExitCode=7)
                    return answer()
                # Only this literal generated test fixture programme is run locally.
                call = subprocess.run([sys.executable, '-I', '-B', mounts['/program/candidate.py']['source'],
                    '--input', mounts['/input/public']['source'],
                    '--output', str(volume/'submission.json')], capture_output=True, timeout=5)
                row['info']['State'].update(Status='exited', Running=False, Pid=0, ExitCode=call.returncode)
            return answer()
        if argv[0] == 'wait':
            if self.fault == 'timeout':
                raise TimeoutError('generated wait failure')
            return answer(stdout=str(self.resources[argv[1]]['info']['State']['ExitCode'])+'\n')
        if argv[0] == 'rm':
            name = argv[-1]
            if self.fault == 'cleanup' and 'candidate' in name:
                return answer(1, '', 'generated removal failure')
            self.resources.pop(name, None); return answer()
        if argv[:2] == ['volume', 'rm']:
            self.resources.pop(argv[-1], None); return answer()
        if argv[0] == 'exec':
            self.assert_candidate_absent()
            mounts = self.resources[argv[1]]['mounts']
            volume = self.resources[mounts['/capture']['source']]['path']
            return answer(stdout=json.dumps(holder.capture(volume, Path(mounts['/export']['source']))))
        raise AssertionError(argv)

    def assert_candidate_absent(self):
        assert not any(x.get('role') == 'candidate' for x in self.resources.values())



class CompleteControls(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='neural030-generated-')
        self.base=Path(self.tmp.name).resolve();(self.base/'dockerconfig').mkdir()
        self.program=self.base/'generated.py'
        self.program.write_text("import argparse,json\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument('--input');p.add_argument('--output');a=p.parse_args()\nr=Path(a.input);r=r/'public' if (r/'public').exists() else r\nv=json.loads((r/'case.json').read_text());q=v['case']['query']\nassert not Path(a.output).exists()\nassert all('counts' not in t for t in q)\nPath(a.output).write_text(json.dumps([{'trial_id':t['trial_id'],'counts':[1]*round(t['delay_s']/.1)} for t in q]))\n")
        public={'schema':'neural030_cerebellar_public_v1','cases':[],
                'view_scope':'retrospective_processed_within_session_calibration','query_target_feedback':False}
        expected=[];private_cases=[];mapping={}
        i=0
        for condition,(delay,ncase) in views.GROUPS.items():
            for _ in range(ncase):
                sid='generated-session-'+str(i);mapping[sid]='generated-mouse-'+str(i%5)
                case={'session_id':sid,'condition':condition,'delay_s':delay,'train':[],'development':[],'query':[]}
                nb=round(delay/.1);case_expected=[];dispositions=[]
                for j in range(6):
                    split='train' if j<3 else 'development' if j==3 else 'query'
                    tid=sid+'-trial-'+str(j)
                    trial={'trial_id':tid,'session_id':sid,'trial_order':j+1,'delay_s':delay,'stage':condition,
                        'neural_time':[k/10 for k in range(nb)],'grc':[[0.]*nb], 'cf':[[0]*nb],
                        'handle_time':[k/200 for k in range(round(delay*200))],
                        'handle':[[0.]*(round(delay*200)) for k in range(2)]}
                    if split!='query':trial['counts']=[1]*nb
                    else:case_expected.append({'trial_id':tid,'session_id':sid,'bin_count':nb,'counts':[1]*nb})
                    dispositions.append({'trial_id':tid,'fold':split,'included':True})
                    case[split].append(trial)
                public['cases'].append(case);expected.extend(case_expected)
                private_cases.append({'session_id':sid,'expected':case_expected,'dispositions':dispositions,
                    'source_identity':{'generated':True},'authenticity_established':False})
                i+=1
        private={'schema':'neural030_cerebellar_private_v1','cases':private_cases,'expected':expected,
                 'mouse_binding':{'verification_status':'operator_attested','binding_id':'generated-only',
                    'evidence_sha256':'0'*64,'session_to_mouse':mapping},
                 'scientific_qualification':False,'input_authenticity_not_established_by_preparer':True}
        pub=save(self.base/'public.json',public);priv=save(self.base/'private.json',private)
        docker=self.base/'fake-docker';docker.write_bytes(b'NEVER EXECUTED')
        def pin(path):
            raw=path.read_bytes();return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        self.r={'schema':'neural030-fixed-adaptive-request-v1','fixed_program':str(self.program),
            'fixed_program_pin':pin(self.program),'adaptive_driver':str(self.program),'adaptive_driver_pin':pin(self.program),
            'public':str(self.base/'public.json'),'public_pin':pub,'private':str(self.base/'private.json'),'private_pin':priv,
            'grader_python':sys.executable,'docker':str(docker),'docker_pin':pin(docker),
            'docker_host':'unix:///generated-not-real.sock','docker_config':str(self.base/'dockerconfig'),
            'image':'sha256:'+'0'*64,'output':str(self.base/'run'),
            'candidate_wall_seconds':10,'grade_wall_seconds':30,'cleanup_wall_seconds':30,'whole_wall_seconds':21000,
            'candidate_cpu_seconds':10,'candidate_memory_bytes':536870912,'candidate_nano_cpus':1000000000,
            'host_memory_budget_bytes':2147483648,'retention_budget_bytes':68719476736,
            'submission_cap_bytes':1048576}
        FakeDocker.fault=None;FakeDocker.instances=[];FakeDocker.dispatches=0;FakeDocker.inputs=[];FakeDocker.budgets=[]
        source=(HERE/'SOURCE_MANIFEST.json').read_bytes();self.source=source
        self.bodies={n:(HERE/n).read_bytes() for n in json.loads(source)['files']}

    def tearDown(self):self.tmp.cleanup()

    def run_generated(self):
        command=native.bounded_command
        def guarded(argv,*args,**kwargs):
            # Real trusted grader is exercised, but no native Docker is invoked.
            assert FakeDocker.dispatches==128
            assert all(not engine.resources for engine in FakeDocker.instances)
            return command(argv,*args,**kwargs)
        with patch.object(native,'Docker',FakeDocker),patch.object(native,'bounded_command',guarded):
            return executor.execute(self.r,self.bodies,self.source)

    def test_complete128_equal_inputs_budgets_fresh_state_actual_scorer(self):
        result=self.run_generated();self.assertEqual(result['dispatches'],128)
        self.assertEqual(len(FakeDocker.instances),128)
        self.assertEqual(FakeDocker.inputs[:64],FakeDocker.inputs[64:])
        self.assertTrue(all(x==FakeDocker.budgets[0] for x in FakeDocker.budgets))
        self.assertEqual(len({engine.owned[0][1] for engine in FakeDocker.instances}),128)
        grade=json.loads((Path(self.r['output'])/'grade.json').read_text())
        for mode in views.MODES:
            self.assertEqual(set(grade['candidates'][mode]),set(views.ARMS))
            for arm in views.ARMS:
                g=grade['candidates'][mode][arm]
                self.assertEqual(len(g['trial_results']),32);self.assertEqual(len(g['session_results']),16)
                self.assertEqual(len(g['mouse_results']),5);self.assertEqual(g['mouse_macro']['mse'],0)
        for index,raw in enumerate(FakeDocker.inputs):
            value=json.loads(raw);arm=value['arm']
            for split in ('train','development','query'):
                for trial in value['case'][split]:
                    self.assertEqual('grc' in trial,arm in ('grc','joint'))
                    self.assertEqual('cf' in trial,arm in ('cf','joint'))
                    self.assertEqual('counts' in trial,split!='query')

    def test_final128th_failure_never_enters_private_grading(self):
        FakeDocker.fault='last_failure'
        with self.assertRaises(ValueError):self.run_generated()
        self.assertEqual(FakeDocker.dispatches,128)
        self.assertTrue(all(not e.resources for e in FakeDocker.instances))
        self.assertFalse((Path(self.r['output'])/'PANEL.json').exists())
        self.assertFalse((Path(self.r['output'])/'grade-process.json').exists())

    def test_extra_mount_and_cleanup_fail_closed(self):
        for fault in ('extra_mount','cleanup','timeout'):
            FakeDocker.fault=fault;self.r['output']=str(self.base/('run-'+fault))
            with self.assertRaises((ValueError,TimeoutError)):self.run_generated()
            self.assertFalse((Path(self.r['output'])/'PANEL.json').exists())
            shutil.rmtree(self.r['output'])

    def test_program_pin_and_complete_session_population_before_native(self):
        self.r['fixed_program_pin']['sha256']='f'*64
        with self.assertRaises(ValueError):self.run_generated()
        self.assertEqual(FakeDocker.dispatches,0)
        self.r['fixed_program_pin']['sha256']=hashlib.sha256(self.program.read_bytes()).hexdigest()
        self.r['output']=str(self.base/'incomplete')
        public=json.loads((self.base/'public.json').read_text());public['cases'].pop()
        self.r['public_pin']=save(self.base/'public.json',public)
        with self.assertRaises(ValueError):self.run_generated()
        self.assertEqual(FakeDocker.dispatches,0)

    def test_missing_duplicate_wrong_count_vectors(self):
        public=json.loads((self.base/'public.json').read_text());case=public['cases'][0]
        good=[{'trial_id':t['trial_id'],'counts':[1]*10} for t in case['query']]
        for bad in (good[:1],good+[good[0]],[good[0],good[0]],
                    [{'trial_id':good[0]['trial_id'],'counts':[1]*9},good[1]]):
            with self.assertRaises(ValueError):views.predictions(bad,case)

    def test_private_not_read_if_panel_missing(self):
        Path(self.r['output']).mkdir()
        original=grading.read_pinned
        def watch(path,*args,**kwargs):
            if str(path)==self.r['private']:raise AssertionError('private opened')
            return original(path,*args,**kwargs)
        with patch.object(grading,'read_pinned',watch),self.assertRaises(FileNotFoundError):grading.grade(self.r)

    def test_shape_admission_refuses_dense_reference_before_dispatch(self):
        public=json.loads((self.base/'public.json').read_text())
        for split in ('train','development','query'):
            for trial in public['cases'][0][split]:trial['grc']=[trial['grc'][0]]*20000
        views.validate(public)
        with self.assertRaisesRegex(ValueError,'dimension-derived'):budget.admit(public,self.r)
        self.assertEqual(FakeDocker.dispatches,0)

    def test_cleanup_record_failure_preserves_original_timeout(self):
        FakeDocker.fault='timeout';original=executor.safe.write_new
        def fail(path,*args,**kwargs):
            if Path(path).name=='closure.json':raise OSError('generated closure evidence error')
            return original(path,*args,**kwargs)
        with patch.object(executor.safe,'write_new',fail),self.assertRaises(TimeoutError) as caught:self.run_generated()
        self.assertTrue(any('Closure preservation failed' in n for n in caught.exception.__notes__))
        result=json.loads((Path(self.r['output'])/'RESULT.json').read_text())
        self.assertIn('TimeoutError',result['error'])

    def test_declared_output_cap_precedes_host_submission_parse(self):
        original=holder.capture
        def oversized(*args,**kwargs):
            result=original(*args,**kwargs);result['bytes']=self.r['submission_cap_bytes']+1;return result
        with patch.object(holder,'capture',oversized),self.assertRaisesRegex(ValueError,'Exact bounded pin'):self.run_generated()
        self.assertFalse((Path(self.r['output'])/'jobs/0-0-00/submission.json').exists())

    def test_private_metadata_waits_for_all128_closures_and_late_symlink_refuses(self):
        protected=self.base/'operator-private';protected.mkdir()
        target=protected/'targets.json';target.write_bytes(Path(self.r['private']).read_bytes())
        self.r['private']=str(target);observed=[]
        original_symlink=Path.is_symlink;original_lstat=Path.lstat
        def guarded(original,name):
            def check(path,*args,**kwargs):
                if path==protected or protected in path.parents:
                    self.assertEqual(FakeDocker.dispatches,128,'private metadata before all128 dispatches')
                    self.assertTrue(all(not e.resources for e in FakeDocker.instances),'private metadata before closure')
                    observed.append((name,str(path)))
                return original(path,*args,**kwargs)
            return check
        def inprocess_trusted_grade(argv,*args,**kwargs):
            self.assertEqual(FakeDocker.dispatches,128)
            self.assertTrue(all(not e.resources for e in FakeDocker.instances))
            request=json.loads(Path(argv[argv.index('--request')+1]).read_text())
            result=grading.grade(request)
            return {'returncode':0,'stdout':json.dumps(result),'stderr':''}
        with patch.object(Path,'is_symlink',guarded(original_symlink,'is_symlink')), \
             patch.object(Path,'lstat',guarded(original_lstat,'lstat')), \
             patch.object(native,'Docker',FakeDocker),patch.object(native,'bounded_command',inprocess_trusted_grade):
            result=executor.execute(self.r,self.bodies,self.source)
            self.assertEqual(result['dispatches'],128)
            self.assertEqual({x[0] for x in observed},{'is_symlink','lstat'})
            bad=protected/'linked.json';bad.symlink_to(target)
            malformed=dict(self.r,private=str(bad))
            FakeDocker.dispatches=0
            executor.validate_request(malformed)  # Lexical admission does not inspect the link.
            FakeDocker.dispatches=128
            with self.assertRaisesRegex(ValueError,'ordinary path without symlink'):
                grading.grade(malformed)

    def test_owned_case_permissions_under_umask077(self):
        original_modes={name:Path(self.r[name]).stat().st_mode for name in ('public','private','fixed_program')}
        def inspect_views(*args,**kwargs):
            root=Path(self.r['output'])/'cases'
            self.assertEqual(root.stat().st_mode & 0o777,0o755)
            self.assertEqual(len(list(root.iterdir())),64)
            for case in root.iterdir():
                self.assertEqual(case.stat().st_mode & 0o777,0o755)
                self.assertEqual((case/'case.json').stat().st_mode & 0o777,0o444)
            raise RuntimeError('generated permission-only stop')
        previous=os.umask(0o077)
        try:
            with patch.object(executor,'invoke',inspect_views),self.assertRaisesRegex(RuntimeError,'permission-only'):
                executor.execute(self.r,self.bodies,self.source)
        finally:
            os.umask(previous)
        for name,mode in original_modes.items():self.assertEqual(Path(self.r[name]).stat().st_mode,mode)
        self.assertEqual(FakeDocker.dispatches,0)

    def test_shared_pid_ipc_modes_refused(self):
        import copy,time
        folder=self.base/'namespace-control';folder.mkdir()
        engine=FakeDocker(self.r,folder,time.monotonic()+30)
        mounts={'/program/candidate.py':{'type':'bind','source':str(self.program),'rw':False},
            '/input/public':{'type':'bind','source':str(self.base),'rw':False},
            '/output':{'type':'volume','source':'generated-volume','rw':True}}
        try:
            engine.create('generated-isolated-candidate','candidate',mounts)
            info=engine.resources['generated-isolated-candidate']['info']
            argv=contract.create_argv('generated-isolated-candidate','candidate',mounts,self.r)
            self.assertEqual(argv[argv.index('--ipc')+1],'private')
            for field,values in [('PidMode',('host','container:other','private')),
                                 ('IpcMode',('host','container:other','shareable',''))]:
                for value in values:
                    altered=copy.deepcopy(info);altered['HostConfig'][field]=value
                    with self.assertRaisesRegex(ValueError,'fresh private process/IPC'):
                        contract.verify(altered,'generated-isolated-candidate','candidate',mounts,self.r)
        finally:
            self.assertEqual(engine.close(),[])
        self.assertEqual(FakeDocker.dispatches,0)

    def test_private_role_aliases_refuse_before_any_filesystem_check(self):
        executor.validate_request(self.r)
        early=[self.r[name] for name in ('fixed_program','adaptive_driver','public','docker',
                                        'docker_config','grader_python','output')]
        early.append(self.r['docker_host'][7:])
        def forbidden(*args,**kwargs):
            raise AssertionError('filesystem check before private-role alias refusal')
        with patch.object(Path,'is_symlink',forbidden),patch.object(Path,'lstat',forbidden):
            for operand in early:
                for private in (operand,str(Path(operand).parent),operand+'/private-target.json'):
                    with self.subTest(operand=operand,private=private),self.assertRaisesRegex(ValueError,'Private operand disjoint'):
                        executor.validate_request(dict(self.r,private=private))
        self.assertEqual(FakeDocker.dispatches,0)

    def test_double_root_operands_refuse_before_filesystem_checks(self):
        def forbidden(*args,**kwargs):
            raise AssertionError('filesystem check before canonical-root refusal')
        altered=[dict(self.r,private='//'+self.r['public'].lstrip('/'))]
        for name in ('fixed_program','adaptive_driver','public','docker','docker_config','grader_python','output'):
            altered.append(dict(self.r,**{name:'//'+self.r[name].lstrip('/')}))
        altered.append(dict(self.r,docker_host='unix:////generated-not-real.sock'))
        with patch.object(Path,'is_symlink',forbidden),patch.object(Path,'lstat',forbidden):
            for request in altered:
                with self.assertRaisesRegex(ValueError,'Canonical lexical'):
                    executor.validate_request(request)
        self.assertEqual(FakeDocker.dispatches,0)

if __name__=='__main__':unittest.main(verbosity=2)
