"""Generated source-interface controls; never load biological observations."""
import copy
import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location("hierarchy", Path(__file__).with_name("hierarchy.py"))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def token(kind="integer", value="1"):
    return {"kind": kind, "source_type": "builtins.int" if kind == "integer" else "builtins.str",
            "dtype": None, "encoding": "decimal" if kind == "integer" else "unicode", "value": value,
            "missing": False, "missing_reason": None}


def checked(index, count=1, label=None):
    member = h.roster()[index]
    label = token() if label is None else label
    rows = []
    for number in range(count):
        rows.append({**{key: member[key] for key in h.IDENTITY}, "source_member": member["name"],
                     "source_row0": number, "dendrite_id": copy.deepcopy(label),
                     "namespaced_dendrite_id": None if label["missing"] else
                     [member["mouse_id"], member["FOV"], member["session"], copy.deepcopy(label)],
                     "spine_volume": object(), "followup_volume": object()})
    return {"rows": rows}


def full():
    # Generated cardinality control, not source-observed per-member row counts.
    members = [h.project_member(checked(i, 1117 if i == 0 else 1), i) for i in range(27)]
    sidecar = h.assemble(members)
    observations = [{key: row[key] for key in ("row_id", "member_index0", "source_row0", "mouse_id", "compartment")}
                    for row in sidecar["rows"]]
    return members, sidecar, observations


class HierarchyTests(unittest.TestCase):
    def test_projector_omits_all_measurements_and_preserves_rows(self):
        result = h.project_member(checked(0, 2), 0)
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(set(result["rows"][0]), h.ROW_FIELDS)
        self.assertNotIn("spine_volume", result["rows"][0])
        self.assertEqual(result["rows"][1]["row_id"], "m00r0001")

    def test_member_namespace_prevents_cross_fov_merging(self):
        rows = [h.project_member(checked(i), i)["rows"][0] for i in range(27)]
        namespaces = [str(row["namespaced_dendrite_id"]) for row in rows]
        self.assertEqual(len(set(namespaces)), 27)

    def test_missing_ids_are_kept_without_fabricated_group(self):
        empty = token("string", "")
        empty.update(missing=True, missing_reason="empty_string")
        result = h.project_member(checked(0, 2, empty), 0)
        self.assertEqual(len(result["rows"]), 2)
        self.assertTrue(all(row["namespaced_dendrite_id"] is None for row in result["rows"]))

    def test_integer_string_and_float_labels_remain_distinct(self):
        labels = [token(), token("string", "1"), {"kind": "float", "source_type": "builtins.float",
                  "dtype": None, "encoding": "binary64-big-endian", "value": struct.pack(">d", 1.0).hex(),
                  "missing": False, "missing_reason": None}]
        result = [h.validate_token(label) for label in labels]
        self.assertEqual(len({str(x) for x in result}), 3)

    def test_typed_nan_cannot_be_forged_into_group(self):
        value = {"kind": "float", "source_type": "numpy.float32", "dtype": "<f4",
                 "encoding": "numpy-scalar-bytes", "value": struct.pack("<f", float("nan")).hex(),
                 "missing": True, "missing_reason": "nan"}
        self.assertTrue(h.validate_token(value)["missing"])
        value["missing"] = False
        with self.assertRaises(h.Invalid):
            h.validate_token(value)

    def test_wrong_row_order_source_and_namespace_rejected(self):
        for field, value in [("source_row0", 1), ("mouse_id", "JW999"), ("FOV", "FOV99_apical"),
                             ("source_member", "invented"), ("namespaced_dendrite_id", None)]:
            current = checked(0)
            current["rows"][0][field] = value
            with self.subTest(field=field), self.assertRaises(h.Invalid):
                h.project_member(current, 0)

    def test_bad_token_type_range_and_missing_reason_rejected(self):
        for fields in [{"kind": "boolean"}, {"value": "01"}, {"value": "-0"}, {"dtype": False},
                       {"missing": 0}, {"missing_reason": "nan"}, {"source_type": "builtins.bool"},
                       {"source_type": "numpy.uint8", "dtype": "|u1", "value": "256"}]:
            label = token(); label.update(fields)
            with self.subTest(fields=fields), self.assertRaises(h.Invalid):
                h.validate_token(label)

    def test_full_assembly_requires_all_members_and_original_count(self):
        members, sidecar, _ = full()
        self.assertEqual(len(sidecar["rows"]), 1143)
        self.assertEqual(len({r["mouse_id"] for r in sidecar["rows"]}), 20)
        for modified in [members[:-1], members[:-1] + [members[0]],
                         [{"member_index0": i, "rows": m["rows"][:-1]} if i == 0 else m
                          for i, m in enumerate(members)]]:
            with self.assertRaises(h.Invalid):
                h.assemble(modified)

    def test_full_join_preserves_values_and_rejects_identity_corruption(self):
        _, sidecar, observations = full()
        observations[0]["baseline_volume"] = 3.5
        result = h.join_rows(observations, sidecar)
        self.assertEqual(result[0]["observation"]["baseline_volume"], 3.5)
        result[0]["observation"]["baseline_volume"] = 7
        self.assertEqual(observations[0]["baseline_volume"], 3.5)
        for mutation in ("duplicate", "missing", "mouse", "member", "pin"):
            rows, metadata = copy.deepcopy(observations), copy.deepcopy(sidecar)
            if mutation == "duplicate": rows[-1] = rows[0]
            elif mutation == "missing": rows.pop()
            elif mutation == "mouse": rows[0]["mouse_id"] = "JW999"
            elif mutation == "member": rows[0]["member_index0"] = True
            else: metadata["observation_export"]["sha256"] = "0" * 64
            with self.subTest(mutation=mutation), self.assertRaises(h.Invalid):
                h.join_rows(rows, metadata)

    def test_python_numeric_equality_cannot_mask_metadata_type_errors(self):
        members, sidecar, observations = full()
        members[0]["rows"][0]["member_index0"] = False
        with self.assertRaises(h.Invalid):
            h.assemble(members)
        sidecar["observation_export"]["bytes"] = float(h.INPUT["bytes"])
        with self.assertRaises(h.Invalid):
            h.join_rows(observations, sidecar)
        audited = checked(0)
        audited["rows"][0]["namespaced_dendrite_id"][3]["missing"] = 0
        with self.assertRaises(h.Invalid):
            h.project_member(audited, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
