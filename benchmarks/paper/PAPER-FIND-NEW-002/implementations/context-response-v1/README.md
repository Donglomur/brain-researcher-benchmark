# Released Figure 3 H/I response arithmetic

This component reconstructs the numerical responses used by the released
`Figure3_panelGI.ipynb`, cells 8–9 (zero-based). It extends the empirical source
support beyond the existing Figure 2C example. It does not establish complete
primary reproduction, a new benchmark score, or improvement over the paper.

The operator supplies the five numeric condition matrices for each of `expt1`,
`expt2`, and `expt3`, plus the original ordered stimulated-cell selections of
9, 13, and 10 cells. For every selected cell, it subtracts visual-only activity
from the corresponding visual-plus-opto condition, then averages frames
`[125:128]`. Opto-only uses that same window without visual subtraction. The
three released revision matrices retain all 108 rows and 200 frames; these
already-derived conditions use `[123:126]` directly. The output retains all
140 rows, their original cell IDs or revision-row IDs, and their exact windows.

The source plotting code pools cells. `pooled_cell_means` preserves that
weighting; separately named namespace means are diagnostics. The 108 revision
rows do not imply one new experiment or 108 biological replicates. Their
animal/session provenance remains unresolved. No inferential test is added.

Panel H/I's source function does **not** use `nan_to_num`; Panel G's trace
preparation does. Undefined H/I responses become explicit JSON `null` values
with a nonfinite status. They are never replaced by zero or omitted. An
undefined response leaves its pooled source mean undefined. Finite arithmetic
uses float64, so bitwise parity with unspecified original array dtypes is not
claimed. Original unselected cells and frames are not used to invent exclusions.

`reconstruct_responses(experiments, revision)` accepts in-memory numeric
arrays. It intentionally does not open NPZ archives or enable pickle. Authentic
source-member verification and safe conversion of object-typed selections must
precede future operator use. The API's shape/count checks cannot authenticate
input provenance. The original arrays were not read or run in this construction.

The source dataset's large Figure 3 archive includes volumetric Panel BF data.
This component needs only the 18 named GI experiment operands (15 condition
matrices and three selections) and three revision matrices listed in
`SOURCE_EVIDENCE.json`; it does not require decoding BF or J arrays. This is an
operand selection for H/I arithmetic, not permission to omit other controls
required by the complete paper task.

The final paper's 300 ms response definition, archive/final figure crosswalk,
per-experiment clocks, upstream normalization, animal/session joins, complete
primary controls, and a meaningful ordered same-result improvement comparison
remain unresolved. Source frame indices are not relabeled as 300 ms.

Generated controls can be run with NumPy already installed:

```sh
python3 -B -m unittest discover -s . -p 'test_context_response.py'
```

Maintainers must enroll this component and command in the existing integrity
registry before publication. The task's canonical outcome/scoring/admission
contracts remain unchanged.
