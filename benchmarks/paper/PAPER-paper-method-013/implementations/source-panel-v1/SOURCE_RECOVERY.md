# DeepCaImX source recovery and current execution limit

This package now converts the complete original ten-file manual ROI panel and scores a complete segmentation submission using the retained evaluator's strict IoU rule. The real author masks were authenticated, converted and exercised through the scorer. No movie-to-mask model was run, and the published F1 of 0.847 ± 0.037 has not been reproduced. See [SOURCE_PANEL.md](SOURCE_PANEL.md) for executable conversion and scoring commands.

## What is authenticated

The ten original MATLAB `seg` arrays match both the official Git blobs in author revision `305a4827929b2c6e82e44c5c69b2ea9d410e20a4` and SHA256 pins in [roi_sources.json](roi_sources.json). Together they contain 1,563 ROIs. Conversion preserves their 488×488 spatial coordinates and overlapping masks; it only moves the ROI axis. Full-panel identity and empty-prediction software controls passed against the actual converted targets. These are arithmetic controls, not model-performance results. The conversion and controls took 56.7 seconds with peak RSS 869,400,576 bytes; the external cache and receipts occupy 372,241,405 bytes. No target arrays are distributed here.

The [official Allen API](https://api.brain-map.org/api/v2/data/query.json?criteria=model::OphysExperiment,rma::criteria,[id$in501271265,501704220,524691284,531006860,603516552,604145810,607040613,669233895,671162628,679353932],rma::include,specimen(donor),targeted_structure) identifies **eight donors across the ten videos**. Recordings 603516552/604145810 share donor 593402240; 669233895/671162628 share donor 657195961. Four recordings are outside VISp. This conflicts with the paper's ten-mice/primary-visual-cortex wording. Keep the original arithmetic mean over ten videos; any paired uncertainty must respect the actual donor clusters.

The official full-version checkpoint is 7,316,832 bytes, Git blob `93ae42338f0e0922621a2ac833f6fa5f4df8582d`, SHA256 `608bc595d52bc135748fac1226973eb85fd09f93e414762e212eef01a02ccc5c`. Its HDF5 configuration was inspected without executing TensorFlow or deserializing executable Lambda functions. The stored Keras 2.9.0 model takes 400×64×64×1 input, has eight neuronal output channels, and uses temporal kernels 3,3,1 with valid padding, implying 396 trace samples under the released demo temporal convention. Native output shapes were not verified. This authenticates the released full-version artifact, **not its equivalence to the paper's N=15/P=9 architecture**.

```sh
python checkpoint.py inspect --checkpoint /external/weights/full-model.h5 \
  --output /external/evidence/checkpoint.json
``` The earlier Zenodo v1.0.0 archive contains the mini checkpoint and must not be substituted for the full artifact.

## Full source intervals fit the capacity, but paper mapping remains unresolved

All ten official motion-corrected HDF5 movie objects are accessible through the [Allen source route](https://github.com/AllenInstitute/AllenSDK/wiki/Use-the-Allen-Brain-Observatory-%E2%80%93-Visual-Coding-on-AWS). Structural inspection reads only 2,512 bytes per movie using exact HTTP 206 ranges, strong ETag checks and fixed cumulative transfer limits. All ten store `data` as time×512×512 uint16, uncompressed, with one frame per chunk. The full source objects total 613,364,551,600 bytes. A complete 5,000-frame interval from each contains exactly 26,214,400,000 pixel bytes (24.41 GiB), plus HDF chunk-index traffic. A float32 488×488×5000 cache would add 47,628,800,000 bytes for ten videos, so a bulk raw-plus-float cache would exceed the initial 45 GiB allocation. Sequential conversion/inference or preserved uint16 source slices is necessary.

```sh
python range_source.py --recording-id 501271265 --output /external/evidence/movie-header.json
```

Reserve source-transfer capacity before invoking the inspector. Its output describes physical HDF storage and explicitly leaves paper mapping unauthenticated. It refuses a server's whole-file fallback. `visititems`, `get_storage_size` on chunked data, and `get_chunk_info_by_coord` traversed extensive source chunk indexes during investigation; the accepted inspector directly opens `data` and avoids these calls. Failed bounded inspections were retained as acquisition cost. No pixel payloads were evaluated, and no original 5,000-frame movie slice was acquired.

The paper states that the source frames were cropped to 488×488 and that 5,000 consecutive frames were selected. Author filenames name frames 18501–23500. The inspected code loads a prepared MATLAB movie; it does not recover the raw HDF frame index base or the spatial crop origin. A centered crop or assumed one-based index would be a new choice. Source-file names, strong ETags and matching array dimensions cannot establish those missing transformations.

## Why an original full-model replay remains blocked

| Component | Paper | Released source / current evidence |
|---|---|---|
| Full model | N=15, P=9 architecture | Authenticated full checkpoint has eight outputs and 396-sample traces; historical weight equivalence unresolved |
| Input mapping | 488×488×5000 experimental clips | Official physical movies are 512×512; exact crop and raw frame-index origin absent |
| Tiling | 64×64×400, 11-pixel spatial overlap, 9×9×13 tiles | Generic author MATLAB tailor defaults to 100 temporal frames; the retained geometry planner is not a native reconstruction |
| Assembly | Spatial trace correlation >0.95; temporal footprint IoU >0.9 | Full historical reconstruction and boundary/trace-support behavior unqualified |
| Trace reference | Bilateral filtering, temporal lowpass background removal and overlap correction | Demo subtracts a spatial Gaussian, then applies bilateral filtering, and displays four ROI means |
| Segmentation | Highest-IoU prediction per reference, strict IoU >0.5 | Matching collisions remain unspecified; retained scorer refuses ambiguity |
| Summary | Ten-video macro F1, SD 0.037 | Scorer reports macro mean and both SD conventions explicitly; no convention is silently inferred |

The next scientific prerequisite is exact original movie-to-reference mapping and paper-equivalent full checkpoint/assembly evidence. A newly trained replacement, a mini-model run, an arbitrary frame/crop choice or a synthetic-video demo cannot resolve it. The implementation permits primary segmentation calculation without fabricated trace targets, runtimes or candidate methods, while keeping the paper's trace/runtime endpoints and full baseline qualification outstanding.
