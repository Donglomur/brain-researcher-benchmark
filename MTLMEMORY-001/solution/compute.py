"""Reference solution for MTLMEMORY-001.

Deliverable: from the human medial-temporal-lobe (MTL) single-neuron recordings in the new/old
recognition-memory task (DANDI 000004, Faraut/Rutishauser), report how well an individual
memory-selective MTL neuron discriminates NOVEL from FAMILIAR images during recognition -- the mean
single-neuron new/old ROC AUC across the memory-selective neurons -- together with the proportion of
MTL neurons that are memory-selective.

The correct analysis keeps the neuron SELECTION independent of the discriminability ESTIMATE. A
neuron is called "memory-selective" because its recognition-period firing rate separates novel from
familiar trials, and the same separation is then what the new/old ROC AUC measures. If you select
the neurons on a set of trials and then measure their AUC on those SAME trials, the AUC is inflated
by a winner's curse (non-independence / "double dipping", Kriegeskorte et al. 2009): you picked the
neurons whose noise happened to separate the labels, and on the same trials that noise still
separates the labels. The honest estimate selects the memory-selective neurons (and their preferred
novelty/familiarity direction) on one split of the recognition trials and measures the new/old AUC
on a held-out split.

Validated ground truth (DANDI 000004, ALL sessions pooled, MTL = hippocampus + amygdala units by
electrode location; recognition phase; per-trial firing rate over the [0.2, 1.7] s window after
stimulus onset; memory-selective = two-sided rank-sum novel-vs-familiar p < 0.05; new/old AUC taken
in the neuron's preferred direction):
  n MTL neurons pooled              = ~1864
  proportion memory-selective       = ~0.057   (barely above the 0.05 chance false-positive rate)
  NAIVE  mean new/old AUC of MS cells, selected AND measured on the SAME trials  = ~0.63
  CORRECT mean new/old AUC of MS cells, selection/direction on train, AUC on held-out = ~0.51
The apparent 0.63 single-neuron memory signal is almost entirely a selection artifact: the
memory-selective fraction is at the chance false-positive rate, and out-of-sample the discrimination
is ~0.51 (chance). Selecting the cells on independent trials (any reasonable held-out / nested
scheme) removes the inflation and the honest new/old AUC is ~0.51. A reported ~0.63 fails the match.
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

DANDISET = "000004"
REGION_KEYS = ("Hippocampus", "Amygdala")   # medial temporal lobe
WIN = (0.2, 1.7)          # s after stimulus onset
MS_ALPHA = 0.05           # memory-selective: two-sided rank-sum novel vs familiar
N_SPLITS = 60             # repeated stratified halves for the honest held-out estimate
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
    from scipy.stats import mannwhitneyu
    from sklearn.metrics import roc_auc_score
except Exception as e:  # pragma: no cover
    fail(f"missing dependency: {e}")


def auc(scores, labels):
    if len(np.unique(labels)) < 2:
        return 0.5
    return roc_auc_score(labels, scores)


def collect_neurons():
    """Stream every session's recognition-phase MTL spiking; return list of (fr, lab) per neuron.

    fr = per-recognition-trial firing rate in the [0.2, 1.7] s window; lab = 1 for familiar (old),
    0 for novel (new). Only the MTL units' spike_times are read, so the streaming stays light.
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
                rec = tr[tr["stim_phase"] == "recog"]
                on = rec["stim_on_time"].values.astype(float)
                lab = (rec["new_old_labels_recog"].values.astype(str) == "1").astype(int)
                if len(on) < 20 or len(np.unique(lab)) < 2:
                    continue
                u = nwb.units
                el = nwb.electrodes.to_dataframe()
                for i in range(len(u.id)):
                    eidx = u["electrodes"][i].index.values
                    locs = el.loc[eidx, "location"].values
                    loc = str(locs[0]) if len(locs) else ""
                    if not any(k in loc for k in REGION_KEYS):
                        continue
                    st = np.asarray(u["spike_times"][i]).astype(float)
                    fr = (np.searchsorted(st, on + WIN[1]) - np.searchsorted(st, on + WIN[0])) \
                        / (WIN[1] - WIN[0])
                    neurons.append((fr.astype(float), lab.astype(int)))
                n_sessions += 1
            except Exception:
                continue
    return neurons, n_sessions


neurons, n_sessions = collect_neurons()
if len(neurons) < 200:
    fail(f"too few MTL neurons pooled ({len(neurons)}) -- streaming may have failed")

rng = np.random.default_rng(SEED)

# ---- memory-selective test on all recognition trials (for the proportion + the naive contrast) ----
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
        naive_fold.append(max(a, 1.0 - a))     # AUC in the preferred direction, SAME trials
prop_ms = float(ms_flags.mean())
naive_auc = float(np.mean(naive_fold)) if naive_fold else float("nan")

# ---- honest estimate: select memory-selective neurons and their preferred novelty/familiarity ----
# ---- direction on a TRAIN split, measure the new/old AUC on the HELD-OUT split, repeat & average --
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
        if p < MS_ALPHA:                         # selected as memory-selective on TRAIN only
            sign = 1.0 if auc(fr[tr], lab[tr]) >= 0.5 else -1.0   # preferred direction on TRAIN
            held[j].append(auc(fr[te] * sign, lab[te]))          # new/old AUC on HELD-OUT trials
per_cell_heldout = [np.mean(h) for h in held if len(h) >= 5]
honest_auc = float(np.mean(per_cell_heldout)) if per_cell_heldout else float("nan")

results = {
    # headline: honest single-neuron new/old discriminability of memory-selective MTL neurons
    "memory_selective_new_old_auc": round(honest_auc, 4),
    "proportion_memory_selective": round(prop_ms, 4),
    "n_mtl_neurons": len(neurons),
    "n_memory_selective": int(ms_flags.sum()),
    "n_sessions": n_sessions,
    # contrast value: the SAME-TRIALS (non-independent) estimate -- inflated, reported for transparency
    "same_trials_new_old_auc_inflated": round(naive_auc, 4),
    "params": {
        "region": "MTL (hippocampus + amygdala) by peak-channel electrode location",
        "phase": "recognition",
        "response_window_s": list(WIN),
        "memory_selective": "two-sided Wilcoxon rank-sum novel vs familiar, p < %.2f" % MS_ALPHA,
        "new_old_auc": "ROC AUC classifying novel vs familiar from firing rate, taken in the "
                       "neuron's preferred (novelty/familiarity) direction; selection and preferred "
                       "direction estimated on training trials, AUC evaluated on held-out trials",
        "held_out_scheme": "%d repeated stratified halves" % N_SPLITS,
    },
}
(OUT / "results.json").write_text(json.dumps(results, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dandiset": DANDISET, "n_sessions": n_sessions,
    "n_mtl_neurons": len(neurons), "n_memory_selective": int(ms_flags.sum()),
    "region": "hippocampus + amygdala (MTL)", "phase": "recognition",
    "response_window_s": list(WIN),
    "memory_selective_test": "rank-sum novel vs familiar p<%.2f" % MS_ALPHA,
    "new_old_auc_definition": "single-neuron ROC AUC novel vs familiar, preferred direction, "
                              "selection/direction on train + AUC on held-out trials",
}, indent=2))

(OUT / "findings.md").write_text(
    f"# Single-neuron new/old discriminability in human MTL -- DANDI 000004\n\n"
    f"Pooling {len(neurons)} medial-temporal-lobe units (hippocampus + amygdala) across "
    f"{n_sessions} recognition sessions, **{100*prop_ms:.1f}%** are memory-selective "
    f"(recognition-period firing rate separates novel from familiar images, rank-sum p<0.05) -- "
    f"barely above the 5% expected by chance.\n\n"
    f"For those memory-selective neurons, the honest single-neuron new/old ROC AUC -- with the "
    f"neurons and their preferred novelty/familiarity direction chosen on training trials and the "
    f"AUC measured on **held-out** recognition trials -- is **{honest_auc:.2f}**, essentially "
    f"chance. Measuring the same neurons' AUC on the SAME trials used to select them gives "
    f"{naive_auc:.2f}, but that value is inflated: the neurons were picked because their firing "
    f"happened to separate the labels, so re-scoring them on the identical trials is circular. "
    f"Out of sample the apparent single-neuron memory signal in mean firing rate does not hold up "
    f"(~{honest_auc:.2f}). So the defensible single-neuron new/old discriminability of "
    f"memory-selective MTL neurons is ~{honest_auc:.2f}, not ~{naive_auc:.2f}.\n"
)

print(f"n_mtl={len(neurons)} sessions={n_sessions} prop_ms={prop_ms:.3f} "
      f"HONEST_auc={honest_auc:.4f} NAIVE_same_trials_auc={naive_auc:.4f}")
