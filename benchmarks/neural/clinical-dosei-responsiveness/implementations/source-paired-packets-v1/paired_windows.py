"""Pure streaming participant projection for the adopted DoSEI source condition.

This core consumes already authenticated native rows and private source events.
It never authenticates a cohort, opens signal files, invents a person split,
renders images, or grades predictions. Those are separate driver obligations.
"""
from collections import deque
import hashlib
import hmac
import math
import struct

CONDITION = "native_marker_relative_30s_v1"
WINDOW_MS = 30000
CHANNELS = ("Intellivue/EEG_1", "Intellivue/EEG_2")
PUBLIC_FIELDS = frozenset(("schema", "condition", "case_id", "channels", "units",
    "interval_ms", "relative_time_ms", "values_uv", "observation_mask",
    "source_endpoint_mask", "coverage"))


class PacketRefusal(ValueError):
    """Invalid source envelope or incomplete stream proof; never filter a case."""


def require(condition, message):
    if not condition:
        raise PacketRefusal(message)


def opaque_case_id(secret: bytes, recording_id: str, source_row: int) -> str:
    """Stable across access modes; secret and source identity stay evaluator-side."""
    require(type(secret) is bytes and len(secret) == 32, "32-byte private key required")
    require(type(recording_id) is str and 1 <= len(recording_id) <= 9 and recording_id.isascii() and
            recording_id.isdecimal() and str(int(recording_id)) == recording_id,
            "canonical recording ID required")
    require(type(source_row) is int and 0 <= source_row < 4000000, "invalid row")
    message = f"dosei-case-v1\0{recording_id}\0{source_row}".encode("ascii")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def observe(value, quality, policy):
    """Null conversion-invalid values; preserve exact finite hardware endpoints.

    The private native projection retains every original numeric approximation.
    Public masks describe source conversion, never released offline artifacts.
    Endpoint observations stay visible and explicitly flagged; this is not a
    declaration that a saturated sample is physiologically informative.
    """
    require(type(value) is float and type(quality) is int and
            quality in policy.ALLOWED_STATUSES, "invalid numeric projection")
    if quality & (policy.BLANK | policy.MALFORMED | policy.SOURCE_NONFINITE |
                  policy.FINITE_OVERFLOW):
        require(struct.pack("<d", value) == policy.FIXED_NAN_BYTES,
                "invalid fixed-NaN projection")
    else:
        require(math.isfinite(value), "nonfinite finite-source projection")
        if quality == policy.EXACT_ENDPOINT:
            require(abs(value) == 187.5, "endpoint flag mismatch")
        elif quality == policy.OUT_OF_RANGE:
            # A just-outside exact decimal may round to the binary endpoint.
            require(abs(value) >= 187.5, "range flag mismatch")
        elif quality == policy.NONZERO_UNDERFLOW:
            require(value == 0.0, "underflow flag mismatch")
        elif quality == 0:
            require(abs(value) <= 187.5, "unflagged range violation")
    valid = policy.conversion_valid(quality)
    return value if valid else None, valid, quality == policy.EXACT_ENDPOINT


class PairedWindowBuilder:
    """Consume every row, from zero, before constructing each marker's window.

    Native rows are (source_row, calendar_ordinal_ms, eeg1, eeg2, q1, q2).
    The marker row and every row at or after its timestamp are excluded from
    the observation. Equal earlier timestamps are retained as separate rows.
    A caller must finish and authenticate the complete recording before
    publishing provisional packets. The source-specific cohort driver must
    join every source event exactly once and audit all 171 recording receipts.
    """
    def __init__(self, recording_id, secret, policy):
        opaque_case_id(secret, recording_id, 0)
        self.recording_id, self.secret, self.policy = recording_id, secret, policy
        self.next_row = 0
        self.first_time = self.previous_time = None
        self.history = deque()
        self.case_count = 0
        self.failed = False

    def consume(self, row, event=None):
        """A refused or interrupted stream is terminal; it cannot be retried.

        Earlier returned packets are provisional and must not be published if
        any later row fails. The full driver must retain an explicit failure
        receipt; a new builder is not an authorized retry of the source run.
        """
        require(not self.failed, "failed native stream cannot resume")
        try:
            return self._consume(row, event)
        except BaseException:
            self.failed = True
            raise

    def _consume(self, row, event=None):
        require(type(row) is tuple and len(row) == 6, "six-field native tuple required")
        source_row, time_ms, value1, value2, quality1, quality2 = row
        require(type(source_row) is int and source_row == self.next_row,
                "all native rows must arrive once from row zero")
        require(type(time_ms) is int and time_ms >= 0, "exact source clock required")
        if self.previous_time is not None:
            require(time_ms - self.previous_time in (0, 4),
                    "unadmitted source clock discontinuity")
        values, masks, endpoints = [], [], []
        for value, quality in ((value1, quality1), (value2, quality2)):
            observed, valid, endpoint = observe(value, quality, self.policy)
            values.append(observed); masks.append(valid); endpoints.append(endpoint)
        if self.first_time is None:
            self.first_time = time_ms
        while self.history and self.history[0][0] < time_ms - WINDOW_MS:
            self.history.popleft()
        require(len(self.history) <= 7501, "window exceeds admitted clock capacity")

        result = None
        if event is not None:
            require(type(event) is dict and event.get("schema") ==
                    "dosei_private_annotation_event_v1" and
                    event.get("visibility") == "evaluator_private" and
                    event.get("recording_id") == self.recording_id and
                    type(event.get("source_row")) is int and event["source_row"] == source_row and
                    event.get("source_event_id") == f"recording:{self.recording_id}/row:{source_row}" and
                    type(event.get("recognized_time_ms")) is int and
                    event["recognized_time_ms"] == time_ms and event.get("condition") == CONDITION,
                    "source event does not match the native marker row")
            if event.get("marker_kind") == "moaas_assessment_marker":
                target = event.get("moaas_grouped_ordinal")
                require(target is None or (type(target) is int and 1 <= target <= 5),
                        "invalid source responsiveness category")
                require(event.get("biological_person_id") is None and
                        event.get("assessment_onset_verified") is False,
                        "unadmitted person or clinical-onset assertion")
                # A source row before the marker may share its exact timestamp.
                # Time membership, not source-row position, enforces no future access.
                selected = [item for item in self.history if item[0] < time_ms]
                case_id = opaque_case_id(self.secret, self.recording_id, source_row)
                missing_prefix = max(0, min(WINDOW_MS, self.first_time - (time_ms - WINDOW_MS)))
                participant = {
                    "schema": "dosei_paired_observation_v1", "condition": CONDITION,
                    "case_id": case_id, "channels": list(CHANNELS), "units": "microvolt",
                    "interval_ms": [-WINDOW_MS, 0],
                    "relative_time_ms": [item[0] - time_ms for item in selected],
                    "values_uv": [list(item[1]) for item in selected],
                    "observation_mask": [list(item[2]) for item in selected],
                    "source_endpoint_mask": [list(item[3]) for item in selected],
                    "coverage": {"source_prefix_missing_ms": missing_prefix,
                                 "full_interval_recorded": missing_prefix == 0,
                                 "row_count": len(selected)},
                }
                require(set(participant) == PUBLIC_FIELDS, "participant allowlist changed")
                evaluator = {
                    "schema": "dosei_private_case_binding_v1", "visibility": "evaluator_private",
                    "case_id": case_id, "source_event_id": event["source_event_id"],
                    "recording_id": self.recording_id, "source_row": source_row,
                    "marker_time_ms": time_ms, "moaas_grouped_ordinal": target,
                    "source_unresolved_reason_codes": list(event["unresolved_reason_codes"]),
                    "biological_person_id": None, "split": None,
                    "canonical_scoring_admitted": False,
                    "population_disposition": "retained_without_signal_quality_filtering",
                }
                self.case_count += 1
                result = participant, evaluator
        self.history.append((time_ms, tuple(values), tuple(masks), tuple(endpoints)))
        self.previous_time = time_ms
        self.next_row += 1
        return result
