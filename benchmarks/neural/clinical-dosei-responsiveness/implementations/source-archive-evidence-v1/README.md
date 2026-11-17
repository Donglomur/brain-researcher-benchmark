# Verified original DOSE-I source archive

The original v2 `data.zip` has been acquired and its complete bytes match the publisher's MD5. Its observed full SHA256, directory totals and all 171 CSV header observations are recorded in `source-verification.json`. Raw data and private acquisition receipts are not included in this repository.

This receipt closes archive availability and header compatibility. It does not establish an assessment denominator, biological-person identity, signal validity, complete native parsing or a ready benchmark. The metadata summary counts and inherited scorer population still require reconciliation with original events; recording IDs must not be treated as verified biological-person IDs.

The compressed archive is 724,356,077 bytes. The directory declares 4,410,298,417 expanded bytes, with a largest CSV of 66,526,033 bytes. The preparation path should stream recordings rather than extract the whole collection. All 171 files include `Time`, both `Intellivue/EEG` channels, `EVENT`, `MOAAS`, `SOC` and `Misc`. Recordings 83 and 84 omit optional peripheral measurements; name-based EEG/annotation readers need no remapping.

Header-only inspection can cause ZIP-library read-ahead beyond returned header bytes. It does not verify complete CSV-member CRCs or parse source signal/clinical rows. The record reports these limits explicitly. Existing source-reader, population and canonical-scoring holds remain in force.

To independently verify the same input, retrieve `data.zip` from the exact [Zenodo v2 release](https://zenodo.org/records/22145442), check its exact size and complete publisher MD5, then compare the observed SHA256 in the receipt. A matching filename or a partial-file hash is insufficient. Any subsequent preparation must bind the selected member to this complete archive and retain member-level completion evidence.
