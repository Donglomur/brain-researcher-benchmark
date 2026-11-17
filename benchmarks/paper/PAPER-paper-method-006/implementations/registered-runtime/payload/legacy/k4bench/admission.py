"""Closed world admission of complete source, cases, effects and exposure."""
from __future__ import annotations
from .protocol import (Rejected, require, integer, fraction, identifier, unique,
                       digest, validate_pin, relative, outcome)
from .identity import manifest_digest, plan_digest, job_digest

CANONICAL = "PAPER-paper-method-006"
CELLS = ("A-R", "B-R", "A-I", "B-I")
PROFILES = ("R_source20", "R_paper40", "I_bijective_full")
GATES = ("S01-document-body", "S01-inherited-method", *[f"S{i:02}" for i in range(2, 15)])
ROLES = {"paper", "common-observation", "common-metadata", "common-numeric-resource",
         "author-code", "author-notebook", "truth", "reference-output", "R-output",
         "grader", "source-constructor", "protected-analysis", "environment"}


def member_map(members):
    by_id = unique(members)
    for row in members:
        validate_pin(row["pin"])
        require(row["role"] in ROLES, "unknown-role", row["id"])
        require(isinstance(row.get("source_evidence"), list) and row["source_evidence"],
                "missing-source-evidence", row["id"])
        for pin in row["source_evidence"]:
            validate_pin(pin)
    paths = [x["pin"]["path"] for x in members]
    require(len(paths) == len(set(paths)), "ambiguous-member-role", "one role per physical pin")
    return by_id


def validate_case(case):
    identifier(case["id"])
    require(case["kind"] in {"hybrid", "synthetic", "biophysical", "diagnostic"},
            "unknown-case-kind", case["id"])
    require(fraction(case["duration_seconds"]) > 0, "invalid-clock", case["id"])
    integer(case["samples"], "samples", 1)
    require(fraction(case["sample_frequency_hz"]) > 0, "invalid-clock", case["id"])
    require(fraction(case["duration_seconds"]) ==
            case["samples"] / fraction(case["sample_frequency_hz"]),
            "inconsistent-clock", case["id"])
    require(case["sample_origin"] == 0, "unsupported-origin", "admit a full exact transform first")
    require(case["complete_support"] == {"first_sample": 0, "stop_sample": case["samples"]},
            "partial-support", case["id"])
    require(case["clock_transform"]["kind"] in {"identity", "every-second-sample"},
            "unadmitted-transform", case["id"])
    if case["clock_transform"]["kind"] == "every-second-sample":
        require(case["kind"] == "biophysical" and
                case["clock_transform"].get("truth_time_scale") == [1, 2]
                and case["clock_transform"].get("odd_source_events") == "exact-half-sample",
                "unadmitted-twice-speed-clock", case["id"])
    units = unique(case["unit_roles"], "unit_id")
    positive = [x for x in units.values() if x["role"] == "single-unit-target"]
    background = [x for x in units.values() if x["role"] == "MUA-generator"]
    require(all(x["role"] in {"single-unit-target", "MUA-generator", "unlabelled-natural"}
                for x in units.values()), "invalid-unit-role", case["id"])
    if case["kind"] == "hybrid":
        require(len(positive) == 100, "hybrid-roster-incomplete", case["id"])
    if case["kind"] == "synthetic":
        require(len(positive) == len(background) == 600,
                "synthetic-role-join-incomplete", case["id"])
        require(fraction(case["duration_seconds"]) == 2700,
                "simulation-cropped", case["id"])
    if case["kind"] == "biophysical":
        require(positive, "biophysical-roster-unadmitted", case["id"])
        # Caption 250 alone is not an authenticated roster; no hard-coded slicing.
    require(case["role_join_evidence"] and case["clock_evidence"],
            "missing-case-evidence", case["id"])
    for pin in case["role_join_evidence"] + case["clock_evidence"]:
        validate_pin(pin)
    require(case["signal_view_id"] and case["physical_root_id"],
            "missing-lineage", case["id"])
    return case


def packet_members(members, cell):
    """Pure view constructor; never copies a protected object into an I packet."""
    require(cell in CELLS, "invalid-cell", cell)
    allowed = {"paper", "common-observation", "common-metadata", "common-numeric-resource"}
    if cell.startswith("B"):
        allowed |= {"author-code", "author-notebook"}
    if cell.endswith("R"):
        allowed |= {"truth", "source-constructor"}
    result = []
    for member in member_map(members).values():
        if member["role"] not in allowed:
            continue
        if member["role"] in {"author-code", "author-notebook"}:
            require(member.get("screening_receipts"), "source-unscreened", member["id"])
            require(member.get("output_free") is True and member.get("contains_model") is False,
                    "author-resource-role-conflict", member["id"])
            for pin in member["screening_receipts"]:
                validate_pin(pin)
        if member["role"] == "common-numeric-resource":
            require(member.get("equal_AB_admission_receipt"),
                    "common-resource-unadmitted", member["id"])
            validate_pin(member["equal_AB_admission_receipt"])
        result.append(member)
    return sorted(result, key=lambda x: x["id"])


def validate_matched_packets(members):
    packets = {cell: packet_members(members, cell) for cell in CELLS}
    for purpose in ("R", "I"):
        a = {x["id"]: x["pin"] for x in packets[f"A-{purpose}"]}
        b = {x["id"]: x["pin"] for x in packets[f"B-{purpose}"]
             if x["role"] not in {"author-code", "author-notebook"}}
        require(a == b, "AB-input-mismatch", purpose)
    return packets


def resource_contract(value):
    for name in ("wall_seconds", "cpu_seconds", "memory_bytes", "disk_bytes",
                 "read_bytes", "write_bytes", "tmp_bytes", "log_bytes", "output_bytes",
                 "max_processes", "threads", "max_events", "max_units", "max_work",
                 "max_precision_digits"):
        integer(value[name], name, 1)
    integer(value["gpu_memory_bytes"], "GPU memory")
    require(value["scientific_workers"] == 1, "scientific-concurrency", "must be one")
    require(value["output_bytes"] + value["log_bytes"] <= value["disk_bytes"],
            "invalid-storage-reservation", "outputs and retained logs")
    require(value["tmp_bytes"] < value["memory_bytes"], "invalid-memory-reservation", "tmpfs")
    return value


def scope_inventory(catalog):
    return ({x["obligation_id"] for x in catalog["scope"]["panels"]}
            | {x["xml_id"] for x in catalog["scope"]["methods"]}
            | {x["id"] for x in catalog["supplement"]["obligations"]}
            | {"Table1", "ReportingSummary", "CompleteProducerInputs"})


def validate_manifest(manifest, catalog):
    """No I/O. Valid structure is neither scientific admission nor authority."""
    require(manifest["canonical_id"] == CANONICAL, "wrong-canonical", "manifest")
    require(manifest["profiles"] == list(PROFILES), "profile-collapse", "all three profiles")
    require(manifest["cells"] == list(CELLS), "missing-cell", "matched A/B, R/I")
    members = member_map(manifest["members"])
    validate_matched_packets(manifest["members"])
    cases = unique(manifest["cases"])
    for case in cases.values():
        validate_case(case)
        require(all(i in members for i in case["member_ids"]), "unknown-case-member", case["id"])
    for kind, expected in (("hybrid", 3), ("synthetic", 6), ("biophysical", 2)):
        require(sum(c["kind"] == kind for c in cases.values()) == expected,
                "incomplete-core-cases", kind)
    require({c.get("condition") for c in cases.values() if c["kind"] == "synthetic"}
            == set(catalog["scope"]["cohorts"]["drift_simulations"]["names"]),
            "missing-simulation-condition", "six complete conditions")
    require(manifest["I_query_ids"] and set(manifest["I_query_ids"]) == set(cases),
            "incomplete-I-query-roots", "core plus every diagnostic root")
    require(manifest["query_root_join_evidence"], "unclosed-J_I", "full lineage join")
    for pin in manifest["query_root_join_evidence"]:
        validate_pin(pin)
    coverage = unique(manifest["coverage"], "obligation_id")
    require(set(coverage) == scope_inventory(catalog), "scope-loss", "complete obligations")
    jobs = unique(manifest["jobs"])
    for job in jobs.values():
        require(job["family"] in {f"G{x:02}" for x in range(1, 23)}, "unknown-family", job["id"])
        resource_contract(job["resources"])
        require(set(job["depends_on"]) <= set(jobs), "unknown-dependency", job["id"])
        require(job["id"] not in job["depends_on"], "self-dependency", job["id"])
        require(job["producer_id"] in manifest["producer_profiles"], "missing-producer", job["id"])
        require(set(job["input_member_ids"]) <= set(members), "unknown-input", job["id"])
        require(job["profile"] in PROFILES, "unknown-profile", job["id"])
    require({x["family"] for x in jobs.values()} == {f"G{x:02}" for x in range(1, 23)},
            "missing-job-family", "full G01-G22 graph")
    for row in coverage.values():
        require(row["job_ids"] and set(row["job_ids"]) <= set(jobs),
                "unimplemented-obligation", row["obligation_id"])
        require(row["constructor_profile_pin"], "undefined-constructor", row["obligation_id"])
        validate_pin(row["constructor_profile_pin"])
    # Topological order also proves no cycle; no dependency is treated as optional.
    ready, done = [], set()
    while len(done) < len(jobs):
        batch = sorted(j for j, row in jobs.items()
                       if j not in done and set(row["depends_on"]) <= done)
        require(batch, "cyclic-job-graph", "dependencies")
        ready.extend(batch)
        done.update(batch)
    return {"schema": "kilosort4_structural_admission_v1", "status": "structure-valid",
            "manifest_digest": manifest_digest(manifest), "order": ready,
            "scientific_admitted": False, "native_qualified": False,
            "I_query_count": len(cases), "scope_count": len(coverage)}


class Authority:
    """Trusted-host selection boundary. Exact acceptance pins are necessary,
    not proofs that the original science succeeds. The source-build selection
    deliberately fails this interface's scientific-execution purpose check.
    """
    def __init__(self, store, selection_pin):
        self.store = store
        self.selection_pin = validate_pin(selection_pin)
        self.selection = store.json(selection_pin, 1024 * 1024)
        require(self.selection.get("purpose") == "scientific-execution",
                "execution-not-selected", "this build is source-only")
        require(self.selection.get("canonical_id") == CANONICAL,
                "wrong-canonical", "execution selection")
        require(self.selection.get("scoped_job_ids"), "unbounded-authority", "job IDs")
        self.admission = store.json(self.selection["admission_receipt_pin"], 4 * 1024 * 1024)
        require(self.admission["manifest_digest"] == self.selection["manifest_digest"],
                "authority-manifest-mismatch", "admission receipt")
        self.closed = unique(self.admission["gate_receipts"], "gate")

    def permit(self, manifest, job):
        require(manifest_digest(manifest) == self.selection["manifest_digest"],
                "authority-manifest-mismatch", "execution")
        require(job["id"] in self.selection["scoped_job_ids"],
                "job-not-selected", job["id"])
        selected_job = next((x for x in manifest["jobs"] if x["id"] == job["id"]), None)
        require(selected_job is not None and digest(selected_job) == digest(job),
                "job-mutated-after-selection", job["id"])
        for gate in job["required_gates"]:
            receipt = self.closed.get(gate)
            require(receipt is not None and receipt["status"] == "admitted"
                    and receipt["evidence_pins"], "required-unscorable", gate)
            for pin in receipt["evidence_pins"]:
                self.store.read(validate_pin(pin))
        require(self.admission["isolation_qualification_pin"],
                "isolation-unqualified", job["id"])
        return {"selection_pin": self.selection_pin,
                "admission_receipt_pin": self.selection["admission_receipt_pin"],
                "job_id": job["id"], "job_digest": job_digest(job),
                "manifest_digest": manifest_digest(manifest), "plan_digest": plan_digest(manifest)}
