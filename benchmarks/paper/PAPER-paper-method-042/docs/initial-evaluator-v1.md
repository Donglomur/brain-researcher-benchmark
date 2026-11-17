# UMBRAE REC grounding evaluator

This package implements a complete local scoring and paired-control component for existing BrainHub referring-expression comprehension (REC) outputs. Its primary endpoint is **All-category accuracy at strict IoU > 0.5, separately for subjects S1, S2, S5 and S7**. This is a prospective, paper-grounded endpoint selection for the canonical task, whose registered grading boundary was unresolved. It does not complete the broader training, transfer, adaptation, captioning or whole-paper requirements. Scientific qualification remains unknown.

The implementation consumes already extracted bounding boxes, computes geometric overlap, preserves every image/category query, reports the five published salience groups and evaluates paired candidate/baseline/neural-free/shuffled-neural comparisons. It performs no acquisition, model loading, training or inference. No native reference execution or empirical performance is claimed.

## Scientific semantics and source grounding

[UMBRAE v2](https://arxiv.org/html/2404.07202v2), sections 4.4 and B/C, motivates grounding and the accuracy/IoU endpoints. The [canonical author inference](https://raw.githubusercontent.com/weihaox/UMBRAE/8c1795c434a41cdd38ce6628b7e1a774f31d9483/umbrae/inference_rec.py) averages repeated fMRI observations, processes 982 shared test images for subjects 1, 2, 5 and 7, and queries known object-category expressions. This is category-conditioned REC, not free object discovery. Query category names are permitted inputs; reference coordinates are operator-side answers.

The [pinned BrainHub scorer](https://raw.githubusercontent.com/weihaox/BrainHub/4838666f1a04d0521c2184fa50b5b77e7e7ac5ee/eval_bbox_rec.py) selects `ground_truth[image][category][0]` and `prediction[image][category][0][0]`. This package preserves that rule: no optimal assignment, best-overlap selection or all-instance averaging. The population of 5,829 annotated boxes is therefore larger than the scored image/category query population. Queries have equal weight within each subject/group. Accuracy uses **strict `>`**, including secondary thresholds 0.3 and 0.7. IoU is intersection area divided by union area on continuous normalized xyxy coordinates; no pixel-inclusive `+1` is used. The author's uniform multiplication by 1,000 does not change this geometry.

All, Salient, Salient Creatures, Salient Objects and Inconspicuous use the fixed [source category membership](https://raw.githubusercontent.com/weihaox/BrainHub/4838666f1a04d0521c2184fa50b5b77e7e7ac5ee/data/processing/coco/coco_categorized_labels.json), with 80/28/11/17/52 classes. A group without queries returns null metrics and zero count; it never becomes a perfect score.

Explicit prospective corrections to released scoring:

- Responses join by image ID and category, avoiding the source's independent dictionary/set traversals and truncating `zip` behavior. Extra image/category keys reject the input; omitted images/categories remain zero-IoU failures with their original denominator.
- Empty extraction, null response, malformed nesting, nonfinite/out-of-range coordinates, reversed corners and boolean coordinates count as prediction failures. Zero-area predictions yield zero overlap. No clipping or corner repair occurs. Malformed reference boxes reject the entire evaluation; reference queries are never silently dropped.
- Duplicate JSON keys and nonfinite JSON literals reject the file. The scorer accepts extracted `rec_response.json`, not raw text; it does not replace the author's text parser with a more permissive parser.
- The additional paired summary pools equal-population subject/query differences for All-category accuracy. This equals a subject mean here, and is a prospective comparison summary rather than a replacement for the published per-subject endpoint. Optional uncertainty resamples the shared target image jointly across subjects and all its queries, recalculating the query-weighted denominator. It is conditional on these four subjects and cannot support new-subject inference. Empty-query images remain eligible image clusters; zero-query resamples are counted and omitted, with requested/valid draw counts reported.

BrainHub commit `4838666f...` is the newly pinned current snapshot, not an asserted paper-time snapshot. Complete URL, version and inspection metadata are in `../implementations/initial-evaluator-v1/source-provenance.json`.

## Operator input boundary

Run `grounding.py --contract CONTRACT --annotations ANNOTATIONS --image-order ORDER --output NEW_RESULT`. All arguments are local files. The output path must not exist. Relative response paths resolve against the contract's directory. Python 3.10 or newer and its standard library suffice.

`ANNOTATIONS` is the native BrainHub object: image-index strings map to category names, which map to lists of normalized `[x1,y1,x2,y2]` boxes. All reference boxes must have positive area representable in binary64 (underflowed areas reject); only the first is scored. Image indices are contiguous from `"0"`. Empty-category images are retained. Do not provide raw COCO pixel boxes: the paper/source square-image transformation has not been reimplemented or independently qualified here.

`ORDER` maps those exact image indices to unique, stable NSD/COCO stimulus identifiers. An independent operator must establish the correspondence between NSD test-shard iteration, BrainHub annotation indices and source image content. This file is not inferred from dictionary order, and all subjects use the same order. Repeated fMRI measurements are already averaged upstream; they must not appear as extra indices.

`CONTRACT` contains:

- `task_id: "PAPER-paper-method-042"`, `profile: "paper_population"` or `"engineering_controls"`, and `subject_design: "shared_subjects_1_2_5_7"`.
- `brainhub_revision: "4838666f1a04d0521c2184fa50b5b77e7e7ac5ee"`; `annotations_sha256` and `image_order_sha256`, verified against input bytes.
- `all_images_sha256: "1a313a2d4796f14aa4a930afb0ce94a1080ae9ea0482862f597a1b0afd539078"`. This identity is pinned from HF LFS metadata at dataset revision `77d4f8e1c1d6d417a363ac32c380f12924bd92c8`; no tensor was fetched or locally verified. The tensor is not needed by this scorer.
- `exposure` with SHA-256 declarations `training_neural_sha256`, `pretrained_language_sha256`, `pretrained_image_sha256`, `prompt_sha256`; `training_subjects: ["S1","S2","S5","S7"]`; unique `training_stimulus_ids`; and nonnegative integer `training_presentations`. Native profile requires nonempty training exposure. Evaluation/training stimulus overlap rejects the contract.
- `runs` with exactly `candidate`, `official_baseline`, `neural_free`, and `shuffled_neural`. Each supplies a nonempty `model_id`, a `checkpoint_sha256`, an identical copy of `exposure`, and `responses` mapping every subject to its native response JSON. `neural_condition` must respectively be `observed`, `observed`, `none`, and `permuted`.
- Both control runs require `control_of: "candidate"` and the same declared checkpoint hash as the candidate. This prospectively fixes controls to the candidate weights. Checkpoint pairing and actual intervention fidelity remain unverified declarations.
- The shuffled run also supplies `source_image_by_target`, mapping each subject to a complete within-subject permutation of image IDs, with no fixed points. This records neural input assignment; it is not a post hoc shuffle of candidate responses. The code validates its declared bijection but cannot attest that a producer actually executed it.

The complete contract example is generated by `make_control.py`; its SHA placeholders and generated training identities are expressly engineering data. `paper_population` additionally requires exactly 982 images and 5,829 total reference boxes within the fixed 80-class ontology, and never establishes native authenticity from cardinality alone. Observed class coverage is reported rather than requiring a minimum class frequency from unverified native membership. `engineering_controls` allows small generated populations while retaining all four comparison subjects. Both profiles always retain scientific/reference holds. This component specifically tests held-out **stimuli** with the shared-subject training design; it does not label these subjects held out or implement adaptation.

Output includes input byte pins, population counts, per-subject/group accuracy and IoU, extraction-failure counts, all per-query results, paired deltas and shared-image bootstrap intervals. Default bootstrap is 1,000 draws, seed 0; `--bootstrap-draws 0` disables intervals. The maximum of 10,000 bounds scorer computation and is an engineering limit, not a scientific power recommendation. Candidate isolation must be enforced by the calling operator: the scorer is trusted to read references and all arms, while candidates must receive only permitted neural inputs and query labels.

## Generated engineering verification

From repository root:

```sh
python3 -m unittest discover -s benchmarks/paper/PAPER-paper-method-042/implementations/initial-evaluator-v1/tests -v
python3 benchmarks/paper/PAPER-paper-method-042/implementations/initial-evaluator-v1/make_control.py /tmp/umbrae-grounding-control
python3 benchmarks/paper/PAPER-paper-method-042/implementations/initial-evaluator-v1/grounding.py --contract /tmp/umbrae-grounding-control/contract.json --annotations /tmp/umbrae-grounding-control/annotations.json --image-order /tmp/umbrae-grounding-control/image_order.json --output /tmp/umbrae-grounding-control/result.json --bootstrap-draws 1000 --seed 7
```

Use a new control directory on each invocation. The four-image generated control has four scored queries, five annotated boxes, one empty-query image and four subject labels. Candidate acc@0.5 is 0.75, mean IoU is 0.875; candidate minus baseline is 0.5. These values are hand-constructed software checks, not UMBRAE or NSD results. Independent control derivation covers exact-threshold behavior, first-box semantics, query weighting, keyed alignment, missing-response denominators, salience partitions and shared-image grouping.

## Requirement mapping and remaining gates

| Canonical requirement | This component | Remaining gate |
|---|---|---|
| `/primary_outputs/0`: held-out NSD decoding | Native output scoring for all four subjects and complete stimulus counts | Author training/inference and authentic reference agreement not run |
| `/primary_outputs/1`: matched baseline/transfer comparison | Paired official-baseline and neural control scoring; matched exposure declarations | Baseline competence, actual budgets and adaptation/transfer execution not established |
| `/evaluation/comparability` | Neural-free and within-subject shuffled arms required; prior/data/prompt identity declarations compared | Declarations do not verify execution or prior contamination |
| `/evaluation/unresolved_grading` | One explicit primary downstream endpoint and exact extracted-response scoring rule selected prospectively | Independent native annotation/order and complete membership qualification |
| `/next_implementation_action` | Versioned scorer/category map and all_images LFS identity metadata pinned | Annotation content SHA/native order unresolved; no runtime/GPU allocation |
| `/access_conditions` and `/holds` | Original rights, protected reference, exposure and scientific gates retained in every report | NSD/stimulus, COCO and model terms require separate review |

The canonical task and historical records remain immutable. No task-count or scientific-qualification increase follows from this package. Current resources: standard-library CPU engineering checks only; zero native scientific runs, zero GPU/model/API execution, no installations, checkpoints, NSD archives or image tensors. One independent source reviewer accessed an annotation blob HTML page while seeking metadata; it may have embedded annotations and was discarded without extracting, saving or scoring labels. This source exposure is recorded rather than hidden. Official code licensing does not resolve participant, stimulus or pretrained-model rights.
