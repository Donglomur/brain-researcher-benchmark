# Old/new discrimination and selection sensitivity in human MTL recordings

Using the fixed public human single-neuron release, compare two explicitly
different summaries: discrimination among units selected on all recognition
trials, and discrimination conditional on repeated training-split selection.
Report the measured values even if they are equal, reversed, near chance or
large. No particular AUC, selected fraction or narrative is a success condition.

This is a **paper-derived method/sensitivity control**, not either paper's exact
finding. [Faraut et al. (2018), Figure 1e–f and Table 4](https://doi.org/10.1038/sdata.2018.10)
used behavioral exclusions, correctly recognized trials and bootstrap selection.
[Chandravadia et al. (2020), Figure 5f](https://doi.org/10.1038/s41597-020-0415-9)
used a one-second response and bootstrap selection in the expanded release.
Here the declared adaptation retains all recognition trials, a 1.5-second
window and the public rank-sum/repeated-half method below.

## Original offline inputs

Use `/app/data/mtlmemory`, containing the exact 87 original NWB assets of DANDI
`000004/0.220126.1852` and their source manifest. Published SHA-256 digests,
sizes and version-pinned object identities authenticate these files. The release
declares 59 subject identifiers and CC-BY-4.0; retain attribution to the dataset
and papers. No runtime download, synthetic substitute or silent session omission
is permitted. Calendar dates are anonymized; asset/session and subject identities
are separate, and a filename date is not a session deduplication key.

The public `/app/method_contract.json` gives the exact schemas, source rules,
numerical recipe, undefined cases and tolerances. Preserve original trial/unit
IDs separately from their source row positions.

Important source conventions are part of the task, not hidden knowledge:

- Recognition uses `stim_phase == "recog"`. Source label `0` means **new** and
  `1` means **old**. The exported label description and one paper paragraph
  reverse this meaning; the author's analysis code and complete learning
  histories support the stated coding. Eight sessions have incomplete released
  learning histories: 160 old-labelled recognition images lack within-session
  learning-path evidence. Retain the released labels and report this mismatch;
  do not relabel, drop trials or infer exposure from another session's images.
  Keep original path strings, not image basenames, when checking identity.
  This measures released stimulus labels, not independently verified exposure,
  the patient's reported response or successful recall.
- Use each unit's referenced electrode-table row for anatomy. The source is a
  microwire assignment, not a peak-channel estimator. Keep the original unit
  row/ID, electrode row/ID and location; account for non-MTL units explicitly.
  Include the declared hippocampus/amygdala locations, without outcome-based
  unit-quality or firing-rate selection.
- Trial/event timestamps and spikes use the common acquisition-clock seconds
  supported by source conversion lineage. Do not reset them to separate origins.
  Acquisition timestamps have a literal seconds attribute; the spike-time
  dataset need not have a unit attribute. Record that distinction honestly.
- `stim_on_time` is stimulus onset, `stim_off_time` is stimulus offset, and
  `stop_time` is the released trial-end field. In one session, 97 learning rows
  have a stop before onset despite exact stored TTL6 linkage. Retain these
  literal values and report the temporal-order violations; matching TTL values
  does not establish a correct biological trial-end assignment. Learning stop
  times do not define the recognition response windows. All four time fields
  must remain finite, with start equal to onset and onset no later than offset;
  recognition rows must additionally have offset no later than stop. All 8,700
  released recognition rows satisfy that full order. Do not shift events or
  omit this session. The response window is onset + **[0.2, 1.7) seconds**,
  with both endpoints computed in float64. Count every stored finite event in
  that interval, retaining duplicates, and divide by the nominal 1.5 seconds.
  Counting must be order-invariant: a sorted copy is allowed, but never modify
  the source, deduplicate, or search an unsorted vector as though it were sorted.
  Thirteen units in seven sessions contain timestamp inversions; two of those
  units also contain 2,046 duplicate occurrences. Report original ordering and
  multiplicity diagnostics. These are counts of released events, not a claim
  that every duplicate represents a distinct physical spike. Reject nonfinite
  timestamps.
  Do not clip to stimulus offset or infer observation bounds from spike extrema.
  The window can include post-offset/question-period activity; uninterrupted
  observation is not established when explicit observation intervals are absent.

## Public estimator and populations

For every included MTL unit, retain all source recognition trials and their
integer response counts. Positive class is source code 1 (old). Calculate AUC
with half credit for ties, and a two-sided independent-samples Mann–Whitney
rank-sum test with the disclosed asymptotic tie correction and continuity
correction. This is not the paired signed-rank test. All-tied supported inputs
have AUC 0.5 and p=1; an exception is not permission to substitute p=1.
These nominal p-values define the method's selection rule; this task does not
establish a calibrated biological null under serial dependence or stimulus
structure. The legacy `memory_selective` field names that rule, not a verified
memory-cell identity. Likewise `rate_hz` means released-event count/1.5 seconds.

1. **Full-data-selected/same-trial population.** Select units using strict
   full-data p<0.05. Report each raw code-1 AUC, preferred-direction folded AUC,
   p-value and selection. The summary is an equal-unit mean of folded AUC among
   selected units, evaluated on the same trials used for selection. Report the
   selected fraction with all included MTL units as its denominator.
2. **Repeated-split conditional population.** Use the exact public 60-repeat
   PCG64(0) stratified-half schedule. Its traversal order and random draw order
   are fixed in the contract; do not reset the generator per unit or session.
   On each training half, select with p<0.05 and fix preferred direction there.
   Evaluate that direction on the other half. **Do not fold the test AUC**:
   a legitimate directed test AUC can be below 0.5. Retain every unit×repeat
   event, including nonselected and unsupported cases, and exact original-ID
   membership evidence. For each unit average its train-selected splits; the
   reported population contains units selected in at least five repeats. Then
   average eligible units equally, not all split rows indiscriminately.

Report both summaries, both populations' sizes and overlap. If a selected
population is empty, report its zero denominator and a null mean, not NaN or an
invented 0.5. Any headline must explicitly identify which population it describes.
There is no requirement that one summary be lower than the other.

These populations are not interchangeable. In particular, eligibility based on
at least five selections across overlapping resamples is itself data-dependent:
a trial held out in one split can enter training in other splits. The conditional
summary is therefore **not guaranteed unbiased outer validation**. Different
populations, training sample sizes and direction estimation also contribute to
the contrast; it is not a pure estimate of selection bias.

## Outputs and interpretation

Write the nine artifacts specified in the public contract to `${OUTPUT_DIR}`
(default `/app/output`): session, trial and unit ledgers; primitive response
counts and split memberships; all split events; per-unit measurements;
`results.json`; `run_metadata.json`; and nonempty `findings.md`.

The verifier binds exact source identities and counts, reconstructs every
selection/direction/aggregation, and accepts equivalent implementations within
published numerical tolerances. Complete row/axis reordering and ordinary prose
differences are not errors. Correlation with a reference, a plausible group mean
or an explanation alone is insufficient.

Treat these as descriptive measurements of recorded units. Units within a
session and sessions within a patient are dependent; pooling units overweights
patients with more recordings. No patient-level uncertainty or new-subject
generalization is estimated. A nominal selected fraction near 0.05 does not
identify the false-discovery proportion, and a mean AUC near 0.5 does not prove
absence or equivalence. Incomplete exposure histories, ambiguous event
multiplicity, stimulus identity/order and post-offset activity remain
limitations. Do not turn either summary into an assertion that the paper's
memory finding has been reproduced or disproved.

If a required source, schema or numerical prerequisite fails, exit nonzero and
write parseable `results.json`, `run_metadata.json` and `findings.md` with
`status: failed_precondition` and a nonempty reason. Preserve existing output
and source evidence; do not fabricate a complete run or quietly shrink the cohort.
