"""Additional invented provider-MD5 and HTTP-original integrity controls.

No fixture is authentic release metadata. Every byte provider is injected offline;
these tests neither download archives nor establish a scientific reproduction.
"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from archive_intake import acquire
from retina_contract import ARCHIVES, DATA_COMMIT, DATA_DOI, Refusal
from test_retina_construction import Response

H = "a" * 64


class ProviderMD5Controls(unittest.TestCase):
    def provider_manifest(self, payload=b"abc"):
        import hashlib
        from provider_md5 import LAST_CHANGE_COMMIT
        md5 = hashlib.md5(payload, usedforsecurity=False).hexdigest()
        return {"schema": "retina-provider-md5-intake-v1", "data_doi": DATA_DOI,
                "data_commit": DATA_COMMIT, "last_change_commit": LAST_CHANGE_COMMIT,
                "provider_metadata_sha256": H,
                "archives": [{"name": name, "bytes": len(payload), "provider_md5": md5,
                              "git_annex_key": f"MD5-s{len(payload)}--{md5}",
                              "metadata_evidence_sha256": H} for name in ARCHIVES]}

    def provider_case(self, body=b"abc", response_factory=None, headers=None):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        output = Path(t.name).resolve() / "provider-out"
        calls = []
        def opener(url, seconds):
            calls.append(url)
            return response_factory(url) if response_factory else Response(url, body, headers=headers)
        return output, calls, lambda: acquire(self.provider_manifest(), str(output), 10, opener)

    def test_54_all18_provider_md5_canonical(self):
        from provider_md5 import validate_provider_md5_manifest
        m = self.provider_manifest()
        m["archives"].reverse()
        p = validate_provider_md5_manifest(m)
        self.assertEqual([x["name"] for x in p["archives"]], list(ARCHIVES))
        self.assertEqual(p["total_archive_bytes"], 54)
        self.assertFalse(p["metadata_authority_verified"])
        self.assertFalse(p["provider_sha256_available"])

    def test_55_provider_nonhex_md5_refuses(self):
        from provider_md5 import validate_provider_md5_manifest
        m = self.provider_manifest()
        m["archives"][0]["provider_md5"] = "x" * 32
        with self.assertRaisesRegex(Refusal, "md5"):
            validate_provider_md5_manifest(m)

    def test_56_provider_key_size_mismatch_refuses(self):
        from provider_md5 import validate_provider_md5_manifest
        m = self.provider_manifest()
        m["archives"][0]["bytes"] = 4
        with self.assertRaisesRegex(Refusal, "key_size_or_digest"):
            validate_provider_md5_manifest(m)

    def test_57_provider_key_digest_mismatch_refuses(self):
        from provider_md5 import validate_provider_md5_manifest
        m = self.provider_manifest()
        m["archives"][0]["provider_md5"] = "a" * 32
        with self.assertRaisesRegex(Refusal, "key_size_or_digest"):
            validate_provider_md5_manifest(m)

    def test_58_provider_missing_archive_refuses(self):
        from provider_md5 import validate_provider_md5_manifest
        m = self.provider_manifest()
        m["archives"].pop()
        with self.assertRaisesRegex(Refusal, "all18"):
            validate_provider_md5_manifest(m)

    def test_59_provider_duplicate_archive_refuses(self):
        from provider_md5 import validate_provider_md5_manifest
        m = self.provider_manifest()
        m["archives"][-1] = copy.deepcopy(m["archives"][0])
        with self.assertRaisesRegex(Refusal, "duplicate"):
            validate_provider_md5_manifest(m)

    def test_60_provider_sha256_cannot_be_invented(self):
        from provider_md5 import validate_provider_md5_manifest
        m = self.provider_manifest()
        m["archives"][0]["sha256"] = H
        with self.assertRaisesRegex(Refusal, "schema"):
            validate_provider_md5_manifest(m)

    def test_61_provider_evidence_missing_refuses(self):
        from provider_md5 import validate_provider_md5_manifest
        m = self.provider_manifest()
        m["provider_metadata_sha256"] = None
        with self.assertRaisesRegex(Refusal, "sha256"):
            validate_provider_md5_manifest(m)

    def test_62_md5_verified_local_sha256_observed_all18(self):
        output, calls, run = self.provider_case()
        r = run()
        self.assertEqual(len(calls), 18)
        self.assertEqual(r["successfully_written_bytes"], 54)
        self.assertTrue(r["provider_digest_verified"])
        self.assertFalse(r["provider_sha256_available"])
        for row in r["attempted_archives"]:
            self.assertTrue(row["complete"])
            self.assertTrue(row["provider_digest_verified"])
            self.assertEqual(row["written_sha256"], hashlib.sha256(b"abc").hexdigest())
            self.assertEqual(row["written_md5"], hashlib.md5(b"abc", usedforsecurity=False).hexdigest())
            self.assertEqual(row["unretained_observed_bytes"], 0)

    def test_63_md5_failure_keeps_received_bytes_no_retry(self):
        output, calls, run = self.provider_case(body=b"abd")
        with self.assertRaises(Refusal):
            run()
        r = json.loads((output / "RECEIPT.json").read_text())
        self.assertEqual(r["error"]["message"], "body:provider_md5")
        self.assertEqual((output / ARCHIVES[0]).read_bytes(), b"abd")
        self.assertEqual(r["attempted_archives"][0]["written_sha256"], hashlib.sha256(b"abd").hexdigest())
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(r["not_attempted"]), 17)

    def test_64_provider_short_body_partial_retained(self):
        output, calls, run = self.provider_case(body=b"ab")
        with self.assertRaises(Refusal):
            run()
        r = json.loads((output / "RECEIPT.json").read_text())
        self.assertEqual(r["error"]["message"], "body:short")
        self.assertEqual((output / ARCHIVES[0]).read_bytes(), b"ab")
        self.assertFalse(r["attempted_archives"][0]["provider_digest_verified"])
        self.assertEqual(len(calls), 1)

    def test_65_overflow_sentinel_retained_and_hashed(self):
        output, calls, run = self.provider_case(body=b"abcd")
        with self.assertRaises(Refusal):
            run()
        r = json.loads((output / "RECEIPT.json").read_text())
        row = r["attempted_archives"][0]
        self.assertEqual(r["error"]["message"], "body:overflow")
        self.assertEqual((output / ARCHIVES[0]).read_bytes(), b"abcd")
        self.assertEqual(row["observed_bytes"], 4)
        self.assertEqual(row["written_bytes"], 4)
        self.assertEqual(row["written_sha256"], hashlib.sha256(b"abcd").hexdigest())
        self.assertEqual(row["unretained_observed_bytes"], 0)
        self.assertEqual(len(calls), 1)

    def test_66_incomplete_read_partial_bytes_preserved(self):
        import http.client
        class Partial(Response):
            def read(self, n):
                raise http.client.IncompleteRead(b"ab", 1)
        output, calls, run = self.provider_case(response_factory=lambda url: Partial(url))
        with self.assertRaises(Refusal):
            run()
        r = json.loads((output / "RECEIPT.json").read_text())
        row = r["attempted_archives"][0]
        self.assertEqual(r["error"]["message"], "body:incomplete_read")
        self.assertEqual((output / ARCHIVES[0]).read_bytes(), b"ab")
        self.assertEqual(row["incomplete_read_partial_retained"], 2)
        self.assertEqual(row["written_sha256"], hashlib.sha256(b"ab").hexdigest())
        self.assertFalse(r["failed_read_prefix_bytes_unmeasured"])
        self.assertEqual(len(calls), 1)

    def test_67_wrong_provider_last_change_refuses(self):
        from provider_md5 import validate_provider_md5_manifest
        m = self.provider_manifest()
        m["last_change_commit"] = "a" * 40
        with self.assertRaisesRegex(Refusal, "last_change"):
            validate_provider_md5_manifest(m)

    def test_68_provider_url_override_refuses(self):
        from provider_md5 import validate_provider_md5_manifest
        m = self.provider_manifest()
        m["archives"][0]["url"] = "https://example.invalid/override"
        with self.assertRaisesRegex(Refusal, "schema"):
            validate_provider_md5_manifest(m)

    def test_69_noncanonical_annex_keys_refuse(self):
        from provider_md5 import validate_provider_md5_manifest
        for prefix in ("SHA256-s3--", "MD5-s03--", "md5-s3--"):
            m = self.provider_manifest()
            m["archives"][0]["git_annex_key"] = prefix + m["archives"][0]["provider_md5"]
            with self.subTest(prefix=prefix), self.assertRaisesRegex(Refusal, "key_size_or_digest"):
                validate_provider_md5_manifest(m)

    def test_70_complete_http_header_originals_preserved(self):
        output, calls, run = self.provider_case(headers=[("Content-Length", "3"), ("X-Example", "invented")])
        r = run()
        self.assertEqual(len(calls), 18)
        for row in r["attempted_archives"]:
            pin = row["http_original"]
            b = (output / pin["name"]).read_bytes()
            self.assertEqual(len(b), pin["bytes"])
            self.assertEqual(hashlib.sha256(b).hexdigest(), pin["sha256"])
            h = json.loads(b)
            self.assertEqual(h["status"], 200)
            self.assertEqual(h["requested_url"], h["final_url"])
            self.assertIn(["X-Example", "invented"], h["headers"])

    def test_71_disk_admission_prevents_network(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as t:
            out = Path(t).resolve() / "out"
            calls = []
            with patch("archive_intake.shutil.disk_usage", return_value=SimpleNamespace(free=0)):
                with self.assertRaises(Refusal):
                    acquire(self.provider_manifest(), str(out), 10,
                            lambda u, s: calls.append(u), minimum_free_bytes=1)
            r = json.loads((out / "RECEIPT.json").read_text())
            self.assertEqual(calls, [])
            self.assertEqual(len(r["not_attempted"]), 18)
            self.assertEqual(r["error"]["message"], "disk:remaining_all18_capacity")

    def test_72_header_custody_ceiling_prevents_body_read(self):
        output, calls, run = self.provider_case(headers=[("X-Too-Large", "x" * 300000)])
        with self.assertRaises(Refusal):
            run()
        r = json.loads((output / "RECEIPT.json").read_text())
        self.assertEqual(r["error"]["message"], "http:header_custody_ceiling")
        self.assertEqual(r["observed_entity_bytes"], 0)
        self.assertEqual((output / ARCHIVES[0]).read_bytes(), b"")
        self.assertEqual(len(calls), 1)

    def observed_http_pins(self, output):
        rows = []
        for name in ARCHIVES:
            p = output / (name + ".http.json")
            b = p.read_bytes()
            rows.append({"name": p.name, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()})
        return rows

    def test_73_mutated_unallowlisted_header_original_refuses(self):
        from http_original_integrity import verify_http_original_bindings
        output, calls, run = self.provider_case(headers=[("Content-Length", "3"), ("X-Example", "original")])
        receipt = run()
        self.assertTrue(verify_http_original_bindings(receipt["attempted_archives"],
                                                     self.observed_http_pins(output), ARCHIVES))
        p = output / (ARCHIVES[0] + ".http.json")
        h = json.loads(p.read_text())
        before = (h["requested_url"], h["final_url"], h["status"], h["headers"][0])
        h["headers"][1][1] = "tampered"
        p.write_text(json.dumps(h, sort_keys=True) + "\n")
        self.assertEqual(before, (h["requested_url"], h["final_url"], h["status"], h["headers"][0]))
        with self.assertRaisesRegex(ValueError, "header_original_binding"):
            verify_http_original_bindings(receipt["attempted_archives"], self.observed_http_pins(output), ARCHIVES)
        self.assertEqual((output / ARCHIVES[0]).read_bytes(), b"abc")
        self.assertEqual(len(calls), 18)

    def test_74_missing_http_receipt_pin_refuses(self):
        from http_original_integrity import verify_http_original_bindings
        output, _, run = self.provider_case()
        receipt = run()
        del receipt["attempted_archives"][0]["http_original"]
        with self.assertRaisesRegex(ValueError, "header_original_binding"):
            verify_http_original_bindings(receipt["attempted_archives"], self.observed_http_pins(output), ARCHIVES)

    def test_75_duplicate_observed_http_original_refuses(self):
        from http_original_integrity import verify_http_original_bindings
        output, _, run = self.provider_case()
        receipt = run()
        observed = self.observed_http_pins(output)
        observed[1] = copy.deepcopy(observed[0])
        with self.assertRaisesRegex(ValueError, "header_original_missing_or_duplicate"):
            verify_http_original_bindings(receipt["attempted_archives"], observed, ARCHIVES)

    def test_76_wrong_http_original_filename_refuses(self):
        from http_original_integrity import verify_http_original_bindings
        output, _, run = self.provider_case()
        receipt = run()
        receipt["attempted_archives"][0]["http_original"]["name"] = ARCHIVES[1] + ".http.json"
        with self.assertRaisesRegex(ValueError, "header_original_binding"):
            verify_http_original_bindings(receipt["attempted_archives"], self.observed_http_pins(output), ARCHIVES)
