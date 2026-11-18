"""Generated metadata controls; no authentic images, neural values or targets."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


design = load("neural051_metadata_builder_test", HERE / "design.py")
PINS = {p: hashlib.sha256(("generated-source-" + p).encode()).hexdigest() for p in ("01", "02", "03")}
SEED = "generated-not-a-production-secret-20261118"


def fixture():
    # Twelve720-image blocks plus100 repeated images per session. Independent
    # session permutations yield exactly five global query blocks and three
    # surviving validation blocks, leaving four training blocks for each person.
    orders = {"01": [2, 3, 4, 7, 8, 9, 10, 11, 5, 6, 0, 1],
              "02": [1, 4, 6, 7, 8, 9, 10, 11, 5, 0, 2, 3],
              "03": [0, 2, 5, 6, 8, 9, 10, 11, 7, 1, 3, 4]}
    people = {}
    for person, order in orders.items():
        rows = []
        for session, block in enumerate(order, 1):
            images = [(f"b{block:02d}_{i:03d}.jpg", f"c{i:03d}", "train") for i in range(720)]
            images.extend((f"repeat_{i:03d}.jpg", f"c{i:03d}", "test") for i in range(100))
            for i, (stimulus, concept, kind) in enumerate(images):
                rows.append({"trial_type": kind, "session": session, "run": i // 82 + 1,
                             "subject_id": int(person), "trial_id": len(rows),
                             "stimulus": stimulus, "concept": concept})
        people[person] = rows
    return people


class MetadataPreparationControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = fixture()
        cls.mapping, cls.roster = design.build_rows(cls.rows, SEED, PINS)

    def test_full_generated_census_and_current_scorer_interoperability(self):
        scorer = load("neural051_existing_scorer_for_metadata_test", HERE.parent / "retrieval-scorer-v1/scorer.py")
        scorer.validate_roster(self.roster)
        mapping = scorer.validate_design(self.roster, self.mapping)
        self.assertEqual(len(mapping), 6)
        self.assertEqual(len(self.mapping["candidates"]), 3700)
        self.assertEqual(len(set(self.mapping["candidate_concepts"])), 720)
        for case in self.mapping["cases"]:
            self.assertEqual(len(case["queries"]), 1540)
            self.assertEqual(sum(len(q["trial_ids"]) for q in case["queries"]), 1640)
            self.assertEqual(len(case["train_trial_ids"]), 2880)
            self.assertEqual(len(case["validation_trial_ids"]), 1440 if case["person"] == "01" else 720)

    def test_exact_source_image_join_and_global_exclusions(self):
        query_images = set(self.mapping["candidates"])
        validation_images = {name for case in self.mapping["cases"] for name in case["validation_images"]}
        for case in self.mapping["cases"]:
            source = self.rows[case["person"]]
            for query in case["queries"]:
                name = self.mapping["candidates"][query["candidate_index"]]
                self.assertEqual({source[i]["stimulus"] for i in query["trial_ids"]}, {name})
            self.assertFalse(set(case["train_images"]) & (query_images | validation_images))
            self.assertFalse(set(case["validation_images"]) & query_images)
        # Person02 sees a person01 query block in its development session10.
        self.assertFalse(any(name.startswith("b00_") for name in self.mapping["cases"][2]["validation_images"]))

    def test_public_projection_and_private_seed_semantics(self):
        raw = json.dumps(self.roster)
        for forbidden in (SEED, '"trial_ids"', '"candidate_index"', '"c000"', ".jpg"):
            self.assertFalse(forbidden in raw, "public roster contains a forbidden metadata value/key")
        self.assertTrue(all(set(row) == {"query_ids", "candidate_ids"} for row in self.roster.values()))
        changed, roster = design.build_rows(self.rows, SEED + "different", PINS)
        self.assertEqual(self.mapping["candidate_ids"], changed["candidate_ids"])
        self.assertNotEqual(self.roster["sub-01_V1"]["query_ids"], roster["sub-01_V1"]["query_ids"])
        self.assertEqual(roster["sub-01_V1"], roster["sub-01_IT"])
        self.assertNotIn(SEED, json.dumps(self.mapping))

    def test_in_memory_input_is_not_mutated_or_shared_between_rois(self):
        self.assertEqual(self.rows["01"][0]["trial_id"], 0)
        mapped, _ = design.build_rows(self.rows, SEED, PINS)
        mapped["cases"][0]["queries"][0]["trial_ids"].append(999999)
        self.assertNotIn(999999, mapped["cases"][1]["queries"][0]["trial_ids"])

    def test_incomplete_cohort_and_seed_rejected(self):
        with self.assertRaisesRegex(ValueError, "three-person"):
            design.build_rows({"01": self.rows["01"]}, SEED, PINS)
        with self.assertRaisesRegex(ValueError, "private operator seed"):
            design.build_rows(self.rows, "short", PINS)
        with self.assertRaisesRegex(ValueError, "source pins"):
            design.build_rows(self.rows, SEED, {"01": "x"})

    def test_duplicate_native_trial_and_noninteger_indices_rejected(self):
        rows = copy.deepcopy(self.rows)
        rows["01"][1]["trial_id"] = 0
        with self.assertRaises(ValueError):
            design.build_rows(rows, SEED, PINS)
        for value in (True, 1.0, "1"):
            rows["01"][1]["trial_id"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "integer source"):
                design.build_rows(rows, SEED, PINS)

    def test_changed_candidate_concept_census_rejected(self):
        rows = copy.deepcopy(self.rows)
        for records in rows.values():
            for row in records:
                if row["stimulus"] == "b00_000.jpg":
                    row["concept"] = "c001"
        with self.assertRaisesRegex(ValueError, "720-concept"):
            design.build_rows(rows, SEED, PINS)

    def test_csv_rejects_duplicate_columns_missing_cells_and_extra_cells(self):
        header = ",".join(design.FIELDS)
        good = "train,1,1,1,0,image.jpg,concept"
        parsed = design.parse_metadata((header + "\n" + good + "\n").encode())
        self.assertEqual(parsed[0]["trial_id"], 0)
        for raw in ((header + ",trial_id\n" + good + ",0\n").encode(),
                    (header + "\ntrain,1,1,1,0,image.jpg\n").encode(),
                    (header + "\n" + good + ",extra\n").encode(),
                    (header + "\ntrain,1.0,1,1,0,image.jpg,concept\n").encode()):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                design.parse_metadata(raw)

    def test_source_hash_mismatch_prevents_preparation(self):
        # Actual bounded-reader path with tiny generated bytes, not authentic data.
        with tempfile.TemporaryDirectory(prefix="n051-metadata-generated-") as directory:
            root = Path(directory).resolve()
            (root / "sub-01_StimulusMetadata.csv").write_bytes(b"generated wrong source\n")
            with self.assertRaisesRegex(ValueError, "match pin"):
                design.capture_design(root, PINS, SEED)

    def test_operator_outputs_private_create_only_and_receipt_last(self):
        # Writer boundary only; full support exercised in-memory above to avoid
        # writing multi-megabyte generated metadata copies.
        with tempfile.TemporaryDirectory(prefix="n051-private-writer-generated-") as directory:
            root = Path(directory).resolve() / "out"
            receipt = design.write_bundle(root, {"source_pins": PINS}, {})
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            self.assertEqual({p.name for p in root.iterdir()}, {"design.json", "roster.json", "PREPARATION.json"})
            for name, pin in receipt["files"].items():
                body = (root / name).read_bytes()
                self.assertEqual(len(body), pin["bytes"])
                self.assertEqual(hashlib.sha256(body).hexdigest(), pin["sha256"])
                self.assertEqual(stat.S_IMODE((root / name).stat().st_mode), 0o600)
            self.assertFalse(receipt["runtime_qualified"])
            self.assertFalse(receipt["source_response_join_verified"])
            with self.assertRaises(FileExistsError):
                design.write_bundle(root, {"source_pins": PINS}, {})


class _BoundedDiagnosticStream:
    """Cap the entire generated-test diagnostic stream at2048 UTF8 bytes."""
    def __init__(self, stream):
        self.stream, self.remaining = stream, 2048

    def write(self, value):
        raw = value.encode("utf-8")
        kept = raw[:self.remaining].decode("utf-8", errors="ignore")
        self.remaining -= len(kept.encode("utf-8"))
        self.stream.write(kept)
        return len(value)

    def flush(self):
        self.stream.flush()


if __name__ == "__main__":
    unittest.main(testRunner=unittest.TextTestRunner(stream=_BoundedDiagnosticStream(sys.stderr), verbosity=1))
