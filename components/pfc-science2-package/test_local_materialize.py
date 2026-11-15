"""Narrow invented controls for local-ID/staging delta, no scientific execution."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import tomllib
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location('_pfc_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


local = load('local_materialize')
binding = load('bind_local_images')


class LocalDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(os.environ['PFC_LOCAL_FIXTURE_ROOT']) / self._testMethodName
        self.root.mkdir(parents=True)
        self.module = local.load_base()
        self.release = self.root / 'release'
        self.release.mkdir()
        self.stage = self.root / 'assets'
        self.output = self.root / 'tasks/life-sciences/neuroscience/pfc-conditional-reconstruction'
        self.output.parent.mkdir(parents=True)
        self.notices = {}
        for name, target in [(name, self.module.ASSETS) for name in self.module.ASSETS] + [(name, self.notices) for name in self.module.NOTICE_NAMES]:
            raw = ('invented local-only ' + name + '\n').encode()
            (self.release / name).write_bytes(raw)
            target[name] = (len(raw), hashlib.sha256(raw).hexdigest())
        raw = b'{"invented_manifest":true}\n'
        (self.release / 'PUBLIC_ASSET_MANIFEST.json').write_bytes(raw)
        self.manifest = (len(raw), hashlib.sha256(raw).hexdigest())
        self.request = dict(schema=local.SCHEMA, execution_selected=True,
                            release_root=str(self.release), asset_stage=str(self.stage),
                            output_root=str(self.output), agent_image_id='sha256:' + 'a' * 64,
                            verifier_image_id='sha256:' + 'a' * 64)

    def run_local(self, **kwargs):
        return local.materialize_local(self.request, self.module, notice_pins=self.notices,
                                       manifest_pin=self.manifest, **kwargs)

    def before_write_refusal(self):
        with self.assertRaises(ValueError):
            self.run_local()
        self.assertFalse(self.stage.exists())
        self.assertFalse(self.output.exists())

    def test_complete_eight_stage_and_twenty_eight_output(self):
        report = self.run_local()
        self.assertEqual(len(report['staged_files']), 8)
        self.assertEqual(len(report['files']), 28)
        self.assertFalse((self.stage / 'PUBLIC_ASSET_MANIFEST.json').exists())
        for subdir in ('environment', 'tests'):
            self.assertTrue((self.output / subdir / 'Dockerfile').read_text().startswith('FROM sha256:' + 'a' * 64 + '\n'))
        self.assertFalse(report['image_content_platform_and_availability_verified'])
        self.assertFalse(report['native_harbor_validation'])
        self.assertFalse(report['registry_reference_or_portability_claim'])
        self.assertEqual(report['scientific_or_benchmark_count_delta'], 0)
        for row in report['staged_files']:
            original = self.release / row['path']
            staged = self.stage / row['path']
            self.assertEqual(original.read_bytes(), staged.read_bytes())
            self.assertNotEqual(original.stat().st_ino, staged.stat().st_ino)
            self.assertEqual(staged.stat().st_mode & 0o777, 0o400)

    def test_public_registry_mode_remains_unchanged(self):
        self.run_local()
        fresh = local.load_base()
        self.assertIsNone(fresh.IMAGE.fullmatch('sha256:' + 'a' * 64))
        self.assertIsNotNone(fresh.IMAGE.fullmatch('ghcr.io/invented/pfc@sha256:' + 'a' * 64))
        self.assertEqual(hashlib.sha256(local.BASE_PATH.read_bytes()).hexdigest(), local.BASE_SHA256)

    def test_local_rejects_tag_registry_short_and_injection(self):
        for image in ('owned:latest', 'ghcr.io/invented/pfc@sha256:' + 'a' * 64, 'sha256:abc', 'sha256:' + 'a' * 64 + '\nRUN bad'):
            with self.subTest(image=image):
                self.request['agent_image_id'] = image
                self.before_write_refusal()

    def test_false_or_numeric_selection_refused(self):
        for selection in (False, 1, 'true'):
            self.request['execution_selected'] = selection
            self.before_write_refusal()

    def test_manifest_corruption_refused(self):
        (self.release / 'PUBLIC_ASSET_MANIFEST.json').write_bytes(b'{}')
        self.before_write_refusal()

    def test_extra_missing_and_hardlinked_release_refused(self):
        extra = self.release / 'extra.json'
        extra.write_bytes(b'{}')
        self.before_write_refusal()
        extra.unlink()
        target = self.release / 'LICENSE'
        saved = target.read_bytes()
        target.unlink()
        self.before_write_refusal()
        target.write_bytes(saved)
        os.link(target, self.root / 'hardlink')
        self.before_write_refusal()

    def test_source_output_ancestry_refused(self):
        self.module.HERE = self.root / 'source'
        self.module.HERE.mkdir()
        self.output = self.module.HERE / 'tasks/life-sciences/neuroscience/pfc-conditional-reconstruction'
        self.output.parent.mkdir(parents=True)
        self.request['output_root'] = str(self.output)
        self.before_write_refusal()

    def test_nested_source_roots_remain_valid(self):
        with patch.object(local, 'SOURCE_ROOT', self.module.HERE / 'task'):
            report = self.run_local()
        self.assertEqual(len(report['staged_files']), 8)
        self.assertEqual(len(report['files']), 28)

    def test_own_source_ancestor_rejected_before_writes(self):
        protected = self.root / 'own-source'
        protected.mkdir()
        self.stage = protected / 'assets'
        self.request['asset_stage'] = str(self.stage)
        with patch.object(local, 'SOURCE_ROOT', protected):
            self.before_write_refusal()

    def test_release_cannot_be_own_source(self):
        with patch.object(local, 'SOURCE_ROOT', self.release):
            self.before_write_refusal()

    def test_stage_output_ancestry_refused(self):
        self.request['asset_stage'] = str(self.output.parent)
        with self.assertRaises(ValueError):
            self.run_local()
        self.assertFalse(self.output.exists())

    def test_staged_corruption_preserves_failure(self):
        stage = self.stage
        class CorruptStage(self.module.Reads):
            def read(self, path, limit, expected=None):
                if Path(path) == stage / 'LICENSE':
                    path.chmod(0o600)
                    path.write_bytes(b'corrupt')
                return super().read(path, limit, expected)
        with self.assertRaises(ValueError):
            self.run_local(reader=CorruptStage())
        self.assertTrue(self.stage.exists())
        self.assertFalse(self.output.exists())
        self.assertEqual((self.stage / 'LICENSE').read_bytes(), b'corrupt')

    def test_local_complete_image_overlay_only_two_fields(self):
        body = (self.module.HERE / 'task/task.toml').read_bytes()
        overlay = binding.overlay_complete_images(body, 'sha256:' + 'b' * 64, 'sha256:' + 'c' * 64)
        before = tomllib.loads(body.decode())
        after = tomllib.loads(overlay.decode())
        self.assertEqual(after['environment'].pop('docker_image'), 'sha256:' + 'b' * 64)
        self.assertEqual(after['verifier']['environment'].pop('docker_image'), 'sha256:' + 'c' * 64)
        self.assertEqual(after, before)
        self.assertEqual(after['verifier']['environment']['network_mode'], 'no-network')

    def test_overlay_rejects_changed_task_and_equal_or_mutable_images(self):
        body = (self.module.HERE / 'task/task.toml').read_bytes()
        for candidate, left, right in [(body + b'\n', 'sha256:' + 'b' * 64, 'sha256:' + 'c' * 64),
                                       (body, 'sha256:' + 'b' * 64, 'sha256:' + 'b' * 64),
                                       (body, 'owned:latest', 'sha256:' + 'c' * 64)]:
            with self.assertRaises(ValueError):
                binding.overlay_complete_images(candidate, left, right)


if __name__ == '__main__':
    unittest.main(verbosity=2)
