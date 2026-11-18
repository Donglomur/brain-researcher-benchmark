# Complete decoded observations for the OFC TCA component

This operator-side projection supplies the five-event input structure consumed by
the existing `tensor-source-analysis/ofc_tca_inputs.py`. The earlier four-event
projection omits `Opt` and cannot supply that transformation. This component
preserves `COFF`, `SON`, `SOFF`, `Rew` and `Opt` for every source-eligible unit,
without selecting trials, cropping columns, normalizing, averaging or fitting.
It does not establish paper reproduction, improvement or benchmark readiness.

The consumed fields and source gates come from the retained author
[`makeTensor_TCA.m`](https://github.com/constantinoplelab/published/blob/b7b68ca8c107d8ce4a061e16da214307f175c3e5/OFC_cognitiveStrategies/analysis/Electrophysiology/makeTensor_TCA.m).
Exact local source and consumer identities are in `SOURCE_PROVENANCE.json`.
The source-exclusion rule remains fewer than five units or fewer than four block
transitions. Excluded sessions retain supplied animal/session/cohort and every
unit identity; their unused event fields are not fabricated. Eligibility and
original cohort identity still require independent source qualification.

`project_decoded(decoded, identity=..., source_binding=...,
max_projected_elements=...)` accepts the unsqueezed structured-array representation
of `S` and `SU` used by `scipy.io.loadmat(struct_as_record=True,
squeeze_me=False)`. The function itself has no file reader. The source archive,
MAT version, decompression bounds, source authentication and actual decoding
must be handled by a separately admitted operator. It does not call `loadmat`
on real data or claim compatibility with uninspected HDF5/MAT-v7.3 objects.

The explicit `identity` is exactly `session_id`, `animal_id` and `cohort`
(`Expert` or `Naive`). The external `source_binding` contains a `source_sha256`
and `decoder_id`. Their syntax is checked, but this is not a source-authentication
receipt. Identities are never inferred from filenames, and the returned binding
is marked `external_not_verified_by_projection`.

For a source-eligible session, the output retains complete `S.Block` and `S.vios`,
all unit identifiers, the first unit's full `xvec.COFF`, and all five full
trial-by-time `hmat` matrices. The author uses the first unit's COFF axis for
every event; other axes are neither copied into that role nor invented. MATLAB
row/column vectors preserve their linear order. The projection refuses
nonvector `SU`, squeezed/ragged/complex structures, duplicate unit identifiers,
extended-precision values and missing `Opt`. Integer unit identifiers never pass
through binary64. Logical violation masks become their exact zero/one values.
NaN, infinities and signed zero in event matrices are preserved for the existing
transform's explicit missingness and nonfinite policy.

The returned `session` can be passed to the existing `prepare_session`. Complete
cohort use still requires the existing `prepare_cohort` and its externally
authenticated ordered roster. This projection cannot prove that the declared
191 Expert or 96 Naive sessions are the original eligible source cohorts. It
does not emit a smaller substitute cohort or a concatenated partial tensor.

`max_projected_elements` limits copied primitive elements. It is not a bound on
previous decoder allocation or Python-object memory; actual memory and runtime
admission remain separate. NumPy is a production dependency; SciPy is used only
by the generated test fixtures. No installation is performed.

The 13 maintained controls exercise generated MAT-v5 round trips, the actual
existing tensor transform, all five events, uncropped/violation observations,
row/column vector order, large integer identities, source exclusions, missing
events, shape/type failures, nonfinite preservation, copy limits and no mutation.
Run from the repository root after separately provisioning dependencies:

```sh
OFC_TCA_INPUTS_PATH=benchmarks/paper/PAPER-ROOT-ADD-018/implementations/tensor-source-analysis/ofc_tca_inputs.py \
python3 -I -B benchmarks/paper/PAPER-ROOT-ADD-018/implementations/tca-decoded-projection-v1/test_tca_decoded_projection.py
```

Private construction ran the initial 12 tests and then the added
extended-precision refusal test, both through the shared generated-test pool.
No authentic observations, model fits, numerical paper results or full native
MATLAB-equivalence checks were run. Public CI enrollment is an integration step.

This is operator-only source. It does not change what either paper/data or
paper/data/author-code participants receive. The original primary comparisons,
TCA decomposition and rank/restart/coordinate interpretation, source numerical
parity, hLDS producers, S8 metric, expected results and same-primary improvement
criterion remain unresolved.
