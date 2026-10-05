# CLINCONN-001: a CNP motion-sensitivity method control

Retain the original public resting-state data and ask a narrower, answer-neutral
question: how does the signed diagnosis association change between a crude
comparison, mean-FD adjustment, and a prespecified low-FD population?
This is an easy secondary-analysis control, not a calibrated hard task or an
original paper finding.

## Paper and source relationship

[Poldrack et al. 2016](https://doi.org/10.1038/sdata.2016.110) provides the CNP
cohort, not this schizophrenia connectivity result. The public preprocessing
descriptor, [Gorgolewski et al. 2017](https://f1000research.com/articles/6-1262/v2),
documents the surface pipeline in Figure 1 and missing-T1 participants in
Table 1. [Power et al. 2012](https://doi.org/10.1016/j.neuroimage.2011.10.018)
provides the distance-related motion-sensitivity rationale; its cohort, regions
and frame-removal analysis differ from this task.

The legacy `ds000030_R1.0.5` source yields 177 phenotype candidates but only
172 complete released left/right/confound sets. Five controls are explicitly
unavailable before any signal analysis, consistent with the preprocessing
paper's missing-T1 list. Their identities stay in a candidate ledger; subsequent
transfer or processing errors cannot silently shrink the selected cohort.

Original S3 object versions, byte lengths and ETags are captured before data
transfer. Measured SHA-256 pins additionally make later builds fail closed on
changed bytes; they are not misrepresented as independently published hashes.
Fixed Destrieux annotations and fsaverage5 geometry are bound separately.
Build-time acquisition produces an offline runtime, not a mutable network task.

Legacy dataset metadata says PDDL, not the later raw snapshot's CC0. File-specific
atlas/mesh licensing remains unestablished; no public data/image release follows
from local validation. Preprocessing source/geometry lineage and any remaining
limits must accompany the measurements.

## Changes from the old endpoint

The estimator is public: source cohort, anatomical label exclusions, float64
parcellation, temporal cleaning, nuisance rank, FD denominator, common-edge
family, Fisher clipping, distance ties and signed OLS uncertainty. Mean FD
excludes its undefined first difference rather than claiming a measured zero.
The `FD < 0.2` analysis is a restriction, not a motion-matched sample.

The old oracle's numerical answers and assertions of higher FC, attenuation,
“approximately chance” edge counts and exclusive motion causation are withdrawn.
No direction, significance threshold crossing, prose phrase or near-null result
is a success condition. An adjusted association is not an intervention on motion;
age, sex, medication and selection remain limitations. Dependent edges do not
increase the number of independent participants.

The two edgewise model families are fully reported, including undefined
statistics. Their `|t| > 2` summaries and QC-FC map correlations are descriptive,
not multiplicity-corrected discoveries. The task adds no classifier, causal
decomposition or unsupported original-paper finding.

## Verification and evidence boundary

Require all candidate identities, original parcel/edge catalogues, per-subject
measurements and FD/cleaning diagnostics, the complete numeric subject-edge
array, and signed model outputs. Recompute summaries and uncertainty from the
submitted source-bound measurements. Do not accept subject-level correlation
with a reference, a permissive coverage fraction, or a narrative alone.

A fresh source-only grading bank and a separate independent computation must
both read the authenticated originals. Genuine positive controls include that
alternative implementation and harmless order/serialization changes; negatives
include coherent fabricated summaries, changed phenotype/FD/edge identities,
incorrect denoising, omitted subjects, invalid distance bins and wrong signs.

Source-free fixtures check implementation mechanics only. Native execution,
independent checks and clean-commit Harbor acceptance are separate evidence
steps recorded in `REPAIR_STATUS.md` and external receipts. Historical results
are not evidence for the repaired revision. Oracle success does not establish
Sol difficulty; no such model run is authorized here.
