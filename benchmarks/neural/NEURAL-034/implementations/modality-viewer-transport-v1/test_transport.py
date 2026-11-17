"""Mandatory macOS generated transport integration, not authentic/model runs."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import generated_fixtures as F
M, C, T = F.M, F.C, F.T


class RestrictedModalityTransport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != 'darwin' or not F.FRAMEWORK.is_file() or not Path('/usr/bin/sandbox-exec').is_file():
            raise RuntimeError('Actual macOS framework interpreter and sandbox-exec required; no silent skip')
        cls.root = Path(tempfile.mkdtemp(prefix='neural034-modality-host-', dir=os.environ.get('NEURAL034_CONTROL_TMP'))).resolve()
        cls.guard = F.guarded_writes(cls.root); cls.guard.__enter__()
        cls.addClassCleanup(cls.guard.__exit__, None, None, None)
        cls.deps = F.generated(); cls.deps.__enter__()
        cls.addClassCleanup(cls.deps.__exit__, None, None, None)
        cls.source = F.pins()
        cls.client = cls.root / 'fixed-client.py'; cls.client.write_text(F.CLIENT)
        cls.packets = [F.Packet(fold, 'combined_calcium_behavior_v1') for fold in range(7)]
        cls.sessions, cls.results = {}, {}
        cls.counter = 0
        for condition in C.CONDITIONS:
            cls.sessions[condition], cls.results[condition] = [], []
            for fold in range(7):
                packet = F.Packet(fold, condition)
                output = cls.root / f'{condition}-{fold}'
                result = M.run_fold(packet, output, cls.client, condition=condition,
                                    python=F.FRAMEWORK, sandbox='macos', limits=F.limits())
                if result['status'] != 'complete_unscored':
                    raise AssertionError(f'Generated complete session failed: {result}')
                if packet.arrays.excluded.intersection(packet.arrays.accesses):
                    raise AssertionError('Excluded modality accessed')
                cls.sessions[condition].append(output); cls.results[condition].append(result)
        cls.collected = M.collect_matched(cls.packets, cls.sessions, cls.root / 'matched')

    @classmethod
    def tearDownClass(cls):
        if F.pins() != cls.source:
            raise AssertionError('Source changed during generated controls')
        print(json.dumps({'fixture_root': str(cls.root), 'known_fixture_bytes_written': F.WRITTEN,
                          'cap_bytes': F.CAP, 'generated_render_calls_including_audits': F.RENDER_CALLS,
                          'complete_primary_episodes': 21, 'authentic_input_reads': 0,
                          'authentic_renders': 0, 'model_calls': 0, 'scientific_grader_calls': 0,
                          'scope': 'Actual macOS participant transport with invented packet arrays and small PNGs; no authentic signal raster.'}))

    def run_client(self, body, *, condition='behavior_only_v1', limits=None):
        type(self).counter += 1
        index = type(self).counter
        client = self.root / f'extra-client-{index}.py'; client.write_text(body)
        output = self.root / f'extra-session-{index}'
        result = M.run_fold(F.Packet(0, condition), output, client, condition=condition,
                            python=F.FRAMEWORK, sandbox='macos', limits=limits or F.limits())
        return output, result

    def failed_clean(self, output, result):
        self.assertEqual(result['status'], 'failed')
        self.assertTrue(result['workspace_destroyed'])
        self.assertTrue(result['code_directory_destroyed'])
        self.assertIn(result['process_group_cleanup'], ('absent', 'signalled'))
        self.assertTrue((output / 'failure.json').is_file())
        self.assertFalse((output / 'viewer' / 'history.json').exists())
        with self.assertRaises((ValueError, OSError)):
            M.audit_transport(output, F.Packet(0, result['condition']), result['condition'])

    def test_complete_three_original_submissions_and_fresh_episodes(self):
        episodes, workspaces, code_paths, clients, budgets = set(), set(), set(), set(), set()
        for condition, paths in self.sessions.items():
            submission = F.decode(self.root / 'matched' / condition / 'probabilities.json')
            self.assertEqual(submission, {'schema_version': 1, 'probabilities': [
                {'fold': fold, 'query_id': query_id, 'probability': 0.5}
                for fold in range(7) for query_id in C.IDS[fold]]})
            for path, result in zip(paths, self.results[condition]):
                boundary = F.decode(path / 'BOUNDARY.json')
                self.assertEqual(boundary['condition'], condition)
                self.assertEqual((result['actions'], result['images']), (161, 140))
                self.assertEqual(result['process_group_cleanup'], 'absent')
                self.assertTrue(result['workspace_destroyed'])
                self.assertTrue(result['code_directory_destroyed'])
                self.assertFalse(Path(boundary['code_path']).parent.exists())
                self.assertFalse(Path(boundary['workspace']).exists())
                self.assertFalse(boundary['provider_context_qualified'])
                self.assertFalse(boundary['provider_image_capacity_qualified'])
                episodes.add(boundary['episode_id']); workspaces.add(boundary['workspace'])
                code_paths.add(boundary['code_path'])
                clients.add(boundary['client_sha256']); budgets.add(T.encode(boundary['limits']))
        self.assertEqual((len(episodes), len(workspaces), len(code_paths), len(clients), len(budgets)), (21, 21, 21, 1, 1))

    def test_new_condition_projection_and_guarded_audit(self):
        for condition in ('calcium_only_v1', 'behavior_only_v1'):
            packet = F.Packet(0, condition)
            receipt = M.audit_transport(self.sessions[condition][0], packet, condition)
            self.assertEqual(set(receipt['answers']), set(C.IDS[0]))
            self.assertTrue(packet.arrays.excluded.isdisjoint(packet.arrays.accesses))
        with self.assertRaises(ValueError):
            M.audit_transport(self.sessions['behavior_only_v1'][0], F.Packet(0, 'calcium_only_v1'), 'calcium_only_v1')

    def test_matched_collection_refuses_condition_client_budget_and_episode_changes(self):
        path = self.sessions['behavior_only_v1'][0] / 'BOUNDARY.json'
        for key, value in (('condition', 'calcium_only_v1'), ('client_sha256', '0' * 64),
                           ('source', {}), ('python', '/usr/bin/python3'),
                           ('episode_id', F.decode(self.sessions['calcium_only_v1'][0] / 'BOUNDARY.json')['episode_id']),
                           ('workspace', F.decode(self.sessions['calcium_only_v1'][0] / 'BOUNDARY.json')['workspace']),
                           ('limits', dict(C.asdict(F.limits()), max_images=141))):
            changed = F.decode(path); changed[key] = value
            with self.subTest(key=key), F.replaced(path, T.encode(changed)), self.assertRaises(ValueError):
                M.collect_matched(self.packets, self.sessions, self.root / 'must-not-collect')
        self.assertFalse((self.root / 'must-not-collect' / 'MATCHED_COMPLETE.json').exists())

    def test_new_boundary_rejects_old_transport_and_operator_history(self):
        path = self.sessions['calcium_only_v1'][0] / 'BOUNDARY.json'
        for schema in ('neural034-viewer-transport/v1', 'neural034-modality-viewer-history/v1'):
            changed = F.decode(path); changed['schema'] = schema
            with F.replaced(path, T.encode(changed)), self.assertRaises(ValueError):
                M.audit_transport(path.parent, F.Packet(0, 'calcium_only_v1'), 'calcium_only_v1')

    def test_query_label_injection_in_rehashed_wire_fails_projection_audit(self):
        root = self.sessions['behavior_only_v1'][0] / 'transport'
        raw, rows = (root / 'wire.bin').read_bytes(), [T.decode(line) for line in (root / 'journal.jsonl').read_bytes().splitlines()]
        out, new_rows, previous, changed = bytearray(), [], '0' * 64, False
        for row in rows:
            body = raw[row['offset']:row['offset'] + row['bytes']]
            if row['direction'] == 'out' and not changed:
                header, image = T.unpack(body)
                if header.get('kind') == 'view' and header.get('role') == 'query':
                    header['context_label'] = 1
                    body = T.wire(header, image); changed = True
            altered = dict(row, offset=len(out), bytes=len(body), sha256=T.digest(body), previous=previous)
            encoded = T.encode(altered); new_rows.append(encoded); previous = T.digest(encoded); out.extend(body)
        self.assertTrue(changed)
        with F.replaced(root / 'wire.bin', bytes(out)), F.replaced(root / 'journal.jsonl', b''.join(new_rows)), self.assertRaises(ValueError):
            M.audit_transport(root.parent, F.Packet(0, 'behavior_only_v1'), 'behavior_only_v1')

    def test_sandbox_denies_cross_condition_files_writes_network_children_and_parent_state(self):
        secret = self.root / 'withheld-other-condition.txt'; secret.write_text('GENERATED_PRIVATE_SENTINEL')
        target = self.root / 'outside-write.txt'
        code = F.CLIENT_FUNCTIONS + '\n' + f'''
import errno, os, socket, subprocess, tempfile
from pathlib import Path
code = Path(__file__).resolve()
assert code == Path(sys.argv[0]).resolve()
assert code.name == 'client.py' and code.parent.name.startswith('neural034-modality-code-')
assert code.parent.parent == Path('/tmp').resolve()
assert Path.cwd().parent == Path('/tmp').resolve()
assert {str(self.root)!r} not in str(code)
assert not os.listdir('.')
assert 'NEURAL034_PARENT_SENTINEL' not in os.environ
def denied(call):
    try: call()
    except (OSError, PermissionError): return
    raise AssertionError('Prohibited operation succeeded')
denied(lambda: open({str(secret)!r}, 'rb').read())
denied(lambda: open({str(target)!r}, 'wb').write(b'x'))
denied(lambda: open('carry-over.txt', 'wb').write(b'x'))
try:
    socket.create_connection(('127.0.0.1', 9), timeout=.1)
except OSError as exc:
    assert exc.errno in (errno.EACCES, errno.EPERM), 'Network refusal must be a sandbox permission failure'
else:
    raise AssertionError('Network connection was permitted')
denied(lambda: subprocess.Popen(['/usr/bin/true']))
main()
'''
        with patch.dict(os.environ, {'NEURAL034_PARENT_SENTINEL': 'SHOULD_NOT_ENTER_CLIENT'}):
            output, result = self.run_client(code)
        self.assertEqual(result['status'], 'complete_unscored')
        self.assertFalse(target.exists())
        self.assertTrue(result['workspace_destroyed'])

    def test_deadline_action_image_and_output_budget_fail_closed(self):
        sleep = F.CLIENT_FUNCTIONS + '\nimport time\nreceive()\ntime.sleep(5)\n'
        output, result = self.run_client(sleep, limits=F.limits(wall_seconds=.2))
        self.failed_clean(output, result)
        self.assertLess(result['wall_seconds'], 3)
        for limits, count in ((F.limits(max_actions=200), 141),
                              (F.limits(max_images=161), 162),
                              (F.limits(max_output_bytes=T.PNG_MAX + T.HEADER_MAX + T.PREFIX.size + T.RESERVE), 1)):
            code = F.CLIENT_FUNCTIONS + f"\nreceive()\nfor i in range({count}):\n    send({{'action':'inspect'}})\n    receive()\n"
            if count == 162:
                code = F.CLIENT_FUNCTIONS + "\nreceive()\nsend({'action':'inspect'})\nview, _ = receive()\nsend({'action':'respond','query_id':view['query_id'],'probability':0.5})\nreceive()\nfor i in range(160):\n    send({'action':'inspect'})\n    receive()\n"
            output, result = self.run_client(code, limits=limits)
            self.failed_clean(output, result)
            if count == 162:
                self.assertEqual(result['images'], 160)
                self.assertIn('action budget', result['reason']['message'])

    def test_last_answer_without_finish_and_trailing_output_do_not_complete(self):
        incomplete = F.CLIENT.replace("send({'action': 'finish'})", "raise RuntimeError('after last answer, before finish')")
        trailing = F.CLIENT_FUNCTIONS + "\nmain()\nsys.stdout.buffer.write(b'trailing')\nsys.stdout.buffer.flush()\n"
        for code in (incomplete, trailing):
            output, result = self.run_client(code)
            self.failed_clean(output, result)


if __name__ == '__main__':
    unittest.main()
