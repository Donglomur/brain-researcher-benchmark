"""Concrete fresh author context and training-only tool loop."""
import json
import os
from pathlib import Path
import uuid

from .common import (AdapterError, BoundAdapter, authenticate, canonical, copy_exact,
                     digest, file_pin, json_exact, need, write_fresh)
from .process import DockerSandbox, workspace_extent
from .provider import ChatCompletionTransport


PROGRAM_ABI = """Write a Python training program, with no query access. It will run once
with /training/features.npy and /training/metadata.json available read-only,
/benchmark containing the declared benchmark source, and /work writable.
Use only this case's training information and tools. Produce /work/plan.json
in the neural053_row_plan_v1 typed row-local inference schema. No arbitrary
query callback is accepted. The program must preserve all classes/features
and may not request query values. Return exactly JSON {\"program_source\":\"...\"}.
The complete program is sealed before any numerical training input is exposed.
"""
INVESTIGATE_ABI = """Investigate only the current case's training information.
The python tool runs in a network-disabled case-only container with read-only
/training/features.npy, /training/metadata.json, and /benchmark source, plus
/work for persistent case-local artifacts. Each tool process is isolated and
fully observed. Never request queries or another case's data. When finished,
write /work/plan.json in neural053_row_plan_v1 schema and return exactly JSON
{\"plan_path\":\"plan.json\"}. This seals the final model before any query exposure.
"""


def case_key(case):
    keys = (case.get("mode"), case.get("replication"), case.get("fold_ordinal"), case.get("arm"))
    need(keys[0] in ("fixed_program", "training_investigation") and type(keys[1]) is int and keys[1] in (0, 1, 2)
         and type(keys[2]) is int and keys[2] in range(4) and keys[3] in ("neural", "ocular", "joint", "neural_availability"), "canonical author context key")
    return keys


class ProviderContextFactory(BoundAdapter):
    def __init__(self, config, budget, authorization, *, case_files):
        super().__init__(config, budget, authorization, "author_candidates")
        self.case_files = {tuple(key): json.loads(canonical(value)) for key, value in case_files.items()}
        self._used = set()

    def __call__(self, case):
        self.verify_current()
        key = case_key(case)
        need(key not in self._used and key in self.case_files, "one fresh context for each admitted case")
        self._used.add(key)
        row = self.case_files[key]
        need(set(row) == {"case_id", "arm", "training", "training_metadata"} and row["arm"] == key[3], "training-only descriptor set; no query/target operands")
        return ProviderContext(self, case, row)


class ProviderContext:
    def __init__(self, factory, case, row):
        self.factory, self.case, self.descriptors = factory, dict(case), row
        self.namespace_id = "neural053-author-" + digest({"case": list(case_key(case)),
                              "config": factory._bound_config_digest})[:32]
        self.root = Path(factory.config["workspace_root"]) / self.namespace_id
        self.root.mkdir(mode=0o700, parents=False)
        self.work = self.root / "work"; self.work.mkdir(mode=0o777); self.work.chmod(0o777)
        self.scripts = self.root / "scripts"; self.scripts.mkdir(mode=0o755)
        self.budget = factory.new_budget()
        self.provider = ChatCompletionTransport(factory.config["provider"], self.budget, self.root / "provider")
        self.docker = DockerSandbox(factory.config["sandbox"], self.budget, self.root)
        self.phase = "new"; self.program = None; self.training = None; self.source = None
        self.messages = []; self.events = []; self.tool_records = []; self.source_records = []

    def _event(self, name, **fields):
        event = {"event": name, "namespace_id": self.namespace_id, **fields,
                 "budget": self.budget.snapshot()}
        self.events.append(event)
        write_fresh(self.root / f"event-{len(self.events):04d}.json", canonical(event), self.budget)

    def seal_program(self, spec):
        need(self.case["mode"] == "fixed_program" and self.phase == "new", "fixed data-free seal must be first")
        self.messages = [{"role": "system", "content": PROGRAM_ABI},
                         {"role": "user", "content": spec if type(spec) is str else canonical(spec).decode()}]
        message, finish = self.provider.complete(self.messages, allow_tools=False)
        need(finish == "stop", "complete fixed source response")
        answer = json.loads(message["content"])
        need(set(answer) == {"program_source"} and type(answer["program_source"]) is str and answer["program_source"], "exact fixed program source")
        pin = write_fresh(self.scripts / "fixed_program.py", answer["program_source"].encode(), self.budget)
        self.source_records.append(pin)
        self.program = {"schema": "neural053_fixed_program_seal_v2", "namespace_id": self.namespace_id,
                        "source": pin, "static_spec_sha256": digest(spec),
                        "provider_transcript_sha256": digest(self.messages + [message]), "before_training_mount": True}
        self.phase = "program_sealed"
        self._event("program_sealed_before_training", seal=self.program, provider=self.provider.records[-1])
        self.budget.check_clock()
        return dict(self.program)

    def _admit_training(self, packet):
        need(self.phase in ("program_sealed", "new"), "training phase has not already opened")
        if self.case["mode"] == "fixed_program": need(self.phase == "program_sealed", "fixed source seal before training")
        staged_metadata = json_exact(self.descriptors["training_metadata"], self.budget, cap=64 * 1024 * 1024)
        need(canonical(staged_metadata) == canonical(packet), "actual packet differs from pinned staged metadata")
        self.training = self.root / "training"; self.training.mkdir(mode=0o755)
        copy_exact(self.descriptors["training"], self.training / "features.npy", self.budget)
        copy_exact(self.descriptors["training_metadata"], self.training / "metadata.json", self.budget)
        self.source = self.factory.stage_source(self.root / "benchmark", self.budget)
        self.phase = "training_admitted"
        self._event("training_admitted", training=self.descriptors, metadata_digest=digest(packet))

    def _run(self, pin):
        need(self.phase == "training_admitted", "Python tools require training admission")
        authenticate(pin, self.budget)
        self.factory.verify_staged_source(self.source, self.budget)
        result = self.docker.run_python("/scripts/" + Path(pin["path"]).name,
            mounts=[(str(self.training), "/training", True), (str(self.source), "/benchmark", True),
                    (str(self.scripts), "/scripts", True), (str(self.work), "/work", False)], work_root=self.work)
        authenticate(pin, self.budget)
        self.factory.verify_staged_source(self.source, self.budget)
        self.tool_records.append({"source": pin, "observation": result["container_observation"]})
        self._event("training_tool_completed", source=pin, observation=result["container_observation"])
        self.budget.check_clock()
        return {"stdout": result["stdout"].decode("utf-8", errors="replace"),
                "stderr": result["stderr"].decode("utf-8", errors="replace")}

    def _finish(self, packet):
        need(self.phase == "training_admitted", "final seal requires training phase")
        plan_pin = file_pin(self.work / "plan.json", self.factory.config["sandbox"]["workspace_cap_bytes"], self.budget)
        plan = json_exact(plan_pin, self.budget, cap=self.factory.config["sandbox"]["workspace_cap_bytes"])
        # Actual method parser and independent method review are parent gates.
        need(plan.get("schema") == "neural053_row_plan_v1", "typed final plan required")
        self.factory.verify_current()
        for role, filename in (("training", "features.npy"), ("training_metadata", "metadata.json")):
            authenticate({**self.descriptors[role], "path": str(self.training / filename)}, self.budget)
        for pin in self.source_records: authenticate(pin, self.budget)
        self.phase = "model_sealed"
        self._event("model_sealed_before_queries", plan_pin=plan_pin)
        result = {"plan": plan,
                "training_lineage": {"schema": "neural053_candidate_training_lineage_v2",
                    "namespace_id": self.namespace_id, "context_key": list(case_key(self.case)),
                    "training_descriptors": self.descriptors, "packet_digest": digest(packet),
                    "program_seal": self.program, "tool_source_and_observations": self.tool_records,
                    "query_access": False, "other_case_mounts": False},
                "final_source_seal": {"source_manifest_sha256": self.factory._bound_source_digest,
                    "program_sources": self.source_records, "plan_artifact": plan_pin,
                    "provider_config_sha256": digest(self.factory.config["provider"])},
                "resource_receipt": {"schema": "neural053_candidate_resource_observation_v2",
                    "budget": self.budget.snapshot(), "provider_requests": self.provider.records,
                    "owned_containers": self.docker.resources, "events": self.events,
                    "operator_independent_admission": "still_required", "scientific_qualification_conferred": False}}
        self.budget.check_clock()
        return result

    def train_fixed(self, seal, packet, X):
        need(self.case["mode"] == "fixed_program" and self.phase == "program_sealed" and
             canonical(seal) == canonical(self.program), "exact data-free fixed program seal required")
        # X is deliberately not a separate transport operand: the concrete job
        # consumes only the authenticated staged training artifact the parent used.
        self._admit_training(packet)
        self._run(self.program["source"])
        return self._finish(packet)

    def investigate(self, spec, packet, X):
        need(self.case["mode"] == "training_investigation" and self.phase == "new", "fresh investigation context")
        self._admit_training(packet)
        self.messages = [{"role": "system", "content": INVESTIGATE_ABI},
                         {"role": "user", "content": spec if type(spec) is str else canonical(spec).decode()}]
        while True:
            message, finish = self.provider.complete(self.messages, allow_tools=True)
            self.messages.append(message)
            if finish == "stop":
                answer = json.loads(message["content"])
                need(answer == {"plan_path": "plan.json"}, "only sealed case-local plan.json final path")
                return self._finish(packet)
            call = message["tool_calls"][0]; args = json.loads(call["function"]["arguments"])
            pin = write_fresh(self.scripts / f"cell-{len(self.source_records):04d}.py", args["code"].encode(), self.budget)
            self.source_records.append(pin)
            result = self._run(pin)
            self.messages.append({"role": "tool", "tool_call_id": call["id"], "content": canonical(result).decode()})

    def close(self):
        if self.phase == "closed": return
        need(all(x.get("owned_container_absent") is True for x in self.docker.resources),
             "owned container retirement unresolved; no successful context closure")
        self.budget.check_clock()
        self.phase = "closed"
        # Retain evidence/model artifacts in the operator-owned context directory;
        # no shared cleanup, namespace reuse or deletion of another job occurs.
