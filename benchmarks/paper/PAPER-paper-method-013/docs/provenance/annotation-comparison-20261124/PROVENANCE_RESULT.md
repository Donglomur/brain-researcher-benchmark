The four authenticated DeepCaImX and official STNeuroNet FinalGT annotation pairs contain the same 1,050 ROI masks, in the same order, under one of eight prespecified representation conditions: swap the two spatial axes of each h5py-exposed FinalGT mask, then place the complete 487 × 487 mask at zero-based offset `(0,0)` in a zero-filled 488 × 488 array. This is an observed annotation relation; it does not determine the coordinate transform for raw movies.

The complete audit covered recordings 501271265 (237 ROIs), 501704220 (176), 524691284 (355), and 531006860 (282). All eight source arrays were finite exact binary values. Whole-mask comparisons preserved order, duplicate multiplicities, and empty masks; no normalization, threshold, registration, or additional offset search was used. No duplicate masks occurred within a source recording.

| Spatial orientation | Zero-padding offset | Ordered exact matches | Multiset exact matches per source |
| --- | --- | ---: | ---: |
| As stored | (0,0) | 0 / 1,050 | 0 / 1,050 |
| As stored | (0,1) | 0 / 1,050 | 0 / 1,050 |
| As stored | (1,0) | 0 / 1,050 | 0 / 1,050 |
| As stored | (1,1) | 0 / 1,050 | 0 / 1,050 |
| Spatial axes swapped | (0,0) | 1,050 / 1,050 | 1,050 / 1,050 |
| Spatial axes swapped | (0,1) | 0 / 1,050 | 0 / 1,050 |
| Spatial axes swapped | (1,0) | 0 / 1,050 | 0 / 1,050 |
| Spatial axes swapped | (1,1) | 0 / 1,050 | 0 / 1,050 |

All conditions were reported for every recording. The machine-readable companion preserves all 32 per-recording results and source pins. The native comparison completed once in 4.673 seconds; the child reported a 521,748,480-byte peak RSS. Forty-one generated controls and a source review preceded the approved run. Only aggregate results leave the operator process; no individual masks, pixel values, ROI mappings, or per-ROI hashes are exposed.

The sources are pinned to [DeepCaImX commit 305a482](https://github.com/KangningZhang/DeepCaImX/tree/305a4827929b2c6e82e44c5c69b2ea9d410e20a4) and [STNeuroNet commit 6537096](https://github.com/soltanianzadeh/STNeuroNet/tree/6537096d8b2c05858320703418e2a3e2897be928). Exact repository paths, Git blob identities, file sizes, and SHA-256 values accompany the result.

This resolves semantic equivalence for these four annotation pairs. It does not establish causal lineage, the original 512-to-488 movie crop, the selected frame window or 400-frame extraction, the six other original recordings, or the checkpoint and N15/P9 assembly. It does not reproduce the paper's F1 result or demonstrate an improvement. The full original-paper endpoint remains unqualified, and the ready-benchmark count is unchanged.
