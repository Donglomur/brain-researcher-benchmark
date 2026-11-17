"""Generated metadata controls only; no authentic events or signal are read."""
import copy
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import content_identity as ci


def descriptor(path, body, mode="120000"):
    return {"path": path, "bytes": len(body), "git_mode": mode,
            "git_object": hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()}


def pointer(size=1234, suffix=".vhdr", digest="a" * 64):
    key = f"SHA256E-s{size}--{digest}{suffix}"
    return f"../../.git/annex/objects/Z0/G1/{key}/{key}".encode()


def invented_cohort():
    rows, pointers, events = [], {}, {}
    for person in ci.PEOPLE:
        for task in ci.TASKS:
            prefix = f"{person}/eeg/{person}_task-{task}"
            row = {"subject": person, "task": task}
            for role, (_, suffix, _) in ci.ANNEX_ROLES.items():
                path = prefix + "_eeg" + suffix
                body = pointer(suffix=suffix, digest=hashlib.sha256(path.encode()).hexdigest())
                pointers[path] = body
                row[role] = descriptor(path, body)
            path = prefix + "_events.tsv"
            body = ("invented metadata body " + path).encode()
            events[path] = body
            row["events"] = descriptor(path, body, "100644")
            rows.append(row)
    return rows, pointers, events


class ContentIdentityControls(unittest.TestCase):
    def test_pinned_inventory_is_metadata_for_exact64_recordings(self):
        rows = ci.inventory_rows()
        self.assertEqual(len(ci._validated_rows(rows)), 64)
        self.assertEqual(sum(row[role]["git_mode"] == "120000"
                             for row in rows for role in ci.ANNEX_ROLES), 192)

    def test_pointer_extent_is_not_payload_extent(self):
        body = pointer(543210)
        source = descriptor("example_eeg.vhdr", body)
        result = ci.resolve_pointer(source, body, extension=".vhdr", maximum=2**20)
        self.assertEqual(result, {"path": "example_eeg.vhdr", "bytes": 543210,
                                  "sha256": "a" * 64})
        self.assertNotEqual(result["bytes"], len(body))
        self.assertNotEqual(result["sha256"], hashlib.sha256(body).hexdigest())

    def test_git_object_framing_and_body_authentication(self):
        body = pointer()
        source = descriptor("example_eeg.vhdr", body)
        wrong = dict(source, git_object=hashlib.sha1(body).hexdigest())
        with self.assertRaisesRegex(ValueError, "Git blob identity"):
            ci.authenticate_git_blob(wrong, body)
        with self.assertRaises(ValueError):
            ci.authenticate_git_blob(source, body.replace(b"aaaa", b"bbbb", 1))
        with self.assertRaises(ValueError):
            ci.authenticate_git_blob(dict(source, bytes=len(body) + 1), body)

    def test_authenticated_malformed_pointer_rejected(self):
        valid = pointer()
        malformed = [valid + b"\n", valid.replace(b"../../", b"ab/cd/"),
                     valid.replace(b"SHA256E", b"MD5E"),
                     valid.rsplit(b"/", 1)[0] + b"/wrong-key",
                     valid.replace(b"s1234", b"s01234"),
                     valid.replace(b".git/annex", b".git/../annex")]
        for body in malformed:
            with self.subTest(body=body):
                with self.assertRaises(ValueError):
                    ci.resolve_pointer(descriptor("x", body), body,
                                       extension=".vhdr", maximum=2**20)

    def test_role_size_and_mode_refusals(self):
        body = pointer()
        for suffix, maximum, mode in [(".eeg", 2**20, "120000"),
                                      (".vhdr", 1233, "120000"),
                                      (".vhdr", 2**20, "100644")]:
            with self.subTest(suffix=suffix, maximum=maximum, mode=mode):
                with self.assertRaises(ValueError):
                    ci.resolve_pointer(descriptor("x", body, mode), body,
                                       extension=suffix, maximum=maximum)

    def test_complete64_provider_selections_and_exact_event_hashes(self):
        rows, pointers, events = invented_cohort()
        with patch.object(ci, "inventory_rows", return_value=rows):
            metadata = ci.compile_metadata(pointers)
            selections = ci.compile_provider_selections(pointers, events)
        self.assertEqual(len(selections), 64)
        self.assertEqual(sum(len(r["annex_payload_pins"]) for r in metadata), 192)
        for record in selections:
            self.assertEqual(set(record), {"source_commit", "participant", "task", "files"})
            self.assertEqual(set(record["files"]), {"header", "markers", "signal", "events"})
            for pin in record["files"].values():
                self.assertEqual(set(pin), {"path", "bytes", "sha256"})
            event = record["files"]["events"]
            self.assertEqual(event["sha256"], hashlib.sha256(events[event["path"]]).hexdigest())
            self.assertEqual(record["files"]["signal"]["bytes"], 1234)

    def test_missing_extra_duplicate_or_cross_recording_inputs_refused(self):
        rows, pointers, _ = invented_cohort()
        path = next(iter(pointers))
        bad_rows = [rows[:-1], rows[:-1] + [rows[0]]]
        wrong_path = copy.deepcopy(rows)
        wrong_path[0]["header"]["path"] = rows[1]["header"]["path"]
        bad_rows.append(wrong_path)
        for records in bad_rows:
            with self.assertRaises(ValueError):
                ci._compile_metadata(records, pointers)
        for values in [{k: v for k, v in pointers.items() if k != path},
                       {**pointers, "extra": b"extra"},
                       {**pointers, path: pointers[rows[1]["header"]["path"]]}]:
            with self.assertRaises(ValueError):
                ci._compile_metadata(rows, values)

    def test_event_binding_cannot_be_replaced_by_caller_pin(self):
        rows, pointers, events = invented_cohort()
        path = next(iter(events))
        bad_events = [dict(events, **{path: events[path] + b"x"}),
                      {k: v for k, v in events.items() if k != path},
                      {**events, "extra": b"extra"}]
        with patch.object(ci, "inventory_rows", return_value=rows):
            for bodies in bad_events:
                with self.assertRaises(ValueError):
                    ci.compile_provider_selections(pointers, bodies)


if __name__ == "__main__":
    unittest.main(verbosity=2)
