"""Generated relocated wiring controls; no data, real probes, network or child."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(path):
    spec = importlib.util.spec_from_file_location('generated_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = load(HERE / 'configure.py')


class Portable(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='consensus-portable-generated-')
        self.base = Path(self.tmp.name).resolve()
        self.package = self.base / 'relocated-package'
        shutil.copytree(HERE, self.package)
        self.config = {
            'schema': 'consensus35_portable_configuration_v1',
            'python': {'path': str(self.base / 'external-python-not-opened'), 'bytes': 1, 'sha256': 'a' * 64},
            'output_path': str(self.base / 'producer'), 'capture_path': str(self.base / 'capture'),
            'audit_output_path': str(self.base / 'audit'),
        }
        self.config.update({k: {'path': str(self.base / ('external-' + k)), 'bytes': size, 'sha256': sha}
                            for k, (size, sha) in C.EXTERNAL.items()})
        self.blockers = [patch.object(socket, 'socket', side_effect=AssertionError('no network')),
                         patch.object(subprocess, 'Popen', side_effect=AssertionError('no child or probes'))]
        for blocker in self.blockers:
            blocker.start()

    def tearDown(self):
        for blocker in reversed(self.blockers):
            blocker.stop()
        self.tmp.cleanup()

    def configured(self):
        return C.configure(self.config, self.base / 'operator', self.package)

    def test_relocated_complete_graph_without_external_reads(self):
        original_read = C.read
        def read(path, *args, **kwargs):
            self.assertTrue(Path(path).is_relative_to(self.package))
            return original_read(path, *args, **kwargs)
        with patch.object(C, 'read', read):
            result = self.configured()
        self.assertEqual((result['files'], result['execution_authority'], result['external_files_read']), (18, False, 0))
        bundle = Path(result['bundle'])
        manifest = json.loads((bundle / 'GENERATED_MANIFEST.json').read_text())
        self.assertEqual(len(manifest['files']), 17)
        for row in manifest['files']:
            raw = Path(row['path']).read_bytes()
            self.assertEqual(C.pin(Path(row['path']), raw), row)
        request = json.loads((bundle / 'REQUEST_INERT.json').read_text())
        self.assertEqual(len(request['sources']), 11)
        self.assertEqual(request['sources']['operands'], self.config['operands'])
        self.assertEqual(request['sources']['targets'], self.config['targets'])
        self.assertFalse(request['execution_authority'])
        self.assertIsNone(request['observer_cpu_reserved_slots'])
        recipe = json.loads((bundle / 'OPERATION.json').read_text())
        self.assertEqual(recipe['future_scope'], dict(objects=35, animals=7, ranges=105,
                         HTTP_transactions=210, successful_namespace_files=440, maximum_returned_entity_bytes=143780))
        self.assertEqual(recipe['bootstrap_source_read_reservation_bytes'], (bundle / 'audit.py').stat().st_size + 1)
        for name in ('producer', 'capture', 'audit', 'external-python-not-opened', 'external-operands', 'external-targets'):
            self.assertFalse((self.base / name).exists())

    def test_inert_launcher_and_owner_refuse_before_external_or_process_work(self):
        result = self.configured()
        bundle = Path(result['bundle'])
        selected = result['request']
        launch = load(bundle / 'launch_once.py')
        owner = load(bundle / 'header_owner.py')
        with patch.object(os, 'setsid', side_effect=AssertionError('no session')), \
             patch.object(os, 'execv', side_effect=AssertionError('no exec')):
            with self.assertRaisesRegex(ValueError, 'inert request cannot launch'):
                launch.launch(selected['path'], selected['bytes'], selected['sha256'])
            with self.assertRaisesRegex(ValueError, 'inert source cannot dispatch'):
                owner.authenticate(selected)
        self.assertFalse(Path(self.config['output_path']).exists())
        self.assertFalse(Path(self.config['output_path'] + '.OUTER_BIRTH.json').exists())

    def test_inert_auditor_refuses_before_any_evidence(self):
        result = self.configured()
        bundle = Path(result['bundle'])
        auditor = load(bundle / 'audit.py')
        inert = {'schema': 'consensus35_offline_header_audit_v1', 'execution_authority': False,
                 'root_authority': 'GENERATED INERT', 'owner_request': {}, 'outer_birth': {},
                 'launch': {}, 'returned': {}, 'auditor': {}, 'output_path': self.config['audit_output_path']}
        path = self.base / 'inert-audit.json'
        body = C.encoded(inert)
        path.write_bytes(body)
        with patch.object(sys, 'argv', ['audit.py', '--request', str(path), '--bytes', str(len(body)),
                                      '--sha256', hashlib.sha256(body).hexdigest()]):
            with self.assertRaisesRegex(ValueError, 'selected offline audit only'):
                auditor.main()
        self.assertFalse(Path(self.config['audit_output_path']).exists())

    def test_changed_package_and_unlisted_member_refused_before_create(self):
        source = self.package / 'runtime' / 'transport.py'
        original = source.read_bytes()
        source.write_bytes(original + b'\n')
        with self.assertRaisesRegex(ValueError, 'manifest source identity|bounded ordinary source'):
            self.configured()
        self.assertFalse((self.base / 'operator').exists())
        source.write_bytes(original)
        (self.package / 'extra.py').write_text('pass\n')
        with self.assertRaisesRegex(ValueError, 'declared ordinary package member|bounded namespace entries'):
            self.configured()
        self.assertFalse((self.base / 'operator').exists())

    def test_invalid_manifest_budgets_refuse_before_member_reads(self):
        manifest = self.package / 'SOURCE_MANIFEST.json'
        original = manifest.read_bytes()
        for rows in ([{'path': 'f%d.py' % i, 'bytes': 1, 'sha256': 'a' * 64} for i in range(65)],
                     [{'path': 'f%d.py' % i, 'bytes': 262144, 'sha256': 'a' * 64} for i in range(9)],
                     [{'path': 'f.py', 'bytes': True, 'sha256': 'a' * 64}]):
            manifest.write_bytes(C.encoded({'schema': 'consensus35_portable_source_manifest_v1', 'files': rows}))
            calls = []
            read = C.read
            def tracked(path, *args, **kwargs):
                calls.append(str(path))
                return read(path, *args, **kwargs)
            with patch.object(C, 'read', tracked):
                with self.assertRaises(ValueError):
                    C.verify_package(self.package)
            self.assertEqual(calls, [str(manifest)])
        manifest.write_bytes(original)

    def test_declared_member_size_is_pre_read_cap_and_extra_directory_refused(self):
        root = self.base / 'tiny-package'
        root.mkdir()
        (root / 'f.py').write_bytes(b'x' * 262144)
        (root / 'SOURCE_MANIFEST.json').write_bytes(C.encoded({
            'schema': 'consensus35_portable_source_manifest_v1',
            'files': [{'path': 'f.py', 'bytes': 1, 'sha256': 'a' * 64}]}))
        calls = []
        read = C.read
        def tracked(path, cap=262144):
            calls.append((str(path), cap))
            return read(path, cap)
        with patch.object(C, 'read', tracked):
            with self.assertRaisesRegex(ValueError, 'bounded ordinary source'):
                C.verify_package(root)
        self.assertEqual(calls[-1], (str(root / 'f.py'), 1))
        (self.package / 'undeclared-empty-directory').mkdir()
        with patch.object(C, 'read', tracked):
            with self.assertRaisesRegex(ValueError, 'declared package directory|bounded namespace entries'):
                C.verify_package(self.package)
        self.assertFalse((self.base / 'operator').exists())

    def test_fixed_population_descriptors_exact_and_no_authority_field(self):
        for field, value in [('bytes', True), ('sha256', '0' * 64)]:
            old = copy.deepcopy(self.config)
            self.config['operands'][field] = value
            with self.assertRaises(ValueError):
                self.configured()
            self.config = old
        self.config['execution_authority'] = True
        with self.assertRaisesRegex(ValueError, 'exact configuration fields'):
            self.configured()
        self.assertFalse((self.base / 'operator').exists())

    def test_overlap_symlink_and_repeat_refused(self):
        original = self.config['capture_path']
        self.config['capture_path'] = self.config['output_path']
        with self.assertRaisesRegex(ValueError, 'distinct'):
            self.configured()
        self.config['capture_path'] = original
        alias = self.base / 'alias'
        alias.symlink_to(self.base, target_is_directory=True)
        self.config['capture_path'] = str(alias / 'capture')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.configured()
        self.config['capture_path'] = original
        self.configured()
        with self.assertRaisesRegex(ValueError, 'fresh root'):
            self.configured()

    def test_complete_functions_and_runtime_bodies_survive_relocation(self):
        result = self.configured()
        bundle = Path(result['bundle'])
        for name in C.ROLES.values():
            self.assertEqual((bundle / name).read_bytes(), (self.package / 'runtime' / name).read_bytes())
        for name in ('header_owner.py', 'launch_once.py', 'bind_audit.py'):
            def functions(path):
                return {n.name: ast.dump(n, include_attributes=False)
                        for n in ast.parse(path.read_bytes()).body
                        if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
            self.assertEqual(functions(bundle / name), functions(self.package / 'templates' / name))
        auditor = load(bundle / 'audit.py')
        self.assertEqual(str(auditor.ROOT), self.config['output_path'])
        self.assertEqual(str(auditor.AUDIT_ROOT), self.config['audit_output_path'])
        reader = auditor.Reader()
        reserved = auditor.reserve_bootstrap(reader, (bundle / 'audit.py').stat().st_size)
        self.assertEqual(reader.maximum + reserved, 12 * 1048576)
        static = json.loads((bundle / 'STATIC_BINDINGS.json').read_text())
        self.assertEqual(static['producer_request'], result['request'])
        self.assertIn(repr(C.pin(bundle / 'STATIC_BINDINGS.json', (bundle / 'STATIC_BINDINGS.json').read_bytes())),
                      (bundle / 'audit.py').read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
