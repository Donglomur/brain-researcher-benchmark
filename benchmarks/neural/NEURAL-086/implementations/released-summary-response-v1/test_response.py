"""Generated controls only; no recordings, participant model or scientific fit."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import types
import unittest
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("neural086_observations", HERE / "response.py")
response = importlib.util.module_from_spec(spec)
spec.loader.exec_module(response)


def h(value):
    return response.digest(str(value).encode())


def identity(arm="PLUS_EEG"):
    return {"task": "NEURAL-086", "person_token": h("held-person"), "item_fold": 2,
            "context": "FFD", "arm": arm, "representation": "released_summary",
            "mode": "frozen_program", "seed": 0, "programme_sha256": h("programme"),
            "source_sha256": h("source"), "split_sha256": h("split"),
            "information_set": "offline_case_local", "generation": h("generation"),
            "role": "participant", "method": "candidate"}


def feature(arm):
    numeric = [float(i) / 3 for i in range(19)]
    numeric[12] = None
    eeg = [0.125, 1.5, None, -3.0, 4, 5.5, 6, 7]
    blocks = {"base": numeric + [int(x is None) for x in numeric] + [int(x is None) for x in eeg]}
    if arm != "COVARIATES":
        blocks["eeg"] = eeg
    return blocks


def packet(arm="PLUS_EEG"):
    training = []
    for person in range(17):
        for label in (0, 1):
            training.append({"id": h((person, label)), "features": feature(arm),
                             "label": label, "weight": 1.0,
                             "person_group": h(("person", person)), "item_group": h("training-item")})
    queries = [{"id": h(("query", i)), "features": feature(arm)} for i in range(3)]
    shared = {"identity": identity(arm), "information_set": "offline_case_local"}
    return {**copy.deepcopy(shared), "train": training}, {**copy.deepcopy(shared), "query": queries}


def bind(training, query):
    t, q = response.encode(training), response.encode(query)
    binding = {"training": {"bytes": len(t), "sha256": response.digest(t)},
               "query": {"bytes": len(q), "sha256": response.digest(q)},
               "identity_sha256": response.digest(training["identity"]),
               "training_census_sha256": response.digest([r["id"] for r in training["train"]]),
               "query_ids": [r["id"] for r in query["query"]]}
    return t, q, binding


def session(arm="PLUS_EEG"):
    return response.Session(*bind(*packet(arm)), max_input_bytes=65536)


class ObservationControls(unittest.TestCase):
    def test_complete_collection_preserves_probabilities_and_original_ids(self):
        s = session()
        self.assertEqual(s.overview()["training_rows"], 34)
        s.begin_inference()
        for i, p in enumerate((0, 0.5, 1)):
            observation = s.query(i)
            s.answer(observation["session"], observation["token"], p)
        result = s.finish_operator()
        self.assertEqual(result["probabilities"], [{"id": h(("query", i)), "p": p} for i, p in enumerate((0, 0.5, 1))])
        self.assertEqual(result["probability_sha256"], response.digest(result["probabilities"]))
        self.assertFalse(result["campaign_admitted"])
        self.assertFalse(result["scientifically_qualified"])
        for action in (lambda: s.query(0), lambda: s.training(0), s.finish_operator):
            with self.assertRaises(ValueError):
                action()

    def test_training_is_complete_optional_and_available_during_inference(self):
        s = session()
        self.assertEqual({s.training(i)["person_group"] for i in range(34)}, {"person-%03d" % i for i in range(1, 18)})
        self.assertEqual({s.training(i)["label"] for i in range(34)}, {0, 1})
        s.begin_inference()
        self.assertEqual(s.training(33)["weight"], 1.0)

    def test_queries_have_no_source_identity_or_training_labels(self):
        s = session()
        s.begin_inference()
        shown = s.query(0)
        serialized = json.dumps(shown)
        for forbidden in (h("held-person"), h(("query", 0)), h("source"), h("split"), '"label"', '"person_group"', '"item_group"'):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(len(shown["base"]), 46)
        self.assertEqual(len(shown["eeg"]), 8)

    def test_feature_values_and_missingness_survive_without_transforms(self):
        s = session()
        shown = s.training(0)
        self.assertEqual(list(shown["base"].values()), feature("PLUS_EEG")["base"])
        self.assertEqual([x["value"] for x in shown["eeg"].values()], feature("PLUS_EEG")["eeg"])
        shown["base"]["word_chars"] = 999
        self.assertNotEqual(s.training(0)["base"]["word_chars"], 999)

    def test_covariate_arm_keeps_masks_without_eeg_values(self):
        a, b = session("COVARIATES"), session("PLUS_EEG")
        self.assertEqual(a.training(0)["base"], b.training(0)["base"])
        self.assertNotIn("eeg", a.training(0))
        self.assertEqual(a.overview()["eeg_columns"], [])
        self.assertIn("eeg", session("COVARIATES_SHUFFLED_E").training(0))

    def test_inference_and_complete_response_barriers(self):
        s = session()
        with self.assertRaisesRegex(ValueError, "inference_not_started"):
            s.query(0)
        s.begin_inference()
        with self.assertRaisesRegex(ValueError, "query_not_presented"):
            s.answer(s.overview()["session"], "query-0", 0.5)
        s.query(0)
        s.answer(s.overview()["session"], "query-0", 0.5)
        with self.assertRaisesRegex(ValueError, "incomplete_responses"):
            s.finish_operator()
        with self.assertRaisesRegex(ValueError, "response_already_final"):
            s.answer(s.overview()["session"], "query-0", 0.9)

    def test_cross_session_and_malformed_responses_rejected(self):
        s = session()
        s.begin_inference()
        shown = s.query(0)
        for token in ("query--1", "query-00", "training-0", "query-999"):
            with self.assertRaises(ValueError):
                s.answer(shown["session"], token, 0.5)
        with self.assertRaisesRegex(ValueError, "response_binding"):
            s.answer(h("other-session"), shown["token"], 0.5)
        for p in (True, "0.5", -0.1, 1.01, float("nan"), float("inf")):
            with self.assertRaisesRegex(ValueError, "finite_probability"):
                s.answer(shown["session"], shown["token"], p)

    def test_missing_extra_and_reordered_query_census_fail(self):
        t, q, bound = bind(*packet())
        for ids in (bound["query_ids"][:-1], bound["query_ids"] + [h("extra")], list(reversed(bound["query_ids"]))):
            bad = copy.deepcopy(bound)
            bad["query_ids"] = ids
            with self.assertRaisesRegex(ValueError, "query_census"):
                response.Session(t, q, bad, max_input_bytes=65536)
        bad = copy.deepcopy(bound)
        bad["training_census_sha256"] = h("subset")
        with self.assertRaisesRegex(ValueError, "training_census"):
            response.Session(t, q, bad, max_input_bytes=65536)

    def test_query_labels_administrative_fields_and_wrong_arms_fail(self):
        for field, value in (("label", 1), ("source_path", "NR.mat"), ("person_group", h("private"))):
            training, query = packet()
            query["query"][0][field] = value
            with self.assertRaisesRegex(ValueError, "closed_query_row"):
                response.Session(*bind(training, query), max_input_bytes=65536)
        training, query = packet("COVARIATES")
        query["query"][0]["features"]["eeg"] = [0] * 8
        with self.assertRaisesRegex(ValueError, "closed_feature_blocks"):
            response.Session(*bind(training, query), max_input_bytes=65536)

    def test_wrong_support_and_missingness_fail(self):
        for mutation, error in ((lambda t, q: t["train"].pop(), "seventeen_training_people_both_conditions"),
                                (lambda t, q: q["query"][0]["features"]["base"].__setitem__(31, 0), "base_missingness"),
                                (lambda t, q: q["query"][0]["features"]["base"].__setitem__(40, 0), "eeg_missingness"),
                                (lambda t, q: q["query"].append(copy.deepcopy(q["query"][0])), "unique_disjoint_rows")):
            training, query = packet()
            mutation(training, query)
            with self.assertRaisesRegex(ValueError, error):
                response.Session(*bind(training, query), max_input_bytes=65536)

    def test_pins_budget_duplicate_json_and_source_route_fail(self):
        t, q, binding = bind(*packet())
        with self.assertRaisesRegex(ValueError, "input_bytes_budget"):
            response.Session(t, q, binding, max_input_bytes=len(t) + len(q) - 1)
        with self.assertRaisesRegex(ValueError, "input_pin_mismatch"):
            response.Session(t + b" ", q, binding, max_input_bytes=65536)
        duplicate = t[:-2] + b',"train":[]}\n'
        changed = copy.deepcopy(binding)
        changed["training"] = {"bytes": len(duplicate), "sha256": response.digest(duplicate)}
        with self.assertRaisesRegex(ValueError, "duplicate_json_key"):
            response.Session(duplicate, q, changed, max_input_bytes=65536)
        for field, value in (("context", "TRT"), ("representation", "raw_waveform"), ("role", "reference")):
            training, query = packet()
            training["identity"][field] = query["identity"][field] = value
            with self.assertRaisesRegex(ValueError, "supported_source_job"):
                response.Session(*bind(training, query), max_input_bytes=65536)

    def test_static_svg_preserves_all54_feature_values(self):
        s = session()
        s.begin_inference()
        shown = s.query(0)
        svg = response.render_svg(shown)
        root = ET.fromstring(svg)
        texts = [element.text for element in root.iter("{http://www.w3.org/2000/svg}text")]
        self.assertEqual(len(texts), 56)
        for field, value in shown["base"].items():
            self.assertIn(field + " = " + json.dumps(value), texts)
        self.assertNotIn("<script", svg)
        self.assertNotIn("href=", svg)

    def test_actual_source_feature_abi_on_generated_original_shape_rows(self):
        source_root = Path(os.environ.get("NEUROBENCH_TEST_SOURCE_ROOT", str(HERE.parents[4])))
        shared = source_root / "benchmarks/shared/zuco2/zuco2-neural085-086-complete-v1/zuco"
        self.assertEqual(response.digest((shared / "features.py").read_bytes()),
                         "68204e30edd38e95a5ed2e814d7f8064473583faeabb00c4c95f0edd2444ff4a")
        name = "_neural086_observation_source"
        package = types.ModuleType(name)
        package.__path__ = [str(shared)]
        sys.modules[name] = package
        feature_spec = importlib.util.spec_from_file_location(name + ".features", shared / "features.py")
        features = importlib.util.module_from_spec(feature_spec)
        feature_spec.loader.exec_module(features)
        self.assertEqual(tuple(features.BASE_NAMES), response.BASE_NAMES)
        def original_row(person, label):
            word = {"word": "word", "FFD": 100, "GD": 150, "GPT": 150, "TRT": 170,
                    "nFixations": 2, "meanPupilSize": 3}
            sentence = {"text": "word", "words": [word], "person": person,
                        "condition": "TSR" if label else "NR", "omission": 0,
                        "duration_seconds": 1.2}
            values = [float(k // 105) for k in range(840)]
            values[210] = None
            return {"sentence": sentence, "word": word, "word_index": 0,
                    "window": {"band_values": values, "pupil": 3}}
        rows = [original_row(p, label) for p in range(17) for label in (0, 1)]
        partition = {"train": rows, "query": [original_row(17, 0), original_row(17, 1)],
                     "train_ids": [h(("source", k)) for k in range(34)],
                     "query_ids": [h(("source-query", k)) for k in range(2)], "weights": [1] * 34}
        for arm in response.ARMS:
            view = features.public_rows(partition, identity(arm))
            for row, original in zip(view["train"], rows):
                row["person_group"] = h(("source-person", original["sentence"]["person"]))
                row["item_group"] = h("source-item")
            training = {"train": view["train"], "identity": view["identity"], "information_set": "offline_case_local"}
            query = {"query": view["query"], "identity": view["identity"], "information_set": "offline_case_local"}
            s = response.Session(*bind(training, query), max_input_bytes=65536)
            s.begin_inference()
            shown = s.query(0)
            self.assertEqual(list(shown["base"].values()), query["query"][0]["features"]["base"])
            if arm != "COVARIATES":
                self.assertEqual([x["value"] for x in shown["eeg"].values()], [0, 1, None, 3, 4, 5, 6, 7])

    def test_long_finite_values_fit_complete_bounded_svg_extent(self):
        training, query = packet()
        query["query"][0]["features"]["base"][0] = 10 ** 300
        s = response.Session(*bind(training, query), max_input_bytes=65536)
        s.begin_inference()
        svg = response.render_svg(s.query(0))
        root = ET.fromstring(svg)
        width = int(root.attrib["width"])
        self.assertGreater(width, 1100)
        self.assertIn(str(10 ** 300), svg)
        for text in root.iter("{http://www.w3.org/2000/svg}text"):
            self.assertLessEqual(int(text.attrib["x"]) + int(text.attrib["textLength"]), width - 16)
            self.assertEqual(text.attrib["lengthAdjust"], "spacingAndGlyphs")
        self.assertLessEqual(len(svg.encode()), 131072)

    def test_empty_source_query_retains_explicit_operator_disposition(self):
        training, query = packet()
        query["query"] = []
        s = response.Session(*bind(training, query), max_input_bytes=65536)
        self.assertEqual(s.begin_inference()["query_rows"], 0)
        result = s.finish_operator()
        self.assertEqual(result["probabilities"], [])
        self.assertEqual(result["prediction_count"], 0)
        self.assertEqual(result["query_disposition"], "empty_supplied_query_census_requires_operator_disposition")
        self.assertFalse(result["campaign_admitted"])
        self.assertFalse(result["scientifically_qualified"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
