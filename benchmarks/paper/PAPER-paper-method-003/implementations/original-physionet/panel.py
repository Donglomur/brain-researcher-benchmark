"""Original REVE PhysioNet-MI panel: official EDFs to bounded, labelled operator shards.

This is an explicit implementation of the released 06a7059 preprocessing profile,
not a claim that its direct-200-Hz recipe generated the historical Table 12 score.
All data, annotations, derived arrays and predictions belong outside public Git.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from types import ModuleType
import urllib.request

SOURCE_COMMIT = "06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7"
DATA_URL = "https://physionet.org/files/eegmmidb/1.0.0/"
RUNS = (4, 6, 8, 10, 12, 14)
PROFILE = "released-06a7059-direct200"
CHANNELS = ("Fc5. Fc3. Fc1. Fcz. Fc2. Fc4. Fc6. C5.. C3.. C1.. Cz.. C2.. C4.. C6.. "
            "Cp5. Cp3. Cp1. Cpz. Cp2. Cp4. Cp6. Fp1. Fpz. Fp2. Af7. Af3. Afz. Af4. Af8. "
            "F7.. F5.. F3.. F1.. Fz.. F2.. F4.. F6.. F8.. Ft7. Ft8. T7.. T8.. T9.. T10. "
            "Tp7. Tp8. P7.. P5.. P3.. P1.. Pz.. P2.. P4.. P6.. P8.. Po7. Po3. Poz. Po4. "
            "Po8. O1.. Oz.. O2.. Iz..").split()


def need(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def split_for(participant):
    need(type(participant) is int and 1 <= participant <= 109, "original participant ID required")
    return "train" if participant <= 70 else "val" if participant <= 89 else "test"


def roster():
    return [{"participant": p, "run": run, "split": split_for(p),
             "path": f"S{p:03d}/S{p:03d}R{run:02d}.edf"}
            for p in range(1, 110) for run in RUNS]


def checksums(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        value, name = line.split(maxsplit=1)
        name = name.lstrip("*")
        need(re.fullmatch(r"[0-9a-f]{64}", value), "invalid official checksum")
        need(name not in result, "duplicate checksum path")
        result[name] = value
    need(all(row["path"] in result for row in roster()), "official checksums omit original runs")
    return result


def download(url, destination, expected_hash=None, max_bytes=16 * 1024**2):
    destination = Path(destination)
    if destination.exists():
        need(expected_hash is not None and digest(destination) == expected_hash, "existing file fails official checksum")
        return destination.stat().st_size
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    count = 0
    try:
        with urllib.request.urlopen(url, timeout=60) as response, partial.open("xb") as handle:
            declared = response.headers.get("Content-Length")
            if declared is not None:
                need(int(declared) <= max_bytes, "download exceeds individual cap")
            while True:
                chunk = response.read(min(1024 * 1024, max_bytes + 1 - count))
                if not chunk:
                    break
                count += len(chunk)
                need(count <= max_bytes, "download exceeded individual cap")
                handle.write(chunk)
        if expected_hash:
            need(digest(partial) == expected_hash, "official SHA256 mismatch")
        partial.replace(destination)
        return count
    finally:
        if partial.exists():
            partial.unlink()


def acquire(root, *, workers=4, max_bytes=4 * 1024**3):
    """Acquire exactly 654 selected EDFs; caller reserves cumulative disk first."""
    need(1 <= workers <= 4, "at most four bounded download workers")
    root = Path(root)
    checksum_file = root / "SHA256SUMS.txt"
    if not checksum_file.exists():
        download(DATA_URL + "SHA256SUMS.txt", checksum_file, max_bytes=1024**2)
    sums = checksums(checksum_file)
    # Fixed worst-case bound, checked before any EDF transfer. Current EDFs are
    # about 2.6 MB; 4 MiB per recording covers the complete original panel.
    per_file_cap = 4 * 1024**2
    need(len(roster()) * per_file_cap + checksum_file.stat().st_size <= max_bytes,
         "max_bytes too small for fixed pre-transfer panel bound")
    def fetch(row):
        size = download(DATA_URL + row["path"], root / row["path"], sums[row["path"]], per_file_cap)
        return {**row, "bytes": size, "sha256": sums[row["path"]]}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        records = list(pool.map(fetch, roster()))
    result = {"schema": "reve-official-edf-acquisition-v1", "dataset": "eegmmidb/1.0.0",
              "source_url": DATA_URL, "checksum_manifest_sha256": digest(checksum_file),
              "files": records, "bytes": sum(x["bytes"] for x in records),
              "all_109_participants": True, "runs_per_participant": list(RUNS)}
    target = root / "acquisition.json"
    if target.exists():
        need(json.loads(target.read_text()) == result, "existing acquisition receipt differs")
    else:
        save(target, result)
    return result


def inspect(root):
    """Validate every source file and literal EDF header without reading target values."""
    root = Path(root)
    sums = checksums(root / "SHA256SUMS.txt")
    records = []
    for row in roster():
        path = root / row["path"]
        need(path.is_file() and digest(path) == sums[row["path"]], "missing/corrupt EDF: " + row["path"])
        with path.open("rb") as handle:
            header = handle.read(256)
            channels = int(header[252:256])
            details = handle.read(channels * 256)
        labels = [details[i * 16:(i + 1) * 16].decode("ascii").strip() for i in range(channels)]
        need(all(c in labels for c in CHANNELS), "source EEG channel missing")
        duration = float(header[244:252]); n_records = int(header[236:244])
        offset = 216 * channels
        samples = [int(details[offset + 8*i:offset + 8*(i+1)]) for i in range(channels)]
        rates = {samples[labels.index(c)] / duration for c in CHANNELS}
        need(len(rates) == 1, "mixed EEG sampling rates")
        records.append({**row, "sha256": sums[row["path"]], "bytes": path.stat().st_size,
                        "source_hz": rates.pop(), "duration_s": n_records * duration})
    return {"schema": "reve-edf-inspection-v1", "records": records,
            "source_identity": identity(records), "participant_count": 109, "recording_count": 654}


def prepare(root, output, *, profile=PROFILE):
    """Process one original recording at a time; never silently omit a participant/run.

    All annotations/targets remain under operator/. Inputs contain signals and
    label-free event IDs only. This directory separation is not an OS sandbox.
    """
    need(profile == PROFILE, "historical 128-Hz recipe has not been established")
    import mne
    import numpy as np
    import scipy
    root, output = Path(root), Path(output)
    need(not output.exists(), "fresh preparation directory required")
    source = inspect(root)
    output.mkdir(parents=True)
    (output / "operator").mkdir(mode=0o700)
    (output / "inputs").mkdir()
    records, targets, drops = [], [], []
    for rec in source["records"]:
        raw = mne.io.read_raw_edf(root / rec["path"], preload=True, verbose="ERROR")
        raw.pick(CHANNELS)
        need(raw.ch_names == CHANNELS, "ordered source channels must be preserved")
        need(not raw.info["bads"], "bad channels require authenticated interpolation geometry")
        raw.set_eeg_reference(ref_channels="average", verbose="ERROR")
        raw.filter(l_freq=0.3, h_freq=None, verbose="ERROR")
        raw.notch_filter(60, verbose="ERROR")
        raw.resample(200, verbose="ERROR")
        events, event_dict = mne.events_from_annotations(raw, verbose="ERROR")
        need(event_dict == {"T0": 1, "T1": 2, "T2": 3}, "original annotation ontology required")
        epochs = mne.Epochs(raw, events, event_dict, tmin=0, tmax=4.0-1/200,
                            baseline=None, preload=True, verbose="ERROR")
        data = epochs.get_data(units="uV", copy=True)
        keep = epochs.events[:, 2] != 1
        selected = data[keep, :, -800:]
        need(selected.ndim == 3 and selected.shape[1:] == (64, 800) and np.isfinite(selected).all(),
             "complete finite 64 x 800 epoch required")
        event_ids = []
        for local_index, source_index in enumerate(epochs.selection):
            code = int(epochs.events[local_index, 2])
            if code == 1:
                continue
            # IDs contain source identity and temporal event index, never class.
            event_id = f"S{rec['participant']:03d}R{rec['run']:02d}-event{int(source_index):03d}"
            event_ids.append(event_id)
            targets.append({"event_id": event_id, "participant": rec["participant"], "run": rec["run"],
                            "split": rec["split"], "label": code - 2 if rec["run"] in (4, 8, 12) else code,
                            "onset_sample_200hz": int(epochs.events[local_index, 0])})
        dropped = [{"annotation_index": i, "reason": list(reason), "event_code": int(events[i, 2])}
                   for i, reason in enumerate(epochs.drop_log) if reason]
        drops.append({"source": rec["path"], "annotations": len(events), "kept_imagery": len(event_ids), "drops": dropped})
        name = f"S{rec['participant']:03d}R{rec['run']:02d}.npy"
        np.save(output / "inputs" / name, selected, allow_pickle=False)
        records.append({"participant": rec["participant"], "run": rec["run"], "split": rec["split"],
                        "signal": name, "sha256": digest(output / "inputs" / name),
                        "shape": list(selected.shape), "event_ids": event_ids})
        del raw, epochs, data, selected
        if len(records) % 60 == 0:
            print(json.dumps({"prepared_recordings": len(records), "total_recordings": 654}), file=sys.stderr, flush=True)
    counts = {split: sum(r["shape"][0] for r in records if r["split"] == split) for split in ("train", "val", "test")}
    panel = {"schema": "reve-original-physionet-inputs-v1", "source_commit": SOURCE_COMMIT,
             "source_identity": source["source_identity"], "profile": profile,
             "historical_recipe_verified": False, "units": "uV", "dtype": "float64", "sampling_hz": 200,
             "channels": CHANNELS, "records": records, "counts": counts, "targets_identity": identity(targets),
             "normalization": "none; apply exact frozen author loader normalization in predictor",
             "published_epoch_count": 9837, "observed_epoch_count": sum(counts.values()),
             "published_epoch_count_matches": sum(counts.values()) == 9837,
             "runtime": {"mne": mne.__version__, "numpy": np.__version__, "scipy": scipy.__version__}}
    panel["panel_identity"] = identity(panel)
    save(output / "inputs" / "panel.json", panel)
    save(output / "operator" / "targets.json", {"panel_identity": panel["panel_identity"], "targets": targets})
    save(output / "operator" / "source-inspection.json", source)
    save(output / "operator" / "epoch-accounting.json", drops)
    return {k: v for k, v in panel.items() if k != "records"}


def load_panel(path):
    path = Path(path)
    panel = json.loads(path.read_text())
    stored = panel.pop("panel_identity")
    need(identity(panel) == stored, "panel manifest identity mismatch")
    panel["panel_identity"] = stored
    need(panel.get("schema") == "reve-original-physionet-inputs-v1" and panel.get("source_commit") == SOURCE_COMMIT,
         "known source schema/commit required")
    need(panel.get("units") == "uV" and panel.get("dtype") == "float64" and panel.get("sampling_hz") == 200
         and panel.get("channels") == CHANNELS, "exact physical input contract required")
    need(panel["profile"] == PROFILE and len(panel["records"]) == 654, "full original profile required")
    need([(r["participant"], r["run"], r["split"]) for r in panel["records"]] ==
         [(r["participant"], r["run"], r["split"]) for r in roster()], "original participant/run/split roster required")
    all_ids = []
    counts = {split: 0 for split in ("train", "val", "test")}
    for rec in panel["records"]:
        need(rec["signal"] == f"S{rec['participant']:03d}R{rec['run']:02d}.npy", "invalid shard path")
        shape = rec["shape"]
        need(isinstance(shape, list) and len(shape) == 3 and type(shape[0]) is int and shape[0] > 0
             and shape[1:] == [64, 800], "invalid shard shape")
        need(len(rec["event_ids"]) == shape[0] and all(isinstance(x, str) for x in rec["event_ids"]),
             "invalid event row mapping")
        all_ids.extend(rec["event_ids"]); counts[rec["split"]] += shape[0]
    need(len(all_ids) == len(set(all_ids)), "duplicate event IDs")
    need(panel["counts"] == counts and panel["observed_epoch_count"] == sum(counts.values())
         and panel["published_epoch_count"] == 9837
         and panel["published_epoch_count_matches"] == (sum(counts.values()) == 9837), "epoch census differs")
    return panel


def predict(panel_path, predictor_path, output, *, checkpoint, checkpoint_sha256, adapter_sha256, split="test", batch_size=16):
    """Run a frozen explicit adapter, given only signals + channel names + fixed geometry.

    Adapter exports load_predictor(checkpoint) -> object.predict(signals_uv,
    channel_names) yielding finite Nx4 logits. It owns documented normalization
    and exact author geometry; this API never fabricates a classifier head.
    """
    import numpy as np
    need(split in ("train", "val", "test") and 1 <= batch_size <= 64, "bounded valid inference batch")
    panel = load_panel(panel_path)
    need(digest(checkpoint) == checkpoint_sha256, "frozen checkpoint digest mismatch")
    predictor_path = Path(predictor_path).resolve()
    adapter_bytes = predictor_path.read_bytes()
    need(hashlib.sha256(adapter_bytes).hexdigest() == adapter_sha256, "frozen predictor source digest mismatch")
    module = ModuleType("reve_frozen_predictor")
    module.__file__ = str(predictor_path)
    exec(compile(adapter_bytes, str(predictor_path), "exec"), module.__dict__)
    predictor = module.load_predictor(str(Path(checkpoint).resolve()))
    rows = []
    for rec in panel["records"]:
        if rec["split"] != split:
            continue
        signal_path = Path(panel_path).parent / rec["signal"]
        need(digest(signal_path) == rec["sha256"], "signal shard identity mismatch")
        signal = np.load(signal_path, allow_pickle=False, mmap_mode="r")
        need(list(signal.shape) == rec["shape"] and len(rec["event_ids"]) == len(signal)
             and signal.dtype == np.dtype("float64"), "shard row mapping/dtype mismatch")
        for start in range(0, len(signal), batch_size):
            batch = np.array(signal[start:start+batch_size], copy=True)
            need(np.isfinite(batch).all(), "nonfinite signal batch")
            scores = np.asarray(predictor.predict(batch, list(panel["channels"])))
            need(scores.shape == (len(batch), 4) and np.isfinite(scores).all(), "predictor must return finite N x 4 logits")
            rows.extend({"event_id": eid, "scores": score.tolist()} for eid, score in zip(rec["event_ids"][start:start+len(batch)], scores))
    result = {"panel_identity": panel["panel_identity"], "split": split, "checkpoint_sha256": checkpoint_sha256,
              "predictor_sha256": adapter_sha256, "predictor_identity": getattr(predictor, "identity", None), "predictions": rows,
              "claim": "frozen checkpoint predictions; historical reproduction requires independent qualification"}
    save(output, result)
    return {k: v for k, v in result.items() if k != "predictions"} | {"rows": len(rows)}



def score(panel_path, targets_path, prediction_path, output, *, author_path=None,
          bootstrap_samples=2000, bootstrap_seed=0):
    """Operator-only scoring: the authentic preparation binds the full target set."""
    metrics_path = Path(__file__).with_name("metrics.py")
    metric_module = ModuleType("reve_original_metrics")
    metric_module.__file__ = str(metrics_path)
    exec(compile(metrics_path.read_bytes(), str(metrics_path), "exec"), metric_module.__dict__)
    score_predictions, compare_predictions = metric_module.score_predictions, metric_module.compare_predictions
    panel = load_panel(panel_path)
    target_doc = json.loads(Path(targets_path).read_text())
    need(target_doc["panel_identity"] == panel["panel_identity"], "target panel mismatch")
    all_targets = target_doc["targets"]
    need(identity(all_targets) == panel["targets_identity"], "target content differs from preparation")
    expected = {eid: (rec["participant"], rec["run"], rec["split"])
                for rec in panel["records"] for eid in rec["event_ids"]}
    need(len(all_targets) == len(expected) and len({t["event_id"] for t in all_targets}) == len(expected),
         "target manifest not complete")
    need(all(expected.get(t["event_id"]) == (t["participant"], t["run"], t["split"]) for t in all_targets),
         "target participant/run/split mapping differs")
    targets = [t for t in all_targets if t["split"] == "test"]
    prediction = json.loads(Path(prediction_path).read_text())
    need(prediction["panel_identity"] == panel["panel_identity"] and prediction["split"] == "test",
         "prediction must be the same complete test panel")
    if author_path is None:
        result = score_predictions(prediction["predictions"], targets)
    else:
        author = json.loads(Path(author_path).read_text())
        need(author["split"] == "test", "author must use the original test panel")
        result = compare_predictions(prediction["predictions"], author["predictions"], targets,
                                     panel_identity=panel["panel_identity"],
                                     candidate_panel_identity=prediction["panel_identity"],
                                     author_panel_identity=author["panel_identity"],
                                     bootstrap_samples=bootstrap_samples, bootstrap_seed=bootstrap_seed)
        result["author_prediction_file_sha256"] = digest(author_path)
    result["panel_identity"] = panel["panel_identity"]
    result["prediction_file_sha256"] = digest(prediction_path)
    result["target_file_sha256"] = digest(targets_path)
    result["profile"] = panel["profile"]
    save(output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("acquire"); p.add_argument("--root", required=True); p.add_argument("--max-bytes", type=int, default=4*1024**3)
    p = sub.add_parser("inspect"); p.add_argument("--root", required=True); p.add_argument("--output", required=True)
    p = sub.add_parser("prepare"); p.add_argument("--root", required=True); p.add_argument("--output", required=True)
    p = sub.add_parser("predict"); p.add_argument("--panel", required=True); p.add_argument("--adapter", required=True); p.add_argument("--adapter-sha256", required=True); p.add_argument("--checkpoint", required=True); p.add_argument("--checkpoint-sha256", required=True); p.add_argument("--output", required=True); p.add_argument("--split", default="test"); p.add_argument("--batch-size", type=int, default=16)
    p = sub.add_parser("score"); p.add_argument("--panel", required=True); p.add_argument("--targets", required=True); p.add_argument("--predictions", required=True); p.add_argument("--author-predictions"); p.add_argument("--output", required=True); p.add_argument("--bootstrap-samples", type=int, default=2000); p.add_argument("--bootstrap-seed", type=int, default=0)
    args = parser.parse_args()
    if args.command == "acquire":
        result = acquire(args.root, max_bytes=args.max_bytes); result = {k:v for k,v in result.items() if k != "files"}
    elif args.command == "inspect":
        result = inspect(args.root); save(args.output, result); result = {k:v for k,v in result.items() if k != "records"}
    elif args.command == "prepare": result = prepare(args.root, args.output)
    elif args.command == "score": result = score(args.panel, args.targets, args.predictions, args.output, author_path=args.author_predictions, bootstrap_samples=args.bootstrap_samples, bootstrap_seed=args.bootstrap_seed)
    else: result = predict(args.panel, args.adapter, args.output, checkpoint=args.checkpoint, checkpoint_sha256=args.checkpoint_sha256, adapter_sha256=args.adapter_sha256, split=args.split, batch_size=args.batch_size)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
