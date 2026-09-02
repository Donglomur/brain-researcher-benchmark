# Intravoxel-incoherent-motion perfusion fraction in a diffusion-MRI ROI (PERFDIFF-001)

## Scientific context

Intravoxel incoherent motion (IVIM; Le Bihan et al. 1988, *Radiology*,
https://doi.org/10.1148/radiology.168.2.3393671) models the diffusion-weighted
signal as a biexponential: a tissue-diffusion compartment (coefficient **D**) and a
fast pseudo-diffusion / microvascular-perfusion compartment (coefficient **D\***)
with **perfusion fraction f**. The perfusion fraction f is the headline IVIM
biomarker.

## Task

Using the IVIM dataset shipped by dipy (`dipy.data.fetch_ivim` /
`dipy.data.read_ivim` — a diffusion acquisition with **21 b-values from 0 to
1000 s/mm²**), **estimate the IVIM perfusion fraction f (and the diffusion
coefficient D and pseudo-diffusion coefficient D\*) in the ROI defined below.**

Reproducible ROI (as in dipy's IVIM example): **axial slice z = 33**, in-plane box
**x ∈ [90, 120), y ∈ [90, 120)**; restrict to tissue voxels (signal at b0 above
half the ROI median).

Fit the biexponential IVIM model with dipy's `IvimModel`. Standard implementation
details the method leaves to the analyst (initialisation, exactly how the
biexponential is solved, bounds) should follow common IVIM practice; the brief does
not spell them out.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `ivim_results.json` — the estimated **perfusion fraction f**, **D**, and **D\***
  for the ROI, and the ROI definition you used.
- `run_metadata.json` — dataset id, number of b-values, the ROI, and the fitting
  choices you made.
- `findings.md` — a short written summary reporting the ROI perfusion fraction f
  (and D, D\*) and how confident you are in it. State only what your analysis
  actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write a parseable `run_metadata.json`,
`ivim_results.json`, and `findings.md`.
