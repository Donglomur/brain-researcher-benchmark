"""Generated portable-builder controls; no original EEG or demo bodies are read."""
from __future__ import annotations
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import time
import types
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load("portable_erp_builder", "builder.py")
recipe = load("portable_erp_recipe", "recipe.py")


def budget():
    return builder.Budget(time.monotonic() + 30)


def generated_inputs():
    return {
        "schema": "erp-core-full32-packet-inputs-v1",
        "condition_id": builder.CONDITION,
        "people": 32,
        "queries": 6400,
        "metadata_census": {"bytes": 1, "sha256": builder.CENSUS_SHA},
        "participants": [
            {"participant_id": person,
             "metadata": {"bytes": 1, "sha256": "0" * 64},
             "summary": {"stimuli": 200, "targets": 40, "nontargets": 160,
                         "channels": 33, "sample_rate_hz": 1024, "samples": 2048},
             "fdt": {"basename": person + "_task-P3_eeg.fdt",
                     "source_path": person + "/eeg/" + person + "_task-P3_eeg.fdt",
                     "bytes": 2048 * 33 * 4, "sha256": "1" * 64}}
            for person in builder.PEOPLE
        ],
    }


class PortableBuilderControls(unittest.TestCase):
    def test_cli_has_explicit_external_inputs_without_private_selection(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as caught:
            builder.cli(["--help"])
        self.assertEqual(caught.exception.code, 0)
        help_text = output.getvalue()
        for flag in ("--inputs", "--metadata-root", "--fdt-root", "--demonstrations",
                     "--prompt", "--response-schema", "--key", "--output"):
            self.assertIn(flag, help_text)
        for flag in ("--selection", "--acquisition-receipt", "--grant", "--recipe"):
            self.assertNotIn(flag, help_text)
        self.assertEqual(builder.descriptor((HERE / "recipe.py").read_bytes()), builder.RECIPE_PIN)

    def test_full32_descriptor_cannot_select_a_subset_or_other_census(self):
        value = generated_inputs()
        self.assertEqual(len(builder.check_inputs(value)), 32)
        for mutate in (lambda v: v["participants"].pop(),
                       lambda v: v["participants"].reverse(),
                       lambda v: v["participants"][0]["summary"].update(stimuli=199),
                       lambda v: v["metadata_census"].update(sha256="0" * 64),
                       lambda v: v["participants"][0]["fdt"].update(bytes=4)):
            changed = copy.deepcopy(value)
            mutate(changed)
            with self.assertRaises(builder.Refusal):
                builder.check_inputs(changed)

    def test_metadata_retains_source_anchors_and_targets_without_filtering(self):
        row = generated_inputs()["participants"][0]
        events = [{"event_code": 11 if i % 5 == 0 else 12,
                   "released_anchor_0based": 256 + i,
                   "set_latency_1based": 257 + i, "tsv_sample": 257 + i,
                   "target": int(i % 5 == 0)} for i in range(200)]
        meta = {"participant_id": row["participant_id"],
                "status": "metadata_admitted_signal_unread", "summary": row["summary"],
                "external_data": {"basename": row["fdt"]["basename"],
                                  "manifest_declared_bytes": row["fdt"]["bytes"]},
                "events_operator_only": events, "stimuli_operator_only": copy.deepcopy(events)}
        self.assertEqual(builder.validate_metadata(meta, row), events)
        for mutate in (lambda m: m["stimuli_operator_only"].pop(),
                       lambda m: m["stimuli_operator_only"][0].update(released_anchor_0based=282),
                       lambda m: m["stimuli_operator_only"][0].update(target=0)):
            changed = copy.deepcopy(meta)
            mutate(changed)
            with self.assertRaises(builder.Refusal):
                builder.validate_metadata(changed, row)

    def test_fdt_hash_layout_and_all_channel_finite_gate(self):
        # One generated 1024-sample source is 135,168 bytes, not a full corpus.
        samples = np.arange(1024 * 33, dtype=np.float32).reshape(1024, 33)
        with tempfile.TemporaryDirectory(prefix="erp-builder-source-") as directory:
            path = Path(directory) / "generated.fdt"
            body = samples.astype("<f4").tobytes()
            path.write_bytes(body)
            pin = builder.descriptor(body)
            raw, checks = builder.read_epochs(path, pin, {"samples": 1024},
                [{"released_anchor_0based": 256}], [0], budget(), np)
            self.assertEqual(checks, 165)
            np.testing.assert_array_equal(raw[0], samples.T)
            self.assertEqual(raw.shape, (1, 33, 1024))
            with self.assertRaisesRegex(builder.Refusal, "Complete FDT source hash"):
                builder.read_epochs(path, {**pin, "sha256": "0" * 64}, {"samples": 1024},
                    [{"released_anchor_0based": 256}], [0], budget(), np)
            # HEOG is not an output channel, but nonfinite source values must refuse.
            samples[500, 30] = np.nan
            changed = samples.astype("<f4").tobytes()
            path.write_bytes(changed)
            with self.assertRaisesRegex(builder.Refusal, "Nonfinite source amplitude"):
                builder.read_epochs(path, builder.descriptor(changed), {"samples": 1024},
                    [{"released_anchor_0based": 256}], [0], budget(), np)

    def test_exact_recipe_reference_baseline_and_full_geometry(self):
        self.assertEqual(sys.version_info[:3], (3, 11, 6))
        self.assertEqual(np.__version__, "1.26.3")
        raw = np.empty((200, 33, 1024), dtype=np.float32)
        times = np.arange(1024, dtype=np.float32)
        for person in range(200):
            for channel in range(33):
                raw[person, channel] = person / 2 + channel / 4 + times * ((channel + 1) / 1024)
        actual = recipe.transform(raw)
        self.assertEqual(actual.shape, (200, 2, 1024))
        self.assertEqual(actual.dtype, np.dtype("float64"))
        p9, p10 = (recipe.CHANNELS.index(x) for x in ("P9", "P10"))
        for person in (0, 37, 199):
            for out, name in enumerate(("Cz", "Pz")):
                channel = recipe.CHANNELS.index(name)
                def referenced(sample):
                    return float(raw[person, channel, sample]) - (
                        float(raw[person, p9, sample]) + float(raw[person, p10, sample])) / 2
                baseline = math.fsum(referenced(i) for i in range(256)) / 256
                for sample in (0, 255, 256, 1023):
                    self.assertEqual(actual[person, out, sample], referenced(sample) - baseline)

    def test_reference_promotes_before_sum_and_refuses_partial_nonfinite_epochs(self):
        raw = np.zeros((200, 33, 1024), dtype=np.float32)
        raw[:, recipe.CHANNELS.index("P9"), :] = np.float32(3e38)
        raw[:, recipe.CHANNELS.index("P10"), :] = np.float32(3e38)
        with np.errstate(over="raise", invalid="raise"):
            actual = recipe.transform(raw)
        self.assertTrue(np.isfinite(actual).all())
        for invalid in (raw[:199], raw.astype(np.float64)):
            with self.assertRaises(ValueError):
                recipe.transform(invalid)
        raw[0, 30, 0] = np.nan
        with self.assertRaises(ValueError):
            recipe.transform(raw)

    def test_serialization_preserves_all_binary64_values_and_signed_zero(self):
        values = np.linspace(-2.0, 2.0, 2048, dtype=np.float64).reshape(2, 1024)
        values[0, 0] = -0.0
        values[0, 1] = np.nextafter(0.0, 1.0)
        values[1, -1] = np.nextafter(1.0, 2.0)
        body, error = recipe.record_bytes("q-" + "a" * 32, values)
        parsed = json.loads(body)
        self.assertEqual(set(parsed), {"trial_id", "channels"})
        restored = np.asarray(parsed["channels"], dtype=np.float64)
        self.assertEqual(restored.shape, (2, 1024))
        np.testing.assert_array_equal(restored.view(np.uint64), values.view(np.uint64))
        self.assertEqual(error, 0.0)
        self.assertTrue(np.signbit(restored[0, 0]))
        self.assertLessEqual(len(body), 60000)

    def test_opaque_ids_depend_on_secret_and_kind_without_source_labels(self):
        key = bytes(range(32))
        ids = [builder.opaque_id(key, "query", person, 256 + i)
               for person in builder.PEOPLE for i in range(200)]
        self.assertEqual(len(set(ids)), 6400)
        self.assertTrue(all(len(x) == 34 and x.startswith("q-") and "sub-" not in x for x in ids))
        self.assertNotEqual(ids[0], builder.opaque_id(b"x" * 32, "query", builder.PEOPLE[0], 256))
        self.assertNotEqual(ids[0], builder.opaque_id(key, "person", builder.PEOPLE[0], 256))

    def test_actual_manifest_expression_sorts_and_excludes_private_members(self):
        tree = ast.parse((HERE / "builder.py").read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "build")
        statements = [n for n in ast.walk(function) if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "public_files" for t in n.targets)]
        self.assertEqual(len(statements), 1)
        code = compile(ast.fix_missing_locations(ast.Module(body=statements, type_ignores=[])),
                       "<actual-builder-manifest-expression>", "exec")
        members = [("public/queries/p-z.jsonl", {"bytes": 1, "sha256": "a" * 64}),
                   ("private/PARTICIPANT_JOIN.json", {"secret": "not-for-participants"}),
                   ("public/queries/p-a.jsonl", {"bytes": 1, "sha256": "b" * 64}),
                   ("public/demonstrations.json", {"bytes": 1, "sha256": "c" * 64})]
        results = []
        for order in (members, list(reversed(members))):
            namespace = {"out": types.SimpleNamespace(files=dict(order))}
            exec(code, namespace)
            results.append(namespace["public_files"])
        self.assertEqual(list(results[0]), sorted(results[0]))
        self.assertEqual(builder.encoded(results[0]), builder.encoded(results[1]))
        self.assertTrue(all(not x.startswith("private/") for x in results[0]))
        self.assertNotIn(b"not-for-participants", builder.encoded(results[0]))

    def test_invalid_external_descriptor_refuses_before_creating_output(self):
        with tempfile.TemporaryDirectory(prefix="erp-builder-refusal-") as directory:
            parent = Path(directory)
            inputs = parent / "inputs.json"
            body = builder.encoded({**generated_inputs(), "queries": 400})
            inputs.write_bytes(body)
            output = parent / "must-stay-absent"
            with self.assertRaises(builder.Refusal):
                builder.build(inputs, builder.descriptor(body), parent, parent,
                    parent / "absent-demos", output, time.monotonic() + 30,
                    prompt_path=parent / "absent-prompt", response_schema_path=parent / "absent-schema",
                    key_path=parent / "absent-key", key_pin={"bytes": 32, "sha256": "0" * 64})
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
