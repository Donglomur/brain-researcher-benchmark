"""Manufactured-only MAPREL artifacts. Never imports source/oracle readers."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

import proof_of_work as p
import spin_math as m


def reference():
    ids = np.arange(1, 401, dtype=np.int64)
    x = ids.astype(float)
    return dict(parcel_ids=ids, labels=[f"parcel_{i}" for i in ids], networks=[f"net_{i%7}" for i in ids],
                hemisphere=np.repeat([0, 1], 200), support_n=np.full(400, 3),
                support_sha256=[f"{int(i):064x}" for i in ids],
                centroids=np.column_stack([np.cos(x), np.sin(x), np.cos(x/3)])*100,
                maps=np.column_stack([np.sin(x/9)+x/300, np.cos(x/13)-x/700]),
                pins=dict(source_manifest_sha256="a"*64, method_contract_sha256="b"*64, output_schema_sha256="c"*64),
                source_files=[dict(path="dummy.gii", role="gradient_l", size_bytes=17, sha256="d"*64)],
                source_observed={role: dict(arrays=[dict(shape=[1200], dtype="<f4", metadata={"dtype": "documentary literal"})])
                                 for role in p.GIFTI_ROLES})


def fake_construct(centroids, hemisphere, parcel_ids, method, seed, count):
    """Deliberately toy assignments; not a generator-conformance fixture."""
    ids = np.asarray(parcel_ids)
    indices = np.arange(len(ids))
    columns = []
    for k in range(count):
        column = indices.copy()
        for hemi in (0, 1):
            subset = indices[np.asarray(hemisphere) == hemi]
            column[subset] = np.roll(subset, (k+seed+1) % len(subset))
        columns.append(column)
    return ids[np.column_stack(columns)], []


def write_json(path, value):
    Path(path).write_text(json.dumps(value, allow_nan=False, indent=2)+"\n", encoding="utf-8")


def emit(directory, ref, *, method="original", seed=0, count=100, own=None, mapped=None):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    own = ref["maps"].copy() if own is None else own
    if mapped is None: mapped, _ = fake_construct(ref["centroids"], ref["hemisphere"], ref["parcel_ids"], method, seed, count)
    with (root/"parcels.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=p.PARCEL_FIELDS)
        writer.writeheader()
        for i, parcel_id in enumerate(ref["parcel_ids"]):
            writer.writerow(dict(parcel_id=int(parcel_id), label=ref["labels"][i], network=ref["networks"][i],
                                 hemisphere="L" if ref["hemisphere"][i] == 0 else "R", n_vertices=int(ref["support_n"][i]),
                                 support_sha256=ref["support_sha256"][i], gradient2=float(own[i, 0]), thickness=float(own[i, 1])))
    np.savez_compressed(root/"spin_evidence.npz", parcel_ids=ref["parcel_ids"], rotation_ids=np.arange(count),
                        centroids=ref["centroids"], hemisphere=ref["hemisphere"], spin_parcel_ids=mapped)
    write_json(root/"results.json", p.expected_results(m.replay(own, ref["maps"], ref["parcel_ids"], mapped), method, seed, count))
    metadata = p.metadata_expected(ref, mapped)
    metadata.update(software_versions={"python": "manufactured"}, warnings=[])
    write_json(root/"run_metadata.json", metadata)
    (root/"findings.md").write_text("Manufactured signed-map result; no prescribed conclusion.\n", encoding="utf-8")
    return root
