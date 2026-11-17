"""Materialize complete REVE PhysioNet participant inputs without test labels.

Trusted operator preparation, not an execution sandbox or historical reproduction.
Only the released direct-200-Hz profile is accepted. No model is imported or run.
"""
from __future__ import annotations

import argparse
from array import array
import ast
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import sys
import tempfile

SOURCE_COMMIT = "06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7"
PROFILE = "released-06a7059-direct200"
PAPER_SHA256 = "83cbe94dc11b77ea7fd4f1fe46bc896cd25e71eba99b5e449325f794d7d63973"
CODE_SHA256 = "687d7c5d3d45f8351d524c9ace8a8fb970b04324fbece4fc97072f7495622ed7"
PAPER_BYTES = 2717915
CODE_BYTES = 259040
POSITIONS_SHA256 = "f62ca8d7dd4b88e1422ea17348440a41ed0b73b9ff7d12c3b1229492c9b448a5"
POSITIONS_BYTES = 59729
RUNS = (4, 6, 8, 10, 12, 14)
CHANNELS = ("Fc5. Fc3. Fc1. Fcz. Fc2. Fc4. Fc6. C5.. C3.. C1.. Cz.. C2.. C4.. C6.. "
            "Cp5. Cp3. Cp1. Cpz. Cp2. Cp4. Cp6. Fp1. Fpz. Fp2. Af7. Af3. Afz. Af4. Af8. "
            "F7.. F5.. F3.. F1.. Fz.. F2.. F4.. F6.. F8.. Ft7. Ft8. T7.. T8.. T9.. T10. "
            "Tp7. Tp8. P7.. P5.. P3.. P1.. Pz.. P2.. P4.. P6.. P8.. Po7. Po3. Poz. Po4. "
            "Po8. O1.. Oz.. O2.. Iz..").split()
ELECTRODES = ("FC5 FC3 FC1 FCz FC2 FC4 FC6 C5 C3 C1 CZ C2 C4 C6 CP5 CP3 CP1 CPz CP2 CP4 CP6 "
              "FP1 Fpz FP2 AF7 AF3 AFz AF4 AF8 F7 F5 F3 F1 FZ F2 F4 F6 F8 FT7 FT8 T3 T4 T9 T10 "
              "TP7 TP8 T5 P5 P3 P1 PZ P2 P4 P6 T6 PO7 PO3 POz PO4 PO8 O1 OZ O2 Iz").split()
MAX_JSON_BYTES = 16 * 1024**2
MAX_SHARD_BYTES = 64 * 1024**2
MAX_TOTAL_BYTES = 8 * 1024**3
CHUNK = 64 * 1024
HEX = re.compile(r"[0-9a-f]{64}\Z")
CONDITIONS = ("paper_data", "paper_data_code")


class MaterialError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise MaterialError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def identity(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _state(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


@contextmanager
def regular(path, cap):
    """Open one bounded ordinary source file; reject aliases and detect mutation."""
    path = Path(path)
    require(type(cap) is int and 0 < cap <= MAX_TOTAL_BYTES, "invalid byte limit")
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) |
                     getattr(os, "O_NONBLOCK", 0))
    except OSError as exc:
        raise MaterialError(f"cannot open ordinary source: {path.name}") from exc
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                "source must be a regular file without hardlink aliases")
        require(0 < before.st_size <= cap, "source size outside bounded input limit")
        require(not path.is_symlink(), "source symlink is forbidden")
        yield handle, before.st_size
        after = os.fstat(handle.fileno())
        require(_state(before) == _state(after), "source changed during read")
        require(_state(path.stat(follow_symlinks=False)) == _state(before),
                "source pathname changed during read")


def read_json(path):
    with regular(path, MAX_JSON_BYTES) as (handle, size):
        body = handle.read(MAX_JSON_BYTES + 1)
        require(len(body) == size, "JSON source length changed")
    try:
        value = json.loads(body, object_pairs_hook=_unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(MaterialError("nonfinite JSON")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise MaterialError("invalid bounded JSON source") from exc
    require(isinstance(value, dict), "JSON document must be an object")
    return value


def split_for(person):
    return "train" if person <= 70 else "val" if person <= 89 else "test"


def validate_panel(document):
    """Authenticate the exact existing panel schema and complete source roster."""
    require(isinstance(document, dict), "panel must be an object")
    panel = dict(document)
    stored = panel.pop("panel_identity", None)
    require(isinstance(stored, str) and HEX.fullmatch(stored) and identity(panel) == stored,
            "panel identity mismatch")
    require(panel.get("schema") == "reve-original-physionet-inputs-v1" and
            panel.get("source_commit") == SOURCE_COMMIT and panel.get("profile") == PROFILE,
            "exact released source/profile required; historical 128-Hz recipe is unresolved")
    require(panel.get("units") == "uV" and panel.get("dtype") == "float64" and
            panel.get("sampling_hz") == 200 and panel.get("channels") == CHANNELS,
            "exact physical observation contract required")
    require(panel.get("historical_recipe_verified") is False, "historical recipe cannot be promoted")
    require(isinstance(panel.get("targets_identity"), str) and
            HEX.fullmatch(panel["targets_identity"]), "target identity missing")
    records = panel.get("records")
    expected = [(p, r, split_for(p)) for p in range(1, 110) for r in RUNS]
    require(isinstance(records, list) and len(records) == 654,
            "all 109 people and six original runs are required")
    require(all(isinstance(r, dict) for r in records), "invalid recording record")
    require([(r.get("participant"), r.get("run"), r.get("split")) for r in records] == expected,
            "ordered original 654-record cohort/split required")
    seen, counts = set(), {"train": 0, "val": 0, "test": 0}
    for row in records:
        p, r = row["participant"], row["run"]
        require(type(p) is int and type(r) is int, "integer person/run required")
        require(row.get("signal") == f"S{p:03d}R{r:02d}.npy", "signal path must be the exact local basename")
        shape = row.get("shape")
        require(isinstance(shape, list) and len(shape) == 3 and
                all(type(n) is int for n in shape) and shape[0] > 0 and shape[1:] == [64, 800],
                "complete float64 [epochs,64,800] shard required")
        require(math.prod(shape) * 8 + 65548 <= MAX_SHARD_BYTES, "shard exceeds finite allocation")
        require(isinstance(row.get("sha256"), str) and HEX.fullmatch(row["sha256"]), "invalid shard SHA256")
        ids = row.get("event_ids")
        require(isinstance(ids, list) and len(ids) == shape[0], "event mapping/shape mismatch")
        expression = re.compile(fr"S{p:03d}R{r:02d}-event[0-9]{{3,}}\Z")
        for eid in ids:
            require(isinstance(eid, str) and expression.fullmatch(eid), "event ID does not bind its person/run")
            require(eid not in seen, "duplicate event ID")
            seen.add(eid)
        counts[row["split"]] += shape[0]
    require(panel.get("counts") == counts and panel.get("observed_epoch_count") == sum(counts.values()),
            "epoch accounting mismatch")
    require(panel.get("published_epoch_count") == 9837 and
            panel.get("published_epoch_count_matches") is (sum(counts.values()) == 9837),
            "published count must remain descriptive")
    return document


def project_targets(panel, target_document):
    """Bind every source target then return only training/validation labels."""
    require(target_document.get("panel_identity") == panel["panel_identity"], "target panel mismatch")
    targets = target_document.get("targets")
    require(isinstance(targets, list) and identity(targets) == panel["targets_identity"],
            "complete original target manifest identity required")
    expected = {eid: (row["participant"], row["run"], row["split"])
                for row in panel["records"] for eid in row["event_ids"]}
    require(len(targets) == len(expected), "target roster length differs")
    seen, allowed = set(), {}
    for row in targets:
        require(isinstance(row, dict), "invalid target row")
        eid = row.get("event_id")
        require(isinstance(eid, str) and eid in expected and eid not in seen, "target event must be a bijection")
        seen.add(eid)
        require((row.get("participant"), row.get("run"), row.get("split")) == expected[eid] and
                type(row.get("participant")) is int and type(row.get("run")) is int,
                "target source person/run/split mismatch")
        label = row.get("label")
        require(type(label) is int and label in range(4), "four-class integer label required")
        require(label in ((0, 1) if row["run"] in (4, 8, 12) else (2, 3)),
                "label incompatible with source imagery run")
        if row["split"] != "test":
            allowed[eid] = label
    return allowed


def _write_json(path, value):
    body = canonical(value) + b"\n"
    require(len(body) <= MAX_JSON_BYTES, "output JSON exceeds bound")
    with Path(path).open("xb") as handle:
        handle.write(body)
    os.chmod(path, 0o444)
    return len(body)


def _copy_blob(source, destination, expected_hash, expected_size):
    digest = hashlib.sha256()
    with regular(source, expected_size) as (inp, size):
        require(size == expected_size, "pinned source length differs")
        with Path(destination).open("xb") as out:
            remaining = size
            while remaining:
                chunk = inp.read(min(CHUNK, remaining))
                require(chunk, "pinned source truncated during copy")
                digest.update(chunk)
                out.write(chunk)
                remaining -= len(chunk)
            require(inp.read(1) == b"", "pinned source grew during copy")
    require(digest.hexdigest() == expected_hash, "pinned document/source archive digest differs")
    os.chmod(destination, 0o444)
    return size


def copy_signal(source, destination, row):
    """Copy exactly one finite C-order little-endian float64 NPY, streaming."""
    digest = hashlib.sha256()
    with regular(source, MAX_SHARD_BYTES) as (inp, size):
        prefix = inp.read(8)
        require(prefix[:6] == b"\x93NUMPY" and prefix[6:] in (b"\x01\x00", b"\x02\x00", b"\x03\x00"),
                "ordinary NumPy array format required")
        width = 2 if prefix[6] == 1 else 4
        encoded_size = inp.read(width)
        require(len(encoded_size) == width, "truncated NumPy header length")
        header_size = int.from_bytes(encoded_size, "little")
        require(0 < header_size <= 65536, "bounded NumPy header required")
        header = inp.read(header_size)
        require(len(header) == header_size, "truncated NumPy header")
        try:
            fields = ast.literal_eval(header.decode("utf-8" if prefix[6] == 3 else "latin1"))
        except (ValueError, SyntaxError, UnicodeError, RecursionError) as exc:
            raise MaterialError("invalid NumPy header") from exc
        require(isinstance(fields, dict) and set(fields) == {"descr", "fortran_order", "shape"},
                "unexpected NumPy header fields")
        require(fields["descr"] == "<f8" and fields["fortran_order"] is False and
                fields["shape"] == tuple(row["shape"]) and
                all(type(n) is int for n in fields["shape"]), "NumPy header differs from exact shard contract")
        prefix = prefix + encoded_size + header
        require(size == len(prefix) + math.prod(row["shape"]) * 8, "NumPy payload length differs")
        digest.update(prefix)
        with Path(destination).open("xb") as out:
            out.write(prefix)
            remaining = size - len(prefix)
            while remaining:
                chunk = inp.read(min(CHUNK, remaining))
                require(chunk and len(chunk) % 8 == 0, "truncated float64 payload")
                numbers = array("d")
                numbers.frombytes(chunk)
                if sys.byteorder != "little":
                    numbers.byteswap()
                require(all(math.isfinite(x) for x in numbers), "nonfinite signal payload")
                digest.update(chunk)
                out.write(chunk)
                remaining -= len(chunk)
            require(inp.read(1) == b"", "unexpected trailing signal bytes")
    require(digest.hexdigest() == row["sha256"], "signal shard digest mismatch")
    os.chmod(destination, 0o444)
    return size


def public_rows(panel, labels):
    """Whitelist the candidate schema; never forward arbitrary source fields."""
    rows = []
    for source in panel["records"]:
        row = {key: source[key] for key in ("participant", "run", "split", "shape", "sha256", "event_ids")}
        row["signal"] = "signals/" + source["signal"]
        if source["split"] != "test":
            row["labels"] = [labels[eid] for eid in source["event_ids"]]
        rows.append(row)
    return rows


def make_manifest(panel, labels, condition):
    """Construct the same observation payload under either official-code condition."""
    require(condition in CONDITIONS, "unknown access condition")
    data = {"profile": PROFILE, "units": "uV", "dtype": "float64", "sampling_hz": 200,
            "channels": CHANNELS, "class_order": ["left_fist", "right_fist", "both_fists", "feet"],
            "counts": panel["counts"], "records": public_rows(panel, labels),
            "geometry": {"path": "positions.json", "sha256": POSITIONS_SHA256,
                         "bytes": POSITIONS_BYTES, "electrodes_in_signal_channel_order": ELECTRODES,
                         "coordinate_convention": "unchanged numeric coordinates in the pinned author bank"}}
    manifest = {"schema": "reve-candidate-materials-v1", "condition": condition,
                "source_panel_identity": panel["panel_identity"], "source_commit": SOURCE_COMMIT,
                "data_identity": identity(data), "data": data,
                "published_epoch_count": panel["published_epoch_count"],
                "observed_epoch_count": panel["observed_epoch_count"],
                "published_epoch_count_matches": panel["published_epoch_count_matches"],
                "paper": {"path": "paper.pdf", "sha256": PAPER_SHA256, "bytes": PAPER_BYTES},
                "official_code": ({"path": "official-code.tar.gz", "sha256": CODE_SHA256,
                                   "bytes": CODE_BYTES, "commit": SOURCE_COMMIT}
                                  if condition == "paper_data_code" else None),
                "test_labels_delivered": False, "historical_recipe_verified": False,
                "scientific_qualification": False,
                "limits": ["Trusted operator export; mount only this tree into a separately qualified candidate environment.",
                           "Original annotations are publicly exposed; physical omission does not create a new secret holdout.",
                           "Pretrained encoder weights are not included; identical pretrained access requires separate provision and admission.",
                           "Full Table12 preprocessing, trained classifier and seed/run aggregation remain unresolved."]}
    manifest["materials_identity"] = identity(manifest)
    return manifest


def discard_owned_tree(path, owner):
    """Remove only the directory inode created by this invocation."""
    try:
        current = Path(path).lstat()
    except FileNotFoundError:
        return False
    if not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != owner:
        return False
    for directory, _dirs, _files in os.walk(path):
        os.chmod(directory, 0o700)
    shutil.rmtree(path)
    return True


def publish(stage, output):
    """Keep the private0700 root movable on macOS, finalize permissions on success."""
    info = Path(stage).lstat()
    owner = info.st_dev, info.st_ino
    require(stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700,
            "private stage root required before publication")
    require(not Path(output).exists() and not Path(output).is_symlink(), "output appeared during export")
    moved = False
    try:
        # The operator-owned parent must not have concurrent untrusted writers.
        os.rename(stage, output)
        moved = True
        current = Path(output).lstat()
        require((current.st_dev, current.st_ino) == owner, "published directory identity changed")
        os.chmod(output, 0o555)
    except BaseException:
        if moved:
            discard_owned_tree(output, owner)
        raise


def export(panel_path, targets_path, paper_path, output, *, condition, expected_panel_identity, positions_path,
           code_archive=None, max_bytes=MAX_TOTAL_BYTES):
    """Make a fresh physical participant tree, publishing only after validation.

    The caller must authenticate custody of the original prepared panel. Hashes
    establish internal consistency, not independent biological provenance.
    Failure removes only this invocation's temporary tree. No existing destination
    is overwritten, and no symlinks or hardlinks to operator files are created.
    """
    require(condition in CONDITIONS, "explicit paper/data access condition required")
    require((condition == "paper_data_code") == (code_archive is not None),
            "official code archive is required only in the code-assisted condition")
    require(type(max_bytes) is int and 0 < max_bytes <= MAX_TOTAL_BYTES, "bounded positive output budget required")
    panel_path = Path(panel_path)
    signal_root = panel_path.parent.resolve(strict=True)
    # A resolved root is intentional; all source members below it must be ordinary.
    require(not (signal_root / panel_path.name).is_symlink(), "panel symlink is forbidden")
    panel = validate_panel(read_json(signal_root / panel_path.name))
    require(isinstance(expected_panel_identity, str) and HEX.fullmatch(expected_panel_identity) and
            panel["panel_identity"] == expected_panel_identity,
            "panel differs from independently selected operator identity")
    labels = project_targets(panel, read_json(targets_path))
    rows = public_rows(panel, labels)
    expected_signal_bytes = sum(math.prod(r["shape"]) * 8 + 65548 for r in rows)
    require(expected_signal_bytes + PAPER_BYTES + POSITIONS_BYTES + (CODE_BYTES if code_archive else 0) + MAX_JSON_BYTES <= max_bytes,
            "complete material budget is insufficient; no truncated panel is emitted")
    output = Path(output).absolute()
    require(output.name not in ("", ".", ".."), "named output directory required")
    parent = output.parent.resolve(strict=True)
    output = parent / output.name
    require(not output.exists() and not output.is_symlink(), "fresh output destination required")
    require(not output.is_relative_to(signal_root) and not signal_root.is_relative_to(output),
            "participant output must be separate from the source signal tree")
    stage = Path(tempfile.mkdtemp(prefix=".reve-materials-", dir=parent))
    stage_info = stage.lstat()
    stage_owner = stage_info.st_dev, stage_info.st_ino
    known_written = 0
    try:
        (stage / "signals").mkdir(mode=0o700)
        known_written += _copy_blob(paper_path, stage / "paper.pdf", PAPER_SHA256, PAPER_BYTES)
        known_written += _copy_blob(positions_path, stage / "positions.json", POSITIONS_SHA256, POSITIONS_BYTES)
        geometry = read_json(stage / "positions.json")
        require(len(geometry) == 543 and all(name in geometry for name in ELECTRODES),
                "complete original position bank and all64 ordered electrode aliases required")
        require(all(isinstance(key, str) and isinstance(value, list) and len(value) == 3 and
                    all(type(number) in (float, int) and math.isfinite(number) for number in value)
                    for key, value in geometry.items()), "finite three-coordinate author bank required")
        if code_archive is not None:
            known_written += _copy_blob(code_archive, stage / "official-code.tar.gz", CODE_SHA256, CODE_BYTES)
        for source in panel["records"]:
            known_written += copy_signal(signal_root / source["signal"], stage / "signals" / source["signal"], source)
        manifest = make_manifest(panel, labels, condition)
        known_written += _write_json(stage / "materials.json", manifest)
        require(known_written <= max_bytes, "completed export exceeds byte allocation")
        os.chmod(stage / "signals", 0o555)
        publish(stage, output)
        return {"schema": "reve-candidate-materials-receipt-v1", "condition": condition,
                "materials_identity": manifest["materials_identity"], "data_identity": manifest["data_identity"],
                "source_panel_identity": panel["panel_identity"], "recordings": 654, "participants": 109,
                "counts": panel["counts"], "labelled_epochs": len(labels), "test_labels_delivered": False,
                "created_bytes": known_written, "files": 657 + int(code_archive is not None),
                "scientific_qualification": False}
    except BaseException:
        discard_owned_tree(stage, stage_owner)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", required=True)
    parser.add_argument("--expected-panel-identity", required=True)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--paper", required=True)
    parser.add_argument("--positions", required=True)
    parser.add_argument("--condition", choices=CONDITIONS, required=True)
    parser.add_argument("--code-archive")
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-bytes", type=int, default=MAX_TOTAL_BYTES)
    args = parser.parse_args(argv)
    result = export(args.panel, args.targets, args.paper, args.output,
                    condition=args.condition, expected_panel_identity=args.expected_panel_identity,
                    positions_path=args.positions, code_archive=args.code_archive, max_bytes=args.max_bytes)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
