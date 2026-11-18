"""Generated public controls; no original data or NumPy is read or imported."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("binding", HERE / "source_record_binding.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def text(value):
    return {"t": "str", "v": value}


def fixture():
    files, records = [], []
    def asset(name, size):
        for row in files:
            if row["name"] == name:
                return row
        aid = 100 + len(files)
        row = {"id": aid, "name": name, "size": size,
               "download_url": "https://ndownloader.figshare.com/files/" + str(aid)}
        files.append(row)
        return row
    groups = [("unsup_test3", [0, 1]), ("sup_train1_before_learning", [2])]
    for i in range(3):
        group = groups[0][0] if i < 2 else groups[1][0]
        mouse = "A" if i < 2 else "B"
        stem = mouse + "_2022_01_01_1"
        fields = {"mname": text(mouse), "datexp": text("2022_01_01"), "blk": text("1"),
                  "rewType": text("None" if i < 2 else "Passive"),
                  "stim_id": {"t": "ndarray", "items": [
                      {"t": "ieee_nonfinite", "classification": "nan", "raw_hex": "010000000000f87f",
                       "width_bytes": 8, "byteorder": "<", "signbit": 0}]},
                  "unknown_optional_field": {"t": "tuple", "items": [{"t": "none"}]}}
        if i < 2:
            fields["stimtype"] = text("swap" + str(i + 1))
        records.append({"ordinal": i, "source_group": text(group),
                        "source_pointer": ["group", text(group), "index", i if i < 2 else 0],
                        "fields": fields, "group_metadata": None, "candidate_session_stem": stem,
                        "neural_asset": asset(stem + "_neural_data.npy", 1000),
                        "transform_asset": asset(mouse + "_2022_01_01_trans.npz", 10),
                        "behavior_container_asset": asset("Beh_" + group + ".npy", 100),
                        "phase_semantics": None, "behavior_nested_key_verified": False})
    asset("unjoined-original.npy", 9999)
    roster = {"records": records, "record_count": 3,
              "groups": [{"original_group": text(name), "record_ordinals": ids} for name, ids in groups],
              "duplicate_session_stems": {"A_2022_01_01_1": [0, 1]},
              "existing_evaluator_plan_created": False, "scientific_phase_or_cohort_selected": False,
              "unmatched_neural_ordinals": [], "unmatched_behavior_container_ordinals": [],
              "unmatched_transform_ordinals": []}
    return {"roster": roster}, {"version": 2, "files": files, "count": len(files)}


class BindingControls(unittest.TestCase):
    def test_same_recording_conditions_keep_full_identity_and_nan_bits(self):
        export, inventory = fixture()
        before = copy.deepcopy(export)
        out = b.bind_documents(export, inventory)
        self.assertEqual(export, before)
        self.assertEqual([r["ordinal"] for r in out["records"]], [0, 1, 2])
        for original, row in zip(export["roster"]["records"], out["records"]):
            self.assertEqual(row["original_fields"], original["fields"])
            self.assertEqual(list(row["original_fields"]), list(original["fields"]))
            self.assertEqual(row["source_pointer"], original["source_pointer"])
            self.assertEqual(row["source_record_json_sha256"], b.digest(original))
        a, other = out["records"][:2]
        self.assertEqual(a["physical_session_stem"], other["physical_session_stem"])
        self.assertNotEqual(a["binding_id"], other["binding_id"])
        self.assertNotEqual(a["behavior_lookup"]["key"], other["behavior_lookup"]["key"])
        self.assertEqual(a["original_identity_tuple"], other["original_identity_tuple"])
        out["records"][0]["original_fields"]["stim_id"]["items"][0]["raw_hex"] = "changed"
        self.assertEqual(export, before)

    def test_optional_presence_not_truthiness_and_source_stimulus_authority(self):
        export, inventory = fixture()
        export["roster"]["records"][0]["fields"]["stimtype"] = text("")
        out = b.bind_documents(export, inventory)
        self.assertEqual(out["records"][0]["behavior_lookup"]["key"], "A_2022_01_01_1_")
        self.assertEqual(out["records"][2]["behavior_lookup"]["key"], "B_2022_01_01_1")
        self.assertTrue(out["records"][0]["stimtype_present"])
        self.assertFalse(out["records"][2]["stimtype_present"])
        self.assertEqual(out["safe_export_field_sources"]["stim_id"]["asset_role"], "behavior_container")
        self.assertIsNone(out["records"][0]["metadata_stim_id_is_behavior_mapping"])
        export["roster"]["records"][0]["fields"]["stimtype"] = {"t": "none"}
        with self.assertRaisesRegex(ValueError, "stimtype"):
            b.bind_documents(export, inventory)

    def test_dependency_and_storage_do_not_count_conditions_twice(self):
        out = b.bind_documents(*fixture())
        self.assertEqual(out["storage"]["joined_original_files"], {"count": 6, "bytes": 2220})
        self.assertEqual(out["storage"]["unjoined_original_files"], {"count": 1, "bytes": 9999})
        self.assertEqual(out["storage"]["whole_inventory"]["bytes"], 12219)
        self.assertEqual(out["dependencies"]["literal_mname"][0], {"value": "A", "record_ordinals": [0, 1]})
        self.assertEqual(out["dependencies"]["neural_asset_id"][0]["record_ordinals"], [0, 1])
        self.assertFalse(out["dependencies"]["record_count_is_independent_sample_count"])
        self.assertEqual(len(out["asset_inventory"]), 7)
        self.assertFalse(any(a["payload_verified"] for a in out["asset_inventory"]))

    def test_before_learning_and_reward_text_never_become_phase_or_split(self):
        out = b.bind_documents(*fixture())
        for row in out["records"]:
            self.assertIsNone(row["phase"])
            self.assertIsNone(row["split"])
            self.assertIsNone(row["prereward_eligible"])
        c = out["consumer_compatibility"]
        self.assertFalse(c["compatible"])
        self.assertFalse(c["five_field_plan_created"])
        self.assertFalse(c["safe_npz_created"])
        self.assertEqual(c["repeated_physical_stems"], {"A_2022_01_01_1": [0, 1]})
        self.assertFalse(c["current_consumer_demonstrated_split_leak"])

    def test_missing_extra_reordered_and_fabricated_identities_fail(self):
        mutations = [lambda e: e["roster"]["records"].pop(),
                     lambda e: e["roster"]["records"].reverse(),
                     lambda e: e["roster"]["records"].append(copy.deepcopy(e["roster"]["records"][0])),
                     lambda e: e["roster"]["records"][0]["fields"].update(mname=text("A_swap1")),
                     lambda e: e["roster"]["groups"][0].update(record_ordinals=[0]),
                     lambda e: e["roster"]["records"][0].update(phase_semantics="prereward"),
                     lambda e: e["roster"].update(duplicate_session_stems={})]
        for mutation in mutations:
            export, inventory = fixture()
            mutation(export)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                b.bind_documents(export, inventory)

    def test_inventory_and_source_role_spoofs_fail(self):
        export, inventory = fixture()
        export["roster"]["records"][0]["neural_asset"] = dict(export["roster"]["records"][0]["transform_asset"])
        with self.assertRaisesRegex(ValueError, "asset mismatch"):
            b.bind_documents(export, inventory)
        export, inventory = fixture()
        inventory["files"][-1]["id"] = inventory["files"][0]["id"]
        with self.assertRaisesRegex(ValueError, "duplicate inventory"):
            b.bind_documents(export, inventory)

    def test_json_input_pin_duplicate_key_and_nonfinite_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.json"
            for body in (b'{"k":1,"k":2}', b'{"k":NaN}'):
                path.write_bytes(body)
                with self.assertRaises(ValueError):
                    b.read_pinned_json(path, hashlib.sha256(body).hexdigest())
            path.write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError, "SHA256"):
                b.read_pinned_json(path, "0" * 64)
            self.assertEqual(b.read_pinned_json(path, hashlib.sha256(b'{}').hexdigest()), {})

    def test_output_limit_and_no_overwrite(self):
        self.assertEqual(b.MAX_OUTPUT_BYTES, 524288)
        original = b.MAX_OUTPUT_BYTES
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "out.json"
                b.MAX_OUTPUT_BYTES = len(b.canonical({"x": 1})) + 1
                pin = b.write_new_json(path, {"x": 1})
                self.assertEqual(pin["bytes"], b.MAX_OUTPUT_BYTES)
                with self.assertRaises(FileExistsError):
                    b.write_new_json(path, {"x": 1})
                other = Path(tmp) / "overflow.json"
                with self.assertRaisesRegex(ValueError, "byte limit"):
                    b.write_new_json(other, {"x": 10})
                self.assertFalse(other.exists())
        finally:
            b.MAX_OUTPUT_BYTES = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
