"""Construction guidance changes neither historical bytes nor scientific admission."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("guidance_fixtures", HERE / "test_neural_understanding.py")
fixtures = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixtures)
engine = fixtures.engine


class CurrentGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.UnderstandingBindingTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        original = json.loads(f.original)
        original["holds"] = [
            {"id": "scorer", "requirement": "Implement evaluator", "status": "open"},
            {"id": "provenance", "requirement": "Authenticate observation lineage", "status": "open"},
        ]
        original["next_implementation_action"] = ["Implement evaluator"]
        f.original = (json.dumps(original) + "\n").encode()
        for key in ("specification", "original_specification"):
            f.row[key].update(bytes=len(f.original), sha256=fixtures.digest(f.original))
        fixtures.put(f.root, "benchmarks/registry.json", f.registry)
        fixtures.put(f.root, f.home + "/task.json", f.original)
        f.contract = fixtures.contract(f.task_id, f.original, f.source)
        self.requirement = "Qualify the existing scorer on authenticated inputs; scientific execution is unverified."

    def select(self):
        self.fixture.contract["current_guidance"] = {"holds": [{
            "id": "scorer", "requirement": self.requirement, "evidence_ids": ["scorer"]}]}
        fixtures.put(self.fixture.root, self.fixture.home + "/" + engine.CONTRACT, self.fixture.contract)

    def test_guidance_updates_current_construction_only_and_preserves_history(self):
        f = self.fixture
        self.select()
        contract_before = copy.deepcopy(f.contract)
        outputs = f.apply()
        current = json.loads(outputs[Path(f.home + "/task.json")])
        self.assertEqual(outputs[Path(f.home + "/" + engine.HISTORY)], f.original)
        self.assertEqual(current["holds"][0], {"id": "scorer", "requirement": self.requirement, "status": "open"})
        self.assertEqual(current["holds"][1], json.loads(f.original)["holds"][1])
        self.assertEqual(current["next_implementation_action"], f.contract["implementation"]["missing"])
        self.assertEqual(current["status"], "specification_only")
        for key in ("runnable", "research_qualified", "submission_ready"):
            self.assertIs(current["admission"][key], False)
        self.assertEqual(f.contract, contract_before)
        self.assertEqual(engine.build_outputs(f.root), outputs)
        self.assertEqual(engine.validate_neural_understanding(f.root), [])

    def test_unselected_contract_preserves_inherited_guidance(self):
        f = self.fixture
        fixtures.put(f.root, f.home + "/" + engine.CONTRACT, f.contract)
        current = json.loads(f.apply()[Path(f.home + "/task.json")])
        original = json.loads(f.original)
        self.assertEqual(current["holds"], original["holds"])
        self.assertEqual(current["next_implementation_action"], original["next_implementation_action"])

    def test_unknown_and_primary_only_evidence_are_rejected(self):
        self.select()
        for evidence in ("absent", "paper"):
            with self.subTest(evidence=evidence):
                c = copy.deepcopy(self.fixture.contract)
                c["current_guidance"]["holds"][0]["evidence_ids"] = [evidence]
                self.assertTrue(any("known local evidence" in e for e in engine.validate_contract(c)))

    def test_duplicate_guidance_ids_are_rejected(self):
        self.select()
        c = self.fixture.contract
        second = copy.deepcopy(c["current_guidance"]["holds"][0])
        second["requirement"] = "Different text for the same hold"
        c["current_guidance"]["holds"].append(second)
        self.assertTrue(any("duplicate hold ID" in e for e in engine.validate_contract(c)))

    def test_unknown_or_ambiguous_existing_hold_is_rejected(self):
        self.select()
        f = self.fixture
        for holds in ([], [{"id": "scorer"}, {"id": "scorer"}]):
            with self.subTest(holds=holds):
                old = json.loads(f.original)
                old["holds"] = holds
                with self.assertRaisesRegex(ValueError, "one existing hold"):
                    engine._current(old, f.contract, {}, f.task_id)

    def test_guidance_cannot_change_admission_or_hold_state(self):
        self.select()
        for extra in ({"status": "complete"}, {"research_qualified": True}, {"remove": True}):
            with self.subTest(extra=extra):
                c = copy.deepcopy(self.fixture.contract)
                c["current_guidance"]["holds"][0].update(extra)
                self.assertTrue(engine.validate_contract(c))
        c = copy.deepcopy(self.fixture.contract)
        c["current_guidance"]["admission"] = {"runnable": True}
        self.assertTrue(engine.validate_contract(c))

    def test_guidance_evidence_still_requires_exact_source_bytes(self):
        f = self.fixture
        self.select()
        f.apply()
        fixtures.put(f.root, f.home + "/scorer.py", f.source + b"# changed\n")
        with self.assertRaisesRegex(ValueError, "Evidence SHA-256 mismatch"):
            engine.load_neural_understanding(f.root, f.task_id)


if __name__ == "__main__":
    unittest.main()
