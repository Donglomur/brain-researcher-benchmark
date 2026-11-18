# Figure 5 fit-object export

This component connects already-produced Figure 5 fit objects and their source
dataframes to `fig5-coefficient-alignment-v1`. It does not fit a model or read a
pickle, NPZ, deposited data table, or scientific array. The source notebook's
cells 5, 7, 8 and 9 provide the dataframe/fit/table connection. The existing
diagnostic remains unchanged and computes both intercept interpretations.

`fit_export.export_panel` accepts dictionaries with exactly `activated` and
`suppressed` keys for models, source dataframes, complete cell rosters and
factor bindings. Each model must expose `.data`, `.coefs`, `.fixef`, `.ranef` as
dataframes. This is a narrow structural interface: missing tables, lists of
group tables and other historical APIs are refused. It is not a claim that a
particular pymer4 release generated the original results. All objects must be
trusted operator objects; accessing arbitrary Python properties is not a
sandbox or a guarantee against side effects.

The dataframe must contain `cell`, `basef`, `preceding`, `opto`. Every row is
retained with its zero-based position and original integer/text index label.
Repeated index labels and repeated baseline values across distinct cells are
preserved. Numeric NumPy integer/real scalars normalize to JSON numbers;
integer and string cell identities remain distinct. Noninteger real values must
round-trip exactly through binary64; wider finite values cannot silently round,
underflow to zero or become infinity tags. Unsupported identities or
missing/nonfinite modeled values refuse the whole export, without selecting
complete cases. Extra dataframe column names/dtypes are recorded, but their
values are outside the modeled projection and its digest. A digest of this
projection is not the identity of an original pickle or full dataframe.

Each explicit `factor_bindings` list pairs a native coefficient-table
`factor_level` with a typed source `cell_id`. It must bijectively cover the
complete supplied roster and every conditional/random table row. There is no
positional mapping, integer parsing of text factors, sorting to invent identity,
or inference from matching baseline values. These checks do not authenticate
the supplied map or establish that the roster is the original population.

Raw fixed, conditional and random tables retain their row/column labels, order,
dtypes and values. Ancillary NaN/infinity cells have explicit JSON states;
selected coefficients must be finite. Random effects come from `.ranef`, never
from subtraction. The narrow fixed-effect ABI requires `(Intercept)`, then
`basef`: notebook cell 9 reads `Estimate.iloc[0]` and `[1]`. This structural
restriction avoids silently reinterpreting a different native table layout.
It is not a new scientific inclusion rule. Conditional/random rows and columns
may be reordered because their identities are explicit.

`model.data` must match the supplied dataframe's modeled row/index projection.
That does not prove which observations R used after missing-value handling.
An exposed string `.formula` must match the source formula
`opto ~ 1 + basef + (1 + preceding|cell)` up to whitespace. If that attribute is
absent, formula identity remains explicitly unverified. A matching exposed
string also does not authenticate the actual historical fit.

The caller must declare `conditional_semantics="fixed_plus_random"` and supply
`runtime_record={"python": ..., "pymer4": ..., "lme4": ...}` with observed strings
or null for unknown versions. Neither declaration establishes runtime parity.
There is no automatic intercept correction. The exact existing diagnostic
source is hash checked before use; it returns both literal-notebook and
conditional-model branches and consistency residuals without a new tolerance.

Explicit positive engineering limits are required: `max_rows`, `max_cells`,
`max_columns`, `max_output_bytes`. The coefficient-row bound must cover the two
fixed-effect rows as well as native factor rows. Capacity refusal returns no
partial panel. These bounds are not scientific cohort sizes.

The result contains `exports` for the existing diagnostic, `lineage` for rows,
factor bindings and raw tables, and the unchanged `diagnostic` result. No
reproduction/improvement acceptance, original fit support, historical runtime,
or scientific readiness is established. Figure S13 refit/permutation policy,
animal/experiment joins, source population and a same-result improvement
criterion remain separate unresolved requirements.

## Changed-boundary controls

`test_fit_export.py` constructs only synthetic pandas dataframes and inert fit
containers whose `fit()` raises. It checks the native dataframe boundary,
identity preservation, unsupported layouts and diagnostic connection. The
previous 14-method diagnostic suite is not replayed.

After integration, the intended command is:

```sh
python3 -I -B benchmarks/paper/PAPER-FIND-ADD-015/implementations/fig5-keyed-fit-export-v1/test_fit_export.py
```

The default diagnostic path is the adjacent `fig5-coefficient-alignment-v1`
component. Private generated checks may supply `--alignment-source` with the
same exact pinned body and `--scratch-root` for their ten-byte corrupted-source
fixture. Shared CI enrollment and a compatible pinned pandas/NumPy environment
remain sole-integrator work; no installation or shared CI change is included.
