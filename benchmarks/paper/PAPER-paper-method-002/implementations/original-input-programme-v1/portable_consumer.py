"""Portable reference-only label consumer kernels. SOURCE ONLY: not executed.

The two grouping functions are unchanged selected definitions from accepted
retina_inputs.py (SHA256 49a00541fd30e456eb9156686b58e07091cf88049e8a8b7c30a9635541d8f073),
lines 404-481. Original author data_utils is MIT; source lineage is in SOURCE_PINS.json.
This module reads no files, imports no numerical packages at module scope, and
does not run preprocessing or select input authority.
"""

CELL = "20161028_1"
FIELDS = tuple(range(1, 16))

def construct_target_recordings(recording_meta, label_frame, num_datapoints=1024):
    """data_utils:L37-L45/L64-L67, with an independent association sidecar.

    Encoded-key collisions, duplicates and unmatched rows are reported, not
    repaired or discarded by a new identity rule. Legacy averaged numeric IDs
    remain numeric columns and never stand in for constituent ROI identity.
    """
    import numpy as np
    meta = recording_meta[(recording_meta["cell_id"] == CELL) & recording_meta["rec_id"].isin(FIELDS)].copy()
    labels = label_frame[(label_frame["cell_id"] == CELL) & label_frame["rec_id"].isin(FIELDS)].copy()
    meta["_constructor_recording_row"] = np.flatnonzero(
        (recording_meta["cell_id"] == CELL) & recording_meta["rec_id"].isin(FIELDS))
    labels["_constructor_label_row"] = np.flatnonzero(
        (label_frame["cell_id"] == CELL) & label_frame["rec_id"].isin(FIELDS))
    labels["ca"] = np.stack(labels["ca"].to_numpy())[:, :num_datapoints].tolist()
    labels["unique_id"] = labels["rec_id"] * 100 + labels["roi_id"]
    meta["unique_id"] = meta["rec_id"] * 100 + meta["roi_id"]
    joined = meta.join(labels.set_index("unique_id"), on="unique_id", how="left", rsuffix="_ca")
    lineage = joined[["_constructor_recording_row", "_constructor_label_row", "unique_id",
                      "rec_id", "roi_id", "rec_id_ca", "roi_id_ca"]].copy().reset_index(drop=True)
    lineage = lineage.rename(columns={"_constructor_recording_row": "recording_meta_row",
                                      "_constructor_label_row": "label_frame_row"})
    lineage.insert(0, "joined_recording_row", np.arange(len(lineage)))
    encoded_keys = {}
    for frame in (meta, labels):
        for key, field, roi in frame[["unique_id", "rec_id", "roi_id"]].itertuples(index=False, name=None):
            encoded_keys.setdefault(key, set()).add((field, roi))
    diagnostics = {
        "encoded_key_collisions": [{"unique_id": key, "distinct_original_keys": sorted(keys)}
                                   for key, keys in encoded_keys.items() if len(keys) > 1],
        "duplicate_recording_key_rows": meta.loc[meta["unique_id"].duplicated(keep=False),
                                                  "_constructor_recording_row"].tolist(),
        "duplicate_label_key_rows": labels.loc[labels["unique_id"].duplicated(keep=False),
                                                "_constructor_label_row"].tolist(),
        "unmatched_recording_rows": lineage.loc[lineage["label_frame_row"].isna(),
                                                  "recording_meta_row"].tolist(),
        "unmatched_label_rows": labels.loc[~labels["unique_id"].isin(meta["unique_id"]),
                                             "_constructor_label_row"].tolist(),
        "recording_rows_outside_original_field_panel": np.flatnonzero(~recording_meta["rec_id"].isin(FIELDS)).tolist(),
        "label_rows_outside_original_field_panel": np.flatnonzero(~label_frame["rec_id"].isin(FIELDS)).tolist(),
        "source_join_output_rows": len(joined),
    }
    recordings = joined.drop(columns=["cell_id_ca", "rec_id_ca",
                                        "_constructor_recording_row", "_constructor_label_row"])
    return recordings, lineage, diagnostics


def construct_target_averages(recordings, rec_ids=FIELDS, num_datapoints=1024):
    """data_utils:L72-L104; return actual group membership/order separately."""
    import numpy as np
    import pandas as pd
    averages, membership = [], []
    for rec_id in rec_ids:
        rows = recordings[recordings["rec_id"] == rec_id].copy()
        positions = np.flatnonzero(recordings["rec_id"] == rec_id)
        discrete = np.clip(np.floor(rows["comp"] * 4).tolist(), a_min=0, a_max=3)
        rows["comp_discrete"] = discrete
        # Sidecar index is independent of duplicate source DataFrame indexes.
        member_rows = pd.DataFrame({"branch_ind": rows["branch_ind"].to_numpy(),
                                    "comp_discrete": discrete, "joined_recording_row": positions})
        for (branch, bin_id), group in member_rows.groupby(["branch_ind", "comp_discrete"]):
            membership.append({"average_row": len(membership), "rec_id": rec_id,
                               "branch_ind": branch, "comp_discrete": bin_id,
                               "joined_recording_rows": group["joined_recording_row"].tolist()})
        rows = rows.drop(columns="cell_id")
        calcium_columns = [f"ca{i}" for i in range(num_datapoints)]
        rows[calcium_columns] = pd.DataFrame(rows.ca.tolist(), index=rows.index)
        rows = rows.drop(columns="ca")
        mean_rows = rows.groupby(["branch_ind", "comp_discrete"]).mean()
        mean_rows["ca"] = mean_rows[calcium_columns].values.tolist()
        for name in calcium_columns:
            mean_rows = mean_rows.drop(columns=name)
        averages.append(mean_rows.reset_index())
    average_frame = pd.concat(averages)
    average_frame["rec_id"] = average_frame["rec_id"].astype(int)
    for ordinal, (_, row) in enumerate(average_frame.iterrows()):
        membership[ordinal]["continuous_comp_mean"] = row["comp"]
    return average_frame, membership


def require(ok, message):
    if not ok:
        raise ValueError(message)


def reference_versions():
    """Numerical compatibility check; enclosing owner attests full runtime."""
    import sys
    import numpy as np
    import pandas as pd
    require(sys.version_info[:3] == (3, 11, 3), "reference Python 3.11.3 required")
    require(np.__version__ == "1.24.3", "reference NumPy 1.24.3 required")
    require(pd.__version__ == "1.5.3", "reference pandas 1.5.3 required")


def consume_decoded(label_frame, recording_receipt, join_receipt, site_receipt):
    """Consume admitted native labels and authenticated bridge metadata.

    Caller owns input authentication, trusted pickle decode, runtime admission,
    resource bounds and output custody. Receipts supply data, never authority.
    This function does not open paths, rerun preprocessing or import Jaxley.
    Returns evaluator-private averages, exact association and constituent data.
    """
    reference_versions()
    import numpy as np
    import pandas as pd
    require(type(label_frame) is pd.DataFrame, "native label DataFrame required")
    require(list(label_frame.columns) == ["inds", "cell_id", "rec_id", "roi_id", "ca"], "label columns/order")
    require([str(d) for d in label_frame.dtypes] == ["int64", "object", "int64", "int64", "object"], "native label dtypes")
    require(type(label_frame.index) is pd.RangeIndex and label_frame.index.equals(pd.RangeIndex(232)), "fresh label RangeIndex")
    require(label_frame["inds"].tolist() == list(range(232)), "fresh setup row order")
    require(label_frame["cell_id"].tolist() == [CELL] * 232, "target cell only")
    require(all(type(v) is list and len(v) == 1498 for v in label_frame["ca"]), "full1498 source labels")
    raw_values = np.stack(label_frame["ca"].to_numpy())
    require(raw_values.shape == (232, 1498) and raw_values.dtype == np.dtype("float64"), "unconverted native label values")
    require(bool(np.isfinite(raw_values).all()), "nonfinite native label")

    columns = ["cell_id", "rec_id", "roi_id", "roi_x", "roi_y", "roi_z", "branch_ind", "comp"]
    dtypes = ["object", "int64", "int64", "float64", "float64", "float64", "int64", "float64"]
    table = recording_receipt["table"]
    require(table["rows"] == 232 and table["columns"] == columns and table["dtypes"] == dtypes, "recording metadata schema")
    require(table["index_class"] == "pandas.core.indexes.range.RangeIndex" and table["index_dtype"] == "int64" and table["index_names"] == [None], "recording index schema")
    rows = recording_receipt["rows"]
    require(type(rows) is list and len(rows) == 232 and all(set(r) == set(columns) for r in rows), "complete metadata rows")
    # JSON float values are round-tripped binary64 from the authenticated receipt.
    # Do not call modern Jaxley or recompute geometry during label consumption.
    recording_meta = pd.DataFrame(rows, columns=columns)
    require([str(d) for d in recording_meta.dtypes] == dtypes, "metadata reconstruction dtype change")
    require(recording_meta["cell_id"].tolist() == [CELL] * 232, "metadata target cell")
    require(recording_meta[["rec_id", "roi_id"]].values.tolist() == label_frame[["rec_id", "roi_id"]].values.tolist(), "complete ordered ROI identity")
    require(bool(np.isfinite(recording_meta[columns[3:]].to_numpy()).all()), "nonfinite geometry")
    require(bool(recording_meta["comp"].between(0.0, 1.0).all()), "continuous compartment bounds")

    recordings, association, diagnostics = construct_target_recordings(recording_meta, label_frame, 1024)
    require(diagnostics["source_join_output_rows"] == 232, "source join row count")
    require(all(not value for key, value in diagnostics.items() if key != "source_join_output_rows"), "source join diagnostic failure")
    require(join_receipt["projection_only"] is True, "expected identity-only saved join")
    require(association.to_dict("records") == join_receipt["lineage"], "full source join association differs")
    averages, groups = construct_target_averages(recordings, FIELDS, 1024)
    require(len(averages) == len(groups) == 147, "complete original site support")
    require(site_receipt["identity_only_projection"] is True, "saved site projection scope")
    keys = ("average_row", "rec_id", "branch_ind", "comp_discrete", "joined_recording_rows", "continuous_comp_mean")
    expected = [{key: row[key] for key in keys} for row in site_receipt["groups"]]
    require(groups == expected, "actual group order/membership/continuous-comp differs")
    require(averages.drop(columns="ca").to_dict("records") == site_receipt["group_scalar_means"], "all numeric metadata group means differ")
    require(sorted(i for g in groups for i in g["joined_recording_rows"]) == list(range(232)), "ROI constituent partition")
    averaged_values = np.stack(averages["ca"].to_numpy())
    require(averaged_values.shape == (147, 1024) and averaged_values.dtype == np.dtype("float64"), "averaged label dtype/shape")
    require(bool(np.isfinite(averaged_values).all()), "nonfinite averaged labels")
    return averages, association, groups, diagnostics


def numeric_crossing(averages, groups):
    """No pickle/object arrays; preserve numeric values, columns and row index.

    Evaluator-private return. Serialize each array with np.save(...,
    allow_pickle=False); the owner binds whole-file bytes/hash and the descriptor.
    The consumer on the other side MUST verify descriptors and numeric bytes.
    """
    import hashlib
    import numpy as np
    require(len(averages) == len(groups) == 147, "crossing site count")
    arrays = {"index": np.asarray(averages.index)}
    descriptors = []
    for ordinal, name in enumerate(averages.columns):
        array = np.stack(averages[name].to_numpy()) if name == "ca" else averages[name].to_numpy()
        require(array.dtype.kind in "if" and bool(np.isfinite(array).all()), "finite numeric crossing only")
        key = "column_%03d" % ordinal
        arrays[key] = np.ascontiguousarray(array)
        descriptors.append({"name": name, "key": key})
    require(arrays["index"].dtype == np.dtype("int64"), "source average index dtype")
    portable_groups = [{"average_row": int(g["average_row"]), "rec_id": int(g["rec_id"]),
        "branch_ind": int(g["branch_ind"]), "comp_discrete": float(g["comp_discrete"]),
        "joined_recording_rows": [int(i) for i in g["joined_recording_rows"]],
        "continuous_comp_mean": float(g["continuous_comp_mean"])} for g in groups]
    manifest = {"schema": "jaxley-147-native-numeric-crossing-v1", "columns": descriptors,
                "index_name": averages.index.name, "arrays": {}, "groups": portable_groups,
                "label_units": "dimensionless whole-cropped-record population z-score followed by causal lowpass; no postfilter normalization",
                "coordinate_units": "original SWC source-coordinate units unchanged",
                "preprocessing_access": "all target ROI traces and first1498 stimulus rows before downstream split",
                "scope": "fresh source-defined first1024/group means; no model performance or historical-cache equality"}
    for key, array in arrays.items():
        require(array.dtype.byteorder in ("=", "<", "|"), "little-endian reference crossing required")
        data = array.tobytes(order="C")
        manifest["arrays"][key] = {"shape": list(array.shape), "dtype": array.dtype.str,
            "order": "C", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return arrays, manifest


def restore_numeric_crossing(arrays, manifest):
    """Modern-runtime boundary: restore ONLY after byte/dtype/order equality.

    No pandas 1.5 pickle enters a modern runtime. No numeric cast or new mean is
    permitted here. Caller authenticates manifest and .npy files before loading
    them with allow_pickle=False, and applies a <=2 MiB aggregate numeric cap.
    """
    import hashlib
    import numpy as np
    import pandas as pd
    require(manifest["schema"] == "jaxley-147-native-numeric-crossing-v1", "crossing schema")
    require(set(arrays) == set(manifest["arrays"]), "crossing array set")
    require(sum(a.nbytes for a in arrays.values()) <= 2 * 1024 * 1024, "crossing bound")
    for key, array in arrays.items():
        desc = manifest["arrays"][key]
        require(type(array) is np.ndarray and array.dtype.kind in "if", "numeric array type")
        require(array.flags.c_contiguous and list(array.shape) == desc["shape"] and array.dtype.str == desc["dtype"], "crossing dtype/shape/order")
        require(desc["order"] == "C" and array.nbytes == desc["bytes"], "crossing extent")
        require(bool(np.isfinite(array).all()), "crossing finite check")
        require(hashlib.sha256(array.tobytes(order="C")).hexdigest() == desc["sha256"], "crossing exact numeric bytes")
    columns = manifest["columns"]
    require(len({d["name"] for d in columns}) == len(columns), "crossing duplicate column")
    values = {d["name"]: arrays[d["key"]].tolist() if d["name"] == "ca" else arrays[d["key"]] for d in columns}
    frame = pd.DataFrame(values, index=arrays["index"])
    frame.index.name = manifest["index_name"]
    require(len(frame) == 147 and np.stack(frame["ca"]).shape == (147, 1024), "restored support")
    return frame
