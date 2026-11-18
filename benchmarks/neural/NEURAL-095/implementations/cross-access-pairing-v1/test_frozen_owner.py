"""Generated owner/collection controls; no authentic payload or native launch."""
import base64
import ast
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
I = Path(os.environ['NEURAL095_IMPLEMENTATIONS']).absolute()
P = I / 'neural-095-four-cell-runner'
WRITTEN = 0


def load(name, path, body=None, injected=None):
    m = types.ModuleType(name); m.__file__ = str(path)
    m.__dict__.update(injected or {}); sys.modules[name] = m
    exec(compile(path.read_bytes() if body is None else body, str(path), 'exec'), m.__dict__)
    return m


collection_body = (HERE / 'frozen_collection.py').read_bytes()
owner = load('_test_frozen_owner', HERE / 'frozen_owner.py', injected={'COLLECTION_SOURCE': collection_body})
collection = load('_test_frozen_collection', HERE / 'frozen_collection.py', collection_body)
BASE, Q = owner.BASE, owner.Q
IDS = tuple('dmfc-%06d' % i for i in range(258))
NUMERIC = b'# Generated candidate syntax only; numerical infrastructure is explicitly stubbed.\n'


def operator():
    image = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
    return {'schema': 'dmfc-portable-deployment/v1', 'output_relative': 'artifacts-build/run',
        'runtime_identity': {'transport': {'docker': '/generated/docker', 'environment': {
            'PATH': '/usr/bin:/bin', 'HOME': '/generated/home', 'TMPDIR': '/generated/tmp',
            'LANG': 'C', 'LC_ALL': 'C', 'DOCKER_HOST': 'unix:///generated/socket', 'DOCKER_CONFIG': '/generated/config'}},
            'server': {'ID': 'generated', 'Name': 'generated', 'ServerVersion': 'generated', 'OSType': 'linux', 'Architecture': 'arm64'},
            'image': {'reference': image, 'Id': image, 'Os': 'linux', 'Architecture': 'arm64'}}}


def write(path, body):
    global WRITTEN
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        n = f.write(body); WRITTEN += n
        if n != len(body): raise ValueError('partial generated fixture')


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = Path(tempfile.mkdtemp(prefix='f95', dir=Path('/tmp').resolve()))
        cls.destination = cls.temp / 'r'
        helper = owner.capture(P / 'configure.py').decode()
        start = helper.index('    # All validation/rendering happens before the one fresh destination is created.\n')
        end = helper.index('\n\ndef main(', start)
        helper = helper[:start] + "    return {'bodies': bodies, 'payload': payload}\n" + helper[end:]
        cls.c = load('_test_original_configure', P / 'configure.py', helper.encode())
        rendered = cls.c.configure(operator(), cls.destination, P)
        cls.original = rendered['bodies']
        method = cls.original[BASE + '/numerical-policy/METHOD.json']
        gate = load('_test_review', P / 'source' / owner.GATE / 'candidate_admission.py', cls.original[owner.GATE + '/candidate_admission.py'])
        reader = load('_test_method', P / 'source/authoring/dmfc-timing/paired-program-cli-v1/admission.py',
            cls.original['authoring/dmfc-timing/paired-program-cli-v1/admission.py'], {'need': owner.need, 'decode': owner.decode, 'json': json})
        review = {'schema': 'dmfc-external-candidate-review/v1', 'candidate_id': 'NEURAL-095',
            'decision': 'source_and_procedure_reviewed_for_original_contract', 'execution_authority': False,
            'matched_method_proven_by_grader': False, 'base_owner_freeze': gate.BASE_FREEZE,
            'public_contract': gate.CONTRACT, 'program': {'path': BASE + '/frozen-candidate/program.py', **owner.pin(NUMERIC)},
            'method': {'path': BASE + '/frozen-candidate/METHOD.json', **owner.pin(method)},
            'reviewer': 'Generated control only', 'findings': 'Synthetic wiring, not candidate scientific approval.',
            'checks': dict.fromkeys(gate.CHECKS, True),
            'method_field_findings': dict.fromkeys(reader.METHOD_FIELDS, 'Synthetic source-binding assertion only.')}
        cls.raw = {'program': NUMERIC, 'method': method, 'review': owner.encode(review)}
        cls.expected = {k: owner.pin(v) for k, v in cls.raw.items()}
        with patch('subprocess.Popen', side_effect=AssertionError('assembly never launches')):
            cls.assembled = owner.assemble(I, operator(), cls.destination, **cls.raw, expected=cls.expected)
        cls.bodies = cls.assembled['bodies']; cls.payload = cls.assembled['payload']
        cls.api = load('_test_original_cell', P / 'source' / BASE / 'adaptive_producer.py', cls.original[BASE + '/adaptive_producer.py'])
        cls.live = load('_test_original_live', P / 'source' / Q / 'dmfc-live-four-cell-transport-20261115-v1/live_adapter.py',
            cls.original[Q + '/dmfc-live-four-cell-transport-20261115-v1/live_adapter.py'])
        cls.backend_module = load('_test_original_actor_backend', P / 'source' / BASE / 'actor_backend.py',
            cls.original[BASE + '/actor_backend.py'], {'live': cls.live})

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp)
        print('GENERATED_WRITTEN_BYTES=' + str(WRITTEN), flush=True)
        print('OBSERVED_PYTHON=' + sys.version.replace('\n', ' '), flush=True)

    def test_01_in_memory_assembly_preserves_original_science_and_limits(self):
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.payload['collection_mode'], owner.MODE)
        self.assertEqual(set(self.payload['actor']['arms']), set(owner.CONTEXTS))
        original_config = load('_original_limits', P / 'source' / BASE / 'configuration.py', self.original[BASE + '/configuration.py'])
        self.assertEqual(self.payload['limits'], original_config.LIMITS)
        for name in ('adaptive_producer.py', 'actor_backend.py', 'offline_actor.py'):
            self.assertEqual(self.bodies[BASE + '/' + name], self.original[BASE + '/' + name])
        self.assertNotIn(b'PairedEvaluator(', self.bodies[BASE + '/controller.py'])
        profile = owner.decode(self.bodies[BASE + '/OPERATION_PROFILE.json'])
        self.assertEqual((profile['whole_seconds'], profile['work_seconds'], profile['maximum_numerical_units']), (4800, 4200, 6))
        freeze = owner.decode(self.bodies[BASE + '/SOURCE_FREEZE.json'])
        self.assertEqual(freeze['scientific_scope']['reference_count'], 5)
        self.assertEqual(freeze['scientific_scope']['gradings_in_collection'], 0)
        self.assertEqual(self.assembled['deployment']['core_member_count'], len(freeze['files']))

    def test_02_reviewed_operands_must_equal_selected_operands(self):
        review = owner.decode(self.raw['review'])
        review['program'] = {'path': BASE + '/numerical-policy/program.py', **owner.pin(self.original[BASE + '/numerical-policy/program.py'])}
        changed = {**self.raw, 'review': owner.encode(review)}
        with self.assertRaises(ValueError):
            owner.assemble(I, operator(), self.destination, **changed, expected={k: owner.pin(v) for k,v in changed.items()})

    def test_03_manifest_second_read_uses_captured_first_bytes(self):
        original = owner.capture; count = [0]
        def read(path, cap=1048576):
            if Path(path) == P / 'SOURCE_MANIFEST.json': count[0] += 1
            return original(path, cap)
        with patch.object(owner, 'capture', read):
            owner.assemble(I, operator(), self.destination, **self.raw, expected=self.expected)
        self.assertEqual(count[0], 1)

    def test_04_real_cells_backend_and_offline_actor_complete_two_views(self):
        api, live, backend_module = self.api, self.live, self.backend_module
        output = self.temp / 'collection'; output.mkdir()
        manifest = copy.deepcopy(api.load_manifest())
        memory = {}; source = self.original[BASE + '/offline_actor.py']
        identity_path = self.temp / 'generated_identity.json'
        identity_body = owner.encode({'schema_version': 1, 'case_id': IDS})
        memory[identity_path] = identity_body
        manifest['evaluator_only_assets']['identity'] = {'path': str(identity_path), **owner.pin(identity_body)}
        for view in owner.VIEWS:
            rows = []
            for name, mount in (('train.npz','train.npz'),('query.npz','query.npz'),('schema.json','schema.json'),('units.json','units.json'),('contract.json','contract.json')):
                path = self.temp / 'generated' / view / name
                raw = owner.encode({'generated': view + '/' + name, 'training': 748, 'queries': 258, 'neural_shape': [4,40]})
                memory[path] = raw
                rows.append({'path': str(path), **owner.pin(raw), 'mount_destination': '/input/' + mount, 'read_only': True})
            manifest['public_views'][view]['public_inputs'] = rows
        original_read, original_write = live.read, live.write
        def virtual_read(path, expected=None, cap=1048576):
            body = memory.get(Path(path))
            if body is None: return original_read(path, expected, cap)
            if expected is not None: self.assertEqual((len(body), hashlib.sha256(body).hexdigest()), tuple(expected))
            return body
        def generated_write(path, body, cap=1048576):
            self.assertLessEqual(len(body), cap); write(Path(path), body)
            return live.pin(path, body)
        events, actors, backends, units = [], [], [], []
        class Executor:
            def absence(self): return True
            def execute(_self, numeric, inputs, *, output_name, **kwargs):
                units.append((numeric, copy.deepcopy(inputs), output_name))
                if output_name == 'submission.npz':
                    self.assertTrue(all(p.poll() == 0 for p in actors))
                    events.append('export')
                    return Path(inputs[0]['path']).read_bytes(), 0
                self.assertEqual(numeric, NUMERIC)
                op = owner.decode(Path(next(x['path'] for x in inputs if x['mount_destination'] == '/input/operation.json')).read_bytes())
                if op['operation'] == 'prepare':
                    self.assertNotIn('/input/query.npz', [x['mount_destination'] for x in inputs])
                    result = {'artifact_base64': base64.b64encode(b'generated-training-fit').decode()}
                else:
                    self.assertEqual(op['operation'], 'tool'); self.assertEqual(op['payload']['arguments'], {})
                    result = {'case_id': list(IDS), 'prediction_ms': [-1.0 + i / 8 for i in range(258)]}
                return owner.encode({'payload': result, 'state': None}), 0
        launcher = output / 'actor_launcher.py'
        write(launcher, b"import builtins,pathlib,sys\np=pathlib.Path(sys.argv[1]); b=p.read_bytes(); old=builtins.__import__\ndef imp(n,*a,**k):\n if n=='pathlib':\n  import types\n  return types.SimpleNamespace(Path=lambda x:p if x=='/actor/program.py' else pathlib.Path(x))\n return old(n,*a,**k)\nexec(compile(b,str(p),'exec'),{'__name__':'__main__','__builtins__':dict(vars(builtins),__import__=imp)})\n")
        actor_source = output / 'actor.py'; write(actor_source, source)
        class Channel:
            def __init__(_self): _self.proc = None
            def accept(_self, until): self.assertIsNotNone(_self.proc)
            def receive(_self, expected, until):
                with selectors.DefaultSelector() as s:
                    s.register(_self.proc.stdout, selectors.EVENT_READ)
                    self.assertTrue(s.select(max(.001, min(5, until-time.monotonic()))))
                message = owner.decode(_self.proc.stdout.readline(65537))
                self.assertEqual(message['op'], expected)
                return message.get('source') if expected == 'freeze' else message.get('request')
            def answer(_self, value, until, status='ok'):
                reply = {'status': status, **value} if status == 'committed' else {'status': status, 'payload': value}
                _self.proc.stdin.write(owner.encode(reply)+b'\n'); _self.proc.stdin.flush()
            def close(_self):
                for stream in (_self.proc.stdin, _self.proc.stdout, _self.proc.stderr): stream.close()
        def factory(mode, view):
            def actor_factory(started, deadline, backend):
                channel = Channel()
                class Actor:
                    def launch(_self):
                        _self.proc = subprocess.Popen([sys.executable,'-I','-B',str(launcher),str(actor_source)],
                            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0,
                            env={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C'})
                        actors.append(_self.proc); channel.proc = _self.proc
                        _self.proc.stdin.write(owner.encode({'schema':'dmfc-offline-reference/v1',
                            'mode':mode+'__'+view,'tool_id':tool,'policy':owner.POLICY})+b'\n'); _self.proc.stdin.flush()
                    def stop(_self):
                        self.assertEqual(_self.proc.wait(timeout=5),0)
                        events.append('actor-stopped'); return {'absence_verified':True}
                return Actor(), channel
            backend = backend_module.ActorBackend(api=api, mode=mode,view=view,executor=Executor(),
                output=output/view,tools={tool:NUMERIC},case_ids=IDS,limits=limits,reservations=reservations,
                comparison_id='generated-comparison',actor_factory=actor_factory,preparation_tool_id=tool,
                _engineering_fixture=True)
            backends.append(backend); return backend
        limits = api.Limits(api.Usage(**self.payload['limits']['total']), api.Usage(**self.payload['limits']['preparation']),
            self.payload['limits']['wall_us'],self.payload['limits']['preparation_wall_us'],
            self.payload['limits']['max_memory_bytes'],self.payload['limits']['response_bytes'])
        reservations = {k:api.Usage(**v) for k,v in self.payload['reservation_policy'].items()}
        tool = 'dmfc_predict@'+owner.pin(NUMERIC)['sha256']; sealed=[]
        def seal(pair):
            self.assertTrue(all(b.closed and b.actor_absent for b in backends))
            sealed.append(copy.deepcopy(pair)); return owner.pin(owner.encode(pair))['sha256']
        try:
            with patch.object(api,'load_manifest',return_value=manifest), patch.object(live,'read',virtual_read), \
                 patch.object(live,'write',generated_write), patch.object(live.PairedEvaluator,'__init__',side_effect=AssertionError('no evaluator')):
                study=collection.FrozenPairCollection(api=api,source=source,method=self.raw['method'],case_ids=IDS,
                    limits=limits,reservations=reservations,tool_ids=(tool,),backend_factory=factory,
                    comparison_id='generated-comparison',seal=seal)
                result=study.run()
                with self.assertRaises(ValueError): study.run()
            self.assertEqual(result['status'],collection.STATUS)
            self.assertEqual(len(units),6); self.assertEqual([b.decisions for b in backends],[258,258])
            self.assertEqual([b.tool_calls for b in backends],[1,1])
            self.assertEqual(events,['actor-stopped','export','actor-stopped','export'])
            self.assertEqual(sealed[0]['case_ids'],list(IDS))
            self.assertEqual(sealed[0]['private_grades_so_far'],0)
            self.assertEqual(study.outputs['cue_only'],study.outputs['neural'])
            self.assertEqual(study.outputs['neural'],api.submission_npz(IDS,tuple(-1.0+i/8 for i in range(258))))
        finally:
            for p in actors:
                if p.poll() is None: p.kill(); p.wait(timeout=3)
                for s in (p.stdin,p.stdout,p.stderr):
                    if not s.closed:s.close()

    def test_05_changed_public_or_fitted_mount_refused(self):
        deployment, folder = self.temp / 'unused', self.temp / 'unused/cells/neural'
        row = {'path':'public/query.npz','bytes':17,'sha256':'a'*64,
               'mount_destination':'/input/query.npz','read_only':True}
        fitted = {'bytes':8,'sha256':'b'*64}
        expected = [{**row,'path':str(deployment / row['path'])},
            {'path':str(folder/'fitted.bin'),**fitted,'mount_destination':'/input/fitted.bin','read_only':True},
            {'path':str(folder/'request-0001.json'),'bytes':23,'sha256':'c'*64,
             'mount_destination':'/input/operation.json','read_only':True}]
        self.assertEqual(owner.validate_mounts(deployment,folder,{'public_inputs':[row]},expected,'tool',fitted),expected[-1])
        for index, key, changed in ((0,'sha256','d'*64),(0,'path','/private/targets.npz'),(0,'read_only',False),
                                    (1,'sha256','e'*64),(1,'path','/private/targets.npz'),
                                    (2,'path','/private/targets.npz')):
            bad=copy.deepcopy(expected);bad[index][key]=changed
            with self.subTest(index=index,key=key), self.assertRaises(ValueError), \
                 patch.object(owner,'capture',side_effect=AssertionError('mount admission must never read')):
                owner.validate_mounts(deployment,folder,{'public_inputs':[row]},bad,'tool',fitted)

    def test_06_opaque_export_rejects_extra_or_changed_inputs(self):
        folder=self.temp/'unused'; p={'bytes':100,'sha256':'a'*64}
        writer=b"from pathlib import Path\nPath('/output/submission.npz').write_bytes(Path('/input/opaque.bin').read_bytes())\n"
        intent={'program':owner.pin(writer),'unit':{'output_filename':'submission.npz','max_output_bytes':1048576,
            'public_inputs':[{'path':str(folder/'opaque-output.bin'),**p,'mount_destination':'/input/opaque.bin','read_only':True}]}}
        owner.validate_export(folder,intent,p)
        for change in ('source','extra','path','cap'):
            bad=copy.deepcopy(intent)
            if change=='source':bad['program']['sha256']='b'*64
            if change=='extra':bad['unit']['public_inputs'].append({'path':'private-targets'})
            if change=='path':bad['unit']['public_inputs'][0]['path']='/private/targets.npz'
            if change=='cap':bad['unit']['max_output_bytes']=1048577
            with self.subTest(change=change),self.assertRaises(ValueError):owner.validate_export(folder,bad,p)

    def _outer(self, name, unit_count=6, group_absent=True, inner_status=collection.STATUS):
        op=load('_actual_outer_'+name,self.destination/BASE/'operation_owner.py',self.bodies[BASE+'/operation_owner.py'])
        out=self.temp/('outer-'+name)
        profile=owner.decode(self.bodies[BASE+'/OPERATION_PROFILE.json'])
        config=types.SimpleNamespace(started_monotonic=time.monotonic(),value={**self.payload,'output_root':str(out)},
            sha256='a'*64,request_sha256='b'*64,source_path=self.temp/'generated-config.json',bootstrap_read_bytes=0)
        req={'profile':{'path':'GENERATED_PROFILE','bytes':1,'sha256':'c'*64},'prior_known_seconds':0,'family_ceiling_seconds':4800}
        events=[]; controller={'path':BASE+'/controller.py',**owner.pin(self.bodies[BASE+'/controller.py'])}
        class Budget:
            def __init__(self,*args):pass
            def write(self,path,body,**kwargs):write(Path(path),body)
        class Process:
            pid=123456789
            def poll(self):return 0
        class ProcessOwner:
            def launch(self,argv,folder,seconds,desc):
                self_test.assertEqual(desc,controller)
                write(folder/'process_owner.json',owner.encode({'token':'generated'}))
                write(folder/'process_completion.json',owner.encode({'token':'generated','returncode':0,'group_leader_waits_for_owner_stop':True}))
                write(out/'controller_result.json',owner.encode({'schema':'dmfc-frozen-pair-ungraded-controller-result/v1',
                    'config_sha256':config.sha256,'request_sha256':config.request_sha256,'status':inner_status,
                    'study_result':{'status':inner_status}}))
                events.append('launch');return Process()
            def read(self,path):return owner.decode(Path(path).read_bytes())
            def stop(self,folder,until,proc=None):events.append('main-stop');return {'absence_verified':group_absent}
        self_test=self
        entry=types.SimpleNamespace(captured_descriptor=lambda *a:controller,
            group_stop=lambda owner,folder,until: (events.append('creator-stop:'+folder.parent.name) or {'absence_verified':True}))
        stack=types.SimpleNamespace(entrypoint=entry,live=object(),actor_runtime=types.SimpleNamespace(
            recover_mode=lambda config,stack,runtime,key,budget,until:(events.append('actor-recover:'+key) or {'absence_verified':True})))
        runtime=types.SimpleNamespace(HostBudget=Budget,root=self.destination,owner=ProcessOwner(),
            verify_identity=lambda *a: {'generated_only':True})
        guard=types.SimpleNamespace(recovery=False,report=lambda:{'generated_only':True})
        def numerical(*a):
            events.append('numerical-recover');return {'all_owned_absent':True,'unit_family_identity_valid':True,
                'all_unit_commits_verified':True,'unit_count':unit_count}
        with patch.object(op,'admit',return_value=(profile,req,{'generated_only':True})), \
             patch.object(op,'install_managed_reads',return_value=guard),patch.object(op,'recover_numerical',numerical), \
             patch.object(op.signal,'getitimer',return_value=(0.0,0.0)),patch.object(op.signal,'setitimer'), \
             patch.object(op.signal,'signal',return_value=None),patch('subprocess.Popen',side_effect=AssertionError('no native launch')):
            result=op.run_operation(config,stack,runtime)
        return result,events,out

    def test_07_actual_outer_accepts_exact_six_after_all_creators_close(self):
        result,events,out=self._outer('six')
        self.assertEqual(result['status'],'complete_frozen_pair_ungraded_operation')
        self.assertTrue(result['all_owned_absent']);self.assertEqual(result['charged_seconds'],4800)
        self.assertEqual(events,['launch','main-stop',*('creator-stop:'+k for k in owner.CONTEXTS),
            *('actor-recover:'+k for k in owner.CONTEXTS),'numerical-recover'])
        self.assertEqual(owner.decode((out/'OUTER_RESULT.json').read_bytes()),result)

    def test_08_actual_outer_rejects_incomplete_extra_and_old_scored_cells(self):
        for name,count,status in (('five',5,collection.STATUS),('seven',7,collection.STATUS),('old',6,'four_cell_outputs_scored')):
            result,events,out=self._outer(name,count,inner_status=status)
            with self.subTest(name=name):self.assertEqual(result['status'],'failed_preserved')

    def test_09_actual_outer_creator_failure_prevents_native_recovery(self):
        result,events,out=self._outer('group-failure',group_absent=False)
        self.assertEqual(result['status'],'failed_preserved')
        self.assertNotIn('numerical-recover',events)
        self.assertFalse(any(x.startswith('actor-recover') for x in events))
        self.assertEqual(events[-2:],['creator-stop:'+k for k in owner.CONTEXTS])

    def test_10_old_scored_configuration_refused_before_module_or_payload(self):
        body=owner.encode({'schema':'dmfc-complete-four-cell-config/v1'})
        selection={'deployment_root':str(self.destination),'configuration':{'path':'CONFIG.json',**owner.pin(body)},
                   'source_freeze':{'path':BASE+'/SOURCE_FREEZE.json','bytes':1,'sha256':'a'*64},'outer_result':{'bytes':1,'sha256':'b'*64}}
        with patch.object(owner,'checked',return_value=body) as reads, \
             patch.object(owner,'module',side_effect=AssertionError('old closure cannot import')),self.assertRaises(ValueError):
            owner.validate_closed(self.temp/'run',selection)
        self.assertEqual(reads.call_count,1)

    def closed_fixture(self):
        """Complete in-memory metadata graph; native/source filesystem is stubbed.

        Real selected configuration.load, process_owner.expected, read_intent,
        original completed_unit, actor constructor and Cell.specification run.
        No deployment or neural arrays are written. This is not native proof.
        """
        deployment=self.destination; root=deployment/'artifacts-build/run'; memory={}
        def put(path,value):
            body=value if type(value) is bytes else owner.encode(value)
            memory[Path(path)]=body;return owner.pin(body)
        def read(path,cap=1048576):
            path=Path(path)
            if path not in memory:raise AssertionError('unexpected fixture read: '+str(path))
            body=memory[path];self.assertLessEqual(len(body),cap);return body
        bodies=dict(self.bodies); manifest=copy.deepcopy(self.api.load_manifest())
        identity={'path':'generated/identity.json',**put(deployment/'generated/identity.json',{'schema_version':1,'case_id':IDS})}
        manifest['evaluator_only_assets']['identity']=identity
        # Protected assets deliberately point to forbidden, absent memory keys.
        for k in manifest['evaluator_only_assets']:
            if k!='identity':manifest['evaluator_only_assets'][k]={'path':'FORBIDDEN/'+k,'bytes':1,'sha256':'f'*64}
        for view in owner.VIEWS:
            manifest['public_views'][view]['public_inputs']=[{'path':'generated/'+view+'/'+name,
                'bytes':100+i,'sha256':hashlib.sha256((view+name).encode()).hexdigest(),
                'mount_destination':'/input/'+name,'read_only':True}
                for i,name in enumerate(('train.npz','query.npz','schema.json','units.json','contract.json'))]
        manifest_path=Q+'/dmfc-paired-delivery-20261114-v1/DELIVERY_MANIFEST.json'
        bodies[manifest_path]=owner.encode(manifest)
        freeze=owner.decode(bodies[BASE+'/SOURCE_FREEZE.json'])
        freeze['files'][manifest_path]=owner.pin(bodies[manifest_path]);bodies[BASE+'/SOURCE_FREEZE.json']=owner.encode(freeze)
        value=copy.deepcopy(self.payload);value['successor_freeze']={'path':BASE+'/SOURCE_FREEZE.json',**owner.pin(bodies[BASE+'/SOURCE_FREEZE.json'])}
        profile_descriptor={'path':BASE+'/OPERATION_PROFILE.json',**owner.pin(bodies[BASE+'/OPERATION_PROFILE.json'])}
        request={'schema':'dmfc-frozen-pair-ungraded-root-request/v1','candidate_id':'NEURAL-095',
            'decision':'admit_one_complete_dmfc_frozen_pair_ungraded_operation','configuration_payload_sha256':owner.pin(owner.encode(value))['sha256'],
            'source_freeze':value['successor_freeze'],'output_root':str(root),'actor_contexts':list(owner.CONTEXTS),
            'runtime_identity':value['runtime_identity'],'profile':profile_descriptor}
        value['request']={'path':'GENERATED_REQUEST.json',**put(deployment/'GENERATED_REQUEST.json',request)}
        config_pin={'path':'GENERATED_CONFIG.json',**put(deployment/'GENERATED_CONFIG.json',value)}
        for path,body in bodies.items():put(deployment/path,body)
        source_config=load('_closed_real_configuration',deployment/BASE/'configuration.py',bodies[BASE+'/configuration.py'])
        source_config.capture=read
        config,captured,unused=source_config.load(deployment/config_pin['path'],config_pin['sha256'])
        actual_owner=load('_closed_real_operation_owner',deployment/BASE/'operation_owner.py',bodies[BASE+'/operation_owner.py'])
        actual_owner.read=read
        actual_contract=load('_closed_real_actor_contract',deployment/freeze['modules']['actor_contract'],bodies[freeze['modules']['actor_contract']])
        ar_nodes=[n for n in ast.parse(bodies[freeze['modules']['actor_runtime']]).body
                  if isinstance(n,ast.FunctionDef) and n.name in ('folder_for','read_intent')]
        ar=types.ModuleType('_closed_real_actor_reader');ar.__dict__.update(Path=Path,re=__import__('re'),need=owner.need)
        exec(compile(ast.Module(body=ar_nodes,type_ignores=[]),'<actual-actor-read-only-functions>','exec'),ar.__dict__)
        trusted=load('_closed_trusted_controller',deployment/BASE/'trusted_controller.py',bodies[BASE+'/trusted_controller.py'])
        nodes=[n for n in ast.parse(bodies[BASE+'/process_owner.py']).body if isinstance(n,ast.FunctionDef) and n.name=='expected']
        proc_owner=types.ModuleType('_closed_real_process_expected')
        proc_owner.__dict__.update(Path=Path,sys=sys,HERE=deployment/BASE,read=lambda path:owner.decode(read(path,16384)),
                                  validate_controller=trusted.validate_controller)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'<actual-process-expected>','exec'),proc_owner.__dict__)
        live=types.SimpleNamespace(ROOT=deployment,UNIT=deployment/'authoring/task-ownership-successors-20261102/nlb017-recovery-capacity-v4/nlb_unit.py',
            UNIT_PIN=(7541,'9057ff748128ccc1909f7db3c5f77f12584823e60ffd6338750af5bb7abfade9'))
        # Canonical numerical constructor boundary is explicitly scripted; actor
        # constructor and original completed_unit comparison are real.
        engines=types.SimpleNamespace(volume_expected=lambda n:{'argv':['generated-volume',n]},
            container_expected=lambda n,r,m,p:{'argv':['generated-container',n,r,owner.encode(m).decode(),owner.encode(p).decode()]})
        selected_modules={freeze['modules'][k]:v for k,v in (('operation_owner',actual_owner),('live',live),
            ('actor_runtime',ar),('actor_contract',actual_contract),('producer',self.api))}
        runtime=types.SimpleNamespace(sys=sys,owner=proc_owner,engines=engines,
            bind_aliases=lambda aliases:None,load=lambda path:selected_modules[path])
        def descriptor(name):
            path=freeze['modules'][name];return {'path':path,**freeze['files'][path]}
        def group(folder,pid,desc,argv):
            token='%032x'%pid
            args=[sys.executable,'-I','-B',str(deployment/BASE/'group_bootstrap.py'),'--owner',str(folder/'process_owner.json'),
                  '--token',token,'--seconds','120.0']
            own={'controller':desc,'pid':pid,'pgid':pid,'token':token,'bootstrap_argv':args,'child_argv':argv,
                 'seconds':120.0,'pid_recorded_before_activation':True}
            put(folder/'process_owner.json',own)
            put(folder/'process_intent.json',{'bootstrap_argv':args,'token':token,'activation_requires_fsynced_owner':True,'controller':desc})
            put(folder/'process_ready.json',{'token':token,'pid':pid,'pgid':pid,'python_initialized_before_identity_snapshot':True})
            put(folder/'process_gate.json',{'token':token,'activate':True})
            return {'pid':pid,'pgid':pid,'status':'owned_group_absent','absence_verified':True},token
        controller_argv=[sys.executable,str(deployment/descriptor('controller')['path']),'--config',str(deployment/config_pin['path']),
            '--config-sha256',config.sha256,'--owner-directory',str(root/'owner'),'--work-deadline','4201.0','--whole-deadline','4801.0']
        main_clean,token=group(root/'owner',2000,descriptor('controller'),controller_argv)
        put(root/'owner/process_completion.json',{'token':token,'returncode':0,'group_leader_waits_for_owner_stop':True})
        actor_clean,creator_clean={},{}
        for i,key in enumerate(owner.CONTEXTS):
            folder=root/'actors'/key;context=value['actor']['arms'][key]
            argv=[sys.executable,str(deployment/descriptor('actor_service')['path']),'--config',str(deployment/config_pin['path']),
                '--config-sha256',config.sha256,'--mode',key,'--owner-directory',str(folder/'owner')]
            creator_clean[key],unused=group(folder/'owner',2001+i,descriptor('actor_service'),argv)
            prog={'path':str(folder/'program.py'),**put(folder/'program.py',bodies[context['program']['path']])}
            cfg={'path':str(folder/'config.json'),**put(folder/'config.json',bodies[context['config']['path']])}
            name='offline-actor-'+'%032x'%(100+i)
            put(folder/'actor_intent.json',{'schema':'isolated-offline-actor-intent/v1','mode':key,'config_sha256':config.sha256,
                'request_sha256':config.request_sha256,'context':context,'name':name,'program':prog,'actor_config':cfg,
                'deadline_us':900000000,'child_argv':argv,'controller':descriptor('actor_service')})
            mounts={'/actor/program.py':{'type':'bind','source':prog['path'],'rw':False}}
            put(folder/'engine/resource_ownership.json',{'owned':[{'kind':'container','name':name,'attempted_before_dispatch':True,
                'canonical_create_argv':actual_contract.argv(name,'offline_actor',mounts,actual_contract.descriptor())}]})
            actor_clean[key]={'mode':key,'absence_verified':True,'profile':actual_contract.descriptor(),
                'container':{'kind':'container','name':name,'absence_verified':True,'immutable_id_and_name_absence':True,
                             'verified_identity':'%064x'%(100+i)}}
        limits=self.api.Limits(self.api.Usage(**value['limits']['total']),self.api.Usage(**value['limits']['preparation']),
            value['limits']['wall_us'],value['limits']['preparation_wall_us'],value['limits']['max_memory_bytes'],value['limits']['response_bytes'])
        reservations={k:self.api.Usage(**v) for k,v in value['reservation_policy'].items()};records=[]
        def unit(index,source,inputs,filename,cap,output):
            folder=root/'units'/('unit-%04d'%index);suffix='%032x'%index
            program={'path':str(folder/'program.py'),**put(folder/'program.py',source)}
            spec={'unit_id':'dmfc-four-cell/unit-%04d'%index,'public_inputs':inputs,'output_filename':filename,'max_output_bytes':cap}
            intent={'unit':spec,'dispatches':1,'runner':{'path':str(live.UNIT),'bytes':live.UNIT_PIN[0],'sha256':live.UNIT_PIN[1]},'program':program}
            put(folder/'UNIT_INTENT.json',intent)
            names=[p+suffix for p in ('dmfc-prog-volume-','dmfc-prog-holder-','dmfc-prog-worker-')]
            profile={'public_destinations':tuple(x['mount_destination'] for x in inputs),'output_name':filename,'max_output_bytes':cap}
            owned=[]
            for pos,name in enumerate(names):
                if pos==0:args=engines.volume_expected(name)['argv']
                else:
                    mounts=({'/trusted/holder.py':{'type':'bind','source':str(deployment/'authoring/shared-large-npz-runner-v1/holder_profile.py'),'rw':False},
                             '/capture':{'type':'volume','source':names[0],'rw':False}} if pos==1 else
                            {'/program/program.py':{'type':'bind','source':str(folder/'program.py'),'rw':False},'/output':{'type':'volume','source':names[0],'rw':True}})
                    if pos==2:mounts.update({x['mount_destination']:{'type':'bind','source':str(deployment/x['path']),'rw':False} for x in inputs})
                    args=engines.container_expected(name,'holder' if pos==1 else 'candidate',mounts,profile)['argv']
                owned.append({'kind':'volume' if pos==0 else 'container','name':name,'attempted_before_dispatch':True,'canonical_create_argv':args})
            put(folder/'attempt/resource_ownership.json',{'owned':owned})
            outpin=put(folder/'attempt'/filename,output)
            commit={'status':'removed_producer_output_committed','candidate_id':'NEURAL-095','unit_id':spec['unit_id'],
                'program_sha256':program['sha256'],'producer_removed_before_capture':True,'all_candidate_holder_volume_absent':True,
                'public_inputs':inputs,'output':outpin,'producer':{'name':names[2],'container_id':'%064x'%(1000+index*2+1)}}
            commit_pin=put(folder/'attempt/commit.json',commit)
            cleanup=[{'kind':'volume' if i==0 else 'container','name':n,'absence_verified':True,
                      **({'verified_identity':'%064x'%(1000+index*2+i-1)} if i else {})} for i,n in enumerate(names)]
            put(folder/'attempt/execution.json',{'status':'unit_committed','all_owned_absent':True,'candidate_id':'NEURAL-095',
                'unit_id':spec['unit_id'],'program_sha256':program['sha256'],'commit_sha256':commit_pin['sha256'],
                'output':outpin,'cleanup':cleanup})
        for i,view in enumerate(owner.VIEWS):
            folder=root/'cells'/('frozen_program__'+view);actor=value['actor']['arms']['frozen_program__'+view]['program']
            cell=self.api.Cell(mode='frozen_program',view=view,source=bodies[actor['path']],method=self.raw['method'],case_ids=IDS,
                limits=limits,reservations=reservations,tool_ids=('dmfc_predict@'+owner.pin(NUMERIC)['sha256'],),backend=None,
                comparison_id=config.request_sha256,manifest=manifest,clock_us=lambda:0,on_admission=lambda _:None)
            admission=cell.specification();admitpin=put(folder/'ADMISSION.json',admission);fitpin=put(folder/'fitted.bin',b'generated-fit')
            freeze_pin=put(folder/'FREEZE.json',{'specification_sha256':admitpin['sha256'],'training_artifacts_sha256':fitpin['sha256'],
                                               'source_sha256':actor['sha256'],'method_sha256':value['method']['sha256']})
            submission=self.api.submission_npz(IDS,tuple(float(j) for j in range(258)));subpin=put(folder/'submission.npz',submission)
            put(folder/'opaque-output.bin',submission)
            record={'mode':'frozen_program','view':view,'session_id':'generated-'+view,'submission':subpin,
                'source_sha256':actor['sha256'],'method_sha256':value['method']['sha256'],'freeze_sha256':freeze_pin['sha256'],
                'limits_sha256':limits.identity(),'case_count':258,'absence':dict.fromkeys(self.api.ABSENCE,True)}
            put(folder/'COMMIT.json',record);records.append(record)
            for j,operation in enumerate(('prepare','tool')):
                op={'schema':'dmfc-offline-policy-call-v1','operation':operation,'state':None,'tool_observation':None,
                    'payload':None if j==0 else {'case_id':IDS[0],'action':'tool','tool_id':'dmfc_predict@'+owner.pin(NUMERIC)['sha256'],'arguments':{}}}
                op_path=folder/('request-%04d.json'%j);op_pin=put(op_path,op)
                inputs=[{**p,'path':str(deployment/p['path'])} for p in admission['public_inputs'] if j or p['mount_destination']!='/input/query.npz']
                inputs.append({'path':str(op_path),**op_pin,'mount_destination':'/input/operation.json','read_only':True})
                if j:inputs.append({'path':str(folder/'fitted.bin'),**fitpin,'mount_destination':'/input/fitted.bin','read_only':True})
                unit(3*i+j,NUMERIC,inputs,'result.json',262144,b'generated-numerical-output')
            writer=b"from pathlib import Path\nPath('/output/submission.npz').write_bytes(Path('/input/opaque.bin').read_bytes())\n"
            unit(3*i+2,writer,[{'path':str(folder/'opaque-output.bin'),**subpin,'mount_destination':'/input/opaque.bin','read_only':True}],
                 'submission.npz',1048576,submission)
        pair={'schema':'dmfc-frozen-pair-ungraded-collection/v1','mode':owner.MODE,'comparison_id':config.request_sha256,
            'case_count_per_cell':258,'training_count':748,'case_ids':list(IDS),'limits_sha256':limits.identity(),
            'delivery_manifest_sha256':owner.pin(bodies[manifest_path])['sha256'],'cells':records,'policy':owner.POLICY,
            'private_grades_so_far':0,'private_target_reads':0,'private_reference_reads':0,'numerical_units_expected':6}
        pairpin=put(root/'FROZEN_PAIR.json',pair)
        inner={'schema':'dmfc-frozen-pair-ungraded-controller-result/v1','config_sha256':config.sha256,
            'request_sha256':config.request_sha256,'status':collection.STATUS,'study_result':{'status':collection.STATUS,
                'mode':owner.MODE,'pair_sha256':pairpin['sha256'],'private_grades_so_far':0,'operational_qualification_claimed':False}}
        innerpin=put(root/'controller_result.json',inner)
        folders=[root/'units'/('unit-%04d'%i) for i in range(6)]
        names,ids=set(),set()
        rows=[actual_owner.completed_unit(folder,i,live,engines,names,ids) for i,folder in enumerate(folders)]
        outer={'schema':'dmfc-frozen-pair-ungraded-outer-result/v1','status':'complete_frozen_pair_ungraded_operation',
            'all_owned_absent':True,'controller_returncode':0,'config_sha256':config.sha256,'request_sha256':config.request_sha256,
            'profile':profile_descriptor,'automatic_retry':False,'research_qualified':False,'work_deadline':4201.0,'whole_deadline':4801.0,
            'actual_runtime':{'server':value['runtime_identity']['server'],'image':{k:value['runtime_identity']['image'][k] for k in ('Id','Os','Architecture')}},
            'controller_result':innerpin,'group_cleanup':main_clean,'actor_creator_group_cleanup':creator_clean,'actor_cleanup':actor_clean,
            'numerical_cleanup':{'all_owned_absent':True,'unit_family_identity_valid':True,'all_unit_commits_verified':True,'unit_count':6,
                'reused_closed_receipts':6,'pending_units_recovered':0,'closed_receipt_reuse_disabled':False,'units':rows}}
        outerpin=put(root/'OUTER_RESULT.json',outer)
        selected={'deployment_root':str(deployment),'configuration':config_pin,'source_freeze':value['successor_freeze'],'outer_result':outerpin}
        original_module=owner.module
        def loading(name,path,body,injected=None):
            m=original_module(name,path,body,injected)
            if name=='_frozen_selected_configuration':m.capture=read
            elif name=='_frozen_closed_runtime':m.load_runtime=lambda *a:runtime
            return m
        return types.SimpleNamespace(root=root,memory=memory,selected=selected,read=read,loading=loading,folders=folders,put=put,outer=outer)

    def _validate_fixture(self,f):
        original_iterdir=Path.iterdir
        with patch.object(owner,'capture',f.read),patch.object(owner,'module',f.loading), \
             patch.object(Path,'iterdir',lambda p:iter(f.folders) if p==f.root/'units' else original_iterdir(p)), \
             patch('subprocess.Popen',side_effect=AssertionError('closure validation never dispatches')), \
             patch('subprocess.run',side_effect=AssertionError('closure validation never probes')):
            return owner.validate_closed(f.root,f.selected)

    def test_11_complete_real_closed_validator_traversal_and_resource_policy(self):
        f=self.closed_fixture();result=self._validate_fixture(f)
        self.assertEqual((result['mode'],result['status']),(owner.MODE,'closed_ungraded'))
        self.assertEqual(result['case_ids'],list(IDS));self.assertEqual(set(result['submissions']),set(owner.VIEWS))
        self.assertEqual(result['resource_policy']['limits'],self.payload['limits'])
        self.assertEqual(len(result['closure']['numerical_units']),6)
        for view in owner.VIEWS:
            self.assertEqual(result['submissions'][view]['pin'],owner.pin(result['submissions'][view]['body']))
            self.assertEqual(result['submission_paths'][view],str(f.root/'cells'/('frozen_program__'+view)/'submission.npz'))

    def test_12_complete_validator_refuses_final_commit_and_closure_changes(self):
        for change in ('last-output','cell-commit','missing-actor-absence','seventh-unit'):
            f=self.closed_fixture()
            if change=='last-output':f.memory[f.root/'cells/frozen_program__neural/submission.npz']+=b'changed'
            elif change=='cell-commit':
                path=f.root/'cells/frozen_program__neural/COMMIT.json';v=owner.decode(f.memory[path]);v['view']='cue_only';f.put(path,v)
            elif change=='missing-actor-absence':
                f.outer['actor_cleanup'][owner.CONTEXTS[-1]]['container']['absence_verified']=False
                f.selected['outer_result']=f.put(f.root/'OUTER_RESULT.json',f.outer)
            else:f.folders.append(f.root/'units/unit-0006')
            with self.subTest(change=change),self.assertRaises(ValueError):self._validate_fixture(f)

    def test_13_source_role_refused_before_original_loader_can_read_operand(self):
        f=self.closed_fixture()
        path=self.destination/f.selected['configuration']['path']
        value=owner.decode(f.memory[path]);value['numerical_tool']={'path':'FORBIDDEN/targets.npz','bytes':1,'sha256':'f'*64}
        f.selected['configuration']={'path':f.selected['configuration']['path'],**f.put(path,value)}
        with patch.object(owner,'capture',f.read),patch.object(owner,'module',side_effect=AssertionError('role refused before source loader')), \
             self.assertRaises(ValueError):
            owner.validate_closed(f.root,f.selected)

    def test_14_relative_package_cannot_reopen_selected_manifest(self):
        actual_module=owner.module;manifest_reads=[]
        def loading(name,path,body,injected=None):
            m=actual_module(name,path,body,injected)
            if name=='_frozen_original_configure':
                original=m.capture
                def read(path,cap=262144):
                    if Path(path).name=='SOURCE_MANIFEST.json':
                        manifest_reads.append(str(path));raise AssertionError('authenticated manifest was reopened')
                    return original(path,cap)
                m.capture=read
            return m
        with patch.object(owner,'module',loading), patch('os.getcwd',return_value=str(I.parent)):
            result=owner.assemble(Path(I.name),operator(),self.destination,**self.raw,expected=self.expected)
        self.assertEqual(manifest_reads,[]);self.assertEqual(result['payload']['collection_mode'],owner.MODE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
