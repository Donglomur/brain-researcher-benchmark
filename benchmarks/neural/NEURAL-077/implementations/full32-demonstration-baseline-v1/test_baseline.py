"""Four generated scientific controls through the frozen programme frame ABI.

No acquired EEG, released demonstrations, query packets, private targets, provider
or model is opened. Synthetic discrimination is not performance or calibration
evidence for the original task. Every programme call uses one frozen source/config
bundle, a fresh isolated Python process and exactly one complete prompt frame.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import secrets
import struct
import subprocess
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parent / "full32-paired-benchmark-v1" / "bundle.py"
BUNDLE_PIN = {"bytes": 13969, "sha256": "c78870347454935e1bc95d770ef30c1cb5b5fc516d76f5082a5bf721875291ff"}
CONSUMER = BUNDLE.parent / "consumer.py"
CONSUMER_PIN = {"bytes": 21146, "sha256": "6825dc00428b64c20cf23e1ac82068c891c4dd121fd980e0076b0ce89cb7629d"}
PROGRAMME_PERMISSION = ("Numerical tools and candidate code execution are allowed for this query. "
                        "Do not use external retrieval, other files, or memory from other query trials.")
QUERY = "q-" + "1" * 32
PREFIX = struct.Struct("!I")
PROMPT_CAP = 196608
FIXTURE_WRITE_CAP = 512 * 1024


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def ordinary(path):
    if not path.is_absolute() or ".." in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("An absolute ordinary path is required")
    return path


def bounded_read(path, cap):
    ordinary(path)
    info = path.stat()
    if not path.is_file() or info.st_nlink != 1 or not 0 < info.st_size <= cap:
        raise ValueError("A bounded singly linked source file is required")
    body = path.read_bytes()
    if len(body) != info.st_size:
        raise ValueError("Source changed during read")
    return body


class Artifacts:
    def __init__(self):
        configured = os.environ.get("ARTIFACT_DIR")
        parent = (Path(configured) if configured else Path(tempfile.gettempdir()).resolve() /
                  ("erp-template-controls-" + secrets.token_hex(8)))
        ordinary(parent)
        for source in (HERE, BUNDLE.parent, HERE.parents[4]):
            if parent.is_relative_to(source) or source.is_relative_to(parent):
                raise ValueError("ARTIFACT_DIR and authenticated source trees must be disjoint")
        parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.root = parent / "erp-four-demo-template-controls"
        self.root.mkdir(mode=0o700)  # Fresh evidence only; no overwrite or reuse.
        self.written = 0

    def emit(self, name, body):
        path = ordinary(self.root / name)
        if (not path.is_relative_to(self.root) or type(body) is not bytes or
                self.written + len(body) > FIXTURE_WRITE_CAP):
            raise ValueError("Generated artifact byte/path ceiling")
        self.written += len(body)
        with path.open("xb") as stream:
            stream.write(body)
        return pin(body)


def waveform(polarity, amplitude=1.12, phase=0.35):
    """Independent smooth synthetic traces; pulse geometry is not a feature-bin oracle."""
    channels = []
    for channel in range(2):
        values = []
        for sample in range(1024):
            noise = 0.08 * math.cos(2 * math.pi * sample / 17 + phase + channel / 3)
            signal = 0.0
            if sample >= 256:
                center = 560 + 55 * channel
                signal = polarity * amplitude * (1 - 0.35 * channel) * math.exp(-((sample - center) / 95)**2)
            values.append(round(noise + signal, 6))
        channels.append(values)
    return channels


def demonstrations():
    return [{"trial_id": "generated-demonstration-" + str(2 * target + repeat),
             "target": target, "channels": waveform(2 * target - 1, amplitude, phase)}
            for target in (0, 1) for repeat, (amplitude, phase) in enumerate(((1.0, 0.0), (1.25, 0.7)))]


def query(polarity, identifier=QUERY):
    return {"trial_id": identifier, "channels": waveform(polarity)}


def prompt(demos, item):
    # The accepted source defines JSON shapes and ordering, not prose delimiters.
    body = ("Generated source control. " + PROGRAMME_PERMISSION + "\n" +
            encoded(demos).decode() + "\n" + encoded(item).decode() +
            "\nReturn the query ID and one target_probability.").encode()
    if not 0 < len(body) <= PROMPT_CAP:
        raise ValueError("Generated complete prompt capacity exceeded")
    return body


class DemonstrationTemplateControls(unittest.TestCase):
    maxDiff = 800

    @classmethod
    def setUpClass(cls):
        source = bounded_read(BUNDLE, 131072)
        if pin(source) != BUNDLE_PIN:
            raise ValueError("Accepted frozen-programme ABI source changed")
        spec = importlib.util.spec_from_file_location("erp_template_control_bundle", BUNDLE)
        bundle = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = bundle
        exec(compile(source, str(BUNDLE), "exec", dont_inherit=True), bundle.__dict__)
        consumer_source = bounded_read(CONSUMER, 131072)
        if pin(consumer_source) != CONSUMER_PIN:
            raise ValueError("Accepted scalar response ABI source changed")
        consumer_spec = importlib.util.spec_from_file_location("erp_template_control_consumer", CONSUMER)
        cls.consumer = importlib.util.module_from_spec(consumer_spec)
        sys.modules[consumer_spec.name] = cls.consumer
        exec(compile(consumer_source, str(CONSUMER), "exec", dont_inherit=True), cls.consumer.__dict__)
        declaration = json.loads(bounded_read(HERE / "BUNDLE_MANIFEST.json", 8192))
        # Capture before any generated query is created or presented.
        cls.frozen = bundle.capture(HERE / "programme", declaration)
        client = bundle.verify(cls.frozen)
        cls.artifacts = Artifacts()
        cls.client_pin = cls.artifacts.emit("CLIENT.py", client)
        cls.client = cls.artifacts.root / "CLIENT.py"
        cls.observations = []

    @classmethod
    def tearDownClass(cls):
        body = encoded({"schema": "erp-four-demo-generated-controls-v1",
            "generated_fixture_only": True, "original_data_reads": 0, "private_target_reads": 0,
            "provider_calls": 0, "scientific_accuracy_qualified": False,
            "probability_calibration_qualified": False, "frozen_bundle": cls.frozen["bundle_identity"],
            "frozen_client": cls.client_pin, "calls": cls.observations,
            "artifact_cap": FIXTURE_WRITE_CAP, "write_charge_before_receipt": cls.artifacts.written})
        cls.artifacts.emit("OBSERVATIONS.json", body)

    def invoke(self, wire, expected_id=None, refusal=False):
        self.assertLessEqual(len(wire), PROMPT_CAP + 4)
        started = time.monotonic()
        command = [sys.executable, "-I", "-S", "-B", str(self.client)]
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                cwd=self.artifacts.root, close_fds=True,
                                env={"PATH": os.defpath, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                                     "MKL_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1"})
        timed_out = False
        try:
            output, diagnostic = proc.communicate(input=wire, timeout=5)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            output, diagnostic = proc.communicate(timeout=2)
        self.observations.append({"case": self.id().rsplit(".", 1)[-1], "input": pin(wire),
            "output": pin(output), "stderr": pin(diagnostic), "pid": proc.pid,
            "retained_first_frame_hex": output[:4100].hex(), "output_retention_complete": len(output) <= 4100,
            "stderr_prefix": diagnostic[:2048].decode(errors="replace"),
            "returncode": proc.returncode, "wait_completed": proc.returncode is not None,
            "timed_out": timed_out, "expected_refusal": refusal,
            "closure_scope": "communicate completed and child reaped; escaped-descendant containment unqualified",
            "seconds": round(time.monotonic() - started, 6)})
        self.assertFalse(timed_out, "Frozen programme exceeded the generated-case deadline")
        self.assertLessEqual(len(output), 4100)
        self.assertLessEqual(len(diagnostic), 16384)
        if refusal:
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(output, b"", "Malformed input emitted an admissible response")
            return None
        self.assertEqual(proc.returncode, 0, diagnostic[:800].decode(errors="replace"))
        self.assertEqual(diagnostic, b"")
        self.assertGreater(len(output), 4)
        self.assertEqual(PREFIX.unpack(output[:4])[0], len(output) - 4)
        value = json.loads(output[4:])
        self.assertEqual(set(value), {"trial_id", "target_probability"})
        self.assertEqual(value["trial_id"], expected_id)
        probability = value["target_probability"]
        self.assertIn(type(probability), (int, float))
        self.assertTrue(math.isfinite(probability))
        self.assertGreaterEqual(probability, 0.0); self.assertLessEqual(probability, 1.0)
        self.assertEqual(self.consumer.parse_response(output[4:].decode(), expected_id), probability)
        return probability

    def predict(self, demos, item):
        body = prompt(demos, item)
        return self.invoke(PREFIX.pack(len(body)) + body, item["trial_id"])

    def test_separated_signals_discriminate_through_complete_frame(self):
        demos = demonstrations()
        low = self.predict(demos, query(-1)); high = self.predict(demos, query(1))
        self.assertLess(low, 0.25)
        self.assertGreater(high, 0.75)
        self.assertGreater(high - low, 0.5)
        # Necessary ABI boundaries stay within this scientific method: a cut
        # signal or a query carrying its target must never receive a prediction.
        complete = prompt(demos, query(1))
        self.invoke(PREFIX.pack(len(complete)) + complete[:-1], refusal=True)
        leaked = query(1); leaked["target"] = 1
        malformed = prompt(demos, leaked)
        self.invoke(PREFIX.pack(len(malformed)) + malformed, refusal=True)

    def test_swapping_demonstration_labels_reverses_decision(self):
        demos = demonstrations(); swapped = copy.deepcopy(demos)
        for item in swapped:
            item["target"] = 1 - item["target"]
        for polarity in (-1, 1):
            with self.subTest(polarity=polarity):
                original = self.predict(demos, query(polarity))
                reversed_label = self.predict(swapped, query(polarity))
                self.assertAlmostEqual(reversed_label, 1.0 - original, delta=1e-12)
                self.assertLess((original - 0.5) * (reversed_label - 0.5), 0)

    def test_demonstration_order_does_not_change_probability(self):
        # A near-boundary query prevents logit clipping from hiding order drift.
        demos = demonstrations(); item = query(0.03)
        reference = self.predict(demos, item)
        self.assertGreater(reference, 0.05); self.assertLess(reference, 0.95)
        for order in ((3, 2, 1, 0), (2, 0, 3, 1), (1, 0, 2, 3)):
            with self.subTest(order=order):
                changed = self.predict([demos[index] for index in order], item)
                self.assertAlmostEqual(changed, reference, delta=1e-12)

    def test_only_opaque_query_identity_changes_no_probability(self):
        # Avoid a saturated answer that could conceal identity-dependent drift.
        demos = demonstrations(); original = query(-0.03)
        renamed = copy.deepcopy(original); renamed["trial_id"] = "q-" + "e" * 32
        before = self.predict(demos, original); after = self.predict(demos, renamed)
        self.assertGreater(before, 0.05); self.assertLess(before, 0.95)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
