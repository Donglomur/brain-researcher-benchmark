"""Replay source row selection and bind native exports; never fit trajectories.

Inputs are five externally pinned CSV byte bodies. Content binding does not
authenticate their origin. Only the explicitly supported CSV import subset is
admitted; native MATLAB numerical statistics remain supplied, not verified.
"""
from __future__ import annotations

import csv
from decimal import Decimal
import hashlib
import io
import math
import re

REVISION = "7a6ecc2bbf8f1e1fbca3b769a0db53299ee8171c"
INPUTS = ("source", "first_timing", "later_timing", "first_export", "later_export")
NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")
MISSING = ("", "NaN", "nan", "NAN")


def _number(token, where, *, missing=False):
    if missing and token in MISSING:
        return None
    if len(token) > 128 or NUMBER.fullmatch(token) is None:
        raise ValueError(where + ": unsupported numeric token")
    value = float(token)
    mantissa = token.lower().split("e", 1)[0]
    if not math.isfinite(value) or (value == 0 and any(c in "123456789" for c in mantissa)):
        raise ValueError(where + ": numerical overflow/underflow")
    return value


def _integer(token, where, *, positive=True):
    value = _number(token, where)
    exact = Decimal(token)
    if exact != exact.to_integral_value() or (positive and exact < 1) or abs(exact) > 1000000:
        raise ValueError(where + ": expected bounded integer")
    return int(value)


def _table(raw, where):
    if type(raw) is not bytes or len(raw) > 16 * 1024 * 1024:
        raise ValueError(where + ": bounded CSV bytes required")
    try:
        content = raw.decode("utf-8-sig")
        if "\x00" in content:
            raise ValueError(where + ": NUL byte")
        rows = list(csv.reader(io.StringIO(content, newline=""), strict=True))
    except (UnicodeError, csv.Error) as exc:
        raise ValueError(where + ": invalid UTF-8 CSV") from exc
    if not rows or not rows[0] or len(rows) > 100001:
        raise ValueError(where + ": absent or excessive table")
    header, body = rows[0], rows[1:]
    if any(len(row) != len(header) for row in body):
        raise ValueError(where + ": ragged CSV")
    return header, body


def _column(header, name):
    if header.count(name) != 1:
        raise ValueError("expected unique column: " + name)
    return header.index(name)


def _timing(raw, branch):
    header, rows = _table(raw, branch + " timing")
    mouse_col = _column(header, "mouse")
    fields = ("opto_first_day1",) if branch == "opto_first" else ("opto_on", "opto_off")
    columns = [_column(header, field) for field in fields]
    result = {}
    for row in rows:
        mouse = row[mouse_col]
        if not mouse or mouse in result:
            raise ValueError(branch + ": absent or ambiguous mouse timing")
        values = tuple(_integer(row[col], branch + " timing") for col in columns)
        if branch == "opto_later" and values[0] > values[1]:
            raise ValueError("later timing interval is reversed")
        result[mouse] = values
    return result


def _same_cell(original, exported):
    # MATLAB writetable can change decimal formatting. No tolerance or float
    # rounding is used to hide changes to source columns.
    if original in MISSING or exported in MISSING:
        return original in MISSING and exported in MISSING
    if (len(original) <= 128 and len(exported) <= 128
            and NUMBER.fullmatch(original) and NUMBER.fullmatch(exported)):
        return Decimal(original) == Decimal(exported)
    return original == exported


def _replay(header, rows, timing, branch):
    columns = {name: _column(header, name) for name in ("mouse", "env", "emergeLap")}
    if len(header) < 65 or max(columns.values()) >= 21:
        raise ValueError("source must retain the author table's 21 metadata columns and 44 lap columns")
    retained, excluded = [], []
    for source_row1, cells in enumerate(rows, 1):
        mouse, env = cells[columns["mouse"]], cells[columns["env"]]
        onset = _integer(cells[columns["emergeLap"]], "emergeLap")
        if env not in (branch + "_day1", "control_day1"):
            excluded.append({"source_row1": source_row1, "reason": "other_environment"})
            continue
        if mouse not in timing:
            raise ValueError(branch + ": relevant source mouse lacks unique timing")
        values = timing[mouse]
        if branch == "opto_first":
            end = values[0]  # released restrict=1; no invented 44-lap cap here
            selected = onset <= end
        else:
            on, off = values
            end = min(off, 44)
            selected = on <= onset <= off - 10 and onset < 44
        if not selected:
            excluded.append({"source_row1": source_row1, "reason": "outside_onset_window"})
            continue
        if not 1 <= onset <= end <= len(cells) - 21:
            raise ValueError(branch + ": source trajectory indices out of bounds")
        # MATLAB table column 21+lap is one-based. Addition of one and 5-cm
        # scaling happen before centering, matching the author arithmetic.
        bins = [_number(v, "source COM", missing=True) for v in cells[20 + onset:21 + end]]
        origin = None if bins[0] is None else (bins[0] + 1) * 5
        raw = [None if v is None or origin is None else (v + 1) * 5 - origin for v in bins]
        if any(v is not None and not math.isfinite(v) for v in raw):
            raise ValueError("centering/scaling overflow")
        observed = [i for i, v in enumerate(raw) if v is not None]
        # A finite onset yields zero at index 0. Interior interp1 fills gaps;
        # trailing NaNs remain missing and are dropped. No interpolation fit
        # or extrapolation is required to recover the retained span.
        span = observed[-1] + 1 if len(observed) > 1 else 0
        if span < 15:
            excluded.append({"source_row1": source_row1, "reason": "fewer_than_15_interpolated_laps"})
            continue
        # MATLAB find counts NaNs as nonzero. Do not replace this source rule
        # with the number of observed points or a valid-observation fraction.
        active = sum(v is None or v != 0 for v in raw)
        if active < 0.3 * span:
            # The author has no else for this branch: PFopto remains 1 but no
            # COMtrajMat row is appended, invalidating subsequent row pairing.
            raise ValueError(f"source_alignment_hole: {branch} source row {source_row1}")
        retained.append({
            "source_row1": source_row1, "mouse": mouse, "environment": env,
            "onset_lap": onset, "end_lap": end, "opto_on": int(env == branch + "_day1"),
            "raw_window_length": len(raw), "interpolated_span_laps": span,
            "source_find_count": active, "saved_matrix_laps": 15,
            "raw_regression_laps1": [i + 1 for i in observed],
            "raw_regression_cm": [raw[i] for i in observed],
        })
    return retained, excluded


def bind_native_exports(inputs, expected_sha256, mice):
    """Return aggregation inputs and auditable raw-regression row lineage.

    All five expected digests must come from a separately admitted operator
    manifest. No native inference is recomputed or asserted by this function.
    """
    if not isinstance(inputs, dict) or set(inputs) != set(INPUTS):
        raise ValueError("exactly five named source/native CSV byte inputs required")
    if not isinstance(expected_sha256, dict) or set(expected_sha256) != set(INPUTS):
        raise ValueError("five external input digests required")
    if (not isinstance(mice, list) or len(mice) != 9 or any(type(m) is not str or not m for m in mice)
            or len(set(mice)) != 9):
        raise ValueError("nine distinct declared mice required")
    for key in INPUTS:
        digest = expected_sha256[key]
        if type(inputs[key]) is not bytes or len(inputs[key]) > 16 * 1024 * 1024:
            raise ValueError(key + ": bounded bytes required")
        if (not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                or hashlib.sha256(inputs[key]).hexdigest() != digest):
            raise ValueError(key + ": operator digest mismatch")
    source_header, source_rows = _table(inputs["source"], "source")
    roster_rows, derived_rows, lineage, branch_audits = [], [], [], {}
    for short, branch in (("first", "opto_first"), ("later", "opto_later")):
        selected, excluded = _replay(source_header, source_rows, _timing(inputs[short + "_timing"], branch), branch)
        export_header, export_rows = _table(inputs[short + "_export"], short + " native export")
        if not selected or len(export_rows) != len(selected):
            raise ValueError(branch + ": native export does not cover every retained source row")
        if len(export_header) < len(source_header):
            raise ValueError(branch + ": native export omitted original source columns")
        for name in ("mouse", "env", "emergeLap"):
            if _column(export_header, name) != _column(source_header, name):
                raise ValueError(branch + ": native metadata column order differs")
        stat_cols = {name: _column(export_header, name) for name in ("COM_slope", "COM_pval", "Opto_ON")}
        if any(col < len(source_header) for col in stat_cols.values()):
            raise ValueError("native statistics must be appended to original source columns")
        for row1, (item, exported) in enumerate(zip(selected, export_rows), 1):
            original = source_rows[item["source_row1"] - 1]
            if any(not _same_cell(a, b) for a, b in zip(original, exported[:len(original)])):
                raise ValueError(branch + ": native source-row content/order mismatch")
            opto = _integer(exported[stat_cols["Opto_ON"]], "Opto_ON", positive=False)
            if opto != item["opto_on"]:
                raise ValueError(branch + ": exported treatment differs from source environment")
            p = _number(exported[stat_cols["COM_pval"]], "COM_pval", missing=True)
            slope = _number(exported[stat_cols["COM_slope"]], "COM_slope", missing=True)
            if p is not None and not 0 <= p <= 1:
                raise ValueError("COM_pval outside probability range")
            meta = {"id": f"{branch}/{row1}", "branch": branch, "row1": row1,
                    "mouse": item["mouse"], "opto_on": opto}
            roster_rows.append(meta)
            derived_rows.append({**meta, "slope_cm_per_lap": slope, "p_value": p})
            lineage.append({"id": meta["id"], **item})
        branch_audits[branch] = {"retained_count": len(selected), "excluded": excluded}
    if {row["mouse"] for row in roster_rows} != set(mice):
        raise ValueError("retained two-branch source rows do not cover exactly the nine declared mice")
    return {
        "schema": "find013-opto-trajectory-classification-lineage/v1",
        "source_revision": REVISION,
        "roster": {"schema": "find013-opto-derived-roster/v1", "source_revision": REVISION,
                   "mice": list(mice), "rows": roster_rows},
        "derived_rows": derived_rows, "lineage": lineage, "branch_audits": branch_audits,
        "input_bindings": dict(expected_sha256), "source_row_count": len(source_rows),
        "native_statistics": "supplied_from_row_bound_exports_not_recomputed",
        "original_source_authentication": "required_separately",
        "scientific_reproduction": "unknown", "scientific_improvement": "unknown",
        "readiness_promoted": False,
    }
