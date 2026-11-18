"""Generated structural controls only: no original observations or model calls."""
import copy
import json
import math
import unittest

import static_direct_response as adapter


def values(trial):
    return dict(offer=2.0, rp=1.5, exp_valence=-1.0, ep_valence=0.5,
                exp_arousal=0.2, ep_arousal=0.3, trialLocal=(trial - 1) % 5 + 1,
                trialGlobal=trial, abs_R=0.5, abs_V=1.5, abs_A=abs(0.2 - 0.3))


def fixture(full=False):
    held = adapter.ACTIVE[0]
    clusters = [{"fit_id": "cluster_%02d" % i, "original_participant": person}
                for i, person in enumerate(adapter.ACTIVE) if person != held]
    training = []
    for i, cluster in enumerate(clusters, 1):
        for trial in (range(1, 181) if full else (1, 180)):
            training.append(dict(values(trial), participant=cluster["fit_id"],
                                 original_participant=cluster["original_participant"],
                                 source_row=i * 180 + trial,
                                 FRN_N2_offer=i / 2.0 + trial, P3b_offer=i - trial / 3.0))
    query = [dict(values(trial), source_row=trial) for trial in (1, 2, 180)]
    return {"schema": "neural006-case-v1", "participant": held,
            "training": training, "query": query, "clusters": clusters}


def response(binding):
    return {"schema": "neural006-static-numeric-response-v1",
            "packet_sha256": binding["packet_sha256"],
            "predictions": [[token, i + 0.25, -i - 0.75]
                            for i, (token, _) in enumerate(binding["query_source_rows"])]}


class DirectResponseTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture()
        self.packet, self.binding = adapter.prepare_case(self.case)

    def test_roundtrip_preserves_full_support_and_original_prediction_ids(self):
        value = response(self.binding)
        value["predictions"].reverse()
        result = adapter.collect(self.case, self.binding, adapter.canonical(value))
        self.assertEqual(result["candidate"]["predictions"],
                         [[1, 0.25, -0.75], [2, 1.25, -1.75], [180, 2.25, -2.75]])
        self.assertEqual(result["scientific_qualification"], "not_established")

    def test_packet_contains_all_numerics_but_no_administrative_identity_columns(self):
        packet = json.loads(self.packet)
        self.assertEqual(len(packet["training"]), len(self.case["training"]))
        self.assertEqual(len(packet["query"]), len(self.case["query"]))
        self.assertEqual(packet["training"][0][1:],
                         [self.case["training"][0][k] for k in adapter.FEATURES + adapter.TARGETS])
        self.assertEqual(packet["query"][0][1:],
                         [self.case["query"][0][k] for k in adapter.FEATURES])
        for name in ("participant", "original_participant", "source_row", "clusters"):
            self.assertNotIn(name.encode(), self.packet)
        self.assertTrue(set(adapter.TARGETS).isdisjoint(packet["query_columns"]))

    def test_full_5760_training_rows_are_preserved_without_sampling(self):
        body, _ = adapter.prepare_case(fixture(full=True))
        self.assertEqual(len(json.loads(body)["training"]), 5760)
        self.assertLess(len(body), adapter.MAX_PACKET_BYTES)

    def test_source_case_is_not_mutated(self):
        before = copy.deepcopy(self.case)
        adapter.collect(self.case, self.binding, adapter.canonical(response(self.binding)))
        self.assertEqual(self.case, before)

    def test_training_or_query_targets_cannot_be_smuggled_in_query(self):
        for field in ("FRN_N2_offer", "P3b_offer", "paired_target_eligible", "participant"):
            changed = copy.deepcopy(self.case)
            changed["query"][0][field] = 999
            with self.subTest(field=field), self.assertRaises(adapter.InvalidDirectResponse):
                adapter.prepare_case(changed)

    def test_held_roster_bootstrap_or_reserve_case_is_refused(self):
        changes = [lambda c: c.update(participant="226"),
                   lambda c: c["clusters"].pop(),
                   lambda c: c["clusters"].reverse(),
                   lambda c: c["clusters"][0].update(original_participant=c["participant"])]
        for change in changes:
            altered = copy.deepcopy(self.case)
            change(altered)
            with self.assertRaises(adapter.InvalidDirectResponse):
                adapter.prepare_case(altered)

    def test_row_identity_and_derived_feature_corruptions_are_refused(self):
        changes = [lambda c: c["query"][0].update(source_row=True),
                   lambda c: c["query"][0].update(source_row=c["training"][0]["source_row"]),
                   lambda c: c["query"][0].update(abs_R=7),
                   lambda c: c["training"][0].update(trialGlobal=True),
                   lambda c: c["training"][1].update(source_row=c["training"][0]["source_row"]),
                   lambda c: c["query"].reverse()]
        for change in changes:
            altered = copy.deepcopy(self.case)
            change(altered)
            with self.assertRaises(adapter.InvalidDirectResponse):
                adapter.prepare_case(altered)

    def test_missing_duplicate_or_unknown_response_rows_fail(self):
        changes = [lambda v: v["predictions"].pop(),
                   lambda v: v["predictions"].append(["q004", 0, 0]),
                   lambda v: v["predictions"][1].__setitem__(0, "q001"),
                   lambda v: v["predictions"][0].__setitem__(0, "q999")]
        for change in changes:
            value = response(self.binding)
            change(value)
            with self.assertRaises(adapter.InvalidDirectResponse):
                adapter.collect(self.case, self.binding, adapter.canonical(value))

    def test_boolean_nonfinite_and_abstained_predictions_fail(self):
        for invalid in (True, None, "0.5", math.inf, math.nan):
            value = response(self.binding)
            value["predictions"][0][1] = invalid
            wire = (json.dumps(value, allow_nan=True) + "\n").encode()
            with self.subTest(invalid=invalid), self.assertRaises(adapter.InvalidDirectResponse):
                adapter.collect(self.case, self.binding, wire)

    def test_packet_or_private_case_mutation_invalidates_binding(self):
        changed = copy.deepcopy(self.case)
        changed["training"][0]["FRN_N2_offer"] += 1
        with self.assertRaises(adapter.InvalidDirectResponse):
            adapter.collect(changed, self.binding, adapter.canonical(response(self.binding)))
        changed_binding = copy.deepcopy(self.binding)
        changed_binding["query_source_rows"][0][1] = 999
        with self.assertRaises(adapter.InvalidDirectResponse):
            adapter.collect(self.case, changed_binding, adapter.canonical(response(self.binding)))
        wrong_response = response(self.binding)
        wrong_response["packet_sha256"] = "0" * 64
        with self.assertRaises(adapter.InvalidDirectResponse):
            adapter.collect(self.case, self.binding, adapter.canonical(wrong_response))

    def test_strict_json_rejects_duplicate_keys_trailing_text_and_non_utf8(self):
        for body in (b'{"a":1,"a":2}', b'{} trailing', b'\xff', b'[]' * 10000):
            with self.assertRaises(adapter.InvalidDirectResponse):
                adapter.collect(self.case, self.binding, body)

    def test_response_size_cap_and_extra_fields_are_refused(self):
        with self.assertRaises(adapter.InvalidDirectResponse):
            adapter.collect(self.case, self.binding, b' ' * (adapter.MAX_RESPONSE_BYTES + 1))
        value = response(self.binding)
        value["explanation"] = "not part of the scored response"
        with self.assertRaises(adapter.InvalidDirectResponse):
            adapter.collect(self.case, self.binding, adapter.canonical(value))

    def test_private_binding_boolean_identity_is_not_equal_to_integer_one(self):
        changed_binding = copy.deepcopy(self.binding)
        changed_binding["query_source_rows"][0][1] = True
        self.assertEqual(changed_binding, self.binding)  # Python equality alone is unsafe here.
        with self.assertRaises(adapter.InvalidDirectResponse):
            adapter.collect(self.case, changed_binding, adapter.canonical(response(self.binding)))

    def test_huge_json_integer_is_refused_without_numeric_overflow(self):
        value = response(self.binding)
        value["predictions"][0][1] = 10 ** 400
        with self.assertRaises(adapter.InvalidDirectResponse):
            adapter.collect(self.case, self.binding, adapter.canonical(value))

    def test_finite_primitives_with_overflowing_difference_are_refused(self):
        changed = copy.deepcopy(self.case)
        changed["query"][0].update(offer=10 ** 308, rp=-(10 ** 308), abs_R=0.5)
        with self.assertRaisesRegex(adapter.InvalidDirectResponse, "derived_prediction_error"):
            adapter.prepare_case(changed)


if __name__ == "__main__":
    unittest.main()
