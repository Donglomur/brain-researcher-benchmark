"""Reference solution for WMLOAD-001.

Deliverable: from the human medial-temporal-lobe (MTL) single-neuron recordings in the Sternberg
working-memory task (DANDI 000673, Daume et al. 2024), report how well an individual load-selective
MTL neuron discriminates the working-memory load (one vs three maintained items) from its firing rate
during the maintenance (delay) period -- the mean single-neuron load ROC AUC across the
load-selective neurons -- together with the proportion of MTL neurons that are load-selective.

In each trial the subject encodes either one or three pictures, holds them across a delay
(maintenance) period, and is then probed. A neuron is "load-selective" because its maintenance-period
firing rate separates load-1 from load-3 trials, and the same separation is then what the load ROC
AUC measures. If you select the neurons on a set of trials and then measure their AUC on those SAME
trials, the AUC is inflated by a winner's curse (non-independence / "double dipping", Kriegeskorte et
al. 2009): you picked the neurons whose noise happened to separate the two loads, and on the same
trials that noise still separates them. The honest estimate selects the load-selective neurons (and
their preferred load direction) on one split of the trials and measures the load AUC on a held-out
split.

Validated ground truth (DANDI 000673, ALL sessions pooled; MTL = hippocampus + amygdala units by
electrode location; maintenance period = from the maintenance-onset timestamp to the probe-onset
timestamp; per-trial firing rate over that window; load-selective = two-sided rank-sum load-1 vs
load-3 p < 0.05; load AUC taken in the neuron's preferred load direction):
  n MTL neurons pooled              = ~856
  proportion load-selective         = ~0.123
  NAIVE  mean load AUC of load-selective cells, selected AND measured on the SAME trials  = ~0.62
  CORRECT mean load AUC of load-selective cells, selection/direction on train, AUC on held-out = ~0.54
Single MTL neurons carry only a weak load signal in mean maintenance firing rate: out of sample the
honest load AUC is ~0.54 (barely above chance), and the load-selective fraction (~0.12) is only
modestly above the 0.05 chance false-positive rate. The apparent ~0.62 single-neuron load signal is
largely a selection artifact; selecting the cells on independent trials (any reasonable held-out /
nested scheme) removes most of the inflation. A reported ~0.62 fails the match.
"""
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

DANDISET = "000673"
REGION_KEYS = ("hippocampus", "amygdala")   # medial temporal lobe (electrode location, lower-cased)
LOAD_LOW, LOAD_HIGH = 1, 3
MS_ALPHA = 0.05           # load-selective: two-sided rank-sum load-1 vs load-3
N_SPLITS = 50             # repeated stratified halves for the honest held-out estimate
SEED = 0


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dandiset": DANDISET}, indent=2))
    (OUT / "results.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    import h5py
    import remfile
    from dandi.dandiapi import DandiAPIClient
    from pynwb import NWBHDF5IO
    from scipy.stats import mannwhitneyu, rankdata
except Exception as e:  # pragma: no cover
    fail(f"missing dependency: {e}")


def auc(scores, labels):
    """ROC AUC that the load-high trials (labels==1) have higher firing than the load-low trials."""
    labels = np.asarray(labels).astype(int)
    npos = int(labels.sum())
    nneg = len(labels) - npos
    if npos == 0 or nneg == 0:
        return 0.5
    r = rankdata(scores)
    return float((r[labels == 1].sum() - npos * (npos + 1) / 2.0) / (npos * nneg))


def collect_neurons():
    """Stream every session's maintenance-period MTL spiking; return list of (fr, lab) per neuron.

    fr = per-trial firing rate over the maintenance window [maintenance-onset, probe-onset];
    lab = 1 for load-3 (high), 0 for load-1 (low). Only the MTL units' spike_times are read, so the
    streaming stays light.
    """
    neurons = []
    n_sessions = 0
    with DandiAPIClient() as client:
        ds = client.get_dandiset(DANDISET, "draft")
        paths = sorted(a.path for a in ds.get_assets() if a.path.endswith(".nwb"))
        if not paths:
            fail(f"no NWB assets in dandiset {DANDISET}")
        for p in paths:
            try:
                url = ds.get_asset_by_path(p).get_content_url(follow_redirects=1, strip_query=False)
                io = NWBHDF5IO(file=h5py.File(remfile.File(url), "r"), load_namespaces=True)
                nwb = io.read()
                tr = nwb.trials.to_dataframe()
                loads = tr["loads"].values.astype(int)
                m0 = tr["timestamps_Maintenance"].values.astype(float)   # maintenance onset
                m1 = tr["timestamps_Probe"].values.astype(float)         # probe onset (delay end)
                keep_tr = np.array([(m1[t] > m0[t] > 0) and (loads[t] in (LOAD_LOW, LOAD_HIGH))
                                    for t in range(len(loads))])
                if keep_tr.sum() < 20:
                    continue
                u = nwb.units
                el = nwb.electrodes.to_dataframe()
                for i in range(len(u.id)):
                    eidx = u["electrodes"][i].index.values
                    locs = el.loc[eidx, "location"].values
                    loc = str(locs[0]).lower() if len(locs) else ""
                    if not any(k in loc for k in REGION_KEYS):
                        continue
                    st = np.asarray(u["spike_times"][i]).astype(float)
                    fr = []
                    lab = []
                    for t in range(len(loads)):
                        if not keep_tr[t]:
                            continue
                        fr.append((np.searchsorted(st, m1[t]) - np.searchsorted(st, m0[t]))
                                  / (m1[t] - m0[t]))
                        lab.append(1 if loads[t] == LOAD_HIGH else 0)
                    neurons.append((np.asarray(fr, float), np.asarray(lab, int)))
                n_sessions += 1
            except Exception:
                continue
    return neurons, n_sessions


neurons, n_sessions = collect_neurons()
if len(neurons) < 100:
    fail(f"too few MTL neurons pooled ({len(neurons)}) -- streaming may have failed")

rng = np.random.default_rng(SEED)

# ---- load-selective test on all trials (for the proportion + the naive contrast) ----
ms_flags = np.zeros(len(neurons), dtype=bool)
naive_fold = []
for j, (fr, lab) in enumerate(neurons):
    try:
        _, p = mannwhitneyu(fr[lab == 0], fr[lab == 1], alternative="two-sided")
    except Exception:
        p = 1.0
    if p < MS_ALPHA:
        ms_flags[j] = True
        a = auc(fr, lab)
        naive_fold.append(max(a, 1.0 - a))     # load AUC in the preferred direction, SAME trials
prop_ms = float(ms_flags.mean())
naive_auc = float(np.mean(naive_fold)) if naive_fold else float("nan")

# ---- honest estimate: select load-selective neurons and their preferred load direction on a TRAIN ----
# ---- split, measure the load AUC on the HELD-OUT split, repeat and average --------------------------
held = [[] for _ in neurons]
for rep in range(N_SPLITS):
    for j, (fr, lab) in enumerate(neurons):
        idx = np.arange(len(lab))
        i0, i1 = idx[lab == 0], idx[lab == 1]
        if len(i0) < 4 or len(i1) < 4:
            continue
        tr = np.concatenate([rng.choice(i0, len(i0) // 2, replace=False),
                             rng.choice(i1, len(i1) // 2, replace=False)])
        te = np.setdiff1d(idx, tr)
        try:
            _, p = mannwhitneyu(fr[tr][lab[tr] == 0], fr[tr][lab[tr] == 1], alternative="two-sided")
        except Exception:
            p = 1.0
        if p < MS_ALPHA:                         # selected as load-selective on TRAIN only
            sign = 1.0 if auc(fr[tr], lab[tr]) >= 0.5 else -1.0   # preferred load direction on TRAIN
            held[j].append(auc(fr[te] * sign, lab[te]))          # load AUC on HELD-OUT trials
per_cell_heldout = [np.mean(h) for h in held if len(h) >= 5]
honest_auc = float(np.mean(per_cell_heldout)) if per_cell_heldout else float("nan")

results = {
    # headline: honest single-neuron working-memory load discriminability of load-selective neurons
    "load_selective_load_auc": round(honest_auc, 4),
    "proportion_load_selective": round(prop_ms, 4),
    "n_mtl_neurons": len(neurons),
    "n_load_selective": int(ms_flags.sum()),
    "n_sessions": n_sessions,
    # contrast value: the SAME-TRIALS (non-independent) estimate -- inflated, reported for transparency
    "same_trials_load_auc_inflated": round(naive_auc, 4),
    "params": {
        "region": "MTL (hippocampus + amygdala) by peak-channel electrode location",
        "epoch": "maintenance (delay) period, from the maintenance-onset timestamp to the probe onset",
        "loads_compared": [LOAD_LOW, LOAD_HIGH],
        "load_selective": "two-sided Wilcoxon rank-sum load-1 vs load-3, p < %.2f" % MS_ALPHA,
        "load_auc": "ROC AUC classifying load-1 vs load-3 from maintenance firing rate, taken in the "
                    "neuron's preferred load direction; neuron selection and preferred direction "
                    "estimated on training trials, AUC evaluated on held-out trials",
        "held_out_scheme": "%d repeated stratified halves" % N_SPLITS,
    },
}
(OUT / "results.json").write_text(json.dumps(results, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dandiset": DANDISET, "n_sessions": n_sessions,
    "n_mtl_neurons": len(neurons), "n_load_selective": int(ms_flags.sum()),
    "region": "hippocampus + amygdala (MTL)", "epoch": "maintenance (delay) period",
    "loads_compared": [LOAD_LOW, LOAD_HIGH],
    "load_selective_test": "rank-sum load-1 vs load-3 p<%.2f" % MS_ALPHA,
    "load_auc_definition": "single-neuron ROC AUC load-1 vs load-3, preferred direction, "
                           "selection/direction on train + AUC on held-out trials",
}, indent=2))

(OUT / "findings.md").write_text(
    f"# Single-neuron working-memory load discriminability in human MTL -- DANDI 000673\n\n"
    f"Pooling {len(neurons)} medial-temporal-lobe units (hippocampus + amygdala) across "
    f"{n_sessions} sessions of a Sternberg working-memory task, **{100*prop_ms:.1f}%** are "
    f"load-selective (maintenance-period firing rate separates load-1 from load-3 trials, "
    f"rank-sum p<0.05).\n\n"
    f"Selecting each load-selective neuron and its preferred load direction on one split of the "
    f"trials and measuring its load ROC AUC on a held-out split gives a mean single-neuron load AUC "
    f"of **{honest_auc:.3f}** -- only slightly above chance (0.5). The single-neuron working-memory "
    f"load signal in mean maintenance firing is therefore weak; the **{naive_auc:.3f}** obtained "
    f"when the same trials are used to select the neurons and to score the AUC overstates it, because "
    f"that estimate is inflated by selection (a winner's curse).\n\n"
    f"Reported headline: mean held-out load AUC = **{honest_auc:.3f}** "
    f"(proportion load-selective = {prop_ms:.3f}).\n")

print(f"n_mtl_neurons={len(neurons)} n_sessions={n_sessions} prop_ms={prop_ms:.4f} "
      f"honest_auc={honest_auc:.4f} naive_auc={naive_auc:.4f}")
