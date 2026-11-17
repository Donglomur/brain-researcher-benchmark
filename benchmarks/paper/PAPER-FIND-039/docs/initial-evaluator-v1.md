# Initial Figure 2 metric implementation

This additive component implements spatial-stability and context-specificity
kernels for PAPER-FIND-039. The input boundary is an operator-admitted table of
trial-by-position spike counts, occupancy and frozen cell classifications. The
implementation produces cell and session metrics, all declared classification
sensitivities, and a prospective mouse-level age contrast with seeded uncertainty.
It does not claim authentic empirical reproduction or complete the canonical task.
The original `task.json` and its historical admission state are unchanged.

The task pin is SHA-256
`811245002efb23f378626e214f2d1579a38067db660e2f1b159b40a807b05911`
(83,955 bytes). The paper is Herber et al., *Nature Communications* 16, 8770
(2025), [version of record](https://doi.org/10.1038/s41467-025-63229-0),
[PMC12494969](https://pmc.ncbi.nlm.nih.gov/articles/PMC12494969/).
The 2024 preprint is not substituted for that paper.

## Scientific boundary and source mapping

The implementation was written independently from the mathematical operations
observed in [Herber2024 revision
1a9dd3040c9f77662caf26a34c9452403579087a](https://github.com/GiocomoLab/Herber2024/tree/1a9dd3040c9f77662caf26a34c9452403579087a).
No upstream code, notebook, images, data or published numeric outputs are bundled.
Source paths/revision are immutable provenance pins; no unmeasured content hash
is asserted for remotely rendered source. Public code access is not a conclusion
about downstream redistribution rights.

| Requirement | Primary source | Implemented behavior |
|---|---|---|
| Occupancy-corrected trial maps | `pipeline/process_spikes.py`, `tuning_curve_bytrial` | Counts/dwell, previous-bin carry, wrapped Gaussian, global per-cell min-max |
| Unshifted trial similarity | `pipeline/process_spikes.py`, `cross_trial_correlation` | Row centering, L2 plus 1e-6, dot product; input not mutated |
| Fig. 2 stability | `Figure 2 & Supplementary Fig. 3.ipynb`, local cross-trial stability cell | Ten neighbors at offsets ±1…5, interior trials only, separate block/alternation |
| Fig. 2 specificity | Same notebook, context match/mismatch cell | Whole-matrix normalization; block, within-alternation, and block-to-alternation ratios |
| Population integrity | Canonical evaluation comparability/holds | Independent complete roster, all declared masks, no silent mouse/session/cell/trial/bin omission |
| Mouse uncertainty | Canonical proposed improvement | Explicitly prospective equal-session/equal-mouse estimator; mouse bootstrap |

The [source helper](https://raw.githubusercontent.com/GiocomoLab/Herber2024/1a9dd3040c9f77662caf26a34c9452403579087a/pipeline/process_spikes.py)
and [Figure 2 notebook](https://raw.githubusercontent.com/GiocomoLab/Herber2024/1a9dd3040c9f77662caf26a34c9452403579087a/Figure%202%20%26%20Supplementary%20Fig.%203.ipynb)
are the precise kernel references. The implementation retains their epsilon and
unit-diagonal subtraction. Those details should not be silently replaced with
ordinary Pearson correlation or trace subtraction. Source session means ignore
undefined cells; counts expose every omission. The reviewer-derived analytic
controls explicitly distinguish these alternatives.

**Unresolved source discrepancy:** the paper describes 5 cm smoothing, while the
pinned Figure 2 notebook calls the helper with `sigma=5`, `b=2`; SciPy interprets
sigma in bins, giving 10 cm. This component follows that exact notebook call. It
does not resolve the scientific discrepancy or register a grading tolerance.

## Inputs and operation

Run from the implementation directory with an existing NumPy/SciPy environment:

```sh
python evaluator.py input.json roster.json output.json --seed 0 --bootstrap-replicates 1000
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider tests
```

Both JSON documents carry `task_id: "PAPER-FIND-039"` and `source_revision` equal
to the pinned commit. `input.json` additionally carries `bin_width_cm: 2` and a
`sessions` list. Each session contains `mouse_id`, `session_id`, ordered
`cell_ids`, ordered `trial_ids`, `position_bin_ids`, integer `spike_counts`
(trials × position bins × cells), and `occupancy_seconds` (trials × position
bins). Dwell and counts must be finite and nonnegative; occupied spikes with
zero dwell are rejected. Input bytes are never loaded through pickle.

The separately managed `roster.json` contains `classification_policies` (every
predeclared mask name) and `mice`, keyed by mouse identity. A mouse contains
`age_group` (`young`, `middle_aged`, `aged`) and a `sessions` object keyed by
session identity. Each expected session freezes `cell_ids`, `trial_ids`,
`position_bin_ids`, `segments` and `masks`. Each mask is one boolean per complete
cell roster; its key must appear in `classification_policies`. A supplied packet
cannot introduce a different subset or a new sensitivity policy.

`position_bin_ids` are the increasing positive integer bin indices from the
source digitization, including precisely the bins observed anywhere in that
session. They are not assumed to cover every physical track bin. The source
compresses globally unobserved bins; this component rejects all-zero occupancy
columns, preserving that boundary. A per-trial missing bin carries its preceding
rate; a missing first bin initializes to zero. Completely constant normalized
cells produce undefined endpoints, with counts, rather than an invented score.

Each trial's segment is one of `block_A`, `block_B`, `alternation_A`,
`alternation_A_gain`, `alternation_B`, `alternation_B_gain`. Within each segment,
the roster order is temporal. The evaluator concatenates segments in that order.
The trusted adapter must map corrected trial identities, dark/trial-220 removal,
gain status and context from the native source. The packet must cover every
admitted trial. This implementation cannot verify native trial correction from
aggregate counts and does not drop trials automatically.

Gain trials remain in full-matrix normalization and local alternation stability;
the three context ratios select the nongain submatrices. Local ±5 windows can
cross the concatenated A/B boundary, matching the source. A phase with ≤10 trials
has no interior and yields `null`. Context ratios return `null` for undefined
normalization, absent required contexts or zero mismatch denominator.

`tests/test_evaluator.py::make_packet` is a complete input example generated only
for engineering validation. Its masks and cells have no empirical meaning. The
output contains canonical JSON-content hashes of both supplied documents, the
seed and bootstrap count, complete per-cell metrics, and every mask's cell,
session, mouse and age counts. The hashes bind the submitted content but do not
authenticate a roster or transform untrusted data into a protected reference.

## Estimand and uncertainty

The prospective estimator gives selected cells equal weight within each session,
sessions equal weight within each mouse, and mice equal weight within each age
group. It reports `middle_aged_minus_young` and `aged_minus_young` for every
metric. Every session endpoint required by a mouse must be defined before its
mouse mean is reported. Every expected mouse endpoint must be defined before an
age mean or contrast is reported. Undefined values retain coverage counts.

The optional percentile bootstrap resamples whole mouse summaries independently
within age groups, then computes differences of resampled age means. It requires
at least two defined mice per group for an interval. It is deterministic for the
recorded seed and sorted mouse identities. This descriptive bootstrap is a
prospective recipe, not the paper's mixed-effects model, an adjustment for speed
or recording quality, a protected generalization estimate, or a competence score.
All declared classification masks are reported without choosing a favorable one.

## Remaining gates

The author import and shuffle recipes, native classification masks, authoritative
mouse/session roster, and classification threshold sensitivity have not run.
Fig. 2 chooses cohorts C and D through metadata-indexed session lists; displayed
historical sample counts do not establish our current full-population admission.
The source NGS classifier has stale-variable/typo ambiguities; this package
therefore consumes explicitly frozen masks and does not claim to repair it.
The published mixed-effects analysis, behavior associations, network-remapping
results, and the other figures remain outside this component.

Before benchmark admission, retain the task's requirements for locomotion and
recording-quality adjustment, age-balanced whole-mouse partition before cell
selection, complete native replay, a competent reference, numerical tolerances,
equal candidate access, independent scientific review, and isolated protected
grading. Paper/data/component rights and historical exposure need their original
qualification. Dryad metadata's 23,064,708,896-byte archive size is not a measured
working set. No archive, empirical data, model, native scientific campaign, or
dependency installation was used to validate this package.
