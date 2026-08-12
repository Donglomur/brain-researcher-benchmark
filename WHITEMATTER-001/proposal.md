## WHITEMATTER-001

**Proposal Title:** Reproduce the FA-as-white-matter-integrity reading (Pierpaoli & Basser 1996) — an un-cued crossing-fiber model-misspecification confound, with atlas-based anatomical localization (the *wrong-cause* failure axis; answer + numbers in private calibration.md)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / white-matter microstructure

**Source paper:** Pierpaoli & Basser (1996), *Magnetic Resonance in Medicine*, https://doi.org/10.1002/mrm.1910360612 ("Toward a quantitative assessment of diffusion anisotropy"), establishing FA as the standard rotationally-invariant measure of white-matter organization. Crossing-fiber critique: Jeurissen et al. (2013), *Human Brain Mapping*, https://doi.org/10.1002/hbm.22099; Tournier et al. (2007), *NeuroImage* (constrained spherical deconvolution). Dataset: dipy's cached Stanford HARDI (single subject, 150 directions, b≈2000) + its co-registered FreeSurfer parcellation. **Opens the diffusion modality — none of the other tasks are diffusion.**

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the standard reading → reveal the hidden confound), modelled on GMATROPHY-001 / TOPEDGES-001. Rebuilt to the maintainer VALIDITY standard (repair #27: atlas-based anatomical localization).**

### Why this exists

FA-as-integrity is one of the most-cited interpretive moves in diffusion imaging. Reproduced at face value it looks routine — compute FA, and the lowest-FA white matter is the "least-organized" tissue. The un-cued judgement is that the diffusion tensor is a single-orientation (rank-1) model, so FA **collapses wherever fibers cross**, for a *modelling* reason, not low integrity — and crossing configurations occupy about half of all white matter. The agent is asked to reproduce the FA reading, localize the lowest-FA white matter to named anatomical regions, and report whether the reading holds; it fails only if it does not *volunteer* that the lowest-FA regions are dominated by crossing-fiber model failure. Failure axis **wrong-cause** (a differentiated 2nd instance vs DEVCONN-001's motion, on a new modality).

### The reproduction and the trap (Step-0 validated) — held privately

The face-value FA map holds: a clean single-tensor FA map is obtained and the lowest-FA white-matter regions are readily named. The trap is that those lowest-FA regions are dominated by **crossing-fiber model failure** (a crossing-aware CSD/fODF peak count separates single- from crossing-fiber voxels), not by genuinely low integrity. **The specific lowest-FA region names, the crossing fractions, the single- vs crossing-fiber FA gap, the region-level FA-vs-crossing anti-correlation, and all validated numbers are in the private, git-ignored `calibration.md`** (rule 4: public repo + agents have internet). The instruction is un-cued: it names the tensor-fit + FA + atlas-localization method in full, but **never mentions crossing fibers, the single-tensor limitation, CSD/fODF, or fiber geometry**.

**The repair (#27) — atlas-based anatomical localization.** The oracle no longer emits only a global number: it OUTPUTS the named white-matter regions where single-tensor FA collapses in crossing-fiber areas. Each white-matter voxel is labelled by the nearest FreeSurfer cortical-gyral parcel (wmparc-style) from the subject's co-registered `aparc` parcellation (the corpus callosum kept explicit), and `regional_fa.csv` carries per-region FA, crossing fraction, and single- vs crossing-fiber FA. The verifier checks the region names are **real** and that the FA drop is in the **right direction** (crossing < single).

**Honesty note (no-fake-traps discipline).** The trap is real and quantified, not a recited caveat: the lowest-FA named regions are demonstrably the highest-crossing ones (a strong negative region-level FA-vs-crossing correlation), crossing-fiber FA is below single-fiber FA in **every** territory, and the corpus callosum — the textbook coherent single-fiber tract — has the highest FA and almost no crossing (the confirming contrast). Numbers in `calibration.md`.

### Route (route-a, internet on)

Packaging is impractical — the Stanford HARDI DWI is **91 MB** (above the ~50 MB packaging threshold and ~6.5× the committed TOPEDGES bundle) and cannot be shrunk without degrading the acquisition or changing the format the "fit a tensor with dipy" task expects. So the DWI + its tiny co-registered atlas are fetched at runtime via `read_stanford_hardi()` + `read_stanford_labels()` (cached under `~/.dipy`). `allow_internet=true`.

### Verifier (2 plain checks — validate the ACTUAL data)

`tests/test_outputs.py`: (1) `test_localization_computed` — validates the real emitted data: the named white-matter regions are **real** (FreeSurfer gyral / canonical WM-tract / lobar-WM labels, not placeholders), FA values are plausible fractional anisotropies, the white-matter voxel count is sane, and — where single- vs crossing-fiber FA is reported — the FA drop is in the **right direction** (crossing < single). Empty / fabricated fails. (2) `test_recognises_crossing_fibers` — passes if EITHER the emitted per-region localization genuinely demonstrates the confound in the DATA (real regions, crossing-fiber FA below single-fiber FA, lowest-FA regions = highest-crossing — recognition-in-data), OR `findings.md` recognises that low FA in a large fraction of white matter is a **crossing-fiber artifact of the single-tensor model**, not low integrity (crossing-aware CSD/fODF needed). A flat "regions X, Y, Z have the lowest integrity" over-claims; a name-drop-then-dismiss ("ruled out any crossing artefact; the low FA is a real integrity deficit") and an unlinked hedge ("FA was low / noisy") both fail. The recognition must LINK crossing / the single-tensor model to FA being misleading as integrity.

**Discrimination (validated locally, this rebuild — full table in `calibration.md`):**

| submission | localization (data) | recognition | overall |
|---|---|---|---|
| **oracle** (named lowest-FA regions = crossing regions, right direction) | PASS | PASS | **PASS** |
| genuine crossing text ("single-tensor FA collapses where fibers cross; lowest-FA regions are the crossing ones") | PASS | PASS | **PASS** |
| naive ("regions X, Y, Z have the lowest integrity", real regions, no crossing check) | PASS | **FAIL** | **FAIL** |
| fabricated (fake region names) | **FAIL** | FAIL | **FAIL** |
| fabricated (real names, crossing FA > single FA) | **FAIL** | FAIL | **FAIL** |
| dismissal ("ruled out crossing; the low FA is real integrity loss") | PASS | **FAIL** | **FAIL** |
| unlinked hedge ("FA was noisy / low in places") | PASS | **FAIL** | **FAIL** |
| empty | **FAIL** | FAIL | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle passes both checks (validated end-to-end, deterministic). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families fit the tensor, compute FA, name the lowest-FA white-matter regions, and report them as the lowest integrity, without volunteering — un-cued — that ~half the white matter crosses and the lowest-FA regions are dominated by that model failure. **Honest risk flagged for the gate:** the crossing-fiber limitation of DTI is textbook, so a well-informed agent may volunteer the caveat un-cued (making it easier); but the task now requires QUANTIFYING and LOCALIZING that the lowest-FA *named regions* ARE the crossing-fiber regions via a multi-fiber model, which is more than reciting the caveat. The gate will show whether that localization step is where agents stop.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: the honest conclusion is naturally negated ("low FA does **not** mean low integrity"), and dismissers negate the crossing explanation from a distance, so the downgrades require the honest *completion* (FA drops for a modelling/geometry reason independent of integrity; the single-tensor model cannot represent crossing; the lowest-FA voxels are crossing) rather than a bare "crossing depresses FA" a dismisser would trip — and there is **no** fragile "genuine"-veto. The DATA-based pass (recognition-in-data) requires a genuine localization signature (real regions + right within-region direction + between-region anti-correlation), which a naive no-crossing submission cannot satisfy and a fabricated one fails. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (dipy Stanford HARDI single subject + co-registered atlas, cached under `~/.dipy` after first fetch). Deps: dipy + numpy + scipy. Single-subject tensor fit + CSD peak extraction + wmparc-style atlas localization (~30 s cached); timeouts generous.
