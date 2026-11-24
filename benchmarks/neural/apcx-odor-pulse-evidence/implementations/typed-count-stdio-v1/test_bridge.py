"""Generated-only request/response controls on the real bridge entrypoint."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SOURCE = Path(os.environ.get("APCX_IMPLEMENTATIONS_ROOT", str(HERE.parent)))
sys.path.insert(0, str(HERE))
import bridge
sys.path.insert(0, str(SOURCE / "typed-count-viewer-v1"))
import test_viewer as fixtures

TEMP_WRITTEN_BYTES = 0


class BridgeControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.episode = fixtures.episode()

    def complete(self):
        return [{"action": "answer", "case_id": row["case_id"], "count": -2.5}
                for row in self.episode["session"]["queries"]] + [{"action": "finish"}]

    def run_bridge(self, requests, *, episode=None, pin=None, source=SOURCE):
        global TEMP_WRITTEN_BYTES
        episode = self.episode if episode is None else episode
        body = bridge.canonical(episode)
        path = self.root / "episode.json"
        path.write_bytes(body)
        TEMP_WRITTEN_BYTES += len(body)
        pin = hashlib.sha256(body).hexdigest() if pin is None else pin
        incoming = requests if type(requests) is bytes else b"".join(map(bridge.canonical, requests))
        outgoing, errors = io.BytesIO(), io.BytesIO()
        code = bridge.main(["--episode", str(path), "--episode-sha256", pin,
                            "--source-root", str(source)], incoming=io.BytesIO(incoming),
                           outgoing=outgoing, errors=errors)
        return code, [json.loads(line) for line in outgoing.getvalue().splitlines()], errors.getvalue()

    def test_complete_typed_channel_keeps_existing_response_envelope(self):
        requests = [{"action": "describe"}, fixtures.view_request(self.episode),
                    fixtures.view_request(self.episode, "calibration")] + self.complete()
        code, replies, errors = self.run_bridge(requests)
        self.assertEqual(code, 0)
        self.assertEqual(errors, b"")
        self.assertEqual(replies[0]["observed_interval_ms"], [500, 5000])
        self.assertNotIn("spikes", replies[1])
        self.assertIsNone(replies[1]["support_label"])
        fixtures.decode_png(replies[1])
        self.assertIsNotNone(replies[2]["support_label"])
        final = replies[-1]
        self.assertFalse(final["process_isolation_verified"])
        self.assertFalse(final["scientific_qualification"])
        response = final["response"]
        self.assertEqual(response["episode_sha256"], fixtures.boundary.digest(self.episode))
        self.assertEqual(response["participant_packet_sha256"], self.episode["participant_packet_sha256"])
        fixtures.boundary.validate_candidate_records(self.episode, response["records"])
        self.assertTrue(all(row["count"] == -2.5 for row in response["records"]))

    def test_rejected_requests_are_visible_and_do_not_finalize_or_consume_answers(self):
        cid = self.episode["session"]["queries"][0]["case_id"]
        raw = (b'{"action":"describe","action":"finish"}\n' +
               b'{"action":"answer","case_id":"' + cid.encode() + b'","count":NaN}\n' +
               b'\xff\n' + bridge.canonical({"action": "finish"}) +
               bridge.canonical({"action": "execute", "path": "/owner/secret"}) +
               b"".join(map(bridge.canonical, self.complete())))
        code, replies, errors = self.run_bridge(raw)
        self.assertEqual(code, 0)
        self.assertEqual(errors, b"")
        self.assertEqual([reply["code"] for reply in replies[:5]], ["invalid_request"] * 5)
        self.assertNotIn("/owner/secret", json.dumps(replies))
        self.assertEqual(replies[-1]["schema"], "apcx-viewer-finish-v1")

    def test_first_final_answer_cannot_be_rewritten_over_the_channel(self):
        first = self.complete()[0]
        code, replies, _ = self.run_bridge([first, {**first, "count": 900}] + self.complete()[1:])
        self.assertEqual(code, 0)
        self.assertEqual(replies[1]["code"], "invalid_request")
        self.assertEqual(replies[-1]["response"]["records"][0]["count"], -2.5)

    def test_eof_without_complete_finish_has_no_successful_response(self):
        code, replies, errors = self.run_bridge(self.complete()[:-2])
        self.assertEqual(code, 2)
        self.assertEqual(errors, b"")
        self.assertEqual(replies[-1]["code"], "incomplete_eof")
        self.assertFalse(any("response" in reply for reply in replies))

    def test_oversized_or_unterminated_request_never_succeeds(self):
        for raw, last_code in ((b" " * (bridge.MAX_REQUEST_BYTES + 1), "request_too_large"),
                               (b'{"action":"finish"}', "incomplete_eof")):
            with self.subTest(last_code=last_code):
                code, replies, _ = self.run_bridge(raw)
                self.assertEqual(code, 2)
                self.assertEqual(replies[-1]["code"], last_code)
                self.assertFalse(any("response" in reply for reply in replies))

    def test_wrong_pin_and_query_target_injection_refused_before_channel(self):
        injected = copy.deepcopy(self.episode)
        injected["session"]["queries"][0]["count"] = 8
        for episode, pin in ((self.episode, "0" * 64), (injected, None)):
            with self.subTest(injected=episode is injected):
                code, replies, errors = self.run_bridge(self.complete(), episode=episode, pin=pin)
                self.assertEqual(code, 2)
                self.assertEqual(replies, [])
                self.assertEqual(json.loads(errors)["code"], "operator_input_refused")

    def test_changed_viewer_is_refused_before_code_executes(self):
        global TEMP_WRITTEN_BYTES
        folder = self.root / "typed-count-viewer-v1"
        folder.mkdir()
        body = b"raise RuntimeError('untrusted source executed')\n"
        (folder / "viewer.py").write_bytes(body)
        TEMP_WRITTEN_BYTES += len(body)
        code, replies, errors = self.run_bridge(self.complete(), source=self.root)
        self.assertEqual(code, 2)
        self.assertEqual(replies, [])
        self.assertEqual(json.loads(errors)["code"], "operator_input_refused")

    def test_nonordinary_episode_path_is_refused(self):
        path = self.root / "alias.json"
        path.symlink_to(self.root / "absent.json")
        with self.assertRaises(ValueError):
            bridge.read_episode(path)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BridgeControls))
    print(json.dumps({"generated_only": True, "authentic_inputs_read": False,
                      "temporary_written_bytes": TEMP_WRITTEN_BYTES,
                      "tests": result.testsRun, "passed": result.wasSuccessful()}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
