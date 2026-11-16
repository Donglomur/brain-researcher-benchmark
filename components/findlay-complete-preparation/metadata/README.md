# Provision Findlay preparation metadata

These two commands reproduce **two of the three** existing external metadata
inputs exactly. They do not modify the accepted fresh-original intake, lower
its authentication requirements, run an analysis or create a new benchmark.
The complete scope remains 13 released tables and 98 published analysis
families. Outputs are private operator inputs, not public source artifacts.

Use Python 3.11 or later with its standard library. From the public repository
root, use the commands below. Keep both exporter scripts and
`CURATED_CROSSWALK.json` together in this directory. Obtain legitimate copies of
the following original sources separately. Neither command downloads,
executes or modifies official code, evaluates spreadsheet formulas, reads
Parquet observations or contacts a service.

The fixed [official repository revision](https://github.com/grahamfindlay/Findlay_et_al_2025_Nature_Neuroscience/tree/1bb2e72a3d590556e63aec1ffed6b461734c8021)
supplies the Python core, R loader, ordinary contrast-export notebook and all
14 parameter YAML files. The accepted code audit links its scientific tree to
the `v1.0.0` release tag `1e7afd0f5b1dfd7a12eb2bf6a1e1d28c3049719e`.
This is not validation of the Zenodo ZIP. Root MIT and the R subtree's
CC BY-NC-ND notices are distinct; bring original files under their applicable
terms. This package contains our parsing software and authored crosswalk,
not copies of those source bodies.

The [publisher Supplementary Table 1](https://static-content.springer.com/esm/art%3A10.1038%2Fs41593-025-02141-8/MediaObjects/41593_2025_2141_MOESM3_ESM.xlsx)
must be the exact 26,378-byte workbook with SHA256
`e0f45c39c36cf9b9b82f84d54e622cb2449ac2e7607ac57ab3fec20ddc17f62b`.
Keep it outside the public source checkout. Extraction uses only the literal
response, covariate and figure labels in columns A:C of `Supplementary Table 1`.
It does not export result columns D:I. Internal ZIP/XML bytes include those
other cells, so byte-level access is not a claim that outcome-bearing workbook
content is inaccessible.

## Exact private identity policy

Set these illustrative paths to your legitimate external inputs and a pre-existing
private output directory. The outputs must remain outside the public checkout:

```sh
FINDLAY_OFFICIAL_SOURCE=../operator-inputs/official-code
FINDLAY_WORKBOOK=../operator-inputs/41593_2025_2141_MOESM3_ESM.xlsx
FINDLAY_PRIVATE_METADATA=../operator-private-metadata
```

Then run from the public repository root:

```sh
python3 -B components/findlay-complete-preparation/metadata/provision_identity_policy.py \
  --core "$FINDLAY_OFFICIAL_SOURCE/src/findlay2025a/core.py" \
  --loader "$FINDLAY_OFFICIAL_SOURCE/r/f25a/R/data_loading.R" \
  --exporter "$FINDLAY_OFFICIAL_SOURCE/notebooks/data_export/condition_constrasts.ipynb" \
  --output "$FINDLAY_PRIVATE_METADATA/PRIVATE_IDENTITY_POLICY.json"
```

The spelling `condition_constrasts.ipynb` is the author's actual filename.
Static parsing obtains the full 16-animal/29-session roster, the R loader's
five-animal balanced list, experiment aliases and all six source exclusions.
Applying the notebook's substring rule to its 27 displayed columns leaves
one applicable subject/protocol exclusion with 13 columns; the other five
source exclusions affect none of these selected columns. No animal identity
is embedded in the authored software. Exact accepted provenance pins remain
in the output. They identify benchmark policy ancestry, not publisher claims.

The result must be **935 bytes**, SHA256
`4879ce87b72c06d88a67149c990f876ffca8254bfcfc659229a72e0ebd569ab2`.
Source validation reconstructed these exact bytes from the pinned official
files. Expected exclusions remain accounted exclusions, not numerical
matches. Their presence does not itself make a full reconciliation unresolved.

## Exact complete published-family ledger

```sh
python3 -B components/findlay-complete-preparation/metadata/provision_family_ledger.py \
  --workbook "$FINDLAY_WORKBOOK" \
  --official-source-root "$FINDLAY_OFFICIAL_SOURCE" \
  --output "$FINDLAY_PRIVATE_METADATA/PUBLISHED_98_LEDGER.json"
```

`CURATED_CROSSWALK.json` is **our benchmark-authored curation**, extracted from
the already accepted full ledger. The publisher did not supply this join.
It explicitly maps all 98 unique worksheet row numbers to source family IDs,
template paths and input tables. It contains no result values or animal IDs.
It retains the accepted alias decisions, including regional SWA versus iDelta,
DS versus DSPK, the published change label versus source Surge, and the
ripple figure-label discrepancy. These are not automatic fuzzy matches.

The command authenticates the crosswalk, workbook and all 14 exact parameter
files. The parser supports only the observed flat string-mapping YAML subset.
It preserves physical source line numbers and configuration order, includes
all 109 source configurations, excludes exactly 15 declared drafts, and
expands the one occupancy rendering configuration into the existing five
families. All 94 selected configurations and 98 family rows are required.
No condition or subgroup becomes a new task.

All 98 literal A:C label triples were independently joined to their accepted
row identities in the accepted source review; no header was guessed or
selected by a result value. The complete result must be **66,285 bytes**, SHA256
`e6602394041e2a6f448db374ffccbf06856f262e13df468003a901ae4fa2eced`.
Exact output reconstruction was observed. The `code_map_sha256` field is the
fixed accepted benchmark map's lineage pin, not a claim that this command
reconstructs the separate map document or validates official runtime behavior.

Both commands reject substitutions before accepting output. They create a
new mode-0600 file and refuse to replace an existing path. Errors preserve any
partial output. Console receipts contain hashes and scope only, not identities
or publisher outcomes. The old metadata and scientific runs are unchanged.

## The complete input ledger still needs the accepted audit input

Supply the existing **18,075-byte** complete input ledger, SHA256
`d2756c791ccdedf22de2ef5e2949b43d804c0232c1aeddcb6ff25411ddaafed1`,
from an authorized benchmark operator. The two commands do not manufacture it.
It binds all 17 archive members, all 13 footer schemas/counts, the complete
roster, the observed HTTP entity and the original audit's exposure state.

The factual member extents/CRCs/modes come from the complete archive directory;
columns, row groups, counts and footer hashes come from thirteen exact Parquet
footers; the roster comes from the pinned core manifest. Those facts can be
checked against legitimate originals. The DOI/revision and published support
counts have separate retained primary sources. They do not determine the
ledger's authored role/scope descriptions, `sha256_status`, `census_gaps`,
`memory_limit_inference` or the audit-time facts `endpoint_census_verified=false`
and `metadata_observation_pages_read=0`. The historic ETag is an observed HTTP
header, not an archive content digest. A fresh public read cannot reconstruct
that prior audit's history, and later accepted runs do not rewrite it.

An independent operator therefore needs this one exact audit metadata input
in addition to legitimate originals. Reproducing it automatically would require
making its accepted authored policy and exact historical observation metadata
available under an explicit provisioning decision. Silently replacing its
pin, declaring fresh exposure to be historical zero, copying another run's
receipt or guessing prose would change the existing contract. None is done.
This is a specific provisioning limit, not a missing dataset or a reason to
drop any table/family. The existing binder can consume the two reconstructed
files and the one accepted operator-supplied ledger unchanged.

## Validation and scientific limits

Run generated interface controls from the repository root:

```sh
python3 -I -S -B components/findlay-complete-preparation/metadata/test_provisioning.py
python3 -I -S -B components/findlay-complete-preparation/metadata/test_public_layout.py
```
Fixtures are invented. They cover complete scopes, parser boundaries,
unexpected/missing/duplicate memberships, source substitutions, ignored
outcome columns and no-clobber behavior. Metadata reconstruction is not an
authentic numerical study. It adds no fit, baseline, model score, scientific
qualification or finished-benchmark count. The prior iEta, gamma, regional,
cohort and numerical-reference holds remain.

The workbook contains published statistical outcomes. Public-result exposure
does not disqualify a paper-reproduction task intentionally supplying the paper,
but these utilities do not establish candidate blindness or protected evaluation.

The parsers, tests and explicit benchmark-authored crosswalk are distributed
under the component [MIT license](../LICENSE). This license does not relicense
the official R sources, workbook or external metadata. See the
[component notice](../NOTICE.md) and [preparation guide](../README.md).
