"""Generated engineering controls. These fixtures contain no clinical data."""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import source_intake as intake


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clock(index):
    ms = index * 4
    minute, ms = divmod(ms, 60000)
    second, milli = divmod(ms, 1000)
    return f"2022-01-01 00:{minute:02d}:{second:02d}.{milli:03d}"


def csv_bytes(headers, rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue().encode()


class Controls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="generated-control-", dir=Path(__file__).parent)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def native(self, name="native.csv", *, clinical=False, bad_future=False, omit=None, duplicate=None):
        path = self.root / name
        rows = []
        for index in range(7502):
            if index == omit:
                continue
            # Irregular sparsity and phase changes are deliberate: selecting
            # every other row would destroy real values in this generated test.
            left = index / 100 if index % 3 != 1 else ""
            right = -index / 100 if index % 5 != 2 else ""
            if bad_future and index >= 7500:
                left, right = "NaN", "malformed_future"
            event, label, soc = ("changed_private_annotation", "4", "1") if clinical else ("", "", "")
            if index == 7500 and not clinical:
                event, label, soc = "UNVERIFIED_EVENT_LITERAL", "3", "0"
            rows.append([clock(index if index != duplicate else index - 1), left, right, event, label, soc, "never_public"])
        path.write_bytes(csv_bytes(["Time", "Intellivue/EEG_1-uV", "Intellivue/EEG_2-uV", "EVENT", "MOAAS", "SOC", "Propofol"], rows))
        return path

    def metadata(self, *, bad_static=False):
        fields = ["", "MOAAS_sum", "SOC_trans", "MOAAS1", "MOAAS2", "MOAAS3", "MOAAS4", "MOAAS5"]
        rows = []
        for index in range(171):
            total = 43 if index < 163 else 42
            rows.append([str(index + 1), total, 7 if index < 106 else 6, total, "", "", "", ""])
        metadata, static = self.root / "metadata.zip", self.root / "static.zip"
        with zipfile.ZipFile(metadata, "w") as archive:
            archive.writestr(intake.METADATA_MEMBER, csv_bytes(fields, rows))
        ids = list(range(1, 172))
        if bad_static:
            ids[-1] = 1
        with zipfile.ZipFile(static, "w") as archive:
            archive.writestr(intake.STATIC_MEMBER, csv_bytes(["ID", "private_covariate"], [[i, "unused"] for i in ids]))
        return metadata, static

    def test_complete_metadata_preserves_version_discrepancy_and_blanks(self):
        metadata, static = self.metadata()
        report = intake.reconcile_metadata(metadata, static, digest(metadata), digest(static))
        self.assertEqual(report["metadata_aggregate_counts"], {"recordings": 171, "assessments": 7345, "transitions": 1132})
        self.assertEqual(report["count_discrepancies"]["assessments"]["difference"], 17)
        self.assertEqual(report["count_discrepancies"]["transitions"]["difference"], 3)
        self.assertIsNone(report["recordings"][0]["category_counts"]["2"])
        self.assertFalse(report["biological_person_join_verified"])
        self.assertFalse(report["original_EVENT_census_complete"])
        self.assertEqual(report["canonical_admission"], "held")
        self.assertNotIn("private_covariate", json.dumps(report))

    def test_duplicate_static_identity_refused(self):
        metadata, static = self.metadata(bad_static=True)
        with self.assertRaisesRegex(intake.Refusal, "duplicate static"):
            intake.reconcile_metadata(metadata, static, digest(metadata), digest(static))

    def test_exact_sparse_half_open_window(self):
        path = self.native()
        packet = intake.marker_window(path, digest(path), clock(7500), "opaque_case")
        self.assertEqual(packet["relative_time_ms"], list(range(-30000, 0, 4)))
        self.assertEqual(len(packet["values"]), 7500)
        self.assertEqual(packet["values"][0], [0.0, 0.0])
        self.assertEqual(packet["values"][7499], [74.99, -74.99])
        self.assertIsNone(packet["values"][1][0])
        self.assertEqual(packet["values"][3][0], .03)
        self.assertEqual(packet["observed"][2], [True, False])
        self.assertFalse(packet["assessment_onset_verified"])

    def test_clinical_columns_do_not_change_participant_packet(self):
        original = self.native("original.csv")
        mutated = self.native("mutated.csv", clinical=True)
        a = intake.marker_window(original, digest(original), clock(7500), "opaque_case")
        b = intake.marker_window(mutated, digest(mutated), clock(7500), "opaque_case")
        self.assertEqual(a, b)
        for forbidden in ("MOAAS", "SOC", "Propofol", "source_sha256", "recording_id", "person_id", "marker_time_ms", "artifact"):
            self.assertNotIn(forbidden, json.dumps(a))

    def test_cutoff_and_future_signal_values_do_not_change_packet(self):
        original = self.native("original.csv")
        future = self.native("future.csv", bad_future=True)
        self.assertEqual(intake.marker_window(original, digest(original), clock(7500), "case"),
                         intake.marker_window(future, digest(future), clock(7500), "case"))

    def test_adopted_candidate_condition_binds_original_annotation_row(self):
        path = self.native()
        packet = intake.candidate_window(path, digest(path), 7500, "opaque_case")
        self.assertEqual(packet["source_condition"], "native_marker_relative_30s_v1")
        self.assertEqual(packet["cutoff_role"], "original_coded_MOAAS_candidate_marker")
        self.assertTrue(packet["source_event_marker_verified"])
        self.assertFalse(packet["original_EVENT_assessment_identity_verified"])
        self.assertFalse(packet["assessment_onset_verified"])
        self.assertTrue(packet["assessment_challenge_activity_may_be_present"])
        with self.assertRaisesRegex(intake.Refusal, "requires original EVENT"):
            intake.candidate_window(path, digest(path), 7499, "opaque_case")

    def test_candidate_packet_preserves_clinical_and_future_noninterference(self):
        original = self.native("original.csv")
        changed = self.native("changed.csv", clinical=True, bad_future=True)
        a = intake.candidate_window(original, digest(original), 7500, "case")
        b = intake.candidate_window(changed, digest(changed), 7500, "case")
        self.assertEqual(a, b)
        self.assertNotIn("original_fields", a)
        self.assertNotIn("category", a)
        self.assertNotIn("source_row", a)

    def test_generated_metadata_hashes_do_not_authenticate_release(self):
        metadata, static = self.metadata()
        report = intake.reconcile_metadata(metadata, static, digest(metadata), digest(static))
        self.assertFalse(report["source_release_authenticated"])
        self.assertEqual(report["source_release"], "unverified_fixture_or_operator_bytes")

    def test_incomplete_and_off_grid_windows_refused(self):
        path = self.native()
        with self.assertRaisesRegex(intake.Refusal, "incomplete"):
            intake.marker_window(path, digest(path), clock(7499), "case")
        with self.assertRaisesRegex(intake.Refusal, "grid timestamp"):
            intake.marker_window(path, digest(path), "2022-01-01 00:00:30.001", "case")

    def test_missing_and_duplicate_clock_rows_refused(self):
        for kwargs in ({"omit": 125}, {"duplicate": 125}):
            path = self.native(**kwargs)
            with self.assertRaisesRegex(intake.Refusal, "contiguous 4ms"):
                intake.scan_recording(path, digest(path), "3")

    def test_original_annotations_remain_private_candidates(self):
        path = self.native()
        report = intake.scan_recording(path, digest(path), "3")
        self.assertEqual(report["source_row_counts"]["nonempty_MOAAS_rows"], 1)
        self.assertEqual(report["source_row_counts"]["nonempty_SOC_rows"], 1)
        item = report["protected_annotation_ledger"][0]
        self.assertEqual(item["source_row"], 7500)
        self.assertEqual(item["category"], 3)
        self.assertEqual(item["window_status"], "complete")
        self.assertEqual(item["timing_status"], "unresolved")
        self.assertFalse(report["original_EVENT_census_complete"])

    def test_released_labels_no_guessing_or_zero_imputation(self):
        self.assertEqual(intake.label_disposition(""), {"category": None, "label_status": "missing"})
        for raw in ("0", "6", "1.0", "2|3", "unknown"):
            self.assertEqual(intake.label_disposition(raw), {"category": None, "label_status": "ambiguous"})
        for category in range(1, 6):
            self.assertEqual(intake.label_disposition(str(category))["category"], category)

    def test_source_hardware_range_not_sentinel_or_clipping(self):
        self.assertEqual(intake.sample("187.5"), 187.5)
        self.assertEqual(intake.sample("-187.5"), -187.5)
        self.assertIsNone(intake.sample(""))
        self.assertEqual(intake.sample("0"), 0.0)
        for value in ("300", "-300", "187.5001", "NaN", "inf"):
            with self.assertRaises(intake.Refusal):
                intake.sample(value)

    def test_person_join_complete_grouping_does_not_authenticate_identity(self):
        ids = {str(index) for index in range(1, 172)}
        rows = [{"recording_id": rid, "person_id": "person_a" if int(rid) % 2 else "person_b"} for rid in sorted(ids, key=int)]
        join = {"schema": "dosei_recording_person_crosswalk_v1", "source_sha256": "a" * 64, "rows": rows}
        report = intake.validate_person_join(join, ids)
        self.assertEqual(len(report["person_groups"]), 2)
        self.assertFalse(report["biological_person_join_verified"])
        bad = copy.deepcopy(join)
        bad["rows"][-1]["recording_id"] = "1"
        with self.assertRaises(intake.Refusal):
            intake.validate_person_join(bad, ids)

    def test_cohort_requires_all_recordings_and_does_not_admit_equal_counts(self):
        metadata, static = self.metadata()
        report = intake.reconcile_metadata(metadata, static, digest(metadata), digest(static))
        records = [{"recording_id": row["recording_id"], "source_row_counts": {
            "nonempty_MOAAS_rows": row["metadata_assessments"], "nonempty_SOC_rows": row["metadata_transitions"]}}
            for row in report["recordings"]]
        complete = intake.cohort_report(report, records)
        self.assertEqual(complete["observed_nonempty_coded_rows"]["MOAAS"], 7345)
        self.assertFalse(complete["original_EVENT_census_complete"])
        with self.assertRaises(intake.Refusal):
            intake.cohort_report(report, records[:-1])
        with self.assertRaisesRegex(intake.Refusal, "projection held"):
            intake.project_existing_scorer(complete)

    def test_artifact_intervals_are_private_timestamp_audit_only(self):
        archive = self.root / "artifacts.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("artifacts/artifacts/10-003_artifacts.csv", csv_bytes(
                ["begin_idx", "end_idx", "is_artifact", "reason"],
                [["2022-01-01 00:00:28", "2022-01-01 00:00:30", "True", "3"],
                 ["2022-01-01 00:00:30", "2022-01-01 00:00:32", "False", "0"]]))
        intervals = intake.artifact_intervals(archive, "3", digest(archive))
        audit = intake.artifact_window_audit(intervals, clock(7500))
        self.assertEqual(len(audit["conservative_closed_interval_overlaps"]), 2)
        self.assertFalse(audit["participant_input_allowed"])
        self.assertEqual(audit["artifact_status"], "unresolved")

    def test_input_hash_symlink_and_unsafe_zip_refusals(self):
        path = self.root / "small.csv"
        path.write_text("small")
        with self.assertRaisesRegex(intake.Refusal, "SHA256 mismatch"):
            intake.sha256_file(path, "0" * 64)
        link = self.root / "link"
        link.symlink_to(path)
        with self.assertRaisesRegex(intake.Refusal, "non-symlink"):
            intake.sha256_file(link, digest(path))
        archive = self.root / "unsafe.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("../bad", "x")
        with self.assertRaisesRegex(intake.Refusal, "unsafe ZIP"):
            intake.archive_member(archive, digest(archive), "../bad")

    def test_fresh_private_output(self):
        path = self.root / "report.json"
        intake.write_fresh_json(path, {"canonical_admission": "held"})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        original = path.read_bytes()
        with self.assertRaises(FileExistsError):
            intake.write_fresh_json(path, {"bad": True})
        self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
