"""Selected Generic-feature classification ABI; separate from raw-window ABI.

The complete source feature/QC provenance belongs to the evaluator. Only the
188 selected finite scalars are delivered. This module neither fits models nor
qualifies raw feature extraction, runtime containment, or scientific superiority.
"""
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
import struct

MODE = "generic_feature_classification_v1"
PAIR = ("face", "object")
ORIENTATION = ("Category_Selective", "Prefrontal_Cortex")
PANEL_SCHEMA = "meg-generic-classification-panel/v1"
CONTEXT_SCHEMA = "meg-generic-classification-context/v1"
RESPONSE_SCHEMA = "meg-generic-classification-response/v1"
ROSTER_PATH = Path(__file__).resolve().parent.parent / "nested-connectivity-v1" / "published_participants.txt"
ROSTER_SHA256 = "6e0970cb1a1a9aab53a35c43c3bcf84af527131631418bfd00594528e43bf70a"
HEX = re.compile(r"[0-9a-f]{64}")


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def fields(value, names, name):
    require(type(value) is dict and set(value) == set(names), name + " fields")


def name(value):
    require(type(value) is str and 0 < len(value) <= 512 and value == value.strip()
            and all(ord(c) >= 32 for c in value), "bounded identifier")
    return value


def sha(value):
    require(type(value) is str and HEX.fullmatch(value) is not None, "SHA256 identity")
    return value


def finite(value):
    require(type(value) in (int, float), "finite real value, not bool")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError("finite real value") from exc
    require(math.isfinite(result), "finite real value")
    return result


def binding(value):
    fields(value, ("bytes", "sha256"), "source binding")
    require(type(value["bytes"]) is int and value["bytes"] > 0, "positive source bytes")
    sha(value["sha256"])


def published_participants():
    raw = ROSTER_PATH.read_bytes()
    require(len(raw) == 563 and hashlib.sha256(raw).hexdigest() == ROSTER_SHA256,
            "exact public94-person roster")
    people = tuple(raw.decode().splitlines())
    require(len(people) == len(set(people)) == 94, "94 unique participants")
    return people


def source_id(participant, label):
    name(participant)
    require(label in PAIR, "face/object selected label")
    return f"{participant}|{label}|Irrelevant|1000ms|on|Generic|CS-PFC|bary-sq_dtw_max"


def scalar_sha(value):
    return hashlib.sha256(struct.pack("<d", finite(value))).hexdigest()


def checked_folds(folds):
    require(type(folds) is dict and set(folds) == set(published_participants()), "exact94-person folds")
    require(all(type(v) is int and 0 <= v < 10 for v in folds.values())
            and set(folds.values()) == set(range(10)), "all ten participant folds")


def build_panel(records, folds, key, source_binding):
    """Freeze188 selected post-QC scalar rows and their private source mapping."""
    require(type(records) is list and len(records) == 188, "exact188 selected source rows")
    checked_folds(folds)
    binding(source_binding)
    require(type(key) is bytes and len(key) == 32, "private random32-byte HMAC key")
    private = []
    for record in records:
        fields(record, ("row_key", "participant", "label", "value"), "selected scalar")
        participant, label = record["participant"], record["label"]
        source = source_id(participant, label)
        row = {"source_id": source, "row_key": name(record["row_key"]),
               "participant": participant, "label": label, "scalar_sha256": scalar_sha(record["value"])}
        row["group_id"] = hmac.new(key, canonical([MODE, "group", source_binding, participant]), hashlib.sha256).hexdigest()
        row["id"] = hmac.new(key, canonical([MODE, "row", source_binding, row]), hashlib.sha256).hexdigest()
        private.append(row)
    panel = {"schema": PANEL_SCHEMA, "input_mode": MODE, "source_binding": dict(source_binding),
             "participant_folds": dict(folds), "private_records": private,
             "public_rows": sorted(({k: r[k] for k in ("id", "group_id", "scalar_sha256")}
                                    for r in private), key=lambda r: r["id"])}
    panel["panel_sha256"] = digest(panel)
    return checked_panel(panel)


def checked_panel(panel):
    fields(panel, ("schema", "input_mode", "source_binding", "participant_folds", "private_records",
                   "public_rows", "panel_sha256"), "Generic panel")
    require(panel["schema"] == PANEL_SCHEMA and panel["input_mode"] == MODE, "explicit Generic mode")
    binding(panel["source_binding"])
    checked_folds(panel["participant_folds"])
    require(sha(panel["panel_sha256"]) == digest({k: v for k, v in panel.items() if k != "panel_sha256"}), "panel identity")
    records = panel["private_records"]
    require(type(records) is list and len(records) == 188, "188 selected private records")
    support, keys, ids, groups = set(), set(), set(), {}
    for row in records:
        fields(row, ("source_id", "row_key", "participant", "label", "scalar_sha256", "id", "group_id"), "private row")
        require(row["source_id"] == source_id(row["participant"], row["label"]), "Generic canonical ID")
        pair = (row["participant"], row["label"])
        require(pair not in support and name(row["row_key"]) not in keys and sha(row["id"]) not in ids, "unique source/opaque support")
        support.add(pair); keys.add(row["row_key"]); ids.add(row["id"])
        sha(row["scalar_sha256"]); sha(row["group_id"])
        require(groups.get(row["participant"], row["group_id"]) == row["group_id"], "one opaque participant group")
        groups[row["participant"]] = row["group_id"]
    require(support == {(p, label) for p in published_participants() for label in PAIR}
            and len(set(groups.values())) == 94, "exact94 paired participants")
    expected = sorted(({k: r[k] for k in ("id", "group_id", "scalar_sha256")} for r in records), key=lambda r: r["id"])
    require(panel["public_rows"] == expected, "opaque bank order")
    return panel


def ordered_public_rows(panel):
    return [dict(r) for r in checked_panel(panel)["public_rows"]]


def private_source_join(panel):
    return {r["source_id"]: dict(r) for r in checked_panel(panel)["private_records"]}


def public_context(panel, fold):
    panel = checked_panel(panel)
    require(type(fold) is int and 0 <= fold < 10, "fold0..9")
    training, queries = [], []
    for row in panel["private_records"]:
        if panel["participant_folds"][row["participant"]] == fold:
            queries.append(row["id"])
        else:
            training.append({"id": row["id"], "label": row["label"]})
    context = {"schema": CONTEXT_SCHEMA, "input_mode": MODE, "panel_sha256": panel["panel_sha256"],
               "source_binding": dict(panel["source_binding"]), "fold": fold,
               "rows": ordered_public_rows(panel), "training": training, "queries": sorted(queries)}
    context["context_sha256"] = digest(context)
    return checked_context(context)


def checked_context(context):
    fields(context, ("schema", "input_mode", "panel_sha256", "source_binding", "fold", "rows",
                     "training", "queries", "context_sha256"), "Generic context")
    require(context["schema"] == CONTEXT_SCHEMA and context["input_mode"] == MODE, "Generic context mode")
    require(sha(context["context_sha256"]) == digest({k: v for k, v in context.items() if k != "context_sha256"}), "context identity")
    sha(context["panel_sha256"]); binding(context["source_binding"])
    require(type(context["fold"]) is int and 0 <= context["fold"] < 10, "fold0..9")
    rows = context["rows"]
    require(type(rows) is list and len(rows) == 188, "188 public scalar rows")
    identities, groups = set(), {}
    for row in rows:
        fields(row, ("id", "group_id", "scalar_sha256"), "public scalar row")
        identifier = sha(row["id"]); sha(row["group_id"]); sha(row["scalar_sha256"])
        require(identifier not in identities, "unique public row")
        identities.add(identifier); groups.setdefault(row["group_id"], set()).add(identifier)
    require(rows == sorted(rows, key=lambda r: r["id"]) and len(groups) == 94
            and all(len(v) == 2 for v in groups.values()), "opaque order and94paired groups")
    train = {}
    require(type(context["training"]) is list, "ordered training rows")
    for row in context["training"]:
        fields(row, ("id", "label"), "training row")
        require(row["id"] in identities and row["id"] not in train and row["label"] in PAIR, "unique labeled training row")
        train[row["id"]] = row["label"]
    query = context["queries"]
    require(type(query) is list and query == sorted(set(query)) and query, "unique ordered held queries")
    require(set(train).isdisjoint(query) and set(train) | set(query) == identities and train, "exact training/held partition")
    for members in groups.values():
        require(members <= set(train) or members <= set(query), "no participant across training/held")
        if members <= set(train):
            require({train[i] for i in members} == set(PAIR), "paired face/object training labels")
    return context


def validate_prediction(body, context, outcome):
    require(outcome in ("reproduction", "improvement"), "declared separate outcome")
    context = checked_context(context)
    fields(body, ("schema", "input_mode", "context_sha256", "probabilities"), "classification response")
    require(body["schema"] == RESPONSE_SCHEMA and body["input_mode"] == MODE
            and body["context_sha256"] == context["context_sha256"], "matching classification context")
    probabilities = body["probabilities"]
    require(type(probabilities) is dict and set(probabilities) == set(context["queries"]), "exact held predictions")
    return {"probabilities": {i: probability(probabilities[i]) for i in context["queries"]}}


def probability(value):
    value = finite(value)
    require(0 <= value <= 1, "probability in[0,1]")
    return value


def collect(panel, predictions_by_fold, outcome):
    panel = checked_panel(panel)
    require(type(predictions_by_fold) is dict and len(predictions_by_fold) == 10
            and all(type(f) is int for f in predictions_by_fold)
            and set(predictions_by_fold) == set(range(10)), "all ten responses")
    predictions = {}
    for fold in range(10):
        probabilities = validate_prediction(predictions_by_fold[fold], public_context(panel, fold), outcome)["probabilities"]
        require(set(predictions).isdisjoint(probabilities), "held row repeated")
        predictions.update(probabilities)
    records = panel["private_records"]
    require(len(predictions) == 188 and set(predictions) == {r["id"] for r in records}, "exact188 held predictions")
    observations = [{"id": r["source_id"], "participant": r["participant"], "label": r["label"],
                     "fold": panel["participant_folds"][r["participant"]]} for r in records]
    return {"observations": observations,
            "probabilities_object": {r["source_id"]: predictions[r["id"]] for r in records}}


def reference_binding(panel):
    panel = checked_panel(panel)
    return {"input_mode": MODE, "truth_encoding": "face_object_strings",
            "source_inventory_sha256": panel["source_binding"]["sha256"], "rows": {
        r["source_id"]: {"row_key": r["row_key"], "participant": r["participant"], "label": r["label"],
                         "fold": panel["participant_folds"][r["participant"]]}
        for r in panel["private_records"]}}


def validate_frozen_folds(ledger, panel):
    """Recheck the accepted pre-fit ledger after complete transport closure."""
    panel = checked_panel(panel)
    fields(ledger, ("schema", "plans", "input_sha256"), "frozen fold ledger")
    require(ledger["schema"] == "meg-frozen-before-first-fit-v1"
            and ledger["input_sha256"] == panel["source_binding"]["sha256"], "frozen source identity")
    require(type(ledger["plans"]) is list, "frozen plans")
    plans = [p for p in ledger["plans"] if type(p) is dict and p.get("orientation") == list(ORIENTATION)]
    require(len(plans) == 1, "unique primary orientation plan")
    # This helper is the same source-only plan validator used by preparation.
    # Importing it loads no bank, predictions, model library, or candidate code.
    from generic_prepare import validate_frozen_plan
    records = [{k: r[k] for k in ("row_key", "participant", "label")} for r in panel["private_records"]]
    folds = validate_frozen_plan(records, published_participants(), plans[0])
    require(folds == panel["participant_folds"], "private panel uses the frozen reference folds")
