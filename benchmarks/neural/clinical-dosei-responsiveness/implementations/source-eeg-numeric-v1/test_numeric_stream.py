"""Generated streaming/provenance controls; no original source files accessed."""
import copy
import csv
import hashlib
import io
import math
import struct
import unittest
import zlib

from numeric_stream import ANNOTATIONS, CHANNELS, ProjectionRefusal, exact_time, project_member


def fixture():
    header = ["Time", *CHANNELS, *ANNOTATIONS]
    rows = [
        ["2026-01-01 00:00:00.000", "", "1.25", "MOAAS1", "1.0", "", "", "", "", ""],
        ["2026-01-01 00:00:00.000", "300", "-0", "PROP", "", "", "", "20.0", "", ""],
    ]
    text = io.StringIO(newline="")
    writer = csv.writer(text, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    raw = text.getvalue().encode()
    expected = {"expanded_bytes": len(raw), "source_rows": len(rows),
                "header_sha256": hashlib.sha256(raw.splitlines(keepends=True)[0]).hexdigest(),
                "member_sha256": hashlib.sha256(raw).hexdigest(),
                "crc32": f"{zlib.crc32(raw) & 0xffffffff:08x}",
                "annotation_rows": 2, "clock_issue_counts": {"duplicate_timestamp": 1}}
    ledger = [{"source_row": index, "source_physical_line_end": index + 2,
               "raw_time": fields[0], "recognized_time_ms": exact_time(fields[0]),
               "timestamp_issues": [] if index == 0 else ["duplicate_timestamp"],
               "original_fields": dict(zip(ANNOTATIONS, fields[3:]))} for index, fields in enumerate(rows)]
    return raw, expected, ledger


def run(raw, expected, ledger, sinks=None):
    sinks = sinks or {key: io.BytesIO() for key in ("time", "eeg", "quality")}
    report = project_member(io.BytesIO(raw), expected=expected, annotation_rows=iter(ledger), sinks=sinks, block_rows=1)
    return report, sinks


class NumericStreamTests(unittest.TestCase):
    def test_two_channels_sparse_values_and_duplicates_preserved(self):
        raw, expected, ledger = fixture()
        report, sinks = run(raw, expected, ledger)
        self.assertEqual(report["source_rows"], 2)
        self.assertEqual(report["annotation_rows_joined"], 2)
        self.assertEqual(report["clock_issue_counts"], {"duplicate_timestamp": 1})
        self.assertEqual([len(sinks[key].getvalue()) for key in ("time", "eeg", "quality")], [16, 32, 4])
        self.assertEqual(struct.unpack("<qq", sinks["time"].getvalue()), (exact_time(ledger[0]["raw_time"]),) * 2)
        values = struct.unpack("<dddd", sinks["eeg"].getvalue())
        self.assertTrue(math.isnan(values[0]))
        self.assertEqual(values[1:3], (1.25, 300.0))
        self.assertEqual(math.copysign(1, values[3]), -1)
        self.assertEqual(sinks["quality"].getvalue(), bytes((1, 0, 8, 0)))
        for key, sink in sinks.items():
            self.assertEqual(report["outputs"][key]["sha256"], hashlib.sha256(sink.getvalue()).hexdigest())
        self.assertFalse(report["canonical_scoring_admitted"])

    def test_complete_source_hash_and_crc_are_required(self):
        raw, expected, ledger = fixture()
        for key, wrong in (("member_sha256", "0" * 64), ("crc32", "0" * 8), ("header_sha256", "0" * 64)):
            changed = dict(expected, **{key: wrong})
            with self.assertRaises(ProjectionRefusal):
                run(raw, changed, ledger)

    def test_ledger_raw_field_physical_position_and_time_must_match(self):
        raw, expected, ledger = fixture()
        for key, value in (("source_row", 5), ("source_physical_line_end", 4),
                           ("recognized_time_ms", 1), ("timestamp_issues", [])):
            changed = copy.deepcopy(ledger)
            changed[1][key] = value
            with self.assertRaises(ProjectionRefusal):
                run(raw, expected, changed)
        changed = copy.deepcopy(ledger)
        changed[1]["original_fields"]["Propofol"] = "10.0"
        with self.assertRaises(ProjectionRefusal):
            run(raw, expected, changed)

    def test_missing_extra_and_reordered_ledger_rows_refuse(self):
        raw, expected, ledger = fixture()
        for changed in (ledger[:1], ledger + ledger[-1:], list(reversed(ledger))):
            with self.assertRaises(ProjectionRefusal):
                run(raw, expected, changed)

    def test_clock_census_and_source_row_count_must_be_complete(self):
        raw, expected, ledger = fixture()
        with self.assertRaises(ProjectionRefusal):
            run(raw, dict(expected, clock_issue_counts={}), ledger)
        for count in (1, 3):
            with self.assertRaises(ProjectionRefusal):
                run(raw, dict(expected, source_rows=count), ledger)

    def test_short_write_is_incomplete_and_retains_written_prefix(self):
        class ShortSink(io.BytesIO):
            def write(self, value):
                return super().write(value[:-1])
        raw, expected, ledger = fixture()
        sinks = {key: io.BytesIO() for key in ("time", "eeg", "quality")}
        sinks["eeg"] = ShortSink()
        with self.assertRaises(ProjectionRefusal):
            run(raw, expected, ledger, sinks)
        self.assertEqual(len(sinks["time"].getvalue()), 8)
        self.assertEqual(len(sinks["eeg"].getvalue()), 15)
        self.assertEqual(len(sinks["quality"].getvalue()), 0)

    def test_exact_clock_no_timezone_or_syntax_repair(self):
        for raw in ("2026-01-01T00:00:00.000", "2026-01-01 00:00:00", "2026-02-30 00:00:00.000",
                    "2026-01-01 00:00:00.000+00:00", " 2026-01-01 00:00:00.000"):
            with self.assertRaises(ProjectionRefusal):
                exact_time(raw)
        self.assertEqual(exact_time("0001-01-01 00:00:00.000"), 86_400_000)


if __name__ == "__main__":
    unittest.main()
