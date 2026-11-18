# Author reference-table key adapter

This module provides exact author key operations on **already-typed pandas DataFrames**, followed by explicit strict admission checks. It performs no file reading, scientific scoring, value normalization, fitting, or genuine-data run. The four published CSVs have a separately accepted structural inventory; that inventory is not reread or reinterpreted here.

## Authenticated source behavior

The retained `evaluation/conversion_accuracy/plot_figure.py` is 11,647 bytes, SHA256 `638811c8038d1c0d43e03577d7ddd2243eb2bf9c5b061412288add7e51fd8566`, Git blob `27f1255c19db57380877250badddc38f64148578`, exactly matching original-release commit `edbff02edd6a08d3c6c829af45a957fd14bdc460`. Source URL: https://github.com/KamitaniLab/InterSiteNeuralCodeConversion/blob/edbff02edd6a08d3c6c829af45a957fd14bdc460/evaluation/conversion_accuracy/plot_figure.py

| Reference input | Subject conversion | Index conversion before identifier |
| --- | --- | --- |
| Pattern ceiling | `.str.replace('-', '')` | `Series.astype(int)`, then `.values.astype(str)` |
| Pattern threshold | None | `Series.astype(int)`, then `.values.astype(str)` |
| Profile ceiling | None | `.values.astype(str)` only |
| Profile threshold | None | `.values.astype(str)` only |

Lines 23–44 concatenate Subject + ROI + resulting index text **without a separator**. No general whitespace trimming, case folding, subject stringification or profile integer conversion appears in these reference functions. Pattern floating values use the author's actual integer cast, including truncation; object text such as `7.0` is not silently parsed through `int(float(...))`. Profile references retain dtype-sensitive spelling, so integer 1, float 1.0 and text `001` need not share identifiers.

Author reference loaders first call `pd.read_csv` with defaults. This adapter requires the caller's already-reviewed typed DataFrames; it does not reconstruct CSV inference or claim the author's unpinned pandas/NumPy environment. Generated parity records identify the locally installed package versions. The source prediction merges use Target instead of Subject and integer-cast both pattern Image index and profile Vox_idx (lines 48–58). Those prediction conversions are documented here but are not implemented by this reference-only module.

Author reference joins are ceiling-left joins to threshold identifiers (lines 33/44), with `rsuffix='_'`. The adapter does not replay permissive left-join behavior. Its output is a strict one-to-one key/row-position alignment. Author filtering, `nan_to_num`, clipping and averaging at lines 62 onward are excluded.

## Stricter adapter admission policy

The following are deliberate adapter safeguards, not claims about the author: refuse absent or duplicate columns; empty tables; missing, nontext or oversized subject/ROI components; unsupported, boolean, nonnumeric or nonfinite feature scalars; nonnumeric/nonfinite reference values; unsafe native integer overflow; empty transformed subjects; duplicate canonical keys; missing/extra keys between tables; and delimiter-free identifier collisions within or across tables. No value is replaced or dropped. Numeric value columns must already expose a NumPy integer/unsigned/float dtype. Inputs are copied before author transformations. Reference row positions preserve ceiling order and map threshold order explicitly. Maximum table length is 1,000,000 rows and key text length 1,024 characters per component; these are engineering envelopes.

Collision checks compare the transformed component tuples as well as the exact delimiter-free author identifier. A subject/ROI split such as (`ab`, `c`) versus (`a`, `bc`) must not silently match. Author-approved pattern subject/index transformations that create the same component tuple across the two roles are legitimate matches; repeated canonical keys within one table are refused.

## Portable interface and generated controls

`reference_keys(frame, axis='pattern'|'profile', role='ceiling'|'threshold')` returns frozen `ReferenceKey` records, including exact identifier, transformed components and original zero-based row position. `align_reference_keys(ceiling, threshold, axis=...)` returns frozen `ReferencePair` records with both row positions. It does not return a scientific score or repair dtypes.

Run the sibling `test_reference_key_adapter.py` using an existing Python environment with pandas and NumPy. Tests use RAM-generated DataFrames and the separately pinned verbatim author reference-loader fragment. `pd.read_csv` is mocked only in that fragment; no CSV files are read. Valid generated cases are compared with the actual author expressions and join result, and strict refusals are tested separately. The fragment preserves the upstream MIT notice.

## Integration seam and remaining qualification

Place this document with the module, test script and author fragment in `implementations/reference-key-adapter-v1/` (see the external integration map). The existing evaluator's `load_ceiling_tables` currently strips hyphens in both roles and both axes, parses pattern features as float, and integer-normalizes profile features. Those operations differ from the exact reference source above. This packet does not silently replace that function or alter `apply_ceilings`.

Later wiring must establish typed input provenance, bind reference identifiers to the separately documented prediction-side identifiers and original trial/voxel identities, and preserve the evaluator's explicit refusal of undefined-value imputation. Genuine-data key matching, scientific scoring, and a readiness promotion require separate admission. The observed zero raw-pattern overlap alone supplies no license to guess a conversion.
