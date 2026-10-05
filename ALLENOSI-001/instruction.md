# Descriptive two-point orientation selectivity in one VISp session

Compute the fraction of all recorded VISp clusters with the two-point OSI defined
below greater than 0.5. This is a single-session method case using original
Allen Visual Coding data, not a population prevalence estimate or a reproduction
of the paper's hierarchy finding.

## Data and scope

The original NWB and checksum manifest are under `/app/data/allenosi`:
`sub-707296975_ses-721123822.nwb`, DANDI `000021`, immutable version
`0.251116.2246`, https://doi.org/10.48324/dandi.000021/0.251116.2246.
Verify the manifest and source hashes. Runtime is offline; no download, new spike
sorting, waveform processing or original-data modification is needed.
The public recipe/template is `/app/method_contract.json`.

The associated study is Siegle et al. (2021),
https://doi.org/10.1038/s41586-020-03171-x. The task's pairwise OSI and preferred
frequency rule are custom descriptive choices. They are **not** the AllenSDK
double-angle vector-strength `g_osi_dg` or the paper's figure-specific selection.
DANDI's CC-BY-4.0 notice and the additional Allen research/noncommercial terms
are retained in the manifest; this task does not establish redistribution rights.

## Public calculation

1. Join each original unit's `peak_channel_id` to the electrode table's **id**,
   not its row number. Include every unit whose resulting `location` is exactly
   `VISp`, regardless of unit quality or responsiveness. Retain original IDs.
2. Use the original `drifting_gratings_presentations` table, excluding blank
   orientations (NaN in this source). A nonblank orientation with missing,
   infinite or nonpositive temporal frequency is an error, not another blank.
   Preserve selected presentation IDs and actual start/stop times. Check the
   complete 8-direction grid, 0 through 315 degrees in 45-degree steps, and every
   direction×temporal-frequency condition. Missing conditions are errors, not
   zero responses. Do not tune a minimum number of units or trials.
3. Count each unit's spikes in half-open `[start_time,stop_time)` intervals.
   Divide counts by each presentation's actual duration. Compute the arithmetic
   mean of presentation rates for each direction×frequency condition; do not
   substitute pooled counts divided by pooled duration.
4. For each unit, choose the temporal frequency with the largest **single-direction
   condition mean**; exact ties select the lowest frequency. At that frequency,
   average each direction with its 180-degree opposite, with equal weights, to
   obtain four orientation rates at 0, 45, 90 and 135 degrees. Choose the largest;
   exact ties select the lowest orientation. The orthogonal orientation is
   `(preferred+90) mod 180`.
5. Compute `OSI=(R_pref-R_orth)/(R_pref+R_orth)` and classify strictly `OSI>0.5`.
   If the denominator is zero, emit `osi=0,osi_defined=false,selective=false` and
   retain that unit in the primary denominator. Any preferred value in this case
   is a computational tie convention, not evidence of a biological preference.
6. Divide the number classified selective by **all** source VISp units. Use
   unrounded counts/source durations for ties and classifications, not rounded
   output rates. If there are no VISp units or required source support is missing,
   report a failed precondition rather than inventing a result.

Source inspection found 30 blank presentations and 598 nonblank presentations;
conditions have 14 or 15 repeats, not an assumed balanced 15 each. Selected
contrast is 0.8. The five source invalid-time intervals overlap neither selected
stimulus windows nor their 0.5-second baseline windows; no additional exclusions
are introduced. Original recorded durations are slightly longer than 2 seconds.

You may additionally report a separately denominated QC/responsiveness
sensitivity analysis. Its public gate is finite original `isi_violations<0.5`,
`amplitude_cutoff<0.1`, `presence_ratio>0.9`, plus peak condition rate `>2 Hz`
and `>mean_baseline_rate+1 Hz`. Baseline counts use `[start-0.5,start)` for each
selected presentation, and baseline rate is their mean divided by 0.5 seconds.
Missing QC metrics remain blank and fail this optional gate only. A zero
QC-responsive denominator gives a JSON-null fraction, not zero. Never replace
the primary all-VISp denominator with this subset.

## Outputs

Write to `${OUTPUT_DIR}` (default `/app/output`). CSV row/column order is free;
extra descriptive columns are allowed. Required identities must appear exactly
once. Retain sufficient numerical precision.

- `presentations.csv`: `presentation_id,start_time,stop_time,duration_seconds,`
  `direction,temporal_frequency` for every selected original presentation.
- `trial_responses.csv`: `unit_id,presentation_id,spike_count,rate_hz` for every
  VISp-unit×selected-presentation combination, including zero counts.
- `condition_means.csv`: `unit_id,direction,temporal_frequency,n_presentations,`
  `mean_rate_hz` for every unit×condition.
- `units.csv`: `unit_id,peak_channel_id,preferred_temporal_frequency,`
  `preferred_orientation,r_pref_hz,r_orth_hz,peak_rate_hz,osi,osi_defined,selective`.
- `results.json`: `status:"ok"`, `pipeline_id:"allen-visp-two-point-osi-v2"`,
  `orientation_selective_fraction,n_visp_units_total,n_visp_units_analyzed,`
  `n_orientation_selective,n_osi_undefined,osi_threshold`. Both VISp counts use
  the complete primary denominator; threshold is 0.5.
- `run_metadata.json`: the public template plus `status:"ok"`, `n_units_total,`
  `n_visp_units_total,n_original_presentations,n_blank_presentations,`
  `n_gratings_presentations,directions,temporal_frequencies,include_qc`.
- `findings.md`: a brief numerical summary, denominator and relevant limitations.

If reporting QC sensitivity, also provide both:

- `baseline_counts.csv`: `unit_id,presentation_id,spike_count`, covering every
  primary unit×selected presentation, not only the retained QC subset.
- `qc_sensitivity.csv`: `unit_id,isi_violations,amplitude_cutoff,presence_ratio,`
  `qc_metrics_complete,qc_pass,baseline_rate_hz,responsive,in_qc_responsive`,
  covering all primary units. Add `n_qc_responsive_units,`
  `n_qc_responsive_orientation_selective,qc_responsive_selective_fraction` to
  results and set metadata `include_qc=true`. Otherwise set it false. Supplying
  any of these named QC artifacts or result keys invokes the complete QC contract.

The verifier checks full source-keyed counts, tables and recomputed aggregates,
not prose keywords or a desired fraction. IDs/counts/categories are exact;
rates, OSI and fractions use atol=rtol=1e-6. Original timestamps and durations
use absolute tolerance 1e-9 seconds with no relative component. Scoring is
all-or-nothing. Authoring-only private arrays are not participant requirements.

Recorded clusters are not automatically isolated single neurons. Preference and
optional responsiveness are selected on these same trials, so this is descriptive
rather than held-out tuning validation. A QC-related change in fraction does not
establish that noise caused inflation. Do not generalize one session to a mouse
population or describe this custom recipe as AllenSDK's gOSI.

On source or required-support failure, exit nonzero and still write parseable
results/metadata with `status:"failed_precondition"`, a nonempty reason and
findings. Do not fabricate missing units, trials or conditions.
