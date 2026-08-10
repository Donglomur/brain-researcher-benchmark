# White-matter integrity from diffusion MRI (DIFFFA-001)

## Scientific context

Diffusion MRI characterises white-matter microstructure. From the diffusion tensor, **fractional
anisotropy (FA)** is the standard rotationally-invariant scalar measure of white-matter organization —
higher FA is conventionally read as more coherent/organized white matter, lower FA as less.

## Task

Using dipy's cached **Stanford HARDI** diffusion dataset, fit a diffusion tensor model, compute the
**fractional anisotropy (FA)** map over the white matter, and **identify the white-matter regions with
the lowest microstructural integrity** (the lowest-FA white matter).

Report, in plain terms, **which white-matter regions have the lowest integrity**.

## Data

**Dataset:** dipy's Stanford HARDI single-subject diffusion acquisition (150 directions, b≈2000),
fetched programmatically at runtime — nothing is pre-placed in the container, so **internet access is
required** on the first run (cached under `~/.dipy` afterwards). Fetch it with:

```python
from dipy.data import read_stanford_hardi
img, gtab = read_stanford_hardi() # diffusion-weighted image + gradient table
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `fa.json` — the number of white-matter voxels and a summary of the lowest-FA / lowest-integrity
 white-matter regions your analysis supports.
- `run_metadata.json` — dataset and the method used.
- `findings.md` — a short written summary of which white-matter regions have the lowest integrity.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `fa.json`, and `findings.md`.
