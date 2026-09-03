"""Reference solution for AUDN1-001.

Reproduce the auditory N100 (the ~100 ms auditory evoked negativity, the EEG counterpart
of the MEG N100m/M100) in the MNE ``sample`` dataset, for the LEFT-auditory condition,
quantified as the peak Global Field Power (GFP) amplitude of the scalp EEG in the
80-120 ms window (average reference).

The one choice the brief leaves un-cued is whether the evoked response is
**baseline-corrected** against the pre-stimulus interval before the amplitude is measured.
An evoked amplitude (and the GFP, which is the spatial standard deviation across
electrodes) must be measured relative to a pre-stimulus baseline: without baseline
correction, the residual per-electrode pre-stimulus offsets inflate the spatial variance
and hence the GFP, badly overstating the N100. On this recording the correctly
baseline-corrected N100 GFP peak is ~4.4 uV, whereas skipping baseline correction inflates
it to ~9 uV (and to ~27 uV if the un-filtered raw file is used instead).

Everything else is pinned (the ``sample`` filtered raw file, the left-auditory trigger,
the EEG channels with the marked bad channel excluded, the average reference, the
-0.2..0.5 s epoch, and the 80-120 ms GFP peak measurement), so only the baseline choice
moves the number.

Validated (MNE 1.12.1, sample, Left Auditory, 72 epochs):
    baseline-corrected N100 GFP peak (correct) : 4.4 uV   <-- reported here
    no baseline correction (naive)             : 9.2 uV   (~2.1x on the filtered file)
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

COND_ID = 1                 # Left Auditory trigger in the sample dataset
TMIN, TMAX = -0.2, 0.5
N1_WIN = (0.08, 0.12)       # auditory N100 measurement window, s
BASELINE = (None, 0)        # pre-stimulus baseline


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset_id": "sample"}, indent=2))
    (OUT / "n1.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    import mne
    mne.set_log_level("ERROR")
except Exception as e:  # pragma: no cover
    fail(f"mne import failed: {e}")


def sample_raw_path():
    env = os.environ.get("SAMPLE_DIR")
    if env:
        cand = Path(env) / "MEG" / "sample" / "sample_audvis_filt-0-40_raw.fif"
        if cand.exists():
            return cand
    try:
        p = mne.datasets.sample.data_path()
    except Exception as e:
        fail(f"could not fetch the sample dataset: {e}")
    return Path(p) / "MEG" / "sample" / "sample_audvis_filt-0-40_raw.fif"


def n1_gfp_peak(baseline):
    """Peak GFP amplitude (uV) of the left-auditory EEG evoked in the N100 window."""
    raw = mne.io.read_raw_fif(sample_raw_path(), preload=True, verbose=False)
    events = mne.find_events(raw, stim_channel="STI 014", verbose=False)
    epochs = mne.Epochs(raw, events, event_id={"aud_l": COND_ID}, tmin=TMIN, tmax=TMAX,
                        baseline=baseline, proj=True, picks="eeg", preload=True, verbose=False)
    epochs.set_eeg_reference("average", projection=False, verbose=False)
    evoked = epochs.average()
    evoked.pick([c for c in evoked.ch_names if c not in raw.info["bads"]])
    gfp = evoked.data.std(axis=0)
    tt = evoked.times
    m = (tt >= N1_WIN[0]) & (tt <= N1_WIN[1])
    return 1e6 * float(gfp[m].max()), len(epochs)


try:
    amp_correct, n_ep = n1_gfp_peak(BASELINE)
    amp_naive, _ = n1_gfp_peak(None)
except Exception as e:
    fail(f"could not compute the auditory N100 GFP: {e}")

(OUT / "n1.json").write_text(json.dumps({
    "n100_gfp_amplitude_uv": amp_correct,
    "condition": "left auditory",
    "window_ms": [int(N1_WIN[0] * 1000), int(N1_WIN[1] * 1000)],
    "reference": "average",
    "n_epochs": int(n_ep),
    "no_baseline_amplitude_uv_for_reference": amp_naive,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "sample (MNE sample audiovisual dataset)",
    "file": "sample_audvis_filt-0-40_raw.fif",
    "condition": "left auditory (trigger 1)",
    "n_epochs": int(n_ep),
    "channels": "EEG, marked bad channel excluded",
    "reference": "average",
    "epoch_ms": [int(TMIN * 1000), int(TMAX * 1000)],
    "measure": "peak Global Field Power amplitude in the 80-120 ms auditory N100 window",
    "baseline_ms": [-200, 0],
}, indent=2))

(OUT / "findings.md").write_text(f"""# AUDN1-001 - auditory N100 amplitude (MNE sample, left auditory)

For the left-auditory condition of the MNE ``sample`` dataset ({n_ep} epochs; EEG,
average reference), the auditory **N100** produces a clear peak in the scalp Global Field
Power around 100 ms. Measured as the **peak GFP amplitude in the 80-120 ms window** on the
baseline-corrected evoked response, the N100 amplitude is **{amp_correct:.2f} uV**.

Baseline correction matters for this amplitude: omitting the pre-stimulus baseline
correction inflates the GFP peak to about **{amp_naive:.2f} uV** on this file, because the
residual per-electrode pre-stimulus offsets add to the spatial standard deviation. The
baseline-corrected value above is the correct N100 amplitude.
""")
print(f"OK: N100 GFP peak (baseline-corrected)={amp_correct:.2f} uV | "
      f"no-baseline(naive)={amp_naive:.2f} uV | n_epochs={n_ep}")
