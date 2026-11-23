"""Generated public-response controls; no authentic arrays or model fitting."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("neural025_preflight_test", HERE / "preflight.py")
f = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f)
d = f.d
WRITTEN = 0


def fixture(mode="direct_observation"):
    packet = {"schema": d.PACKET_SCHEMA, "task_id": "NEURAL-025",
              "target_field": "jointAngles", "target_units": "degrees",
              "joint_names": list(d.p.JOINT_NAMES), "time_ms": list(range(-100, 401, 10)),
              "sessions": []}
    for i in range(1, 11):
        packet["sessions"].append({"session_id": f"session-{i:02d}",
                                   "query": [{"case_id": "query-00001"}, {"case_id": "query-00002"}]})
    response = {"schema": d.RESPONSE_SCHEMA, "task_id": "NEURAL-025",
                "packet_sha256": d.p.digest(packet), "mode": mode,
                "target_field": packet["target_field"], "target_units": packet["target_units"],
                "joint_names": packet["joint_names"][:], "time_ms": packet["time_ms"][:],
                "predictions": {s["session_id"]: {q["case_id"]: [[float(j-t) for j in range(24)]
                                  for t in range(51)] for q in s["query"]} for s in packet["sessions"]}}
    if mode == "frozen_program":
        response["frozen_program_sha256"] = "a" * 64
    return packet, response


class PreflightControls(unittest.TestCase):
    def setUp(self):
        self.packet, self.response = fixture()

    def check(self, response=None, **kwargs):
        return f.preflight(self.response if response is None else response, self.packet,
                           expected_packet_sha256=d.p.digest(self.packet),
                           expected_mode=kwargs.pop("expected_mode", "direct_observation"), **kwargs)

    def test_all_modes_complete_counts_and_no_scientific_result(self):
        for mode in d.MODES:
            packet, response = fixture(mode)
            with self.subTest(mode=mode), patch.object(d.p, "fit_train_only", side_effect=AssertionError("fit")), \
                    patch.object(d.p, "_score", side_effect=AssertionError("score")):
                result = f.preflight(response, packet, expected_packet_sha256=d.p.digest(packet),
                                     expected_mode=mode,
                                     expected_program_sha256="a"*64 if mode == "frozen_program" else None)
            self.assertEqual((result["sessions"], result["query_trials"], result["timepoints_per_trial"],
                              result["joints_per_timepoint"]), (10, 20, 51, 24))
            for field in ("private_index_checked", "scientific_score_computed",
                          "process_isolation_verified", "scientific_qualification"):
                self.assertIs(result[field], False)
            self.assertNotIn("metrics", result)

    def test_public_validation_retains_predictions_and_private_mapping(self):
        public = d.validate_response(self.response, self.packet,
                                      expected_packet_sha256=d.p.digest(self.packet),
                                      expected_mode="direct_observation")
        self.assertEqual(public, self.response["predictions"])
        index = {"schema": d.INDEX_SCHEMA, "task_id": d.p.TASK_ID,
                 "packet_sha256": d.p.digest(self.packet),
                 "sessions": {sid: {"session_id": "native-"+sid,
                                    "query": {case: "native-"+case for case in rows}}
                              for sid, rows in public.items()}}
        native = d.collect_response(self.response, self.packet, index,
                                    expected_packet_sha256=d.p.digest(self.packet),
                                    expected_index_sha256=d.p.digest(index), expected_mode="direct_observation")
        self.assertEqual(native, {"native-"+sid: {"native-"+case: value for case, value in rows.items()}
                                  for sid, rows in public.items()})
        index["sessions"]["session-01"]["query"]["query-00002"] = "native-query-00001"
        with self.assertRaisesRegex(d.p.Refusal, "Repeated native trial"):
            d.collect_response(self.response, self.packet, index,
                               expected_packet_sha256=d.p.digest(self.packet),
                               expected_index_sha256=d.p.digest(index), expected_mode="direct_observation")

    def test_missing_extra_session_or_case_rejected(self):
        for mutation in (lambda r: r["predictions"].pop("session-10"),
                         lambda r: r["predictions"].update(extra={}),
                         lambda r: r["predictions"]["session-01"].pop("query-00002"),
                         lambda r: r["predictions"]["session-01"].update(extra=[[0]*24]*51)):
            response = copy.deepcopy(self.response)
            mutation(response)
            with self.assertRaises(d.p.Refusal):
                self.check(response)

    def test_full_trajectory_and_numeric_domain_rejected(self):
        for value in ([[0]*24]*50, [[0]*23]*51,
                      [[True]+[0]*23]*51, [[float("inf")]+[0]*23]*51,
                      [[float("nan")]+[0]*23]*51, [[2**53+1]+[0]*23]*51):
            response = copy.deepcopy(self.response)
            response["predictions"]["session-01"]["query-00001"] = value
            with self.assertRaises(d.p.Refusal):
                self.check(response)

    def test_endpoint_order_grid_units_and_extra_fields_rejected(self):
        for key, value in (("target_field", "jointVelocities"), ("target_units", "radians"),
                           ("joint_names", list(reversed(d.p.JOINT_NAMES))),
                           ("time_ms", list(range(-90, 411, 10))), ("extra", "private target")):
            response = copy.deepcopy(self.response)
            response[key] = value
            with self.assertRaises(d.p.Refusal):
                self.check(response)

    def test_access_mode_and_frozen_program_checks(self):
        with self.assertRaises(d.p.Refusal):
            self.check(expected_mode="tool_assisted")
        with self.assertRaises(d.p.Refusal):
            self.check(expected_program_sha256="a"*64)
        packet, response = fixture("frozen_program")
        with self.assertRaises(d.p.Refusal):
            f.preflight(response, packet, expected_packet_sha256=d.p.digest(packet),
                        expected_mode="frozen_program", expected_program_sha256="b"*64)
        with self.assertRaises(d.p.Refusal):
            f.preflight(response, packet, expected_packet_sha256=d.p.digest(packet),
                        expected_mode="frozen_program")

    def test_packet_or_response_identity_changes_rejected(self):
        with self.assertRaises(d.p.Refusal):
            f.preflight(self.response, self.packet, expected_packet_sha256="b"*64,
                        expected_mode="direct_observation")
        self.response["packet_sha256"] = "b"*64
        with self.assertRaises(d.p.Refusal):
            self.check()

    def test_velocity_endpoint_retains_separate_units(self):
        for obj in (self.packet, self.response):
            obj.update(target_field="jointVelocities", target_units="degrees_per_second")
        self.response["packet_sha256"] = d.p.digest(self.packet)
        self.assertEqual(self.check()["target_units"], "degrees_per_second")

    def test_bounded_cli_success_and_refusals_without_private_inputs(self):
        global WRITTEN
        with tempfile.TemporaryDirectory(prefix="n025-preflight-") as root:
            root = Path(root)
            packet = root / "packet.json"
            response = root / "response.json"
            for path, value in ((packet, self.packet), (response, self.response)):
                body = d.p.canonical_bytes(value)
                path.write_bytes(body)
                WRITTEN += len(body)
            cmd = [sys.executable, "-B", str(HERE / "preflight.py"),
                   "--packet", str(packet), "--response", str(response),
                   "--expected-packet-sha256", d.p.digest(self.packet),
                   "--mode", "direct_observation", "--max-input-bytes", "1000000", "--max-output-bytes", "4096"]
            good = subprocess.run(cmd, capture_output=True, timeout=20)
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertEqual(json.loads(good.stdout)["query_trials"], 20)
            for option, limit in (("--max-input-bytes", "1"), ("--max-output-bytes", "1")):
                bad = cmd[:]
                bad[bad.index(option)+1] = limit
                result = subprocess.run(bad, capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(json.loads(result.stderr)["status"], "refused")
            body = b'{"schema":1,"schema":2}'
            response.write_bytes(body)
            WRITTEN += len(body)
            result = subprocess.run(cmd, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b"Duplicate JSON key", result.stderr)
            self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        print(json.dumps({"generated_fixture_bytes_written": WRITTEN,
                          "authentic_inputs": 0, "model_fits": 0, "scoring_calls": 0}), file=sys.stderr)
