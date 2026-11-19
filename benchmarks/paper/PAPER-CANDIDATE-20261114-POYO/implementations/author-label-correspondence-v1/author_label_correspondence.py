"""Bind two fixed author-project label sources without executing author code.

This is an observed label correspondence, not a biological-session manifest,
train/test assignment, model producer, or original-paper qualification.
"""
from __future__ import annotations

import ast
from collections import Counter
import hashlib
import json


SOURCE_SHA256 = "070d1c9e7f3238fdb210ebc3c3fef289c822516a97d1b3069bfcb9051157a467"
SOURCE_BLOB = "dfcdeda2c6e0fd72a8cbcf47b1e01f035b8d5f42"
METADATA_SHA256 = "8688e0e9230e946c63c04ea6e9ee5dfe8e205095381b0c847587c1d7e971126e"
METADATA_BLOB = "d88790b1d29fb4ce601747c4eebc3f99bed6ab2f"
TYPE_RULES = (
    ("Chewie", "C"), ("Mihili", "M"), ("Jaco", "J"), ("indy", "I"),
    ("loco", "L"), ("sub-Nitschke", "N"), ("sub-Jenkins", "Je"), ("Flint", "F"),
)
SUFFIXES = ("_RT", "_Maze", "_CO")


class BindingError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise BindingError(message)


def _pin(body, size, sha256, git_blob):
    _require(type(body) is bytes and len(body) == size, "source extent differs")
    _require(hashlib.sha256(body).hexdigest() == sha256, "source SHA256 differs")
    framed = b"blob " + str(size).encode("ascii") + b"\0" + body
    _require(hashlib.sha1(framed).hexdigest() == git_blob, "Git blob identity differs")


def _literal_rows(source):
    """Inspect a literal assignment only; imports, calls and writes never run."""
    tree = ast.parse(source)
    assignments = [
        node for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "monkey_dict"
                for target in node.targets)
    ]
    _require(len(assignments) == 1 and len(assignments[0].targets) == 1,
             "one direct monkey_dict assignment is required")
    value = assignments[0].value
    _require(isinstance(value, ast.Dict) and 0 < len(value.keys) <= 500,
             "monkey_dict must be a bounded literal dictionary")
    labels, ordinals = [], []
    for key, ordinal in zip(value.keys, value.values):
        _require(isinstance(key, ast.Constant) and type(key.value) is str
                 and 0 < len(key.value) <= 256, "literal nonempty label required")
        _require(isinstance(ordinal, ast.Constant) and type(ordinal.value) is int,
                 "literal integer ordinal required")
        labels.append(key.value)
        ordinals.append(ordinal.value)
    _require(len(labels) == len(set(labels)), "duplicate raw source label")
    _require(ordinals == list(range(len(labels))), "ordered source ordinals differ")
    return list(zip(labels, ordinals))


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate metadata key")
        result[key] = value
    return result


def _join(rows, metadata):
    _require(type(metadata) is dict and set(metadata) == {"names", "types"},
             "metadata keys differ")
    names, types = metadata["names"], metadata["types"]
    _require(type(names) is list and type(types) is list
             and len(names) == len(types) == len(rows), "metadata support differs")
    _require(all(type(name) is str and name for name in names)
             and len(names) == len(set(names)), "duplicate or invalid display label")
    result = []
    for (source_label, ordinal), display_label, code in zip(rows, names, types):
        matches = [candidate for fragment, candidate in TYPE_RULES if fragment in source_label]
        _require(len(matches) == 1 and type(code) is str and code == matches[0],
                 "source type correspondence differs")
        suffix = None
        if source_label != display_label:
            candidates = [s for s in SUFFIXES if source_label == display_label + s]
            _require(len(candidates) == 1, "ordered label correspondence differs")
            suffix = candidates[0]
        result.append({
            "source_ordinal": ordinal, "source_literal_label": source_label,
            "browser_metadata_label": display_label, "author_type_code": code,
            "observed_relation": "literal_equal" if suffix is None else "terminal_suffix_omitted",
            "source_terminal_suffix": suffix,
        })
    return result


def build_binding(source_body, metadata_body):
    """Return a source-bound index; never fabricate original experiment roles."""
    _pin(source_body, 9478, SOURCE_SHA256, SOURCE_BLOB)
    _pin(metadata_body, 6285, METADATA_SHA256, METADATA_BLOB)
    rows = _literal_rows(source_body.decode("utf-8"))
    metadata = json.loads(metadata_body.decode("utf-8"), object_pairs_hook=_unique_object)
    _require(len(rows) == 158, "fixed author label extent differs")
    joined = _join(rows, metadata)
    return {
        "schema": "poyo-author-project-label-correspondence/v1",
        "task_id": "PAPER-CANDIDATE-20261114-POYO",
        "source_repository": "https://github.com/poyo-brain/poyo-brain.github.io",
        "source_snapshot": {
            "revision": "db43cacd2fc43022e4fb0f8f8470aa51d1aba4a4",
            "tree": "e4a260464d60d4ff26bbfb264747673a4a002ec4",
            "meaning": "Specific author-project repository snapshot dated 2023; not proof of first public availability or experiment execution.",
        },
        "source_members": {
            "scripts/sess_types.py": {"bytes": 9478, "sha256": SOURCE_SHA256, "git_blob": SOURCE_BLOB},
            "assets/sess_md.json": {"bytes": 6285, "sha256": METADATA_SHA256, "git_blob": METADATA_BLOB},
        },
        "label_count": len(joined),
        "type_code_counts": dict(Counter(row["author_type_code"] for row in joined)),
        "relation_counts": dict(Counter(row["observed_relation"] for row in joined)),
        "rows": joined,
        "physical_session_count": None,
        "biological_subject_count": None,
        "historical_train_test_membership": None,
        "checkpoint_or_score_binding": None,
        "scientifically_qualified": False,
        "limitations": [
            "The author script writes sess_metadata.json, while the browser reads sess_md.json; this observed correspondence does not prove a production lineage.",
            "Preserve both raw spellings and every ordinal. Similar dates or filenames do not authorize collapsing physical sessions.",
            "Eight author type codes are not a reconciled biological-subject count or proof of the paper's stated seven-primate training scope.",
            "Original data bytes, trial splits, adaptation budgets, masks, checkpoints and historical scoring remain unbound.",
        ],
    }
