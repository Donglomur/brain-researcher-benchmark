"""J13 concrete full-chain HMC producers; no numerical import-time effects.

Source density, source display and fully bound alternatives are separate.
The family never creates input/resource/native authority or completion receipts.
"""
from . import conductance as cg

PRODUCTS = ("chains_200_transitions_500", "log_density", "acceptance", "last_samples",
            "distance_bin_quantiles", "mixing_calibration")


def density_functions(bundle):
    import jax, jax.numpy as jnp
    choices = bundle["choices"]
    transform, unflatten = bundle["transform"], bundle["unflatten"]
    @jax.jit
    def log_det_transform(tree):
        def transformed_sum(value):
            return jax.tree_util.tree_reduce(lambda x,y: jnp.add(x.sum(), y.sum()), transform.forward(value))
        derivative = jax.grad(transformed_sum)(tree)
        logged = jax.tree_util.tree_map(lambda x: jnp.log(jnp.abs(x)), derivative)
        return jax.tree_util.tree_reduce(lambda x,y: jnp.add(x.sum(), y.sum()), logged)
    def prior(flat):
        unconstrained = unflatten(flat)
        return -choices["posterior_regularizer_weight"]*bundle["penalty"](unconstrained) + log_det_transform(unconstrained)
    def likelihood(flat):
        physical = transform.forward(unflatten(flat))
        voltage = bundle["simulate_posterior"](physical)
        return -bundle["voltage_loss"](voltage)/choices["likelihood_scale"]
    return prior, likelihood


def hmc_stage(ctx, key, position, density, transitions, step_size, retain_positions):
    """All original transitions are observed, including the 2000-step prior.

    Full posterior arrays are allocated only in a real selected native job.
    Their sizes are compiler resource demand, not a claim that host/JAX device
    allocations are already qualified. No thinning or silently shortened run.
    """
    import numpy as np
    import jax, jax.numpy as jnp, blackjax
    if tuple(position.shape) != (200,1390) or type(transitions) is not int or transitions <= 0:
        raise ValueError("complete chain/coordinate support required")
    algorithm = blackjax.hmc(logdensity_fn=density, inverse_mass_matrix=jnp.ones(1390),
                             num_integration_steps=5, step_size=step_size)
    state = jax.vmap(algorithm.init)(position)
    step = jax.jit(jax.vmap(algorithm.step))
    log_density = np.empty((transitions,200), dtype=np.float64)
    acceptance = np.empty((transitions,200), dtype=np.float64)
    accepted = np.empty((transitions,200), dtype=np.bool_)
    divergent = np.empty((transitions,200), dtype=np.bool_)
    gradient_norm = np.empty((transitions,200), dtype=np.float64)
    trajectory = np.empty((transitions,200,1390), dtype=np.float64) if retain_positions else None
    initial_log_density = cg.finite_array(state.logdensity, (200,)).copy()
    for transition in range(transitions):
        ctx.checkpoint()
        key, subkey = jax.random.split(key)
        keys = jax.random.split(subkey, 200)
        state, info = step(keys, state)
        log_density[transition] = cg.finite_array(state.logdensity, (200,))
        acceptance[transition] = cg.finite_array(info.acceptance_rate, (200,))
        accepted[transition] = np.asarray(info.is_accepted, dtype=bool)
        divergent[transition] = np.asarray(info.is_divergent, dtype=bool)
        gradient_norm[transition] = cg.finite_array(jnp.linalg.norm(state.logdensity_grad, axis=-1), (200,))
        if np.any((acceptance[transition] < 0) | (acceptance[transition] > 1)):
            raise ValueError("invalid HMC acceptance probability")
        if trajectory is not None:
            trajectory[transition] = cg.finite_array(state.position, (200,1390))
    terminal = cg.finite_array(state.position, (200,1390)).copy()
    ctx.checkpoint()
    return {"terminal": terminal, "trajectory": trajectory, "log_density": log_density,
            "acceptance": acceptance, "accepted": accepted, "divergent": divergent,
            "gradient_norm": gradient_norm, "initial_log_density": initial_log_density,
            "transitions": transitions, "step_size": step_size, "leapfrog_steps": 5}


def sample(ctx, bundle, posterior_steps):
    """Explicit CLI200 diagnostic or full500; callers cannot conflate products."""
    import jax, jax.numpy as jnp
    if posterior_steps not in (200,500):
        raise ValueError("source-bound posterior transition count required")
    prior_density, likelihood = density_functions(bundle)
    key = jax.random.PRNGKey(ctx.config["posterior_seed"])
    unused_key, init_key, prior_key, sample_key = jax.random.split(key, 4)
    initial = jax.vmap(lambda k: jax.random.normal(k, shape=(1390,))*2)(jax.random.split(init_key, 200))
    prior = hmc_stage(ctx, prior_key, initial, prior_density, 2000, 0.1, False)
    posterior = hmc_stage(ctx, sample_key, jnp.asarray(prior["terminal"]),
                          lambda x: prior_density(x)+likelihood(x), posterior_steps, 0.01, True)
    return initial, prior, posterior


def physical_terminal(bundle, terminal):
    import jax, jax.numpy as jnp
    transform = bundle["transform"]; unflatten = bundle["unflatten"]
    convert = jax.jit(jax.vmap(lambda x: bundle["flatten"](transform.forward(unflatten(x)))))
    return cg.finite_array(convert(jnp.asarray(terminal)), (200,1390))


def channel_columns(identity):
    """All ten spatial channels, with actual ordered parameter and branch IDs."""
    channels = list(cg.gt_apical) + list(cg.gt_axon)[:7]
    return [(key, [row["index"] for row in identity["parameters"] if row["key"] == key]) for key in channels]


def distance_quantiles(ctx, bundle, physical):
    import numpy as np
    from scipy.interpolate import CubicSpline
    from scipy.ndimage import gaussian_filter1d
    identity = bundle["identity"]; choices = bundle["choices"]
    complete = choices["binning"] == "explicit_complete_edges"
    supplied = bundle["expected"]["complete_bin_edges"]
    if complete and (type(supplied) is not dict or set(supplied) != {"apical", "axon"}):
        raise ValueError("independently selected complete bin edges required")
    if not complete and supplied is not None:
        raise ValueError("literal diagnostic cannot consume alternate edges")
    alphas = np.linspace(0.0, 1.0, 101)
    result = []
    for key, columns in channel_columns(identity):
        ctx.checkpoint()
        group = "apical" if key in cg.gt_apical else "axon"
        distances = np.asarray(identity["distance_um"][group], dtype=float)
        if len(columns) != len(distances) or not len(columns):
            raise ValueError("complete channel/distance support required")
        if complete:
            edges = cg.finite_array(supplied[group], (12,))
            if not np.all(np.diff(edges) > 0) or np.any(distances < edges[0]) or np.any(distances > edges[-1]):
                raise ValueError("selected eleven-bin partition omits parameter support")
            assignments = np.searchsorted(edges, distances, side="right")-1
            assignments[distances == edges[-1]] = 10
            thresholds = None
        else:
            # Literal source has eleven THRESHOLDS and twelve assignments;
            # its renderer omits assignment11. Every omitted identity is kept
            # explicitly below, never called complete eleven-bin coverage.
            thresholds = np.linspace(100,1100,11) if group == "apical" else np.linspace(50,600,11)
            assignments = np.digitize(distances, thresholds)
            edges = None
        bins, quantile_columns = [], []
        for b in range(11):
            local = np.flatnonzero(assignments == b)
            selected_columns = [columns[int(j)] for j in local]
            draws = physical[:, selected_columns].reshape(-1)
            row = {"bin": b, "parameter_indices": selected_columns,
                   "branch_ids": [identity["parameters"][j]["branch"] for j in selected_columns],
                   "parameter_count": len(selected_columns), "sample_count": int(draws.size)}
            if not draws.size:
                row.update(defined=False, reason="empty_bin", quantiles=None)
                quantile_columns.append(None)
            else:
                q = cg.finite_array(np.quantile(draws, alphas, method="linear"), (101,))
                row.update(defined=True, quantiles=q.tolist())
                quantile_columns.append(q)
            bins.append(row)
        omitted = [columns[int(j)] for j in np.flatnonzero((assignments < 0) | (assignments > 10))]
        if complete and (omitted or sum(x["parameter_count"] for x in bins) != len(columns)):
            raise ValueError("complete bin partition failed")
        display = {"defined": False, "reason": "not_literal_source_profile"}
        if not complete:
            if any(q is None for q in quantile_columns):
                display = {"defined": False, "reason": "source_renderer_has_empty_bin", "available_case_fallback": False}
            else:
                q = np.stack(quantile_columns, axis=1)
                smooth = gaussian_filter1d(q, 0.1, axis=1)
                x = np.linspace(0,1200,100) if group == "apical" else np.linspace(0,600,100)
                rendered = cg.finite_array(np.stack([CubicSpline(thresholds, smooth[i])(x) for i in range(100)]), (100,100))
                display = {"defined": True, "x_um": x.tolist(), "quantiles": rendered.tolist(),
                           "retained_quantile_indices": list(range(100)), "excluded_q1_index": 100,
                           "lower_index": 5, "upper_index": 95,
                           "smoothing_sigma": 0.1, "extrapolates": True,
                           "monotonicity_or_bounds_repair": False}
        # The notebook's black plotted axon GP differs from its simulated
        # constant-overwrite truth. Keep both vectors; do not mutate the cell.
        plotted = np.interp(distances, bundle["gp_grid"], bundle["profiles"][group][key])*cg.bounds[key][1]
        actual_truth = cg.finite_array(bundle["flatten"](bundle["parameters"]))[columns]
        result.append({"channel": key, "group": group, "parameter_indices": columns,
                       "distance_um": distances.tolist(), "assignments": assignments.tolist(),
                       "physical_bounds_source_numeric": cg.bounds[key],
                       "source_y_axis": np.linspace(cg.bounds[key][0], cg.bounds[key][1], 101).tolist(),
                       "gp_grid_um": bundle["gp_grid"].tolist(),
                       "plot_gp_profile": (np.asarray(bundle["profiles"][group][key])*cg.bounds[key][1]).tolist(),
                       "thresholds": None if thresholds is None else thresholds.tolist(),
                       "edges": None if edges is None else edges.tolist(), "bins": bins,
                       "omitted_parameter_indices": omitted, "all_parameters_assigned": not omitted,
                       "literal_display": display, "plot_gp_truth": plotted.tolist(),
                       "actual_simulated_truth": actual_truth.tolist()})
    return {"profile": choices["binning"], "quantile_method": choices["quantile_method"],
            "alphas": alphas.tolist(), "chains": list(range(200)), "channels": result,
            "draw_unit": "terminal_chain_by_parameter_within_bin_not_independent_biology"}


def diagnostics(ctx, bundle, prior, posterior, physical):
    """Raw support plus elementary descriptive diagnostics, no pass threshold.

    This does not invent ESS, convergence or frequentist calibration claims.
    Pointwise terminal-draw intervals are distinct from pooled distance bins.
    """
    import numpy as np
    trajectory = posterior["trajectory"]
    pointwise = cg.finite_array(np.quantile(physical, [0.05,0.5,0.95], axis=0, method="linear"), (3,1390))
    truth = cg.finite_array(bundle["flatten"](bundle["parameters"]), (1390,))
    covered = (truth >= pointwise[0]) & (truth <= pointwise[2])
    rows = []
    for coordinate in range(1390):
        ctx.checkpoint()
        values = trajectory[:,:,coordinate]
        centered = values-values.mean(axis=0, keepdims=True)
        lag_den = np.sqrt(np.sum(centered[:-1]**2, axis=0)*np.sum(centered[1:]**2, axis=0))
        lag_num = np.sum(centered[:-1]*centered[1:], axis=0)
        per_chain_lag = [None if lag_den[i] == 0 else float(lag_num[i]/lag_den[i]) for i in range(200)]
        rows.append({"parameter_index": coordinate, "chain_mean_unconstrained": values.mean(axis=0).tolist(),
                     "chain_population_variance_unconstrained": values.var(axis=0, ddof=0).tolist(),
                     "lag_one_descriptive_correlation": per_chain_lag,
                     "undefined_constant_chain_indices": [i for i in range(200) if lag_den[i] == 0],
                     "terminal_pointwise_q05_q50_q95_physical": pointwise[:,coordinate].tolist(),
                     "truth_physical": float(truth[coordinate]), "truth_within_pointwise_90": bool(covered[coordinate])})
    return {"identity": bundle["identity"], "parameter_diagnostics": rows,
            "coverage_numerator": int(covered.sum()), "coverage_denominator": 1390,
            "coverage_unit": "coordinates_in_one_synthetic_problem_not_replicated_calibration",
            "calibration_qualification": "not_established", "convergence_threshold": None,
            "prior_terminal_unconstrained": prior["terminal"].tolist(),
            "prior_initial_log_density": prior["initial_log_density"].tolist(),
            "posterior_initial_log_density": posterior["initial_log_density"].tolist(),
            "prior_accepted": prior["accepted"].tolist(), "posterior_accepted": posterior["accepted"].tolist(),
            "prior_divergent": prior["divergent"].tolist(), "posterior_divergent": posterior["divergent"].tolist(),
            "prior_gradient_norm": prior["gradient_norm"].tolist(),
            "posterior_gradient_norm": posterior["gradient_norm"].tolist(),
            "stage_transition_counts": {"prior": 2000, "posterior": 500},
            "chain_count": 200, "leapfrog_steps_per_transition": 5}


def run(ctx):
    if ctx.group != "J13" or ctx.action != "posterior_full":
        raise ValueError("fixed complete J13 action required")
    choices = cg.selected_config(ctx)
    bundle = cg.prepare(ctx, choices)
    initial, prior, posterior = sample(ctx, bundle, 500)
    physical = physical_terminal(bundle, posterior["terminal"])
    bins = distance_quantiles(ctx, bundle, physical)
    mixing = diagnostics(ctx, bundle, prior, posterior, physical)
    import numpy as np
    ctx.emit_numeric("chains_200_transitions_500", cg.finite_array(posterior["trajectory"], (500,200,1390)))
    ctx.emit_numeric("log_density", cg.finite_array(np.concatenate((prior["log_density"], posterior["log_density"])), (2500,200)))
    ctx.emit_numeric("acceptance", cg.finite_array(np.concatenate((prior["acceptance"], posterior["acceptance"])), (2500,200)))
    ctx.emit_numeric("last_samples", physical)
    ctx.emit_json("distance_bin_quantiles", bins)
    ctx.emit_json("mixing_calibration", mixing)
    ctx.record("posterior_output_extent", {"float64_trajectory_bytes": 1112000000,
        "ordering": ["posterior_transition", "chain", "parameter"],
        "prior_transitions_included_in_cost_and_diagnostics": 2000, "source_cli_default": 200,
        "executed_full_transition_count": 500, "scientific_qualification": False})
    ctx.checkpoint()
