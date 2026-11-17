"""Generated/source controls only; no Engine, real inputs or scientific scoring."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import deployment as d
import workflow as w


class Controls(unittest.TestCase):
    def image(self):
        return {'id': d.IMAGE, 'os': 'linux', 'architecture': 'arm64', 'size': 539583315,
                'layers': d.LAYERS.copy(), 'entrypoint': None, 'command': ['python3'],
                'user': '', 'working_directory': '/work'}

    def test_exact_image_selection_and_no_qualification(self):
        value = d.validate_image(self.image())
        self.assertTrue(value['available'])
        for key in ('runtime_qualified', 'package_versions_executed',
                    'numerical_compatibility_executed', 'participant_isolation_executed'):
            self.assertIs(value[key], False)
        for key, replacement in [('id', 'neuro-authoring-science:20261029'),
                                 ('architecture', 'amd64'), ('layers', list(reversed(d.LAYERS))),
                                 ('entrypoint', ['sh']), ('size', True), ('command', ['bash'])]:
            changed = self.image(); changed[key] = replacement
            with self.subTest(key=key), self.assertRaises(ValueError):
                d.validate_image(changed)
        changed = self.image(); changed['qualified'] = True
        with self.assertRaises(ValueError):
            d.validate_image(changed)

    def test_metadata_duplicates_and_real_cli_capture_fail_closed(self):
        with self.assertRaises(ValueError):
            d.decode(b'{"id":1,"id":2}')
        command = [sys.executable, '-I', '-B', '-c']
        self.assertEqual(d.bounded_cli(command + ['print("ok")'], os.environ.copy()), b'ok\n')
        for code, seconds, cap in [('import sys; sys.stderr.write("bad")', 2, 100),
                                   ('print("x"*2000)', 2, 64),
                                   ('import sys; sys.exit(7)', 2, 100),
                                   ('import time; time.sleep(10)', .1, 100)]:
            with self.subTest(code=code), self.assertRaises(ValueError):
                d.bounded_cli(command + [code], os.environ.copy(), seconds, cap)

    def test_literal_source_capture_rejects_changes_and_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); source = root / 'a.py'; source.write_bytes(b'x=1\n')
            expected = {'a.py': d.pin(b'x=1\n')}
            w.verify_files(root, expected)
            source.write_bytes(b'x=2\n')
            with self.assertRaises(ValueError):
                w.verify_files(root, expected)
            link = root / 'link'; link.symlink_to(source)
            with self.assertRaises(ValueError):
                d.read(link, 100)
            hard = root / 'hard'; os.link(source, hard)
            with self.assertRaises(ValueError):
                d.read(source, 100)
            with self.assertRaises(ValueError):
                w.verify_files(root, {'../escape': expected['a.py']})

    def test_selected_release_authenticates_original_source_without_inputs(self):
        digest = d.pin(d.read(HERE / 'SOURCE.json', 65536))['sha256']
        manifest = w.release(digest)
        self.assertEqual(manifest['task_id'], 'NEURAL-034')
        self.assertEqual(manifest['native_qualification'], False)
        self.assertIn(w.OWNER, manifest['files'])
        with self.assertRaises(ValueError):
            w.release('0' * 64)

    def arguments(self, operation, extra):
        return w.parser().parse_args(['--release-sha256', '0' * 64, operation,
                                      '--workspace', '/operator/workspace', *extra])

    def test_provision_delegates_explicit_existing_successor_pair(self):
        args = self.arguments('provision', ['--inputs', '/operator/locators.json'])
        argv, _, _ = w.command(args, {})
        self.assertEqual(argv[3], str(w.PORTABLE / 'provision.py'))
        self.assertEqual(argv[argv.index('--manifest-sha256') + 1], w.MANIFEST_SHA)
        self.assertEqual(argv[argv.index('--current-source-manifest') + 1], str(HERE / 'CURRENT_SOURCE.json'))
        self.assertEqual(argv[argv.index('--current-source-manifest-sha256') + 1],
                         d.pin(d.read(HERE / 'CURRENT_SOURCE.json', 65536))['sha256'])

    def test_relocated_exact_source_without_authentic_inputs_and_tampered_successor_refusal(self):
        manifest = d.decode(d.read(HERE / 'CURRENT_SOURCE.json', 65536))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); root.chmod(0o700)
            for name in manifest['files']:
                target = root / name; target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(w.PORTABLE / name, target)
            shutil.copyfile(w.PORTABLE / 'SOURCE_MANIFEST.json', root / 'SOURCE_MANIFEST.json')
            shutil.copyfile(HERE / 'CURRENT_SOURCE.json', root / 'CURRENT_SOURCE_MANIFEST.json')
            self.assertEqual(w.workspace_source(root, manifest), root)
            self.assertFalse((root / 'artifacts-build').exists())
            (root / 'CURRENT_SOURCE_MANIFEST.json').write_text('{}')
            with self.assertRaises(ValueError):
                w.workspace_source(root, manifest)

    def test_program_delegates_exact_owner_without_mutating_authority(self):
        args = self.arguments('program', ['--program', '/operator/candidate.py',
            '--output', '/operator/workspace/artifacts-build/control01',
            '--review', '/operator/workspace/operator/review.json',
            '--other-reserve-bytes', '400000000', '--docker', '/operator/docker',
            '--host', 'unix:///operator/docker.sock'])
        with (mock.patch.object(w, 'workspace_source', return_value=Path('/operator/workspace')),
              mock.patch.dict(os.environ, {'DOCKER_CONTEXT': 'wrong', 'NEURAL034_DOCKER': 'old'})):
            argv, env, cwd = w.command(args, {})
        self.assertEqual(argv[1:4], ['-I', '-B', '/operator/workspace/' + w.OWNER])
        self.assertEqual(argv[0], str(Path(sys.executable).absolute()))
        self.assertEqual(cwd, '/operator/workspace')
        self.assertNotIn('DOCKER_CONTEXT', env)
        self.assertEqual(env['NEURAL034_DOCKER'], '/operator/docker')
        self.assertEqual(argv[argv.index('--review') + 1], '/operator/workspace/operator/review.json')
        self.assertNotIn('--qualified', argv)
        self.assertEqual(argv[-1], '400000000')
        args.other_reserve_bytes = 0
        with (mock.patch.object(w, 'workspace_source', return_value=Path('/operator/workspace')),
              self.assertRaises(ValueError)):
            w.command(args, {})

    def test_viewer_seven_folds_and_collector_keep_original_restricted_route(self):
        extras = ['--output', '/operator/result', '--client', '/operator/client.py',
                  '--client-python', '/operator/framework-python', '--max-actions', '161',
                  '--max-images', '140', '--max-output-bytes', '67108864', '--wall-seconds', '900']
        with mock.patch.object(w, 'workspace_source', return_value=Path('/operator/workspace')):
            for fold in range(7):
                args = self.arguments('viewer-fold', extras + ['--fold', str(fold)])
                argv, _, _ = w.command(args, {})
                self.assertEqual(argv[3], str(w.VIEWER / 'transport.py'))
                self.assertEqual(argv[argv.index('--sandbox') + 1], 'macos')
                self.assertEqual(argv[argv.index('--packet') + 1], w.packets(Path('/operator/workspace'))[fold])
                self.assertNotIn('--condition', argv)
            args = self.arguments('viewer-collect', ['--sessions', '/operator/sessions', '--output', '/operator/complete'])
            argv, _, _ = w.command(args, {})
            self.assertEqual(argv[argv.index('--packets') + 1:argv.index('--sessions')],
                             w.packets(Path('/operator/workspace')))
            self.assertEqual(argv[argv.index('--sessions') + 1:argv.index('--output')],
                             [f'/operator/sessions/fold-{i:02d}' for i in range(7)])

    def test_plan_only_cannot_dispatch_and_checker_is_existing_successor(self):
        sha = d.pin(d.read(HERE / 'SOURCE.json', 65536))['sha256']
        text = io.StringIO()
        with (mock.patch.object(w, 'workspace_source', return_value=Path('/operator/workspace')),
              mock.patch.object(d, 'observe') as observe,
              mock.patch.object(os, 'execve') as execute,
              mock.patch('sys.stdout', text)):
            w.main(['--release-sha256', sha, '--plan-only', 'check-program',
                    '--workspace', '/operator/workspace', '--output', '/operator/result'])
        observe.assert_not_called(); execute.assert_not_called()
        plan = json.loads(text.getvalue())
        self.assertEqual(plan['argv'][3:], ['/operator/workspace/check_result.py', '--output', '/operator/result'])
        self.assertIs(plan['authentic_inputs_opened'], False)
        self.assertIs(plan['runtime_qualified'], False)

    def write_packet(self, path, ids):
        stream = io.BytesIO(); np.lib.format.write_array(stream, np.asarray(ids), allow_pickle=False)
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('query_ids.npy', stream.getvalue())
            # A control that tries to decode observations or labels would fail.
            archive.writestr('train_windows.npy', b'NOT AN ARRAY')
            archive.writestr('train_labels.npy', b'NOT AN ARRAY')

    def test_fixed_program_all140_generated_ids_no_observation_or_label_decoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); total = []
            for fold in range(7):
                active = root / str(fold); active.mkdir(); out = active / 'out'; out.mkdir()
                ids = [f'{fold*20+i:024x}' for i in range(20)]
                self.write_packet(active / 'public.npz', ids)
                result = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'fixed_program.py'),
                    '--input', str(active), '--out', str(out)], capture_output=True, timeout=10)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
                document = json.loads((out / 'probabilities.json').read_text())
                self.assertEqual(document, {'schema_version': 1, 'probabilities':
                    [{'query_id': q, 'probability': .5} for q in ids]})
                total.extend(document['probabilities'])
            self.assertEqual(len(total), 140)
            self.assertEqual(len({row['query_id'] for row in total}), 140)

    def test_fixed_program_refuses_incomplete_or_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); out = root / 'out'; out.mkdir()
            for ids in ([f'{i:024x}' for i in range(19)], ['0' * 24] * 20):
                self.write_packet(root / 'public.npz', ids)
                result = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'fixed_program.py'),
                    '--input', str(root), '--out', str(out)], capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((out / 'probabilities.json').exists())


if __name__ == '__main__':
    unittest.main()
