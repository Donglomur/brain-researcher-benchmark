"""Third source-only reconstruction of MSC sphere primitives.

No oracle code, generated means/FC, prior reference or model receipts are
inputs. Low-level nibabel loading and verifier schema/arithmetic utilities are
shared and disclosed; sphere enumeration and voxel reductions are independent.
Full original execution requires the separately recorded parent gate.
"""
import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import struct
import time

import nibabel as nib
import numpy as np

import proof_of_work as p
import qc_contract as q


def destinations(source, output, report):
    source = Path(source).absolute()
    targets = [Path(output).absolute(), Path(report).absolute()]
    p.require(targets[0] != targets[1], "bank and report destinations must differ")
    for path in [source, *targets]:
        p.require(not any(v.is_symlink() for v in (path, *path.parents)), "symlink ancestor/leaf")
    # Check the original spelling for links before resolving lexical '..'.
    source = source.resolve(strict=False)
    targets = [path.resolve(strict=False) for path in targets]
    p.require(targets[0] != targets[1], "bank and report destinations alias")
    for path in targets:
        p.require(not path.exists() and not os.path.lexists(path), "preserve existing evidence")
        p.require(source != path and source not in path.parents and path not in source.parents,
                  "evidence destination overlaps source directory")
    p.require(targets[0] not in targets[1].parents and targets[1] not in targets[0].parents,
              "nested evidence destinations")
    return targets


def validate_inventory(root, records):
    expected = {"source_manifest.json", *[r["path"] for r in records]}
    expected_dirs = {parent.as_posix() for name in expected for parent in Path(name).parents
                     if parent != Path(".")}
    actual = set()
    actual_dirs = set()
    for folder, dirs, files in os.walk(root, followlinks=False):
        for name in [*dirs, *files]:
            path = Path(folder) / name
            p.require(not path.is_symlink(), "source symlink")
            mode = path.stat().st_mode
            p.require(stat.S_ISREG(mode) or stat.S_ISDIR(mode), "special source file")
            if stat.S_ISREG(mode):
                actual.add(path.relative_to(root).as_posix())
            else:
                actual_dirs.add(path.relative_to(root).as_posix())
    p.require(actual == expected, "missing or unexpected source inventory")
    p.require(actual_dirs == expected_dirs, "missing or unexpected source directories")


def load_inputs(source_dir, method_path):
    root = Path(source_dir).absolute()
    p.require(root.is_dir() and not any(x.is_symlink() for x in (root, *root.parents)), "source root")
    root = root.resolve(strict=False)
    p.require(p.sha256(method_path) == p.METHOD_SHA, "frozen method SHA mismatch")
    manifest_path = root / "source_manifest.json"
    p.require(p.sha256(manifest_path) == p.SOURCE_SHA, "frozen source manifest SHA mismatch")
    method, manifest = p.read_json(method_path), p.read_json(manifest_path)
    records = manifest["files"]
    p.require(len(records) == 42 and len({r["path"] for r in records}) == 42, "source inventory cardinality")
    validate_inventory(root, records)
    run_records, provenance = {}, {}
    for record in records:
        path = root / record["path"]
        p.require(not Path(record["path"]).is_absolute() and ".." not in Path(record["path"]).parts,
                  "unsafe source path")
        p.require(path.stat().st_size == record["size_bytes"], "source byte count")
        digest = hashlib.sha256(); md5 = hashlib.md5()
        with p.regular_file(path).open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block); md5.update(block)
        p.require(digest.hexdigest() == record["sha256"], "source SHA mismatch")
        if "published_md5" in record:
            p.require(md5.hexdigest() == record["published_md5"], "source published MD5 mismatch")
        if record["role"] in ("bold", "tmask"):
            key = record["subject"], record["session"], record["role"]
            p.require(key not in run_records, "duplicate source run")
            run_records[key] = record
        else:
            p.require(record["role"] not in provenance, "duplicate provenance role")
            provenance[record["role"]] = record
    p.require(set(run_records) == {(s, t, r) for s in p.SUBJECTS for t in p.SESSIONS for r in ("bold", "tmask")},
              "incomplete source run set")
    p.require(provenance["atlas_coordinates"]["sha256"] == method["provenance"]["power_integer_coordinate_sha256"] and
              provenance["point_transform"]["sha256"] == method["provenance"]["published_transform_sha256"],
              "coordinate provenance mismatch")
    return dict(root=root, method=method, manifest=manifest, runs=run_records, provenance=provenance)


def inspect_header(path, subject, session, method):
    with gzip.open(p.regular_file(path), "rb") as stream:
        raw = stream.read(352)
    p.require(len(raw) == 352 and struct.unpack_from("<i", raw)[0] == 348, "NIfTI header endian/length")
    image = nib.load(path)
    header = image.header
    qform, qcode = header.get_qform(coded=True)
    sform, scode = header.get_sform(coded=True)
    units = header.get_xyzt_units()
    observed = dict(subject_id=subject, session_id=session, shape=list(image.shape), stored_dtype=header.get_data_dtype().name,
                    byte_order="little", voxel_offset_bytes=int(struct.unpack_from("<f", raw, 108)[0]),
                    spatial_zooms_mm=list(map(float, header.get_zooms()[:3])), xyzt_units_code=int(header["xyzt_units"]),
                    spatial_unit=units[0], temporal_unit=units[1], qform_code=int(qcode),
                    qform=None if qform is None else qform.tolist(), sform_code=int(scode), sform=sform.tolist(),
                    raw_scl_slope=float(struct.unpack_from("<f", raw, 112)[0]),
                    raw_scl_inter=float(struct.unpack_from("<f", raw, 116)[0]),
                    effective_scale=float(image.dataobj.slope), effective_offset=float(image.dataobj.inter),
                    raw_header_tr_seconds=float(header.get_zooms()[3]),
                    description=raw[148:228].split(b"\0",1)[0].decode("ascii"))
    for key, expected in method["source"]["expected_header"].items():
        if key == "description_required_suffix":
            p.require(observed["description"].endswith(expected), "source description suffix")
        else:
            if key in ("sform", "spatial_zooms_mm"):
                expected = np.asarray(expected, dtype=float).tolist()
            p.match(observed[key], expected, key, 1e-9 if key in ("sform", "spatial_zooms_mm") else 0)
    return image, observed


def sphere_geometry(mni, affine, shape, transform, radius=5.):
    mni = np.asarray(mni, dtype=np.float64)
    grid = np.indices(shape, dtype=np.int64).reshape(3, -1).T
    homogeneous = np.column_stack([grid, np.ones(len(grid))])
    world_grid = homogeneous @ np.asarray(affine, dtype=np.float64).T
    mapped = np.column_stack([mni, np.ones(len(mni))]) @ np.asarray(transform, dtype=np.float64).T
    segments, rows, offsets = [], [], [0]
    for i, (original, point) in enumerate(zip(mni, mapped)):
        delta = world_grid[:, :3] - point[:3]
        squared = (delta[:, 0]*delta[:, 0] + delta[:, 1]*delta[:, 1]) + delta[:, 2]*delta[:, 2]
        members = grid[squared <= radius*radius]
        p.require(len(members) > 0, "empty source sphere")
        segments.append(members); offsets.append(offsets[-1] + len(members))
        rows.append(dict(roi_id=i+1, geometry_id="released_canonical_333",
                         mni_x_mm=int(original[0]), mni_y_mm=int(original[1]), mni_z_mm=int(original[2]),
                         world_x_mm=float(point[0]), world_y_mm=float(point[1]), world_z_mm=float(point[2]),
                         radius_mm=float(radius), n_voxels=len(members),
                         boundary_min_abs_mm2=float(np.min(np.abs(squared-radius*radius)))))
    return np.array(offsets, dtype=np.int64), np.concatenate(segments), rows


def source_means(image, offsets, ijk):
    # Read original scaled values once, validate the entire image, not only ROIs.
    values = np.asarray(image.dataobj, dtype=np.float64)
    p.require(values.ndim == 4 and np.isfinite(values).all(), "nonfinite original BOLD values")
    means = np.empty((values.shape[3], len(offsets)-1), dtype=np.float64)
    peaks = np.empty(len(offsets)-1, dtype=np.float64)
    for j, (start, stop) in enumerate(zip(offsets[:-1], offsets[1:])):
        v = ijk[start:stop]
        selected = values[v[:, 0], v[:, 1], v[:, 2], :]
        means[:, j] = np.einsum("vt->t", selected, optimize=False) / len(v)
        peaks[j] = np.max(np.abs(selected))
    p.require(np.isfinite(means).all() and np.isfinite(peaks).all(), "nonfinite sphere reduction")
    return means, peaks


def reconstruct(inputs, pilot=False):
    root, method = inputs["root"], inputs["method"]
    atlas_path = root / inputs["provenance"]["atlas_coordinates"]["path"]
    with atlas_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    p.require(len(rows) == 264, "original atlas row count")
    # Published Nilearn table uses ROI,X,Y,Z; do not re-round its integers.
    roi_ids = [p.integer(r["ROI"]) for r in rows]
    p.require(roi_ids == list(range(1,265)), "original atlas IDs")
    mni = np.array([[p.integer(r[c]) for c in ("X", "Y", "Z")] for r in rows], dtype=np.int64)
    affine = np.asarray(method["source"]["expected_header"]["sform"], dtype=np.float64)
    offsets, ijk, geometry = sphere_geometry(mni, affine, (48,64,48), method["geometry"]["mni_to_world_matrix"])
    run_keys = [(s,t) for s in (p.SUBJECTS[:1] if pilot else p.SUBJECTS) for t in p.SESSIONS]
    means, peaks, masks, headers = [], [], [], []
    images = {}
    # All source header identities are retained even in the first-person pilot.
    # These bounded header reads are separate from the selected BOLD reductions.
    for subject in p.SUBJECTS:
        for session in p.SESSIONS:
            image, observed = inspect_header(root/inputs["runs"][(subject,session,"bold")]["path"], subject, session, method)
            images[(subject,session)] = image
            headers.append(observed)
    for subject, session in run_keys:
        image = images[(subject,session)]
        mask = np.loadtxt(root/inputs["runs"][(subject,session,"tmask")]["path"], dtype=np.float64)
        p.require(mask.shape == (818,) and np.isfinite(mask).all() and np.all((mask==0)|(mask==1)), "source tmask")
        mean, peak = source_means(image, offsets, ijk)
        means.append(mean); peaks.append(peak); masks.append(mask.astype(bool))
    arrays = dict(run_subject=np.array([s for s,t in run_keys]), run_session=np.array([t for s,t in run_keys]),
                  roi_ids=np.arange(1,265,dtype=np.int64), frame_indices=np.tile(np.arange(818), (len(run_keys),1)),
                  tmask=np.array(masks), roi_means=np.array(means), roi_source_peak_abs=np.array(peaks),
                  voxel_offsets=offsets, voxel_ijk=ijk)
    fields = method["outputs"]["run_metadata.json"]["source_files"]["required_fields"]
    source_files = []
    for key in sorted(inputs["runs"]):
        row = dict(inputs["runs"][key], subject_id=key[0], session_id=key[1])
        source_files.append({field: row[field] for field in fields})
    metadata = dict(status="resource_pilot" if pilot else "ok", pipeline_id=q.PIPELINE,
                    method_contract=method, method_contract_sha256=p.METHOD_SHA, source_manifest_sha256=p.SOURCE_SHA,
                    source_files=source_files,
                    source_observed=dict(n_subjects=6, n_runs=18, n_original_files=36, headers=headers,
                                         timing_policy=method["timing"], original_files_modified=False),
                    software_versions=dict(python=platform.python_version(), numpy=np.__version__, nibabel=nib.__version__))
    arrays.update(metadata=metadata, geometry=geometry, method=method)
    return arrays


def write_bank(path, ref, pilot=False):
    payload = {f"ref_{k}": ref[k] for k in p.PRIMITIVES}
    payload.update(bank_schema=np.array("precisfc-resource-pilot-v2" if pilot else p.BANK_SCHEMA),
                   metadata_json=np.array(json.dumps(ref["metadata"], allow_nan=False)),
                   geometry_json=np.array(json.dumps(ref["geometry"], allow_nan=False)))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("xb") as stream:
        np.savez_compressed(stream, **payload)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=Path("/app/data/precisfc"))
    parser.add_argument("--method-contract", type=Path, default=Path("/app/method_contract.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--oracle-output", type=Path)
    args=parser.parse_args()
    output, report = destinations(args.source_dir, args.output, args.report)
    started=time.monotonic()
    inputs=load_inputs(args.source_dir,args.method_contract)
    ref=reconstruct(inputs,args.pilot)
    derived=q.derive(ref)
    result=dict(status="resource_pilot" if args.pilot else "ok", method_contract_sha256=p.METHOD_SHA,
                source_manifest_sha256=p.SOURCE_SHA, n_processed_runs=len(ref["run_subject"]),
                primitive_shape=list(ref["roi_means"].shape), diagnostic_stats=derived["stats"],
                construction="authenticated originals only; nibabel low-level reader; independent native spheres and einsum voxel reduction; verifier arithmetic shared",
                script_sha256={name:p.sha256(Path(__file__).with_name(name)) for name in
                               ("build_reference.py","proof_of_work.py","qc_contract.py")})
    write_bank(output,ref,args.pilot)
    result["bank_sha256"]=p.sha256(output)
    if args.oracle_output:
        p.require(not args.pilot, "pilot comparison is separately scoped; not a full participant output")
        p.validate_output_directory(args.oracle_output,ref)
        result["oracle_validation"]="passed after independent source construction"
    result["elapsed_seconds"]=time.monotonic()-started
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("x",encoding="utf-8") as stream:
        json.dump(result,stream,indent=2,allow_nan=False); stream.write("\n")
    print(json.dumps(result,allow_nan=False))


if __name__ == "__main__":
    main()
