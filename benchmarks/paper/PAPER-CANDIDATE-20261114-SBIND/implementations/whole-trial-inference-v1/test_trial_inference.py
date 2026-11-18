"""Generated complete-census boundary controls; no authentic/model execution."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
DEPENDENCY = Path(os.environ.get("SBIND_TRIAL_PREPARATION", str(HERE.parent / "whole-trial-preparation")))
EXPECTED_DEPENDENCY = "c11d1afeb8a32a8d0984c656ffb5e98b092dc4a3bf60a7c0b9af566bb9f02a5e"
if hashlib.sha256((DEPENDENCY / "trial_preparation.py").read_bytes()).hexdigest() != EXPECTED_DEPENDENCY:
    raise RuntimeError("whole-trial dependency identity differs from reviewed source")
sys.path[:0] = [str(HERE), str(DEPENDENCY)]
import trial_inference as api


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def pin(raw):
    return hashlib.sha256(raw).hexdigest()


def metadata():
    census = {"schema": "sbind-complete-widefield-census-v1", "task_id": api.trials.TASK, "assays": []}
    split = {"schema": "sbind-prospective-whole-trial-folds-v1", "task_id": api.trials.TASK,
             "census_sha256": None, "assays": []}
    for name, count, channels in (("WFCI1", 248, 14), ("WFCI2", 412, 4)):
        rows = []
        start = 0
        for index in range(count):
            length = index + 2 if name == "WFCI1" and index < 2 else 1
            rows.append({"trial_id": f"{name}-trial-{index}", "source_start": start, "length": length})
            start += length
        ids = [r["trial_id"] for r in rows]
        test_sets = [ids[:2], *[ids[2 + i::4] for i in range(4)]]
        folds = []
        for number, test in enumerate(test_sets):
            other = [x for x in ids if x not in test]
            folds.append({"fold": number, "train": other[1:], "validation": other[:1], "test": test})
        census["assays"].append({"assay_id": name, "source_sha256": "a" * 64,
                                 "representation_sha256": "b" * 64, "neural_shape": [1, 128, 128],
                                 "behavior_channels": [f"behavior-{i}" for i in range(channels)], "trials": rows})
        split["assays"].append({"assay_id": name, "folds": folds})
    raw = encode(census)
    split["census_sha256"] = pin(raw)
    return raw, encode(split)


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, fields, *, x_init, behavior_width):
        self.calls.append((len(fields), x_init, behavior_width))
        return {"neural": fields,
                "behavior": [[float(i) for i in range(14)] for _ in fields]}


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.census, cls.split = metadata()
        cls.arguments = dict(census_sha256=pin(cls.census), split_sha256=pin(cls.split),
                             representations_sha256="c" * 64, normalization_sha256="d" * 64,
                             role="test", fold=0, max_trial_frames=3)
        header, spans = api._plan(cls.census, cls.split, **cls.arguments)
        records = [header]
        for span in spans:
            for offset in range(span.length):
                index = span.source_start + offset
                records.append({"record": "frame", "role": "test", "trial_id": span.trial_id,
                                "source_index": index, "trial_offset": offset, "reset": offset == 0,
                                "neural": [[[float(index)] * 128 for _ in range(128)]]})
        cls.records = records
        cls.raw = b"".join(encode(r) for r in records)

    def run_case(self, *, raw=None, recorder=None, stream=None, sink=None, arguments=None, digest=None,
                 max_output_bytes=2**20):
        raw = self.raw if raw is None else raw
        recorder = Recorder() if recorder is None else recorder
        sink = io.BytesIO() if sink is None else sink
        result = api.predict_held_wfci1(
            self.census, self.split, **(self.arguments if arguments is None else arguments),
            stream=io.BytesIO(raw) if stream is None else stream,
            stream_sha256=pin(raw) if digest is None else digest, stream_bytes=len(raw),
            infer_trial=recorder, sink=sink, max_output_bytes=max_output_bytes)
        return result, recorder, sink

    def mutated(self, mutate):
        records = json.loads(json.dumps(self.records))
        mutate(records)
        return b"".join(encode(r) for r in records)

    def test_complete_unequal_trials_reset_and_source_identity(self):
        result, recorder, sink = self.run_case()
        self.assertEqual(recorder.calls, [(2, True, 14), (3, True, 14)])
        rows = [json.loads(r) for r in sink.getvalue().splitlines()]
        self.assertEqual([r["source_index"] for r in rows[1:]], list(range(5)))
        self.assertEqual([r["trial_offset"] for r in rows[1:]], [0, 1, 0, 1, 2])
        self.assertEqual([r["neural"][0][0][0] for r in rows[1:]], list(range(5)))
        self.assertEqual(result["frames"], 5)
        self.assertEqual(result["trials"], 2)
        self.assertEqual(result["output_sha256"], pin(sink.getvalue()))
        self.assertEqual(result["output_bytes"], len(sink.getvalue()))
        self.assertFalse(result["historical_reproduction_qualified"])

    def test_rejects_held_behavior_and_wrong_header_before_callback(self):
        for mutate in (lambda r: r[1].update(behavior=[1] * 14),
                       lambda r: r[0].update(includes_behavior=True),
                       lambda r: r[0].update(assay_id="WFCI2"),
                       lambda r: r[0].update(fold=False),
                       lambda r: r[0].update(extra="target")):
            recorder, sink = Recorder(), io.BytesIO()
            with self.subTest(mutation=mutate), self.assertRaises(api.InferenceError):
                self.run_case(raw=self.mutated(mutate), recorder=recorder, sink=sink)
            self.assertEqual(recorder.calls, [])
            self.assertEqual(sink.getvalue(), b"")

    def test_rejects_missing_reordered_duplicate_reset_and_nonfinite_frames(self):
        mutations = [lambda r: r.pop(), lambda r: r.append(r[-1]),
                     lambda r: r[2].update(source_index=0), lambda r: r[1].update(source_index=False),
                     lambda r: r[3].update(reset=False), lambda r: r[2].update(reset=True),
                     lambda r: r[2]["neural"][0][0].pop(),
                     lambda r: r[2]["neural"][0][0].__setitem__(0, True)]
        for mutate in mutations:
            recorder = Recorder()
            with self.subTest(mutation=mutate), self.assertRaises(api.InferenceError):
                self.run_case(raw=self.mutated(mutate), recorder=recorder)
            self.assertFalse(recorder.calls)
        with self.assertRaises(api.InferenceError):
            self.run_case(raw=self.raw.replace(b'"source_index":0', b'"source_index":0,"source_index":0', 1))
        with self.assertRaises(api.InferenceError):
            self.run_case(raw=self.raw.replace(b'[[[0.0,', b'[[[NaN,', 1))

    def test_source_hash_and_complete_metadata_admission_before_stream_or_model(self):
        recorder, sink = Recorder(), io.BytesIO()
        with self.assertRaises(api.InferenceError):
            self.run_case(digest="0" * 64, recorder=recorder, sink=sink)
        self.assertEqual((recorder.calls, sink.getvalue()), ([], b""))
        arguments = dict(self.arguments, max_trial_frames=2)
        with self.assertRaises(api.InferenceError):
            self.run_case(arguments=arguments)
        for changed in ({"fold": True}, {"role": "train"}, {"census_sha256": "0" * 64}):
            with self.subTest(changed=changed), self.assertRaises((api.InferenceError, api.trials.AdmissionError)):
                self.run_case(arguments=dict(self.arguments, **changed))
        census = json.loads(self.census)
        census["assays"][1]["trials"].pop()
        incomplete = encode(census)
        with self.assertRaises(api.trials.AdmissionError):
            api._plan(incomplete, self.split, **dict(self.arguments, census_sha256=pin(incomplete)))

    def test_rejects_model_tail_drop_extra_output_and_invalid_values(self):
        class Bad:
            def __init__(self, which): self.which = which
            def __call__(self, fields, **kwargs):
                out = Recorder()(fields, **kwargs)
                if self.which == 0: out["neural"] = fields[:-1]
                if self.which == 1: out["behavior"] = out["behavior"] + out["behavior"][:1]
                if self.which == 2: out["behavior"][0][0] = float("inf")
                if self.which == 3: out["behavior"][0].pop()
                if self.which == 4: out["targets"] = "forbidden"
                return out
        for which in range(5):
            with self.subTest(which=which), self.assertRaises(api.InferenceError):
                self.run_case(recorder=Bad(which))

    def test_mutated_second_pass_trial_refused_before_model_call(self):
        alternate = self.raw.replace(b'[[[0.0,', b'[[[9.0,', 1)
        class Changing(io.BytesIO):
            def __init__(self, raw): super().__init__(raw); self.seeks = 0
            def seek(self, offset, whence=0):
                self.seeks += 1
                if self.seeks == 2:
                    super().seek(0); self.write(alternate)
                return super().seek(offset, whence)
        recorder = Recorder()
        with self.assertRaisesRegex(api.InferenceError, "source changed"):
            self.run_case(stream=Changing(self.raw), recorder=recorder)
        self.assertFalse(recorder.calls)

    def test_short_writes_complete_and_failed_writes_do_not_return_success(self):
        class Short(io.BytesIO):
            def write(self, raw): return super().write(raw[:97])
        result, _, sink = self.run_case(sink=Short())
        self.assertEqual(result["output_sha256"], pin(sink.getvalue()))
        class Failed(io.BytesIO):
            def write(self, raw): return 0
        recorder = Recorder()
        with self.assertRaises(api.InferenceError):
            self.run_case(sink=Failed(), recorder=recorder)
        self.assertFalse(recorder.calls)
        with self.assertRaises(api.InferenceError):
            self.run_case(max_output_bytes=50)

    def test_line_and_extent_limits_and_unterminated_json(self):
        for raw in (self.raw[:-1], self.raw + b"x", b" " * (api.LINE_LIMIT + 1) + b"\n"):
            recorder = Recorder()
            with self.subTest(length=len(raw)), self.assertRaises(api.InferenceError):
                self.run_case(raw=raw, recorder=recorder)
            self.assertFalse(recorder.calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
