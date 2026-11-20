"""Focused generated inspect controls; no Docker, data, estimator or model calls."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("neural060_inspect_materialize", HERE / "materialize.py")
relocation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relocation)
REPOSITORY = HERE.parents[4]


def fixture():
    """Invented complete fields consumed by the actual admission function."""
    wanted = {
        "Cmd": ["python", "-I", "-B", "/work/program.py"], "User": "65534:65534",
        "WorkingDir": "/work", "Tty": False, "Labels": {"neural060.run": "generated"},
        "Env": ["OMP_NUM_THREADS=1"],
        "HostConfig": {
            "NetworkMode": "none", "ReadonlyRootfs": True, "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"], "Memory": 1048576,
            "MemorySwap": 1048576, "NanoCpus": 0, "CpuPeriod": 100000,
            "CpuQuota": 100000, "PidsLimit": 4, "Binds": ["/generated/source:/input:ro"],
            "AutoRemove": False, "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
            "Tmpfs": {"/work": "rw,noexec,nosuid,nodev,size=1048576"},
            "LogConfig": {"Type": "none", "Config": {}},
            "Ulimits": [{"Name": "core", "Soft": 0, "Hard": 0}],
        },
    }
    observed = {"Image": "sha256:" + "1" * 64,
                "Config": copy.deepcopy({k: v for k, v in wanted.items() if k != "HostConfig"}),
                "HostConfig": copy.deepcopy(wanted["HostConfig"])}
    observed["HostConfig"].update(Privileged=False, PidMode="", Devices=[], DeviceRequests=[])
    return observed, wanted


class InspectSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(prefix="neural060-inspect-source-")
        cls.addClassCleanup(temporary.cleanup)
        cls.output = Path(temporary.name).resolve() / "runtime"
        cls.receipt = relocation.materialize(str(REPOSITORY), str(cls.output))
        cls.original_root = REPOSITORY / relocation.PROGRAM
        bootstrap = relocation.captured_bootstrap(
            relocation.capture(cls.original_root / "bootstrap.py", relocation.BOOTSTRAP_PIN),
            cls.original_root / "bootstrap.py")
        cls.original = bootstrap.Sources(cls.original_root, relocation.MANIFEST_PIN)
        cls.successor = bootstrap.Sources(cls.output, cls.receipt["successor_manifest"])
        cls.old_engine = cls.original.module("engine")
        cls.new_engine = cls.successor.module("engine")

    def test_actual_predecessor_refusal_and_enabled_successor_forms(self):
        observed, wanted = fixture()
        self.old_engine.admit_configuration(observed, wanted, observed["Image"])
        for option in ("no-new-privileges", "no-new-privileges:true"):
            with self.subTest(option=option):
                observed["HostConfig"]["SecurityOpt"] = [option]
                self.new_engine.admit_configuration(observed, wanted, observed["Image"])
        with self.assertRaisesRegex(ValueError, "exact native host isolation:SecurityOpt"):
            self.old_engine.admit_configuration(observed, wanted, observed["Image"])

    def test_missing_false_duplicate_malformed_and_extra_options_refused(self):
        invalid = [None, [], "no-new-privileges:true", ("no-new-privileges:true",),
                   [True], ["no-new-privileges:false"], ["no-new-privileges:1"],
                   ["no-new-privileges=true"], ["NO-NEW-PRIVILEGES:true"],
                   ["no-new-privileges", "no-new-privileges"],
                   ["no-new-privileges:true", "no-new-privileges:true"],
                   ["no-new-privileges", "no-new-privileges:true"],
                   ["no-new-privileges:true", "no-new-privileges:false"],
                   ["no-new-privileges:true", "label=disable"],
                   ["no-new-privileges", "seccomp=unconfined"]]
        # The ':true' plus label=disable pair was observed in an actual Docker
        # inspect, SHA256 0408c22d04478876f1115bc7f5dd1832c895a126923a880d3bd2f3a2407c50d1.
        # That other runtime's label policy does not authorize it for this one.
        for options in invalid:
            with self.subTest(options=options):
                observed, wanted = fixture()
                observed["HostConfig"]["SecurityOpt"] = options
                with self.assertRaisesRegex(ValueError, "exact native host isolation:SecurityOpt"):
                    self.new_engine.admit_configuration(observed, wanted, observed["Image"])
        observed, wanted = fixture()
        del observed["HostConfig"]["SecurityOpt"]
        with self.assertRaises(KeyError):
            self.new_engine.admit_configuration(observed, wanted, observed["Image"])

    def test_other_inspection_boundaries_remain_refusals(self):
        changes = [
            ("HostConfig", "NetworkMode", "host"), ("HostConfig", "ReadonlyRootfs", False),
            ("HostConfig", "CapDrop", []), ("HostConfig", "CapDrop", ["ALL", "ALL"]),
            ("HostConfig", "Memory", 2097152), ("HostConfig", "MemorySwap", 2097152),
            ("HostConfig", "NanoCpus", False), ("HostConfig", "CpuPeriod", 99999),
            ("HostConfig", "CpuQuota", 200000), ("HostConfig", "PidsLimit", 8),
            ("HostConfig", "Binds", ["/other:/input:ro"]),
            ("HostConfig", "Binds", ["/generated/source:/other:ro"]),
            ("HostConfig", "Binds", ["/generated/source:/input:rw"]),
            ("HostConfig", "AutoRemove", True), ("HostConfig", "RestartPolicy", {"Name": "always"}),
            ("HostConfig", "Tmpfs", {}), ("HostConfig", "LogConfig", {"Type": "json-file"}),
            ("HostConfig", "Ulimits", []), ("HostConfig", "Privileged", True),
            ("HostConfig", "PidMode", "host"), ("HostConfig", "Devices", [{"PathOnHost": "/dev/mem"}]),
            ("HostConfig", "DeviceRequests", [{"Capabilities": [["gpu"]]}]),
            ("Config", "Cmd", ["sh"]), ("Config", "User", "0:0"),
            ("Config", "WorkingDir", "/"), ("Config", "Tty", True),
            ("Config", "Labels", {}), ("Config", "Env", []),
        ]
        for section, key, value in changes:
            with self.subTest(section=section, key=key, value=value):
                observed, wanted = fixture()
                observed["HostConfig"]["SecurityOpt"] = ["no-new-privileges:true"]
                observed[section][key] = value
                with self.assertRaises(ValueError):
                    self.new_engine.admit_configuration(observed, wanted, observed["Image"])
        observed, wanted = fixture()
        with self.assertRaisesRegex(ValueError, "qualified resolved image identity"):
            self.new_engine.admit_configuration(observed, wanted, "sha256:" + "2" * 64)

    def test_full_closure_identity_and_declared_changes(self):
        self.assertEqual(len(self.successor.bodies), 18)
        changed = {name for name in self.original.bodies
                   if self.original.bodies[name] != self.successor.bodies[name]}
        self.assertEqual(changed, {"bootstrap.py", "engine.py"})
        self.assertEqual(self.successor.bodies["engine.py"].replace(
            relocation.ENGINE_CHECK_AFTER, relocation.ENGINE_CHECK_BEFORE, 1),
            self.original.bodies["engine.py"])
        self.assertEqual(self.successor.bodies["bootstrap.py"].replace(
            relocation.ROSTER.encode(), relocation.OLD_ROSTER.encode(), 1),
            self.original.bodies["bootstrap.py"])
        self.assertEqual(self.receipt["inspect_compatibility"]["before"], relocation.ENGINE_PIN)
        self.assertEqual(self.receipt["inspect_compatibility"]["after"],
                         relocation.pin(self.successor.bodies["engine.py"]))
        self.assertEqual(len(self.receipt["unchanged_runtime_files"]), 16)
        self.assertEqual(self.receipt["schema"], "neural060_current_layout_source_v2")
        self.original.recheck()
        self.successor.recheck()
        print(json.dumps({"source_only": True, "successor_manifest": self.receipt["successor_manifest"],
                          "successor_engine": self.receipt["inspect_compatibility"]["after"],
                          "generated_closure_bytes": sum(p.stat().st_size for p in self.output.rglob("*") if p.is_file())},
                         sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=REPOSITORY)
    args, remaining = parser.parse_known_args()
    REPOSITORY = relocation.canonical(args.repository)
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
