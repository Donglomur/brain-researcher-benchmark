"""Finite reference-to-modern crossings and exact source BC-loader composition.

Source-only functions; caller authenticates bodies/runtime and owns all IO.
Legacy native pickles are decoded ONLY in the admitted reference1.5.3 stage.
The modern BC/model stage receives numeric arrays and authenticated metadata.
"""

CELL = "20161028_1"
FIELDS = tuple(range(1, 16))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest_json(value):
    import hashlib
    import json
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def numerical_descriptor(array):
    import hashlib
    import numpy as np
    require(type(array) is np.ndarray and array.dtype.kind in "biuf", "numeric array only")
    require(bool(np.isfinite(array).all()) and array.flags.c_contiguous, "finite C-order numeric array")
    return {"shape": list(array.shape), "dtype": array.dtype.str, "order": "C",
        "bytes": array.nbytes, "sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest()}


def reference_camera_packet(consumer, camera_receipt):
    """Call only in reference stage, after exact C9 extraction; no new compute."""
    consumer.reference_versions()
    import numpy as np
    require(camera_receipt["schema"] == "jaxley-source-camera-centers-v1" and camera_receipt["cell_id"] == CELL, "source camera schema")
    require(camera_receipt["field_order"] == list(FIELDS), "source camera field support")
    centers = np.asarray(camera_receipt["centers"])
    require(centers.shape == (15, 2) and centers.dtype == np.dtype("float64"), "native camera numerical dtype/shape")
    arrays = {"field_ids": np.arange(1, 16, dtype=np.int64), "centers": np.ascontiguousarray(centers)}
    return arrays, {"schema": "jaxley-camera-numeric-crossing-v1", "cell_id": CELL,
        "arrays": {key: numerical_descriptor(value) for key, value in arrays.items()},
        "units": camera_receipt["units"], "source_camera_receipt_sha256": digest_json(camera_receipt),
        "source_profile": {"numpy": "1.24.3", "pandas": "1.5.3"}}


def restore_camera_packet(arrays, metadata):
    """Modern stage; numeric hashes/order/dtypes exact, no legacy pickle."""
    import numpy as np
    import pandas as pd
    require(metadata["schema"] == "jaxley-camera-numeric-crossing-v1" and metadata["cell_id"] == CELL, "camera crossing schema")
    require(set(arrays) == set(metadata["arrays"]) == {"field_ids", "centers"}, "camera array keys")
    for key in arrays:
        require(numerical_descriptor(arrays[key]) == metadata["arrays"][key], "camera exact numeric crossing")
    require(arrays["field_ids"].dtype == np.dtype("int64") and arrays["field_ids"].tolist() == list(FIELDS), "camera exact fields")
    require(arrays["centers"].dtype == np.dtype("float64") and arrays["centers"].shape == (15, 2), "camera exact float64 axes")
    return pd.DataFrame(arrays["centers"], index=arrays["field_ids"], columns=["image_center_x", "image_center_y"])


def reference_split_packet(consumer):
    """New reference preparation emits this once; old consumer stays unchanged.

    Exact default dataloader arithmetic and legacy RNG, with complete initial
    and post-permutation state. This is a fresh split, not historical indices.
    """
    consumer.reference_versions()
    import numpy as np
    rng = np.random.RandomState(0)

    def state_packet(state):
        return {"algorithm": state[0], "keys": state[1].tolist(), "position": state[2],
                "has_gauss": state[3], "cached_gaussian": state[4]}

    before = state_packet(rng.get_state())
    num_datapoints, num_test, val_frac = 15360, 128, 0.2
    test_frac = num_test / num_datapoints
    val_frac = val_frac * (1 - test_frac)
    num_train = int(num_datapoints * (1 - val_frac - test_frac))
    all_inds = rng.permutation(np.arange(num_datapoints))
    splits = {"test": all_inds[:num_test].tolist(),
        "train": all_inds[num_test:num_test + num_train].tolist(),
        "val": all_inds[num_test + num_train:].tolist()}
    require([len(splits[name]) for name in ("train", "val", "test")] == [12185, 3047, 128], "source allocation")
    return {"schema": "jaxley-reference-source-split-v1", "numpy": "1.24.3", "seed": 0,
        "splits": splits, "splits_sha256": digest_json(splits),
        "rng_before": before, "rng_after": state_packet(rng.get_state()),
        "scope": "fresh source-default MT19937; no historical split equality"}


def validate_full_bc_table(bc_output):
    import numpy as np
    require(len(bc_output) == 1650 and list(bc_output.columns) == ["cell_id", "rec_id", "bc_id", "x_loc", "y_loc", "activity"], "full source BC table")
    require(bc_output["cell_id"].tolist() == [CELL] * 1650, "BC target cell")
    require(bc_output["rec_id"].tolist() == [field for field in FIELDS for _ in range(110)], "BC field-major source order")
    require(bc_output["bc_id"].tolist() == list(range(1, 111)) * 15, "one-based source BC order")
    activity = np.stack(bc_output["activity"].to_numpy())
    require(activity.shape == (1650, 1500) and activity.dtype == np.dtype("float64") and bool(np.isfinite(activity).all()), "full1500 finite BC activity")
    # Source connections are shared: all field rows preserve the same BC grid.
    coordinates = bc_output[["x_loc", "y_loc"]].to_numpy().reshape(15, 110, 2)
    require(coordinates.dtype == np.dtype("float64") and bool(np.isfinite(coordinates).all()), "finite BC grid")
    require(all(np.array_equal(coordinates[0], coordinates[i]) for i in range(1, 15)), "source common BC geometry")


def source_loader_join(noise, bc_output, stimuli_meta):
    """data_utils.read_data source order/slice/join, no label recomputation.

    Its source IO is replaced with admitted passed objects; source target is
    explicitly20161028_1/fields1..15/start0/1024. Existing average labels are
    passed separately to the masked builder, not loaded from a historical cache.
    """
    from itertools import chain
    import numpy as np
    validate_full_bc_table(bc_output)
    require(type(noise) is np.ndarray and noise.shape == (15, 20, 1500), "original source noise extent")
    require(noise.dtype.kind in "biuf" and bool(np.isfinite(noise).all()), "finite source noise")
    rec_ids = list(FIELDS)
    noise_stimulus = noise[:, :, 0:0 + 1024]
    noise_full = np.concatenate([noise_stimulus for _ in range(len(rec_ids))], axis=2)
    stimuli_meta = stimuli_meta[stimuli_meta["cell_id"] == CELL]
    bc_output = bc_output[bc_output["cell_id"] == CELL]
    bc_output = bc_output[bc_output["rec_id"].isin(rec_ids)].copy()
    constrained_activities = np.stack(bc_output["activity"].to_numpy())[:, 0:0 + 1024].tolist()
    bc_output["activity"] = constrained_activities
    bc_output_concatenated = bc_output.groupby("bc_id", sort=False)["activity"].apply(lambda x: list(chain(*list(x))))
    bc_output = bc_output[bc_output["rec_id"] == rec_ids[0]].copy()
    require(bc_output_concatenated.index.tolist() == bc_output["bc_id"].tolist(), "source group-assignment identity")
    bc_output["activity"] = list(bc_output_concatenated.to_numpy())
    stimuli = stimuli_meta.join(bc_output.set_index("bc_id"), on="bc_id", how="left", rsuffix="_bc")
    stimuli = stimuli.drop(columns="cell_id_bc")
    require(len(stimuli) == len(stimuli_meta) > 0, "source left-join connection count")
    require(stimuli["bc_id"].tolist() == stimuli_meta["bc_id"].tolist(), "source connection row/BC order")
    require(all(type(values) is list and len(values) == 15360 for values in stimuli["activity"]), "all15 first1024 activity segments")
    # Author train.py transposes the returned plotting images into image-major.
    return stimuli, noise_full.transpose(2, 0, 1)


def compose_model_inputs(noise, bc_output, stimuli_meta, averages, groups, association,
                         input_binding, frozen_reference_split, max_dense_bytes):
    """Compose finite full-support model inputs; return PRIVATE targets/binding.

    Model worker owns participant export (train+permitted validation targets,
    no final test targets), dependencies, source model, budget and owned caller.
    """
    import numpy as np
    require(type(max_dense_bytes) is int and max_dense_bytes > 0, "explicit dense-array byte allowance")
    connections = len(stimuli_meta)
    # Check before constructing dense currents or repeated image/label matrices.
    dense_estimate = 15360 * (connections + 2 * 147) * 8 + 15360 * 15 * 20 * noise.dtype.itemsize
    require(dense_estimate <= max_dense_bytes, "complete source arrays exceed selected allowance; never truncate")
    split = frozen_reference_split
    require(split["schema"] == "jaxley-reference-source-split-v1" and split["numpy"] == "1.24.3" and split["seed"] == 0, "reference split profile")
    require(digest_json(split["splits"]) == split["splits_sha256"], "reference split identity")
    stimuli, images = source_loader_join(noise, bc_output, stimuli_meta)
    bound = input_binding.bind_model_arrays(images, stimuli, averages, groups, association)
    require(bound["splits"] == split["splits"], "modern split differs from frozen reference split")
    bound["splits"] = {key: list(value) for key, value in split["splits"].items()}
    bound["reference_split_packet_sha256"] = digest_json(split)
    receipt = {"schema": "jaxley-source-model-input-composition-v1", "cell_id": CELL,
        "source_bc_frames": 1500, "loader_start": 0, "frames_per_field": 1024,
        "rows": 15360, "sites": 147, "observed_target_entries": int(bound["mask"].sum()),
        "connection_rows": connections, "bc_ids_are_one_based": True,
        "dense_array_bytes_estimate": dense_estimate, "dense_array_allowance": max_dense_bytes,
        "memory_scope": "logical principal arrays only, not OS/process-tree peak RAM",
        "current_dtype": bound["currents"].dtype.str, "image_dtype": images.dtype.str,
        "identity_sha256": bound["identity_sha256"],
        "reference_split_packet_sha256": bound["reference_split_packet_sha256"],
        "whole_record_preprocessing": True, "targets_are_evaluator_private": True,
        "delay_handling": "already-produced shared-delay labels; no second shift or fit",
        "label_units": "source filtered whole-record population-zscore calcium",
        "current_units": "author current convention,0.1*BC_activity/num_synapses,unchanged"}
    return bound, stimuli, receipt
