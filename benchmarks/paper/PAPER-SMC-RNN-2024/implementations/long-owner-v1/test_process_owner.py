"""Generated process-custody controls only: no Docker, candidate or neural data."""
from pathlib import Path
import copy
import hashlib
import json
import os
import socket
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import process_owner as owner
import trusted_controller as trusted


def grant(fixture=False):
    origin = time.monotonic()
    span, reserve = (8, 2) if fixture else (22560, 60)
    return {'outcome': 'improvement', 'origin': origin, 'deadline': origin + span,
            'controller_deadline': origin + span - reserve, 'clock_identity': owner.clock_identity(),
            'invocation_pin': {'bytes': 2, 'sha256': hashlib.sha256(b'{}').hexdigest()}}


class ProcessOwnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='smc-owner-generated-')
        # macOS's default temporary path contains /var -> /private/var. The
        # actual operator contract deliberately rejects symlink ancestors.
        self.root = Path(self.tmp.name).resolve()
        self.root.chmod(0o700)
        self.parents = []
        self.sockets = []

    def tearDown(self):
        # Cleanup is limited to this test's returned owned Popen identities.
        for proc, folder in reversed(self.parents):
            if proc.poll() is None or owner.group_exists(proc.pid):
                owner.stop(folder, time.monotonic() + 1, proc)
        for sock in self.sockets:
            sock.close()
        self.tmp.cleanup()

    def pair(self):
        left, right = socket.socketpair()
        left.settimeout(2)
        self.sockets.extend((left, right))
        return left, right

    def start(self, behavior='complete'):
        folder = self.root / ('owner-' + str(len(self.parents)))
        folder.mkdir(mode=0o700)
        left, right = self.pair()
        argv = [sys.executable, '-I', '-B', str(HERE / 'trusted_fixture.py'),
                '--channel-fd', str(right.fileno()), '--behavior', behavior]
        before = grant(True)
        proc = owner._launch_fixture(argv, folder, before, trusted.fixture_descriptor(), right.fileno())
        self.parents.append((proc, folder))
        right.close()
        return proc, folder, left, before

    def wait_completion(self, folder):
        end = time.monotonic() + 2
        while not (folder / 'process_completion.json').exists():
            if time.monotonic() >= end:
                self.fail('Expected fixed fixture completion')
            time.sleep(.01)
        return owner.read(folder / 'process_completion.json')

    def test_exact_production_profiles_and_recovery_reserve(self):
        for outcome, span in owner.PAIR_SECONDS.items():
            value = grant()
            value.update(outcome=outcome, deadline=value['origin'] + span,
                         controller_deadline=value['origin'] + span - 60)
            self.assertEqual(owner.validate_grant(value), value)
            wrong = copy.deepcopy(value)
            wrong['controller_deadline'] += 1
            with self.assertRaises(ValueError):
                owner.validate_grant(wrong)

    def test_changed_boot_cannot_reuse_retained_deadline(self):
        value = grant()
        value['clock_identity'] += '-other-boot'
        with self.assertRaisesRegex(ValueError, 'same boot'):
            owner.validate_grant(value)

    def test_expired_grant_is_not_renewed(self):
        value = grant(True)
        value['origin'] -= 9
        value['deadline'] -= 9
        value['controller_deadline'] -= 9
        with self.assertRaises(TimeoutError):
            owner.validate_grant(value, fixture=True)
        self.assertEqual(owner.validate_grant(value, fixture=True, require_remaining=False), value)

    def test_malformed_clocks_pins_and_extended_budget_refused(self):
        for field, replacement in [('origin', float('nan')), ('deadline', True),
                                   ('outcome', 'custom'), ('invocation_pin', {'bytes': 0, 'sha256': '0' * 64})]:
            value = grant()
            value[field] = replacement
            with self.assertRaises(ValueError):
                owner.validate_grant(value)
        value = grant()
        value['deadline'] += 1
        value['controller_deadline'] += 1
        with self.assertRaises(ValueError):
            owner.validate_grant(value)

    def test_atomic_records_never_replace_prior_evidence(self):
        file = self.root / 'record.json'
        owner.atomic(file, {'value': 1})
        with self.assertRaises(FileExistsError):
            owner.atomic(file, {'value': 2})
        self.assertEqual(owner.read(file), {'value': 1})

    def test_duplicate_and_linked_journal_refused(self):
        file = self.root / 'bad.json'
        file.write_text('{"a": 1, "a": 2}')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            owner.read(file)
        link = self.root / 'alias.json'
        link.symlink_to(file)
        with self.assertRaises(ValueError):
            owner.read(link)

    def test_public_launch_cannot_select_fixture_or_arbitrary_controller(self):
        left, right = self.pair()
        value = trusted.fixture_descriptor()
        argv = [sys.executable, '-I', '-B', str(HERE / 'trusted_fixture.py'),
                '--channel-fd', str(right.fileno()), '--behavior', 'complete']
        with self.assertRaisesRegex(ValueError, 'fixed task controller'):
            owner.launch(argv, self.root, grant(), value, right.fileno())
        bad = copy.deepcopy(value)
        bad['path'] = trusted.PREFIX + '../candidate.py'
        with self.assertRaises(ValueError):
            trusted.validate_controller(bad, argv, fixture=True)

    def test_channel_fd_is_bound_once_and_is_socket(self):
        left, right = self.pair()
        with self.assertRaises(ValueError):
            owner._channel(['--channel-fd', str(right.fileno()), '--channel-fd', str(right.fileno())], right.fileno())
        with self.assertRaises(ValueError):
            owner._channel(['--channel-fd', str(right.fileno() + 1)], right.fileno())
        with (self.root / 'ordinary').open('wb') as stream:
            with self.assertRaisesRegex(ValueError, 'socket'):
                owner._channel(['--channel-fd', str(stream.fileno())], stream.fileno())

    def test_launch_fsynced_owner_before_fixed_child_and_channel_transfer(self):
        proc, folder, channel, clock = self.start()
        message = channel.recv(128)
        self.assertTrue(message.startswith(b'fixed-trusted-fixture:'))
        recorded, args = owner.expected(folder)
        completed = self.wait_completion(folder)
        self.assertEqual(recorded['grant'], clock)
        self.assertEqual(recorded['pid'], proc.pid)
        self.assertTrue(recorded['pid_recorded_before_activation'])
        self.assertEqual(owner.read(folder / 'process_gate.json'), {'activate': True, 'token': recorded['token']})
        self.assertEqual(completed['returncode'], 0)
        self.assertEqual(int(message.split(b':')[1]), completed['child_pid'])
        self.assertEqual(owner.read(folder / 'process_child.json'), {'token': recorded['token'],
                'child_pid': completed['child_pid'], 'controller_pgid': proc.pid,
                'observed_birth_identity_claimed': False})
        self.assertEqual(completed['controller_deadline'], clock['controller_deadline'])
        self.assertEqual(channel.recv(1), b'')  # Bootstrap did not retain the endpoint.
        self.assertIsNone(proc.poll())  # Leader waits for exact-owner cleanup.
        result = owner.stop(folder, clock['deadline'] + 100, proc)
        self.assertEqual(result['cleanup_cutoff'], clock['deadline'])
        self.assertTrue(result['absence_verified'])
        self.assertFalse(result['independent_provider_CLI_custody_established'])

    def test_owned_group_interrupt_closes_fixture_channel(self):
        proc, folder, channel, clock = self.start('wait')
        self.assertTrue(channel.recv(128).startswith(b'fixed-trusted-fixture:'))
        result = owner.stop(folder, time.monotonic() + 1, proc)
        self.assertTrue(result['absence_verified'])
        self.assertEqual(channel.recv(1), b'')
        self.assertIsNotNone(proc.poll())

    def test_nonmatching_leader_does_not_receive_a_signal(self):
        proc, folder, channel, clock = self.start('wait')
        channel.recv(128)
        observed = owner.read(folder / 'process_owner.json')['observed_leader']
        observed['started'] = 'different birth'
        with mock.patch.object(owner, 'inspect_leader', return_value=observed), \
                mock.patch.object(owner.os, 'killpg') as killer:
            with self.assertRaisesRegex(ValueError, 'nonmatching'):
                owner.stop(folder, time.monotonic() + 1, proc)
            self.assertTrue(all(call.args[1] == 0 for call in killer.call_args_list))
        self.assertIsNone(proc.poll())

    def test_modified_grant_cannot_be_recovered_as_same_invocation(self):
        proc, folder, channel, clock = self.start()
        channel.recv(128)
        self.wait_completion(folder)
        file = folder / 'process_owner.json'
        original = file.read_bytes()
        changed = json.loads(original)
        changed['grant']['invocation_pin']['sha256'] = '1' * 64
        file.chmod(0o600)
        file.write_text(json.dumps(changed))
        try:
            with self.assertRaisesRegex(ValueError, 'Immutable invocation'):
                owner.expected(folder)
        finally:
            file.write_bytes(original)
            file.chmod(0o400)

    def test_bootstrap_alarm_uses_original_absolute_cutoff(self):
        proc, folder, channel, clock = self.start('wait')
        channel.recv(128)
        proc.wait(timeout=7)
        self.assertLess(time.monotonic(), clock['deadline'])
        self.assertLess(proc.returncode, 0)
        self.assertEqual(channel.recv(1), b'')
        end = min(clock['deadline'], time.monotonic() + .5)
        while owner.group_exists(proc.pid) and time.monotonic() < end:
            time.sleep(.01)
        self.assertFalse(owner.group_exists(proc.pid))
        result = owner.stop(folder, clock['deadline'], proc)
        self.assertTrue(result['absence_verified'])

    def test_partial_unactivated_owner_never_certifies_host_absence(self):
        owner.atomic(self.root / 'process_intent.json', {'partial': True})
        with mock.patch.object(owner.os, 'killpg') as killer:
            result = owner.stop(self.root, time.monotonic() + 1)
            killer.assert_not_called()
        self.assertEqual(result['status'], 'unactivated_ownership_incomplete')
        self.assertFalse(result['absence_verified'])

    def test_never_activated_does_not_claim_group_identity(self):
        result = owner.stop(self.root, time.monotonic() + 1)
        self.assertEqual(result, {'status': 'never_activated', 'absence_verified': True,
                                 'no_group_identity_claim': True})

    def test_startup_failure_keeps_popen_identity_unreaped_until_signal(self):
        left, right = self.pair()
        selected_grant = grant(True)
        argv = [sys.executable, '-I', '-B', str(HERE / 'trusted_fixture.py'),
                '--channel-fd', str(right.fileno()), '--behavior', 'complete']
        fake = mock.Mock(pid=424242, returncode=None)
        events = []
        def poll():
            fake.returncode = 0
            events.append('reaped-by-poll')
            return 0
        fake.poll.side_effect = poll
        def communicate(**_):
            events.append('communicate')
            fake.returncode = -9
            return b'', b''
        fake.communicate.side_effect = communicate
        def signal_group(pid, sig):
            self.assertEqual((pid, sig), (fake.pid, owner.signal.SIGKILL))
            self.assertIsNone(fake.returncode)
            events.append('kill-unreaped')
        def ready(_):
            intent = owner.read(self.root / 'process_intent.json')
            owner.atomic(self.root / 'process_ready.json', {'token': intent['token'],
                'pid': fake.pid, 'pgid': fake.pid, 'python_initialized_before_identity_snapshot': True})
        with mock.patch.object(owner.subprocess, 'Popen', return_value=fake), \
                mock.patch.object(owner, 'clock_identity', return_value=selected_grant['clock_identity']), \
                mock.patch.object(owner.time, 'sleep', side_effect=ready), \
                mock.patch.object(owner, 'inspect_leader', return_value=None), \
                mock.patch.object(owner.os, 'killpg', side_effect=signal_group):
            with self.assertRaisesRegex(ValueError, 'Observed exact bootstrap'):
                owner._launch_fixture(argv, self.root, selected_grant, trusted.fixture_descriptor(), right.fileno())
        self.assertEqual(events, ['kill-unreaped', 'communicate'])
        fake.poll.assert_not_called()

    def test_reaped_or_unknown_zombie_identity_does_not_authorize_signal(self):
        proc, folder, channel, clock = self.start('wait')
        channel.recv(128)
        observed = owner.read(folder / 'process_owner.json')['observed_leader']
        observed.update(state='Z', command='<defunct>')
        stale = mock.Mock(pid=proc.pid, returncode=0)
        with mock.patch.object(owner, 'inspect_leader', return_value=observed), \
                mock.patch.object(owner.os, 'killpg') as killer:
            for handle in (None, stale):
                with self.assertRaisesRegex(ValueError, 'nonmatching'):
                    owner.stop(folder, time.monotonic() + 1, handle)
            self.assertTrue(all(call.args[1] == 0 for call in killer.call_args_list))

    def test_scoped_subreaper_runs_after_bootstrap_reap_and_cannot_certify_failure(self):
        (self.root / 'process_owner.json').write_text('{}')
        deadline = time.monotonic() + 5
        observed = {'pid': 424242, 'pgid': 424242, 'started': 'fixed birth',
                    'command': 'fixed trusted bootstrap', 'state': 'S'}
        record = {'pid': 424242, 'grant': {'deadline': deadline}, 'observed_leader': observed}
        proc = mock.Mock(pid=424242, returncode=None)
        events = []
        def communicate(**_):
            events.append('communicate')
            proc.returncode = -9
            return b'', b''
        proc.communicate.side_effect = communicate
        def scoped_reap(cutoff):
            self.assertEqual(cutoff, deadline)
            self.assertIsNotNone(proc.returncode)
            events.append('scoped-reap')
        with mock.patch.object(owner, 'expected', return_value=(record, [])), \
                mock.patch.object(owner, 'inspect_leader', return_value=observed), \
                mock.patch.object(owner, 'group_exists', side_effect=[True, True, False, False]), \
                mock.patch.object(owner.os, 'killpg', side_effect=lambda *_: events.append('kill')), \
                mock.patch.object(owner.time, 'sleep'):
            result = owner.stop(self.root, deadline + 100, proc, reap_owned_children=scoped_reap)
        self.assertEqual(events, ['kill', 'communicate', 'scoped-reap', 'scoped-reap'])
        self.assertTrue(result['absence_verified'])
        self.assertEqual(result['scoped_child_reap_calls'], 2)
        with mock.patch.object(owner, 'expected', return_value=(record, [])), \
                mock.patch.object(owner, 'group_exists', return_value=False):
            with self.assertRaisesRegex(ValueError, 'unverified child'):
                owner.stop(self.root, deadline, proc,
                    reap_owned_children=mock.Mock(side_effect=ValueError('unverified child')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
