"""Pure, evaluator-owned MEG panel, fold-view and prediction contracts.

This module reads only the pinned public participant roster. It never opens
neural arrays, executes a programme, fits a model or grants runtime authority.
``build_panel`` consumes an evaluator-private 32-byte key but does not retain it.
The returned panel and ``collect`` result contain targets and source identities:
neither is a participant packet. Only ``public_context`` is participant-visible.

Context bytes are shared by both information conditions. The outer owner must
separately bind condition, frozen programme, input files and actual closure.
Hashes ensure consistency, not provenance, isolation or contamination immunity.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
from pathlib import Path
import re


PANEL_SCHEMA = "meg-paired-program-private-panel/v1"
CONTEXT_SCHEMA = "meg-paired-program-context/v1"
RESPONSE_SCHEMA = "meg-paired-program-response/v1"
COLLECTION_SCHEMA = "meg-paired-program-private-collection/v1"
OUTCOMES = ("reproduction", "improvement")
CATEGORIES = ("false", "face", "letter", "object")
PAIR = ("face", "object")
ROSTER_SHA256 = "6e0970cb1a1a9aab53a35c43c3bcf84af527131631418bfd00594528e43bf70a"
ROSTER_PATH = Path(__file__).parent.parent / "nested-connectivity-v1" / "published_participants.txt"
HEX = re.compile(r"[0-9a-f]{64}\Z")


class ContractError(ValueError):
    """The supplied protected panel, public context or response is inconsistent."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def _json_value(value):
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        require(math.isfinite(value), "nonfinite JSON number")
        return
    if type(value) is list:
        for child in value:
            _json_value(child)
        return
    if type(value) is dict:
        require(all(type(k) is str for k in value), "JSON object keys must be strings")
        for child in value.values():
            _json_value(child)
        return
    raise ContractError("only ordinary JSON values are permitted")


def canonical(value):
    """Return deterministic UTF-8 JSON bytes; refuse non-JSON and nonfinite data."""
    _json_value(value)
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ContractError("invalid canonical JSON") from exc


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def decode_json(body):
    """Decode bounded-by-caller JSON bytes/text with duplicate-key rejection.

    Filesystem extent, nesting/resource bounds and untrusted transport containment
    belong to the outer reader. This pure helper is not a file-size sandbox.
    """
    require(type(body) in (bytes, str), "JSON body must be bytes or text")

    def unique(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(value):
        raise ContractError("nonfinite JSON constant: " + value)

    try:
        result = json.loads(body, object_pairs_hook=unique, parse_constant=nonfinite)
        _json_value(result)  # Also catches exponent overflow such as 1e10000.
        return result
    except (ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError("invalid JSON body") from exc


def _fields(value, fields, name):
    require(type(value) is dict and set(value) == set(fields), name + " has wrong fields")


def _name(value, name):
    require(type(value) is str and 0 < len(value) <= 512 and value == value.strip(),
            name + " must be a nonempty bounded name")
    require(not any(ord(c) < 32 for c in value), name + " has a control character")


def _sha(value, name):
    require(type(value) is str and HEX.fullmatch(value) is not None, name + " must be SHA256 hex")


def _finite(value, name):
    require(type(value) in (int, float), name + " must be a real number, not bool")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ContractError(name + " is outside finite float range") from exc
    require(math.isfinite(result), name + " must be finite")
    return result


def _binding(value):
    _fields(value, ("bytes", "sha256"), "source binding")
    require(type(value["bytes"]) is int and value["bytes"] > 0, "positive source byte extent required")
    _sha(value["sha256"], "source binding hash")


def published_participants():
    """Authenticate the small existing public roster, without importing a scorer."""
    with ROSTER_PATH.open("rb") as stream:
        raw = stream.read(4097)
    require(len(raw) <= 4096 and hashlib.sha256(raw).hexdigest() == ROSTER_SHA256,
            "published roster identity changed")
    people = tuple(raw.decode("utf-8").splitlines())
    require(len(people) == len(set(people)) == 94, "exact 94-person roster required")
    return people


def _folds(folds, people):
    require(type(folds) is dict and set(folds) == set(people), "folds require exactly the 94 source people")
    require(all(type(v) is int and 0 <= v < 10 for v in folds.values()), "folds must be integers 0..9")
    require(set(folds.values()) == set(range(10)), "all ten folds must be represented")


def _category(value):
    require(type(value) is str and value in ("False", *CATEGORIES), "unknown source category")
    return "false" if value == "False" else value


def source_observation_id(participant, category):
    """Exact selected producer identity; evaluator-private because it names class.

    This reproduces original-feature-producer-v1/producer.py::observation_id.
    Matching an identifier does not authenticate its associated tensor bytes.
    """
    _name(participant, "participant")
    category = _category(category)
    return f"{participant}|{category}|Irrelevant|1000ms|on|Raw|CS-PFC|bary-sq_dtw_max"


def _records(records, people, *, private=False):
    require(type(records) is list and len(records) == 376, "exact 376 ordered source windows required")
    fields = {"source_id", "participant", "category", "tensor_sha256"}
    if private:
        fields.update(("id", "group_id"))
    identities, support, opaque, groups = set(), set(), set(), {}
    for row in records:
        _fields(row, fields, "source record")
        _name(row["source_id"], "source ID")
        require(row["source_id"] not in identities, "duplicate source ID")
        identities.add(row["source_id"])
        require(type(row["participant"]) is str and row["participant"] in people, "unknown source participant")
        category = _category(row["category"])
        require(row["source_id"] == source_observation_id(row["participant"], category),
                "source ID differs from exact selected producer route")
        key = (row["participant"], category)
        require(key not in support, "duplicate participant/category, including aliases")
        support.add(key)
        _sha(row["tensor_sha256"], "source tensor hash")
        if private:
            require(row["category"] == category, "private category must be normalized")
            _sha(row["id"], "opaque window ID")
            _sha(row["group_id"], "opaque group ID")
            require(row["id"] not in opaque, "duplicate opaque window ID")
            opaque.add(row["id"])
            require(groups.get(row["participant"], row["group_id"]) == row["group_id"], "participant group changed")
            groups[row["participant"]] = row["group_id"]
    require(support == {(p, c) for p in people for c in CATEGORIES}, "incomplete source category support")
    if private:
        require(len(set(groups.values())) == 94, "opaque groups collide")


def build_panel(records, folds, key, source_binding):
    """Build the evaluator-private complete panel without loading tensor bodies.

    ``records`` retain the declared source order; it is not authenticated as the
    historical paper order. Each exact record is source_id, participant, category,
    tensor_sha256. ``folds`` is an already selected complete participant map.
    Supplying either does not establish provenance or historical equivalence.
    """
    people = published_participants()
    _records(records, people)
    _folds(folds, people)
    _binding(source_binding)
    require(type(key) is bytes and len(key) == 32, "one private 32-byte HMAC key required")
    private = []
    for row in records:
        normalized = {**row, "category": _category(row["category"])}
        group = hmac.new(key, canonical(["meg-group-v1", source_binding, row["participant"]]), hashlib.sha256).hexdigest()
        opaque = hmac.new(key, canonical(["meg-window-v1", source_binding, normalized]), hashlib.sha256).hexdigest()
        private.append({**normalized, "id": opaque, "group_id": group})
    public = sorted(({k: r[k] for k in ("id", "group_id", "tensor_sha256")} for r in private), key=lambda r: r["id"])
    panel = {"schema": PANEL_SCHEMA, "source_binding": dict(source_binding),
             "participant_folds": dict(folds), "private_records": private, "public_windows": public}
    panel["panel_sha256"] = digest(panel)
    _checked_panel(panel)
    return panel


def _checked_panel(panel):
    _fields(panel, ("schema", "source_binding", "participant_folds", "private_records", "public_windows", "panel_sha256"), "private panel")
    require(panel["schema"] == PANEL_SCHEMA, "wrong panel schema")
    _sha(panel["panel_sha256"], "panel hash")
    require(panel["panel_sha256"] == digest({k: v for k, v in panel.items() if k != "panel_sha256"}), "private panel changed")
    people = published_participants()
    _binding(panel["source_binding"])
    _folds(panel["participant_folds"], people)
    _records(panel["private_records"], people, private=True)
    expected = sorted(({k: r[k] for k in ("id", "group_id", "tensor_sha256")} for r in panel["private_records"]), key=lambda r: r["id"])
    require(panel["public_windows"] == expected, "public window roster changed")
    return panel


def ordered_public_windows(panel):
    """Return fresh public window rows in exact WINDOWS tensor-row order.

    The provisioning owner must join these opaque IDs to ``private_source_join``
    and copy the authenticated original matrices in this order. Hash metadata is
    not evidence that such copying or actual byte validation has happened.
    """
    return [dict(row) for row in _checked_panel(panel)["public_windows"]]


def private_source_join(panel):
    """Return source_id -> private source/opaque join; NEVER deliver to candidate.

    Each value has source_id, participant, normalized category, tensor_sha256,
    opaque id and group_id. This helper avoids making a caller reconstruct HMACs.
    The caller authenticates original tensor bytes and source-binding provenance.
    """
    return {row["source_id"]: dict(row) for row in _checked_panel(panel)["private_records"]}


def public_context(panel, fold):
    """Return a fresh copy of the only public fold view, identical across arms.

    All 376 unlabeled windows remain available for declared global source QC.
    Training labels retain source-row order; held pair IDs are opaque-sorted.
    Labels/source identities for held rows never appear. The complete held batch
    remains available for original held-batch transform extrema. The outer owner
    must prevent mutable state or feedback crossing fold processes.
    """
    panel = _checked_panel(panel)
    require(type(fold) is int and 0 <= fold < 10, "fold must be integer 0..9")
    train, query = [], []
    for row in panel["private_records"]:
        if row["category"] not in PAIR:
            continue
        if panel["participant_folds"][row["participant"]] == fold:
            query.append(row["id"])
        else:
            train.append({"id": row["id"], "label": row["category"]})
    context = {"schema": CONTEXT_SCHEMA, "panel_sha256": panel["panel_sha256"],
               "source_binding": dict(panel["source_binding"]), "fold": fold,
               "windows": [dict(r) for r in panel["public_windows"]],
               "training": train, "queries": sorted(query)}
    context["context_sha256"] = digest(context)
    _checked_context(context)
    return context


def _checked_context(context):
    _fields(context, ("schema", "panel_sha256", "source_binding", "fold", "windows", "training", "queries", "context_sha256"), "public context")
    require(context["schema"] == CONTEXT_SCHEMA, "wrong context schema")
    _sha(context["panel_sha256"], "panel hash")
    _sha(context["context_sha256"], "context hash")
    require(context["context_sha256"] == digest({k: v for k, v in context.items() if k != "context_sha256"}), "context hash mismatch")
    _binding(context["source_binding"])
    require(type(context["fold"]) is int and 0 <= context["fold"] < 10, "invalid context fold")
    windows = context["windows"]
    require(type(windows) is list and len(windows) == 376, "complete public window roster required")
    ids, groups = [], {}
    for row in windows:
        _fields(row, ("id", "group_id", "tensor_sha256"), "public window")
        for key in row:
            _sha(row[key], key)
        ids.append(row["id"])
        groups.setdefault(row["group_id"], set()).add(row["id"])
    require(len(set(ids)) == 376 and ids == sorted(ids), "public IDs must be unique and opaque-sorted")
    require(len(groups) == 94 and all(len(v) == 4 for v in groups.values()), "public group geometry must be 94 by 4")
    training, query = context["training"], context["queries"]
    require(type(training) is list and type(query) is list, "training and query sequences required")
    known = {}
    for row in training:
        _fields(row, ("id", "label"), "training row")
        require(type(row["id"]) is str and row["id"] in ids and row["id"] not in known, "invalid or duplicate training ID")
        require(type(row["label"]) is str and row["label"] in PAIR, "invalid training label")
        known[row["id"]] = row["label"]
    require(all(type(x) is str for x in query), "query IDs must be strings")
    require(len(set(query)) == len(query) and query == sorted(query), "query IDs must be unique and opaque-sorted")
    require(query and training and not (set(query) & set(known)), "empty or overlapping train/query support")
    require(set(query) <= set(ids) and len(query) + len(training) == 188, "exact selected 188-row support required")
    held_groups = 0
    for members in groups.values():
        train_members, query_members = members & set(known), members & set(query)
        if train_members:
            require(not query_members and len(train_members) == 2 and {known[x] for x in train_members} == set(PAIR), "training group must have one face/object pair and no queries")
        else:
            require(len(query_members) == 2, "held group must contain exactly two query rows")
            held_groups += 1
    require(0 < held_groups < 94, "nonempty grouped training and held support required")
    return context


def validate_prediction(body, context, outcome):
    """Validate one complete response and return normalized numeric dictionaries.

    Reproduction requires a claimed scalar for every source window, with explicit
    nulls allowed for source solver failures. This does not check scalar numerical
    agreement. Improvement may set that whole field to null. No omitted/invalid
    predictions are filled automatically, and bool is never a numeric prediction.
    """
    require(type(outcome) is str and outcome in OUTCOMES, "unknown outcome")
    context = _checked_context(context)
    _fields(body, ("schema", "context_sha256", "probabilities", "source_feature_values"), "response")
    require(body["schema"] == RESPONSE_SCHEMA, "wrong response schema")
    require(body["context_sha256"] == context["context_sha256"], "response is for a different context")
    values = body["probabilities"]
    require(type(values) is dict and set(values) == set(context["queries"]), "response must cover exactly the held IDs")
    probabilities = {}
    for identifier in context["queries"]:
        value = _finite(values[identifier], "probability")
        require(0 <= value <= 1, "probability outside [0,1]")
        probabilities[identifier] = value
    features = body["source_feature_values"]
    require(features is not None or outcome == "improvement", "reproduction requires complete claimed source features")
    if features is not None:
        expected = [r["id"] for r in context["windows"]]
        require(type(features) is dict and set(features) == set(expected), "claimed source features must cover all 376 IDs")
        features = {identifier: None if features[identifier] is None else _finite(features[identifier], "source feature") for identifier in expected}
    return {"schema": RESPONSE_SCHEMA, "context_sha256": context["context_sha256"],
            "probabilities": probabilities, "source_feature_values": features}


def collect(panel, predictions_by_fold, outcome):
    """Join ten validated responses to the evaluator-private original scorer ABI.

    The return value contains source identities and held labels. Its observations
    and probabilities may be passed to the unchanged score_cell(..., PAIR) only
    after the outer owner establishes complete actual producer/transport closure.
    This function cannot establish runtime isolation or author-code availability.
    """
    panel = _checked_panel(panel)
    require(type(predictions_by_fold) is dict and len(predictions_by_fold) == 10
            and all(type(k) is int for k in predictions_by_fold)
            and set(predictions_by_fold) == set(range(10)), "exact integer fold keys 0..9 required")
    probabilities, context_hashes, feature_vectors = {}, {}, []
    for fold in range(10):
        context = public_context(panel, fold)
        checked = validate_prediction(predictions_by_fold[fold], context, outcome)
        require(not (set(probabilities) & set(checked["probabilities"])), "held observations repeated across folds")
        probabilities.update(checked["probabilities"])
        context_hashes[str(fold)] = context["context_sha256"]
        feature_vectors.append(checked["source_feature_values"])
    selected = [r for r in panel["private_records"] if r["category"] in PAIR]
    require(len(selected) == len(probabilities) == 188 and set(probabilities) == {r["id"] for r in selected}, "full original selected support must be collected exactly once")
    observations = [{"id": r["source_id"], "participant": r["participant"], "label": r["category"],
                     "fold": panel["participant_folds"][r["participant"]]} for r in selected]
    joined = {r["source_id"]: probabilities[r["id"]] for r in selected}
    global_features = None
    if outcome == "reproduction":
        first = canonical(feature_vectors[0])
        require(all(canonical(values) == first for values in feature_vectors[1:]), "reproduction global feature claims changed across folds")
        global_features = [{"id": r["source_id"], "participant": r["participant"], "label": r["category"],
                            "value": feature_vectors[0][r["id"]]} for r in panel["private_records"]]
    return {"schema": COLLECTION_SCHEMA, "outcome": outcome, "panel_sha256": panel["panel_sha256"],
            "context_sha256_by_fold": context_hashes, "observations": observations,
            "probabilities_object": joined, "source_feature_rows": global_features,
            "feature_claim_sha256_by_fold": {str(f): None if v is None else digest(v) for f, v in enumerate(feature_vectors)},
            "original_fold_authentication": "not_established_by_this_contract",
            "feature_numerical_agreement_verified": False, "runtime_qualified": False,
            "scientific_result_qualified": False}
