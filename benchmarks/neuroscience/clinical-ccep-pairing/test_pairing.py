"""All values, identities, packets, references and targets are invented."""
import base64
import copy
import contextlib
import hashlib
import itertools
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import pairing as C


def blob(value):
    body = C.canonical(value)
    return base64.b64encode(body).decode(), C.digest(body)


class Fixture:
    def __init__(self, root):
        self.root = root
        people = ["invented-P" + str(i) for i in range(5)]
        sites = [["A", "B", "C"], ["A", "A", "B", "C"], ["A", "A", "B"], ["A"], ["A", "B"]]
        self.blocks, cases, rows, targets = {}, [], [], []
        for i, person in enumerate(people):
            for j, site in enumerate(sites[i]):
                name = person + "-case" + str(j)
                reps = 2 + i
                layout = {"relative_times_seconds": ["0.011", "0.125", "0.500"], "units": "uV",
                          "missing": [[False, True, False] for _ in range(reps)],
                          "artifact": [[False, True, bool(k % 2)] for k in range(reps)]}
                response = [[i * 100 + j * 10 + k, None, -(j + k + 1)] for k in range(reps)]
                rb, rh = blob(response); lb, lh = blob(layout)
                cb, ch = blob({"recording_location": "invented-recipient-context-" + name})
                block = {"schema": "ccep-complete-block-v1", "task_id": C.P.TASK, "case_id": name,
                         "response_b64": rb, "layout_b64": lb, "context_b64": cb}
                self.blocks[name] = block
                cases.append({"case_id": name, "patient": person, "session": "invented-session",
                              "site_block": "block" + str(j), "VTC_contact": "invented-contact",
                              "repetitions": reps, "packet_sha256": "0" * 64,
                              "coverage": "ready", "coverage_reason": ""})
                nuisance = {key: C.digest(("invented-" + key).encode()) for key in C.NUISANCE}
                if i == 4 and j == 1:
                    nuisance["pulse_intensity"] = "9" * 64
                rows.append({"case_id": name, "stimulated_site": "site" + site, "nuisance": nuisance,
                             "response_sha256": rh, "layout_sha256": lh, "context_sha256": ch})
                targets.append({"case_id": name, "class_index": 0})
        self.targets = {"schema": "ccep-targets-v1", "task_id": C.P.TASK, "rows": targets}
        self.policy = {"schema": "ccep-operator-policy-v1", "task_id": C.P.TASK, "contract_sha256": C.P.CONTRACT,
                       "release": "ds004457:1.0.2", "class_order": list(C.P.CLASSES), "patients": people,
                       "folds": [{"held_patient": p, "training_patients": [x for x in people if x != p]} for p in people],
                       "cases": cases, "numeric_policy": {"log_base": "natural", "loss_floor": 1e-12,
                       "sum_tolerance": 1e-12, "tie_break": "first_class_in_frozen_order", "calibration_bins": 10},
                       "provenance": {key: "8" * 64 for key in ("source_census_sha256", "anatomical_mapping_sha256",
                                      "packet_manifest_sha256", "exposure_audit_sha256")}, "targets_sha256": "0" * 64,
                       "scope_assertion": "all_five_patients_all_VTC_contacts_all_site_blocks_all_repetitions"}
        self.control = {"schema": "ccep-pairing-policy-v1", "task_id": C.P.TASK,
                        "primary_policy_sha256": "0" * 64, "algorithm": C.ALGORITHM,
                        "source_protocol_sha256": "7" * 64, "envelope_schema": "ccep-complete-block-v1",
                        "arms": [{"id": "candidate", "role": "candidate", "provenance_sha256": "4" * 64},
                                 {"id": "reference", "role": "reference", "provenance_sha256": "5" * 64}], "rows": rows}

    def write(self, name, obj):
        body = C.canonical(obj) + b"\n"
        path = self.root / (name + ".json"); path.write_bytes(body)
        return path, C.digest(body)

    def freeze(self):
        self.paths = {}
        for case in self.policy["cases"]:
            name = case["case_id"]; path, digest = self.write(name, self.blocks[name])
            self.paths[name] = path; case["packet_sha256"] = digest
        self.tp, self.policy["targets_sha256"] = self.write("targets", self.targets)
        self.pp, self.ph = self.write("policy", self.policy)
        self.control["primary_policy_sha256"] = self.ph
        self.cp, self.ch = self.write("control", self.control)
        self.mapping = C.maps(self.pp, self.ph, self.cp, self.ch)
        self.mp, self.mh = self.write("map", self.mapping)
        return self

    def original(self, name):
        truep = .8 if name == "candidate" else .25
        return {"schema": "ccep-predictions-v1", "task_id": C.P.TASK, "policy_sha256": self.ph,
                "class_order": list(C.P.CLASSES), "condition": "original_full_scope",
                "rows": [{"case_id": c["case_id"], "probabilities": [truep] + [(1 - truep) / 3] * 3}
                         for c in self.policy["cases"]]}

    def artifact(self):
        arms = []
        for arm in ("candidate", "reference"):
            transforms = []
            for transform in self.mapping["transforms"]:
                rows = []
                for pair in transform["donors"]:
                    name = pair["recipient"]
                    truep = (.4 if name.startswith("invented-P0") else .2) if arm == "candidate" else .25
                    rows.append({"case_id": name, "probabilities": [truep] + [(1 - truep) / 3] * 3})
                transforms.append({"id": transform["id"], "rows": rows})
            arms.append({"id": arm, "original": self.original(arm), "transforms": transforms})
        return {"schema": "ccep-paired-predictions-v1", "task_id": C.P.TASK,
                "primary_policy_sha256": self.ph, "control_policy_sha256": self.ch, "map_sha256": self.mh,
                "class_order": list(C.P.CLASSES), "arms": arms}

    def score(self, artifact=None):
        ap, _ = self.write("artifact", self.artifact() if artifact is None else artifact)
        return C.score(self.pp, self.ph, self.cp, self.ch, self.mp, self.mh, ap, self.tp)


class Controls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.f = Fixture(self.root).freeze()

    def tearDown(self): self.tmp.cleanup()

    def test_complete_strata_seed_cap_and_dedup(self):
        m = self.f.mapping
        self.assertEqual(m["full_original_case_count"], 13)
        self.assertEqual(len(m["seeds"]), 20)
        self.assertEqual([s["seed"] for s in m["seeds"]], list(range(20)))
        self.assertTrue(all(s["candidate_attempts"] <= 100 for s in m["seeds"]))
        signatures = [C.canonical(t["donors"]) for t in m["transforms"]]
        self.assertEqual(len(signatures), len(set(signatures)))
        self.assertEqual(m["actual_distinct_transform_count"], len(signatures))
        self.assertEqual(sum(g["blocks"] for g in m["groups"] if g["supported"]), 7)
        self.assertEqual(len(m["unsupported_cases"]), 6)
        rows = {r["case_id"]: r for r in self.f.control["rows"]}
        for t in m["transforms"]:
            recipients = {x["recipient"] for x in t["donors"]}
            self.assertEqual(recipients, {x["donor"] for x in t["donors"]})
            for pair in t["donors"]:
                self.assertNotEqual(rows[pair["recipient"]]["stimulated_site"], rows[pair["donor"]]["stimulated_site"])

    def test_majority_impossibility_against_small_exhaustive_matching(self):
        for counts in [(1, 1), (2, 1), (2, 2), (2, 1, 1), (3, 2, 1), (4, 1, 1), (2, 2, 2)]:
            labels = [str(k) for k, n in enumerate(counts) for _ in range(n)]
            feasible = any(all(labels[i] != labels[j] for i, j in enumerate(perm))
                           for perm in itertools.permutations(range(len(labels))))
            self.assertEqual(feasible, max(counts) * 2 <= len(labels))
            if feasible:
                cases = ["x" + str(i) for i in range(len(labels))]
                rows = {name: {"stimulated_site": label} for name, label in zip(cases, labels)}
                g = {"cases": cases, "id": "0" * 64, "largest_site_multiplicity": max(counts)}
                for seed in range(20):
                    pairs = C._rotation(g, rows, seed)
                    self.assertEqual(set(cases), {x["donor"] for x in pairs})
                    self.assertTrue(all(rows[x["recipient"]]["stimulated_site"] != rows[x["donor"]]["stimulated_site"] for x in pairs))

    def test_all_allowed_shifts_for_unequal_multiplicities(self):
        # Independent exhaustive interval check, not the sampler's chosen offsets.
        for counts in [(3, 2, 1), (3, 3, 2), (4, 3, 3), (2, 2, 1), (1, 1, 1, 1)]:
            for site_order in itertools.permutations(range(len(counts))):
                values = [site for site in site_order for _ in range(counts[site])]
                n, largest = len(values), max(counts)
                for shift in range(largest, n - largest + 1):
                    donors = [(i + shift) % n for i in range(n)]
                    self.assertEqual(len(set(donors)), n)
                    self.assertTrue(all(values[i] != values[j] for i, j in enumerate(donors)))

    def test_mapping_ignores_targets_responses_and_arm_predictions(self):
        original = [t["donors"] for t in self.f.mapping["transforms"]]
        self.f.targets["rows"][0]["class_index"] = 3
        self.f.control["rows"][0]["response_sha256"] = "f" * 64
        self.f.control["arms"][0]["provenance_sha256"] = "e" * 64
        self.f.freeze()
        self.assertEqual(original, [t["donors"] for t in self.f.mapping["transforms"]])
        self.f.tp.unlink()
        self.assertEqual(self.f.mapping, C.maps(self.f.pp, self.f.ph, self.f.cp, self.f.ch))

    def test_every_required_nuisance_field_can_prevent_pairing(self):
        original = C._policy(self.f.pp, self.f.ph, self.f.cp, self.f.ch)
        cases, rows = original[2], original[6]
        first = next(iter(cases))
        for key in C.NUISANCE:
            changed = copy.deepcopy(rows); changed[first]["nuisance"][key] = "f" * 64
            group = next(g for g in C._groups(cases, changed) if first in g["cases"])
            self.assertEqual(group["blocks"], 1)
        for key in ("patient", "session", "VTC_contact", "repetitions"):
            changed = copy.deepcopy(cases)
            changed[first][key] = 999 if key == "repetitions" else "different"
            self.assertEqual(next(g for g in C._groups(changed, rows) if first in g["cases"])["blocks"], 1)

    def test_whole_response_moves_recipient_context_and_layout_stay(self):
        t = self.f.mapping["transforms"][0]; pair = t["donors"][0]
        r, d = pair["recipient"], pair["donor"]
        out = C.packet(self.f.pp, self.f.ph, self.f.cp, self.f.ch, self.f.mp, self.f.mh,
                       t["id"], r, self.f.paths[r], self.f.paths[d])
        self.assertEqual(out["response_b64"], self.f.blocks[d]["response_b64"])
        self.assertEqual(out["layout_b64"], self.f.blocks[r]["layout_b64"])
        self.assertEqual(out["context_b64"], self.f.blocks[r]["context_b64"])
        self.assertEqual(set(out), {"schema", "task_id", "case_id", "transform_id", "response_b64", "layout_b64", "context_b64"})
        self.assertNotIn("donor", out)
        with self.assertRaises(C.P.Invalid):
            C.packet(self.f.pp, self.f.ph, self.f.cp, self.f.ch, self.f.mp, self.f.mh,
                     t["id"], r, self.f.paths[r], self.f.paths[r])

    def test_envelope_shape_masks_and_time_domain(self):
        name = self.f.policy["cases"][0]["case_id"]
        original = copy.deepcopy(self.f.blocks[name])
        for which, mutate in [("response", lambda a: a.pop()),
                              ("response", lambda a: a[0].__setitem__(1, 0)),
                              ("layout", lambda a: a["artifact"][0].__setitem__(0, 1)),
                              ("layout", lambda a: a["relative_times_seconds"].__setitem__(0, "0.010")),
                              ("layout", lambda a: a["relative_times_seconds"].__setitem__(0, "0.0_11")),
                              ("layout", lambda a: a["relative_times_seconds"].__setitem__(1, "0.011"))]:
            self.f.blocks[name] = copy.deepcopy(original)
            value = json.loads(base64.b64decode(original[which + "_b64"]))
            mutate(value); b64, h = blob(value)
            self.f.blocks[name][which + "_b64"] = b64
            next(r for r in self.f.control["rows"] if r["case_id"] == name)[which + "_sha256"] = h
            self.f.freeze()
            case = next(r for r in self.f.policy["cases"] if r["case_id"] == name)
            row = next(r for r in self.f.control["rows"] if r["case_id"] == name)
            with self.assertRaises(C.P.Invalid): C._envelope(self.f.paths[name], case, row)

    def test_paired_hand_arithmetic_and_matched_reference(self):
        report = self.f.score()
        expected = (math.log(2) + math.log(4)) / 2
        pooled = (3 * math.log(2) + 4 * math.log(4)) / 7
        self.assertGreater(abs(expected - pooled), .04)
        self.assertAlmostEqual(report["equal_transform_arm_effects"]["candidate"], expected)
        self.assertEqual(report["equal_transform_arm_effects"]["reference"], 0)
        for t in report["transforms"]:
            self.assertEqual(t["supported_patients"], ["invented-P0", "invented-P1"])
            self.assertEqual(len(t["patients_without_support"]), 3)
            self.assertEqual(t["supported_blocks"], 7)
            self.assertAlmostEqual(t["matched_comparisons"][0]["candidate_minus_reference_pairing_effect"], expected)
            self.assertEqual([r["supported_blocks"] for r in t["arm_effects"]["candidate"]["patient_rows"]], [3, 4, 0, 0, 0])
        self.assertAlmostEqual(report["original_full_scores"]["candidate"]["primary_patient_macro_log_loss"], -math.log(.8))
        self.assertEqual([x["blocks"] for x in report["original_full_scores"]["candidate"]["patient_folds"]], [3, 4, 3, 1, 2])

    def test_original_primary_matches_unchanged_scorer(self):
        report = self.f.score()
        original_path, _ = self.f.write("original", self.f.original("candidate"))
        primary = C.P.score_files(self.f.pp, self.f.ph, original_path, self.f.tp)
        self.assertEqual(primary["primary_patient_macro_log_loss"], report["original_full_scores"]["candidate"]["primary_patient_macro_log_loss"])
        self.assertEqual(primary["patient_folds"], report["original_full_scores"]["candidate"]["patient_folds"])

    def test_null_unavailable_preserves_natural_score_and_all_cases(self):
        for row in self.f.control["rows"]: row["stimulated_site"] = "same"
        self.f.freeze(); report = self.f.score()
        self.assertEqual(len(self.f.mapping["transforms"]), 0)
        self.assertEqual(report["status"], "null_unavailable")
        self.assertEqual(len(report["unsupported_cases"]), 13)
        self.assertIsNone(report["equal_transform_arm_effects"])
        self.assertAlmostEqual(report["original_full_scores"]["candidate"]["primary_patient_macro_log_loss"], -math.log(.8))

    def test_all_arms_admitted_before_targets(self):
        for mutate in [lambda a: a["arms"][-1]["transforms"][-1]["rows"].pop(),
                       lambda a: a["arms"][-1]["original"]["rows"].pop(),
                       lambda a: a["arms"].pop(),
                       lambda a: a["arms"][-1]["transforms"][-1]["rows"][-1].update(probabilities=[.5] * 4)]:
            a = self.f.artifact(); mutate(a); opened = []
            read = C.P.read_document
            def spy(path, expected=None):
                opened.append(Path(path).name)
                return read(path, expected)
            with patch.object(C.P, "read_document", side_effect=spy):
                with self.assertRaises(C.P.Invalid): self.f.score(a)
            self.assertNotIn("targets.json", opened)

    def test_no_identity_forged_map_or_shrunken_support(self):
        forged = copy.deepcopy(self.f.mapping)
        forged["transforms"][0]["donors"][0]["donor"] = forged["transforms"][0]["donors"][0]["recipient"]
        mp, mh = self.f.write("forged", forged)
        with self.assertRaises(C.P.Invalid):
            C._frozen_map(mp, mh, self.f.ph, self.f.ch,
                          {x["case_id"]: x for x in self.f.policy["cases"]},
                          {x["case_id"]: x for x in self.f.control["rows"]})
        a = self.f.artifact(); a["arms"][0]["transforms"][0]["rows"].append({"case_id": "invented-P3-case0", "probabilities": [.25] * 4})
        with self.assertRaises(C.P.Invalid): self.f.score(a)

    def test_original_unresolved_keeps_full_scope_and_no_target_open(self):
        self.f.policy["cases"][-1].update(coverage="unsupported_anatomy", coverage_reason="invented unresolved join")
        self.f.freeze(); self.f.tp.unlink(); report = self.f.score()
        self.assertEqual(report["status"], "construction_unestablished")
        self.assertFalse(report["targets_opened"])
        self.assertIsNone(report["original_full_scores"])

    def test_maps_cli_and_score_cli(self):
        common = [sys.executable, "-I", "-B", str(Path(C.__file__).resolve())]
        args = ["--policy", str(self.f.pp), "--policy-sha256", self.f.ph,
                "--control", str(self.f.cp), "--control-sha256", self.f.ch]
        result = subprocess.run(common + ["maps"] + args, capture_output=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), self.f.mapping)
        ap, _ = self.f.write("artifact", self.f.artifact())
        result = subprocess.run(common + ["score"] + args + ["--map", str(self.f.mp), "--map-sha256", self.f.mh,
                                "--artifact", str(ap), "--targets", str(self.f.tp)], capture_output=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), self.f.score())

    def test_packet_cli_preserves_exact_payload_components(self):
        t = self.f.mapping["transforms"][0]; pair = t["donors"][0]
        args = [sys.executable, "-I", "-B", str(Path(C.__file__).resolve()), "packet",
                "--policy", str(self.f.pp), "--policy-sha256", self.f.ph,
                "--control", str(self.f.cp), "--control-sha256", self.f.ch,
                "--map", str(self.f.mp), "--map-sha256", self.f.mh, "--transform-id", t["id"],
                "--recipient-id", pair["recipient"], "--recipient-packet", str(self.f.paths[pair["recipient"]]),
                "--donor-packet", str(self.f.paths[pair["donor"]])]
        result = subprocess.run(args, capture_output=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual(out["response_b64"], self.f.blocks[pair["donor"]]["response_b64"])
        self.assertEqual(out["context_b64"], self.f.blocks[pair["recipient"]]["context_b64"])

    def test_equal_distinct_transform_mean_not_duplicate_seed_weight(self):
        artifact = self.f.artifact()
        expected = []
        for i, t in enumerate(artifact["arms"][0]["transforms"]):
            ptrue = .8 / (1 + .1 * (i + 1))
            expected.append(math.log(1 + .1 * (i + 1)))
            for row in t["rows"]: row["probabilities"] = [ptrue] + [(1 - ptrue) / 3] * 3
        report = self.f.score(artifact)
        self.assertGreater(len(expected), 1)
        self.assertAlmostEqual(report["equal_transform_arm_effects"]["candidate"], math.fsum(expected) / len(expected))
        self.assertEqual(len(report["transforms"]), len(expected))

    def test_control_and_map_hashes_are_required_before_later_reads(self):
        for operation in [lambda: C.maps(self.f.pp, self.f.ph, self.f.cp, None),
                          lambda: C.score(self.f.pp, self.f.ph, self.f.cp, self.f.ch, self.f.mp, None, "unused", "unused")]:
            with patch.object(C.P, "read_document", side_effect=AssertionError("unexpected read")):
                with self.assertRaises(C.P.Invalid): operation()

    def test_complete_map_output_above_reader_limit_is_refused(self):
        # Make additional complete strata feasible; original tiny fixture's map
        # was 14,135 B, below its 14,275 B input maximum (preserved failed witness).
        for row in self.f.control["rows"]:
            row["stimulated_site"] = "unique-" + row["case_id"]
        self.f.freeze()
        cap = max(self.f.pp.stat().st_size, self.f.cp.stat().st_size)
        self.assertGreater(len(C.canonical(self.f.mapping)) + 1, cap)
        with patch.object(C.P, "MAX_BYTES", cap):
            with self.assertRaisesRegex(C.P.Invalid, "output size"):
                C.maps(self.f.pp, self.f.ph, self.f.cp, self.f.ch)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = C.main(["maps", "--policy", str(self.f.pp), "--policy-sha256", self.f.ph,
                               "--control", str(self.f.cp), "--control-sha256", self.f.ch])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output.getvalue())["status"], "invalid_or_incomplete")
            self.assertNotIn("transforms", json.loads(output.getvalue()))

    def test_exact_output_boundary_includes_final_lf(self):
        result = {"invented": "\u00e9"}
        size = len(C.canonical(result)) + 1
        with patch.object(C.P, "MAX_BYTES", size):
            self.assertIs(C._admit_output(result), result)
        with patch.object(C.P, "MAX_BYTES", size - 1):
            with self.assertRaises(C.P.Invalid): C._admit_output(result)

    def test_all_output_routes_use_complete_output_admission(self):
        t = self.f.mapping["transforms"][0]; pair = t["donors"][0]
        operations = [lambda: C.maps(self.f.pp, self.f.ph, self.f.cp, self.f.ch),
                      lambda: C.packet(self.f.pp, self.f.ph, self.f.cp, self.f.ch, self.f.mp, self.f.mh,
                                       t["id"], pair["recipient"], self.f.paths[pair["recipient"]], self.f.paths[pair["donor"]]),
                      lambda: self.f.score()]
        for operation in operations:
            with patch.object(C, "_admit_output", side_effect=C.P.Invalid("forced complete output refusal")):
                with self.assertRaisesRegex(C.P.Invalid, "forced complete output refusal"): operation()
        for row in self.f.control["rows"]: row["stimulated_site"] = "same"
        self.f.freeze()
        with patch.object(C, "_admit_output", side_effect=C.P.Invalid("forced complete output refusal")):
            with self.assertRaisesRegex(C.P.Invalid, "forced complete output refusal"): self.f.score()
        self.f.policy["cases"][0].update(coverage="invalid_signal", coverage_reason="invented")
        self.f.freeze()
        with patch.object(C, "_admit_output", side_effect=C.P.Invalid("forced complete output refusal")):
            with self.assertRaisesRegex(C.P.Invalid, "forced complete output refusal"): self.f.score()


if __name__ == "__main__": unittest.main(verbosity=2)
