"""Generated catalogue-snapshot controls; no optical or EP data are opened."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("native_roi_population_snapshot", ROOT / "extract.py")
extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract)


def fixture():
    catalogue = {"recordings": [{"recording_id": f"generated-{i:02d}",
        "cell_id": f"generated-cell-{i % 9}",
        "raw_tiff": {"object": f"generated-{i}.tif", "bytes": 100}}
        for i in range(22)]}
    body = json.dumps(catalogue).encode()
    methods = ["raw", "cellmincer", "n2s"]
    panel = {"schema_version": 1, "task_id": extract.TASK_ID,
        "population_sha256": hashlib.sha256(body).hexdigest(), "methods": methods,
        "recordings": [{"recording_id": row["recording_id"], "cell_id": row["cell_id"],
            "shape_yx": [2, 3], "roi": {},
            "movies": {method: {"path": method + ".tif", "sha256": "a" * 64,
                **({"source_object": copy.deepcopy(row["raw_tiff"])} if method == "raw" else {})}
                for method in methods}} for row in catalogue["recordings"]]}
    return body, catalogue, panel


class PopulationSnapshot(unittest.TestCase):
    def exercise(self, panel, body, replacement=None):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "population.json"
            path.write_bytes(body)
            original_read = Path.read_bytes
            def read_then_replace(current):
                captured = original_read(current)
                if current == path and replacement is not None:
                    path.write_bytes(replacement)
                return captured
            with mock.patch.object(extract, "POPULATION", path), mock.patch.object(Path, "read_bytes", read_then_replace):
                return extract.validate_panel(panel)

    def test_stable_complete_generated_catalogue(self):
        body, catalogue, panel = fixture()
        rows, observed = self.exercise(panel, body)
        self.assertEqual(rows, panel["recordings"])
        self.assertEqual(observed, {r["recording_id"]: r for r in catalogue["recordings"]})

    def test_replacement_cannot_change_authenticated_catalogue(self):
        body, catalogue, panel = fixture()
        replacement = copy.deepcopy(catalogue)
        replacement["recordings"][0]["cell_id"] = "replacement-cell"
        rows, observed = self.exercise(panel, body, json.dumps(replacement).encode())
        self.assertEqual(rows, panel["recordings"])
        self.assertEqual(observed, {r["recording_id"]: r for r in catalogue["recordings"]})

    def test_replacement_identity_cannot_borrow_original_hash(self):
        body, catalogue, panel = fixture()
        replacement = copy.deepcopy(catalogue)
        replacement["recordings"][0]["cell_id"] = "replacement-cell"
        panel["recordings"][0]["cell_id"] = "replacement-cell"
        with self.assertRaisesRegex(extract.InputError, "cell identity"):
            self.exercise(panel, body, json.dumps(replacement).encode())


if __name__ == "__main__":
    unittest.main(verbosity=2)
