"""Invented cases only. No fixture represents an observed retina or a data file."""
import copy
from email.message import Message
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from retina_contract import (ARCHIVES, CELL_TYPES, DATA_COMMIT, DATA_DOI, METHODS, Refusal,
                             coverage_ledger, projection_plan, validate_release_manifest)
from scientific_kernels import improvement_population_gate, pair_disagreement_ranking, score_response
from archive_intake import acquire

H = "a" * 64


def manifest(payload=b"abc"):
    return {"schema": "retina-exact-release-v1", "data_doi": DATA_DOI, "data_commit": DATA_COMMIT,
            "archives": [{"name": n, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
                          "metadata_evidence_sha256": H} for n in ARCHIVES]}


def inventory():
    return {"schema": "retina-field-inventory-v1", "data_commit": DATA_COMMIT,
            "sessions": [{"archive": n, "complete_member_inventory": True,
                          "members": [{"name": f, "sha256": H, "bytes": 1,
                                       "complete_field_inventory": True, "fields": fields}
                                      for f, fields in (
                                          ("expdata.mat", ["animal", "units", "fs"]),
                                          ("fixationmovie_data.mat", ["runningbin", "frozenbin", "rawdata",
                                                                     "runningImages", "frozenImages"]),
                                          ("gratingflicker_data.mat", ["spikesfit", "orderfit"]),
                                      )]} for n in ARCHIVES]}


def coverage():
    return {"schema": "retina-unit-coverage-v1", "data_commit": DATA_COMMIT,
            "sessions": [{"archive": n, "animal_id": "animal-" + str(i),
                          "piece_id": "piece-" + str(i), "identity_evidence_sha256": H,
                          "source_unit_count": 1, "units": [{
                              "unit_id": "unit-1", "cell_type": "ON parasol" if "_marmoset_" in n else "sustained-ON alpha",
                              "fig4_disposition": "eligible", "fig4_reason": "invented fixture",
                              "eligibility_evidence_sha256": H,
                              "methods": {m: {"status": "complete", "reason": "invented fixture",
                                              "scope_evidence_sha256": H} for m in METHODS}
                          }]} for i, n in enumerate(ARCHIVES)]}


class Response:
    def __init__(self, url, body=b"abc", status=200, headers=None, fail_read=False, short_chunks=False):
        self.url, self.status, self.body = url, status, io.BytesIO(body)
        self.fail_read, self.short_chunks = fail_read, short_chunks
        self.headers = Message()
        for k, v in headers or []:
            self.headers[k] = v

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.body.close()

    def geturl(self):
        return self.url

    def read(self, n):
        if self.fail_read:
            raise OSError("invented read failure")
        return self.body.read(min(n, 1) if self.short_chunks else n)


class RetinaConstructionControls(unittest.TestCase):
    def test_01_all18_exact_release(self):
        m = manifest()
        m["archives"].reverse()
        p = validate_release_manifest(m)
        self.assertEqual([x["name"] for x in p["archives"]], list(ARCHIVES))
        self.assertEqual(p["total_archive_bytes"], 54)
        self.assertFalse(p["metadata_authority_verified"])

    def test_02_missing_archive(self):
        m = manifest()
        m["archives"].pop()
        with self.assertRaisesRegex(Refusal, "all18"):
            validate_release_manifest(m)

    def test_03_duplicate_archive(self):
        m = manifest()
        m["archives"][-1] = copy.deepcopy(m["archives"][0])
        with self.assertRaisesRegex(Refusal, "duplicate"):
            validate_release_manifest(m)

    def test_04_wrong_release_commit(self):
        m = manifest()
        m["data_commit"] = "b" * 40
        with self.assertRaisesRegex(Refusal, "identity"):
            validate_release_manifest(m)

    def test_05_url_override_forbidden(self):
        m = manifest()
        m["archives"][0]["url"] = "https://example.invalid/"
        with self.assertRaisesRegex(Refusal, "schema"):
            validate_release_manifest(m)

    def test_06_boolean_size_forbidden(self):
        m = manifest()
        m["archives"][0]["bytes"] = True
        with self.assertRaisesRegex(Refusal, "positive_integer"):
            validate_release_manifest(m)

    def test_07_unresolved_digest_cannot_acquire(self):
        m = manifest()
        m["archives"][0]["sha256"] = None
        with self.assertRaisesRegex(Refusal, "sha256"):
            validate_release_manifest(m)

    def test_08_frozen_and_mixed_responses_protected(self):
        out = projection_plan(inventory())
        protected = [x for x in out["rows"] if x["field"] in ("frozenbin", "rawdata")]
        self.assertEqual(len(protected), 36)
        self.assertTrue(all(not x["participant_allowed"] for x in protected))
        self.assertFalse(out["participant_materialization_ready"])

    def test_09_fitted_answers_never_participant_fields(self):
        v = inventory()
        v["sessions"][0]["members"].append({"name": "modelparameters.txt", "sha256": H, "bytes": 1,
                                           "complete_field_inventory": True, "fields": []})
        out = projection_plan(v)
        row = next(x for x in out["rows"] if x["member"] == "modelparameters.txt")
        self.assertFalse(row["participant_allowed"])
        self.assertEqual(row["role"], "protected_fitted_answer")

    def test_10_unknown_fields_hold(self):
        v = inventory()
        v["sessions"][0]["members"][1]["fields"].append("undocumented")
        out = projection_plan(v)
        self.assertTrue(any(x.endswith(":undocumented") for x in out["holds"]))
        self.assertFalse(next(x for x in out["rows"] if x["field"] == "undocumented")["participant_allowed"])

    def test_11_missing_required_member_is_not_silently_dropped(self):
        v = inventory()
        v["sessions"][0]["members"].pop()
        self.assertTrue(any("gratingflicker_data.mat:absent" in x for x in projection_plan(v)["holds"]))

    def test_12_incomplete_field_inventory_refuses(self):
        v = inventory()
        v["sessions"][0]["members"][0]["complete_field_inventory"] = False
        with self.assertRaisesRegex(Refusal, "incomplete_fields"):
            projection_plan(v)

    def test_13_duplicate_field_refuses(self):
        v = inventory()
        v["sessions"][0]["members"][0]["fields"].append("animal")
        with self.assertRaisesRegex(Refusal, "fields"):
            projection_plan(v)

    def test_14_all_units_and_methods_retained(self):
        r = coverage_ledger(coverage())
        self.assertEqual(r["source_units"], 18)
        self.assertEqual(sum(r["fig4_expected_cells"].values()), 390)
        self.assertEqual(sum(r["fig4_expected_pairs"].values()), 4453)
        self.assertFalse(r["fig4_cell_count_match"])
        self.assertFalse(r["historical_cohort_verified"])

    def test_15_omitted_unit_refuses(self):
        v = coverage()
        v["sessions"][0]["units"] = []
        with self.assertRaisesRegex(Refusal, "unit_omission"):
            coverage_ledger(v)

    def test_16_duplicate_source_unit_refuses(self):
        v = coverage()
        v["sessions"][0]["units"] *= 2
        v["sessions"][0]["source_unit_count"] = 2
        with self.assertRaisesRegex(Refusal, "duplicate"):
            coverage_ledger(v)

    def test_17_missing_method_refuses(self):
        v = coverage()
        del v["sessions"][0]["units"][0]["methods"]["stnmf"]
        with self.assertRaisesRegex(Refusal, "methods:schema"):
            coverage_ledger(v)

    def test_18_stnmf_parasol_failure_stays_in_denominator(self):
        v = coverage()
        v["sessions"][12]["units"][0]["methods"]["stnmf"]["status"] = "historical_stnmf_omitted"
        r = coverage_ledger(v)
        self.assertEqual(r["source_units"], 18)
        self.assertEqual(r["all_method_status_counts"]["stnmf"]["historical_stnmf_omitted"], 1)
        self.assertEqual(sum(r["all_method_status_counts"]["stnmf"].values()), 18)

    def test_19_stnmf_omission_not_relabelled_for_other_type(self):
        v = coverage()
        u = v["sessions"][12]["units"][0]
        u["cell_type"] = "OFF midget"
        u["methods"]["stnmf"]["status"] = "historical_stnmf_omitted"
        with self.assertRaisesRegex(Refusal, "invalid_stnmf_omission"):
            coverage_ledger(v)

    def test_20_no_animal_identity_guess_from_filename(self):
        v = coverage()
        v["sessions"][0]["animal_id"] = None
        r = coverage_ledger(v)
        self.assertTrue(any(x.endswith(":animal_piece_lineage") for x in r["unresolved"]))

    def test_21_sg_exclusion_remains_counted(self):
        v = coverage()
        u = v["sessions"][0]["units"][0]
        u["fig4_disposition"] = "excluded"
        u["methods"]["subunit_grid"]["status"] = "no_eligible_model"
        r = coverage_ledger(v)
        self.assertEqual(r["source_units"], 18)
        self.assertEqual(r["eligibility_counts"]["excluded"], 1)
        self.assertEqual(r["all_method_status_counts"]["subunit_grid"]["no_eligible_model"], 1)

    def test_22_nonfinite_predictions_refuse(self):
        with self.assertRaisesRegex(Refusal, "finite"):
            score_response([0, 1], [0, float("nan")])

    def test_23_missing_prediction_frame_refuses(self):
        with self.assertRaisesRegex(Refusal, "complete_frames"):
            score_response([0, 1], [0])

    def test_24_boolean_prediction_refuses(self):
        with self.assertRaisesRegex(Refusal, "finite"):
            score_response([0, 1], [0, True])

    def test_25_clipped_and_unclipped_scores_separate(self):
        r = score_response([0, 1], [2, 3])
        self.assertEqual(r["r2_unclipped"], -15.)
        self.assertEqual(r["r2_historical_clipped"], 0.)
        self.assertFalse(r["historical_nan_dropping_used"])

    def test_26_constant_target_has_explicit_hold(self):
        r = score_response([1, 1], [1, 2])
        self.assertTrue(r["constant_target_hold"])
        self.assertIsNone(r["r2_unclipped"])

    def test_27_test_range_normalization_and_full_order(self):
        r = pair_disagreement_ranking([[0, 0], [0, 0]], [[1, 3], [2, 4]], [[2, 4], [10, 14]],
                                      [{"id": "f0", "frames": [0]}, {"id": "f1", "frames": [1]}])
        self.assertEqual([x["score"] for x in r["ranked_fixations"]], [1.25, .5])
        self.assertFalse(r["selection_applied"])
        self.assertIsNone(r["top20_rounding_policy"])

    def test_28_missing_fixation_frames_refuse(self):
        with self.assertRaisesRegex(Refusal, "missing_frame"):
            pair_disagreement_ranking([[0, 0]] * 2, [[1, 1]] * 2, [[0, 1]] * 2,
                                      [{"id": "f", "frames": [0]}])

    def test_29_reused_fixation_frame_refuses(self):
        with self.assertRaisesRegex(Refusal, "duplicate_frame"):
            pair_disagreement_ranking([[0, 0]] * 2, [[1, 1]] * 2, [[0, 1]] * 2,
                                      [{"id": "f", "frames": [0]}, {"id": "g", "frames": [0, 1]}])

    def test_30_zero_response_range_holds(self):
        r = pair_disagreement_ranking([[0, 0]] * 2, [[1, 1]] * 2, [[1, 1]] * 2,
                                      [{"id": "f", "frames": [0, 1]}])
        self.assertEqual(r["status"], "HELD_ZERO_OR_NONFINITE_TEST_RANGE")
        self.assertIsNone(r["ranked_fixations"])

    def test_31_ties_not_historical_selection(self):
        r = pair_disagreement_ranking([[0, 0]] * 2, [[1, 1]] * 2, [[0, 1]] * 2,
                                      [{"id": "f", "frames": [0]}, {"id": "g", "frames": [1]}])
        self.assertTrue(r["ties"])
        self.assertFalse(r["historical_selection_parity"])

    def test_32_declared_ids_cannot_authorize_animal_balanced_score(self):
        rows = [{"animal_id": a, "piece_id": p, "unit_id": u, "candidate_mse": e,
                 "sg_mse": 4., "dog_mse": 5.} for a, p, u, e in
                [("a", "a1", "1", 0.), ("a", "a2", "2", 0.), ("b", "b1", "1", 6.)]]
        r = improvement_population_gate(rows)
        self.assertIsNone(r["animal_balanced_scores"])
        self.assertIsNone(r["authenticated_animals"])
        self.assertEqual(r["declared_group_ids"], 2)
        self.assertFalse(r["original_metrics_replaced"])
        self.assertFalse(r["improvement_claim"])

    def test_33_unknown_animal_refuses_grouped_score(self):
        row = {"animal_id": None, "piece_id": "p", "unit_id": "u",
               "candidate_mse": 1., "sg_mse": 2., "dog_mse": 3.}
        with self.assertRaisesRegex(Refusal, "missing_identity"):
            improvement_population_gate([row])

    def test_34_failed_baseline_cannot_drop_from_improvement(self):
        row = {"animal_id": "a", "piece_id": "p", "unit_id": "u",
               "candidate_mse": 1., "sg_mse": float("nan"), "dog_mse": 3.}
        with self.assertRaisesRegex(Refusal, "failed_or_nonfinite"):
            improvement_population_gate([row])

    def test_35_duplicate_unit_cannot_improve_group_weight(self):
        row = {"animal_id": "a", "piece_id": "p", "unit_id": "u",
               "candidate_mse": 1., "sg_mse": 2., "dog_mse": 3.}
        with self.assertRaisesRegex(Refusal, "duplicate_unit"):
            improvement_population_gate([row, row])

    def intake_case(self, body=b"abc", headers=None, status=200, wrong_url=False,
                    fail_read=False, m=None):
        """Temporary fixture bytes only; this injected opener cannot access network."""
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        output = Path(temp.name).resolve() / "capture"
        calls = []
        def opener(url, seconds):
            calls.append(url)
            return Response(url + "/changed" if wrong_url else url, body, status, headers, fail_read)
        return output, calls, lambda: acquire(m or manifest(), str(output), 10, opener)

    def test_36_complete_all18_byte_path(self):
        output, calls, run = self.intake_case(headers=[("Content-Length", "3")])
        r = run()
        self.assertEqual(len(calls), 18)
        self.assertEqual(r["successfully_written_bytes"], 54)
        self.assertEqual(r["status"], "COMPLETE_ARCHIVE_BYTES_ONLY")
        self.assertEqual(len(list(output.glob("*.rar"))), 18)
        self.assertFalse(r["archive_extraction_performed"])

    def test_37_truncated_body_retained(self):
        output, calls, run = self.intake_case(body=b"ab")
        with self.assertRaisesRegex(Refusal, "intake incomplete"):
            run()
        r = json.loads((output / "RECEIPT.json").read_text())
        self.assertEqual((output / ARCHIVES[0]).read_bytes(), b"ab")
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(r["not_attempted"]), 17)
        self.assertEqual(r["error"]["message"], "body:short")

    def test_38_oversized_body_refuses(self):
        output, calls, run = self.intake_case(body=b"abcd")
        with self.assertRaises(Refusal):
            run()
        r = json.loads((output / "RECEIPT.json").read_text())
        self.assertEqual(r["error"]["message"], "body:overflow")
        self.assertEqual(r["observed_entity_bytes"], 4)
        self.assertEqual(len(calls), 1)

    def test_39_digest_mismatch_refuses(self):
        output, _, run = self.intake_case(body=b"abd")
        with self.assertRaises(Refusal):
            run()
        self.assertEqual(json.loads((output / "RECEIPT.json").read_text())["error"]["message"], "body:digest")

    def test_40_redirect_refuses(self):
        output, _, run = self.intake_case(wrong_url=True)
        with self.assertRaises(Refusal):
            run()
        self.assertEqual(json.loads((output / "RECEIPT.json").read_text())["error"]["message"],
                         "http:status_or_redirect")

    def test_41_content_encoding_refuses(self):
        output, _, run = self.intake_case(headers=[("Content-Encoding", "gzip")])
        with self.assertRaises(Refusal):
            run()
        self.assertEqual(json.loads((output / "RECEIPT.json").read_text())["error"]["message"], "http:encoding")

    def test_42_conflicting_framing_refuses(self):
        output, _, run = self.intake_case(headers=[("Content-Length", "3"), ("Transfer-Encoding", "chunked")])
        with self.assertRaises(Refusal):
            run()
        self.assertEqual(json.loads((output / "RECEIPT.json").read_text())["error"]["message"], "http:ambiguous_framing")

    def test_43_duplicate_length_refuses(self):
        output, _, run = self.intake_case(headers=[("Content-Length", "3"), ("Content-Length", "3")])
        with self.assertRaises(Refusal):
            run()
        self.assertEqual(json.loads((output / "RECEIPT.json").read_text())["error"]["message"], "http:duplicate_length")

    def test_44_existing_output_cannot_restart(self):
        output, calls, run = self.intake_case()
        output.mkdir()
        with self.assertRaises(FileExistsError):
            run()
        self.assertEqual(calls, [])

    def test_45_read_failure_lower_bound_explicit(self):
        output, _, run = self.intake_case(fail_read=True)
        with self.assertRaises(Refusal):
            run()
        r = json.loads((output / "RECEIPT.json").read_text())
        self.assertTrue(r["failed_read_prefix_bytes_unmeasured"])
        self.assertEqual(r["requested_read_bytes"], 4)
        self.assertEqual(len(r["not_attempted"]), 17)

    def test_46_symlink_ancestor_refuses(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t).resolve()
            (p / "real").mkdir()
            (p / "alias").symlink_to(p / "real", target_is_directory=True)
            calls = []
            with self.assertRaisesRegex(Refusal, "ancestor"):
                acquire(manifest(), str(p / "alias" / "out"), 1,
                        lambda u, s: calls.append(u))
            self.assertEqual(calls, [])

    def test_47_worker_clock_failure_preserved(self):
        output, calls, run = self.intake_case()
        with patch("archive_intake.time.monotonic", side_effect=[0., 0., 11., 12.]):
            with self.assertRaises(Refusal):
                run()
        r = json.loads((output / "RECEIPT.json").read_text())
        self.assertEqual(r["error"]["message"], "wall:expired_during_stream")
        self.assertEqual(len(calls), 1)

    def test_48_inputs_not_mutated(self):
        v = inventory()
        before = copy.deepcopy(v)
        projection_plan(v)
        self.assertEqual(v, before)

    def test_49_declared_nonfixation_frames_keep_full_test_range(self):
        r = pair_disagreement_ranking([[0, 0, 0]] * 2, [[1, 1, 999]] * 2, [[0, 2, 10]] * 2,
                                      [{"id": "f", "frames": [0, 1]}], nonfixation_frames=[2])
        self.assertAlmostEqual(r["ranked_fixations"][0]["score"], .1)
        self.assertEqual(r["declared_nonfixation_frames"], 1)
        self.assertFalse(r["fixation_mapping_authenticated"])

    def test_50_fixation_and_nonfixation_overlap_refuses(self):
        with self.assertRaisesRegex(Refusal, "nonfixation_overlap"):
            pair_disagreement_ranking([[0, 0]] * 2, [[1, 1]] * 2, [[0, 1]] * 2,
                                      [{"id": "f", "frames": [0, 1]}], nonfixation_frames=[1])

    def test_51_species_cell_type_mismatch_refuses(self):
        v = coverage()
        v["sessions"][0]["units"][0]["cell_type"] = "ON parasol"
        with self.assertRaisesRegex(Refusal, "species_cell_type"):
            coverage_ledger(v)

    def test_52_sg_exclusion_not_reassigned_to_other_baseline(self):
        v = coverage()
        v["sessions"][0]["units"][0]["methods"]["dog_ln"]["status"] = "no_eligible_model"
        with self.assertRaisesRegex(Refusal, "invalid_sg_exclusion"):
            coverage_ledger(v)


    def test_53_finite_inputs_cannot_return_infinite_r2(self):
        # Finite squared error (~1e308), but dividing by SST=.5 overflows.
        with self.assertRaisesRegex(Refusal, "metric:nonfinite_ratio"):
            score_response([0., 1.], [1e154, 1.])
