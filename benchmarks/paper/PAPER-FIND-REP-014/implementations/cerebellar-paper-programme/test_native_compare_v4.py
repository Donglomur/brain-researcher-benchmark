"""Generated counterexamples for six new metadata guards, never native data.

Only the changed non-IO branches run here. The accepted three-IO suite is not
copied or replayed. Complete declared roots are represented by small fixtures.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import BRANCHES
import native_compare_v3 as old
import native_compare_v4 as new


BRANCHES_UNDER_TEST = (
    'MainData', 'learningCurves_DA', 'CF_novice', 'passiveMFB', 'gtacr1',
    'learningCurves_gtacr1',
)
# Independent transcription of MainData.m's 37 assigned mgrps fields.
GROUP_NAMES = '''VTA VTA_250 MFB GrCs_all GrCs_CF GrCs_VTA GrCs_MFB
DA1s_grcs DA1s_grcs_mfb DA1s_grcs_dat DA2s_grcs DA2s_grcs_mfb DA2s_grcs_dat
grcs_2s_has1smatch grcs_2s_has1smatch_mfb grcs_1s_has2smatch
DA1s_grcs_haswater DA1s_grcs_haswater_matched DA1s_grcs_haswater_matched_mfb
DA1s_grcs_haswater_mfb DA1s_grcs_haswater_dat DA1s_grcs_haswater_waterfirst
DA1s_haswater DA1s_waterfirst CF_DA CFs_haswater CFs_waterfirst
CFs_haswater_matched CFs_haswater_MFB CFs_haswater_VTA CF_gcamp CF_rcamp
CFs_VTA CFs_MFB CF_gcamp_VTA male female'''.split()


def learning(branch):
    mice = []
    for mouse in range(2):
        days = [{
            'source_day_ordinal': float(day + 1), 'n_movements': 2.0,
            'completed_mask': [True, False], 'good_movement_mask': [True, True],
            'rewarded_mask': [False, True], 'dtb': 0.001,
        } for day in range(2)]
        item = {
            'source_mouse_ordinal': float(mouse + 1), 'trainingDirs': ['d1', 'd2'],
            'normTime': [0.0, 1.0], 'days': days,
        }
        if branch == 'learningCurves_gtacr1':
            item['group'] = ['Normative Baseline', 'GrC stgtacr1 inhibition'][mouse]
        mice.append(item)
    return mice


def fixture(branch):
    if branch.startswith('learningCurves_'):
        metadata = learning(branch)
    elif branch == 'MainData':
        metadata = {
            'dirTable': [{'Delay': 1.0, 'stimParams': [0.25, 0.01, 20.0],
                          'DAType': 'DAT'}],
            'native_mname': ['m1', 'm2', 'm3'],
            'groups': {name: [1.0, 3.0] for name in GROUP_NAMES},
            'n_native_sessions': 3.0, 'source_conditions': ['DA', 'water'],
            'GrC_clock': [-1.0, 0.0, 1.0], 'CF_clock': [-1.0, 0.0, 1.0],
        }
    elif branch == 'CF_novice':
        metadata = {'native_sessions': 3.0, 'session_cell_counts': [2.0, 1.0, 0.0],
                    'condition': 'first DA training session'}
    elif branch == 'passiveMFB':
        metadata = {'native_sessions': 3.0, 'source_clock_last_session': [-1.0, 0.0, 1.0],
                    'condition': 'passive MFB'}
    else:
        # Group labels are a source plotting convention: do not invent an
        # equality between their length and the number of source collections.
        metadata = {'native_group_counts': [2.0, 1.0, 0.0], 'group_collections': 3.0,
                    'source_group_labels': ['g1', 'g2', 'g3', 'g4']}
    roots, records = [], []
    for root in BRANCHES[branch]['targets']:
        empty_table = root in ('GrCsChronInfo', 'CFsChronInfo')
        shape = [0, 0] if empty_table else [1, 1]
        roots.append({'name': root, 'class': 'cell' if empty_table else 'double',
                      'shape': shape})
        record = {'key': root, 'shape': shape, 'values': [] if empty_table else [1.0],
                  'codes': [] if empty_table else [0]}
        if not empty_table:
            record['source_class'] = 'double'
        records.append(record)
    return {'schema': 'filio_native_numeric_v1', 'family': branch,
            'roots': roots, 'records': records, 'metadata': metadata,
            'matlab_version': 'generated-fixture-not-native'}


def value_at(tree, path):
    for key in path:
        tree = tree[key]
    return tree


def set_at(tree, path, value):
    value_at(tree, path[:-1])[path[-1]] = value


DISCRETE_PATHS = {
    'MainData': [('metadata', 'n_native_sessions'),
                 *[('metadata', 'groups', group, 0) for group in GROUP_NAMES]],
    'CF_novice': [('metadata', 'native_sessions'), ('metadata', 'session_cell_counts', 0)],
    'passiveMFB': [('metadata', 'native_sessions')],
    'gtacr1': [('metadata', 'native_group_counts', 0), ('metadata', 'group_collections')],
}
for _branch in ('learningCurves_DA', 'learningCurves_gtacr1'):
    DISCRETE_PATHS[_branch] = [
        ('metadata', mouse, 'source_mouse_ordinal') for mouse in range(2)
    ] + [
        ('metadata', mouse, 'days', day, field)
        for mouse in range(2) for day in range(2)
        for field in ('source_day_ordinal', 'n_movements')
    ]


class HistoricalMetadataGuards(unittest.TestCase):
    def test_complete_48_roots_and_original_scores_retained(self):
        self.assertEqual(sum(len(BRANCHES[b]['targets']) for b in BRANCHES_UNDER_TEST), 48)
        for branch in BRANCHES_UNDER_TEST:
            with self.subTest(branch=branch):
                ref = fixture(branch)
                before, after = old.compare(ref, copy.deepcopy(ref), branch), new.compare(ref, copy.deepcopy(ref), branch)
                for key in ('matched', 'elements', 'fraction', 'leaves', 'all_roots_present', 'matlab_versions'):
                    self.assertEqual(before[key], after[key])
                self.assertEqual(after['fraction'], 1.0)

    def test_small_float_drift_that_v3_accepts_is_rejected_for_every_declared_field(self):
        for branch, paths in DISCRETE_PATHS.items():
            ref = fixture(branch)
            for path in paths:
                with self.subTest(branch=branch, path=path):
                    got = copy.deepcopy(ref)
                    set_at(got, path, value_at(got, path) + 1e-9)
                    self.assertEqual(old.compare(ref, got, branch)['fraction'], 1.0)
                    with self.assertRaises(ValueError):
                        new.compare(ref, got, branch)

    def test_invalid_identical_reference_and_candidate_cannot_self_certify(self):
        for branch, paths in DISCRETE_PATHS.items():
            for bad in (-1.0, 1.5, True, '1', float('nan'), float('inf')):
                with self.subTest(branch=branch, bad=bad):
                    ref = fixture(branch)
                    set_at(ref, paths[0], bad)
                    with self.assertRaises(ValueError):
                        new.compare(ref, copy.deepcopy(ref), branch)

    def test_scalar_counts_and_ordinals_do_not_accept_agreeing_arrays(self):
        for branch, paths in DISCRETE_PATHS.items():
            path = paths[0] if branch != 'gtacr1' else ('metadata', 'group_collections')
            with self.subTest(branch=branch):
                ref = fixture(branch)
                set_at(ref, path, [1.0])
                with self.assertRaises(ValueError):
                    new.compare(ref, copy.deepcopy(ref), branch)

    def test_all_main_groups_have_positive_integral_exact_indices(self):
        self.assertEqual(len(GROUP_NAMES), 37)
        for group in GROUP_NAMES:
            for bad in (0.0, -1.0, 1.5, True):
                with self.subTest(group=group, bad=bad):
                    ref = fixture('MainData')
                    ref['metadata']['groups'][group] = [bad]
                    with self.assertRaises(ValueError):
                        new.compare(ref, copy.deepcopy(ref), 'MainData')

    def test_main_group_order_and_complete_field_set_are_not_relaxed(self):
        ref = fixture('MainData')
        got = copy.deepcopy(ref)
        got['metadata']['groups']['VTA'].reverse()
        with self.assertRaises(ValueError):
            new.compare(ref, got, 'MainData')
        for field in GROUP_NAMES:
            with self.subTest(missing=field):
                bad = copy.deepcopy(ref)
                del bad['metadata']['groups'][field]
                with self.assertRaises(ValueError):
                    new.compare(bad, copy.deepcopy(bad), 'MainData')
        ref['metadata']['groups']['unreviewed'] = [1.0]
        with self.assertRaises(ValueError):
            new.compare(ref, copy.deepcopy(ref), 'MainData')

    def test_scalar_and_empty_exported_group_vectors_are_preserved(self):
        ref = fixture('MainData')
        ref['metadata']['groups']['VTA'] = []
        ref['metadata']['groups']['MFB'] = 2.0
        self.assertEqual(new.compare(ref, copy.deepcopy(ref), 'MainData')['fraction'], 1.0)
        for branch, field in (('CF_novice', 'session_cell_counts'), ('gtacr1', 'native_group_counts')):
            ref = fixture(branch)
            ref['metadata'][field] = 0.0
            self.assertEqual(new.compare(ref, copy.deepcopy(ref), branch)['fraction'], 1.0)

    def test_learning_ordinals_positive_and_source_masks_logical(self):
        for branch in ('learningCurves_DA', 'learningCurves_gtacr1'):
            for path in (('metadata', 0, 'source_mouse_ordinal'),
                         ('metadata', 1, 'days', 1, 'source_day_ordinal')):
                with self.subTest(branch=branch, zero=path):
                    ref = fixture(branch)
                    set_at(ref, path, 0.0)
                    with self.assertRaises(ValueError):
                        new.compare(ref, copy.deepcopy(ref), branch)
            for field in ('completed_mask', 'good_movement_mask', 'rewarded_mask'):
                for bad in (1.0, 1, 'true'):
                    with self.subTest(branch=branch, field=field, bad=bad):
                        ref = fixture(branch)
                        ref['metadata'][0]['days'][1][field] = [bad]
                        with self.assertRaises(ValueError):
                            new.compare(ref, copy.deepcopy(ref), branch)
                ref, got = fixture(branch), fixture(branch)
                got['metadata'][1]['days'][1][field][0] = not got['metadata'][1]['days'][1][field][0]
                with self.assertRaises(ValueError):
                    new.compare(ref, got, branch)

    def test_learning_optional_group_and_masks_follow_source_helper(self):
        ref = fixture('learningCurves_DA')
        self.assertEqual(new.compare(ref, copy.deepcopy(ref), 'learningCurves_DA')['fraction'], 1.0)
        ref['metadata'][0]['group'] = 'source supplied group'
        for mouse in ref['metadata']:
            for day in mouse['days']:
                del day['good_movement_mask'], day['rewarded_mask']
        self.assertEqual(new.compare(ref, copy.deepcopy(ref), 'learningCurves_DA')['fraction'], 1.0)
        got = copy.deepcopy(ref)
        del got['metadata'][0]['group']
        with self.assertRaises(ValueError):
            new.compare(ref, got, 'learningCurves_DA')
        ref = fixture('learningCurves_gtacr1')
        del ref['metadata'][0]['group']
        with self.assertRaises(ValueError):
            new.compare(ref, copy.deepcopy(ref), 'learningCurves_gtacr1')

    def test_closed_metadata_keys_and_full_mouse_day_mask_support(self):
        for branch in BRANCHES_UNDER_TEST:
            ref = fixture(branch)
            obj = ref['metadata'][0] if branch.startswith('learning') else ref['metadata']
            obj['invented'] = 1.0
            with self.subTest(branch=branch), self.assertRaises(ValueError):
                new.compare(ref, copy.deepcopy(ref), branch)
        for branch in ('learningCurves_DA', 'learningCurves_gtacr1'):
            for path in (('metadata',), ('metadata', 1, 'days'),
                         ('metadata', 1, 'days', 1, 'completed_mask')):
                with self.subTest(branch=branch, path=path):
                    ref, got = fixture(branch), fixture(branch)
                    value_at(got, path).pop()
                    with self.assertRaises(ValueError):
                        new.compare(ref, got, branch)

    def test_continuous_clocks_normtime_dtb_and_root_tolerance_unchanged(self):
        paths = {
            'MainData': [('metadata', 'GrC_clock', 1), ('metadata', 'CF_clock', 1)],
            'passiveMFB': [('metadata', 'source_clock_last_session', 1)],
            'learningCurves_DA': [('metadata', 1, 'normTime', 1), ('metadata', 1, 'days', 1, 'dtb')],
            'learningCurves_gtacr1': [('metadata', 1, 'normTime', 1), ('metadata', 1, 'days', 1, 'dtb')],
        }
        for branch in BRANCHES_UNDER_TEST:
            for path in [('records', 0, 'values', 0), *paths.get(branch, [])]:
                with self.subTest(branch=branch, path=path):
                    ref, got = fixture(branch), fixture(branch)
                    set_at(got, path, value_at(got, path) + 1e-9)
                    self.assertEqual(new.compare(ref, got, branch)['fraction'], 1.0)
                    set_at(got, path, value_at(ref, path) + 1.0)
                    self.assertLess(new.compare(ref, got, branch)['fraction'], 1.0)

    def test_dir_table_is_explicitly_untyped_and_still_uses_v2_tolerance(self):
        ref, got = fixture('MainData'), fixture('MainData')
        got['metadata']['dirTable'][0]['Delay'] += 1e-9
        result = new.compare(ref, got, 'MainData')
        self.assertEqual(result['fraction'], 1.0)
        self.assertEqual(result['metadata_typing_holds'], ['dirTable'])

    def test_complete_root_leaf_status_and_discrete_root_rules_still_apply(self):
        for branch in BRANCHES_UNDER_TEST:
            ref = fixture(branch)
            for field in ('roots', 'records'):
                got = copy.deepcopy(ref)
                got[field].pop()
                with self.subTest(branch=branch, omitted=field), self.assertRaises(ValueError):
                    new.compare(ref, got, branch)
            got = copy.deepcopy(ref)
            got['records'][0]['codes'][0] = 0.0
            with self.assertRaises(ValueError):
                new.compare(ref, got, branch)
        ref, got = fixture('passiveMFB'), fixture('passiveMFB')
        next(r for r in got['records'] if r['key'] == 'sessnums')['values'][0] += 1e-9
        self.assertLess(new.compare(ref, got, 'passiveMFB')['fraction'], 1.0)

    def test_private_grade_checks_both_arms_and_preserves_reference_pins(self):
        branch = 'CF_novice'
        payload = {'schema': 'paper_i_worker_native_grade_v1', 'branch': branch,
                   **{role: {'path': role + '.json', 'pin': 'generated-pin-' + role}
                      for role in ('reference', 'A', 'B')}}

        class Store:
            def __init__(self):
                self.trees = {role + '.json': fixture(branch) for role in ('reference', 'A', 'B')}
                self.calls = []

            def json(self, path, pin):
                self.calls.append((path, pin))
                return self.trees[path]

        store = Store()
        result = new.grade(payload, store)
        self.assertEqual(store.calls, [(role + '.json', 'generated-pin-' + role)
                                      for role in ('reference', 'A', 'B')])
        self.assertFalse(result['biological_truth'])
        self.assertTrue(result['complete'])
        for role in ('A', 'B'):
            with self.subTest(role=role):
                store = Store()
                store.trees[role + '.json']['metadata']['native_sessions'] += 1e-9
                with self.assertRaises(ValueError):
                    new.grade(payload, store)


if __name__ == '__main__':
    unittest.main(verbosity=2)
