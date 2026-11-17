"""Generated contract tests only; these data are not neuroscience evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("lep_packets", HERE / "packets.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
scorer_spec = importlib.util.spec_from_file_location("lep_scorer", HERE.parent / "full-assay-scorer" / "scorer.py")
scorer = importlib.util.module_from_spec(scorer_spec)
scorer_spec.loader.exec_module(scorer)
PIN = "a" * 64


class GeneratedInputs:
    def __init__(self, endpoint="right_open"):
        self.calls = []
        documentation = "GENERATED TEST ONLY. Predict the recorded pain intensity on the 0 to 10 scale."
        self.protocol = {
            "schema": "lep-packet-protocol-v1", "task_id": p.TASK_ID,
            "documentation": documentation,
            "documentation_sha256": hashlib.sha256(documentation.encode()).hexdigest(),
            "context_review_sha256": PIN,
            "contexts": {device: {"device": device, "reference": "generated reviewed reference",
                                   "rating_protocol": "generated continuous intensity report"}
                         for device in set(p.DEVICES)},
            "stimulated_sides": ["left", "right", "unrecorded"],
        }
        self.representation = {
            "schema": "lep-normalized-representation-v1", "task_id": p.TASK_ID,
            "normalization_review_sha256": PIN, "endpoint_convention": endpoint,
            "times_us": list(range(-1_000_000, 2_000_000 + (endpoint == "inclusive"), 10_000)),
            "sample_rate_hz": 100, "bandlimit_hz": 30, "quantization_uv": 0.01,
            "montages": {"m" + str(n): {"coordinate_system": "generated_mm",
                          "channels": [{"label": "C" + str(c), "xyz_mm": [float(c), 0, 1] if c else None}
                                       for c in range(n)]} for n in (2, 3)},
        }
        self.bodies, self.overrides = {}, {}
        for n in (2, 3):
            count = len(self.representation["times_us"])
            values = [[0.0] * count for _ in range(n)]
            mask = [[True] * count for _ in range(n)]
            values[0][:5] = [1.235, 1.225, -2.345, None, 0]
            mask[0][3] = False
            self.bodies["m" + str(n)] = p.encode({
                "schema": "lep-normalized-epoch-v1",
                "representation_sha256": p.sha256(self.representation),
                "samples_uv": values, "valid_mask": mask,
                "delivered_energy_j": 1.25, "stimulated_side": "left", "calibration_category": 3,
            })
        self.ledger = {
            "schema": "lep-normalized-ledger-v1", "task_id": p.TASK_ID,
            "protocol_sha256": p.sha256(self.protocol),
            "representation_sha256": p.sha256(self.representation),
            "inventory_receipt_sha256": PIN, "producer_receipt_sha256": PIN,
            "identity_receipt_sha256": PIN, "identity_linkage": "complete", "people": [],
        }
        for exp, count in enumerate(p.COUNTS, 1):
            for person in range(count):
                key = "source_person_%02d_%03d" % (exp, person)
                montage = "m" + str(2 + (exp % 2))
                trials = []
                for trial in range(4):
                    trials.append({"trial_key": "source_trial_%d" % trial,
                        "chronology": trial, "eligible": bool(trial),
                        "rating": ((person + trial) % 21) / 2 if trial else None,
                        "exclusion_reason": None if trial else "generated predeclared exclusion",
                        "alias_group": "alias_%s_%d" % (key, trial),
                        "epoch_sha256": hashlib.sha256(self.bodies[montage]).hexdigest() if trial else None,
                        "montage_id": montage if trial else None,
                        "context_id": p.DEVICES[exp - 1] if trial else None})
                self.ledger["people"].append({"experiment": exp, "person_key": key,
                                             "biological_group": "group_" + key, "trials": trials})

    def person(self, exp, index=0):
        return next(row for row in self.ledger["people"]
                    if row["experiment"] == exp and row["person_key"].endswith("_%03d" % index))

    def key(self, exp=1, person=0, trial=3):
        row = self.person(exp, person)
        return (exp, row["person_key"], row["trials"][trial]["trial_key"])

    def change_epoch(self, key, edit):
        person = next(row for row in self.ledger["people"] if (row["experiment"], row["person_key"]) == key[:2])
        trial = next(row for row in person["trials"] if row["trial_key"] == key[2])
        epoch = json.loads(self.overrides.get(key, self.bodies[trial["montage_id"]]))
        edit(epoch)
        raw = p.encode(epoch)
        self.overrides[key] = raw
        trial["epoch_sha256"] = hashlib.sha256(raw).hexdigest()

    def build(self):
        lookup = {(person["experiment"], person["person_key"], trial["trial_key"]): trial["montage_id"]
                  for person in self.ledger["people"] for trial in person["trials"] if trial["eligible"]}
        def loader(key):
            self.calls.append(key)
            return self.overrides.get(key, self.bodies[lookup[key]])
        return p.PreparedAssay(self.ledger, self.protocol, self.representation, loader,
            protocol_sha256=p.sha256(self.protocol), representation_sha256=p.sha256(self.representation),
            support_salt=b"s" * 32, opaque_key=b"k" * 32)


class PacketContractTests(unittest.TestCase):
    def setUp(self):
        self.f = GeneratedInputs()

    def test_full_roster_and_existing_scorer_interoperate(self):
        assay = self.f.build()
        self.assertEqual(self.f.calls, [])
        people, required, excluded, source = scorer.validate_targets(
            assay.private_targets(), assay.protocol_sha256, assay.representation_sha256)
        self.assertEqual((len(people), len(required), excluded, source), (678, 678, 678, 2712))
        self.assertEqual(set(required), set(assay.query_ids))
        self.assertTrue(all(len(row["calibration_ids"]) == 2 for row in people.values()))
        for row in people.values():
            self.assertTrue(set(row["calibration_ids"]).isdisjoint(required))

    def test_query_has_exact_evidence_and_same_mode_bytes(self):
        assay = self.f.build()
        qid = assay._trial_id(1, self.f.key())
        modes = assay.packets_for_modes(qid)
        self.assertIs(modes["A"], modes["B"])
        self.assertIs(modes["A"], modes["C"])
        doc = json.loads(modes["A"])
        self.assertEqual(len(doc["training_support"]), 8)
        self.assertEqual(len(doc["calibration"]), 2)
        self.assertNotIn("rating", doc["query"])
        self.assertEqual(doc["query"]["id"], qid)
        self.assertEqual([row["rating"] for row in doc["calibration"]], [0.5, 1.0])
        self.assertEqual(len(self.f.calls), 11)
        self.assertEqual(set(key[0] for key in self.f.calls[:8]), set(range(2, 10)))
        self.assertEqual(self.f.calls[-3:], [self.f.key(trial=i) for i in (1, 2, 3)])
        self.assertNotIn(b"source_person", modes["A"])
        self.assertNotIn(b"source_trial", modes["A"])
        self.assertNotIn(b"biological_group", modes["A"])
        self.assertNotIn(b"alias_group", modes["A"])

    def test_authoring_never_loads_heldout_recordings(self):
        assay = self.f.build()
        doc = json.loads(assay.authoring_packet(1))
        self.assertEqual(len(self.f.calls), 8)
        self.assertTrue(all(key[0] != 1 for key in self.f.calls))
        self.assertEqual(len(doc["training_support"]), 8)
        self.assertNotIn("calibration", doc)
        self.assertNotIn("query", doc)

    def test_query_target_and_future_trials_do_not_enter_packet(self):
        assay = self.f.build()
        qid = assay._trial_id(1, self.f.key())
        before = assay.query_packet(qid)
        self.f.person(1)["trials"][3]["rating"] = 9.125
        other = self.f.build()
        self.assertEqual(before, other.query_packet(qid))
        self.assertNotEqual(assay.private_targets(), other.private_targets())
        future = copy.deepcopy(self.f.person(1)["trials"][3])
        future.update(trial_key="future_trial", chronology=50, alias_group="unique_future_alias", rating=0)
        self.f.person(1)["trials"].append(future)
        later = self.f.build()
        self.assertEqual(len(later.query_ids), 679)
        self.assertEqual(before, later.query_packet(qid))
        _, required, _, total = scorer.validate_targets(later.private_targets(), later.protocol_sha256,
                                                       later.representation_sha256)
        self.assertEqual((len(required), total), (679, 2713))

    def test_support_selection_is_label_and_row_order_blind(self):
        before = self.f.build().private_selection_audit()
        for person in self.f.ledger["people"]:
            for trial in person["trials"]:
                if trial["eligible"]:
                    trial["rating"] = 10 - trial["rating"]
        self.f.ledger["people"].reverse()
        self.assertEqual(before, self.f.build().private_selection_audit())
        self.assertEqual(self.f.calls, [])

    def test_known_identity_of_any_heldout_person_purges_all_their_training_trials(self):
        self.f.person(2)["biological_group"] = self.f.person(1, 1)["biological_group"]
        assay = self.f.build()
        audit = assay.private_selection_audit()["folds"][0]
        expected = {self.f.key(2, trial=i) for i in (1, 2, 3)}
        self.assertTrue(expected.issubset(set(audit["purged_source_keys"])))
        self.assertTrue(expected.isdisjoint(audit["support_source_keys"]))

    def test_excluded_alias_links_purge_entire_transitive_person_component(self):
        self.f.ledger["identity_linkage"] = "unresolved"
        for person in self.f.ledger["people"]:
            person["biological_group"] = None
        # Trial0 is excluded, but still proves a repeated source person. A second
        # alias joins the next person transitively through a known eligible trial.
        self.f.person(2)["trials"][0]["alias_group"] = self.f.person(1, 1)["trials"][0]["alias_group"]
        self.f.person(3)["trials"][0]["alias_group"] = self.f.person(2)["trials"][1]["alias_group"]
        assay = self.f.build()
        audit = assay.private_selection_audit()["folds"][0]
        expected = {self.f.key(exp, trial=i) for exp in (2, 3) for i in (1, 2, 3)}
        self.assertTrue(expected.issubset(set(audit["purged_source_keys"])))
        self.assertTrue(expected.isdisjoint(audit["support_source_keys"]))
        self.assertEqual(assay.private_selection_audit()["identity_linkage"], "unresolved")

    def test_duplicate_eligible_alias_is_not_calibration_or_double_scored(self):
        for other in (self.f.person(1)["trials"][1], self.f.person(2)["trials"][1]):
            with self.subTest(alias=other["alias_group"]):
                self.f.person(1)["trials"][3]["alias_group"] = other["alias_group"]
                with self.assertRaisesRegex(p.ContractError, "duplicate eligible"):
                    self.f.build()

    def test_empty_training_cohort_after_purge_holds_entire_build(self):
        for person in self.f.ledger["people"]:
            if person["experiment"] == 2:
                person["biological_group"] = self.f.person(1)["biological_group"]
        with self.assertRaisesRegex(p.ContractError, "without a support"):
            self.f.build()
        self.assertEqual(self.f.calls, [])

    def test_channel_roster_mask_grid_and_quantization_retained(self):
        assay = self.f.build()
        doc = json.loads(assay.query_packet(assay._trial_id(1, self.f.key())))
        all_cases = doc["training_support"] + doc["calibration"] + [doc["query"]]
        self.assertEqual({len(case["channels"]) for case in all_cases}, {2, 3})
        self.assertEqual(len(doc["signal_grid"]["times_us"]), 300)
        for case in all_cases:
            self.assertEqual(case["samples_001uv"][0][:5], [124, 122, -234, None, 0])
            self.assertEqual(case["valid_mask"][0][:5], [True, True, True, False, True])
            self.assertEqual(case["quantization"], {"max_abs_residual_uv": 0.005, "missing_samples": 1})
            self.assertTrue(all(len(row) == 300 for row in case["samples_001uv"]))
            self.assertIsNone(case["channels"][0]["xyz_mm"])
            self.assertEqual(case["delivered_energy_j"], 1.25)
            self.assertEqual(case["calibration_category"], 3)

    def test_endpoint_convention_explicit_and_inclusive_grid_complete(self):
        fixture = GeneratedInputs("inclusive")
        assay = fixture.build()
        packet = json.loads(assay.query_packet(assay._trial_id(1, fixture.key())))
        self.assertEqual(packet["signal_grid"]["times_us"][-1], 2_000_000)
        self.assertEqual(len(packet["query"]["samples_001uv"][0]), 301)
        fixture.representation["endpoint_convention"] = "default"
        with self.assertRaises(p.ContractError):
            fixture.build()

    def test_no_clipping_of_finite_physical_samples(self):
        huge = 10 ** 100 + 1
        self.f.change_epoch(self.f.key(), lambda epoch: epoch["samples_uv"][0].__setitem__(4, huge))
        assay = self.f.build()
        packet = json.loads(assay.query_packet(assay._trial_id(1, self.f.key())))
        self.assertEqual(packet["query"]["samples_001uv"][0][4], huge * 100)

    def test_full_ledger_validation_refuses_invalid_scientific_units(self):
        original = copy.deepcopy(self.f.ledger)
        edits = [lambda d: d["people"].pop(),
                 lambda d: d["people"][0].__setitem__("experiment", True),
                 lambda d: d["people"][0].__setitem__("biological_group", None),
                 lambda d: d["people"][0]["trials"].pop(),
                 lambda d: d["people"][0]["trials"].reverse(),
                 lambda d: d["people"][0]["trials"][1].__setitem__("rating", True),
                 lambda d: d["people"][0]["trials"][1].__setitem__("rating", 10.1),
                 lambda d: d["people"][0]["trials"][1].__setitem__("montage_id", "absent"),
                 lambda d: d["people"][0]["trials"][1].__setitem__("context_id", "ANT"),
                 lambda d: d["people"][0]["trials"][0].__setitem__("exclusion_reason", ""),
                 lambda d: d["people"][0]["trials"][0].__setitem__("rating", 0),
                 lambda d: d["people"][0].__setitem__("person_key", "/raw/file"),
                 lambda d: d["people"][1].__setitem__("person_key", d["people"][0]["person_key"]),
                 lambda d: d.__setitem__("protocol_sha256", "b" * 64)]
        for index, edit in enumerate(edits):
            with self.subTest(edit=index):
                self.f.ledger = copy.deepcopy(original)
                edit(self.f.ledger)
                with self.assertRaises(p.ContractError):
                    self.f.build()
        self.assertEqual(self.f.calls, [])

    def test_epoch_fields_masks_and_completeness_are_strict(self):
        edits = [lambda d: d.__setitem__("rating", 5),
                 lambda d: d.__setitem__("source_path", "/recording/file"),
                 lambda d: d["samples_uv"].pop(),
                 lambda d: d["samples_uv"][0].pop(),
                 lambda d: d["samples_uv"][0].__setitem__(3, 0),
                 lambda d: d["samples_uv"][0].__setitem__(0, None),
                 lambda d: d["valid_mask"][0].__setitem__(0, 1),
                 lambda d: d.__setitem__("calibration_category", True),
                 lambda d: d.__setitem__("delivered_energy_j", -1),
                 lambda d: d.__setitem__("stimulated_side", "unreviewed"),
                 lambda d: d.__setitem__("representation_sha256", "b" * 64)]
        for index, edit in enumerate(edits):
            with self.subTest(edit=index):
                self.f.overrides.clear()
                self.f.change_epoch(self.f.key(), edit)
                assay = self.f.build()
                with self.assertRaises(p.ContractError):
                    assay.query_packet(assay._trial_id(1, self.f.key()))

    def test_body_digest_and_duplicate_json_keys_refuse(self):
        raw = b'{"x":1,"x":2}'
        with self.assertRaises(p.ContractError):
            p.decode_epoch(raw, hashlib.sha256(raw).hexdigest())
        for raw in (b'{"x":NaN}', b'{"x":Infinity}', b'\xff', b'[]'):
            with self.subTest(raw=raw):
                if raw != b'[]':
                    with self.assertRaises(p.ContractError):
                        p.decode_epoch(raw, hashlib.sha256(raw).hexdigest())
                with self.assertRaises(p.ContractError):
                    p.decode_epoch(raw, "b" * 64)

    def test_context_capacity_uses_exact_supplied_counter_and_never_truncates(self):
        raw = b"complete packet"
        calls = []
        def counter(body):
            calls.append(body)
            return p.MAX_LIVE_TOKENS
        result = p.check_context_capacity(raw, counter, tokenizer_sha256=PIN,
                                          expected_packet_sha256=hashlib.sha256(raw).hexdigest())
        self.assertEqual(calls, [raw])
        self.assertEqual(result["live_context_tokens"], p.MAX_LIVE_TOKENS)
        for count in (p.MAX_LIVE_TOKENS + 1, 0, True, 4.5):
            with self.subTest(count=count), self.assertRaises(p.ContractError):
                p.check_context_capacity(raw, lambda _: count, tokenizer_sha256=PIN,
                                         expected_packet_sha256=hashlib.sha256(raw).hexdigest())
        with self.assertRaises(p.ContractError):
            p.check_context_capacity(raw + b"tamper", counter, tokenizer_sha256=PIN,
                                     expected_packet_sha256=hashlib.sha256(raw).hexdigest())

    def test_complete_producer_streams_every_query_and_only_success_returns_receipt(self):
        assay = self.f.build()
        authoring, queries, counted = set(), set(), []
        def accept_authoring(identity, raw):
            self.assertNotIn(identity, authoring)
            authoring.add(identity)
            doc = json.loads(raw)
            self.assertEqual(len(doc["training_support"]), 8)
            self.assertNotIn("query", doc)
        def accept_query(identity, raw):
            self.assertNotIn(identity, queries)
            queries.add(identity)
            doc = json.loads(raw)
            self.assertEqual(doc["query"]["id"], identity)
            self.assertNotIn("rating", doc["query"])
            self.assertEqual(len(doc["training_support"]) + len(doc["calibration"]), 10)
        def generated_counter(raw):
            # Deliberately fake tokenizer: exercises accounting, establishes no
            # tokenizer fit or authentic-model readiness.
            counted.append(hashlib.sha256(raw).hexdigest())
            return 123
        receipt = assay.prepare_all(accept_authoring, accept_query, generated_counter, tokenizer_sha256=PIN)
        self.assertEqual((len(authoring), len(queries), len(counted)), (9, 678, 687))
        self.assertEqual(queries, set(assay.query_ids))
        self.assertEqual(len(self.f.calls), 9 * 8 + 678 * 11)
        self.assertEqual(receipt["query_packets"], 678)
        self.assertEqual([item["sha256"] for item in receipt["packets"]], counted)
        self.assertFalse(receipt["scientific_qualification"])
        self.assertFalse(receipt["execution_qualification"])
        staged = []
        with self.assertRaises(p.ContractError):
            assay.prepare_all(lambda *args: staged.append(args), lambda *args: staged.append(args),
                              lambda _: p.MAX_LIVE_TOKENS + 1, tokenizer_sha256=PIN)
        self.assertEqual(staged, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
