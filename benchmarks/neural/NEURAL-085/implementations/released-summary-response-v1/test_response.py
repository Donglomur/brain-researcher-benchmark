"""Generated source-path controls, never authentic observations or model scores."""
import argparse
import copy
import importlib.util
import os
from pathlib import Path
import resource
import signal
import sys
import types
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("n085_response", HERE / "response.py")
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
ROOT = Path(os.environ.get("NEUROBENCH_TEST_SOURCE_ROOT", str(HERE.parents[4])))
SHARED = ROOT / "benchmarks/shared/zuco2/zuco2-neural085-086-complete-v1/zuco"


def h(x): return M.digest(str(x).encode())


def identity(arm="NTGE", person=17, fold=0):
    return {"task": "NEURAL-085", "person_token": h(("person", person)), "item_fold": fold,
            "context": "sentence", "arm": arm, "representation": "released_summary",
            "mode": "frozen_program", "seed": 0, "programme_sha256": h("programme"),
            "source_sha256": h("source"), "split_sha256": h("split"),
            "information_set": "offline_case_local", "generation": h("generation"),
            "role": "participant", "method": "candidate"}


def source_exporter():
    expected = "68204e30edd38e95a5ed2e814d7f8064473583faeabb00c4c95f0edd2444ff4a"
    assert M.digest((SHARED / "features.py").read_bytes()) == expected
    name = "_n085_source"
    package = types.ModuleType(name); package.__path__ = [str(SHARED)]; sys.modules[name] = package
    s = importlib.util.spec_from_file_location(name + ".features", SHARED / "features.py")
    module = importlib.util.module_from_spec(s); s.loader.exec_module(module)
    return module


SOURCE = source_exporter()


def packets(arm="NTGE", query_count=2):
    def row(person, label, idx):
        eeg = [None if k % 7 == 0 else (-1.25 if label else 2.5) for k in range(840)]
        return {"sentence": {"person": person, "condition": "TSR" if label else "NR",
                "text": ' Literal "sentence"; \n\t\U0001f9e0 ' + str(idx),
                "words": [{"word": "Literal"}, {"word": "sentence"}],
                "gaze_summary": [110.0, 1.0, None, 0.0, 130.0, 0.5, 140.0, 1.0, 2.0, 1.0, 0.0, 1.25],
                "eeg_summary": eeg, "valid_gaze_fractions": [1.0, 0.0, 0.5, 1.0, 1.0]},
                "word_index": None}
    train = [row(p, y, p * 2 + y) for p in range(17) for y in (0, 1)]
    query = [row(17, k % 2, k) for k in range(query_count)]
    partition = {"train": train, "query": query,
                 "train_ids": [h(("t", k)) for k in range(len(train))],
                 "query_ids": [h(("q", k)) for k in range(len(query))],
                 "weights": [1.25 if k % 2 else 0.75 for k in range(len(train))]}
    view = SOURCE.public_rows(partition, identity(arm))
    for r, original in zip(view["train"], train):
        r["person_group"] = h(("training-person", original["sentence"]["person"]))
        r["item_group"] = h(("training-item", original["sentence"]["text"]))
    shared = {"identity": view["identity"], "information_set": "offline_case_local"}
    return {**shared, "train": view["train"]}, {**shared, "query": view["query"]}


def bound(t, q):
    a, b = M.encode(t), M.encode(q)
    binding = {"training": M.pin(a), "query": M.pin(b), "identity_sha256": M.digest(t["identity"]),
               "training_census_sha256": M.digest([r["id"] for r in t["train"]]),
               "query_ids": [r["id"] for r in q["query"]]}
    return a, b, binding


def caps():
    return {"input_bytes": 2**32, "condition_transport_bytes": 2**32, "frame_bytes": 2**26,
            "job_retained_bytes": 2**27, "job_retained_tokens": 2**27, "condition_tokens": 2**32,
            "response_reserve_bytes_per_job": 131072, "response_reserve_tokens_per_job": 131072,
            "token_measurement_id": "generated_byte_counter_not_a_provider_tokenizer"}


def measure(frames): return sum(map(len, frames))


def prepared(t=None, q=None, cap=None):
    if t is None: t, q = packets()
    return M.PreparedJob(*bound(t, q), cap or caps(), measure)


class Controls(unittest.TestCase):
    def test_all_nine_real_exporter_arms_preserve_complete_values_masks_order_groups(self):
        for arm in M.ARMS:
            t, q = packets(arm); j = prepared(t, q)
            calibration, inference = map(M.decode, j._frames)
            self.assertEqual(calibration["training"], inference["training"])
            for raw, shown in zip(t["train"], calibration["training"]):
                self.assertEqual(shown["features"], raw["features"])
                self.assertEqual((shown["label"], shown["weight"]), (raw["label"], raw["weight"]))
            for raw, shown in zip(q["query"], inference["query"]):
                self.assertEqual(shown["features"], raw["features"])
                self.assertEqual(set(shown), {"token", "features"})
            original_groups = [(a["person_group"], a["item_group"]) for a in t["train"]]
            shown_groups = [(a["person_group"], a["item_group"]) for a in calibration["training"]]
            for x in range(len(original_groups)):
                for y in range(len(original_groups)):
                    self.assertEqual([original_groups[x][k] == original_groups[y][k] for k in (0, 1)],
                                     [shown_groups[x][k] == shown_groups[y][k] for k in (0, 1)])
            for secret in (t["identity"]["person_token"], h("source"), t["train"][0]["id"], q["query"][0]["id"]):
                self.assertNotIn(secret.encode(), b"".join(j._frames))
            with self.assertRaisesRegex(ValueError, "condition_not_admitted"):
                j.calibration()

    def test_masks_ranges_missing_fields_and_arm_leakage_rejected(self):
        cases = [lambda t, q: q["query"][0].update(label=1),
                 lambda t, q: t.update(raw_training=[]),
                 lambda t, q: q["query"][0]["features"].update(source_path="NR.mat"),
                 lambda t, q: q["query"][0]["features"]["nuisance"]["eeg_support"].__setitem__(0, 0),
                 lambda t, q: q["query"][0]["features"]["nuisance"]["gaze_missing"].__setitem__(2, 0),
                 lambda t, q: q["query"][0]["features"]["nuisance"]["valid_gaze_fractions"].__setitem__(0, 2),
                 lambda t, q: q["query"][0]["features"]["nuisance"].update(source_word_slots=True),
                 lambda t, q: t["train"].pop(),
                 lambda t, q: t["train"][0].update(weight=0)]
        for mutate in cases:
            t, q = packets(); mutate(t, q)
            with self.assertRaises(ValueError): prepared(t, q)
        for arm in ("TEXT", "GAZE", "JOINT"):
            t, q = packets(arm); q["query"][0]["features"]["nuisance"] = {}
            with self.assertRaisesRegex(ValueError, "feature_blocks"): prepared(t, q)

    def test_bound_census_and_literal_extreme_values(self):
        t, q = packets(); a, b, binding = bound(t, q)
        for name, value in (("query_ids", list(reversed(binding["query_ids"]))),
                            ("training_census_sha256", h("wrong"))):
            bad = copy.deepcopy(binding); bad[name] = value
            with self.assertRaises(ValueError): M.PreparedJob(a, b, bad, caps(), measure)
        with self.assertRaisesRegex(ValueError, "input_pin_mismatch"):
            M.PreparedJob(a + b" ", b, binding, caps(), measure)
        q["query"][0]["features"]["eeg"][1] = -1.7976931348623157e308
        j = prepared(t, q)
        self.assertEqual(M.decode(j._frames[1])["query"][0]["features"], q["query"][0]["features"])
        duplicate = a[:-2] + b',"train":[]}\n'; bad = copy.deepcopy(binding); bad["training"] = M.pin(duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate_json_key"):
            M.PreparedJob(duplicate, b, bad, caps(), measure)

    def test_pre_exposure_per_job_capacity_and_unqualified_token_measurement(self):
        t, q = packets(); j = prepared(t, q); r = j.preflight_operator()
        for field, value in (("input_bytes", 1), ("frame_bytes", 1), ("job_retained_bytes", 1),
                             ("job_retained_tokens", 1), ("response_reserve_bytes_per_job", 1),
                             ("response_reserve_tokens_per_job", 1)):
            c = caps(); c[field] = value
            with self.assertRaises(M.CapacityError) as ctx: prepared(t, q, c)
            self.assertFalse(ctx.exception.disposition["participant_exposure"])
        self.assertFalse(r["provider_capacity_qualified"])
        with self.assertRaisesRegex(ValueError, "operator_token_measurement"):
            M.PreparedJob(*bound(t, q), caps(), lambda frames: True)

    def test_same_input_nonce_and_order_phase_and_frame_mismatch(self):
        t, q = packets(); a, b = prepared(t, q), prepared(t, q)
        self.assertNotEqual(a._session, b._session)
        self.assertTrue(M.require_same_prepared_exposure(a, b)["exact_frozen_input_order_phase_equal"])
        changed = copy.deepcopy(t); changed["train"].reverse()
        with self.assertRaisesRegex(ValueError, "different_frozen_exposure"):
            M.require_same_prepared_exposure(a, prepared(changed, q))
        b._frames = (b._frames[1], b._frames[0])
        with self.assertRaisesRegex(ValueError, "prepared_frame_or_receipt_changed"):
            M.require_same_prepared_exposure(a, b)

    def test_full_census_arithmetic_preserves_empty_fold_and_refuses_duplicates(self):
        # Compact descriptors exercise census arithmetic only; actual exporter,
        # complete frame preparation and810-job admission are separate controls.
        rs = [{"identity": identity(a, p, f), "query_rows": (0, 185, 185, 185, 184)[f]}
              for p in range(18) for f in range(5) for a in M.ARMS]
        M.validate_census(rs)
        for bad in (rs[:-1], rs[:-1] + [rs[0]]):
            with self.assertRaises(ValueError): M.validate_census(bad)
        bad = copy.deepcopy(rs); bad[0]["query_rows"] = 1
        with self.assertRaisesRegex(ValueError, "original_739"): M.validate_census(bad)

    def test_cumulative_capacity_refuses_before_any_exposure(self):
        t, q = packets("NTGE"); t2, q2 = copy.deepcopy(t), copy.deepcopy(q)
        t2["identity"] = q2["identity"] = identity("NTGE", 16, 0)
        first_args, second_args = bound(t, q), bound(t2, q2)
        # Unopened future bindings are a compact issuer fixture in this focused
        # early-overflow check; the separate810 test validates every real job.
        expected = [first_args[2], second_args[2]]
        for k in range(808):
            b = copy.deepcopy(first_args[2]); b["identity_sha256"] = h(("unused-future", k))
            expected.append(b)
        base = prepared(t, q).preflight_operator()
        for field, receipt_field in (("input_bytes", "input_bytes"),
                                      ("condition_transport_bytes", "transport_bytes"),
                                      ("condition_tokens", "retained_tokens")):
            c = caps(); c[field] = base[receipt_field] + 1024
            jobs = [M.PreparedJob(*args, c, measure) for args in (first_args, second_args)]
            with self.assertRaises(M.CapacityError) as ctx: M.Condition(jobs, expected, c)
            self.assertFalse(ctx.exception.disposition["participant_exposure"])
            self.assertTrue(all(j._admission is None for j in jobs))
            for j in jobs:
                with self.assertRaisesRegex(ValueError, "condition_not_admitted"): j.calibration()

    def test_single_active_job_is_enforced_before_loading_another_capture(self):
        # Isolate the reviewed controller-state branch; no source or admission
        # qualification is claimed by this small constructed state fixture.
        binding = bound(*packets())[2]; key = M.digest(binding)
        condition = object.__new__(M.Condition)
        condition._records = {key: {}, "already-active": {}}
        condition._states = {key: "ready", "already-active": "opened"}
        with self.assertRaisesRegex(ValueError, "previous_job_still_open"):
            condition.open(b"not-read", b"not-read", binding, measure)

    def test_real_prepared_810_condition_complete_preflight_and_collection_barriers(self):
        # Stream actual materialized/validated frames, retaining receipts only.
        started = time.monotonic()
        templates = {a: packets(a, 148) for a in M.ARMS}
        c = caps()
        coords = [(p, f, a) for p in range(18) for f in range(5) for a in M.ARMS]
        def inputs(coord):
            p, f, arm = coord; t0, q0 = templates[arm]; ident = identity(arm, p, f)
            t = {**t0, "identity": ident}
            q = {**q0, "identity": ident, "query": q0["query"][:147 if f == 4 else 148]}
            return bound(t, q)
        bindings = [inputs(coord)[2] for coord in coords]
        print("generated issuer810 bindings prepared: %.3fs" % (time.monotonic() - started), flush=True)
        first = M.PreparedJob(*inputs(coords[0]), c, measure)
        with self.assertRaisesRegex(ValueError, "missing_prepared_job"):
            M.Condition([first], bindings, c)
        with self.assertRaisesRegex(ValueError, "condition_not_admitted"):
            first.calibration()
        bad = M.PreparedJob(*inputs(coords[0]), c, measure)
        bad._frames = (bad._frames[0], bad._frames[1] + b" ")
        with self.assertRaisesRegex(ValueError, "prepared_frame_or_receipt_changed"):
            M.Condition([bad], bindings, c)
        condition = M.Condition((M.PreparedJob(*inputs(coord), c, measure) for coord in coords), bindings, c)
        print("actual generated810 frames preflighted: %.3fs" % (time.monotonic() - started), flush=True)
        self.assertEqual(condition.preflight_operator()["jobs_count"], 810)
        self.assertFalse(condition.preflight_operator()["provider_capacity_qualified"])
        self.assertFalse(any(isinstance(v, M.PreparedJob) for v in condition.__dict__.values()))
        args = inputs(coords[0])
        with self.assertRaisesRegex(ValueError, "input_pin_mismatch"):
            condition.open(args[0] + b" ", args[1], args[2], measure)
        with self.assertRaisesRegex(ValueError, "reloaded_preparation_mismatch"):
            condition.open(*args, lambda frames: measure(frames) + 1)
        j = condition.open(*args, measure)
        with self.assertRaisesRegex(ValueError, "unknown_or_already_opened"):
            condition.open(*args, measure)
        twin = M.PreparedJob(*args, c, measure)
        cal = M.decode(j.calibration()); infer = M.decode(j.inference())
        self.assertEqual(cal["training"], infer["training"])
        reply = {"session": infer["session"], "token": "query-0", "p_tsr": 0.25}
        with self.assertRaisesRegex(ValueError, "reply_binding"):
            j.answer({**reply, "session": twin._session})
        for p in (True, float("nan"), float("inf"), -0.1, 1.1):
            with self.assertRaisesRegex(ValueError, "probability_range"): j.answer({**reply, "p_tsr": p})
        with self.assertRaisesRegex(ValueError, "reply_fields"): j.answer({**reply, "extra": 1})
        j.answer(reply)
        with self.assertRaisesRegex(ValueError, "unknown_or_final"): j.answer(reply)
        with self.assertRaisesRegex(ValueError, "incomplete_or_closed"): condition.collect(j)
        for i in range(1, len(infer["query"])):
            j.answer({**reply, "token": "query-%d" % i, "p_tsr": 0.5})
        result = condition.collect(j)
        self.assertEqual([r["id"] for r in result["probabilities"]], bindings[0]["query_ids"])
        self.assertEqual(result["probabilities"][0]["p_tsr"], 0.25)
        self.assertFalse(result["actual_participant_delivery_attested"])
        with self.assertRaisesRegex(ValueError, "incomplete_condition"): condition.finish_operator()
        for ordinal, coord in enumerate(coords[1:], 2):
            job = condition.open(*inputs(coord), measure)
            job.calibration(); frame = M.decode(job.inference())
            for row in frame["query"]:
                job.answer({"session": frame["session"], "token": row["token"], "p_tsr": 0.5})
            condition.collect(job)
            if ordinal % 180 == 0:
                print("generated jobs collected=%d: %.3fs" % (ordinal, time.monotonic() - started), flush=True)
        self.assertTrue(condition.finish_operator()["complete_810_job_collection"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--control-timeout-seconds", type=int, default=120)
    args, remaining = parser.parse_known_args()
    if not 0 < args.control_timeout_seconds <= 600:
        parser.error("positive generated-control timeout at most600 seconds required")
    signal.alarm(args.control_timeout_seconds)
    try:
        unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
    finally:
        print("maximum_rss_native_units=" + str(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
              + " platform=" + sys.platform)
