"""Manufactured data only. Never discovers, mounts, or opens original inputs."""
import csv
import hashlib
import json

import numpy as np

import circular_contract as c


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_write(path, obj):
    path.write_text(json.dumps(obj, allow_nan=False, indent=2) + "\n")


def manufactured_basis(clean=None, active=(True, True)):
    clean = np.asarray(clean if clean is not None else [[1, 1], [0, 1], [-1, 0], [0, 0], [0, 0]], dtype=float)
    n = len(clean)
    labels = np.asarray([*c.TARGETS, *[f"map_{j}" for j in range(2, 39)]])
    header = dict(shape=[4, 4, 4, n], selected_affine=np.eye(4).tolist(), storage_dtype="<f4",
                  spatial_units="mm", temporal_units="sec", zooms=[1., 1., 1., 2.], raw_toffset=0.,
                  raw_scl_slope="NaN", raw_scl_inter="NaN", effective_slope=1., effective_intercept=0.)
    metadata = dict(schema_version="restconn-metadata-v2", status="ok", task_id="RESTCONN-001",
                    method_sha256="a" * 64, output_schema_sha256="b" * 64, source_manifest_sha256="c" * 64,
                    source_files=[dict(path="dummy", role="bold", participant_id=c.SUBJECT, size_bytes=1, sha256="d" * 64)],
                    source_observed=dict(bold_header=header, atlas_header={**header, "shape": [4, 4, 4, 39]}, frame_count=n,
                        confound_columns=["csf", "wm"], selected_confound_columns=["csf", "wm"], excluded_confound_columns=[],
                        n_confound_rows=n, map_labels=[dict(map_id=j, map_label=str(label)) for j, label in enumerate(labels)],
                        target_map_ids=[0, 1], operational_TR_s=2., frame_origin_s=0.),
                    analysis_observed=dict(map_rank=39, confound_rank=2, target_support=[
                        dict(map_id=j, map_label=label, raw_sample_sd=1., residual_centered_l2=1. if active[j] else 0.,
                             activity_threshold=1e-12 * n**.5, active=bool(active[j])) for j, label in enumerate(c.TARGETS)]),
                    software_versions=dict(python="manufactured", numpy="manufactured", scipy="manufactured", nibabel="not_used", nilearn="not_used"), warnings=[])
    return dict(participant_id=c.SUBJECT, frame_indices=np.arange(n), map_ids=np.arange(39), map_labels=labels,
                raw_coefficients=np.arange(n * 39, dtype=float).reshape(n, 39) / 37,
                cleaned_series=clean, target_labels=c.TARGETS, target_map_ids=np.array([0, 1]), active=np.asarray(active, bool), metadata=metadata)


def emit(output, basis, *, cleaned=None):
    output.mkdir()
    cleaned = basis["cleaned_series"] if cleaned is None else np.asarray(cleaned, dtype=float)
    np.savez_compressed(output / "raw_map_coefficients.npz", participant_id=np.asarray(c.SUBJECT),
                        frame_indices=basis["frame_indices"], map_ids=basis["map_ids"], map_labels=basis["map_labels"], raw_coefficients=basis["raw_coefficients"])
    with (output / "timeseries.csv").open("w", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(["frame_index", *c.TARGETS])
        writer.writerows([i, *map(float, row)] for i, row in enumerate(cleaned))
    json_write(output / "connectivity.json", c.circular_evidence(cleaned, basis["active"]))
    json_write(output / "run_metadata.json", basis["metadata"])
    (output / "findings.md").write_text("Manufactured example; no claim is required.\n")


def synthetic_sources(tmp_path, monkeypatch, *, n=64):
    import nibabel as nib
    import source_reference as r
    root = tmp_path / "source"; root.mkdir()
    rng = np.random.default_rng(927)
    atlas = rng.normal(size=(4, 4, 4, 39)).astype(np.float32)
    coefficients = rng.normal(size=(n, 39))
    bold = (atlas.reshape(-1, 39) @ coefficients.T).reshape(4, 4, 4, n).astype(np.float32)
    roles = {"bold.nii.gz": "bold", "confounds.csv": "confounds", "atlas.nii": "atlas_image", "labels.csv": "atlas_labels",
             "ids.txt": "cohort_ids", "phenotype.csv": "phenotype_metadata", "slice.csv": "slice_timing_metadata",
             "provenance/a.txt": "provenance", "provenance/b.txt": "provenance", "provenance/c.txt": "provenance"}
    for name, data in (("bold.nii.gz", bold), ("atlas.nii", atlas)):
        image = nib.Nifti1Image(data, np.diag([2., 2., 2., 1.]))
        image.header.set_xyzt_units("mm", "sec"); image.header.set_zooms([2., 2., 2., 2.])
        nib.save(image, root / name)
    columns = ["constant", "csf", "linearTrend", "wm", "global", "motion-pitch", "motion-roll", "motion-yaw", "motion-x", "motion-y", "motion-z", "gm", *[f"compcor{j}" for j in range(1, 6)]]
    with (root / "confounds.csv").open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t"); writer.writerow(columns); writer.writerows(rng.normal(size=(n, len(columns))))
    labels = [*c.TARGETS, *[f"map_{j}" for j in range(2, 39)]]
    with (root / "labels.csv").open("w", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(["name", "net name", "x", "y", "z"])
        writer.writerows([label, "network", 0, 0, 0] for label in labels)
    (root / "ids.txt").write_text("0010064\n0099999\n")
    (root / "phenotype.csv").write_text("literal,metadata\n0010064,untouched\n")
    (root / "slice.csv").write_text("unused,document\n1,2\n")
    (root / "provenance").mkdir()
    for letter in "abc": (root / f"provenance/{letter}.txt").write_text("Manufactured provenance only.\n")
    rows = [dict(path=name, role=role, participant_id=c.SUBJECT if role in ("bold", "confounds") else None,
                 size_bytes=(root / name).stat().st_size, sha256=digest(root / name)) for name, role in roles.items()]
    json_write(root / "source_manifest.json", dict(participant_ids=[c.SUBJECT], files=rows))
    monkeypatch.setattr(r, "SOURCE_SHA256", digest(root / "source_manifest.json"))
    method = tmp_path / "method.json"; schema = tmp_path / "schema.json"
    json_write(method, dict(source=dict(participant_id=c.SUBJECT, n_frames=n, map_ids=list(range(39)), target_labels=list(c.TARGETS),
                    target_map_ids=[0, 1], source_manifest_sha256=r.SOURCE_SHA256, bold_shape=[4,4,4,n], atlas_shape=[4,4,4,39],
                    original_confound_columns=columns, operational_TR_s=2., operational_origin_s=0.),
                    temporal_cleaning=dict(confound_columns=[col for col in columns if col in r.NUISANCE])))
    json_write(schema, {"status": "manufactured_only"})
    monkeypatch.setattr(r, "METHOD_SHA256", digest(method)); monkeypatch.setattr(r, "SCHEMA_SHA256", digest(schema))
    return root, method, schema
