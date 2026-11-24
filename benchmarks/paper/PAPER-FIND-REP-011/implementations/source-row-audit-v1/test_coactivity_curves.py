"""Generated controls for the source curve endpoint; no source recordings."""
import copy
import json
import unittest

from coactivity_curves import SOURCE_SHA256, export_curves


def fixture():
    return {"schema_version": "rep011-coactivity-curves-input-v1",
            "source_sha256": SOURCE_SHA256,
            "input_kind": "generated_engineering_control", "population_id": "generated-only",
            "native_pair_order_provenance": "generated directed-pair order, not native data",
            "rows": [
                {"row_id": "early-stable", "animal_id": "A", "session": "early", "stability": "stable", "distance_um": 2, "area_um2": 1},
                {"row_id": "early-elim", "animal_id": "B", "session": "early", "stability": "eliminated", "distance_um": 2, "area_um2": 2},
                {"row_id": "middle-stable", "animal_id": "A", "session": "middle", "stability": "stable", "distance_um": 3, "area_um2": 1}],
            "responses": [{"row_id": key, "normalized_coactivity": value} for key, value in
                          [("middle-stable", 3), ("early-elim", 7), ("early-stable", 1)]]}


def point(result, family="all_spines", stability="stable", stratum=None, start=0):
    curve = next(c for c in result["curves"] if (c["family"], c["stability"], c["stratum"]) ==
                 (family, stability, stratum))
    return next(p for p in curve["points"] if p["bin_start_um"] == start)


class CurveTests(unittest.TestCase):
    def test_source_mean_sem_full_bins_and_unchanged_audit(self):
        data = fixture()
        before = copy.deepcopy(data)
        result = export_curves(data)
        observed = point(result)
        self.assertEqual(observed["row_ids"], ["early-stable", "middle-stable"])
        self.assertEqual(observed["mean_normalized_coactivity"], 2)
        self.assertEqual(observed["source_sem"], 1)
        self.assertEqual(len(result["curves"]), 10)
        self.assertEqual(sum(len(c["points"]) for c in result["curves"]), 110)
        self.assertEqual(point(result, start=50)["plot_center_um"], 52.5)
        self.assertEqual(point(result, start=50)["summary_status"], "no_nonmissing_values")
        self.assertTrue(result["row_audit"]["size_models_lines_260_264"]["paired_animal_mismatches"])
        self.assertEqual(data, before)
        self.assertFalse(result["complete_original_population_verified"])
        self.assertIsNone(result["reproduction_score"])
        self.assertIsNone(result["improvement_score"])

    def test_strata_remain_distinct_and_singleton_sem_is_zero(self):
        result = export_curves(fixture())
        self.assertEqual(point(result, "session_stratified", stratum="early")["mean_normalized_coactivity"], 1)
        self.assertEqual(point(result, "session_stratified", stratum="middle")["mean_normalized_coactivity"], 3)
        self.assertEqual(point(result, "session_stratified", stratum="early")["source_sem"], 0)
        self.assertEqual(point(result, "size_stratified", "eliminated", "large")["row_ids"], ["early-elim"])
        self.assertEqual(point(result, "size_stratified", "eliminated", "small")["rows"], 0)

    def test_nan_is_omitted_but_infinity_is_retained(self):
        data = fixture()
        data["responses"][0]["normalized_coactivity"] = None
        result = point(export_curves(data))
        self.assertEqual((result["rows"], result["nonmissing_rows"], result["nan_rows"]), (2, 1, 1))
        self.assertEqual(result["mean_normalized_coactivity"], 1)
        self.assertEqual(result["source_sem"], 0)
        data["responses"][2]["normalized_coactivity"] = "Inf"
        result = point(export_curves(data))
        self.assertEqual(result["mean_normalized_coactivity"], "Inf")
        self.assertIsNone(result["source_sem"])
        self.assertEqual(result["positive_infinity_rows"], 1)
        json.dumps(export_curves(data), allow_nan=False)

    def test_distance_area_boundaries_and_missingness(self):
        data = fixture()
        template = data["rows"][0]
        data["rows"] = [{**template, "row_id": name, "distance_um": distance, "area_um2": area}
                        for name, distance, area in [("cutoff", 50, 1.0960), ("missing-area", 54.99, None),
                                                    ("outside", 55, 2), ("missing-distance", None, 1)]]
        data["responses"] = [{"row_id": row["row_id"], "normalized_coactivity": 1} for row in data["rows"]]
        result = export_curves(data)
        self.assertEqual(point(result, start=50)["row_ids"], ["cutoff", "missing-area"])
        self.assertEqual(point(result, "size_stratified", stratum="small", start=50)["row_ids"], ["cutoff"])
        self.assertEqual(result["row_audit"]["distance_excluded_row_ids"], ["outside", "missing-distance"])
        self.assertEqual(result["missing_area_row_ids"], ["missing-area"])
        self.assertTrue(result["row_audit"]["size_models_lines_260_264"]["table_length_mismatch"])

    def test_keyed_coverage_is_exact_even_for_distance_excluded_rows(self):
        good = fixture()
        good["rows"][0]["distance_um"] = 55
        for entries in (good["responses"][:-1], good["responses"] + [good["responses"][0]],
                        good["responses"] + [{"row_id": "extra", "normalized_coactivity": 1}]):
            with self.assertRaises(ValueError):
                export_curves({**good, "responses": entries})
        other = copy.deepcopy(good)
        other["responses"].reverse()
        self.assertEqual(export_curves(good)["curves"], export_curves(other)["curves"])

    def test_invalid_response_values_and_source_pin_fail(self):
        for value in (-1, True, float("nan"), float("inf"), "NaN", "-Inf", "1"):
            data = fixture()
            data["responses"][0]["normalized_coactivity"] = value
            with self.assertRaises(ValueError):
                export_curves(data)
        with self.assertRaises(ValueError):
            export_curves({**fixture(), "source_sha256": "0" * 64})
        with self.assertRaises(ValueError):
            export_curves({**fixture(), "rows": []})


if __name__ == "__main__":
    unittest.main()
