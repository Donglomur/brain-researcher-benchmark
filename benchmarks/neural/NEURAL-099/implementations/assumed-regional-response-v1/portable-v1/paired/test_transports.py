"""Two tiny generated region cases; no fixture files, providers or native runs."""

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import unittest


_spec = importlib.util.spec_from_file_location("neural099_transports", Path(__file__).with_name("transports.py"))
transports = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(transports)


def observations():
    return [{
        "case": {"case_id": "source:3:" + region, "animal_id": "animal-a", "asset_id": "source",
                 "region": region, "source_trial_row": 3, "source_cluster_count": clusters},
        "timing": {"click_duration_seconds": 0.0001,
                   "elapsed_since_first_click_seconds": 1.65,
                   "previous_click_interval_seconds": 0.55},
        "history_rates": [rate] * 100,
    } for region, clusters, rate in (("MGv", 4, 250.0), ("MGm", 2, 500))]


def profile(mode):
    condition = {"native_structured_no_tools": "direct-structured-zero-label-current-trial-v1",
                 "frozen_programme": "frozen-programme-zero-label-current-trial-v1"}[mode]
    return {"condition_id": condition, "mode": mode, "information_condition": "timing_history",
            "demonstration_labels": 0, "benchmark_response_labels": "none",
            "selection_training_refit": "none", "state_scope": "fresh_per_trial",
            "feedback": "none", "memory": "none"}


class MatchedTransportTests(unittest.TestCase):
    def test_both_modes_receive_identical_canonical_information(self):
        rows = observations()
        encoded = transports.canonical_observation_bytes(rows)
        self.assertEqual(encoded, transports.canonical_observation_bytes(list(reversed(rows))))
        self.assertEqual([row["case"]["region"] for row in json.loads(encoded)], ["MGm", "MGv"])
        native = transports.build_request(profile("native_structured_no_tools"), rows, "study", "trial")
        programme = transports.build_request(profile("frozen_programme"), rows, "study", "trial")
        self.assertEqual(native["payload"], programme["payload"])
        self.assertEqual(native["payload_sha256"], hashlib.sha256(encoded).hexdigest())
        self.assertEqual(transports.canonical_observation_bytes(native["payload"]), encoded)
        self.assertEqual(transports.canonical_observation_bytes(programme["payload"]), encoded)
        self.assertNotEqual(native["condition_id"], programme["condition_id"])
        self.assertNotEqual(native["mode"], programme["mode"])
        for field in set(native) - {"condition_id", "mode"}:
            self.assertEqual(native[field], programme[field])
        self.assertNotIn("authorized", native)
        self.assertNotIn("enforcement_verified", native)

    def test_numeric_values_and_types_preserved_without_float_coercion(self):
        rows = observations()
        integer = 10 ** 308 + 1
        rows[0]["history_rates"][0] = integer
        rows[0]["history_rates"][1] = math.nextafter(1.0, 2.0)
        rows[0]["history_rates"][2] = -0.0
        result = transports.build_request(profile("frozen_programme"), rows, "study", "trial")
        values = next(row for row in result["payload"] if row["case"]["region"] == "MGv")["history_rates"]
        self.assertIs(type(values[0]), int)
        self.assertEqual(values[0], integer)
        self.assertEqual(values[1], math.nextafter(1.0, 2.0))
        self.assertEqual(math.copysign(1, values[2]), -1)
        values[0] = 0
        self.assertEqual(rows[0]["history_rates"][0], integer)

    def test_private_and_unknown_fields_fail_closed(self):
        for location, name in (("case", "source_trial_id"), ("case", "trial_start_seconds"),
                               ("case", "trial_stop_seconds"), ("timing", "future_response"),
                               (None, "response_counts"), (None, "private_gold")):
            rows = observations()
            target = rows[0] if location is None else rows[0][location]
            target[name] = 123
            with self.subTest(name=name), self.assertRaises(ValueError):
                transports.canonical_observation_bytes(rows)

    def test_current_trial_regions_timing_and_identity_must_agree(self):
        invalid = []
        for field, value in (("animal_id", "other"), ("asset_id", "other"),
                             ("source_trial_row", 4), ("region", "MGv"),
                             ("case_id", "source:3:MGv")):
            rows = observations()
            rows[1]["case"][field] = value
            invalid.append(rows)
        rows = observations()
        rows[1]["timing"]["previous_click_interval_seconds"] = 0.56
        invalid.append(rows)
        rows = observations()
        del rows[1]["history_rates"]
        invalid.append(rows)
        for rows in invalid:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                transports.canonical_observation_bytes(rows)

    def test_history_shape_finiteness_and_case_types_are_strict(self):
        for value in (True, math.nan, math.inf, -math.inf, -1, 10 ** 309):
            rows = observations()
            rows[0]["history_rates"][0] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                transports.canonical_observation_bytes(rows)
        for field, value in (("source_cluster_count", True), ("source_cluster_count", 0),
                             ("source_trial_row", True), ("region", " ")):
            rows = observations()
            rows[0]["case"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                transports.canonical_observation_bytes(rows)
        for count in (99, 101):
            rows = observations()
            rows[0]["history_rates"] = [0] * count
            with self.subTest(count=count), self.assertRaises(ValueError):
                transports.canonical_observation_bytes(rows)

    def test_timing_and_optional_history_encoder_do_not_expand_selected_pair(self):
        rows = observations()
        for row in rows:
            del row["history_rates"]
        encoded = transports.canonical_observation_bytes(rows)
        self.assertTrue(all(set(row) == {"case", "timing"} for row in json.loads(encoded)))
        with self.assertRaises(ValueError):
            transports.build_request(profile("native_structured_no_tools"), rows, "study", "trial")
        for field, value in (("click_duration_seconds", 0), ("click_duration_seconds", True),
                             ("elapsed_since_first_click_seconds", -1),
                             ("previous_click_interval_seconds", 0)):
            rows = observations()
            rows[0]["timing"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                transports.canonical_observation_bytes(rows)

    def test_training_labels_selection_feedback_and_memory_profiles_are_rejected(self):
        invalid = []
        changes = {"demonstration_labels": 1, "benchmark_response_labels": "training",
                   "selection_training_refit": "refit", "state_scope": "session",
                   "feedback": "previous_answers", "memory": "persistent",
                   "information_condition": "timing", "mode": "frozen_programme",
                   "condition_id": "unselected"}
        for field, value in changes.items():
            value_profile = profile("native_structured_no_tools")
            value_profile[field] = value
            invalid.append(value_profile)
        value_profile = profile("native_structured_no_tools")
        value_profile["demonstration_labels"] = False
        invalid.append(value_profile)
        value_profile = profile("native_structured_no_tools")
        value_profile["extra"] = "permission"
        invalid.append(value_profile)
        for value_profile in invalid:
            with self.subTest(profile=value_profile), self.assertRaises(ValueError):
                transports.build_request(value_profile, observations(), "study", "trial")

    def test_tokens_and_empty_or_duplicate_observation_sets_refuse(self):
        for study, token in (("", "trial"), ("study", ""), ("study", "trial\n"),
                             (True, "trial"), ("study", "\ud800")):
            with self.subTest(study=study, token=token), self.assertRaises(ValueError):
                transports.build_request(profile("native_structured_no_tools"), observations(), study, token)
        for rows in ([], observations() * 2, observations() * 4):
            with self.subTest(size=len(rows)), self.assertRaises(ValueError):
                transports.canonical_observation_bytes(rows)


if __name__ == "__main__":
    unittest.main(verbosity=2)
