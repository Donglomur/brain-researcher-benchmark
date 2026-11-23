# Mixed text and figure analysis results

The active investigator loop now preserves textual and numerical analysis
evidence when the same result contains figures. Previously, the image branch
removed the entire `evidence` object from the text message, so a result containing
both a summary and `images` delivered the figures but silently lost the summary.
Even an empty `images` list suppressed the remaining evidence.

The revised branch removes only `images` from the copied text payload. Inline
image bytes, order, provenance, image limits and ordinary text-only results retain
their existing handling. The original analysis result is not mutated. Text is
still subject to the existing output-byte limit; oversized evidence is refused,
not silently truncated. The effective source manifest and its downstream pins
identify this revised delivery behavior; historical predecessor source is retained.

Run the generated controls from the repository root:

```sh
python3 -I -S -B benchmarks/neural/NEURAL-004/implementations/mixed-analysis-evidence-v1/test_mixed_evidence.py
```

These controls exercise the actual investigator loop with in-memory process and
provider doubles. They inspect the next generated request, including mixed text,
numeric evidence, inline figures, empty image lists and unchanged limits. They
execute no participant Python, provider, authentic EEG, target access or fit.
Existing protected-grading identity controls also verify the revised source-pin
chain. Delivery checks establish neither provider compatibility nor scientific
performance. Full authentic source admission, reference competence, participant
isolation and runtime qualification remain open.
