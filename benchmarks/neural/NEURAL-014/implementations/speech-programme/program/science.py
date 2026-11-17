"""Captured unchanged NEURAL014 scientific contract functions; no actual inputs."""
import hashlib,hmac,json,unicodedata,math,re
from collections import Counter

SCHEMA = "neural014-v1"

ARMS = ("full_fixed", "full_adapt", "loss_fixed", "loss_adapt",
        "shuffle_adapt", "zero_adapt", "language_prior")

CALIBRATION_PREFIX = 20

FEATURES = 512

LOSS_COLUMNS = tuple(sorted(sorted(range(FEATURES), key=lambda j:
    hashlib.sha256(("neural014-feature-loss-v1|" + str(j)).encode()).digest())[:128]))

MAX_CASES = 50_000

MAX_STEPS = 100_000

MAX_JSON = 64_000_000

MAX_DP_CELLS = 256_000_000

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()

def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def sentence_key(text):
    require(type(text) is str and 0 < len(text) <= 16384 and "\x00" not in text, "Complete bounded transcript required")
    normalized = " ".join(unicodedata.normalize("NFC", text).casefold().split())
    require(bool(normalized), "Empty normalized transcript")
    return hashlib.sha256(normalized.encode()).hexdigest()

def opaque(secret, values):
    require(type(secret) is bytes and len(secret) == 32, "32-byte operator secret required")
    return hmac.new(secret, b"neural014|" + canonical(values), hashlib.sha256).hexdigest()

def assign(records, sessions):
    """Pure private assignment; preserve suffix, never replace excluded prefix."""
    require(type(records) is list and 0 < len(records) <= MAX_CASES, "Bounded full source roster")
    require(len(sessions) == 45 and [s["role"] for s in sessions] ==
            ["train"] * 27 + ["development"] * 9 + ["query"] * 9, "Full chronological45 sessions")
    by_session = {r["source_session"]: [] for r in sessions}
    require(len(by_session) == 45, "Unique source sessions")
    used = set()
    for row in records:
        key = (row["session"], row["block_num"], row["trial_num"])
        require(key[0] in by_session and key not in used, "Unique known session/block/trial")
        require(all(type(n) is int and n >= 0 for n in key[1:]), "Integer block/trial chronology")
        used.add(key)
        item = dict(row, sentence_key=sentence_key(row["transcription"]))
        by_session[key[0]].append(item)
    partitioned = []
    for spec in sessions:
        rows = sorted(by_session[spec["source_session"]], key=lambda x: (x["block_num"], x["trial_num"]))
        require(bool(rows), "Every declared source session requires support")
        for i, row in enumerate(rows):
            role = spec["role"]
            if role == "query":
                role = "calibration" if i < CALIBRATION_PREFIX else "query"
            partitioned.append(dict(row, role=role, session_id=spec["session_id"], source_ordinal=i))
    # Query suffix wins globally, then all calibration identities, then dev.
    # No candidate can change this roster; all arms share exactly these queries.
    rank = {"train": 0, "development": 1, "calibration": 2, "query": 3}
    highest = {}
    for row in partitioned:
        k = row["sentence_key"]
        highest[k] = max(highest.get(k, -1), rank[row["role"]])
    kept, excluded = [], []
    for row in partitioned:
        if rank[row["role"]] == highest[row["sentence_key"]]:
            kept.append(row)
        else:
            excluded.append({"source_key": [row["session"], row["block_num"], row["trial_num"]],
                             "role": row["role"], "reason": "same_sentence_in_higher_priority_partition"})
    for spec in sessions:
        needed = ("calibration", "query") if spec["role"] == "query" else (spec["role"],)
        for role in needed:
            require(any(r["session_id"] == spec["session_id"] and r["role"] == role for r in kept),
                    "Complete endpoint unavailable: empty required session/partition after grouping")
    return kept, excluded

def context_id(generation, session, arm, query_ids):
    require(arm in ARMS, "Known arm")
    return fingerprint({"schema": SCHEMA, "generation": generation, "session": session,
                        "arm": arm, "query_ids": query_ids})

MAX_TOKENS = 2048

SOURCE_CLASSES = ('BLANK', 'AA', 'AE', 'AH', 'AO', 'AW', 'AY', 'B', 'CH',
                  'D', 'DH', 'EH', 'ER', 'EY', 'F', 'G', 'HH', 'IH', 'IY',
                  'JH', 'K', 'L', 'M', 'N', 'NG', 'OW', 'OY', 'P', 'R',
                  'S', 'SH', 'T', 'TH', 'UH', 'UW', 'V', 'W', 'Y', 'Z',
                  'ZH', ' | ')

TOKENS = tuple(x.strip() for x in SOURCE_CLASSES[1:])

TOKEN_SET = frozenset(TOKENS)

class ContractError(ValueError):
    pass

def need(ok, why):
    if not ok:
        raise ContractError(why)

def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def normalize_tokens(value):
    """Formatting only: ASCII case and whitespace. No stress/CTC/LM repair."""
    if type(value) is str:
        need(len(value) <= MAX_TOKENS * 8 and value.isascii(), 'bounded ASCII token string')
        parts = value.split()
    else:
        need(type(value) is list and len(value) <= MAX_TOKENS, 'token list or whitespace string')
        parts = value
    need(len(parts) <= MAX_TOKENS, 'token count exceeds declared interface bound')
    result = []
    for token in parts:
        need(type(token) is str and len(token) <= 8 and token.isascii(), 'ASCII token required')
        token = token.strip().upper()
        need(token in TOKEN_SET, 'unknown token, stress suffix or CTC blank')
        result.append(token)
    return result

def labels_from_source(ids, seq_len):
    need(type(seq_len) is int and 0 < seq_len <= len(ids) <= MAX_TOKENS,
         'positive bounded source seq_len')
    need(all(type(x) is int for x in ids), 'integer source class IDs')
    need(all(1 <= x < len(SOURCE_CLASSES) for x in ids[:seq_len]),
         'source target prefix must contain only classes1..40')
    need(all(x == 0 for x in ids[seq_len:]), 'nonzero values beyond source seq_len')
    return [SOURCE_CLASSES[x].strip() for x in ids[:seq_len]]

def edit_counts(reference, prediction):
    """Unit-cost Levenshtein; tie order diagonal, deletion, insertion.

    Only total distance is unique in general. I/D/S are a deterministic minimum
    alignment decomposition, not independently observed phonetic events.
    """
    previous = [(j, 0, 0, j) for j in range(len(prediction) + 1)]
    for i, ref in enumerate(reference, 1):
        current = [(i, 0, i, 0)]
        for j, pred in enumerate(prediction, 1):
            d, s, deletion, insertion = previous[j - 1]
            sub = int(ref != pred)
            diagonal = (d + sub, s + sub, deletion, insertion)
            d, s, deletion, insertion = previous[j]
            drop = (d + 1, s, deletion + 1, insertion)
            d, s, deletion, insertion = current[-1]
            add = (d + 1, s, deletion, insertion + 1)
            current.append(min((diagonal, drop, add), key=lambda x: x[0]))
        previous = current
    d, s, deletion, insertion = previous[-1]
    return {'distance': d, 'substitutions': s, 'deletions': deletion, 'insertions': insertion}

HEX = re.compile(r"[0-9a-f]{64}\Z")

def suite_contexts(suite):
    require(type(suite) is dict and set(suite) == {"schema", "generation", "contexts"} and
            suite["schema"] == "neural014-suite-v1" and type(suite["generation"]) is str and HEX.fullmatch(suite["generation"]), "Exact suite generation")
    rows = suite["contexts"]
    require(type(rows) is list and len(rows) == 63, "All9 sessions×7 arms")
    result = {}; joined = {}; all_ids = set()
    for r in rows:
        require(type(r) is dict and set(r) == {"session", "arm", "query_ids", "context_id"}, "Exact context fields")
        s, arm, ids = r["session"], r["arm"], r["query_ids"]
        require(s in [f"session-{i:03}" for i in range(37, 46)] and arm in ARMS and (s, arm) not in result, "Unique complete arm/session")
        require(type(ids) is list and 0 < len(ids) <= 50000 and all(type(i) is str and HEX.fullmatch(i) for i in ids)
                and ids == sorted(set(ids)), "Complete sorted opaque query IDs")
        require(r["context_id"] == context_id(suite["generation"], s, arm, ids), "Bound context fingerprint")
        if s in joined: require(ids == joined[s], "All arms use identical query support")
        else:
            require(not (set(ids) & all_ids), "No query case belongs to two sessions")
            joined[s] = ids; all_ids.update(ids)
        result[(s, arm)] = r
    require(len(all_ids) <= 50000, "Full query count bound")
    return result

def admit(contexts, candidates):
    require(type(candidates) is dict and set(candidates) == {r["context_id"] for r in contexts.values()}, "Every63 candidate output required")
    predictions = {}
    for pair, r in contexts.items():
        answer = candidates[r["context_id"]]
        require(type(answer) is dict and set(answer) == {"schema", "context_id", "predictions"} and
                answer["schema"] == "neural014-predictions-v1" and answer["context_id"] == r["context_id"], "Exact candidate/context join")
        rows = answer["predictions"]
        require(type(rows) is list and len(rows) == len(r["query_ids"]), "Every query prediction required")
        out = {}; expected_ids = set(r["query_ids"])
        for row in rows:
            require(type(row) is dict and set(row) == {"id", "tokens"} and
                    type(row["id"]) is str and row["id"] in expected_ids and row["id"] not in out, "Unique known prediction ID")
            out[row["id"]] = normalize_tokens(row["tokens"])
        require(set(out) == set(r["query_ids"]), "No missing/extra predictions")
        if r["arm"] == "language_prior":
            require(len({tuple(v) for v in out.values()}) == 1, "Unconditioned language prior must be identical across query IDs")
        predictions[pair] = out
    return predictions

def score(suite, candidates, load_gold):
    contexts = suite_contexts(suite)
    predictions = admit(contexts, candidates)
    gold = load_gold()
    require(type(gold) is dict and set(gold) == {"schema", "generation", "targets"} and
            gold["schema"] == "neural014-gold-v1" and gold["generation"] == suite["generation"], "Private generation join")
    ids = {i for r in contexts.values() for i in r["query_ids"]}
    require(type(gold["targets"]) is list and len(gold["targets"]) == len(ids), "Full private support")
    targets = {}
    for r in gold["targets"]:
        require(type(r) is dict and set(r) == {"id", "tokens"} and type(r["id"]) is str and r["id"] in ids and r["id"] not in targets, "Unique private target join")
        targets[r["id"]] = normalize_tokens(r["tokens"])
        require(bool(targets[r["id"]]), "Empty private target denies whole endpoint")
    cells = sum((len(targets[i]) + 1) * (len(p) + 1) for pred in predictions.values() for i, p in pred.items())
    if cells > MAX_DP_CELLS:
        return {"status": "unsupported_complexity", "primary_PER": None, "cells": cells,
                "reason": "Complete63-context DP budget exceeded; no truncation/partial score"}
    sessions = {}
    for (session, arm), pred in predictions.items():
        totals = {k: 0 for k in ("distance", "substitutions", "deletions", "insertions")}
        for key, p in pred.items():
            for k, value in edit_counts(targets[key], p).items(): totals[k] += value
        denominator = sum(len(targets[i]) for i in pred)
        sessions.setdefault(session, {})[arm] = {**totals, "reference_tokens": denominator,
                                               "trials": len(pred), "PER": totals["distance"] / denominator}
    for s, arms in sessions.items():
        arms["contrasts"] = contrasts({a: arms[a]["PER"] for a in ARMS})
    macro = {a: math.fsum(v[a]["PER"] for v in sessions.values()) / 9 for a in ARMS}
    return {"status": "scored", "generation": suite["generation"], "primary_metric": "adapted_full_session_macro_PER", "direction": "lower",
        "primary_PER": macro["full_adapt"], "arm_macro_PER": macro, "paired_contrasts": contrasts(macro),
        "sessions": sessions, "query_trials": len(ids), "query_sessions": 9, "participants": 1,
        "cost_accounting": {"status": "requires_separate_trusted_execution_capture", "measured_cost": None},
        "qualified_adaptation_gain": None, "qualified_neural_dependence": None, "comparator_competence_verified": False,
        "causal_drift_or_population_claim": False, "p_values": None, "confidence_intervals": None,
        "checkpoint_and_isolation_replay_verified": False, "scientific_threshold": None}

def contrasts(p):
    # Positive numbers mean the named adaptation/content comparison improved.
    return {"adaptation_gain_full": p["full_fixed"] - p["full_adapt"],
            "adaptation_gain_loss": p["loss_fixed"] - p["loss_adapt"],
            "loss_penalty_fixed": p["loss_fixed"] - p["full_fixed"],
            "loss_penalty_adapted": p["loss_adapt"] - p["full_adapt"],
            "temporal_order_penalty_conditional_on_length": p["shuffle_adapt"] - p["full_adapt"],
            "neural_zero_penalty_conditional_on_length": p["zero_adapt"] - p["full_adapt"],
            "language_prior_minus_adapted": p["language_prior"] - p["full_adapt"]}

def validate_pool(pool):
    require(type(pool) is dict and set(pool) == {"schema", "generation", "sessions", "rows"} and
            pool["schema"] == SCHEMA and type(pool["generation"]) is str and HEX.fullmatch(pool["generation"]), "Exact private pool")
    specs = pool["sessions"]
    require(type(specs) is list and len(specs) == 45 and [s["session_id"] for s in specs] ==
            [f"session-{i:03}" for i in range(1, 46)] and [s["role"] for s in specs] ==
            ["train"] * 27 + ["development"] * 9 + ["query"] * 9, "Full chronological session roster")
    roles = {s["session_id"]: s["role"] for s in specs}
    require(type(pool["rows"]) is list and 0 < len(pool["rows"]) <= 50000, "Bounded full rows")
    seen = set(); support = set()
    for r in pool["rows"]:
        require(type(r) is dict and set(r) == {"id", "session", "role", "steps", "features", "tokens", "sentence_key", "source_key", "ordinal"}, "Exact private row")
        require(type(r["id"]) is str and HEX.fullmatch(r["id"]) and r["id"] not in seen and r["session"] in roles, "Unique known row")
        allowed = ("calibration", "query") if roles[r["session"]] == "query" else (roles[r["session"]],)
        require(r["role"] in allowed and type(r["ordinal"]) is int and r["ordinal"] >= 0 and
                (r["role"] != "calibration" or r["ordinal"] < 20) and
                (r["role"] != "query" or r["ordinal"] >= 20), "Fixed prefix/suffix assignment")
        require(bool(normalize_tokens(r["tokens"])) and type(r["steps"]) is int and 0 < r["steps"] <= 100000, "Complete target/geometry")
        require(type(r["sentence_key"]) is str and HEX.fullmatch(r["sentence_key"]), "Exact private sentence identity")
        seen.add(r["id"]); support.add((r["session"], r["role"]))
    for s, role in roles.items():
        for r in (("calibration", "query") if role == "query" else (role,)):
            require((s, r) in support, "No missing session/partition")
    groups = {}
    for r in pool["rows"]:
        groups.setdefault(r["sentence_key"], set()).add(r["role"])
    require(all(len(v) == 1 for v in groups.values()), "Cross-partition exact sentence overlap")

def select(pool, session, arm):
    validate_pool(pool)
    if arm == "base":
        require(session is None, "Base view has no later session")
        return [r for r in pool["rows"] if r["role"] in ("train", "development")]
    require(arm in ARMS and session in [f"session-{i:03}" for i in range(37, 46)], "Fixed later session/arm")
    selected = [r for r in pool["rows"] if r["session"] == session and r["role"] == "query"]
    if arm not in ("full_fixed", "loss_fixed"):
        selected += [r for r in pool["rows"] if r["session"] == session and r["role"] == "calibration"]
    if arm == "language_prior":
        selected += [r for r in pool["rows"] if r["role"] == "train"]
    return sorted(selected, key=lambda r: r["id"])
