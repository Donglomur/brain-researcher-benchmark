"""Generated full-shape operator evidence controls; no authentic input or fit."""
import copy
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cardiac_admission_generated", HERE / "admission.py")
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)


class CompleteDrawEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = A.load_contract()
        text = io.StringIO(newline="")
        writer = csv.writer(text)
        writer.writerow(cls.contract["columns"])
        for n in range(1, 656):
            writer.writerow([n - 1, "invented-" + str(n), n, 0.5 * n - 7, 2 * n + 1, -n + 3])
        cls.csv = text.getvalue().encode()
        table = A.parse_complete_table(cls.csv, cls.contract)
        # This pure-helper fixture is not original-input admission.
        cls.prepared = {"contract": cls.contract, "models": A.prepare_models(table, cls.contract)}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cardiac-generated-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.root = self.home / "draws"
        self.root.mkdir()
        self.manifest = {"schema": "cardiac_operator_draw_review_v1", "benchmark_id": A.TASK,
            "input_sha256": self.contract["input"]["sha256"],
            "participant_id_sha256": self.contract["participant_id_hash"], "models": {}}
        for role in ("producer", "environment_record", "execution_record"):
            self.manifest[role] = self.write(role + ".txt", ("invented, unexecuted " + role).encode())
        for index, (name, prepared) in enumerate(self.prepared["models"].items()):
            xm = prepared["scales"]["x_mean"]
            ac = [1 + index / 10 + j / 10000 for j in range(8000)]
            beta = [0.1 + index / 100 + (j % 51) / 10000 for j in range(8000)]
            values = {"alpha_c": ac, "beta": beta,
                "sigma": [1 + (j % 25) / 1000 for j in range(8000)],
                "nu": [5 + (j % 31) / 100 for j in range(8000)],
                "alpha": [a - xm * b for a, b in zip(ac, beta)]}
            self.manifest["models"][name] = {"fit_id": "invented-fit-" + str(index),
                "seed": None, "requested_tune_per_chain": 2000, "draws": {}}
            for variable, array in values.items():
                filename = name + "--" + variable + ".f64"
                self.manifest["models"][name]["draws"][variable] = {
                    "encoding": "float64-le-chain-major", "shape": [4, 2000],
                    "artifact": self.write(filename, struct.pack("<8000d", *array))}
        self.save_manifest()
        self.first = next(iter(self.manifest["models"]))

    def write(self, name, raw):
        (self.root / name).write_bytes(raw)
        return {"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

    def save_manifest(self):
        (self.root / "draws.json").write_bytes(A.encoded(self.manifest))

    def stream(self, variable="beta"):
        return self.manifest["models"][self.first]["draws"][variable]

    def mutate_stream(self, variable, at, value):
        d = self.stream(variable)
        values = list(struct.unpack("<8000d", (self.root / d["artifact"]["path"]).read_bytes()))
        values[at] = value
        d["artifact"] = self.write(d["artifact"]["path"], struct.pack("<8000d", *values))
        self.save_manifest()

    def review(self):
        return A.review_draws(self.prepared, self.root)

    def test_complete_shape_current_scorer_and_ungranted_authority(self):
        body, report = self.review()
        summary = json.loads(body)
        scorer = A.load_current_scorer()
        scorer.validate(summary)
        self.assertEqual(scorer.score(summary, summary)["primary_beta_mean_rmse_reference_sd"], 0)
        self.assertEqual(report["retained_draw_values"], 240000)
        self.assertEqual(len(report["models"]), 6)
        for field in ("reference_accepted", "independently_fitted_reference_verified", "data_dependence_verified",
                      "tuning_verified", "convergence_verified", "custody_verified", "runtime_qualified", "scientific_qualified"):
            self.assertIs(report[field], False)
        for row in summary["models"].values():
            self.assertEqual(set(row["summary"]), set(A.VARIABLES))
            self.assertIsNone(row["diagnostics"]["tune_per_chain"])
            self.assertIsNone(row["diagnostics"]["max_rhat"])

    def test_missing_parameter_refuses(self):
        del self.manifest["models"][self.first]["draws"]["alpha"]
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "five draw"):
            self.review()

    def test_missing_sixth_model_refuses(self):
        self.manifest["models"].pop(next(reversed(self.manifest["models"])))
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "six models"):
            self.review()

    def test_duplicate_stream_role_refuses(self):
        self.manifest["models"][self.first]["draws"]["alpha"] = copy.deepcopy(self.stream("alpha_c"))
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "distinct"):
            self.review()

    def test_zero_sigma_refuses(self):
        self.mutate_stream("sigma", 7999, 0.0)
        with self.assertRaisesRegex(ValueError, "positive sigma"):
            self.review()

    def test_negative_nu_refuses(self):
        self.mutate_stream("nu", 7999, -0.01)
        with self.assertRaisesRegex(ValueError, "positive sigma"):
            self.review()

    def test_nonfinite_final_draw_refuses(self):
        self.mutate_stream("alpha", 7999, math.nan)
        with self.assertRaisesRegex(ValueError, "finite complete"):
            self.review()

    def test_float_shape_counts_refuse(self):
        self.stream()["shape"] = [4.0, 2000]
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "full shape"):
            self.review()

    def test_truncated_shape_refuses_even_with_matching_pin(self):
        d = self.stream()["artifact"]
        self.stream()["artifact"] = self.write(d["path"], (self.root / d["path"]).read_bytes()[:-8])
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "complete distinct"):
            self.review()

    def test_extra_draw_refuses(self):
        d = self.stream()["artifact"]
        self.stream()["artifact"] = self.write(d["path"], (self.root / d["path"]).read_bytes() + struct.pack("<d", 1))
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "bounded declared"):
            self.review()

    def test_wrong_input_join_precedes_producer_read(self):
        self.manifest["input_sha256"] = "0" * 64
        (self.root / self.manifest["producer"]["path"]).unlink()
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "input/cohort join"):
            self.review()

    def test_false_tuning_claim_type_refuses(self):
        self.manifest["models"][self.first]["requested_tune_per_chain"] = True
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "tuning prescription"):
            self.review()

    def test_duplicate_fit_identity_refuses(self):
        names = list(self.manifest["models"])
        self.manifest["models"][names[1]]["fit_id"] = self.manifest["models"][names[0]]["fit_id"]
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "distinct declared"):
            self.review()

    def test_changed_producer_refuses(self):
        (self.root / self.manifest["producer"]["path"]).write_bytes(b"different producer")
        with self.assertRaises(ValueError):
            self.review()

    def test_escaping_draw_path_refuses(self):
        self.stream()["artifact"]["path"] = "../outside.f64"
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "canonical relative"):
            self.review()

    def test_alpha_identity_discrepancy_is_reported_without_invented_threshold(self):
        d = self.stream("alpha")["artifact"]
        old = struct.unpack("<8000d", (self.root / d["path"]).read_bytes())[7999]
        self.mutate_stream("alpha", 7999, old + 0.01)
        _, report = self.review()
        row = report["models"][self.first]
        self.assertAlmostEqual(row["alpha_identity_max_absolute_error"], 0.01)
        self.assertEqual(row["alpha_identity_nonzero_binary64_differences"], 1)
        self.assertIsNone(row["alpha_identity_acceptance_tolerance"])
        self.assertIs(report["reference_accepted"], False)

    def test_constant_draws_fail_unchanged_reference_schema(self):
        d = self.stream()["artifact"]
        self.stream()["artifact"] = self.write(d["path"], struct.pack("<8000d", *([1.] * 8000)))
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "positive SD"):
            self.review()

    def test_operator_outputs_are_private_and_do_not_overwrite(self):
        out = A.fresh_directory(self.home / "output", [A.ROOT, self.root])
        A.write_private(out / "check.json", b"{}\n")
        self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((out / "check.json").stat().st_mode), 0o600)
        with self.assertRaises(FileExistsError):
            A.write_private(out / "check.json", b"replacement")
        with self.assertRaises(ValueError):
            A.fresh_directory(out, [A.ROOT, self.root])

    def test_cli_rejects_generated_input_without_output(self):
        csv_path = self.home / "generated.csv"
        csv_path.write_bytes(self.csv)
        out = self.home / "must-not-exist"
        result = subprocess.run([sys.executable, "-I", "-S", "-B", str(HERE / "admission.py"),
            "inspect-input", "--csv", str(csv_path), "--out", str(out)], text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "refused")
        self.assertFalse(out.exists())

    def test_cli_authenticates_current_source_only(self):
        result = subprocess.run([sys.executable, "-I", "-S", "-B", str(HERE / "admission.py"), "verify-source"],
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(len(report["dependencies"]), 5)
        self.assertIs(report["scientific_qualified"], False)

    def test_case_alias_cannot_reuse_physical_artifact(self):
        original = self.root / self.manifest["producer"]["path"]
        alias = original.with_name(original.name.upper())
        if not alias.exists():
            # On a case-sensitive filesystem a true hardlink is also refused.
            os.link(original, alias)
        self.manifest["environment_record"] = {
            **self.manifest["producer"], "path": alias.name}
        self.save_manifest()
        with self.assertRaises(ValueError):
            self.review()

    def test_dotdot_cannot_bypass_output_source_separation(self):
        (self.home / "escape").mkdir()
        out = self.home / "escape" / ".." / "draws" / "forbidden"
        with self.assertRaisesRegex(ValueError, "canonical absolute"):
            A.fresh_directory(out, [self.root])
        self.assertFalse((self.root / "forbidden").exists())

    def test_subnormal_summary_mean_uses_full_sum(self):
        chains = [[1e-320] * 2000, [1e-320] * 2000, [2e-320] * 2000, [2e-320] * 2000]
        row = A.summarize_chains(chains)
        self.assertEqual(row["mean"], 1.5e-320)
        self.assertEqual(row["sd_population"], 5e-321)

    def test_all_source_density_probes_keep_positive_transform_jacobian(self):
        probes = A.prepare_density_probes(self.prepared["models"])
        self.assertEqual(set(probes), set(self.prepared["models"]))
        self.assertEqual(sum(map(len, probes.values())), 18)
        for rows in probes.values():
            for row in rows:
                point = row["natural_point"]
                self.assertAlmostEqual(
                    row["expected_log_density_with_log_sigma_nu_jacobian"] - row["expected_log_density"],
                    math.log(point["sigma"]) + math.log(point["nu"]), places=10)

    def test_independent_closed_form_nu_six_density_expectations(self):
        model = self.prepared["models"]["raw__ECG_not_rejected"]
        sigma = 2 * math.sqrt(35752)
        # Independent reviewer reduced Gamma(7/2)/Gamma(3) and HalfT(4)
        # normalizers analytically; no candidate formula/helper supplied these values.
        expected = [-4537.981254846294, -4891.391642583693]
        for ac, value in zip((657, 657 + sigma), expected):
            self.assertAlmostEqual(A.log_density(model, ac, 2, sigma, 6), value, places=9)


if __name__ == "__main__":
    unittest.main()
