"""Generated ownership-failure controls; no real process or scope is launched.

The parent supplies the exact source-selected derived bytes. Only unchanged
function AST nodes execute, in fresh namespaces with explicitly simulated native
observations. Generated closure facts never qualify a physical runtime.
"""
import ast
import copy
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace


def _functions(raw, names, namespace):
    tree = ast.parse(raw)
    selected = [node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in selected} != set(names):
        raise AssertionError('Exact named production function bodies required')
    code = ast.Module(body=selected, type_ignores=[])
    env = dict(namespace)
    exec(compile(code, '<source-selected-closure-control>', 'exec'), env)
    return env


def exercise_closure(testcase, derived_common_raw, derived_runner_raw,
                     derived_process_owner_raw, artifact_root, accounting=None):
    """Run one method's small generated fixtures inside the parent's campaign.

    Accounting values are additive. The input byte count includes source AST
    inspection. In-memory publication versions and reads are counted separately
    from physical fixture writes; the caller may conservatively charge both.
    No temporary fixture is deleted by this helper.
    """
    counts = {'closure_source_input_bytes': 0, 'closure_fixture_write_bytes': 0,
              'closure_metadata_write_bytes': 0, 'closure_metadata_read_bytes': 0}

    def add(key, count):
        testcase.assertIs(type(count), int)
        testcase.assertGreaterEqual(count, 0)
        counts[key] += count
        if accounting is not None:
            accounting[key] = accounting.get(key, 0) + count

    for raw in (derived_common_raw, derived_runner_raw, derived_process_owner_raw):
        testcase.assertIs(type(raw), bytes)
        add('closure_source_input_bytes', len(raw))
    common_tree = ast.parse(derived_common_raw)
    constants = {}
    for node in common_tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in {'CONDITIONS', 'PAIR_SECONDS'}:
                constants[node.targets[0].id] = ast.literal_eval(node.value)
    testcase.assertEqual(constants['CONDITIONS'], ('validation_reference',))
    testcase.assertEqual(constants['PAIR_SECONDS']['restricted_validation_reference'], 11280)
    common = _functions(derived_common_raw, {'need', 'encoded', 'pin', 'parse'},
                        {'json': json, 'hashlib': hashlib})
    need, encoded, pin = common['need'], common['encoded'], common['pin']
    root = Path(artifact_root)
    testcase.assertTrue(root.is_absolute() and root.is_dir())
    root = root / 'closure-controls'
    testcase.assertFalse(root.exists())
    root.mkdir(mode=0o700)

    def put(path, document):
        raw = encoded(document)
        testcase.assertFalse(path.exists())
        path.write_bytes(raw)
        add('closure_fixture_write_bytes', len(raw))
        return raw

    def forbidden(*args, **kwargs):
        raise AssertionError('A real or unselected native boundary was reached')

    def stop_namespace(state, owner, trace):
        def expected(folder, **kwargs):
            raw = (Path(folder) / 'process_owner.json').read_bytes()
            add('closure_metadata_read_bytes', len(raw))
            saved = common['parse'](raw)
            testcase.assertEqual(saved, owner)
            trace.append(('expected_generated_owner', str(folder)))
            return copy.deepcopy(owner), pin(raw)

        def group_exists(pid):
            testcase.assertEqual(pid, owner['pid'])
            trace.append(('observe_simulated_group', bool(state['group_exists'])))
            return state['group_exists']

        def inspect_leader(pid, end):
            trace.append(('inspect_simulated_leader', pid, end))
            return copy.deepcopy(state['leader'])

        namespace = {'Path': Path, 'math': math,
                     'time': SimpleNamespace(monotonic=lambda: state['now'], sleep=forbidden),
                     'os': SimpleNamespace(killpg=forbidden),
                     'signal': SimpleNamespace(SIGKILL=9), 'expected': expected,
                     'group_exists': group_exists, 'inspect_leader': inspect_leader}
        return _functions(derived_process_owner_raw, {'stop'}, namespace)

    class FakeProcess:
        def __init__(self, pid, trace):
            self.pid, self.trace, self.returncode = pid, trace, None

        def communicate(self, timeout):
            testcase.assertGreater(timeout, 0)
            self.trace.append(('simulated_communicate', timeout))
            self.returncode = 0
            return b'', b''

    owner = {'pid': 900001, 'grant': {'deadline': 160.0},
             'observed_leader': {'pid': 900001, 'pgid': 900001,
                                 'started': 'generated-birth', 'command': '/generated/no-process'}}
    trace = []
    state = {'now': 10.0, 'group_exists': False,
             'leader': {**owner['observed_leader'], 'state': 'Z'}}
    stop = stop_namespace(state, owner, trace)['stop']
    direct_results = {}

    empty = root / 'no-launch-intent'
    empty.mkdir()
    direct_results['no_launch_intent'] = stop(empty, 160.0)
    testcase.assertEqual(direct_results['no_launch_intent'],
                         {'status': 'never_activated', 'absence_verified': True,
                          'no_group_identity_claim': True})
    testcase.assertEqual(trace, [])

    incomplete = root / 'intent-without-owner'
    incomplete.mkdir()
    put(incomplete / 'process_intent.json', {'generated_intent': True})
    direct_results['intent_without_owner'] = stop(incomplete, 160.0)
    testcase.assertEqual(direct_results['intent_without_owner']['status'], 'unactivated_ownership_incomplete')
    testcase.assertIs(direct_results['intent_without_owner']['absence_verified'], False)
    testcase.assertIs(direct_results['intent_without_owner']['no_group_identity_claim'], True)
    testcase.assertIs(direct_results['intent_without_owner']['activation_observed'], False)
    testcase.assertEqual(trace, [])

    gate = root / 'gate-without-owner'
    gate.mkdir()
    put(gate / 'process_gate.json', {'generated_gate': True})
    with testcase.assertRaisesRegex(ValueError, 'Activation without ownership'):
        stop(gate, 160.0)
    testcase.assertEqual(trace, [])

    launched = root / 'simulated-owned-group'
    launched.mkdir()
    put(launched / 'process_owner.json', owner)
    fake = FakeProcess(owner['pid'], trace)
    direct_results['simulated_owned_group_absent'] = stop(
        launched, 999.0, fake, reap_owned_children=lambda end: trace.append(('simulated_reap', end)))
    closed = direct_results['simulated_owned_group_absent']
    testcase.assertEqual(closed['cleanup_cutoff'], 160.0)
    testcase.assertIs(closed['absence_verified'], True)
    testcase.assertEqual(closed['status'], 'owned_group_absent')
    testcase.assertEqual(closed['scoped_child_reap_calls'], 1)
    testcase.assertIs(closed['independent_provider_CLI_custody_established'], False)
    testcase.assertEqual(fake.returncode, 0)

    with testcase.assertRaisesRegex(ValueError, 'Only the actual owned Popen handle'):
        stop(launched, 160.0, FakeProcess(owner['pid'] + 1, trace))
    state.update(group_exists=True, now=160.0)
    before = len(trace)
    with testcase.assertRaisesRegex(TimeoutError, 'Original process cleanup deadline'):
        stop(launched, 160.0, FakeProcess(owner['pid'], trace))
    testcase.assertFalse(any(row[0] in {'inspect_simulated_leader', 'simulated_communicate'}
                             for row in trace[before:]))
    state.update(now=10.0, leader={**owner['observed_leader'], 'pid': 900002, 'state': 'R'})
    with testcase.assertRaisesRegex(ValueError, 'Refuse nonmatching process-group leader'):
        stop(launched, 160.0, FakeProcess(owner['pid'], trace))

    def execute_failure(mode):
        folder = root / mode
        folder.mkdir()
        clock = {'origin': 1.0, 'controller_deadline': 11221.0, 'deadline': 11281.0,
                 'outcome': 'restricted_validation_reference', 'clock_identity': 'linux:generated'}
        invocation = {'owner': str(folder), 'output': str(folder / 'unopened-output'),
                      'source': pin(b'generated selected owner source'), 'clock': copy.deepcopy(clock),
                      'transport_cost_allocation': {'generated_conservative_allocation': True}}
        invocation_pin = pin(encoded(invocation))
        runtime = {'deployment': {'generated_unqualified': True}}
        log, documents = [], {}
        state = {'now': 10.0, 'group_exists': False,
                 'leader': {**owner['observed_leader'], 'state': 'Z'}}
        selected_owner = copy.deepcopy(owner)
        selected_owner['grant']['deadline'] = clock['deadline']
        process_env = stop_namespace(state, selected_owner, log)
        real_stop = process_env['stop']
        launches = []
        pump_calls = []
        stop_results = []
        fake = FakeProcess(selected_owner['pid'], log)

        class Writer:
            def __init__(self, initial_bytes):
                testcase.assertEqual(initial_bytes, invocation_pin['bytes'])
                self.used = initial_bytes

            def publish(self, path, value, **kwargs):
                raw = encoded(value)
                add('closure_metadata_write_bytes', len(raw))
                documents[Path(path).name] = raw
                log.append(('publish', Path(path).name))
                self.used += len(raw)
                return pin(raw)

        class Custody:
            children = {}

            def __init__(self, engine, deadline):
                testcase.assertEqual(deadline, clock['deadline'])

            def close(self, deadline):
                testcase.assertEqual(deadline, clock['deadline'])
                log.append(('simulated_cli_close', deadline))
                return {'all_acknowledged_cli_absent': True, 'records': []}

        class Scopes:
            def __init__(self, deployment, selected_clock, selected_pin, source, writer, selected_folder):
                testcase.assertEqual(deployment, runtime['deployment'])
                testcase.assertEqual(selected_clock, clock)
                testcase.assertEqual(selected_pin, invocation_pin)
                testcase.assertEqual(selected_folder, folder)
                log.append(('scope_construct', mode))
                if mode == 'predispatch_failure':
                    raise ValueError('generated predispatch scope refusal')

            def close(self, closure_pin):
                log.append(('simulated_scope_close', closure_pin))
                return {'all_scopes_empty': True, 'complete': True, 'within_limits': True,
                        'counters_complete': True, 'scopes': {}}

            def remove(self, provider_pin):
                log.append(('simulated_scope_remove', provider_pin))
                return {'complete': True, 'all_scopes_removed': True, 'scopes': {}}

            def emergency_close(self, custody):
                log.append(('simulated_emergency_close', clock['deadline']))
                return {'all_scopes_empty': False, 'gradeable_closure': False,
                        'generated_unknown_scope_observation': True}

        class Endpoint:
            def fileno(self):
                return 17

            def close(self):
                log.append(('simulated_channel_close',))

        def launch(argv, process_folder, grant, controller, channel_fd):
            testcase.assertEqual(grant, {**clock, 'invocation_pin': invocation_pin})
            testcase.assertEqual(channel_fd, 17)
            testcase.assertEqual(process_folder, folder / 'process')
            launches.append(copy.deepcopy(argv))
            log.append(('simulated_launch', mode))
            process_folder.mkdir()
            put(process_folder / 'process_intent.json', {'generated_intent': True})
            if mode != 'incomplete_launch_intent':
                put(process_folder / 'process_owner.json', selected_owner)
                put(process_folder / 'process_gate.json', {'generated_gate': True})
            return fake

        def expected(process_folder, **kwargs):
            if mode == 'incomplete_launch_intent':
                raise ValueError('generated launch ownership not durably established')
            return process_env['expected'](process_folder, **kwargs)

        def owned_stop(process_folder, end, actual_process, **kwargs):
            log.append(('actual_stop_body_enter', end))
            value = real_stop(process_folder, end, actual_process, **kwargs)
            stop_results.append(copy.deepcopy(value))
            log.append(('actual_stop_body_return', value['absence_verified']))
            return value

        def pump(*args):
            pump_calls.append(True)
            log.append(('simulated_pump_timeout', mode))
            if mode == 'launched_cleanup_unknown':
                state.update(now=clock['deadline'], group_exists=True)
            raise TimeoutError('generated controller deadline failure')

        def provider_closed(*args):
            log.append(('simulated_provider_closure', mode))
            if mode in {'incomplete_launch_intent', 'launched_cleanup_unknown'}:
                raise ValueError('generated provider closure remains unknown')
            return {'generated_unqualified_provider_closure': True}

        def body(path):
            testcase.assertEqual(Path(path).name, 'controller.py')
            raw = b'generated controller source boundary; never executed'
            add('closure_metadata_read_bytes', len(raw))
            return raw

        journal = SimpleNamespace(done=None, aggregate_final={}, bytes=0, sequence=0,
                                  ownership={}, closed=set(), prepared={})
        namespace = {'Path': Path, 'OwnerWriter': Writer,
            'make_invocation': lambda *args: (invocation, invocation_pin, SimpleNamespace(), runtime),
            'fcntl': SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=lambda *args: None),
            'signal': SimpleNamespace(SIGINT=2, SIGTERM=15, SIGHUP=1, SIG_IGN=object(),
                                      signal=lambda *args: 'generated prior signal handler'),
            'socket': SimpleNamespace(socketpair=lambda: (Endpoint(), Endpoint())),
            'CliCustody': Custody, 'ScopeManager': Scopes,
            'ParentJournal': lambda *args: journal, 'engine_for': lambda *_: object(),
            'body': body, 'pin': pin, 'CONTROLLER': '/generated/controller.py',
            'HERE': Path('/generated/source'), 'sys': SimpleNamespace(executable='/generated/python'),
            'process_owner': SimpleNamespace(launch=launch, expected=expected, stop=owned_stop),
            'pump': pump, 'reap_controller': lambda handles: log.append(('simulated_child_reap',)),
            'need': need, 'recover_phases': lambda *args: [],
            'provider_closed_document': provider_closed, 'CONDITIONS': ('validation_reference',),
            'JOURNAL_CAP': 32 * 1024**2, 'os': SimpleNamespace(close=forbidden)}
        execute = _functions(derived_runner_raw, {'execute'}, namespace)['execute']
        with testcase.assertRaisesRegex(ValueError, 'Preserved terminal owned-episode failure'):
            execute(Path('/generated/protocol'), 'a' * 64, Path(invocation['output']), folder, 1, 1)
        testcase.assertEqual(invocation['clock'], clock)
        testcase.assertEqual((folder / 'OWNER.lock').stat().st_size, 0)
        testcase.assertNotIn('CUSTODY.json', documents)
        testcase.assertNotIn('FREEZE.json', documents)

        def document(name):
            raw = documents[name]
            add('closure_metadata_read_bytes', len(raw))
            return common['parse'](raw)

        result, closure = document('RESULT.json'), document('CONTROLLER_CLOSED.json')
        testcase.assertEqual(result['status'], 'failed')
        testcase.assertIsNone(result['scientific_success'])
        testcase.assertIsNone(result['pair_closed_pin'])
        testcase.assertIs(result['AI_performance_verified'], False)
        testcase.assertIs(result['actual_linux_docker_runtime_qualification_inherited'], False)
        testcase.assertIs(result['error']['automatic_retry'], False)
        testcase.assertIs(closure['unacknowledged_cli_host_absence_verified'], False)
        testcase.assertIs(closure['outer_parent_death_watchdog_qualified'], False)
        stop_position = next(i for i, item in enumerate(log) if item[0] == 'actual_stop_body_enter')
        cli_position = next(i for i, item in enumerate(log) if item[0] == 'simulated_cli_close')
        published_position = log.index(('publish', 'CONTROLLER_CLOSED.json'))
        testcase.assertLess(stop_position, cli_position)
        testcase.assertLess(cli_position, published_position)
        if mode == 'predispatch_failure':
            testcase.assertEqual(launches, [])
            testcase.assertEqual(pump_calls, [])
            testcase.assertEqual(stop_results[0]['status'], 'never_activated')
            testcase.assertIs(closure['future_controller_and_acknowledged_cli_release_closed'], True)
            testcase.assertEqual(result['error']['type'], 'ValueError')
            testcase.assertNotIn('AGGREGATE_CLOSED.json', documents)
            testcase.assertNotIn('AGGREGATE_EMERGENCY.json', documents)
        elif mode == 'incomplete_launch_intent':
            testcase.assertEqual(len(launches), 1)
            testcase.assertEqual(pump_calls, [])
            testcase.assertEqual(stop_results[0]['status'], 'unactivated_ownership_incomplete')
            testcase.assertIs(closure['future_controller_and_acknowledged_cli_release_closed'], False)
            testcase.assertNotIn('AGGREGATE_CLOSED.json', documents)
            testcase.assertIs(document('AGGREGATE_EMERGENCY.json')['gradeable_closure'], False)
        elif mode == 'launched_timeout_closed':
            testcase.assertEqual(len(launches), 1)
            testcase.assertEqual(len(pump_calls), 1)
            testcase.assertEqual(stop_results[0]['status'], 'owned_group_absent')
            testcase.assertIs(closure['future_controller_and_acknowledged_cli_release_closed'], True)
            testcase.assertEqual(result['error']['type'], 'TimeoutError')
            testcase.assertIsNone(result['recovery_error'])
            testcase.assertIn('AGGREGATE_CLOSED.json', documents)
            testcase.assertIn('AGGREGATE_REMOVED.json', documents)
            testcase.assertNotIn('AGGREGATE_EMERGENCY.json', documents)
        else:
            testcase.assertEqual(len(launches), 1)
            testcase.assertEqual(len(pump_calls), 1)
            testcase.assertEqual(stop_results, [])
            testcase.assertEqual(closure['controller_group'], {'absence_verified': False, 'error': 'TimeoutError'})
            testcase.assertIs(closure['future_controller_and_acknowledged_cli_release_closed'], False)
            testcase.assertNotIn('AGGREGATE_CLOSED.json', documents)
            testcase.assertIs(document('AGGREGATE_EMERGENCY.json')['gradeable_closure'], False)
        return {'case': mode, 'launches_simulated': len(launches), 'pump_calls': len(pump_calls),
                'result_status': result['status'], 'controller_group': closure['controller_group'],
                'future_release_closed': closure['future_controller_and_acknowledged_cli_release_closed'],
                'error_type': result['error']['type'],
                'captured_documents': sorted(documents), 'scientific_success': None}

    results = [execute_failure(mode) for mode in
               ('predispatch_failure', 'incomplete_launch_intent',
                'launched_timeout_closed', 'launched_cleanup_unknown')]
    total = sum(counts.values())
    testcase.assertLessEqual(total, 262144, 'Finite closure-control source/generated-work allowance')
    return {'schema': 'smc_validation_generated_closure_control_v1',
            'actual_function_bodies': ['runner.execute', 'process_owner.stop'],
            'source_namespace_mutation': False, 'production_globals_mutated': False,
            'direct_stop_cases': 7, 'runner_failure_cases': results,
            'never_launched_claim_scope': 'Only missing intent, gate and owner in actual generated fixture directory',
            'actual_process_signal_socket_cgroup_or_Docker_execution': False,
            'physical_runtime_qualified': False, 'numerical_freeze_or_scoring_performed': False,
            'native_and_provider_observations': 'Explicit doubles; generated facts are not real closure proofs',
            'accounting': counts, 'generated_work_upper_bytes': 262144}
