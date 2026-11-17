"""Generated clock, identity, source binding and split adversarial controls."""

from copy import deepcopy
from fractions import Fraction
import unittest

from protocol import (ContractError, Reference, canonical_bytes, fold_map,
                      packet, prepare_reference)
from evaluate import compare, evaluate
from test_metrics import fixture, predictions, PRIVATE_KEY, RECORDINGS


def source_reader(_rid, start, stop):
    return [[n + channel / 100 for channel in range(18)] for n in range(start, stop)]


def rational_fixture(num, den, count):
    _, description, _ = fixture()
    record = description["recordings"][0]
    seconds = int(Fraction(count * den, num))
    record.update(sample_rate={"num": num, "den": den}, sample_count=count,
                  labels=[[0] * seconds for _ in range(3)],
                  quality_flags=[False] * seconds)
    return prepare_reference(description, source_reader, PRIVATE_KEY), description


class PacketControls(unittest.TestCase):
    def test_fractional_clock_preserves_native_phase_and_variable_sample_counts(self):
        reference, _ = rational_fixture(7, 4, 56)
        first = packet(reference, "eeg1", 30, source_reader)  # [1,31)
        second = packet(reference, "eeg1", 31, source_reader)  # [2,32)
        # Independent enumeration of native times, not the implementation's ceil formula.
        expected1 = [n for n in range(56) if Fraction(1) <= Fraction(n * 4, 7) < 31]
        expected2 = [n for n in range(56) if Fraction(2) <= Fraction(n * 4, 7) < 32]
        self.assertEqual((len(expected1), len(expected2)), (53, 52))
        self.assertEqual([row[0] for row in first["samples"]], expected1)
        self.assertEqual([row[0] for row in second["samples"]], expected2)
        self.assertEqual(first["sample_clock"], {"first_tick": 1, "step_ticks": 4, "ticks_per_second": 7})
        self.assertEqual(second["sample_clock"], {"first_tick": 2, "step_ticks": 4, "ticks_per_second": 7})
        self.assertEqual(first["prediction_interval_seconds"], [29, 30])

    def test_reader_is_requested_only_exact_half_open_causal_interval(self):
        reference, _ = rational_fixture(7, 4, 56)
        requests = []

        def reader(rid, start, stop):
            requests.append((rid, start, stop))
            return source_reader(rid, start, stop)

        packet(reference, "eeg1", 30, reader)
        self.assertEqual(requests, [("eeg1", 2, 55)])

    def test_incomplete_last_second_does_not_create_a_prediction(self):
        reference, _ = rational_fixture(10, 3, 104)
        result = evaluate(reference, predictions(reference, 0))
        infant = next(row for row in result["infants"] if row["recording_id"] == "eeg1")
        self.assertEqual(infant["n"], 2)  # 31 complete seconds: k29,30.
        self.assertEqual(result["n_cases"], 80)
        self.assertEqual(infant["excluded_initial_complete_seconds"], 29)
        remainder = infant["excluded_final_incomplete_second"]
        self.assertEqual(Fraction(remainder["num"], remainder["den"]), Fraction(1, 5))
        with self.assertRaises(ContractError):
            packet(reference, "eeg1", 31, source_reader)

    def test_labels_cannot_change_public_packet_bytes(self):
        ref, description, reader = fixture()
        changed = deepcopy(description)
        changed["recordings"][0]["labels"][0][29] = 1
        other = prepare_reference(changed, reader, PRIVATE_KEY)
        self.assertEqual(canonical_bytes(packet(ref, "eeg1", 29, reader)),
                         canonical_bytes(packet(other, "eeg1", 29, reader)))
        self.assertNotEqual(ref.reference_sha256, other.reference_sha256)

    def test_packet_allowlist_excludes_private_provenance_and_absolute_offsets(self):
        ref, _, reader = fixture()
        body = packet(ref, "eeg1", 29, reader)
        self.assertEqual(set(body), {
            "case_id", "assessment_id", "protocol_id", "representation_sha256", "fold",
            "schema", "montage", "units", "duration_seconds", "prediction_interval_seconds",
            "sample_clock", "samples", "quality_flags", "detector_sha256", "input_sha256",
        })
        self.assertEqual(len(body["case_id"]), 64)
        self.assertNotIn(b'eeg1', canonical_bytes(body))
        self.assertNotIn(PRIVATE_KEY, canonical_bytes(body))

    def test_original_flags_are_preserved_and_frozen(self):
        ref, _, reader = fixture(durations={"eeg1": 32}, flags={"eeg1": {0, 30}})
        body = packet(ref, "eeg1", 31, reader)
        self.assertEqual(len(body["quality_flags"]), 30)
        self.assertEqual([i for i, value in enumerate(body["quality_flags"]) if value], [28])
        changed = ref.document
        changed["recordings"][0]["quality_flags"][30] = False
        modified = Reference(changed, PRIVATE_KEY)
        with self.assertRaises(ContractError):
            packet(modified, "eeg1", 31, reader)

    def test_samples_changed_after_binding_are_rejected(self):
        ref, _, reader = fixture()

        def modified(rid, start, stop):
            rows = reader(rid, start, stop)
            rows[-1][0] += 0.001
            return rows

        with self.assertRaises(ContractError):
            packet(ref, "eeg1", 29, modified)

    def test_wrong_sample_count_channel_count_and_nonfinite_values_fail(self):
        ref, _, reader = fixture()
        for defect in ("future_sample", "missing_sample", "channel", "nan", "bool"):
            def broken(rid, start, stop):
                rows = reader(rid, start, stop)
                if defect == "future_sample":
                    rows.append([0] * 18)
                elif defect == "missing_sample":
                    rows.pop()
                elif defect == "channel":
                    rows[0].pop()
                elif defect == "nan":
                    rows[0][0] = float("nan")
                else:
                    rows[0][0] = True
                return rows
            with self.subTest(defect=defect), self.assertRaises(ContractError):
                packet(ref, "eeg1", 29, broken)

    def test_wrong_case_key_and_unbound_reference_fail(self):
        ref, description, _ = fixture()
        with self.assertRaises(ContractError):
            Reference(ref.document, b"different-private-key-0123456789abcd")
        with self.assertRaises(ContractError):
            Reference(description, PRIVATE_KEY)


class SourceAndSplitControls(unittest.TestCase):
    def test_hash_folds_are_input_order_independent_and_balanced(self):
        folds = fold_map(RECORDINGS, "fixture-seed")
        self.assertEqual(folds, fold_map(reversed(RECORDINGS), "fixture-seed"))
        self.assertEqual(sorted(list(folds.values()).count(fold) for fold in range(5)), [15, 16, 16, 16, 16])
        ref, _, _ = fixture()
        for fold in range(5):
            parts = ref.partition(fold)
            self.assertEqual(set().union(*[set(x) for x in parts.values()]), set(RECORDINGS))
            self.assertEqual(sum(len(x) for x in parts.values()), 79)
            self.assertTrue(all(parts.values()))

    def test_held_infant_cannot_enter_development(self):
        ref, description, reader = fixture()
        description["development_by_fold"]["0"] = ref.partition(0)["held"][:1]
        with self.assertRaises(ContractError):
            prepare_reference(description, reader, PRIVATE_KEY)

    def test_zero_support_infant_does_not_disappear(self):
        _, description, reader = fixture()
        record = description["recordings"][0]
        record.update(sample_count=29, labels=[[0] * 29 for _ in range(3)], quality_flags=[False] * 29)
        with self.assertRaises(ContractError):
            prepare_reference(description, reader, PRIVATE_KEY)

    def test_nonzero_clock_origin_wrong_montage_and_bad_flags_fail(self):
        _, description, reader = fixture()
        for defect in ("origin", "montage", "flag_count", "flag_type", "nonreduced_rate", "unknown_field"):
            changed = deepcopy(description)
            record = changed["recordings"][0]
            if defect == "origin":
                record["sample_zero_annotation_second"] = 1
            elif defect == "montage":
                changed["montage"][0] = "ECG"
            elif defect == "flag_count":
                record["quality_flags"].pop()
            elif defect == "flag_type":
                record["quality_flags"][0] = 0
            elif defect == "nonreduced_rate":
                record["sample_rate"] = {"num": 2, "den": 2}
            else:
                record["clinical_report"] = "forbidden unrecognized field"
            with self.subTest(defect=defect), self.assertRaises(ContractError):
                prepare_reference(changed, reader, PRIVATE_KEY)

    def test_frozen_bindings_require_every_infant_and_timestamp(self):
        ref, _, _ = fixture()
        for defect in ("infant", "timestamp", "hash"):
            changed = ref.document
            bindings = changed["input_sha256_by_recording"]
            if defect == "infant":
                del bindings["eeg1"]
            elif defect == "timestamp":
                bindings["eeg1"].pop()
            else:
                bindings["eeg1"][0] = "wrong"
            with self.subTest(defect=defect), self.assertRaises(ContractError):
                Reference(changed, PRIVATE_KEY)

    def test_private_snapshot_cannot_be_changed_by_mutating_export(self):
        ref, _, _ = fixture()
        exported = ref.document
        exported["recordings"][0]["labels"][0][29] = 1
        self.assertEqual(evaluate(ref, predictions(ref, 0))["primary_soft_vote_brier"], 0)

    def test_comparison_is_paired_by_infant_and_rejects_other_reference(self):
        ref, _, _ = fixture()
        left = evaluate(ref, predictions(ref, 0.5))
        right = evaluate(ref, predictions(ref, 0))
        result = compare(left, right)
        self.assertEqual(result["macro_right_minus_left_soft_vote_brier"], -0.25)
        self.assertEqual(len(result["infants"]), 79)
        changed = deepcopy(right)
        changed["reference_sha256"] = "0" * 64
        with self.assertRaises(ContractError):
            compare(left, changed)
        changed = deepcopy(right)
        changed["infants"][0] = changed["infants"][1]
        with self.assertRaises(ContractError):
            compare(left, changed)

    def test_comparison_refuses_zero_support_malformed_counts_and_inconsistent_macro(self):
        ref, _, _ = fixture()
        original = evaluate(ref, predictions(ref, 0.5))
        for defect in ("zero", "boolean", "missing_hash", "total", "macro", "missing_loss", "missing_id"):
            changed = deepcopy(original)
            if defect == "zero":
                changed["n_infants"] = changed["n_cases"] = 0
                for row in changed["infants"]:
                    row["n"] = 0
            elif defect == "boolean":
                changed["infants"][0]["n"] = True
            elif defect == "missing_hash":
                del changed["reference_sha256"]
            elif defect == "total":
                changed["n_cases"] += 1
            elif defect == "macro":
                changed["primary_soft_vote_brier"] = 1
            elif defect == "missing_loss":
                del changed["infants"][0]["soft_vote_brier"]
            else:
                del changed["infants"][0]["recording_id"]
            with self.subTest(defect=defect), self.assertRaises(ContractError):
                compare(changed, changed)
if __name__ == "__main__":
    unittest.main()
