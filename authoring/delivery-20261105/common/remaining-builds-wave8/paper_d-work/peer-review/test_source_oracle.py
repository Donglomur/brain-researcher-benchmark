"""Independent invented-only review of the held MATLAB source's supported domain.

The oracle reduces each selected raw-column mean analytically, then applies the
full-event mean/SD. It does not call or copy the component's normalization,
window, or averaging helpers. Decimal precision is an arithmetic cross-check,
not a MATLAB runtime/precision qualification. No authentic arrays or rosters.
"""
import copy
from decimal import Decimal, localcontext
import hashlib
import math
from pathlib import Path
import sys
import unittest

LANE = Path(__file__).resolve().parents[1]
ROOT = LANE.parents[2]
sys.path.insert(0, str(LANE))
import ofc_tca_inputs as component

EVENTS = ("COFF", "SON", "SOFF", "Rew", "Opt")
BLOCKS = (3, 1, 2)
SOURCE = ROOT / "ofc-belief/private/author_code/analysis/Electrophysiology/makeTensor_TCA.m"
SOURCE_SHA256 = "6372e3fe24b6363a9b685019a7ef886c1d14bb423f92cbe26e9f4472872f63a9"


def invented_session(name="review-invented-session", cohort="Expert"):
    return {
        "session_id": name, "animal_id": "review-invented-animal", "cohort": cohort,
        "S": {"Block": [3, 1, 2, 3, 1, 2, 3, 1, 2],
              "vios": [0, 0, 0, 0, 1, 0, 0, 0, 0]},
        "SU": [
            {"cluster_id": 71 - unit * 7, "xvec": {"COFF": [-2., -1., -.4, 0., .8, 1., 2.]},
             "hmat": {event: [[float(((row + 2) * (column + 3) + row * row * 11
                                       - column * column + ei * 19 + (unit + 1) * column * 7)
                                      % 97 - 40 + row * 3 - ei * column)
                                for column in range(7)] for row in range(9)]
                      for ei, event in enumerate(EVENTS)}}
            for unit in range(5)]}


def raw_mean_oracle(session, *, cropped_normalizer=False, population_sd=False,
                    elementwise_gate=False):
    """Closed-form raw-mean equivalent on a fixed invented integer-valued grid."""
    # All index values are explicit independent expectations for this fixture.
    event_columns = (range(1, 6), range(1, 6), range(1, 6), range(1, 5), range(1, 5))
    selected = [[r for r, (b, v) in enumerate(zip(session["S"]["Block"], session["S"]["vios"]))
                 if b == block and v == 0] for block in BLOCKS]
    assert all(len(rows) != 1 for rows in selected)
    answer = [[[0.0] * 3 for _ in range(23)] for _ in session["SU"]]
    start = 0
    with localcontext() as context:
        context.prec = 60
        for event, columns in zip(EVENTS, event_columns):
            moments = []
            for unit in session["SU"]:
                matrix = unit["hmat"][event]
                vals = [Decimal(int(value)) for row in matrix
                        for column, value in enumerate(row)
                        if not math.isnan(value) and (not cropped_normalizer or column in columns)]
                if not vals:
                    moments.append(None)
                    continue
                n = Decimal(len(vals))
                mu = sum(vals) / n
                # Independent second-moment identity, not centered float reduction.
                ss = sum(value * value for value in vals) - sum(vals) * sum(vals) / n
                sd = (ss / (n if population_sd else max(Decimal(1), n - 1))).sqrt()
                moments.append((mu, sd) if sd else None)
            for bi, rows in enumerate(selected):
                local = []
                for unit, moment in zip(session["SU"], moments):
                    means = []
                    for col in columns:
                        vals = [Decimal(int(unit["hmat"][event][row][col])) for row in rows
                                if not math.isnan(unit["hmat"][event][row][col])]
                        means.append(None if not vals or moment is None else
                                     float((sum(vals) / Decimal(len(vals)) - moment[0]) / moment[1]))
                    local.append(means)
                any_nan = any(value is None for row in local for value in row)
                if elementwise_gate or not any_nan:
                    for ui, row in enumerate(local):
                        for ci, value in enumerate(row):
                            if value is not None:
                                answer[ui][start + ci][bi] = value
            start += len(columns)
    return answer


def greatest_difference(a, b):
    return max(abs(x - y) for au, bu in zip(a, b) for ar, br in zip(au, bu)
               for x, y in zip(ar, br))


class IndependentHeldSourceReview(unittest.TestCase):
    def test_exact_source_bytes_and_semantic_statements(self):
        data = SOURCE.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), SOURCE_SHA256)
        source = data.decode()
        for statement in (
            "events = {'COFF' 'SON' 'SOFF' 'Rew' 'Opt'};",
            "check = find(diff(S.Block));", "if n < 5 || length(check) < 4",
            "blockVec = [3, 1, 2];",
            "zscore = @(x) (x - mean(x,'all','omitnan')) / std(x,0,'all','omitnan');",
            "find(round(SU(1).xvec.COFF, 3) == x)",
            "timeBin = [-1 0.8];", "mean(zSU{x}(trials{ii},w(1):w(2)), 'omitnan')",
            "if ~isnan(avg_resp)", "initial(:,:,ii) = avg_resp;",
        ):
            self.assertIn(statement, source)

    def test_decimal_oracle_all_events_units_and_block_means(self):
        session = invented_session()
        # Include missing data that has a remaining selected observation, a
        # violation-row outlier, and an out-of-window outlier in different events.
        session["SU"][2]["hmat"]["SON"][0][3] = math.nan
        session["SU"][1]["hmat"]["Opt"][4][2] = 10001.0
        session["SU"][3]["hmat"]["SOFF"][5][6] = -10003.0
        observed = component.prepare_session(session)
        self.assertEqual(observed["report"]["status"], "transformed")
        self.assertLess(greatest_difference(observed["data"], raw_mean_oracle(session)), 2e-15)
        self.assertEqual([x["event"] for x in observed["layout"]], list(EVENTS))
        self.assertEqual([len(x["times_s"]) for x in observed["layout"]], [5, 5, 5, 4, 4])
        self.assertEqual([x["cluster_id"] for x in observed["tensor_info"]], [71, 64, 57, 50, 43])
        # These plausible incorrect oracles must visibly disagree on these inputs.
        self.assertGreater(greatest_difference(raw_mean_oracle(session),
                                               raw_mean_oracle(session, cropped_normalizer=True)), .1)
        self.assertGreater(greatest_difference(raw_mean_oracle(session),
                                               raw_mean_oracle(session, population_sd=True)), .001)

    def test_matrix_gate_oracle_detects_elementwise_repair(self):
        session = invented_session()
        for row in (0, 3, 6):
            session["SU"][4]["hmat"]["COFF"][row][2] = math.nan
        actual = component.prepare_session(session)
        expected = raw_mean_oracle(session)
        self.assertLess(greatest_difference(actual["data"], expected), 2e-15)
        self.assertGreater(greatest_difference(expected, raw_mean_oracle(session, elementwise_gate=True)), .1)
        self.assertTrue(all(row[0] == 0.0 for unit in actual["data"] for row in unit[:5]))
        self.assertTrue(actual["report"]["event_block_gates"][0]["zero_initialized_retained"])

    def test_literal_transition_gate_and_absent_block_source_behavior(self):
        session = invented_session()
        session["S"]["Block"] = [1, 2, 1, 2, 1, 2, 1, 2, 1]
        session["S"]["vios"] = [0] * 9
        actual = component.prepare_session(session)
        self.assertEqual(actual["report"]["status"], "transformed")
        self.assertEqual(actual["report"]["block_transitions"], 8)
        self.assertLess(greatest_difference(actual["data"], raw_mean_oracle(session)), 2e-15)
        self.assertEqual(actual["report"]["selected_source_rows_one_based"][0], [])

    def test_singleton_remains_unsupported_with_every_identity(self):
        session = invented_session()
        session["S"]["vios"][0] = session["S"]["vios"][3] = 1
        actual = component.prepare_session(session)
        self.assertEqual(actual["report"]["status"], "unsupported")
        self.assertIn("singleton", actual["report"]["reason"])
        self.assertEqual(actual["report"]["cluster_ids"], [71, 64, 57, 50, 43])
        self.assertIsNone(actual["data"])

    def test_nonconstant_underflow_is_hold_not_false_constant_zero_slice(self):
        session = invented_session()
        for row in session["SU"][2]["hmat"]["SON"]:
            row[:] = [value * 1e-200 for value in row]
        actual = component.prepare_session(session)
        self.assertEqual(actual["report"]["status"], "unsupported")
        self.assertIn("underflow", actual["report"]["reason"])
        self.assertIsNone(actual["data"])
        self.assertEqual(actual["report"]["cluster_ids"], [71, 64, 57, 50, 43])

    def test_complete_invented_rosters_order_and_partial_output_refusal(self):
        for cohort, count in (("Expert", 191), ("Naive", 96)):
            sessions = [{"session_id": "review-invented-%s-%03d" % (cohort, i),
                         "animal_id": "review-invented-animal-%d" % (i % 11), "cohort": cohort,
                         "S": {"Block": [3, 1, 2, 3, 1, 2]}, "SU": []}
                        for i in range(count)]
            # Position near the end exposes accidental prefix-only processing.
            for i in (1, count - 2):
                sessions[i] = invented_session(sessions[i]["session_id"], cohort)
            roster = [s["session_id"] for s in sessions]
            actual = component.prepare_cohort(sessions, cohort=cohort, expected_session_ids=roster)
            self.assertEqual(actual["status"], "transformed")
            self.assertEqual([r["session_id"] for r in actual["reports"]], roster)
            self.assertEqual([r["session_id"] for r in actual["tensor_info"]],
                             [roster[1]] * 5 + [roster[count - 2]] * 5)
            self.assertFalse(actual["whole_task_complete"])
            self.assertFalse(actual["native_parity"])
            self.assertEqual(actual["all_source_session_ids"], roster)
            bad = copy.deepcopy(sessions)
            bad[-2]["S"]["vios"][0] = bad[-2]["S"]["vios"][3] = 1
            held = component.prepare_cohort(bad, cohort=cohort, expected_session_ids=roster)
            self.assertEqual(held["status"], "unsupported")
            self.assertEqual(len(held["reports"]), count)
            self.assertEqual(held["all_source_session_ids"], roster)
            self.assertIsNone(held["data"])
            self.assertEqual(held["tensor_info"], [])
            with self.assertRaisesRegex(component.Unsupported, "coverage/order"):
                component.prepare_cohort(sessions[:-1], cohort=cohort, expected_session_ids=roster)


if __name__ == "__main__":
    unittest.main(verbosity=2)
