#!/usr/bin/env python3
"""Source-grammar UMBRAE raw-response conversion; operator construction only.

No model, data loader, raw append-log interpretation or scientific decision is
implemented here. See README.md for provenance and native-parity limitations.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re

CORE_PATH = Path(__file__).resolve().parents[1] / "initial-evaluator-v1" / "grounding.py"
CORE_SHA256 = "1a9ae2432fd941ef531b5f1078731f1ce3ee3dd878311aaa17e729c9573c0014"
if hashlib.sha256(CORE_PATH.read_bytes()).hexdigest() != CORE_SHA256:
    raise RuntimeError("reviewed grounding dependency changed")
_spec = importlib.util.spec_from_file_location("umbrae_raw_grounding", CORE_PATH)
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)

SCHEMA = "umbrae-keyed-raw-panel/v1"
MAX_TEXT_BYTES = 65536
MAX_INPUT_BYTES = 256 * 1024 * 1024
# Same accepted lexical language as the pinned author's extract_boxes: one
# decimal digit, optional decimal fraction; four comma-separated coordinates;
# optional semicolon-separated boxes. Whitespace/sign/exponent repair is absent.
_NUMBER = r"\d(?:\.\d*)?"
_BOX = rf"{_NUMBER}(?:,{_NUMBER}){{3}}"
_GROUP = re.compile(rf"\[{_BOX}(?:;{_BOX})*\]")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def extract_source_grammar(text: str) -> list[list[list[float]]]:
    """Retain every source-accepted group/box in encounter order, without repair."""
    g._require(isinstance(text, str), "raw response must be text")
    try:
        encoded = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise g.ContractError("raw response must be valid UTF-8 text") from exc
    g._require(len(encoded) <= MAX_TEXT_BYTES, "raw response exceeds explicit byte limit")
    return [[[float(coordinate) for coordinate in box.split(",")]
             for box in match.group(0)[1:-1].split(";")]
            for match in _GROUP.finditer(text)]


def validate_roster(roster: object, profile: str) -> dict[str, list[str]]:
    """Validate an operator query list; cardinality is not source authentication."""
    g._require(profile in ("engineering_controls", "paper_population"), "unknown profile")
    g._require(isinstance(roster, dict) and bool(roster), "operator query roster required")
    g._require(set(roster) == {str(i) for i in range(len(roster))},
               "image keys must be contiguous strings starting at zero")
    if profile == "paper_population":
        g._require(len(roster) == 982, "paper population requires all 982 images")
    total = 0
    for image, categories in roster.items():
        g._require(isinstance(categories, list)
                   and all(isinstance(c, str) and c in g.GROUPS["All"] for c in categories),
                   f"{image}: known category strings required")
        g._require(len(set(categories)) == len(categories), f"{image}: duplicate query category")
        total += len(categories)
    g._require(total > 0, "query population is empty")
    return roster


def convert_panel(packet: object, roster: object) -> dict:
    """Convert a full four-arm/four-subject packet to existing scorer format.

    A null response records a missing answer explicitly. Missing keys reject the
    packet instead of permitting silent population reduction. Coordinate values
    are not clipped or reordered: the reviewed scorer still rejects an invalid
    first box, even when a later box is valid.
    """
    g._require(isinstance(packet, dict) and set(packet) == {
        "schema", "task_id", "profile", "query_roster_sha256", "responses"},
        "exact raw-panel fields required")
    g._require(packet["schema"] == SCHEMA and packet["task_id"] == g.TASK,
               "wrong raw-panel schema or task")
    roster = validate_roster(roster, packet["profile"])
    roster_digest = canonical_sha256(roster)
    g._require(packet["query_roster_sha256"] == roster_digest, "query roster commitment differs")
    panel = packet["responses"]
    g._require(isinstance(panel, dict) and set(panel) == set(g.ROLES), "exact four arms required")
    converted, audit = {}, {}
    for role in g.ROLES:
        subjects = panel[role]
        g._require(isinstance(subjects, dict) and set(subjects) == set(g.SUBJECTS),
                   f"{role}: exact four subjects required")
        converted[role], audit[role] = {}, {}
        for subject in g.SUBJECTS:
            images = subjects[subject]
            g._require(isinstance(images, dict) and set(images) == set(roster),
                       f"{role}/{subject}: complete image support required")
            converted[role][subject], rows = {}, []
            counts = Counter()
            for image in sorted(roster, key=int):
                answers = images[image]
                g._require(isinstance(answers, dict) and set(answers) == set(roster[image]),
                           f"{role}/{subject}/{image}: complete query support required")
                converted[role][subject][image] = {}
                for category in sorted(roster[image]):
                    text = answers[category]
                    g._require(text is None or isinstance(text, str), "answer must be text or explicit null")
                    extracted = None if text is None else extract_source_grammar(text)
                    converted[role][subject][image][category] = extracted
                    _, first_status = g._prediction(extracted)
                    counts[first_status] += 1
                    rows.append({"image_id": image, "category": category,
                                 "raw_utf8_sha256": None if text is None else hashlib.sha256(text.encode("utf-8")).hexdigest(),
                                 "raw_utf8_bytes": None if text is None else len(text.encode("utf-8")),
                                 "extracted_sha256": canonical_sha256(extracted),
                                 "extracted_group_count": None if extracted is None else len(extracted),
                                 "first_box_status": first_status})
            audit[role][subject] = {"query_count": len(rows), "first_box_status_counts": dict(counts),
                                    "rows": rows}
    return {"schema": "umbrae-source-grammar-conversion/v1", "task_id": g.TASK,
            "profile": packet["profile"], "query_roster_sha256": roster_digest,
            "responses": converted, "audit": audit,
            "grounding_dependency_sha256": CORE_SHA256,
            "scientific_qualification": "not_established",
            "native_author_parser_parity": "not_run",
            "holds": ["The raw packet must be captured independently from an admitted producer; hashes do not attest generation.",
                      "Query roster, native image order, annotation transforms, checkpoints and original source-time lineage remain unqualified.",
                      "This parser follows the inspected pinned grammar, not an authenticated full author-runtime execution.",
                      "The existing keyed scorer has explicit corrections relative to author traversal; native numerical parity remains open.",
                      "No inference, model execution, isolation, reproduction, improvement or readiness is established."]}


def extraction_comparison(converted: dict, existing: object) -> dict:
    """Report all discrepancies against a separately supplied extracted panel."""
    expected = converted["responses"]
    g._require(isinstance(existing, dict) and set(existing) == set(g.ROLES), "comparison requires all four arms")
    differences = []
    for role in g.ROLES:
        g._require(isinstance(existing[role], dict) and set(existing[role]) == set(g.SUBJECTS),
                   "comparison requires all four subjects")
        for subject in g.SUBJECTS:
            observed = existing[role][subject]
            target = expected[role][subject]
            g._require(isinstance(observed, dict) and set(observed) == set(target),
                       "comparison image support differs")
            for image, categories in target.items():
                g._require(isinstance(observed[image], dict) and set(observed[image]) == set(categories),
                           "comparison category support differs")
                for category, value in categories.items():
                    # JSON-byte comparison avoids bool==1 and permits an exact
                    # representation comparison, rather than approximate boxes.
                    if canonical_sha256(observed[image][category]) != canonical_sha256(value):
                        differences.append({"role": role, "subject": subject,
                                            "image_id": image, "category": category})
    return {"status": "equal_extracted_values" if not differences else "extraction_disagreement",
            "mismatch_count": len(differences), "mismatches": differences,
            "scope": "Supplied structured outputs only; no independent author execution is attested."}


def read_bounded(path: Path) -> tuple[object, dict]:
    with path.open("rb") as stream:
        body = stream.read(MAX_INPUT_BYTES + 1)
    g._require(len(body) <= MAX_INPUT_BYTES, "input exceeds explicit byte limit")
    def reject_constant(value):
        raise g.ContractError("nonfinite JSON constant: " + value)
    value = json.loads(body.decode("utf-8"), object_pairs_hook=g._pairs, parse_constant=reject_constant)
    return value, {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-panel", type=Path, required=True)
    parser.add_argument("--query-roster", type=Path, required=True)
    parser.add_argument("--compare-extracted-panel", type=Path)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        raw, raw_pin = read_bounded(args.raw_panel)
        roster, roster_pin = read_bounded(args.query_roster)
        result = convert_panel(raw, roster)
        result["input_pins"] = {"raw_panel": raw_pin, "query_roster": roster_pin}
        if args.compare_extracted_panel is not None:
            existing, existing_pin = read_bounded(args.compare_extracted_panel)
            result["extraction_comparison"] = extraction_comparison(result, existing)
            result["input_pins"]["comparison_extracted_panel"] = existing_pin
        args.output_directory.mkdir(exist_ok=False)
        file_pins = {}
        for role in g.ROLES:
            file_pins[role] = {}
            for subject in g.SUBJECTS:
                path = args.output_directory / f"{role}-{subject}.json"
                body = (json.dumps(result["responses"][role][subject], sort_keys=True,
                                   ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
                with path.open("xb") as stream:
                    stream.write(body)
                file_pins[role][subject] = {"path": path.name, "bytes": len(body),
                                           "sha256": hashlib.sha256(body).hexdigest()}
        result.pop("responses")
        result["extracted_files"] = file_pins
        result["raw_panel_value_sha256"] = canonical_sha256(raw)
        result["complete"] = True
        # This final manifest is absent if any preceding output creation fails.
        with (args.output_directory / "conversion.json").open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
    except (g.ContractError, OSError, UnicodeError, ValueError, RecursionError) as exc:
        parser.exit(2, f"raw-response conversion rejected: {exc}\n")


if __name__ == "__main__":
    main()
