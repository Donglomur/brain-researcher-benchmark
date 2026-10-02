# Within-run connectivity selection sensitivity (FCSTAB-001)

Use the fixed 40-person ABIDE PCP CC200 cohort to compare signed
later-minus-earlier Fisher-z connectivity under four edge-selection schemes.
This is a methods case study: selecting extreme edges can affect the measured
change, and the comparison does not by itself identify a genuine neural
temporal effect. No sign, magnitude, significance or equivalence result is
required.

## Offline data and public contract

Original CPAC `filt_noglobal/rois_cc200` text, full phenotype provenance and a
source notice are baked into `/app/data/fcstab`. The fixed identities and
canonical order are in `/app/source_manifest.json` and `/app/subject_ids.txt`.
There are 40 original timeseries, each 196×200; all selected phenotype joins have
raw tokens `SITE_ID=PITT` and `EYE_STATUS_AT_SCAN=2`. TR is unverified: do not
infer a scan duration or recode acquisition facts without authority. Do not
replace the cohort with a fresh loader query or use a converted answer bundle.

Read `/app/methods.md`, `/app/method_contract.json` and
`/app/output_schema.json` for the exact estimator, support/undefined rules,
artifact schema and numerical bounds. `/app/selection_kernel.py` is an optional
public implementation of selection and replay arithmetic. Source rights and
attribution are described in `/app/SOURCE_NOTICE.md`. Runtime is offline.

## Analysis

Authenticate the original files, preserve frame and column identities, and split
each run into its first and last floor(T/2) rows. Add no preprocessing. Use the
single source-defined common ROI mask: population SD strictly >1e−8 for every
person in first, second and full segments. Compute signed Pearson/Fisher-z
edges with the documented stable arithmetic and clipping. Do not assume a
particular retained-ROI count.

For each person select k=max(1,E//10) edges using:

1. `forward`: largest signed first-half z.
2. `reverse`: largest signed second-half z.
3. `independent`: largest mean full-run z from exactly the other 39 people.
4. `random`: the fixed size-matched PCG64(0) schedule.

Every delta is second mean minus first mean. Apply the exact pair tie rule and
canonical draw schedule. Report per-person values, four group summaries and
nominal uncertainty; independent-delta TOST at ±.05; forward first/second means;
and overlap/Pearson/Spearman reliability. Preserve nulls when source support or
numerical resolution makes inference unavailable. All 40 remain represented.

Source-bound submitted connectivity primitives determine selections. Accepted
CSV rows determine group statistics; accepted reliability receipts determine
reliability means. The public conditioned-fidelity rules prevent tolerated
rounding from inventing inference on source-constant or unresolved variation.
Full precision may be necessary. There is no hidden selected-set or endpoint
target.

## Deliverables

Write to `${OUTPUT_DIR}` (default `/app/output`):

- `connectivity.npz`: aligned identities, source common mask and all three z arrays.
- `stability.csv`: one row per fixed subject with the eight required fields.
- `selection_evidence.json`: all four selected sets, all 39 training IDs,
  per-scheme means and reliability receipts.
- `summary.json`: source observations, provenance, accepted-row summaries,
  TOST, reliability and support statuses.
- `findings.md`: concise interpretation of the actual results and limitations.

Exact fields, types, permutations, tolerances and bounded extras are specified
in `/app/output_schema.json`; all five files are required. Undefined inferential
endpoints can be valid complete results. On a failed source/numerical
precondition, exit nonzero and preserve `failure_report.json` with a nonempty
reason; never masquerade as a complete or reduced-cohort result.

Explain that the common mask is transductive and LOSO excludes a person only
from ranking. Different selectors can target different edges, ordinary t/TOST
does not account for shared selectors or temporal dependence, and Pearson is
not ICC. Neither a selected decline, sign reversal, nonsignificance nor an
equivalence result alone establishes or rules out a neural temporal process.
