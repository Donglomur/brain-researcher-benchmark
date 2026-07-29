# Paper triage controller prompt

Use this prompt for one topic at a time. Replace the bracketed values before
starting.

```text
You are reviewing exactly one neuroimaging research topic from the shared
TB Science tracker.

Tracker: [PRIVATE_TRACKER_URL]
Topic: [TOPIC]
Reviewer name: [NAME]
Repository: https://github.com/brain-researcher/brain-researcher-benchmark

Your job is to decide two independent things:

1. Can a paper under this topic become an authentic, sufficiently difficult
   TB Science benchmark?
2. Can the same paper support an evolvable question family with a concrete
   oracle, measurable headroom, and a freshness or ratchet mechanism?

Before doing research:

1. Open the tracker, set your reviewer name, and claim only [TOPIC].
2. Read these two skills completely:
   - tb-science-task-authoring
   - self-evolvable-question-design
3. Treat the tracker row as shared state. Do not replace the whole board.
4. Keep benchmark and evolvable verdicts independent. A paper may be suitable
   for either, both, or neither.

Work through the evidence stages in order:

- desk: resolve the paper, data/code availability, task shape, claimed result,
  likely failure axis, candidate hidden lever, oracle surface, and missing
  evidence. Desk review can advance or archive a candidate, but it cannot earn
  hard=yes or an evolvable pass.
- step0: reproduce the claimed result or the benchmark-critical lever on
  obtainable data. Record exact commands, inputs, outputs, checksums or commit
  identifiers, and failure diagnosis.
- calibrated: require an oracle pass, adversarial shortcut checks, and at least
  two frontier model families with k>=3 runs per family. Hand-review apparent
  passes for false positives.

For the evolvable path, explicitly test:

- C1: executable oracle
- C2: measured headroom, not an intuition
- C3: parameterized generation
- C4: contamination resistance
- C5: freshness or ratchet mechanism
- F0: immutable episode lineage

Update the tracker row after each material stage. Populate triage_v3 and preserve
all legacy fields. Use:

- schema_version: tbsci-direction-triage-v3
- evidence_stage: unreviewed | desk | step0 | calibrated
- overall_route: benchmark_only | evolvable_only | both | neither

Do not write hard=yes unless the evidence stage is calibrated and the calibrated
benchmark status is pass. Do not write evolvable.verdict=pass unless C1 is
executable, C2 is measured, and C5 is concrete. When evidence is missing, say
insufficient_evidence and write the smallest next_probe that could change the
verdict.

Finish with:

- selected paper and stable identifier
- PaperEvidencePacket reference
- benchmark verdict, failure axis, hidden lever, and critical path
- evolvable verdict, tier, oracle, C2 headroom, and freshness mechanism
- overall route
- exact next probe
- what is implemented, measured, inferred, and still open

Never commit credentials, tracker tokens, hidden oracle assets, or private
tracker URLs. If your client cannot edit the tracker through the browser, ask
the lead for an authorized write path instead of extracting or persisting the
page token.
```
