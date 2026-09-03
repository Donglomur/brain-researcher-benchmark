## HIPPORIPPLE-001

**Proposal Title:** Reproduce the non-REM sharp-wave-ripple incidence rate on a freely-moving mouse CA1 recording — one un-cued off-critical-path error (state contamination of the denominator: whole-recording vs non-REM normalisation)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Systems neuroscience / hippocampal sharp-wave ripples

**Source finding:** Huszár, Zhang, Blockus, Buzsáki (2022), *Nature Neuroscience*, https://doi.org/10.1038/s41593-022-01138-x ("Preconfigured dynamics in the hippocampus are guided by embryonic birthdate and rate of neurogenesis"). **Dataset:** DANDI dandiset **`000552`** (chronic mouse CA1 recordings, NWB), fetched at runtime. Pinned session/asset: **`sub-e15-13f1/sub-e15-13f1_ses-e15-13f1-220117_behavior+ecephys.nwb`** (~270 MB, one asset, streamed).

**Status: FULL runnable task** (real-data, runtime DANDI streaming fetch via `DandiAPIClient` + `remfile`, `allow_internet=true`). Reproduction genre (numeric match), animal hippocampal ephys.

### The measurement and the un-cued lever

The brief pins the deliverable — the **CA1 sharp-wave-ripple (SWR) incidence rate during non-REM sleep, in events per second** — and points at the two provided NWB tables (`processing/ecephys/Ripples` detections; `processing/behavior/SleepStates` annotations, labels `Awake`/`Non-REM`/`REM`). It never says "denominator", "divide by non-REM duration, not the session", or warns about normalisation.

The single off-critical-path choice: **SWRs are a state-specific phenomenon** — abundant in non-REM sleep, rare during locomotion and REM. The incidence rate *during non-REM sleep* is (ripples occurring in non-REM) / (time spent in non-REM). A naive pipeline normalises by the **whole recording** instead of by the non-REM duration (state contamination of the denominator), or counts all ripples over the whole session, and reports a rate about half as large. On this ~7 h session the animal is in non-REM only ~35% of the time, so the two denominators differ ~3×.

### The trap (Step-0 validated, real data)

Provided `Ripples` (9135 events) and `SleepStates` annotations; ripple assigned to a state by its peak time:

| numerator | denominator | rate | reading |
|---|---|---|---|
| all ripples (9135) | whole recording (25499 s) | **0.358 /s** | naive — ignores state entirely |
| non-REM ripples (6772) | whole recording (25499 s) | 0.266 /s | naive — right numerator, wrong denominator |
| **non-REM ripples (6772)** | **non-REM duration (9016 s)** | **0.751 /s** | non-REM incidence ← reported |
| awake ripples | awake duration | 0.148 /s | (context) SWRs rare when awake/moving |
| REM ripples | REM duration | 0.046 /s | (context) SWRs rare in REM |

**Robustness (Step-0):** the non-REM rate is **identical (0.751 /s)** whether ripples are assigned to a state by their peak time or their onset time — deterministic given the provided detections and annotations. The graded tolerance (±0.15 around 0.75 → [0.60, 0.90]) cleanly fails both whole-recording normalisations (0.27 / 0.36, margins ≥ 0.39 /s below the pass floor) while accepting the correct non-REM incidence. The grader also canonicalises a per-minute report (×1/60), so a correct 45 /min still passes and a naive 21 /min still fails. The quantity is an event rate in events/s — convention-invariant (fixed, provided detections; no threshold choice).

### The failure mode (un-cued, reproduction)

The agent divides ripples by the whole-recording duration (or counts all ripples over the session) rather than by the non-REM sleep duration, and reports ~0.27-0.36 /s instead of the ~0.75 /s non-REM incidence. A reported ~0.27-0.36 /s fails the numeric match.

### Verifier (3 plain checks, reproduction genre)

`tests/test_outputs.py`: (1) a real run — a plausible ripple count (~9135) and non-REM duration (~9016 s) are recorded; (2) **numeric reproduction** — the headline `ripple_rate_hz` (a value the submission labelled whole-recording / total / awake / REM is never taken as the headline; a per-minute figure is canonicalised) matches **0.75 ± 0.15 /s**, which fails the naive ~0.27-0.36; (3) light honesty check — findings.md mentions ripples and non-REM and states a rate consistent with the non-REM value. Offline discrimination (locked): reference oracle **3/3 PASS** (0.751 /s); whole-recording naive (0.358 /s) and non-REM-over-total naive (0.266 /s) each **FAIL 2/3**.

### Difficulty — Step-5 frontier calibration PENDING

Oracle **reward 1.0**; both naive baselines **reward 0** (validated locally against the pinned DANDI asset; runtime content-URL streaming fetch verified via remfile). The ≥2-frontier-family gate (GPT-5.x + Claude, k≥3 each) is a maintainer step and is **not yet run**.

### Distinctness

Distinct from RATPLACE-001 (CA1 place-cell Skaggs spatial information + shuffle bias) and from HIPPOTHETA-001 (theta oscillation peak *frequency* during locomotion): different phenomenon (discrete sharp-wave ripple *events*), different measured quantity (an event *rate* in events/s), and a different analysis (intersecting two ragged NWB `TimeIntervals` tables), with no spectral or spatial-coding computation.

### Cost

`hard`. cpus 2, mem 8 GB, internet on. Streams one ~270 MB NWB asset at runtime (not the ~1.5 TB dandiset); DANDI/S3 can throttle. Agent timeout 7200 s, verifier 1800 s. Deps: dandi 0.78 / pynwb 4.2 / numpy / scipy / pandas / h5py / remfile / fsspec (pinned in the Dockerfile).
