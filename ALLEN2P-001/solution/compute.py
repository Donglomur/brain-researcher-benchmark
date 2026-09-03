"""Reference solution for ALLEN2P-001.

Deliverable: the fraction of imaged neurons in a two-photon field of primary visual cortex (VISp)
that are orientation- or direction-selective (OSI > 0.5 or DSI > 0.5) in their responses to
drifting gratings, from one Allen Brain Observatory experiment (de Vries et al. 2020,
ophys_experiment_id 501271265, VISp, three_session_A).

The correct analysis avoids an off-critical-path error that inflates the fraction. OSI and DSI are
*ratio contrast statistics* -- (R_pref - R_orth)/(R_pref + R_orth) with the preferred condition
chosen as the argmax of the mean response over the 8 x n_tf grating conditions. If the preferred
condition is chosen on the same trials that are then used to measure R_pref, R_orth and R_null,
the selection is a winner's-curse: R_pref is biased upward by having been picked as the maximum of
noisy per-condition estimates, so OSI/DSI are biased high and a large fraction of neurons -- even
neurons that are not really tuned -- clear the 0.5 threshold. This is textbook circular analysis
(double dipping).

The honest estimate breaks the circularity: the preferred (direction, temporal-frequency)
condition is chosen on one set of trials and OSI/DSI are then measured on a disjoint, held-out set
of trials. Averaged over repeated random halves this gives an unbiased selective fraction that is
much lower than the same-trials number and is stable across the split scheme.

Validated ground truth (ophys_experiment_id 501271265, VISp, drifting gratings, per-trial response
= mean dF/F over the presentation window, preferred (direction, temporal frequency), OSI =
(R_pref-R_orth)/(R_pref+R_orth), DSI = (R_pref-R_null)/(R_pref+R_null), selective if OSI>0.5 or
DSI>0.5, denominator = all imaged neurons) -- filled in from the Step-0 reproduction:
  n imaged neurons (all)                                  = 215
  NAIVE  (select-and-test on same trials) frac selective  = ~0.78   (double-dipping inflated)
  CORRECT (held-out preferred-condition selection)        = ~0.55   <-- reported
The held-out value is stable across split schemes (50/50, odd/even, 80/20: 0.50-0.61). A reported
~0.78 fails the numeric match.
"""
import json
import os
import sys
import time
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

EXP_ID = 501271265
REGION = "VISp"
STIMULUS = "drifting_gratings"
SI_THRESHOLD = 0.5
N_SPLITS = 50          # repeated random halves for a stable held-out estimate
SEED = 0
MANIFEST = os.environ.get("BOC_MANIFEST", "/app/boc_cache/manifest.json")


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason,
         "ophys_experiment_id": EXP_ID}, indent=2))
    (OUT / "results.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def _retry(fn, what, n=8):
    """The Allen Institute API intermittently returns 502s; retry with backoff."""
    last = None
    for a in range(n):
        try:
            return fn()
        except Exception as ex:  # noqa: BLE001
            last = ex
            sys.stderr.write(f"[retry {a}] {what}: {type(ex).__name__}: {str(ex)[:90]}\n")
            time.sleep(4 + a * 3)
    raise RuntimeError(f"{what} failed after {n} attempts: {last}")


# ---- open the ONE experiment at runtime via the Allen Brain Observatory cache (no creds) ----
try:
    from allensdk.core.brain_observatory_cache import BrainObservatoryCache
    Path(MANIFEST).parent.mkdir(parents=True, exist_ok=True)
    boc = BrainObservatoryCache(manifest_file=MANIFEST)
    data_set = _retry(lambda: boc.get_ophys_experiment_data(EXP_ID), "get_ophys_experiment_data")
except Exception as e:  # noqa: BLE001
    fail(f"could not open Allen Brain Observatory experiment {EXP_ID}: {e}")

# ---- dF/F traces, cells, stimulus table ----
try:
    _, dff = data_set.get_dff_traces()          # (n_cells, n_frames)
    cell_ids = list(data_set.get_cell_specimen_ids())
    meta = data_set.get_metadata()
    stim = data_set.get_stimulus_table(STIMULUS)
except Exception as e:  # noqa: BLE001
    fail(f"experiment {EXP_ID} lacks dF/F traces or {STIMULUS} table: {e}")

nU = dff.shape[0]
if nU < 20:
    fail(f"too few imaged neurons ({nU})")

ori = stim["orientation"].values.astype(float)
tf = stim["temporal_frequency"].values.astype(float)
starts = stim["start"].values.astype(int)
ends = stim["end"].values.astype(int)
is_blank = np.isnan(ori) | np.isnan(tf)
if "blank_sweep" in stim.columns:
    is_blank = is_blank | (stim["blank_sweep"].values.astype(float) > 0)
ori0 = np.where(np.isnan(ori), 0.0, ori)
tf0 = np.where(np.isnan(tf), 0.0, tf)
ntr = len(stim)
if ntr < 100 or is_blank.all():
    fail(f"too few / degenerate {STIMULUS} presentations ({ntr})")

# ---- per-trial response: mean dF/F over the presentation window ----
msr = np.full((nU, ntr), np.nan)
for ti in range(ntr):
    a, b = int(starts[ti]), int(ends[ti])
    if b <= a:
        b = a + 1
    msr[:, ti] = dff[:, a:b].mean(axis=1)

orivals = np.array(sorted(set(ori0[~is_blank].tolist())))     # 8 drift directions
tfvals = np.array(sorted(set(tf0[~is_blank].tolist())))       # non-blank temporal frequencies
if len(orivals) < 8 or len(tfvals) < 2:
    fail(f"unexpected grating grid: {len(orivals)} directions x {len(tfvals)} temporal freqs")


def response_matrix(trial_mask):
    """mean response per (direction, temporal_frequency) -> (nU, nDir, nTf) over the given trials."""
    R = np.full((nU, len(orivals), len(tfvals)), np.nan)
    for oi, o in enumerate(orivals):
        for tj, t in enumerate(tfvals):
            cols = np.where(trial_mask & (~is_blank) & (ori0 == o) & (tf0 == t))[0]
            if len(cols):
                R[:, oi, tj] = msr[:, cols].mean(axis=1)
    return R


def osi_dsi(R_select, R_measure):
    """OSI/DSI per neuron: preferred (direction, tf) is the argmax of R_select; the indices
    R_pref/R_orth/R_null are then read off R_measure (held-out when R_measure != R_select)."""
    osi = np.full(nU, np.nan)
    dsi = np.full(nU, np.nan)
    for c in range(nU):
        Rs = R_select[c]
        Rm = R_measure[c]
        if np.all(np.isnan(Rs)) or np.all(np.isnan(Rm)):
            continue
        po, pt = np.unravel_index(np.nanargmax(Rs), Rs.shape)
        r_pref = Rm[po, pt]
        r_orth = (Rm[(po + 2) % 8, pt] + Rm[(po - 2) % 8, pt]) / 2.0
        r_null = Rm[(po + 4) % 8, pt]
        osi[c] = (r_pref - r_orth) / (r_pref + r_orth) if (r_pref + r_orth) != 0 else np.nan
        dsi[c] = (r_pref - r_null) / (r_pref + r_null) if (r_pref + r_null) != 0 else np.nan
    return osi, dsi


def selective_fraction(osi, dsi):
    return float(np.sum((osi > SI_THRESHOLD) | (dsi > SI_THRESHOLD)) / nU)


# ---- NAIVE contrast: choose the preferred condition and measure OSI/DSI on the SAME trials ----
R_all = response_matrix(np.ones(ntr, bool))
osi_same, dsi_same = osi_dsi(R_all, R_all)
frac_naive = selective_fraction(osi_same, dsi_same)

# ---- CORRECT: preferred condition chosen on one half, OSI/DSI measured on the held-out half ----
rng = np.random.default_rng(SEED)
frac_splits = []
for _ in range(N_SPLITS):
    half = rng.random(ntr) < 0.5
    R_a = response_matrix(half)
    R_b = response_matrix(~half)
    # symmetric: select on A measure on B, and select on B measure on A
    o1, d1 = osi_dsi(R_a, R_b)
    o2, d2 = osi_dsi(R_b, R_a)
    frac_splits.append(0.5 * (selective_fraction(o1, d1) + selective_fraction(o2, d2)))
frac_correct = float(np.mean(frac_splits))
frac_correct_sd = float(np.std(frac_splits))
n_selective = int(round(frac_correct * nU))

results = {
    # the value that should be REPORTED: unbiased, held-out selective fraction
    "selective_fraction": round(frac_correct, 4),
    "n_neurons_total": int(nU),
    "n_neurons_analyzed": int(nU),          # denominator = all imaged neurons
    "n_selective": n_selective,
    "osi_dsi_threshold": SI_THRESHOLD,
    "selective_fraction_sd_across_splits": round(frac_correct_sd, 4),
    "same_trials_no_holdout_fraction": round(frac_naive, 4),   # inflated contrast, for reference
    "params": {
        "region": REGION,
        "selectivity": "OSI=(R_pref-R_orth)/(R_pref+R_orth), DSI=(R_pref-R_null)/(R_pref+R_null) "
                       "at preferred (direction, temporal frequency)",
        "preferred_condition_selection": "chosen on held-out trials, OSI/DSI measured on the "
                                         f"complementary trials, averaged over {N_SPLITS} random halves",
        "response": "mean dF/F over the presentation window",
        "stimulus": "drifting_gratings (8 directions x temporal frequencies)",
    },
}
(OUT / "results.json").write_text(json.dumps(results, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "ophys_experiment_id": EXP_ID,
    "targeted_structure": meta.get("targeted_structure"),
    "session_type": meta.get("session_type"),
    "cre_line": meta.get("cre_line"),
    "n_neurons_total": int(nU),
    "n_neurons_analyzed": int(nU),
    "n_gratings_presentations": int(np.sum(~is_blank)),
    "selectivity_definition": "OSI=(R_pref-R_orth)/(R_pref+R_orth); DSI=(R_pref-R_null)/(R_pref+R_null)",
    "osi_dsi_threshold": SI_THRESHOLD,
    "preferred_condition_selection": "held-out trials (disjoint from the trials used to measure "
                                     "OSI/DSI), averaged over repeated random halves",
}, indent=2))

(OUT / "findings.md").write_text(
    f"# Orientation-/direction-selective fraction in VISp -- Allen Brain Observatory {EXP_ID}\n\n"
    f"Of {nU} neurons imaged in this VISp field, an estimated **{n_selective}/{nU} = "
    f"{frac_correct:.2f}** are orientation- or direction-selective to the drifting gratings "
    f"(OSI > {SI_THRESHOLD} or DSI > {SI_THRESHOLD} at the preferred temporal frequency), when each "
    f"neuron's preferred (direction, temporal frequency) condition is chosen on one set of trials "
    f"and OSI/DSI are measured on a disjoint held-out set. This held-out estimate is stable across "
    f"the split scheme (standard deviation {frac_correct_sd:.02f} over random halves).\n\n"
    f"For contrast, choosing each neuron's preferred condition and measuring OSI/DSI on the *same* "
    f"trials gives {frac_naive:.2f}. That number is inflated: the preferred condition is the argmax "
    f"of noisy per-condition estimates, so R_pref carries an upward selection bias (a winner's "
    f"curse) and OSI/DSI -- ratio contrast statistics -- are pushed high even for neurons that are "
    f"not genuinely tuned. The honest, held-out selective fraction of this field is "
    f"~{frac_correct:.2f}.\n"
)

print(f"EXP={EXP_ID} nCells={nU} nSel={n_selective} "
      f"CORRECT(held-out)={frac_correct:.4f}+/-{frac_correct_sd:.4f} NAIVE(same-trials)={frac_naive:.4f}")
