# Reference-Logan window sensitivity on public DASB TACs

Analyze the four original deposited PETPrep regional TAC tables from OpenNeuro
ds001420, snapshot 1.2.0: two people, baseline and rescan for each. This is a
paper-derived **method sensitivity control**, not reproduction of a named regional
binding finding or validation of absolute DASB distribution volume ratios (DVRs).

## Scientific question

How do simplified reference-Logan slopes, fit residuals and target/reference
concentration ratios change across declared fitting windows and scan durations?
Report all cases; do not select a winning window or equate high R-squared with
validated kinetics.

The method is motivated by Logan et al. (1996),
[reference-tissue graphical analysis](https://doi.org/10.1097/00004647-199609000-00008),
especially the distinction between the reference-efflux expression and its simplified
form (Equations 6–7). Here we compute only the simplified form. Omitting the
reference-efflux term needs assumptions beyond an apparently straight plot.
Concentration-ratio stability is diagnostic, not proof of DVR validity. No efflux
constant, arterial input, independent binding ground truth or validated DASB window
is supplied. A two-term reference regression would not be plasma-input Ichise MA1.

## Offline source data

Use `/app/data/petdvr/source_manifest.json` and its 24 checksum-pinned original
source/lineage files. The four TAC paths follow:

```
derivatives/PETPrep1/<subject>/<session>/pet/<subject>_<session>_pvc-nopvc_desc-mc_tacs.tsv
```

Subjects are `sub-01`, `sub-02`; sessions are `ses-baseline`, `ses-rescan`.
Analyze exactly these seven columns separately: `highbinding`, `left_thalamus`,
`right_thalamus`, `left_caudate`, `right_caudate`, `left_putamen`, `right_putamen`.
Use the supplied `reference` column, not a newly constructed bilateral average.
That column matches the deposited AGTM reference stream; extraction logs select
cerebellar cortex labels 8 and 47. The archive does not establish its exact extraction
revision or the high-binding composite's weighting. Do not infer identical correction
history for every column from the TSV filename.

Frame times are seconds. Check each TSV against its raw PET JSON sidecar. The sidecars
declare Bq/mL and extraction logs use `--no-rescale`, but TAC-specific units metadata
are absent: units are inherited from that lineage, not independently calibrated.
The published snapshot declares CC0 and requests Cimbi attribution. The
[PET-BIDS paper](https://doi.org/10.1038/s41597-022-01164-1) provides the dataset-format
context, not this task's numerical endpoint.

## Public analysis contract

`/app/method_contract.json` is the complete machine-readable method and output
contract. All scientific choices and required fields are public. Equivalent numerical
implementations are welcome; no particular library or hidden automatic selector is
required.

1. Preserve source frame order and signed finite concentrations. Convert times to
   minutes. Approximate each concentration as constant within its original frame:
   its integral to frame midpoint is the sum of all preceding concentration-times-
   duration products plus half the current product. Always integrate from scan start,
   including frames before the fitting window. Do not invent a zero concentration
   at injection or reset the integral at the fitting start.
2. Form `x = integral(reference) / target` and
   `y = integral(target) / target`. A zero target makes that frame's graph
   coordinates undefined, not a small epsilon denominator. Keep its source record.
3. Evaluate every start in 0, 10, 20, 30, 40 minutes under both end policies:
   `native` and `common50`. Include a frame only if its midpoint is at/after the
   start and its **complete original frame end** is at/before the end cutoff.
   Do not clip or interpolate partial frames. Report actual retained frame bounds.
4. Fit unweighted least squares with an intercept to the valid graph coordinates.
   The contract defines minimum frame count, numerical rank convention, predictions,
   signed residuals and diagnostics. Preserve undefined fits with explicit reasons;
   do not silently fall back to another window.
5. Independently summarize target/reference concentration ratios for window frames
   with nonzero reference, including valid ratio frames that have undefined graph
   coordinates. Report counts, dispersion and time slope as specified. Do not use
   these diagnostics as a hidden acceptance or exclusion threshold.
6. Report signed within-person rescan-minus-baseline slope differences, and descriptive
   per-target/window scan summaries with available scan/person counts. These are
   four scans from **two** people, not four independent participants.

The first baseline scan ends at 53.6 minutes; the other three end at 90 minutes.
Consequently native-end paired comparisons are duration-confounded. The common50
policy avoids later frames but still ends at 48.6 minutes for that first scan versus
50 minutes for the others. Report that residual support difference. The 40-minute
common50 windows contain only two frames and must remain insufficient-frame cases.

## Deliverables and grading

Write the seven files specified by `output_definitions` in the public contract to
`${OUTPUT_DIR}` (default `/app/output`): source frame ledger, graph coordinates,
all 280 window fits, window-frame predictions/residuals, numerical summary,
run metadata and a concise `findings.md`.

The verifier requires complete source-bound coverage and recomputes signed summaries;
it checks source values, frame membership, integrals, fits and diagnostics against an
independent calculation. Row/column order and extra ungraded diagnostics are allowed.
Required numerical values must be finite, except contract-defined undefined fields
represented explicitly. Binary reward is 1 only if all required checks pass; there is
no promised proportional score. Findings are not graded by preferred keywords or
expected scientific direction.

Explain sensitivity and limitations without asserting a true optimal window, a
validated absolute DVR, a population effect, or reproduction of paper-specific values.
On a source/metadata/checksum failure, exit nonzero with a useful diagnostic; never
download replacement data or manufacture a successful result.
