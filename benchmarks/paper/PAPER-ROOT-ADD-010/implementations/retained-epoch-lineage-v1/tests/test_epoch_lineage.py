"""Generated metadata controls only: no original events, FIF or neural arrays."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("epoch_lineage", ROOT / "epoch_lineage.py")
e = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(e)
PIN = {"bytes": 100, "sha256": "a" * 64}


def events(shapes):
    return [{"shape": s, "condition": "reference" if i % 2 == 0 else "outlier"}
            for i, s in enumerate(shapes)]


def runs(subject="sub-01", length=40):
    return [{"run": r, "bytes": 100, "sha256": hashlib.sha256(str(r).encode()).hexdigest(),
             "events": events(["square"] * length)} for r in e.expected_runs(subject)]


def full_subject(subject):
    result = []
    for run in e.expected_runs(subject):
        rows = events([shape for shape in e.SHAPES for _ in range(8)])
        result.append({"run": run, "bytes": 100,
                       "sha256": hashlib.sha256(f"{subject}/{run}".encode()).hexdigest(), "events": rows})
    # Retain all rows in a deliberately non-chronological order. Source selection
    # follows current epoch order, not a re-sorted or renumbered event catalogue.
    selection = list(range(sum(len(x["events"]) for x in result)))[::-1]
    return e.project_subject(subject, result, selection, PIN)


class LineageTests(unittest.TestCase):
    def test_rejection_does_not_renumber_early_late(self):
        result = e.project_subject("sub-01", runs(), [6, 7, 35, 36], PIN)
        self.assertEqual([r["is_early"] for r in result["trials"]], ["late", "late", "early", "late"])
        self.assertEqual([r["trial_number_from_miniblock"] for r in result["retained_epoch_lineage"]], [6, 7, 5, 6])

    def test_counter_preserves_shape_reset_and_thirty_wrap(self):
        data = runs()
        data[0]["events"] = events(["square"] * 31 + ["rectangle"] * 7)
        result = e.project_subject("sub-01", data, [0, 5, 6, 29, 30, 31, 36, 37], PIN)
        self.assertEqual([r["trial_number_from_miniblock"] for r in result["retained_epoch_lineage"]],
                         [0, 5, 6, 29, 0, 0, 5, 6])

    def test_same_shape_continues_across_run_boundary(self):
        result = e.project_subject("sub-01", runs(length=8), [7, 8, 9, 29, 30], PIN)
        self.assertEqual([r["trial_number_from_miniblock"] for r in result["retained_epoch_lineage"]],
                         [7, 8, 9, 29, 0])
        self.assertEqual(result["retained_epoch_lineage"][1]["source_run_row_index"], 0)
        self.assertEqual(result["retained_epoch_lineage"][1]["run"], 2)
        self.assertEqual(result["trials"][1]["is_early"], "late")

    def test_reordering_preserves_identity_and_selection_order(self):
        forward = e.project_subject("sub-01", runs(), [2, 7, 40], PIN)
        reverse = e.project_subject("sub-01", runs(), [40, 7, 2], PIN)
        self.assertEqual(forward["trials"], reverse["trials"][::-1])
        self.assertEqual([r["source_event_index"] for r in reverse["retained_epoch_lineage"]], [40, 7, 2])
        altered = runs(); altered[0]["sha256"] = "b" * 64
        new = e.project_subject("sub-01", altered, [2, 7, 40], PIN)
        self.assertNotEqual(forward["trials"][0]["trial_id"], new["trials"][0]["trial_id"])
        self.assertEqual(forward["trials"][2]["trial_id"], new["trials"][2]["trial_id"])

    def test_invalid_selections_and_invented_runs_rejected(self):
        for selection in ([], [1, 1], [-1], [320], [True], [1.0]):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                e.project_subject("sub-01", runs(), selection, PIN)
        for subject in ("sub-10", "sub-11"):
            valid = runs(subject)
            self.assertEqual(len(valid), 7)
            with self.assertRaisesRegex(ValueError, "run inventory"):
                e.project_subject(subject, runs("sub-01"), [0], PIN)
        with self.assertRaisesRegex(ValueError, "run inventory"):
            e.project_subject("sub-01", runs()[:-1], [0], PIN)

    def test_tsv_parser_retains_order_and_rejects_ambiguous_rows(self):
        data = b"onset\ttrial_type\n0\tshape/square/reference\n1\tshape/square/outlier/3\n"
        self.assertEqual(e.parse_events(data), events(["square", "square"]))
        for bad in (b"trial_type\ttrial_type\na\tb\n", b"trial_type\nshape/unknown/reference\n",
                    b"trial_type\nshape/square/mystery\n", b"trial_type\nshape/square/outlier/5\n",
                    b"trial_type\nshape/square/reference\textra\n", b"onset\ttrial_type\n0\n"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                e.parse_events(bad)

    def test_full_twenty_subject_output_feeds_existing_six_fold_planner(self):
        spec = importlib.util.spec_from_file_location("oddball_auroc", ROOT.parent / "oddball-auroc-v1" / "oddball_auroc.py")
        oddball = importlib.util.module_from_spec(spec); spec.loader.exec_module(oddball)
        run_count = 0
        for subject in e.SUBJECTS:
            result = full_subject(subject)
            plans = oddball.fold_plan(subject, result["trials"])
            self.assertEqual(len(plans), 6)
            counts = {r["trial_id"]: 0 for r in result["trials"]}
            for plan in plans:
                self.assertFalse(set(plan["train_ids"]) & set(plan["test_ids"]))
                for identity in plan["test_ids"]:
                    counts[identity] += 1
            self.assertTrue(all(counts[r["trial_id"]] == (3 if r["is_early"] == "late" else 0)
                                for r in result["trials"]))
            run_count += len(result["event_file_pins"])
        self.assertEqual(run_count, 158)

    def test_file_extent_digest_path_and_budget_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "events.tsv").write_bytes(b"abc")
            pin = {"path": "events.tsv", "bytes": 3, "sha256": hashlib.sha256(b"abc").hexdigest()}
            self.assertEqual(e.BoundedFiles(root).read(pin), b"abc")
            for changed in ({"bytes": 2}, {"sha256": "a" * 64}, {"path": "../events.tsv"},
                            {"path": "/events.tsv"}, {"path": "./events.tsv"}):
                with self.subTest(changed=changed), self.assertRaises(ValueError):
                    e.BoundedFiles(root).read({**pin, **changed})
            (root / "link.tsv").symlink_to(root / "events.tsv")
            with self.assertRaisesRegex(ValueError, "symlink"):
                e.BoundedFiles(root).read({**pin, "path": "link.tsv"})
            with self.assertRaisesRegex(ValueError, "byte bound"):
                e.BoundedFiles(root, max_file_bytes=2).read(pin)

    def test_strict_json_and_exclusive_output(self):
        for raw in (b'{"a":1,"a":2}', b'{"x":NaN}'):
            with self.assertRaises(ValueError): e.strict_json(raw)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            e.write_result(output, {"ok": True})
            with self.assertRaises(FileExistsError): e.write_result(output, {"ok": False})
            self.assertEqual(json.loads(output.read_bytes()), {"ok": True})

    def test_cohort_loader_requires_exact_roster_before_file_reads(self):
        entries = [{"subject": s, "events": [{"run": r, "file": {**PIN, "path": "absent.tsv"}}
                    for r in e.expected_runs(s)], "selection": {**PIN, "path": "absent.json"}}
                   for s in e.SUBJECTS]
        manifest = {"schema": "root010-epoch-lineage-input/v1", "source_revision": e.SOURCE_REVISION,
                    "subjects": entries}
        for mutation in (lambda x: x["subjects"].pop(),
                         lambda x: x["subjects"].__setitem__(1, x["subjects"][0]),
                         lambda x: x["subjects"][-1]["events"].pop()):
            broken = copy.deepcopy(manifest); mutation(broken)
            with self.assertRaises(ValueError): e.load_cohort(broken, ROOT)

    def test_complete_loader_binds_bytes_without_claiming_fif_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def save(name, raw):
                (root / name).write_bytes(raw)
                return {"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            event_pin = save("events.tsv", b"trial_type\nshape/square/reference\n")
            entries = []
            for subject in e.SUBJECTS:
                selected = {"schema": "root010-mne-selection-export/v1", "subject": subject,
                            "selection": [0], "prepared_epochs": PIN}
                selection_pin = save(subject + ".json", json.dumps(selected).encode())
                entries.append({"subject": subject, "events": [{"run": run, "file": event_pin}
                                for run in e.expected_runs(subject)], "selection": selection_pin})
            manifest = {"schema": "root010-epoch-lineage-input/v1", "source_revision": e.SOURCE_REVISION,
                        "subjects": entries[::-1]}
            result = e.load_cohort(manifest, root)
            self.assertFalse(result["research_qualified"])
            self.assertEqual([x["subject"] for x in result["subjects"]], list(e.SUBJECTS))
            self.assertEqual(sum(len(x["event_file_pins"]) for x in result["subjects"]), 158)
            self.assertEqual(result["subjects"][0]["prepared_epoch_identity_declared_unverified"], PIN)
            broken = copy.deepcopy(manifest)
            broken["subjects"][0]["selection"] = entries[0]["selection"]
            with self.assertRaisesRegex(ValueError, "selection subject"):
                e.load_cohort(broken, root)


if __name__ == "__main__":
    unittest.main()
