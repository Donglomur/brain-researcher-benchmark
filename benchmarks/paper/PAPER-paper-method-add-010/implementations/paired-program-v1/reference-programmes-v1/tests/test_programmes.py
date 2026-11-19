"""Portable generated CLI checks; no original bank or private reference input."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE.parent))
import generic_contract as contract

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
              "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS"):
    os.environ[_name] = "1"
import numpy as np


class PortableProgrammes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="meg-programme-public-")
        cls.root = Path(cls.temp.name)
        cls.calls = 0
        cls.written = 0
        cls.people = contract.published_participants()
        cls.folds = {}
        start = 0
        for fold, count in enumerate([10] * 4 + [9] * 6):
            for participant in cls.people[start:start + count]:
                cls.folds[participant] = fold
            start += count
        cls.records = [
            {"row_key": hashlib.sha256(("portable-" + p + "-" + label).encode()).hexdigest(),
             "participant": p, "label": label,
             "value": (1 if label == "face" else 4) + index / 100}
            for index, p in enumerate(cls.people) for label in contract.PAIR
        ]
        cls.base = cls.make_input(cls.records, "base")
        cls.baseline = {arm: cls.run_programme(arm, cls.base[0])
                        for arm in ("original", "training-range")}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def write(cls, path, body):
        cls.written += len(body)
        if cls.written > 524288:
            raise AssertionError("generated fixture/response cumulative write budget")
        with path.open("xb") as stream:
            stream.write(body)

    @classmethod
    def make_input(cls, records, name):
        directory = cls.root / name
        directory.mkdir()
        inventory = np.asarray([r["value"] for r in records], dtype="<f8").tobytes()
        panel = contract.build_panel(records, cls.folds, b"p" * 32,
            {"bytes": len(inventory), "sha256": hashlib.sha256(inventory).hexdigest()})
        context = contract.public_context(panel, 0)
        by_key = {r["row_key"]: r["value"] for r in records}
        private = {r["id"]: r for r in panel["private_records"]}
        values = np.asarray([by_key[private[r["id"]]["row_key"]]
                             for r in context["rows"]], dtype="<f8")
        array = io.BytesIO()
        np.save(array, values, allow_pickle=False)
        cls.write(directory / "CONTEXT.json", contract.canonical(context) + b"\n")
        cls.write(directory / "FEATURES.npy", array.getvalue())
        return directory, context, {r["id"]: r["source_id"] for r in panel["private_records"]}

    @classmethod
    def run_programme(cls, arm, directory, successful=True):
        cls.calls += 1
        if cls.calls > 6:
            raise AssertionError("six sequential portable CLI calls maximum")
        output = cls.root / ("response-" + str(cls.calls) + ".json")
        source = PACKAGE / "programmes" / arm / "submission.py"
        completed = subprocess.run(
            [sys.executable, "-I", "-B", str(source), "--input", str(directory),
             "--output", str(output)],
            cwd=cls.root, capture_output=True, timeout=12, check=False)
        if len(completed.stdout) + len(completed.stderr) > 32768:
            raise AssertionError("bounded trusted-programme diagnostic capture")
        if not successful:
            if completed.returncode == 0 or output.exists():
                raise AssertionError("malformed public input accepted")
            return None
        if completed.returncode != 0:
            raise AssertionError("portable CLI failed: " + completed.stderr.decode(errors="replace")[-2048:])
        if not output.is_file() or output.stat().st_size > 65536:
            raise AssertionError("bounded ordinary response missing")
        body = output.read_bytes()
        cls.written += len(body)
        if cls.written > 524288:
            raise AssertionError("generated output budget")
        return json.loads(body)

    def test_complete_public_contract_and_both_standalone_clis(self):
        context = self.base[1]
        self.assertEqual((len(context["rows"]), len(context["queries"])), (188, 20))
        for response in self.baseline.values():
            for outcome in ("reproduction", "improvement"):
                admitted = contract.validate_prediction(response, context, outcome)
                self.assertEqual(set(admitted["probabilities"]), set(context["queries"]))
        self.assertTrue(any(abs(self.baseline["original"]["probabilities"][key] -
                                self.baseline["training-range"]["probabilities"][key]) > 1e-10
                            for key in context["queries"]))

    def test_held_batch_distinction_survives_portable_paths(self):
        records = copy.deepcopy(self.records)
        records[19]["value"] = 12.0
        directory, context, sources = self.make_input(records, "changed-held")
        changed_source = contract.source_id(self.people[9], "object")
        witness = contract.source_id(self.people[8], "object")
        for arm in ("original", "training-range"):
            response = self.run_programme(arm, directory)
            contract.validate_prediction(response, context, "reproduction")
            before = {self.base[2][key]: value for key, value in self.baseline[arm]["probabilities"].items()}
            after = {sources[key]: value for key, value in response["probabilities"].items()}
            delta = {key: abs(before[key] - after[key]) for key in before if key != changed_source}
            if arm == "original":
                self.assertGreater(delta[witness], 1e-10)
            else:
                self.assertLessEqual(max(delta.values()), 1e-12)

    def test_private_reference_field_refused_through_actual_cli(self):
        directory, context, _ = self.make_input(self.records, "invalid-public")
        context["private_reference_path"] = "FORBIDDEN_GENERATED_SENTINEL"
        context["context_sha256"] = contract.digest({k: v for k, v in context.items()
                                                   if k != "context_sha256"})
        path = directory / "CONTEXT.json"
        path.unlink()
        self.write(path, contract.canonical(context) + b"\n")
        for arm in ("original", "training-range"):
            self.run_programme(arm, directory, successful=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
