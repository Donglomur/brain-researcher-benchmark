"""Prepare explicit mouse grouping for the unchanged native summary function.

This reads roster metadata and file metadata only. It does not inspect MAT
payloads, select eligible pairs, run MATLAB, or qualify an original-paper cohort.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(f"{label} contains a control character")
    return value


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_inputs(roster_bytes: bytes, input_root: Path) -> list[dict]:
    """Validate every declared location, preserving its order and mouse label."""
    roster = json.loads(roster_bytes, object_pairs_hook=_unique_keys)
    if not isinstance(roster, dict) or set(roster) != {"schema", "records"}:
        raise ValueError("roster requires exactly schema and records")
    if roster["schema"] != "unitmatch-summary-roster/v1":
        raise ValueError("unsupported roster schema")
    records = roster["records"]
    if not isinstance(records, list) or not records:
        raise ValueError("records must be a nonempty list")
    root = input_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("input root must be a directory")
    groups: dict[str, int] = {}
    identities = set()
    files = set()
    inputs = []
    for index, record in enumerate(records):
        if not isinstance(record, dict) or set(record) != {
            "mouse_id", "location_id", "unitmatch_file"
        }:
            raise ValueError(f"record {index} requires mouse_id, location_id, unitmatch_file")
        mouse = _text(record["mouse_id"], "mouse_id")
        location = _text(record["location_id"], "location_id")
        identity = (mouse, location)
        if identity in identities:
            raise ValueError(f"duplicate mouse/location identity in record {index}")
        identities.add(identity)
        relative = _text(record["unitmatch_file"], "unitmatch_file")
        path = PurePosixPath(relative)
        if (path.is_absolute() or "\\" in relative or
                any(part in {"", ".", ".."} for part in relative.split("/")) or
                path.name != "UnitMatch.mat"):
            raise ValueError("unitmatch_file must be a relative path ending in UnitMatch.mat")
        full_path = root.joinpath(*path.parts).resolve(strict=True)
        if not full_path.is_relative_to(root):
            raise ValueError("unitmatch_file resolves outside the input root")
        if not full_path.is_file() or full_path.stat().st_size == 0:
            raise ValueError("unitmatch_file must be a nonempty regular file")
        stat = full_path.stat()
        file_identity = (stat.st_dev, stat.st_ino)
        if file_identity in files:
            raise ValueError("the same UnitMatch file appears more than once")
        files.add(file_identity)
        group = groups.setdefault(mouse, len(groups) + 1)
        inputs.append({**record, "absolute_file": str(full_path), "group": group})
    return inputs


def _matlab_string(value: str) -> str:
    # A single-quoted MATLAB character vector escapes an apostrophe by doubling.
    return "'" + value.replace("'", "''") + "'"


def render_script(inputs: list[dict], output_file: Path) -> str:
    def cell(field: str) -> str:
        return "{" + ", ".join(_matlab_string(row[field]) for row in inputs) + "}"

    groups = " ".join(str(row["group"]) for row in inputs)
    return f"""% Generated preparation for summaryFunctionalPlots; no cohort qualification.
% Configure the complete pinned author checkout and dependencies on MATLAB's path.
UMFiles = {cell('absolute_file')};
mouseIds = {cell('mouse_id')};
locationIds = {cell('location_id')};
groupVector = [{groups}];
resultFile = {_matlab_string(str(output_file))};
assert(~isfile(resultFile), 'Refusing to overwrite native summary output');
for fileIndex = 1:numel(UMFiles)
    assert(isfile(UMFiles{{fileIndex}}), 'A declared UnitMatch file is missing');
end
resolvedSummaryFunction = which('summaryFunctionalPlots');
assert(~isempty(resolvedSummaryFunction), 'Configure the complete author checkout first');
res = summaryFunctionalPlots(UMFiles, 'Corr', groupVector, 0, 0);
save(resultFile, 'res', 'UMFiles', 'mouseIds', 'locationIds', ...
    'groupVector', 'resolvedSummaryFunction', '-v7.3');
"""


def prepare(roster_path: Path, input_root: Path, output_dir: Path) -> dict:
    """Create a fresh preparation directory; never load a scientific array."""
    roster_bytes = roster_path.read_bytes()
    inputs = load_inputs(roster_bytes, input_root)
    output_dir = output_dir.absolute()
    # Root paths also become MATLAB literals, so reject newline injection there.
    for row in inputs:
        _text(row["absolute_file"], "resolved input path")
    _text(str(output_dir), "output path")
    script = render_script(inputs, output_dir / "native_summary.mat")
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "roster.json").write_bytes(roster_bytes)
    (output_dir / "run_summary.m").write_text(script, encoding="utf-8")
    return {
        "locations": len(inputs),
        "mice": len({row["mouse_id"] for row in inputs}),
        "group_vector": [row["group"] for row in inputs],
        "matlab_executed": False,
        "original_cohort_qualified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roster", required=True, type=Path)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = prepare(args.roster, args.input_root, args.output)
    except (OSError, ValueError) as error:
        parser.exit(2, f"preparation refused: {error}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
