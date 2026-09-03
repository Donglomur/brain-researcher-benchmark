## PRECISFC-001

**Proposal Title:** Test-retest reliability of the individual functional connectome (MSC) — an un-cued data-quality gap (frame-censoring + documented subject exclusions)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Precision resting-state functional connectivity

**Source finding:** Gordon et al. (2017), *Neuron*, https://doi.org/10.1016/j.neuron.2017.07.011 ("Precision Functional Mapping of Individual Human Brains"); Laumann et al. (2015); motion-censoring: Power et al. (2012). Data: OpenNeuro `ds000224` (Midnight Scan Club) **volume-pipeline** resting-state derivatives, fetched at runtime from the public no-credentials S3 bucket.

**Status: FULL runnable task, real fetched data.** A new dataset (MSC) and a new failure axis for the suite — **un-cued data-quality controls** — distinct from the motion *wrong-cause* confound in DEVCONN-001 / CLINCONN-001.

### Why this exists

Asked to "quantify the test-retest reliability of the individual connectome", an agent will load the processed BOLD runs, correlate the per-session connectomes, and report a single reliability figure — without volunteering the two controls that MSC precision mapping depends on and that the task never spells out: (1) **censoring high-motion frames** using the supplied temporal mask (`*_tmask.txt` / FD scrubbing), and (2) **excluding the documented low-quality subjects** MSC08 (pervasive drowsiness → unstable networks) and MSC09 (excessive motion). Ignoring either deflates and contaminates the estimate.

### The trap (Step-0 validated, real)

On `ds000224` volume_pipeline (Power-264 5 mm spheres; sub-MSC01/02/05/06/08/09, ses-func01/02/03; reliability = mean pairwise correlation of per-session connectome edge-vectors):

| subject | frame retention | reliability (all frames) | reliability (censored) |
|---|---|---|---|
| MSC01 | 80% | 0.63 | 0.66 |
| MSC02 | 86% | 0.54 | 0.54 |
| MSC05 | 84% | 0.68 | 0.69 |
| MSC06 | 93% | 0.75 | 0.75 |
| **MSC08** (drowsy) | **24%** | **0.09** | 0.30 |
| **MSC09** (high motion) | 60% | 0.51 | 0.53 |

| group mean reliability | value |
|---|---|
| **naive** (all frames, all 6 subjects) | **0.53** |
| censored only (all subjects) | 0.58 |
| exclude MSC08/09 only (all frames) | 0.65 |
| **correct** (censored **and** exclude MSC08/09) | **0.66** |

Both controls matter: frame-censoring lifts the high-motion subject MSC08 from 0.09 → 0.30, and MSC08/MSC09 are clear outliers that drag the group mean down. The honest estimate (0.66) is materially higher than the naive one (0.53); the individual connectome is highly reliable **only once the data-quality controls are applied**.

**Honesty notes (no-fake-traps discipline, from Step-0):** the MSC derivatives are already GSR'd/nuisance-regressed, so frame-censoring changes a single clean session's connectome only slightly; the censoring effect is real and large exactly where it should be — the **high-motion subject** (MSC08 0.09 → 0.30) — and shows up on the **reliability** metric rather than on a single-session edge weight. The exclusion is anchored on documented data quality (Gordon 2017; Laumann 2015), and is corroborated by frame retention (MSC08 24%, MSC09 60% vs 80–93% for the usable subjects) in the data itself.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) per-subject reliability computed for the subjects (values in [−1, 1]), with the low-quality subjects MSC08/MSC09 present so the exclusion is a real decision; (2) `findings.md` recognises **both** data-quality controls — censoring high-motion frames (temporal mask / FD scrubbing) **and** excluding the documented low-quality subjects (MSC08 drowsy / MSC09 high-motion). Offline discrimination (locked): reference + "scrub frames & drop drowsy/high-motion subjects" wordings PASS; flat "reliable, r = 0.53" FAIL; censoring-only FAIL; exclusion-only FAIL; per-subject-values-without-recognition FAIL. Whitespace normalised before matching.

### Difficulty

`hard`. cpus 2, mem 8 GB, internet on, storage 24 GB. Fetches, at runtime, 18 processed MSC resting runs (~200 MB each, ~3.6 GB total) + their temporal masks; one Power-264 sphere extraction per run; agent timeout 10800 s, verifier 7200 s. Deps: nilearn 0.12.1 + scipy/sklearn/pandas/nibabel. **Step-5 frontier calibration PENDING.**

### Cost

Data volume ~3.6 GB (the MSC volume BOLD is large). The graded quantity (reliability of the individual connectome, a correlation) is convention-invariant, and the un-cued judgement is whether to apply the supplied frame-censoring and drop the documented low-quality subjects.
