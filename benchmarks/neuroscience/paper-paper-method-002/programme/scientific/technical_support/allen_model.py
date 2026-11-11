"""Source-derived closed Allen cell factory, safe explicit morphology path and amplitude."""
def build(specimen,swc_path,amplitude):
    import numpy as np
    import jax
    import jax.numpy as jnp
    import jaxley as jx
    from jaxley.channels import Leak
    from .allen_compat import (NaTs2T,SKv3_1,M,H,SKE2,CaNernstReversal,CaPump,CaHVA,CaLVA,NaTaT,KPst,KTst)
    from math import log10
    from typing import Callable,Tuple
    from jax import Array
    setup={
        "485574832":(155,-85.6,6.0,-88.0),
        "488683425":(195,-83.15625,2.0,-88.0),
        "480353286":(170,-88.90625,6.0,-95.0),
        "473601979":(195,-89.06251,2.5,-95.0),
    }
    if specimen not in setup:raise ValueError("closed Allen specimen")
    rotation,v_init,capacitance,eleak=setup[specimen]
    swc_fname=swc_path
    dt=0.025;i_delay=50.0;i_amp=amplitude;gleak=1e-4
    def build_cell(nseg=4):
        cell = jx.read_swc(swc_fname, ncomp=nseg, max_branch_len=300.0, assign_groups=True)
        cell.rotate(rotation)
        soma_inds = np.unique(cell.soma.nodes.global_branch_index).tolist()
        apical_inds = np.unique(cell.apical.nodes.global_branch_index).tolist()
    
        ########## APICAL ##########
        cell.insert(Leak())
        cell.apical.insert(NaTs2T().change_name("apical_NaTs2T"))
        cell.apical.insert(SKv3_1().change_name("apical_SKv3_1"))
        cell.apical.insert(M().change_name("apical_M"))
        cell.apical.insert(H().change_name("apical_H"))
        for b in apical_inds:
            for c in range(4):
                distance = (
                    cell.branch(b)
                    .comp(c)
                    .distance(cell.branch(soma_inds[0]).loc(0.5))
                )
                cond = (-0.8696 + 2.087 * np.exp(distance * 0.0031)) * 8e-5
                cell.branch(b).comp(c).set("apical_H_gH", cond)
    
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
        cell.axon.insert(NaTaT().change_name("axonal_NaTaT"))
        cell.axon.insert(KPst().change_name("axonal_KPst"))
        cell.axon.insert(KTst().change_name("axonal_KTst"))
        cell.axon.insert(SKE2().change_name("axonal_SKE2"))
        cell.axon.insert(SKv3_1().change_name("axonal_SKv3_1"))
    
        ca_dynamics_axonal = CaNernstReversal()
        ca_dynamics_axonal.channel_constants["T"] = 307.15
        cell.axon.insert(ca_dynamics)
        cell.set("CaCon_i", 5e-05)
        cell.set("CaCon_e", 2.0)
        cell.axon.insert(CaHVA().change_name("axonal_CaHVA"))
        cell.axon.insert(CaLVA().change_name("axonal_CaLVA"))
        cell.axon.insert(CaPump().change_name("axonal_CaPump"))
    
        ########## WHOLE CELL  ##########
        cell.set("axial_resistivity", 100.0)
        cell.set("capacitance", capacitance)
        cell.set("Leak_eLeak", eleak)
        cell.set("Leak_gLeak", gleak)
        return cell

    def setup_simulator(cell, t_max=200):
        i_dur = 1000.0
        time_vec = np.arange(0, t_max+2*dt, dt)
        levels = 3
        checkpoints = [int(np.ceil(len(time_vec)**(1/levels)).item()) for _ in range(levels)]
        
        # Build cell with approriate stimuli.
        cell.delete_stimuli()
        cell.delete_recordings()
    
        current = jx.step_current(i_delay, i_dur, i_amp, dt, t_max)
    
        cell.soma.select(nodes=cell.soma.nodes.index[:1].to_numpy()).stimulate(current)  # Stimulate soma
        cell.soma.select(nodes=cell.soma.nodes.index[:1].to_numpy()).record()
        cell.set("v", v_init)
        cell.init_states()
    
        def simulate(params):
            pstate = None
            pstate = cell.data_set("HVA_tau", 10 ** params[0], pstate)
            pstate = cell.data_set("LVA_tau", 10 ** params[1], pstate)
            pstate = cell.data_set("vt", params[2], pstate)
            pstate = cell.data_set("eK", params[3], pstate)
            pstate = cell.data_set("eNa", params[4], pstate)
    
            pstate = cell.soma.data_set("somatic_NaTs2T_gNaTs2T", params[5], pstate)
            pstate = cell.soma.data_set("somatic_SKv3_1_gSKv3_1", params[6], pstate)
            pstate = cell.soma.data_set("somatic_SKE2_gSKE2", params[7], pstate)
            pstate = cell.soma.data_set("somatic_CaHVA_gCaHVA", params[8], pstate)
            pstate = cell.soma.data_set("somatic_CaLVA_gCaLVA", params[9], pstate)
            pstate = cell.soma.data_set("somatic_CaPump_gamma", params[10], pstate)
            pstate = cell.soma.data_set("somatic_CaPump_decay", 10 ** params[11], pstate)
    
            pstate = cell.apical.data_set("apical_NaTs2T_gNaTs2T", params[12], pstate)
            pstate = cell.apical.data_set("apical_SKv3_1_gSKv3_1", params[13], pstate)
            pstate = cell.apical.data_set("apical_M_gM", params[14], pstate)
            pstate = cell.apical.data_set("apical_M_tau", 10 ** params[15], pstate)
    
            pstate = cell.axon.data_set("axonal_NaTaT_gNaTaT", params[16], pstate)
            pstate = cell.axon.data_set("axonal_KPst_gKPst", params[17], pstate)
            pstate = cell.axon.data_set("axonal_KTst_gKTst", params[18], pstate)
            pstate = cell.axon.data_set("axonal_SKE2_gSKE2", params[19], pstate)
            pstate = cell.axon.data_set("axonal_SKv3_1_gSKv3_1", params[20], pstate)
            pstate = cell.axon.data_set("axonal_CaHVA_gCaHVA", params[21], pstate)
            pstate = cell.axon.data_set("axonal_CaLVA_gCaLVA", params[22], pstate)
            pstate = cell.axon.data_set("axonal_CaPump_gamma", params[23], pstate)
            pstate = cell.axon.data_set("axonal_CaPump_decay", 10 ** params[24], pstate)
    
            return jx.integrate(cell, param_state=pstate, checkpoint_lengths=checkpoints)
        
        return simulate

    def transform_uniform_to_normal(
        lower: Array, upper: Array
    ) -> Tuple[Callable, Callable]:
        def transform(params: Array) -> Array:
            p = (params - lower) / (upper - lower)
            eps = jax.scipy.stats.norm.ppf(p)
            return eps
    
        def inv_transform(params: Array) -> Array:
            u = jax.scipy.stats.norm.cdf(params)
            return u * (upper - lower) + lower
    
        return transform, inv_transform

    def get_bounds():
        bounds = {}
    
        #### GLOBAL PARAMETERS ####
        bounds["HVA_tau"] = [log10(0.2), log10(5.0)]
        bounds["LVA_tau"] = [log10(0.2), log10(5.0)]
        bounds["vt"] = [0.0, 10.0]
        bounds["eK"] = [-100.0, -70.0]
        bounds["eNa"] = [40.0, 60.0]
    
        #### SOMATIC ####
        bounds["somatic_NaTs2T_gNaTs2T"] = [0.0, 6.0]
        bounds["somatic_SKv3_1_gSKv3_1"] = [0.25, 1.0]  # [0, 1]
        bounds["somatic_SKE2_gSKE2"] = [0, 0.1]
        bounds["somatic_CaHVA_gCaHVA"] = [0, 0.001]
        bounds["somatic_CaLVA_gCaLVA"] = [0, 0.01]
        bounds["somatic_CaPump_gamma"] = [0.0005, 0.05]
        bounds["somatic_CaPump_decay"] = [log10(1), log10(100)]  # [5, 100]
    
        #### APICAL ####
        bounds["apical_NaTs2T_gNaTs2T"] = [0, 0.04]
        bounds["apical_SKv3_1_gSKv3_1"] = [0, 0.001]
        bounds["apical_M_gM"] = [0, 0.1]
        bounds["apical_M_tau"] = [log10(0.2), log10(5.0)]  # Newly added parameter.
    
        #### AXONAL ####
        bounds["axonal_NaTaT_gNaTaT"] = [0.0, 6.0]
        bounds["axonal_KPst_gKPst"] = [0.0, 1.0]
        bounds["axonal_KTst_gKTst"] = [0.0, 0.1]
        bounds["axonal_SKE2_gSKE2"] = [0.0, 0.1]
        bounds["axonal_SKv3_1_gSKv3_1"] = [0.0, 2.0]
        bounds["axonal_CaHVA_gCaHVA"] = [0, 0.001]
        bounds["axonal_CaLVA_gCaLVA"] = [0, 0.01]
        bounds["axonal_CaPump_gamma"] = [0.0005, 0.05]
        bounds["axonal_CaPump_decay"] = [log10(1), log10(100)]  # [5, 100]
    
        # Number of params:
        print(f"Number of parameters: {len(bounds.keys())}")
        lowers_and_uppers = jnp.asarray(list(bounds.values()))
    
        names = list(bounds.keys())
        lowers = lowers_and_uppers[:, 0]
        uppers = lowers_and_uppers[:, 1]
        return names, lowers, uppers
    cell=build_cell(nseg=4)
    names,lower,upper=get_bounds()
    return cell,setup_simulator,names,lower,upper,transform_uniform_to_normal
