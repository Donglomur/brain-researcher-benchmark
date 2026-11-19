# NEURAL-063: original metadata qualification

[Task overview](../README.md) · [Evidence summary](original-metadata-evidence.json)

For **Omission-conditional calcium population trajectory prediction**, one original NWB file of **227,971,260 bytes** passed full SHA-256 and BLAKE2b authentication and local metadata/support qualification. This completes one local metadata/support unit. Neural values were not decoded, no response projection was performed, and the result is not an ordinary complete-session input or a completed benchmark run.

The prescribed `processing/ophys/dff/traces` series has the complete raw shape **[48,147, 1]**: 48,147 time points and one source ROI column. Its entire referenced `processing/ophys/image_segmentation/cell_specimen_table` contains **one row**. The single-column result reflects the complete contents of that series and table; the producer did not filter a larger valid population in those datasets down to one ROI. This finding does not enumerate every other series, table or modality in the NWB file.

The historical **184** count means supported omission events in an earlier saved comparison. The current metadata contains **195 omitted presentation rows**. Neither number is an ROI count. This qualification did not reconstruct how the earlier scheduling and support rules related those two event counts.

The declared inventory remains **1,936 planes across 703 sessions and 107 mice**, with **73 fit, 15 validation and 19 query mice**. Only the selected local metadata/support unit completed; **1,935 other planes are unattempted and all 703 sessions remain incomplete**. Authentication applies to the selected original object. Cohort-wide full-object verification, metadata/support completion, full-host execution and benchmark readiness remain unestablished.

Preparation for a full-cohort layouts-only stage passed six generated control groups. The latest actual layout caller then stopped at its time-bound guard: it requested 1,800 seconds while the retained maximum was 630 seconds. It stopped before native or provider work and issued zero provider requests. These preparation checks therefore establish no cohort download or complete layout bank.

Remaining work follows this order:

1. Complete the fixed-version layout and byte-range bank for all 1,936 planes.
2. Complete metadata, agreement among every member of each of the 703 sessions, event support and schedules; publish the exact metadata/support and range-schedule formats.
3. Complete the physical storage census for every source column, including columns with no eligible events, contiguous storage, unallocated or fill regions, and finite extents.
4. Separately review and select the neural-value projection producer against the complete banks, then complete the full-cohort equivalence, model and scoring requirements.

The [evidence summary](original-metadata-evidence.json) records the selected object's SHA-256 and the byte lengths and SHA-256 hashes of the saved qualification, ROI-scope, layout-preparation and actual-layout receipts. These receipts support the scope above; they do not change the registered task, mouse split or readiness status.
