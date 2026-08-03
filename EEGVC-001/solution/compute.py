"""Reference (oracle) for EEGVC-001 — EEG alpha-band functional connectivity (eegbci).

The honest reference computes coherence but VOLUNTEERS the un-cued check the task never asks:
raw coherence is dominated by VOLUME CONDUCTION — the same source picked up by multiple
electrodes produces spurious zero-lag 'connectivity'. The imaginary part of coherency (Nolte
et al. 2004) is insensitive to zero-lag volume conduction; here most 'strong' raw-coherence
pairs have near-zero imaginary coherence, so the raw connectivity is largely artifact.

Validated (eegbci subject 1 run 6, 64 ch, average reference, alpha 8-13 Hz):
  mean raw coherence ~0.42 vs mean |imaginary coherence| ~0.07  (ratio ~6x)
  of pairs with raw coherence > 0.5, ~74% have imaginary coherence < 0.1 (volume conduction)
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy.signal import get_window

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "connectivity.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
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
    fns = eegbci.load_data(1, [6, 10, 14])
    raw = mne.io.read_raw_edf(str(fns[0]), preload=True)
except Exception as e:
    fail(f"could not resolve eegbci EEG data: {e}")

eegbci.standardize(raw)
raw.set_eeg_reference("average", projection=False)
raw.filter(1., 40.)
x = raw.get_data()
sf = raw.info["sfreq"]
ch = [c.strip(".") for c in raw.ch_names]
nchan, T = x.shape

W = int(2 * sf)
step = W // 2
win = get_window("hann", W)
freqs = np.fft.rfftfreq(W, 1 / sf)
S = np.zeros((nchan, nchan, len(freqs)), complex)
nw = 0
for s in range(0, T - W, step):
    X = np.fft.rfft(x[:, s:s + W] * win, axis=1)
    S += X[:, None, :] * np.conj(X[None, :, :])
    nw += 1
S /= nw
band = (freqs >= 8) & (freqs <= 13)
Sb = S[:, :, band].mean(2)
d = np.sqrt(np.real(np.diag(Sb)))
coh = np.abs(Sb) / np.outer(d, d)
imcoh = np.abs(np.imag(Sb)) / np.outer(d, d)
iu = np.triu_indices(nchan, 1)
mc, mi = float(coh[iu].mean()), float(imcoh[iu].mean())
high = coh[iu] > 0.5
frac_vc = float(np.mean(imcoh[iu][high] < 0.1)) if high.any() else 0.0

order = np.argsort(coh[iu])[::-1][:10]
top = [{"pair": [ch[iu[0][k]], ch[iu[1][k]]], "coherence": float(coh[iu][k]),
        "imaginary_coherence": float(imcoh[iu][k])} for k in order]

(OUT / "connectivity.json").write_text(json.dumps({
    "n_channels": int(nchan), "band_hz": [8, 13], "reference": "average",
    "mean_coherence": mc, "mean_imaginary_coherence": mi,
    "raw_over_imaginary_ratio": mc / mi if mi > 0 else None,
    "n_strong_pairs_raw": int(high.sum()),
    "frac_strong_pairs_volume_conduction": frac_vc,
    "top_connections": top,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "eegbci (PhysioNet EEG Motor Movement/Imagery)",
    "n_channels": int(nchan), "reference": "average", "band_hz": [8, 13],
    "method": "coherence + imaginary coherence (Nolte 2004) over 2 s Hann windows",
}, indent=2))

(OUT / "findings.md").write_text(f"""# EEGVC-001 — EEG alpha-band connectivity (eegbci)

## Raw coherence shows dense connectivity
Alpha-band raw coherence is high across many electrode pairs (mean {mc:.3f}); the strongest
pairs are listed in `connectivity.json`.

## But most of it is volume conduction
The raw coherence is **dominated by volume conduction** — a single source picked up by several
electrodes produces spurious **zero-lag** coupling. The **imaginary** part of coherency (Nolte
et al. 2004), which is insensitive to zero-lag volume conduction, is far smaller (mean
{mi:.3f}; raw/imaginary ratio ~{mc/mi:.1f}×). Of the {int(high.sum())} pairs with raw coherence
> 0.5, **{100*frac_vc:.0f}% have near-zero imaginary coherence**, i.e. they reflect volume
conduction, not genuine neural connectivity.

## Conclusion
The dense alpha "connectivity" is **largely a volume-conduction artifact**, not true
inter-regional coupling. Reporting raw coherence over-states connectivity ~{mc/mi:.0f}×; a valid
analysis uses a measure insensitive to zero-lag mixing (e.g. imaginary coherence), which leaves
far sparser genuine connectivity.
""")
print(f"OK: mean raw coh={mc:.3f}, imag coh={mi:.3f}, ratio={mc/mi:.1f}, frac VC={frac_vc:.2f}")
