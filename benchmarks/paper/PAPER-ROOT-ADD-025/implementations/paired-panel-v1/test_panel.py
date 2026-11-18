"""Generated controls for complete S11 paired-score support, not scientific runs."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np

spec = importlib.util.spec_from_file_location("s11_panel", Path(__file__).with_name("panel.py"))
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def fixture():
    """30 generated identities, two contexts, variable PCs; no empirical arrays."""
    cohort = [{"source_ordinal": o, "participant": f"generated-{o}"} for o in panel.SOURCE_ORDINALS]
    manifest = {"schema": "park_s11_paired_panel_manifest/v1", "source_commit": panel.SOURCE_COMMIT,
                "cohort": cohort, "entries": []}
    designs = []
    for person in cohort:
        for context in ("attn", "choice"):
            pc = 2 if person["source_ordinal"] == 1 and context == "choice" else 1
            design = {"schema": "park_source_decoder_design/v2", "source_commit": panel.SOURCE_COMMIT,
                      "participant": person["participant"], "parcel": "generated-parcel", "context": context,
                      "n_components": pc, "n_times": 129, "n_folds": 10, "n_repeats": 5,
                      "generative_selection": "fgmu_0_all_finite", "fold_unit": "pooled_sample_row",
                      "cells": []}
            for pair in range(1, 7):
                for name in ("consistent", "inconsistent", "all"):
                    # One entire unsupported pair remains in both arms.
                    n = 9 if pair == 6 else 20
                    design["cells"].append({"pair": pair, "consistency": name, "available_rows": n,
                                            "matched_rows": n, "status": "planned" if n == 20
                                            else "insufficient_rows_for_10_folds"})
            design["design_sha256"] = digest(design)
            manifest["entries"].append({k: design[k] for k in
                                       ("participant", "parcel", "context", "n_components", "design_sha256")})
            designs.append(design)
    return manifest, designs


def score(design, value):
    result = {"schema": "park_source_decoder_scores/v2", "design_sha256": design["design_sha256"],
              **{k: design[k] for k in ("participant", "parcel", "context")},
              "metric_names": list(panel.METRICS), "fold_score_axes": panel.FOLD_AXES,
              "mean_fold_axes": panel.MEAN_AXES, "cells": []}
    for cell in design["cells"]:
        out = dict(cell)
        if cell["status"] != "planned":
            out.update(fold_scores=None, mean_fold_scores=None, undefined_fold_correlations=None)
        else:
            fold = np.broadcast_to(np.float64(value), (5, 10, 3, design["n_components"], 129))
            out.update(status="scored", fold_scores=fold, mean_fold_scores=np.mean(fold, axis=1),
                       undefined_fold_correlations=0, prediction_sha256=["1"*64, "2"*64])
        result["cells"].append(out)
    return result


def records(designs, value=.25):
    for design in designs:
        yield {"design": design, "scores": score(design, value)}


class PairedPanelTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.designs = fixture()

    def test_complete_signed_panel_preserves_variable_pcs_companions_and_unavailable_cells(self):
        result = panel.compare_panel(self.manifest, records(self.designs, -.5), records(self.designs, -.75))
        self.assertEqual(len(result["entries"]), 60)
        self.assertIsNone(result["paper_win"])
        self.assertIsNone(result["scalar_reduction"])
        self.assertFalse(result["source_support_authenticated"])
        self.assertEqual(result["same_task_superiority"], "unknown")
        self.assertEqual(result["entries"][1]["cells"][0]["candidate"].shape, (5, 3, 2, 129))
        for entry in result["entries"]:
            self.assertEqual(len(entry["cells"]), 18)
            for cell in entry["cells"][:15]:
                np.testing.assert_array_equal(cell["candidate_minus_author"], .25)
            for cell in entry["cells"][15:]:
                self.assertIsNone(cell["candidate_minus_author"])

    def test_original_ordinal_support_and_both_contexts_required(self):
        for change in ("missing_person", "wrong_ordinal", "missing_context", "duplicate_entry"):
            bad = copy.deepcopy(self.manifest)
            if change == "missing_person":
                bad["cohort"].pop()
            elif change == "wrong_ordinal":
                bad["cohort"][0]["source_ordinal"] = 12
            elif change == "missing_context":
                bad["entries"] = [e for e in bad["entries"] if not
                                  (e["participant"] == "generated-1" and e["context"] == "attn")]
            else:
                bad["entries"].append(bad["entries"][0])
            with self.subTest(change=change), self.assertRaises(ValueError):
                panel.validate_manifest(bad)

    def test_missing_extra_reordered_and_different_designs_rejected(self):
        variants = [self.designs[:-1], self.designs + self.designs[:1], self.designs[::-1]]
        for designs in variants:
            with self.subTest(length=len(designs)), self.assertRaises(ValueError):
                panel.compare_panel(self.manifest, records(designs), records(self.designs))
        bad = copy.deepcopy(self.designs[0])
        bad["seed"] = 999
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            panel.compare_panel(self.manifest, records([bad] + self.designs[1:]), records(self.designs))

    def test_mean_fold_tampering_and_metric_relabeling_rejected(self):
        for change in ("mean", "metric", "shape", "infinity", "undefined_count", "drop_cell"):
            first = {"design": self.designs[0], "scores": score(self.designs[0], .25)}
            cell = first["scores"]["cells"][0]
            if change == "mean":
                cell["mean_fold_scores"][0, 0, 0, 0] += .1
            elif change == "metric":
                first["scores"]["metric_names"][0] = "absolute_correlation"
            elif change == "shape":
                cell["fold_scores"] = np.zeros((5, 10, 3, 1, 128))
            elif change == "infinity":
                cell["fold_scores"] = np.full((5, 10, 3, 1, 129), np.inf)
            elif change == "undefined_count":
                cell["undefined_fold_correlations"] = 1
            else:
                first["scores"]["cells"].pop()
            with self.subTest(change=change), self.assertRaises(ValueError):
                panel.compare_panel(self.manifest, iter([first]), records(self.designs))

    def test_one_arm_undefined_is_preserved_without_repair_or_omission(self):
        first = {"design": self.designs[0], "scores": score(self.designs[0], .25)}
        cell = first["scores"]["cells"][0]
        fold = cell["fold_scores"].copy()
        fold[0, 0, 0, 0, 0] = np.nan
        cell.update(fold_scores=fold, mean_fold_scores=np.mean(fold, axis=1),
                    undefined_fold_correlations=1, status="undefined_fold_correlations")
        def candidate():
            yield first
            yield from records(self.designs[1:])
        result = panel.compare_panel(self.manifest, candidate(), records(self.designs))
        paired = result["entries"][0]["cells"][0]
        self.assertFalse(paired["candidate_defined"][0, 0, 0, 0])
        self.assertTrue(paired["author_defined"][0, 0, 0, 0])
        self.assertTrue(np.isnan(paired["candidate_minus_author"][0, 0, 0, 0]))
        self.assertEqual(len(result["entries"]), 60)

    def test_favorable_unavailable_cell_or_missing_companion_not_admitted(self):
        for change in ("unavailable", "prediction"):
            first = {"design": self.designs[0], "scores": score(self.designs[0], .25)}
            if change == "unavailable":
                first["scores"]["cells"][-1]["status"] = "scored"
            else:
                first["scores"]["cells"][0]["prediction_sha256"].pop()
            with self.subTest(change=change), self.assertRaises(ValueError):
                panel.compare_panel(self.manifest, iter([first]), records(self.designs))

    def test_existing_decoder_generated_record_is_accepted_without_relabeling(self):
        path = Path(__file__).parent.parent / "source-decoder-v2" / "decoder.py"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), panel.DECODER_SHA256)
        source_spec = importlib.util.spec_from_file_location("source_decoder", path)
        decoder = importlib.util.module_from_spec(source_spec)
        source_spec.loader.exec_module(decoder)
        n = 40
        samples = np.broadcast_to(np.array([1., -1.] * 6), (n, 12)).copy()
        behavior = dict(trial_ids=np.array([f"generated-trial-{i}" for i in range(n)]),
                        sess=np.full(n, 3), samples=samples, binary_choices=np.ones(n),
                        interm_cues=np.ones(n), estimations=np.linspace(-2, 2, n),
                        gen_means=np.linspace(-4, 4, n),
                        consistent_samples=np.where(samples > 0, samples, np.nan),
                        inconsistent_samples=np.where(samples < 0, samples, np.nan))
        design = decoder.prepare_design(behavior, behavior["trial_ids"], participant="generated-1",
                                        parcel="generated-parcel", context="choice", n_components=1, seed=7)
        predictions = []
        for cell in design["cells"]:
            shape = (5, cell["matched_rows"], 1, 129)
            predictions.append(dict(pair=cell["pair"], consistency=cell["consistency"],
                                    repeats=cell["repeats"], stimulus=np.zeros(shape), estimate=np.zeros(shape)))
        scored = decoder.score_predictions(design, behavior, predictions)
        entry = {k: design[k] for k in ("participant", "parcel", "context", "n_components", "design_sha256")}
        panel._design(design, entry)
        means = panel._scores(scored, design)
        self.assertEqual(len(means), 18)
        self.assertTrue(all(np.isnan(x["mean"]).all() for x in means))


if __name__ == "__main__":
    unittest.main()
