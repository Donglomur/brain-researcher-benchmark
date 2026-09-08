## N170PROFILE-001

**Proposal Title:** Spatiotemporal profile of the N170 face effect — an un-cued multiple-comparisons trap (hard EEG/ERP)

**Scientific Domain:** Life Sciences / Neuroscience / EEG-ERP (face perception, N170)

**Source paper / dataset:** Kappenman, Farrens, Zhang, Stewart & Luck (2021), *ERP CORE: An open resource for human event-related potential research*, NeuroImage, https://doi.org/10.1016/j.neuroimage.2020.117465. Data: ERP CORE **N170** continuous EEGLAB recordings (`<n>_N170_shifted_ds.set/.fdt`), subjects 1-12, fetched at runtime from the ERP CORE OSF node (`pfde9`) via pinned `https://osf.io/download/<id>/` file ids.

**Status: FULL runnable task; oracle + adversarial validated locally. Step-5 frontier calibration PENDING (maintainer step).**

### Genre
Process / rigor (recognition), same style as DEVCONN-001 / SOCIALBRAIN-001. The whole preprocessing pipeline is pinned in the instruction — subjects 1-12, **average reference**, filter 0.1-30 Hz, epochs -200..400 ms, -200..0 baseline, 150 uV rejection, face codes 1-40 / car codes 41-80. The reference (which was the un-cued lever in the retired FACEERP-001) is now pinned, so it is not a confound. The **only** open, un-cued judgement is *how to decide where/when the two conditions "reliably differ"* across the ~4600 electrode-by-time comparisons.

### The un-cued lever (PRIVATE — never named in instruction.md)
Correction for **multiple comparisons**. The instruction asks the agent to map the face-minus-car difference across the 30 scalp electrodes and the whole epoch and report where/when faces and cars *reliably differ* (onset latency, time range, and the set of electrodes). The natural default — a point-by-point one-sample t-test at every electrode and every sample, thresholded at p<.05 — is exactly what a competent analyst reaches for AND it is wrong. The instruction never says "multiple comparisons", "correction", "cluster", "permutation", "FDR", or "family-wise". The honest analyst volunteers a correction (cluster-based permutation / TFCE / FDR / Bonferroni) and reports only the corrected effect.

### Why this is off the critical path (un-cued volunteered judgement)
The agent can fully answer the request — produce an onset, a time range, and a set of "significant" electrodes — WITHOUT ever correcting. The failure is therefore a volunteered-rigor gap, not a step the request forces: uncorrected mass-univariate testing yields a well-formed (but wrong) answer.

### Step-0 result (measured; subjects 1-12, average reference, per-subject face-minus-car difference waves)
| analysis | result |
|---|---|
| PO8 face-minus-car peak (110-150 ms, per-subject then mean) | **-6.15 uV** (sanity: the N170 is real and correctly measured) |
| **NAIVE** uncorrected point-wise t-test (p<.05), 30 ch x 154 samples (~4600 tests) | **754** significant electrode-time points, **125 of them in the pre-stimulus baseline** (physically impossible), across **all 30/30 electrodes**, first "significant" at **35 ms** |
| **HONEST** spatio-temporal cluster-based permutation (electrode adjacency) | reliable effect confined to **82-145 ms** over **28 posterior-dominant electrodes**; onset **82 ms**; baseline/early false positives gone (two clusters, p=.004 and .018) |

The 125 baseline "significant" points are the load-bearing measured signal: they cannot be a real face-vs-car effect (they precede the stimulus), so they are unambiguous multiple-comparisons false positives that the correction removes. This is a real, measured pitfall on the data (no fabricated trap), matching the Eklund-2016 / mass-univariate ERP-methods literature.

### Verifier (3 plain checks, `tests/test_outputs.py`)
1. **N170 computed** — `n170.json` reports a PO8 peak with |amp| in [4.5, 8.0] uV (the ~-6.15 N170), n_subjects>=12, a `sig_time_range_ms` overlapping the N170 window (80-220 ms), and PO8 among `sig_electrodes`. Ensures the ERP pipeline is right and the real effect was found.
2. **Multiple-comparisons recognition** (the discriminator, co-occurrence guarded, DEVCONN-style) — `findings.md` must EITHER volunteer a genuine positive correction (a real method/concept co-occurring with the effect; a bare "did NOT correct for multiple comparisons" hedge is excised first) OR explicitly flag the uncorrected point-wise map as spurious (baseline / early / whole-scalp false positives). Correction-method tokens are not part of the pinned pipeline vocabulary, so a naive write-up cannot trip them; "baseline"/"uncorrected" only count when tied to a spurious claim (guards the SOCIALBRAIN-style pipeline-vocabulary false positive).
3. **Reports the profile** — `findings.md` reports the N170 face effect at PO8/posterior with a PO8 amplitude consistent with `n170.json`.

No weighted rubric, no score.json.

### Discrimination (validated locally: oracle + 8 adversarial variants)
| solution | verdict |
|---|---|
| reference / oracle (cluster-based permutation correction) | **PASS** (reward 1.0) |
| honest via FDR correction | **PASS** |
| honest via cluster permutation, no editorializing | **PASS** |
| honest: flags uncorrected baseline/early false positives, reports clean 110-190 ms posterior effect | **PASS** |
| naive: reports inflated 35-300 ms / all-30-electrode uncorrected profile as real | **FAIL** |
| naive: eyeballed clean window but never engages multiple comparisons | **FAIL** |
| naive: labels p-values "uncorrected" but no recognition/correction | **FAIL** |
| hedge: "I did not correct for multiple comparisons" + inflated result | **FAIL** |
| wrong ERP pipeline (PO8 peak -2.9 uV) | **FAIL** (computed gate) |

### Cost
`hard`. cpus 2, mem 8 GB, internet on (fetches 12 subjects x 2 EEGLAB files ~0.5 GB from OSF at runtime). Deps: mne 1.12.1 + numpy 2.2.6 + scipy 1.14.1. Oracle runtime ~2-4 min (cluster permutation is fast on 12 x 30 x 154).

### Notes / caveats
- **Grader is recognition-genre (prose-graded judgement)** — the intrinsic ceiling noted in the tb-science skill (Step 4). It is guarded with a co-occurrence check tuned against 8 real/adversarial write-ups (oracle + naive + hedge + defensible-correct), following the DEVCONN/SOCIALBRAIN false-positive lessons.
- **A "lucky eyeballer"** who reports a substantively-correct posterior window without engaging multiple comparisons FAILS the recognition gate by design: the deliverable requires an electrode-and-time significance characterization, so the intended honest path passes through the multiple-comparisons decision.
- **OSF-fetch reliability caveat:** the shipped fetch pulls 24 files from `osf.io/download/<id>/` at runtime; OSF occasionally throttles/times out (transient failure -> `failed_precondition`, not a task FAIL). For dev, `ERPCORE_N170_DIR` can point at a local cache.
- Step-5 frontier calibration (>=2 frontier families, k>=3, hand re-scored) is the maintainer gate and is PENDING; this proposal ships the oracle-pass + adversarial-fail evidence.

### Replaces
FACEERP-001 (PR #146), whose lever was the EEG reference convention (average vs mastoid) — a knowledge convention a frontier model likely already knows (rated MODERATE). This task keeps the same ERP CORE N170 data and EEG modality but moves onto a genuinely un-cued rigor axis (multiple comparisons) where the analyst default is actually wrong.
