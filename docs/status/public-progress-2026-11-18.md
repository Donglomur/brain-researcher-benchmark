# Public progress — November 18, 2026

The fork now publishes a complete 936-case ABR observation release and records
new original-data preparation evidence for Jaxley and NEURAL-063. The links below
show what is available and what remains to establish scientific outcomes.

The [source publication in PR #213](https://github.com/Donglomur/brain-researcher-benchmark/pull/213)
was merged at commit `8c342a4be77378c3790d53a7104b0078689f5cd4`.
Its accepted head passed 26 hosted workflow runs and 260 checks. Those checks verify
software; they do not establish reproduction, improvement or neural-model quality.

## Paper track: reproduction and improvement

The [Jaxley original-data diagnostic](../../benchmarks/paper/PAPER-paper-method-002/docs/jaxley-original-data-diagnostic.v1.md)
reached its 540-second science deadline after completing at least 300 of 1,500
frames. Morphology construction took 1.696 seconds, and all 15 fields were
prepared. This locates the remaining work in sustained frame processing; the exact
last completed frame was not observed. There is no complete candidate output,
model training result, paper reproduction, improvement or SOTA result from this
run. Completion and scientific evaluation remain open; a longer timeout alone
has not been shown to resolve them.

## Neural track: interpretation and tool/model building

The [ABR observation release](https://github.com/Donglomur/brain-researcher-benchmark/releases/tag/abr-observations-v1-20261118)
contains 936 complete case packets from 104 mice, with 16,226 traces. All four
published asset names, sizes and service SHA-256 digests were verified. Use the
[tagged operator guide](https://github.com/Donglomur/brain-researcher-benchmark/blob/abr-observations-v1-20261118/benchmarks/neural/NEURAL-SCOPE-20261114-ABR-TRANSFER/implementations/native-delivery-v1/OPERATOR_GUIDE.md)
to verify the download, view cases and create manual submissions through sealing.
Scoring requires separate protected evaluator inputs. The observations retain raw
amplitudes and native sample indices; physical calibration remains unestablished.
The release carries no AI or participant scores, clinical-accuracy result or
expert-equivalence claim.

For [NEURAL-063, one authentic original metadata/support unit succeeded](../../benchmarks/neural/NEURAL-063/docs/original-metadata-qualification.md).
The prescribed source series has 48,147 rows and one column, and its complete
referenced ROI table has one row. These are source-metadata findings: no neural
values were decoded or projected. The other 1,935 planes remain unattempted, and
all 703 sessions remain incomplete. Full-cohort metadata, support and source-range
preparation must precede neural-value projection and model or scoring work.

These updates leave the existing inventory at **235 registrations: 117 paper and
118 neural**. They do not change the published zero-improvement-ready audit or the
eight historical scored attempts. The [status index](README.md) retains those
reports and their original scopes; the [four-outcome definitions](../design/four-outcomes.md)
explain the separate scientific requirements for each track.
