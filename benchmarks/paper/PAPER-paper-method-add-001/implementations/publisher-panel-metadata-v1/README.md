# Original NoMAD monkey-panel metadata

This component prepares the original relative-session calendar and complete
directed-pair identities from the publisher's source-data workbook. It supplies
previously missing input identities for both paper reproduction and improvement
on the same task. Those remain separate outcomes; neither is evaluated here.

The [publisher source data](https://pmc-oa-opendata.s3.amazonaws.com/PMC12089531.1/41467_2025_59652_MOESM4_ESM.xlsx?md5=93d1ffcae2bf540a9bbe474f502a72a4)
for [the original paper](https://www.nature.com/articles/s41467-025-59652-y)
has two main monkey sheets. Inspection authenticated the 3,077,326-byte workbook
to SHA-256 `58c45c042767ffeda0c03e34446656dc3ddb7994a52c157436d0c8a6adfd7ab4`
and the independent publisher MD5 `93d1ffcae2bf540a9bbe474f502a72a4`.

| Source sheet | Source task | Sessions | Directed pairs per method | Null-query anchor rows per method | Total source rows |
| --- | --- | ---: | ---: | ---: | ---: |
| Figure 3 | force | 20 | 380 | 20 | 1,600 |
| Figure 4 | reaching | 12 | 132 | 12 | 576 |

Both sheets contain the four literal method labels `NoMAD (causal)`,
`Aligned FA`, `ADAN`, and `Static decoder`. All 2,048 transfer rows and 128
null-query anchor rows are retained with their exact worksheet row numbers.
The latter have a literal `None` in **Day K Dataset** and an ordinary relative
day in **Day 0 Dataset**. The paper's Figure 3d/4d captions describe the separate
within-day reference-decoder results; the output preserves the source's null
label instead of fabricating a diagonal source row.

The source day labels are:

- Force: 0, 1, 2, 6, 7, 8, 9, 10, 21, 25, 26, 27, 28, 29, 32, 37, 38, 40, 91, 95.
- Reaching: 0, 1, 2, 3, 9, 10, 14, 15, 16, 36, 37, 38.

These are relative-day coordinates. They do not identify raw recording
filenames, channel identities, trials or evaluation bins. The calendars yield
22 force and 16 reaching directed pairs separated by one day. That is a derived
calendar subset, not a demonstrated row correspondence to Supplementary
Figure 7, which remains separately unresolved.

## Prepare the metadata

Supply the exact publisher workbook outside the checkout. From the repository
root, the standard-library Python 3.11 command is:

```sh
python3 -I -B benchmarks/paper/PAPER-paper-method-add-001/implementations/publisher-panel-metadata-v1/panel_metadata.py \
  --workbook /operator/source.xlsx \
  --output /operator/new-panel-metadata.json
```

The command verifies the complete workbook bytes, follows its internal sheet
relationships, and binds the result to every consumed XML member's byte hash.
It requires all four methods, both complete panels, each directed pair once
per method, and one null-query anchor per session/method. It preserves original
source row order alongside canonical directed-pair ordering and signed/absolute
day gaps. It refuses missing or duplicated rows, aliases, identity formulas,
fractional days, incorrect task labels and incomplete session coverage. The
output destination must be new.

The authentic Figure 3 header includes 21 empty, styled cells F1:Z1. Their
addresses are retained as formatting metadata. Populated extra columns refuse;
they are never silently discarded. This distinction was found by authentic
source execution and is covered by a generated regression.

Column E contains published results. XML package bytes necessarily contain
those cells, but the program does not decode their values, convert them to
numbers, retain them in its output or compute scores. There are no neural
recordings, private targets, published score arrays or author software bundled
in this component. `parse_workbook` is a structural parser for generated
controls; only `prepare_source_roster` authenticates the pinned publication
body. These functions are trusted operator utilities, not a candidate sandbox.

## Evidence and remaining scope

Generated controls exercise full-panel coverage, direction, anchor integrity,
task/method identity, score opacity and refusal of fixture provenance. They do
not establish neural-data preparation or model performance. Run the tests with
`python3 -I -B .../test_panel_metadata.py` under the project's reviewed test pool
when operating in this parallel build.

This is a concrete source-metadata preparation component. It does not alter
the predecessor recovered operators or the current task contract. The source
workbook is published evidence, never a newly reproduced author result. Source
force and reaching R² reductions remain separate over all 380 and 132 pairs;
there is no pooled score or newly chosen split. Their source-author replay,
original trial/channel/event support, preprocessing and fixed-decoder lineage
remain unresolved. No behavior-target access or adaptation is performed.

All supplementary and human obligations remain in scope. In particular, the
128 anchors here belong to four main-figure methods and do not replace the
predecessor's broader 160-anchor/five-method programme. Relative calendars
partially resolve U09; they do not resolve recording-file joins, S7 row lineage
or the T11 chronology. No historical source-qualification flags are changed.

Reproduction and improvement may use this same complete roster once the other
source obligations are resolved. Paired paper-plus-data versus
paper-plus-data-plus-author-code conditions still require independently
admitted data access and rights; this extractor neither supplies nor clears
the restricted original software. No reproduction result, improvement, SOTA
claim or ready benchmark is established.

The independent extractor contains no copied original-software bodies. Raw
publisher files and extraction outputs stay operator-owned and outside Git;
their applicable source terms remain separate from repository code licensing.
