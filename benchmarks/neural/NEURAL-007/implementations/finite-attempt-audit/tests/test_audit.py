"""Full-size generated controls, not model/science/pilot executions."""
from pathlib import Path
import importlib.util
import json
import os
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sleep_attempt_audit", HERE / "audit.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

CANDIDATE = '''from pathlib import Path
import argparse, json, os
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--output');a=p.parse_args()
r=json.loads(Path(a.request).read_text())
assert not list(Path.cwd().iterdir()), 'fresh scratch'
assert set(x.name for x in Path(r['case_directory']).iterdir()) == {'public.json'}
config=json.loads((Path(__file__).parent/'CONFIG.json').read_text())
assert config['generated_control']
Path(a.output).write_text(json.dumps({'ids':r['ids'],'probabilities':[[.2]*5 for _ in r['ids']]}))
print(json.dumps({'pid':os.getpid(),'case':r['case_id']}))
'''


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.audit = module.Audit(os.environ.get("SLEEP_LIFECYCLE_DIR"))
        self.lc = self.audit.lc
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.run, self.source = self.base / "run", self.base / "source"
        self.witness, self.final = self.base / "commit.json", self.base / "complete.json"
        self.source.mkdir()
        (self.source / "candidate.py").write_text(CANDIDATE)
        (self.source / "METHOD.md").write_text("Generated constant control; no scientific method result.\n")
        (self.source / "CONFIG.json").write_text('{"generated_control": true, "seed": 0}\n')
        self.run.mkdir()
        (self.run / "events").mkdir()
        (self.run / "inputs/training").mkdir(parents=True)
        self.lc.write_json(self.run / "inputs/training/labels.json", {"generated": True})
        cases = {}
        for case, count in module.COUNTS.items():
            folder = self.run / "inputs/development" / case
            folder.mkdir(parents=True)
            self.lc.write_json(folder / "public.json", {"generated": True, "case": case})
            cases[case] = {"count": count, "ids": [f"{case}/{i:05d}" for i in range(count)]}
        packet = {"schema": "frozen_neural_lifecycle_v1", "task_id": "NEURAL-007",
                  "evidence_kind": "generated_engineering_control", "case_order": list(module.COUNTS),
                  "cases": cases, "inputs": self.lc.inventory(self.run / "inputs"),
                  "scorer_memory_bytes": 4 * 1024**3}
        self.lc.write_json(self.run / "packet.json", packet)
        self.lc.record(self.run, "prepared", packet=self.lc.pin(self.run / "packet.json"), generated=True)

    def tearDown(self):
        self.temp.cleanup()

    def commit(self):
        self.commit_pin = self.audit.commit(self.run, self.source, self.witness, engineering_control=True)

    def complete(self):
        self.commit()
        self.final_pin = self.audit.complete(self.run, self.witness, self.commit_pin, self.final, engineering_control=True)

    def verify(self, final=True):
        return self.audit.verify(self.run, self.witness, self.commit_pin,
            self.final if final else None, self.final_pin if final else None, engineering_control=True)

    def rewrite(self, index, **changes):
        """Simulate a forged but internally consistent suffix without its external pin."""
        paths = sorted((self.run / "events").iterdir())
        previous = None if index == 0 else self.lc.pin(paths[index-1])["sha256"]
        for i, path in enumerate(paths[index:], index):
            row = self.lc.read_json(path)
            if i == index:
                row.update(changes)
            row["previous"] = previous
            path.write_text(json.dumps(row))
            previous = self.lc.pin(path)["sha256"]

    def test_complete_generated_path_has_original_roster_and_no_grade(self):
        self.complete()
        report = self.verify()
        self.assertEqual(report["epochs"], 5450)
        self.assertEqual(report["people"], 2)
        self.assertEqual(len(report["events"]), 11)
        self.assertFalse(report["private_targets_opened"])
        self.assertFalse(report["grade_invoked"])
        self.assertFalse(report["security_isolation_attested"])
        self.assertFalse(report["prior_authoring_history_attested"])
        self.assertEqual(report["evidence_kind"], "generated_engineering_control")

    def test_commitment_is_required_and_external(self):
        with self.assertRaises(FileNotFoundError):
            self.audit.complete(self.run, self.witness, {"bytes": 1, "sha256": "0"*64}, self.final)
        self.assertFalse((self.run / "processes").exists())
        with self.assertRaisesRegex(ValueError, "outside"):
            self.audit.commit(self.run, self.source, self.run / "witness.json", engineering_control=True)

    def test_method_configuration_is_explicit(self):
        (self.source / "CONFIG.json").unlink()
        with self.assertRaisesRegex(ValueError, "configuration"):
            self.commit()
        self.assertFalse(self.witness.exists())
        self.assertFalse((self.run / "processes").exists())

    def test_witness_inside_method_source_refused_before_mutation_or_dispatch(self):
        other = self.base / "other"
        other.mkdir()
        aliases = [self.source / "commit.json", other / "../source/commit.json"]
        for destination in aliases:
            with self.assertRaisesRegex(ValueError, "outside committed source"):
                self.audit.commit(self.run, self.source, destination, engineering_control=True)
        with self.assertRaisesRegex(ValueError, "outside the attempt"):
            self.audit.commit(self.run, self.source, other / "../run/commit.json", engineering_control=True)
        with self.assertRaisesRegex(ValueError, "outside committed source"):
            self.audit.commit(self.run, self.source, self.source / "commit.json", engineering_control=True)
        self.assertFalse((self.run / "method_commit.json").exists())
        self.commit()
        with self.assertRaisesRegex(ValueError, "outside committed source"):
            self.audit.complete(self.run, self.witness, self.commit_pin,
                                self.source / "complete.json", engineering_control=True)
        self.assertFalse((self.run / "processes").exists())

    def test_linked_completion_parent_refused_before_dispatch(self):
        alias = self.base / "alias"
        alias.symlink_to(self.source, target_is_directory=True)
        self.commit()
        with self.assertRaisesRegex(ValueError, "Ordinary external"):
            self.audit.complete(self.run, self.witness, self.commit_pin,
                                alias / "complete.json", engineering_control=True)
        self.assertFalse((self.run / "processes").exists())

    def test_configuration_change_after_commit_refuses_first_dispatch(self):
        self.commit()
        (self.source / "CONFIG.json").write_text('{"seed":1}')
        with self.assertRaisesRegex(ValueError, "tree changed"):
            self.audit.complete(self.run, self.witness, self.commit_pin, self.final, engineering_control=True)
        self.assertFalse((self.run / "processes").exists())

    def test_method_change_after_first_development_prediction_refuses_second(self):
        origin = repr(str(self.source / "CONFIG.json"))
        (self.source / "candidate.py").write_text(CANDIDATE +
            f"\nPath({origin}).write_text('{{\"generated_control\":true,\"seed\":1}}')\n")
        self.commit()
        with self.assertRaisesRegex(ValueError, "tree changed"):
            self.audit.complete(self.run, self.witness, self.commit_pin, self.final, engineering_control=True)
        self.assertTrue((self.run / "processes/development-001/output/predictions.json").exists())
        self.assertFalse((self.run / "processes/development-002").exists())
        self.assertFalse(self.final.exists())

    def test_missing_terminal_suffix_and_middle_event_refused(self):
        self.complete()
        terminal = self.run / "events/0010.json"
        body = terminal.read_bytes(); terminal.unlink()
        with self.assertRaisesRegex(ValueError, "terminal"):
            self.verify()
        terminal.write_bytes(body)
        (self.run / "events/0006.json").unlink()
        with self.assertRaisesRegex(ValueError, "Contiguous"):
            self.verify()

    def test_valid_chain_rewrite_is_detected_by_external_completion(self):
        self.complete()
        self.rewrite(4, elapsed_seconds=0.01)
        with self.assertRaisesRegex(ValueError, "retained final"):
            self.verify()

    def test_external_commitment_replacement_refused(self):
        self.complete()
        self.witness.chmod(0o644)
        self.witness.write_text(self.witness.read_text().replace("unobserved", "observed!!"))
        with self.assertRaises(ValueError):
            self.verify()

    def test_wrong_stage_order_even_with_valid_chain_refused(self):
        self.complete()
        self.rewrite(3, event="case_admitted")
        with self.assertRaisesRegex(ValueError, "stage order"):
            self.verify(final=False)

    def test_pid_and_exit_and_source_joins(self):
        self.complete()
        self.rewrite(4, pid=1)
        with self.assertRaisesRegex(ValueError, "process identity"):
            self.verify(final=False)

    def test_incomplete_or_failed_resources_refused(self):
        self.complete()
        resource = self.run / "processes/development-001/resources.json"
        row = self.lc.read_json(resource); row["status"] = "resource_setup_failed"
        resource.write_text(json.dumps(row))
        self.rewrite(4, resources=self.lc.pin(resource))
        with self.assertRaisesRegex(ValueError, "Resource receipt"):
            self.verify(final=False)

    def test_copied_training_tree_must_match_committed_inputs(self):
        self.complete()
        p = self.run / "processes/development-001/training/labels.json"
        p.write_text('{"wrong":true}')
        with self.assertRaisesRegex(ValueError, "tree changed"):
            self.verify(final=False)

    def test_current_person_request_cannot_name_previous_person_output(self):
        self.complete()
        p = self.run / "processes/development-002/request.json"
        row = self.lc.read_json(p)
        row["case_directory"] = str(self.run / "processes/development-001/output")
        p.write_text(json.dumps(row))
        self.rewrite(6, request=self.lc.pin(p))
        with self.assertRaisesRegex(ValueError, "current-person"):
            self.verify(final=False)

    def test_native_submission_cannot_differ_from_per_person_output(self):
        self.complete()
        import numpy as np
        p = self.run / "submission.npz"
        with np.load(p, allow_pickle=False) as data:
            arrays = {k: data[k] for k in data.files}
        arrays["development-001__probabilities"][0] = [1, 0, 0, 0, 0]
        p.unlink(); np.savez(p, **arrays)
        self.rewrite(10, submission=self.lc.pin(p))
        with self.assertRaisesRegex(ValueError, "equals admitted"):
            self.verify(final=False)

    def test_duplicate_missing_foreign_or_reordered_full_clock_ids(self):
        self.complete()
        import numpy as np
        p = self.run / "submission.npz"
        original = p.read_bytes()
        for variant in ("duplicate", "missing", "foreign", "reordered"):
            p.write_bytes(original)
            with np.load(p, allow_pickle=False) as data:
                arrays = {k: data[k] for k in data.files}
            ids = arrays["development-001__epoch_id"]
            if variant == "duplicate": ids[0] = ids[1]
            elif variant == "missing": arrays["development-001__epoch_id"] = ids[:-1]
            elif variant == "foreign": ids[0] = "development-999/00000"
            else: ids[[0, 1]] = ids[[1, 0]]
            p.unlink(); np.savez(p, **arrays)
            self.rewrite(10, submission=self.lc.pin(p))
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                self.verify(final=False)

    def test_failed_candidate_never_gets_completion_and_no_resume(self):
        (self.source / "candidate.py").write_text("raise SystemExit(9)\n")
        self.commit()
        with self.assertRaises(ValueError):
            self.audit.complete(self.run, self.witness, self.commit_pin, self.final, engineering_control=True)
        self.assertFalse(self.final.exists())
        self.assertFalse((self.run / "submission.npz").exists())
        with self.assertRaises(ValueError):
            self.audit.complete(self.run, self.witness, self.commit_pin, self.final, engineering_control=True)

    def test_generated_control_cannot_pass_authentic_route(self):
        with self.assertRaisesRegex(ValueError, "Authentic"):
            self.audit.commit(self.run, self.source, self.witness)
        self.assertFalse(self.witness.exists())

    def test_wrong_packet_roster_rejected_before_dispatch(self):
        p = self.run / "packet.json"
        row = self.lc.read_json(p); row["cases"]["development-001"]["ids"][0] = "wrong"
        p.write_text(json.dumps(row)); self.rewrite(0, packet=self.lc.pin(p))
        with self.assertRaisesRegex(ValueError, "5450"):
            self.commit()

    def test_source_link_or_extra_file_after_commit_refused(self):
        self.commit()
        (self.source / "extra.py").write_text("pass")
        with self.assertRaises(ValueError):
            self.audit.complete(self.run, self.witness, self.commit_pin, self.final, engineering_control=True)
        self.assertFalse((self.run / "processes").exists())


if __name__ == "__main__":
    unittest.main()
