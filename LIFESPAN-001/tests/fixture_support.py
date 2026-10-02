"""Manufactured references and honest source-reference serialization.

The writer performs no numerical inference. The real-source driver calls the
same serialization only AFTER source_reference.reconstruct; no oracle imports.
"""
import copy
import csv
import hashlib
import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path
import tempfile
import shutil

import numpy as np
import io_contract as io_c
import lifespan_statistics as science
import source_reference as source


def json_write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def csv_write(path, rows, fields=None):
    with Path(path).open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def primitive_arrays(ref):
    b, parcels = ref["basis"], ref["parcels"]
    s, t, r = b["roi_timeseries"].shape
    arrays = {k:b[k].copy() for k in ("subject_id", "roi_index", "parcel_status", "edge_roi_index",
              "edge_valid", "raw_r", "fisher_z", "group_valid", "group_features")}
    arrays.update(subject_frame_offsets=np.arange(s+1, dtype=np.int64)*t,
                  frame_index=np.tile(np.arange(t, dtype=np.int64), s),
                  roi_timeseries=b["roi_timeseries"].reshape(s*t, r).copy(),
                  vertex_offsets=np.r_[0, np.cumsum([len(p["vertices"]) for p in parcels])],
                  vertex_index=np.concatenate([p["vertices"] for p in parcels]))
    return arrays


def write_output(ref, output_dir):
    root = io_c.safe_path(output_dir)
    io_c.need(not root.exists(), "fresh output directory required")
    root.mkdir(parents=True, exist_ok=False)
    csv_write(root / "cohort.csv", ref["cohort_rows"])
    csv_write(root / "parcels.csv", ref["parcels"], ("roi_index", "hemisphere", "annotation_id", "label_name", "vertex_count"))
    with (root / "connectome_primitives.npz").open("xb") as stream:
        np.savez_compressed(stream, **primitive_arrays(ref))
    b = ref["basis"]
    labels = b["partition"]["labels"]
    csv_write(root / "roi_partition.csv", [dict(roi_index=int(j), network_id="" if labels is None else str(labels[j]),
              status=b["partition"]["status"]) for j in b["roi_index"]])
    json_write(root / "partition.json", ref["partition_doc"])
    csv_write(root / "connectome_summary.csv", b["summary_rows"])
    json_write(root / "results.json", b["results"])
    json_write(root / "run_metadata.json", ref["metadata"])
    with (root / "findings.md").open("x", encoding="utf-8") as stream:
        stream.write("This source-conditioned descriptive method case uses the declared convenience cohort and one shared-cohort, age-blind partition.\n\n")
        for key in ("overall_connectivity_vs_age", "system_segregation_vs_age"):
            e = b["results"][key]
            stream.write(f"{key}: status={e['status']}; defined={e['n_defined']}/{e['n_expected']}; signed r={e['pearson_r']}; p={e['p']}; conditional Fisher interval={e['ci95']}.\n\n")
        stream.write("The cross-sectional association and plug-in interval do not establish longitudinal ageing or account for uncertainty in the shared partition. Source reconstruction shares NumPy correlation and the pinned sklearn fit; annotation decoding, numerical diagnostics and endpoint tail arithmetic are independently implemented.\n")
    return root


def manufactured(s=5, t=12, r=8, *, mode="ordinary", seed=815):
    rng = np.random.default_rng(seed)
    q = rng.normal(size=(s,t,r)).astype(np.float32)
    if mode == "constant": q[:, :, 0] = np.float32(0.1)
    elif mode == "all_constant": q[:] = 1
    elif mode == "fewer_clusters": q[:] = np.arange(t, dtype=np.float32)[None, :, None]
    age = np.arange(s, dtype=np.float32)+20
    if mode == "constant_age": age[:] = 30
    ids = [f"person-{i:02d}" for i in range(s)]
    basis = science.build_basis(q, age, ids, np.arange(r), expected_subjects=s, expected_rois=r)
    files, rows, parcels = [], [], []
    for i, person in enumerate(ids):
        row = dict(subject_id=person, cohort_index=i, phenotype_row_index=i,
                   age_source=float(age[i]), age_computational=float(age[i]), sex="source-token")
        for side in ("left", "right"):
            name = f"{person}/{side}.gii"
            sha = hashlib.sha256(name.encode()).hexdigest()
            row.update({side+"_path":name, side+"_sha256":sha})
            files.append(dict(path=name, role="surface_timeseries", size_bytes=100, sha256=sha))
        rows.append(row)
    for j in range(r):
        parcels.append(dict(roi_index=j, hemisphere="lh" if j < r//2 else "rh", annotation_id=j+1,
                            label_name=f"source_label_{j}", vertex_count=2,
                            vertices=np.array([2*(j % (r//2)), 2*(j % (r//2))+1], dtype=np.int64)))
    headers = [dict(subject_id=p, **{side+"_"+key:value for side in ("left", "right")
                for key,value in dict(data_array_count=t, values_per_array=r, storage_dtype="float32", intents=[2001]).items()}) for p in ids]
    observed = dict(left_vertices=r, right_vertices=r, left_cortical_parcels=r//2, right_cortical_parcels=r-r//2,
                    header_timestep_literals=["1000.000000"], header_timing_unit=None, documented_tr_seconds=.645,
                    timing_policy="index_order_no_new_temporal_processing", subjects=headers)
    return source.assemble_reference(basis, {}, dict(files=files), rows, parcels, observed)


@contextmanager
def artifact_copy(original, parent=None):
    """One bounded, exact temporary tree, reclaimed even on failed assertions."""
    def regular_tree(root):
        root = io_c.safe_path(root)
        io_c.need(root.is_dir(), "artifact copy source directory")
        total = 0
        for directory, dirs, names in os.walk(root, followlinks=False):
            for name in dirs + names:
                path = Path(directory) / name
                mode = path.lstat().st_mode
                io_c.need(stat.S_ISDIR(mode) or stat.S_ISREG(mode), "artifact copy refuses links/special files")
                if stat.S_ISREG(mode): total += path.stat().st_size
                io_c.need(total <= io_c.LIMIT, "artifact copy size cap")
        for name in io_c.REQUIRED_FILES:
            io_c.need((root / name).is_file(), "artifact copy missing required file")
        return root
    original = regular_tree(original)
    if parent is not None: parent = io_c.safe_path(parent)
    with tempfile.TemporaryDirectory(prefix="lifespan-evidence-", dir=parent) as tmp:
        target = Path(tmp) / "output"
        shutil.copytree(original, target, symlinks=True)
        # Copy symlinks as links, never follow them, then reject even a link
        # introduced by a source race before any mutation helper sees the copy.
        regular_tree(target)
        yield target
