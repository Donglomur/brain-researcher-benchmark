# Local repair status

This remains a simplified, paper-derived lateralization methods case, not the published
ERP CORE N2pc characterization: N=12, 200–300 ms, all stimulus trials, and no ICA,
behavioral exclusion, or HEOG artifact rejection. A raw lateralized difference is not by
itself evidence for artifact-free covert attention.

Implemented: exact 12 unique subjects, signed contra-minus-ipsi row identities, reference
contra/ipsi comparisons, recomputed group measurements and trial totals, and fail-closed
paired `.set`/`.fdt` cache validation. Oracle reports observed SHA256 for every raw file.

Still pending: independently pinned expected raw-file digests; trial-count reference and
event/QC receipts; independent raw-data reference regeneration and in-container oracle.
Existing amplitude reference was not modified. Authoring fixtures test the contract, not
scientific validity or model difficulty. Harbor/Sol calibration has not been run.
Equal target-left/right weighting and exact -0.200..+0.450-second epochs are now
public; a tested production helper preserves that original numerical endpoint.
