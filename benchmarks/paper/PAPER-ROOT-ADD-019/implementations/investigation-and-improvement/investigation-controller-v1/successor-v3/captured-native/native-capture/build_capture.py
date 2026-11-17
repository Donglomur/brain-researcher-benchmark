"""Construct exact source-bound MATLAB observation successors; never run MATLAB.

build(root_id, mode, authenticated_source_bytes, context_id) is a pure source
construction interface apart from bounded reads of this frozen component.
Its output must be admitted by the parent authority/custody/resource controller.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from collections.abc import Mapping

HERE = Path(__file__).resolve().parent
CONTRACT_BYTES = 131816
CONTRACT_SHA256 = "93f2cc9f79c4002c2dfa4702402ef95255063a6e63e4339b076e7bfbeafe2ac5"


class CaptureRefusal(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise CaptureRefusal(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode()


def exact_read(path, size, sha):
    need(type(size) is int and 0 <= size <= 262144, "bounded component member")
    with path.open("rb") as handle:
        body = handle.read(size + 1)
    need(len(body) == size and digest(body) == sha, "component source pin")
    return body


def contract():
    value = json.loads(exact_read(HERE / "CAPTURE_CONTRACT.json",
                                 CONTRACT_BYTES, CONTRACT_SHA256))
    need(value["root_count"] == 37 and len(value["roots"]) == 37,
         "complete declared root roster")
    need(len({v["root_id"] for v in value["roots"]}) == 37, "unique roots")
    return value


def _source_packet(descriptor, packets):
    name = descriptor["author_relative_path"]
    body = packets[name]
    need(type(body) is bytes, "source bytes only")
    need(len(body) == descriptor["bytes"] and digest(body) == descriptor["sha256"],
         "original source mismatch: " + name)
    need(b"achcap_" not in body and b"ach_native_capture" not in body,
         "reserved instrumentation name already present")
    body.decode("utf-8", "strict")
    return body


def _quoted(value):
    need(type(value) is str and "\n" not in value and "\r" not in value,
         "single line MATLAB literal")
    return "'" + value.replace("'", "''") + "'"


def reverse_file(transformed, edits, original_sha256):
    """Restore and hash-check original bytes; no parser or numerical execution."""
    need(type(transformed) is bytes, "transformed bytes")
    result = transformed
    last = len(result) + 1
    for edit in reversed(edits):
        start = edit["generated_byte_offset"]
        replacement = edit["replacement_utf8"].encode("utf-8")
        original = edit["original_utf8"].encode("utf-8")
        need(type(start) is int and 0 <= start < last,
             "ordered nonoverlapping source edits")
        need(result[start:start + len(replacement)] == replacement,
             "transformed source differs from exact edit record")
        result = result[:start] + original + result[start + len(replacement):]
        last = start
    need(digest(result) == original_sha256, "source reversal pin")
    return result


def _transform(item, original, root_id, *, root=False):
    lines = original.decode("utf-8").splitlines(keepends=True)
    changes = {}
    insert_before = {}
    insert_after = {}
    transformations = []
    if root:
        fn = item["functions"][0]
        need(fn["start_line"] == 1 and fn["header_end_line"] == 1,
             "fixed root declaration shape")
        original_name = item["original_entry_name"]
        generated_name = "ach_native_" + root_id
        need(re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", generated_name), "entry identifier")
        changed = lines[0].replace("function " + original_name + "(",
                                   "function " + generated_name + "(", 1)
        need(changed != lines[0], "exact root entry rename")
        changes[1] = changed
        transformations.append({"kind": "entry_rename", "original": original_name,
                                "generated": generated_name,
                                "original_arguments": item["entry_arguments"]})
        if "cache_branch" in item:
            branch = item["cache_branch"]
            line = branch["predicate_line"]
            need(lines[line - 1].rstrip("\r\n") == branch["original_predicate"],
                 "cache predicate source anchor")
            flag = "true" if branch["cache_branch_when_predicate_true"] else "false"
            newline = "\r\n" if lines[line - 1].endswith("\r\n") else "\n"
            changes[line] = ("if ach_native_capture('cache_branch', " + _quoted(root_id)
                             + ", " + branch["path_variable"] + ", " + flag + ")" + newline)
            save_line = branch["save_line"]
            need(lines[save_line - 1].rstrip("\r\n") == branch["original_save"],
                 "cache save source anchor")
            old = "save(" + branch["path_variable"] + ","
            need(lines[save_line - 1].count(old) == 1, "single original cache save")
            changes[save_line] = lines[save_line - 1].replace(
                old, "save(ach_native_capture('cache_output'),", 1)
            transformations.append({"kind": "explicit_cache_mode_and_owned_save",
                                    "details": branch})
        for change in item["transforms"]:
            line = change["line"]
            if change["kind"] == "omit_unresolved_visual_helper_only":
                need(lines[line - 1].strip() == change["original"], "visual omission anchor")
                changes[line] = "% ach capture successor: unresolved plotPairs omitted; no visual parity.\n"
            elif change["kind"] == "identity_value_tap":
                old = change["original_expression"]
                need(lines[line - 1].count(old) == 1, "single original expression tap")
                new = "ach_native_capture('value', " + _quoted(change["tag"]) + ", " + old + ")"
                changes[line] = lines[line - 1].replace(old, new, 1)
            else:
                raise CaptureRefusal("undeclared source transform")
            transformations.append(change)
    for anchor in item["capture_anchors"]:
        line = anchor["line"]
        need(lines[line - 1].rstrip("\r\n") == anchor["original_line"],
             "snapshot source anchor")
        tag = item["source"]["author_relative_path"] + "::" + anchor["function"] + "::L" + str(line)
        indent = re.match(r"^[ \t]*", lines[line - 1]).group()
        call = indent + "ach_native_capture('snapshot', " + _quoted(tag) + ", " + _quoted(anchor["kind"]) + ");\n"
        target = insert_before if anchor["position"] == "before" else insert_after
        target.setdefault(line, []).append(call)
    chunks = []
    edits = []
    offset = 0
    for number, line in enumerate(lines, 1):
        replacement = ("".join(insert_before.get(number, [])) + changes.get(number, line)
                       + "".join(insert_after.get(number, [])))
        if replacement != line:
            edits.append({"original_line": number, "generated_byte_offset": offset,
                          "original_utf8": line, "replacement_utf8": replacement})
        encoded = replacement.encode("utf-8")
        chunks.append(encoded)
        offset += len(encoded)
    output = b"".join(chunks)
    need(reverse_file(output, edits, digest(original)) == original,
         "all original bytes must be recoverable")
    return output, edits, transformations


def _wrapper(root, mode, context_id, spec_sha):
    name = "ach_native_" + root["root_id"]
    args = root["entry_arguments"]
    need(args in ([], ["datadir"]), "declared root argument ABI")
    invocation = name + ("(datadir);" if args else "();")
    fields = {"root_id": root["root_id"], "mode": mode, "context_id": context_id,
              "capture_spec_sha256": spec_sha, "original_source_sha256": root["source"]["sha256"]}
    cfg = "struct(" + ", ".join(_quoted(k) + ", " + _quoted(v) for k, v in fields.items()) + ")"
    return ("function achcap_result = ach_native_run(datadir, capture_dir, limits)\n"
            "% Generated exact-root entry. Parent owns qualification/authority/outer custody.\n"
            "achcap_cfg = " + cfg + ";\n"
            "ach_native_capture('begin', achcap_cfg, capture_dir, limits);\n"
            "achcap_cleanup = onCleanup(@() ach_native_capture('reset'));\n"
            "try\n    " + invocation + "\n"
            "    achcap_result = ach_native_capture('finish');\n"
            "catch achcap_error\n"
            "    try\n        ach_native_capture('failure', achcap_error);\n"
            "    catch achcap_diagnostic_error\n"
            "        achcap_error = addCause(achcap_error, achcap_diagnostic_error);\n"
            "    end\n    rethrow(achcap_error);\nend\nend\n").encode("utf-8")


def build(root_id, mode, authenticated_source_bytes, context_id):
    """Return source files/spec/pins for one of the exact 37 complete root obligations.

    Input map keys must be the selected root author-relative path plus exactly
    utils/plotPretty.m and utils/plotDLCaligned.m. All other unchanged dependency
    staging belongs to the parent source/authority controller. No file is written.
    """
    need(type(root_id) is str and type(mode) is str, "typed root and mode")
    need(type(context_id) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", context_id),
         "bounded exact context identifier")
    need(isinstance(authenticated_source_bytes, Mapping), "source packet map")
    cfg = contract()
    matches = [r for r in cfg["roots"] if r["root_id"] == root_id]
    need(len(matches) == 1, "selected root is outside complete roster")
    root = matches[0]
    need(mode in root["allowed_modes"], "explicit per-root scientific mode")
    items = [root] + cfg["external_instrumented_helpers"]
    names = {v["source"]["author_relative_path"] for v in items}
    need(set(authenticated_source_bytes) == names, "exact original source packet domain")
    sources = {}
    source_edits = []
    for index, item in enumerate(items):
        original = _source_packet(item["source"], authenticated_source_bytes)
        generated, edits, transformations = _transform(item, original, root_id, root=index == 0)
        destination = ("ach_native_" + root_id + ".m" if index == 0
                       else Path(item["source"]["author_relative_path"]).name)
        sources[destination] = generated
        source_edits.append({"destination": destination, "original": item["source"],
                             "generated_bytes": len(generated), "generated_sha256": digest(generated),
                             "exact_reversal_edits": edits, "scientific_transforms": transformations})
    for template in cfg["runtime_templates"]:
        sources[template["name"]] = exact_read(HERE / template["name"],
                                               template["bytes"], template["sha256"])
    spec = {"schema": "ach_native_generated_capture_spec_v1", "root_id": root_id,
            "mode": mode, "context_id": context_id,
            "contract": {"bytes": CONTRACT_BYTES, "sha256": CONTRACT_SHA256},
            "root_contract": root, "external_helpers": cfg["external_instrumented_helpers"],
            "source_edits": source_edits, "sink_templates": cfg["runtime_templates"],
            "entry": {"function": "ach_native_run", "arguments": ["datadir", "capture_dir", "limits"],
                      "original_entry_arguments": root["entry_arguments"]},
            "output": {"index": "CAPTURE_INDEX.json", "typed_leaves": "leaf-NNNNNNNNN.bin",
                       "snapshots": "snapshot-NNNNNNNNN.json", "acceptance": "provisional",
                       "native_cache_MAT_requires_separate_body_schema_admission": mode == "forced_recompute"},
            "unchanged_parent_dependencies_must_be_admitted": True,
            "ED_controls_and_missing_producers_not_closed": True,
            "native_qualified": False, "scientific_qualified": False}
    spec_body = canonical(spec)
    spec_sha = digest(spec_body)
    sources["ach_native_run.m"] = _wrapper(root, mode, context_id, spec_sha)
    pins = [{"path": k, "bytes": len(v), "sha256": digest(v)} for k, v in sorted(sources.items())]
    return {"sources": sources, "capture_spec": spec, "capture_spec_bytes": spec_body,
            "capture_spec_sha256": spec_sha, "generated_source_pins": pins,
            "no_execution_or_output_directory_mutation": True}


__all__ = ["build", "contract", "reverse_file", "CaptureRefusal"]
