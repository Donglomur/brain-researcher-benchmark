"""One generated execute-boundary failure control; no native lifecycle calls."""
import copy
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runner
from common import encoded, pin


class EmergencyExecuteControl(unittest.TestCase):
    def test_failed_closure_publication_still_attempts_non_gradeable_emergency_cleanup(self):
        trace, documents = [], {}
        source = pin(b'generated owner source')
        original_clock = {'origin': 1.0, 'controller_deadline': 22501.0,
            'deadline': 22561.0, 'outcome': 'improvement', 'clock_identity': 'linux:generated'}
        with tempfile.TemporaryDirectory(prefix='smc-generated-execute-') as temp:
            folder = Path(temp).resolve()
            invocation = {'owner': str(folder), 'output': '/generated/unopened-output',
                'source': source, 'clock': copy.deepcopy(original_clock)}
            invocation_pin = pin(encoded(invocation))
            runtime = {'deployment': {'generated_unqualified': True}}
            process = object()
            owner = {'pid': 1234, 'pgid': 1234, 'token': 'generated-token'}

            class Writer:
                used = 0

                def publish(self, path, value, **_):
                    name = Path(path).name
                    trace.append(('publish', name))
                    if name == 'CONTROLLER_CLOSED.json':
                        raise OSError('injected controller-closure publication failure')
                    documents[name] = copy.deepcopy(value)
                    return pin(encoded(value))

            writer = Writer()
            custody = Mock()
            custody.children = {}

            def cli_close(deadline):
                self.assertEqual(deadline, original_clock['deadline'])
                trace.append(('cli_close', deadline))
                return {'all_acknowledged_cli_absent': True, 'records': []}

            custody.close.side_effect = cli_close
            scopes = Mock()

            def emergency(actual_custody):
                self.assertIs(actual_custody, custody)
                self.assertEqual(invocation['clock'], original_clock)
                trace.append(('emergency_close', original_clock['deadline']))
                return {'all_scopes_empty': True, 'gradeable_closure': False}

            scopes.emergency_close.side_effect = emergency
            streams = [Mock(name='generated_parent_channel'), Mock(name='generated_child_channel')]
            streams[1].fileno.return_value = 17

            def stop(path, deadline, actual_process, **_):
                self.assertEqual(path, folder / 'process')
                self.assertEqual(deadline, original_clock['deadline'])
                self.assertIs(actual_process, process)
                trace.append(('group_stop', deadline))
                return {'absence_verified': True, 'pgid': owner['pgid']}

            with ExitStack() as stack:
                use = stack.enter_context
                use(patch.object(runner, 'make_invocation',
                    return_value=(invocation, invocation_pin, SimpleNamespace(), runtime)))
                use(patch.object(runner, 'OwnerWriter', return_value=writer))
                scope_type = use(patch.object(runner, 'ScopeManager', return_value=scopes))
                use(patch.object(runner, 'CliCustody', return_value=custody))
                use(patch.object(runner, 'ParentJournal',
                    return_value=SimpleNamespace(done=None, bytes=0, sequence=0)))
                use(patch.object(runner, 'engine_for', return_value=object()))
                use(patch.object(runner, 'body', return_value=b'generated controller source'))
                use(patch.object(runner.socket, 'socketpair', return_value=tuple(streams)))
                use(patch.object(runner.fcntl, 'flock', return_value=None))
                use(patch.object(runner.signal, 'signal', return_value=runner.signal.SIG_DFL))
                launch = use(patch.object(runner.process_owner, 'launch', return_value=process))
                use(patch.object(runner.process_owner, 'expected', return_value=(owner, {})))
                stop_mock = use(patch.object(runner.process_owner, 'stop', side_effect=stop))
                use(patch.object(runner, 'pump',
                    side_effect=ValueError('generated controller failure')))
                recover = use(patch.object(runner, 'recover_phases'))
                provider_closed = use(patch.object(runner, 'provider_closed_document'))
                grade = use(patch.object(runner, 'grade'))
                with self.assertRaisesRegex(OSError, 'injected controller-closure publication failure'):
                    runner.execute(Path('/generated/protocol'), 'a' * 64,
                                   Path(invocation['output']), folder, 131072, 131072)
                scope_type.assert_called_once_with(runtime['deployment'], original_clock,
                    invocation_pin, source, writer, folder)
                launch.assert_called_once()
                self.assertEqual(launch.call_args.args[2], {**original_clock, 'invocation_pin': invocation_pin})
                stop_mock.assert_called_once()
                custody.close.assert_called_once_with(original_clock['deadline'])
                scopes.emergency_close.assert_called_once_with(custody)
                scopes.close.assert_not_called()
                scopes.remove.assert_not_called()
                recover.assert_not_called()
                provider_closed.assert_not_called()
                grade.assert_not_called()
            self.assertEqual(invocation['clock'], original_clock)
            positions = {name: next(i for i, row in enumerate(trace) if row[0] == name)
                         for name in ('group_stop', 'cli_close', 'emergency_close')}
            self.assertLess(positions['group_stop'], positions['cli_close'])
            self.assertLess(positions['cli_close'], positions['emergency_close'])
            failed_publish = trace.index(('publish', 'CONTROLLER_CLOSED.json'))
            self.assertLess(positions['cli_close'], failed_publish)
            self.assertLess(failed_publish, positions['emergency_close'])
            failure = documents['TERMINAL_FAILURE.json']
            self.assertEqual(failure['original_error']['type'], 'ValueError')
            self.assertEqual(failure['terminal_error'], 'OSError')
            self.assertIsNone(failure['controller_closure_pin'])
            self.assertIsNone(failure['scientific_success'])
            self.assertIs(failure['automatic_retry'], False)
            self.assertIs(documents['AGGREGATE_EMERGENCY.json']['gradeable_closure'], False)
            self.assertEqual(documents['AGGREGATE_EMERGENCY.json']['clock'], original_clock)
            self.assertNotIn('RESULT.json', documents)
            self.assertEqual([p.name for p in folder.iterdir()], ['OWNER.lock'])
            self.assertEqual((folder / 'OWNER.lock').stat().st_size, 0)


if __name__ == '__main__':
    names = ('test_execute_emergency.py', 'runner.py')
    before = {name: pin((HERE / name).read_bytes()) for name in names}
    print(json.dumps({'schema': 'smc_execute_emergency_generated_source_v1', 'source_before': before}), flush=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EmergencyExecuteControl)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    after = {name: pin((HERE / name).read_bytes()) for name in names}
    print(json.dumps({'schema': 'smc_execute_emergency_generated_result_v1',
        'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'skips': len(result.skipped), 'source_unchanged': before == after, 'source_after': after,
        'filesystem_fixture': 'one temporary directory and zero-byte OWNER.lock, removed',
        'actual_process_socket_signal_cgroup_or_scientific_execution': False}), flush=True)
    raise SystemExit(0 if result.wasSuccessful() and before == after else 1)
