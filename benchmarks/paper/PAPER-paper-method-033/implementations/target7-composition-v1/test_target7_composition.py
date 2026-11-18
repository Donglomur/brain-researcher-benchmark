"""Full-support invented metadata controls; no arrays, models or disk fixtures.

Run only through the existing shared pool. Required explicit paths are supplied by
the admitted operator; imported NumPy is an existing transitive dependency only.
"""
from contextlib import contextmanager, ExitStack
import hashlib
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import target7_composition as c


@contextmanager
def edit(mapping, key, value):
    original = mapping[key]
    mapping[key] = value
    try:
        yield
    finally:
        mapping[key] = original


def fixture(deps):
    rows = {}
    sha = hashlib.sha256(b'invented metadata only').hexdigest()
    for si, subject in enumerate(c.SUBJECTS):
        rows[str(subject)] = {}
        for split, count in c.COUNTS.items():
            records = []
            for i in range(count):
                key = f'sample{i:05d}'
                # Descending image IDs intentionally disagree with source key order.
                image = 70000 + i if split == 'test' else si * 9000 + (8558 - i if split == 'train' else 8559 + i)
                records.append({'key': key, 'image_id': image, 'files': {
                    ext: {'path': f'webdataset_avg_split/{split}/subj{subject:02d}/{key}.{ext}',
                          'bytes': 1, 'sha256': sha} for ext in c.FIELDS}})
            rows[str(subject)][split] = records
    cases = []
    for base in deps['protocol'].cases():
        subject = rows[str(base['subject'])]
        cases.append({**base,
            'query_ids': [hashlib.sha256(f"{base['case_id']}:{i}".encode()).hexdigest() for i in range(982)],
            'train_keys': [r['key'] for r in subject['train'][:base['budget']]],
            'validation_keys': [r['key'] for r in subject['val']]})
    plan = {'generation': deps['generation'], 'cases': cases, 'private_source_rows': rows,
            'selection': 'first lexicographically sorted K training keys;300validation separate',
            'runtime_verified': False}
    required = deps['provision'].designated_records(deps['manifest'])
    receipt = {'source_files_verified': [{k: r[k] for k in ('path', 'bytes', 'sha256')} for r in required],
               'source_bytes': sum(r['bytes'] for r in required),
               'native_decoded_schema_verified': False, 'models_executed': False}
    descriptor = {'path': 'invented.npy', 'bytes': 1, 'sha256': sha}
    payload = {'image_sha256': sha, 'extraction_receipt_sha256': sha, 'selection': descriptor,
               'rgb425': descriptor, 'features': {name: descriptor for name in deps['panel'].FEATURES}}
    targets = [{**payload, 'image_sha256': hashlib.sha256(f'target:{i}'.encode()).hexdigest()}
               for i in range(982)]
    candidates = [[{**payload, 'image_sha256': hashlib.sha256(f'candidate:{i}:{j}'.encode()).hexdigest()}
                   for j in range(8)] for i in range(982)]
    conditions = []
    for case in cases:
        if case['subject'] != 7 or case['mode'] not in c.MODE_ARM:
            continue
        conditions.append({'case_id': case['case_id'], 'freeze_receipt_sha256': sha,
            'generation_frozen_before_target_selection': True,
            # Reverse arrival order: only opaque identity binding can recover the gallery.
            'images': [{'query_id': q, 'target': targets[i], 'candidates': candidates[i]}
                       for i, q in reversed(list(enumerate(case['query_ids'])))]})
    bundle = {'source_kind': 'generated_engineering_control', 'information_condition': 'paper_data',
              'skimage_version': 'invented-not-executed', 'feature_pipeline_sha256': sha,
              'image_prior_sha256': sha, 'conditions': list(reversed(conditions))}
    return plan, receipt, bundle


class CompositionControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.deps = c.load_dependencies(os.environ['MINDBRIDGE_OPERATOR_ROOT'], os.environ['MINDBRIDGE_IMPLEMENTATIONS_ROOT'])
        cls.plan, cls.receipt, cls.bundle = fixture(cls.deps)
        cls.pins = {name: {'bytes': 1, 'sha256': 'a' * 64} for name in ('plan', 'receipt', 'bundle')}

    def compose(self):
        return c.compose_panel(self.plan, self.receipt, self.bundle, self.deps, input_pins=self.pins)

    def invalid(self):
        with self.assertRaises(ValueError):
            self.compose()

    def selected_case(self, mode='reset', budget=500):
        return next(x for x in self.plan['cases'] if x['case_id'] == f'adapt_{mode}_s07_k{budget:04d}')

    def test_full_original_support_and_opaque_query_join(self):
        with patch.object(self.deps['panel'], 'stable_bytes', side_effect=AssertionError('payload opened')):
            result = self.compose()
        self.assertEqual(result['information_condition'], 'paper_data')
        self.assertEqual(len(result['rows']), 6)
        self.assertEqual(len(result['test_image_ids']), 982)
        self.assertEqual({(r['arm'], r['budget']) for r in result['rows']},
                         {(a, b) for a in ('vanilla', 'mindbridge') for b in c.BUDGETS})
        for row in result['rows']:
            self.assertEqual([r['image_id'] for r in row['images']], result['test_image_ids'])
            self.assertEqual(len(row['images'][0]['candidates']), 8)
            self.assertEqual(row['images'][0]['target']['image_sha256'],
                             hashlib.sha256(b'target:0').hexdigest())
            self.assertEqual(row['images'][1]['target']['image_sha256'],
                             hashlib.sha256(b'target:1').hexdigest())
            self.assertEqual([r['image_sha256'] for r in row['images'][0]['candidates']],
                             [hashlib.sha256(f'candidate:0:{i}'.encode()).hexdigest() for i in range(8)])
        self.assertEqual(result['test_image_ids'][:2], ['nsd73k:70000', 'nsd73k:70001'])
        self.assertEqual(result['calibration']['500'][0], 'sample00000')
        self.assertEqual(result['calibration']['500'], result['calibration']['4000'][:500])
        for values in result['calibration'].values():
            self.assertEqual(values, sorted(values))
        provenance = result['preparation_composition']
        self.assertTrue(provenance['operator_private'])
        self.assertEqual(provenance['indexed_case_count'], 32)
        self.assertEqual(provenance['source_file_count'], 88)
        self.assertEqual(provenance['source_tar_count'], 84)
        self.assertEqual(provenance['calibration_source_binding'][0],
                         {'source_key': 'sample00000', 'coco73k_image_id': 35558})
        self.assertEqual(provenance['finding_count'], 48)
        self.assertEqual(tuple(provenance['metrics']), c.METRICS)
        for key in ('original_membership_authenticated', 'freeze_chronology_authenticated',
                    'payloads_opened', 'runtime_qualified', 'scientific_qualification'):
            self.assertIs(provenance[key], False)
        for condition in provenance['conditions']:
            if condition['arm'] == 'mindbridge':
                self.assertEqual([r['subject'] for r in condition['pretraining']], [1, 2, 5])
                self.assertEqual([r['subject'] for r in condition['adaptation']], [1, 2, 5, 7])
                self.assertTrue(all(r['train_count'] == 8559 and r['validation_count'] == 300
                                    for r in condition['pretraining']))
            else:
                self.assertEqual(condition['pretraining'], [])
                self.assertEqual([r['subject'] for r in condition['adaptation']], [7])

    def test_variable_width_sample_keys_preserve_source_lexicographic_order(self):
        records = []
        for i, row in enumerate(self.plan['private_source_rows']['7']['train']):
            key = f'sample{i}'
            records.append({**row, 'key': key, 'files': {
                ext: {**descriptor, 'path': f'webdataset_avg_split/train/subj07/{key}.{ext}'}
                for ext, descriptor in row['files'].items()}})
        records.sort(key=lambda r: r['key'])
        keys = [r['key'] for r in records]
        with ExitStack() as stack:
            stack.enter_context(edit(self.plan['private_source_rows']['7'], 'train', records))
            for case in self.plan['cases']:
                if case['subject'] == 7:
                    stack.enter_context(edit(case, 'train_keys', keys[:case['budget']]))
            result = self.compose()
        self.assertEqual(result['calibration']['500'], keys[:500])
        self.assertLess(result['calibration']['500'].index('sample1'),
                        result['calibration']['500'].index('sample10'))

    def test_access_condition_is_orthogonal_not_defaulted(self):
        with edit(self.bundle, 'information_condition', 'paper_data_author_code'):
            result = self.compose()
            self.assertEqual(result['information_condition'], 'paper_data_author_code')
            self.assertEqual({r['arm'] for r in result['rows']}, {'vanilla', 'mindbridge'})
        with edit(self.bundle, 'information_condition', 'mindbridge'):
            self.invalid()

    def test_full88_required_not_three_target_assets(self):
        with edit(self.receipt, 'source_files_verified', self.receipt['source_files_verified'][:3]):
            self.invalid()

    def test_duplicate_or_wrong_source_pin(self):
        records = self.receipt['source_files_verified']
        with edit(records, 1, records[0]):
            self.invalid()
        with edit(records[0], 'sha256', 'f' * 64):
            self.invalid()

    def test_full32_required_before_six_selected(self):
        with edit(self.plan, 'cases', self.plan['cases'][1:]):
            self.invalid()

    def test_nonselected_source_inventory_cannot_be_dropped(self):
        rows = self.plan['private_source_rows']['2']
        with edit(rows, 'train', rows['train'][:-1]):
            self.invalid()

    def test_cross_subject_test_leak_rejected(self):
        row = self.plan['private_source_rows']['1']['train'][0]
        with edit(row, 'image_id', 70000):
            self.invalid()

    def test_duplicate_images_and_missing_modality_rejected(self):
        rows = self.plan['private_source_rows']['7']['test']
        with edit(rows[1], 'image_id', rows[0]['image_id']):
            self.invalid()
        with edit(rows[0], 'files', {'jpg': rows[0]['files']['jpg']}):
            self.invalid()

    def test_payload_path_cannot_switch_split_or_subject(self):
        desc = self.plan['private_source_rows']['7']['train'][0]['files']['jpg']
        with edit(desc, 'path', desc['path'].replace('/train/', '/val/')):
            self.invalid()

    def test_complete_common_gallery_not_just_same_count(self):
        row = self.plan['private_source_rows']['2']['test'][0]
        with edit(row, 'image_id', 72999):
            self.invalid()

    def test_train_prefix_validation_and_source_exposure(self):
        case = self.selected_case()
        with edit(case, 'train_keys', list(reversed(case['train_keys']))):
            self.invalid()
        with edit(case, 'validation_keys', case['train_keys'][-300:]):
            self.invalid()
        with edit(case, 'source_subjects', [1, 2, 7]):
            self.invalid()

    def test_case_specific_query_identity_and_generation(self):
        a, b = self.plan['cases'][:2]
        with edit(a['query_ids'], 0, b['query_ids'][0]):
            self.invalid()
        with edit(self.plan, 'generation', 'b' * 64):
            self.invalid()

    def test_missing_extra_duplicate_condition(self):
        items = self.bundle['conditions']
        with edit(self.bundle, 'conditions', items[:-1]):
            self.invalid()
        with edit(items, 1, items[0]):
            self.invalid()
        with edit(items[0], 'case_id', 'main_single_s07'):
            self.invalid()

    def test_duplicate_missing_or_cross_case_payload_query(self):
        items = self.bundle['conditions'][0]['images']
        with edit(items, 1, items[0]):
            self.invalid()
        with edit(self.bundle['conditions'][0], 'images', items[:-1]):
            self.invalid()
        with edit(items[0], 'query_id', self.bundle['conditions'][1]['images'][0]['query_id']):
            self.invalid()

    def test_shared_targets_all_eight_candidates_and_freeze(self):
        condition = self.bundle['conditions'][0]
        item = condition['images'][0]
        with edit(item, 'target', {**item['target'], 'image_sha256': 'f' * 64}):
            self.invalid()
        with edit(item, 'candidates', item['candidates'][:7]):
            self.invalid()
        with edit(condition, 'generation_frozen_before_target_selection', False):
            self.invalid()

    def test_integer_alias_and_input_pin_types(self):
        with edit(self.selected_case(), 'subject', 7.0):
            self.invalid()
        with edit(self.pins['plan'], 'bytes', True):
            self.invalid()

    def test_cli_refuses_underbudget_before_any_dependency_load(self):
        argv = ['composer', '--operator-root', '/not/read', '--implementations-root', '/not/read',
                '--output', '/not/written', '--max-read-bytes', '3', '--max-output-bytes', '100']
        for name in ('plan', 'receipt', 'bundle'):
            argv += ['--' + name, '/not/read', '--' + name + '-bytes', '1',
                     '--' + name + '-sha256', 'a' * 64]
        with patch.object(sys, 'argv', argv), patch.object(c, 'load_dependencies',
                side_effect=AssertionError('dependency opened')):
            with self.assertRaises(c.CompositionError):
                c.main()


if __name__ == '__main__':
    class BoundedOutput:
        def __init__(self):
            self.count = 0
            self.exceeded = False

        def write(self, value):
            raw = value.encode('utf-8')
            keep = raw[:max(0, 16383 - self.count)]
            self.exceeded |= len(keep) != len(raw)
            self.count += len(keep)
            sys.__stderr__.buffer.write(keep)

        def flush(self):
            sys.__stderr__.flush()

    output = BoundedOutput()
    sys.stdout = sys.stderr = output
    program = unittest.main(verbosity=2, exit=False)
    raise SystemExit(0 if program.result.wasSuccessful() and not output.exceeded else 1)
