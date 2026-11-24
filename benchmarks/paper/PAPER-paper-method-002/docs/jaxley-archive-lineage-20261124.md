# Recorded retinal runs differ from the maintained default

The author’s [Zenodo result archive](https://zenodo.org/records/14166049) contains two retinal training runs with concrete configurations and logs. Neither establishes the exact final-paper realization. The earlier archive also does not prove that current author defaults are wrong for the later final paper. Both must remain distinct from the maintained 128-test-row route; matching 1,008 optimizer updates does not establish the same experiment.

| Property | Both archived configurations | Maintained streamed route |
|---|---:|---:|
| Training / validation / test rows | 9,216 / 3,072 / 3,072 | 12,185 / 3,047 / 128 |
| Validation fraction after removing test rows | 0.25 | 0.20 |
| Soma radius | 5.0 | 7.5 |
| Output scale | 60.0 | 40.0 |
| Batches per epoch | 36 full batches of 256 | 47 batches of 256 plus 153 rows |
| Planned epochs | 28 | 21 |
| Planned optimizer updates | 1,008 | 1,008 |

All routes use 15 fields and 147 recording sites. The archived logs report 15,360 rows and 287 input connection columns. Both configurations request 1,000 iterations; the observed schedules process whole epochs, so 28×36 and 21×48 both give 1,008. That arithmetic does not remove the split, morphology or output-scale differences.

The `2024_05_30__10_55_30` log records 28 complete epochs, 1,008 completed batches and a final `Finished` marker. The `2024_08_01__20_57_21` log records 23 complete epochs and five batches of the next epoch, 833 completed batches in total, with no `Finished` marker. This describes the retrieved logs; it does not prove that no complete copy of the August run exists. Neither run was selected by agreement with a published score.

The directory lists `data/train_inds.pkl`, `data/val_inds.pkl`, `data/test_inds.pkl` and numbered parameter checkpoints for each run. Those contents were not decoded. Their names make ordered split and checkpoint recovery a concrete next step, but do not authenticate the final figure, source revision or 607-parameter realization. The prior primary-literature audit records ten epochs in the [final Methods](https://www.nature.com/articles/s41592-025-02895-w) and 560 gradient steps in [Supplement Table 1](https://static-content.springer.com/esm/art:10.1038%2Fs41592-025-02895-w/MediaObjects/41592_2025_2895_MOESM1_ESM.pdf). Neither archived schedule reconciles those statements.

Four exact HTTP 206 ranges received 111,062 bytes from the 2,004,411,212-byte archive. They cover its complete 298-entry directory and eight selected YAML/log texts, totaling 195,464 decompressed bytes. Selected local headers, directory entries, data descriptors, sizes and CRCs agree. The server supplied no ETag or Last-Modified validator, and the whole-archive publisher MD5 was not verified. The tail range also transported 26,088 opaque compressed bytes from a final PNG plus its 16-byte descriptor; the image was not decoded. No checkpoint, prediction array or target values are included here.

[Machine-readable source pins and comparison](jaxley-archive-lineage-20261124.json) retain both runs and the exact checked maintained source files. This is provenance evidence, not a new fit, paper reproduction, improved result or benchmark-readiness claim. Scientific execution and scoring sources remain unchanged.
