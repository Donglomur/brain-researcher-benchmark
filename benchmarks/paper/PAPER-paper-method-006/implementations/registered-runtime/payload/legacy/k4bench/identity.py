"""Acyclic, domain-separated execution identities (successor protocol v2).

Construction: logical plan -> producer profile -> request/dispatch/snapshot ->
manifest with profile pins -> admission receipt -> external execution selection.
Snapshots/requests/admission live outside the profile and are selected by the
external selection. None contains the hash of a descendant document.
"""
from hashlib import sha256
from .protocol import canonical, require


def identity(domain, value):
    return sha256(b"kilosort4-v2\0" + domain.encode("ascii") + b"\0" + canonical(value)).hexdigest()


def plan_core(manifest):
    require(manifest.get("identity_protocol") == "kilosort4-v2", "identity-protocol", "v2 required")
    # This single explicitly excluded field contains only descendant profile
    # pins. Every other manifest field, including the complete jobs, cases and
    # scientific scope, is bound in the immutable plan.
    return {key: value for key, value in manifest.items() if key != "producer_profiles"}


def plan_digest(manifest):
    return identity("plan-core", plan_core(manifest))


def manifest_digest(manifest):
    return identity("manifest", manifest)


def job_digest(job):
    return identity("job", job)


def profile_digest(profile):
    forbidden = {"manifest_sha256", "mount_snapshot_receipt_pin", "request_pin", "selection_pin"}
    require(not forbidden.intersection(profile), "cyclic-profile-reference", "descendant references belong in external admission")
    return identity("producer-profile", profile)


def bind_profile(manifest, job, profile):
    require(profile["plan_digest"] == plan_digest(manifest)
            and profile["job_digest"] == job_digest(job)
            and profile["job_id"] == job["id"], "profile-plan-job-mismatch", job["id"])
    return profile_digest(profile)
