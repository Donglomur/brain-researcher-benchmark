"""Recover retained structural identity from the pinned auditor's row interface.

This is an operator construction helper, not a participant interface or a source
authenticator. It neither loads pickle/data nor changes the existing observation
export. The complete source audit and observation authentication remain external.
Typed dendrite labels are provenance, not verified biological dendrites.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import re
import struct

INPUT = {"bytes": 477396, "sha256": "4f095339e7b60f647f0d977d3713e72e373a2e397ce579fa451ba04ed23164a6"}
ROSTER_SHA256 = "4b45c9d09e659f8c060807a03a03a7777acdce36e8969029da1031731da3fdb8"
SCHEMA = "neural032-hierarchy-sidecar/v1"
TOKEN_FIELDS = {"kind", "source_type", "dtype", "encoding", "value", "missing", "missing_reason"}
ROW_FIELDS = {"row_id", "member_index0", "source_row0", "mouse_id", "FOV", "session", "compartment", "source_member", "dendrite_id", "namespaced_dendrite_id"}
IDENTITY = ("mouse_id", "FOV", "session", "compartment")


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def roster():
    """Read only the fixed public source-member metadata, never an observation."""
    body = Path(__file__).with_name("source_roster.json").read_bytes()
    require(hashlib.sha256(body).hexdigest() == ROSTER_SHA256, "source roster changed")
    return json.loads(body)["members"]


def validate_token(token):
    """Preserve source type and byte representation; reject forged missing states."""
    require(type(token) is dict and set(token) == TOKEN_FIELDS, "exact typed token fields required")
    kind, source, dtype = token["kind"], token["source_type"], token["dtype"]
    value, encoding = token["value"], token["encoding"]
    require(type(source) is str and 0 < len(source) <= 256, "bounded source type required")
    require(dtype is None or type(dtype) is str and len(dtype) <= 128, "bounded dtype required")
    require(type(token["missing"]) is bool, "missing must be boolean")
    missing, reason = False, None
    if kind == "none":
        require(source == "builtins.NoneType" and dtype is None and encoding == "none" and value is None,
                "none token identity mismatch")
        missing, reason = True, "none"
    elif kind == "string":
        require(encoding == "unicode" and type(value) is str and len(value) <= 128,
                "bounded string token required")
        value.encode("utf-8", errors="strict")
        require((source == "builtins.str" and dtype is None) or
                (source == "numpy.str_" and type(dtype) is str and re.fullmatch(r"[<>|]U[0-9]+", dtype)),
                "string source type/dtype mismatch")
        missing, reason = value == "", "empty_string" if value == "" else None
    elif kind == "integer":
        require(encoding == "decimal" and type(value) is str and
                re.fullmatch(r"0|-?[1-9][0-9]*", value) and len(value) <= 79,
                "canonical bounded integer token required")
        require(int(value).bit_length() <= 256, "integer token too large")
        if source == "builtins.int":
            require(dtype is None, "Python integer must not declare NumPy dtype")
        else:
            match = re.fullmatch(r"numpy\.(u?int)(8|16|32|64)", source)
            require(match is not None and type(dtype) is str, "integer source type required")
            width = int(match[2]) // 8
            require(re.fullmatch(r"[<>|]" + ("u" if match[1] == "uint" else "i") + str(width), dtype),
                    "integer dtype mismatch")
            minimum = 0 if match[1] == "uint" else -(1 << (8 * width - 1))
            maximum = (1 << (8 * width)) - 1 if match[1] == "uint" else (1 << (8 * width - 1)) - 1
            require(minimum <= int(value) <= maximum, "integer outside dtype range")
    elif kind == "float":
        require(type(value) is str and re.fullmatch(r"[0-9a-f]+", value), "lowercase IEEE hex required")
        if source == "builtins.float":
            require(dtype is None and encoding == "binary64-big-endian" and len(value) == 16,
                    "Python float encoding mismatch")
            fmt = ">d"
        else:
            match = re.fullmatch(r"numpy\.float(16|32|64)", source)
            require(match is not None and type(dtype) is str and encoding == "numpy-scalar-bytes",
                    "NumPy float source type/encoding required")
            width = int(match[1]) // 8
            require(re.fullmatch(r"[<>]f" + str(width), dtype) and len(value) == width * 2,
                    "float dtype/extent mismatch")
            fmt = dtype[0] + {2: "e", 4: "f", 8: "d"}[width]
        number = struct.unpack(fmt, bytes.fromhex(value))[0]
        if math.isnan(number):
            missing, reason = True, "nan"
        elif math.isinf(number):
            missing, reason = True, "positive_infinity" if number > 0 else "negative_infinity"
    else:
        raise Invalid("unsupported typed label kind")
    require(token["missing"] is missing and token["missing_reason"] == reason,
            "typed label missing-state mismatch")
    return copy.deepcopy(token)


def project_member(checked, index):
    """Use audit_dictionary(...)[rows]; ignore every measured numeric field."""
    require(type(index) is int and 0 <= index < 27, "exact member index required")
    member = roster()[index]
    require(type(checked) is dict and type(checked.get("rows")) is list and
            0 < len(checked["rows"]) <= 1143, "audited nonempty rows required")
    rows = []
    for number, row in enumerate(checked["rows"]):
        require(type(row) is dict and type(row.get("source_row0")) is int and row["source_row0"] == number,
                "complete original row order required")
        require(all(row.get(key) == member[key] for key in IDENTITY) and
                row.get("source_member") == member["name"], "audited row/source identity mismatch")
        token = validate_token(row.get("dendrite_id"))
        namespace = None if token["missing"] else [member["mouse_id"], member["FOV"], member["session"], token]
        supplied_namespace = row.get("namespaced_dendrite_id")
        if token["missing"]:
            require(supplied_namespace is None, "missing label must not create a group")
        else:
            require(type(supplied_namespace) is list and len(supplied_namespace) == 4 and
                    supplied_namespace[:3] == namespace[:3] and
                    validate_token(supplied_namespace[3]) == token, "auditor namespace mismatch")
        rows.append({"row_id": f"m{index:02d}r{number:04d}", "member_index0": index,
                     "source_row0": number, **{key: member[key] for key in IDENTITY},
                     "source_member": member["name"], "dendrite_id": token,
                     "namespaced_dendrite_id": copy.deepcopy(namespace)})
    return {"member_index0": index, "rows": rows}


def assemble(members):
    """Require all27 members/1143 rows; unknown labels do not drop observations."""
    require(type(members) is list and len(members) == 27, "all 27 source members required")
    by_index = {}
    for member in members:
        require(type(member) is dict and set(member) == {"member_index0", "rows"}, "exact member fields required")
        index = member["member_index0"]
        require(type(index) is int and 0 <= index < 27 and index not in by_index, "unique original member required")
        # Re-project to validate identity, order, typed label and missingness.
        expected = project_member({"rows": member["rows"]}, index)
        require(member == expected and all(set(row) == ROW_FIELDS for row in member["rows"]),
                "sidecar must contain only structural metadata")
        require(all(type(row["member_index0"]) is int and row["member_index0"] == index
                    for row in member["rows"]), "row member index must be an integer")
        by_index[index] = expected
    rows = [row for index in range(27) for row in by_index[index]["rows"]]
    require(len(rows) == 1143 and len({row["mouse_id"] for row in rows}) == 20,
            "complete 1143-row/20-mouse source scope required")
    return {"schema": SCHEMA, "task_id": "NEURAL-032", "observation_export": copy.deepcopy(INPUT),
            "source_roster_sha256": ROSTER_SHA256,
            "identity_semantics": "typed_source_labels_not_verified_biological_dendrites",
            "rows": rows}


def join_rows(observations, sidecar):
    """Identity join only. Caller must authenticate the original observation file.

    Return separate observation/hierarchy objects, leaving the historical export
    and the paired-MAE scorer's exact row schema intact. No imputation or filter.
    """
    require(type(sidecar) is dict and set(sidecar) ==
            {"schema", "task_id", "observation_export", "source_roster_sha256", "identity_semantics", "rows"},
            "exact sidecar fields required")
    require(type(sidecar["rows"]) is list, "sidecar row list required")
    binding = sidecar["observation_export"]
    require(type(binding) is dict and set(binding) == set(INPUT) and
            type(binding["bytes"]) is int and binding == INPUT, "exact observation binding required")
    grouped = {index: [] for index in range(27)}
    for row in sidecar["rows"]:
        require(type(row) is dict and type(row.get("member_index0")) is int and row["member_index0"] in grouped,
                "source member index required")
        grouped[row["member_index0"]].append(row)
    expected = assemble([{"member_index0": index, "rows": grouped[index]} for index in range(27)])
    require(sidecar == expected, "sidecar content/binding mismatch")
    require(type(observations) is list and len(observations) == 1143, "complete observation rows required")
    by_id = {row["row_id"]: row for row in sidecar["rows"]}
    seen = set()
    result = []
    for row in observations:
        require(type(row) is dict and type(row.get("row_id")) is str and row["row_id"] in by_id and
                row["row_id"] not in seen, "exact unique observation row IDs required")
        seen.add(row["row_id"])
        identity = by_id[row["row_id"]]
        require(all(type(row.get(key)) is int and row[key] == identity[key] for key in ("member_index0", "source_row0"))
                and all(row.get(key) == identity[key] for key in ("mouse_id", "compartment")),
                "observation/sidecar identity mismatch")
        result.append({"observation": copy.deepcopy(row), "hierarchy": copy.deepcopy(identity)})
    return result
