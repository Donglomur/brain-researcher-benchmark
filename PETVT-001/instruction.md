# Two blood-reference assumptions in arterial-input PET kinetics

Use seven released baseline participants from OpenNeuro ds005619 snapshot 1.1.0
to measure sensitivity to two explicit assumptions about blood activity reference
time. This is a methods-sensitivity case, not paper replication or identification
of the true blood-reference convention.

Original TACs, manual blood tables, matched sidecars and provenance are staged
offline under `/app/data/petvt`. Their exact 31-member identity is in
`/app/source_manifest.json`, also inside the source directory. Read
`/app/SOURCE_NOTICE.md`, `/app/ANALYSIS_CONTRACT.md`,
`/app/method_contract.json` and `/app/output_schema.json`.
These are the complete public scientific and serialization rules. Do not
substitute sources, participants or historical answers.

For sub-sf02, sub-sf05, sub-sf06, sub-sf07, sub-sf08, sub-sf09 and sub-sf10:

1. Form each frame's equal-weight mean of the 68 cortical region columns.
   This is not a volume-weighted cortex or a mean of separately fitted regional V_T.
2. Preserve every original blood row in the eligibility/duplicate ledger.
   Coalesce only exact same-time, identical plasma-and-parent pairs without
   averaging. Conflicting pairs fail. Do not discard time-zero rows as presumed
   padding. Use the operational pre-bolus zero anchor only when zero is absent.
3. Apply both assumptions at the paired observed knots:
   `already_image_reference` uses plasma × parent fraction;
   `sample_time_reference` additionally multiplies by
   exp(log(2) × (time − image_reference) / 6586.2), with times in seconds.
   Neither branch is called correct. Interpolate transformed knots linearly.
4. Use exact piecewise-linear input integration and frame-duration tissue
   integration in minutes. Fit unweighted Logan and MA1 to every frame midpoint
   at or after 30 minutes, using the published normalized least-squares recipe.
   No held-tail extrapolation, adaptive window, outcome-selected cutoff or
   exclusion of signed nonpositive estimates is allowed.
5. Retain all 28 participant/assumption/estimator slots and typed unavailable
   results. Report complete-seven summaries for four families and each signed
   paired assumption change (sample-time minus already-image-reference).
   Incomplete families have null group statistics, not changed denominators.

Write five required artifacts to `${OUTPUT_DIR:-/app/output}`:

- `vt_estimates.csv`: 28 keyed records with status, fit-row count, rank,
  coefficient receipts, signed V_T, nonpositive flag and RSS diagnostics.
- `kinetic_evidence.npz`: complete source-bound cortical/frame/knot axes and
  primitive receipts, masks, source-design diagnostics and coefficients, with
  the exact arrays in the output schema.
- `sensitivity_summary.json`: four complete-family summaries, all 14 signed
  paired changes and two complete paired summaries.
- `run_metadata.json`: three authority hashes, complete source identity and
  row ledgers, software strings and warnings; no answer targets.
- `findings.md`: describe both assumptions, the estimand, fitted estimates,
  sample SD/defined counts, signed sensitivity and unavailable results. Explain
  the unresolved reference convention. Do not infer genotype, clinical effects,
  tracer validity or paper replication.

The verifier reconstructs source primitives independently. Source-close
submitted NPZ coefficients are the single downstream authority for V_T and
summaries; CSV coefficients and primitive/design diagnostics are receipts,
never separate refitting inputs. Canonical source support and the public
coefficient/MA1-relative fidelity rules are enforced, not a historical V_T,
preferred direction, estimator agreement or physiological range. The two
implementations share the specified SciPy least-squares solver, not source
extraction or integral/replay code.

Malformed or changed sources are errors: exit nonzero with a concise
`failure_report.json` in a safe output directory. Method-defined numerical
unavailability is retained, not a task failure. Never serialize NaN/Infinity.
Bounded harmless extra reports/code are allowed but have no acceptance role.
Analysis and grading are offline. Difficulty metadata is provisional and
has not been calibrated by model runs.
