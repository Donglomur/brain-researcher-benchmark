"""Generated metadata controls; no recordings or model dependencies."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("intake", Path(__file__).with_name("intake.py"))
intake = importlib.util.module_from_spec(spec)
spec.loader.exec_module(intake)


def fixture():
    prefix = "/source/derivatives/fmriprep/sub-001/func/"
    scans = ["sub-001_task-alpha_run-1", "sub-001_task-alpha_run-2", "sub-001_task-beta"]
    subject = {"confounds": [prefix + sid + "_desc-confounds_regressors.tsv" for sid in scans],
               "bold": {"fsaverage6": {"preproc": [prefix + sid + "_space-fsaverage6_hemi-" + h +
                           ".func.gii" for sid in reversed(scans) for h in ("R", "L")]}}}
    return {"sub-001": subject}, {"sub-001": {"alpha", "beta"}}


class IntakeTest(unittest.TestCase):
    def test_shuffled_bilateral_join_preserves_runs(self):
        subjects, participants = fixture()
        result = intake.join_inventory(subjects, participants, {})
        self.assertEqual(result["counts"], {"people": 1, "scans": 3, "surface_files": 6,
                                          "task_aliases": 2, "raw_scans_checked": 0})
        self.assertEqual([r["run_entity"] for r in result["scans"]], ["1", "2", None])
        for row in result["scans"]:
            for hemi, path in row["preproc_fsaverage6"].items():
                self.assertTrue(path.endswith(row["scan_id"] + "_space-fsaverage6_hemi-" + hemi + ".func.gii"))
            self.assertEqual(row["raw_membership"], "not_checked")
            self.assertIsNone(row["story_family"])
            self.assertIsNone(row["selected_clean_derivative"])
            self.assertFalse(row["confounds"].startswith("/"))

    def test_duplicate_and_missing_hemisphere_rejected(self):
        for mutation in ("duplicate", "missing"):
            subjects, participants = fixture()
            surfaces = subjects["sub-001"]["bold"]["fsaverage6"]["preproc"]
            surfaces.append(surfaces[0]) if mutation == "duplicate" else surfaces.pop()
            with self.assertRaises(ValueError):
                intake.join_inventory(subjects, participants, {})

    def test_duplicate_confound_rejected(self):
        subjects, participants = fixture()
        paths = subjects["sub-001"]["confounds"]
        paths.append(paths[0])
        with self.assertRaisesRegex(ValueError, "duplicate confound"):
            intake.join_inventory(subjects, participants, {})

    def test_cross_person_and_pipeline_paths_rejected(self):
        for before, after in (("sub-001/func", "sub-002/func"), ("fmriprep", "afni-nosmooth")):
            subjects, participants = fixture()
            paths = subjects["sub-001"]["confounds"]
            paths[0] = paths[0].replace(before, after)
            with self.assertRaises(ValueError):
                intake.join_inventory(subjects, participants, {})

    def test_raw_disagreement_retained_without_repair(self):
        subjects, participants = fixture()
        participants["sub-001"] = {"alpha", "gamma"}
        raw = b"filename\nfunc/sub-001_task-alpha_run-1_bold.nii.gz\nfunc/sub-001_task-gamma_bold.nii.gz\n"
        result = intake.join_inventory(subjects, participants, {"sub-001": raw})
        self.assertEqual(result["participant_task_discrepancies"], [{"person": "sub-001",
                         "participants_only": ["gamma"], "derivative_only": ["beta"]}])
        comparison = result["raw_scan_comparisons"][0]
        self.assertEqual(comparison["raw_only"], ["sub-001_task-gamma"])
        self.assertEqual(len(comparison["derivative_only"]), 2)
        self.assertEqual(len(result["scans"]), 3)
        self.assertEqual(sum(r["raw_membership"] == "confirmed" for r in result["scans"]), 1)

    def test_missing_participant_rejected(self):
        subjects, participants = fixture()
        with self.assertRaisesRegex(ValueError, "participant membership"):
            intake.join_inventory(subjects, {}, {})

    def test_wrong_source_pin_rejected_before_parsing(self):
        with self.assertRaisesRegex(ValueError, "subject metadata source pin"):
            intake.compile_inventory(b"not JSON", b"not TSV", {})

    def test_duplicate_json_and_participant_members_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            intake.json.loads('{"sub-001":{},"sub-001":{}}', object_pairs_hook=intake._unique_object)
        with self.assertRaisesRegex(ValueError, "duplicate/invalid participant"):
            intake.participant_tasks(b"participant_id\ttask\nsub-001\talpha\nsub-001\tbeta\n")

    def test_deterministic_source_order_independence(self):
        subjects, participants = fixture()
        changed = copy.deepcopy(subjects)
        changed["sub-001"]["confounds"].reverse()
        changed["sub-001"]["bold"]["fsaverage6"]["preproc"].reverse()
        self.assertEqual(intake.join_inventory(subjects, participants, {}),
                         intake.join_inventory(changed, participants, {}))


if __name__ == "__main__":
    unittest.main()
