"""Independent generated controls; no authentic source pickle or model is run."""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import pickle
import shutil
import stat
import struct
import sys
import tempfile
import types
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("inputs", HERE / "inputs.py")
inputs = importlib.util.module_from_spec(spec)
sys.modules["inputs"] = inputs
spec.loader.exec_module(inputs)
decoder = inputs.load_decoder()
spec = importlib.util.spec_from_file_location("preprocess", HERE / "preprocess.py")
preprocess = importlib.util.module_from_spec(spec)
sys.modules["preprocess"] = preprocess
spec.loader.exec_module(preprocess)
spec = importlib.util.spec_from_file_location("results", HERE / "results.py")
results = importlib.util.module_from_spec(spec)
sys.modules["results"] = results
spec.loader.exec_module(results)

RATS = ("achilles", "buddy", "cicero", "gatsby")
SOURCE_SHA = "29dffd951853a98615827e7b8f3507907f9e0f0ef67e875410778ab4aadd42ab"
LAYOUTS = {
    "achilles": {"neural": ((10000, 120), (1, 10178), 0, 1221360),
                 "continuous_index": ((10000, 3), (3, 1), 0, 30534)},
    "buddy": {"neural": ((6577, 48), (48, 1), 0, 315696),
              "continuous_index": ((6577, 3), (3, 1), 0, 19731)},
    "cicero": {"neural": ((10000, 55), (55, 1), 2035000, 2608705),
               "continuous_index": ((10000, 3), (3, 1), 111000, 142293)},
    "gatsby": {"neural": ((10000, 66), (66, 1), 165000, 1123716),
               "continuous_index": ((10000, 3), (3, 1), 7500, 51078)},
}


def tensor(shape=(3, 2), stride=(1, 5), offset=2, count=13):
    return {"shape": shape, "stride": stride, "storage_offset": offset,
            "storage_elements": count, "dtype": "<f4",
            "raw": np.arange(count, dtype="<f4").tobytes()}


def storage_payload(values, *, pid=None, count=None, protocol=1001, little=True, tail=b""):
    """Minimal independent legacy Torch storage writer, without importing Torch."""
    values = np.asarray(values, dtype="<f4")
    if pid is None:
        pid = ("storage", "float32", "generated-storage", "cpu", len(values), None)
    body = io.BytesIO()
    for value in (119547037146038801333356, protocol,
                  {"protocol_version": 1001, "little_endian": little}):
        pickle.dump(value, body, protocol=2)
    # BINPERSID applies to the explicit tuple; the reader never instantiates a
    # Torch class or imports Torch for this generated primitive identity.
    encoded_pid = pickle.dumps(pid, protocol=2)
    body.write(encoded_pid[:-1] + b"Q.")
    pickle.dump([pid[2]], body, protocol=2)
    body.write(struct.pack("<Q", len(values) if count is None else count))
    body.write(values.tobytes()); body.write(tail)
    return body.getvalue()


class AnalyticFixtureBackend:
    """Deliberately simple generated kernel; not an Elephant approximation."""
    provenance = {"implementation": "generated-three-tap-analytic-control", "native_elephant_parity": False}

    def __init__(self): self.calls = []

    def __call__(self, events, length):
        self.calls.append((np.array(events, copy=True), length))
        # Independently sum finite-support impulse contributions with zero
        # outside support. This fixture says nothing about Elephant boundaries.
        result = np.zeros((length, 1), dtype=np.float64)
        for event in events:
            for shift, weight in ((-1, 0.25), (0, 0.5), (1, 0.25)):
                if 0 <= event + shift < length:
                    result[event + shift, 0] += weight
        return result


def pinned_author_function(backend):
    """Extract exact function syntax without executing heavy author imports."""
    path = HERE / "reference/rat_utils.py"
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != "e90bac90d46b91a13604728ba893aa36343c2fd2a4c634a4c0dcf84b0b461623":
        raise AssertionError("pinned author function changed")
    tree = ast.parse(body, filename=str(path))
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == "convert_spikes_to_rates"]
    if len(selected) != 1: raise AssertionError("exact source function missing")
    calls = {"kernel": [], "train": [], "rate": [], "construct": []}
    def gaussian(width):
        calls["kernel"].append(width)
        return {"generated_kernel_width": width}
    def spike_train(events, *, units, t_stop):
        calls["train"].append((np.array(events, copy=True), units, t_stop))
        return types.SimpleNamespace(events=np.array(events), length=t_stop)
    def rate(train, *, kernel, sampling_period):
        calls["rate"].append((kernel, sampling_period))
        return types.SimpleNamespace(magnitude=backend(train.events, train.length))
    def construct(**kwargs):
        calls["construct"].append(kwargs)
        return types.SimpleNamespace(**kwargs)
    namespace = {"np": np, "PCA": preprocess.PCA, "GaussianKernel": gaussian, "ms": 1.0,
                 "neo": types.SimpleNamespace(SpikeTrain=spike_train), "instantaneous_rate": rate,
                 "MARBLE": types.SimpleNamespace(construct_dataset=construct)}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["convert_spikes_to_rates"], calls


def provenance():
    return {"embedding_producer_sha256": "1" * 64, "preprocessing_receipt_sha256": "2" * 64,
            "model_or_fit_receipt_sha256": "3" * 64, "upstream_exposure": "unknown",
            "historical_checkpoint_lineage": "unresolved"}


def canonical_pin(document):
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def pinned_author_decoder():
    path = HERE / "reference/rat_utils.py"
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != "e90bac90d46b91a13604728ba893aa36343c2fd2a4c634a4c0dcf84b0b461623":
        raise AssertionError("author helper changed")
    tree = ast.parse(body, filename=str(path))
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in ("find_sequences", "decoding_pos_dir")]
    if len(selected) != 2: raise AssertionError("original decoding functions missing")
    # CEBRA's floating-label KNN decoder delegates to sklearn. This deliberately
    # supplies that exact sklearn decoder without pretending CEBRA was installed.
    from sklearn import metrics
    namespace = {"np": np, "sklearn": types.SimpleNamespace(metrics=metrics),
                 "cebra": types.SimpleNamespace(KNNDecoder=results.KNeighborsRegressor)}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["decoding_pos_dir"]


class RestrictedDecoderControls(unittest.TestCase):
    def test_retained_decoder_exact_hash_and_only_declared_globals(self):
        self.assertEqual(hashlib.sha256((HERE / "dependencies/intake.py").read_bytes()).hexdigest(),
                         "de8eee64c1400251d18a59bd8c09c8138e352f39f91d15b40201002b19c07d07")
        reader = decoder.DataReader(io.BytesIO())
        self.assertIs(reader.find_class("torch._utils", "_rebuild_tensor_v2"), decoder.rebuild_tensor)
        for module, name in (("os", "system"), ("builtins", "eval"), ("torch", "load"), ("numpy", "dtype")):
            with self.assertRaises(ValueError): reader.find_class(module, name)

    def test_malicious_pickle_global_is_refused_without_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "never-created"
            class Malicious:
                def __reduce__(self):
                    return (os.system, ("touch " + str(sentinel),))
            payload = pickle.dumps(Malicious(), protocol=2)
            with self.assertRaises(ValueError): decoder.DataReader(io.BytesIO(payload)).load()
            self.assertFalse(sentinel.exists())

    def test_primitive_and_storage_persistent_identity_boundaries(self):
        with self.assertRaises(ValueError): decoder.Primitive(io.BytesIO()).persistent_load(("storage",))
        reader = decoder.StorageSpecReader(io.BytesIO())
        good = ("storage", "float32", "generated", "cpu", 9, None)
        self.assertEqual(reader.persistent_load(good), good)
        for bad in (("storage",), ("storage", "float64", "generated", "cpu", 9, None),
                    ("storage", "float32", "generated", "cuda:0", 9, None),
                    ("storage", "float32", "generated", "cpu", True, None),
                    ("storage", "float32", "generated", "cpu", 6000001, None),
                    ("storage", "float32", "generated", "cpu", 9, "view")):
            with self.assertRaises(ValueError): reader.persistent_load(bad)

    def test_legacy_storage_payload_extent_version_and_endianness(self):
        values = np.array([0.0, -1.5, 2.25, 9.0], dtype="<f4")
        raw, count = decoder.storage_from_bytes(storage_payload(values))
        self.assertEqual(count, 4)
        np.testing.assert_array_equal(np.frombuffer(raw, dtype="<f4"), values)
        for body in (storage_payload(values, count=5), storage_payload(values, little=False),
                     storage_payload(values, protocol=1002), storage_payload(values, tail=b"extra"),
                     storage_payload(values)[:-1]):
            with self.assertRaises((ValueError, EOFError, pickle.UnpicklingError)):
                decoder.storage_from_bytes(body)

    def test_rebuild_tensor_refuses_hooks_gradient_and_overrun(self):
        raw = np.arange(13, dtype="<f4").tobytes()
        rebuilt = decoder.rebuild_tensor((raw, 13), 2, (3, 2), (1, 5), False, {})
        np.testing.assert_array_equal(inputs.tensor_view(rebuilt), [[2, 7], [3, 8], [4, 9]])
        for offset, shape, stride, grad, hooks in ((9, (3, 2), (1, 5), False, {}),
                (0, (3, 2), (0, 5), False, {}), (0, (3, 2), (1, 5), True, {}),
                (0, (3, 2), (1, 5), False, {"hook": "forbidden"}), (0, (3,), (1,), False, {})):
            with self.assertRaises(ValueError):
                decoder.rebuild_tensor((raw, 13), offset, shape, stride, grad, hooks)

    def test_wrong_file_size_rejected_before_pickle_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "generated.pkl"
            path.write_bytes(pickle.dumps({"not": "the release"}))
            with mock.patch.object(decoder, "DataReader", side_effect=AssertionError("must not decode")):
                with self.assertRaises(ValueError): decoder.read_pinned(path)


class TensorViewControls(unittest.TestCase):
    def test_noncontiguous_nonzero_offset_and_exact_last_element(self):
        value = tensor(shape=(3, 2), stride=(1, 5), offset=2, count=10)
        view = inputs.tensor_view(value, ((3, 2), (1, 5), 2, 10))
        np.testing.assert_array_equal(view, [[2, 7], [3, 8], [4, 9]])
        self.assertFalse(view.flags.c_contiguous)
        self.assertFalse(view.flags.writeable)

    def test_shape_stride_offset_extent_type_and_schema_fail_closed(self):
        valid = tensor()
        changes = [{"shape": [3, 2]}, {"shape": (True, 2)}, {"stride": (0, 5)},
                   {"stride": (-1, 5)}, {"storage_offset": -1}, {"storage_offset": 6},
                   {"storage_elements": True}, {"storage_elements": 6000001}, {"dtype": ">f4"},
                   {"raw": valid["raw"][:-1]}, {"raw": bytearray(valid["raw"])}, {"extra": 1}]
        for change in changes:
            with self.assertRaises(inputs.InputError): inputs.tensor_view({**valid, **change})
        with self.assertRaises(inputs.InputError): inputs.tensor_view(valid, ((3, 2), (2, 3), 2, 13))

    def test_complete_recorded_layout_inventory_and_achilles_stride_are_fixed(self):
        self.assertEqual(inputs.LAYOUTS, LAYOUTS)
        # Small analogue of Achilles: time stride1, neuron stride longer than
        # the exposed time window. Flatten+reshape would return wrong values.
        view = inputs.tensor_view(tensor((4, 3), (1, 6), 0, 18))
        np.testing.assert_array_equal(view, [[0, 6, 12], [1, 7, 13], [2, 8, 14], [3, 9, 15]])
        self.assertFalse(np.array_equal(view, np.arange(12).reshape(4, 3)))

    def test_release_requires_all_named_rats_and_exact_tensor_layouts(self):
        with self.assertRaises(inputs.InputError): inputs.validate_release({})
        fake = {rat: {"neural": tensor(), "continuous_index": tensor()} for rat in RATS}
        with self.assertRaises(inputs.InputError): inputs.validate_release(fake)
        reordered = {rat: fake[rat] for rat in reversed(RATS)}
        with self.assertRaises(inputs.InputError): inputs.validate_release(reordered)


class SourceSupportControls(unittest.TestCase):
    def test_canonical_row_identity_bounds_and_source_identity(self):
        identity = inputs.row_id("achilles", 9999)
        self.assertEqual(identity, f"rat_data:{SOURCE_SHA}:achilles:row:9999")
        self.assertEqual(inputs.row_index(identity), 9999)
        for invalid in (-1, 10000, True):
            with self.assertRaises(inputs.InputError): inputs.row_id("achilles", invalid)
        for invalid in (identity.replace(SOURCE_SHA, "0" * 64), identity.replace("9999", "09999"),
                        inputs.row_id("gatsby", 9999), identity + "\n"):
            with self.assertRaises(inputs.InputError): inputs.row_index(invalid)

    def test_released_decoding_source_support_loses_terminal_rows_without_crossing_split(self):
        support = inputs.recipe_support(inputs.DECODING)
        self.assertEqual(support["rat"], "achilles")
        self.assertEqual(support["pca_components"], 20)
        self.assertEqual(support["recording_bin_width_seconds"], 0.025)
        self.assertEqual(support["helper_event_index_step_ms"], 1.0)
        self.assertEqual(support["helper_gaussian_sigma_ms"], 10.0)
        self.assertEqual(support["equivalent_recording_bin_sigma_seconds"], 0.25)
        self.assertFalse(support["absolute_recording_time_or_bin_phase_known"])
        self.assertFalse(support["figure5d_2000_query_eligible"])
        train, query = support["segments"]["training"], support["segments"]["query"]
        self.assertEqual(train["marble_anchor_source_row_interval"], [0, 7999])
        self.assertEqual(train["marble_forward_partner_source_row_interval"], [1, 8000])
        self.assertEqual(query["marble_anchor_source_row_interval"], [8000, 9999])
        self.assertEqual(query["marble_forward_partner_source_row_interval"], [8001, 10000])
        self.assertEqual((train["marble_rows"], query["marble_rows"]), (7999, 1999))
        self.assertEqual(query["omitted_terminal_anchor_source_row"], 9999)

    def test_paper_recipe_unknowns_remain_unavailable_and_four_rat_consistency_stays_separate(self):
        with self.assertRaises(inputs.InputError): inputs.recipe_support(inputs.PAPER)
        with self.assertRaises(inputs.InputError): inputs.recipe_support("invented-padded-paper")
        for rat in RATS[1:]:
            with self.assertRaises(inputs.InputError): inputs.recipe_support(inputs.DECODING, rat)
        for rat in RATS:
            support = inputs.recipe_support(inputs.CONSISTENCY, rat)
            self.assertEqual(support["pca_components"], 10)
            self.assertEqual(set(support["segments"]), {"whole"})
            self.assertEqual(support["segments"]["whole"]["marble_rows"], LAYOUTS[rat]["neural"][0][0] - 1)
            self.assertFalse(support["figure5d_2000_query_eligible"])

    def test_existing_endpoint_still_rejects_1999_rows_before_decoding(self):
        path = HERE.parent / "figure5d-endpoint-v1/score.py"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         "5f3938de84672f0a146fba9f807d17e3275c812b2699f56fd03833114dbd8921")
        spec = importlib.util.spec_from_file_location("marble_retained_endpoint_under_test", path)
        endpoint = importlib.util.module_from_spec(spec); spec.loader.exec_module(endpoint)
        support = {"schema": "marble_figure5d_support_v1", "task_id": "PAPER-paper-method-034",
                   "panel": "Figure 5d", "animal": "rat1", "unit": "m", "source_sha256": SOURCE_SHA,
                   "training_row_ids": inputs.source_rows("achilles", 0, 7999),
                   "query_row_ids": inputs.source_rows("achilles", 8000, 9999)}
        with self.assertRaisesRegex(ValueError, "wrong number of rows"):
            endpoint.support_check(support)


class PreprocessingControls(unittest.TestCase):
    def test_nonzero_magnitudes_collapse_once_and_time_neuron_orientation_is_preserved(self):
        neural = np.array([[0, 1], [2.5, 0], [-3, 0], [0, -0.5], [0, 0], [0, 4]], dtype=np.float32)
        before = neural.copy()
        backend = AnalyticFixtureBackend()
        rates, receipt = preprocess.source_rates(neural, backend)
        np.testing.assert_array_equal(neural, before)
        np.testing.assert_array_equal(backend.calls[0][0], [1, 2])
        np.testing.assert_array_equal(backend.calls[1][0], [0, 3, 5])
        self.assertEqual([length for _, length in backend.calls], [6, 6])
        np.testing.assert_array_equal(rates[:, 0], [0.25, 0.75, 0.75, 0.25, 0, 0])
        np.testing.assert_array_equal(rates[:, 1], [0.5, 0.25, 0.25, 0.5, 0.5, 0.5])
        self.assertEqual(receipt["nonzero_events_per_neuron"], [2, 3])
        self.assertEqual(receipt["negative_values"], 2)
        self.assertEqual(receipt["nonintegral_values"], 2)
        self.assertFalse(receipt["backend"]["native_elephant_parity"])

    def test_backend_geometry_provenance_and_nonfinite_values_fail_closed(self):
        neural = np.zeros((7, 3), dtype=np.float64)
        for bad in (np.full((7, 3), np.nan), np.zeros((1, 3)), np.zeros((7, 121)),
                    np.zeros((7, 3), dtype=bool)):
            with self.assertRaises(inputs.InputError): preprocess.source_rates(bad, AnalyticFixtureBackend())
        with self.assertRaises(inputs.InputError): preprocess.source_rates(neural, lambda *_: np.zeros((7, 1)))
        for value in (np.zeros((6, 1)), np.zeros(7), np.zeros((7, 1), dtype=np.int64), np.full((7, 1), np.nan)):
            class BadBackend:
                provenance = {"implementation": "generated-bad-backend"}
                def __call__(self, *_): return value
            with self.assertRaises(inputs.InputError): preprocess.source_rates(neural, BadBackend())

    def test_training_pca_query_transform_and_unscaled_derivative_are_exact(self):
        # Orthogonal cube with known principal axes; no source observations.
        cube = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], dtype=float)
        train = cube * [3, 2, 1] + [10, 20, 30]
        rows = inputs.source_rows("achilles", 10, 18)
        segment, pca = preprocess.project_segment(train, rows, 2)
        np.testing.assert_allclose(pca.mean_, [10, 20, 30], rtol=0, atol=1e-12)
        np.testing.assert_allclose(np.abs(pca.components_), [[1, 0, 0], [0, 1, 0]], atol=1e-12)
        coordinates = (train - [10, 20, 30]) @ pca.components_.T
        np.testing.assert_allclose(segment["anchor"], coordinates[:-1], atol=1e-12)
        np.testing.assert_allclose(segment["vector"], coordinates[1:] - coordinates[:-1], atol=1e-12)
        self.assertEqual(segment["row_ids"], rows[:-1])
        self.assertEqual(segment["forward_partner_row_ids"], rows[1:])
        self.assertEqual(segment["omitted_terminal_anchor"], rows[-1])
        before_mean, before_components = pca.mean_.copy(), pca.components_.copy()
        query_rates = train[:5] + [100, -40, 9]
        query_rows = inputs.source_rows("achilles", 80, 85)
        with mock.patch.object(pca, "fit", side_effect=AssertionError("query refit")), \
                mock.patch.object(pca, "fit_transform", side_effect=AssertionError("query refit")):
            query, same = preprocess.project_segment(query_rates, query_rows, 2, pca)
        self.assertIs(same, pca)
        self.assertFalse(query["pca_fitted_here"])
        expected = (query_rates - before_mean) @ before_components.T
        np.testing.assert_allclose(query["anchor"], expected[:-1], atol=1e-12)
        np.testing.assert_allclose(query["vector"], np.diff(expected, axis=0), atol=1e-12)
        np.testing.assert_array_equal(pca.mean_, before_mean)
        np.testing.assert_array_equal(pca.components_, before_components)
        receipt = preprocess.pca_receipt(pca, rows)
        self.assertEqual(receipt["fit_row_ids"], rows)
        self.assertFalse(receipt["historical_seed_or_PCA_state_verified"])

    def test_exact_author_function_differential_under_explicit_generated_backend(self):
        rng = np.random.default_rng(88)
        train = (rng.random((31, 5)) < 0.3).astype(float)
        train[2, 1] = -2.5; train[4, 3] = 7.0
        labels = np.arange(31 * 3, dtype=float).reshape(31, 3)
        author_backend, adapter_backend = AnalyticFixtureBackend(), AnalyticFixtureBackend()
        original, calls = pinned_author_function(author_backend)
        author_data, author_labels, author_pca = original(train.T, labels, pca_n=3)
        rates, _ = preprocess.source_rates(train, adapter_backend)
        rows = inputs.source_rows("achilles", 0, len(train))
        adapter_data, adapter_pca = preprocess.project_segment(rates, rows, 3)
        np.testing.assert_allclose(adapter_data["anchor"], author_data.anchor, rtol=1e-12, atol=1e-12)
        np.testing.assert_allclose(adapter_data["vector"], author_data.vector, rtol=1e-12, atol=1e-12)
        np.testing.assert_array_equal(author_labels, labels[:-1])
        np.testing.assert_allclose(adapter_pca.components_, author_pca.components_, rtol=1e-12, atol=1e-12)
        self.assertEqual(calls["kernel"], [10.0])
        self.assertEqual(calls["construct"][0]["k"], 15)
        self.assertEqual(calls["construct"][0]["delta"], 1.5)
        self.assertEqual([t[1:] for t in calls["train"]], [("ms", 31)] * 5)
        self.assertEqual([call[1] for call in calls["rate"]], [1.0] * 5)
        for (left, left_n), (right, right_n) in zip(author_backend.calls, adapter_backend.calls):
            np.testing.assert_array_equal(left, right)
            self.assertEqual(left_n, right_n)
        query = (rng.random((13, 5)) < 0.4).astype(float)
        query_labels = np.arange(39, dtype=float).reshape(13, 3)
        author_query, author_y, returned_pca = original(query.T, query_labels, pca=author_pca)
        query_rates, _ = preprocess.source_rates(query, adapter_backend)
        query_rows = inputs.source_rows("achilles", 100, 113)
        adapter_query, same_pca = preprocess.project_segment(query_rates, query_rows, 3, adapter_pca)
        self.assertIs(returned_pca, author_pca); self.assertIs(same_pca, adapter_pca)
        np.testing.assert_allclose(adapter_query["anchor"], author_query.anchor, rtol=1e-12, atol=1e-12)
        np.testing.assert_allclose(adapter_query["vector"], author_query.vector, rtol=1e-12, atol=1e-12)
        np.testing.assert_array_equal(author_y, query_labels[:-1])

    def test_projection_requires_nonempty_difference_support_and_unique_rows(self):
        for rates, rows, dimension in ((np.zeros((1, 3)), ["one"], 1),
                (np.zeros((3, 3)), ["one", "one", "two"], 2),
                (np.zeros((3, 3)), ["one", "two"], 2),
                (np.full((3, 3), np.nan), ["one", "two", "three"], 2),
                (np.zeros((3, 3)), ["one", "two", "three"], True)):
            with self.assertRaises(inputs.InputError): preprocess.project_segment(rates, rows, dimension)

    def test_original_wrapper_refuses_wrong_orientation_or_missing_source_rows_before_backend(self):
        backend = mock.Mock(side_effect=AssertionError("backend must not run"))
        with self.assertRaises(inputs.InputError):
            preprocess.released_decoding(np.zeros((120, 10000)), inputs.source_rows("achilles", 0, 10000), backend)
        with self.assertRaises(inputs.InputError):
            preprocess.released_decoding(np.zeros((10000, 120)), inputs.source_rows("achilles", 0, 9999), backend)
        backend.assert_not_called()

    def test_native_backend_requires_explicit_installed_version_map_without_fallback(self):
        with self.assertRaises(inputs.InputError): preprocess.ElephantBackend({})
        expected = {package: "generated-version" for package in preprocess.ElephantBackend.PACKAGES}
        with mock.patch.object(preprocess.importlib.metadata, "version", return_value="different-version"):
            with self.assertRaises(inputs.InputError): preprocess.ElephantBackend(expected)

    def test_complete_generated_achilles_wrapper_preserves_split_and_records_1999_refusal(self):
        neural = ((np.arange(10000)[:, None] + 7 * np.arange(120)[None, :]) % 97 == 0).astype(np.float32)
        neural[7999, 0] = -2.5
        neural[8000, 0] = 0.0
        backend = AnalyticFixtureBackend()
        result = preprocess.released_decoding(neural, inputs.source_rows("achilles", 0, 10000), backend)
        train, query = result["segments"]["training"], result["segments"]["query"]
        self.assertEqual(train["anchor"].shape, (7999, 20))
        self.assertEqual(query["anchor"].shape, (1999, 20))
        self.assertEqual(query["vector"].shape, (1999, 20))
        self.assertEqual(train["row_ids"], inputs.source_rows("achilles", 0, 7999))
        self.assertEqual(query["row_ids"], inputs.source_rows("achilles", 8000, 9999))
        self.assertEqual(query["forward_partner_row_ids"], inputs.source_rows("achilles", 8001, 10000))
        self.assertEqual(result["pca_receipt"]["fit_row_ids"], inputs.source_rows("achilles", 0, 8000))
        self.assertTrue(train["pca_fitted_here"]); self.assertFalse(query["pca_fitted_here"])
        self.assertIn("1999", result["figure5d_bridge_refusal"])
        self.assertFalse(result["recipe"]["figure5d_2000_query_eligible"])
        self.assertEqual(len(backend.calls), 240)
        self.assertEqual([n for _, n in backend.calls], [8000] * 120 + [2000] * 120)
        np.testing.assert_array_equal(backend.calls[0][0], np.flatnonzero(neural[:8000, 0]))
        np.testing.assert_array_equal(backend.calls[120][0], np.flatnonzero(neural[8000:, 0]))

    def test_all_four_generated_consistency_wrappers_keep_whole_source_support_separate(self):
        for rat in RATS:
            with self.subTest(rat=rat):
                n, channels = LAYOUTS[rat]["neural"][0]
                neural = ((np.arange(n)[:, None] + 3 * np.arange(channels)[None, :]) % 83 == 0).astype(np.float32)
                backend = AnalyticFixtureBackend()
                rows = inputs.source_rows(rat, 0, n)
                result = preprocess.released_consistency(neural, rows, backend, rat)
                self.assertEqual(set(result["segments"]), {"whole"})
                segment = result["segments"]["whole"]
                self.assertEqual(segment["anchor"].shape, (n - 1, 10))
                self.assertEqual(segment["vector"].shape, (n - 1, 10))
                self.assertEqual(segment["row_ids"], rows[:-1])
                self.assertEqual(segment["forward_partner_row_ids"], rows[1:])
                self.assertEqual(result["pca_receipt"]["fit_row_ids"], rows)
                self.assertEqual([length for _, length in backend.calls], [n] * channels)
                self.assertIn("Figure5e", result["figure5d_bridge_refusal"])
                self.assertFalse(result["recipe"]["figure5d_2000_query_eligible"])


class ResultBridgeControls(unittest.TestCase):
    def test_native_six_outputs_match_pinned_helper_with_float_knn_delegation(self):
        rng = np.random.default_rng(213)
        training = rng.normal(size=(50, 32)).astype(np.float32)
        query = rng.normal(size=(19, 32)).astype(np.float32)
        labels = np.column_stack((np.linspace(0, 2, 50), np.arange(50) % 2, (np.arange(50) + 1) % 2)).astype(np.float32)
        targets = np.column_stack((np.linspace(0.3, 1.8, 19), np.arange(19) // 5 % 2,
                                   1 - np.arange(19) // 5 % 2)).astype(np.float32)
        author = pinned_author_decoder()
        expected = author(training, query, labels, targets)
        actual = results.decode_notebook_pair(training, query, labels, targets)
        for index in range(6):
            np.testing.assert_array_equal(actual[index], expected[index])

    def test_sequence_statistic_selects_endpoints_instead_of_whole_interval(self):
        labels = np.column_stack((np.arange(6), [0, 0, 0, 1, 1, 1], [1, 1, 1, 0, 0, 0])).astype(float)
        errors = np.array([1, 100, 5, 7, 100, 11], dtype=float)
        prediction = labels[:, :2].copy(); prediction[:, 0] += errors
        output = results.native_summary(prediction, labels)
        np.testing.assert_array_equal(output[5], [3, 9])
        self.assertEqual(results.sequences(labels[:, 1]), [(0, 2), (3, 5)])
        self.assertNotEqual(output[5][0], np.median(errors[:3]))

    @staticmethod
    def notebook_data():
        labels = np.column_stack((np.arange(10000) * 0.001,
                                  np.arange(10000) // 70 % 2, 1 - np.arange(10000) // 70 % 2)).astype(float)
        outputs = {}
        for method in results.METHODS:
            count = 1999 if method == "marble" else 2000
            prediction = labels[8000:8000 + count, :2].copy()
            prediction[:, 0] += 0.25
            if count == 2000: prediction[-1, 0] += 2000.0
            outputs[method] = results.native_summary(prediction, labels[8000:8000 + count])
        return labels, outputs, {method: provenance() for method in results.METHODS}

    def test_all_native_cebra_rows_survive_while_the_exact_plot_support_remains_1999(self):
        labels, outputs, declarations = self.notebook_data()
        report = results.adapt_notebook_outputs(outputs, labels, declarations)
        self.assertFalse(report["figure5d_eligible"])
        self.assertIsNone(report["scientific_improvement_awarded"])
        self.assertFalse(report["historical_checkpoint_or_training_exposure_verified"])
        self.assertEqual(report["cell15_pointplot"]["rows"], 1999)
        for method in results.METHODS:
            row = report["native_method_results"][method]
            plot = report["cell15_pointplot"]["methods"][method]
            count = 1999 if method == "marble" else 2000
            self.assertEqual(row["query_rows"], count)
            self.assertEqual(len(row["prediction_position_direction"]), count)
            self.assertEqual(len(row["absolute_position_errors_m"]), count)
            self.assertAlmostEqual(plot["mean_error_m"], 0.25, places=11)
            if method != "marble":
                self.assertAlmostEqual(row["absolute_position_errors_m"][-1], 2000.25, places=10)
                self.assertAlmostEqual(row["mean_absolute_position_error_m"], 1.25, places=10)
                self.assertAlmostEqual(plot["discarded_final_native_error_from_this_plot_only"], 2000.25, places=10)
            else:
                self.assertIsNone(plot["discarded_final_native_error_from_this_plot_only"])

    def test_wrong_marble_length_missing_methods_or_changed_helper_outputs_refused(self):
        labels, outputs, declarations = self.notebook_data()
        bad = dict(outputs); del bad["cebra-time"]
        with self.assertRaises(inputs.InputError): results.adapt_notebook_outputs(bad, labels, declarations)
        bad = dict(outputs); bad["marble"] = outputs["cebra-time"]
        with self.assertRaises(inputs.InputError): results.adapt_notebook_outputs(bad, labels, declarations)
        bad = dict(outputs); values = list(outputs["marble"]); values[4] = np.zeros(1999); bad["marble"] = values
        with self.assertRaises(inputs.InputError): results.adapt_notebook_outputs(bad, labels, declarations)
        wrong = {method: dict(provenance(), upstream_exposure="claimed_secret_holdout") for method in results.METHODS}
        with self.assertRaises(inputs.InputError): results.adapt_notebook_outputs(outputs, labels, wrong)

    def test_notebook_sem_preserves_original_float32_error_arithmetic(self):
        from scipy.stats import sem
        labels, _, declarations = self.notebook_data()
        labels = labels.astype(np.float32)
        outputs = {}
        for method in results.METHODS:
            n = 1999 if method == "marble" else 2000
            prediction = labels[8000:8000 + n, :2].copy()
            prediction[:, 0] += np.linspace(0.001, 0.237, n, dtype=np.float32)
            outputs[method] = results.native_summary(prediction, labels[8000:8000 + n])
        report = results.adapt_notebook_outputs(outputs, labels, declarations)
        for method in results.METHODS:
            self.assertEqual(outputs[method][4].dtype, np.dtype("float32"))
            self.assertEqual(report["native_method_results"][method]["median_plot_errorbar_sem_of_mean_errors_m"],
                             float(sem(outputs[method][4])))

    def test_finite_inputs_that_overflow_derived_metrics_are_rejected(self):
        labels = np.array([[0.0, 0, 1], [1.0, 1, 0], [2.0, 0, 1]])
        prediction = np.array([[1e308, 0], [1e308, 1], [1e308, 0]])
        with np.errstate(over="ignore", invalid="ignore"), self.assertRaises(inputs.InputError):
            results.native_summary(prediction, labels)

    @staticmethod
    def complete_fixture():
        support = {"schema": "marble_figure5d_support_v1", "task_id": "PAPER-paper-method-034",
                   "panel": "Figure 5d", "animal": "rat1", "unit": "m", "source_sha256": SOURCE_SHA,
                   "training_row_ids": inputs.source_rows("achilles", 0, 36),
                   "query_row_ids": inputs.source_rows("achilles", 8000, 10000)}
        labels = np.zeros((10000, 3), dtype=float)
        labels[:36, 0] = 1.0
        labels[9999, 0] = 2001.0
        training = {"row_ids": support["training_row_ids"], "embedding": np.ones((36, 32))}
        query = {"row_ids": support["query_row_ids"], "embedding": np.ones((2000, 32))}
        return support, training, query, labels

    def test_genuine_generated_2000_query_join_preserves_last_row_and_unchanged_endpoint(self):
        support, training, query, labels = self.complete_fixture()
        bound = results.figure5_inputs(support, canonical_pin(support), training, query, labels, provenance())
        self.assertEqual(set(bound["query"]), {"row_ids", "embedding"})
        self.assertEqual(bound["targets"]["position_m"][-1], 2001.0)
        report = results.score_complete(bound)
        self.assertEqual(report["score"]["samples"], 2000)
        # 1m error on1999rows and2000m on the last; omission changes the mean.
        self.assertAlmostEqual(report["score"]["mean_absolute_error_m"], 3999 / 2000, places=12)
        self.assertEqual(report["decoder"], {"neighbors": 36, "metric": "cosine", "weights": "uniform",
                                            "embedding_dimension": 32})
        self.assertFalse(report["historical_source_support_verified"])
        self.assertFalse(report["author_baseline_qualified"])
        self.assertIsNone(report["scientific_improvement_awarded"])

    def test_complete_bridge_rejects_1999_pin_order_source_and_query_labels(self):
        support, training, query, labels = self.complete_fixture()
        for bad_support, bad_training, bad_query, pin in (
                (dict(support, query_row_ids=support["query_row_ids"][:-1]), training,
                 {"row_ids": query["row_ids"][:-1], "embedding": query["embedding"][:-1]}, None),
                (support, training, query, "0" * 64),
                (support, training, dict(query, row_ids=list(reversed(query["row_ids"]))), None),
                (support, training, dict(query, position_m=[0.0] * 2000), None),
                (dict(support, source_sha256="0" * 64), training, query, None)):
            with self.assertRaises((inputs.InputError, ValueError)):
                results.figure5_inputs(bad_support, pin or canonical_pin(bad_support), bad_training,
                                       bad_query, labels, provenance())

    def test_source_graph_arguments_and_embedding_keep_exact_node_order_and_geometry(self):
        rates = np.arange(18, dtype=float).reshape(6, 3) + np.eye(6, 3)
        segment, _ = preprocess.project_segment(rates, inputs.source_rows("achilles", 20, 26), 2)
        seen = []
        def construct(**kwargs):
            seen.append(kwargs)
            return types.SimpleNamespace(sample_ind=np.arange(5), pos=kwargs["anchor"].astype(np.float32),
                                         x=kwargs["vector"].astype(np.float32), emb=np.zeros((5, 32)))
        graph = preprocess.construct_source_graph(segment, construct)
        self.assertEqual(set(seen[0]), {"anchor", "vector", "k", "delta"})
        self.assertEqual((seen[0]["k"], seen[0]["delta"]), (15, 1.5))
        bound = results.graph_embedding(graph, segment)
        self.assertEqual(bound["row_ids"], segment["row_ids"])
        for field, value in (("sample_ind", np.arange(5)[::-1]), ("sample_ind", np.arange(4)),
                             ("pos", graph.pos + 1), ("x", graph.x + 1), ("emb", np.zeros((4, 32)))):
            mutated = copy.copy(graph); setattr(mutated, field, value)
            with self.assertRaises(inputs.InputError): results.graph_embedding(mutated, segment)


@unittest.skipUnless(os.environ.get("MARBLE_FIXTURE_ROOT"),
                     "complete export requires an explicitly reserved MARBLE_FIXTURE_ROOT")
class FullGeneratedExportControl(unittest.TestCase):
    def test_complete_four_rat_view_export_retains_offsets_values_and_generated_scope(self):
        declared = Path(os.environ["MARBLE_FIXTURE_ROOT"])
        declared.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="generated-four-rat-", dir=declared))
        try:
            decoded = {}
            for rat in RATS:
                decoded[rat] = {}
                for name, (shape, stride, offset, count) in LAYOUTS[rat].items():
                    raw = ((np.arange(count, dtype=np.float32) % 1024 - 512) / 8).astype("<f4")
                    decoded[rat][name] = {"shape": shape, "stride": stride, "storage_offset": offset,
                        "storage_elements": count, "dtype": "<f4", "raw": raw.tobytes()}
            arrays = inputs.validate_release(decoded)
            with self.assertRaises(inputs.InputError): inputs.export_source(arrays, root / "unmarked")
            self.assertFalse((root / "unmarked").exists())
            # Exercise mutation binding with a generated SourceViews instance;
            # this is not a claim of authentic source admission.
            frozen = inputs.SourceViews(copy.deepcopy(arrays))
            changed = frozen["achilles"]["neural"].copy(); changed[0, 0] += 1
            frozen["achilles"]["neural"] = changed
            with self.assertRaises(inputs.InputError): inputs.export_source(frozen, root / "mutated")
            self.assertFalse((root / "mutated").exists())
            exported = inputs.export_source(arrays, root / "export", _generated=True)
            self.assertEqual(exported["rats"], 4)
            self.assertFalse(exported["scientific_preprocessing_or_model_run"])
            public_path, private_path = Path(exported["public_manifest"]), Path(exported["private_manifest"])
            public, public_pin = inputs.read_json(public_path)
            private, _ = inputs.read_json(private_path)
            self.assertEqual(public["source_authentication"], "generated_control_views")
            self.assertEqual(private["public_manifest_sha256"], public_pin)
            self.assertEqual(set(p.name for p in public_path.parent.iterdir()),
                             {"inputs.json", *(f"{rat}-neural.npy" for rat in RATS)})
            self.assertNotIn("position_m", json.dumps(public))
            for rat in RATS:
                for name, layout in LAYOUTS[rat].items():
                    shape, stride, offset, _ = layout
                    descriptor = public["rats"][rat]["neural"] if name == "neural" else private["rats"][rat]["continuous_index"]
                    directory = public_path.parent if name == "neural" else private_path.parent
                    path = directory / descriptor["path"]
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), descriptor["sha256"])
                    actual = np.load(path, mmap_mode="r", allow_pickle=False)
                    addressed = offset + np.arange(shape[0])[:, None] * stride[0] + np.arange(shape[1])[None, :] * stride[1]
                    expected = ((addressed % 1024 - 512) / 8).astype(np.float32)
                    np.testing.assert_array_equal(actual, expected)
                    self.assertEqual(actual.dtype, np.dtype("<f4"))
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o444 if name == "neural" else 0o600)
                    self.assertTrue(np.any(actual < 0))
                    self.assertTrue(np.any(actual != np.trunc(actual)))
            self.assertEqual(stat.S_IMODE(public_path.parent.stat().st_mode), 0o555)
        finally:
            created = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
            for directory, _, _ in os.walk(root): Path(directory).chmod(0o700)
            shutil.rmtree(root)
            accounting = os.environ.get("MARBLE_EXPORT_ACCOUNTING")
            if accounting:
                with Path(accounting).open("x") as stream:
                    json.dump({"scope": "complete original-shape generated views; no source pickle decoding",
                               "generated_logical_bytes_created_and_reclaimed": created,
                               "retained_generated_bytes": 0 if not root.exists() else None,
                               "authentic_payload_decodes": 0, "models_or_scientific_scores": 0}, stream, indent=2)
                    stream.write("\n")


if __name__ == "__main__":
    unittest.main()
