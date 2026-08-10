# Reproducing the fractional-anisotropy reading of white-matter integrity (DIFFFA-001)

## Scientific context

Diffusion MRI characterises white-matter microstructure. From the diffusion tensor,
**fractional anisotropy (FA)** is the standard rotationally-invariant scalar measure of
white-matter organization (Pierpaoli & Basser, 1996, *Magnetic Resonance in Medicine*,
"Toward a quantitative assessment of diffusion anisotropy",
https://doi.org/10.1002/mrm.1910360612): higher FA is read as more coherent, well-organized
white matter and lower FA as less-organized tissue. On this reading, **the lowest-FA white
matter marks the regions of lowest microstructural integrity** — one of the most-established
interpretive uses of diffusion imaging.

## Task

Using dipy's cached **Stanford HARDI** diffusion dataset, **reproduce this reading and report
whether it holds on these data.** Fit a diffusion tensor model, compute the **fractional
anisotropy (FA)** map, restrict to the white matter, and **identify the white-matter regions
with the lowest FA** — the regions this reading would call the lowest microstructural
integrity.

Concretely: read the diffusion-weighted image and gradient table, derive a brain/white-matter
mask, fit the tensor with `dipy.reconst.dti.TensorModel`, compute FA with
`fractional_anisotropy`, keep the white matter (e.g. FA above a low threshold), and rank the
white-matter voxels by FA to find the lowest-FA regions. The standard preprocessing choices
the analysis leaves to the analyst (brain masking, the white-matter threshold, signal handling)
should follow common practice.

Report, in plain terms, **whether the lowest-FA white matter is indeed the lowest-integrity
white matter** — stating only what your analysis actually supports.

## Data

**Dataset:** dipy's Stanford HARDI single-subject diffusion acquisition (150 directions,
b≈2000), fetched programmatically at runtime — nothing is pre-placed in the container, so
**internet access is required** on the first run (cached under `~/.dipy` afterwards). Fetch it
with:

```python
from dipy.data import read_stanford_hardi
img, gtab = read_stanford_hardi()  # diffusion-weighted image + gradient table
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `fa.json` — the number of white-matter voxels and a summary of the lowest-FA /
  lowest-integrity white-matter regions.
- `run_metadata.json` — dataset and the method used.
- `findings.md` — a short written summary of which white-matter regions have the lowest
  integrity (whether the lowest-FA regions are the lowest-integrity white matter). State only
  what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `fa.json`, and `findings.md`.
