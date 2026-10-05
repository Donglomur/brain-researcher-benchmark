"""Small manufactured mechanics only: never a scientific reference bank."""
import copy
import csv
import json
from pathlib import Path
import numpy as np
import qc_contract as q


def fixture_reference(frames=12, rois=4, constant=False):
    method_path = Path(__file__).parents[1] / "environment" / "method_contract.json"
    method = json.loads(method_path.read_text())
    rng = np.random.default_rng(391)
    x = rng.normal(size=(3, frames, rois))
    if constant:
        x[:] = 1
    masks = np.ones((3, frames), dtype=bool)
    masks[:, ::4] = False
    ref = dict(run_subject=np.array(["toy"]*3), run_session=np.array(["func01", "func02", "func03"]),
               roi_ids=np.arange(1, rois+1), frame_indices=np.tile(np.arange(frames), (3, 1)),
               tmask=masks, roi_means=x, roi_source_peak_abs=np.full((3, rois), 100.0),
               voxel_offsets=np.arange(rois+1), voxel_ijk=np.array([[i, 0, 0] for i in range(rois)]))
    ref["geometry"] = [dict(roi_id=i+1, geometry_id="released_canonical_333", mni_x_mm=i, mni_y_mm=0,
                            mni_z_mm=0, world_x_mm=float(i), world_y_mm=0., world_z_mm=0.,
                            radius_mm=5., n_voxels=1, boundary_min_abs_mm2=.25) for i in range(rois)]
    ref["method"] = method
    metadata = dict(status="ok", pipeline_id=q.PIPELINE, method_contract=copy.deepcopy(method),
                    method_contract_sha256="toy-method", source_manifest_sha256="toy-source",
                    source_files=[dict(subject_id="toy", session_id=s, role=role, path=f"{s}.{role}",
                                       size_bytes=123, sha256="a"*64, published_md5="b"*32,
                                       git_blob_sha1="c"*40, version_id="version", etag="etag")
                                  for s in ref["run_session"] for role in ("bold", "tmask")],
                    source_observed=dict(n_subjects=1, n_runs=3, n_original_files=6,
                                         headers=[dict(subject_id="toy", session_id=s,
                                                       **{k: v for k, v in method["source"]["expected_header"].items()
                                                          if k != "description_required_suffix"},
                                                       description="original header") for s in ref["run_session"]],
                                         timing_policy=copy.deepcopy(method["timing"]), original_files_modified=False),
                    software_versions={"python": "fixture", "numpy": np.__version__, "nibabel": "not_used"})
    ref["metadata"] = metadata
    return ref


def emit(directory, ref, means=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    arrays = {k: ref[k].copy() for k in ("run_subject", "run_session", "roi_ids", "frame_indices", "tmask",
              "roi_means", "roi_source_peak_abs", "voxel_offsets", "voxel_ijk")}
    if means is not None:
        arrays["roi_means"] = np.asarray(means).copy()
    derived = q.derive(arrays)
    arrays.update(arm_names=np.array(q.ARMS), **{k: derived[k] for k in
                  ("common_roi", "edge_roi_ids", "edge_valid", "raw_r", "fisher_z")})
    np.savez_compressed(directory / "connectivity_arrays.npz", **arrays)
    tables = {name: derived[name] for name in ("session_qc", "roi_status", "session_pairs", "reliability")}
    tables["roi_geometry"] = ref["geometry"]
    for name, rows in tables.items():
        with (directory / f"{name}.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=ref["method"]["outputs"][f"{name}.csv"]["columns"])
            writer.writeheader()
            writer.writerows([{k: (int(v) if isinstance(v, bool) else v) for k, v in r.items()} for r in rows])
    metadata = copy.deepcopy(ref["metadata"])
    keys = ref["method"]["outputs"]["run_metadata.json"]["analysis_observed"]["required_fields"]
    metadata["analysis_observed"] = {k: derived["stats"][k] for k in keys}
    (directory / "run_metadata.json").write_text(json.dumps(metadata, allow_nan=False))
    (directory / "reliability_stats.json").write_text(json.dumps(derived["stats"], allow_nan=False))
    (directory / "findings.md").write_text("Manufactured parser fixture, not a scientific result.\n")
    return arrays, derived
