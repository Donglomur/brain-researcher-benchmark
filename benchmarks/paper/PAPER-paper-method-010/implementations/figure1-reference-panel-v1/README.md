# Original-format Figure 1 reference panel admission

The existing scorer implements the Figure 1 metrics but has no reader for the
author's complete `sim_performance.npz` result artifact. This operator-only
component admits that format without fitting an algorithm or resampling a
metric. It reuses the pinned existing scorer's aggregation implementation.

The pinned author's `embedding_performance` writes two float64 C-order arrays:
`scores_all` with shape `[10, 2, 8, 5]` and `embs_all` with shape
`[10, 7, 6000, 1]`. The score axes contain contamination, correct triplets,
seven plotted methods and a sampled random companion. The coordinates retain
all seven methods and every original neuron. The random companion is not an
eighth fitted method. Its realized scores remain separate from the analytical
guide lines. These layouts are grounded in the [pinned producer](https://github.com/MouseLand/rastermap/blob/b37644ea52c4cd81f143a9c2cec90286ffd61c49/paper/simulations.py)
and [plot consumer](https://github.com/MouseLand/rastermap/blob/b37644ea52c4cd81f143a9c2cec90286ffd61c49/paper/fig1.py).

The caller supplies an independently acquired artifact and its SHA-256. The
reader bounds archive and member reads, requires exactly the two original
members, validates primitive NPY geometry before allocating array views, and
rejects missing axes, extra members, objects, nonfinite values, altered source
precision and scores outside `[0, 1]`. It does not unpickle or extract files.
Complete tied coordinates remain valid, matching the existing metric policy.

The report preserves the complete score panel and its source mean/SEM, and
binds all 70 coordinate vectors by canonical little-endian float64 hashes.
Hashes are commitments to coordinate bytes; they are not a data-use verifier.
The coordinates themselves are retained in the input artifact, not published
in the report. Reports belong to operator evidence and must not be repeatedly
returned to a participant before a feedback policy is frozen.

```sh
python3 reference_panel.py /absolute/operator/sim_performance.npz \
  --expected-sha256 OPERATOR_PIN --output /absolute/operator/reference-report.json
```

The output is created exclusively and existing reports are not overwritten.
The default aggregation source is the sibling `figure1-scorer-v1/scorer.py`.
Its exact byte pin is checked before those same bytes are loaded. The API's
optional `scorer_path` supports private construction tests against that exact
existing source; a different implementation is refused.

**This does not authenticate a published result.** A fresh rerun can have the
same schema, so all publication, source-execution, RNG-recovery, reproduction
and improvement flags remain false, with `paper_win` null. Neither the original
artifact nor original simulation data were acquired or read for this change.
The OSF metadata endpoint was inaccessible in the browser attempt. No numeric
paper targets, tolerances, original post-fit RNG state, meaningful effects,
joint superiority rule or information-condition budget is recovered here.

Generated controls cover complete geometry, the source SEM, random/analytical
distinction, missing axes, stale pins, malformed archives/NPY headers,
nonfinite values, objects, float32/Fortran substitutions and immutable reports.
Run them through the shared bounded test pool; inside the pool the command is:

```sh
python3 -I -B tests/test_reference_panel.py
```

Private tests may set `RASTERMAP_REVIEW_SCORER` to the existing read-only scorer;
its hard pin remains enforced. Dependencies are Python 3.10+ and existing
NumPy. No environment installation or native author fit is included. New CI
component enrollment is an integration requirement, not claimed by these
private files.
