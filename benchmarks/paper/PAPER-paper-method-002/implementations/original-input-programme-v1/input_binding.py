"""Source-defined array/split/access binding. SOURCE ONLY: not executed.

The build_training_data body below is copied from author data_utils.body
SHA256 37008ab91159c2719347fc04d4339f13ee9cd30b5d16e4660525b78f227cee3e
starting line107. Its only source delta is a call-local NumPy import.
No BC generation, simulation, fitting, scoring or file IO is performed here.
"""

def build_training_data(
    i_amp,
    stimuli,
    avg_recordings,
    rec_ids,
    num_datapoints_per_scanfield,
    number_of_recordings_each_scanfield,
):
    import numpy as np
    number_of_recordings = len(avg_recordings)
    
    # The currents that will be used as step currents.
    bc_activity = np.stack(stimuli["activity"].to_numpy()).T
    currents = i_amp * np.asarray(bc_activity) / stimuli["num_synapses_of_bc"].to_numpy()
    
    # Labels will also have to go to a dataloader.
    loss_weights = np.zeros((number_of_recordings, len(rec_ids) * num_datapoints_per_scanfield))
    labels = np.zeros((number_of_recordings, len(rec_ids) * num_datapoints_per_scanfield))
    
    cumsum_rec = np.cumsum([0] + number_of_recordings_each_scanfield)
    for i in range(len(rec_ids)):
        rec_id = rec_ids[i]
        start = cumsum_rec[i]
        end = cumsum_rec[i+1]
    
        # Masks for loss.
        loss_weights[start:end, i*num_datapoints_per_scanfield: (i+1)*num_datapoints_per_scanfield] = 1.0
    
        # Labels.
        recordings_in_this_scanfield = avg_recordings[avg_recordings["rec_id"] == rec_id]
        labels_in_this_scanfield = np.asarray(np.stack(recordings_in_this_scanfield["ca"].to_numpy()).T)
        labels[start:end, i*num_datapoints_per_scanfield: (i+1)*num_datapoints_per_scanfield] = labels_in_this_scanfield.T
        i += 1
    
    loss_weights = np.asarray(loss_weights)
    loss_weights = loss_weights.T  # shape (num_images_per_scanfield, 4).
    
    labels = labels.T  # shape (num_images_per_scanfield, 4).
    labels = np.asarray(labels)

    return currents, labels, loss_weights


def require(ok, message):
    if not ok:
        raise ValueError(message)


def source_split():
    """Fresh source-defined default split; never historical-index identity.

    train.body resets legacy NumPy RNG to seed_membrane_conds+seed_ruler=0
    before dataloader.body calls permutation. A private RandomState preserves
    that exact legacy algorithm without touching another caller's global RNG.
    Source fraction arithmetic/order is deliberately retained.
    """
    import numpy as np
    num_datapoints, num_test, val_frac = 15360, 128, 0.2
    test_frac = num_test / num_datapoints
    val_frac = val_frac * (1 - test_frac)
    num_train = int(num_datapoints * (1 - val_frac - test_frac))
    all_inds = np.random.RandomState(0).permutation(np.arange(num_datapoints))
    splits = {"test": all_inds[:num_test].tolist(),
              "train": all_inds[num_test:num_test + num_train].tolist(),
              "val": all_inds[num_test + num_train:].tolist()}
    require([len(splits[k]) for k in ("train", "val", "test")] == [12185, 3047, 128], "source split counts")
    require(sorted(sum(splits.values(), [])) == list(range(15360)), "complete disjoint source split")
    return splits


def source_sites(groups, association):
    """Use actual constituent ROI keys; averaged numeric IDs are never identity."""
    require(len(groups) == 147 and len(association) == 232, "source site support")
    records = association.to_dict("records")
    sites = []
    for ordinal, group in enumerate(groups):
        require(group["average_row"] == ordinal, "source site order")
        rows = [records[i] for i in group["joined_recording_rows"]]
        require(all(row["rec_id"] == group["rec_id"] for row in rows), "site field association")
        sites.append({"field": int(group["rec_id"]), "branch": int(group["branch_ind"]),
                      "bin": int(group["comp_discrete"]), "raw_roi_ids": [int(r["roi_id"]) for r in rows]})
    keys = [(s["field"], s["branch"], s["bin"]) for s in sites]
    rois = [(s["field"], roi) for s in sites for roi in s["raw_roi_ids"]]
    require(len(set(keys)) == 147 and len(set(rois)) == len(rois) == 232, "unique source sites and ROIs")
    require(keys == sorted(keys) and {s["field"] for s in sites} == set(range(1, 16)), "source field/group order")
    return sites


def bind_model_arrays(noise_full, stimuli, averages, groups, association):
    """Available input-binding component; requires separately admitted BC data.

    noise_full is the source image-major array (15360,15,20); stimuli is the
    source-joined BC/stimulus table, in original stimulus-row order. Both need
    their own authenticated source producer and custody before this call.
    This function does not produce those missing inputs or qualify a model.
    Return is evaluator-private, including every true target and its mask.
    """
    import hashlib
    import json
    import numpy as np
    sites = source_sites(groups, association)
    require(averages[["rec_id", "branch_ind", "comp_discrete"]].values.tolist() == [[s["field"], s["branch"], s["bin"]] for s in sites], "average numerical row/site identity")
    require(averages["comp"].tolist() == [g["continuous_comp_mean"] for g in groups], "continuous recording compartment order")
    require(type(noise_full) is np.ndarray and noise_full.shape == (15360, 15, 20), "original image-major support")
    require(noise_full.dtype.kind in "iuf" and bool(np.isfinite(noise_full).all()), "finite original image dtype")
    counts = list(averages.groupby("rec_id").size())
    require(len(counts) == 15 and sum(counts) == 147 and all(n > 0 for n in counts), "complete source field counts")
    require(len(stimuli) > 0 and bool((stimuli["num_synapses_of_bc"] > 0).all()), "source BC denominators")
    currents, labels, mask = build_training_data(0.1, stimuli, averages, list(range(1, 16)), 1024, counts)
    require(currents.shape == (15360, len(stimuli)), "current row/column extent")
    require(labels.shape == mask.shape == (15360, 147), "dense label/mask extent")
    require(labels.dtype == mask.dtype == np.dtype("float64"), "source zeros-derived label/mask dtype")
    require(bool(np.isfinite(currents).all()) and bool(np.isfinite(labels).all()), "finite model arrays")
    expected_mask = (np.arange(15360)[:, None] // 1024 + 1 == np.asarray([s["field"] for s in sites])[None, :])
    require(np.array_equal(mask, expected_mask), "mask is exact observed field support")
    require(bool((labels[~expected_mask] == 0.0).all()), "source unobserved fill")
    splits = source_split()
    identity = {"sites": sites, "splits": splits}
    identity_sha = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return {"schema": "jaxley-original-model-binding-v1", "noise": noise_full,
            "currents": currents, "labels": labels, "mask": mask, "sites": sites,
            "splits": splits, "identity_sha256": identity_sha,
            "preprocessing_access": "whole cropped traces/all ROI delay selection before downstream split",
            "split_scope": "fresh source-default MT19937 seed0; historical split files not claimed",
            "current_units": "author current-unit convention: i_amp=0.1 times BC activity / num_synapses_of_bc; no cast, unit conversion or reordering"}


def candidate_view(private_binding, information_condition):
    """Release train targets and held-out features; never val/test target data.

    Access isolation is an enclosing process/mount responsibility: never pass
    private_binding to candidate code. A Python dictionary is not a sandbox.
    The information condition controls source-code availability separately; the
    data, split, targets, validation/development access and budget must be equal.
    This feature packet is paired with the source-defined validation access for
    model selection; it does not prohibit validation feedback or early stopping.
    Exact permitted feedback/cadence is frozen by the operation role contract.
    A generic validation broker is not required by this implementation.
    """
    import numpy as np
    require(information_condition in ("paper+data", "paper+data+code"), "information condition")
    out = {"schema": "jaxley-retinal-candidate-input-v1", "cell_id": "20161028_1",
           "information_condition": information_condition,
           "identity_sha256": private_binding["identity_sha256"],
           "site_keys": [[s["field"], s["branch"], s["bin"]] for s in private_binding["sites"]],
           "preprocessing_access": private_binding["preprocessing_access"], "splits": {}}
    for name in ("train", "val", "test"):
        rows = np.asarray(private_binding["splits"][name], dtype=np.int64)
        view = {"row_ids": rows.copy(), "images": private_binding["noise"][rows].copy(),
                "currents": private_binding["currents"][rows].copy(),
                "mask": private_binding["mask"][rows].copy()}
        if name == "train":
            view["targets"] = private_binding["labels"][rows].copy()
        out["splits"][name] = view
    return out


def operator_packet(private_binding):
    """Exact existing retinal-heldout score.compare operator interface.

    This packet and score report are evaluator-only. Both author and candidate
    submit schema jaxley-retinal-prediction-v1, cell_id, test_row_ids, site_keys,
    predictions; reuse pinned score.compare(operator, author, candidate).
    """
    import numpy as np
    rows = np.asarray(private_binding["splits"]["test"], dtype=np.int64)
    labels = private_binding["labels"][rows]
    mask = private_binding["mask"][rows]
    return {"schema": "jaxley-retinal-target-v1", "cell_id": "20161028_1",
            "sites": private_binding["sites"], "splits": private_binding["splits"],
            "labels": [[float(v) if bool(valid) else None for v, valid in zip(row, weights)] for row, weights in zip(labels, mask)],
            "mask": mask.tolist()}
