"""Invented-only wrapper/information-boundary controls; no scientific fits."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import types
import unittest

import task
import participant_core as core
import released_profile as profile
import grader
import episode_boundary as boundary


def invented():
    trials = []
    for animal in range(3):
        for index in range(50):
            trials.append({"animal": f"INVENTED_ANIMAL_{animal}",
                "session": f"INVENTED_SESSION_{animal}", "trial": index,
                "target": 2*(animal+1), "spikes": [[index%3]*90], "units": [0],
                "old_flags_owner_only": {0: []}, "diagnostic_reference_owner_only": {}})
    return {c: profile.invented_packet(trials, bytes(range(32)), c) for c in core.CONDITIONS}


class PortableControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.budget = task.budget()

    def write(self, name, value):
        path = self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(core.canonical(value))
        return path

    def test_duplicate_json_keys_refused(self):
        path = self.root/'bad.json'; path.write_bytes(b'{"x":1,"x":2}')
        with self.assertRaises(ValueError): task.read_json(path, self.budget)

    def test_nonfinite_json_constant_refused(self):
        path = self.root/'bad.json'; path.write_bytes(b'{"x":NaN}')
        with self.assertRaises(ValueError): task.read_json(path, self.budget)

    def test_whole_file_bound_refuses_before_decode(self):
        path = self.write('large.json', {"x": 'a'*100})
        with self.assertRaises(ValueError): task.read_json(path, self.budget, 32)
        self.assertEqual(self.budget.used['input_bytes'], 0)

    def test_wrong_whole_hash_refused(self):
        path = self.write('input.json', {"x": 1})
        with self.assertRaises(ValueError):
            task.read_json(path, self.budget, expected={"bytes": path.stat().st_size, "sha256": '0'*64})

    def test_symlink_input_refused(self):
        target = self.write('input.json', {"x": 1}); link = self.root/'link.json'; link.symlink_to(target)
        with self.assertRaises(ValueError): task.read_json(link, self.budget)

    def test_hardlink_input_refused(self):
        target = self.write('input.json', {"x": 1}); link = self.root/'link.json'; os.link(target, link)
        with self.assertRaises(ValueError): task.read_json(link, self.budget)

    def test_existing_output_is_never_overwritten(self):
        path = self.write('output.json', {"old": 1})
        with self.assertRaises(FileExistsError): task.write_json(path, {"new": 1}, self.budget)
        self.assertEqual(json.loads(path.read_text()), {"old": 1})

    def test_manifest_requires_external_frozen_hash(self):
        root = task.fresh_directory(self.root/'bundle')
        body = {"schema": "invented-manifest", "profile": profile.PROFILE}
        pin = task.write_json(root/'BUNDLE.json', body, self.budget)
        self.assertEqual(task.manifest_at(root, 'BUNDLE.json', pin['sha256'], self.budget, 'invented-manifest'), body)
        with self.assertRaises(ValueError): task.manifest_at(root, 'BUNDLE.json', '0'*64, self.budget, 'invented-manifest')

    def test_unfrozen_predictions_refused_before_any_owner_input(self):
        root = task.fresh_directory(self.root/'bundle')
        bundle = {"schema": "apcx-portable-private-bundle-v1", "profile": profile.PROFILE,
            "members": {n: {"bytes": 1, "sha256": '0'*64} for n in task.PROFILE_FILES},
            "remaining_holds": list(core.HOLDS)}
        bundle_pin = task.write_json(root/'BUNDLE.json', bundle, self.budget)
        frozen = task.fresh_directory(self.root/'frozen')
        frozen_pin = task.write_json(frozen/'FROZEN.json', {"schema": "apcx-complete-frozen-submissions-v1",
            "profile": profile.PROFILE}, self.budget)
        args = types.SimpleNamespace(bundle=root, bundle_sha256=bundle_pin['sha256'],
            submissions=frozen, frozen_sha256='0'*64, output=self.root/'output')
        # Owner files deliberately do not exist: an early owner read fails this
        # test with FileNotFoundError instead of the required manifest rejection.
        with self.assertRaisesRegex(ValueError, 'trusted manifest identity'):
            task.score(args, self.budget)
        self.assertEqual(self.budget.used['input_bytes'], bundle_pin['bytes']+frozen_pin['bytes'])
        self.assertFalse(args.output.exists())

    def test_converter_rejects_wrong_provision_size_without_body_read(self):
        cfg = task.config(); name = 'PARTICIPANT_MATCHED.json'
        path = self.write(name, {"fake": True})
        with self.assertRaises(ValueError): task.read_bytes(path, self.budget, task.MAX_DOCUMENT, cfg['accepted_profile_inputs'][name])
        self.assertEqual(self.budget.used['input_bytes'], 0)

    def test_invented_subset_cannot_become_authentic_bundle(self):
        values = invented()
        with self.assertRaises(ValueError): task.audit_pair({c: p for c,(p,o) in values.items()})

    def test_query_label_injection_refused(self):
        packet, _ = invented()['matched']; e = boundary.from_public_packet(packet)[0]
        e['session']['queries'][0]['count'] = 3
        with self.assertRaises(ValueError): boundary.validate_episode(e)

    def test_duplicate_query_identity_refused(self):
        packet, _ = invented()['matched']; e = boundary.from_public_packet(packet)[0]
        e['session']['queries'][1]['case_id'] = e['session']['queries'][0]['case_id']
        with self.assertRaises(ValueError): boundary.validate_episode(e)

    def test_missing_prediction_has_no_aggregate(self):
        packet, owner = invented()['matched']
        records = [{"case_id": c['case_id'], "count": c['count']} for c in owner['cases']][:-1]
        report = grader.grade(owner, profile.submission(packet, records))
        self.assertIsNone(report['primary_metric'])
        self.assertEqual(report['status'], 'INCOMPLETE_OR_INVALID_NO_AGGREGATE_SCORE')

    def test_cross_condition_submission_refused(self):
        values = invented(); packet, owner = values['matched']
        records = [{"case_id": c['case_id'], "count": c['count']} for c in owner['cases']]
        report = grader.grade(values['full_calibration'][1], profile.submission(packet, records))
        self.assertIsNone(report['primary_metric'])

    def response_fixture(self):
        values = invented(); packets = {c: p for c,(p,o) in values.items()}
        root = self.root/'responses'; root.mkdir()
        for condition in core.CONDITIONS:
            (root/condition).mkdir()
            owner = values[condition][1]
            cases = {r['case_id']: r for r in owner['cases']}
            for episode in boundary.from_public_packet(packets[condition]):
                records = []
                for row in episode['session']['queries']:
                    target = cases[row['case_id']]['count']
                    records.append({"case_id": row['case_id'], "count": target + target/2})
                response = {"schema": 'apcx-candidate-session-result-v1', "profile": profile.PROFILE,
                    "condition": condition, "session_id": episode['session']['session_id'],
                    "participant_packet_sha256": episode['participant_packet_sha256'],
                    "episode_sha256": boundary.digest(episode), "records": records}
                self.write('responses/'+condition+'/'+episode['session']['session_id']+'.json', response)
        return values, packets, root

    def test_complete_small_response_join_has_independent_macro_answer(self):
        values, packets, root = self.response_fixture()
        responses = task.complete_responses(root, packets, self.budget)
        for condition in core.CONDITIONS:
            records = [r for response in responses[condition].values() for r in response['records']]
            packet, owner = values[condition]
            report = grader.grade(owner, profile.submission(packet, records))
            # Three constant-target animals have RMSE1,2,3 respectively: mean2.
            self.assertEqual(report['primary_metric']['value'], 2.0)
            self.assertEqual(report['required_cases'], 30)

    def test_missing_response_file_refuses_whole_collection(self):
        _, packets, root = self.response_fixture()
        next((root/'matched').iterdir()).unlink()
        with self.assertRaises(ValueError): task.complete_responses(root, packets, self.budget)

    def test_extra_response_file_refuses_whole_collection(self):
        _, packets, root = self.response_fixture()
        self.write('responses/matched/extra.json', {})
        with self.assertRaises(ValueError): task.complete_responses(root, packets, self.budget)

    def test_wrong_episode_hash_refuses_replayed_response(self):
        _, packets, root = self.response_fixture()
        path = next((root/'matched').iterdir()); x = json.loads(path.read_text()); x['episode_sha256'] = '0'*64
        path.write_bytes(core.canonical(x))
        with self.assertRaises(ValueError): task.complete_responses(root, packets, self.budget)

    def test_boolean_prediction_refused(self):
        _, packets, root = self.response_fixture()
        path = next((root/'matched').iterdir()); x = json.loads(path.read_text()); x['records'][0]['count'] = True
        path.write_bytes(core.canonical(x))
        with self.assertRaises(ValueError): task.complete_responses(root, packets, self.budget)

    def test_physical_primary_cannot_be_relabelled_ready(self):
        with self.assertRaises(core.ScientificHold): core.build_authentic_packet(ready=True)
        self.assertEqual(grader.evaluate_physical_primary()['remaining_holds'], list(core.HOLDS))


if __name__ == '__main__':
    unittest.main()
