"""Generated seam controls only; no authentic arrays or native fitting."""
import csv
import hashlib
import importlib.util
import io
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("find013_lineage", HERE / "lineage.py")
lineage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lineage)


def csv_bytes(header, rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(header)
    writer.writerows(rows)
    return stream.getvalue().encode()


def fixture():
    mice = [f"mouse_{i}" for i in range(1, 10)]
    header = ["mouse", "env", "emergeLap"] + [f"meta_{i}" for i in range(18)] + [f"lap_{i}" for i in range(1, 45)]
    rows = []
    for mouse in mice:
        for env, onset in (("control_day1", 6), ("opto_first_day1", 1), ("opto_later_day1", 5)):
            rows.append([mouse, env, str(onset)] + ["source" for _ in range(18)] + [str(i) for i in range(44)])
    return {"mice": mice, "header": header, "rows": rows,
            "first_timing": [[m, "24"] for m in mice],
            "later_timing": [[m, "5", "35"] for m in mice]}


def inputs_for(f, *, first_indices=None, later_indices=None):
    # These explicit fixture coordinates are independent of the production
    # selection function. Every third control row appears in both branches.
    first_indices = first_indices if first_indices is not None else [i for i in range(27) if i % 3 in (0, 1)]
    later_indices = later_indices if later_indices is not None else [i for i in range(27) if i % 3 in (0, 2)]
    extra = ["COM_slope", "COM_pval", "Opto_ON", "COMinterp_slope", "COMinterp_pval", "shiftDir"]
    exports = {}
    for name, indices in (("first", first_indices), ("later", later_indices)):
        rows = []
        for i in indices:
            source = f["rows"][i]
            opto = int(source[1] != "control_day1")
            rows.append(source + ["-2" if opto else "3", "0.05", str(opto), "999", "0.9", "0"])
        exports[name + "_export"] = csv_bytes(f["header"] + extra, rows)
    return {"source": csv_bytes(f["header"], f["rows"]),
            "first_timing": csv_bytes(["mouse", "opto_first_day1"], f["first_timing"]),
            "later_timing": csv_bytes(["mouse", "opto_on", "opto_off"], f["later_timing"]), **exports}


def hashes(inputs):
    return {key: hashlib.sha256(value).hexdigest() for key, value in inputs.items()}


def bind(f, inputs=None):
    inputs = inputs_for(f) if inputs is None else inputs
    return lineage.bind_native_exports(inputs, hashes(inputs), f["mice"])


def change_export(inputs, key, transform):
    header, rows = lineage._table(inputs[key], key)
    transform(header, rows)
    inputs[key] = csv_bytes(header, rows)


class LineageControls(unittest.TestCase):
    def test_full_source_lineage_and_existing_aggregate(self):
        result = bind(fixture())
        self.assertEqual(result["source_row_count"], 27)
        self.assertEqual(len(result["derived_rows"]), 36)
        self.assertEqual([r["source_row1"] for r in result["lineage"][:4]], [1, 2, 4, 5])
        self.assertEqual([r["source_row1"] for r in result["lineage"][18:22]], [1, 3, 4, 6])
        summary = AGGREGATION.summarize(result["derived_rows"], result["roster"])
        self.assertEqual(summary["branch_row_counts"], {"opto_first": 18, "opto_later": 18})
        self.assertEqual(summary["pooled"]["opto"]["counts"]["backward"], 18)
        self.assertEqual(summary["pooled"]["control"]["counts"]["forward"], 18)
        self.assertEqual(summary["per_mouse"][0]["control"]["denominator"], 2)
        self.assertFalse(result["readiness_promoted"])
        self.assertEqual(result["native_statistics"], "supplied_from_row_bound_exports_not_recomputed")

    def test_full_raw_clock_not_saved_15_lap_or_interpolated_statistics(self):
        f = fixture()
        for lap in (7, 23, 24):
            f["rows"][0][20 + lap] = "NaN"
        result = bind(f)
        first = result["lineage"][0]
        self.assertEqual(first["raw_window_length"], 19)
        self.assertEqual(first["interpolated_span_laps"], 17)
        self.assertEqual(first["saved_matrix_laps"], 15)
        self.assertEqual(first["raw_regression_laps1"], [1] + list(range(3, 18)))
        self.assertEqual(first["raw_regression_cm"][:3], [0, 10, 15])
        self.assertEqual(result["derived_rows"][0]["slope_cm_per_lap"], 3)
        self.assertEqual(result["derived_rows"][0]["p_value"], .05)

    def test_released_onset_windows_and_short_span_exclusions(self):
        f = fixture()
        f["rows"][1][2] = "25"  # first onset exceeds 24
        f["rows"][2][2] = "25"  # later onset passes off-10 but yields only 11 laps
        f["rows"][5][2] = "26"  # later onset exceeds off-10
        first = [i for i in range(27) if i % 3 in (0, 1) and i != 1]
        later = [i for i in range(27) if i % 3 in (0, 2) and i not in (2, 5)]
        result = bind(f, inputs_for(f, first_indices=first, later_indices=later))
        exclusions = result["branch_audits"]["opto_later"]["excluded"]
        self.assertIn({"source_row1": 3, "reason": "fewer_than_15_interpolated_laps"}, exclusions)
        self.assertIn({"source_row1": 6, "reason": "outside_onset_window"}, exclusions)
        self.assertEqual(len(result["derived_rows"]), 33)

    def test_later_cap44_first_restrict_has_no_invented_cap(self):
        f = fixture()
        f["header"].append("lap_45")
        for row in f["rows"]:
            row.append("44")
        for row in f["first_timing"]:
            row[1] = "45"
        for row in f["later_timing"]:
            row[2] = "50"
        result = bind(f)
        self.assertEqual(result["lineage"][0]["end_lap"], 45)
        self.assertEqual(result["lineage"][18]["end_lap"], 44)

    def test_alignment_hole_is_refused_instead_of_silently_dropping_row(self):
        f = fixture()
        f["rows"][0][21:] = ["2"] * 44
        with self.assertRaisesRegex(ValueError, "source_alignment_hole"):
            bind(f)

    def test_nan_entries_count_for_source_find_rule(self):
        f = fixture()
        f["rows"][0][21:] = ["2"] * 44
        for lap in range(7, 15):
            f["rows"][0][20 + lap] = "NaN"
        f["rows"][0][20 + 25] = "NaN"  # later branch needs 9/30 find entries
        result = bind(f)
        self.assertEqual(result["lineage"][0]["source_find_count"], 8)
        self.assertEqual(result["lineage"][0]["interpolated_span_laps"], 19)
        self.assertEqual(set(result["lineage"][0]["raw_regression_cm"]), {0})

    def test_native_row_permutation_missing_duplicate_and_wrong_state_refused(self):
        f = fixture()
        operations = (
            lambda h, rows: rows.reverse(),
            lambda h, rows: rows.pop(),
            lambda h, rows: rows.__setitem__(1, list(rows[0])),
            lambda h, rows: rows[0].__setitem__(h.index("Opto_ON"), "1"),
            lambda h, rows: rows[0].__setitem__(3, "changed source metadata"),
        )
        for operation in operations:
            with self.subTest(operation=operation):
                inputs = inputs_for(f)
                change_export(inputs, "first_export", operation)
                with self.assertRaises(ValueError):
                    bind(f, inputs)

    def test_timing_identity_and_exact_nine_mouse_roster(self):
        for mode in ("duplicate", "missing", "reversed"):
            f = fixture()
            if mode == "duplicate":
                f["first_timing"].append(list(f["first_timing"][0]))
            elif mode == "missing":
                f["first_timing"].pop()
            else:
                f["later_timing"][0][1:] = ["40", "35"]
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                bind(f)
        f = fixture()
        f["mice"][-1] = "unobserved_mouse"
        with self.assertRaisesRegex(ValueError, "nine declared mice"):
            bind(f)

    def test_missing_native_statistic_stays_unclassified_and_never_refitted(self):
        f = fixture()
        inputs = inputs_for(f)
        change_export(inputs, "first_export", lambda h, rows: rows[0].__setitem__(h.index("COM_pval"), "NaN"))
        result = bind(f, inputs)
        summary = AGGREGATION.summarize(result["derived_rows"], result["roster"])
        self.assertIsNone(result["derived_rows"][0]["p_value"])
        self.assertEqual(summary["classifications"][0]["class"], "unclassified")

    def test_nonfinite_underflow_invalid_probability_and_numeric_grammar(self):
        f = fixture()
        for token in ("inf", "-inf", "1e999", "1e-999", "0_1", " 0.1", "١", "1.1", "-0.1"):
            with self.subTest(token=token):
                inputs = inputs_for(f)
                change_export(inputs, "first_export", lambda h, rows: rows[0].__setitem__(h.index("COM_pval"), token))
                with self.assertRaises(ValueError):
                    bind(f, inputs)

    def test_operator_pins_required_and_source_rounding_is_not_hidden(self):
        f = fixture()
        inputs = inputs_for(f)
        expected = hashes(inputs)
        inputs["source"] += b"\n"
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            lineage.bind_native_exports(inputs, expected, f["mice"])
        inputs = inputs_for(f)
        with self.assertRaises(ValueError):
            lineage.bind_native_exports(inputs, {}, f["mice"])
        change_export(inputs, "first_export", lambda h, rows: rows[0].__setitem__(21, "0.0000000000000001"))
        with self.assertRaisesRegex(ValueError, "content/order mismatch"):
            bind(f, inputs)
        self.assertTrue(lineage._same_cell("1.000", "1e0"))
        self.assertFalse(lineage._same_cell("9007199254740992", "9007199254740993"))

    def test_source_layout_and_native_statistic_column_rejection(self):
        f = fixture()
        inputs = inputs_for(f)
        change_export(inputs, "first_export", lambda h, rows: h.__setitem__(h.index("COM_slope"), "COMinterp_slope"))
        with self.assertRaises(ValueError):
            bind(f, inputs)
        inputs = inputs_for(f)
        inputs["source"] = b"mouse,env,emergeLap\nmouse_1,control_day1,6\n"
        with self.assertRaisesRegex(ValueError, "21 metadata columns"):
            bind(f, inputs)


if __name__ == "__main__":
    if "--aggregation" in sys.argv:
        i = sys.argv.index("--aggregation")
        aggregate_path = Path(sys.argv[i + 1])
        del sys.argv[i:i + 2]
    else:
        aggregate_path = HERE.parent / "opto-linear-aggregation-v1" / "aggregation.py"
    expected = "c5f2e396c10309aa12bd488666ebfc496f280882ce087e66e34c6e932775d1fb"
    if hashlib.sha256(aggregate_path.read_bytes()).hexdigest() != expected:
        raise RuntimeError("old aggregation dependency differs from reviewed pin")
    spec = importlib.util.spec_from_file_location("find013_existing_aggregation", aggregate_path)
    AGGREGATION = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(AGGREGATION)
    unittest.main()
