"""Adversarial tests of the offline draft/evidence validator; no task is executed."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "validate_neuro_tasks.py"
SPEC = importlib.util.spec_from_file_location("validate_neuro_tasks", SCRIPT)
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)

CONFIG = '''schema_version = "1.4"
artifacts = ["/root/results/predictions.csv"]
[task]
name = "terminal-bench-science/test-task"
description = "A fixture, never a submission"
authors = [{name="Test Fixture",email="fixture@example.invalid"}]
keywords = ["neuroscience"]
[metadata]
author_name = "Test Fixture"
author_email = "fixture@example.invalid"
author_organization = "Test fixture"
author_profile = "https://example.invalid/fixture"
domain = "life-sciences"
field = "neuroscience"
subfield = "systems"
tags = ["test"]
expert_time_estimate_hours = 1.0
relevant_experience = "Test fixture only"
conflicts_of_interest = "Test fixture only"
[agent]
timeout_sec = 28800
[environment]
network_mode = "public"
build_timeout_sec = 600
cpus = 2
memory_mb = 4096
storage_mb = 10000
[verifier]
timeout_sec = 300
environment_mode = "separate"
[verifier.environment]
network_mode = "no-network"
'''


class ValidatorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.task = self.base / "test-task"
        self.evidence = self.base / "external-authoring"
        self.write("task.toml", CONFIG)
        self.write("instruction.md", "Write /root/results/predictions.csv." + v.SUFFIX)
        self.write("README.md", "## Difficulty\nRequires analysis.\n## Reference solution\nFit reference.\n## Verification\nCheck held-out outputs.\n")
        self.write("solution/solve.sh", "#!/bin/sh\npython /solution/reference.py\n")
        self.write("environment/Dockerfile", "FROM python:3.11.9-slim\nCOPY data /data\n")
        self.write("environment/data/input.csv", "trial,value\n1,4\n")
        self.write("tests/Dockerfile", "FROM python:3.11.9-slim\nRUN pip install pytest==8.4.1 pytest-json-ctrf==0.3.5\nCOPY . /tests/\nRUN mkdir -p /root/results /logs/verifier\n")
        self.write("tests/test.sh", "#!/bin/sh\nif pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py; then\n echo 1 > /logs/verifier/reward.txt\nelse\n echo 0 > /logs/verifier/reward.txt\nfi\n")
        self.lock = {"schema_version": 1, "inputs": [{"id": "neural-input", "role": "public_input", "url": "https://example.invalid/input-v1.csv", "version": "v1", "sha256": v.sha256(self.task / "environment/data/input.csv"), "bytes": (self.task / "environment/data/input.csv").stat().st_size, "local_path": "environment/data/input.csv", "license": "Synthetic test fixture, not research input"}]}
        self.qual = {"schema_version": 1, "instruction_authorship": {"kind": "ai_draft"}, "runs": {"oracle": {"status": "not_run"}, "nop": {"status": "not_run"}}}
        self.save_sidecars()

    def write(self, relative, text):
        path = self.task / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def json_write(self, relative, value):
        path = self.evidence / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return path

    def save_sidecars(self):
        self.json_write("provenance/inputs.lock.json", self.lock)
        self.json_write("evidence/qualification.json", self.qual)

    def audit(self):
        return v.validate_task(self.task, self.evidence)

    def assert_issue(self, code):
        report = self.audit()
        self.assertFalse(report["static_pass"], report)
        self.assertIn(code, [i["code"] for i in report["issues"]], report)
        self.assertFalse(report["accepted"])

    def replace_config(self, old, new):
        path = self.task / "task.toml"
        path.write_text(path.read_text().replace(old, new))

    def record(self, kind, mutate=None):
        fingerprint = self.audit()["task_fingerprint"]
        expected = 1 if kind == "oracle" else 0
        result = {"task_name": "test-task", "trial_name": "fixture-trial", "task_checksum": "a" * 64, "finished_at": "2026-10-29T10:00:00+00:00", "agent_info": {"name": kind}, "config": {"agent": {"name": kind}}, "exception_info": None, "verifier_environment_mode": "separate", "verifier_result": {"rewards": {"reward": expected}}, "step_results": None}
        if mutate:
            mutate(result)
        path = self.json_write(f"evidence/{kind}/result.json", result)
        reward = self.json_write(f"evidence/{kind}/reward.txt", expected)
        ctrf = self.json_write(f"evidence/{kind}/ctrf.json", {"results": {"tests": [{"name": "behavior", "status": "passed" if expected else "failed"}], "summary": {"tests": 1, "passed": expected, "failed": 1 - expected, "skipped": 0, "pending": 0, "other": 0}}})
        self.qual["runs"][kind] = {"status": "recorded", "result_path": path.relative_to(self.evidence).as_posix(), "result_sha256": v.sha256(path), "reward_path": reward.relative_to(self.evidence).as_posix(), "reward_sha256": v.sha256(reward), "ctrf_path": ctrf.relative_to(self.evidence).as_posix(), "ctrf_sha256": v.sha256(ctrf), "task_fingerprint": fingerprint, "harbor_version": "test-fixture", "completed_at": result.get("finished_at"), "command": ["harbor", "run", "-a", kind]}
        self.save_sidecars()

    def test_valid_draft_is_not_runtime_or_acceptance(self):
        result = self.audit()
        self.assertTrue(result["static_pass"], result)
        self.assertEqual(result["qualification_status"], "static_pass_runtime_unverified")
        self.assertFalse(result["accepted"])
        self.assertEqual(result["runtime_evidence"]["oracle"]["status"], "not_run")

    def remove_human_metadata(self):
        lines = (self.task / "task.toml").read_text().splitlines()
        prefixes = tuple(k + " =" for k in (*v.HUMAN_METADATA, "authors", "expert_time_estimate_hours"))
        self.write("task.toml", "\n".join(line for line in lines if not line.startswith(prefixes)) + "\n")

    def test_strict_default_does_not_waive_missing_human_metadata(self):
        self.remove_human_metadata()
        result = self.audit()
        self.assertFalse(result["static_pass"])
        self.assertTrue(result["technical_pass"])
        self.assertFalse(result["publication_metadata_complete"])
        self.assertEqual(result["profile"]["mode"], "science")

    def test_explicit_local_draft_allows_only_missing_declarations(self):
        self.remove_human_metadata()
        result = v.validate_task(self.task, self.evidence, profile="local-draft")
        self.assertTrue(result["static_pass"], result)
        self.assertFalse(result["publication_metadata_complete"])
        self.assertFalse(result["accepted"])
        self.assertEqual(result["profile"]["mode"], "local-draft")

    def test_local_draft_does_not_waive_scientific_metadata(self):
        self.remove_human_metadata()
        self.replace_config('domain = "life-sciences"', '')
        result = v.validate_task(self.task, self.evidence, profile="local-draft")
        self.assertFalse(result["static_pass"])
        self.assertFalse(result["technical_pass"])

    def test_local_draft_rejects_malformed_present_human_fields(self):
        for old, new in [('author_name = "Test Fixture"', 'author_name = ["not a string"]'), ('expert_time_estimate_hours = 1.0', 'expert_time_estimate_hours = -1'), ('authors = [{name="Test Fixture",email="fixture@example.invalid"}]', 'authors = "not an array"')]:
            with self.subTest(new=new):
                self.write("task.toml", CONFIG.replace(old, new))
                result = v.validate_task(self.task, self.evidence, profile="local-draft")
                self.assertFalse(result["static_pass"])
                self.assertFalse(result["publication_metadata_complete"])

    def test_runtime_consistency_reported_despite_publication_blocker(self):
        self.remove_human_metadata()
        self.record("oracle")
        self.record("nop")
        strict = self.audit()
        draft = v.validate_task(self.task, self.evidence, profile="local-draft")
        self.assertFalse(strict["static_pass"])
        self.assertEqual(strict["runtime_evidence_status"], "consistent")
        self.assertTrue(draft["static_pass"])
        self.assertEqual(draft["runtime_evidence_status"], "consistent")
        self.assertFalse(strict["accepted"])
        self.assertFalse(draft["accepted"])

    def test_local_draft_cannot_waive_network_isolation(self):
        self.remove_human_metadata()
        self.replace_config('network_mode = "no-network"', 'network_mode = "public"')
        result = v.validate_task(self.task, self.evidence, profile="local-draft")
        self.assertFalse(result["static_pass"])

    def test_cli_local_draft_is_explicit_opt_in(self):
        self.remove_human_metadata()
        command = [sys.executable, str(SCRIPT), str(self.task), "--evidence-dir", str(self.evidence), "--json"]
        strict = subprocess.run(command, capture_output=True, text=True)
        draft = subprocess.run(command + ["--profile", "local-draft"], capture_output=True, text=True)
        self.assertEqual(strict.returncode, 1)
        self.assertEqual(draft.returncode, 0)
        report = json.loads(draft.stdout)
        self.assertEqual(report["accepted_count"], 0)
        self.assertFalse(report["reports"][0]["publication_metadata_complete"])

    def test_schema_version_is_not_hardcoded(self):
        self.replace_config('schema_version = "1.4"', 'schema_version = "1.5"')
        self.assertTrue(self.audit()["static_pass"])

    def test_misplaced_artifacts_cannot_silently_disappear(self):
        self.replace_config('artifacts = ["/root/results/predictions.csv"]\n', '')
        self.replace_config('[verifier]\n', '[verifier]\nartifacts = ["/root/results/predictions.csv"]\n')
        self.assert_issue("artifacts")
        self.assert_issue("unknown_field")

    def test_unknown_native_environment_field_fails(self):
        self.replace_config('[environment]\n', '[environment]\nnetwork_mod = "public"\n')
        self.assert_issue("unknown_field")

    def test_shared_verifier_rejected(self):
        self.replace_config('environment_mode = "separate"', 'environment_mode = "shared"')
        self.assert_issue("separate_verifier")

    def test_implicit_or_public_verifier_network_rejected(self):
        for replacement in ('', 'network_mode = "public"'):
            with self.subTest(replacement=replacement):
                self.write("task.toml", CONFIG.replace('network_mode = "no-network"', replacement))
                self.assert_issue("network_policy")

    def test_phase_override_cannot_disable_public_agent(self):
        self.replace_config('[agent]\n', '[agent]\nnetwork_mode = "no-network"\n')
        self.assert_issue("agent_network_override")

    def test_resource_bool_and_nonpositive_rejected(self):
        for value in ('true', '0', '-3', 'nan'):
            with self.subTest(value=value):
                self.write("task.toml", CONFIG.replace('cpus = 2', 'cpus = ' + value))
                self.assert_issue("resource")

    def test_tbs_hosted_extension_allowed_for_large_compute(self):
        self.replace_config('cpus = 2', 'cpus = 8\nbackend = "hosted"')
        self.assertTrue(self.audit()["static_pass"])

    def test_artifact_traversal_or_protected_location_fails(self):
        for path in ('/root/results/../secret', '/tests/answer.csv', '/root', '/root/results/*.csv'):
            with self.subTest(path=path):
                self.write("task.toml", CONFIG.replace('/root/results/predictions.csv', path))
                self.assert_issue("artifact_path")

    def test_output_parent_must_be_precreated(self):
        path = self.task / "tests/Dockerfile"
        path.write_text(path.read_text().replace('/root/results ', ''))
        self.assert_issue("artifact_parent")

    def test_json_copy_form_accepted(self):
        path = self.task / "tests/Dockerfile"
        path.write_text(path.read_text().replace('COPY . /tests/', 'COPY [".", "/tests/"]'))
        self.assertTrue(self.audit()["static_pass"])

    def test_agent_copy_of_solution_is_rejected(self):
        self.write("environment/Dockerfile", 'FROM python:3.11.9-slim\nCOPY ../solution /solution\n')
        self.assert_issue("agent_copy_boundary")

    def test_runtime_installs_rejected(self):
        path = self.task / "tests/test.sh"
        path.write_text(path.read_text() + '\npython -m pip install scipy\n')
        self.assert_issue("runtime_install")

    def test_exact_final_instruction_required(self):
        self.write("instruction.md", "Write /root/results/predictions.csv.\nYou have 28800 seconds to complete this task.\n")
        self.assert_issue("instruction_suffix")

    def test_comment_only_readme_is_not_substantive(self):
        self.write("README.md", "## Difficulty\n<!-- Explain difficulty. -->\n## Reference solution\nFit.\n## Verification\nCheck.\n")
        self.assert_issue("readme_section")

    def test_fractional_reward_rejected(self):
        path = self.task / "tests/test.sh"
        path.write_text(path.read_text().replace('echo 1 >', 'echo 0.5 >'))
        self.assert_issue("fractional_reward")

    def test_ambiguous_reward_precedence_rejected(self):
        self.write("tests/other.py", "# reward.json is another output\n")
        self.assert_issue("reward_precedence")

    def test_modified_local_input_rejected(self):
        self.write("environment/data/input.csv", "trial,value\n1,5\n")
        self.assert_issue("input_hash_mismatch")

    def test_input_symlink_rejected_even_within_root(self):
        path = self.task / "environment/data/input.csv"
        path.rename(path.with_name("original.csv"))
        path.symlink_to("original.csv")
        self.assert_issue("input_local_path")

    def test_input_traversal_rejected(self):
        self.lock["inputs"][0]["local_path"] = "../outside.csv"
        self.save_sidecars()
        self.assert_issue("input_local_path")

    def test_mutable_alias_and_duplicate_ids_rejected(self):
        self.lock["inputs"][0]["version"] = "main"
        self.lock["inputs"].append(copy.deepcopy(self.lock["inputs"][0]))
        self.save_sidecars()
        self.assert_issue("input_id")
        self.assert_issue("input_version")

    def test_malformed_nested_sidecars_fail_without_crash(self):
        for document, path in (([], "provenance/inputs.lock.json"), ({"schema_version": 1, "inputs": ["bad", {"role": []}]}, "provenance/inputs.lock.json"), ({"schema_version": 1, "instruction_authorship": {"kind": []}, "runs": []}, "evidence/qualification.json"), ({"schema_version": 1, "instruction_authorship": {"kind": "ai_draft"}, "runs": {"oracle": {"status": []}}}, "evidence/qualification.json")):
            with self.subTest(document=document):
                self.save_sidecars()
                self.json_write(path, document)
                result = self.audit()
                self.assertFalse(result["static_pass"])
                self.assertFalse(result["accepted"])

    def test_malformed_table_fails_without_crash(self):
        self.replace_config('[agent]\ntimeout_sec = 28800', 'agent = ["bad"]')
        self.assertFalse(self.audit()["static_pass"])

    def test_recorded_trials_are_consistency_not_acceptance(self):
        self.record("oracle")
        self.record("nop")
        result = self.audit()
        self.assertTrue(result["static_pass"], result)
        self.assertEqual(result["qualification_status"], "runtime_evidence_consistent_review_pending")
        self.assertFalse(result["accepted"])
        self.assertFalse(result["runtime_evidence"]["oracle"]["verified"])

    def test_changed_task_invalidates_recorded_evidence(self):
        self.record("oracle")
        self.write("solution/solve.sh", "#!/bin/sh\necho changed\n")
        self.assert_issue("stale_evidence")

    def test_changed_extensionless_program_invalidates_evidence(self):
        self.write("environment/tool", "old executable contents")
        self.record("oracle")
        self.write("environment/tool", "new executable contents")
        self.assert_issue("stale_evidence")

    def test_changed_binary_reference_invalidates_evidence(self):
        path = self.task / "tests/reference.npz"
        path.write_bytes(b"old numerical archive")
        self.record("oracle")
        path.write_bytes(b"new numerical archive")
        self.assert_issue("stale_evidence")

    def test_native_checksum_disagreement_is_not_same_task(self):
        self.record("oracle")
        self.record("nop", lambda r: r.update(task_checksum="b" * 64))
        self.assert_issue("run_checksum_disagreement")

    def test_invalid_native_field_types_rejected(self):
        changes = [('description = "A fixture, never a submission"', 'description = ["bad"]'), ('keywords = ["neuroscience"]', 'keywords = [["bad"]]'), ('memory_mb = 4096', 'memory_mb = 1.5'), ('[agent]\n', '[agent]\nuser = {}\n'), ('[environment]\n', '[environment]\nos = "bogus"\n'), ('[verifier]\n', '[verifier]\ncollect = "bad"\n')]
        for old, new in changes:
            with self.subTest(new=new):
                self.write("task.toml", CONFIG.replace(old, new))
                self.assertFalse(self.audit()["static_pass"])

    def test_ctrf_failed_or_zero_oracle_tests_rejected(self):
        self.record("oracle")
        path = self.evidence / self.qual["runs"]["oracle"]["ctrf_path"]
        report = json.loads(path.read_text())
        report["results"]["tests"][0]["status"] = "failed"
        self.json_write(path.relative_to(self.evidence), report)
        self.qual["runs"]["oracle"]["ctrf_sha256"] = v.sha256(path)
        self.save_sidecars()
        self.assert_issue("ctrf_oracle")
        self.assert_issue("ctrf_summary")
        report["results"]["tests"] = []
        self.json_write(path.relative_to(self.evidence), report)
        self.qual["runs"]["oracle"]["ctrf_sha256"] = v.sha256(path)
        self.save_sidecars()
        self.assert_issue("ctrf_results")

    def test_wrong_task_or_agent_cannot_qualify(self):
        self.record("oracle", lambda r: r.update(task_name="another-task"))
        self.assert_issue("run_task")
        self.record("oracle", lambda r: r["agent_info"].update(name="nop"))
        self.assert_issue("run_agent")

    def test_boolean_or_fractional_reward_cannot_qualify(self):
        for reward in (True, 0.7, {"reward": 1, "other": 1}):
            with self.subTest(reward=reward):
                self.record("oracle", lambda r: r["verifier_result"].update(rewards=reward if isinstance(reward, dict) else {"reward": reward}))
                self.assert_issue("run_reward")

    def test_nop_must_fail_task_not_infrastructure(self):
        self.record("nop", lambda r: r.update(exception_info={"exception_type": "BuildError"}))
        self.assert_issue("run_exception")
        self.record("nop", lambda r: r["verifier_result"].update(rewards={"reward": 1}))
        self.assert_issue("run_reward")

    def test_step_exception_invalidates_trial(self):
        self.record("oracle", lambda r: r.update(step_results=[{"exception_info": {"exception_type": "Timeout"}}]))
        self.assert_issue("run_step_exception")

    def test_reward_capture_required(self):
        self.record("oracle")
        del self.qual["runs"]["oracle"]["reward_path"]
        self.save_sidecars()
        self.assert_issue("reward_evidence")

    def test_status_passed_is_not_evidence(self):
        self.qual["runs"]["oracle"] = {"status": "passed"}
        self.save_sidecars()
        self.assert_issue("run_status")

    def test_result_tampering_rejected(self):
        self.record("oracle")
        path = self.evidence / self.qual["runs"]["oracle"]["result_path"]
        path.write_text(path.read_text() + "\n")
        self.assert_issue("run_digest")

    def test_cli_json_and_require_runtime_evidence(self):
        command = [sys.executable, str(SCRIPT), str(self.task), "--evidence-dir", str(self.evidence), "--json"]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["accepted_count"], 0)
        result = subprocess.run(command + ["--require-runtime-evidence"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)

    def test_empty_collection_is_not_a_pass(self):
        empty = self.base / "empty"
        empty.mkdir()
        result = subprocess.run([sys.executable, str(SCRIPT), str(empty), "--json"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No task.toml", result.stderr)


if __name__ == "__main__":
    unittest.main()
