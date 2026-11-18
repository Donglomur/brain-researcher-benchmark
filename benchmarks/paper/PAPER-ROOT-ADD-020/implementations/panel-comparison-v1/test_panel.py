"""Generated complete-shape engineering controls; no biological observations."""
import importlib.util
from pathlib import Path
import sys
import unittest
from dataclasses import replace


HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


p = load("paper020_panel", HERE / "panel.py")
d = load("paper020_original_metric", HERE.parent / "feature-decoding-v1" / "decoding.py")
H = "a" * 64


def contract():
    pops = tuple(p.Population(region, region,
        tuple(f"{region}-unfamiliar-{i}" for i in range(1000)),
        tuple(f"{region}-familiar-{i}" for i in range(36)),
        ("feature-x", "feature-y", "feature-z"), ("external-window-opaque-1",), H)
        for region in ("AM", "PR", "TP"))
    conditions = (p.Condition("original", "original", H),) + tuple(
        p.Condition(f"shuffle-{i}", "identity_shuffled", f"{i + 1:064x}") for i in range(10))
    return p.PanelContract(pops, conditions, H, "paper_data")


def scores(pop, value):
    ordinary = d.FeatureCorrelation(value, "defined")
    return d.FeatureCorrelationScores(pop.unfamiliar_ids, (ordinary,) * 1000,
                                      pop.familiar_ids, ((ordinary,) * 36,) * 1000)


def cells(layout, value):
    populations = {pop.identity: pop for pop in layout.populations}
    # Cache only one complete per-population score object in this generated
    # fixture. Production source/control/window values are supplied separately.
    generated = {key: scores(pop, value) for key, pop in populations.items()}
    digest = layout.sha256
    for key in layout.schedule():
        yield p.ScoreCell(key, digest, "b" * 64, generated[key[0]])


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.layout = contract()

    def test_full_support_keeps_signed_and_undefined_dependence(self):
        expected = list(self.layout.schedule())
        observed = []
        def candidate():
            for index, cell in enumerate(cells(self.layout, .5)):
                if index == 0:
                    s = cell.scores
                    row0 = (d.FeatureCorrelation(-.25, "defined"),
                            d.FeatureCorrelation(None, "constant_decoded")) + s.familiar_by_fold[0][2:]
                    s = replace(s, familiar_by_fold=(row0,) + s.familiar_by_fold[1:])
                    cell = replace(cell, scores=s)
                yield cell
        def consume(cell):
            observed.append(cell.key)
            self.assertEqual(len(cell.unfamiliar), 1000)
            self.assertEqual(len(cell.familiar_by_fold), 1000)
            self.assertEqual(len(cell.familiar_by_fold[999]), 36)
            self.assertEqual(cell.unfamiliar[999].candidate_minus_baseline, .25)
            if len(observed) == 1:
                self.assertEqual(cell.familiar_by_fold[0][0].candidate_minus_baseline, -.5)
                self.assertIsNone(cell.familiar_by_fold[0][1].candidate_minus_baseline)
                self.assertEqual(cell.familiar_by_fold[0][1].candidate_state, "constant_decoded")
                self.assertEqual(cell.familiar_by_fold[1][0].candidate_minus_baseline, .25)
        receipt = p.compare_panels(self.layout, cells(self.layout, .25), candidate(), consume)
        self.assertEqual(observed, expected)
        self.assertEqual(receipt["cell_count"], 33)
        self.assertEqual(receipt["correlation_count"], 3 * 11 * (1000 + 1000 * 36))
        self.assertEqual(receipt["undefined_paired_differences"], 1)
        self.assertEqual(receipt["improvement_outcome"], "unknown")
        self.assertIsNone(receipt["paper_win"])
        self.assertNotIn("mean", receipt)
        self.assertNotIn("significance", receipt)

    def test_no_partial_or_extra_completion_receipt(self):
        first = next(cells(self.layout, .25))
        partial_emissions = []
        with self.assertRaisesRegex(p.PanelError, "incomplete"):
            p.compare_panels(self.layout, [first], [first], partial_emissions.append)
        self.assertEqual(len(partial_emissions), 1)
        # Exact-tail rejection exercises the real full schedule, not a reduced
        # three-face stand-in. Earlier emitted cells remain unqualified.
        def extra():
            yield from cells(self.layout, .25)
            yield first
        with self.assertRaisesRegex(p.PanelError, "extra"):
            p.compare_panels(self.layout, extra(), cells(self.layout, .25), lambda _: None)

    def test_region_shuffle_and_source_scope_fail_closed(self):
        for changes in ({"populations": self.layout.populations[:-1]},
                        {"conditions": self.layout.conditions[:-1]},
                        {"conditions": self.layout.conditions[:-1] + (self.layout.conditions[0],)},
                        {"source_scope_sha256": "unknown"},
                        {"access_condition": "pooled_arms"}):
            with self.assertRaises(p.PanelError):
                replace(self.layout, **changes)
        second_window = replace(self.layout.populations[0],
                                window_ids=("window-1", "window-2"))
        layout = replace(self.layout, populations=(second_window,) + self.layout.populations[1:])
        self.assertEqual(layout.cell_count, 44)
        self.assertEqual(len(list(layout.schedule())), 44)
        self.assertNotEqual(layout.sha256, self.layout.sha256)

    def test_reordered_or_cross_condition_inputs_fail_before_emit(self):
        baseline = next(cells(self.layout, .25))
        other_arm = replace(self.layout, access_condition="paper_data_author_code")
        variants = [replace(baseline, key=("PR", baseline.key[1], baseline.key[2])),
                    replace(baseline, contract_sha256=other_arm.sha256),
                    replace(baseline, prediction_commitment_sha256=""),
                    replace(baseline, scores=replace(baseline.scores,
                        familiar_ids=tuple(reversed(baseline.scores.familiar_ids)))),
                    replace(baseline, scores=replace(baseline.scores,
                        familiar_by_fold=baseline.scores.familiar_by_fold[0]))]
        for candidate in variants:
            emitted = []
            with self.assertRaises(p.PanelError):
                p.compare_panels(self.layout, [baseline], [candidate], emitted.append)
            self.assertEqual(emitted, [])

    def test_invalid_values_and_impossible_actual_state_fail(self):
        baseline = next(cells(self.layout, .25))
        for value in (d.FeatureCorrelation(float("nan"), "defined"),
                      d.FeatureCorrelation(True, "defined"),
                      d.FeatureCorrelation(1.01, "defined"),
                      d.FeatureCorrelation(10**10000, "defined"),
                      d.FeatureCorrelation(None, "invented_missing_state"),
                      d.FeatureCorrelation(0., "constant_decoded"),
                      d.FeatureCorrelation(None, "constant_actual")):
            candidate = replace(baseline, scores=replace(baseline.scores,
                                unfamiliar=(value,) + baseline.scores.unfamiliar[1:]))
            with self.assertRaises(p.PanelError):
                p.compare_panels(self.layout, [baseline], [candidate], lambda _: None)

    def test_emitter_failure_never_returns_completion(self):
        first = next(cells(self.layout, .25))
        def fail(_):
            raise OSError("generated sink failure")
        with self.assertRaisesRegex(OSError, "sink failure"):
            p.compare_panels(self.layout, [first], [first], fail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
