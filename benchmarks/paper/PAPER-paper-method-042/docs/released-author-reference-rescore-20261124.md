# UMBRAE released-reference scoring

The complete four-subject released-output rescore recovered the original Table 2 All-category percentages after rounding. This is a reusable scoring reference; it does not reproduce generation from fMRI or establish an improvement.

| Subject | Reported percent | Recomputed percent | Queries | Empty answers retained |
| --- | ---: | ---: | ---: | ---: |
| S1 | 18.93 | 18.9334435717 | 2,419 | 8 |
| S2 | 18.27 | 18.2720132286 | 2,419 | 1 |
| S5 | 18.19 | 18.1893344357 | 2,419 | 2 |
| S7 | 16.74 | 16.7424555601 | 2,419 | 1 |

Both prespecified Python hash seeds (0 and 1) scored the complete 80-cell panel: four subjects, five category groups, three strict IoU thresholds, and mean IoU. The five groups overlap. No seed was selected by agreement with the paper.

All 60 accuracy cells agree across seeds and with the keyed float32 calculation. Every subject/group traversal changed order between seeds, while all query pairs stayed aligned. The largest mean-IoU difference across seeds was 2.98e-8; the largest source-versus-keyed-float64 mean difference was 2.64e-8. There were no float32/float64 threshold-decision differences. These are numerical diagnostics, not an invented scientific tolerance or a claim that all 80 cells are bit-identical.

The frozen calculation retains the first reference box and first extracted prediction. Empty answers remain in the full denominator. The reusable route also retains missing identities as incorrect in keyed scoring, while exposing the original scorer's image-count assertion and independent positional behavior separately.

The CPU operation completed in 24.97 seconds with all owned processes and streams closed. It used an existing contemporary Python 3.12.12 / Torch 2.7.1 / torchvision 0.22.1 runtime and one numerical thread. The declared 2 GiB RAM allowance was a cooperative planning bound, not a measured peak or enforced operating-system quota.

The [complete result](released-author-reference-rescore-20261124.v1.json) contains both full source panels, the canonical keyed panel, precision diagnostics, and immutable input/code identities. The [reference-only route](../implementations/released-reference-rescore-v1/README.md) avoids inventing candidate or control streams for baseline qualification.

Exact paper-producing lineage and native image-index to NSD/COCO/subject-shard joins remain unresolved. Git commit timestamps alone do not prove historical public availability. This result changes the reference-scoring evidence; participant isolation, independent fMRI reproduction, same-task candidate improvement, and full benchmark readiness remain open.

Sources: [paper v2](https://arxiv.org/html/2404.07202v2), [immutable author evaluator](https://github.com/weihaox/BrainHub/blob/d8880b247465576715cf08dacbc5167851ed6820/eval_bbox_rec.py).

The observed agreement applies only to these released outputs; it does not establish interchangeability of the original float32 and keyed scorers for future candidate predictions.
