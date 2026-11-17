"""Generated metadata/shape controls only; no authentic observations or models."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import h5py
import numpy as np


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


scorer = module('smc_offline_test_scorer', 'scorer.py')
delivery = module('smc_offline_test_delivery', 'delivery.py')


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pred = self.root / 'submission.h5'
        self.panel = self.root / 'panel.json'
        self.reference = self.root / 'generated_reference.json'
        self.episode_path = self.root / 'episode.json'
        self.manifest = self.root / 'delivery.json'
        self.freeze_path = self.root / 'freeze.json'
        self.score_path = self.root / 'score.json'
        self.target = self.root / 'operator/target.h5'
        self.target.parent.mkdir()
        self.data = {
            'schema': 'smc_nlb_panel_v1', 'dataset': 'mc_maze_20', 'phase': 'test',
            'source_commit': scorer.source.AUTHOR_COMMIT, 'dandiset': '000128',
            'dandi_version': '0.220113.0400', 'bin_ms': 20,
            'n_train': 6, 'n_eval': 4, 'n_bins': 35, 'forward_bins': 10,
            'n_heldin': 137, 'n_heldout': 45, 'condition_count': 108,
            'trial_indices_sha256': '1' * 64, 'neuron_indices_sha256': '2' * 64,
            'conditions_sha256': '3' * 64, 'tensor_trial_indices_sha256': '4' * 64,
            'condition_membership_sha256': '5' * 64, 'split_counts': {'train': 4, 'val': 2, 'test': 4},
            'inputs_sha256': {'generated_fixture': '6' * 64},
            'input_content_sha256': {'generated_fixture': '7' * 64},
            'nwb_sources': [{'name': 'generated_fixture', 'sha256': '8' * 64}],
        }
        self.data['expected_shapes'] = {key: [6 if key.startswith('train_') else 4,
            10 if key.endswith('_forward') else 35, 137 if 'heldin' in key else 45]
            for key in scorer.source.RATE_KEYS}
        self.panel.write_text(json.dumps(self.data))
        self.reference.write_text(json.dumps(self.data))
        self.patch(scorer.source, 'REFERENCE_PANEL', self.reference)
        # Tests use a small declared reference; production always pins the full original panel.
        self.patch(scorer.policy, 'contracts', lambda: {})
        with h5py.File(self.pred, 'w') as handle:
            group = handle.create_group(scorer.source.DATASET)
            for key in scorer.source.REQUIRED_KEYS:
                group.create_dataset(key, data=np.ones(self.data['expected_shapes'][key]))
        self.manifest.write_text(json.dumps({'schema': 'smc_offline_participant_delivery_v1', 'condition': 'paper_data',
            'task_id': scorer.policy.TASK_ID, 'primary_contract_sha256': scorer.policy.PRIMARY_SHA256,
            'current_task_sha256': '8' * 64}))
        self.episode = {
            'schema': 'smc_offline_episode_policy_v1', 'task_id': scorer.policy.TASK_ID,
            'comparison_scope': 'original_offline_mc_maze_20ms',
            'primary_contract_sha256': scorer.policy.PRIMARY_SHA256,
            'current_task_sha256': '8' * 64,
            'reference_panel_sha256': scorer.source.sha256(self.reference),
            'paired_delivery_sha256': 'a' * 64,
            'condition_manifest_sha256': {'paper_data': scorer.source.sha256(self.manifest), 'paper_data_author_code': 'b' * 64},
            'materials_policy_sha256': 'c' * 64, 'selection_adaptation_policy_sha256': 'd' * 64,
            'resource_budget_policy_sha256': 'e' * 64, 'scientific_comparison_policy_sha256': 'f' * 64,
            'trusted_operator_review_sha256': '0' * 64,
            'author_calibration_receipt_sha256': {'causal': '1' * 64, 'noncausal': '2' * 64},
            'references': [
                {'id': 'published-causal', 'role': 'published', 'arm': 'causal', 'co_bps': 0.3225, 'source_receipt_sha256': '3' * 64},
                {'id': 'published-noncausal', 'role': 'published', 'arm': 'noncausal', 'co_bps': 0.3407, 'source_receipt_sha256': '3' * 64},
                {'id': 'reproduced-causal', 'role': 'qualified_reproduced', 'arm': 'causal', 'co_bps': 0.31, 'source_receipt_sha256': '1' * 64},
                {'id': 'reproduced-noncausal', 'role': 'qualified_reproduced', 'arm': 'noncausal', 'co_bps': 0.33, 'source_receipt_sha256': '2' * 64},
            ],
            'selected_reference_id': 'published-noncausal',
        }
        self.write_episode()

    def patch(self, owner, key, value):
        item = patch.object(owner, key, value)
        item.start()
        self.addCleanup(item.stop)

    def write_episode(self):
        self.episode_path.write_text(json.dumps(self.episode))
        self.episode_sha = scorer.source.sha256(self.episode_path)

    def freeze(self, **overrides):
        options = dict(condition='paper_data', method_id='generated-only', run_receipt_sha256='9' * 64,
            seed=0, behavior_guided_fitting=False, behavior_guided_selection=False)
        options.update(overrides)
        return scorer.freeze_predictions(self.pred, self.panel, self.episode_path, self.episode_sha,
            self.manifest, self.freeze_path, **options)

    def validate(self):
        return scorer.validate_freeze(self.pred, self.panel, self.episode_path, self.episode_sha,
            self.manifest, self.freeze_path)

    def test_one_full_window_candidate_without_source_arm(self):
        self.assertFalse(self.target.exists())
        record = self.freeze()
        self.assertNotIn('arm', record)
        self.assertEqual(record['scientific_outcome'], 'unknown')
        self.validate()
        interface = delivery.participant_task(self.data, 'a' * 64)
        self.assertTrue(interface['temporal_access']['full_observed_window_allowed'])
        self.assertEqual(interface['prediction_abi']['primary_improvement_submission'], 'offline/submission.h5')
        self.assertNotIn('submissions', interface['prediction_abi'])
        with self.assertRaises(FileExistsError):
            self.freeze()

    def test_cannot_choose_lower_reproduced_or_weaker_published_anchor(self):
        for selected in ('published-causal', 'reproduced-noncausal'):
            with self.subTest(selected=selected):
                self.episode['selected_reference_id'] = selected
                self.write_episode()
                with self.assertRaisesRegex(ValueError, 'not strongest'):
                    self.freeze()

    def test_stronger_reproduced_anchor_is_required_when_present(self):
        self.episode['references'][2]['co_bps'] = 0.35
        self.write_episode()
        with self.assertRaisesRegex(ValueError, 'not strongest'):
            self.freeze()
        self.episode['selected_reference_id'] = 'reproduced-causal'
        self.write_episode()
        self.freeze()

    def test_published_anchor_and_original_panel_cannot_change(self):
        self.episode['references'][1]['co_bps'] = 0.3
        self.write_episode()
        with self.assertRaisesRegex(ValueError, 'published 20-ms anchor'):
            self.freeze()
        self.episode['references'][1]['co_bps'] = 0.3407
        self.write_episode()
        self.data['trial_indices_sha256'] = 'a' * 64
        self.panel.write_text(json.dumps(self.data))
        with self.assertRaisesRegex(scorer.source.ContractError, 'complete source reference'):
            self.freeze()

    def test_missing_companion_arrays_and_bad_shape_fail(self):
        with h5py.File(self.pred, 'a') as handle:
            del handle[scorer.source.DATASET]['eval_rates_heldout_forward']
        with self.assertRaisesRegex(scorer.source.ContractError, 'missing or extra'):
            self.freeze()
        with h5py.File(self.pred, 'a') as handle:
            handle[scorer.source.DATASET].create_dataset('eval_rates_heldout_forward', data=np.ones((1, 10, 45)))
        with self.assertRaisesRegex(scorer.source.ContractError, 'incomplete or misaligned'):
            self.freeze()

    def test_old_author_or_source_matched_freeze_is_refused(self):
        self.freeze_path.write_text(json.dumps({'schema': 'smc_nlb_prediction_freeze_v1', 'role': 'author_calibration', 'arm': 'noncausal'}))
        with self.assertRaisesRegex(ValueError, 'not a primary offline AI freeze'):
            self.validate()

    def test_policy_and_condition_identity_are_bound(self):
        with self.assertRaisesRegex(ValueError, 'frozen condition'):
            self.freeze(condition='paper_data_author_code')
        self.freeze()
        self.episode['selected_reference_id'] = 'reproduced-noncausal'
        self.episode_path.write_text(json.dumps(self.episode))
        with self.assertRaisesRegex(ValueError, 'operator-frozen identity'):
            self.validate()

    def test_missing_policy_or_behavior_declaration_is_not_admitted(self):
        self.episode['scientific_comparison_policy_sha256'] = None
        self.write_episode()
        with self.assertRaisesRegex(ValueError, 'missing/invalid frozen identity'):
            self.freeze()
        self.episode['scientific_comparison_policy_sha256'] = 'f' * 64
        self.write_episode()
        with self.assertRaisesRegex(ValueError, 'behavior use'):
            self.freeze(behavior_guided_fitting=None)
        result = self.freeze(behavior_guided_fitting=True)
        self.assertTrue(result['behavior_guided_fitting'])
        self.assertEqual(result['scientific_outcome'], 'unknown')

    def test_score_keeps_all_metrics_and_never_declares_success(self):
        self.freeze()
        self.target.write_bytes(b'generated target stub; not neural data')
        metrics = {'co-bps': 0.36, 'vel R2': 0.8, 'psth R2': 0.6, 'fp-bps': 0.25}
        self.patch(scorer.source, 'TARGET_SHA256', scorer.source.sha256(self.target))
        self.patch(scorer.source, 'load_original_scorer', lambda unused: types.SimpleNamespace(
            evaluate=lambda target, prediction: [{scorer.source.DATASET + '_split': metrics}]))
        result = scorer.score_predictions(self.pred, self.panel, self.episode_path, self.episode_sha,
            self.manifest, self.freeze_path, self.target, scorer.source.TARGET_SHA256, 'generated-stub', self.score_path)
        self.assertEqual(result['metrics'], metrics)
        self.assertEqual(result['scientific_outcome'], 'unknown')
        self.assertNotIn('arm', result)

    def test_pinned_manifest_cannot_contradict_task_or_primary_identity(self):
        original = json.loads(self.manifest.read_text())
        for key, value, message in [('task_id', 'PAPER-WRONG-TASK', 'delivery task'),
            ('primary_contract_sha256', '7' * 64, 'delivery primary contract'),
            ('current_task_sha256', '6' * 64, 'delivery current task')]:
            with self.subTest(key=key):
                self.manifest.write_text(json.dumps({**original, key: value}))
                self.episode['condition_manifest_sha256']['paper_data'] = scorer.source.sha256(self.manifest)
                self.write_episode()
                with self.assertRaisesRegex(ValueError, message):
                    self.freeze()

    def test_freeze_receipt_replacement_during_scoring_is_rejected(self):
        self.freeze()
        self.target.write_bytes(b'generated target stub; not neural data')
        self.patch(scorer.source, 'TARGET_SHA256', scorer.source.sha256(self.target))
        def replace_receipt(target, prediction):
            record = json.loads(self.freeze_path.read_text())
            self.freeze_path.write_text(json.dumps({**record, 'behavior_guided_fitting': True}))
            return [{scorer.source.DATASET + '_split': dict(zip(scorer.source.METRICS, [0.36, 0.8, 0.6, 0.25]))}]
        self.patch(scorer.source, 'load_original_scorer', lambda unused: types.SimpleNamespace(evaluate=replace_receipt))
        with self.assertRaisesRegex(ValueError, 'freeze receipt changed during scoring'):
            scorer.score_predictions(self.pred, self.panel, self.episode_path, self.episode_sha,
                self.manifest, self.freeze_path, self.target, scorer.source.TARGET_SHA256, 'generated-stub', self.score_path)
        self.assertFalse(self.score_path.exists())

    def test_changed_submission_refused_before_target_read(self):
        self.freeze()
        with h5py.File(self.pred, 'a') as handle:
            handle[scorer.source.DATASET]['eval_rates_heldout'][0, 0, 0] = 2
        with self.assertRaisesRegex(ValueError, 'frozen content changed: submission'):
            scorer.score_predictions(self.pred, self.panel, self.episode_path, self.episode_sha,
                self.manifest, self.freeze_path, self.target, scorer.source.TARGET_SHA256, 'unused', self.score_path)
        self.assertFalse(self.target.exists())

    def test_full_window_freeze_cannot_be_relabeled_online_or_author(self):
        record = self.freeze()
        for field, value in [('role', 'author_calibration'), ('comparison_scope', 'strict_online')]:
            altered = {**record, field: value}
            self.freeze_path.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError, 'not a primary offline AI freeze'):
                self.validate()

    def test_public_target_exposure_cannot_be_relabelled_or_removed(self):
        record = self.freeze()
        for value in ('blind_private_holdout', None):
            with self.subTest(value=value):
                altered = {**record, 'target_exposure': value}
                self.freeze_path.write_text(json.dumps(altered))
                with self.assertRaisesRegex(ValueError, 'original public release'):
                    scorer.score_predictions(self.pred, self.panel, self.episode_path, self.episode_sha,
                        self.manifest, self.freeze_path, self.target, scorer.source.TARGET_SHA256, 'unused', self.score_path)
                self.assertFalse(self.target.exists())

    def test_freeze_time_requires_explicit_valid_utc_without_authenticating_it(self):
        record = self.freeze()
        for value in (None, 'not-a-time', '2026-11-17T00:00:00', '2026-11-17T00:00:00-08:00'):
            with self.subTest(value=value):
                self.freeze_path.write_text(json.dumps({**record, 'created_utc': value}))
                with self.assertRaisesRegex(ValueError, 'timestamp'):
                    self.validate()

    def test_episode_duplicate_keys_and_nonfinite_reference_fail(self):
        self.episode_path.write_text('{"schema": "one", "schema": "two"}')
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            scorer.policy.read_json(self.episode_path)
        self.episode['references'][2]['co_bps'] = float('nan')
        self.write_episode()
        with self.assertRaisesRegex(ValueError, 'nonfinite JSON'):
            self.freeze()

    def test_generated_export_preserves_pair_and_uses_offline_metadata(self):
        """Use generated metadata bytes at the authentic-phase admission seam.

        The retained phase/HDF5 admission controls are unchanged; this exercises
        the new planner, manifests, actual copy boundary and atomic output.
        """
        generated = self.root / 'generated_inputs'
        generated.mkdir()
        phase_data = {}
        for phase in ('val', 'test'):
            root = generated / phase
            root.mkdir()
            names = ['train_input_20ms.h5', 'eval_input_20ms.h5']
            if phase == 'val':
                names.append('eval_target_20ms.h5')
            for name in names:
                (root / name).write_bytes(('generated metadata fixture ' + phase + name).encode())
            panel = copy.deepcopy(self.data)
            panel['phase'] = phase
            panel['inputs_sha256'] = {name: scorer.source.sha256(root / name) for name in names if not name.startswith('eval_target')}
            if phase == 'val':
                panel['validation_target_sha256'] = scorer.source.sha256(root / 'eval_target_20ms.h5')
                panel['validation_target_shapes'] = {'generated_fixture': [1]}
            phase_data[phase] = (panel, root)
        paper = self.root / 'paper.pdf'
        paper.write_bytes(b'%PDF-generated fixture')
        task = self.root / 'task.json'
        task.write_text(json.dumps({'id': scorer.policy.TASK_ID, 'generated_fixture': True}))
        primary = self.root / 'improvement.json'
        primary.write_text('{"generated_fixture": "improvement"}')
        reproduction = self.root / 'reproduction.json'
        reproduction.write_text('{"generated_fixture": "reproduction"}')
        license_file = self.root / 'LICENSE'
        license_file.write_text('generated official-code fixture')
        code_row = {'path': 'LICENSE', 'role': 'source', 'bytes': license_file.stat().st_size,
                    'sha256': scorer.source.sha256(license_file)}
        self.patch(delivery.retained, 'PAPER_SHA256', scorer.source.sha256(paper))
        self.patch(delivery.retained, 'admitted_phase', lambda root, phase: phase_data[phase])
        self.patch(delivery.retained, 'official_source_files', lambda *args: (
            [(license_file, Path('LICENSE'), code_row)], {'schema': 'generated_fixture'}))
        self.patch(delivery.policy, 'PRIMARY_CONTRACT', primary)
        self.patch(delivery.policy, 'PRIMARY_SHA256', scorer.source.sha256(primary))
        self.patch(delivery.policy, 'REPRODUCTION_CONTRACT', reproduction)
        self.patch(delivery.policy, 'REPRODUCTION_SHA256', scorer.source.sha256(reproduction))
        output = self.root / 'pair'
        pair = delivery.export_pair(generated, self.root, paper, task, scorer.source.sha256(task), output)
        self.assertEqual(pair['schema'], 'smc_offline_paired_delivery_v1')
        self.assertEqual(pair['code_condition_additions'], ['official_source/LICENSE', 'official_source_manifest.json'])
        self.assertFalse(pair['execution_verified'])
        left = output / 'paper_data'
        right = output / 'paper_data_author_code'
        self.assertEqual((left / 'task.json').read_bytes(), (right / 'task.json').read_bytes())
        self.assertEqual((left / 'reproduction.v1.json').read_bytes(), (right / 'reproduction.v1.json').read_bytes())
        self.assertFalse((left / 'inputs/mc_maze/test/eval_target_20ms.h5').exists())
        self.assertTrue((left / 'inputs/mc_maze/val/eval_target_20ms.h5').exists())
        self.assertFalse((left / 'official_source/LICENSE').exists())
        self.assertTrue((right / 'official_source/LICENSE').exists())
        delivered = json.loads((left / 'task.json').read_text())
        self.assertEqual(delivered['prediction_abi']['primary_improvement_submission'], 'offline/submission.h5')
        self.assertTrue(delivered['temporal_access']['full_observed_window_allowed'])
        with self.assertRaisesRegex(ValueError, 'output already exists'):
            delivery.export_pair(generated, self.root, paper, task, scorer.source.sha256(task), output)


if __name__ == '__main__':
    unittest.main()
