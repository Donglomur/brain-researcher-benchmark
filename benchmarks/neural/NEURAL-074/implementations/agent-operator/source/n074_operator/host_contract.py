"""Exact ABI for a separately selected fresh native owner; no backend lives here.

All names/metadata are operator-authored. A submitted programme never supplies
an admission or receipt. Source presence is not native qualification. The owner
must authenticate every Carrier and enforce isolation/lifetime/resource bounds.
"""
from dataclasses import dataclass
from .owned_io import Pin


@dataclass(frozen=True)
class Carrier:
    root: str                 # canonical absolute, private operator-owned directory
    path: str                 # canonical relative path under root, no symlinks
    pin: Pin                  # exact bounded ordinary bytes


@dataclass(frozen=True)
class Programme:
    programme: Carrier        # fixed UTF-8 Python entry, read-only /program/program.py
    method: Carrier           # fixed UTF-8 declaration, unavailable to candidate
    identity: str             # sha256 canonical identity of both carriers' content pins


@dataclass(frozen=True)
class HostPolicy:
    identity: str             # independently selected policy identity, not candidate input
    owner_source_identity: str
    image_identity: str       # immutable digest, never a mutable tag or candidate choice
    qualification_identity: str  # actual independent native qualification; no prospective success
    wall_seconds: int
    cleanup_seconds: int
    cpu_millis: int
    memory_bytes: int
    pids: int
    threads: int
    maximum_input_bytes: int
    maximum_output_bytes: int
    maximum_programme_bytes: int
    maximum_method_bytes: int
    maximum_log_bytes: int
    maximum_metadata_bytes: int


@dataclass(frozen=True)
class OwnerAdmission:
    policy_identity: str
    owner_source_identity: str
    image_identity: str
    qualification_identity: str


@dataclass(frozen=True)
class FoldRequest:
    identity: str             # sha256 of selected full-panel/fold/input manifest identity
    selection_identity: str
    held_person: str
    held_family: str
    programme_identity: str
    input_root: str            # only current-fold public inputs; RO /input
    input_manifest: Pin       # fold.json; all other admitted files named/pinned in inputs
    inputs: tuple             # exact tuple[(relative path, Pin)]; includes fold.json
    output_root: str           # selected ABSENT path; owner creates fresh private directory
    query_endpoints: tuple     # exact output row order, never target source identities
    map_length: int            # independently selected support geometry; dtype <f8


@dataclass(frozen=True)
class OwnerReceipt:
    request_identity: str
    programme_identity: str
    policy_identity: str
    context_identity: str      # fresh unique owned context; cannot repeat across folds
    owner_source_identity: str
    image_identity: str
    qualification_identity: str
    input_manifest: Pin
    output_root: str
    producers_closed: bool    # true only after complete owned cleanup/reaping
    all_owned_absent: bool    # no surviving candidate/container/process group/mount
    status: str               # completed | candidate_failed | timed_out | invalid_output
    reason: str | None
    output: Pin | None         # only predictions.f64, <f8 C row-major; no header/trailer
    evidence: Carrier          # immutable actual owner evidence, separate from candidate output


class MissingNativeOwner(RuntimeError):
    pass


class UnissuedNativeOwner:
    def authenticate_selected_owner(self):
        raise MissingNativeOwner('A separately selected and qualified native owner is required')

    def run_fresh(self, programme, request, policy):
        raise MissingNativeOwner('No native owner implementation has been selected')
