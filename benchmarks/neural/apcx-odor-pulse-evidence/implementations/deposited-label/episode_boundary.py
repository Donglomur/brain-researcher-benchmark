"""One target-free session episode and closed result envelope.

This module contains no owner targets, original identity map or filesystem access.
It is mounted with the reference program; only the selected session is supplied.
"""
import hashlib
import json
import math
import re

PROFILE = "apcx-deposited-total-pulse-within-session-v1"
CONTRACT = "f7338d33fc67d7bc231e1bba7344f30f9c70ce5362f169998dc2b4302c042d0b"
DOCUMENT = "80bbffc26ff7cf444ebb5db87f1af1e615d19518dd70e0934462064886221934"
HEX = re.compile("[0-9a-f]{64}")
CONDITIONS = ("matched", "full_calibration")
MAX_EPISODE_BYTES = 2 * 1024**2
MAX_RESULT_BYTES = 4 * 1024**2


def need(value, reason):
    if not value:
        raise ValueError(reason)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def closed(value, keys):
    need(type(value) is dict and set(value) == set(keys), "closed episode schema")


def identifier(value):
    need(type(value) is str and HEX.fullmatch(value) is not None, "exact opaque identifier")


def integer(value):
    need(type(value) is int and 0 <= value < 2**31, "exact nonnegative int32")


def validate_episode(e):
    closed(e, ("schema", "profile", "profile_contract_sha256", "profile_document_sha256",
               "condition", "participant_packet_sha256", "invented", "session", "documentation_utf8"))
    need(e["schema"] == "apcx-one-public-session-v1" and e["profile"] == PROFILE
         and e["profile_contract_sha256"] == CONTRACT and e["profile_document_sha256"] == DOCUMENT,
         "exact declared deposited profile")
    need(type(e["documentation_utf8"]) is str and
         hashlib.sha256(e["documentation_utf8"].encode()).hexdigest() == DOCUMENT,
         "complete identical public documentation")
    need(e["condition"] in CONDITIONS and type(e["invented"]) is bool, "condition and provenance")
    identifier(e["participant_packet_sha256"])
    s = e["session"]
    closed(s, ("session_id", "channel_ids", "calibration", "development", "queries"))
    identifier(s["session_id"])
    units = s["channel_ids"]
    need(type(units) is list and 1 <= len(units) <= 19 and len(set(units)) == len(units),
         "complete released channel basis")
    for value in units:
        identifier(value)
    seen = set()
    for name, maximum in (("calibration", 220), ("development", 73), ("queries", 74)):
        rows = s[name]
        need(type(rows) is list and 1 <= len(rows) <= maximum, "complete bounded trial split")
        need([x.get("case_id") for x in rows if type(x) is dict] ==
             sorted(x.get("case_id") for x in rows if type(x) is dict), "canonical public case order")
        for row in rows:
            closed(row, ("case_id", "spikes") if name == "queries" else
                   ("case_id", "spikes", "count", "high"))
            identifier(row["case_id"])
            need(row["case_id"] not in seen, "distinct trial across all splits")
            seen.add(row["case_id"])
            matrix = row["spikes"]
            need(type(matrix) is list and len(matrix) == len(units), "every declared session unit")
            for vector in matrix:
                need(type(vector) is list and len(vector) == 90, "every observed 50ms bin")
                for count in vector:
                    integer(count)
            if name != "queries":
                integer(row["count"])
                need(type(row["high"]) is int and row["high"] == int(row["count"] >= 9),
                     "support label-derived category")
    if e["condition"] == "matched":
        need(len(s["calibration"]) == 16 and len(s["development"]) == 8, "matched support16/8")
    need(len(s["queries"]) >= 10, "whole protected-session quota")
    return e


def from_public_packet(packet):
    # Trusted owner validates the complete original packet with the existing
    # profile auditor before calling this pure one-session projection.
    packet_sha = digest(packet)
    common = {"schema": "apcx-one-public-session-v1", "profile": packet["profile"],
              "profile_contract_sha256": packet["profile_contract_sha256"],
              "profile_document_sha256": packet["documentation_sha256"],
              "condition": packet["condition"], "participant_packet_sha256": packet_sha,
              "invented": packet["invented"], "documentation_utf8": packet["documentation_utf8"]}
    episodes = [{**common, "session": s} for s in packet["sessions"]]
    for e in episodes:
        validate_episode(e)
    need(len({e["session"]["session_id"] for e in episodes}) == len(episodes), "unique complete session set")
    return episodes


def validate_candidate_records(episode, records):
    """Reusable participant return boundary; no missing-case success."""
    validate_episode(episode)
    expected = {r["case_id"] for r in episode["session"]["queries"]}
    need(type(records) is list and len(records) == len(expected), "every protected query required")
    seen = set()
    for row in records:
        closed(row, ("case_id", "count"))
        cid = row["case_id"]
        need(cid in expected and cid not in seen, "unique expected participant query")
        seen.add(cid)
        value = row["count"]
        need(type(value) in (int, float) and math.isfinite(value), "finite participant prediction")
    need(seen == expected, "complete participant query support")
    return records
