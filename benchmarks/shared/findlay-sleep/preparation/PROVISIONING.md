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

These are fixed benchmark metadata, not original observations or a historical
execution graph. The [metadata provisioning commands](metadata/README.md) now
reconstruct the published-family ledger and identity policy with exactly these
sizes and digests. The one complete input ledger still comes from an authorized
benchmark operator. Reformatting JSON changes the selected digest; no schema or
formatting fallback is accepted.

The family exporter authenticates the publisher workbook and all 14 official
parameter files, then uses our explicit 98-row curated crosswalk. This mapping
is benchmark-authored, not publisher-supplied. It preserves all 109 source
configurations, the 94 selected rendering configurations, the five-family
occupancy expansion and all 15 excluded drafts. The identity exporter derives
the five balanced animals and one applicable 13-column exclusion from exact
official sources without embedding animal identities in this repository.

## One accepted audit ledger remains operator-supplied

The input ledger binds the 17-member archive census, all thirteen footer
schemas/counts and the full 16-animal/29-session roster. Those factual fields
can be checked against legitimate originals. The same fixed body also contains
its original audit's exposure assertions, historic HTTP observation and authored
policy/prose. A new archive read cannot reconstruct that earlier history.

This is a precise provisioning requirement, not a missing dataset or permission
to omit a table. The accepted audit metadata can be supplied separately; the
commands do not fabricate its history, replace its pin or copy prior receipts.
The [metadata guide](metadata/README.md) identifies the exact public origins,
commands, source/metadata digests and remaining audit-input boundary.

No publisher workbook, official source body, animal identity, reconstructed
metadata or numerical answer is redistributed here. The official code's root
MIT notice does not supersede the R subtree's CC BY-NC-ND notice. The software
and crosswalk do not qualify scientific results or claim a blind evaluation.

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

