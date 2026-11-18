"""Generated parity/guard controls only; no authentic CSV, models or scoring."""
import hashlib
import json
from pathlib import Path
import socket
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import pandas as pd
import reference_key_adapter as adapter
import _author_reference_key_fragment as author

fragment = Path(__file__).with_name('_author_reference_key_fragment.py').read_bytes()
assert hashlib.sha256(fragment).hexdigest() == 'e806fb77fc58f12fc344d9d718cd8030ef131bd1a03fc9c30483e21928ffacec'
network_attempts = 0
mocked_author_csv_calls = 0


def no_network(*args, **kwargs):
    global network_attempts
    network_attempts += 1
    raise AssertionError('network forbidden')


def frame(role, axis='pattern', indices=None, subjects=None, rois=None):
    indices = [1] if indices is None else indices
    n = len(indices)
    return pd.DataFrame({'Subject': subjects if subjects is not None else ['sub01']*n,
        'ROI': rois if rois is not None else ['V1']*n,
        'Image index' if axis == 'pattern' else 'Vox_idx': indices,
        'Correlation' if role == 'ceiling' else 'Threshold 1': [0.5]*n})


def source_join(left, right, axis):
    global mocked_author_csv_calls
    right = right.copy(deep=True)
    right['generated_threshold_position'] = list(range(len(right)))
    load = author.load_nc_data_pattern if axis == 'pattern' else author.load_nc_data_profile
    with mock.patch.object(author.pd, 'read_csv', side_effect=[left.copy(deep=True), right]) as read:
        try:
            result = load('GENERATED_CEILING_NO_FILE', 'GENERATED_THRESHOLD_NO_FILE')
        finally:
            mocked_author_csv_calls += read.call_count
        assert read.call_count == 2
    return result


class AdapterControls(unittest.TestCase):
    def assert_parity(self, left, right, axis):
        original_left, original_right = left.copy(deep=True), right.copy(deep=True)
        got = adapter.align_reference_keys(left, right, axis=axis)
        expected = source_join(left, right, axis)
        self.assertEqual([p.key.identifier for p in got], expected['identifier'].tolist())
        self.assertEqual([p.threshold_position for p in got], expected['generated_threshold_position'].tolist())
        self.assertEqual([p.ceiling_position for p in got], list(range(len(left))))
        pd.testing.assert_frame_equal(left, original_left)
        pd.testing.assert_frame_equal(right, original_right)
        return got

    def test_pattern_exact_subject_and_fractional_float_casts(self):
        left = frame('ceiling', indices=[1.9, -2.7], subjects=['sub-01','sub-02'])
        right = frame('threshold', indices=[-2,1], subjects=['sub02','sub01'])
        got = self.assert_parity(left, right, 'pattern')
        self.assertEqual([p.key.components for p in got], [('sub01','V1','1'),('sub02','V1','-2')])
        self.assertEqual([p.threshold_position for p in got], [1,0])

    def test_hyphens_are_removed_only_pattern_ceiling(self):
        for axis in ('pattern','profile'):
            with self.subTest(axis=axis):
                left = frame('ceiling', axis=axis, subjects=['sub01'])
                right = frame('threshold', axis=axis, subjects=['sub-01'])
                self.assertEqual(adapter.reference_keys(right,axis=axis,role='threshold')[0].subject,'sub-01')
                with self.assertRaisesRegex(adapter.ReferenceKeyError,'missing/extra'):
                    adapter.align_reference_keys(left,right,axis=axis)
        keys = adapter.reference_keys(frame('ceiling',axis='profile',subjects=['sub-01']),axis='profile',role='ceiling')
        self.assertEqual(keys[0].subject,'sub-01')

    def test_no_case_whitespace_or_delimiter_changes(self):
        left = frame('ceiling',axis='profile',subjects=[' Sub01 '],rois=[' V1 '])
        right = frame('threshold',axis='profile',subjects=[' Sub01 '],rois=[' V1 '])
        got=self.assert_parity(left,right,'profile')
        self.assertEqual(got[0].key.identifier,' Sub01  V1 1')

    def test_pattern_string_cast_is_not_int_of_float(self):
        got=self.assert_parity(frame('ceiling',indices=['0007']),frame('threshold',indices=['7']),'pattern')
        self.assertEqual(got[0].key.index_text,'7')
        left=frame('ceiling',indices=['7.0']);right=frame('threshold',indices=['7'])
        with self.assertRaises((ValueError,TypeError)):source_join(left,right,'pattern')
        with self.assertRaisesRegex(adapter.ReferenceKeyError,'author reference cast'):
            adapter.align_reference_keys(left,right,axis='pattern')

    def test_profile_dtype_is_not_integer_normalized(self):
        got=self.assert_parity(frame('ceiling',axis='profile',indices=[1.0]),frame('threshold',axis='profile',indices=[1.0]),'profile')
        self.assertEqual(got[0].key.index_text,'1.0')
        with self.assertRaisesRegex(adapter.ReferenceKeyError,'missing/extra'):
            adapter.align_reference_keys(frame('ceiling',axis='profile',indices=[1.0]),frame('threshold',axis='profile',indices=[1]),axis='profile')
        got=self.assert_parity(frame('ceiling',axis='profile',indices=['001']),frame('threshold',axis='profile',indices=['001']),'profile')
        self.assertEqual(got[0].key.index_text,'001')

    def test_missing_and_extra_keys_refused(self):
        for left,right in [(frame('ceiling',indices=[1,2]),frame('threshold',indices=[1])),
                           (frame('ceiling',indices=[1]),frame('threshold',indices=[1,2]))]:
            with self.assertRaisesRegex(adapter.ReferenceKeyError,'missing/extra'):
                adapter.align_reference_keys(left,right,axis='pattern')

    def test_missing_and_duplicate_columns_refused(self):
        left=frame('ceiling').drop(columns=['ROI'])
        with self.assertRaisesRegex(adapter.ReferenceKeyError,'missing reference column'):
            adapter.reference_keys(left,axis='pattern',role='ceiling')
        left=frame('ceiling');left.columns=['Subject','ROI','ROI','Correlation']
        with self.assertRaisesRegex(adapter.ReferenceKeyError,'duplicate column'):
            adapter.reference_keys(left,axis='pattern',role='ceiling')

    def test_duplicates_after_author_transform_refused(self):
        left=frame('ceiling',indices=[1.2,1.8],subjects=['sub-01','sub01'])
        with self.assertRaisesRegex(adapter.ReferenceKeyError,'duplicate canonical'):
            adapter.reference_keys(left,axis='pattern',role='ceiling')

    def test_delimiter_free_collisions_within_and_across(self):
        left=frame('ceiling',indices=[1,1],subjects=['ab','a'],rois=['c','bc'])
        with self.assertRaisesRegex(adapter.ReferenceKeyError,'collision within'):
            adapter.reference_keys(left,axis='pattern',role='ceiling')
        left=frame('ceiling',subjects=['ab'],rois=['c'])
        right=frame('threshold',subjects=['a'],rois=['bc'])
        with self.assertRaisesRegex(adapter.ReferenceKeyError,'collision across'):
            adapter.align_reference_keys(left,right,axis='pattern')

    def test_nonfinite_reference_values_refused(self):
        for role,column in [('ceiling','Correlation'),('threshold','Threshold 1')]:
            for value in (float('nan'),float('inf'),-float('inf')):
                with self.subTest(role=role,value=value):
                    data=frame(role);data[column]=value
                    with self.assertRaisesRegex(adapter.ReferenceKeyError,'nonfinite'):
                        adapter.reference_keys(data,axis='pattern',role=role)

    def test_nonfinite_features_and_unsupported_scalars_refused(self):
        for axis in ('pattern','profile'):
            for value in (float('nan'),float('inf'),-float('inf'),'NaN','inf','1e999',None,True,complex(1,1)):
                with self.subTest(axis=axis,value=repr(value)):
                    with self.assertRaises(adapter.ReferenceKeyError):
                        adapter.reference_keys(frame('ceiling',axis=axis,indices=[value]),axis=axis,role='ceiling')

    def test_failed_cast_does_not_mutate_inputs(self):
        left=frame('ceiling',subjects=['sub-01'],indices=['1.2']);before=left.copy(deep=True)
        with self.assertRaises(adapter.ReferenceKeyError):
            adapter.reference_keys(left,axis='pattern',role='ceiling')
        pd.testing.assert_frame_equal(left,before)


if __name__=='__main__':
    with mock.patch.object(socket,'socket',side_effect=no_network),mock.patch.object(socket,'getaddrinfo',side_effect=no_network):
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AdapterControls))
    report={'scope':'generated author-source key parity and strict admission guards only',
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'numpy_version':np.__version__,'pandas_version':pd.__version__,
        'network_attempts':network_attempts,'mocked_author_csv_calls':mocked_author_csv_calls,
        'authentic_CSV_bytes_read':0,'generated_fixture_disk_bytes':0,'scoring_or_normalization':False,
        'failure_details':[(t.id(),detail[-1000:]) for t,detail in result.failures+result.errors]}
    text=json.dumps(report,separators=(',',':'));assert len(text.encode())+1<=4096
    print(text);raise SystemExit(0 if result.wasSuccessful() and network_attempts==0 else 1)
