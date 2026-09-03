"""Reference solution for SOMATOERD-001.

Reproduce the contralateral sensorimotor beta (15-30 Hz) event-related desynchronization
(ERD) evoked by median-nerve stimulation in the MNE ``somato`` dataset, expressed as the
percent change in beta power relative to a pre-stimulus baseline, over a fixed set of
contralateral gradiometers and a fixed early post-stimulus window.

The one choice the brief leaves un-cued is HOW the time-frequency power is obtained from
the trials. Beta ERD/ERS are INDUCED (non-phase-locked) phenomena: the correct estimate
computes the time-frequency power of every single trial and then averages the power
across trials (``epochs.compute_tfr(..., average=True)`` -- the MNE default path). A naive
pipeline instead computes the time-frequency power of the TRIAL-AVERAGE (the evoked
response, ``epochs.average().compute_tfr(...)``): that keeps only phase-locked (evoked)
power and discards the induced modulation. On these data the evoked response is dominated
by the early, strongly phase-locked somatosensory evoked field, whose beta-band power sits
far ABOVE the tiny (noise-averaged-down) pre-stimulus evoked baseline, so the evoked-power
"ERD" comes out as a large POSITIVE percentage -- the opposite sign of the true ERD.

Everything else is pinned (the gradiometer set, Morlet wavelets over 15-30 Hz with
n_cycles = freq/2, percent baseline over -1.0..-0.25 s, beta band 15-30 Hz, the
0.10-0.35 s ERD window), so only the single-trial-vs-average choice moves the number.

Validated (MNE 1.12.1, somato sub-01, 111 median-nerve trials):
    induced / total power (per-trial then averaged)  :  -17.7 %   <-- reported here
    evoked power (average then time-frequency)        : +443.6 %   (naive, wrong sign)
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

# contralateral sensorimotor gradiometers (two Neuromag gradiometer pairs over the
# hemisphere contralateral to the stimulated median nerve)
CHANS = ["MEG 1342", "MEG 1343", "MEG 1332", "MEG 1333"]
FREQS = np.arange(15.0, 31.0, 1.0)          # beta band, 1 Hz grid
N_CYCLES = FREQS / 2.0
BASELINE = (-1.0, -0.25)                     # pre-stimulus baseline, s
BETA = (15.0, 30.0)                          # Hz
ERD_WIN = (0.10, 0.35)                       # early post-stimulus ERD window, s
TMIN, TMAX = -1.5, 1.5


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset_id": "somato"}, indent=2))
    (OUT / "erd.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    import mne
    mne.set_log_level("ERROR")
except Exception as e:  # pragma: no cover
    fail(f"mne import failed: {e}")


def somato_raw_path():
    """Local cache via SOMATO_DIR if it points at the fif, else fetch from OSF."""
    env = os.environ.get("SOMATO_DIR")
    if env:
        cand = Path(env) / "sub-01" / "meg" / "sub-01_task-somato_meg.fif"
        if cand.exists():
            return cand
    try:
        p = mne.datasets.somato.data_path()
    except Exception as e:
        fail(f"could not fetch the somato dataset: {e}")
    return Path(p) / "sub-01" / "meg" / "sub-01_task-somato_meg.fif"


def beta_percent(tfr):
    """Mean percent-baseline beta power over the pinned channels/band/window."""
    t = tfr.copy().pick(CHANS).apply_baseline(BASELINE, mode="percent")
    fmask = (t.freqs >= BETA[0]) & (t.freqs <= BETA[1])
    tmask = (t.times >= ERD_WIN[0]) & (t.times <= ERD_WIN[1])
    return 100.0 * float(t.data[:, fmask, :][:, :, tmask].mean())


try:
    raw = mne.io.read_raw_fif(somato_raw_path(), preload=True, verbose=False)
    events = mne.find_events(raw, stim_channel="STI 014", verbose=False)
    raw.pick("grad")
    epochs = mne.Epochs(raw, events, event_id={"stim": 1}, tmin=TMIN, tmax=TMAX,
                        baseline=None, preload=True, verbose=False)
    n_trials = len(epochs)
    # CORRECT: induced (total) power -- per-trial time-frequency, then average
    tfr_induced = epochs.compute_tfr("morlet", freqs=FREQS, n_cycles=N_CYCLES,
                                     use_fft=True, return_itc=False, average=True)
    # naive contrast: evoked power -- time-frequency of the trial-average
    tfr_evoked = epochs.average().compute_tfr("morlet", freqs=FREQS, n_cycles=N_CYCLES,
                                              use_fft=True)
    erd_induced = beta_percent(tfr_induced)
    erd_evoked = beta_percent(tfr_evoked)
except Exception as e:
    fail(f"could not compute the beta ERD: {e}")

(OUT / "erd.json").write_text(json.dumps({
    "beta_erd_percent": erd_induced,
    "band_hz": [BETA[0], BETA[1]],
    "channels": CHANS,
    "window_ms": [int(ERD_WIN[0] * 1000), int(ERD_WIN[1] * 1000)],
    "baseline_ms": [int(BASELINE[0] * 1000), int(BASELINE[1] * 1000)],
    "n_trials": int(n_trials),
    "evoked_power_percent_for_reference": erd_evoked,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "somato (MNE median-nerve somatosensory dataset, sub-01)",
    "n_trials": int(n_trials),
    "channels": CHANS,
    "tfr": "Morlet wavelets, 15-30 Hz (1 Hz grid), n_cycles = freq/2",
    "baseline": "percent change vs -1.0..-0.25 s",
    "band_hz": [BETA[0], BETA[1]],
    "erd_window_ms": [int(ERD_WIN[0] * 1000), int(ERD_WIN[1] * 1000)],
    "measure": "mean percent-baseline beta power over the contralateral sensorimotor gradiometers",
}, indent=2))

(OUT / "findings.md").write_text(f"""# SOMATOERD-001 - contralateral sensorimotor beta ERD (MNE somato)

Median-nerve stimulation in the MNE ``somato`` dataset (sub-01, {n_trials} trials) drives
a beta-band (15-30 Hz) **event-related desynchronization** over the contralateral
sensorimotor gradiometers ({', '.join(CHANS)}). Computing the time-frequency power per
trial and averaging (induced/total power), expressed as percent change from the
-1.0..-0.25 s baseline and averaged over the 100-350 ms window, the beta ERD is
**{erd_induced:.1f}%** (a power DECREASE).

Note the induced nature of the effect matters: taking the time-frequency power of the
trial-average (the evoked response) instead gives **{erd_evoked:+.0f}%** over the same
band/window -- a large positive value of the wrong sign, because the averaged evoked field
retains only phase-locked power (dominated here by the early somatosensory evoked field)
and its pre-stimulus baseline is averaged down toward zero. The induced-power value above
is the correct ERD.
""")
print(f"OK: beta ERD induced={erd_induced:.2f}% | evoked(naive)={erd_evoked:+.1f}% | n={n_trials}")
