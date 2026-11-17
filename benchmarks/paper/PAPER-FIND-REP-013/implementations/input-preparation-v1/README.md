# Purkinje public input preparation

This fills the missing public archive-to-provider step for the original ten-cell
observations, supporting descriptive reproduction and the existing numerical
calibration. It prepares all 15 files in the original
[input pins](../registered-runtime/program-v1/INPUT_PINS.json), plus the unmodified
author RMarkdown. An optional exact historical article capture completes the
provider needed by the existing [paired packet builder](../paired-access/README.md).
The paired builder supplies its own shared task, schema and attribution files.

Descriptive reproduction is a first-class outcome, separate from performance
improvement. The current registered task remains **ineligible for performance improvement**:
comparative anatomical estimands have no ordered method-performance endpoint.
These inputs support reconstruction of the original observations; their local
numerical reference is not a source-paper performance baseline. Original-procedure
and whole-paper reproduction remain unqualified, for the source limits below.

The predecessor preparation lived in a private authoring checkout and depended on
its directory layout, NumPy, a separately extracted source-semantics record and
mutable extraction contents. This implementation reads the fixed public release
directly, reconstructs the source excerpts from numbered RMarkdown lines, and
checks every prepared byte against the already published input pins. It never
executes R, analyzes SWC geometry, opens private references or runs a participant.

## Operator command

With CPython 3.11+ and authenticated local source files, use canonical paths whose
parents are not symlinks. The output must not exist; its parent must exist.

```sh
python3 -I -B prepare.py \
  --archive /operator/sources/Dendrite-reconstructions.zip \
  --rmd /operator/sources/HumanvsMousePaperAnalysis.Rmd \
  --output /operator/fresh-purkinje-provider \
  > /operator/preparation-receipt.json
```

The archive filename on disk may differ; its exact byte identity may not.
`--paper /operator/sources/paper.html` optionally includes the 622,639-byte
historical publisher capture pinned by the paired contract. Without it, the
receipt explicitly records `paired_article_provisioned: false`. A current HTML
response must not be accepted by loosening that historical pin. The provider
also contains the historical program `TASK.md` and `SCHEMA.json`; the paired
builder ignores these copies and uses its own contract-bound files.

Every prepared original input must match its existing byte count and SHA-256
before any output directory is published. The generated author totals use the
Sholl export's `DEND-LENGTH` column, in micrometres, and the historical 12-digit
serialization. `math.fsum` replaces NumPy's reduction; agreement is required by
the final exact pin check, never assumed. A rounding difference fails closed and
requires investigation, not pin replacement. On a complete successful preparation
the receipt contains 16 output identities (17 with the article), with no local
paths or anatomical target values. Store source bodies and outputs outside Git.

The tool performs no download. Acquisition and authentic preparation must follow
the active operator's resource protocol. Existing protected runtime/reference
provisioning and paired execution qualification remain separate work.

## Source and unit fidelity

- Source: Busch and Hansel, [eLife article](https://doi.org/10.7554/eLife.105013.3),
  [Zenodo v3 record 15066697](https://zenodo.org/records/15066697), CC BY 4.0.
  Exact source and inherited input identities are in [SOURCE.json](SOURCE.json).
- All ten SWCs and all ten Sholl exports are required. No component, point type
  or cell is filtered, repaired or substituted. The release's literal filename
  `H13 Split 1 Reconstructionswc.swc` maps to `raw/H13_Split_1.swc`.
- SWC bytes remain unchanged, including the seven-column files and H13 Split 1's
  disconnected components. The preparer does not produce branch or section
  tables and cannot establish their numerical correctness.
- Human filename prefixes stay source specimen labels. Mouse individual mapping
  stays unavailable. Ten cells are not ten independent donors.
- Author Sholl totals remain explicitly answer-bearing public development
  observations. They are not hidden scientific truth and do not replace raw
  reconstructions.
- The source snippets retain both the radius-to-diameter declaration and later
  reload without that conversion. Historical R execution state, H13 Split 1
  source/export mismatch, donor mapping and complete paper coverage remain open.

## Qualification boundary

`test_prepare.py` exercises the actual capture, complete-panel derivation,
exact-output authentication and atomic publication path on generated controls.
It contains no authentic anatomy. All 11 generated controls passed in the shared
pool; [VALIDATION.json](VALIDATION.json) records their source and receipt identities.
This result is a software check, not native
source preparation, reproduction, improved scientific performance or an agent
trial. The external handoff records the exact test command and outcome from
the shared test-pool run. No historical input pin, scorer, task or prior evidence
has been changed.
