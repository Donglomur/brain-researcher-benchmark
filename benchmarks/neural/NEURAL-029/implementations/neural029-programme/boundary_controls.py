"""Focused generated boundary controls; no Docker, neural data or model calls.

The complete executor control substitutes the native producer and numeric
grader with inert leaves. It tests ordering and path/mode handling, not a
scientific score or native isolation. Historical source pins remain preserved;
the current numerical scorer successor has a separate exact binding below.
"""
import copy
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
BOOT = {'__file__': str(HERE/'run.py'), '__name__': 'boundary_control_bootstrap'}
exec(compile((HERE/'run.py').read_bytes(), str(HERE/'run.py'), 'exec'), BOOT)
MANIFEST_RAW = (HERE/'SOURCE_MANIFEST.json').read_bytes()
MANIFEST, BODIES = BOOT['source_check'](len(MANIFEST_RAW), hashlib.sha256(MANIFEST_RAW).hexdigest())
executor = BOOT['load_runtime'](BODIES)
contract = sys.modules['runtime_contract']
for name in ('holder', 'source_identity_join'):
    module = types.ModuleType(name); module.__file__ = str(HERE/(name+'.py'))
    sys.modules[name] = module
    exec(compile(BODIES[name+'.py'], module.__file__, 'exec'), module.__dict__)
# Reuse only the accepted generated Docker-inspection fixture. No NumPy setup,
# candidate programme, grader or original scientific test is executed here.
ORIGINAL_TESTS = {'__file__': str(HERE/'tests.py'), '__name__': 'accepted_fixture_source'}
saved_path = list(sys.path)
exec(compile(BODIES['tests.py'], str(HERE/'tests.py'), 'exec'), ORIGINAL_TESTS)
sys.path[:] = saved_path
FixtureDocker = ORIGINAL_TESTS['FakeDocker']


def write(path, value):
    raw = json.dumps(value, sort_keys=True).encode()
    path.write_bytes(raw)
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


class BoundaryControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='neural029-boundary-generated-')
        self.base = Path(self.temp.name).resolve()
        self.prepared = self.base/'prepared'
        (self.prepared/'public').mkdir(parents=True)
        (self.prepared/'private').mkdir()
        (self.base/'config').mkdir()
        self.program = self.base/'program.py'; self.program.write_text('# inert generated fixture\n')
        self.docker = self.base/'docker'; self.docker.write_text('not an executable\n')
        pairs = []
        for i in range(3):
            key = hashlib.sha256(str(i).encode()).hexdigest()
            raw = b'inert-public-NPZ-fixture-no-array-decoder'; name = key+'.npz'
            (self.prepared/'public'/name).write_bytes(raw)
            pairs.append({'pair_id': key, 'cell_ids': ['a'*64], 'query_ids': ['b'*64],
                'source_delay_seconds': 1, 'target_delay_seconds': 2, 'reward_type': 'DAT',
                'calibration_trials': 4, 'validation_trials': 1,
                'file': {'path': 'public/'+name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}})
        public = {'schema': 'neural029-public-v1', 'time_seconds': [i/20 for i in range(61)], 'pairs': pairs}
        pub = write(self.prepared/'public/MANIFEST.json', public)
        self.binding = self.prepared/'private/BINDING.json'
        write(self.binding, {'schema': 'neural029-binding-v2',
            'public': {'path': 'public/MANIFEST.json', **pub}, 'private': {}, 'identity': {}})
        def pin(path):
            raw = path.read_bytes(); return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        self.request = {'schema': 'neural029-program-request-v1', 'program': str(self.program),
            'program_pin': pin(self.program), 'prepared_root': str(self.prepared),
            'public_manifest_pin': pub, 'binding': str(self.binding), 'method_root': str(HERE),
            'grader_python': sys.executable, 'docker': str(self.docker), 'docker_pin': pin(self.docker),
            'docker_host': 'unix:///generated-neural029-not-real.sock', 'docker_config': str(self.base/'config'),
            'image': 'sha256:'+'0'*64, 'output': str(self.base/'run'),
            'candidate_wall_seconds': 10, 'grade_wall_seconds': 10, 'cleanup_wall_seconds': 30,
            'whole_wall_seconds': 150, 'candidate_cpu_seconds': 10, 'candidate_memory_bytes': 536870912,
            'candidate_nano_cpus': 1000000000, 'host_memory_budget_bytes': 536870912,
            'retention_budget_bytes': 536870912}

    def tearDown(self):
        self.temp.cleanup()

    def test_binding_metadata_not_admitted_by_request_validation(self):
        original = Path.is_symlink
        def watched(path):
            if path == self.binding or path == self.prepared/'private':
                raise AssertionError('private metadata before closure')
            return original(path)
        with patch.object(Path, 'is_symlink', watched):
            executor.validate_request(self.request)

    def test_actual_cli_passes_its_request_path_to_alias_admission(self):
        path=self.base/'operator-request.json'
        write(path,dict(self.request,binding=str(path)))
        run=subprocess.run([sys.executable,'-I','-S','-B',str(HERE/'run.py'),'run',
            '--source-bytes',str(len(MANIFEST_RAW)),'--source-sha256',hashlib.sha256(MANIFEST_RAW).hexdigest(),
            '--request',str(path)],capture_output=True,timeout=5)
        self.assertLess(len(run.stdout)+len(run.stderr),131072)
        self.assertNotEqual(run.returncode,0)
        self.assertIn(b'lexically disjoint',run.stderr)
        self.assertFalse(Path(self.request['output']).exists())

    def test_all_private_aliases_refuse_before_any_metadata_query(self):
        request_path = str(self.base/'operator-request.json')
        bindings = [self.request[k] for k in ('program', 'docker', 'grader_python', 'output')]
        bindings += [str(self.prepared/'public/MANIFEST.json'), str(HERE/'core.py'),
                     str(HERE/'run.py'), str(self.base/'config/config.json'),
                     self.request['docker_host'][7:], request_path]
        for binding in bindings:
            with self.subTest(binding=binding):
                r = dict(self.request, binding=binding)
                with patch.object(Path, 'is_symlink', side_effect=AssertionError('metadata before alias refusal')):
                    with self.assertRaisesRegex(ValueError, 'lexically disjoint'):
                        executor.validate_request(r, request_path=request_path)
        for key in ('program', 'method_root', 'docker', 'docker_config', 'output', 'grader_python'):
            with self.subTest(private_subtree_operand=key):
                r = dict(self.request); r[key] = str(self.prepared/'private'/key)
                with patch.object(Path, 'is_symlink', side_effect=AssertionError('metadata before alias refusal')):
                    with self.assertRaisesRegex(ValueError, 'lexically disjoint'):
                        executor.validate_request(r)

    def test_double_root_spellings_refuse_before_any_metadata_query(self):
        for key in ('program', 'prepared_root', 'binding', 'method_root', 'grader_python',
                    'docker', 'docker_config', 'output'):
            with self.subTest(key=key):
                r = dict(self.request); r[key] = '/'+r[key]
                with patch.object(Path, 'is_symlink', side_effect=AssertionError('double root metadata query')):
                    with self.assertRaisesRegex(ValueError, 'Canonical lexical path'):
                        executor.validate_request(r)
        r = dict(self.request, docker_host='unix:////generated.sock')
        with patch.object(Path, 'is_symlink', side_effect=AssertionError('socket metadata query')):
            with self.assertRaisesRegex(ValueError, 'Canonical lexical path'):
                executor.validate_request(r)
            with self.assertRaisesRegex(ValueError, 'Canonical lexical path'):
                executor.validate_request(self.request, request_path='//operator/request.json')

    def test_umask077_public_directory_and_files_have_explicit_modes(self):
        work = self.base/'staged'; work.mkdir()
        old = os.umask(0o077)
        try:
            result = executor.stage_public(self.request, work)
        finally:
            os.umask(old)
        self.assertEqual(result['pairs'], 3)
        self.assertEqual(stat.S_IMODE((work/'public').stat().st_mode), 0o755)
        self.assertTrue(all(stat.S_IMODE(p.stat().st_mode) == 0o444 for p in (work/'public').iterdir()))

    def native_fixture(self, role):
        mounts = ({'/trusted/holder.py': {'type':'bind','source':str(HERE/'holder.py'),'rw':False},
                   '/capture': {'type':'volume','source':'generated-volume','rw':False},
                   '/export': {'type':'bind','source':str(self.base/'export'),'rw':True}}
                  if role == 'holder' else
                  {'/program/candidate.py': {'type':'bind','source':str(self.program),'rw':False},
                   '/input/public': {'type':'bind','source':str(self.prepared/'public'),'rw':False},
                   '/output': {'type':'volume','source':'generated-volume','rw':True}})
        fake = FixtureDocker(self.request, self.base, time.monotonic()+30)
        argv = contract.create_argv('generated', role, mounts, self.request)
        fake.call(argv)
        return argv, fake.resources['generated']['info'], mounts

    def test_exact_requested_and_effective_private_namespaces_for_both_roles(self):
        for role in ('holder', 'candidate'):
            argv, info, mounts = self.native_fixture(role)
            self.assertEqual(argv[argv.index('--ipc')+1], 'private')
            self.assertNotIn('--pid', argv)
            self.assertEqual(contract.verify(info, 'generated', role, mounts, self.request)['role'], role)
            for field in ('PidMode', 'IpcMode'):
                for bad in ('host', 'container:other', 'container:generated', 'shareable', None,
                            'private' if field == 'PidMode' else ''):
                    with self.subTest(role=role, field=field, value=bad):
                        changed = copy.deepcopy(info); changed['HostConfig'][field] = bad
                        with self.assertRaisesRegex(ValueError, 'private PID/IPC'):
                            contract.verify(changed, 'generated', role, mounts, self.request)
                changed = copy.deepcopy(info); del changed['HostConfig'][field]
                with self.assertRaisesRegex(ValueError, 'private PID/IPC'):
                    contract.verify(changed, 'generated', role, mounts, self.request)

    def execute_with_boundary_leaves(self, fail_cleanup=False):
        trace = {'closed': False, 'private_metadata': [], 'private_reads': []}
        self.last_trace = trace
        request = self.request
        class NativeLeaf:
            def __init__(self, r, output, end):
                self.end=end; self.resources=set()
            def volume(self, name): self.resources.add(name)
            def create(self, name, role, mounts): self.resources.add(name)
            def remove(self, kind, name): self.resources.discard(name)
            def inspect(self, kind, name):
                return {'State': {'Running':'holder' in name, 'Pid':100 if 'holder' in name else 0,
                                  'OOMKilled':False, 'ExitCode':0}}
            def call(self, argv, seconds=10):
                out='0' if argv[0]=='wait' else ''
                if argv[0]=='exec':
                    assert not any('candidate' in name for name in self.resources)
                    path=Path(request['output'])/'capture/submission.json'
                    pin=write(path, {'schema':'generated-inert-boundary-submission'})
                    out=json.dumps({'status':'captured', **pin})
                return {'returncode':0, 'stdout':out, 'stderr':''}
            def close(self):
                if fail_cleanup: return ['generated closure failure']
                self.resources.clear(); trace['closed']=True; return []
        def grade_leaf(argv, env, end, seconds):
            assert trace['closed']
            write(Path(argv[-1]), {'schema':'neural029-grade-v2','all_pairs_retained':True,'pairs':[{}, {}, {}]})
            return {'returncode':0, 'stdout':'', 'stderr':''}
        def private(path):
            p=Path(path); root=self.prepared/'private'
            return p==root or root in p.parents
        with ExitStack() as stack:
            for name in ('is_symlink', 'lstat', 'stat', 'resolve'):
                original=getattr(Path,name)
                def guarded(path, *args, _original=original, _name=name, **kwargs):
                    if private(path):
                        trace['private_metadata'].append((_name,str(path),trace['closed']))
                        assert trace['closed'], 'private metadata before closure'
                    return _original(path,*args,**kwargs)
                stack.enter_context(patch.object(Path,name,guarded))
            original_read=executor.safe.read
            def read(path,*args,**kwargs):
                if private(path):
                    trace['private_reads'].append((str(path),trace['closed']))
                    assert trace['closed'], 'private body before closure'
                return original_read(path,*args,**kwargs)
            stack.enter_context(patch.object(executor.safe,'read',read))
            stack.enter_context(patch.object(executor,'Docker',NativeLeaf))
            stack.enter_context(patch.object(executor,'bounded_command',grade_leaf))
            if fail_cleanup:
                with self.assertRaisesRegex(ValueError,'resources absent'):
                    executor.execute(request,request_path=str(self.base/'operator-request.json'))
                self.assertFalse(trace['private_metadata']); self.assertFalse(trace['private_reads'])
            else:
                result=executor.execute(request,request_path=str(self.base/'operator-request.json'))
                self.assertEqual(result['status'],'programme_captured_and_graded')
                self.assertTrue(trace['private_metadata']); self.assertTrue(trace['private_reads'])
        return trace

    def test_actual_executor_defers_private_metadata_and_body_until_closure(self):
        trace=self.execute_with_boundary_leaves()
        self.assertTrue(all(row[-1] for row in trace['private_metadata']+trace['private_reads']))

    def test_actual_failed_cleanup_never_touches_private_metadata_or_body(self):
        self.execute_with_boundary_leaves(fail_cleanup=True)

    def test_private_symlink_is_refused_only_after_complete_resource_closure(self):
        self.binding.unlink(); self.binding.symlink_to(self.program)
        with self.assertRaisesRegex(ValueError, 'Canonical no-link path'):
            self.execute_with_boundary_leaves()
        self.assertTrue(self.last_trace['closed'])
        self.assertTrue(self.last_trace['private_metadata'])
        self.assertTrue(all(row[-1] for row in self.last_trace['private_metadata']))
        self.assertFalse(self.last_trace['private_reads'])

    def test_scientific_method_and512MiB_resource_reservation_unchanged(self):
        previous=json.loads((HERE/'PREDECESSOR.json').read_bytes())['files']
        for name in ('grade.py','source_identity_join.py','io_utils.py','RESOURCE_BOUND.json'):
            raw=(HERE/name).read_bytes()
            self.assertEqual(len(raw),previous[name]['bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),previous[name]['sha256'])
        # PREDECESSOR is historical evidence, not the current numerical scorer.
        # Pin the reviewed successor separately while preserving the original
        # metric definitions, target reader, identity join and resource policy.
        self.assertEqual(previous['core.py'], {
            'bytes': 7275,
            'sha256': '69257f2b7d7931100834f1b36812a3b3652829caa4dbeadf963ccb85e4803550'})
        current = {'bytes': len(BODIES['core.py']),
                   'sha256': hashlib.sha256(BODIES['core.py']).hexdigest()}
        self.assertEqual(current, {
            'bytes': 9137,
            'sha256': 'cfa13c3d1e43e7705221c74c6fe5ba1000934e3a743a014f4682b8445b3f3ed1'})
        self.assertEqual(executor.METHOD['core.py'], (current['bytes'], current['sha256']))
        resource=json.loads(BODIES['RESOURCE_BOUND.json'])
        self.assertEqual(resource['aggregate_reservation_minimum_bytes'],536870912)
        self.assertEqual(contract.OUTPUT_BYTES,100000000)
        self.assertEqual(contract.VOLUME_BYTES,134217728)


if __name__=='__main__':
    unittest.main()
