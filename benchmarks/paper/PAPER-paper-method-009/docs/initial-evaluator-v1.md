# Intracellular DSR construction bridge

This package implements a concrete prospective voltage/spike analysis for
`PAPER-paper-method-009`. It reads the named Pala MATLAB fields, detects and
removes action potentials, fits voltage-to-rate splines, integrates operational
time, and pairs those estimates with the exact pinned DSRP spike-only estimator.
It does not establish an authentic Fig. 3 reconstruction, qualified benchmark,
reference answer, or improvement result. The original task and history remain
unchanged.

## Inputs and invocation

Use an existing Python environment with NumPy and SciPy. No installation or
data acquisition is performed by this package. From the repository root:

```sh
python benchmarks/paper/PAPER-paper-method-009/implementations/initial-evaluator-v1/evaluator.py --mat /approved/data.mat --plan /approved/plan.json --output /approved/report.json
```

The CLI requires the source-recorded data.mat MD5
`dc333d3d03b79460f2ec1d36122206c8`, records its SHA-256 and the plan SHA-256, and
refuses a mismatch. It does not claim that a checksum validates biological
identity or schema. MATLAB v7.3/HDF5 remains unsupported pending actual source
schema qualification. `load_pala(..., verify_source=False)` exists exclusively
for generated adapter tests; the CLI has no checksum bypass.

The Pala scalar `data` struct must contain aligned trial vectors:
`Trial_MembranePotential`, `Trial_MembranePotential_SamplingRate`, `Trial_Type`,
`Cell_Type`, `Mouse_Name`, and `Cell_Counter`. Voltage must be a cell vector of
numeric row/column traces in mV. Identities are `Mouse_Name_Cell_Counter` and
stable one-based source row IDs such as `pala-row-000001`; the loader never
concatenates trials, changes units, or reorders rows. These fields are supported
by PalaPetersen_Analysis.m, not by inspection of the 1.31 GB data payload.

The plan explicitly acknowledges a prospective recipe and partitions every
qualifying cell's trials. The example is a shape illustration, not an authentic
cohort manifest:

```json
{
  "recipe": "prospective-held-trial-natural-cubic-v1",
  "cells": {
    "example_mouse_1": {
      "calibration_trial_ids": ["pala-row-000001", "pala-row-000002"],
      "assessment_trial_ids": ["pala-row-000003", "pala-row-000004", "pala-row-000005", "pala-row-000006", "pala-row-000007", "pala-row-000008", "pala-row-000009", "pala-row-000010"]
    }
  }
}
```

Each partition needs at least two trials; overlap, repeated IDs, missing cells,
and omitted qualifying trials fail. Freeze this plan before assessment access.
The software checks membership, not the historical independence of the plan.
Inclusion uses the full observed source recording before splitting, as a fixed
cohort rule; this is disclosed assessment exposure, not training-only selection.

## Source requirements and implemented behavior

| Requirement | Implementation and provenance |
| --- | --- |
| PV intracellular scope, 20 kHz, mean rate at least 20 Hz, at least ten 20 s trials | `audit_population`; ledger includes all source cells, candidate and noncandidate trial IDs, observed rate, and exclusion reasons. Non-20 s PV spontaneous trials fail closed pending a selection/truncation policy; no smaller cohort is substituted. |
| Pala PV spontaneous fields and mouse/cell nesting | `decode_pala`; field mapping comes from the deposited original analysis helper. Original-study first-trial deletions and 1 s trimming are not imported into DSR. Their applicability remains unresolved. |
| Upward −30 mV crossings; remove −3/+5 ms and linearly interpolate | `spike_indices`, `remove_spikes`; overlapping windows are merged before interpolation. A missing edge endpoint fails rather than extrapolating. Spike timing remains at 20 kHz. |
| Voltage/rate relationship | `fit_voltage_curve`; both 25 and 50 ms bins run on calibration trials only, followed by 1 mV voltage bins from −68 to −40 mV. |
| DSR spike-only estimate | Exact unmodified MIT `neuron_stat.py` at commit `ba0490d064ea299c975e12bb94f3d922468f6b50`, checked by SHA-256 before use. Full finite trial matrices only, alpha=2, source population variance/MAD/refinement/quadratic behavior retained. |
| DSR bin width | Paper methods `T=2/E[lambda]`; implementation rounds upward to integer ms and uses a fixed 50 ms shift. Rounding and shift are explicit prospective policies. The 25/50 ms voltage sensitivities are separate from DSR width. |
| Native binary milliseconds | Detected spikes are rasterized in left-closed 1 ms bins. Collisions fail rather than drop spikes. Original timestamps remain available for raw and voltage ISIs. |
| Operational irregularity | `operational_isis`; integrates the nonnegative sampled rate using a left-constant rule. The official `time_rescaling.py` is an inverse simulator and is not used for this operation. No normalization forces the operational mean to one. |
| Outputs | Per-neuron native phi, raw population CV², voltage phi, both phi/raw-CV² fractions, paired phi differences, operational mean, counts, spline support diagnostics, and Poisson phi=1 reference. Fractions above one remain visible; a zero raw CV² yields null fraction. |
| Stability and biological units | Per-assessment-trial 10 s voltage/raw segments; separate aligned 10 s DSR windows across assessment trials. No ISI crosses trial boundaries or the boundaries of segment estimates. Segment mean/SEM is descriptive within a neuron; neuron summaries remain nested within mice. |

## Explicit prospective choices and remaining holds

The primary paper's text/methods use 50 ms voltage bins, while Fig. 3 uses 25 ms.
Both outputs are retained; neither is selected for agreement. The printed
voltage-bin-coordinate formula is inconsistent with the stated range. This
recipe uses conventional centers −67.5 through −40.5 mV. The paper says
“spline” without fixing family, degree, smoothing, support extrapolation, or
negative-rate handling. This recipe uses a natural cubic interpolant through
occupied bins, requires four occupied bins, clamps voltage to observed fit
support, and floors negative interpolation values at zero. It reports every
clamped/floored sample count and omitted out-of-voltage-range calibration bin.
These policies are prospective, not recovered author choices.

Fig. 3 describes twenty 10 s segments per neuron but the pinned estimator takes
an across-trial axis. The exact mapping and any selection from more than ten
trials remain unresolved. This bridge preserves all qualifying trials and labels
its aligned-window DSR estimates separately; it does not relabel them as the
published twenty-segment analysis. A held-trial fit also differs from the
descriptive full-recording spline in the paper and serves a prospective stability
assessment. Native nonfinite/quadratic failures remain null with a reason and do
not trigger filtering out cells. There is no score or pass/fail scientific grade.

Authentic MAT schema, preprocessing, all eight neuron identities/five mice,
source-specific source-trial exclusions, full-population reference execution,
independent scientific validation, protected assessment, grading tolerances,
difficulty and resource qualification remain open. A matching 8/5 count is
explicitly not identity validation. The scope remains Fig. 3 intracellular
validation; no cortical-hierarchy or whole-paper claim is made. The paper and
results are public, data are CC BY 4.0, and code is MIT; no blind code-benefit or
compute-equivalence claim follows from this bridge.

## Engineering validation

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s benchmarks/paper/PAPER-paper-method-009/implementations/initial-evaluator-v1/tests -v
```

The generated tests include independently derived native count solutions
`phi=1` and `phi=12−sqrt(113)`, rational CV² and piecewise-rate integrals,
unclipped fractions, action-potential overlap/edges, MATLAB schema round-trip,
native-source pin parity, collision and missing-data refusals, full pipeline
25/50 ms output, cohort boundaries, split overlap/omission, and segment/trial
boundaries. Generated controls establish implementation behavior only. No
authentic data, model, archive, or native scientific campaign was run.

Primary references and exact inspected-source hashes are in `provenance.json`.
The vendored estimator retains its original MIT license and copyright notice.
