"""Generated timing controls; no authentic NWB, arrays, fitting or predictions."""
from contextlib import contextmanager
from pathlib import Path
import importlib.util
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from timeline import next_onsets, overlaps_post
spec = importlib.util.spec_from_file_location("n062_projection_v2", HERE / "project.py")
projection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(projection)


def table(group, ids, starts, **extra):
    n = len(ids)
    return {"group": group, "ids": ids, "starts": starts,
            "image_names": ["test_image"] * n, "omitted": [False] * n,
            "blocks": ["change_detection"] * n, "changes": [1] * n,
            "ends": [t + .25 for t in starts], "active": [True] * n, **extra}


class Array(list):
    def __getitem__(self, index):
        result = super().__getitem__(index)
        return Array(result) if isinstance(index, slice) else result

    def tolist(self):
        return list(self)

    def asstr(self):
        return self


class Subject:
    def __getitem__(self, index):
        return b"generated_mouse"


RECORD = {"asset": {"file_hash": "0" * 128}, "published_rois": [[1, 10]],
          "mouse_id": "generated_mouse", "ophys_experiment_id": "generated_experiment",
          "cre_line": "Slc17a7-IRES2-Cre", "targeted_structure": "VISp",
          "experience_level": "Familiar", "project_code": "VisualBehavior",
          "passive": "False", "indicator": "GCaMP6f", "targeted_imaging_depth": 200}


@contextmanager
def generated_source(tables):
    """Replace source I/O and numerical summaries, retaining actual project logic.

    This tests admission/census on the executable projection path. It deliberately
    makes no claim about HDF5 reading, native feature numerics or source hashing.
    """
    by_group = {t["group"]: t for t in tables}

    @contextmanager
    def opened(path, binding):
        yield object()

    def internal(f, path):
        if path == "general/subject/subject_id":
            return Subject()
        _, group, name = path.split("/")
        if name != "stimulus_block_name":
            raise AssertionError(path)
        return Array(by_group[group]["blocks"])

    def vector(f, path, n, kind, cap):
        _, group, name = path.split("/")
        values = by_group[group][{"is_change": "changes", "stop_time": "ends",
                                 "active": "active"}[name]]
        assert len(values) == n
        return values

    with patch.multiple(projection.src, opened_source=opened, internal=internal,
                        presentations=lambda f: tables, vector=vector), \
         patch.object(projection.src, "neural", return_value=(None, None, None)) as neural, \
         patch.object(projection.legacy, "behavior", return_value=(None,) * 4), \
         patch.object(projection.legacy, "summaries", return_value=[0.] * 14) as summaries, \
         patch.object(projection.legacy, "behavior_mean", return_value=(2., 1.)):
        yield neural, summaries


class TimelineTests(unittest.TestCase):
    def test_cross_table_next_event_and_table_order_invariance(self):
        a = table("a", [7, 8], [1., 3.])
        b = table("b", [7], [1.2])  # Legal reuse of a table-local ID.
        expected = {("a", 7): 1.2, ("b", 7): 3., ("a", 8): None}
        self.assertEqual(next_onsets([a, b]), expected)
        self.assertEqual(next_onsets([b, a]), expected)

    def test_half_open_boundary_and_final_event(self):
        self.assertTrue(overlaps_post(1., 1.549999, .55))
        self.assertFalse(overlaps_post(1., 1.55, .55))
        self.assertFalse(overlaps_post(1., 1.550001, .55))
        self.assertFalse(overlaps_post(1., None, .55))

    def test_reject_ambiguous_clock_and_identity(self):
        invalid = [
            [], [table("a", [], [])],
            [table("a", [1], [float("nan")])],
            [table("a", [1], [float("inf")])],
            [table("a", [1, 2], [2., 1.])],
            [table("a", [1, 2], [1., 1.])],
            [table("a", [1, 1], [1., 2.])],
            [table("a", [1], [1.]), table("a", [2], [2.])],
            [table("a", [1], [1.]), table("b", [2], [1.])],
            [table("a", [1.5], [1.])],
            [table("a", [True], [1.])],
            [table("a", [1], [True])],
        ]
        for tables in invalid:
            with self.subTest(tables=tables), self.assertRaises(ValueError):
                next_onsets(tables)
        broken = table("a", [1], [1.])
        broken["ids"] = [1, 2]
        with self.assertRaises(ValueError):
            next_onsets([broken])

    def test_single_table_retains_predecessor_boundary(self):
        source = table("a", [1, 2, 3, 4], [0., .4, 1., 1.55])
        following = next_onsets([source])
        retained = [sid for sid, t in zip(source["ids"], source["starts"])
                    if not overlaps_post(t, following[("a", sid)], .55)]
        self.assertEqual(retained, [2, 3, 4])


class ProjectionTests(unittest.TestCase):
    def project(self, tables):
        with generated_source(tables) as controls:
            result = projection.project(HERE / "generated-not-opened.nwb", RECORD, 1)
        return result, controls

    def test_actual_projection_excludes_cross_table_contamination(self):
        a = table("a", [1, 2], [1., 3.])
        b = table("b", [1], [1.2])
        result, (_, summaries) = self.project([a, b])
        self.assertEqual([(r["group"], r["presentation_id"]) for r in result["rows"]],
                         [("a", 2), ("b", 1)])
        self.assertEqual(result["census"]["near_next_presentation"], 1)
        self.assertEqual(result["census"]["all_source_image_rows"], 3)
        self.assertEqual(summaries.call_count, 4)
        self.assertNotIn(1., [call.args[3] for call in summaries.call_args_list])
        self.assertEqual(result["format"], "neural062_projection_v2")
        self.assertIn("presentation-timeline-v2/timeline.py", result["method"])
        self.assertIn("registered-runtime/source/private/extract.py", result["method"])

    def test_later_ineligible_rows_still_bound_current_post_window(self):
        variants = [
            {"omitted": [True], "image_names": ["omitted"]},
            {"blocks": ["other_stimulus_block"]},
            {"changes": [float("nan")]},
            {"ends": [1.21]},
        ]
        for variant in variants:
            with self.subTest(variant=variant):
                result, (_, summaries) = self.project([
                    table("current", [1], [1.]), table("next", [2], [1.2], **variant),
                ])
                self.assertEqual(result["rows"], [])
                self.assertEqual(result["census"]["near_next_presentation"], 1)
                self.assertEqual(sum(v for k, v in result["census"].items()
                                     if k != "all_source_image_rows"), 2)
                summaries.assert_not_called()

    def test_exact_cross_table_endpoint_is_retained(self):
        result, _ = self.project([table("a", [1], [1.]), table("b", [1], [1.55])])
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(result["census"]["near_next_presentation"], 0)
        self.assertEqual(result["rows"][0]["covariates"], [2.] * 4 + [1.] * 4)

    def test_ambiguous_timeline_fails_before_numerical_reads(self):
        with generated_source([table("a", [1], [1.]), table("b", [1], [1.])]) as (neural, summaries):
            with self.assertRaisesRegex(ValueError, "Coincident"):
                projection.project(HERE / "generated-not-opened.nwb", RECORD, 1)
            neural.assert_not_called()
            summaries.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
