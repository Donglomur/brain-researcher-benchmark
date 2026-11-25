"""Generated controls for the identity of bytes actually scored."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import grounding as g
from make_control import build


class GroundingSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "control"
        self.contract = build(self.root)
        self.annotations = self.root / "annotations.json"
        self.order = self.root / "image_order.json"

    def tearDown(self):
        self.tmp.cleanup()

    def evaluate(self):
        return g.evaluate(self.contract, self.annotations, self.order,
                          bootstrap_draws=0)

    def test_replacement_cannot_authenticate_different_annotations(self):
        annotations = json.loads(self.annotations.read_text())
        annotations["0"]["person"] = [[0, 0, .25, .25]]
        replacement = json.dumps(annotations).encode()
        contract = json.loads(self.contract.read_text())
        contract["annotations_sha256"] = hashlib.sha256(replacement).hexdigest()
        self.contract.write_text(json.dumps(contract))
        original = g.prepare_reference

        def replace_after_parse(*args):
            targets = original(*args)
            self.annotations.write_bytes(replacement)
            return targets

        with patch.object(g, "prepare_reference", side_effect=replace_after_parse):
            with self.assertRaisesRegex(g.ContractError, "annotation bytes"):
                self.evaluate()

    def test_response_pin_identifies_scored_bytes_after_replacement(self):
        response = self.root / "candidate_S1.json"
        scored = response.read_bytes()
        original = g.score_subject

        def replace_after_parse(*args):
            response.write_bytes(b"{}")
            return original(*args)

        with patch.object(g, "score_subject", side_effect=replace_after_parse):
            result = self.evaluate()
        self.assertEqual(result["input_pins"]["responses"]["candidate"]["S1"],
                         {"sha256": hashlib.sha256(scored).hexdigest(), "bytes": len(scored)})
        self.assertEqual(result["scores"]["candidate"]["S1"]["All"]["accuracy"]["0.5"], .75)

    def test_contract_pin_identifies_validated_bytes_after_replacement(self):
        validated = self.contract.read_bytes()
        original = g.validate_design

        def replace_after_validation(*args):
            original(*args)
            self.contract.write_bytes(b"{}")

        with patch.object(g, "validate_design", side_effect=replace_after_validation):
            result = self.evaluate()
        self.assertEqual(result["input_pins"]["contract_sha256"],
                         hashlib.sha256(validated).hexdigest())

    def test_unchanged_inputs_preserve_full_panel_and_pins(self):
        expected = {p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                             "bytes": p.stat().st_size}
                    for p in self.root.glob("*.json")}
        result = self.evaluate()
        for field, name in (("contract_sha256", "contract.json"),
                            ("annotations_sha256", "annotations.json"),
                            ("image_order_sha256", "image_order.json")):
            self.assertEqual(result["input_pins"][field], expected[name]["sha256"])
        for role in g.ROLES:
            for subject in g.SUBJECTS:
                self.assertEqual(result["input_pins"]["responses"][role][subject],
                                 expected[f"{role}_{subject}.json"])
        self.assertEqual(result["population"]["shared_images"], 4)
        self.assertEqual(result["population"]["queries_per_subject"], 4)
        for subject in g.SUBJECTS:
            self.assertEqual(result["scores"]["candidate"][subject]["All"]["accuracy"],
                             {"0.3": 1, "0.5": .75, "0.7": .75})
            self.assertEqual(result["scores"]["official_baseline"][subject]["All"]["accuracy"]["0.5"], .25)


if __name__ == "__main__":
    unittest.main()
