"""Generated controls only; no authentic source or saved projection access."""
import importlib.util
import json
from pathlib import Path
import unittest


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


HERE = Path(__file__).resolve().parent
m = load("paired_windows", HERE / "paired_windows.py")
p = load("dosei_policy", HERE.parent / "source-eeg-numeric-v1/numeric_policy.py")
KEY = b"G" * 32  # Explicit generated fixture; never use this key for source cases.


def event(row, ms, target=3, recording="41", reasons=None):
    return {"schema": "dosei_private_annotation_event_v1", "visibility": "evaluator_private",
            "source_event_id": f"recording:{recording}/row:{row}", "recording_id": recording,
            "source_row": row, "recognized_time_ms": ms, "condition": m.CONDITION,
            "marker_kind": "moaas_assessment_marker", "moaas_grouped_ordinal": target,
            "biological_person_id": None, "assessment_onset_verified": False,
            "unresolved_reason_codes": reasons or []}


def row(index, ms=None, values=(1.0, 2.0), quality=(0, 0)):
    return (index, 100000 + index * 4 if ms is None else ms, *values, *quality)


class Windows(unittest.TestCase):
    def builder(self):
        return m.PairedWindowBuilder("41", KEY, p)

    def test_full_7500_rows_exact_cutoff_and_no_current_or_future_values(self):
        outputs = []
        for current in ((3.0, 4.0), (180.0, -180.0)):
            b = self.builder()
            for i in range(7500):
                self.assertIsNone(b.consume(row(i)))
            packet, private = b.consume(row(7500, values=current), event(7500, 130000))
            outputs.append(packet)
            b.consume(row(7501, values=(-170.0, 170.0)))
            self.assertEqual(packet["coverage"], {"source_prefix_missing_ms": 0,
                             "full_interval_recorded": True, "row_count": 7500})
            self.assertEqual(packet["relative_time_ms"], list(range(-30000, 0, 4)))
            self.assertEqual(private["source_row"], 7500)
        self.assertEqual(outputs[0], outputs[1])

    def test_duplicate_earlier_timestamps_retained_but_marker_time_excluded(self):
        b = self.builder()
        for i in range(7501):
            # One duplicate at time100004, all original rows retained.
            b.consume(row(i, 100000 + max(0, i - 1) * 4))
        packet, _ = b.consume(row(7501, 130000), event(7501, 130000))
        self.assertEqual(packet["coverage"]["row_count"], 7501)
        self.assertEqual(packet["relative_time_ms"][:2], [-30000, -30000])
        b2 = self.builder()
        for i in range(7501):
            b2.consume(row(i))
        same_time, _ = b2.consume(row(7501, 130000), event(7501, 130000))
        self.assertEqual(same_time["coverage"]["row_count"], 7500)
        self.assertNotIn(0, same_time["relative_time_ms"])

    def test_all_missing_and_short_prefix_are_retained(self):
        b = self.builder()
        blank, quality = p.parse_sample("")
        for i in range(3):
            b.consume(row(i, values=(blank, blank), quality=(quality, quality)))
        packet, private = b.consume(row(3), event(3, 100012, None, reasons=["ambiguous"]))
        self.assertEqual(packet["values_uv"], [[None, None]] * 3)
        self.assertEqual(packet["observation_mask"], [[False, False]] * 3)
        self.assertFalse(packet["coverage"]["full_interval_recorded"])
        self.assertEqual(packet["coverage"]["source_prefix_missing_ms"], 29988)
        self.assertIsNone(private["moaas_grouped_ordinal"])
        self.assertFalse(private["canonical_scoring_admitted"])

    def test_label_changes_do_not_change_public_packet(self):
        outputs = []
        for target in (1, 5, None):
            b = self.builder()
            b.consume(row(0))
            packet, private = b.consume(row(1), event(1, 100004, target))
            self.assertEqual(private["moaas_grouped_ordinal"], target)
            self.assertEqual(set(packet), m.PUBLIC_FIELDS)
            text = json.dumps(packet, allow_nan=False)
            for forbidden in ("recording_id", "source_row", "marker_time_ms", "moaas", "soc", "100004"):
                self.assertNotIn(forbidden, text.lower())
            outputs.append(packet)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1], outputs[2])

    def test_repeated_assessments_get_distinct_stable_arm_ids(self):
        b = self.builder()
        first = b.consume(row(0), event(0, 100000, 2))
        second = b.consume(row(1), event(1, 100004, 2))
        self.assertNotEqual(first[0]["case_id"], second[0]["case_id"])
        self.assertEqual(b.case_count, 2)
        self.assertEqual(first[0]["case_id"], m.opaque_case_id(KEY, "41", 0))
        self.assertNotEqual(first[0]["case_id"], m.opaque_case_id(b"x" * 32, "41", 0))
        self.assertEqual(first[0]["coverage"]["row_count"], 0)

    def test_endpoints_remain_observed_and_invalid300_is_not_signal(self):
        b = self.builder()
        b.consume(row(0, values=(187.5, 300.0), quality=(p.EXACT_ENDPOINT, p.OUT_OF_RANGE)))
        packet, _ = b.consume(row(1), event(1, 100004))
        self.assertEqual(packet["values_uv"], [[187.5, None]])
        self.assertEqual(packet["observation_mask"], [[True, False]])
        self.assertEqual(packet["source_endpoint_mask"], [[True, False]])
        for value, quality in ((-187.5, p.EXACT_ENDPOINT), (0.0, p.NONZERO_UNDERFLOW),
                               (float("nan"), p.BLANK), (187.5, p.OUT_OF_RANGE)):
            m.observe(value, quality, p)
        for value, quality in ((188.0, 0), (1.0, p.EXACT_ENDPOINT),
                               (3.0, p.NONZERO_UNDERFLOW), (300.0, p.BLANK), (0.0, 128)):
            with self.assertRaises(m.PacketRefusal):
                m.observe(value, quality, p)

    def test_source_row_clock_and_event_alignment_fail_closed(self):
        for bad in (row(2), row(1, 99999), row(1, 100008),
                    (True, 100004, 1.0, 2.0, 0, 0)):
            b = self.builder(); b.consume(row(0))
            with self.assertRaises(m.PacketRefusal): b.consume(bad)
        for changed in ({"recording_id": "43"}, {"source_row": 2},
                        {"recognized_time_ms": 100000}, {"assessment_onset_verified": True},
                        {"biological_person_id": "invented-person"}, {"moaas_grouped_ordinal": True}):
            b = self.builder(); b.consume(row(0))
            e = event(1, 100004); e.update(changed)
            with self.assertRaises(m.PacketRefusal): b.consume(row(1), e)

    def test_failure_poison_prevents_pruned_history_retry(self):
        b = self.builder()
        for i in range(7501): b.consume(row(i))
        with self.assertRaises(m.PacketRefusal):
            b.consume(row(7501), event(7501, 130004, target=99))
        self.assertTrue(b.failed)
        with self.assertRaises(m.PacketRefusal):
            b.consume(row(7501, 130000), event(7501, 130000))
        fresh = self.builder()
        with self.assertRaises(m.PacketRefusal): fresh.consume(row(1))
        with self.assertRaises(m.PacketRefusal): fresh.consume(row(0), event(0, 100000))

    def test_non_target_markers_are_not_added_as_ordinal_cases(self):
        b = self.builder(); e = event(0, 100000)
        e.update(marker_kind="soc_transition_marker", moaas_grouped_ordinal=None)
        self.assertIsNone(b.consume(row(0), e))
        self.assertEqual(b.case_count, 0)

    def test_private_key_and_source_identity_envelopes(self):
        for args in ((b"x", "41", 0), (KEY, "041", 0), (KEY, "４１", 0),
                     (KEY, "9" * 10000, 0), (KEY, "41", True), (KEY, "41", -1)):
            with self.assertRaises(m.PacketRefusal): m.opaque_case_id(*args)


if __name__ == "__main__":
    unittest.main()
