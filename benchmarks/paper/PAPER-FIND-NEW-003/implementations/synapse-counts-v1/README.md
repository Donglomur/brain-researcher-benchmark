# Original BANC synapse evaluation: source count reconstruction

This component authenticates the author's 16-cutout evaluation CSV and reconstructs its pooled precision, recall and F1 from integer TP/FP/FN. It preserves the cutout IDs, neuropils, regions and per-cutout diagnostics. It is an executable count-reconstruction component for the retained secondary synaptic-link endpoint (Extended Data Figure 2b). The [authoritative task](../../task.json) retains sensory-to-effector graph organization as its primary scientific scope; reconstructing these synapse counts cannot discharge primary graph reproduction or improvement. This component is neither a detector rerun nor an admitted paper-improvement evaluator.

For this retained secondary component, the assessed result is reconstruction of the released count table. Full detector reproduction, paired paper+data versus paper+data+author-code delivery, and detector improvement remain unqualified. The [primary outcome contract](../../outcomes.v1.json) remains unavailable; this component does not select a primary numerical panel, justify a primary improvement comparison, or alter the historical graph runtime or canonical task/contract.

## Source recovered

The [pinned author table](https://github.com/htem/BANC-project/blob/2e78ce38e946ab80e120a42f504a019b3a567fef/data/synapses/251013_synapse_evaluation.csv) is 6,299 bytes, SHA-256 `5e04a7856146118fedb0ca15a63344b9372ac36d76d281cbdcb5d16c837f418f`, Git blob `097aecf3d15879aa6790ce2dbd99a18e347acb89`. Its identity and complete row roster are in [source_pin.json](source_pin.json). Raw source bytes, review-state links and authentic result JSON remain external to Git.

The existing pinned `R/figures/panels_synapse_review.R` reads this exact file in its “Synaptic manual review” block. The [paper's Methods, “Synapse detection evaluation”](https://pmc.ncbi.nlm.nih.gov/articles/PMC13518251/) and Extended Data Figure 2b define the endpoint: both synaptic partners must be correct; sum counts over all 16 cutouts of one fly before computing dataset metrics. The separate 4,648-synapse sparse review and neurotransmitter classifier are different endpoints.

The recovered table contains 16 rows and no pooled row. `counts.py` computes the pooled result once, rejects missing, duplicate or changed cutout/region identities, requires integer counts, retains undefined metrics as undefined, and checks source metric displays without allowing them to replace the count-derived metric. If explicitly supplied in a future table, a pooled row is checked separately and excluded from the sum. The parser handles the author's trailing notes column without consuming it as a numerical field.

## Reconciliation findings

- The source counts total TP=793, FP=119 and FN=218. The resulting F1 is `1586/1923`, approximately 0.824753. Nearest two-decimal rounding gives 0.82, whereas the paper reports 0.83. Preserve both; source-table reconstruction does not by itself reconcile the published headline or certify the original detector baseline.
- Two source F1 displays (`SPS_left` and `HTct_left`) differ from the exact count-derived values by more than half their last printed unit, but less than one unit. The report preserves these differences as diagnostics; it never edits the source counts. The cause of those display differences is not established.
- All rows declare 16×16×45 nm resolution. Fifteen bounding boxes span 128×128×16 voxels (2,048×2,048×720 nm). `cutout001` literally spans 12×10×2 voxels (192×160×90 nm), inconsistent with the paper's approximate 2×2×0.7 µm cutouts. No coordinate is repaired or substituted. The imagery cohort remains unresolved until this is reconciled against authoritative original review states.
- First/final expert-review state links are present in the source. Their annotation payloads were not retrieved; matching, ambiguity adjudication, immutable segmentation/partner identities, original training overlap, checkpoints and image-version binding remain unresolved.
- The table is pinned to the already registered author-source commit. Release tag `v2.0.5` resolved to annotated tag object `f8221fe02a048b5175a387bcb6ba791f8dd3d9e9`; dereferencing that object hit an HTTP 403 API rate limit. Equivalence to the original Zenodo release is not asserted.

## Run

Python standard library only; no package installation, R graph runtime, images, model, network or fitting is required. Acquire the exact pinned source separately under the operator's source protocol. Keep authentic outputs outside the repository:

```sh
python3 -B inspect_author_table.py /external/source/251013_synapse_evaluation.csv \
  --output /external/evidence/source_count_report.json
python3 -B -m unittest -v test_counts
```

During the parallel construction wave, both commands must run through the shared verified `test_pool.py`; these examples document the underlying commands, not an exception to the resource policy. Existing output files are never overwritten. The CLI verifies bytes and SHA-256 before parsing and rejects repository-local output paths.

Tests use explicitly generated fixtures. They distinguish pooled F1 from mean cutout F1, reject cohort/count/source tampering, preserve source precision diagnostics and literal geometric discrepancies, and exercise both 16-row input and an explicitly declared extra pooled row. They establish software behavior, not prediction accuracy or independent-animal replication.

## Integration boundary

Propose updating source-recovery blockers to distinguish recovered count-table IDs/metadata from unresolved image, annotation, split and matching provenance. Keep full reproduction and improvement dispositions unresolved. No benchmark score, binary reward, uncertainty threshold, candidate method or current-SOTA claim is introduced here. The author-count source must remain evaluator-owned in a future paired participant protocol; exposing the recovered review annotations to candidates would need an explicit exposure policy.
