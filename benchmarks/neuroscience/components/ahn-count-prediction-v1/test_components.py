"""Invented controls only; no original AHN data or model fitting."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
def module(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj
S = module("predictive_score")
V = module("verify_release")


def fixture():
    animals = [{"id": group + str(i), "group": group} for group, n in S.GROUPS.items() for i in range(n)]
    regions = ["AHN"] + ["invented-region-" + str(i) for i in range(451)]
    roster = {"schema": "ahn-evaluator-roster-v1", "animals": animals, "regions": regions,
              "binding": {"input_manifest_sha256": "0" * 64, "cohort_review_sha256": "1" * 64}}
    truth = {"schema": "ahn-count-truth-v1", "rows": [{"animal": a["id"], "region": r, "count": 1} for a in animals for r in regions]}
    pred = {"schema": "ahn-nb-predictions-v1", "rows": [{"animal": a["id"], "region": r, "mean": 1.0, "size": 1.0} for a in animals for r in regions]}
    return roster, truth, pred


class Scoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster, cls.truth, cls.pred = fixture()

    def test_complete_full_population_and_group_denominators(self):
        out = S.score(self.roster, self.truth, self.pred)
        self.assertEqual((out["animals"], out["regions"], out["targets"]), (28, 452, 12656))
        self.assertAlmostEqual(out["primary"], -math.log(4), places=13)
        self.assertEqual({k: v["animals"] for k, v in out["by_group"].items()}, S.GROUPS)
        self.assertFalse(out["protected_runner_verified"])

    def test_geometric_distribution_analytic_values(self):
        for k in (0, 1, 5, 128, 129, 999):
            self.assertAlmostEqual(S.nb_logpmf(k, 3, 1), -math.log(4) + k * math.log(.75), places=10)

    def test_zero_count_and_large_dispersion_stability(self):
        self.assertAlmostEqual(S.nb_logpmf(0, 2, 4), 4 * math.log(2 / 3), places=13)
        self.assertAlmostEqual(S.nb_logpmf(3, 2, 1e12), -2 + 3 * math.log(2) - math.lgamma(4), places=9)

    def test_bad_distribution_parameters_and_counts_refuse(self):
        for args in [(True, 1, 1), (-1, 1, 1), (1.0, 1, 1), (1, 0, 1), (1, 1, 0), (1, True, 1), (1, float("inf"), 1), (1, 1, float("nan"))]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                S.nb_logpmf(*args)

    def test_missing_and_duplicate_rows_refuse(self):
        p = copy.deepcopy(self.pred)
        p["rows"].pop()
        with self.assertRaises(ValueError): S.score(self.roster, self.truth, p)
        p["rows"].append(copy.deepcopy(p["rows"][0]))
        with self.assertRaises(ValueError): S.score(self.roster, self.truth, p)

    def test_unknown_animal_region_and_extra_fields_refuse(self):
        for key, value in [("animal", "unknown"), ("region", "unknown"), ("answer", 1)]:
            p = copy.deepcopy(self.pred);p["rows"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                S.score(self.roster, self.truth, p)

    def test_changed_group_or_missing_control_animal_refuses(self):
        r = copy.deepcopy(self.roster);r["animals"][0]["group"] = "NS"
        with self.assertRaises(ValueError): S.score(r, self.truth, self.pred)
        r = copy.deepcopy(self.roster);r["animals"].pop()
        with self.assertRaises(ValueError): S.score(r, self.truth, self.pred)

    def test_duplicate_region_and_missing_ahn_refuse(self):
        for replacement in ("invented-region-0", "other"):
            r = copy.deepcopy(self.roster);r["regions"][0] = replacement
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                S.score(r, self.truth, self.pred)

    def test_row_permutation_does_not_change_score(self):
        p = {"schema": self.pred["schema"], "rows": list(reversed(self.pred["rows"]))}
        self.assertEqual(S.score(self.roster, self.truth, p), S.score(self.roster, self.truth, self.pred))

    def test_all_animals_and_regions_contribute(self):
        p = copy.deepcopy(self.pred)
        for row in p["rows"]:
            if row["animal"] == "Ctrl0": row["mean"] = 9
        out = S.score(self.roster, self.truth, p)
        expected = (27 * S.nb_logpmf(1, 1, 1) + S.nb_logpmf(1, 9, 1)) / 28
        self.assertAlmostEqual(out["primary"], expected, places=13)
        self.assertNotEqual(out["by_group"]["Ctrl"]["mean_log_predictive_density"], out["by_group"]["NS"]["mean_log_predictive_density"])

    def test_paired_difference_requires_same_animal_group_and_region(self):
        out = S.score(self.roster, self.truth, self.pred)
        self.assertEqual(S.paired_difference(out, out)["delta_mean_lpd"], 0)
        bad = copy.deepcopy(out);bad["by_animal"][0]["group"] = "S"
        with self.assertRaises(ValueError): S.paired_difference(out, bad)

    def test_strict_json_duplicate_and_nonfinite_constants(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.json"
            for body in ('{"a":1,"a":2}', '{"a":NaN}'):
                p.write_text(body)
                with self.assertRaises(ValueError): S.load(p, 100)

    def test_above_128_counts_at_extreme_size_match_poisson_limit(self):
        for k in (129, 1000):
            for size in (1e16, 1e300):
                expected = -k + k * math.log(k) - math.lgamma(k + 1)
                self.assertAlmostEqual(S.nb_logpmf(k, k, size), expected, places=8)

    def test_nb_size_two_exact_probability(self):
        for k in (129, 1000):
            expected = math.log(k + 1) + 2 * math.log(2 / 5) + k * math.log(3 / 5)
            self.assertAlmostEqual(S.nb_logpmf(k, 3, 2), expected, places=10)

    def test_tiny_size_large_mean_and_underflow_ratio(self):
        self.assertAlmostEqual(S.nb_logpmf(129, 1e300, 1e-300), math.log(1e-300) - math.log(129), places=10)
        self.assertEqual(S.nb_logpmf(0, 1e-300, 1e300), -1e-300)
        with self.assertRaises(ValueError):
            S.nb_logpmf(1000001, 1, 1)

    def test_paired_comparison_refuses_changed_binding_or_truth(self):
        baseline = S.score(self.roster, self.truth, self.pred)
        changed = copy.deepcopy(self.roster);changed["binding"]["input_manifest_sha256"] = "2" * 64
        candidate = S.score(changed, self.truth, self.pred)
        with self.assertRaises(ValueError): S.paired_difference(candidate, baseline)
        changed_truth = copy.deepcopy(self.truth);changed_truth["rows"][0]["count"] = 2
        candidate = S.score(self.roster, changed_truth, self.pred)
        with self.assertRaises(ValueError): S.paired_difference(candidate, baseline)


class ReleaseIntegrity(unittest.TestCase):
    def test_git_blob_includes_header_and_sha256(self):
        with tempfile.TemporaryDirectory() as d:
            d = str(Path(d).resolve())
            p = Path(d) / "input.csv";b = b"x,y\n1,2\n";p.write_bytes(b)
            oid = hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()
            row = V.verify_one(d, "input.csv", len(b), oid)
            self.assertEqual(row["sha256"], hashlib.sha256(b).hexdigest())
            with self.assertRaises(ValueError): V.verify_one(d, "input.csv", len(b), "0" * 40)

    def test_symlink_hardlink_wrong_extent_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            d = str(Path(d).resolve())
            p = Path(d) / "x";p.write_bytes(b"abc")
            q = Path(d) / "y";q.symlink_to(p)
            oid = hashlib.sha1(b"blob 3\0abc").hexdigest()
            with self.assertRaises(ValueError): V.verify_one(d, "y", 3, oid)
            q.unlink();q.hardlink_to(p)
            with self.assertRaises(ValueError): V.verify_one(d, "x", 3, oid)
            q.unlink()
            with self.assertRaises(ValueError): V.verify_one(d, "x", 2, oid)

    def test_complete_fixed_release_manifest(self):
        self.assertEqual(len(V.FILES), 6)
        self.assertEqual(sum(row[1] for row in V.FILES), 2945407)
        self.assertFalse(any("STable" in row[0] or "Fig1" in row[0] for row in V.FILES))


if __name__ == "__main__":
    unittest.main()
