"""Generated scientific ambiguity and source-identity controls; no native data."""
import copy
import unittest

from annotation_events import AnnotationRefusal, FIELDS, adapt_annotation, adapt_recording, _time_ms


def row(marker="MOAAS1", field="MOAAS", value="1.0", index=0):
    raw = {name: "" for name in FIELDS}
    raw["EVENT"] = marker
    raw[field] = value
    time = "2026-01-01 00:01:00.000"
    return {"source_row": index, "source_physical_line_end": index + 2,
            "raw_time": time, "recognized_time_ms": _time_ms(time),
            "timestamp_issues": [], "original_fields": raw}


class AnnotationEventsTests(unittest.TestCase):
    def test_five_grouped_categories_remain_five_without_original_seven_claim(self):
        for value in range(1, 6):
            result = adapt_annotation("41", row(f"MOAAS{value}", "MOAAS", f"{value}.0"))
            self.assertEqual(result["moaas_grouped_ordinal"], value)
            self.assertIsNone(result["soc_transition_state"])
            self.assertIsNone(result["biological_person_id"])
            self.assertFalse(result["canonical_scoring_admitted"])

    def test_soc_transitions_use_explicit_marker_and_derivative_only(self):
        for marker, value in (("LOC", 0), ("ROC", 1)):
            result = adapt_annotation("43", row(marker, "SOC", f"{value}.0"))
            self.assertEqual(result["soc_transition_state"], value)
            self.assertIsNone(result["moaas_grouped_ordinal"])
        inconsistent = adapt_annotation("43", row("LOC", "SOC", "1.0"))
        self.assertIsNone(inconsistent["soc_transition_state"])
        self.assertIn("soc_marker_and_derived_field_disagree", inconsistent["unresolved_reason_codes"])

    def test_repeated_scores_and_duplicate_times_preserve_distinct_source_rows(self):
        first, second = row(index=20), row(index=21)
        second["timestamp_issues"] = ["duplicate_timestamp"]
        results = list(adapt_recording("41", [first, second]))
        self.assertEqual(len(results), 2)
        self.assertEqual([item["moaas_grouped_ordinal"] for item in results], [1, 1])
        self.assertNotEqual(results[0]["source_event_id"], results[1]["source_event_id"])
        self.assertEqual(results[1]["timestamp_issues"], ["duplicate_timestamp"])

    def test_duplicate_row_is_integrity_failure_not_silent_dedup(self):
        with self.assertRaises(AnnotationRefusal):
            list(adapt_recording("41", [row(index=20), row(index=20)]))
        with self.assertRaises(AnnotationRefusal):
            list(adapt_recording("41", [row(index=21), row(index=20)]))

    def test_physical_line_provenance_must_increase_with_source_rows(self):
        first, second = row(index=0), row(index=1)
        first["source_physical_line_end"] = 100
        for impossible in (3, 100):
            second["source_physical_line_end"] = impossible
            with self.assertRaises(AnnotationRefusal):
                list(adapt_recording("41", [first, second]))

    def test_unknown_numeric_spelling_and_empty_target_remain_null(self):
        for raw in ("", "1", "1.00", " 1.0", "NaN", "0.0", "6.0"):
            result = adapt_annotation("1", row(value=raw))
            self.assertIsNone(result["moaas_grouped_ordinal"])
            self.assertIsNone(result["soc_transition_state"])

    def test_conflicting_companion_field_never_derives_two_targets(self):
        source = row()
        source["original_fields"]["SOC"] = "0.0"
        result = adapt_annotation("1", source)
        self.assertIsNone(result["moaas_grouped_ordinal"])
        self.assertIsNone(result["soc_transition_state"])
        self.assertIn("unexpected_companion_annotation_for_moaas", result["unresolved_reason_codes"])

    def test_unknown_multi_marker_casing_and_space_never_guess(self):
        for marker in ("MOAAS1;LOC", "MOAAS1 LOC", "moaas1", " MOAAS1", "", "Error"):
            result = adapt_annotation("1", row(marker))
            self.assertIsNone(result["moaas_grouped_ordinal"])
            self.assertIsNone(result["soc_transition_state"])
            self.assertEqual(result["original_fields"]["EVENT"], marker)

    def test_medication_and_other_rows_preserve_unresolved_source_fields(self):
        for marker in ("BEGIN", "END", "PARA", "PROP"):
            source = row(marker, "Propofol", "20.0")
            before = copy.deepcopy(source)
            result = adapt_annotation("1", source)
            self.assertEqual(source, before)
            self.assertEqual(result["original_fields"], before["original_fields"])
            self.assertEqual(result["marker_kind"], "retained_ungraded_source_marker")
            self.assertIsNone(result["moaas_grouped_ordinal"])

    def test_clock_invalid_or_disagrees_does_not_make_a_target(self):
        source = row()
        source["recognized_time_ms"] += 4
        self.assertIsNone(adapt_annotation("1", source)["moaas_grouped_ordinal"])
        source["raw_time"] = "2026-02-31 00:00:00.000"
        self.assertIsNone(adapt_annotation("1", source)["moaas_grouped_ordinal"])

    def test_envelope_integrity_refuses_missing_fields_and_boolean_row(self):
        source = row()
        del source["original_fields"]["Misc"]
        with self.assertRaises(AnnotationRefusal):
            adapt_annotation("1", source)
        source = row()
        source["source_row"] = True
        with self.assertRaises(AnnotationRefusal):
            adapt_annotation("1", source)
        with self.assertRaises(AnnotationRefusal):
            adapt_annotation("person-1", row())


if __name__ == "__main__":
    unittest.main()
