"""Reference solution for MEGAEF-001.

Reproduce the latency of the auditory **M100** (the N100m, the ~100 ms auditory evoked
field) to the standard tones in the Brainstorm ``bst_auditory`` MEG recording, quantified
as the time of the peak Global Field Power (GFP) over the MEG magnetometers, relative to
the onset of the auditory stimulus.

The one choice the brief leaves un-cued is **what marks the stimulus onset**. In this
recording the digital stimulus trigger on ``UPPT001`` does NOT coincide with the acoustic
delivery of the tone: the sound reaches the subject about 14 ms AFTER the trigger fires
(a fixed presentation/soundcard delay). The recording captures the delivered sound itself
on an analog audio channel (``UADC001``), so the true acoustic onset is recoverable. The
physiological M100 latency must be measured relative to that true acoustic onset. Timing
the epochs to the raw digital trigger (the naive choice) therefore over-states the M100
latency by the fixed ~14 ms trigger delay.

Everything else is pinned (run 1, the standard-tone trigger code 1, the MEG magnetometers,
the -0.1..0.4 s epoch with a pre-stimulus baseline, a 40 Hz low-pass, and the GFP peak in
the 60-160 ms window), so only the stimulus-timing choice moves the number.

Validated (MNE 1.12.1, bst_auditory run 1, 200 standard tones):
    trigger->sound delay (from the analog audio channel) : 13.9 +/- 0.3 ms
    M100 GFP-peak latency, acoustic-onset aligned (correct): 93.3 ms   <-- reported here
    M100 GFP-peak latency, raw-trigger timing (naive)      : 107.5 ms  (~+14 ms)
The correct value is robust (92-94 ms across 30/40 Hz / no low-pass, several measurement
windows, and audio-detection thresholds 1.5-3.0 x sigma); the naive value is ~107-109 ms.
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

STANDARD = 1                 # standard-tone trigger code on UPPT001
TMIN, TMAX = -0.1, 0.4
M100_WIN = (0.06, 0.16)      # auditory M100 measurement window, s
BASELINE = (None, 0)
LOWPASS = 40.0


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset_id": "bst_auditory"}, indent=2))
    (OUT / "m100.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    import mne
    mne.set_log_level("ERROR")
except Exception as e:  # pragma: no cover
    fail(f"mne import failed: {e}")


RUN1 = "S01_AEF_20131218_01.ds"


def raw_path():
    env = os.environ.get("BST_AUDITORY_DIR")
    if env:
        cand = Path(env) / RUN1
        if cand.exists():
            return cand
    try:
        p = Path(mne.datasets.brainstorm.bst_auditory.data_path(accept=True))
    except Exception as e:
        fail(f"could not fetch the bst_auditory dataset: {e}")
    direct = p / "MEG" / "bst_auditory" / RUN1
    if direct.exists():
        return direct
    hits = sorted(p.glob(f"**/{RUN1}"))
    if hits:
        return hits[0]
    fail(f"could not locate {RUN1} under {p}")


def acoustic_onsets(raw, events):
    """Detect the true acoustic onset of each stimulus from the analog audio channel and
    return an events array re-timed to those onsets."""
    audio_names = [c for c in raw.ch_names if "UADC" in c]
    if not audio_names:
        fail("no analog audio channel (UADC*) found to recover the acoustic onset")
    audio = raw.copy().pick(audio_names[0]).get_data()[0]
    sfreq = raw.info["sfreq"]
    onsets = np.where(np.abs(audio) > 2.0 * np.std(audio))[0]
    min_diff = int(0.5 * sfreq)
    d = np.concatenate([[min_diff + 1], np.diff(onsets)])
    onsets = onsets[d > min_diff]
    new_ev = events.copy()
    delays = []
    for i, e in enumerate(events):
        after = onsets[onsets >= e[0] - int(0.05 * sfreq)]
        if len(after):
            new_ev[i, 0] = after[0]
            delays.append((after[0] - e[0]) / sfreq * 1000.0)
    return new_ev, np.array(delays)


def m100_gfp_latency(raw, events, win=M100_WIN):
    r = raw.copy().filter(None, LOWPASS, picks="mag", verbose=False)
    ep = mne.Epochs(r, events, event_id={"standard": STANDARD}, tmin=TMIN, tmax=TMAX,
                    baseline=BASELINE, picks="mag", preload=True, verbose=False)
    ev = ep.average()
    gfp = ev.data.std(axis=0)
    tt = ev.times
    m = (tt >= win[0]) & (tt <= win[1])
    lat_ms = 1000.0 * float(tt[m][np.argmax(gfp[m])])
    amp_ft = 1e15 * float(gfp[m].max())
    return lat_ms, amp_ft, len(ep)


try:
    raw = mne.io.read_raw_ctf(str(raw_path()), preload=True, verbose=False)
    events = mne.find_events(raw, stim_channel="UPPT001", verbose=False)
    ev_sound, delays = acoustic_onsets(raw, events)
    lat_correct, amp, n_std = m100_gfp_latency(raw, ev_sound)
    lat_trigger, _, _ = m100_gfp_latency(raw, events)
except Exception as e:
    fail(f"could not compute the auditory M100 latency: {e}")

(OUT / "m100.json").write_text(json.dumps({
    "m100_latency_ms": lat_correct,
    "condition": "standard tone",
    "measure": "peak Global Field Power (magnetometers)",
    "window_ms": [int(M100_WIN[0] * 1000), int(M100_WIN[1] * 1000)],
    "n_trials": int(n_std),
    "m100_gfp_amplitude_ft": amp,
    "latency_from_raw_trigger_ms_for_reference": lat_trigger,
    "trigger_to_sound_delay_ms": float(np.mean(delays)) if len(delays) else None,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "bst_auditory (Brainstorm auditory oddball MEG)",
    "file": "S01_AEF_20131218_01.ds (run 1)",
    "condition": "standard tone (UPPT001 trigger code 1)",
    "n_trials": int(n_std),
    "channels": "MEG magnetometers",
    "reference_measure": "peak Global Field Power (spatial std across magnetometers)",
    "epoch_ms": [int(TMIN * 1000), int(TMAX * 1000)],
    "baseline_ms": [-100, 0],
    "lowpass_hz": LOWPASS,
    "measurement_window_ms": [int(M100_WIN[0] * 1000), int(M100_WIN[1] * 1000)],
}, indent=2))

(OUT / "findings.md").write_text(f"""# MEGAEF-001 - auditory M100 latency (bst_auditory, standard tones)

For the standard tones of the Brainstorm ``bst_auditory`` MEG recording (run 1,
{n_std} trials; magnetometers), the auditory **M100** (N100m) produces a clear peak in the
Global Field Power. Measured as the **peak-GFP latency in the 60-160 ms window** relative
to the true acoustic stimulus onset, the M100 latency is **{lat_correct:.1f} ms**.

The stimulus timing matters for this latency. The digital trigger on ``UPPT001`` precedes
the acoustic delivery of the tone by about **{float(np.mean(delays)):.1f} ms** (recovered
from the analog audio channel), so timing the epochs to the raw trigger instead of the
acoustic onset inflates the apparent M100 latency to about **{lat_trigger:.1f} ms**. The
value above is aligned to the true sound onset and is the correct M100 latency
(peak-GFP amplitude {amp:.0f} fT).
""")
print(f"OK: M100 latency (acoustic-onset aligned)={lat_correct:.1f} ms | "
      f"raw-trigger(naive)={lat_trigger:.1f} ms | delay={np.mean(delays):.1f} ms | n={n_std}")
