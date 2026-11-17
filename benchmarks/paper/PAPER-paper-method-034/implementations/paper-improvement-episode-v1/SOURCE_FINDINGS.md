# MARBLE author-baseline admission findings

Checked on 16 November 2026. The active same-task paper improvement disposition is **source unresolved**. No author numerical baseline, paper reproduction, improvement or SOTA result is established here.

MARBLE is a performance-bearing methods paper with accessible official code and a versioned 22,055,089-byte real-data file. Those features make it a useful next admission target. Other examined packages had larger or missing inputs (MotorMINT), extensive unqualified multi-dataset baselines (CBraMod), or unresolved session/masking support (DFINE). Accessibility is a reason to investigate MARBLE, not to relax the same-task requirement.

## Published task and official-source differences

| Evidence | Observed source fact | Consequence |
| --- | --- | --- |
| [Published paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11903309/), Figure 5d and Methods, “Linear maze experiments in rats” | Figure 5d reports within-rat1 mean position error and standard deviation, with 2,000 observations. Methods specifies 32-dimensional decoding, 36 cosine neighbors, mean absolute error, and five PCA components fitted across the animal's data. | Mean error is primary. The existing four-rat, half-neuron, 1,999-row Achilles panel is a prospective extension, not the same published comparison. |
| [Official decoding notebook](https://raw.githubusercontent.com/Dynamics-of-Neural-Systems-Lab/MARBLE/09491ec077bf153b7dece8518cc65ddaa20eb26d/examples/rat_hippocampus/decoding.ipynb), `split_data`, preprocessing and model-loading cells | Selects Achilles; chronological 80/20 split; PCA20 fit on training, applied to query; loads three Dataverse checkpoints. The main comparison plots per-row absolute errors with a mean point plot; a later plot uses the helper's median. | Neither the checkpoint's training membership nor paper preprocessing equivalence follows from this evaluation notebook. Never substitute median for the published mean. |
| [Official training notebook](https://raw.githubusercontent.com/Dynamics-of-Neural-Systems-Lab/MARBLE/09491ec077bf153b7dece8518cc65ddaa20eb26d/examples/rat_hippocampus/run_marble_and_cebra.ipynb), CEBRA training loop and MARBLE loop | The loops pass each complete recording to fitting; CEBRA-behavior also receives complete behavior labels. MARBLE preprocessing requests PCA10. | These cells do not establish a label-held-out historical comparator, nor prove how the released checkpoints were trained. Keep checkpoint lineage unresolved. |
| [Official helper](https://raw.githubusercontent.com/Dynamics-of-Neural-Systems-Lab/MARBLE/09491ec077bf153b7dece8518cc65ddaa20eb26d/examples/rat_hippocampus/rat_utils.py), `convert_spikes_to_rates` and `decoding_pos_dir` | Drops a final row for forward differences; computes both per-row errors and a median. Treats sample indices as milliseconds; notebook describes 25-ms input bins. | The existing segment-specific last-row omissions are explicit. Physical-time smoothing correspondence needs resolution. Interpreting width10 as ten input bins is a source-based inference, not a publication finding. |
| Existing `fit-closed-comparator` source | Uses a train-only prospective implementation with common row support across methods. Its scorer already returns both mean and median. | Reuse its mean-error diagnostics without modifying old scores. Its locally authored controller is not a substitute for an authenticated author baseline. |

The publication's generic fitting description, notebook recipes and post-publication code revision are not silently reconciled. Query graph construction and temporal preprocessing can use query neural context, so the proposed extension is offline reconstruction; no causal or online-decoding claim follows.

## Exact public input and baseline routes

The canonical task records Harvard Dataverse DOI `10.7910/DVN/KTE4PC`, dataset version `12.0` (version ID `420908`), file ID `7609512`, file metadata version `1`, publisher MD5 `c94ab6ce283030f215a75e4919eef37c`, and prior-acquisition SHA256 `29dffd951853a98615827e7b8f3507907f9e0f0ef67e875410778ab4aadd42ab`. These are inherited public task descriptors, not a new payload hash or schema validation. The current data payload was not opened.

The official decoding notebook identifies Achilles32D checkpoint routes `7659512` (MARBLE), `7609517` (CEBRA-time), and `7609520` (CEBRA-behavior). Their bytes, digests, training provenance and numeric results remain unadmitted. No checkpoint was downloaded or deserialized. `BASELINE_MANIFEST.json` preserves these missing fields as null. The other three rats' exact publication checkpoints are unresolved.

The existing protocol's row intervals are frozen in `EPISODE.json`: Achilles/Cicero/Gatsby have raw rows `[0,10000)`, fit input `[0,8000)`, fit output `[0,7999)`, query input `[8000,10000)`, query output `[8000,9999)`; Buddy has raw `[0,6577)`, fit input `[0,5261)`, fit output `[0,5260)`, query input `[5261,6577)`, query output `[5261,6576)`. These identities label the existing extension only. They cannot satisfy Figure5d's different support merely by changing its reported sample count.

## Current-best comparison

Current best is **unknown**. CEBRA is a verified historical author-used competitor, not a verified present-day winner. [EbC Appendix C.5](https://arxiv.org/html/2510.21706v1#A3.SS5) is a concrete later comparison on the same underlying data family, but uses three rats, behavior supervision, KNN3, a different split and median errors. It reports performance comparable to CEBRA. Those results cannot be ranked against this task without a matched rerun. No matched latest SOTA result was verified by the focused primary-source search.

## Admission boundary

The next useful same-task work is recovering authentic historical checkpoint/recipe/result provenance and an exact paper evaluation support manifest. It must resolve the differences above before candidate execution. A predeclared meaningful-improvement and uncertainty rule must use defensible independent units; 2,000 correlated time bins are not 2,000 independent animals. No universal margin or significance threshold is supplied.

All data are public. Not reading labels during this build does not make them secret or certify an uncontaminated confirmation set. Candidate access isolation, exposure history, native runtime, budgets and reference competence remain external gates. The repository's earlier pilot established none of these paper-improvement claims.
