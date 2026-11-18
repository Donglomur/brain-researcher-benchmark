"""Generated arithmetic/identity controls; no original data or model fitting."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("opto_aggregation", Path(__file__).with_name("aggregation.py"))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def example():
    mice = [f"generated-mouse-{i}" for i in range(1, 10)]
    entries, rows = [], []
    for branch, state in (("opto_first", 0), ("opto_later", 1)):
        for i, mouse in enumerate(mice, 1):
            entry = {"id": f"{branch}/{i}", "branch": branch, "row1": i,
                     "mouse": mouse, "opto_on": state}
            entries.append(entry)
            rows.append({**entry, "slope_cm_per_lap": -1 if state else 1,
                         "p_value": 0.01 if state else 0.2})
    roster = {"schema": "find013-opto-derived-roster/v1", "source_revision": a.REVISION,
              "mice": mice, "rows": entries}
    return rows, roster


class AggregationControls(unittest.TestCase):
    def test_inclusive_threshold_and_zero_slope_are_distinct(self):
        self.assertEqual(a.classify(-2, 0.05), "backward")
        self.assertEqual(a.classify(2, 0.05), "forward")
        self.assertEqual(a.classify(2, math.nextafter(0.05, math.inf)), "nonsignificant")
        self.assertEqual(a.classify(0, 0.05), "unclassified")
        self.assertEqual(a.classify(-0.0, 0.05), "unclassified")
        self.assertEqual(a.classify(0, 0.2), "nonsignificant")

    def test_source_nan_comparison_semantics_use_explicit_nulls(self):
        self.assertEqual(a.classify(None, 0.2), "nonsignificant")
        self.assertEqual(a.classify(None, 0.01), "unclassified")
        self.assertEqual(a.classify(1, None), "unclassified")

    def test_invalid_numbers_are_not_silently_source_missingness(self):
        for slope, p in ((True, 0.1), (math.nan, 0.1), (math.inf, 0.1),
                         (1, math.nan), (1, -0.1), (1, 1.1), (1, False), ("1", 0.1)):
            with self.subTest(slope=slope, p=p), self.assertRaises(ValueError):
                a.classify(slope, p)

    def test_pooled_and_mouse_denominators_remain_different(self):
        rows, roster = example()
        rows[9].update(slope_cm_per_lap=0, p_value=0.05)
        rows[10]["p_value"] = None
        result = a.summarize(rows, roster)
        pooled = result["pooled"]["opto"]
        self.assertEqual(pooled["denominator"], 9)
        self.assertEqual(pooled["classified_row_count"], 7)
        self.assertEqual(pooled["fractions"]["backward"], 7 / 9)
        self.assertEqual(pooled["p_only_shifting_fraction_all_rows"], 8 / 9)
        self.assertEqual(pooled["unclassified_row_ids"], ["opto_later/1", "opto_later/2"])
        mouse = result["per_mouse"][0]["opto"]
        self.assertEqual(mouse["source_row_count"], 1)
        self.assertEqual(mouse["denominator"], 0)
        self.assertIsNone(mouse["directional_shifting_fraction"])
        self.assertEqual(mouse["p_only_shifting_fraction_all_rows"], 1)
        self.assertIsNone(result["per_mouse"][0]["contrast"]["fractions"]["backward"])

    def test_missing_slope_with_nonsignificant_p_keeps_denominator(self):
        rows, roster = example()
        rows[9].update(slope_cm_per_lap=None, p_value=0.2)
        row = a.summarize(rows, roster)["per_mouse"][0]["opto"]
        self.assertEqual(row["denominator"], 1)
        self.assertEqual(row["fractions"]["nonsignificant"], 1)
        self.assertEqual(row["undefined_slope_row_ids"], ["opto_later/1"])

    def test_contrasts_keep_opto_minus_control_and_no_scientific_pass(self):
        rows, roster = example()
        result = a.summarize(rows, roster)
        self.assertEqual(result["pooled"]["contrast"]["fractions"],
                         {"backward": 1, "forward": 0, "nonsignificant": -1})
        self.assertEqual(result["pooled"]["contrast"]["orientation"], "opto_minus_control")
        self.assertEqual(result["scientific_reproduction"], "unknown")
        self.assertEqual(result["scientific_improvement"], "unknown")
        self.assertIsNone(result["inferential_tests"])
        self.assertFalse(result["readiness_promoted"])
        self.assertEqual(len(result["per_mouse"]), 9)

    def test_unordered_derived_rows_join_by_full_identity_without_mutation(self):
        rows, roster = example()
        before = copy.deepcopy((rows, roster))
        self.assertEqual(a.summarize(rows, roster), a.summarize(list(reversed(rows)), roster))
        self.assertEqual((rows, roster), before)
        self.assertEqual(a.summarize(rows, roster)["branch_row_counts"], {"opto_first": 9, "opto_later": 9})

    def test_missing_extra_duplicate_or_relabelled_rows_are_rejected(self):
        rows, roster = example()
        for mutate in (
            lambda x: x.pop(),
            lambda x: x.append(copy.deepcopy(x[0])),
            lambda x: x.__setitem__(1, copy.deepcopy(x[0])),
            lambda x: x[0].update(mouse="generated-mouse-2"),
            lambda x: x[0].update(opto_on=1),
            lambda x: x[0].update(opto_on=False),
            lambda x: x[0].update(row1=True),
            lambda x: x[0].update(branch="opto_later"),
            lambda x: x[0].update(unexpected="ignored?"),
        ):
            changed = copy.deepcopy(rows)
            mutate(changed)
            with self.assertRaises(ValueError):
                a.summarize(changed, roster)

    def test_roster_must_keep_both_complete_branches_and_all_nine_mice(self):
        rows, roster = example()
        for mutate in (
            lambda x: x["mice"].pop(),
            lambda x: x["mice"].__setitem__(0, x["mice"][1]),
            lambda x: x["rows"][0].update(row1=2),
            lambda x: x["rows"].reverse(),
            lambda x: x["rows"][0].update(opto_on=True),
            lambda x: x.update(source_revision="wrong"),
        ):
            changed = copy.deepcopy(roster)
            mutate(changed)
            with self.assertRaises(ValueError):
                a.summarize(rows, changed)
        only_first = {**roster, "rows": roster["rows"][:9]}
        with self.assertRaisesRegex(ValueError, "both timing"):
            a.summarize(rows[:9], only_first)

    def test_content_binding_rejects_changed_roster_before_parsing_rows(self):
        rows, roster = example()
        raw = json.dumps(roster).encode()
        digest = hashlib.sha256(raw).hexdigest()
        result = a.summarize_bytes(json.dumps(rows).encode(), raw, digest)
        self.assertEqual(result["input_bindings"]["roster_sha256"], digest)
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            a.summarize_bytes(b"not json", raw + b" ", digest)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            a.summarize_bytes(b'[{"id":"a","id":"b"}]', raw, digest)
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            a.summarize_bytes(b'[NaN]', raw, digest)

    def test_json_underflow_cannot_turn_a_directional_slope_into_zero(self):
        rows, roster = example()
        raw = json.dumps(roster).encode()
        digest = hashlib.sha256(raw).hexdigest()
        for token in (b"1e-1000", b"-1e-1000", b"1e1000"):
            derived = json.dumps(rows).encode().replace(b'"slope_cm_per_lap": 1',
                                                      b'"slope_cm_per_lap": ' + token, 1)
            with self.subTest(token=token), self.assertRaisesRegex(ValueError, "overflow/underflow"):
                a.summarize_bytes(derived, raw, digest)
        self.assertEqual(a._decode(b"0e-1000"), 0)


if __name__ == "__main__":
    unittest.main()
