"""Trusted projection and participant-disjoint fold construction.

Only opaque identifiers, cell context and fixed shape signal arrays enter the
query. Private ledger and authenticated nuisance fields stay with the evaluator.
Do not mount this process's objects into an untrusted worker; isolation is a gate.
"""
import hashlib
import hmac
from collections import Counter
from contract import PEOPLE, TASKS, CELLS, CLASSES, require
from importer import validate_cohort
from windows import extract


def prepare(recordings, readers, certificates, private_nonce, *, premarker=False):
    validate_cohort(recordings)
    require(set(readers) == set(recordings) == set(certificates), "provider cohort mismatch")
    orders = {tuple(certificates[key].get("channel_names", [])) for key in certificates}
    require(len(orders) == 1 and len(next(iter(orders))) == 62,
            "all64 recordings need the same authenticated channel order")
    require(isinstance(private_nonce, bytes) and len(private_nonce) >= 32, "private nonce minimum32bytes")
    records, ledger = [], []
    for key in sorted(recordings):
        for row in recordings[key]:
            identity = row["source_identity"].encode("ascii")
            uid = hmac.new(private_nonce, b"query\0" + identity, hashlib.sha256).hexdigest()
            x = extract(readers[key], row, certificates[key], premarker=premarker)
            records.append({"id": uid, "participant": row["participant"],
                            "cell": row["cell"], "x": x, "label": row["label"]})
            ledger.append({"id": uid, **row})
    require(len({r["id"] for r in records}) == 9984, "opaque ID collision")
    # HMAC order prevents reconstructing chronology from emitted row order.
    records.sort(key=lambda r: r["id"])
    ledger.sort(key=lambda r: r["id"])
    return records, ledger


def fold(records, held_participant):
    require(held_participant in PEOPLE, "unknown outer fold")
    require(len(records) == 9984 and len({r["id"] for r in records}) == 9984,
            "full nominal cohort required; no silent exclusions")
    counts = Counter((r["participant"], r["cell"], r["label"]) for r in records)
    require(set(counts) == {(p, c, y) for p in PEOPLE for c in CELLS for y in range(CLASSES)}
            and set(counts.values()) == {2}, "complete participant/cell/class coverage")
    train, query, targets = [], [], []
    for r in records:
        if r["participant"] == held_participant:
            query.append({k: r[k] for k in ("id", "cell", "x")})
            targets.append({k: r[k] for k in ("id", "participant", "cell", "label")})
        else:
            train.append({k: r[k] for k in ("id", "participant", "cell", "x", "label")})
    return {"training": train, "query": query}, targets


def grouped_validation_people(held_participant):
    require(held_participant in PEOPLE, "unknown outer fold")
    # Deterministic training-only leave-person-out inner roster. No held labels.
    people = [p for p in PEOPLE if p != held_participant]
    return [(tuple(p for p in people if p != valid), (valid,)) for valid in people]
