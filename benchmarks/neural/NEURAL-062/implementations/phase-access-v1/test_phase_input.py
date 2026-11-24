"""Generated public FIT/INFER controls; no authentic data or model execution."""
from contextlib import redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("phase_input", HERE / "phase_input.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PUBLIC = Path(os.environ.get("NEURAL062_PUBLIC_CODE", str(MODULE.PUBLIC)))
PROTOCOL, _ = MODULE.dependencies(PUBLIC)


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def put(path, value):
    raw = (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()
    path.write_bytes(raw)
    return pin(raw)


def npy(rows, width, descriptor="<f4", fortran=False, header_override=None):
    header = header_override or repr({"descr": descriptor, "fortran_order": fortran,
                                     "shape": (len(rows), width)})
    text = header.encode("latin1")
    text += b" " * ((64 - (10 + len(text) + 1) % 64) % 64) + b"\n"
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(text)) + text + b"".join(
        struct.pack("<" + "f" * width, *row) for row in rows)


class PhaseAccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get("NEURAL062_TEST_TMP"))
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, phase="fit", arm="POST", count=None):
        root = self.root / (phase + str(len(list(self.root.iterdir()))))
        root.mkdir()
        width = len(PROTOCOL.names(arm))
        count = (16 if phase == "fit" else 3) if count is None else count
        rows = [[float(index + column / 10) for column in range(width)] for index in range(count)]
        if rows:
            rows[0][0] = float("nan")
        if phase == "fit":
            rows = [row + [index % 8, (index + 1) / 4] for index, row in enumerate(rows)]
        name = "train.npy" if phase == "fit" else "query.npy"
        raw = npy(rows, width + (2 if phase == "fit" else 0))
        (root / name).write_bytes(raw)
        view = {"format": "neural062_phase_view_v1", "phase": phase,
                "generation": "a" * 64, "case": "b" * 64, "arm": arm,
                "feature_names": list(PROTOCOL.names(arm)), "classes": list(range(8)),
                "array_name": name, "array": dict(pin(raw), shape=[count, width + (2 if phase == "fit" else 0)])}
        if phase == "fit":
            groups = {"schema": "neural062.train-mouse-groups.v1", "rows": count,
                      "runs": [{"group": "c" * 64, "count": 3},
                               {"group": "d" * 64, "count": 5},
                               {"group": "c" * 64, "count": count - 8}]}
            view["groups_pin"] = put(root / "TRAIN_GROUPS.json", groups)
        else:
            view["query_ids"] = [hashlib.sha256(str(x).encode()).hexdigest() for x in range(count)]
        put(root / "VIEW.json", view)
        return root, view, rows

    def update_array(self, root, view, raw):
        (root / view["array_name"]).write_bytes(raw)
        view["array"].update(pin(raw))
        put(root / "VIEW.json", view)

    def predictions(self, view):
        return {"format": "neural062_predictions_v1", **{k: view[k] for k in ("generation", "case", "arm")},
                "probabilities": [{"id": key, "p": [0.125] * 8} for key in view["query_ids"]]}

    def test_all_panels_complete_training_group_join(self):
        for arm, expected in [("CONTEXT", 32), ("PRE", 46), ("POST", 46), ("PRE_POST", 60)]:
            with self.subTest(arm=arm):
                root, view, original = self.fixture(arm=arm)
                with MODULE.open_phase(root, PUBLIC) as phase:
                    rows = list(phase.rows())
                    self.assertEqual(len(rows), 16)
                    self.assertEqual(len(rows[0]["features"]), expected)
                    self.assertTrue(math.isnan(rows[0]["features"][0]))
                    self.assertEqual([r["label"] for r in rows], list(range(8)) * 2)
                    self.assertEqual([r["weight"] for r in rows], [(i + 1) / 4 for i in range(16)])
                    self.assertEqual([r["group"] for r in rows], ["c" * 64] * 3 + ["d" * 64] * 5 + ["c" * 64] * 8)
                    with self.assertRaises(ValueError):
                        list(phase.rows())

    def test_infer_preserves_ids_features_and_empty_case(self):
        for count in [0, 3]:
            root, view, original = self.fixture("infer", count=count)
            with MODULE.open_phase(root, PUBLIC) as phase:
                rows = list(phase.rows())
                self.assertEqual([r["id"] for r in rows], view["query_ids"])
                self.assertTrue(all(set(r) == {"id", "features"} for r in rows))
                if rows:
                    self.assertAlmostEqual(rows[-1]["features"][-1], original[-1][-1], places=5)
            path = self.root / ("prediction" + str(count) + ".json")
            put(path, self.predictions(view))
            result = MODULE.prediction_preflight(root, path, PUBLIC)
            self.assertEqual(result["rows"], count)
            self.assertFalse(result["scientifically_qualified"])

    def test_invalid_late_values_fail_before_any_row_is_exposed(self):
        for change in ["infinite_feature", "nan_label", "fractional_label", "zero_weight", "missing_class"]:
            with self.subTest(change=change):
                root, view, rows = self.fixture()
                if change == "infinite_feature": rows[-1][0] = float("inf")
                elif change == "nan_label": rows[-1][-2] = float("nan")
                elif change == "fractional_label": rows[-1][-2] = 2.5
                elif change == "zero_weight": rows[-1][-1] = 0
                else:
                    for row in rows:
                        if row[-2] == 7: row[-2] = 6
                self.update_array(root, view, npy(rows, len(rows[0])))
                entered = False
                with self.assertRaises(ValueError):
                    with MODULE.open_phase(root, PUBLIC):
                        entered = True
                self.assertFalse(entered)

    def test_group_pin_geometry_and_group_types_fail(self):
        for change in ["pin", "short", "zero", "boolean", "id", "rows", "extra"]:
            with self.subTest(change=change):
                root, view, rows = self.fixture()
                groups = json.loads((root / "TRAIN_GROUPS.json").read_text())
                if change in ("pin", "short"): groups["runs"][-1]["count"] -= 1
                elif change == "zero": groups["runs"][0]["count"] = 0
                elif change == "boolean": groups["runs"][0]["count"] = True
                elif change == "id": groups["runs"][0]["group"] = "real-mouse"
                elif change == "rows": groups["rows"] = 15
                else: groups["runs"][0]["mouse_id"] = "forbidden"
                new_pin = put(root / "TRAIN_GROUPS.json", groups)
                if change != "pin": view["groups_pin"] = new_pin
                put(root / "VIEW.json", view)
                with self.assertRaises(ValueError):
                    with MODULE.open_phase(root, PUBLIC): pass

    def test_wrong_phase_target_fields_and_extra_files_fail(self):
        for change in ["extra_file", "query_labels", "duplicate_id", "training_array", "feature_names", "bool_class"]:
            with self.subTest(change=change):
                root, view, rows = self.fixture("infer")
                if change == "extra_file": (root / "train.npy").write_bytes(b"forbidden")
                elif change == "query_labels": view["labels"] = [0, 1, 2]
                elif change == "duplicate_id": view["query_ids"][1] = view["query_ids"][0]
                elif change == "training_array": view["array_name"] = "train.npy"
                elif change == "feature_names": view["feature_names"][-1] = "wrong"
                else: view["classes"][0] = False
                put(root / "VIEW.json", view)
                with self.assertRaises(ValueError):
                    with MODULE.open_phase(root, PUBLIC): pass

    def test_numpy_and_pins_reject_ambiguous_or_changed_arrays(self):
        for change in ["pin", "extent", "float64", "fortran", "duplicate_header", "geometry"]:
            with self.subTest(change=change):
                root, view, rows = self.fixture("infer")
                width = len(rows[0])
                if change == "float64": raw = npy(rows, width, descriptor="<f8")
                elif change == "fortran": raw = npy(rows, width, fortran=True)
                elif change == "duplicate_header":
                    raw = npy(rows, width, header_override="{'descr':'<f4','descr':'<f4','fortran_order':False,'shape':(3,46)}")
                elif change == "geometry": raw = npy(rows, width, header_override="{'descr':'<f4','fortran_order':False,'shape':(3,60)}")
                else: raw = npy(rows, width) + b"x"
                if change == "pin": (root / "query.npy").write_bytes(raw)
                else: self.update_array(root, view, raw)
                with self.assertRaises(ValueError):
                    with MODULE.open_phase(root, PUBLIC): pass

    def test_prediction_preflight_rejects_missing_wrong_or_invalid_rows(self):
        root, view, rows = self.fixture("infer")
        for change in ["missing", "duplicate", "other_id", "generation", "arm", "negative", "sum", "bool", "nan", "extra"]:
            with self.subTest(change=change):
                value = self.predictions(view)
                if change == "missing": value["probabilities"].pop()
                elif change == "duplicate": value["probabilities"][1] = copy.deepcopy(value["probabilities"][0])
                elif change == "other_id": value["probabilities"][0]["id"] = "f" * 64
                elif change == "generation": value["generation"] = "c" * 64
                elif change == "arm": value["arm"] = "PRE"
                elif change == "negative": value["probabilities"][0]["p"] = [-1] + [2 / 7] * 7
                elif change == "sum": value["probabilities"][0]["p"] = [0.1] * 8
                elif change == "bool": value["probabilities"][0]["p"] = [True] + [0] * 7
                elif change == "extra": value["probabilities"][0]["target"] = 0
                else: value["probabilities"][0]["p"] = [float("nan")] + [0] * 7
                path = self.root / "prediction.json"
                if change == "nan": path.write_text(json.dumps(value))
                else: put(path, value)
                with self.assertRaises(ValueError): MODULE.prediction_preflight(root, path, PUBLIC)

    def test_cli_reports_public_structure_and_limits(self):
        root, view, rows = self.fixture("infer")
        output = io.StringIO()
        with patch("sys.argv", ["phase_input.py", "--input", str(root), "--public-code", str(PUBLIC)]), redirect_stdout(output):
            MODULE.main()
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "public_phase_structure_valid")
        self.assertEqual(result["rows"], 3)
        self.assertEqual(result["private_target_reads"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
