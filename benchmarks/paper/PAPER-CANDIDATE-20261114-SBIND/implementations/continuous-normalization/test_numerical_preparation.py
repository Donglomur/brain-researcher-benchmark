"""Invented source-boundary controls; no NumPy, Torch, original arrays or models."""
from collections.abc import Sequence
import copy
from fractions import Fraction
import hashlib
import io
import json
import math
import unittest
from unittest.mock import patch

import numerical_preparation as subject
import test_trial_preparation as prior
import trial_preparation as trials


def image(left, right=None):
    right = left if right is None else right
    return ((tuple([left] * 64 + [right] * 64),) * 128,)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def metadata():
    census, split = prior.fixture()
    # Invented full 660-trial census; one unequal first trial, no authentic claim.
    for assay in census["assays"]:
        cursor = 0
        for i, row in enumerate(assay["trials"]):
            row["source_start"] = cursor; row["length"] = 2 if i == 0 else 1
            cursor += row["length"]
    c, s, pins = prior.bind(census, split)
    protocol = trials.compile_protocol(c, s, **pins)
    declarations = {"schema": "sbind-owner-fold-representations-v1", "task_id": trials.TASK,
                    **pins, "folds": []}
    for assay in protocol.assays:
        for fold in assay.folds:
            declarations["folds"].append({"assay_id": assay.assay_id, "fold": fold.number,
                                         "source_sha256": assay.source_sha256,
                                         "representation_sha256": assay.representation_sha256,
                                         "fit_trial_ids": [s.trial_id for s in fold.train],
                                         "fitted_artifact_sha256": "3" * 64,
                                         "method_source_sha256": "4" * 64})
    r = encode(declarations)
    return c, s, r, dict(pins, representations_sha256=hashlib.sha256(r).hexdigest()), protocol


class InspectSink:
    def __init__(self, role, expected):
        self.role = role; self.expected = expected; self.frames = []; self.header = None
        self.sha = hashlib.sha256(); self.bytes = 0
    def write(self, raw):
        self.sha.update(raw); self.bytes += len(raw)
        value = json.loads(raw)
        if value["record"] == "header":
            self.header = value
        else:
            if self.role != "owner":
                assert ("behavior" in value) == (self.role == "train")
                assert len(value["neural"]) == 1 and len(value["neural"][0]) == 128
                assert all(len(row) == 128 for row in value["neural"][0])
            else:
                assert "neural" not in value and "behavior" in value
            self.frames.append({k: v for k, v in value.items() if k not in ("neural", "behavior")})
        return len(raw)


class NumericalTests(unittest.TestCase):
    def test_source_defined_global_raw_sd_and_channel_stats(self):
        frames = [trials.Frame(0, "a", 0, True, image(0, 10), (0, 7)),
                  trials.Frame(1, "a", 1, False, image(2, 12), (2, 7))]
        stats = subject.fit_training(frames, 2)
        self.assertEqual(stats["neural_mean"][:64], (1.0,) * 64)
        self.assertEqual(stats["neural_mean"][64:128], (11.0,) * 64)
        self.assertEqual(stats["neural_sd"], math.sqrt(26))
        self.assertNotEqual(stats["neural_sd"], 1.0)  # Not pixel-demeaned residual SD.
        self.assertEqual(stats["behavior_mean"], (1.0, 7.0))
        self.assertEqual(stats["behavior_sd"], (1.0, 1.0))
        self.assertEqual(stats["training_frames"], 2)

    def test_finite_extremes_zero_sd_and_unrepresentable_result(self):
        top = float.fromhex("0x1.fffffffffffffp+1023")
        self.assertEqual(subject._sqrt_ratio(Fraction(top) ** 2), top)
        self.assertEqual(subject._standardize(top, -top, top), 2.0)
        self.assertEqual(subject._sqrt_ratio(Fraction(0)), 1.0)
        tiny = float.fromhex("0x0.0000000000001p-1022")
        self.assertEqual(subject._sqrt_ratio(Fraction(tiny) ** 2), tiny)
        with self.assertRaises(trials.AdmissionError):
            subject._standardize(top, -top, 1.0)
        with self.assertRaises(trials.AdmissionError):
            subject._sqrt_ratio(Fraction(tiny) ** 2 / 100)

    def test_complete_representation_grid_before_source_access(self):
        c, s, r, pins, protocol = metadata()
        self.assertEqual(len(subject.admit_representations(r, pins["representations_sha256"], protocol)), 10)
        for mutate in (lambda x: x["folds"].pop(),
                       lambda x: x["folds"][0].update(fitted_artifact_sha256=None),
                       lambda x: x["folds"][0]["fit_trial_ids"].append(protocol.assays[0].folds[0].test[0].trial_id),
                       lambda x: x["folds"][9].update(fold=True)):
            broken = json.loads(r); mutate(broken); raw = encode(broken)
            p = dict(pins, representations_sha256=hashlib.sha256(raw).hexdigest())
            calls = []
            with self.assertRaises(trials.AdmissionError):
                subject.prepare_selected_fold(c, s, raw, **p, assay_id="WFCI1", fold=0,
                                              source_loader=lambda *a: calls.append(a),
                                              sinks={k: io.BytesIO() for k in subject.ROLES},
                                              owner_targets_sink=io.BytesIO())
            self.assertEqual(calls, [])

    def test_complete_fold_serialization_visibility_targets_last_and_resets(self):
        c, s, r, pins, protocol = metadata(); assay = protocol.assays[0]; fold = assay.folds[0]
        expected = {role: sum(s.length for s in getattr(fold, role)) for role in subject.ROLES}
        sinks = {role: InspectSink(role, expected[role]) for role in subject.ROLES}
        owner = InspectSink("owner", expected["validation"] + expected["test"])
        train_indices = {i for span in fold.train for i in range(span.source_start, span.source_start + span.length)}
        private_reads = []
        class HeldBehavior(Sequence):
            def __len__(self):
                assert all(len(sinks[k].frames) == expected[k] for k in subject.ROLES)
                return 2
            def __getitem__(self, index):
                if index >= 2: raise IndexError(index)
                assert all(len(sinks[k].frames) == expected[k] for k in subject.ROLES)
                private_reads.append(index)
                return 8675309.0
        class Rows(Sequence):
            def __len__(self): return assay.total_frames
            def __getitem__(self, index):
                if not 0 <= index < len(self): raise IndexError(index)
                return image(index % 3), ((index % 2, 7) if index in train_indices else HeldBehavior())
        calls = []
        def loader(admitted, chosen, declaration):
            calls.append((admitted.assay_id, chosen, declaration["fit_trial_ids"]))
            return trials.SourceRows(admitted.source_sha256, admitted.representation_sha256,
                                     trials.SHAPE, admitted.channels, Rows())
        result = subject.prepare_selected_fold(c, s, r, **pins, assay_id="WFCI1", fold=0,
                                               source_loader=loader, sinks=sinks, owner_targets_sink=owner)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["complete_selected_fold_frames"], expected)
        self.assertEqual(sum(expected.values()), 249)
        all_ids = set()
        for role, sink in sinks.items():
            spans = getattr(fold, role)
            self.assertEqual([x["source_index"] for x in sink.frames],
                             [i for t in spans for i in range(t.source_start, t.source_start + t.length)])
            self.assertEqual([x["reset"] for x in sink.frames],
                             [i == 0 for t in spans for i in range(t.length)])
            self.assertEqual([x["trial_offset"] for x in sink.frames],
                             [i for t in spans for i in range(t.length)])
            ids = {x["trial_id"] for x in sink.frames}; self.assertFalse(ids & all_ids); all_ids |= ids
            self.assertEqual(result["participant_streams"][role],
                             {"bytes": sink.bytes, "sha256": sink.sha.hexdigest(), "records": expected[role] + 1})
        self.assertEqual(len(all_ids), 248)
        self.assertEqual(len(private_reads), 2 * owner.expected)
        self.assertEqual(result["normalization"]["behavior_mean"][1], 7.0)
        self.assertEqual(result["normalization"]["behavior_mean"][0],
                         float(Fraction(sum(i % 2 for i in train_indices), len(train_indices))))
        self.assertEqual(owner.bytes, result["owner_targets"]["bytes"])
        self.assertTrue(all(not result[k] for k in result if k.endswith("qualified")))

    def test_sink_failure_precedes_private_target_inspection(self):
        c, s, r, pins, protocol = metadata(); assay = protocol.assays[0]
        class NeverRows(Sequence):
            def __len__(self): return assay.total_frames
            def __getitem__(self, i): raise AssertionError("no values needed after mocked fit/header refusal")
        class Refuse:
            def write(self, raw): return 0
        owner = io.BytesIO(); sinks = {k: io.BytesIO() for k in subject.ROLES}; sinks["train"] = Refuse()
        stats = {"policy": subject.POLICY, "training_frames": 1, "neural_mean": (0.0,) * subject.PIXELS,
                 "neural_sd": 1.0, "behavior_mean": (0.0, 0.0), "behavior_sd": (1.0, 1.0)}
        with patch.object(subject, "fit_training", return_value=stats):
            with self.assertRaises(trials.AdmissionError):
                subject.prepare_selected_fold(c, s, r, **pins, assay_id="WFCI1", fold=0,
                    source_loader=lambda a, f, d: trials.SourceRows(a.source_sha256, a.representation_sha256,
                                                                  trials.SHAPE, a.channels, NeverRows()),
                    sinks=sinks, owner_targets_sink=owner)
        self.assertEqual(owner.getvalue(), b"")

    def test_short_writes_account_exact_bytes_and_refuse_invalid_returns(self):
        class Short(io.BytesIO):
            def write(self, raw): return super().write(raw[:3])
        sink = Short(); writer = subject._Writer(sink); writer.put({"x": [1, 2, 3]})
        raw = sink.getvalue()
        self.assertEqual(writer.receipt(), {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "records": 1})
        for value in (None, False, -1, 10000):
            class Bad:
                def write(self, raw): return value
            with self.assertRaises(trials.AdmissionError): subject._Writer(Bad()).put({"x": 1})

    def test_numeric_shapes_types_and_nonfinite_are_refused(self):
        for value in (True, float("nan"), float("inf"), "1", 10 ** 1000):
            with self.assertRaises(trials.AdmissionError): subject._number(value)
        for value in ([], [[[]]], image(1)[0], image(True)):
            with self.assertRaises(trials.AdmissionError): subject._neural(value)
        with self.assertRaises(trials.AdmissionError): subject._behavior([1], 2)
        with self.assertRaises(trials.AdmissionError): subject.fit_training([], 2)


if __name__ == "__main__":
    unittest.main()
