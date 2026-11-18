"""Generated complete260-slot controls; no credentialed custody or real data."""
import ast
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import types
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
BASE = "8e9eeddf8327094d631a2f015d9334b9078e98f5"
PROGRAMME = "benchmarks/neural/NEURAL-004/implementations/programme-source/"
CENTRAL = PROGRAMME + "implementation-v1/central-integration/successor-v3/"
PARENT = CENTRAL + "effective-parent/"
ORIGINAL = PROGRAMME + "implementation-v1/successor-v3/"
BASE_REPO = os.environ.get("NEURAL004_IDENTITY_BASE_REPO")
EVIDENCE = Path(os.environ["NEURAL004_IDENTITY_EVIDENCE"]) if os.environ.get("NEURAL004_IDENTITY_EVIDENCE") else None
CACHE = {}
NOTES = []


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def read(relative):
    if relative not in CACHE:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or not relative.startswith(PROGRAMME):
            raise ValueError("declared programme source only")
        selected = REPO / relative
        if selected.is_file():
            with selected.open("rb") as handle:
                body = handle.read(1048577)
        elif BASE_REPO:
            # Private construction only: immutable named base blobs, never HEAD.
            result = subprocess.run(["git", "-C", BASE_REPO, "cat-file", "-p", BASE + ":" + relative],
                                    env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"),
                                    capture_output=True, check=True)
            body = result.stdout
        else:
            raise ValueError("selected source missing: " + relative)
        if len(body) > 1048576 or sum(map(len, CACHE.values())) + len(body) > 2097152:
            raise ValueError("bounded named source capture required")
        CACHE[relative] = body
    return CACHE[relative]


def document(relative):
    return json.loads(read(relative))


def check_pin(relative, expected):
    if pin(read(relative)) != {k: expected[k] for k in ("bytes", "sha256")}:
        raise ValueError("source descriptor mismatch: " + relative)


def module(name, body, filename):
    obj = types.ModuleType(name)
    obj.__file__ = str(filename)
    sys.modules[name] = obj
    exec(compile(body, str(filename), "exec"), obj.__dict__)
    return obj


def verify_source_closure():
    bindings = document(CENTRAL + "BINDINGS.json")
    effective = document(CENTRAL + "EFFECTIVE_PARENT_MANIFEST.json")
    own = document(CENTRAL + "SOURCE_MANIFEST.json")
    freeze = document(CENTRAL + "QUALIFICATION_SOURCE_FREEZE.json")
    proposal = document(CENTRAL + "manifest.proposed.json")
    assert len(effective["files"]) == 46
    assert bindings["parent_members"] == effective["files"]
    assert effective["numerical_and_grading_source_unchanged"] is False
    assert "grading.py" in effective["modified"]
    check_pin(CENTRAL + "EFFECTIVE_PARENT_MANIFEST.json", bindings["parent_manifest"])
    assert set(own["files"]) == set(bindings["own_members"])
    for name, expected in own["files"].items():
        check_pin(CENTRAL + name, expected)
        assert freeze["files"][bindings["central_root"] + "/" + name] == expected
    for expected in effective["files"]:
        check_pin(PARENT + expected["path"], expected)
        assert freeze["files"][bindings["parent_root"] + "/" + expected["path"]] == {
            k: expected[k] for k in ("bytes", "sha256")}
    assert freeze["files"][bindings["parent_manifest"]["path"]] == pin(read(CENTRAL + "EFFECTIVE_PARENT_MANIFEST.json"))
    assert freeze["files"][bindings["central_root"] + "/SOURCE_MANIFEST.json"] == pin(read(CENTRAL + "SOURCE_MANIFEST.json"))
    for path, expected in bindings["external_sources"].items():
        assert freeze["files"][path] == expected  # Original declared sources remain historical.
    check_pin(CENTRAL + "EXTERNAL_SOURCES.json", bindings["external_declarations"])
    assignments = {target.id: ast.literal_eval(node.value)
                   for node in ast.parse(read(CENTRAL + "entry.py")).body
                   if isinstance(node, ast.Assign)
                   for target in node.targets
                   if isinstance(target, ast.Name) and target.id == "BINDINGS_PIN"}
    assert assignments["BINDINGS_PIN"] == pin(read(CENTRAL + "BINDINGS.json"))
    execution = proposal["program_execution"]
    assert execution["entrypoint"]["sha256"] == pin(read(CENTRAL + "entry.py"))["sha256"]
    check_pin(CENTRAL + "SOURCE_MANIFEST.json", execution["preferred_source_interface"]["source"])
    check_pin(CENTRAL + "QUALIFICATION_SOURCE_FREEZE.json", execution["source_freeze"])
    assert execution["execution_selected"] is False and execution["runtime_qualified"] is False
    assert execution["scientific_qualified"] is False and freeze["qualified"] is False
    assert own["actual_operation_selected"] is False
    return effective


class UncredentialedFixtureAuthority:
    """Structural authority double, explicitly not authentication evidence."""
    def __init__(self, common):
        self.common = common

    def envelope(self, role, kind, subject, facts):
        return {"generated_only": True, "credentialed": False,
                "role": role, "kind": kind, "subject": subject, "facts": facts}

    def verify(self, envelope, role, kind, subject):
        if envelope["role"] != role or envelope["kind"] != kind or envelope["subject"] != subject:
            raise ValueError("fixture verifier subject mismatch")
        return {"facts": envelope["facts"], "envelope_pin": self.common.pin(envelope)}


def slot_maps(common, views):
    seed = b"generated-N004-identity-only-seed!"
    actors = {(m, v, p): views.opaque(seed, "context", "prediction", [m, v, p])
              for m in common.MODES for v in common.VIEWS for p in common.PEOPLE}
    references = {(f, p): views.opaque(seed, "context", "reference", [f, p])
                  for f in ("B", "N") for p in common.PEOPLE}
    return seed, actors, references


def fixture(package, *, legacy=False, statuses=None):
    grading = package.module("grading")
    common = package.module("common")
    views = package.module("views")
    budget = package.module("context_budget")
    seed, actor_slots, reference_slots = slot_maps(common, views)
    ledger = types.SimpleNamespace(origin=0, scientific=900, closeout=1000, tick=lambda: 800)
    authority = UncredentialedFixtureAuthority(common)
    barrier = grading.ReleaseBarrier(
        list(actor_slots.values()) if legacy else actor_slots,
        list(reference_slots.values()) if legacy else reference_slots, authority, ledger)
    answers = {p: [{"id": p + "/" + str(t), "value": .25 + int(p) * .005 + t * .01}
                   for t in range(1 + int(p) % 3)] for p in common.PEOPLE}
    actors = {policy: {} for policy in common.PREDICTION_POLICIES}
    references = {family: {} for family in ("B", "N")}
    maps = {}
    statuses = statuses or {}
    slots = [("actor", m + "/" + v, p, context) for (m, v, p), context in actor_slots.items()]
    slots += [("reference", f, p, context) for (f, p), context in reference_slots.items()]
    for role, policy, person, context in slots:
        status = statuses.get((role, policy, person), "sealed")
        offset = (.1 if policy == "B" else .05) if role == "reference" else .01 * (common.PREDICTION_POLICIES.index(policy) + 1)
        mapping = [{"id": views.opaque(seed, context if role == "actor" else "reference-private", "trial", [person, t]),
                    "source_id": row["id"]} for t, row in enumerate(answers[person])]
        forecasts = [{"id": row["id"], "prediction": answer["value"] + offset + int(person) * .001}
                     for row, answer in zip(mapping, answers[person])]
        seal = {"forecast_pin": common.pin(forecasts, 8 * 1048576), "generated_only": True}
        operation = common.pin({"generated_operation": context})["sha256"]
        operations = [] if status == "blocked" else [operation]
        qualifications = {key: {"qualified_custody": True, "uncredentialed_fixture_only": True} for key in operations}
        disposition = {"context": context, "status": status,
                       "seal_pin": common.pin(seal, 8 * 1048576) if status == "sealed" else None,
                       "history_pin": common.pin({"generated_history": context}),
                       "operation_bindings": operations}
        limits = {name: 1000 for name in budget.PHYSICAL_CAPS.values()}
        barrier.register(context, disposition, limits, qualifications)
        facts = {"all_context_processes_closed": True, "all_provider_requests_closed": True,
                 "no_feedback_released": True, "isolation_receipt": common.pin({"fixture": "not-authentication"}),
                 "source_view_receipt": common.pin({"fixture": "not-authentic-source"}),
                 "operation_bindings": operations,
                 "operation_qualifications_pin": common.pin(qualifications, 8 * 1048576),
                 "physical_resources": {name: 0 for name in budget.PHYSICAL_CAPS},
                 "origin_ns": 10, "finished_ns": 100, "unknown": []}
        barrier.close(context, disposition, authority.envelope("observer", "operation_closure", common.pin(disposition), facts))
        record = {"context": context, "status": status,
                  "forecasts": forecasts if status == "sealed" else None,
                  "seal": seal if status == "sealed" else None,
                  "answer_map": mapping if status == "sealed" else []}
        (actors if role == "actor" else references)[policy][person] = record
        if status == "sealed":
            maps[context] = mapping
    bundle = {"answers": answers, "context_answer_maps": maps,
              "source_admission_pin": common.pin({"uncredentialed_generated_fixture": True})}
    subject = {"contexts_pin": common.pin(barrier.closed, 8 * 1048576),
               "target_bundle_pin": common.pin(bundle, 32 * 1048576)}
    release = authority.envelope("operator", "target_release", subject,
        {"prediction_contexts_closed": True, "no_live_actor_feedback_route": True,
         "protected_scorer_identity": common.pin({"fixture_only": True}), "release_ns": 400})
    barrier.open(bundle, release)
    return grading, barrier, actors, references, bundle, actor_slots, reference_slots


def grade(value):
    grading, barrier, actors, references, bundle, *_ = value
    return grading.grade_prediction_panels(barrier, actors, references, bundle)


class IdentityControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if EVIDENCE is not None and (not EVIDENCE.is_dir() or any(EVIDENCE.iterdir())):
            raise ValueError("existing empty selected evidence directory required")
        cls.effective = verify_source_closure()
        cls.previous_central_io = sys.modules.get("central_io")
        module("central_io", read(CENTRAL + "central_io.py"), REPO / CENTRAL / "central_io.py")
        cls.loader = module("_n004_identity_source_loader", read(CENTRAL + "source_loader.py"), REPO / CENTRAL / "source_loader.py")
        bodies = {row["path"]: read(PARENT + row["path"]) for row in cls.effective["files"]}
        cls.current = cls.loader.Captured("_n004_identity_current", REPO / PARENT, bodies).install()
        original = read(ORIGINAL + "grading.py")
        if pin(original) != {"bytes": 15656, "sha256": "d37e077a4847293f2fa6a2982f4ddc64e740bdcabd9873bed70b403905ce80bf"}:
            raise ValueError("retained pre-guard grading source changed")
        cls.legacy = cls.loader.Captured("_n004_identity_legacy", REPO / PARENT,
                                         dict(bodies, **{"grading.py": original})).install()

    @classmethod
    def tearDownClass(cls):
        cls.legacy.close()
        cls.current.close()
        sys.modules.pop("_n004_identity_source_loader", None)
        if cls.previous_central_io is None:
            sys.modules.pop("central_io", None)
        else:
            sys.modules["central_io"] = cls.previous_central_io
        raw = (json.dumps({"schema": "neural004_identity_generated_controls_v1",
                           "generated_only": True, "credentialed_custody": False,
                           "retained_private_data_used": False, "source_bytes_captured": sum(map(len, CACHE.values())),
                           "notes": NOTES}, indent=1, sort_keys=True) + "\n").encode()
        if len(raw) > 16384:
            raise ValueError("bounded generated control evidence")
        if EVIDENCE is not None:
            with (EVIDENCE / "results.json").open("xb") as handle:
                handle.write(raw)

    def assert_swap_refused(self, name, mutation, *, statuses=None, legacy_accepts=True):
        old = fixture(self.legacy, legacy=True, statuses=statuses)
        new = fixture(self.current, statuses=statuses)
        mutation(old[2], old[3])
        mutation(new[2], new[3])
        self.assertEqual(len(new[1].closed), 260)
        if legacy_accepts:
            grade(old)
        else:
            with self.assertRaises(ValueError):
                grade(old)
        with self.assertRaisesRegex(ValueError, "source-owned role/person context") as rejected:
            grade(new)
        NOTES.append({"case": name, "all260_closed": True, "legacy_accepts": legacy_accepts,
                      "new_refused": True, "reason": str(rejected.exception)})

    def test_complete260_target_and_equal_person_units_match_retained_grader(self):
        old, new = fixture(self.legacy, legacy=True), fixture(self.current)
        before, after = grade(old), grade(new)
        self.assertEqual(before, after)
        self.assertTrue(after["whole_prediction_complete"])
        self.assertFalse(after["whole_study_qualified"])
        panel = after["actors"]["I/E"]
        expected = math.fsum((.06 + p * .001) ** 2 for p in range(26)) / 26
        trial_weighted = math.fsum((1 + p % 3) * (.06 + p * .001) ** 2 for p in range(26)) / 51
        self.assertAlmostEqual(panel["macro_mse"], expected, places=14)
        self.assertNotAlmostEqual(panel["macro_mse"], trial_weighted, places=10)
        self.assertEqual(panel["unit"], "fractional contrast squared")
        self.assertAlmostEqual(panel["display_percentage_point_rmse"], 100 * math.sqrt(expected), places=12)
        self.assertEqual(len(panel["descriptive_delete_one_person_macro"]), 26)
        NOTES.append({"case": "valid260", "exact_predecessor_output_equality": True,
                      "people": 26, "actor_slots": 208, "reference_slots": 52,
                      "trials_per_panel": 51, "macro_mse_I_E": panel["macro_mse"],
                      "raw_grade_sha256": pin(json.dumps(after, sort_keys=True).encode())["sha256"]})

    def test_same_person_policy_swap_refused(self):
        def swap(a, r):
            a["P/E"]["0"], a["I/E"]["0"] = a["I/E"]["0"], a["P/E"]["0"]
        self.assert_swap_refused("policy_swap", swap)

    def test_actor_reference_role_swap_refused(self):
        def swap(a, r):
            a["P/E"]["0"], r["N"]["0"] = r["N"]["0"], a["P/E"]["0"]
        self.assert_swap_refused("actor_reference_swap", swap)

    def test_reference_family_swap_refused(self):
        def swap(a, r):
            r["B"]["0"], r["N"]["0"] = r["N"]["0"], r["B"]["0"]
        self.assert_swap_refused("reference_family_swap", swap)

    def test_closed_context_replay_without_complete_use_refused(self):
        def replay(a, r):
            a["I/E"]["0"] = copy.deepcopy(a["P/E"]["0"])
        self.assert_swap_refused("context_replay", replay)

    def test_person_swaps_cover_sealed_and_unscored_failures(self):
        def swap(a, r):
            a["P/E"]["0"], a["P/E"]["1"] = a["P/E"]["1"], a["P/E"]["0"]
        self.assert_swap_refused("sealed_person_swap", swap, legacy_accepts=False)
        statuses = {("actor", "P/E", "0"): "failed", ("actor", "P/E", "1"): "blocked"}
        self.assert_swap_refused("failed_blocked_person_swap", swap, statuses=statuses)

    def test_incomplete_panels_without_failed_answer_maps_preserved(self):
        statuses = {("actor", "I/EH", "2"): "blocked", ("actor", "P/H", "4"): "failed",
                    ("reference", "B", "3"): "failed"}
        old, new = fixture(self.legacy, legacy=True, statuses=statuses), fixture(self.current, statuses=statuses)
        before, after = grade(old), grade(new)
        self.assertEqual(before, after)
        self.assertFalse(after["whole_prediction_complete"])
        self.assertEqual(len(new[4]["context_answer_maps"]), 257)
        self.assertIsNone(after["actors"]["I/EH"]["macro_mse"])
        self.assertIsNone(after["references"]["B"]["macro_mse"])
        self.assertIsNone(after["actors"]["P/E"]["versus_behavior_reference"])
        NOTES.append({"case": "incomplete257_maps260_slots", "exact_predecessor_output_equality": True,
                      "no_maps_or_seals_required_for_failed_blocked": True})

    def test_constructor_requires_original_slot_domains_and_disjoint_values(self):
        c, v, g = self.current.module("common"), self.current.module("views"), self.current.module("grading")
        _, actors, refs = slot_maps(c, v)
        for defect in ("legacy_lists", "missing_person", "wrong_policy", "duplicate_actor", "actor_reference_alias"):
            a, r = dict(actors), dict(refs)
            if defect == "legacy_lists":
                a, r = list(a.values()), list(r.values())
            elif defect == "missing_person":
                a.pop(("P", "B", "0"))
            elif defect == "wrong_policy":
                a[("Q", "B", "0")] = a.pop(("P", "B", "0"))
            elif defect == "duplicate_actor":
                a[("P", "E", "0")] = a[("P", "B", "0")]
            else:
                r[("B", "0")] = a[("P", "B", "0")]
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                g.ReleaseBarrier(a, r, None, None)
        NOTES.append({"case": "constructor_roster", "malformed_variants_refused": 5})

    def test_constructor_detaches_source_owned_caller_maps(self):
        value = fixture(self.current)
        before = grade(value)
        value[5][("P", "B", "0")] = "caller-mutated-actor"
        value[6][("B", "0")] = "caller-mutated-reference"
        self.assertEqual(before, grade(value))
        NOTES.append({"case": "caller_map_mutation", "retained_assignment_unchanged": True})

    def test_real_captured_controller_joins_exact_grading_and_source_pins(self):
        controller = self.current.module("controller")
        grading = self.current.module("grading")
        self.assertIs(controller.ReleaseBarrier, grading.ReleaseBarrier)
        self.assertIs(controller.grade_prediction_panels, grading.grade_prediction_panels)
        self.assertEqual(len(verify_source_closure()["files"]), 46)
        NOTES.append({"case": "captured_package_and_manifest_closure", "effective_members": 46,
                      "central_members": 17, "whole_programme_executed": False})


if __name__ == "__main__":
    unittest.main(verbosity=2)
