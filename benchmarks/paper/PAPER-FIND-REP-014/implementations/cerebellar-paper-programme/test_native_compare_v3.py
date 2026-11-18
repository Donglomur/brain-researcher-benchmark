"""Generated metadata regressions: no authentic arrays, MATLAB, fits or targets."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import BRANCHES
import native_compare_v2 as previous
import native_compare_v3 as current


def metadata(branch):
    if branch == 'IOChRmine':
        return {
            'n_io': 2.0, 'n_control': 1.0,
            'source_group_labels': ['IO', 'VTA', 'MFB', 'H2O', 'Light control'],
            'native_iodats_size': [2.0, 3.0], 'native_ctl_size': [1.0, 2.0],
        }
    if branch == 'IOChRmine_imaging':
        return {'native_sessions': 2.0, 'session_cell_counts': [4.0, 7.0]}
    if branch == 'learningCurves_IOChRmine':
        return [{
            'source_mouse_ordinal': 1.0, 'trainingDirs': ['day-one', 'day-two'],
            'normTime': [0.0, 1.0], 'group': 'IO',
            'days': [{
                'source_day_ordinal': 1.0, 'n_movements': 2.0,
                'completed_mask': [True, False], 'dtb': 0.001,
                'good_movement_mask': [True, True],
                'rewarded_mask': [True, False],
            }, {
                'source_day_ordinal': 2.0, 'n_movements': 1.0,
                'completed_mask': True, 'dtb': 0.001,
            }],
        }]
    return {}


def tree(branch):
    # Complete existing root declarations, generated empty numeric arrays.
    # Metadata supplies nonempty comparison support; no biological values.
    return {
        'schema': 'filio_native_numeric_v1', 'family': branch,
        'matlab_version': 'generated-only', 'metadata': metadata(branch),
        'roots': [{'name': name, 'matlab_class': 'double', 'shape': [0, 0],
                   'empty': True} for name in BRANCHES[branch]['targets']],
        'records': [{'key': name, 'shape': [0, 0], 'values': [], 'codes': [],
                     'source_class': 'double'}
                    for name in BRANCHES[branch]['targets']],
    }


class Figure6MetadataTests(unittest.TestCase):
    def test_exact_selected_branch_inputs_are_preserved(self):
        for branch in current.REVIEWED_BRANCHES:
            with self.subTest(branch=branch):
                ref = tree(branch)
                result = current.compare(ref, copy.deepcopy(ref), branch)
                self.assertEqual(result['fraction'], 1)
                self.assertEqual(result['metadata_policy'],
                                 'fig6_source_discrete_metadata_exact_v1')

    def test_expert_fractional_count_predecessor_counterexample(self):
        ref = tree('IOChRmine')
        got = copy.deepcopy(ref)
        got['metadata']['n_io'] += 1e-7
        self.assertEqual(previous.compare(ref, got, 'IOChRmine')['fraction'], 1)
        with self.assertRaisesRegex(ValueError, 'integral source metadata'):
            current.compare(ref, got, 'IOChRmine')

    def test_exact_integer_change_inside_relative_tolerance_refuses(self):
        ref = tree('IOChRmine')
        ref['metadata']['n_io'] = 1000000.0
        got = copy.deepcopy(ref)
        got['metadata']['n_io'] = 1000001.0
        self.assertEqual(previous.compare(ref, got, 'IOChRmine')['fraction'], 1)
        with self.assertRaisesRegex(ValueError, 'Exact source metadata differs'):
            current.compare(ref, got, 'IOChRmine')

    def test_imaging_counts_and_expert_shapes_cannot_float(self):
        for branch, field, index in (
                ('IOChRmine_imaging', 'session_cell_counts', 1),
                ('IOChRmine', 'native_iodats_size', 0),
                ('IOChRmine', 'native_ctl_size', 1)):
            ref = tree(branch)
            got = copy.deepcopy(ref)
            got['metadata'][field][index] += 1e-7
            with self.subTest(field=field):
                self.assertEqual(previous.compare(ref, got, branch)['fraction'], 1)
                with self.assertRaises(ValueError):
                    current.compare(ref, got, branch)

    def test_learning_mouse_and_day_ordinals_and_counts_cannot_float(self):
        branch = 'learningCurves_IOChRmine'
        for field in ('source_mouse_ordinal', 'source_day_ordinal', 'n_movements'):
            ref = tree(branch)
            got = copy.deepcopy(ref)
            target = got['metadata'][0]
            if field != 'source_mouse_ordinal':
                target = target['days'][0]
            target[field] += 1e-7
            with self.subTest(field=field):
                self.assertEqual(previous.compare(ref, got, branch)['fraction'], 1)
                with self.assertRaises(ValueError):
                    current.compare(ref, got, branch)

    def test_reference_metadata_must_also_be_integral(self):
        ref = tree('IOChRmine_imaging')
        for value in (True, -1, float('nan'), float('inf'), 1.5):
            with self.subTest(value=value):
                ref['metadata']['native_sessions'] = value
                with self.assertRaises(ValueError):
                    current.compare(ref, copy.deepcopy(ref), 'IOChRmine_imaging')

    def test_clock_and_normalized_time_keep_existing_tolerance(self):
        branch = 'learningCurves_IOChRmine'
        ref = tree(branch)
        got = copy.deepcopy(ref)
        got['metadata'][0]['normTime'][1] += 5e-7
        got['metadata'][0]['days'][0]['dtb'] += 5e-9
        self.assertEqual(current.compare(ref, got, branch)['fraction'], 1)
        got['metadata'][0]['days'][0]['dtb'] += 1e-5
        self.assertLess(current.compare(ref, got, branch)['fraction'], 1)

    def test_learning_masks_are_boolean_and_exact(self):
        branch = 'learningCurves_IOChRmine'
        for field in ('completed_mask', 'good_movement_mask', 'rewarded_mask'):
            for value in (1, False):
                ref = tree(branch)
                got = copy.deepcopy(ref)
                got['metadata'][0]['days'][0][field][0] = value
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        current.compare(ref, got, branch)

    def test_missing_day_or_optional_mask_refuses(self):
        branch = 'learningCurves_IOChRmine'
        ref = tree(branch)
        for omission in ('day', 'mask'):
            got = copy.deepcopy(ref)
            if omission == 'day':
                got['metadata'][0]['days'].pop()
            else:
                got['metadata'][0]['days'][0].pop('rewarded_mask')
            with self.subTest(omission=omission), self.assertRaises(ValueError):
                current.compare(ref, got, branch)

    def test_unreviewed_metadata_field_refuses_even_if_both_sides_match(self):
        ref = tree('IOChRmine')
        ref['metadata']['unreviewed_identity'] = 1.0
        with self.assertRaisesRegex(ValueError, 'Reviewed source metadata keys'):
            current.compare(ref, copy.deepcopy(ref), 'IOChRmine')

    def test_numeric_source_roots_still_complete(self):
        ref = tree('IOChRmine')
        got = copy.deepcopy(ref)
        got['roots'].pop()
        with self.assertRaisesRegex(ValueError, 'All declared roots'):
            current.compare(ref, got, 'IOChRmine')

    def test_unreviewed_branches_keep_historical_metadata_semantics(self):
        ref = tree('CF_novice')
        ref['metadata'] = {'unreviewed_float': 2.0}
        got = copy.deepcopy(ref)
        got['metadata']['unreviewed_float'] += 1e-7
        old = previous.compare(ref, got, 'CF_novice')
        new = current.compare(ref, got, 'CF_novice')
        self.assertEqual(old['fraction'], new['fraction'])
        self.assertEqual(new['metadata_policy'], 'historical_v2_metadata_unchanged')

    def test_grade_applies_guard_to_both_information_conditions(self):
        branch = 'IOChRmine'
        docs = {role: tree(branch) for role in ('reference', 'A', 'B')}
        class Store:
            def json(self, path, pin):
                return docs[path]
        payload = {'schema': 'paper_i_worker_native_grade_v1', 'branch': branch,
                   **{role: {'path': role, 'pin': {}} for role in docs}}
        result = current.grade(payload, Store())
        self.assertTrue(result['complete'])
        self.assertFalse(result['biological_truth'])
        for role in ('A', 'B'):
            docs[role]['metadata']['n_control'] += 1e-8
            with self.subTest(role=role), self.assertRaises(ValueError):
                current.grade(payload, Store())
            docs[role] = tree(branch)


if __name__ == '__main__':
    unittest.main()
