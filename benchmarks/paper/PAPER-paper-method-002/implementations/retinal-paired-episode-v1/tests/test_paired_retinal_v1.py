"""One bounded, generated-only paired retinal software-control campaign.

Run under Python 3.11 with -I -B. ARTIFACT_DIR must name a fresh directory
outside source trees. No original data, model, reference, provider or Git is
used. Full metadata and source-shaped synthetic arrays check logical release;
they establish no physical isolation or scientific benchmark readiness.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time
import types
import unittest


# Sealed by the source author after the independent interface authors finish.
PINS = {
    "control_runtime.py": (7530, "2cb993f420a8e12164763ff2ebe436e506fae519c1e412017643762a685c8541"),
    "generated_retinal_fixture.py": (5243, "c5bbb49b4dd584fd680c48d2d6fc76072fad38f9bc1e3dde01a28956ab6e9f92"),
    "generated_episode_fixture.py": (7410, "d64079838a12d7c8858699c5418e59f93ed0b04c02e97bfce2d8f6beebe1b876"),
    "paired_episode.py": (25944, "563bbf84b2efce0a9beffabbef6308ce40cd1d6bcd4921f0492984a33d7d6e14"),
    "paired_assessment.py": (14799, "4c4cd59ec5ff2ff1fa356a0be9ca49d08183968f713d2069f0db4e5b2603affc"),
}


def bootstrap_runtime(path):
    """Authenticate the small local loader before any target code is loaded."""
    size, digest = PINS[path.name]
    if not 0 < size <= 131072 or path.is_symlink():
        raise ValueError("runtime source is not sealed")
    with path.open("rb") as stream:
        body = stream.read(size + 1)
    if len(body) != size or hashlib.sha256(body).hexdigest() != digest:
        raise ValueError("runtime source digest mismatch")
    module = types.ModuleType("_paired_control_runtime")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec", dont_inherit=True), module.__dict__)
    return module


class CompactResult(unittest.TestResult):
    """Bound diagnostics independently of array or exception representations."""
    def __init__(self):
        super().__init__()
        self.records = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({"test": test.id().split(".")[-1], "status": "PASS"})

    def addFailure(self, test, err):
        # Avoid the unittest traceback, which can retain/dump payload-like locals.
        self.failures.append((test, "bounded failure"))
        self.records.append({"test": test.id().split(".")[-1], "status": "FAIL",
                             "exception": err[0].__name__[:96], "detail": str(err[1])[:512]})

    def addError(self, test, err):
        self.errors.append((test, "bounded error"))
        self.records.append({"test": test.id().split(".")[-1], "status": "ERROR",
                             "exception": err[0].__name__[:96], "detail": str(err[1])[:512]})

    def addSubTest(self, test, subtest, err):
        if err is not None:
            self.failures.append((subtest, "bounded generated mutation failure"))
            self.records.append({"test": test.id().split(".")[-1], "status": "FAIL",
                                 "exception": err[0].__name__[:96], "detail": str(err[1])[:512]})


def write_unittest_summary(result, elapsed_seconds):
    """Publish bounded standard unittest status from the already-run result."""
    successful = result.wasSuccessful()
    counters = (
        ("failures", len(result.failures)),
        ("errors", len(result.errors)),
        ("skipped", len(result.skipped)),
        ("expected failures", len(result.expectedFailures)),
        ("unexpected successes", len(result.unexpectedSuccesses)),
    )
    details = ", ".join(f"{name}={count}" for name, count in counters if count)
    status = "OK" if successful else "FAILED"
    if details or not successful:
        status += f" ({details})"
    summary = (f"\nRan {result.testsRun} tests in {elapsed_seconds:.3f}s\n\n"
               f"{status}\n")
    if len(summary.encode("utf-8")) > 1024:
        raise ValueError("unittest summary exceeds 1024 bytes")
    sys.stderr.write(summary)


def make_campaign(runtime, fixture, metadata, paired, assessment, np, roots, output):
    class PairedRetinalGeneratedControls(unittest.TestCase):
        def operands_episode(self):
            operands = fixture.generated_retinal_operands()
            return (*operands, metadata.generated_episode(*operands))

        def assess(self, operator, author, candidate, episode, **kwargs):
            return assessment.assess_pair(
                operator, author, candidate, episode=episode,
                implementations_root=roots["implementations"],
                episode_source_root=roots["episode"], **kwargs)

        def assert_unqualified(self, result):
            self.assertEqual(result["qualification"], "UNQUALIFIED")
            for field in ("reproduced", "improved", "uncertainty"):
                self.assertIsNone(result[field])
            self.assertFalse(result["published_rounded_score_used_as_threshold"])
            self.assertFalse(result["implementation"]["scientific_policy_evaluator_bound"])
            self.assertFalse(result["implementation"]["transport_verifier_bound"])
            self.assertIsNone(result["both_candidate_conditions_completed"])

        def test_actual_release_shared_validation_private_test_and_detached_copies(self):
            private = fixture.generated_private_binding(np)
            declaration = fixture.generated_validation_access_declaration()
            a = paired.candidate_view_v2(private, "paper+data", validation_access=declaration)
            b = paired.candidate_view_v2(private, "paper+data+code", validation_access=declaration)
            expected_top = {"schema", "cell_id", "information_condition", "identity_sha256",
                            "site_keys", "preprocessing_access", "validation_access_sha256", "splits"}
            self.assertEqual(set(a), expected_top)
            self.assertEqual(set(b), expected_top)
            self.assertEqual(a["schema"], "jaxley-retinal-candidate-input-v2")
            self.assertEqual(a["site_keys"], b["site_keys"])
            self.assertEqual(a["identity_sha256"], b["identity_sha256"])
            self.assertEqual(a["validation_access_sha256"], b["validation_access_sha256"])
            for split in ("train", "val", "test"):
                va, vb = a["splits"][split], b["splits"][split]
                expected_keys = {"row_ids", "images", "currents", "mask"}
                if split != "test":
                    expected_keys.add("targets")
                self.assertEqual(set(va), expected_keys)
                self.assertEqual(set(vb), expected_keys)
                rows = private["splits"][split]
                for key in expected_keys:
                    self.assertTrue(np.array_equal(va[key], vb[key]), key)
                    self.assertFalse(np.shares_memory(va[key], vb[key]), key)
                self.assertTrue(np.array_equal(va["row_ids"], rows))
                self.assertTrue(np.array_equal(va["mask"], private["mask"][rows]))
                if split != "test":
                    self.assertTrue(np.array_equal(va["targets"], private["labels"][rows]))
                    self.assertFalse(np.shares_memory(va["targets"], private["labels"]))
            # A concrete write through the released A view cannot change B/source.
            row = private["splits"]["val"][0]
            original = float(private["labels"][row, 0])
            a["splits"]["val"]["targets"][0, 0] = original + 123.0
            self.assertEqual(float(private["labels"][row, 0]), original)
            self.assertEqual(float(b["splits"]["val"]["targets"][0, 0]), original)
            self.assertNotIn("author_code", b)
            declaration["candidate_validation_query_limit"] = 21
            with self.assertRaises(paired.EpisodeContractError):
                paired.candidate_view_v2(private, "paper+data", validation_access=declaration)

        def test_all_site_signed_signal_scores_and_axis_alignment(self):
            operator, author, candidate, episode = self.operands_episode()
            result = self.assess(operator, author, candidate, episode)
            self.assert_unqualified(result)
            compared = result["legacy_comparison"]
            self.assertEqual(compared["recording_sites"], 147)
            self.assertEqual(compared["raw_roi_count"], 232)
            self.assertEqual(compared["test_rows"], 128)
            self.assertEqual(len(compared["sites"]), 147)
            self.assertTrue(all(site["valid_count"] >= 8 for site in compared["sites"]))
            self.assertAlmostEqual(compared["author_mean_pearson"], -1.0, places=12)
            self.assertAlmostEqual(compared["candidate_mean_pearson"], 1.0, places=12)
            self.assertAlmostEqual(compared["paired_delta"], 2.0, places=12)
            self.assertEqual(result["descriptive_paired_delta"], compared["paired_delta"])
            self.assertFalse(compared["undefined_sites_dropped"])
            self.assertTrue(result["episode_validation"]["contract_valid"])
            self.assertNotIn("EPISODE_SCORED_PACKET_BINDING_MISMATCH", result["qualification_reasons"])
            self.assertNotIn("EPISODE_TARGET_IDENTITY_MISMATCH", result["qualification_reasons"])

        def test_declared_policy_receipts_and_provenance_cannot_self_qualify(self):
            operator, author, candidate, episode = self.operands_episode()
            episode["execution_provenance"] = {
                role: metadata.generated_provenance(episode, role)
                for role in ("reference", "A", "B")}
            # These are declared hashes of generated text, not a scientific policy.
            descriptor = {"bytes": 40, "sha256": hashlib.sha256(b"generated-unverified-policy-metadata-only").hexdigest()}
            policy = {"schema": "jaxley-retinal-policy-precommit-v1",
                      "policy_artifact": descriptor,
                      "commitment_receipt": dict(descriptor),
                      "commit_event_id": "generated-event-not-authenticated"}
            evidence = {"qualified": True, "approved": True, "physical_transport_verified": True}
            result = self.assess(operator, author, candidate, episode,
                                 trusted_operator_evidence=evidence, policy_precommit=policy)
            self.assert_unqualified(result)
            self.assertTrue(result["episode_validation"]["contract_valid"])
            self.assertFalse(result["episode_validation"]["qualification"])
            self.assertEqual(result["policy_precommit"]["status"], "PRESENT_UNVERIFIED")
            self.assertFalse(result["policy_precommit"]["authority_verified"])
            self.assertFalse(result["policy_precommit"]["chronology_verified"])
            self.assertIn("CALLER_SUPPLIED_OPERATOR_EVIDENCE_CANNOT_QUALIFY_UNBOUND_TRANSPORT",
                          result["qualification_reasons"])

        def test_mismatched_exposure_private_targets_and_frozen_provenance_refused(self):
            operator, author, candidate, base = self.operands_episode()
            self.assertTrue(paired.validate_pair(base)["contract_valid"])
            mutations = []
            bad = copy.deepcopy(base)
            bad["conditions"]["B"]["view"]["splits"]["val"]["targets"]["sha256"] = "f" * 64
            mutations.append(("validation_targets", bad))
            bad = copy.deepcopy(base)
            bad["conditions"]["B"]["paper"]["sha256"] = "e" * 64
            mutations.append(("common_paper", bad))
            bad = copy.deepcopy(base)
            bad["conditions"]["A"]["author_code"] = copy.deepcopy(bad["conditions"]["B"]["author_code"])
            mutations.append(("code_in_A", bad))
            bad = copy.deepcopy(base)
            for condition in ("A", "B"):
                bad["conditions"][condition]["paper"] = copy.deepcopy(bad["reference_programme"]["source_snapshot"])
            mutations.append(("author_code_disguised_as_common_paper", bad))
            bad = copy.deepcopy(base)
            bad["conditions"]["A"]["view"]["splits"]["test"]["targets"] = copy.deepcopy(bad["private_materials"]["observed_test_calcium"])
            mutations.append(("test_targets", bad))
            bad = copy.deepcopy(base)
            for condition in ("A", "B"):
                bad["conditions"][condition]["paper"] = copy.deepcopy(bad["private_materials"]["observed_test_calcium"])
            mutations.append(("private_target_disguised_as_common_input", bad))
            bad = copy.deepcopy(base)
            bad["reference_programme"]["configuration_sha256"] = "d" * 64
            mutations.append(("programme_digest", bad))
            bad = copy.deepcopy(base)
            provenance = metadata.generated_provenance(bad, "reference")
            provenance["source_snapshot"]["sha256"] = "c" * 64
            bad["execution_provenance"]["reference"] = provenance
            mutations.append(("reference_source_snapshot", bad))
            bad = copy.deepcopy(base)
            provenance = metadata.generated_provenance(bad, "reference")
            provenance["context_sha256"] = "b" * 64
            bad["execution_provenance"]["reference"] = provenance
            mutations.append(("reference_context", bad))
            for label, episode in mutations:
                with self.subTest(mutation=label):
                    with self.assertRaises(paired.EpisodeContractError):
                        paired.validate_pair(episode)
            result = self.assess(operator, author, candidate, mutations[0][1])
            self.assert_unqualified(result)
            self.assertIn("EPISODE_CONTRACT_INVALID", result["qualification_reasons"])
            self.assertAlmostEqual(result["descriptive_paired_delta"], 2.0, places=12)
            stale = copy.deepcopy(base)
            stale["scored_packet_sha256"]["candidate"] = "a" * 64
            result = self.assess(operator, author, candidate, stale)
            self.assert_unqualified(result)
            self.assertIn("EPISODE_SCORED_PACKET_BINDING_MISMATCH", result["qualification_reasons"])

        def test_nonfinite_refused_and_undefined_site_never_dropped(self):
            operator, author, candidate, episode = self.operands_episode()
            for nonfinite in (float("nan"), float("inf"), -float("inf")):
                bad = copy.deepcopy(candidate)
                bad["predictions"][0][0] = nonfinite
                with self.assertRaises(ValueError) as caught:
                    self.assess(operator, author, bad, episode)
                self.assertEqual(type(caught.exception).__name__, "Refusal")
                self.assertIn("finite_real_number", str(caught.exception))
            constant = fixture.replace_candidate_site_with_constant(candidate, candidate["site_keys"][0])
            episode = metadata.generated_episode(operator, author, constant)
            result = self.assess(operator, author, constant, episode)
            self.assert_unqualified(result)
            self.assertIsNone(result["descriptive_paired_delta"])
            self.assertIsNone(result["legacy_comparison"]["candidate_mean_pearson"])
            self.assertEqual(len(result["legacy_comparison"]["sites"]), 147)
            self.assertFalse(result["legacy_comparison"]["undefined_sites_dropped"])
            self.assertIn("COMPLETE_ALL_SITE_METRIC_UNDEFINED", result["qualification_reasons"])

        def test_portable_public_layout_defaults_use_unchanged_scorer(self):
            sources = {relative: (roots["implementations"] / relative, pin)
                       for relative, pin in assessment.LEGACY_PINS.items()}
            component = "retinal-paired-episode-v1"
            for name, key in (("paired_episode.py", "episode"),
                              ("paired_assessment.py", "assessment")):
                sources[component + "/" + name] = (roots[key] / name, PINS[name])
            staged = runtime.stage_portable_sources(output, sources)
            portable = runtime.load_pinned_source(
                "_paired_assessment_portable_control", staged / component / "paired_assessment.py",
                PINS["paired_assessment.py"])
            operator, author, candidate, episode = self.operands_episode()
            result = portable.assess_pair(operator, author, candidate, episode=episode)
            self.assert_unqualified(result)
            self.assertTrue(result["episode_validation"]["contract_valid"])
            self.assertAlmostEqual(result["descriptive_paired_delta"], 2.0, places=12)
            self.assertEqual(result["legacy_comparison"]["metric_source_sha256"],
                             {Path(path).name: pin[1] for path, pin in assessment.LEGACY_PINS.items()
                              if Path(path).name != "score.py"})

        def test_output_root_refuses_source_ancestor_descendant_and_symlink(self):
            protected = list(roots["protected"])
            controls = roots["controls"]
            for forbidden in (controls, controls.parent, controls / "forbidden-output"):
                with self.assertRaises(runtime.ControlBoundaryError):
                    runtime.validate_artifact_root(forbidden, protected)
            alias = output / "generated-source-symlink"
            alias.symlink_to(controls, target_is_directory=True)
            try:
                with self.assertRaises(runtime.ControlBoundaryError):
                    runtime.validate_artifact_root(alias / "forbidden-output", protected)
            finally:
                alias.unlink()
            self.assertEqual(runtime.validate_artifact_root(output, protected), output)

    return PairedRetinalGeneratedControls


def main():
    if sys.version_info[:2] != (3, 11):
        raise SystemExit("requires the selected Python 3.11 runtime")
    if not sys.dont_write_bytecode or not sys.flags.isolated:
        raise SystemExit("requires -I -B; source pycache is forbidden")
    controls = Path(__file__).resolve().parent
    component = controls.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode-source-root", type=Path, default=component)
    parser.add_argument("--assessment-source-root", type=Path, default=component)
    parser.add_argument("--implementations-root", type=Path, default=component.parent)
    parser.add_argument("--protected-source-root", type=Path, action="append", default=[])
    args = parser.parse_args()
    runtime = bootstrap_runtime(controls / "control_runtime.py")
    roots = {"episode": args.episode_source_root.resolve(strict=True),
             "assessment": args.assessment_source_root.resolve(strict=True),
             "implementations": args.implementations_root.resolve(strict=True),
             "controls": controls}
    roots["protected"] = tuple(dict.fromkeys(list(roots.values()) + args.protected_source_root))
    artifact_value = os.environ.get("ARTIFACT_DIR")
    if artifact_value is None:
        raise SystemExit("ARTIFACT_DIR must name a fresh, disjoint artifact directory")
    output = runtime.prepare_artifact_root(artifact_value, roots["protected"])
    fixture = runtime.load_pinned_source("_generated_retinal_fixture", controls / "generated_retinal_fixture.py", PINS["generated_retinal_fixture.py"])
    metadata = runtime.load_pinned_source("_generated_episode_fixture", controls / "generated_episode_fixture.py", PINS["generated_episode_fixture.py"])
    paired = runtime.load_pinned_source("_paired_episode_control", roots["episode"] / "paired_episode.py", PINS["paired_episode.py"])
    assessment = runtime.load_pinned_source("_paired_assessment_control", roots["assessment"] / "paired_assessment.py", PINS["paired_assessment.py"])
    import numpy as np
    started = time.monotonic()
    campaign = make_campaign(runtime, fixture, metadata, paired, assessment, np, roots, output)
    result = CompactResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(campaign).run(result)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    report = {"schema": "jaxley-paired-retinal-generated-controls-v1",
              "scope": "generated software behavior only; no biological/model/reference execution",
              "status": "PASS" if result.wasSuccessful() else "FAIL", "tests_run": result.testsRun,
              "results": result.records, "source_pins": PINS,
              "python": ".".join(map(str, sys.version_info[:3])), "numpy": np.__version__,
              "elapsed_seconds": time.monotonic() - started,
              "peak_rss_native_units": usage.ru_maxrss,
              "peak_rss_units": "bytes" if sys.platform == "darwin" else "KiB",
              "logical_release_generated_control_passed": any(
                  row["test"] == "test_actual_release_shared_validation_private_test_and_detached_copies" and
                  row["status"] == "PASS" for row in result.records),
              "physical_transport_qualified": False, "scientific_improvement_qualified": False,
              "original_payloads_read": False, "model_calls": 0,
              "generated_fixture_counts": {"sites": 147, "raw_rois": 232, "fields": 15,
                                            "split_rows": 15360, "test_rows": 128},
              "artifact_file_byte_limit": runtime.MAX_OUTPUT_BYTES,
              "artifact_total_byte_limit": runtime.MAX_TOTAL_OUTPUT_BYTES}
    receipt = runtime.write_summary(output, report)
    print(json.dumps({"status": report["status"], "tests_run": result.testsRun,
                      "scope": "generated software controls only", "artifact": receipt}, sort_keys=True))
    write_unittest_summary(result, report["elapsed_seconds"])
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
