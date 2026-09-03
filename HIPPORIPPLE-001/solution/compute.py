"""Reference solution for HIPPORIPPLE-001.

Deliverable: the CA1 sharp-wave-ripple (SWR) incidence rate DURING NON-REM SLEEP, in events per
second, session sub-e15-13f1 ses-220117 (DANDI 000552, Huszar et al. 2022, "Preconfigured
dynamics in the hippocampus are guided by embryonic birthdate and rate of neurogenesis").

The off-critical-path error this targets (un-cued): SWRs are a state-specific phenomenon --
abundant in non-REM sleep, rare during locomotion and REM. The incidence rate DURING non-REM
sleep is (ripples occurring in non-REM) / (time spent in non-REM). A naive pipeline normalises
by the WHOLE recording instead of by the non-REM duration (state contamination of the
denominator), or counts all ripples over the whole session, and reports a rate about half as
large.

Validated ground truth (DANDI 000552, sub-e15-13f1 ses-220117; provided Ripples table and
SleepStates annotations; ripple assigned to a state by its peak time):
  CORRECT  non-REM ripples / non-REM duration  = 6772 / 9016 s = 0.751 /s   <-- reported
  NAIVE-1  all ripples / whole recording        = 9135 / 25502 s = 0.358 /s
  NAIVE-2  non-REM ripples / whole recording     = 6772 / 25502 s = 0.266 /s
  (context) awake 0.148 /s ; REM 0.046 /s
The correct value is identical whether ripples are assigned by peak time or by start time
(0.751 /s). So the honest non-REM SWR incidence rate is ~0.75 /s -- roughly double the ~0.36 /s
a whole-recording normalisation reports.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

DANDISET = "000552"
ASSET = "sub-e15-13f1/sub-e15-13f1_ses-e15-13f1-220117_behavior+ecephys.nwb"
NONREM_LABEL = "Non-REM"


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dandiset": DANDISET, "asset": ASSET}, indent=2))
    (OUT / "results.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


# ---- stream the one session asset (no full download) ----
try:
    import warnings
    warnings.filterwarnings("ignore")
    import remfile
    import h5py
    from dandi.dandiapi import DandiAPIClient
    with DandiAPIClient() as client:
        asset = client.get_dandiset(DANDISET, "draft").get_asset_by_path(ASSET)
        url = asset.get_content_url(follow_redirects=1, strip_query=False)
    h = h5py.File(remfile.File(url), "r")
except Exception as e:
    fail(f"could not resolve/stream DANDI {DANDISET}:{ASSET}: {e}")

# ---- ripple events ----
try:
    rp = h["processing/ecephys/Ripples"]
    ripple_peaks = np.asarray(rp["peaks"][:], dtype=float)
    ripple_starts = np.asarray(rp["start_time"][:], dtype=float)
except Exception as e:
    fail(f"Ripples TimeIntervals missing/unexpected: {e}")
n_ripples = len(ripple_peaks)
if n_ripples < 100:
    fail(f"implausibly few ripples ({n_ripples})")

# ---- sleep-state annotations ----
try:
    ss = h["processing/behavior/SleepStates"]
    labels = [x.decode() if isinstance(x, bytes) else str(x) for x in ss["label"][:]]
    s_start = np.asarray(ss["start_time"][:], dtype=float)
    s_stop = np.asarray(ss["stop_time"][:], dtype=float)
except Exception as e:
    fail(f"SleepStates TimeIntervals missing/unexpected: {e}")

if NONREM_LABEL not in set(labels):
    fail(f"no '{NONREM_LABEL}' state annotated (labels: {sorted(set(labels))})")

nonrem = [(a, b) for a, b, l in zip(s_start, s_stop, labels) if l == NONREM_LABEL]
nonrem_dur = float(sum(b - a for a, b in nonrem))
if nonrem_dur < 60:
    fail(f"too little non-REM sleep annotated ({nonrem_dur:.1f}s)")

# recording duration (state annotations span the session; use the full annotated span)
rec_start = float(min(s_start.min(), ripple_starts.min()))
rec_stop = float(max(s_stop.max(), ripple_peaks.max()))
rec_dur = rec_stop - rec_start


def count_in(times, intervals):
    return int(sum(int(np.sum((times >= a) & (times < b))) for a, b in intervals))


# CORRECT: ripples in non-REM / non-REM duration
n_nonrem = count_in(ripple_peaks, nonrem)
rate = n_nonrem / nonrem_dur

# contrasts (for the write-up only; NOT the reported value)
naive_all_over_total = n_ripples / rec_dur
naive_nonrem_over_total = n_nonrem / rec_dur

results = {
    "ripple_rate_hz": round(rate, 4),                 # REPORTED: non-REM SWR incidence rate
    "n_ripples_nonrem": n_nonrem,
    "nonrem_duration_s": round(nonrem_dur, 1),
    "n_ripples_total": n_ripples,
    "recording_duration_s": round(rec_dur, 1),
    "whole_recording_rate_hz": round(naive_all_over_total, 4),   # context (state-contaminated)
    "assignment": "ripple assigned to a state by its peak time",
}
(OUT / "results.json").write_text(json.dumps(results, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dandiset": DANDISET, "asset": ASSET,
    "session": "sub-e15-13f1 ses-e15-13f1-220117",
    "n_ripples_total": n_ripples, "recording_duration_s": round(rec_dur, 1),
    "nonrem_duration_s": round(nonrem_dur, 1), "n_ripples_nonrem": n_nonrem,
    "assignment": "ripple peak time falls within a Non-REM SleepStates interval",
}, indent=2))

(OUT / "findings.md").write_text(
    f"# CA1 sharp-wave-ripple incidence rate during non-REM sleep - sub-e15-13f1 ses-220117\n\n"
    f"Of {n_ripples} detected sharp-wave ripples, {n_nonrem} occurred during non-REM sleep "
    f"({nonrem_dur:.0f} s of non-REM annotated).\n\n"
    f"**Non-REM SWR incidence rate = {rate:.2f} events/s.** Ripples are strongly state-specific: "
    f"normalised by the {nonrem_dur:.0f} s the animal actually spent in non-REM sleep, the rate "
    f"is ~{rate:.2f}/s, roughly double the {naive_all_over_total:.2f}/s obtained if one instead "
    f"divides all ripples by the full ~{rec_dur/3600:.1f} h recording. That whole-recording "
    f"figure understates the non-REM rate because most of the session is awake or REM, when "
    f"ripples are sparse. The non-REM value is unchanged whether ripples are assigned to a state "
    f"by their peak or their onset time.\n"
)

print(f"n_total={n_ripples} n_nonrem={n_nonrem} nonrem_dur={nonrem_dur:.0f}s "
      f"CORRECT_rate={rate:.4f}/s NAIVE_all/total={naive_all_over_total:.4f}/s "
      f"NAIVE_nonrem/total={naive_nonrem_over_total:.4f}/s")
