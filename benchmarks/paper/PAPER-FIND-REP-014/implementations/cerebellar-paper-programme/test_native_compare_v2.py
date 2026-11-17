"""Generated format-level controls. No author targets, arrays, fits or MATLAB."""
import copy
import unittest

from core import BRANCHES
import native_compare as predecessor
import native_compare_v2 as current


def tree(branch, entries=()):
    """All required roots; generated nonempty leaves only where specified."""
    result = {
        'schema': 'filio_native_numeric_v1', 'family': branch,
        'matlab_version': 'generated-control', 'metadata': {},
        'roots': [], 'records': [],
    }
    by_root = {}
    for key, values, codes, source_class in entries:
        by_root.setdefault(key.split('/')[0], []).append({
            'key': key, 'shape': [1, len(values)], 'values': values,
            'codes': codes, 'source_class': source_class,
        })
    for root in BRANCHES[branch]['targets']:
        records = by_root.get(root)
        direct = records and len(records) == 1 and records[0]['key'] == root
        result['roots'].append({
            'name': root,
            'matlab_class': (records[0]['source_class'] if direct else
                             'cell' if records else 'double'),
            'shape': records[0]['shape'] if direct else [1, 1] if records else [0, 0],
            'empty': not bool(records),
        })
        empty = {
            'key': root, 'shape': [0, 0], 'values': [], 'codes': [],
            'source_class': 'double',
        }
        if root in ('GrCsChronInfo', 'CFsChronInfo') and not records:
            # nb_export's empty cell / zero-width table path has no class.
            empty.pop('source_class')
            result['roots'][-1]['matlab_class'] = 'cell'
        result['records'].extend(records or [empty])
    return result


def altered(reference, key, *, value=None, code=None):
    result = copy.deepcopy(reference)
    row = next(r for r in result['records'] if r['key'] == key)
    if value is not None:
        row['values'][0] = value
    if code is not None:
        row['codes'][0] = code
    return result


class NativeComparisonTests(unittest.TestCase):
    def test_continuous_chronic_measurement_regression(self):
        # Source postrew is mean calcium response, not a source identity.
        key = 'GrCsChronInfo/{2}/postrew'
        ref = tree('MainData', [(key, [2.0], [0], 'double')])
        candidate = altered(ref, key, value=2.000001)
        self.assertEqual(predecessor.compare(ref, candidate, 'MainData')['matched'], 0)
        self.assertEqual(current.compare(ref, candidate, 'MainData')['fraction'], 1)

    def test_source_continuous_columns_share_declared_tolerance(self):
        columns = ('stTau', 'reliab', 'delay_activ_cent', 'delay_activ_cent_4s',
                   'delay_activ_centi', 'prerew_grc', 'postrew', 'postomit',
                   'del_act', 'half_del_act', 'prerewmbase_grc', 'mvmag',
                   'prerewmrewdec_grc')
        for root in ('GrCsChronInfo', 'CFsChronInfo'):
            for column in columns:
                with self.subTest(root=root, column=column):
                    key = root + '/{1}/' + column
                    ref = tree('MainData', [(key, [2.0], [0], 'double')])
                    within = altered(ref, key, value=2.000001)
                    outside = altered(ref, key, value=2.000003)
                    self.assertEqual(current.compare(ref, within, 'MainData')['matched'], 1)
                    self.assertEqual(current.compare(ref, outside, 'MainData')['matched'], 0)

    def test_identity_membership_and_sort_columns_remain_exact(self):
        for column in ('sessionNum', 'cellNum', 'otherCellNum', 'nOmit',
                       'hasDLC', 'sortIx', 'sortIxi', 'prerewSortIx'):
            with self.subTest(column=column):
                key = 'GrCsChronInfo/{1}/' + column
                ref = tree('MainData', [(key, [2.0], [0], 'double')])
                candidate = altered(ref, key, value=2.000001)
                self.assertEqual(current.compare(ref, candidate, 'MainData')['matched'], 0)

    def test_double_storage_counts_regression(self):
        for branch, root in (('passiveMFB', 'antbysess'),
                             ('passiveMFB', 'ncsbysess'),
                             ('IOChRmine', 'cumultrials'),
                             ('gtacr1', 'cumultrials_opto')):
            with self.subTest(root=root):
                key = root if branch == 'passiveMFB' else root + '/{1}'
                ref = tree(branch, [(key, [2.0], [0], 'double')])
                candidate = altered(ref, key, value=2.000001)
                self.assertEqual(predecessor.compare(ref, candidate, branch)['fraction'], 1)
                self.assertEqual(current.compare(ref, candidate, branch)['matched'], 0)

    def test_continuous_integer_valued_observation_is_not_a_count(self):
        ref = tree('passiveMFB', [('antbysesspct', [1.0], [0], 'double')])
        candidate = altered(ref, 'antbysesspct', value=1.0000005)
        self.assertEqual(current.compare(ref, candidate, 'passiveMFB')['fraction'], 1)

    def test_native_integer_class_still_exact(self):
        ref = tree('CF_novice', [('postmag', [2], [0], 'int64')])
        candidate = altered(ref, 'postmag', value=3)
        self.assertEqual(current.compare(ref, candidate, 'CF_novice')['matched'], 0)

    def test_complete_nine_branch_root_support(self):
        self.assertEqual(sum(len(b['targets']) for b in BRANCHES.values()), 67)
        self.assertEqual(len(BRANCHES), 9)
        for branch, spec in BRANCHES.items():
            with self.subTest(branch=branch):
                root = spec['targets'][0]
                ref = tree(branch, [(root, [1.0], [0], 'double')])
                self.assertEqual(current.compare(ref, ref, branch)['fraction'], 1)
                missing_root = copy.deepcopy(ref)
                missing_root['roots'].pop()
                with self.assertRaises(ValueError):
                    current.compare(ref, missing_root, branch)
                missing_leaf = copy.deepcopy(ref)
                missing_leaf['records'].pop()
                with self.assertRaises(ValueError):
                    current.compare(ref, missing_leaf, branch)

    def test_status_codes_and_zero_placeholders(self):
        key = 'GrCsChronInfo/{1}/postomit'
        ref = tree('MainData', [(key, [0, 0, 0, 2], [1, 2, 3, 0], 'double')])
        self.assertEqual(current.compare(ref, ref, 'MainData')['fraction'], 1)
        for code in (True, 1.0, 4):
            with self.subTest(code=code), self.assertRaises(ValueError):
                current.compare(ref, altered(ref, key, code=code), 'MainData')
        mismatch = altered(ref, key, code=2)
        self.assertEqual(current.compare(ref, mismatch, 'MainData')['matched'], 3)
        nonzero_placeholder = altered(ref, key, value=0.000000001)
        self.assertEqual(current.compare(ref, nonzero_placeholder, 'MainData')['matched'], 3)

    def test_unknown_table_column_refuses(self):
        key = 'GrCsChronInfo/{1}/unreviewedMeasurement'
        ref = tree('MainData', [(key, [2], [0], 'double')])
        with self.assertRaisesRegex(ValueError, 'Unreviewed chronic-table column'):
            current.compare(ref, ref, 'MainData')

    def test_empty_chronic_table_is_structural_not_scalar(self):
        ref = tree('MainData', [('allGrCs_rew/{1}', [1], [0], 'double')])
        row = next(r for r in ref['records'] if r['key'] == 'GrCsChronInfo')
        row['key'] = 'GrCsChronInfo/{1}'
        self.assertEqual(current.compare(ref, ref, 'MainData')['elements'], 1)

    def test_private_grade_uses_successor_comparison(self):
        key = 'CFsChronInfo/{1}/postrew'
        ref = tree('MainData', [(key, [2], [0], 'double')])
        candidate = altered(ref, key, value=2.000001)
        documents = {'reference': ref, 'A': candidate, 'B': candidate}
        class Store:
            def json(self, path, pin):
                return documents[path]
        payload = {'schema': 'paper_i_worker_native_grade_v1', 'branch': 'MainData',
                   **{role: {'path': role, 'pin': {}} for role in documents}}
        result = current.grade(payload, Store())
        self.assertTrue(result['complete'])
        self.assertFalse(result['biological_truth'])
        self.assertEqual(result['arms']['A']['fraction'], 1)
        self.assertEqual(result['arms']['B']['fraction'], 1)


if __name__ == '__main__':
    unittest.main()
