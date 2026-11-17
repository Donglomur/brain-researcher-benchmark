# Figure 5b published reference recovery

This component recovers the complete published aggregate Figure 5b panel from
the paper's official source workbook: **26 records, comprising six pooled and
twenty study-specific estimates, with 78 numerical estimate/interval values**.
It advances the original pretrained-signature assessment that the current
contract identifies as source unresolved. It does not change the task,
historical reconstruction implementation, cohort, split, or metric.

The [official Figure 5 source workbook](https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-026-11203-1/MediaObjects/41586_2026_11203_MOESM10_ESM.xlsx)
contains separate `Fig5a` and `Fig5b` sheets. The importer reads only `Fig5b!A1:F27`.
These are published aggregate results, with columns `outcome`, `signature`,
`study`, `estimate`, `conf.low`, and `conf.high`. They are not participant outcomes,
beta images, signature weights, or candidate predictions. All source payloads
and generated reference JSON remain outside Git.

The importer authenticates the workbook's exact byte count and SHA-256 before
reading it, resolves the named sheet, preserves decimal-comma source strings and
their full precision, and retains every original row's cell location. Its JSON
uses decimal strings so downstream code need not lose precision through binary
floating point. It rejects altered sources, incomplete/duplicate pairs,
unexpected targets, cached formulas, and study support that violates the
decoder-specific training exclusions.

| Signature | Included source study labels for each of the two outcomes |
| --- | --- |
| Negative Affect Decoder | Study 2, Study 3, Study 4, Average |
| Reappraisal Ability Decoder | Study 1, Study 3, Study 4, Average |
| Reappraisal State Decoder | Study 1, Study 2, Study 3, Study 4, Average |

Both original outcomes are retained: trait questionnaire and task-based affective
rating. `Average` is the source's label for pooled person-level analysis after
within-study standardization. The importer does not calculate an equal-weight
mean of study correlations, an absolute correlation, or a composite score.
The [Figure 5 caption and Methods](https://www.nature.com/articles/s41586-026-11203-1)
identify Study 1 as AHAB-2 (180), Study 2 as PIP (176), Study 3 as Doren (139),
and Study 4 as the Brehl reference cohort (235). These caption totals do not
authenticate person identities or per-pair missingness.

Use Python 3.11 or later with its standard library and an authorized local copy
of the exact workbook. The output path must be new and external to the repository:

```sh
python recover_reference.py --source "$SOURCE_FIG5_XLSX" --output "$EXTERNAL_REFERENCE_JSON"
```

The separate [Extended Data Table 3 page](https://www.nature.com/articles/s41586-026-11203-1/tables/4)
uses a table image. All eighteen displayed pooled correlation and confidence
limit values were visually transcribed from that image and independently matched
to the workbook after rounding to two decimal places. Its six P values and six
Bayes factors were retained in an external transcription; they were not
recomputed. The importer extracts the workbook quantities only and never infers
P values or sample sizes from rounded coefficients. Exact source pins are in
[SOURCE_MANIFEST.json](SOURCE_MANIFEST.json).

On 2026-11-17 UTC, eleven generated software controls passed through the shared
two-slot pool (`paper03-exp003-verify01`), followed by successful extraction from
the authentic workbook and the eighteen-value source cross-check. The controls
exercise omitted pairs, prohibited training cohorts, duplicate pairs, wrong
targets, numeric ambiguity, malformed intervals, column changes, cached
formulas, missing cells/rows, and an equal-length source digest mismatch. No
scientific model, participant-data preparation, training, author inference, or
candidate trial ran. New source acquisition cost was 234,926 bytes including
response headers; the generated extraction/control artifacts were 20,058 bytes.

Reproduction and improvement remain separate first-class outcomes. This is
**published-reference recovery**, not successful reproduction of the underlying
analyses or evidence of exceeding the paper. It supplies a source-pinned
reference for future paired paper+data and paper+data+author-code conditions.
The required participant/image/outcome joins, pretrained weights and training
provenance, exact preprocessing and missingness handling, author rerun,
reproduction tolerances, and improvement direction/margin/uncertainty policy
remain unqualified. No canonical task/contract, readiness count, historical
score, or access/exposure record is changed by this component.
