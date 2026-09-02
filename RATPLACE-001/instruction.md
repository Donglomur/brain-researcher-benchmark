# Hippocampal place-cell spatial information on a familiar track (RATPLACE-001)

## Scientific context

Hippocampal CA1 pyramidal cells are classically *place cells*: individual neurons fire
in restricted regions of an environment, and the amount of spatial detail a cell carries
is summarised by the **Skaggs spatial information** rate (Skaggs et al. 1993, *Advances
in Neural Information Processing Systems*; Skaggs, McNaughton, Gothard & Markus, 1996),

```
I  =  Σ_i  p_i · (λ_i / λ̄) · log2(λ_i / λ̄)      [bits per spike]
```

where the environment is discretised into bins `i`, `p_i` is the fraction of time the
animal occupied bin `i`, `λ_i` is the cell's firing rate in that bin, and `λ̄ = Σ_i p_i λ_i`
is its overall mean rate. It is the standard scalar readout of how spatially informative a
hippocampal neuron is, and the per-cell values are routinely averaged to describe a
population.

## Task

Using the NWB file for **Rat 1, session `ses-19980425T124500`** from DANDI dandiset
**`001754`** (`sub-Rat1/sub-Rat1_ses-19980425T124500_behavior+ecephys.nwb`), **compute the
Skaggs spatial information (bits/spike) for the recorded CA1 units and report the
population mean.**

Fetch the asset at runtime from the DANDI archive (e.g. `DandiAPIClient`); do not assume a
local copy. Restrict the analysis to the session's **Baseline rectangular-track** condition
(the epochs whose `session_type` is `BL`), and to **running** periods only (compute the
animal's speed from the tracked position and drop samples below a low running threshold, a
few px/s, so that stationary periods do not dominate the occupancy). Build each cell's
firing-rate map over a **4 × 5 grid of 20 spatial bins** spanning the range of occupied
positions, using the matching occupancy map for `p_i`. Analyse the **CA1 pyramidal units**
— the recording targets area CA1; keep well-sampled putative principal cells (a minimum
spike count on the track during running and a mean running rate below ~5 Hz, which excludes
the few fast-spiking interneurons).

Standard implementation choices the method leaves to the analyst (the exact running-speed
cutoff within a sensible range, the smoothing of the speed trace, how spikes are assigned
to position samples, minimum-spike and rate cutoffs for including a unit) should follow
common practice; the brief does not spell them out.

Report, in plain terms, **the mean CA1 place-cell spatial information for this track and how
strong the spatial coding is** — stating only what your analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `spatial_information.csv` — one row per analysed CA1 unit:
  `unit_index, tetrode, cluster_id, n_spikes, mean_rate_hz, spatial_information_bits_per_spike`.
- `results.json` — the headline result: the **population mean** spatial information you would
  report for these CA1 units (`mean_spatial_information_bits_per_spike`), `n_units`, and the
  binning / running / selection parameters you used.
- `run_metadata.json` — dandiset id, session, epoch(s) used, n units, grid, running threshold.
- `findings.md` — a short written summary (a few sentences) stating the mean CA1 place-cell
  spatial information on this track and how strong / reliable the spatial coding is. State
  only what your analysis actually supports.

## Failure handling

If the dandiset asset cannot be resolved or the session lacks the expected position/units
data, exit non-zero with `failed_precondition` and a non-empty reason, and still write a
parseable `run_metadata.json`, `results.json`, and `findings.md`.
