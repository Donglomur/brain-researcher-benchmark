"""Bounded BrainVision EEG observation preparation for NEURAL-065.

Consumes an independently frozen sample-window plan. It neither reads behavioral
logs/targets nor derives alignment, filters signals, fits scalers or runs models.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import tempfile

TASK_ID = "NEURAL-065"
DATA_COMMIT = "88f9096c6ce3a3fb17cc7b8e3131ff7f96da5684"
SOURCE_COMMIT = "5f9889621d0df391c5aab37c996683d308e6e926"
FORMATS = {"INT_16": ("h", 2), "IEEE_FLOAT_32": ("f", 4)}
UNITS = {"V": 1.0, "mV": 1e-3, "uV": 1e-6, "µV": 1e-6, "μV": 1e-6}


class PreparationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PreparationError(message)


def exact_keys(value, names, context):
    require(isinstance(value, dict) and set(value) == set(names.split()), context + ": fields")


def positive_int(value, name):
    require(type(value) is int and value > 0, name + ": positive integer required")
    return value


def sha(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "invalid SHA256")
    return value


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def open_regular(path):
    """Do not follow a final symlink or wait on a FIFO supplied as a source."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise PreparationError("source must be a regular file")
    return os.fdopen(fd, "rb")


def hash_stream(stream, maximum):
    total = 0
    digest = hashlib.sha256()
    while True:
        chunk = stream.read(min(65536, maximum - total + 1))
        if not chunk:
            break
        total += len(chunk)
        require(total <= maximum, "source byte limit exceeded")
        digest.update(chunk)
    stream.seek(0)
    return digest.hexdigest(), total


def pinned_small_file(path, expected, maximum):
    sha(expected)
    with open_regular(path) as stream:
        raw = stream.read(maximum + 1)
    require(len(raw) <= maximum, "metadata byte limit exceeded")
    require(hashlib.sha256(raw).hexdigest() == expected, "metadata digest mismatch")
    return raw


def parse_plan(raw):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            require(key not in obj, "duplicate JSON field")
            obj[key] = value
        return obj
    def bad(value):
        raise PreparationError("nonfinite JSON constant")
    try:
        plan = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=bad)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise PreparationError("invalid plan JSON") from exc
    exact_keys(plan, "schema_version task_id source_commit data_commit recording_subject session_id "
               "selection_sha256 alignment_evidence_sha256 channel_names windows", "plan")
    require(type(plan["schema_version"]) is int and plan["schema_version"] == 1, "plan version")
    require(plan["task_id"] == TASK_ID and plan["source_commit"] == SOURCE_COMMIT
            and plan["data_commit"] == DATA_COMMIT, "task/source version mismatch")
    subject = plan["recording_subject"]
    require(isinstance(subject, str) and re.fullmatch(r"Pinet2024Eeg/[0-9]{3}", subject), "canonical EEG subject required")
    require(int(subject.rsplit("/", 1)[1]) > 1, "source-excluded EEG subject")
    require(isinstance(plan["session_id"], str) and re.fullmatch(r"session[1-9][0-9]*", plan["session_id"]), "session identifier")
    sha(plan["selection_sha256"]); sha(plan["alignment_evidence_sha256"])
    names = plan["channel_names"]
    require(isinstance(names, list) and names and all(isinstance(x, str) and x for x in names), "channel roster")
    require(len(names) == len(set(names)) and len(names) <= 4096, "duplicate/oversized channel roster")
    windows = plan["windows"]
    require(isinstance(windows, list) and windows, "empty window inventory")
    seen_ids, seen_windows = set(), set()
    for row in windows:
        exact_keys(row, "query_id start_sample stop_sample", "window")
        qid, first, stop = row["query_id"], row["start_sample"], row["stop_sample"]
        require(isinstance(qid, str) and re.fullmatch(r"[0-9a-f]{32}", qid), "opaque query ID required")
        require(qid not in seen_ids, "duplicate query ID")
        require(type(first) is int and type(stop) is int and 0 <= first < stop, "invalid sample interval")
        require((first, stop) not in seen_windows, "duplicate sample interval")
        seen_ids.add(qid); seen_windows.add((first, stop))
    return plan


def parse_header(raw):
    """Read the restricted binary, multiplexed BrainVision 1.0 profile."""
    try:
        # BrainVision ANSI files use Windows-1252; UTF-8 files declare UTF-8.
        utf8 = re.search(br"(?im)^Codepage\s*=\s*UTF-8\s*$", raw) is not None
        text = raw.decode("utf-8-sig" if utf8 else "cp1252")
        lines = text.splitlines()
        require(lines and lines[0].strip() in {
            "BrainVision Data Exchange Header File Version 1.0",
            "Brain Vision Data Exchange Header File Version 1.0"}, "unsupported BrainVision header")
        parser = configparser.ConfigParser(interpolation=None, strict=True, comment_prefixes=(";",))
        # Trailing [Comment] is free-form acquisition text, not participant data.
        body = re.split(r"(?im)^\[Comment\]\s*$", "\n".join(lines[1:]), maxsplit=1)[0]
        parser.read_string(body)
        common, binary, channel = parser["Common Infos"], parser["Binary Infos"], parser["Channel Infos"]
        require(not parser.defaults(), "header defaults forbidden")
        require(common["DataFormat"] == "BINARY" and common["DataOrientation"] == "MULTIPLEXED", "unsupported storage orientation/format")
        require(binary.get("UseBigEndianOrder", "NO") == "NO", "big-endian data unsupported")
        fmt = binary["BinaryFormat"]
        require(fmt in FORMATS, "unsupported binary sample type")
        n_channels = int(common["NumberOfChannels"])
        require(0 < n_channels <= 4096, "invalid channel count")
        interval_us = float(common["SamplingInterval"])
        require(math.isfinite(interval_us) and interval_us > 0, "invalid sampling interval")
        frequency = 1e6 / interval_us
        require(math.isfinite(frequency) and frequency > 0, "invalid sampling frequency")
        filename = common["DataFile"]
        require(filename and Path(filename).name == filename and "/" not in filename and "\\" not in filename, "data file must be a basename")
        require(set(channel) == {f"ch{i}" for i in range(1, n_channels + 1)}, "incomplete/extra channel rows")
        channels = []
        for i in range(1, n_channels + 1):
            fields = channel[f"Ch{i}"].split(",")
            require(len(fields) == 4, "channel requires name,reference,resolution,unit")
            name, reference, resolution, unit = [x.strip().replace("\\1", ",") for x in fields]
            require(name and unit in UNITS, "missing channel name or unsupported physical unit")
            resolution = float(resolution)
            require(math.isfinite(resolution) and resolution > 0, "invalid channel resolution")
            scale = resolution * UNITS[unit]
            require(math.isfinite(scale) and scale > 0, "invalid SI scale")
            channels.append({"name": name, "reference": reference, "resolution": resolution,
                             "source_unit": unit, "scale_to_volts": scale, "index": i - 1})
        require(len({x["name"] for x in channels}) == n_channels, "duplicate source channel name")
        return {"data_file": filename, "n_channels": n_channels, "format": fmt,
                "sampling_frequency_hz": frequency, "channels": channels}
    except (UnicodeError, configparser.Error, KeyError, ValueError, OverflowError) as exc:
        if isinstance(exc, PreparationError):
            raise
        raise PreparationError("malformed BrainVision header") from exc


def prepare(header_path, data_path, plan_path, output, *, header_sha256, data_sha256,
            plan_sha256, max_source_bytes, max_output_bytes):
    """Publish atomically after source and every selected output pass validation."""
    positive_int(max_source_bytes, "source limit"); positive_int(max_output_bytes, "output limit")
    sha(data_sha256)
    header_path, data_path, plan_path, output = map(Path, (header_path, data_path, plan_path, output))
    require(not output.exists() and not output.is_symlink(), "output already exists")
    raw_header = pinned_small_file(header_path, header_sha256, 65536)
    raw_plan = pinned_small_file(plan_path, plan_sha256, 4 * 1024 * 1024)
    header, plan = parse_header(raw_header), parse_plan(raw_plan)
    require(data_path.name == header["data_file"], "data file/header name mismatch")
    require(header_path.parent.resolve() == data_path.parent.resolve(), "data must share header directory")
    eligible = [ch for ch in header["channels"] if "EOG" not in ch["name"]]
    # Native loader keeps source order and excludes EOG. No silent channel subset.
    require(plan["channel_names"] == [ch["name"] for ch in eligible], "plan must retain all non-EOG source channels in order")
    require(eligible, "no eligible EEG channels")
    subject = plan["recording_subject"].rsplit("/", 1)[1]
    session = plan["session_id"].removeprefix("session")
    require(re.fullmatch(re.escape(subject) + r"_DECOMEG_S" + re.escape(session) +
                         r"_[0-9]+_task(?:1|2)?\.eeg", data_path.name), "recording identity/task mismatch")
    fmt, sample_bytes = FORMATS[header["format"]]
    frame_bytes = sample_bytes * header["n_channels"]
    planned_bytes = sum((row["stop_sample"] - row["start_sample"]) * len(eligible) * 8 for row in plan["windows"])
    require(planned_bytes <= max_output_bytes, "observation output byte limit exceeded")
    require(output.parent.is_dir(), "output parent missing")
    staging = None
    try:
        with open_regular(data_path) as stream:
            digest, source_bytes = hash_stream(stream, max_source_bytes)
            require(digest == data_sha256, "neural source digest mismatch")
            require(source_bytes > 0 and source_bytes % frame_bytes == 0, "truncated/incomplete source frame")
            n_samples = source_bytes // frame_bytes
            require(all(w["stop_sample"] <= n_samples for w in plan["windows"]), "sample interval outside recording")
            staging = Path(tempfile.mkdtemp(prefix=".neural065-", dir=output.parent))
            (staging / "assets").mkdir()
            observations, asset_hashes = [], set()
            decoder = struct.Struct("<" + fmt * header["n_channels"])
            encoder = struct.Struct("<" + "d" * len(eligible))
            frames_per_chunk = max(1, 65536 // frame_bytes)
            for window in plan["windows"]:
                count = window["stop_sample"] - window["start_sample"]
                stream.seek(window["start_sample"] * frame_bytes)
                asset = "assets/" + window["query_id"] + ".f64le"
                asset_digest = hashlib.sha256()
                with (staging / asset).open("xb") as target:
                    remaining = count
                    while remaining:
                        take = min(remaining, frames_per_chunk)
                        block = stream.read(take * frame_bytes)
                        require(len(block) == take * frame_bytes, "source changed/truncated during extraction")
                        converted = bytearray()
                        for frame in decoder.iter_unpack(block):
                            # Check all source samples, including excluded EOG channels.
                            require(all(math.isfinite(v) for v in frame), "nonfinite source sample")
                            values = [frame[ch["index"]] * ch["scale_to_volts"] for ch in eligible]
                            require(all(math.isfinite(v) for v in values), "nonfinite scaled sample")
                            converted.extend(encoder.pack(*values))
                        target.write(converted); asset_digest.update(converted)
                        remaining -= take
                asset_hash = asset_digest.hexdigest()
                require(asset_hash not in asset_hashes, "duplicate observation content")
                asset_hashes.add(asset_hash)
                observations.append({"query_id": window["query_id"], "neural_asset_sha256": asset_hash,
                    "path": asset, "bytes": count * encoder.size, "shape": [count, len(eligible)]})
            # A second hash detects in-place changes while extracting; no file reopening.
            stream.seek(0)
            require(hash_stream(stream, max_source_bytes) == (digest, source_bytes), "source changed during extraction")
        manifest = {"schema_version": 1, "task_id": TASK_ID, "modality": "EEG",
            "dtype": "float64", "byte_order": "little", "axes": ["time", "channel"],
            "unit": "V", "sampling_frequency_hz": header["sampling_frequency_hz"],
            "time_origin_s": 0, "time_coordinate": "sample_index / sampling_frequency_hz, relative to each window",
            # Preserve one-to-one channel correspondence without copying free text.
            "channel_ids": [f"EEG{i:03d}" for i in range(len(eligible))], "observations": observations}
        (staging / "observations.json").write_bytes(json_bytes(manifest))
        receipt = {"schema_version": 1, "task_id": TASK_ID, "source_commit": SOURCE_COMMIT,
            "data_commit": DATA_COMMIT, "header_sha256": header_sha256, "data_sha256": data_sha256,
            "plan_sha256": plan_sha256, "source_bytes": source_bytes, "source_samples": n_samples,
            "plan": plan, "source_channel_metadata": header["channels"], "output_data_bytes": planned_bytes,
            "manifest_sha256": hashlib.sha256((staging / "observations.json").read_bytes()).hexdigest(),
            "qualification": "preparation_component_only", "native_alignment_reconstructed": False,
            "source_authenticity": "external hash provenance required", "model_executed": False}
        # Private provenance is deliberately outside the participant directory.
        private_receipt = output.parent / (output.name + ".private-receipt.json")
        require(not private_receipt.exists() and not private_receipt.is_symlink(), "private receipt already exists")
        with private_receipt.open("xb") as handle:
            os.chmod(private_receipt, 0o600)
            handle.write(json_bytes(receipt))
        require(not output.exists() and not output.is_symlink(), "output appeared during extraction")
        staging.rename(output)
        staging = None
        return {"observations": len(observations), "source_bytes": source_bytes,
                "output_data_bytes": planned_bytes, "qualification": "preparation_component_only"}
    finally:
        if staging is not None:
            shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("header", "data", "plan", "output", "header-sha256", "data-sha256", "plan-sha256"):
        parser.add_argument("--" + name, required=True)
    for name in ("max-source-bytes", "max-output-bytes"):
        parser.add_argument("--" + name, required=True, type=int)
    args = vars(parser.parse_args())
    try:
        result = prepare(args.pop("header"), args.pop("data"), args.pop("plan"), args.pop("output"), **args)
        print(json.dumps(result, sort_keys=True))
    except (PreparationError, OSError) as exc:
        parser.exit(2, "preparation refused: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
