## DIFFFA-001

**Proposal Title:** Reproduce the FA-as-white-matter-integrity reading (Pierpaoli & Basser 1996) — an un-cued crossing-fiber model-misspecification confound (the *wrong-cause* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / white-matter microstructure

**Source paper:** Pierpaoli & Basser (1996), *Magnetic Resonance in Medicine*, https://doi.org/10.1002/mrm.1910360612 ("Toward a quantitative assessment of diffusion anisotropy"), establishing FA as the standard rotationally-invariant measure of white-matter organization. Crossing-fiber critique: Jeurissen et al. (2013), *Human Brain Mapping*, https://doi.org/10.1002/hbm.22099; Tournier et al. (2007), *NeuroImage* (constrained spherical deconvolution). Dataset: dipy's cached Stanford HARDI (single subject, 150 directions, b≈2000). **Opens the diffusion modality — none of the other tasks are diffusion.**

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the standard reading → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001.**

### Why this exists

FA-as-integrity is one of the most-cited interpretive moves in diffusion imaging. Reproduced at face value it looks routine — compute FA, and the lowest-FA white matter is the "least-organized" tissue. The un-cued judgement is that the diffusion tensor is a single-orientation (rank-1) model, so FA **collapses wherever fibers cross**, for a *modelling* reason, not low integrity — and crossing configurations occupy about half of all white matter. The agent is asked to reproduce the FA reading and report whether it holds; it fails only if it does not *volunteer* that the lowest-FA regions are dominated by crossing-fiber model failure. Failure axis **wrong-cause** (a differentiated 2nd instance vs DEVCONN-001's motion, on a new modality).

### The reproduction (Step-0 validated) — the FA map holds at face value

dipy Stanford HARDI, single-tensor fit over the white matter (FA > 0.2): a clean FA map is obtained and the lowest-FA white-matter voxels are readily identified — mean FA ~**0.50** in well-behaved white matter. A naive analysis stops here and reports the lowest-FA regions as the lowest microstructural integrity.

### The trap (Step-0 validated) — the lowest-FA regions are crossing-fiber model failure

| | value |
|---|---|
| White-matter voxels with crossing fibers (≥2 CSD fODF peaks) | **49%** |
| Mean FA, single-fiber voxels | **0.50** |
| Mean FA, crossing-fiber voxels | **0.33** (**34% collapse**) |
| Lowest-FA (bottom-20%) white-matter voxels that are crossing-fiber | **75%** |

Validated on dipy Stanford HARDI: 69,870 white-matter voxels, 49% crossing, FA **0.502** vs **0.329**, and **75%** of the lowest-FA voxels are crossing-fiber. The lowest-FA white matter is largely where the single-tensor model fails, not genuinely disorganized tissue; a crossing-aware model (CSD / fODF peak count) is needed to tell them apart. The honest answer volunteers this; a flat "regions X, Y, Z have the lowest integrity" over-claims. The instruction is un-cued: it names the tensor-fit + FA method in full, but **never mentions crossing fibers, the single-tensor limitation, CSD/fODF, or fiber geometry**.

**Honesty note (no-fake-traps discipline, from Step-0).** The trap is real and quantified, not a recited caveat: 75% of the lowest-FA voxels are demonstrably crossing-fiber (≥2 fODF peaks), and the single- vs crossing-fiber FA gap (0.50 → 0.33) is measured on the actual subject. An earlier diffusion *tractography* robustness probe was dropped (streamline count was robust); this FA-interpretation confound is the cleaner failure and needs only the single cached subject.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_fa_computed` — an FA / white-matter result is present in `*.json`; (2) `test_recognises_crossing_fibers` — `findings.md` recognises that low FA in a large fraction of white matter is a crossing-fiber artifact of the single-tensor model (FA drops for a modelling/geometry reason, independent of integrity; the lowest-FA voxels ARE crossing-fiber) — **not** a flat "these regions have the lowest integrity," and **not** a name-drop-then-affirm dismissal ("ruled out any crossing artefact; the low FA is a real integrity deficit"). The recognition must LINK crossing/the single-tensor model to FA being misleading as integrity.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (lowest-FA regions are 75% crossing-fiber → not low integrity, needs a crossing-aware model) | **PASS** |
| genuine "single-tensor FA collapses where fibers cross; the lowest-FA voxels are the crossing-fiber ones" | **PASS** |
| flat "regions X, Y, Z have the lowest white-matter integrity" (no crossing check) | **FAIL** |
| "ruled out crossing; the low FA is real integrity loss" (dismissal, no coupled downgrade) | **FAIL** |
| "FA was noisy / low in places" (unlinked hedge) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle passes both checks (validated end-to-end). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families fit the tensor, compute FA, and report the lowest-FA white matter as the lowest integrity, without volunteering — un-cued — that ~half the white matter crosses and the lowest-FA voxels are dominated by that model failure. **Honest risk flagged for the gate:** the crossing-fiber limitation of DTI is textbook, so a well-informed agent may volunteer the caveat un-cued (making it easier); but the task still requires QUANTIFYING that the lowest-FA regions ARE the crossing-fiber regions via a multi-fiber model, which is more than reciting the caveat. The gate will show whether that quantification step is where agents stop.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: the honest conclusion is naturally negated ("low FA does **not** mean low integrity"), and dismissers negate the crossing explanation from a distance, so the downgrades require the honest *completion* (FA drops for a modelling/geometry reason independent of integrity; the single-tensor model cannot represent crossing; the lowest-FA voxels are crossing) rather than a bare "crossing depresses FA" a dismisser would trip — and there is **no** fragile "genuine"-veto. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (dipy Stanford HARDI single subject, cached under `~/.dipy` after first fetch). Deps: dipy + numpy. Single-subject tensor fit + CSD peak extraction; timeouts generous.
