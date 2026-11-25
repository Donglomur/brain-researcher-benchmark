"""Generated artifact-custody regressions; no R or authentic scientific inputs."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_companion_generated_fixtures", HERE / "generated_controls.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
replay, contract, base = fixtures.replay, fixtures.contract, fixtures.base


class ArtifactCustodyControls(unittest.TestCase):
    def assert_validation_rejects_replacement(self, name, replacement):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures.generated_bundle(root)
            original = contract.artifact_identity
            replaced = []
            def identify(path):
                observed = original(path)
                if path == root / name:
                    path.write_bytes(replacement(path.read_bytes()))
                    replaced.append(name)
                return observed
            with patch.object(contract, 'artifact_identity', side_effect=identify):
                with self.assertRaisesRegex(ValueError, 'artifact_changed_during_validation'):
                    contract.check_bundle(root, 'A', 1_000_000, base)
            self.assertEqual(replaced, [name])

    def test_reject_changed_json_after_inventory(self):
        def alter(raw):
            obj = json.loads(raw)
            obj['vectors']['TE']['values'][0]['value'] = .125
            return base.json_bytes(obj)
        self.assert_validation_rejects_replacement('dl/quest_self.json', alter)

    def test_reject_changed_png_after_inventory(self):
        name = next(iter(contract.FIGURES.values()))
        self.assert_validation_rejects_replacement(name, lambda raw: fixtures.generated_png(2, 1))

    def pipeline(self, mutate):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'out'
            args = fixtures.GeneratedCompanionControls().arguments(output)
            check = contract.check_bundle
            def checked(root, arm, limit, current_base):
                result = check(root, arm, limit, current_base)
                if mutate:
                    path = root / 'dl/quest_self.rds'
                    raw = path.read_bytes()
                    replacement = raw.replace(b'GENERATED', b'ALTEREDXX', 1)
                    self.assertNotEqual(raw, replacement)
                    self.assertEqual(len(raw), len(replacement))
                    path.write_bytes(replacement)
                return result
            def launch(command, *, cwd, env, **kwargs):
                fixtures.generated_bundle(cwd / 'out')
                return subprocess.CompletedProcess(command, 0, b'generated stdout', b'')
            with patch.object(contract, 'load_predecessor', return_value=base), \
                 patch.object(base, 'public_contract', return_value=fixtures.public), \
                 patch.object(base, 'read_pinned', return_value=b'GENERATED SOURCE'), \
                 patch.object(contract, 'source_manifest', return_value=fixtures.generated_manifest()), \
                 patch.object(contract, 'check_bundle', side_effect=checked), \
                 patch.object(replay.subprocess, 'run', side_effect=launch) as invoked:
                if mutate:
                    with self.assertRaisesRegex(ValueError, 'artifact_changed_during_copy'):
                        replay.run(args)
                    self.assertFalse((output / 'MANIFEST.json').exists())
                    record = json.loads((output / 'PROVENANCE.json').read_text())
                    self.assertFalse(record['artifact_bundle_complete'])
                else:
                    manifest = replay.run(args)
                    self.assertEqual(len(manifest['artifacts']), 26)
                    for name, identity in manifest['artifacts'].items():
                        raw = (output / name).read_bytes()
                        self.assertEqual(len(raw), identity['bytes'])
                        self.assertEqual(contract.digest(raw), identity['sha256'])
                    self.assertFalse(manifest['complete_primary_success'])
                invoked.assert_called_once()

    def test_no_complete_manifest_for_changed_copy(self):
        self.pipeline(True)

    def test_unchanged_complete_publication_keeps_exact_pins(self):
        self.pipeline(False)


if __name__ == '__main__':
    unittest.main()
