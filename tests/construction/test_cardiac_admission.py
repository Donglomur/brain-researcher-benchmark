"""Independent generated controls for full-cohort cardiac preparation.

The arithmetic expectations below come from finite arithmetic-sequence sums,
not from the implementation's moment or summary helpers. These invented rows
are intentionally rejected by the production authentic-input gate. No fitting,
original participant data, protected reference or native execution is used.
"""

import csv
import importlib.util
import io
import math
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / (
    "benchmarks/paper/PAPER-ROOT-ADD-016/implementations/"
    "full-cohort-admission-v1/admission.py"
)


def generated_rows():
    """655 invented identifiers and values with closed-form column moments."""
    return [
        [str(i), f"invented-{i:04d}", i + 1, (i + 1) / 2 - 7,
         2 * (i + 1) + 1, -(i + 1) + 3]
        for i in range(655)
    ]


def csv_bytes(rows, columns=None):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(columns or [
        "", "subject_id", "age", "ECG_components",
        "ECG_not_rejected", "ECG_rejected",
    ])
    writer.writerows(rows)
    return stream.getvalue().encode("utf8")


class CardiacAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        name = "_independent_cardiac_admission_controls"
        spec = importlib.util.spec_from_file_location(name, MODULE)
        cls.admission = importlib.util.module_from_spec(spec)
        sys.modules[name] = cls.admission
        previous_bytecode = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            spec.loader.exec_module(cls.admission)
        finally:
            sys.dont_write_bytecode = previous_bytecode
        cls.contract = cls.admission.load_contract()

    def table(self, rows=None):
        return self.admission.parse_complete_table(
            csv_bytes(generated_rows() if rows is None else rows), self.contract)

    def test_complete_generated_support_is_preserved(self):
        table = self.table()
        self.assertEqual(len(table["participant_ids"]), 655)
        self.assertEqual(table["participant_ids"][0], "invented-0000")
        self.assertEqual(table["participant_ids"][-1], "invented-0654")
        self.assertEqual(table["columns"]["age"], list(range(1, 656)))
        self.assertEqual(set(table["columns"]), {
            "age", "ECG_components", "ECG_not_rejected", "ECG_rejected"})

    def test_model_preparation_matches_independent_arithmetic_sequences(self):
        models = self.admission.prepare_models(self.table(), self.contract)
        conditions = {
            "ECG_not_rejected": (2.0, 1.0),
            "ECG_rejected": (-1.0, 3.0),
            "ECG_components": (0.5, -7.0),
        }
        self.assertEqual(set(models), {
            scale + "__" + condition
            for scale in ("raw", "zscore") for condition in conditions
        })
        # For the integers 1,...,655, mean=(n+1)/2 and variance=(n^2-1)/12.
        mean, variance = 328.0, 35752.0
        sd = math.sqrt(variance)
        for condition, (slope, intercept) in conditions.items():
            with self.subTest(condition=condition, scale="raw"):
                model = models["raw__" + condition]
                self.assertEqual(model["x"], list(range(1, 656)))
                self.assertEqual(model["y"], [slope * x + intercept
                                            for x in range(1, 656)])
                expected = {
                    "x_mean": mean, "y_mean": slope * mean + intercept,
                    "x_sd": sd, "y_sd": abs(slope) * sd,
                    "beta_sd": 2.5 * abs(slope),
                    "alpha_c_sd": 2.5 * abs(slope) * math.sqrt(variance + mean**2),
                }
                for key, value in expected.items():
                    self.assertAlmostEqual(model["scales"][key], value,
                                           delta=1e-11 * max(1.0, abs(value)))
            with self.subTest(condition=condition, scale="zscore"):
                model = models["zscore__" + condition]
                self.assertEqual(len(model["x"]), 655)
                self.assertEqual(len(model["y"]), 655)
                sign = 1 if slope > 0 else -1
                for i, (x, y) in enumerate(zip(model["x"], model["y"])):
                    expected_x = (i + 1 - mean) / sd
                    self.assertAlmostEqual(x, expected_x, delta=1e-12)
                    self.assertAlmostEqual(y, sign * expected_x, delta=1e-12)
                for key, value in {
                    "x_mean": 0.0, "y_mean": 0.0, "x_sd": 1.0,
                    "y_sd": 1.0, "beta_sd": 2.5, "alpha_c_sd": 2.5,
                }.items():
                    self.assertAlmostEqual(model["scales"][key], value, delta=1e-12)

    def test_last_row_contributes_to_preparation(self):
        rows = generated_rows()
        rows[-1][2] += 655
        models = self.admission.prepare_models(self.table(rows), self.contract)
        for condition in ("ECG_not_rejected", "ECG_rejected", "ECG_components"):
            with self.subTest(condition=condition):
                self.assertEqual(models["raw__" + condition]["x"][-1], 1310)
                self.assertAlmostEqual(models["raw__" + condition]["scales"]["x_mean"],
                                       329.0, delta=1e-12)

    def test_natural_parameter_density_matches_closed_form_normalizers(self):
        # These inputs and prior scales come from independent sequence sums.
        # alpha_c + beta * (x - 328) = 657 + 2 * (x - 328) = 2*x + 1,
        # so all 655 likelihood residuals are exactly zero.
        sigma = math.sqrt(143008.0)
        alpha_sd = math.sqrt(3583400.0)
        prepared = {
            "x": list(range(1, 656)),
            "y": [2 * x + 1 for x in range(1, 656)],
            "scales": {
                "x_mean": 328.0, "y_mean": 657.0,
                "x_sd": math.sqrt(35752.0), "y_sd": sigma,
                "beta_sd": 5.0, "alpha_c_sd": alpha_sd,
            },
        }
        # t_2(0; scale=sigma) = 1/(2*sqrt(2)*sigma).
        # The two Normal priors contribute 1/(2*pi*alpha_sd*5)*exp(-.08).
        # Half-t_4(sigma; scale=sigma) = .75/sigma * (1.25)^(-5/2).
        # Gamma(shape=2, rate=.1) at nu=2 = .02*exp(-.2).
        # These closed forms do not call lgamma or any implementation helper,
        # and no log-sigma/log-nu coordinate Jacobian belongs to this density.
        expected = (
            -655 * math.log(2 * math.sqrt(2) * sigma)
            - math.log(2 * math.pi * alpha_sd * 5) - 0.08
            + math.log(0.75 / sigma) - 2.5 * math.log(1.25)
            + math.log(0.02) - 0.2
        )
        observed = self.admission.log_density(prepared, 657.0, 2.0, sigma, 2.0)
        self.assertAlmostEqual(observed, expected, delta=16 * math.ulp(expected))

    def test_incomplete_and_extra_rows_refuse(self):
        rows = generated_rows()
        for bad in (rows[:-1], rows + [["655", "invented-0655", 656, 321, 1313, -653]]):
            with self.subTest(rows=len(bad)), self.assertRaises(ValueError):
                self.table(bad)

    def test_duplicate_participant_refuses(self):
        rows = generated_rows()
        rows[-1][1] = rows[0][1]
        with self.assertRaises(ValueError):
            self.table(rows)

    def test_missing_and_surplus_csv_cells_refuse(self):
        for change in ("missing", "extra"):
            rows = generated_rows()
            rows[-1] = rows[-1][:-1] if change == "missing" else rows[-1] + ["extra"]
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.table(rows)

    def test_wrong_column_mapping_refuses(self):
        columns = ["", "subject_id", "age", "ECG_components",
                   "ECG_rejected", "ECG_not_rejected"]
        with self.assertRaises(ValueError):
            self.admission.parse_complete_table(csv_bytes(generated_rows(), columns),
                                                self.contract)

    def test_nonfinite_column_tail_refuses(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            for column in range(2, 6):
                rows = generated_rows()
                rows[-1][column] = value
                with self.subTest(value=value, column=column), self.assertRaises(ValueError):
                    self.table(rows)

    def test_constant_columns_refuse(self):
        for column in range(2, 6):
            rows = generated_rows()
            for row in rows:
                row[column] = 1
            with self.subTest(column=column), self.assertRaises(ValueError):
                self.admission.prepare_models(self.table(rows), self.contract)

    def test_production_identity_gate_rejects_complete_generated_table(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "meg_slope_data_sbg.csv"
            path.write_bytes(csv_bytes(generated_rows()))
            with self.assertRaises(ValueError):
                self.admission.inspect_input(path)

    def test_exact_draw_summary_matches_closed_form_moments_and_tie_rule(self):
        result = self.admission.summarize_chains([list(range(2000)) for _ in range(4)])
        # Pooled order statistics repeat every integer four times. Every
        # 7,520-index window has width 1,880, so the earliest starts at zero.
        self.assertEqual(result["mean"], 999.5)
        self.assertAlmostEqual(result["sd_population"], math.sqrt(333333.25), delta=1e-12)
        self.assertEqual(result["hdi_94_low"], 0.0)
        self.assertEqual(result["hdi_94_high"], 1880.0)
        # Eighty batch means repeat 49.5,149.5,...,1949.5 four times.
        self.assertAlmostEqual(result["mcse_mean_batch"], math.sqrt(332500.0 / 79),
                               delta=1e-12)

    def test_skew_mean_outside_shortest_interval_is_preserved(self):
        chain = [0.0] * 1900 + [100.0] * 100
        result = self.admission.summarize_chains([list(chain) for _ in range(4)])
        self.assertEqual(result["mean"], 5.0)
        self.assertAlmostEqual(result["sd_population"], math.sqrt(475.0), delta=1e-12)
        self.assertEqual((result["hdi_94_low"], result["hdi_94_high"]), (0.0, 0.0))
        self.assertAlmostEqual(result["mcse_mean_batch"], math.sqrt(475.0 / 79), delta=1e-12)

    def test_constant_summary_reports_zero_dispersion_without_invented_jitter(self):
        result = self.admission.summarize_chains([[3.0] * 2000 for _ in range(4)])
        self.assertEqual(result, {
            "mean": 3.0, "sd_population": 0.0, "hdi_94_low": 3.0,
            "hdi_94_high": 3.0, "mcse_mean_batch": 0.0,
        })

    def test_chain_shape_must_be_four_by_two_thousand(self):
        for chains in (
            [[0.0] * 2000 for _ in range(3)],
            [[0.0] * 2000 for _ in range(5)],
            [[0.0] * 1999 for _ in range(4)],
            [[0.0] * 2001 for _ in range(4)],
            [[0.0] * 2000 for _ in range(3)] + [[0.0] * 1999],
        ):
            with self.subTest(shape=[len(x) for x in chains]), self.assertRaises(ValueError):
                self.admission.summarize_chains(chains)

    def test_last_draw_nonfinite_refuses(self):
        for value in (math.nan, math.inf, -math.inf):
            chains = [[0.0] * 2000 for _ in range(4)]
            chains[-1][-1] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.admission.summarize_chains(chains)

    def test_json_duplicate_keys_and_nonfinite_constants_refuse(self):
        for body in (b'{"x":1,"x":2}', b'{"x":{"y":1,"y":2}}',
                     b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.admission.decode(body)

    def test_regular_file_reader_enforces_size_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "source.bin"
            path.write_bytes(b"abcde")
            self.assertEqual(self.admission.read_regular(path, 5), b"abcde")
            with self.assertRaises(ValueError):
                self.admission.read_regular(path, 4)

    def test_regular_file_reader_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory).resolve() / "source.bin"
            link = Path(directory).resolve() / "alias.bin"
            source.write_bytes(b"abcde")
            link.symlink_to(source)
            with self.assertRaises(ValueError):
                self.admission.read_regular(link, 5)


if __name__ == "__main__":
    unittest.main()
