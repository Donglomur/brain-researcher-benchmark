"""Generated controls only; no authentic packet, Docker or model execution."""
import copy
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common
import grade
import run
from transport import bounds, holder, provider
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

    def holder_start(self, cpu, memory, accepted):
        """Actual main/guard and policy parser; generated kernel views, no container."""
        cgroup = self.root / 'cgroup'
        for name, value in {'cpu.max': cpu, 'memory.max': memory,
                            'memory.swap.max': '0', 'pids.max': '64'}.items():
            save(cgroup / name, (value + '\n').encode('ascii'))
        ready = self.root / 'ready'
        ready.mkdir(mode=0o700, exist_ok=True)
        policy = {'schema': 'osl_holder_policy_v1', 'phase_id': 'generated',
                  'role': 'A', 'file_cap': 35651584, 'total_cap': 41943040,
                  'files': 3, 'directories': 1}
        policy_path = self.root / 'POLICY.json'
        policy_pin = save(policy_path, common.encoded(policy))
        mountinfo = self.root / 'mountinfo'
        save(mountinfo, (
            '1 0 0:1 / /capture ro,noexec,nosuid,nodev - tmpfs tmpfs ro\n'
            f'2 0 0:2 / {ready} rw,noexec,nosuid,nodev - tmpfs tmpfs rw\n'
        ).encode('utf-8'))
        real_lstat = Path.lstat

        def kernel_path(value):
            return {'/sys/fs/cgroup': cgroup,
                    '/proc/self/mountinfo': mountinfo}.get(value, Path(value))

        def kernel_lstat(path):
            result = real_lstat(path)
            if path == ready:
                fields = {name: getattr(result, name) for name in holder.FIELDS}
                fields.update(st_uid=65534, st_gid=65534)
                return SimpleNamespace(**fields)
            return result

        def kernel_statvfs(path):
            self.assertIn(path, (Path('/capture'), ready))
            return SimpleNamespace(f_blocks=41943040 if path == Path('/capture') else 4096,
                                   f_frsize=1)

        class HoldStarted(Exception):
            pass

        owner = 'osl-' + 'a' * 24 + '/holder'
        argv = ['holder.py', 'hold', '--owner-token', owner, '--role', 'A',
                '--policy', str(policy_path), '--policy-sha256', policy_pin['sha256']]
        with ExitStack() as stack:
            stack.enter_context(patch.object(holder, 'Path', side_effect=kernel_path))
            stack.enter_context(patch.object(holder, 'READY_ROOT', ready))
            stack.enter_context(patch.object(holder, 'POLICY', None))
            stack.enter_context(patch.object(Path, 'lstat', kernel_lstat))
            stack.enter_context(patch.object(holder.os, 'getuid', return_value=65534))
            stack.enter_context(patch.object(holder.os, 'statvfs', side_effect=kernel_statvfs))
            stack.enter_context(patch.object(sys, 'argv', argv))
            publish = stack.enter_context(patch.object(holder, 'publish_ready'))
            sleep = stack.enter_context(patch.object(holder.time, 'sleep', side_effect=HoldStarted))
            with self.assertRaises(HoldStarted if accepted else ValueError):
                holder.main()
            if accepted:
                publish.assert_called_once_with(Path('/capture'), owner)
                sleep.assert_called_once_with(1)
            else:
                publish.assert_not_called()
                sleep.assert_not_called()

    def test_holder_quarter_cpu_256mib_profiles_reach_readiness(self):
        for cpu in ('25000 100000', '250000 1000000', '1 4'):
            with self.subTest(cpu=cpu):
                self.holder_start(cpu, '268435456', True)

    def test_holder_old_and_independent_mismatches_refuse_before_readiness(self):
        for cpu, memory in (('100000 100000', '134217728'),
                            ('100000 100000', '268435456'),
                            ('25000 100000', '134217728')):
            with self.subTest(cpu=cpu, memory=memory):
                self.holder_start(cpu, memory, False)

    def test_holder_unlimited_nonpositive_and_malformed_cpu_refuse_readiness(self):
        for cpu in ('max 100000', '0 100000', '25000 0', '0 0', '-1 -4',
                    '-25000 100000', '25000 -100000', '25001 100000',
                    '', '25000', '25000 100000 extra', '25000.0 100000', 'invalid'):
            with self.subTest(cpu=cpu):
                self.holder_start(cpu, '268435456', False)

    def test_holder_unlimited_nonpositive_and_malformed_memory_refuse_readiness(self):
        for memory in ('max', '0', '-1', '268435455', '268435457', '', 'invalid'):
            with self.subTest(memory=memory):
                self.holder_start('25000 100000', memory, False)

    def test_committed_public_program_mode_under_private_umask(self):
        program = self.generated_program()
        original = program.read_bytes()
        destination = self.root / 'attempt'
        real_fchmod, calls = os.fchmod, []

        def finalize(fd, mode):
            before = os.fstat(fd)
            self.assertTrue(stat.S_ISREG(before.st_mode))
            self.assertEqual(stat.S_IMODE(before.st_mode), 0o400)
            self.assertEqual(before.st_size, len(original))
            calls.append(mode)
            real_fchmod(fd, mode)

        previous = os.umask(0o077)
        try:
            with patch.object(common.os, 'fchmod', side_effect=finalize):
                identity = run.commit(program, destination, self.source, {})
            self.assertEqual(os.umask(0o077), 0o077)
        finally:
            os.umask(previous)
        self.assertEqual(calls, [0o444])
        self.assertEqual(identity, common.pin(original))
        self.assertEqual((destination / 'program.py').read_bytes(), original)
        self.assertEqual(stat.S_IMODE((destination / 'program.py').stat().st_mode), 0o444)
        self.assertEqual(stat.S_IMODE((destination / 'COMMIT.json').stat().st_mode), 0o400)
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o700)

    def test_public_request_policy_and_private_transport_modes_under077(self):
        global WRITTEN
        control = self.root / 'control'
        meter = bounds.Meter(1024, 4096, time.monotonic() + 10)
        real_fchmod, calls = os.fchmod, []
        payload = b'{"generated":"transport metadata"}\n'

        def finalize(fd, mode):
            before = os.fstat(fd)
            self.assertTrue(stat.S_ISREG(before.st_mode))
            self.assertEqual(stat.S_IMODE(before.st_mode), 0o400)
            self.assertEqual(before.st_size, len(payload))
            calls.append(mode)
            real_fchmod(fd, mode)

        previous = os.umask(0o077)
        try:
            control.mkdir(mode=0o700)
            with patch.object(bounds.os, 'fchmod', side_effect=finalize):
                for name in ('REQUEST.json', 'POLICY.json'):
                    self.assertEqual(bounds.publish(control / name, payload, meter, mode=0o444),
                                     common.pin(payload))
                bounds.publish(control / 'OWNERSHIP.json', payload, meter)
            self.assertEqual(os.umask(0o077), 0o077)
        finally:
            os.umask(previous)
            WRITTEN += meter.write_bytes
        self.assertEqual(calls, [0o444, 0o444])
        for name in ('REQUEST.json', 'POLICY.json'):
            self.assertEqual((control / name).read_bytes(), payload)
            self.assertEqual(stat.S_IMODE((control / name).stat().st_mode), 0o444)
        self.assertEqual(stat.S_IMODE((control / 'OWNERSHIP.json').stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(control.stat().st_mode), 0o700)

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
                predicted.chmod(0o600)
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

    def test_captured_prediction_finalization_preserves_private_boundary(self):
        parent = self.root / 'capture'
        parent.mkdir(mode=0o700)
        previous = os.umask(0o077)
        try:
            prediction = parent / 'predictions.npz'
            expected = save(prediction, b'generated complete opaque prediction')
            private = parent / 'PRIVATE.json'
            save(private, b'private generated record')
            self.assertEqual(stat.S_IMODE(prediction.stat().st_mode), 0o600)
            before = prediction.stat()
            self.assertEqual(common.prepare_grader_prediction(prediction, expected), expected)
            self.assertEqual(common.pin(prediction.read_bytes()), expected)
            self.assertEqual(stat.S_IMODE(prediction.stat().st_mode), 0o444)
            self.assertEqual((before.st_ino, before.st_size, before.st_mtime_ns),
                             (prediction.stat().st_ino, prediction.stat().st_size, prediction.stat().st_mtime_ns))
            self.assertEqual(stat.S_IMODE(parent.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o600)
            self.assertEqual(os.umask(0o077), 0o077)
        finally:
            os.umask(previous)

    def test_captured_prediction_wrong_identity_stays_private(self):
        prediction = self.root / 'predictions.npz'
        save(prediction, b'generated owned capture')
        prediction.chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'Frozen prediction identity'):
            common.prepare_grader_prediction(prediction, common.pin(b'different'))
        self.assertEqual(stat.S_IMODE(prediction.stat().st_mode), 0o600)

    def test_captured_prediction_rejects_aliases_before_public_mode(self):
        prediction = self.root / 'predictions.npz'
        expected = save(prediction, b'generated owned capture')
        prediction.chmod(0o600)
        symbolic = self.root / 'symbolic.npz'
        symbolic.symlink_to(prediction)
        with self.assertRaises(ValueError):
            common.prepare_grader_prediction(symbolic, expected)
        linked = self.root / 'hard.npz'
        os.link(prediction, linked)
        with self.assertRaises(ValueError):
            common.prepare_grader_prediction(prediction, expected)
        fifo = self.root / 'pipe.npz'
        os.mkfifo(fifo, 0o600)
        with self.assertRaises(ValueError):
            common.prepare_grader_prediction(fifo, expected)
        self.assertEqual(stat.S_IMODE(prediction.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(linked.stat().st_mode), 0o600)

    def test_complete_exposes_only_committed_prediction_before_grader(self):
        output = self.root / 'attempt'
        identity = run.commit(self.generated_program(), output, self.source, {})
        capture_root = self.root / 'captured'
        capture_root.mkdir(mode=0o700)
        predicted = capture_root / 'predictions.npz'
        prediction_pin = save(predicted, b'generated opaque invalid archive')
        predicted.chmod(0o600)
        private = capture_root / 'PRIVATE.json'
        save(private, b'private generated receipt')
        private.chmod(0o600)
        tester, calls = self, []
        class GeneratedBackend:
            def produce(self, programme):
                tester.assertEqual(stat.S_IMODE(predicted.stat().st_mode), 0o600)
                return predicted, {'source':tester.source,'program':programme,
                    'submission':prediction_pin,'producer_removed_before_capture':True,
                    'all_native_resources_closed':True}
        def grader(action, path, destination, config, deadline, source):
            calls.append(action)
            tester.assertEqual(path, predicted)
            tester.assertTrue((output/'PREDICTION_COMMIT.json').exists())
            tester.assertEqual(common.pin(path.read_bytes()), prediction_pin)
            tester.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o444)
            tester.assertEqual(stat.S_IMODE(capture_root.stat().st_mode), 0o700)
            tester.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o600)
            return {'status':'rejected_no_score','target_loader_invocations':0}
        result = run.complete({}, output, self.source, identity, GeneratedBackend(), grader,
                              time.monotonic()+140)
        self.assertEqual(calls, ['score'])
        self.assertEqual(result['status'], 'rejected_no_score')
        self.assertTrue((output/'COMPLETE.json').exists())

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
        for enabled in ('no-new-privileges', 'no-new-privileges:true'):
            for extra in ([], ['label=disable']):
                info['HostConfig']['SecurityOpt'] = [enabled, *extra]
                with self.subTest(enabled=enabled, extra=extra):
                    grade.inspect_contract(info,name,mounts,'score','b'*64)
        invalid = [None, 'no-new-privileges', {'no-new-privileges': True}, [],
                   ['label=disable'], ['no-new-privileges:false'],
                   ['no-new-privileges:true', 'no-new-privileges:false'],
                   ['no-new-privileges', 'no-new-privileges:true'],
                   ['no-new-privileges:true', 'no-new-privileges:true'],
                   ['no-new-privileges', 'no-new-privileges'],
                   ['no-new-privileges:yes'], ['no-new-privileges:true:true'],
                   ['no-new-privileges=true'], [1], ['no-new-privileges', None]]
        for options in invalid:
            bad = copy.deepcopy(info)
            bad['HostConfig']['SecurityOpt'] = options
            with self.subTest(options=options), self.assertRaises(ValueError):
                grade.inspect_contract(bad,name,mounts,'score','b'*64)
        # Other admission checks must hold under either accepted spelling.
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
        for name in ('__init__.py','archive.py','contract.py','engine.py'):
            original=common.REPO/'benchmarks/neural/NEURAL-007/implementations/whole-night-programme/program/vendor_transport'/name
            self.assertEqual((HERE/'transport'/name).read_bytes(),original.read_bytes())
        self.assertNotIn('holder.py', source['unchanged_transport_modules'])
        self.assertNotIn('bounds.py', source['unchanged_transport_modules'])
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
