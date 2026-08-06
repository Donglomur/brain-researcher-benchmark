# DIFFFA-001 — proposal

## Topic → paper
Topics: **diffusion MRI / fractional anisotropy / white matter** (landscape; the entire diffusion
bucket was previously marked BLOCKED for a *hard* task — this is the paper-level Step-0 that found the
feasible, non-tractography angle). Anchor: Pierpaoli & Basser 1996 (FA as the diffusion-anisotropy
measure); crossing-fiber limitation: Jeurissen et al. 2013; Tournier et al. 2007 (CSD). **Opens the
diffusion modality — none of the other 18 tasks are diffusion.**

## The un-cued trap (model-misspecification axis, NEW modality)
The task asks a routine diffusion analysis — compute FA, identify the lowest-integrity white matter —
without mentioning fiber geometry. The trap: the diffusion tensor is a single-orientation (rank-1)
model, so FA collapses wherever fibers cross, for a *modelling* reason, not low integrity.

| | value |
|---|---|
| White-matter voxels with crossing fibers (≥2 CSD peaks) | **49%** |
| Mean FA, single-fiber voxels | **0.50** |
| Mean FA, crossing-fiber voxels | **0.33** (34% collapse) |
| Lowest-FA (bottom-20%) WM voxels that are crossing-fiber | **75%** |

An agent that reports the lowest-FA voxels as the least-organized white matter is wrong: those regions
are dominated by crossing-fiber model failure. The honest, un-cued move is to VOLUNTEER that FA is
confounded by fiber geometry and that a crossing-aware model (CSD/fODF peak count) is needed.

Validated on dipy Stanford HARDI: 69,870 WM voxels, 49% crossing, FA 0.502 vs 0.329, 75% of lowest-FA
voxels crossing.

## Distinctness
New modality (diffusion) and new axis (single-tensor model misspecification). Not a duplicate of any
built task; the earlier diffusion *tractography* robustness probe was dropped (streamline count robust),
but this FA-interpretation trap is a different, cleaner failure that needs only the single cached subject.

## Grading
`test_fa_computed` — an FA / white-matter result is present in the JSON. `test_recognises_crossing_fibers`
— `findings.md` names the crossing-fiber / single-tensor-model limitation AND links it to FA being
misleading as integrity. Oracle passes; a naive "regions X,Y,Z have the lowest white-matter integrity"
report fails.

## Honest risk
The crossing-fiber limitation of DTI is textbook; a well-informed agent may volunteer it un-cued, which
would make this easier at the difficulty gate. Flagged for gate scrutiny — but the task still requires
QUANTIFYING that the lowest-FA regions ARE the crossing-fiber regions (via a multi-fiber model), which
is more than reciting the caveat.
