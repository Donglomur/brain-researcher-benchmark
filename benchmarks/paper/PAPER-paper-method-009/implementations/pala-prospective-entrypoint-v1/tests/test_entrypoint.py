"""Generated orchestration controls; no original recording or fit is loaded."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

COMPONENT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pala_entrypoint_test_target", COMPONENT / "entrypoint.py")
ep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ep)
REFERENCE = Path(os.environ.get("PALA_REFERENCE_TASK", str(COMPONENT.parents[1])))


def receipt(rows):
    return {
        "source_md5": ep.SOURCE_MD5, "source_sha256": "a" * 64,
        "source_bytes": ep.SOURCE_BYTES, "source_voltage_unit": "V",
        "output_voltage_unit": "mV", "voltage_multiplier": 1000.0,
        "source_rows": rows, "source_row_order_preserved": True,
        "cohort_selection_applied": False,
    }


def report():
    return {
        "task_id": ep.TASK_ID, "recipe": ep.RECIPE,
        "classification": "prospective_engineering_bridge",
        "scientific_qualified": False, "exact_figure_reproduction": False,
        "holds": ["unresolved original identities and voltage-reference policy"],
        "cells": [{"cell_id": "generated-mouse-cell", "generated_only": True}],
    }


class EntrypointTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.plan = self.root / "plan.json"
        self.plan.write_text(json.dumps({"recipe": ep.RECIPE, "cells": {
            "generated-mouse-cell": {"calibration_trial_ids": ["g1", "g2"],
                                     "assessment_trial_ids": ["g3", "g4"]}}}))
        self.output = self.root / "report.json"
        self.trials = tuple(SimpleNamespace(trial_id="g" + str(i)) for i in range(1, 5))
        self.recording = SimpleNamespace(trials=self.trials, receipt=receipt(4))
        self.adapter = SimpleNamespace(load_pala=mock.Mock(return_value=self.recording))
        self.evaluator = SimpleNamespace(
            evaluate=mock.Mock(return_value=report()),
            audit_population=mock.Mock(return_value=({"generated-mouse-cell": self.trials}, [])),
            load_pala=mock.Mock(side_effect=AssertionError("legacy volts loader must not run")))

    def invoke(self):
        with mock.patch.object(ep, "_load_components", return_value=(self.adapter, self.evaluator)):
            return ep.run(self.root / "not-an-authentic-mat.mat", self.plan, self.output)

    def test_actual_source_members_import_without_data_or_fit(self):
        adapter, evaluator = ep._load_components(REFERENCE)
        self.assertEqual(Path(adapter.load_pala.__code__.co_filename),
                         REFERENCE / "implementations/pala-source-adapter-v2/source_adapter.py")
        self.assertEqual(Path(evaluator.evaluate.__code__.co_filename),
                         REFERENCE / "implementations/initial-evaluator-v1/evaluator.py")
        self.assertIsNot(adapter.load_pala, evaluator.load_pala)

    def test_corrected_loader_trials_and_original_holds_pass_unchanged(self):
        got = self.invoke()
        self.adapter.load_pala.assert_called_once_with(self.root / "not-an-authentic-mat.mat")
        self.evaluator.load_pala.assert_not_called()
        self.evaluator.audit_population.assert_called_once_with(self.trials)
        self.assertIs(self.evaluator.evaluate.call_args.args[0], self.trials)
        self.assertEqual(got["holds"], report()["holds"])
        self.assertEqual(got["cells"], report()["cells"])
        self.assertFalse(got["scientific_qualified"])
        self.assertFalse(got["exact_figure_reproduction"])
        self.assertNotIn("paper_win", got)
        self.assertEqual(got, json.loads(self.output.read_text()))
        self.assertEqual(got["source_receipt"], self.recording.receipt)
        self.assertNotIn(str(self.root), self.output.read_text())

    def test_tampered_selected_member_refuses_before_import(self):
        read_bytes = Path.read_bytes

        def changed(path):
            raw = read_bytes(path)
            return raw + b"\n" if path.name == "source_adapter.py" else raw

        with mock.patch.object(Path, "read_bytes", changed), mock.patch.object(
                ep.importlib.util, "spec_from_file_location") as imported:
            with self.assertRaisesRegex(ep.EntryError, "differs from its pin"):
                ep.run(self.root / "unused.mat", self.plan, self.output, task_root=REFERENCE)
            imported.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_source_authentication_failure_never_reaches_evaluator(self):
        self.adapter.load_pala.side_effect = ValueError("source MD5 mismatch")
        with self.assertRaisesRegex(ValueError, "source MD5 mismatch"):
            self.invoke()
        self.evaluator.evaluate.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_wrong_unit_cohort_extent_and_row_receipts_refuse_before_evaluation(self):
        invalid = [
            ("source_voltage_unit", "mV"), ("output_voltage_unit", "V"),
            ("voltage_multiplier", 1.0), ("source_bytes", ep.SOURCE_BYTES - 1),
            ("source_md5", "0" * 32), ("source_sha256", "not a hash"),
            ("source_rows", 1), ("source_rows", True),
            ("source_row_order_preserved", False), ("cohort_selection_applied", True),
        ]
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                self.recording.receipt = {**receipt(4), field: value}
                with self.assertRaises(ep.EntryError):
                    self.invoke()
                self.evaluator.evaluate.assert_not_called()
                self.assertFalse(self.output.exists())

    def test_bad_plans_refuse_before_any_source_import(self):
        plans = [
            '{"recipe":"' + ep.RECIPE + '","recipe":"other","cells":{"x":{}}}',
            '{"recipe":"' + ep.RECIPE + '","cells":{"x":{}},"x":NaN}',
            '{"recipe":"' + ep.RECIPE + '","cells":{"x":{}},"x":1e999}',
            '{"recipe":"historical-figure3","cells":{"x":{}}}',
            json.dumps({"recipe": ep.RECIPE, "cells": {}}), "[]", "{",
        ]
        for text in plans:
            with self.subTest(text=text):
                self.plan.write_text(text)
                with mock.patch.object(ep, "_load_components") as loaded:
                    with self.assertRaises(ep.EntryError):
                        ep.run(self.root / "unused.mat", self.plan, self.output)
                    loaded.assert_not_called()

    def test_oversize_plan_refuses_before_import(self):
        # This allocation is generated control text, not a source recording.
        with mock.patch.object(ep, "MAX_PLAN_BYTES", 64):
            with mock.patch.object(ep, "_load_components") as loaded:
                with self.assertRaisesRegex(ep.EntryError, "exceeds"):
                    ep.run(self.root / "unused.mat", self.plan, self.output)
                loaded.assert_not_called()

    def test_invalid_later_cell_never_reaches_any_evaluation_or_fit(self):
        trials = tuple(SimpleNamespace(trial_id="g" + str(i)) for i in range(1, 9))
        self.recording.trials = trials
        self.recording.receipt = receipt(8)
        self.evaluator.audit_population.return_value = ({"first": trials[:4],
                                                         "second": trials[4:]}, [])
        self.evaluator.dsr = mock.Mock(side_effect=AssertionError("no fit may start"))
        self.evaluator.fit_voltage_curve = mock.Mock(side_effect=AssertionError("no fit may start"))
        invalid_second = [
            {"calibration_trial_ids": ["g5", "g6"], "assessment_trial_ids": ["g6", "g8"]},
            {"calibration_trial_ids": ["g5", "g6"], "assessment_trial_ids": ["g7", "wrong-source-id"]},
            {"calibration_trial_ids": ["g5", "g6"], "assessment_trial_ids": ["g7", "g8", "extra"]},
        ]
        for second in invalid_second:
            with self.subTest(second=second):
                self.plan.write_text(json.dumps({"recipe": ep.RECIPE, "cells": {
                    "first": {"calibration_trial_ids": ["g1", "g2"],
                              "assessment_trial_ids": ["g3", "g4"]},
                    "second": second}}))
                with self.assertRaises(ep.EntryError):
                    self.invoke()
                self.evaluator.evaluate.assert_not_called()
                self.evaluator.dsr.assert_not_called()
                self.evaluator.fit_voltage_curve.assert_not_called()
                self.assertFalse(self.output.exists())

    def test_existing_output_is_preserved_before_source_access(self):
        self.output.write_bytes(b"prior-output")
        with mock.patch.object(ep, "_load_components") as loaded:
            with self.assertRaises(ep.EntryError):
                ep.run(self.root / "unused.mat", self.plan, self.output)
            loaded.assert_not_called()
        self.assertEqual(self.output.read_bytes(), b"prior-output")

    def test_broken_symlink_destination_is_preserved(self):
        self.output.symlink_to(self.root / "absent")
        with self.assertRaises(ep.EntryError):
            self.invoke()
        self.adapter.load_pala.assert_not_called()
        self.assertTrue(self.output.is_symlink())

    def test_changed_scientific_claim_or_nonfinite_report_is_not_published(self):
        cases = [
            {**report(), "scientific_qualified": True},
            {**report(), "exact_figure_reproduction": True},
            {**report(), "recipe": "historical"},
            {**report(), "cells": [float("nan")]},
        ]
        for item in cases:
            with self.subTest(item=item):
                self.evaluator.evaluate.return_value = item
                with self.assertRaises(ep.EntryError):
                    self.invoke()
                self.assertFalse(self.output.exists())
                self.assertFalse(list(self.root.glob(".pala-report-*")))

    def test_concurrent_output_creation_does_not_overwrite_or_leave_partial_file(self):
        real_link = os.link

        def raced(src, dst):
            Path(dst).write_bytes(b"concurrent-report")
            return real_link(src, dst)

        with mock.patch.object(ep.os, "link", side_effect=raced):
            with self.assertRaises(FileExistsError):
                self.invoke()
        self.assertEqual(self.output.read_bytes(), b"concurrent-report")
        self.assertFalse(list(self.root.glob(".pala-report-*")))

    def test_report_bound_is_enforced_without_creating_destination(self):
        with mock.patch.object(ep, "MAX_REPORT_BYTES", 8):
            with self.assertRaisesRegex(ep.EntryError, "report exceeds"):
                self.invoke()
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob(".pala-report-*")))


if __name__ == "__main__":
    unittest.main()
