"""Generated metadata controls; no EEG or fitted-regressor values are used."""
import copy
import json
import unittest

from lineage import (ORIGINAL_KEYS, SOURCE_COMMIT, audit_lineage, read_document)


def fixture(stage="second_choice", omitted=()):
    omitted = set(omitted)
    keys = list(ORIGINAL_KEYS)
    selected = [i for i in range(len(keys)) if i not in omitted]
    code = {"first_choice": "0024", "first_result": "0003",
            "second_choice": "0025", "second_result": "0006"}[stage]
    events = [{"participant_id": keys[i][0], "trial_index": keys[i][1],
               "event_index": 5 * i + 3, "event_code": code} for i in selected]
    return {
        "schema_version": "freeenergy-neural-lineage/v1",
        "task_id": "PAPER-FIND-037", "source_commit": SOURCE_COMMIT,
        "stage": stage,
        "behavior_rows": [{"participant_id": p, "trial_index": t} for p, t in keys],
        "selected_behavior_indices": selected,
        "response_events": events,
        "covariance_events": copy.deepcopy(events),
        "omissions": [{"behavior_index": i, "participant_id": keys[i][0],
                       "trial_index": keys[i][1], "reason": "epoch_rejection",
                       "evidence_sha256": "a" * 64} for i in sorted(omitted)],
    }


class LineageTests(unittest.TestCase):
    def test_complete_original_reference_each_stage(self):
        for stage in ("first_choice", "first_result", "second_choice", "second_result"):
            with self.subTest(stage=stage):
                out = audit_lineage(fixture(stage))
                self.assertEqual(out["reference_trials"], 2760)
                self.assertEqual(out["aligned_response_events"], 2760)
                self.assertEqual(out["covariance_events"], 2760)
                self.assertTrue(out["windows_have_identical_event_support"])
                self.assertFalse(out["authentic_data_identity_verified"])
                self.assertFalse(out["scientific_reproduction_verified"])
                self.assertFalse(out["readiness_promoted"])

    def test_equal_count_wrong_trial_is_rejected(self):
        doc = fixture()
        doc["response_events"][0]["trial_index"] = 1
        doc["covariance_events"][0]["trial_index"] = 1
        with self.assertRaisesRegex(ValueError, "regressor rows exactly"):
            audit_lineage(doc)

    def test_covariance_support_difference_is_reported_without_repair(self):
        for edit in ("delete", "different_annotation"):
            with self.subTest(edit=edit):
                doc = fixture("second_result")
                if edit == "delete":
                    doc["covariance_events"].pop()
                else:
                    doc["covariance_events"][0]["event_index"] += 1
                unchanged = copy.deepcopy(doc)
                out = audit_lineage(doc)
                self.assertFalse(out["windows_have_identical_event_support"])
                self.assertEqual(out["aligned_response_events"], 2760)
                self.assertEqual(out["response_only_event_count"], 1)
                self.assertEqual(out["covariance_only_event_count"],
                                 int(edit == "different_annotation"))
                self.assertEqual(doc, unchanged)

    def test_shared_original_event_cannot_change_trial_or_code(self):
        for field, value in (("trial_index", 1), ("event_code", "0007"),
                             ("participant_id", 2)):
            with self.subTest(field=field):
                doc = fixture("second_result")
                doc["covariance_events"][0][field] = value
                with self.assertRaises(ValueError):
                    audit_lineage(doc)

    def test_literal_719_bound_to_declared_biological_identity(self):
        doc = fixture("second_result", omitted=(719,))
        doc["omissions"][0]["reason"] = "source_literal_719"
        out = audit_lineage(doc)
        self.assertEqual(out["literal_source_deletion_identities"],
                         [{"behavior_index": 719, "participant_id": 8,
                           "trial_index": 119}])
        self.assertFalse(out["omission_reasons_independently_verified"])
        doc["omissions"][0]["participant_id"] = 9
        with self.assertRaisesRegex(ValueError, "wrong participant/trial"):
            audit_lineage(doc)

    def test_literal_deletion_cannot_be_reused_on_another_stage(self):
        doc = fixture("first_choice", omitted=(719,))
        doc["omissions"][0]["reason"] = "source_literal_719"
        with self.assertRaisesRegex(ValueError, "second-result"):
            audit_lineage(doc)

    def test_all_omissions_must_be_declared_once_with_identity(self):
        doc = fixture("first_choice", omitted=(0, 4, 2000))
        out = audit_lineage(doc)
        self.assertEqual(out["omission_counts"], {"epoch_rejection": 3})
        for edit in ("missing", "duplicate", "bad_evidence", "unknown_reason"):
            with self.subTest(edit=edit):
                bad = copy.deepcopy(doc)
                if edit == "missing":
                    bad["omissions"].pop()
                elif edit == "duplicate":
                    bad["omissions"].append(copy.deepcopy(bad["omissions"][0]))
                elif edit == "bad_evidence":
                    bad["omissions"][0]["evidence_sha256"] = "unverified"
                else:
                    bad["omissions"][0]["reason"] = "convenient_outlier"
                with self.assertRaises(ValueError):
                    audit_lineage(bad)

    def test_original_cohort_and_order_not_replaceable(self):
        for edit in ("swap", "missing", "extra_person", "bool_trial"):
            with self.subTest(edit=edit):
                doc = fixture()
                if edit == "swap":
                    doc["behavior_rows"][0], doc["behavior_rows"][120] = (
                        doc["behavior_rows"][120], doc["behavior_rows"][0])
                elif edit == "missing":
                    doc["behavior_rows"].pop()
                elif edit == "extra_person":
                    doc["behavior_rows"][0]["participant_id"] = 2
                else:
                    doc["behavior_rows"][0]["trial_index"] = False
                with self.assertRaises(ValueError):
                    audit_lineage(doc)

    def test_selected_indices_and_event_grammar(self):
        for edit in ("duplicate_selection", "permuted_selection", "bool_index",
                     "unknown_code", "duplicate_event", "negative_event"):
            with self.subTest(edit=edit):
                doc = fixture()
                if edit == "duplicate_selection":
                    doc["selected_behavior_indices"][1] = 0
                elif edit == "permuted_selection":
                    doc["selected_behavior_indices"][:2] = [1, 0]
                elif edit == "bool_index":
                    doc["selected_behavior_indices"][0] = False
                elif edit == "unknown_code":
                    doc["response_events"][0]["event_code"] = "boundary"
                elif edit == "duplicate_event":
                    doc["response_events"][1]["event_index"] = 3
                else:
                    doc["response_events"][0]["event_index"] = -1
                with self.assertRaises(ValueError):
                    audit_lineage(doc)

    def test_strict_transport_version_and_fields(self):
        for body in (b'{"x": 1, "x": 2}', b'{"x": NaN}'):
            with self.assertRaises(ValueError):
                read_document(body)
        doc = fixture()
        parsed = read_document(json.dumps(doc).encode())
        self.assertEqual(audit_lineage(parsed)["reference_trials"], 2760)
        for key, value in (("source_commit", "another-version"),
                           ("task_id", "another-task"),
                           ("schema_version", "v0"), ("stage", [])):
            bad = copy.deepcopy(doc)
            bad[key] = value
            with self.assertRaises(ValueError):
                audit_lineage(bad)


if __name__ == "__main__":
    unittest.main()
