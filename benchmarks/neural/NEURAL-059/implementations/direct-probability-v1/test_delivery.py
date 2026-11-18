"""Generated full-roster controls; no authentic data or model execution."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import delivery

# Reuse only the existing generated fixture, not its test suite.
FIXTURE = HERE.parent / "prepared-support-v2/test_support.py"
if hashlib.sha256(FIXTURE.read_bytes()).hexdigest() != \
        "4ad74a7b11a61c8ae13a4cf4b9c69c4a5895be6d64836f7896f201755a9d597a":
    raise ValueError("fixture_source_changed")
spec = importlib.util.spec_from_file_location("_direct059_generated_fixture", FIXTURE)
fixture_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_module)


def create(sessions=None, **overrides):
    limits = {"max_input_bytes": 1_000_000, "max_packet_bytes": 10_000,
              "max_response_bytes": 1_000, "max_total_response_bytes": 1_000_000}
    limits.update(overrides)
    return delivery.DirectCollection(fixture_module.fixture() if sessions is None else sessions,
                                     **limits)


def response(observation, probability=.5, **overrides):
    row = {"case_id": json.loads(observation)["observation"]["case_id"],
           "observation_sha256": hashlib.sha256(observation).hexdigest(),
           "p_left": probability}
    row.update(overrides)
    return json.dumps(row, separators=(",", ":")).encode()


class DeliveryTests(unittest.TestCase):
    def test_complete_full_roster_and_four_conditions(self):
        owner = create()
        for session in range(29):
            channels = [owner.channel(session, condition) for condition in delivery.CONDITIONS]
            for trial in range(2):
                observed_ids = []
                for channel in channels:
                    body = channel.observation()
                    view = json.loads(body)["observation"]
                    self.assertEqual(set(view), {"case_id", "condition", "feature_names", "features"})
                    observed_ids.append(view["case_id"])
                    channel.answer(response(body, .25 + .5 * trial))
                self.assertEqual(len(set(observed_ids)), 1)
        report = owner.finish()
        self.assertEqual(report["sessions"], 29)
        self.assertEqual(report["expected_responses"], 232)
        self.assertEqual(len(report["predictions"]), 232)
        for row in report["predictions"]:
            captured = row["response_utf8"].encode("utf-8")
            self.assertEqual(delivery.pin(captured), row["response"])
            self.assertEqual(json.loads(captured)["p_left"], row["p_left"])
        self.assertIsNone(report["score"])
        self.assertFalse(report["scientific_qualification"])
        self.assertFalse(report["participant_isolation_qualified"])
        self.assertFalse(report["model_execution_proved"])
        with self.assertRaisesRegex(delivery.DeliveryError, "collection_sealed"):
            channels[0].observation()

    def test_information_projection_and_full_neural_axis(self):
        sessions = fixture_module.fixture()
        for session in sessions:
            session["unit_ids"].append("second-generated-unit")
            for case in session["cases"]:
                case["unit_ids"].append("second-generated-unit")
                case["count_row"].append(7)
                case["N"].append(math.log1p(7))
            session["counts"]["unit_count"] = 2
            session["counts"]["matrix"] = [c["count_row"][:] for c in session["cases"]]
        owner = create(sessions)
        for condition in delivery.CONDITIONS:
            channel = owner.channel(0, condition)
            view = json.loads(channel.observation())["observation"]
            names = view["feature_names"]
            self.assertEqual(sum(x.startswith("B:") for x in names), 3 if "B" in condition else 0)
            self.assertEqual(sum(x.startswith("N:") for x in names), 2 if "N" in condition else 0)
            if "N" in condition:
                self.assertEqual(view["features"][-2:], [math.log1p(3), math.log1p(7)])
            self.assertNotIn("y", view)
            self.assertEqual(channel.calibration_counts(), {"train": 1, "val": 1})
            labelled = json.loads(channel.calibration("train", 0))["observation"]
            self.assertEqual(labelled["y"], 0)
            self.assertEqual(labelled["feature_names"], names)
            with self.assertRaisesRegex(delivery.DeliveryError, "calibration_split"):
                channel.calibration("test", 0)

    def test_four_condition_history_barrier(self):
        owner = create()
        channels = [owner.channel(0, condition) for condition in delivery.CONDITIONS]
        first = channels[0].observation()
        channels[0].answer(response(first))
        with self.assertRaisesRegex(delivery.DeliveryError, "panel_barrier"):
            channels[0].observation()
        for channel in channels[1:]:
            body = channel.observation()
            self.assertEqual(json.loads(body)["observation"]["case_id"],
                             json.loads(first)["observation"]["case_id"])
            channel.answer(response(body))
        second = json.loads(channels[0].observation())["observation"]
        self.assertNotEqual(second["case_id"], json.loads(first)["observation"]["case_id"])
        # Original intervening no-response history in trial1, then prior left/rewarded in trial2.
        self.assertEqual(json.loads(first)["observation"]["features"][9:], [0, 0, 0, 0, 0, 1, 0])
        self.assertEqual(second["features"][9:], [0, 0, 0, 0, 1, 0, 0])

    def test_original_support_omission_is_rejected_before_delivery(self):
        sessions = fixture_module.fixture()
        sessions[0]["cases"].pop()
        with self.assertRaisesRegex(ValueError, "eligible_slot_case_bijection"):
            create(sessions)
        with self.assertRaisesRegex(ValueError, "complete_roster_size"):
            create(fixture_module.fixture()[:-1])

    def test_incomplete_collection_does_not_emit_complete_artifact(self):
        owner = create()
        with self.assertRaisesRegex(delivery.DeliveryError, "incomplete_full_support"):
            owner.finish()

    def test_input_mutation_does_not_change_delivered_values(self):
        sessions = fixture_module.fixture()
        owner = create(sessions)
        channel = owner.channel(0, "SHN")
        before = channel.observation()
        sessions[0]["cases"][2]["N"][0] = 12345
        sessions[0]["cases"][2]["y"] = 43210
        self.assertEqual(channel.observation(), before)
        self.assertNotIn(b"12345", before)
        self.assertNotIn(b"43210", before)

    def test_invalid_response_is_terminal(self):
        owner = create()
        channel = owner.channel(0, "SH")
        body = channel.observation()
        with self.assertRaisesRegex(delivery.DeliveryError, "response_identity"):
            channel.answer(response(body, observation_sha256="0" * 64))
        with self.assertRaisesRegex(delivery.DeliveryError, "collection_failed"):
            channel.answer(response(body))
        with self.assertRaisesRegex(delivery.DeliveryError, "collection_failed"):
            owner.finish()

    def test_duplicate_response_cannot_overwrite_probability(self):
        owner = create()
        channel = owner.channel(0, "SH")
        body = channel.observation()
        channel.answer(response(body, .1))
        with self.assertRaisesRegex(delivery.DeliveryError, "duplicate_response"):
            channel.answer(response(body, .9))
        self.assertEqual(owner._records[0]["p_left"], .1)

    def test_response_parser_rejects_bad_probabilities_and_schema(self):
        for value in (True, False, None, "0.5", -0.01, 1.01, float("inf"), float("nan")):
            body = json.dumps({"case_id": "c", "observation_sha256": "s", "p_left": value}).encode()
            with self.subTest(value=repr(value)), self.assertRaises(delivery.DeliveryError):
                delivery.parse_response(body, 1000)
        for body in (
            b'{"case_id":"c","observation_sha256":"s","p_left":1e999}',
            b'{"case_id":"c","observation_sha256":"s","p_left":0,"p_left":1}',
            b'{"case_id":"c","observation_sha256":"s","p_left":0.5,"extra":0}',
            b'[]', b'not-json',
        ):
            with self.subTest(body=body), self.assertRaises(delivery.DeliveryError):
                delivery.parse_response(body, 1000)

    def test_byte_limits_and_observation_requirement(self):
        with self.assertRaisesRegex(delivery.DeliveryError, "json_byte_ceiling"):
            create(max_input_bytes=100)
        owner = create(max_packet_bytes=100)
        with self.assertRaisesRegex(delivery.DeliveryError, "json_byte_ceiling"):
            owner.channel(0, "SH").observation()
        owner = create(max_total_response_bytes=1)
        channel = owner.channel(0, "SH")
        body = channel.observation()
        with self.assertRaisesRegex(delivery.DeliveryError, "response_total_ceiling"):
            channel.answer(response(body))
        owner = create()
        with self.assertRaisesRegex(delivery.DeliveryError, "observation_not_delivered"):
            owner.channel(0, "SH").answer(b'{"case_id":"c","observation_sha256":"s","p_left":0.5}')

    def test_response_must_be_utf8_not_implicitly_decoded_utf16(self):
        text = '{"case_id":"c","observation_sha256":"s","p_left":0.5}'
        for encoding in ("utf-16", "utf-32"):
            with self.subTest(encoding=encoding), self.assertRaisesRegex(
                    delivery.DeliveryError, "response_json"):
                delivery.parse_response(text.encode(encoding), 1000)


if __name__ == "__main__":
    unittest.main(verbosity=1)
