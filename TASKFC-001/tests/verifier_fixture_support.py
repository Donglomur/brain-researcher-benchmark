"""Small ten-person manufactured reference and seven-file emitter; no sources."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

import proof_of_work as p
import sensitivity_math as m


def json_ready(value):
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, dict): return {key: json_ready(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)): return [json_ready(child) for child in value]
    return value


def manufactured_reference(mode="active"):
    assert mode in ("active", "one_inactive", "all_inactive", "zero_variance")
    participants, cohort, events, source_files = {}, [], [], []
    for i, pid in enumerate(p.PARTICIPANTS):
        n = 60 if mode == "zero_variance" else 60+i
        rng = np.random.default_rng(900 if mode == "zero_variance" else 900+i)
        times = np.arange(n)*1.5+.75
        motion = rng.normal(size=(n, 6))
        onset, duration = np.array([3., 30., 45., 60.]), np.array([5., 6., 3., 4.])
        conditions = np.array(["language", "string", "language", "string"])
        design = m.build_design(times, onset, duration, conditions, np.ones(4), motion,
                                high_pass=.01, oversampling=50, min_onset=-24.)
        raw = rng.normal(size=(n, 2))+100.
        if mode == "one_inactive" and i == 0: raw[:, 0] = .1
        if mode == "all_inactive": raw[:] = .1
        x0, x1 = design["nuisance_design"], design["full_design"]
        fits = [m.fit_residuals(raw, matrix) for matrix in (x0, x1)]
        residuals = np.stack([fit["residuals"] for fit in fits], axis=1)
        support = m.source_support(raw, residuals)
        model_records = []
        for k, model in enumerate(m.MODELS):
            fit = fits[k]
            model_records.append(dict(model_id=model,
                column_ids=design["nuisance_columns" if k == 0 else "full_columns"],
                rank=fit["design_rank"], residual_df=fit["residual_df"],
                singular_values=fit["singular_values"].tolist(), rank_cutoff=fit["rank_cutoff"],
                roi_support=[dict(roi_id=roi, raw_sample_sd=float(support["raw_sample_sd"][j]),
                    residual_centered_l2=float(support["residual_centered_l2"][k, j]),
                    activity_threshold=float(support["activity_threshold"][j]),
                    active=bool(support["active"][k, j])) for j, roi in enumerate(m.ROIS)]))
        header = dict(shape=[3, 4, 5, n], selected_affine=np.diag([4., 4., 4., 1.]).tolist(),
                      storage_dtype="<f4", spatial_units="mm", temporal_units="sec", zooms=[4., 4., 4., 1.5],
                      raw_toffset=0., raw_scl_slope=1., raw_scl_inter=0., effective_slope=1., effective_intercept=0.)
        participants[pid] = dict(frame_index=np.arange(n), frame_times=times, raw=raw,
            designs={m.MODELS[0]: x0, m.MODELS[1]: x1},
            design_columns={m.MODELS[0]: design["nuisance_columns"], m.MODELS[1]: design["full_columns"]},
            residuals=residuals, active=support["active"],
            source_observed=dict(header=header, event_column_names=["onset", "duration", "trial_type"],
                                 confound_column_names=["RotX", "RotY", "RotZ", "X", "Y", "Z"]),
            analysis_observed=dict(models=model_records))
        row = dict(subject=pid, n_frames=n, operational_TR_s=1.5, operational_frame_origin_s=.75,
                   left_n_voxels=2, right_n_voxels=3,
                   left_support_sha256=hashlib.sha256(b"TASKFC_support_v2\n"+np.array([1, 2], dtype="<i8").tobytes()).hexdigest(),
                   right_support_sha256=hashlib.sha256(b"TASKFC_support_v2\n"+np.array([3, 4, 5], dtype="<i8").tobytes()).hexdigest())
        for role, suffix in (("bold", "bold.nii.gz"), ("events", "events.tsv"), ("confounds", "motion.tsv")):
            path = f"{pid}/{suffix}"
            row[role+"_path"] = path
            source_files.append(dict(path=path, role=role, participant_id=pid, size_bytes=123,
                                     sha256=hashlib.sha256(path.encode()).hexdigest()))
        cohort.append(row)
        for e, (start, length, condition) in enumerate(zip(onset, duration, conditions)):
            events.append(dict(subject=pid, source_event_index=e, trial_type=str(condition),
                               onset_token=str(start), duration_token=str(length), modulation_token="",
                               onset_s=float(start), duration_s=float(length), modulation=1.))
    for i in range(18):
        path = f"provenance/doc-{i:02}.txt"
        source_files.append(dict(path=path, role="provenance", participant_id=None,
                                 size_bytes=30, sha256=hashlib.sha256(path.encode()).hexdigest()))
    return dict(participant_ids=list(p.PARTICIPANTS), participants=participants, cohort=cohort,
                events=events, source_files=source_files,
                pins=dict(source_manifest_sha256="0"*64, method_sha256="1"*64, output_schema_sha256="2"*64))


def canonical_arrays(reference):
    columns = p.union_columns(reference)
    identifiers, indices, times, raw, residuals, designs = [], [], [], [], [], []
    included = np.zeros((10, 2, len(columns)), bool)
    for s, pid in enumerate(p.PARTICIPANTS):
        part = reference["participants"][pid]
        n = len(part["raw"])
        identifiers.extend([pid]*n); indices.extend(range(n)); times.extend(part["frame_times"])
        raw.append(part["raw"]); residuals.append(part["residuals"])
        full = np.zeros((n, len(columns)))
        full[:, [columns.index(name) for name in part["design_columns"][m.MODELS[1]]]] = part["designs"][m.MODELS[1]]
        designs.append(full)
        for k, model in enumerate(m.MODELS):
            included[s, k] = [name in part["design_columns"][model] for name in columns]
    return dict(participant_ids=np.array(p.PARTICIPANTS), roi_ids=np.array(m.ROIS), model_ids=np.array(m.MODELS),
                design_column_ids=np.array(columns), frame_participant_id=np.array(identifiers),
                source_frame_index=np.array(indices), frame_time_s=np.array(times), roi_signals=np.concatenate(raw),
                design_values=np.concatenate(designs), design_included=included, residuals=np.concatenate(residuals))


def write_json(path, value):
    path.write_text(json.dumps(json_ready(value), allow_nan=False, indent=2)+"\n")


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows([{key: "" if value is None else value for key, value in row.items()} for row in rows])


def emit(output, reference):
    output = Path(output); output.mkdir()
    data = canonical_arrays(reference)
    np.savez_compressed(output/"model_arrays.npz", **data)
    write_csv(output/"cohort.csv", reference["cohort"])
    write_csv(output/"events.csv", reference["events"])
    derived = m.derive_cohort({pid: part["residuals"] for pid, part in reference["participants"].items()},
                             {pid: part["active"] for pid, part in reference["participants"].items()}, p.PARTICIPANTS)
    write_csv(output/"connectivity.csv", list(derived["per_subject"].values()))
    write_json(output/"connectivity_summary.json", dict(schema_version="taskfc-results-v2", status="complete", **derived["summary"]))
    metadata = p.expected_metadata(reference)
    metadata.update(software_versions={"manufactured": "source-free"}, warnings=[])
    write_json(output/"run_metadata.json", metadata)
    (output/"findings.md").write_text("Manufactured arithmetic fixture, not a scientific result.\n")
    return output
