"""Generated complete-support controls; no authentic data or model fitting."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("figure5d_panel", Path(__file__).with_name("panel.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    positive = [1.0] + [0.0] * 31
    negative = [-1.0] + [0.0] * 31
    support = {"schema": "marble_figure5d_support_v1", "task_id": m.endpoint.TASK_ID,
               "panel": "Figure 5d", "animal": "rat1", "unit": "m", "source_sha256": "a" * 64,
               "training_row_ids": [f"generated/train/{i}" for i in range(72)],
               "query_row_ids": [f"generated/query/{i}" for i in range(2000)]}
    methods = {}
    for method in m.METHODS:
        # Every method has identical labels and support. Only the embeddings
        # differ: CEBRA-time decodes 2 m; the other methods decode 0 m.
        first, second = ((negative, positive) if method == "cebra-time"
                         else (positive, negative))
        methods[method] = {
            "training": {"row_ids": support["training_row_ids"].copy(),
                         "embedding": [first.copy() for _ in range(36)] +
                                      [second.copy() for _ in range(36)],
                         "position_m": [0.0] * 36 + [2.0] * 36},
            "query": {"row_ids": support["query_row_ids"].copy(),
                      "embedding": [positive.copy() for _ in range(2000)]},
        }
    targets = {"row_ids": support["query_row_ids"].copy(), "position_m": [0.0] * 1999 + [2000.0]}
    return support, methods, targets


class PanelTests(unittest.TestCase):
    def test_complete_method_panel_and_last_row_have_independent_expected_scores(self):
        report = m.score_panel(*fixture())
        self.assertEqual(report["method_order"], list(m.METHODS))
        for method, expected in (("cebra-time", 2.998), ("cebra-behaviour", 1.0), ("marble", 1.0)):
            self.assertEqual(report["method_scores"][method]["samples"], 2000)
            self.assertEqual(report["method_scores"][method]["mean_absolute_error_m"], expected)
        pairs = report["paired_descriptive_comparisons"]
        self.assertEqual(pairs["marble_minus_cebra-time"]["mean_absolute_error_difference_m"], -1.998)
        self.assertEqual(pairs["marble_minus_cebra-behaviour"]["mean_absolute_error_difference_m"], 0.0)
        self.assertFalse(report["complete_original_figure5_reproduction"])
        self.assertIsNone(report["scientific_improvement_awarded"])

    def test_missing_extra_or_substituted_methods_fail_before_decoding(self):
        for mutation in ("missing", "extra", "renamed"):
            support, methods, _ = fixture()
            if mutation == "missing":
                methods.pop("cebra-time")
            elif mutation == "extra":
                methods["candidate"] = methods["marble"]
            else:
                methods["other"] = methods.pop("cebra-time")
            with self.subTest(mutation=mutation), mock.patch.object(m.endpoint, "decode") as decoder:
                with self.assertRaisesRegex(ValueError, "all three"):
                    m.decode_panel(support, methods)
                decoder.assert_not_called()

    def test_changed_training_labels_fail_before_decoding(self):
        support, methods, _ = fixture()
        methods["marble"]["training"]["position_m"][-1] = 100
        with mock.patch.object(m.endpoint, "decode") as decoder:
            with self.assertRaisesRegex(ValueError, "identical training positions"):
                m.decode_panel(support, methods)
            decoder.assert_not_called()

    def test_each_method_must_preserve_complete_ordered_label_free_query(self):
        for mutation in ("reordered", "1999", "query-labels"):
            support, methods, _ = fixture()
            query = methods["cebra-time"]["query"]
            if mutation == "reordered":
                query["row_ids"].reverse()
            elif mutation == "1999":
                query["embedding"].pop()
            else:
                query["position_m"] = [0.0] * 2000
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                m.decode_panel(support, methods)

    def invoke(self, operands, *, pin=None, failure=None):
        bodies = {key: json.dumps(value).encode() for key, value in operands.items()}
        events = []

        class MemoryPath:
            def __init__(self, value):
                self.name = str(value)

            def open(self, mode):
                self.assert_mode = mode == "rb"
                if not self.assert_mode:
                    raise AssertionError("bounded JSON reads required")
                events.append("read:" + self.name)
                return io.BytesIO(bodies[self.name])

        original = m.endpoint.decode
        count = 0

        def decode(*args):
            nonlocal count
            method = m.METHODS[count]
            count += 1
            events.append("decode:" + method)
            if method == failure:
                raise ValueError("generated decoder failure")
            return original(*args)

        args = ["--support", "support", "--methods", "methods", "--targets", "targets",
                "--support-sha256", pin or m.endpoint.sha256(bodies["support"])]
        with mock.patch.object(m.endpoint, "Path", MemoryPath), \
                mock.patch.object(m.endpoint, "decode", decode), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            status = m.main(args)
        return status, json.loads(output.getvalue()), events

    def test_cli_decodes_all_methods_once_before_one_target_read(self):
        operands = dict(zip(("support", "methods", "targets"), fixture()))
        status, report, events = self.invoke(operands)
        self.assertEqual(status, 0)
        self.assertEqual(events, ["read:support", "read:methods", "decode:cebra-time",
                                  "decode:cebra-behaviour", "decode:marble", "read:targets"])
        self.assertEqual(set(report["input_pins"]), {"support", "methods", "targets"})
        for name, value in operands.items():
            self.assertEqual(report["input_pins"][name]["sha256"],
                             m.endpoint.sha256(json.dumps(value).encode()))
        self.assertEqual(report["method_scores"]["marble"]["mean_absolute_error_m"], 1)
        self.assertNotIn("position_m", report)

    def test_failed_support_method_or_last_decoder_never_reads_targets(self):
        for mutation in ("support-pin", "incomplete-methods", "last-decoder"):
            operands = dict(zip(("support", "methods", "targets"), fixture()))
            kwargs = {}
            if mutation == "support-pin":
                kwargs["pin"] = "b" * 64
            elif mutation == "incomplete-methods":
                operands["methods"].pop("marble")
            else:
                kwargs["failure"] = "marble"
            with self.subTest(mutation=mutation):
                status, report, events = self.invoke(operands, **kwargs)
                self.assertEqual(status, 1)
                self.assertIn("error", report)
                self.assertNotIn("read:targets", events)
                if mutation == "support-pin":
                    self.assertEqual(events, ["read:support"])


if __name__ == "__main__":
    unittest.main()
