## ERRMON-001  (DOWNGRADED to an honest EASY CONTROL)

**Proposal Title:** Error-related frontocentral negativity in the ERP CORE Flankers task — a clean single-subject ERP reproduction (calibration control)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** cognitive EEG / event-related potentials

**Source finding / dataset:** The **error-related negativity (ERN)** — the frontocentral (FCz) negativity that follows an erroneous button press — quantified as the **mean error-minus-correct amplitude at FCz in the 0-100 ms post-response window** for the **ERP CORE** Flankers task (subject 001). **Dataset:** fetched at runtime with `mne.datasets.erp_core.data_path()` (no credentials). Genre: **reproduction (easy control)**.

### Audit verdict: no fair un-cued hard lever survives → downgrade to control

The prior version's only lever was the **epoch time-locking** (response vs stimulus): the ERN emerges when epochs are locked to the erroneous **response** (~-5.9 µV at FCz) and all but cancels when locked to the **stimulus** (~-0.6 µV), because the button press follows the flanker array by a variable ~400 ms. This does **not** clear the tb-science bar (GRADIENT/SOCIALBRAIN/DEVCONN), for two reasons:

1. **It is knowledge recall, not an un-cued metacognitive gap.** The ERN is *by definition* a response-locked component — a fact frontier agents reliably know. The difficulty ladder (skill Step 2) shows procedural/knowledge items are absorbed by priors; the frontier gap is metacognitive (does the agent volunteer a check it was not told to run), which time-locking is not. An agent that knows the ERN is response-locked simply does it right, so there is no population gap to gate on.

2. **No other un-cued, off-critical-path lever with a real, defensible signal survives on this pipeline.** Checked and rejected: the **flanker-compatibility confound** in error-minus-correct (errors are mostly incompatible) is smeared by RT jitter under response-locking and leaves no clean, large, defensible signal; **single-subject reliability** (54 error trials) is a caveat, not a wrong-number lever, and the value reproduces robustly; **baseline window, low-pass edge and reference** are all pinned (and the within-electrode difference is convention-robust to the first two). There is no remaining axis a frontier agent would skip that materially moves a defensible number.

Per the hardening spec ("if none survives that a frontier agent would skip, DOWNGRADE it to an honest easy-control rather than forcing an unfair trap"), the task is relabeled as a **control** and the trap is removed.

### What changed (de-trapped)

- The ambiguous "epoch the data around the events of interest" is replaced by an explicit pin: **epoch time-locked to the button-press (response) event**, with a **pre-response baseline** and the **0-100 ms post-response** measurement window. This removes the hidden penalty for a reasonable analyst who might otherwise stimulus-lock, making the task a clean, fully-pinned reproduction.
- `task.toml` difficulty `hard` → `easy`.
- The verifier is reframed from a response-vs-stimulus discriminator to a straightforward reproduction gate (the docstring states it is a control).

### Step-0 (validated, real data — MNE 1.12.1)

Pinned pipeline; mean error-minus-correct amplitude at FCz, 0-100 ms post-response window (subject 001, 400 trials paired, 54 errors / 346 correct): **response-locked ERN = -5.9 µV** (real reference re-run: **-5.91 µV**). Robust **-5.5 to -6.2 µV** across low-pass 15/20/30/40 Hz and pre-response baseline windows, average reference.

### Verifier (3 plain checks — reproduction)

`tests/test_outputs.py`: (1) an ERN amplitude averaged over a plausible number of error trials is reported; (2) the reported amplitude **magnitude** reproduces the response-locked value (`| |amp| − 5.9 | < 2.0` µV); (3) `findings.md` reports an amplitude consistent with `ern.json`. Schema-robust: searches any depth, matches on magnitude (an unsigned report also passes), and excludes explicitly-labelled per-condition / reference fields.

### Validation (MEASURED locally)

- **Oracle** (`solution/compute.py`, real ERP CORE fetch, 54 error / 346 correct): ERN = **-5.91 µV**; verifier **PASS (3/3)**.
- **Off-pin fixture** (stimulus-locked -0.58 µV — did not follow the pinned response-locking): **FAIL** — the reproduction gate still bites.
- **Defensible variant** (-6.1 µV from a different low-pass): **PASS**. **Grossly-wrong** (-1.2 µV): **FAIL**.
- Data fetches at runtime via the MNE ERP CORE fetcher (no credentials); `allow_internet=true`.
- **Role:** calibration control (proves a clean single-subject ERP reproduction is solvable in-container). **Live gate = maintainer.**

### Cost

`easy` (control). cpus 2, mem 8 GB, storage 20 GB, internet on (downloads the ~92 MB ERP CORE Flankers bundle once). Deps: mne 1.12.1 + numpy/scipy/pooch. Sensor-space EEG only.

---

## Proof-of-work verifier (2026-09)

The prior grader accepted any `ern.json` whose single `ern_amplitude_uv` magnitude was
~5.9 (|.| in [3.4, 8.4]) — a fabricated scalar + a keyword `findings.md` passed. This
revision applies the suite-wide proof-of-work contract (single-value / RESTCONN model). The
pinned response-locking makes this a clean reproduction control (QSMDIPOLE model): the
held-out reference makes the number hittable only by the real response-locked analysis.

**Held-out reference** (`tests/reference.npz`, built from `solution/compute.py` on the real
ERP CORE Flankers subject-001 recording, never shipped to the agent): the FCz error-average
and correct-average response-locked waveforms (820 samples over -0.25..0.55 s) + `ref_stats`
(response-locked window ERN -5.91 uV, stimulus-locked -0.58 uV). sha256
`c13453fca50176b773ab10bc52eedef027b61c8162d030073bca0ade93fb9d96`.

**Neutral intermediate** (added to Required Outputs): `fcz_waveforms.csv` — the FCz
error/correct averages vs time. Any ERP analysis produces these; matched to the held-out
response-locked reference they close fabrication AND a stimulus-locked analysis (the
response- and stimulus-locked FCz difference waveforms are ~uncorrelated, r ~ -0.13).

**Four pillars**: (1) the submitted error waveform tracks the reference (r>=0.80) and the
error-minus-correct difference waveform tracks the reference (r>=0.75); (2) the window ERN
recomputed FROM the waveforms == reference == reported `ern.json`; (3) the ERN graded as a
negativity (<= -2.5 uV), closer to the response-locked value than the stimulus-locked one;
(4) secondary prose.

**Validation** (subprocess pytest per case, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, numpy 2.1.3):

| case | result |
|---|---|
| honest (oracle) | PASS |
| defensible (waveforms + numerical noise) | PASS |
| no waveforms | FAIL |
| constant waveforms | FAIL |
| fabricated (right window ERN, scrambled waveforms) | FAIL (pillar 1 only — the intended teeth) |
| naive stimulus-locked waveforms | FAIL |

Data still fetches at runtime (`allow_internet=true`); baking the derived FCz epochs is a
maintainer follow-up.
