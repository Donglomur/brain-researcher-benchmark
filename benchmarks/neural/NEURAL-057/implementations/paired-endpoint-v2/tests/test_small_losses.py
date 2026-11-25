"""Generated complete-report numerical controls; no scientific input or run."""
import importlib.util
import math
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("n057_small_loss_endpoints", HERE / "endpoints.py")
endpoint = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(endpoint)


def complete_report(reference=0.0, participant=0.0, participant_base=None):
    results = {}
    for owner, value in (("reference", reference), ("participant", participant)):
        cells = []
        for person in endpoint.PEOPLE:
            for mode in endpoint.MODES:
                for panel in endpoint.PANELS:
                    loss = participant_base if owner == "participant" and panel == "BASE" and participant_base is not None else value
                    tag = {"status": "positive_infinity", "value": None} if math.isinf(loss) else {"status": "finite", "value": loss}
                    cells.append({"cell": {"person": person, "mode": mode, "panel": panel},
                                  "loss": dict(tag), "concept_loss": {"generated-one": dict(tag), "generated-two": dict(tag)},
                                  "scored_concepts": 2, "query_rows": 200,
                                  "unsupported_query_ids": [f"generated-unsupported-{i}" for i in range(198)],
                                  "categories": 53, "unit": "nats_per_category",
                                  "repeat_unit": "one 80-repeat mean per original query image"})
        results[owner] = {"cells": cells}
    return {"schema": "neural057-complete-report-v1", "status": "numerical_complete_pending_independent_semantic_qualification", "results": results}


class SmallLossControls(unittest.TestCase):
    def test_complete_subnormal_primary_and_independent_loss(self):
        smallest = math.ulp(0.0)
        result = endpoint.build_endpoints(complete_report(participant=smallest))
        for primary in result["primary_native_loss"]["participant"]:
            self.assertEqual(primary["primary_loss"], {"status": "finite", "value": smallest})
        for comparison in result["independent_comparisons"]:
            self.assertEqual(comparison["right_mean_loss"]["value"], smallest)
            self.assertEqual(comparison["left_minus_right"]["value"], -smallest)
            self.assertEqual(comparison["person_denominator"], 10)

    def test_constant_subnormal_paired_interval_uses_preserved_mean(self):
        smallest = math.ulp(0.0)
        result = endpoint.build_endpoints(complete_report(participant_base=smallest))
        for comparison in result["within_owner_descriptive_comparisons"]["participant"]:
            self.assertEqual(comparison["left_minus_right"]["value"], smallest)
            self.assertEqual(comparison["uncertainty"]["person_t9_descriptive_interval"], [smallest, smallest])
            self.assertEqual(comparison["uncertainty"]["person_sem_ddof1"], 0.0)

    def test_normal_complete_values_and_units_are_unchanged(self):
        result = endpoint.build_endpoints(complete_report(reference=1.25, participant=0.25, participant_base=0.5))
        for row in result["independent_comparisons"]:
            self.assertEqual(row["left_minus_right"]["value"], 1.0)
            self.assertEqual(row["unit"], "nats_per_category")
            self.assertEqual(row["category_denominator"], 53)
        for row in result["within_owner_descriptive_comparisons"]["participant"]:
            self.assertEqual(row["left_minus_right"]["value"], 0.25)
            self.assertEqual(row["uncertainty"]["person_t9_descriptive_interval"], [0.25, 0.25])

    def test_infinite_complete_support_retains_undefined_contrast(self):
        result = endpoint.build_endpoints(complete_report(reference=math.inf, participant=math.inf))
        for row in result["independent_comparisons"]:
            self.assertEqual(row["left_minus_right"]["status"], "undefined")
            self.assertEqual(row["uncertainty"]["status"], "unavailable")
            self.assertEqual(row["person_denominator"], 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
