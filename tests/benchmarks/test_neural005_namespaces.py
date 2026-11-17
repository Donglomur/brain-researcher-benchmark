"""Generated inspect records and a mocked Docker path; no containers or data."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "benchmarks/neural/NEURAL-005/implementations/registered-runtime/score.py"
SPEC = importlib.util.spec_from_file_location("neural005_namespace_controls", SOURCE)
score = importlib.util.module_from_spec(SPEC)
exec(compile(SOURCE.read_bytes(), str(SOURCE), "exec"), score.__dict__)


def inspection(name, mounts, environment, *, pid_mode="", ipc_mode="private"):
    """A complete generated pre-start record satisfying the other contract fields."""
    return {
        "Name": "/" + name,
        "Image": score.IMAGE,
        "Config": {
            "Image": score.IMAGE,
            "User": "65534:65534",
            "Entrypoint": ["python"],
            "Cmd": ["-I", "-B", "/source/grader.py"],
            "WorkingDir": "/tmp",
            "Tty": False,
            "OpenStdin": False,
            "Env": [key + "=" + value for key, value in environment.items()],
        },
        "HostConfig": {
            "NetworkMode": "none",
            "ReadonlyRootfs": True,
            "Privileged": False,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges:true"],
            "PidMode": pid_mode,
            "IpcMode": ipc_mode,
            "RestartPolicy": {"Name": "no"},
            "Memory": 4 * 1024**3,
            "MemorySwap": 4 * 1024**3,
            "NanoCpus": 2_000_000_000,
            "PidsLimit": 32,
            "ShmSize": 1048576,
            "Tmpfs": copy.deepcopy(score.TMPFS),
            "LogConfig": {"Type": "none", "Config": {}},
            "Ulimits": [{"Name": key, "Soft": value[0], "Hard": value[1]}
                        for key, value in score.ULIMITS.items()],
            "Mounts": [{"Type": "bind", "Source": source, "Target": target,
                        "ReadOnly": True} for target, source in mounts.items()],
        },
        "Mounts": [{"Type": "bind", "Source": source, "Destination": target,
                    "RW": False} for target, source in mounts.items()]
                  + [{"Type": "tmpfs", "Destination": "/tmp", "RW": True}],
        "State": {"Status": "created", "Running": False, "Pid": 0},
    }


class NamespaceTests(unittest.TestCase):
    def setUp(self):
        self.name = "generated-neural005"
        self.mounts = {"/source/grader.py": "/generated/grader.py",
                       "/submission/probabilities.json": "/generated/predictions.json"}
        self.environment = {"PATH": "/usr/bin"}

    def verify(self, info):
        return score.verify(info, self.name, self.mounts, self.environment)

    def test_accepts_default_isolated_pid_and_explicit_private_ipc(self):
        self.verify(inspection(self.name, self.mounts, self.environment))

    def test_refuses_shared_host_and_unrecognized_pid_namespaces(self):
        for value in ("host", "container:generated-peer", "private", "shareable",
                      "unexpected", None, False, [], {}):
            with self.subTest(pid_mode=value):
                with self.assertRaisesRegex(ValueError, "offline nonroot isolation"):
                    self.verify(inspection(self.name, self.mounts, self.environment,
                                           pid_mode=value))

    def test_refuses_shared_host_default_and_unrecognized_ipc_namespaces(self):
        for value in ("host", "container:generated-peer", "shareable", "", "none",
                      "unexpected", None, False, [], {}):
            with self.subTest(ipc_mode=value):
                with self.assertRaisesRegex(ValueError, "offline nonroot isolation"):
                    self.verify(inspection(self.name, self.mounts, self.environment,
                                           ipc_mode=value))

    def test_other_isolation_and_prestart_checks_remain_required(self):
        cases = [("HostConfig", "NetworkMode", "bridge"),
                 ("HostConfig", "ReadonlyRootfs", False),
                 ("HostConfig", "Privileged", True),
                 ("HostConfig", "Memory", 1024),
                 ("State", "Running", True),
                 ("State", "Pid", 123)]
        for section, key, value in cases:
            with self.subTest(section=section, key=key):
                info = inspection(self.name, self.mounts, self.environment)
                info[section][key] = value
                with self.assertRaises(ValueError):
                    self.verify(info)

    def run_generated_child(self, *, pid_mode="", ipc_mode="private"):
        calls = []
        with tempfile.TemporaryDirectory(prefix="neural005-namespace-") as temporary:
            root = Path(temporary).resolve()
            package = root / "source"
            package.mkdir()
            run = root / "operator"
            run.mkdir()
            submission = root / "generated-submission.json"
            submission.write_text("{}")
            (package / "grader.py").write_text("# Generated; never executed.\n")
            (package / "execution_pins.json").write_text(json.dumps({"files": []}))
            plan = {"max_submission_bytes": 1000000, "source_files": {}}
            for field in ("public_panel", "private_targets", "private_references"):
                path = root / (field + ".json")
                path.write_text('{"generated":true}')
                plan[field] = {"path": path.name, **score.lock(path)}
            (package / "operator_assets.json").write_text(json.dumps(plan))
            (run / "child_ownership.json").write_text(json.dumps({
                "pid": os.getpid(), "process_group": os.getpgrp(), "container": self.name}))
            created = False
            requested_mounts = {}
            requested_environment = {"PATH": "/usr/bin"}

            def fake_docker(args, deadline, cap=300000):
                nonlocal created
                calls.append(list(args))
                if args[:2] == ["image", "inspect"]:
                    body = [{"Id": score.IMAGE, "Config": {"Env": ["PATH=/usr/bin"]}}]
                    return {"returncode": 0, "stdout": json.dumps(body), "stderr": ""}
                if args[0] == "create":
                    created = True
                    for index, item in enumerate(args):
                        if item == "--mount":
                            fields = dict(part.split("=", 1) for part in args[index + 1].split(",")
                                          if "=" in part)
                            requested_mounts[fields["dst"]] = fields["src"]
                        if item == "--env":
                            key, value = args[index + 1].split("=", 1)
                            requested_environment[key] = value
                    return {"returncode": 0, "stdout": "generated-container-id", "stderr": ""}
                if args[:3] == ["inspect", "--type", "container"]:
                    if not created:
                        return {"returncode": 1, "stdout": "",
                                "stderr": "Error: No such object: " + self.name}
                    body = inspection(self.name, requested_mounts, requested_environment,
                                      pid_mode=pid_mode, ipc_mode=ipc_mode)
                    return {"returncode": 0, "stdout": json.dumps([body]), "stderr": ""}
                if args[:2] == ["start", "--attach"]:
                    return {"returncode": 0, "stdout": '{"status":"scored"}', "stderr": ""}
                raise AssertionError("Unexpected Docker operation: " + repr(args))

            with patch.object(score, "ROOT", root), patch.object(score, "HERE", package), \
                 patch.object(score, "docker", side_effect=fake_docker), \
                 patch.object(score, "cleanup", return_value={"absent": True}) as cleanup, \
                 patch.object(score.subprocess, "Popen", side_effect=AssertionError("No process execution")):
                score.run_child(submission, run, self.name)
                cleanup.assert_called_once()
            receipt = json.loads((run / "child_receipt.json").read_text())
        return calls, receipt

    def test_creation_requests_private_ipc_and_valid_inspection_reaches_mocked_start(self):
        calls, receipt = self.run_generated_child()
        creation = next(row for row in calls if row[0] == "create")
        self.assertEqual(creation.count("--ipc"), 1)
        self.assertEqual(creation[creation.index("--ipc") + 1], "private")
        self.assertNotIn("--pid", creation)  # Docker's default is an independent PID namespace.
        self.assertEqual(sum(row[:2] == ["start", "--attach"] for row in calls), 1)
        self.assertEqual(receipt["status"], "scored")
        self.assertFalse(receipt["candidate_code_executed"])

    def test_shared_or_unconfirmed_inspection_cannot_reach_start(self):
        for kwargs in ({"pid_mode": "container:generated-peer"},
                       {"ipc_mode": "container:generated-peer"},
                       {"ipc_mode": "shareable"}, {"ipc_mode": ""}):
            with self.subTest(**kwargs):
                calls, receipt = self.run_generated_child(**kwargs)
                self.assertFalse(any(row[0] == "start" for row in calls))
                self.assertEqual(receipt["status"], "operator_error")
                self.assertIn("offline nonroot isolation", receipt["error"])
                self.assertTrue(receipt["cleanup"]["absent"])


if __name__ == "__main__":
    unittest.main()
