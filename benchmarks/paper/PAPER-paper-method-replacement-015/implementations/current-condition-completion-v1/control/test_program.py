"""Generated CLI/interface controls; no original data or native container use."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
DELIVERY = HERE.parents[1] / "current-condition-delivery-v1"
sys.path.insert(0, str(DELIVERY))
import contract
import collect
import materials

spec = importlib.util.spec_from_file_location("fixed_control", HERE / "program.py")
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
FIXTURE_BYTES = 0
OUTPUT_BYTES = 0


def write(path, body):
    global FIXTURE_BYTES
    path.write_bytes(body)
    FIXTURE_BYTES += len(body)


class ProgramTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current = materials.load_current()

    def fixture(self, arm="paper_data", purpose="reproduction"):
        temporary = tempfile.TemporaryDirectory(prefix="spinal-fixed-control-",
                                                  dir=Path(tempfile.gettempdir()).resolve())
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        inputs = root / "input"; inputs.mkdir()
        output = root / "output"; output.mkdir()
        pair, unused = contract.freeze_pair(HERE, HERE, purpose, "hz")
        fold = {"schema": "spinal_current_fold_materials_v1", "condition_id": contract.CONDITION,
                "held_neuron": "generated-neuron", "cohort": "glutamatergic", "arm": arm,
                "purpose": purpose, "nominal_rate_hz": 30., "target_sigma_seconds": .05,
                "context_margin_bins": 32, "training_records": [],
                "query_records": [{"recording_id": "generated-neuron/recording-000",
                    "neuron_id": "generated-neuron", "offset": 0, "samples": 65},
                    {"recording_id": "generated-neuron/recording-001",
                     "neuron_id": "generated-neuron", "offset": 65, "samples": 81}]}
        files = {"FOLD.json": contract.encoded(fold)}
        binding = contract.fold_binding(pair, arm, fold, files)
        config = pair["arms"][arm]["seal"]["configuration"]
        write(inputs / "FOLD.json", files["FOLD.json"])
        write(root / "binding.json", contract.encoded(binding))
        write(root / "config.json", contract.encoded(config))
        return root, fold, binding, config

    def invoke(self, root):
        global OUTPUT_BYTES
        result = subprocess.run([sys.executable, "-I", "-S", "-B", str(HERE / "program.py"),
            "--input", str(root / "input"), "--config", str(root / "config.json"),
            "--binding", str(root / "binding.json"), "--output", str(root / "output")],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=10, umask=0o077, check=False)
        OUTPUT_BYTES += sum(p.stat().st_size for p in (root / "output").iterdir() if p.is_file())
        self.assertLessEqual(len(result.stdout) + len(result.stderr), 8192)
        return result

    def rewrite(self, root, fold, binding):
        body = contract.encoded(fold)
        binding["fold_manifest"] = contract.pin(body)
        binding["input_files"]["FOLD.json"] = contract.pin(body)
        binding["query_records"] = deepcopy(fold["query_records"])
        write(root / "input/FOLD.json", body)
        write(root / "binding.json", contract.encoded(binding))

    def test_original_collector_accepts_full_one_hz_both_arms_and_purposes(self):
        for arm in contract.ARMS:
            for purpose in ("reproduction", "improvement"):
                with self.subTest(arm=arm, purpose=purpose):
                    root, fold, binding, unused = self.fixture(arm, purpose)
                    # Deliberately absent: training.npz, query.npz, electrical
                    # targets, author code and paper. Metadata-only control.
                    result = self.invoke(root)
                    self.assertEqual(result.returncode, 0, result.stderr.decode())
                    outputs = root / "output"
                    self.assertEqual({p.name for p in outputs.iterdir()}, {"fold.json", "predictions.npy"})
                    rows = []
                    for path in sorted(outputs.iterdir()):
                        body = path.read_bytes()
                        rows.append({"path": path.name, **contract.pin(body)})
                        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)
                    # This is a generated lifecycle fixture ONLY; it exercises
                    # the genuine collector, not actual container isolation.
                    receipt = {"status": "captured", "all_resources_closed": True,
                        "cli_reaped": True, "candidate_closed_before_capture": True,
                        "natural_exit": {"Status": "exited", "Running": False, "Dead": False,
                            "Pid": 0, "ExitCode": 0, "OOMKilled": False},
                        "closures": [{"kind": kind, "closed": True} for kind in
                                     ("container", "container", "volume")], "outputs": rows}
                    values = collect.collect_fold(binding, receipt, outputs, self.current)
                    self.assertEqual(list(values), [row["recording_id"] for row in fold["query_records"]])
                    for row in fold["query_records"]:
                        vector = values[row["recording_id"]]
                        self.assertEqual(vector.shape, (row["samples"],))
                        self.assertTrue((vector == 1.0).all())

    def test_wrong_units_fail_before_outputs(self):
        root, unused, binding, config = self.fixture()
        binding["output_unit"] = config["output_unit"] = "expected_spikes_per_bin"
        write(root / "binding.json", contract.encoded(binding))
        write(root / "config.json", contract.encoded(config))
        result = self.invoke(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"exactly 1 Hz", result.stderr)
        self.assertEqual(list((root / "output").iterdir()), [])

    def test_bad_record_geometries_fail_before_outputs(self):
        for defect in ("offset", "short", "other-neuron", "duplicate", "oversized", "boolean"):
            with self.subTest(defect=defect):
                root, fold, binding, unused = self.fixture()
                row = fold["query_records"][1]
                if defect == "offset": row["offset"] += 1
                elif defect == "short": row["samples"] = 64
                elif defect == "other-neuron": row["neuron_id"] = "different-neuron"
                elif defect == "duplicate": row["recording_id"] = fold["query_records"][0]["recording_id"]
                elif defect == "oversized": row["samples"] = 125000
                else: row["offset"] = True
                self.rewrite(root, fold, binding)
                result = self.invoke(root)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(list((root / "output").iterdir()), [])

    def test_changed_fold_is_not_silently_used(self):
        root, fold, unused, unused_config = self.fixture()
        fold["query_records"][0]["samples"] += 1
        write(root / "input/FOLD.json", contract.encoded(fold))
        result = self.invoke(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"fold bytes match", result.stderr)
        self.assertEqual(list((root / "output").iterdir()), [])

    def test_duplicate_and_oversized_metadata_are_rejected(self):
        for body in (b'{"arm":"paper_data","arm":"paper_data_author_code"}', b" " * 100001):
            root, unused_fold, unused_binding, unused_config = self.fixture()
            write(root / "config.json", body)
            result = self.invoke(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(list((root / "output").iterdir()), [])

    def test_existing_output_is_preserved_and_refused(self):
        root, unused_fold, unused_binding, unused_config = self.fixture()
        write(root / "output/prior.txt", b"preserve-generated-prior")
        result = self.invoke(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((root / "output/prior.txt").read_bytes(), b"preserve-generated-prior")
        self.assertEqual({p.name for p in (root / "output").iterdir()}, {"prior.txt"})

    @classmethod
    def tearDownClass(cls):
        print(json.dumps({"scope": "generated_fixed_control_tests_only",
                          "fixture_write_bytes": FIXTURE_BYTES,
                          "observed_output_bytes": OUTPUT_BYTES,
                          "deleted_fixture_bytes_remain_charged": True}, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
