"""Generated input-boundary controls; no authentic values, optimizer or model."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("held_contrast_exchange", PACKAGE / "exchange.py")
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def fixture(n=2, ragged=True, extra_behavior=True):
    people = [f"private-person-{i:02d}" for i in range(n)]
    trials = []
    for person in people:
        for condition in ("accuracy", "speed"):
            for contrast in (5, 20, 80):
                if ragged and person == people[1] and contrast == 5:
                    continue
                trials.append(dict(participant=person, epoch=f"private-epoch-{condition}-{contrast}",
                    condition=condition, contrast_percent=contrast, side="left",
                    response="right" if contrast == 5 else "left", rt_ms=700 + contrast,
                    model_end_ms=710 + contrast, event_times_ms=[11 + contrast / 100, 111, 211, 411, 511]))
    inv = [dict(participant=r["participant"], epoch=r["epoch"], disposition="retained") for r in trials]
    hmp = dict(schema="decision-times-export-v1", purpose="engineering_control",
        sample_rate_hz=512, time_unit="ms", contrast_unit="percent", time_origin="stimulus_onset",
        point_time_method="explicit_point_estimates", expected_participants=people,
        trial_inventory=inv, trials=trials)
    behavior = dict(time_unit="ms", contrast_unit="percent", trial_inventory=copy.deepcopy(inv),
        trials=[{k: v for k, v in r.items() if k not in ("model_end_ms", "event_times_ms")} for r in trials])
    if extra_behavior:
        row = copy.deepcopy(behavior["trials"][0])
        row.update(epoch="private-behavior-only", rt_ms=1234)
        behavior["trials"].append(row)
        behavior["trial_inventory"].append(dict(participant=row["participant"], epoch=row["epoch"], disposition="retained"))
    return dict(schema="decision-times-panel-targets-v2", hmp=hmp, behavior=behavior,
                operator_secret="PRIVATE_REFERENCE_PARAMETERS_DO_NOT_EXPORT")


def exchange(target=None, **kwargs):
    return e.OperatorExchange(fixture() if target is None else target,
        run_id="generated-only-run", method_id="arbitrary_candidate",
        access_condition=kwargs.pop("access_condition", "paper_data"), **kwargs)


def response(packet, latency=-.125):
    rows = []
    for person in packet["participants"]:
        for q in person["queries"]:
            row = dict(prediction_id=q["prediction_id"], latency_seconds=latency)
            if packet["predict_accuracy"]:
                row["probability_correct"] = .75
            rows.append(row)
    return dict(schema="decision-times-fitting-response-v1", case_id=packet["case_id"],
                packet_sha256=e.fingerprint(packet), predictions=rows)


def answer_held(operator):
    for _ in range(len(operator._held_cases)):
        operator.accept_response(response(operator.next_packet()))


def answer_full(operator):
    for _ in range(len(operator._full_cases)):
        operator.accept_response(response(operator.next_packet(), .456))


class ExchangeControls(unittest.TestCase):
    def test_first_packet_exact_source_rows_units_accuracy_and_reversible_aliases(self):
        target = fixture()
        operator = exchange(target)
        packet, binding = operator.next_packet(), operator.operator_binding()
        self.assertEqual((packet["target"], packet["condition"]), ("stimulus_to_C1", "accuracy"))
        self.assertEqual(packet["units"], {"contrast": "fraction", "latency": "seconds", "accuracy": "binary_correct"})
        first = packet["participants"][0]
        self.assertEqual([r["contrast_fraction"] for r in first["fitting_trials"]], [.2, .8])
        for row, expected in zip(first["fitting_trials"], (.0112, .0118)):
            self.assertAlmostEqual(row["latency_seconds"], expected, places=14)
        self.assertEqual([r["accuracy"] for r in first["fitting_trials"]], [1, 1])
        self.assertEqual(first["queries"][0]["contrast_fraction"], .05)
        aliases = binding["participant_aliases"][0]
        self.assertEqual(aliases["original_participant"], "private-person-00")
        self.assertEqual(aliases["trial_aliases"][0]["original_key"], ["private-person-00", "private-epoch-accuracy-20"])
        self.assertNotIn("private-person", json.dumps(packet))
        self.assertNotIn("private-epoch", json.dumps(packet))

    def test_changed_withheld_latency_and_accuracy_do_not_change_public_packet(self):
        target = fixture()
        changed = copy.deepcopy(target)
        changed["hmp"]["trials"][0]["event_times_ms"][0] = 19.87654321
        changed["hmp"]["trials"][0]["response"] = "left"
        changed["behavior"]["trials"][0]["response"] = "left"
        first, second = exchange(target), exchange(changed)
        self.assertEqual(first.next_packet(), second.next_packet())
        self.assertNotEqual(first.operator_binding()["targets_sha256"], second.operator_binding()["targets_sha256"])
        raw = json.dumps(first.next_packet())
        for forbidden in ("PRIVATE_REFERENCE", "event_times_ms", "model_end_ms", "original_key",
                          "targets_sha256", "fit_input_sha256", '"side"', '"response"', '"parameters"'):
            self.assertNotIn(forbidden, raw)

    def test_every_source_law_must_agree_before_any_candidate_input_is_returned(self):
        real = e.source.fit_jobs
        def altered(prepared):
            for job in real(prepared):
                if job["law"] == "linear" and job["mode"] == "held_out" and job["omitted_contrast_percent"] == 5:
                    job = copy.deepcopy(job)
                    job["latency_seconds"][0] += .001
                    job["fit_input_sha256"] = e.source.digest({k: v for k, v in job.items() if k != "fit_input_sha256"})
                yield job
        operator = exchange()
        with patch.object(e.source, "fit_jobs", altered):
            with self.assertRaisesRegex(ValueError, "laws disagree"):
                operator.next_packet()
        self.assertIsNone(operator._pending)
        self.assertEqual(operator._index, 0)

    def test_missing_law_cannot_silently_supply_candidate_plan(self):
        real = e.source.fit_jobs
        def missing(prepared):
            yield from (j for j in real(prepared) if j["law"] != "pieron")
        with patch.object(e.source, "fit_jobs", missing):
            with self.assertRaisesRegex(ValueError, "incomplete source law"):
                exchange().next_packet()

    def test_ragged_global_query_requires_participant_without_held_observation(self):
        operator = exchange()
        packet = operator.next_packet()
        second = packet["participants"][1]
        self.assertEqual([r["contrast_fraction"] for r in second["fitting_trials"]], [.2, .8])
        self.assertEqual(second["queries"][0]["contrast_fraction"], .05)
        reply = response(packet)
        reply["predictions"].pop()
        with self.assertRaisesRegex(ValueError, "incomplete response"):
            operator.accept_response(reply)
        self.assertEqual(operator._index, 0)
        operator.accept_response(response(packet))
        self.assertEqual(len(operator._held), 2)

    def test_separate_B_population_and_trial_weight_preserved_without_collapsing_repeated_contrast(self):
        target = fixture()
        # A B-only contrast creates one additional RT-accuracy global query.
        target["behavior"]["trials"][-1]["contrast_percent"] = 50
        operator = exchange(target)
        self.assertEqual(len(operator._held_cases), 55)
        wanted = None
        for _ in range(55):
            packet = operator.next_packet()
            if packet["target"] == "rt" and packet["condition"] == "accuracy" and packet["participants"][0]["queries"][0]["contrast_fraction"] == .8:
                wanted = packet
            operator.accept_response(response(packet))
        self.assertIsNotNone(wanted)
        self.assertEqual([r["latency_seconds"] for r in wanted["participants"][0]["fitting_trials"]], [.705, .72, 1.234])
        self.assertEqual([r["accuracy"] for r in wanted["participants"][0]["fitting_trials"]], [0, 1, 0])
        self.assertEqual([r["contrast_fraction"] for r in wanted["participants"][0]["fitting_trials"]], [.05, .2, .5])
        same_contrast = exchange(fixture())
        rt_packet = None
        for _ in range(54):
            packet = same_contrast.next_packet()
            if packet["target"] == "rt" and packet["condition"] == "accuracy" and packet["participants"][0]["queries"][0]["contrast_fraction"] == .8:
                rt_packet = packet
            same_contrast.accept_response(response(packet))
        self.assertEqual([r["contrast_fraction"] for r in rt_packet["participants"][0]["fitting_trials"]], [.05, .2, .05])

    def test_invalid_response_is_atomic_and_does_not_advance_or_replace_answer(self):
        operator = exchange()
        packet = operator.next_packet()
        original = response(packet)
        changes = [lambda r: r["predictions"].pop(),
                   lambda r: r["predictions"].append(copy.deepcopy(r["predictions"][0])),
                   lambda r: r.update(packet_sha256="0" * 64),
                   lambda r: r["predictions"][0].update(latency_seconds=True),
                   lambda r: r["predictions"][0].update(latency_seconds=float("nan")),
                   lambda r: r["predictions"][0].update(latency_seconds=1e308),
                   lambda r: r["predictions"][0].update(prediction_id="other-person")]
        for change in changes:
            bad = copy.deepcopy(original); change(bad)
            with self.assertRaises(ValueError):
                operator.accept_response(bad)
            self.assertEqual(operator._index, 0)
            self.assertEqual(operator._held, [])
        operator.accept_response(original)
        with self.assertRaisesRegex(ValueError, "no pending response"):
            operator.accept_response(original)
        operator.next_packet()
        with self.assertRaisesRegex(ValueError, "packet identity"):
            operator.accept_response(original)
        self.assertEqual(operator._index, 1)

    def test_packet_and_binding_are_detached_snapshots(self):
        operator = exchange()
        packet = operator.next_packet()
        binding = operator.operator_binding()
        expected = copy.deepcopy(packet)
        packet["participants"][0]["fitting_trials"][0]["latency_seconds"] = 999
        binding["queries"].clear()
        self.assertEqual(operator.next_packet(), expected)
        operator.accept_response(response(expected))
        self.assertEqual(len(operator._held), 2)

    def test_full_data_input_is_unavailable_until_all_held_predictions_are_frozen(self):
        operator = exchange()
        with self.assertRaisesRegex(ValueError, "complete held"):
            operator.seal_held_predictions()
        with self.assertRaisesRegex(ValueError, "complete full-data"):
            operator.finish()
        answer_held(operator)
        with self.assertRaisesRegex(ValueError, "seal held predictions first"):
            operator.next_packet()
        held = copy.deepcopy(operator._held)
        seal = operator.seal_held_predictions()
        public = operator.next_packet()
        self.assertEqual(public["phase"], "full_data")
        self.assertEqual(public["held_prediction_commitment"], seal["sha256"])
        self.assertEqual([r["contrast_fraction"] for r in public["participants"][0]["fitting_trials"]], [.05, .2, .8])
        with self.assertRaisesRegex(ValueError, "complete held"):
            operator.seal_held_predictions()
        seal["body"]["held_out_sha256"] = "0" * 64
        answer_full(operator)
        result = operator.finish()
        self.assertEqual(result["candidate"]["held_out"], held)
        self.assertTrue(all(r["latency_ms"] == -125 for r in held))
        self.assertTrue(all(r["latency_ms"] == 456 for r in result["candidate"]["full_data"]))
        result["candidate"]["held_out"].clear()
        self.assertEqual(operator.finish()["candidate"]["held_out"], held)
        with self.assertRaisesRegex(ValueError, "finished"):
            operator.next_packet()

    def test_complete_26_person_join_matches_existing18_cell_interface(self):
        target = fixture(26, False, False)
        operator = exchange(target)
        answer_held(operator)
        operator.seal_held_predictions()
        answer_full(operator)
        result = operator.finish()
        method = result["candidate"]
        self.assertEqual(len(method["held_out"]), 26 * 18 * 3)
        self.assertEqual(len(method["full_data"]), 26 * 18 * 3)
        self.assertEqual({(r["target"], r["condition"]) for r in method["held_out"]}, set(operator._prepared))
        self.assertEqual(method["targets_sha256"], e.panel.target_digest(target))
        self.assertFalse(result["readiness_promoted"])
        self.assertFalse(result["scientific_qualification"])

    def test_optional_accuracy_is_frozen_and_complete_only_for_full_data(self):
        operator = exchange(predict_accuracy=True)
        first = operator.next_packet()
        self.assertFalse(first["predict_accuracy"])
        bad = response(first); bad["predictions"][0]["probability_correct"] = .5
        with self.assertRaisesRegex(ValueError, "exact prediction fields"):
            operator.accept_response(bad)
        answer_held(operator)
        operator.seal_held_predictions()
        full = operator.next_packet()
        self.assertTrue(full["predict_accuracy"])
        bad = response(full); del bad["predictions"][0]["probability_correct"]
        with self.assertRaisesRegex(ValueError, "exact prediction fields"):
            operator.accept_response(bad)
        bad = response(full); bad["predictions"][0]["probability_correct"] = 1.01
        with self.assertRaisesRegex(ValueError, "outside"):
            operator.accept_response(bad)
        answer_full(operator)
        method = operator.finish()["candidate"]
        self.assertTrue(all(r["probability_correct"] == .75 for r in method["full_data"]))
        self.assertTrue(all("probability_correct" not in r for r in method["held_out"]))

    def test_shared_numeric_inputs_but_response_bound_to_frozen_access_and_method(self):
        first = exchange(access_condition="paper_data")
        second = exchange(access_condition="paper_data_author_code")
        a, b = first.next_packet(), second.next_packet()
        self.assertEqual(a["participants"], b["participants"])
        self.assertNotEqual(e.fingerprint(a), e.fingerprint(b))
        with self.assertRaisesRegex(ValueError, "packet identity"):
            first.accept_response(response(b))
        b["method_id"] = "different_candidate"
        with self.assertRaisesRegex(ValueError, "packet identity"):
            first.accept_response(response(b))

    def test_duplicate_json_keys_nonfinite_tokens_and_bool_profile_rejected(self):
        for raw in ('{"case_id":"a","case_id":"b"}', '{"predictions":[NaN]}'):
            with self.assertRaises(ValueError):
                e.parse_response(raw)
        with self.assertRaisesRegex(ValueError, "boolean"):
            exchange(predict_accuracy=1)


if __name__ == "__main__":
    unittest.main()
