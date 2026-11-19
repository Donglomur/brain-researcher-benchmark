"""New producer/composition controls, authored but NOT executed.

Root's previous20-check campaign is closed and is not rerun here. These new
cases require a separate root-selected campaign or admission phase in the next
owned original operation. Source/runtime custody remains owner responsibility.
"""


def run_generated_differential(producer, composition, kernel_factory):
    from types import SimpleNamespace
    from jax import config
    config.update("jax_enable_x64", True)
    config.update("jax_platform_name", "cpu")
    import jax
    import numpy as np
    import pandas as pd
    from jax.scipy.signal import convolve2d
    checks = []

    def check(condition, name):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    def refuses(call, name):
        try:
            call()
        except ValueError:
            checks.append(name)
            return
        raise AssertionError("did not refuse:" + name)

    check(jax.default_backend() == "cpu" and bool(config.read("jax_enable_x64")), "actual source convolution CPU/x64")
    # Generated geometry controls only the source grid anchor, no SWC parse.
    cell = SimpleNamespace(xyzr=[np.asarray([[0., 0., 0., 5.]]), np.asarray([[0., 0., 0., 5.], [1., 0., 0., 5.]])])
    camera = pd.DataFrame({"image_center_x": [0.0, 13.25], "image_center_y": [0.0, -7.5]}, index=[1, 2])
    noise = np.fromfunction(lambda x, y, t: (3*x + 5*y + 2*t) % 7 < 3, (15, 20, 2), dtype=np.int64).astype(np.float32)
    counts = {"literal": 0, "shared": 0}

    def factory_for(name):
        def counted_convolution(image, kernel, mode):
            counts[name] += 1
            return convolve2d(image, kernel, mode=mode)
        return kernel_factory(np, counted_convolution, cell, pixel_size=30)

    literal = producer.literal_field_loop(np, pd, factory_for("literal"), cell, noise, camera, (1, 2), lambda: None)
    shared = producer.shared_field_loop(np, pd, factory_for("shared"), cell, noise, camera, (1, 2), lambda: None)
    check(literal.index.equals(shared.index) and list(literal.columns) == list(shared.columns), "literal/shared source row-index and column order")
    check(literal.drop(columns="activity").equals(shared.drop(columns="activity")), "literal/shared exact BC coordinates and one-based IDs")
    left = np.stack(literal.activity)
    right = np.stack(shared.activity)
    check(left.dtype == right.dtype == np.dtype("float64") and left.shape == (220, 2), "complete110BC source precision for generated fields")
    check(left.tobytes(order="C") == right.tobytes(order="C"), "literal/shared exact numeric equality")
    check(counts == {"literal": 6, "shared": 3}, "sharing removes only repeated field-invariant convolution calls")
    check(bool(np.isfinite(right).all()) and bool((right.reshape(2, 110, 2).min(axis=1) == 0).all()) and bool((right.reshape(2, 110, 2).max(axis=1) == 1).all()), "normalization uses all110 BCs separately perfield/frame")

    # Independent ID/time sentinels exercise the new loader rather than replay
    # any original signal-processing or already-accepted label helper tests.
    fields = np.repeat(np.arange(1, 16, dtype=np.int64), 110)
    ids = np.tile(np.arange(1, 111, dtype=np.int64), 15)
    sentinel = fields[:, None] / 64.0 + ids[:, None] / 1024.0 + np.arange(1500, dtype=np.float64)[None, :] / 4096.0
    xy = literal[literal.rec_id == 1][["x_loc", "y_loc"]].to_numpy()
    bc = pd.DataFrame({"cell_id": ["20161028_1"] * 1650, "rec_id": fields, "bc_id": ids,
        "x_loc": np.tile(xy[:, 0], 15), "y_loc": np.tile(xy[:, 1], 15), "activity": sentinel.tolist()})
    stimuli_meta = pd.DataFrame({"cell_id": ["20161028_1"] * 3, "bc_id": [110, 1, 110],
        "branch_ind": [3, 1, 5], "comp": [0.1, 0.25, 0.8], "dist_from_bc": [1., 2., 3.], "num_synapses_of_bc": [2, 1, 2]})
    full_noise = np.fromfunction(lambda x, y, t: (17*x + 3*y + t) % 251, (15, 20, 1500), dtype=np.int64).astype(np.uint8)
    joined, images = composition.source_loader_join(full_noise, bc, stimuli_meta)
    check(joined.bc_id.tolist() == [110, 1, 110] and len(joined) == 3, "source leftjoin preserves connection-row and duplicated BC order")
    for column, bc_id in enumerate((110, 1, 110)):
        activity = np.asarray(joined.activity.iloc[column])
        expected = np.concatenate([field / 64.0 + bc_id / 1024.0 + np.arange(1024) / 4096.0 for field in range(1, 16)])
        check(activity.tobytes() == expected.tobytes(), "all15fields use first1024 source frames in order, BC" + str(column))
    check(images.shape == (15360, 15, 20) and images.dtype == np.dtype("uint8"), "source image-major shape and original dtype")
    check(np.array_equal(images[1024 + 13], full_noise[:, :, 13]), "image axes/time/field repeat binding")
    wrong_order = bc.iloc[np.r_[np.arange(110, 220), np.arange(110), np.arange(220, 1650)]]
    refuses(lambda: composition.source_loader_join(full_noise, wrong_order, stimuli_meta), "loader refuses changed field support order")
    wrong_key = stimuli_meta.copy()
    wrong_key.loc[0, "bc_id"] = 111
    refuses(lambda: composition.source_loader_join(full_noise, bc, wrong_key), "loader refuses unmatched source BC identity")
    return {"schema": "jaxley-new-producer-generated-differential-v1", "status": "PASS",
        "exact_numeric_equal": True, "checks": checks, "convolution_calls": counts,
        "runtime": {"numpy": np.__version__, "pandas": pd.__version__, "jax": jax.__version__, "backend": jax.default_backend(), "x64": True},
        "scope": "two generated fields/two frames/all110BCs plus full-size synthetic loader sentinels; no original bodies or model fit",
        "fixtures_persisted": False, "current_source_and_runtime_bound": False,
        "admission_note": "Owner/reviewer must authenticate source/runtime and convert this result into admission; raw result never issues authority."}
