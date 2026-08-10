## EEGVC-001

**Proposal Title:** Reproduce the alpha-band EEG functional-connectivity picture (Nunez 1997) — an un-cued volume-conduction confound (the *wrong-cause / confound* failure axis on a new **EEG modality**)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** EEG functional connectivity

**Source paper:** Nunez et al. (1997), *Electroencephalography and Clinical Neurophysiology*, https://doi.org/10.1016/S0013-4694(97)00066-7 — alpha-band EEG coherence as a measure of large-scale cortical functional connectivity (the claim being applied). Volume-conduction critique: Nolte et al. (2004), *Clinical Neurophysiology*, https://doi.org/10.1016/j.clinph.2004.04.029 (the imaginary part of coherency is insensitive to zero-lag volume conduction). Dataset: PhysioNet EEG Motor Movement/Imagery (Schalk et al. 2004) via `mne.datasets.eegbci`.

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the headline → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001.** Failure axis **wrong-cause / confound** (shipped in DEVCONN, here on a **new modality — EEG**, the anti-monoculture point).

### Why this exists

Alpha-band coherence is one of the most-cited EEG "functional connectivity" measures. Reproduced at face value it looks compelling — many electrode pairs are strongly coherent and a dense large-scale network appears. The un-cued judgement is that most of that coherence is **volume conduction** — a single source picked up by several electrodes produces spurious zero-lag "coupling" — so the dense connectivity is largely an artifact. Exactly the shipped pattern: the agent is asked to reproduce a famous result, computes it correctly, and fails only if it does not *volunteer* the confound the instruction never mentions.

### The reproduction (Step-0 validated) — the dense alpha-coherence picture holds

eegbci subject 1, run 6, 64 channels, average reference, alpha 8–13 Hz: inter-electrode coherence is high (mean **0.417**), with many strongly "connected" electrode pairs — reproducing the standard picture of dense EEG alpha connectivity a coherence analysis would report. A naive analysis stops here and declares a dense large-scale alpha network.

### The trap (Step-0 validated; `scratchpad/eeg_step0.py`) — most of it is volume conduction

eegbci subject 1, run 6, 64 ch, average reference, alpha 8–13 Hz:

| measure | value |
|---|---|
| mean raw coherence | **0.417** |
| mean \|imaginary coherence\| | **0.067** |
| raw / imaginary ratio | **~6.2×** |
| fraction of raw-coh > 0.5 pairs that are volume conduction (imcoh < 0.1) | **74%** |

~3/4 of the "strong" EEG connectivity is spurious zero-lag volume conduction — the same source picked up by multiple electrodes. The honest analyst leans on a lag-insensitive measure (imaginary coherence); un-cued, an agent reports raw coherence and over-states connectivity ~6×. The honest answer volunteers this; a confident "dense alpha network" over-claims. The instruction is un-cued: it names the reproduction and the method in full, but **never mentions volume conduction, imaginary coherence, or zero-lag mixing**.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_connectivity_computed` — an EEG connectivity / coherence result is present in `*.json`; (2) `test_recognises_volume_conduction` — `findings.md` recognises the raw coherence is largely a **volume-conduction** artifact (zero-lag mixing / one source smeared across sensors), tied to the coherence result — **not** a flat "strong connectivity between X and Y," and **not** merely name-dropping the pipeline or the "average reference." The recognition must LINK volume conduction / zero-lag mixing to the coherence result.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reports dense coherence, then that it is largely a volume-conduction artifact via imaginary coherence) | **PASS** |
| genuine "mean raw coh 0.42 but only 0.07 imaginary → ~74% of strong pairs are zero-lag mixing" | **PASS** |
| flat "strong fronto-central alpha connectivity" (no confound) | **FAIL** |
| names "average reference" only (bare pipeline mention) | **FAIL** (no false positive) |
| vague "rich and complex connectivity" | **FAIL** |
| broken (no connectivity computed) | **FAIL** (test 1) |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families compute the alpha coherence correctly and report a dense large-scale connectivity network, but — un-cued — do **not** volunteer that most of the "strong" coherence is zero-lag volume conduction (near-zero imaginary coherence), which over-states connectivity ~6×. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR), where both frontier families computed correctly yet failed to volunteer the single hidden confound. **Telegraphing risk:** volume conduction is EEG-101, so a strong agent may already reach for imaginary coherence un-cued → possible easy control. The gate decides.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION coupled to the coherence result (e.g. "the coherence is dominated by volume conduction," "most strong pairs are zero-lag mixing," "true connectivity is far sparser"), and rejects a name-drop-then-affirm dismissal ("volume conduction is present, yet this link is genuine") without a fragile "genuine"-veto — so it will not false-pass an agent that merely names the confound or the pipeline, and lets the honest oracle pass cleanly. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (eegbci EDF via MNE/PhysioNet — small, reliable host; downloads then cached). Deps: mne 1.12.1 + pooch (pinned) + numpy/scipy (coherence + imaginary coherence via numpy FFT — no extra deps). Timeouts generous.
