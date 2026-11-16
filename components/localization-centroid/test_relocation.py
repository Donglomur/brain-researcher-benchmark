"""Only new public relocation checks; all numerical fixtures are invented."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_centroid_control import fixture


def load(path):
    spec = importlib.util.spec_from_file_location('portable_centroid_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RelocationTests(unittest.TestCase):
    def test_package_closure_and_no_private_source_paths(self):
        package = json.loads((HERE / 'SOURCE.json').read_text())
        names = {item['path'] for item in package['files']}
        self.assertEqual(names, {'neutral_contract.py', 'centroid_control.py',
            'test_centroid_control.py', 'test_relocation.py', 'README.md', 'SPECIFICATION.md', 'ATTRIBUTION.md'})
        for member in package['files']:
            self.assertEqual(Path(member['path']).name, member['path'])
            raw = (HERE / member['path']).read_bytes()
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()),
                             (member['bytes'], member['sha256']))
            for forbidden in (b'/Us' + b'ers/', b'/ho' + b'me/', b'benchmark-engineering-' + b'evidence', b'authoring/' + b'delivery-'):
                self.assertNotIn(forbidden, raw)
        self.assertFalse(package['scientifically_qualified'])
        self.assertEqual(package['task_id'], 'NEURAL-SCOPE-20261114-LOCALIZATION')

    def test_full_cli_and_scorer_from_unrelated_directory(self):
        neural, bodies, reference = fixture()
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); component = base / 'portable'; component.mkdir()
            for name in ('neutral_contract.py', 'centroid_control.py'):
                shutil.copyfile(HERE / name, component / name)
            inputs = base / 'packet'; (inputs / 'inputs').mkdir(parents=True)
            for digest, body in bodies.items():
                (inputs / 'inputs' / (digest + '.npy')).write_bytes(body)
            raw = json.dumps(neural).encode(); manifest = base / 'manifest.json'; manifest.write_bytes(raw)
            program = hashlib.sha256((component / 'centroid_control.py').read_bytes()).hexdigest()
            module = load(component / 'centroid_control.py')
            previous = Path.cwd()
            try:
                os.chdir(base)
                module.main(['--repo-root', str(component), '--manifest', str(manifest),
                    '--manifest-sha256', hashlib.sha256(raw).hexdigest(), '--program-sha256', program,
                    '--participant-root', str(inputs), '--geometry-byte-budget', '10000',
                    '--output', str(base / 'predictions.json'), '--receipt', str(base / 'receipt.json')])
            finally:
                os.chdir(previous)
            predictions = json.loads((base / 'predictions.json').read_text())
            receipt = json.loads((base / 'receipt.json').read_text())
            score = module.load_neutral(component).score(neural, reference, predictions, program)
            self.assertEqual((receipt['cases'], score['requested'], score['valid']), (880, 2640, 2640))
            self.assertEqual(score['status'], 'COMPLETE_SUPPORT_SCORE')
            self.assertEqual(score['primary_spike_macro_accuracy'], .5)
            self.assertEqual(receipt['forbidden_body_requests'], 0)
            self.assertTrue(all(row['distance_from_own_undegraded_template_um'] == 0
                                for row in score['template_stability']))

    def test_portable_dependency_and_program_tamper_refused(self):
        neural, _, _ = fixture()
        with tempfile.TemporaryDirectory() as folder:
            component = Path(folder)
            for name in ('neutral_contract.py', 'centroid_control.py'):
                shutil.copyfile(HERE / name, component / name)
            module = load(component / 'centroid_control.py')
            program = hashlib.sha256((component / 'centroid_control.py').read_bytes()).hexdigest()
            manifest = hashlib.sha256(json.dumps(neural, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
            def refused_loader(_): self.fail('geometry read after source identity mismatch')
            for name in ('neutral_contract.py', 'centroid_control.py'):
                original = (component / name).read_bytes()
                (component / name).write_bytes(original + b'\n# changed\n')
                with self.assertRaises(module.ControlError):
                    module.produce(neural, refused_loader, repo_root=component,
                        expected_manifest_sha256=manifest, expected_program_sha256=program,
                        geometry_byte_budget=10000)
                (component / name).write_bytes(original)


if __name__ == '__main__':
    unittest.main()
