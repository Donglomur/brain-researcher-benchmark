"""Generated software controls only; no source neural data or model trials."""
import copy
import importlib.util
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("direct_delivery", HERE / "direct_delivery.py")
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def views(split="query"):
    count = {"query": 19, "fit": 73}[split]
    rows = []
    for i in range(count):
        token = f"{split}-{i:03}"
        rows.append({"id": "event-" + token, "mouse": "mouse-" + token,
                     "session": "session-" + token, "experiment": "plane-" + token,
                     "split": split, "previous": [
                         {"image": f"image-{j}", "omitted": False,
                          "start_relative_seconds": -2.25 + .75 * j} for j in range(3)],
                     "context": {"cre_line": "generated-cre", "targeted_structure": "VISp",
                                 "image_set": "generated", "experience_level": "Familiar",
                                 "passive": False, "imaging_depth": 175, "session_number": 1},
                     "history": [j / 100 for j in range(-11, 1)]})
        if split == "fit":
            rows[-1]["target"] = [i / 100, .2, -.3]
    neural = {"schema": "neural063_rows_v2", "split": split, "rows": rows}
    timing = copy.deepcopy(neural)
    for row in timing["rows"]:
        del row["history"]
    return timing, neural


def answers(bundle):
    return [{"request_sha256": r["request_sha256"], "id": r["id"],
             "information": r["information"], "values": [0.1, -0.2, 0.3]}
            for r in bundle["requests"]]


class DirectControls(unittest.TestCase):
    def setUp(self):
        self.t, self.n = views()

    def test_complete_pair_has_exact_views_units_and_bins(self):
        bundle = d.build(self.t, self.n)
        self.assertEqual(len(bundle["requests"]), 38)
        self.assertEqual(bundle["query_mice"], 19)
        self.assertEqual(bundle["exposure_condition"], "zero_shot")
        for i, (t, n) in enumerate(zip(bundle["requests"][::2], bundle["requests"][1::2])):
            self.assertEqual(t["observation"], self.t["rows"][i])
            self.assertEqual(n["observation"], self.n["rows"][i])
            self.assertNotIn("history_bins_seconds", t)
            self.assertNotIn("history", t["observation"])
            self.assertNotIn("target", n["observation"])
            self.assertEqual(n["history_bins_seconds"][0], [-2.4, -2.2])
            self.assertEqual(n["history_bins_seconds"][-1], [-.2, 0])
            self.assertEqual(n["target_bins_seconds"], [[0, .2], [.2, .4], [.4, .6]])
            self.assertEqual(t["units"], "dimensionless dF/F")
            self.assertEqual(t["id"], n["id"])
            self.assertNotEqual(t["request_sha256"], n["request_sha256"])

    def test_collection_uses_existing_scorer_shape(self):
        bundle = d.build(self.t, self.n)
        result = d.collect(bundle, answers(bundle), expected_bundle_sha256=d.digest(bundle))
        for info in ("T", "N"):
            ids = [row["id"] for row in self.t["rows"]]
            admitted = d.admit_predictions(result["predictions"][info], ids)
            self.assertEqual(len(admitted), 19)
            self.assertEqual(admitted[ids[0]], [.1, -.2, .3])

    def test_input_mutation_cannot_change_built_request(self):
        bundle = d.build(self.t, self.n)
        frozen = d.digest(bundle)
        self.n["rows"][0]["history"][0] = 42
        self.assertEqual(d.digest(bundle), frozen)

    def test_query_targets_and_extra_fields_fail_in_both_views(self):
        for view in ("T", "N"):
            for key, value in (("target", [1, 2, 3]), ("source_nwb", "forbidden")):
                t, n = views()
                (t if view == "T" else n)["rows"][0][key] = value
                with self.subTest(view=view, key=key), self.assertRaises(d.ContractError):
                    d.build(t, n)

    def test_mismatched_pair_is_not_silently_projected(self):
        self.t["rows"][0]["previous"][0]["image"] = "changed"
        with self.assertRaises(d.ContractError):
            d.build(self.t, self.n)

    def test_incomplete_or_reordered_query_schedule_fails(self):
        for mutation in (lambda r: r.pop(), lambda r: r.reverse(), lambda r: r.append(r[0])):
            t, n = views()
            mutation(t["rows"])
            mutation(n["rows"])
            with self.assertRaises(d.ContractError):
                d.build(t, n)

    def test_invalid_history_and_cadence_fail(self):
        for bad in (math.nan, True, 1e400, 10**400):
            t, n = views()
            n["rows"][0]["history"][0] = bad
            with self.assertRaises(d.ContractError):
                d.build(t, n)
        self.n["rows"][0]["history"][-1] = 1
        with self.assertRaises(d.ContractError):
            d.build(self.t, self.n)
        t, n = views()
        for view in (t, n):
            view["rows"][0]["previous"][0]["start_relative_seconds"] = -4
        with self.assertRaises(d.ContractError):
            d.build(t, n)

    def test_paired_fit_demonstrations_have_separate_exposure_condition(self):
        ft, fn = views("fit")
        selected = [ft["rows"][5]["id"], ft["rows"][0]["id"]]
        bundle = d.build(self.t, self.n, fit_timing=ft, fit_neural=fn, demonstration_ids=selected)
        self.assertEqual(bundle["exposure_condition"], "fixed_fit_demonstrations")
        for request in bundle["requests"]:
            demos = request["demonstrations"]
            self.assertEqual([r["id"] for r in demos], selected)
            self.assertEqual(demos[0]["target"], [.05, .2, -.3])
            self.assertEqual("history" in demos[0], request["information"] == "N")
        self.assertNotEqual(bundle["requests"][0]["request_sha256"],
                            d.build(self.t, self.n)["requests"][0]["request_sha256"])

    def test_demo_admission_rejects_overlap_absence_duplicates_and_zero_shot_targets(self):
        ft, fn = views("fit")
        ident = ft["rows"][0]["id"]
        cases = [dict(fit_timing=ft, fit_neural=fn),
                 dict(demonstration_ids=[ident]),
                 dict(fit_timing=ft, fit_neural=fn, demonstration_ids=["absent"]),
                 dict(fit_timing=ft, fit_neural=fn, demonstration_ids=[ident, ident])]
        for kwargs in cases:
            with self.assertRaises(d.ContractError):
                d.build(self.t, self.n, **kwargs)
        for source in (ft, fn):
            source["rows"][0]["mouse"] = self.t["rows"][0]["mouse"]
        with self.assertRaises(d.ContractError):
            d.build(self.t, self.n, fit_timing=ft, fit_neural=fn, demonstration_ids=[ident])

    def test_partial_swapped_and_wrong_binding_responses_fail(self):
        bundle = d.build(self.t, self.n)
        variants = []
        partial = answers(bundle); partial.pop(); variants.append(partial)
        swapped = answers(bundle); swapped[0], swapped[1] = swapped[1], swapped[0]; variants.append(swapped)
        rebound = answers(bundle); rebound[0]["request_sha256"] = "0" * 64; variants.append(rebound)
        extra = answers(bundle); extra[0]["explanation"] = "not a prediction"; variants.append(extra)
        for response in variants:
            with self.assertRaises(d.ContractError):
                d.collect(bundle, response, expected_bundle_sha256=d.digest(bundle))

    def test_nonfinite_bool_and_wrong_length_predictions_fail(self):
        bundle = d.build(self.t, self.n)
        for values in ([math.nan, 0, 0], [math.inf, 0, 0], [True, 0, 0], [0, 0], [10**400, 0, 0]):
            response = answers(bundle)
            response[0]["values"] = values
            with self.assertRaises(d.ContractError):
                d.collect(bundle, response, expected_bundle_sha256=d.digest(bundle))

    def test_bundle_tamper_and_duplicate_json_keys_fail(self):
        bundle = d.build(self.t, self.n)
        frozen = d.digest(bundle)
        bundle["requests"][0]["observation"]["context"]["imaging_depth"] = 200
        with self.assertRaises(d.ContractError):
            d.collect(bundle, answers(bundle), expected_bundle_sha256=frozen)
        with self.assertRaises(d.ContractError):
            d.decode('{"id":"first","id":"second"}')

    def test_cli_round_trip_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "t.json").write_bytes(d.canonical(self.t))
            (root / "n.json").write_bytes(d.canonical(self.n))
            common = ["--timing", str(root / "t.json"), "--neural", str(root / "n.json")]
            command = [sys.executable, "-I", "-B", str(HERE / "direct_delivery.py")]
            built = subprocess.run(command + ["build"] + common + ["--output", str(root / "requests.json")],
                                   capture_output=True, text=True, check=True)
            bundle = d.read_json(root / "requests.json")
            self.assertEqual(built.stdout.strip(), d.digest(bundle))
            (root / "responses.json").write_bytes(d.canonical(answers(bundle)))
            subprocess.run(command + ["collect"] + common + ["--responses", str(root / "responses.json"),
                           "--requests-sha256", built.stdout.strip(), "--output", str(root / "collected.json")],
                           capture_output=True, text=True, check=True)
            self.assertEqual(d.read_json(root / "collected.json")["events"], 19)
            repeat = subprocess.run(command + ["build"] + common + ["--output", str(root / "requests.json")],
                                    capture_output=True, text=True)
            self.assertNotEqual(repeat.returncode, 0)

    def test_cli_zero_shot_rejects_fit_before_open(self):
        result = subprocess.run([sys.executable, "-I", "-B", str(HERE / "direct_delivery.py"),
                                 "build", "--timing", "/unopened-query-T", "--neural", "/unopened-query-N",
                                 "--fit-timing", "/unopened-FIT-targets", "--output", "/unwritten"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("demonstrations require both FIT views", result.stderr)
        self.assertNotIn("FileNotFoundError", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
