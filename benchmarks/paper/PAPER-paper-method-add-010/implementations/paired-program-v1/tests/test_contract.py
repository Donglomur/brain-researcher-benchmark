"""Generated contract controls: no neural arrays, fits or runtime execution."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("meg_generated_contract", HERE.parent / "contract.py")
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)


def fixture():
    people = contract.published_participants()
    categories = ["False", "face", "letter", "object"]
    records = []
    # Deliberately non-lexical source order exercises order-preserving joins.
    for index, participant in enumerate(reversed(people)):
        order = categories[index % 4:] + categories[:index % 4]
        for category in order:
            source_id = contract.source_observation_id(participant, category)
            records.append({"source_id": source_id, "participant": participant,
                            "category": category,
                            "tensor_sha256": hashlib.sha256(("fictional-values:" + source_id).encode()).hexdigest()})
    folds = {person: index % 10 for index, person in enumerate(people)}
    binding = {"bytes": 1234, "sha256": hashlib.sha256(b"generated-binding-only").hexdigest()}
    return records, folds, bytes(range(32)), binding


def build():
    return contract.build_panel(*fixture())


def response(context, *, features=False):
    return {"schema": contract.RESPONSE_SCHEMA, "context_sha256": context["context_sha256"],
            "probabilities": {identifier: 0.5 for identifier in context["queries"]},
            "source_feature_values": ({row["id"]: (None if index == 7 else index / 376)
                                       for index, row in enumerate(context["windows"])} if features else None)}


def rehash_context(context):
    context["context_sha256"] = contract.digest({k: v for k, v in context.items() if k != "context_sha256"})


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = build()
        cls.contexts = {fold: contract.public_context(cls.panel, fold) for fold in range(10)}

    def test_complete_panel_and_deterministic_public_identity(self):
        panel = build()
        self.assertEqual(panel, self.panel)
        self.assertEqual(len(panel["private_records"]), 376)
        self.assertEqual(len(panel["public_windows"]), 376)
        self.assertEqual(len({r["group_id"] for r in panel["public_windows"]}), 94)
        self.assertEqual([r["source_id"] for r in panel["private_records"]], [r["source_id"] for r in fixture()[0]])
        self.assertNotIn("key", panel)
        self.assertEqual({r["category"] for r in panel["private_records"]}, set(contract.CATEGORIES))

    def test_provisioning_helpers_join_exact_public_order_to_source_identity(self):
        public = contract.ordered_public_windows(self.panel)
        joined = contract.private_source_join(self.panel)
        by_opaque = {row["id"]: row for row in joined.values()}
        self.assertEqual(public, self.contexts[0]["windows"])
        self.assertEqual(set(joined), {row["source_id"] for row in self.panel["private_records"]})
        for row in public:
            source = by_opaque[row["id"]]
            self.assertEqual(source["tensor_sha256"], row["tensor_sha256"])
            self.assertEqual(source["source_id"], contract.source_observation_id(source["participant"], source["category"]))
        public[0]["id"] = "a" * 64
        joined[next(iter(joined))]["source_id"] = "modified"
        self.assertEqual(contract.ordered_public_windows(self.panel), self.contexts[0]["windows"])

    def test_opaque_ids_depend_on_key_and_tensor_content(self):
        records, folds, key, binding = fixture()
        different_key = contract.build_panel(records, folds, b"x" * 32, binding)
        self.assertTrue({r["id"] for r in self.panel["public_windows"]}.isdisjoint(r["id"] for r in different_key["public_windows"]))
        records[0]["tensor_sha256"] = "a" * 64
        changed = contract.build_panel(records, folds, key, binding)
        old = {r["source_id"]: r["id"] for r in self.panel["private_records"]}
        new = {r["source_id"]: r["id"] for r in changed["private_records"]}
        self.assertEqual(sum(old[k] != new[k] for k in old), 1)
        self.assertNotEqual(changed["panel_sha256"], self.panel["panel_sha256"])

    def test_source_multiplicity_and_alias_duplicates_refused(self):
        records, folds, key, binding = fixture()
        bad = records[:-1]
        with self.assertRaises(contract.ContractError):
            contract.build_panel(bad, folds, key, binding)
        bad = copy.deepcopy(records)
        bad[1]["source_id"] = bad[0]["source_id"]
        with self.assertRaises(contract.ContractError):
            contract.build_panel(bad, folds, key, binding)
        false_index = next(i for i, row in enumerate(records) if row["category"] == "False")
        bad = copy.deepcopy(records)
        other = next(i for i, row in enumerate(records) if row["participant"] == bad[false_index]["participant"] and i != false_index)
        bad[other]["category"] = "false"
        with self.assertRaises(contract.ContractError):
            contract.build_panel(bad, folds, key, binding)

    def test_input_extras_unknown_participant_and_invalid_hash_refused(self):
        for change in (lambda r: r.update(extra=True), lambda r: r.update(participant="other"),
                       lambda r: r.update(tensor_sha256="X" * 64), lambda r: r.update(category=True),
                       lambda r: r.update(source_id="fabricated")):
            with self.subTest(change=change):
                records, folds, key, binding = fixture()
                change(records[0])
                with self.assertRaises(contract.ContractError):
                    contract.build_panel(records, folds, key, binding)

    def test_folds_must_cover_exact_people_ten_groups_and_integer_values(self):
        records, folds, key, binding = fixture()
        for bad in ({k: 0 for k in folds}, {k: v for i, (k, v) in enumerate(folds.items()) if i},
                    {**folds, next(iter(folds)): True}, {**folds, next(iter(folds)): 10},
                    {**folds, "other": 0}):
            with self.subTest(bad=bad):
                with self.assertRaises(contract.ContractError):
                    contract.build_panel(records, bad, key, binding)

    def test_binding_and_secret_key_are_strict(self):
        records, folds, key, binding = fixture()
        for bad in ({**binding, "path": "private"}, {**binding, "bytes": True},
                    {**binding, "bytes": 0}, {**binding, "sha256": "bad"}):
            with self.assertRaises(contract.ContractError):
                contract.build_panel(records, folds, key, bad)
        for bad in (b"short", bytearray(key), "0" * 32):
            with self.assertRaises(contract.ContractError):
                contract.build_panel(records, folds, bad, binding)

    def test_all_public_views_retain_unlabeled376_and_no_source_names(self):
        private = self.panel["private_records"]
        for fold, context in self.contexts.items():
            self.assertEqual(len(context["windows"]), 376)
            self.assertEqual(set(context), {"schema", "panel_sha256", "source_binding", "fold", "windows", "training", "queries", "context_sha256"})
            self.assertTrue(all(set(row) == {"id", "group_id", "tensor_sha256"} for row in context["windows"]))
            encoded = contract.canonical(context).decode()
            for row in private:
                self.assertNotIn(row["source_id"], encoded)
                self.assertNotIn(row["participant"], encoded)
            self.assertNotIn('"source_id"', encoded)
            self.assertNotIn('"category"', encoded)
            expected_training = [{"id": r["id"], "label": r["category"]} for r in private
                                 if r["category"] in contract.PAIR and self.panel["participant_folds"][r["participant"]] != fold]
            self.assertEqual(context["training"], expected_training)
            held = {r["id"] for r in private if r["category"] in contract.PAIR and self.panel["participant_folds"][r["participant"]] == fold}
            self.assertEqual(context["queries"], sorted(held))
            self.assertTrue(held.isdisjoint(row["id"] for row in context["training"]))

    def test_views_are_identical_between_arms_and_independent_copies(self):
        first = contract.public_context(self.panel, 3)
        second = contract.public_context(self.panel, 3)
        self.assertEqual(contract.canonical(first), contract.canonical(second))
        first["windows"][0]["id"] = "0" * 64
        first["source_binding"]["bytes"] = 99
        self.assertEqual(second, self.contexts[3])
        self.assertEqual(contract.public_context(self.panel, 3), second)

    def test_panel_and_context_tampering_refused(self):
        bad = copy.deepcopy(self.panel)
        bad["private_records"][0]["tensor_sha256"] = "f" * 64
        with self.assertRaises(contract.ContractError):
            contract.public_context(bad, 0)
        bad_context = copy.deepcopy(self.contexts[0])
        bad_context["queries"].reverse()
        with self.assertRaises(contract.ContractError):
            contract.validate_prediction(response(self.contexts[0]), bad_context, "improvement")
        for bad_fold in (True, -1, 10, "0"):
            with self.assertRaises(contract.ContractError):
                contract.public_context(self.panel, bad_fold)

    def test_rehashed_context_cannot_add_target_labels_or_split_groups(self):
        bad = copy.deepcopy(self.contexts[0])
        bad["windows"][0]["label"] = "face"
        rehash_context(bad)
        with self.assertRaises(contract.ContractError):
            contract.validate_prediction(response(bad), bad, "improvement")
        bad = copy.deepcopy(self.contexts[0])
        train = bad["training"][0]
        held = bad["queries"][0]
        train["id"], bad["queries"][0] = held, train["id"]
        bad["queries"].sort()
        rehash_context(bad)
        with self.assertRaises(contract.ContractError):
            contract.validate_prediction(response(bad), bad, "improvement")

    def test_prediction_support_context_and_extra_fields_are_strict(self):
        context = self.contexts[0]
        for mutation in (lambda b: b.update(extra=1), lambda b: b.update(schema="other"),
                         lambda b: b.update(context_sha256=self.contexts[1]["context_sha256"]),
                         lambda b: b["probabilities"].pop(context["queries"][0]),
                         lambda b: b["probabilities"].update({"foreign": 0.2})):
            body = response(context)
            mutation(body)
            with self.assertRaises(contract.ContractError):
                contract.validate_prediction(body, context, "improvement")

    def test_prediction_numbers_are_finite_bounded_and_not_bools(self):
        context = self.contexts[0]
        for value in (True, False, -0.01, 1.01, float("nan"), float("inf"), "0.5", None, 10**400):
            body = response(context)
            body["probabilities"][context["queries"][0]] = value
            with self.subTest(value=str(value)[:30]):
                with self.assertRaises(contract.ContractError):
                    contract.validate_prediction(body, context, "improvement")
        for value in (0, 0.5, 1):
            body = response(context)
            body["probabilities"][context["queries"][0]] = value
            self.assertEqual(contract.validate_prediction(body, context, "improvement")["probabilities"][context["queries"][0]], float(value))

    def test_reproduction_requires_all376_feature_claims_not_agreement(self):
        context = self.contexts[0]
        with self.assertRaises(contract.ContractError):
            contract.validate_prediction(response(context), context, "reproduction")
        good = response(context, features=True)
        checked = contract.validate_prediction(good, context, "reproduction")
        self.assertEqual(len(checked["source_feature_values"]), 376)
        self.assertEqual(sum(x is None for x in checked["source_feature_values"].values()), 1)
        for change in (lambda d: d.pop(next(iter(d))), lambda d: d.update(foreign=0.0),
                       lambda d: d.update({next(iter(d)): True}), lambda d: d.update({next(iter(d)): math.inf})):
            bad = copy.deepcopy(good)
            change(bad["source_feature_values"])
            with self.assertRaises(contract.ContractError):
                contract.validate_prediction(bad, context, "reproduction")

    def test_collect_full_exact188_in_private_source_order(self):
        responses = {fold: response(ctx) for fold, ctx in self.contexts.items()}
        out = contract.collect(self.panel, responses, "improvement")
        selected = [r for r in self.panel["private_records"] if r["category"] in contract.PAIR]
        self.assertEqual(len(out["observations"]), 188)
        self.assertEqual([r["id"] for r in out["observations"]], [r["source_id"] for r in selected])
        self.assertEqual(set(out["probabilities_object"]), {r["source_id"] for r in selected})
        self.assertEqual({r["participant"] for r in out["observations"]}, set(contract.published_participants()))
        self.assertEqual({r["fold"] for r in out["observations"]}, set(range(10)))
        self.assertEqual({r["label"] for r in out["observations"]}, set(contract.PAIR))
        self.assertIsNone(out["source_feature_rows"])
        self.assertFalse(out["scientific_result_qualified"])
        self.assertFalse(out["runtime_qualified"])

    def test_collect_refuses_missing_string_bool_or_wrong_fold_responses(self):
        responses = {fold: response(ctx) for fold, ctx in self.contexts.items()}
        for bad in ({k: v for k, v in responses.items() if k != 9},
                    {str(k): v for k, v in responses.items()},
                    {False if k == 0 else k: v for k, v in responses.items()},
                    {**responses, 0: responses[1]}):
            with self.assertRaises(contract.ContractError):
                contract.collect(self.panel, bad, "improvement")

    def test_reproduction_features_are_global_and_exactly_consistent(self):
        responses = {fold: response(ctx, features=True) for fold, ctx in self.contexts.items()}
        out = contract.collect(self.panel, responses, "reproduction")
        self.assertEqual(len(out["source_feature_rows"]), 376)
        self.assertEqual(len(set(out["feature_claim_sha256_by_fold"].values())), 1)
        self.assertFalse(out["feature_numerical_agreement_verified"])
        identifier = next(iter(responses[9]["source_feature_values"]))
        responses[9]["source_feature_values"][identifier] += 0.01
        with self.assertRaises(contract.ContractError):
            contract.collect(self.panel, responses, "reproduction")
        # Improvement may declare fold-trained representations, not global reproduction.
        self.assertIsNone(contract.collect(self.panel, responses, "improvement")["source_feature_rows"])

    def test_strict_json_duplicate_keys_nonfinite_and_roundtrip(self):
        for value in (b'{"a":1,"a":2}', b'{"outer":{"x":0,"x":1}}',
                      b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e10000}', b'\xff', b'{'):
            with self.assertRaises(contract.ContractError):
                contract.decode_json(value)
        self.assertEqual(contract.decode_json(contract.canonical(self.contexts[0])), self.contexts[0])
        with self.assertRaises(contract.ContractError):
            contract.canonical({0: "not-string-key"})
        with self.assertRaises(contract.ContractError):
            contract.canonical({"number": math.nan})
        with self.assertRaises(contract.ContractError):
            contract.validate_prediction(response(self.contexts[0]), self.contexts[0], "SOTA")


if __name__ == "__main__":
    unittest.main(verbosity=2)
