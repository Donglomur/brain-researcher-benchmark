"""Generated observations only; no authentic MEG, participant or private inputs."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("N097_SOURCE_ROOT", ROOT.parent / "registered-runtime/full-cogitate-meg-v1"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


current = load("n097_restricted_observation", ROOT / "observation.py")
package = types.ModuleType("n097_metadata_control")
package.__path__ = [str(SOURCE / "n097")]
sys.modules[package.__name__] = package
legacy_views = load(package.__name__ + ".views", SOURCE / "n097/views.py")
legacy_collection = load(package.__name__ + ".collection", SOURCE / "n097/collection.py")


def pin(path):
    return {"path": path, "bytes": 0, "sha256": "0" * 64}


def views(arm="SIGNAL", key="b" * 48):
    training = {"schema": "neural097-train-view-v2", "opaque_episode_nonce": "a" * 48,
                "contract_version": {"scientific": pin("contracts/SCIENTIFIC_CONTRACT.json"),
                                     "estimand_reporting": pin("contracts/ESTIMAND_REPORTING_CONTRACT.json")},
                "access_arm": "A", "feature_arm": arm, "feature_columns": legacy_views.feature_columns(arm),
                "feature_units": current.UNITS, "features_member": pin("features.npy"),
                "training_rows_member": pin("rows.json"), "inner_validation_plan_member": pin("inner.json")}
    neural = [((i - 30) * 1.2345678901234567e-15) for i in range(60)]
    neural[0] = -0.0
    neural[1] = 5e-324
    neural[-1] = 1.7976931348623157e308
    nuisance = [0.0, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0]
    values = nuisance if arm == "NUISANCE" else neural + (nuisance if arm.endswith("_NUISANCE") else [])
    return training, {"schema": "neural097-query-v2", "opaque_episode_nonce": "a" * 48,
                      "opaque_query_nonce": key, "x_numeric_vector": values}


def packet(arm="SIGNAL", key="b" * 48):
    return current.make_packet(*views(arm, key))


def response(key="b" * 48, **fields):
    return {"schema": "neural097-query-prediction-v2", "opaque_episode_nonce": "a" * 48,
            "opaque_query_nonce": key, **(fields or {"status": "complete", "p_face": .7})}


class ObservationTests(unittest.TestCase):
    def test_all_five_arms_match_existing_coordinate_order_and_values(self):
        for arm, dimension in zip(current.ARMS, (60, 60, 8, 68, 68)):
            with self.subTest(arm=arm):
                training, query = views(arm)
                before = copy.deepcopy((training, query))
                p = current.make_packet(training, query)
                self.assertEqual(p["feature_columns"], legacy_views.feature_columns(arm))
                self.assertEqual(len(p["query"]["x_numeric_vector"]), dimension)
                self.assertEqual(current.canonical(p["query"]), current.canonical(query))
                self.assertEqual(p["training_view_identity"], current.identity(training))
                rows = current.render_text(p).split("Coordinate\tUnits\tValue\n")[1].splitlines()
                self.assertEqual(len(rows), dimension)
                for row, value, column in zip(rows, query["x_numeric_vector"], p["feature_columns"]):
                    name, units, literal = row.split("\t")
                    self.assertEqual((name, units), (column["name"], column["units"]))
                    self.assertEqual(json.dumps(float(literal)), json.dumps(float(value)))
                self.assertEqual((training, query), before)
                p["query"]["x_numeric_vector"][0] = 2
                self.assertEqual((training, query), before)

    def test_forbidden_fields_and_wrong_order_are_refused(self):
        for field in ("y", "stratum", "private_id", "image_identity", "Stim_trigger", "source_person"):
            training, query = views()
            query[field] = "PRIVATE-SENTINEL"
            with self.subTest(field=field), self.assertRaises(current.ObservationError):
                current.make_packet(training, query)
        training, query = views()
        training["feature_columns"].reverse()
        with self.assertRaises(current.ObservationError):
            current.make_packet(training, query)
        training, query = views()
        training["source_person"] = "PRIVATE-SENTINEL"
        with self.assertRaises(current.ObservationError):
            current.make_packet(training, query)
        self.assertNotIn("PRIVATE-SENTINEL", current.render_text(packet()))

    def test_feature_and_episode_validation(self):
        for value in (True, float("nan"), float("inf"), "1", 10 ** 400):
            training, query = views()
            query["x_numeric_vector"][0] = value
            with self.subTest(value=type(value).__name__), self.assertRaises(current.ObservationError):
                current.make_packet(training, query)
        for mutate in (lambda q: q["x_numeric_vector"].pop(),
                       lambda q: q.update(opaque_episode_nonce="c" * 48),
                       lambda q: q.update(opaque_query_nonce="source-person-name")):
            training, query = views()
            mutate(query)
            with self.assertRaises(current.ObservationError):
                current.make_packet(training, query)
        training, query = views("NUISANCE")
        query["x_numeric_vector"][0] = 1
        with self.assertRaises(current.ObservationError):
            current.make_packet(training, query)

    def test_training_context_identity_changes_with_any_member(self):
        training, query = views()
        original = current.make_packet(training, query)
        training["features_member"]["sha256"] = "1" * 64
        changed = current.make_packet(training, query)
        self.assertNotEqual(original["training_view_identity"], changed["training_view_identity"])
        self.assertEqual(original["query"], changed["query"])

    def test_collection_is_accepted_by_existing_outcomes_parser(self):
        packets = [packet(key=key * 48) for key in ("b", "c", "d")]
        responses = [response("d" * 48, status="complete", p_face=.2), response(),
                     response("c" * 48, status="complete", p_face=1)]
        body = current.collect_responses(packets, responses)
        values, failures = legacy_collection.prediction_rows(body, "a" * 48, {x * 48 for x in "bcd"})
        self.assertEqual(values, {"b" * 48: .7, "c" * 48: 1, "d" * 48: .2})
        self.assertEqual(failures, [])
        self.assertEqual([r["opaque_query_nonce"] for r in body["outcomes"]], [x * 48 for x in "bcd"])

    def test_missing_abstained_and_failed_responses_are_retained(self):
        packets = [packet(key=key * 48) for key in ("b", "c", "d")]
        body = current.collect_responses(packets, [response(status="abstain", reason="uncertain"),
                                                   response("c" * 48, status="failed", reason="time limit")])
        values, failures = legacy_collection.prediction_rows(body, "a" * 48, {x * 48 for x in "bcd"})
        self.assertEqual(values, dict.fromkeys([x * 48 for x in "bcd"], None))
        self.assertEqual(len(failures), 3)
        self.assertEqual([r["reason"] for r in body["outcomes"]], ["uncertain", "time limit", "missing_response"])
        self.assertEqual(len(current.collect_responses(packets, [])["outcomes"]), 3)

    def test_no_duplicate_unknown_or_malformed_response_is_discarded(self):
        for responses in ([response(), response()], [response("c" * 48)],
                          [response(status="complete", p_face=True)],
                          [response(status="complete", p_face=float("nan"))],
                          [response(status="complete", p_face=1.1)],
                          [response(status="failed", reason="")],
                          [{**response(), "y": 1}], [{**response(), "opaque_episode_nonce": "d" * 48}]):
            with self.subTest(responses=responses), self.assertRaises(current.ObservationError):
                current.collect_responses([packet()], responses)

    def test_collection_requires_same_context_and_exact_expected_roster(self):
        p = packet()
        for second in (copy.deepcopy(p), packet("PRE", "c" * 48)):
            with self.assertRaises(current.ObservationError):
                current.collect_responses([p, second], [])
        changed = packet(key="c" * 48)
        changed["training_view_identity"]["sha256"] = "1" * 64
        with self.assertRaises(current.ObservationError):
            current.collect_responses([p, changed], [])
        with self.assertRaises(current.ObservationError):
            current.collect_responses([], [])

    def test_cli_render_and_collect_preserve_original_files(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("N097_TEST_TMPDIR")) as temp:
            root = Path(temp)
            training, query = views()
            for name, value in (("training.json", training), ("query.json", query)):
                (root / name).write_bytes(current.canonical(value))
            argv = ["observation.py", "render", "--training-view", str(root / "training.json"),
                    "--query", str(root / "query.json"), "--packet", str(root / "packet.json"),
                    "--text", str(root / "card.txt")]
            with patch.object(sys, "argv", argv):
                current.main()
            self.assertEqual((root / "card.txt").read_text(), current.render_text(packet()))
            before = (root / "packet.json").read_bytes()
            with patch.object(sys, "argv", argv), self.assertRaises(current.ObservationError):
                current.main()
            self.assertEqual((root / "packet.json").read_bytes(), before)
            (root / "packets.json").write_bytes(current.canonical([json.loads(before)]))
            (root / "responses.json").write_bytes(current.canonical([response()]))
            with patch.object(sys, "argv", ["observation.py", "collect", "--packets", str(root / "packets.json"),
                                            "--responses", str(root / "responses.json"), "--output", str(root / "outcomes.json")]):
                current.main()
            self.assertEqual(json.loads((root / "outcomes.json").read_bytes()), current.collect_responses([packet()], [response()]))

    def test_duplicate_or_nonfinite_json_and_over_cap_refused(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("N097_TEST_TMPDIR")) as temp:
            path = Path(temp) / "bad.json"
            for body, cap in ((b'{"x":1,"x":2}', 100), (b'{"x":NaN}', 100), (b'[]', 1)):
                path.write_bytes(body)
                with self.assertRaises(current.ObservationError):
                    current.read_json(path, cap)


if __name__ == "__main__":
    unittest.main()
