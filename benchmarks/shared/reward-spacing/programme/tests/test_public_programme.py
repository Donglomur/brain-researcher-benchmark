"""Relocated source/programme controls; no original data, fitting or native runtime."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]


class PublicProgrammeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="reward-public-generated-")
        cls.workspace = Path(cls.temporary.name).resolve()
        cls.package = cls.workspace / "relocated source"
        shutil.copytree(PACKAGE, cls.package,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        cls.foreign = cls.workspace / "unrelated working directory"
        cls.foreign.mkdir()
        spec = importlib.util.spec_from_file_location(
            "reward_example_builder", cls.package / "examples/make_engineering_request.py")
        cls.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.builder)
        cls.lock = cls.builder.pin(cls.package / "CURRENT_SOURCE_LOCK.json")

    @classmethod
    def tearDownClass(cls):
        cls.retained_generated_bytes_before_cleanup = sum(
            p.stat().st_size for p in cls.workspace.rglob("*") if p.is_file())
        assert cls.retained_generated_bytes_before_cleanup < 8 << 20
        cls.temporary.cleanup()

    def cli(self, argv):
        result = subprocess.run(argv, cwd=self.foreign, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=70, env={"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertLess(len(result.stdout) + len(result.stderr), 131072)
        return result

    def source_command(self, task, sha=None):
        return [sys.executable, "-I", "-S", "-B", str(self.package / "run.py"),
                "source-check", "--task", task, "--source-bytes", str(self.lock["bytes"]),
                "--source-sha256", sha or self.lock["sha256"]]

    def test_three_relocated_default_source_checks(self):
        for task in ("PAPER-FIND-044", "NEURAL-045", "NEURAL-046"):
            with self.subTest(task=task):
                result = self.cli(self.source_command(task))
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                value = json.loads(result.stdout)
                self.assertEqual(value["paper_panels"], 166)
                self.assertEqual(value["source_conditions"], 13)
                self.assertEqual(value["neural_cells"], 84)
                self.assertEqual(value["independent_corpora"], 1)
                self.assertEqual(value["deployment"], "unconfigured")
                self.assertFalse(value["scientific_qualification"])

    def test_real_named_program_output_is_closed_before_grade(self):
        command = self.builder.build(self.workspace / "generated positive")
        result = self.cli(command["argv"])
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        envelope = json.loads(result.stdout)
        self.assertIsNone(envelope["failure"])
        self.assertFalse(envelope["scientific_qualification"])
        collected = envelope["result"]
        self.assertEqual(collected["accounted_slots"], command["required_slots"])
        self.assertFalse(collected["full_scientific_completion"])
        job = collected["results"][command["chosen_slot"]]
        self.assertEqual(job["status"], "engineering_collected")
        summary = job["reference_comparison"]
        self.assertEqual(len(summary["families"]), 9)
        self.assertEqual(summary["primary_status"], "engineering_score_only")
        self.assertTrue(summary["any_mandatory_reference_unscorable"])
        self.assertIsNotNone(job["closed_result"]["metrics"]["reference_relative_skill"])
        root = self.workspace / "generated positive/output/numerical"
        plan = json.loads((root / "plan.json").read_bytes())
        state = json.loads((root / "state.json").read_bytes())
        self.assertEqual(state["phase"], "complete_engineering")
        self.assertTrue(state["private_targets_opened"])
        self.assertEqual(len(plan["jobs"]), 2)
        self.assertEqual(plan["reference_jobs"], {"job_0": "job_1"})
        self.assertEqual(len({v["private_digest"] for v in state["jobs"].values()}), 1)
        for ident in plan["jobs"]:
            process = json.loads((root / "jobs" / ident / "operator/process_receipt.json").read_bytes())
            terminal = json.loads((root / "terminal" / ident / "process_receipt.json").read_bytes())
            self.assertTrue(process["process_group_closed"])
            self.assertTrue(terminal["process_group_closed"])
            self.assertTrue(process["engineering_only"])
            self.assertEqual(process["returncode"], 0)
            self.assertEqual(terminal["returncode"], 0)
            self.assertFalse(process["production_sandbox_qualified"])

    def test_authentic_marker_remains_refused_before_execution(self):
        directory = self.workspace / "generated refusal"
        command = self.builder.build(directory)
        request = json.loads((directory / "request.json").read_bytes())
        request["binding"]["synthetic"] = False
        (directory / "request.json").write_bytes(self.builder.encode(request))
        review = json.loads((directory / "review.json").read_bytes())
        review["request"] = {"path": str(directory / "request.json"),
                             **self.builder.pin(directory / "request.json")}
        (directory / "review.json").write_bytes(self.builder.encode(review))
        result = self.cli(command["argv"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("invented phase only", result.stderr.decode())
        self.assertFalse((directory / "output").exists())

    def test_wrong_source_digest_refused_before_dispatch(self):
        result = self.cli(self.source_command("NEURAL-045", "0" * 64))
        self.assertEqual(result.returncode, 2)
        self.assertIn("source bytes changed", result.stderr.decode())

    def test_historical_source_pin_does_not_admit_changed_current_source(self):
        old = self.builder.pin(self.package / "SOURCE_LOCK.json")
        command = self.source_command("NEURAL-045", old["sha256"])
        command[command.index("--source-bytes") + 1] = str(old["bytes"])
        result = self.cli(command)
        self.assertEqual(result.returncode, 2)
        self.assertIn("ordinary source pin", result.stderr.decode())

    def test_same_size_current_source_tamper_refused_before_import(self):
        for member in ("central/comparisons.py", "central/source.py"):
            with self.subTest(member=member):
                path = self.package / member
                original = path.read_bytes()
                marker = self.workspace / "must-not-execute"
                payload = ("open(" + repr(str(marker)) + ", 'w').write('executed')\n").encode()
                try:
                    path.write_bytes(payload + b" " * (len(original) - len(payload)))
                    result = self.cli(self.source_command("NEURAL-045"))
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("source bytes changed", result.stderr.decode())
                    self.assertFalse(marker.exists())
                finally:
                    path.write_bytes(original)

    def test_incomplete_current_lock_refused_even_with_matching_outer_pin(self):
        path = self.package / "CURRENT_SOURCE_LOCK.json"
        original = path.read_bytes()
        try:
            value = json.loads(original)
            value["files"] = [row for row in value["files"]
                              if row["path"] != "central/comparisons.py"]
            path.write_bytes(self.builder.encode(value))
            pin = self.builder.pin(path)
            command = self.source_command("NEURAL-045", pin["sha256"])
            command[command.index("--source-bytes") + 1] = str(pin["bytes"])
            result = self.cli(command)
            self.assertEqual(result.returncode, 2)
            self.assertIn("current source closure membership", result.stderr.decode())
        finally:
            path.write_bytes(original)

    def test_paper_registration_binds_current_scoring_lock(self):
        from central.execute import run
        from central.io import Refusal
        from central.source import configuration, paper
        role = next(iter(paper("pipeline").source_roles(configuration())["roles"].values()))
        common = {"actor_lineage": "invented", "context_id": "invented-A",
                  "paper_pins": [], "data_pins": [], "tool_contract": {},
                  "budget": {}, "prompt_sha256": "0" * 64, "ordinary_author_code": []}
        other = dict(common, context_id="invented-B", ordinary_author_code=[role["pin"]])
        setup = {"task": "PAPER-FIND-044", "condition": "invented-empty-binding-control",
                 "binding": {"synthetic": True}, "slots": []}
        request = {"mode": "engineering", "jobs": {}, "evaluation_banks": {},
                   "paired_access": {"paper_data": common, "paper_data_author_code": other},
                   "scoring_source_lock_sha256": self.lock["sha256"]}
        result = run(setup, request, self.workspace, None, None)
        self.assertEqual(result["available_slots"], 0)
        self.assertFalse(result["full_scientific_completion"])
        self.assertFalse(result["scientific_qualification"])
        request["scoring_source_lock_sha256"] = self.builder.pin(self.package / "SOURCE_LOCK.json")["sha256"]
        with self.assertRaisesRegex(Refusal, "actual registered scoring source"):
            run(setup, request, self.workspace, None, None)

    def test_all_route_and_external_role_obligations_survive_relocation(self):
        from central.source import TASKS, FULL, configuration, paper, neural
        from central.plan import construct, conditions
        registry, corpus = self.builder.invented_corpus()
        binding = {"corpus_id": "reward-spacing-10.1038-s41593-026-02206-2",
                   "version": "invented-metadata", "synthetic": True,
                   "asset_manifest_sha256": self.builder.digest("invented"),
                   "biological_registry_sha256": self.builder.digest(registry),
                   "views": {"paper": self.builder.digest("invented paper"),
                             "neural": self.builder.digest(corpus)}}
        route_count = 0
        for task in TASKS:
            expected = construct(task, None, registry, binding)
            self.assertEqual(expected, construct(task, FULL, registry, binding))
            for condition in conditions(task):
                self.assertEqual(construct(task, condition, registry, binding)["condition"], condition)
                route_count += 1
        self.assertEqual(route_count, 175)
        config = configuration()
        roles = paper("pipeline").source_roles(config)["roles"]
        self.assertEqual(len(roles), 8)
        self.assertTrue(all(v["pin"]["path"].startswith("owner-inputs/public/code/") for v in roles.values()))
        jobs = paper("native").build_native_jobs(
            {"roles": roles}, config["MODEL_PROGRAMME"],
            {"sha256": "invented-corpus"}, None, config["FIGURE_OBLIGATIONS"])
        self.assertFalse(jobs["all_native_roles_closed"])
        self.assertTrue(all("qualified_environment" in job["missing_roles"] for job in jobs["jobs"]))
        self.assertTrue(all(job["source_execution_authority"] is False for job in jobs["jobs"]))
        self.assertEqual(len(neural("contracts").specifications()[0]["cells"]), 84)

    def test_corrected_scoring_and_final_byte_source_custody(self):
        expected = "0bb78d584082c259e6b88e7987fd2c14d7d3334075d96f7a93c758a6f973f722"
        self.assertEqual(hashlib.sha256(
            (self.package / "neural/neuro/scoring.py").read_bytes()).hexdigest(), expected)
        distribution = json.loads((self.package / "SOURCE.json").read_bytes())
        self.assertFalse(distribution["authentic_execution_available"])
        self.assertFalse(distribution["scientific_qualification"])
        lock = json.loads((self.package / "CURRENT_SOURCE_LOCK.json").read_bytes())
        self.assertEqual(lock["schema"], "reward_complete_central_current_source_lock_v1")
        self.assertEqual({row["path"] for row in lock["files"]},
                         ({row["path"] for row in distribution["files"]} | {"SOURCE.json"}) - {"README.md"})
        self.assertFalse(lock["scientific_qualification"])
        self.assertFalse(lock["authentic_execution_available"])
        for field in ("predecessor_source_lock", "predecessor_distribution"):
            row = lock[field]
            self.assertEqual(self.builder.pin(self.package / row["path"]),
                             {k: row[k] for k in ("bytes", "sha256")})
        for row in lock["files"]:
            raw = (self.package / row["path"]).read_bytes()
            self.assertEqual(len(raw), row["bytes"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row["sha256"])
            self.assertTrue(raw.endswith(b"\n"))
            self.assertFalse(raw.endswith(b"\n\n"))
            self.assertTrue(all(line.rstrip(b" \t") == line for line in raw.splitlines()))
            if row["path"] in {member["path"] for member in
                               json.loads((self.package / "SOURCE_LOCK.json").read_bytes())["files"]}:
                self.assertNotIn(b"/Users/", raw)
                self.assertNotIn(b"authoring/", raw)


if __name__ == "__main__":
    unittest.main()
