"""Shared positive schemas. A source identity never certifies authentic custody."""
import hashlib
import json
import math
from copy import deepcopy

CONDITIONS = ("SH", "SHN", "SBH", "SBHN")
ARMS = ("F", "I")
GATES = tuple("G%02d" % i for i in range(1, 25))
STATUS = "source_only_unqualified"

def need(ok, message):
    if not ok:
        raise ValueError(message)

def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode()

def pin(value):
    body = value if type(value) is bytes else canonical(value)
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}

def finite(value):
    return type(value) in (int, float) and math.isfinite(value)

def probability(value):
    need(finite(value) and 0 <= value <= 1, "finite probability in [0,1]")
    return float(value)

def identity(value):
    need(type(value) in (str, dict), "explicit source identity")
    need(bool(value), "nonempty source identity")
    canonical(value)
    return deepcopy(value)

def member_map(members):
    need(type(members) in (list, tuple) and len(members) == 29, "complete29 roster")
    need(pin(list(members))["sha256"] ==
         "2d7b37af47a41fceedef09c4591984b942ee40ab2d3ea5530827e8f7dd32db58",
         "exact original ordered asset descriptor roster")
    by_id = {}
    for m in members:
        need(type(m) is dict and all(type(m.get(k)) is str and m[k]
             for k in ("eid", "subject", "lab")), "complete roster identities")
        need(m["eid"] not in by_id, "duplicate session")
        by_id[m["eid"]] = m
    need(len({m["subject"] for m in members}) == 13, "complete13 animals")
    need(len({m["lab"] for m in members}) == 7, "complete7 labs")
    return by_id

def check_prepared(sessions, members):
    expected = member_map(members)
    need(type(sessions) in (list, tuple) and len(sessions) == 29, "all29 prepared")
    need([s["session_id"] for s in sessions] == [m["eid"] for m in members],
         "original roster order and exact sessions")
    for s in sessions:
        m = expected[s["session_id"]]
        need(s["subject_id"] == m["subject"] and s["lab"] == m["lab"],
             "session/animal/lab join")
        identity(s["source_identity"])
        need(type(s["unit_ids"]) is list and s["unit_ids"] and
             len(s["unit_ids"]) == len(set(s["unit_ids"])), "full distinct units")
        need(type(s["slots"]) is list and type(s["cases"]) is list, "full source rows")
        need([x["ordinal"] for x in s["slots"]] == list(range(len(s["slots"]))),
             "all original sorted slots")
        seen = set()
        for c in s["cases"]:
            need(c["case_id"] not in seen, "unique case")
            seen.add(c["case_id"])
            need(type(c["ordinal"]) is int and 0 <= c["ordinal"] < len(s["slots"]),
                 "case original ordinal")
            need(c["split"] in ("train", "val", "test"), "selected split")
            need(type(c["y"]) is int and c["y"] in (0, 1), "choice axis")
            need(len(c["N"]) == len(s["unit_ids"]), "all units retained")
        need([c["ordinal"] for c in s["cases"]] == sorted(c["ordinal"] for c in s["cases"]),
             "original case chronology")
    return expected

def inspect_status():
    return {"status": STATUS, "scientific_ready": False, "source_complete": False,
            "activation": False, "run": None, "score": None, "program_execution": None,
            "sessions": 29, "animals": 13, "labs": 7, "conditions": list(CONDITIONS),
            "reference_fit_slots": 61132, "open_gates": list(GATES)}
