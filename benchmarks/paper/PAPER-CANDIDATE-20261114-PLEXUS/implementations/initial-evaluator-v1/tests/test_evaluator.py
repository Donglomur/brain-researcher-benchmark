"""Bounded generated engineering controls; these are not authentic Plexus data."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "plexus_evaluator.py"
spec = importlib.util.spec_from_file_location("plexus_evaluator", MODULE)
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def controls():
    genes = [f"ENGINEERING_GENE_{i:02}" for i in range(52)]
    wells = []
    for line in e.CELL_LINES:
        for role, suffix in (("train", "train_batch"), ("test", "held_batch_1"), ("test", "held_batch_2")):
            batch = line + "/" + suffix
            for i, gene in enumerate(genes+[None, None]):
                wells.append(dict(cell_line=line, batch=batch, plate=batch+"/plate", well=f"w{i:03}",
                                  guide=f"guide_{i}", exchangeability_block="curator_declared_block", role=role,
                                  is_control=gene is None, eligible=True, exclusion_reason=None, n_cells=10,
                                  gene=gene))
    manifest = dict(task_id=e.TASK_ID, dataset_record=e.RECORD, contract_sha256=e.CONTRACT_SHA256,
                    genes=genes, cell_lines=list(e.CELL_LINES), wells=wells,
                    population_source_sha256="1"*64, cell_line_mapping_sha256="9"*64, split_plan_sha256="2"*64,
                    exchangeability_design_sha256="3"*64, exchangeability_approved=True,
                    population_scope="GENERATED ENGINEERING CONTROL; never an authentic released census")
    lineage = [list(e.well_key(r)) for r in wells if r["role"] == "train"]
    models = {}
    for method in e.METHODS:
        models[method] = dict(source_sha256="4"*64, configuration_sha256="5"*64,
                             fitted_artifact_sha256="6"*64, tuning_plan_sha256="7"*64,
                             input_basis="metadata_only" if method == "nuisance_only" else "processed_neuronal_inputs",
                             checkpoint_exposure="train_only", fit_wells=lineage, statistics_wells=lineage,
                             frozen_before_held_labels=True)
        if method == "label_shuffle_refit":
            models[method]["training_label_shuffle_plan_sha256"] = "8"*64
    submission = dict(manifest_sha256=e.canonical_hash(manifest), policy="prospective-held-plate-v1",
                      fdr_alpha=.05, models=models, scores=[])
    for method in e.METHODS:
        for gene in genes:
            for row in wells:
                if row["role"] == "test" and (row["is_control"] or row["gene"] == gene):
                    submission["scores"].append(dict(method=method, target_gene=gene,
                        **{k: row[k] for k in ("cell_line", "batch", "plate", "well")},
                        probability=(.1 if row["is_control"] else .9) if method == "network" else .5))
    return manifest, submission


class StatisticalTests(unittest.TestCase):
    def test_tie_aware_auc_and_degenerate_class(self):
        self.assertEqual(e.auroc([1, 0, 1, 0], [.8, .8, .9, .1]), .875)
        self.assertIsNone(e.auroc([0, 0], [.1, .9]))
        self.assertEqual(e.auroc([1, 0], [.5, .5]), .5)

    def test_calibration_closed_form(self):
        got = e.binary_metrics([0, 1], [.25, .75])
        self.assertEqual(got["brier"], .0625)
        self.assertEqual(got["ece_10_fixed_bins"], .25)
        self.assertEqual(got["control_positive_rate_at_0_5"], 0)
        self.assertEqual(got["score_separation"], .5)
        self.assertEqual(got["prevalence"], .5)

    def test_by_keeps_full_family_and_monotone(self):
        self.assertEqual(e.by_adjust([0, 0, 1]), [0, 0, 1])
        got = e.by_adjust([.01, .04, 1])
        self.assertAlmostEqual(got[0], .055)
        self.assertAlmostEqual(got[1], .11)
        self.assertEqual(got[2], 1)

    def test_cluster_interval_requires_biological_replication(self):
        self.assertIsNone(e.cluster_interval([("same_batch", 0), ("same_batch", 1)], 20, 0)["ci95"])
        got = e.cluster_interval([("a", .3), ("b", .3)], 20, 0)
        self.assertEqual(got["ci95"], [.3, .3])

    def test_permutation_null_and_exchangeability_gate(self):
        rows = [dict(cell_line="L", batch="B", plate="P", well=str(i), exchangeability_block="X") for i in range(4)]
        self.assertEqual(e.blocked_randomization(rows, [0, 0, 1, 1], [.5]*4, True, 99, 3)["p_value"], 1)
        self.assertIsNone(e.blocked_randomization(rows, [0, 0, 1, 1], [0,0,1,1], False, 99, 3)["p_value"])
        rows[2]["exchangeability_block"] = rows[3]["exchangeability_block"] = "Y"
        self.assertIsNone(e.blocked_randomization(rows, [0, 0, 1, 1], [0,0,1,1], True, 99, 3)["p_value"])

    def test_sign_direction_and_plus_one(self):
        rows = [dict(cell_line="L", batch="B", plate="P", well=str(i), exchangeability_block="X") for i in range(4)]
        positive = e.blocked_randomization(rows, [0,0,1,1], [0,0,1,1], True, 999, 2)
        negative = e.blocked_randomization(rows, [0,0,1,1], [1,1,0,0], True, 999, 2)
        self.assertTrue(.1 < positive["p_value"] < .25)  # six equally likely label allocations
        self.assertEqual(negative["p_value"], 1)
        self.assertGreaterEqual(positive["p_value"], .001)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.m, self.s = controls()

    def validate(self):
        return e.validate(self.m, self.s, self.s["manifest_sha256"])

    def repin(self):
        self.s["manifest_sha256"] = e.canonical_hash(self.m)

    def test_exact_52_gene_population_and_all_methods(self):
        self.validate()
        self.s["scores"].pop()
        with self.assertRaisesRegex(e.ContractError, "population mismatch"):
            self.validate()

    def test_missing_gene_cannot_be_hidden_by_census(self):
        self.m["wells"] = [r for r in self.m["wells"] if r["gene"] != self.m["genes"][0]]
        self.repin()
        with self.assertRaisesRegex(e.ContractError, "census omits"):
            self.validate()

    def test_batch_leakage_and_lineage_leakage(self):
        self.m["wells"][0]["role"] = "test"
        self.repin()
        with self.assertRaisesRegex(e.ContractError, "batch leakage"):
            self.validate()
        self.m, self.s = controls()
        self.s["models"]["network"]["statistics_wells"] = [list(e.well_key(self.m["wells"][-1]))]
        with self.assertRaisesRegex(e.ContractError, "non-training"):
            self.validate()

    def test_control_truth_and_duplicates(self):
        self.s["scores"].append(copy.deepcopy(self.s["scores"][0]))
        with self.assertRaisesRegex(e.ContractError, "duplicate prediction"):
            self.validate()
        self.m, self.s = controls()
        self.m["wells"][-1]["gene"] = self.m["genes"][0]
        self.repin()
        with self.assertRaisesRegex(e.ContractError, "negative control"):
            self.validate()

    def test_nonfinite_boolean_probability_and_manifest_tamper(self):
        for value in (float("nan"), float("inf"), -.1, 1.1, True):
            self.s["scores"][0]["probability"] = value
            with self.assertRaisesRegex(e.ContractError, "finite probability"):
                self.validate()
        self.m["population_scope"] = "changed after freeze"
        with self.assertRaisesRegex(e.ContractError, "SHA256"):
            self.validate()

    def test_version_and_checkpoint_rejection(self):
        self.m["dataset_record"] = "10.5281/zenodo.14714574"
        self.repin()
        with self.assertRaisesRegex(e.ContractError, "v2"):
            self.validate()
        self.m, self.s = controls()
        self.s["models"]["network"]["checkpoint_exposure"] = "released_held_trained"
        with self.assertRaisesRegex(e.ContractError, "checkpoints forbidden"):
            self.validate()

    def test_end_to_end_complete_screen_and_paired_plate_estimates(self):
        result = e.evaluate(self.m, self.s, self.s["manifest_sha256"], permutations=19, bootstraps=19, seed=17)
        self.assertEqual(len(result["gene_line_table"]), 52*5*4)
        self.assertEqual(len(result["plate_table"]), 52*5*2*4)
        self.assertEqual(len(result["guide_plate_table"]), 52*5*2*4)
        self.assertEqual(len(result["paired_comparisons"]), 52*4*4)
        self.assertEqual(result["fdr"]["family_size"], 208)
        self.assertEqual(result["scientific_qualification"], "unknown")
        network = result["gene_line_table"][0]
        self.assertEqual(network["plate_macro_auroc"], 1)
        self.assertAlmostEqual(network["score_separation"]["estimate"], .8)
        self.assertEqual(network["score_separation"]["n_batches"], 2)
        contrast = result["paired_comparisons"][0]["metrics"]
        self.assertEqual(contrast["network_minus_auroc"]["estimate"], .5)
        self.assertAlmostEqual(contrast["network_minus_brier"]["estimate"], -.24)
        self.assertTrue(all(not r["rejected_at_fdr_0_05"] for r in result["gene_line_table"]))
        json.dumps(result, allow_nan=False)

    def test_unavailable_gene_retained_in_fdr_family(self):
        gene = self.m["genes"][0]
        for row in self.m["wells"]:
            if row["gene"] == gene and row["role"] == "test":
                row.update(eligible=False, exclusion_reason="ENGINEERING exclusion for coverage control")
        self.repin()
        removed = {e.well_key(r) for r in self.m["wells"] if not r["eligible"]}
        self.s["scores"] = [r for r in self.s["scores"] if e.well_key(r) not in removed]
        result = e.evaluate(self.m, self.s, self.s["manifest_sha256"], permutations=1, bootstraps=2)
        row = result["gene_line_table"][0]
        self.assertEqual(row["gene"], gene)
        self.assertEqual(row["multiplicity_p"], 1)
        self.assertIsNone(row["plate_macro_auroc"])
        self.assertEqual(len(result["gene_line_table"]), 1040)
        self.assertEqual(len(result["census"]["exclusions"]), 8)

    def test_physical_batch_cross_line_leakage(self):
        train_batch = self.m["wells"][0]["batch"]
        other_line = [r for r in self.m["wells"] if r["cell_line"] == e.CELL_LINES[1] and r["role"] == "test"]
        for r in other_line:
            r["batch"] = train_batch
        self.repin()
        with self.assertRaisesRegex(e.ContractError, "batch leakage"):
            self.validate()

    def test_brier_comparison_includes_single_class_plates(self):
        gene = self.m["genes"][0]
        for row in self.m["wells"]:
            if row["gene"] == gene and row["role"] == "test" and "held_batch_2" in row["batch"]:
                row.update(eligible=False, exclusion_reason="generated control for single-class plate")
        self.repin()
        removed = {e.well_key(r) for r in self.m["wells"] if not r["eligible"]}
        self.s["scores"] = [r for r in self.s["scores"] if e.well_key(r) not in removed]
        for row in self.s["scores"]:
            if row["method"] == "network" and row["target_gene"] == gene and "held_batch_2" in row["batch"]:
                row["probability"] = 1.0
        result = e.evaluate(self.m, self.s, self.s["manifest_sha256"], permutations=1, bootstraps=2)
        metrics = result["paired_comparisons"][0]["metrics"]
        self.assertAlmostEqual(metrics["network_minus_brier"]["estimate"], .255)
        self.assertEqual(metrics["network_minus_brier"]["n_plates"], 2)
        self.assertEqual(metrics["network_minus_auroc"]["n_plates"], 1)

    def test_cli_real_path_and_duplicate_json_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/"manifest.json").write_text(json.dumps(self.m))
            (root/"scores.json").write_text(json.dumps(self.s))
            process = subprocess.run([sys.executable, str(MODULE), "--manifest", str(root/"manifest.json"),
                "--manifest-sha256", self.s["manifest_sha256"], "--submission", str(root/"scores.json"),
                "--output", str(root/"report.json"), "--permutations", "1", "--bootstraps", "2"], capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads((root/"report.json").read_text())["task_id"], e.TASK_ID)
            (root/"duplicate.json").write_text('{"x": 1, "x": 2}')
            with self.assertRaisesRegex(e.ContractError, "duplicate JSON"):
                e.read_json(str(root/"duplicate.json"))


if __name__ == "__main__":
    unittest.main()
