"""Generated complete-roster interface and leakage-boundary controls only."""
import builtins
import copy
import hashlib
import importlib.util
import math
from pathlib import Path
import struct
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("retina_constant", Path(__file__).with_name("constant.py"))
constant = importlib.util.module_from_spec(spec)
spec.loader.exec_module(constant)
T, S = constant.TRAIN, constant.SCORE


def ident(n):
    return format(n, "032x")


def npy(shape, values, dtype="<u8"):
    header = repr({"descr": dtype, "fortran_order": False, "shape": tuple(shape)}).encode("ascii")
    header += b" " * ((-10 - len(header) - 1) % 64) + b"\n"
    code = T.DTYPES[dtype][0]
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + struct.pack("<" + code * len(values), *values)


def fixture(condition="wn_to_wn", large=False):
    labels = [name for name, count in T.CLASSES.items() for _ in range(count)]
    cells = [{"cell_id": ident(i + 1), "published_class": label} for i, label in enumerate(labels)]
    preparations = [{"dataset": d, "cells": roster} for d, roster in
                    zip(sorted(T.DATASETS), (cells[:51], cells[51:]))]
    source_streams, bodies, truth = [], {}, {}
    for prep in preparations:
        for domain, seed, trials, frames in (("WN", None, 1, 3), ("NM", 1, 1, 4), ("NM", 2, 2, 5)):
            key = (prep["dataset"], domain, seed)
            values = []
            truth[key] = {}
            for cell in prep["cells"]:
                base = int(cell["cell_id"], 16) + (100 if domain == "WN" else 10 * seed)
                row = [base + j for j in range(trials * frames)]
                if large:
                    row = [2**53 + 1 + j for j in range(trials * frames)]
                truth[key][cell["cell_id"]] = row
                values.extend(row)
            shape = [len(prep["cells"]), trials, frames]
            body = npy(shape, values)
            bodies[key] = body
            source_streams.append({"dataset": key[0], "stimulus": domain, "seed": seed,
                "source_cell_ids": [c["cell_id"] for c in prep["cells"]],
                "train_trial_ids": [ident(10000 + j) for j in range(trials)],
                "train_frames_per_trial": frames, "test_frames_per_trial": 5,
                "timing_evidence_sha256": "a" * 64, "independent_extent_evidence_sha256": "b" * 64,
                "artifact": {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                             "dtype": "<u8", "shape": shape}})
    policy = {"schema": "marmoset-train-only-policy-v1", "task_id": T.TASK,
              "source_release": "10.12751/g-node.t43ph1", "condition": condition,
              "cohort_evidence_sha256": "c" * 64, "complete_stream_census_sha256": "d" * 64,
              "preparations": preparations, "streams": source_streams}
    policy_sha = hashlib.sha256(T.canonical(policy)).hexdigest()
    with mock.patch.object(T, "read_training", side_effect=lambda root, s: bodies[constant._key(s)]):
        prepared = T.prepare_training(policy, policy_sha256=policy_sha, source_root=Path("unused-generated-root"),
                                      read_byte_budget=2**20, output_byte_budget=2**20)
    streams = []
    for source in source_streams:
        if source["stimulus"] != S.TARGET_DOMAIN[condition]:
            continue
        streams.append({"stream_id": ident(2000 + len(streams)), "dataset": source["dataset"],
            "stimulus": source["stimulus"], "seed": source["seed"], "sequence_sha256": "e" * 64,
            "repeat_ids": [ident(3000), ident(3001)], "repeat_sequence_sha256": ["e" * 64] * 2,
            "frame_ids": [ident(4000 + i) for i in range(3)], "alignment_evidence_sha256": "f" * 64})
    score = {"schema": "marmoset-protected-score-policy-v1", "task_id": T.TASK,
        "source_release": policy["source_release"], "condition": condition,
        "training_policy_sha256": policy_sha, "cohort_evidence_sha256": policy["cohort_evidence_sha256"],
        "complete_stream_census_sha256": policy["complete_stream_census_sha256"],
        "rate_floor": 0.01, "coverage_policy": "all_cells_or_null",
        "preparations": copy.deepcopy(preparations), "streams": streams}
    return policy, prepared, score, truth


def run(data, **overrides):
    policy, prepared, score, _ = data
    kwargs = {"training_policy_sha256": hashlib.sha256(T.canonical(policy)).hexdigest(),
              "training_result_sha256": S.fingerprint(prepared), "score_policy_sha256": S.fingerprint(score),
              "training_count_byte_budget": 2**20, "prediction_byte_budget": 2**20}
    kwargs.update(overrides)
    return constant.predict(policy, prepared, score, **kwargs)


class ConstantBaselineTests(unittest.TestCase):
    def test_all_six_conditions_use_complete_fit_domain_weighted_counts(self):
        for condition in T.CONDITIONS:
            with self.subTest(condition=condition):
                data = fixture(condition)
                result = run(data)
                self.assertEqual(len(result["fit"]["cells"]), 170)
                self.assertFalse(result["scientifically_qualified"])
                fit_domain = next(d for d, access in T.CONDITIONS[condition].items() if access == "fit")
                for row in result["fit"]["cells"]:
                    values = [v for key, cells in data[3].items()
                              if key[0] == row["dataset"] and key[1] == fit_domain
                              for v in cells[row["cell_id"]]]
                    self.assertEqual(row["count_sum"], sum(values))
                    self.assertEqual(row["source_observations"], len(values))
                    self.assertEqual(row["mean_count"], sum(values) / len(values))
                self.assertEqual(len(result["predictions"]["streams"]), len(data[2]["streams"]))
                for packet in result["predictions"]["streams"]:
                    stream = next(s for s in data[2]["streams"] if s["stream_id"] == packet["stream_id"])
                    means = {r["cell_id"]: r["mean_count"] for r in result["fit"]["cells"] if r["dataset"] == stream["dataset"]}
                    expected = [means[c] for c in packet["cell_ids"] for _ in packet["frame_ids"]]
                    self.assertEqual([v[0] for v in struct.iter_unpack("<d", packet["values"])], expected)

    def test_assisted_calibration_is_delivered_but_never_fitted(self):
        for condition in ("nm_to_nm_wn_calibrated_author", "nm_to_wn_wn_assisted"):
            data = fixture(condition)
            out = run(data)
            self.assertEqual(len(out["fit"]["calibration_streams_excluded_from_mean"]), 2)
            self.assertEqual({s["stimulus"] for s in out["fit"]["fit_streams"]}, {"NM"})
            changed = copy.deepcopy(data)
            packet = next(p for p in changed[1]["packets"] if p["stimulus"] == "WN")
            packet["response_access"] = "fit"
            with self.assertRaisesRegex(S.InputError, "response_access"):
                run(changed)

    def test_exact_integer_accumulation_above_binary64_integer_precision(self):
        data = fixture("nm_to_nm_source_only", large=True)
        out = run(data)
        row = out["fit"]["cells"][0]
        values = [v for key, cells in data[3].items() if key[0] == row["dataset"] and key[1] == "NM"
                  for v in cells[row["cell_id"]]]
        self.assertEqual(row["count_sum"], sum(values))
        self.assertEqual(row["mean_count"], sum(values) / len(values))
        self.assertNotEqual(sum(values), sum(int(float(v)) for v in values))

    def test_existing_scorer_retains_undefined_pearson_and_finite_poisson(self):
        data = fixture()
        out = run(data)
        p = data[2]
        candidate = out["predictions"]
        target = {k: copy.deepcopy(candidate[k]) for k in ("task_id", "condition", "training_policy_sha256", "unit")}
        target.update(schema="marmoset-target-counts-v1", streams=[])
        reference = copy.deepcopy(candidate)
        reference["model_sha256"] = "1" * 64
        for packet, ref_packet in zip(candidate["streams"], reference["streams"]):
            stream = next(s for s in p["streams"] if s["stream_id"] == packet["stream_id"])
            n = len(packet["cell_ids"])
            target["streams"].append({**packet, "repeat_ids": stream["repeat_ids"],
                "values": struct.pack("<" + "d" * n * 6, *([0, 1, 2, 2, 3, 4] * n))})
            ref_packet["values"] = struct.pack("<" + "d" * n * 3, *([1, 2, 3] * n))
        report = S.score(p, target, candidate, reference, policy_sha256=S.fingerprint(p),
            targets_sha256=S.fingerprint(target), candidate_sha256=S.fingerprint(candidate),
            reference_sha256=S.fingerprint(reference))
        self.assertEqual(len(report["cells"]), 170)
        self.assertIsNone(report["equal_preparation_descriptive"]["candidate_r"])
        self.assertTrue(all(r["candidate_undefined"] == ["constant_prediction"] for r in report["cells"]))
        self.assertTrue(all(math.isfinite(r["candidate_poisson_nll"]) for r in report["cells"]))

    def test_missing_duplicate_and_extra_permitted_streams_refuse(self):
        for change in (lambda d: d[1]["packets"].pop(),
                       lambda d: d[1]["packets"].__setitem__(0, copy.deepcopy(d[1]["packets"][1])),
                       lambda d: d[2]["streams"].pop(),
                       lambda d: d[1]["packets"][0].update(seed=True)):
            data = fixture("nm_to_nm_source_only")
            change(data)
            with self.assertRaises(S.InputError):
                run(data)

    def test_changed_cohort_condition_and_calibration_binding_refuse(self):
        for change in (lambda d: d[2].update(training_policy_sha256="9" * 64),
                       lambda d: d[2].update(cohort_evidence_sha256="9" * 64),
                       lambda d: d[2].update(complete_stream_census_sha256="9" * 64),
                       lambda d: d[2]["preparations"][0]["cells"].reverse(),
                       lambda d: d[1].update(condition="wn_to_nm_source_only")):
            data = fixture()
            change(data)
            with self.assertRaises(S.InputError):
                run(data)

    def test_bad_prepared_count_bodies_and_metadata_refuse(self):
        for change in (lambda p: p.update(counts=b""), lambda p: p.update(counts_sha256="0" * 64),
                       lambda p: p["cell_ids"].reverse(), lambda p: p.update(unit="spikes_per_second"),
                       lambda p: p.update(train_trial_ids=[ident(11111)]),
                       lambda p: p.update(protected_test_counts=b"hidden")):
            data = fixture()
            change(data[1]["packets"][0])
            with self.assertRaises(S.InputError):
                run(data)

    def test_nonintegral_nonfinite_and_negative_float_training_refuse(self):
        for bad in (-1.0, 0.5, math.nan, math.inf):
            data = fixture()
            packet = data[1]["packets"][0]
            stream = next(s for s in data[0]["streams"] if constant._key(s) == constant._key(packet))
            stream["artifact"]["dtype"] = packet["dtype"] = "<f8"
            body = struct.pack("<d", bad) + struct.pack("<d", 1.0) * (len(packet["counts"]) // 8 - 1)
            packet["counts"] = body
            packet["counts_sha256"] = hashlib.sha256(body).hexdigest()
            policy_sha = hashlib.sha256(T.canonical(data[0])).hexdigest()
            data[1]["policy_sha256"] = data[2]["training_policy_sha256"] = policy_sha
            with self.assertRaisesRegex(S.InputError, "integral training"):
                run(data)

    def test_wrong_external_identities_and_incomplete_buffer_budgets_refuse(self):
        data = fixture()
        for field in ("training_policy_sha256", "training_result_sha256", "score_policy_sha256"):
            with self.assertRaises(S.InputError):
                run(data, **{field: "0" * 64})
        for field in ("training_count_byte_budget", "prediction_byte_budget"):
            with self.assertRaisesRegex(S.InputError, "allocation"):
                run(data, **{field: 1})

    def test_no_runtime_file_access_and_model_commitment_changes_with_counts(self):
        data = fixture()
        with mock.patch.object(builtins, "open", side_effect=AssertionError("scientific file open")), \
             mock.patch.object(Path, "read_bytes", side_effect=AssertionError("scientific file read")):
            original = run(data)
        modified = copy.deepcopy(data)
        packet = modified[1]["packets"][0]
        packet["counts"] = struct.pack("<Q", 999) + packet["counts"][8:]
        packet["counts_sha256"] = hashlib.sha256(packet["counts"]).hexdigest()
        other = run(modified)
        self.assertNotEqual(original["predictions"]["model_sha256"], other["predictions"]["model_sha256"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
