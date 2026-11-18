"""Generated semantic and failure controls; no authentic source payloads."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("audit_export", Path(__file__).with_name("audit_export.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def documents():
    inventory = {"schema": "physiop300_recording_inventory_v1", "recordings": []}
    captures = {"schema": "physiop300_converter_epoch_metadata_v1",
                "converter_source_sha256": audit.CONVERTER_SHA256, "recordings": []}
    for subject in audit.PROBE_SUBJECTS:
        rid = f"subject-{subject}/recording-1"
        source_hash = str(int(subject) % 10) * 64
        inventory["recordings"].append({"recording_id": rid, "subject_id": subject,
                                        "source_member": f"s{subject}/r1.edf", "source_bytes": 100,
                                        "source_sha256": source_hash})
        if subject == "1":
            continue
        captures["recordings"].append({"recording_id": rid, "source_sha256": source_hash,
            "event_id": {"#TgtP_RC01_SOA63": 1, "#start": 2, "MNOPQR": 3, "ABCDEF": 4, "#end": 5},
            "events": [[0, 0, 1], [100, 0, 2], [200, 0, 3], [300, 0, 4], [400, 0, 5]],
            "selection": [1, 2, 3], "drop_log": [["NO_DATA"], [], [], [], ["TOO_SHORT"]]})
    captures["inventory_commitment"] = audit.commitment(inventory)
    return inventory, captures


class ExportAuditTests(unittest.TestCase):
    def test_filename_uses_retained_epoch_ordinal_not_original_index(self):
        inv, cap = documents()
        out = audit.audit_export(inv, cap)
        first = out["intended_writes"][0]
        self.assertEqual((first["original_event_index"], first["retained_epoch_ordinal"]), (2, 1))
        self.assertEqual(first["legacy_output_key"], "1/1.sub2")
        self.assertEqual(out["unvisited_probe_recordings"], ["subject-1/recording-1"])
        self.assertEqual(len(out["dropped_original_events"]), 16)
        self.assertFalse(out["scientific_readiness"])
        self.assertIsNone(out["historical_surviving_events"])

    def test_two_recordings_collide_without_inventing_winner(self):
        inv, cap = documents()
        second = copy.deepcopy(inv["recordings"][1])
        second.update(recording_id="subject-2/recording-2", source_member="s2/r2.edf", source_sha256="e"*64)
        inv["recordings"].append(second)
        obs = copy.deepcopy(cap["recordings"][0])
        obs.update(recording_id=second["recording_id"], source_sha256=second["source_sha256"])
        cap["recordings"].append(obs)
        cap["inventory_commitment"] = audit.commitment(inv)
        out = audit.audit_export(inv, cap)
        self.assertEqual(len(out["colliding_output_keys"]), 2)
        self.assertEqual(out["displaced_writes_if_all_writes_completed"], 2)
        self.assertEqual(len(out["intended_writes"]), 18)
        self.assertIsNone(out["historical_surviving_events"])

    def test_class_directory_changes_collision_identity(self):
        inv, cap = documents()
        extra = copy.deepcopy(inv["recordings"][1])
        extra.update(recording_id="other", source_member="s2/other.edf")
        inv["recordings"].append(extra)
        obs = copy.deepcopy(cap["recordings"][0])
        obs["recording_id"] = "other"
        obs["event_id"] = {"#TgtA_RC02_SOA63": 1, "#start": 2, "MNOPQR": 3, "ABCDEF": 4, "#end": 5}
        cap["recordings"].append(obs)
        cap["inventory_commitment"] = audit.commitment(inv)
        self.assertEqual(audit.audit_export(inv, cap)["colliding_output_keys"], [])

    def test_drop_log_and_selection_must_agree(self):
        inv, cap = documents()
        cap["recordings"][0]["drop_log"][2] = ["USER"]
        with self.assertRaisesRegex(audit.Refusal, "contradiction"):
            audit.audit_export(inv, cap)

    def test_missing_or_extra_recording_refused(self):
        for mutation in ("missing", "extra"):
            with self.subTest(mutation=mutation):
                inv, cap = documents()
                if mutation == "missing":
                    cap["recordings"].pop()
                else:
                    extra = copy.deepcopy(cap["recordings"][0])
                    extra["recording_id"] = inv["recordings"][0]["recording_id"]
                    cap["recordings"].append(extra)
                with self.assertRaises(audit.Refusal):
                    audit.audit_export(inv, cap)

    def test_missing_ninth_inventory_token_is_not_silently_accepted(self):
        inv, cap = documents()
        inv["recordings"].pop(0)
        cap["inventory_commitment"] = audit.commitment(inv)
        with self.assertRaisesRegex(audit.Refusal, "nine"):
            audit.audit_export(inv, cap)

    def test_mismatched_recording_and_inventory_commitments_refused(self):
        for field in ("source_sha256", "inventory_commitment", "converter_source_sha256"):
            with self.subTest(field=field):
                inv, cap = documents()
                if field == "source_sha256":
                    cap["recordings"][0][field] = "f"*64
                else:
                    cap[field] = "f"*64
                with self.assertRaises(audit.Refusal):
                    audit.audit_export(inv, cap)

    def test_ambiguous_target_refused_instead_of_dictionary_order_choice(self):
        inv, cap = documents()
        cap["recordings"][0]["event_id"]["#TgtQ_RC02_SOA63"] = 6
        with self.assertRaisesRegex(audit.Refusal, "exactly one target"):
            audit.audit_export(inv, cap)

    def test_duplicate_samples_may_exist_only_before_drop(self):
        inv, cap = documents()
        record = cap["recordings"][0]
        record["events"][3][0] = record["events"][2][0]
        with self.assertRaisesRegex(audit.Refusal, "duplicate sample"):
            audit.audit_export(inv, cap)
        record["selection"] = [1, 2]
        record["drop_log"][3] = ["DROP DUPLICATE"]
        out = audit.audit_export(inv, cap)
        self.assertTrue(any(x["reasons"] == ["DROP DUPLICATE"] for x in out["dropped_original_events"]))

    def test_bad_index_boolean_and_unknown_event_code_refused(self):
        for mutation in ("outside", "boolean", "unmapped", "reordered"):
            with self.subTest(mutation=mutation):
                inv, cap = documents()
                record = cap["recordings"][0]
                if mutation == "outside": record["selection"] = [1, 2, 99]
                elif mutation == "boolean": record["selection"] = [True, 2, 3]
                elif mutation == "unmapped": record["events"][2][2] = 99
                else: record["selection"] = [3, 2, 1]
                with self.assertRaises(audit.Refusal): audit.audit_export(inv, cap)

    def test_later_duplicate_cannot_replace_first_event(self):
        inv, cap = documents()
        record = cap["recordings"][0]
        record["events"][3][0] = record["events"][2][0]
        record["selection"] = [1, 3]
        record["drop_log"][2] = ["DROP DUPLICATE"]
        with self.assertRaisesRegex(audit.Refusal, "first row"):
            audit.audit_export(inv, cap)

    def test_duplicate_json_keys_and_nonfinite_refused(self):
        for value in (b'{"a":1,"a":2}', b'{"a":NaN}'):
            with self.assertRaises(audit.Refusal): audit.decode(value)

    def test_permuted_recording_order_cannot_claim_historical_survivor(self):
        inv, cap = documents()
        cap["recordings"].reverse()
        result = audit.audit_export(inv, cap)
        self.assertEqual(result["unique_legacy_output_keys"], 16)
        self.assertIsNone(result["historical_surviving_events"])
        self.assertFalse(result["historical_converter_execution_verified"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
