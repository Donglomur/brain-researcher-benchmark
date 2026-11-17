"""Generated mathematical/software controls; no authentic targets or model trials."""
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score


MEANS = [2.0] * score.CHANNELS
COUNTS = [0] * 48 + [2] * 48
REFERENCES = {name: [float(index + 1)] * score.CHANNELS
              for index, name in enumerate(score.REFERENCE_NAMES)}


def prediction(sequence, means=None):
    return {"sequence": sequence, "means": MEANS if means is None else means}


def outcome(sequence, counts=None, references=None):
    return {"sequence": sequence, "counts": COUNTS if counts is None else counts,
            "reference_means": REFERENCES if references is None else references}


class FullEpisodeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Warmup is both present and radically different, so an accidental
        # denominator/support inclusion changes every expected result.
        predictions = (prediction(i, [1e200] * 96 if i < 10 else None)
                       for i in range(score.ROUNDS))
        observations = (outcome(i, [1000] * 96 if i < 10 else None)
                        for i in range(score.ROUNDS))
        cls.result = score.score_records(predictions, observations)

    def test_exact_support_and_spike_weighting(self):
        result = self.result
        self.assertEqual(result["protocol_rounds"], 22100)
        self.assertEqual(result["scored_cells"], 2120640)
        self.assertEqual(result["observed_spikes"], 2120640)
        self.assertEqual((result["target_bin_first"], result["target_bin_last"]), (3010, 25099))
        self.assertFalse(result["causal_access_established"])

    def test_full_likelihood_retains_factorial(self):
        # Half the cells are k=0 and half k=2: LL/cell = log(2)/2 - 2.
        expected_mean_nll = 2 - math.log(2) / 2
        self.assertAlmostEqual(self.result["mean_nll"], expected_mean_nll, places=12)
        self.assertAlmostEqual(self.result["full_poisson_log_likelihood"],
                               -2120640 * expected_mean_nll, places=7)

    def test_all_six_signed_contrasts_with_common_denominator(self):
        for index, name in enumerate(score.REFERENCE_NAMES):
            ref = index + 1
            # Mean count is 1. This independent closed form uses log2.
            expected_bps = math.log2(2 / ref) - (2 - ref) / math.log(2)
            result = self.result["signed_reference_contrasts"][name]
            self.assertAlmostEqual(result["bits_per_spike"], expected_bps, places=12)
        self.assertEqual(self.result["bits_per_spike_vs_calibration_rate"], 0)
        self.assertLess(self.result["signed_reference_contrasts"]["source_rate"]["bits_per_spike"], 0)
        self.assertGreater(self.result["signed_reference_contrasts"]["self_history_frozen"]["bits_per_spike"], 0)

    def test_quiet_channels_remain_in_full_likelihood(self):
        quiet, active = self.result["per_channel"][0], self.result["per_channel"][95]
        self.assertEqual(quiet["full_poisson_log_likelihood"], -2 * 22090)
        self.assertEqual(quiet["observed_spikes"], 0)
        self.assertEqual(quiet["denominator_status"], "undefined_zero_spikes")
        self.assertTrue(all(x is None for x in quiet["bits_per_spike"].values()))
        self.assertEqual(active["observed_spikes"], 44180)
        self.assertEqual(len(self.result["per_channel"]), 96)

    def test_json_output_is_finite(self):
        json.dumps(self.result, allow_nan=False)


class RejectionControls(unittest.TestCase):
    def reject_first(self, predicted=None, observed=None):
        with self.assertRaises(score.ScoreError) as caught:
            score.score_records([prediction(0) if predicted is None else predicted],
                                [outcome(0) if observed is None else observed])
        self.assertNotIn("partial score forbidden", str(caught.exception))

    def test_values_rejected_even_in_warmup(self):
        for value in (0, -1, True, "1", float("nan"), float("inf"), 10**400):
            with self.subTest(value=str(value)[:20]):
                self.reject_first(predicted=prediction(0, [value] * 96))
        for value in (False, 0.0, -1, 2**32):
            with self.subTest(count=value):
                self.reject_first(observed=outcome(0, [value] * 96))

    def test_identity_and_completeness(self):
        for seq in (True, 1, -1, "0"):
            self.reject_first(predicted=prediction(seq))
        self.reject_first(predicted=prediction(0, [1.0] * 95))
        self.reject_first(observed=outcome(0, [1] * 97))
        self.reject_first(observed=outcome(0, references={"calibration_rate": [1] * 96}))
        self.reject_first(predicted={**prediction(0), "nonce": "not-a-protocol-admission"})
        # Complete individual rows never authorize scoring a favorable prefix.
        with self.assertRaisesRegex(score.ScoreError, "partial score forbidden"):
            score.score_records((prediction(i) for i in range(11)),
                                (outcome(i) for i in range(11)))

    def test_duplicate_and_out_of_order_later_identity(self):
        with self.assertRaisesRegex(score.ScoreError, "out-of-order"):
            score.score_records([prediction(0), prediction(0)], [outcome(0), outcome(1)])

    def test_extra_round_detection_without_repeated_arithmetic(self):
        # Guard the extra-row branch independently of costly full accumulation.
        # Only this parser/control test temporarily reduces constants; actual
        # complete-episode controls above always use the original fixed support.
        with patch.object(score, "ROUNDS", 1), self.assertRaisesRegex(score.ScoreError, "extra rounds"):
            score.score_records([prediction(0), prediction(1)], [outcome(0)])
        with patch.object(score, "ROUNDS", 1), self.assertRaisesRegex(score.ScoreError, "extra rounds"):
            score.score_records([prediction(0)], [outcome(0), outcome(1)])

    def test_accumulation_overflow_fails_instead_of_clipping(self):
        with self.assertRaisesRegex(score.ScoreError, "overflow"):
            score.score_records((prediction(i, [1e308] * 96) for i in range(13)),
                                (outcome(i) for i in range(13)))


class FileControls(unittest.TestCase):
    def test_strict_json_and_line_bounds(self):
        for raw in (b'{"x":1,"x":2}\n', b'{"x":NaN}\n', b'\n', b'{}', b'\xff\n'):
            with self.subTest(raw=raw), self.assertRaises(score.ScoreError):
                list(score._jsonl(io.BytesIO(raw), 4096))
        with self.assertRaises(score.ScoreError):
            list(score._jsonl(io.BytesIO(b'{} \n'), 3))
        self.assertEqual(list(score._jsonl(io.BytesIO(b'{}\n'), 4096)), [{}])

    def test_digest_is_of_exact_consumed_bytes(self):
        raw = b'{"sequence":0}\n{"sequence":1}\n'
        digest = hashlib.sha256()
        self.assertEqual(len(list(score._jsonl(io.BytesIO(raw), 4096, digest))), 2)
        self.assertEqual(digest.hexdigest(), hashlib.sha256(raw).hexdigest())

    def test_untrusted_digest_never_releases_result(self):
        # Exercise the file/digest boundary independently of arithmetic with a
        # consuming scorer stub; native success is covered by complete streams.
        def consume(candidate, truth):
            list(candidate), list(truth)
            return {"sentinel": "must-not-escape-on-mismatch"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "generated.jsonl"
            path.write_bytes(b'{}\n')
            with patch.object(score, "score_records", consume):
                with self.assertRaisesRegex(score.ScoreError, "SHA-256 mismatch"):
                    score.score_files(path, path, "0" * 64)
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                result = score.score_files(path, path, digest)
                self.assertEqual(result["operator_stream_sha256"], digest)
        with self.assertRaises(score.ScoreError):
            score.score_files(Path("missing"), Path("missing"), "not-a-digest")


class ZeroEpisodeControls(unittest.TestCase):
    def test_all_zero_denominator_is_undefined_not_clipped(self):
        result = score.score_records((prediction(i) for i in range(score.ROUNDS)),
                                     (outcome(i, [0] * 96) for i in range(score.ROUNDS)))
        self.assertIsNone(result["bits_per_spike_vs_calibration_rate"])
        self.assertEqual(result["denominator_status"], "undefined_zero_spikes")
        self.assertEqual(result["mean_nll"], 2)
        self.assertEqual(result["scored_cells"], 2120640)


if __name__ == "__main__":
    unittest.main()
