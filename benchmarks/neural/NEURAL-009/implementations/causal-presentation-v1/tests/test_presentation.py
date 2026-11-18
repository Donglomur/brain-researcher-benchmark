"""Generated protocol composition checks, not authentic EEG or model results."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--implementations", type=Path, default=HERE.parent)
args, remaining = parser.parse_known_args()
spec = importlib.util.spec_from_file_location("presentation", HERE / "presentation.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)
D = P.Dependencies(args.implementations)
INDEX, PEOPLE, INDEX_SHA = D.core.source_index()
POLICY = D.core.recommended_policy()
SECRET = b"generated opaque test key only 0000"
WRITTEN = 0


def write(path, body):
    global WRITTEN
    WRITTEN += len(body)
    assert WRITTEN <= 16384
    path.write_bytes(body)


def fixture(label="A-B", ticks=2, rate=30):
    rows = [{"recording_id": name, "biological_person": r["biological_person"],
             "native_sample_rate_hz": rate, "native_sample_count": ticks * rate // 10,
             "observed_ticks": ticks, "predictor_channels": [{"index": 0, "label": label}]}
            for name, r in sorted(INDEX.items())]
    support = {"schema": "neural009_public_support_v1", "task_id": "NEURAL-009",
               "source_index_sha256": INDEX_SHA, "folds": D.core._folds(PEOPLE), "records": rows}
    protocol = {"schema": "neural009_typed_svg_protocol_v1", "lookback_ticks": 2,
                "width_px": 301, "channel_height_px": 101, "max_svg_bytes": 4096,
                "max_total_svg_bytes_per_record": 16384, "max_actions_per_record": ticks + 30,
                "max_views_per_tick": 3, "max_window_samples": rate,
                "max_window_values": rate, "scales_uv": {r["recording_id"]:
                    [{"index": 0, "minimum": -2000, "maximum": 2000}] for r in rows}}
    limits = {"max_record_ticks": ticks, "max_total_ticks": 686 * ticks,
              "max_prediction_segments": 686 * ticks}
    return support, protocol, limits


def cohort(data=None):
    support, protocol, limits = data or fixture()
    return P.Cohort(support, POLICY, protocol, expected_support_sha256=P.digest(support),
                    expected_policy_sha256=P.digest(POLICY), expected_protocol_sha256=P.digest(protocol),
                    recipe_sha256="a" * 64, limits=limits, secret=SECRET, dependencies=D)


def fake_reader(row, *, values=None, close_error=False):
    # Pure generated operand facade. No EDF source-authentication claim.
    class Generated(D.reader.RecordWindow):
        def __init__(self):
            self.sample_rate_hz = row["native_sample_rate_hz"]
            self.sample_count = row["native_sample_count"]
            self.observed_ticks = row["observed_ticks"]
            self.calls = []
            self.closed = False

        def window(self, start, stop, *, available_through_tick):
            self.calls.append((start, stop, available_through_tick))
            assert stop <= min(self.sample_count, available_through_tick * self.sample_rate_hz // 10 + 1)
            samples = values or list(range(self.sample_count))
            return {"schema": "neural009_calibrated_causal_window_v1", "sample_start": start,
                    "sample_stop": stop, "sample_rate_hz": self.sample_rate_hz,
                    "available_through_tick": available_through_tick,
                    "channels": [{"channel_index": c["index"], "label": c["label"],
                                  "unit": "uV", "samples": samples[start:stop]}
                                 for c in row["predictor_channels"]]}

        def close(self):
            self.closed = True
            if close_error:
                raise OSError("/PRIVATE/clinical/source.edf")
    return Generated()


def open_fake(c, case=None, **kwargs):
    case = case or c.case_ids()[0]
    r = fake_reader(c._records[c._join[case]], **kwargs)
    c._start(case, lambda: r)
    return case, r


def answer(c, case, tick, value):
    return c.dispatch({"action": "answer", "case_id": case, "tick": tick, "probability": value})


def view(c, case, end=1, lookback=1):
    return c.dispatch({"action": "view", "case_id": case, "end_tick": end, "lookback_ticks": lookback})


def field(value, width):
    encoded = str(value).encode("ascii")
    assert len(encoded) <= width
    return encoded.ljust(width, b" ")


def edf(reserved=""):
    # One genuine-format generated record: six30Hz samples over0.2seconds.
    fixed = (b"0       " + field("PRIVATE PATIENT", 80) + field("PRIVATE SOURCE", 80) +
             b"01.01.0000.00.00" + field(512, 8) + field(reserved, 44) +
             field(1, 8) + field("0.2", 8) + field(1, 4))
    fields = [("A-B", 16), ("", 80), ("uV", 8), (-32768, 8), (32767, 8),
              (-32768, 8), (32767, 8), ("", 80), (6, 8), ("", 32)]
    header = fixed + b"".join(field(v, w) for v, w in fields)
    body = header + struct.pack("<6h", 0, 1, 2, 3, 999, 1000)
    name = sorted(INDEX)[0]
    row = {"recording_id": name, "biological_person": INDEX[name]["biological_person"],
           "edf_sha256": hashlib.sha256(body).hexdigest(), "edf_header_sha256": hashlib.sha256(header).hexdigest(),
           "native_sample_rate_hz": 30, "native_sample_count": 6, "observed_ticks": 2,
           "channels": [{"label": "A-B", "role": "eeg"}], "predictor_channels": [0]}
    return body, row


class PresentationTests(unittest.TestCase):
    def test_actual_reader_first_endpoint_and_future_signal_absence(self):
        c = cohort(); body, row = edf()
        case = next(k for k, name in c._join.items() if name == row["recording_id"])
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            p = Path(temporary) / "private-generated.edf"; write(p, body)
            reader = D.reader.RecordWindow(p, row, max_edf_bytes=len(body), max_window_samples=30,
                                           max_output_values=30)
            c._start(case, lambda: reader)
            result = view(c, case)
            self.assertEqual(result["status"], "view")
            poly = ET.fromstring(result["svg"]).find(".//{http://www.w3.org/2000/svg}polyline")
            self.assertEqual(len(poly.attrib["points"].split()), 4)  # j=3 is exactly0.1s.
            self.assertNotIn("999", result["svg"])
            answer(c, case, 1, .2)
            result = view(c, case, 2, 2)
            poly = ET.fromstring(result["svg"]).find(".//{http://www.w3.org/2000/svg}polyline")
            self.assertEqual(len(poly.attrib["points"].split()), 6)
            answer(c, case, 2, .2)
            self.assertTrue(reader._closed)

    def test_future_and_beyond_declared_history_refused_before_read(self):
        c = cohort(fixture(ticks=5)); case, reader = open_fake(c)
        self.assertEqual(view(c, case, 2)["status"], "refused")
        self.assertEqual(reader.calls, [])
        for tick in (1, 2, 3):answer(c, case, tick, 0)
        self.assertEqual(view(c, case, 1)["status"], "refused")
        self.assertEqual(reader.calls, [])
        self.assertEqual(view(c, case, 4, 2)["status"], "view")
        self.assertEqual(reader.calls, [(6, 13, 4)])
        c._fail("generated_cleanup")

    def test_svg_escapes_labels_and_contains_no_external_elements(self):
        c = cohort(fixture(label='<x&"\'>')); case, reader = open_fake(c)
        result = view(c, case)
        root = ET.fromstring(result["svg"])
        self.assertEqual({e.tag.split("}")[-1] for e in root.iter()}, {"svg", "title", "g", "polyline"})
        self.assertIn('&lt;x&amp;&quot;&#x27;&gt;', result["svg"])
        self.assertNotIn("samples", result)
        c._fail("generated_cleanup")

    def test_opaque_replies_exclude_source_person_hashes_and_targets(self):
        c = cohort(); case, _ = open_fake(c)
        public = json.dumps([list(c.case_ids()), view(c, case), answer(c, case, 1, .1)])
        self.assertEqual(len(set(c.case_ids())), 686)
        self.assertNotEqual([c._join[k] for k in c.case_ids()], sorted(INDEX))
        for name, row in INDEX.items():
            self.assertNotIn(name, public)
            self.assertNotIn(row["publisher_sha256"], public)
        self.assertNotIn("chb01", public)
        self.assertNotIn(INDEX_SHA, public)
        self.assertNotIn("reference_intervals", public)
        c._fail("generated_cleanup")

    def test_closed_requests_and_bad_probabilities_never_advance_tick(self):
        c = cohort(); case, _ = open_fake(c)
        for value in (True, float("nan"), float("inf"), -1, 2, "0.1"):
            self.assertEqual(answer(c, case, 1, value)["status"], "refused")
        for request in ({"action": "read", "case_id": case, "path": "/private"},
                        {"action": "answer", "case_id": case, "tick": True, "probability": .5},
                        {"action": "answer", "case_id": case, "tick": 1, "probability": .5, "labels": []}):
            self.assertEqual(c.dispatch(request)["status"], "refused")
        self.assertEqual(c._state[c._join[case]]["ticks"], 0)
        self.assertEqual(answer(c, case, 1, .5)["next_endpoint_tick"], 2)
        self.assertEqual(answer(c, case, 1, .2)["status"], "refused")
        answer(c, case, 2, .5)
        matched = next(r for r in c.finish()["records"] if r["recording_id"] == c._join[case])
        self.assertEqual(matched["runs"], [[0, 2, .5]])

    def test_missing_and_failed_records_never_become_partial_candidates(self):
        c = cohort(); first, _ = open_fake(c)
        answer(c, first, 1, 0); answer(c, first, 2, 0)
        second = c.case_ids()[1]
        def fail():raise OSError("/PRIVATE/CHB/answer-file.seizures")
        result = c._start(second, fail)
        self.assertEqual(result, {"case_id": second, "status": "failed", "reason": "source_refused"})
        self.assertIsNone(c.finish()["candidate"])
        self.assertEqual(len(c.finish()["records"]), 686)
        with self.assertRaises(P.Refused):c._start(second, fail)

    def test_edf_plus_failure_retained_and_source_case_binding_not_bypassed(self):
        c = cohort(); body, row = edf("EDF+C")
        case = next(k for k, name in c._join.items() if name == row["recording_id"])
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            p = Path(temporary) / "PRIVATE.edf"; write(p, body)
            result = c._start(case, lambda: D.reader.RecordWindow(p, row, max_edf_bytes=len(body),
                              max_window_samples=30, max_output_values=30))
            self.assertEqual(result["reason"], "source_refused")
            self.assertIsNone(c.finish()["candidate"])
        other = cohort()
        with patch.object(D.reader, "RecordWindow") as opened:
            result = other.start_edf(case, "/must/not/open", row, max_edf_bytes=1024)
            self.assertEqual(result["reason"], "source_refused")
            opened.assert_not_called()  # Generated hash cannot impersonate original.

    def test_complete686_probabilities_reach_unchanged_event_scorer(self):
        c = cohort()
        for case in c.case_ids():
            open_fake(c, case)
            answer(c, case, 1, .5); answer(c, case, 2, .1)
        result = c.finish(); candidate = result["candidate"]
        self.assertEqual(len(candidate["records"]), 686)
        self.assertEqual({r["biological_person"] for r in candidate["records"]}, set(PEOPLE))
        self.assertTrue(all(r["predicted_intervals"] == [[0, 1]] for r in candidate["records"]))
        aliases = [r for r in candidate["records"] if r["recording_id"].startswith("chb21/")]
        self.assertTrue(aliases and all(r["fold_id"] == "chb01" for r in aliases))
        admission = {"schema": "neural009_admission_v1", "task_id": "NEURAL-009",
                     "source_index_sha256": INDEX_SHA, "public_development_only": True,
                     "normalization_recipe_sha256": "b"*64, "clock_review_sha256": "c"*64,
                     "rights_review_sha256": "d"*64, "folds": D.core._folds(PEOPLE), "records": []}
        for row in c._support["records"]:
            name = row["recording_id"]
            admission["records"].append({k: row[k] for k in ("recording_id", "biological_person",
                "native_sample_rate_hz", "native_sample_count", "observed_ticks")} | {
                "edf_sha256": INDEX[name]["publisher_sha256"], "edf_header_sha256": "e"*64,
                "annotation_sha256": "f"*64, "annotation_status": "explicit_events",
                "channels": [{"label": "A-B", "role": "eeg"}], "predictor_channels": [0],
                "reference_intervals": [[0, 1]]})
        scored = D.core.evaluate(admission, POLICY, candidate,
                                expected_policy_sha256=P.digest(POLICY), limits=c._limits)
        self.assertEqual(scored["counts"]["recordings"], 686)
        self.assertEqual(scored["counts"]["biological_people"], 23)
        self.assertEqual(scored["primary"]["value"], 1)
        self.assertFalse(scored["verification"]["scientific_qualification"])

    def test_source_errors_scale_and_byte_limits_keep_record_failure(self):
        c = cohort(); case, _ = open_fake(c, values=[9000]*6)
        self.assertEqual(view(c, case)["reason"], "presentation_refused")
        self.assertIsNone(c.finish()["candidate"])
        data = fixture(); data[1]["max_svg_bytes"] = 1
        c = cohort(data); case, _ = open_fake(c)
        self.assertEqual(view(c, case)["reason"], "presentation_refused")
        self.assertEqual(c._state[c._join[case]]["status"], "failed")

    def test_cleanup_failure_and_action_budget_cannot_look_complete(self):
        c = cohort(); case, _ = open_fake(c, close_error=True)
        answer(c, case, 1, .1)
        self.assertEqual(answer(c, case, 2, .1)["status"], "failed")
        self.assertIsNone(c.finish()["candidate"])
        data = fixture(); data[1]["max_actions_per_record"] = 2
        c = cohort(data); case, _ = open_fake(c)
        view(c, case); answer(c, case, 1, .1)
        self.assertEqual(answer(c, case, 2, .1)["reason"], "action_budget_exhausted")

    def test_interrupted_final_cleanup_remains_incomplete(self):
        c = cohort(); case, reader = open_fake(c)
        def interrupted():raise KeyboardInterrupt()
        reader.close = interrupted
        answer(c, case, 1, .1)
        with self.assertRaises(KeyboardInterrupt):answer(c, case, 2, .1)
        self.assertIsNone(c.finish()["candidate"])
        self.assertEqual(c._state[c._join[case]]["status"], "failed")
        self.assertEqual(c._state[c._join[case]]["cleanup_failures"], 1)
        self.assertIs(c._reader, reader)
        self.assertEqual(answer(c, case, 3, .1)["reason"], "case_failed")

    def test_bounded_request_refusal_never_serializes_nested_or_excess_input(self):
        c = cohort(); case, _ = open_fake(c)
        nested = []
        for _ in range(5000):nested = [nested]
        request = {"action": "answer", "case_id": case, "tick": 1, "probability": nested}
        excess = {"action": "answer", "case_id": case, "tick": 1, "probability": .2,
                  "unknown": "x" * 131072}
        with patch.object(P.json, "dumps", side_effect=AssertionError("participant serialization")):
            self.assertEqual(c.dispatch(request)["status"], "refused")
            self.assertEqual(c.dispatch(excess)["status"], "refused")
            self.assertEqual(c._state[c._join[case]]["ticks"], 0)
            self.assertEqual(answer(c, case, 1, .5)["next_endpoint_tick"], 2)
        c.abort_active()

    def test_owner_abort_preserves_failure_and_retries_retained_cleanup(self):
        c = cohort(); case, reader = open_fake(c)
        original = reader.close
        calls = []
        def close_once_fails():
            calls.append(True)
            if len(calls) == 1:raise OSError("/private/answer-bearing-path")
            original()
        reader.close = close_once_fails
        answer(c, case, 1, .1)
        result = c.abort_active()
        self.assertEqual(result, {"case_id": case, "status": "failed",
                                 "reason": "operator_aborted", "cleanup_complete": False})
        self.assertIs(c._reader, reader)
        with self.assertRaises(P.Refused):open_fake(c, c.case_ids()[1])
        self.assertEqual(answer(c, case, 2, .1)["reason"], "case_failed")
        self.assertTrue(c.abort_active()["cleanup_complete"])
        self.assertTrue(reader.closed)
        self.assertIsNone(c._reader)
        self.assertIsNone(c.finish()["candidate"])
        retained = c._state[c._join[case]]
        self.assertEqual((retained["status"], retained["failure"], retained["cleanup_failures"]),
                         ("failed", "operator_aborted", 1))

    def test_every_selected_duplicate_label_channel_keeps_its_band(self):
        data = fixture()
        for r in data[0]["records"]:
            r["predictor_channels"] = [{"index": 0, "label": "A-B"}, {"index": 2, "label": "A-B"}]
            data[1]["scales_uv"][r["recording_id"]] = [
                {"index": i, "minimum": -2000, "maximum": 2000} for i in (0, 2)]
        data[1]["max_window_values"] = 60
        c = cohort(data); case, _ = open_fake(c)
        root = ET.fromstring(view(c, case)["svg"])
        polylines = root.findall(".//{http://www.w3.org/2000/svg}polyline")
        self.assertEqual(len(polylines), 2)
        self.assertTrue(all(len(p.attrib["points"].split()) == 4 for p in polylines))
        self.assertNotEqual(polylines[0].attrib["points"], polylines[1].attrib["points"])
        c._fail("generated_cleanup")

    def test_mutable_inputs_are_detached_and_commitments_fail_closed(self):
        data = fixture(); c = cohort(data); case = c.case_ids()[0]
        data[0]["records"][0]["predictor_channels"][0]["label"] = "PRIVATE TARGET"
        data[1]["scales_uv"].clear()
        open_fake(c, case)
        self.assertEqual(view(c, case)["status"], "view")
        c._fail("generated_cleanup")
        support, protocol, limits = fixture()
        with self.assertRaises(P.Refused):
            P.Cohort(support, POLICY, protocol, expected_support_sha256="0"*64,
                expected_policy_sha256=P.digest(POLICY), expected_protocol_sha256=P.digest(protocol),
                recipe_sha256="a"*64, limits=limits, secret=SECRET, dependencies=D)

    def test_changed_dependency_refused_before_execution(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            p = Path(temporary) / "seizure-events-v1" / "core.py"; p.parent.mkdir()
            write(p, b"raise AssertionError('must not execute')\n")
            with self.assertRaisesRegex(P.Refused, "dependency_changed"):P.Dependencies(Path(temporary))


if __name__ == "__main__":
    unittest.main(argv=[__file__] + remaining, verbosity=2)
