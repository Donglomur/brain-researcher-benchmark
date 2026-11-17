"""Retinal input computations adapted from the MIT 5e7a862 author sources.

No input descriptor issues admission authority. The enclosing JobContext must
already own a qualified, sealed input mount. No pickle or directory discovery.
"""

FIELDS = tuple(range(1, 16))
BASELINE_FIELDS = (1, 2, 3, 5, 7, 9, 13)
SIZES = (32, 64, 128, 256, 512)
SEEDS = (0, 1, 2, 3, 4)
FAMILIES = ("linear", "MLP", "hybrid")
CELL = "20161028_1"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def exact_keys(value, keys, label):
    require(type(value) is dict and set(value) == set(keys), label)


def validate_config(group, cfg):
    """Closed metadata boundary, before imports, input reads or numerical work."""
    exact_keys(cfg, ("profile", "manifest", "choices", "training"), "retina config")
    require(group in ("J09", "J15", "J16", "J17", "J18", "J19"), "retina group")
    require(cfg["profile"] == "published-code-5e7a862-retina-v1", "unimplemented method profile")
    require(type(cfg["manifest"]) is str and bool(cfg["manifest"]), "manifest logical name")
    choices = cfg["choices"]
    exact_keys(choices, ("raw_join", "site_aggregation", "contour_profile", "output_scale", "soma_radius", "training_budget", "evaluation_checkpoint_epoch", "rfest_profile", "baseline_dtype", "experimental_rf", "jax_platform"), "retina choices")
    require(choices["raw_join"] == "explicit-keyed-pairs-no-positional-parity", "raw pair convention")
    require(choices["site_aggregation"] == "recompute-author-branch-bin-mean", "site aggregation")
    require(choices["contour_profile"] in ("paper-0.6", "author-results-0.5", "author-assembly-0.4"), "contour profile")
    require(type(choices["output_scale"]) in (int, float) and choices["output_scale"] in (40.0, 60.0), "explicit source scale 40 or 60")
    require(type(choices["soma_radius"]) in (int, float) and choices["soma_radius"] in (5.0, 7.5), "explicit source soma radius")
    require(choices["training_budget"] == "source-iterations-rounded-to-complete-epochs", "training budget semantics")
    require(type(choices["evaluation_checkpoint_epoch"]) is int and choices["evaluation_checkpoint_epoch"] >= 0, "explicit produced evaluation checkpoint epoch")
    require(choices["rfest_profile"] in ("fa18170-full20-tolerance20", "fa18170-max20-tolerance10"), "explicit prospective RFEST profile")
    require(choices["baseline_dtype"] in ("author-inferred-dtypes", "explicit-float64-adapter"), "baseline dtype profile")
    require(choices["experimental_rf"] == "reestimate-from-averaged-labels-prospective", "experimental RF method choice")
    require(choices["jax_platform"] in ("cpu", "gpu"), "explicit original train/evaluation backend")
    t = cfg["training"]
    exact_keys(t, ("iterations", "batch_size", "lr", "momentum", "beta", "reduce_every", "reduce_by", "val_frac", "test_num", "eval_every", "seed_weights", "seed_membrane", "seed_tf_loader", "seed_tf_loop", "seed_ruler"), "training keys")
    for key in ("iterations", "batch_size", "reduce_every", "reduce_by", "test_num", "eval_every"):
        require(type(t[key]) is int and t[key] > 0, "positive integer " + key)
    for key in ("seed_weights", "seed_membrane", "seed_tf_loader", "seed_tf_loop", "seed_ruler"):
        require(type(t[key]) is int and 0 <= t[key] < 2**31, "seed " + key)
    require(t["lr"] == 0.01 and type(t["lr"]) is float, "source learning rate")
    require(t["momentum"] == 0.5 and type(t["momentum"]) is float, "source momentum")
    require(t["beta"] == 0.99 and type(t["beta"]) is float, "source normalization exponent")
    require(t["val_frac"] == 0.2 and type(t["val_frac"]) is float, "source 20-percent validation")
    require(t["reduce_by"] == 10 and t["reduce_every"] == 350, "source schedule")
    return cfg


def validate_manifest(m):
    exact_keys(m, ("schema", "cell_id", "fields", "noise", "morphology", "rois"), "raw retinal manifest")
    require(m["schema"] == "retina-explicit-paired-raw-v1" and m["cell_id"] == CELL, "cell/version")
    require(type(m["fields"]) is list and tuple(m["fields"]) == FIELDS and all(type(x) is int for x in m["fields"]), "all fifteen fields")
    require(all(type(m[k]) is str and m[k] for k in ("noise", "morphology")), "logical input names")
    require(type(m["rois"]) is list and len(m["rois"]) == 232, "complete 232-ROI roster")
    seen = set()
    for row in m["rois"]:
        exact_keys(row, ("rec_id", "roi_id", "xyz", "recording_center", "stack_pixel_size", "trace", "times", "triggers"), "ROI keys")
        require(type(row["rec_id"]) is int and row["rec_id"] in FIELDS and type(row["roi_id"]) is int and row["roi_id"] > 0, "ROI coordinate")
        key = row["rec_id"], row["roi_id"]
        require(key not in seen, "duplicate paired ROI")
        seen.add(key)
        for name in ("xyz", "recording_center"):
            require(type(row[name]) is list and len(row[name]) == 3 and all(type(x) in (int, float) for x in row[name]), "ROI vector")
        require(type(row["stack_pixel_size"]) in (int, float) and row["stack_pixel_size"] > 0, "stack scale")
        require(all(type(row[k]) is str and row[k] for k in ("trace", "times", "triggers")), "raw trace logical names")
    require({r["rec_id"] for r in m["rois"]} == set(FIELDS), "field coverage")
    return m


def closest_site(xyzr, xyz):
    import numpy as np
    distances, compartments = [], []
    for branch in xyzr:
        d = np.sum((np.asarray(xyz) - branch[:, :3]) ** 2, axis=1)
        at = int(np.argmin(d))
        distances.append(float(np.min(d)))
        compartments.append(at / (len(branch) - 1) if len(branch) > 1 else 0.5)
    branch = int(np.argmin(distances))
    return branch, compartments[branch]


def image_centers(rois):
    """01_setup: preserve relative camera positions and one global mean shift."""
    import numpy as np
    centers, shifts = {}, []
    for field in FIELDS:
        rows = [r for r in rois if r["rec_id"] == field]
        first = rows[0]
        require(all(r["recording_center"] == first["recording_center"] and r["stack_pixel_size"] == first["stack_pixel_size"] for r in rows), "inconsistent camera center/scale")
        center = np.asarray(first["recording_center"]) * first["stack_pixel_size"]
        centers[field] = center[:2]
        shifts.append(np.mean([r["xyz"] for r in rows], axis=0)[:2] - center[:2])
    shift = np.mean(shifts, axis=0)
    return {k: v + shift for k, v in centers.items()}, shift


def filter_trace(trace, times, triggers):
    """02_labels cell5: zscore BEFORE causal fourth-order 7Hz filter."""
    import numpy as np
    from scipy import signal
    require(trace.ndim == times.ndim == triggers.ndim == 1 and len(trace) == len(times), "raw trace shapes")
    require(len(triggers) >= 1500 and np.all(np.diff(triggers) > 0) and np.all(np.diff(times) > 0), "ordered raw timebase")
    keep = (times > np.min(triggers)) & (times < np.max(triggers) + 0.4)
    y, t = trace[keep], times[keep]
    scale = np.std(y)
    require(np.isfinite(scale) and scale > 0, "undefined raw zscore")
    normalized = (y - np.mean(y)) / scale
    return signal.sosfilt(signal.butter(4, 7.0, "low", fs=31.25, output="sos"), normalized), t


def delayed_labels(filtered, times, triggers, delay):
    import numpy as np
    from scipy.interpolate import interp1d
    indices = interp1d(triggers[:1500], np.arange(1500), kind="zero", fill_value="extrapolate")(times)
    y = filtered[delay:]
    index = indices[:-delay]
    last = np.concatenate([np.diff(index), [0]]) > 0
    result = y[last]
    require(len(result) >= 1498, "insufficient full source delay support")
    return result[:1498]


def preprocess(ctx, manifest, cell):
    """Full actual raw ROI→label/site→BC-current path, no cached result input."""
    ctx.checkpoint()
    import numpy as np
    from sklearn.linear_model import LinearRegression
    from sklearn.model_selection import KFold, cross_val_score
    m = validate_manifest(manifest)
    noise = ctx.read_array(m["noise"])
    require(noise.shape == (15, 20, 1500), "original checkerboard axis/extent")
    centers, center_shift = image_centers(m["rois"])
    filtered, times, triggers, mappings = [], [], [], []
    design = noise.reshape(300, 1500).T[:1498]
    delay_scores = []
    for row in m["rois"]:
        ctx.checkpoint()
        tr = ctx.read_array(row["trace"]); tm = ctx.read_array(row["times"]); tg = ctx.read_array(row["triggers"])
        y, t = filter_trace(tr, tm, tg)
        scores = []
        for delay in range(6, 14):
            ctx.checkpoint()
            labels = delayed_labels(y, t, tg, delay)
            cv = KFold(n_splits=5, shuffle=True, random_state=0)
            scores.append(float(np.mean(cross_val_score(LinearRegression(), design, labels, cv=cv, scoring="neg_mean_absolute_error", verbose=0))))
        delay_scores.append(scores)
        filtered.append(y); times.append(t); triggers.append(tg)
        branch, comp = closest_site(cell.xyzr, row["xyz"])
        mappings.append(dict(rec_id=row["rec_id"], roi_id=row["roi_id"], branch=branch, comp=comp, bin=int(np.clip(np.floor(comp * 4), 0, 3)), xyz=row["xyz"]))
    best_delay = int(np.argmax(np.mean(delay_scores, axis=0))) + 6
    raw_labels = np.stack([delayed_labels(y, t, tg, best_delay)[:1024] for y, t, tg in zip(filtered, times, triggers)])
    # pandas groupby in the original sorts branch/bin within each ascending field.
    keys = sorted({(r["rec_id"], r["branch"], r["bin"]) for r in mappings})
    require(len(keys) == 147, "actual aggregation does not reproduce 147 sites")
    sites, values = [], []
    for key in keys:
        indices = [i for i, r in enumerate(mappings) if (r["rec_id"], r["branch"], r["bin"]) == key]
        sites.append(dict(field=key[0], branch=key[1], bin=key[2], comp=float(np.mean([mappings[i]["comp"] for i in indices])), xyz=np.mean([mappings[i]["xyz"] for i in indices], axis=0).tolist(), raw_roi_ids=[mappings[i]["roi_id"] for i in indices]))
        values.append(np.mean(raw_labels[indices], axis=0))
    labels = np.zeros((15 * 1024, 147)); mask = np.zeros_like(labels)
    for j, (site, values_j) in enumerate(zip(sites, values)):
        start = (site["field"] - 1) * 1024
        labels[start:start + 1024, j] = values_j
        mask[start:start + 1024, j] = 1
    ctx.record("retina_preprocessing", dict(delay_steps=best_delay, delay_scores=delay_scores, raw_roi_count=232, site_count=147, field_order=list(FIELDS), center_shift=center_shift.tolist(), raw_join="explicit-keyed-pairs-no-positional-parity", filter_order="zscore-then-butter-sosfilt", delay_metric="5fold-negative-MAE"))
    currents, connections, bc = bipolar_currents(ctx, cell, noise[:, :, :1024], centers)
    return dict(noise=noise[:, :, :1024], images=np.concatenate([noise[:, :, :1024]] * 15, axis=2), labels=labels, mask=mask, sites=sites, roi_mapping=mappings, currents=currents, connections=connections, bc=bc, centers=centers, delay=best_delay, delay_scores=delay_scores)


def bipolar_currents(ctx, cell, noise, centers):
    """04_bc_output and05_stimuli_meta, full fifteen fields; source Gaussian20."""
    import numpy as np
    from jax.scipy.signal import convolve2d
    x, y = np.meshgrid(np.linspace(-50, 50, 100), np.linspace(-50, 50, 100))
    kernel = np.exp(-(x*x + y*y) / 20.0**2) / 20.0 / 100.0
    max_input = np.max(convolve2d(np.ones((200, 200)), kernel, mode="valid"))
    intensity = (1 + np.asarray([-100,-50,-25,-12.5,-6.75,-3,3,6.75,12.5,25,50,100]) / 100) / 2
    response = np.asarray([-.05,-.12,-.15,-.1,-.08,-.03,.1,.18,.37,.64,.85,1])
    gx, gy = np.meshgrid(np.arange(0, 450*.85, 40), np.arange(0, 600*.6, np.sqrt(40**2-20**2)))
    gx[::2] += 20
    bx = gx.ravel() + cell.xyzr[1][0, 0] + 20 - 7.5*30*.85
    by = gy.ravel() + cell.xyzr[1][0, 1] - 10 - 10*30*.6
    connections = []
    for bc_id, (px, py) in enumerate(zip(bx, by)):
        for branch, points in enumerate(cell.xyzr):
            dist = np.sqrt((px-points[:, 0])**2 + (py-points[:, 1])**2)
            if np.min(dist) < 20:
                at = int(np.argmin(dist)); comp = at/(len(points)-1) if len(points)>1 else .5
                connections.append(dict(bc_id=bc_id, branch=branch, comp=comp))
    require(len(connections) > 0, "no BC-to-RGC connections")
    counts = [sum(c["bc_id"] == i for c in connections) for i in range(len(bx))]
    activity = []
    for field in FIELDS:
        ctx.checkpoint()
        ox, oy = centers[field]
        px = np.linspace(-7.5*30+.5, 7.5*30-.5, 450)+ox
        py = -np.linspace(-10*30+.5, 10*30-.5, 600)+oy
        # Euclidean closest Cartesian-grid point equals separate-axis argmin.
        ix = [int(np.argmin((px-v)**2)) for v in bx]
        iy = [int(np.argmin((py-v)**2)) for v in by]
        field_activity = []
        for image in (1-noise).transpose(2, 1, 0):
            ctx.checkpoint()
            enlarged = np.repeat(np.repeat(image, 30, axis=0), 30, axis=1)
            padded = np.zeros((enlarged.shape[0]+99, enlarged.shape[1]+99))
            padded[50:-49, 50:-49] = enlarged
            linear = convolve2d(padded, kernel, mode="valid")
            nonlinear = np.interp(linear/max_input, intensity, response)
            values = nonlinear[iy, ix]
            values = values-np.min(values)
            require(np.max(values)>0, "undefined BC range normalization")
            field_activity.append(values/np.max(values))
        activity.extend(field_activity)
    activity = np.asarray(activity)
    currents = np.stack([.1*activity[:,c["bc_id"]]/counts[c["bc_id"]] for c in connections], axis=1)
    return currents, connections, dict(x=bx, y=by, kernel=kernel, intensity=intensity, response=response)


def field_dataset(data, field, size):
    """Every reduced case retains first(size+512) images and its complete sites."""
    import numpy as np
    require(type(field) is int and field in BASELINE_FIELDS and type(size) is int and size in SIZES, "baseline coordinate")
    site_indices = [i for i,s in enumerate(data["sites"]) if s["field"] == field]
    require(bool(site_indices), "empty field")
    rows = np.arange((field-1)*1024, (field-1)*1024+size+512)
    return dict(images=data["images"][:, :, rows], currents=data["currents"][rows], labels=data["labels"][rows][:,site_indices], mask=data["mask"][rows][:,site_indices], sites=[data["sites"][i] for i in site_indices], row_ids=rows, site_indices=site_indices)
