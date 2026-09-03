# Category representational geometry in ventral-temporal cortex (CATGEOM-001)

## Scientific context

Haxby et al. (2001, *Science* 293:2425, https://doi.org/10.1126/science.1063736)
showed that ventral-temporal (VT) cortex carries distributed information about object
category. Beyond decoding, a standard way to characterise this is **representational
similarity analysis**: summarise each category by its response pattern, build the
**representational dissimilarity matrix (RDM)** of the categories, and ask how strongly
the categories are separated in the neural representation. A compact summary of that
separation is the **category discriminability index** — how much larger the average
dissimilarity between *different* categories is than the average dissimilarity between
*repeats of the same* category.

## Task

Using the classic Haxby dataset (`nilearn.datasets.fetch_haxby`), **characterise the
representational geometry of the eight object categories in ventral-temporal cortex and
report the category discriminability index of the VT representational dissimilarity
matrix.**

Work with **`subject 3`** only. Fetch it with `fetch_haxby(subjects=[3])`; the returned
object gives the 4-D BOLD run (`func[0]`), the ventral-temporal mask (`mask_vt[0]`), and a
labels/session table (`session_target[0]`) that lists, for every volume, the stimulus
category (`labels`) and the acquisition run it belongs to (`chunks`).

Pin the analysis as follows so the number is comparable:

- **Samples:** every volume whose `labels` is one of the eight object categories
  (`bottle, cat, chair, face, house, scissors, scrambledpix, shoe`) — i.e. drop only
  the `rest` volumes.
- **Features:** the voxels inside `mask_vt`, extracted with `nilearn`'s `NiftiMasker`
  using per-run z-scored, detrended voxel time series
  (`standardize="zscore_sample"`, `detrend=True`, `t_r=2.5`).
- **Response patterns:** estimate each category's response pattern **in each acquisition
  run** as the mean of that category's volumes within that run.
- **Dissimilarity:** define the dissimilarity between two response patterns as
  **one minus their Pearson correlation coefficient**.
- **Discriminability index:** report

  ```
  (mean between-category dissimilarity - mean within-category dissimilarity)
  ------------------------------------------------------------------------
  (mean between-category dissimilarity + mean within-category dissimilarity)
  ```

  where a *within-category* dissimilarity compares two response patterns of the same
  category and a *between-category* dissimilarity compares patterns of two different
  categories.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `rsa_results.json` — at least a field `discriminability` (float in −1…1), the category
  discriminability index you obtained, plus `mean_between_category_dissimilarity`,
  `mean_within_category_dissimilarity`, `n_categories`, `n_runs`, and `n_voxels`.
- `run_metadata.json` — dataset id, subject, mask, and the preprocessing / pattern /
  dissimilarity choices you made.
- `findings.md` — a short written summary stating the category discriminability index for
  ventral-temporal cortex and how you estimated it. State only what your analysis actually
  supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write parseable `run_metadata.json`, `rsa_results.json`, and
`findings.md`.
