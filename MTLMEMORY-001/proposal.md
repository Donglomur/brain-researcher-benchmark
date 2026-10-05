# MTLMEMORY-001: recorded-unit selection sensitivity

Retain the public human MTL data, but replace the hidden near-chance target with
a public, source-bound comparison of two conditional populations. This is an
easy method control; difficulty has not been calibrated on a model.

## Relationship to the papers

[Faraut et al. (2018)](https://doi.org/10.1038/sdata.2018.10) demonstrates
selected-cell proportions in Table 4 and confidence-related single-neuron ROC
measurements in Figure 1e–f. Its behavioral exclusions, correct-trial population
and bootstrap selection differ from this task.
[Chandravadia et al. (2020)](https://doi.org/10.1038/s41597-020-0415-9)
provides the expanded NWB release; its Figure 5f uses a one-second response and
bootstrap selection. Neither paper establishes the former task's hard-coded
rank-sum/held-out AUC as ground truth.

The present adaptation uses all released recognition trials, a fixed onset +
[0.2,1.7)-second interval, tie-corrected asymptotic rank-sum selection and a fully
disclosed repeated-half procedure. It does not claim to reproduce either paper's
numerical finding, behavioral-QC sample or memory-signal prevalence.

## Source and semantics

Freeze all 87 original assets in DANDI `000004/0.220126.1852`, with published
SHA-256, byte lengths, asset UUIDs and S3 object versions. The release declares
59 subject identifiers and CC-BY-4.0. Acquire at image-build time, authenticate
complete files, and run offline. Streaming a few selected fields is not full-byte
hash verification. No derived count/answer arrays belong in the runtime inputs.

Source inspection must precede counting. The exported label description is
reversed relative to author analysis code and complete full-path histories:
source 1 is labelled old, and source 0 new. Eight sessions lack within-session
learning evidence for 160 old-labelled recognition images. Retain these rows
and labels, disclose the unresolved exposure history, and never infer actual
exposure from other sessions' image catalogs. Original Windows path basenames
are insufficient identifiers. The source clock has an arbitrary nonzero origin;
trial/event and spike conversion share seconds without separate resets. Literal
spike-unit metadata is absent and must not be invented. Anatomy is a referenced
microwire row, not an undisclosed peak-channel calculation.

Keep `stim_off_time` distinct from trial `stop_time`. A 1.5-second response may
extend beyond the stimulus and include question-related activity. Missing
observation intervals leave continuity unverified; spike extrema are not bounds.
One session also has 97 learning rows with the stored trial end before onset.
Preserve and count these anomalies, without shifting TTL events or excluding
the session. All 8,700 recognition rows have valid temporal order. Exact stored
TTL6 linkage alone does not authenticate a biological trial-end assignment;
learning stop times do not enter recognition response windows.
Thirteen units in seven sessions have unordered timestamps; two units also have
2,046 duplicate occurrences. Define counts over the stored event multiset,
independent of ordering. Sorting a separate copy is lossless and allowed;
deduplication or source rewriting is not. Disclose ordering and multiplicity
diagnostics rather than asserting corrected physical-spike truth.
These are public interpretation limits, not targets to tune away.

## Measurement, not an absence test

The full-data-selected population is evaluated on its selection trials. The
repeated-split population is selected at least five times among 60 training
halves and summarized from train-directed test AUCs. Report both, with exact
support and overlap. Test AUCs can legitimately fall below 0.5.

Training-only selection avoids direct reuse within a split, but overlapping
resamples and the final eligibility condition do not supply independent outer
validation. Changing populations, sample sizes and direction estimates also
contribute to the difference. The comparison is not an unbiased causal estimate
of selection bias or evidence that memory coding disappears.

Remove every required near-chance number, selected-proportion range, forced
attenuation and prose-keyword escape. A selected fraction near the nominal test
level cannot identify the false-positive fraction. Units and repeated sessions
are clustered within patients; this descriptive task adds no cell-wise or
split-wise confidence interval masquerading as patient-population uncertainty.

## Public contract and verification

Disclose class semantics, original row/ID axes, count interval and boundary
arithmetic, rank-test tie/continuity convention, exact PCG64 traversal and draw
order, all 60 events, direction, eligibility, aggregation weights, empty cases,
output types and tolerances before inspecting count-derived outcomes.
The numerical recipe was frozen before response counts. A later explicit v3
amendment followed one-asset pilots and failed full-source attempts: it retains
and diagnoses the anomalous learning stop values rather than rejecting the
session. It changes no response window, selection, RNG, aggregation or tolerance.
The original checks had missed this temporal-order defect; preserve the failures
and rerun the amended contract instead of presenting it as the original freeze.

Require all source ledgers, integer response counts and complete memberships,
not merely selected rows. A fresh source-only bank and a separate independent
implementation must reconstruct the original data. Exact primitive binding
allows recomputed statistics to be cached without trusting submitted summaries.
Any cache is keyed to the exact source-bound counts/memberships, never a headline.

Accept the separate original-source implementation, either correctly identified
headline, harmless ordering/serialization and legitimate null/zero outcomes.
Reject coherent count scaling even when it leaves ranks unchanged, wrong labels
or times, missing sessions, altered splits, test-set direction folding, fabricated
eligibility and incorrect denominator/aggregation. Numerical checks, not prose,
must distinguish a valid analysis from those shortcuts.

## Evidence boundary

Record source authentication, structural inspection, public-contract freeze,
source-free fixtures, original numerical pilot, native/full independent results,
fresh bank, genuine accept/reject matrix and clean-commit Harbor separately.
Historical summary values do not validate this revision. No push, merge, model
calibration or public image release is implied by local engineering acceptance.
