"""Inert generated configuration controls; never deserialize executable layers."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


MODULE = Path(__file__).resolve().parents[1] / "checkpoint.py"
SPEC = importlib.util.spec_from_file_location("checkpoint_under_test", MODULE)
CHECKPOINT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKPOINT)


def invented_config():
    layers = [{"class_name": "InputLayer", "name": "input",
               "config": {"batch_input_shape": [None, 400, 64, 64, 1]}}]
    previous = "input"
    for index, units in enumerate([128, 64, 32, 16, 8]):
        name = f"dense_{index}"
        layers.append({"class_name": "Dense", "name": name, "config": {"units": units},
                       "inbound_nodes": [[[previous, 0, 0, {}]]]})
        previous = name
    # Deliberately invalid function data demonstrates that no bytecode decoding,
    # import or model deserialization is attempted by this metadata inspector.
    layers.append({"class_name": "Lambda", "name": "ignored_lambda_payload",
                   "config": {"function": ["this is not base64 bytecode", {"do_not_run": True}]}})
    for index, (kernel, filters) in enumerate([(3, 32), (3, 16), (1, 8)]):
        name = f"conv_{index}"
        layers.append({"class_name": "Conv1D", "name": name,
                       "config": {"kernel_size": [kernel], "strides": [1],
                                  "dilation_rate": [1], "padding": "valid",
                                  "data_format": "channels_last", "filters": filters},
                       "inbound_nodes": [[[previous, 0, 0, {}]]]})
        previous = name
    return {"class_name": "Functional",
            "config": {"layers": layers, "output_layers": [["conv_2", 0, 0]]}}


class ConfigurationTests(unittest.TestCase):
    def test_inert_dimensions_and_valid_convolution_arithmetic(self):
        result = CHECKPOINT.summarize_config(invented_config())
        self.assertEqual(result["batch_input_shape"], [None, 400, 64, 64, 1])
        self.assertEqual(result["terminal_dense_units"], 8)
        self.assertEqual([r["derived_length"] for r in result["temporal_convolutions"]], [398, 396, 396])
        self.assertEqual(result["derived_temporal_output_length"], 396)
        self.assertEqual(result["serialized_lambda_layer_count"], 1)
        self.assertFalse(result["lambda_payloads_executed_or_decoded"])
        self.assertFalse(result["native_output_shapes_verified"])

    def test_length_uses_actual_config_kernel_stride_and_dilation(self):
        config = invented_config()
        config["config"]["layers"][-3]["config"].update(kernel_size=[5], strides=[2], dilation_rate=[2])
        # floor((400 - (2*(5-1)+1))/2)+1=196, then 196-3+1=194.
        self.assertEqual(CHECKPOINT.summarize_config(config)["derived_temporal_output_length"], 194)

    def test_parallel_convolutions_cannot_be_reported_as_a_serial_chain(self):
        config = invented_config()
        config["config"]["layers"][-1]["inbound_nodes"] = [[["input", 0, 0, {}]]]
        with self.assertRaisesRegex(ValueError, "serial chain"):
            CHECKPOINT.summarize_config(config)

    def test_unresolved_output_and_padding_are_refused(self):
        for modify in (lambda c: c["config"].update(output_layers=[["dense_4", 0, 0]]),
                       lambda c: c["config"]["layers"][-1]["config"].update(padding="same")):
            config = invented_config()
            modify(config)
            with self.assertRaises(ValueError):
                CHECKPOINT.summarize_config(config)

    def test_duplicate_layer_names_and_nonpositive_dimensions_are_refused(self):
        for modify in (lambda c: c["config"]["layers"][-1].update(name="input"),
                       lambda c: c["config"]["layers"][-1]["config"].update(kernel_size=[0]),
                       lambda c: c["config"]["layers"][0]["config"].update(batch_input_shape=[None, True, 64, 64, 1])):
            config = invented_config()
            modify(config)
            with self.assertRaises(ValueError):
                CHECKPOINT.summarize_config(config)

    def test_json_rejects_duplicate_fields_and_nonfinite_constants(self):
        for text in ('{"config": {}, "config": {}}', '{"config": NaN}'):
            with self.assertRaises(ValueError):
                CHECKPOINT.parse_config(text)

    def test_wrong_bytes_are_refused_before_hdf_parser_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "not_a_checkpoint.h5"
            path.write_bytes(b"invented bytes")
            parser = SimpleNamespace(File=lambda *a, **k: self.fail("HDF parser called before authentication"))
            with patch.object(CHECKPOINT, "EXPECTED_BYTES", path.stat().st_size), patch.dict(sys.modules, {"h5py": parser}):
                with self.assertRaisesRegex(ValueError, "identity mismatch"):
                    CHECKPOINT.inspect_checkpoint(path)

    def test_authenticated_generated_hdf_reads_only_model_config(self):
        import h5py

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invented_checkpoint.h5"
            with h5py.File(path, "w") as file:
                file.attrs["model_config"] = json.dumps(invented_config())
                file.attrs["training_config"] = "not JSON and must not be parsed"
                file["unread_weights"] = h5py.ExternalLink("unavailable.h5", "/no_such_weights")
            body = path.read_bytes()
            with patch.multiple(CHECKPOINT, EXPECTED_BYTES=len(body),
                                EXPECTED_SHA256=hashlib.sha256(body).hexdigest(),
                                EXPECTED_GIT_BLOB_SHA1=hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()):
                result = CHECKPOINT.inspect_checkpoint(path)
            self.assertEqual(result["configuration"]["terminal_dense_units"], 8)
            self.assertFalse(result["paper_equivalence_established"])


if __name__ == "__main__":
    unittest.main()
