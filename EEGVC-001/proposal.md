## EEGVC-001

**Proposal Title:** EEG alpha-band functional connectivity (eegbci) — an un-cued volume-conduction confound (the *wrong-cause / confound* axis on a new **EEG modality**)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** EEG functional connectivity

**Source finding:** Nolte et al. (2004), *Clinical Neurophysiology*, https://doi.org/10.1016/j.clinph.2004.04.029 (imaginary coherence is insensitive to zero-lag volume conduction). Dataset: PhysioNet EEG Motor Movement/Imagery (Schalk et al. 2004) via `mne.datasets.eegbci`.

**Status: FULL runnable task, built with `tb-science-task-authoring`.** **First task on the EEG modality** — the whole shipped + session suite was fMRI (connectivity/decoding); this breaks the single-modality monoculture. The failure axis (**wrong-cause / confound**) is shipped (DEVCONN motion), but on a **new modality** it fills a fresh axis×modality cell (the anti-monoculture point).

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### The trap (Step-0 validated; `scratchpad/eeg_step0.py`)
eegbci subject 1 run 6, 64 ch, average reference, alpha 8–13 Hz:

| measure | value |
|---|---|
| mean raw coherence | **0.417** |
| mean \|imaginary coherence\| | **0.067** |
| raw / imaginary ratio | **~6.2×** |
| fraction of raw-coh>0.5 pairs that are volume conduction (imcoh<0.1) | **74%** |

~3/4 of the "strong" EEG connectivity is spurious zero-lag volume conduction — the same source picked up by multiple electrodes. The honest analyst uses a lag-insensitive measure (imaginary coherence); un-cued, an agent reports raw coherence and over-states connectivity ~6×.

### Verifier (2 plain checks) + local calibration
`tests/test_outputs.py`: (1) EEG connectivity/coherence computed; (2) `findings.md` recognises the raw coherence is largely a **volume-conduction** artifact (zero-lag mixing / imaginary coherence) — a flat "strong connectivity between X and Y" over-states it. Linked-insight + strong-token guard (a bare "average reference" mention does not pass).

Local calibration (`scratchpad/validate_eegvc.py`):

| output | computed | recognises_VC |
|---|---|---|
| **oracle** | PASS | PASS — reward 1.0 |
| correct (volume conduction / imaginary coherence) | PASS | PASS |
| flat "strong fronto-central connectivity" | PASS | **FAIL** |
| names "average reference" only | PASS | **FAIL** (no false positive) |
| vague "rich and complex" | PASS | **FAIL** |
| broken (no connectivity) | **FAIL** | — |

### Honest caveats / open risks
1. **Difficulty UNTESTED** — needs the gate. **Telegraphing:** volume conduction is EEG-101; a strong agent may already use imaginary coherence → possible easy control. The gate decides.
2. **Prose/judgement verifier** (rigor genre) — linked-insight + strong-token guards mitigate false positives.
3. **New dependency:** `mne` + `pooch` (pinned); data downloads from PhysioNet at runtime (`allow_internet`).

### Cost
`hard`. cpus 2, mem 8 GB, internet on (eegbci EDF via MNE/PhysioNet — small, reliable). Deps: mne 1.12.1 + pooch + numpy/scipy.
