# BLOCKED papers — OpenNeuro re-triage (2026-08-07)

After the OpenNeuro unlock (S3-HTTPS + dipy-affine + CompCor pipeline → analysis-ready connectomes with
no data-use agreement; first task TRANSDX-001), the **149 BLOCKED-DATA papers** were re-triaged: which
are now reachable, which stay hard-gated.

## 149 BLOCKED → 80 now-reachable · 79 still hard-gated

### Now-reachable via OpenNeuro (80) — disorder/task fMRI or structural
Clinical & cognitive datasets that OpenNeuro hosts as raw BIDS, processable by the pipeline:

| bucket | papers | status |
|---|---:|---|
| schizophrenia / bipolar / ADHD | (done) | **built → TRANSDX-001** (UCLA CNP ds000030) |
| alzheimer disease + MCI | 16 | Step-0 in progress |
| parkinson disease | 8 | Step-0 in progress |
| major depression | 7 | Step-0 in progress |
| epilepsy | 7 | Step-0 in progress |
| multiple sclerosis | 5 | Step-0 in progress |
| stroke | 4 | Step-0 in progress |
| traumatic brain injury | 4 | Step-0 in progress |
| EEG / MEG clinical | 9 | reachable (mne / OpenNeuro) |
| task paradigms (sleep, memory…) | ~20 | reachable (OpenNeuro task fMRI) |

### Still hard-gated (79) — no open dataset, special acquisition or consortium
`PET` / amyloid / tau tracers · `MRS` / spectroscopy · `ASL` / perfusion · `SWI` / `QSM` / iron ·
`qMRI` / relaxometry / myelin · `7T` / high-field / laminar · `UK Biobank` · `HCP` · `ABCD` · `ENIGMA` ·
imaging genetics / GWAS. These need the specific modality hardware or a registered-access consortium —
not unlockable by processing open BIDS.

## The honest caveat on the 80
Reachable ≠ a new task. Most disorder datasets, once processed, yield the SAME failure axes already
built — a plain "classify disorder X vs control" duplicates BASERATE/DECODE, and "X classifier also
detects Y" duplicates TRANSDX. A genuinely NEW task needs a **disorder-specific reproducible finding**
whose natural trap is none of the 23 built axes, AND that finding must survive the lightweight
(affine + CompCor, no fMRIPrep) pipeline. The per-disorder Step-0 (workflow wf_b56f714a-606) tests
exactly that; results appended below.

## Per-disorder Step-0 results (workflow wf_b56f714a-606 + my verification)

7 reachable disorders processed through the real pipeline → **0 new tasks**:

| Disorder | Dataset | Verdict | Why |
|---|---|---|---|
| schizophrenia/bipolar/ADHD | ds000030 CNP | **BUILT (earlier)** | TRANSDX-001 (non-specificity) — classification survives preprocessing |
| epilepsy (TLE) | ds004469 | **DROP** (verified) | laterality axis was genuinely novel, but the ipsilateral hippocampal-FC reduction does NOT reproduce: native null (p=0.32/0.30) AND ipsi-aligned also null (d=−0.13, p=0.65) |
| parkinson | ds004392 | DROP | FC→cognition at chance (r=0.03); severity classification AUC 0.50; only sig effect is age-confounded wrong-sign |
| major depression | ds002748 | DUP | every MDD FC finding → DECODE/BWAS/AUTCONN/BRAINAGE/DYNFC (biotypes = un-CV CCA + null-cluster) |
| TBI | ds000220 | DROP | atrophy/partial-volume confound doesn't reproduce |
| stroke | ds003999 | **hemodynamic-lag → separate build** | axis distinct (within-patient timing artifact); running now |
| MS / alzheimer | — | BLOCKED | no adequate OpenNeuro rest-fMRI patient+control cohort |

## The honest empirical verdict on the 80 reachable papers
Testing the top disorders **falsified the optimistic count**: the 80 reachable papers yield **~0 additional
non-duplicate tasks** with the available (lightweight, no-fMRIPrep) preprocessing, because of a hard
dichotomy —
- **Robust findings** (disorder-vs-control classification) survive preprocessing but **duplicate built
  axes** (BASERATE / DECODE / TRANSDX).
- **Subtle disorder-specific findings** (regional FC contrasts: epilepsy hippocampus, Parkinson
  striato-cortical, TBI hyperconnectivity) **wash out** without fMRIPrep-grade preprocessing.

So the clinical growth reserve's real yield was **one task (TRANSDX)** — the schizophrenia case worked only
because classification is preprocessing-robust AND the non-specificity twist is a new axis. The lone
remaining structurally-different candidate is **stroke hemodynamic-lag** (a within-patient signal-timing
artifact, robust by nature) — build result appended if it reproduces.

## Paper-by-paper Step-0 of all 80 reachable (workflow wf_dfeeb04f-0a5)
Re-ran the reserve **paper by paper** (not by disorder), each paper judged on its own specific finding:

| verdict | count |
|---|---:|
| NO-TASK-infra (tool/pipeline/segmentation/benchmark) | 31 |
| DUP-of-built | 27 |
| DROP-washes-out (subtle regional FC, no fMRIPrep) | 10 |
| BLOCKED-no-dataset | 8 |
| BUILD-CANDIDATE | 2 (same axis) |

The **only** candidate the granular pass surfaced beyond the disorder sweep: **Drysdale 2017 + Dinga 2019
depression "biotypes"** — the spurious-clustering / cluster-validity axis (unsupervised subtyping always
returns k groups; test cluster tendency/stability vs a null). Step-0'd on cached ABIDE and **DROPPED**: the
refutation is not clean — k=2 silhouette 0.34 looks like biotypes, but Hopkins (0.66) and the gap statistic
are ambiguous, cluster stability (0.54) is inconclusive, and the split is actually driven by **global mean
connectivity** (0.357 vs 0.182), a nuisance-scaling artifact rather than the clean "unimodal, no clusters"
story. It is also a borderline near-duplicate of DYNFC (clustering manufactures apparent structure, refuted
by a null). Two strikes → drop.

## FINAL yield of the entire BLOCKED reserve (149 papers)
- **79 hard-gated** (PET/MRS/ASL/SWI/qMRI/7T/consortium/genetics) — genuinely unreachable.
- **80 reachable** → **1 task built (TRANSDX-001)** + **stroke hemodynamic-lag** (pending) + 0 others.
Empirically, "reachable" almost never means "new non-duplicate hard task": the reserve collapses under two
forces — robust findings duplicate built axes, subtle findings wash out without fMRIPrep, and the rest are
tools. The reserve's value was **proving the OpenNeuro-clinical pipeline works** (TRANSDX) and mapping,
paper by paper, exactly what is and isn't there.
