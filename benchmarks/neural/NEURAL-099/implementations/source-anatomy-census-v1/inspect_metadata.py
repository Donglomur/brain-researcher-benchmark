"""Inspect authenticated NWB identity/anatomy metadata; never load response arrays."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import h5py
import numpy as np


ALLOWED_ARRAYS = {
    "units/id", "units/electrodes", "units/electrodes_index", "units/quality",
    "general/extracellular_ephys/electrodes/id",
    "general/extracellular_ephys/electrodes/location",
    "general/extracellular_ephys/electrodes/group_name",
    "general/extracellular_ephys/electrodes/group",
    "general/extracellular_ephys/electrodes/x",
    "general/extracellular_ephys/electrodes/y",
    "general/extracellular_ephys/electrodes/z",
}
ALLOWED_SCALARS = {
    "session_description", "session_start_time", "timestamps_reference_time",
    "general/session_id", "general/subject/subject_id", "general/subject/sex",
    "general/subject/species", "general/subject/strain", "general/subject/age",
    "general/subject/date_of_birth", "general/subject/description", "identifier",
}
READS: list[str] = []
HERE = Path(__file__).resolve().parent
PROTECTED_VALUES = (
    "units/spike_times", "units/spike_times_index", "units/waveforms",
    "units/waveforms_index", "intervals/trials/id",
    "intervals/trials/start_time", "intervals/trials/stop_time",
)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def plain(value):
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, np.ndarray):
        return [plain(x) for x in value.tolist()]
    if isinstance(value, np.generic):
        return plain(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return {"nonfinite": str(value)}
    if isinstance(value, h5py.Reference):
        return "HDF5 object reference; resolved separately"
    if isinstance(value, (list, tuple)):
        return [plain(x) for x in value]
    return value


def meta_read(handle, name):
    if name not in ALLOWED_ARRAYS | ALLOWED_SCALARS:
        raise ValueError("Metadata value is not allowlisted: " + name)
    if name not in handle:
        return None
    prefix = ""
    for part in name.split("/"):
        prefix = (prefix + "/" + part).lstrip("/")
        if not isinstance(handle.get(prefix, getlink=True), h5py.HardLink):
            raise ValueError("Indirect metadata link")
    item = handle[name]
    if not isinstance(item, h5py.Dataset) or item.is_virtual or item.external:
        raise ValueError("Indirect metadata dataset")
    # A hard link can give a response/index object an otherwise permitted name.
    # Check object identity before reading the supposedly metadata-only values.
    for protected in PROTECTED_VALUES:
        if protected in handle and item.id == handle[protected].id:
            raise ValueError("Metadata aliases a protected response or schema-only object")
    limit = 4096 if name in ALLOWED_ARRAYS else 8
    if item.size > limit:
        raise ValueError("Metadata dataset is outside bounded schema")
    READS.append(name)
    return item[()]


def describe(handle, name):
    item = handle[name]
    record = {"kind": "dataset" if isinstance(item, h5py.Dataset) else "group",
              "attrs": {str(k): plain(v) for k, v in item.attrs.items()}}
    if isinstance(item, h5py.Dataset):
        record.update(shape=list(item.shape), dtype=str(item.dtype))
    return record


def inspect(path, source):
    if path.is_symlink() or path.stat().st_size != source["bytes"] or digest(path) != source["sha256"]:
        raise ValueError("Source content differs from authenticated manifest")
    first_read = len(READS)
    with h5py.File(path, "r") as f:
        identity = {name: plain(meta_read(f, name)) for name in sorted(ALLOWED_SCALARS)}
        subject = identity["general/subject/subject_id"]
        if subject != source["subject_id"]:
            raise ValueError("Subject identifier mismatch")
        unit_ids = np.asarray(meta_read(f, "units/id"))
        contacts = np.asarray(meta_read(f, "units/electrodes"))
        if unit_ids.ndim != 1 or unit_ids.dtype.kind not in "iu" or contacts.shape != unit_ids.shape or contacts.dtype.kind not in "iu":
            raise ValueError("Non-single-contact unit schema needs explicit review")
        if "units/electrodes_index" in f:
            raise ValueError("Ragged contact assignment needs explicit review")
        if len(set(unit_ids.tolist())) != len(unit_ids):
            raise ValueError("Duplicate unit identifiers")
        table = f["general/extracellular_ephys/electrodes"]
        if f[f["units/electrodes"].attrs["table"]].name != table.name:
            raise ValueError("Unit contact reference points outside the electrode table")
        locations = plain(meta_read(f, "general/extracellular_ephys/electrodes/location"))
        refs = meta_read(f, "general/extracellular_ephys/electrodes/group")
        if np.any(contacts < 0) or np.any(contacts >= len(locations)) or len(refs) != len(locations):
            raise ValueError("Invalid electrode-row mapping")
        quality = plain(meta_read(f, "units/quality"))
        if not isinstance(quality, list) or len(quality) != len(unit_ids):
            raise ValueError("Missing per-unit source quality labels")
        assignments = []
        for uid, contact, q in zip(unit_ids, contacts, quality):
            group = f[refs[int(contact)]]
            assignments.append({"unit_id": int(uid), "electrode_row": int(contact),
                                "location_literal": locations[int(contact)],
                                "group_location": plain(group.attrs.get("location")),
                                "quality_literal": q})
        coordinate_support = {}
        for axis in ("x", "y", "z"):
            values = np.asarray(meta_read(f, "general/extracellular_ephys/electrodes/" + axis))
            if values.dtype.kind not in "fiu" or values.shape != (len(locations),):
                raise ValueError("Unexpected coordinate metadata")
            finite = values[np.isfinite(values)]
            coordinate_support[axis] = {"shape": list(values.shape), "finite": int(np.isfinite(values).sum()),
                                        "total": int(values.size),
                                        "unique_finite_values": plain(np.unique(finite)),
                                        "physical_unit_conversion_applied": False,
                                        "descriptor": describe(f, "general/extracellular_ephys/electrodes/" + axis)}
        schema = {name: describe(f, name) for name in (
            "units", "units/spike_times", "units/spike_times_index",
            "intervals/trials", "intervals/trials/id", "intervals/trials/start_time",
            "intervals/trials/stop_time")}
        if "units/obs_intervals" in f:
            schema["units/obs_intervals"] = describe(f, "units/obs_intervals")
        relevant_objects = []
        def visit(name, item):
            if any(word in name.lower() for word in ("interval", "duration", "valid", "recording", "observation", "rate", "timestamp")):
                relevant_objects.append({"path": name, **describe(f, name)})
        f.visititems(visit)
        signal_containers = {}
        for container in ("acquisition", "processing", "analysis", "scratch"):
            signal_containers[container] = (
                {name: describe(f, container + "/" + name) for name in f[container]}
                if container in f else None
            )
        return {
            "asset_id": source["asset_id"], "path": source["path"], "bytes": source["bytes"],
            "sha256": source["sha256"], "identity": identity,
            "nwb_version": plain(f.attrs.get("nwb_version")), "declared_unit_count": len(unit_ids),
            "source_anatomy_unit_counts": dict(sorted(Counter(x["location_literal"] for x in assignments).items())),
            "source_quality_unit_counts": dict(sorted(Counter(quality).items())),
            "unit_assignments": assignments, "coordinate_support": coordinate_support,
            "schema": schema, "coverage_related_objects": relevant_objects,
            "signal_container_schema": signal_containers,
            "obs_intervals_present": "units/obs_intervals" in f,
            "metadata_value_reads": READS[first_read:],
            "response_array_values_opened": False,
        }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    start = time.monotonic()
    source_path = HERE / "SOURCES.json"
    manifest = json.loads(source_path.read_text())
    sources = manifest["assets"]
    if len(sources) != 26 or sum(x["bytes"] for x in sources) != 455615424:
        raise ValueError("Expected exact complete MGN component")
    records = [inspect(a.raw_root / Path(x["path"]).name, x) for x in sources]
    report = {"schema": "neural099_authenticated_metadata_census_v1",
              "source_manifest_sha256": digest(source_path), "inspector_sha256": digest(Path(__file__)),
              "source_files": len(records), "source_bytes": sum(x["bytes"] for x in records),
              "response_array_values_opened": False, "scientific_qualified": False,
              "records": records, "wall_seconds": time.monotonic() - start,
              "usage": {"user_cpu_seconds": resource.getrusage(resource.RUSAGE_SELF).ru_utime,
                        "system_cpu_seconds": resource.getrusage(resource.RUSAGE_SELF).ru_stime,
                        "max_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                        "max_rss_native_unit": "bytes" if sys.platform == "darwin" else "KiB",
                        "platform": sys.platform},
              "versions": {"numpy": np.__version__, "h5py": h5py.__version__}}
    with a.output.open("x") as h:
        json.dump(report, h, indent=2, allow_nan=False)
        h.write("\n")
    print(json.dumps({"source_files": len(records), "source_bytes": report["source_bytes"],
                      "units": sum(x["declared_unit_count"] for x in records),
                      "files_with_obs_intervals": sum(x["obs_intervals_present"] for x in records),
                      "wall_seconds": report["wall_seconds"]}))


if __name__ == "__main__":
    main()
