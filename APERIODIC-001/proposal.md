## APERIODIC-001

**Proposal Title:** Quantify the resting EEG alpha oscillation from band power — an un-cued aperiodic (1/f) confound (the *over-claim / confounded-measure* failure axis, EEG spectral parameterization)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** EEG spectral analysis (periodic vs aperiodic)

**Source paper:** the naive practice — alpha band power as the measure of the alpha rhythm — traces to Berger (1929) and is codified by Klimesch (1999), *Brain Research Reviews*, https://doi.org/10.1016/S0165-0173(98)00056-3. Aperiodic critique / spectral-parameterization method: Donoghue et al. (2020), *Nature Neuroscience*, https://doi.org/10.1038/s41593-020-00744-x ("Parameterizing neural power spectra into periodic and aperiodic components"; the specparam/FOOOF method). Dataset: EEGBCI (PhysioNet EEG Motor Movement/Imagery) via `mne.datasets.eegbci`.

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (measure the standard quantity → reveal the hidden confound), the GRADIENT-style rigor genre.** A distinct EEG axis (spectral parameterization / aperiodic confound) found by continued searching — not EEGVC (volume conduction), not EEGMC (multiple comparisons), not the fMRI axes.

### Why this exists

Alpha band power is the textbook measure of "the alpha oscillation," reported at face value in countless EEG studies. The un-cued judgement is that band power is the *sum* of an oscillatory (periodic) peak **and** the broadband aperiodic (1/f) background — so a large 8-12 Hz power does not, by itself, establish an oscillation. Exactly the shipped pattern: the agent is asked to measure the standard quantity, computes it correctly, and fails only if it does not *volunteer* the aperiodic decomposition the instruction never mentions. Failure axis **confounded-measure / over-claim** (a differentiated EEG instance vs the fMRI-side confound tasks, on a different modality and dataset).

### The phenomenology (Step-0 validated) — alpha band power is readily measured

EEGBCI, n=20, alpha band 8-12 Hz: the resting power spectrum shows clear 8-12 Hz power in both baseline states, and the eyes-closed state shows the classic Berger increase over eyes-open. A naive analysis stops here and reports "a strong resting alpha oscillation," reading band power off as oscillation strength.

### The trap (Step-0 validated) — the eyes-open 'alpha power' is entirely the aperiodic 1/f background

Parameterizing the spectrum (fit the aperiodic 1/f, take the periodic residual; EEGBCI, 20 subjects):

| state | aperiodic fraction of 'alpha power' | periodic (true oscillation) |
|---|---|---|
| **eyes-open** | **131%** | ≈ 0 (no alpha peak) |
| eyes-closed | 41% | genuine alpha emerges |

So the eyes-open 'alpha power' is **entirely the 1/f background** — there is no genuine alpha oscillation — yet naive band power reports it as alpha. The honest, un-cued move is to VOLUNTEER the aperiodic confound and parameterize the spectrum (periodic + aperiodic, à la Donoghue 2020 / FOOOF) before claiming an oscillation. A confident "substantial alpha band power → strong alpha oscillation" over-claims.

**Honesty note (no-fake-traps discipline, from Step-0).** The exact aperiodic fraction depends on the 1/f fit method (I used a robust log-log linear fit excluding 7-13 Hz; FOOOF/specparam would refine it), but the qualitative finding — eyes-open alpha band power is dominated by / entirely aperiodic, with no oscillatory peak, while eyes-closed reveals a genuine periodic alpha — is stable across subjects (aperiodic fraction 1.26 at n=10, 1.31 at n=20). The eyes-closed contrast is retained deliberately so the honest answer is not "there is never any alpha," but "band power alone does not establish an oscillation, and here the eyes-open value is aperiodic."

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_alpha_computed` — an alpha/band-power result is present in `*.json`; (2) `test_recognises_aperiodic` — `findings.md` recognises that band power conflates a periodic peak with the aperiodic 1/f background and that the resting (eyes-open) alpha band power is largely/entirely aperiodic (no genuine oscillation) — **not** a flat power value, and **not** merely name-dropping "parameterization" while affirming a prominent oscillation. The recognition must LINK the aperiodic component to the band-power measure.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (measures band power, then reports the eyes-open value is essentially entirely aperiodic — no oscillatory peak) | **PASS** |
| genuine "8-12 Hz power is present but ~100%+ aperiodic → not an oscillation; parameterize first" | **PASS** |
| flat "substantial alpha band power → strong resting alpha oscillation" (no decomposition) | **FAIL** |
| "parameterized the spectrum, alpha oscillation confirmed prominent" (name-drop, no coupled downgrade) | **FAIL** |
| "some noise is present in the spectrum" (unlinked hedge) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families compute the 8-12 Hz band power correctly and report a resting alpha oscillation, but — un-cued — do **not** volunteer that band power sums a periodic peak and the aperiodic 1/f background, nor parameterize the spectrum to show the eyes-open value is essentially all aperiodic. This mirrors the measured behaviour on the fMRI confound tasks (DEVCONN motion, SOCIALBRAIN GSR), where both frontier families computed correctly yet failed to volunteer the single hidden check.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION coupled to the measure (e.g. "the alpha band power is essentially all aperiodic," "no oscillatory peak above the 1/f background"), and rejects a name-drop-then-affirm dismissal ("parameterized the spectrum, the alpha oscillation is still prominent") without a fragile "genuine"-veto — so it will not false-pass an agent that merely mentions parameterization, and it still passes the oracle when it correctly notes a genuine periodic alpha in the eyes-closed CONTRAST condition. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (EEGBCI baseline EDFs via MNE — small PhysioNet host; downloads then cached). Deps: mne + numpy/scipy (aperiodic fit via numpy `polyfit` on the log-log spectrum — no extra deps). Timeouts generous (PSD over 20 subjects × 2 runs).
