# Protocol for the bounded CA trajectory component

This is a protocol-guided numerical reconstruction from processed place-field trajectories. It is not a paper+data versus paper+data+code comparison, raw neural-data understanding, a replication of the full publication, or a test of a biological mechanism. These instructions define the task independently of access to the final article. Implementations may use any numerically equivalent valid OLS method.

## JSON syntax and scalar limits

The following limits describe the existing decoder and apply before scientific scoring. Serialize ordinary short JSON numbers; equivalent longer spellings can exceed the token limits. The output must be one nonempty strict UTF-8 JSON object, without a byte-order mark, and no more than 5,000,000 bytes in total. Duplicate object keys and the nonstandard literals NaN, Infinity and -Infinity are rejected. Strings must contain valid Unicode scalar values.

- Each floating-point token (a JSON number with a decimal point or exponent) may contain at most 128 characters, counting its sign, decimal point and exponent. It must convert to a finite Python binary64 float. A literal with any nonzero mantissa digit that converts to zero is rejected as underflow.
- Each integer token may contain at most 32 characters, including a leading minus sign. A `count` field must be an integer from 0 through 1,000,000; an `integer` field must be an integer from -1,000,000 through 1,000,000. Booleans are not integers or numbers for this contract. Other numeric fields accept finite integers or floats as specified by their result shape.
- Objects may have at most 40 members; object keys may have at most 128 decoded characters. Arrays may have at most 5,000 items. Every string, including `reason`, may have at most 512 decoded characters, subject to any stricter identity or enumeration rule. These character counts use decoded Unicode code points, not UTF-8 bytes.
- The decoder's nesting limit is 16: the root value has depth 0; traversing from an object to any key or value, or from an array to an item, adds one. Every traversed value must have depth at most 16.

These are syntax and representation limits, not a scientific accuracy threshold. All exact key sets, scalar types, identity rosters, enumerations, declared-null masks and probability bounds in the sections below and `PUBLIC_CONTRACT.json` still apply. Keep undefined scientific quantities as the specified JSON null/status combination; do not replace them with nonfinite numbers or remove their records.

## Exact JSON wire format

The top-level object has **exactly** these keys: `schema_version`, `candidate_id`, `case_fingerprint`, `submission_status`, `reason`, `planes`, `fields`, `groups`, `animals`, `contrasts`, and `coverage`. Set integer `schema_version` to 1, `candidate_id` to `PAPER-FIND-013`, and `case_fingerprint` to the exact string in the supplied public contract. `submission_status` is `complete`, `partial` or `abstained`; `reason` is a string of at most 512 characters (an empty string is allowed). Do not add keys.

For `complete` or `partial`, retain exactly every identity in each public roster; record order is unrestricted. The five table fields are arrays. A plane record is exactly `{ "identity": <roster identity>, "status": <plane status>, "field_count": <public field count> }`. Plane status is `processed`, `empty_source_plane` or, for partial submissions only, `abstained`. Copy the plane identity and integer field count from `rosters.planes`; preserve empty planes explicitly.

Each record in `fields`, `groups`, `animals` and `contrasts` is exactly `{ "identity": <roster identity>, "result_status": "reported", "result": <scientific result object> }`. The result object follows the matching entry in the public contract's `result_shapes`; contrast shape is selected by `identity.kind`. For an explicitly unreported partial row, use `result_status: "abstained"` and `result: null` while retaining its identity. Complete submissions prohibit abstained rows.

`coverage` has no identity: it is exactly `{ "result_status": "reported", "result": <coverage object> }`, using `result_shapes.coverage`. A partial submission may instead use `{ "result_status": "abstained", "result": null }`. Public `result_shapes` tokens describe nested scalar types, nullable quantities and exact enumerations; they do not replace these outer wrappers. All unknown, duplicate, omitted or wrongly typed keys/identities are invalid. NaN/Infinity are not JSON numbers for this interface.

Whole abstention is the following complete object after replacing the fingerprint placeholder with the public contract's actual fingerprint. It has five empty arrays and a **null coverage field**, not a coverage wrapper:

```json
{
  "schema_version": 1,
  "candidate_id": "PAPER-FIND-013",
  "case_fingerprint": "COPY_THE_PUBLIC_CONTRACT_CASE_FINGERPRINT",
  "submission_status": "abstained",
  "reason": "No numerical answer supplied.",
  "planes": [],
  "fields": [],
  "groups": [],
  "animals": [],
  "contrasts": [],
  "coverage": null
}
```

Whole abstention invokes no numerical private-reference callback. A partial submission with no reported scientific result also receives an abstention outcome; it still must pass the complete roster/wrapper admission rules. Merely omitting an answer is not the same as declaring an abstention.

## Public structure and identity

`CA1.mat` and `CA3.mat` are MATLAB v5 files with one scientific variable, `data`, a scalar structure. Its conditions are `f` (familiar) and `n` (novel). Each condition is a scalar structure of named planes; every plane is a scalar structure with exactly `COM` and `onset_lap`. `COM` is a real matrix with fields in rows and original laps in columns. Nonempty COM matrices use float64 and preserve NaNs. `onset_lap` is a real row or column vector with one onset per field; flatten that vector in MATLAB column-major order, not the COM matrix. Source-empty planes retain matching 0×0 uint8 arrays and contribute no field rows.

Use the supplied identity manifest for region, condition, plane name, condition ordinal, plane ordinal, field count and source-assigned animal label. Preserve every plane, including empty ones. `pf1` is the one-based COM row index within that plane. Do not infer animal identity from field names or reorder a positional assignment. The labels reflect the released source assignment, not an independently verified biological mapping. Public contract rosters provide the exact allowed identities; all tables may be submitted in any order provided every identity occurs once.

## Observation clock, response and support

For each field, onset `o` is a finite integer in the one-based range 1 through the number of COM columns. Take the entire COM segment from column `o` through its final original column. Its origin `c₀` is the value at onset, which is finite in this admitted input. For offset `j=1,…,L` within that segment, define `xⱼ=j` and `yⱼ=6*cⱼ − 6*c₀`. Perform the two multiplications before subtraction. This is the source conversion to centimeters; slope units are source cm/lap and intercept units source cm. There is no circular unwrapping, smoothing, clipping or recentering at another lap.

Omit NaN response observations from the regression while retaining their original x coordinates. Never compress gaps into consecutive observed indices. Exact zero displacement is a valid observation. Infinities, an invalid onset or a non-finite origin are not silently repaired. The qualified input range is finite absolute COM no greater than 2⁵⁰, or NaN.

Report the raw post-onset segment length, finite-observation count and NaN count. With at least two finite observations, the interior support span is `last_finite_x − first_finite_x + 1`; otherwise it is null. This is the span that an interior linear interpolation would cover, without extrapolation. Eligibility is exactly a defined span of at least 15 laps. Interpolation values are **not** used in OLS. Fit every field's full observed post-onset segment, including fields ineligible for group summaries. Do not limit a fit to its first 15 laps or use the finite-observation count as the span.

## OLS and diagnostics

Fit `y = intercept + slope*x` to the finite pairs with an intercept. For n observations, define centered sums `Sxx=Σ(x−x̄)²`, `Sxy=Σ(x−x̄)(y−ȳ)` and `SST=Σ(y−ȳ)²`. Then `slope=Sxy/Sxx`, `intercept=ȳ−slope*x̄`, and `SSE=Σ[y−(intercept+slope*x)]²` using direct residuals. Report n, df=n−2, these sums and coefficients. When defined, residual variance is SSE/df, slope SE is √(variance/Sxx), signed t is slope/SE, F is t², two-sided slope p is the upper F(1,df) tail (equivalently a two-sided Student-t tail), and R² is 1−SSE/SST. Sxx has units lap², Sxy lap·source cm, SST/SSE/variance source cm²; t, F, p and R² are dimensionless. Do not substitute a robust model or an intercept-fixed-at-zero regression.

Represent undefined quantities with JSON null and the public contract's exact fit/status mask:

- Fewer than two observations: `insufficient_observations`; all numeric fit entries null, with the observed n and df retained.
- Nonpositive Sxx: `rank_deficient_predictor`; retain Sxx, Sxy and SST, with the other numeric entries null.
- Zero SST after defined coefficients: `constant_response`; retain coefficients and sums/SSE. For n>2, variance and SE are zero; for n≤2 they are null. p, R², t and F are null.
- Nonconstant response with n≤2: `no_residual_df`; coefficients, sums/SSE and R² remain defined, but variance, SE, t, F and p are null.
- Nonconstant exact fit with n>2 and SSE=0: `exact_nonconstant_fit`; p=0, variance/SE=0 and R²=1. Numeric t and F are null; their statuses record signed infinity for t and positive infinity for F.
- Otherwise use `ols_defined` with finite diagnostics and p in [0,1]. Destructive or non-finite derived arithmetic is `unsupported_derived_numerics`, with every numeric fit entry null and an explicit supported error reason. Never encode Infinity or NaN, or silently turn an unrepresentable nonzero result into zero.

These states define computation, not a desired biological effect. Missing p is not evidence of nonsignificance.

## Three separate classification conventions

Compute classifications for every field. Apply summary counts only to the eligible fields of the requested condition or animal-condition population. Positive slope is forward and negative slope backward. Preserve these separate conventions:

| Family | Forward/backward | Other category | Proportion denominator |
|---|---|---|---|
| `pooled_strict` | finite p<0.05 and positive/negative finite slope | nonsignificant if finite p≥0.05 | All eligible fields |
| `helper_inclusive` | finite p≤0.05 and positive/negative finite slope | shifting if finite p≤0.05 regardless of slope sign | All eligible fields |
| `animal_inclusive` | finite p≤0.05 and positive/negative finite slope | nonsignificant if finite p>0.05 | Union of these three classified sets |

Retain eligible counts, classified/unclassified counts where requested, undefined-p counts and the helper's shifting count with zero or undefined slope. Zero or undefined denominators yield null proportions. Do not drop unclassified rows from the eligible count. The legacy `shiftDir` label uses the strict pooled directional rule and otherwise `N`; its separate invalid-p flag must distinguish this fallback from valid nonsignificance. In particular p=0.05 belongs to pooled nonsignificance but the inclusive helper/animal directional categories when slope is nonzero.

## Group, animal and contrast summaries

For each region/condition group, summarize all eligible fields: arithmetic mean signed slope, median absolute slope, and all three classification families. An even-sized median is the mean of its two central absolute values. `n` is the declared summary population; `n_defined` counts finite slopes. An empty population produces `empty_denominator`; if any member slope is undefined, preserve `undefined_member_preserved` and null mean/median rather than silently reducing the denominator. Unsupported summary arithmetic likewise stays explicit.

For each animal/condition, report all/eligible counts and all classification families. `source_classified_slope_summary` uses only the animal-inclusive forward, backward or nonsignificant union. `descriptive_all_eligible_slope_summary` separately uses every eligible field. The two populations must not be conflated. Sort animal labels only for presentation; membership comes from the manifest.

Group contrasts are familiar minus novel (F−N) for mean slope, median absolute slope, pooled forward/backward/nonsignificant proportions and helper shifting proportion. The regional contrast subtracts the CA3 F−N contrast from the CA1 F−N contrast, component by component.

Within each animal, descriptive contrasts use F−N for the source-classified mean slope, median absolute slope and animal-inclusive proportions; shifting is forward plus backward. The separate source-oriented contrast also uses F−N **except median absolute slope, which uses N−F**. Report both orientations explicitly. Equal-animal descriptions average each animal's descriptive F−N difference with one vote per animal, not one vote per field. If any required animal component is null, that equal-animal component remains null; do not reduce its denominator. These are descriptive endpoints, with `inference_performed=false`; no t test, confidence interval, permutation, bootstrap or significance selection is required here.

Global coverage counts include every declared field, eligibility/exclusion, undefined slope and undefined p. Empty planes are explicitly `empty_source_plane` with zero fields; processed nonempty planes are `processed`. No field, exclusion, empty plane or undefined result may disappear from a complete submission. Partial/whole-abstention forms and exact nested output keys are supplied by `PUBLIC_CONTRACT.json`. The scorer reports separate endpoint errors and coverage without a blended success criterion or a positive-effect target.
