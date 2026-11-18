"""Compare T15 source block counts without loading labels or neural arrays.

This is a pure operator metadata check. Header rows must come from separately
authenticated source files; this module cannot establish that acquisition or
header extraction occurred. A successful comparison is not task admission.
"""
from __future__ import annotations

import csv
from datetime import date
import hashlib
import io
import json
import re

ARCHIVE_SHA256 = "fb828fa7ef937aca405d6912addc876f6747f75a8a1711f6d2052aacf34ec5b5"
MEMBER_LIST_SHA256 = "462a4609b31e6cbbbdcb07a67621c39c9fdcbecb28943e7e716586e7a03751f4"
README_SENTENCE_COUNT = 10948
MAX_TRIALS = 50000
MAX_JSON = 8 * 1024 * 1024
MAX_CSV = 256 * 1024
HEX = re.compile(r"[0-9a-f]{64}\Z")
MEMBER = re.compile(r"hdf5_data_final/(t15\.(\d{4})\.(\d{2})\.(\d{2}))/data_(train|val|test)\.hdf5\Z")
GROUP = re.compile(r"trial_[0-9]{4,6}\Z")
CSV_FIELDS = ("Date", "Post-implant day", "Block number", "Number of sentences", "Corpus", "Split")


def need(condition, why):
    if not condition:
        raise ValueError(why)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def parse(body, cap):
    need(type(body) is bytes and 0 < len(body) <= cap, "bounded captured JSON bytes")
    def invalid_constant(value):
        raise ValueError("nonfinite JSON constant: " + value)
    return json.loads(body, object_pairs_hook=unique_pairs, parse_constant=invalid_constant)


def source_members(task_body):
    task = parse(task_body, 256 * 1024)
    need(task.get("id") == "NEURAL-014", "NEURAL-014 task source required")
    records = task["input_assets"]["readiness_records"]
    need(type(records) is list and len(records) == 1 and records[0]["source_id"] == "D-N052",
         "exact T15 source record")
    manifest = records[0]["data_manifest"]
    archives = [r for r in manifest["files"] if r.get("name") == "t15_copyTask_neuralData.zip"]
    need(len(archives) == 1 and archives[0]["bytes"] == 11051034483
         and archives[0]["sha256"] == ARCHIVE_SHA256, "frozen original archive")
    members = manifest["neural_archive_members"]
    need(type(members) is list and len(members) == 127, "complete127-member source roster")
    need(hashlib.sha256(canonical(sorted(members, key=lambda r: r["name"]))).hexdigest()
         == MEMBER_LIST_SHA256, "unchanged frozen member names and extents")
    result = {}
    for row in members:
        match = MEMBER.fullmatch(row["name"])
        need(match is not None and row["name"] not in result, "ordinary unique source member")
        session, year, month, day, split = match.groups()
        day_string = date(int(year), int(month), int(day)).isoformat()
        result[row["name"]] = {"bytes": row["size"], "session": session,
                               "date": day_string, "split": split}
    need(len({r["session"] for r in result.values()}) == 45, "all45 original sessions")
    return result


def number(text, label, *, positive=False):
    need(type(text) is str and re.fullmatch(r"0|[1-9][0-9]*", text) is not None,
         "canonical integer CSV " + label)
    value = int(text)
    need((value > 0 if positive else value >= 0) and value <= MAX_TRIALS,
         "bounded CSV " + label)
    return value


def blocks(csv_body, expected_dates):
    need(type(csv_body) is bytes and 0 < len(csv_body) <= MAX_CSV, "bounded author CSV bytes")
    reader = csv.DictReader(io.StringIO(csv_body.decode("utf-8"), newline=""))
    need(tuple(reader.fieldnames or ()) == CSV_FIELDS, "exact author CSV columns")
    result = {}
    for row in reader:
        need(len(result) < MAX_TRIALS and set(row) == set(CSV_FIELDS)
             and all(type(value) is str for value in row.values()), "complete bounded CSV row")
        day = row["Date"]
        need(date.fromisoformat(day).isoformat() == day and day in expected_dates,
             "known canonical source date")
        block = number(row["Block number"], "block")
        number(row["Post-implant day"], "post-implant day")
        total = number(row["Number of sentences"], "sentence count", positive=True)
        need(row["Split"] in ("Train", "Val/Test"), "author Train or combined Val/Test split")
        need(0 < len(row["Corpus"]) <= 128 and "\x00" not in row["Corpus"], "bounded corpus label")
        key = (day, block)
        need(key not in result, "duplicate author date/block")
        result[key] = {"declared": total, "split": row["Split"], "corpus": row["Corpus"]}
    need({key[0] for key in result} == expected_dates, "author CSV covers all45 source dates")
    need(sum(r["declared"] for r in result.values()) <= MAX_TRIALS, "bounded full declared count")
    return result


def reconcile(task_body, csv_body, header_body):
    """Compare a complete labeled-only or all-source metadata inventory.

    No transcript, token, signal, array or score field is accepted. Native trial
    identity must be unique across files, including train/val/test. Differences
    remain explicit; neither a matching global sum nor a nominal loader count
    authorizes dropping observations or amending source splits.
    """
    members = source_members(task_body)
    declared = blocks(csv_body, {r["date"] for r in members.values()})
    doc = parse(header_body, MAX_JSON)
    need(type(doc) is dict and set(doc) == {"schema", "coverage", "archive_sha256", "members"}
         and doc["schema"] == "neural014-trial-header-census-v1", "exact header census schema")
    coverage = doc["coverage"]
    need(coverage in ("labeled_train_val", "all_source_members"), "explicit census coverage")
    need(doc["archive_sha256"] == ARCHIVE_SHA256, "exact declared archive identity")
    expected = {name for name, row in members.items()
                if coverage == "all_source_members" or row["split"] != "test"}
    rows = doc["members"]
    need(type(rows) is list and len(rows) == len(expected), "every selected source member required")
    seen_members, seen_trials = set(), set()
    observed = {key: {"train": 0, "val": 0, "test": 0} for key in declared}
    for row in rows:
        need(type(row) is dict and set(row) == {"name", "bytes", "sha256", "trials"},
             "exact member metadata fields")
        name = row["name"]
        need(type(name) is str and name in expected and name not in seen_members,
             "unique selected source member")
        spec = members[name]
        need(type(row["bytes"]) is int and row["bytes"] == spec["bytes"]
             and type(row["sha256"]) is str and HEX.fullmatch(row["sha256"]),
             "original extent and explicit member byte-identity claim")
        seen_members.add(name)
        trials = row["trials"]
        need(type(trials) is list and len(trials) <= 5000, "bounded complete member trial list")
        seen_groups = set()
        for trial in trials:
            need(type(trial) is dict and set(trial) == {"group", "session", "block_num", "trial_num"},
                 "only native identity metadata permitted")
            group = trial["group"]
            need(type(group) is str and GROUP.fullmatch(group) and group not in seen_groups,
                 "ordinary unique trial group")
            seen_groups.add(group)
            need(trial["session"] == spec["session"], "file and native session join")
            need(all(type(trial[k]) is int and 0 <= trial[k] <= MAX_TRIALS
                     for k in ("block_num", "trial_num")), "native integer identity")
            native_key = (trial["session"], trial["block_num"], trial["trial_num"])
            need(native_key not in seen_trials, "duplicate native trial across source files")
            seen_trials.add(native_key)
            need(len(seen_trials) <= MAX_TRIALS, "bounded complete source trials")
            block_key = (spec["date"], trial["block_num"])
            need(block_key in declared, "source trial block missing from author CSV")
            split = spec["split"]
            need((split == "train") == (declared[block_key]["split"] == "Train"),
                 "observed file split disagrees with author block split")
            observed[block_key][split] += 1
    need(seen_members == expected, "complete selected member coverage")
    comparisons = []
    for key, row in sorted(declared.items()):
        counts = observed[key]
        total = sum(counts.values())
        complete_block = row["split"] == "Train" or coverage == "all_source_members"
        comparisons.append({"date": key[0], "block_num": key[1], "corpus": row["corpus"],
            "source_split": row["split"], "declared_count": row["declared"],
            "observed_by_split": counts, "observed_count": total,
            "comparison": "exact" if complete_block else "lower_bound_without_official_test",
            "observed_minus_declared": total - row["declared"] if complete_block else None,
            "unobserved_or_discrepant_count": None if complete_block else row["declared"] - total,
            "within_declared_bound": total <= row["declared"],
            "matches": total == row["declared"] if complete_block else None})
    full = coverage == "all_source_members"
    declared_total = sum(r["declared"] for r in declared.values())
    exact = [r for r in comparisons if r["comparison"] == "exact"]
    return {"schema": "neural014-source-count-comparison-v1", "task_id": "NEURAL-014",
        "status": "complete_comparison" if full else "partial_comparison_official_test_unobserved",
        "source_inputs": {"task": pin(task_body), "author_csv": pin(csv_body), "header_inventory": pin(header_body)},
        "coverage": coverage, "source_member_count": len(rows), "source_sessions": 45,
        "observed_trial_count": len(seen_trials), "csv_declared_count": declared_total,
        "readme_declared_count": README_SENTENCE_COUNT,
        "csv_minus_readme": declared_total - README_SENTENCE_COUNT,
        "observed_minus_readme": len(seen_trials) - README_SENTENCE_COUNT if full else None,
        "all_exact_blocks_match": all(r["matches"] for r in exact),
        "all_lower_bounds_valid": all(r["within_declared_bound"] for r in comparisons if r["matches"] is None),
        "all_source_blocks_match": all(r["matches"] for r in comparisons) if full else None,
        "blocks": comparisons,
        "source_exclusions_inferred": False, "source_payload_authentication_established": False,
        "neural_values_read_by_this_function": False, "scientific_qualified": False,
        "scope": "Pure comparison of supplied identity metadata; independent authenticated source extraction remains required."}
