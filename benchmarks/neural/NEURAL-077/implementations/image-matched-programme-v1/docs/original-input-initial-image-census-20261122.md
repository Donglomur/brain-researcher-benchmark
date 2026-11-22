# Original ERP input audit — 22 November 2026

All **6,400 queries from 32 participants** passed the initial-image interface audit in one attempt: **zero failed and zero unattempted cases**. This validates input preparation for `NEURAL-077`; it adds no benchmark task or model result.

For each query, **one shared initial render** fed the existing direct and programme local projections. Their PNG bytes were identical, and public headers matched after the specified permission-sentence and episode-identifier normalization. These were local projections of the same render, not two independently executed participant arms.

The [machine-readable result](original-input-initial-image-census-20261122.json) retains the exact aggregate outcome, accounting and limitations. All 36 public packet members and all 32 whole query shards were authenticated. The earlier 400-case condition remains unchanged.

## Reproducibility

The campaign used an isolated copy of source commit [`ac0b563`](https://github.com/Donglomur/brain-researcher-benchmark/tree/ac0b563a8b233d1c421c174a9fd4c7caccfa2188), tree `7daf741c52543c7fb61663ee04d18ff0e77c91e6`, plus the unchanged [collector](../initial_image_census.py). Publication on a later commit does not change the execution's source identity.

| Input or environment | Recorded identity |
| --- | --- |
| Collector SHA-256 | `44a66b3d4cd50134da73202464b6a6bc5c8aa2eaa58029a422b3175b361eb05c` |
| Public packet manifest SHA-256 | `241870678fed37fca67cc9c64e2e3a0830e0a97f9815332e27fa3018ed6c9f3f` |
| Manifest size | 5,428 bytes |
| Manifest and public members | 235,921,250 bytes |
| Runtime | Python 3.11.6; NumPy 1.26.3; arm64 |
| zlib | Compile 1.2.11; runtime 1.2.12 |

See the [collector instructions](../INITIAL_IMAGE_CENSUS.md) for the input and execution contract. The retained hash-linked census was checked for the complete ordered roster and absence of partial tails. Successful session images were deleted after durable census records; the hashes alone cannot reconstruct those images.

## Interpretation

This audit covers initial query images only. It does not cover later viewer actions, demonstrations, two native participant deliveries, predictions, model calls or scoring. Event-label identity is not evidence of physiological P3 presence. Source-coordinate timing, physical amplitude calibration and possible prior exposure to public data remain limitations.

Observed elapsed time was approximately 759.42 seconds. The result records 176,761,806 cumulative written bytes, including deleted session files, and 15,750,717 retained metadata bytes. The recorded maximum child RSS is not simultaneous process-tree memory or a hard memory limit.
