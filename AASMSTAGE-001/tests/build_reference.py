"""Third source-only EDF/manual Welch route and fresh shared-sklearn forests.

No oracle code, generated features, prior bank or model receipts are inputs.
Verifier parsing/arithmetic is shared and disclosed; original EDF bytes,
annotation reconstruction, SciPy rFFT periodograms and tree traversal are local.
The explicit --oracle-output is read only after the fresh bank is constructed.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import platform
import stat
import time
import warnings

import numpy as np
import scipy
from scipy.fft import rfft
import sklearn
from sklearn.ensemble import RandomForestClassifier

import metric_contract as q
import proof_of_work as p


def safe_path(path):
    path = Path(path).absolute()
    q.need(not any(x.is_symlink() for x in (path, *path.parents)), "symlink source/evidence path")
    return path


def destinations(source, output, report):
    source = safe_path(source)
    output, report = safe_path(output), safe_path(report)
    q.need(output != report and output not in report.parents and report not in output.parents, "evidence destinations overlap")
    for path in (output, report):
        q.need(not path.exists(), "evidence destination already exists")
        q.need(path != source and source not in path.parents and path not in source.parents, "evidence must be outside source")
        q.need(path.parent.is_dir(), "create a fresh evidence parent directory first")
    return output, report


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def load_inputs(source_dir, method_path):
    source = safe_path(source_dir); method_path = safe_path(method_path)
    q.need(method_path.is_file() and stat.S_ISREG(method_path.stat().st_mode), "method must be a regular file")
    method_bytes = method_path.read_bytes()
    q.need(p.digest(method_bytes) == q.METHOD_SHA, "frozen method digest differs")
    manifest_path = safe_path(source/"source_manifest.json")
    q.need(manifest_path.is_file() and stat.S_ISREG(manifest_path.stat().st_mode), "source manifest must be a regular file")
    manifest_bytes = manifest_path.read_bytes()
    q.need(p.digest(manifest_bytes) == q.SOURCE_SHA, "frozen source manifest digest differs")
    manifest = q.json_loads(manifest_bytes.decode()); method = q.json_loads(method_bytes.decode())
    expected = {x["path"] for x in manifest["files"]}|{"source_manifest.json"}
    q.need(source.is_dir() and {x.name for x in source.iterdir()} == expected, "exact original source inventory required")
    for item in source.iterdir():
        safe_path(item)
        q.need(stat.S_ISREG(item.stat().st_mode), "source contains non-regular file")
    for row in manifest["files"]:
        path = source/row["path"]
        q.need(path.stat().st_size == row["size_bytes"] and file_hash(path) == row["sha256"], "original EDF size/SHA differs")
    return {"source": source, "method": method, "manifest": manifest,
            "method_json": method_bytes.decode(), "manifest_json": manifest_bytes.decode()}


def edf_header(path):
    """Fixed-width EDF header only; no scientific signal values read here."""
    with Path(path).open("rb") as stream:
        fixed = stream.read(256)
        q.need(len(fixed) == 256, "truncated EDF fixed header")
        text = lambda a, b: fixed[a:b].decode("ascii").strip()
        size, n_channels = int(text(184, 192)), int(text(252, 256))
        q.need(size == 256*(n_channels+1) and n_channels > 0, "EDF header size")
        raw = fixed+stream.read(size-256)
        q.need(len(raw) == size, "truncated EDF channel header")
    header = {"version": text(0, 8), "start_date": text(168, 176), "start_time": text(176, 184),
              "header_bytes": size, "reserved": text(192, 236), "n_records": int(text(236, 244)),
              "record_duration_text": text(244, 252), "n_signals": n_channels,
              "header_sha256": p.digest(raw)}
    widths = [("label", 16), ("transducer", 80), ("physical_dimension", 8),
              ("physical_min_text", 8), ("physical_max_text", 8), ("digital_min_text", 8),
              ("digital_max_text", 8), ("prefilter", 80), ("samples_per_record_text", 8), ("reserved", 32)]
    channels = [{"row": i} for i in range(n_channels)]; cursor = 256
    for name, width in widths:
        for i in range(n_channels):
            channels[i][name] = raw[cursor+i*width:cursor+(i+1)*width].decode("ascii").strip()
        cursor += n_channels*width
    samples = [q.integer(c["samples_per_record_text"]) for c in channels]
    q.need(header["n_records"] >= 0 and all(n > 0 for n in samples), "EDF sample layout")
    q.need(Path(path).stat().st_size == size+2*header["n_records"]*sum(samples), "EDF payload size")
    return header, channels


def parse_tals(raw):
    """Packed annotation bytes; preserve original TAL and description indices."""
    annotations, timekeepers = [], []
    tal_index = 0
    for fragment in raw.split(b"\x00"):
        if not fragment:
            continue
        q.need(fragment.endswith(b"\x14"), "annotation TAL requires final delimiter")
        parts = fragment.split(b"\x14")
        q.need(len(parts) >= 2, "malformed annotation TAL")
        clock = parts[0].split(b"\x15")
        q.need(len(clock) in (1, 2), "malformed TAL clock")
        onset = q.number(clock[0].decode("ascii"))
        duration = q.number(clock[1].decode("ascii")) if len(clock) == 2 else 0.0
        q.need(duration >= 0, "negative annotation duration")
        q.need(math.isfinite(onset+duration), "nonfinite annotation end")
        descriptions = [part.decode("utf-8") for part in parts[1:] if part]
        if not descriptions:
            timekeepers.append({"tal_index": tal_index, "onset_s": onset})
        for description in descriptions:
            annotations.append({"annotation_index": len(annotations), "tal_index": tal_index,
                                "onset_s": onset, "duration_s": duration, "description": description})
        tal_index += 1
    q.need(timekeepers == [{"tal_index": 0, "onset_s": 0.0}], "annotation timekeeper precondition")
    q.need(annotations, "no original annotations")
    # MNE's annotation ordering is stable lexicographic onset/duration sorting.
    order = sorted(range(len(annotations)), key=lambda i: (annotations[i]["onset_s"], annotations[i]["duration_s"]))
    q.need(order == list(range(len(annotations))), "original annotation order differs from pinned MNE order")
    return annotations, timekeepers


def annotation_support(original, subject, n_samples, mapping):
    q.need(len(original) >= 3, "at least three annotations required")
    crop_left = original[1]["onset_s"]-1800.0
    crop_right = original[-2]["onset_s"]+1800.0
    q.need(crop_right > crop_left, "invalid annotation-index crop")
    duration = n_samples/100
    annrows, epochs = [], []
    bad = [a for a in original if a["description"].lower().startswith("bad") and a["duration_s"] > 0]
    for a in original:
        left = max(a["onset_s"], crop_left, 0.0)
        right = min(a["onset_s"]+a["duration_s"], crop_right, duration)
        stage = mapping.get(a["description"])
        outside = right < left
        starts = np.array([], float) if outside else np.arange(left, right, 30.0, dtype=float)
        starts = starts[right-starts >= 30-1e-8]
        if not outside:
            q.need(all(abs(v*100-round(v*100)) <= 1e-7 for v in (left, right)), "annotation bounds not sample aligned")
        status = ("outside_crop_or_recording" if outside else "unsupported_stage" if stage is None
                  else "used" if len(starts) else "no_complete_chunk")
        annrows.append({"subject": subject, "recording": 1, **a, "stage_id": stage,
                        "effective_onset_s": None if outside else float(left),
                        "effective_stop_s": None if outside else float(right),
                        "n_complete_chunks": len(starts),
                        "discarded_tail_s": None if outside else float(max(0, right-left-30*len(starts))),
                        "status": status})
        for chunk, start in enumerate(starts):
            q.need(abs(start*100-round(start*100)) <= 1e-7, "chunk not sample aligned")
            sample = int(np.rint(start*100)); end = sample+3000
            reason = ("unsupported_stage" if stage is None else "outside_recording" if sample < 0 or end > n_samples
                      else "overlap_bad_annotation" if any(start < a["onset_s"]+a["duration_s"] and start+30 > a["onset_s"] for a in bad)
                      else "retained")
            epochs.append({"subject": subject, "recording": 1, "annotation_index": a["annotation_index"],
                           "chunk_index": chunk, "onset_s": float(start), "onset_sample": sample,
                           "end_sample_exclusive": end, "n_samples": 3000, "stage_id": stage,
                           "retained": reason == "retained", "drop_reason": reason})
    q.need(len({r["onset_sample"] for r in epochs}) == len(epochs), "duplicate source epoch start")
    mapped = sorted((r for r in epochs if r["stage_id"] is not None), key=lambda r: r["onset_sample"])
    q.need(all(b["onset_sample"] >= a["end_sample_exclusive"] for a, b in zip(mapped, mapped[1:])), "overlapping mapped epochs")
    gaps = overlaps = 0
    for a, b in zip(original, original[1:]):
        delta = b["onset_s"]-(a["onset_s"]+a["duration_s"])
        gaps += int(delta > 1e-9); overlaps += int(delta < -1e-9)
    observed = {"requested_crop_start_s": crop_left, "requested_crop_stop_s": crop_right,
                "effective_crop_start_s": max(crop_left, 0.0), "effective_crop_stop_s": min(crop_right, duration),
                "n_source_annotations": len(original), "annotation_description_counts": dict(Counter(a["description"] for a in original)),
                "n_bad_prefix_annotations": sum(a["description"].lower().startswith("bad") for a in original),
                "n_annotation_gaps": gaps, "n_annotation_overlaps": overlaps,
                "n_candidate_epochs": len(epochs), "n_retained_epochs": sum(r["retained"] for r in epochs),
                "n_dropped_epochs": sum(not r["retained"] for r in epochs),
                "annotation_status_counts": dict(Counter(r["status"] for r in annrows)),
                "epoch_status_counts": dict(Counter(r["drop_reason"] for r in epochs)),
                "n_duplicate_candidate_start_samples": 0}
    return annrows, sorted(epochs, key=lambda r: r["onset_sample"]), observed


def extract_epochs(path, header, channels, rows):
    sizes = [q.integer(c["samples_per_record_text"]) for c in channels]
    layout = np.memmap(path, dtype="<i2", mode="r", offset=header["header_bytes"],
                       shape=(header["n_records"], sum(sizes)))
    output = np.empty((len(rows), 2, 3000), dtype=np.float64)
    for channel in range(2):
        c = channels[channel]; offset = sum(sizes[:channel])
        raw = layout[:, offset:offset+sizes[channel]].reshape(-1)
        digital_min = q.number(c["digital_min_text"]); digital_max = q.number(c["digital_max_text"])
        physical_min = q.number(c["physical_min_text"]); physical_max = q.number(c["physical_max_text"])
        q.need(digital_max > digital_min and physical_max > physical_min, "invalid source calibration")
        slope = (physical_max-physical_min)/(digital_max-digital_min)
        intercept = physical_min-digital_min*slope
        for i, row in enumerate(rows):
            values = raw[row["onset_sample"]:row["end_sample_exclusive"]].astype(np.float64)
            q.need(values.shape == (3000,), "source epoch samples missing")
            output[i, channel] = (values*slope+intercept)*1e-6
    q.need(np.isfinite(output).all(), "nonfinite calibrated source EEG")
    return output


def welch_features(epochs):
    x = np.asarray(epochs, dtype=np.float64)
    q.need(x.ndim == 3 and x.shape[1:] == (2, 3000) and np.isfinite(x).all(), "finite two-channel epochs required")
    w = .54-.46*np.cos(2*np.pi*np.arange(256)/256)
    segments = x[..., :2816].reshape(len(x), 2, 11, 256).copy()
    segments -= segments.mean(axis=-1, keepdims=True)
    segments *= w
    spectral = np.abs(rfft(segments, n=256, axis=-1))**2/(100*np.sum(w*w))
    spectral[..., 1:-1] *= 2
    psd = spectral.mean(axis=2)
    denom = psd[..., 2:77].sum(axis=-1)
    q.need(np.isfinite(denom).all() and np.all(denom > 0), "PSD normalization denominator must be positive")
    normalized = psd/denom[..., None]
    features = np.concatenate([normalized[..., a:b].mean(axis=-1)
                               for a, b in ((2, 12), (12, 22), (22, 30), (30, 40), (40, 77))], axis=1)
    p.validate_features(features, denom)
    return features, denom


def prepare_source(inputs):
    annotations, epochs, observed, features, sums, retained_all = [], [], [], [], [], []
    records = {(r["subject"], r["role"]): r for r in inputs["manifest"]["files"]}
    for subject in range(6):
        psg = inputs["source"]/records[subject, "psg"]["path"]
        hyp = inputs["source"]/records[subject, "hypnogram"]["path"]
        ph, pc = edf_header(psg); hh, hc = edf_header(hyp)
        q.need((ph["start_date"], ph["start_time"]) == (hh["start_date"], hh["start_time"]), "source header clocks differ")
        q.need(ph["version"] == "0" and hh["version"] == "0" and hh["reserved"] == "EDF+C", "source EDF format")
        q.need([c["label"] for c in pc[:2]] == inputs["method"]["epochs"]["channels"], "EEG channel identity")
        record_duration = q.number(ph["record_duration_text"])
        n_samples = ph["n_records"]*q.integer(pc[0]["samples_per_record_text"])
        eeg = []
        for c in pc[:2]:
            q.need(c["physical_dimension"] == "uV" and q.integer(c["samples_per_record_text"])/record_duration == 100, "source EEG units/rate")
            q.need(ph["n_records"]*q.integer(c["samples_per_record_text"]) == n_samples, "source channel support differs")
            eeg.append({**c, "sfreq_hz": 100.0, "n_samples": n_samples})
        q.need(len(hc) == 1 and hc[0]["label"] == "EDF Annotations", "hypnogram annotation channel")
        with hyp.open("rb") as stream:
            stream.seek(hh["header_bytes"])
            original, timekeepers = parse_tals(stream.read())
        ann, ep, support = annotation_support(original, subject, n_samples, inputs["method"]["classes"]["annotation_mapping"])
        retained = [r for r in ep if r["retained"]]
        q.need(retained, "source subject has no retained epochs")
        x = extract_epochs(psg, ph, pc, retained)
        f, d = welch_features(x)
        del x
        annotations.extend(ann); epochs.extend(ep); retained_all.extend(retained)
        features.append(f); sums.append(d)
        observed.append({"subject": subject, "recording": 1, "psg_path": psg.name, "hypnogram_path": hyp.name,
                         "psg_header": ph, "hypnogram_header": hh, "header_start_date_time_match": True,
                         "annotation_orig_time": None, "annotation_timekeepers": timekeepers,
                         "annotation_source_order_equal_mne": True, "first_samp": 0, "sfreq_hz": 100.0,
                         "n_samples": n_samples, "recording_duration_s": n_samples/100,
                         "eeg_channels": eeg, **support})
    return {"keys": np.array([[r[k] for k in ("subject", "recording", "onset_sample")] for r in retained_all], dtype=np.int64),
            "truth": np.array([r["stage_id"] for r in retained_all], dtype=np.int64),
            "features": np.concatenate(features), "psd_sum": np.concatenate(sums),
            "annotations": annotations, "epochs": epochs, "observed": observed}


def tree_probabilities(tree, features):
    x = np.asarray(features, dtype=np.float32)
    nodes = np.zeros(len(x), dtype=np.int64)
    active = np.flatnonzero(tree.children_left[nodes] != -1)
    while len(active):
        current = nodes[active]
        values = x[active, tree.feature[current]].astype(np.float64)
        left = values <= tree.threshold[current]
        nodes[active] = np.where(left, tree.children_left[current], tree.children_right[current])
        active = np.flatnonzero(tree.children_left[nodes] != -1)
    leaf = np.asarray(tree.value[nodes, 0], dtype=float)
    return leaf/leaf.sum(axis=1, keepdims=True)


def fit_source(prepared, method, pilot=False):
    q.need(sklearn.__version__ == "1.8.0", "reference forest backend must be scikit-learn 1.8.0")
    probabilities = np.full((len(prepared["keys"]), 5), np.nan)
    state, fits = {}, []
    for heldout in ([0] if pilot else range(6)):
        test = prepared["keys"][:, 0] == heldout; train = ~test
        model = RandomForestClassifier(**method["classifier"]["parameters"])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model.fit(prepared["features"][train], prepared["truth"][train])
        manual = np.zeros((int(test.sum()), len(model.classes_)))
        for estimator in model.estimators_:
            manual += tree_probabilities(estimator.tree_, prepared["features"][test])
        manual /= len(model.estimators_)
        library = model.predict_proba(prepared["features"][test])
        q.need(np.all(np.abs(manual-library) <= 1e-14), "independent tree traversal mismatch")
        full = np.zeros((int(test.sum()), 5)); full[:, model.classes_.astype(int)-1] = manual
        probabilities[test] = full
        prefix = f"forest_{heldout}_"
        state[prefix+"node_offsets"] = np.cumsum([0]+[e.tree_.node_count for e in model.estimators_])
        for field in ("children_left", "children_right", "feature", "threshold", "value"):
            state[prefix+field] = np.concatenate([getattr(e.tree_, field) for e in model.estimators_])
        state[prefix+"classes"] = model.classes_
        state[prefix+"train_keys"] = prepared["keys"][train]
        state[prefix+"test_keys"] = prepared["keys"][test]
        state[prefix+"tree_seeds"] = np.array([e.random_state for e in model.estimators_], dtype=np.int64)
        fits.append({"heldout_subject": heldout, "n_train": int(train.sum()), "n_test": int(test.sum()),
                     "n_trees": len(model.estimators_), "n_nodes": int(state[prefix+"node_offsets"][-1]),
                     "treewalk_max_abs": float(np.max(np.abs(manual-library))),
                     "warnings": [str(w.message) for w in caught]})
    return probabilities, state, fits


def make_metadata(inputs, prepared, pilot=False):
    return {"status": "resource_pilot" if pilot else "ok", "task_id": "AASMSTAGE-001", "pipeline_id": q.PIPELINE,
            "dataset_id": "sleep-edfx", "dataset_version": "1.0.0", "source_manifest_sha256": q.SOURCE_SHA,
            "method_contract_sha256": q.METHOD_SHA,
            "source_sha256": {x["path"]: x["sha256"] for x in inputs["manifest"]["files"]},
            "method_contract": inputs["method"], "feature_dtype": "float64", "forest_input_dtype": "float32",
            "software_versions": {"Python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "scikit-learn": sklearn.__version__},
            "source_observed": {"n_subjects": 6, "n_source_annotations": len(prepared["annotations"]),
                                "n_candidate_epochs": len(prepared["epochs"]), "n_retained_epochs": len(prepared["keys"]),
                                "n_dropped_epochs": len(prepared["epochs"])-len(prepared["keys"]),
                                "subjects": prepared["observed"]}}


def validate_pilot(output, ref):
    output = Path(output)
    for name, field in (("annotations.csv", "annotations"), ("epochs.csv", "epochs")):
        p.validate_source_table(output/name, ref["payload"][field], ref["method"]["outputs"][name])
    p.validate_feature_output(output/"epoch_features.csv", ref)
    spec = ref["method"]["outputs"]["epoch_predictions.csv"]
    rows = q.table(output/"epoch_predictions.csv", spec["columns"], spec["key"])
    selected = ref["keys"][:, 0] == 0
    keys = [tuple(int(v) for v in row) for row in ref["keys"][selected]]
    q.need(set(rows) == set(keys), "pilot held-out coverage")
    prob = np.array([[q.number(rows[k][field]) for field in q.PROBS] for k in keys])
    q.need(np.all(np.abs(prob-ref["probabilities"][selected]) <= 1e-10+1e-9*np.abs(ref["probabilities"][selected])), "pilot probabilities differ")
    q.need(np.array_equal([q.integer(rows[k]["predicted_stage"]) for k in keys], q.own_predictions(prob)), "pilot argmax")
    q.need(np.array_equal([q.integer(rows[k]["true_stage"]) for k in keys], ref["truth"][selected]), "pilot truth")
    p.validate_metadata(q.read_json(output/"run_metadata.json"), ref["payload"]["metadata"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=Path("/app/data/aasmstage"))
    parser.add_argument("--method-contract", type=Path, default=Path("/app/method_contract.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--oracle-output", type=Path)
    args = parser.parse_args()
    output, report_path = destinations(args.source_dir, args.output, args.report)
    started = time.monotonic()
    report = {"status": "started", "method_contract_sha256": q.METHOD_SHA, "source_manifest_sha256": q.SOURCE_SHA,
              "builder_id": p.BUILDER_ID, "pilot": args.pilot,
              "script_sha256": {f.name: file_hash(f) for f in (Path(__file__), Path(q.__file__), Path(p.__file__))}}
    try:
        inputs = load_inputs(args.source_dir, args.method_contract)
        prepared = prepare_source(inputs)
        probabilities, states, fits = fit_source(prepared, inputs["method"], args.pilot)
        payload = {"builder_id": p.BUILDER_ID, "method_json": inputs["method_json"], "manifest_json": inputs["manifest_json"],
                   "annotations": prepared["annotations"], "epochs": prepared["epochs"],
                   "metadata": make_metadata(inputs, prepared, args.pilot), "provenance": report.copy()}
        ref = {name: prepared[name] for name in ("keys", "truth", "features", "psd_sum")}
        ref.update(probabilities=probabilities, payload=payload)
        p.validate_bank(ref, args.pilot)
        arrays = {"ref_"+name: ref[name] for name in ("keys", "truth", "features", "psd_sum", "probabilities")}
        arrays.update(states)
        with output.open("xb") as stream:
            np.savez_compressed(stream, reference_json=np.array(json.dumps(payload, allow_nan=False)), **arrays)
        rebuilt = p.load_reference(output, args.pilot)
        if args.oracle_output:
            (validate_pilot if args.pilot else p.validate_output_directory)(args.oracle_output, rebuilt)
        report.update(status="passed", n_epochs=len(prepared["keys"]), n_candidates=len(prepared["epochs"]),
                      fits=fits, bank_sha256=file_hash(output), bank_size_bytes=output.stat().st_size,
                      postconstruction_validation=str(args.oracle_output) if args.oracle_output else None)
    except Exception as exc:
        report.update(status="failed", reason=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic()-started
        with report_path.open("x") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
    print(json.dumps(report, allow_nan=False))


if __name__ == "__main__":
    main()
