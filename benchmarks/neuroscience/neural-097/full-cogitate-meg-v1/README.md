# NEURAL-097: COGITATE MEG prediction and scientific interpretation

This is complete, scientifically unqualified benchmark **source** for one task. It specifies single-trial face-versus-object prediction from fixed MEG sensor summaries, paired access and interaction conditions, independent reference methods, and a separate scientific interpretation assessment. It contains no evaluation data, participant roster, targets, trained models, numerical results, or paper bodies.

Scientific execution is disabled in both the controller and native launcher. All **22 qualification gates remain open**. Source review and engineering checks are not scientific validation, reference competence, SOTA performance, or submission acceptance by another benchmark.

The task preserves 33 selected participants, 66 person/image-half folds, five feature arms, four access/mode settings and three seeds: 3,960 candidate fold/arm jobs. It also requires 1,650 fixed-reference jobs, 12 interpretation reports, complete failure and resource records, and 31 future control groups. These are parts of **one benchmark**, not separate benchmark counts. Actual query counts and source storage requirements remain unqualified.

## Scientific question and conditions

The task asks how a prespecified bounded procedure predicts image category on this fixed panel. The five input arms are `SIGNAL`, `PRE`, `NUISANCE`, `SIGNAL_NUISANCE`, and `PRE_NUISANCE`. SIGNAL and PRE each contain 60 summaries from six sensors and ten bins; NUISANCE contains eight declared experimental-design indicators. Every arm uses the same retained trial universe.

| Axis | Conditions |
|---|---|
| Knowledge | A: paper/specification and permitted data; B: the same material plus audited ordinary author code |
| Interaction | F: candidate source frozen before evaluation views; I: training investigation followed by isolated single-query analysis using frozen training-derived state |
| Candidate seeds | 97097, 97098, 97099, all mandatory |
| References | R0–R4, one qualified fixed panel per recipe; no invented access/mode or seed replicates |

The primary setting is **B/F/SIGNAL balanced accuracy on task-irrelevant trials**. The reporting order then gives the fixed R2 comparison, two secondary feature comparisons, and every mandatory setting, arm, metric, relevance, seed, support count and failure. Equal-person, equal-duration/orientation-cell weighting is fixed. Missing required support produces null metrics; it does not remove a participant or change a denominator. See [the reporting contract](contracts/ESTIMAND_REPORTING_CONTRACT.json).

This prospective sensor-level task is different from the paper's source-space, label-aware pseudotrial analyses. Its scores do not reproduce those analyses or adjudicate consciousness theories. Neither sign of a paired accuracy difference estimates conditional mutual information, proves conditional independence, identifies a neural source, removes confounding, or establishes population generalization. See [scientific limits](SCIENTIFIC_LIMITS.md).

## Source layout

`entry.py` defines the complete and named-condition controller routes. `n097/` contains source preparation, cohort/run census, splits and views, genuine participant execution, original-process custody, target-last collection and grading, fixed references, complete reports and the separate rubric. `native_launcher.py` and `native/` contain disabled physical-isolation source. `contracts/` preserves the full scientific/API design, 15 objects, nine operations, 20 stages and all open gates. [TASK.md](public/TASK.md) and [SUBMISSION.md](public/SUBMISSION.md) describe candidate-facing interfaces.

The files under `contracts/` are retained design records. Their past-tense reading claims, phase budgets and phrases such as “unimplemented” describe that historical design phase. They are not current execution authority or a claim that this public preparation reread a paper. The executable source and this release status describe the current source package; the scientific qualification status remains open in both.

For a source-only plan, the entry point provides `--source-plan-only --output PATH`. This builds fixed job metadata without reading the protected roster or data. It has not been executed in this public-content preparation. Ordinary execution routes fail while `DEPLOYMENT_ENABLED` and `NATIVE_DEPLOYMENT` are false. Editing those constants alone does not qualify a run.

## Inputs and qualification still required

A future authorized operator must separately obtain lawful paper and data access, authenticate the complete source/part inventory, reconcile all 33 selected people and 330 declared person/run dispositions, establish event/epoch clocks and eligibility, qualify numerical and isolation environments, fit competent references, audit exposure, and validate the interpretation rubric. There are no signed download links, credentials, data stubs, or fabricated observations in this package.

The selected roster is an **unpublished protected dependency**, not a freely chosen list of 33 participants. [Protected inputs](PROTECTED_INPUTS.md) describes its exact binding. Publishing source does not make the public archive unseen to a model, and NEURAL-098 shares the source family; a new run identifier cannot repair exposure.

This candidate makes two explicit publication amendments: private provenance locators become opaque unbundled-source identifiers with coherent portable contract pins; the embedded roster becomes a fail-closed protected source dependency. All 41 accepted runtime roles remain present. [Source provenance](SOURCE_PROVENANCE.json) distinguishes each exact copy from each proposed amendment. An independent content and amendment review is required before publication. No private build history is part of the public allowlist.

The retained `PINS.json` schema calls its selected descriptor `original`; in this public candidate that field pins the current portable body. It is not a claim that an amended body equals its earlier private version. Each PINS row also retains `source_identity` for the immutable pre-projection source bytes, while `original` is the exact current portable body. Earlier body identities and exact-copy flags are recorded separately in `SOURCE_PROVENANCE.json`. The loader authenticates the complete fixed PINS index before any contract body.

The included project software is under [MIT](LICENSE). Paper, data, author code, Python packages, container images and future candidate submissions are separate dependencies with their own terms; see [third-party scope](THIRD_PARTY.md).

The canonical central package is the parent directory. Its source-only run/score/operator adapters authenticate this complete 41-role runtime before entering the existing disabled programme. Public source metadata carries no private build history.
