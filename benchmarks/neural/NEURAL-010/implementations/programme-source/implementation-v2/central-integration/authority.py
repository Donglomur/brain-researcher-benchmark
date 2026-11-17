"""Concrete protected file-channel metadata admission, never a result callback.

Issuer custody and its registered source qualification are external trust anchors.
No candidate or benchmark process is allowed to write the response directory.
Ordinary uid/mode checks supplement, never establish, that isolation guarantee.
"""
import os
from pathlib import Path
import stat
import time
import uuid

KINDS = {"central_admission", "phase_admission", "phase_observation", "assessment_release"}


def directory(path, owner):
    p = u.absolute(path); fd = u.parent_fd(p)
    try:
        s = os.stat(p.name, dir_fd=fd, follow_symlinks=False)
        u.need(stat.S_ISDIR(s.st_mode) and s.st_uid == owner and s.st_mode & 0o022 == 0, "qualified ordinary protected directory")
        return u.stamp(s)
    finally: os.close(fd)


class FileAuthority:
    def __init__(self, policy, policy_pin, reader, run_nonce, binding, *, sequence=0):
        u.need(type(policy) is dict and set(policy) == {"schema", "task_id", "issuer", "issuer_source_closure", "request_root", "response_root", "response_owner_uid", "operand_roots", "max_message_bytes", "max_wait_seconds"}
               and policy["schema"] == "neural010_protected_file_authority_v1" and policy["task_id"] == "NEURAL-010", "qualified closed authority policy")
        u.need(type(policy["issuer"]) is str and policy["issuer"], "independent issuer")
        u.integer(policy["response_owner_uid"])
        u.integer(policy["max_message_bytes"], 1024)
        u.need(policy["max_message_bytes"] <= 16777216 and u.finite(policy["max_wait_seconds"]) > 0, "bounded authority messages/wait")
        u.need(type(policy["operand_roots"]) is list and 1 <= len(policy["operand_roots"]) <= 32, "finite admitted operand roots")
        for root in policy["operand_roots"]: u.absolute(root)
        self.policy, self.policy_pin, self.reader = policy, u.descriptor(policy_pin), reader
        u.integer(sequence); u.need(sequence < 32, "bounded exact integer channel sequence")
        self.nonce, self.binding, self.sequence = run_nonce, binding, sequence
        self.scientific_end = u.finite(binding["original_deadline"])
        u.need(type(run_nonce) is str and len(run_nonce) == 32, "fresh central run nonce")
        self.request_root = u.absolute(policy["request_root"]); self.response_root = u.absolute(policy["response_root"])
        u.need(self.request_root != self.response_root and not self.request_root.is_relative_to(self.response_root)
               and not self.response_root.is_relative_to(self.request_root), "separate request/issuer response custody")
        self.request_stamp = directory(str(self.request_root), os.getuid())
        self.response_stamp = directory(str(self.response_root), policy["response_owner_uid"])
        self.records = []

    def request(self, kind, payload):
        u.integer(self.sequence)
        u.need(kind in KINDS and self.sequence < 32, "finite ordered authority protocol")
        self.reader.tick(self.scientific_end); seq = self.sequence; self.sequence += 1
        request = {"schema": "neural010_operator_request_v1", "kind": kind, "sequence": seq, "run_nonce": self.nonce,
                   "policy": self.policy_pin, "binding": self.binding, "payload": payload}
        name = f"{self.nonce}-{seq:02d}-{kind}.json"
        target = self.response_root / name
        u.need(not target.exists() and not target.is_symlink(), "no preexisting/replayed issuer response")
        body = u.bounded_canonical(request, self.policy["max_message_bytes"])
        request_pin = self.reader.write_new(self.request_root / name, body, self.policy["max_message_bytes"])
        end = min(self.reader.deadline, self.scientific_end, self.reader.tick(self.scientific_end) + self.policy["max_wait_seconds"])
        while not target.exists():
            self.reader.tick(end); time.sleep(min(0.05, max(0, end - self.reader.tick(end))))
        self.reader.tick(end)
        s = target.lstat()
        u.need(s.st_uid == self.policy["response_owner_uid"] and s.st_mode & 0o022 == 0, "issuer-owned ordinary response")
        value, pin = self.reader.json(target, self.policy["max_message_bytes"])
        response_pin = {"path": str(target), **pin}
        u.need(set(value) == {"schema", "kind", "sequence", "run_nonce", "request", "policy", "binding_sha256", "issuer", "decision", "admitted"}
               and value["schema"] == "neural010_operator_response_v1" and value["kind"] == kind and type(value["sequence"]) is int and value["sequence"] == seq
               and value["run_nonce"] == self.nonce and value["request"] == request_pin and value["policy"] == self.policy_pin
               and value["binding_sha256"] == u.digest(self.binding) and value["issuer"] == self.policy["issuer"]
               and value["decision"] == "independently_approved_exact_request", "independent exact response; no stale/replayed approval")
        if kind in ("phase_admission", "assessment_release"): p.validate_phase_response(value["admitted"])
        else:
            u.need(type(value["admitted"]) is dict and set(value["admitted"]) == {"payload_sha256"}
                   and value["admitted"]["payload_sha256"] == u.digest(payload), "observation/admission binds exact payload only")
        # Namespace identity/ownership is checked, not mtime (issuer writes change it).
        now_req = directory(str(self.request_root), os.getuid()); now_res = directory(str(self.response_root), self.policy["response_owner_uid"])
        u.need(now_req[:3] == self.request_stamp[:3] and now_res[:3] == self.response_stamp[:3], "authority namespace identity unchanged")
        self.records.append({"kind": kind, "sequence": seq, "request": request_pin, "response": response_pin})
        self.reader.tick(end); return value["admitted"]
