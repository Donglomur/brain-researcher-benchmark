## HIPPOTHETA-001

**Proposal Title:** The hippocampal theta peak frequency of a freely-moving mouse CA1 recording — one un-cued off-critical-path over-claim (asserting a single state-independent theta frequency when it is state-dependent)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Systems neuroscience / hippocampal oscillations

**Source finding:** Huszár, Zhang, Blockus, Buzsáki (2022), *Nature Neuroscience*, https://doi.org/10.1038/s41593-022-01138-x. **Dataset:** DANDI dandiset **`000552`** (chronic mouse CA1 recordings, NWB), fetched at runtime. Pinned session: **`sub-e15-13f1` / `ses-e15-13f1-220117`**, using two assets — the LFP raw-ecephys file (`...-220117-raw_ecephys.nwb`, ~6.8 GB, streamed one channel at a time) and the behaviour file (`...-220117_behavior+ecephys.nwb`, ~270 MB, position).

**Status: FULL runnable task** (real-data, runtime DANDI streaming fetch via `DandiAPIClient` + `remfile`, `allow_internet=true`). **Over-claim / recognition genre** with a numeric anchor — the GRADIENT-001 pattern (assert a single confident identity that the data does not support), applied to a state-dependent oscillation frequency.

### The measurement and the un-cued lever (de-cued)

The brief pins the deliverable — the **peak frequency of the 6-10 Hz theta rhythm in the CA1 LFP for this session** — and the non-lever machinery (LFP at 1250 Hz, a clear-theta hippocampal channel, a Welch spectrum). The previous version *instructed* the lever ("while the mouse is locomoting", "derive the running speed", "during locomotion"); that telegraph has been removed. The instruction now names only the quantity and provides the behaviour asset (tracked position) as available data, never telling the analyst to condition on movement or state.

The single off-critical-path judgement: **theta frequency is state-dependent.** Running (locomotion) theta is FAST (~9 Hz); theta during REM sleep and awake immobility is ~1.5 Hz SLOWER (~7.4-7.5 Hz). This session is a ~7.08 h recording that is **mostly home-cage rest/sleep** with a single ~30.7 min maze epoch. So a theta-band spectral peak taken over the **whole recording** (the naive default — open the LFP, Welch it, read the 6-10 Hz peak) is dragged down to ~7.9 Hz by the dominant slow-theta periods. A mature analyst VOLUNTEERS the state-conditioning, recovers the ~9 Hz movement theta, and reports the frequency as state-dependent — exactly as a mature GRADIENT-001 answer reports that the principal-gradient identity is not stable.

The extra wrinkle raising the floor: LFP and position live in **two different NWB files** of the session, so the analyst must pair them on the shared clock before it can condition on movement at all.

### The trap (Step-0 re-validated, real data)

Best theta-power channel, Welch 4 s Hann windows, parabolic-interpolated peak over 5-11 Hz, 6-10 Hz band:

| LFP subset | theta peak | reading |
|---|---|---|
| **whole recording** (no state conditioning) | **~7.9 Hz** | naive over-claim — dominated by rest/REM slow theta |
| REM sleep only | ~7.4 Hz | slow theta |
| awake immobility (speed < 1) only | ~7.5 Hz | slow theta |
| **locomotion** (speed > 5 units/s) | **~9.0 Hz** | movement-related theta ← honest |
| maze epoch, no speed gate | 8.90 Hz | (conditioned on the behavioural epoch) |

Speed within the maze: 79% of time > 1 unit/s, 36% > 5 unit/s (so the maze epoch is movement-dominated). The locomotion peak is stable across the theta channel (48/63/78 → ~9.0; oracle max-power pick → ~9.0) and the running cutoff (>3 → 8.86, >5 → 8.99). Gap ≈ 1.0-1.1 Hz vs the naive whole-recording value.

### The failure mode (un-cued, over-claim)

The agent estimates one theta peak over the whole LFP, asserts a single flat ~7.9 Hz, and never asks whether it depends on the animal's behavioural state — when it does. Only conditioning on movement recovers the movement-related ~9 Hz.

### Verifier (3 plain checks, over-claim genre — cf. GRADIENT-001)

`tests/test_outputs.py`: (1) a theta peak in a plausible band and a `findings.md` that mentions theta; (2) **the analysis conditioned on the animal's movement / behavioural state** — a structured multi-condition report, or prose that conditions/compares theta across movement vs rest/REM (co-occurrence guarded so the bare "running an eight-maze" *context* does not count) — the check a whole-recording answer fails; (3) **the reported theta peak reproduces the movement value (~8.9 ± 0.55 Hz), or the prose explicitly reports the faster running theta (~9 Hz) distinct from the slower rest/REM theta** — a flat ~7.9 Hz whole-recording estimate fails. A value the submission labelled whole-recording / REM / immobility / rest is never taken as the headline. Offline discrimination (locked; self-tested on synthetic + real oracle): reference oracle **PASS**; whole-recording naive (~7.9) **FAILS**; a context-only "ran an eight-maze" mention does not sneak past the conditioning check.

**Fairness / no-fake-trap:** this is the GRADIENT-001 over-claim genre — a submission that computes a real number but asserts it as a single state-independent identity, without checking the axis it actually varies on (here, behavioural state), over-claims and fails. The honest answer is a real, reproducible value (~9 Hz movement theta) plus the state-dependence.

### Difficulty — Step-5 frontier calibration PENDING

Oracle **reward 1.0** (re-validated on the pinned DANDI assets; single-channel streaming over S3 range requests via remfile); whole-recording naive baseline **reward 0**. The ≥2-frontier-family gate (GPT-5.x + Claude, k≥3 each) is the maintainer's step and is **not yet run**.

### Cost

`hard`. cpus 2, mem 12 GB, internet on. Streams a channel-selection window (all channels, one ~120 s block ≈ 100 MB) plus one full channel of the ~6.8 GB LFP (~130 MB over S3 range requests) and a ~270 MB behaviour file — not the whole dandiset (~1.5 TB); DANDI/S3 can throttle. Agent timeout 7200 s, verifier 1800 s. Deps: dandi 0.78 / pynwb 4.2 / numpy / scipy / pandas / h5py / scikit-learn / remfile / fsspec (pinned in the Dockerfile).
