"""Fresh-target author BC04/stimuli05 transformations. SOURCE ONLY.

No file IO, decode, geometry parse, model fit or runtime admission occurs here.
The literal helper factory is separately pinned. The caller admits the source
NumPy/pandas/JAX CPU-x64 runtime, geometry and exact camera/noise inputs.
"""

CELL = "20161028_1"
FIELDS = tuple(range(1, 16))
SWC_SHA256 = "0ecddbbac1b847734539aab847d883a3403a7840ae5d8063aac52fd97881f069"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def validate_geometry(cell, geometry_binding):
    import numpy as np
    require(geometry_binding["cell_id"] == CELL and geometry_binding["source_swc_sha256"] == SWC_SHA256, "source producer morphology identity")
    require(geometry_binding["source_parameters"] == {"nseg": 4, "max_branch_len": 300.0, "min_radius": 5.0}, "source producer geometry stage")
    basis = geometry_binding["basis"]
    require(basis in ("source-min-radius5-parse", "proved-identical-xy-branch-order-point-counts"), "producer geometry basis")
    if basis != "source-min-radius5-parse":
        proof = geometry_binding["equivalence_proof_sha256"]
        require(type(proof) is str and len(proof) == 64 and all(c in "0123456789abcdef" for c in proof), "qualified geometry reuse proof")
    require(len(cell.xyzr) >= 2, "source branch1 grid anchor")
    for branch in cell.xyzr:
        points = np.asarray(branch)
        require(points.ndim == 2 and points.shape[0] > 0 and points.shape[1] == 4, "source xyzr shape")
        require(points.dtype == np.dtype("float64") and bool(np.isfinite(points).all()), "finite x64 source geometry")


def validate_noise_camera(noise, camera_fields):
    import numpy as np
    require(type(noise) is np.ndarray and noise.shape == (15, 20, 1500), "complete source stimulus extent")
    require(noise.dtype.kind in "biuf" and bool(np.isfinite(noise).all()), "finite source noise without casting")
    require(camera_fields.index.tolist() == list(FIELDS), "source camera field order")
    centers = camera_fields[["image_center_x", "image_center_y"]].to_numpy()
    require(centers.shape == (15, 2) and centers.dtype == np.dtype("float64") and bool(np.isfinite(centers).all()), "exact C9 camera columns")


def source_runtime(kernel_factory, cell):
    import numpy as np
    import pandas as pd
    import jax
    from jax.scipy.signal import convolve2d
    require(bool(jax.config.read("jax_enable_x64")), "source BC x64 required")
    require(jax.default_backend() == "cpu", "source BC CPU backend")
    return np, pd, kernel_factory(np, convolve2d, cell, pixel_size=30)


def source_grid(ops, cell):
    # Literal04C5 arithmetic and04C15 grid calls; no soma-coordinate shortcut.
    pixel_size = 30
    size_multiplier_for_bc_grid_x = 0.85
    size_multiplier_for_bc_grid_y = 0.6
    bc_spacing = 40.0
    offset_for_bc_center_x = -20.0
    offset_for_bc_center_y = 10.0
    soma_x = cell.xyzr[1][0, 0] - offset_for_bc_center_x
    soma_y = cell.xyzr[1][0, 1] - offset_for_bc_center_y
    bc_grid_start_x = soma_x - 7.5 * pixel_size * size_multiplier_for_bc_grid_x
    bc_grid_start_y = soma_y - 10.0 * pixel_size * size_multiplier_for_bc_grid_y
    bc_grid_size_x = 450.0 * size_multiplier_for_bc_grid_x
    bc_grid_size_y = 600.0 * size_multiplier_for_bc_grid_y
    bc_loc_x_origin_0, bc_loc_y_origin_0 = ops["get_bc_cell_locations"](bc_spacing, bc_grid_size_x, bc_grid_size_y)
    return ops["move_bc_locations"](bc_loc_x_origin_0, bc_loc_y_origin_0, bc_grid_start_x, bc_grid_start_y)


def frame_table(np, pd, rec_id, bc_loc_x, bc_loc_y, activities_across_time):
    # Literal04C15L42/L46. BC identities start at1 and source index restarts.
    activities_across_time = np.asarray(activities_across_time).T
    require(activities_across_time.shape[0] == 110 and bool(np.isfinite(activities_across_time).all()), "complete finite BC output")
    return pd.DataFrame().from_dict({"cell_id": CELL, "rec_id": rec_id,
        "bc_id": np.arange(1, len(bc_loc_x) + 1), "x_loc": bc_loc_x,
        "y_loc": bc_loc_y, "activity": activities_across_time.tolist()})


def literal_field_loop(np, pd, ops, cell, noise, camera_fields, fields, checkpoint):
    """Literal04C15 work order, with passed inputs and checkpoint-only additions.

    The production facade requires all15 fields/all1500 frames. A generated
    equivalence control may call this pure loop with a smaller generated extent.
    """
    dfs = []
    for rec_id in fields:
        checkpoint()
        # C9 centers are common to every ROI in a field; this one-row view is
        # the exact center selected by source setup[cell,rec_id,roi_id=1].
        df = camera_fields.loc[[rec_id]]
        im_pos_x, im_pos_y = ops["get_image_locs"](df)
        noise_stimulus = 1.0 - noise
        opl_kernel = ops["build_opl_kernel"](filter="Gaussian", std=20.0, filter_size=50)
        max_of_bc_inputs = np.max(ops["opl"](np.ones((200, 200)), opl_kernel))
        BC = ops["BipolarCell"](max_of_bc_inputs)
        bc_loc_x, bc_loc_y = source_grid(ops, cell)
        activities_across_time = []
        for time_point in range(noise_stimulus.shape[2]):
            checkpoint()
            image = noise_stimulus[:, :, time_point].T
            upsampled_image = ops["upsample_image"](image, 30, 50)
            bc_input = ops["opl"](upsampled_image, opl_kernel)
            bc_output = BC(bc_input)
            bipolar_cell_activity = ops["discretize_bc_output"](bc_output, bc_loc_x, bc_loc_y, im_pos_x, im_pos_y)
            activities_across_time.append(bipolar_cell_activity)
        dfs.append(frame_table(np, pd, rec_id, bc_loc_x, bc_loc_y, activities_across_time))
    return pd.concat(dfs)


def source_sampling_indices(np, bc_loc_x, bc_loc_y, im_pos_x, im_pos_y):
    """Exact04C13L39-L52 calculation, hoisted because geometry is frame-invariant.

    Retains meshgrid, squared differences, sqrt, flattened first argmin and
    unravel_index. Does not replace them with separate-axis nearest sampling.
    """
    grid_x, grid_y = np.meshgrid(im_pos_x, im_pos_y)
    dists = []
    for x, y in zip(bc_loc_x, bc_loc_y):
        dist_x = (grid_x - x)**2
        dist_y = (grid_y - y)**2
        dist = np.sqrt(dist_x + dist_y)
        min_ind = np.unravel_index(np.argmin(dist), dist.shape)
        dists.append(min_ind)
    return np.asarray(dists)


def sample_and_normalize(np, bc_output, indices):
    # Same scalar sampling order and literal all-BC normalization as04C13.
    output_vals_at_bc_loc = []
    for min_ind in indices:
        output_vals_at_bc_loc.append(bc_output[tuple(min_ind)])
    output_vals_at_bc_loc = output_vals_at_bc_loc - np.min(output_vals_at_bc_loc)
    output_vals_at_bc_loc = output_vals_at_bc_loc / np.max(output_vals_at_bc_loc)
    return output_vals_at_bc_loc


def shared_field_loop(np, pd, ops, cell, noise, camera_fields, fields, checkpoint):
    """Same source operations with field-invariant work shared explicitly.

    Each frame is processed, and every field/BC value is sampled/normalized.
    No FFT, separable kernel, changed formula, dtype cast or frame truncation.
    Literal-versus-shared generated equivalence must precede original selection.
    """
    noise_stimulus = 1.0 - noise
    opl_kernel = ops["build_opl_kernel"](filter="Gaussian", std=20.0, filter_size=50)
    max_of_bc_inputs = np.max(ops["opl"](np.ones((200, 200)), opl_kernel))
    BC = ops["BipolarCell"](max_of_bc_inputs)
    bc_loc_x, bc_loc_y = source_grid(ops, cell)
    indices, activities = {}, {field: [] for field in fields}
    for rec_id in fields:
        checkpoint()
        im_pos_x, im_pos_y = ops["get_image_locs"](camera_fields.loc[[rec_id]])
        indices[rec_id] = source_sampling_indices(np, bc_loc_x, bc_loc_y, im_pos_x, im_pos_y)
    for time_point in range(noise_stimulus.shape[2]):
        checkpoint()
        image = noise_stimulus[:, :, time_point].T
        upsampled_image = ops["upsample_image"](image, 30, 50)
        bc_input = ops["opl"](upsampled_image, opl_kernel)
        bc_output = BC(bc_input)
        for rec_id in fields:
            activities[rec_id].append(sample_and_normalize(np, bc_output, indices[rec_id]))
    return pd.concat([frame_table(np, pd, field, bc_loc_x, bc_loc_y, activities[field]) for field in fields])


def produce_off_bc_literal(noise, camera_fields, cell, geometry_binding, kernel_factory, checkpoint):
    validate_geometry(cell, geometry_binding)
    validate_noise_camera(noise, camera_fields)
    np, pd, ops = source_runtime(kernel_factory, cell)
    output = literal_field_loop(np, pd, ops, cell, noise, camera_fields, FIELDS, checkpoint)
    return output, producer_receipt(output, "literal-field-major", 22500, 15, 15 * 1500 * 110)


def produce_off_bc_shared(noise, camera_fields, cell, geometry_binding, kernel_factory, checkpoint):
    validate_geometry(cell, geometry_binding)
    validate_noise_camera(noise, camera_fields)
    np, pd, ops = source_runtime(kernel_factory, cell)
    output = shared_field_loop(np, pd, ops, cell, noise, camera_fields, FIELDS, checkpoint)
    return output, producer_receipt(output, "shared-field-invariant-source-operations", 1500, 1, 15 * 110)


def producer_receipt(output, method, frame_convolutions, normalization_convolutions, pixel_argmins):
    import numpy as np
    require(len(output) == 1650 and list(output.columns) == ["cell_id", "rec_id", "bc_id", "x_loc", "y_loc", "activity"], "source BC table schema")
    require(output["rec_id"].tolist() == [field for field in FIELDS for _ in range(110)], "source BC field-major order")
    require(output["bc_id"].tolist() == list(range(1, 111)) * 15, "source one-based BC identities")
    values = np.stack(output["activity"].to_numpy())
    require(values.shape == (1650, 1500) and values.dtype == np.dtype("float64") and bool(np.isfinite(values).all()), "full1500 finite x64 activities")
    return {"schema": "jaxley-source-bc-output-v1", "cell_id": CELL, "method": method,
        "field_order": list(FIELDS), "bc_id_order": list(range(1, 111)),
        "activity_shape": [1650, 1500], "activity_dtype": values.dtype.str,
        "activity_units": "source OFF-BC nonlinear response, frame-wise min/range normalized over all110 BCs",
        "full_input_extent_before_loader_slice": True, "frame_convolution_calls": frame_convolutions,
        "max_input_convolution_calls": normalization_convolutions,
        "full_2d_first_argmin_calls": pixel_argmins, "source_min_radius": 5.0,
        "new_target_parameterization": "20161028_1/noise/fields1..15; source notebook saved another target"}


def produce_stimuli_meta(bc_output, cell, geometry_binding, kernel_factory, checkpoint):
    """Literal05C6-C13: source rec_id1 geometry, BC then branch row order."""
    import numpy as np
    import pandas as pd
    validate_geometry(cell, geometry_binding)
    ops = kernel_factory(np, None, cell, pixel_size=30)
    stim = bc_output[bc_output["cell_id"] == CELL]
    stim = stim[stim["rec_id"] == 1]
    require(stim["bc_id"].tolist() == list(range(1, 111)), "source rec_id1 ordered BC geometry")
    bc_loc_x = stim["x_loc"].to_numpy()
    bc_loc_y = stim["y_loc"].to_numpy()
    bc_ids = stim["bc_id"].to_numpy()
    branch_inds_for_every_bc = []
    comp_inds_for_every_bc = []
    mind_dists_of_branches_for_every_bc = []
    bc_ids_per_stim = []
    for x, y, id in zip(bc_loc_x, bc_loc_y, bc_ids):
        checkpoint()
        branches, comps, min_dist_of_branch_in_pixel = ops["compute_jaxley_stim_locations"](x, y)
        branch_inds_for_every_bc += branches
        comp_inds_for_every_bc += comps
        mind_dists_of_branches_for_every_bc += min_dist_of_branch_in_pixel
        bc_ids_per_stim += [id] * len(branches)
    stim_df = pd.DataFrame().from_dict({"cell_id": CELL, "bc_id": bc_ids_per_stim,
        "branch_ind": branch_inds_for_every_bc, "comp": comp_inds_for_every_bc,
        "dist_from_bc": mind_dists_of_branches_for_every_bc})
    stim_df["num_synapses_of_bc"] = stim_df.groupby("bc_id").bc_id.transform(len)
    require(len(stim_df) > 0, "source generated no BC connections")
    require(bool(np.isfinite(stim_df.drop(columns="cell_id").to_numpy()).all()), "finite source stimuli metadata")
    return stim_df
