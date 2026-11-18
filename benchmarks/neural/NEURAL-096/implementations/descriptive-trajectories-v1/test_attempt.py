"""Generated boundaries only; no authentic data, renderer, model or grading."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import zlib

import attempt


GENERATED_DISK_CEILING = 1024 * 1024


def generated_inputs():
    """All 48 groups, 54 units, 20 bins; 27 supported and 21 unsupported."""
    cells, observation_cells = [], []
    for i, identifier in enumerate(attempt.IDS):
        split = "train" if i < 24 else "val"
        long = short = 1 if i < 27 else 0
        if i == 0:
            long += 102
        elif i == 24:
            long += 47
        elif i == 27:
            long = 1  # One-sided unsupported validation group, as in real support.
        row = {"cell_id": identifier, "source_split": split, "observation_segment": (i % 24)//4,
               "is_eye": bool((i % 4)//2), "theta": (i % 2)*180, "n_long": long, "n_short": short,
               "supported": bool(long and short),
               "missing_priors": [name for name, n in (("long", long), ("short", short)) if not n]}
        cells.append({**row, "svg": "viewer/cells/" + identifier + ".svg"})
        observation_cells.append({**row,
                                  "long_rate_hz": [[0]*20 for _ in range(54)] if long else None,
                                  "short_rate_hz": [[0]*20 for _ in range(54)] if short else None})
    index = {"schema": "neural096-typed-svg-index/v1", "method": attempt.METHOD,
             "unit_ids": list(range(54)), "phase_bins": 20,
             "quarter_bin_slices": [[0, 5], [5, 10], [10, 15], [15, 20]],
             "rate_units": "spikes/s/source unit", "display_rate_max_hz": 1.0,
             "cells": cells, "precision": copy.deepcopy(attempt.PRECISION), "scope": attempt.SCOPE}
    observations = {key: copy.deepcopy(index[key]) for key in
                    ("method", "unit_ids", "phase_bins", "quarter_bin_slices", "rate_units", "display_rate_max_hz")}
    observations.update(schema="neural096-matched-prior-mean-observations/v1", cells=observation_cells,
                        information_condition="matched_prior_specific_aggregate_trajectories", limits=list(attempt.LIMITS))
    index_body, observation_body = attempt.encode(index), attempt.encode(observations)
    binding = {"observation_manifest_sha256": "a"*64,
               "observation_sha256": hashlib.sha256(observation_body).hexdigest(),
               "preparation_completion_sha256": "b"*64,
               "index_sha256": hashlib.sha256(index_body).hexdigest()}
    return index, observations, index_body, observation_body, binding


def chunk(kind, payload):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)


def generated_png():
    # Full declared dimensions. Raster semantics are tested by the separate
    # renderer work, while these controls exercise unchanged PNG-byte custody.
    pixels = (b"\x00" + b"\xff"*(1360*3))*1180
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1360, 1180, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(pixels, 9)) + chunk(b"IEND", b""))


def config(identifier, **limits):
    return {"attempt_id": identifier, "max_requests": 64,
            "instruction_sha256": "d"*64, "answer_contract_sha256": "e"*64,
            "max_response_bytes": 384 * 1024**2, "max_final_answer_bytes": attempt.MAX_ANSWER, **limits}


class AdapterControls(unittest.TestCase):
    """Reuse one read-only material pair; charge every write, including restores."""
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="neural096-generated-attempt-")
        cls.root = Path(cls.temporary.name).resolve()
        cls.index, cls.observations, cls.index_body, cls.observation_body, cls.binding = generated_inputs()
        cls.png = generated_png()
        sanitized = attempt.sanitize_index(cls.index_body)
        native_binding = {**cls.binding, "renderer_manifest_sha256": "c"*64}
        native_files = {"INDEX.json": attempt.pin(sanitized),
                        **{"cells/" + key + ".png": attempt.pin(cls.png) for key in attempt.IDS}}
        programme_files = {"INDEX.json": attempt.pin(sanitized), "observations.json": attempt.pin(cls.observation_body)}
        native_manifest = attempt.encode(attempt._material_manifest("native", native_binding, native_files, sanitized))
        programme_manifest = attempt.encode(attempt._material_manifest("programme", cls.binding, programme_files, sanitized))
        cls.planned_material_write_bytes = (49*len(cls.png) + 2*len(sanitized) + len(cls.observation_body)
                                           + len(native_manifest) + len(programme_manifest))
        # A strict reserve covers all small attempts, event/final receipts,
        # deliberate corruptions/restores and the one PNG restore control.
        if cls.planned_material_write_bytes + 256*1024 > GENERATED_DISK_CEILING:
            raise AssertionError("full material pair plus control-write reserve exceeds generated grant")
        cls.written_bytes = 0
        cls.real_write = attempt.write_new
        def counted(path, body):
            cls.written_bytes += len(body)
            if cls.written_bytes > GENERATED_DISK_CEILING:
                raise AssertionError("generated cumulative disk budget exceeded")
            cls.real_write(path, body)
        cls.write_patch = mock.patch.object(attempt, "write_new", counted)
        cls.write_patch.start()
        cls.png_source = cls.root / "source.png"
        counted(cls.png_source, cls.png)
        sources = {key: {"path": str(cls.png_source), **attempt.pin(cls.png)} for key in attempt.IDS}
        cls.native = cls.root / "native"
        cls.programme = cls.root / "programme"
        cls.native_result = attempt.materialize_native(cls.index_body, sources, native_binding, cls.native)
        cls.programme_result = attempt.materialize_programme(cls.index_body, cls.observation_body, cls.binding, cls.programme)
        cls.sequence = 0

    @classmethod
    def tearDownClass(cls):
        cls.write_patch.stop()
        cls.temporary.cleanup()

    @classmethod
    def attempt_for(cls, arm="native", **limits):
        cls.sequence += 1
        output = cls.root / f"attempt-{cls.sequence}"
        material = cls.native if arm == "native" else cls.programme
        result = cls.native_result if arm == "native" else cls.programme_result
        made = attempt.create_attempt(material, result["material_manifest"]["sha256"], config(f"generated_{cls.sequence}", **limits), output)
        return output, made["attempt_manifest"]["sha256"], material

    def replace(self, path, body):
        # Explicitly count temporary corruptions and restoration writes too.
        type(self).written_bytes += len(body)
        self.assertLessEqual(type(self).written_bytes, GENERATED_DISK_CEILING)
        path.write_bytes(body)

    def test_material_roots_are_separate_complete_and_observation_only(self):
        self.assertEqual(set(p.name for p in self.native.iterdir()), {"INDEX.json", "MATERIAL.json", "cells"})
        self.assertEqual(set(p.name for p in self.programme.iterdir()), {"INDEX.json", "MATERIAL.json", "observations.json"})
        self.assertEqual(len(list((self.native / "cells").iterdir())), 48)
        self.assertEqual((self.native / "INDEX.json").read_bytes(), (self.programme / "INDEX.json").read_bytes())
        index = attempt.decode((self.native / "INDEX.json").read_bytes())
        self.assertEqual(sum(row["supported"] for row in index["cells"]), 27)
        self.assertEqual(len(index["unit_ids"]), 54)
        self.assertEqual(index["phase_bins"], 20)
        self.assertEqual(index["cells"][27]["missing_priors"], ["short"])
        self.assertEqual(index["cells"][27]["n_long"], 1)
        self.assertIsNotNone(self.observations["cells"][27]["long_rate_hz"])
        self.assertIsNone(self.observations["cells"][27]["short_rate_hz"])
        for row in index["cells"]:
            self.assertEqual(set(row), attempt.CELL_KEYS)
            self.assertNotIn("svg", row)
            self.assertNotIn("long_rate_hz", row)
        self.assertEqual((self.programme / "observations.json").read_bytes(), self.observation_body)
        for root in (self.native, self.programme):
            self.assertNotIn(str(self.root), (root / "MATERIAL.json").read_text())

    def test_native_png_and_shared_index_programme_exact_bytes(self):
        native, ns, nr = self.attempt_for()
        programme, ps, pr = self.attempt_for("programme")
        left = attempt.request_observation(nr, native, ns, {"kind": "index"})
        right = attempt.request_observation(pr, programme, ps, {"kind": "index"})
        self.assertEqual(left["body"], right["body"])
        image = attempt.request_observation(nr, native, ns, {"kind": "view", "cell_id": attempt.IDS[47]})
        self.assertEqual(image["content_type"], "image/png")
        self.assertEqual(image["body"], self.png)
        numeric = attempt.request_observation(pr, programme, ps, {"kind": "observations"})
        self.assertEqual(numeric["content_type"], "application/json")
        self.assertEqual(numeric["body"], self.observation_body)
        self.assertEqual(set(image), {"content_type", "body", "event_receipt"})
        self.assertNotIn(str(self.root), attempt.encode(image["event_receipt"]).decode())

    def test_wrong_arm_unknown_and_path_selectors_read_no_material(self):
        root, sha, material = self.attempt_for()
        requests = [{"kind": "observations"}, {"kind": "exec", "code": "print(1)"},
                    {"kind": "view", "cell_id": "../observations.json"},
                    {"kind": "view", "cell_id": "/etc/passwd"},
                    {"kind": "view", "cell_id": attempt.IDS[0], "path": "private"},
                    {"kind": "index", "extra": "hidden"}]
        original = attempt.read_body
        def read(path, maximum, **kwargs):
            self.assertFalse(Path(path).is_relative_to(material), "invalid selector touched material")
            return original(path, maximum, **kwargs)
        with mock.patch.object(attempt, "read_body", read):
            for request in requests:
                with self.subTest(request=request), self.assertRaises(attempt.AttemptError):
                    attempt.request_observation(material, root, sha, request)
        self.assertEqual(len(list((root / "events").iterdir())), len(requests))
        programme, ps, pr = self.attempt_for("programme")
        with self.assertRaisesRegex(attempt.AttemptError, "wrong_arm_request"):
            attempt.request_observation(pr, programme, ps, {"kind": "view", "cell_id": attempt.IDS[0]})

    def test_wrong_material_and_attempt_pins_refused(self):
        root, sha, material = self.attempt_for()
        with self.assertRaisesRegex(attempt.AttemptError, "attempt_manifest_identity"):
            attempt.request_observation(material, root, "0"*64, {"kind": "index"})
        with self.assertRaisesRegex(attempt.AttemptError, "material_manifest_identity"):
            attempt.request_observation(self.programme, root, sha, {"kind": "view", "cell_id": attempt.IDS[0]})
        with self.assertRaises(attempt.AttemptError):
            attempt.create_attempt(material, "0"*64, config("wrong_pin"), self.root / "wrong_pin")

    def test_request_and_response_caps_precede_payload_reads(self):
        root, sha, material = self.attempt_for(max_requests=1)
        attempt.request_observation(material, root, sha, {"kind": "index"})
        with self.assertRaisesRegex(attempt.AttemptError, "request_budget"):
            attempt.request_observation(material, root, sha, {"kind": "index"})
        limited, ls, lm = self.attempt_for(max_response_bytes=1)
        original = attempt.read_body
        def read(path, maximum, **kwargs):
            self.assertNotEqual(Path(path), lm / "INDEX.json", "budget refusal read index payload")
            return original(path, maximum, **kwargs)
        with mock.patch.object(attempt, "read_body", read), self.assertRaisesRegex(attempt.AttemptError, "response_budget"):
            attempt.request_observation(lm, limited, ls, {"kind": "index"})
        final = attempt.submit_final(limited, ls, b"{}")
        self.assertEqual(final["receipt"]["observation_log"]["events"], 1)
        self.assertEqual(final["receipt"]["observation_log"]["charged_bytes"], 0)

    def test_final_is_one_capture_bound_to_input_and_observation_log(self):
        root, sha, material = self.attempt_for()
        attempt.request_observation(material, root, sha, {"kind": "view", "cell_id": attempt.IDS[0]})
        captured = attempt.submit_final(root, sha, b'{"candidate":"generated"}\n')
        verified = attempt.verify_final(root, sha, captured["receipt_pin"]["sha256"])
        self.assertEqual(verified["receipt_pin"], captured["receipt_pin"])
        self.assertEqual(verified["answer_bytes"], b'{"candidate":"generated"}\n')
        self.assertEqual(verified["receipt"]["attempt_manifest"]["sha256"], sha)
        self.assertEqual(verified["manifest"]["observation_manifest_sha256"], self.binding["observation_manifest_sha256"])
        for key in attempt.INSTRUCTION_FIELDS:
            self.assertEqual(verified["receipt"][key], verified["manifest"]["config"][key])
        self.assertEqual(verified["receipt"]["observation_log"], verified["log"])
        self.assertEqual(verified["log"]["events"], 1)
        with self.assertRaisesRegex(attempt.AttemptError, "attempt_sealed"):
            attempt.submit_final(root, sha, b"different")
        with self.assertRaisesRegex(attempt.AttemptError, "attempt_sealed"):
            attempt.request_observation(material, root, sha, {"kind": "index"})

    def test_malformed_final_is_captured_without_grader_feedback(self):
        root, sha, _ = self.attempt_for("programme")
        result = attempt.submit_final(root, sha, b"not valid JSON")
        self.assertEqual(result["receipt"]["status"], "captured")
        self.assertFalse(result["receipt"]["grading_feedback_provided"])
        self.assertEqual(attempt.get_final(root, sha, result["receipt_pin"]["sha256"])["answer_bytes"], b"not valid JSON")

    def test_size_rejected_final_is_terminal_without_large_disk_write(self):
        root, sha, material = self.attempt_for(max_final_answer_bytes=8)
        result = attempt.submit_final(root, sha, b"123456789")
        self.assertEqual(result["receipt"]["status"], "rejected")
        self.assertFalse((root / "ANSWER.bin").exists())
        with self.assertRaises(attempt.AttemptError):
            attempt.verify_final(root, sha, result["receipt_pin"]["sha256"])
        with self.assertRaisesRegex(attempt.AttemptError, "attempt_sealed"):
            attempt.submit_final(root, sha, b"{}")
        with self.assertRaisesRegex(attempt.AttemptError, "attempt_sealed"):
            attempt.request_observation(material, root, sha, {"kind": "index"})

    def test_partial_final_and_tampered_answer_fail_closed(self):
        root, sha, material = self.attempt_for()
        attempt.write_new(root / "ANSWER.bin", b"partial")
        with self.assertRaisesRegex(attempt.AttemptError, "attempt_sealed"):
            attempt.submit_final(root, sha, b"{}")
        with self.assertRaises(attempt.AttemptError):
            attempt.verify_final(root, sha, "0"*64)
        completed, cs, _ = self.attempt_for()
        captured = attempt.submit_final(completed, cs, b"original")
        self.replace(completed / "ANSWER.bin", b"changed!")
        with self.assertRaisesRegex(attempt.AttemptError, "file_integrity"):
            attempt.verify_final(completed, cs, captured["receipt_pin"]["sha256"])

    def test_final_and_attempt_commitment_mutations_are_detected(self):
        root, sha, _ = self.attempt_for()
        captured = attempt.submit_final(root, sha, b"{}")
        final_sha = captured["receipt_pin"]["sha256"]
        final_path = root / "FINAL.json"
        original = final_path.read_bytes()
        changed = attempt.decode(original)
        changed["observation_manifest_sha256"] = "0"*64
        self.replace(final_path, attempt.encode(changed))
        with self.assertRaises(attempt.AttemptError):
            attempt.verify_final(root, sha, final_sha)
        self.replace(final_path, original)
        altered_instruction = attempt.decode(original)
        altered_instruction["instruction_sha256"] = "0"*64
        self.replace(final_path, attempt.encode(altered_instruction))
        with self.assertRaises(attempt.AttemptError):
            attempt.verify_final(root, sha, final_sha)
        self.replace(final_path, original)
        manifest_path = root / "ATTEMPT.json"
        altered = attempt.decode(manifest_path.read_bytes())
        altered["arm"] = "programme"
        self.replace(manifest_path, attempt.encode(altered))
        with self.assertRaisesRegex(attempt.AttemptError, "attempt_manifest_identity"):
            attempt.verify_final(root, sha, final_sha)

    def test_coherent_replacement_refused_by_independent_final_pin_before_payload_reads(self):
        root, sha, material = self.attempt_for()
        attempt.request_observation(material, root, sha, {"kind": "index"})
        captured = attempt.submit_final(root, sha, b"original")
        final_sha = captured["receipt_pin"]["sha256"]
        final_path, answer_path = root / "FINAL.json", root / "ANSWER.bin"
        event_path = root / "events/000001.json"
        original_final, original_event = final_path.read_bytes(), event_path.read_bytes()
        original_read = attempt.read_body
        def read(path, maximum, **kwargs):
            self.assertNotEqual(Path(path), answer_path, "changed final read answer bytes")
            self.assertFalse(Path(path).is_relative_to(root / "events"), "changed final read journal")
            return original_read(path, maximum, **kwargs)
        changed = attempt.decode(original_final)
        changed["answer"] = attempt.pin(b"replacement")
        self.replace(answer_path, b"replacement")
        self.replace(final_path, attempt.encode(changed))
        with mock.patch.object(attempt, "read_body", read), self.assertRaisesRegex(attempt.AttemptError, "final_receipt_identity"):
            attempt.verify_final(root, sha, final_sha)
        self.replace(answer_path, b"original")
        event = attempt.decode(original_event)
        event["response"]["sha256"] = "0"*64
        changed_event = attempt.encode(event)
        changed = attempt.decode(original_final)
        changed["observation_log"]["head_sha256"] = attempt.pin(changed_event)["sha256"]
        self.replace(event_path, changed_event)
        self.replace(final_path, attempt.encode(changed))
        with mock.patch.object(attempt, "read_body", read), self.assertRaisesRegex(attempt.AttemptError, "final_receipt_identity"):
            attempt.verify_final(root, sha, final_sha)

    def test_event_reorder_truncation_and_extra_files_are_refused(self):
        root, sha, material = self.attempt_for()
        for _ in range(2):
            attempt.request_observation(material, root, sha, {"kind": "index"})
        captured = attempt.submit_final(root, sha, b"{}")
        final_sha = captured["receipt_pin"]["sha256"]
        first, second = root / "events/000001.json", root / "events/000002.json"
        a, b = first.read_bytes(), second.read_bytes()
        self.replace(first, b)
        self.replace(second, a)
        with self.assertRaises(attempt.AttemptError):
            attempt.verify_final(root, sha, final_sha)
        self.replace(first, a)
        self.replace(second, b)
        second.unlink()
        with self.assertRaises(attempt.AttemptError):
            attempt.verify_final(root, sha, final_sha)
        attempt.write_new(second, b)
        extra = root / "private_answer.json"
        attempt.write_new(extra, b"no")
        with self.assertRaises(attempt.AttemptError):
            attempt.verify_final(root, sha, final_sha)

    def test_extra_symlink_and_missing_material_entries_fail_closed(self):
        root, sha, material = self.attempt_for()
        extra = material / "private_answer.json"
        attempt.write_new(extra, b"no")
        try:
            with self.assertRaises(attempt.AttemptError):
                attempt.request_observation(material, root, sha, {"kind": "index"})
        finally:
            extra.unlink()
        image = material / "cells" / (attempt.IDS[0] + ".png")
        body = image.read_bytes()
        image.unlink()
        try:
            with self.assertRaises(attempt.AttemptError):
                attempt.request_observation(material, root, sha, {"kind": "index"})
            image.symlink_to(self.png_source)
            with self.assertRaises(attempt.AttemptError):
                attempt.request_observation(material, root, sha, {"kind": "view", "cell_id": attempt.IDS[0]})
            image.unlink()
        finally:
            if image.is_symlink():
                image.unlink()
            if not image.exists():
                attempt.write_new(image, body)

    def test_selected_material_mutation_and_aliasing_do_not_leak(self):
        settings = config("mutable_config")
        destination = self.root / "mutable_config_attempt"
        made = attempt.create_attempt(self.native, self.native_result["material_manifest"]["sha256"], settings, destination)
        sha = made["attempt_manifest"]["sha256"]
        settings["max_requests"] = 0
        settings["instruction_sha256"] = "0"*64
        result = attempt.request_observation(self.native, destination, sha, {"kind": "index"})
        result["event_receipt"]["response"]["sha256"] = "0"*64
        captured = attempt.submit_final(destination, sha, b"{}")
        final_sha = captured["receipt_pin"]["sha256"]
        self.assertEqual(attempt.verify_final(destination, sha, final_sha)["log"]["events"], 1)
        self.assertEqual(attempt.verify_final(destination, sha, final_sha)["manifest"]["instruction_sha256"], "d"*64)
        image = self.native / "cells" / (attempt.IDS[0] + ".png")
        original = image.read_bytes()
        self.replace(image, original[:-1] + bytes([original[-1] ^ 1]))
        root, rs, material = self.attempt_for(max_requests=2)
        try:
            for _ in range(2):
                with self.assertRaisesRegex(attempt.AttemptError, "file_integrity"):
                    attempt.request_observation(material, root, rs, {"kind": "view", "cell_id": attempt.IDS[0]})
            with self.assertRaisesRegex(attempt.AttemptError, "request_budget"):
                attempt.request_observation(material, root, rs, {"kind": "view", "cell_id": attempt.IDS[0]})
        finally:
            self.replace(image, original)
        failed = attempt.submit_final(root, rs, b"{}")
        verified = attempt.verify_final(root, rs, failed["receipt_pin"]["sha256"])
        self.assertEqual(verified["log"]["events"], 2)
        self.assertEqual(verified["log"]["charged_bytes"], 0)

    def test_regular_file_hardlink_fifo_and_oversize_bounds(self):
        path = self.root / "ordinary-small"
        attempt.write_new(path, b"safe")
        self.assertEqual(attempt.read_body(path, 4), b"safe")
        with self.assertRaises(attempt.AttemptError):
            attempt.read_body(path, 3)
        link = self.root / "linked-small"
        os.link(path, link)
        try:
            with self.assertRaises(attempt.AttemptError):
                attempt.read_body(path, 4)
        finally:
            link.unlink()
        pipe = self.root / "generated-fifo"
        os.mkfifo(pipe)
        try:
            with self.assertRaises(attempt.AttemptError):
                attempt.read_body(pipe, 4)
        finally:
            pipe.unlink()
        real_fstat = os.fstat
        def oversized(fd):
            st = real_fstat(fd)
            return SimpleNamespace(st_mode=st.st_mode, st_nlink=1, st_size=attempt.MAX_PNG + 1)
        with mock.patch.object(attempt.os, "fstat", oversized), self.assertRaises(attempt.AttemptError):
            attempt.read_body(path, attempt.MAX_PNG)

    def test_sanitized_index_rejects_extra_hidden_reordered_and_alias_fields(self):
        mutations = []
        for kind in ("top", "rates", "path", "order", "bool_count", "precision", "unit_type", "scale_overflow", "support_count"):
            data = copy.deepcopy(self.index)
            if kind == "top":
                data["private_reference"] = [42]
            elif kind == "rates":
                data["cells"][0]["long_rate_hz"] = [[42]]
            elif kind == "path":
                data["cells"][0]["svg"] = "../private/answer.svg"
            elif kind == "order":
                data["cells"][0], data["cells"][1] = data["cells"][1], data["cells"][0]
            elif kind == "bool_count":
                data["cells"][0]["n_short"] = True
            elif kind == "precision":
                data["precision"]["viewer"] = "/operator/private/path"
            elif kind == "unit_type":
                data["unit_ids"][0] = []
            elif kind == "scale_overflow":
                data["display_rate_max_hz"] = 10**400
            else:
                data["cells"][27].update(n_long=0, missing_priors=["long", "short"])
                data["cells"][28].update(n_long=1, n_short=1, supported=True, missing_priors=[])
                data["cells"][24]["n_long"] -= 1
            mutations.append(data)
        for i, data in enumerate(mutations):
            with self.subTest(mutation=i), self.assertRaises(attempt.AttemptError):
                attempt.sanitize_index(attempt.encode(data))
        original = copy.deepcopy(self.index)
        sanitized = attempt.decode(attempt.sanitize_index(attempt.encode(original)))
        sanitized["cells"][0]["n_long"] = 0
        self.assertEqual(original["cells"][0]["n_long"], 103)

    def test_png_contract_rejects_wrong_dimensions_metadata_crc_and_trailing_content(self):
        attempt.validate_png(self.png)
        wrong = (self.png[:8] + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + self.png[33:])
        ancillary = self.png[:-12] + chunk(b"tEXt", b"private=answer") + self.png[-12:]
        broken_crc = self.png[:-1] + bytes([self.png[-1] ^ 1])
        for data in (wrong, ancillary, broken_crc, self.png + b"private", b"<svg>not PNG</svg>", self.png[:8], self.png[:33]):
            with self.subTest(bytes=len(data)), self.assertRaises(attempt.AttemptError):
                attempt.validate_png(data)

    def test_input_parser_bounds_and_per_attempt_nonce(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'not json'):
            with self.assertRaises(attempt.AttemptError):
                attempt.decode(raw)
        first, fs, _ = self.attempt_for()
        second, ss, _ = self.attempt_for()
        self.assertNotEqual(fs, ss)
        self.assertNotEqual(attempt.decode((first / "ATTEMPT.json").read_bytes())["attempt_nonce"],
                            attempt.decode((second / "ATTEMPT.json").read_bytes())["attempt_nonce"])
        with self.assertRaises(attempt.AttemptError):
            attempt.create_attempt(self.native, self.native_result["material_manifest"]["sha256"], config("reuse"), first)
        with self.assertRaises(attempt.AttemptError):
            attempt.create_attempt(self.native, self.native_result["material_manifest"]["sha256"], config("nested"), self.native / "attempt")

    def test_operator_io_error_does_not_expose_filesystem_path(self):
        root, sha, material = self.attempt_for()
        (root / "LOCK").unlink()
        with self.assertRaises(attempt.AttemptError) as caught:
            attempt.request_observation(material, root, sha, {"kind": "index"})
        self.assertEqual(str(caught.exception), "operator_io_failure")
        self.assertNotIn(str(root), str(caught.exception))
        backend, bs, bm = self.attempt_for(max_requests=1)
        error = PermissionError(13, "permission denied", "/operator/private/observations.json")
        with mock.patch.object(attempt, "_material", side_effect=error), self.assertRaises(attempt.AttemptError) as caught:
            attempt.request_observation(bm, backend, bs, {"kind": "index"})
        self.assertEqual(str(caught.exception), "operator_io_failure")
        event = attempt.decode((backend / "events/000001.json").read_bytes())
        self.assertEqual(event["reason"], "observation_integrity_or_io_failure")
        self.assertNotIn("/operator/private", attempt.encode(event).decode())
        with self.assertRaisesRegex(attempt.AttemptError, "request_budget"):
            attempt.request_observation(bm, backend, bs, {"kind": "index"})
        captured = attempt.submit_final(backend, bs, b"{}")
        self.assertEqual(attempt.verify_final(backend, bs, captured["receipt_pin"]["sha256"])["log"]["events"], 1)

    def test_z_generated_cumulative_write_budget(self):
        self.assertLessEqual(type(self).written_bytes, GENERATED_DISK_CEILING)
        self.assertEqual(GENERATED_DISK_CEILING, 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
