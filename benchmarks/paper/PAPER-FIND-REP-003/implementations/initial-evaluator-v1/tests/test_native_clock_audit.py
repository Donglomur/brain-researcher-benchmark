"""Generated software controls for native-clock admission; no study data."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("native_clock_audit", Path(__file__).parents[1] / "native_clock_audit.py")
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)

SESSIONS = {("cfaVG1", "20210304_153342"): 2, ("cfaVG4", "20210601_152047"): 2}


def fixture():
    rows = []
    for (mouse, session), n in SESSIONS.items():
        for trial in range(1, n + 1):
            row = dict.fromkeys(A.FIELDS, 0)
            row.update(animalID=mouse, date=session, trialNumber=trial, success=1,
                       waterTime=1000.0, liftTimeC=1250.0, grabTimeC=2000.0,
                       liftRT=250.0, grabRT=1000.0)
            rows.append(row)
    return rows


class NativeClockControls(unittest.TestCase):
    def test_nonzero_origin_is_preserved_and_interpretation_stays_unqualified(self):
        rows = fixture()
        original = copy.deepcopy(rows)
        result = A.audit_records(rows, SESSIONS)
        self.assertEqual(rows, original)
        self.assertEqual(result["record_count"], 4)
        self.assertEqual(result["clock_identities"]["grabTimeC"]["nonzero_water_time_rows"], 4)
        self.assertEqual(result["source_plot_transform"], "grabTimeC / 1000")
        self.assertFalse(result["cue_clock_interpretation_validated"])
        self.assertFalse(result["endpoint_targets_exported"])
        self.assertNotIn("opto_trials", result)
        self.assertNotIn("histograms", result)

    def test_missing_events_retained_with_failed_trial(self):
        rows = fixture()
        rows[0].update(success=0, liftTimeC=float("nan"), grabTimeC=float("nan"),
                       liftRT=float("nan"), grabRT=float("nan"), waterTime=float("nan"))
        result = A.audit_records(rows, SESSIONS)
        self.assertEqual(result["record_count"], 4)
        self.assertEqual(result["missing_native_event_counts"]["grabTimeC"], 1)
        self.assertEqual(result["clock_identities"]["grabTimeC"]["finite_identity_rows"], 3)

    def test_identity_hash_ignores_order_and_retains_full_session_timestamp(self):
        rows = fixture()
        result = A.audit_records(rows, SESSIONS)
        self.assertEqual(result["identity_sha256"], A.audit_records(rows[::-1], SESSIONS)["identity_sha256"])
        rows[0]["date"] = "20210304"
        with self.assertRaisesRegex(A.AuditError, "timestamp"):
            A.audit_records(rows, SESSIONS)

    def test_subset_duplicate_and_noncontiguous_ids_rejected(self):
        for mutate, message in (
            (lambda r: r.pop(), "population"),
            (lambda r: r.__setitem__(1, r[0]), "duplicate"),
            (lambda r: r[0].update(trialNumber=99), "trial-number"),
        ):
            rows = fixture()
            mutate(rows)
            with self.subTest(message=message), self.assertRaisesRegex(A.AuditError, message):
                A.audit_records(rows, SESSIONS)

    def test_clock_reanchoring_and_rt_corruption_rejected(self):
        for change in ({"grabTimeC": 1000.0}, {"grabRT": 1001.0}, {"waterTime": 0.0}):
            rows = fixture()
            rows[0].update(change)
            with self.subTest(change=change), self.assertRaisesRegex(A.AuditError, "does not equal RT"):
                A.audit_records(rows, SESSIONS)

    def test_invalid_fields_fail_even_for_failed_trials(self):
        for change in ({"grabTimeC": float("inf")}, {"grabTimeC": "2000"},
                       {"grabRT": float("nan")}, {"waterTime": float("nan")},
                       {"optoProblem": 2}, {"trialNumber": True}):
            rows = fixture()
            rows[0].update(success=0, **change)
            with self.subTest(change=change), self.assertRaises(A.AuditError):
                A.audit_records(rows, SESSIONS)

    def test_unpinned_mat_rejected_before_parser(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "optoData.mat"
            path.write_bytes(b"not native")
            with self.assertRaisesRegex(A.AuditError, "byte count"):
                A.audit_native(path)
            path.write_bytes(b"x" * A.DATA_BYTES)
            with self.assertRaisesRegex(A.AuditError, "SHA256"):
                A.audit_native(path)


if __name__ == "__main__":
    unittest.main()
