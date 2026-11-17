"""Failure and exposure controls for the operator command, without target data."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import py_compile
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('operator_routes', ROOT / 'src/neurobench/operator.py')
op = importlib.util.module_from_spec(spec)
spec.loader.exec_module(op)


class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.repo = self.base / 'checkout'
        (self.repo / 'src/neurobench').mkdir(parents=True)
        self.source = self.repo / 'tool.py'
        self.source.write_text("raise RuntimeError('must not import')\n")
        self.manifest = {'schema': 'neurobench_operator_sources_v1',
                         'routes': {task: ['tool.py'] for task in op.TASKS},
                         'files': {'tool.py': op.digest(self.source)}}
        for task in op.TASKS:
            names = [op.LIFECYCLE, 'benchmarks/shared/frozen-neural-lifecycle-v1/candidate_entry.py',
                     'benchmarks/neural/' + task + '/implementations/portable-grading/score.py']
            if task == 'NEURAL-007':
                names += ['benchmarks/neural/NEURAL-007/implementations/finite-attempt-audit/audit.py']
            for name in names:
                path = self.repo/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('pass\n')
                self.manifest['files'][name] = op.digest(path)
            self.manifest['routes'][task] += names
        (self.repo / op.MANIFEST).write_text(json.dumps(self.manifest))

    def tearDown(self):
        self.temp.cleanup()

    def test_source_checks_do_not_execute(self):
        self.assertEqual(op.sources(self.repo, 'NEURAL-077')['tool.py'], op.digest(self.source))
        self.assertTrue(op.routes(self.repo)[0]['source_verified'])
        self.assertEqual(op.routes(self.repo)[0]['scientific_qualification'], 'not_established')
        self.assertEqual(op.routes(self.repo)[0]['authentic_grading'], 'not_executed')

    def test_source_change_refuses_before_data_inspection_and_retains_failure(self):
        self.source.write_text('changed')
        args = argparse.Namespace(action='inspect', task='NEURAL-077', output=str(self.base/'result'),
                                  data_root=str(self.base/'does-not-exist'), layout='original')
        with mock.patch.object(op, 'inspect_inputs', side_effect=AssertionError('must not inspect')):
            result, code = op.run(args, self.repo)
        self.assertEqual(code, 3)
        self.assertIn('source changed', result['error'])
        self.assertEqual(op.read_json(self.base/'result/operator.json')['exit_code'], 3)

    def test_source_links_and_traversal_refused(self):
        self.source.unlink()
        target = self.base / 'outside.py'
        target.write_text('not allowed')
        self.source.symlink_to(target)
        with self.assertRaises(ValueError):
            op.sources(self.repo, 'NEURAL-077')
        with self.assertRaises(ValueError):
            op.source_path(self.repo, '../outside.py')

    def test_authenticated_source_does_not_execute_matching_unpinned_bytecode(self):
        lifecycle = self.repo / op.LIFECYCLE
        marker = self.base / 'cached-code-executed'
        malicious = 'from pathlib import Path\nPath(' + repr(str(marker)) + ").write_text('executed')\n"
        lifecycle.write_text(malicious)
        saved = lifecycle.stat()
        py_compile.compile(str(lifecycle), doraise=True)
        # This comment has the same size and mtime as the compiled code. A normal
        # SourceFileLoader accepts the stale cache even with python -B.
        lifecycle.write_text('#' * (len(malicious) - 1) + '\n')
        os.utime(lifecycle, ns=(saved.st_atime_ns, saved.st_mtime_ns))
        self.manifest['files'][op.LIFECYCLE] = op.digest(lifecycle)
        (self.repo / op.MANIFEST).write_text(json.dumps(self.manifest))
        op.sources(self.repo, 'NEURAL-077')
        op.load_lifecycle(self.repo)
        self.assertFalse(marker.exists())

    def test_output_reuse_repository_and_link_refused(self):
        for output in (self.repo/'result', self.repo, self.base):
            with self.assertRaises(ValueError):
                op.fresh_output(self.repo, output)
        alias = self.base / 'alias'
        alias.symlink_to(self.repo, target_is_directory=True)
        with self.assertRaises(ValueError):
            op.fresh_output(self.repo, alias/'result')

    def test_inspect_allowlist_complete_counts_and_no_private_traversal(self):
        data = self.base / 'data'
        data.mkdir()
        selected = []
        for case in op.CASES:
            file = data / (case+'.npz')
            file.write_bytes(case.encode())
            selected.append(({**op.digest(file), 'path': file.name}, file.name, 'development_features', case))
        private = data/'private'
        private.symlink_to('/does/not/exist')
        class Life:
            @staticmethod
            def _unicode_array(path, key, n):
                return [path.name+'/'+str(i) for i in range(n)]
        with mock.patch.object(op, 'public_members', return_value=(Life, selected)):
            report = op.inspect_inputs(self.repo, 'NEURAL-077', data)
            self.assertTrue(report['complete'])
            self.assertEqual(report['development_rows'], 400)
            self.assertFalse(report['private_assets_opened'])
            (data/selected[-1][0]['path']).write_bytes(b'corrupt')
            failed = op.inspect_inputs(self.repo, 'NEURAL-077', data)
            self.assertFalse(failed['complete'])
            self.assertEqual(failed['members'][-1]['status'], 'unavailable_or_changed')

    def test_native_failure_cannot_be_qualified(self):
        args = argparse.Namespace(action='grade', task='NEURAL-077', output=str(self.base/'grade'),
                                  purpose='development-control', artifacts='descriptor.json', submission='s.npz',
                                  docker_cli='/docker', docker_host='unix:///socket', docker_config='/config')
        def fail(argv, output):
            native = output/'native'
            native.mkdir()
            op.save(native/'result.json', {'status':'scoring_error'})
            return 3
        with mock.patch.object(op, 'dispatch', side_effect=fail):
            result, code = op.run(args, self.repo)
        self.assertEqual(code, 3)
        self.assertEqual(result['authentic_grading'], 'dispatch_attempted_not_completed')
        self.assertEqual(result['scientific_qualification'], 'not_established')
        self.assertTrue((self.base/'grade/dispatch.json').is_file())

    def test_finished_file_score_is_not_method_provenance(self):
        args = argparse.Namespace(action='grade', task='NEURAL-077', output=str(self.base/'grade'),
                                  purpose='model-evaluation', artifacts='descriptor.json', submission='s.npz',
                                  docker_cli='/docker', docker_host='unix:///socket', docker_config='/config')
        def score(argv, output):
            (output/'native').mkdir()
            op.save(output/'native/result.json', {'status':'scored'})
            return 0
        with mock.patch.object(op, 'dispatch', side_effect=score):
            result, code = op.run(args, self.repo)
        self.assertEqual(code, 0)
        self.assertEqual(result['scientific_qualification'], 'not_established')
        self.assertEqual(result['evaluation_kind'], 'submitted_model_output_score_without_independent_method_provenance')

    def test_native_zero_exit_without_valid_result_is_failure(self):
        for index, body in enumerate((None, '{invalid', '[]', '{"status":"scoring_error"}')):
            with self.subTest(body=body):
                args = argparse.Namespace(action='grade', task='NEURAL-077',
                    output=str(self.base / ('grade-invalid-' + str(index))),
                    purpose='development-control', artifacts='descriptor.json', submission='s.npz',
                    docker_cli='/docker', docker_host='unix:///socket', docker_config='/config')
                def child(argv, output):
                    (output / 'native').mkdir()
                    if body is not None:
                        (output / 'native/result.json').write_text(body)
                    return 0
                with mock.patch.object(op, 'dispatch', side_effect=child):
                    result, code = op.run(args, self.repo)
                self.assertEqual(code, 3)
                self.assertEqual(result['status'], 'refused_or_failed')
                self.assertEqual(result['authentic_grading'], 'dispatch_attempted_not_completed')
                self.assertEqual(op.read_json(Path(args.output) / 'operator.json')['exit_code'], 3)

    def test_child_loader_cannot_consume_existing_unpinned_bytecode(self):
        helper = self.base / 'helper.py'
        marker = self.base / 'child-cache-executed'
        malicious = 'from pathlib import Path\nPath(' + repr(str(marker)) + ").write_text('executed')\n"
        helper.write_text(malicious)
        saved = helper.stat()
        py_compile.compile(str(helper), doraise=True)
        helper.write_text('#' * (len(malicious) - 1) + '\n')
        os.utime(helper, ns=(saved.st_atime_ns, saved.st_mtime_ns))
        script_name = 'benchmarks/neural/NEURAL-077/implementations/portable-grading/score.py'
        script = self.repo / script_name
        script.write_text(
            'import importlib.util,sys\nfrom pathlib import Path\n'
            "spec=importlib.util.spec_from_file_location('cached_helper', " + repr(str(helper)) + ')\n'
            'module=importlib.util.module_from_spec(spec)\nspec.loader.exec_module(module)\n'
            "output=Path(sys.argv[sys.argv.index('--output-dir')+1])\noutput.mkdir()\n"
            "(output/'result.json').write_text('{\"status\":\"scored\"}')\n")
        self.manifest['files'][script_name] = op.digest(script)
        (self.repo / op.MANIFEST).write_text(json.dumps(self.manifest))
        args = argparse.Namespace(action='grade', task='NEURAL-077', output=str(self.base / 'child-grade'),
            purpose='development-control', artifacts='descriptor.json', submission='s.npz',
            docker_cli='/docker', docker_host='unix:///socket', docker_config='/config')
        result, code = op.run(args, self.repo)
        self.assertEqual(code, 0)
        self.assertFalse(marker.exists())
        self.assertIn('pycache_prefix=' + str(Path(args.output) / 'bytecode'), result['argv'])
        self.assertFalse((Path(args.output) / 'bytecode').exists())

    def test_prepared_relocation_copies_only_authenticated_complete_allowlist(self):
        data = self.base / 'prepared'
        data.mkdir()
        life = op.load_lifecycle(ROOT)
        selected = []
        for case in op.CASES:
            path = data / (case + '.npz')
            ids = [case + '/' + str(index) for index in range(200)]
            with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as archive:
                archive.writestr('trial_ids.npy', life._npy(ids, (200,), unicode=True))
            selected.append(({**op.digest(path), 'path': 'original/' + path.name},
                             path.name, 'development_features', case))
        (data / 'private-target.txt').write_text('must never be copied')
        (data / 'private-link').symlink_to('/does/not/exist')
        args = argparse.Namespace(action='prepare', task='NEURAL-077', output=str(self.base / 'relocated'),
                                  data_root=str(data), layout='prepared')
        def prepared(argv, output):
            expected = {Path(row[0]['path']) for row in selected}
            copied = {p.relative_to(output / 'source-layout')
                      for p in (output / 'source-layout').rglob('*') if p.is_file()}
            self.assertEqual(copied, expected)
            for asset, _, _, _ in selected:
                self.assertEqual(op.digest(output / 'source-layout' / asset['path']),
                                 {key: asset[key] for key in ('bytes', 'sha256')})
            return 0
        with mock.patch.object(op, 'public_members', return_value=(life, selected)):
            with mock.patch.object(op, 'dispatch', side_effect=prepared):
                report, code = op.run(args, self.repo)
            self.assertEqual(code, 0)
            self.assertEqual(report['inspection']['development_rows'], 400)
            self.assertFalse(report['inspection']['private_assets_opened'])
            (data / selected[-1][1]).write_bytes(b'changed')
            args.output = str(self.base / 'rejected-prepared')
            with mock.patch.object(op, 'dispatch', side_effect=AssertionError('must not dispatch')):
                rejected, code = op.run(args, self.repo)
            self.assertEqual(code, 3)
            self.assertFalse((Path(args.output) / 'source-layout').exists())
            self.assertFalse(rejected['inspection']['complete'])


if __name__ == '__main__':
    unittest.main()
