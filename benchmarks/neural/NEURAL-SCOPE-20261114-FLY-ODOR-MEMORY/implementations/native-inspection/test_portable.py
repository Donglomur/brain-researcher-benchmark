"""Generated relocation/admission checks; no authentic input or capacity probes."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class PortableControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.package = self.root / 'moved source with spaces'
        shutil.copytree(ROOT, self.package)
        self.p = module('generated_fly_provision', self.package / 'provision.py')
        self.config = {'python': sys.executable, 'archive': str(self.root / 'missing archive.zip'),
                       'operand_plan': str(self.root / 'missing base.json'),
                       'optional_plan': str(self.root / 'missing optional.json')}
        self.target = self.root / 'new operator with spaces'

    def test_complete_relocated_graph_without_opening_external_inputs(self):
        calls = []
        original = self.p.read
        def record(path, *args):
            calls.append(str(path))
            return original(path, *args)
        with mock.patch.object(self.p, 'read', side_effect=record):
            result = self.p.provision(self.config, str(self.target))
        self.assertFalse(result['selected'])
        self.assertEqual(result['external_bodies_opened'], 0)
        self.assertEqual(set(calls) & set(self.config.values()), set())
        request = json.loads((self.target / 'runtime/REQUEST_TEMPLATE.json').read_bytes())
        for row in request['sources'] + [request[k] for k in ('base_owner', 'process_owner', 'process_closer')]:
            path = Path(row['path'])
            self.assertTrue(path.is_relative_to(self.target))
            body = path.read_bytes()
            self.assertEqual((len(body), hashlib.sha256(body).hexdigest()), (row['bytes'], row['sha256']))
        auditor = module('generated_relocated_auditor', self.target / 'runtime/audit_values.py')
        previous = {key: sys.modules.get(key) for key in ('structural_stream', 'optional_inputs', 'diagnostics')}
        consumer = auditor.load_consumer()
        self.assertEqual(Path(consumer.__file__).parent, self.target / 'runtime/inspector')
        self.assertEqual(previous, {key: sys.modules.get(key) for key in previous})
        self.assertFalse((self.target / 'products').exists())
        self.assertFalse((self.target / 'owner').exists())

    def test_unchanged_request_contract_and_inert_dispatch(self):
        self.p.provision(self.config, str(self.target))
        original = json.loads((self.package / 'templates/REQUEST_TEMPLATE.json').read_bytes())
        bound = json.loads((self.target / 'runtime/REQUEST_TEMPLATE.json').read_bytes())
        for name in ('archive', 'operand_plan', 'optional_plan'):
            self.assertEqual({k: v for k, v in original[name].items() if k != 'path'},
                             {k: v for k, v in bound[name].items() if k != 'path'})
        for name in ('limits', 'own_host_bytes', 'own_retention_bytes', 'task_id', 'schema',
                     'scientific_admission', 'no_network_model_fit', 'attempt'):
            self.assertEqual(bound[name], original[name])
        owner = module('generated_relocated_owner', self.target / 'runtime/owner.py')
        inert = self.target / 'selection/REQUEST_TEMPLATE.json'
        with self.assertRaisesRegex(ValueError, 'not selected'):
            owner.read_request(inert)
        selected = copy.deepcopy(bound)
        selected.update(selected=True, selected_at_unix_ns=100, outside_host_bytes=0,
                        outside_disk_bytes=0, other_selected_cpu_slots=0,
                        root_decision={'path': str(self.root/'generated decision'), 'bytes': 1, 'sha256': '0'*64})
        path = self.target/'selection/GENERATED_REQUEST.json'
        path.write_text(json.dumps(selected)); path.chmod(0o600)
        with mock.patch.object(owner.time, 'time_ns', return_value=101):
            self.assertEqual(owner.read_request(path)[0], selected)
            selected['optional_plan']['sha256'] = '0'*64
            path.write_text(json.dumps(selected))
            with self.assertRaisesRegex(ValueError, 'fixed request fields'):
                owner.read_request(path)
        result = subprocess.run(['/bin/sh', str(self.target/'selection/INERT_DISPATCH.sh')],
                                capture_output=True, text=True, timeout=10,
                                env={'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('inert: root has not bound a selected request', result.stderr)
        self.assertFalse((self.target/'selection/DISPATCH.json').exists())
        self.assertFalse((self.target/'owner').exists())

    def test_source_drift_refuses_before_output_creation(self):
        path = self.package/'runtime/inspector/diagnostics.py'
        path.write_bytes(path.read_bytes()+b'\n# generated drift\n')
        with self.assertRaisesRegex(ValueError, 'source identity mismatch'):
            self.p.provision(self.config, str(self.target))
        self.assertFalse(self.target.exists())

    def test_existing_output_symlinks_and_unsafe_config_refuse(self):
        self.target.mkdir()
        marker=self.target/'keep'; marker.write_text('unchanged')
        with self.assertRaisesRegex(ValueError, 'fresh output'):
            self.p.provision(self.config, str(self.target))
        self.assertEqual(marker.read_text(), 'unchanged')
        link=self.root/'operator link'; link.symlink_to(self.target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'fresh output'):
            self.p.provision(self.config, str(link))
        for config in (dict(self.config, selected=True), dict(self.config, archive='relative'),
                       dict(self.config, optional_plan=self.config['archive'])):
            with self.assertRaises(ValueError):
                self.p.provision(config, str(self.root/'not-created'))
        self.assertFalse((self.root/'not-created').exists())

    def test_fifo_and_non_utf8_config_refuse_before_output_creation(self):
        fifo = self.root / 'config.fifo'
        os.mkfifo(fifo, 0o600)
        encoded = self.root / 'config.utf16.json'
        encoded.write_bytes(json.dumps(self.config).encode('utf-16'))
        for config_path, message in ((fifo, 'ordinary bounded source/config file required'),
                                     (encoded, 'UnicodeDecodeError')):
            result = subprocess.run(
                [sys.executable, '-I', '-S', '-B', str(self.package/'provision.py'),
                 '--config', str(config_path), '--output', str(self.target)],
                capture_output=True, text=True, timeout=5,
                env={'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C'})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(message, result.stderr)
            self.assertFalse(self.target.exists())

    def test_manifest_cannot_drop_dependency_or_request_changed_population(self):
        manifest_path=self.package/'SOURCE_MANIFEST.json'
        manifest=json.loads(manifest_path.read_bytes())
        manifest['files']=[r for r in manifest['files'] if r['path']!='runtime/inspector/diagnostics.py']
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'complete exact package member set'):
            self.p.provision(self.config, str(self.target))
        self.assertFalse(self.target.exists())


if __name__ == '__main__':
    unittest.main()
