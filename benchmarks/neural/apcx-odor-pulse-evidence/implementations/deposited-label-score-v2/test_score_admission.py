"""Generated-only score-entrypoint controls; no authentic packets or targets."""
import copy
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

import task
import participant_core as core
import released_profile as profile
from test_task import invented


class PublicSubmissionAdmission(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        values = invented()
        self.packets = {condition: pair[0] for condition, pair in values.items()}
        # Predictions depend only on the public query roster, never owner labels.
        self.submissions = {
            condition: profile.submission(packet, [
                {"case_id": row["case_id"], "count": 0.0}
                for session in packet["sessions"] for row in session["queries"]
            ]) for condition, packet in self.packets.items()
        }
        self.owner_reads = []

    def run_score(self, submissions=None, methods=None, selection_mutator=None):
        submissions = self.submissions if submissions is None else submissions
        methods = ["candidate"] if methods is None else methods
        budget = task.budget()
        bundle = task.fresh_directory(self.root/'bundle')
        bundle_pin = task.write_json(bundle/'BUNDLE.json', {
            "schema": "apcx-portable-private-bundle-v1", "profile": profile.PROFILE,
            "members": {name: {"bytes": 1, "sha256": '0'*64} for name in task.PROFILE_FILES},
            "remaining_holds": list(core.HOLDS)}, budget)
        frozen = task.fresh_directory(self.root/'frozen')
        members = {}
        selections = {}
        for condition in core.CONDITIONS:
            for method in methods:
                name = f'{condition}__{method}.json'
                members[name] = task.write_json(frozen/name, submissions[condition], budget)
            if methods != ["candidate"]:
                selection = {
                    "schema": "apcx-complete-condition-reference-selection-v1",
                    "condition": condition,
                    "participant_packet_sha256": core.digest(self.packets[condition]),
                    "submissions": {method: submissions[condition] for method in methods},
                }
                if selection_mutator:
                    selection_mutator(condition, selection)
                selections[condition] = task.write_json(
                    frozen/f'REFERENCE_SELECTION_{condition}.json', selection, budget)
        frozen_pin = task.write_json(frozen/'FROZEN.json', {
            "schema": "apcx-complete-frozen-submissions-v1", "profile": profile.PROFILE,
            "methods": methods, "conditions": list(core.CONDITIONS),
            "bundle_sha256": bundle_pin["sha256"], "members": members,
            "reference_selection_pins": selections}, budget)
        args = types.SimpleNamespace(bundle=bundle, bundle_sha256=bundle_pin['sha256'],
            submissions=frozen, frozen_sha256=frozen_pin['sha256'], output=self.root/'scores')
        actual_read = task.read_json

        def observe_read(path, *a, **kw):
            if Path(path).name.startswith('OWNER_'):
                self.owner_reads.append(Path(path).name)
                raise RuntimeError('OWNER_READ_SENTINEL')
            return actual_read(path, *a, **kw)

        # Only replace full authentic cohort loading: the generated packet keeps
        # its explicit invented flag and still receives normal profile validation.
        with mock.patch.object(task, 'load_packets', return_value=self.packets), \
                mock.patch.object(task, 'read_json', side_effect=observe_read):
            return task.score(args, budget)

    def assert_refused_before_targets(self, mutate, methods=None):
        submissions = copy.deepcopy(self.submissions)
        mutate(submissions['full_calibration'])
        with self.assertRaises(ValueError):
            self.run_score(submissions, methods)
        self.assertEqual(self.owner_reads, [])
        self.assertFalse((self.root/'scores').exists())

    def test_hash_valid_missing_last_condition_query_refused_before_targets(self):
        self.assert_refused_before_targets(lambda s: s['records'].pop())

    def test_hash_valid_duplicate_query_refused_before_targets(self):
        self.assert_refused_before_targets(lambda s: s['records'].__setitem__(0, copy.deepcopy(s['records'][1])))

    def test_hash_valid_unknown_query_refused_before_targets(self):
        self.assert_refused_before_targets(lambda s: s['records'][0].update(case_id='f'*64))

    def test_hash_valid_cross_condition_envelope_refused_before_targets(self):
        self.assert_refused_before_targets(lambda s: s.update(condition='matched'))

    def test_hash_valid_cross_packet_replay_refused_before_targets(self):
        self.assert_refused_before_targets(lambda s: s.update(participant_packet_sha256='0'*64))

    def test_hash_valid_altered_profile_document_refused_before_targets(self):
        self.assert_refused_before_targets(lambda s: s.update(profile_document_sha256='0'*64))

    def test_hash_valid_boolean_count_refused_before_targets(self):
        self.assert_refused_before_targets(lambda s: s['records'][0].update(count=True))

    def test_hash_valid_overflow_integer_refused_before_targets(self):
        self.assert_refused_before_targets(lambda s: s['records'][0].update(count=10**400))

    def test_hash_valid_partial_probability_column_refused_before_targets(self):
        self.assert_refused_before_targets(lambda s: s['records'][0].update(prob_high=0.5))

    def test_hash_valid_reference_missing_query_refused_before_targets(self):
        self.assert_refused_before_targets(lambda s: s['records'].pop(), list(task.reference_protocol.METHODS))

    def test_hash_valid_reference_wrong_condition_refused_before_targets(self):
        def mutate(condition, selection):
            if condition == 'full_calibration':
                selection['condition'] = 'matched'
        with self.assertRaises(ValueError):
            self.run_score(methods=list(task.reference_protocol.METHODS), selection_mutator=mutate)
        self.assertEqual(self.owner_reads, [])

    def test_complete_valid_predictions_reach_later_owner_phase(self):
        with self.assertRaisesRegex(RuntimeError, '^OWNER_READ_SENTINEL$'):
            self.run_score()
        self.assertEqual(self.owner_reads, ['OWNER_MATCHED.json'])

    def test_complete_optional_probabilities_and_negative_counts_are_preserved(self):
        for submission in self.submissions.values():
            for row in submission['records']:
                row.update(count=-2.5, prob_high=0.25)
        with self.assertRaisesRegex(RuntimeError, '^OWNER_READ_SENTINEL$'):
            self.run_score()
        self.assertEqual(self.owner_reads, ['OWNER_MATCHED.json'])
        self.assertTrue(all(row['count'] == -2.5 for s in self.submissions.values() for row in s['records']))


if __name__ == '__main__':
    unittest.main()
