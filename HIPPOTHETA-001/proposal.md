## HIPPOTHETA-001

**Proposal Title:** Reproduce the hippocampal theta peak frequency during locomotion on a freely-moving mouse CA1 recording — one un-cued off-critical-path error (state contamination: whole-recording spectrum vs movement-conditioned)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Systems neuroscience / hippocampal oscillations

**Source finding:** Huszár, Zhang, Blockus, Buzsáki (2022), *Nature Neuroscience*, https://doi.org/10.1038/s41593-022-01138-x ("Preconfigured dynamics in the hippocampus are guided by embryonic birthdate and rate of neurogenesis"). **Dataset:** DANDI dandiset **`000552`** (chronic mouse CA1 recordings, NWB), fetched at runtime. Pinned session: **`sub-e15-13f1` / `ses-e15-13f1-220117`**, using two of its assets — the LFP raw-ecephys file (`...-220117-raw_ecephys.nwb`, ~6.8 GB, streamed one channel at a time) and the behaviour file (`...-220117_behavior+ecephys.nwb`, ~270 MB, position).

**Status: FULL runnable task** (real-data, runtime DANDI streaming fetch via `DandiAPIClient` + `remfile`, `allow_internet=true`). Reproduction genre (numeric match), animal hippocampal LFP.

### The measurement and the un-cued lever

The brief pins the deliverable — the **peak frequency of the 6-10 Hz theta rhythm in the CA1 LFP while the mouse is locomoting** — and the non-lever machinery (LFP at 1250 Hz, running speed from the tracked position, a clear-theta hippocampal channel, a Welch spectrum). It never says "REM", "sleep", "immobility", "state", "rest", or "condition on movement".

The single off-critical-path choice: **theta frequency is state-dependent.** Running (locomotion) theta is FAST (~9 Hz); theta during REM sleep and awake immobility is ~1.5 Hz SLOWER (~7.4-7.5 Hz). This session is a ~7 h recording that is **mostly home-cage rest/sleep** with a single ~31 min maze epoch. So a theta-band spectral peak taken over the **whole recording** (or otherwise not conditioned on movement) is dragged down to ~7.9 Hz by the dominant slow-theta periods. Only restricting the spectrum to locomotion recovers the movement-related ~9 Hz.

An extra wrinkle raising the floor: LFP and running speed live in **two different NWB files** of the session (the raw-ecephys file has the 128-channel LFP but no behaviour; the behaviour file has position but no LFP). The agent must pair them and align on the shared clock (both start at t=0) before it can condition on movement at all.

### The trap (Step-0 validated, real data)

Best theta-power channel, Welch 4 s Hann windows, parabolic-interpolated peak over 5-11 Hz, 6-10 Hz band:

| LFP subset | theta peak | reading |
|---|---|---|
| **whole recording** (no movement gating) | **7.92 Hz** | naive — dominated by rest/REM slow theta |
| REM sleep only | 7.42 Hz | slow theta |
| awake immobility (speed < 1) only | 7.50 Hz | slow theta |
| **locomotion** (speed > 5 units/s) | **8.99-9.01 Hz** | movement-related theta ← reported |

**Robustness (Step-0):** the locomotion peak is stable across the theta channel (ch 48/63/78 → 8.99 Hz; the oracle's max-power pick, ch 64 → 9.01 Hz) and the running-speed cutoff (speed>3 → 8.86, speed>5 → 8.99, speed>8 → ~8.9). The whole-recording value is stable across channels (7.92-7.93 Hz). Gap ≈ 1.0-1.1 Hz. The graded tolerance (±0.5 around 8.9 → [8.4, 9.4]) cleanly fails the whole-recording / REM / immobility values (7.4-7.9, margin ≥ 0.4 Hz below the pass floor) while accepting any correct movement-conditioned estimate (~8.7-9.0). The quantity is a frequency in Hz — convention-invariant (no reference/units ambiguity).

### The failure mode (un-cued, reproduction)

The agent estimates the theta peak over the whole LFP (or fails to gate on movement — easy to do since it must first pair the LFP file with the separate behaviour file) and reports ~7.9 Hz, the rest/REM-contaminated value, rather than the ~9 Hz movement-related theta. A reported ~7.9 Hz fails the numeric match.

### Verifier (3 plain checks, reproduction genre)

`tests/test_outputs.py`: (1) a real run — a running/locomotion criterion is recorded and (if present) the locomotion time is plausible for a ~31 min maze epoch; (2) **numeric reproduction** — the headline `theta_peak_frequency_hz` (a value the submission labelled whole-recording / REM / immobility / rest is never taken as the headline) matches **8.9 ± 0.5 Hz**, which fails the naive ~7.9; (3) light honesty check — findings.md mentions theta and states a Hz value consistent with the locomotion peak. Accepts nested keys and canonicalises. Offline discrimination (locked): reference oracle **3/3 PASS** (reports 9.007 Hz); whole-recording naive baseline (reports 7.927 Hz) **FAILS 2/3**.

### Difficulty — Step-5 frontier calibration PENDING

Oracle **reward 1.0**; whole-recording naive baseline **reward 0** (validated locally against the pinned DANDI assets; runtime content-URL streaming fetch verified — single-channel reads over S3 range requests via remfile). The ≥2-frontier-family gate (GPT-5.x + Claude, k≥3 each) is a maintainer step and is **not yet run**.

### Cost

`hard`. cpus 2, mem 12 GB, internet on. Streams one channel of a ~6.8 GB LFP file (per-channel chunking → ~50-65 MB per channel over S3 range requests) plus a ~270 MB behaviour file — not the whole dandiset (~1.5 TB); DANDI/S3 can throttle. Agent timeout 7200 s, verifier 1800 s. Deps: dandi 0.78 / pynwb 4.2 / numpy / scipy / pandas / h5py / scikit-learn / remfile / fsspec (pinned in the Dockerfile).
