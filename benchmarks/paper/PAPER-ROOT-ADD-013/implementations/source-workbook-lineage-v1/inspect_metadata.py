"""Inert, source-pinned inspection of the author's A1:O274 metadata range.

This reads metadata only. It does not load MAT/LFP observations, execute Excel
formulas, map records to paper figures, or reproduce a physiological finding.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import xml.etree.ElementTree as ET
import zipfile

SOURCE_IDENTITY = {
    "bytes": 41384,
    "md5": "76f694ff38e548c43fd97812a6dfaf4c",
    "sha256": "dedfd00fb7211013e87afabd17cea17a6901550333810ae05c444d336cd5ebe7",
}
MAX_COMPRESSED = 65536
MAX_EXPANDED = 4 * 1024 * 1024
MAX_ENTRIES = 128
MAX_REPORT = 524288
REPORT_SHAPE_BOUND = 521592
MAX_LITERAL_JSON = 96
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P = "http://schemas.openxmlformats.org/package/2006/relationships"


class MetadataError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise MetadataError(message)


def identity(raw):
    return {"bytes": len(raw), "md5": hashlib.md5(raw).hexdigest(),
            "sha256": hashlib.sha256(raw).hexdigest()}


def xml(raw):
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise MetadataError("only UTF-8 OOXML is supported") from exc
    need("\x00" not in text, "NUL or non-UTF-8 XML encoding")
    declaration = re.match(r'''^\s*<\?xml\b[^?]*encoding\s*=\s*(["'])([^"']+)\1''', text)
    need(declaration is None or declaration.group(2).lower() in ("utf-8", "utf8"),
         "only UTF-8 XML declarations are supported")
    need("<!DOCTYPE" not in text.upper() and "<!ENTITY" not in text.upper(),
         "DTD/entities are not permitted")
    try:
        return ET.fromstring(text)
    except ET.ParseError as exc:
        raise MetadataError("malformed OOXML") from exc


def safe_member(name):
    p = PurePosixPath(name)
    need(bool(name) and not name.startswith("/") and "\\" not in name
         and ":" not in name and not any(x in ("", ".", "..") for x in name.split("/"))
         and str(p) == name, "noncanonical ZIP member")
    return name


def typed_counts(values):
    counts = Counter(json.dumps(value, sort_keys=True) for value in values)
    return [dict(json.loads(value), count=count) for value, count in sorted(counts.items())]


def compact_json(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def value_identity(value):
    raw = value.encode("utf-8")
    return {"encoding": "utf-8", "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def bounded_name(value):
    if value is None or len(compact_json(value)) <= MAX_LITERAL_JSON:
        return value
    return value_identity(value)


def bounded_cell(cell):
    result = dict(cell)
    if len(compact_json(result["value"])) > MAX_LITERAL_JSON:
        result["value_identity"] = value_identity(result.pop("value"))
    need(len(compact_json(result)) <= 192, "typed output representation bound")
    return result


def project_report(report):
    """Bound emitted identities only; complete-value groups/counts are already fixed."""
    result = dict(report)
    result["schema"] = "food-ripples-workbook-lineage/v3"
    result["first_sheet_name"] = bounded_name(report["first_sheet_name"])
    result["selected_sheet_member"] = bounded_name(report["selected_sheet_member"])
    result["members_read"] = [dict(member, name=bounded_name(member["name"]))
                              for member in report["members_read"]]
    result["headers"] = [bounded_cell(cell) for cell in report["headers"]]
    result["groups"] = [dict(group, animal=bounded_cell(group["animal"]),
                             day=bounded_cell(group["day"]),
                             session_counts=[bounded_cell(cell) for cell in group["session_counts"]],
                             condition_counts=[bounded_cell(cell) for cell in group["condition_counts"]],
                             records=[dict(record, session=bounded_cell(record["session"]),
                                           condition=bounded_cell(record["condition"]))
                                      for record in group["records"]])
                        for group in report["groups"]]
    result["summary"] = dict(report["summary"])
    for field in ("session_values", "condition_values"):
        result["summary"][field] = [bounded_cell(cell) for cell in report["summary"][field]]
    result["identity_output_policy"] = {
        "literal_json_bytes_max": MAX_LITERAL_JSON,
        "long_values": "Opaque full UTF-8 SHA256 and byte extent; type retained. No truncation or digest-based grouping.",
        "grouping": "Complete typed source values before output projection; projected identities cannot establish source equivalence or recover labels.",
    }
    return result


def serialize_report(report):
    body = (compact_json(project_report(report)) + "\n").encode("ascii")
    need(len(body) <= REPORT_SHAPE_BOUND <= MAX_REPORT, "report shape/byte cap")
    return body


def run_receipt(report, body):
    receipt = {"output_bytes": len(body), "output_sha256": hashlib.sha256(body).hexdigest(),
               "summary": {key: value for key, value in report["summary"].items()
                           if type(value) is int}, "readiness_promoted": False}
    result = compact_json(receipt)
    need(len(result) + 1 <= 2048, "stdout receipt cap")
    return result


def cell_value(cell, strings):
    need(cell.find("{" + S + "}f") is None, "formula in selected metadata range")
    kind = cell.get("t", "n")
    values = cell.findall("{" + S + "}v")
    need(len(values) <= 1, "multiple cell values")
    value = values[0].text or "" if values else ""
    if kind == "s":
        need(re.fullmatch(r"[0-9]+", value) is not None, "invalid shared-string index")
        index = int(value)
        need(index < len(strings), "shared-string index outside table")
        return {"kind": "text", "value": strings[index]}
    if kind == "inlineStr":
        node = cell.find("{" + S + "}is")
        need(node is not None and not values, "invalid inline string")
        return {"kind": "text", "value": "".join(n.text or "" for n in node.iter("{" + S + "}t"))}
    need(kind in ("n", "str", "b", "e", "d"), "unsupported cell type")
    need(len(value) <= 4096, "metadata cell too long")
    # Numeric/date encodings stay literal: do not invent MATLAB import semantics.
    return {"kind": kind, "value": value}


def inspect_workbook(raw, expected=SOURCE_IDENTITY):
    need(type(raw) is bytes and 0 < len(raw) <= MAX_COMPRESSED, "compressed workbook bound")
    need(identity(raw) == expected, "workbook identity mismatch")
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise MetadataError("invalid ZIP") from exc
    with archive:
        infos = archive.infolist()
        need(0 < len(infos) <= MAX_ENTRIES, "ZIP entry bound")
        names = [safe_member(i.filename) for i in infos]
        need(len(names) == len(set(names)), "duplicate ZIP member")
        need(sum(i.file_size for i in infos) <= MAX_EXPANDED, "expanded workbook bound")
        for entry in infos:
            need(not entry.flag_bits & 1 and not stat.S_ISLNK(entry.external_attr >> 16),
                 "encrypted or symlink ZIP member")
            need(entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                 "unsupported compression")
            lowered = entry.filename.lower()
            need(not any(x in lowered for x in ("vbaproject", "vbadata", "macrosheets/", "activex/")),
                 "macro or active content is not permitted")
        by_name = dict(zip(names, infos))
        read_bytes = 0
        read_members = []
        parsed_members = {}

        def read(name):
            nonlocal read_bytes
            if name in parsed_members:
                return parsed_members[name]
            need(name in by_name, "missing OOXML member: " + name)
            entry = by_name[name]
            need(read_bytes + entry.file_size <= MAX_EXPANDED, "expanded read bound")
            with archive.open(entry) as stream:
                body = stream.read(entry.file_size + 1)
            need(len(body) == entry.file_size, "member extent mismatch")
            read_bytes += len(body)
            read_members.append({"name": name, "bytes": len(body),
                                 "sha256": hashlib.sha256(body).hexdigest()})
            parsed_members[name] = xml(body)
            return parsed_members[name]

        for name in names:
            if name.endswith(".rels"):
                for relationship in read(name):
                    need(relationship.get("TargetMode", "Internal") == "Internal",
                         "external package relationship")
                    need(not any(x in relationship.get("Type", "").lower()
                                 for x in ("vbaproject", "macrosheet", "activex")),
                         "active package relationship")
        if "[Content_Types].xml" in names:
            for item in read("[Content_Types].xml"):
                need(not any(x in item.get("ContentType", "").lower()
                             for x in ("macroenabled", "vba", "activex")),
                     "active content type")

        workbook = read("xl/workbook.xml")
        need(workbook.tag == "{" + S + "}workbook", "workbook root namespace")
        rels = read("xl/_rels/workbook.xml.rels")
        need(rels.tag == "{" + P + "}Relationships", "relationships root")
        relationships = {}
        for rel in rels:
            need(rel.tag == "{" + P + "}Relationship", "unknown relationship element")
            rid = rel.get("Id")
            need(rid and rid not in relationships, "duplicate relationship ID")
            need(rel.get("TargetMode", "Internal") == "Internal", "external workbook relationship")
            target = rel.get("Target", "")
            target = target[1:] if target.startswith("/xl/") else "xl/" + target
            relationships[rid] = (safe_member(target), rel.get("Type", ""))
        sheets = workbook.findall("{" + S + "}sheets/{" + S + "}sheet")
        need(0 < len(sheets) <= 32, "sheet count bound")
        first = sheets[0]
        need(first.get("state", "visible") == "visible", "first sheet hidden; import semantics unresolved")
        rid = first.get("{" + R + "}id")
        need(rid in relationships, "missing first sheet relationship")
        target, relation_type = relationships[rid]
        need(relation_type == R + "/worksheet", "first sheet is not worksheet")
        shared = [p for p, kind in relationships.values() if kind == R + "/sharedStrings"]
        need(len(shared) <= 1, "duplicate shared-string table")
        strings = []
        if shared:
            root = read(shared[0])
            need(root.tag == "{" + S + "}sst", "shared-string table root")
            for item in root.findall("{" + S + "}si"):
                value = "".join(n.text or "" for n in item.iter("{" + S + "}t"))
                need(len(value) <= 4096, "shared string too long")
                strings.append(value)
            need(len(strings) <= 32768, "shared-string count bound")
        sheet = read(target)
        need(sheet.tag == "{" + S + "}worksheet", "worksheet root")
        cells = {}
        outside_cells = 0
        for cell in sheet.findall("{" + S + "}sheetData/{" + S + "}row/{" + S + "}c"):
            match = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]{0,6})", cell.get("r", ""))
            need(match is not None, "noncanonical cell reference")
            letters, row_text = match.groups()
            column = 0
            for letter in letters:
                column = column * 26 + ord(letter) - 64
            row = int(row_text)
            if row > 274 or column > 15:
                outside_cells += 1
                continue
            key = (row, column)
            need(key not in cells, "duplicate selected cell")
            cells[key] = cell_value(cell, strings)
        blank = {"kind": "blank", "value": ""}
        headers = [cells.get((1, column), blank) for column in range(1, 16)]
        rows = []
        for row in range(2, 275):
            values = [cells.get((row, column), blank) for column in range(1, 16)]
            if not any(x["value"] for x in values):
                continue
            record = {"row": row, "day": values[0], "animal": values[1],
                      "session": values[2], "condition": values[3],
                      "recording_path_sha256": hashlib.sha256(values[4]["value"].encode()).hexdigest()
                      if values[4]["value"] else None}
            rows.append(record)
        groups = defaultdict(list)
        for row in rows:
            key = json.dumps([row["animal"], row["day"]], sort_keys=True)
            groups[key].append(row)
        group_rows = []
        for key, records in sorted(groups.items()):
            animal, day = json.loads(key)
            group_rows.append({"animal": animal, "day": day,
                               "rows": [r["row"] for r in records],
                               "records": [{"row": r["row"], "session": r["session"],
                                            "condition": r["condition"]} for r in records],
                               "session_counts": typed_counts(r["session"] for r in records),
                               "condition_counts": typed_counts(r["condition"] for r in records)})
        summary = {
            "nonblank_metadata_rows": len(rows),
            "distinct_literal_animal_values": len(set(json.dumps(r["animal"], sort_keys=True) for r in rows)),
            "distinct_literal_animal_day_groups": len(groups),
            "session_values": typed_counts(r["session"] for r in rows),
            "condition_values": typed_counts(r["condition"] for r in rows),
            "groups_with_literal_presleep_and_postsleep": sum(
                all(any(c["kind"] in ("text", "str") and c["value"] == state
                        for c in g["session_counts"]) for state in ("presleep", "postsleep"))
                for g in group_rows),
            "groups_with_multiple_condition_values_or_types": sum(len(g["condition_counts"]) > 1 for g in group_rows),
            "rows_with_blank_animal_or_day": sum(not r["animal"]["value"] or not r["day"]["value"] for r in rows),
        }
        return {"schema": "food-ripples-workbook-lineage/v1", "source": expected,
                "range": "A1:O274", "first_sheet_name": first.get("name"),
                "sheet_count": len(sheets), "selected_sheet_member": target,
                "expanded_bytes_read": read_bytes, "members_read": read_members,
                "zip_entries": len(infos), "declared_total_expanded_bytes": sum(i.file_size for i in infos),
                "selected_cells": len(cells), "cells_outside_selected_range_not_interpreted": outside_cells,
                "headers": headers, "summary": summary, "groups": group_rows,
                "limits": ["Literal metadata values/type categories only; shared/inline strings normalize to text. No MATLAB readtable parity or date conversion claim.",
                           "No MAT/neural data read, condition-code-to-figure mapping or reproduction result.",
                           "Recording paths and their hashes are not emitted; recording contents are not authenticated.",
                           "Pair presence is not valid physiological support or independent biological replication."],
                "readiness_promoted": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source, output = Path(args.workbook), Path(args.output)
    need(source.is_file() and not source.is_symlink(), "regular workbook required")
    need(not output.exists() and not output.is_symlink(), "fresh output required")
    with source.open("rb") as stream:
        raw = stream.read(MAX_COMPRESSED + 1)
    report = inspect_workbook(raw)
    body = serialize_report(report)
    receipt = run_receipt(report, body)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(body)
    print(receipt)


if __name__ == "__main__":
    main()
