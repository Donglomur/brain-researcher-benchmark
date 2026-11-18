"""Live owned-leader regression; no scientific input or remote participant."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import transport as t
import test_transport as fixture_helpers


RECEIPTS = []


class LiveUnknownCleanupControls(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        path = os.environ.get("HELSINKI_LIVE_CLEANUP_PROOF_PATH")
        if path:
            body = (json.dumps({"schema": "generated-live-unknown-cleanup-v1",
                "scope": "Two owned generated hung leaders; no model or authentic data.",
                "receipts": RECEIPTS}, indent=2) + "\n").encode()
            assert len(body) <= 8192
            target = Path(path); assert not target.exists(); target.write_bytes(body)

    def check_live_unknown(self, persistent):
        owner, _, _, packets = fixture_helpers.fixture()
        real_killpg = os.killpg
        injected = []
        def unavailable_group(pgid, sig):
            if sig == 0 and (persistent or not injected):
                injected.append(pgid)
                raise PermissionError("generated unavailable group observation")
            return real_killpg(pgid, sig)
        with tempfile.TemporaryDirectory(prefix="helsinki-live-unknown-") as root:
            with patch.object(t.os, "killpg", side_effect=unavailable_group):
                with self.assertRaises(t.TransportError) as raised:
                    t.run_case(owner, packets[0], argv=fixture_helpers.command("hang_before", 0),
                        limits=dict(fixture_helpers.LIMITS, wall_seconds=1), scratch_root=root)
            error = raised.exception
            self.assertEqual(error.code, "participant_deadline")
            receipt = error.evidence
            cleanup = receipt["cleanup"]
            self.assertTrue(cleanup["group_probe_unavailable"])
            self.assertTrue(cleanup["leader_termination_requested"])
            self.assertTrue(cleanup["leader_reaped"])
            self.assertFalse(cleanup["termination_requested"])
            self.assertIsNone(cleanup["leader_termination_error"])
            self.assertEqual(cleanup["owned_group_absent"], not persistent)
            self.assertFalse(receipt["collector_committed"])
            self.assertTrue(receipt["scratch_removed"])
            self.assertEqual(owner._rows, [])
            self.assertEqual(list(Path(root).iterdir()), [])
            self.assertLess(receipt["wall_seconds"], 1.2)
            with self.assertRaises(t.collector.CollectionError): owner.finish()
            # Independent post-fixture observation; do not rewrite the transport's
            # truthful unknown group result when observation was unavailable.
            with self.assertRaises(ProcessLookupError): real_killpg(receipt["pid"], 0)
            RECEIPTS.append({"persistent_unknown": persistent,
                "injected_probe_count": len(injected),
                "lifecycle": fixture_helpers.compact(receipt),
                "post_fixture_group_absent_observed": True})

    def test_persistently_unknown_group_still_reaps_owned_live_leader_without_claiming_group_absence(self):
        self.check_live_unknown(True)

    def test_transient_unknown_group_reaps_owned_live_leader_and_observes_later_absence(self):
        self.check_live_unknown(False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
