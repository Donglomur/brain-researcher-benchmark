"""Authenticate original ZuCo2 materials and join ordered recording text metadata.

No EEG, gaze, targets, candidate predictions, or model fitting are read here.
CSV prefixes are retained; their recording/practice roles are not inferred.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import unicodedata

CONDITIONS = ("NR", "TSR")
PEOPLE = ("YAC", "YAG", "YAK", "YDG", "YDR", "YFR", "YFS", "YHS", "YIS",
          "YLS", "YMD", "YMS", "YRH", "YRK", "YRP", "YSD", "YSL", "YTL")
COUNTS = {"NR": 349, "TSR": 390}
NAMES = tuple(f"{c.lower()}_{b}.csv" for c in CONDITIONS for b in range(1, 8))


class SourceError(ValueError):
    """A source or identity invariant was not satisfied."""


def require(condition, message):
    if not condition:
        raise SourceError(message)


def exact_text(text):
    require(type(text) is str and 0 < len(text) <= 10000, "invalid sentence text")
    result = " ".join(unicodedata.normalize("NFKC", text).split())
    require(bool(result), "empty normalized sentence")
    return result


def text_id(text):
    return hashlib.sha256(exact_text(text).encode("utf-8")).hexdigest()


def group_id(text):
    # Diagnostic only. This punctuation/case-insensitive identity cannot define J.
    grouped = " ".join(re.sub(r"[^\w]+", " ", exact_text(text).casefold()).split())
    return hashlib.sha256(grouped.encode("utf-8")).hexdigest()


def read_ordinary(path, cap):
    path = Path(path).absolute()
    require(not path.is_symlink() and not any(p.is_symlink() for p in path.parents),
            "ordinary source path required")
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= cap, "bounded regular source required")
    with path.open("rb") as stream:
        raw = stream.read(cap + 1)
    after = path.stat()
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    require(len(raw) <= cap and identity(before) == identity(after), "source changed during read")
    return raw


def load_materials(source, pins, quote_policy):
    """Return every original CSV record, authenticated before parsing."""
    require(quote_policy in ("literal_quotes", "legacy_csv"), "explicit quote policy required")
    entries = pins["files"]
    require(len(entries) == 14 and {p["name"] for p in entries} == set(NAMES),
            "exact fourteen material pins required")
    by_name = {p["name"]: p for p in entries}
    rows = []
    for condition in CONDITIONS:
        material_index = 0
        legacy_index = 0
        for block in range(1, 8):
            name = f"{condition.lower()}_{block}.csv"
            pin = by_name[name]
            require(type(pin["bytes"]) is int and 0 < pin["bytes"] <= 1024 * 1024,
                    "bounded material pin required")
            require(pin["version"] == 1, "original version one materials required")
            raw = read_ordinary(Path(source) / name, pin["bytes"])
            require(len(raw) == pin["bytes"] and hashlib.sha256(raw).hexdigest() == pin["sha256"],
                    f"material identity mismatch: {name}")
            # The authenticated source includes unescaped quotations that fail
            # strict CSV parsing. Preserve two interpretations until recording
            # content establishes which text was actually presented.
            decoded = raw.decode("utf-8-sig")
            if quote_policy == "literal_quotes":
                # Literal source-line interpretation keeps both sentence quotes
                # and internal semicolons. The first two source identifiers and
                # final annotation delimit the text. It is not claimed to be
                # the presentation application's parser.
                reader = []
                for line in decoded.splitlines():
                    prefix = line.split(";", 2)
                    require(len(prefix) == 3 and all(x.isdecimal() for x in prefix[:2]),
                            "literal material identifier fields required")
                    reader.append(prefix[:2] + prefix[2].rsplit(";", 1))
            else:
                reader = csv.reader(io.StringIO(decoded, newline=""), delimiter=";", strict=False)
            block_count = 0
            for record_number, fields in enumerate(reader, 1):
                require(len(fields) == 4, f"four source fields required: {name}:{record_number}")
                literal = fields[2]
                prefix = record_number <= 3
                rows.append({
                    "source_record_id": f"{name}:{record_number}", "quote_policy": quote_policy,
                    "condition": condition, "block_within_condition": block,
                    "csv_record_number": record_number, "material_index": material_index,
                    "source_fields": fields, "text": literal,
                    "exact_text_id": text_id(literal), "conservative_group_id": group_id(literal),
                    "legacy_prefix": prefix,
                    "legacy_retained_index": None if prefix else legacy_index,
                    "source_sha256": pin["sha256"],
                })
                material_index += 1
                legacy_index += int(not prefix)
                block_count += 1
            require(block_count > 3, f"incomplete material block: {name}")
        require(legacy_index == COUNTS[condition], "legacy material extent disagrees with source scope")
    return rows


def summarize(rows):
    exact = {c: Counter(r["exact_text_id"] for r in rows if r["condition"] == c) for c in CONDITIONS}
    conservative = {c: {r["conservative_group_id"] for r in rows if r["condition"] == c} for c in CONDITIONS}
    shared = set(exact["NR"]) & set(exact["TSR"])
    return {
        "material_records": {c: sum(exact[c].values()) for c in CONDITIONS},
        "unique_exact_texts": {c: len(exact[c]) for c in CONDITIONS},
        "shared_exact_texts": len(shared),
        "shared_occurrences": {c: sum(exact[c][s] for s in shared) for c in CONDITIONS},
        "cross_condition_occurrence_pairs": sum(exact["NR"][s] * exact["TSR"][s] for s in shared),
        "shared_conservative_groups": len(conservative["NR"] & conservative["TSR"]),
    }


def material_audit(rows):
    """Explain membership changes, without publishing text or case identifiers."""
    retained = [r for r in rows if not r["legacy_prefix"]]
    shared = lambda rs: ({r["exact_text_id"] for r in rs if r["condition"] == "NR"}
                         & {r["exact_text_id"] for r in rs if r["condition"] == "TSR"})
    lost = shared(rows) - shared(retained)
    categories = Counter()
    for item in lost:
        states = []
        for condition in CONDITIONS:
            occurrences = [r for r in rows if r["condition"] == condition and r["exact_text_id"] == item]
            states.append("prefix_only" if all(r["legacy_prefix"] for r in occurrences) else "retained")
        categories["NR_" + states[0] + "__TSR_" + states[1]] += 1
    return {
        "schema": "zuco2-material-membership-audit-v1",
        "all_materials": summarize(rows),
        "legacy_after_first_three_per_block": summarize(retained),
        "first_three_per_block": summarize([r for r in rows if r["legacy_prefix"]]),
        "shared_exact_items_lost_by_legacy_prefix_removal": len(lost),
        "lost_item_membership_counts": dict(sorted(categories.items())),
        "practice_roles_inferred": False,
        "paper_duplicate_obligations_reconciled": False,
        "limits": [
            "Material equality does not authenticate a MAT presentation or a practice exclusion.",
            "Paper duplicate obligations and the primary recorded matched set J require source-content joins.",
            "Conservative groups and occurrence-pair counts never replace exact sentence identities.",
        ],
    }


def align_exact(material_texts, recording_texts):
    """Find a unique order-preserving exact subsequence, or refuse to choose one.

    Counts saturate at two because only zero/one/multiple is required. Repeated
    sentences remain distinct source records. No fuzzy matching or first-match
    tie break can manufacture a recording identity.
    """
    material = [exact_text(t) for t in material_texts]
    observed = [exact_text(t) for t in recording_texts]
    require(len(material) <= 1000 and len(observed) <= 1000, "bounded content sequence required")
    n, m = len(material), len(observed)
    ways = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        ways[i][0] = 1
    for i in range(1, n + 1):
        for j in range(1, min(i, m) + 1):
            match = ways[i - 1][j - 1] if material[i - 1] == observed[j - 1] else 0
            ways[i][j] = min(2, ways[i - 1][j] + match)
    count = ways[n][m]
    if count != 1:
        return {"status": "no_exact_ordered_join" if count == 0 else "ambiguous_exact_ordered_join",
                "alignment_count_capped_at_two": count, "material_indices": None}
    indices = []
    i, j = n, m
    while j:
        if ways[i - 1][j]:
            i -= 1
        else:
            indices.append(i - 1)
            i -= 1
            j -= 1
    return {"status": "unique_exact_ordered_join", "alignment_count_capped_at_two": 1,
            "material_indices": list(reversed(indices))}


def join_presentations(materials, document):
    """Join a full source-content metadata census; never ingest query answers.

    Each source container must carry its original byte/hash identity. This
    command hashes the metadata file, but cannot authenticate the upstream MAT
    extraction from that claim alone; independent extraction custody remains
    required before the result is a scientifically qualified input.
    """
    require(set(document) == {"schema", "containers"} and document["schema"] == "zuco2-presentation-content-v1",
            "presentation metadata schema required")
    containers = document["containers"]
    require(type(containers) is list and len(containers) == 36, "complete 36-container metadata required")
    expected = {(p, c) for p in PEOPLE for c in CONDITIONS}
    seen = set()
    material_by_condition = {c: [r for r in materials if r["condition"] == c] for c in CONDITIONS}
    results = []
    observed_by_slot = {}
    for container in containers:
        require(set(container) == {"person", "condition", "source_bytes", "source_sha256", "presentations"},
                "exact content-only container fields required")
        key = (container["person"], container["condition"])
        require(key in expected and key not in seen, "duplicate or unknown source container")
        seen.add(key)
        person, condition = key
        require(type(container["source_bytes"]) is int and container["source_bytes"] > 0
                and type(container["source_sha256"]) is str
                and re.fullmatch(r"[0-9a-f]{64}", container["source_sha256"]), "original container pin required")
        presentations = container["presentations"]
        require(type(presentations) is list and len(presentations) == COUNTS[condition],
                "complete presentation metadata required")
        indices = []
        for p in presentations:
            require(set(p) == {"source_index", "text"} and type(p["source_index"]) is int,
                    "content and original source index only")
            indices.append(p["source_index"])
        require(indices == list(range(COUNTS[condition])), "ordered complete original source indices required")
        for p in presentations:
            slot = (condition, p["source_index"])
            normalized = exact_text(p["text"])
            require(slot not in observed_by_slot or observed_by_slot[slot] == normalized,
                    "cross-person original presentation text disagreement")
            observed_by_slot[slot] = normalized
        rows = material_by_condition[condition]
        result = align_exact([r["text"] for r in rows], [p["text"] for p in presentations])
        result.update({"person": person, "condition": condition,
                       "source_sha256": container["source_sha256"], "presentation_count": len(presentations)})
        if result["material_indices"] is not None:
            selected = [rows[i] for i in result["material_indices"]]
            selected_ids = {r["source_record_id"] for r in selected}
            result["source_record_ids"] = [r["source_record_id"] for r in selected]
            result["unobserved_material_record_ids"] = [r["source_record_id"] for r in rows
                                                        if r["source_record_id"] not in selected_ids]
            result["agrees_with_legacy_first_three_removal"] = selected_ids == {
                r["source_record_id"] for r in rows if not r["legacy_prefix"]}
        results.append(result)
    require(seen == expected, "complete original cohort required")
    sets = {c: {text_id(t) for (cc, _), t in observed_by_slot.items() if cc == c} for c in CONDITIONS}
    all_unique = all(r["status"] == "unique_exact_ordered_join" for r in results)
    return {"schema": "zuco2-material-content-joins-v1", "people": 18, "source_containers": 36,
            "presentations": 13302, "all_content_joins_unique": all_unique,
            "observed_exact_shared_items": sorted(sets["NR"] & sets["TSR"]),
            "containers": sorted(results, key=lambda r: (r["person"], r["condition"])),
            "source_extraction_custody_verified": False,
            "paper_duplicate_obligations_reconciled": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="directory containing the 14 original CSVs")
    parser.add_argument("--output", type=Path, required=True, help="fresh operator-owned directory outside Git")
    parser.add_argument("--presentation-content", type=Path,
                        help="optional full 36-container content-only metadata census")
    args = parser.parse_args(argv)
    repository = Path(__file__).resolve().parents[5]
    output = args.output.resolve()
    require(output != repository and repository not in output.parents, "operator output must be outside repository")
    pin_path = Path(__file__).with_name("pinned_materials.json")
    pin_raw = read_ordinary(pin_path, 65536)
    pins = json.loads(pin_raw)
    rows = {policy: load_materials(args.source, pins, policy) for policy in ("literal_quotes", "legacy_csv")}
    audit = {policy: material_audit(records) for policy, records in rows.items()}
    require([r["source_record_id"] for r in rows["literal_quotes"]] ==
            [r["source_record_id"] for r in rows["legacy_csv"]], "quote interpretations change record boundaries")
    report = {"schema": "zuco2-material-dialect-audit-v1", "by_quote_policy": audit,
              "material_pins_sha256": hashlib.sha256(pin_raw).hexdigest(),
              "quote_policy_selected": None,
              "parse_sensitive_records": sum(a["text"] != b["text"] for a, b in
                                               zip(rows["literal_quotes"], rows["legacy_csv"]))}
    outputs = {"material_rows.json": rows, "material_audit.json": report}
    if args.presentation_content:
        raw = read_ordinary(args.presentation_content, 32 * 1024 * 1024)
        document = json.loads(raw)
        joined = {policy: join_presentations(records, document) for policy, records in rows.items()}
        outputs["presentation_joins.json"] = {"by_quote_policy": joined,
                                               "presentation_metadata_sha256": hashlib.sha256(raw).hexdigest()}
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name, content in outputs.items():
        (output / name).write_text(json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                                  encoding="utf-8")
    print(json.dumps({"material_records": len(rows["literal_quotes"]), "output_files": sorted(outputs),
                      "content_metadata_join_supplied": bool(args.presentation_content)}, sort_keys=True))


if __name__ == "__main__":
    main()
