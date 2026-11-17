"""Strict packet/report metadata and bounded event publication; no file I/O."""
import hashlib
import json
import math
import numbers
import re
from .budget import require

METRICS = ("corrected_mi", "mi", "trial_null", "shift_null", "early_mi",
           "late_mi", "theta_power", "gamma_power", "firing_rate",
           "harmonic_plv", "waveform_asymmetry")
DESIGNS = ("count_only", "nuisance_matched")
CONTRASTS = ("load3_minus_load1_correct", "correct_minus_incorrect_within_load")
LINEAGE = frozenset(("packet", "source", "environment", "reference_source", "protocol"))
ID = re.compile(r"[0-9a-f]{24}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
REFERENCE = "R2"


def opaque(value, budget):
    require(type(value) is str and ID.fullmatch(value) is not None, "opaque_id", budget)
    return value


def lineage_valid(value, budget):
    require(type(value) is dict and set(value) == LINEAGE, "lineage_fields", budget)
    for key, pin in value.items():
        require(type(pin) is dict and set(pin) == {"bytes", "sha256"}
                and type(pin["bytes"]) is int and pin["bytes"] >= 0
                and type(pin["sha256"]) is str and SHA.fullmatch(pin["sha256"]) is not None,
                "typed_lineage_pin", budget)


def canonical_bytes(value, budget, capacity, *, reserve=True):
    require(type(capacity) is int and capacity > 0, "encoding_capacity", budget)
    if reserve:
        budget.reserve("serialized_bytes", capacity)
    with budget.live(4 * capacity):
        chunks, used = [], 0
        encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=True, allow_nan=False)
        for chunk in encoder.iterencode(value):
            raw = chunk.encode("ascii")
            used += len(raw)
            require(used <= capacity, "canonical_encoding_capacity", budget)
            chunks.append(raw)
        budget.tick()
        return b"".join(chunks)


class EventSlot:
    """Reserve before building the event payload. Owner persists before resuming."""
    def __init__(self, world, person, kind, lineage, budget, payload_capacity):
        self.budget = budget
        self.capacity = payload_capacity + 16384
        self.world, self.person, self.kind, self.lineage = world, person, kind, lineage
        budget.reserve("events", 1)
        budget.reserve("serialized_bytes", self.capacity)
        # Covers dictionaries/strings as a declared peak, not measured Python RSS.
        budget.reserve("live_bytes", 8 * self.capacity)

    def finish(self, payload):
        b = self.budget
        copied = {k: {"bytes": p["bytes"], "sha256": p["sha256"]}
                  for k, p in self.lineage.items()}
        event = {"schema": "neural042_reference_event_v1", "reference": REFERENCE,
                 "world": self.world, "person": self.person, "kind": self.kind,
                 "payload": payload, "lineage": copied, "budget": b.snapshot()}
        canonical_bytes(event, b, self.capacity, reserve=False)
        return event


def seed(identity, budget):
    budget.reserve("serialized_bytes", len(identity) * 4 + 64)
    raw = ("neural042-v1:" + identity).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def state_copy(generator, budget):
    # PCG64's fixed scalar schema; no array or foreign generator state is accepted.
    budget.reserve("serialized_bytes", 2048)
    state = generator.bit_generator.state
    require(type(state) is dict and state.get("bit_generator") == "PCG64",
            "declared_PCG64", budget)
    return json.loads(canonical_bytes(state, budget, 2048, reserve=False))


def packet_metadata(packet, budget):
    import numpy as np
    require(type(packet) is dict and set(packet) ==
            {"schema", "world", "person", "sessions", "channels", "lineage"},
            "packet_fields", budget)
    require(packet["schema"] == "neural042_reference_person_v1"
            and packet["world"] in ("O", "D"), "packet_profile_world", budget)
    opaque(packet["person"], budget)
    lineage_valid(packet["lineage"], budget)
    sessions, channels = packet["sessions"], packet["channels"]
    require(type(sessions) is list and len(sessions) <= 44 and type(channels) is list,
            "session_channel_lists", budget)
    budget.reserve("elements", 32 * (len(sessions) + len(channels) + 1))
    budget.reserve("serialized_bytes", 4096 + 2048 * (len(sessions) + len(channels)))
    for s in sessions:
        opaque(s, budget)
    require(sessions == sorted(set(sessions)), "sorted_unique_sessions", budget)
    ids = []
    seen_trial = {}
    for c in channels:
        require(type(c) is dict and set(c) ==
                {"id", "session", "lfp", "rates", "loads", "correct", "probe", "order", "ids"},
                "channel_fields", budget)
        opaque(c["id"], budget)
        require(c["session"] in sessions, "channel_session_membership", budget)
        require(type(c["ids"]) is list and len(c["ids"]) <= 140, "trial_ids", budget)
        ids.append(c["id"])
        n = len(c["ids"])
        budget.reserve("elements", 32 * (n + 1))
        budget.reserve("serialized_bytes", 1024 + 512 * n)
        for key in ("loads", "correct", "probe", "order"):
            require(type(c[key]) is list or (type(c[key]) is np.ndarray
                    and c[key].ndim == 1 and c[key].dtype.kind in "iu"),
                    "primitive_metadata_vector", budget)
            try:
                length = len(c[key])
            except (TypeError, AttributeError):
                budget.fail("metadata_vector_length")
            require(length == n, "metadata_vector_length", budget)
        require(len(set(c["ids"])) == n, "unique_channel_trials", budget)
        orders = []
        for i, tid in enumerate(c["ids"]):
            opaque(tid, budget)
            vals = []
            for key, allowed in (("loads", {1, 3}), ("correct", {0, 1}),
                                 ("probe", {0, 1}), ("order", set(range(140)))):
                v = c[key][i]
                require(isinstance(v, numbers.Integral) and type(v) is not bool
                        and type(v).__name__ != "bool_" and int(v) in allowed,
                        "metadata_integer_value", budget)
                vals.append(int(v))
            orders.append(vals[-1])
            identity = (c["session"], *vals)
            require(tid not in seen_trial or seen_trial[tid] == identity,
                    "shared_trial_metadata_conflict", budget)
            seen_trial[tid] = identity
        require(len(set(orders)) == n, "unique_original_rows", budget)
        budget.tick()
    require(ids == sorted(set(ids)), "sorted_unique_channels", budget)
    return packet


def channel_arrays(channel, budget):
    import numpy as np
    n = len(channel["ids"])
    budget.reserve("elements", 3 * n * 1000 + 8 * n)
    budget.reserve("work_units", 4 * n * 1000 + 8 * n)
    for key, shape in (("lfp", (n, 1000)), ("rates", (n,))):
        value = channel[key]
        if type(value) is np.ndarray:
            require(value.dtype == np.dtype("float64") and value.shape == shape,
                    "primitive_float64_shape", budget)
        else:
            require(type(value) is list and len(value) == n, "nested_numeric_list", budget)
            for row in value if key == "lfp" else [value]:
                if key == "lfp":
                    require(type(row) is list and len(row) == 1000, "nested_lfp_shape", budget)
                for item in row:
                    require(isinstance(item, numbers.Real) and not isinstance(item, (bool, np.bool_))
                            and math.isfinite(float(item)), "nested_finite_numeric", budget)
    with budget.live(32 * n * 1000 + 128 * (n + 1)):
        x = np.array(channel["lfp"], dtype=np.float64, copy=True).reshape(n, 1000)
        rates = np.array(channel["rates"], dtype=np.float64, copy=True).reshape(n)
        require(bool(np.isfinite(x).all() and np.isfinite(rates).all()
                     and (rates >= 0).all()), "signal_rate_values", budget)
        budget.tick()
        return x, rates


def metrics_valid(metrics, budget):
    require(type(metrics) is dict and set(metrics) == set(METRICS), "metric_fields", budget)
    for value in metrics.values():
        require(type(value) in (int, float) and math.isfinite(value), "finite_metric", budget)


def average_metrics(vectors, budget):
    require(bool(vectors), "nonempty_metric_average", budget)
    budget.reserve("elements", len(vectors) * len(METRICS) + len(METRICS))
    budget.reserve("work_units", len(vectors) * len(METRICS))
    for row in vectors:
        metrics_valid(row, budget)
    answer = {k: math.fsum(row[k] for row in vectors) / len(vectors) for k in METRICS}
    metrics_valid(answer, budget)
    return answer

