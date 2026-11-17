"""Generated controls only; no authentic packet, Docker or model execution."""
import copy
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common
import grade
import run
from transport import provider
from transport.contract import validate_request, validate_exposure
sys.path.insert(0, str(common.SCORER))
import scoring_core

WRITTEN = 0
ORIGINAL_PUBLISH = common.publish


def tracked_publish(path, body, mode=0o400):
    global WRITTEN
    WRITTEN += len(body)
    if WRITTEN > 36 * 1024**2:
        raise AssertionError('Per-run generated fixture write ceiling')
    return ORIGINAL_PUBLISH(path, body, mode)


run.publish = tracked_publish


def save(path, body):
    global WRITTEN
    WRITTEN += len(body)
    if WRITTEN > 36 * 1024**2:
        raise AssertionError('Per-run generated fixture write ceiling')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return common.pin(body)


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='neural018-generated-')
        self.root = Path(self.temp.name).resolve()
        self.source = common.pin((HERE / 'SOURCE.json').read_bytes())

    def tearDown(self):
        self.temp.cleanup()

    def test_full574_unicode64_archive_retains_original_34mib_contract(self):
        trials = np.asarray([f'generated-trial-{i:04d}' for i in range(574)], dtype='<U64')
        units = np.asarray([f'generated-unit-{i:03d}' for i in range(182)], dtype='<U64')
        public = {'trial_ids': trials, 'forecast_unit_ids': units,
                  'bin_left_edges_ms': np.arange(450,650,5,dtype='<i8'),
                  'prediction_units': 'expected_spikes_per_bin', 'panel_fingerprint': 'a' * 64}
        data = io.BytesIO()
        np.savez(data, expected_counts=np.ones((574,40,182), dtype='<f8'), **public)
        body = data.getvalue()
        self.assertGreater(len(body), 32 * 1024**2)
        self.assertLessEqual(len(body), common.MAX_OUTPUT)
        path = self.root / 'complete.npz'
        identity = save(path, body)
        self.assertEqual(common.pin(common.capture(path, common.MAX_OUTPUT, identity)), identity)
        result = scoring_core.load_validated_submission(path, public)
        self.assertEqual(result['expected_counts'].shape, (574,40,182))
        self.assertTrue(np.array_equal(result['trial_ids'], trials))
        with self.assertRaises(ValueError):
            common.capture(path, 32 * 1024**2)

    def test_transport_original_holder_and_thread_envelope(self):
        request = {'resources': run.LIMITS, 'command': ['/generated/command'], 'image': grade.IMAGE}
        item = {'name': 'generated', 'owner': 'generated/holder'}
        holder = provider.create_args(item, True, {}, request, ['/generated/holder'])
        candidate = provider.create_args(item, False, {}, request, ['/generated/holder'])
        self.assertEqual(holder[holder.index('--cpus')+1], '0.250000000')
        self.assertEqual(holder[holder.index('--memory')+1], str(256*1024**2))
        self.assertEqual(candidate[candidate.index('--cpus')+1], '1.750000000')
        self.assertEqual(candidate[candidate.index('--memory')+1], str(3*1024**3))
        for key in grade.THREADS:
            self.assertEqual(provider.fixed_environment(False)[key], '2')
        self.assertEqual(run.LIMITS['max_file_bytes'], scoring_core.MAX_PREDICTIONS)

    def test_complete_public_mounts_never_include_private_assets(self):
        mounts = run.public_mounts('/generated/assets')
        self.assertEqual(set(mounts), set(common.PUBLIC.values()))
        self.assertEqual(sum(next(iter(v['files'].values()))['bytes'] for v in mounts.values()), 138824524)
        self.assertTrue(all(v['purpose'] == 'input' for v in mounts.values()))

    def test_real_native_adapter_and_observer_binding(self):
        output = self.root / 'attempt'
        identity = run.commit(self.generated_program(), output, self.source, {})
        config = {'assets_root': '/generated/assets', 'image': grade.IMAGE,
                  'control_root': str(self.root/'control'), 'quarantine_root': str(self.root/'capture'),
                  'docker_binary': '/generated/docker', 'docker_socket': '/generated/socket',
                  'mechanical_policy_pin': common.pin(b'generated-policy')}
        policy = {'image_inventory_sha256': 'b'*64}
        tester, observations = self, []
        class GeneratedProvider:
            def __init__(self, control, quarantine, binary, socket, engine_pin, exposures, read_cap, write_cap):
                self.exposures, self.quarantine = exposures, Path(quarantine)
                tester.assertEqual(read_cap, 513*1024**2)
            def execute_phase(self, request, mounts, deadline, journal):
                validate_request(request, mounts, deadline)
                exposure = common.decode(common.capture(self.exposures[request['exposure']['sha256']], 32768))
                validate_exposure(exposure, request, mounts)
                tester.assertEqual(len(mounts), 5)
                tester.assertNotIn('/input/gold.npz', mounts)
                directory = self.quarantine / request['phase_id']
                prediction = save(directory/'predictions.npz', b'generated opaque invalid archive')
                result = save(directory/'RESULT.json', common.encoded({'schema':'neural018_program_exit_v1','candidate_exit_code':0}))
                self.receipt = {'status':'captured','producer_closed_before_capture':True,'all_native_resources_closed':True,
                    'cli_reaped':True,'error':None,'natural_exit':{'ExitCode':0,'OOMKilled':False},
                    'source':request['source'],'image':request['image'],'role':'A','exposure':request['exposure'],
                    'input_before':mounts,'input_after':mounts,'quarantine_root':str(directory),
                    'output_inventory':{'complete':True,'files':{'predictions.npz':prediction,'RESULT.json':result,'OUTPUTS.json':{}}}}
                self.request = request
                return {'receipt_pin':common.pin(common.encoded(self.receipt)),'receipt_path':'/generated/receipt.json'}
            def observe(self, phase, request_sha, receipt_pin, deadline):
                tester.assertEqual(phase, self.request['phase_id'])
                tester.assertEqual(request_sha, common.pin(common.encoded(self.request))['sha256'])
                observations.append(phase)
                return {'receipt':self.receipt}
        with patch.object(run, 'Provider', GeneratedProvider):
            backend = run.Native(config, policy, output, self.source, time.monotonic(), time.monotonic()+140)
            path, evidence = backend.produce(identity)
            self.assertEqual(path.name, 'predictions.npz')
            self.assertTrue(evidence['all_native_resources_closed'])
        self.assertEqual(len(observations), 1)

    def generated_program(self):
        path = self.root / 'candidate.py'
        save(path, b'# Generated source; never executed\n')
        return path

    def completion(self, mutation):
        output = self.root / 'attempt'
        identity = run.commit(self.generated_program(), output, self.source, {})
        predicted = self.root / 'opaque.npz'
        prediction_pin = save(predicted, b'generated opaque output')
        calls, test = [], self
        class GeneratedBackend:
            def produce(self, programme):
                test.assertTrue((output/'COMMIT.json').is_file())
                if mutation == 'programme':
                    (output/'program.py').chmod(0o600)
                    save(output/'program.py', b'# Changed after access\n')
                return predicted, {'source':test.source,'program':programme,'submission':prediction_pin,
                    'producer_removed_before_capture':mutation!='live','all_native_resources_closed':True}
        def grader(action, path, destination, config, deadline, source):
            calls.append(action)
            test.assertTrue((output/'PREDICTION_COMMIT.json').exists())
            if mutation == 'capture_after':
                save(predicted,b'changed')
            if mutation == 'invalid':
                return {'status':'rejected_no_score','target_loader_invocations':0}
            if mutation == 'late_targets':
                return {'status':'rejected_no_score','target_loader_invocations':1}
            keys = common.assets()['reference_panel']
            return {'status':'scored','signed_differences':{k:0. for k in list(keys)[:4] if mutation=='missing_reference'} if mutation=='missing_reference' else {k:0. for k in keys}}
        deadline = time.monotonic() + (59 if mutation=='time' else 140)
        if mutation in ('good','invalid'):
            value=run.complete({},output,self.source,identity,GeneratedBackend(),grader,deadline)
            self.assertEqual(value['status'], 'scored' if mutation=='good' else 'rejected_no_score')
            self.assertTrue((output/'COMPLETE.json').exists())
        else:
            with self.assertRaises(ValueError):
                run.complete({},output,self.source,identity,GeneratedBackend(),grader,deadline)
            self.assertFalse((output/'COMPLETE.json').exists())
            if mutation in ('programme','live','time'):
                self.assertEqual(calls, [])

    def test_success_and_invalid_public_output(self):
        self.completion('good')

    def test_invalid_public_output_has_no_scientific_score(self):
        self.completion('invalid')

    def test_live_producer_never_dispatches_grade(self):
        self.completion('live')

    def test_changed_source_never_dispatches_grade(self):
        self.completion('programme')

    def test_full_original_grader_time_must_remain(self):
        self.completion('time')

    def test_late_private_read_is_not_a_valid_rejection(self):
        self.completion('late_targets')

    def test_missing_reference_prevents_completion(self):
        self.completion('missing_reference')

    def test_capture_mutation_after_grade_prevents_completion(self):
        self.completion('capture_after')

    def test_grader_preserves_original_resource_and_mount_contract(self):
        mounts = {'/package/worker.py':'/generated/worker.py','/input/submission.npz':'/generated/submission.npz'}
        name='nlb-forecast-score-v2-'+'a'*32
        host={'NetworkMode':'none','ReadonlyRootfs':True,'Privileged':False,'CapDrop':['ALL'],'CapAdd':[],
            'SecurityOpt':['no-new-privileges:true'],'Devices':[],'DeviceRequests':[],'IpcMode':'private','PidMode':'',
            'PortBindings':{},'Memory':4*1024**3,'MemorySwap':4*1024**3,'NanoCpus':2000000000,'PidsLimit':64,
            'RestartPolicy':{'Name':'no'},'AutoRemove':False,'Tmpfs':{'/tmp':'rw,noexec,nosuid,nodev,size=134217728,mode=1777'},
            'LogConfig':{'Type':'local','Config':{'max-size':'256k','max-file':'1','compress':'false'}},
            'Ulimits':[{'Name':k,'Soft':a,'Hard':b} for k,(a,b) in {'cpu':(40,42),'nofile':(1024,1024),'core':(0,0),'fsize':(35651584,35651584)}.items()],
            'Mounts':[{'Type':'bind','Source':v,'Target':k,'ReadOnly':True} for k,v in mounts.items()]}
        config={'Image':grade.IMAGE,'Cmd':['-I','/package/worker.py','score'],'Entrypoint':['python'],'WorkingDir':'/tmp',
            'User':'65534:65534','Env':[k+'=2' for k in grade.THREADS]+['PYTHONDONTWRITEBYTECODE=1','EXPECTED_SUBMISSION_SHA256='+'b'*64]}
        info={'Name':'/'+name,'Image':grade.IMAGE,'HostConfig':host,'Config':config,'State':{'Status':'created','Running':False,'Pid':0},
            'NetworkSettings':{'Networks':{}},'Mounts':[{'Type':'bind','Source':v,'Destination':k,'RW':False} for k,v in mounts.items()]}
        grade.inspect_contract(info,name,mounts,'score','b'*64)
        for mutate in ('thread','memory','extra_mount','submission_digest','duplicate_environment'):
            bad=copy.deepcopy(info)
            if mutate=='thread': bad['Config']['Env'][0]=grade.THREADS[0]+'=1'
            if mutate=='memory': bad['HostConfig']['Memory']=3*1024**3
            if mutate=='extra_mount': bad['Mounts'].append({'Type':'bind','Source':'/private','Destination':'/private','RW':False})
            if mutate=='submission_digest': bad['Config']['Env'][-1]='EXPECTED_SUBMISSION_SHA256='+'c'*64
            if mutate=='duplicate_environment': bad['Config']['Env'].append('EXPECTED_SUBMISSION_SHA256='+'b'*64)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                grade.inspect_contract(bad,name,mounts,'score','b'*64)

    def test_grader_refuses_insufficient_clock_before_any_native_call(self):
        with patch.object(grade.subprocess,'run',side_effect=AssertionError('Unexpected native dispatch')):
            with self.assertRaisesRegex(ValueError,'sixty-second'):
                grade.execute('score','/generated/submission',self.root/'score.json',{'image':grade.IMAGE},time.monotonic()+59,self.source)

    def exercise_grader(self, mode):
        """Run the portable launcher against a scripted CLI, never real Docker."""
        public = {}
        for key in ('past','manifest'):
            name = key + '.generated'
            identity = save(self.root/name, b'generated public placeholder')
            public[key] = {'path':name, **identity}
        private = {}
        for key in ('targets','comparator','followup_grade','followup_prediction_freeze','followup_compact'):
            name = key + '.generated'
            identity = save(self.root/name, b'generated private placeholder')
            private[key] = {'path':name, **identity}
        submission = self.root/'opaque.npz'
        save(submission,b'generated submission placeholder')
        config = {'image':grade.IMAGE,'assets_root':str(self.root),'docker_binary':'/generated/docker',
                  'docker_config':str(self.root/'docker-config'),'docker_socket':'/generated/socket'}
        result = {'status':'rejected_no_score','target_loader_invocations':0} if mode=='invalid' else {
            'status':'scored','target_loader_invocations':1,'signed_differences':{k:0. for k in common.assets()['reference_panel']}}
        calls, inspected = [], []
        state = {'inspects':0,'name':None}
        def native(argv, **kwargs):
            self.assertEqual(argv[0],'/generated/docker')
            self.assertNotIn('DOCKER_CONTEXT',kwargs['env'])
            self.assertEqual(kwargs['env']['DOCKER_HOST'],'unix:///generated/socket')
            self.assertGreater(kwargs['timeout'],0)
            calls.append(argv[1:])
            op=argv[1]
            if op=='inspect':
                state['inspects']+=1
                name=argv[-1]
                if state['inspects'] in (1,4):
                    if mode=='uncertain_cleanup' and state['inspects']==4:
                        return subprocess.CompletedProcess(argv,1,'','permission denied')
                    return subprocess.CompletedProcess(argv,1,'',f'Error: No such object: {name}')
                return subprocess.CompletedProcess(argv,0,json.dumps([{'Name':'/'+name,'State':{'Running':False,'OOMKilled':False}}]),'')
            if op=='create':
                state['name']=argv[argv.index('--name')+1]
                self.assertIn('cpu=40:42',argv)
                self.assertIn('fsize=35651584:35651584',argv)
                self.assertIn('EXPECTED_SUBMISSION_SHA256='+grade.digest(submission),argv)
                mounted=[argv[i+1] for i,v in enumerate(argv) if v=='--mount']
                destinations={x.split('dst=',1)[1].split(',')[0] for x in mounted}
                self.assertEqual(destinations,{'/package/worker.py','/package/scoring_core.py','/package/assets.json',
                    '/input/public.npz','/input/manifest.json','/input/submission.npz','/input/gold.npz',
                    '/input/reference.npz','/input/followup_grade.json','/input/followup_prediction_freeze.json','/input/followup_compact.npz'})
                self.assertFalse(any('/program/' in x for x in mounted))
            if op=='wait':
                return subprocess.CompletedProcess(argv,0,'2\n' if mode=='invalid' else '0\n','')
            if op=='logs':
                return subprocess.CompletedProcess(argv,0,json.dumps(result),'')
            return subprocess.CompletedProcess(argv,0,'generated','')
        def inspect(info,name,mounts,action,submission_digest):
            inspected.append(name)
            self.assertEqual(action,'score')
            self.assertEqual(len(mounts),11)
            self.assertEqual(submission_digest,grade.digest(submission))
        def counted_save(path,value):
            save(Path(path),(json.dumps(value,indent=2,allow_nan=False)+'\n').encode())
        with patch.object(grade,'load_assets',return_value={'public':public,'private':private}), \
             patch.object(grade.subprocess,'run',side_effect=native), patch.object(grade,'inspect_contract',side_effect=inspect), \
             patch.object(grade,'save',side_effect=counted_save), patch.dict(os.environ,{'DOCKER_CONTEXT':'untrusted-remote'}):
            if mode=='uncertain_cleanup':
                with self.assertRaisesRegex(ValueError,'closure'):
                    grade.execute('score',submission,self.root/'score.json',config,time.monotonic()+90,self.source)
            else:
                actual=grade.execute('score',submission,self.root/'score.json',config,time.monotonic()+90,self.source)
                self.assertEqual(actual['status'],result['status'])
        self.assertEqual(len(inspected),1)
        self.assertEqual(sum(c[0]=='create' for c in calls),1)
        self.assertTrue(any(c[:2]==['rm','--force'] for c in calls))
        self.assertTrue((self.root/'score.json.ownership.json').exists())
        self.assertTrue((self.root/'score.json.execution.json').exists())

    def test_portable_grader_actual_launcher_binding(self):
        self.exercise_grader('good')

    def test_portable_grader_worker_rejection_and_cleanup(self):
        self.exercise_grader('invalid')

    def test_portable_grader_ambiguous_absence_is_failure(self):
        self.exercise_grader('uncertain_cleanup')

    def test_source_freeze_and_transport_copied_closure(self):
        self.assertEqual(common.authenticate(self.source),self.source)
        source = common.decode(common.capture(HERE/'PROVENANCE.json',65536))
        for name in ('__init__.py','archive.py','bounds.py','contract.py','engine.py','holder.py'):
            original=common.REPO/'benchmarks/neural/NEURAL-007/implementations/whole-night-programme/program/vendor_transport'/name
            self.assertEqual((HERE/'transport'/name).read_bytes(),original.read_bytes())
        self.assertEqual(source['historical_accounting']['charged_seconds'],910)

    def test_configuration_preserves_old_charges_and_requires_new_amendment(self):
        config={'schema':'neural018_submitted_program_configuration_v1','source':self.source,'image':grade.IMAGE}
        for name in ('assets_root','docker_binary','docker_socket','docker_config','control_root','quarantine_root'):
            config[name]=str(self.root/name)
        policy={'schema':'neural018_mechanical_boundary_v1','source':self.source,'image':grade.IMAGE,
                'image_inventory_sha256':'a'*64,'approved_rule':'three_original_public_inputs_then_isolated_original_grader_v1'}
        config['mechanical_policy_path']=str(self.root/'policy.json')
        config['mechanical_policy_pin']=save(self.root/'policy.json',common.encoded(policy))
        allocation={'schema':'neural018_new_runtime_allocation_v1','source':self.source,
                    'historical_charges_seconds':[60,120,180,90,250,90,120],'historical_total_seconds':910,
                    'historical_amended_ceiling_seconds':1000,'new_whole_seconds':140,
                    'new_cumulative_ceiling_seconds':1050,'operator_approved':True,
                    'source_read_bytes':513*1024**2,'transport_write_bytes':48*1024**2,'additional_operator_output_bytes':2*1024**2}
        config['allocation_path']=str(self.root/'allocation.json')
        for mutation in ('valid','reset_history','no_amendment','no_approval'):
            amended=copy.deepcopy(allocation)
            if mutation=='reset_history': amended['historical_total_seconds']=0
            if mutation=='no_amendment': amended['new_cumulative_ceiling_seconds']=1000
            if mutation=='no_approval': amended['operator_approved']=False
            config['allocation_pin']=save(self.root/'allocation.json',common.encoded(amended))
            save(self.root/'configuration.json',common.encoded(config))
            if mutation=='valid':
                self.assertEqual(run.configuration(self.root/'configuration.json')[2]['historical_total_seconds'],910)
            else:
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                    run.configuration(self.root/'configuration.json')


if __name__ == '__main__':
    print(json.dumps({'python':platform.python_version(),'numpy':np.__version__,'scope':'generated_software_controls_only'}),flush=True)
    try:
        unittest.main(verbosity=2)
    finally:
        print(json.dumps({'generated_fixture_file_bytes_written':WRITTEN,'authentic_payload_reads':0,
                          'private_target_reads':0,'model_calls':0,'native_runs':0}),flush=True)
