# Original Figure 3 output reduction

This addition recovers the original Figure 3b endpoint from the author notebook
and applies it to the complete released C1–D1 result panel. It leaves both
predecessor implementations and the canonical task unchanged.

The recovered notebook fixes the contextual comparison at **zero-based layer 5,
time indices 17–19**, corresponding to **−300, −200 and −100 ms** in the C1
−2000…1900 ms output. It averages the three correlations within each session,
then averages the fourteen session values equally. It does not maximize over
time or layer, average people equally, or weight this endpoint by neuron count.
Syntactic, word2vec and combined controls use their three original C3 bins, with
matching shuffled controls retained. These rules are bound to source cells 4–10
in [SOURCE_MAP.json](SOURCE_MAP.json).

`source_panel.py` reads all **224 original NPY files**: sixteen fields for every
one of the fourteen sessions, including all 567 released `fr_matrix` neuron
columns and their complete 40 × 33 D1 panels. It validates NPY headers before
allocating arrays, hashes the exact decoded bytes, and refuses missing controls,
changed shapes, invalid correlations or truncated payloads. Source NaNs remain
undefined; the primary endpoint never silently removes a session.
The expected output shapes are derived from retained input-header counts and
the source scripts' array allocations. Authentic D1 output headers and numerical
values have not been opened in this work; the released 567-row layout does not
by itself reconcile the original 579-neuron cohort.

`figure3.py` calculates the fixed Figure 3b summary and separate Figure 3c/3d
companion summaries. It also retains unweighted population and neuron-average
40 × 33 dynamics, with explicit per-cell defined-neuron counts. Figure 3c has
its own source group-mean layer selection; that selection is never used for
Figure 3b. The Figure 3b permutation observations are retained as 14 × 3 values,
but the source permutation tests and the Figure 3c exponential fit are not run.

Two original joins remain incomplete. Figure 3e's weighted population display
uses counts from `self_FR_aligned2word.npy`; replacing those counts with the 567
`fr_matrix` columns would be unjustified. Figure 3f starts with 579 selectivity
rows and applies `trans_ind.npy` before joining the D1 rows. The notebook reveals
that mapping route, but neither its values nor the reason for the twelve-row
difference has been verified. Both outputs are explicitly marked uncomputed.

For an operator-provided original `result_llm` directory:

```sh
python figure3.py --result-root /operator/result_llm --output /operator/summary.json
python figure3.py --result-root /operator/candidate/result_llm \
  --reference-root /operator/author/result_llm --output /operator/comparison.json
```

The comparison reports reproduction discrepancies over every field separately
from the fixed Figure 3b improvement delta. It retains paired session differences
and participant clusters, without imposing a new equal-person primary score.
No binary reproduction threshold, participant uncertainty test or scientific
win is invented. Supplied result files do not authenticate candidate execution
or source preprocessing. The same evaluator can serve paired paper+data and
paper+data+author-code conditions only after those observation deliveries and
execution provenance are bound by the operator.

Eight generated tests cover fixed selection, session weighting, all companions,
undefined support, complete source-format loading, the CLI comparison, unsafe
NPY headers and coverage failures. They are software evidence, not a reproduced
paper result or improvement. No neural arrays, author result arrays, model
inference, fitting, new solver trial or statistical experiment was run here.
The original unrounded baseline, source/adapter parity, weighted and selectivity
joins, and complete protected evaluation remain unqualified.

The recovered source is [Zenodo record 20128462](https://zenodo.org/records/20128462),
`analysis/computation/figure/Figure3.ipynb`, distributed under the record's
CC BY 4.0 license. The exact notebook member was retrieved as a 189,998-byte
HTTP range and authenticated against the retained ZIP member size and CRC.
The whole archive MD5 was not recomputed. Raw notebook outputs and acquisition
receipts remain outside the repository; only source identities and methods are
recorded here.
