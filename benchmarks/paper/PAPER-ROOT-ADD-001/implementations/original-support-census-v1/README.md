# Original language support census

This component determines the original C1–D1 held-sentence schedule before a
protected candidate run is admitted. It preserves all14 sessions/eight people,
4,209 jobs/session (58,926 total),33 supplied PCA feature layers and the224 output
arrays. It fits no model, produces no predictions and evaluates no scientific
score. It does not replace the original schedule with the older70-fold task.

The accepted preparation receipt contains member hashes, not the support masks
needed to count held-sentence invocations. The census therefore reads exactly56
already-acquired members:14 transcription CSVs,14 speaker matrices,14 sem_syn and
14 word2vec embeddings. This is authentic support preparation. It traverses and
authenticates each complete selected ZIP member against the pinned prior
preparation SHA/CRC. Only timing/qid, speaker column0 and first-PC NaN inclusion
bits become numerical operands. It reads no firing-rate member, context/random/
ngram features, self_FR response values or analysis results. Full selected
lexical-member traversal is charged even though only missingness is used.

`ArchiveView` meters every Python-level archive read, including directory reads
and repeated seeks. Unbuffered reads must lie wholly inside frozen selected
member segments or metadata tails; selected local-header offsets also match the
cached source roster. Only the small transcription ZIP permits whole-container
coverage. Expanded members have a separate pre-read allocation.
Selected member hashes authenticate their complete contents; whole-archive
checksums are not repeated and are not claimed to have been reverified. The
already-accepted preparation receipt is itself required at its exact SHA.
Archive extents and ordinary-file identities remain stable throughout intake.

`session_census` reproduces word overwrite order, sentinel behavior, speaker
filtering, positive-lag zero-qid padding, lexical exclusions and all145 field/lag
groups. Centered response smoothing is represented by source-row lineage;
negative-lag zero padding and the original NumPy seed20 permutation are included.
No response value is required to identify which source response rows are exposed.

Equal support signatures prove equal complete ordered input-time support, qid
grouping, output kind and response-row lineage. Each held qid within a signature
remains a separate isolation unit. This is a conservative sufficient partition;
it is not advertised as the coarsest possible partition. All layer/feature jobs
remain distinct. Equality is not permission for a model to combine feature
layers or carry state across different held-label boundaries. A later executor
must prove its concrete batching and candidate-state policy separately.
These signatures are not `bridge.request_identity` hashes: those require the
full feature and training-response bytes and are not computed here.

The output is operator-private. It retains recoverable timing/qid and support
bits in14 NPZ files, binds the repeated held-group rosters by hashes, and reports
the exact source invocation count and proven equivalence-unit count. It also
computes cumulative unbatched six-array payload, NPY headers, bounded request/
index JSON, f64 prediction output, and private-product payload/reserve costs.
These are logical serialization costs, not peak disk, total kernel I/O or a
measured wall-time estimate. No full run is admitted merely by passing census.
Centered smoothing, global PCA and shuffled controls retain their original
statistical dependencies; isolation cannot retrospectively remove them.

Generated verification:

```
python3 -I -B benchmarks/paper/PAPER-ROOT-ADD-001/implementations/original-support-census-v1/test_census.py -v
```

Controls compare all4,209 generated jobs against the unchanged original request
constructor, test full response lineage and payload accounting, and exercise
restricted archive intake, mismatches, caps, replacement, repeated reads and
support boundaries. They do not execute Docker or authentic science.

The command-line census requires explicit existing archive paths, the accepted
preparation path, finite archive/expanded/output limits and a fresh output
directory. Authentic execution additionally requires the separately reviewed
root protocol. There is no download, install, candidate execution or scorer in
this component. A protected per-source-fold executor and its runtime
qualification remain separate work.
