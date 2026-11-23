"""Generated controls for declared output-position alignment; no EEG or models."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("aligned_endpoints", HERE / "endpoints.py")
ep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ep)
np = ep.np


class Alignment(unittest.TestCase):
    def test_all_twelve_routes_preserve_metrics(self):
        for dataset, (kind, classes) in ep.DATASETS.items():
            with self.subTest(dataset=dataset):
                if kind == "multiclass":
                    y = np.arange(40) % classes
                    out = np.eye(classes)[(y + (np.arange(40) % 7 == 0)) % classes]
                elif kind == "binary":
                    y = np.arange(40) % 2
                    out = np.where(y[:, None] == 1, .8, .2)
                else:
                    y = np.arange(40, dtype=float) / 40
                    out = (y + .05)[:, None]
                ids = ["generated-position-" + str(i) for i in range(40)]
                if dataset == "ISRUC":
                    y, out = y.reshape(2, 20), out.reshape(2, 20, 5)
                    ids = [ids[:20], ids[20:]]
                got = ep.score_aligned(dataset, y, out, target_row_ids=ids, output_row_ids=ids)
                self.assertEqual(got.pop("row_alignment"), "exact declared position order")
                self.assertEqual(got, ep.score(dataset, y, out))

    def test_wrong_order_rejected_before_scoring(self):
        # Equal shapes can produce a plausible but incorrect perfect score.
        # The target/export position declarations reveal the swapped rows.
        with patch.object(ep, "score") as scorer:
            with self.assertRaisesRegex(ValueError, "identities or order differ"):
                ep.score_aligned("TUAB", [0, 1], [[.2], [.8]],
                                 target_row_ids=["a", "b"], output_row_ids=["b", "a"])
            scorer.assert_not_called()

    def test_incomplete_duplicate_and_invalid_ids_rejected(self):
        for ids in (["a"], ["a", "b", "c"], ["a", "a"], ["a", "c"],
                    ["a", ""], ["a", " "], ["a", 2], [["a"], ["b"]]):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                ep.score_aligned("TUAB", [0, 1], [[.2], [.8]],
                                 target_row_ids=["a", "b"], output_row_ids=ids)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            ep.score_aligned("TUAB", [0, 1], [[.2], [.8]],
                             target_row_ids=["a", "a"], output_row_ids=["a", "a"])

    def test_isruc_requires_complete_block_and_position_identity(self):
        y = (np.arange(40) % 5).reshape(2, 20)
        out = np.eye(5)[y]
        ids = [["block-%d-position-%d" % (b, i) for i in range(20)] for b in range(2)]
        bad = [ids[0] + ids[1], [ids[1], ids[0]],
               [ids[0][::-1], ids[1]], [ids[0], ids[1][:-1]],
               [ids[0], ids[0]]]
        for output_ids in bad:
            with self.subTest(ids=output_ids), self.assertRaises(ValueError):
                ep.score_aligned("ISRUC", y, out, target_row_ids=ids, output_row_ids=output_ids)

    def test_numeric_validation_still_applies(self):
        for y, out in (([0, 1], [[-.2], [.8]]), ([0, 1], [[.2], [np.nan]]),
                       ([0, 1], [[.2, .8], [.8, .2]]), ([0, 2], [[.2], [.8]])):
            with self.subTest(y=y, out=out), self.assertRaises(ValueError):
                ep.score_aligned("TUAB", y, out,
                                 target_row_ids=["a", "b"], output_row_ids=["a", "b"])

    def test_cli_optional_ids_and_legacy_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            np.save(root / "targets.npy", np.array([0, 1]))
            np.save(root / "scores.npy", np.array([[.2], [.8]]))
            (root / "targets.json").write_text('["a", "b"]', encoding="utf-8")
            (root / "scores.json").write_text('["a", "b"]', encoding="utf-8")
            base = ["TUAB", str(root / "targets.npy"), str(root / "scores.npy")]
            flags = ["--target-row-ids", str(root / "targets.json"),
                     "--output-row-ids", str(root / "scores.json")]
            old, aligned = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(old):
                ep.main(base)
            with contextlib.redirect_stdout(aligned):
                ep.main(base + flags)
            actual = json.loads(aligned.getvalue())
            self.assertEqual(actual.pop("row_alignment"), "exact declared position order")
            self.assertEqual(actual, json.loads(old.getvalue()))
            (root / "scores.json").write_text('["b", "a"]', encoding="utf-8")
            refused = io.StringIO()
            with contextlib.redirect_stdout(refused), self.assertRaises(ValueError):
                ep.main(base + flags)
            self.assertEqual(refused.getvalue(), "")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as failure:
                ep.main(base + flags[:2])
            self.assertEqual(failure.exception.code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
