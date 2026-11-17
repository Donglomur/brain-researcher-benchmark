"""Generated standard-library controls; no EEG or model responses are used."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


d = load(HERE / "delivery.py", "complete_delivery_test")
response = load(HERE.parent / "direct-response/portable/response_contract.py", "response_test")


def fixture():
    ids = [f"{case}-{i:024x}" for case in d.CASES for i in range(200)]
    manifest = {"development_ids": ids, "query_count": 400,
                "demonstration_count": 4, "natural_class_prior_supplied": False}
    members = {"manifest.json": d.encoded(manifest),
               "queries.jsonl": b"".join(d.encoded({"trial_id": i, "channels": [[0], [1]]}) for i in ids),
               "demonstrations.json": b'[{"generated":true}]\n',
               "prompt.txt": (d.NO_TOOLS + "\n{{demonstrations_json}}\n{{query_json}}\n").encode(),
               "response_schema.json": b"{}\n"}
    return members


def envelopes(contexts):
    return [{"ordinal": r["ordinal"], "trial_id": r["trial_id"],
             "context_sha256": r["context_sha256"], "status": "ok", "error": None,
             "response": json.dumps({"trial_id": r["trial_id"], "target_probability": 0.25})}
            for r in contexts]


def ledger(rows):
    return b"".join(d.encoded(r) for r in rows)


class Portable(unittest.TestCase):
    def setUp(self):
        self.members = fixture()
        self.contexts = list(d.context_rows(self.members, d.CONDITIONS[0]))
        self.rows = envelopes(self.contexts)

    def test_all400_and_only_permission_sentence_differs(self):
        matched = list(d.context_rows(self.members, d.CONDITIONS[1]))
        self.assertEqual(len(self.contexts), 400)
        for left, right in zip(self.contexts, matched):
            self.assertEqual(left["trial_id"], right["trial_id"])
            self.assertEqual(left["prompt"].replace(d.NO_TOOLS, d.PROGRAMME_TOOLS), right["prompt"])
            self.assertEqual(hashlib.sha256(right["prompt"].encode()).hexdigest(), right["context_sha256"])

    def test_reordered_complete_panel(self):
        self.assertEqual(d.response_values(ledger(self.rows[::-1]), self.contexts, response), [0.25] * 400)

    def test_omitted_or_duplicate_attempt(self):
        with self.assertRaises(ValueError):
            d.response_values(ledger(self.rows[:-1]), self.contexts, response)
        self.rows[-1] = self.rows[0]
        with self.assertRaises(ValueError):
            d.response_values(ledger(self.rows), self.contexts, response)

    def test_request_body_identity_cannot_be_swapped(self):
        self.rows[0]["response"], self.rows[1]["response"] = self.rows[1]["response"], self.rows[0]["response"]
        with self.assertRaisesRegex(ValueError, "Exact current query identity"):
            d.response_values(ledger(self.rows), self.contexts, response)

    def test_wrong_context_or_condition(self):
        self.rows[0]["context_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "context mismatch"):
            d.response_values(ledger(self.rows), self.contexts, response)
        matched = list(d.context_rows(self.members, d.CONDITIONS[1]))
        with self.assertRaises(ValueError):
            d.response_values(ledger(envelopes(matched)), self.contexts, response)

    def test_transport_error_is_not_a_prediction(self):
        self.rows[200].update(status="error", error="generated timeout", response=None)
        with self.assertRaisesRegex(ValueError, "attempted query failed"):
            d.response_values(ledger(self.rows), self.contexts, response)

    def test_invalid_scalar_duplicate_fields_extra_prose(self):
        for value in (True, -0.1, 1.1, float("nan")):
            with self.subTest(value=value):
                self.rows[0]["response"] = json.dumps({"trial_id": self.rows[0]["trial_id"],
                                                     "target_probability": value})
                with self.assertRaises(ValueError):
                    d.response_values(ledger(self.rows), self.contexts, response)
        for body in ('{"trial_id":"a","trial_id":"b","target_probability":0.2}',
                     'Here is my answer: {}', '{}'):
            self.rows[0]["response"] = body
            with self.assertRaises(ValueError):
                d.response_values(ledger(self.rows), self.contexts, response)

    def test_boolean_ordinal_and_duplicate_envelope_fields(self):
        self.rows[0]["ordinal"] = False
        with self.assertRaises(ValueError):
            d.response_values(ledger(self.rows), self.contexts, response)
        self.rows = envelopes(self.contexts)
        raw = ledger(self.rows).replace(b'"ordinal":0,', b'"ordinal":0,"ordinal":0,', 1)
        with self.assertRaises(ValueError):
            d.response_values(raw, self.contexts, response)

    def test_substituted_roster_and_incomplete_packet(self):
        manifest = json.loads(self.members["manifest.json"])
        manifest["development_ids"][0] = "wrong-person"
        self.members["manifest.json"] = d.encoded(manifest)
        with self.assertRaises(ValueError):
            list(d.context_rows(self.members, d.CONDITIONS[0]))
        self.members = fixture()
        self.members["queries.jsonl"] = self.members["queries.jsonl"].split(b"\n", 1)[1]
        with self.assertRaises(ValueError):
            list(d.context_rows(self.members, d.CONDITIONS[0]))

    def test_pinned_reader_rejects_tamper_link_and_oversize(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "ordinary"
            p.write_bytes(b"original")
            pin = d.descriptor(b"original")
            self.assertEqual(d.pinned(p, pin), b"original")
            p.write_bytes(b"modified")
            with self.assertRaises(ValueError):
                d.pinned(p, pin)
            with self.assertRaises(ValueError):
                d.read_regular(p, 1)
            link = Path(tmp) / "link"
            link.symlink_to(p)
            with self.assertRaises(OSError):
                d.read_regular(link, 100)


if __name__ == "__main__":
    unittest.main()
