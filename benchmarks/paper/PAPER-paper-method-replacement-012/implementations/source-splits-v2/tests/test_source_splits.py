import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from inert_pickle import FormatError, Record, Symbol
import source_splits as ss


def arr(values, shape=None):
    dtype = Record(Symbol("numpy.dtype"), ("O8", False, True), (3, "|", None, None, None, -1, -1, 63))
    return Record(Symbol("numpy.core.multiarray._reconstruct"), (Symbol("numpy.ndarray"), (0,), b"b"),
                  (1, shape or (len(values),), dtype, False, list(values)))


def ix(values):
    return Record(Symbol("pandas.core.indexes.base._new_Index"), (Symbol("pandas.core.indexes.base.Index"), {"data": arr(values), "name": None}))


def source_fixture():
    # Four known source animals, two generated observations per label per animal.
    sessions = ["sb025_20191007", "sb026_20191014", "sb028_20191107", "sb030_20200110"]
    ids = [f"{s}_u{i}" for s in sessions for i in range(4)]
    labels = ["EC", "IN", "EC", "IN"]*4
    block = Record(Symbol("pandas._libs.internals._unpickle_block"), (arr(labels, (1, len(ids))), Record(Symbol("builtins.slice"), (0, 1, 1)), 2))
    mgr = Record(Symbol("pandas.core.internals.managers.BlockManager"), ((block,), [ix(["label"]), ix(ids)]))
    frame = Record(Symbol("pandas.core.frame.DataFrame"), (), {"_mgr": mgr, "_typ": "dataframe", "_metadata": [], "attrs": {}, "_flags": {"allows_duplicate_labels": True}})
    test = [x for x in ids if x.startswith("sb028")]
    train = [x for x in ids if x not in test]
    cv = []
    for subject in ("sb025", "sb026", "sb030"):
        val = [x for x in train if x.startswith(subject)]
        cv.append({"train": arr([x for x in train if x not in val]), "val": arr(val)})
    return {"label_map": frame, "splits": [{"train": arr(train), "test": arr(test), "train_cv": cv}]}, ids


class SourceProjectionTests(unittest.TestCase):
    def project_fixture(self, source):
        with patch.object(ss, "parse", return_value=source):
            return ss.project(b"generated structure control", "ei", "inductive_zero_shot")

    def test_original_axis_and_membership_order(self):
        source, ids = source_fixture()
        projection = self.project_fixture(source)
        self.assertEqual(list(projection["label_map"]), ids)
        self.assertEqual(projection["splits"][0]["test"], ids[8:12])
        self.assertTrue(ss.topology_audit(projection)["matches_registered_topology"])
        selected = ss.select_readout_panel([projection], "ei", "inductive_zero_shot")
        self.assertEqual(selected["required_readout_class_balance"], "resample")
        self.assertNotIn("source_archive_sha256", projection)

    def test_leaking_source_remains_inspectable_but_not_selectable(self):
        source, ids = source_fixture()
        source["splits"][0]["train_cv"][0]["train"].state[-1].extend(ids[8:12])
        value = source["splits"][0]["train_cv"][0]["train"]
        value.state = (1, (len(value.state[-1]),), value.state[2], False, value.state[-1])
        projection = self.project_fixture(source)
        audit = ss.topology_audit(projection)
        self.assertFalse(audit["matches_registered_topology"])
        self.assertEqual(audit["folds"][0]["cv"][0]["train_test_overlap"], 4)
        self.assertEqual(len(projection["splits"][0]["train_cv"][0]["train"]), 12)
        with self.assertRaisesRegex(ValueError, "CV crosses"):
            ss.select_readout_panel([projection], "ei", "inductive_zero_shot")

    def test_unknown_constructor_is_never_interpreted(self):
        source, _ = source_fixture()
        source["label_map"].constructor.name = "builtins.eval"
        with self.assertRaises(FormatError): self.project_fixture(source)

    def test_source_axis_shape_and_dtype_must_match(self):
        source, _ = source_fixture()
        block = source["label_map"].state["_mgr"].args[0][0]
        block.args[0].state = (1, (2, 8), block.args[0].state[2], False, block.args[0].state[-1])
        with self.assertRaisesRegex(FormatError, "axis/value"):
            self.project_fixture(source)
        with self.assertRaisesRegex(FormatError, "dtype"):
            ss.array(Record(Symbol("numpy.core.multiarray._reconstruct"), (Symbol("numpy.ndarray"), (0,), b"b"), (1, (1,), Record(Symbol("numpy.dtype"), ("i8", False, True)), False, ["x"])))

    def test_archive_must_match_before_zip_open(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            path = Path(tmp)/"source.zip"
            path.write_bytes(b"not the author archive")
            with patch.object(ss.zipfile, "ZipFile", side_effect=AssertionError("must not open zip")):
                with self.assertRaisesRegex(FormatError, "archive pin"):
                    ss.read_archive(path)


if __name__ == "__main__":
    unittest.main()
