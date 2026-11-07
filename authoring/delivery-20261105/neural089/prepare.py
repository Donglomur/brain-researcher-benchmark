"""Pinned2025 MEG preparation, target-free query HDF5, train-only normalization.

No downloads/model calls. Full preparation has not been run on empirical data.
The actual retained example was inspected only for schema and clock geometry.
"""
import argparse
import csv
import hashlib
import hmac
import math
from pathlib import Path, PurePosixPath
from io_contract import TASK, MAX_QUERIES, need, strict, read, write

REVISION = "5a7c332b34fc7be329c4df3e527a41f67bfd878f"
PNPL = "33aff3fd70a197a47f73a06cb5d1e6b0e1cbfb9b"
VAL = ["0", "11", "Sherlock1", "2"]
TEST = ["0", "12", "Sherlock1", "2"]
WINDOW = 125


def verify_asset(root, record):
    relative = PurePosixPath(record["path"])
    need(not relative.is_absolute() and ".." not in relative.parts and str(relative) == record["path"], "local asset path")
    path = root / relative
    need(path.resolve() == path and path.is_file() and path.stat().st_size == record["bytes"], "complete ordinary staged asset")
    digest = hashlib.sha256() if "sha256" in record else hashlib.sha1()
    if "git_blob_sha1" in record: digest.update(("blob " + str(record["bytes"]) + "\0").encode())
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""): digest.update(block)
    need(digest.hexdigest() == record.get("sha256", record.get("git_blob_sha1")), "source content pin")
    return path


def parse_events(raw, classes, sample_count):
    rows = csv.DictReader(raw.decode("utf-8").splitlines(), delimiter="\t")
    need(rows.fieldnames is not None and len(set(rows.fieldnames)) == len(rows.fieldnames)
         and {"kind", "segment", "timemeg", "idx"} <= set(rows.fieldnames), "exact required annotation columns")
    selected, source_ids, excluded = [], set(), 0
    for index, row in enumerate(rows):
        need(None not in row and None not in row.values() and row["idx"] not in source_ids, "complete unique source event row")
        source_ids.add(row["idx"])
        if row["kind"] != "phoneme" or row["segment"] in ("sil", "oov_S"):
            excluded += 1; continue
        label = row["segment"].split("_")[0]
        need(label in classes, "unknown target phoneme; no silent run/row skipping")
        onset = float(row["timemeg"])
        need(math.isfinite(onset) and onset >= 0, "finite nonnegative onset")
        first = int(onset * 250)
        need(first + WINDOW <= sample_count, "complete125-sample event window; no padding/truncation")
        selected.append({"row0": index, "source_idx": row["idx"], "start": first, "label": classes.index(label)})
    need(selected, "every selected run must contain eligible phonemes")
    return selected, {"source_rows": len(source_ids), "excluded_non_target_rows": excluded, "target_rows": len(selected)}


def inspect_h5(handle, schema):
    import numpy as np
    need(set(handle) == {"data", "times"}, "expected2025 continuous data/times HDF5")
    data, times = handle["data"], handle["times"]
    need(data.ndim == 2 and data.shape[0] == 306 and data.dtype.kind == "f"
         and data.dtype.itemsize in (4, 8) and times.shape == (data.shape[1],)
         and times.dtype.kind == "f" and times.dtype.itemsize in (4, 8), "real channel-by-time source")
    need(float(handle.attrs["sample_frequency"]) == 250., "exact250Hz")
    need(handle.attrs["channel_names"].split(", ") == schema["channel_names"]
         and handle.attrs["channel_types"].split(", ") == schema["channel_types"], "exact observed channel order/type")
    n = data.shape[1]; need(125 <= n <= 100000000, "bounded full recording extent")
    need(float(times[0]) == 0., "exact zero-origin original2025 clock; reduced-origin adaptation is separate")
    last_time = float(times[-1]); tolerance = np.finfo(times.dtype).eps * max(1., abs(last_time))
    previous = -math.inf
    for start in range(0, n, 65536):
        t = times[start:start + 65536].astype(np.float64)
        expected = np.arange(start, start + len(t), dtype=np.float64) / 250
        need(np.isfinite(t).all() and t[0] > previous and (np.diff(t) > 0).all()
             and np.max(np.abs(t - expected)) <= tolerance, "zero-origin uniform clock within source rounding")
        previous = float(t[-1])
    return n


def training_stats(blocks):
    """Population channel moments over training continuous samples, not queries."""
    import numpy as np
    n, mean, m2 = 0, np.zeros(306), np.zeros(306)
    for block in blocks:
        x = np.asarray(block, dtype=np.float64)
        need(x.ndim == 2 and x.shape[0] == 306 and x.shape[1] > 0 and np.isfinite(x).all(), "finite training-only block")
        count = x.shape[1]; center = x.mean(axis=1); local_m2 = ((x - center[:, None]) ** 2).sum(axis=1)
        delta = center - mean; total = n + count
        mean += delta * (count / total); m2 += local_m2 + delta ** 2 * (n * count / total); n = total
    need(n > 0, "training samples required")
    std = np.sqrt(m2 / n)
    need(np.isfinite(mean).all() and np.isfinite(std).all() and (std > 0).all(), "nonconstant finite training channels")
    return mean, std, n


def normalized_window(data, start, mean, std):
    import numpy as np
    x = np.asarray(data[:, start:start + WINDOW], dtype=np.float64)
    need(x.shape == (306, WINDOW) and np.isfinite(x).all(), "complete finite source window")
    return np.clip((x - mean[:, None]) / std[:, None], -10., 10.).astype(np.float32)


def write_run(destination, source, events, mean, std, key, source_sha256, labeled):
    import h5py
    import numpy as np
    ids = [hmac.new(key, (source_sha256 + ":" + str(row["row0"])).encode(), hashlib.sha256).hexdigest()[:24] for row in events]
    need(len(ids) == len(set(ids)), "opaque ID collision")
    order = sorted(range(len(ids)), key=ids.__getitem__)
    with h5py.File(destination, "x") as out:
        windows = out.create_dataset("windows", shape=(len(events), 306, WINDOW), dtype="<f4", chunks=(1,306,WINDOW))
        out.create_dataset("ids", data=np.asarray([ids[i].encode() for i in order], dtype="S24"))
        if labeled: out.create_dataset("labels", data=np.asarray([events[i]["label"] for i in order], dtype=np.int16))
        out.attrs["schema_version"] = 1; out.attrs["task_id"] = TASK
        out.attrs["sampling_rate_hz"] = 250; out.attrs["units"] = "training_channel_standard_deviations"
        for j, i in enumerate(order): windows[j] = normalized_window(source, events[i]["start"], mean, std)
    destination.chmod(0o444)
    return [{"query_id": ids[i], "label": events[i]["label"], "source_row0": events[i]["row0"]} for i in order]


def build(lock_path, classes_path, channel_path, staged, output, key_path, max_output_bytes):
    import h5py
    import numpy as np
    lock = strict(read(lock_path, 1000000)); classes = strict(read(classes_path, 100000))["classes"]
    schema = strict(read(channel_path, 100000)); rows = lock["runs"]
    need(lock["revision"] == REVISION and lock["pnpl_revision"] == PNPL and lock["edition"] == "2025-phoneme"
         and len(rows) == 90 and len({tuple(r["run_key"]) for r in rows}) == 90
         and len(classes) == len(set(classes)) == 39, "complete frozen2025 manifest/class map")
    for row in rows:
        expected = "validation" if row["run_key"] == VAL else "query" if row["run_key"] == TEST else "train"
        need(row["split"] == expected and row["run_key"][0] == "0", "native single-person run split")
    need(sum(r["split"] == "train" for r in rows) == 88 and sum(r["split"] == "validation" for r in rows) == 1
         and sum(r["split"] == "query" for r in rows) == 1, "88/1/1 complete native partitions")
    need(not output.exists() and 0 < max_output_bytes <= 1000000000000, "fresh explicitly bounded output")
    key = read(key_path, 32); need(len(key) == 32, "private32-byte HMAC key")
    staged = staged.resolve(); loaded = []; total_windows = 0
    for row in rows:
        recording = verify_asset(staged, row["recording"]); annotations = verify_asset(staged, row["events"])
        with h5py.File(recording, "r") as source: count = inspect_h5(source, schema)
        events, accounting = parse_events(read(annotations, 10000000), classes, count)
        total_windows += len(events); need(total_windows <= 2000000, "whole-source window cap; never truncate")
        if row["split"] == "query": need(len(events) <= MAX_QUERIES, "whole-query cap")
        loaded.append((row, recording, events, accounting))
    # An uncompressed upper bound is checked before any preparation output.
    need(total_windows * (306 * WINDOW * 4 + 256) + 10000000 <= max_output_bytes, "complete packet exceeds output budget")
    def blocks():
        for row, recording, _, _ in loaded:
            if row["split"] != "train": continue
            with h5py.File(recording, "r") as source:
                for start in range(0, source["data"].shape[1], 8192): yield source["data"][:, start:start+8192]
    mean, std, samples = training_stats(blocks())
    output.mkdir(mode=0o700); (output/"public").mkdir(); (output/"private").mkdir(mode=0o700)
    descriptors, provenance, targets = [], [], []
    for row, recording, events, accounting in loaded:
        opaque_run = hmac.new(key, ("run:" + row["recording"]["sha256"]).encode(), hashlib.sha256).hexdigest()[:24]
        name = row["split"] + "-" + opaque_run + ".h5"; dest = output/"public"/name
        with h5py.File(recording, "r") as source:
            records = write_run(dest, source["data"], events, mean, std, key,
                                row["recording"]["sha256"], row["split"] != "query")
        digest = hashlib.sha256()
        with dest.open("rb") as stream:
            for b in iter(lambda:stream.read(1048576),b""): digest.update(b)
        descriptors.append({"partition":row["split"],"group_id":opaque_run,"path":name,"windows":len(records),
                            "bytes":dest.stat().st_size,"sha256":digest.hexdigest()})
        provenance.append({"run_key":row["run_key"],"source_sha256":row["recording"]["sha256"],
                           "accounting":accounting,"records":records})
        if row["split"] == "query": targets = [{"query_id":r["query_id"],"label":r["label"]} for r in records]
    panel = {"schema_version":1,"task_id":TASK,"query_ids":[r["query_id"] for r in targets]}
    panel_pin = write(output/"public"/"panel.json",panel)
    target_pin = write(output/"private"/"targets.json",{"schema_version":1,"task_id":TASK,
                         "panel_sha256":panel_pin["sha256"],"targets":targets})
    write(output/"public"/"inputs.json",{"schema_version":1,"task_id":TASK,"runs":descriptors})
    write(output/"private"/"source_rows.json",{"runs":provenance})
    write(output/"private"/"normalization.json",{"training_samples":samples,"mean":mean.tolist(),"population_std":std.tolist(),
                                                    "training_runs":88,"validation_or_query_statistics_used":False})
    actual = sum(f.stat().st_size for f in output.rglob('*') if f.is_file())
    need(actual + 100000 <= max_output_bytes,"actual complete output cap")
    write(output/"private"/"PREPARATION.json",{"status":"prepared_not_empirically_qualified","task_id":TASK,
          "lock_sha256":hashlib.sha256(read(lock_path,1000000)).hexdigest(),"panel":panel_pin,"targets":target_pin,
          "windows":total_windows,"actual_bytes_before_receipt":actual,"models_fit":0,"empirical_scores":0,
          "numpy":np.__version__,"h5py":h5py.__version__})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("lock","classes","channels","staged","output","key"):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--max-output-bytes',type=int,required=True);a=p.parse_args()
    build(a.lock,a.classes,a.channels,a.staged,a.output,a.key,a.max_output_bytes)


if __name__=='__main__':main()
