# Cerebellar reconstruction input layout

This document describes the public observations for the complete released F2/F3 reconstruction task. The scientific question, numerical rules and required answer schema are supplied separately. Each submission uses all 1,006 F2 units and all 14 F3 panels/560 trials in the supplied source order.

| Candidate path | Exact representation | Bytes |
|---|---|---:|
| `/input/f2_rates.f64` | Headerless little-endian IEEE binary64, C order, 104312 rows × 350 columns | 292,073,600 |
| `/input/f3_rates.float64le` | Headerless little-endian IEEE binary64, C order, 560 rows × 350 columns | 1,568,000 |
| `/input/public_layout.json` | Strict JSON metadata with the schema below | At most 262,144 |
| `/input/ROSTER.json` | Complete ordered F2 unit and F3 panel identities | 122,364 |

The two binary files are observations, not precomputed detection curves or timing answers. Their complete byte hashes are supplied by the input admission manifest. Do not infer biological trial correspondence between F2 and F3 from their shared mouse labels. Mouse folders are source labels, and source unit/trial positions are the available identifiers.

`public_layout.json` has exactly three top-level keys:

```json
{
  "schema_version": 1,
  "units": [
    {
      "mouse_source_label": "Mice01",
      "unit_index1": 1,
      "trials": 78,
      "row_start0": 0,
      "row_stop0": 78,
      "increasing_direction": true
    }
  ],
  "panels": [
    {
      "mouse_source_label": "Mice01",
      "reward_code": 1,
      "trials": 19,
      "units": 131,
      "row_start0": 0,
      "row_stop0": 19
    }
  ]
}
```

The one-row objects above illustrate the schema; the direction value is illustrative and must be read from the supplied complete layout. The actual file contains all 1,006 unit rows and 14 panel rows. Every row range is half-open: `[row_start0, row_stop0)`. Multiply a row offset by 350 × 8 to obtain its byte offset. Unit indices are one-based; binary row offsets are zero-based.

F2 rows follow Mice01 through Mice07, then original unit order, then original trial order. The mouse unit counts are 131, 143, 111, 107, 246, 176 and 92. `increasing_direction` means membership in the released `idx_expert2` input classification. It is a required input to the prescribed branch, not an evaluation label to predict. Classification duplicates do not duplicate scientific units. Preserve the required delta state across consecutive trials and unit boundaries within each mouse. Reset the four-value state to zero only when starting the next mouse; do not initialize each unit independently. No carried state value is supplied.

F2 rates retain the original processed values and float64 bit patterns after a storage-layout transpose; physical units remain unverified. All 350 columns enter the analysis. The nominal bin labels run from −1500 through 1990 ms in 10 ms increments; use the separate scientific protocol's exact peak-clock arithmetic for strict boundary comparisons.

F3 rows follow each mouse's reward code 1, then reward code 9, followed by the original trial-cell order. Each input row is a released pseudo-population rate derived by averaging its contributing units at each 30 kHz sample, summing 300 samples per 10 ms bin and multiplying by 100. Only source samples 1 through 105000 contribute to the 350 rate bins. The additional 105001st source sample is excluded by the released numerical procedure. The contributing units may come from different sessions/depths within a mouse and matched choice/outcome histories. These rows do not establish simultaneous population recording or prospective prediction performance.

Both information conditions receive identical observations, layout, roster and the explicit numerical protocol. The code condition additionally receives the released F2 and F3 analysis scripts. The code condition does not add saved author-answer MAT files. Exact paper and numerical-protocol assets must be admitted before the package is described as a paper-plus-data comparison.
