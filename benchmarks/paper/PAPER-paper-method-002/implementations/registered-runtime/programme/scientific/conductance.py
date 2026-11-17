"""J12 concrete source producers. No numerical work or imports on module import.

Published constructor adapted from mackelab/jaxley_experiments at
5e7a86282adb9d4603b5546ac5d8dad59aec7cc0, MIT; see LICENSE and SOURCE_CELL_MAP.
Actual execution requires main-owned JobContext and all original native gates.
"""
bounds = {'apical_NaTs2T_gNaTs2T': [0, 0.04], 'apical_SKv3_1_gSKv3_1': [0, 0.04], 'apical_M_gM': [0, 0.001], 'somatic_NaTs2T_gNaTs2T': [0.0, 1.0], 'somatic_SKv3_1_gSKv3_1': [0.25, 1], 'somatic_SKE2_gSKE2': [0, 0.1], 'somatic_CaPump_gamma': [0.0005, 0.01], 'somatic_CaPump_decay': [20, 1000], 'somatic_CaHVA_gCaHVA': [0, 0.001], 'somatic_CaLVA_gCaLVA': [0, 0.01], 'axonal_NaTaT_gNaTaT': [0.0, 4.0], 'axonal_KPst_gKPst': [0.0, 1.0], 'axonal_KTst_gKTst': [0.0, 0.1], 'axonal_SKE2_gSKE2': [0.0, 0.1], 'axonal_SKv3_1_gSKv3_1': [0.0, 2.0], 'axonal_CaHVA_gCaHVA': [0, 0.001], 'axonal_CaLVA_gCaLVA': [0, 0.01], 'axonal_CaPump_gamma': [0.0005, 0.05], 'axonal_CaPump_decay': [20, 1000]}
gt_apical = {'apical_NaTs2T_gNaTs2T': 0.026145, 'apical_SKv3_1_gSKv3_1': 0.004226, 'apical_M_gM': 0.000143}
gt_soma = {'somatic_NaTs2T_gNaTs2T': 0.983955, 'somatic_SKv3_1_gSKv3_1': 0.303472, 'somatic_SKE2_gSKE2': 0.008407, 'somatic_CaPump_gamma': 0.000609, 'somatic_CaPump_decay': 210.485291, 'somatic_CaHVA_gCaHVA': 0.000994, 'somatic_CaLVA_gCaLVA': 0.000333}
gt_axon = {'axonal_NaTaT_gNaTaT': 3.137968, 'axonal_KPst_gKPst': 0.973538, 'axonal_KTst_gKTst': 0.089259, 'axonal_SKE2_gSKE2': 0.007104, 'axonal_SKv3_1_gSKv3_1': 1.021945, 'axonal_CaHVA_gCaHVA': 0.00099, 'axonal_CaLVA_gCaLVA': 0.008752, 'axonal_CaPump_gamma': 0.00291, 'axonal_CaPump_decay': 287.19873}

def build_cell(ctx, choices):
    import numpy as np
    import jax
    import jaxley as jx
    from jaxley.channels import Leak
    from jaxley_mech.channels.l5pc import NaTs2T, SKv3_1, M, H, SKE2, CaNernstReversal, CaPump, CaHVA, CaLVA, NaTaT, KTst, KPst
    if not jax.config.x64_enabled:
        raise ValueError("selected float64 JAX configuration required before construction")
    ctx.checkpoint()
    evals = np.linspace(0, 1200, 100)
    kernel = np.empty((100, 100))
    for i, x in enumerate(evals):
        for j, y in enumerate(evals):
            kernel[i, j] = np.exp(-((x-y)**2) / 400**2)
    def sample_profile():
        draw = np.random.multivariate_normal(np.zeros(100), kernel)
        return jax.scipy.stats.norm.cdf(draw) * 0.8 + 0.1
    np.random.seed(2)
    gt_profiles_apical = {key: sample_profile() for key in gt_apical}
    np.random.seed(22)
    gt_profiles_axonal = {key: sample_profile() for key in list(gt_axon)[:7]}
    nseg = 4
    cell = jx.read_swc(ctx.input_path("morphology"), nseg=nseg, max_branch_len=300.0, assign_groups=True)



    soma_inds = np.unique(cell.group_nodes["soma"].branch_index).tolist()
    apical_inds = np.unique(cell.group_nodes["apical"].branch_index).tolist()
    basal_inds = np.unique(cell.group_nodes["basal"].branch_index).tolist()
    axonal_inds = np.unique(cell.group_nodes["axon"].branch_index).tolist()

    ########## APICAL ##########
    cell.apical.set("capacitance", 2.0)
    cell.apical.insert(NaTs2T().change_name("apical_NaTs2T"))
    cell.apical.insert(SKv3_1().change_name("apical_SKv3_1"))
    cell.apical.insert(M().change_name("apical_M"))
    cell.apical.insert(H().change_name("apical_H"))
    for b in apical_inds:
        for c in [0.125, 0.375, 0.625, 0.875]:
            distance = cell.branch(b).loc(c).distance(cell.branch(0).loc(0.0))
            cond = (-0.8696 + 2.087* np.exp(distance*0.0031)) * 8e-5
            cell.branch(b).loc(c).set("apical_H_gH", cond)

    ########## SOMA ##########
    cell.soma.insert(NaTs2T().change_name("somatic_NaTs2T"))
    cell.soma.insert(SKv3_1().change_name("somatic_SKv3_1"))
    cell.soma.insert(SKE2().change_name("somatic_SKE2"))
    ca_dynamics = CaNernstReversal()
    ca_dynamics.channel_constants["T"] = 307.15
    cell.soma.insert(ca_dynamics)
    cell.soma.insert(CaPump().change_name("somatic_CaPump"))
    cell.soma.insert(CaHVA().change_name("somatic_CaHVA"))
    cell.soma.insert(CaLVA().change_name("somatic_CaLVA"))
    cell.soma.set("CaCon_i", 5e-05)
    cell.soma.set("CaCon_e", 2.0)

    ########## BASAL ##########
    cell.basal.insert(H().change_name("basal_H"))
    cell.basal.set("basal_H_gH", 8e-5)

    # ########## AXON ##########
    cell.insert(CaNernstReversal())
    cell.set("CaCon_i", 5e-05)
    cell.set("CaCon_e", 2.0)

    cell.axon.insert(NaTaT().change_name("axonal_NaTaT"))
    cell.axon.set("axonal_NaTaT_gNaTaT", 3.137968)

    cell.axon.insert(KTst().change_name("axonal_KTst"))
    cell.axon.set("axonal_KTst_gKTst", 0.089259)

    cell.axon.insert(CaPump().change_name("axonal_CaPump"))
    cell.axon.set("axonal_CaPump_gamma", 0.00291)
    cell.axon.set("axonal_CaPump_decay", 287.19873)

    cell.axon.insert(SKE2().change_name("axonal_SKE2"))
    cell.axon.set("axonal_SKE2_gSKE2", 0.007104)

    cell.axon.insert(CaHVA().change_name("axonal_CaHVA"))
    cell.axon.set("axonal_CaHVA_gCaHVA", 0.00099)

    cell.axon.insert(KPst().change_name("axonal_KPst"))
    cell.axon.set("axonal_KPst_gKPst", 0.973538)

    cell.axon.insert(SKv3_1().change_name("axonal_SKv3_1"))
    cell.axon.set("axonal_SKv3_1_gSKv3_1", 1.021945)

    cell.axon.insert(CaLVA().change_name("axonal_CaLVA"))
    cell.axon.set("axonal_CaLVA_gCaLVA", 0.008752)


    ########## WHOLE CELL  ##########
    cell.insert(Leak())
    cell.set("Leak_gLeak", 3e-05)
    cell.set("Leak_eLeak", -75.0)

    cell.set("axial_resistivity", 100.0)
    cell.set("eNa", 50.0)
    cell.set("eK", -85.0)
    cell.set("v", -65.0)


    # Apical.
    for b in apical_inds:
        distance = cell.branch(b).loc(0.0).distance(cell.branch(0).loc(0.0))
        for key, item in gt_profiles_apical.items():
            cond = np.interp(distance, evals, item)
            cell.branch(b).set(key, cond * bounds[key][1])

    for key in gt_soma.keys():
        cell.soma.set(key, gt_soma[key])

    for b in axonal_inds:
        distance = cell.branch(b).loc(0.0).distance(cell.branch(0).loc(0.0))
        for key, item in gt_profiles_axonal.items():
            cond = np.interp(distance, evals, item)
            cell.branch(b).set(key, cond * bounds[key][1])

    if choices["axon_truth"] == "source_constants_after_gp":
        for key in gt_axon.keys():
            cell.axon.set(key, gt_axon[key])
    else:
        for key in ("axonal_CaPump_gamma", "axonal_CaPump_decay"):
            cell.axon.set(key, gt_axon[key])
        
        
    cell.delete_trainables()

    for key in gt_profiles_apical.keys():
        cell.branch(apical_inds).make_trainable(key)

    for key in gt_soma.keys():
        cell.soma.make_trainable(key)

    for key in gt_profiles_axonal.keys():
        cell.branch(axonal_inds).make_trainable(key)

    cell.axon.make_trainable("axonal_CaPump_gamma")
    cell.axon.make_trainable("axonal_CaPump_decay")

    parameters = cell.get_parameters()
    
    repeats = {
        "apical_NaTs2T_gNaTs2T": len(apical_inds),
        "apical_SKv3_1_gSKv3_1": len(apical_inds),
        "apical_M_gM": len(apical_inds), 
        "somatic_NaTs2T_gNaTs2T": 1,
        "somatic_SKv3_1_gSKv3_1": 1,
        "somatic_SKE2_gSKE2": 1,
        "somatic_CaHVA_gCaHVA": 1,
        "somatic_CaLVA_gCaLVA": 1,
        "somatic_CaPump_gamma": 1,
        "somatic_CaPump_decay": 1,
        "axonal_NaTaT_gNaTaT": len(axonal_inds),
        "axonal_KPst_gKPst": len(axonal_inds),
        "axonal_KTst_gKTst": len(axonal_inds),
        "axonal_SKE2_gSKE2": len(axonal_inds),
        "axonal_SKv3_1_gSKv3_1": len(axonal_inds),
        "axonal_CaHVA_gCaHVA": len(axonal_inds),
        "axonal_CaLVA_gCaLVA": len(axonal_inds),
        "axonal_CaPump_gamma": 1,
        "axonal_CaPump_decay": 1,
    }
    num_params = sum(list(repeats.values()))
    if num_params != 1390:
        raise ValueError("complete 1390-parameter morphology required")
    
    dt = 0.025
    t_max = 5.0
    time_vec = np.arange(0, t_max+2*dt, dt)

    cell.delete_stimuli()
    cell.delete_recordings()

    i_delay = 0.0
    i_dur = choices["stimulus_duration_ms"]
    i_amp = 3.0
    current = jx.step_current(i_delay, i_dur, i_amp, dt, t_max)
    cell.branch(soma_inds[0]).loc(0.0).stimulate(current)  # Stimulate soma
    cell[range(0,339,1),0].record()

    cell.set("v", -70.0)
    cell.init_states()
    
    groups = {"soma": soma_inds, "apical": apical_inds, "basal": basal_inds, "axon": axonal_inds}
    return {"cell": cell, "parameters": parameters, "groups": groups,
            "profiles": {"apical": gt_profiles_apical, "axon": gt_profiles_axonal},
            "gp_grid": evals, "choices": choices}

PRODUCTS = ("whole_branch_voltage", "parameters_1390", "regularizer", "loss_trajectory", "GA_comparison")
SOURCE_CHOICES = {
    "axon_truth": "source_constants_after_gp", "stimulus_duration_ms": 3.0,
    "gd_max_iterations": 500, "gd_stop_below": 0.5, "gd_gradient_normalization": "source_power_0.8",
    "ga_assignment": "source_discard_pump_returns", "loss_reduction": "mean",
    "regularizer_coordinates": "unconstrained", "gd_regularizer_weight": 0.001,
    "posterior_regularizer_weight": 1.0, "likelihood_scale": 0.001,
    "prior_measure": "uniform_physical_with_transform_jacobian",
    "binning": "literal_digitize_diagnostic", "quantile_method": "linear_type7",
}


def selected_config(ctx):
    """Read only compiler-owned explicit method choices, before input access.

    A selection ID is provenance, never an authority issuer. The main compiler
    must pin the actual selection; this module cannot authorize alternatives.
    """
    import math
    c = ctx.config
    required = {"profile", "selection_id", "scientific_choices", "posterior_seed", "identity_input"}
    if type(c) is not dict or set(c) != required:
        raise ValueError("complete exact family configuration required")
    if type(c["selection_id"]) is not str or not c["selection_id"]:
        raise ValueError("explicit selected method provenance required")
    if type(c["posterior_seed"]) is not int or not 0 <= c["posterior_seed"] < 2**32:
        raise ValueError("explicit uint32 posterior seed required")
    if c["identity_input"] != "conductance_identity":
        raise ValueError("fixed parameter identity input required")
    choices = c["scientific_choices"]
    if type(choices) is not dict or set(choices) != set(SOURCE_CHOICES):
        raise ValueError("every scientific choice must be bound")
    for key, source_value in SOURCE_CHOICES.items():
        value = choices[key]
        if isinstance(source_value, str):
            if type(value) is not str:
                raise ValueError("scientific choice must be a string: " + key)
        elif key == "gd_max_iterations":
            if type(value) is not int:
                raise ValueError("exact integer iteration count required")
        elif key == "gd_stop_below" and value is None:
            pass
        elif type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("finite nonboolean scientific number required: " + key)
    if c["profile"] == "literal_source_explicit500":
        if choices != SOURCE_CHOICES:
            raise ValueError("literal source choices cannot be overwritten")
    elif c["profile"] == "fully_bound_alternative":
        allowed = {
            "axon_truth": {"source_constants_after_gp", "all_ten_gp_profiles"},
            "stimulus_duration_ms": {3.0, 5.0}, "gd_max_iterations": {500},
            "gd_stop_below": {None, 0.5}, "gd_gradient_normalization": {"source_power_0.8"},
            "ga_assignment": {"source_discard_pump_returns", "assign_all_parameters"},
            "loss_reduction": {"mean", "sum"}, "regularizer_coordinates": {"unconstrained", "physical"},
            "prior_measure": {"uniform_physical_with_transform_jacobian"},
            "binning": {"literal_digitize_diagnostic", "explicit_complete_edges"},
            "quantile_method": {"linear_type7"},
        }
        for key, values in allowed.items():
            if choices[key] not in values or type(choices[key]) is bool:
                raise ValueError("unsupported explicit scientific choice: " + key)
        for key in ("gd_regularizer_weight", "posterior_regularizer_weight", "likelihood_scale"):
            value = choices[key]
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError("positive finite selected weight/scale required")
    else:
        raise ValueError("unselected profile; no guessed paper defaults")
    return dict(choices)


def parameter_identity(bundle):
    """Derive all ordered coordinates from the actual constructed parameter tree."""
    import numpy as np
    from jax.flatten_util import ravel_pytree
    cell, groups = bundle["cell"], bundle["groups"]
    keys = list(bounds)
    params = bundle["parameters"]
    if len(params) != len(keys) or sorted(set(sum(groups.values(), []))) != list(range(339)):
        raise ValueError("complete source branch support required")
    rows, offset = [], 0
    for position, (key, leaf) in enumerate(zip(keys, params)):
        if set(leaf) != {key}:
            raise ValueError("native parameter order differs from selected source")
        if key.startswith("apical_"):
            owner, branches = "apical", groups["apical"]
        elif key.startswith("axonal_") and key not in list(gt_axon)[-2:]:
            owner, branches = "axon", groups["axon"]
        elif key.startswith("somatic_"):
            owner, branches = "soma", [None]
        else:
            owner, branches = "axon_shared", [None]
        if tuple(leaf[key].shape) != (len(branches),):
            raise ValueError("parameter leaf support changed")
        for local, branch in enumerate(branches):
            rows.append({"index": offset, "leaf": position, "local_index": local,
                         "key": key, "owner": owner, "branch": branch,
                         "lower": bounds[key][0], "upper": bounds[key][1]})
            offset += 1
    flat, unflatten = ravel_pytree(params)
    if offset != 1390 or tuple(flat.shape) != (1390,):
        raise ValueError("full 1390 coordinates required")
    parents = np.asarray(cell.comb_parents).astype(int).tolist()
    if len(parents) != 339:
        raise ValueError("full branch parent roster required")
    distances = {group: [float(cell.branch(b).loc(0.0).distance(cell.branch(0).loc(0.0)))
                         for b in groups[group]] for group in ("apical", "axon")}
    identity = {"groups": groups, "parameters": rows, "parents": parents,
                "recorded_branches": list(range(339)), "recorded_compartment": 0,
                "distance_um": distances, "fit_time_indices": list(range(40, 200, 5)),
                "delta_t_ms": 0.025, "t_max_ms": 5.0}
    return identity, flat, unflatten


def prepare(ctx, choices):
    import numpy as np
    import jax, jax.numpy as jnp, jaxley as jx
    from jax.flatten_util import ravel_pytree
    bundle = build_cell(ctx, choices)
    identity, flat, unflatten = parameter_identity(bundle)
    expected = ctx.read_json("conductance_identity")
    # Expected identity is independently pinned by the main compiler; numerical
    # distances are validated separately against its explicit tolerance.
    if type(expected) is not dict or set(expected) != {"identity", "distance_tolerance_um", "complete_bin_edges"}:
        raise ValueError("complete identity and explicit bin selection required")
    tolerance = expected["distance_tolerance_um"]
    if type(tolerance) not in (int, float) or not np.isfinite(tolerance) or tolerance < 0:
        raise ValueError("invalid distance tolerance")
    other = dict(expected["identity"])
    wanted_distances = other.pop("distance_um")
    actual = dict(identity); actual.pop("distance_um")
    if other != actual or set(wanted_distances) != {"apical", "axon"}:
        raise ValueError("actual source identities differ from complete selected roster")
    for group in wanted_distances:
        wanted = np.asarray(wanted_distances[group], dtype=float)
        observed = np.asarray(identity["distance_um"][group], dtype=float)
        if wanted.shape != observed.shape or not np.all(np.isfinite(wanted)) or not np.all(np.abs(wanted-observed) <= tolerance):
            raise ValueError("actual branch distances differ from selected support")
    transform = jx.ParamTransform(lowers={k: v[0] for k,v in bounds.items()},
                                 uppers={k: v[1] for k,v in bounds.items()})
    cell = bundle["cell"]
    # The source GD notebook integrates directly; posterior utility uses the
    # same fixed checkpoint split. No solver substitution is made here.
    simulate = jax.jit(lambda p: jx.integrate(cell, params=p))
    simulate_posterior = jax.jit(lambda p: jx.integrate(cell, params=p, checkpoint_lengths=[101, 2]))
    truth = jax.jit(lambda: jx.integrate(cell))()
    if truth.ndim != 2 or truth.shape[0] != 339 or truth.shape[1] < 200:
        raise ValueError("complete branch/time truth unavailable")
    pairs = {}
    for group in ("apical", "axon"):
        branches = bundle["groups"][group]; lookup = {b: i for i,b in enumerate(branches)}
        pairs[group] = [(i, lookup[identity["parents"][b]]) for i,b in enumerate(branches)
                        if identity["parents"][b] in lookup]
    def regularizer(tree):
        total = jnp.asarray(0.0)
        for leaf in tree:
            key = next(iter(leaf))
            group = "apical" if key in gt_apical else "axon" if key in list(gt_axon)[:7] else None
            if group is not None:
                for child, parent in pairs[group]:
                    total = total + (leaf[key][child] - leaf[key][parent])**2
        return total
    def penalty(unconstrained):
        return regularizer(transform.forward(unconstrained) if choices["regularizer_coordinates"] == "physical" else unconstrained)
    def voltage_loss(voltage):
        errors = jnp.abs(voltage[:, 40:200:5] - truth[:, 40:200:5])
        return jnp.mean(errors) if choices["loss_reduction"] == "mean" else jnp.sum(errors)
    bundle.update(identity=identity, expected=expected, truth=truth, transform=transform,
                  unflatten=unflatten, flatten=lambda p: ravel_pytree(p)[0],
                  simulate=simulate, simulate_posterior=simulate_posterior,
                  penalty=penalty, voltage_loss=voltage_loss)
    ctx.record("parameter_identity", identity)
    ctx.record("method_choices", {"profile": ctx.config["profile"], "selection_id": ctx.config["selection_id"], "choices": choices})
    ctx.checkpoint()
    return bundle


def finite_array(value, shape=None):
    import numpy as np
    array = np.asarray(value)
    if shape is not None and array.shape != tuple(shape):
        raise ValueError("incomplete scientific product shape")
    if array.dtype.kind not in "fiu" or not np.all(np.isfinite(array)):
        raise ValueError("nonfinite scientific product")
    return array


def gradient_descent(ctx, bundle):
    import numpy as np
    import jax, jax.numpy as jnp, optax
    c = bundle["choices"]; transform = bundle["transform"]
    initial = transform.inverse(bundle["parameters"])
    def objective(p):
        return bundle["voltage_loss"](bundle["simulate"](transform.forward(p))) + c["gd_regularizer_weight"]*bundle["penalty"](p)
    loss_grad = jax.jit(jax.value_and_grad(objective))
    # Source notebook cells27 and29 perform a loss and gradient evaluation at
    # the truth-derived unconstrained start before the seeded optimization.
    warm_loss = float(objective(initial))
    warm_grad_loss, warm_gradient = loss_grad(initial)
    warm_norm = float(jnp.sqrt(sum(jnp.sum(g*g) for g in jax.tree_util.tree_leaves(warm_gradient))))
    finite_array([warm_loss, float(warm_grad_loss), warm_norm])
    np.random.seed(1)
    params = jax.tree_util.tree_map(lambda p: jnp.asarray(2*np.random.randn(*p.shape)), initial)
    initial_flat = bundle["flatten"](params)
    optimizer = optax.sgd(learning_rate=0.1, momentum=0.9)
    state = optimizer.init(params)
    best, best_loss = params, 100.0
    best_written = False
    history, updates = [], 0
    for iteration in range(c["gd_max_iterations"]):
        ctx.checkpoint()
        loss, grads = loss_grad(params)
        loss_value = float(loss)
        if not np.isfinite(loss_value):
            raise ValueError("nonfinite GD loss")
        if loss_value < best_loss:
            best, best_loss = params, loss_value
            best_written = True
        norm = jnp.sqrt(sum(jnp.sum(g*g) for g in jax.tree_util.tree_leaves(grads)))
        norm_value = float(norm)
        if not np.isfinite(norm_value):
            raise ValueError("nonfinite GD gradient norm")
        row = {"iteration": iteration, "loss_before_update": loss_value,
               "gradient_norm": norm_value, "corrected_gradient_norm": None,
               "update_norm": None, "updated": False}
        history.append(row)
        if norm_value > 0:
            normalized = jax.tree_util.tree_map(lambda g: g/norm**0.8, grads)
            row["corrected_gradient_norm"] = float(jnp.sqrt(sum(jnp.sum(g*g) for g in jax.tree_util.tree_leaves(normalized))))
        if c["gd_stop_below"] is not None and loss_value < c["gd_stop_below"]:
            break
        # The source divides by zero at this boundary. Refuse explicitly rather
        # than inventing a gradient update or reporting numerical success.
        if norm_value == 0:
            raise ValueError("undefined source zero-gradient normalization")
        changes, state = optimizer.update(normalized, state)
        row["update_norm"] = float(jnp.sqrt(sum(jnp.sum(g*g) for g in jax.tree_util.tree_leaves(changes))))
        params = optax.apply_updates(params, changes)
        row["updated"] = True; updates += 1
    if not best_written:
        # The source would reopen an absent or stale opt_params.pkl. This
        # reconstruction refuses that unsupported external-state dependency.
        raise ValueError("source best-parameter checkpoint was never produced")
    best_physical = transform.forward(best)
    final_physical = transform.forward(params)
    return {"best_tree": best_physical, "best_unconstrained": best,
            "best": finite_array(bundle["flatten"](best_physical), (1390,)),
            "final": finite_array(bundle["flatten"](final_physical), (1390,)),
            "initial_unconstrained": finite_array(initial_flat, (1390,)),
            "voltage": finite_array(bundle["simulate"](best_physical), bundle["truth"].shape),
            "history": history, "updates": updates, "source_best_threshold": 100.0,
            "best_loss_recorded": best_loss,
            "regularizer": float(bundle["penalty"](best)),
            "warmup": {"loss_evaluations": 1, "gradient_evaluations": 1,
                       "loss": warm_loss, "gradient_loss": float(warm_grad_loss), "gradient_norm": warm_norm}}


def genetic_algorithm(ctx, bundle):
    import numpy as np
    import jax, jax.numpy as jnp, jaxley as jx
    import bluepyopt as bpopt
    from bluepyopt.parameters import Parameter
    c, cell, groups = bundle["choices"], bundle["cell"], bundle["groups"]
    log = []; candidate_rows = []; batch_minima = []
    def parameter_state(flat):
        state = None; counter = 0
        for key in gt_apical:
            for branch in groups["apical"]:
                state = cell.branch(branch).data_set(key, flat[counter], state); counter += 1
        for key in gt_soma:
            state = cell.soma.data_set(key, flat[counter], state); counter += 1
        for key in list(gt_axon)[:7]:
            for branch in groups["axon"]:
                state = cell.branch(branch).data_set(key, flat[counter], state); counter += 1
        for key in list(gt_axon)[-2:]:
            returned = cell.axon.data_set(key, flat[counter], state)
            if c["ga_assignment"] == "assign_all_parameters":
                state = returned
            counter += 1
        if counter != 1390:
            raise ValueError("GA omitted coordinates")
        return state
    simulate_ga = jax.jit(lambda flat: jx.integrate(cell, param_state=parameter_state(flat)))
    batch_simulate = jax.jit(jax.vmap(simulate_ga))
    evaluate_penalty = jax.jit(jax.vmap(lambda flat: bundle["penalty"](bundle["transform"].inverse(bundle["unflatten"](flat)))))
    losses_from_v = jax.jit(jax.vmap(bundle["voltage_loss"]))
    class Evaluator(bpopt.evaluators.Evaluator):
        def __init__(self, parameters):
            super().__init__(objectives=["loss"], params=parameters)
        def init_simulator_and_evaluate_with_lists(self, param_list):
            ctx.checkpoint()
            values = finite_array(param_list)
            if values.ndim != 2 or values.shape[1] != 1390 or not len(values):
                raise ValueError("complete GA batch required")
            voltage = batch_simulate(jnp.asarray(values))
            losses = losses_from_v(voltage)
            penalties = evaluate_penalty(jnp.asarray(values))
            total = finite_array(losses + c["gd_regularizer_weight"]*penalties, (len(values),))
            batch_minima.append(float(np.min(total)))
            for i in range(len(values)):
                candidate_rows.append(values[i].tolist())
                log.append({"evaluation": len(log), "batch": batch_counter[0],
                            "loss": float(total[i]), "data_loss": float(losses[i]),
                            "regularizer": float(penalties[i])})
            batch_counter[0] += 1
            return total[:, None].tolist()
    batch_counter = [0]
    parameters = [Parameter(row["key"]+"_"+str(row["local_index"]), bounds=(row["lower"], row["upper"]))
                  for row in bundle["identity"]["parameters"]]
    evaluator = Evaluator(parameters)
    def batch_map(evaluate_with_lists, candidates):
        # Exact source batch dispatch. BluePyOpt version and this callback
        # contract must be qualified; no replacement evolutionary algorithm.
        return evaluate_with_lists(candidates)
    optimizer = bpopt.deapext.optimisations.IBEADEAPOptimisation(
        evaluator, offspring_size=10, map_function=batch_map, seed=6,
        eta=10, mutpb=1.0, cxpb=1.0)
    population, hall, logbook, history = optimizer.run(max_ngen=500)
    if not log or not hall:
        raise ValueError("complete GA evaluation history/Hall of Fame required")
    best = finite_array(list(hall[0]), (1390,))
    final_population = finite_array([list(p) for p in population])
    if final_population.ndim != 2 or final_population.shape[1] != 1390:
        raise ValueError("GA terminal population incomplete")
    best_tree = bundle["unflatten"](jnp.asarray(best))
    best_unconstrained = bundle["transform"].inverse(best_tree)
    return {"best": best, "voltage": finite_array(simulate_ga(jnp.asarray(best)), bundle["truth"].shape),
            "regularizer": float(bundle["penalty"](best_unconstrained)),
            "evaluations": log, "all_evaluated_parameters": candidate_rows,
            "source_batch_minimum_losses": batch_minima,
            "final_population": final_population.tolist(), "hall_of_fame": [finite_array(list(p), (1390,)).tolist() for p in hall],
            "generations": [dict(row) for row in logbook],
            "genealogy_tree": {str(k): list(v) for k,v in history.genealogy_tree.items()},
            "genealogy_parameters": {str(k): finite_array(list(v), (1390,)).tolist() for k,v in history.genealogy_history.items()},
            "assignment": c["ga_assignment"], "evaluation_count": len(log), "batch_count": batch_counter[0]}


def prediction_all_compartments(ctx, bundle, physical):
    """Notebook cells35–37; distinct from the 339-record fitting observation."""
    import jaxley as jx
    cell = bundle["cell"]
    ctx.checkpoint()
    cell.delete_stimuli(); cell.delete_recordings()
    current = jx.step_current(0.0, bundle["choices"]["stimulus_duration_ms"], 3.0, 0.025, 5.0)
    cell.branch(bundle["groups"]["soma"][0]).loc(0.0).stimulate(current)
    cell.record(); cell.set("v", -70.0); cell.init_states()
    native_ids = [int(x) for x in cell.nodes["global_comp_index"].tolist()]
    if native_ids != list(range(339*4)):
        raise ValueError("full source all-compartment recording order unavailable")
    voltage = finite_array(jx.integrate(cell, params=physical), (339*4, bundle["truth"].shape[1]))
    return {"global_compartment_ids": native_ids, "voltage_mv": voltage.tolist(),
            "source": "02_voltage_imaging.ipynb cells35–37", "not_the_fitting_observation": True}


def json_ready(value):
    """Convert concrete native scalar logs, rejecting nonfinite/opaque values."""
    import numpy as np
    import math
    if isinstance(value, np.generic):
        value = value.item()
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("nonfinite scientific log")
        return value
    if type(value) in (list, tuple):
        return [json_ready(v) for v in value]
    if type(value) is dict:
        if any(type(k) is not str for k in value):
            raise ValueError("scientific log keys must be strings")
        return {k: json_ready(v) for k,v in value.items()}
    raise ValueError("opaque scientific log value")


def run(ctx):
    if ctx.group != "J12" or ctx.action != "conductance_full":
        raise ValueError("fixed complete J12 action required")
    choices = selected_config(ctx)
    bundle = prepare(ctx, choices)
    gd = gradient_descent(ctx, bundle)
    ga = genetic_algorithm(ctx, bundle)
    all_compartments = prediction_all_compartments(ctx, bundle, gd["best_tree"])
    import numpy as np
    voltage = finite_array(np.stack((bundle["truth"], gd["voltage"], ga["voltage"])))
    physical = finite_array(np.stack((bundle["flatten"](bundle["parameters"]), gd["best"], ga["best"])), (3,1390))
    regularizers = finite_array([float(bundle["penalty"](bundle["transform"].inverse(bundle["parameters"]))), gd["regularizer"], ga["regularizer"]], (3,))
    ctx.emit_numeric("whole_branch_voltage", voltage)
    ctx.emit_numeric("parameters_1390", physical)
    ctx.emit_numeric("regularizer", regularizers)
    ctx.emit_json("loss_trajectory", {"identity": bundle["identity"], "methods": ["truth", "GD", "GA"],
        "profile": ctx.config["profile"], "choices": choices, "gd": {
            "history": gd["history"], "updates": gd["updates"],
            "initial_unconstrained": gd["initial_unconstrained"].tolist(), "final_physical": gd["final"].tolist(),
            "source_best_threshold": gd["source_best_threshold"], "best_loss_recorded": gd["best_loss_recorded"],
            "warmup": gd["warmup"]}, "postfit_all_compartments": all_compartments,
        "gp_grid_um": bundle["gp_grid"].tolist(),
        "sampled_gp_profiles": {group:{key:finite_array(value).tolist() for key,value in profiles.items()}
                                for group,profiles in bundle["profiles"].items()}})
    ctx.emit_json("GA_comparison", json_ready({k:v for k,v in ga.items() if k not in ("best", "voltage")}))
    ctx.checkpoint()
