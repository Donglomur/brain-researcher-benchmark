# STEINMETZ-001 — registered-response prediction sensitivity

## Role and paper connection

This is an **easy computational method control** using an actual original-study
session. It is not currently calibrated as hard or claimed to defeat any model.
Its named paper connection is Steinmetz et al. (2019), *Distributed coding of
choice, action and engagement across the mouse brain*, Figure 4c and Methods
([DOI](https://doi.org/10.1038/s41586-019-1787-x)).

The paper's regional movement-relative decoding distinguishes choice-related
activity from other task components. This benchmark instead compares raw
all-cluster predictions of the registered response in one session. It retains
the authentic data and the choice-decoding methodological question without
claiming to reproduce the paper's regional finding or its full cohort.

The previous proposal's hidden-lever narrative, prescribed approximately
0.72-versus-0.95 contrast, strictly pre-movement claim, causal leakage attribution,
and fold-variability gate are withdrawn. Neither outcome is an acceptance rule.

## Data and provenance

Use only the published DANDI `000017/0.240329.1926` NWB session
`sub-Cori/sub-Cori_ses-20161214T120000.nwb`. The source is CC-BY-4.0,
311,814,662 bytes, with authoritative published SHA256 verified before analysis.
See `environment/source_manifest.json` for the asset ID, immutable content URL,
release DOI, attribution, hash and conversion caveats. Image building stages
the exact bytes; both solver and verifier run without network access.

Original-byte inspection established 214 trial rows, 201 marked included, and
134 included binary-response trials with finite alignment times. The selected
labels are 69 right (`-1`) and 65 left (`+1`). There are 1,085 unique, noncontiguous
unit IDs: 351 MUA, 5 Good, and 729 Unsorted. All stored clusters are deliberately
used; this is not the paper's quality-filtered neuron set. Duplicate spike times
within seven units are retained, not silently deduplicated.

Registered response is not initial movement onset. The NWB and
[author dictionary](https://github.com/nsteinme/steinmetz-et-al-2019/wiki/data-files)
make this distinction explicit and give the correct sign mapping. The included
flag omits response-timing criteria used in the paper. Unused wheel fields have
conversion/shape caveats; this task does not infer movement onset from them.

## Public estimators and evidence

The instruction and public `/app/method_contract.json` disclose selection,
half-open feature windows, all-unit ordering, train-only standardization,
logistic-regression parameters, fixed fold generation, class labels, baseline
ties, numerical tolerances and aggregation. The factors are bundled recipes:
250 ms stimulus counts versus 200 ms peri-response counts; contiguous unstratified
KFold versus randomly shuffled stratified folds. Membership is reused across
windows, and all four cells are reported. No direction is prescribed.

The headline is the unweighted mean of five stimulus/blocked fold accuracies;
pooled trial accuracy is reported separately. Training-fold-majority performance
is a real held-out baseline, unlike the merely descriptive full-sample majority
fraction. Response timing is counted in disjoint half-open categories and never
equated with first movement.

The reference builder rereads exact source trial IDs, labels, unit IDs, spike
counts and timing. It validates retained train-fold transforms and fitted state,
then checks the public outputs before replacing the old scalar reference. The
verifier binds all four recipes to full source-keyed out-of-fold predictions and
recomputes 20 folds and every reported aggregate. Wrong identities, signs,
splits, metadata and coherent fabricated predictions are rejected. Row order,
extra columns and free prose are not scientific failure criteria.

Independent authoring checks use separately constructed source counts and
training-fold transforms, with shared library components explicitly identified.
A deliberately globally standardized classifier may be run as a separate real
negative control, never as evidence that every recipe difference is leakage.
Retained source/fit arrays are authoring evidence, not an extra required agent
output format.

## Limits and validation boundary

One session is not a population sample of independent animals. Training on both
sides of contiguous held-out blocks is not prospective prediction and provides
no temporal buffer. Fold score dispersion is descriptive, not a population
confidence interval. Raw decoding may reflect sensory, motor and other
correlates; it does not isolate causal or necessarily pre-movement choice coding.

Tests establish implementation and verifier behavior. Even a reward-1 offline
oracle does not establish the paper finding or agent difficulty. Current
execution evidence belongs in `REPAIR_STATUS.md` and the external clean-commit
receipt; claims are not inherited from older fixtures or a previous PR head.
No frontier-model calibration, push, PR comment or merge is part of this repair.
