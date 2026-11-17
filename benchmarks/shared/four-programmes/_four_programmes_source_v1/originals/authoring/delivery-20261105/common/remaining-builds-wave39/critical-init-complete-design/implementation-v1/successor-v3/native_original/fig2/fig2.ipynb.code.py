import numpy as np 
import torch
import sys, os
sys.path.insert(0, "../")
import analysis
from pathlib import Path
import matplotlib.pyplot as plt

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# datasets will be shared upon publication
# available to reviewers at private figshare link
# will take ~20 min to run on GPU
dbs_2P = [  
            {"mouse_name": "FX14", "date": "2024_11_23", "area": "V1"},
            {"mouse_name": "FX17", "date": "2024_11_24", "area": "V1"},
            {"mouse_name": "FX26", "date": "2024_11_20", "area": "V1"},
            {"mouse_name": "FX42", "date": "2024_12_12", "area": "V1"},
            {"mouse_name": "FX43", "date": "2024_12_12", "area": "V1"},
            {"mouse_name": "QZ2", "date": "2024_12_15", "area": "V1", "hasrunning": True},
            {"mouse_name": "VGa7", "date": "2025_09_27", "area": "V1", "hasrunning": True},
            {"mouse_name": "WT2", "date": "2025_09_21", "area": "V1", "hasrunning": True},
            {"mouse_name": "WT3", "date": "2025_09_28", "area": "V1", "hasrunning": True},
            {"mouse_name": "RL_CAG5", "date": "2025_05_28", "area": "sensorimotor", "hasrunning": True},
            {"mouse_name": "RL_CAG10", "date": "2025_06_04", "area": "sensorimotor"},
            {"mouse_name": "RL_CAG11", "date": "2025_06_05", "area": "sensorimotor"},
            {"mouse_name": "FXa15", "date": "2025_10_24", "area": "sensorimotor", "hasrunning": True}, 
            {"mouse_name": "FXa16", "date": "2025_10_24", "area": "sensorimotor", "hasrunning": True}, 
            {"mouse_name": "FXa5", "date": "2025_10_27", "area": "PPC"},
            {"mouse_name": "FX41", "date": "2025_05_29", "area": "PPC", "hasrunning": True},
            {"mouse_name": "FX43", "date": "2025_05_29", "area": "PPC"},
            {"mouse_name": "FXa11", "date": "2025_09_10", "area": "PPC"},
            {"mouse_name": "GP7", "date": "2024_11_27", "area": "CA1"},
            {"mouse_name": "GP8", "date": "2024_11_29", "area": "CA1"},
            {"mouse_name": "GP9", "date": "2024_11_26", "area": "CA1"},
            {"mouse_name": "GP10", "date": "2024_11_29", "area": "CA1"},
            {"mouse_name": "GP39", "date": "2025_10_22", "area": "CA1"},
            {"mouse_name": "GP40", "date": "2025_10_23", "area": "CA1"},
            {"mouse_name": "WT4", "date": "2025_10_21", "area": "CA1"},
            {"mouse_name": "WT5", "date": "2025_10_21", "area": "CA1"},
            ]
dbs_ephys = [{"mouse_name": "Krebs"},
             {"mouse_name": "Waksman"},
             {"mouse_name": "Robbins"}]

root = Path("/media/carsen/disk1/random_matrix") # folder with shared datasets

out = analysis.neural_powerlaws(root, dbs_2P, dbs_ephys, device=device)

evals_all, evals_all_neurons, evals_all_times, evals_svca2_all, evals_svca2_all_neurons, evals_svca2_all_times, evals_svca_all, evals_svca_all_neurons, evals_svca_all_times, evals_shuff_all, areas_all, Xexs, isorts, snr_rat, shapes = out

os.makedirs("../results", exist_ok=True)
np.save("../results/evals_neural_all.npy", {"evals_all": evals_all, 
                                 "evals_svca2_all": evals_svca2_all,
                                 "evals_svca2_all_neurons": evals_svca2_all_neurons,
                                 "evals_svca_all_neurons": evals_svca_all_neurons,
                                 "evals_all_neurons": evals_all_neurons,
                                 "evals_svca2_all_times": evals_svca2_all_times,
                                 "evals_svca_all_times": evals_svca_all_times,
                                 "evals_all_times": evals_all_times,
                                 "evals_svca_all": evals_svca_all,
                                 "evals_shuff_all": evals_shuff_all, 
                                 "areas_all": areas_all, "Xexs": Xexs, "isorts": isorts, 
                                 "snr_rat": snr_rat, "shapes": shapes})


evals_run_all, dmd_evals_all, areas = analysis.running(root, dbs_2P)
np.save('../results/evals_running.npy', {'evals_run_all': evals_run_all, 'dmd_evals_all': dmd_evals_all, 'areas': areas})


evals_areas, area_groups, nneurons, spks_sort = analysis.ephys_areas(root, dbs_ephys)
np.save('../results/ephys_areas.npy', {'evals_areas': evals_areas, 
                                       'area_groups': area_groups,
                                       'nneurons': nneurons,
                                       'spks_sort': spks_sort})

evals_tbins, tbins = analysis.ephys_tbins(root, dbs_ephys)
np.save('../results/ephys_tbins.npy', {'evals_tbins': evals_tbins, 
                                       'tbins': tbins})

### will need to download other data for this - see function
analysis.gcamp_subsample(root, dbs_2P)

import simulations

evals_all, alphas_all, enorms = simulations.enorm_sweep()
np.save('../results/enorm_sims.npy', {'evals_enorms': evals_all, 'enorms': enorms})

evals_sub, Xemb_ex = simulations.sims_fig2(n_sim = 10)
np.save('../results/sims_fig2_2.npy', {'evals_sub': evals_sub, 'Xemb_ex': Xemb_ex})

import fig2
# importlib.reload(fig2)

dat = np.load("../results/evals_neural_all.npy", allow_pickle=True).item()
dat_traces = np.load("traces.npy", allow_pickle=True).item()
dat_sim = np.load('../results/sims_fig2_2.npy', allow_pickle=True).item()
dat_enorms = np.load('../results/enorm_sims.npy', allow_pickle=True).item()
dat = {**dat, **dat_traces, **dat_sim, **dat_enorms}

fig, alphas = fig2.fig2(dat)
os.makedirs("../figures", exist_ok=True)
fig.savefig("../figures/fig2.pdf")

dat_areas = np.load('../results/ephys_areas.npy', allow_pickle=True).item()
dat_tbins = np.load('../results/ephys_tbins.npy', allow_pickle=True).item()
fig = fig2.suppfig_ephys(dat, dat_areas, dat_tbins)
fig.savefig('../figures/suppfig_ephys.pdf')

dat = np.load('../results/evals_running.npy', allow_pickle=True).item()
fig = fig2.suppfig_running(dat)
fig.savefig('../figures/suppfig_running.pdf')

dat_janelia = np.load("../results/gcamp6_svca_janelia.npy", allow_pickle=True).item()
dat_london = np.load("../results/gcamp6_svca_london.npy", allow_pickle=True).item()
dat_subsample = np.load("../results/gcamp8_svca_subsample.npy", allow_pickle=True).item()
fig = fig2.suppfig_svca2(dat, dat_subsample, dat_janelia, dat_london)
fig.savefig("../figures/suppfig_svca2.pdf")