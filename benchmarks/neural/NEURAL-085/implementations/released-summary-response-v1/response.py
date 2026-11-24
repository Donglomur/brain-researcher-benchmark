"""Complete N085 released-summary numerical observations; operator-owned only.

No files, recordings, targets, models or scorers are opened. Prepared bytes and
operator capacity declarations are not authenticated source/runtime qualification.
"""
import copy
import hashlib
import json
import math
import re
import secrets

ARMS = {
    "TEXT": ("text",), "GAZE": ("gaze",), "EEG": ("eeg", "nuisance"),
    "TEXT_GAZE": ("text", "gaze"), "JOINT": ("text", "gaze", "eeg"),
    "NUISANCE": ("nuisance",), "NTG": ("text", "gaze", "nuisance"),
    "NTGE": ("text", "gaze", "nuisance", "eeg"),
    "NTG_SHUFFLED_E": ("text", "gaze", "nuisance", "eeg"),
}
IDENTITY_FIELDS = ("task", "person_token", "item_fold", "context", "arm",
                   "representation", "mode", "seed", "programme_sha256",
                   "source_sha256", "split_sha256", "information_set",
                   "generation", "role", "method")
PHASE_POLICY = "complete_calibration_then_complete_query_with_training_copy/v1"
HEX = re.compile(r"[0-9a-f]{64}\Z")
CAPACITY_FIELDS = ("input_bytes", "condition_transport_bytes", "frame_bytes",
                   "job_retained_bytes", "job_retained_tokens", "condition_tokens",
                   "response_reserve_bytes_per_job", "response_reserve_tokens_per_job",
                   "token_measurement_id")


def need(ok, code):
    if not ok:
        raise ValueError(code)


def exact(obj, fields, code):
    need(type(obj) is dict and set(obj) == set(fields), code)


def finite(x):
    try:
        return type(x) in (int, float) and math.isfinite(x)
    except OverflowError:
        return False


def encode(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def digest(obj):
    return hashlib.sha256(obj if type(obj) is bytes else encode(obj)).hexdigest()


def decode(raw):
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, "duplicate_json_key")
            out[k] = v
        return out
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")))


def ishex(x):
    return type(x) is str and HEX.fullmatch(x) is not None


def pin(raw):
    return {"bytes": len(raw), "sha256": digest(raw)}


def check_pin(raw, descriptor):
    exact(descriptor, ("bytes", "sha256"), "pin_fields")
    need(type(descriptor["bytes"]) is int and ishex(descriptor["sha256"])
         and descriptor == pin(raw), "input_pin_mismatch")


class CapacityError(ValueError):
    """No exposure occurs when any complete-condition capacity check fails."""
    def __init__(self, resource, required, limit):
        self.disposition = {"status": "whole_condition_refused_before_exposure",
                            "resource": resource, "required": required, "limit": limit,
                            "participant_exposure": False}
        super().__init__(resource + "_capacity")


def capacity_check(resource, required, limit):
    if required > limit:
        raise CapacityError(resource, required, limit)


def validate_capacity(c):
    exact(c, CAPACITY_FIELDS, "capacity_fields")
    for k in CAPACITY_FIELDS[:-1]:
        need(type(c[k]) is int and c[k] > 0, "positive_capacity_" + k)
    need(type(c["token_measurement_id"]) is str and 0 < len(c["token_measurement_id"]) <= 256,
         "token_measurement_id")


def vector(v, size, code, predicate=lambda x: x is None or finite(x)):
    need(type(v) is list and len(v) == size and all(predicate(x) for x in v), code)


def features(f, arm):
    exact(f, ARMS[arm], "feature_blocks")
    if "text" in f:
        need(type(f["text"]) is str and 0 < len(f["text"]) <= 10000
             and bool(f["text"].strip()), "literal_sentence_text")
    if "eeg" in f:
        vector(f["eeg"], 840, "eeg840")
    if "gaze" in f:
        vector(f["gaze"], 12, "gaze12")
        for i, x in enumerate(f["gaze"]):
            if x is not None:
                need(x >= 0 and (x <= 1 if i in (1, 3, 5, 7, 9, 10) else True), "gaze_range")
    if "nuisance" in f:
        n = f["nuisance"]
        exact(n, ("eeg_support",) if arm == "EEG" else
              ("eeg_support", "gaze_missing", "source_word_slots", "valid_gaze_fractions"),
              "nuisance_fields")
        binary = lambda x: type(x) is int and x in (0, 1)
        vector(n["eeg_support"], 840, "eeg_support840", binary)
        if "eeg" in f:
            need(n["eeg_support"] == [int(x is None) for x in f["eeg"]], "eeg_missingness")
        if arm != "EEG":
            vector(n["gaze_missing"], 12, "gaze_missing12", binary)
            need(type(n["source_word_slots"]) is int and n["source_word_slots"] >= 0, "word_slots")
            vector(n["valid_gaze_fractions"], 5, "valid_gaze_fractions",
                   lambda x: finite(x) and 0 <= x <= 1)
            if "gaze" in f:
                need(n["gaze_missing"] == [int(x is None) for x in f["gaze"]], "gaze_missingness")
                need(n["valid_gaze_fractions"] == f["gaze"][1:10:2], "gaze_fraction_parity")


def validate_views(training_raw, query_raw, binding):
    exact(binding, ("training", "query", "identity_sha256", "training_census_sha256", "query_ids"),
          "binding_fields")
    check_pin(training_raw, binding["training"]); check_pin(query_raw, binding["query"])
    t, q = decode(training_raw), decode(query_raw)
    exact(t, ("train", "identity", "information_set"), "training_envelope")
    exact(q, ("query", "identity", "information_set"), "query_envelope")
    identity = t["identity"]
    exact(identity, IDENTITY_FIELDS, "identity_fields")
    need(identity == q["identity"] and digest(identity) == binding["identity_sha256"], "bound_identity")
    need(identity["task"] == "NEURAL-085" and identity["context"] == "sentence"
         and identity["representation"] == "released_summary" and identity["role"] == "participant"
         and identity["method"] == "candidate" and identity["arm"] in ARMS, "source_job")
    need(identity["mode"] in ("frozen_program", "case_adaptive")
         and type(identity["item_fold"]) is int and 0 <= identity["item_fold"] < 5
         and type(identity["seed"]) is int and identity["seed"] == 0, "source_schedule")
    need(all(ishex(identity[k]) for k in ("person_token", "programme_sha256", "source_sha256",
                                        "split_sha256", "generation")), "source_hashes")
    need(all(x == "offline_case_local" for x in (identity["information_set"], t["information_set"],
                                                 q["information_set"])), "information_set")
    need(type(t["train"]) is list and t["train"] and type(q["query"]) is list, "row_lists")
    ids = {}; people = {}
    for phase, rows in (("train", t["train"]), ("query", q["query"])):
        ids[phase] = []
        for r in rows:
            exact(r, ("id", "features", "label", "weight", "person_group", "item_group")
                  if phase == "train" else ("id", "features"), "closed_" + phase + "_row")
            need(ishex(r["id"]), "row_id"); ids[phase].append(r["id"])
            features(r["features"], identity["arm"])
            if phase == "train":
                need(type(r["label"]) is int and r["label"] in (0, 1), "training_label")
                need(finite(r["weight"]) and r["weight"] > 0, "training_weight")
                need(ishex(r["person_group"]) and ishex(r["item_group"]), "training_groups")
                people.setdefault(r["person_group"], set()).add(r["label"])
    need(len(people) == 17 and all(v == {0, 1} for v in people.values()), "seventeen_people_both_classes")
    need(all(len(v) == len(set(v)) for v in ids.values()) and not set(ids["train"]) & set(ids["query"]),
         "unique_disjoint_ids")
    need(digest(ids["train"]) == binding["training_census_sha256"], "ordered_training_census")
    need(ids["query"] == binding["query_ids"], "ordered_query_census")
    return t, q


class PreparedJob:
    """Private operator object. No participant-facing method works before admission."""
    def __init__(self, training_raw, query_raw, binding, capacity, measure_tokens, *, _frozen_nonce=None):
        validate_capacity(capacity)
        need(type(training_raw) is bytes and type(query_raw) is bytes, "input_bytes")
        capacity_check("input_bytes", len(training_raw) + len(query_raw), capacity["input_bytes"])
        t, q = validate_views(training_raw, query_raw, binding)
        self._identity = copy.deepcopy(t["identity"]); self._binding = copy.deepcopy(binding)
        self._session = secrets.token_hex(32) if _frozen_nonce is None else _frozen_nonce
        need(ishex(self._session), "session_nonce")
        people = {x: "person-%02d" % i for i, x in enumerate(sorted({r["person_group"] for r in t["train"]}))}
        items = {x: "item-%05d" % i for i, x in enumerate(sorted({r["item_group"] for r in t["train"]}))}
        train = [{"token": "training-%d" % i, "features": r["features"], "label": r["label"],
                  "weight": r["weight"], "person_group": people[r["person_group"]],
                  "item_group": items[r["item_group"]]} for i, r in enumerate(t["train"])]
        query = [{"token": "query-%d" % i, "features": r["features"]} for i, r in enumerate(q["query"])]
        header = {"schema": "neural085-complete-numeric-frame/v1", "session": self._session,
                  "task": "NEURAL-085", "arm": self._identity["arm"],
                  "representation": "released_summary_numeric", "phase_policy": PHASE_POLICY,
                  "target": "p_tsr: probability of TSR (1); NR is 0",
                  "limits": "Numerical summaries, not raw EEG; runtime and scientific qualification absent."}
        self._frames = (encode({**header, "phase": "calibration", "training": train}),
                        encode({**header, "phase": "inference", "training": train, "query": query}))
        self._frame_pins = tuple(pin(b) for b in self._frames)
        # Overbound the ASCII wire form of every legal binary64 probability.
        # Extra host framing and provider tokens remain operator qualifications.
        reply_bound = sum(len(encode({"session": self._session, "token": r["token"],
                                      "p_tsr": "0" * 32})) for r in query)
        capacity_check("response_reserve_bytes_per_job", reply_bound,
                       capacity["response_reserve_bytes_per_job"])
        capacity_check("response_reserve_tokens_per_job", reply_bound,
                       capacity["response_reserve_tokens_per_job"])
        retained = sum(map(len, self._frames)) + capacity["response_reserve_bytes_per_job"]
        for b in self._frames:
            capacity_check("frame_bytes", len(b), capacity["frame_bytes"])
        capacity_check("job_retained_bytes", retained, capacity["job_retained_bytes"])
        # Caller must measure complete framed context, not independently sum token
        # counts that omit prompt/framing overhead. This is still operator evidence.
        tokens = measure_tokens(self._frames)
        need(type(tokens) is int and tokens >= 0, "operator_token_measurement")
        tokens += capacity["response_reserve_tokens_per_job"]
        capacity_check("job_retained_tokens", tokens, capacity["job_retained_tokens"])
        self._capacity = copy.deepcopy(capacity)
        self._receipt = {"identity": self._identity, "input_binding": self._binding, "session_nonce": self._session,
                         "phase_policy": PHASE_POLICY, "frame_pins": list(self._frame_pins),
                         "input_bytes": len(training_raw) + len(query_raw),
                         "observation_bytes": sum(map(len, self._frames)), "transport_bytes": retained, "retained_bytes": retained,
                         "retained_tokens": tokens, "training_rows": len(train), "query_rows": len(query),
                         "token_measurement_id": capacity["token_measurement_id"],
                         "provider_capacity_qualified": False}
        self._receipt_hash = digest(self._receipt)
        self._admission = None; self._phase = "prepared"; self._responses = {}; self._issued = []

    def preflight_operator(self):
        return copy.deepcopy(self._receipt)

    def _verify(self):
        need(digest(self._receipt) == self._receipt_hash
             and tuple(pin(b) for b in self._frames) == self._frame_pins
             and self._receipt["frame_pins"] == list(self._frame_pins), "prepared_frame_or_receipt_changed")

    def calibration(self):
        need(self._admission is not None and self._phase == "prepared", "condition_not_admitted_or_phase")
        self._verify(); self._phase = "calibration_issued"; self._issued.append(self._frame_pins[0])
        return self._frames[0]

    def inference(self):
        need(self._admission is not None and self._phase == "calibration_issued", "calibration_not_issued")
        self._verify(); self._phase = "inference"; self._issued.append(self._frame_pins[1])
        return self._frames[1]

    def answer(self, reply):
        need(self._phase == "inference", "inference_not_issued")
        exact(reply, ("session", "token", "p_tsr"), "reply_fields")
        need(reply["session"] == self._session and type(reply["token"]) is str
             and re.fullmatch(r"query-(0|[1-9][0-9]*)", reply["token"]), "reply_binding")
        i = int(reply["token"][6:])
        need(i < self._receipt["query_rows"] and i not in self._responses, "unknown_or_final_query")
        p = reply["p_tsr"]; need(finite(p) and 0 <= p <= 1, "probability_range")
        self._responses[i] = p

    def finish_operator(self):
        need(self._phase == "inference" and len(self._responses) == self._receipt["query_rows"],
             "incomplete_or_closed_job")
        self._verify()
        values = [{"id": rid, "p_tsr": self._responses[i]} for i, rid in enumerate(self._binding["query_ids"])]
        self._phase = "closed"
        return {"schema": "neural085-numeric-response-collection/v1", "probabilities": values,
                "probability_sha256": digest(values), "preflight": self.preflight_operator(),
                "condition_admission_sha256": self._admission, "issued_frame_pins": copy.deepcopy(self._issued),
                "complete_supplied_job": True, "empty_query_disposition": not values,
                "actual_participant_delivery_attested": False, "campaign_admitted": False,
                "runtime_isolation_established": False, "scientifically_qualified": False}


def validate_census(receipts):
    """Full810-coordinate and original presentation-count check, no query targets."""
    need(len(receipts) == 810, "complete_810_jobs")
    coordinates = set(); people = set(); common = None; counts = {}
    for r in receipts:
        i = r["identity"]; key = (i["person_token"], i["item_fold"], i["arm"])
        need(key not in coordinates, "duplicate_job_coordinate"); coordinates.add(key); people.add(key[0])
        fields = ("task", "context", "representation", "mode", "seed", "programme_sha256",
                  "source_sha256", "split_sha256", "information_set", "generation", "role", "method")
        scope = tuple(i[k] for k in fields)
        need(common is None or common == scope, "mixed_condition"); common = scope
        counts[key] = r["query_rows"]
    need(len(people) == 18 and coordinates == {(p, f, a) for p in people for f in range(5) for a in ARMS},
         "full_person_fold_arm_census")
    for p in people:
        for arm in ARMS:
            need(sum(counts[p, f, arm] for f in range(5)) == 739, "original_739_presentations")
        for f in range(5):
            need(len({counts[p, f, a] for a in ARMS}) == 1, "same_fold_arm_query_counts")


class Condition:
    """Stream complete preparation; retain receipts, never all serialized frames.

    The operator retains immutable input captures and reloads them for open().
    Reloaded bytes and regenerated frames must match the original full preflight.
    This is source custody checking, not an OS sandbox or provider qualification.
    """
    def __init__(self, jobs, expected_bindings, capacity):
        validate_capacity(capacity)
        need(type(expected_bindings) is list and len(expected_bindings) == 810, "issuer_810_bindings")
        expected = {digest(b): b for b in expected_bindings}
        need(len(expected) == 810, "unique_issuer_bindings")
        self._records = {}; self._states = {}; self._outputs = {}; receipts = []
        self._capacity = copy.deepcopy(capacity)
        transport = tokens = inputs = 0
        for job in jobs:
            need(type(job) is PreparedJob and job._phase == "prepared" and job._admission is None,
                 "fresh_prepared_job_required")
            job._verify(); need(job._capacity == capacity, "same_condition_capacity")
            key = digest(job._binding)
            need(key in expected and key not in self._records, "issuer_job_binding")
            r = job.preflight_operator(); receipts.append(r); self._records[key] = r
            inputs += r["input_bytes"]; transport += r["transport_bytes"]; tokens += r["retained_tokens"]
            capacity_check("input_bytes", inputs, capacity["input_bytes"])
            capacity_check("condition_transport_bytes", transport, capacity["condition_transport_bytes"])
            capacity_check("condition_tokens", tokens, capacity["condition_tokens"])
            # Preparation objects cannot be reused as another live session.
            job._phase = "consumed_preflight"
        need(set(self._records) == set(expected), "missing_prepared_job")
        validate_census(receipts)
        self._receipt = {"schema": "neural085-complete-condition-preflight/v1",
                         "jobs": [digest(r) for r in receipts], "issuer_bindings_sha256": digest(expected_bindings),
                         "phase_policy": PHASE_POLICY, "input_bytes": inputs, "transport_bytes": transport,
                         "retained_tokens_sum": tokens, "capacity": copy.deepcopy(capacity),
                         "people": 18, "jobs_count": 810, "presentations_per_arm": 13302,
                         "provider_capacity_qualified": False, "actual_delivery_attested": False}
        self._seal = digest(self._receipt)
        self._record_hashes = {k: digest(r) for k, r in self._records.items()}
        self._states = {k: "ready" for k in self._records}

    def preflight_operator(self):
        return copy.deepcopy(self._receipt)

    def open(self, training_raw, query_raw, binding, measure_tokens):
        key = digest(binding)
        need(key in self._records and self._states[key] == "ready", "unknown_or_already_opened_job")
        need(not any(state == "opened" for state in self._states.values()), "previous_job_still_open")
        need(digest(self._receipt) == self._seal, "condition_receipt_changed")
        r = self._records[key]
        need(digest(r) == self._record_hashes[key], "condition_job_receipt_changed")
        job = PreparedJob(training_raw, query_raw, binding, self._capacity, measure_tokens,
                          _frozen_nonce=r["session_nonce"])
        need(job.preflight_operator() == r, "reloaded_preparation_mismatch")
        job._admission = self._seal; self._states[key] = "opened"
        return job

    def collect(self, job):
        need(type(job) is PreparedJob and job._admission == self._seal, "foreign_job")
        key = digest(job._binding)
        need(key in self._records and self._states[key] == "opened"
             and job._receipt_hash == self._record_hashes[key], "collection_job_identity")
        result = job.finish_operator()
        self._outputs[key] = result["probability_sha256"]; self._states[key] = "closed"
        return result

    def finish_operator(self):
        need(all(state == "closed" for state in self._states.values()), "incomplete_condition_responses")
        return {"condition_preflight_sha256": self._seal, "complete_810_job_collection": True,
                "prediction_hashes": copy.deepcopy(self._outputs),
                "campaign_admitted": False, "scientifically_qualified": False}


def require_same_prepared_exposure(a, b):
    """Compare exact frozen issuer inputs/order/phase; exclude fresh session nonce.

    This is not cross-campaign original-occurrence or runtime qualification.
    """
    need(type(a) is PreparedJob and type(b) is PreparedJob, "prepared_jobs_required")
    a._verify(); b._verify()
    need(a._binding == b._binding and a._receipt["phase_policy"] == b._receipt["phase_policy"],
         "different_frozen_exposure")
    return {"exact_frozen_input_order_phase_equal": True,
            "original_cross_campaign_case_equivalence_qualified": False,
            "runtime_access_and_resource_equivalence_qualified": False}
