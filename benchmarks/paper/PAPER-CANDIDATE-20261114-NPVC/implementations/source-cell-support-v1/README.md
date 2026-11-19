# NPvC author cell-selection construction

The released dataset README documents `session.mat` as a 4732-cell, seven-column
global metadata table and names four quality-selection index vectors:
`okunlabeled`, `ACC`, `RETRO` and `PPC`. `cell_support.py` constructs explicit
source cell/session/animal rows from those decoded variables. It preserves the
documented one-based global cell indices, including the first and last rows.

This is upstream of the existing FDE and paired-support components. Those
components consume already constructed observations and cannot recover these
source quality-selection memberships. The new function does not replace them.

The table columns remain, in order: source session number, source animal number,
session number within that animal, ACC flag, cPPC flag, RETRO flag, and unlabelled
flag. The selector named `PPC` checks the cPPC column; `RETRO` checks its separate
column. The global source table must retain all 4732 rows and its documented
64 source-session identifiers. These are source-release metadata extents, not
the paper's separately unresolved 59-session/2860-cell analysis population.

Every selected ID must be a finite integral one-based index into this exact
table. A repeated ID within one selector or a selector contradicting its own
documented flag refuses. Overlap across different selectors is preserved: the
output counts each unique cell once, records every selector membership and
keeps every source flag. Multi-selector and multi-flag rows are exposed without
an invented projection-priority rule or extra exclusion criterion. The helper
does not assert that overlaps actually occur in the original data.

`construct_cell_support(session, selections)` accepts an explicitly decoded
row table and flat index vectors. It performs no file loading. A caller
must authenticate the original MAT assets and establish their actual variable
shapes, orientation and decoding before calling it. Integral MATLAB doubles
are accepted without rounding; boolean masks are not interpreted as indices.

The result also lists cells not selected by any supplied quality vector. This
is not a list of cells excluded by the source paper. Numeric animal/session
IDs are kept verbatim; no AW filename, archive order, trace-row order, retained
study cohort, time origin, epoch boundary or historical fold is inferred.
Original-study eligibility and scientific readiness remain unestablished.
No original MAT array, neural trace, model or fit was used to construct the
implementation or its generated controls. The later original-metadata check
below authenticates only the three specified metadata files.

Primary documentary source: the README in Harvard Dataverse dataset
[`10.7910/DVN/NL1CAQ`, version 1.0](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NL1CAQ).
Authenticated source text: 1941 bytes, SHA-256
`d72d9ee89d8369b8d319628a7559a639e9d584529e349a0aba115a14e99ff62b`.
The separate source-recovery packet retains the provider metadata and checksums.

The focused data-free controls cover one-based boundaries, projection-column
order, overlapping memberships, exact numeric identities, source-table
completeness and refusal of contradictory selections. They establish the
constructor's behavior, not original data preparation or paper reproduction.
## Observed original metadata

A subsequent bounded operation authenticated and decoded all three original
metadata files, then called the unchanged constructor. The observed table has
4,732 rows and seven columns, covering 64 source-session IDs. The four quality
selectors retain 3,134 unique cells across 59 source-session IDs: 2,732
`okunlabeled`, 155 `ACC`, 129 `RETRO` and 118 `PPC`. No cross-selector overlaps
or multiple projection flags were observed. Overlap remains supported by the
constructor; this observation introduces no new exclusion rule.

The observed selection of 59 source IDs does not establish membership in the
paper's historical 59-session cohort. The 3,134 quality-selected cells are not
the paper's reported 2,860-neuron analysis population; that membership join is
unresolved. Archive/trace-row mappings, trial eligibility, temporal alignment,
epochs, folds and reference predictions remain unresolved. This metadata check
establishes no reproduction, improvement or scientific benchmark readiness.

All 7,902 original bytes matched provider extents and MD5 checksums before
parsing. Independent SHA-256 values bind the received bytes:

| Original file | Bytes | Provider MD5 | Received SHA-256 |
| --- | ---: | --- | --- |
| [session.mat](https://dataverse.harvard.edu/api/access/datafile/11912032) | 1,857 | `cb1aa27af581744d7257a70708e05927` | `0a3791675357591e9478fae9c6be3b78dbe6a396478ab0e3b4aafd8ec59b38b8` |
| [okcel2.mat](https://dataverse.harvard.edu/api/access/datafile/11912076) | 4,957 | `0819b3370e6299b152aaaa5de0fd03ab` | `db7c774e981ded38c251a43c8f81f22a3dfe7c282ba7746775b41ecb9f0104d1` |
| [goodlabeledcells.mat](https://dataverse.harvard.edu/api/access/datafile/11912082) | 1,088 | `54139196f77e99286a455929d3232682` | `a5363f14435aab702516ae263cc25fb08f19f6a0ddd063753eef65d7753c2425` |

`SOURCE.json` records this original-metadata admission, its stable file
checksums and aggregate counts, and the SHA-256 of its preserved preparation
predecessor. The source algorithm and generated controls are unchanged.
Neural trace/model reads and model runs remain zero; original-paper cohort
membership and scientific readiness remain unestablished. Raw metadata,
signed delivery URLs and subject/session ID rosters are not included here.
