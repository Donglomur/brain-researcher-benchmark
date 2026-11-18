# NEURAL-051 operator metadata preparation

This component restores the metadata-to-design construction missing from the public task package. It builds the protected image/trial mapping and separate public roster for the existing six-panel scorer. It reads three bounded, hash-pinned stimulus-metadata CSV files, never neural responses or image pixels. No authentic metadata or labels are bundled here.

The original target-free `build_design.py` is preserved byte for byte under `legacy/` for provenance, not execution. `design.py` reuses the existing scorer package's preserved split and image-ID implementation. It preserves the original source-seeded query ordering, IDs, case order and design schema. It adds strict CSV field-width/duplicate-header checks, exact integer types, candidate-concept and query-repeat census checks, explicit cross-person exclusion checks, independent paired-ROI structures and a public-only roster projection.

## Operator use

From an already admitted operator environment, after separately authorizing authentic source access:

```sh
python design.py --metadata /operator/stimulus-metadata \
  --pins /operator/source-pins.json --seed-file /operator/private-seed.txt \
  --output /operator/fresh-private-output
```

The metadata directory contains `sub-01_StimulusMetadata.csv` through `sub-03_StimulusMetadata.csv`. The pins object has exactly keys `01`, `02`, `03` and the expected lowercase SHA256 of each source body. Each body is limited to the original 500,000-byte envelope. Metadata fields are exactly `trial_type,session,run,subject_id,trial_id,stimulus,concept`. The seed is operator-private and must have at least32 bytes; this length check does not establish entropy. Neither seed nor source filenames appear in the public roster. Candidate IDs are the original deterministic filename hashes and are **not** evidence of anonymity or hidden-label security.

The new output directory has mode0700; its three files are mode0600 and create-only:

- `design.json`: protected source names, concepts, native trial indices, training/development membership and query-to-candidate mapping.
- `roster.json`: only the exact six-panel query/candidate opaque-ID lists accepted by the existing scorer. Publish this file alone through the separately qualified participant delivery process.
- `PREPARATION.json`: exact output-file hashes, the separately identified canonical roster digest, source pins and explicit qualification limits. It is written last. An interrupted operation may leave a partial private directory; its existence is not completion, and automatic overwrite/retry is not supplied.

`build_rows` is a trusted in-memory construction API. Its supplied pins are declarations until `capture_design` authenticates the source bodies; calling it alone cannot prove acquisition. `write_bundle` is a trusted writer used after construction, not a substitute for input validation. Filesystem permissions and symlink checks are cooperative protections, not a process sandbox or race-proof capability boundary.

## Preserved scientific scope

The original prospective split uses sessions1–8 for training,9–10 for development and11–12 for queries. Query-image and surviving development-image unions are removed globally across all three people. It is image-disjoint, not concept-disjoint. Each person has2,880 training images; development has1,440/720/720 images;1,640 query presentations form1,540 image groups, including100 two-presentation groups. All six panels use the same3,700 candidates, with720 concepts and5/6 candidates per concept. V1 and IT share the same person's query order and target mapping; they are dependent panels, not six independent people.

This component does not verify that source metadata trial indices correctly address a particular response table, select or authenticate independent ROI masks, aggregate response values, authenticate candidate JPEG/PNG pixels, enforce participant access, run a decoder or score a scientific result. Source labels are publicly available in THINGS, so lookup/exposure remains a separate evaluation concern. All direct/viewer/tool/programme conditions and canonical readiness remain unchanged. Authentic packet preparation and paired neural/image joins are still required before evaluation.

Run generated software controls with an existing Python environment containing NumPy (needed only to interoperate with the existing scorer): `python -I -B test_design.py`. Tests construct the complete declared metadata census in memory, check source-index/image joins, deliberate leakage/type/header/hash failures, paired ROI identity, public/private projection, and create-only private output permissions. Generated controls establish software behavior only.
