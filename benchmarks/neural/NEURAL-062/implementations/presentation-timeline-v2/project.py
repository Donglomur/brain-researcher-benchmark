"""NEURAL-062 source projection with a cross-table next-presentation boundary.

This additive component reuses the predecessor's native source authentication,
ROI join, feature summaries and behavior preprocessing. It has not processed
authentic data and is not wired into the registered programme.
"""
from math import isfinite
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
LEGACY = HERE.parent / "registered-runtime" / "source" / "private"
sys.path.insert(0, str(LEGACY))
import extract as legacy
import delivery_io as io
import protocol as p
import nwb_source as src
sys.path.insert(0, str(HERE))
from timeline import next_onsets, overlaps_post


def method():
    paths = [HERE / "project.py", HERE / "timeline.py"] + [
        LEGACY / name for name in (
            "extract.py", "nwb_source.py", "protocol.py", "delivery_io.py",
            "cohort_binding.py",
        )
    ]
    return {str(path.relative_to(HERE.parent)): io.read(path, 200000, retain=False)
            for path in paths}


def project(path, record, byte_binding):
    io.need(type(byte_binding) is int and 0 < byte_binding <= 4_000_000_000,
            "Exact bounded future byte binding; larger source needs explicit resource revision")
    binding = {"bytes": byte_binding, "blake2b_512": record["asset"]["file_hash"]}
    roi = {"rois": [{"cell_roi_id": a, "cell_specimen_id": b}
                    for a, b in record["published_rois"]]}
    output = []
    counts = {key: 0 for key in (
        "all_source_image_rows", "omitted", "unknown_context", "not_change_detection",
        "near_next_presentation", "invalid_current_clock",
    )}
    p.static(record)
    with src.opened_source(io.regular(path), binding) as f:
        subject = src.internal(f, "general/subject/subject_id")[()]
        subject = subject.decode() if isinstance(subject, bytes) else str(subject)
        io.need(subject == record["mouse_id"], "Exact NWB mouse")
        tables = src.presentations(f)
        # Establish the complete image/omission boundary before any event filter
        # and before reading neural/behavior samples. IDs remain table-local.
        following = next_onsets(tables)
        ds, ts, cols = src.neural(f, roi)
        run, rt, pupil, et = legacy.behavior(f)
        for table in tables:
            n = len(table["ids"])
            base = "intervals/" + table["group"] + "/"
            blocks = src.internal(f, base + "stimulus_block_name").asstr()[:].tolist()
            changes = src.vector(f, base + "is_change", n, "bif", 200000)
            ends = src.vector(f, base + "stop_time", n, "f", 200000)
            active = src.vector(f, base + "active", n, "b", 200000)
            io.need(len(blocks) == n, "Native presentation block alignment")
            io.need(all(value in (0, 1) for value in table["omitted"]), "Omitted0/1")
            rows = zip(table["ids"], table["starts"], ends, table["image_names"],
                       table["omitted"], blocks, changes)
            for i, (sid, t, end, name, omitted, block, change) in enumerate(rows):
                counts["all_source_image_rows"] += 1
                if "change_detection" not in block:
                    counts["not_change_detection"] += 1
                    continue
                io.need(bool(active[i]) == (record["passive"] == "False"),
                        "Source active/passive agrees with cohort")
                if omitted:
                    counts["omitted"] += 1
                    continue
                io.need(name != "omitted" and 1 <= len(name) <= 512, "Named shown image")
                if not isfinite(change) or change not in (0, 1):
                    counts["unknown_context"] += 1
                    continue
                if not isfinite(end) or not .15 <= end - t <= .35:
                    counts["invalid_current_clock"] += 1
                    continue
                if overlaps_post(float(t), following[(table["group"], int(sid))],
                                 p.WINDOWS["POST"][-1]):
                    counts["near_next_presentation"] += 1
                    continue
                pre = legacy.summaries(ds, ts, cols, float(t), p.WINDOWS["PRE"])
                post = legacy.summaries(ds, ts, cols, float(t), p.WINDOWS["POST"])
                r = [legacy.behavior_mean(run, rt, float(t), a, b)
                     for a, b in ((-.5, -.25), (-.25, 0))]
                e = [legacy.behavior_mean(pupil, et, float(t), a, b)
                     for a, b in ((-.5, -.25), (-.25, 0))]
                cov = [r[0][0], r[1][0], e[0][0], e[1][0],
                       r[0][1], r[1][1], e[0][1], e[1][1]]
                speed = ((r[0][0] + r[1][0]) / 2
                         if all(x[0] is not None for x in r) else None)
                output.append({"presentation_id": int(sid), "group": table["group"],
                               "image_name": name, "context": "CHANGE" if change else "REPEAT",
                               "running_bin": p.running_bin(speed), "covariates": cov,
                               "PRE": pre, "POST": post})
    return {"format": "neural062_projection_v2", "experiment": record["ophys_experiment_id"],
            "mouse": record["mouse_id"], "source": binding,
            "record_sha256": io.pin(io.canonical(record))["sha256"],
            "rows": output, "census": counts, "method": method()}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--cohort", required=True, help="Exact predecessor-pinned cohort JSON")
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--bytes", required=True, type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    cohort = legacy.cohort_binding.load(LEGACY, args.cohort)
    rows = [r for r in cohort["rows"] if r["ophys_experiment_id"] == args.experiment]
    io.need(len(rows) == 1, "Exactly one pinned cohort experiment")
    io.put(args.output, project(args.source, rows[0], args.bytes), 16000000)


if __name__ == "__main__":
    main()
