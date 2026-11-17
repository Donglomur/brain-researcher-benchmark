# NPvC signed-network scientific component

This implements the graph calculation underlying Figure 5c/d of the existing
PAPER-CANDIDATE-20261114-NPVC task, plus the finite-size two-pool forward model.
It is a complete deterministic operation on a supplied graph population. It is
not a complete reproduction of the registered Figures 2–6 benchmark.

For every supplied session/condition graph it counts **all unordered triples**,
retaining all ten multisets of information-limiting (-1), independent (0), and
information-enhancing (+1) edges. It computes the paper's closed/(closed+open)
clustering coefficient separately for IE and IL edges. This differs from the
common transitivity convention that counts three centered wedges per triangle.
It also evaluates every supplied within-graph edge-label permutation and reports
observed-minus-shuffled probabilities and clustering coefficients. Independent
edges remain present, with their full diagnostic counts. Undefined denominators
are explicit; an undefined shuffle is never omitted from a mean.

`motifs.py` uses Python's standard library. Generated controls are in
`test_motifs.py`. No original data, author implementation, dependency payload,
fitted NPvC model, or historical numerical answer is included.

## Inputs and interface

```
python3 -I -S -B motifs.py --manifest MANIFEST.json --records GRAPHS.jsonl --output FRESH_REPORT.json
```

The manifest has exactly `schema: npvc-motif-input-v1`, the existing `task_id`,
`cases`, `shuffle_ids`, and `two_pool_models`. Each case has `case_id`, `animal_id`,
`session_id`, `projection`, `outcome`, `task_variable`, `neuron_ids`, and a
`classification_provenance` identifier. The caller must externally freeze and
authenticate the full original population and the classification provenance.
Allowed projection labels are ACC, RSC, contralateral_PPC and unlabeled; outcome
labels are correct/incorrect; task variables are choice/sample_cue/test_cue.
An empty, missing, or duplicated case is not silently recovered. These enum
labels do not prove the authentic complete session roster or mouse identities.

Records are ordered by the manifest cases. Each begins with an observed record
containing exactly `case_id`, `kind: observed`, and `labels`. Labels follow the
lexicographic upper triangle of the supplied neuron order: (0,1), (0,2), ...,
(1,2), ... . Every pair must appear once, even when its label is zero. For each
prescribed shuffle ID, one record then contains `case_id`, `kind: shuffle`,
`shuffle_id`, and `permutation`. This is a complete bijection of pair-slot
indices; it preserves all three edge counts within the current graph. No data
or labels move between sessions. The output retains every shuffle's counts,
probabilities, clustering and differences. A finite roster of shuffles is
required; no random seed, bootstrap sample, or shuffle count is invented.

Each optional two-pool point specifies `model_id`, even `n`, `p`, `delta1`,
`delta2`. The exact finite equal-pool model computes the between-pool probability
by conservation of the expected total edge count. Inadmissible probabilities
are refused without clipping. Empty model grids are permitted because no
historical figure grid has been recovered. No inverse fit is performed.

The source enforces complete-input byte/work limits and fails rather than
subsampling. Present ceilings are 512 nodes/case, 1,024 cases, 10,000 named
shuffles, 100 million pair visits, 8 MiB/record, a 256 MiB graph-record stream
plus a separately capped 8 MiB manifest, and 8 MiB compact
accumulated case-result material. These engineering ceilings are not paper
eligibility rules or permission to reduce the full population. Full authentic
runtime/memory feasibility remains unqualified; a larger required operation
must be explicitly prepared, not quietly truncated. The CLI is a scientific
component, not a protected filesystem/process owner. A future owner must supply
contained regular files, resource admission, commitment, and private output
custody. The fresh-output check alone does not provide that isolation.

## Scientific limits

No authentic graph manifest has been created. All 70 released files and every
paper-eligible population remain required by the unchanged task contract.
Pair labels require source-supported preprocessing, fitted conditional
interaction information, the original two-second time window, and multiple-test
classification. This component consumes those labels and does not validate them.

The paper specifies 100 bootstrap subsamples. Neither their exact sample maps
nor the final session/animal weighting and historical shuffle draws were
recovered. This implementation supplies per-graph full-population point
calculations and explicit shuffle comparisons; it supplies **no confidence
interval, t test, population-level significance, or historical bootstrap claim**.
Triplets are not treated as independent animals. No cross-session aggregate is
silently substituted for the missing historical weighting. The optional exact
uniform-permutation expectation is an analytic diagnostic, distinct from the
finite supplied shuffles and from bootstrap uncertainty.

The two-pool forward model is also distinct from the empirical fixed-count
shuffle: its edge draws are independent Bernoulli variables. No Figure 6
information-per-motif weights, population-information curve, trained model,
protected A/B run, model improvement, or successful paper reproduction follows
from these graph outputs. Output `numerical_pass` stays null; readiness and task
counts do not increase.
