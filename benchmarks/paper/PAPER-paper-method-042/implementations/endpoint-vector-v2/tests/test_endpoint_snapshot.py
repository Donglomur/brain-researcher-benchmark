"""The vector report must reuse the authenticated complete image population."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("snapshot_endpoint_vector", HERE / "endpoint_vector.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
sys.path.insert(0, str(HERE.parent / "initial-evaluator-v1"))
from make_control import build


class EndpointSnapshotTests(unittest.TestCase):
    def test_replaced_order_cannot_change_sampling_population(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "control"
            contract = build(root)
            order = root / "image_order.json"
            original = v.g.evaluate

            def replace_after_scoring(*args, **kwargs):
                result = original(*args, **kwargs)
                order.write_bytes(b'{"0":"replacement-only"}')
                return result

            with patch.object(v.g, "evaluate", side_effect=replace_after_scoring):
                result = v.evaluate(contract, root / "annotations.json", order, draws=0)
            panel = result["endpoint_vector"]
            self.assertEqual(panel["shared_image_count"], 4)
            self.assertEqual(panel["empty_query_image_count"], 1)
            self.assertEqual(panel["query_count_per_subject"], 4)
            self.assertEqual(panel["scores_percent"]["candidate"], {s: 75 for s in v.SUBJECTS})


if __name__ == "__main__":
    unittest.main()
