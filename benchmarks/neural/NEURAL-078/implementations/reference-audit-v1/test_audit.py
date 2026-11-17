"""Generated controls only; no original recordings, historical gold, or models."""
import contextlib
import copy
import importlib.util
import io
import itertools
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

SPEC = importlib.util.spec_from_file_location("neural078_reference_audit", Path(__file__).with_name("audit.py"))
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
core = audit.load_core()


def packet(person, value=1.0, pairs=12):
    n = pairs * 2
    epochs = np.full((n, 3, 1024), 4096.0, dtype=np.float64)
    epochs[:, :, 614:717] = 0.0
    epochs[:, 0, 102:205] = 0.0
    epochs[:pairs, 0, 614:717] = value
    epochs[:pairs, 1, 614:717] = 2.0
    epochs[:pairs, 2, 614:717] = -3.0
    epochs[:pairs, 0, 102:205] = -4.0
    return {"participant_id": np.asarray(person),
            "trial_ids": np.asarray([f"{person}-{i:024x}" for i in range(n)]),
            "epochs": epochs, "response_error": np.asarray([1] * pairs + [0] * pairs, dtype=np.uint8),
            "response_hand": np.asarray([1 + (i % 4) // 2 for i in range(pairs)] * 2, dtype=np.uint8),
            "stimulus_congruency": np.asarray([1 + i % 2 for i in range(pairs)] * 2, dtype=np.uint8),
            "rt_samples": np.asarray([500] * n, dtype=np.int64),
            "sample_offsets": np.arange(-614, 410, dtype=np.int16),
            "channels": np.asarray(["FCz_reref", "HEOG_bipolar", "VEOG_bipolar"]),
            "units": np.asarray("native_EEGLAB_amplitude")}


def unrestricted_objective(es, cs, rt):
    """Tiny exhaustive assignment oracle; includes crossing and unmatched pairs."""
    if not es:
        return (0, 0)
    e = es[0]
    options = [unrestricted_objective(es[1:], cs, rt)]
    for c in cs:
        distance = abs(rt[e] - rt[c])
        if distance * 1000 <= 25 * 1024:
            count, cost = unrestricted_objective(es[1:], [v for v in cs if v != c], rt)
            options.append((count + 1, cost - distance))
    return max(options)


class MatchingTests(unittest.TestCase):
    def test_exhaustive_unrestricted_objective_and_source_ties(self):
        # 1,600 panels cover empty sides, duplicates, cardinality/cost tradeoffs,
        # and exact 25-vs-26-sample caliper boundaries without sampling outcomes.
        panels = 0
        for m, n in itertools.product(range(4), repeat=2):
            for rt in itertools.product((500, 525, 526), repeat=m + n):
                es, cs = list(range(m)), list(range(m, m + n))
                ids = [f"t-{i:02}" for i in reversed(range(m + n))]
                pairs = audit.prefix_pairs(es, cs, rt, ids)
                self.assertEqual((len(pairs), -sum(abs(rt[e] - rt[c]) for e, c in pairs)),
                                 unrestricted_objective(es, cs, rt))
                self.assertEqual(pairs, core.optimal_pairs(es, cs, rt, ids))
                panels += 1
        self.assertEqual(panels, 1600)

    def test_cardinality_precedes_distance_and_tie_uses_identity(self):
        rt, ids = [500, 525, 525, 550], ["e0", "e1", "c0", "c1"]
        self.assertEqual(audit.prefix_pairs([0, 1], [2, 3], rt, ids), [(0, 2), (1, 3)])
        rt, ids = [500] * 4, ["e-b", "e-a", "c-b", "c-a"]
        self.assertEqual(audit.prefix_pairs([0, 1], [2, 3], rt, ids), [(1, 3), (0, 2)])

    def test_strata_cannot_borrow_pair_support(self):
        d = packet("sub-001")
        d["response_hand"][:12] = 1
        d["response_hand"][12:] = 2
        row = audit.independent_summary(d, "sub-001")
        self.assertEqual(row["matched_pairs_n"], 0)
        self.assertTrue(all(row[k] is None for k in audit.NUMBERS))


class ArithmeticTests(unittest.TestCase):
    def test_analytic_eight_person_windows_controls_and_descriptive_se(self):
        values = [-2, -1, 0, 1, 2, 3, 4, 5]
        report, check = audit.audit_packets(((p, packet(p, v)) for p, v in zip(audit.PEOPLE, values)), core)
        self.assertEqual(check["checked_fields"], 195)
        self.assertEqual(report["aggregate"][audit.AGGREGATES[0]], 1.5)
        self.assertAlmostEqual(report["aggregate"][audit.AGGREGATES[1]], math.sqrt(0.75))
        for row, value in zip(report["participants"], values):
            self.assertEqual(row["matched_FCz_contrast"], value)
            self.assertEqual(row["unmatched_FCz_contrast"], value)
            self.assertEqual(row["matched_HEOG_contrast"], 2)
            self.assertEqual(row["matched_VEOG_contrast"], -3)
            self.assertEqual(row["matched_preresponse_FCz_placebo"], -4)
            self.assertEqual(row["matched_pairs_n"], 12)
            self.assertEqual(row["mean_RT_difference_ms"], 0)
            self.assertTrue(all(s["pairs_n"] == 3 for s in row["stratum_support"].values()))

    def test_units_and_exact_inclusive_window_endpoints(self):
        d = packet("sub-001", value=0)
        d["epochs"][:, :, :] = 0
        # One value at each included endpoint, with larger adjacent excluded values.
        for index in (614, 716):
            d["epochs"][:12, 0, index] = 103
        for index in (613, 717, 101, 205):
            d["epochs"][:12, 0, index] = 10000
        for index in (102, 204):
            d["epochs"][:12, 0, index] = -103
        d["rt_samples"][:12] += 25
        row = audit.independent_summary(d, "sub-001")
        self.assertEqual(row["matched_FCz_contrast"], 2)
        self.assertEqual(row["matched_preresponse_FCz_placebo"], -2)
        self.assertEqual(row["mean_RT_difference_ms"], 25 * 1000 / 1024)
        self.assertEqual(row["max_abs_RT_difference_ms"], 25 * 1000 / 1024)

    def test_one_unsupported_person_preserves_all_nulls(self):
        report, check = audit.audit_packets(((p, packet(p, pairs=9 if i == 3 else 12))
                                            for i, p in enumerate(audit.PEOPLE)), core)
        self.assertEqual(check["checked_fields"], 195)
        self.assertEqual(report["aggregate"]["status"], "not_all_participants_supported")
        self.assertTrue(all(report["aggregate"][k] is None for k in audit.AGGREGATES))
        self.assertTrue(all(report["participants"][3][k] is None for k in audit.NUMBERS))

    def test_row_permutation_preserves_pairs_digest_and_arithmetic(self):
        d = packet("sub-001", value=-5)
        expected = audit.independent_summary(d, "sub-001")
        order = np.arange(24)[::-1]
        reordered = {k: v[order] if k in ("trial_ids", "epochs", "response_error", "response_hand",
                                          "stimulus_congruency", "rt_samples") else v for k, v in d.items()}
        self.assertEqual(audit.independent_summary(reordered, "sub-001"), expected)

    def test_disagreement_in_support_or_numerics_is_refused(self):
        row = audit.independent_summary(packet("sub-001"), "sub-001")
        for key, changed in (("pair_digest", "0" * 64), ("matched_FCz_contrast", 3),
                             ("matched_HEOG_contrast", float("nan"))):
            other = copy.deepcopy(row)
            other[key] = changed
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit.check_agreement(row, other)

    def test_missing_or_repeated_people_and_invalid_rt_refused(self):
        with self.assertRaisesRegex(ValueError, "cohort"):
            audit.audit_packets(((p, packet(p)) for p in audit.PEOPLE[:-1]), core)
        with self.assertRaisesRegex(ValueError, "cohort"):
            audit.audit_packets(((audit.PEOPLE[0], packet(audit.PEOPLE[0])) for _ in range(8)), core)
        d = packet("sub-001")
        d["rt_samples"][0] = (1 << 61) + 512
        with self.assertRaisesRegex(ValueError, "Eligible marker RT"):
            audit.audit_packets(iter([("sub-001", d)]), core)

    def test_independent_matcher_does_not_use_source_pairing(self):
        d = packet("sub-001")
        with mock.patch.object(core, "optimal_pairs", side_effect=AssertionError("source matcher used")):
            self.assertEqual(audit.independent_summary(d, "sub-001")["matched_pairs_n"], 12)


class CLITests(unittest.TestCase):
    def make_inputs(self, root):
        data = root / "packets"
        data.mkdir()
        pins = {}
        for p in audit.PEOPLE:
            path = data / (p + ".npz")
            np.savez_compressed(path, **packet(p))
            pins[p] = audit.pin(path.read_bytes())
        pins_path = root / "pins.json"
        pins_path.write_text(json.dumps(pins))
        return ["--packet-directory", str(data), "--packet-pins", str(pins_path),
                "--output-directory", str(root / "output")]

    def test_complete_cli_new_outputs_and_pinned_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.make_inputs(root)
            self.assertEqual(audit.main(args), 0)
            receipt = json.loads((root / "output/AUDIT.json").read_text())
            self.assertEqual(receipt["comparison"]["checked_fields"], 195)
            self.assertFalse(receipt["historical_reference_opened"])
            self.assertEqual(receipt["reference"], audit.pin((root / "output/REFERENCE.json").read_bytes()))
            self.assertEqual(receipt["source_core_sha256"], audit.CORE_SHA256)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(audit.main(args), 2)

    def test_wrong_packet_pin_never_publishes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.make_inputs(root)
            pins = json.loads((root / "pins.json").read_text())
            pins[audit.PEOPLE[-1]]["sha256"] = "0" * 64
            (root / "pins.json").write_text(json.dumps(pins))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(audit.main(args), 2)
            self.assertFalse((root / "output").exists())

    def test_source_replacement_refused_before_import(self):
        with mock.patch.object(audit, "read_bounded", return_value=b"raise AssertionError('imported')"):
            with self.assertRaisesRegex(ValueError, "source identity"):
                audit.load_core()

    def test_duplicate_pins_and_nonfinite_json_refused(self):
        for raw in (b'{"a":0,"a":1}', b'{"a":NaN}'):
            with self.assertRaises(ValueError):
                audit.strict_json(raw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
