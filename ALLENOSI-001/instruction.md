# Orientation-selective fraction in mouse V1 from Neuropixels drifting-grating responses (ALLENOSI-001)

## Scientific context

In the Allen Institute Visual Coding -- Neuropixels project (Siegle et al. 2021, *Nature*,
"Survey of spiking in the mouse visual system reveals functional hierarchy",
https://doi.org/10.1038/s41586-020-03171-x), head-fixed mice passively view a battery of visual
stimuli while Neuropixels probes record hundreds of neurons across the visual system. A **drifting
grating** block presents a full-field sinusoidal grating that drifts in one of 8 directions
(0-315 deg) at several temporal frequencies. A basic characterization of primary visual cortex
(**VISp**) is what fraction of its neurons are **orientation-selective** -- respond much more
strongly to one grating orientation than to the orthogonal one.

## Task

Using the NWB file for session **`sub-707296975/sub-707296975_ses-721123822.nwb`** from DANDI
dandiset **`000021`**, **report the fraction of VISp units that are orientation-selective (OSI
above threshold) in their responses to the drifting gratings.**

Fetch this one session's asset at runtime from the DANDI archive -- obtain its download/content
URL with the `DandiAPIClient` (`get_dandiset("000021", "draft").get_asset_by_path(...)`) and read
it (streaming the remote NWB, e.g. with `remfile`, avoids a multi-GB download); do not assume a
local copy.

Pinned analysis choices (use exactly these so the reported number is comparable):

- **Units / region.** Consider units localized to **VISp** (map each unit to its peak-channel
  electrode's brain-region `location`).
- **Stimulus.** Use the `drifting_gratings_presentations` interval table; drop blank sweeps (null
  orientation). Each grating has a `orientation` (drift direction, 0-315 deg in 45 deg steps) and a
  `temporal_frequency`.
- **Response.** For each unit and each presentation, take the mean firing rate over the
  presentation window (`start_time` to `stop_time`, ~2 s).
- **Tuning and OSI.** For each unit, take its **preferred temporal frequency** (the temporal
  frequency giving the largest response), and at that temporal frequency build the orientation
  tuning by folding the 8 drift directions onto 4 orientations (average each direction with its
  180 deg opposite). Define the **orientation selectivity index**
  **OSI = (R_pref - R_orth) / (R_pref + R_orth)**, where R_pref is the response at the preferred
  orientation and R_orth the response at the orthogonal (preferred + 90 deg) orientation.
- **Selective.** A unit is orientation-selective if **OSI > 0.5**.

Report the **fraction of VISp units that are orientation-selective**, i.e. the number of
orientation-selective units divided by the number of VISp units you analyze.

Standard implementation choices the brief leaves to the analyst (exactly which units enter the
denominator, how you establish that a unit genuinely responds to the gratings) should follow
common practice for characterizing single-unit tuning in a Neuropixels dataset -- report a number
you would stand behind as the orientation-selective fraction of VISp, stating only what your
analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `results.json` -- the headline result: `orientation_selective_fraction` (the fraction you would
  report), the number of VISp units total and the number you analyzed, the number selective, the
  OSI threshold, and the analysis parameters you used.
- `run_metadata.json` -- dandiset id, session, region, number of VISp units (total and analyzed),
  number of gratings presentations, OSI definition and threshold.
- `findings.md` -- a short written summary (a few sentences) stating the orientation-selective
  fraction of VISp and how reliable that estimate is. State only what your analysis actually
  supports.

## Failure handling

If the dandiset asset cannot be resolved or the session lacks the expected units / gratings data,
exit non-zero with `failed_precondition` and a non-empty reason, and still write a parseable
`run_metadata.json`, `results.json`, and `findings.md`.
