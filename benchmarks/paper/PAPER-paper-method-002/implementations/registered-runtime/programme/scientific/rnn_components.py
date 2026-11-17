"""Fixed source-derived RNN components; no scientific work on import.

Original MIT jaxley_experiments revision5e7a86282adb9d4603b5546ac5d8dad59aec7cc0.
Function bodies are source-derived under one explicit lazy factory.
The n_out=0 extension passes no nonexistent readout indices to E/I normalization;
this is an explicit prospective constructor variant, not the missing notebook alias.
Global configuration, cloud login, file writes and training entrypoints are not
copied. Their concrete scientific consumers live in rnn.py.
"""
def components():
    import numpy as np
    import jax.numpy as jnp
    import jaxley as jx
    from jaxley.channels import HH
    from jaxley.connect import connect
    from jaxley.synapses import IonotropicSynapse
    from jaxley_mech.channels.l5pc import NaTs2T, CaHVA, CaLVA, CaPump, CaNernstReversal, SKv3_1, SKE2, M, H
    from jaxley_mech.channels.fm97 import Leak
    from jaxley.solver_gate import save_exp
    from scipy.signal import butter, lfilter
    from typing import Dict, List
    def init_inh_ex_gS(
        network, inh_indices, gain, out_indices = [],e_syn_inh=-75, e_syn_ex=0, out_scale=1, return_matrix=False,dist = "normal",name = "IonotropicSynapse"
    ):
        """
        Initialises an excitatory inhibitory network with random weights, such that EI balance is preserved
        """

        n_units = (
            max(
                np.max(network.edges["pre_cell_index"]),
                np.max(network.edges["post_cell_index"]),
            )
            + 1
        )
        n_out = len(out_indices)
        n_units_rec = n_units-n_out
        n_inh = len(inh_indices)
        rec_inds = [ind for ind in range(n_units) if ind not in out_indices]
        recurrent_post_indices = [ind for ind in network.edges["post_cell_index"] if ind not in out_indices]
        n_conn_rec = len(recurrent_post_indices)
        n_conn = len(network.edges["pre_cell_index"])

        average_in_rec = n_conn_rec / n_units_rec
        #print(n_inh,n_units_rec)
        p_inh = n_inh / n_units_rec
        n_ex = n_units_rec - n_inh
        print(average_in_rec)
        print(n_conn_rec)
        print(n_units_rec)
        p_rec = average_in_rec / n_units_rec
        print("conn probability recurrence: " + str(p_rec))
        conn_matrix = np.zeros((n_units, n_units))

        EIratio = (1 - p_inh) / (p_inh)
        print("EIratio:" + str(EIratio))

        normaliser = np.sqrt((1 / (1 - (2 * p_rec) / np.pi)) / EIratio)
        print("Normaliser: " + str(normaliser))
        # this normaliser scales the variances of the two half normal distributions to be gain**2 / N

        for i in range(n_conn):
            pre = int(network.edges.iloc[i]["pre_cell_index"])
            post = int(network.edges.iloc[i]["post_cell_index"])
            if dist=="normal":
                samp = abs(np.random.normal(0, 1, 1)[0])
            elif dist =="uniform":
                samp = abs(np.random.uniform(0, 1))
            else:
                print("dist not recognised, use normal or uniform")
            if post in out_indices:
                samp*=out_scale

            if pre in inh_indices:
                w = samp * normaliser * gain * EIratio / np.sqrt(average_in_rec)
                network.edges.iloc[
                    i, network.edges.columns.get_loc(name+"_gS")
                ] = w
                network.edges.iloc[i, network.edges.columns.get_loc(name+"_e_syn")] = e_syn_inh
                conn_matrix[pre, post] = w * -1

            else:
                w = samp * normaliser * gain / np.sqrt(average_in_rec)
                network.edges.iloc[
                    i, network.edges.columns.get_loc(name+"_gS")
                ] = w
                network.edges.iloc[i, network.edges.columns.get_loc(name+"_e_syn")] = e_syn_ex
                conn_matrix[pre, post] = w

        ev = np.linalg.eigvals(conn_matrix[rec_inds][:,rec_inds])
        print("Spectral radius recurrence: " + str(np.max(np.abs(ev))))
        # this should be close to gain!

        if return_matrix:
            return conn_matrix

    def initialize_RNN(params):
        n_cells = params["n_rec"]
        n_inh = params["n_inh"]
        n_out = params["n_out"]
        init_gain = params["init_gain"]
        out_scale = params["out_scale"]
        inp_scale = params["inp_scale"]
        in_conn_prob = params["in_conn_prob"]
        out_conn_prob = params["out_conn_prob"]
        rec_conn_prob = params["rec_conn_prob"]
        k_minus = params["k_minus"]
        out_k_minus = params["out_k_minus"]

        _ = np.random.seed(params["RNN_seed"])

        # Define the cell
        comp = jx.Compartment()
        branch = jx.Branch(comp, nseg=1)
        cell = jx.Cell([branch, branch, branch], parents=[-1, 0, 0])

        cell.branch(0).add_to_group("apical")
        cell.branch(1).add_to_group("soma")
        cell.branch(2).add_to_group("basal")
        cell.compute_xyz()

        # APICAL
        # Sodium
        cell.apical.insert(NaTs2T())
        cell.apical.set("NaTs2T_gNaTs2T", 0.026145)
        # Potassium
        cell.apical.insert(SKv3_1())
        cell.apical.set("SKv3_1_gSKv3_1", 0.004226)
        cell.apical.insert(M())
        cell.apical.set("M_gM", 0.000143)
        # Nonspecific cation
        cell.apical.insert(H())
        for c in [0.125, 0.375, 0.625, 0.875]:
            distance = cell.branch(0).loc(c).distance(cell.branch(0).loc(0.0))
            cond = (-0.8696 + 2.087 * np.exp(distance * 0.0031)) * 8e-5
            cell.branch(0).loc(c).set("H_gH", cond)

        cell.apical.set("capacitance", 2.0)

        # SOMA
        # Calcium
        ca_dynamics = CaNernstReversal()
        ca_dynamics.channel_constants["T"] = 307.15
        cell.soma.insert(ca_dynamics)
        cell.soma.set("CaCon_i", 5e-05)
        cell.soma.set("CaCon_e", 2.0)
        cell.soma.insert(CaPump())
        cell.soma.set("CaPump_gamma", 0.000609)
        cell.soma.set("CaPump_decay", 210.485291)
        cell.soma.insert(CaHVA())
        cell.soma.set("CaHVA_gCaHVA", 0.000994)
        cell.soma.insert(CaLVA())
        cell.soma.set("CaLVA_gCaLVA", 0.000333)
        # Potassium
        cell.soma.insert(SKv3_1())
        cell.soma.set("SKv3_1_gSKv3_1", 0.303472)
        cell.soma.insert(SKE2())
        cell.soma.set("SKE2_gSKE2", 0.008407)
        # Sodium
        cell.soma.insert(NaTs2T())
        cell.soma.set("NaTs2T_gNaTs2T", 0.983955)

        # BASAL
        # Nonspecific cation
        cell.basal.insert(H())
        cell.basal.set("H_gH", 8e-5)

        # GLOBAL
        cell.insert(Leak())
        cell.set("Leak_gLeak", 3e-05)
        cell.set("Leak_eLeak", -75.0)
        cell.set("axial_resistivity", 100.0)
        cell.set("eNa", 50.0)
        cell.set("eK", -85.0)

        readout = jx.Cell([branch], parents=[-1])
        readout.insert(Leak())
        readout.set("Leak_gLeak", 3e-2)
        readout.show()

        # Define the network
        network = jx.Network([cell for _ in range(n_cells)] + [readout]*n_out)

        # Connect the somas to the apical dendrites
        for i in range(n_cells):
            for j in range(n_cells):
                if np.random.binomial(1, rec_conn_prob):
                    connect(
                        network.cell(i).branch(1).comp(0),
                        network.cell(j).branch(0).comp(0),
                        IonotropicSynapse(),
                    )
            # Connect the cell to the readouts
            if n_out:
                if out_conn_prob < 1.0:
                    if np.random.binomial(1, out_conn_prob):
                        connect(
                            network.cell(i).branch(1).comp(0),
                            network.cell(n_cells).branch(0).comp(0),
                            IonotropicSynapse(),
                        )
                    if np.random.binomial(1, out_conn_prob):
                        connect(
                            network.cell(i).branch(1).comp(0),
                            network.cell(n_cells + 1).branch(0).comp(0),
                            IonotropicSynapse(),
                        )
                else:
                    connect(
                        network.cell(i).branch(1).comp(0),
                        network.cell(n_cells).branch(0).comp(0),
                        IonotropicSynapse(),
                    )
                    connect(
                        network.cell(i).branch(1).comp(0),
                        network.cell(n_cells + 1).branch(0).comp(0),
                        IonotropicSynapse(),
                    )

        # Define inhibitory vs excitatory connectivity
        negative_inds = np.arange(n_inh).tolist()
        conn_matrix = init_inh_ex_gS(
            network,
            negative_inds,
            init_gain,
            out_indices=([n_cells, n_cells + 1] if n_out else []),
            out_scale=out_scale,
            return_matrix=True,
            dist="normal",
        )

        input_weights = np.zeros((n_cells,n_out))
        if n_out:
            # Initialization of input weights sparse and from a uniform distribution
            if in_conn_prob < 1.0:
                for i in range(n_cells):
                    # if np.random.rand()>p_in_conn*2:
                    #    input_weights[i,np.random.randint(0,n_out)]=1
                    if np.random.rand() < in_conn_prob:
                        input_weights[i, 0] = abs(np.random.uniform(0, 1))
                    if np.random.rand() < in_conn_prob:
                        input_weights[i, 1] = abs(np.random.uniform(0, 1))
                input_weights = [{"input_weights": jnp.asarray(input_weights * inp_scale)}]
            # Initialization of input weights not sparse and from a normal distribution
            else:
                input_weights = [
                    {"input_weights": jnp.asarray(np.random.randn(n_cells) * inp_scale)}
                ]

        # Set the k_minus values
        n_conn = len(network.edges["pre_cell_index"])
        for i in range(n_conn):
            post = int(network.edges.iloc[i]["post_cell_index"])
            if post < n_cells:
                # k_mins = 1.0 still ok for in the recurrent network for now
                network.edges.iloc[
                    i, network.edges.columns.get_loc("IonotropicSynapse_k_minus")
                ] = k_minus
            else:
                # Lower k_minus for the leak neuron readout
                network.edges.iloc[
                    i, network.edges.columns.get_loc("IonotropicSynapse_k_minus")
                ] = out_k_minus

        # Set some parameters
        network.set("v", -65.0)
        network.init_states()

        return network, conn_matrix, input_weights

    def butter_lowpass_filter(data, cutoff, fs, order=5):
        b, a = butter(order, cutoff, fs=fs, btype='low', analog=False)
        y = lfilter(b, a, data)
        return y

    def gen_stim(task_params, return_offsets=False, return_mean=False, stim_mean_dist="normal"):
        # Filter of the stimulus
        cutoff = 5 # desired cutoff frequency of the filter, mHz
        order = 6
        fs = task_params["stim_freq_max"]

        # Make the stimulus
        if stim_mean_dist == "normal":
            mean_offset = np.random.binomial(1, 0.5)
            stim_mean = np.random.normal(task_params["stim_mean"][mean_offset], task_params["stim_mean_std"])
        if stim_mean_dist == "uniform":
            stim_mean = np.random.uniform(task_params["stim_mean"][0], task_params["stim_mean"][1]) 
        
        stim_std = task_params["stim_std"]
        n = int(task_params["total_time"] / task_params["dt"])
        stim_unfiltered = np.random.normal(stim_mean, stim_std, size=n)
        stim = butter_lowpass_filter(stim_unfiltered, cutoff, fs, order)

        # Build the mask
        mask = np.zeros_like(stim)
        start_response_dt = int(task_params["response_time"] / task_params["dt"])
        end_response_dt = int((task_params["response_time"] + task_params["response_length"]) / task_params["dt"])
        mask[start_response_dt:end_response_dt] = 1

        # Calculate the target
        offsets = jnp.sum(stim * np.invert(mask.astype(bool)).astype(int))
        
        if task_params["loss"] == "MSE":
            depol_response = np.ones_like(stim) * -70
            depol_response[start_response_dt:end_response_dt] = task_params["target_pol"]
            rest_response = np.ones_like(stim) * -70
            if jnp.sign(offsets) > 0:
                target_response = np.stack([depol_response, rest_response])
            else:
                target_response = np.stack([rest_response, depol_response])
        elif task_params["loss"] == "CE":
            if jnp.sign(offsets) > 0:
                target_response = np.array([1, 0])
            else:
                target_response = np.array([0, 1])
                
        data = [stim, target_response, mask]
        if return_offsets:
            data.append(offsets)
        if return_mean:
            data.append(stim_mean)
        return data

    def gen_stim_batch(task_params, batch_size):
        stims = []
        targets = []
        masks = []
        for _ in range(batch_size):
            stim, target_response, mask = gen_stim(task_params)
            stims.append(stim) 
            targets.append(target_response)
            masks.append(mask)
        return jnp.array(stims), jnp.array(targets), jnp.array(masks)

    def softplus(x: jnp.ndarray,b:float) -> jnp.ndarray:
        """Softplus."""
        return (1/b)*jnp.log(1 + save_exp(x*b))

    def inv_softplus(x: jnp.ndarray,b:float) -> jnp.ndarray:
        """Inverse softplus."""
        return jnp.log(save_exp(b*x) - 1)/b

    def sigmoid(x: jnp.ndarray) -> jnp.ndarray:
        """Sigmoid."""
        return 1 / (1 + save_exp(-x))

    def expit(x: jnp.ndarray) -> jnp.ndarray:
        """Inverse sigmoid (expit)"""
        return -jnp.log(1 / x - 1)

    class ParamTransform:
        """Parameter transformation utility.

        Updated version that allows scaling the softplus with an additional parameter b

        This class is used to transform parameters from an unconstrained space to a constrained space
        and back. If the range is bounded both from above and below, we use the sigmoid function to
        transform the parameters. If the range is only bounded from below or above, we use softplus.

        Attributes:
            lowers: A dictionary of lower bounds for each parameter (None for no bound).
            uppers: A dictionary of upper bounds for each parameter (None for no bound).

        """

        def __init__(self, lowers: Dict[str, float], uppers: Dict[str, float],bs: Dict[str,float]) -> None:
            """Initialize the bounds.

            Args:
                lowers: A dictionary of lower bounds for each parameter (None for no bound).
                uppers: A dictionary of upper bounds for each parameter (None for no bound).
            """

            self.lowers = lowers
            self.uppers = uppers
            self.bs = bs

        def forward(self, params: List[Dict[str, jnp.ndarray]]) -> jnp.ndarray:
            """Pushes unconstrained parameters through a tf such that they fit the interval.

            Args:
                params: A list of dictionaries with unconstrained parameters.

            Returns:
                A list of dictionaries with transformed parameters.

            """

            tf_params = []
            for param in params:
                key = list(param.keys())[0]

                # If constrained from below and above, use sigmoid
                if self.lowers[key] is not None and self.uppers[key] is not None:
                    tf = (
                        sigmoid(param[key]) * (self.uppers[key] - self.lowers[key])
                        + self.lowers[key]
                    )
                    tf_params.append({key: tf})

                # If constrained from below, use softplus
                elif self.lowers[key] is not None:
                    b = self.bs[key]
                    tf = softplus(param[key],b) + self.lowers[key]
                    tf_params.append({key: tf})

                # If constrained from above, use negative softplus
                elif self.uppers[key] is not None:
                    b = self.bs[key]
                    tf = -softplus(-param[key],b) + self.uppers[key]
                    tf_params.append({key: tf})
                # Else just pass through
                else:
                    tf_params.append({key: param[key]})
                    
            return tf_params

        def inverse(self, params: jnp.ndarray) -> jnp.ndarray:
            """Takes parameters from within the interval and makes them unconstrained.

            Args:
                params: A list of dictionaries with transformed parameters.

            Returns:
                A list of dictionaries with unconstrained parameters.
            """

            tf_params = []
            for param in params:
                key = list(param.keys())[0]

                # If constrained from below and above, use expit
                if self.lowers[key] is not None and self.uppers[key] is not None:
                    tf = expit(
                        (param[key] - self.lowers[key])
                        / (self.uppers[key] - self.lowers[key])
                    )
                    tf_params.append({key: tf})

                # If constrained from below, use inv_softplus
                elif self.lowers[key] is not None:
                    b = self.bs[key]
                    tf = inv_softplus(param[key] - self.lowers[key],b)
                    tf_params.append({key: tf})

                # If constrained from above, use negative inv_softplus
                elif self.uppers[key] is not None:
                    b = self.bs[key]
                    tf = -inv_softplus(-(param[key] - self.uppers[key]),b)
                    tf_params.append({key: tf})

                # else just pass through
                else:
                    tf_params.append({key: param[key]})

            return tf_params

    class DMS():
        """
        Class for generating delayed match to sample task data
        """
        def __init__(self, task_params):
            self.params = task_params
        
        def gen_batch(self):
            """
            Generate a batch of trials with randomly generated delays and stimulus identities
            Returns:
                Stim: stimulus array [batch_size, duration, 2]
                target: target array [batch_size, duration, 2]
                mask: target array [batch_size, duration, 2]
            """
            n_out=2
            if len(self.params["stim_onset"])>1:
                ramp_up =(np.random.uniform(low = self.params['stim_onset'][0], high = self.params['stim_onset'][1],size=(self.params['batch_size'],)))
                ramp_up = ramp_up.astype(int)
            else:
                ramp_up = [self.params["stim_onset"][0]]*self.params['batch_size']
          
            if len(self.params["delay"])>1:
                delay =(np.random.uniform(low = self.params['delay'][0], high = self.params['delay'][1],size=(self.params['batch_size'],)))
                delay = delay.astype(int)
            else:
                delay = [self.params["delay"][0]]*self.params['batch_size']
          
            sim_time = self.params["stim_len"]*2 + self.params['delay'][-1] + self.params["stim_onset"][-1] + self.params['response_onset'] + self.params["response"]
            stim1_end = np.array(ramp_up) + self.params["stim_len"]
            delay_end = stim1_end + np.array(delay)
            stim2_end = delay_end + self.params["stim_len"]
            response_onset = stim2_end + self.params['response_onset']
            response_end = response_onset+self.params['response']

            stim = np.zeros((self.params['batch_size'], sim_time,n_out))
            target = np.zeros((self.params['batch_size'], sim_time,n_out))
            mask = np.zeros((self.params['batch_size'], sim_time,n_out))

            stim1 = np.random.randint(0,2,self.params['batch_size'])
            stim2 = np.random.randint(0,2,self.params['batch_size'])
            match = (stim1==stim2).astype(int)

            for i in range(self.params['batch_size']):
                stim[i, ramp_up[i]:stim1_end[i],stim1[i]] += self.params['stim_amp']+np.random.randn(self.params['stim_len'])*self.params['stim_noise_sd']
                stim[i, delay_end[i]:stim2_end[i],stim2[i]] += self.params['stim_amp']+np.random.randn(self.params['stim_len'])*self.params['stim_noise_sd']
                target[i,response_onset[i]:,match[i]]=1
                mask[i,response_onset[i]:response_end[i]]=1

            return stim, target, mask
        
        def gen(self):
            """
            Generate four trials, one corresponding to each possible stimulus combination
            Returns:
                Stim: stimulus array [4, duration, 2]
                target: target array [4, duration, 2]
                mask: target array [4, duration, 2]
            """
            n_trials=4
            n_out=2
            if len(self.params["stim_onset"])>1:
                ramp_up =(np.random.uniform(low = self.params['stim_onset'][0], high = self.params['stim_onset'][1],size=(n_trials,)))
                ramp_up = ramp_up.astype(int)
            else:
                ramp_up = [self.params["stim_onset"][0]]*n_trials
          
            if len(self.params["delay"])>1:
                delay =(np.random.uniform(low = self.params['delay'][0], high = self.params['delay'][1],size=(n_trials,)))
                delay = delay.astype(int)
            else:
                delay = [self.params["delay"][0]]*n_trials

          
            sim_time = self.params["stim_len"]*2 + self.params['delay'][-1] + self.params["stim_onset"][-1] + self.params['response_onset'] + self.params["response"]
            stim1_end = np.array(ramp_up) + self.params["stim_len"]
            delay_end = stim1_end + np.array(delay)
            stim2_end = delay_end + self.params["stim_len"]
            response_onset = stim2_end + self.params['response_onset']
            response_end = response_onset+self.params['response']

            stim = np.zeros((n_trials, sim_time,n_out))
            target = np.zeros((n_trials, sim_time,n_out))
            mask = np.zeros((n_trials, sim_time,1))

            stim[0, ramp_up[0]:stim1_end[0],0] += self.params['stim_amp']+np.random.randn(self.params['stim_len'])*self.params['stim_noise_sd']
            stim[1, ramp_up[1]:stim1_end[1],0] += self.params['stim_amp']+np.random.randn(self.params['stim_len'])*self.params['stim_noise_sd']
            stim[2, ramp_up[2]:stim1_end[2],1] += self.params['stim_amp']+np.random.randn(self.params['stim_len'])*self.params['stim_noise_sd']
            stim[3, ramp_up[3]:stim1_end[3],1] += self.params['stim_amp']+np.random.randn(self.params['stim_len'])*self.params['stim_noise_sd']

            stim[0, delay_end[0]:stim2_end[0],0] += self.params['stim_amp']+np.random.randn(self.params['stim_len'])*self.params['stim_noise_sd']
            stim[1, delay_end[1]:stim2_end[1],1] += self.params['stim_amp']+np.random.randn(self.params['stim_len'])*self.params['stim_noise_sd']
            stim[2, delay_end[2]:stim2_end[2],0] += self.params['stim_amp']+np.random.randn(self.params['stim_len'])*self.params['stim_noise_sd']
            stim[3, delay_end[3]:stim2_end[3],1] += self.params['stim_amp']+np.random.randn(self.params['stim_len'])*self.params['stim_noise_sd']

            target[0,response_onset[0]:,1]=1
            target[1,response_onset[1]:,0]=1
            target[2,response_onset[2]:,0]=1
            target[3,response_onset[3]:,1]=1

            for i in range(4):
                mask[i,response_onset[i]:response_end[i]]=1
            return stim, target, mask

    return {'initialize_RNN':initialize_RNN,'gen_stim':gen_stim,'gen_stim_batch':gen_stim_batch,'DMS':DMS,'ParamTransform':ParamTransform}
