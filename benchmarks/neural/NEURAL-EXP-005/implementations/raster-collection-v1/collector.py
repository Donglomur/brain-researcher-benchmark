"""Label-free full-schedule collector for the existing Helsinki raster Session.

All objects in this module are trusted-side objects. The participant receives
only the current Session.act responses through a separately admitted transport.
This does not supply that transport, OS containment, model perception evidence,
authentic source admission, or a replacement scorer.
"""

from copy import deepcopy
import hashlib
import math
from pathlib import Path
import types

VIEWER_SHA256 = "4645cb193d1307a0a8ce7bb7c0135cc0101f65c055063608d0b304e898a569b6"
SCHEDULE_SCHEMA = "helsinki-raster-complete-schedule-v1"
COLLECTION_SCHEMA = "helsinki-raster-complete-collection-v1"
MODE = "typed_raster_viewer"
BINDING_FIELDS = frozenset(("case_id", "assessment_id", "protocol_id",
                            "representation_sha256", "fold", "input_sha256"))


class CollectionError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise CollectionError(message)


def _load_viewer():
    path = Path(__file__).resolve().parent.parent / "typed-raster-viewer-v1" / "viewer.py"
    body = path.read_bytes()
    require(hashlib.sha256(body).hexdigest() == VIEWER_SHA256,
            "accepted raster Session changed; requalification required")
    module = types.ModuleType("_helsinki_collection_bound_viewer")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


viewer = _load_viewer()
protocol = viewer._load_protocol()


def _exact(value, fields, name):
    require(type(value) is dict and set(value) == set(fields), name + ": exact fields required")


def _sha(value, name):
    require(type(value) is str and len(value) == 64 and
            all(c in "0123456789abcdef" for c in value), "invalid " + name)


def _binding(value):
    _exact(value, BINDING_FIELDS, "case binding")
    for key in ("case_id", "representation_sha256", "input_sha256"):
        _sha(value[key], key)
    require(type(value["assessment_id"]) is str and 0 < len(value["assessment_id"]) <= 256,
            "invalid assessment identity")
    require(value["protocol_id"] == protocol.PROTOCOL, "wrong source protocol")
    require(type(value["fold"]) is int and value["fold"] in range(5), "invalid source fold")


def _probability(value):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1
    except OverflowError:
        valid = False
    require(valid, "one finite probability in[0,1] required")


def _schedule(schedule):
    _exact(schedule, {"schema", "task_id", "source_reference_sha256", "protocol_source_sha256",
                      "viewer_source_sha256", "infants", "case_count", "bindings"}, "schedule")
    require(schedule["schema"] == SCHEDULE_SCHEMA and schedule["task_id"] == "NEURAL-EXP-005",
            "wrong schedule schema/task")
    _sha(schedule["source_reference_sha256"], "source reference digest")
    require(schedule["protocol_source_sha256"] == viewer.PROTOCOL_SHA256 and
            schedule["viewer_source_sha256"] == VIEWER_SHA256, "wrong frozen source versions")
    require(type(schedule["infants"]) is int and schedule["infants"] == 79,
            "original79-infant scope required")
    rows = schedule["bindings"]
    require(type(rows) is list and type(schedule["case_count"]) is int and
            schedule["case_count"] == len(rows) >= 79, "complete positive case roster required")
    seen, folds, shared = set(), set(), None
    for row in rows:
        _binding(row)
        require(row["case_id"] not in seen, "duplicate frozen case")
        seen.add(row["case_id"])
        folds.add(row["fold"])
        identity = (row["assessment_id"], row["protocol_id"], row["representation_sha256"])
        if shared is None:
            shared = identity
        require(identity == shared, "mixed assessment/protocol/representation")
    require(folds == set(range(5)), "all original five folds required")
    return rows


def freeze_reference(reference):
    """Project the trusted existing Reference schedule without reading labels.

    reference must be the operator's source-admitted existing Reference. This
    function calls only record_ids(), case_rows() and reference_sha256. Roster
    shape and hashes cannot independently authenticate biological identities,
    source completeness, or an arbitrary caller-supplied object.
    """
    ids = tuple(reference.record_ids())
    require(len(ids) == 79 and len(set(ids)) == 79, "complete source reference required")
    result = {"schema": SCHEDULE_SCHEMA, "task_id": "NEURAL-EXP-005",
              "source_reference_sha256": reference.reference_sha256,
              "protocol_source_sha256": viewer.PROTOCOL_SHA256,
              "viewer_source_sha256": VIEWER_SHA256, "infants": 79,
              "bindings": [deepcopy(row) for row in reference.case_rows()]}
    result["case_count"] = len(result["bindings"])
    _schedule(result)
    return result


def _admit_schedule(schedule, expected_sha256):
    # Snapshot first: a later caller mutation cannot alter validated content.
    frozen = deepcopy(schedule)
    _sha(expected_sha256, "protected schedule digest")
    require(protocol.digest(frozen) == expected_sha256, "schedule differs from protected commitment")
    _schedule(frozen)
    return frozen


def _row(row, expected):
    _exact(row, BINDING_FIELDS | {"probability"}, "final prediction")
    require(type(row["fold"]) is int and all(row[k] == expected[k] for k in BINDING_FIELDS),
            "wrong, repeated or out-of-order case binding")
    _probability(row["probability"])


def admit_collection(schedule, collection, *, expected_schedule_sha256,
                     expected_collection_sha256):
    """Validate the complete label-free export before passing rows to evaluate.

    This validates supplied records. It does not prove that an external model
    viewed pixels or generated the probabilities.
    """
    frozen = _admit_schedule(schedule, expected_schedule_sha256)
    value = deepcopy(collection)
    _sha(expected_collection_sha256, "protected final collection digest")
    require(protocol.digest(value) == expected_collection_sha256,
            "collection differs from protected final commitment")
    _exact(value, {"schema", "mode", "task_id", "schedule_sha256", "source_reference_sha256",
                   "case_count", "rows_sha256", "rows"}, "complete collection")
    require(value["schema"] == COLLECTION_SCHEMA and value["mode"] == MODE and
            value["task_id"] == "NEURAL-EXP-005", "wrong collection schema/mode/task")
    require(value["schedule_sha256"] == expected_schedule_sha256 and
            value["source_reference_sha256"] == frozen["source_reference_sha256"],
            "collection source/schedule mismatch")
    rows = value["rows"]
    require(type(value["case_count"]) is int and value["case_count"] == frozen["case_count"] and
            type(rows) is list and len(rows) == frozen["case_count"], "complete frozen prediction support required")
    for row, expected in zip(rows, frozen["bindings"]):
        _row(row, expected)
    _sha(value["rows_sha256"], "row commitment")
    require(protocol.digest(rows) == value["rows_sha256"], "changed final prediction rows")
    return rows


class Collector:
    """One active case at a time; no partial-complete export or case skipping.

    This in-memory operator implementation has no participant process, network,
    durable crash recovery or deployment admission. Real complete-source memory
    and runtime remain to be measured; no reduced cohort is substituted.
    """

    def __init__(self, schedule, *, expected_schedule_sha256):
        self._schedule = _admit_schedule(schedule, expected_schedule_sha256)
        self._digest = expected_schedule_sha256
        self._rows = []
        self._active = None
        self._finished = False

    def open_case(self, packet):
        """Trusted host opens only the next frozen case; return remains private."""
        require(not self._finished, "collection is finalized")
        require(self._active is None, "current case must commit before another opens")
        index = len(self._rows)
        require(index < self._schedule["case_count"], "no remaining case")
        # Reuse the accepted strict packet/clock/montage/hash/raster adapter.
        session = viewer.Session(packet, self._schedule["bindings"][index])
        self._active = session
        return session

    def commit_current(self):
        """Commit Session.finish; no candidate row injection or scoring hook."""
        require(not self._finished and self._active is not None, "no active uncommitted case")
        row = self._active.finish()  # Refuses until one final probability exists.
        _row(row, self._schedule["bindings"][len(self._rows)])
        self._rows.append(deepcopy(row))
        self._active = None
        return {"schema": "helsinki-raster-commit-receipt-v1", "case_id": row["case_id"],
                "input_sha256": row["input_sha256"], "row_sha256": protocol.digest(row)}

    def finish(self):
        """Trusted-only complete export, after the last frozen case commits."""
        require(not self._finished, "collection already exported")
        require(self._active is None and len(self._rows) == self._schedule["case_count"],
                "incomplete collection; no complete export")
        value = {"schema": COLLECTION_SCHEMA, "mode": MODE, "task_id": "NEURAL-EXP-005",
                 "schedule_sha256": self._digest,
                 "source_reference_sha256": self._schedule["source_reference_sha256"],
                 "case_count": len(self._rows), "rows": deepcopy(self._rows),
                 "rows_sha256": protocol.digest(self._rows)}
        self._finished = True
        return value
