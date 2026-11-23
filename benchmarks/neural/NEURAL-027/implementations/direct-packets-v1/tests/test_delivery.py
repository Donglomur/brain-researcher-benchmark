"""Generated transport/scorer controls; no authentic data or participant trial."""
import copy
import importlib.util
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

MODULE = Path(__file__).resolve().parents[1] / "delivery.py"
spec = importlib.util.spec_from_file_location("delivery", MODULE)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
fixture_path = MODULE.parents[1] / "initial-evaluator-v1" / "tests" / "test_evaluator.py"
spec = importlib.util.spec_from_file_location("generated_fixture", fixture_path)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def packet():
    plan, sessions = fixture.fixture()
    train, _, _ = d.base.prepare(sessions, plan)
    ids = [r["item_id"] for r in train]
    public, private = d.build(sessions, plan, ids, key=b"generated-test-key" * 2)
    return plan, sessions, public, private


def responses(private):
    out = {"neural": [], "movement_position": []}
    for row in private["expected"]:
        # Unequal mouse behavior makes the mouse aggregation observable.
        p = ([.9, .1] if row["label"] == 0 else [.1, .9]) if row["mname"] == "c" else [.8, .2]
        out["neural"].append({"item_id": row["item_id"], "probabilities": p})
        out["movement_position"].append({"item_id": row["item_id"], "probabilities": [.5, .5]})
    return out


class DeliveryTests(unittest.TestCase):
    def test_complete_pair_and_independent_metric_oracle(self):
        _, _, public, private = packet()
        response = responses(private)
        response["neural"].reverse()
        result = d.collect(public, private, response, bootstrap_draws=100)
        metric = result["neural"]["by_phase"]["reward_free_after"]
        self.assertAlmostEqual(metric["mouse_macro_log_loss"], (-math.log(.9) - (math.log(.8) + math.log(.2))/2)/2)
        self.assertEqual(metric["mouse_macro_balanced_accuracy"], .75)
        self.assertAlmostEqual(result["movement_position"]["by_phase"]["reward_free_after"]["mouse_macro_log_loss"], math.log(2))
        self.assertEqual(result["paired_uncertainty"]["reward_free_after"]["paired_mice"], ["c", "d"])
        self.assertFalse(result["access_enforcement_verified"])
        self.assertEqual(result["scientific_qualification"], "not_established")

    def test_public_allowlist_and_exact_arm_observations(self):
        plan, sessions, public, private = packet()
        train, expected, _ = d.base.prepare(sessions, plan)
        source = {r["item_id"]: r for r in expected}
        binding = {r["item_id"]: r for r in private["expected"]}
        for arm, feature, width in (("neural", "neural", 4), ("movement_position", "context", 2)):
            self.assertEqual(public[arm]["feature_order"], d.FEATURES[arm])
            for row in public[arm]["items"]:
                self.assertEqual(set(row), {"item_id", "values"})
                self.assertEqual(len(row["values"]), width)
                original = source[binding[row["item_id"]]["source_item_id"]]
                self.assertEqual(row["values"], original[feature])
                self.assertNotEqual(row["item_id"], original["item_id"])
            for row, original in zip(public[arm]["demonstrations"], train):
                self.assertEqual(set(row), {"values", "label"})
                self.assertEqual(row["values"], original[feature])
                self.assertEqual(row["label"], original["label"])
        self.assertEqual([r["item_id"] for r in public["neural"]["items"]], [r["item_id"] for r in public["movement_position"]["items"]])
        text = json.dumps(public)
        for forbidden in ("mname", "datexp", "session_id", "WallID", "source_item_id", "private_identity_key_hex", "extraction_audit"):
            self.assertNotIn('"' + forbidden + '"', text)
        for meta in plan["sessions"]:
            self.assertNotIn(meta["session_id"], text)

    def test_private_labels_cannot_change_public_packets(self):
        plan, sessions, public, private = packet()
        changed = copy.deepcopy(sessions)
        for session in changed:
            if session["mname"] in plan["evaluation_mice"]:
                session["behavior"]["stim_id"] = [2, 0]
        altered, altered_private = d.build(changed, plan, private["demonstration_source_ids"], key=b"generated-test-key" * 2)
        self.assertEqual(altered, public)
        self.assertNotEqual(altered_private["expected"], private["expected"])

    def test_demonstrations_are_training_only_balanced_and_complete(self):
        plan, sessions, _, private = packet()
        ids = private["demonstration_source_ids"]
        for selected, message in ((ids + [ids[0]], "duplicate"),
                                  ([private["expected"][0]["source_item_id"]], "training-only"),
                                  (ids[:-1], "balance")):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                d.build(sessions, plan, selected)
        train, _, _ = d.base.prepare(sessions, plan)
        # Balanced across mouse/class, but only bin zero of every training trial.
        partial = [r["item_id"] for r in train if r["position_bin"] == 0]
        with self.assertRaisesRegex(ValueError, "complete trial-position"):
            d.build(sessions, plan, partial)

    def test_zero_demonstration_is_separate_frozen_condition(self):
        plan, sessions, _, _ = packet()
        public, private = d.build(sessions, plan, [])
        for arm in d.FEATURES:
            self.assertEqual(public[arm]["demonstration_condition"], "zero_demonstrations")
            self.assertEqual(public[arm]["demonstrations"], [])
        self.assertEqual(d.collect(public, private, responses(private), bootstrap_draws=100)["demonstration_condition"], "zero_demonstrations")

    def test_per_item_prompt_contains_only_one_query(self):
        _, _, public, _ = packet()
        item = public["neural"]["items"][4]
        prompt = json.loads(d.render_prompt(public["neural"], item["item_id"]))
        self.assertNotIn("items", prompt)
        self.assertEqual(prompt["query"], item)
        self.assertEqual(prompt["demonstrations"], public["neural"]["demonstrations"])
        with self.assertRaisesRegex(ValueError, "unknown"):
            d.render_prompt(public["neural"], "unregistered")

    def test_prompt_rejects_private_or_unregistered_fields(self):
        _, _, public, _ = packet()
        item_id = public["neural"]["items"][0]["item_id"]
        for extra in ("label", "phase", "mname", "session_id", "ft_WallID"):
            altered = copy.deepcopy(public["neural"])
            altered["items"][0][extra] = "private-value"
            with self.assertRaisesRegex(ValueError, "fields"):
                d.render_prompt(altered, item_id)
        altered = copy.deepcopy(public["neural"])
        altered["private_key"] = "not allowed"
        with self.assertRaisesRegex(ValueError, "fields"):
            d.render_prompt(altered, item_id)

    def test_packet_mutation_including_demo_target_rejected(self):
        _, _, public, private = packet()
        for section, field, value in (("items", "values", [100]*4), ("demonstrations", "label", 2)):
            bad = copy.deepcopy(public)
            bad["neural"][section][0][field] = value
            with self.assertRaisesRegex(ValueError, "changed after freeze"):
                d.collect(bad, private, responses(private), bootstrap_draws=100)

    def test_complete_both_arm_coverage_required(self):
        _, _, public, private = packet()
        good = responses(private)
        bad_values = [good["neural"][:-1], good["neural"] + [good["neural"][0]],
                      [dict(r, item_id="unknown") if i == 0 else r for i, r in enumerate(good["neural"])]]
        for rows in bad_values:
            with self.assertRaises(ValueError):
                d.collect(public, private, dict(good, neural=rows), bootstrap_draws=100)
        with self.assertRaisesRegex(ValueError, "both paired"):
            d.collect(public, private, {"neural": good["neural"]}, bootstrap_draws=100)

    def test_strict_probability_types_shapes_and_simplex(self):
        _, _, public, private = packet()
        for invalid in ([True, False], ["0.5", "0.5"], [float("nan"), .5], [float("inf"), .5], [-.1, 1.1], [.4, .4], [.5, .5, 0]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                bad = responses(private)
                bad["neural"][0]["probabilities"] = invalid
                d.collect(public, private, bad, bootstrap_draws=100)
        bad = responses(private)
        bad["neural"][0]["reasoning"] = "not accepted"
        with self.assertRaisesRegex(ValueError, "fields"):
            d.collect(public, private, bad, bootstrap_draws=100)

    def test_json_duplicate_keys_and_nonfinite_constants_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "response.json"
            for text in ('{"probabilities":[0.5,0.5],"probabilities":[1,0]}', '{"x":NaN}', '{"x":Infinity}'):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    d.read_json(path)

    def test_key_controls_identity_without_changing_observation(self):
        plan, sessions, _, private = packet()
        a, _ = d.build(sessions, plan, [], key=b"a"*32)
        b, _ = d.build(sessions, plan, [], key=b"b"*32)
        self.assertFalse({r["item_id"] for r in a["neural"]["items"]} & {r["item_id"] for r in b["neural"]["items"]})
        self.assertEqual(sorted(r["values"] for r in a["neural"]["items"]), sorted(r["values"] for r in b["neural"]["items"]))
        with self.assertRaisesRegex(ValueError, "32 bytes"):
            d.build(sessions, plan, [], key=b"weak")

    def test_cli_safe_export_to_prompt_to_paired_scoring(self):
        plan, sessions, _, private = packet()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/"plan.json").write_text(json.dumps(plan))
            (root/"demos.json").write_text(json.dumps(private["demonstration_source_ids"]))
            for s in sessions:
                np.savez(root/(s["session_id"]+".npz"), spks=np.concatenate(s["spks"]), iarea=s["iarea"], **s["behavior"])
            command = [sys.executable, str(MODULE), "build", "--plan", str(root/"plan.json"), "--session-dir", tmp,
                       "--demonstration-ids", str(root/"demos.json"), "--public-dir", str(root/"public"), "--private-dir", str(root/"private")]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual({p.name for p in (root/"public").iterdir()}, {"neural.json", "movement_position.json"})
            binding = d.read_json(root/"private/binding.json")
            self.assertEqual(len(binding["input_pins"]), 4)
            generated = responses(binding)
            for arm, rows in generated.items():
                (root/(arm+"-responses.json")).write_text(json.dumps(rows))
            result = subprocess.run([sys.executable, str(MODULE), "prompt", "--packet", str(root/"public/neural.json"), "--item-id", binding["expected"][0]["item_id"]], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("query", json.loads(result.stdout))
            result = subprocess.run([sys.executable, str(MODULE), "score", "--public-dir", str(root/"public"), "--private-binding", str(root/"private/binding.json"),
                                     "--neural-responses", str(root/"neural-responses.json"), "--movement-position-responses", str(root/"movement_position-responses.json"),
                                     "--output", str(root/"private/report.json")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(d.read_json(root/"private/report.json")["neural"]["by_phase"]["reward_free_after"]["n_mice"], 2)
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must be new", result.stderr)

    def test_npz_replacement_cannot_change_captured_identity(self):
        plan, sessions = fixture.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for session in sessions:
                np.savez(root/(session["session_id"]+".npz"),
                         spks=np.concatenate(session["spks"]),
                         iarea=session["iarea"], **session["behavior"])
            first = sessions[0]
            target = root/(first["session_id"]+".npz")
            captured = target.read_bytes()
            replacement = io.BytesIO()
            np.savez(replacement, spks=np.concatenate(first["spks"]) + 77,
                     iarea=first["iarea"], **first["behavior"])
            original_load = np.load
            replaced = False

            def load_then_replace(*args, **kwargs):
                nonlocal replaced
                archive = original_load(*args, **kwargs)
                if not replaced:
                    alternate = root/"replacement.npz"
                    alternate.write_bytes(replacement.getvalue())
                    alternate.replace(target)
                    replaced = True
                return archive

            with mock.patch.object(d.np, "load", side_effect=load_then_replace):
                loaded, pins = d.load_sessions(plan, root)
            self.assertTrue(replaced)
            np.testing.assert_array_equal(loaded[0]["spks"], np.concatenate(first["spks"]))
            self.assertNotEqual(target.read_bytes(), captured)
            self.assertEqual(pins[0]["sha256"], hashlib.sha256(captured).hexdigest())
            self.assertEqual(pins[0]["bytes"], len(captured))

    def test_plan_replacement_cannot_change_captured_identity(self):
        plan, sessions = fixture.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path = root/"plan.json"
            captured = json.dumps(plan).encode()
            plan_path.write_bytes(captured)
            (root/"demos.json").write_text("[]")
            for session in sessions:
                np.savez(root/(session["session_id"]+".npz"),
                         spks=np.concatenate(session["spks"]),
                         iarea=session["iarea"], **session["behavior"])
            original_loader = d.load_sessions

            def load_then_replace(*args, **kwargs):
                result = original_loader(*args, **kwargs)
                changed = copy.deepcopy(plan)
                changed["pre_reward_training_attestation"] = False
                plan_path.write_text(json.dumps(changed))
                return result

            command = [str(MODULE), "build", "--plan", str(plan_path),
                       "--session-dir", tmp, "--demonstration-ids", str(root/"demos.json"),
                       "--public-dir", str(root/"public"), "--private-dir", str(root/"private")]
            with mock.patch.object(sys, "argv", command), \
                 mock.patch.object(d, "load_sessions", side_effect=load_then_replace):
                d.main()
            binding = d.read_json(root/"private/binding.json")
            self.assertFalse(d.read_json(plan_path)["pre_reward_training_attestation"])
            self.assertEqual(binding["plan_sha256"], d.digest(plan))
            self.assertEqual(binding["plan_file_sha256"], hashlib.sha256(captured).hexdigest())

    def test_nested_output_directories_rejected_before_reading_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = subprocess.run([sys.executable, str(MODULE), "build", "--plan", "absent", "--session-dir", "absent", "--demonstration-ids", "absent",
                                     "--public-dir", str(root/"public"), "--private-dir", str(root/"public/private")], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must be disjoint", result.stderr)
            self.assertFalse((root/"public").exists())

    def test_score_refuses_public_report_path_before_reading_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = subprocess.run([sys.executable, str(MODULE), "score", "--public-dir", str(root/"public"), "--private-binding", "absent",
                                     "--neural-responses", "absent", "--movement-position-responses", "absent", "--output", str(root/"public/report.json")], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("outside public directory", result.stderr)
            self.assertFalse((root/"public").exists())


if __name__ == "__main__":
    unittest.main()
