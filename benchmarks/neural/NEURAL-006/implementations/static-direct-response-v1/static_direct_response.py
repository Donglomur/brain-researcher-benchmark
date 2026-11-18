"""Static numeric behavior-to-ERP packet and response adapter, operator use only.

This preserves one supplied observed development case. It does not authenticate
source data, enforce no-tools execution, score responses, or read held targets.
The binding returned by prepare_case is private operator state, not model input.
"""
import hashlib
import json
import math

ACTIVE = tuple(sorted((
    "223", "207", "209", "234", "231", "228", "240", "239", "245", "206",
    "212", "224", "204", "233", "211", "217", "202", "222", "237", "219",
    "238", "215", "241", "230", "229", "203", "221", "213", "225", "214",
    "232", "205", "244")))
FEATURES = ("offer", "rp", "exp_valence", "ep_valence", "exp_arousal",
            "ep_arousal", "trialLocal", "trialGlobal", "abs_R", "abs_V", "abs_A")
TARGETS = ("FRN_N2_offer", "P3b_offer")
MAX_PACKET_BYTES = 4 * 1024 * 1024
MAX_RESPONSE_BYTES = 128 * 1024


class InvalidDirectResponse(ValueError):
    """The supplied projection or response does not satisfy this adapter."""


def require(condition, reason):
    if not condition:
        raise InvalidDirectResponse(reason)


def keys(value, expected, reason):
    require(type(value) is dict and set(value) == set(expected), reason)


def finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def digest(body):
    return hashlib.sha256(body).hexdigest()


def source_row(value):
    require(type(value) is int and 1 <= value <= 7380, "source_row_identity")
    return value


def features(row):
    require(all(finite(row[name]) for name in FEATURES), "finite_features")
    require(type(row["trialLocal"]) is int and 1 <= row["trialLocal"] <= 5,
            "local_trial")
    require(type(row["trialGlobal"]) is int and 1 <= row["trialGlobal"] <= 180,
            "global_trial")
    for output, left, right in (("abs_R", "offer", "rp"),
                                ("abs_V", "exp_valence", "ep_valence"),
                                ("abs_A", "exp_arousal", "ep_arousal")):
        expected = abs(row[left] - row[right])
        require(finite(expected) and
                math.isclose(row[output], expected, rel_tol=0, abs_tol=1e-8),
                "derived_prediction_error")
    return [row[name] for name in FEATURES]


def prepare_case(case):
    """Return (public_packet_bytes, private_binding) without changing the case.

    Only the observed development_lopo33 projection is supported: one held
    active person and all other32 original training people, each once. All
    supplied training/query rows are presented, without sampling or truncation.
    Completeness relative to original source missingness remains a custody check.
    """
    keys(case, ("schema", "participant", "training", "query", "clusters"),
         "case_fields")
    require(case["schema"] == "neural006-case-v1" and
            type(case["participant"]) is str and case["participant"] in ACTIVE,
            "observed_development_case_only")
    expected_clusters = [
        {"fit_id": "cluster_%02d" % index, "original_participant": person}
        for index, person in enumerate(ACTIVE) if person != case["participant"]]
    require(type(case["clusters"]) is list and
            case["clusters"] == expected_clusters, "complete_observed_training_roster")
    require(type(case["training"]) is list and 32 <= len(case["training"]) <= 5760,
            "bounded_training_rows")
    require(type(case["query"]) is list and 1 <= len(case["query"]) <= 180,
            "bounded_query_rows")
    group_ids = [row["fit_id"] for row in expected_clusters]
    originals = {row["fit_id"]: row["original_participant"] for row in expected_clusters}
    tokens = {name: "c%03d" % (index + 1) for index, name in enumerate(group_ids)}
    grouped = {name: [] for name in group_ids}
    seen_source = set()
    encountered_groups = []
    training = []
    for row in case["training"]:
        keys(row, FEATURES + TARGETS + ("participant", "original_participant", "source_row"),
             "training_row_fields")
        group = row["participant"]
        require(type(group) is str and group in originals and
                row["original_participant"] == originals[group], "training_person_identity")
        sid = source_row(row["source_row"])
        require(sid not in seen_source, "duplicate_training_source")
        seen_source.add(sid)
        require(all(finite(row[name]) for name in TARGETS), "finite_training_targets")
        values = features(row)
        grouped[group].append((sid, row["trialGlobal"]))
        if not encountered_groups or encountered_groups[-1] != group:
            encountered_groups.append(group)
        training.append([tokens[group], *values, *(row[name] for name in TARGETS)])
    require(encountered_groups == group_ids, "original_training_group_order")
    for rows in grouped.values():
        require(1 <= len(rows) <= 180, "training_cluster_support")
        require(all(a[0] < b[0] and a[1] < b[1] for a, b in zip(rows, rows[1:])),
                "training_source_trial_order")
    query = []
    mapping = []
    previous = (0, 0)
    for index, row in enumerate(case["query"], 1):
        keys(row, FEATURES + ("source_row",), "query_fields_no_targets_or_masks")
        sid = source_row(row["source_row"])
        require(sid not in seen_source, "query_training_overlap")
        values = features(row)
        require(sid > previous[0] and row["trialGlobal"] > previous[1], "query_order")
        previous = (sid, row["trialGlobal"])
        token = "q%03d" % index
        query.append([token, *values])
        mapping.append([token, sid])
    packet = {
        "schema": "neural006-static-numeric-packet-v1",
        "condition": "direct_numeric_behavior_to_erp_encoding",
        "scope": "one_observed_development_lopo33_case",
        "training_columns": ["cluster", *FEATURES, *TARGETS],
        "query_columns": ["query", *FEATURES],
        "training": training,
        "query": query,
        "targets": list(TARGETS),
        "target_units": "original_exported_amplitude_units_physical_scale_unresolved",
        "response_schema": "neural006-static-numeric-response-v1",
        "response_columns": ["query", *TARGETS],
        "response_rule": "Submit finite predictions for every query exactly once; no abstention."
    }
    body = canonical(packet)
    require(len(body) <= MAX_PACKET_BYTES, "complete_packet_exceeds_byte_limit_no_truncation")
    binding = {"schema": "neural006-static-numeric-binding-v1",
               "case_sha256": digest(canonical(case)), "packet_sha256": digest(body),
               "query_source_rows": mapping}
    return body, binding


def strict_response(body):
    require(type(body) is bytes and 0 < len(body) <= MAX_RESPONSE_BYTES, "response_bytes")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def constant(value):
        raise InvalidDirectResponse("nonfinite_json_constant")

    try:
        return json.loads(body.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=constant)
    except InvalidDirectResponse:
        raise
    except (UnicodeError, ValueError, RecursionError) as error:
        raise InvalidDirectResponse("invalid_response_json") from error


def collect(case, binding, response_body):
    """Validate a full response against the exact previously presented case.

    Call only in trusted operator code after the participant response is fixed.
    This returns one candidate vector; it does not relabel it as either existing
    scorer mode or establish that tools/feedback were unavailable to a model.
    """
    _, expected_binding = prepare_case(case)
    keys(binding, ("schema", "case_sha256", "packet_sha256", "query_source_rows"),
         "binding_fields")
    mapping = binding["query_source_rows"]
    require(type(mapping) is list and len(mapping) == len(case["query"]),
            "binding_query_support")
    for item in mapping:
        require(type(item) is list and len(item) == 2 and type(item[0]) is str,
                "binding_query_row")
        source_row(item[1])
    require(all(type(binding[name]) is str for name in
                ("schema", "case_sha256", "packet_sha256")) and
            binding == expected_binding,
            "presented_case_binding_changed")
    response = strict_response(response_body)
    keys(response, ("schema", "packet_sha256", "predictions"), "response_fields")
    require(response["schema"] == "neural006-static-numeric-response-v1" and
            response["packet_sha256"] == binding["packet_sha256"], "response_packet_identity")
    expected = {token for token, _ in mapping}
    rows = response["predictions"]
    require(type(rows) is list and len(rows) == len(mapping), "complete_response_support")
    by_token = {}
    for row in rows:
        require(type(row) is list and len(row) == 3, "response_row")
        token = row[0]
        require(type(token) is str and token in expected and token not in by_token,
                "response_query_identity")
        require(all(finite(value) for value in row[1:]), "finite_response_predictions")
        by_token[token] = row[1:]
    candidate = {"status": "complete", "predictions": [
        [sid, *by_token[token]] for token, sid in mapping]}
    return {"schema": "neural006-static-numeric-collection-v1",
            "condition": "direct_numeric_behavior_to_erp_encoding",
            "participant": case["participant"],
            "case_sha256": binding["case_sha256"],
            "packet_sha256": binding["packet_sha256"],
            "response_sha256": digest(response_body),
            "prediction_sha256": digest(canonical(candidate)),
            "candidate": candidate,
            "scientific_qualification": "not_established"}
