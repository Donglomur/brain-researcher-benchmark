"""Independent production-function controls with invented RAM/process seams only.

No child is started. No real timer, socket, Docker daemon, dataset or filesystem
artifact is used. The imported review harness reads only Python source files.
"""
import copy
import importlib.util
from pathlib import Path
import signal
import stat
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('isttc_native_review_harness', Path(__file__).with_name('test_native.py'))
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
N = T.n
holder_spec = importlib.util.spec_from_file_location('isttc_holder_review_harness', Path(__file__).with_name('test_holder.py'))
F = importlib.util.module_from_spec(holder_spec)
holder_spec.loader.exec_module(F)


class Stream:
    def __init__(self, label, events, fail=False):
        self.label, self.events, self.fail = label, events, fail
    def fileno(self): return 40 if self.label == 'stdout' else 41
    def close(self):
        self.events.append(('stream_close', self.label))
        if self.fail: raise OSError('invented stream closure error')


class Process:
    pid = 123456
    def __init__(self, events, waits=None, stream_fail=False):
        self.events = events
        self.waits = list(waits or [0])
        self.stdout = Stream('stdout', events, fail=stream_fail)
        self.stderr = Stream('stderr', events)
    def wait(self, timeout):
        self.events.append(('wait', timeout))
        result = self.waits.pop(0) if self.waits else 0
        if isinstance(result, BaseException): raise result
        return result


class Selector:
    def __init__(self, events, fail=False): self.events, self.fail = events, fail
    def register(self, stream, event, key): self.events.append(('register', key))
    def get_map(self): return {}  # invented already-drained empty response
    def close(self):
        self.events.append(('selector_close',))
        if self.fail: raise OSError('invented selector closure error')


class IndependentNativeControls(unittest.TestCase):
    def setUp(self):
        T.FakeDocker.instances = []
        T.FakeDocker.fail = None

    def test_relative_domain_matches_holder_ascii(self):
        for name in ('methods.json', 'view/VIEW.json', 'view/a-b_1.npy'):
            self.assertEqual(N.relative_name(name), name)
        for name in ('view/space name.npy', 'view/é.npy', '.hidden', 'view/a:b', 'view/../x',
                     'view//x', '/absolute', 'a' * 513, '/'.join(['a'] * 9)):
            with self.assertRaises(ValueError): N.relative_name(name)

    def test_actual_mount_domains_require_exact_types(self):
        for phase in ('reproduction', 'improvement', 'reference'):
            directory_targets = ('/input',)
            target_sources = {'/input': '/invented/input', '/request.json': '/invented/request.json'}
            kinds = {str(source): stat.S_IFDIR | 0o700 if target in directory_targets else stat.S_IFREG | 0o400
                     for target, source in target_sources.items()}
            kinds['/invented/program.py'] = stat.S_IFREG | 0o400
            links = {name: 2 if stat.S_ISDIR(mode) else 1 for name, mode in kinds.items()}
            def status(path): return SimpleNamespace(st_mode=kinds[str(path)], st_nlink=links[str(path)], st_size=8)
            request = T.req(phase, sorted(N.OUTPUTS[phase]))
            def invoke():
                return N.checked_mounts(phase, target_sources,
                                        Path('/invented/program.py') if phase != 'reference' else None,
                                        Path('/invented/source'), request)
            with patch.object(N, 'path', side_effect=Path), patch.object(Path, 'lstat', status):
                got = invoke()
                self.assertTrue(all(value[2] is False for value in got.values()))
                for target, source in target_sources.items():
                    original_mode = kinds[source]
                    kinds[source] = stat.S_IFREG | 0o400 if target in directory_targets else stat.S_IFDIR | 0o700
                    with self.assertRaises(ValueError): invoke()
                    kinds[source] = original_mode
                links['/invented/request.json'] = 2
                with self.assertRaises(ValueError): invoke()

    def test_selected_eight_mib_program_domains_and_reference_program_refusal(self):
        for phase, cap in [('reproduction', 8388608), ('improvement', 8388608)]:
            size = [cap]
            def status(path):
                directory = str(path) == '/invented/input'
                return SimpleNamespace(st_mode=(stat.S_IFDIR | 0o700) if directory else (stat.S_IFREG | 0o400),
                                       st_nlink=2 if directory else 1,
                                       st_size=size[0] if str(path) == '/invented/program.py' else 8)
            def invoke(role=phase, program=Path('/invented/program.py')):
                return N.checked_mounts(role, {'/input': '/invented/input', '/request.json': '/invented/request.json'},
                                        program, Path('/invented/source'), T.req(role, sorted(N.OUTPUTS[role])))
            with patch.object(N, 'path', side_effect=Path), patch.object(Path, 'lstat', status):
                self.assertIn('/program/program.py', invoke())
                for bad in (0, cap + 1, 16777216):
                    size[0] = bad
                    with self.assertRaisesRegex(ValueError, 'program.*domain'): invoke()
                size[0] = 1
                self.assertIn('/program/program.py', invoke())
                self.assertNotIn('/program/program.py', invoke('reference', None))
                with self.assertRaisesRegex(ValueError, 'no candidate program'):
                    invoke('reference', Path('/invented/program.py'))

    def test_exact_source_bound_helper_maps_for_every_role(self):
        common = {'/trusted/entry_common.py': 'entry_common.py'}
        reference = dict(common, **{'/trusted/baseline.py': 'baseline/baseline.py',
                                   '/trusted/read_inputs.py': 'baseline/read_inputs.py'})
        suffixes = ('__init__.py', 'acfunc.py', 'tau.py', 'spike_utils.py',
                    'scripts/__init__.py', 'scripts/calculate_acf.py',
                    'scripts/calculate_tau.py', 'scripts/spike_train_utils.py')
        for suffix in suffixes:
            reference['/trusted/source/src/isttc/' + suffix] = 'baseline/source/src/isttc/' + suffix
        self.assertEqual(N.SUPPORT, {'reproduction': common, 'improvement': common, 'reference': reference})
        self.assertEqual(len(N.SUPPORT['reference']), 11)
        self.assertEqual(N.relative_name('__init__.py'), '__init__.py')
        self.assertEqual(N.relative_name('scripts/__init__.py'), 'scripts/__init__.py')
        for role in ('reproduction', 'improvement', 'reference'):
            request = T.req(role, sorted(N.OUTPUTS[role]))
            N.validate_request(role, request)
            self.assertEqual(request['entry_support'], N.SUPPORT[role])
            for target in request['entry_support']:
                alias = copy.deepcopy(request)
                alias['entry_support'][target] = 'different_source.py'
                with self.assertRaisesRegex(ValueError, 'support|helper'):
                    N.validate_request(role, alias)
                missing = copy.deepcopy(request)
                del missing['entry_support'][target]
                with self.assertRaisesRegex(ValueError, 'support|helper'):
                    N.validate_request(role, missing)
            extra = copy.deepcopy(request)
            extra['entry_support']['/trusted/extra.py'] = 'extra.py'
            with self.assertRaisesRegex(ValueError, 'support|helper'):
                N.validate_request(role, extra)

    def test_exact_role_output_names_caps_and_empty_refusal(self):
        holder = {'owner': 'isttc-' + 'a' * 24 + '/holder'}
        def inventory(role, sizes):
            files = [{'name': name, 'bytes': size,
                      'stamp': [1, i + 2, stat.S_IFREG | 0o400, size, 1, 65534, 65534, 1, 1]}
                     for i, (name, size) in enumerate(sorted(sizes.items()))]
            return dict(schema='isttc_capture_inventory_v1', owner=holder['owner'], role=role,
                        root_stamp=[1, 1, stat.S_IFDIR | 0o700, 0, 2, 65534, 65534, 1, 1],
                        directories=[], files=files, total_bytes=sum(sizes.values()))
        expected = {role: {'estimates.csv': 100000000, 'methods.json': 20000}
                    for role in ('reproduction', 'improvement', 'reference')}
        self.assertEqual(N.OUTPUTS, expected)
        for role, sizes in expected.items():
            valid = inventory(role, sizes)
            N.artifact_inventory(N.encoded(valid), holder, role, sorted(sizes))
            for name in sizes:
                for bad in (0, sizes[name] + 1):
                    excessive = dict(sizes)
                    excessive[name] = bad
                    with self.assertRaisesRegex(ValueError, 'artifact extent'):
                        N.artifact_inventory(N.encoded(inventory(role, excessive)), holder, role, sorted(sizes))
            request = T.req(role, ['unexpected.json'])
            with self.assertRaisesRegex(ValueError, 'role output filenames'): N.validate_request(role, request)

    def test_role_cpu_memory_and_exact_transport_budget(self):
        for role in ('reproduction', 'improvement', 'reference'):
            cpu, memory, chunks, total = '4', 8589934592, 28, 100020000
            prefix = 'isttc-' + 'c' * 24
            item = dict(kind='container', name=prefix + '-' + role, owner=prefix + '/' + role)
            mounts = {'/input': ('bind', Path('/input-source'), False)}
            argv = N.create_args(item, role, mounts, memory, T.IMAGE, role)
            self.assertEqual(argv[argv.index('--cpus') + 1], cpu)
            self.assertEqual(argv[argv.index('--memory') + 1], str(memory))
            d = T.FakeDocker('/invented/docker', '/invented/socket')
            ident = d.route(argv, 'create_' + role).decode().strip()
            item['id'] = ident
            value = d.items[ident]
            N.admission(value, item, role, mounts, memory, T.IMAGE, role)
            scratch = '/work' if role == 'reference' else '/tmp'
            self.assertEqual(value['HostConfig']['Tmpfs'], {scratch: 'rw,nosuid,nodev,noexec,size=134217728'})
            wrong_scratch = copy.deepcopy(value)
            wrong_scratch['HostConfig']['Tmpfs']['/other'] = 'rw,nosuid,nodev,noexec,size=134217728'
            with self.assertRaisesRegex(ValueError, 'scratch'):
                N.admission(wrong_scratch, item, role, mounts, memory, T.IMAGE, role)
            value['HostConfig']['NanoCpus'] = 1000000000
            with self.assertRaisesRegex(ValueError, 'typed resource'):
                N.admission(value, item, role, mounts, memory, T.IMAGE, role)
            budget = N.phase_budget(role, len(N.OUTPUTS[role]))
            self.assertEqual((budget['max_chunks'], budget['host_artifact_bytes']), (chunks, total))
            self.assertEqual((budget['max_calls'], budget['reply_budget']), (158, 174003616))
            self.assertEqual(N.TIMES[role], dict(setup_seconds=120, producer_seconds=172800,
                                               capture_seconds=1800, cleanup_seconds=120))
            self.assertEqual(sum(N.TIMES[role].values()), 174840)

    def test_actual_source_auth_allows_pinned_empty_package_member_only(self):
        names = ['engine/native.py', 'engine/holder.py', 'reproduction_entry.py',
                 'improvement_entry.py', 'reference_entry.py']
        empty_name = 'baseline/source/src/isttc/scripts/__init__.py'
        files = {name: b'# invented source\n' for name in names}
        files[empty_name] = b''
        manifest = {'files': {name: N.pin(body) for name, body in files.items()}}
        raw = N.encoded(manifest)
        fs = F.MemoryFS()
        for name, body in files.items(): fs.add('/source/' + name, body)
        fs.add('/source/SOURCE_MANIFEST.json', raw)
        executor = T.Executor()
        with fs.patched(), patch.object(N, 'path', side_effect=Path):
            got = N.source_auth(Path('/source'), N.pin(raw), executor)
        self.assertEqual(got['files'][empty_name], N.pin(b''))
        self.assertEqual(got['members'], 6)
        self.assertEqual(got['read_bytes'], len(raw) + 1 + sum(len(b) + 1 for b in files.values()))
        self.assertEqual(executor.reads, got['read_bytes'])
        self.assertEqual(fs.fds, {})
        wrong = copy.deepcopy(manifest)
        wrong['files'][empty_name]['sha256'] = 'f' * 64
        changed = N.encoded(wrong)
        fs.add('/source/SOURCE_MANIFEST.json', changed)
        with fs.patched(), patch.object(N, 'path', side_effect=Path), self.assertRaisesRegex(ValueError, 'source pin'):
            N.source_auth(Path('/source'), N.pin(changed), T.Executor())
        self.assertEqual(fs.fds, {})
        fs.add('/source/SOURCE_MANIFEST.json', b'')
        with fs.patched(), patch.object(N, 'path', side_effect=Path), self.assertRaisesRegex(ValueError, 'bounded source file'):
            N.source_auth(Path('/source'), N.pin(b''), T.Executor())
        self.assertEqual(fs.fds, {})

    def test_empty_descriptor_opt_in_remains_typed(self):
        self.assertEqual(N.descriptor(N.pin(b''), allow_empty=True), N.pin(b''))
        with self.assertRaises(ValueError): N.descriptor(N.pin(b''))
        wrong = N.pin(b'')
        wrong['bytes'] = False
        with self.assertRaises(ValueError): N.descriptor(wrong, allow_empty=True)

    def test_slow_final_publication_refuses_actual_execute_success(self):
        helper = T.NativeControls('test_complete_reproduction_route_and_capture')
        baseline, _, _, _ = helper.run_phase(files=['estimates.csv', 'methods.json'])
        self.assertEqual(baseline['status'], 'captured')
        original = N.execute
        late = []
        def wrapper(*args, **kwargs):
            publish = kwargs['publish']
            def delayed(name, value):
                publish(name, value)
                if name.endswith('-PHASE'):
                    late.append(copy.deepcopy(value))
                    # run_phase owns a mocked monotonic clock: advance that mock only.
                    N.time.monotonic.return_value = value['phase_end'] + 0.01
            kwargs['publish'] = delayed
            return original(*args, **kwargs)
        with patch.object(N, 'execute', wrapper), self.assertRaisesRegex(ValueError, 'after durable receipt'):
            helper.run_phase(files=['estimates.csv', 'methods.json'])
        self.assertEqual(len(late), 1)
        self.assertEqual(late[0]['status'], 'captured')
        self.assertEqual(T.FakeDocker.instances[-1].items, {})
        # The provisional receipt exists, but the function never returns success.

    def test_actual_docker_cap_count_budget_reject_before_spawn(self):
        cases = [('wrong_phase_cap', 2, 8192, [], 4095),
                 ('count_exhausted', 1, 8192, [{}], 4096),
                 ('budget_exhausted', 2, 4095, [], 4096)]
        for label, calls, budget, records, cap in cases:
            with self.subTest(label=label), patch.object(N, 'path', side_effect=Path), \
                    patch.object(N.time, 'monotonic', return_value=100.), \
                    patch.object(N.subprocess, 'Popen') as spawn:
                d = N.Docker('/invented/docker', '/invented/socket', max_calls=calls, reply_budget=budget)
                d.records = records
                with self.assertRaises(ValueError): d(['invented'], 110., 'holder_ready', cap)
                spawn.assert_not_called()
                self.assertEqual(d.reserved, 0)

    def test_holder_admission_exact_false_and_cli_init_option(self):
        prefix = 'isttc-' + 'c' * 24
        item = dict(kind='container', name=prefix + '-holder', owner=prefix + '/holder')
        mounts = {'/trusted/holder.py': ('bind', Path('/source/engine/holder.py'), False),
                  '/capture': ('volume', prefix + '-volume', False)}
        argv = N.create_args(item, 'holder', mounts, N.HOLDER_MEMORY, T.IMAGE, 'reproduction')
        self.assertEqual(argv.count('--init=false'), 1)
        self.assertEqual(argv[argv.index('--memory') + 1], '134217728')
        d = T.FakeDocker('/invented/docker', '/invented/socket')
        ident = d.route(argv, 'create_holder').decode().strip()
        item['id'] = ident
        value = d.items[ident]
        N.admission(value, item, 'holder', mounts, N.HOLDER_MEMORY, T.IMAGE, 'reproduction')
        for bad in (0, True, None, 'false', 'MISSING'):
            changed = copy.deepcopy(value)
            if bad == 'MISSING': changed['HostConfig'].pop('Init')
            else: changed['HostConfig']['Init'] = bad
            with self.assertRaisesRegex(ValueError, 'PID1'):
                N.admission(changed, item, 'holder', mounts, N.HOLDER_MEMORY, T.IMAGE, 'reproduction')

    def command(self, *, stream_fail=False, selector_fail=False, waits=None, group_alive=False):
        events = []
        process = Process(events, waits=waits, stream_fail=stream_fail)
        selector = Selector(events, fail=selector_fail)
        state = {'alive': group_alive}
        def killpg(pid, sig):
            self.assertEqual(pid, process.pid)
            events.append(('killpg', sig))
            if sig == signal.SIGKILL:
                state['alive'] = False
                return
            if not state['alive']: raise ProcessLookupError('invented absent group')
        with patch.object(N, 'path', side_effect=Path), patch.object(N.time, 'monotonic', return_value=100.), \
                patch.object(N.subprocess, 'Popen', return_value=process) as spawn, \
                patch.object(N.selectors, 'DefaultSelector', return_value=selector), \
                patch.object(N.os, 'set_blocking'), patch.object(N.os, 'killpg', side_effect=killpg), \
                patch.object(N.time, 'sleep', side_effect=AssertionError('unexpected live-group polling')):
            d = N.Docker('/invented/docker', '/invented/socket', max_calls=1, reply_budget=4096)
            error = None
            try: body = d(['invented'], 110., 'holder_ready', 4096)
            except BaseException as exc: error, body = exc, None
            self.assertEqual(spawn.call_count, 1)
            self.assertIs(spawn.call_args.kwargs['start_new_session'], True)
        return d, events, body, error

    def test_actual_docker_happy_natural_group_closure(self):
        d, events, body, error = self.command()
        self.assertIsNone(error)
        self.assertEqual(body, b'')
        self.assertTrue(d.reaped)
        N.validate_cli_records(d.records)
        self.assertIn(('stream_close', 'stdout'), events)
        self.assertIn(('stream_close', 'stderr'), events)

    def test_actual_docker_close_faults_attempt_both_streams_and_refuse(self):
        for stream, selector in ((True, False), (False, True), (True, True)):
            d, events, body, error = self.command(stream_fail=stream, selector_fail=selector)
            self.assertIsInstance(error, N.CommandError)
            self.assertIsNone(body)
            self.assertFalse(d.reaped)
            self.assertIn(('selector_close',), events)
            self.assertIn(('stream_close', 'stdout'), events)
            self.assertIn(('stream_close', 'stderr'), events)
            self.assertIs(d.records[0]['cleanup_complete'], False)

    def test_actual_docker_wait_fault_still_kills_reaps_and_closes(self):
        timeout = subprocess.TimeoutExpired('invented', 1)
        d, events, body, error = self.command(waits=[timeout, 0], group_alive=True)
        self.assertIs(error, timeout)
        self.assertIsNone(body)
        self.assertIn(('killpg', signal.SIGKILL), events)
        self.assertEqual(sum(x[0] == 'wait' for x in events), 2)
        self.assertIn(('stream_close', 'stderr'), events)
        self.assertIs(d.records[0]['client_reaped'], True)
        self.assertEqual(d.records[0]['error_type'], 'TimeoutExpired')
        with self.assertRaises(ValueError): N.validate_cli_records(d.records)

    def test_actual_docker_failed_reap_still_closes_other_resources(self):
        timeout = subprocess.TimeoutExpired('invented', 1)
        d, events, body, error = self.command(waits=[timeout, timeout], group_alive=True)
        self.assertIs(error, timeout)
        self.assertFalse(d.reaped)
        self.assertIs(d.records[0]['client_reaped'], False)
        self.assertIs(d.records[0]['cleanup_complete'], False)
        self.assertIn(('selector_close',), events)
        self.assertIn(('stream_close', 'stdout'), events)
        self.assertIn(('stream_close', 'stderr'), events)

    def test_actual_docker_leader_exit_with_live_group_refused_and_cleaned(self):
        d, events, body, error = self.command(group_alive=True)
        self.assertIsInstance(error, N.CommandError)
        self.assertIn(('killpg', signal.SIGKILL), events)
        self.assertIs(d.records[0]['leader_exited_with_group_alive'], True)
        self.assertIs(d.records[0]['owned_group_absence_observed'], True)
        with self.assertRaises(ValueError): N.validate_cli_records(d.records)


if __name__ == '__main__':
    unittest.main(verbosity=2)
