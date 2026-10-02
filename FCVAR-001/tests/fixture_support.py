"""Manufactured full-schema fixtures; never reads original data or a bank."""
import copy
import csv
import json

import numpy as np

import source_reference as s


def manufactured_reference(*, quantitative=False):
    ids, rois = list(s.IDS), list(s.ROIS)
    people, cohort, source_people, analysis = {}, [], {}, {}
    labels = [f"Manufactured ROI {j}" for j in rois]
    header = dict(shape=[2, 2, 2, 52], selected_affine=np.eye(4).tolist(), storage_dtype="<f4",
                  spatial_units="mm", temporal_units="sec", zooms=[1., 1., 1., 2.], raw_toffset=0.,
                  raw_scl_slope=0., raw_scl_inter=0., effective_slope=1., effective_intercept=0.)
    for index, sid in enumerate(ids):
        clean = np.zeros((52, 48))
        active = np.zeros(48, dtype=bool)
        if quantitative:
            clean[:, :3] = np.random.default_rng(1000+index).normal(size=(52, 3))
            active[:3] = True
        elif index == 0:
            clean[:, :2] = np.sin(np.arange(52)[:, None] / 3.)
            active[:2] = True
        norms = np.array([s.n.centered_components(clean[:, j])[2] for j in range(48)])
        p = dict(n_frames=52, raw=clean.copy(), clean=clean, active=active,
                 geometry_present=np.ones(48, dtype=bool), n_voxels=np.ones(48, dtype=np.int64),
                 support_sha256=np.asarray([f"{j:064x}" for j in rois]),
                 raw_sample_sd=norms / np.sqrt(51), prestandardization_centered_l2=norms,
                 activity_threshold=norms*1e-12, full_clean_centered_l2=norms,
                 cleaning_rank=0, tr_sec=2., site="manufactured")
        people[sid] = p
        n_active = int(active.sum())
        cohort.append(dict(subject=sid, source_order=index, site="manufactured", n_timepoints=52, tr_sec=2.,
                           bold_path=sid+".nii.gz", confounds_path=sid+".tsv", n_global_active_rois=n_active,
                           n_edges=n_active*(n_active-1)//2, status="ok"))
        source_people[sid] = dict(bold_header=copy.deepcopy(header), confound_columns=list(s.n.CONFOUNDS),
                                 selected_confound_columns=list(s.n.CONFOUNDS), excluded_confound_columns=[],
                                 n_confound_rows=52, frame_count=52, site="manufactured", source_participant_token=sid,
                                 operational_TR_s=2., frame_origin_s=0.)
        analysis[sid] = dict(cleaning_rank=0, n_global_active_rois=n_active, n_edges=n_active*(n_active-1)//2)
    metadata = dict(schema_version="fcvar-metadata-v3", task_id="FCVAR-001", status="ok",
                    source_manifest_sha256="a"*64, method_contract_sha256="b"*64, output_schema_sha256="c"*64,
                    source_files=[dict(path="manufactured", role="provenance", participant_id=None, size_bytes=1, sha256="d"*64)],
                    source_observed=dict(atlas_header={**header, "shape": [2, 2, 2], "zooms": [1., 1., 1.]},
                        roi_labels=[dict(roi_id=j, roi_label=label) for j, label in zip(rois, labels)], persons=source_people,
                        phenotype_columns=["id", "site"], slice_timing_columns=["site", "TR"]),
                    analysis_observed=dict(persons=analysis), software_versions={k: "manufactured" for k in ("python", "numpy", "scipy", "nibabel", "nilearn")}, warnings=[])
    return dict(status="complete", participant_ids=ids, roi_ids=rois, roi_labels=labels, persons=people, cohort=cohort, metadata=metadata)


def evidence(reference, kernel, seed=0, *, accepted=None):
    ids = reference["participant_ids"]
    own = {sid: reference["persons"][sid]["clean"] for sid in ids} if accepted is None else accepted
    analyses = [kernel.analyze_subject(own[sid], reference["persons"][sid]["clean"],
                                        reference["persons"][sid]["active"], sid, seed) for sid in ids]
    arrays = dict(participant_ids=np.asarray(ids), roi_ids=np.asarray(reference["roi_ids"]), roi_labels=np.asarray(reference["roi_labels"]),
                  frame_subject=np.asarray([sid for sid in ids for _ in range(reference["persons"][sid]["n_frames"])]),
                  frame_index=np.concatenate([np.arange(reference["persons"][sid]["n_frames"]) for sid in ids]),
                  raw_roi_mean=np.concatenate([reference["persons"][sid]["raw"] for sid in ids]),
                  clean_roi_series=np.concatenate([own[sid] for sid in ids]))
    for field in ("geometry_present", "n_voxels", "support_sha256", "raw_sample_sd", "prestandardization_centered_l2", "activity_threshold", "full_clean_centered_l2"):
        arrays[field] = np.asarray([reference["persons"][sid][field] for sid in ids])
    arrays["roi_active"] = np.asarray([reference["persons"][sid]["active"] for sid in ids])
    keys, phases = [], []
    for result in analyses:
        for w in kernel.WINDOWS:
            block = result["phases"][w].T
            keys.extend((result["subject"], w, i) for i in range(len(block)))
            phases.extend(block)
    arrays.update(phase_subject=np.asarray([k[0] for k in keys]), phase_window=np.asarray([k[1] for k in keys]),
                  frequency_index=np.asarray([k[2] for k in keys]), surrogate_ids=np.arange(50), phase_angles=np.asarray(phases))
    metadata = copy.deepcopy(reference["metadata"]); metadata["seed"] = seed
    return {"cohort.csv": copy.deepcopy(reference["cohort"]), "roi_evidence.npz": arrays,
            "variability.csv": [row for result in analyses for row in result["windows"]],
            "surrogate_statistics.csv": [row for result in analyses for row in result["surrogates"]],
            "dynamics.json": kernel.summarize_subjects(analyses, ids), "run_metadata.json": metadata,
            "findings.md": "Manufactured schema evidence only; no originals or scientific claim.\n"}


def emit(output, files):
    output.mkdir()
    for name, value in files.items():
        path = output / name
        if name.endswith(".npz"): np.savez(path, **value)
        elif name.endswith(".json"): path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")
        elif name.endswith(".csv"):
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(value[0]))
                writer.writeheader(); writer.writerows(value)
        else: path.write_text(value, encoding="utf-8")
