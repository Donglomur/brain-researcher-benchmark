"""Typed stage API. A completion result is produced by code, never an input flag."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from .io import Artifact, ArtifactStore, ContractError, capture, decode, canonical, ordinary


@dataclass
class StageResult:
    outcome: str
    artifacts: dict[str, Artifact]
    measurements: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    def object(self):
        return {"outcome": self.outcome,
                "artifacts": {k: v.object() for k, v in self.artifacts.items()},
                "measurements": self.measurements, "reasons": self.reasons}


class StageContext:
    def __init__(self, stage, attempt, store, inputs, parameters, prerequisites,
                 contract, limits, operation, receipt_refs=None, qualification=None):
        self.stage, self.attempt, self.store = stage, attempt, store
        self.inputs = {k: Artifact.parse(v) for k, v in inputs.items()}
        self.parameters = parameters
        self.prerequisites = prerequisites
        self.receipt_refs = dict(receipt_refs or {})
        self.contract, self.limits, self.operation = contract, limits, operation
        self.qualification = dict(qualification or {})
        self.written = {}
        self.custody_bytes = 0
        self.store.mkdir(stage)

    def input_ref(self, name, *, roles):
        if name not in self.inputs or self.inputs[name].role not in roles:
            raise ContractError("missing/wrong-role input: " + name)
        if (self.inputs[name].role in ("query_targets", "query_private_binding")
                and self.stage not in ("E00", "E02")):
            raise ContractError("target-bearing artifact forbidden to this stage")
        return self.inputs[name]

    def read_input(self, name, *, roles, cap):
        return self.store.read_json(self.input_ref(name, roles=roles), roles=roles,
                                    cap=cap)

    def input_path(self, name, *, roles):
        """A helper must authenticate this descriptor on its same open FD."""
        return self.input_ref(name, roles=roles)

    def write_json(self, name, value, *, role, visibility="operator"):
        if name in self.written or Path(name).name != name or name.startswith("_custody_"):
            raise ContractError("unique single-component output name required")
        artifact = self.store.json(self.stage + "/" + name, value,
                                   role=role, visibility=visibility,
                                   producer=self.stage)
        self._record_written(name, artifact)
        return artifact

    def write_bytes(self, name, body, *, role, visibility="operator",
                    media_type="application/octet-stream"):
        if name in self.written or Path(name).name != name or name.startswith("_custody_"):
            raise ContractError("unique single-component output name required")
        artifact = self.store.write(self.stage + "/" + name, body,
                                    role=role, visibility=visibility,
                                    producer=self.stage, media_type=media_type)
        self._record_written(name, artifact)
        return artifact

    def record_streamed(self, name, artifact):
        """Register a same-FD hashed, byte-metered streaming writer result.

        The trusted producer must charge every raw block before writing it and
        obtain this digest from that same FD. Registration opens no body.
        """
        if name in self.written or Path(name).name != name or name.startswith("_custody_"):
            raise ContractError("unique nonreserved streamed output name required")
        artifact = Artifact.parse(artifact.object() if isinstance(artifact, Artifact) else artifact)
        path = ordinary(self.store.root / self.stage / name)
        if artifact.path != str(path) or artifact.producer != self.stage or artifact.bytes != path.stat().st_size:
            raise ContractError("streamed output must bind exact stage path, producer and size")
        self._record_written(name, artifact)
        return artifact

    def _record_written(self, name, artifact):
        # A durable descriptor survives worker failure without the parent
        # opening native/target bodies during recovery. An interrupted body
        # write without a descriptor is explicitly an unbound partial output.
        record = {"schema": "neural063_output_custody_v1", "attempt": self.attempt,
                  "stage": self.stage, "filename": name, "artifact": artifact.object()}
        size = len(canonical(record))
        if self.custody_bytes + size > self.limits["journal_bytes"] // 8:
            raise ContractError("durable output descriptors exceed reserved parent-read cap")
        self.store.json(self.stage + "/_custody_" + name + ".json", record,
                        role="output_custody_record", visibility="operator", producer=self.stage)
        self.custody_bytes += size
        self.written[name] = artifact

    def prerequisite(self, stage):
        if stage not in self.prerequisites:
            raise ContractError("undeclared prerequisite requested")
        return self.prerequisites[stage]

    def abort_for_containment(self, retained_failure=None, *, initiating_failure=None):
        """Never return through multiprocessing shutdown, even if custody fails.

        A nonblocking stderr emergency record reaches the parent's bounded
        capture when normal artifact custody fails. The original error and
        unknown counters are retained; no unresolved child is declared closed.
        """
        if self.operation != "authorized_scientific_stage":
            raise ContractError("owned escalation requires an admitted trusted worker")
        import os
        record={"schema":"neural063_owned_stage_escalation_v2","attempt":self.attempt,
                "stage":self.stage,"initiating_failure":initiating_failure,
                "retained_failure":retained_failure.object() if retained_failure else None,
                "action":"immediate_trusted_worker_exit125_parent_owned_cgroup_cleanup",
                "child_reader_closure":"unresolved_or_unknown"}
        try:
            if retained_failure is not None and not any(retained_failure.object()==a.object() for a in self.written.values()):
                raise ContractError("failure artifact lacks completed durable custody")
            self.write_json("containment_escalation.json",record,role="containment_escalation")
        except BaseException as exc:
            record['custody_error']={"type":type(exc).__name__,"message":str(exc)[:2048]}
            try:
                body=canonical(record);prefix=canonical({"emergency_record_bytes":len(body),"prefix_may_be_truncated":len(body)>16384})+body[:16384]
                os.set_blocking(2,False);os.write(2,prefix)
            except BaseException:pass  # existing claim, logs and parent closure stay authoritative
        finally:
            os._exit(125)

    def require_scientific(self):
        if self.operation != "authorized_scientific_stage":
            raise ContractError("authentic/native/model/scientific operation is not authorized")
        import time
        if (type(self.limits.get("monotonic_deadline")) not in (int,float) or
                type(self.limits.get("attempt_expires_at")) is not int or
                time.monotonic() >= self.limits["monotonic_deadline"] or
                time.time() >= self.limits["attempt_expires_at"]):
            raise ContractError("bounded admitted scientific lifetime missing or exhausted")
