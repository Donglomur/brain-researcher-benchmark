# Direct artifact grading routes

These five source routes grade complete, finished submissions. Follow the linked
guide for the exact command, interpreter/dependencies, submission schema and
input/reference commitments. Operators must separately provision the accepted
assets; this checkout does not contain the private references or complete neural
input packets.

| Existing task/profile | Command guide and finished submission | Required external assets |
| --- | --- | --- |
| TMS fixed-region reconstruction (`PAPER-paper-signal-add-021`) | [TMS artifact commands](../../components/tms-fixed-region-artifacts/README.md): validate and freeze both complete JSON arms, then `score-pair`. | Accepted four-file input projection; private fixed-region reference; lawfully supplied paper and selected official code for the declared A/B conditions. CPython 3.11.6 is required for scoring. |
| Across-day motor decoding (`NEURAL-023`) | [Motor artifact command](../../benchmarks/neuroscience/neural-023/external-artifact-v1/README.md): `external_score.py` grades the complete 22,091-row prediction NPZ. | Exact source-day/calibration/assessment inputs and coordinate manifest; separate private assessment targets and reference metrics. Use the guide's Python/NumPy environment and explicit dependency root. |
| Purkinje morphology (`PAPER-FIND-REP-013`) | [Purkinje artifact commands](../../components/purkinje-artifacts/README.md): `inputs`, `freeze`, then `score` for the complete ten-tree numerical output. | Exact fifteen-file provider input packet and five private numerical references; CPython 3.11.6. Arbitrary raw SWCs do not replace the accepted packet. |
| Optogenetics central panels (`PAPER-FIND-ADD-015`) | [Optogenetics artifact command](../../components/opto-central-artifacts/README.md): `artifact_score.py` grades `central_submission.zip`. | Complete accepted 18-file participant packet and three private reference files; CPython 3.12.8 with NumPy 2.2.6. The guide retains the scope and provenance limits of this processed-data reconstruction. |
| Active-to-passive movement decoding (`NEURAL-022`) | [NEURAL-022 artifact command](../../components/neural022-artifact-grading/README.md): `private/score.py` grades a commitment binding all 92 prediction rows. | Authorized local neural packet, actual case roster, private target/seven-reference NPZ, fixed-reference scalar checks and operator manifest in a private package copy; Python 3.12 with NumPy 2.3.5. |

Use these direct commands: the generic `neurobench score` command is not a
selector for all finite profiles. Artifact graders do not execute participant
programs or certify producer shutdown, fitting provenance or protected access.
Keep references and score feedback outside participant access according to the
study policy. Source publication grants no additional data redistribution rights
and adds no benchmark IDs, authentic runs or qualification claims.
