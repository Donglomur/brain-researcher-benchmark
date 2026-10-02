# FCSTAB-001: within-run connectivity selection sensitivity

This method is fixed before connectivity and group endpoints. The machine-readable
method is `/app/method_contract.json`; exact artifact fields, types and bounds are
in `/app/output_schema.json`. `/app/selection_kernel.py` provides the public
selection, conditioning and accepted-value arithmetic. Using that module is
optional; a faithful implementation must satisfy the same declared rules.

## Question and interpretation

For a fixed cohort, how does signed later-minus-earlier mean Fisher-z connectivity
depend on selecting edges from earlier connectivity, later connectivity, other
participants' full-run connectivity, or a fixed random control?

This is a within-run methods case study. The four schemes can select different
edges and need not estimate the same population quantity. A selected-set change
alone does not identify a genuine temporal neural effect. Opposite signs would
not rule out temporal processes; a small mean or nonsignificant test would not
establish stability. No cancellation identity for forward/reverse changes is
assumed. There is no required sign, magnitude, minimum gap, significance or
equivalence result. No diagnosis, age/site effect or repeat-session inference is
part of the task. Pearson agreement across edges is not ICC.

Participants, not edges or frames, are the reporting units for group summaries.
The common ROI mask uses every participant, including each held-out participant.
The scheme named `independent` is specifically LOSO-ranked: it excludes a person
from ranking scores only, not from preprocessing support. LOSO selectors also
share training participants. Participant t intervals and TOST are nominal,
model-based descriptive diagnostics, not dependence-adjusted population-valid
inference. They do not account for common-mask uncertainty, shared selection,
temporal dependence or population sampling. The inherited ±0.05 Fisher-z margin
is operational, not a validated clinical or neural minimum effect.

## Authenticated sources, fixed cohort and frame clock

Use `/app/data/fcstab`, containing 40 original ABIDE PCP CPAC
`filt_noglobal/rois_cc200` text files, the full original phenotype CSV, and an
official Nilearn source notice. These 42 members total 16,147,721 bytes; the
internal `source_manifest.json` is an additional file and is byte-identical to
`/app/source_manifest.json`. Its SHA256 is
`c57fed19c165e8a606c2b6a9aef89099103a2642d6ab54b93bf525d71ea46171`.

Canonical participant order is the manifest's `participant_file_ids`; each
timeseries member supplies the literal FILE_ID and decimal `subject_id` mapping.
`/app/subject_ids.txt` has SHA256
`7645fc4276e63ed4f09e4135bac9d38da3b036a2e4e522fae432ae490d4d28cb`.
This is an explicitly retained 40-person cohort, not a new loader query. No
subject substitution, alias normalization, exclusion or phenotype-based
selection is allowed. Preserve all original ROI columns and frame positions.

Source structural inspection, before connectivity and endpoints, confirmed
40 files of 196 rows × 200 columns, all finite, with positional tab-separated
headers `#1` through `#200`. The full phenotype contains 1,112 original rows:
1,035 named derivatives and 77 `no_filename` rows. Preserve that complete
provenance ledger separately from the selected 40 joins. All selected rows have
literal `SITE_ID=PITT` and `EYE_STATUS_AT_SCAN=2`; report those raw tokens without
inventing acquisition documentation. TR is unverified and unknown. Do not infer
TR or run duration from row count.

Authenticate all member bytes before decoding. Parse original decimal ROI text
directly to binary64; a converted float32 bundle or historical numerical bank
is not source authority. Missing/nonfinite values or broken identity/dimensions
are failed preconditions, not permission to discard people or values. Add no
filtering, nuisance regression, censoring, interpolation or normalization to
these released preprocessed series.

The manifest distinguishes measured SHA256 identity from publisher metadata.
S3 `versionId=null` is not an immutable release and ETag is an If-Match token,
not assumed MD5. See `/app/SOURCE_NOTICE.md` and the manifest for attribution,
noncommercial use, registration and share-alike terms. Public transport does not
itself authorize unrestricted redistribution or commercial use.

For T rows, let L=floor(T/2): first is `[0,L)`, second is `[T−L,T)`, full is
`[0,T)`. An odd middle row is excluded from halves but retained in full. Each
half requires at least two rows; the authenticated source has 98 rows per half.

## Common support and signed connectivity

For each person, original ROI and first/second/full segment, compute population
SD (`ddof=0`). Exact constants have mean equal to their first value and SD 0.
Otherwise compute the mean with scalar `math.fsum` in original frame order
divided by segment length, and SD from the accurate squared centered deviations
divided by length. Use stable scaled sum-of-squares to prevent underflow or
overflow; finite moments are required.

A column is common exactly when its SD is strictly greater than 1e−8 for every
person in all three segments. This is an operational criterion in source units,
not a biological QC rule. The source-derived operative mask is exact: no
subject-specific mask, threshold search, near-constant rescue or expected mask
cardinality. Require at least two common columns; otherwise fail preconditions
without changing the cohort. The common mask is transductive as described above.

For every common pair i<j, use centered, L2-normalized columns to calculate
Pearson correlation. This scale-normalized formulation avoids a tiny product of
norms. Finite excursions beyond [−1,1] up to 1e−12 can be clipped; larger
excursions fail. Fisher-z is `atanh(clip(r,−.999999,+.999999))`. Keep signed
values. Original ROI IDs 1..200 are positional, not anatomical label claims.
Canonical pairs are lexicographic original `(roi_i,roi_j)`. With M common ROIs,
E=M(M−1)/2 and k=max(1,E//10). Every pair, including negative edges, belongs to
the selection universe.

## Selections from accepted source-bound primitives

The verifier independently reconstructs source support and z. Submitted z must
first satisfy elementwise source fidelity and the conditioned-vector rule below;
cohort, common mask and pair membership are exact. Accepted z then determines
selection and participant arithmetic. There is no additional exact oracle-set
target near ties or rounding boundaries.

Rank decreasing signed score, breaking exact ties by increasing canonical
original pair, without rounding or tolerance-based tie merging:

| Scheme | Ranking or drawing rule |
| --- | --- |
| `forward` | This person's accepted first-half z |
| `reverse` | This person's accepted second-half z |
| `independent` | `fsum/39` of accepted full-run z over all other 39 in canonical cohort order |
| `random` | k canonical edge indices without replacement |

The training IDs are exactly the other 39, not a data-selected subset. Their
serialized order may vary. Initialize `numpy.random.Generator(numpy.random.PCG64(0))`
once, then make one `choice(E,size=k,replace=False)` call per canonical subject,
with no intervening draws. CSV/NPZ storage order does not affect this schedule.

Selected index order is immaterial to membership. Reduce selected values in
canonical pair order using `math.fsum/k`. Every scheme's delta is second mean
minus first mean, including reverse. Evidence indices address the submitted
NPZ edge axis and are remapped through original pairs before set checks.

## Source-conditioned support, not hidden endpoint targets

For each person's first, second and full E-edge vector, let b be source z and a
accepted z. Elementwise fidelity always applies. If the centered source norm
is positive, require positive accepted centered norm and
`||center(a)−center(b)||2 <= 1e−6*||center(b)||2`, without an absolute floor.
Exact constants center to zero; use accurate means and stable scaled norms.

Pearson and average-rank Spearman reliability use accepted first/second z.
Source E<2 gives `source_insufficient_edges`; either source vector constant gives
`source_constant`; both cases require null correlations even if accepted jitter
creates variance. Active accepted vectors determine the coefficients; no source
coefficient is a second target. Exact accepted ties determine average ranks,
so tiny near-tie changes can alter Spearman. Collapsed accepted active support
is invalid, not a new source-inactive status.

Delta conditioning is selected-set-specific. Evaluate each accepted selected
set on unrounded independent source z to obtain each source delta d_i; do not
substitute sets ranked on source z. For each scheme's 40-vector d, define
`C=stableL2(d−mean(d))`, and
`b_i=8*eps64*(mean_abs(source_first_selected_z)+mean_abs(source_second_selected_z)+abs(d_i))`.
Let B=stableL2(b) and tau=1e−6. C=0 is `source_zero_variance`;
0<C<=B/tau is `numerical_resolution`; C>B/tau is active. Evaluate ratios/norms
stably and handle underflow/nonfinite values explicitly. This is a public
selected-mean cancellation-resolution convention, not a universal bound for
arbitrary FC solvers and not an additive fidelity floor.

On active schemes, accepted CSV deltas a must also satisfy
`||a−d||2 <= 1e−6*C`. The error is not centered: a uniform shift could otherwise
change tiny-SE inference arbitrarily. This condition contains no hidden
source t, p, TOST or Boolean endpoint target. Full-precision storage may be
needed; six-decimal CSV or float32 is not universally adequate.

For source-inactive schemes, accepted-row mean/SD/SE and negative count remain
own descriptors, even if receipt jitter creates positive SD. All t/p/CI/TOST
fields stay null with the source-inactive status. Do not claim accepted SE is
zero merely because source inference is inactive, or infer a population null.

## Accepted rows, group arithmetic and reliability receipts

Each CSV mean/delta is checked against selected accepted-z replay. Forward
delta versus accepted second-minus-first uses the sum of all three component
error bounds. Accepted CSV deltas alone drive group statistics, negative counts
and TOST. Duplicate evidence means are receipts against NPZ replay only, never
replacement group values. If comparing separately rounded evidence and CSV,
add their bounds instead of requiring exact equality.

Reduce the 40 accepted deltas in canonical subject order: mean=`fsum/40`,
sample SD with denominator 39, SE=SD/sqrt40 and df 39. When source-active with
positive finite SE, t=mean/SE, p=`2*scipy.stats.t.sf(abs(t),39)` and
CI95=`mean ± scipy.stats.t.ppf(.975,39)*SE`. Unavailable arithmetic uses
`numerical_underflow` or `numerical_nonfinite` with null inferential fields,
never NaN/Infinity, a reduced cohort or a fabricated finite statistic. A finite
tail probability computed as zero is not claimed to be exactly zero in real
arithmetic. Count negative deltas with strict accepted value<0, no epsilon.

Only `independent_delta` receives TOST: margin m=.05 and alpha=.05;
`p_lower=t.sf((mean+m)/SE,39)`, `p_upper=t.sf((m−mean)/SE,39)`,
`tost_p=max(p_lower,p_upper)`. `equivalent_within_margin` is strictly
`tost_p<.05` from unrounded own replay, not a displayed p, CI or source Boolean.
Inactive/undefined inference makes all three p fields and the Boolean null,
including source-constant vectors at ±margin. No equivalence outcome is required.

Forward group first/second means come from accepted CSV means; its `change`
equals the accepted forward delta mean, with propagated linear coherence.
Forward/reverse averages and percentage changes are not required or graded.

Per-person reliability receipts contain overlap `|forward∩reverse|/k`, Pearson,
Spearman and exact source-support status. After checking them against accepted-z
replay and source activity, their accepted values drive group reliability means.
Overlap uses all 40. Each correlation mean uses all 40 only if all are defined;
otherwise it is null with exact n_defined/n_undefined and `undefined_member`.
There is no partial-subset average or ICC substitution.

## Five artifacts and tolerances

Write all five files to `${OUTPUT_DIR}` (default `/app/output`):

1. `connectivity.npz`: subject/segment/original-ROI/pair axes, exact common mask,
   and first/second/full z. Axes and fields are in `/app/output_schema.json`.
2. `stability.csv`: the eight required named columns and one row per subject;
   `n_edges` is E, not k. Bounded descriptive extra columns are allowed.
3. `selection_evidence.json`: `fcstab-selection-v3`, status `complete`, four
   digest pins, E/k/seed 0 and 40 subject records with training IDs, four sets,
   per-scheme first/second receipts and reliability. No common-ROI list is
   required here; support is in the NPZ and summary source observations.
4. `summary.json`: `fcstab-summary-v3`, status `complete`, four digest pins,
   exact source/cohort observations, software, four group summaries, TOST,
   forward mean/change, reliability and per-scheme source-inference statuses.
   Numeric conditioning diagnostics are optional and ungraded.
5. `findings.md`: concise interpretation of actual results and the stated
   methods-case limitations, with no mandated sign or conclusion wording.

Source z and per-person receipts use atol1e−6/rtol1e−6; summary replay uses
atol1e−8/rtol1e−6. The scalar formula is `|a−b|<=atol+rtol*|b|`.
Vector-fidelity rules above are additional. Support, membership, counts and
statuses are exact after identity alignment. Nonlinear outcomes and Booleans
use the one accepted-value replay. The serialized Fisher cap permits its stated
source-fidelity rounding allowance.

Unique coherent axis/row permutations, numeric formatting, memory order,
endianness and stored/deflated NPZ member order are not scientific targets.
Safe real numeric storage must still satisfy shape, finiteness, domain and
conditioned-fidelity rules; there is no unconditional dtype equivalence.
Identity values must be integral and non-Boolean (exact integral floats are
allowed). Masks use Boolean or integer 0/1. No pickle, object/structured/complex
arrays, duplicate JSON keys, nonfinite numbers or ambiguous identities. Preserve
literal strings and schema nulls; omitted keys are not nulls. Descriptive extras
cannot override required fields.

Bounds: NPZ 64 MiB stored /128 MiB expanded /16 members; evidence 16 MiB; summary 8 MiB;
CSV 1 MiB; findings 64 KiB; entire output 96 MiB. Exact additional reader bounds are
in the output schema. Reject unsafe paths, links and archive names. Source,
output and private paths are disjoint; use fresh exclusive outputs. Any
`failure_report.json` entry, including a dangling link, invalidates completion.
A partial pilot is not a complete 40-person result. Failures must exit nonzero
and preserve a truthful failure receipt; do not overwrite prior evidence.

The verifier authenticates source independently of mutable participant/oracle
or staging code. Source reconstruction is separate from the shared public
selection/replay kernel; sharing that kernel is disclosed arithmetic, not an
independence claim for inference or scientific validity.

## Paper motivation and adaptation boundary

[Barnett et al. (2005)](https://pubmed.ncbi.nlm.nih.gov/15333621/) motivates
checking how selection of extreme baseline values affects subsequent change.
[Noble et al. (2019)](https://pmc.ncbi.nlm.nih.gov/articles/PMC6907736/) provides
the functional-connectivity reliability context; the present edgewise Pearson
correlation is not its test-retest ICC estimand. These papers motivate the
question and interpretation limits, not this particular cohort or a prescribed
numerical outcome. This task does not reproduce a named paper figure or table.
