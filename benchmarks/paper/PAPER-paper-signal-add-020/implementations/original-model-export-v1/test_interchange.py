"""Generated interchange controls only: no authentic data, fitted R objects or score."""
import copy
import csv
import importlib.util
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("erp_export", HERE / "finalize.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
WRITTEN_BYTES = 0


def write(path, data):
    global WRITTEN_BYTES
    if isinstance(data, str):
        data = data.encode()
    path.write_bytes(data)
    WRITTEN_BYTES += len(data)


def fixture():
    contract = {"models": {}, "public_input_files": []}
    for i in range(8):
        contract["public_input_files"].append({"path": f"public/table-{i}.csv", "bytes": 1, "sha256": "0" * 64, "rows": 8})
    models, prepared = {}, {}
    for name in bridge.RANDOM:
        fixed = ["(Intercept)", "abs_rpe_s", "abs_epe_valence_s", "abs_epe_arousal_s"]
        fixed += ["P2_offer_s", "P2_base_offer_s"] if name == "FRN" else [name + "_base_offer_s"]
        formula = bridge.OUTCOMES[name] + " ~ " + " + ".join(fixed[1:]) + " + (1 + " + " + ".join(bridge.RANDOM[name][1:]) + " | sub)"
        contract["models"][name] = {"terms": fixed, "formula": formula, "required_rows": 4, "required_participants": 2}
        numeric = [bridge.OUTCOMES[name]] + fixed[1:]
        rows = []
        for i, source in enumerate([1, 3, 5, 7]):
            row = {"source_row": str(source), "sub": "A" if i < 2 else "B", "trialGlobal": str(i % 2 + 1)}
            row.update({field: str((i + 1) * (j + 1) / 8) for j, field in enumerate(numeric)})
            rows.append(row)
        prepared[name] = rows
        covariance = [[2. if i == j else .25 for j in range(len(fixed))] for i in range(len(fixed))]
        models[name] = {
            "formula": formula, "REML": True, "weights": None, "offset": None,
            "fixed_design_verified": True, "random_design_verified": True,
            "random_group": "sub", "random_terms": bridge.RANDOM[name][:], "group_levels": ["A", "B"],
            "frame": {field: [float(r[field]) for r in rows] for field in numeric},
            "native_frame_row_names": ["2", "4", "6", "8"],
            "operator_bound_source_rows": [1, 3, 5, 7],
            "terms": fixed[:], "coefficients": [i / 4 for i in range(len(fixed))], "covariance": covariance,
            "diagnostics": {"singular": False, "fitted_call": "generated fixture; no R object", "convergence_code": 0,
                            "optimizer": "generated", "optimizer_control": {}, "convergence_messages": None, "optimizer_warnings": None},
        }
        models[name]["frame"]["sub"] = [r["sub"] for r in rows]
    export = {"schema": "erp-original-model-export/v1", "source_revision": bridge.REVISION,
              "binding_basis": "operator_supplied_original_source_rows",
              "export_runtime": {"R": "generated fixture", "packages": {"lme4": "fixture", "jsonlite": "fixture"}},
              "models": models}
    return export, prepared, contract


class InterchangeTests(unittest.TestCase):
    def setUp(self):
        self.export, self.prepared, self.contract = fixture()

    def validate(self):
        return bridge.validate_export(self.export, self.prepared, self.contract)

    def test_exact_abi_and_separate_native_row_names(self):
        summary, provenance = self.validate()
        self.assertEqual(set(summary), {"schema_version", "candidate_id", "input_manifest_sha256", "analysis_family", "method", "models", "P3b_report"})
        for name in summary["models"]:
            self.assertEqual(set(summary["models"][name]), {"terms", "coefficients", "covariance", "retained_source_rows"})
            self.assertEqual(summary["models"][name]["retained_source_rows"], [1, 3, 5, 7])
            self.assertNotIn("native_frame_row_names", summary["models"][name])
            self.assertEqual(provenance[name]["participants"], 2)
        self.assertEqual(json.loads(bridge.canonical(summary)), summary)

    def test_covariance_and_tail_conventions_are_distinct(self):
        summary, _ = self.validate()
        report = summary["P3b_report"]
        self.assertAlmostEqual(report["estimate"], .25)
        self.assertAlmostEqual(report["full_covariance_se"], math.sqrt(3.5))
        self.assertAlmostEqual(report["historical_independence_se"], 2.)
        self.assertAlmostEqual(report["full_covariance_two_sided_normal_p"], math.erfc(.25 / math.sqrt(3.5) / math.sqrt(2)))
        self.assertAlmostEqual(report["historical_single_normal_tail_p"], .5 * math.erfc(.125 / math.sqrt(2)))

    def test_native_warning_and_optimizer_retained_in_method(self):
        self.export["models"]["FRN"]["diagnostics"].update(
            optimizer="bobyqa", optimizer_control={"maxfun": 200000},
            convergence_messages="generated warning", optimizer_warnings=["generated optimizer warning"])
        summary, provenance = self.validate()
        self.assertIn("generated warning", summary["method"])
        self.assertIn("generated optimizer warning", summary["method"])
        self.assertIn('"maxfun":200000', summary["method"])
        self.assertEqual(provenance["FRN"]["native_diagnostics"]["optimizer"], "bobyqa")

    def test_missing_diagnostics_refused_but_explicit_null_preserved(self):
        self.validate()  # Explicit null warnings are retained as reported absence.
        for field in ("optimizer", "optimizer_control", "convergence_code", "convergence_messages", "optimizer_warnings", "singular"):
            with self.subTest(field=field):
                self.setUp()
                del self.export["models"]["FRN"]["diagnostics"][field]
                with self.assertRaisesRegex(bridge.ExportError, "diagnostics missing"):
                    self.validate()

    def test_term_permutation_tracks_both_covariance_axes(self):
        baseline = self.validate()[0]["P3b_report"]
        model = self.export["models"]["P3b"]
        model["terms"].reverse()
        model["coefficients"].reverse()
        model["covariance"] = [row[::-1] for row in model["covariance"][::-1]]
        self.assertEqual(self.validate()[0]["P3b_report"], baseline)

    def test_reject_changed_frame_value_and_order(self):
        for mutate in (lambda m: m["frame"]["abs_rpe_s"].reverse(),
                       lambda m: m["frame"]["FRN_N2_offer_s"].__setitem__(0, 99.)):
            with self.subTest(mutation=mutate):
                self.setUp(); mutate(self.export["models"]["FRN"])
                with self.assertRaises(bridge.ExportError): self.validate()

    def test_reject_source_binding_duplicates_order_boolean_and_range(self):
        for ids in ([1, 1, 5, 7], [3, 1, 5, 7], [True, 3, 5, 7], [1, 3, 5, 9]):
            with self.subTest(ids=ids):
                self.setUp(); self.export["models"]["FRN"]["operator_bound_source_rows"] = ids
                with self.assertRaises(bridge.ExportError): self.validate()

    def test_reject_participant_relabel_and_unused_group(self):
        for key, value in [("group_levels", ["A", "C"]), ("group_levels", ["A", "B", "C"]),
                           ("group_levels", ["A", "A"])]:
            with self.subTest(value=value):
                self.setUp(); self.export["models"]["FRN"][key] = value
                with self.assertRaises(bridge.ExportError): self.validate()
        self.setUp(); self.export["models"]["FRN"]["frame"]["sub"] = ["B", "B", "A", "A"]
        with self.assertRaises(bridge.ExportError): self.validate()

    def test_reject_altered_estimator_weights_offset_and_design(self):
        for field, value in [("REML", False), ("weights", [1, 1, 1, 1]), ("offset", [0, 0, 0, 0]),
                             ("fixed_design_verified", False), ("random_design_verified", False),
                             ("random_terms", ["(Intercept)"]), ("random_group", "trial"),
                             ("formula", "FRN_N2_offer_s ~ abs_rpe_s + (1 | sub)")]:
            with self.subTest(field=field):
                self.setUp(); self.export["models"]["FRN"][field] = value
                with self.assertRaises(bridge.ExportError): self.validate()

    def test_reject_duplicate_terms_bad_covariance_and_nonfinite(self):
        mutations = [lambda m: m["terms"].__setitem__(0, m["terms"][1]),
                     lambda m: m["covariance"][0].__setitem__(1, .9),
                     lambda m: m["covariance"][0].__setitem__(0, -1.),
                     lambda m: m["coefficients"].__setitem__(0, float("nan")),
                     lambda m: m["coefficients"].__setitem__(0, True)]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                self.setUp(); mutate(self.export["models"]["FRN"])
                with self.assertRaises(bridge.ExportError): self.validate()

    def test_conditional_support_not_companion_panel(self):
        self.export["models"]["FRN_unconditional"] = copy.deepcopy(self.export["models"]["FRN"])
        with self.assertRaises(bridge.ExportError): self.validate()
        self.setUp(); self.prepared["FRN"].pop()
        with self.assertRaises(bridge.ExportError): self.validate()

    def test_invalid_native_names_and_unacknowledged_binding(self):
        self.export["models"]["FRN"]["native_frame_row_names"] = ["1"] * 4
        with self.assertRaises(bridge.ExportError): self.validate()
        self.setUp(); self.export["binding_basis"] = "assumed_row_names"
        with self.assertRaises(bridge.ExportError): self.validate()

    def test_strict_json_duplicate_and_nonfinite(self):
        for data in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}'):
            with self.subTest(data=data), self.assertRaises(ValueError): bridge.strict_json(data)

    def test_prepared_csv_identity_receipt_and_same_bytes(self):
        with tempfile.TemporaryDirectory(prefix="generated-", dir=HERE) as temporary:
            root = Path(temporary)
            receipt = {"component": bridge.TASK + "/processed-inputs-v1", "source_revision": bridge.REVISION,
                       "contract_sha256": "fixture-contract", "sources": [], "models": {}}
            receipt["sources"] = [{"name": Path(s["path"]).name, "bytes": s["bytes"], "sha256": s["sha256"], "rows": s["rows"]}
                                  for s in self.contract["public_input_files"]]
            for name, rows in self.prepared.items():
                columns = list(rows[0])
                stream = io.StringIO(newline="")
                writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
                writer.writeheader(); writer.writerows(rows)
                raw = stream.getvalue().encode(); write(root / (name + ".csv"), raw)
                receipt["models"][name] = {"columns": columns, "formula": self.contract["models"][name]["formula"],
                    "retained_rows": 4, "participants": 2,
                    "ordered_identity_sha256": bridge.digest(bridge.canonical([[int(r["source_row"]), r["sub"], r["trialGlobal"]] for r in rows])),
                    "output": {"name": name + ".csv", "bytes": len(raw), "sha256": bridge.digest(raw)}}
            write(root / "receipt.json", bridge.canonical(receipt))
            actual, pins = bridge.load_prepared(root, self.contract, "fixture-contract")
            self.assertEqual(actual, self.prepared)
            write(root / "FRN.csv", (root / "FRN.csv").read_bytes() + b"\n")
            with self.assertRaises(bridge.ExportError): bridge.load_prepared(root, self.contract, "fixture-contract")

    def test_production_refuses_unpinned_contract_before_export_read(self):
        with tempfile.TemporaryDirectory(prefix="generated-", dir=HERE) as temporary:
            root = Path(temporary); write(root / "contract.json", bridge.canonical(self.contract))
            with self.assertRaisesRegex(bridge.ExportError, "Unreviewed public contract"):
                bridge.finalize(root / "absent-export.json", root, root / "contract.json", root / "out")


if __name__ == "__main__":
    program = unittest.main(verbosity=2, exit=False)
    print("generated_fixture_cumulative_bytes_written=" + str(WRITTEN_BYTES))
    raise SystemExit(not program.result.wasSuccessful())
