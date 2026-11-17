"""Invented values only: full declared census plus analytical representation witnesses."""
import copy
import math
import unittest
from fractions import Fraction

from fullfield import (ConstructionError, delta_pixel, encode, prepare_fold,
                       record_deltas, rounded, select_frames, source_value)
from roster import ROSTER
from scorer import CONTRACT_SHA256, ROSTER_SHA256


def invented_intake():
    intake = {"schema": "fus_adjudicated_intake_v1", "contract_sha256": CONTRACT_SHA256,
              "source_roster_sha256": ROSTER_SHA256, "source_archive_sha256": "a" * 64,
              "intake_review_sha256": "b" * 64, "records": []}
    counter = 0
    for rid, _, _, n, _ in ROSTER:
        record = {"record_id": rid, "native_hz": 2 if n else None,
                  "reconciliation_sha256": "c" * 64,
                  "clock_mapping_sha256": "d" * 64 if n else None,
                  "representation_sha256": "e" * 64 if n else None, "trials": []}
        for i in range(n):
            counter += 1
            record["trials"].append({"source_trial_id": f"invented-{counter}", "source_order": i,
                "disposition": "eligible", "query_id": f"q_{counter:032x}", "direction": i % 8,
                "timing": {"cue": 0, "memory_start": 1, "memory_end": 3, "go": 3,
                           "baseline_start": -2, "baseline_end": -1,
                           "acquisition_start": 2, "acquisition_end": 3},
                "exclusion_reason": None, "adjudication_sha256": None})
        intake["records"].append(record)
    return intake


def frame(identity, order, start, end, pixels, complete=True):
    return {"frame_id": identity, "source_order": order, "start": start, "end": end,
            "complete": complete, "pixels": list(pixels)}


def normalized(record, memory=(4.0, 2.0, "nan", 2.0), baseline=(2.0, 2.0, 2.0, 0.0)):
    frames = [frame("early-baseline", 0, -4, -3, [900.0] * 4),
              frame("baseline", 1, -2, -1, baseline),
              frame("ends-at-cue", 2, -1, 0, [800.0] * 4),
              frame("early-memory", 3, 1, 2, [700.0] * 4),
              frame("memory", 4, 2, 3, memory),
              frame("partial-later", 5, 2.5, 3.5, [600.0] * 4),
              frame("incomplete-later", 6, 2.5, 3, [500.0] * 4, False)]
    return {"schema": "fus_normalized_fullfield_record_v1", "record_id": record["record_id"],
            "native_hz": record["native_hz"], "source_float": "binary32", "shape": [2, 2],
            "spatial_pitch": [0.1, 0.2], "spatial_pitch_unit": "mm",
            "acquisition_census_sha256": "f" * 64,
            "trials": [{"source_trial_id": t["source_trial_id"], "source_order": t["source_order"],
                        "frames": frames if t["disposition"] == "eligible" else None}
                       for t in record["trials"]]}


class ArithmeticTests(unittest.TestCase):
    def test_declared_ieee_rounding_ties_subnormal_and_overflow(self):
        midpoint = Fraction(1) + Fraction(1, 2**24)
        self.assertEqual(rounded(midpoint, "binary32"), 1.0)
        self.assertEqual(rounded(midpoint + Fraction(1, 2**80), "binary32"), 1 + 2**-23)
        self.assertEqual(rounded(Fraction(1, 2**150), "binary32"), 0.0)
        self.assertEqual(rounded(Fraction(3, 2**150), "binary32"), 2**-148)
        self.assertEqual(rounded(Fraction(2**128), "binary32"), math.inf)
        m64 = Fraction(1) + Fraction(1, 2**53)
        self.assertEqual(rounded(m64, "binary64"), 1.0)
        self.assertEqual(rounded(m64 + Fraction(1, 2**120), "binary64"), 1 + 2**-52)

    def test_separate_source_operations_and_invalid_operands(self):
        self.assertEqual(delta_pixel(3.0, 2.0, "binary32"), 0.5)
        self.assertIsNone(delta_pixel(-2.0**127, 2.0**127, "binary32"))
        for memory, baseline in [("nan", 1), (1, "+inf"), (1, 0), (1, -1), ("-inf", 1)]:
            self.assertIsNone(delta_pixel(memory, baseline, "binary64"))
        with self.assertRaises(ConstructionError):
            source_value(0.1, "binary32")
        with self.assertRaises(ConstructionError):
            source_value(True, "binary64")

    def test_exact_quantizer_mask_saturation_and_error_bound(self):
        self.assertEqual(encode(-2.0, 2.0), ((0, 0, 0), False))
        self.assertEqual(encode(0.0, 2.0), ((128, 128, 128), False))
        self.assertEqual(encode(2.0, 2.0), ((255, 255, 255), False))
        self.assertEqual(encode(3.0, 2.0), ((255, 255, 255), True))
        self.assertEqual(encode(None, 2.0), ((255, 0, 255), False))
        for i in range(-1024, 1025):
            d = Fraction(i, 512)
            pixel, saturated = encode(float(d), 2.0)
            reconstructed = Fraction(2) * (Fraction(2 * pixel[0], 255) - 1)
            self.assertFalse(saturated)
            self.assertLessEqual(abs(d - reconstructed), Fraction(2, 255))


class FullSupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.intake = invented_intake()

    def setUp(self):
        self.by_id = {r["record_id"]: r for r in self.intake["records"]}
        self.held = ROSTER[0][0]
        self.fold_key = "fold_" + "1" * 32

    def test_complete_49_rows_20622_trials_and_all_47_training_records(self):
        calls, observed = [], []
        def load(rid):
            calls.append(rid)
            # A held extreme must saturate, not change the scale.
            return normalized(self.by_id[rid], memory=(200.0, 2.0, "nan", 2.0) if rid == self.held
                              else (4.0, 2.0, "nan", 2.0))
        result = prepare_fold(self.intake, load, observed.append,
                              held_record_id=self.held, fold_key=self.fold_key)
        self.assertEqual(result["declared_source_trials"], 20622)
        self.assertEqual(result["training_records"], 47)
        self.assertEqual(result["training_maps"], 20622 - 316)
        self.assertEqual(result["scale"], 1.0)
        self.assertEqual(calls[-1], self.held)
        self.assertEqual(set(calls[:-1]), {r[0] for r in ROSTER if r[3] and r[0] != self.held})
        self.assertEqual(len(calls), 48)
        self.assertNotIn("L-S45-R1", calls)
        self.assertEqual((result["calibration_maps"], result["query_maps"]), (8, 308))
        self.assertEqual(len(observed), 316)
        self.assertEqual(sum(len(r["trials"]) - 8 for r in self.intake["records"] if r["trials"]), 20238)
        for payload in observed:
            self.assertEqual(payload["shape"], [2, 2])
            self.assertEqual(payload["spatial_pitch"], [0.1, 0.2])
            self.assertEqual(payload["rgb"], bytes([255, 255, 255, 128, 128, 128, 255, 0, 255, 255, 0, 255]))
            self.assertEqual((payload["invalid_pixels"], payload["saturated_pixels"]), (2, 1))
            self.assertNotIn("record_id", payload)
            self.assertNotIn("source_trial_id", payload)
            self.assertNotIn("timing", payload)
            self.assertEqual("direction" in payload, payload["role"] == "calibration")

    def test_last_complete_selection_and_no_presumed_hz(self):
        record = self.by_id[self.held]
        source = normalized(record)
        baseline, memory = select_frames(source["trials"][0]["frames"], record["trials"][0]["timing"])
        self.assertEqual((baseline["frame_id"], memory["frame_id"]), ("baseline", "memory"))
        # An acquisition crossing the cue is never a pre-cue baseline.
        frames = copy.deepcopy(source["trials"][0]["frames"])
        frames.append(frame("crosses-cue", len(frames), -0.5, 0.5, [9] * 4))
        self.assertEqual(select_frames(frames, record["trials"][0]["timing"])[0]["frame_id"], "baseline")

    def test_ambiguous_last_and_frozen_selection_mismatch_refuse(self):
        record = self.by_id[self.held]
        frames = normalized(record)["trials"][0]["frames"]
        frames.append(frame("tied", len(frames), 2.25, 3, [1] * 4))
        with self.assertRaises(ConstructionError):
            select_frames(frames, record["trials"][0]["timing"])
        frames.pop()
        frames[1]["end"] = -0.5
        with self.assertRaises(ConstructionError):
            select_frames(frames, record["trials"][0]["timing"])

    def test_missing_frame_source_order_crop_and_missing_trial_refuse(self):
        record = self.by_id[self.held]
        for change in (lambda x: x["trials"].pop(),
                       lambda x: x["trials"][0].update(source_order=1),
                       lambda x: x["trials"][0]["frames"][4].update(pixels=[1]),
                       lambda x: x["trials"][0]["frames"][4].update(complete=False)):
            source = normalized(record)
            change(source)
            with self.assertRaises(ConstructionError):
                list(record_deltas(record, source))

    def test_full_intake_admission_precedes_any_callback(self):
        intake = dict(self.intake)
        intake["records"] = self.intake["records"][:-1]
        def forbidden(*args):
            self.fail("callback before complete support admission")
        with self.assertRaises(ConstructionError):
            prepare_fold(intake, forbidden, forbidden, held_record_id=self.held, fold_key=self.fold_key)

    def test_zero_scale_refuses_before_held_callback(self):
        calls = []
        def load(rid):
            self.assertNotEqual(rid, self.held)
            calls.append(rid)
            return normalized(self.by_id[rid], memory=(2, 2, 2, 2), baseline=(2, 2, 2, 2))
        with self.assertRaises(ConstructionError):
            prepare_fold(self.intake, load, lambda x: self.fail("zero scale emitted"),
                         held_record_id=self.held, fold_key=self.fold_key)
        self.assertEqual(len(calls), 47)

    def test_adjudicated_missingness_retained_never_added(self):
        record = copy.deepcopy(self.by_id[self.held])
        excluded = record["trials"][20]
        excluded.update(disposition="adjudicated_excluded", query_id=None, timing=None,
                        exclusion_reason="missing_baseline", adjudication_sha256="b" * 64)
        source = normalized(record)
        maps = list(record_deltas(record, source))
        self.assertEqual(len(maps), 315)
        self.assertEqual(len(source["trials"]), 316)
        source["trials"][20]["frames"] = []
        with self.assertRaises(ConstructionError):
            list(record_deltas(record, source))

    def test_late_failure_has_no_complete_receipt(self):
        # Partial staged maps must never be committed as a completed fold.
        emitted = []
        def load(rid):
            obj = normalized(self.by_id[rid])
            if rid == self.held:
                obj["trials"][-1] = dict(obj["trials"][-1], source_order=-1)
            return obj
        with self.assertRaises(ConstructionError):
            prepare_fold(self.intake, load, emitted.append, held_record_id=self.held, fold_key=self.fold_key)
        self.assertEqual(len(emitted), 315)


if __name__ == "__main__":
    unittest.main()
