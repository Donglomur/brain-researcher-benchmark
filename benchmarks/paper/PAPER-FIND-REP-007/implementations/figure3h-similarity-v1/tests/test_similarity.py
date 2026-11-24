"""Generated Figure 3h arithmetic, complete-inventory and boundary controls."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

FILE = Path(__file__).resolve().parents[1] / "similarity.py"
SPEC = importlib.util.spec_from_file_location("rep007_figure3h", FILE)
si = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(si)


def projection(leaf2=2.0, marker="generated"):
    data = {"schema": "rep007-coding-direction-source-variant/v1", "task_id": si.TASK,
        "source_revision": si.REVISION, "variant": si.INPUT_VARIANT,
        "reference_ids": [2, 0], "percentile": 5,
        "positions": {"previous_trial_tail": 10, "current_trial": 60},
        "source_trial_count": 6, "generated_marker": marker, "areas": {}}
    for area in si.AREAS:
        populations = {}
        for name in ("first_reference", "second_reference"):
            slots = {}
            for code in range(7):
                present = code in (0, 2, 3)
                indices = {0: [1], 2: [3], 3: [4, 5]}.get(code, [])
                contrast = {0: 0., 2: 2., 3: leaf2}.get(code, 0.)
                value = 7. + contrast if name == "first_reference" else 7.
                slots[str(code)] = {"stimulus_name": str(code) if present else None,
                    "present_in_identity_map": present, "trial_indices": indices,
                    "trial_count": len(indices),
                    "trial_role": "odd_zero_based_reference_trials" if code in (0, 2) else "all_trials",
                    "values": [[None] * 10 + [value] * 40 + [9999.] * 20 for _ in indices]}
            populations[name] = {"stimuli": slots}
        data["areas"][area] = {"populations": populations}
    return data


class RecordControls(unittest.TestCase):
    def test_absolute_distance_oracle_and_all_areas(self):
        for leaf2, expected in ((2., 1.), (0., -1.), (1., 0.), (8., 1.), (-8., -1.)):
            out = si.record_similarity(projection(leaf2))
            self.assertEqual(list(out["areas"]), list(si.AREAS))
            for area in out["areas"].values():
                self.assertEqual(area["leaf2_similarity_index"], expected)
                self.assertEqual(area["reference_separation"], 2.)
                self.assertEqual(set(area["stimuli"]), set(map(str, range(7))))
            json.dumps(out, allow_nan=False)

    def test_excludes_previous_tail_and_post_texture_without_dropping_texture(self):
        data = projection()
        baseline = si.record_similarity(data)
        for area in data["areas"].values():
            for population in area["populations"].values():
                for slot in population["stimuli"].values():
                    for row in slot["values"]:
                        row[:10] = [1e9] * 10
                        row[50:] = [None] * 20
        self.assertEqual(si.record_similarity(data), baseline)
        row = data["areas"]["V1"]["populations"]["first_reference"]["stimuli"]["3"]["values"][0]
        row[10] = None
        area = si.record_similarity(data)["areas"]["V1"]
        self.assertIsNone(area["leaf2_similarity_index"])
        self.assertEqual(area["stimuli"]["3"]["trial_count"], 2)
        self.assertEqual(area["stimuli"]["3"]["trial_texture_contrasts"], [None, 2.])

    def test_ratio_follows_trial_means_not_mean_of_trial_ratios(self):
        data = projection()
        for area in data["areas"].values():
            values = area["populations"]["first_reference"]["stimuli"]["3"]["values"]
            values[0][10:50] = [7.] * 40
            values[1][10:50] = [11.] * 40
        result = si.record_similarity(data)["areas"]["V1"]
        self.assertEqual(result["stimuli"]["3"]["trial_texture_contrasts"], [0., 4.])
        self.assertEqual(result["leaf2_similarity_index"], 1.)  # Per-trial ratio averaging gives zero.

    def test_does_not_mutate_inputs(self):
        data = projection()
        before = copy.deepcopy(data)
        si.record_similarity(data)
        self.assertEqual(before, data)

    def test_zero_reference_separation_remains_undefined(self):
        data = projection()
        for area in data["areas"].values():
            area["populations"]["first_reference"]["stimuli"]["2"]["values"][0][10:50] = [7.] * 40
        result = si.record_similarity(data)["areas"]["V1"]
        self.assertIsNone(result["leaf2_similarity_index"])
        self.assertEqual(result["status"], "undefined_zero_reference_separation")

    def test_absent_required_target_is_retained_as_undefined(self):
        data = projection()
        for population in data["areas"]["V1"]["populations"].values():
            population["stimuli"]["3"].update(values=[], trial_count=0, trial_indices=[],
                present_in_identity_map=False, stimulus_name=None)
        self.assertIsNone(si.record_similarity(data)["areas"]["V1"]["leaf2_similarity_index"])

    def test_mismatched_population_trial_or_stimulus_identity_fails(self):
        for key, value in (("trial_indices", [0, 5]), ("stimulus_name", "wrong")):
            data = projection()
            data["areas"]["V1"]["populations"]["second_reference"]["stimuli"]["3"][key] = value
            with self.assertRaises(ValueError): si.record_similarity(data)

    def test_source_variant_axes_and_shapes_are_not_inferred(self):
        cases = []
        for key, value in (("reference_ids", [0, 2]), ("percentile", 10),
                           ("positions", {"previous_trial_tail": 0, "current_trial": 60}),
                           ("source_revision", "unbound")):
            data = projection(); data[key] = value; cases.append(data)
        data = projection(); del data["areas"]["V1"]; cases.append(data)
        data = projection(); del data["areas"]["V1"]["populations"]["first_reference"]["stimuli"]["6"]; cases.append(data)
        data = projection(); data["areas"]["V1"]["populations"]["first_reference"]["stimuli"]["3"]["values"][0].pop(); cases.append(data)
        for data in cases:
            with self.assertRaises(ValueError): si.record_similarity(data)

    def test_overflow_is_undefined_and_strict_json_serializable(self):
        data = projection()
        for area in data["areas"].values():
            for population in area["populations"].values():
                for code in ("0", "2", "3"):
                    for row in population["stimuli"][code]["values"]:
                        row[10:50] = [(-1e308 if code == "0" else 1e308) if population is area["populations"]["first_reference"] else 0.] * 40
        result = si.record_similarity(data)
        self.assertIsNone(result["areas"]["V1"]["leaf2_similarity_index"])
        json.dumps(result, allow_nan=False)


class PanelControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "panel.json"
        self.panel = {"schema_version": 1, "task_id": si.TASK,
            "population_evidence": "generated control only, not an authentic original cohort",
            "expected_record_ids": {}, "records": []}
        for exp_index, experiment in enumerate(si.EXPERIMENTS):
            ids = []
            for i, target in enumerate((2., 0., 0.)):
                identity = f"generated-{exp_index}-{i}"
                ids.append(identity)
                raw = (json.dumps(projection(target, identity)) + "\n").encode()
                filename = identity + ".json"
                (self.root / filename).write_bytes(raw)
                self.panel["records"].append({"record_id": identity,
                    "animal_id": f"animal-{exp_index}-{'a' if i < 2 else 'b'}",
                    "experiment": experiment, "projection_path": filename,
                    "sha256": hashlib.sha256(raw).hexdigest()})
            self.panel["expected_record_ids"][experiment] = ids

    def write_panel(self):
        self.path.write_text(json.dumps(self.panel) + "\n")

    def test_complete_four_condition_source_record_weighting_and_sem(self):
        self.write_panel()
        result = si.evaluate_panel(self.path)
        for group in result["conditions"].values():
            self.assertEqual(len(group["records"]), 3)
            self.assertEqual(len(group["animal_ids"]), 2)
            for area in group["areas"].values():
                self.assertAlmostEqual(area["mean"], -1/3)
                self.assertAlmostEqual(area["sample_sem"], 2/3)
        self.assertFalse(result["original_cohort_verified"])
        self.assertFalse(result["scientific_improvement_assessed"])
        self.assertFalse(result["full_contract_complete"])
        json.dumps(result, allow_nan=False)

    def test_missing_extra_duplicate_records_and_missing_condition_fail(self):
        original = copy.deepcopy(self.panel)
        changes = [lambda p: p["records"].pop(),
                   lambda p: p["records"].append(dict(p["records"][0])),
                   lambda p: p["expected_record_ids"].pop(si.EXPERIMENTS[0]),
                   lambda p: p["expected_record_ids"][si.EXPERIMENTS[0]].append("missing")]
        for change in changes:
            self.panel = copy.deepcopy(original); change(self.panel); self.write_panel()
            with self.assertRaises(ValueError): si.evaluate_panel(self.path)

    def test_tampered_payload_and_reused_payload_fail(self):
        self.write_panel()
        record = self.panel["records"][0]
        path = self.root / record["projection_path"]
        original = path.read_bytes(); path.write_bytes(original + b" ")
        with self.assertRaisesRegex(ValueError, "hash mismatch"): si.evaluate_panel(self.path)
        path.write_bytes(original)
        self.panel["records"][1].update(projection_path=record["projection_path"], sha256=record["sha256"])
        self.write_panel()
        with self.assertRaisesRegex(ValueError, "reused"): si.evaluate_panel(self.path)

    def test_undefined_record_is_counted_and_propagates_to_summary(self):
        record = self.panel["records"][0]
        path = self.root / record["projection_path"]
        data = json.loads(path.read_text())
        data["areas"]["V1"]["populations"]["first_reference"]["stimuli"]["3"]["values"][0][10] = None
        raw = json.dumps(data).encode(); path.write_bytes(raw)
        record["sha256"] = hashlib.sha256(raw).hexdigest(); self.write_panel()
        area = si.evaluate_panel(self.path)["conditions"][si.EXPERIMENTS[0]]["areas"]["V1"]
        self.assertEqual(area["source_record_count"], 3)
        self.assertEqual(area["defined_record_count"], 2)
        self.assertIsNone(area["mean"]); self.assertIsNone(area["sample_sem"])

    def test_cli_writes_bound_strict_json(self):
        self.write_panel()
        output = self.root / "report.json"
        si.main([str(self.path), "--output", str(output)])
        result = json.loads(output.read_text())
        self.assertEqual(result["panel_sha256"], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(result["scientific_qualification"], "unknown")


if __name__ == "__main__":
    unittest.main(verbosity=2)
