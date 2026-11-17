"""Operator-owned explicit source selection. Candidate declarations grant no authority."""
import os
import stat
from .strict import Root, require, relative, integer

REQUIRED_CAPABILITIES = frozenset({
    "source_freeze", "original_data_lineage", "scientific_profile",
    "native_dependencies", "process_isolation", "target_barrier",
    "resource_accounting", "independent_numerics", "reference_competence",
})

class Authority:
    def __init__(self, custody, receipt_path, expected_pin, *, clock):
        require(type(custody) is Root, "held operator root required")
        self.root = custody
        self.receipt = custody.json(receipt_path, 2*1024*1024, pin=expected_pin, clock=clock)
        r = self.receipt
        require(r.get("schema")=="jaxley_operator_qualification_v1", "qualification schema")
        require(r.get("task_id")=="PAPER-paper-method-002", "task mismatch")
        require(r.get("mode")=="authentic", "engineering receipt cannot activate scientific execution")
        require(set(r.get("capabilities",{}))==REQUIRED_CAPABILITIES, "complete capability roster")
        require(r.get("source_program_sha256") and r.get("scientific_profile_sha256"), "exact source/profile binding")
        require(r.get("unresolved_required_gates")==[], "unresolved required gates")
        for key,row in r["capabilities"].items():
            require(type(row) is dict and row.get("decision")=="accepted", "unaccepted capability: "+key)
            require(type(row.get("evidence")) is list and row["evidence"], "external evidence required")
            for evidence in row["evidence"]:
                relative(evidence["path"])
                # Evidence bodies are not blindly interpreted as authority; their exact
                # identities are fixed by the separately selected root-owned receipt.
                custody.read(evidence["path"], integer(evidence["bytes"],"evidence bytes"),pin=evidence,clock=clock)
    def bind(self, source_sha, profile_sha):
        require(self.receipt["source_program_sha256"]==source_sha, "unqualified source")
        require(self.receipt["scientific_profile_sha256"]==profile_sha, "unqualified scientific profile")
    def producer(self, producer_id):
        rows=self.receipt.get("producers",{})
        require(producer_id in rows, "producer not independently qualified: "+producer_id)
        p=rows[producer_id]
        require(p.get("kind") in {"native_constructor","native_reference","candidate_method","native_exporter"}, "unknown producer kind")
        require(p.get("source") and p.get("entrypoint") and p.get("output_contract"), "incomplete concrete producer")
        require(p.get("allow_network") is False, "networked scientific producer not admitted")
        return p

