"""Generated full-shape software controls; no authentic data or model runs."""
import copy
import hashlib
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import scorer
import targets


def sha(value):
    return hashlib.sha256(repr(value).encode()).hexdigest()


def fixture():
    d = scorer.load_sources()
    c = d["controls"]
    original, roster = {}, []
    for ordinal in range(1, 40):
        query_count = 52 if ordinal < 39 else 66
        row = dict(ordinal=ordinal, session="generated-session-" + str(ordinal),
                   mouse="generated-mouse-" + str((ordinal - 1) % 10),
                   counts={"fitval": 50, "query": query_count}, original_manifests={})
        original[ordinal] = {}
        for arm in c.ORIGINAL_ARMS:
            original[ordinal][arm], row["original_manifests"][arm] = {}, {}
            for phase in c.PHASES:
                doc = dict(schema="neural093-candidate-public-packet-v1", candidate_id="NEURAL-093",
                           arm=arm, phase=phase, session_token=sha(("session", ordinal)),
                           case_tokens=[sha((ordinal, phase, i)) for i in range(row["counts"][phase])],
                           case_splits=["fit"] * 40 + ["validation"] * 10 if phase == "fitval"
                           else ["query"] * query_count, unit_count=5,
                           wheel_observations_present=arm == c.ORIGINAL_ARMS[1],
                           query_labels_present=False, observation=c.parent.OBSERVATION,
                           files={name: dict(bytes=20, sha256=sha((ordinal, name, phase if name != "units.npz" else "")), role=role)
                                  for name, role in c.parent.roles(arm, phase).items()})
                raw = c.encoded(doc)
                original[ordinal][arm][phase] = raw
                row["original_manifests"][arm][phase] = dict(path="generated", **c.pin(raw))
        roster.append(row)
    binding = dict(schema="neural093_prospective_control_binding_v1", task_id="NEURAL-093",
                   required_queries=2042, roster=roster)
    # Only generated tests bypass the immutable authentic binding pin.
    panel = c._prepare_panel(original, binding)
    plan = dict(schema="neural093_four_arm_operator_plan_v1", packet_count=312,
                prediction_count=156, sessions=[])
    commit = dict(schema="neural093_prospective_four_arm_commit_v1", program_sha256=sha("program"),
                  recipe_sha256=sha("recipe"), tuning_policy_sha256=sha("policy"),
                  program_frozen_before_first_fitval=True, same_reviewed_tuning_policy_and_budget=True,
                  separate_fits_per_arm=True, all_four_models_sealed_before_each_query_release=True,
                  all_predictions_committed_before_any_feedback=True,
                  all_owned_producers_absent_before_grading=True, private_grading_started=False, sessions={})
    outputs, private = {}, {}
    for session in panel["sessions"]:
        token = session["session_token"]
        mapping = dict(schema="neural093-candidate-private-session-v1",
                       **{k: session[k] for k in ("ordinal", "session", "mouse", "session_token")},
                       query=[dict(token=t, source_row=i, target=0) for i, t in enumerate(session["query_tokens"])],
                       public_manifests={arm: {"query": c.pin(session["original_manifest_bytes"][arm]["query"])}
                                         for arm in c.ORIGINAL_ARMS})
        body = c.encoded(mapping)
        private[token] = body
        planned = dict(ordinal=session["ordinal"], session_token=token, packets={},
                       private_mapping=dict(path=token, **c.pin(body)))
        entry = dict(query_tokens_sha256=c.pin(c.encoded(session["query_tokens"]))["sha256"], arms={})
        for arm in c.ARMS:
            planned["packets"][arm] = {}
            for phase in c.PHASES:
                raw = (session["original_manifest_bytes"] if arm in c.ORIGINAL_ARMS else session["control_manifest_bytes"])[arm][phase]
                doc = c.parse(raw, c.MAX_MANIFEST)
                planned["packets"][arm][phase] = dict(manifest=c.pin(raw), files=doc["files"])
            output = c.encoded(dict(schema="neural093-candidate-predictions-v1", arm=arm,
                                    session_token=token, candidate_sha256=commit["program_sha256"],
                                    predictions=[dict(token=t, probabilities=[1/3] * 3)
                                                 for t in reversed(session["query_tokens"])]))
            outputs[token, arm] = output
            entry["arms"][arm] = dict(fit_instance_id=sha((token, arm)), model=c.pin(b"generated model"),
                                      prediction=c.pin(output), query_manifest=planned["packets"][arm]["query"]["manifest"])
        commit["sessions"][token] = entry
        plan["sessions"].append(planned)
    return d, panel, plan, commit, outputs, private


class ScoringControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = fixture()

    def arrange(self):
        d, *values = self.data
        return d, *copy.deepcopy(values)

    def update(self, d, commit, outputs, key, change):
        c = d["controls"]
        doc = c.parse(outputs[key], 262144)
        change(doc)
        outputs[key] = c.encoded(doc)
        commit["sessions"][key[0]]["arms"][key[1]]["prediction"] = c.pin(outputs[key])

    def test_uniform_full_panel_and_token_alignment(self):
        d, panel, plan, commit, outputs, private = self.arrange()
        calls = []
        result = scorer.score_study(panel, plan, commit, outputs,
                                   lambda desc: calls.append(desc["path"]) or private[desc["path"]], np)
        self.assertEqual(len(calls), 39)
        self.assertAlmostEqual(result["primary"]["value"]["value"], math.log(3))
        report = result["recovered_four_arm_summary"]
        self.assertEqual((report["sessions"], report["mice"], report["queries_per_arm"]), (39, 10, 2042))
        for arm in d["controls"].ARMS:
            metrics = report["equal_mouse_absolute_metrics"][arm]
            self.assertAlmostEqual(metrics["multiclass_Brier_mean_sum3"]["value"], 2/3)
            self.assertEqual(metrics["top1_accuracy"]["value"], 1.0)  # Fixed tie: class 0.
        self.assertEqual(report["uncertainty"]["lower"], 0)
        self.assertEqual(report["uncertainty"]["upper"], 0)
        self.assertFalse(result["participant_runtime_qualified"])

    def test_equal_session_then_mouse_is_not_trial_pooling(self):
        d, panel, plan, commit, outputs, private = self.arrange()
        losses = {}
        for session in panel["sessions"]:
            loss = (session["ordinal"] % 7 + 1) / 3
            losses[session["session_token"]] = loss
            p = math.exp(-loss)
            for arm in d["controls"].ARMS:
                self.update(d, commit, outputs, (session["session_token"], arm),
                            lambda doc, p=p: [row.update(probabilities=[p, (1-p)/2, (1-p)/2]) for row in doc["predictions"]])
        result = scorer.score_study(panel, plan, commit, outputs, lambda desc: private[desc["path"]], np)
        expected = math.fsum(math.fsum(losses[s["session_token"]] for s in panel["sessions"] if s["mouse"] == mouse)
                             / sum(s["mouse"] == mouse for s in panel["sessions"])
                             for mouse in sorted({s["mouse"] for s in panel["sessions"]})) / 10
        pooled = math.fsum(losses[s["session_token"]] * len(s["query_tokens"]) for s in panel["sessions"]) / 2042
        self.assertAlmostEqual(result["primary"]["value"]["value"], expected)
        self.assertNotAlmostEqual(expected, pooled, places=5)

    def test_malformed_last_output_prevents_every_target_read(self):
        mutations = [lambda doc: doc["predictions"][-1].update(probabilities=[.9, .9, .9]),
                     lambda doc: doc["predictions"][-1].update(probabilities=[True, 0, 0]),
                     lambda doc: doc["predictions"][-1].update(token=doc["predictions"][0]["token"]),
                     lambda doc: doc["predictions"].pop()]
        for mutate in mutations:
            d, panel, plan, commit, outputs, private = self.arrange()
            key = (panel["sessions"][-1]["session_token"], d["controls"].ARMS[-1])
            self.update(d, commit, outputs, key, mutate)
            calls = []
            with self.assertRaises(ValueError):
                scorer.score_study(panel, plan, commit, outputs, lambda desc: calls.append(desc), np)
            self.assertEqual(calls, [])

    def test_matched_neural_gain_keeps_loss_and_accuracy_directions(self):
        d, panel, plan, commit, outputs, private = self.arrange()
        for key in outputs:
            p = [.6, .2, .2] if key[1] in d["controls"].ORIGINAL_ARMS else [.2, .4, .4]
            self.update(d, commit, outputs, key,
                        lambda doc, p=p: [row.update(probabilities=p) for row in doc["predictions"]])
        result = scorer.score_study(panel, plan, commit, outputs, lambda desc: private[desc["path"]], np)
        self.assertAlmostEqual(result["primary"]["value"]["value"], -math.log(.6))
        report = result["recovered_four_arm_summary"]
        effect = report["equal_mouse_improvements"]["neural_increment_given_wheel_context"]
        self.assertAlmostEqual(effect["natural_log_loss"]["value"], math.log(3))
        self.assertAlmostEqual(effect["multiclass_Brier_mean_sum3"]["value"], .72)
        self.assertEqual(effect["top1_accuracy"]["value"], 1.)
        self.assertAlmostEqual(report["uncertainty"]["lower"], math.log(3))
        self.assertAlmostEqual(report["uncertainty"]["upper"], math.log(3))

    def test_probability_tolerance_normalizes_without_clipping(self):
        core = self.data[0]["score_core"]
        values = np.array([[.2, .3, .5 + 5e-9]])
        actual = core.probabilities(values, np)
        np.testing.assert_array_equal(actual, values / values.sum(axis=1)[:, None])
        with self.assertRaises(ValueError):
            core.probabilities(np.array([[.2, .3, .5 + 2e-8]]), np)
        with self.assertRaises(ValueError):
            core.probabilities(np.array([[np.nan, 0., 1.]]), np)

    def test_truncated_plan_and_missing_arm_fail_before_target_reads(self):
        for mutation in ("plan", "output"):
            d, panel, plan, commit, outputs, private = self.arrange()
            if mutation == "plan":
                plan["sessions"].pop()
            else:
                outputs.pop(next(reversed(outputs)))
            calls = []
            with self.assertRaises(ValueError):
                scorer.score_study(panel, plan, commit, outputs, lambda desc: calls.append(desc), np)
            self.assertEqual(calls, [])

    def test_zero_true_probability_keeps_infinity_and_undefined_difference(self):
        d, panel, plan, commit, outputs, private = self.arrange()
        session = panel["sessions"][0]
        for arm in ("wheel_plus_context", "neural_wheel_plus_context"):
            self.update(d, commit, outputs, (session["session_token"], arm),
                        lambda doc: doc["predictions"][0].update(probabilities=[0., .5, .5]))
        result = scorer.score_study(panel, plan, commit, outputs, lambda desc: private[desc["path"]], np)
        self.assertEqual(result["primary"]["value"]["status"], "positive_infinity")
        report = result["recovered_four_arm_summary"]
        self.assertEqual(report["equal_mouse_improvements"]["neural_increment_given_wheel_context"]["natural_log_loss"]["status"], "undefined")
        self.assertEqual(report["uncertainty"]["status"], "undefined_nonfinite_mouse_effect")
        d["controls"].encoded(result)  # Strict JSON: no NaN/Infinity literals.

    def test_private_hash_and_identity_checks(self):
        d, panel, plan, commit, outputs, private = self.arrange()
        with self.assertRaises(ValueError):
            scorer.score_study(panel, plan, commit, outputs, lambda desc: private[desc["path"]] + b" ", np)
        key = panel["sessions"][0]["session_token"]
        mapping = d["controls"].parse(private[key], 2097152)
        mapping["mouse"] = "wrong-mouse"
        private[key] = d["controls"].encoded(mapping)
        plan["sessions"][0]["private_mapping"].update(d["controls"].pin(private[key]))
        with self.assertRaises(ValueError):
            scorer.score_study(panel, plan, commit, outputs, lambda desc: private[desc["path"]], np)

    def test_control_views_preserve_rows_without_neural_leaks(self):
        d, panel, *_ = self.data
        for session in panel["sessions"]:
            for arm in d["controls"].CONTROL_ARMS:
                for phase in d["controls"].PHASES:
                    control = session["controls"][arm][phase]
                    original = session["original_manifests"]["neural_wheel_plus_context"][phase]
                    self.assertEqual(control["case_tokens"], original["case_tokens"])
                    self.assertNotIn("unit_count", control)
                    self.assertNotIn("neural.npz", control["files"])
                    self.assertNotIn("units.npz", control["files"])
                    self.assertEqual("labels.npz" in control["files"], phase == "fitval")

    def test_target_order_equal_blank_invalid_and_original_split(self):
        labels, valid = targets.target_classes([1, 0, .5, 0, np.nan, -.1, 1.1],
                                              [0, 0, .5, 1, 0, 0, 0], np)
        self.assertEqual(labels.tolist(), [0, 1, 1, 2, -1, -1, -1])
        self.assertEqual(valid.tolist(), [True] * 4 + [False] * 3)
        self.assertEqual(targets.partitions(214), {"fit": (0, 128), "validation": (128, 170), "query": (170, 214)})
        mask = np.ones(214, dtype=bool)
        mask[:120] = False
        rows = targets.eligible_split_rows(214, mask, np)
        self.assertEqual([len(rows[k]) for k in ("fit", "validation", "query")], [8, 42, 44])
        with self.assertRaises(ValueError):
            targets.target_classes([True], [False], np)


if __name__ == "__main__":
    unittest.main()
