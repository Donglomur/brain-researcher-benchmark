"""Independent commitment and completion witnesses for the existing sleep lifecycle.

This wraps, rather than reimplements, frozen-neural-lifecycle-v1. It is trusted
operator orchestration on a shared host, not a sandbox or authoring-history proof.
The original five-class scorer is unchanged and is never invoked by this module.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import os
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
COUNTS = {"development-001": 2780, "development-002": 2670}
GRAMMAR = ["prepared", "method_committed", "execution_started"] + [
    name for _ in COUNTS for name in ("case_started", "case_exited", "case_admitted")
] + ["execution_completed", "submission_frozen"]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def byte_pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def load_module(name, path, package=False):
    spec = importlib.util.spec_from_file_location(name, path,
        submodule_search_locations=[str(path.parent)] if package else None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def dependencies(lifecycle_dir=None):
    """Only independently pinned, locally reviewed source may be imported."""
    pins = json.loads((HERE / "DEPENDENCIES.json").read_text())
    programme = HERE.parent / "whole-night-programme/program"
    for name, expected in pins["reused_custody"].items():
        require(byte_pin((programme / name).read_bytes()) == expected, "Changed reused custody source")
    load_module("_sleep_audit_custody", programme / "__init__.py", package=True)
    common = load_module("_sleep_audit_custody.common", programme / "common.py")
    root = Path(lifecycle_dir or REPO / "benchmarks/shared/frozen-neural-lifecycle-v1").absolute()
    for name, expected in pins["lifecycle"].items():
        common.capture(root / name, expected)
    common.capture(HERE / "vendor/candidate_adapter.py", pins["candidate_adapter"])
    common.capture(HERE.parent / "registered-runtime/public_assets.json", pins["public_assets"])
    lifecycle = load_module("_sleep_audited_lifecycle", root / "lifecycle.py")
    adapter = load_module("_sleep_audit_candidate_adapter", HERE / "vendor/candidate_adapter.py")
    return lifecycle, common, adapter, pins


class Audit:
    def __init__(self, lifecycle_dir=None):
        self.lc, self.c, self.adapter, self.pins = dependencies(lifecycle_dir)

    def read(self, path, expected=None):
        return self.c.decode(self.c.capture(Path(path).absolute(), expected))

    def source(self):
        paths = {"audit.py": HERE / "audit.py", "DEPENDENCIES.json": HERE / "DEPENDENCIES.json"}
        return {name: self.c.pin(self.c.capture(path)) for name, path in paths.items()}

    def history(self, run):
        """Reject non-record entries, gaps, duplicates and nonmonotonic times."""
        folder = run / "events"
        require(folder.is_dir() and not folder.is_symlink(), "Ordinary event directory")
        paths = sorted(folder.iterdir())
        require(2 <= len(paths) <= len(GRAMMAR), "Bounded commitment/completion history")
        records, pins, previous, last_time = [], [], None, -1
        for index, path in enumerate(paths):
            require(path.name == f"{index:04d}.json", "Contiguous exact event filenames")
            body = self.c.capture(path)
            row = self.c.decode(body)
            require(type(row["sequence"]) is int and row["sequence"] == index and row["previous"] == previous,
                    "Exact append-only event linkage")
            require(type(row["time_ns"]) is int and row["time_ns"] >= last_time, "Ordered event timestamps")
            require(row["event"] == GRAMMAR[index], "Exact successful lifecycle stage order")
            records.append(row); pins.append(self.c.pin(body))
            previous, last_time = pins[-1]["sha256"], row["time_ns"]
        return records, pins

    def public_inputs(self, packet, engineering_control=False):
        require(packet["schema"] == "frozen_neural_lifecycle_v1" and packet["task_id"] == "NEURAL-007"
                and packet["case_order"] == list(COUNTS), "Only original sleep development roster")
        for case, count in COUNTS.items():
            row = packet["cases"][case]
            require(type(row["count"]) is int and row["count"] == count
                    and row["ids"] == [f"{case}/{i:05d}" for i in range(count)],
                    "Exact complete 5450 full-clock epoch roster")
        require(set(packet["cases"]) == set(COUNTS), "Exact two people")
        require(packet["scorer_memory_bytes"] == 4 * 1024**3, "Original grader allocation")
        if engineering_control:
            require(packet["evidence_kind"] == "generated_engineering_control", "Generated controls only")
            return
        require(packet["evidence_kind"] == "authentic_public_inputs" and packet["condition"] == "feature_programme",
                "Authentic original finite feature condition required")
        descriptor = packet["public_descriptor"]
        require({k: descriptor[k] for k in ("bytes", "sha256")} == self.pins["public_assets"],
                "Original public allowlist identity")
        public = self.read(HERE.parent / "registered-runtime/public_assets.json", self.pins["public_assets"])
        expected = {}
        for item in public["files"]:
            role, case = item["role"], item.get("case_id")
            if role.startswith("training_"):
                logical = "training/" + case + "/" + Path(item["logical_path"]).name
            elif role.startswith("development_"):
                logical = "development/" + case + "/" + Path(item["logical_path"]).name
            else:
                require(role == "common_model_reader", "Known public input role")
                logical = item["logical_path"]
            require(logical not in expected, "Unique allowlist member")
            expected[logical] = {k: item[k] for k in ("bytes", "sha256")}
        require(packet["inputs"] == expected, "Exact authentic public files; no extra or missing input")

    def state(self, run, engineering_control=False):
        rows, event_pins = self.history(run)
        packet = self.read(run / "packet.json", rows[0]["packet"])
        method = self.read(run / "method_commit.json", rows[1]["commitment"])
        self.public_inputs(packet, engineering_control)
        require(method["packet"] == rows[0]["packet"] and method["task_id"] == "NEURAL-007",
                "Method commits this exact packet")
        require(method["controller"] == self.pins["lifecycle"]["lifecycle.py"]
                and method["bootstrap"] == self.pins["lifecycle"]["candidate_entry.py"], "Reviewed lifecycle source")
        require(method["memory_bytes"] == 2 * 1024**3 and method["cpu_threads"] == 2
                and method["wall_seconds_per_person"] == 120
                and method["authoring_access"] == "policy_only_shared_host", "Exact declared execution configuration")
        require("CONFIG.json" in method["files"], "Explicit method configuration in committed bundle")
        config = self.read(run / "method/CONFIG.json", method["files"]["CONFIG.json"])
        require(type(config) is dict and config, "Nonempty explicit method configuration")
        # Reuse the runner's complete source/input inventory checks, including origin.
        self.lc.packet(run)
        self.lc.method(run)
        return rows, event_pins, packet, method

    @staticmethod
    def external(run, path, source=None):
        path = Path(os.path.abspath(path))
        run = Path(os.path.abspath(run))
        require(not any(p.is_symlink() for p in (path, *path.parents)), "Ordinary external witness path")
        require(path != run and run not in path.parents, "Witness must be held outside the attempt")
        if source is not None:
            source = Path(os.path.abspath(source))
            require(path != source and source not in path.parents, "Witness must be outside committed source")
        require(path.parent.is_dir(), "Existing external witness directory")
        return path

    def commit(self, run, source, witness, entrypoint="candidate.py", *, engineering_control=False):
        """Commit via the existing runner, then export the anchor before execution."""
        run = Path(os.path.abspath(run))
        source = Path(os.path.abspath(source))
        witness = self.external(run, witness, source)
        require(not witness.exists(), "New commitment witness only")
        self.lc.commit(run, source, entrypoint)
        rows, pins, packet, method = self.state(run, engineering_control)
        require(len(rows) == 2 and not (run / "processes").exists() and not (run / "submission.npz").exists(),
                "Witness before any candidate development execution")
        anchor = {"schema": "neural007_external_commitment_v1", "attempt": uuid.uuid4().hex,
                  "run": str(run), "created_ns": time.time_ns(), "events": pins,
                  "packet": rows[0]["packet"], "method": rows[1]["commitment"], "auditor": self.source(),
                  "lifecycle": self.pins["lifecycle"], "evidence_kind": packet["evidence_kind"],
                  "scope": "Observed source/config commitment before first candidate development dispatch; prior authoring/exposure unobserved"}
        body = self.c.encoded(anchor)
        self.c.publish(witness, body)
        return self.c.pin(body)

    def anchor(self, run, witness, expected, engineering_control=False):
        witness = self.external(run, witness)
        anchor = self.read(witness, expected)
        require(anchor["schema"] == "neural007_external_commitment_v1" and anchor["run"] == str(run)
                and anchor["auditor"] == self.source() and anchor["lifecycle"] == self.pins["lifecycle"],
                "Exact externally retained attempt/source commitment")
        rows, pins, packet, method = self.state(run, engineering_control)
        require(pins[:2] == anchor["events"] and rows[0]["packet"] == anchor["packet"]
                and rows[1]["commitment"] == anchor["method"] and packet["evidence_kind"] == anchor["evidence_kind"],
                "Unchanged committed history prefix")
        return anchor, rows, pins, packet, method

    def complete(self, run, witness, expected, final_witness, *, engineering_control=False):
        """Run the existing producers once; audit before an external completion seal."""
        run = Path(os.path.abspath(run))
        final_witness = self.external(run, final_witness)
        require(not final_witness.exists(), "New completion witness only")
        _, rows, _, _, method = self.anchor(run, witness, expected, engineering_control)
        self.external(run, final_witness, method["source_origin"])
        require(len(rows) == 2, "Execution exactly once after external commitment")
        self.lc.execute(run)
        self.lc.freeze(run)
        report = self.verify(run, witness, expected, engineering_control=engineering_control)
        receipt = {"schema": "neural007_external_completion_v1", "commitment_witness": expected,
                   "created_ns": time.time_ns(), **report}
        body = self.c.encoded(receipt)
        self.c.publish(final_witness, body)
        return self.c.pin(body)

    def verify(self, run, witness, expected, final_witness=None, final_expected=None, *, engineering_control=False):
        """Validate all joins and full numerical coverage without opening any targets."""
        import numpy as np
        run = Path(os.path.abspath(run))
        anchor, rows, pins, packet, method = self.anchor(run, witness, expected, engineering_control)
        require(len(rows) == len(GRAMMAR), "Complete terminal history required; no prefix may grade")
        require(rows[2]["commitment"] == anchor["method"] and rows[-1]["commitment"] == anchor["method"],
                "Same committed method at execution and freeze")
        require(rows[-2]["persons"] == 2 and rows[-1]["population"] == 5450
                and rows[-1]["evidence_kind"] == packet["evidence_kind"], "Complete original population")
        values, outputs = {}, {}
        for offset, (case, count) in enumerate(COUNTS.items()):
            started, exited, admitted = rows[3 + offset*3:6 + offset*3]
            require(all(r["case_id"] == case for r in (started, exited, admitted)), "Independent ordered person stages")
            require(type(started["pid"]) is int and started["pid"] > 0 and exited["pid"] == started["pid"],
                    "Same observed process identity within person")
            require(type(exited["returncode"]) is int and exited["returncode"] == 0
                    and exited["reaped"] is True and exited["remaining_group"] is False,
                    "Natural zero exit, reaping and observed process-group absence")
            elapsed = exited["elapsed_seconds"]
            require(type(elapsed) in (int, float) and math.isfinite(elapsed) and 0 <= elapsed <= method["wall_seconds_per_person"],
                    "Completed within committed person budget")
            root = run / "processes" / case
            request = self.read(root / "request.json", started["request"])
            require(request == {"task_id": "NEURAL-007", "case_id": case, "ids": packet["cases"][case]["ids"],
                "training_directory": str(root / "training"), "case_directory": str(root / "case"),
                "helpers_directory": str(root / "helpers") if any(k.startswith("helpers/") for k in packet["inputs"]) else None,
                "response": "JSON object with exactly ids and probabilities; complete person"},
                "Only training and current-person operands in exact request")
            self.lc.verify_tree(root / "source", method["files"])
            for key, prefix in (("training", "training/"), ("case", "development/" + case + "/"), ("helpers", "helpers/")):
                members = {k[len(prefix):]: v for k, v in packet["inputs"].items() if k.startswith(prefix)}
                if members:
                    self.lc.verify_tree(root / key, members)
                else:
                    require(not (root / key).exists(), "No undeclared copied input tree")
            resources = self.read(root / "resources.json", exited["resources"])
            require(resources["status"] == "admitted" and resources["memory_bytes"] == method["memory_bytes"]
                    and resources["cpu_threads_environment"] == 2
                    and resources["authoring_and_filesystem_security"] == "not_isolated", "Resource receipt joins")
            if engineering_control:
                require(resources["mode"] == "generated", "Engineering process receipt")
            else:
                require(resources["mode"] == "hard" and resources["platform"] == "linux"
                        and resources["memory_enforcement"] == "RLIMIT_AS", "Declared hard memory admission")
            for name in ("stdout", "stderr"):
                self.c.capture(root / (name + ".log"), exited[name], cap=2 * 1024**2)
            require(admitted["count"] == count and {p.name for p in (root / "output").iterdir()} == {"predictions.json"},
                    "Exactly one complete person output")
            output = root / "output/predictions.json"
            self.c.capture(output, admitted["output"], cap=2 * 1024**2)
            values[case] = self.lc.response(output, packet["cases"][case]["ids"], "NEURAL-007")
            outputs[case] = admitted["output"]
        require({p.name for p in (run / "processes").iterdir()} == set(COUNTS), "Exactly two execution directories")
        specification = self.adapter.Specification(tuple(self.adapter.Case(c, n) for c, n in COUNTS.items()), ("YASA", "RF"))
        validated = self.adapter.validate_submission(run / "submission.npz", rows[-1]["submission"], specification)
        for case in COUNTS:
            require(np.array_equal(validated["people"][case]["probabilities"], np.asarray(values[case], dtype=np.float64)),
                    "Native submission equals admitted per-person predictions")
        report = {"attempt": anchor["attempt"], "run": str(run), "events": pins, "head": pins[-1],
                  "submission": rows[-1]["submission"], "person_outputs": outputs, "epochs": 5450,
                  "people": 2, "evidence_kind": packet["evidence_kind"], "private_targets_opened": False,
                  "grade_invoked": False, "security_isolation_attested": False, "prior_authoring_history_attested": False,
                  "dependency_environment_closed": False}
        if final_witness is not None:
            require(final_expected is not None, "Externally retained completion pin required")
            final = self.read(self.external(run, final_witness), final_expected)
            require(final["schema"] == "neural007_external_completion_v1" and final["commitment_witness"] == expected
                    and {k: final[k] for k in report} == report, "Exact retained final history and artifact witness")
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lifecycle-dir")
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("commit", "complete", "verify"):
        p = sub.add_parser(action)
        p.add_argument("--run", required=True)
        p.add_argument("--witness", required=True)
        if action == "commit":
            p.add_argument("--source", required=True)
            p.add_argument("--entrypoint", default="candidate.py")
        else:
            p.add_argument("--witness-bytes", type=int, required=True)
            p.add_argument("--witness-sha256", required=True)
            p.add_argument("--final-witness", required=True)
            if action == "verify":
                p.add_argument("--final-bytes", type=int, required=True)
                p.add_argument("--final-sha256", required=True)
    args = parser.parse_args()
    audit = Audit(args.lifecycle_dir)
    if args.action == "commit":
        result = audit.commit(args.run, args.source, args.witness, args.entrypoint)
    else:
        expected = {"bytes": args.witness_bytes, "sha256": args.witness_sha256}
        if args.action == "complete":
            result = audit.complete(args.run, args.witness, expected, args.final_witness)
        else:
            result = audit.verify(args.run, args.witness, expected, args.final_witness,
                                  {"bytes": args.final_bytes, "sha256": args.final_sha256})
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
