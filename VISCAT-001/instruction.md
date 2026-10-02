# Visual-category preference in human MTL recordings

Reproduce a specified descriptive analysis of public single-unit recordings.
Report how selection and evaluation choices define two different populations of
recorded units. This is a paper-derived method control, not a reproduction of
either paper's numerical finding or a test of patient-population prevalence.

## Data and paper correspondence

All 87 original NWB assets from DANDI 000004, published version
0.220126.1852, are available offline under /app/data/viscat.
The source manifest in that directory records the exact asset identities,
immutable object versions, sizes and SHA-256 hashes. Verify the complete bundle
before analysis. Do not download, replace, omit or silently repair source files.

[Faraut et al. (2018)](https://doi.org/10.1038/sdata.2018.10), Table 2 and the
selective-cell Methods, provides the three visual-category variants and a
1.5-second response interval beginning 200 ms after stimulus onset.
[Chandravadia et al. (2020)](https://doi.org/10.1038/s41597-020-0415-9), Figure 5f,
uses a one-second ANOVA analysis on the expanded release. Our all-session,
Kruskal–Wallis and repeated-half recipe below is an explicit adaptation:
neither original ANOVA result nor the original behavior-filtered population is
being reproduced.

The full public numerical and output schema is /app/method_contract.json.
It specifies required columns, array axes, types, nulls and tolerances. Implement
the stated mathematics by any equivalent method; there is no hidden estimator.

## Source measurements

Retain every original session, trial and unit in the source ledgers. Analyze all
trials whose literal phase is recog and all units whose sole recorded
electrode-table link has a location containing Hippocampus or Amygdala.
Keep source rows AND IDs, asset path/UUID, subject ID, electrode row/ID, original
channel and exact location. This is a recorded electrode link, not a measured
peak channel. Do not apply additional behavior, confidence, firing-rate or unit-QC
exclusions.

Category codes 1–5 are session-local. Preserve each code's literal category_name
and full external_image_file; do not apply the first variant's labels globally.

| Original image-path prefix | Literal names for codes 1, 2, 3, 4, 5 |
| --- | --- |
| newolddelay | houses, landscapes, mobility, phones, smallAnimal |
| newolddelay2 | fruit, kids, military, space, zzanimal |
| newolddelay3 | 1cars, 2food, 3people, 4spatial, 5animals |

These path/name correspondences identify the observed stimulus variants; they
are not an invented literal NWB variant field or a cross-session category
ontology. Use numeric codes only within each session's statistical comparisons.

Count every stored timestamp occurrence in the half-open interval
[float64(stim_on_time)+0.2, float64(stim_on_time)+1.7).
Divide by 1.5 for Hz. Preserve the common arbitrary acquisition-clock origin,
full timestamp precision and multiplicity. Some arrays are unsorted; a stable
sorted copy, direct interval predicates or equivalent counting is valid.
Never binary-search unsorted input, deduplicate, shift clocks independently,
or modify the source.

Audit source TTL and experiment-ID links using each session's original mapping.
Retain finite original start/onset/offset/stop fields. All rows require
start=onset and onset<=offset; recognition additionally requires offset<=stop.
Known learning-only stop-field anomalies remain literal diagnostics, not a
reason to drop valid recognition data. Observation intervals are absent:
continuous recording coverage is unknown and cannot be inferred from spike
extrema. The fixed post-onset response window can extend beyond stimulus display.
Released events are not independently authenticated unique physical spikes.

## Statistics and splits

Use integer occurrence counts as the rank-statistic primitive.

For each MTL unit, use all recognition trials for a five-group Kruskal–Wallis
test with average ranks, pooled tie correction and chi-square survival with
four degrees of freedom. There is no continuity correction. Selection means
unrounded p<0.05. Explicitly handle all-identical counts as H=0, p=1,
status all_tied, not selected. Do not convert arbitrary errors to p=1.

The preferred category has the largest mean count; compare exact integer
sum/count fractions and break exact ties by the smallest numeric category code.
Preferred-versus-rest AUC is the probability that a preferred count exceeds a
rest count, plus half credit for equal counts. Record its exact doubled-U
numerator and class sizes. Do not flip the AUC: highest mean does not guarantee
AUC above 0.5. Missing support is undefined, not 0.5.

Generate 50 stratified training halves with one NumPy Generator(PCG64(0)),
using the NumPy 2.2.6 shuffle sequence. Traverse repetitions 0–49, then units
ordered by lexical full asset path and original unit-table row, then categories
1–5. For each category, copy recognition-position indices in original trial
order, shuffle the copy, and take the first floor(n/2) indices.
Sort their union into original trial order; the complement is held out.
Do not reset the RNG per unit/session or share membership between units.
The contract specifies unsupported cases and their zero-RNG-consumption rule.

For every supported split, compute selection and preference using TRAINING
counts only; compute unflipped AUC on the held-out counts using that training
preference. Save all fifty events per unit, including unselected events,
and their source-keyed membership. All five categories must exist for full-data
statistics and have at least two trials each for a supported split.
Keep unsupported rows and explicit nulls; do not silently shrink denominators.

## Two separately defined populations

Report both:

1. full_data_selected_same_trials: equal-unit mean full-data AUC among units
   selected on those same full-data trials.
2. crossfit_selected_at_least_five_splits: first average held-out AUC within
   each unit over its training-selected splits, then average units selected in
   at least five of the fifty splits, weighting units equally.

A unit selected on one to four splits retains its diagnostic conditional mean
but is not eligible for the second population; zero selected splits gives null.
Full-data selection is not required for second-population eligibility.
Empty populations have count zero and mean null, not a substituted chance score.

Also report selected/all-MTL proportion, supported/unsupported counts, each
population's denominator and their overlap. Declare either population as the
headline and make the headline value agree with it. Neither a particular
mean/order nor an above-chance conclusion is required.

The first estimate is selection-conditioned. The second uses dependent,
overlapping halves and eligibility determined across the full procedure.
The populations differ; their difference is not an identified estimate of
selection bias. Units are nested in sessions and repeated patients, not
independent people or necessarily distinct biological neurons across sessions.
No IID-unit/split confidence interval, patient-generalization, neural-specificity
or cell-prevalence claim follows from these summaries.

## Required outputs and grading

Write to OUTPUT_DIR, default /app/output, following the public contract:

- sessions.csv: every source asset and its identity/support counts.
- trials.csv: every original trial, including nonanalysis rows and local categories.
- units.csv: every original unit and exact electrode mapping/inclusion.
- responses.npz: source-keyed integer counts, rates and complete split membership.
- neurons.csv: all MTL units' full-data statistics and conditional summaries.
- split_events.csv: all MTL unit × repetition events and their arithmetic.
- results.json: both populations, denominators, overlap and declared headline.
- run_metadata.json: exact source/method identities, measured diagnostics and
  actual implementation versions.
- findings.md: a short, appropriately qualified interpretation.

The verifier reconstructs source primitives and splits and checks complete
identity coverage, public arithmetic and aggregation. It accepts coherent
row/axis reorderings and equivalent implementations within the published
tolerances. Findings text is not keyword-graded. A source-consistent result
does not prove how it was historically produced.
Scoring is binary: 1 for the complete verified contract, otherwise 0; partial
outputs are not proportionally scored.

Use a fresh output directory. On invalid source, nonfinite input, inconsistent
identity or unexpected numerical failure, exit nonzero and write an explicit
failed_precondition receipt with a reason. Do not overwrite prior evidence,
drop problematic observations silently, or present partial success as a
complete analysis.
