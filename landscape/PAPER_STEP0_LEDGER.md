# Per-paper Step-0 ledger — all 420 landscape papers (2026-08-05)

The landscape package gives **111 topics** with a ranked shortlist of **5–14 papers each** (median 8),
drawn from a **420-paper library** (845 topic→paper links; 85 papers serve >1 topic). This ledger runs
Step-0 (build-time feasibility) at the **paper** level — every one of the 420 gets a verdict.

## Method
Step-0 asks, per paper: can its primary empirical finding be (1) reproduced on cached/fetchable data
and (2) turned into an un-cued trap where a correct reference scores 1.0 but a naive-but-competent
agent fails — without duplicating a built task and without weak numbers? A fast local triage classifies
every paper; the genuinely feasible-empirical subset then gets **real code probes** (multi-agent).

## Triage of all 420 papers

| Bucket | Count | Meaning |
|---|---:|---|
| **NO-TASK-INFRA** | 207 | tool / pipeline / toolbox / dataset-descriptor / consensus paper — no empirical finding to trap (EEGLAB, FieldTrip, MNE, ComBat, CSD, fMRIPrep, MRIQC, atlas releases, …) |
| **BLOCKED-DATA** | 149 | finding needs data with no public one-command fetch (UK Biobank / HCP / ABCD / ENIGMA / imaging-genetics / PET / MRS / ASL / SWI / qMRI / 7T / clinical cohorts) |
| **FEASIBLE-PROBE** | 36 | empirical + cached-data-plausible → real code Step-0 (see below) |
| **COVERED** | 24 | topic/finding already realised by one of the 18 built tasks |
| **OTHER/UNCLEAR** | 4 | ambiguous metadata |

The library skews hard to infrastructure: **296 of 420** are typed "modern method/tool (2020+)" (auto-
added, flagged "verify"), and most curated entries are pipelines/toolboxes. This is why the topic→task
build rate is low by design — the landscape is mostly *methods*, and the *empirical* papers mostly need
gated data or reproduce an already-built axis.

## The 36 FEASIBLE-PROBE papers — real code Step-0 (workflow wf_f9b18a3d-a08, 5 agents)

Each of the 36 got a real probe. After a second dedup pass against the 3 **reference** tasks
(DEVCONN/SOCIALBRAIN/GRADIENT — which the agents didn't have), verdicts:

| Verdict | Count | Notes |
|---|---:|---|
| NO-TASK-INFRA | 10 | method/tool papers (Tournier CSD, Ashburner VBM/DARTEL, Rubinov, Bullmore, SPM book, Behrens ×2, …) |
| BLOCKED-DATA | 10 | need gated data (Wager pain, Knutson reward, Kay/Fedorenko/Binder task paradigms, sleep ×3, …) |
| DUPLICATE | 10 | Haxby→DECODE, Cole-BrainAge→BRAINAGE, Heinsfeld→CNN-dropped, Carp→MULTIVERSE, Ciric→DEVCONN, Finn→CPM-dropped, Schaefer→MODULAR, **Power 2012→DEVCONN** (motion), **Fox 2005→SOCIALBRAIN** (GSR) |
| DROP | 4 | non-reproducing / weak on cached data |
| **BUILD** | **2** | **Eklund 2016** + **Pierpaoli 1996** |

### The 2 new tasks (verified + built)
- **EKLUND-001** ← Eklund 2016 "Cluster failure". Parametric cluster-extent FWE inference is
  anti-conservative: on ADHD-200 resting null (CDT z>2.58), real-fMRI max-cluster p95 ≈ 137 vox vs a
  Gaussian field of matched smoothness ≈ 49 → using the parametric threshold gives **FWER ≈ 0.43, ~9×
  nominal**. Fix = permutation. Distinct from AUTCONN (edgewise FDR), SPMAR (temporal AR), MAPCORR
  (spin test). Oracle + 2 adversarials validated.
- **DIFFFA-001** ← Pierpaoli 1996 (FA) + Jeurissen 2013 (crossing fibers). **NEW modality: diffusion.**
  Single-tensor FA collapses in crossing-fiber voxels: 49% of WM crosses; FA 0.50 (single) → 0.33
  (crossing), 34% collapse; 84% of the lowest-FA WM voxels are crossing-fiber. Trap: read low FA as low
  integrity. Fix = crossing-aware model (CSD/fODF). dipy Stanford HARDI. Oracle + adversarial validated.

Two important reference-task collisions the sub-agents flagged as "novel" but are NOT: **Power 2012**
(motion→spurious FC) duplicates DEVCONN (which cites Power 2012), and **Fox 2005** (GSR→anticorrelation)
duplicates SOCIALBRAIN. Both correctly demoted to DUPLICATE.

## Bottom line
Of **420 papers**, exactly **2** yielded new non-duplicate tasks on public data (EKLUND, DIFFFA) — the
rest are tools (207), gated-data (149+10), already-covered/duplicate (24+10), or drop (4+4). The suite
goes **18 → 20**. This is the true, exhaustive per-paper ceiling on cached data; further growth is
data-access-bound (the 149 BLOCKED-DATA papers).
