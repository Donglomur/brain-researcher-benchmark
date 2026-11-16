# Provision originals and fixed metadata

The fresh mode removes dependence on the earlier local attempt. It needs the
legitimate original release plus the three frozen external metadata files
described below. It makes new receipts for the current operation. It never
pretends that a previous download, failure or cleanup happened on this host.

## Original release

The primary source is the [published data DOI](https://doi.gin.g-node.org/10.12751/g-node.xzmv31/).
Its fixed archive locator is
[10.12751_g-node.xzmv31.zip](https://doi.gin.g-node.org/10.12751/g-node.xzmv31/10.12751_g-node.xzmv31.zip).
The retained DOI-snapshot metadata binds archived GIN revision
`9b85130f884e98c1e699ca60107d2ba394a2e121`.

Supply an ordinary local copy of the complete **3,015,691-byte** archive. The
accepted observed SHA256 is
`2379c49ca5c8bf88a419ff6e6c726cb91f6534fd7360a51fb8aaf19de210a534`.
This is a previously measured and independently checked release identity,
**not** a provider-published checksum and not a conversion of the HTTP ETag.
Acquisition is separate from this package; neither binder nor first-intake
worker contacts the network, refreshes a changed release, or retries a failure.

The source validates all 17 stored ZIP members and all 13 Parquet footer
bindings. All extracted members total 3,012,983 bytes; the 13 tables total
2,989,690 bytes. A different archive, even if it is a later legitimate release,
does not silently become the frozen benchmark input. Original data rights are
CC BY 4.0 according to the retained DOI/DataCite metadata; preserve attribution
and independently satisfy the applicable terms when obtaining or sharing it.

## Fixed external grading metadata

The following bodies are required outside the source checkout:

| Role | Exact bytes | SHA256 |
| --- | ---: | --- |
| Complete input ledger | 18,075 | `d2756c791ccdedf22de2ef5e2949b43d804c0232c1aeddcb6ff25411ddaafed1` |
| Complete published-family ledger | 66,285 | `e6602394041e2a6f448db374ffccbf06856f262e13df468003a901ae4fa2eced` |
| Private identity policy | 935 | `4879ce87b72c06d88a67149c990f876ffca8254bfcfc659229a72e0ebd569ab2` |

These are frozen benchmark metadata, not original observations and not a
historical execution graph. Obtain the accepted bodies from an authorized
benchmark operator. The source does not currently publish them or provide a
deterministic exporter that reconstructs their exact serialization from public
origins. Reformatting JSON also changes the selected digest; no formatting or
schema fallback is accepted.

The input ledger binds the exact 17-member ZIP census, thirteen complete
footer schemas/row counts and the full 16-animal/29-session roster. The family
ledger binds all 98 published analyses, their exact source parameters and table
joins. The private policy binds the accepted five-animal balanced subset and
one fixed thirteen-column ordinary exclusion, without embedding their
identities in the software.

## Exact public-origin generation operation still missing

Independent provisioning without an operator-supplied metadata bundle needs
one deterministic, separately reviewed metadata exporter. The current
first-intake implementation does not substitute a guessed exporter. Its
required operands and outputs are concrete:

1. Parse the exact original archive's complete directory and all thirteen
   Parquet footers, preserving ZIP sizes/CRC/modes and footer hashes. Join the
   original archived source metadata for the full roster and protocol mapping.
   Generate every input-ledger field, including the complete member and
   observation-page-exposure descriptions, without selecting animals from
   outcomes or decoding observations merely to guess metadata.
2. Read the publisher's
   [Supplementary Table 1](https://static-content.springer.com/esm/art%3A10.1038%2Fs41593-025-02141-8/MediaObjects/41593_2025_2141_MOESM3_ESM.xlsx),
   **26,378 bytes**, SHA256
   `e0f45c39c36cf9b9b82f84d54e622cb2449ac2e7607ac57ab3fec20ddc17f62b`.
   Join all 98 table rows to the official source's 94 rendering configurations.
   The occupancy configuration contains five analyses; the 15 unpublished
   source configurations remain excluded explicitly. These are analysis
   families within one task, not 98 separate benchmarks.
3. Use the [official code release](https://zenodo.org/records/17364618)
   (`v1.0.0`, release-linked tag commit
   `1e7afd0f5b1dfd7a12eb2bf6a1e1d28c3049719e`). The retained audit used its
   direct parent `1bb2e72a3d590556e63aec1ffed6b461734c8021`; scientific
   source/dependency/R-data top-level Git objects were identical and README
   differed. This is a source-object correspondence, not a byte validation of
   the Zenodo ZIP. Capture the exact source parameters and formula/table map,
   and derive the balanced-cohort and ordinary exclusion identities from that
   source, never from similar labels or favorable results.
4. Produce complete ledgers and the identity policy with deterministic
   serialization. Check their exact fixed digests, schema, all 98 unique IDs,
   thirteen table memberships and policy-to-full-roster joins. If exact
   reconstruction is impossible because a curated field's derivation is
   missing, retain the discrepancy for explicit scientific review; do not
   accept a different metadata body under the existing endpoint.

This metadata-export operation is unimplemented in the selected package.
The missing operation does not stop an operator who already holds the three
accepted metadata bodies from performing a fresh full preparation. It does
limit a claim that every prerequisite can currently be reconstructed
automatically from public links alone. The source does not distribute the
publisher workbook, official code, roster identities or numerical answers.
The code's root MIT notice does not supersede the nested R source's separate
CC BY-NC-ND notice.

## Fresh operation and its outputs

Follow the guide's binder with `--original-archive`. It verifies software and
fixed metadata, checks the local archive's ordinary-file extent, and binds the
expected digest. At actual worker execution, the entire body is hashed **before**
copy/extraction. The immutable new copy is independently read by the existing
ZIP/member/footer validator. Only then is the complete admitted native census
invoked. All thirteen tables, including the complete OFF-duration table, are
scanned; no old table report or partial cohort is reused.

The worker writes a new `ORIGINAL_INPUT.private.json` rather than an invented
HTTP receipt, full integrity/table/group/family receipts and both contrast
reports. It checks every stored member again after census. Original input
files and old operation directories are not edited. Failures leave the new
partial evidence and retain the same scientific holds.

The current 32 MiB worker / 40 MiB whole-operation retention ceiling incorporates
the previously accepted correction to the original 12 MiB worker ceiling.
That older attempt failed at output retention after complete table census.
It is preserved as historical evidence, not required to use this new branch.
The 24 MiB worker-read partition and 180-second work/60-second recovery clocks
remain enforced; this source phase has not measured a fresh native run.

No participant scorer, 98-family numerical reference set, fit, baseline or
model result is created by this preparation. Scientific qualification remains
false until the still-required scientific work and independent outcome review
are completed.

