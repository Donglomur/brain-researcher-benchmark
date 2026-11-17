# Exact assets and evaluator conversion

Obtain research assets directly from their upstream sources for your authorized use. Do not put them, generated references, acquisition receipts or private host configuration in this source tree. No downloader or automatic scientific operation runs during plan/build/select.

## Complete data and paper

The published study is [Dake and Curtis, Nature Communications (2025), DOI 10.1038/s41467-025-57882-8](https://www.nature.com/articles/s41467-025-57882-8). Acquire the publisher's main article PDF through that page. The selected article is **1,996,585 bytes**, SHA256 `8c8cc3ca22cdeb08459ad3688e86b43b95ef0b052572f319994d1235ae3676fc`. A different download or article rendering is not silently accepted. Both arms receive the same exact PDF.

Use the [official OSF project](https://osf.io/hf5a4/) and [behavioralData_allsubs.csv download](https://osf.io/download/jx82h/). The retained release metadata identifies OSF file `67c0625c1e694f4f4180699a`, version 1. The complete derivative is **4,926,544 bytes**, SHA256 `b677bede5c7c8c2806e2796ed58c783b07d2a73687d662b97ceb078916ade80a`. The exact hash is authoritative if a mutable download locator later changes. Do not substitute the much smaller per-outcome summary CSVs.

Keep these CSV bytes unchanged: no spreadsheet resaving, row sampling, line-ending normalization, subject filtering, deduplication or NaN replacement. No conversion is needed for candidate input. The full release contains 14,061 trials and all 15 declared release participant codes; codes are source identifiers, not physical identities inferred by this benchmark. The parser requires `subjID`, `day`, `TMS_condition`, `ierr`, `isacc_rt`, and `isacc_peakvel`, rejects ragged/duplicate columns and unexpected cohorts, counts outcome missingness, and requires every participant-condition-outcome cell. The seven figure predicates exclude No TMS rows on days 4–5; no additional trial filters apply.

## Exactly two official files for B

Acquire the byte-exact files at these immutable revisions. Do not clone and mount an entire repository into B; the allowed comparison is precisely these two files.

| Relative destination under B's `/task/code/` | Immutable upstream | Bytes | SHA256 |
| --- | --- | ---: | --- |
| `generateFigure2.py` | [clayspacelab/Dake_Curtis_TMSV1_2025, 1e2c149e](https://raw.githubusercontent.com/clayspacelab/Dake_Curtis_TMSV1_2025/1e2c149e6e61f85b45acb8486c0fb31dc38d2dfa/generateFigure2.py) | 3201 | `7dfae3dd3cf2f948fa843ec57174b3ca2c1fa1a50f6f7d3412cb4d6f8905bd6f` |
| `mgsAnalysis/analysisEye/helpers.py` | [mindemory/mgs_stimul, 57c4aeac](https://raw.githubusercontent.com/mindemory/mgs_stimul/57c4aeac3028c02f4b886eb4fd05435e126a80fe/mgsAnalysis/analysisEye/helpers.py) | 14445 | `8d03646d8be38e154c52d9e435c45d94c0ae263beba467f76b33360ee157c58f` |

The figure script supplies the figure predicates and absolute means. The helper contains signed formulas and a different original pro/anti and grouping pipeline. The excerpt is for inspection/adaptation, not a claim that two files form an executable upstream repository or prove the historical publication execution.

## Verify and prepare the protected evaluator

The byte lengths and digests above also appear in `portable/CATALOG.json`; `METHOD.json` and the owner bind the complete CSV. Hash the downloaded ordinary files before supplying their absolute locators in the private request. For example:

```sh
wc -c /OWNER/assets/behavioralData_allsubs.csv
shasum -a 256 /OWNER/assets/behavioralData_allsubs.csv
```

If the accepted protected reference is already available, reuse it unchanged. Otherwise, after separately selecting evaluator preparation on the exact normative **CPython 3.11.6** runtime, run the included authored reference implementation on the complete authenticated CSV:

```sh
/OWNER/runtime/python3.11 -I -S -B /ABSOLUTE/behavior-v1/reference/behavior_reference.py /OWNER/assets/behavioralData_allsubs.csv /OWNER/evaluator/behavior_reference.json
wc -c /OWNER/evaluator/behavior_reference.json
shasum -a 256 /OWNER/evaluator/behavior_reference.json
```

The output path must be fresh. Use no optional `--literal-draws` argument. Defaults preserve seed 20261114, 2,000 participant bootstrap draws per contrast, all 32,768 sign patterns and all 270 omission summaries. The CLI serializes `json.dump(indent=2, allow_nan=False)` plus one newline; intake derives only from CSV content, not its location. The accepted reference commitment is **225,502 bytes**, SHA256 `5e95581135da69b9ebea97fa653fc27d202169abc1d61aee4b8d20c942ff3198`. Source and the prior accepted execution support this relocation recipe; this export did not regenerate the reference. If bytes differ, preserve the discrepancy and diagnose it. Do not update the commitment to make a new file pass.

Keep the generated file evaluator-private and independently review the complete output before using it. No participant-visible mount may contain it. The included construction program computes only the submission from the CSV; it is a fixed validation control, not an LLM-generated solution. The complete scorer compares finite floats with relative tolerance 1e-7 and absolute tolerance 1e-9 and exact types/structures otherwise. A/B byte equality does not imply exact floating-point equality to the protected reference.

## Attribution and rights boundaries

The upstream article identifies a CC BY-NC-ND 4.0 license. The publication code repository contains an Apache 2.0 license at the inspected revision. Retained inspection did not establish a redistribution grant for the linked auxiliary analysis repository or a license assigned to the OSF project. Absence of an inspected grant is not a claim that use is prohibited. Verify the applicable source terms for your intended access and distribution; this repository's MIT license covers only the authored benchmark software.

This export redistributes none of the article, data or official code. Acquire them upstream; local possession and a matching digest do not grant redistribution permission. Any later redistribution must preserve applicable attribution and other terms and resolve the auxiliary/data rights separately. Do not infer permission from a public URL, GitHub visibility, this recipe, or successful provisioning.
