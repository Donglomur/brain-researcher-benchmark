"""Generated controls only. No paper draws, recordings, or source fits."""
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate as ev
from metrics import Invalid, pccafa_metrics, spectrum


def raw(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def endpoints():
    return {c: {"psv_percent": 20 if c.startswith("across") else 10,
                "dshared": 5 if c.startswith("across") else 3} for c in ev.COMPONENTS}


def fixture():
    rows, candidates = [], []
    for n, i in ev.KEYS:
        identity = {"trials": n, "draw": i, "observations_sha256": hashlib.sha256(f"generated:{n}:{i}".encode()).hexdigest()}
        truth = endpoints()
        author = copy.deepcopy(truth)
        author["across_1"]["psv_percent"] += 2
        author["across_2"]["psv_percent"] -= 2
        author["within_1"]["dshared"] += 1
        author["within_2"]["dshared"] -= 1
        control = {c: {"psv_percent": 28, "dshared": 6} for c in ("across_1", "across_2")}
        rows.append({**identity, "truth": truth, "author": author, "pcca": control})
        candidates.append({**identity, "estimates": copy.deepcopy(truth)})
    support = {"schema": "pcca-fig3-support-v1", "task": ev.TASK,
               "preparation_sha256": "1" * 64, "protocol_sha256": "2" * 64, "rows": rows}
    candidate = {"schema": "pcca-fig3-submission-v1", "task": ev.TASK,
                 "support_sha256": hashlib.sha256(raw(support)).hexdigest(),
                 "condition": "paper_data", "rows": candidates}
    return support, candidate


class Figure3Tests(unittest.TestCase):
    def test_original_signed_area_pooling_and_separate_losses(self):
        prepared, candidate = fixture()
        report = ev.compare(raw(prepared), raw(candidate))
        curve = report["source_curves"][0]
        self.assertEqual(curve["signed_error"]["author"], {"mean": 0, "std_population": 2, "n_area_values": 60})
        self.assertEqual(curve["independent_datasets"], 30)
        self.assertEqual(curve["signed_error"]["pcca"]["mean"], 8)
        self.assertEqual(report["improvement_diagnostics"][0]["paired_differences_by_draw"], [-2] * 30)
        self.assertEqual(len(report["per_draw"]), 180)
        self.assertEqual(len(report["source_curves"]), 24)
        self.assertIsNone(report["reproduction_pass"])
        self.assertIsNone(report["improvement_pass"])
        self.assertNotIn("pcca", report["source_curves"][2]["signed_error"])

    def test_conditions_are_retained_and_inputs_identical(self):
        prepared, candidate = fixture()
        first = ev.compare(raw(prepared), raw(candidate))
        candidate["condition"] = "paper_data_author_code"
        second = ev.compare(raw(prepared), raw(candidate))
        self.assertEqual(first["source_curves"], second["source_curves"])
        self.assertNotEqual(first["condition"], second["condition"])

    def test_trial_conditions_do_not_mix(self):
        prepared, candidate = fixture()
        for row in candidate["rows"]:
            row["estimates"]["across_1"]["psv_percent"] += row["trials"] / 100
            row["estimates"]["across_2"]["psv_percent"] += row["trials"] / 100
        report = ev.compare(raw(prepared), raw(candidate))
        for curve in report["source_curves"]:
            if curve["component"] == "across" and curve["metric"] == "psv_percent":
                self.assertEqual(curve["signed_error"]["candidate"]["mean"], curve["trials"] / 100)

    def test_missing_reordered_and_wrong_observation_fail(self):
        prepared, original = fixture()
        for mutation in (lambda c: c["rows"].pop(),
                         lambda c: c["rows"].reverse(),
                         lambda c: c["rows"][0].update(observations_sha256="0" * 64)):
            candidate = copy.deepcopy(original)
            mutation(candidate)
            with self.assertRaises(Invalid):
                ev.compare(raw(prepared), raw(candidate))

    def test_exact_support_binding(self):
        prepared, candidate = fixture()
        with self.assertRaises(Invalid):
            ev.compare(raw(prepared) + b"\n", raw(candidate))

    def test_duplicate_support_observation_and_invented_pcca_within_fail(self):
        prepared, candidate = fixture()
        prepared["rows"][1]["observations_sha256"] = prepared["rows"][0]["observations_sha256"]
        with self.assertRaises(Invalid):
            ev.support(raw(prepared))
        prepared, candidate = fixture()
        prepared["rows"][0]["pcca"]["within_1"] = {"psv_percent": 10, "dshared": 3}
        with self.assertRaises(Invalid):
            ev.support(raw(prepared))

    def test_nonfinite_duplicate_bool_and_extra_fields_fail(self):
        for content in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.assertRaises(Invalid):
                ev.decode(content)
        for value in (True, -1, 101, float("inf")):
            obj = endpoints()
            obj["across_1"]["psv_percent"] = value
            with self.assertRaises(Invalid):
                ev.endpoint(obj)
        prepared, candidate = fixture()
        candidate["arbitrary_drop_mask"] = []
        with self.assertRaises(Invalid):
            ev.compare(raw(prepared), raw(candidate))

    def test_symlink_and_oversized_files_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "real"
            p.write_bytes(b"{}")
            symlink = Path(folder) / "link"
            symlink.symlink_to(p)
            with self.assertRaises(OSError):
                ev.read(symlink)
            p.write_bytes(b" " * (ev.CAP + 1))
            with self.assertRaises(Invalid):
                ev.read(p)

    def test_huge_json_integers_are_normal_refusals(self):
        prepared, candidate = fixture()
        candidate["rows"][-1]["estimates"]["across_1"]["psv_percent"] = 10 ** 1000
        with self.assertRaises(Invalid):
            ev.compare(raw(prepared), raw(candidate))
        with self.assertRaises(Invalid):
            ev.decode(b'{"value":' + b'1' * 6000 + b'}')

    def test_neuron_fraction_mean_differs_from_ratio_of_traces(self):
        # Fifteen neurons have total variance 2 and fifteen have total 10.
        # Mean channel fraction = (50 + 10)/2 = 30%; trace ratio = 1/6.
        params = {"W1": [[1.0] for _ in range(30)], "W2": [[1.0] for _ in range(30)],
                  "L1": [[] for _ in range(30)], "L2": [[] for _ in range(30)],
                  "psi1": [1.0] * 15 + [9.0] * 15, "psi2": [3.0] * 30}
        result = pccafa_metrics(params)
        self.assertEqual(result["across_1"], {"psv_percent": 30, "dshared": 1})
        self.assertEqual(result["across_2"], {"psv_percent": 25, "dshared": 1})
        self.assertEqual(result["within_1"], {"psv_percent": 0, "dshared": 0})

    def test_spectrum_rotation_and_source_boundary(self):
        original = [[math.sqrt(95), 0], [0, math.sqrt(5)]]
        root2 = math.sqrt(2)
        rotated = [[(a + b) / root2, (a - b) / root2] for a, b in original]
        self.assertEqual(spectrum(original)[1], 1)
        self.assertEqual(spectrum(rotated)[1], 1)
        self.assertEqual(spectrum([[math.sqrt(94.99999), 0], [0, math.sqrt(5.00001)]])[1], 2)
        with self.assertRaises(Invalid):
            spectrum([[0.0], [0.0]])

    def test_invalid_parameter_support(self):
        params = {"W1": [[1.0]] * 30, "W2": [[1.0]] * 30,
                  "L1": [[]] * 30, "L2": [[]] * 30, "psi1": [1.0] * 30, "psi2": [1.0] * 30}
        params["W2"] = [[1.0, 2.0]] * 30
        with self.assertRaises(Invalid):
            pccafa_metrics(params)
        params["W2"] = [[1.0]] * 30
        params["psi1"][0] = -1
        with self.assertRaises(Invalid):
            pccafa_metrics(params)


if __name__ == "__main__":
    unittest.main()
