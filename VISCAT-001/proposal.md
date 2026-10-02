# VISCAT-001: category preference and conditional-selection sensitivity

This is an explicitly specified, descriptive method control on authentic public
human MTL recordings, not an uncued trap or a reproduction of a named numerical
paper finding. Difficulty is provisionally easy; no Sol or frontier calibration
is claimed by this repair.

## Paper and data correspondence

[Faraut et al. (2018)](https://doi.org/10.1038/sdata.2018.10) supplies the
new/old task, three category dictionaries (Table 2), and the visual-selectivity
Methods' 1.5-second response window beginning 200 ms after onset. That analysis
uses one-way ANOVA, and the illustrated sample applies behavioral session
exclusions. [Chandravadia et al. (2020)](https://doi.org/10.1038/s41597-020-0415-9)
describes the expanded NWB release and uses a one-second ANOVA window for the
selective-cell analysis in Figure 5f.

This task instead retains all 87 sessions of
[DANDI 000004, version 0.220126.1852](https://doi.org/10.48324/dandi.000004/0.220126.1852),
all recognition trials and all source-mapped hippocampal/amygdala units, with
Kruskal–Wallis selection and 50 repeated stratified halves. These are deliberate
method adaptations, not the papers' original estimator, population or results.
The manifest pins asset UUIDs, immutable object versions, full-file sizes and
published SHA-256 values for 6,197,474,020 original bytes. Build-time staging
verifies those bytes and bakes them into the image; analysis is offline. Source
attribution and CC-BY-4.0 metadata are retained. This local repair does not publish
the data or image.

## What the task measures

Compute two separately denominated summaries: preferred-category-versus-rest
AUC among full-data-selected units on the same trials; and the per-unit mean
held-out AUC among units selected on at least five of fifty training halves.
Both are valid descriptive endpoints when labelled correctly. Neither is an
unbiased patient-population estimate; their populations differ and the repeated
halves overlap. No required ordering, above-chance value, selection proportion,
effect size, or prose keyword is part of acceptance.

The public contract exposes all estimator, split, support and serialization rules.
The substantive work is preserving source identity, session-local category
semantics, timestamp multiplicity, trial partitions and the two denominators.
There is no secret estimator or preferred numerical answer.

## Source limitations

Category codes 1–5 have three different session-local dictionaries; retain the
literal names and image paths rather than relabelling all sessions as variant 1.
A unit's recorded single electrode link is not a measured peak channel.
Unsorted spike arrays must be handled without losing duplicate occurrences.
The target is released-event counts, not verified unique physical spikes.
Observation intervals are absent, so continuous coverage is unknown. Preserve
the original acquisition-clock origin. The fixed half-open post-onset window
can extend beyond image display. Learning-only stop-field anomalies and
incomplete learning histories are disclosed, not used to exclude otherwise
valid category-analysis trials.

## Verification and evidence boundaries

The verifier reconstructs source counts, complete trial membership and public
arithmetic. It requires all source ledgers, every split including unselected
ones, exact categorical decisions, and both endpoint denominators. Equivalent
implementations and either declared headline are accepted. Findings text is
ungraded. A source-consistent submission is not proof of independent historical
execution, and a public task cannot honestly be called fabrication-proof.

The historical numerical bank is retired from grading and preserved outside the
task for recovery. Native tests, independent reconstruction, clean-commit Harbor
execution and final-image checks are separate evidence gates recorded in
REPAIR_STATUS.md and the maintainer's external receipts. Passing them does not
establish scientific generalization or benchmark hardness.
