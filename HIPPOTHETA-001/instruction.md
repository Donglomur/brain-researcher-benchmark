# Locomotion-conditioned and mixed-session spectra of a fixed recorded channel

This is a custom method control using original mouse electrophysiology from
[Huszár et al. (2022)](https://doi.org/10.1038/s41593-022-01138-x),
archived in [DANDI 000552, version 0.230630.2304](https://doi.org/10.48324/dandi.000552/0.230630.2304).
It is not a reproduction of the paper's birthdate/connectivity finding. The
paper's theta-cycle method used 6–12 Hz filtering/Hilbert analysis; here the
specified 6–10 Hz Welch peak is a different, explicitly defined measurement.

Estimate both the **locomotion-conditioned** and **whole-recording** spectra and
their 6–10 Hz peaks for the fixed channel below. Report the observed difference
without requiring either condition to be faster or slower. Do not call the
whole-recording estimate REM-specific or treat a band maximum as proof of theta.

## Offline original data and scope

Two complete source files are baked into `/app/source/`:

- `sub-e15-13f1/sub-e15-13f1_ses-e15-13f1-220117-raw_ecephys.nwb`
- `sub-e15-13f1/sub-e15-13f1_ses-e15-13f1-220117_behavior+ecephys.nwb`

`/app/source/source_manifest.json` gives exact published asset IDs, sizes, SHA256,
object versions, attribution and limitations. Do not fetch other data. These are
released processed LFP/position recordings, not untouched instrument signals.

Read LFP at `/processing/ecephys/LFP/ElectricalSeriesLFP`: 31,878,000 samples,
128 columns, 1250 Hz, relative start 0 seconds. Fix **column 0**, mapped through
its `electrodes` DynamicTableRegion to electrode-table row/id **0**, channel name
`1`. Convert integer counts to volts using the data's conversion and offset
(`1.95e-7 V/count`, offset 0). Do not select a different channel by inspecting
power. Every released electrode location is `unknown`; report this channel's
location as unknown, not anatomically confirmed CA1 or a particular layer.

Read original x/y position and timestamps from
`/processing/behavior/SubjectPosition/SpatialSeries`. Position is in cm,
timestamps in seconds. Use the original relative recording seconds. The two
files' calendar/reference dates conflict (2011-08-18 versus 2022-01-17); retain
and disclose this discrepancy and **do not** align by subtracting those dates.
Common relative timing is an inherited upstream assumption supported by paired
session identity, original converter timestamps and duration metadata, not an
independently verified synchronization result.

## Public numerical contract

`/app/method_contract.json` specifies exact schemas, units, conventions and
numerical tolerances. Implement that contract; library choice and row ordering
are not scientific requirements. Use float64 intermediate computations.

1. Require finite, strictly increasing original behavior timestamps. Let `dt0`
   be their median adjacent difference. Split finite-position support into
   blocks at each nonfinite x/y row or original adjacent time gap greater than
   `1.5*dt0`. Never interpolate missing paths, sort timestamps or smooth across
   these boundaries.
2. Within each block, smooth each x/y coordinate at each original timestamp
   with normalized weights `exp(-0.5*((t_j-t_i)/0.25)^2)` over original samples
   satisfying `abs(t_j-t_i)<=1.0 s`. A smoothed point is supported only if its
   complete ±1-second interval lies inside the block. This is a timestamp-based
   kernel, not a fixed-index filter or invented regularly sampled trajectory.
3. Use the three-point nonuniform central derivative at each point, requiring
   that it and both neighboring smoothed points have full support. For adjacent
   spacings `h0=t_i-t_(i-1)` and `h1=t_(i+1)-t_i`, the coefficients are
   `-h1/(h0*(h0+h1))`, `(h1-h0)/(h0*h1)`, `h0/(h1*(h0+h1))`.
   Speed is the Euclidean norm of the x/y derivatives, in cm/s. Unsupported
   quantities remain null/blank, not zero.
4. Select elementary `[t_i,t_(i+1))` intervals only when **both** endpoint speeds
   are supported and strictly greater than **5 cm/s**. Merge only adjacent
   selected intervals within the same block. For each resulting `[u,v)` bout,
   set `a=ceil((u-lfp_start)*fs)`, `b=floor((v-lfp_start)*fs)`; require
   `0<=a<=b<=N`, without silent clipping. This conservatively retains the full
   time support of each included sample. Report short bouts as well as retained
   bouts. Do not apply an undisclosed minimum total locomotion duration.
5. Each complete spectral window contains **5000 samples (4 s)**, with hop
   **2500 (50% overlap)**. Locomotion starts are `a+2500*k` with end `<=b`
   separately inside each bout. Do not concatenate bouts, pad short bouts or
   bridge gaps. Whole-recording starts are `2500*k` with end `<=N`.
   The locomotion spectrum therefore describes sustained, sufficiently long
   above-threshold support, not every moment of above-threshold movement.
   Report the unique support used, alongside all selected and discarded bouts.
6. Remove each window's arithmetic mean, multiply by periodic Hann
   `0.5-0.5*cos(2*pi*n/5000)`, and use an NFFT of 5000. One-sided density is
   `abs(rfft(x*hann))^2/(fs*sum(hann^2))`, doubling bins other than DC/Nyquist.
   Average complete-window periodograms with equal **window**, not bout,
   weights. Report both complete 0–625 Hz spectra in V²/Hz. Window theta power
   is the trapezoidal integral on the inclusive 6–10 Hz grid, with half-weight
   endpoint bins; also report each window's pre-detrend mean and mean-square.
7. Within the inclusive **6–10 Hz** band, take the largest density bin; break
   exact ties toward lower frequency. For an interior-band maximum with nonzero
   curvature, use `delta=0.5*(Pleft-Pright)/(Pleft-2*Pcenter+Pright)` and
   `peak=fgrid+0.25*delta`. At a band edge or zero curvature use the grid peak.
   Report grid and interpolated peaks, exact tied-bin count and band-edge flag.
   Do not alter the channel, band or processing to obtain a more appealing peak.

No additional baseline normalization, artifact censoring, filtering, clipping
or sleep classification is part of this fixed method. Real artifacts and
upstream processing limitations therefore remain relevant to interpretation.

## Outputs

Write these eight files to `${OUTPUT_DIR}` (default `/app/output`). Exact field
names and structured schemas are in the public method contract:

- `behavior.csv`: every source row, original time/x/y, valid support/block,
  smoothed coordinates, speed and outgoing locomotion-interval flag.
- `blocks.csv`: every finite-position block, source row/time bounds and counts
  of supported smoothed/speed points, including blocks too short to contribute.
- `bouts.csv`: every selected locomotion bout, row/time/sample bounds, complete
  window count and retained/short status.
- `windows.csv`: every contributing window for both conditions, its identity,
  sample bounds, raw mean/mean-square in volts/volts² and theta-band power.
- `spectrum.csv`: both full frequency grids and density values, keyed by condition.
- `results.json`: numerical summaries, both peaks, window/bout/support counts,
  durations and the signed locomotion-minus-whole peak difference.
- `run_metadata.json`: exact source and method identities, channel/units/clock
  provenance, and the disclosed anatomical and synchronization limitations.
- `findings.md`: a short interpretation with the measured estimates, sampling
  support and limitations. No particular wording or effect direction is required.

CSV row order is flexible; identifiers must remain unique and complete. Preserve
scientific precision; unsupported numeric fields must be blank, not NaN/Infinity
or fabricated zeros. Harmless extra explanatory JSON fields are allowed outside
closed source/method identity structures. Software version strings are provenance,
not a correctness gate.

## Validation and failure handling

The verifier checks source-bound values, complete membership and internal
arithmetic for both conditions. Scoring is **all-or-nothing**, not proportional
partial credit. A plausible peak, correlated spectral shape or correct prose is
insufficient. Alternative code implementing the declared estimator is acceptable.

Fail nonzero with a nonempty reason in `results.json`, `run_metadata.json` and
`findings.md` if source identity/units/clock support fail, timestamps are invalid,
LFP values are nonfinite, or no complete locomotion window exists. A failed
precondition is not a successful scientific output and does not receive reward.
