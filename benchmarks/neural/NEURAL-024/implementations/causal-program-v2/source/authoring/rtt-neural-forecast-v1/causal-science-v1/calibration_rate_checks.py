"""Invented controls for a future isolated qualification; not run at authoring.

run(candidate, np) receives the independently loaded candidate module and NumPy.
It opens no data files.  Its fake NPZ loader serves only invented in-memory data.
The one complete protocol walk retains only the current metadata request/reply.
"""

import io
import json


GUARD_NAMES = (
    "hand_rate_excludes_first_ten_calibration_rows",
    "zero_counts_have_positive_half_count_rate",
    "maximum_uint32_sum_is_exact_before_smoothing",
    "calibration_shape_dtype_and_clock_rejections",
    "only_calibration_file_and_exact_npz_members",
    "bounded_strict_json_lines",
    "exact_initialize_contract",
    "prediction_schema_sequence_clock_and_observation_rejections",
    "revealed_counts_cannot_update_fixed_rates",
    "all_22100_rounds_warmup_boundary_and_final_stop",
    "canonical_finite_reply_and_newline_byte_cap",
    "ready_initialized_order_and_premature_eof_failure",
)


def run(candidate, np):
    completed = []
    counts = np.zeros((3000, 96), dtype=np.uint32)
    # Absolute native time: the first prediction is at relative time 60 s.
    edges = 745.0 + np.arange(3001, dtype=np.float64) / 50.0
    synthetic_predictions = 0

    def reject(function):
        try:
            function()
        except (candidate.ProtocolError, ValueError, TypeError, OverflowError):
            return
        raise AssertionError("invalid invented input accepted")

    def done(name):
        assert name == GUARD_NAMES[len(completed)]
        completed.append(name)

    def session():
        state = candidate.FixedRateSession([0.25] * 96, 60.0)
        assert state.handle(dict(candidate.INITIALIZE)) == {
            "status": "initialized", "protocol": "NEURAL024-causal-v1"
        }
        return state

    def request(seq, previous_count=0):
        return {
            "protocol": "NEURAL024-causal-v1", "status": "predict",
            "sequence": seq, "target_bin": 3000 + seq,
            "interval": [60.0 + seq / 50.0, 60.0 + (seq + 1) / 50.0],
            "scored": seq >= 10, "nonce": format(seq, "032x"),
            "observation": None if seq == 0 else {
                "target_bin": 2999 + seq, "counts": [previous_count] * 96
            },
        }

    counts[:] = 2
    counts[:10] = 4294967295
    means, first_begin = candidate.calibration_model(np, counts, edges)
    assert means == [(5980 + 0.5) / 2990.5] * 96
    assert first_begin == 60.0
    done("hand_rate_excludes_first_ten_calibration_rows")

    counts[:] = 0
    means, _ = candidate.calibration_model(np, counts, edges)
    assert means == [0.5 / 2990.5] * 96 and all(x > 0 for x in means)
    done("zero_counts_have_positive_half_count_rate")

    counts[:] = 4294967295
    means, _ = candidate.calibration_model(np, counts, edges)
    assert means == [(2990 * 4294967295 + 0.5) / 2990.5] * 96
    done("maximum_uint32_sum_is_exact_before_smoothing")

    reject(lambda: candidate.calibration_model(np, counts[:-1], edges))
    reject(lambda: candidate.calibration_model(np, counts[:, :-1], edges))
    reject(lambda: candidate.calibration_model(np, counts.astype(np.int64), edges))
    reject(lambda: candidate.calibration_model(np, counts, edges[:-1]))
    reject(lambda: candidate.calibration_model(np, counts, edges.astype(np.float32)))
    changed = edges.copy()
    changed[17] = changed[16]
    reject(lambda: candidate.calibration_model(np, counts, changed))
    changed[17] = float("nan")
    reject(lambda: candidate.calibration_model(np, counts, changed))
    changed[17] = float("inf")
    reject(lambda: candidate.calibration_model(np, counts, changed))
    done("calibration_shape_dtype_and_clock_rejections")

    opened = []

    class FakeArchive:
        files = ["counts", "bin_edges_seconds"]

        def __enter__(self):
            return self

        def __exit__(self, *unused):
            return False

        def __getitem__(self, name):
            return {"counts": counts, "bin_edges_seconds": edges}[name]

    class FakeNumpy:
        def __getattr__(self, name):
            return getattr(np, name)

        def load(self, path, **kwargs):
            opened.append((path, kwargs))
            return FakeArchive()

    loaded = candidate.load_calibration(FakeNumpy())
    assert loaded[0] == means and loaded[1] == 60.0
    assert opened == [("/training/calibration_counts.npz", {"allow_pickle": False})]
    FakeArchive.files = ["counts", "bin_edges_seconds", "extra"]
    reject(lambda: candidate.load_calibration(FakeNumpy()))
    FakeArchive.files = ["counts", "counts", "bin_edges_seconds"]
    reject(lambda: candidate.load_calibration(FakeNumpy()))
    assert all(path == "/training/calibration_counts.npz" for path, _ in opened)
    done("only_calibration_file_and_exact_npz_members")

    assert candidate.read_message(io.BytesIO(b'{"ok":1}\n')) == {"ok": 1}
    for raw in (b'', b'{"ok":1}', b'[]\n', b'{"x":1,"x":2}\n',
                b'{"x":NaN}\n', b'{"x":Infinity}\n',
                b' ' * 4096 + b'\n', b'\xff\n'):
        reject(lambda raw=raw: candidate.read_message(io.BytesIO(raw)))
    done("bounded_strict_json_lines")

    for change in ({"rounds": 22100.0}, {"channels": 95},
                   {"status": "predict"}, {"extra": None}):
        state = candidate.FixedRateSession([0.25] * 96, 60.0)
        bad = dict(candidate.INITIALIZE)
        bad.update(change)
        reject(lambda: state.handle(bad))
        assert state.phase == "initialize" and state.next_sequence == 0
    done("exact_initialize_contract")

    for field, value in (
        ("protocol", "wrong"), ("status", "stop"), ("sequence", True),
        ("sequence", 1), ("target_bin", 3001), ("scored", 0),
        ("scored", True), ("nonce", "g" * 32), ("nonce", "0" * 31),
        ("interval", [60.01, 60.02]), ("interval", [60.0, 60.0]),
        ("interval", [60.0, float("inf")]), ("interval", [True, 60.02]),
        ("observation", {"target_bin": 2999, "counts": [0] * 96}),
        ("extra", None),
    ):
        state = session()
        bad = request(0)
        bad[field] = value
        reject(lambda: state.handle(bad))
        assert state.next_sequence == 0 and state.previous_end == 60.0
    for bad_observation in (
        None, {"target_bin": 2999, "counts": [0] * 96},
        {"target_bin": 3000.0, "counts": [0] * 96},
        {"target_bin": 3000, "counts": [0] * 95},
        *({"target_bin": 3000, "counts": [x] + [0] * 95}
          for x in (True, 0.0, -1, 4294967296)),
    ):
        state = session()
        state.handle(request(0))
        bad = request(1)
        bad["observation"] = bad_observation
        reject(lambda: state.handle(bad))
        assert state.next_sequence == 1
    done("prediction_schema_sequence_clock_and_observation_rejections")

    zero_state, large_state = session(), session()
    for seq in range(3):
        a = zero_state.handle(request(seq, 0))
        b = large_state.handle(request(seq, 4294967295))
        assert a == b and a["mean_counts"] == [0.25] * 96
    done("revealed_counts_cannot_update_fixed_rates")

    state = session()
    reject(lambda: state.handle({"protocol": "NEURAL024-causal-v1", "status": "stop",
                                 "observation": {"target_bin": 25099, "counts": [0] * 96}}))
    for seq in range(22100):
        valid = request(seq, seq % 2)
        if seq in (9, 10):
            bad = dict(valid)
            bad["scored"] = not valid["scored"]
            reject(lambda: state.handle(bad))
            assert state.next_sequence == seq
        reply = state.handle(valid)
        synthetic_predictions += 1
        assert set(reply) == {"sequence", "nonce", "mean_counts"}
        assert reply["sequence"] == seq and reply["nonce"] == format(seq, "032x")
        assert reply["mean_counts"] == [0.25] * 96
    assert state.next_sequence == 22100 and state.phase == "stop"
    reject(lambda: state.handle(request(22100)))
    stop = {"protocol": "NEURAL024-causal-v1", "status": "stop",
            "observation": {"target_bin": 25098, "counts": [0] * 96}}
    reject(lambda: state.handle(stop))
    assert state.phase == "stop"
    stop["observation"]["target_bin"] = 25099
    assert state.handle(stop) == {"status": "stopped"}
    reject(lambda: state.handle(stop))
    done("all_22100_rounds_warmup_boundary_and_final_stop")

    assert candidate.encode_message({"b": 2, "a": "\u00e9"}) == b'{"a":"\\u00e9","b":2}\n'
    encoded = candidate.encode_message({"sequence": 22099, "nonce": "f" * 32,
                                        "mean_counts": means})
    assert len(encoded) <= 4096 and encoded.endswith(b"\n")
    assert set(json.loads(encoded)) == {"sequence", "nonce", "mean_counts"}
    reject(lambda: candidate.encode_message({"x": float("nan")}))
    reject(lambda: candidate.encode_message({"x": "a" * 4096}))
    done("canonical_finite_reply_and_newline_byte_cap")

    out = io.BytesIO()
    inp = io.BytesIO(candidate.encode_message(dict(candidate.INITIALIZE)))
    reject(lambda: candidate.run_session(inp, out, [0.25] * 96, 60.0))
    assert out.getvalue() == (
        b'{"status":"ready"}\n'
        b'{"protocol":"NEURAL024-causal-v1","status":"initialized"}\n'
    )
    done("ready_initialized_order_and_premature_eof_failure")

    assert tuple(completed) == GUARD_NAMES
    return {"status": "passed", "guard_count": len(completed),
            "guards": completed, "invented_only": True,
            "complete_lifecycle_predictions": synthetic_predictions,
            "empirical_data_files_opened": 0}
