"""Generated whole-grade regressions; authored now, execution separately selected.

Running this suite is a numerical grade campaign, not the fixture-sizing pass.
It needs an independently selected NumPy directory/version; absence skips the
suite rather than discovering/installing a runtime. It uses the actual captured
operator entry, never a duplicate scorer or direct reducer substitute.

NOMAD_TEST_ARTIFACT_ROOT optionally selects an existing ordinary absolute
directory for exclusive per-case folders. Successes and failures are retained
there; when absent the original temporary-directory cleanup is preserved.
The frozen builder request and measurement remain untouched. A prospective
test-owned request refresh caps logical grader writes at 64 MiB and complete
refreshed fixture files at 64 MiB per case: 128 MiB per case. Four separately
selected cases need at most 512 MiB plus a 16 MiB pool/log allowance. These are
software limits, not an OS disk quota or a reservation for an unbounded suite.
"""
from collections import Counter
from contextlib import contextmanager
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
_fixture_spec = importlib.util.spec_from_file_location(
    'nomad_generated_fixture_only', Path(__file__).resolve().parent / 'fixture_builder.py')
_fixture_module = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(_fixture_module)
build, GROUPS = _fixture_module.build, _fixture_module.GROUPS
packed_json, byte_pin = _fixture_module.packed_json, _fixture_module.pin
NEGATIVE_CASES = (
    'missing_pair_fact', 'duplicate_pair_fact', 'missing_anchor_selector',
    'duplicate_anchor_reference', 'wrong_anchor_role', 'candidate_profile_mismatch',
    'product_id_alias', 'candidate_label_collision', 'missing_candidate_panel',
    'query_support_mismatch', 'anchor_sample_mismatch', 'anchor_axis_mismatch',
)
NEGATIVE_MESSAGES = {
    'missing_pair_fact': 'unresolved/invalid scientific archive support before targets',
    'duplicate_pair_fact': 'unresolved/invalid scientific archive support before targets',
    'missing_anchor_selector': 'every expected method/anchor/attempt exactly once before targets',
    'duplicate_anchor_reference': 'cross-method full anchor support|one actual anchor',
    'wrong_anchor_role': 'actual expected archive identity role',
    'candidate_profile_mismatch': 'actual source and method profile before targets',
    'product_id_alias': 'one actual product per ID',
    'candidate_label_collision': 'distinct_bounded_candidate_identity',
    'missing_candidate_panel': 'both_complete_candidate_panels_required',
    'query_support_mismatch': 'actual expected archive identity target_support_pin',
    'anchor_sample_mismatch': 'cross-method full anchor support and target identity before targets',
    'anchor_axis_mismatch': 'cross-method full anchor support and target identity before targets',
}


def exact(value):
    return Fraction(int(value['numerator_hex'], 16), int(value['denominator_hex'], 16))


class CandidateGradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.version = os.environ.get('NOMAD_TEST_NUMPY_VERSION')
        package_parent = os.environ.get('NOMAD_TEST_NUMPY_DIR')
        if not cls.version or cls.version == 'numerical-runtime-unselected' or not package_parent:
            raise unittest.SkipTest('Separate numerical campaign/runtime selection is required.')
        cls.package_parent = Path(package_parent)
        if not cls.package_parent.is_absolute() or not cls.package_parent.is_dir():
            raise ValueError('NOMAD_TEST_NUMPY_DIR must be an independently selected absolute directory.')
        cls.old_path = list(sys.path)
        cls.addClassCleanup(cls._restore_path)
        sys.path.insert(0, str(cls.package_parent))
        # Only the stdlib adapter is loaded here. Its actual run_operator captures
        # and imports the pinned runtime; numerical imports happen in that path.
        specification = importlib.util.spec_from_file_location('candidate_grade_adapter', ROOT / 'operator_entry.py')
        cls.adapter = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(cls.adapter)
        manifest = json.loads((ROOT / 'SOURCE_MANIFEST.json').read_bytes())
        cls.source_capture_bytes = len((ROOT / 'SOURCE_MANIFEST.json').read_bytes()) + sum(
            row['bytes'] for row in manifest['files'].values())
        if cls.source_capture_bytes > 512 * 1024:
            raise ValueError('Re-quote generated fixture startup bound before campaign.')

    @classmethod
    def _restore_path(cls):
        sys.path[:] = cls.old_path

    @contextmanager
    def _case_folder(self):
        selected = os.environ.get('NOMAD_TEST_ARTIFACT_ROOT')
        if selected is None:
            with tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve()) as folder:
                yield Path(folder)
            return
        root = Path(selected)
        if (not root.is_absolute() or str(root) != selected or '..' in root.parts
                or not selected.isascii() or len(selected) > 768):
            raise ValueError('NOMAD_TEST_ARTIFACT_ROOT must be a bounded canonical absolute path.')
        if any(path.is_symlink() for path in (root, *root.parents)):
            raise ValueError('NOMAD_TEST_ARTIFACT_ROOT ancestry must not contain symlinks.')
        if not stat.S_ISDIR(root.lstat().st_mode):
            raise ValueError('NOMAD_TEST_ARTIFACT_ROOT must be an existing ordinary directory.')
        name = self._testMethodName
        if not name.isascii() or len(name) > 128 or not all(c.isalnum() or c == '_' for c in name):
            raise ValueError('Bounded ordinary test identity required for retained output.')
        folder = Path(tempfile.mkdtemp(prefix='nomad-' + name + '-', dir=root))
        if (folder.parent != root or any(path.is_symlink() for path in (folder, *folder.parents))
                or not stat.S_ISDIR(folder.lstat().st_mode)):
            raise ValueError('Retained case must be an ordinary exclusive child of the selected root.')
        # No cleanup on success or exception: the explicitly selected owner keeps
        # complete fixture, measurement, result, barrier and failure artifacts.
        yield folder

    def _fixture(self, folder, **options):
        destination = Path(folder) / 'fixture'
        measurement = build(destination, self.version, self.source_capture_bytes, **options)
        request_path = destination / 'request.json'
        request_raw = request_path.read_bytes()
        self.assertEqual(hashlib.sha256(request_raw).hexdigest(), measurement['request']['sha256'])
        self.assertEqual(len(request_raw), measurement['request']['bytes'])
        self.assertFalse(measurement['grade_executed'])
        # Preserve the exact builder request/measurement. These deliberately
        # smaller prospective guards have not been measured by a grade run.
        request = json.loads(request_raw)
        request['arguments']['statistical_limits'].update(
            metadata_bytes=4 * 1024 ** 3, live_bytes=2 * 1024 ** 3,
            copy_bytes=1024 ** 3, json_bytes=32 * 1048576)
        request['io_limits'].update(read_bytes=32 * 1048576,
                                    write_bytes=64 * 1048576, max_member_bytes=1048576)
        grade_raw = packed_json(request)
        grade_path = destination / 'grade-request.json'
        capture_bytes = self.source_capture_bytes + len(grade_raw)
        self.assertLessEqual(len(grade_raw), 2 * 1048576,
                             're-quote request extent before a selected campaign')
        self.assertLessEqual(capture_bytes, 16 * 1048576,
                             'complete source/request ceiling remains unchanged')
        measurement_raw = (destination / 'measurement.json').read_bytes()
        refresh = {
            'schema': 'nomad_generated_grade_request_refresh_v1',
            'scope': 'test-only-generated-nonhistorical',
            'original_request': {'path': 'request.json', **byte_pin(request_raw)},
            'builder_measurement': {'path': 'measurement.json', **byte_pin(measurement_raw)},
            'grade_request': {'path': 'grade-request.json', **byte_pin(grade_raw)},
            'numpy_version_declaration': self.version,
            'numpy_parent_declaration': str(self.package_parent),
            'runtime_selected_by_this_refresh': False,
            'runtime_independently_authenticated': False,
            'io_limits': request['io_limits'],
            'statistical_limits': request['arguments']['statistical_limits'],
            'source_capture_bytes_from_manifest': self.source_capture_bytes,
            'source_plus_request_capture_bytes': capture_bytes,
            'request_cap_bytes': 2 * 1048576, 'source_capture_cap_bytes': 16 * 1048576,
            'refreshed_fixture_cap_bytes': 64 * 1048576,
            'grade_executed_by_refresh': False, 'authentic_or_native_data': False,
            'historical_parity': False, 'scientific_qualification': False,
            'guard_basis': 'conservative-unmeasured-prospective-campaign-limits',
            'automatic_retry_or_limit_enlargement': False}
        refresh_raw = packed_json(refresh)
        self.assertLessEqual(measurement['total_file_bytes'] + len(grade_raw) + len(refresh_raw),
                             64 * 1048576, 'complete retained fixture bound before refresh writes')
        for path, raw in ((grade_path, grade_raw),
                          (destination / 'GRADE_REQUEST_REFRESH.json', refresh_raw)):
            with path.open('xb') as handle:
                os.fchmod(handle.fileno(), 0o644)
                handle.write(raw)
        return destination, grade_path, grade_raw, refresh

    def _invoke(self, fixture, *, allow_protected):
        destination, request_path, request_raw, measurement = fixture
        protected = str(destination / 'protected') + os.sep
        grade_destination = destination / 'grade-result'
        opens = []
        original_open = os.open

        def guarded_open(path, flags, *args, **kwargs):
            absolute = str(Path(os.fsdecode(path)).absolute())
            if absolute.startswith(protected):
                opens.append(absolute)
                if not allow_protected:
                    raise AssertionError('Protected body opened before expected archive refusal')
                self.assertTrue((grade_destination / 'PRETARGET_CAPTURE.json').is_file(),
                                'actual pretarget barrier must exist before the first protected read')
            return original_open(path, flags, *args, **kwargs)

        error = None
        result = None
        with patch('os.open', guarded_open):
            try:
                result = self.adapter.run_operator(
                    ROOT, request_path, hashlib.sha256(request_raw).hexdigest(),
                    source_read_limit=measurement['source_plus_request_capture_bytes'])
            except Exception as caught:
                error = caught
        self.assertFalse(any(name.startswith('_nomad_recovered_') for name in sys.modules),
                         'owned captured scientific modules must close')
        return result, error, opens, grade_destination

    def _successful(self, fixture):
        result, error, opens, grade_destination = self._invoke(fixture, allow_protected=True)
        if error is not None:
            raise error
        self.assertTrue(opens)
        raw = (grade_destination / result['result']['path']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), result['result']['sha256'])
        terminal = json.loads(raw)
        self.assertFalse(result['historical_parity'])
        self.assertFalse(result['runtime_qualified'])
        for name in ('whole_original_study_complete', 'historical_parity', 'runtime_qualified'):
            self.assertFalse(terminal[name])
        actual = terminal['result']
        self.assertEqual(actual['local_archive_closure']['expected_count'], 2720)
        self.assertFalse(actual['original_native_reproduction_or_superiority_qualified'])
        stats = actual['statistical_outputs']
        self.assertEqual(stats['nominal_tests'], 102)
        self.assertEqual(len(stats['tests']), 102)
        self.assertEqual(len({test['test_id'] for test in stats['tests']}), 102)
        self.assertEqual(dict(Counter(test['group_id'].split('/')[0] for test in stats['tests'])),
                         {'F3_F4': 12, 'F5': 12, 'S1': 6, 'S3': 2, 'S5': 2,
                          'S7': 56, 'S8': 2, 'S9': 2, 'S12_historical': 2, 'S14': 6})
        main = [test for test in stats['tests'] if test['group_id'] in GROUPS]
        self.assertEqual(len(main), 12)
        originals = ('Static decoder', 'Aligned FA', 'ADAN', 'NoMAD')
        contrasts = [(originals[i], originals[j]) for i in range(4) for j in range(i)]
        for group in GROUPS:
            self.assertEqual([(test['first'], test['second']) for test in main
                              if test['group_id'] == group], contrasts)
        self.assertTrue(all('Candidate' not in (test['first'], test['second']) for test in stats['tests']))
        self.assertFalse(stats['original_parity'])
        self.assertFalse(stats['full_original_profile_complete'])
        panels = stats['candidate_comparisons']
        self.assertEqual([panel['group_id'] for panel in panels], list(GROUPS))
        for panel, count in zip(panels, (380, 132)):
            self.assertEqual(panel['candidate_method'], 'Candidate')
            self.assertEqual(panel['author_method'], 'NoMAD')
            self.assertEqual(panel['expected_pairs'], count)
            self.assertEqual(len(panel['paired_values']), count)
            self.assertEqual(len({row['pair_id'] for row in panel['paired_values']}), count)
            self.assertFalse(panel['superiority_qualified'])
        return stats, panels, actual

    def test_complete_panels_use_actual_pooled_metric_and_keep_original_hold(self):
        with self._case_folder() as folder:
            fixture = self._fixture(folder, original_mode=True)
            stats, panels, actual = self._successful(fixture)
            self.assertEqual(actual['local_archive_closure']['complete_count'], 2720)
            for panel, candidate, delta in zip(panels, (Fraction(49, 50), Fraction(41, 50)),
                                                (Fraction(3, 50), Fraction(-1, 10))):
                self.assertEqual(panel['status'], 'computed')
                self.assertEqual(panel['computed_pairs'], panel['expected_pairs'])
                self.assertEqual(panel['anchor_failures'], [])
                for row in panel['paired_values']:
                    self.assertEqual(exact(row['author']['value']['exact']), Fraction(23, 25))
                    self.assertEqual(exact(row['candidate']['value']['exact']), candidate)
                    self.assertEqual(exact(row['delta']['exact']), delta)
                    self.assertNotEqual(row['candidate']['query']['product_id'],
                                        row['author']['query']['product_id'])
            # Independent analytical oracle for these generated arrays. This is
            # not a historical runtime rerun or a comparison to empirical data.
            original_values = {'Static decoder': Fraction(17, 25),
                               'Aligned FA': Fraction(41, 50),
                               'ADAN': Fraction(7, 8), 'NoMAD': Fraction(23, 25)}
            pair_counts = dict(zip(GROUPS, (380, 132)))
            anchor_counts = dict(zip(GROUPS, (20, 12)))
            seen_pairs, seen_anchors = set(), set()
            for summary in stats['summaries']:
                group, method = summary['group_id'], summary['method']
                if group not in GROUPS:
                    continue
                self.assertIsNone(summary['quantiles'])
                if method not in original_values:
                    continue
                if summary['kind'] == 'all_complete_group_pairs':
                    seen_pairs.add((group, method))
                    self.assertEqual(summary['expected'], pair_counts[group])
                    self.assertEqual(summary['computed'], pair_counts[group])
                    self.assertEqual(summary['failures'], [])
                    self.assertEqual(len(summary['full_pair_values']), pair_counts[group])
                    for row in summary['full_pair_values']:
                        self.assertEqual(row['method'], method)
                        self.assertEqual(exact(row['value']['exact']), original_values[method])
                elif summary['kind'] == 'anchors':
                    seen_anchors.add((group, method))
                    self.assertEqual(summary['expected'], anchor_counts[group])
                    self.assertEqual(summary['computed'], anchor_counts[group])
                    self.assertEqual(summary['failures'], [])
                    self.assertEqual(summary['outcome_counts']['positive'], anchor_counts[group])
                    self.assertEqual(summary['outcome_counts']['unavailable'], 0)
            expected_summaries = {(group, method) for group in GROUPS for method in original_values}
            self.assertEqual(seen_pairs, expected_summaries)
            self.assertEqual(seen_anchors, expected_summaries)
            for test in stats['tests']:
                if test['group_id'] not in GROUPS:
                    continue
                self.assertEqual(test['status'], 'unavailable_historical_statistical_profile')
                count = pair_counts[test['group_id']]
                self.assertEqual(test['expected_pairs'], count)
                self.assertEqual(test['computed_pairs'], count)
                self.assertEqual(test['invalid_pairs'], [])
                self.assertEqual(len(test['paired_values']), count)
                self.assertEqual(len(test['differences']), count)
                first, second = original_values[test['first']], original_values[test['second']]
                for paired, difference in zip(test['paired_values'], test['differences']):
                    self.assertEqual(paired['pair_id'], difference['pair_id'])
                    self.assertEqual(paired['first']['method'], test['first'])
                    self.assertEqual(paired['second']['method'], test['second'])
                    self.assertEqual(exact(paired['first']['value']['exact']), first)
                    self.assertEqual(exact(paired['second']['value']['exact']), second)
                    self.assertEqual(exact(difference['value']['exact']), first - second)

    def test_equal_bytes_distinct_arms_and_reverse_capture_order(self):
        with self._case_folder() as folder:
            fixture = self._fixture(folder, scenario='equal', reverse_products=True)
            _, panels, _ = self._successful(fixture)
            for panel in panels:
                self.assertEqual(panel['status'], 'computed')
                for row in panel['paired_values']:
                    self.assertEqual(exact(row['delta']['exact']), 0)
                    self.assertNotEqual(row['candidate']['query']['product_id'],
                                        row['author']['query']['product_id'])

    def test_panel_median_difference_is_not_median_pair_difference(self):
        with self._case_folder() as folder:
            fixture = self._fixture(folder, scenario='median_trap')
            stats, panels, _ = self._successful(fixture)
            for panel in panels:
                medians = {}
                for summary in stats['summaries']:
                    if (summary['group_id'] == panel['group_id']
                            and summary['kind'] == 'all_complete_group_pairs'
                            and summary['method'] in ('NoMAD', 'Candidate')):
                        medians[summary['method']] = exact(
                            summary['quantiles']['values']['median']['exact'])
                self.assertEqual(medians['Candidate'] - medians['NoMAD'], Fraction(2, 25))
                differences = [exact(row['delta']['exact']) for row in panel['paired_values']]
                self.assertEqual(statistics.median(differences), 0)
                self.assertNotEqual(medians['Candidate'] - medians['NoMAD'],
                                    statistics.median(differences))

    def test_candidate_anchor_failure_and_nonfinite_query_remain_in_slots(self):
        with self._case_folder() as folder:
            fixture = self._fixture(folder, mutation='failed_and_nonfinite')
            _, panels, actual = self._successful(fixture)
            self.assertEqual(actual['local_archive_closure']['complete_count'], 2719)
            self.assertEqual(len(actual['local_archive_closure']['failed_attempts']), 1)
            self.assertEqual(panels[0]['status'], 'unavailable_incomplete_paired_values_or_anchors')
            self.assertEqual(panels[0]['computed_pairs'], 379)
            self.assertTrue(panels[0]['anchor_failures'])
            failed_pairs = [row for row in panels[0]['paired_values'] if row['delta'] is None]
            self.assertEqual(len(failed_pairs), 1)
            self.assertEqual(failed_pairs[0]['candidate']['query']['status'], 'invalid_nonfinite_prediction')
            self.assertEqual(panels[1]['status'], 'computed')
            self.assertEqual(panels[1]['computed_pairs'], 132)

    def _assert_pretarget_refusal(self, mutation):
        with self._case_folder() as folder:
            fixture = self._fixture(folder, mutation=mutation)
            result, error, opens, grade_destination = self._invoke(fixture, allow_protected=False)
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            self.assertRegex(str(error), NEGATIVE_MESSAGES[mutation])
            self.assertEqual(opens, [])
            prefix = getattr(error, 'nomad_failure_prefix', None)
            self.assertIsNotNone(prefix, 'must exercise actual grade refusal, not startup/request failure')
            self.assertEqual(prefix['protected_target_captures'], [])
            self.assertFalse((grade_destination / 'PRETARGET_CAPTURE.json').exists())
            self.assertTrue((grade_destination / 'FAILURE.json').is_file())

    def test_missing_pair_fact_refuses_before_target(self):
        self._assert_pretarget_refusal('missing_pair_fact')

    def test_duplicate_pair_fact_refuses_before_target(self):
        self._assert_pretarget_refusal('duplicate_pair_fact')

    def test_missing_anchor_selector_refuses_before_target(self):
        self._assert_pretarget_refusal('missing_anchor_selector')

    def test_duplicate_anchor_reference_refuses_before_target(self):
        self._assert_pretarget_refusal('duplicate_anchor_reference')

    def test_wrong_anchor_role_refuses_before_target(self):
        self._assert_pretarget_refusal('wrong_anchor_role')

    def test_candidate_profile_mismatch_refuses_before_target(self):
        self._assert_pretarget_refusal('candidate_profile_mismatch')

    def test_product_id_alias_refuses_before_target(self):
        self._assert_pretarget_refusal('product_id_alias')

    def test_candidate_label_collision_refuses_before_target(self):
        self._assert_pretarget_refusal('candidate_label_collision')

    def test_missing_candidate_panel_refuses_before_target(self):
        self._assert_pretarget_refusal('missing_candidate_panel')

    def test_query_support_mismatch_refuses_before_target(self):
        self._assert_pretarget_refusal('query_support_mismatch')

    def test_anchor_sample_mismatch_refuses_before_target(self):
        self._assert_pretarget_refusal('anchor_sample_mismatch')

    def test_anchor_axis_mismatch_refuses_before_target(self):
        self._assert_pretarget_refusal('anchor_axis_mismatch')


if __name__ == '__main__':
    unittest.main()
