# this notebook processes data and simulations for figure 3 and saves the results 
# as a list in "evals37.npy". Run "make_figure3" after this. 

# install the latest version of torch first
import sys 
sys.path.insert(0, '../')
import os, torch, lyapun
import simulations
import numpy as np 
import matplotlib.pyplot as plt

# replace 'cuda' with 'cpu' if you don't have a GPU (it will be slow)
device = torch.device('cuda')

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
            {"mouse_name": "WT4", "date": "2025_10_21", "area": "CA1"},
            {"mouse_name": "WT5", "date": "2025_10_21", "area": "CA1"},
            {"mouse_name": "GP40", "date": "2025_10_23", "area": "CA1"},
            {"mouse_name": "GP39", "date": "2025_10_22", "area": "CA1"},
            ]
dbs_ephys = [{"mouse_name": "Waksman"},
             {"mouse_name": "Robbins"},
             {"mouse_name": "Krebs"},
             ]


# replace this with your own path to the data (~10GB/file)
root = r'/media/carsen/disk1/random_matrix/'

evals = []

for iexp, db in enumerate(dbs_2P): 
    fname = os.path.join(root, 'F_%s_%s.npz'%(db['mouse_name'],db['date']))
    
    print(fname)

    # this data has already been deconvolved as described in the paper
    dat = np.load(fname, allow_pickle = True)    
    sp = dat['sp']
    print(sp.shape)
    xpos, ypos = dat['xpos'], dat['ypos']

    sp_s = lyapun.zscore(sp, axis=1)    
    
    # use dynamic mode decomposition to estimate complex eigenvalues
    e   = lyapun.dmd(    sp_s, lam = .01, delta = 5,device = device)[1]

    # compute the autocorrelation time scales
    acg = lyapun.pc_timescales(sp_s, xpos, ypos, device = device)

    evals.append({'e': e, 'acg':acg })  

from scipy.sparse import csr_matrix
mname = ['Waksman', 'Robbins', 'Krebs']

tbin = 1./22
for iexp, db in enumerate(dbs_ephys): 
    mouse_name = db["mouse_name"]
    dat = np.load(os.path.join(root, f"{mouse_name}_spks_face.npz"), allow_pickle=True)
    area = dat["areas"]
    clu = dat["clu"]
    st = dat["st"]
    st -= st.min()
    sp = csr_matrix((np.ones(clu.size, "uint8"), (clu, np.round(st / tbin).astype("uint32"))), 
                                shape=(clu.max()+1, int(np.round(st.max() / tbin)) + 1))
    sp = sp.toarray().astype("float32")
    
    # keep neurons with firing rate > 0.01 Hz
    igood = sp.mean(axis=1) > 0.01 * tbin
    sp = sp[igood]
    ypos = dat["ypos"][igood]
    xpos = dat["iprobe"][igood].astype("float32") * 0
    
    # normalize like above
    spz = lyapun.zscore(sp, axis=-1)

    # run the same analyses as above 
    e   = lyapun.dmd(spz, lam = .1, delta = 5, device = device)[1]

    # sig = 2 is the default for the ephys data due to high noise (see paper)
    acg = lyapun.pc_timescales(spz, xpos, ypos, sig = 2, device = device)

    evals.append({'e': e, 'acg':acg })


n_sim = 4
nn = 10000
simulations.set_seed(0, device)
# nonsymmetry levels of random connectivity matrix
nonsyms = [0., 1]
tbins = np.unique(np.round(np.exp(np.linspace(np.log(1), np.log(2000), 20)))).astype(int)
evals_bin_all = np.zeros((n_sim, len(nonsyms), len(tbins), nn))
for ni, nonsym in enumerate(nonsyms):
    for i in range(n_sim):
        A, Xi, evals0 = simulations.simulate_random(nn=nn, nonsym=nonsym)
        sp = Xi.cpu().numpy()

        # Generate random positions in the range 0-1000 "um". 
        # These are necessary for neuron splits into train/test like we do for the real data.
        xpos = 1000 * np.random.rand(nn,)
        ypos = 1000 * np.random.rand(nn,)

        # run the same analyses as for the real data
        e   = lyapun.dmd(sp, lam = .01, delta = 5, device = device, nt=2434)[1]
        acg = lyapun.pc_timescales(sp, xpos, ypos, device = device)
        evals.append({'e': e, 'acg':acg })


np.savez(r'../results/evals37.npz', 
         evals=np.array(evals, dtype=object))

from matplotlib import pyplot as plt
import numpy as np 
import matplotlib as mpl 
import sys
sys.path.insert(0, '../')
# make sure you have fig3.py in this same folder
import fig3 

# evals37.npz contains the results of the analyses 
evals = np.load(r'../results/evals37.npz', allow_pickle=True)['evals']
evals = list(evals)

print(len(evals))

import importlib as imp
imp.reload(fig3)
mpl.rcParams['font.family'] = 'Arial' 


fig = plt.figure(figsize=(14,7.5))

dcolors = [[.5,0,0], [.5,.5,0], [0,0,.5], [.75, .75, .75], [.5, .5, .5]]
grid = plt.GridSpec(3,5, figure=fig, left=0.02, right=0.98, top=0.98, bottom=0.02, 
                    wspace = 0.5, hspace = 0.5)
il = 0

il = fig3.fig00(fig, il, grid, evals)
il = fig3.fig02(fig, il, grid, evals)
il = fig3.fig10(fig, il, grid, evals)
il = fig3.fig11(fig, il, grid, evals)
il = fig3.fig20(fig, il, grid, evals)
il = fig3.fig23(fig, il, grid, evals)

fig.savefig("../figures/fig3.pdf", dpi=300, bbox_inches = 'tight')