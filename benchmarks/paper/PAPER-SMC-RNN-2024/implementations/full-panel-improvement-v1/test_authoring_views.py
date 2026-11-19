"""Generated-fixture controls on the accepted development exporter path."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
CONTRACT = Path(os.environ.get('SMC_FULL_PANEL_CONTRACT_ROOT', str(HERE)))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bridge = load('smc_authoring_preparation', HERE / 'prepare_authoring_views.py')
accepted = load('smc_accepted_fixture_helper', CONTRACT / 'test_benchmark.py')


class AuthoringPreparationControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        accepted.FullPanelControls.setUpClass()

    def setUp(self):
        self.fixture = accepted.FullPanelControls()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        # macOS TemporaryDirectory names use /var; its canonical /private/var
        # spelling is required by the real unlinked-output guard.
        self.api, self.root = self.fixture.api, self.fixture.root.resolve()
        self.output = self.root / 'pretest'
        expected = {}
        for condition in bridge.CONDITIONS:
            base, rows = self.api._condition_files(self.fixture.pair, self.fixture.pair_doc, condition)
            if condition == bridge.CONDITIONS[1]:
                path = base / 'official_source/example.py'
                path.parent.mkdir()
                path.write_bytes(b'# generated allowed official source fixture\n')
                rows.append({'path': 'official_source/example.py', 'bytes': path.stat().st_size,
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
                self.fixture.pair_doc['condition_manifest_sha256'][condition] = accepted.dump(
                    base / 'delivery_manifest.json', {'files': sorted(rows, key=lambda row: row['path'])})
            rows = sorted((r for r in rows if r['path'] != accepted.module.TEST_INPUT), key=lambda r: r['path'])
            record = {'schema': 'smc_full_panel_development_view_v1', 'task_id': accepted.module.TASK_ID,
                'inference_condition_id': accepted.module.INFERENCE_CONDITION, 'condition': condition,
                'current_task_sha256': self.api.task_sha256, 'policy_sha256': self.api.policy_sha256,
                'pair_sha256': bridge.PAIR_SHA, 'excluded_paths': [accepted.module.TEST_INPUT],
                'files': rows, 'test_input_delivered': False, 'earlier_authoring_blindness_verified': False}
            body = (json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
            expected[condition] = {'manifest_bytes': len(body), 'manifest_sha256': hashlib.sha256(body).hexdigest(),
                'files': len(rows) + 1, 'bytes': sum(r['bytes'] for r in rows) + len(body)}
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(bridge, 'EXPECTED', expected).start()
        for name in ('release_inference_view', 'freeze_method', 'freeze', 'score'):
            mock.patch.object(self.api, name, side_effect=AssertionError('No execution, freeze or TEST release in preparation')).start()

    def prepare(self):
        return bridge.prepare_views(self.api, self.fixture.pair, self.output,
                                    max_bytes=bridge.MAX_BYTES, reserve_bytes=0)

    def test_exact_paired_views_retain_train_validation_and_condition_access(self):
        receipt = self.prepare()
        self.assertEqual(self.api.inspect_pair.call_count, 2)
        for condition in bridge.CONDITIONS:
            root = self.output / condition
            self.assertFalse((root / accepted.module.TEST_INPUT).exists())
            self.assertTrue((root / 'inputs/mc_maze/test/train_input_20ms.h5').is_file())
            self.assertTrue((root / 'inputs/mc_maze/val/eval_target_20ms.h5').is_file())
            self.assertEqual((root / 'official_source/example.py').exists(), condition == bridge.CONDITIONS[1])
            self.assertEqual(receipt['views'][condition]['bytes'], sum(p.stat().st_size for p in root.rglob('*') if p.is_file()))
        for key in ('test_input_delivered', 'authoring_process_started', 'authoring_resources_measured',
                    'pre_test_authoring_isolation_verified', 'candidate_or_model_execution', 'AI_result'):
            self.assertIs(receipt[key], False)
        self.assertEqual(json.loads((self.output / 'AUTHORING_HANDOFF.json').read_text()), receipt)

    def test_bad_capacity_refuses_before_any_material_access(self):
        for cap in (0, True, bridge.MAX_BYTES - 1):
            with self.subTest(cap=cap), self.assertRaises(ValueError):
                bridge.prepare_views(self.api, self.fixture.pair, self.output, max_bytes=cap, reserve_bytes=0)
        self.api.inspect_pair.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_partial_second_view_failure_is_preserved_and_cannot_retry(self):
        original = self.api.prepare_development_view
        def fail_second(*args, **kwargs):
            if args[4] == bridge.CONDITIONS[1]:
                raise RuntimeError('generated second-view failure')
            return original(*args, **kwargs)
        with mock.patch.object(self.api, 'prepare_development_view', side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError, 'second-view failure'):
                self.prepare()
        self.assertTrue((self.output / bridge.CONDITIONS[0] / 'development_manifest.json').is_file())
        self.assertFalse((self.output / 'AUTHORING_HANDOFF.json').exists())
        with self.assertRaisesRegex(ValueError, 'destination already exists'):
            self.prepare()

    def test_changed_development_manifest_cannot_receive_handoff(self):
        original = self.api.prepare_development_view
        def change_after_publish(*args, **kwargs):
            result = original(*args, **kwargs)
            manifest = Path(args[5]) / 'development_manifest.json'
            manifest.chmod(0o600)
            manifest.write_bytes(manifest.read_bytes() + b' ')
            return result
        with mock.patch.object(self.api, 'prepare_development_view', side_effect=change_after_publish):
            with self.assertRaisesRegex(ValueError, 'metadata differs from trusted frozen identity'):
                self.prepare()
        self.assertFalse((self.output / 'AUTHORING_HANDOFF.json').exists())

    def test_symlink_output_parent_refuses_before_material_access(self):
        linked = self.root / 'linked'
        linked.symlink_to(self.root, target_is_directory=True)
        self.output = linked / 'pretest'
        with self.assertRaisesRegex(ValueError, 'Unlinked'):
            self.prepare()
        self.api.inspect_pair.assert_not_called()

    def test_changed_exporter_source_is_rejected_before_import(self):
        root = self.root / 'component'
        root.mkdir()
        source = CONTRACT / 'benchmark.py'
        raw = source.read_bytes()
        (root / 'benchmark.py').write_bytes(b'!' + raw[1:])
        with self.assertRaisesRegex(ValueError, 'source changed'):
            bridge.load_api(self.fixture.repository, root)


if __name__ == '__main__':
    unittest.main(verbosity=2)
