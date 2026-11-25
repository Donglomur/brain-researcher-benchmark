"""Generated complete-path controls for signed neuron-contrast cancellation."""
import copy
from fractions import Fraction
import importlib.util
import itertools
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

scorer = load("n088_signed_scorer", HERE / "scorer.py")
paired = load("n088_signed_paired", HERE / "paired_access.py")

def three_neurons(pre_ids=(1, 2, 3)):
    rows = [dict(edge_id=f"edge-{i}", pre_id=pre, post_id=100 + i,
                 projection="A-B", sampling_weight=1)
            for i, pre in enumerate(pre_ids)]
    views = {view: [{"edge_id": row["edge_id"], "mean": mean}
                    for row, mean in zip(rows, means)]
             for view, means in zip(scorer.VIEWS, ([1e299, 1, 0], [0, .5, 1e299]))}
    counts = [{"edge_id": row["edge_id"], "count": 0} for row in rows]
    return rows, views, counts

class ContrastPrecisionControls(unittest.TestCase):
    def test_signed_contrasts_retain_small_gain_after_cancellation(self):
        rows, views, counts = three_neurons()
        for sign in (1, -1):
            predictions = views if sign == 1 else dict(zip(scorer.VIEWS, reversed(list(views.values()))))
            report = scorer.grade(rows, predictions, predictions, lambda: counts, rate_floor=1e-9)
            self.assertEqual(report["status"], "scored")
            # Binary64 per-neuron differences are exactly +2e299, +1, -2e299.
            expected = float(Fraction(sign, 3))
            for key in ("fixed_reference_anatomy_minus_joint", "candidate_self_contrast_descriptive_only"):
                self.assertEqual(report[key]["equal_presynaptic_loss_difference"], expected)
            self.assertEqual(report["fixed_reference_joint_minus_candidate_joint"]["equal_presynaptic_loss_difference"], 0)
            json.dumps(report, allow_nan=False)

    def test_administrative_neuron_labels_do_not_change_contrast(self):
        for identities in itertools.permutations((1, 2, 3)):
            with self.subTest(identities=identities):
                rows, views, counts = three_neurons(identities)
                report = scorer.grade(rows, views, views, lambda: counts, rate_floor=1e-9)
                self.assertEqual(report["fixed_reference_anatomy_minus_joint"]["equal_presynaptic_loss_difference"], float(Fraction(1, 3)))

    def test_complete_paired_panel_preserves_signed_direct_program_contrast(self):
        rows, targets, direct, programme, reference = [], [], [], [], []
        direct_means, program_means = [1e299, 1, 0], [0, .5, 1e299]
        for i in range(6691):
            pre = i % 21
            key = f"generated-edge-{i}"
            rows.append(dict(edge_id=key, pre_id=pre, post_id=100000 + i,
                             projection="A-B", sampling_weight=1))
            targets.append(dict(edge_id=key, count=0))
            direct.append(dict(edge_id=key, mean=direct_means[pre] if pre < 3 else 0))
            programme.append(dict(edge_id=key, mean=program_means[pre] if pre < 3 else 0))
            reference.append(dict(edge_id=key, mean=0))
        bindings = {view: {"query_observations_sha256": "a" * 64,
                           "fit_validation_exposure_sha256": "b" * 64}
                    for view in scorer.VIEWS}
        protocol = dict(rows=rows, rate_floor=1e-9,
                        fixed_reference_views={v: reference for v in scorer.VIEWS},
                        information_bindings={mode: copy.deepcopy(bindings) for mode in paired.MODES})
        submissions = {paired.MODES[0]: {v: direct for v in scorer.VIEWS},
                       paired.MODES[1]: {v: programme for v in scorer.VIEWS}}
        calls = []
        def private():
            calls.append(True)
            return targets
        report = paired.compare(protocol, submissions, private)
        self.assertEqual(report["status"], "scored")
        self.assertEqual(report["edge_n"], 6691)
        self.assertEqual(report["unique_presynaptic_n"], 21)
        self.assertEqual(len(calls), 1)
        self.assertEqual(report["direct_minus_program"]["joint_view_primary_difference"], float(Fraction(1, 21)))
        json.dumps(report, allow_nan=False)

    def test_ordinary_primary_and_unscorable_semantics_are_retained(self):
        rows = [dict(edge_id="a", pre_id=1, post_id=10, projection="A-B", sampling_weight=1),
                dict(edge_id="b", pre_id=1, post_id=11, projection="A-B", sampling_weight=3),
                dict(edge_id="c", pre_id=2, post_id=10, projection="A-B", sampling_weight=1)]
        def views(a, b):
            return {view: [dict(edge_id=row["edge_id"], mean=mu) for row, mu in zip(rows, values)]
                    for view, values in zip(scorer.VIEWS, (a, b))}
        candidate, reference = views([1, 1, 1], [1, 3, 5]), views([1, 1, 1], [2, 2, 2])
        targets = [dict(edge_id=row["edge_id"], count=0) for row in rows]
        report = scorer.grade(rows, candidate, reference, lambda: targets, rate_floor=1e-9)
        self.assertEqual(report["primary"]["value"], 7.5)
        self.assertEqual(report["fixed_reference_anatomy_minus_joint"]["equal_presynaptic_loss_difference"], -2)
        self.assertEqual(report["fixed_reference_joint_minus_candidate_joint"]["equal_presynaptic_loss_difference"], -3.5)
        candidate["anatomy"][0]["mean"] = sys.float_info.max
        report = scorer.grade(rows, candidate, reference, lambda: targets, rate_floor=1e-9)
        self.assertEqual(report["status"], "valid_unscorable_arithmetic")
        self.assertIsNone(report["primary"]["value"])
        self.assertIsNone(report["candidate_self_contrast_descriptive_only"]["equal_presynaptic_loss_difference"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
