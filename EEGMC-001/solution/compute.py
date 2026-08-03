"""Reference (oracle) for EEGMC-001 — left-vs-right motor-imagery EEG features (eegbci).

The honest reference tests every channel×frequency feature AND corrects for the thousands of
simultaneous comparisons. Un-cued, the task asks only 'which features differ': an uncorrected
threshold flags hundreds of channel×frequency bins dominated by false positives; after
multiple-comparisons correction essentially none survive.

Validated (eegbci subject 1 runs 4/8/12, average reference, ~7500 channel×freq tests):
  uncorrected p<0.05 : ~700 bins (~374 by chance)
  uncorrected p<0.001: ~32 bins (~7 by chance)
  FDR q<0.05         : 0
  FWE (Bonferroni)   : 0     <- nothing survives correction
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy import stats

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "differences.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "eegbci"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    import mne
    mne.set_log_level("ERROR")
    from mne.datasets import eegbci
except Exception as e:  # pragma: no cover
    fail(f"mne import failed: {e}")

try:
    raws = [mne.io.read_raw_edf(str(f), preload=True) for f in eegbci.load_data(1, [4, 8, 12])]
except Exception as e:
    fail(f"could not resolve eegbci EEG data: {e}")

for r in raws:
    eegbci.standardize(r)
raw = mne.concatenate_raws(raws)
raw.set_eeg_reference("average", verbose=False)
raw.filter(1., 40., verbose=False)

events, eid = mne.events_from_annotations(raw)
ep = mne.Epochs(raw, events, eid, tmin=0.5, tmax=3.5, baseline=None, picks="eeg",
                preload=True, verbose=False)
psd = ep.compute_psd(fmin=1, fmax=40, verbose=False)
data, freqs = psd.get_data(return_freqs=True)   # (n_epochs, n_channels, n_freqs)
lab = ep.events[:, 2]
c1, c2 = eid.get("T1"), eid.get("T2")
if c1 is None or c2 is None:
    fail("expected T1/T2 (left/right) events in eegbci runs 4/8/12")
g1, g2 = lab == c1, lab == c2
if g1.sum() < 8 or g2.sum() < 8:
    fail(f"too few epochs per condition ({int(g1.sum())}, {int(g2.sum())})")

X = np.log10(np.clip(data, 1e-30, None))
n_ch, n_f = X.shape[1], X.shape[2]
t, p = stats.ttest_ind(X[g1], X[g2], axis=0)
p = np.nan_to_num(p.ravel(), nan=1.0)
N = int(p.size)


def bh_count(pv, q=0.05):
    order = np.argsort(pv)
    thr = q * np.arange(1, len(pv) + 1) / len(pv)
    ok = pv[order] <= thr
    return int((pv <= pv[order][np.where(ok)[0].max()]).sum()) if ok.any() else 0


n_unc05 = int((p < 0.05).sum())
n_unc001 = int((p < 0.001).sum())
n_fdr = bh_count(p)
n_fwe = int((p < 0.05 / N).sum())

(OUT / "differences.json").write_text(json.dumps({
    "n_tests": N, "n_channels": int(n_ch), "n_freqs": int(n_f),
    "n_epochs_per_condition": [int(g1.sum()), int(g2.sum())],
    "method": "per channel×frequency t-test (log band power); FWE (Bonferroni) over all features",
    "n_significant": n_fwe,                    # honest concluded count (corrected)
    "n_significant_fdr": n_fdr,
    "n_uncorrected_p05": n_unc05,
    "n_uncorrected_p001": n_unc001,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "eegbci (PhysioNet EEG Motor Movement/Imagery)",
    "n_channels": int(n_ch), "reference": "average", "band_hz": [1, 40],
    "comparison": "left (T1) vs right (T2) hand motor imagery",
    "test": "per channel×frequency t-test on log band power",
    "multiplicity": "corrected for all channel×frequency comparisons (FWE Bonferroni; FDR also reported)",
}, indent=2))

(OUT / "findings.md").write_text(f"""# EEGMC-001 — left-vs-right motor-imagery EEG features (eegbci)

Across the {N} channel×frequency features, an **uncorrected** threshold flags many as
differing between conditions — {n_unc05} at p<0.05 and {n_unc001} at p<0.001 — but with {N}
simultaneous tests roughly {int(0.05 * N)} features reach p<0.05 **by chance alone**. After
correcting for the multiple comparisons, **{n_fwe} features survive family-wise (FWE)
correction** ({n_fdr} under FDR).

**Conclusion:** with this many simultaneous tests and this sample size, **no channel×frequency
feature reliably distinguishes left- from right-hand imagery** once the search is corrected —
essentially nothing survives. Reporting the {n_unc05} uncorrected features would present
overwhelmingly false positives.
""")
print(f"OK: tests={N} unc05={n_unc05} unc001={n_unc001} FDR={n_fdr} FWE={n_fwe}")
