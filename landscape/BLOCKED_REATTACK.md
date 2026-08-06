# BLOCKED topics — re-attack record (2026-08-05)

All 39 topics that the full-coverage Step-0 sweep marked **BLOCKED** were re-examined to decide
whether a hard task is actually reachable with public, single-command data, or whether the topic is
genuinely gated. The one feasible bucket (diffusion, via `dipy`) was *empirically tested*, not
assumed. Verdicts below.

## FEASIBLE — re-tested this pass

### Diffusion bucket → CONFIRM-BLOCKED (evidence-based, not "no data")
Topics: `diffusion MRI`, `tractography`, `white matter`, `fractional anisotropy`,
`structural connectivity` (5).

Installed `dipy 1.12.1`, fetched the cached **Stanford HARDI** single subject
(`read_stanford_hardi`), fit CSD, ran tractography.

- **Robustness trap (the intended winner) FAILS.** Streamline count is essentially invariant across
  the defensible tracking choices: deterministic vs probabilistic × angle 30/45/60 →
  **70,630–70,735 streamlines (1.0×)**. The "arbitrary tracking parameter → arbitrary connectome
  quantity" pattern that powers the other robustness tasks does **not** hold here.
- **Crossing fibers (Jeurissen 2013):** 72% of WM voxels fail the single-tensor model — real, but
  textbook enough that a careful agent volunteers the caveat → borderline difficulty.
- The **strong** diffusion traps — FA≠integrity *group* differences, tractography *false-positive
  rates* — need gated group cohorts (HCP/UKB) or a ground-truth phantom (Maier-Hein 2017), neither
  reachable by a single fetch. → **Blocked for a *hard* task, with evidence.**

### MEG → DROP as near-duplicate
A MEG source-leakage task (spurious zero-lag connectivity from field spread / source leakage) is the
**same failure axis as the already-built EEGVC-001** (volume conduction / imaginary coherence).
Near-duplicate → drop per the anti-monoculture rule, even though `mne` sample data is fetchable.

## GENUINELY GATED — no public single-command data

**Modality-gated** (no nilearn/dipy/mne fetch exists): `MRS`, `quantitative MRI`,
`susceptibility weighted imaging`, `arterial spin labeling`, `PET`, `high field MRI` (6).

**Cohort-gated** (registered/approved access only): `uk biobank`, `enigma`, `imaging genetics` (3).

**Clinical-cohort-gated** (no public single-command clinical imaging; the only public clinical sets
we already use are ABIDE-autism and ADHD-200): `major depression`, `bipolar disorder`,
`schizophrenia`, `parkinson disease`, `stroke`, `multiple sclerosis`, `epilepsy`,
`traumatic brain injury`, `brain tumor`, `transdiagnostic`, `treatment response`, `pain` (12).

**Structural / segmentation** (need FreeSurfer surfaces or co-registered multimodal data not in the
container): `thalamus`, `cortical thickness`, `surface area`, `segmentation`,
`individualized parcellation`, `multimodal imaging` (6).

**Task-cognitive** (need a specific paradigm dataset; the cached Brainomics Localizer is too limited
to anchor a primary finding): `executive function`, `working memory`, `emotion`, `reward`,
`episodic memory`, `sleep` (6).

## Tally
39 BLOCKED = 5 diffusion (tested → confirm-blocked) + 1 MEG (near-dup drop) + 6 modality-gated +
3 cohort-gated + 12 clinical-gated + 6 structural/segmentation + 6 task-cognitive. **No new tasks**
from the BLOCKED bucket — the one feasible bucket was tested and is robust; the rest are genuinely
gated. The value was verifying diffusion empirically rather than assuming it.
