# Movie10 whole-film development evaluator

This component supplies the missing executable BOLD scorer for a named, narrower development condition of NEURAL-039. It scores the four original people (`sub-01`, `sub-02`, `sub-03`, `sub-05`) and four Movie10 films (`bourne`, `figures`, `life`, `wolf`), retaining all 1,000 native parcel columns. It does not qualify the full Friends plus Movie10 audiovisual task, deliver a participant runtime, or establish direct/viewer interpretation.

The new condition is `movie10_whole_film_development_strict_v2`. Historical protocol, declarations, predictions and exposed-data labels are preserved. Version 2 rejects a constant prediction in any scored parcel before opening targets, as required by the current task; historical version 1 instead assigned that parcel zero. The two versions must not be pooled or silently substituted. Historical submissions need explicit regeneration against the new query schema; this evaluator does not relabel them.

## Scientific endpoint

For each person and held film, retain original response indices `[8, N-5)` separately in every HDF5 segment/run. Concatenate those retained rows in lexicographic native-key order, including both original viewings of *Life* and *Hidden Figures*. Compute Pearson correlation separately over the complete film for every parcel; average equally over 1,000 parcels, then four films, then four people. Negative correlations are retained. There is no Fisher transform, response-dependent selection, per-run normalization, time weighting, noise-ceiling correction or parcel filtering. All 16 case means, 16,000 parcel correlations and four person means are returned. Four people are the biological sample size; no population interval is inferred.

The guards and development folds come from the preserved local Movie10 protocol. They are **not** the native organizer OOD `[5:-5]` trim or its six-film server panel. The organizer source supports the within-film correlation and nesting, while the whole-Movie10 holdout and `[8,N-5)` recipe remain a prospective development choice. Three-TR feature delay and declared feature context must be enforced by future training/participant delivery; scoring array alignment cannot prove that training respected them.

## Operator input and public queries

Use an external, operator-owned `panel.json`; do not commit it or source responses. Freeze its SHA256 before candidate prediction generation. Its exact structure is:

```json
{
  "schema": "neural039_movie10_panel_v1",
  "source_commit": "96750e7017b30cb02f011c11561a3df897695853",
  "subjects": {
    "sub-01": {
      "file": "sub-01_movie10.h5",
      "bytes": "integer source byte count",
      "sha256": "source file SHA256",
      "datasets": {"native HDF5 dataset key": ["native sample count", 1000]}
    }
  }
}
```

This is structural documentation, not a usable or authentic panel: replace the descriptive strings with measured metadata and supply all four people and every native dataset. No authentic inventory or targets are bundled. Dataset shape and key inventories must come from the pinned original source under an approved preparation protocol. The source root contains exactly named per-person HDF5 files; metadata are not accepted from candidate-controlled storage. A matching hash is a byte-identity check, not evidence that the operator selected the correct original source.

Export public queries using the existing NumPy/h5py environment's Python (query export itself uses only the standard library):

```sh
python evaluate.py --panel /operator/panel.json --panel-sha256 FROZEN_SHA256 --output /public/queries.json queries
```

Each query carries participant/film, source revision, native segment/run key, fixed start/stop TR, concatenation offset, shape, TR of 1.49 seconds, and native subject parcel order. No source paths or response values are exported. Native parcel indices are HDF5 columns 0–999, not a new cross-person atlas remapping. A query defines expected ordering; it cannot authenticate the biological truth of a candidate's numeric predictions.

## Submission and scoring

The submission root must contain exactly the 16 `<subject>_hold-<film>` directories. Each contains only:

- `predictions.npy`: little-endian float32, C order, NPY version 1 or 2, exactly the query's time-by-1,000 shape. No object arrays, nonfinite values, constant parcels, truncated bodies or trailing bytes.
- `submission.json`: exactly `{"schema":"neural039_prediction_v2","case_id":"…","query_sha256":"…"}`. Compute the digest from the query object using the supplied `canonical` function: sorted keys, compact separators, no NaN, and one final newline.

```sh
python evaluate.py --panel /operator/panel.json --panel-sha256 FROZEN_SHA256 --output /operator/result.json score --submission-dir /captured/predictions --source-root /operator/responses
```

All prediction files are read, bound to exact queries, checked and captured in memory before any source response file is opened. `--validate-only` returns prediction byte hashes and never opens targets. Scoring verifies each complete HDF5 byte hash, native key inventory, shape, dtype and local storage, then uses all retained samples. Missing or malformed candidates receive `candidate_invalid` and no number; source drift, omitted source runs, constant/nonfinite target parcels or invalid operator metadata fail without a primary score. CLI exits nonzero on scoring failure and refuses to overwrite outputs.

The evaluator performs no fitting and executes no candidate code. Captured prediction hashes do not prove candidate freezing, permitted pretrained exposure, train-only fitting, cross-fold isolation or matching compute budgets. Those remain separate participant-delivery requirements. Source responses remain historically public development data even if their local scorer mount is restricted. Neither organizer hidden/server targets nor historical private target payloads were opened to develop this component.

## Verification and limits

`test_evaluate.py` builds tiny synthetic HDF5 files with the full four-person/four-film/1,000-parcel structure. It checks an independently calculated Pearson endpoint, unequal film lengths, concatenation before correlation, complete coverage, all-predictions-before-target ordering, TR identity changes, missing repeats, source drift, omitted runs, malformed arrays and constant-output failures. These controls establish software behavior, not authentic encoding performance. Run only through the revision's approved lightweight test pool during this construction wave.

Expected numerical dependencies are the existing `numpy==2.2.6` and `h5py==3.13.0` environment; no dependency installation is included. The implementation retains all prediction arrays in memory and hashes four source HDF5 files. Authentic full-panel resource use has not been measured. A source preparation/qualification protocol and lease are required before native runs; the generated controls do not authorize one.

No nuisance/time reference, transcript reference, encoder trial, full audiovisual comparison, real data preparation, source qualification, direct observer delivery or viewer delivery is claimed. Integrating this component requires a separately reviewed registry/contract update; this task-local package does not change current registration status.

## Original Movie10 source inventory preparation

`prepare_panel.py` supplies an offline producer for the operator `panel.json` consumed above. The four exact Movie10 pointers at the pinned organizer commit declare **368,950,005 bytes** in total. Browser-visible pointer text was reconstructed and its Git blob SHA1 matched the existing task inventory for every participant; this verifies the recovered pointer identity, not acquisition or HDF5 contents. The tool performs no download.

| Person | Original HDF5 bytes | Annex MD5 |
| --- | ---: | --- |
| sub-01 | 92,248,907 | `679e60674df5d669e09467c3a84fbba1` |
| sub-02 | 92,262,363 | `5fc31c031b40e5c032c145816dedeb3d` |
| sub-03 | 92,197,356 | `3748698c8261e92bf3be29944829543b` |
| sub-05 | 92,241,379 | `1b16eaea10be5a58052b891806cf10e6` |

The exact source URLs and recovered pointer provenance are in `source-provenance.json`. `sources` exports these fixed expectations without opening payloads or importing numerical dependencies:

```sh
python prepare_panel.py --output /operator/movie10-source-expectations.json sources
```

After a separate approved acquisition/preparation step, stage the four originals as ordinary singly linked files named `sub-01_movie10.h5`, `sub-02_movie10.h5`, `sub-03_movie10.h5`, and `sub-05_movie10.h5` in one source directory. No other files may be in that directory. Under an admitted operator runtime with h5py installed:

```sh
python prepare_panel.py --output /operator/panel.json prepare --source-root /operator/responses
```

Preparation streams all four files to verify their exact annex extents and MD5s before parsing any HDF5 container, observes SHA256s for the emitted panel, and keeps the same descriptors open until metadata checks finish. It inspects local dataset keys, shapes, float32 dtype and storage metadata; it rejects soft and external links, virtual/external storage, missing repeat viewings and the existing evaluator's other panel violations. It never indexes response datasets, casts values, drops parcels, normalizes responses or substitutes a different participant. The output retains the current `neural039_movie10_panel_v1` schema and must be frozen by hash before candidate generation. Existing-file outputs are refused.

`test_prepare_panel.py` tests generated HDF5 metadata, exact pointer reconstruction, all-four identity checks before parsing, schema/repeat rejection and mutation detection. No authentic source HDF5, neural array, model or candidate was used to construct or test it. The numerical source dtype, complete source key inventory, finite responses, sample counts and anonymous payload retrieval therefore remain unverified in practice. A successful future metadata preparation would still not prove train-only fitting, temporal-context isolation, authentic numerical performance, full audiovisual delivery or native understanding.
