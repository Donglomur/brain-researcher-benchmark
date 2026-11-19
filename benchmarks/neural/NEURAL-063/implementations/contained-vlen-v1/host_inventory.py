"""NEURAL-063 surviving host inventory. Never reads scientific artifact content.

One serial operator owns this inventory outside every contained worker. A unit's
entire envelope is charged before dispatch. Only authenticated, durably closed
success may settle measured usage; failed or uncertain work keeps the full charge. The final inventory has a separate
write reserve. The enclosing native owner's final group check remains external.
"""
import hashlib
import json
import os
import math
from collections import Counter
from pathlib import Path
import re
import stat

COUNTERS = {"http_requests", "http_response_body_bytes", "http_header_reservation_bytes",
            "logical_read_bytes", "export_read_bytes", "host_write_bytes",
            "control_bytes", "closure_seconds", "worker_artifact_write_bytes", "worker_control_bytes",
            "source_setup_read_bytes"}
REASONS = {"not_attempted", "awaiting_complete_session", "global_budget_exhausted",
           "dispatch_publication_failed", "worker_failed", "oom", "timeout",
           "export_failed", "ownership_unknown", "cleanup_unknown", "scientific_refusal",
           "complete", "outer_operator_interrupted"}
ASSETS_IDENTITY = {"bytes": 1485117,
                   "sha256": "41dc23799cd96d8e9f8bf0aa0961f049187435109454a4055126d51c53f1b7d2"}
SELECTION = {"bytes": 9605316,
             "sha256": "d484ac018c7b7a0cc9ed826de5977a9ec9724a82e68126ec7e13be23507c1ab7"}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False, ensure_ascii=False) + "\n").encode()


def ordinary_directory(path):
    p = Path(path)
    need(p.is_absolute() and str(p) == os.path.normpath(str(p))
         and all(not x.is_symlink() for x in (p, *p.parents)), "ordinary canonical host directory")
    need(p.is_dir(), "existing host directory")
    return p


def exclusive_bytes(path, body):
    """Caller reserves complete requested bytes first; failed files remain."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        # One precharged control write; a short/uncertain write is failure, not retry.
        need(os.write(fd, body) == len(body), "complete precharged inventory write")
        os.fsync(fd)
        os.fchmod(fd, 0o444)
    finally:
        os.close(fd)
    parent_fd = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    return {"name": Path(path).name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}



def strict(body):
    def pairs(rows):
        value = {}
        for key, item in rows:
            need(key not in value, "duplicate custody key")
            value[key] = item
        return value
    def bad(_):
        raise ValueError("nonfinite custody value")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad)


def reserve_startup(profile, root, owner_sha256, envelope, validate_profile):
    """Root-owned admission precedes source/runtime/ASSETS startup reads."""
    validate_profile(profile)
    need(type(owner_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", owner_sha256), "startup owner")
    need(set(envelope) == COUNTERS and all(type(v) is int and v >= 0 for v in envelope.values()),
         "complete nonrefundable startup envelope")
    for key, count in envelope.items():
        ceiling = profile["global_caps"][key]
        if key in ("control_bytes", "host_write_bytes"):
            ceiling -= profile["terminal_inventory_bytes"]
        need(count <= ceiling, "startup inside protected global budget")
    need(envelope["control_bytes"] >= 8192 and envelope["host_write_bytes"] >= 8192,
         "startup publication reserved")
    path = Path(root)
    ordinary_directory(path.parent)
    need(not path.exists() and not path.is_symlink(), "one fresh startup namespace")
    path.mkdir(mode=0o700)
    value = {"schema": "neural063-startup-reservation-v1", "owner": owner_sha256,
             "envelope": dict(envelope), "no_refund": True}
    body = encoded(value)
    need(len(body) <= 8192, "bounded startup reservation")
    receipt = exclusive_bytes(path / "STARTUP.json", body)
    return {"root": str(path), "owner": owner_sha256, "envelope": dict(envelope), "receipt": receipt}


class Inventory:
    def __init__(self, assets_bytes, *, assets_identity, profile, validate_profile,
                 root, owner_sha256, startup):
        validate_profile(profile)
        need(assets_identity == ASSETS_IDENTITY and type(assets_bytes) is bytes
             and len(assets_bytes) == ASSETS_IDENTITY["bytes"]
             and hashlib.sha256(assets_bytes).hexdigest() == ASSETS_IDENTITY["sha256"],
             "exact compiled ASSETS bytes authenticated before JSON decoding")
        need(set(startup) == {"root", "owner", "envelope", "receipt"}
             and startup["root"] == str(Path(root)) and startup["owner"] == owner_sha256,
             "same durable startup reservation")
        self.root = ordinary_directory(root)
        startup_body = encoded({"schema": "neural063-startup-reservation-v1", "owner": owner_sha256,
                                "envelope": startup["envelope"], "no_refund": True})
        need(startup["receipt"] == {"name": "STARTUP.json", "bytes": len(startup_body),
             "sha256": hashlib.sha256(startup_body).hexdigest()}, "startup receipt identity")
        sp = self.root / "STARTUP.json"
        sfd = os.open(sp, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(sfd)
            body = os.read(sfd, len(startup_body) + 1)
            after, named = os.fstat(sfd), sp.lstat()
            stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                 and before.st_size == len(startup_body) and body == startup_body
                 and stamp(before) == stamp(after) == stamp(named),
                 "durable same-FD startup record before ASSETS parse")
        finally:
            os.close(sfd)
        assets_manifest = strict(assets_bytes)
        self.assets_canonical_sha256 = hashlib.sha256(encoded(assets_manifest)).hexdigest()
        need(assets_manifest.get("schema") == "neural063_versioned_range_assets_v1"
             and assets_manifest.get("selection_sha256") == SELECTION["sha256"]
             and assets_manifest.get("source_counts") == {"experiments": 1936, "mice": 107, "sessions": 703, "rois": 133066}
             and assets_manifest.get("mouse_splits") == {"fit": 73, "validation": 15, "query": 19}
             and assets_manifest.get("full_object_BLAKE2b_verified") is False,
             "authenticated compiled full-scope identity manifest")
        need(type(owner_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", owner_sha256),
             "owned operation identity")
        rows = assets_manifest["assets"]
        need(type(rows) is list and len(rows) == 1936, "complete compiled assets")
        mice = {}
        self.profile, self.owner = profile, owner_sha256
        self.planes, self.sessions, self.members = {}, {}, {}
        for row in rows:
            eid, sid, mid = (row[k] for k in ("experiment", "session", "mouse"))
            need(eid not in self.planes and row["split"] in ("fit", "validation", "query"), "unique complete plane")
            need(mice.setdefault(mid, row["split"]) == row["split"], "original mouse split consistency")
            need(all(type(x) is str and re.fullmatch(r"[0-9]{1,20}", x) for x in (eid, sid, mid)),
                 "bounded original numeric identities")
            self.planes[eid] = {"session": sid, "mouse": mid, "split": row["split"],
                                "state": "unattempted", "reason": "not_attempted", "artifact": None}
            self.sessions[sid] = {"state": "held", "reason": "awaiting_complete_session", "artifact": None}
            self.members.setdefault(sid, []).append(eid)
        need(len(self.planes) == 1936 and len(self.sessions) == 703 and len(mice) == 107
             and Counter(mice.values()) == {"fit": 73, "validation": 15, "query": 19},
             "complete original host inventory/split")
        need(all(len({self.planes[e]["mouse"] for e in es}) == 1 for es in self.members.values()),
             "one original mouse per session")
        self.spent = dict(startup["envelope"])
        self.initial_reserved_cumulative = dict(startup["envelope"])
        self.settlements = {}
        self.control_written = 0
        self.reservations = {}
        self.reservation_refs = {}
        self.unit_control_written = {}
        self.export_claims = {}
        self.active = None
        self.stopped = False
        self.finalized = False
        self.publication_failures = []
        self.terminal = profile["terminal_inventory_bytes"]
        need(self.terminal >= 8192 + 4096 * len(self.planes) + 2048 * len(self.sessions),
             "complete terminal inventory reservation")
        need(profile["global_caps"]["host_write_bytes"] >= self.terminal
             and profile["global_caps"]["control_bytes"] >= self.terminal,
             "disjoint protected terminal write/control allowance")
        self.initial_ref = self._record("INITIAL.json", {"owner": self.owner, "selection": SELECTION,
                     "assets_identity": ASSETS_IDENTITY, "planes": self.planes, "sessions": self.sessions,
                     "host_transient": "Bounded 1485117-byte assets JSON parse; no opaque scientific JSON or ROI table parse. No hard host RAM certificate.",
                     "benchmark_ready": False}, self.terminal, initial=True)

    def _record(self, name, value, limit, *, terminal=False, initial=False):
        need(re.fullmatch(r"(?:INITIAL|FINAL|(?:plane|session)-[0-9]{1,20}-(?:reservation|inputs|export|result|settlement))\.json", name),
             "finite task record namespace")
        body = encoded(value)
        need(len(body) <= limit, "bounded inventory record")
        ceiling = self.profile["global_caps"]["control_bytes"] - (0 if terminal else self.terminal)
        need(self.control_written + len(body) <= ceiling, "protected terminal control reserve")
        if initial:
            for key in ("control_bytes", "host_write_bytes"):
                need(self.spent[key] + len(body) <= self.profile["global_caps"][key] - self.terminal,
                     "initial inventory charged outside terminal reserve")
                self.spent[key] += len(body)
                self.initial_reserved_cumulative[key] += len(body)
        if not terminal and not initial:
            key = name.rsplit("-", 1)[0]
            need(key in self.reservations, "record belongs to reserved unit")
            used = self.unit_control_written.get(key, 0)
            need(used + len(body) <= self.reservations[key]["control_bytes"] // 2, "inventory half of unit control reserve")
            self.unit_control_written[key] = used + len(body)
        self.control_written += len(body)
        try:
            return exclusive_bytes(self.root / name, body)
        except BaseException:
            self.publication_failures.append(name)
            self.stopped = True
            raise

    def reserve(self, kind, identity):
        need(kind in ("plane", "session") and not self.stopped and not self.finalized
             and self.active is None, "single serial admitted unit")
        table = self.planes if kind == "plane" else self.sessions
        need(identity in table and table[identity]["artifact"] is None, "original uncompleted unit")
        key = kind + "-" + identity
        need(key not in self.reservations, "no automatic retry or reservation reset")
        if kind == "session":
            need(all(self.planes[eid]["state"] == "complete" for eid in self.members[identity]),
                 "session held until every original plane is complete")
        cap = dict(self.profile["unit_caps"][kind])
        need(set(cap) == COUNTERS, "complete unit envelope")
        for field, value in cap.items():
            ceiling = self.profile["global_caps"][field]
            if field in ("host_write_bytes", "control_bytes"):
                ceiling -= self.terminal
            if self.spent[field] + value > ceiling:
                self.stopped = True
                table[identity]["reason"] = "global_budget_exhausted"
                raise ValueError("global reservation exhausted before dispatch")
        for field, value in cap.items():
            self.spent[field] += value
            self.initial_reserved_cumulative[field] += value
        self.reservations[key] = cap
        table[identity].update(state="dispatched", reason="not_attempted")
        self.active = (kind, identity)
        record = {"owner": self.owner, "kind": kind, "identity": identity,
                  "envelope": cap, "no_refund": True, "scientific_stage": "metadata_support_only"}
        try:
            ref = self._record(key + "-reservation.json", record, 8192)
        except BaseException:
            table[identity].update(state="failed", reason="dispatch_publication_failed")
            self.active = None
            raise
        self.reservation_refs[key] = ref
        return {"kind": kind, "identity": identity, "envelope": cap,
                "reservation_sha256": ref["sha256"]}

    def session_custody(self, identity):
        need(self.active == ("session", identity), "custody only after whole-session reserve")
        rows = []
        for eid in sorted(self.members[identity]):
            saved = self.planes[eid]
            need(saved["state"] == "complete" and saved["artifact"] is not None,
                 "every original session plane complete")
            rows.append({"experiment": eid, "state": "complete", "artifact": dict(saved["artifact"])})
        value = {"owner": self.owner, "kind": "session", "identity": identity,
                 "reservation_sha256": self.reservation_refs["session-" + identity]["sha256"],
                 "plane_custody": rows}
        ref = self._record("session-" + identity + "-inputs.json", value, 8192)
        return {"value": value, "receipt": ref}

    def claim_export(self, kind, identity, *, expected, container_id, producer_receipt_sha256,
                     ownership_receipt_sha256, host_deadline_monotonic):
        need(self.active == (kind, identity), "exact active export unit")
        key = kind + "-" + identity
        need(key not in self.export_claims, "one copyout attempt, no hidden retry")
        wanted = "plane_metadata.json" if kind == "plane" else "session_support.json"
        need(type(expected) is dict and set(expected) == {"name", "bytes", "sha256"}
             and expected["name"] == wanted and type(expected["bytes"]) is int
             and 0 < expected["bytes"] <= self.profile["output_caps"][kind]
             and re.fullmatch(r"[0-9a-f]{64}", expected["sha256"]), "opaque expected output")
        need(all(type(v) is str and re.fullmatch(r"[0-9a-f]{64}", v)
                 for v in (container_id, producer_receipt_sha256, ownership_receipt_sha256)),
             "exact producer/container ownership receipts")
        need(type(host_deadline_monotonic) in (int, float) and math.isfinite(host_deadline_monotonic),
             "finite host-local deadline")
        cap = self.reservations[key]
        folder = self.root / key
        lease = {"kind": kind, "identity": identity, "container_id": container_id,
                 "output_path": str(folder / wanted), "clock_domain": "host_monotonic",
                 "host_deadline_monotonic": host_deadline_monotonic,
                 "closure_seconds": cap["closure_seconds"],
                 "export_read_bytes": cap["export_read_bytes"] - self.profile["output_caps"][kind] - 1,
                 "host_write_bytes": cap["host_write_bytes"] - cap["control_bytes"],
                 "reservation_sha256": self.reservation_refs[key]["sha256"],
                 "producer_receipt_sha256": producer_receipt_sha256,
                 "ownership_receipt_sha256": ownership_receipt_sha256,
                 "image_id": self.profile["deployment"]["image_id"], "single_export_attempt": True}
        self.export_claims[key] = {"lease": lease, "expected": dict(expected)}
        self._record(key + "-export.json", {"owner": self.owner, **self.export_claims[key]}, 8192)
        folder.mkdir(mode=0o700)
        return dict(lease)

    def finish_unit(self, kind, identity, *, artifact=None, closure=None, copyout_result=None,
                    settlement_receipt=None, failure=None):
        need(self.active == (kind, identity), "exact outstanding unit")
        table = self.planes if kind == "plane" else self.sessions
        key = kind + "-" + identity
        success = failure is None
        if success:
            claim = self.export_claims.get(key)
            need(claim is not None and artifact == claim["expected"], "same reserved expected artifact")
            lease = claim["lease"]
            required = {"producer_complete", "producer_zero_exit", "oom_absent", "timeout_absent",
                        "copyout_verified", "streams_eof", "cli_reaped", "ownership_verified",
                        "container_absence_verified"}
            need(type(closure) is dict and set(closure) == {"kind", "identity", "reservation_sha256",
                 "container_id", "producer_receipt_sha256", "ownership_receipt_sha256",
                 "export_receipt_sha256", "artifact", "proofs"}, "cross-bound closure receipt")
            need(closure["kind"] == kind and closure["identity"] == identity and closure["artifact"] == artifact
                 and all(closure[k] == lease[k] for k in ("reservation_sha256", "container_id",
                       "producer_receipt_sha256", "ownership_receipt_sha256")), "same owned original unit")
            need(type(copyout_result) is dict and copyout_result.get("verified") is True
                 and copyout_result.get("identity") == identity and copyout_result.get("artifact") == artifact
                 and copyout_result.get("container_id") == lease["container_id"]
                 and copyout_result.get("reservation_sha256") == lease["reservation_sha256"]
                 and closure["export_receipt_sha256"] == hashlib.sha256(encoded(copyout_result)).hexdigest(),
                 "same complete opaque copyout receipt")
            need(type(closure["proofs"]) is dict and set(closure["proofs"]) == required
                 and all(v is True for v in closure["proofs"].values()), "all closure observations required")
            usage = self._success_usage(kind, identity, artifact, closure, copyout_result, settlement_receipt)
            table[identity].update(state="complete", reason="complete", artifact=artifact)
        else:
            need(failure in REASONS - {"complete", "not_attempted", "awaiting_complete_session"},
                 "bounded explicit failure reason")
            table[identity].update(state="failed", reason=failure, artifact=None)
        if not success:
            if copyout_result is not None:
                need(type(copyout_result) is dict and len(encoded(copyout_result)) <= 8192
                     and copyout_result.get("identity") == identity
                     and copyout_result.get("reservation_sha256") == self.reservation_refs[key]["sha256"],
                     "bounded same-unit partial copyout evidence")
            if closure is not None:
                need(type(closure) is dict and len(encoded(closure)) <= 4096
                     and closure.get("identity") == identity and closure.get("kind") == kind,
                     "bounded same-unit unknown closure evidence")
        self.active = None
        record = {"owner": self.owner, "kind": kind, "identity": identity, "state": table[identity],
                  "closure": closure, "copyout_result": copyout_result,
                  "full_envelope_still_charged": True}
        try:
            self._record(key + "-result.json", record, 16384)
            if success:
                settlement = {"owner": self.owner, "kind": kind, "identity": identity,
                              "reservation_sha256": self.reservation_refs[key]["sha256"],
                              "initial_envelope": self.reservations[key], "retained_charge": usage,
                              "evidence": settlement_receipt, "unknown_residuals_retained": True}
                ref = self._record(key + "-settlement.json", settlement, 16384)
                # Release only after the complete settlement and result are durable.
                for field in COUNTERS:
                    self.spent[field] -= self.reservations[key][field] - usage[field]
                self.settlements[key] = ref
        except BaseException:
            table[identity].update(state="failed", reason="dispatch_publication_failed")
            raise

    def _success_usage(self, kind, identity, artifact, closure, copyout, receipt):
        key = kind + "-" + identity
        cap = self.reservations[key]
        fields = {"schema", "kind", "identity", "reservation_sha256", "container_id", "output",
                  "worker_output", "range", "session_input_bytes_read_including_EOF_probes",
                  "source_setup_read_bytes", "copyout", "controller_requested_write_bytes",
                  "controller_control_bytes", "unmeasured_residuals_stay_reserved", "receipt_hashes"}
        need(type(receipt) is dict and set(receipt) == fields and len(encoded(receipt)) <= 8192,
             "complete bounded success settlement evidence")
        need(receipt["schema"] == "neural063_unit_success_settlement_v1"
             and receipt["kind"] == kind and receipt["identity"] == identity
             and receipt["reservation_sha256"] == self.reservation_refs[key]["sha256"]
             and receipt["container_id"] == closure["container_id"] and receipt["output"] == artifact
             and receipt["copyout"] == copyout and receipt["unmeasured_residuals_stay_reserved"] is True,
             "same closed source-exclusive unit")
        hashes = receipt["receipt_hashes"]
        need(set(hashes) == {"ready", "configuration", "exit", "absence", "copyout"}
             and all(type(v) is str and re.fullmatch(r"[0-9a-f]{64}", v) for v in hashes.values())
             and hashes["ready"] == closure["producer_receipt_sha256"]
             and hashes["copyout"] == closure["export_receipt_sha256"], "complete closure evidence join")
        for usage, ceiling in ((receipt["worker_output"], cap["worker_artifact_write_bytes"]),
                               (copyout.get("write_usage"), cap["host_write_bytes"] - cap["control_bytes"])):
            need(type(usage) is dict and set(usage) == {"bytes_requested", "bytes_confirmed", "write_calls",
                 "exclusive_append_only", "same_fd_path", "fsync", "complete", "sha256"}, "writer counter provenance")
            need(all(type(usage[k]) is int for k in ("bytes_requested", "bytes_confirmed", "write_calls"))
                 and usage["bytes_confirmed"] == artifact["bytes"]
                 and artifact["bytes"] <= usage["bytes_requested"] <= ceiling and usage["write_calls"] > 0
                 and usage["sha256"] == artifact["sha256"]
                 and all(usage[k] is True for k in ("exclusive_append_only", "same_fd_path", "fsync", "complete")),
                 "confirmed complete append-only writes, not extent inference")
        controller_cap = cap["control_bytes"] - cap["control_bytes"] // 2 - 1024
        need(all(type(receipt[k]) is int and 0 <= receipt[k] <= controller_cap
                 for k in ("controller_requested_write_bytes", "controller_control_bytes")),
             "disjoint controller/control-marker reservation")
        need(type(receipt["source_setup_read_bytes"]) is int
             and 0 <= receipt["source_setup_read_bytes"] <= cap["source_setup_read_bytes"],
             "complete worker setup-read counter")
        need(receipt["controller_requested_write_bytes"] == receipt["controller_control_bytes"],
             "same complete controller/journal requested-write counter")
        inventory_prefix = self.unit_control_written.get(key)
        need(type(inventory_prefix) is int and 0 <= inventory_prefix <= cap["control_bytes"] // 2,
             "precharged inventory control-write prefix")
        # Both future inventory publications remain reserved at their full 16 KiB
        # maxima, plus the unchanged 1 KiB copyout-marker residual. A partial or
        # failed publication cannot release anything: finish_unit releases only
        # after both complete result and settlement records are durable.
        retained_control = min(cap["control_bytes"],
            receipt["controller_requested_write_bytes"] + inventory_prefix + 2 * 16384 + 1024)
        used = dict(cap)  # Worker-control, setup, closure and other residuals stay reserved.
        used["control_bytes"] = retained_control
        used["worker_artifact_write_bytes"] = receipt["worker_output"]["bytes_requested"]
        used["host_write_bytes"] = copyout["write_usage"]["bytes_requested"] + retained_control
        used["export_read_bytes"] = copyout["read_bytes"] + artifact["bytes"] + 1
        # Worker pinned reads omit fixed bootstrap and READY polling reads.
        # Their full jointly admitted envelope stays reserved; never settle it
        # from the worker-only count. Export includes the pinned exporter's
        # hard requested-read ceiling separately from observed host capture.
        if kind == "plane":
            ranges = receipt["range"]
            need(type(ranges) is dict and ranges.get("failed") is False
                 and ranges.get("request_unresolved") is False, "complete unchanged range usage")
            count = ranges["requests_admitted"]
            need(type(count) is int and count >= 0 and ranges["records_count"] == count
                 and ranges["range_receipt_bytes_reserved"] == count * 512
                 and ranges["complete_response_body_bytes_observed"] ==
                     ranges["response_body_bytes_reserved_including_failures"]
                 and re.fullmatch(r"[0-9a-f]{64}", ranges["range_records_sha256"]),
                 "all request/body receipts accounted, detailed records retained only by digest")
            used.update(http_requests=count,
                        http_response_body_bytes=ranges["response_body_bytes_reserved_including_failures"],
                        http_header_reservation_bytes=count * 32768,
                        logical_read_bytes=ranges["logical_bytes_requested"])
            need(receipt["session_input_bytes_read_including_EOF_probes"] == 0, "no session reads in plane")
        else:
            need(receipt["range"] is None, "session has no range source route")
            used.update(http_requests=0, http_response_body_bytes=0, http_header_reservation_bytes=0,
                        logical_read_bytes=receipt["session_input_bytes_read_including_EOF_probes"])
        need(all(type(v) is int and 0 <= v <= cap[k] for k, v in used.items()),
             "complete source-owned use inside original envelope")
        return used

    def finalize(self, *, interrupted=False):
        need(not self.finalized, "one protected final inventory attempt")
        self.finalized = True
        if self.active is not None:
            kind, identity = self.active
            table = self.planes if kind == "plane" else self.sessions
            table[identity].update(state="failed", reason="outer_operator_interrupted" if interrupted else "worker_failed")
            self.active = None
        for sid, row in self.sessions.items():
            if any(self.planes[eid]["state"] != "complete" for eid in self.members[sid]):
                row.update(state="held", reason="awaiting_complete_session", artifact=None)
        complete = (all(r["state"] == "complete" for r in self.planes.values())
                    and all(r["state"] == "complete" for r in self.sessions.values())
                    and not self.publication_failures and not interrupted)
        result = {"schema": "neural063_contained_inventory_v1", "owner": self.owner,
                  "selection": SELECTION, "assets_identity": ASSETS_IDENTITY,
                  "planes": self.planes, "sessions": self.sessions,
                  "charged_including_failures": self.spent, "initial_reserved_cumulative": self.initial_reserved_cumulative,
                  "settlements": self.settlements, "protected_terminal_bytes": self.terminal, "unit_attempts": len(self.reservations),
                  "publication_failures": self.publication_failures,
                  "metadata_support_complete": complete, "benchmark_ready": False,
                  "full_object_hash_verified": False, "vlen_allocation_bound": None,
                  "external_native_group_absence_and_final_publication_required": True}
        return self._record("FINAL.json", result, self.terminal, terminal=True)
