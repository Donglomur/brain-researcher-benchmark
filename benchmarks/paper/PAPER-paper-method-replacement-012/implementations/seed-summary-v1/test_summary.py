"""Generated JSON controls; no arrays, fitting, fixtures on disk or model calls."""
from copy import deepcopy
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import summary

ROOT = Path(os.environ['NUCLR_IMPLEMENTATIONS']) if 'NUCLR_IMPLEMENTATIONS' in os.environ else None
EV = summary._evaluator(ROOT)
SEEDS = [17, 2, 99, 6, 41]


def packet(panel='transductive'):
    sessions = ['sb025_20191007', 'sb026_20191014', 'sb028_20191107', 'sb030_20200110']
    metadata = sum((EV.session_metadata(s, ['EC', 'IN'] * 4, 8) for s in sessions), [])
    ids = [row['id'] for row in metadata]
    labels = {row['id']: row['ei_class'] for row in metadata}
    if panel == 'transductive':
        splits = [{'id': 'neuron-wise', 'train': ids[:4] + ids[8:12] + ids[16:20] + ids[24:28],
                   'val': ids[4:6] + ids[12:14] + ids[20:22] + ids[28:30],
                   'test': ids[6:8] + ids[14:16] + ids[22:24] + ids[30:32]}]
    else:
        splits = []
        for session in sessions:
            test = [uid for uid in ids if uid.startswith(session)]
            train = [uid for uid in ids if uid not in test]
            folds = []
            for validation in [s for s in sessions if s != session]:
                val = [uid for uid in train if uid.startswith(validation)]
                folds.append({'train': [uid for uid in train if uid not in val], 'val': val})
            splits.append({'id': session, 'train': train, 'test': test, 'train_cv': folds})
    suffix = 'transductive' if panel == 'transductive' else 'transductive_zs'
    return {'schema_version': 1, 'task_id': EV.TASK_ID, 'source_commit': EV.SOURCE_COMMIT,
            'input_role': 'generated_engineering_control', 'label_level': 'ei', 'panel': panel,
            'context_variant': 'population_context', 'class_balance': 'resample',
            'source_session_manifest': sessions, 'representation_training_sessions': sessions,
            'label_vocabulary': ['EC', 'IN'], 'source_label_mapping': {'EC': 'EC', 'IN': 'IN'},
            'label_map': labels, 'metadata': metadata, 'splits': splits,
            'provenance': {'split_sha256': 'a'*64, 'metadata_sha256': 'b'*64, 'data_receipt_sha256': 'c'*64,
                           'split_member': f'ei_{suffix}.pkl', 'split_release': 'other_explicit',
                           'split_release_detail': 'Generated control, not source data'},
            'checkpoints': [{'id': f'epoch_{epoch}', 'epoch': epoch, 'ids': ids,
                             'embeddings': [[float(i), float(epoch)] for i in range(len(ids))]}
                            for epoch in (2, 10)]}


def result_for(p, perfect=False):
    spec = EV.validate_packet(p)
    records, selected = [], []
    for split in spec['splits']:
        rows = [{'split_id': split['id'], 'unit_id': uid,
                 'subject_id': spec['metadata'][uid]['subject_id'].lower(),
                 'true': spec['label_map'][uid], 'pred': spec['label_map'][uid] if perfect else 'EC'}
                for uid in spec['ordered_ids'] if uid in split['test']]
        metrics = EV.classification_metrics([r['true'] for r in rows], [r['pred'] for r in rows], spec['vocabulary'])
        selected.append({'split_id': split['id'], 'checkpoint_index': 0, 'checkpoint_id': p['checkpoints'][0]['id'],
                         'epoch': 2, 'cv_metrics': [{'macro_f1': 0.5}, {'macro_f1': 0.5}], 'test_metrics': metrics})
        records.extend(rows)
    return {'schema_version': 1, 'task_id': EV.TASK_ID, 'source_commit': EV.SOURCE_COMMIT,
            'component': 'initial-evaluator-v1', 'status': 'engineering_readout_only',
            'contract_sha256': EV.CONTRACT_SHA256, 'input_role': p['input_role'],
            'panel': p['panel'], 'label_level': p['label_level'], 'context_variant': p['context_variant'],
            'source_label_mapping': p['source_label_mapping'], 'packet_sha256': summary.digest(p),
            'provenance': p['provenance'], 'research_qualified': False, 'full_contract_complete': False,
            'aggregation': 'concatenated selected test predictions; repeated split appearances retain source weight',
            'records': records, 'selected': selected,
            'metrics': EV.classification_metrics([r['true'] for r in records], [r['pred'] for r in records], spec['vocabulary']),
            'resources': {'readout_fits': sum(2 * len(split['cv']) + 1 for split in spec['splits'])}}


def runs(panel='transductive'):
    values = []
    for index, seed in enumerate(SEEDS):
        p = packet(panel)
        # Allow genuinely distinct per-run checkpoint names and features.
        for row in p['checkpoints']:
            row['id'] += f'_seed_{seed}'
            row['embeddings'][0][0] = float(seed)
        values.append({'seed': seed, 'training_run_sha256': summary.digest({'seed': seed}),
                       'packet': p, 'readout_result': result_for(p, perfect=index == 0)})
    return values


def summarize(values, seed_roster=None):
    return summary.summarize_panel(values, seed_roster=SEEDS if seed_roster is None else seed_roster,
                                   method_sha256='d'*64, protocol_sha256='e'*64, implementation_root=ROOT)


class SeedSummaryTests(unittest.TestCase):
    def test_mean_is_seed_mean_not_cross_seed_pooled_f1(self):
        values = runs()
        out = summarize(values)
        self.assertAlmostEqual(out['metrics']['macro_f1']['mean'], 7/15)
        all_records = [r for run in values for r in run['readout_result']['records']]
        pooled = EV.classification_metrics([r['true'] for r in all_records], [r['pred'] for r in all_records])
        self.assertNotAlmostEqual(out['metrics']['macro_f1']['mean'], pooled['macro_f1'])
        self.assertAlmostEqual(out['metrics']['macro_f1']['descriptive_seed_sd_ddof0'], 4/15)
        self.assertAlmostEqual(out['metrics']['macro_f1']['descriptive_seed_sd_ddof1'], (4/15)*(5/4)**0.5)
        self.assertFalse(out['execution_verified'])
        self.assertFalse(out['paper_dispersion_convention_verified'])

    def test_declared_seed_order_is_preserved_without_mutation(self):
        values = runs()[::-1]
        before = deepcopy(values)
        out = summarize(values)
        self.assertEqual([row['seed'] for row in out['runs']], SEEDS)
        self.assertEqual(values, before)
        self.assertEqual(out, summarize(values[::-1]))

    def test_full_zero_shot_outer_panel_retained(self):
        out = summarize(runs('transductive_zero_shot'))
        self.assertEqual([row['test_record_count'] for row in out['runs']], [32]*5)
        self.assertTrue(all(len(row['selected_checkpoints']) == 4 for row in out['runs']))

    def test_missing_duplicate_extra_and_boolean_seeds_refused(self):
        for mode in ('missing', 'duplicate', 'extra', 'boolean', 'wrong_roster'):
            values = runs()
            if mode == 'missing': values.pop()
            elif mode == 'duplicate': values[-1]['seed'] = values[0]['seed']
            elif mode == 'extra': values.append(deepcopy(values[0]))
            elif mode == 'boolean': values[0]['seed'] = True
            else: values[-1]['seed'] = 123
            with self.subTest(mode=mode), self.assertRaises(summary.SummaryError): summarize(values)
        with self.assertRaises(summary.SummaryError): summarize(runs(), [1, 2, 3, 4, 4])

    def test_duplicate_training_run_identity_refused(self):
        values = runs()
        values[1]['training_run_sha256'] = values[0]['training_run_sha256']
        with self.assertRaisesRegex(summary.SummaryError, 'training run identities'): summarize(values)

    def test_changed_panel_provenance_exposure_and_schedule_refused(self):
        for mode in ('provenance', 'context', 'schedule', 'class_balance'):
            values = runs()
            p = values[-1]['packet']
            if mode == 'provenance': p['provenance']['split_sha256'] = 'f'*64
            elif mode == 'context': p['context_variant'] = 'ablated_context'
            elif mode == 'schedule': p['checkpoints'][1]['epoch'] = 11
            else: p['class_balance'] = 'weight'
            values[-1]['readout_result'] = result_for(p)
            with self.subTest(mode=mode), self.assertRaisesRegex(summary.SummaryError, 'seeds must share'): summarize(values)

    def test_incomplete_duplicate_reordered_and_changed_target_records_refused(self):
        for mode in ('missing', 'duplicate', 'order', 'target', 'subject', 'prediction'):
            values = runs()
            rows = values[0]['readout_result']['records']
            if mode == 'missing': rows.pop()
            elif mode == 'duplicate': rows[-1] = deepcopy(rows[0])
            elif mode == 'order': rows.reverse()
            elif mode == 'target': rows[0]['true'] = 'IN'
            elif mode == 'subject': rows[0]['subject_id'] = 'sb099'
            else: rows[0]['pred'] = 'unknown'
            with self.subTest(mode=mode), self.assertRaises(ValueError): summarize(values)

    def test_forged_summary_packet_binding_and_status_refused(self):
        for mode in ('metrics', 'packet', 'status', 'fit_count', 'split_metrics'):
            values = runs()
            r = values[0]['readout_result']
            if mode == 'metrics': r['metrics']['macro_f1'] = 0.0
            elif mode == 'packet': r['packet_sha256'] = '0'*64
            elif mode == 'status': r['research_qualified'] = True
            elif mode == 'fit_count': r['resources']['readout_fits'] = 2
            else: r['selected'][0]['test_metrics']['macro_f1'] = 0.0
            with self.subTest(mode=mode), self.assertRaises(summary.SummaryError): summarize(values)

    def test_wrong_checkpoint_tie_and_nonfinite_cv_refused(self):
        for mode in ('tie', 'nonfinite', 'missing'):
            values = runs()
            s = values[0]['readout_result']['selected'][0]
            if mode == 'tie': s['checkpoint_index'] = 1
            elif mode == 'nonfinite': s['cv_metrics'][0]['macro_f1'] = float('nan')
            else: s['cv_metrics'].pop()
            with self.subTest(mode=mode), self.assertRaises(summary.SummaryError): summarize(values)

    def test_pinned_dependency_and_no_fit_boundary(self):
        with patch.object(summary, 'EVALUATOR_SHA256', '0'*64):
            with self.assertRaisesRegex(summary.SummaryError, 'frozen evaluator'): summarize(runs())
        with patch.object(EV, '_fit_predict', side_effect=AssertionError('must not fit')):
            with patch.object(summary, '_evaluator', return_value=EV):
                summarize(runs())


if __name__ == '__main__':
    unittest.main()
