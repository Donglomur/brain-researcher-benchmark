"""One generated source control for the public MEG Provider NNP policy.

The original Provider predicate and generated inspect fixture are preserved.
Only public transport/vendor sources are loaded. No daemon, image, native
process, private volume decoder or scientific workload is invoked.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import types
import unittest

METHODS = ["AbsenceAndProviderControls.test_provider_singleton_nnp_admission"]
LOG_CAP = 65536
RESULT_CAP = 16384
READ_CAP = 2097152
IMPLICIT_VENDOR_READ_RESERVATION = 95475
PINS = {'transport': {'bytes': 21160, 'sha256': '64c6687475a49cd63ff33c90640327a4f6bcd6dda3fb26818c8bc0fd13ea5b8e'}, 'vendor/SOURCE_MANIFEST.json': {'bytes': 987, 'sha256': '0b9dd9c76837a1f19033f3fb45c1beb606d3b362205b83f457bae4d6edae57a0'}, 'vendor/__init__.py': {'bytes': 110, 'sha256': '4d74f90e3eac2bdf0310923beb1ff17c72de467dcb0ff4d0f0f46f3db396b2c0'}, 'vendor/archive.py': {'bytes': 9511, 'sha256': '6fb24ac481de7bb1843eac612bfaa659e9608ad90aa9e9c9c422f80f939db0b1'}, 'vendor/bounds.py': {'bytes': 8160, 'sha256': 'b1b6e19351ef58be83f885c270d0943decb8e799570edd3f5904d9379e29b3ef'}, 'vendor/contract.py': {'bytes': 7002, 'sha256': 'fe2ad5eb9272cb1ef0651734ee885d360c1e2881da05b624fee17924e1cdd6fc'}, 'vendor/engine.py': {'bytes': 19380, 'sha256': '9f615f314c9e8a2128c70c5889f90c8a29da5dbd6c3b98aa1752c2c484f93f9d'}, 'vendor/holder.py': {'bytes': 10830, 'sha256': '67f3c5a88771b623c41497529d94bae750c2354efb50e1c9a0132734a020f68c'}, 'vendor/provider.py': {'bytes': 35391, 'sha256': '9dded7dca195f7441901939484066f40ea62cc7a7657a8107ea1f6081959b3f3'}}
EXPECTED_PUBLIC_SUCCESSORS = {'core/paired-program-v1/transport.py': {'bytes': 21160, 'sha256': '64c6687475a49cd63ff33c90640327a4f6bcd6dda3fb26818c8bc0fd13ea5b8e'}, 'core/paired-program-v1/vendor_transport/SOURCE_MANIFEST.json': {'bytes': 987, 'sha256': '0b9dd9c76837a1f19033f3fb45c1beb606d3b362205b83f457bae4d6edae57a0'}, 'core/paired-program-v1/vendor_transport/provider.py': {'bytes': 35391, 'sha256': '9dded7dca195f7441901939484066f40ea62cc7a7657a8107ea1f6081959b3f3'}}
CONTEXT = None


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def ordinary(path):
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("ordinary source and output paths required")


def public_sources():
    source = Path(__file__).absolute()
    ordinary(source)
    root = source.resolve(strict=True).parent.parent
    sources, descriptors = {}, {}
    read_reservation = IMPLICIT_VENDOR_READ_RESERVATION
    for key, expected in PINS.items():
        path = root / ("transport.py" if key == "transport" else
                       "vendor_transport/" + key.removeprefix("vendor/"))
        ordinary(path)
        read_reservation += expected["bytes"] + 1
        if read_reservation > READ_CAP:
            raise ValueError("bounded public source closure")
        with path.open("rb") as stream:
            body = stream.read(expected["bytes"] + 1)
        if pin(body) != expected:
            raise ValueError("public source pin mismatch: " + key)
        sources[key] = body
        descriptors[key] = {"path": str(path), **expected}
    return root, {"sources": descriptors}, sources, read_reservation


class AbsenceAndProviderControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        inputs, sources = CONTEXT
        cls.inputs = inputs
        module = types.ModuleType("meg_provider_nnp_public_transport")
        module.__file__ = inputs["sources"]["transport"]["path"]
        sys.modules[module.__name__] = module
        exec(compile(sources["transport"], module.__file__, "exec"), module.__dict__)
        cls.transport = module
        # Test-only expected source identities preserve the original assertion;
        # this object neither imports nor represents private qualification.
        cls.qualification = types.SimpleNamespace(
            PROVIDER_SOURCE_SUCCESSORS=copy.deepcopy(EXPECTED_PUBLIC_SUCCESSORS))

    def provider_fixture(self, provider, holder):
        """Complete generated inspect/request fields for the real pure guard."""
        resources = {"memory_bytes": 268435456, "cpu_nanos": 2000000000,
                     "pids": 32, "scratch_bytes": 8192, "max_file_bytes": 4096}
        request = {"image": "sha256:" + "a" * 64,
                   "command": ["python3", "/program/submission.py"], "resources": resources}
        holder_command = ["python3", "/control/holder.py"]
        command = holder_command if holder else request["command"]
        item = {"kind": "container", "name": "generated-holder" if holder else "generated-participant",
                "owner": "generated-source-control", "id": "c" * 64}
        mounts = {"/artifact": ("volume", "generated-artifact", True),
                  "/program": ("bind", "/generated/program", False)}
        if not holder:
            mounts["/input"] = ("bind", "/generated/input", False)
        image_env = ["PATH=/usr/bin:/bin", "SOURCE_CONTROL=generated"]
        environment = {"PATH": "/usr/bin:/bin", "SOURCE_CONTROL": "generated",
                       **provider.fixed_environment(holder)}
        value = {"Id": item["id"], "Name": "/" + item["name"], "Image": request["image"],
                 "Config": {"Image": request["image"], "User": "65534:65534",
                            "Entrypoint": [command[0]], "Cmd": command[1:],
                            "WorkingDir": "/" if holder else "/work",
                            "Env": [key + "=" + val for key, val in environment.items()],
                            "Labels": {provider.LABEL: item["owner"]}},
                 "Mounts": [], "HostConfig": {
                     "Memory": provider.HOLDER_MEMORY if holder else resources["memory_bytes"],
                     "MemorySwap": provider.HOLDER_MEMORY if holder else resources["memory_bytes"],
                     "NanoCpus": 1000000000 if holder else resources["cpu_nanos"],
                     "PidsLimit": 64 if holder else resources["pids"], "ShmSize": 16777216,
                     "NetworkMode": "none", "ReadonlyRootfs": True, "CgroupnsMode": "private",
                     "IpcMode": "private", "PidMode": "", "LogConfig": {"Type": "none"},
                     "Privileged": False, "CapAdd": None, "Devices": [], "DeviceRequests": [],
                     "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges:true"],
                     "RestartPolicy": {"Name": "no"}, "AutoRemove": False, "Init": False,
                     "Tmpfs": {"/ready": provider.READY_OPTIONS} if holder else
                               {"/work": provider.scratch_options(resources["scratch_bytes"])},
                     "Ulimits": [{"Name": "core", "Soft": 0, "Hard": 0},
                                 {"Name": "nofile", "Soft": 128, "Hard": 128},
                                 {"Name": "fsize", "Soft": 256 if holder else resources["max_file_bytes"],
                                  "Hard": 256 if holder else resources["max_file_bytes"]}]}}
        for destination, (kind, source, rw) in mounts.items():
            value["Mounts"].append({"Type": kind, "Destination": destination, "RW": rw,
                                    "Name" if kind == "volume" else "Source": source})
        return value, item, mounts, request, holder_command, image_env

    def test_provider_singleton_nnp_admission(self):
        # This is the actual transport loader and exact eight-file source guard.
        vendor = self.transport._vendor()
        provider = vendor.provider
        descriptors = self.inputs["sources"]
        identity = lambda key: {field: descriptors[key][field] for field in ("bytes", "sha256")}
        self.assertEqual(self.transport.VENDOR_PIN, identity("vendor/SOURCE_MANIFEST.json"))
        self.assertEqual(self.qualification.PROVIDER_SOURCE_SUCCESSORS, {
            "core/paired-program-v1/transport.py": identity("transport"),
            "core/paired-program-v1/vendor_transport/SOURCE_MANIFEST.json": identity("vendor/SOURCE_MANIFEST.json"),
            "core/paired-program-v1/vendor_transport/provider.py": identity("vendor/provider.py")})
        invalid = [[], ["no-new-privileges:false"], ["no-new-privileges:True"],
                   ["no-new-privileges=true"], ["label=disable"],
                   ["no-new-privileges:true", "label=disable"],
                   ["no-new-privileges", "no-new-privileges"],
                   ["no-new-privileges", "no-new-privileges:true"],
                   ["no-new-privileges:true", "unexpected=true"],
                   [False], ("no-new-privileges",), "no-new-privileges", None]
        for holder in (True, False):
            value, item, mounts, request, holder_command, image_env = self.provider_fixture(provider, holder)
            argv = provider.create_args(item, holder, mounts, request, holder_command)
            self.assertEqual(argv.count("--security-opt"), 1)
            self.assertEqual(argv[argv.index("--security-opt") + 1], "no-new-privileges")
            for option in ("no-new-privileges", "no-new-privileges:true"):
                with self.subTest(holder=holder, accepted=option):
                    observed = copy.deepcopy(value)
                    observed["HostConfig"]["SecurityOpt"] = [option]
                    self.assertIsNone(provider.admit_container(observed, item, holder, mounts,
                                      request, holder_command, image_env))
            for options in invalid:
                with self.subTest(holder=holder, refused=options):
                    observed = copy.deepcopy(value)
                    observed["HostConfig"]["SecurityOpt"] = options
                    with self.assertRaises(ValueError):
                        provider.admit_container(observed, item, holder, mounts, request,
                                                 holder_command, image_env)


class BoundedLog:
    def __init__(self, path):
        self.stream = path.open("xb")
        self.bytes_written = 0
        self.overflow = False

    def write(self, text):
        body = text.encode("utf-8")
        remaining = LOG_CAP - self.bytes_written
        self.stream.write(body[:remaining])
        self.bytes_written += min(len(body), remaining)
        self.stream.flush()
        if len(body) > remaining:
            self.overflow = True
            raise ValueError("bounded control log exceeded")
        sys.stderr.write(text)
        sys.stderr.flush()
        return len(text)

    def flush(self):
        self.stream.flush()


class Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.positive_methods = []

    def addSuccess(self, test):
        self.positive_methods.append(test.id().split(".", 1)[-1])
        super().addSuccess(test)


def main():
    global CONTEXT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=os.environ.get("ARTIFACT_DIR"))
    args = parser.parse_args()
    if not args.output:
        parser.error("--output or ARTIFACT_DIR is required")
    output = Path(args.output).absolute()
    ordinary(output)
    output = output.resolve(strict=False)
    source_root = Path(__file__).resolve(strict=True).parent.parent
    if output.exists() or not output.parent.is_dir():
        raise ValueError("fresh external control output required")
    if output.is_relative_to(source_root) or source_root.is_relative_to(output):
        raise ValueError("output must be disjoint from public implementation")
    output.mkdir(mode=0o700)
    stream = BoundedLog(output / "CONTROL.log")
    outcome = {"schema": "meg-public-provider-nnp-control/v1", "success": False,
               "expected_methods": METHODS, "count": 1, "errors": [],
               "native_or_docker_execution": False,
               "generated_observations_issue_authority": False,
               "private_volume_controls_included": False}
    try:
        _, inputs, sources, read_reservation = public_sources()
        CONTEXT = (inputs, sources)
        outcome["source_read_reservation_bytes"] = read_reservation
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(AbsenceAndProviderControls)
        roster = [test.id().split(".", 1)[-1] for test in suite]
        if roster != METHODS:
            raise ValueError("exact one-method public roster")
        result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=Result).run(suite)
        outcome.update(tests_run=result.testsRun, positive_methods=result.positive_methods,
                       failure_count=len(result.failures), error_count=len(result.errors),
                       skipped_count=len(result.skipped))
        outcome["success"] = (result.wasSuccessful() and result.testsRun == 1
                              and result.positive_methods == METHODS
                              and not result.skipped and not stream.overflow)
    except BaseException as error:
        outcome["errors"].append({"type": type(error).__name__, "message": str(error)[:1000]})
    finally:
        stream.stream.close()
        outcome.update(log_bytes=stream.bytes_written, log_truncated=stream.overflow)
        body = (json.dumps(outcome, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        if len(body) > RESULT_CAP:
            raise ValueError("bounded control result")
        with (output / "CONTROL_RESULT.json").open("xb") as target:
            target.write(body)
    print(json.dumps({"schema": outcome["schema"], "success": outcome["success"],
                      "count": 1, "tests_run": outcome.get("tests_run", 0),
                      "positive_methods": len(outcome.get("positive_methods", []))}))
    return 0 if outcome["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
