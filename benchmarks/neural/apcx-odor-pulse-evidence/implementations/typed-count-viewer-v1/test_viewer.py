"""Generated APCx viewer controls. No authentic arrays, owner targets or fits."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zlib

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import viewer

SOURCE = Path(os.environ.get("APCX_BOUNDARY_DIRECTORY", str(HERE.parent / "deposited-label")))
sys.path.insert(0, str(SOURCE))
import episode_boundary as boundary
import released_profile as profile
import task as predecessor

TEMP_WRITTEN_BYTES = 0


def opaque(text):
    return hashlib.sha256(text.encode()).hexdigest()


def episode(condition="matched", index=0, *, units=2, query_count=10, full_cal=30, full_dev=10):
    session = {"session_id": opaque("GENERATED_SESSION_" + str(index)),
               "channel_ids": [opaque(f"GENERATED_UNIT_{index}_{u}") for u in range(units)],
               "calibration": [], "development": [], "queries": []}
    sizes = {"calibration": 16 if condition == "matched" else full_cal,
             "development": 8 if condition == "matched" else full_dev, "queries": query_count}
    for split, size in sizes.items():
        for trial in range(size):
            row = {"case_id": opaque(f"GENERATED_CASE_{index}_{split}_{trial}"),
                   "spikes": [[(trial + u + b) % 4 for b in range(90)] for u in range(units)]}
            if split != "queries":
                row.update(count=trial % 19, high=int(trial % 19 >= 9))
            session[split].append(row)
        session[split].sort(key=lambda row: row["case_id"])
    return {"schema": "apcx-one-public-session-v1", "profile": boundary.PROFILE,
            "profile_contract_sha256": boundary.CONTRACT, "profile_document_sha256": boundary.DOCUMENT,
            "condition": condition, "participant_packet_sha256": opaque("GENERATED_PACKET_" + condition),
            "invented": True, "session": session,
            "documentation_utf8": boundary.canonical(profile.DOCUMENTATION).decode()}


def session(value=None):
    value = episode() if value is None else value
    return viewer.Session(value, boundary.digest(value), boundary_directory=SOURCE)


def view_request(e, split="queries", row=0, **changes):
    request = {"action": "view", "split": split, "case_id": e["session"][split][row]["case_id"],
               "unit_start": 0, "unit_stop": len(e["session"]["channel_ids"]), "bin_start": 0, "bin_stop": 90}
    request.update(changes)
    return request


def complete(s, e, count=-2.5):
    for row in reversed(e["session"]["queries"]):
        s.dispatch({"action": "answer", "case_id": row["case_id"], "count": count})
    return s.dispatch({"action": "finish"})


def decode_png(reply):
    raw = base64.b64decode(reply["png_base64"], validate=True)
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")
    assert hashlib.sha256(raw).hexdigest() == reply["png_sha256"]
    pos, compressed, kinds = 8, bytearray(), []
    while pos < len(raw):
        size = struct.unpack(">I", raw[pos:pos + 4])[0]
        kind = raw[pos + 4:pos + 8]
        payload = raw[pos + 8:pos + 8 + size]
        crc = struct.unpack(">I", raw[pos + 8 + size:pos + 12 + size])[0]
        assert crc == zlib.crc32(kind + payload) & 0xFFFFFFFF
        kinds.append(kind)
        if kind == b"IHDR":
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            assert (depth, color, compression, filtering, interlace) == (8, 0, 0, 0, 0)
        if kind == b"IDAT":
            compressed += payload
        pos += size + 12
    assert kinds == [b"IHDR", b"IDAT", b"IEND"]
    pixels = zlib.decompress(compressed)
    assert len(pixels) == height * (width + 1)
    assert all(pixels[y * (width + 1)] == 0 for y in range(height))
    return width, height, pixels


class ViewerControls(unittest.TestCase):
    def test_png_exact_counts_and_fixed_absolute_scale(self):
        e = episode(units=19)
        values = [0, 1, 2, 3, 15, 16, 2**31 - 1]
        e["session"]["queries"][0]["spikes"][0][:len(values)] = values
        s = session(e)
        reply = s.dispatch(view_request(e))
        w, h, pixels = decode_png(reply)
        self.assertEqual((w, h), (5104, 418))
        self.assertEqual(reply["half_open_interval_ms"], [500, 5000])
        self.assertIsNone(reply["support_label"])
        for col, count in enumerate(values):
            gray = 255 - min(224, 16 * count.bit_length())
            # A background pixel away from the integer annotation is an exact
            # independent check of absolute, not query-normalized, color.
            self.assertEqual(pixels[(viewer.TOP + 1) * (w + 1) + 1 + viewer.LEFT + col * viewer.CELL_W + 1], gray)
        last = s.dispatch(view_request(e, unit_start=18, unit_stop=19, bin_start=89, bin_stop=90))
        self.assertEqual(last["half_open_interval_ms"], [4950, 5000])
        self.assertEqual(last["unit_indices"], [18, 19])
        self.assertEqual(last["bin_indices"], [89, 90])
        decode_png(last)

    def test_maximum_int32_all_ten_digits_fit_without_clipping(self):
        e = episode(units=1)
        e["session"]["queries"][0]["spikes"][0][0] = 2**31 - 1
        reply = session(e).dispatch(view_request(e, bin_stop=1))
        w, _, pixels = decode_png(reply)
        # Independently inspect every white glyph pixel of the actual integer.
        for idx, digit in enumerate("2147483647"):
            for yy, line in enumerate(viewer._GLYPHS[digit].split("/")):
                for xx, bit in enumerate(line):
                    if bit == "1":
                        x, y = viewer.LEFT + 2 + idx * 5 + xx, viewer.TOP + 5 + yy
                        self.assertLess(x, viewer.LEFT + viewer.CELL_W - 1)
                        self.assertEqual(pixels[y * (w + 1) + 1 + x], 255)

    def test_complete_support_is_optional_and_query_has_no_numeric_signal_reply(self):
        e = episode()
        s = session(e)
        info = s.dispatch({"action": "describe"})
        self.assertEqual({k: len(v) for k, v in info["case_ids"].items()}, {"calibration": 16, "development": 8, "queries": 10})
        self.assertTrue(info["support_views_optional"])
        self.assertEqual(info["documentation_utf8"], e["documentation_utf8"])
        for split in ("calibration", "development"):
            reply = s.dispatch(view_request(e, split))
            self.assertEqual(reply["support_label"], {k: e["session"][split][0][k] for k in ("count", "high")})
        query = s.dispatch(view_request(e))
        self.assertEqual(query["media_type"], "image/png")
        self.assertNotIn("spikes", query)
        self.assertIsNone(query["support_label"])
        # A participant may answer without any support or query-view action.
        self.assertEqual(len(complete(session(e), e)["response"]["records"]), 10)

    def test_only_complete_first_final_answers_finish_and_negative_values_are_preserved(self):
        e = episode()
        s = session(e)
        cid = e["session"]["queries"][0]["case_id"]
        s.dispatch({"action": "answer", "case_id": cid, "count": -4.25})
        with self.assertRaisesRegex(ValueError, "first-final"):
            s.dispatch({"action": "answer", "case_id": cid, "count": 10})
        with self.assertRaisesRegex(ValueError, "every protected query"):
            s.dispatch({"action": "finish"})
        for row in e["session"]["queries"][1:]:
            s.dispatch({"action": "answer", "case_id": row["case_id"], "count": 7})
        response = s.dispatch({"action": "finish"})["response"]
        self.assertEqual(response["records"][0]["count"], -4.25)
        self.assertEqual(response["episode_sha256"], boundary.digest(e))
        self.assertEqual(response["participant_packet_sha256"], e["participant_packet_sha256"])
        boundary.validate_candidate_records(e, response["records"])
        with self.assertRaisesRegex(ValueError, "already finalized"):
            s.dispatch({"action": "describe"})

    def test_nonfinite_boolean_and_non_numeric_predictions_rejected(self):
        e = episode()
        s = session(e)
        cid = e["session"]["queries"][0]["case_id"]
        for value in (True, False, float("inf"), float("nan"), "3", None, 10**400):
            with self.subTest(value=type(value).__name__), self.assertRaises(ValueError):
                s.dispatch({"action": "answer", "case_id": cid, "count": value})
        s.dispatch({"action": "answer", "case_id": cid, "count": 0})

    def test_closed_actions_forbid_paths_code_and_other_session_or_split(self):
        e = episode()
        s = session(e)
        invalid = [{"action": "execute", "code": "print(1)"}, {"action": "describe", "path": "/owner"},
                   view_request(e, case_id=opaque("NOT_THIS_SESSION")),
                   view_request(e, split="calibration", case_id=e["session"]["queries"][0]["case_id"]),
                   {"action": "answer", "case_id": e["session"]["calibration"][0]["case_id"], "count": 0}]
        for request in invalid:
            with self.assertRaises(ValueError):
                s.dispatch(request)

    def test_viewports_cannot_invent_unobserved_bins_or_drop_declared_geometry(self):
        e = episode()
        s = session(e)
        for kwargs in ({"bin_start": -10}, {"bin_stop": 91}, {"bin_stop": 0}, {"unit_stop": 3},
                       {"unit_start": True}, {"bin_start": 0.5}, {"unit_start": 1, "unit_stop": 1}):
            with self.assertRaises(ValueError):
                s.dispatch(view_request(e, **kwargs))
        e["session"]["queries"][0]["spikes"][0].pop()
        with self.assertRaisesRegex(ValueError, "every observed"):
            session(e)

    def test_injected_query_label_wrong_document_and_cross_condition_pin_rejected(self):
        e = episode()
        wrong = copy.deepcopy(e)
        wrong["session"]["queries"][0]["count"] = 8
        with self.assertRaisesRegex(ValueError, "closed episode"):
            session(wrong)
        wrong = copy.deepcopy(e)
        wrong["documentation_utf8"] += "physical delivery verified"
        with self.assertRaisesRegex(ValueError, "identical public documentation"):
            session(wrong)
        other = episode("full_calibration")
        with self.assertRaisesRegex(ValueError, "externally pinned"):
            viewer.Session(other, boundary.digest(e), boundary_directory=SOURCE)

    def test_operator_input_and_audit_return_mutations_do_not_rewrite_session(self):
        e = episode()
        s = session(e)
        request = view_request(e)
        before = s.dispatch(request)["png_sha256"]
        e["session"]["queries"][0]["spikes"][0][0] = 999
        self.assertEqual(before, s.dispatch(request)["png_sha256"])
        audit = s.operator_audit()
        audit["events"][0]["request"]["case_id"] = "REWRITTEN"
        self.assertNotEqual(s.operator_audit()["events"][0]["request"]["case_id"], "REWRITTEN")

    def test_hash_chain_recomputes_and_explicitly_does_not_claim_isolation(self):
        e = episode()
        s = session(e)
        s.dispatch({"action": "describe"})
        final = complete(s, e)
        self.assertFalse(final["scientific_qualification"])
        self.assertFalse(final["process_isolation_verified"])
        audit = s.operator_audit()
        prior = viewer._sha(viewer._canonical({"schema": viewer.SCHEMA, "episode_sha256": boundary.digest(e),
                                               "boundary_sha256": viewer.BOUNDARY_SHA256}))
        for seq, event in enumerate(audit["events"]):
            self.assertEqual(event["previous_sha256"], prior)
            self.assertEqual(event["sequence"], seq)
            payload = {k: v for k, v in event.items() if k != "event_sha256"}
            prior = viewer._sha(viewer._canonical(payload))
            self.assertEqual(prior, event["event_sha256"])
        self.assertEqual(prior, audit["final_chain_sha256"])
        self.assertTrue(audit["closed"])
        self.assertFalse(audit["rejected_actions_recorded"])

    def test_altered_boundary_is_refused_before_execution(self):
        global TEMP_WRITTEN_BYTES
        e = episode()
        with tempfile.TemporaryDirectory() as tmp:
            data = b"raise RuntimeError('must not execute')\n"
            (Path(tmp) / "episode_boundary.py").write_bytes(data)
            TEMP_WRITTEN_BYTES += len(data)
            with self.assertRaisesRegex(ValueError, "pinned APCx"):
                viewer.Session(e, boundary.digest(e), boundary_directory=tmp)

    def test_generated_complete86_episode_outputs_join_original_assembler(self):
        packets, responses = {}, {}
        support_totals = {}
        for condition in boundary.CONDITIONS:
            es = [episode(condition, i, units=9 if i < 39 else 8,
                          query_count=52 if i < 6 else 51, full_cal=151 if i < 32 else 150, full_dev=50)
                  for i in range(43)]
            packet = {"schema": "apcx-deposited-label-participant-v1", "profile": boundary.PROFILE,
                      "profile_contract_sha256": boundary.CONTRACT, "condition": condition,
                      "documentation_utf8": es[0]["documentation_utf8"], "documentation_sha256": boundary.DOCUMENT,
                      "sessions": sorted((e["session"] for e in es), key=lambda s: s["session_id"]), "invented": True}
            packets[condition] = packet
            support_totals[condition] = {k: sum(len(s[k]) for s in packet["sessions"]) for k in viewer.SPLITS}
            for e in boundary.from_public_packet(packet):
                responses[(condition, e["session"]["session_id"])] = complete(session(e), e)["response"]
        self.assertEqual(support_totals, {"matched": {"calibration": 688, "development": 344, "queries": 2199},
                                          "full_calibration": {"calibration": 6482, "development": 2150, "queries": 2199}})
        self.assertEqual(len(responses), 86)
        # Empty ordinary filenames exercise the real complete path-set check;
        # only the JSON-read transport is replaced with generated memory bodies.
        # No owner documents, source arrays or scientific predictions are read.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            for condition in boundary.CONDITIONS:
                (root / condition).mkdir()
            for condition, sid in responses:
                (root / condition / (sid + ".json")).touch()
            def read(path, budget, maximum):
                return copy.deepcopy(responses[(Path(path).parent.name, Path(path).stem)])
            with mock.patch.object(predecessor, "read_json", side_effect=read):
                joined = predecessor.complete_responses(root, packets, predecessor.budget())
            self.assertEqual(set(joined), set(boundary.CONDITIONS))
            self.assertEqual([len(joined[c]) for c in boundary.CONDITIONS], [43, 43])
            for c in boundary.CONDITIONS:
                self.assertEqual(sum(len(r["records"]) for r in joined[c].values()), 2199)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(ViewerControls))
    print(json.dumps({"generated_only": True, "authentic_arrays_read": False, "native_model_fits": 0,
                      "temporary_written_bytes": TEMP_WRITTEN_BYTES, "methods": result.testsRun,
                      "success": result.wasSuccessful()}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
