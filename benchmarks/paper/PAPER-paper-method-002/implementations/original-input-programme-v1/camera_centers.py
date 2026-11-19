"""Separate source-only camera prerequisite for the later exact BC producer.

Extracted from accepted retina_inputs.py setup C9 (lines248/250-251/257-283).
No source coordinate values, raw calcium, label data, file paths or IO are here.
This component is NOT part of the four-input 147-site label-consumer call.
"""

CELL = "20161028_1"


def construct_target_camera_centers(consumer, data_roi, data_scans, data_stacks_info):
    """Use only separately admitted/decoded original metadata in reference1.5.3.

    All grouping, inner joins, mean order, first stack row, first camera center,
    stack scaling, in-place camera shifts and float64 center-column assignment
    match the existing source block. No repair or center approximation occurs.
    """
    consumer.reference_versions()
    import numpy as np
    meta = data_roi[data_roi["expdate"] == CELL].copy()
    scans = data_scans[data_scans["cell_id"] == CELL]
    stacks = data_stacks_info[data_stacks_info["cell_id"] == CELL]

    grouped_meta = meta.groupby("recording_id")["roi_pos"].apply(list).to_frame()
    grouped_meta["recording_id"] = grouped_meta.index
    grouped_centers = meta.groupby("recording_id")["recording_center"].apply(list).to_frame()
    grouped_scans = scans.groupby("rec_id")["position"].apply(list).to_frame()
    grouped_scans["rec_id"] = grouped_scans.index
    scan_fields = grouped_meta.join(grouped_scans, how="inner")
    scan_fields = scan_fields.join(grouped_centers, how="inner")
    scale = stacks["pixel_size"].to_numpy()[0][0]
    shifts_x, shifts_y = [], []
    for _, field in scan_fields.iterrows():
        roi_pos = np.stack(field["roi_pos"])
        desired = np.mean(roi_pos, axis=0)
        camera = field["recording_center"][0] * scale
        shifts_x.append(desired[0] - camera[0])
        shifts_y.append(desired[1] - camera[1])
    shift_x, shift_y = np.mean(shifts_x), np.mean(shifts_y)
    scan_fields["image_center_x"] = np.zeros(len(scan_fields))
    scan_fields["image_center_y"] = np.zeros(len(scan_fields))
    for rec_id, field in scan_fields.iterrows():
        camera = field["recording_center"][0] * scale
        camera[0] += shift_x
        camera[1] += shift_y
        scan_fields.loc[rec_id, "image_center_x"] = camera[0]
        scan_fields.loc[rec_id, "image_center_y"] = camera[1]
    scan_fields = scan_fields.drop(columns=["recording_center", "roi_pos"])

    # Extra adapter checks occur after the unchanged source calculation.
    consumer.require(scan_fields.index.tolist() == list(range(1, 16)), "complete source camera field order")
    values = scan_fields[["image_center_x", "image_center_y"]].to_numpy()
    consumer.require(values.shape == (15, 2) and values.dtype == np.dtype("float64"), "source camera numeric shape/dtype")
    consumer.require(bool(np.isfinite(values).all()), "finite source camera centers")
    return scan_fields, {"schema": "jaxley-source-camera-centers-v1", "cell_id": CELL,
        "field_order": list(range(1, 16)), "centers": values.tolist(),
        "dtype": values.dtype.str, "center_shift": [float(shift_x), float(shift_y)],
        "pixel_size_first_stack_row_first_component": float(scale),
        "units": "source ROI coordinate convention after original recording_center times stack pixel_size; unchanged",
        "source": "accepted setup C9, source-defined fresh target parameterization",
        "raw_calcium_or_labels_consumed": False, "geometry_inferred_from_sites": False}
