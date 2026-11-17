"""Generated binary controls, never authentic neural data or model results."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("neural065_prepare", ROOT / "prepare.py")
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture(root, sample_format="INT_16"):
    data_name = "002_DECOMEG_S1_9696_task1.eeg"
    header = ("BrainVision Data Exchange Header File Version 1.0\n"
        "; generated fixture, no authentic observations\n"
        "[Common Infos]\nCodepage=UTF-8\nDataFile=" + data_name + "\n"
        "MarkerFile=private-keypress-sentinel.vmrk\nDataFormat=BINARY\n"
        "DataOrientation=MULTIPLEXED\nNumberOfChannels=3\nSamplingInterval=2000\n"
        "[Binary Infos]\nBinaryFormat=" + sample_format + "\n"
        "[Channel Infos]\nCh1=Fp1,,0.1,µV\nCh2=EOG1,,1,mV\nCh3=Cz,,2,uV\n"
        "[Comment]\nPRIVATE-PATIENT-TEXT and intended sentence\n").encode()
    fmt = "h" if sample_format == "INT_16" else "f"
    data = struct.pack("<" + fmt * 12, 10, 1, -10, 20, 2, -20, 30, 3, -30, 40, 4, -40)
    plan = {"schema_version": 1, "task_id": p.TASK_ID, "source_commit": p.SOURCE_COMMIT,
        "data_commit": p.DATA_COMMIT, "recording_subject": "Pinet2024Eeg/002", "session_id": "session1",
        "selection_sha256": "1" * 64, "alignment_evidence_sha256": "2" * 64,
        "channel_names": ["Fp1", "Cz"], "windows": [
            {"query_id": "a" * 32, "start_sample": 1, "stop_sample": 3},
            {"query_id": "b" * 32, "start_sample": 3, "stop_sample": 4}]}
    header_path, data_path, plan_path = root / "recording.vhdr", root / data_name, root / "private-plan.json"
    header_path.write_bytes(header); data_path.write_bytes(data); plan_path.write_bytes(p.json_bytes(plan))
    return {"header_path": header_path, "data_path": data_path, "plan_path": plan_path, "output": root / "participant",
        "header_sha256": digest(header), "data_sha256": digest(data), "plan_sha256": digest(plan_path.read_bytes()),
        "max_source_bytes": 4096, "max_output_bytes": 4096}


def change_plan(args, edit):
    obj = json.loads(args["plan_path"].read_bytes()); edit(obj)
    args["plan_path"].write_bytes(p.json_bytes(obj))
    args["plan_sha256"] = digest(args["plan_path"].read_bytes())


def change_header(args, edit):
    raw = edit(args["header_path"].read_bytes())
    args["header_path"].write_bytes(raw); args["header_sha256"] = digest(raw)


class PreparationControls(unittest.TestCase):
    def test_literal_binary_oracle_units_frame_offset_channel_order_and_privacy(self):
        for fmt in ("INT_16", "IEEE_FLOAT_32"):
            with self.subTest(fmt=fmt), tempfile.TemporaryDirectory() as folder:
                args = fixture(Path(folder), fmt); result = p.prepare(**args)
                out = args["output"]; manifest = json.loads((out / "observations.json").read_bytes())
                first = manifest["observations"][0]; raw = (out / first["path"]).read_bytes()
                # Independent manually derived physical values, time-major order.
                for actual, expected in zip(struct.unpack("<4d", raw), [2e-6, -40e-6, 3e-6, -60e-6]):
                    self.assertAlmostEqual(actual, expected, places=18)
                self.assertEqual(first["shape"], [2, 2]); self.assertEqual(first["neural_asset_sha256"], digest(raw))
                self.assertEqual(manifest["sampling_frequency_hz"], 500)
                self.assertEqual(manifest["axes"], ["time", "channel"]); self.assertEqual(manifest["unit"], "V")
                self.assertEqual(manifest["channel_ids"], ["EEG000", "EEG001"])
                self.assertEqual(result["output_data_bytes"], 48)
                text = (out / "observations.json").read_text()
                for forbidden in ("Pinet", "session1", "Fp1", "Cz", "EOG", "private", "9696", "start_sample", "target"):
                    self.assertNotIn(forbidden, text)
                self.assertEqual(sorted(x.name for x in out.iterdir()), ["assets", "observations.json"])
                receipt = json.loads(out.with_name(out.name + ".private-receipt.json").read_bytes())
                self.assertEqual(receipt["source_samples"], 4); self.assertEqual(receipt["plan"]["windows"][0]["start_sample"], 1)
                self.assertFalse(receipt["native_alignment_reconstructed"])

    def test_partial_final_frames_wrong_pin_and_limits_refuse_before_publication(self):
        edits = [lambda a: a.update(data_sha256="0" * 64),
                 lambda a: a.update(header_sha256="0" * 64),
                 lambda a: a.update(plan_sha256="0" * 64),
                 lambda a: a.update(max_source_bytes=5),
                 lambda a: a.update(max_output_bytes=47)]
        for edit in edits:
            with self.subTest(edit=edit), tempfile.TemporaryDirectory() as folder:
                args = fixture(Path(folder)); edit(args)
                with self.assertRaises(p.PreparationError): p.prepare(**args)
                self.assertFalse(args["output"].exists())
        with tempfile.TemporaryDirectory() as folder:
            args = fixture(Path(folder)); raw = args["data_path"].read_bytes()[:-1]
            args["data_path"].write_bytes(raw); args["data_sha256"] = digest(raw)
            with self.assertRaisesRegex(p.PreparationError, "frame"): p.prepare(**args)

    def test_header_profile_refuses_unsupported_storage_or_units(self):
        mutations = [(b"MULTIPLEXED", b"VECTORIZED"), (b"INT_16", b"INT_32"),
            (b"DataFormat=BINARY", b"DataFormat=ASCII"), (b"2,uV", b"2,arbitrary"),
            (b"0.1,", b"0,"), (b"SamplingInterval=2000", b"SamplingInterval=nan"),
            (b"Ch3=Cz", b"Ch3=Fp1"), (b"[Binary Infos]", b"[Binary Infos]\nUseBigEndianOrder=YES"),
            (b"DataFile=002", b"DataFile=../002")]
        for old, new in mutations:
            with self.subTest(new=new), tempfile.TemporaryDirectory() as folder:
                args = fixture(Path(folder)); change_header(args, lambda raw: raw.replace(old, new))
                with self.assertRaises(p.PreparationError): p.prepare(**args)
                self.assertFalse(args["output"].exists())

    def test_window_identity_coverage_and_channel_exclusions(self):
        edits = [lambda d: d["windows"][0].update(stop_sample=5),
            lambda d: d["windows"][0].update(start_sample=-1),
            lambda d: d["windows"][0].update(start_sample=True),
            lambda d: d["windows"][0].update(query_id="answer-bearing"),
            lambda d: d["windows"][1].update(query_id="a" * 32),
            lambda d: d["windows"][1].update(start_sample=1, stop_sample=3),
            lambda d: d.update(channel_names=["Cz", "Fp1"]),
            lambda d: d.update(channel_names=["Fp1"]),
            lambda d: d.update(channel_names=["Fp1", "EOG1", "Cz"]),
            lambda d: d.update(recording_subject="Pinet2024Eeg/001"),
            lambda d: d.update(recording_subject="Pinet2024Eeg/003"),
            lambda d: d.update(session_id="session2"),
            lambda d: d.update(data_commit="V2"),
            lambda d: d["windows"][0].update(target_text="hidden")]
        for edit in edits:
            with self.subTest(edit=edit), tempfile.TemporaryDirectory() as folder:
                args = fixture(Path(folder)); change_plan(args, edit)
                with self.assertRaises(p.PreparationError): p.prepare(**args)
                self.assertFalse(args["output"].exists())

    def test_nonfinite_neural_samples_refuse_and_remove_staging(self):
        for index in (3, 4):  # Both selected EEG and excluded EOG must be finite.
            with self.subTest(index=index), tempfile.TemporaryDirectory() as folder:
                args = fixture(Path(folder), "IEEE_FLOAT_32")
                values = list(struct.unpack("<12f", args["data_path"].read_bytes())); values[index] = float("nan")
                raw = struct.pack("<12f", *values); args["data_path"].write_bytes(raw); args["data_sha256"] = digest(raw)
                with self.assertRaisesRegex(p.PreparationError, "nonfinite"): p.prepare(**args)
                self.assertFalse(args["output"].exists())
                self.assertFalse(list(Path(folder).glob(".neural065-*")))

    def test_existing_output_and_symlink_input_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            args = fixture(Path(folder)); p.prepare(**args)
            original = (args["output"] / "observations.json").read_bytes()
            with self.assertRaises(p.PreparationError): p.prepare(**args)
            self.assertEqual((args["output"] / "observations.json").read_bytes(), original)
        with tempfile.TemporaryDirectory() as folder:
            args = fixture(Path(folder)); raw = args["data_path"].read_bytes()
            args["data_path"].unlink(); target = Path(folder) / "other.eeg"; target.write_bytes(raw)
            args["data_path"].symlink_to(target)
            with self.assertRaises(OSError): p.prepare(**args)

    def test_duplicate_observation_content_not_hidden_by_distinct_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            args = fixture(Path(folder))
            raw = struct.pack("<12h", *([1, 2, 3] * 4)); args["data_path"].write_bytes(raw); args["data_sha256"] = digest(raw)
            change_plan(args, lambda d: d["windows"][0].update(stop_sample=2))
            with self.assertRaisesRegex(p.PreparationError, "duplicate observation"): p.prepare(**args)
            self.assertFalse(args["output"].exists())

    def test_source_mutation_after_first_hash_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            args = fixture(Path(folder)); original = p.hash_stream; count = 0
            def changing(stream, maximum):
                nonlocal count
                result = original(stream, maximum); count += 1
                if count == 1:
                    raw = bytearray(args["data_path"].read_bytes()); raw[0] ^= 1
                    args["data_path"].write_bytes(raw)
                return result
            with mock.patch.object(p, "hash_stream", side_effect=changing):
                with self.assertRaisesRegex(p.PreparationError, "changed"): p.prepare(**args)
            self.assertFalse(args["output"].exists())

    def test_cp1252_microvolt_header_and_chunk_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            args = fixture(Path(folder))
            change_header(args, lambda raw: raw.decode().replace("Codepage=UTF-8", "Codepage=ANSI").encode("cp1252"))
            # One selected window crosses the reader's 64 KiB frame boundary.
            raw = struct.pack("<3h", 3, 4, 5) * 11000
            args["data_path"].write_bytes(raw); args["data_sha256"] = digest(raw)
            args.update(max_source_bytes=70000, max_output_bytes=200000)
            change_plan(args, lambda d: d.update(windows=[{"query_id": "a" * 32, "start_sample": 1, "stop_sample": 11000}]))
            result = p.prepare(**args)
            self.assertEqual(result["output_data_bytes"], 10999 * 16)

    def test_legacy_spaced_header_signature(self):
        with tempfile.TemporaryDirectory() as folder:
            args = fixture(Path(folder))
            change_header(args, lambda raw: raw.replace(b"BrainVision Data", b"Brain Vision Data"))
            self.assertEqual(p.prepare(**args)["observations"], 2)

    def test_duplicate_and_invalid_json(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'\xff', b'[' * 1500 + b']' * 1500):
            with self.subTest(raw=raw[:20]), self.assertRaises(p.PreparationError): p.parse_plan(raw)

    def test_unmapped_source_tasks_are_refused(self):
        # The pinned loader maps task/task1 -> block1, task2 -> block2;
        # task1bis is not a supported log mapping, and tapping is excluded.
        for task in ("task1bis", "tapping", "task3"):
            with self.subTest(task=task), tempfile.TemporaryDirectory() as folder:
                args = fixture(Path(folder)); old = args["data_path"]
                new = old.with_name(old.name.replace("task1", task)); old.rename(new)
                args["data_path"] = new
                change_header(args, lambda raw: raw.replace(old.name.encode(), new.name.encode()))
                with self.assertRaisesRegex(p.PreparationError, "task mismatch"): p.prepare(**args)

    def test_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            args = fixture(Path(folder)); command = [sys.executable, "-I", "-B", str(ROOT / "prepare.py")]
            names = {"header_path": "header", "data_path": "data", "plan_path": "plan"}
            for key, value in args.items():
                command.extend(["--" + names.get(key, key).replace("_", "-"), str(value)])
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["observations"], 2)
            again = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(again.returncode, 2)


if __name__ == "__main__":
    unittest.main()
