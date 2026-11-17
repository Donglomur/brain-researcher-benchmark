"""Generated software controls only. No source labels, neural data or model runs."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


PATH = Path(__file__).resolve().parents[1] / "prepare.py"
spec = importlib.util.spec_from_file_location("neural015_prepare_test", PATH)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def alignment(payload):
    return {"recording_id": "sub_1_trial000", "movie_id": "fantastic-mr-fox",
            "sample_count": 5000, "transcript_sha256": sha(payload),
            "triggers": [{"movie_time_seconds": 0, "neural_sample_index": 100},
                         {"movie_time_seconds": 2, "neural_sample_index": 4196}],
            "max_clock_residual_samples": 0}


class ExtractionControls(unittest.TestCase):
    def test_missing_nuisance_features_do_not_select_words(self):
        payload = b"text,start,end,gpt2_surprisal,motion\nfirst,0.5,0.7,,\nsecond,1.0,,nan,\n,1.5,,,\n"
        out = p.extract_word_starts(payload, sha(payload))
        self.assertEqual(out["source_record_count"], 3)
        self.assertEqual(out["word_count"], 3)
        self.assertEqual([row["movie_time_seconds"] for row in out["word_starts"]], [.5, 1., 1.5])
        self.assertNotIn("first", json.dumps(out))

    def test_sorting_keeps_row_identity_and_coincident_words(self):
        payload = b"word_idx,start\n7,1.5\n7,0.5\n9,0.5\n"
        out = p.extract_word_starts(payload, sha(payload))
        self.assertEqual([row["source_record_number"] for row in out["word_starts"]], [2, 3, 1])
        self.assertEqual([row["movie_time_seconds"] for row in out["word_starts"]], [.5, .5, 1.5])

    def test_csv_quoting_bom_and_multiline_fields_preserve_record_identity(self):
        payload = b'\xef\xbb\xbftext,start\r\n"hello, world",0.5\r\n"two\nlines",1.0\r\n'
        out = p.extract_word_starts(payload, sha(payload))
        self.assertEqual([row["source_record_number"] for row in out["word_starts"]], [1, 2])
        self.assertEqual(out["transcript_sha256"], sha(payload))

    def test_invalid_start_never_drops_a_row(self):
        for value in ("", "NA", "nan", "inf", "-0.1", "True", "1e9999"):
            with self.subTest(value=value):
                payload = ("text,start\na,0.5\nb," + value + "\n").encode()
                with self.assertRaises(p.ContractError):
                    p.extract_word_starts(payload, sha(payload))

    def test_invalid_tables_reject_entire_extract(self):
        for payload in (b"", b"start\n", b"end\n1\n", b"start,start\n1,1\n",
                        b"text,start\nx,1,extra\n", b"text,start\nx\n",
                        b"start\n1\n\n", b'text,start\n"unclosed,1\n', b"start\n\xff\n"):
            with self.subTest(payload=payload):
                with self.assertRaises(p.ContractError):
                    p.extract_word_starts(payload, sha(payload))

    def test_exact_source_digest_is_required(self):
        payload = b"start\n0.5\n"
        with self.assertRaises(p.ContractError):
            p.extract_word_starts(payload, "0" * 64)
        with self.assertRaises(p.ContractError):
            p.extract_word_starts(payload, sha(payload).upper())


class AlignmentControls(unittest.TestCase):
    def test_all_words_reach_sample_mapping_with_no_feature_filter(self):
        payload = b"start,motion\n1.5,\n0.5,\n0.5,\n"
        out = p.prepare_unpaused_recording(payload, alignment(payload))
        self.assertEqual(out["word_onset_samples"], [1124, 1124, 3172])
        self.assertEqual(out["source_record_numbers_in_sample_order"], [2, 3, 1])
        self.assertEqual(out["source_record_count"], out["word_count"])
        self.assertFalse(out["native_alignment_validated"])

    def test_wrong_join_and_out_of_recording_triggers_fail(self):
        payload = b"start\n0.5\n"
        for key, value in (("movie_id", "another-movie"), ("recording_id", "unknown"),
                           ("sample_count", 4000), ("sample_count", True)):
            data = alignment(payload)
            data[key] = value
            with self.subTest(key=key):
                with self.assertRaises(p.ContractError):
                    p.prepare_unpaused_recording(payload, data)

    def test_uncovered_word_fails_without_clipping_or_subset_selection(self):
        payload = b"start\n0.5\n2.1\n"
        with self.assertRaisesRegex(p.ContractError, "coverage"):
            p.prepare_unpaused_recording(payload, alignment(payload))

    def test_pause_or_replay_clock_is_not_inferred(self):
        payload = b"start\n0.5\n"
        for movie_time, sample_index in ((2, 4500), (1, 4500), (3, 4500)):
            data = alignment(payload)
            data["triggers"].append({"movie_time_seconds": movie_time, "neural_sample_index": sample_index})
            with self.subTest(movie_time=movie_time):
                with self.assertRaises(p.ContractError):
                    p.prepare_unpaused_recording(payload, data)

    def test_original_target_free_query_remains_unchanged(self):
        # Reuse only generated reference constructor; real private targets are absent.
        fixture_path = p.BASE / "tests" / "test_evaluator.py"
        spec = importlib.util.spec_from_file_location("generated_reference_fixture", fixture_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        ref, submission = module.fixture()
        before = p.e.public_query(ref)
        payload = b"start,motion\n0,\n0.0029296875,\n"
        data = alignment(payload)
        data["sample_count"] = 20
        data["triggers"] = [{"movie_time_seconds": 0, "neural_sample_index": 4},
                            {"movie_time_seconds": 0.005859375, "neural_sample_index": 16}]
        prepared = p.prepare_unpaused_recording(payload, data)
        row = next(row for row in ref["recordings"] if row["recording_id"] == data["recording_id"])
        row["word_onset_samples"] = prepared["word_onset_samples"]
        self.assertEqual(row["word_onset_samples"], [4, 10])
        self.assertEqual(p.e.public_query(ref), before)
        self.assertEqual(p.e.evaluate(ref, submission)["primary_uniform_grid"]["participant_macro"]["neural_average_precision"], 1)

    def test_cli_private_output_and_failure_preserve_existing_files(self):
        payload = b"start\n0.5\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transcript = root / "generated.csv"
            output = root / "private.json"
            transcript.write_bytes(payload)
            args = ["extract", str(transcript), "--expected-sha256", sha(payload), "--output", str(output)]
            self.assertEqual(p.main(args), 0)
            first = output.read_bytes()
            self.assertEqual(os.stat(output).st_mode & 0o777, 0o600)
            self.assertEqual(p.main(args), 2)
            self.assertEqual(output.read_bytes(), first)
            self.assertEqual(transcript.read_bytes(), payload)
            bad = root / "must-not-exist.json"
            args[-1] = str(bad)
            args[3] = "0" * 64
            self.assertEqual(p.main(args), 2)
            self.assertFalse(bad.exists())


if __name__ == "__main__":
    unittest.main()
