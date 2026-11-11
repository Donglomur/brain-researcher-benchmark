"""Source-derived J10 L5PC constructor; no model construction on import.

Adapted from Deistler et al. jaxley_experiments revision
5e7a86282adb9d4603b5546ac5d8dad59aec7cc0, MIT; see upstream LICENSE.
The morphology remains an unissued runtime input, not source-code authority.
"""
def build(morphology_path):
    import numpy as np
    import jax
    import jax.numpy as jnp
    from jax import jit, vmap
    import jaxley as jx
    from jaxley.channels import Leak
    from jaxley_mech.channels.l5pc import NaTs2T, SKv3_1, M, H, SKE2, CaNernstReversal, CaPump, CaHVA, CaLVA, NaTaT, KTst, KPst
    if not jax.config.read('jax_enable_x64'):
        raise ValueError('Selected original x64 installation is required')
    bounds = {}
    gt_apical = {}
    gt_soma = {}
    gt_axon = {}

    bounds["apical_NaTs2T_gNaTs2T"] = [0, 0.04]
    gt_apical["apical_NaTs2T_gNaTs2T"] = 0.026145

    bounds["apical_SKv3_1_gSKv3_1"] = [0, 0.04]
    gt_apical["apical_SKv3_1_gSKv3_1"] = 0.004226

    bounds["apical_M_gM"] = [0, 0.001]
    gt_apical["apical_M_gM"] = 0.000143

    bounds["somatic_NaTs2T_gNaTs2T"] = [0.0, 1.0]
    gt_soma["somatic_NaTs2T_gNaTs2T"] = 0.983955

    bounds["somatic_SKv3_1_gSKv3_1"] = [0.25, 1]
    gt_soma["somatic_SKv3_1_gSKv3_1"] = 0.303472

    bounds["somatic_SKE2_gSKE2"] = [0, 0.1]
    gt_soma["somatic_SKE2_gSKE2"] = 0.008407

    bounds["somatic_CaPump_gamma"] = [0.0005,0.01]
    gt_soma["somatic_CaPump_gamma"] = 0.000609

    bounds["somatic_CaPump_decay"] = [20, 1_000]
    gt_soma["somatic_CaPump_decay"] = 210.485291

    bounds["somatic_CaHVA_gCaHVA"] = [0, 0.001]
    gt_soma["somatic_CaHVA_gCaHVA"] = 0.000994

    bounds["somatic_CaLVA_gCaLVA"] = [0, 0.01]
    gt_soma["somatic_CaLVA_gCaLVA"] = 0.000333

    bounds["axonal_NaTaT_gNaTaT"] = [0.0, 4.0]
    gt_axon["axonal_NaTaT_gNaTaT"] = 3.137968

    bounds["axonal_KPst_gKPst"] = [0.0, 1.0]
    gt_axon["axonal_KPst_gKPst"] = 0.973538

    bounds["axonal_KTst_gKTst"] = [0.0, 0.1]
    gt_axon["axonal_KTst_gKTst"] = 0.089259

    bounds["axonal_SKE2_gSKE2"] = [0.0, 0.1]
    gt_axon["axonal_SKE2_gSKE2"] = 0.007104

    bounds["axonal_SKv3_1_gSKv3_1"] = [0.0, 2.0]  # [0, 2.0]
    gt_axon["axonal_SKv3_1_gSKv3_1"] = 1.021945

    bounds["axonal_CaHVA_gCaHVA"] = [0, 0.001]  # 0.001
    gt_axon["axonal_CaHVA_gCaHVA"] = 0.00099

    bounds["axonal_CaLVA_gCaLVA"] = [0, 0.01]  # 0.01
    gt_axon["axonal_CaLVA_gCaLVA"] = 0.008752

    bounds["axonal_CaPump_gamma"] = [0.0005, 0.05]  # [0.0005,0.05]
    gt_axon["axonal_CaPump_gamma"] = 0.00291

    bounds["axonal_CaPump_decay"] = [20, 1_000]
    gt_axon["axonal_CaPump_decay"] = 287.19873

    nseg = 4
    cell = jx.read_swc(morphology_path, nseg=nseg, max_branch_len=300.0, assign_groups=True)

    soma_inds = np.unique(cell.group_nodes["soma"].branch_index).tolist()
    apical_inds = np.unique(cell.group_nodes["apical"].branch_index).tolist()
    basal_inds = np.unique(cell.group_nodes["basal"].branch_index).tolist()
    axon_inds = np.unique(cell.group_nodes["axon"].branch_index).tolist()

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

    for key in gt_apical.keys():
        cell.apical.set(key, gt_apical[key])

    for key in gt_soma.keys():
        cell.soma.set(key, gt_soma[key])

    for key in gt_axon.keys():
        cell.axon.set(key, gt_axon[key])

    def set_all_branches(params):
        """
        Args:
            params: Should have shape `(10,)`.
        """
        counter = 0
        pstate = None

        # Apical.
        for key in gt_apical.keys():
            pstate = cell.apical.data_set(key, params[counter], pstate)
            counter += 1
        
        # Soma.
        for key in gt_soma.keys():
            pstate = cell.soma.data_set(key, params[counter], pstate)
            counter += 1

        # Axon.
        for key in gt_axon.keys():
            pstate = cell.axon.data_set(key, params[counter], pstate)
            counter += 1

        assert counter == 19
        return pstate

    dt = 0.025
    t_max = 100.0
    time_vec = np.arange(0, t_max+2*dt, dt)

    cell.delete_stimuli()
    cell.delete_recordings()

    i_delay = 10.0
    i_dur = 80.0
    i_amp = 3.0
    current = jx.step_current(i_delay, i_dur, i_amp, dt, t_max)
    cell.branch(soma_inds[0]).loc(0.0).stimulate(current)  # Stimulate soma
    cell.branch(soma_inds[0]).loc(0.0).record()

    cell.set("v", -65.0)
    cell.init_states()

    num_cp = 2
    cp = [int(np.ceil((100 * 40)**(1/num_cp))) for _ in range(num_cp)]

    def simulate(params):
        parameters = set_all_branches(params)
        return jx.integrate(cell, param_state=parameters, checkpoint_lengths=cp)

    jitted_sim = jit(simulate)
    vmapped_sim = jit(vmap(simulate, in_axes=(0,)))

    def sim_gt():
        return jx.integrate(cell)

    jitted_sim_gt = jit(sim_gt)
    order=tuple(bounds)
    if len(order)!=19:raise ValueError('Original nineteen parameters required')
    true_values=jnp.asarray([({**gt_apical,**gt_soma,**gt_axon})[k]for k in order])
    return dict(cell=cell, bounds=bounds, parameter_order=order, true_values=true_values,
                simulate=jitted_sim, simulate_many=vmapped_sim, simulate_ground_truth=jitted_sim_gt,
                time=time_vec, dt=dt, checkpoint_lengths=cp)
