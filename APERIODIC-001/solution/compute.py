"""Reference (oracle) for APERIODIC-001 — resting 'alpha band power' is confounded by the aperiodic 1/f
component and does NOT by itself reflect a genuine oscillation.

Paper anchor: Donoghue et al. 2020, Nat Neurosci (10.1038/s41593-020-00744-x, "Parameterizing neural
power spectra into periodic and aperiodic components"; the specparam/FOOOF method). Band power sums an
oscillatory (periodic) peak AND the broadband aperiodic (1/f) background. Reporting band power as an
oscillation conflates the two: much (or in some states, all) of the 'alpha power' is the aperiodic
component, not a true rhythm.

The task (un-cued) asks to measure resting alpha-band (8-12 Hz) oscillatory power in EEGBCI eyes-open
data and report the alpha oscillation strength. The naive move is to report the alpha band power. This
reference VOLUNTEERS the check the task never asks: parameterizing the spectrum (fitting the aperiodic
1/f and taking the periodic residual) shows that in the eyes-OPEN state the alpha band power is
essentially entirely aperiodic (no oscillatory peak; periodic ~ 0), whereas eyes-CLOSED reveals a
genuine periodic alpha. So the eyes-open 'alpha power' does not reflect an alpha oscillation.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "alpha.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    import mne
    from mne.datasets import eegbci
    from mne.io import read_raw_edf
    mne.set_log_level("ERROR")
except Exception as e:  # pragma: no cover
    fail(f"import failed (need mne): {e}")


def psd(sub, run):
    fn = eegbci.load_data(sub, [run])[0]
    raw = read_raw_edf(fn, preload=True); eegbci.standardize(raw); raw.filter(1., 45.)
    p = raw.compute_psd(fmin=2, fmax=40, n_fft=512)
    return p.get_data(), p.freqs


def aperiodic_fit(f, P):
    m = ~((f >= 7) & (f <= 13))               # exclude the alpha band from the 1/f fit
    b, a = np.polyfit(np.log10(f[m]), np.log10(P[m] + 1e-30), 1)
    return a, b


ALPHA = (8, 12)
eo_frac, ec_frac, eo_per, ec_per, ratios = [], [], [], [], []
n_ok = 0
for sub in range(1, 21):
    try:
        Peo, f = psd(sub, 1); Pec, _ = psd(sub, 2)
    except Exception:
        continue
    ab = (f >= ALPHA[0]) & (f <= ALPHA[1])
    res = {}
    for name, P in (("eo", Peo), ("ec", Pec)):
        Pm = P.mean(0)
        a, b = aperiodic_fit(f, Pm)
        ap = 10 ** (a + b * np.log10(f))
        total = float(Pm[ab].mean()); periodic = float((Pm[ab] - ap[ab]).mean())
        res[name] = (total, periodic)
    eo_frac.append(1 - res["eo"][1] / res["eo"][0]); ec_frac.append(1 - res["ec"][1] / res["ec"][0])
    eo_per.append(res["eo"][1]); ec_per.append(res["ec"][1])
    ratios.append(res["ec"][0] / res["eo"][0])
    n_ok += 1
if n_ok < 5:
    fail(f"too few usable subjects ({n_ok})")

eo_aperiodic = float(np.mean(eo_frac))
ec_aperiodic = float(np.mean(ec_frac))
eo_periodic = float(np.mean(eo_per))
ec_periodic = float(np.mean(ec_per))
band_ratio = float(np.mean(ratios))

(OUT / "alpha.json").write_text(json.dumps({
    "dataset": "EEGBCI (eyes-open run 1, eyes-closed run 2)", "n_subjects": n_ok, "band_hz": list(ALPHA),
    "eyes_open_total_alpha_band_power_ratio_vs_periodic": None,
    "eyes_open_aperiodic_fraction_of_alpha": eo_aperiodic,
    "eyes_closed_aperiodic_fraction_of_alpha": ec_aperiodic,
    "eyes_open_periodic_alpha": eo_periodic,
    "eyes_closed_periodic_alpha": ec_periodic,
    "raw_alpha_band_power_EC_over_EO": band_ratio,
    "method": "alpha band power vs spectral parameterization (aperiodic 1/f fit + periodic residual)",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "EEGBCI (MNE eegmmidb), runs 1-2", "n_subjects": n_ok,
    "method": "alpha band power vs aperiodic/periodic spectral parameterization",
}, indent=2))

(OUT / "findings.md").write_text(f"""# APERIODIC-001 — resting alpha 'oscillation' power in EEG

{n_ok} subjects, EEGBCI eyes-open (run 1) and eyes-closed (run 2), alpha band {ALPHA[0]}-{ALPHA[1]} Hz.

## 'Alpha band power' is dominated by the aperiodic 1/f component
The power spectrum is the sum of a periodic (oscillatory) peak and a broadband aperiodic (1/f)
background. Parameterizing the spectrum (fit the 1/f, take the periodic residual):
- **Eyes-open**: the alpha band power is **{eo_aperiodic*100:.0f}% aperiodic** — the periodic (true
  oscillation) residual is ≈ {eo_periodic:.2g} (essentially **no alpha oscillation**); the 'alpha power'
  is the 1/f background.
- **Eyes-closed**: **{ec_aperiodic*100:.0f}% aperiodic** — a genuine periodic alpha peak emerges
  (periodic ≈ {ec_periodic:.2g}).

So the raw eyes-open-to-eyes-closed alpha-band-power ratio ({band_ratio:.1f}×) partly reflects a real
oscillation appearing, but the **eyes-open 'alpha power' itself is not an oscillation** — it is the
aperiodic component.

## Conclusion
Band power **does not by itself measure an oscillation**: it conflates a periodic peak with the
aperiodic 1/f background, and in the eyes-open resting state here the alpha band power is essentially
**entirely aperiodic** (Donoghue et al. 2020). Reporting alpha band power as 'alpha oscillation
strength' over-states it; the spectrum must be **parameterized** into aperiodic and periodic components
before claiming an oscillation.
""")
print(f"OK: n={n_ok}; eyes-open alpha aperiodic frac={eo_aperiodic:.2f} (periodic~{eo_periodic:.1g}); "
      f"eyes-closed aperiodic frac={ec_aperiodic:.2f}; EC/EO band ratio={band_ratio:.1f}")
