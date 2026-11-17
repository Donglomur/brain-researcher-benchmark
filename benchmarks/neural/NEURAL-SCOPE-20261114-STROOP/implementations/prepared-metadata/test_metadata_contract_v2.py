"""Invented complete-population controls; no authentic metadata/arrays opened."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).absolute().parent
spec = importlib.util.spec_from_file_location("metadata_contract", HERE / "metadata_contract_v2.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def number(x):
    return {"class": 6, "name": "", "shape": [1, 1], "logical": False, "values": [x]}


def chars(x):
    return {"class": 4, "name": "", "shape": [1, len(x)], "logical": False, "text": x}


def steps(values):
    return {"class": 1, "name": "", "shape": [1, len(values)], "logical": False,
            "cells": [{"class": 1, "name": "", "shape": [1, len(row)], "logical": False,
                       "cells": [chars(s) for s in row]} for row in values]}


def schema(shape):
    return {"class": 6, "storage_type": 9, "shape": shape,
            "stored_bytes": math.prod(shape) * 8}


def fixture():
    rows, reports = [], []
    for session in (1, 2, 3):
        for group in range(55):
            i = len(rows);sid = "invented_%03d" % group
            onsets = {"11": [200], "12": [800], "13": [1400], "101": [1], "102": [2000]}
            row = {"index": i, "session": session, "source_id": sid,
                   "member": "generated/test%d/prep/%s.mat" % (session, sid),
                   "bytes": 200, "crc32": 1234 + i, "matrix_bytes": 256,
                   "compressed_element_bytes": 64, "fields": list(m.inspector.FIELDS),
                   "marker_onsets": onsets}
            rows.append(row)
            metadata = {k: chars("") for k in m.inspector.FIELDS
                        if k not in ("oxyData", "dxyData", "totalData", "vector_onset")}
            metadata.update(T=number(.0390625), nch=number(35), subject=chars(sid),
                            preprocessSet=steps([["NR_segment", "15", "5"]]))
            report = {"schema": "stroop_prepared_schema_clock_inspection_v1", "index": i,
                      "session": session, "saved_subject_join": "exact", "scientific_ready": False,
                      "file_integrity": {"bytes": 200, "crc32": 1234 + i,
                                         "sha256": hashlib.sha256(("invented-only-%d" % i).encode()).hexdigest(),
                                         "maximum_physical_read_bytes": 128, "publisher_SHA256_predeclared": False},
                      "signals": {k: schema([2200, 35]) for k in ("oxyData", "dxyData", "totalData")},
                      "signal_values_decoded": False, "signal_finiteness_verified": False,
                      "metadata_private": metadata,
                      "clock": {"saved_T_seconds": .0390625, "saved_T_source": "nirsdata.T scalar",
                                "explicit_original_time_vector": "absent from observed root field roster",
                                "uniform_time_verified": False, "fitted_or_replaced_clock": False},
                      "preprocessing": m.inspector.preprocessing_evidence(metadata["preprocessSet"], .0390625),
                      "units": {"concentration_pathlength_scale": "unresolved; no explicit root unit field",
                                "geometry_units_not_concentration_units": True},
                      "onsets": {"schema": schema([2200, 1]), "indices_shifted": False,
                                 "nonzero_code_counts": {code: 1 for code in m.CODES},
                                 "direct_marker_comparison": {code: {"expected": 1, "same_index_same_code": 1,
                                                                     "wrong_code_at_expected_index": 0,
                                                                     "expected_indices_outside_sample_axis": 0,
                                                                     "vector_count": 1, "exact": True}
                                                              for code in m.CODES}}}
            reports.append(report)
    contract = {"schema": "stroop165_prospective_prepared_metadata_contract_v1", "rows": rows}
    audit = {"schema": "stroop165_independent_whole_outcome_audit_v1",
             "status": "COMPLETE165_INDEPENDENT_OUTCOME_VERIFIED", "complete165_verified": True,
             "scientific_qualification": False, "complete_originals": 165, "complete_inspection_reports": 165,
             "regenerated_summary": {"schema": "stroop165_complete_prepared_metadata_inspection_v1",
                                     "complete": True, "records": 165, "source_internal_ids": 55, "sessions": 3,
                                     "physical_member_bytes": 33000, "records_with_exact_direct_marker_join": 165,
                                     "distinct_saved_T_values": [.0390625], "signal_arrays_materialized": False,
                                     "clock_fitted": False, "marker_shifted": False, "scientific_ready": False,
                                     "contract_sha256": m.CONTRACT_SHA}}
    return contract, audit, reports


class MetadataContractTests(unittest.TestCase):
    def test_full165_native_support_and_no_promotion(self):
        c, a, r = fixture();o = m.compile_metadata(c, a, iter(r))
        self.assertEqual((o["records"], o["source_internal_ids"], o["condition_onsets_retained"]), (165, 55, 495))
        self.assertEqual(o["condition_onsets_discarded"], 0)
        self.assertEqual(o["recorded_crop_counts"], {"15/5": 165})
        self.assertTrue(all(x["clock_geometry"]["sample_count"] == 640 for x in o["records_private"]))
        self.assertTrue(all(g["sessions"] == [1, 2, 3] for g in o["groups_private"]))
        self.assertFalse(o["scientific_ready"] or o["candidate_packet"] or o["eligibility_assigned"])
        self.assertTrue(all(not g["verified_distinct_biological_person"] for g in o["groups_private"]))

    def test_missing_extra_reordered_and_duplicate_population_refuse(self):
        c, a, r = fixture()
        for wrong in (r[:-1], r + [r[0]], [r[1], r[0], *r[2:]], [r[0], r[0], *r[2:]]):
            with self.assertRaises(ValueError): m.compile_metadata(c, a, wrong)
        c["rows"][55]["source_id"] = "different_group"
        with self.assertRaises(ValueError): m.compile_metadata(c, a, r)

    def test_saved_subject_and_session_mismatch_refuse(self):
        for change in (lambda x: x["metadata_private"]["subject"].update(text="invented_999"),
                       lambda x: x.update(session=2)):
            c, a, r = fixture();change(r[0])
            with self.assertRaises(ValueError): m.compile_metadata(c, a, r)

    def test_consistent_mismatch_retained_but_forged_boolean_refused(self):
        c, a, r = fixture();row = r[0]["onsets"]["direct_marker_comparison"]["11"]
        row.update(same_index_same_code=0, wrong_code_at_expected_index=1, exact=False)
        a["regenerated_summary"]["records_with_exact_direct_marker_join"] = 164
        o = m.compile_metadata(c, a, r)
        self.assertEqual(o["condition_onsets_retained"], 495)
        self.assertIn("internal_marker_mismatch", o["records_private"][0]["all_condition_onset_windows_private"][0]["geometry_flags"])
        row["exact"] = True
        with self.assertRaises(ValueError): m.compile_metadata(c, a, r)

    def test_marker_count_and_summary_arithmetic_refuse(self):
        for mutate in (lambda a, r: r[0]["onsets"]["direct_marker_comparison"]["11"].update(expected=2),
                       lambda a, r: r[0]["onsets"]["direct_marker_comparison"]["11"].update(wrong_code_at_expected_index=1),
                       lambda a, r: a["regenerated_summary"].update(records_with_exact_direct_marker_join=164),
                       lambda a, r: a["regenerated_summary"].update(physical_member_bytes=32999)):
            c, a, r = fixture();mutate(a, r)
            with self.assertRaises(ValueError): m.compile_metadata(c, a, r)

    def test_unmapped_codes_retained_without_guessed_positions(self):
        c, a, r = fixture();r[0]["onsets"]["nonzero_code_counts"]["4"] = 3
        o = m.compile_metadata(c, a, r);record = o["records_private"][0]
        self.assertEqual(record["unmapped_nonzero_code_counts"], {"4": 3})
        self.assertEqual(len(record["all_condition_onset_windows_private"]), 3)
        self.assertTrue(all("unmapped_vector_codes_positions_not_retained" in x["geometry_flags"]
                            for x in record["all_condition_onset_windows_private"]))

    def test_exact_saved_clock_half_open_boundaries(self):
        for T, expected in ((.0390625, (-128, 512, 640)), (.5, (-10, 40, 50)),
                            (math.nextafter(.0390625, math.inf), (-127, 512, 639)),
                            (math.nextafter(.0390625, 0), (-128, 513, 641))):
            result = m.window_offsets(T)
            self.assertEqual(tuple(result[k] for k in ("first_offset_inclusive", "stop_offset_exclusive", "sample_count")), expected)
            p = m.Fraction(T);first, stop, _ = expected
            self.assertTrue(first*p >= -5 and (first-1)*p < -5)
            self.assertTrue((stop-1)*p < 20 and stop*p >= 20)
        for bad in (0, -1, True, float("nan"), float("inf")):
            with self.assertRaises(ValueError): m.window_offsets(bad)

    def test_boundary_and_next_onset_flags_do_not_drop_events(self):
        c, a, r = fixture()
        c["rows"][0]["marker_onsets"].update({"11": [1], "12": [500], "13": [2200]})
        c["rows"][0]["marker_onsets"]["101"] = [2]  # Keep the invented vector feasible.
        o = m.compile_metadata(c, a, r);windows = o["records_private"][0]["all_condition_onset_windows_private"]
        self.assertIn("starts_before_recording", windows[0]["geometry_flags"])
        self.assertIn("contains_subsequent_condition_onset", windows[0]["geometry_flags"])
        self.assertIn("ends_after_recording", windows[2]["geometry_flags"])
        self.assertEqual(o["condition_onsets_retained"], 495)
        c["rows"][0]["marker_onsets"]["12"] = [513]  # Exclusive stop for onset1.
        o = m.compile_metadata(c, a, r)
        self.assertNotIn("contains_subsequent_condition_onset", o["records_private"][0]["all_condition_onset_windows_private"][0]["geometry_flags"])

    def test_crop_categories_do_not_infer_execution_or_removed_samples(self):
        c, a, r = fixture()
        cases = ([["NR_segment", "15", "15"]], [["NR_segment", "2", "3"]], [],
                 [["NR_segment", "15", "5"], ["NR_segment", "15", "5"]],
                 [["custom_operation", "anything"]])
        for record, values in zip(r, cases):
            record["metadata_private"]["preprocessSet"] = steps(values)
            record["preprocessing"] = m.inspector.preprocessing_evidence(record["metadata_private"]["preprocessSet"], .0390625)
        o = m.compile_metadata(c, a, r)
        self.assertEqual(o["recorded_crop_counts"], {"15/5": 160, "15/15": 1, "other_literal": 1,
                                                   "unresolved:missing": 2, "unresolved:ambiguous_multiple_trim_steps": 1})
        self.assertTrue(all(not x["recorded_preprocessing"]["time_preserving_history_verified"] for x in o["records_private"]))
        self.assertIsNone(o["records_private"][0]["recorded_preprocessing"]["trim"]["removed_sample_counts"])

    def test_clock_unit_array_or_failure_promotion_refuse(self):
        mutations = (lambda a, r: r[0]["clock"].update(uniform_time_verified=True),
                     lambda a, r: r[0]["clock"].update(saved_T_seconds=.04),
                     lambda a, r: r[0]["units"].update(concentration_pathlength_scale="mM.mm"),
                     lambda a, r: r[0]["signals"]["dxyData"].update(shape=[2200, 34]),
                     lambda a, r: r[0].update(signal_finiteness_verified=True),
                     lambda a, r: a.update(status="FAILED_OPERATION_CUSTODY_PRESERVED"),
                     lambda a, r: a.update(complete_inspection_reports=164))
        for mutate in mutations:
            c, a, r = fixture();mutate(a, r)
            with self.assertRaises(ValueError): m.compile_metadata(c, a, r)

    def test_serial_metadata_caps_and_integer_axes(self):
        value = schema([1, 1]);value["shape"] = [True, 1]
        with self.assertRaises(ValueError): m.numeric_schema(value, [1, 1], "generated")
        old_cap = m.io.CAP
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory).resolve()/"bounded.json";body = b"[0,0,0]";path.write_bytes(body)
                m.io.CAP = len(body)-1
                with self.assertRaises(ValueError): m.io.load_json(path, hashlib.sha256(body).hexdigest())
                m.io.CAP = len(body)
                self.assertEqual(m.io.load_json(path, hashlib.sha256(body).hexdigest()), [0, 0, 0])
        finally: m.io.CAP = old_cap

    def test_impossible_vector_lower_and_upper_bounds(self):
        c, a, r = fixture()
        r[0]["onsets"]["nonzero_code_counts"].pop("11")
        r[0]["onsets"]["direct_marker_comparison"]["11"].update(vector_count=0, exact=False)
        a["regenerated_summary"]["records_with_exact_direct_marker_join"] = 164
        with self.assertRaises(ValueError): m.compile_metadata(c, a, r)
        c, a, r = fixture()
        r[0]["onsets"]["nonzero_code_counts"] = {"11": 2200}
        for code, item in r[0]["onsets"]["direct_marker_comparison"].items():
            item.update(same_index_same_code=0, wrong_code_at_expected_index=1,
                        vector_count=2200 if code == "11" else 0, exact=False)
        a["regenerated_summary"]["records_with_exact_direct_marker_join"] = 164
        with self.assertRaises(ValueError): m.compile_metadata(c, a, r)

    def test_exact_overlap_and_nonexact_subset_bound_refuse(self):
        c, a, r = fixture();c["rows"][0]["marker_onsets"]["12"] = [200]
        with self.assertRaises(ValueError): m.compile_metadata(c, a, r)
        c, a, r = fixture()
        for code in ("11", "12", "13"):
            c["rows"][0]["marker_onsets"][code] = [200, 201]
            r[0]["onsets"]["nonzero_code_counts"][code] = 3
            r[0]["onsets"]["direct_marker_comparison"][code].update(
                expected=2, same_index_same_code=2, vector_count=3, exact=False)
        a["regenerated_summary"]["records_with_exact_direct_marker_join"] = 164
        with self.assertRaises(ValueError): m.compile_metadata(c, a, r)

    def test_feasible_overlap_mismatch_is_retained(self):
        c, a, r = fixture();c["rows"][0]["marker_onsets"]["12"] = [200]
        r[0]["onsets"]["direct_marker_comparison"]["12"].update(
            same_index_same_code=0, wrong_code_at_expected_index=1, exact=False)
        a["regenerated_summary"]["records_with_exact_direct_marker_join"] = 164
        o = m.compile_metadata(c, a, r)
        self.assertEqual(o["condition_onsets_retained"], 495)
        windows = o["records_private"][0]["all_condition_onset_windows_private"]
        self.assertEqual(len(windows), 3)
        self.assertIn("simultaneous_condition_codes", windows[0]["geometry_flags"])
        self.assertIn("internal_marker_mismatch", windows[0]["geometry_flags"])
        self.assertFalse(o["eligibility_assigned"] or o["scientific_ready"])

    def test_owner_only_CLI_exact_hash_and_create_once(self):
        # In-memory synthetic contract identity substitutes only in this invented test.
        c, a, r = fixture();old_size, old_sha = m.CONTRACT_BYTES, m.CONTRACT_SHA
        try:
            with tempfile.TemporaryDirectory() as directory:
                # macOS /var is an alias; use the same generated files through
                # their physical directory rather than relaxing the donor guard.
                p = Path(directory).resolve();cb = json.dumps(c).encode()
                m.CONTRACT_BYTES = len(cb);m.CONTRACT_SHA = hashlib.sha256(cb).hexdigest()
                a["regenerated_summary"]["contract_sha256"] = m.CONTRACT_SHA
                (p/"contract.json").write_bytes(cb);pins = []
                for i, report in enumerate(r):
                    path = p/("record-%03d.json" % i);body = json.dumps(report).encode();path.write_bytes(body)
                    pins.append({"path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
                a["regenerated_reports"] = pins;ab = json.dumps(a).encode();(p/"audit.json").write_bytes(ab)
                argv = ["--audit", str(p/"audit.json"), "--audit-sha256", hashlib.sha256(ab).hexdigest(),
                        "--contract", str(p/"contract.json"), "--output", str(p/"ledger.json")]
                with contextlib.redirect_stdout(io.StringIO()): m.main(argv)
                self.assertEqual((p/"ledger.json").stat().st_mode & 0o777, 0o600)
                result = json.loads((p/"ledger.json").read_bytes());self.assertFalse(result["candidate_packet"])
                with self.assertRaises(FileExistsError): m.main(argv)
                (p/"record-004.json").write_bytes(b"{}")
                argv[-1] = str(p/"not-created.json")
                with self.assertRaises(ValueError): m.main(argv)
                self.assertFalse((p/"not-created.json").exists())
        finally:
            m.CONTRACT_BYTES, m.CONTRACT_SHA = old_size, old_sha


if __name__ == "__main__":
    unittest.main()
