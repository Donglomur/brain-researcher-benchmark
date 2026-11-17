"""Generated controls only; no authentic observations, labels or model calls."""
import copy
import hashlib
import importlib.util
import itertools
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("materials_join", Path(__file__).with_name("materials_join.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def synthetic_materials(root):
    pins = {"files": []}
    for condition in m.CONDITIONS:
        remaining = m.COUNTS[condition]
        for block in range(1, 8):
            count = remaining // (8 - block)
            remaining -= count
            text = [f'{block};{i};{condition} prefix {block} {i};' for i in range(3)]
            text += [f'{block};{i + 3};{condition} sentence {block} {i};CONTROL' for i in range(count)]
            if condition == "NR" and block == 1:
                text[0] = '1;0;"A quotation" with a tail;CONTROL'
            raw = ("\n".join(text) + "\n").encode()
            name = f"{condition.lower()}_{block}.csv"
            (root / name).write_bytes(raw)
            pins["files"].append({"name": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "version": 1})
    return pins


def presentation_document(materials):
    containers = []
    for person in m.PEOPLE:
        for condition in m.CONDITIONS:
            records = [r for r in materials if r["condition"] == condition and not r["legacy_prefix"]]
            containers.append({"person": person, "condition": condition, "source_bytes": 1000,
                               "source_sha256": hashlib.sha256((person + condition).encode()).hexdigest(),
                               "presentations": [{"source_index": i, "text": r["text"]} for i, r in enumerate(records)]})
    return {"schema": "zuco2-presentation-content-v1", "containers": containers}


class MaterialsTests(unittest.TestCase):
    def test_all_materials_and_quote_interpretations_remain_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            pins = synthetic_materials(root)
            literal = m.load_materials(root, pins, "literal_quotes")
            legacy = m.load_materials(root, pins, "legacy_csv")
            self.assertEqual(len(literal), 781)
            self.assertEqual(sum(r["legacy_prefix"] for r in literal), 42)
            self.assertEqual(literal[0]["text"], '"A quotation" with a tail')
            self.assertNotEqual(literal[0]["text"], legacy[0]["text"])
            self.assertEqual([r["source_record_id"] for r in literal], [r["source_record_id"] for r in legacy])
            self.assertEqual(m.material_audit(literal)["legacy_after_first_three_per_block"]["material_records"],
                             {"NR": 349, "TSR": 390})
            self.assertFalse(m.material_audit(literal)["practice_roles_inferred"])

    def test_hash_drift_missing_pin_and_symlink_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            pins = synthetic_materials(root)
            path = root / "nr_1.csv"
            original = path.read_bytes()
            path.write_bytes(original.replace(b"quotation", b"Quotation"))
            with self.assertRaisesRegex(m.SourceError, "identity mismatch"):
                m.load_materials(root, pins, "literal_quotes")
            path.write_bytes(original)
            with self.assertRaisesRegex(m.SourceError, "fourteen"):
                m.load_materials(root, {"files": pins["files"][:-1]}, "literal_quotes")
            alternate = root / "copy.csv"
            alternate.write_bytes(original)
            path.unlink()
            path.symlink_to(alternate)
            with self.assertRaisesRegex(m.SourceError, "ordinary"):
                m.load_materials(root, pins, "literal_quotes")

    def test_ordered_join_matches_exhaustive_independent_enumeration(self):
        for n in range(6):
            for source in itertools.product(("a", "b"), repeat=n):
                for k in range(4):
                    for query in itertools.product(("a", "b"), repeat=k):
                        candidates = [list(ix) for ix in itertools.combinations(range(n), k)
                                      if tuple(source[i] for i in ix) == query]
                        actual = m.align_exact(source, query)
                        self.assertEqual(actual["alignment_count_capped_at_two"], min(2, len(candidates)))
                        self.assertEqual(actual["material_indices"], candidates[0] if len(candidates) == 1 else None)

    def test_exact_normalization_does_not_fuzzy_match_punctuation(self):
        self.assertEqual(m.align_exact(["Ａ  test"], ["A\ttest"])["material_indices"], [0])
        self.assertIsNone(m.align_exact(["A test."], ["A test"])["material_indices"])
        self.assertEqual(m.align_exact(["x", "a", "a", "b"], ["a", "a", "b"])["material_indices"], [1, 2, 3])
        self.assertEqual(m.align_exact(["a", "x", "a", "b"], ["a", "b"])["status"], "ambiguous_exact_ordered_join")

    def test_complete_content_join_preserves_source_roles_and_refuses_bad_census(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            materials = m.load_materials(root, synthetic_materials(root), "literal_quotes")
            document = presentation_document(materials)
            joined = m.join_presentations(materials, document)
            self.assertTrue(joined["all_content_joins_unique"])
            self.assertEqual(joined["presentations"], 13302)
            self.assertEqual(len(joined["containers"]), 36)
            self.assertTrue(all(c["agrees_with_legacy_first_three_removal"] for c in joined["containers"]))
            self.assertFalse(joined["source_extraction_custody_verified"])
            self.assertFalse(joined["paper_duplicate_obligations_reconciled"])
            incomplete = copy.deepcopy(document)
            incomplete["containers"].pop()
            with self.assertRaisesRegex(m.SourceError, "36-container"):
                m.join_presentations(materials, incomplete)
            duplicate = copy.deepcopy(document)
            duplicate["containers"][1] = duplicate["containers"][0]
            with self.assertRaisesRegex(m.SourceError, "duplicate or unknown"):
                m.join_presentations(materials, duplicate)
            disagree = copy.deepcopy(document)
            disagree["containers"][2]["presentations"][0]["text"] = "different sentence"
            with self.assertRaisesRegex(m.SourceError, "cross-person"):
                m.join_presentations(materials, disagree)
            labels = copy.deepcopy(document)
            labels["containers"][0]["presentations"][0]["label"] = 1
            with self.assertRaisesRegex(m.SourceError, "content and original source index only"):
                m.join_presentations(materials, labels)


if __name__ == "__main__":
    unittest.main()
