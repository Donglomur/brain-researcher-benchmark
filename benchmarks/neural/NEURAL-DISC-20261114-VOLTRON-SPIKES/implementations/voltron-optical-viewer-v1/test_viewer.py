"""Invented full-roster protocol tests; no authentic signals or event labels."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import re
import unittest

P = Path(__file__).with_name("viewer.py")
spec = importlib.util.spec_from_file_location("voltron_optical_generated", P)
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)


def fixture():
    cells = ["c" + str(i) for i in range(12)]
    public = {"schema": "voltron-native-frame-public/v1", "task_id": V.TASK,
              "profile": V.S.PROFILE, "release_manifest_sha256": "0" * 64,
              "cells": cells, "expected_subjects": 6, "movies": {}}
    traces = {}
    for i in range(34):
        mid = "m" + str(i)
        public["movies"][mid] = {"cell_id": cells[i % 12], "fold_id": "f" + str(i % 12 // 2),
            "nominal_optical_rate_hz": 400 if i % 2 else 1000,
            "start_time": 0, "end_time": [1, 20],
            "frame_times": [[j, 401] for j in (0, 1, 3, 4, 9, 10)],
            "input_disposition": "ready", "optical_valid_intervals": [[0, [1, 20]]],
            "cores": [{"core_id": mid + "a", "start_frame": 0, "end_frame": 3},
                      {"core_id": mid + "b", "start_frame": 3, "end_frame": 6}]}
        traces[mid] = {"samples": [0., .5, 1., -.5, 0., .25],
                       "amplitude_unit": "delta_f_over_f", "indicator_polarity": -1,
                       "exposure_seconds": [1, 1000]}
    packet = {"schema": "voltron-prepared-optical-traces/v1", "task_id": V.TASK,
              "public_sha256": V.S.identity(public), "preparation_sha256": "1" * 64,
              "movies": traces}
    return public, packet


def session(public, packet, fold="f0", program="2" * 64):
    return V.Session(public, packet, fold_id=fold, program_sha256=program,
                     calibration_sha256=hashlib.sha256(fold.encode()).hexdigest())


def complete(s):
    for c in s.catalog():
        s.answer(c["core_id"], [c["start_frame"]])
    return s.finish()


def resign(receipt):
    receipt["receipt_sha256"] = V.identity({k: v for k, v in receipt.items() if k != "receipt_sha256"})


def rechain(receipt):
    head = V.identity({k: receipt[k] for k in ("schema", "task_id", "public_sha256", "packet_sha256",
                                              "fold_id", "program_sha256", "calibration_sha256")})
    for action in receipt["actions"]:
        action["previous_sha256"] = head
        action["sha256"] = V.identity({k: v for k, v in action.items() if k != "sha256"})
        head = action["sha256"]
    receipt["action_head_sha256"] = head
    resign(receipt)


class ViewerControls(unittest.TestCase):
    def test_full_six_fold_join_reaches_existing_scorer_interface(self):
        public, packet = fixture()
        receipts = [complete(session(public, packet, "f" + str(i))) for i in range(6)]
        candidate = V.assemble_candidate(public, packet, receipts)
        self.assertEqual(len(candidate["cores"]), 68)
        predictions = {"schema": "voltron-native-frame-predictions/v1", "task_id": V.TASK,
                       "public_sha256": V.S.identity(public),
                       "roles": {r: copy.deepcopy(candidate) for r in V.S.ROLES}}
        captured, commitments = V.S.capture_predictions(predictions, V.S.public_contract(public))
        self.assertEqual(len(captured["candidate"]), 34)
        self.assertEqual(sum(map(len, captured["candidate"].values())), 68)
        self.assertEqual(commitments["candidate"]["program_sha256"], "2" * 64)

    def test_nonuniform_native_time_axis_not_nominal_clock(self):
        public, packet = fixture()
        response = session(public, packet).view("m0a", start_frame=0, end_frame=6, low=-1, high=1)
        self.assertEqual(response["native_last_seconds"], [10, 401])
        xs = [float(x) for x in re.findall(r'<circle cx="([0-9.]+)"', response["svg"])]
        self.assertEqual(xs, [60., 170., 390., 500., 1050., 1160.])
        self.assertEqual(response["core_end_frame"], 3)
        self.assertEqual(response["exposure_seconds"], [1, 1000])
        self.assertNotIn("spikes", response)

    def test_only_held_fold_core_can_be_viewed_or_answered(self):
        public, packet = fixture()
        s = session(public, packet)
        self.assertNotIn("m2a", {c["core_id"] for c in s.catalog()})
        with self.assertRaises(V.ViewerError):
            s.view("m2a", start_frame=0, end_frame=3, low=-1, high=1)
        with self.assertRaises(V.ViewerError):
            s.answer("m2a", [])

    def test_first_final_answer_and_frozen_packet(self):
        public, packet = fixture()
        s = session(public, packet)
        public["movies"]["m0"]["frame_times"][1] = [1, 1]
        packet["movies"]["m0"]["samples"][1] = 9999
        response = s.view("m0a", start_frame=0, end_frame=3, low=-1, high=1)
        self.assertEqual(response["clipped_frames"], [])
        values = [1]
        acknowledgement = s.answer("m0a", values)
        values[:] = [2]
        acknowledgement["frames"][:] = [2]
        with self.assertRaises(V.ViewerError):
            s.answer("m0a", [2])
        for c in s.catalog():
            if c["core_id"] != "m0a":
                s.answer(c["core_id"], [])
        r = s.finish()
        self.assertEqual(r["cores"]["m0a"], [1])
        r["cores"]["m0a"][:] = [2]
        self.assertEqual(s.finish()["cores"]["m0a"], [1])
        with self.assertRaises(V.ViewerError):
            s.view("m0a", start_frame=0, end_frame=3, low=-1, high=1)

    def test_bad_event_outputs_and_incomplete_finish(self):
        public, packet = fixture()
        s = session(public, packet)
        for values in ([True], [1.], [1, 1], [2, 1], [-1], [3], [float("nan")]):
            with self.subTest(values=values), self.assertRaises(V.ViewerError):
                s.answer("m0a", values)
        with self.assertRaises(V.ViewerError):
            s.finish()
        self.assertEqual(s.answer("m0a", [1])["frames"], [1])

    def test_bad_scope_binding_and_forbidden_extra_channel(self):
        public, packet = fixture()
        for mutate in (lambda p: p["movies"].pop("m33"),
                       lambda p: p.update(public_sha256="a" * 64),
                       lambda p: p["movies"]["m0"].update(spikes=[0]),
                       lambda p: p["movies"]["m0"]["samples"].pop()):
            broken = copy.deepcopy(packet)
            mutate(broken)
            with self.assertRaises((V.ViewerError, V.S.ContractError)):
                session(public, broken)
        broken = copy.deepcopy(public)
        broken["movies"]["m0"]["fold_id"] = "f99"
        packet["public_sha256"] = V.S.identity(broken)
        with self.assertRaises(V.ViewerError):
            session(broken, packet)

    def test_missingness_and_failed_extraction_preserve_complete_roster(self):
        public, packet = fixture()
        packet["movies"]["m0"]["samples"][1] = None
        with self.assertRaises(V.ViewerError):
            session(public, packet)
        public["movies"]["m0"]["optical_valid_intervals"] = [[0, [1, 401]], [[3, 401], [1, 20]]]
        packet["public_sha256"] = V.S.identity(public)
        response = session(public, packet).view("m0a", start_frame=0, end_frame=6, low=-1, high=1)
        self.assertEqual(response["missing_frames"], [1])
        self.assertEqual(response["svg"].count("<circle"), 5)
        # Explicit total extraction failure still requires the same clock and cores.
        public["movies"]["m0"]["input_disposition"] = "optical_extraction_failed"
        public["movies"]["m0"]["optical_valid_intervals"] = []
        packet["movies"]["m0"]["samples"] = [None] * 6
        packet["public_sha256"] = V.S.identity(public)
        s = session(public, packet)
        self.assertEqual(s.view("m0a", start_frame=0, end_frame=6, low=-1, high=1)["missing_frames"], list(range(6)))
        self.assertIn("m0a", {c["core_id"] for c in s.catalog()})
        self.assertFalse(complete(s)["scientific_qualified"])

    def test_explicit_gain_clipping_and_bad_display_requests(self):
        public, packet = fixture()
        s = session(public, packet)
        r = s.view("m0a", start_frame=0, end_frame=6, low=-.25, high=.25)
        self.assertEqual(r["clipped_frames"], [1, 2, 3])
        self.assertEqual(r["svg"].count('fill="#c33"'), 3)
        for kw in ({"low": 0, "high": 0}, {"low": float("nan"), "high": 1},
                   {"low": True, "high": 1}, {"start_frame": True}, {"end_frame": 7}):
            args = dict(start_frame=0, end_frame=3, low=-1, high=1)
            args.update(kw)
            with self.assertRaises(V.ViewerError):
                s.view("m0a", **args)

    def test_failed_extraction_refuses_fabricated_trace_and_event_budget_is_atomic(self):
        public, packet = fixture()
        broken = copy.deepcopy(public)
        broken["movies"]["m0"]["input_disposition"] = "optical_extraction_failed"
        broken["movies"]["m0"]["optical_valid_intervals"] = []
        changed = copy.deepcopy(packet)
        changed["public_sha256"] = V.S.identity(broken)
        with self.assertRaises(V.ViewerError):
            session(broken, changed)
        s = session(public, packet)
        s._event_total = V.S.MAX_EVENTS - 1  # generated boundary setup, not a participant API
        with self.assertRaises(V.ViewerError):
            s.answer("m0a", [0, 1])
        self.assertEqual(s._event_total, V.S.MAX_EVENTS - 1)
        s.answer("m0a", [0])
        self.assertEqual(s._event_total, V.S.MAX_EVENTS)
        self.assertEqual(s.answer("m0b", [])["frames"], [])
        with self.assertRaises(V.ViewerError):
            s.answer("m1a", [0])

    def test_physical_one_second_halo_and_window_ceiling(self):
        public, packet = fixture()
        row = public["movies"]["m0"]
        row["frame_times"] = [[i, 1000] for i in range(3000)]
        row["end_time"] = 3
        row["cores"] = [{"core_id": "m0a", "start_frame": 0, "end_frame": 1000},
                        {"core_id": "m0b", "start_frame": 1000, "end_frame": 3000}]
        row["optical_valid_intervals"] = [[0, 3]]
        packet["movies"]["m0"]["samples"] = [0.] * 3000
        packet["public_sha256"] = V.S.identity(public)
        s = session(public, packet)
        s.view("m0a", start_frame=1900, end_frame=2000, low=-1, high=1)
        with self.assertRaises(V.ViewerError):
            s.view("m0a", start_frame=1900, end_frame=2001, low=-1, high=1)
        with self.assertRaises(V.ViewerError):
            s.view("m0b", start_frame=0, end_frame=2049, low=-1, high=1)

    def test_duplicate_fold_missing_receipt_and_program_mismatch(self):
        public, packet = fixture()
        receipts = [complete(session(public, packet, "f" + str(i))) for i in range(6)]
        for broken in (receipts[:-1], receipts[:-1] + [receipts[0]],
                       receipts[:-1] + [complete(session(public, packet, "f5", "9" * 64))]):
            with self.assertRaises(V.ViewerError):
                V.assemble_candidate(public, packet, broken)

    def test_tampered_or_rehashed_inconsistent_answers_refused(self):
        public, packet = fixture()
        receipts = [complete(session(public, packet, "f" + str(i))) for i in range(6)]
        for new_value in ([1], [0.], [False]):
            broken = copy.deepcopy(receipts)
            broken[0]["cores"]["m0a"] = new_value
            resign(broken[0])
            with self.assertRaises(V.ViewerError):
                V.assemble_candidate(public, packet, broken)
        broken = copy.deepcopy(receipts)
        broken[0]["actions"][0]["response_sha256"] = "0" * 64
        rechain(broken[0])
        with self.assertRaises(V.ViewerError):
            V.assemble_candidate(public, packet, broken)

    def test_rehashed_illegal_view_still_refused(self):
        public, packet = fixture()
        s = session(public, packet)
        s.view("m0a", start_frame=0, end_frame=3, low=-1, high=1)
        receipts = [complete(s)] + [complete(session(public, packet, "f" + str(i))) for i in range(1, 6)]
        receipts[0]["actions"][0]["request"]["end_frame"] = 9999
        rechain(receipts[0])
        with self.assertRaises(V.ViewerError):
            V.assemble_candidate(public, packet, receipts)

    def test_complete_six_fold_roster_cannot_split_one_cells_movies(self):
        public, packet = fixture()
        # m0/m12/m24 belong to c0. Six fold IDs and all34movies remain present;
        # the public geometry alone is sufficient to prove this split impossible.
        public["movies"]["m12"]["fold_id"] = "f1"
        packet["public_sha256"] = V.S.identity(public)
        self.assertEqual(len(public["movies"]), 34)
        self.assertEqual(len({m["fold_id"] for m in public["movies"].values()}), 6)
        with self.assertRaisesRegex(V.ViewerError, "one public fold per cell"):
            session(public, packet)
        with self.assertRaisesRegex(V.ViewerError, "one public fold per cell"):
            V.assemble_candidate(public, packet, [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
