## N170PROFILE-001

**Proposal Title:** The ERP CORE N170 face effect at PO8 — full N=37 analysis sample, signed per-subject amplitude + 50%-fractional-peak onset, proof-of-work verifier

**Scientific Domain:** Life Sciences / Neuroscience / EEG-ERP (face perception, N170)

**Source paper / dataset:** Kappenman, Farrens, Zhang, Stewart & Luck (2021), *ERP CORE: An open resource for human event-related potential research*, NeuroImage, https://doi.org/10.1016/j.neuroimage.2020.117465. Data: ERP CORE **N170** continuous EEGLAB recordings (`<n>_N170_shifted_ds.set/.fdt`) from the ERP CORE OSF node (`pfde9`). The task ships the **per-subject face-minus-car difference waves** for the exact **N=37 analysis sample** baked into the image (`allow_internet=false`).

**Status: FULL runnable task; recut per maintainer review (PR #197, @zjc062); oracle + adversarial validated locally. Step-5 frontier calibration PENDING (maintainer step).**

### What this task measures (recut to the paper's actual N170 characterization)
Reproduce the ERP CORE N170 characterization exactly as Kappenman et al. report it in **Figure 2 / Tables 1-3**: over the **full N=37 analysis sample**, at the **a priori PO8 electrode**, from the **face-minus-car difference wave**. The two headline measurements, computed **per subject** and aggregated to a group mean + 95% CI:

1. **Signed PO8 mean amplitude, 110-150 ms** — the ERP CORE N170 amplitude score (`meanbl` on the difference wave; Table 2 window 110-150 ms; a negative value; paper group mean −3.37 µV, SD 2.71).
2. **50% fractional-peak onset latency** — the ERP CORE onset measure (ERPLAB `fpeaklat`, negative polarity, peak searched in 10-150 ms, onset = pre-peak crossing of 50% of the peak; paper 95.76 ms, SD 29.05).

The N=37 analysis sample is the ERP CORE N170 grand-average/measurement sample: **subjects 1-40 excluding 1, 5 and 16** (verified against the ERP CORE processing scripts `9_Grand_Average_ERPs.m` / `12_Measure_ERPs.m`, whose `SUB` list is exactly these 37).

### Changes vs the reviewed version (addressing every point of the @zjc062 review)
- **Full N=37 analysis sample** (was subjects 1-12). **A priori PO8** electrode (was a data-derived "most significant" electrode set). Effect measured **at PO8** from the difference wave.
- **`onset_latency_ms` is now the paper's 50%-fractional-peak onset** (was the cluster-derived onset).
- **`sig_electrodes` removed.**
- The whole-scalp cluster analysis is **descriptive**, not pointwise significance: if reported, it carries the **corrected cluster p-value(s) + cluster mass**, and its time/electrode membership is labelled **`cluster_level_only`**. The "uncorrected point-wise significance is spurious" judgement remains, but only as a caveat — the headline is the PO8 amplitude + 50%-fractional-peak onset with **signed per-subject values**.
- **Verifier requires signed per-subject measurements and recomputes the group result** (below); it no longer checks prose keywords or `abs(amplitude)`.

### Packaging (proof-of-work / reproducibility)
- **Baked inputs, no internet.** The per-subject face-minus-car difference waves for the exact 37 subjects (produced by the pinned pipeline: EOG excluded, band-pass 0.1-30 Hz, faces=codes 1-40 / cars=41-80, epochs −200..400 ms, average reference, −200..0 baseline, 150 µV rejection) are baked to `/app/data/n170_diff_waves.npz` (`subjects` [37], `diff_uv` [37×30×n_t] µV, `ch_names`, `times_ms`, `sfreq`). `task.toml` sets `allow_internet=false`; the image installs `pytest` so the verifier needs no network.
- **Provenance pinned:** the exact ERP CORE OSF file ids for the 37 subjects and per-file SHA-256 hashes, and the SHA-256 of the baked `.npz`, are recorded in `n170_provenance.json` (build artifact). Excluded subjects: 1, 5, 16.

### Held-out reference + proof-of-work verifier (`tests/`)
`tests/reference.npz` (held out; never shipped to the agent) is built by running `solution/compute.py` on the exact 37-subject data: per-subject SIGNED PO8 amplitude + 50%-fractional-peak onset, group mean/CI, and the corrected cluster p-value / mass. `tests/proof_of_work.py` provides the reusable checks; `tests/test_outputs.py` calls them in three pillars:
1. **Exact subjects + signed per-subject values** — `per_subject.csv` must cover ≥90% of the 37 reference ids (no fabricated-id padding), be **non-constant**, and match the held-out per-subject values **SIGNED** (amplitude tol 0.40 µV @ ≥90%; onset tol 25 ms @ ≥70%, onset being noisier per subject). No `abs()`.
2. **Recompute + cross-check** — the group mean recomputed **from the submitted rows** must match BOTH the reference AND the reported JSON headline (amplitude tol 0.30 µV, onset tol 12 ms).
3. **Conclusion as numbers** — reported signed amplitude (negative, tol 0.30 µV) and 50%-fractional-peak onset (tol 12 ms, and explicitly distinct from the uncorrected/cluster "onset"); and, **if the cluster analysis is reported**, its corrected cluster p-value (tol 0.03) and cluster mass (rel tol 0.35). A prose `findings.md` profile check remains only as a SECONDARY signal.

### Ground truth (measured on the exact 37-subject baked data; see `tests/reference.npz`)
| quantity | value |
|---|---|
| PO8 signed mean amplitude 110-150 ms (per-subject then mean) | **−3.66 µV**, 95% CI [−4.60, −2.71] (paper: −3.37 µV, SD 2.71) |
| 50% fractional-peak onset (per-subject then mean) | **110.7 ms**, 95% CI [104.5, 116.9] (paper: 95.76 ms on their ICA/LP pipeline) |
| finite per-subject onset | 37/37 |
| whole-scalp corrected cluster | p=0.002, mass 1377.2, descriptive support 74-156 ms over 17 electrodes |
| naive uncorrected point-wise | 149 pre-stimulus-baseline "significant" points; first "significant" at 0 ms (spurious) |

The signed PO8 mean amplitude reproduces the ERP CORE score (−3.66 vs −3.37 µV). The
50%-fractional-peak onset lands ~111 ms on the task's pinned pipeline (band-pass 0.1-30 Hz, no
ICA / no extra low-pass) vs 95.76 ms in the paper's fully processed data; it is the same
measure, and the verifier grades against the oracle's value on this pipeline (`reference.npz`),
not the paper's headline number. Baked data SHA-256:
`8d248b3dcbc7909277e3588c9c01b0f5ee81a24626ff2ff50d9113a3d1c61140` (OSF file ids + per-file
hashes in `solution/data_provenance.json`).

### Validation matrix (oracle + adversarial; run locally with the baked data + grader)
| solution | verdict | why |
|---|---|---|
| ORACLE (`solution/solve.sh`) — signed per-subject amp + 50%-fractional-peak onset over 37 | **PASS (6/6)** | reward 1.0 |
| fabricated JSON scalars + keyword sentence, NO per-subject table | **FAIL** | per_subject.csv missing (pillar 1) |
| right-number JSON + CONSTANT per-subject table | **FAIL** | non-constant guard (pillar 1) |
| right-number JSON + non-constant but FABRICATED per-subject table | **FAIL** | only 4/37 signed values match reference (pillar 1) |
| naive: uncorrected point-wise "onset" (0 ms) + amp-only table | **FAIL** | onset ≠ 50%-fractional-peak (pillar 3) + onset column absent (pillar 1) |
| abs(amplitude) reported (positive) | **FAIL** | amplitude not signed-negative (pillar 3a / signed match) |
| defensible-correct (independent recompute: strict window, 1 ms-grid onset, no cluster) | **PASS** | 6/6 within tolerance |

The reviewer's core objection is closed: the **single-JSON-scalar fabrication now FAILS** (the
old cut had no per-subject table, so fabricated scalars + a keyword sentence passed).

### Cost
`hard`. cpus 2, mem 8 GB, **internet off** (all inputs baked). Deps: mne 1.12.1 + numpy 2.2.6 + scipy 1.14.1 + pytest. Oracle runtime ~1-2 min (the cluster permutation on 37×30×n_t is fast; amplitude/onset are trivial once the difference waves are loaded).

### Notes / caveats
- The whole-scalp cluster test is retained only as a **descriptive** (cluster-level) summary; the grade never rests on pointwise electrode/time significance.
- Per-subject onset (50% fractional-peak) is intrinsically noisier than amplitude; the verifier puts the tight teeth on the signed amplitude + group recompute and grades onset with a looser per-subject tolerance but a tight group-level tolerance.
- Step-5 frontier calibration (≥2 frontier families, k≥3, hand re-scored) is the maintainer gate and is PENDING.

### Replaces
FACEERP-001 (PR #146) and the earlier N170PROFILE-001 cut (uncorrected-multiple-comparisons framing with a data-derived electrode set and a prose-graded judgement), per the maintainer review on PR #197.
