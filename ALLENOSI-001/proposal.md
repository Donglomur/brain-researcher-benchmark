# ALLENOSI-001: one-session descriptive orientation-selectivity control

## Scientific target and connection to the paper

Use an original Allen Visual Coding Neuropixels session to compute a completely
specified two-point orientation contrast for every recorded VISp cluster.
Report the fraction above a fixed threshold, retaining silent/nonselective
clusters in the denominator. Optionally contrast the fraction in a publicly
specified QC/responsiveness subset, with its own denominator.

The data connection is Siegle et al. (2021), *Survey of spiking in the mouse
visual system reveals functional hierarchy*, DOI
https://doi.org/10.1038/s41586-020-03171-x. Its Figure 1 describes the acquisition
and processing framework. This task uses original released data from that
program, but does not reproduce the paper's population-level hierarchical
finding or its figure-specific selection procedure.

The task's preferred frequency maximizes the largest single-direction condition
response, then folds opposite directions and compares preferred versus orthogonal
orientations. This is a **custom two-point descriptor**, not AllenSDK's
double-angle vector-strength `g_osi_dg`. The official implementation also chooses
preferred frequency differently:
https://allensdk.readthedocs.io/en/latest/_modules/allensdk/brain_observatory/ecephys/stimulus_analysis/drifting_gratings.html.
These distinctions are explicit in the public contract; there is no secret
"correct" QC denominator or required fraction.

## Original data and reproducibility

- DANDI `000021`, immutable published version `0.251116.2246`:
  https://doi.org/10.48324/dandi.000021/0.251116.2246.
- Exactly one NWB: `sub-707296975/sub-707296975_ses-721123822.nwb`,
  asset `224b57e5-c9a3-46ef-85db-966713f3ccbe`.
- Published size 1,736,516,600 bytes; SHA256
  `4e284295a1be5c6cca49df84fab52ad38b4749d2361b2edebeb676051cf09921`.
- Source bytes remain unchanged; original sorting, electrode mapping, unit IDs,
  spike times and stimulus-table IDs are retained. No synthetic primary data,
  new sorting, broad dandiset download or mutable-draft resolution is used.
- Exact source is verified and baked into the image at build time. Agent and
  verifier run offline. Tiny generated data are only authoring test fixtures.

DANDI declares CC-BY-4.0 but its description also references Allen Institute
terms, which include research/noncommercial restrictions. Both notices and
attribution are retained in the source manifest. Local research validation does
not resolve commercial use or public redistribution of the image/data.

## What is measured and verified

Unit-to-electrode identity is joined by original ID, not row position. Every
selected presentation and every VISp-unit×presentation integer count must be
accounted for. Rates use actual source durations and condition means weight
presentations equally. Preference ties, opposite-direction folding, zero-response
handling, strict OSI threshold and optional QC are public.

The verifier binds all source identities, counts, rates, condition means and
unit-level metrics, then recomputes the fractions. It does not accept merely
correlated OSIs, a broad aggregate answer band, unexplained exclusions, prose
keywords or altered IDs. Optional QC requires its source metric and baseline
count receipts; it cannot silently replace the primary denominator. Row/column
order and harmless numeric notation are not scientific tests.

## Scope and difficulty

This is an easy/method control pending later empirical model calibration, not
an established hard task. One mouse/session cannot support mouse-population
prevalence; recorded clusters are not automatically isolated single neurons.
Preference and optional responsiveness are selected using the same trials, so
the comparison is descriptive, not held-out tuning validation or evidence that
noise caused an inflated fraction. No desired direction or fraction is required.

Numerical/source validation, final container oracle results and remaining limits
are recorded separately in the dated repair receipt. They do not establish
scientific ground truth or frontier-model difficulty.
