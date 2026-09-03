"""Reference solution for VISCAT-001.

Deliverable: from the human medial-temporal-lobe (MTL) single-neuron recordings in the new/old
recognition-memory task (DANDI 000004, Faraut/Rutishauser), report how well an individual
visually-category-selective MTL neuron discriminates its preferred visual category from the other
categories during the recognition phase -- the mean single-neuron preferred-category-vs-rest ROC AUC
across the category-selective neurons -- together with the proportion of MTL neurons that are
category-selective.

Each recognition trial shows an image drawn from one of five visual categories (houses, landscapes,
mobility/vehicles, phones, small animals; `stimCategory` in {1..5}). A neuron is "category-selective"
because its firing rate differs across the five categories, and each such neuron has a "preferred"
category (the one it fires most for). The preferred-category-vs-rest AUC then measures how well the
neuron's firing separates its preferred category from the rest.

The correct analysis keeps the neuron SELECTION and preferred-category assignment independent of the
AUC ESTIMATE. If you (a) call a neuron category-selective and (b) pick its preferred category on a
set of trials, and then (c) measure the preferred-vs-rest AUC on those SAME trials, the AUC is
inflated by a winner's curse (non-independence / "double dipping", Kriegeskorte et al. 2009): among
five categories you pick the one whose noise happened to give the highest firing, and on the same
trials that noise still separates it from the rest. The honest estimate selects the category-selective
neurons and fixes their preferred category on one split of the recognition trials and measures the
preferred-vs-rest AUC on a held-out split.

Validated ground truth (DANDI 000004, ALL sessions pooled; MTL = hippocampus + amygdala units by
electrode location; recognition phase; per-trial firing rate over the [0.2, 1.7] s window after
stimulus onset; category-selective = Kruskal-Wallis across the five categories p < 0.05; preferred
category = highest mean firing rate; preferred-vs-rest AUC in the neuron's preferred direction):
  n MTL neurons pooled                 = ~1864
  proportion category-selective        = ~0.167
  NAIVE  mean preferred-vs-rest AUC, selected AND measured on the SAME trials   = ~0.70
  CORRECT mean preferred-vs-rest AUC, selection/preferred on train, AUC on held-out = ~0.57
Unlike a null signal, visual-category selectivity is a genuine positive effect: the honest held-out
preferred-vs-rest AUC (~0.57) stays clearly above chance (and the category-selective fraction, ~0.17,
is well above the 0.05 chance false-positive rate). But the SAME-trials estimate (~0.70) materially
overstates it. A reported ~0.70 fails the match.
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
CATS = (1, 2, 3, 4, 5)    # the five visual categories (stimCategory)
SEL_ALPHA = 0.05          # category-selective: Kruskal-Wallis across the five categories
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
    from scipy.stats import kruskal, rankdata
except Exception as e:  # pragma: no cover
    fail(f"missing dependency: {e}")


def auc_pref_vs_rest(scores, is_pref):
    """ROC AUC that the preferred-category trials (is_pref==1) have higher firing than the rest."""
    is_pref = np.asarray(is_pref).astype(int)
    npos = int(is_pref.sum())
    nneg = len(is_pref) - npos
    if npos == 0 or nneg == 0:
        return 0.5
    r = rankdata(scores)
    return float((r[is_pref == 1].sum() - npos * (npos + 1) / 2.0) / (npos * nneg))


def selective_and_preferred(fr, cat):
    """(p-value of the across-category Kruskal-Wallis test, preferred category by mean firing rate)."""
    groups = [fr[cat == c] for c in CATS if (cat == c).sum() > 0]
    try:
        _, p = kruskal(*groups)
    except Exception:
        p = 1.0
    means = np.array([fr[cat == c].mean() if (cat == c).sum() > 0 else -np.inf for c in CATS])
    pref = CATS[int(np.argmax(means))]
    return float(p), pref


def collect_neurons():
    """Stream every session's recognition-phase MTL spiking; return list of (fr, cat) per neuron.

    fr = per-recognition-trial firing rate in the [0.2, 1.7] s window; cat = the trial's visual
    category (stimCategory, 1..5). Only the MTL units' spike_times are read, so streaming stays light.
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
                cat = rec["stimCategory"].values.astype(int)
                if len(on) < 20 or len(np.unique(cat)) < len(CATS):
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
                    neurons.append((fr.astype(float), cat.astype(int)))
                n_sessions += 1
            except Exception:
                continue
    return neurons, n_sessions


neurons, n_sessions = collect_neurons()
if len(neurons) < 200:
    fail(f"too few MTL neurons pooled ({len(neurons)}) -- streaming may have failed")

rng = np.random.default_rng(SEED)

# ---- category-selective test on all recognition trials (for the proportion + the naive contrast) ----
sel_flags = np.zeros(len(neurons), dtype=bool)
naive_auc_list = []
for j, (fr, cat) in enumerate(neurons):
    p, pref = selective_and_preferred(fr, cat)
    if p < SEL_ALPHA:
        sel_flags[j] = True
        naive_auc_list.append(auc_pref_vs_rest(fr, cat == pref))   # SAME trials -> inflated
prop_sel = float(sel_flags.mean())
naive_auc = float(np.mean(naive_auc_list)) if naive_auc_list else float("nan")

# ---- honest estimate: select the category-selective neurons and fix their preferred category on a ----
# ---- TRAIN split, measure the preferred-vs-rest AUC on the HELD-OUT split, repeat and average --------
held = [[] for _ in neurons]
for rep in range(N_SPLITS):
    for j, (fr, cat) in enumerate(neurons):
        n = len(fr)
        idx = np.arange(n)
        tr = []
        for c in CATS:
            ci = idx[cat == c]
            if len(ci) < 2:
                continue
            ci = ci.copy()
            rng.shuffle(ci)
            tr.extend(ci[:len(ci) // 2])
        tr = np.array(sorted(tr))
        te = np.setdiff1d(idx, tr)
        if len(tr) < 8 or len(te) < 8:
            continue
        p, pref = selective_and_preferred(fr[tr], cat[tr])   # selection + preferred on TRAIN only
        if p < SEL_ALPHA:
            held[j].append(auc_pref_vs_rest(fr[te], cat[te] == pref))   # AUC on HELD-OUT trials
per_cell_heldout = [np.mean(h) for h in held if len(h) >= 5]
honest_auc = float(np.mean(per_cell_heldout)) if per_cell_heldout else float("nan")

results = {
    # headline: honest single-neuron preferred-category-vs-rest discriminability of category cells
    "category_selective_pref_vs_rest_auc": round(honest_auc, 4),
    "proportion_category_selective": round(prop_sel, 4),
    "n_mtl_neurons": len(neurons),
    "n_category_selective": int(sel_flags.sum()),
    "n_sessions": n_sessions,
    # contrast value: the SAME-TRIALS (non-independent) estimate -- inflated, reported for transparency
    "same_trials_pref_vs_rest_auc_inflated": round(naive_auc, 4),
    "params": {
        "region": "MTL (hippocampus + amygdala) by peak-channel electrode location",
        "phase": "recognition",
        "response_window_s": list(WIN),
        "categories": "five visual categories (stimCategory 1..5)",
        "category_selective": "Kruskal-Wallis across the five categories, p < %.2f" % SEL_ALPHA,
        "pref_vs_rest_auc": "ROC AUC classifying the preferred category vs the other four from firing "
                            "rate; neuron selection and preferred category estimated on training "
                            "trials, AUC evaluated on held-out trials",
        "held_out_scheme": "%d repeated stratified halves" % N_SPLITS,
    },
}
(OUT / "results.json").write_text(json.dumps(results, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dandiset": DANDISET, "n_sessions": n_sessions,
    "n_mtl_neurons": len(neurons), "n_category_selective": int(sel_flags.sum()),
    "region": "hippocampus + amygdala (MTL)", "phase": "recognition",
    "response_window_s": list(WIN),
    "category_selective_test": "Kruskal-Wallis across five visual categories p<%.2f" % SEL_ALPHA,
    "pref_vs_rest_auc_definition": "single-neuron ROC AUC preferred category vs the other four, "
                                   "selection/preferred category on train + AUC on held-out trials",
}, indent=2))

(OUT / "findings.md").write_text(
    f"# Single-neuron visual-category selectivity in human MTL -- DANDI 000004\n\n"
    f"Pooling {len(neurons)} medial-temporal-lobe units (hippocampus + amygdala) across "
    f"{n_sessions} recognition sessions, **{100*prop_sel:.1f}%** are category-selective "
    f"(recognition-period firing rate differs across the five visual categories, "
    f"Kruskal-Wallis p<0.05).\n\n"
    f"Estimating each category-selective neuron's preferred category on one split of the recognition "
    f"trials and measuring its preferred-category-vs-rest ROC AUC on a held-out split gives a mean "
    f"single-neuron AUC of **{honest_auc:.3f}**. This stays clearly above chance (0.5), so visual-"
    f"category selectivity is a genuine single-neuron signal in the human MTL -- but it is more modest "
    f"than the {naive_auc:.3f} obtained when the same trials are used to pick the preferred category "
    f"and to score the AUC, which is inflated by selection (a winner's curse over the five "
    f"categories).\n\n"
    f"Reported headline: mean held-out preferred-category-vs-rest AUC = **{honest_auc:.3f}** "
    f"(proportion category-selective = {prop_sel:.3f}).\n")

print(f"n_mtl_neurons={len(neurons)} n_sessions={n_sessions} prop_sel={prop_sel:.4f} "
      f"honest_auc={honest_auc:.4f} naive_auc={naive_auc:.4f}")
