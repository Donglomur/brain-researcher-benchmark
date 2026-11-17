# Verification benchmark — track (retired approach; lesson kept)

We explored a second benchmark family — **verification**: instead of testing
whether a model *does* an analysis well (the doer tasks `GRADIENT-001`,
`SOCIALBRAIN-001`, `DEVCONN-001`), test whether a model can **audit another
model's finished analysis and judge whether the science is valid**.

**Status: the "fabricate an analysis and inject a flaw" approach was retired as
inauthentic.** This file keeps the reasoning so the mistake isn't repeated.

## Why it was retired

To hand a model "another analysis to audit," you almost always have to
**fabricate that analysis and plant a flaw** — a lot of post-processing that is
**not a real scientific workflow**. In practice that scaffolding is also where it
broke: the planted flaw ended up *not actually in the code as run* (a library API
did something different from what the write-up claimed), so the answer key graded
a **fabricated description** rather than the code — which would score a *competent*
reviewer WRONG for reading the code correctly.

**Principle:** a good task comes **directly from a paper with minimal
post-processing**. If it needs heavy artificial scaffolding, it isn't authentic.

## The important corollary

"Can a model catch bad science" is **already covered, authentically, by the doer
format.** `DEVCONN-001` asks a model to reproduce a developmental-connectivity
finding and it must notice, un-cued, that the effect is really **head motion** —
that *is* verifying whether the science holds, reached with zero fabrication.

The only authentic *pure*-verification path left would be auditing a **real
published paper whose real analysis was really refuted** (a finding plus its
failed replication). Its ground truth leans on the refutation literature; worth
doing only if that specific narrative is wanted. Not being pursued now.

## Where things stand
- No active verification task. `VERIFY-CLUSTER-001` (seeded on Eklund 2016
  *Cluster failure*) was **dropped and deleted**.
- Work continues in the **doer** family — reproduce a real paper's real analysis
  on real data, judgement embedded in reality.
- The live tracker keeps an (empty) verification section reserved for a possible
  future real-refuted-paper audit. Ask the maintainer for the URL.
