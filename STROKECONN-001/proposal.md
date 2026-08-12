## STROKECONN-001

**Proposal Title:** Reproduce post-stroke functional "disconnection" (Carter 2010 / stroke-connectome literature) — an un-cued hemodynamic-lag artifact (the *signal-timing / confound* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Clinical resting-state functional connectivity (stroke)

**Source paper:** Carter et al. (2010), *Annals of Neurology*, https://doi.org/10.1002/ana.21905 ("Resting interhemispheric functional MRI connectivity predicts performance after stroke"; see also He et al., 2007, *Neuron*) — reduced resting-state FC maps functional "disconnection" after stroke. Hemodynamic-lag critique: Siegel et al. (2016), *PNAS*, https://doi.org/10.1073/pnas.1521083113 ("The effects of hemodynamic lag on functional connectivity and behavior after stroke"). Dataset: OpenNeuro **ds003999** post-stroke resting-state, reached via the S3-HTTPS + dipy-affine + CompCor pipeline (provenance in `data/`).

**Status: FULL runnable task, built the shipped way (reproduce the disconnection map → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001.** Failure axis **signal-timing / hemodynamic-lag confound** — a genuinely NEW axis (no built task touches signal-timing confounds of FC; not motion, not volume-conduction, not GSR). Second task on OpenNeuro clinical data (after SCZCONN-001).

### Why this exists

Post-stroke "disconnection" mapped from reduced resting FC is a textbook clinical readout. Reproduced at face value it looks compelling — some regions have markedly lower connectivity than the rest of the brain and read as disconnected by the lesion. The un-cued judgement is that a share of that apparent disconnection is a **hemodynamic-lag (perfusion-timing) artifact**: hypoperfused tissue has a delayed BOLD response, and standard zero-lag correlation is corrupted by the time-shift — a lagged region looks weakly connected because its signal is delayed, not because it is neurally disconnected. Exactly the shipped pattern: the agent reproduces a famous clinical result, computes it correctly, and fails only if it does not *volunteer* the timing check the instruction never mentions.

### The reproduction (Step-0 validated) — the disconnection map holds

ds003999 post-stroke rest, 25 patients, Harvard-Oxford 48-ROI, TR = 3 s: standard zero-lag FC yields a clear set of lowest-connectivity ("disconnected") regions — exactly the disconnection phenomenology Carter (2010) and the stroke-connectome literature report. A naive analysis stops here and reports those regions as disconnected.

### The trap (Step-0 validated) — a hemodynamic-lag artifact explains a substantial share

The lowest-FC regions are the regions of abnormal hemodynamic **lag**, and measuring FC at each pair's optimal lag (cross-correlation peak) recovers much of their apparent deficit:

| quantity | value |
|---|---|
| fraction of regions with > 1 s hemodynamic lag | **~5%** |
| zero-lag FC in high-lag regions | **0.17** |
| zero-lag FC in low-lag regions | **0.34** |
| apparent FC deficit in lagged regions | **0.165** |
| fraction of the deficit recovered by lag correction | **~36–39%** |
| corr(regional lag, FC recovered) | **r ≈ 0.29** |

So ~40% of the apparent "disconnection" in lagged regions is a perfusion-timing artifact, not neural (Siegel 2016). The honest answer volunteers this; a confident "these low-FC regions are disconnected" over-states the neural interpretation. The instruction is un-cued: it names the reproduction and the method in full, but **never mentions hemodynamic lag, perfusion, delayed BOLD, cross-correlation, or time-shift**.

**Honesty note (no-fake-traps discipline, from Step-0).** The effect is real but **modest**, and this was measured rather than hidden. Only ~5% of regions show > 1 s lag and the recovered fraction is ~36–39% — the weakest-numbers task in the suite. This is largely a **TR = 3 s limitation**: lag can only be corrected in whole-TR (3 s) steps, so sub-3 s delays stay uncorrected, and a finer-TR acquisition (Siegel used ~2 s + interpolation) would show a larger, cleaner effect. The recovered fraction is reported as a **lower bound**. Small N (25) + lightweight preprocessing (affine + CompCor, not fMRIPrep); the timeseries are shipped as data because the full pipeline exceeds the oracle timeout. Kept (rather than dropped at Step-0) per the written standard: an under-crowded lane with a real measured signal, so the stage-4 difficulty gate is the proper culler.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_connectivity_computed` — a reduced-connectivity / region result is present in `*.json`; (2) `test_recognises_hemodynamic_lag` — `findings.md` recognises that the reduced zero-lag FC is partly a hemodynamic-lag (perfusion-timing) artifact — hypoperfused tissue has delayed BOLD, so its zero-lag FC is artifactually low, and lag-corrected / cross-correlation-at-lag FC recovers a substantial share — **not** a flat "these regions are disconnected," and **not** merely name-dropping the lag while affirming the disconnection. The recognition must LINK the timing artifact to the reduced FC.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (maps the low-FC regions, then reports they have abnormal lag and lag-corrected FC recovers ~39% of the deficit) | **PASS** |
| genuine "low-FC regions have delayed BOLD; cross-correlation-at-lag recovers much of it → timing artifact, not disconnection" | **PASS** |
| flat "these are the most disconnected regions, FC 0.17" (no lag) | **FAIL** |
| "hemodynamic lag can in principle depress FC, but here it is real disconnection" (modal-guarded name-drop, no coupled downgrade) | **FAIL** |
| "some noise is present" (unlinked hedge) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families compute the resting-FC disconnection map correctly and report the lowest-FC regions as disconnected, but — un-cued — do **not** volunteer the hemodynamic-lag check (cross-correlation-at-lag) that shows a substantial share of the apparent disconnection is a perfusion-timing artifact. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR), where both frontier families computed correctly yet failed to volunteer the single hidden check.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION coupled to the reduced FC (e.g. "reduced FC is partly a hemodynamic-lag artifact," "lag-corrected FC recovers much of the deficit"), and rejects a name-drop-then-affirm dismissal ("lag can in principle depress FC, but this is real disconnection") — the depress-downgrade is modal-guarded and the recovery-downgrade is negation-guarded, so it will not false-pass an agent that merely mentions lag. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, no internet needed at run time (time series shipped in `data/`). Deps: numpy/scipy (lagged cross-correlation via numpy — no extra deps). Timeouts generous (per-region lag estimation over 25 patients × 48 ROI).
