## ALPHACONN-001

**Proposal Title:** Reproduce the alpha-band EEG functional-connectivity picture (Nunez 1997) — an un-cued volume-conduction confound (the *wrong-cause / confound* failure axis on a new **EEG modality**)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** EEG functional connectivity

**Source paper:** Nunez et al. (1997), *Electroencephalography and Clinical Neurophysiology*, https://doi.org/10.1016/S0013-4694(97)00066-7 — alpha-band EEG coherence as a measure of large-scale cortical functional connectivity (the claim being applied). Volume-conduction critique: Nolte et al. (2004), *Clinical Neurophysiology*, https://doi.org/10.1016/j.clinph.2004.04.029 (the imaginary part of coherency is insensitive to zero-lag volume conduction). Dataset: PhysioNet EEG Motor Movement/Imagery (Schalk et al. 2004) via `mne.datasets.eegbci`.

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the headline → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001 / TOPEDGES-001.** Failure axis **wrong-cause / confound** (shipped in DEVCONN, here on a **new modality — EEG**, the anti-monoculture point). **Route b (offline):** the single raw EDF is packaged in `data/` and read offline (`allow_internet = false`).

### Why this exists

Alpha-band coherence is one of the most-cited EEG "functional connectivity" measures. Reproduced at face value it looks compelling — many electrode pairs are strongly coherent and a dense large-scale network appears. The un-cued judgement is that most of that coherence is **volume conduction** — a single source picked up by several electrodes produces spurious zero-lag "coupling" — so the dense connectivity is largely an artifact. The imaginary part of coherency (Nolte et al. 2004) is insensitive to zero-lag mixing, and the strong raw-coherence pairs have near-zero imaginary coherence, so the network collapses under a lag-insensitive measure. Exactly the shipped pattern: the agent is asked to reproduce a famous result, computes it correctly, and fails only if it does not *volunteer* the confound the instruction never mentions.

### The reproduction and the trap (validated) — held privately

The validated numbers (mean raw coherence, mean imaginary coherence, ratio, the strong-pair volume-conduction fraction) and the oracle receipt are in the **private, git-ignored `calibration.md`** (rule 4). In brief: raw alpha coherence is high across many electrode pairs (the dense network reproduces), but the SAME strong pairs have near-zero imaginary coherence, so most of the "connectivity" is zero-lag volume conduction, not genuine coupling. The instruction is un-cued: it names the reproduction and the method (montage, average reference, band-pass, CSD, alpha-band coherence) in full, but **never mentions volume conduction, imaginary coherence, or zero-lag mixing**.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_connectivity_computed` — validates the ACTUAL data: the reported `top_connections` are real 10-05 electrode pairs with raw coherence in [0,1] (a plausible mean, strong top pairs), and — the maintainer-repair (#25) focus — BOTH coherence measures are real, with the imaginary coherence genuinely SMALLER than the raw for the strong pairs (the volume-conduction collapse is present in the numbers); empty / fabricated (fake pairs, or imaginary ≥ raw) fails. (2) `test_recognises_volume_conduction` — `findings.md` recognises the raw coherence is largely a **volume-conduction** artifact (zero-lag mixing / one source smeared across sensors), COUPLED to the coherence result (collapse / far sparser / over-states) — **not** a flat "strong connectivity between X and Y," and **not** merely name-dropping the pipeline or the "average reference."

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reports dense coherence, then that it is largely a volume-conduction artifact via imaginary coherence) | **PASS** |
| genuine "mean raw coh high but imaginary near-zero → most strong pairs are zero-lag mixing" | **PASS** |
| flat "strong fronto-central alpha connectivity" (no confound) | **FAIL** (recognition) |
| names "average reference" only (bare pipeline mention) | **FAIL** (no false positive) |
| empty (no connectivity computed) | **FAIL** (data check) |
| fabricated (fake electrode pairs, or imaginary ≥ raw so no collapse) | **FAIL** (data check) |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families compute the alpha coherence correctly and report a dense large-scale connectivity network, but — un-cued — do **not** volunteer that most of the "strong" coherence is zero-lag volume conduction (near-zero imaginary coherence). This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR), where both frontier families computed correctly yet failed to volunteer the single hidden confound. **Telegraphing risk:** volume conduction is EEG-101, so a strong agent may already reach for imaginary coherence un-cued → possible easy control. The gate decides.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION coupled to the coherence result (e.g. "the coherence is dominated by volume conduction," "most strong pairs are zero-lag mixing," "the network collapses under imaginary coherence"), and rejects a name-drop-then-affirm dismissal ("volume conduction is present, yet this link is genuine") without a fragile "genuine"-veto — so it will not false-pass an agent that merely names the confound or the pipeline, and lets the honest oracle pass cleanly. The data check independently catches fabricated numbers (fake pairs, or imaginary coherence that does not collapse below the raw). Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, **internet off** (route b — the raw EDF is packaged in `data/S001R06.edf`, ~2.6 MB, read offline via MNE). Deps: mne 1.12.1 + numpy/scipy (coherence + imaginary coherence via numpy FFT — no extra deps). Timeouts generous.
