"""Generated software controls only; never load authentic source or targets."""
import bisect
import importlib.util
from pathlib import Path
import unittest

import numpy as np


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


windows, views = load("windows"), load("views")


def source():
    t = np.arange(0, 300.5, .5)
    return np.column_stack((t, 1000 + 2 * t)), t, (np.arange(len(t)) % 2).astype(float), t.copy()


class WindowProjection(unittest.TestCase):
    def test_complete_literal_grid_and_independent_predecessor_oracle(self):
        x, t, state, clock = source()
        out = windows.project(x, t, state, clock)
        self.assertEqual({k: v.shape for k, v in out.items()}, {
            "neural": (5, 300, 2), "shifted": (5, 300, 2), "history": (5, 300),
            "target": (5,), "persistence": (5,)})
        self.assertTrue(all(v.dtype == np.dtype("<f8") for v in out.values()))
        for block in range(5):
            for step in (0, 1, 149, 299):
                at = 60 * block + 10.05 + step * .1
                index = bisect.bisect_right(t.tolist(), at) - 1
                np.testing.assert_array_equal(out["neural"][block, step], x[index])
                shifted = bisect.bisect_right(t.tolist(), 60 * block + .05 + step * .1) - 1
                np.testing.assert_array_equal(out["shifted"][block, step], x[shifted])
            target_values = [state[bisect.bisect_right(clock.tolist(), 60 * block + 50.05 + j * .1) - 1]
                             for j in range(100)]
            self.assertEqual(out["target"][block], sum(target_values) / 100)
        np.testing.assert_array_equal(out["target"], np.full(5, .5))

    def test_irregular_clock_uses_predecessor_and_exact_equality_not_next_sample(self):
        _, _, state, clock = source()
        t = np.array([0., 10., 10.04, 10.05, 10.06, 39.94, 39.96, 60., 300.])
        x = np.column_stack((np.arange(len(t)), np.arange(len(t)) + 100)).astype(float)
        out = windows.project(x, t, state, clock)
        np.testing.assert_array_equal(out["neural"][0, 0], x[3])
        np.testing.assert_array_equal(out["neural"][0, 1], x[4])
        np.testing.assert_array_equal(out["neural"][0, -1], x[5])

    def test_later_values_cannot_change_earlier_input_and_shift_is_not_wraparound(self):
        x, t, state, clock = source()
        before = windows.project(x, t, state, clock)
        x[t >= 40] += 10000
        state[clock >= 40] = 1
        after = windows.project(x, t, state, clock)
        for field in ("neural", "shifted", "history", "persistence"):
            np.testing.assert_array_equal(before[field][0], after[field][0])
        self.assertNotEqual(before["target"][0], after["target"][0])
        self.assertEqual(after["shifted"][0, 0, 0], 0)

    def test_geometry_types_missing_values_and_duplicate_clock_fail_closed(self):
        cases = []
        x, t, state, clock = source()
        cases.extend([(x[:, :0], t, state, clock), (x, t[:, None], state, clock),
                      (x, t, state[:, None], clock), (x, t, state, clock[:, None]),
                      (x[:-1], t, state, clock), (x.astype(object), t, state, clock),
                      (np.ma.array(x, mask=False), t, state, clock)])
        if np.dtype(np.longdouble).itemsize > 8:
            cases.append((x.astype(np.longdouble), t, state, clock))
        for operand in range(4):
            row = [v.copy() for v in source()]
            row[operand].flat[0] = np.nan
            cases.append(row)
        row = list(source()); row[1][3] = row[1][2]; cases.append(row)
        row = list(source()); row[2][0] = .5; cases.append(row)
        # Subtraction-based checks can wrap a decreasing unsigned clock.
        row = list(source()); row[1] = np.arange(len(row[1]), dtype=np.uint64)
        row[1][10] = 1; cases.append(row)
        for i, args in enumerate(cases):
            with self.subTest(case=i), self.assertRaises(ValueError):
                windows.project(*args)

    def test_no_extrapolation_at_any_of_three_grids(self):
        x, t, state, clock = source()
        for args in ((x[1:], t[1:], state, clock),
                     (x, t, state[clock >= 10.5], clock[clock >= 10.5]),
                     (x[t <= 279], t[t <= 279], state, clock),
                     (x, t, state[clock <= 299], clock[clock <= 299])):
            with self.assertRaises(ValueError):
                windows.project(*args)
        # Behavior does not serve the earlier shifted-neural grid. Its clock
        # need only cover the actual history/future grids, not the entire session.
        windows.project(x, t, state[clock >= 10], clock[clock >= 10])


class GuardedMapping:
    def __init__(self, allowed):
        self.allowed, self.reads = allowed, []

    def __getitem__(self, name):
        self.reads.append(name)
        if name not in self.allowed:
            raise AssertionError("forbidden field lookup: " + name)
        return self.allowed[name]


class ViewProjection(unittest.TestCase):
    def setUp(self):
        self.fields = windows.project(*source())

    def test_all_query_arms_read_only_selected_fields_never_targets_or_persistence(self):
        for arm in views.ARMS:
            permitted = {"history": self.fields["history"]}
            if arm != "history":
                name = "shifted" if arm == "shift" else "neural"
                permitted[name] = self.fields[name]
            mapping = GuardedMapping(permitted)
            result = views.project_view(mapping, "query", arm)
            self.assertEqual(set(mapping.reads), set(permitted))
            self.assertEqual(set(result), {"history"} if arm == "history" else {"history", "neural"})

    def test_training_adds_only_targets_and_preserves_four_arm_transformations(self):
        for arm in views.ARMS:
            view = views.project_view(self.fields, "train", arm)
            np.testing.assert_array_equal(view["target"], self.fields["target"])
            np.testing.assert_array_equal(view["history"], self.fields["history"])
            if arm != "history":
                want = self.fields["shifted"] if arm == "shift" else self.fields["neural"]
                if arm == "reverse":
                    want = want[:, ::-1, :]
                np.testing.assert_array_equal(view["neural"], want)
            self.assertNotIn("persistence", view)

    def test_invalid_role_or_arm_fails_before_any_field_read(self):
        for role, arm in (("test", "joint"), ("query", "neural"), (None, "history")):
            mapping = GuardedMapping({})
            with self.assertRaises(ValueError):
                views.project_view(mapping, role, arm)
            self.assertEqual(mapping.reads, [])

    def test_outputs_do_not_alias_operator_arrays(self):
        originals = {k: v.copy() for k, v in self.fields.items()}
        for arm in views.ARMS:
            result = views.project_view(self.fields, "train", arm)
            for value in result.values():
                value.flat[0] = 12345
        for key in originals:
            np.testing.assert_array_equal(self.fields[key], originals[key])

    def test_bad_selected_array_fails_but_irrelevant_fields_are_not_touched(self):
        fields = dict(self.fields)
        fields["target"] = np.array([2., 0., 0., 0., 0.])
        with self.assertRaises(ValueError):
            views.project_view(fields, "train", "history")
        views.project_view(fields, "query", "history")
        for value in (np.zeros((5, 299, 2)), np.zeros((5, 300, 0)),
                      np.full((5, 300, 2), np.inf), np.zeros((5, 300, 2), dtype=np.float32),
                      np.ma.array(np.zeros((5, 300, 2)), mask=False)):
            fields = dict(self.fields); fields["neural"] = value
            with self.assertRaises(ValueError):
                views.project_view(fields, "query", "joint")
            views.project_view(fields, "query", "history")


if __name__ == "__main__":
    unittest.main()
