"""Native-grid input bridge for the existing Stroop55 task.

Accepts normalized, already loaded author MAT fields; does not load a MAT file,
acquire data, fit preprocessing, downsample, or assert authentic eligibility.
"""
import hashlib
import hmac
import math
import numbers
import re
from stroop import TASK, fold_assignment, validate_manifest

SOURCE_CODES = {11: 0, 12: 1, 13: 2}
SAMPLING_HZ = 25.6
CHANNELS = 35
PRE_SAMPLES = 128
POST_SAMPLES = 512
NATIVE_SAMPLES = 640
UNIT_STATUS = "author_plot_mM.mm; device_export_scale_unverified"


class InvalidBridge(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise InvalidBridge(message)


def integral(value, name, minimum=0):
    require(isinstance(value, numbers.Real) and not isinstance(value, bool)
            and math.isfinite(value) and value == int(value) and value >= minimum,
            name + ": finite integral value required")
    return int(value)


def sequence(value, name):
    require(not isinstance(value, (str, bytes, dict)) and hasattr(value, '__len__')
            and hasattr(value, '__getitem__'), name + ": indexed sequence required")
    return value


def source_inventory(member_names):
    """Join all55 basenames across three prep and raw CSV/TXT inventories."""
    names = list(member_names)
    require(len(names) == len(set(names)), "duplicate archive member name")
    groups = {(session, kind, suffix): set() for session in (1, 2, 3)
              for kind, suffix in (("prep", ".mat"), ("raw", ".csv"), ("raw", ".TXT"))}
    for name in names:
        require(isinstance(name, str), "member name type")
        m = re.fullmatch(r"StroopDecData/NirsData/test([123])/(prep|raw)/([^/]+)", name)
        if m is None:
            continue
        session, kind, filename = int(m[1]), m[2], m[3]
        suffix = next((s for s in (".mat", ".csv", ".TXT") if filename.endswith(s)), None)
        require((session, kind, suffix) in groups, "unexpected file in exact recording directory")
        stem = filename[:-len(suffix)]
        require(stem and stem not in (".", "..") and "\\" not in stem, "source basename")
        groups[session, kind, suffix].add(stem)
    roster = groups[1, "prep", ".mat"]
    require(len(roster) == 55 and all(values == roster for values in groups.values()),
            "all55 source basenames must match in all nine complete inventories")
    return {"source_stems": sorted(roster), "recordings": [
        {"source_stem": stem, "session": session,
         "prep_member": f"StroopDecData/NirsData/test{session}/prep/{stem}.mat",
         "raw_csv_member": f"StroopDecData/NirsData/test{session}/raw/{stem}.csv",
         "raw_txt_member": f"StroopDecData/NirsData/test{session}/raw/{stem}.TXT"}
        for stem in sorted(roster) for session in (1, 2, 3)]}


def marker_columns(columns):
    """design_inf row columns2/3/4: first column is a1-based prep sample index.

    Biological row-to-person binding is external and must be verified. This
    function never assigns a person by sorting names or by unverified row order.
    """
    require(isinstance(columns, dict) and set(columns) == set(SOURCE_CODES),
            "exact condition11/12/13 marker columns")
    result = {}
    for code, table in columns.items():
        sequence(table, "marker table")
        indices = []
        for row in table:
            sequence(row, "marker row")
            require(len(row) >= 1, "marker first column absent")
            indices.append(integral(row[0], "MATLAB onset", 1))
        require(len(indices) == len(set(indices)), "duplicate marker indices")
        result[code] = sorted(indices)
    require(len(set(x for rows in result.values() for x in rows))
            == sum(len(rows) for rows in result.values()), "same onset assigned multiple conditions")
    return result


def native_block_plan(vector_onset, columns):
    """Strict join of both author marker representations, then native640 windows.

    The contract's[-5,20) grid is[-128,+512) samples. No padding, interpolation,
    chronological leakage, first30 truncation or class-dependent cropping.
    """
    sequence(vector_onset, "nirsdata.vector_onset")
    count = len(vector_onset)
    declared = marker_columns(columns)
    observed = {code: [] for code in SOURCE_CODES}
    for index, value in enumerate(vector_onset):
        code = integral(value, "vector_onset")
        require(code in (0, 11, 12, 13, 101, 102), "unresolved source marker code")
        if code in observed:
            observed[code].append(index + 1)
    require(observed == declared, "design_inf and nirsdata.vector_onset do not share verified prep coordinates")
    events = sorted((onset, code) for code, onsets in observed.items() for onset in onsets)
    require(events, "no source blocks")
    blocks = []
    for block, (onset1, code) in enumerate(events):
        onset0 = onset1 - 1
        start, stop = onset0 - PRE_SAMPLES, onset0 + POST_SAMPLES
        require(0 <= start < stop <= count, "incomplete native window; no zero padding or silent exclusion")
        if block + 1 < len(events):
            require(stop <= events[block + 1][0] - 1, "window intersects following source block")
        blocks.append({"block": block, "onset_sample1": onset1, "start_sample0": start,
                       "stop_sample0_exclusive": stop, "target": SOURCE_CODES[code]})
    return blocks


def native_windows(nirsdata, columns):
    """Yield one640x70 HbO-then-HbR native block at a time.

    This is input to future validated40x70 serialization, not that serialization.
    Original unit scale is preserved; no unverified molar conversion is applied.
    """
    require(isinstance(nirsdata, dict) and
            {"oxyData", "dxyData", "vector_onset"} <= set(nirsdata), "author nirsdata fields absent")
    oxy, dxy, vector = (nirsdata[k] for k in ("oxyData", "dxyData", "vector_onset"))
    for name, values in (("oxyData", oxy), ("dxyData", dxy)):
        sequence(values, name)
        require(len(values) == len(vector), "signal and marker sample-count mismatch")
        for row in values:
            sequence(row, name + " row")
            require(len(row) == CHANNELS, "exact35 author channels required")
    blocks = native_block_plan(vector, columns)
    for block in blocks:
        matrix = []
        for i in range(block["start_sample0"], block["stop_sample0_exclusive"]):
            row = list(oxy[i]) + list(dxy[i])
            require(all(isinstance(x, numbers.Real) and not isinstance(x, bool) and math.isfinite(x)
                        for x in row), "nonfinite/invalid signal; no implicit imputation or exclusion")
            matrix.append([float(x) for x in row])
        yield {"private_source_block": dict(block), "native_values": matrix,
               "relative_time_seconds": [(i - PRE_SAMPLES) / SAMPLING_HZ for i in range(NATIVE_SAMPLES)],
               "signal_order": "35 source-order HbO channels then35 source-order HbR channels",
               "unit_status": UNIT_STATUS, "sampling_hz": SAMPLING_HZ}


def private_manifest(inventory, aliases, seed_hex, case_key, recording_plans):
    """Bind complete generated/future plans to the already accepted evaluator.

    Keep case_key, aliases, source plans and output in evaluator custody. Neither
    this declaration nor generated tests establish real identity/exposure/rights.
    """
    require(isinstance(case_key, bytes) and len(case_key) == 32, "one precommitted32-byte private case key")
    require(isinstance(aliases, dict) and set(aliases) == set(inventory["source_stems"]),
            "complete separately verified source-to-opaque identity map")
    people = list(aliases.values())
    assignments = fold_assignment(people, seed_hex)
    expected = {(stem, session) for stem in aliases for session in (1, 2, 3)}
    inventory_pairs = {(r["source_stem"], r["session"]) for r in inventory["recordings"]}
    require(len(inventory["recordings"]) == 165 and inventory_pairs == expected and
            all(type(r["session"]) is int for r in inventory["recordings"]), "exact55 times sessions1/2/3 inventory")
    require(len(recording_plans) == 165, "complete165 recording plans")
    seen, cases = set(), []
    for recording in recording_plans:
        stem, session = recording["source_stem"], recording["session"]
        require(type(session) is int, "recording session integer type")
        key = (stem, session)
        require(key in expected and key not in seen, "missing, duplicate or foreign recording")
        seen.add(key)
        blocks = recording["blocks"]
        require(type(recording["n_samples"]) is int, "recording sample count integer type")
        sample_count = integral(recording["n_samples"], "recording sample count", 1)
        require(all(all(type(b[field]) is int for field in
                        ("block", "onset_sample1", "start_sample0", "stop_sample0_exclusive", "target"))
                    for b in blocks), "canonical integral block-plan fields")
        require(blocks and [b["block"] for b in blocks] == list(range(len(blocks))),
                "complete chronological source block indices")
        onsets = [integral(b["onset_sample1"], "plan onset", 1) for b in blocks]
        require(onsets == sorted(set(onsets)), "unique ordered plan onsets")
        targets = {integral(b["target"], "plan target") for b in blocks}
        require(targets <= {0, 1, 2} and (session != 3 or targets == {0, 1, 2}),
                "valid classes and complete three-class support for intended evaluation")
        for index, b in enumerate(blocks):
            require(b["start_sample0"] == b["onset_sample1"] - 1 - 128 and
                    b["stop_sample0_exclusive"] == b["onset_sample1"] - 1 + 512 and
                    0 <= b["start_sample0"] < b["stop_sample0_exclusive"] <= sample_count,
                    "fixed native-grid window geometry")
            if index + 1 < len(blocks):
                require(b["stop_sample0_exclusive"] <= onsets[index + 1] - 1, "plan crosses following source block")
            if session != 3:
                continue
            person = aliases[stem]
            message = b"stroop55-private-case-v1\0" + person.encode("ascii") + b"\0" + str(b["onset_sample1"]).encode("ascii")
            cases.append({"case_id": hmac.new(case_key, message, hashlib.sha256).hexdigest(),
                          "participant": person, "session": 3, "block": b["block"],
                          "fold": assignments[person], "target": b["target"]})
    require(seen == expected, "all source recordings required")
    # HMAC ordering avoids publishing temporal ordering. The key remains private.
    cases.sort(key=lambda x: x["case_id"])
    manifest = {"schema": "stroop55-private-labels-v1", "task": TASK, "partition_seed": seed_hex,
                "cohort": [{"participant": p, "sessions": [1, 2, 3]} for p in sorted(people)],
                "cases": cases}
    validate_manifest(manifest)
    return manifest

