"""Reference (oracle) for RESTALPHA-001 — resting 'alpha band power' is confounded by the aperiodic
1/f component, so it does NOT by itself establish a genuine oscillation.

Paper anchor: Donoghue et al. 2020, Nat Neurosci (10.1038/s41593-020-00744-x, "Parameterizing neural
power spectra into periodic and aperiodic components"; the FOOOF / specparam method). The power
spectrum is the sum of a broadband aperiodic (1/f) background AND, where present, narrowband periodic
peaks. Band power sums the two; reporting band power as an oscillation conflates them.

The task (un-cued) asks to measure resting alpha-band (8-12 Hz) power in EEGBCI eyes-open data and
report the alpha oscillation strength. The naive move is to report the alpha band power. This
reference reproduces that band power, then VOLUNTEERS the check the task never asks: it PARAMETERIZES
each spectrum with FOOOF (a validated spectral-parameterization method) — fitting the aperiodic 1/f
(offset, exponent) and the periodic peaks — and reports the aperiodic FRACTION of the alpha band
power together with the fitted parameters. In the eyes-OPEN state the alpha band power is essentially
entirely aperiodic (aperiodic fraction ~0.94, an alpha peak fitted in only a minority of subjects;
periodic residual ~ 0 — no oscillatory peak), whereas eyes-CLOSED reveals a genuine periodic alpha
(aperiodic fraction ~0.33, an alpha peak in nearly every subject). So the eyes-open 'alpha power' is
the 1/f background, not an alpha oscillation.

Route b (offline): reads the packaged per-channel PSD bundle (data/eegbci_psd.npz) — no network.

Emitted for the verifier to CHECK the actual data (not just prose):
  fooof_fits.csv   — one row per (subject, state): aperiodic offset/exponent, r^2, alpha-peak
                     cf/pw, alpha total/aperiodic/periodic band power, aperiodic fraction, n peaks
  alpha.json       — naive alpha band power (EO/EC) + the FOOOF decomposition per state + params
  run_metadata.json, findings.md
Validated numbers are written by this run and echoed to stdout (the receipt).
"""
import csv
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(__file__).resolve().parent.parent / "data" / "eegbci_psd.npz"

ALPHA = (8.0, 12.0)          # the classic alpha band
FIT_RANGE = (2.0, 40.0)      # FOOOF fit range
PEAK_BAND = (7.0, 13.0)      # count a peak as 'alpha' if its centre is here


def fail(reason):
    (OUT / "alpha.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "eegbci"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from fooof import FOOOF
except Exception as e:  # pragma: no cover
    fail(f"spectral-parameterization import failed (need fooof/specparam): {e}")

try:
    d = np.load(DATA, allow_pickle=True)
    psd_eo = d["psd_eo"].astype(float)   # (n_subj, n_ch, n_freq) linear power, eyes-open
    psd_ec = d["psd_ec"].astype(float)   # eyes-closed
    freqs = d["freqs"].astype(float)
    subjects = d["subjects"].astype(int)
except Exception as e:
    fail(f"could not load packaged PSD bundle {DATA}: {e}")

n_subj = psd_eo.shape[0]
if n_subj < 5:
    fail(f"too few subjects in bundle ({n_subj})")

ab = (freqs >= ALPHA[0]) & (freqs <= ALPHA[1])


def parameterize(spectrum):
    """FOOOF-parameterize one channel-averaged spectrum; return the fitted params + the aperiodic
    fraction of the 8-12 Hz band power (aperiodic-only fit power / total power over the band)."""
    fm = FOOOF(peak_width_limits=(1.0, 12.0), max_n_peaks=6, aperiodic_mode="fixed", verbose=False)
    fm.fit(freqs, spectrum, FIT_RANGE)
    fb = (fm.freqs >= ALPHA[0]) & (fm.freqs <= ALPHA[1])
    ap_lin = 10 ** fm._ap_fit          # aperiodic-only model, linear power, over fm.freqs
    tot_lin = 10 ** fm.power_spectrum  # the (log10) input spectrum, back to linear
    ap_bp = float(ap_lin[fb].mean())
    tot_bp = float(tot_lin[fb].mean())
    per_bp = tot_bp - ap_bp
    frac = ap_bp / tot_bp if tot_bp > 0 else float("nan")
    off, exp = (float(fm.aperiodic_params_[0]), float(fm.aperiodic_params_[-1]))
    peaks = fm.peak_params_ if fm.peak_params_ is not None else np.empty((0, 3))
    apk = [p for p in peaks if PEAK_BAND[0] <= p[0] <= PEAK_BAND[1]]
    if apk:
        best = max(apk, key=lambda p: p[1])   # strongest alpha peak
        cf, pw, bw = float(best[0]), float(best[1]), float(best[2])
    else:
        cf = pw = bw = float("nan")
    return {
        "offset": off, "exponent": exp, "r_squared": float(fm.r_squared_),
        "fit_error": float(fm.error_), "n_alpha_peaks": int(len(apk)),
        "alpha_peak_cf": cf, "alpha_peak_pw": pw, "alpha_peak_bw": bw,
        "alpha_total_power": tot_bp, "alpha_aperiodic_power": ap_bp,
        "alpha_periodic_power": per_bp, "aperiodic_fraction": frac,
    }


rows = []
for i, sub in enumerate(subjects):
    for state, cube in (("eyes_open", psd_eo), ("eyes_closed", psd_ec)):
        spec = cube[i].mean(0)               # average across EEG channels
        r = parameterize(spec)
        r.update({"subject": int(sub), "state": state,
                  "naive_alpha_band_power": float(spec[ab].mean())})
        rows.append(r)

eo = [r for r in rows if r["state"] == "eyes_open"]
ec = [r for r in rows if r["state"] == "eyes_closed"]


def _m(lst, key):
    v = [r[key] for r in lst if np.isfinite(r[key])]
    return float(np.mean(v)) if v else float("nan")


eo_frac, ec_frac = _m(eo, "aperiodic_fraction"), _m(ec, "aperiodic_fraction")
eo_per, ec_per = _m(eo, "alpha_periodic_power"), _m(ec, "alpha_periodic_power")
eo_naive, ec_naive = _m(eo, "naive_alpha_band_power"), _m(ec, "naive_alpha_band_power")
eo_exp, ec_exp = _m(eo, "exponent"), _m(ec, "exponent")
eo_peakN = sum(1 for r in eo if r["n_alpha_peaks"] > 0)
ec_peakN = sum(1 for r in ec if r["n_alpha_peaks"] > 0)
band_ratio = ec_naive / eo_naive if eo_naive else float("nan")

# ---- fooof_fits.csv: the per-item fitted parameters the verifier checks ----
cols = ["subject", "state", "offset", "exponent", "r_squared", "fit_error",
        "n_alpha_peaks", "alpha_peak_cf", "alpha_peak_pw", "alpha_peak_bw",
        "alpha_total_power", "alpha_aperiodic_power", "alpha_periodic_power",
        "aperiodic_fraction", "naive_alpha_band_power"]
with open(OUT / "fooof_fits.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(cols)
    for r in rows:
        w.writerow([r["subject"], r["state"]] + [
            (f"{r[c]:.6g}" if isinstance(r[c], float) else r[c]) for c in cols[2:]])


def _per_state(lst):
    return {
        "mean_aperiodic_fraction_of_alpha": _m(lst, "aperiodic_fraction"),
        "mean_periodic_alpha_power": _m(lst, "alpha_periodic_power"),
        "mean_aperiodic_exponent": _m(lst, "exponent"),
        "mean_aperiodic_offset": _m(lst, "offset"),
        "mean_fit_r_squared": _m(lst, "r_squared"),
        "n_subjects_with_alpha_peak": sum(1 for r in lst if r["n_alpha_peaks"] > 0),
        "mean_naive_alpha_band_power": _m(lst, "naive_alpha_band_power"),
    }


(OUT / "alpha.json").write_text(json.dumps({
    "dataset": "EEGBCI (eyes-open run 1, eyes-closed run 2)",
    "n_subjects": n_subj, "band_hz": list(ALPHA),
    "spectral_parameterization": "FOOOF (Donoghue 2020): aperiodic 1/f (offset, exponent) + periodic peaks",
    "fit_range_hz": list(FIT_RANGE),
    # the naive answer the task literally asks for:
    "naive_alpha_band_power_eyes_open": eo_naive,
    "naive_alpha_band_power_eyes_closed": ec_naive,
    "raw_alpha_band_power_EC_over_EO": band_ratio,
    # the volunteered decomposition:
    "eyes_open": _per_state(eo),
    "eyes_closed": _per_state(ec),
    "eyes_open_aperiodic_fraction_of_alpha": eo_frac,
    "eyes_closed_aperiodic_fraction_of_alpha": ec_frac,
    "eyes_open_periodic_alpha": eo_per,
    "eyes_closed_periodic_alpha": ec_per,
    "method": "alpha band power vs FOOOF spectral parameterization (aperiodic 1/f + periodic peaks)",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "EEGBCI (MNE eegmmidb), baseline runs 1 (eyes-open) & 2 (eyes-closed)",
    "n_subjects": n_subj, "source": "packaged per-channel PSD bundle data/eegbci_psd.npz (offline)",
    "psd": "MNE Welch, 2 s windows 50% overlap, 1-45 Hz, channel-averaged",
    "method": "alpha band power vs FOOOF (specparam) aperiodic/periodic spectral parameterization",
    "fit": "FOOOF fixed aperiodic mode, fit range 2-40 Hz, peak_width_limits (1,12), max 6 peaks",
}, indent=2))

(OUT / "findings.md").write_text(f"""# RESTALPHA-001 — resting alpha 'oscillation' power in EEG

{n_subj} subjects, EEGBCI eyes-open (run 1) and eyes-closed (run 2), alpha band {ALPHA[0]:.0f}-{ALPHA[1]:.0f} Hz.

## The alpha band power is readily measured (reproduces the standard result)
Averaging the power spectrum across EEG channels and taking the mean 8-12 Hz power gives a clear
alpha-band value in both baseline states, and it is larger eyes-closed than eyes-open
(EC/EO ratio {band_ratio:.1f}x) — the classic Berger increase. A naive analysis stops here and reports
"a strong resting alpha oscillation," reading band power off as oscillation strength.

## But band power conflates a periodic peak with the aperiodic 1/f background
The power spectrum is the sum of a broadband **aperiodic (1/f)** background and, where present,
narrowband **periodic** peaks. Parameterizing each spectrum with FOOOF (Donoghue et al. 2020) — fitting
the aperiodic component (offset, exponent) and the periodic peaks — and taking the aperiodic FRACTION
of the 8-12 Hz band power:

- **Eyes-open**: the alpha band power is **{eo_frac*100:.0f}% aperiodic** — the periodic (true
  oscillation) residual is essentially **zero** (mean periodic power ~ {eo_per:.2g}), and a genuine
  alpha peak is fitted in only **{eo_peakN}/{n_subj}** subjects (mean aperiodic exponent {eo_exp:.2f}).
  There is **no reliable alpha oscillation** here; the 'alpha power' is the 1/f background.
- **Eyes-closed**: the alpha band power is only **{ec_frac*100:.0f}% aperiodic** — a genuine periodic
  alpha peak emerges (mean periodic power ~ {ec_per:.2g}; alpha peak fitted in
  **{ec_peakN}/{n_subj}** subjects).

## Conclusion
Alpha band power **does not by itself establish an oscillation**: it sums a periodic peak and the
aperiodic 1/f background, and in the eyes-open resting state here the alpha band power is essentially
**entirely aperiodic** (no oscillatory peak above the 1/f background). Reporting the eyes-open alpha
band power as 'alpha oscillation strength' **over-states** it; the spectrum must be **parameterized**
into aperiodic and periodic components (FOOOF / specparam) before an oscillation can be claimed. The
eyes-closed contrast confirms the method detects a genuine alpha when one is present.
""")

print(f"OK: n={n_subj}; EO alpha aperiodic frac={eo_frac:.2f} (periodic~{eo_per:.1g}, "
      f"alpha-peak {eo_peakN}/{n_subj}); EC aperiodic frac={ec_frac:.2f} (alpha-peak {ec_peakN}/{n_subj}); "
      f"EC/EO band ratio={band_ratio:.1f}; exp EO={eo_exp:.2f}/EC={ec_exp:.2f}")
