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
