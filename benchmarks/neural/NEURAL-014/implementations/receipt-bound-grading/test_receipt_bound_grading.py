"""Generated full45/164-phase receipt controls; no authentic data or models."""
import copy
import json
from pathlib import Path
import types
import unittest


HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / "completed-collection-grading"


def load(path):
    mod = types.ModuleType(path.stem)
    mod.__file__ = str(path)
    raw = path.read_bytes()
    exec(compile(raw, str(path), "exec"), mod.__dict__)
    return mod


fixture = load(PREVIOUS / "test_grade_completed.py")
successor = load(HERE / "receipt_bound_grading.py")


class ReceiptCommitment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.CompleteGrade.setUpClass()
        cls.old = fixture.CompleteGrade("test_complete_grade_and_reference")
        cls.c = cls.old.c
        cls.bodies = cls.old.bodies
        cls.legacy_raw = (PREVIOUS / "grade_completed.py").read_bytes()

    def graph(self, **kwargs):
        fs, request, phases = self.old.fixture_graph(**kwargs)
        raw = successor.seal_collection(request["selection"], request["external"],
                                        self.legacy_raw, self.c, self.bodies, fs.read)
        self.assertEqual(fs.gold_reads, 0)
        return fs, request, phases, raw, self.c.pin(raw)

    def evaluate(self, fs, request, raw, pin, read=None):
        return successor.evaluate(request, raw, pin, self.legacy_raw,
                                  self.c, self.bodies, read or fs.read)

    def alter_input(self, fs, phases, kind="infer"):
        phase = next(p for p in phases if p["kind"] == kind and p["panel"] == "candidate")
        directory = "/attempt/phases/" + phase["phase_id"]
        request = json.loads(fs.files[directory + "/REQUEST.json"])
        request["input"] = self.c.pin(b"different generated input manifest")
        pin = fs.put(directory + "/REQUEST.json", self.c.encoded(request))
        closed = json.loads(fs.files[directory + "/CLOSED.json"])
        closed["request"] = pin
        fs.put(directory + "/CLOSED.json", self.c.encoded(closed))
        if kind == "adapt":
            seal = json.loads(fs.files[directory + "/MODEL_SEAL.json"])
            seal["input"] = request["input"]
            fs.put(directory + "/MODEL_SEAL.json", self.c.encoded(seal))
        return directory

    def test_unchanged_complete_scoring_is_identical(self):
        fs, req, phases, raw, pin = self.graph(heterogeneous=True)
        self.assertEqual(len(phases), 164)
        expected = self.old.execute(fs, req)
        fs.gold_reads = 0
        actual = self.evaluate(fs, req, raw, pin)
        self.assertEqual(actual["grade"], expected)
        self.assertAlmostEqual(actual["grade"]["result"]["candidate"]["primary_PER"], 2 / 9)
        self.assertEqual(fs.gold_reads, 1)
        self.assertFalse(actual["grade"]["scientific_qualified"])
        self.assertGreater(actual["collection_files"], len(phases) * 3)

    def test_original_counterexample_remains_reproducible(self):
        fs, req, phases, _, _ = self.graph()
        expected = self.old.execute(fs, req)
        external = fs.files["/external.json"]
        self.alter_input(fs, phases)
        self.assertEqual(self.old.execute(fs, req), expected)
        self.assertEqual(fs.files["/external.json"], external)

    def test_coherent_inference_input_change_refused_before_gold(self):
        fs, req, phases, raw, pin = self.graph()
        self.alter_input(fs, phases)
        with self.assertRaisesRegex(ValueError, "receipt commitment changed"):
            self.evaluate(fs, req, raw, pin)
        self.assertEqual(fs.gold_reads, 0)

    def test_coherent_adaptation_input_and_seal_change_refused(self):
        fs, req, phases, raw, pin = self.graph()
        self.alter_input(fs, phases, "adapt")
        with self.assertRaisesRegex(ValueError, "receipt commitment changed"):
            self.evaluate(fs, req, raw, pin)
        self.assertEqual(fs.gold_reads, 0)

    def test_native_metadata_change_refused_even_when_summary_matches(self):
        fs, req, phases, raw, pin = self.graph()
        phase = next(p for p in phases if p["kind"] == "infer")
        directory = "/attempt/phases/" + phase["phase_id"]
        native = json.loads(fs.files[directory + "/NATIVE.json"])
        native["command_metadata"][0]["phase"] = "altered-generated-command-description"
        changed = fs.put(directory + "/NATIVE.json", self.c.encoded(native))
        closed = json.loads(fs.files[directory + "/CLOSED.json"])
        closed["native"] = changed
        fs.put(directory + "/CLOSED.json", self.c.encoded(closed))
        with self.assertRaisesRegex(ValueError, "receipt commitment changed"):
            self.evaluate(fs, req, raw, pin)
        self.assertEqual(fs.gold_reads, 0)

    def test_mutation_between_verification_and_grade_is_refused(self):
        fs, req, phases, raw, pin = self.graph()
        phase = next(p for p in phases if p["kind"] == "infer")
        closed_path = "/attempt/phases/" + phase["phase_id"] + "/CLOSED.json"
        reads = 0

        def changing_read(path, cap, expected=None):
            nonlocal reads
            if str(path) == closed_path:
                reads += 1
                if reads == 2:
                    self.alter_input(fs, phases)
            return fs.read(path, cap, expected)

        with self.assertRaisesRegex(ValueError, "exact read pin"):
            self.evaluate(fs, req, raw, pin, changing_read)
        self.assertEqual(reads, 2)
        self.assertEqual(fs.gold_reads, 0)

    def test_seal_identity_is_checked_before_collection_reads(self):
        fs, req, _, raw, pin = self.graph()
        before = fs.read_bytes
        with self.assertRaisesRegex(ValueError, "seal identity"):
            self.evaluate(fs, req, raw + b" ", pin)
        self.assertEqual(fs.read_bytes, before)
        self.assertEqual(fs.gold_reads, 0)

    def test_regenerating_seal_cannot_satisfy_original_trusted_pin(self):
        fs, req, phases, raw, pin = self.graph()
        self.alter_input(fs, phases)
        replacement = successor.seal_collection(req["selection"], req["external"],
                                                self.legacy_raw, self.c, self.bodies, fs.read)
        self.assertNotEqual(raw, replacement)
        with self.assertRaisesRegex(ValueError, "seal identity"):
            self.evaluate(fs, req, replacement, pin)
        self.assertEqual(fs.gold_reads, 0)

    def test_existing_authority_requirement_is_preserved(self):
        fs, req, _, raw, pin = self.graph()
        value = json.loads(fs.files[req["authority"]["path"]])
        value["scientific_grading_authorized"] = False
        p = fs.put(req["authority"]["path"], self.c.encoded(value))
        req["authority"].update(p)
        with self.assertRaisesRegex(ValueError, "grading authorization"):
            self.evaluate(fs, req, raw, pin)
        self.assertEqual(fs.gold_reads, 0)

    def test_private_target_alias_refused_before_read(self):
        fs, req, _, raw, pin = self.graph()
        req = copy.deepcopy(req)
        req["selection"] = copy.deepcopy(req["private_gold"])
        with self.assertRaisesRegex(ValueError, "private target cannot alias"):
            self.evaluate(fs, req, raw, pin)
        self.assertEqual(fs.gold_reads, 0)

    def test_same_path_must_keep_one_identity_during_sealing(self):
        fs, req, _, _, _ = self.graph()
        seen = 0

        def changing_read(path, cap, expected=None):
            nonlocal seen
            if str(path) == "/attempt/COMPLETE.json":
                seen += 1
                if seen == 2:
                    # Deliberately weak reader: _CapturedReads must also verify
                    # the expected pin rather than trust a callback blindly.
                    return fs.files[str(path)] + b" "
            return fs.read(path, cap, expected)

        with self.assertRaisesRegex(ValueError, "captured collection pin"):
            successor.seal_collection(req["selection"], req["external"], self.legacy_raw,
                                      self.c, self.bodies, changing_read)
        self.assertEqual(fs.gold_reads, 0)


if __name__ == "__main__":
    unittest.main()
